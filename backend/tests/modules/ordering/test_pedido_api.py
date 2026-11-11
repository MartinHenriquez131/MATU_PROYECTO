"""MATU-61 · El pedido sin pagar contra PostgreSQL (RF-21, ADR-027; decisiones 193 a 219; C1 a C10).

Camino feliz (crear, confirmar, resumen), lo que falta al confirmar (C5), el total que vence a los 15 minutos según el
Reloj, volver a confirmar y cambiar el pedido (C1, C9), los roles (C3), la autorización de pedidos (403), otro grupo
(404), la idempotencia, cancelar, el retiro de despacho y el borrado de la persona con un pedido sin pagar (D1, D2),
la dirección sin la autorización (C8), y que nada del pedido vaya a los logs.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from tests.base_datos import DSN, requiere_base
from tests.modules.ordering.conftest import COSTO_ENVIO, DIRECCION, TELEFONO, EntornoPedido

pytestmark = [pytest.mark.rf("RF-21"), requiere_base]


def _crear_y_confirmar(entorno: EntornoPedido, **kwargs: Any) -> tuple[Any, dict[str, Any]]:
    familia = entorno.lista_para_pedir(entorno.fabrica.familia())
    entorno.hay("panal", "uno")
    creado = entorno.crear(familia, [{"oferta_id": entorno.oferta("panal", "uno"), "cantidad": 2}])
    assert creado.status_code == 201, creado.text
    confirmado = entorno.confirmar(familia, creado.json()["id"], **kwargs)
    assert confirmado.status_code == 200, confirmado.text
    return familia, confirmado.json()


def _auditoria(pedido_id: str) -> list[str]:
    with psycopg.connect(DSN) as cx:
        return [
            f[0]
            for f in cx.execute(
                "SELECT accion FROM auditoria WHERE entidad = 'pedido' AND entidad_id = %s ORDER BY id", (pedido_id,)
            )
        ]


def _transiciones(pedido_id: str) -> list[tuple[str | None, str, str | None]]:
    with psycopg.connect(DSN) as cx:
        return [
            tuple(f)
            for f in cx.execute(
                "SELECT desde, hacia, motivo FROM pedido_transicion WHERE pedido_id = %s ORDER BY id", (pedido_id,)
            )
        ]


# --- Camino feliz ---------------------------------------------------------------------------------------------------


def test_crear_y_confirmar_el_total_con_un_solo_envio(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia = e.lista_para_pedir(e.fabrica.familia())
    e.hay("panal", "uno")
    e.hay("crema", "dos")

    creado = e.crear(
        familia,
        [
            {"oferta_id": e.oferta("panal", "uno"), "cantidad": 2},
            {"oferta_id": e.oferta("crema", "dos"), "cantidad": 1},
        ],
    )

    assert creado.status_code == 201, creado.text
    borrador = creado.json()
    assert creado.headers["Cache-Control"] == "no-store"
    assert creado.headers["Location"] == f"/v1/pedidos/{borrador['id']}"
    assert creado.headers["ETag"] == borrador["etag"] == '"v1"'
    assert borrador["estado"] == "borrador" and borrador["total"] is None and borrador["entrega"] is None
    assert borrador["costo_envio"] == COSTO_ENVIO and borrador["ventana_entrega"] == "Entre 24 y 48 horas hábiles"
    assert [x["regla_faltante"] for x in borrador["lineas"]] == ["otro_comercio", "otro_comercio"]
    assert "grupo_id" not in borrador and "creado_por" not in borrador

    confirmado = e.confirmar(familia, borrador["id"])

    assert confirmado.status_code == 200, confirmado.text
    pedido = confirmado.json()
    assert pedido["estado"] == "total_confirmado"
    # Total = suma exacta de cantidad × precio + un solo envío, aunque lo preparen dos comercios (C5)
    assert pedido["subtotal_productos"] == 2 * 12990 + 7290
    assert pedido["total"] == 2 * 12990 + 7290 + COSTO_ENVIO
    assert [p["subtotal_productos"] for p in pedido["comercios"]] == sorted(
        [2 * 12990, 7290], key=lambda s: s != 2 * 12990
    ) or len(pedido["comercios"]) == 2
    vence = datetime.fromisoformat(pedido["vence_en"])
    assert vence - datetime.fromisoformat(pedido["total_confirmado_en"]) == timedelta(minutes=15)
    assert pedido["vigencia_segundos"] == 900
    assert pedido["entrega"]["calle"] == DIRECCION["calle"]
    assert (pedido["entrega"]["telefono_contacto"], pedido["entrega"]["telefono_origen"]) == ("+56955550177", "escrito")
    assert pedido["resumen"]["vendedor"] == "MATU, piloto académico, sin persona jurídica"
    assert pedido["resumen"]["condiciones"]["enlace"] == "/v1/condiciones-pedido"
    assert all(x["cambio"] is None for x in pedido["lineas"]) and pedido["salieron"] == []
    assert _auditoria(pedido["id"]) == ["pedido.crear", "pedido.confirmar"]
    assert _transiciones(pedido["id"]) == [(None, "borrador", None), ("borrador", "total_confirmado", None)]


def test_las_condiciones_del_pedido_son_publicas_y_calzan_con_el_resumen(entorno_pedido: EntornoPedido) -> None:
    _, pedido = _crear_y_confirmar(entorno_pedido)
    respuesta = entorno_pedido.iam.cliente.get("/v1/condiciones-pedido")
    assert respuesta.status_code == 200 and respuesta.headers["Cache-Control"] == "no-cache"
    assert respuesta.json()["huella"] == pedido["resumen"]["condiciones"]["huella"]
    assert respuesta.json()["version"] == "0.1"


# --- Si falta un producto (C5) --------------------------------------------------------------------------------------


def test_otro_comercio_busca_el_mismo_producto_y_quitar_lo_saca(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia = e.lista_para_pedir(e.fabrica.familia())
    e.hay("panal", "dos")  # el carrito lo tiene en «uno», que no tiene stock
    e.hay("bolsa", "dos")
    creado = e.crear(
        familia,
        [
            {"oferta_id": e.oferta("panal", "uno"), "cantidad": 1},
            {"oferta_id": e.oferta("bolsa", "uno"), "cantidad": 1},
        ],
    ).json()
    bolsa = str(e.catalogo.productos["bolsa"])
    reglas = e.pedir(
        "PUT",
        f"/v1/pedidos/{creado['id']}/reglas-faltante",
        familia.admin,
        familia,
        {"reglas": [{"producto_id": bolsa, "accion": "quitar"}]},
        **{"If-Match": creado["etag"]},
    )
    assert reglas.status_code == 200, reglas.text

    pedido = e.confirmar(familia, creado["id"]).json()

    [linea] = pedido["lineas"]
    assert linea["producto"]["id"] == str(e.catalogo.productos["panal"])
    assert linea["comercio"]["id"] == str(e.catalogo.comercios["dos"]) and linea["precio_unitario"] == 9990
    assert linea["cambio"]["precio_antes"] == 12990
    assert linea["cambio"]["comercio_antes"]["id"] == str(e.catalogo.comercios["uno"])
    # Con quitar, sale aunque otro comercio lo tenga
    assert [s["producto"]["id"] for s in pedido["salieron"]] == [bolsa]
    assert pedido["total"] == 9990 + COSTO_ENVIO
    assert "pedido.regla_faltante" in _auditoria(pedido["id"])


def test_nada_disponible_no_cambia_el_pedido(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia = e.lista_para_pedir(e.fabrica.familia())
    creado = e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}]).json()
    respuesta = e.confirmar(familia, creado["id"])
    assert respuesta.status_code == 409 and respuesta.json()["type"] == "/errores/nada-disponible"
    assert e.pedir("GET", f"/v1/pedidos/{creado['id']}", familia.admin, familia).json()["estado"] == "borrador"


# --- Vencimiento, volver a confirmar y cambiar (C1, C9) -------------------------------------------------------------


def test_el_total_vence_a_los_15_minutos_y_se_vuelve_a_confirmar(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia, pedido = _crear_y_confirmar(e)
    e.avanzar(timedelta(minutes=15))

    visto = e.pedir("GET", f"/v1/pedidos/{pedido['id']}", familia.admin, familia).json()
    assert visto["estado"] == "vencido" and visto["vigencia_segundos"] == 0 and visto["resumen"] is None

    otra = e.confirmar(familia, pedido["id"], cuerpo={})
    assert otra.status_code == 200, otra.text
    assert otra.json()["estado"] == "total_confirmado" and otra.json()["vigencia_segundos"] == 900
    # El vencimiento quedó en la línea de tiempo en el instante en que venció (decisión 204)
    assert ("total_confirmado", "vencido", "total_vencio") in _transiciones(pedido["id"])


def test_volver_a_confirmar_un_total_vigente_da_15_minutos_nuevos(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia, pedido = _crear_y_confirmar(e)
    e.avanzar(timedelta(minutes=13))
    otra = e.confirmar(familia, pedido["id"], cuerpo={}).json()
    assert otra["estado"] == "total_confirmado" and otra["vigencia_segundos"] == 900
    assert datetime.fromisoformat(otra["vence_en"]) > datetime.fromisoformat(pedido["vence_en"])
    # El teléfono escrito se conserva al volver a confirmar sin cuerpo
    assert otra["entrega"]["telefono_contacto"] == "+56955550177"


@pytest.mark.parametrize("minutos", [0, 20], ids=["vigente", "vencido"])
def test_cambiar_el_pedido_vuelve_al_carrito(entorno_pedido: EntornoPedido, minutos: int) -> None:
    e = entorno_pedido
    familia, pedido = _crear_y_confirmar(e)
    e.avanzar(timedelta(minutes=minutos))
    lineas = e.pedir(
        "PUT",
        f"/v1/pedidos/{pedido['id']}/lineas",
        familia.admin,
        familia,
        {"lineas": []},
        **{"If-Match": pedido["etag"]},
    )
    assert lineas.status_code == 409 and lineas.json()["type"] == "/errores/estado-pedido"

    cambiado = e.pedir(
        "POST", f"/v1/pedidos/{pedido['id']}/cambiar", familia.admin, familia, **{"Idempotency-Key": e.clave()}
    )

    assert cambiado.status_code == 200, cambiado.text
    borrador = cambiado.json()
    assert borrador["estado"] == "borrador" and borrador["total"] is None and borrador["entrega"] is None
    assert _transiciones(pedido["id"])[-1] == (
        "vencido" if minutos else "total_confirmado",
        "borrador",
        "familia_cambia_carrito",
    )
    with psycopg.connect(DSN) as cx:
        assert cx.execute("SELECT count(*) FROM pedido_entrega WHERE pedido_id = %s", (pedido["id"],)).fetchone() == (
            0,
        )
        assert cx.execute("SELECT count(*) FROM pedido_comercio WHERE pedido_id = %s", (pedido["id"],)).fetchone() == (
            0,
        )
    ajustado = e.pedir(
        "PUT",
        f"/v1/pedidos/{pedido['id']}/lineas",
        familia.admin,
        familia,
        {"lineas": [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 3}]},
        **{"If-Match": borrador["etag"]},
    )
    assert ajustado.status_code == 200 and ajustado.json()["lineas"][0]["cantidad"] == 3


# --- Roles (C3), autorización (403) y otro grupo (404) ----------------------------------------------------------------


def test_pagador_ve_todo_y_no_confirma_y_observador_ve_el_carrito(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia, pedido = _crear_y_confirmar(e)
    pagador, observador = familia.miembros["pagador"].usuario, familia.miembros["observador"].usuario

    visto = e.pedir("GET", f"/v1/pedidos/{pedido['id']}", pagador, familia)
    assert visto.status_code == 200 and visto.json()["entrega"] is not None and visto.json()["resumen"] is not None
    assert e.confirmar(familia, pedido["id"], usuario=pagador).status_code == 404
    assert (
        e.pedir(
            "POST", f"/v1/pedidos/{pedido['id']}/cancelar", pagador, familia, **{"Idempotency-Key": e.clave()}
        ).status_code
        == 404
    )

    del_observador = e.pedir("GET", f"/v1/personas-cuidadas/{familia.persona.id}/pedido-en-curso", observador, familia)
    assert del_observador.status_code == 200
    assert not {"entrega", "resumen", "etag"} & set(del_observador.json())
    assert "ETag" not in del_observador.headers
    assert (
        e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}], usuario=observador).status_code
        == 404
    )


def test_el_cuidador_arma_confirma_y_cancela(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia = e.lista_para_pedir(e.fabrica.familia())
    cuidador = familia.miembros["cuidador"].usuario
    e.hay("panal", "uno")
    creado = e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}], usuario=cuidador).json()
    assert e.confirmar(familia, creado["id"], usuario=cuidador).status_code == 200
    cancelado = e.pedir(
        "POST", f"/v1/pedidos/{creado['id']}/cancelar", cuidador, familia, **{"Idempotency-Key": e.clave()}
    )
    assert cancelado.status_code == 200 and cancelado.json()["estado"] == "cancelado"


def test_sin_autorizacion_de_pedidos_403(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia = e.fabrica.familia()
    respuesta = e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}])
    assert respuesta.status_code == 403
    assert respuesta.json()["type"] == "/errores/sin-autorizacion-pedidos"
    assert respuesta.json()["finalidad"] == "despacho"
    assert respuesta.headers["Cache-Control"] == "no-store"


def test_otro_grupo_404(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia, pedido = _crear_y_confirmar(e)
    otra = e.fabrica.familia()
    for metodo, ruta in (
        ("GET", f"/v1/pedidos/{pedido['id']}"),
        ("GET", f"/v1/personas-cuidadas/{familia.persona.id}/pedido-en-curso"),
    ):
        respuesta = e.pedir(metodo, ruta, otra.admin, otra)
        assert respuesta.status_code == 404 and respuesta.headers["Cache-Control"] == "no-store"
    assert e.confirmar(otra, pedido["id"], usuario=otra.admin).status_code == 404


# --- Idempotencia y un solo pedido abierto -------------------------------------------------------------------------


def test_idempotencia_al_crear(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia = e.lista_para_pedir(e.fabrica.familia())
    linea = [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}]
    clave = e.clave()
    primero = e.crear(familia, linea, clave=clave)
    repetido = e.crear(familia, linea, clave=clave)
    assert primero.status_code == repetido.status_code == 201
    assert primero.json()["id"] == repetido.json()["id"]

    otro_cuerpo = e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 2}], clave=clave)
    assert otro_cuerpo.status_code == 422 and otro_cuerpo.json()["type"] == "/errores/idempotencia-reutilizada"
    otra_cuenta = e.crear(familia, linea, usuario=familia.miembros["cuidador"].usuario, clave=clave)
    assert otra_cuenta.status_code == 422

    sin_clave = e.pedir(
        "POST", f"/v1/personas-cuidadas/{familia.persona.id}/pedidos", familia.admin, familia, {"lineas": linea}
    )
    assert sin_clave.status_code == 428 and sin_clave.json()["type"] == "/errores/falta-idempotencia"
    mala = e.crear(familia, linea, clave="corta")
    assert mala.status_code == 422 and mala.json()["errores"][0]["campo"] == "Idempotency-Key"

    abierto = e.crear(familia, linea)
    assert abierto.status_code == 409 and abierto.json()["type"] == "/errores/pedido-abierto"
    assert abierto.json()["pedido_id"] == primero.json()["id"]
    with psycopg.connect(DSN) as cx:
        columnas = {
            f[0]
            for f in cx.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'idempotencia'")
        }
    assert "respuesta" not in columnas  # D5: solo el estado y el id


def test_cancelar_es_idempotente_y_borra_la_entrega(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia, pedido = _crear_y_confirmar(e)
    clave = e.clave()
    ruta = f"/v1/pedidos/{pedido['id']}/cancelar"
    primero = e.pedir("POST", ruta, familia.admin, familia, **{"Idempotency-Key": clave})
    repetido = e.pedir("POST", ruta, familia.admin, familia, **{"Idempotency-Key": clave})
    otra = e.pedir("POST", ruta, familia.admin, familia, **{"Idempotency-Key": e.clave()})
    assert (primero.status_code, repetido.status_code, otra.status_code) == (200, 200, 409)
    assert otra.json()["estado"] == "cancelado"
    with psycopg.connect(DSN) as cx:
        assert cx.execute("SELECT count(*) FROM pedido_entrega WHERE pedido_id = %s", (pedido["id"],)).fetchone() == (
            0,
        )
    assert _auditoria(pedido["id"])[-1] == "pedido.cancelar"
    assert _transiciones(pedido["id"])[-1] == ("total_confirmado", "cancelado", "familia_cancela")


def test_lineas_exige_if_match(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia = e.lista_para_pedir(e.fabrica.familia())
    creado = e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}]).json()
    ruta = f"/v1/pedidos/{creado['id']}/lineas"
    assert e.pedir("PUT", ruta, familia.admin, familia, {"lineas": []}).status_code == 428
    viejo = e.pedir("PUT", ruta, familia.admin, familia, {"lineas": []}, **{"If-Match": '"v99"'})
    assert viejo.status_code == 412 and viejo.json()["actual"]["etag"] == creado["etag"]


def test_errores_de_confirmar(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia = e.lista_para_pedir(e.fabrica.familia())
    e.hay("panal", "uno")
    creado = e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}]).json()
    # Sin teléfono ni celular verificado de quien confirma
    sin_telefono = e.confirmar(familia, creado["id"], cuerpo={})
    assert sin_telefono.status_code == 422 and sin_telefono.json()["errores"][0]["tipo"] == "telefono_requerido"
    # Sin dirección (C7)
    assert (
        e.pedir(
            "DELETE",
            f"/v1/personas-cuidadas/{familia.persona.id}/direccion",
            familia.admin,
            familia,
            **{"If-Match": '"v2"'},
        ).status_code
        == 204
    )
    assert e.confirmar(familia, creado["id"]).json()["type"] == "/errores/sin-direccion"
    # Carrito vacío
    vacio = e.pedir(
        "PUT",
        f"/v1/pedidos/{creado['id']}/lineas",
        familia.admin,
        familia,
        {"lineas": []},
        **{"If-Match": creado["etag"]},
    )
    assert vacio.status_code == 200
    assert e.confirmar(familia, creado["id"]).json()["type"] == "/errores/pedido-vacio"


# --- Retiro de despacho, borrado de la persona y dirección (D1, D2, C6, C8) ---------------------------------------


def test_retirar_despacho_cancela_lo_no_pagado_y_conserva_la_direccion(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    familia, pedido = _crear_y_confirmar(e)
    retiro = e.pedir(
        "POST", f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos/despacho/retiro", familia.admin, familia
    )
    assert retiro.status_code == 200, retiro.text
    assert retiro.json()["pedidos_cancelados"] == 1 and retiro.json()["enlaces_cortados"] == 0
    assert e.pedir("GET", f"/v1/pedidos/{pedido['id']}", familia.admin, familia).json()["estado"] == "cancelado"
    assert _transiciones(pedido["id"])[-1][2] == "autorizacion_retirada"
    with psycopg.connect(DSN) as cx:
        assert cx.execute("SELECT count(*) FROM pedido_entrega WHERE pedido_id = %s", (pedido["id"],)).fetchone() == (
            0,
        )
        # C6: la dirección de la persona se conserva
        assert cx.execute(
            "SELECT direccion_entrega_id IS NOT NULL FROM persona_cuidada WHERE id = %s", (familia.persona.id,)
        ).fetchone() == (True,)
    # Sin la autorización, escribir un pedido responde 403
    nuevo = e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}])
    assert nuevo.status_code == 403


def test_con_la_autorizacion_retirada_admin_vacia_la_direccion(entorno_pedido: EntornoPedido) -> None:
    """C8: la dirección es de la persona y no pide la autorización de pedidos."""
    e = entorno_pedido
    familia = e.lista_para_pedir(e.fabrica.familia())
    assert (
        e.pedir(
            "POST",
            f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos/despacho/retiro",
            familia.admin,
            familia,
        ).status_code
        == 200
    )

    vaciada = e.pedir(
        "DELETE",
        f"/v1/personas-cuidadas/{familia.persona.id}/direccion",
        familia.admin,
        familia,
        **{"If-Match": '"v2"'},
    )

    assert vaciada.status_code == 204 and vaciada.headers["Cache-Control"] == "no-store"
    with psycopg.connect(DSN) as cx:
        assert cx.execute(
            "SELECT count(*) FROM auditoria WHERE accion = 'direccion.cambiar' AND grupo_id = %s", (familia.grupo.id,)
        ).fetchone() == (2,)


def test_borrar_a_la_persona_con_un_pedido_sin_pagar(entorno_pedido: EntornoPedido) -> None:
    """D2: en la misma transacción del borrado, el pedido sin pagar se cancela y se borra su entrega."""
    e = entorno_pedido
    familia, pedido = _crear_y_confirmar(e)
    borrado = e.pedir("POST", f"/v1/personas-cuidadas/{familia.persona.id}/borrado", familia.admin, familia)
    assert borrado.status_code == 200, borrado.text
    with psycopg.connect(DSN) as cx:
        assert cx.execute("SELECT estado FROM pedido WHERE id = %s", (pedido["id"],)).fetchone() == ("cancelado",)
        assert cx.execute("SELECT count(*) FROM pedido_entrega WHERE pedido_id = %s", (pedido["id"],)).fetchone() == (
            0,
        )
        assert cx.execute(
            "SELECT motivo FROM pedido_transicion WHERE pedido_id = %s ORDER BY id DESC LIMIT 1", (pedido["id"],)
        ).fetchone() == ("persona_borrada",)


def test_nada_del_pedido_va_a_los_logs(entorno_pedido: EntornoPedido) -> None:
    e = entorno_pedido
    _crear_y_confirmar(e)
    texto = e.iam.texto_log()
    for dato in (DIRECCION["calle"], DIRECCION["comuna"], "55550177", TELEFONO, "12990", "Idempotency"):
        assert dato not in texto, dato


# --- Conservación (D5 y C10) ----------------------------------------------------------------------------------------


def test_lo_no_pagado_se_borra_a_los_30_dias_del_ultimo_cambio(entorno_pedido: EntornoPedido) -> None:
    from app.modules.ordering.infrastructure.tarea_conservacion import ejecutar
    from tests.base_datos import fabrica_scheduler
    from tests.dobles.reloj_fijo import RelojFijo

    e = entorno_pedido
    familia = e.lista_para_pedir(e.fabrica.familia())
    viejo = e.crear(familia, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}]).json()
    otra = e.lista_para_pedir(e.fabrica.familia())
    reciente = e.crear(otra, [{"oferta_id": e.oferta("panal", "uno"), "cantidad": 1}]).json()
    hace_40 = datetime.now(UTC) - timedelta(days=40)
    with psycopg.connect(DSN) as cx, cx.transaction():
        cx.execute("SET LOCAL session_replication_role = replica")
        cx.execute(
            "UPDATE pedido SET creado_en = %s, actualizado_en = %s WHERE id = %s", (hace_40, hace_40, viejo["id"])
        )
        # Creado hace 40 días, pero con un cambio hace 2 (C10): no se borra
        cx.execute(
            "UPDATE pedido SET creado_en = %s, actualizado_en = %s WHERE id = %s",
            (hace_40, datetime.now(UTC) - timedelta(days=2), reciente["id"]),
        )

    resultado = ejecutar(fabrica_scheduler(), RelojFijo(datetime.now(UTC)))

    assert resultado.pedidos_borrados >= 1
    with psycopg.connect(DSN) as cx:
        quedan = {
            str(f[0])
            for f in cx.execute("SELECT id FROM pedido WHERE id = ANY(%s::uuid[])", ([viejo["id"], reciente["id"]],))
        }
    assert quedan == {reciente["id"]}

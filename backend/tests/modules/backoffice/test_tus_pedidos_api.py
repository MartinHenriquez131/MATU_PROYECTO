"""MATU-92 · «Tus pedidos» contra PostgreSQL: la lista por rol, el seguimiento, el retracto ampliado, lo vencido, el
otro grupo, C6, C8 (idempotencia y concurrencia), C11 y C13. Solo datos sintéticos.
"""

import threading
import uuid
from datetime import timedelta
from typing import Any

import psycopg
import pytest

from tests.base_datos import DSN, requiere_base
from tests.concurrencia import esperar_bloqueada_por
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.backoffice.conftest import Despacho
from tests.modules.backoffice.test_despacho_api import PRECIO_PANAL, _codigo, _parte, _preparar_todo, _validar
from tests.modules.ordering.conftest import (
    COSTO_ENVIO,
    MONTOS_PARA_EL_OBSERVADOR,
    cifras_a_la_vista,
    claves_a_cualquier_profundidad,
)
from tests.modules.payments.conftest import pagar, pedido_confirmado, sin_sesion_volver
from tests.textos import aparece_como_dato

pytestmark = [pytest.mark.rf("RF-20"), pytest.mark.rf("RF-25"), requiere_base]

TOTAL = 2 * PRECIO_PANAL + COSTO_ENVIO
# MATU-113 (decisión 472): suma entregado_en, y el estado es el real de familia
CAMPOS_OBSERVADOR = {
    "vista", "pedido_id", "pagado_en", "estado", "entregado_en", "productos", "resumen_productos", "productos_borrados",
}


def _lista(d: Despacho, familia: FamiliaCreada, usuario: UsuarioCreado, **consulta: Any) -> Any:
    sufijo = "&".join(f"{k}={v}" for k, v in consulta.items())
    ruta = f"/v1/personas-cuidadas/{familia.persona.id}/pedidos" + (f"?{sufijo}" if sufijo else "")
    return d.e.pedir("GET", ruta, usuario, familia)


def _rol(d: Despacho, familia: FamiliaCreada, rol: str) -> UsuarioCreado:
    return d.e.usuario(familia, rol)


def _entregar(d: Despacho, pedido: dict[str, Any]) -> None:
    parte, etag = _parte(d, pedido)
    _preparar_todo(d, parte, etag)
    assert _validar(d, parte, _codigo(d, parte)).json()["resultado"] == "correcto"
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/en-camino").status_code == 200
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/entregado").status_code == 200


def _pagado_por_el_pagador(d: Despacho) -> tuple[FamiliaCreada, dict[str, Any]]:
    familia, pedido = pedido_confirmado(d.e)
    token = pagar(d.e, familia, pedido, _rol(d, familia, "pagador")).json()["token"]
    d.pasarela.pagar(token)
    assert sin_sesion_volver(d.e, {"token_ws": token}).json()["resultado"] == "aprobado"
    return familia, pedido


def _otro_pagado(d: Despacho, familia: FamiliaCreada) -> dict[str, Any]:
    """Otro pedido pagado de la misma familia, que ya tiene la autorización y la dirección."""
    d.e.hay("panal", "uno")
    creado = d.e.crear(familia, [{"oferta_id": d.e.oferta("panal", "uno"), "cantidad": 2}])
    assert creado.status_code == 201, creado.text
    confirmado = d.e.confirmar(familia, creado.json()["id"])
    assert confirmado.status_code == 200, confirmado.text
    token = pagar(d.e, familia, confirmado.json()).json()["token"]
    d.pasarela.pagar(token)
    assert sin_sesion_volver(d.e, {"token_ws": token}).json()["resultado"] == "aprobado"
    return dict(confirmado.json())


def _linea(d: Despacho, pedido: dict[str, Any]) -> str:
    [(linea,)] = d.sql("SELECT id FROM pedido_linea WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    return str(linea)


def _sin_nada_del_comercio(d: Despacho, pedido: dict[str, Any], texto: str) -> None:
    """C15: ni la referencia de la parte ni nada del código de retiro."""
    [(referencia,)] = d.sql("SELECT referencia FROM pedido_comercio WHERE pedido_id = %s", uuid.UUID(pedido["id"]))
    assert referencia not in texto
    assert "codigo" not in texto


def test_la_lista_y_el_seguimiento_por_rol(despacho: Despacho) -> None:
    d = despacho
    familia, pedido = d.pagado()
    [(referencia,)] = d.sql("SELECT referencia FROM pedido WHERE id = %s", uuid.UUID(pedido["id"]))

    # admin: el total, lo devuelto, el estado (H8) y lo que se puede hacer (C7)
    r = _lista(d, familia, familia.admin)
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"] == "no-store"
    [fila] = r.json()["items"]
    assert r.json()["siguiente_cursor"] is None
    assert (fila["pedido_id"], fila["referencia"], fila["estado"]) == (pedido["id"], referencia, "pagado")
    assert (fila["total"], fila["devuelto"], fila["devuelto_todo"]) == (TOTAL, 0, False)
    assert (fila["puede_cancelar"], fila["cancelar_motivo"]) == (True, None)
    assert (fila["puede_arrepentirse"], fila["arrepentirse_motivo"]) == (False, "sin_entregar")
    assert fila["plazo_hasta"] is None and fila["entregado_en"] is None
    assert [(x["producto"]["nombre"], x["cantidad"]) for x in fila["productos"]] == [
        (fila["resumen_productos"]["primero"], 2)
    ]
    assert fila["resumen_productos"]["otros"] == 0 and fila["productos_borrados"] is False
    _sin_nada_del_comercio(d, pedido, r.text)

    # cuidador y pagador (que no pagó): con montos, sin cancelar
    for rol in ("cuidador", "pagador"):
        [fila] = _lista(d, familia, _rol(d, familia, rol)).json()["items"]
        assert fila["total"] == TOTAL
        assert (fila["puede_cancelar"], fila["cancelar_motivo"]) == (False, "rol")

    # observador (D-92-1 a, C3): la fecha, los productos y «Pagado», nada más
    r = _lista(d, familia, _rol(d, familia, "observador"))
    assert r.status_code == 200, r.text
    [fila] = r.json()["items"]
    assert set(fila) == CAMPOS_OBSERVADOR and fila["estado"] == "pagado" and fila["entregado_en"] is None
    for nunca in ("total", "devuelto", "monto", "referencia", "puede_", "plazo", str(TOTAL), referencia):
        assert nunca not in r.text, nunca

    # El seguimiento: la parte por comercio, con su estado y sin nada del comercio (C15, C16)
    r = d.e.pedir("GET", f"/v1/pedidos/{pedido['id']}/seguimiento", familia.admin, familia)
    assert r.status_code == 200, r.text
    seguimiento = r.json()
    [parte] = seguimiento["partes"]
    assert parte["comercio"]["nombre_fantasia"] and parte["comercio"]["ficticio"] in (True, False)
    assert (parte["estado"], parte["cancelada_por"]) == ("enviada", None)
    assert [(x["cantidad"], x["unidades_faltantes"]) for x in parte["lineas"]] == [(2, 0)]
    assert (seguimiento["puede_cancelar"], seguimiento["estado"]) == (True, "pagado")
    _sin_nada_del_comercio(d, pedido, r.text)
    # El observador no tiene detalle
    observador = _rol(d, familia, "observador")
    assert d.e.pedir("GET", f"/v1/pedidos/{pedido['id']}/seguimiento", observador, familia).status_code == 404


def test_la_lista_pagina_con_cursor(despacho: Despacho) -> None:
    d = despacho
    familia, primero = d.pagado()
    d.e.avanzar(timedelta(minutes=1))
    segundo = _otro_pagado(d, familia)
    r = _lista(d, familia, familia.admin, limite=1)
    [fila] = r.json()["items"]
    assert fila["pedido_id"] == segundo["id"]
    r = _lista(d, familia, familia.admin, limite=1, cursor=r.json()["siguiente_cursor"])
    assert [x["pedido_id"] for x in r.json()["items"]] == [primero["id"]]
    assert r.json()["siguiente_cursor"] is None
    malo = _lista(d, familia, familia.admin, cursor="no-es-un-cursor")
    assert malo.status_code == 422 and malo.json()["errores"][0]["campo"] == "cursor"


def test_otro_grupo_y_un_id_que_no_es_uuid_responden_404(despacho: Despacho) -> None:
    d = despacho
    familia, pedido = d.pagado()
    otra = d.e.fabrica.familia()
    rutas = [
        ("GET", f"/v1/personas-cuidadas/{familia.persona.id}/pedidos"),
        ("GET", f"/v1/pedidos/{pedido['id']}/seguimiento"),
        ("GET", f"/v1/pedidos/{pedido['id']}/retractos"),
    ]
    for metodo, ruta in rutas:
        assert d.e.pedir(metodo, ruta, otra.admin, otra).status_code == 404, ruta
    cuerpo = {"lineas": [{"linea_id": _linea(d, pedido), "cantidad": 1}]}
    assert d.post_familia(f"/v1/pedidos/{pedido['id']}/retractos", otra.admin, otra, cuerpo).status_code == 404
    assert d.post_familia(f"/v1/pedidos/{pedido['id']}/cancelar-con-devolucion", otra.admin, otra).status_code == 404
    for ruta in ("/v1/personas-cuidadas/no-es-uuid/pedidos", "/v1/pedidos/no-es-uuid/seguimiento"):
        assert d.e.pedir("GET", ruta, familia.admin, familia).status_code == 404
    # Sigue siendo de la familia: la otra no lo canceló
    assert d.estado_pedido(pedido["id"]) == "pagado"


@pytest.mark.rf("R3")
def test_c6_el_observador_recibe_404_al_pedir_el_retracto(despacho: Despacho) -> None:
    d = despacho
    familia, pedido = d.pagado()
    _entregar(d, pedido)
    observador = _rol(d, familia, "observador")
    cuerpo = {"lineas": [{"linea_id": _linea(d, pedido), "cantidad": 1}]}
    r = d.post_familia(f"/v1/pedidos/{pedido['id']}/retractos", observador, familia, cuerpo)
    assert r.status_code == 404, r.text
    # Antes que la cabecera: sin Idempotency-Key, también 404
    sin_clave = d.e.pedir("POST", f"/v1/pedidos/{pedido['id']}/retractos", observador, familia, cuerpo)
    assert sin_clave.status_code == 404
    assert d.sql("SELECT count(*) FROM retracto WHERE pedido_id = %s", uuid.UUID(pedido["id"])) == [(0,)]


# MATU-116 (C5): la fila de quien pagó y se informa es la de quien paga, sin cancelar
CAMPOS_PAGASTE = {
    "vista", "pedido_id", "referencia", "pagado_en", "estado", "entregado_en", "cancelado_en", "productos",
    "resumen_productos", "productos_borrados", "total", "devuelto", "devuelto_todo", "puede_arrepentirse",
    "arrepentirse_motivo", "plazo_hasta", "plazo_correo_hasta",
}


@pytest.mark.rf("R3")
@pytest.mark.rf("RNF-07")
def test_c5_quien_pago_y_paso_a_se_informa_ve_ese_pedido_y_se_arrepiente_y_los_demas_no(despacho: Despacho) -> None:
    """MATU-116 (J1, C5; reemplaza la prueba de C6 de MATU-92 que esperaba 404): quien pagó y pasó a «Se informa» ve
    en la lista la fila de quien paga en el pedido que pagó, su detalle sin cancelar ni la entrega, y puede
    arrepentirse. El pedido que pagó otra cuenta sigue con la fila de «Se informa» y 404 en el detalle y el retracto."""
    d = despacho
    familia, pedido = _pagado_por_el_pagador(d)
    _entregar(d, pedido)
    d.e.avanzar(timedelta(minutes=1))
    ajeno = _otro_pagado(d, familia)
    pagador = _rol(d, familia, "pagador")
    d.sql("UPDATE membresia SET rol = 'observador' WHERE usuario_id = %s AND grupo_id = %s", pagador.id,
          familia.grupo.id)

    r = _lista(d, familia, pagador)
    assert r.status_code == 200, r.text
    filas = {x["pedido_id"]: x for x in r.json()["items"]}
    assert [x["pedido_id"] for x in r.json()["items"]] == [ajeno["id"], pedido["id"]]
    suya, otra = filas[pedido["id"]], filas[ajeno["id"]]
    assert set(suya) == CAMPOS_PAGASTE and suya["vista"] == "pagaste"
    assert (suya["total"], suya["puede_arrepentirse"], suya["arrepentirse_motivo"]) == (TOTAL, True, None)
    assert set(otra) == CAMPOS_OBSERVADOR and otra["vista"] == "se_informa"
    [(referencia_ajena,)] = d.sql("SELECT referencia FROM pedido WHERE id = %s", uuid.UUID(ajeno["id"]))
    assert referencia_ajena not in r.text

    detalle = d.e.pedir("GET", f"/v1/pedidos/{pedido['id']}/seguimiento", pagador, familia)
    assert detalle.status_code == 200, detalle.text
    cuerpo_detalle = detalle.json()
    assert "puede_cancelar" not in cuerpo_detalle and "cancelar_motivo" not in cuerpo_detalle
    assert (cuerpo_detalle["total"], cuerpo_detalle["puede_arrepentirse"]) == (TOTAL, True)
    # Sin la entrega (dirección y teléfono) ni las notas del equipo
    assert not claves_a_cualquier_profundidad(cuerpo_detalle) & {"entrega", "calle", "telefono_contacto",
                                                                  "lo_que_paso", "nota"}
    _sin_nada_del_comercio(d, pedido, detalle.text)
    para_devolver = d.e.pedir("GET", f"/v1/pedidos/{pedido['id']}/retractos", pagador, familia)
    assert para_devolver.status_code == 200, para_devolver.text
    # El comprobante de quien paga (GET …/pago), con su tarjeta; del pedido ajeno, solo pagado o no
    pago = d.e.pedir("GET", f"/v1/pedidos/{pedido['id']}/pago", pagador, familia)
    assert pago.status_code == 200, pago.text
    assert pago.json()["comprobante"]["pagaste_tu"] is True and pago.json()["comprobante"]["total"] == TOTAL
    pago_ajeno = d.e.pedir("GET", f"/v1/pedidos/{ajeno['id']}/pago", pagador, familia)
    assert pago_ajeno.status_code == 200 and set(pago_ajeno.json()) == {"pedido_id", "estado"}, pago_ajeno.text

    # El pedido que no pagó: 404 en el detalle, lo que se puede devolver y el retracto
    for ruta in (f"/v1/pedidos/{ajeno['id']}/seguimiento", f"/v1/pedidos/{ajeno['id']}/retractos"):
        assert d.e.pedir("GET", ruta, pagador, familia).status_code == 404, ruta
    _entregar(d, ajeno)
    cuerpo_ajeno = {"lineas": [{"linea_id": _linea(d, ajeno), "cantidad": 1}]}
    r = d.post_familia(f"/v1/pedidos/{ajeno['id']}/retractos", pagador, familia, cuerpo_ajeno)
    assert r.status_code == 404, r.text
    assert d.sql("SELECT count(*) FROM retracto WHERE pedido_id = %s", uuid.UUID(ajeno["id"])) == [(0,)]

    # «Arrepentirme de la compra» del pedido que pagó
    cuerpo = {"lineas": [{"linea_id": _linea(d, pedido), "cantidad": 1}]}
    r = d.post_familia(f"/v1/pedidos/{pedido['id']}/retractos", pagador, familia, cuerpo)
    assert r.status_code == 201, r.text
    assert r.json()["es_tuyo"] is True
    assert d.sql("SELECT solicitado_por FROM retracto WHERE pedido_id = %s", uuid.UUID(pedido["id"])) == [
        (pagador.id,)]

    # Un observador que no pagó nada: solo filas de «Se informa», y 404 en el detalle
    observador = _rol(d, familia, "observador")
    r = _lista(d, familia, observador)
    assert {x["vista"] for x in r.json()["items"]} == {"se_informa"}
    assert d.e.pedir("GET", f"/v1/pedidos/{pedido['id']}/seguimiento", observador, familia).status_code == 404
    r = d.post_familia(f"/v1/pedidos/{pedido['id']}/retractos", observador, familia, cuerpo)
    assert r.status_code == 404, r.text


@pytest.mark.rf("R3")
def test_el_retracto_ampliado_idempotente_y_c13_el_pago_con_retracto_devuelto(despacho: Despacho) -> None:
    d = despacho
    familia, pedido = d.pagado()
    _entregar(d, pedido)
    linea = _linea(d, pedido)
    ruta = f"/v1/pedidos/{pedido['id']}/retractos"

    # Antes: todo disponible; sin la clave, 428
    ver = d.e.pedir("GET", ruta, familia.admin, familia)
    assert ver.status_code == 200, ver.text
    [disponible] = ver.json()["lineas"]
    assert (disponible["entregadas"], disponible["ya_pedidas"], disponible["disponibles"]) == (2, 0, 2)
    assert disponible["precio_pagado"] == PRECIO_PANAL
    assert ver.json()["puede_arrepentirse"] is True and ver.json()["arrepentirse_motivo"] is None
    assert ver.json()["plazo_correo_hasta"] > ver.json()["plazo_hasta"]
    # Con la 0.3, devolver todo lo entregado devuelve el envío (D-63-10, b)
    assert (ver.json()["incluye_envio_si_todo"], ver.json()["costo_envio"]) == (True, COSTO_ENVIO)
    cuerpo = {"lineas": [{"linea_id": linea, "cantidad": 1}]}
    sin_clave = d.e.pedir("POST", ruta, familia.admin, familia, cuerpo)
    assert sin_clave.status_code == 428 and sin_clave.json()["type"] == "/errores/falta-idempotencia"

    # C8: la misma clave devuelve el mismo retracto y no pide dos
    clave = d.e.clave()
    r = d.e.pedir("POST", ruta, familia.admin, familia, cuerpo, **{"Idempotency-Key": clave})
    assert r.status_code == 201, r.text
    retracto = r.json()
    assert (retracto["es_tuyo"], retracto["origen"], retracto["resuelto_en"]) == (True, "app", None)
    assert [(x["linea_id"], x["cantidad"], x["monto"]) for x in retracto["lineas"]] == [(linea, 1, PRECIO_PANAL)]
    otra_vez = d.e.pedir("POST", ruta, familia.admin, familia, cuerpo, **{"Idempotency-Key": clave})
    assert otra_vez.status_code == 201 and otra_vez.json()["id"] == retracto["id"]
    distinto = d.e.pedir(
        "POST", ruta, familia.admin, familia, {"lineas": [{"linea_id": linea, "cantidad": 2}]},
        **{"Idempotency-Key": clave},
    )
    assert distinto.status_code == 422 and distinto.json()["type"] == "/errores/idempotencia-reutilizada"
    assert d.sql("SELECT count(*) FROM retracto WHERE pedido_id = %s", uuid.UUID(pedido["id"])) == [(1,)]

    # Lo ve el cuidador, sin que sea suyo (C18); y él no puede pedirlo (C7)
    cuidador = _rol(d, familia, "cuidador")
    ver = d.e.pedir("GET", ruta, cuidador, familia).json()
    assert [x["es_tuyo"] for x in ver["retractos"]] == [False]
    assert ver["lineas"][0]["disponibles"] == 1 and ver["lineas"][0]["ya_pedidas"] == 1
    assert (ver["puede_arrepentirse"], ver["arrepentirse_motivo"]) == (False, "rol")
    seguimiento = d.e.pedir("GET", f"/v1/pedidos/{pedido['id']}/seguimiento", familia.admin, familia).json()
    assert (seguimiento["estado"], seguimiento["cancelar_motivo"]) == ("entregado", "ya_se_prepara")
    assert seguimiento["puede_arrepentirse"] is True and seguimiento["entregado_en"] is not None

    # C13: operación lo devuelve y GET …/pago sigue respondiendo, con la devolución por retracto
    resuelto = d.operacion("POST", f"/retractos/{retracto['id']}/resolver", {"decision": "devolver"})
    assert resuelto.status_code == 200, resuelto.text
    pago = d.e.pedir("GET", f"/v1/pedidos/{pedido['id']}/pago", familia.admin, familia)
    assert pago.status_code == 200, pago.text
    assert [(x["motivo"], x["monto"]) for x in pago.json()["devoluciones"]] == [("retracto", PRECIO_PANAL)]
    ver = d.e.pedir("GET", ruta, familia.admin, familia).json()
    assert ver["retractos"][0]["estado"] == "devuelto" and ver["retractos"][0]["resuelto_en"] is not None
    [fila] = _lista(d, familia, familia.admin).json()["items"]
    assert (fila["estado"], fila["devuelto"]) == ("entregado", PRECIO_PANAL)

    logs = d.e.iam.salida_logs.getvalue()
    # La clave es larga y única: se busca como subcadena. El precio, como dato: buscado como subcadena aparecía al
    # azar dentro de un UUID de los logs (hallazgo de Martín, CI de #101)
    assert clave not in logs
    assert not aparece_como_dato(str(PRECIO_PANAL), logs)


@pytest.mark.rf("R15")
def test_c11_cancelar_dos_veces_es_estado_pedido_y_la_repeticion_es_200(despacho: Despacho) -> None:
    d = despacho
    familia, pedido = d.pagado()
    ruta = f"/v1/pedidos/{pedido['id']}/cancelar-con-devolucion"
    sin_clave = d.e.pedir("POST", ruta, familia.admin, familia)
    assert sin_clave.status_code == 428
    clave = d.e.clave()
    r = d.e.pedir("POST", ruta, familia.admin, familia, **{"Idempotency-Key": clave})
    assert r.status_code == 200 and r.json()["estado"] == "cancelado_con_devolucion", r.text
    repetida = d.e.pedir("POST", ruta, familia.admin, familia, **{"Idempotency-Key": clave})
    assert repetida.status_code == 200 and repetida.json()["estado"] == "cancelado_con_devolucion"
    otra = d.post_familia(ruta, familia.admin, familia)
    assert otra.status_code == 409, otra.text
    assert (otra.json()["type"], otra.json()["estado"]) == ("/errores/estado-pedido", "cancelado_con_devolucion")
    assert d.cargo(pedido["id"]) == ("anulado", TOTAL, TOTAL)

    seguimiento = d.e.pedir("GET", f"/v1/pedidos/{pedido['id']}/seguimiento", familia.admin, familia).json()
    assert (seguimiento["estado"], seguimiento["cancelar_motivo"]) == ("cancelado_con_devolucion", "cancelado")
    assert (seguimiento["devuelto"], seguimiento["devuelto_todo"]) == (TOTAL, True)
    assert seguimiento["cancelado_en"] is not None
    assert [(p["estado"], p["cancelada_por"]) for p in seguimiento["partes"]] == [("cancelada", "pedido")]


@pytest.mark.rf("RF-25")
def test_lo_vencido_no_aparece(despacho: Despacho) -> None:
    """D-92-2 y C27: 2 años desde el cierre. El cancelado vence; el que sigue en curso, no."""
    d = despacho
    familia, cancelado = d.pagado()
    assert d.post_familia(f"/v1/pedidos/{cancelado['id']}/cancelar-con-devolucion", familia.admin,
                          familia).status_code == 200
    en_curso = _otro_pagado(d, familia)
    assert {x["pedido_id"] for x in _lista(d, familia, familia.admin).json()["items"]} == {
        cancelado["id"], en_curso["id"]}

    d.e.avanzar(timedelta(days=2 * 366))
    for usuario in (familia.admin, _rol(d, familia, "observador")):
        ids = [x["pedido_id"] for x in _lista(d, familia, usuario).json()["items"]]
        assert ids == [en_curso["id"]]
    vencido = d.e.pedir("GET", f"/v1/pedidos/{cancelado['id']}/seguimiento", familia.admin, familia)
    assert vencido.status_code == 404
    assert d.e.pedir("GET", f"/v1/pedidos/{en_curso['id']}/seguimiento", familia.admin, familia).status_code == 200


def test_c1_de_una_persona_eliminada_la_lista_y_el_seguimiento_responden_404(despacho: Despacho) -> None:
    """C1: con la persona eliminada (eliminado_en), su lista, el seguimiento y lo que se puede devolver responden el
    mismo 404 que otro grupo, para todos los roles. El pedido sigue guardado: solo no se muestra aquí."""
    d = despacho
    familia, pedido = d.pagado()
    _entregar(d, pedido)
    rutas = [
        f"/v1/personas-cuidadas/{familia.persona.id}/pedidos",
        f"/v1/pedidos/{pedido['id']}/seguimiento",
        f"/v1/pedidos/{pedido['id']}/retractos",
    ]
    for ruta in rutas:
        assert d.e.pedir("GET", ruta, familia.admin, familia).status_code == 200, ruta

    d.sql("UPDATE persona_cuidada SET eliminado_en = now() WHERE id = %s", familia.persona.id)
    for usuario in (familia.admin, _rol(d, familia, "cuidador"), _rol(d, familia, "pagador")):
        for ruta in rutas:
            r = d.e.pedir("GET", ruta, usuario, familia)
            assert r.status_code == 404, (ruta, r.text)
            assert pedido["id"] not in r.text
    r = _lista(d, familia, _rol(d, familia, "observador"))
    assert r.status_code == 404, r.text
    assert d.sql("SELECT count(*) FROM pedido WHERE id = %s", uuid.UUID(pedido["id"])) == [(1,)]


def test_c4_quien_salio_del_grupo_no_ve_sus_pedidos(despacho: Despacho) -> None:
    """C4: quien sale del grupo deja de ver la lista, el seguimiento y lo que se puede devolver, aunque haya pagado.
    Su token sigue siendo válido, así que sesion_de_grupo responde 404 (no es miembro activo), no 401. La membresía se
    retira con SQL, como en test_grupos.py: POST …/salida (membresia_retirar) exige el instante actual, y el reloj de
    este entorno es sintético. La salida por la API la prueba test_miembros_api.py."""
    d = despacho
    familia, pedido = _pagado_por_el_pagador(d)
    _entregar(d, pedido)
    pagador = _rol(d, familia, "pagador")
    rutas = [
        f"/v1/personas-cuidadas/{familia.persona.id}/pedidos",
        f"/v1/pedidos/{pedido['id']}/seguimiento",
        f"/v1/pedidos/{pedido['id']}/retractos",
    ]
    for ruta in rutas:
        assert d.e.pedir("GET", ruta, pagador, familia).status_code == 200, ruta

    d.sql("UPDATE membresia SET estado = 'retirada' WHERE usuario_id = %s AND grupo_id = %s", pagador.id,
          familia.grupo.id)
    for ruta in rutas:
        r = d.e.pedir("GET", ruta, pagador, familia)
        assert r.status_code == 404, (ruta, r.text)
        assert pedido["id"] not in r.text
    # Tampoco puede pedir un retracto, aunque haya pagado el pedido; nada queda escrito
    cuerpo = {"lineas": [{"linea_id": _linea(d, pedido), "cantidad": 1}]}
    r = d.post_familia(f"/v1/pedidos/{pedido['id']}/retractos", pagador, familia, cuerpo)
    assert r.status_code == 404, r.text
    assert d.sql("SELECT count(*) FROM retracto WHERE pedido_id = %s", uuid.UUID(pedido["id"])) == [(0,)]
    # El resto del grupo lo sigue viendo
    assert [x["pedido_id"] for x in _lista(d, familia, familia.admin).json()["items"]] == [pedido["id"]]


@pytest.mark.rf("R3")
def test_c8_dos_retractos_a_la_vez_no_piden_mas_de_lo_entregado(despacho: Despacho) -> None:
    """Quien pagó con el rol pagador (RLS no le deja FOR UPDATE sobre un pedido pagado): una transacción toma el
    bloqueo del pedido y pide las 2 unidades; la petición espera y, al confirmarse la otra, ve lo ya pedido: 422."""
    d = despacho
    familia, pedido = _pagado_por_el_pagador(d)
    _entregar(d, pedido)
    pagador = _rol(d, familia, "pagador")
    linea = _linea(d, pedido)
    pedido_id = uuid.UUID(pedido["id"])
    [(grupo, entregado)] = d.sql("SELECT grupo_id, entregado_en FROM pedido WHERE id = %s", pedido_id)

    respuestas: list[Any] = []
    with psycopg.connect(DSN) as cx:
        cx.execute("SELECT pg_advisory_xact_lock(hashtextextended('retracto:' || CAST(%s AS text), 0))",
                   (str(pedido_id),))
        retracto = uuid.uuid4()
        cx.execute(
            "INSERT INTO retracto (id, grupo_id, pedido_id, solicitado_por, solicitado_en, plazo_hasta, incluye_envio)"
            " VALUES (%s, %s, %s, %s, %s, %s, false)",
            (retracto, grupo, pedido_id, pagador.id, entregado + timedelta(minutes=1), entregado + timedelta(days=10)),
        )
        cx.execute(
            "INSERT INTO retracto_linea (retracto_id, grupo_id, pedido_linea_id, cantidad) VALUES (%s, %s, %s, 2)",
            (retracto, grupo, uuid.UUID(linea)),
        )
        pid = cx.info.backend_pid
        d.e.token(pagador)  # el login antes del hilo
        hilo = threading.Thread(target=lambda: respuestas.append(d.post_familia(
            f"/v1/pedidos/{pedido['id']}/retractos", pagador, familia,
            {"lineas": [{"linea_id": linea, "cantidad": 1}]})))
        hilo.start()
        esperar_bloqueada_por(pid, hilo)
        cx.commit()
    hilo.join(timeout=30)
    [r] = respuestas
    assert r.status_code == 422 and r.json()["type"] == "/errores/producto-no-retractable", r.text
    assert d.sql("SELECT sum(rl.cantidad) FROM retracto_linea rl JOIN retracto r ON r.id = rl.retracto_id"
                 " WHERE r.pedido_id = %s", pedido_id) == [(2,)]
    # Sin la carrera, quien pagó sí puede: el bloqueo no es solo de admin y cuidador
    d.sql("DELETE FROM retracto WHERE id = %s", retracto)
    r = d.post_familia(f"/v1/pedidos/{pedido['id']}/retractos", pagador, familia,
                       {"lineas": [{"linea_id": linea, "cantidad": 1}]})
    assert r.status_code == 201, r.text
    assert r.json()["es_tuyo"] is True


def test_matu113_el_observador_ve_el_cancelado_con_devolucion_sin_lo_devuelto(despacho: Despacho) -> None:
    """Decisión 472: el estado completo (cancelado con devolución), sin el monto devuelto ni ningún otro."""
    d = despacho
    familia, pedido = d.pagado()
    cancelado = d.post_familia(f"/v1/pedidos/{pedido['id']}/cancelar-con-devolucion", familia.admin, familia)
    assert cancelado.status_code == 200, cancelado.text
    ruta = f"/v1/pedidos/{pedido['id']}"
    assert d.e.pedir("GET", ruta, familia.admin, familia).json()["total"] == TOTAL

    visto = d.e.pedir("GET", ruta, _rol(d, familia, "observador"), familia)
    assert visto.status_code == 200, visto.text
    assert visto.json()["estado"] == "cancelado_con_devolucion"
    claves = claves_a_cualquier_profundidad(visto.json())
    assert not claves & MONTOS_PARA_EL_OBSERVADOR, claves & MONTOS_PARA_EL_OBSERVADOR
    a_la_vista = cifras_a_la_vista(visto.json(), (PRECIO_PANAL, 2 * PRECIO_PANAL, COSTO_ENVIO, TOTAL))
    assert not a_la_vista, a_la_vista


def test_matu113_el_observador_ve_en_su_fila_el_pedido_en_camino_y_entregado_sin_montos(despacho: Despacho) -> None:
    """Decisión 472 (reemplaza D-92-1 en lo del estado): la fila del observador trae el estado real de familia y
    entregado_en, y sigue sin ningún monto, referencia ni código."""
    d = despacho
    familia, pedido = d.pagado()
    [(referencia,)] = d.sql("SELECT referencia FROM pedido WHERE id = %s", uuid.UUID(pedido["id"]))
    observador = _rol(d, familia, "observador")

    def fila_del_observador() -> dict[str, Any]:
        r = _lista(d, familia, observador)
        assert r.status_code == 200, r.text
        claves = claves_a_cualquier_profundidad(r.json())
        assert not claves & MONTOS_PARA_EL_OBSERVADOR, claves & MONTOS_PARA_EL_OBSERVADOR
        a_la_vista = cifras_a_la_vista(r.json(), (TOTAL, PRECIO_PANAL))
        assert not a_la_vista, a_la_vista
        for nunca in (referencia, "codigo", "referencia", "puede_", "plazo"):
            assert nunca not in r.text, nunca
        [fila] = r.json()["items"]
        assert set(fila) == CAMPOS_OBSERVADOR
        return fila

    parte, etag = _parte(d, pedido)
    _preparar_todo(d, parte, etag)
    assert _validar(d, parte, _codigo(d, parte)).json()["resultado"] == "correcto"
    assert d.operacion("POST", f"/pedidos/{pedido['id']}/en-camino").status_code == 200
    fila = fila_del_observador()
    assert (fila["estado"], fila["entregado_en"]) == ("en_ruta", None)

    assert d.operacion("POST", f"/pedidos/{pedido['id']}/entregado").status_code == 200
    fila = fila_del_observador()
    assert fila["estado"] == "entregado" and fila["entregado_en"] is not None
    # Quien ve el pago ve lo mismo, con sus montos
    [completa] = _lista(d, familia, familia.admin).json()["items"]
    assert (completa["estado"], completa["entregado_en"], completa["total"]) == (
        "entregado", fila["entregado_en"], TOTAL)

"""MATU-62 · El pago contra PostgreSQL, con la PasarelaFalsa (RF-25, ADR-027; decisiones 224 a 247).

Camino feliz (pagar, Webpay, la vuelta, el comprobante), quién paga (admin y pagador; cuidador, observador y otro grupo
404), el 403 sin despacho, las cabeceras (428 y 412), el total vencido (409 vencido sin llamar a la pasarela), el pago
en curso (409 en pagar y en confirmar), las condiciones que cambiaron, Webpay caído (503 sin cobro), la idempotencia,
la vuelta con y sin sesión, y lo que nunca va a los logs. Corre como matu_app, con RLS (migración 0024).
"""

from datetime import timedelta
from typing import Any

import psycopg
import pytest

from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa
from tests.base_datos import DSN, requiere_base
from tests.modules.ordering.conftest import COSTO_ENVIO, EntornoPedido
from tests.modules.payments.conftest import cuerpo_pagar, pagar, pedido_confirmado, sin_sesion_volver

pytestmark = [pytest.mark.rf("RF-25"), requiere_base]

PRECIO_PANAL = 12990
TOTAL = 2 * PRECIO_PANAL + COSTO_ENVIO


def _consultar(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return [tuple(f) for f in cx.execute(sql, parametros)]


def _pagado(e: EntornoPedido, pasarela: PasarelaFalsa, *, debito: bool = False) -> tuple[Any, dict[str, Any], str]:
    familia, pedido = pedido_confirmado(e)
    inicio = pagar(e, familia, pedido)
    assert inicio.status_code == 201, inicio.text
    token = inicio.json()["token"]
    pasarela.pagar(token, debito=debito)
    vuelta = sin_sesion_volver(e, {"token_ws": token}, e.token(familia.admin))
    assert vuelta.status_code == 200 and vuelta.json()["resultado"] == "aprobado", vuelta.text
    return familia, pedido, token


# --- Camino feliz ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("debito", [False, True], ids=["credito", "debito"])
def test_pagar_volver_y_el_comprobante(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa, debito: bool
) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)

    inicio = pagar(e, familia, pedido)

    assert inicio.status_code == 201, inicio.text
    assert inicio.headers["Location"] == f"/v1/pedidos/{pedido['id']}/pago"
    assert inicio.headers["Cache-Control"] == "no-store"
    cuerpo = inicio.json()
    assert set(cuerpo) == {"intento_id", "estado", "monto", "total_confirmado_en", "url", "token"}
    assert (cuerpo["estado"], cuerpo["monto"]) == ("iniciada", TOTAL) and cuerpo["monto"] == pedido["total"]
    assert cuerpo["total_confirmado_en"] == pedido["total_confirmado_en"]
    # Mientras está en Webpay, el pedido lo dice
    leido = e.pedir("GET", f"/v1/pedidos/{pedido['id']}", familia.admin, familia).json()
    assert (leido["pago_en_curso"], leido["pagado_en"]) == (True, None)

    pasarela_falsa.pagar(cuerpo["token"], debito=debito, ultimos4="7763" if debito else "2032")
    vuelta = sin_sesion_volver(e, {"token_ws": cuerpo["token"]}, e.token(familia.admin))

    assert vuelta.status_code == 200, vuelta.text
    assert vuelta.json() == {
        "resultado": "aprobado",
        "ya_registrado": False,
        "anulacion": None,
        "volver_a_preguntar_en": None,
        "grupo_id": str(familia.grupo.id),
        "persona_cuidada_id": str(familia.persona.id),
        "pedido_id": pedido["id"],
        "pago_de_prueba": True,
    }
    pago = e.pedir("GET", f"/v1/pedidos/{pedido['id']}/pago", familia.admin, familia)
    assert pago.status_code == 200 and pago.headers["Cache-Control"] == "no-store"
    vista = pago.json()
    assert (vista["estado"], vista["pago_en_curso"], vista["intento"]["resultado"]) == ("aprobado", False, "aprobado")
    comprobante = vista["comprobante"]
    assert (comprobante["total"], comprobante["subtotal_productos"], comprobante["costo_envio"]) == (
        TOTAL,
        2 * PRECIO_PANAL,
        COSTO_ENVIO,
    )
    assert comprobante["pagaste_tu"] is True
    assert comprobante["tarjeta"] == {
        "tipo": "debito" if debito else "credito",
        "ultimos4": "7763" if debito else "2032",
        "cuotas": 0,
    }
    # Decisión 249: en el piloto el comprobante no se envía por correo, y correo va en null
    assert comprobante["pago_de_prueba"] is True and comprobante["correo"] is None
    assert comprobante["condiciones"]["version"] == "0.3"
    assert comprobante["condiciones"]["enlace"] == "/v1/condiciones-pedido?version=0.3"
    assert 4 <= len(comprobante["referencia"]) <= 6 and comprobante["referencia"].isdigit()
    # El pedido quedó pagado, con sus condiciones fijas y quién las aceptó
    assert _consultar(
        "SELECT estado, condiciones_aceptadas_por FROM pedido WHERE id = %s", pedido["id"]
    ) == [("pagado", familia.admin.id)]
    assert _consultar(
        "SELECT estado, monto_cobrado FROM cargo WHERE pedido_id = %s", pedido["id"]
    ) == [("pagado", TOTAL)]
    assert _consultar(
        "SELECT payload_respuesta FROM transaccion_pasarela t JOIN cargo c ON c.id = t.cargo_id WHERE c.pedido_id = %s",
        pedido["id"],
    ) == [(None,)]
    assert pasarela_falsa.cobrado(cuerpo["token"]) == TOTAL


def test_el_comprobante_de_otra_persona_no_trae_la_tarjeta_y_el_observador_solo_sabe_si_esta_pagado(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    familia, pedido, _ = _pagado(e, pasarela_falsa)
    cuidador = e.usuario(familia, "cuidador")
    vista = e.pedir("GET", f"/v1/pedidos/{pedido['id']}/pago", cuidador, familia).json()
    comprobante = vista["comprobante"]
    assert comprobante["pagaste_tu"] is False
    assert (comprobante["tarjeta"], comprobante["codigo_autorizacion"]) == (None, None)
    assert comprobante["correo"] is None
    observador = e.usuario(familia, "observador")
    assert e.pedir("GET", f"/v1/pedidos/{pedido['id']}/pago", observador, familia).json() == {
        "pedido_id": pedido["id"],
        "estado": "pagado",
    }
    pagado = e.pedir("GET", f"/v1/personas-cuidadas/{familia.persona.id}/pedido-pagado", familia.admin, familia)
    assert pagado.status_code == 200 and pagado.json()["pedido_id"] == pedido["id"]


def test_el_pagador_paga_y_acepta_las_condiciones_a_su_nombre(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    pagador = e.usuario(familia, "pagador")
    inicio = pagar(e, familia, pedido, pagador)
    assert inicio.status_code == 201, inicio.text
    assert _consultar("SELECT condiciones_aceptadas_por FROM pedido WHERE id = %s", pedido["id"]) == [(pagador.id,)]


# --- Quién paga, 403 y cabeceras -----------------------------------------------------------------------------------


@pytest.mark.parametrize("rol", ["cuidador", "observador"])
def test_cuidador_y_observador_no_pagan_404(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa, rol: str
) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    respuesta = pagar(e, familia, pedido, e.usuario(familia, rol))
    assert respuesta.status_code == 404
    assert pasarela_falsa.llamadas == []


def test_otro_grupo_404_y_no_ve_el_pago(entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    otra = e.lista_para_pedir(e.fabrica.familia())
    assert pagar(e, otra, pedido).status_code == 404
    assert e.pedir("GET", f"/v1/pedidos/{pedido['id']}/pago", otra.admin, otra).status_code == 404
    assert pasarela_falsa.llamadas == []


def test_sin_despacho_403(entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    retiro = e.pedir(
        "POST", f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos/despacho/retiro", familia.admin, familia
    )
    assert retiro.status_code == 200
    respuesta = pagar(e, familia, pedido)
    assert (respuesta.status_code, respuesta.json()["type"]) == (403, "/errores/sin-autorizacion-pedidos")


def test_sin_cabeceras_428_y_con_otra_version_412_sin_cobrar(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    ruta = f"/v1/pedidos/{pedido['id']}/pagar"
    sin_clave = e.pedir("POST", ruta, familia.admin, familia, cuerpo_pagar(), **{"If-Match": pedido["etag"]})
    assert (sin_clave.status_code, sin_clave.json()["type"]) == (428, "/errores/falta-idempotencia")
    sin_version = e.pedir("POST", ruta, familia.admin, familia, cuerpo_pagar(), **{"Idempotency-Key": e.clave()})
    assert (sin_version.status_code, sin_version.json()["type"]) == (428, "/errores/falta-version")
    otra = pagar(e, familia, pedido, etag='"v1"')
    assert (otra.status_code, otra.json()["type"]) == (412, "/errores/version-desactualizada")
    assert otra.json()["actual"]["id"] == pedido["id"]
    sin_casilla = pagar(e, familia, pedido, cuerpo={**cuerpo_pagar(), "acepta_condiciones": False})
    assert sin_casilla.status_code == 422
    assert pasarela_falsa.llamadas == []


# --- Total vencido, pago en curso y condiciones --------------------------------------------------------------------


def test_total_vencido_409_vencido_sin_llamar_a_la_pasarela(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    e.avanzar(timedelta(minutes=15))
    respuesta = pagar(e, familia, pedido)
    assert respuesta.status_code == 409
    assert (respuesta.json()["type"], respuesta.json()["estado"]) == ("/errores/estado-pedido", "vencido")
    assert pasarela_falsa.llamadas == []
    assert _consultar("SELECT count(*) FROM cargo WHERE pedido_id = %s", pedido["id"]) == [(0,)]
    assert _consultar("SELECT estado FROM pedido WHERE id = %s", pedido["id"]) == [("total_confirmado",)]


def test_pago_en_curso_bloquea_pagar_y_confirmar_pero_no_cancelar(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    assert pagar(e, familia, pedido).status_code == 201
    otro = pagar(e, familia, pedido)
    assert (otro.status_code, otro.json()["type"]) == (409, "/errores/pago-en-curso")
    reconfirmar = e.confirmar(familia, pedido["id"])
    assert (reconfirmar.status_code, reconfirmar.json()["type"]) == (409, "/errores/pago-en-curso")
    cancelar = e.pedir(
        "POST", f"/v1/pedidos/{pedido['id']}/cancelar", familia.admin, familia, **{"Idempotency-Key": e.clave()}
    )
    assert cancelar.status_code == 200


def test_si_se_cancela_mientras_paga_el_pago_se_anula_completo(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    """D-62-4, regla 3, con la base: el pedido no cambia y el cobro se anula a la misma tarjeta."""
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    token = pagar(e, familia, pedido).json()["token"]
    pasarela_falsa.pagar(token)
    e.pedir("POST", f"/v1/pedidos/{pedido['id']}/cancelar", familia.admin, familia, **{"Idempotency-Key": e.clave()})

    vuelta = sin_sesion_volver(e, {"token_ws": token})

    assert (vuelta.json()["resultado"], vuelta.json()["anulacion"]) == ("anulado", "hecha")
    assert _consultar("SELECT estado, pagado_en FROM pedido WHERE id = %s", pedido["id"]) == [("cancelado", None)]
    assert pasarela_falsa.cobrado(token) == 0
    vista = e.pedir("GET", f"/v1/pedidos/{pedido['id']}/pago", familia.admin, familia).json()
    assert vista["comprobante"] is None and vista["pago_de_prueba"] is True  # decisión 248: el sello del anulado
    assert [(d["motivo"], d["monto"], d["estado"]) for d in vista["devoluciones"]] == [("pago_tardio", TOTAL, "hecha")]


def test_condiciones_que_cambiaron_409_con_la_vigente(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    viejas = {"acepta_condiciones": True, "condiciones": {"version": "0.1", "huella": "a" * 64}}
    respuesta = pagar(e, familia, pedido, cuerpo=viejas)
    assert (respuesta.status_code, respuesta.json()["type"]) == (409, "/errores/condiciones-cambiaron")
    assert respuesta.json()["version_vigente"] == "0.3"
    assert pasarela_falsa.llamadas == []


# --- Webpay caído e idempotencia -----------------------------------------------------------------------------------


def test_webpay_caido_503_sin_cobro_venta_en_error_y_la_clave_libre(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    clave = e.clave()
    pasarela_falsa.caida = True
    caida = pagar(e, familia, pedido, clave=clave)
    assert (caida.status_code, caida.json()["type"]) == (503, "/errores/pasarela-no-disponible")
    assert caida.headers["Retry-After"] and caida.headers["Cache-Control"] == "no-store"
    assert _consultar(
        "SELECT t.estado, t.token FROM transaccion_pasarela t JOIN cargo c ON c.id = t.cargo_id WHERE c.pedido_id = %s",
        pedido["id"],
    ) == [("error", None)]
    pasarela_falsa.caida = False
    # Un 503 no se guarda en la clave: la misma clave abre la venta
    assert pagar(e, familia, pedido, clave=clave).status_code == 201


def test_la_misma_clave_no_abre_dos_ventas(entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    clave = e.clave()
    primera = pagar(e, familia, pedido, clave=clave)
    segunda = pagar(e, familia, pedido, clave=clave)
    assert (primera.status_code, segunda.status_code) == (201, 201)
    assert segunda.json()["token"] == primera.json()["token"]
    assert segunda.json()["intento_id"] == primera.json()["intento_id"]
    assert pasarela_falsa.llamadas.count("create") == 1
    otra_cuenta = pagar(e, familia, pedido, e.usuario(familia, "pagador"), clave=clave)
    assert (otra_cuenta.status_code, otra_cuenta.json()["type"]) == (422, "/errores/idempotencia-reutilizada")


# --- La vuelta y los logs ------------------------------------------------------------------------------------------


def test_la_vuelta_sin_sesion_no_trae_ids_y_nada_del_pago_va_a_los_logs(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    inicio = pagar(e, familia, pedido).json()
    pasarela_falsa.pagar(inicio["token"])
    vuelta = sin_sesion_volver(e, {"token_ws": inicio["token"]})
    assert vuelta.status_code == 200
    assert (vuelta.json()["grupo_id"], vuelta.json()["pedido_id"]) == (None, None)
    otra = e.lista_para_pedir(e.fabrica.familia())
    con_otra_cuenta = sin_sesion_volver(e, {"token_ws": inicio["token"]}, e.token(otra.admin))
    assert con_otra_cuenta.json()["grupo_id"] is None and con_otra_cuenta.json()["ya_registrado"] is True
    texto = e.iam.texto_log()
    venta = _consultar("SELECT buy_order, session_id FROM transaccion_pasarela WHERE token = %s", inicio["token"])[0]
    for secreto in (inicio["token"], *venta, "2032", str(TOTAL)):
        assert secreto not in texto, "un dato del pago llegó a los logs"
    assert pedido["id"] not in [linea.get("ruta") for linea in e.iam.lineas_log()]


def test_la_vuelta_desconocida_es_404(entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa) -> None:
    respuesta = sin_sesion_volver(entorno_pedido, {"token_ws": "token-que-no-es-de-matu"})
    assert respuesta.status_code == 404 and pasarela_falsa.llamadas == []

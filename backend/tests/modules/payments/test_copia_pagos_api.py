"""MATU-54 · Los pedidos y los pagos en las dos copias de los datos (D-54-14 a D-54-16), contra PostgreSQL.

Un pedido pagado con la PasarelaFalsa. En «Datos de» va el pedido con quién pagó y sin el teléfono de contacto ni datos
de la venta o la tarjeta; en «Tus datos» de quien pagó, su pago con la tarjeta y las condiciones que aceptó, sin la
persona ni los productos. Solo datos sintéticos.
"""

from typing import Any

import psycopg
import pytest

from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa
from tests.base_datos import DSN, requiere_base
from tests.modules.ordering.conftest import COSTO_ENVIO, TELEFONO, EntornoPedido
from tests.modules.payments.conftest import pagar, pedido_confirmado, sin_sesion_volver

pytestmark = [requiere_base, pytest.mark.rf("RF-25"), pytest.mark.rf("Ley-21.719")]

PRECIO_PANAL = 12990
TOTAL = 2 * PRECIO_PANAL + COSTO_ENVIO
DE_LA_VENTA = {"token", "buy_order", "session_id", "telefono_contacto", "telefono_origen"}
# F3 (decisión 402): el código de autorización va solo en «Tus datos» de quien pagó, nunca en la copia de la persona
SOLO_DE_QUIEN_PAGO = {"codigo_autorizacion", "tarjeta", "ultimos4", "cuotas"}


def _claves(valor: Any) -> set[str]:
    if isinstance(valor, dict):
        return set(valor) | {c for v in valor.values() for c in _claves(v)}
    if isinstance(valor, list):
        return {c for v in valor for c in _claves(v)}
    return set()


def _codigo(referencia: str) -> str:
    """El código de autorización guardado del pago aprobado del pedido de esa referencia, leído como superusuario."""
    with psycopg.connect(DSN) as cx:
        fila = cx.execute(
            "SELECT t.codigo_autorizacion FROM transaccion_pasarela t JOIN cargo c ON c.id = t.cargo_id"
            " JOIN pedido p ON p.id = c.pedido_id WHERE p.referencia = %s AND t.tipo = 'venta'"
            " AND t.estado = 'aprobada'", (referencia,)).fetchone()
    assert fila is not None and fila[0]
    return str(fila[0])


def _pagado(e: EntornoPedido, pasarela: PasarelaFalsa) -> tuple[Any, dict[str, Any], str]:
    familia, pedido = pedido_confirmado(e)
    inicio = pagar(e, familia, pedido)
    assert inicio.status_code == 201, inicio.text
    token = inicio.json()["token"]
    pasarela.pagar(token, ultimos4="2032")
    vuelta = sin_sesion_volver(e, {"token_ws": token}, e.token(familia.admin))
    assert vuelta.status_code == 200 and vuelta.json()["resultado"] == "aprobado", vuelta.text
    return familia, pedido, token


def test_la_copia_de_la_persona_trae_el_pedido_pagado_sin_telefono_ni_tarjeta(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    familia, _, token = _pagado(e, pasarela_falsa)

    respuesta = e.pedir("GET", f"/v1/personas-cuidadas/{familia.persona.id}/datos", familia.admin, familia)

    assert respuesta.status_code == 200, respuesta.text
    [pedido] = respuesta.json()["pedidos"]
    assert (pedido["estado"], pedido["total"], pedido["costo_envio"]) == ("pagado", TOTAL, COSTO_ENVIO)
    assert pedido["referencia"].isdigit()
    assert [(linea["cantidad"], linea["precio_unitario"], linea["subtotal"]) for linea in pedido["lineas"]] == [
        (2, PRECIO_PANAL, 2 * PRECIO_PANAL)]
    pago = pedido["pago"]
    assert (pago["estado"], pago["cobrado"], pago["devuelto"], pago["pago_de_prueba"]) == ("aprobado", TOTAL, 0, True)
    assert pago["pagado_por"] == {"nombre": familia.admin.nombre, "activo": True}
    assert pedido["entrega"] is not None and "telefono_contacto" not in pedido["entrega"]
    assert TELEFONO not in respuesta.text and token not in respuesta.text and "2032" not in respuesta.text
    assert not _claves(respuesta.json()) & (DE_LA_VENTA | SOLO_DE_QUIEN_PAGO)
    assert _codigo(pedido["referencia"]) not in respuesta.text
    # El historial dice a qué pedido se refiere cada hecho (F1)
    hechos = respuesta.json()["historial"]["hechos"]
    assert {h["referencia"] for h in hechos if h["tipo"] == "pago_aprobado"} == {pedido["referencia"]}


def test_tus_datos_de_quien_pago_trae_su_pago_y_sus_condiciones(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    familia, _, token = _pagado(e, pasarela_falsa)

    respuesta = e.iam.cliente.get("/v1/yo/datos", headers={"Authorization": f"Bearer {e.token(familia.admin)}"})

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    [pago] = cuerpo["pagos"]
    assert pago["grupo"] == familia.grupo.nombre and pago["cobrado"] == TOTAL and pago["devuelto"] == 0
    assert pago["tarjeta"] == {"tipo": "credito", "ultimos4": "2032", "cuotas": 0}
    # F3 (decisión 402): el código de su propio pago, el mismo de su comprobante
    assert pago["codigo_autorizacion"] == _codigo(pago["referencia"]) and pago["codigo_autorizacion"]
    [condiciones] = cuerpo["condiciones_aceptadas"]
    assert condiciones["referencia"] == pago["referencia"] and condiciones["version"] == "0.3"
    # Nada de la persona cuidada ni de la venta. Los nombres de la fábrica pueden repetirse: se busca el de la persona
    # solo si no es también el de quien pide o el del grupo
    for nombre in (familia.persona.nombre, familia.persona.nombre_pila):
        if nombre not in familia.admin.nombre and nombre not in familia.grupo.nombre:
            assert nombre not in respuesta.text
    assert token not in respuesta.text and not _claves(cuerpo) & DE_LA_VENTA


def test_tus_datos_de_quien_no_pago_no_trae_pagos(entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa) -> None:
    e = entorno_pedido
    familia, _, _ = _pagado(e, pasarela_falsa)
    cuidador = familia.miembros["cuidador"].usuario

    respuesta = e.iam.cliente.get("/v1/yo/datos", headers={"Authorization": f"Bearer {e.token(cuidador)}"})

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["pagos"] == [] and respuesta.json()["condiciones_aceptadas"] == []

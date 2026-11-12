"""MATU-62 · Las devoluciones contra PostgreSQL (arquitectura 12.4, casos 3, 4 y 9; decisión 239), sonda O1 del QA.

devolver_linea y devolver_todo con RepositorioPagosSQL, en la transacción del sistema (app.rol = 'sistema' y el grupo
del pedido, AbrirGrupoSQL): pasan por las políticas cargo_sistema_editar, participacion_sistema_editar,
transaccion_sistema_crear y linea_pago_devolver, y por los triggers de la migración 0024. La pasarela es la falsa.
"""

import uuid
from typing import Any

import psycopg
import pytest

from app.core.db import obtener_fabrica_sesiones
from app.modules.payments.application import devoluciones
from app.modules.payments.application.cobro import EstadoAnulacion
from app.modules.payments.domain.cargo import DevolucionInvalida
from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa
from app.modules.payments.infrastructure.sistema import AbrirGrupoSQL
from tests.base_datos import DSN, requiere_base
from tests.modules.ordering.conftest import COSTO_ENVIO, EntornoPedido
from tests.modules.payments.conftest import pagar, pedido_confirmado, sin_sesion_volver

pytestmark = [pytest.mark.rf("RF-25"), requiere_base]

PRECIO_PANAL = 12990
LINEA = 2 * PRECIO_PANAL
TOTAL = LINEA + COSTO_ENVIO


def _consultar(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return [tuple(f) for f in cx.execute(sql, parametros)]


def _cargo(pedido_id: uuid.UUID) -> tuple[str, int, int]:
    [(estado, cobrado, devuelto)] = _consultar(
        "SELECT estado, monto_cobrado, monto_devuelto FROM cargo WHERE pedido_id = %s", pedido_id
    )
    return estado, int(cobrado), int(devuelto)


@pytest.mark.parametrize("debito", [False, True], ids=["credito", "debito"])
def test_devolver_una_linea_y_despues_todo_a_la_misma_tarjeta(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa, debito: bool
) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    token = pagar(e, familia, pedido).json()["token"]
    pasarela_falsa.pagar(token, debito=debito)
    assert sin_sesion_volver(e, {"token_ws": token}).json()["resultado"] == "aprobado"
    pedido_id = uuid.UUID(pedido["id"])
    [(linea,)] = _consultar("SELECT id FROM pedido_linea WHERE pedido_id = %s", pedido_id)
    abrir = AbrirGrupoSQL(obtener_fabrica_sesiones(), e.iam.reloj)
    ahora = e.iam.reloj.ahora()

    # Caso 3: la anulación parcial de la línea que no se entrega
    with abrir(familia.grupo.id) as unidad:
        assert devoluciones.devolver_linea(unidad, pasarela_falsa, pedido_id, linea, ahora) is EstadoAnulacion.HECHA
    assert _cargo(pedido_id) == ("devuelto_parcial", TOTAL, LINEA)
    assert _consultar("SELECT estado_linea, monto_devuelto FROM pedido_linea WHERE id = %s", linea) == [
        ("devuelta", LINEA)
    ]
    assert pasarela_falsa.cobrado(token) == TOTAL - LINEA == COSTO_ENVIO
    assert pasarela_falsa.consultar(token).status == "PARTIALLY_NULLIFIED"

    # Caso 9: la misma línea no se devuelve dos veces
    with abrir(familia.grupo.id) as unidad, pytest.raises(DevolucionInvalida):
        devoluciones.devolver_linea(unidad, pasarela_falsa, pedido_id, linea, ahora)
    assert _cargo(pedido_id) == ("devuelto_parcial", TOTAL, LINEA)

    # Caso 4: se devuelve lo que queda, el envío incluido
    with abrir(familia.grupo.id) as unidad:
        assert devoluciones.devolver_todo(unidad, pasarela_falsa, pedido_id, ahora) is EstadoAnulacion.HECHA
    estado, cobrado, devuelto = _cargo(pedido_id)
    assert (estado, cobrado - devuelto) == ("anulado", 0) and devuelto == TOTAL
    assert pasarela_falsa.cobrado(token) == 0
    assert _consultar(
        "SELECT t.motivo_anulacion, t.monto, t.estado FROM transaccion_pasarela t JOIN cargo c ON c.id = t.cargo_id"
        " WHERE c.pedido_id = %s AND t.tipo = 'anulacion' ORDER BY t.monto DESC",
        pedido_id,
    ) == [("producto_no_entregado", LINEA, "aprobada"), ("cancelacion", COSTO_ENVIO, "aprobada")]

    # Caso 9: no queda nada que devolver
    with abrir(familia.grupo.id) as unidad, pytest.raises((DevolucionInvalida, devoluciones.SinPagoQueDevolver)):
        devoluciones.devolver_todo(unidad, pasarela_falsa, pedido_id, ahora)

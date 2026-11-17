"""MATU-92 · El estado de «Tus pedidos» para la familia y la conservación de lo pagado (D-92-2, C16 y C27). Sin base."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.ordering.domain.estados import SIN_PAGAR, Estado
from app.modules.ordering.domain.seguimiento import (
    MAPA_FAMILIA,
    CanceladaPor,
    EstadoFamilia,
    NoEsUnPedidoPagado,
    cancelada_por,
    cierre_del_pedido,
    conservar_hasta,
    estado_para_la_familia,
    vencido,
)

pytestmark = pytest.mark.rf("RF-25")

E, F = Estado, EstadoFamilia
AHORA = datetime(2026, 11, 16, 15, 0, tzinfo=UTC)

ESPERADO = {
    E.PAGADO: F.PAGADO,
    E.ENVIADO_A_COMERCIO: F.ENVIADO_A_COMERCIO,
    E.PREPARANDO: F.PREPARANDO,
    E.LISTO_RETIRO: F.LISTO_RETIRO,
    E.ASIGNADO: F.LISTO_RETIRO,
    E.SIN_REPARTIDOR: F.LISTO_RETIRO,
    E.RETIRADO: F.LISTO_RETIRO,
    E.EN_RUTA: F.EN_RUTA,
    E.ENTREGADO: F.ENTREGADO,
    E.CERRADO: F.ENTREGADO,
    E.NO_ENTREGADO: F.NO_ENTREGADO,
    E.REPROGRAMADO: F.REPROGRAMADO,
    E.CANCELADO_CON_DEVOLUCION: F.CANCELADO_CON_DEVOLUCION,
}


@pytest.mark.parametrize("estado", list(Estado))
def test_cada_estado_pagado_tiene_su_llave_y_lo_no_pagado_no_va(estado: Estado) -> None:
    if estado in SIN_PAGAR or estado is E.CANCELADO:
        with pytest.raises(NoEsUnPedidoPagado):
            estado_para_la_familia(estado)
    else:
        assert estado_para_la_familia(estado) is ESPERADO[estado]


def test_las_llaves_son_estados_reales_y_cubren_lenguaje_38() -> None:
    assert set(MAPA_FAMILIA) == set(ESPERADO)
    assert {f.value for f in EstadoFamilia} <= {e.value for e in Estado}


@pytest.mark.parametrize(
    ("estado", "motivo", "esperado"),
    [
        ("enviada", None, None),
        ("preparando", None, None),
        ("lista", None, None),
        ("retirada", None, None),
        ("cancelada", "producto_faltante", CanceladaPor.FALTANTE),
        ("cancelada", "familia_cancela", CanceladaPor.PEDIDO),
        ("cancelada", None, CanceladaPor.PEDIDO),
    ],
)
def test_cancelada_por(estado: str, motivo: str | None, esperado: CanceladaPor | None) -> None:
    assert cancelada_por(estado, motivo) is esperado


def test_un_estado_de_parte_desconocido_no_pasa() -> None:
    with pytest.raises(ValueError):
        cancelada_por("rechazada", None)


def test_el_cierre_es_la_entrega_o_la_cancelacion() -> None:
    entrega, cancelacion, pago = AHORA, AHORA - timedelta(days=1), AHORA - timedelta(days=2)
    assert cierre_del_pedido(E.ENTREGADO, entrega, None, pago) == entrega
    assert cierre_del_pedido(E.CERRADO, entrega, None, pago) == entrega
    assert cierre_del_pedido(E.CANCELADO_CON_DEVOLUCION, None, cancelacion, pago) == cancelacion
    # Sin el instante de la cancelación, el pago: más temprano
    assert cierre_del_pedido(E.CANCELADO_CON_DEVOLUCION, None, None, pago) == pago
    for en_curso in (E.PAGADO, E.PREPARANDO, E.EN_RUTA, E.NO_ENTREGADO, E.REPROGRAMADO):
        assert cierre_del_pedido(en_curso, None, None, pago) is None


def test_se_conserva_dos_anios_desde_el_cierre_y_ni_un_instante_mas() -> None:
    cierre = datetime(2026, 11, 16, 15, 0, tzinfo=UTC)
    limite = datetime(2028, 11, 16, 15, 0, tzinfo=UTC)
    assert conservar_hasta(cierre) == limite
    assert not vencido(cierre, limite - timedelta(microseconds=1))
    assert vencido(cierre, limite)
    assert vencido(cierre, limite + timedelta(days=1))


def test_un_pedido_en_curso_no_vence_nunca() -> None:
    assert not vencido(None, AHORA + timedelta(days=3650))


def test_el_29_de_febrero_vence_el_28() -> None:
    assert conservar_hasta(datetime(2028, 2, 29, 12, tzinfo=UTC)) == datetime(2030, 2, 28, 12, tzinfo=UTC)

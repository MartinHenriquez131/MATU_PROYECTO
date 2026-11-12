"""MATU-62 · Las transiciones del cargo y sus devoluciones (decisión 243; arquitectura 12.4, caso 9). Sin base.

Las 25 combinaciones de los 5 estados: cada par es válido exactamente si está en la tabla de la decisión 243, escrita
aquí aparte del dominio. La migración 0024 repite la tabla en el trigger cargo_pago_atado.
"""

from itertools import product

import pytest

from app.modules.payments.domain.cargo import (
    PARTICIPACION_DE,
    TRANSICIONES_CARGO,
    DevolucionInvalida,
    EstadoCargo,
    EstadoParticipacion,
    TransicionCargoInvalida,
    estado_tras_devolver,
    exigir,
    permitida,
)

pytestmark = pytest.mark.rf("RF-25")

C = EstadoCargo
# La tabla de la decisión 243, escrita aparte del dominio
ESPERADAS = {
    (C.PENDIENTE, C.PAGADO),
    (C.PENDIENTE, C.RECHAZADO),
    (C.RECHAZADO, C.PENDIENTE),
    (C.PAGADO, C.DEVUELTO_PARCIAL),
    (C.PAGADO, C.ANULADO),
    (C.DEVUELTO_PARCIAL, C.DEVUELTO_PARCIAL),
    (C.DEVUELTO_PARCIAL, C.ANULADO),
}
PARES = list(product(EstadoCargo, EstadoCargo))


def test_son_25_combinaciones_y_7_validas() -> None:
    assert len(PARES) == 25
    assert TRANSICIONES_CARGO == ESPERADAS
    assert sum(1 for d, h in PARES if (d, h) not in ESPERADAS) == 18


@pytest.mark.parametrize(("desde", "hacia"), PARES, ids=[f"{d.value}->{h.value}" for d, h in PARES])
def test_las_25_combinaciones_del_cargo(desde: EstadoCargo, hacia: EstadoCargo) -> None:
    if (desde, hacia) in ESPERADAS:
        assert permitida(desde, hacia)
        exigir(desde, hacia)
    else:
        assert not permitida(desde, hacia)
        with pytest.raises(TransicionCargoInvalida) as error:
            exigir(desde, hacia)
        assert (error.value.desde, error.value.hacia) == (desde, hacia)


def test_anulado_es_terminal_y_lo_cobrado_no_vuelve_a_pendiente() -> None:
    assert not any(permitida(C.ANULADO, h) for h in EstadoCargo)
    for cobrado in (C.PAGADO, C.DEVUELTO_PARCIAL, C.ANULADO):
        assert not permitida(cobrado, C.PENDIENTE)
        assert not permitida(cobrado, C.RECHAZADO)


def test_la_participacion_sigue_los_mismos_estados_en_femenino() -> None:
    assert {e.value for e in PARTICIPACION_DE.values()} == {e.value for e in EstadoParticipacion}
    assert PARTICIPACION_DE[C.DEVUELTO_PARCIAL] is EstadoParticipacion.DEVUELTA_PARCIAL


# --- Devoluciones a la misma tarjeta (caso 9) -----------------------------------------------------------------------


def test_una_devolucion_parcial_y_despues_la_que_completa_el_total() -> None:
    # $57.460 cobrados; se devuelven 2 × $8.745 y después el resto
    assert estado_tras_devolver(C.PAGADO, 57460, 0, 17490) is C.DEVUELTO_PARCIAL
    assert estado_tras_devolver(C.DEVUELTO_PARCIAL, 57460, 17490, 8990) is C.DEVUELTO_PARCIAL
    assert estado_tras_devolver(C.DEVUELTO_PARCIAL, 57460, 26480, 30980) is C.ANULADO
    assert estado_tras_devolver(C.PAGADO, 57460, 0, 57460) is C.ANULADO


@pytest.mark.parametrize(("devuelto", "monto"), [(0, 57461), (57460, 1), (40000, 17461), (0, 0), (0, -1)])
def test_lo_devuelto_nunca_supera_lo_cobrado(devuelto: int, monto: int) -> None:
    with pytest.raises(DevolucionInvalida):
        estado_tras_devolver(C.PAGADO if devuelto == 0 else C.DEVUELTO_PARCIAL, 57460, devuelto, monto)


@pytest.mark.parametrize("estado", [C.PENDIENTE, C.RECHAZADO, C.ANULADO])
def test_no_se_devuelve_lo_que_no_se_cobro(estado: EstadoCargo) -> None:
    with pytest.raises(TransicionCargoInvalida):
        estado_tras_devolver(estado, 57460, 0, 100)

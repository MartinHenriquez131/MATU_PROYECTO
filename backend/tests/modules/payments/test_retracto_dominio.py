"""MATU-63 · El retracto (R3; D-63-9 y D-63-10): el plazo de 10 días hábiles, qué se puede devolver y cuándo vuelve el
envío."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.payments.domain.retracto import (
    LineaRetractable,
    RetractoInvalido,
    anulacion_a_tiempo,
    en_plazo,
    incluye_envio,
    monto_productos,
    plazo_por_correo,
    plazo_retracto,
    validar,
)

pytestmark = pytest.mark.rf("R3")


def test_diez_dias_habiles_desde_la_entrega_en_chile() -> None:
    # Viernes 13-11-2026 a las 12:00 de Chile (15:00 UTC): cuentan del lunes 16 al viernes 27, hasta las 23:59:59
    entregado = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
    plazo = plazo_retracto(entregado)
    assert plazo.astimezone(UTC) == datetime(2026, 11, 28, 2, 59, 59, 999999, tzinfo=UTC)
    assert en_plazo(entregado, plazo) and not en_plazo(entregado, plazo + timedelta(microseconds=1))


def test_una_entrega_de_noche_cuenta_por_la_fecha_de_chile() -> None:
    # Sábado 14-11 a las 01:00 UTC es viernes 13 a las 22:00 en Chile: el mismo plazo que el mediodía del viernes
    assert plazo_retracto(datetime(2026, 11, 14, 1, 0, tzinfo=UTC)) == plazo_retracto(
        datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
    )


LINEAS = {
    "a": LineaRetractable("a", entregadas=2, precio_unitario=12990),
    "b": LineaRetractable("b", entregadas=1, precio_unitario=4490),
    "c": LineaRetractable("c", entregadas=0, precio_unitario=9990),
}


def test_se_devuelve_lo_entregado_a_precio_pagado() -> None:
    validar(LINEAS, {"a": 1})
    assert monto_productos(LINEAS, {"a": 2, "b": 1}) == 2 * 12990 + 4490


@pytest.mark.parametrize("pedidas", [{}, {"a": 3}, {"c": 1}, {"x": 1}, {"a": 0}])
def test_no_se_pide_lo_que_no_llego(pedidas: dict[str, int]) -> None:
    with pytest.raises(RetractoInvalido):
        validar(LINEAS, pedidas)


def test_una_linea_admite_otro_retracto_hasta_lo_entregado() -> None:
    """H3: varios retractos por línea mientras queden unidades entregadas sin pedir."""
    validar({"a": LineaRetractable("a", 2, 12990, ya_pedidas=1, vigentes=1)}, {"a": 1})
    with pytest.raises(RetractoInvalido):
        validar({"a": LineaRetractable("a", 2, 12990, ya_pedidas=1, vigentes=1)}, {"a": 2})
    with pytest.raises(RetractoInvalido):
        validar({"a": LineaRetractable("a", 2, 12990, ya_pedidas=2, vigentes=2)}, {"a": 1})


def test_lo_rechazado_no_se_vuelve_a_pedir_ni_cuenta_como_devuelto() -> None:
    """H8: el sello ya se abrió. Con 1 rechazado de 2, queda 1 por pedir; con la 0.3 el envío no vuelve, porque lo
    rechazado no se devolvió."""
    linea = LineaRetractable("a", 2, 12990, ya_pedidas=1, vigentes=0)
    validar({"a": linea}, {"a": 1})
    with pytest.raises(RetractoInvalido):
        validar({"a": linea}, {"a": 2})
    assert not incluye_envio("0.3", [linea], {"a": 1}, False)
    # Con uno por resolver (no rechazado), sí: queda devuelto todo lo entregado
    assert incluye_envio("0.3", [LineaRetractable("a", 2, 12990, ya_pedidas=1, vigentes=1)], {"a": 1}, False)


def test_por_correo_el_plazo_es_de_90_dias_desde_la_entrega() -> None:
    """H2 (CL-54, mientras tanto)."""
    entregado = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
    assert plazo_por_correo(entregado) == entregado + timedelta(days=90)


@pytest.mark.parametrize(
    "version, pedidas, ya_devuelto, esperado",
    [
        ("0.2", {"a": 1}, False, True),  # (a): las condiciones 0.2 prometían el envío en todo retracto
        ("0.1", {"a": 1}, False, True),
        ("0.2", {"a": 1}, True, False),  # una sola vez por pedido
        ("0.3", {"a": 1}, False, False),  # (b): solo si vuelve todo lo entregado
        ("0.3", {"a": 2, "b": 1}, False, True),
        (None, {"a": 2}, False, False),
    ],
)
def test_el_envio_segun_las_condiciones_aceptadas(
    version: str | None, pedidas: dict[str, int], ya_devuelto: bool, esperado: bool
) -> None:
    assert incluye_envio(version, list(LINEAS.values()), pedidas, ya_devuelto) is esperado


def test_la_devolucion_es_antes_de_45_dias() -> None:
    solicitado = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
    assert anulacion_a_tiempo(solicitado, solicitado + timedelta(days=45))
    assert not anulacion_a_tiempo(solicitado, solicitado + timedelta(days=45, seconds=1))

"""MATU-44 · RelojDetenido: el mismo instante en cada lectura (decisión 124). Sin base."""

from datetime import UTC, datetime

import pytest

from app.shared.reloj_detenido import RelojDetenido

pytestmark = pytest.mark.rf("RF-02")


def test_siempre_el_mismo_instante() -> None:
    instante = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    reloj = RelojDetenido(instante)
    assert reloj.ahora() == reloj.ahora() == instante


def test_exige_zona_horaria() -> None:
    with pytest.raises(ValueError):
        RelojDetenido(datetime(2026, 11, 7, 12, 0))

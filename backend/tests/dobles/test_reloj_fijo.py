"""El doble RelojFijo se comporta como dice: hora fija, avanza a voluntad y exige zona horaria."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.shared.puertos import Reloj
from tests.dobles.reloj_fijo import RelojFijo

INICIO = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def test_reloj_fijo_no_avanza_solo() -> None:
    # Dado un reloj fijo, usado a través del puerto
    reloj: Reloj = RelojFijo(INICIO)

    # Cuando se pide la hora dos veces
    primera, segunda = reloj.ahora(), reloj.ahora()

    # Entonces es siempre el instante inicial
    assert primera == segunda == INICIO


def test_reloj_fijo_avanza_lo_que_se_le_pide(reloj_fijo: RelojFijo) -> None:
    # Dado el reloj fijo de las fixtures globales
    inicio = reloj_fijo.ahora()

    # Cuando se avanza dos horas
    reloj_fijo.avanzar(timedelta(hours=2))

    # Entonces la hora es dos horas después
    assert reloj_fijo.ahora() == inicio + timedelta(hours=2)


def test_reloj_fijo_rechaza_datetime_sin_zona_horaria() -> None:
    # Dado un datetime sin zona horaria
    sin_zona = datetime(2026, 10, 20, 12, 0)

    # Cuando se crea un reloj con él, entonces se rechaza
    with pytest.raises(ValueError, match="zona horaria"):
        RelojFijo(sin_zona)


def test_reloj_fijo_entrega_utc_aunque_reciba_otra_zona() -> None:
    # Dado un instante con la zona de Chile continental en horario de verano (UTC-3)
    en_chile = datetime(2026, 10, 20, 9, 0, tzinfo=timezone(timedelta(hours=-3)))

    # Cuando se crea un reloj con él
    reloj = RelojFijo(en_chile)

    # Entonces entrega el mismo instante, en UTC
    assert reloj.ahora() == INICIO
    assert reloj.ahora().utcoffset() == timedelta(0)


def test_reloj_fijo_no_retrocede() -> None:
    # Dado un reloj fijo
    reloj = RelojFijo(INICIO)

    # Cuando se intenta avanzar un tiempo negativo, entonces se rechaza y la hora no cambia
    with pytest.raises(ValueError):
        reloj.avanzar(timedelta(minutes=-1))
    assert reloj.ahora() == INICIO

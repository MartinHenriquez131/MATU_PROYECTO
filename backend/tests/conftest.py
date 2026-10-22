"""Fixtures globales: los dobles de los puertos (estrategia de pruebas, sección 3)."""

from datetime import UTC, datetime

import pytest

from tests.dobles.custodia_en_memoria import CustodiaEnMemoria
from tests.dobles.reloj_fijo import RelojFijo


@pytest.fixture
def reloj_fijo() -> RelojFijo:
    """Un reloj detenido en un instante sintético. La prueba lo hace avanzar con avanzar()."""
    return RelojFijo(datetime(2026, 10, 20, 12, 0, tzinfo=UTC))


@pytest.fixture
def custodia() -> CustodiaEnMemoria:
    """Una custodia de claves nueva por prueba, con la versión 1 de la KEK vigente."""
    return CustodiaEnMemoria()

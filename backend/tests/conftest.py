"""Fixtures globales: los dobles de los puertos (estrategia de pruebas, sección 3).

pytest es el ambiente de pruebas: ENTORNO=pruebas se fija aquí, antes de que cualquier conftest o
prueba cargue la configuración. Así, sin POLITICA_VERSION (por ejemplo en el pipeline), la
configuración usa la versión de fábrica en vez de impedir que la API arranque (MATU-07). Las
pruebas que verifican la exigencia fuera de pruebas fijan su propio ENTORNO.
"""

import os
from datetime import UTC, datetime

import pytest

from tests.dobles.custodia_en_memoria import CustodiaEnMemoria
from tests.dobles.reloj_fijo import RelojFijo

os.environ["ENTORNO"] = "pruebas"


@pytest.fixture
def reloj_fijo() -> RelojFijo:
    """Un reloj detenido en un instante sintético. La prueba lo hace avanzar con avanzar()."""
    return RelojFijo(datetime(2026, 10, 20, 12, 0, tzinfo=UTC))


@pytest.fixture
def custodia() -> CustodiaEnMemoria:
    """Una custodia de claves nueva por prueba, con la versión 1 de la KEK vigente."""
    return CustodiaEnMemoria()

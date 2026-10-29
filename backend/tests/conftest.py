"""Fixtures globales: los dobles de los puertos (estrategia de pruebas, sección 3).

pytest es el ambiente de pruebas: ENTORNO=pruebas se fija aquí, antes de que cualquier conftest o
prueba cargue la configuración. Así, sin POLITICA_VERSION (por ejemplo en el pipeline), la
configuración usa la versión de fábrica en vez de impedir que la API arranque (MATU-07). Las
pruebas que verifican la exigencia fuera de pruebas fijan su propio ENTORNO.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from tests.dobles.custodia_en_memoria import CustodiaEnMemoria
from tests.dobles.reloj_fijo import RelojFijo

if TYPE_CHECKING:
    from tests.fabricas import Fabrica

os.environ["ENTORNO"] = "pruebas"


@pytest.fixture
def reloj_fijo() -> RelojFijo:
    """Un reloj detenido en un instante sintético. La prueba lo hace avanzar con avanzar()."""
    return RelojFijo(datetime(2026, 10, 20, 12, 0, tzinfo=UTC))


@pytest.fixture
def custodia() -> CustodiaEnMemoria:
    """Una custodia de claves nueva por prueba, con la versión 1 de la KEK vigente."""
    return CustodiaEnMemoria()


@pytest.fixture
def fabrica() -> Iterator["Fabrica"]:
    """Las fábricas de datos sintéticos (MATU-30). Borra lo que creó al terminar la prueba.

    Se importa aquí adentro para que las pruebas que no tocan la base no necesiten psycopg.
    Siembra como superusuario (MATU_TEST_DSN): quien la use debe marcar la prueba con requiere_base.
    """
    from tests.fabricas import Fabrica

    sembradora = Fabrica()
    yield sembradora
    sembradora.limpiar()


@pytest.fixture
def configuracion_sin_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """La configuración de la API sin el .env del equipo, ni el archivo ni lo que load_dotenv ya copió.

    tests/base_datos.py carga el .env de la raíz en os.environ para las pruebas con base. Las pruebas
    de configuración suponen que solo existen las variables que ellas fijan: esta fixture borra del
    entorno cada variable de Configuracion (salvo DATABASE_URL, que no valida nada) y apaga el
    archivo, y deja ENTORNO=pruebas. No cambia el comportamiento de la API, solo lo que ven estas pruebas.
    """
    from app.core import config

    monkeypatch.setitem(config.Configuracion.model_config, "env_file", None)
    for campo in config.Configuracion.model_fields:
        if campo != "database_url":
            monkeypatch.delenv(campo.upper(), raising=False)
    # El ambiente de las pruebas, como lo fija este conftest; la prueba que necesita otro lo cambia
    monkeypatch.setenv("ENTORNO", "pruebas")
    config.obtener_configuracion.cache_clear()
    yield
    config.obtener_configuracion.cache_clear()

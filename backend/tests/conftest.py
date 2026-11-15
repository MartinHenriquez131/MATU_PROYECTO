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


def pytest_configure(config: pytest.Config) -> None:
    """MATU-94: antes de recolectar, toda conexión de la suite apunta a una base de pruebas (tests/proteccion_base.py).
    Primero se carga el .env, como lo harán tests/base_datos.py y la configuración; si algo apunta a otra base, pytest
    termina sin correr nada y sin mostrar la cadena de conexión."""
    import tests.base_datos  # noqa: F401 - carga el .env en os.environ
    from tests.proteccion_base import exigir_bases_de_prueba

    rechazo = exigir_bases_de_prueba()
    if rechazo is not None:
        raise pytest.UsageError(rechazo)
    config.stash[_SALTADAS_SIN_BASE] = 0


# MATU-105: cuántas pruebas con requiere_base se saltaron por falta de base, para el resumen de la corrida
_SALTADAS_SIN_BASE = pytest.StashKey[int]()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Una prueba marcada con requiere_base sin la base: en CI falla con un mensaje claro y en local se salta y se
    cuenta. Corre antes de preparar las fixtures, que se conectarían a una base que no está."""
    if item.get_closest_marker("requiere_base") is None:
        return
    from tests.base_datos import MENSAJE_CI_SIN_BASE, MOTIVO_SIN_BASE, en_ci, variables_de_base_faltantes

    faltan = variables_de_base_faltantes()
    if not faltan:
        return
    if en_ci():
        pytest.fail(MENSAJE_CI_SIN_BASE.format(faltan=" y ".join(faltan)), pytrace=False)
    item.config.stash[_SALTADAS_SIN_BASE] = item.config.stash.get(_SALTADAS_SIN_BASE, 0) + 1
    pytest.skip(MOTIVO_SIN_BASE.format(faltan=" y ".join(faltan)))


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter, config: pytest.Config) -> None:
    saltadas = config.stash.get(_SALTADAS_SIN_BASE, 0)
    if saltadas:
        terminalreporter.write_sep(
            "!", f"{saltadas} pruebas con base saltadas: falta la base de pruebas (detalle con -rs)", yellow=True
        )


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

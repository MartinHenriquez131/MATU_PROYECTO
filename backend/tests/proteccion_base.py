"""Las pruebas solo corren contra una base de pruebas (MATU-94, decisión de Jorge del 11-11).

El 11-11, una corrida de pytest usó la base de uso ``matu``, y test_aislamiento.py había dejado ahí su semilla el
04-11. tests/conftest.py llama a ``exigir_bases_de_prueba`` al iniciar la sesión de pytest, antes de recolectar
ninguna prueba: toda conexión a PostgreSQL de la suite (``MATU_TEST_DSN`` y toda variable que termine en
``DATABASE_URL``: la de la API, ``MIGRATIONS_DATABASE_URL``, ``SCHEDULER_DATABASE_URL`` y
``PUBLISHER_DATABASE_URL``) tiene que apuntar a una base cuyo nombre termine en ``_test`` o empiece con ``matu_wt``.
Si no, pytest termina con MENSAJE, que nunca muestra la cadena de conexión: a lo más, el nombre de la variable y el
de la base.

La regla mira las bases de origen. Las bases desechables que crea una prueba desde ellas (la de test_migraciones.py)
no pasan por aquí.

**El pipeline** (``.github/workflows/ci.yml``) usa la base ``matu`` de un servicio de PostgreSQL que existe solo
durante la corrida, creada por ``infra/postgres/init/10_matu.sh`` con ese nombre fijo. Por eso, solo con
``GITHUB_ACTIONS=true``, también se acepta ``matu``. En un equipo, ``matu`` es la base de uso y siempre se rechaza.
"""

import os
from collections.abc import Mapping

from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import make_url

MENSAJE = "Las pruebas solo corren contra una base de pruebas (`*_test` o `matu_wt*`). Revisa tu `.env`."

# La base del servicio efímero del pipeline (ver el docstring)
BASE_DEL_PIPELINE = "matu"


def es_variable_de_conexion(nombre: str) -> bool:
    return nombre == "MATU_TEST_DSN" or nombre.endswith("DATABASE_URL")


def nombre_de_la_base(conexion: str) -> str | None:
    """El nombre de la base de una URL (``postgresql+psycopg://…/base``) o de un DSN de libpq (``dbname=base``).
    None si no se puede leer o no lo dice: libpq usaría el nombre del usuario, que no se da por base de pruebas."""
    try:
        if "://" in conexion:
            return make_url(conexion).database or None
        base = conninfo_to_dict(conexion).get("dbname")
        return str(base) if base else None
    except Exception:  # noqa: BLE001 - una cadena ilegible se rechaza, sin mostrarla
        return None


def es_base_de_pruebas(base: str | None, en_el_pipeline: bool = False) -> bool:
    if not base:
        return False
    if en_el_pipeline and base == BASE_DEL_PIPELINE:
        return True
    return base.endswith("_test") or base.startswith("matu_wt")


def problemas(entorno: Mapping[str, str]) -> list[str]:
    """Las variables de conexión definidas que no apuntan a una base de pruebas, con el nombre de su base si se
    pudo leer. Nunca el valor de la variable."""
    en_el_pipeline = entorno.get("GITHUB_ACTIONS") == "true"
    hallados = []
    for nombre in sorted(entorno):
        valor = entorno[nombre]
        if not es_variable_de_conexion(nombre) or not valor.strip():
            continue
        base = nombre_de_la_base(valor)
        if not es_base_de_pruebas(base, en_el_pipeline):
            hallados.append(f"{nombre} apunta a la base «{base}»" if base else f"{nombre} no dice a qué base apunta")
    return hallados


def mensaje_de_rechazo(hallados: list[str]) -> str:
    return MENSAJE + " " + "; ".join(hallados) + "."


def exigir_bases_de_prueba(entorno: Mapping[str, str] | None = None) -> str | None:
    """None si todo apunta a una base de pruebas; si no, el mensaje con que pytest termina."""
    hallados = problemas(os.environ if entorno is None else entorno)
    return mensaje_de_rechazo(hallados) if hallados else None

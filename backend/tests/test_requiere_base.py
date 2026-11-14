"""MATU-105 · requiere_base no salta en silencio (tests/base_datos.py y tests/conftest.py).

Antes era un skipif: sin DATABASE_URL o MATU_TEST_DSN, las pruebas con base se saltaban y el pipeline podía quedar en
verde sin haber probado el aislamiento. Ahora, sin la base, en CI la prueba falla con un mensaje que nombra lo que
falta, y en local se salta con un motivo visible con -rs y una línea de resumen que las cuenta.

Corre pytest en un proceso aparte sobre una prueba marcada, con las dos variables vacías: una variable definida y
vacía le gana al .env, en load_dotenv y en pydantic-settings, así que el proceso nunca ve la base del equipo. No se
conecta a nada. Falla sin la corrección: con el skipif, en CI se saltaba y no había línea de resumen.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.base_datos import en_ci

BACKEND = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.rf("MATU-105")

PRUEBA_CON_BASE = "tests/test_conexion_app.py::test_app_se_conecta_como_matu_app_sin_privilegios"


def _correr_sin_base(ci: str | None) -> subprocess.CompletedProcess[str]:
    entorno = {**os.environ, "DATABASE_URL": "", "MATU_TEST_DSN": "", "PYTHONIOENCODING": "utf-8"}
    entorno.pop("CI", None)
    if ci is not None:
        entorno["CI"] = ci
    return subprocess.run(
        [sys.executable, "-m", "pytest", PRUEBA_CON_BASE, "-q", "-rs", "-p", "no:cacheprovider"],
        cwd=BACKEND,
        env=entorno,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def test_en_ci_sin_base_la_prueba_falla_con_un_mensaje_claro() -> None:
    proceso = _correr_sin_base("true")

    salida = proceso.stdout + proceso.stderr
    assert proceso.returncode == 1, salida
    # Falla al preparar la prueba, antes de las fixtures: pytest la cuenta como error, y la corrida sale con 1
    assert "1 error" in salida, salida
    assert "En CI las pruebas con base no se saltan: falta DATABASE_URL y MATU_TEST_DSN" in salida, salida
    assert "skipped" not in salida, salida


def test_en_local_sin_base_se_salta_a_la_vista_y_se_cuenta() -> None:
    proceso = _correr_sin_base(None)

    salida = proceso.stdout + proceso.stderr
    assert proceso.returncode == 0, salida
    assert "1 skipped" in salida, salida
    # El motivo, con -rs, y la línea del resumen que las cuenta
    assert "sin base de pruebas: falta DATABASE_URL y MATU_TEST_DSN" in salida, salida
    assert "1 pruebas con base saltadas: falta la base de pruebas" in salida, salida


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(None, False), ("", False), ("0", False), ("false", False), ("no", False), ("true", True), ("1", True)],
)
def test_en_ci_lee_la_variable_ci(valor: str | None, esperado: bool) -> None:
    assert en_ci({} if valor is None else {"CI": valor}) is esperado

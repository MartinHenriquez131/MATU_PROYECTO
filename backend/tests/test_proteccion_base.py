"""MATU-94 · Las pruebas solo corren contra una base de pruebas (tests/proteccion_base.py), sin base.

Datos sintéticos: ninguna de estas cadenas abre una conexión. La contraseña y el host son marcas para verificar que
el mensaje no los muestra. Sin marca rf: protege la política 4 de CLAUDE.md (solo datos sintéticos, nunca la base de
demostración), no un requisito funcional.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.proteccion_base import (
    MENSAJE,
    es_base_de_pruebas,
    es_variable_de_conexion,
    exigir_bases_de_prueba,
    nombre_de_la_base,
)

BACKEND = Path(__file__).resolve().parents[1]
CLAVE = "clave-sintetica-no-mostrar"
SERVIDOR = "servidor-sintetico.invalid"


def _dsn(base: str) -> str:
    return f"host={SERVIDOR} port=5432 user=postgres password={CLAVE} dbname={base}"


def _url(base: str) -> str:
    return f"postgresql+psycopg://matu_app:{CLAVE}@{SERVIDOR}:5432/{base}"


@pytest.mark.parametrize("conexion", [_dsn("matu"), _url("matu")], ids=["dsn", "url"])
def test_la_base_de_uso_se_rechaza(conexion: str) -> None:
    rechazo = exigir_bases_de_prueba({"MATU_TEST_DSN": conexion, "DATABASE_URL": _url("matu_wt94")})

    assert rechazo is not None and rechazo.startswith(MENSAJE)
    assert "MATU_TEST_DSN apunta a la base «matu»" in rechazo
    assert "DATABASE_URL" not in rechazo  # la que sí apunta a una base de pruebas no se nombra


@pytest.mark.parametrize("base", ["matu_wt94", "matu_test", "matu_wt61", "otra_test"])
def test_las_bases_de_prueba_se_aceptan(base: str) -> None:
    entorno = {
        "MATU_TEST_DSN": _dsn(base),
        "DATABASE_URL": _url(base),
        "MIGRATIONS_DATABASE_URL": _url(base),
        "SCHEDULER_DATABASE_URL": _url(base),
        "PUBLISHER_DATABASE_URL": _url(base),
    }

    assert exigir_bases_de_prueba(entorno) is None


def test_el_mensaje_no_muestra_la_contrasena_ni_el_host() -> None:
    entorno = {
        "MATU_TEST_DSN": _dsn("matu"),
        "DATABASE_URL": _url("matu"),
        "MIGRATIONS_DATABASE_URL": _url("produccion"),
        "SCHEDULER_DATABASE_URL": f"host={SERVIDOR} password={CLAVE}",  # sin dbname: libpq usaría el usuario
        "PUBLISHER_DATABASE_URL": "postgresql+psycopg://[ilegible",
    }

    rechazo = exigir_bases_de_prueba(entorno)

    assert rechazo is not None
    for nombre in entorno:
        assert nombre in rechazo
    for secreto in (CLAVE, SERVIDOR, "matu_app", "postgres", "5432", "://"):
        assert secreto not in rechazo, secreto


@pytest.mark.parametrize(
    ("base", "en_el_pipeline", "acepta"),
    [
        ("matu", False, False),
        ("matu", True, True),  # el servicio efímero del pipeline (ci.yml)
        ("produccion", True, False),
        ("matu_staging", False, False),
        ("matu_wt", False, True),
        ("mi_test", False, True),
        ("matu_test_", False, False),
        ("", False, False),
        (None, False, False),
    ],
)
def test_la_regla_del_nombre(base: str | None, en_el_pipeline: bool, acepta: bool) -> None:
    assert es_base_de_pruebas(base, en_el_pipeline) is acepta


def test_en_el_pipeline_se_acepta_solo_su_base() -> None:
    entorno = {"GITHUB_ACTIONS": "true", "MATU_TEST_DSN": _dsn("matu"), "DATABASE_URL": _url("matu")}
    assert exigir_bases_de_prueba(entorno) is None
    assert exigir_bases_de_prueba({**entorno, "DATABASE_URL": _url("otra")}) is not None


def test_las_variables_vacias_y_ajenas_no_cuentan() -> None:
    assert exigir_bases_de_prueba({"DATABASE_URL": "", "MATU_TEST_DSN": "  ", "OTRA_URL": _url("matu")}) is None


def test_lee_el_nombre_de_url_y_de_dsn() -> None:
    assert nombre_de_la_base(_url("matu_wt94")) == "matu_wt94"
    assert nombre_de_la_base(_dsn("matu_test")) == "matu_test"
    assert nombre_de_la_base("postgresql://u@h/matu_wt1?sslmode=disable") == "matu_wt1"
    assert nombre_de_la_base("host=h user=u") is None


def test_pytest_termina_antes_de_correr_con_la_base_de_uso() -> None:
    """La sesión de pytest no arranca: no recolecta ni una prueba, y la salida no trae la cadena de conexión. Las
    variables de conexión del equipo se quitan del entorno del proceso hijo; las de la prueba no abren conexión."""
    entorno = {k: v for k, v in os.environ.items() if not es_variable_de_conexion(k) and k != "GITHUB_ACTIONS"}
    entorno.update({"MATU_TEST_DSN": _dsn("matu"), "DATABASE_URL": _url("matu_wt94"), "PYTHONIOENCODING": "utf-8"})

    proceso = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "--collect-only",
         "tests/test_proteccion_base.py"],
        cwd=BACKEND,
        env=entorno,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    salida = proceso.stdout + proceso.stderr

    assert proceso.returncode != 0
    assert MENSAJE in salida and "MATU_TEST_DSN apunta a la base «matu»" in salida
    assert "collected" not in salida and "test_la_regla_del_nombre" not in salida
    assert CLAVE not in salida and SERVIDOR not in salida

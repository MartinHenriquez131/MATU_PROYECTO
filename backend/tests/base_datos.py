"""Acceso a la base en las pruebas: la conexión de superusuario para sembrar y limpiar, la marca requiere_base
(sin DATABASE_URL o MATU_TEST_DSN, la prueba falla en CI y se salta a la vista en local, MATU-105) y las sesiones
de los roles de las tareas (MATU-74)."""

import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Superusuario: solo para sembrar y limpiar. Las verificaciones corren como matu_app.
# MATU-94: sin valor por omisión. Antes caía en dbname=matu, la base de uso; ahora, sin MATU_TEST_DSN, las pruebas con
# base no corren (ver requiere_base), y tests/conftest.py exige que las dos apunten a una base de pruebas
DSN = os.environ.get("MATU_TEST_DSN", "")

# MATU-105: requiere_base ya no es un skipif que salta en silencio. Es una marca, y tests/conftest.py decide al
# preparar cada prueba marcada: si falta la base, en CI la prueba falla con MENSAJE_CI_SIN_BASE, y en local se salta
# con MOTIVO_SIN_BASE (visible con -rs) y se cuenta en el resumen de la corrida
requiere_base = pytest.mark.requiere_base

MOTIVO_SIN_BASE = "sin base de pruebas: falta {faltan} (ver backend/README.md, «Pruebas con base»)"
MENSAJE_CI_SIN_BASE = (
    "En CI las pruebas con base no se saltan: falta {faltan}. Define DATABASE_URL y MATU_TEST_DSN en el job"
    " (ver backend/README.md, «Pruebas con base»)."
)


def variables_de_base_faltantes() -> list[str]:
    """Los nombres de las variables de conexión que faltan para las pruebas con base. Nunca sus valores."""
    faltan = []
    if not obtener_configuracion().database_url:
        faltan.append("DATABASE_URL")
    if not DSN:
        faltan.append("MATU_TEST_DSN")
    return faltan


def en_ci(entorno: Mapping[str, str] | None = None) -> bool:
    """La variable CI presente y no apagada (GitHub Actions la fija en true)."""
    valor = (os.environ if entorno is None else entorno).get("CI")
    return valor is not None and valor.strip().lower() not in ("", "0", "false", "no")


ROLES_DE_LAS_TAREAS = frozenset({"matu_scheduler", "matu_publisher"})


@lru_cache
def fabrica_de_rol(rol: str) -> sessionmaker[Session]:
    """Sesiones como matu_scheduler o matu_publisher, sin su contraseña (MATU-74, migración 0022).

    Conecta con MATU_TEST_DSN y hace SET ROLE al abrir cada conexión: current_user es el rol, y con él los
    permisos y las políticas, igual que con la conexión propia de la tarea. Así corren también donde
    SCHEDULER_DATABASE_URL y PUBLISHER_DATABASE_URL no están definidas, como el pipeline. La conexión propia
    de cada tarea la prueba tests/test_tareas.py."""
    if rol not in ROLES_DE_LAS_TAREAS:
        raise ValueError(f"rol no permitido: {rol!r}")
    engine = create_engine("postgresql+psycopg://", creator=lambda: psycopg.connect(DSN), pool_pre_ping=True)

    @event.listens_for(engine, "connect")
    def _fijar_rol(conexion, _registro):  # type: ignore[no-untyped-def]
        with conexion.cursor() as cursor:
            cursor.execute(f"SET ROLE {rol}")
        conexion.commit()

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def fabrica_scheduler() -> sessionmaker[Session]:
    return fabrica_de_rol("matu_scheduler")


def fabrica_publisher() -> sessionmaker[Session]:
    return fabrica_de_rol("matu_publisher")

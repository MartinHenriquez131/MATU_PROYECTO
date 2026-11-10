"""Acceso a la base en las pruebas: la conexión de superusuario para sembrar y limpiar, la marca
que salta una prueba cuando no hay DATABASE_URL (la conexión de la API, como matu_app) y las sesiones
de los roles de las tareas (MATU-74)."""

import os
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
DSN = os.environ.get("MATU_TEST_DSN", "host=localhost port=5432 user=postgres dbname=matu")

requiere_base = pytest.mark.skipif(not obtener_configuracion().database_url, reason="DATABASE_URL no está definida")

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

"""Acceso a la base en las pruebas: la conexión de superusuario para sembrar y limpiar, y la marca
que salta una prueba cuando no hay DATABASE_URL (la conexión de la API, como matu_app)."""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from app.core.config import obtener_configuracion

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Superusuario: solo para sembrar y limpiar. Las verificaciones corren como matu_app.
DSN = os.environ.get("MATU_TEST_DSN", "host=localhost port=5432 user=postgres dbname=matu")

requiere_base = pytest.mark.skipif(not obtener_configuracion().database_url, reason="DATABASE_URL no está definida")

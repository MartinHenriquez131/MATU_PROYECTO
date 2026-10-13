"""
MATU · La aplicación se conecta con un rol que RLS alcanza siempre.

Usa DATABASE_URL, la misma conexión que usa la API (backend/database.py), y verifica
que el rol es matu_app, que no es superusuario y que no evade RLS.
"""

import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
URL = os.environ.get("DATABASE_URL", "")


@pytest.mark.skipif(not URL, reason="DATABASE_URL no está definida")
def test_app_se_conecta_como_matu_app_sin_privilegios() -> None:
    conninfo = URL.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(conninfo) as cx:
        fila = cx.execute(
            "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        ).fetchone()
    assert fila is not None
    usuario, superusuario, evade_rls = fila
    assert usuario == "matu_app"
    assert superusuario is False
    assert evade_rls is False

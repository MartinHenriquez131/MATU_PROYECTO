"""
MATU · La aplicación se conecta con un rol que RLS alcanza siempre.

Usa el mismo engine que usa la API (app/core/db.py, con DATABASE_URL) y verifica que el
rol es matu_app, que no es superusuario y que no evade RLS.
"""

import pytest
from sqlalchemy import text

from app.core.config import obtener_configuracion
from app.core.db import obtener_engine


@pytest.mark.skipif(not obtener_configuracion().database_url, reason="DATABASE_URL no está definida")
def test_app_se_conecta_como_matu_app_sin_privilegios() -> None:
    with obtener_engine().connect() as cx:
        fila = cx.execute(
            text("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
    usuario, superusuario, evade_rls = fila
    assert usuario == "matu_app"
    assert superusuario is False
    assert evade_rls is False

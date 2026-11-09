"""
MATU · La aplicación se conecta con un rol que RLS alcanza siempre.

Usa el mismo engine que usa la API (app/core/db.py, con DATABASE_URL) y verifica que el
rol es matu_app, que no es superusuario y que no evade RLS.

MATU-47 y MATU-66 (migración 0020): con esa misma conexión, matu_app no borra indice_token, solo escribe su
revocado_en, y no lee usuario.password_hash. Las sentencias llevan WHERE false: PostgreSQL revisa los permisos
antes de buscar filas, así que fallan sin tocar ningún dato, en cualquier base.
"""

import pytest
from psycopg import errors
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import obtener_configuracion
from app.core.db import obtener_engine

requiere_base = pytest.mark.skipif(not obtener_configuracion().database_url, reason="DATABASE_URL no está definida")


@requiere_base
def test_app_se_conecta_como_matu_app_sin_privilegios() -> None:
    with obtener_engine().connect() as cx:
        fila = cx.execute(
            text("SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
    usuario, superusuario, evade_rls = fila
    assert usuario == "matu_app"
    assert superusuario is False
    assert evade_rls is False


@requiere_base
@pytest.mark.rf("RF-05")
@pytest.mark.parametrize(
    "sentencia",
    [
        "DELETE FROM indice_token WHERE false",
        "UPDATE indice_token SET expira_en = expira_en WHERE false",
        "UPDATE indice_token SET referencia_id = referencia_id WHERE false",
        "UPDATE indice_token SET token_hash = token_hash WHERE false",
        "SELECT password_hash FROM usuario WHERE false",
        "SELECT mfa_secreto_cifrado FROM usuario WHERE false",
    ],
    ids=["borrar-token", "alargar-token", "mover-token", "cambiar-huella", "password-hash", "mfa"],
)
def test_la_app_no_borra_tokens_ni_lee_la_contrasena(sentencia: str) -> None:
    with pytest.raises(DBAPIError) as error, obtener_engine().connect() as cx:
        cx.execute(text(sentencia))
    assert isinstance(error.value.orig, errors.InsufficientPrivilege)


@requiere_base
@pytest.mark.rf("RF-05")
def test_la_app_conserva_lo_que_usa_de_indice_token_y_usuario() -> None:
    """Lo que la API sí hace hoy: leer e insertar tokens, cortar uno, y leer la cuenta sin la contraseña."""
    with obtener_engine().connect() as cx:
        permisos = cx.execute(
            text(
                "SELECT has_table_privilege('indice_token', 'SELECT'), has_table_privilege('indice_token', 'INSERT'),"
                " has_column_privilege('indice_token', 'revocado_en', 'UPDATE'),"
                " has_column_privilege('usuario', 'email', 'SELECT'),"
                " has_column_privilege('usuario', 'telefono', 'SELECT'),"
                " has_column_privilege('usuario', 'password_hash', 'UPDATE'),"
                " has_function_privilege('iam_credencial(uuid)', 'EXECUTE')"
            )
        ).one()
        cx.rollback()
    assert all(permisos), permisos

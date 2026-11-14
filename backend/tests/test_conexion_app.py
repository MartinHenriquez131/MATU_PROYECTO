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

from app.core.db import obtener_engine
from tests.base_datos import requiere_base

# MATU-105: sin la base, falla en CI y se salta a la vista en local (tests/base_datos.py)


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
        "UPDATE usuario SET es_operacion = es_operacion WHERE false",
        "UPDATE usuario SET estado = estado WHERE false",
        "DELETE FROM usuario WHERE false",
        "DELETE FROM acceso_relevo WHERE false",
    ],
    ids=["borrar-token", "alargar-token", "mover-token", "cambiar-huella", "password-hash", "mfa",
         "hacerse-operacion", "cambiar-estado", "borrar-cuenta", "borrar-acceso"],
)
def test_la_app_no_borra_tokens_ni_cuentas_ni_lee_la_contrasena(sentencia: str) -> None:
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
                " has_column_privilege('usuario', 'telefono', 'UPDATE'),"
                " has_column_privilege('usuario', 'celular_verificado_en', 'UPDATE'),"
                " has_column_privilege('usuario', 'celular_canal', 'UPDATE'),"
                " has_function_privilege('iam_credencial(uuid)', 'EXECUTE')"
            )
        ).one()
        cx.rollback()
    assert all(permisos), permisos


# MATU-74 (migración 0022, H2): las funciones de las tareas son de matu_scheduler y matu_publisher. La API, con
# app.rol = 'operacion' o sin él, recibe InsufficientPrivilege antes de que la función haga nada
FUNCIONES_DE_LAS_TAREAS = {
    "plan_destruir_claves": "SELECT plan_destruir_claves(now() - interval '90 days', now())",
    "consumo_conservar": "SELECT consumo_conservar(now() - interval '90 days', now())",
    "iam_conservar": "SELECT * FROM iam_conservar(now() - interval '30 days', now() - interval '90 days', now())",
    "quiebre_conservar": "SELECT * FROM quiebre_conservar(now() - interval '90 days', now() - interval '30 days',"
    " now())",
    "outbox_tomar": "SELECT * FROM outbox_tomar(1, now() - interval '1 day')",
    "outbox_publicado": "SELECT outbox_publicado(0, now())",
    "outbox_reintentar": "SELECT outbox_reintentar(0, now() + interval '1 minute', now())",
    "outbox_posponer": "SELECT outbox_posponer(0, now() + interval '1 hour', now())",
}


@requiere_base
@pytest.mark.rf("RF-02")
@pytest.mark.parametrize("sentencia", FUNCIONES_DE_LAS_TAREAS.values(), ids=FUNCIONES_DE_LAS_TAREAS.keys())
def test_la_app_no_ejecuta_las_funciones_de_las_tareas(sentencia: str) -> None:
    with pytest.raises(DBAPIError) as error, obtener_engine().connect() as cx:
        cx.execute(text("SELECT set_config('app.rol', 'operacion', true)"))
        cx.execute(text(sentencia))
    assert isinstance(error.value.orig, errors.InsufficientPrivilege)


def test_la_api_nunca_usa_las_conexiones_de_las_tareas() -> None:
    """SCHEDULER_DATABASE_URL y PUBLISHER_DATABASE_URL solo las lee app/tareas.py: la API (app/core/db.py y los
    módulos) se conecta siempre con DATABASE_URL."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1] / "app"
    usan = sorted(
        str(p.relative_to(raiz)).replace("\\", "/")
        for p in raiz.rglob("*.py")
        if "scheduler_database_url" in p.read_text(encoding="utf-8")
        or "publisher_database_url" in p.read_text(encoding="utf-8")
    )
    assert usan == ["core/config.py", "tareas.py"]

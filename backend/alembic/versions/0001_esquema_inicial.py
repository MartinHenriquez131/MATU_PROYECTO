"""Esquema inicial: 49 tablas, políticas RLS y permisos por rol.

Aplica los scripts de backend/db en orden. Los roles (00_roles.sql) no son parte
de la migración: son objetos del servidor y los crea el script de arranque de la
base (infra/postgres/init) con un superusuario.

Revision ID: 0001
Revises:
Create Date: 2026-10-13
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DB = Path(__file__).resolve().parents[2] / "db"
SCRIPTS = ("01_esquema.sql", "02_rls.sql", "03_permisos.sql")


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        # Modo offline (alembic upgrade --sql): se imprime el SQL en vez de ejecutarlo
        contexto.impl.static_output(sql)
        return
    # Se usa el cursor del driver para que el SQL llegue tal cual, sin que
    # SQLAlchemy interprete los ':' o los '%' del texto.
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


def upgrade() -> None:
    for nombre in SCRIPTS:
        _ejecutar((DB / nombre).read_text(encoding="utf-8"))


def downgrade() -> None:
    # Borra todo lo que creó upgrade en public y deja intacta la extensión
    # btree_gist, que no es parte de esta migración.
    _ejecutar(
        """
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN
                SELECT c.relname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
                  AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype = 'e')
            LOOP
                EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.relname);
            END LOOP;
            FOR r IN
                SELECT p.oid::regprocedure AS firma FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public'
                  AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
            LOOP
                EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.firma);
            END LOOP;
            -- Permisos que 03_permisos.sql deja sobre el esquema y para tablas futuras
            ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM matu_app;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM matu_app;
            REVOKE USAGE ON SCHEMA public FROM matu_app, matu_publisher, matu_scheduler;
        END $$;
        """
    )

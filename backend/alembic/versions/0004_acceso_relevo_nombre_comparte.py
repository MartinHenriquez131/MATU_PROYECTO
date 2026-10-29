"""MATU-18: el acceso de relevo guarda el nombre de pila de quien comparte y cuándo declaró haber
avisado al relevo.

Decisión 28 del contrato (docs/api/README.md): el relevo ve "Carmen te compartió la ficha de María"
antes del PIN, y nunca lee usuario. Por eso acceso_relevo copia el nombre de pila de quien comparte al
crearse, igual que nombre_pila_persona.

- La columna nace NOT NULL y con un CHECK de texto no vacío. No hay un valor por omisión que tenga
  sentido: si la tabla tuviera filas, la migración falla en vez de inventar un nombre. Hoy no hay
  accesos creados por la API (MATU-18 es la primera historia que los crea) y solo hay datos sintéticos.
- No es una tabla nueva: RLS y las políticas de acceso_relevo (02_rls.sql) cubren la columna. matu_app
  ya tiene SELECT, INSERT y UPDATE sobre la tabla.
- relevo_informado_en (decisión 34 de Jorge, 28-10): cuándo quien comparte declaró que le avisó al
  relevo que MATU guarda su nombre y su teléfono. NOT NULL por la misma razón.
- indice_token.revocado_en (decisión 23) es de MATU-19 o MATU-20, no de esta migración.

downgrade() deja el esquema como en 0003. Lo verifica tests/test_migraciones.py.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    # Igual que en 0001 a 0003: el SQL llega tal cual al driver, sin interpretar ':' ni '%'.
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


UPGRADE = """
ALTER TABLE acceso_relevo ADD COLUMN nombre_pila_comparte text NOT NULL
    CONSTRAINT acceso_relevo_nombre_comparte CHECK (btrim(nombre_pila_comparte) <> ''),
    ADD COLUMN relevo_informado_en timestamptz NOT NULL;
COMMENT ON COLUMN acceso_relevo.nombre_pila_comparte IS
    'Nombre de pila de quien compartió, copiado al crear el acceso: el relevo nunca lee usuario';
COMMENT ON COLUMN acceso_relevo.relevo_informado_en IS
    'Cuándo quien comparte declaró que avisó al relevo de qué datos guarda MATU (decisión 34)';
"""

DOWNGRADE = """
ALTER TABLE acceso_relevo DROP COLUMN relevo_informado_en, DROP COLUMN nombre_pila_comparte;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

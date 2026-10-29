"""MATU-14: quién lee la auditoría (decisión 36, de Jorge, 28-10).

- El administrador del grupo lee todas las filas de su grupo.
- Cada miembro lee solo sus propias filas (actor_ref = app.usuario_id), en el grupo del contexto.
- Nadie más tiene lectura amplia: se quita auditoria_operacion (operación leía todo).

Reemplaza solo las políticas de SELECT de auditoria (02_rls.sql). Las de INSERT (auditoria_insertar,
auditoria_relevo) no cambian. No hay tabla nueva ni permisos nuevos.

downgrade() deja las políticas como en 0004. Lo verifica tests/test_migraciones.py.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


UPGRADE = """
DROP POLICY auditoria_familia ON auditoria;
DROP POLICY auditoria_operacion ON auditoria;
CREATE POLICY auditoria_familia ON auditoria FOR SELECT USING (
    grupo_id = app_grupo() AND (
        actor_ref = app_usuario()
        OR EXISTS (SELECT 1 FROM membresia m
                   WHERE m.grupo_id = app_grupo() AND m.usuario_id = app_usuario()
                     AND m.estado = 'activa' AND m.rol = 'admin')));
"""

DOWNGRADE = """
DROP POLICY auditoria_familia ON auditoria;
CREATE POLICY auditoria_familia   ON auditoria FOR SELECT USING (grupo_id = app_grupo());
CREATE POLICY auditoria_operacion ON auditoria FOR SELECT USING (app_rol() = 'operacion');
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

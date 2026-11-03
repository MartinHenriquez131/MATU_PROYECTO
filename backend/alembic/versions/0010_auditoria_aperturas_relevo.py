"""MATU-45: la familia ve quién abrió la ficha (RF-08).

Desde 0005 solo el admin lee las filas de auditoria de su grupo, y cada miembro solo las suyas
(actor_ref = app.usuario_id). Las filas del relevo tienen actor_ref = el acceso, así que el cuidador y
el pagador con puede_ver_plan no las veían, aunque el contrato (relevo.openapi.yaml,
GET /plan/aperturas) dice que listan aperturas admin, cuidador y pagador con puede_ver_plan.

Política nueva auditoria_aperturas_relevo (FOR SELECT, se suma con OR a auditoria_familia): las filas
del grupo del contexto con actor_tipo = 'relevo' y una de las cuatro acciones que lista la ruta
(relevo.presentar, relevo.abrir, relevo.pin_incorrecto, relevo.bloqueo), y solo si el miembro puede ver
el plan (app_puede_ver_plan(), la misma regla de acceso_familia). relevo.canje no se expone: no está en
el enumerado del contrato. Las lecturas de miembros (plan.leer) siguen como en 0005.

down_revision 0009: se encadena después de 0009 (MATU-36, perfil de consumo), ya en main. El SQL no
depende de 0009.

downgrade() deja las políticas como en 0009 (0009 no toca auditoria: son las de 0008). Lo verifica
tests/test_migraciones.py.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
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
CREATE POLICY auditoria_aperturas_relevo ON auditoria FOR SELECT USING (
    grupo_id = app_grupo()
    AND actor_tipo = 'relevo'
    AND accion IN ('relevo.presentar', 'relevo.abrir', 'relevo.pin_incorrecto', 'relevo.bloqueo')
    AND (SELECT app_puede_ver_plan()));
"""

DOWNGRADE = """
DROP POLICY auditoria_aperturas_relevo ON auditoria;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

"""S2: el consentimiento es inalterable; solo se registra la revocación.

- matu_app pierde UPDATE y DELETE sobre consentimiento y conserva UPDATE (revocado_en).
- Trigger consentimiento_solo_revocacion: rechaza cambios fuera de revocado_en y permite pasar
  revocado_en de NULL a un valor una sola vez.
- Trigger consentimiento_sin_borrado: rechaza todo DELETE, también al dueño.
- consentimiento_familia (FOR ALL) se separa en SELECT, INSERT y UPDATE con la misma condición.
- Se documenta el esquema de consentimiento.evidencia (MATU-07, care_circle/domain/personas.py).

downgrade() deja todo como en 0005. Lo verifica tests/test_migraciones.py.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
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
REVOKE UPDATE, DELETE ON consentimiento FROM matu_app;
GRANT UPDATE (revocado_en) ON consentimiento TO matu_app;

CREATE FUNCTION consentimiento_solo_revocacion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW) - 'revocado_en') IS DISTINCT FROM (to_jsonb(OLD) - 'revocado_en') THEN
        RAISE EXCEPTION 'consentimiento es inalterable: solo se registra la revocación'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.revocado_en IS NOT NULL OR NEW.revocado_en IS NULL THEN
        RAISE EXCEPTION 'la revocación del consentimiento se registra una sola vez'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER consentimiento_solo_revocacion BEFORE UPDATE ON consentimiento
    FOR EACH ROW EXECUTE FUNCTION consentimiento_solo_revocacion();

CREATE FUNCTION consentimiento_sin_borrado() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'consentimiento no se borra' USING ERRCODE = 'insufficient_privilege';
END $$;
CREATE TRIGGER consentimiento_sin_borrado BEFORE DELETE ON consentimiento
    FOR EACH ROW EXECUTE FUNCTION consentimiento_sin_borrado();

COMMENT ON COLUMN consentimiento.evidencia IS
'Evidencia mínima (MATU-07), JSON: {"esquema": 1, "declaracion": {"id": "declaracion_<calidad>", '
'"version": "<version_politica>"}, "aviso": {"id", "version", "sha256"} solo si la calidad lleva '
'aviso, "modalidad": "registrada_por_usuario_en_presencia_del_titular" solo si calidad = titular}. '
'Sin IP, sin agente de usuario y sin texto libre.';

DROP POLICY consentimiento_familia ON consentimiento;
CREATE POLICY consentimiento_familia_leer ON consentimiento FOR SELECT USING (grupo_id = app_grupo());
CREATE POLICY consentimiento_familia_crear ON consentimiento FOR INSERT WITH CHECK (grupo_id = app_grupo());
CREATE POLICY consentimiento_familia_revocar ON consentimiento FOR UPDATE
    USING (grupo_id = app_grupo()) WITH CHECK (grupo_id = app_grupo());
"""

DOWNGRADE = """
DROP POLICY consentimiento_familia_leer ON consentimiento;
DROP POLICY consentimiento_familia_crear ON consentimiento;
DROP POLICY consentimiento_familia_revocar ON consentimiento;
CREATE POLICY consentimiento_familia ON consentimiento FOR ALL USING (grupo_id = app_grupo());

COMMENT ON COLUMN consentimiento.evidencia IS NULL;

DROP TRIGGER consentimiento_sin_borrado ON consentimiento;
DROP FUNCTION consentimiento_sin_borrado();
DROP TRIGGER consentimiento_solo_revocacion ON consentimiento;
DROP FUNCTION consentimiento_solo_revocacion();

REVOKE UPDATE (revocado_en) ON consentimiento FROM matu_app;
GRANT UPDATE, DELETE ON consentimiento TO matu_app;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

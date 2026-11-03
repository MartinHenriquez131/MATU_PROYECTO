"""MATU-57: celular verificado y su canal preferido (decisiones 81 a 90).

a) usuario.celular_verificado_en (timestamptz, NULL): cuándo la persona confirmó su celular con un
   código. Mientras sea NULL, la recuperación del acceso va al correo (decisión de Jorge del 03-11).
b) usuario.celular_canal ('sms' o 'whatsapp', por omisión 'sms'): la preferencia de canal, prevista
   pero aún sin uso hasta que Jorge decida (pendiente). El envío del semestre es simulado.
c) Trigger usuario_celular_cambia: si cambia telefono, celular_verificado_en vuelve a NULL. Así un
   número nuevo nunca hereda la verificación del anterior, la cambie quien la cambie.

Sin tabla nueva: los códigos viven en Redis con TTL (decisión 83), por la huella del usuario. Las
políticas de usuario (usuario_propio) ya cubren las columnas nuevas.

Encadenamiento: esta rama (matu-57) sale de matu-39, que llega hasta 0008. Al fusionar a main, donde
existen 0009 a 0011, down_revision se cambia a "0011" en el mismo pull request; la migración no
depende de nada de 0009 a 0011.

downgrade() deja el esquema como en 0008: borra el trigger, su función y las dos columnas.

Revision ID: 0012
Revises: 0008
Create Date: 2026-11-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0008"
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
ALTER TABLE usuario ADD COLUMN celular_verificado_en timestamptz;
ALTER TABLE usuario ADD COLUMN celular_canal text NOT NULL DEFAULT 'sms';
ALTER TABLE usuario ADD CONSTRAINT usuario_celular_canal_check CHECK (celular_canal IN ('sms', 'whatsapp'));
ALTER TABLE usuario ADD CONSTRAINT usuario_celular_verificado_con_numero CHECK (
    celular_verificado_en IS NULL OR telefono IS NOT NULL);
COMMENT ON COLUMN usuario.celular_verificado_en IS
    'MATU-57: cuándo se confirmó el celular con un código. NULL: la recuperación va al correo';
COMMENT ON COLUMN usuario.celular_canal IS 'MATU-57: canal preferido del celular, previsto (pendiente de Jorge)';

CREATE FUNCTION usuario_celular_cambia() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS
$$
BEGIN
    IF NEW.telefono IS DISTINCT FROM OLD.telefono THEN
        NEW.celular_verificado_en := NULL;
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER usuario_celular_cambia BEFORE UPDATE OF telefono ON usuario
    FOR EACH ROW EXECUTE FUNCTION usuario_celular_cambia();
"""

DOWNGRADE = """
DROP TRIGGER usuario_celular_cambia ON usuario;
DROP FUNCTION usuario_celular_cambia();
ALTER TABLE usuario DROP CONSTRAINT usuario_celular_verificado_con_numero;
ALTER TABLE usuario DROP CONSTRAINT usuario_celular_canal_check;
ALTER TABLE usuario DROP COLUMN celular_canal;
ALTER TABLE usuario DROP COLUMN celular_verificado_en;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

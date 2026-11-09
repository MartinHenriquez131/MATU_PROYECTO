"""MATU-72: borrar los datos de la persona al tiro, cuando se pide (decisiones 149 a 157, C11).

Cadena: 0017 (MATU-51) -> 0018. down_revision = "0017".

a) consentimiento_revocacion_motivo admite 'borrado' (D2), además de 'retiro' y 'renovacion'. El borrado
   retira con ese motivo toda autorización no revocada de la persona. El trigger consentimiento_solo_revocacion
   de la 0016 no cambia: el motivo se fija una vez y junto con revocado_en.

b) persona_cuidada.datos_borrados_en timestamptz, la marca durable del borrado (D2). nivel_apoyo acepta NULL
   solo si eliminado_en no es nulo (persona_cuidada_nivel_apoyo_presente), y una persona borrada tiene
   eliminado_en y deja nivel_apoyo y direccion_entrega_id en NULL (persona_cuidada_borrada, D5). El CHECK de
   los valores de nivel_apoyo de 0001 no cambia: NULL lo cumple.

c) Trigger persona_borrada_fija (BEFORE UPDATE): una persona con datos_borrados_en no se vuelve a modificar,
   ni por la API ni por SQL directo. Volver es registrarla de nuevo (MATU-07). DELETE no lo toca.

d) Barrera por rol (C2): persona_familia (ALL, cualquier miembro del grupo) se divide en persona_familia_leer
   (SELECT, todo el grupo, como antes) y persona_familia_crear, persona_familia_editar y persona_familia_borrar
   (INSERT, UPDATE y DELETE), que exigen app_retira_autorizacion() de la 0016: una membresía activa de admin o
   cuidador. Son los mismos que dan de alta, retiran y borran. persona_operacion (SELECT) no cambia.
   matu_app ya tiene UPDATE sobre la tabla completa: la columna nueva no necesita otro GRANT.

backend/db/*.sql no se tocan: son el esquema de 0001.

downgrade() deja el esquema como en 0017. Se detiene, en vez de perder la marca, si hay una persona borrada o
una autorización con motivo 'borrado'. matu_owner está sujeto a RLS forzado y no las vería: la revisión se
hace sin FORCE, solo durante esa sentencia y dentro de la transacción de la migración, como el relleno de 0016.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


# El comentario de la 0016, para el downgrade
COMENTARIO_MOTIVO_0016 = (
    "'MATU-44 (D4): retiro (corta los accesos de relevo) o renovacion (no corta). Se fija junto con revocado_en'"
)

ESCRIBE = "grupo_id = app_grupo() AND (SELECT app_retira_autorizacion())"

UPGRADE = f"""
-- (a) El borrado retira con su propio motivo
ALTER TABLE consentimiento DROP CONSTRAINT consentimiento_revocacion_motivo;
ALTER TABLE consentimiento ADD CONSTRAINT consentimiento_revocacion_motivo
    CHECK (revocacion_motivo IN ('retiro', 'renovacion', 'borrado'));
COMMENT ON COLUMN consentimiento.revocacion_motivo IS
    'MATU-44 (D4): retiro (corta los accesos de relevo) o renovacion (no corta). MATU-72 (D2): borrado (la persona'
    ' pidió borrar sus datos). Se fija junto con revocado_en';

-- (b) La marca durable del borrado
ALTER TABLE persona_cuidada ADD COLUMN datos_borrados_en timestamptz;
ALTER TABLE persona_cuidada ALTER COLUMN nivel_apoyo DROP NOT NULL;
ALTER TABLE persona_cuidada ADD CONSTRAINT persona_cuidada_nivel_apoyo_presente
    CHECK (nivel_apoyo IS NOT NULL OR eliminado_en IS NOT NULL);
ALTER TABLE persona_cuidada ADD CONSTRAINT persona_cuidada_borrada
    CHECK (datos_borrados_en IS NULL
           OR (eliminado_en IS NOT NULL AND nivel_apoyo IS NULL AND direccion_entrega_id IS NULL));
COMMENT ON COLUMN persona_cuidada.datos_borrados_en IS
    'MATU-72 (D2): cuándo se borraron sus datos a pedido. La fila queda sin datos, con su id, y no se modifica más';

-- (c) Una persona borrada no se vuelve a modificar
CREATE FUNCTION persona_borrada_fija() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.datos_borrados_en IS NOT NULL THEN
        RAISE EXCEPTION 'los datos de esta persona se borraron: la fila no se modifica'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER persona_borrada_fija BEFORE UPDATE ON persona_cuidada
    FOR EACH ROW EXECUTE FUNCTION persona_borrada_fija();

-- (d) Leen todos los del grupo; escriben solo admin y cuidador
DROP POLICY persona_familia ON persona_cuidada;
CREATE POLICY persona_familia_leer ON persona_cuidada FOR SELECT USING (grupo_id = app_grupo());
CREATE POLICY persona_familia_crear ON persona_cuidada FOR INSERT WITH CHECK ({ESCRIBE});
CREATE POLICY persona_familia_editar ON persona_cuidada FOR UPDATE USING ({ESCRIBE}) WITH CHECK ({ESCRIBE});
CREATE POLICY persona_familia_borrar ON persona_cuidada FOR DELETE USING ({ESCRIBE});
"""

DOWNGRADE = f"""
-- No se pierde la marca de un borrado: si hay uno, el downgrade se detiene
ALTER TABLE persona_cuidada NO FORCE ROW LEVEL SECURITY;
ALTER TABLE consentimiento NO FORCE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM persona_cuidada WHERE datos_borrados_en IS NOT NULL)
       OR EXISTS (SELECT 1 FROM consentimiento WHERE revocacion_motivo = 'borrado') THEN
        RAISE EXCEPTION 'hay personas borradas (MATU-72): el downgrade de 0018 perdería la marca'
            USING ERRCODE = 'object_in_use';
    END IF;
END $$;
ALTER TABLE consentimiento FORCE ROW LEVEL SECURITY;
ALTER TABLE persona_cuidada FORCE ROW LEVEL SECURITY;

DROP POLICY persona_familia_borrar ON persona_cuidada;
DROP POLICY persona_familia_editar ON persona_cuidada;
DROP POLICY persona_familia_crear ON persona_cuidada;
DROP POLICY persona_familia_leer ON persona_cuidada;
CREATE POLICY persona_familia ON persona_cuidada FOR ALL USING (grupo_id = app_grupo());

DROP TRIGGER persona_borrada_fija ON persona_cuidada;
DROP FUNCTION persona_borrada_fija();

ALTER TABLE persona_cuidada DROP CONSTRAINT persona_cuidada_borrada;
ALTER TABLE persona_cuidada DROP CONSTRAINT persona_cuidada_nivel_apoyo_presente;
ALTER TABLE persona_cuidada ALTER COLUMN nivel_apoyo SET NOT NULL;
ALTER TABLE persona_cuidada DROP COLUMN datos_borrados_en;

ALTER TABLE consentimiento DROP CONSTRAINT consentimiento_revocacion_motivo;
ALTER TABLE consentimiento ADD CONSTRAINT consentimiento_revocacion_motivo
    CHECK (revocacion_motivo IN ('retiro', 'renovacion'));
COMMENT ON COLUMN consentimiento.revocacion_motivo IS {COMENTARIO_MOTIVO_0016};
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

"""MATU-44: retirar una autorización, con su motivo, la barrera por rol y la destrucción de la ficha a los 90 días.

Cadena: 0015 (MATU-60) -> 0016. Decisiones 123 a 135 de docs/api/README.md.

a) consentimiento.revocacion_motivo text (D4): 'retiro' o 'renovacion', fijado junto con revocado_en.
   - CHECK consentimiento_revocacion_motivo: uno de los dos valores.
   - CHECK consentimiento_revocacion_completa: revocado_en y revocacion_motivo van juntos.
   - Las revocaciones que ya existen quedan como 'retiro'. matu_owner está sujeto a RLS forzado y el
     trigger de 0006 rechaza el cambio, así que el relleno se hace sin FORCE y con el trigger apagado,
     solo durante esa sentencia y dentro de la transacción de la migración.
   - matu_app recibe UPDATE (revocacion_motivo).

b) El trigger consentimiento_solo_revocacion (0006) admite fijar revocado_en y revocacion_motivo una
   sola vez y juntas. Todo lo demás sigue inalterable. El corte de los accesos de relevo NO va en un
   trigger: va en el caso de uso del retiro (D4).

c) Barrera por rol: consentimiento_familia_revocar exige app_retira_autorizacion(), una membresía activa
   de admin o cuidador de app.usuario_id en el grupo del contexto. Antes cualquier miembro podía fijar
   revocado_en con SQL directo.

d) Destrucción de la ficha a los 90 días del retiro (D3, decisión 129): plan_destruir_claves(limite,
   ahora), SECURITY DEFINER, dueño matu_owner, search_path fijo, EXECUTE solo para matu_app, que exige
   app.rol = 'operacion', limite <= ahora - 90 días y ahora <= now() + 5 minutos, igual que
   consumo_conservar (0009). Destruye la clave de datos (dek NULL y destruida_en = ahora, el borrado
   criptográfico de MATU-11) de cada persona sin un consentimiento no revocado para plan_cuidado y cuya
   última revocación es igual o anterior a limite, y registra clave.destruir (actor sistema, sin
   detalle) en la misma sentencia. Idempotente: no toca una clave ya destruida. Devuelve un contador.
   matu_owner necesita leer y actualizar clave_datos bajo RLS forzado: clave_destruccion_leer y
   clave_destruccion, solo para él y solo con app.rol = 'operacion'. Lo de la familia no cambia.

backend/db/*.sql no se tocan: son el esquema de 0001.

downgrade() deja el esquema como en 0015 y se pierde revocacion_motivo.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
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
-- (a) El motivo de la revocación
ALTER TABLE consentimiento ADD COLUMN revocacion_motivo text;
ALTER TABLE consentimiento NO FORCE ROW LEVEL SECURITY;
ALTER TABLE consentimiento DISABLE TRIGGER consentimiento_solo_revocacion;
UPDATE consentimiento SET revocacion_motivo = 'retiro' WHERE revocado_en IS NOT NULL;
ALTER TABLE consentimiento ENABLE TRIGGER consentimiento_solo_revocacion;
ALTER TABLE consentimiento FORCE ROW LEVEL SECURITY;
ALTER TABLE consentimiento ADD CONSTRAINT consentimiento_revocacion_motivo
    CHECK (revocacion_motivo IN ('retiro', 'renovacion'));
ALTER TABLE consentimiento ADD CONSTRAINT consentimiento_revocacion_completa
    CHECK ((revocado_en IS NULL) = (revocacion_motivo IS NULL));
COMMENT ON COLUMN consentimiento.revocacion_motivo IS
    'MATU-44 (D4): retiro (corta los accesos de relevo) o renovacion (no corta). Se fija junto con revocado_en';
GRANT UPDATE (revocacion_motivo) ON consentimiento TO matu_app;

-- (b) Solo la revocación, una vez y con su motivo
CREATE OR REPLACE FUNCTION consentimiento_solo_revocacion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW) - 'revocado_en' - 'revocacion_motivo')
       IS DISTINCT FROM (to_jsonb(OLD) - 'revocado_en' - 'revocacion_motivo') THEN
        RAISE EXCEPTION 'consentimiento es inalterable: solo se registra la revocación'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF OLD.revocado_en IS NOT NULL OR NEW.revocado_en IS NULL OR NEW.revocacion_motivo IS NULL THEN
        RAISE EXCEPTION 'la revocación del consentimiento se registra una sola vez, con su motivo'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;

-- (c) Retiran solo admin y cuidador
CREATE FUNCTION app_retira_autorizacion() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT EXISTS (SELECT 1 FROM membresia m
                  WHERE m.grupo_id = app_grupo() AND m.usuario_id = app_usuario()
                    AND m.estado = 'activa' AND m.rol IN ('admin', 'cuidador')) $$;
DROP POLICY consentimiento_familia_revocar ON consentimiento;
CREATE POLICY consentimiento_familia_revocar ON consentimiento FOR UPDATE
    USING (grupo_id = app_grupo() AND (SELECT app_retira_autorizacion()))
    WITH CHECK (grupo_id = app_grupo() AND (SELECT app_retira_autorizacion()));

-- (d) La ficha se destruye 90 días después del retiro
CREATE POLICY clave_destruccion_leer ON clave_datos FOR SELECT TO matu_owner USING (app_rol() = 'operacion');
CREATE POLICY clave_destruccion ON clave_datos FOR UPDATE TO matu_owner
    USING (app_rol() = 'operacion') WITH CHECK (app_rol() = 'operacion' AND dek_cifrada_con_kek IS NULL);

CREATE FUNCTION plan_destruir_claves(limite timestamptz, ahora timestamptz) RETURNS integer
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    n integer := 0;
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'plan_destruir_claves exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '90 days' THEN
        RAISE EXCEPTION 'la ficha se conserva 90 días después del retiro' USING ERRCODE = 'invalid_parameter_value';
    END IF;

    WITH destruidas AS (
        UPDATE public.clave_datos k SET dek_cifrada_con_kek = NULL, destruida_en = ahora
         WHERE k.destruida_en IS NULL
           AND NOT EXISTS (
                   SELECT 1 FROM public.consentimiento c
                    WHERE c.persona_cuidada_id = k.persona_cuidada_id AND c.finalidad = 'plan_cuidado'
                      AND c.revocado_en IS NULL)
           AND (SELECT max(c.revocado_en) FROM public.consentimiento c
                 WHERE c.persona_cuidada_id = k.persona_cuidada_id AND c.finalidad = 'plan_cuidado') <= limite
        RETURNING k.id, k.grupo_id)
    INSERT INTO public.auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id, ocurrido_en)
    SELECT d.grupo_id, 'sistema', NULL, 'clave.destruir', 'clave_datos', d.id, ahora FROM destruidas d;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END
$$;
REVOKE ALL ON FUNCTION plan_destruir_claves(timestamptz, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION plan_destruir_claves(timestamptz, timestamptz) TO matu_app;
"""

DOWNGRADE = """
DROP FUNCTION plan_destruir_claves(timestamptz, timestamptz);
DROP POLICY clave_destruccion ON clave_datos;
DROP POLICY clave_destruccion_leer ON clave_datos;

DROP POLICY consentimiento_familia_revocar ON consentimiento;
CREATE POLICY consentimiento_familia_revocar ON consentimiento FOR UPDATE
    USING (grupo_id = app_grupo()) WITH CHECK (grupo_id = app_grupo());
DROP FUNCTION app_retira_autorizacion();

CREATE OR REPLACE FUNCTION consentimiento_solo_revocacion() RETURNS trigger LANGUAGE plpgsql AS $$
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

REVOKE UPDATE (revocacion_motivo) ON consentimiento FROM matu_app;
ALTER TABLE consentimiento DROP CONSTRAINT consentimiento_revocacion_completa;
ALTER TABLE consentimiento DROP CONSTRAINT consentimiento_revocacion_motivo;
ALTER TABLE consentimiento DROP COLUMN revocacion_motivo;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

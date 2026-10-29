"""MATU-19: abrir la ficha como relevo con enlace y PIN (RF-06).

a) indice_token.revocado_en (decisión 23). Con revocado_en y expira_en en indice_token, la
   presentación, el canje y la ficha del relevo distinguen "revocado" de "vencido" con una sola
   lectura, sin el rol 'sistema' en una ruta pública. MATU-20 la fija al revocar.

b) La política acceso_relevo_propio (FOR ALL, 02_rls.sql) se reemplaza por dos: acceso_relevo_leer
   (SELECT) y acceso_relevo_contar (UPDATE). El relevo ya no puede insertar ni borrar accesos. El
   trigger acceso_relevo_cambios_relevo rechaza, cuando app.rol = 'relevo', cualquier cambio fuera
   de pin_intentos_fallidos, usos y ultimo_uso_en. Lo que hace la familia (acceso_familia) no cambia.

c) relevo_autorizacion_vigente(ahora): SECURITY DEFINER, dueño matu_owner, search_path fijo (pg_temp al
   final), tablas calificadas con public.
   EXECUTE solo para matu_app. Usa el acceso de app.acceso_relevo_id y devuelve SOLO un booleano: si
   la persona del acceso tiene consentimiento no revocado para plan_cuidado y, si lo dio un cuidador
   de hecho, la revisión anual vence después de ``ahora`` (decisión 33 en el relevo, de Martín del
   28-10). ``ahora`` es el instante del puerto Reloj, no now() de la base.
   matu_owner no evade RLS (FORCE): la política consentimiento_autorizacion_relevo le deja leer, solo
   a matu_owner y solo en contexto de relevo, el consentimiento de la persona del acceso. matu_app
   sigue sin ver consentimiento como relevo.

backend/db/*.sql no se tocan: son el esquema de 0001, igual que en 0004 a 0006.

downgrade() deja el esquema como en 0006. Lo verifica tests/test_migraciones.py.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    # Igual que en 0001 a 0006: el SQL llega tal cual al driver, sin interpretar ':' ni '%'.
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


UPGRADE = """
-- (a) Revocado frente a vencido, en una sola lectura (decisión 23)
ALTER TABLE indice_token ADD COLUMN revocado_en timestamptz;
COMMENT ON COLUMN indice_token.revocado_en IS
    'Copia de acceso_relevo.revocado_en, fijada en la misma transacción al revocar (decisión 23)';

-- (b) El relevo lee y cuenta su acceso, sin insertar ni borrar
DROP POLICY acceso_relevo_propio ON acceso_relevo;
CREATE POLICY acceso_relevo_leer ON acceso_relevo FOR SELECT USING (
    app_rol() = 'relevo' AND id = app_acceso_relevo()
    AND revocado_en IS NULL AND expira_en > now());
CREATE POLICY acceso_relevo_contar ON acceso_relevo FOR UPDATE USING (
    app_rol() = 'relevo' AND id = app_acceso_relevo()
    AND revocado_en IS NULL AND expira_en > now())
    WITH CHECK (app_rol() = 'relevo' AND id = app_acceso_relevo());

CREATE FUNCTION acceso_relevo_limitar_relevo() RETURNS trigger LANGUAGE plpgsql AS
$$
BEGIN
    IF app_rol() = 'relevo' AND
       (to_jsonb(NEW) - ARRAY['pin_intentos_fallidos', 'usos', 'ultimo_uso_en'])
       IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['pin_intentos_fallidos', 'usos', 'ultimo_uso_en']) THEN
        RAISE EXCEPTION 'el relevo solo cambia pin_intentos_fallidos, usos y ultimo_uso_en'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER acceso_relevo_cambios_relevo BEFORE UPDATE ON acceso_relevo
    FOR EACH ROW EXECUTE FUNCTION acceso_relevo_limitar_relevo();

-- (c) ¿Sigue vigente la autorización de la persona del acceso? Solo un booleano
CREATE POLICY consentimiento_autorizacion_relevo ON consentimiento FOR SELECT TO matu_owner USING (
    app_rol() = 'relevo' AND EXISTS (
        SELECT 1 FROM acceso_relevo a JOIN plan_cuidado p ON p.id = a.plan_id
        WHERE a.id = app_acceso_relevo() AND p.persona_cuidada_id = consentimiento.persona_cuidada_id
          AND a.grupo_id = consentimiento.grupo_id));

CREATE FUNCTION relevo_autorizacion_vigente(ahora timestamptz) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
    SELECT public.app_rol() = 'relevo' AND EXISTS (
        SELECT 1 FROM public.acceso_relevo a
          JOIN public.plan_cuidado p ON p.id = a.plan_id
          JOIN public.consentimiento c ON c.persona_cuidada_id = p.persona_cuidada_id AND c.grupo_id = a.grupo_id
         WHERE a.id = public.app_acceso_relevo()
           -- Explícito además de RLS: no depende de que matu_owner esté sujeto a las políticas
           AND a.revocado_en IS NULL AND a.expira_en > now()
           AND c.finalidad = 'plan_cuidado' AND c.revocado_en IS NULL
           AND (c.calidad_otorgante <> 'cuidador_de_hecho'
                OR c.revision_vence_en IS NULL OR c.revision_vence_en > ahora))
$$;
REVOKE ALL ON FUNCTION relevo_autorizacion_vigente(timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION relevo_autorizacion_vigente(timestamptz) TO matu_app;
"""

DOWNGRADE = """
DROP FUNCTION relevo_autorizacion_vigente(timestamptz);
DROP POLICY consentimiento_autorizacion_relevo ON consentimiento;

DROP TRIGGER acceso_relevo_cambios_relevo ON acceso_relevo;
DROP FUNCTION acceso_relevo_limitar_relevo();
DROP POLICY acceso_relevo_contar ON acceso_relevo;
DROP POLICY acceso_relevo_leer ON acceso_relevo;
CREATE POLICY acceso_relevo_propio ON acceso_relevo FOR ALL USING (
    app_rol() = 'relevo' AND id = app_acceso_relevo()
    AND revocado_en IS NULL AND expira_en > now());

ALTER TABLE indice_token DROP COLUMN revocado_en;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

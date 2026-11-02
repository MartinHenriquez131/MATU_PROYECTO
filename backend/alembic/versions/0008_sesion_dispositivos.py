"""MATU-38: refresh rotativo, dispositivos y conservación de la sesión (RF-37).

a) motivo_revocacion admite 'dispositivo': sacar un dispositivo revoca sus sesiones con ese motivo.

b) RLS de operación sobre dispositivo y sesion_refresh (decisión 61). Hoy operación tiene
   sesion_operacion (FOR ALL) y dispositivo_operacion (FOR SELECT), que le dejan leer push_token y
   token_hash. Una política RLS decide filas, no columnas, y los permisos por columna son del rol de
   base (matu_app), no de app.rol: con matu_app compartido por la API y operación, ninguna de las dos
   herramientas acota columnas para operación. Por eso:
   - se borran sesion_operacion y dispositivo_operacion: como operación, matu_app no ve ninguna fila
     de las dos tablas, ni push_token ni token_hash;
   - la conservación (decisión 59) es la función iam_conservar(...), SECURITY DEFINER, dueño
     matu_owner, search_path fijo, EXECUTE solo para matu_app, que exige app.rol = 'operacion'. Solo
     BORRA filas vencidas o revocadas y devuelve dos contadores. No devuelve ninguna columna;
   - matu_owner está sujeto a RLS (FORCE): las políticas sesion_conservacion y
     dispositivo_conservacion le dejan leer y borrar, solo a matu_owner y solo con app.rol =
     'operacion', igual que consentimiento_autorizacion_relevo en 0007. Sin UPDATE ni INSERT.

c) Políticas de usuario: dispositivo_propio y sesion_propia ya acotan a usuario_id = app.usuario_id
   (FOR ALL, USING sirve también de WITH CHECK). sesion_propia se reemplaza para exigir además, al
   escribir, que el dispositivo sea del mismo usuario: así nadie cuelga una sesión propia de un
   dispositivo ajeno.

d) auditoria.detalle (jsonb), para los dos datos que MATU-38 registra y que no caben en las columnas
   de 0001: la huella del email de sesion.inicio_fallido y la cantidad de sesiones revocadas de
   dispositivo.sacar. Un CHECK admite solo esas dos claves, la huella como 64 hex y la cantidad como
   número: no puede llevar texto libre, ni el email, ni la IP.

backend/db/*.sql no se tocan: son el esquema de 0001, igual que en 0004 a 0007.

downgrade() deja el esquema como en 0007. Antes de restituir el CHECK de 0001, las sesiones
revocadas con 'dispositivo' pasan a 'operacion' (el valor de 0001 más cercano: revocadas por un
tercero), para que el CHECK no falle. La columna detalle se pierde.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    # Igual que en 0001 a 0007: el SQL llega tal cual al driver, sin interpretar ':' ni '%'.
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


UPGRADE = """
-- (a) Sacar un dispositivo
ALTER TABLE sesion_refresh DROP CONSTRAINT sesion_refresh_motivo_revocacion_check;
ALTER TABLE sesion_refresh ADD CONSTRAINT sesion_refresh_motivo_revocacion_check CHECK (
    motivo_revocacion IN ('logout', 'reutilizacion', 'cambio_clave', 'operacion', 'dispositivo'));

-- (b) Operación ya no lee dispositivo ni sesion_refresh
DROP POLICY sesion_operacion ON sesion_refresh;
DROP POLICY dispositivo_operacion ON dispositivo;

CREATE POLICY sesion_conservacion ON sesion_refresh FOR SELECT TO matu_owner USING (app_rol() = 'operacion');
CREATE POLICY sesion_conservacion_borrar ON sesion_refresh FOR DELETE TO matu_owner USING (app_rol() = 'operacion');
CREATE POLICY dispositivo_conservacion ON dispositivo FOR SELECT TO matu_owner USING (app_rol() = 'operacion');
CREATE POLICY dispositivo_conservacion_borrar ON dispositivo FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion');

-- Borra las sesiones vencidas o revocadas antes de limite_sesion y los dispositivos sin uso desde
-- limite_dispositivo que no tengan sesiones vigentes en ahora. Los tres instantes vienen del Reloj.
CREATE FUNCTION iam_conservar(limite_sesion timestamptz, limite_dispositivo timestamptz, ahora timestamptz)
    RETURNS TABLE (sesiones_borradas integer, dispositivos_borrados integer)
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    n_sesiones integer := 0;
    n_extra integer := 0;
    n_dispositivos integer := 0;
    borrables uuid[];
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'iam_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NOT (limite_sesion <= ahora AND limite_dispositivo <= ahora) THEN
        RAISE EXCEPTION 'los límites deben ser anteriores a ahora' USING ERRCODE = 'invalid_parameter_value';
    END IF;

    -- 1. Sesiones vencidas o revocadas hace más de 30 días
    WITH borradas AS (
        DELETE FROM public.sesion_refresh s
         WHERE s.expira_en <= limite_sesion
            OR (s.revocado_en IS NOT NULL AND s.revocado_en <= limite_sesion)
        RETURNING s.id)
    , indice AS (
        DELETE FROM public.indice_token t USING borradas b
         WHERE t.tipo = 'refresh' AND t.referencia_id = b.id)
    SELECT count(*) INTO n_sesiones FROM borradas;

    -- 2. Dispositivos sin uso desde limite_dispositivo y sin sesiones vigentes. Sus sesiones que
    --    quedan (no vigentes, pero aún dentro de los 30 días) se borran con ellos: la llave foránea
    --    lo exige
    SELECT coalesce(array_agg(d.id), '{}') INTO borrables FROM public.dispositivo d
     WHERE coalesce(d.ultimo_uso_en, d.creado_en) <= limite_dispositivo
       AND NOT EXISTS (
           SELECT 1 FROM public.sesion_refresh s
            WHERE s.dispositivo_id = d.id AND s.revocado_en IS NULL AND s.usado_en IS NULL
              AND s.expira_en > ahora);

    WITH borradas AS (
        DELETE FROM public.sesion_refresh s WHERE s.dispositivo_id = ANY (borrables)
        RETURNING s.id)
    , indice AS (
        DELETE FROM public.indice_token t USING borradas b
         WHERE t.tipo = 'refresh' AND t.referencia_id = b.id)
    SELECT count(*) INTO n_extra FROM borradas;

    DELETE FROM public.dispositivo d WHERE d.id = ANY (borrables);
    GET DIAGNOSTICS n_dispositivos = ROW_COUNT;

    RETURN QUERY SELECT n_sesiones + n_extra, n_dispositivos;
END
$$;
REVOKE ALL ON FUNCTION iam_conservar(timestamptz, timestamptz, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION iam_conservar(timestamptz, timestamptz, timestamptz) TO matu_app;

-- (c) Una sesión propia solo cuelga de un dispositivo propio
DROP POLICY sesion_propia ON sesion_refresh;
CREATE POLICY sesion_propia ON sesion_refresh FOR ALL
    USING (usuario_id = app_usuario())
    WITH CHECK (usuario_id = app_usuario() AND EXISTS (
        SELECT 1 FROM dispositivo d WHERE d.id = sesion_refresh.dispositivo_id AND d.usuario_id = app_usuario()));

-- (d) Detalle acotado de la auditoría de la sesión
ALTER TABLE auditoria ADD COLUMN detalle jsonb;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_detalle_acotado CHECK (
    detalle IS NULL OR (
        jsonb_typeof(detalle) = 'object'
        AND (detalle - ARRAY['huella_email', 'sesiones_revocadas']) = '{}'::jsonb
        AND (NOT detalle ? 'huella_email'
             OR (jsonb_typeof(detalle -> 'huella_email') = 'string'
                 AND detalle ->> 'huella_email' ~ '^[0-9a-f]{64}$'))
        AND (NOT detalle ? 'sesiones_revocadas'
             OR (jsonb_typeof(detalle -> 'sesiones_revocadas') = 'number'
                 AND (detalle ->> 'sesiones_revocadas') ~ '^[0-9]{1,6}$'))));
COMMENT ON COLUMN auditoria.detalle IS
    'MATU-38: solo huella_email (HMAC-SHA-256 en hex) y sesiones_revocadas (entero). Nunca texto libre';
"""

DOWNGRADE = """
ALTER TABLE auditoria DROP CONSTRAINT auditoria_detalle_acotado;
ALTER TABLE auditoria DROP COLUMN detalle;

DROP POLICY sesion_propia ON sesion_refresh;
CREATE POLICY sesion_propia ON sesion_refresh FOR ALL USING (usuario_id = app_usuario());

DROP FUNCTION iam_conservar(timestamptz, timestamptz, timestamptz);
DROP POLICY dispositivo_conservacion_borrar ON dispositivo;
DROP POLICY dispositivo_conservacion ON dispositivo;
DROP POLICY sesion_conservacion_borrar ON sesion_refresh;
DROP POLICY sesion_conservacion ON sesion_refresh;
CREATE POLICY dispositivo_operacion ON dispositivo FOR SELECT USING (app_rol() = 'operacion');
CREATE POLICY sesion_operacion ON sesion_refresh FOR ALL USING (app_rol() = 'operacion');

-- matu_owner no ve las filas de los usuarios (RLS forzado): se cambia el motivo con el contexto de
-- operación, que la política sesion_operacion recién restituida deja escribir
SELECT set_config('app.rol', 'operacion', true);
UPDATE sesion_refresh SET motivo_revocacion = 'operacion' WHERE motivo_revocacion = 'dispositivo';
SELECT set_config('app.rol', '', true);
ALTER TABLE sesion_refresh DROP CONSTRAINT sesion_refresh_motivo_revocacion_check;
ALTER TABLE sesion_refresh ADD CONSTRAINT sesion_refresh_motivo_revocacion_check CHECK (
    motivo_revocacion IN ('logout', 'reutilizacion', 'cambio_clave', 'operacion'));
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

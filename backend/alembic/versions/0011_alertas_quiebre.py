"""MATU-37: alertas de quiebre y reposiciones con RLS por operación, transiciones y conservación (RF-12).

Cadena: down_revision = "0009". La 0010 vive en la rama de MATU-45; al fusionar las dos ramas, esta
migración se encadena sobre la 0010 (se cambia down_revision a "0010" en el merge). No toca nada de lo
que hace la 0010.

a) alerta_quiebre: alerta_hereda (FOR ALL) se reemplaza por políticas separadas.
   - alerta_leer (SELECT): perfil visible del grupo del contexto, nunca con app.rol = 'operacion'.
   - alerta_materializar (INSERT): solo app.rol = 'sistema' (el trabajo diario), estado 'pendiente'.
   - alerta_cerrar_sin_aviso (INSERT): app_escribe_consumo() y estado resuelta o descartada. Es
     "Ya lo resolví" sobre un insumo cuya alerta el trabajo diario aún no creó (decisión 76): la
     familia nunca crea una alerta abierta, que dispararía un aviso.
   - alerta_notificar (UPDATE): solo 'sistema'.
   - alerta_cerrar (UPDATE): app_escribe_consumo() (admin o cuidador activo).
   - Sin DELETE para nadie de matu_app: solo cae por ON DELETE CASCADE del perfil, o por conservación.
   El trigger alerta_transicion fija lo que el UPDATE puede cambiar: id, perfil_id, fecha_prevista y
   creada_en nunca; una alerta cerrada no cambia; pendiente -> notificada solo 'sistema';
   pendiente|notificada -> resuelta|descartada cualquiera que pase RLS. El CHECK alerta_quiebre_cierre
   exige cerrada_en en las cerradas y solo en ellas.

b) reposicion: reposicion_hereda (FOR ALL) se reemplaza por reposicion_leer (SELECT del grupo, salvo
   operación), reposicion_declarar (INSERT, app_escribe_consumo(), origen 'declarada' y
   registrada_por = app.usuario_id) y reposicion_pedido (INSERT, solo 'sistema', origen
   'pedido_matu'). Sin UPDATE ni DELETE: solo la cascada del perfil.

c) Conservación (decisión 77): quiebre_conservar(limite_alertas, limite_eventos, ahora), SECURITY
   DEFINER, dueño matu_owner, search_path fijo, EXECUTE solo para matu_app, exige app.rol =
   'operacion' como consumo_conservar (0009). Borra las alertas cerradas con cerrada_en <=
   limite_alertas, las notificaciones con creada_en <= limite_alertas y los eventos del outbox ya
   publicados con publicado_en <= limite_eventos. limite_alertas debe ser al menos 90 días anterior a
   ahora, limite_eventos al menos 30, y ahora no puede pasar de now() + 5 minutos. Devuelve tres
   contadores. matu_owner está sujeto a RLS (FORCE): alerta_conservacion, alerta_conservacion_borrar y
   notificacion_conservacion_borrar se lo permiten solo con app.rol = 'operacion'.

backend/db/*.sql no se tocan. downgrade() deja el esquema como en 0009.

Revision ID: 0011
Revises: 0009
Create Date: 2026-11-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
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
-- (a) alerta_quiebre
DROP POLICY alerta_hereda ON alerta_quiebre;

CREATE POLICY alerta_leer ON alerta_quiebre FOR SELECT USING (
    app_rol() IS DISTINCT FROM 'operacion' AND EXISTS (
        SELECT 1 FROM perfil_consumo p WHERE p.id = alerta_quiebre.perfil_id AND p.grupo_id = app_grupo()));
CREATE POLICY alerta_materializar ON alerta_quiebre FOR INSERT WITH CHECK (
    app_rol() = 'sistema' AND estado = 'pendiente' AND EXISTS (
        SELECT 1 FROM perfil_consumo p WHERE p.id = alerta_quiebre.perfil_id AND p.grupo_id = app_grupo()));
CREATE POLICY alerta_cerrar_sin_aviso ON alerta_quiebre FOR INSERT WITH CHECK (
    app_escribe_consumo() AND estado IN ('resuelta', 'descartada') AND EXISTS (
        SELECT 1 FROM perfil_consumo p WHERE p.id = alerta_quiebre.perfil_id AND p.grupo_id = app_grupo()));
CREATE POLICY alerta_notificar ON alerta_quiebre FOR UPDATE
    USING (app_rol() = 'sistema' AND EXISTS (
        SELECT 1 FROM perfil_consumo p WHERE p.id = alerta_quiebre.perfil_id AND p.grupo_id = app_grupo()))
    WITH CHECK (app_rol() = 'sistema' AND EXISTS (
        SELECT 1 FROM perfil_consumo p WHERE p.id = alerta_quiebre.perfil_id AND p.grupo_id = app_grupo()));
CREATE POLICY alerta_cerrar ON alerta_quiebre FOR UPDATE
    USING (app_escribe_consumo() AND EXISTS (
        SELECT 1 FROM perfil_consumo p WHERE p.id = alerta_quiebre.perfil_id AND p.grupo_id = app_grupo()))
    WITH CHECK (app_escribe_consumo() AND EXISTS (
        SELECT 1 FROM perfil_consumo p WHERE p.id = alerta_quiebre.perfil_id AND p.grupo_id = app_grupo()));

ALTER TABLE alerta_quiebre ADD CONSTRAINT alerta_quiebre_cierre
    CHECK ((estado IN ('resuelta', 'descartada')) = (cerrada_en IS NOT NULL));

CREATE FUNCTION alerta_transicion() RETURNS trigger LANGUAGE plpgsql AS
$$
BEGIN
    IF NEW.id <> OLD.id OR NEW.perfil_id <> OLD.perfil_id OR NEW.fecha_prevista <> OLD.fecha_prevista
       OR NEW.creada_en <> OLD.creada_en THEN
        RAISE EXCEPTION 'la alerta no cambia de perfil ni de fecha' USING ERRCODE = 'check_violation';
    END IF;
    IF OLD.estado IN ('resuelta', 'descartada') THEN
        RAISE EXCEPTION 'la alerta ya está cerrada' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.estado = 'notificada' AND OLD.estado = 'pendiente' THEN
        IF app_rol() IS DISTINCT FROM 'sistema' OR NEW.notificada_en IS NULL THEN
            RAISE EXCEPTION 'solo el sistema marca una alerta como avisada' USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.estado IN ('resuelta', 'descartada') THEN
        IF NEW.notificada_en IS DISTINCT FROM OLD.notificada_en THEN
            RAISE EXCEPTION 'cerrar no cambia cuándo se avisó' USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'transición de alerta no permitida' USING ERRCODE = 'check_violation';
END
$$;
CREATE TRIGGER alerta_transicion BEFORE UPDATE ON alerta_quiebre
    FOR EACH ROW EXECUTE FUNCTION alerta_transicion();

-- (b) reposicion
DROP POLICY reposicion_hereda ON reposicion;
CREATE POLICY reposicion_leer ON reposicion FOR SELECT USING (
    app_rol() IS DISTINCT FROM 'operacion' AND EXISTS (
        SELECT 1 FROM perfil_consumo p WHERE p.id = reposicion.perfil_id AND p.grupo_id = app_grupo()));
CREATE POLICY reposicion_declarar ON reposicion FOR INSERT WITH CHECK (
    app_escribe_consumo() AND origen = 'declarada' AND registrada_por = app_usuario() AND EXISTS (
        SELECT 1 FROM perfil_consumo p WHERE p.id = reposicion.perfil_id AND p.grupo_id = app_grupo()));
CREATE POLICY reposicion_pedido ON reposicion FOR INSERT WITH CHECK (
    app_rol() = 'sistema' AND origen = 'pedido_matu' AND EXISTS (
        SELECT 1 FROM perfil_consumo p WHERE p.id = reposicion.perfil_id AND p.grupo_id = app_grupo()));

-- (c) Conservación
CREATE POLICY alerta_conservacion ON alerta_quiebre FOR SELECT TO matu_owner USING (app_rol() = 'operacion');
CREATE POLICY alerta_conservacion_borrar ON alerta_quiebre FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion');
CREATE POLICY notificacion_conservacion_borrar ON notificacion FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion');

CREATE FUNCTION quiebre_conservar(limite_alertas timestamptz, limite_eventos timestamptz, ahora timestamptz)
    RETURNS TABLE (alertas integer, eventos integer, notificaciones integer)
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'quiebre_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite_alertas IS NULL OR limite_alertas > ahora - interval '90 days' THEN
        RAISE EXCEPTION 'las alertas y notificaciones se conservan 90 días' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite_eventos IS NULL OR limite_eventos > ahora - interval '30 days' THEN
        RAISE EXCEPTION 'los eventos publicados se conservan 30 días' USING ERRCODE = 'invalid_parameter_value';
    END IF;

    DELETE FROM public.alerta_quiebre
     WHERE estado IN ('resuelta', 'descartada') AND cerrada_en <= limite_alertas;
    GET DIAGNOSTICS alertas = ROW_COUNT;
    DELETE FROM public.evento_outbox WHERE publicado_en IS NOT NULL AND publicado_en <= limite_eventos;
    GET DIAGNOSTICS eventos = ROW_COUNT;
    DELETE FROM public.notificacion WHERE creada_en <= limite_alertas;
    GET DIAGNOSTICS notificaciones = ROW_COUNT;
    RETURN NEXT;
END
$$;
REVOKE ALL ON FUNCTION quiebre_conservar(timestamptz, timestamptz, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION quiebre_conservar(timestamptz, timestamptz, timestamptz) TO matu_app;
"""

DOWNGRADE = """
DROP FUNCTION quiebre_conservar(timestamptz, timestamptz, timestamptz);
DROP POLICY notificacion_conservacion_borrar ON notificacion;
DROP POLICY alerta_conservacion_borrar ON alerta_quiebre;
DROP POLICY alerta_conservacion ON alerta_quiebre;

DROP POLICY reposicion_pedido ON reposicion;
DROP POLICY reposicion_declarar ON reposicion;
DROP POLICY reposicion_leer ON reposicion;
CREATE POLICY reposicion_hereda ON reposicion FOR ALL USING (EXISTS (
    SELECT 1 FROM perfil_consumo p WHERE p.id = reposicion.perfil_id));

DROP TRIGGER alerta_transicion ON alerta_quiebre;
DROP FUNCTION alerta_transicion();
ALTER TABLE alerta_quiebre DROP CONSTRAINT alerta_quiebre_cierre;

DROP POLICY alerta_cerrar ON alerta_quiebre;
DROP POLICY alerta_notificar ON alerta_quiebre;
DROP POLICY alerta_cerrar_sin_aviso ON alerta_quiebre;
DROP POLICY alerta_materializar ON alerta_quiebre;
DROP POLICY alerta_leer ON alerta_quiebre;
CREATE POLICY alerta_hereda ON alerta_quiebre FOR ALL USING (EXISTS (
    SELECT 1 FROM perfil_consumo p WHERE p.id = alerta_quiebre.perfil_id));
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

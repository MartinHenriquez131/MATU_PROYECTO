"""MATU-41: publicador del outbox, avisos por correo y push, y conservación de los eventos fallidos (RF-39).

Cadena: 0012 (MATU-57) -> 0013 (MATU-50, ficha ampliada, PR #41) -> 0014. down_revision = "0013": se
escribió sobre la 0012 y, al integrar main con la 0013, solo cambió la cadena, sin cambiar el SQL. La 0013
no toca ninguno de los objetos de esta migración.

a) notificacion.error con lista cerrada (CHECK notificacion_error): sin_autorizacion, alerta_cerrada,
   miembro_inactivo, sin_destino, push_expirado, proveedor_rechazo y proveedor_no_disponible, o NULL.
   Nunca la respuesta del proveedor. No se agregan columnas de destino ni de texto.

b) dispositivo: el consumidor de avisos corre con app.rol = 'sistema' y app.grupo_id (como el trabajo
   diario) y necesita el push_token de los miembros del grupo.
   - dispositivo_sistema_leer (SELECT): solo los dispositivos de miembros ACTIVOS de app_grupo().
   - dispositivo_sistema_expirar (UPDATE): las mismas filas, y WITH CHECK push_token IS NULL: el
     sistema solo puede borrar el token (push 404 o 410).
   - Trigger dispositivo_sistema_solo_push: con app.rol = 'sistema', un UPDATE no cambia ninguna otra
     columna. usuario.email ya lo lee el sistema por usuario_comiembro (0001): no hay política nueva.

c) Publicador del outbox sin un rol que se salte RLS. matu_app no lee ni actualiza evento_outbox
   (03_permisos.sql) y matu_publisher no tiene credenciales en la infraestructura del semestre: el
   publicador usa cuatro funciones SECURITY DEFINER (dueño matu_owner, search_path fijo, EXECUTE solo
   para matu_app) que exigen app.rol = 'operacion', como quiebre_conservar (0011):
   - outbox_tomar(cantidad, ahora, grupo): hasta 100 eventos pendientes y disponibles (disponible_en
     <= ahora), con FOR UPDATE SKIP LOCKED, y los arrienda 5 minutos (disponible_en = ahora + 5 min):
     otro publicador no los toma mientras tanto, y si este se cae vuelven solos (al menos una vez).
     grupo opcional: solo ese grupo.
   - outbox_publicado(evento, ahora): publicado_en.
   - outbox_reintentar(evento, disponible_en, ahora): intentos + 1; al llegar a 8, fallido_en = ahora
     y no se reintenta solo (arquitectura 8.6). El backoff lo calcula app/shared/outbox.py.
   - outbox_posponer(evento, hasta, ahora): disponible_en = hasta sin sumar un intento (los avisos no
     salen antes de las 09:00 de Chile). hasta no pasa de ahora + 1 día.
   Ninguna devuelve ni recibe otra cosa que identificadores, el tipo y el payload (solo UUID).

d) Conservación (decisión de Jorge del 04-11, amplía la 77): quiebre_conservar borra también los eventos
   fallidos con fallido_en <= limite_eventos (30 días), y las filas de evento_consumido de todo evento
   que borra. Misma firma y mismos tres contadores: "eventos" suma publicados y fallidos.

backend/db/*.sql no se tocan. downgrade() deja el esquema como en 0013.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


# El cuerpo de quiebre_conservar de 0011, para el downgrade
CONSERVAR_0011 = """
CREATE OR REPLACE FUNCTION quiebre_conservar(limite_alertas timestamptz, limite_eventos timestamptz, ahora timestamptz)
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
"""

CONSERVAR_0014 = """
CREATE OR REPLACE FUNCTION quiebre_conservar(limite_alertas timestamptz, limite_eventos timestamptz, ahora timestamptz)
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
        RAISE EXCEPTION 'los eventos publicados y los fallidos se conservan 30 días'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    DELETE FROM public.alerta_quiebre
     WHERE estado IN ('resuelta', 'descartada') AND cerrada_en <= limite_alertas;
    GET DIAGNOSTICS alertas = ROW_COUNT;
    -- MATU-41: los publicados a los 30 días de publicado_en y los fallidos a los 30 de fallido_en, y con
    -- cada evento sus filas de evento_consumido
    WITH borrados AS (
        DELETE FROM public.evento_outbox
         WHERE (publicado_en IS NOT NULL AND publicado_en <= limite_eventos)
            OR (fallido_en IS NOT NULL AND fallido_en <= limite_eventos)
        RETURNING id
    ), consumidos AS (
        DELETE FROM public.evento_consumido c USING borrados b WHERE c.evento_id = b.id RETURNING 1
    )
    SELECT count(*) INTO eventos FROM borrados;
    DELETE FROM public.notificacion WHERE creada_en <= limite_alertas;
    GET DIAGNOSTICS notificaciones = ROW_COUNT;
    RETURN NEXT;
END
$$;
"""

UPGRADE = (
    """
-- (a) notificacion.error: lista cerrada
ALTER TABLE notificacion ADD CONSTRAINT notificacion_error CHECK (error IS NULL OR error IN (
    'sin_autorizacion', 'alerta_cerrada', 'miembro_inactivo', 'sin_destino', 'push_expirado',
    'proveedor_rechazo', 'proveedor_no_disponible'));

-- (b) dispositivo: el sistema ve y expira los tokens de los miembros activos de su grupo
CREATE POLICY dispositivo_sistema_leer ON dispositivo FOR SELECT USING (
    app_rol() = 'sistema' AND EXISTS (SELECT 1 FROM membresia m
        WHERE m.usuario_id = dispositivo.usuario_id AND m.grupo_id = app_grupo() AND m.estado = 'activa'));
CREATE POLICY dispositivo_sistema_expirar ON dispositivo FOR UPDATE
    USING (app_rol() = 'sistema' AND EXISTS (SELECT 1 FROM membresia m
        WHERE m.usuario_id = dispositivo.usuario_id AND m.grupo_id = app_grupo() AND m.estado = 'activa'))
    WITH CHECK (app_rol() = 'sistema' AND push_token IS NULL AND EXISTS (SELECT 1 FROM membresia m
        WHERE m.usuario_id = dispositivo.usuario_id AND m.grupo_id = app_grupo() AND m.estado = 'activa'));

CREATE FUNCTION dispositivo_sistema_solo_push() RETURNS trigger LANGUAGE plpgsql AS
$$
BEGIN
    IF app_rol() = 'sistema' AND (
        (to_jsonb(NEW) - 'push_token') IS DISTINCT FROM (to_jsonb(OLD) - 'push_token')
        OR NEW.push_token IS NOT NULL) THEN
        RAISE EXCEPTION 'el sistema solo borra el push_token de un dispositivo' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER dispositivo_sistema_solo_push BEFORE UPDATE ON dispositivo
    FOR EACH ROW EXECUTE FUNCTION dispositivo_sistema_solo_push();

-- (c) El publicador del outbox, sin un rol que se salte RLS
CREATE FUNCTION outbox_tomar(p_cantidad integer, p_ahora timestamptz, p_grupo uuid DEFAULT NULL)
    RETURNS TABLE (id bigint, grupo_id uuid, tipo text, payload jsonb, intentos smallint)
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'outbox_tomar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_ahora IS NULL OR p_ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_cantidad IS NULL OR p_cantidad < 1 OR p_cantidad > 100 THEN
        RAISE EXCEPTION 'se toman de 1 a 100 eventos' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    RETURN QUERY
    WITH tomados AS (
        SELECT e.id FROM public.evento_outbox e
         WHERE e.publicado_en IS NULL AND e.fallido_en IS NULL AND e.disponible_en <= p_ahora
           AND (p_grupo IS NULL OR e.grupo_id = p_grupo)
         ORDER BY e.id
         LIMIT p_cantidad
         FOR UPDATE SKIP LOCKED
    )
    UPDATE public.evento_outbox e SET disponible_en = p_ahora + interval '5 minutes'
      FROM tomados t WHERE e.id = t.id
    RETURNING e.id, e.grupo_id, e.tipo, e.payload, e.intentos;
END
$$;

CREATE FUNCTION outbox_publicado(p_evento bigint, p_ahora timestamptz) RETURNS boolean
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'outbox_publicado exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    UPDATE public.evento_outbox SET publicado_en = p_ahora
     WHERE id = p_evento AND publicado_en IS NULL AND fallido_en IS NULL;
    RETURN FOUND;
END
$$;

CREATE FUNCTION outbox_reintentar(p_evento bigint, p_disponible_en timestamptz, p_ahora timestamptz)
    RETURNS boolean
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'outbox_reintentar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_disponible_en IS NULL OR p_ahora IS NULL OR p_disponible_en < p_ahora THEN
        RAISE EXCEPTION 'el reintento va después de ahora' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    -- Tope de 8 intentos (arquitectura 8.6): el octavo fallo deja el evento fallido, sin reintento solo
    UPDATE public.evento_outbox
       SET intentos = intentos + 1,
           fallido_en = CASE WHEN intentos + 1 >= 8 THEN p_ahora END,
           disponible_en = CASE WHEN intentos + 1 >= 8 THEN disponible_en ELSE p_disponible_en END
     WHERE id = p_evento AND publicado_en IS NULL AND fallido_en IS NULL;
    -- true si quedó fallido
    RETURN EXISTS (SELECT 1 FROM public.evento_outbox WHERE id = p_evento AND fallido_en IS NOT NULL);
END
$$;

CREATE FUNCTION outbox_posponer(p_evento bigint, p_hasta timestamptz, p_ahora timestamptz) RETURNS boolean
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'outbox_posponer exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_hasta IS NULL OR p_ahora IS NULL OR p_hasta < p_ahora OR p_hasta > p_ahora + interval '1 day' THEN
        RAISE EXCEPTION 'se pospone hasta un día' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    UPDATE public.evento_outbox SET disponible_en = p_hasta
     WHERE id = p_evento AND publicado_en IS NULL AND fallido_en IS NULL;
    RETURN FOUND;
END
$$;

REVOKE ALL ON FUNCTION outbox_tomar(integer, timestamptz, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION outbox_publicado(bigint, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION outbox_reintentar(bigint, timestamptz, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION outbox_posponer(bigint, timestamptz, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION outbox_tomar(integer, timestamptz, uuid) TO matu_app;
GRANT EXECUTE ON FUNCTION outbox_publicado(bigint, timestamptz) TO matu_app;
GRANT EXECUTE ON FUNCTION outbox_reintentar(bigint, timestamptz, timestamptz) TO matu_app;
GRANT EXECUTE ON FUNCTION outbox_posponer(bigint, timestamptz, timestamptz) TO matu_app;

-- (d) Conservación de los fallidos y de evento_consumido
"""
    + CONSERVAR_0014
)

DOWNGRADE = (
    CONSERVAR_0011
    + """
DROP FUNCTION outbox_posponer(bigint, timestamptz, timestamptz);
DROP FUNCTION outbox_reintentar(bigint, timestamptz, timestamptz);
DROP FUNCTION outbox_publicado(bigint, timestamptz);
DROP FUNCTION outbox_tomar(integer, timestamptz, uuid);

DROP TRIGGER dispositivo_sistema_solo_push ON dispositivo;
DROP FUNCTION dispositivo_sistema_solo_push();
DROP POLICY dispositivo_sistema_expirar ON dispositivo;
DROP POLICY dispositivo_sistema_leer ON dispositivo;

ALTER TABLE notificacion DROP CONSTRAINT notificacion_error;
"""
)


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

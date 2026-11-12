"""MATU-42 y MATU-53: invitar a un familiar, ver quiénes forman el grupo, cambiar roles, sacar y salir (RF-38, RF-42).

Cadena: 0025 (MATU-55) -> 0026. «Plan de la 0026» y decisiones 290 a 317 y 318 en adelante de docs/api/README.md,
sección «MATU-42 y MATU-53». Todo el SQL de políticas, permisos, triggers y CHECK va aquí; backend/db/*.sql no se toca.

Upgrade, con las letras del plan:

a) app_es_admin(): una membresía activa con rol admin de app_usuario() en app_grupo().
b) membresia:
   - membresia_familia (ALL) se divide: membresia_familia_leer (SELECT, solo las activas del grupo, D-42-10 a) y
     membresia_admin_editar (UPDATE de una fila activa del grupo, solo admin). membresia_operacion pasa a SELECT.
     membresia_propia y membresia_fundador no cambian. Sin política de DELETE.
   - Sacar y salir dejan la fila 'retirada', que ya no pasa membresia_familia_leer. PostgreSQL exige que la fila
     nueva de un UPDATE con WHERE pase también las políticas SELECT, así que un admin no podría retirar a otra
     persona con un UPDATE de matu_app (decisión 327). Lo hace membresia_retirar(id, ahora), SECURITY DEFINER, que
     exige ser la propia persona o admin activo del grupo, y lee y escribe con las políticas TO matu_owner
     membresia_retiro_leer y membresia_retiro_editar, acotadas al marcador app.funcion = 'membresia_retirar' que
     fija la propia función con set_config al entrar y limpia al salir. matu_app no actualiza estado ni retirado_en.
   - version integer NOT NULL DEFAULT 1 CHECK (version > 0), para el If-Match de PATCH (decisión 303).
   - REVOKE UPDATE, DELETE y GRANT UPDATE (rol, puede_ver_plan, version) a matu_app.
   - membresia_uq pasa a índice único parcial (grupo_id, usuario_id) WHERE estado <> 'retirada' (D-42-11 a).
c) Trigger membresia_nunca_sin_admin (BEFORE UPDATE, C11): si una fila admin activa deja de serlo y no queda otro
   admin activo en el grupo, check_violation con la restricción membresia_ultimo_admin. Serializa con
   pg_advisory_xact_lock sobre el grupo (la alternativa del plan, decisión 328): no exige permisos sobre
   grupo_familiar a quien actúa, y en READ COMMITTED la cuenta posterior al bloqueo ve lo que la otra confirmó.
d) invitacion: falla si tiene filas. Salen destino_email, destino_telefono e invitacion_destino. Entran
   nombre_pila_invita, codigo_hash, codigo_intentos_fallidos, bloqueada_en y sus CHECK. Trigger invitacion_vida_fija.
   invitacion_familia (ALL) se divide en invitacion_admin_leer, _crear y _anular, solo admin. REVOKE UPDATE, DELETE
   y GRANT UPDATE (revocada_en) a matu_app.
e) invitacion_presentar, invitacion_verificar e invitacion_aceptar, SECURITY DEFINER, dueño matu_owner, EXECUTE solo
   para matu_app. Exigen que no haya app.grupo_id y un ahora a no más de 5 minutos del de la base, hacia adelante
   o hacia atrás (decisión 340); aceptar exige app.usuario_id.
   Leen y escriben con políticas TO matu_owner acotadas al marcador app.funcion = 'invitacion', que cada función fija
   con set_config al entrar y limpia al salir (como app.conservacion de la 0024), sobre invitacion, membresia,
   grupo_familiar, persona_cuidada y auditoria. Reciben además p_request_id para la auditoría (decisión 329).
f) grupo_familiar: grupo_familia (ALL) se divide en grupo_familia_leer y grupo_admin_editar. REVOKE UPDATE, DELETE y
   GRANT UPDATE (nombre, actualizado_en).
g) direccion: direccion_familia y direccion_operacion (ALL) se dividen por operación; escriben admin y cuidador
   (app_retira_autorizacion(), 0016), como ya exige la API.
h) usuario_comiembro exige m.estado = 'activa' (D-42-10 a).
i) auditoria_detalle_acotado acepta además rol, de la lista cerrada de los cuatro roles (D-42-8 b).
j) invitacion_conservar(limite, ahora), SECURITY DEFINER, solo para matu_scheduler con app.rol = 'operacion': borra
   las invitaciones cerradas hace 30 días o más y su indice_token (D-42-6).

downgrade() deja el esquema como la 0025. Falla con un mensaje claro si una cuenta tiene dos membresías en el mismo
grupo (volvería membresia_uq). invitacion_destino vuelve validada si la tabla está vacía, NOT VALID si no; el CHECK de
la auditoría de la 0013, NOT VALID si ya hay filas con rol.

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


ROLES = "('admin', 'cuidador', 'pagador', 'observador')"
MARCA_INVITACION = "current_setting('app.funcion', true) = 'invitacion'"
MARCA_RETIRO = "current_setting('app.funcion', true) = 'membresia_retirar'"
ESCRIBE_DIRECCION = "grupo_id = app_grupo() AND (SELECT app_retira_autorizacion())"
ES_ADMIN = "(SELECT app_es_admin())"
# El marcador de las políticas TO matu_owner: la función lo fija al entrar y lo limpia al salir (decisión 327). Un SET
# de la función no sirve: matu_owner no puede fijar en una función un parámetro propio que no está definido
MARCAR_INVITACION = "PERFORM set_config('app.funcion', 'invitacion', true);"
DESMARCAR = "PERFORM set_config('app.funcion', '', true);"

# El CHECK de la 0013, tal como lo deja pg_get_constraintdef, para el downgrade
DETALLE_0013 = (
    "(detalle IS NULL) OR ((jsonb_typeof(detalle) = 'object'::text) AND ((((detalle - 'sesiones_revocadas'::text)"
    " - 'seccion'::text) - 'secciones'::text) = '{}'::jsonb) AND ((NOT (detalle ? 'sesiones_revocadas'::text)) OR"
    " ((jsonb_typeof((detalle -> 'sesiones_revocadas'::text)) = 'number'::text) AND ((detalle ->>"
    " 'sesiones_revocadas'::text) ~ '^[0-9]{1,6}$'::text))) AND ((NOT (detalle ? 'seccion'::text)) OR"
    " ((jsonb_typeof((detalle -> 'seccion'::text)) = 'string'::text) AND ((detalle ->> 'seccion'::text) = ANY"
    " (ARRAY['quien_es'::text, 'preferencias'::text, 'alimentacion'::text, 'movilidad'::text, 'comunicacion'::text,"
    " 'remedios'::text])))) AND ((NOT (detalle ? 'secciones'::text)) OR ((jsonb_typeof((detalle ->"
    " 'secciones'::text)) = 'array'::text) AND (jsonb_array_length((detalle -> 'secciones'::text)) <= 6) AND"
    " ((detalle -> 'secciones'::text) <@ '[\"quien_es\", \"preferencias\", \"alimentacion\", \"movilidad\","
    " \"comunicacion\", \"remedios\"]'::jsonb))))"
)
DETALLE_0026 = (
    "detalle IS NULL OR ("
    " jsonb_typeof(detalle) = 'object'"
    " AND (detalle - 'sesiones_revocadas' - 'seccion' - 'secciones' - 'rol') = '{}'::jsonb"
    " AND (NOT detalle ? 'sesiones_revocadas' OR (jsonb_typeof(detalle -> 'sesiones_revocadas') = 'number'"
    "      AND (detalle ->> 'sesiones_revocadas') ~ '^[0-9]{1,6}$'))"
    " AND (NOT detalle ? 'seccion' OR (jsonb_typeof(detalle -> 'seccion') = 'string'"
    "      AND (detalle ->> 'seccion') IN ('quien_es', 'preferencias', 'alimentacion', 'movilidad', 'comunicacion',"
    "      'remedios')))"
    " AND (NOT detalle ? 'secciones' OR (jsonb_typeof(detalle -> 'secciones') = 'array'"
    "      AND jsonb_array_length(detalle -> 'secciones') <= 6"
    "      AND (detalle -> 'secciones') <@ '[\"quien_es\", \"preferencias\", \"alimentacion\", \"movilidad\","
    " \"comunicacion\", \"remedios\"]'::jsonb))"
    f" AND (NOT detalle ? 'rol' OR (jsonb_typeof(detalle -> 'rol') = 'string' AND (detalle ->> 'rol') IN {ROLES})))"
)

# El estado de la invitación de v, en el orden del contrato (decisión 299). v viene de _BUSCAR
_ESTADO = """
    IF NOT FOUND OR v.revocada_en IS NOT NULL THEN
        resultado := 'no_disponible';
    ELSIF v.aceptada_en IS NOT NULL THEN
        resultado := 'usada';
    ELSIF v.expira_en <= p_ahora THEN
        resultado := 'vencida';
    ELSIF v.bloqueada_en IS NOT NULL THEN
        resultado := 'bloqueada';
        nombre_pila_invita := v.nombre_pila_invita;
    END IF;
"""

_EXIGIR = """
    IF public.app_grupo() IS NOT NULL THEN
        RAISE EXCEPTION '{nombre} no admite app.grupo_id' USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- Decisión 340: el instante del Reloj de la API, a lo más 5 minutos del de la base, hacia adelante o hacia atrás.
    -- Un ahora del pasado aceptaría una invitación vencida o fecharía retirado_en hacia atrás
    IF p_ahora IS NULL OR p_ahora > now() + interval '5 minutes' OR p_ahora < now() - interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora tiene que ser el instante actual' USING ERRCODE = 'invalid_parameter_value';
    END IF;
"""


def _buscar(bloquear: bool) -> str:
    return (
        "SELECT i.* INTO v FROM public.indice_token t JOIN public.invitacion i ON i.id = t.referencia_id"
        " WHERE t.token_hash = p_token_hash AND t.tipo = 'invitacion'" + (" FOR UPDATE OF i;" if bloquear else ";")
    )


# El código: un intento más, el 5.º bloquea; el correcto vuelve el contador a 0 (decisión 298). Escribe la auditoría
# con el actor de cada paso (decisión 312). Deja resultado en 'codigo_incorrecto' o 'bloqueada', o sigue
def _codigo(actor_tipo: str, actor_ref: str) -> str:
    return f"""
    IF v.codigo_hash <> p_codigo_hash THEN
        UPDATE public.invitacion SET codigo_intentos_fallidos = codigo_intentos_fallidos + 1,
               bloqueada_en = CASE WHEN codigo_intentos_fallidos + 1 >= 5 THEN p_ahora END
         WHERE id = v.id;
        IF v.codigo_intentos_fallidos + 1 >= 5 THEN
            resultado := 'bloqueada';
            nombre_pila_invita := v.nombre_pila_invita;
        ELSE
            resultado := 'codigo_incorrecto';
            intentos_restantes := 5 - (v.codigo_intentos_fallidos + 1);
        END IF;
        INSERT INTO public.auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id, request_id,
                                      ocurrido_en, detalle)
        VALUES (v.grupo_id, '{actor_tipo}', {actor_ref},
                CASE WHEN resultado = 'bloqueada' THEN 'invitacion.bloqueo' ELSE 'invitacion.codigo_incorrecto' END,
                'invitacion', v.id, p_request_id, p_ahora, jsonb_build_object('rol', v.rol));
        EXIT paso;
    END IF;
    IF v.codigo_intentos_fallidos > 0 THEN
        UPDATE public.invitacion SET codigo_intentos_fallidos = 0 WHERE id = v.id;
    END IF;
"""


UPGRADE = f"""
SELECT set_config('app.rol', 'operacion', true);

-- (a)
CREATE FUNCTION app_es_admin() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT EXISTS (SELECT 1 FROM membresia m
                  WHERE m.grupo_id = app_grupo() AND m.usuario_id = app_usuario()
                    AND m.estado = 'activa' AND m.rol = 'admin') $$;

-- (b) membresia
DROP POLICY membresia_familia ON membresia;
DROP POLICY membresia_operacion ON membresia;
CREATE POLICY membresia_familia_leer ON membresia FOR SELECT USING (grupo_id = app_grupo() AND estado = 'activa');
CREATE POLICY membresia_admin_editar ON membresia FOR UPDATE
    USING (grupo_id = app_grupo() AND estado = 'activa' AND {ES_ADMIN})
    WITH CHECK (grupo_id = app_grupo() AND estado = 'activa');
CREATE POLICY membresia_operacion ON membresia FOR SELECT USING (app_rol() = 'operacion');
-- Decisión 327: sacar y salir, solo dentro de membresia_retirar
CREATE POLICY membresia_retiro_leer ON membresia FOR SELECT TO matu_owner
    USING ({MARCA_RETIRO} AND grupo_id = app_grupo());
CREATE POLICY membresia_retiro_editar ON membresia FOR UPDATE TO matu_owner
    USING ({MARCA_RETIRO} AND grupo_id = app_grupo() AND estado = 'activa')
    WITH CHECK ({MARCA_RETIRO} AND grupo_id = app_grupo() AND estado = 'retirada' AND NOT puede_ver_plan);
-- (e) La aceptación inserta la membresía de la propia cuenta, activa y sin permiso
CREATE POLICY membresia_invitacion_crear ON membresia FOR INSERT TO matu_owner
    WITH CHECK ({MARCA_INVITACION} AND usuario_id = app_usuario() AND estado = 'activa' AND NOT puede_ver_plan);

ALTER TABLE membresia ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE membresia ADD CONSTRAINT membresia_version CHECK (version > 0);
COMMENT ON COLUMN membresia.version IS
    'MATU-42 (decisión 303): sube con cada cambio de rol, de permiso o de estado. etag = "v<version>"';
ALTER TABLE membresia DROP CONSTRAINT membresia_uq;
CREATE UNIQUE INDEX membresia_uq ON membresia (grupo_id, usuario_id) WHERE estado <> 'retirada';

REVOKE UPDATE, DELETE ON membresia FROM matu_app;
GRANT UPDATE (rol, puede_ver_plan, version) ON membresia TO matu_app;

-- (c) El grupo nunca queda sin admin
CREATE FUNCTION membresia_nunca_sin_admin() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF OLD.rol = 'admin' AND OLD.estado = 'activa' AND (NEW.rol <> 'admin' OR NEW.estado <> 'activa') THEN
        PERFORM pg_advisory_xact_lock(hashtextextended('membresia_admin:' || OLD.grupo_id::text, 0));
        IF NOT EXISTS (SELECT 1 FROM membresia m WHERE m.grupo_id = OLD.grupo_id AND m.id <> OLD.id
                         AND m.rol = 'admin' AND m.estado = 'activa') THEN
            RAISE EXCEPTION 'el grupo no puede quedar sin nadie que lo administre'
                USING ERRCODE = 'check_violation', CONSTRAINT = 'membresia_ultimo_admin';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER membresia_nunca_sin_admin BEFORE UPDATE ON membresia
    FOR EACH ROW EXECUTE FUNCTION membresia_nunca_sin_admin();

CREATE FUNCTION membresia_retirar(p_membresia_id uuid, p_ahora timestamptz) RETURNS text
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_rol text;
    v_usuario uuid;
BEGIN
    IF public.app_grupo() IS NULL OR public.app_usuario() IS NULL THEN
        RAISE EXCEPTION 'membresia_retirar exige app.grupo_id y app.usuario_id'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- Decisión 340: el instante del Reloj de la API, a lo más 5 minutos del de la base, hacia adelante o hacia atrás.
    -- Un ahora del pasado aceptaría una invitación vencida o fecharía retirado_en hacia atrás
    IF p_ahora IS NULL OR p_ahora > now() + interval '5 minutes' OR p_ahora < now() - interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora tiene que ser el instante actual' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    PERFORM set_config('app.funcion', 'membresia_retirar', true);
    SELECT m.rol, m.usuario_id INTO v_rol, v_usuario FROM public.membresia m
     WHERE m.id = p_membresia_id AND m.grupo_id = public.app_grupo() AND m.estado = 'activa' FOR UPDATE;
    IF NOT FOUND OR (v_usuario <> public.app_usuario() AND NOT EXISTS (
        SELECT 1 FROM public.membresia m WHERE m.grupo_id = public.app_grupo() AND m.usuario_id = public.app_usuario()
           AND m.estado = 'activa' AND m.rol = 'admin')) THEN
        v_rol := NULL;
    ELSE
        UPDATE public.membresia SET estado = 'retirada', retirado_en = p_ahora, puede_ver_plan = false,
               version = version + 1
         WHERE id = p_membresia_id;
    END IF;
    PERFORM set_config('app.funcion', '', true);
    RETURN v_rol;
END $$;
REVOKE ALL ON FUNCTION membresia_retirar(uuid, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION membresia_retirar(uuid, timestamptz) TO matu_app;

-- (d) invitacion
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM invitacion) THEN
        RAISE EXCEPTION 'la 0026 exige la tabla invitacion vacía: ninguna ruta las creó antes de MATU-42';
    END IF;
END $$;
ALTER TABLE invitacion DROP CONSTRAINT invitacion_destino;
ALTER TABLE invitacion DROP COLUMN destino_email;
ALTER TABLE invitacion DROP COLUMN destino_telefono;
ALTER TABLE invitacion ADD COLUMN nombre_pila_invita text NOT NULL;
ALTER TABLE invitacion ADD COLUMN codigo_hash bytea NOT NULL;
ALTER TABLE invitacion ADD COLUMN codigo_intentos_fallidos smallint NOT NULL DEFAULT 0;
ALTER TABLE invitacion ADD COLUMN bloqueada_en timestamptz;
ALTER TABLE invitacion ADD CONSTRAINT invitacion_nombre_pila CHECK (char_length(nombre_pila_invita) BETWEEN 1 AND 100);
ALTER TABLE invitacion ADD CONSTRAINT invitacion_codigo_hash CHECK (octet_length(codigo_hash) = 32);
ALTER TABLE invitacion ADD CONSTRAINT invitacion_intentos CHECK (codigo_intentos_fallidos BETWEEN 0 AND 5);
ALTER TABLE invitacion ADD CONSTRAINT invitacion_bloqueo
    CHECK ((bloqueada_en IS NULL) = (codigo_intentos_fallidos < 5));
ALTER TABLE invitacion ADD CONSTRAINT invitacion_token_hash CHECK (octet_length(token_hash) = 32);
ALTER TABLE invitacion ADD CONSTRAINT invitacion_aceptada CHECK ((aceptada_en IS NULL) = (aceptada_por IS NULL));
CREATE INDEX invitacion_grupo_ix ON invitacion (grupo_id, creada_en DESC);
COMMENT ON TABLE invitacion IS
    'MATU-42: sin correo ni teléfono (D-42-1 a). Solo la huella del token y el HMAC del código con PEPPER_PIN';

CREATE FUNCTION invitacion_vida_fija() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF NEW.grupo_id IS DISTINCT FROM OLD.grupo_id OR NEW.rol IS DISTINCT FROM OLD.rol
       OR NEW.token_hash IS DISTINCT FROM OLD.token_hash OR NEW.codigo_hash IS DISTINCT FROM OLD.codigo_hash
       OR NEW.invitado_por IS DISTINCT FROM OLD.invitado_por OR NEW.creada_en IS DISTINCT FROM OLD.creada_en
       OR NEW.nombre_pila_invita IS DISTINCT FROM OLD.nombre_pila_invita THEN
        RAISE EXCEPTION 'lo que define una invitación no cambia' USING ERRCODE = 'check_violation';
    END IF;
    IF (OLD.aceptada_en IS NOT NULL AND (NEW.aceptada_en IS DISTINCT FROM OLD.aceptada_en
                                          OR NEW.aceptada_por IS DISTINCT FROM OLD.aceptada_por))
       OR (OLD.revocada_en IS NOT NULL AND NEW.revocada_en IS DISTINCT FROM OLD.revocada_en)
       OR (OLD.bloqueada_en IS NOT NULL AND NEW.bloqueada_en IS DISTINCT FROM OLD.bloqueada_en) THEN
        RAISE EXCEPTION 'una invitación cerrada no se reabre' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.expira_en > OLD.expira_en THEN
        RAISE EXCEPTION 'el vencimiento de una invitación no se alarga' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER invitacion_vida_fija BEFORE UPDATE ON invitacion
    FOR EACH ROW EXECUTE FUNCTION invitacion_vida_fija();

DROP POLICY invitacion_familia ON invitacion;
CREATE POLICY invitacion_admin_leer ON invitacion FOR SELECT USING (grupo_id = app_grupo() AND {ES_ADMIN});
CREATE POLICY invitacion_admin_crear ON invitacion FOR INSERT
    WITH CHECK (grupo_id = app_grupo() AND invitado_por = app_usuario() AND {ES_ADMIN});
CREATE POLICY invitacion_admin_anular ON invitacion FOR UPDATE
    USING (grupo_id = app_grupo() AND {ES_ADMIN}) WITH CHECK (grupo_id = app_grupo() AND {ES_ADMIN});
CREATE POLICY invitacion_canje_leer ON invitacion FOR SELECT TO matu_owner USING ({MARCA_INVITACION});
CREATE POLICY invitacion_canje_editar ON invitacion FOR UPDATE TO matu_owner
    USING ({MARCA_INVITACION}) WITH CHECK ({MARCA_INVITACION});
CREATE POLICY invitacion_conservacion_borrar ON invitacion FOR DELETE TO matu_owner USING (app_rol() = 'operacion');
REVOKE UPDATE, DELETE ON invitacion FROM matu_app;
GRANT UPDATE (revocada_en) ON invitacion TO matu_app;

-- (e) Lo que leen y escriben las funciones de la persona invitada
CREATE POLICY grupo_invitacion_leer ON grupo_familiar FOR SELECT TO matu_owner USING ({MARCA_INVITACION});
CREATE POLICY persona_invitacion_leer ON persona_cuidada FOR SELECT TO matu_owner USING ({MARCA_INVITACION});
CREATE POLICY auditoria_invitacion ON auditoria FOR INSERT TO matu_owner WITH CHECK (
    {MARCA_INVITACION} AND entidad = 'invitacion'
    AND accion IN ('invitacion.codigo_incorrecto', 'invitacion.bloqueo', 'invitacion.aceptar'));

CREATE FUNCTION invitacion_presentar(p_token_hash bytea, p_ahora timestamptz)
    RETURNS TABLE (resultado text, nombre_pila_invita text, rol text, expira_en timestamptz)
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v public.invitacion%ROWTYPE;
BEGIN
    {_EXIGIR.format(nombre="invitacion_presentar")}
    {MARCAR_INVITACION}
    {_buscar(False)}
    {_ESTADO}
    IF resultado IS NULL THEN
        resultado := 'ok';
        nombre_pila_invita := v.nombre_pila_invita;
        rol := v.rol;
        expira_en := v.expira_en;
    END IF;
    {DESMARCAR}
    RETURN NEXT;
END $$;

CREATE FUNCTION invitacion_verificar(p_token_hash bytea, p_codigo_hash bytea, p_ahora timestamptz,
                                     p_request_id text)
    RETURNS TABLE (resultado text, nombre_pila_invita text, grupo text, personas text[], rol text,
                   expira_en timestamptz, intentos_restantes integer)
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v public.invitacion%ROWTYPE;
BEGIN
    {_EXIGIR.format(nombre="invitacion_verificar")}
    {MARCAR_INVITACION}
    <<paso>>
    BEGIN
    {_buscar(True)}
    {_ESTADO}
    IF resultado IS NOT NULL THEN
        EXIT paso;
    END IF;
    {_codigo("sistema", "NULL")}
    resultado := 'ok';
    nombre_pila_invita := v.nombre_pila_invita;
    rol := v.rol;
    expira_en := v.expira_en;
    SELECT g.nombre INTO grupo FROM public.grupo_familiar g WHERE g.id = v.grupo_id;
    SELECT coalesce(array_agg(p.nombre_pila ORDER BY p.creado_en, p.id), ARRAY[]::text[]) INTO personas
      FROM public.persona_cuidada p WHERE p.grupo_id = v.grupo_id AND p.activa AND p.eliminado_en IS NULL;
    END;
    {DESMARCAR}
    RETURN NEXT;
END $$;

CREATE FUNCTION invitacion_aceptar(p_token_hash bytea, p_codigo_hash bytea, p_ahora timestamptz, p_request_id text)
    RETURNS TABLE (resultado text, nombre_pila_invita text, grupo_id uuid, membresia_id uuid, grupo text, rol text,
                   intentos_restantes integer)
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v public.invitacion%ROWTYPE;
BEGIN
    {_EXIGIR.format(nombre="invitacion_aceptar")}
    IF public.app_usuario() IS NULL THEN
        RAISE EXCEPTION 'invitacion_aceptar exige app.usuario_id' USING ERRCODE = 'insufficient_privilege';
    END IF;
    {MARCAR_INVITACION}
    <<paso>>
    BEGIN
    {_buscar(True)}
    {_ESTADO}
    -- Ya usada por esta misma cuenta, que sigue en el grupo: un doble toque (C27)
    IF resultado = 'usada' AND v.aceptada_por = public.app_usuario() AND EXISTS (
        SELECT 1 FROM public.membresia m WHERE m.grupo_id = v.grupo_id AND m.usuario_id = public.app_usuario()
           AND m.estado = 'activa') THEN
        resultado := 'ya_eres_parte';
        grupo_id := v.grupo_id;
    END IF;
    IF resultado IS NOT NULL THEN
        EXIT paso;
    END IF;
    {_codigo("usuario", "public.app_usuario()")}
    -- Ya es miembro activo por otra vía: no consume la invitación (C27)
    IF EXISTS (SELECT 1 FROM public.membresia m WHERE m.grupo_id = v.grupo_id AND m.usuario_id = public.app_usuario()
                  AND m.estado = 'activa') THEN
        resultado := 'ya_eres_parte';
        grupo_id := v.grupo_id;
        EXIT paso;
    END IF;
    membresia_id := gen_random_uuid();
    INSERT INTO public.membresia (id, grupo_id, usuario_id, rol, puede_ver_plan, estado, invitado_por, unido_en)
    VALUES (membresia_id, v.grupo_id, public.app_usuario(), v.rol, false, 'activa', v.invitado_por, p_ahora);
    UPDATE public.invitacion SET aceptada_en = p_ahora, aceptada_por = public.app_usuario() WHERE id = v.id;
    UPDATE public.indice_token SET revocado_en = p_ahora
     WHERE token_hash = p_token_hash AND tipo = 'invitacion' AND revocado_en IS NULL;
    INSERT INTO public.auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id, request_id,
                                  ocurrido_en, detalle)
    VALUES (v.grupo_id, 'usuario', public.app_usuario(), 'invitacion.aceptar', 'invitacion', v.id, p_request_id,
            p_ahora, jsonb_build_object('rol', v.rol));
    resultado := 'ok';
    grupo_id := v.grupo_id;
    rol := v.rol;
    SELECT g.nombre INTO grupo FROM public.grupo_familiar g WHERE g.id = v.grupo_id;
    END;
    {DESMARCAR}
    RETURN NEXT;
END $$;

REVOKE ALL ON FUNCTION invitacion_presentar(bytea, timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION invitacion_verificar(bytea, bytea, timestamptz, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION invitacion_aceptar(bytea, bytea, timestamptz, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION invitacion_presentar(bytea, timestamptz) TO matu_app;
GRANT EXECUTE ON FUNCTION invitacion_verificar(bytea, bytea, timestamptz, text) TO matu_app;
GRANT EXECUTE ON FUNCTION invitacion_aceptar(bytea, bytea, timestamptz, text) TO matu_app;

-- (f) grupo_familiar
DROP POLICY grupo_familia ON grupo_familiar;
CREATE POLICY grupo_familia_leer ON grupo_familiar FOR SELECT TO matu_app USING (id = app_grupo());
CREATE POLICY grupo_admin_editar ON grupo_familiar FOR UPDATE TO matu_app
    USING (id = app_grupo() AND {ES_ADMIN}) WITH CHECK (id = app_grupo() AND {ES_ADMIN});
REVOKE UPDATE, DELETE ON grupo_familiar FROM matu_app;
GRANT UPDATE (nombre, actualizado_en) ON grupo_familiar TO matu_app;

-- (g) direccion
DROP POLICY direccion_familia ON direccion;
DROP POLICY direccion_operacion ON direccion;
CREATE POLICY direccion_familia_leer ON direccion FOR SELECT USING (grupo_id = app_grupo());
CREATE POLICY direccion_familia_crear ON direccion FOR INSERT WITH CHECK ({ESCRIBE_DIRECCION});
CREATE POLICY direccion_familia_editar ON direccion FOR UPDATE
    USING ({ESCRIBE_DIRECCION}) WITH CHECK ({ESCRIBE_DIRECCION});
CREATE POLICY direccion_familia_borrar ON direccion FOR DELETE USING ({ESCRIBE_DIRECCION});
CREATE POLICY direccion_operacion_leer ON direccion FOR SELECT USING (app_rol() = 'operacion');

-- (h) Los nombres, solo de los miembros activos
DROP POLICY usuario_comiembro ON usuario;
CREATE POLICY usuario_comiembro ON usuario FOR SELECT USING (EXISTS (
    SELECT 1 FROM membresia m WHERE m.usuario_id = usuario.id AND m.grupo_id = app_grupo() AND m.estado = 'activa'));

-- (i) El detalle de la auditoría acepta el rol (D-42-8 b)
ALTER TABLE auditoria DROP CONSTRAINT auditoria_detalle_acotado;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_detalle_acotado CHECK ({DETALLE_0026});

-- (j) Las invitaciones cerradas se borran a los 30 días (D-42-6)
CREATE FUNCTION invitacion_conservar(limite timestamptz, ahora timestamptz) RETURNS integer
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    borradas integer;
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'invitacion_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '30 days' THEN
        RAISE EXCEPTION 'las invitaciones cerradas se conservan 30 días' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    -- Cerrada desde la primera de sus fechas: aceptada, anulada, bloqueada o vencida. LEAST ignora los nulos
    DELETE FROM public.indice_token t USING public.invitacion i
     WHERE t.tipo = 'invitacion' AND t.referencia_id = i.id
       AND LEAST(i.aceptada_en, i.revocada_en, i.bloqueada_en, i.expira_en) <= limite;
    DELETE FROM public.invitacion i WHERE LEAST(i.aceptada_en, i.revocada_en, i.bloqueada_en, i.expira_en) <= limite;
    GET DIAGNOSTICS borradas = ROW_COUNT;
    RETURN borradas;
END $$;
REVOKE ALL ON FUNCTION invitacion_conservar(timestamptz, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION invitacion_conservar(timestamptz, timestamptz) TO matu_scheduler;

SELECT set_config('app.rol', '', true);
"""

DOWNGRADE = f"""
SELECT set_config('app.rol', 'operacion', true);

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM membresia GROUP BY grupo_id, usuario_id HAVING count(*) > 1) THEN
        RAISE EXCEPTION 'la 0026 no baja: una cuenta tiene dos membresías en el mismo grupo (volvió con una'
            ' invitación) y membresia_uq lo impediría. Borra la membresía retirada antes de bajar';
    END IF;
END $$;

-- (j) e (i)
DROP FUNCTION invitacion_conservar(timestamptz, timestamptz);
ALTER TABLE auditoria DROP CONSTRAINT auditoria_detalle_acotado;
-- Como la 0013: validar el CHECK ve todas las filas (RLS no lo acota). Con filas con rol, vuelve NOT VALID
DO $$ BEGIN
    BEGIN
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_detalle_acotado CHECK ({DETALLE_0013});
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'MATU-42: la auditoría tiene detalles con rol; el CHECK de la 0013 vuelve NOT VALID';
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_detalle_acotado CHECK ({DETALLE_0013}) NOT VALID;
    END;
END $$;

-- (h)
DROP POLICY usuario_comiembro ON usuario;
CREATE POLICY usuario_comiembro ON usuario FOR SELECT USING (EXISTS (
    SELECT 1 FROM membresia m WHERE m.usuario_id = usuario.id AND m.grupo_id = app_grupo()));

-- (g)
DROP POLICY direccion_familia_leer ON direccion;
DROP POLICY direccion_familia_crear ON direccion;
DROP POLICY direccion_familia_editar ON direccion;
DROP POLICY direccion_familia_borrar ON direccion;
DROP POLICY direccion_operacion_leer ON direccion;
CREATE POLICY direccion_familia ON direccion FOR ALL USING (grupo_id = app_grupo());
CREATE POLICY direccion_operacion ON direccion FOR ALL USING (app_rol() = 'operacion');

-- (f)
REVOKE UPDATE (nombre, actualizado_en) ON grupo_familiar FROM matu_app;
GRANT UPDATE, DELETE ON grupo_familiar TO matu_app;
DROP POLICY grupo_admin_editar ON grupo_familiar;
DROP POLICY grupo_familia_leer ON grupo_familiar;
CREATE POLICY grupo_familia ON grupo_familiar FOR ALL TO matu_app USING (id = app_grupo());

-- (e)
DROP FUNCTION invitacion_aceptar(bytea, bytea, timestamptz, text);
DROP FUNCTION invitacion_verificar(bytea, bytea, timestamptz, text);
DROP FUNCTION invitacion_presentar(bytea, timestamptz);
DROP POLICY auditoria_invitacion ON auditoria;
DROP POLICY persona_invitacion_leer ON persona_cuidada;
DROP POLICY grupo_invitacion_leer ON grupo_familiar;

-- (d)
REVOKE UPDATE (revocada_en) ON invitacion FROM matu_app;
GRANT UPDATE, DELETE ON invitacion TO matu_app;
DROP POLICY invitacion_conservacion_borrar ON invitacion;
DROP POLICY invitacion_canje_editar ON invitacion;
DROP POLICY invitacion_canje_leer ON invitacion;
DROP POLICY invitacion_admin_anular ON invitacion;
DROP POLICY invitacion_admin_crear ON invitacion;
DROP POLICY invitacion_admin_leer ON invitacion;
CREATE POLICY invitacion_familia ON invitacion FOR ALL USING (grupo_id = app_grupo());
DROP TRIGGER invitacion_vida_fija ON invitacion;
DROP FUNCTION invitacion_vida_fija();
COMMENT ON TABLE invitacion IS NULL;
DROP INDEX invitacion_grupo_ix;
ALTER TABLE invitacion DROP CONSTRAINT invitacion_aceptada;
ALTER TABLE invitacion DROP CONSTRAINT invitacion_token_hash;
ALTER TABLE invitacion DROP CONSTRAINT invitacion_bloqueo;
ALTER TABLE invitacion DROP CONSTRAINT invitacion_intentos;
ALTER TABLE invitacion DROP CONSTRAINT invitacion_codigo_hash;
ALTER TABLE invitacion DROP CONSTRAINT invitacion_nombre_pila;
ALTER TABLE invitacion DROP COLUMN bloqueada_en;
ALTER TABLE invitacion DROP COLUMN codigo_intentos_fallidos;
ALTER TABLE invitacion DROP COLUMN codigo_hash;
ALTER TABLE invitacion DROP COLUMN nombre_pila_invita;
ALTER TABLE invitacion ADD COLUMN destino_email text;
ALTER TABLE invitacion ADD COLUMN destino_telefono text;
DO $$ BEGIN
    BEGIN
        ALTER TABLE invitacion ADD CONSTRAINT invitacion_destino
            CHECK (destino_email IS NOT NULL OR destino_telefono IS NOT NULL);
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'MATU-42: hay invitaciones sin correo ni teléfono; invitacion_destino vuelve NOT VALID';
        ALTER TABLE invitacion ADD CONSTRAINT invitacion_destino
            CHECK (destino_email IS NOT NULL OR destino_telefono IS NOT NULL) NOT VALID;
    END;
END $$;

-- (c) y (b)
DROP FUNCTION membresia_retirar(uuid, timestamptz);
DROP TRIGGER membresia_nunca_sin_admin ON membresia;
DROP FUNCTION membresia_nunca_sin_admin();
REVOKE UPDATE (rol, puede_ver_plan, version) ON membresia FROM matu_app;
GRANT UPDATE, DELETE ON membresia TO matu_app;
DROP INDEX membresia_uq;
ALTER TABLE membresia ADD CONSTRAINT membresia_uq UNIQUE (grupo_id, usuario_id);
ALTER TABLE membresia DROP CONSTRAINT membresia_version;
ALTER TABLE membresia DROP COLUMN version;
DROP POLICY membresia_invitacion_crear ON membresia;
DROP POLICY membresia_retiro_editar ON membresia;
DROP POLICY membresia_retiro_leer ON membresia;
DROP POLICY membresia_operacion ON membresia;
DROP POLICY membresia_admin_editar ON membresia;
DROP POLICY membresia_familia_leer ON membresia;
CREATE POLICY membresia_familia ON membresia FOR ALL USING (grupo_id = app_grupo());
CREATE POLICY membresia_operacion ON membresia FOR ALL USING (app_rol() = 'operacion');

-- (a)
DROP FUNCTION app_es_admin();

SELECT set_config('app.rol', '', true);
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

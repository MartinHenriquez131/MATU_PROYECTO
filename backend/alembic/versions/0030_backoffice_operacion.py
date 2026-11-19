"""MATU-81: el backoffice mínimo de operación, con segundo factor.

Cadena: 0029 (MATU-63) -> 0030. down_revision = "0029". MATU-112 y MATU-92 no traen migración; si MATU-76 lleva una,
va después de esta.

Revisión previa del analista normativo del 17-11 (docs/legal/revision-previa-matu-81.md), decisiones D-81-1 a D-81-12
y condiciones C1 a C34. Decisiones 449 en adelante de docs/api/README.md. backend/db/*.sql no se tocan.

a) incidencia (C10 a C14, D-81-3): los tipos faltante, entrega_fallida, reclamo_familia, cobro_sin_respuesta,
   devolucion_pendiente y otro. descripcion y resolucion pasan a bytea, cifradas (h), cada una con su clave
   (clave_notas_id y resolucion_clave_id): la subida se detiene si ya hay incidencias, porque la nota en claro no se
   puede cifrar desde la base. El largo de 1 a 500 caracteres lo valida la aplicación sobre el texto; la base, el del
   cifrado. Una resuelta lleva su resolución; pedido_id ON DELETE CASCADE; version (el ETag del PATCH), que sube en
   cada cambio; el trigger incidencia_reglas (solo sobre pedidos pagados, creada_por y asignada_a son cuentas de
   operación activas, y lo que se cifra va con la clave vigente de la persona del pedido); las políticas leer, crear
   (creada_por = la cuenta del contexto) y editar, sin DELETE, y matu_app edita solo estado, asignada_a, resolucion,
   resolucion_clave_id y resuelta_en.
b) D-81-2: sale aceptacion_operacion_leer (operación no lee las aceptaciones de la política).
c) Las acciones nuevas en los CHECK de la auditoría: sin grupo, cuenta.mfa_alta, sesion.mfa_correcto,
   sesion.mfa_fallido y catalogo.oferta_cambiar (C4, C32); con persona, operacion.pedido_ver (D-81-5),
   incidencia.crear e incidencia.resolver (C14).
d) MFA (C26 a C33):
   - iam_mfa_secreto(usuario): SECURITY DEFINER, dueño matu_owner y search_path fijo, EXECUTE solo matu_app. Entrega
     lo cifrado solo de la cuenta del contexto, si es de operación y está activa, y nunca con app.rol = 'operacion'
     (como iam_credencial). matu_app sigue sin SELECT sobre usuario.mfa_secreto_cifrado.
   - sesion_refresh.mfa_en: la marca del segundo factor. Con ella, la sesión vence a más tardar 12 horas después del
     segundo factor (CHECK sesion_refresh_mfa), y la marca no cambia (trigger sesion_refresh_mfa). Una cuenta de
     operación no recibe un refresh sin la marca (el mismo trigger).
   - cuenta_operacion_separada: una cuenta de operación no es miembro de un grupo ni de un comercio, y al revés
     (triggers en usuario, membresia y usuario_comercio, como D-63-14).
   - operacion_buscar_cuenta y operacion_alta, solo para matu_scheduler con app.rol = 'operacion': la tarea de consola
     del alta (python -m app.tareas operacion-alta). El alta marca es_operacion, guarda el secreto cifrado, revoca las
     sesiones abiertas de la cuenta (motivo operacion) y audita cuenta.mfa_alta, sin grupo y sin el secreto.
e) D-81-6: sale persona_operacion (operación no lee la persona cuidada) y entrega_operacion queda solo de lectura
   (entrega_operacion_leer). Se mantiene direccion_operacion_leer. consentimiento_operacion pasa a
   consentimiento_conservacion, TO matu_owner (decisión 452): plan_destruir_claves (0016, 0028) y consumo_conservar
   (0009) corren como matu_owner con app.rol = 'operacion' y siguen leyéndolo; matu_app con operación, ya no.
f) C24: retracto.motivo_rechazo (sello_abierto o producto_no_recibido), solo en un retracto rechazado. Las filas
   rechazadas anteriores quedan sin motivo (el CHECK lo admite).
g) C1: operación cambia precio, stock y disponible solo en las ofertas de comercios ficticios (trigger
   oferta_operacion_ficticia).
h) Opción B de Jorge (17-11, decisión 471): clave_notas, la clave propia de las notas de operación, una vigente por
   persona cuidada, envuelta con la misma KEK y nunca clave_datos (§11.2 y §12.8). FORCE ROW LEVEL SECURITY; la leen
   operación (para cifrar y descifrar) y quien es miembro activo del grupo (la copia de sus datos es la única que la
   lee); el comercio, el repartidor y el relevo, nunca. Sin el marcador app.funcion: matu_app lo puede fijar, y una
   política que lo mira es solo TO matu_owner (O2). matu_app la crea y la lee, sin UPDATE ni DELETE. Nace vigente y
   después solo se destruye (trigger clave_notas_solo_destruir). Decisión de Jorge del 17-11: solo cuando se borran
   los datos de la persona (persona_cuidada.datos_borrados_en, MATU-72), la función clave_notas_destruir (SECURITY
   DEFINER, matu_owner) destruye también su clave de notas. Destruir la clave de la ficha (plan_destruir_claves a los
   90 días del retiro, o la familia al volver a autorizar) no la toca: la persona sigue en MATU y su pedido se guarda
   2 años.

downgrade() deja el esquema como en 0029 sin borrar nada. Falla si hay incidencias o claves de notas (lo cifrado no
vuelve a texto sin la KEK), o retractos con motivo de rechazo. La auditoría con las acciones nuevas deja los CHECK
de la 0029 NOT VALID, como las bajadas anteriores.

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


def _lista(acciones: Sequence[str]) -> str:
    return ", ".join(f"'{accion}'" for accion in acciones)


SIN_GRUPO_0029 = (
    "sesion.iniciar",
    "sesion.inicio_fallido",
    "sesion.reutilizacion_detectada",
    "sesion.cerrar",
    "dispositivo.sacar",
    "dispositivo.push_registrar",
    "dispositivo.push_borrar",
    "cuenta.recuperar_solicitar",
    "cuenta.recuperar_verificar_fallido",
    "cuenta.contrasena_cambiar",  # pragma: allowlist secret
    "cuenta.celular_solicitar",
    "cuenta.celular_verificar",
    "cuenta.celular_verificar_fallido",
    "avisos.preferencia",
    "cuenta.datos_descargar",
    "comercio.preparar",
    "comercio.marcar_linea",
    "comercio.listo",
    "comercio.codigo_correcto",
    "comercio.codigo_incorrecto",
    "comercio.codigo_bloqueo",
    "comercio.productos_cambiar",
)
# Las de la cuenta de operación y la del catálogo, sin grupo (C4 y C32). tests/test_migraciones.py verifica que
# coinciden con el código
SIN_GRUPO_0030 = (
    *SIN_GRUPO_0029,
    "cuenta.mfa_alta",
    "sesion.mfa_correcto",
    "sesion.mfa_fallido",
    "catalogo.oferta_cambiar",
)

ACCIONES_DE_PERSONA_0029 = (
    "plan.leer",
    "plan.editar",
    "plan.quitar_seccion",
    "consentimiento.otorgar",
    "consentimiento.revocar",
    "relevo.compartir",
    "relevo.revocar",
    "relevo.presentar",
    "relevo.canje",
    "relevo.pin_incorrecto",
    "relevo.bloqueo",
    "relevo.abrir",
    "consumo.crear",
    "consumo.editar",
    "consumo.desactivar",
    "consumo.activar",
    "consumo.eliminar",
    "alerta.materializar",
    "alerta.descartar",
    "alerta.resolver",
    "reposicion.declarar",
    "clave.destruir",
    "persona.borrar",
    "persona.datos_descargar",
    "direccion.cambiar",
    "pedido.crear",
    "pedido.confirmar",
    "pedido.cancelar",
    "pedido.regla_faltante",
    "pago.iniciar",
    "pago.aprobar",
    "pago.anular",
    "pago.devolver",
    "pedido.retracto_solicitar",
    "codigo_retiro.generar",
    "despacho.en_camino",
    "despacho.entregar",
    "despacho.no_entregado",
    "retracto.resolver",
)
ACCIONES_DE_PERSONA_0030 = (
    *ACCIONES_DE_PERSONA_0029,
    "operacion.pedido_ver",
    "incidencia.crear",
    "incidencia.resolver",
)

TIPOS_0001 = "'desviacion_monto', 'faltante', 'entrega_fallida', 'captura_rechazada', 'reclamo_familia', 'otro'"
TIPOS_0030 = "'faltante', 'entrega_fallida', 'reclamo_familia', 'cobro_sin_respuesta', 'devolucion_pendiente', 'otro'"
FUNCION = "current_setting('app.funcion', true)"

# Opción B de Jorge (17-11, decisión 471): la nota y la resolución van cifradas con AES-256-GCM y una clave propia de
# las notas de operación por persona cuidada (clave_notas), envuelta con la misma KEK. Nunca con clave_datos: operación
# no la alcanza (§11.2 y defecto 2 de la §12.8). Lo cifrado es nonce (12) || texto cifrado con su etiqueta (16): de 1 a
# 500 caracteres en UTF-8 son de 1 a 2000 bytes, y el largo del texto lo valida la aplicación
# (app/shared/notas_operacion.py)
CIFRADO_MIN = 12 + 16 + 1
CIFRADO_MAX = 12 + 16 + 4 * 500
# La DEK de 32 bytes envuelta con AES Key Wrap ocupa 40 bytes (como clave_datos)
LARGO_DEK_ENVUELTA = 40

CLAVE_NOTAS = f"""
-- (h) La clave de las notas de operación, una vigente por persona. Lleva grupo_id y nace con FORCE ROW LEVEL SECURITY
CREATE TABLE clave_notas (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    grupo_id            uuid NOT NULL,
    persona_cuidada_id  uuid NOT NULL,
    dek_cifrada_con_kek bytea,
    kek_version         integer NOT NULL CHECK (kek_version > 0),
    creada_en           timestamptz NOT NULL DEFAULT now(),
    destruida_en        timestamptz,
    -- La persona es del grupo de la fila (persona_cuidada_id_grupo_uq, 0028), sin pasar por RLS
    CONSTRAINT clave_notas_persona_fk FOREIGN KEY (persona_cuidada_id, grupo_id)
        REFERENCES persona_cuidada (id, grupo_id),
    -- Borrado criptográfico: sin DEK, la fecha; con la fecha, sin DEK
    CONSTRAINT clave_notas_destruccion CHECK ((dek_cifrada_con_kek IS NULL) = (destruida_en IS NOT NULL)),
    CONSTRAINT clave_notas_dek_largo
        CHECK (dek_cifrada_con_kek IS NULL OR octet_length(dek_cifrada_con_kek) = {LARGO_DEK_ENVUELTA})
);
CREATE UNIQUE INDEX clave_notas_vigente_uq ON clave_notas (persona_cuidada_id) WHERE destruida_en IS NULL;
ALTER TABLE clave_notas ENABLE ROW LEVEL SECURITY;
ALTER TABLE clave_notas FORCE ROW LEVEL SECURITY;

-- Nace vigente, y después solo se destruye: una clave destruida no vuelve a tener DEK ni cambia
CREATE FUNCTION clave_notas_solo_destruir() RETURNS trigger LANGUAGE plpgsql AS
$$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.destruida_en IS NOT NULL THEN
            RAISE EXCEPTION 'una clave de notas nace vigente' USING ERRCODE = 'check_violation';
        END IF;
    ELSIF OLD.destruida_en IS NOT NULL
          OR NEW.dek_cifrada_con_kek IS NOT NULL OR NEW.destruida_en IS NULL
          OR (NEW.id, NEW.grupo_id, NEW.persona_cuidada_id, NEW.kek_version, NEW.creada_en)
             IS DISTINCT FROM (OLD.id, OLD.grupo_id, OLD.persona_cuidada_id, OLD.kek_version, OLD.creada_en) THEN
        RAISE EXCEPTION 'una clave de notas solo se destruye' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER clave_notas_solo_destruir BEFORE INSERT OR UPDATE ON clave_notas
    FOR EACH ROW EXECUTE FUNCTION clave_notas_solo_destruir();

-- Quién la lee: operación, para cifrar y descifrar las notas de la consola; quien es miembro activo del grupo, que ya
-- lee sus incidencias (incidencia_familia): en la aplicación, solo la copia de sus datos la pide. Sin el marcador
-- app.funcion, que matu_app puede fijar (O2: una política que lo mira es solo TO matu_owner). El comercio, el
-- repartidor y el relevo, nunca. matu_app no la cambia ni la borra
CREATE POLICY clave_notas_operacion_leer ON clave_notas FOR SELECT USING (app_rol() = 'operacion');
CREATE POLICY clave_notas_operacion_crear ON clave_notas FOR INSERT WITH CHECK (app_rol() = 'operacion');
CREATE POLICY clave_notas_familia_leer ON clave_notas FOR SELECT USING (
    grupo_id = app_grupo()
    AND EXISTS (SELECT 1 FROM membresia m WHERE m.grupo_id = clave_notas.grupo_id AND m.usuario_id = app_usuario()
                   AND m.estado = 'activa'));
REVOKE ALL ON clave_notas FROM matu_app;
GRANT SELECT, INSERT ON clave_notas TO matu_app;

-- El borrado criptográfico de las notas sigue al borrado de la persona: cuando se borran sus datos
-- (persona_cuidada.datos_borrados_en, MATU-72), se destruye su clave de notas, y sus notas quedan ilegibles. Destruir
-- la clave de su ficha (plan_destruir_claves a los 90 días del retiro) no la toca: la persona sigue en MATU y sus
-- pedidos se guardan 2 años (decisión de Jorge del 17-11). Corre como matu_owner, con su propia política, también
-- cuando la sesión no ve la clave
CREATE FUNCTION clave_notas_destruir() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_antes text := current_setting('app.funcion', true);
BEGIN
    PERFORM set_config('app.funcion', 'clave_notas_destruir', true);
    UPDATE public.clave_notas SET dek_cifrada_con_kek = NULL, destruida_en = NEW.datos_borrados_en
     WHERE persona_cuidada_id = NEW.id AND destruida_en IS NULL;
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
    RETURN NULL;
END $$;
REVOKE ALL ON FUNCTION clave_notas_destruir() FROM PUBLIC;
CREATE POLICY clave_notas_destruccion_leer ON clave_notas FOR SELECT TO matu_owner
    USING ({FUNCION} = 'clave_notas_destruir');
CREATE POLICY clave_notas_destruccion ON clave_notas FOR UPDATE TO matu_owner
    USING ({FUNCION} = 'clave_notas_destruir') WITH CHECK ({FUNCION} = 'clave_notas_destruir');
CREATE TRIGGER persona_borrada_destruye_notas AFTER UPDATE OF datos_borrados_en ON persona_cuidada
    FOR EACH ROW WHEN (OLD.datos_borrados_en IS NULL AND NEW.datos_borrados_en IS NOT NULL)
    EXECUTE FUNCTION clave_notas_destruir();
"""

CLAVE_NOTAS_BAJADA = """
DROP TRIGGER persona_borrada_destruye_notas ON persona_cuidada;
DROP FUNCTION clave_notas_destruir();
DROP TABLE clave_notas;
DROP FUNCTION clave_notas_solo_destruir();
"""

INCIDENCIA = f"""
-- (a) incidencia. La nota en claro no se puede cifrar desde la base (la KEK no está en ella): con incidencias, la
-- subida se detiene. Ninguna versión anterior las crea (la tabla viene de 01_esquema.sql y no tenía rutas)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM incidencia) THEN
        RAISE EXCEPTION 'MATU-81: hay incidencias con la nota en claro; la 0030 no las cifra ni las borra';
    END IF;
END $$;
ALTER TABLE incidencia DROP CONSTRAINT incidencia_tipo_check;
ALTER TABLE incidencia ADD CONSTRAINT incidencia_tipo_check CHECK (tipo IN ({TIPOS_0030}));
-- La nota y la resolución, cifradas, con la clave de notas con que se cifró cada una (decisión 471). Una resuelta lleva
-- su resolución
ALTER TABLE incidencia ALTER COLUMN descripcion TYPE bytea USING convert_to(descripcion, 'UTF8');
ALTER TABLE incidencia ALTER COLUMN resolucion TYPE bytea USING convert_to(resolucion, 'UTF8');
ALTER TABLE incidencia ADD COLUMN clave_notas_id uuid NOT NULL REFERENCES clave_notas(id);
ALTER TABLE incidencia ADD COLUMN resolucion_clave_id uuid REFERENCES clave_notas(id);
ALTER TABLE incidencia ADD CONSTRAINT incidencia_descripcion_cifrada
    CHECK (octet_length(descripcion) BETWEEN {CIFRADO_MIN} AND {CIFRADO_MAX});
ALTER TABLE incidencia ADD CONSTRAINT incidencia_resolucion_cifrada
    CHECK (resolucion IS NULL OR octet_length(resolucion) BETWEEN {CIFRADO_MIN} AND {CIFRADO_MAX});
ALTER TABLE incidencia ADD CONSTRAINT incidencia_resolucion_con_clave
    CHECK ((resolucion IS NULL) = (resolucion_clave_id IS NULL));
ALTER TABLE incidencia ADD CONSTRAINT incidencia_resuelta_con_resolucion
    CHECK (estado <> 'resuelta' OR resolucion IS NOT NULL);
-- C12: la incidencia sigue a su pedido
ALTER TABLE incidencia DROP CONSTRAINT incidencia_pedido_id_fkey;
ALTER TABLE incidencia ADD CONSTRAINT incidencia_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES pedido(id)
    ON DELETE CASCADE;
-- El ETag del PATCH: sube en cada cambio, lo pone el trigger
ALTER TABLE incidencia ADD COLUMN version integer NOT NULL DEFAULT 1;
CREATE INDEX incidencia_pedido_ix ON incidencia (pedido_id, creada_en);

-- C12 y C13: solo sobre pedidos pagados, y quien la crea o la tiene asignada es una cuenta de operación activa. Lo que
-- se cifra va con la clave vigente de la persona del pedido
CREATE FUNCTION incidencia_reglas() RETURNS trigger LANGUAGE plpgsql AS
$$
BEGIN
    IF TG_OP = 'INSERT' AND NOT EXISTS (
        SELECT 1 FROM pedido p WHERE p.id = NEW.pedido_id AND p.pagado_en IS NOT NULL) THEN
        RAISE EXCEPTION 'una incidencia va solo sobre un pedido pagado' USING ERRCODE = 'check_violation';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM usuario u WHERE u.id = NEW.creada_por AND u.es_operacion AND u.estado = 'activo')
       AND (TG_OP = 'INSERT' OR NEW.creada_por IS DISTINCT FROM OLD.creada_por) THEN
        RAISE EXCEPTION 'la incidencia la crea una cuenta de operación' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.asignada_a IS NOT NULL AND (TG_OP = 'INSERT' OR NEW.asignada_a IS DISTINCT FROM OLD.asignada_a)
       AND NOT EXISTS (SELECT 1 FROM usuario u WHERE u.id = NEW.asignada_a AND u.es_operacion AND u.estado = 'activo')
       THEN
        RAISE EXCEPTION 'la incidencia se asigna a una cuenta de operación' USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'INSERT' AND NOT EXISTS (
        SELECT 1 FROM clave_notas k JOIN pedido p ON p.persona_cuidada_id = k.persona_cuidada_id
         WHERE k.id = NEW.clave_notas_id AND p.id = NEW.pedido_id AND k.destruida_en IS NULL) THEN
        RAISE EXCEPTION 'la nota va con la clave vigente de la persona del pedido' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.resolucion_clave_id IS NOT NULL
       AND (TG_OP = 'INSERT' OR NEW.resolucion_clave_id IS DISTINCT FROM OLD.resolucion_clave_id
            OR NEW.resolucion IS DISTINCT FROM OLD.resolucion)
       AND NOT EXISTS (
        SELECT 1 FROM clave_notas k JOIN pedido p ON p.persona_cuidada_id = k.persona_cuidada_id
         WHERE k.id = NEW.resolucion_clave_id AND p.id = NEW.pedido_id AND k.destruida_en IS NULL) THEN
        RAISE EXCEPTION 'la resolución va con la clave vigente de la persona del pedido'
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        NEW.version := OLD.version + 1;
    ELSE
        NEW.version := 1;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER incidencia_reglas BEFORE INSERT OR UPDATE ON incidencia
    FOR EACH ROW EXECUTE FUNCTION incidencia_reglas();

-- C13: leer, crear y editar, sin DELETE. Crea solo la cuenta del contexto
DROP POLICY incidencia_operacion ON incidencia;
CREATE POLICY incidencia_operacion_leer ON incidencia FOR SELECT USING (app_rol() = 'operacion');
CREATE POLICY incidencia_operacion_crear ON incidencia FOR INSERT
    WITH CHECK (app_rol() = 'operacion' AND creada_por = app_usuario());
CREATE POLICY incidencia_operacion_editar ON incidencia FOR UPDATE
    USING (app_rol() = 'operacion') WITH CHECK (app_rol() = 'operacion');
REVOKE UPDATE, DELETE ON incidencia FROM matu_app;
GRANT UPDATE (estado, asignada_a, resolucion, resolucion_clave_id, resuelta_en) ON incidencia TO matu_app;
"""

INCIDENCIA_BAJADA = f"""
-- Lo cifrado no vuelve a texto sin la KEK, y nunca se borra una incidencia ni una clave: con filas, la bajada se
-- detiene
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM incidencia) OR EXISTS (SELECT 1 FROM clave_notas) THEN
        RAISE EXCEPTION 'MATU-81: hay incidencias o claves de notas; la bajada de la 0030 no las descifra ni las borra';
    END IF;
END $$;
REVOKE UPDATE (estado, asignada_a, resolucion, resolucion_clave_id, resuelta_en) ON incidencia FROM matu_app;
GRANT UPDATE, DELETE ON incidencia TO matu_app;
DROP POLICY incidencia_operacion_editar ON incidencia;
DROP POLICY incidencia_operacion_crear ON incidencia;
DROP POLICY incidencia_operacion_leer ON incidencia;
CREATE POLICY incidencia_operacion ON incidencia FOR ALL USING (app_rol() = 'operacion');
DROP TRIGGER incidencia_reglas ON incidencia;
DROP FUNCTION incidencia_reglas();
DROP INDEX incidencia_pedido_ix;
ALTER TABLE incidencia DROP COLUMN version;
ALTER TABLE incidencia DROP CONSTRAINT incidencia_pedido_id_fkey;
ALTER TABLE incidencia ADD CONSTRAINT incidencia_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES pedido(id);
ALTER TABLE incidencia DROP CONSTRAINT incidencia_resuelta_con_resolucion;
ALTER TABLE incidencia DROP CONSTRAINT incidencia_resolucion_con_clave;
ALTER TABLE incidencia DROP CONSTRAINT incidencia_resolucion_cifrada;
ALTER TABLE incidencia DROP CONSTRAINT incidencia_descripcion_cifrada;
ALTER TABLE incidencia DROP COLUMN resolucion_clave_id;
ALTER TABLE incidencia DROP COLUMN clave_notas_id;
ALTER TABLE incidencia ALTER COLUMN resolucion TYPE text USING convert_from(resolucion, 'UTF8');
ALTER TABLE incidencia ALTER COLUMN descripcion TYPE text USING convert_from(descripcion, 'UTF8');
ALTER TABLE incidencia DROP CONSTRAINT incidencia_tipo_check;
ALTER TABLE incidencia ADD CONSTRAINT incidencia_tipo_check CHECK (tipo IN ({TIPOS_0001}));
"""

AUDITORIA = f"""
-- (c) Las acciones nuevas de la auditoría
ALTER TABLE auditoria DROP CONSTRAINT auditoria_cuenta_acotada;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_cuenta_acotada
    CHECK (grupo_id IS NOT NULL OR accion IN ({_lista(SIN_GRUPO_0030)})) NOT VALID;
ALTER TABLE auditoria VALIDATE CONSTRAINT auditoria_cuenta_acotada;
ALTER TABLE auditoria DROP CONSTRAINT auditoria_persona_obligatoria;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_persona_obligatoria
    CHECK (persona_cuidada_id IS NOT NULL OR accion NOT IN ({_lista(ACCIONES_DE_PERSONA_0030)})) NOT VALID;
"""

AUDITORIA_BAJADA = f"""
ALTER TABLE auditoria DROP CONSTRAINT auditoria_persona_obligatoria;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_persona_obligatoria
    CHECK (persona_cuidada_id IS NOT NULL OR accion NOT IN ({_lista(ACCIONES_DE_PERSONA_0029)})) NOT VALID;
-- Con filas de las acciones nuevas sin grupo, vuelve NOT VALID: nunca se borra un registro de auditoría
ALTER TABLE auditoria DROP CONSTRAINT auditoria_cuenta_acotada;
DO $$ BEGIN
    BEGIN
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_cuenta_acotada
            CHECK (grupo_id IS NOT NULL OR accion IN ({_lista(SIN_GRUPO_0029)}));
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'MATU-81: hay acciones de operación en la auditoría; el CHECK de la 0029 vuelve NOT VALID';
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_cuenta_acotada
            CHECK (grupo_id IS NOT NULL OR accion IN ({_lista(SIN_GRUPO_0029)})) NOT VALID;
    END;
END $$;
"""

MFA = f"""
-- (d) C27: lo cifrado solo de la cuenta que está entrando, como iam_credencial (0020)
CREATE FUNCTION iam_mfa_secreto(p_usuario uuid) RETURNS bytea
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
    SELECT u.mfa_secreto_cifrado FROM public.usuario u
     WHERE u.id = p_usuario AND u.id = public.app_usuario() AND public.app_rol() <> 'operacion'
       AND u.es_operacion AND u.estado = 'activo'
$$;
REVOKE ALL ON FUNCTION iam_mfa_secreto(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION iam_mfa_secreto(uuid) TO matu_app;

-- C29 y C31: la marca del segundo factor en la sesión, y 12 horas como máximo desde él
ALTER TABLE sesion_refresh ADD COLUMN mfa_en timestamptz;
ALTER TABLE sesion_refresh ADD CONSTRAINT sesion_refresh_mfa
    CHECK (mfa_en IS NULL OR (mfa_en <= emitido_en AND expira_en <= mfa_en + interval '12 hours'));
CREATE FUNCTION sesion_refresh_mfa() RETURNS trigger LANGUAGE plpgsql AS
$$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.mfa_en IS DISTINCT FROM OLD.mfa_en THEN
            RAISE EXCEPTION 'la marca del segundo factor no cambia' USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.mfa_en IS NULL AND EXISTS (SELECT 1 FROM usuario u WHERE u.id = NEW.usuario_id AND u.es_operacion) THEN
        RAISE EXCEPTION 'una cuenta de operación entra con el segundo factor' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER sesion_refresh_mfa BEFORE INSERT OR UPDATE ON sesion_refresh
    FOR EACH ROW EXECUTE FUNCTION sesion_refresh_mfa();

-- C33: una cuenta de operación no es miembro de un grupo ni de un comercio, y al revés
CREATE FUNCTION cuenta_operacion_separada() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_antes text := current_setting('app.funcion', true);
    v_choca boolean;
BEGIN
    PERFORM set_config('app.funcion', 'cuentas', true);
    IF TG_TABLE_NAME = 'usuario' THEN
        v_choca := NEW.es_operacion AND (
            EXISTS (SELECT 1 FROM public.membresia m WHERE m.usuario_id = NEW.id AND m.estado = 'activa')
            OR EXISTS (SELECT 1 FROM public.usuario_comercio uc WHERE uc.usuario_id = NEW.id AND uc.activo));
    ELSIF TG_TABLE_NAME = 'membresia' THEN
        v_choca := NEW.estado = 'activa'
                   AND EXISTS (SELECT 1 FROM public.usuario u WHERE u.id = NEW.usuario_id AND u.es_operacion);
    ELSE
        v_choca := NEW.activo
                   AND EXISTS (SELECT 1 FROM public.usuario u WHERE u.id = NEW.usuario_id AND u.es_operacion);
    END IF;
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
    IF v_choca THEN
        RAISE EXCEPTION 'una cuenta de operación no es miembro de un grupo ni de un comercio'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION cuenta_operacion_separada() FROM PUBLIC;
-- La función lee la cuenta como matu_owner, también cuando la sesión no la ve
CREATE POLICY usuario_cuentas ON usuario FOR SELECT TO matu_owner USING ({FUNCION} = 'cuentas');
CREATE TRIGGER usuario_operacion_separada BEFORE INSERT OR UPDATE OF es_operacion ON usuario
    FOR EACH ROW EXECUTE FUNCTION cuenta_operacion_separada();
CREATE TRIGGER membresia_no_operacion BEFORE INSERT OR UPDATE ON membresia
    FOR EACH ROW EXECUTE FUNCTION cuenta_operacion_separada();
CREATE TRIGGER usuario_comercio_no_operacion BEFORE INSERT OR UPDATE ON usuario_comercio
    FOR EACH ROW EXECUTE FUNCTION cuenta_operacion_separada();

-- C28: el alta desde la consola, solo para matu_scheduler con app.rol = 'operacion'. Primero la cuenta por la huella
-- de su correo (el AAD del secreto lleva su id), después el alta
CREATE FUNCTION operacion_buscar_cuenta(p_email_hash bytea) RETURNS TABLE (usuario_id uuid, resultado text)
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_usuario uuid;
    v_estado text;
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'operacion_buscar_cuenta exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT i.usuario_id INTO v_usuario FROM public.indice_credencial i WHERE i.email_hash = p_email_hash;
    IF v_usuario IS NULL THEN
        RETURN QUERY SELECT NULL::uuid, 'sin_cuenta'::text;
        RETURN;
    END IF;
    SELECT u.estado INTO v_estado FROM public.usuario u WHERE u.id = v_usuario;
    IF v_estado IS DISTINCT FROM 'activo' THEN
        RETURN QUERY SELECT NULL::uuid, 'no_activa'::text;
    ELSIF EXISTS (SELECT 1 FROM public.membresia m WHERE m.usuario_id = v_usuario AND m.estado = 'activa') THEN
        RETURN QUERY SELECT NULL::uuid, 'en_un_grupo'::text;
    ELSIF EXISTS (SELECT 1 FROM public.usuario_comercio uc WHERE uc.usuario_id = v_usuario AND uc.activo) THEN
        RETURN QUERY SELECT NULL::uuid, 'de_un_comercio'::text;
    ELSE
        RETURN QUERY SELECT v_usuario, 'ok'::text;
    END IF;
END $$;

CREATE FUNCTION operacion_alta(p_usuario uuid, p_secreto bytea) RETURNS text
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_cambiadas integer;
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'operacion_alta exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_secreto IS NULL OR octet_length(p_secreto) < 1 + 12 + 20 + 16 THEN
        RAISE EXCEPTION 'el secreto cifrado no tiene la forma esperada' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    PERFORM set_config('app.funcion', 'operacion_alta', true);
    UPDATE public.usuario SET es_operacion = true, mfa_secreto_cifrado = p_secreto, actualizado_en = now()
     WHERE id = p_usuario AND estado = 'activo';
    GET DIAGNOSTICS v_cambiadas = ROW_COUNT;
    IF v_cambiadas = 0 THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'sin_cuenta';
    END IF;
    -- Repetir el alta (un teléfono perdido) cierra las sesiones abiertas con el secreto anterior
    UPDATE public.sesion_refresh SET revocado_en = now(), motivo_revocacion = 'operacion'
     WHERE usuario_id = p_usuario AND revocado_en IS NULL;
    PERFORM set_config('app.funcion', '', true);
    INSERT INTO public.auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id)
    VALUES (NULL, 'sistema', NULL, 'cuenta.mfa_alta', 'usuario', p_usuario);
    RETURN 'ok';
END $$;
CREATE POLICY usuario_alta_operacion ON usuario FOR UPDATE TO matu_owner
    USING ({FUNCION} = 'operacion_alta') WITH CHECK ({FUNCION} = 'operacion_alta');
CREATE POLICY sesion_alta_operacion ON sesion_refresh FOR UPDATE TO matu_owner
    USING ({FUNCION} = 'operacion_alta') WITH CHECK ({FUNCION} = 'operacion_alta');
REVOKE ALL ON FUNCTION operacion_buscar_cuenta(bytea) FROM PUBLIC;
REVOKE ALL ON FUNCTION operacion_alta(uuid, bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION operacion_buscar_cuenta(bytea) TO matu_scheduler;
GRANT EXECUTE ON FUNCTION operacion_alta(uuid, bytea) TO matu_scheduler;
"""

MFA_BAJADA = """
REVOKE EXECUTE ON FUNCTION operacion_alta(uuid, bytea) FROM matu_scheduler;
REVOKE EXECUTE ON FUNCTION operacion_buscar_cuenta(bytea) FROM matu_scheduler;
DROP POLICY sesion_alta_operacion ON sesion_refresh;
DROP POLICY usuario_alta_operacion ON usuario;
DROP FUNCTION operacion_alta(uuid, bytea);
DROP FUNCTION operacion_buscar_cuenta(bytea);
DROP TRIGGER usuario_comercio_no_operacion ON usuario_comercio;
DROP TRIGGER membresia_no_operacion ON membresia;
DROP TRIGGER usuario_operacion_separada ON usuario;
DROP POLICY usuario_cuentas ON usuario;
DROP FUNCTION cuenta_operacion_separada();
DROP TRIGGER sesion_refresh_mfa ON sesion_refresh;
DROP FUNCTION sesion_refresh_mfa();
ALTER TABLE sesion_refresh DROP CONSTRAINT sesion_refresh_mfa;
ALTER TABLE sesion_refresh DROP COLUMN mfa_en;
DROP FUNCTION iam_mfa_secreto(uuid);
"""

RETRACTO_Y_OFERTA = """
-- (f) C24: por qué se rechazó un retracto, de una lista cerrada que la familia ve
ALTER TABLE retracto ADD COLUMN motivo_rechazo text;
ALTER TABLE retracto ADD CONSTRAINT retracto_motivo_rechazo
    CHECK (motivo_rechazo IS NULL OR (motivo_rechazo IN ('sello_abierto', 'producto_no_recibido')
                                      AND estado = 'rechazado'));

-- (g) C1: operación cambia precio, stock y disponible solo en las ofertas de comercios ficticios
CREATE FUNCTION oferta_operacion_ficticia() RETURNS trigger LANGUAGE plpgsql AS
$$
BEGIN
    IF app_rol() = 'operacion' AND (NEW.precio, NEW.stock, NEW.disponible) IS DISTINCT FROM
                                   (OLD.precio, OLD.stock, OLD.disponible)
       AND NOT EXISTS (SELECT 1 FROM comercio c WHERE c.id = NEW.comercio_id AND c.ficticio) THEN
        RAISE EXCEPTION 'operación cambia solo las ofertas de los comercios ficticios'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER oferta_operacion_ficticia BEFORE UPDATE ON oferta
    FOR EACH ROW EXECUTE FUNCTION oferta_operacion_ficticia();
"""

RETRACTO_Y_OFERTA_BAJADA = """
DROP TRIGGER oferta_operacion_ficticia ON oferta;
DROP FUNCTION oferta_operacion_ficticia();
-- Nunca se borra un motivo de rechazo: con uno guardado, la bajada se detiene
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM retracto WHERE motivo_rechazo IS NOT NULL) THEN
        RAISE EXCEPTION 'MATU-81: hay retractos con motivo de rechazo; la bajada de la 0030 no los borra';
    END IF;
END $$;
ALTER TABLE retracto DROP CONSTRAINT retracto_motivo_rechazo;
ALTER TABLE retracto DROP COLUMN motivo_rechazo;
"""

POLITICAS = """
-- (b) D-81-2: operación no lee las aceptaciones de la política
DROP POLICY aceptacion_operacion_leer ON aceptacion_politica;

-- (e) D-81-6: operación no lee la persona cuidada, y la entrega del pedido la lee sin escribirla
DROP POLICY persona_operacion ON persona_cuidada;
DROP POLICY entrega_operacion ON pedido_entrega;
CREATE POLICY entrega_operacion_leer ON pedido_entrega FOR SELECT USING (app_rol() = 'operacion');
-- Decisión 452: el consentimiento lo leen solo las funciones de conservación (plan_destruir_claves y
-- consumo_conservar, SECURITY DEFINER como matu_owner), nunca matu_app con app.rol = 'operacion'
DROP POLICY consentimiento_operacion ON consentimiento;
CREATE POLICY consentimiento_conservacion ON consentimiento FOR SELECT TO matu_owner USING (app_rol() = 'operacion');
"""

POLITICAS_BAJADA = """
DROP POLICY consentimiento_conservacion ON consentimiento;
CREATE POLICY consentimiento_operacion ON consentimiento FOR SELECT USING (app_rol() = 'operacion');
DROP POLICY entrega_operacion_leer ON pedido_entrega;
CREATE POLICY entrega_operacion ON pedido_entrega FOR ALL USING (app_rol() = 'operacion');
CREATE POLICY persona_operacion ON persona_cuidada FOR SELECT USING (app_rol() = 'operacion');
CREATE POLICY aceptacion_operacion_leer ON aceptacion_politica FOR SELECT USING (app_rol() = 'operacion');
"""

# La migración corre como matu_owner, con FORCE ROW LEVEL SECURITY: app.rol = 'operacion' le deja ver si hay
# incidencias (incidencia_operacion), claves de notas (clave_notas_operacion_leer) y retractos
# (retracto_operacion_leer)
UPGRADE = (
    "SELECT set_config('app.rol', 'operacion', true);\n"
    + CLAVE_NOTAS
    + INCIDENCIA
    + POLITICAS
    + AUDITORIA
    + MFA
    + RETRACTO_Y_OFERTA
    + "SELECT set_config('app.rol', '', true);\n"
)
DOWNGRADE = (
    "SELECT set_config('app.rol', 'operacion', true);\n"
    + RETRACTO_Y_OFERTA_BAJADA
    + MFA_BAJADA
    + AUDITORIA_BAJADA
    + POLITICAS_BAJADA
    + INCIDENCIA_BAJADA
    + CLAVE_NOTAS_BAJADA
    + "SELECT set_config('app.rol', '', true);\n"
)


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

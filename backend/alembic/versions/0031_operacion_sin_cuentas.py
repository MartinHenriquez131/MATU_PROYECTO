"""MATU-114: operación deja de leer cuentas y membresías por RLS (minimización, Ley 21.719).

Cadena: 0030 (MATU-81) -> 0031. down_revision = "0030". MATU-113 y MATU-76 no traen migración.

Revisión previa del analista normativo del 18-11, condiciones C1 a C19, y decisiones J1, J2 y J4 (O1 y O6) del
mandato de Jorge del 18-11. Decisión 474 de docs/api/README.md. backend/db/*.sql no se tocan.

Cuentas (C1 a C6)
a) C1: sale usuario_operacion_leer. matu_app con app.rol = 'operacion' ya no lee el email, el celular ni el nombre de
   ninguna cuenta; con su propia cuenta en el contexto, solo la suya (usuario_propio_leer). Las rutas de operación
   fijan además el grupo del pedido (AbrirDespachoSQL), y con él usuario_comiembro y membresia_familia_leer le dejaban
   leer las cuentas y las membresías de ese grupo: la política restrictiva usuario_no_operacion (TO matu_app) deja
   solo la propia fila cuando app.rol = 'operacion'. Las funciones (matu_owner) no cambian.
b) C2: operacion_cuenta_activa(uuid) responde solo si la cuenta es de operación y está activa. SECURITY DEFINER, dueño
   matu_owner, search_path fijo, STABLE; lee la cuenta con el marcador app.funcion = 'cuentas' (usuario_cuentas, TO
   matu_owner, 0030) y devuelve el valor anterior al salir. EXECUTE solo matu_app.
c) C3: incidencia_reglas usa operacion_cuenta_activa() para creada_por y asignada_a, en vez de leer usuario.
d) C5: operacion_buscar_cuenta fija el marcador 'cuentas' antes de leer usuario, membresia y usuario_comercio
   (usuario_cuentas de la 0030, membresia_cuentas y usuario_comercio_cuentas de la 0029) y lo devuelve al salir.
e) O6 (J4): sesion_refresh_mfa ya no lee usuario con los permisos de quien llama, que fallaba abierta: si la sesión no
   veía la fila, el refresh se creaba sin el segundo factor. Usa cuenta_es_operacion(uuid) (definer, como C2, con la
   misma regla de hoy: es_operacion, sin mirar el estado).
f) C6, el recorrido de las funciones SECURITY DEFINER y de las tareas con app.rol = 'operacion' que leen usuario,
   membresia o invitacion (las políticas sin TO alcanzan también a matu_owner):
   - incidencia_reglas (invoker, matu_app con operación): leía usuario por usuario_operacion_leer. Pasa a (c).
   - operacion_buscar_cuenta (definer, matu_scheduler con operación, el alta): leía usuario por usuario_operacion_leer
     y membresia por membresia_operacion. Pasa a (d).
   - sesion_refresh_mfa (invoker): leía usuario con la sesión de quien entra. Pasa a (e).
   - invitacion_conservar (definer, matu_scheduler con operación, la conservación de 30 días): su DELETE ... USING
     invitacion y su DELETE ... WHERE necesitan una política de SELECT, y la única era invitacion_operacion. Entra
     invitacion_conservacion_leer, SELECT TO matu_owner con app.rol = 'operacion', igual que
     invitacion_conservacion_borrar: matu_app con operación ya no la ve.
   - operacion_alta (definer, matu_scheduler con operación, el alta): su UPDATE ... WHERE id = ... AND estado =
     'activo' necesita ver la fila, y la veía por usuario_operacion_leer. Entra usuario_alta_operacion_leer, SELECT TO
     matu_owner con su mismo marcador ('operacion_alta'), junto a usuario_alta_operacion (UPDATE, 0030).
   - Sin cambios, porque no dependen de las políticas que salen: cuenta_operacion_separada y cuenta_comercio_o_familia
     (marcador 'cuentas'); iam_credencial e iam_mfa_secreto (la propia cuenta, nunca con operación);
     invitacion_presentar, invitacion_verificar e invitacion_aceptar
     (marcador 'invitacion', sin operación); membresia_retirar (marcador 'membresia_retirar'); las app_* de membresía
     (membresia_propia, con la cuenta del contexto). plan_destruir_claves, consumo_conservar, iam_conservar,
     quiebre_conservar, pedido_conservar, relevo_conservar, despacho_pendiente, codigo_retiro_guardar,
     codigo_retiro_vencer, pagos_por_conciliar y outbox_* no leen usuario, membresia ni invitacion.
   - En la aplicación, con operación: _ADMIN_POR_CORREO y _ES_ADMIN de router_operacion.py leían membresia por
     membresia_operacion. Pasan a (h). Las demás rutas de operación y tareas no leen esas tablas; los avisos
     (notifications) leen membresia y usuario con app.rol = 'sistema' y el grupo del evento (usuario_comiembro).

Membresías, invitaciones y retracto (C7 a C11)
g) C7 y O1: salen membresia_operacion e invitacion_operacion. Ninguna ruta las usa; la tarea de invitaciones, por (f).
   Como en (a), membresia_no_operacion e invitacion_no_operacion (restrictivas, TO matu_app) cierran la lectura por
   el grupo del contexto (membresia_familia_leer, invitacion_admin_leer) cuando app.rol = 'operacion'.
h) C8: operacion_solicitante_retracto(pedido, email_hash, solicitado_por) devuelve solo el id que va en
   retracto.solicitado_por, o NULL; nunca el correo, el nombre, el rol ni por qué no. Definer, dueño matu_owner,
   search_path fijo, EXECUTE solo matu_app. Exige app.rol = 'operacion' y que app.usuario_id sea una cuenta de
   operación activa (si no, insufficient_privilege). Lee membresia con el marcador 'cuentas'. La regla de hoy:
   con la huella, el admin activo del grupo del pedido con esa huella; con el id, que sea quien pagó o un admin
   activo; sin nada, quien pagó; con los dos, NULL. Quien pagó sale de participacion y cargo
   (participacion_operacion_leer y cargo_operacion_leer, que también alcanzan a matu_owner; MATU-122 las revisa).
i) J2: la acción operacion.retracto_correo_fallido, con el grupo y la persona del pedido y sin el correo, se suma a
   auditoria_persona_obligatoria.

Código de retiro (C12 a C15)
j) pedido_comercio.codigo_vigente, columna generada (codigo_hash IS NOT NULL), que lee la consola en vez de la huella.
   matu_app pierde el SELECT de codigo_hash: GRANT por columna de las demás. Los UPDATE ... SET codigo_hash siguen (no
   exigen leerla), y codigo_retiro_guardar, codigo_retiro_vencer y comercio_validar_codigo son definer y no cambian.
   Una columna nueva de pedido_comercio necesita su GRANT de SELECT.

Clave de las notas (C16 y C17)
k) clave_notas_familia_leer pasa a grupo_id = app_grupo() AND app_escribe_plan(): admin y cuidador activos, los mismos
   que piden «Datos de» (router_copia.py, ROLES_QUE_PIDEN), la única que la lee. Pagador y observador, ya no.

Las políticas que no son TO matu_owner y miran app.rol = 'operacion', después de la 0031 (sacada de pg_policies; la
verifica tests/test_migraciones.py, POLITICAS_OPERACION_0031). Ninguna es de usuario, membresia ni invitacion:
- care_circle: direccion_operacion_leer (O3) y grupo_operacion (O7, FOR ALL), que quedan para MATU-122.
- Consumo: alerta_leer, perfil_leer y reposicion_leer (operación lee, como desde la 0009).
- Capa 3: pedido_operacion_leer, pedido_operacion_pago, pedido_comercio_operacion_leer,
  pedido_comercio_operacion_editar, entrega_operacion_leer (O3), linea_pago_devolver, transicion_sistema_crear,
  cargo_operacion_leer, cargo_operacion_editar, participacion_operacion_leer (O4), participacion_operacion_editar,
  transaccion_operacion_leer, transaccion_operacion_crear, transaccion_operacion_editar, retracto_operacion_leer,
  retracto_operacion_crear, retracto_operacion_editar, retracto_linea_operacion_leer, retracto_linea_operacion_crear,
  incidencia_operacion_leer, incidencia_operacion_crear, incidencia_operacion_editar, clave_notas_operacion_leer,
  clave_notas_operacion_crear, consumo_comercio_operacion y auditoria_insertar.
- Catálogo y Product Backlog: categoria_operacion, producto_operacion, comercio_operacion, convenio_operacion,
  oferta_operacion, usuario_comercio_operacion (O2, FOR ALL; MATU-122), asignacion_operacion, oferta_asig_operacion,
  repartidor_operacion y liquidacion_operacion.

downgrade() deja el esquema como en 0030 sin borrar nada: recrea las tres políticas que salen, como en la 0020 y la
0026, devuelve el SELECT completo de pedido_comercio y las funciones de la 0030. La auditoría con la acción nueva deja
el CHECK de la 0030 NOT VALID, como las bajadas anteriores.

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
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


ACCIONES_DE_PERSONA_0030 = (
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
    "operacion.pedido_ver",
    "incidencia.crear",
    "incidencia.resolver",
)
# J2: el intento fallido de registrar un retracto por el correo de quien lo pidió, con el grupo y la persona del pedido
ACCIONES_DE_PERSONA_0031 = (*ACCIONES_DE_PERSONA_0030, "operacion.retracto_correo_fallido")

# Las columnas de pedido_comercio que matu_app lee: todas menos codigo_hash (C12), más codigo_vigente (C13)
COLUMNAS_PARTE = (
    "id, grupo_id, pedido_id, comercio_id, referencia, enviado_en, creado_en, estado, version, preparando_en,"
    " lista_en, retirada_en, cancelada_en, motivo_cancelacion, codigo_generado_en, codigo_expira_en, codigo_usado_en,"
    " codigo_intentos, codigo_bloqueado_en, apartado_hasta"
)

# La regla de C12 y C13 de la 0030, con las cuentas leídas por (c)
INCIDENCIA_REGLAS = """
CREATE OR REPLACE FUNCTION incidencia_reglas() RETURNS trigger LANGUAGE plpgsql AS
$$
BEGIN
    IF TG_OP = 'INSERT' AND NOT EXISTS (
        SELECT 1 FROM pedido p WHERE p.id = NEW.pedido_id AND p.pagado_en IS NOT NULL) THEN
        RAISE EXCEPTION 'una incidencia va solo sobre un pedido pagado' USING ERRCODE = 'check_violation';
    END IF;
    IF {CREADA_POR_NO_ES}
       AND (TG_OP = 'INSERT' OR NEW.creada_por IS DISTINCT FROM OLD.creada_por) THEN
        RAISE EXCEPTION 'la incidencia la crea una cuenta de operación' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.asignada_a IS NOT NULL AND (TG_OP = 'INSERT' OR NEW.asignada_a IS DISTINCT FROM OLD.asignada_a)
       AND {ASIGNADA_A_NO_ES}
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
"""
INCIDENCIA_REGLAS_0031 = INCIDENCIA_REGLAS.replace(
    "{CREADA_POR_NO_ES}", "NOT operacion_cuenta_activa(NEW.creada_por)"
).replace("{ASIGNADA_A_NO_ES}", "NOT operacion_cuenta_activa(NEW.asignada_a)")
INCIDENCIA_REGLAS_0030 = INCIDENCIA_REGLAS.replace(
    "{CREADA_POR_NO_ES}",
    "NOT EXISTS (SELECT 1 FROM usuario u WHERE u.id = NEW.creada_por AND u.es_operacion AND u.estado = 'activo')",
).replace(
    "{ASIGNADA_A_NO_ES}",
    "NOT EXISTS (SELECT 1 FROM usuario u WHERE u.id = NEW.asignada_a AND u.es_operacion AND u.estado = 'activo')",
)

SESION_REFRESH_MFA = """
CREATE OR REPLACE FUNCTION sesion_refresh_mfa() RETURNS trigger LANGUAGE plpgsql AS
$$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.mfa_en IS DISTINCT FROM OLD.mfa_en THEN
            RAISE EXCEPTION 'la marca del segundo factor no cambia' USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.mfa_en IS NULL AND {ES_OPERACION} THEN
        RAISE EXCEPTION 'una cuenta de operación entra con el segundo factor' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
"""
SESION_REFRESH_MFA_0031 = SESION_REFRESH_MFA.replace("{ES_OPERACION}", "cuenta_es_operacion(NEW.usuario_id)")
SESION_REFRESH_MFA_0030 = SESION_REFRESH_MFA.replace(
    "{ES_OPERACION}", "EXISTS (SELECT 1 FROM usuario u WHERE u.id = NEW.usuario_id AND u.es_operacion)"
)

BUSCAR_CUENTA = """
CREATE OR REPLACE FUNCTION operacion_buscar_cuenta(p_email_hash bytea) RETURNS TABLE (usuario_id uuid, resultado text)
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_usuario uuid;
    v_estado text;
{DECLARAR}BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'operacion_buscar_cuenta exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    SELECT i.usuario_id INTO v_usuario FROM public.indice_credencial i WHERE i.email_hash = p_email_hash;
    IF v_usuario IS NULL THEN
        RETURN QUERY SELECT NULL::uuid, 'sin_cuenta'::text;
        RETURN;
    END IF;
{CUERPO}END $$;
"""
BUSCAR_CUENTA_0030 = BUSCAR_CUENTA.replace("{DECLARAR}", "").replace(
    "{CUERPO}",
    """    SELECT u.estado INTO v_estado FROM public.usuario u WHERE u.id = v_usuario;
    IF v_estado IS DISTINCT FROM 'activo' THEN
        RETURN QUERY SELECT NULL::uuid, 'no_activa'::text;
    ELSIF EXISTS (SELECT 1 FROM public.membresia m WHERE m.usuario_id = v_usuario AND m.estado = 'activa') THEN
        RETURN QUERY SELECT NULL::uuid, 'en_un_grupo'::text;
    ELSIF EXISTS (SELECT 1 FROM public.usuario_comercio uc WHERE uc.usuario_id = v_usuario AND uc.activo) THEN
        RETURN QUERY SELECT NULL::uuid, 'de_un_comercio'::text;
    ELSE
        RETURN QUERY SELECT v_usuario, 'ok'::text;
    END IF;
""",
)
# C5: la cuenta, sus grupos y su comercio, con el marcador 'cuentas' (políticas TO matu_owner); se devuelve al salir
BUSCAR_CUENTA_0031 = BUSCAR_CUENTA.replace(
    "{DECLARAR}", "    v_antes text := current_setting('app.funcion', true);\n    v_resultado text;\n"
).replace(
    "{CUERPO}",
    """    PERFORM set_config('app.funcion', 'cuentas', true);
    SELECT u.estado INTO v_estado FROM public.usuario u WHERE u.id = v_usuario;
    IF v_estado IS DISTINCT FROM 'activo' THEN
        v_resultado := 'no_activa';
    ELSIF EXISTS (SELECT 1 FROM public.membresia m WHERE m.usuario_id = v_usuario AND m.estado = 'activa') THEN
        v_resultado := 'en_un_grupo';
    ELSIF EXISTS (SELECT 1 FROM public.usuario_comercio uc WHERE uc.usuario_id = v_usuario AND uc.activo) THEN
        v_resultado := 'de_un_comercio';
    ELSE
        v_resultado := 'ok';
    END IF;
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
    RETURN QUERY SELECT CASE WHEN v_resultado = 'ok' THEN v_usuario END, v_resultado;
""",
)

CUENTAS = """
-- (a) C1: operación no lee las cuentas, tampoco por el grupo del contexto (usuario_comiembro)
DROP POLICY usuario_operacion_leer ON usuario;
CREATE POLICY usuario_no_operacion ON usuario AS RESTRICTIVE FOR SELECT TO matu_app
    USING (app_rol() IS DISTINCT FROM 'operacion' OR id = app_usuario());
-- (f) operacion_alta actualiza la cuenta con su marcador, y el UPDATE ... WHERE exige verla
CREATE POLICY usuario_alta_operacion_leer ON usuario FOR SELECT TO matu_owner
    USING (current_setting('app.funcion', true) = 'operacion_alta');

-- (b) C2: si una cuenta es de operación y está activa, sin leer la fila con los permisos de quien llama
CREATE FUNCTION operacion_cuenta_activa(p_usuario uuid) RETURNS boolean
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_antes text := current_setting('app.funcion', true);
    v_es boolean;
BEGIN
    IF p_usuario IS NULL THEN
        RETURN false;
    END IF;
    PERFORM set_config('app.funcion', 'cuentas', true);
    v_es := EXISTS (SELECT 1 FROM public.usuario u WHERE u.id = p_usuario AND u.es_operacion AND u.estado = 'activo');
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
    RETURN COALESCE(v_es, false);
END $$;
REVOKE ALL ON FUNCTION operacion_cuenta_activa(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION operacion_cuenta_activa(uuid) TO matu_app;

-- (e) O6: la regla del segundo factor de la 0030 (es_operacion, sin mirar el estado), sin depender de la sesión
CREATE FUNCTION cuenta_es_operacion(p_usuario uuid) RETURNS boolean
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_antes text := current_setting('app.funcion', true);
    v_es boolean;
BEGIN
    IF p_usuario IS NULL THEN
        RETURN false;
    END IF;
    PERFORM set_config('app.funcion', 'cuentas', true);
    v_es := EXISTS (SELECT 1 FROM public.usuario u WHERE u.id = p_usuario AND u.es_operacion);
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
    RETURN COALESCE(v_es, false);
END $$;
REVOKE ALL ON FUNCTION cuenta_es_operacion(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION cuenta_es_operacion(uuid) TO matu_app;
"""

CUENTAS_BAJADA = """
DROP FUNCTION cuenta_es_operacion(uuid);
DROP FUNCTION operacion_cuenta_activa(uuid);
DROP POLICY usuario_alta_operacion_leer ON usuario;
DROP POLICY usuario_no_operacion ON usuario;
CREATE POLICY usuario_operacion_leer ON usuario FOR SELECT USING (app_rol() = 'operacion');
"""

MEMBRESIAS = """
-- (g) C7 y O1: operación no lee las membresías ni las invitaciones
DROP POLICY membresia_operacion ON membresia;
DROP POLICY invitacion_operacion ON invitacion;
-- Tampoco por el grupo del contexto (membresia_familia_leer e invitacion_admin_leer): las rutas de operación fijan el
-- grupo del pedido sin ser miembros
CREATE POLICY membresia_no_operacion ON membresia AS RESTRICTIVE FOR SELECT TO matu_app
    USING (app_rol() IS DISTINCT FROM 'operacion');
CREATE POLICY invitacion_no_operacion ON invitacion AS RESTRICTIVE FOR SELECT TO matu_app
    USING (app_rol() IS DISTINCT FROM 'operacion');
-- (f) invitacion_conservar (matu_scheduler con operación) borra con DELETE ... USING y WHERE, que exigen ver la fila
CREATE POLICY invitacion_conservacion_leer ON invitacion FOR SELECT TO matu_owner USING (app_rol() = 'operacion');

-- (h) C8: a nombre de quién va el retracto por correo. Solo el id, o NULL
CREATE FUNCTION operacion_solicitante_retracto(p_pedido uuid, p_email_hash bytea, p_solicitado_por uuid)
    RETURNS uuid
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_antes text;
    v_grupo uuid;
    v_pagador uuid;
    v_solicitante uuid;
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' OR NOT public.operacion_cuenta_activa(public.app_usuario()) THEN
        RAISE EXCEPTION 'operacion_solicitante_retracto exige una cuenta de operación activa'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_email_hash IS NOT NULL AND p_solicitado_por IS NOT NULL THEN
        RETURN NULL;
    END IF;
    SELECT p.grupo_id INTO v_grupo FROM public.pedido p WHERE p.id = p_pedido;
    IF v_grupo IS NULL THEN
        RETURN NULL;
    END IF;
    -- Quien pagó: la primera participación con un cobro (como _QUIEN_PAGO desde MATU-63)
    SELECT pa.usuario_id INTO v_pagador FROM public.participacion pa JOIN public.cargo c ON c.id = pa.cargo_id
     WHERE c.pedido_id = p_pedido AND pa.monto_cobrado > 0 ORDER BY pa.id LIMIT 1;
    v_antes := current_setting('app.funcion', true);
    PERFORM set_config('app.funcion', 'cuentas', true);
    IF p_email_hash IS NOT NULL THEN
        SELECT m.usuario_id INTO v_solicitante
          FROM public.indice_credencial i JOIN public.membresia m ON m.usuario_id = i.usuario_id
         WHERE i.email_hash = p_email_hash AND m.grupo_id = v_grupo AND m.rol = 'admin' AND m.estado = 'activa';
    ELSIF p_solicitado_por IS NOT NULL THEN
        IF p_solicitado_por = v_pagador OR EXISTS (
            SELECT 1 FROM public.membresia m WHERE m.grupo_id = v_grupo AND m.usuario_id = p_solicitado_por
               AND m.rol = 'admin' AND m.estado = 'activa') THEN
            v_solicitante := p_solicitado_por;
        END IF;
    ELSE
        v_solicitante := v_pagador;
    END IF;
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
    RETURN v_solicitante;
END $$;
REVOKE ALL ON FUNCTION operacion_solicitante_retracto(uuid, bytea, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION operacion_solicitante_retracto(uuid, bytea, uuid) TO matu_app;
"""

MEMBRESIAS_BAJADA = """
DROP FUNCTION operacion_solicitante_retracto(uuid, bytea, uuid);
DROP POLICY invitacion_conservacion_leer ON invitacion;
DROP POLICY invitacion_no_operacion ON invitacion;
DROP POLICY membresia_no_operacion ON membresia;
CREATE POLICY invitacion_operacion ON invitacion FOR SELECT USING (app_rol() = 'operacion');
CREATE POLICY membresia_operacion ON membresia FOR SELECT USING (app_rol() = 'operacion');
"""

AUDITORIA = f"""
-- (i) J2: el intento fallido del retracto por correo, con la persona del pedido
ALTER TABLE auditoria DROP CONSTRAINT auditoria_persona_obligatoria;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_persona_obligatoria
    CHECK (persona_cuidada_id IS NOT NULL OR accion NOT IN ({_lista(ACCIONES_DE_PERSONA_0031)})) NOT VALID;
"""

AUDITORIA_BAJADA = f"""
ALTER TABLE auditoria DROP CONSTRAINT auditoria_persona_obligatoria;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_persona_obligatoria
    CHECK (persona_cuidada_id IS NOT NULL OR accion NOT IN ({_lista(ACCIONES_DE_PERSONA_0030)})) NOT VALID;
"""

CODIGO = f"""
-- (j) C12 y C13: matu_app ya no lee la huella del código; la consola sabe si hay uno por codigo_vigente
ALTER TABLE pedido_comercio ADD COLUMN codigo_vigente boolean GENERATED ALWAYS AS (codigo_hash IS NOT NULL) STORED;
REVOKE SELECT ON pedido_comercio FROM matu_app;
GRANT SELECT ({COLUMNAS_PARTE}, codigo_vigente) ON pedido_comercio TO matu_app;
"""

# REVOKE de la tabla quita también los GRANT por columna
CODIGO_BAJADA = """
REVOKE SELECT ON pedido_comercio FROM matu_app;
GRANT SELECT ON pedido_comercio TO matu_app;
ALTER TABLE pedido_comercio DROP COLUMN codigo_vigente;
"""

CLAVE_NOTAS = """
-- (k) C16: la clave de las notas, solo para quienes piden «Datos de» (admin y cuidador activos)
ALTER POLICY clave_notas_familia_leer ON clave_notas USING (grupo_id = app_grupo() AND (SELECT app_escribe_plan()));
"""

CLAVE_NOTAS_BAJADA = """
ALTER POLICY clave_notas_familia_leer ON clave_notas USING (
    grupo_id = app_grupo()
    AND EXISTS (SELECT 1 FROM membresia m WHERE m.grupo_id = clave_notas.grupo_id AND m.usuario_id = app_usuario()
                   AND m.estado = 'activa'));
"""

UPGRADE = (
    CUENTAS
    + INCIDENCIA_REGLAS_0031
    + SESION_REFRESH_MFA_0031
    + BUSCAR_CUENTA_0031
    + MEMBRESIAS
    + AUDITORIA
    + CODIGO
    + CLAVE_NOTAS
)
DOWNGRADE = (
    CLAVE_NOTAS_BAJADA
    + CODIGO_BAJADA
    + AUDITORIA_BAJADA
    + MEMBRESIAS_BAJADA
    + BUSCAR_CUENTA_0030
    + SESION_REFRESH_MFA_0030
    + INCIDENCIA_REGLAS_0030
    + CUENTAS_BAJADA
)


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

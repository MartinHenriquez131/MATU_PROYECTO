"""MATU-124: cada tarea de conservación ve y borra solo con su propio marcador (Ley 21.719, seguridad).

Cadena: 0034 (MATU-79, parte 3) -> 0035. down_revision = "0034".

Revisión previa del analista normativo del 19-11 (hallazgos H1 a H8, condiciones C1 a C11) y decisiones del
orquestador D1 (el alcance completo de H1), D2 (un marcador por función en app.funcion, junto con app.rol; el rol
propio de la base para la conservación va a MATU-129), D3 (direccion_solo_familia) y D4 (sale app.conservacion).
backend/db/*.sql, la API y el contrato OpenAPI no cambian (C10).

El principio: una política TO matu_owner deja pasar a una sola función SECURITY DEFINER, la que fija su marcador
(app.funcion = '<su nombre>') antes de su primera lectura y al salir devuelve el valor con que entró (el patrón de la
0033, l). Antes, las de la conservación se fiaban solo de app.rol = 'operacion': cualquier otra definer de matu_owner
que corriera con operación (las del despacho, las de las cuentas, las de una migración futura) podía leer y borrar lo
que la conservación borra. El marcador lo fija matu_owner dentro de la función; matu_app que lo fija no gana nada,
porque las políticas son TO matu_owner (la prueba de catálogo lo verifica). Que el marcador sea infalsificable, con un
rol de la base propio de la conservación, queda en MATU-129, antes de datos reales.

a) C1 (H1): ALTER POLICY de cada política TO matu_owner que se fiaba solo del rol. Pasan a
   current_setting('app.funcion', true) = '<función>' AND app_rol() = 'operacion', sin cambiar el resto de su condición:
   - pedido_conservar: cargo_, participacion_, transaccion_, linea_, regla_, pedido_comercio_, transicion_ y
     pedido_conservacion_borrar, idempotencia_conservacion e idempotencia_conservacion_borrar; y las tres de la 0033 que
     miraban app.conservacion = 'pedidos' (entrega_conservacion_leer, entrega_conservacion_borrar y
     participacion_conservacion_leer).
   - consumo_conservar y plan_destruir_claves: consentimiento_conservacion, con IN de las dos.
   - iam_conservar: sesion_conservacion(_borrar) y dispositivo_conservacion(_borrar).
   - consumo_conservar: perfil_conservacion(_borrar).
   - quiebre_conservar: alerta_conservacion(_borrar), notificacion_conservacion(_borrar) y reposicion_conservacion
     (_borrar).
   - relevo_conservar: acceso_conservacion_leer y acceso_conservacion.
   - plan_destruir_claves: clave_destruccion(_leer), plan_destruccion(_leer) y seccion_destruccion(_leer).
   - pago_resolver_venta: pedido_resolver_pago, cargo_resolver_pago y transaccion_resolver_pago, con
     app_rol() = 'sistema' AND app_grupo() IS NULL como antes, y el marcador 'pago_resolver_venta'.
b) C2: las siete funciones (pedido_conservar, consumo_conservar, iam_conservar, quiebre_conservar, relevo_conservar,
   plan_destruir_claves y pago_resolver_venta) guardan v_antes, fijan su marcador después de validar los parámetros
   (que no leen tablas) y antes de su primera lectura, y lo devuelven al salir. pedido_conservar deja de usar
   app.conservacion (D4): ninguna política, función ni trigger lo mira desde aquí. pago_resolver_venta pasa de STABLE a
   VOLATILE, porque ahora cambia app.funcion con set_config.
c) C3 (H2): los triggers transaccion_borrado_acotado (transaccion_sin_borrado), transicion_solo_insercion y
   pedido_escritura_del_pago (la versión de la 0029) cambian app.conservacion = 'pedidos' por
   app.funcion = 'pedido_conservar', siempre con current_user = 'matu_owner'.
d) C4: participacion_solicitante_leer, invitacion_conservacion_leer e invitacion_conservacion_borrar suman
   app_rol() = 'operacion' (las dos funciones que las usan ya lo exigen). usuario_aviso_correo (H6) suma
   app_rol() = 'sistema', sin cuenta, con grupo y con la membresía activa de la cuenta en ese grupo, lo mismo que
   aviso_correo ya exigía en su cuerpo.
e) C5 (H5): operacion_solicitante_retracto fija 'solicitante_retracto' antes de leer el pedido (antes lo leía con el
   marcador de quien la llamaba) y lo devuelve también en la salida temprana. app_pago_el_pedido fija 'pago_propio'
   antes de leer la membresía, y conserva su chequeo de v_antes = 'pago_propio' (responde false sin leer).
f) C6 (D3): sale direccion_no_operacion (restrictiva, SELECT, TO matu_app). Entra direccion_solo_familia, restrictiva,
   FOR ALL, TO matu_app, con app_rol() = 'ninguno' AND app_usuario() IS NOT NULL en USING y en WITH CHECK: la dirección
   la lee y la escribe solo una sesión de familia, con una cuenta y sin rol de contexto. Antes, el sistema con el grupo
   en el contexto la leía por direccion_familia_leer.
g) C7 (H8): VOLATILE en las definer que cambian app.funcion con set_config y eran STABLE: operacion_cuenta_activa,
   cuenta_es_operacion y operacion_buscar_cuenta (0031), y app_pago_el_pedido, cuenta_pagos, cuenta_retractos y
   cuenta_condiciones (0032). Una función STABLE no debe cambiar la configuración. El EXPLAIN de las lecturas de la
   familia que pasan por app_pago_el_pedido, antes y después, va en el PR: los mismos planes y los mismos índices, con
   los costos entre 0,1 y 0,3 % más altos.

Recorrido (C9): quién usa cada cambio y por qué no se rompe
- Las tareas (app/tareas.py): como matu_scheduler, con sesion_tenant(rol="operacion") y sin app.funcion, llaman a
  plan_destruir_claves, consumo_conservar, iam_conservar, quiebre_conservar, pedido_conservar, invitacion_conservar y
  relevo_conservar (tarea_destruccion.py, consumption/infrastructure/tarea_conservacion.py y tarea_quiebres.py,
  iam/infrastructure/tarea_conservacion.py, ordering/infrastructure/tarea_conservacion.py,
  tarea_conservacion_invitaciones.py y tarea_conservacion_relevo.py). Cada función fija su marcador adentro: ninguna
  tarea cambia. Nadie en la aplicación fijaba app.conservacion (grep en backend/app e infra).
- outbox_sql.py: matu_publisher con rol="operacion" llama a outbox_tomar, outbox_publicado, outbox_posponer y
  outbox_reintentar, que no leen tablas con RLS (evento_outbox no tiene) ni miran un marcador: no cambian.
- payments/infrastructure/sistema.py: matu_app con rol="sistema" y sin grupo ni cuenta llama a pago_resolver_venta;
  la función fija su marcador y las tres *_resolver_pago lo exigen.
- backoffice/api/router_operacion.py (_SOLICITANTE): operacion_solicitante_retracto, con la cuenta de operación.
  Las políticas de lectura de familia (cargo_familia_leer, participacion_familia_leer, transaccion_familia_leer,
  retracto_familia_leer y retracto_linea_familia_leer) llaman a app_pago_el_pedido; responde lo mismo.
- notifications/infrastructure/repositorio_avisos.py: aviso_correo(:usuario) con sesion_tenant(grupo_id,
  rol='sistema') y sin cuenta, solo para un miembro activo: pasa la condición nueva de usuario_aviso_correo.
- La dirección: la leen y la escriben solo rutas de familia con sesion_de_grupo (cuenta y grupo, sin app.rol):
  care_circle/infrastructure/repositorio_direccion.py, repositorio_personas.py, repositorio_borrado.py (MATU-72) y
  copia_datos.py, y ordering/infrastructure/repositorio_pedidos.py (la dirección de la entrega al confirmar).
  Ninguna ruta del sistema ni de operación la lee (MATU-122).
- La semilla (infra/semillas/demo.py) y --restablecer (MATU-72): crean y restablecen las personas y su dirección con
  sesion_tenant(usuario_id=..., grupo_id=...) del admin de cada familia, sin app.rol: pasan direccion_solo_familia.
  cuenta_comercio corre con rol="operacion" sobre usuario_comercio, que no cambia. Ninguna llama a una función de
  conservación ni fija app.conservacion. catalogo_demo.py escribe el catálogo como operación: no cambia.
- Las pruebas que entran como como(cx, "matu_owner", rol="operacion") (test_aislamiento.py): las de MATU-122
  (participaciones e invitaciones) siguen dando 0; la de la clave de notas que destruye clave_datos como matu_owner
  fija ahora el marcador 'plan_destruir_claves', el de la función que hace eso en producción.

downgrade() deja el catálogo igual al de la 0034 (C8): las políticas con su condición de antes, direccion_no_operacion
de vuelta, las funciones con su cuerpo y su volatilidad de antes y los triggers con app.conservacion. No borra filas.

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


DEFINER = "SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp"
OPERACION = "(app_rol() = 'operacion'::text)"
SIN_GRUPO = "(app_rol() = 'sistema'::text) AND (app_grupo() IS NULL)"
CONSERVACION_0033 = (
    "(app_rol() = 'operacion'::text) AND (current_setting('app.conservacion'::text, true) = 'pedidos'::text)"
)


def _marca(*funciones: str) -> str:
    if len(funciones) == 1:
        return f"(current_setting('app.funcion', true) = '{funciones[0]}')"
    return f"(current_setting('app.funcion', true) IN ({', '.join(repr(f) for f in funciones)}))"


# (a) y (d): (tabla, política, función o funciones del marcador, USING de la 0034, WITH CHECK de la 0034, lo que se
# suma además del marcador). Las condiciones de la 0034 van como las devuelve pg_policies, para que la bajada quede
# letra por letra; en la subida se conservan detrás del marcador (C1), salvo app.conservacion, que sale (D4).
POLITICAS: list[tuple[str, str, tuple[str, ...], str, str | None]] = [
    # pedido_conservar (0023, 0024 y 0033)
    ("cargo", "cargo_conservacion_borrar", ("pedido_conservar",),
     "(app_rol() = 'operacion'::text) AND (estado = ANY (ARRAY['pendiente'::text, 'rechazado'::text]))"
     " AND (monto_cobrado = 0)", None),
    ("participacion", "participacion_conservacion_borrar", ("pedido_conservar",),
     "(app_rol() = 'operacion'::text) AND (estado = ANY (ARRAY['pendiente'::text, 'rechazada'::text]))"
     " AND (monto_cobrado = 0)", None),
    ("participacion", "participacion_conservacion_leer", ("pedido_conservar",), CONSERVACION_0033, None),
    ("transaccion_pasarela", "transaccion_conservacion_borrar", ("pedido_conservar",),
     "(app_rol() = 'operacion'::text) AND (estado <> ALL (ARRAY['aprobada'::text, 'autorizando'::text]))", None),
    ("pedido_linea", "linea_conservacion_borrar", ("pedido_conservar",), OPERACION, None),
    ("regla_sustitucion", "regla_conservacion_borrar", ("pedido_conservar",), OPERACION, None),
    ("pedido_comercio", "pedido_comercio_conservacion_borrar", ("pedido_conservar",), OPERACION, None),
    ("pedido_transicion", "transicion_conservacion_borrar", ("pedido_conservar",), OPERACION, None),
    ("pedido", "pedido_conservacion_borrar", ("pedido_conservar",),
     "(app_rol() = 'operacion'::text) AND (pagado_en IS NULL)", None),
    ("idempotencia", "idempotencia_conservacion", ("pedido_conservar",), OPERACION, None),
    ("idempotencia", "idempotencia_conservacion_borrar", ("pedido_conservar",), OPERACION, None),
    ("pedido_entrega", "entrega_conservacion_leer", ("pedido_conservar",), CONSERVACION_0033, None),
    ("pedido_entrega", "entrega_conservacion_borrar", ("pedido_conservar",), CONSERVACION_0033, None),
    # El consentimiento (0030): lo leen las dos que deciden por el retiro
    ("consentimiento", "consentimiento_conservacion", ("plan_destruir_claves", "consumo_conservar"), OPERACION, None),
    # iam_conservar (0008)
    ("sesion_refresh", "sesion_conservacion", ("iam_conservar",), OPERACION, None),
    ("sesion_refresh", "sesion_conservacion_borrar", ("iam_conservar",), OPERACION, None),
    ("dispositivo", "dispositivo_conservacion", ("iam_conservar",), OPERACION, None),
    ("dispositivo", "dispositivo_conservacion_borrar", ("iam_conservar",), OPERACION, None),
    # consumo_conservar (0009)
    ("perfil_consumo", "perfil_conservacion", ("consumo_conservar",), OPERACION, None),
    ("perfil_consumo", "perfil_conservacion_borrar", ("consumo_conservar",), OPERACION, None),
    # quiebre_conservar (0011, 0017 y 0022)
    ("alerta_quiebre", "alerta_conservacion", ("quiebre_conservar",), OPERACION, None),
    ("alerta_quiebre", "alerta_conservacion_borrar", ("quiebre_conservar",), OPERACION, None),
    ("notificacion", "notificacion_conservacion", ("quiebre_conservar",), OPERACION, None),
    ("notificacion", "notificacion_conservacion_borrar", ("quiebre_conservar",), OPERACION, None),
    ("reposicion", "reposicion_conservacion", ("quiebre_conservar",), OPERACION, None),
    ("reposicion", "reposicion_conservacion_borrar", ("quiebre_conservar",), OPERACION, None),
    # relevo_conservar (0027)
    ("acceso_relevo", "acceso_conservacion_leer", ("relevo_conservar",), OPERACION, None),
    ("acceso_relevo", "acceso_conservacion", ("relevo_conservar",), OPERACION,
     "(app_rol() = 'operacion'::text) AND (otorgado_a_telefono IS NULL)"),
    # plan_destruir_claves (0016)
    ("clave_datos", "clave_destruccion_leer", ("plan_destruir_claves",), OPERACION, None),
    ("clave_datos", "clave_destruccion", ("plan_destruir_claves",), OPERACION,
     "(app_rol() = 'operacion'::text) AND (dek_cifrada_con_kek IS NULL)"),
    ("plan_cuidado", "plan_destruccion_leer", ("plan_destruir_claves",), OPERACION, None),
    ("plan_cuidado", "plan_destruccion", ("plan_destruir_claves",), OPERACION,
     "(app_rol() = 'operacion'::text) AND (completitud_pct = 0)"),
    ("plan_seccion", "seccion_destruccion_leer", ("plan_destruir_claves",), OPERACION, None),
    ("plan_seccion", "seccion_destruccion", ("plan_destruir_claves",), OPERACION, None),
    # pago_resolver_venta (0024), con el sistema y sin grupo
    ("pedido", "pedido_resolver_pago", ("pago_resolver_venta",), SIN_GRUPO, None),
    ("cargo", "cargo_resolver_pago", ("pago_resolver_venta",), SIN_GRUPO, None),
    ("transaccion_pasarela", "transaccion_resolver_pago", ("pago_resolver_venta",), SIN_GRUPO, None),
    # (d) C4: las que ya miraban su marcador y suman el rol
    ("participacion", "participacion_solicitante_leer", ("solicitante_retracto",), "", None),
    ("invitacion", "invitacion_conservacion_leer", ("invitacion_conservar",), "", None),
    ("invitacion", "invitacion_conservacion_borrar", ("invitacion_conservar",), "", None),
]
# (d) C4: lo que suman las que ya miraban su marcador (en la 0034, solo el marcador)
SUMAN = {
    "participacion_solicitante_leer": OPERACION,
    "invitacion_conservacion_leer": OPERACION,
    "invitacion_conservacion_borrar": OPERACION,
}


def _subida(condicion: str) -> str:
    """La condición de la 0034 sin app.conservacion: el marcador de la función la reemplaza (D4)."""
    return OPERACION if condicion == CONSERVACION_0033 else condicion


def _politicas(subir: bool) -> str:
    sentencias = []
    for tabla, nombre, funciones, usando, chequeo in POLITICAS:
        if subir:
            resto = SUMAN.get(nombre) or _subida(usando)
            nuevo = f"{_marca(*funciones)} AND {resto}"
            con = f" WITH CHECK ({_marca(*funciones)} AND {chequeo})" if chequeo else ""
            sentencias.append(f"ALTER POLICY {nombre} ON {tabla} USING ({nuevo}){con};")
        else:
            viejo = usando or _marca(*funciones)
            con = f" WITH CHECK ({chequeo})" if chequeo else ""
            sentencias.append(f"ALTER POLICY {nombre} ON {tabla} USING ({viejo}){con};")
    return "\n".join(sentencias) + "\n"


# (d) H6: el correo de un miembro activo del grupo del contexto, solo al sistema sin cuenta
AVISO_CORREO_0034 = _marca("aviso_correo")
AVISO_CORREO_0035 = (
    f"{AVISO_CORREO_0034} AND app_rol() = 'sistema' AND app_usuario() IS NULL AND app_grupo() IS NOT NULL"
    " AND EXISTS (SELECT 1 FROM membresia m WHERE m.usuario_id = usuario.id AND m.grupo_id = app_grupo()"
    " AND m.estado = 'activa')"
)
AVISOS = f"ALTER POLICY usuario_aviso_correo ON usuario USING ({AVISO_CORREO_0035});\n"
AVISOS_BAJADA = f"ALTER POLICY usuario_aviso_correo ON usuario USING ({AVISO_CORREO_0034});\n"

# (f) C6 y D3: la dirección, solo para una sesión de familia
FAMILIA = "app_rol() = 'ninguno' AND app_usuario() IS NOT NULL"
DIRECCION = f"""
DROP POLICY direccion_no_operacion ON direccion;
CREATE POLICY direccion_solo_familia ON direccion AS RESTRICTIVE FOR ALL TO matu_app
    USING ({FAMILIA}) WITH CHECK ({FAMILIA});
"""
DIRECCION_BAJADA = """
DROP POLICY direccion_solo_familia ON direccion;
CREATE POLICY direccion_no_operacion ON direccion AS RESTRICTIVE FOR SELECT TO matu_app
    USING (app_rol() IS DISTINCT FROM 'operacion');
"""

# (b) El marcador de cada función: el valor con que se entra, el propio antes de leer y el anterior al salir
ANTES = "    v_antes text := current_setting('app.funcion', true);\n"
DEVOLVER = "    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);\n"


def _marcar(funcion: str) -> str:
    return f"    PERFORM set_config('app.funcion', '{funcion}', true);\n"


def _cuerpo(plantilla: str, funcion: str | None) -> str:
    """Con funcion, la versión de la 0035; sin ella, la de la 0034, igual letra por letra."""
    return (
        plantilla.replace("{ANTES}", ANTES if funcion else "")
        .replace("{DECLARE}", "DECLARE\n" + ANTES if funcion else "")
        .replace("{MARCAR}", _marcar(funcion) if funcion else "")
        .replace("{DEVOLVER}", DEVOLVER if funcion else "")
    )


CONSUMO = f"""
CREATE OR REPLACE FUNCTION consumo_conservar(limite timestamptz, ahora timestamptz) RETURNS integer
    LANGUAGE plpgsql VOLATILE {DEFINER} AS
$$
DECLARE
    n integer := 0;
{{ANTES}}BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'consumo_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '90 days' THEN
        RAISE EXCEPTION 'el consumo se conserva 90 días' USING ERRCODE = 'invalid_parameter_value';
    END IF;
{{MARCAR}}
    DELETE FROM public.perfil_consumo p
     WHERE NOT EXISTS (
               SELECT 1 FROM public.consentimiento c
                WHERE c.persona_cuidada_id = p.persona_cuidada_id AND c.finalidad = 'consumo'
                  AND c.revocado_en IS NULL)
       AND (SELECT max(c.revocado_en) FROM public.consentimiento c
             WHERE c.persona_cuidada_id = p.persona_cuidada_id AND c.finalidad = 'consumo') <= limite;
    GET DIAGNOSTICS n = ROW_COUNT;
{{DEVOLVER}}    RETURN n;
END
$$;
"""

IAM = f"""
CREATE OR REPLACE FUNCTION iam_conservar(limite_sesion timestamptz, limite_dispositivo timestamptz,
                                         ahora timestamptz)
    RETURNS TABLE (sesiones_borradas integer, dispositivos_borrados integer)
    LANGUAGE plpgsql VOLATILE {DEFINER} AS
$$
DECLARE
    n_sesiones integer := 0;
    n_extra integer := 0;
    n_dispositivos integer := 0;
    borrables uuid[];
{{ANTES}}BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'iam_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF NOT (limite_sesion <= ahora AND limite_dispositivo <= ahora) THEN
        RAISE EXCEPTION 'los límites deben ser anteriores a ahora' USING ERRCODE = 'invalid_parameter_value';
    END IF;
{{MARCAR}}
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
    SELECT coalesce(array_agg(d.id), '{{}}') INTO borrables FROM public.dispositivo d
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
{{DEVOLVER}}
    RETURN QUERY SELECT n_sesiones + n_extra, n_dispositivos;
END
$$;
"""

QUIEBRE = f"""
CREATE OR REPLACE FUNCTION quiebre_conservar(limite_alertas timestamptz, limite_eventos timestamptz,
                                             ahora timestamptz)
    RETURNS TABLE (alertas integer, eventos integer, notificaciones integer, reposiciones integer)
    LANGUAGE plpgsql VOLATILE {DEFINER} AS
$$
{{DECLARE}}BEGIN
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
{{MARCAR}}
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
    -- MATU-51 (decisión A de Jorge, 145): las compras declaradas a los 90 días de registrada_en. Las de
    -- pedido_matu siguen mientras exista el perfil
    DELETE FROM public.reposicion WHERE origen = 'declarada' AND registrada_en <= limite_alertas;
    GET DIAGNOSTICS reposiciones = ROW_COUNT;
{{DEVOLVER}}    RETURN NEXT;
END
$$;
"""

RELEVO = f"""
CREATE OR REPLACE FUNCTION relevo_conservar(limite timestamptz, ahora timestamptz) RETURNS integer
    LANGUAGE plpgsql VOLATILE {DEFINER} AS
$$
DECLARE
    borrados integer;
{{ANTES}}BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'relevo_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '30 days' THEN
        RAISE EXCEPTION 'el teléfono del relevo se conserva 30 días' USING ERRCODE = 'invalid_parameter_value';
    END IF;
{{MARCAR}}    -- LEAST ignora el nulo: sin corte, cuenta el vencimiento. Un acceso bloqueado o en pausa, también
    UPDATE public.acceso_relevo a SET otorgado_a_telefono = NULL, telefono_borrado_en = ahora
     WHERE a.otorgado_a_telefono IS NOT NULL AND LEAST(a.expira_en, a.revocado_en) <= limite;
    GET DIAGNOSTICS borrados = ROW_COUNT;
{{DEVOLVER}}    RETURN borrados;
END
$$;
"""

# Dos líneas de la 0016 de más de 120 caracteres, igual letra por letra
AUDITORIA_DESTRUIR = (
    "    INSERT INTO public.auditoria (grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id, ocurrido_en,"
    " persona_cuidada_id)\n    SELECT d.grupo_id, 'sistema', NULL, 'clave.destruir', 'clave_datos', d.id, ahora,"
    " d.persona_cuidada_id FROM destruidas d;"
)
PLAN = f"""
CREATE OR REPLACE FUNCTION plan_destruir_claves(limite timestamptz, ahora timestamptz) RETURNS integer
    LANGUAGE plpgsql VOLATILE {DEFINER} AS
$$
DECLARE
    n integer := 0;
{{ANTES}}BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'plan_destruir_claves exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '90 days' THEN
        RAISE EXCEPTION 'la ficha se conserva 90 días después del retiro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
{{MARCAR}}
    WITH destruidas AS (
        UPDATE public.clave_datos k SET dek_cifrada_con_kek = NULL, destruida_en = ahora
         WHERE k.destruida_en IS NULL
           AND NOT EXISTS (
                   SELECT 1 FROM public.consentimiento c
                    WHERE c.persona_cuidada_id = k.persona_cuidada_id AND c.finalidad = 'plan_cuidado'
                      AND c.revocado_en IS NULL)
           AND (SELECT max(c.revocado_en) FROM public.consentimiento c
                 WHERE c.persona_cuidada_id = k.persona_cuidada_id AND c.finalidad = 'plan_cuidado') <= limite
        RETURNING k.id, k.grupo_id, k.persona_cuidada_id),
    -- CL-6: lo cifrado con la clave destruida no se queda en la base, ni sus metadatos
    borradas AS (
        DELETE FROM public.plan_seccion s USING public.plan_cuidado p, destruidas d
         WHERE s.plan_id = p.id AND p.persona_cuidada_id = d.persona_cuidada_id
        RETURNING s.id),
    en_blanco AS (
        UPDATE public.plan_cuidado p SET completitud_pct = 0, actualizado_en = ahora
          FROM destruidas d WHERE p.persona_cuidada_id = d.persona_cuidada_id
        RETURNING p.id)
{AUDITORIA_DESTRUIR}
    GET DIAGNOSTICS n = ROW_COUNT;
{{DEVOLVER}}    RETURN n;
END
$$;
"""

# pago_resolver_venta: además, STABLE en la 0034 y VOLATILE en la 0035 (cambia app.funcion)
RESOLVER = f"""
CREATE OR REPLACE FUNCTION pago_resolver_venta(p_token text, p_orden text, p_sesion text)
    RETURNS TABLE (transaccion_id uuid, grupo_id uuid)
    LANGUAGE plpgsql {{VOLATILIDAD}} {DEFINER} AS
$$
{{DECLARE}}BEGIN
    IF public.app_rol() IS DISTINCT FROM 'sistema' OR public.app_grupo() IS NOT NULL
       OR public.app_usuario() IS NOT NULL THEN
        RAISE EXCEPTION 'pago_resolver_venta exige app.rol = sistema, sin grupo ni cuenta'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
{{MARCAR}}    IF p_token IS NOT NULL THEN
        RETURN QUERY
            SELECT t.id, p.grupo_id FROM public.transaccion_pasarela t
              JOIN public.cargo c ON c.id = t.cargo_id JOIN public.pedido p ON p.id = c.pedido_id
             WHERE t.tipo = 'venta' AND t.token = p_token;
    ELSIF p_orden IS NOT NULL AND p_sesion IS NOT NULL THEN
        RETURN QUERY
            SELECT t.id, p.grupo_id FROM public.transaccion_pasarela t
              JOIN public.cargo c ON c.id = t.cargo_id JOIN public.pedido p ON p.id = c.pedido_id
             WHERE t.tipo = 'venta' AND t.buy_order = p_orden AND t.session_id = p_sesion;
    END IF;
{{DEVOLVER}}END $$;
"""

# pedido_conservar (la de la 0024): lo no pagado vencido del plazo, con dinero o sin él
VIEJO = (
    "p.pagado_en IS NULL AND p.estado IN ('borrador', 'total_confirmado', 'vencido', 'cancelado')"
    " AND GREATEST(p.actualizado_en, COALESCE(p.total_vence_en, p.actualizado_en)) <= limite"
)
CON_DINERO = (
    "EXISTS (SELECT 1 FROM public.cargo c JOIN public.transaccion_pasarela t ON t.cargo_id = c.id"
    " WHERE c.pedido_id = p.id AND t.tipo = 'venta' AND t.estado IN ('aprobada', 'autorizando'))"
)
PEDIDOS = f"""
CREATE OR REPLACE FUNCTION pedido_conservar(limite timestamptz, ahora timestamptz)
    RETURNS TABLE (pedidos integer, idempotencias integer)
    LANGUAGE plpgsql VOLATILE {DEFINER} AS
$$
{{DECLARE}}BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'pedido_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '30 days' THEN
        RAISE EXCEPTION 'lo no pagado se conserva 30 días' USING ERRCODE = 'invalid_parameter_value';
    END IF;
{{ENTRAR}}    -- D-62-13 (c), sin dinero: el intento que no se cobró se va con su pedido
    DELETE FROM public.idempotencia i USING public.pedido p
     WHERE i.pedido_id = p.id AND {VIEJO} AND NOT {CON_DINERO};
    DELETE FROM public.transaccion_pasarela t USING public.cargo c, public.pedido p
     WHERE t.cargo_id = c.id AND c.pedido_id = p.id AND {VIEJO} AND NOT {CON_DINERO};
    DELETE FROM public.participacion pa USING public.cargo c, public.pedido p
     WHERE pa.cargo_id = c.id AND c.pedido_id = p.id AND {VIEJO} AND NOT {CON_DINERO};
    DELETE FROM public.cargo c USING public.pedido p WHERE c.pedido_id = p.id AND {VIEJO} AND NOT {CON_DINERO};
    -- C10: lo no pagado, desde su último cambio o desde que venció su total
    DELETE FROM public.pedido p WHERE {VIEJO}
       AND NOT EXISTS (SELECT 1 FROM public.cargo c WHERE c.pedido_id = p.id);
    GET DIAGNOSTICS pedidos = ROW_COUNT;
    -- D-62-13 (c), con dinero: se conservan el pedido sin entrega, el cargo y las transacciones; lo demás se borra
    DELETE FROM public.pedido_transicion x USING public.pedido p WHERE x.pedido_id = p.id AND {VIEJO} AND {CON_DINERO};
    DELETE FROM public.regla_sustitucion r USING public.pedido p WHERE r.pedido_id = p.id AND {VIEJO} AND {CON_DINERO};
    DELETE FROM public.pedido_linea l USING public.pedido p WHERE l.pedido_id = p.id AND {VIEJO} AND {CON_DINERO};
    DELETE FROM public.pedido_comercio pc USING public.pedido p
     WHERE pc.pedido_id = p.id AND {VIEJO} AND {CON_DINERO};
    DELETE FROM public.pedido_entrega e USING public.pedido p WHERE e.pedido_id = p.id AND {VIEJO} AND {CON_DINERO};
    -- Observación 5: el pedido abierto que quedó sin líneas no sigue como el pedido sin pagar de la persona (C4)
    UPDATE public.pedido p SET estado = 'cancelado'
     WHERE {VIEJO} AND {CON_DINERO} AND p.estado IN ('borrador', 'total_confirmado', 'vencido')
       AND NOT EXISTS (SELECT 1 FROM public.pedido_linea l WHERE l.pedido_id = p.id);
    DELETE FROM public.idempotencia i USING public.pedido p WHERE i.pedido_id = p.id AND {VIEJO} AND {CON_DINERO};
    DELETE FROM public.idempotencia WHERE expira_en <= ahora;
    GET DIAGNOSTICS idempotencias = ROW_COUNT;
{{SALIR}}    RETURN NEXT;
END $$;
"""
# D4: la 0024 fijaba app.conservacion = 'pedidos' y al salir lo dejaba vacío
PEDIDOS_0034 = (
    PEDIDOS.replace("{DECLARE}", "")
    .replace("{ENTRAR}", "    PERFORM set_config('app.conservacion', 'pedidos', true);\n")
    .replace("{SALIR}", "    PERFORM set_config('app.conservacion', '', true);\n")
)
PEDIDOS_0035 = (
    PEDIDOS.replace("{DECLARE}", "DECLARE\n" + ANTES)
    .replace("{ENTRAR}", _marcar("pedido_conservar"))
    .replace("{SALIR}", DEVOLVER)
)

# (c) C3: los triggers que dejan borrar el registro contable y la línea de tiempo, y cancelar el pedido vacío, solo
# dentro de pedido_conservar
MARCA_TRIGGER_0034 = "current_setting('app.conservacion', true) = 'pedidos'"
MARCA_TRIGGER_0035 = "current_setting('app.funcion', true) = 'pedido_conservar'"
TRIGGERS = """
CREATE OR REPLACE FUNCTION transaccion_borrado_acotado() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF current_user = 'matu_owner' AND {MARCA}
       AND OLD.estado NOT IN ('aprobada', 'autorizando') THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'el registro contable de la pasarela no se borra' USING ERRCODE = 'insufficient_privilege';
END $$;

CREATE OR REPLACE FUNCTION transicion_solo_insercion() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    -- En la cascada del borrado de su pedido (pedido_conservar): el pedido ya no está
    IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1
       AND NOT EXISTS (SELECT 1 FROM pedido p WHERE p.id = OLD.pedido_id) THEN
        RETURN OLD;
    END IF;
    -- D-62-13: la de un pedido con dinero que nunca quedó pagado, dentro de pedido_conservar
    IF TG_OP = 'DELETE' AND current_user = 'matu_owner' AND {MARCA}
       AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = OLD.pedido_id AND p.pagado_en IS NULL) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'tabla de solo inserción' USING ERRCODE = 'insufficient_privilege';
END $$;
"""

# La de la 0029 (ESCRITURA_0029), con el marcador en {MARCA}
TRANSICIONES_DESPACHO = (
    "('pagado', 'enviado_a_comercio'), ('pagado', 'cancelado_con_devolucion'),"
    " ('enviado_a_comercio', 'preparando'), ('enviado_a_comercio', 'cancelado_con_devolucion'),"
    " ('preparando', 'listo_retiro'), ('preparando', 'cancelado_con_devolucion'), ('listo_retiro', 'retirado'),"
    " ('retirado', 'en_ruta'), ('en_ruta', 'entregado'), ('en_ruta', 'no_entregado'), ('entregado', 'cerrado'),"
    " ('no_entregado', 'reprogramado'), ('no_entregado', 'cancelado_con_devolucion'), ('reprogramado', 'en_ruta')"
)
ESCRITURA = """
CREATE OR REPLACE FUNCTION pedido_escritura_del_pago() RETURNS trigger LANGUAGE plpgsql AS
$$
DECLARE
    resto public.pedido%ROWTYPE;
    acotado boolean := app_rol() IN ('sistema', 'operacion') AND app_usuario() IS NULL;
BEGIN
    -- Observación 5: dentro de pedido_conservar, un pedido abierto con dinero que quedó sin líneas pasa a cancelado,
    -- y nada más cambia
    IF current_user = 'matu_owner' AND {MARCA}
       AND OLD.pagado_en IS NULL AND OLD.estado IN ('borrador', 'total_confirmado', 'vencido')
       AND NEW.estado = 'cancelado' THEN
        resto := NEW;
        resto.estado := OLD.estado;
        resto.actualizado_en := OLD.actualizado_en;
        IF resto IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'la conservación solo cancela el pedido vacío' USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    -- MATU-63 (0029): después del pago, el pedido lo mueven solo el sistema y operación, sin una cuenta, por las
    -- transiciones del despacho. Nadie más cambia nada de un pedido pagado
    IF OLD.pagado_en IS NOT NULL THEN
        resto := NEW;
        resto.actualizado_en := OLD.actualizado_en;
        IF NOT acotado THEN
            IF resto IS DISTINCT FROM OLD THEN
                RAISE EXCEPTION 'el pedido pagado lo mueve solo el sistema' USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END IF;
        resto.estado := OLD.estado;
        resto.entregado_en := OLD.entregado_en;
        IF resto IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'después del pago el sistema solo cambia el estado' USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.estado IS DISTINCT FROM OLD.estado AND (OLD.estado, NEW.estado) NOT IN ({TRANSICIONES}) THEN
            RAISE EXCEPTION 'el pedido no pasa de ese estado a ese otro' USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.entregado_en IS DISTINCT FROM OLD.entregado_en
           AND (OLD.entregado_en IS NOT NULL OR NEW.estado <> 'entregado') THEN
            RAISE EXCEPTION 'entregado_en se fija una vez, al entregar' USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    -- R5: con el pago, lo aceptado y la referencia quedan fijos
    IF OLD.pagado_en IS NOT NULL AND (NEW.condiciones_version, NEW.condiciones_aceptadas_en, NEW.condiciones_huella,
        NEW.condiciones_aceptadas_por, NEW.referencia) IS DISTINCT FROM (OLD.condiciones_version,
        OLD.condiciones_aceptadas_en, OLD.condiciones_huella, OLD.condiciones_aceptadas_por, OLD.referencia) THEN
        RAISE EXCEPTION 'el pedido ya está pagado: las condiciones aceptadas quedan fijas'
            USING ERRCODE = 'check_violation';
    END IF;
    -- D-62-4: marca el pago solo el sistema u operación, con la venta aprobada del mismo total
    IF OLD.pagado_en IS NULL AND NEW.pagado_en IS NOT NULL THEN
        IF NOT acotado THEN
            RAISE EXCEPTION 'solo el sistema marca un pedido pagado' USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.estado NOT IN ('total_confirmado', 'vencido') OR NEW.estado <> 'pagado' THEN
            RAISE EXCEPTION 'se paga un total confirmado o vencido' USING ERRCODE = 'check_violation';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM transaccion_pasarela t JOIN cargo c ON c.id = t.cargo_id
                        WHERE c.pedido_id = NEW.id AND t.tipo = 'venta' AND t.estado = 'aprobada'
                          AND NOT t.anulacion_total AND t.monto = NEW.total
                          AND t.total_confirmado_en = NEW.total_confirmado_en) THEN
            RAISE EXCEPTION 'el pago es de una venta aprobada del mismo total' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF NEW.referencia IS DISTINCT FROM OLD.referencia AND NOT acotado THEN
        RAISE EXCEPTION 'la referencia la asigna el sistema' USING ERRCODE = 'check_violation';
    END IF;
    -- D-62-16: las condiciones las acepta la cuenta que toca «Pagar», nunca otra
    IF NEW.condiciones_aceptadas_por IS DISTINCT FROM OLD.condiciones_aceptadas_por
       AND NEW.condiciones_aceptadas_por IS NOT NULL AND app_usuario() IS NOT NULL
       AND NEW.condiciones_aceptadas_por <> app_usuario() THEN
        RAISE EXCEPTION 'las condiciones las acepta quien paga' USING ERRCODE = 'check_violation';
    END IF;
    resto := NEW;
    resto.actualizado_en := OLD.actualizado_en;
    IF acotado THEN
        -- El sistema y operación, sin una cuenta: solo el pago
        resto.estado := OLD.estado;
        resto.pagado_en := OLD.pagado_en;
        resto.referencia := OLD.referencia;
        IF resto IS DISTINCT FROM OLD
           OR (NEW.estado IS DISTINCT FROM OLD.estado
               AND NOT (OLD.pagado_en IS NULL AND NEW.pagado_en IS NOT NULL)) THEN
            RAISE EXCEPTION 'el sistema solo marca el pago' USING ERRCODE = 'check_violation';
        END IF;
    ELSIF app_usuario() IS NOT NULL AND app_comercio() IS NULL AND app_repartidor() IS NULL
          AND NOT app_escribe_pedido() THEN
        -- Quien paga y no arma el pedido: solo acepta las condiciones (D-62-16)
        resto.condiciones_version := OLD.condiciones_version;
        resto.condiciones_aceptadas_en := OLD.condiciones_aceptadas_en;
        resto.condiciones_huella := OLD.condiciones_huella;
        resto.condiciones_aceptadas_por := OLD.condiciones_aceptadas_por;
        IF resto IS DISTINCT FROM OLD THEN
            RAISE EXCEPTION 'quien paga solo acepta las condiciones' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
""".replace("{TRANSICIONES}", TRANSICIONES_DESPACHO)


def _triggers(marca: str) -> str:
    return TRIGGERS.replace("{MARCA}", marca) + ESCRITURA.replace("{MARCA}", marca)


# (e) C5 (H5): operacion_solicitante_retracto. La de la 0033 leía el pedido con el marcador de quien la llamaba
QUIEN_PAGO = (
    "    SELECT pa.usuario_id INTO v_pagador FROM public.participacion pa JOIN public.cargo c ON c.id = pa.cargo_id"
)
SOLICITANTE = f"""
CREATE OR REPLACE FUNCTION operacion_solicitante_retracto(p_pedido uuid, p_email_hash bytea, p_solicitado_por uuid)
    RETURNS uuid
    LANGUAGE plpgsql VOLATILE {DEFINER} AS
$$
DECLARE
    v_antes text := current_setting('app.funcion', true);
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
{{PEDIDO}}    -- Quien pagó: la primera participación con un cobro (como _QUIEN_PAGO desde MATU-63)
{{PAGADOR}}{QUIEN_PAGO}
     WHERE c.pedido_id = p_pedido AND pa.monto_cobrado > 0 ORDER BY pa.id LIMIT 1;
    PERFORM set_config('app.funcion', 'cuentas', true);
    IF p_email_hash IS NOT NULL THEN
        SELECT i.usuario_id INTO v_solicitante FROM public.indice_credencial i
         WHERE i.email_hash = p_email_hash
           AND (i.usuario_id = v_pagador OR EXISTS (
                SELECT 1 FROM public.membresia m WHERE m.usuario_id = i.usuario_id AND m.grupo_id = v_grupo
                   AND m.rol = 'admin' AND m.estado = 'activa'));
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
"""
LEER_PEDIDO = "    SELECT p.grupo_id INTO v_grupo FROM public.pedido p WHERE p.id = p_pedido;\n"
SOLICITANTE_0034 = SOLICITANTE.replace(
    "{PEDIDO}", LEER_PEDIDO + "    IF v_grupo IS NULL THEN\n        RETURN NULL;\n    END IF;\n").replace(
    "{PAGADOR}", _marcar("solicitante_retracto"))
SOLICITANTE_0035 = SOLICITANTE.replace(
    "{PEDIDO}", _marcar("solicitante_retracto") + LEER_PEDIDO
    + "    IF v_grupo IS NULL THEN\n" + DEVOLVER.replace("    ", "        ", 1) + "        RETURN NULL;\n"
    "    END IF;\n").replace("{PAGADOR}", "")

# (e) C5 (H5): app_pago_el_pedido. La de la 0032 leía la membresía con el marcador de quien la llamaba
PAGO_PROPIO = f"""
CREATE OR REPLACE FUNCTION app_pago_el_pedido(p_pedido uuid) RETURNS boolean
    LANGUAGE plpgsql {{VOLATILIDAD}} {DEFINER} AS
$$
DECLARE
    v_antes text := current_setting('app.funcion', true);
    v_pago boolean;
BEGIN
    IF p_pedido IS NULL OR public.app_usuario() IS NULL OR public.app_grupo() IS NULL
       OR public.app_rol() <> 'ninguno' OR public.app_comercio() IS NOT NULL OR public.app_repartidor() IS NOT NULL
       OR v_antes = 'pago_propio' THEN
        RETURN false;
    END IF;
{{MARCAR}}    IF NOT EXISTS (SELECT 1 FROM public.membresia m WHERE m.grupo_id = public.app_grupo()
                      AND m.usuario_id = public.app_usuario() AND m.estado = 'activa') THEN
{{DEVOLVER}}        RETURN false;
    END IF;
{{MARCAR_0034}}    v_pago := EXISTS (
        SELECT 1 FROM public.cargo c JOIN public.participacion pa ON pa.cargo_id = c.id
          JOIN public.pedido p ON p.id = c.pedido_id
         WHERE c.pedido_id = p_pedido AND p.grupo_id = public.app_grupo()
           AND pa.usuario_id = public.app_usuario() AND pa.monto_cobrado > 0);
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
    RETURN COALESCE(v_pago, false);
END $$;
"""
PAGO_PROPIO_0034 = (
    PAGO_PROPIO.replace("{VOLATILIDAD}", "STABLE").replace("{MARCAR}", "").replace("{DEVOLVER}", "")
    .replace("{MARCAR_0034}", _marcar("pago_propio"))
)
PAGO_PROPIO_0035 = (
    PAGO_PROPIO.replace("{VOLATILIDAD}", "VOLATILE").replace("{MARCAR}", _marcar("pago_propio"))
    .replace("{DEVOLVER}", DEVOLVER.replace("    ", "        ", 1)).replace("{MARCAR_0034}", "")
)

# (b) Las de la conservación: el cuerpo de la 0034 con el marcador de cada una
CONSERVACION = ((CONSUMO, "consumo_conservar"), (IAM, "iam_conservar"), (QUIEBRE, "quiebre_conservar"),
                (RELEVO, "relevo_conservar"), (PLAN, "plan_destruir_claves"))


def _funciones(subir: bool) -> str:
    sql = "".join(_cuerpo(plantilla, funcion if subir else None) for plantilla, funcion in CONSERVACION)
    sql += _cuerpo(RESOLVER, "pago_resolver_venta" if subir else None).replace(
        "{VOLATILIDAD}", "VOLATILE" if subir else "STABLE")
    sql += PEDIDOS_0035 if subir else PEDIDOS_0034
    sql += SOLICITANTE_0035 if subir else SOLICITANTE_0034
    sql += PAGO_PROPIO_0035 if subir else PAGO_PROPIO_0034
    # REVOKE PUBLIC: CREATE OR REPLACE no cambia los permisos, y ninguna de estas los da a PUBLIC (la 0022 y la 0024)
    sql += "".join(f"REVOKE ALL ON FUNCTION {firma} FROM PUBLIC;\n" for firma in FIRMAS)
    return sql


FIRMAS = (
    "consumo_conservar(timestamptz, timestamptz)", "iam_conservar(timestamptz, timestamptz, timestamptz)",
    "quiebre_conservar(timestamptz, timestamptz, timestamptz)", "relevo_conservar(timestamptz, timestamptz)",
    "plan_destruir_claves(timestamptz, timestamptz)", "pago_resolver_venta(text, text, text)",
    "pedido_conservar(timestamptz, timestamptz)", "operacion_solicitante_retracto(uuid, bytea, uuid)",
    "app_pago_el_pedido(uuid)",
)

# (g) C7 (H8): las que cambian app.funcion y eran STABLE (app_pago_el_pedido y pago_resolver_venta, arriba)
STABLE_0034 = ("operacion_cuenta_activa(uuid)", "cuenta_es_operacion(uuid)", "operacion_buscar_cuenta(bytea)",
               "cuenta_pagos()", "cuenta_retractos()", "cuenta_condiciones()")


def _volatilidad(subir: bool) -> str:
    return "".join(f"ALTER FUNCTION {f} {'VOLATILE' if subir else 'STABLE'};\n" for f in STABLE_0034)


UPGRADE = (_funciones(True) + _triggers(MARCA_TRIGGER_0035) + _politicas(True) + AVISOS + DIRECCION
           + _volatilidad(True))
DOWNGRADE = (_volatilidad(False) + DIRECCION_BAJADA + AVISOS_BAJADA + _politicas(False)
             + _triggers(MARCA_TRIGGER_0034) + _funciones(False))


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

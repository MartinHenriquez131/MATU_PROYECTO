"""MATU-116: quien pagó un pedido sigue viendo sus pagos y puede arrepentirse de esa compra.

Aunque pase a «Se informa» o salga del grupo.

Cadena: 0031 (MATU-114) -> 0032. down_revision = "0031".

Revisión previa del analista normativo del 18-11 (C1 a C9) y decisiones J1 a J7 de Jorge del 18-11. Decisión 475 de
docs/api/README.md. backend/db/*.sql no se tocan. La auditoría no cambia (C8).

«Pagó este pedido» en el grupo (C5 y C6)
a) app_pago_el_pedido(pedido): true solo si quien llama es miembro activo de app_grupo(), el pedido es de ese grupo y
   su participación cobró algo (la regla de _QUIEN_PAGO desde MATU-63). SECURITY DEFINER, dueño matu_owner,
   search_path fijo, EXECUTE solo matu_app (la llaman las políticas). Falla cerrada (false) sin app_usuario() ni
   app_grupo(), con un rol de contexto (operación, sistema, relevo), con app.comercio_id o app.repartidor_id, y si el
   marcador 'pago_propio' ya está puesto: así no se llama a sí misma desde cargo_familia_leer (recursión) y matu_app
   que fija el marcador pierde, no gana. Lee cargo y participacion con el marcador 'pago_propio' (cargo_pago_propio y
   participacion_pago_propio, TO matu_owner; la participación, solo la propia) y lo devuelve al salir. Una función y
   no un EXISTS en la política: cargo_familia_leer no puede mirar participacion, que ya mira cargo (recursión de
   políticas).
b) C6, las lecturas de la familia suman «o pagó este pedido», siempre dentro de app_grupo():
   - cargo_familia_leer: CARGO_DEL_GRUPO AND (app_ve_entrega() OR app_pago_el_pedido(cargo.pedido_id)).
   - participacion_familia_leer y transaccion_familia_leer: la de quien pagó, solo la suya (usuario_id =
     app_usuario()), nunca la de otra cuenta del mismo pedido.
   - retracto_familia_leer y retracto_linea_familia_leer: los retractos del pedido que pagó.
   - retracto_familia_crear: la rama de quien pagó pasa de app_ve_entrega() AND EXISTS (...) a
     app_pago_el_pedido(retracto.pedido_id), que exige que esté activo en el grupo y que haya pagado. El admin, igual.
   - pedido_entrega sigue cerrada para «Se informa» (entrega_familia_leer no cambia).

«Tus datos» (C1 a C4)
c) cuenta_pagos(), cuenta_retractos() y cuenta_condiciones(): los de la cuenta en contexto, en todos sus grupos,
   también los que dejó (J2, J3 y J5; reemplazan las decisiones 360 y 371). SECURITY DEFINER, dueño matu_owner,
   search_path fijo, EXECUTE solo matu_app. Columnas fijas, sin grupo_id: el nombre del grupo solo si la membresía
   está activa (C4) y sigue_en_el_grupo. El pedido va con LEFT JOIN (C2: el pago se guarda 6 años y el pedido 2). Los
   retractos de un grupo que dejó, sin productos (C3). Fallan cerradas (insufficient_privilege) sin app_usuario(),
   con app.rol puesto (operación, sistema, relevo), con app.comercio_id, app.repartidor_id o app.acceso_relevo_id, y
   con la cuenta eliminada o de operación. Filtran por participacion.usuario_id, retracto.solicitado_por y
   pedido.condiciones_aceptadas_por = app_usuario(). Leen con el marcador 'tus_datos' (políticas TO matu_owner):
   - participacion_tus_datos, transaccion_tus_datos, retracto_tus_datos y retracto_linea_tus_datos, solo lo de la
     propia cuenta;
   - cargo_tus_datos y pedido_tus_datos, sin filtro por fila: el filtro va en la función, porque cargo y pedido no
     pueden mirar participacion sin recursión de políticas;
   - grupo_tus_datos, solo los grupos donde la cuenta está activa (C4).
   pedido_linea (linea_leer) y producto (producto_lectura) se leen con sus políticas de hoy.

El retracto por correo (C9, J4)
d) operacion_solicitante_retracto: con la huella, también quien pagó ese pedido, aunque haya salido del grupo. Sigue
   devolviendo solo el id. La regla del titular de C10 de MATU-114 (sin nada, quien pagó) no cambia.

Recorrido (C6, RLS crítica): las políticas que cambian son solo las de la familia (sin TO). Las tareas y funciones que
leen cargo, participacion, transaccion_pasarela o retracto lo hacen con app.rol = 'sistema' u 'operacion' (sus
políticas no cambian, y app_pago_el_pedido les responde false) o con un marcador propio; la semilla de demostración
escribe como dueño. Ninguna política TO matu_owner existente cambia.

downgrade() deja todo como en la 0031: las políticas de la 0024 y la 0029, la función de la 0031, y sin las funciones
ni las políticas nuevas.

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


FUNCION = "current_setting('app.funcion', true)"
LEE = "(SELECT app_ve_entrega())"

# Las de la 0024
CARGO_DEL_GRUPO = "EXISTS (SELECT 1 FROM pedido p WHERE p.id = cargo.pedido_id AND p.grupo_id = app_grupo())"
PARTICIPACION_DEL_GRUPO = (
    "EXISTS (SELECT 1 FROM cargo c JOIN pedido p ON p.id = c.pedido_id"
    " WHERE c.id = participacion.cargo_id AND p.grupo_id = app_grupo())"
)
TRANSACCION_DEL_GRUPO = (
    "EXISTS (SELECT 1 FROM cargo c JOIN pedido p ON p.id = c.pedido_id"
    " WHERE c.id = transaccion_pasarela.cargo_id AND p.grupo_id = app_grupo())"
)

PAGO_EL_PEDIDO = f"""
-- (a) Si quien llama, activo en el grupo del contexto, pagó este pedido
CREATE FUNCTION app_pago_el_pedido(p_pedido uuid) RETURNS boolean
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
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
    IF NOT EXISTS (SELECT 1 FROM public.membresia m WHERE m.grupo_id = public.app_grupo()
                      AND m.usuario_id = public.app_usuario() AND m.estado = 'activa') THEN
        RETURN false;
    END IF;
    PERFORM set_config('app.funcion', 'pago_propio', true);
    v_pago := EXISTS (
        SELECT 1 FROM public.cargo c JOIN public.participacion pa ON pa.cargo_id = c.id
          JOIN public.pedido p ON p.id = c.pedido_id
         WHERE c.pedido_id = p_pedido AND p.grupo_id = public.app_grupo()
           AND pa.usuario_id = public.app_usuario() AND pa.monto_cobrado > 0);
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
    RETURN COALESCE(v_pago, false);
END $$;
REVOKE ALL ON FUNCTION app_pago_el_pedido(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_pago_el_pedido(uuid) TO matu_app;
CREATE POLICY cargo_pago_propio ON cargo FOR SELECT TO matu_owner USING ({FUNCION} = 'pago_propio');
CREATE POLICY participacion_pago_propio ON participacion FOR SELECT TO matu_owner
    USING ({FUNCION} = 'pago_propio' AND usuario_id = app_usuario());
"""

PAGO_EL_PEDIDO_BAJADA = """
DROP POLICY participacion_pago_propio ON participacion;
DROP POLICY cargo_pago_propio ON cargo;
DROP FUNCTION app_pago_el_pedido(uuid);
"""

LECTURAS = f"""
-- (b) C6: «o pagó este pedido», dentro de app_grupo()
ALTER POLICY cargo_familia_leer ON cargo USING ({CARGO_DEL_GRUPO} AND ({LEE} OR app_pago_el_pedido(cargo.pedido_id)));
ALTER POLICY participacion_familia_leer ON participacion USING ({PARTICIPACION_DEL_GRUPO} AND ({LEE} OR (
    usuario_id = app_usuario() AND EXISTS (SELECT 1 FROM cargo c WHERE c.id = participacion.cargo_id
                                              AND app_pago_el_pedido(c.pedido_id)))));
ALTER POLICY transaccion_familia_leer ON transaccion_pasarela USING ({TRANSACCION_DEL_GRUPO} AND ({LEE} OR (
    EXISTS (SELECT 1 FROM participacion pa WHERE pa.id = transaccion_pasarela.participacion_id
               AND pa.usuario_id = app_usuario())
    AND EXISTS (SELECT 1 FROM cargo c WHERE c.id = transaccion_pasarela.cargo_id
                   AND app_pago_el_pedido(c.pedido_id)))));
ALTER POLICY retracto_familia_leer ON retracto
    USING (grupo_id = app_grupo() AND ({LEE} OR app_pago_el_pedido(retracto.pedido_id)));
ALTER POLICY retracto_linea_familia_leer ON retracto_linea USING (grupo_id = app_grupo() AND ({LEE} OR EXISTS (
    SELECT 1 FROM retracto r WHERE r.id = retracto_linea.retracto_id AND app_pago_el_pedido(r.pedido_id))));
ALTER POLICY retracto_familia_crear ON retracto WITH CHECK (
    grupo_id = app_grupo() AND solicitado_por = app_usuario() AND estado = 'solicitado' AND origen = 'app'
    AND ((SELECT app_es_admin()) OR app_pago_el_pedido(retracto.pedido_id)));
"""

LECTURAS_BAJADA = f"""
ALTER POLICY cargo_familia_leer ON cargo USING ({CARGO_DEL_GRUPO} AND {LEE});
ALTER POLICY participacion_familia_leer ON participacion USING ({PARTICIPACION_DEL_GRUPO} AND {LEE});
ALTER POLICY transaccion_familia_leer ON transaccion_pasarela USING ({TRANSACCION_DEL_GRUPO} AND {LEE});
ALTER POLICY retracto_familia_leer ON retracto USING (grupo_id = app_grupo() AND {LEE});
ALTER POLICY retracto_linea_familia_leer ON retracto_linea USING (grupo_id = app_grupo() AND {LEE});
ALTER POLICY retracto_familia_crear ON retracto WITH CHECK (
    grupo_id = app_grupo() AND solicitado_por = app_usuario() AND estado = 'solicitado' AND origen = 'app'
    AND ((SELECT app_es_admin()) OR ({LEE} AND EXISTS (
        SELECT 1 FROM cargo c JOIN participacion pa ON pa.cargo_id = c.id
         WHERE c.pedido_id = retracto.pedido_id AND pa.usuario_id = app_usuario() AND pa.monto_cobrado > 0))));
"""

# (c) La entrada común de las funciones de «Tus datos»: falla cerrada y fija el marcador
_ENTRADA = """
    IF public.app_usuario() IS NULL OR public.app_rol() <> 'ninguno' OR public.app_comercio() IS NOT NULL
       OR public.app_repartidor() IS NOT NULL
       OR nullif(current_setting('app.acceso_relevo_id', true), '') IS NOT NULL THEN
        RAISE EXCEPTION '{nombre} exige la sesión de una cuenta de familia' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.usuario u WHERE u.id = public.app_usuario() AND u.eliminado_en IS NULL
                      AND u.estado <> 'eliminado' AND NOT u.es_operacion) THEN
        RAISE EXCEPTION '{nombre} exige una cuenta vigente' USING ERRCODE = 'insufficient_privilege';
    END IF;
    PERFORM set_config('app.funcion', 'tus_datos', true);
"""
_SALIDA = """
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
"""
# Si la cuenta sigue activa en el grupo, y su nombre solo entonces (C4)
_ACTIVA = (
    "EXISTS (SELECT 1 FROM public.membresia m WHERE m.grupo_id = {grupo} AND m.usuario_id = public.app_usuario()"
    " AND m.estado = 'activa')"
)
_NOMBRE = (
    "(SELECT g.nombre FROM public.grupo_familiar g WHERE g.id = {grupo} AND " + _ACTIVA + ")"
)


def _funcion(nombre: str, columnas: str, consulta: str) -> str:
    return f"""
CREATE FUNCTION {nombre}() RETURNS TABLE ({columnas})
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_antes text := current_setting('app.funcion', true);
BEGIN{_ENTRADA.format(nombre=nombre)}    RETURN QUERY {consulta};{_SALIDA}END $$;
REVOKE ALL ON FUNCTION {nombre}() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION {nombre}() TO matu_app;
"""


# C2: el pago aprobado de la cuenta; lo devuelto, las anulaciones aprobadas de esa venta. El grupo, por el pedido
CUENTA_PAGOS = _funcion(
    "cuenta_pagos",
    "referencia text, pagado_en timestamptz, cobrado bigint, devuelto bigint, tipo_tarjeta text, ultimos4 text,"
    " cuotas integer, codigo_autorizacion text, grupo text, sigue_en_el_grupo boolean",
    "SELECT pe.referencia::text, COALESCE(t.cerrada_en, t.creado_en), t.monto::bigint,"
    " (SELECT COALESCE(sum(a.monto), 0) FROM public.transaccion_pasarela a WHERE a.venta_id = t.id"
    "  AND a.tipo = 'anulacion' AND a.estado = 'aprobada')::bigint,"
    " t.tipo_tarjeta::text, t.ultimos4::text, t.cuotas::integer, t.codigo_autorizacion::text, "
    + _NOMBRE.format(grupo="pe.grupo_id") + "::text, COALESCE(" + _ACTIVA.format(grupo="pe.grupo_id") + ", false)"
    " FROM public.transaccion_pasarela t JOIN public.participacion pa ON pa.id = t.participacion_id"
    " JOIN public.cargo c ON c.id = t.cargo_id LEFT JOIN public.pedido pe ON pe.id = c.pedido_id"
    " WHERE t.tipo = 'venta' AND t.estado = 'aprobada' AND pa.usuario_id = public.app_usuario()"
    " ORDER BY COALESCE(t.cerrada_en, t.creado_en) DESC, t.id DESC",
)

# C3: los retractos que pidió la cuenta; los productos, solo si sigue en el grupo
CUENTA_RETRACTOS = _funcion(
    "cuenta_retractos",
    "referencia text, estado text, solicitado_en timestamptz, resuelto_en timestamptz, motivo_rechazo text,"
    " productos text[], grupo text, sigue_en_el_grupo boolean",
    "SELECT pe.referencia::text, r.estado::text, r.solicitado_en, r.resuelto_en, r.motivo_rechazo::text,"
    " CASE WHEN " + _ACTIVA.format(grupo="r.grupo_id") + " THEN ARRAY(SELECT pr.nombre::text"
    "  FROM public.retracto_linea rl JOIN public.pedido_linea l ON l.id = rl.pedido_linea_id"
    "  JOIN public.producto pr ON pr.id = l.producto_id WHERE rl.retracto_id = r.id ORDER BY pr.nombre, l.id) END, "
    + _NOMBRE.format(grupo="r.grupo_id") + "::text, " + _ACTIVA.format(grupo="r.grupo_id")
    + " FROM public.retracto r LEFT JOIN public.pedido pe ON pe.id = r.pedido_id"
    " WHERE r.solicitado_por = public.app_usuario() ORDER BY r.solicitado_en DESC, r.id DESC",
)

CUENTA_CONDICIONES = _funcion(
    "cuenta_condiciones",
    "referencia text, version text, huella text, aceptadas_en timestamptz, grupo text, sigue_en_el_grupo boolean",
    "SELECT pe.referencia::text, pe.condiciones_version::text, pe.condiciones_huella::text,"
    " pe.condiciones_aceptadas_en, " + _NOMBRE.format(grupo="pe.grupo_id") + "::text, "
    + _ACTIVA.format(grupo="pe.grupo_id")
    + " FROM public.pedido pe WHERE pe.condiciones_aceptadas_por = public.app_usuario()"
    " AND pe.condiciones_aceptadas_en IS NOT NULL ORDER BY pe.condiciones_aceptadas_en DESC, pe.id DESC",
)

TUS_DATOS = f"""
-- (c) Lo que leen las funciones de «Tus datos», con su marcador
CREATE POLICY participacion_tus_datos ON participacion FOR SELECT TO matu_owner
    USING ({FUNCION} = 'tus_datos' AND usuario_id = app_usuario());
CREATE POLICY transaccion_tus_datos ON transaccion_pasarela FOR SELECT TO matu_owner
    USING ({FUNCION} = 'tus_datos' AND EXISTS (SELECT 1 FROM participacion pa
           WHERE pa.id = transaccion_pasarela.participacion_id AND pa.usuario_id = app_usuario()));
CREATE POLICY cargo_tus_datos ON cargo FOR SELECT TO matu_owner USING ({FUNCION} = 'tus_datos');
CREATE POLICY pedido_tus_datos ON pedido FOR SELECT TO matu_owner USING ({FUNCION} = 'tus_datos');
CREATE POLICY retracto_tus_datos ON retracto FOR SELECT TO matu_owner
    USING ({FUNCION} = 'tus_datos' AND solicitado_por = app_usuario());
CREATE POLICY retracto_linea_tus_datos ON retracto_linea FOR SELECT TO matu_owner
    USING ({FUNCION} = 'tus_datos' AND EXISTS (SELECT 1 FROM retracto r
           WHERE r.id = retracto_linea.retracto_id AND r.solicitado_por = app_usuario()));
CREATE POLICY grupo_tus_datos ON grupo_familiar FOR SELECT TO matu_owner
    USING ({FUNCION} = 'tus_datos' AND EXISTS (SELECT 1 FROM membresia m WHERE m.grupo_id = grupo_familiar.id
           AND m.usuario_id = app_usuario() AND m.estado = 'activa'));
{CUENTA_PAGOS}{CUENTA_RETRACTOS}{CUENTA_CONDICIONES}"""

TUS_DATOS_BAJADA = """
DROP FUNCTION cuenta_condiciones();
DROP FUNCTION cuenta_retractos();
DROP FUNCTION cuenta_pagos();
DROP POLICY grupo_tus_datos ON grupo_familiar;
DROP POLICY retracto_linea_tus_datos ON retracto_linea;
DROP POLICY retracto_tus_datos ON retracto;
DROP POLICY pedido_tus_datos ON pedido;
DROP POLICY cargo_tus_datos ON cargo;
DROP POLICY transaccion_tus_datos ON transaccion_pasarela;
DROP POLICY participacion_tus_datos ON participacion;
"""

SOLICITANTE = """
CREATE OR REPLACE FUNCTION operacion_solicitante_retracto(p_pedido uuid, p_email_hash bytea, p_solicitado_por uuid)
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
{HUELLA}    ELSIF p_solicitado_por IS NOT NULL THEN
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
# (d) C9: la huella de quien pagó ese pedido, aunque haya salido del grupo, o la de un admin activo del grupo
SOLICITANTE_0032 = SOLICITANTE.replace(
    "{HUELLA}",
    """        SELECT i.usuario_id INTO v_solicitante FROM public.indice_credencial i
         WHERE i.email_hash = p_email_hash
           AND (i.usuario_id = v_pagador OR EXISTS (
                SELECT 1 FROM public.membresia m WHERE m.usuario_id = i.usuario_id AND m.grupo_id = v_grupo
                   AND m.rol = 'admin' AND m.estado = 'activa'));
""",
)
SOLICITANTE_0031 = SOLICITANTE.replace(
    "{HUELLA}",
    """        SELECT m.usuario_id INTO v_solicitante
          FROM public.indice_credencial i JOIN public.membresia m ON m.usuario_id = i.usuario_id
         WHERE i.email_hash = p_email_hash AND m.grupo_id = v_grupo AND m.rol = 'admin' AND m.estado = 'activa';
""",
)

UPGRADE = PAGO_EL_PEDIDO + LECTURAS + TUS_DATOS + SOLICITANTE_0032
DOWNGRADE = SOLICITANTE_0031 + TUS_DATOS_BAJADA + LECTURAS_BAJADA + PAGO_EL_PEDIDO_BAJADA


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

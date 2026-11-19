"""MATU-122: operación lee solo lo que usa (minimización, Ley 21.719).

Cadena: 0032 (MATU-116) -> 0033. down_revision = "0032".

Revisión previa del analista normativo del 18-11 (O2 a O7, H1, H2 y el ítem de las invitaciones; condiciones C1 a C10)
y decisiones D1 (opción a) y D2 del orquestador. backend/db/*.sql y el contrato OpenAPI no se tocan, y ninguna
respuesta de la API cambia (C10).

Las cuentas de comercio (C1, O2)
a) Sale usuario_comercio_operacion (FOR ALL, sin TO). Entran usuario_comercio_operacion_leer, _crear y _editar, TO
   matu_app, solo para los comercios ficticios (D1, opción a). Sin DELETE: operación ya no borra ni lee los enlaces
   de un comercio real.

El comercio ficticio (C7, H2)
b) El trigger comercio_ficticio_fijo impide que matu_app cambie comercio.ficticio después del INSERT. La semilla del
   catálogo crea los comercios con el valor por omisión (true, 0023) y su ON CONFLICT no toca la columna. Sin esto,
   operación (comercio_operacion, FOR ALL) podía marcar ficticio un comercio real y con (a) leer sus cuentas.

La dirección y la entrega (C2, O3 y H1)
c) Salen direccion_operacion_leer y entrega_operacion_leer. Entran entrega_conservacion_leer (SELECT) y
   entrega_conservacion_borrar (DELETE), TO matu_owner, con app.rol = 'operacion' y app.conservacion = 'pedidos', el
   marcador que pedido_conservar fija al entrar (0024).
d) H1, el defecto: desde la 0030 ninguna política de DELETE de pedido_entrega alcanzaba a matu_owner con operación, y
   el paso «con dinero» de pedido_conservar borraba 0 filas sin avisar: la dirección y el teléfono de un pedido con
   el cobro anulado quedaban guardados. Con (c) se borran. En el camino «sin dinero» se iban por la cascada del
   pedido (01_esquema.sql), que no pasa por RLS.
e) direccion_no_operacion, restrictiva y TO matu_app, como las de la 0031: direccion_familia_leer mira solo
   grupo_id = app_grupo(), y las rutas de operación que fijan el grupo del pedido (AbrirDespachoSQL) la leían igual
   después de (c). Esta no estaba en la revisión previa: la pide la prueba A3 con el grupo en el contexto.

El grupo (C3, O7)
f) Sale grupo_operacion (FOR ALL, TO matu_app), sin reemplazo. Operación ya no lee, renombra ni crea grupos. Como en
   (e), grupo_no_operacion (restrictiva, TO matu_app) cierra la lectura del nombre por el grupo del contexto
   (grupo_familia_leer mira solo id = app_grupo()): tampoco estaba en la revisión previa, y ninguna ruta de operación
   lee grupo_familiar.

Las participaciones (C4, O4)
g) participacion_operacion_leer y participacion_operacion_editar pasan a TO matu_app, con app.rol = 'operacion', sin
   cuenta en el contexto y solo las del grupo del contexto (PARTICIPACION_DEL_GRUPO de la 0024). Así siguen sirviendo a
   la devolución, que corre en AbrirDespachoSQL con el grupo del pedido y sin cuenta (D4).
h) participacion_conservacion_leer, TO matu_owner, con operación y app.conservacion = 'pedidos': el DELETE ... USING
   de pedido_conservar exige ver la fila; sin ella el borrado del cargo falla por la clave foránea (la lección de la
   0020).
i) participacion_solicitante_leer, TO matu_owner, con el marcador app.funcion = 'solicitante_retracto', y
   operacion_solicitante_retracto lo fija antes de leer quién pagó, después fija 'cuentas' y al salir devuelve el
   valor con que entró. La regla de C9 de la 0032 no cambia. 'cuentas' no se amplía a participacion. Pasa de
   STABLE a VOLATILE, porque cambia app.funcion con set_config (observación 3 del QA). invitacion_conservar ya era
   VOLATILE.
j) cargo_operacion_leer y transaccion_operacion_leer no cambian: la consola las usa (consola_sql.py).

Las incidencias (C5, O5)
k) incidencia_familia suma app_escribe_plan(): admin y cuidador activos, los que piden «Datos de» (router_copia.py,
   ROLES_QUE_PIDEN), la única lectura de la familia (copia_pagos.py). Pagador, observador y sistema, ya no.

Las invitaciones (C6, ítem extra)
l) invitacion_conservar fija app.funcion = 'invitacion_conservar' antes de sus dos DELETE y devuelve el valor anterior
   al salir. invitacion_conservacion_leer e invitacion_conservacion_borrar pasan a ese marcador, siguen TO matu_owner:
   otra función definer que corra con app.rol = 'operacion' ya no ve ni borra invitaciones.

Recorrido (C8): cada política que sale o cambia, quién la usaba y por qué no se rompe
- usuario_comercio_operacion: la usaba solo la semilla de demostración (infra/semillas/demo.py, cuenta_comercio), que
  hace INSERT ... ON CONFLICT DO UPDATE como matu_app con operación sobre los comercios ficticios del catálogo; con (a)
  sigue (leer, crear y editar). Las rutas leen la propia por usuario_comercio_propio (iam/api/dependencias.py y
  backoffice/api/dependencias.py); comercio_exigir_sesion, igual; cuenta_operacion_separada,
  cuenta_comercio_o_familia y operacion_buscar_cuenta, con el marcador 'cuentas' (TO matu_owner).
- direccion_operacion_leer y entrega_operacion_leer: ninguna ruta ni tarea de operación lee direccion ni
  pedido_entrega (C34, consola_sql.py, y tests/modules/backoffice/test_consola_api.py lo verifica). La única que usaba
  la entrega era pedido_conservar, por (c). La familia sigue con direccion_familia_* y entrega_familia_*, y «Datos de»
  (copia_pagos.py) con entrega_familia_leer.
- grupo_operacion: nadie, tampoco grupo_familia_leer con operación (f). Los quiebres listan los grupos con
  grupo_scheduler (matu_scheduler), «Tus datos» con grupo_tus_datos y la invitación con grupo_invitacion_leer
  (marcador 'invitacion').
- participacion_operacion_leer y _editar: la devolución (cancelar_con_devolucion y resolver un retracto en
  router_operacion.py, con AbrirDespachoSQL: el grupo del pedido y sin cuenta) lee y guarda la participación
  (repositorio_pagos.py, y cobro.py al terminar la anulación); la sigue viendo por (g). pedido_conservar, por (h).
  operacion_solicitante_retracto (app.usuario_id = la cuenta de operación, sin grupo), por (i). La consola no lee
  participacion (consola_sql.py). La conciliación y los avisos corren con app.rol = 'sistema'
  (participacion_sistema_*).
- incidencia_familia: «Datos de», que piden admin y cuidador (router_copia.py). Operación lee las suyas con
  incidencia_operacion_leer, que no cambia.
- invitacion_conservacion_leer y _borrar: solo invitacion_conservar, por (l). Las demás funciones de la invitación
  usan el marcador 'invitacion'.
- La semilla y --restablecer (MATU-72): --restablecer corre en el contexto del admin de cada familia
  (sesion_tenant con su cuenta y su grupo), con las políticas de la familia; ninguna cambia aquí salvo
  incidencia_familia, que al admin le sigue respondiendo. La semilla del catálogo (catalogo_demo.py) escribe comercio,
  producto y oferta como operación, sin tocar ficticio (b). La de las cuentas de comercio, por (a).
- La consola (C34): lee pedido, pedido_comercio, pedido_linea, pedido_transicion, cargo, transaccion_pasarela,
  retracto, retracto_linea, incidencia, clave_notas, producto y comercio; ninguna de esas políticas sale ni cambia.

Las políticas que no son TO matu_owner y miran app.rol = 'operacion', después de la 0033 (sacada de pg_policies; la
verifica tests/test_migraciones.py, POLITICAS_OPERACION_0033). Respecto de la 0031 salen direccion_operacion_leer,
grupo_operacion, entrega_operacion_leer y usuario_comercio_operacion; entran direccion_no_operacion,
grupo_no_operacion y usuario_comercio_operacion_leer, _crear y _editar:
- care_circle: direccion_no_operacion y grupo_no_operacion (restrictivas), e invitacion_no_operacion,
  membresia_no_operacion y usuario_no_operacion (las tres de la 0031).
- Consumo: alerta_leer, perfil_leer y reposicion_leer.
- Capa 3: pedido_operacion_leer, pedido_operacion_pago, pedido_comercio_operacion_leer,
  pedido_comercio_operacion_editar, linea_pago_devolver, transicion_sistema_crear, cargo_operacion_leer,
  cargo_operacion_editar, participacion_operacion_leer, participacion_operacion_editar, transaccion_operacion_leer,
  transaccion_operacion_crear, transaccion_operacion_editar, retracto_operacion_leer, retracto_operacion_crear,
  retracto_operacion_editar, retracto_linea_operacion_leer, retracto_linea_operacion_crear,
  incidencia_operacion_leer, incidencia_operacion_crear, incidencia_operacion_editar, clave_notas_operacion_leer,
  clave_notas_operacion_crear, consumo_comercio_operacion y auditoria_insertar.
- Catálogo y Product Backlog: categoria_operacion, producto_operacion, comercio_operacion, convenio_operacion,
  oferta_operacion, usuario_comercio_operacion_leer, usuario_comercio_operacion_crear,
  usuario_comercio_operacion_editar, asignacion_operacion, oferta_asig_operacion, repartidor_operacion y
  liquidacion_operacion.

downgrade() deja el catálogo igual al de la 0032 (C9): recrea las políticas que salen como estaban, devuelve las que
cambian y las funciones de la 0026 y la 0032, y quita el trigger, su función y las políticas nuevas. No borra filas.

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


OPERACION = "app_rol() = 'operacion'"
CONSERVACION = f"{OPERACION} AND current_setting('app.conservacion', true) = 'pedidos'"
FICTICIO = (
    f"{OPERACION} AND EXISTS (SELECT 1 FROM comercio c WHERE c.id = usuario_comercio.comercio_id AND c.ficticio)"
)
# La de la 0024
PARTICIPACION_DEL_GRUPO = (
    "EXISTS (SELECT 1 FROM cargo c JOIN pedido p ON p.id = c.pedido_id"
    " WHERE c.id = participacion.cargo_id AND p.grupo_id = app_grupo())"
)
PARTICIPACION_OPERACION = f"{OPERACION} AND app_usuario() IS NULL AND {PARTICIPACION_DEL_GRUPO}"

COMERCIOS = f"""
-- (a) C1: las cuentas de los comercios ficticios, sin DELETE
DROP POLICY usuario_comercio_operacion ON usuario_comercio;
CREATE POLICY usuario_comercio_operacion_leer ON usuario_comercio FOR SELECT TO matu_app USING ({FICTICIO});
CREATE POLICY usuario_comercio_operacion_crear ON usuario_comercio FOR INSERT TO matu_app WITH CHECK ({FICTICIO});
CREATE POLICY usuario_comercio_operacion_editar ON usuario_comercio FOR UPDATE TO matu_app
    USING ({FICTICIO}) WITH CHECK ({FICTICIO});

-- (b) C7: matu_app no cambia si un comercio es ficticio
CREATE FUNCTION comercio_ficticio_fijo() RETURNS trigger LANGUAGE plpgsql
    SET search_path = pg_catalog, public, pg_temp AS
$$
BEGIN
    IF current_user = 'matu_app' THEN
        RAISE EXCEPTION 'si un comercio es ficticio no cambia' USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION comercio_ficticio_fijo() FROM PUBLIC;
CREATE TRIGGER comercio_ficticio_fijo BEFORE UPDATE OF ficticio ON comercio
    FOR EACH ROW WHEN (NEW.ficticio IS DISTINCT FROM OLD.ficticio) EXECUTE FUNCTION comercio_ficticio_fijo();
"""

COMERCIOS_BAJADA = """
DROP TRIGGER comercio_ficticio_fijo ON comercio;
DROP FUNCTION comercio_ficticio_fijo();
DROP POLICY usuario_comercio_operacion_editar ON usuario_comercio;
DROP POLICY usuario_comercio_operacion_crear ON usuario_comercio;
DROP POLICY usuario_comercio_operacion_leer ON usuario_comercio;
CREATE POLICY usuario_comercio_operacion ON usuario_comercio FOR ALL USING (app_rol() = 'operacion');
"""

ENTREGA = f"""
-- (c) C2: operación no lee la dirección ni la entrega; pedido_conservar las ve y las borra con su marcador
DROP POLICY direccion_operacion_leer ON direccion;
DROP POLICY entrega_operacion_leer ON pedido_entrega;
CREATE POLICY entrega_conservacion_leer ON pedido_entrega FOR SELECT TO matu_owner USING ({CONSERVACION});
CREATE POLICY entrega_conservacion_borrar ON pedido_entrega FOR DELETE TO matu_owner USING ({CONSERVACION});
-- (e) Tampoco por el grupo del contexto (direccion_familia_leer)
CREATE POLICY direccion_no_operacion ON direccion AS RESTRICTIVE FOR SELECT TO matu_app
    USING (app_rol() IS DISTINCT FROM 'operacion');

-- (f) C3: operación no lee, renombra ni crea grupos, tampoco por el grupo del contexto (grupo_familia_leer)
DROP POLICY grupo_operacion ON grupo_familiar;
CREATE POLICY grupo_no_operacion ON grupo_familiar AS RESTRICTIVE FOR SELECT TO matu_app
    USING (app_rol() IS DISTINCT FROM 'operacion');
"""

ENTREGA_BAJADA = """
DROP POLICY grupo_no_operacion ON grupo_familiar;
CREATE POLICY grupo_operacion ON grupo_familiar FOR ALL TO matu_app USING (app_rol() = 'operacion');
DROP POLICY direccion_no_operacion ON direccion;
DROP POLICY entrega_conservacion_borrar ON pedido_entrega;
DROP POLICY entrega_conservacion_leer ON pedido_entrega;
CREATE POLICY entrega_operacion_leer ON pedido_entrega FOR SELECT USING (app_rol() = 'operacion');
CREATE POLICY direccion_operacion_leer ON direccion FOR SELECT USING (app_rol() = 'operacion');
"""

PARTICIPACIONES = f"""
-- (g) C4: la devolución, con el grupo del pedido y sin cuenta
ALTER POLICY participacion_operacion_leer ON participacion TO matu_app USING ({PARTICIPACION_OPERACION});
ALTER POLICY participacion_operacion_editar ON participacion TO matu_app
    USING ({PARTICIPACION_OPERACION}) WITH CHECK ({PARTICIPACION_OPERACION});
-- (h) pedido_conservar
CREATE POLICY participacion_conservacion_leer ON participacion FOR SELECT TO matu_owner USING ({CONSERVACION});
-- (i) operacion_solicitante_retracto
CREATE POLICY participacion_solicitante_leer ON participacion FOR SELECT TO matu_owner
    USING (current_setting('app.funcion', true) = 'solicitante_retracto');
"""

PARTICIPACIONES_BAJADA = """
DROP POLICY participacion_solicitante_leer ON participacion;
DROP POLICY participacion_conservacion_leer ON participacion;
ALTER POLICY participacion_operacion_editar ON participacion TO public
    USING (app_rol() = 'operacion') WITH CHECK (app_rol() = 'operacion');
ALTER POLICY participacion_operacion_leer ON participacion TO public USING (app_rol() = 'operacion');
"""

SOLICITANTE = """
CREATE OR REPLACE FUNCTION operacion_solicitante_retracto(p_pedido uuid, p_email_hash bytea, p_solicitado_por uuid)
    RETURNS uuid
    LANGUAGE plpgsql {VOLATILIDAD} SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_antes text{ANTES};
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
{PAGADOR}    PERFORM set_config('app.funcion', 'cuentas', true);
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
# (i) El valor de app.funcion con que se entra, y quién pagó con el marcador 'solicitante_retracto'. VOLATILE: cambia
# app.funcion con set_config, y una función STABLE no cambia la configuración (observación 3 del QA)
SOLICITANTE_0033 = SOLICITANTE.replace("{VOLATILIDAD}", "VOLATILE").replace(
    "{ANTES}", " := current_setting('app.funcion', true)").replace(
    "{PAGADOR}",
    """    -- Quien pagó: la primera participación con un cobro (como _QUIEN_PAGO desde MATU-63)
    PERFORM set_config('app.funcion', 'solicitante_retracto', true);
    SELECT pa.usuario_id INTO v_pagador FROM public.participacion pa JOIN public.cargo c ON c.id = pa.cargo_id
     WHERE c.pedido_id = p_pedido AND pa.monto_cobrado > 0 ORDER BY pa.id LIMIT 1;
""",
) + "REVOKE ALL ON FUNCTION operacion_solicitante_retracto(uuid, bytea, uuid) FROM PUBLIC;\n"
# La de la 0032 (SOLICITANTE_0032), igual letra por letra
SOLICITANTE_0032 = SOLICITANTE.replace("{VOLATILIDAD}", "STABLE").replace("{ANTES}", "").replace(
    "{PAGADOR}",
    """    -- Quien pagó: la primera participación con un cobro (como _QUIEN_PAGO desde MATU-63)
    SELECT pa.usuario_id INTO v_pagador FROM public.participacion pa JOIN public.cargo c ON c.id = pa.cargo_id
     WHERE c.pedido_id = p_pedido AND pa.monto_cobrado > 0 ORDER BY pa.id LIMIT 1;
    v_antes := current_setting('app.funcion', true);
""",
)

INCIDENCIAS = """
-- (k) C5: las notas del equipo, solo para quienes piden «Datos de» (admin y cuidador activos)
ALTER POLICY incidencia_familia ON incidencia USING (
    EXISTS (SELECT 1 FROM pedido p WHERE p.id = incidencia.pedido_id AND p.grupo_id = app_grupo())
    AND (SELECT app_escribe_plan()));
"""

INCIDENCIAS_BAJADA = """
ALTER POLICY incidencia_familia ON incidencia USING (EXISTS (
    SELECT 1 FROM pedido p WHERE p.id = incidencia.pedido_id AND p.grupo_id = app_grupo()));
"""

INVITACIONES = """
CREATE OR REPLACE FUNCTION invitacion_conservar(limite timestamptz, ahora timestamptz) RETURNS integer
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    borradas integer;
{DECLARAR}BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'invitacion_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '30 days' THEN
        RAISE EXCEPTION 'las invitaciones cerradas se conservan 30 días' USING ERRCODE = 'invalid_parameter_value';
    END IF;
{MARCAR}    -- Cerrada desde la primera de sus fechas: aceptada, anulada, bloqueada o vencida. LEAST ignora los nulos
    DELETE FROM public.indice_token t USING public.invitacion i
     WHERE t.tipo = 'invitacion' AND t.referencia_id = i.id
       AND LEAST(i.aceptada_en, i.revocada_en, i.bloqueada_en, i.expira_en) <= limite;
    DELETE FROM public.invitacion i WHERE LEAST(i.aceptada_en, i.revocada_en, i.bloqueada_en, i.expira_en) <= limite;
    GET DIAGNOSTICS borradas = ROW_COUNT;
{DEVOLVER}    RETURN borradas;
END $$;
"""
MARCADOR_INVITACION = "current_setting('app.funcion', true) = 'invitacion_conservar'"
# (l) C6: el marcador propio antes de los dos DELETE, y el valor anterior al salir
INVITACIONES_0033 = (
    INVITACIONES.replace("{DECLARAR}", "    v_antes text := current_setting('app.funcion', true);\n")
    .replace("{MARCAR}", "    PERFORM set_config('app.funcion', 'invitacion_conservar', true);\n")
    .replace("{DEVOLVER}", "    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);\n")
    + f"""REVOKE ALL ON FUNCTION invitacion_conservar(timestamptz, timestamptz) FROM PUBLIC;
ALTER POLICY invitacion_conservacion_leer ON invitacion USING ({MARCADOR_INVITACION});
ALTER POLICY invitacion_conservacion_borrar ON invitacion USING ({MARCADOR_INVITACION});
"""
)
# La de la 0026
INVITACIONES_0032 = (
    INVITACIONES.replace("{DECLARAR}", "").replace("{MARCAR}", "").replace("{DEVOLVER}", "")
    + """ALTER POLICY invitacion_conservacion_borrar ON invitacion USING (app_rol() = 'operacion');
ALTER POLICY invitacion_conservacion_leer ON invitacion USING (app_rol() = 'operacion');
"""
)

UPGRADE = COMERCIOS + ENTREGA + PARTICIPACIONES + SOLICITANTE_0033 + INCIDENCIAS + INVITACIONES_0033
DOWNGRADE = (
    INVITACIONES_0032 + INCIDENCIAS_BAJADA + SOLICITANTE_0032 + PARTICIPACIONES_BAJADA + ENTREGA_BAJADA
    + COMERCIOS_BAJADA
)


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

"""MATU-63: la vista del comercio, el código de retiro por parte, el despacho y el retracto.

Cadena: 0028 (MATU-54) -> 0029. down_revision = "0028".

Decisiones D-63-1 a D-63-16 (revisión previa del analista del 13-11) y O1 a O6 del orquestador sobre la especificación
de diseño (docs/diseno/matu-63-comercio.md). Decisiones 407 en adelante de docs/api/README.md.

a) D-63-1 y D-63-2: el comercio ya no lee ni escribe tablas del pedido. Salen pedido_comercio_ver y
   pedido_comercio_actualizar (pedido), pedido_comercio_propio (pedido_comercio) y linea_comercio_ver (pedido_linea).
   Lee y escribe solo por funciones SECURITY DEFINER (dueño matu_owner, search_path fijo, EXECUTE solo para matu_app):
   comercio_partes, comercio_lineas, comercio_preparar, comercio_marcar_linea, comercio_listo,
   comercio_validar_codigo y comercio_existencias. Cada una exige app_comercio(), sin grupo, con una cuenta y sin rol, y
   la cuenta activa de ese comercio activo (comercio_exigir_sesion). Dentro fijan app.funcion = 'comercio', y las
   políticas TO matu_owner de esas filas lo exigen junto con el comercio de la sesión.
b) D-63-3: un código por parte (pedido_comercio): estado (enviada, preparando, lista, retirada o cancelada) con sus
   instantes, version (el ETag de la vista), el código (hash HMAC, generado, vence, usado, intentos, bloqueado) y el
   apartado del stock (D-63-7). pedido.codigo_retiro_* quedan sin uso. O6: la referencia opaca pasa a 6 caracteres de
   un alfabeto que se dicta (sin 0, O, 1, I ni L); las existentes se rehacen.
c) D-63-7 y O5: el apartado. Una parte confirmada y sin pagar aparta hasta apartado_hasta (total_vence_en más la vida
   de la venta); una parte pagada aparta mientras está enviada o preparando. oferta.stock incluye lo apartado y baja
   al marcar «Listo» (comercio_listo). oferta_disponible entrega stock menos lo apartado por otras familias, para la
   confirmación del pedido.
d) D-63-8: pedido_linea.unidades_faltantes; pedido_linea_devuelta admite la devolución parcial (una línea con
   faltantes devueltos, o con un retracto, puede no estar devuelta entera).
e) D-63-10: retracto y retracto_linea, RLS forzado, y transaccion_linea_devuelta_uq pasa a una anulación por línea y
   motivo; motivo_anulacion suma retracto, y transaccion_pasarela.retracto_id ata la anulación del envío.
f) D-63-14: una cuenta de comercio no es miembro de un grupo, y al revés (trigger en membresia y usuario_comercio).
g) D-63-15: evidencia sin ubicación (CHECK, antes se vacía).
h) pedido_escritura_del_pago: después del pago, solo el sistema y operación, sin cuenta, cambian el estado, por las
   transiciones del despacho, y entregado_en una vez al entregar. Nadie más cambia nada de un pedido pagado. La
   familia ya no edita líneas ni borra partes de un pedido pagado (linea_editar y pedido_comercio_familia_borrar).
i) pedido_comercio por operación y por rol: el sistema (con el grupo) y operación la actualizan.
j) consumo_comercio (RF-31): el comercio solo lee lo suyo; lo escribe operación al entregar, una fila por parte
   (pedido_comercio_id), con la boleta pendiente (monto_boleta y folio_boleta pueden faltar).
k) pedido_transicion: motivos producto_faltante y retracto; el sistema escribe también las del comercio y de la cuenta
   (actor_ref es el comercio o la cuenta, nunca la del encargado).
l) La auditoría del comercio va sin grupo: auditoria_cuenta_acotada suma sus acciones, y la política restrictiva
   auditoria_comercio_propia exige que una sesión de comercio inserte solo actor_tipo = 'comercio', sin grupo ni
   persona. auditoria_persona_obligatoria suma las acciones nuevas de una persona.
m) despacho_resolver_parte (sistema, sin grupo ni cuenta) y despacho_pendiente (matu_scheduler, app.rol =
   'operacion'): solo ids, para que el sistema lleve el estado del pedido y devuelva lo que falta.
n) oferta: el comercio cambia solo stock y disponible (trigger oferta_comercio_acotada).

backend/db/*.sql no se tocan. downgrade() deja el esquema como en 0028. Falla si quedan filas que no caben en el
esquema anterior (una devolución parcial, una anulación por retracto o dos consumos de un mismo pedido), como las
bajadas anteriores, sin borrar nada. Las referencias de 6 caracteres se rehacen con 32.

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
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


ACCIONES_DE_CUENTA_0028 = (
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
)
# Las del comercio van sin grupo ni persona (D-63-12). tests/test_migraciones.py verifica que coinciden con el código
ACCIONES_DEL_COMERCIO_0029 = (
    "comercio.preparar",
    "comercio.marcar_linea",
    "comercio.listo",
    "comercio.codigo_correcto",
    "comercio.codigo_incorrecto",
    "comercio.codigo_bloqueo",
    "comercio.productos_cambiar",
)
SIN_GRUPO_0029 = ACCIONES_DE_CUENTA_0028 + ACCIONES_DEL_COMERCIO_0029
ACCIONES_DE_PERSONA_0028 = (
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
)
ACCIONES_DE_PERSONA_0029 = (
    *ACCIONES_DE_PERSONA_0028,
    "pago.devolver",
    "pedido.retracto_solicitar",
    "despacho.codigo_generar",
    "despacho.en_camino",
    "despacho.entregar",
    "despacho.no_entregado",
    "retracto.resolver",
)

MOTIVOS_0024 = (
    "'total_vencio', 'familia_cancela', 'familia_cambia_carrito', 'autorizacion_retirada', 'persona_borrada',"
    " 'pago_aprobado'"
)
MOTIVOS_0029 = MOTIVOS_0024 + ", 'producto_faltante', 'retracto'"

# Las transiciones del pedido después del pago (arquitectura 8.1, app/modules/ordering/domain/estados.py)
TRANSICIONES_DESPACHO = (
    "('pagado', 'enviado_a_comercio'), ('pagado', 'cancelado_con_devolucion'),"
    " ('enviado_a_comercio', 'preparando'), ('enviado_a_comercio', 'cancelado_con_devolucion'),"
    " ('preparando', 'listo_retiro'), ('preparando', 'cancelado_con_devolucion'), ('listo_retiro', 'retirado'),"
    " ('retirado', 'en_ruta'), ('en_ruta', 'entregado'), ('en_ruta', 'no_entregado'), ('entregado', 'cerrado'),"
    " ('no_entregado', 'reprogramado'), ('no_entregado', 'cancelado_con_devolucion'), ('reprogramado', 'en_ruta')"
)

SISTEMA = "app_rol() = 'sistema' AND app_usuario() IS NULL"
PAGADO_FUERA = "p.pagado_en IS NULL"
LINEA_ESCRIBE_0023 = (
    "EXISTS (SELECT 1 FROM pedido p WHERE p.id = pedido_linea.pedido_id AND p.grupo_id = app_grupo())"
    " AND (SELECT app_escribe_pedido())"
)
LINEA_ESCRIBE_0029 = (
    "EXISTS (SELECT 1 FROM pedido p WHERE p.id = pedido_linea.pedido_id AND p.grupo_id = app_grupo()"
    " AND p.pagado_en IS NULL) AND (SELECT app_escribe_pedido())"
)
PARTE_BORRA_0023 = "grupo_id = app_grupo() AND (SELECT app_escribe_pedido())"
PARTE_BORRA_0029 = "grupo_id = app_grupo() AND enviado_en IS NULL AND (SELECT app_escribe_pedido())"
FUNCION = "current_setting('app.funcion', true)"
# El alfabeto de la referencia opaca (O6): sin 0, O, 1, I ni L
ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # pragma: allowlist secret

ESCRITURA_0024 = """
DECLARE
    resto public.pedido%ROWTYPE;
    acotado boolean := app_rol() IN ('sistema', 'operacion') AND app_usuario() IS NULL;
BEGIN
    -- Observación 5: dentro de pedido_conservar, un pedido abierto con dinero que quedó sin líneas pasa a cancelado,
    -- y nada más cambia
    IF current_user = 'matu_owner' AND current_setting('app.conservacion', true) = 'pedidos'
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
END """

BLOQUE_0029 = f"""
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
        IF NEW.estado IS DISTINCT FROM OLD.estado AND (OLD.estado, NEW.estado) NOT IN ({TRANSICIONES_DESPACHO}) THEN
            RAISE EXCEPTION 'el pedido no pasa de ese estado a ese otro' USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.entregado_en IS DISTINCT FROM OLD.entregado_en
           AND (OLD.entregado_en IS NOT NULL OR NEW.estado <> 'entregado') THEN
            RAISE EXCEPTION 'entregado_en se fija una vez, al entregar' USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
"""
ANCLA_R5 = "    -- R5: con el pago"
ESCRITURA_0029 = ESCRITURA_0024.replace(ANCLA_R5, BLOQUE_0029.lstrip("\n") + ANCLA_R5, 1)

# Lo apartado de una oferta en el instante ahora (D-63-7 y O5), sin lo de un grupo (la familia que vuelve a confirmar)
APARTADO = """
CREATE FUNCTION oferta_apartado(p_oferta uuid, p_ahora timestamptz, p_sin_grupo uuid) RETURNS integer
    LANGUAGE sql STABLE SET search_path = pg_catalog, public, pg_temp AS
$$
    SELECT COALESCE(sum(l.cantidad), 0)::integer
      FROM public.pedido_linea l
      JOIN public.pedido_comercio pc ON pc.id = l.pedido_comercio_id
      JOIN public.pedido p ON p.id = l.pedido_id
     WHERE l.oferta_id = p_oferta AND l.estado_linea NOT IN ('sin_stock', 'eliminada')
       AND ((p.pagado_en IS NULL AND p.estado IN ('total_confirmado', 'vencido') AND pc.apartado_hasta > p_ahora
             AND p.grupo_id IS DISTINCT FROM p_sin_grupo)
            OR (p.pagado_en IS NOT NULL AND pc.enviado_en IS NOT NULL AND pc.estado IN ('enviada', 'preparando')))
$$;
REVOKE ALL ON FUNCTION oferta_apartado(uuid, timestamptz, uuid) FROM PUBLIC;
"""

EXIGIR_SESION = """
CREATE FUNCTION comercio_exigir_sesion() RETURNS uuid
    LANGUAGE plpgsql STABLE SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    v_comercio uuid := public.app_comercio();
BEGIN
    IF v_comercio IS NULL OR public.app_grupo() IS NOT NULL OR public.app_usuario() IS NULL
       OR public.app_rol() <> 'ninguno' OR public.app_repartidor() IS NOT NULL
       OR NOT EXISTS (SELECT 1 FROM public.usuario_comercio uc JOIN public.comercio c ON c.id = uc.comercio_id
                       WHERE uc.usuario_id = public.app_usuario() AND uc.comercio_id = v_comercio AND uc.activo
                         AND c.estado = 'activo') THEN
        RAISE EXCEPTION 'solo la cuenta activa de un comercio activo' USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN v_comercio;
END $$;
REVOKE ALL ON FUNCTION comercio_exigir_sesion() FROM PUBLIC;
"""

DEFINIDOR = "SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp"

FUNCIONES_COMERCIO = f"""
-- Las partes del comercio de la sesión: las abiertas y las cerradas desde p_desde. Sin pedido, grupo, persona,
-- montos, referencia de la familia ni hash (D-63-1)
CREATE FUNCTION comercio_partes(p_desde timestamptz)
    RETURNS TABLE (parte_id uuid, referencia text, estado text, version integer, enviado_en timestamptz,
                   lineas integer, retirada_en timestamptz, cancelada_en timestamptz, codigo_generado_en timestamptz,
                   codigo_con_hash boolean, codigo_expira_en timestamptz, codigo_usado_en timestamptz,
                   codigo_bloqueado_en timestamptz)
    LANGUAGE plpgsql VOLATILE {DEFINIDOR} AS
$$
DECLARE
    v_comercio uuid := public.comercio_exigir_sesion();
BEGIN
    PERFORM set_config('app.funcion', 'comercio', true);
    RETURN QUERY
        SELECT pc.id, pc.referencia, pc.estado, pc.version, pc.enviado_en,
               (SELECT count(*)::integer FROM public.pedido_linea l WHERE l.pedido_comercio_id = pc.id),
               pc.retirada_en, pc.cancelada_en, pc.codigo_generado_en, pc.codigo_hash IS NOT NULL,
               pc.codigo_expira_en, pc.codigo_usado_en, pc.codigo_bloqueado_en
          FROM public.pedido_comercio pc
         WHERE pc.comercio_id = v_comercio AND pc.enviado_en IS NOT NULL
           AND EXISTS (SELECT 1 FROM public.pedido p WHERE p.id = pc.pedido_id AND p.pagado_en IS NOT NULL)
           AND (pc.estado IN ('enviada', 'preparando', 'lista')
                OR COALESCE(pc.retirada_en, pc.cancelada_en) >= p_desde)
         ORDER BY pc.enviado_en, pc.id;
    PERFORM set_config('app.funcion', '', true);
END $$;

-- Las líneas de una parte del comercio: producto, cantidad y lo marcado. Sin precio ni montos
CREATE FUNCTION comercio_lineas(p_parte uuid)
    RETURNS TABLE (linea_id uuid, producto_nombre text, presentacion text, cantidad integer, estado_linea text,
                   unidades_faltantes integer)
    LANGUAGE plpgsql VOLATILE {DEFINIDOR} AS
$$
DECLARE
    v_comercio uuid := public.comercio_exigir_sesion();
BEGIN
    PERFORM set_config('app.funcion', 'comercio', true);
    RETURN QUERY
        SELECT l.id, pr.nombre, pr.presentacion, l.cantidad, l.estado_linea, l.unidades_faltantes
          FROM public.pedido_linea l
          JOIN public.pedido_comercio pc ON pc.id = l.pedido_comercio_id
          JOIN public.producto pr ON pr.id = l.producto_id
         WHERE pc.id = p_parte AND pc.comercio_id = v_comercio AND pc.enviado_en IS NOT NULL
           AND EXISTS (SELECT 1 FROM public.pedido p WHERE p.id = pc.pedido_id AND p.pagado_en IS NOT NULL)
         ORDER BY pr.nombre, pr.presentacion, l.id;
    PERFORM set_config('app.funcion', '', true);
END $$;

-- p_version es la del If-Match, si vino (412 si no calza). Empezar a preparar (D-63-2, D-63-11): bloquea el pedido
-- como la cancelación después de pagar, y nunca prepara un
-- pedido cancelado. Devuelve ok, no_encontrada, version o estado
CREATE FUNCTION comercio_preparar(p_parte uuid, p_version integer, p_ahora timestamptz) RETURNS text
    LANGUAGE plpgsql VOLATILE {DEFINIDOR} AS
$$
DECLARE
    v_comercio uuid := public.comercio_exigir_sesion();
    v_pedido uuid;
    v_parte public.pedido_comercio%ROWTYPE;
    v_estado text;
BEGIN
    PERFORM set_config('app.funcion', 'comercio', true);
    SELECT pc.pedido_id INTO v_pedido FROM public.pedido_comercio pc
     WHERE pc.id = p_parte AND pc.comercio_id = v_comercio AND pc.enviado_en IS NOT NULL;
    IF NOT FOUND THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'no_encontrada';
    END IF;
    SELECT p.estado INTO v_estado FROM public.pedido p WHERE p.id = v_pedido FOR UPDATE;
    SELECT * INTO v_parte FROM public.pedido_comercio pc WHERE pc.id = p_parte FOR UPDATE;
    IF p_version IS NOT NULL AND p_version <> v_parte.version THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'version';
    END IF;
    IF v_parte.estado <> 'enviada' OR v_estado NOT IN ('pagado', 'enviado_a_comercio', 'preparando') THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'estado';
    END IF;
    UPDATE public.pedido_comercio SET estado = 'preparando', preparando_en = p_ahora, version = version + 1
     WHERE id = p_parte;
    PERFORM set_config('app.funcion', '', true);
    RETURN 'ok';
END $$;

-- Marcar una línea (O4: se puede cambiar mientras la parte está preparando; la devolución sale con «Listo»)
CREATE FUNCTION comercio_marcar_linea(p_parte uuid, p_linea uuid, p_estado text, p_faltantes integer,
                                      p_version integer) RETURNS text
    LANGUAGE plpgsql VOLATILE {DEFINIDOR} AS
$$
DECLARE
    v_comercio uuid := public.comercio_exigir_sesion();
    v_parte public.pedido_comercio%ROWTYPE;
    v_cantidad integer;
BEGIN
    PERFORM set_config('app.funcion', 'comercio', true);
    SELECT * INTO v_parte FROM public.pedido_comercio pc
     WHERE pc.id = p_parte AND pc.comercio_id = v_comercio AND pc.enviado_en IS NOT NULL FOR UPDATE;
    IF NOT FOUND THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'no_encontrada';
    END IF;
    SELECT l.cantidad INTO v_cantidad FROM public.pedido_linea l
     WHERE l.id = p_linea AND l.pedido_comercio_id = p_parte;
    IF NOT FOUND THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'no_encontrada';
    END IF;
    IF p_version IS NOT NULL AND p_version <> v_parte.version THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'version';
    END IF;
    IF v_parte.estado <> 'preparando' THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'estado';
    END IF;
    IF NOT ((p_estado = 'preparada' AND p_faltantes = 0)
            OR (p_estado = 'faltante' AND p_faltantes BETWEEN 1 AND v_cantidad)) THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'invalida';
    END IF;
    UPDATE public.pedido_linea SET estado_linea = p_estado, unidades_faltantes = p_faltantes WHERE id = p_linea;
    UPDATE public.pedido_comercio SET version = version + 1 WHERE id = p_parte;
    PERFORM set_config('app.funcion', '', true);
    RETURN 'ok';
END $$;

-- «Listo para retirar» (O3, O5): con todo marcado, la parte queda lista (o cancelada si no tiene nada), y lo
-- preparado sale del stock. Devuelve lista, cancelada, no_encontrada, version, estado o lineas_pendientes
CREATE FUNCTION comercio_listo(p_parte uuid, p_version integer, p_ahora timestamptz) RETURNS text
    LANGUAGE plpgsql VOLATILE {DEFINIDOR} AS
$$
DECLARE
    v_comercio uuid := public.comercio_exigir_sesion();
    v_parte public.pedido_comercio%ROWTYPE;
    v_hay boolean;
BEGIN
    PERFORM set_config('app.funcion', 'comercio', true);
    SELECT * INTO v_parte FROM public.pedido_comercio pc
     WHERE pc.id = p_parte AND pc.comercio_id = v_comercio AND pc.enviado_en IS NOT NULL FOR UPDATE;
    IF NOT FOUND THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'no_encontrada';
    END IF;
    IF p_version IS NOT NULL AND p_version <> v_parte.version THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'version';
    END IF;
    IF v_parte.estado <> 'preparando' THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'estado';
    END IF;
    IF EXISTS (SELECT 1 FROM public.pedido_linea l WHERE l.pedido_comercio_id = p_parte
                AND l.estado_linea NOT IN ('preparada', 'faltante')) THEN
        PERFORM set_config('app.funcion', '', true);
        RETURN 'lineas_pendientes';
    END IF;
    UPDATE public.oferta o SET stock = GREATEST(o.stock - x.unidades, 0), actualizado_en = p_ahora
      FROM (SELECT l.oferta_id, sum(l.cantidad - l.unidades_faltantes) AS unidades FROM public.pedido_linea l
             WHERE l.pedido_comercio_id = p_parte GROUP BY l.oferta_id) x
     WHERE o.id = x.oferta_id AND o.comercio_id = v_comercio AND x.unidades > 0;
    v_hay := EXISTS (SELECT 1 FROM public.pedido_linea l WHERE l.pedido_comercio_id = p_parte
                      AND l.unidades_faltantes < l.cantidad);
    IF v_hay THEN
        UPDATE public.pedido_comercio SET estado = 'lista', lista_en = p_ahora, version = version + 1
         WHERE id = p_parte;
    ELSE
        UPDATE public.pedido_comercio SET estado = 'cancelada', cancelada_en = p_ahora,
               motivo_cancelacion = 'producto_faltante', version = version + 1
         WHERE id = p_parte;
    END IF;
    PERFORM set_config('app.funcion', '', true);
    RETURN CASE WHEN v_hay THEN 'lista' ELSE 'cancelada' END;
END $$;

-- El código de retiro (D-63-4): el hash llega en el cuerpo, nunca el código. Un intento fallido queda contado (la
-- función no lanza). Vacía el hash al usarse, al vencer o al bloquearse. Devuelve el resultado y los intentos que
-- quedan: correcto, no_es, bloqueado, vencido, usado, cancelada, sin_codigo, estado o no_encontrada
CREATE FUNCTION comercio_validar_codigo(p_parte uuid, p_hash text, p_ahora timestamptz)
    RETURNS TABLE (resultado text, intentos_restantes integer)
    LANGUAGE plpgsql VOLATILE {DEFINIDOR} AS
$$
DECLARE
    v_comercio uuid := public.comercio_exigir_sesion();
    v_parte public.pedido_comercio%ROWTYPE;
    v_resultado text;
    v_intentos integer;
BEGIN
    PERFORM set_config('app.funcion', 'comercio', true);
    SELECT * INTO v_parte FROM public.pedido_comercio pc
     WHERE pc.id = p_parte AND pc.comercio_id = v_comercio AND pc.enviado_en IS NOT NULL FOR UPDATE;
    v_intentos := 5 - COALESCE(v_parte.codigo_intentos, 0);
    IF v_parte.id IS NULL THEN
        v_resultado := 'no_encontrada';
    ELSIF v_parte.estado = 'cancelada' THEN
        v_resultado := 'cancelada';
    ELSIF v_parte.estado = 'retirada' OR v_parte.codigo_usado_en IS NOT NULL THEN
        v_resultado := 'usado';
    ELSIF v_parte.estado <> 'lista' THEN
        v_resultado := 'estado';
    ELSIF v_parte.codigo_bloqueado_en IS NOT NULL THEN
        v_resultado := 'bloqueado';
        v_intentos := 0;
    ELSIF v_parte.codigo_expira_en IS NULL THEN
        v_resultado := 'sin_codigo';
    ELSIF v_parte.codigo_hash IS NULL OR v_parte.codigo_expira_en <= p_ahora THEN
        UPDATE public.pedido_comercio SET codigo_hash = NULL WHERE id = p_parte AND codigo_hash IS NOT NULL;
        v_resultado := 'vencido';
    ELSIF v_parte.codigo_hash = p_hash THEN
        UPDATE public.pedido_comercio SET codigo_hash = NULL, codigo_usado_en = p_ahora, estado = 'retirada',
               retirada_en = p_ahora, version = version + 1
         WHERE id = p_parte;
        v_resultado := 'correcto';
    ELSE
        v_intentos := v_intentos - 1;
        IF v_intentos <= 0 THEN
            UPDATE public.pedido_comercio SET codigo_intentos = 5, codigo_hash = NULL, codigo_bloqueado_en = p_ahora
             WHERE id = p_parte;
            v_resultado := 'bloqueado';
            v_intentos := 0;
        ELSE
            UPDATE public.pedido_comercio SET codigo_intentos = codigo_intentos + 1 WHERE id = p_parte;
            v_resultado := 'no_es';
        END IF;
    END IF;
    PERFORM set_config('app.funcion', '', true);
    RETURN QUERY SELECT v_resultado, v_intentos;
END $$;

-- Los productos del comercio: precio, stock, lo apartado y si lo ofrece (D-63-7, O5)
CREATE FUNCTION comercio_existencias(p_ahora timestamptz)
    RETURNS TABLE (oferta_id uuid, producto_nombre text, presentacion text, precio bigint, stock integer,
                   apartado integer, disponible boolean, actualizado_en timestamptz)
    LANGUAGE plpgsql VOLATILE {DEFINIDOR} AS
$$
DECLARE
    v_comercio uuid := public.comercio_exigir_sesion();
BEGIN
    PERFORM set_config('app.funcion', 'disponible', true);
    RETURN QUERY
        SELECT o.id, pr.nombre, pr.presentacion, o.precio, o.stock,
               public.oferta_apartado(o.id, p_ahora, NULL), o.disponible, o.actualizado_en
          FROM public.oferta o JOIN public.producto pr ON pr.id = o.producto_id
         WHERE o.comercio_id = v_comercio
         ORDER BY pr.nombre, pr.presentacion, o.id;
    PERFORM set_config('app.funcion', '', true);
END $$;

-- Lo que queda para confirmar un pedido (D-63-7): stock menos lo apartado por otras familias. Solo con el grupo de la
-- familia que confirma
CREATE FUNCTION oferta_disponible(p_comercios uuid[], p_ahora timestamptz)
    RETURNS TABLE (comercio_id uuid, producto_id uuid, disponible integer)
    LANGUAGE plpgsql VOLATILE {DEFINIDOR} AS
$$
DECLARE
    v_grupo uuid := public.app_grupo();
BEGIN
    IF v_grupo IS NULL OR public.app_comercio() IS NOT NULL THEN
        RAISE EXCEPTION 'oferta_disponible exige el grupo de la familia' USING ERRCODE = 'insufficient_privilege';
    END IF;
    PERFORM set_config('app.funcion', 'disponible', true);
    RETURN QUERY
        SELECT o.comercio_id, o.producto_id, GREATEST(o.stock - public.oferta_apartado(o.id, p_ahora, v_grupo), 0)
          FROM public.oferta o
          JOIN public.producto p ON p.id = o.producto_id
          JOIN public.comercio co ON co.id = o.comercio_id
         WHERE o.disponible AND p.activo AND NOT p.requiere_receta AND co.estado = 'activo'
           AND o.comercio_id = ANY(p_comercios);
    PERFORM set_config('app.funcion', '', true);
END $$;

-- La parte de una acción del comercio, para que el sistema lleve el pedido: solo ids (como pago_resolver_venta)
CREATE FUNCTION despacho_resolver_parte(p_parte uuid) RETURNS TABLE (pedido_id uuid, grupo_id uuid)
    LANGUAGE plpgsql VOLATILE {DEFINIDOR} AS
$$
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'sistema' OR public.app_grupo() IS NOT NULL
       OR public.app_usuario() IS NOT NULL OR public.app_comercio() IS NOT NULL THEN
        RAISE EXCEPTION 'despacho_resolver_parte exige app.rol = sistema, sin grupo, cuenta ni comercio'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    PERFORM set_config('app.funcion', 'despacho', true);
    RETURN QUERY SELECT pc.pedido_id, pc.grupo_id FROM public.pedido_comercio pc WHERE pc.id = p_parte;
    PERFORM set_config('app.funcion', '', true);
END $$;

-- Lo que el sistema tiene que llevar: pedidos pagados cuyo estado quedó atrás de sus partes, o con faltantes sin
-- devolver. Solo ids. Para matu_scheduler con app.rol = 'operacion'
CREATE FUNCTION despacho_pendiente(p_cantidad integer) RETURNS TABLE (pedido_id uuid, grupo_id uuid)
    LANGUAGE plpgsql VOLATILE {DEFINIDOR} AS
$$
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'despacho_pendiente exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_cantidad IS NULL OR p_cantidad < 1 OR p_cantidad > 500 THEN
        RAISE EXCEPTION 'cantidad fuera de rango' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    PERFORM set_config('app.funcion', 'despacho', true);
    RETURN QUERY
        SELECT p.id, p.grupo_id FROM public.pedido p
         WHERE p.pagado_en IS NOT NULL AND p.estado IN ('pagado', 'enviado_a_comercio', 'preparando', 'listo_retiro')
           AND (p.estado = 'pagado'
                OR (p.estado = 'enviado_a_comercio' AND EXISTS (SELECT 1 FROM public.pedido_comercio pc
                     WHERE pc.pedido_id = p.id AND pc.estado <> 'enviada'))
                OR (p.estado = 'preparando' AND NOT EXISTS (SELECT 1 FROM public.pedido_comercio pc
                     WHERE pc.pedido_id = p.id AND pc.estado IN ('enviada', 'preparando')))
                OR (p.estado = 'listo_retiro' AND NOT EXISTS (SELECT 1 FROM public.pedido_comercio pc
                     WHERE pc.pedido_id = p.id AND pc.estado IN ('enviada', 'preparando', 'lista')))
                OR EXISTS (SELECT 1 FROM public.pedido_linea l JOIN public.pedido_comercio pc
                             ON pc.id = l.pedido_comercio_id
                            WHERE l.pedido_id = p.id AND pc.estado IN ('lista', 'retirada', 'cancelada')
                              AND l.monto_devuelto < l.unidades_faltantes * l.precio_unitario))
         ORDER BY p.pagado_en, p.id
         LIMIT p_cantidad;
    PERFORM set_config('app.funcion', '', true);
END $$;
"""

FIRMAS_APP = (
    "comercio_partes(timestamptz)",
    "comercio_lineas(uuid)",
    "comercio_preparar(uuid, integer, timestamptz)",
    "comercio_marcar_linea(uuid, uuid, text, integer, integer)",
    "comercio_listo(uuid, integer, timestamptz)",
    "comercio_validar_codigo(uuid, text, timestamptz)",
    "comercio_existencias(timestamptz)",
    "oferta_disponible(uuid[], timestamptz)",
    "despacho_resolver_parte(uuid)",
)
PERMISOS_FUNCIONES = "\n".join(
    f"REVOKE ALL ON FUNCTION {f} FROM PUBLIC;\nGRANT EXECUTE ON FUNCTION {f} TO matu_app;" for f in FIRMAS_APP
) + (
    "\nREVOKE ALL ON FUNCTION despacho_pendiente(integer) FROM PUBLIC;"
    "\nGRANT EXECUTE ON FUNCTION despacho_pendiente(integer) TO matu_scheduler;"
)

UPGRADE = f"""
SELECT set_config('app.rol', 'operacion', true);

-- (a) El comercio deja de leer y escribir tablas del pedido (D-63-1, D-63-2)
DROP POLICY pedido_comercio_ver ON pedido;
DROP POLICY pedido_comercio_actualizar ON pedido;
DROP POLICY pedido_comercio_propio ON pedido_comercio;
DROP POLICY linea_comercio_ver ON pedido_linea;

-- (b) La parte por comercio: estado, versión, código y apartado (D-63-3, D-63-4, D-63-7)
ALTER TABLE pedido_comercio
    ADD COLUMN estado              text NOT NULL DEFAULT 'enviada'
        CHECK (estado IN ('enviada', 'preparando', 'lista', 'retirada', 'cancelada')),
    ADD COLUMN version             integer NOT NULL DEFAULT 1 CHECK (version > 0),
    ADD COLUMN preparando_en       timestamptz,
    ADD COLUMN lista_en            timestamptz,
    ADD COLUMN retirada_en         timestamptz,
    ADD COLUMN cancelada_en        timestamptz,
    ADD COLUMN motivo_cancelacion  text CHECK (motivo_cancelacion IN ('producto_faltante', 'familia_cancela')),
    ADD COLUMN codigo_hash         text CHECK (codigo_hash ~ '^[0-9a-f]{{64}}$'),
    ADD COLUMN codigo_generado_en  timestamptz,
    ADD COLUMN codigo_expira_en    timestamptz,
    ADD COLUMN codigo_usado_en     timestamptz,
    ADD COLUMN codigo_intentos     smallint NOT NULL DEFAULT 0 CHECK (codigo_intentos BETWEEN 0 AND 5),
    ADD COLUMN codigo_bloqueado_en timestamptz,
    ADD COLUMN apartado_hasta      timestamptz;
ALTER TABLE pedido_comercio
    ADD CONSTRAINT pedido_comercio_estado_enviada CHECK (estado = 'enviada' OR enviado_en IS NOT NULL),
    ADD CONSTRAINT pedido_comercio_retirada CHECK ((estado = 'retirada') = (retirada_en IS NOT NULL)),
    ADD CONSTRAINT pedido_comercio_cancelada
        CHECK ((estado = 'cancelada') = (cancelada_en IS NOT NULL AND motivo_cancelacion IS NOT NULL)),
    ADD CONSTRAINT pedido_comercio_codigo_vence
        CHECK ((codigo_generado_en IS NULL) = (codigo_expira_en IS NULL)
               AND (codigo_hash IS NULL OR codigo_expira_en IS NOT NULL)
               AND (codigo_expira_en IS NULL OR codigo_expira_en > codigo_generado_en)),
    ADD CONSTRAINT pedido_comercio_codigo_en_lista
        CHECK (codigo_generado_en IS NULL OR estado IN ('lista', 'retirada', 'cancelada')),
    ADD CONSTRAINT pedido_comercio_apartado
        CHECK (apartado_hasta IS NULL OR apartado_hasta <= creado_en + interval '1 hour');
-- (c) El apartado de una oferta
{APARTADO}

-- (d) Las unidades que faltan (D-63-8) y la devolución parcial
ALTER TABLE pedido_linea ADD COLUMN unidades_faltantes integer NOT NULL DEFAULT 0;
ALTER TABLE pedido_linea ADD CONSTRAINT pedido_linea_faltantes
    CHECK (unidades_faltantes BETWEEN 0 AND cantidad AND (unidades_faltantes = 0 OR estado_linea <> 'preparada'));
ALTER TABLE pedido_linea DROP CONSTRAINT pedido_linea_devuelta;
ALTER TABLE pedido_linea ADD CONSTRAINT pedido_linea_devuelta CHECK (
    (devuelta_en IS NOT NULL) = (monto_devuelto > 0) AND (estado_linea <> 'devuelta' OR monto_devuelto > 0));

-- (h) Después del pago, el pedido lo mueven solo el sistema y operación
ALTER TABLE pedido ADD COLUMN entregado_en timestamptz;
ALTER TABLE pedido ADD CONSTRAINT pedido_entregado_en
    CHECK (entregado_en IS NULL OR estado IN ('entregado', 'cerrado'));
CREATE OR REPLACE FUNCTION pedido_escritura_del_pago() RETURNS trigger LANGUAGE plpgsql AS
$${ESCRITURA_0029}$$;
ALTER POLICY linea_editar ON pedido_linea USING ({LINEA_ESCRIBE_0029}) WITH CHECK ({LINEA_ESCRIBE_0029});
ALTER POLICY pedido_comercio_familia_borrar ON pedido_comercio USING ({PARTE_BORRA_0029});

-- (i) La parte la actualizan el sistema (con el grupo) y operación
CREATE POLICY pedido_comercio_sistema_editar ON pedido_comercio FOR UPDATE
    USING (grupo_id = app_grupo() AND {SISTEMA}) WITH CHECK (grupo_id = app_grupo() AND {SISTEMA});
CREATE POLICY pedido_comercio_operacion_editar ON pedido_comercio FOR UPDATE
    USING (app_rol() = 'operacion') WITH CHECK (app_rol() = 'operacion');
-- (b) O6: la referencia se dicta. Las de antes (16 a 64 caracteres) se rehacen
ALTER TABLE pedido_comercio DROP CONSTRAINT pedido_comercio_referencia_check;
UPDATE pedido_comercio SET referencia = (
    SELECT string_agg(substr('{ALFABETO}', 1 + floor(random() * {len(ALFABETO)})::integer, 1), '')
      FROM generate_series(1, 6 + 0 * length(pedido_comercio.id::text)));
ALTER TABLE pedido_comercio ADD CONSTRAINT pedido_comercio_referencia_forma
    CHECK (referencia ~ '^[2-9A-HJKMNP-Z]{{6}}$');
-- Dentro de las funciones del comercio: solo las partes de su comercio, ya enviadas
CREATE POLICY pedido_comercio_funcion_comercio ON pedido_comercio FOR SELECT TO matu_owner
    USING ({FUNCION} = 'comercio' AND comercio_id = app_comercio() AND enviado_en IS NOT NULL);
CREATE POLICY pedido_comercio_funcion_comercio_editar ON pedido_comercio FOR UPDATE TO matu_owner
    USING ({FUNCION} = 'comercio' AND comercio_id = app_comercio() AND enviado_en IS NOT NULL)
    WITH CHECK ({FUNCION} = 'comercio' AND comercio_id = app_comercio() AND enviado_en IS NOT NULL);
CREATE POLICY pedido_comercio_funcion_leer ON pedido_comercio FOR SELECT TO matu_owner
    USING ({FUNCION} IN ('disponible', 'despacho'));
CREATE POLICY linea_funcion_comercio ON pedido_linea FOR SELECT TO matu_owner
    USING ({FUNCION} = 'comercio' AND EXISTS (SELECT 1 FROM pedido_comercio pc
           WHERE pc.id = pedido_linea.pedido_comercio_id AND pc.comercio_id = app_comercio()));
CREATE POLICY linea_funcion_comercio_editar ON pedido_linea FOR UPDATE TO matu_owner
    USING ({FUNCION} = 'comercio' AND EXISTS (SELECT 1 FROM pedido_comercio pc
           WHERE pc.id = pedido_linea.pedido_comercio_id AND pc.comercio_id = app_comercio()
             AND pc.estado = 'preparando'))
    WITH CHECK ({FUNCION} = 'comercio');
CREATE POLICY linea_funcion_leer ON pedido_linea FOR SELECT TO matu_owner
    USING ({FUNCION} IN ('disponible', 'despacho'));
CREATE POLICY pedido_funcion_leer ON pedido FOR SELECT TO matu_owner
    USING ({FUNCION} IN ('disponible', 'despacho')
           OR ({FUNCION} = 'comercio' AND EXISTS (SELECT 1 FROM pedido_comercio pc
               WHERE pc.pedido_id = pedido.id AND pc.comercio_id = app_comercio())));
-- Solo para bloquear el pedido (FOR UPDATE) al empezar a preparar: nunca escribe
CREATE POLICY pedido_funcion_bloquear ON pedido FOR UPDATE TO matu_owner
    USING ({FUNCION} = 'comercio' AND EXISTS (SELECT 1 FROM pedido_comercio pc
           WHERE pc.pedido_id = pedido.id AND pc.comercio_id = app_comercio()))
    WITH CHECK (false);
CREATE POLICY oferta_funcion_comercio ON oferta FOR UPDATE TO matu_owner
    USING ({FUNCION} = 'comercio' AND comercio_id = app_comercio())
    WITH CHECK ({FUNCION} = 'comercio' AND comercio_id = app_comercio());

-- (n) El comercio cambia solo stock y disponible de sus ofertas
CREATE FUNCTION oferta_comercio_acotada() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF app_comercio() IS NOT NULL AND (NEW.id, NEW.producto_id, NEW.comercio_id, NEW.precio)
       IS DISTINCT FROM (OLD.id, OLD.producto_id, OLD.comercio_id, OLD.precio) THEN
        RAISE EXCEPTION 'el comercio cambia solo el stock y si lo ofrece' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER oferta_comercio_acotada BEFORE UPDATE ON oferta
    FOR EACH ROW EXECUTE FUNCTION oferta_comercio_acotada();
ALTER TABLE oferta ADD CONSTRAINT oferta_stock_tope CHECK (stock <= 9999);

-- (e) El retracto (D-63-10)
CREATE TABLE retracto (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    grupo_id       uuid NOT NULL REFERENCES grupo_familiar(id),
    pedido_id      uuid NOT NULL REFERENCES pedido(id) ON DELETE CASCADE,
    solicitado_por uuid NOT NULL,
    solicitado_en  timestamptz NOT NULL,
    plazo_hasta    timestamptz NOT NULL,
    incluye_envio  boolean NOT NULL,
    estado         text NOT NULL DEFAULT 'solicitado' CHECK (estado IN ('solicitado', 'devuelto', 'rechazado')),
    resuelto_en    timestamptz,
    resuelto_por   uuid,
    CONSTRAINT retracto_resuelto CHECK ((estado = 'solicitado') = (resuelto_en IS NULL)),
    CONSTRAINT retracto_en_plazo CHECK (solicitado_en <= plazo_hasta)
);
CREATE INDEX retracto_pedido_ix ON retracto (pedido_id);
CREATE TABLE retracto_linea (
    retracto_id     uuid NOT NULL REFERENCES retracto(id) ON DELETE CASCADE,
    grupo_id        uuid NOT NULL REFERENCES grupo_familiar(id),
    pedido_linea_id uuid NOT NULL REFERENCES pedido_linea(id) ON DELETE CASCADE,
    cantidad        integer NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (retracto_id, pedido_linea_id),
    CONSTRAINT retracto_linea_una_vez UNIQUE (pedido_linea_id)
);
ALTER TABLE retracto ENABLE ROW LEVEL SECURITY;
ALTER TABLE retracto FORCE ROW LEVEL SECURITY;
ALTER TABLE retracto_linea ENABLE ROW LEVEL SECURITY;
ALTER TABLE retracto_linea FORCE ROW LEVEL SECURITY;
CREATE FUNCTION retracto_linea_del_pedido() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM retracto r JOIN pedido_linea l ON l.pedido_id = r.pedido_id
                    WHERE r.id = NEW.retracto_id AND r.grupo_id = NEW.grupo_id AND l.id = NEW.pedido_linea_id
                      AND NEW.cantidad <= l.cantidad - l.unidades_faltantes) THEN
        RAISE EXCEPTION 'la línea es del pedido del retracto, hasta lo entregado' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER retracto_linea_del_pedido BEFORE INSERT OR UPDATE ON retracto_linea
    FOR EACH ROW EXECUTE FUNCTION retracto_linea_del_pedido();
CREATE FUNCTION retracto_del_grupo() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pedido p WHERE p.id = NEW.pedido_id AND p.grupo_id = NEW.grupo_id
                      AND p.entregado_en IS NOT NULL) THEN
        RAISE EXCEPTION 'el retracto es de un pedido entregado de su grupo' USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'UPDATE' AND (NEW.grupo_id, NEW.pedido_id, NEW.solicitado_por, NEW.solicitado_en, NEW.plazo_hasta,
                             NEW.incluye_envio) IS DISTINCT FROM (OLD.grupo_id, OLD.pedido_id, OLD.solicitado_por,
                             OLD.solicitado_en, OLD.plazo_hasta, OLD.incluye_envio) THEN
        RAISE EXCEPTION 'lo pedido en el retracto no cambia' USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.estado <> 'solicitado' AND NEW.estado IS DISTINCT FROM OLD.estado THEN
        RAISE EXCEPTION 'un retracto resuelto no cambia' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER retracto_del_grupo BEFORE INSERT OR UPDATE ON retracto
    FOR EACH ROW EXECUTE FUNCTION retracto_del_grupo();
-- Pide el admin, o quien pagó si sigue en el grupo (D-63-10). Leen admin, cuidador y pagador
CREATE POLICY retracto_familia_leer ON retracto FOR SELECT USING (grupo_id = app_grupo() AND (SELECT app_ve_entrega()));
CREATE POLICY retracto_familia_crear ON retracto FOR INSERT WITH CHECK (
    grupo_id = app_grupo() AND solicitado_por = app_usuario() AND estado = 'solicitado'
    AND ((SELECT app_es_admin()) OR ((SELECT app_ve_entrega()) AND EXISTS (
        SELECT 1 FROM cargo c JOIN participacion pa ON pa.cargo_id = c.id
         WHERE c.pedido_id = retracto.pedido_id AND pa.usuario_id = app_usuario() AND pa.monto_cobrado > 0))));
CREATE POLICY retracto_sistema_leer ON retracto FOR SELECT USING (grupo_id = app_grupo() AND {SISTEMA});
CREATE POLICY retracto_sistema_editar ON retracto FOR UPDATE
    USING (grupo_id = app_grupo() AND {SISTEMA}) WITH CHECK (grupo_id = app_grupo() AND {SISTEMA});
CREATE POLICY retracto_operacion_leer ON retracto FOR SELECT USING (app_rol() = 'operacion');
CREATE POLICY retracto_operacion_editar ON retracto FOR UPDATE
    USING (app_rol() = 'operacion') WITH CHECK (app_rol() = 'operacion');
CREATE POLICY retracto_linea_familia_leer ON retracto_linea FOR SELECT
    USING (grupo_id = app_grupo() AND (SELECT app_ve_entrega()));
CREATE POLICY retracto_linea_familia_crear ON retracto_linea FOR INSERT WITH CHECK (
    grupo_id = app_grupo() AND EXISTS (SELECT 1 FROM retracto r WHERE r.id = retracto_linea.retracto_id
                                        AND r.solicitado_por = app_usuario() AND r.estado = 'solicitado'));
CREATE POLICY retracto_linea_sistema_leer ON retracto_linea FOR SELECT USING (grupo_id = app_grupo() AND {SISTEMA});
CREATE POLICY retracto_linea_operacion_leer ON retracto_linea FOR SELECT USING (app_rol() = 'operacion');
REVOKE ALL ON retracto, retracto_linea FROM matu_app;
GRANT SELECT, INSERT, UPDATE ON retracto TO matu_app;
GRANT SELECT, INSERT ON retracto_linea TO matu_app;

ALTER TABLE transaccion_pasarela DROP CONSTRAINT transaccion_pasarela_motivo_anulacion_check;
ALTER TABLE transaccion_pasarela ADD CONSTRAINT transaccion_pasarela_motivo_anulacion_check
    CHECK (motivo_anulacion IN ('pago_tardio', 'producto_no_entregado', 'cancelacion', 'retracto'));
ALTER TABLE transaccion_pasarela ADD COLUMN retracto_id uuid REFERENCES retracto(id);
ALTER TABLE transaccion_pasarela ADD CONSTRAINT transaccion_retracto_de_anulacion
    CHECK (retracto_id IS NULL OR motivo_anulacion = 'retracto');
DROP INDEX transaccion_linea_devuelta_uq;
CREATE UNIQUE INDEX transaccion_linea_devuelta_uq ON transaccion_pasarela (pedido_linea_id, motivo_anulacion)
    WHERE pedido_linea_id IS NOT NULL;
CREATE UNIQUE INDEX transaccion_envio_retracto_uq ON transaccion_pasarela (retracto_id)
    WHERE retracto_id IS NOT NULL AND pedido_linea_id IS NULL;

-- (f) D-63-14: una cuenta de comercio no es miembro de un grupo, y al revés
CREATE FUNCTION cuenta_comercio_o_familia() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    -- La de quien llama (por ejemplo la invitación de la 0026): se devuelve al terminar
    v_antes text := current_setting('app.funcion', true);
    v_choca boolean;
BEGIN
    PERFORM set_config('app.funcion', 'cuentas', true);
    IF TG_TABLE_NAME = 'membresia' THEN
        v_choca := NEW.estado = 'activa' AND EXISTS (SELECT 1 FROM public.usuario_comercio uc
                                                     WHERE uc.usuario_id = NEW.usuario_id AND uc.activo);
    ELSE
        v_choca := NEW.activo AND EXISTS (SELECT 1 FROM public.membresia m
                                          WHERE m.usuario_id = NEW.usuario_id AND m.estado = 'activa');
    END IF;
    PERFORM set_config('app.funcion', COALESCE(v_antes, ''), true);
    IF v_choca THEN
        RAISE EXCEPTION 'una cuenta de comercio no es miembro de un grupo' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION cuenta_comercio_o_familia() FROM PUBLIC;
-- La sesión de familia no ve usuario_comercio ni la del comercio ve membresia: la función lee como matu_owner
CREATE POLICY usuario_comercio_cuentas ON usuario_comercio FOR SELECT TO matu_owner
    USING ({FUNCION} = 'cuentas');
CREATE POLICY membresia_cuentas ON membresia FOR SELECT TO matu_owner USING ({FUNCION} = 'cuentas');
CREATE TRIGGER membresia_no_comercio BEFORE INSERT OR UPDATE ON membresia
    FOR EACH ROW EXECUTE FUNCTION cuenta_comercio_o_familia();
CREATE TRIGGER usuario_comercio_no_familia BEFORE INSERT OR UPDATE ON usuario_comercio
    FOR EACH ROW EXECUTE FUNCTION cuenta_comercio_o_familia();

-- (g) D-63-15: sin ubicación en la evidencia
UPDATE evidencia SET lat = NULL, lng = NULL WHERE lat IS NOT NULL OR lng IS NOT NULL;
ALTER TABLE evidencia ADD CONSTRAINT evidencia_sin_ubicacion CHECK (lat IS NULL AND lng IS NULL);

-- (j) consumo_comercio (RF-31): una fila por parte, la boleta pendiente; el comercio solo lee
DROP POLICY consumo_comercio_propio ON consumo_comercio;
CREATE POLICY consumo_comercio_propio_leer ON consumo_comercio FOR SELECT USING (comercio_id = app_comercio());
ALTER TABLE consumo_comercio ADD COLUMN pedido_comercio_id uuid REFERENCES pedido_comercio(id);
ALTER TABLE consumo_comercio ADD CONSTRAINT consumo_comercio_parte_uq UNIQUE (pedido_comercio_id);
ALTER TABLE consumo_comercio DROP CONSTRAINT consumo_comercio_pedido_id_key;
ALTER TABLE consumo_comercio ALTER COLUMN monto_boleta DROP NOT NULL;
ALTER TABLE consumo_comercio ALTER COLUMN folio_boleta DROP NOT NULL;

-- (k) La línea de tiempo del despacho
ALTER TABLE pedido_transicion DROP CONSTRAINT pedido_transicion_motivo;
ALTER TABLE pedido_transicion ADD CONSTRAINT pedido_transicion_motivo
    CHECK (motivo IS NULL OR motivo IN ({MOTIVOS_0029}));
ALTER POLICY transicion_sistema_crear ON pedido_transicion WITH CHECK (
    app_rol() IN ('sistema', 'operacion') AND app_usuario() IS NULL
    AND actor_tipo IN ('sistema', 'operacion', 'comercio', 'usuario')
    AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = pedido_transicion.pedido_id));

-- (l) La auditoría del comercio
ALTER TABLE auditoria DROP CONSTRAINT auditoria_cuenta_acotada;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_cuenta_acotada
    CHECK (grupo_id IS NOT NULL OR accion IN ({_lista(SIN_GRUPO_0029)})) NOT VALID;
ALTER TABLE auditoria VALIDATE CONSTRAINT auditoria_cuenta_acotada;
ALTER TABLE auditoria DROP CONSTRAINT auditoria_persona_obligatoria;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_persona_obligatoria
    CHECK (persona_cuidada_id IS NOT NULL OR accion NOT IN ({_lista(ACCIONES_DE_PERSONA_0029)})) NOT VALID;
CREATE POLICY auditoria_comercio_propia ON auditoria AS RESTRICTIVE FOR INSERT TO matu_app WITH CHECK (
    app_comercio() IS NULL
    OR (actor_tipo = 'comercio' AND grupo_id IS NULL AND persona_cuidada_id IS NULL AND actor_ref = app_usuario()));

-- (a) y (m) Las funciones
{EXIGIR_SESION}
{FUNCIONES_COMERCIO}
{PERMISOS_FUNCIONES}

SELECT set_config('app.rol', '', true);
"""

DOWNGRADE = f"""
SELECT set_config('app.rol', 'operacion', true);

-- (a) y (m)
DROP FUNCTION despacho_pendiente(integer);
DROP FUNCTION despacho_resolver_parte(uuid);
DROP FUNCTION oferta_disponible(uuid[], timestamptz);
DROP FUNCTION comercio_existencias(timestamptz);
DROP FUNCTION comercio_validar_codigo(uuid, text, timestamptz);
DROP FUNCTION comercio_listo(uuid, integer, timestamptz);
DROP FUNCTION comercio_marcar_linea(uuid, uuid, text, integer, integer);
DROP FUNCTION comercio_preparar(uuid, integer, timestamptz);
DROP FUNCTION comercio_lineas(uuid);
DROP FUNCTION comercio_partes(timestamptz);
DROP FUNCTION comercio_exigir_sesion();

-- (l)
DROP POLICY auditoria_comercio_propia ON auditoria;
ALTER TABLE auditoria DROP CONSTRAINT auditoria_persona_obligatoria;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_persona_obligatoria
    CHECK (persona_cuidada_id IS NOT NULL OR accion NOT IN ({_lista(ACCIONES_DE_PERSONA_0028)})) NOT VALID;
-- Con filas del comercio (sin grupo), vuelve NOT VALID: nunca se borra un registro de auditoría
ALTER TABLE auditoria DROP CONSTRAINT auditoria_cuenta_acotada;
DO $$ BEGIN
    BEGIN
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_cuenta_acotada
            CHECK (grupo_id IS NOT NULL OR accion IN ({_lista(ACCIONES_DE_CUENTA_0028)}));
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'MATU-63: hay acciones del comercio en la auditoría; el CHECK de la 0028 vuelve NOT VALID';
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_cuenta_acotada
            CHECK (grupo_id IS NOT NULL OR accion IN ({_lista(ACCIONES_DE_CUENTA_0028)})) NOT VALID;
    END;
END $$;

-- (k)
ALTER POLICY transicion_sistema_crear ON pedido_transicion WITH CHECK (
    app_rol() IN ('sistema', 'operacion') AND app_usuario() IS NULL AND actor_tipo IN ('sistema', 'operacion')
    AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = pedido_transicion.pedido_id));
ALTER TABLE pedido_transicion DROP CONSTRAINT pedido_transicion_motivo;
ALTER TABLE pedido_transicion ADD CONSTRAINT pedido_transicion_motivo
    CHECK (motivo IS NULL OR motivo IN ({MOTIVOS_0024}));

-- (j)
ALTER TABLE consumo_comercio ALTER COLUMN folio_boleta SET NOT NULL;
ALTER TABLE consumo_comercio ALTER COLUMN monto_boleta SET NOT NULL;
ALTER TABLE consumo_comercio ADD CONSTRAINT consumo_comercio_pedido_id_key UNIQUE (pedido_id);
ALTER TABLE consumo_comercio DROP CONSTRAINT consumo_comercio_parte_uq;
ALTER TABLE consumo_comercio DROP COLUMN pedido_comercio_id;
DROP POLICY consumo_comercio_propio_leer ON consumo_comercio;
CREATE POLICY consumo_comercio_propio ON consumo_comercio USING (comercio_id = app_comercio());

-- (g)
ALTER TABLE evidencia DROP CONSTRAINT evidencia_sin_ubicacion;

-- (f)
DROP TRIGGER usuario_comercio_no_familia ON usuario_comercio;
DROP TRIGGER membresia_no_comercio ON membresia;
DROP POLICY membresia_cuentas ON membresia;
DROP POLICY usuario_comercio_cuentas ON usuario_comercio;
DROP FUNCTION cuenta_comercio_o_familia();

-- (e)
DROP INDEX transaccion_envio_retracto_uq;
DROP INDEX transaccion_linea_devuelta_uq;
CREATE UNIQUE INDEX transaccion_linea_devuelta_uq ON transaccion_pasarela (pedido_linea_id)
    WHERE pedido_linea_id IS NOT NULL;
ALTER TABLE transaccion_pasarela DROP CONSTRAINT transaccion_retracto_de_anulacion;
ALTER TABLE transaccion_pasarela DROP COLUMN retracto_id;
ALTER TABLE transaccion_pasarela DROP CONSTRAINT transaccion_pasarela_motivo_anulacion_check;
ALTER TABLE transaccion_pasarela ADD CONSTRAINT transaccion_pasarela_motivo_anulacion_check
    CHECK (motivo_anulacion IN ('pago_tardio', 'producto_no_entregado', 'cancelacion'));
DROP TABLE retracto_linea;
DROP TABLE retracto;
DROP FUNCTION retracto_del_grupo();
DROP FUNCTION retracto_linea_del_pedido();

-- (n)
ALTER TABLE oferta DROP CONSTRAINT oferta_stock_tope;
DROP TRIGGER oferta_comercio_acotada ON oferta;
DROP FUNCTION oferta_comercio_acotada();

-- (i)
-- (b) Antes de quitar la política de operación que la deja escribir
ALTER TABLE pedido_comercio DROP CONSTRAINT pedido_comercio_referencia_forma;
UPDATE pedido_comercio SET referencia = md5(random()::text || id::text);
ALTER TABLE pedido_comercio ADD CONSTRAINT pedido_comercio_referencia_check
    CHECK (length(referencia) BETWEEN 16 AND 64);
DROP POLICY oferta_funcion_comercio ON oferta;
DROP POLICY pedido_funcion_bloquear ON pedido;
DROP POLICY pedido_funcion_leer ON pedido;
DROP POLICY linea_funcion_leer ON pedido_linea;
DROP POLICY linea_funcion_comercio_editar ON pedido_linea;
DROP POLICY linea_funcion_comercio ON pedido_linea;
DROP POLICY pedido_comercio_funcion_leer ON pedido_comercio;
DROP POLICY pedido_comercio_funcion_comercio_editar ON pedido_comercio;
DROP POLICY pedido_comercio_funcion_comercio ON pedido_comercio;
DROP POLICY pedido_comercio_operacion_editar ON pedido_comercio;
DROP POLICY pedido_comercio_sistema_editar ON pedido_comercio;

-- (h)
ALTER POLICY pedido_comercio_familia_borrar ON pedido_comercio USING ({PARTE_BORRA_0023});
ALTER POLICY linea_editar ON pedido_linea USING ({LINEA_ESCRIBE_0023}) WITH CHECK ({LINEA_ESCRIBE_0023});
CREATE OR REPLACE FUNCTION pedido_escritura_del_pago() RETURNS trigger LANGUAGE plpgsql AS
$${ESCRITURA_0024}$$;
ALTER TABLE pedido DROP CONSTRAINT pedido_entregado_en;
ALTER TABLE pedido DROP COLUMN entregado_en;

-- (d)
ALTER TABLE pedido_linea DROP CONSTRAINT pedido_linea_devuelta;
ALTER TABLE pedido_linea ADD CONSTRAINT pedido_linea_devuelta CHECK (
    (estado_linea = 'devuelta') = (devuelta_en IS NOT NULL) AND (estado_linea = 'devuelta') = (monto_devuelto > 0));
ALTER TABLE pedido_linea DROP CONSTRAINT pedido_linea_faltantes;
ALTER TABLE pedido_linea DROP COLUMN unidades_faltantes;

-- (c)
DROP FUNCTION oferta_apartado(uuid, timestamptz, uuid);

-- (b)
ALTER TABLE pedido_comercio DROP CONSTRAINT pedido_comercio_apartado, DROP CONSTRAINT pedido_comercio_codigo_en_lista,
    DROP CONSTRAINT pedido_comercio_codigo_vence, DROP CONSTRAINT pedido_comercio_cancelada,
    DROP CONSTRAINT pedido_comercio_retirada, DROP CONSTRAINT pedido_comercio_estado_enviada;
ALTER TABLE pedido_comercio DROP COLUMN apartado_hasta, DROP COLUMN codigo_bloqueado_en, DROP COLUMN codigo_intentos,
    DROP COLUMN codigo_usado_en, DROP COLUMN codigo_expira_en, DROP COLUMN codigo_generado_en, DROP COLUMN codigo_hash,
    DROP COLUMN motivo_cancelacion, DROP COLUMN cancelada_en, DROP COLUMN retirada_en, DROP COLUMN lista_en,
    DROP COLUMN preparando_en, DROP COLUMN version, DROP COLUMN estado;

-- (a) Como las dejó la 0023
CREATE POLICY linea_comercio_ver ON pedido_linea FOR SELECT USING (
    EXISTS (SELECT 1 FROM pedido_comercio pc WHERE pc.id = pedido_linea.pedido_comercio_id
            AND pc.comercio_id = app_comercio() AND pc.enviado_en IS NOT NULL));
CREATE POLICY pedido_comercio_propio ON pedido_comercio FOR SELECT
    USING (comercio_id = app_comercio() AND enviado_en IS NOT NULL);
CREATE POLICY pedido_comercio_ver ON pedido FOR SELECT USING (
    pagado_en IS NOT NULL AND estado NOT IN ('borrador', 'total_confirmado', 'vencido', 'pagado')
    AND EXISTS (SELECT 1 FROM pedido_comercio pc WHERE pc.pedido_id = pedido.id
                AND pc.comercio_id = app_comercio() AND pc.enviado_en IS NOT NULL));
CREATE POLICY pedido_comercio_actualizar ON pedido FOR UPDATE USING (
    pagado_en IS NOT NULL AND estado NOT IN ('borrador', 'total_confirmado', 'vencido', 'pagado')
    AND EXISTS (SELECT 1 FROM pedido_comercio pc WHERE pc.pedido_id = pedido.id
                AND pc.comercio_id = app_comercio() AND pc.enviado_en IS NOT NULL));

SELECT set_config('app.rol', '', true);
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

"""MATU-62: el pago del total exacto confirmado con Webpay Plus, venta normal (ADR-027).

Cadena: 0023 (MATU-61) -> 0024. down_revision = "0023" (D-62-1: MATU-62 lleva la 0024 y MATU-55 pasa a la 0025).

Segunda revisión previa del analista (docs/legal/revision-previa-matu-62-segunda.md del repositorio MATU), sección 2,
decisiones D-62-1 a D-62-17, y decisión 245 de docs/api/README.md:

a) app_paga_pedido(): admin o pagador activo del grupo (D-62-8). Pagan admin y pagador; el cuidador y el observador
   no.
b) pedido:
   - condiciones_aceptadas_por (D-62-16), dentro de pedido_condiciones_completas («juntas o ninguna»). Sin llave
     foránea: como auditoria.actor_ref, no impide borrar una cuenta y no se pierde quién aceptó.
   - referencia (decisión 238): 4 a 6 cifras, única por grupo, solo en un pedido pagado. La asigna el sistema.
   - pedido_pago_con_condiciones (0023, NOT VALID) se valida si ninguna fila la viola.
   - trigger pedido_escritura_del_pago: (1) con pagado_en, las condiciones y la referencia quedan fijas (R5); (2)
     marcar pagado lo hacen solo el sistema u operación, desde total_confirmado o vencido, con una venta aprobada y no
     anulada del mismo total y el mismo total_confirmado_en (D-62-4); (3) el sistema y operación, sin una cuenta,
     escriben solo el estado, pagado_en y la referencia; (4) una cuenta que no arma el pedido (el pagador) escribe
     solo las cuatro columnas de las condiciones.
   - políticas de UPDATE nuevas, acotadas por ese trigger: pedido_pagador_condiciones, pedido_sistema_pago y
     pedido_operacion_pago.
c) pedido_transicion: el motivo pago_aprobado (decisión 242) y el actor sistema u operación en las suyas.
d) cargo, participacion y transaccion_pasarela por operación y por rol, sin FOR ALL (sección 2, punto 1): leen admin,
   cuidador y pagador (app_ve_entrega; el observador no); crean admin y pagador (app_paga_pedido), y el pagador
   reabre su cargo y su participación rechazados (D-62-11); actualizan el sistema (la vuelta y la conciliación, con el
   grupo) y operación. REVOKE DELETE a matu_app sobre cargo y participacion (transaccion_pasarela ya lo tenía).
e) Integridad del cobro (sección 2, punto 2):
   - transaccion_pasarela.cargo_id (la venta y su cargo, para las restricciones de abajo), total_confirmado_en,
     session_id, cuotas (P5), motivo_cierre (no_aprobada, usuario_salio, formulario_vencido), retorno_recibido_en (la
     marca del retorno), commit_intentado_en (como mucho un commit cada 10 segundos, decisión 233), cerrada_en,
     anulacion_total (regla 3 de D-62-4 y, en MATU-63, la cancelación), venta_id, motivo_anulacion y pedido_linea_id
     de una anulación, e intentos (D-62-6).
   - transaccion_pago_atado: la venta nace con el monto y el total_confirmado_en del pedido sin pagar; lo que la
     identifica no cambia; una venta aprobada o rechazada no cambia de estado; lo anulado de una venta no supera su
     monto.
   - una sola venta aprobada y no anulada por cargo, el token único de las ventas y una sola anulación por línea.
   - cargo_pago_atado: las transiciones del cargo y de la participación (decisión 243) y, al pasar a pagado, una
     venta aprobada y no anulada por el monto cobrado.
f) R14 (D-62-9): CHECK (payload_respuesta IS NULL) y ultimos4 de cuatro cifras. Antes se vacían.
g) idempotencia.transaccion_id (la venta de la clave, decisión 229) y la política idempotencia_liberar: un 503 de
   pagar libera su clave.
h) pedido_linea: el sistema y operación marcan la devolución de una línea pagada (decisión 239).
i) La conservación (D-62-13, (c), separar por dinero): pedido_conservar se reemplaza. Sin dinero (ninguna venta
   aprobada), el cargo, sus participaciones y sus ventas se borran con el pedido a los 30 días. Con dinero, aunque se
   haya anulado completo, se conservan el pedido sin entrega, el cargo y las transacciones (6 años, PENDIENTE CL-28
   y CL-64, D-62-10), y las líneas, reglas, partes por comercio, entrega, línea de tiempo y claves se borran a los 30
   días. El trigger transaccion_sin_borrado y transicion_solo_insercion dejan borrar solo dentro de pedido_conservar
   (current_user matu_owner y app.conservacion = 'pedidos', que la función fija y limpia).
   Cierre del analista: una venta autorizando también cuenta como dinero (observación 6: el commit pudo cobrar), y
   no se borra; y un pedido con dinero que sigue abierto (borrador, total confirmado o vencido) y queda sin líneas
   pasa a cancelado (observación 5: no deja a la persona con un pedido sin pagar vacío). Solo ese cambio de estado,
   dentro de pedido_conservar, lo admite pedido_escritura_del_pago.
j) pagos_por_conciliar(limite, cantidad), SECURITY DEFINER, solo para matu_scheduler y con app.rol = 'operacion'
   (D-62-5): las ventas autorizando, las iniciadas antes de limite y las anulaciones sin terminar, solo con su id y el
   grupo.
k) pago_resolver_venta(token, orden, sesion), SECURITY DEFINER, para matu_app con app.rol = 'sistema' y sin grupo ni
   cuenta: la vuelta sin sesión encuentra su venta por token, o por buy_order y session_id juntos, y recibe solo el id
   y el grupo (decisión 245).

backend/db/*.sql no se tocan. downgrade() deja el esquema como en 0023. Pierde las columnas nuevas (quién aceptó, la
referencia, los datos de la venta); payload_respuesta y los ultimos4 que no eran cuatro cifras ya se habían vaciado.
Falla si queda una transición con el motivo pago_aprobado (la línea de tiempo es de solo inserción), como la 0023
falla con un pedido sin comercio.

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


MOTIVOS_0023 = (
    "('total_vencio', 'familia_cancela', 'familia_cambia_carrito', 'autorizacion_retirada', 'persona_borrada')"
)
MOTIVOS_0024 = (
    "('total_vencio', 'familia_cancela', 'familia_cambia_carrito', 'autorizacion_retirada', 'persona_borrada',"
    " 'pago_aprobado')"
)

# Las filas de cada tabla del pago que son del grupo del contexto
CARGO_DEL_GRUPO = "EXISTS (SELECT 1 FROM pedido p WHERE p.id = cargo.pedido_id AND p.grupo_id = app_grupo())"
PARTICIPACION_DEL_GRUPO = (
    "EXISTS (SELECT 1 FROM cargo c JOIN pedido p ON p.id = c.pedido_id"
    " WHERE c.id = participacion.cargo_id AND p.grupo_id = app_grupo())"
)
TRANSACCION_DEL_GRUPO = (
    "EXISTS (SELECT 1 FROM cargo c JOIN pedido p ON p.id = c.pedido_id"
    " WHERE c.id = transaccion_pasarela.cargo_id AND p.grupo_id = app_grupo())"
)
SISTEMA = "app_rol() = 'sistema' AND app_usuario() IS NULL"
LEE = "(SELECT app_ve_entrega())"
PAGA = "(SELECT app_paga_pedido())"

# Las transiciones del cargo (decisión 243). La participación sigue los mismos estados en femenino
TRANSICIONES_CARGO = (
    "('pendiente', 'pagado'), ('pendiente', 'rechazado'), ('rechazado', 'pendiente'), ('pagado', 'devuelto_parcial'),"
    " ('pagado', 'anulado'), ('devuelto_parcial', 'devuelto_parcial'), ('devuelto_parcial', 'anulado')"
)
TRANSICIONES_PARTICIPACION = (
    "('pendiente', 'pagada'), ('pendiente', 'rechazada'), ('rechazada', 'pendiente'), ('pagada', 'devuelta_parcial'),"
    " ('pagada', 'anulada'), ('devuelta_parcial', 'devuelta_parcial'), ('devuelta_parcial', 'anulada')"
)

PEDIDO_CONSERVAR_0023 = """
CREATE OR REPLACE FUNCTION pedido_conservar(limite timestamptz, ahora timestamptz)
    RETURNS TABLE (pedidos integer, idempotencias integer)
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'pedido_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '30 days' THEN
        RAISE EXCEPTION 'lo no pagado se conserva 30 días' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    DELETE FROM public.pedido
     WHERE pagado_en IS NULL AND estado IN ('borrador', 'total_confirmado', 'vencido', 'cancelado')
       -- C10: desde el último cambio (actualizado_en, que fija el trigger en cada escritura del pedido, sus líneas
       -- y sus reglas suben la versión) y, con un total confirmado, desde que venció
       AND GREATEST(actualizado_en, COALESCE(total_vence_en, actualizado_en)) <= limite;
    GET DIAGNOSTICS pedidos = ROW_COUNT;
    DELETE FROM public.idempotencia WHERE expira_en <= ahora;
    GET DIAGNOSTICS idempotencias = ROW_COUNT;
    RETURN NEXT;
END $$;
"""

TRANSICION_SOLO_INSERCION_0023 = """
CREATE OR REPLACE FUNCTION transicion_solo_insercion() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    -- Solo en la cascada del borrado de su pedido (pedido_conservar): el pedido ya no está
    IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1
       AND NOT EXISTS (SELECT 1 FROM pedido p WHERE p.id = OLD.pedido_id) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'tabla de solo inserción' USING ERRCODE = 'insufficient_privilege';
END $$;
"""

# Lo no pagado vencido del plazo (C10), como en la 0023
VIEJO = (
    "p.pagado_en IS NULL AND p.estado IN ('borrador', 'total_confirmado', 'vencido', 'cancelado')"
    " AND GREATEST(p.actualizado_en, COALESCE(p.total_vence_en, p.actualizado_en)) <= limite"
)
CON_DINERO = (
    "EXISTS (SELECT 1 FROM public.cargo c JOIN public.transaccion_pasarela t ON t.cargo_id = c.id"
    " WHERE c.pedido_id = p.id AND t.tipo = 'venta' AND t.estado IN ('aprobada', 'autorizando'))"
)

UPGRADE = f"""
SELECT set_config('app.rol', 'operacion', true);

-- (a) Pagan admin y pagador (D-62-8)
CREATE FUNCTION app_paga_pedido() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT EXISTS (SELECT 1 FROM membresia m
                  WHERE m.grupo_id = app_grupo() AND m.usuario_id = app_usuario()
                    AND m.estado = 'activa' AND m.rol IN ('admin', 'pagador')) $$;

-- (b) pedido: quién aceptó (D-62-16) y la referencia corta (decisión 238)
ALTER TABLE pedido ADD COLUMN condiciones_aceptadas_por uuid;
ALTER TABLE pedido DROP CONSTRAINT pedido_condiciones_completas;
ALTER TABLE pedido ADD CONSTRAINT pedido_condiciones_completas CHECK (
    (condiciones_version IS NULL) = (condiciones_aceptadas_en IS NULL)
    AND (condiciones_version IS NULL) = (condiciones_huella IS NULL)
    AND (condiciones_version IS NULL) = (condiciones_aceptadas_por IS NULL)) NOT VALID;
ALTER TABLE pedido ADD COLUMN referencia text;
ALTER TABLE pedido ADD CONSTRAINT pedido_referencia_forma CHECK (referencia ~ '^[0-9]{{4,6}}$');
ALTER TABLE pedido ADD CONSTRAINT pedido_referencia_al_pagar CHECK (referencia IS NULL OR pagado_en IS NOT NULL);
ALTER TABLE pedido ADD CONSTRAINT pedido_referencia_uq UNIQUE (grupo_id, referencia);
-- Se validan si ninguna fila las viola (las de antes de MATU-62 en una base de pruebas pueden hacerlo)
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pedido WHERE NOT (
        (condiciones_version IS NULL) = (condiciones_aceptadas_en IS NULL)
        AND (condiciones_version IS NULL) = (condiciones_huella IS NULL)
        AND (condiciones_version IS NULL) = (condiciones_aceptadas_por IS NULL))) THEN
        ALTER TABLE pedido VALIDATE CONSTRAINT pedido_condiciones_completas;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pedido WHERE pagado_en IS NOT NULL AND condiciones_aceptadas_en IS NULL) THEN
        ALTER TABLE pedido VALIDATE CONSTRAINT pedido_pago_con_condiciones;
    END IF;
END $$;

-- (e) transaccion_pasarela: la venta atada al total, sus datos y la anulación
ALTER TABLE transaccion_pasarela
    ADD COLUMN cargo_id            uuid REFERENCES cargo(id),
    ADD COLUMN total_confirmado_en timestamptz,
    ADD COLUMN session_id          text CHECK (length(session_id) BETWEEN 1 AND 61),
    ADD COLUMN cuotas              smallint CHECK (cuotas BETWEEN 0 AND 48),
    ADD COLUMN motivo_cierre       text CHECK (motivo_cierre IN ('no_aprobada', 'usuario_salio', 'formulario_vencido')),
    ADD COLUMN retorno_recibido_en timestamptz,
    ADD COLUMN commit_intentado_en timestamptz,
    ADD COLUMN cerrada_en          timestamptz,
    ADD COLUMN anulacion_total     boolean NOT NULL DEFAULT false,
    ADD COLUMN venta_id            uuid REFERENCES transaccion_pasarela(id),
    ADD COLUMN motivo_anulacion    text
        CHECK (motivo_anulacion IN ('pago_tardio', 'producto_no_entregado', 'cancelacion')),
    ADD COLUMN pedido_linea_id     uuid REFERENCES pedido_linea(id),
    ADD COLUMN intentos            smallint NOT NULL DEFAULT 0 CHECK (intentos >= 0);
UPDATE transaccion_pasarela t SET cargo_id = pa.cargo_id FROM participacion pa WHERE pa.id = t.participacion_id;
UPDATE transaccion_pasarela t SET total_confirmado_en = COALESCE(
    (SELECT p.total_confirmado_en FROM cargo c JOIN pedido p ON p.id = c.pedido_id WHERE c.id = t.cargo_id),
    t.creado_en) WHERE t.tipo = 'venta';
-- (f) R14 (D-62-9): MATU nunca guarda la respuesta de Transbank
UPDATE transaccion_pasarela SET payload_respuesta = NULL WHERE payload_respuesta IS NOT NULL;
UPDATE transaccion_pasarela SET ultimos4 = NULL WHERE ultimos4 !~ '^[0-9]{{4}}$';
ALTER TABLE transaccion_pasarela ALTER COLUMN cargo_id SET NOT NULL;
ALTER TABLE transaccion_pasarela
    ADD CONSTRAINT transaccion_sin_payload CHECK (payload_respuesta IS NULL),
    ADD CONSTRAINT transaccion_ultimos4 CHECK (ultimos4 ~ '^[0-9]{{4}}$'),
    ADD CONSTRAINT transaccion_venta_con_total CHECK (tipo <> 'venta' OR total_confirmado_en IS NOT NULL),
    ADD CONSTRAINT transaccion_motivo_cierre CHECK (motivo_cierre IS NULL OR estado = 'rechazada'),
    ADD CONSTRAINT transaccion_linea_de_anulacion CHECK (pedido_linea_id IS NULL OR tipo = 'anulacion'),
    ADD CONSTRAINT transaccion_venta_de_anulacion CHECK (venta_id IS NULL OR tipo = 'anulacion');
-- Las anulaciones de antes de MATU-62 (las reversas de la 0002) no tienen venta ni motivo: NOT VALID
ALTER TABLE transaccion_pasarela ADD CONSTRAINT transaccion_anulacion_completa CHECK (
    tipo <> 'anulacion' OR (venta_id IS NOT NULL AND motivo_anulacion IS NOT NULL)) NOT VALID;
CREATE UNIQUE INDEX transaccion_token_uq ON transaccion_pasarela (token) WHERE tipo = 'venta' AND token IS NOT NULL;
CREATE UNIQUE INDEX transaccion_una_aprobada_uq ON transaccion_pasarela (cargo_id)
    WHERE tipo = 'venta' AND estado = 'aprobada' AND NOT anulacion_total;
CREATE UNIQUE INDEX transaccion_linea_devuelta_uq ON transaccion_pasarela (pedido_linea_id)
    WHERE pedido_linea_id IS NOT NULL;
CREATE INDEX transaccion_cargo_ix ON transaccion_pasarela (cargo_id, creado_en);
CREATE INDEX transaccion_orden_sesion_ix ON transaccion_pasarela (buy_order, session_id) WHERE tipo = 'venta';

CREATE FUNCTION transaccion_pago_atado() RETURNS trigger LANGUAGE plpgsql AS
$$
DECLARE
    venta public.transaccion_pasarela%ROWTYPE;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM participacion pa
                    WHERE pa.id = NEW.participacion_id AND pa.cargo_id = NEW.cargo_id) THEN
        RAISE EXCEPTION 'la transacción es del cargo de su participación' USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'INSERT' AND NEW.tipo = 'venta' AND NOT EXISTS (
        SELECT 1 FROM cargo c JOIN pedido p ON p.id = c.pedido_id
         WHERE c.id = NEW.cargo_id AND p.pagado_en IS NULL AND p.total = NEW.monto
           AND p.total_confirmado_en = NEW.total_confirmado_en) THEN
        RAISE EXCEPTION 'la venta va atada al total confirmado del pedido sin pagar' USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'INSERT' AND NEW.tipo = 'anulacion' AND NEW.venta_id IS NOT NULL THEN
        SELECT * INTO venta FROM transaccion_pasarela v WHERE v.id = NEW.venta_id;
        IF NOT FOUND OR venta.tipo <> 'venta' OR venta.estado <> 'aprobada' OR venta.cargo_id <> NEW.cargo_id THEN
            RAISE EXCEPTION 'se anula una venta aprobada del mismo cargo' USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.monto + COALESCE((SELECT sum(a.monto) FROM transaccion_pasarela a
                                  WHERE a.venta_id = NEW.venta_id AND a.tipo = 'anulacion'), 0) > venta.monto THEN
            RAISE EXCEPTION 'lo anulado no supera lo cobrado' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.cargo_id, NEW.participacion_id, NEW.tipo, NEW.monto, NEW.total_confirmado_en, NEW.buy_order,
            NEW.session_id, NEW.venta_id, NEW.pedido_linea_id, NEW.motivo_anulacion, NEW.idempotency_key)
           IS DISTINCT FROM
           (OLD.cargo_id, OLD.participacion_id, OLD.tipo, OLD.monto, OLD.total_confirmado_en, OLD.buy_order,
            OLD.session_id, OLD.venta_id, OLD.pedido_linea_id, OLD.motivo_anulacion, OLD.idempotency_key) THEN
            RAISE EXCEPTION 'lo que identifica la transacción no cambia' USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.token IS NOT NULL AND NEW.token IS DISTINCT FROM OLD.token THEN
            RAISE EXCEPTION 'el token de la venta no cambia' USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.estado IN ('aprobada', 'rechazada') AND NEW.estado IS DISTINCT FROM OLD.estado THEN
            RAISE EXCEPTION 'una transacción cerrada no cambia de estado' USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.anulacion_total AND NOT NEW.anulacion_total THEN
            RAISE EXCEPTION 'una venta anulada no deja de estarlo' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER transaccion_pago_atado BEFORE INSERT OR UPDATE ON transaccion_pasarela
    FOR EACH ROW EXECUTE FUNCTION transaccion_pago_atado();

-- Las transiciones del cargo y de la participación (decisión 243); el cargo pagado, con su venta aprobada
CREATE FUNCTION cargo_pago_atado() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF TG_TABLE_NAME = 'cargo' THEN
        IF NEW.pedido_id IS DISTINCT FROM OLD.pedido_id THEN
            RAISE EXCEPTION 'el cargo es de su pedido' USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.estado IS DISTINCT FROM OLD.estado AND (OLD.estado, NEW.estado) NOT IN ({TRANSICIONES_CARGO}) THEN
            RAISE EXCEPTION 'el cargo no pasa de ese estado a ese otro' USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.estado = 'pagado' AND OLD.estado <> 'pagado' AND NOT EXISTS (
            SELECT 1 FROM transaccion_pasarela t WHERE t.cargo_id = NEW.id AND t.tipo = 'venta'
               AND t.estado = 'aprobada' AND NOT t.anulacion_total AND t.monto = NEW.monto_cobrado) THEN
            RAISE EXCEPTION 'el cargo se paga con una venta aprobada por lo cobrado' USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        IF NEW.cargo_id IS DISTINCT FROM OLD.cargo_id OR NEW.usuario_id IS DISTINCT FROM OLD.usuario_id THEN
            RAISE EXCEPTION 'la participación es de su cargo y de su cuenta' USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.estado IS DISTINCT FROM OLD.estado
           AND (OLD.estado, NEW.estado) NOT IN ({TRANSICIONES_PARTICIPACION}) THEN
            RAISE EXCEPTION 'la participación no pasa de ese estado a ese otro' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER cargo_pago_atado BEFORE UPDATE ON cargo FOR EACH ROW EXECUTE FUNCTION cargo_pago_atado();
CREATE TRIGGER participacion_pago_atado BEFORE UPDATE ON participacion
    FOR EACH ROW EXECUTE FUNCTION cargo_pago_atado();

-- (b) Quién escribe qué del pedido
CREATE FUNCTION pedido_escritura_del_pago() RETURNS trigger LANGUAGE plpgsql AS
$$
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
END $$;
CREATE TRIGGER pedido_escritura_del_pago BEFORE UPDATE ON pedido
    FOR EACH ROW EXECUTE FUNCTION pedido_escritura_del_pago();

CREATE POLICY pedido_pagador_condiciones ON pedido FOR UPDATE
    USING (grupo_id = app_grupo() AND pagado_en IS NULL AND {PAGA})
    WITH CHECK (grupo_id = app_grupo() AND {PAGA});
CREATE POLICY pedido_sistema_pago ON pedido FOR UPDATE
    USING (grupo_id = app_grupo() AND {SISTEMA}) WITH CHECK (grupo_id = app_grupo() AND {SISTEMA});
CREATE POLICY pedido_operacion_pago ON pedido FOR UPDATE
    USING (app_rol() = 'operacion') WITH CHECK (app_rol() = 'operacion');
-- (k) La vuelta sin sesión resuelve su venta como matu_owner, dentro de pago_resolver_venta
CREATE POLICY pedido_resolver_pago ON pedido FOR SELECT TO matu_owner
    USING (app_rol() = 'sistema' AND app_grupo() IS NULL);

-- (c) La línea de tiempo del pago
ALTER TABLE pedido_transicion DROP CONSTRAINT pedido_transicion_motivo;
ALTER TABLE pedido_transicion ADD CONSTRAINT pedido_transicion_motivo
    CHECK (motivo IS NULL OR motivo IN {MOTIVOS_0024});
CREATE POLICY transicion_sistema_crear ON pedido_transicion FOR INSERT WITH CHECK (
    app_rol() IN ('sistema', 'operacion') AND app_usuario() IS NULL AND actor_tipo IN ('sistema', 'operacion')
    AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = pedido_transicion.pedido_id));

-- (d) cargo
DROP POLICY cargo_familia ON cargo;
DROP POLICY cargo_operacion ON cargo;
CREATE POLICY cargo_familia_leer ON cargo FOR SELECT USING ({CARGO_DEL_GRUPO} AND {LEE});
CREATE POLICY cargo_familia_crear ON cargo FOR INSERT WITH CHECK (
    {CARGO_DEL_GRUPO} AND {PAGA} AND estado = 'pendiente' AND monto_cobrado = 0 AND monto_devuelto = 0);
CREATE POLICY cargo_familia_reintentar ON cargo FOR UPDATE
    USING ({CARGO_DEL_GRUPO} AND {PAGA} AND estado = 'rechazado')
    WITH CHECK ({CARGO_DEL_GRUPO} AND {PAGA} AND estado = 'pendiente' AND monto_cobrado = 0 AND monto_devuelto = 0);
CREATE POLICY cargo_sistema_leer ON cargo FOR SELECT USING ({SISTEMA} AND {CARGO_DEL_GRUPO});
CREATE POLICY cargo_sistema_editar ON cargo FOR UPDATE
    USING ({SISTEMA} AND {CARGO_DEL_GRUPO}) WITH CHECK ({SISTEMA} AND {CARGO_DEL_GRUPO});
CREATE POLICY cargo_operacion_leer ON cargo FOR SELECT USING (app_rol() = 'operacion');
CREATE POLICY cargo_operacion_editar ON cargo FOR UPDATE
    USING (app_rol() = 'operacion') WITH CHECK (app_rol() = 'operacion');
CREATE POLICY cargo_resolver_pago ON cargo FOR SELECT TO matu_owner
    USING (app_rol() = 'sistema' AND app_grupo() IS NULL);
CREATE POLICY cargo_conservacion_borrar ON cargo FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion' AND estado IN ('pendiente', 'rechazado') AND monto_cobrado = 0);

-- (d) participacion
DROP POLICY participacion_hereda ON participacion;
CREATE POLICY participacion_familia_leer ON participacion FOR SELECT USING ({PARTICIPACION_DEL_GRUPO} AND {LEE});
CREATE POLICY participacion_familia_crear ON participacion FOR INSERT WITH CHECK (
    {PARTICIPACION_DEL_GRUPO} AND {PAGA} AND usuario_id = app_usuario() AND porcentaje_bp = 10000
    AND estado = 'pendiente' AND monto_cobrado = 0 AND monto_devuelto = 0 AND NOT es_respaldo);
CREATE POLICY participacion_familia_reintentar ON participacion FOR UPDATE
    USING ({PARTICIPACION_DEL_GRUPO} AND {PAGA} AND usuario_id = app_usuario() AND estado = 'rechazada')
    WITH CHECK ({PARTICIPACION_DEL_GRUPO} AND {PAGA} AND usuario_id = app_usuario() AND estado = 'pendiente'
                AND monto_cobrado = 0 AND monto_devuelto = 0);
CREATE POLICY participacion_sistema_leer ON participacion FOR SELECT USING ({SISTEMA} AND {PARTICIPACION_DEL_GRUPO});
CREATE POLICY participacion_sistema_editar ON participacion FOR UPDATE
    USING ({SISTEMA} AND {PARTICIPACION_DEL_GRUPO}) WITH CHECK ({SISTEMA} AND {PARTICIPACION_DEL_GRUPO});
CREATE POLICY participacion_operacion_leer ON participacion FOR SELECT USING (app_rol() = 'operacion');
CREATE POLICY participacion_operacion_editar ON participacion FOR UPDATE
    USING (app_rol() = 'operacion') WITH CHECK (app_rol() = 'operacion');
CREATE POLICY participacion_conservacion_borrar ON participacion FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion' AND estado IN ('pendiente', 'rechazada') AND monto_cobrado = 0);

-- (d) transaccion_pasarela
DROP POLICY transaccion_hereda ON transaccion_pasarela;
CREATE POLICY transaccion_familia_leer ON transaccion_pasarela FOR SELECT USING ({TRANSACCION_DEL_GRUPO} AND {LEE});
-- La venta la abre quien paga, a su nombre, iniciada o con error, sin datos de la respuesta
CREATE POLICY transaccion_familia_crear ON transaccion_pasarela FOR INSERT WITH CHECK (
    {TRANSACCION_DEL_GRUPO} AND {PAGA} AND tipo = 'venta' AND estado IN ('iniciada', 'error')
    AND EXISTS (SELECT 1 FROM participacion pa WHERE pa.id = transaccion_pasarela.participacion_id
                AND pa.usuario_id = app_usuario())
    AND codigo_autorizacion IS NULL AND tipo_tarjeta IS NULL AND ultimos4 IS NULL AND cuotas IS NULL
    AND NOT anulacion_total AND cerrada_en IS NULL);
CREATE POLICY transaccion_sistema_leer ON transaccion_pasarela FOR SELECT USING ({SISTEMA} AND {TRANSACCION_DEL_GRUPO});
CREATE POLICY transaccion_sistema_crear ON transaccion_pasarela FOR INSERT
    WITH CHECK ({SISTEMA} AND {TRANSACCION_DEL_GRUPO} AND tipo = 'anulacion');
CREATE POLICY transaccion_sistema_editar ON transaccion_pasarela FOR UPDATE
    USING ({SISTEMA} AND {TRANSACCION_DEL_GRUPO}) WITH CHECK ({SISTEMA} AND {TRANSACCION_DEL_GRUPO});
CREATE POLICY transaccion_operacion_leer ON transaccion_pasarela FOR SELECT USING (app_rol() = 'operacion');
CREATE POLICY transaccion_operacion_crear ON transaccion_pasarela FOR INSERT
    WITH CHECK (app_rol() = 'operacion' AND tipo = 'anulacion');
CREATE POLICY transaccion_operacion_editar ON transaccion_pasarela FOR UPDATE
    USING (app_rol() = 'operacion') WITH CHECK (app_rol() = 'operacion');
CREATE POLICY transaccion_resolver_pago ON transaccion_pasarela FOR SELECT TO matu_owner
    USING (app_rol() = 'sistema' AND app_grupo() IS NULL);
CREATE POLICY transaccion_conservacion_borrar ON transaccion_pasarela FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion' AND estado NOT IN ('aprobada', 'autorizando'));

REVOKE DELETE ON cargo, participacion FROM matu_app;

-- (i) El registro contable se borra solo dentro de pedido_conservar, y nunca una venta aprobada
CREATE FUNCTION transaccion_borrado_acotado() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF current_user = 'matu_owner' AND current_setting('app.conservacion', true) = 'pedidos'
       AND OLD.estado NOT IN ('aprobada', 'autorizando') THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'el registro contable de la pasarela no se borra' USING ERRCODE = 'insufficient_privilege';
END $$;
DROP TRIGGER transaccion_sin_borrado ON transaccion_pasarela;
CREATE TRIGGER transaccion_sin_borrado BEFORE DELETE ON transaccion_pasarela
    FOR EACH ROW EXECUTE FUNCTION transaccion_borrado_acotado();

CREATE OR REPLACE FUNCTION transicion_solo_insercion() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    -- En la cascada del borrado de su pedido (pedido_conservar): el pedido ya no está
    IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1
       AND NOT EXISTS (SELECT 1 FROM pedido p WHERE p.id = OLD.pedido_id) THEN
        RETURN OLD;
    END IF;
    -- D-62-13: la de un pedido con dinero que nunca quedó pagado, dentro de pedido_conservar
    IF TG_OP = 'DELETE' AND current_user = 'matu_owner' AND current_setting('app.conservacion', true) = 'pedidos'
       AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = OLD.pedido_id AND p.pagado_en IS NULL) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'tabla de solo inserción' USING ERRCODE = 'insufficient_privilege';
END $$;

CREATE POLICY linea_conservacion_borrar ON pedido_linea FOR DELETE TO matu_owner USING (app_rol() = 'operacion');
CREATE POLICY regla_conservacion_borrar ON regla_sustitucion FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion');
CREATE POLICY pedido_comercio_conservacion_borrar ON pedido_comercio FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion');
CREATE POLICY transicion_conservacion_borrar ON pedido_transicion FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion');

CREATE OR REPLACE FUNCTION pedido_conservar(limite timestamptz, ahora timestamptz)
    RETURNS TABLE (pedidos integer, idempotencias integer)
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'pedido_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '30 days' THEN
        RAISE EXCEPTION 'lo no pagado se conserva 30 días' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    PERFORM set_config('app.conservacion', 'pedidos', true);
    -- D-62-13 (c), sin dinero: el intento que no se cobró se va con su pedido
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
    PERFORM set_config('app.conservacion', '', true);
    RETURN NEXT;
END $$;

-- (g) La venta de cada clave de pagar, y un 503 que libera su clave
ALTER TABLE idempotencia ADD COLUMN transaccion_id uuid REFERENCES transaccion_pasarela(id) ON DELETE SET NULL;
CREATE POLICY idempotencia_liberar ON idempotencia FOR DELETE
    USING (grupo_id = app_grupo() AND usuario_id = app_usuario() AND estado_http IS NULL);

-- (h) La devolución de una línea pagada la marcan el sistema y operación (decisión 239)
CREATE POLICY linea_pago_devolver ON pedido_linea FOR UPDATE
    USING (app_rol() IN ('sistema', 'operacion') AND app_usuario() IS NULL
           AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = pedido_linea.pedido_id AND p.pagado_en IS NOT NULL))
    WITH CHECK (app_rol() IN ('sistema', 'operacion') AND app_usuario() IS NULL
                AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = pedido_linea.pedido_id AND p.pagado_en IS NOT NULL));

-- (j) D-62-5: lo que la conciliación revisa, solo identificadores
CREATE FUNCTION pagos_por_conciliar(limite timestamptz, cantidad integer)
    RETURNS TABLE (transaccion_id uuid, grupo_id uuid)
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'pagos_por_conciliar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF limite IS NULL OR cantidad IS NULL OR cantidad < 1 OR cantidad > 500 THEN
        RAISE EXCEPTION 'límite o cantidad fuera de rango' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    RETURN QUERY
        SELECT t.id, p.grupo_id
          FROM public.transaccion_pasarela t
          JOIN public.cargo c ON c.id = t.cargo_id
          JOIN public.pedido p ON p.id = c.pedido_id
         WHERE (t.tipo = 'venta' AND (t.estado = 'autorizando' OR (t.estado = 'iniciada' AND t.creado_en <= limite)))
            OR (t.tipo = 'anulacion' AND t.estado IN ('iniciada', 'error'))
         ORDER BY t.creado_en, t.id
         LIMIT cantidad;
END $$;
REVOKE ALL ON FUNCTION pagos_por_conciliar(timestamptz, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION pagos_por_conciliar(timestamptz, integer) TO matu_scheduler;

-- (k) La vuelta sin sesión: la venta por su token, o por buy_order y session_id juntos
CREATE FUNCTION pago_resolver_venta(p_token text, p_orden text, p_sesion text)
    RETURNS TABLE (transaccion_id uuid, grupo_id uuid)
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'sistema' OR public.app_grupo() IS NOT NULL
       OR public.app_usuario() IS NOT NULL THEN
        RAISE EXCEPTION 'pago_resolver_venta exige app.rol = sistema, sin grupo ni cuenta'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_token IS NOT NULL THEN
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
END $$;
REVOKE ALL ON FUNCTION pago_resolver_venta(text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION pago_resolver_venta(text, text, text) TO matu_app;

SELECT set_config('app.rol', '', true);
"""

DOWNGRADE = f"""
SELECT set_config('app.rol', 'operacion', true);

-- (k) y (j)
DROP FUNCTION pago_resolver_venta(text, text, text);
DROP FUNCTION pagos_por_conciliar(timestamptz, integer);

-- (h)
DROP POLICY linea_pago_devolver ON pedido_linea;

-- (g)
DROP POLICY idempotencia_liberar ON idempotencia;
ALTER TABLE idempotencia DROP COLUMN transaccion_id;

-- (i)
{PEDIDO_CONSERVAR_0023}
DROP POLICY transicion_conservacion_borrar ON pedido_transicion;
DROP POLICY pedido_comercio_conservacion_borrar ON pedido_comercio;
DROP POLICY regla_conservacion_borrar ON regla_sustitucion;
DROP POLICY linea_conservacion_borrar ON pedido_linea;
{TRANSICION_SOLO_INSERCION_0023}
DROP TRIGGER transaccion_sin_borrado ON transaccion_pasarela;
CREATE TRIGGER transaccion_sin_borrado BEFORE DELETE ON transaccion_pasarela
    FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion();
DROP FUNCTION transaccion_borrado_acotado();

-- (d)
GRANT DELETE ON cargo, participacion TO matu_app;
DROP POLICY transaccion_conservacion_borrar ON transaccion_pasarela;
DROP POLICY transaccion_resolver_pago ON transaccion_pasarela;
DROP POLICY transaccion_operacion_editar ON transaccion_pasarela;
DROP POLICY transaccion_operacion_crear ON transaccion_pasarela;
DROP POLICY transaccion_operacion_leer ON transaccion_pasarela;
DROP POLICY transaccion_sistema_editar ON transaccion_pasarela;
DROP POLICY transaccion_sistema_crear ON transaccion_pasarela;
DROP POLICY transaccion_sistema_leer ON transaccion_pasarela;
DROP POLICY transaccion_familia_crear ON transaccion_pasarela;
DROP POLICY transaccion_familia_leer ON transaccion_pasarela;
CREATE POLICY transaccion_hereda ON transaccion_pasarela FOR ALL USING (EXISTS (
    SELECT 1 FROM participacion p WHERE p.id = transaccion_pasarela.participacion_id));

DROP POLICY participacion_conservacion_borrar ON participacion;
DROP POLICY participacion_operacion_editar ON participacion;
DROP POLICY participacion_operacion_leer ON participacion;
DROP POLICY participacion_sistema_editar ON participacion;
DROP POLICY participacion_sistema_leer ON participacion;
DROP POLICY participacion_familia_reintentar ON participacion;
DROP POLICY participacion_familia_crear ON participacion;
DROP POLICY participacion_familia_leer ON participacion;
CREATE POLICY participacion_hereda ON participacion FOR ALL USING (EXISTS (
    SELECT 1 FROM cargo c WHERE c.id = participacion.cargo_id));

DROP POLICY cargo_conservacion_borrar ON cargo;
DROP POLICY cargo_resolver_pago ON cargo;
DROP POLICY cargo_operacion_editar ON cargo;
DROP POLICY cargo_operacion_leer ON cargo;
DROP POLICY cargo_sistema_editar ON cargo;
DROP POLICY cargo_sistema_leer ON cargo;
DROP POLICY cargo_familia_reintentar ON cargo;
DROP POLICY cargo_familia_crear ON cargo;
DROP POLICY cargo_familia_leer ON cargo;
CREATE POLICY cargo_familia ON cargo FOR ALL USING (EXISTS (
    SELECT 1 FROM pedido p WHERE p.id = cargo.pedido_id AND p.grupo_id = app_grupo()));
CREATE POLICY cargo_operacion ON cargo FOR ALL USING (app_rol() = 'operacion');

-- (c)
DROP POLICY transicion_sistema_crear ON pedido_transicion;
ALTER TABLE pedido_transicion DROP CONSTRAINT pedido_transicion_motivo;
ALTER TABLE pedido_transicion ADD CONSTRAINT pedido_transicion_motivo
    CHECK (motivo IS NULL OR motivo IN {MOTIVOS_0023});

-- (b)
DROP POLICY pedido_resolver_pago ON pedido;
DROP POLICY pedido_operacion_pago ON pedido;
DROP POLICY pedido_sistema_pago ON pedido;
DROP POLICY pedido_pagador_condiciones ON pedido;
DROP TRIGGER pedido_escritura_del_pago ON pedido;
DROP FUNCTION pedido_escritura_del_pago();

-- (e)
DROP TRIGGER participacion_pago_atado ON participacion;
DROP TRIGGER cargo_pago_atado ON cargo;
DROP FUNCTION cargo_pago_atado();
DROP TRIGGER transaccion_pago_atado ON transaccion_pasarela;
DROP FUNCTION transaccion_pago_atado();
DROP INDEX transaccion_orden_sesion_ix;
DROP INDEX transaccion_cargo_ix;
DROP INDEX transaccion_linea_devuelta_uq;
DROP INDEX transaccion_una_aprobada_uq;
DROP INDEX transaccion_token_uq;
ALTER TABLE transaccion_pasarela DROP CONSTRAINT transaccion_anulacion_completa,
    DROP CONSTRAINT transaccion_venta_de_anulacion, DROP CONSTRAINT transaccion_linea_de_anulacion,
    DROP CONSTRAINT transaccion_motivo_cierre, DROP CONSTRAINT transaccion_venta_con_total,
    DROP CONSTRAINT transaccion_ultimos4, DROP CONSTRAINT transaccion_sin_payload;
ALTER TABLE transaccion_pasarela DROP COLUMN intentos, DROP COLUMN pedido_linea_id, DROP COLUMN motivo_anulacion,
    DROP COLUMN venta_id, DROP COLUMN anulacion_total, DROP COLUMN cerrada_en, DROP COLUMN commit_intentado_en,
    DROP COLUMN retorno_recibido_en, DROP COLUMN motivo_cierre, DROP COLUMN cuotas, DROP COLUMN session_id,
    DROP COLUMN total_confirmado_en, DROP COLUMN cargo_id;

-- (b)
ALTER TABLE pedido DROP CONSTRAINT pedido_referencia_uq, DROP CONSTRAINT pedido_referencia_al_pagar,
    DROP CONSTRAINT pedido_referencia_forma;
ALTER TABLE pedido DROP COLUMN referencia;
ALTER TABLE pedido DROP CONSTRAINT pedido_condiciones_completas;
ALTER TABLE pedido ADD CONSTRAINT pedido_condiciones_completas CHECK (
    (condiciones_version IS NULL) = (condiciones_aceptadas_en IS NULL)
    AND (condiciones_version IS NULL) = (condiciones_huella IS NULL));
ALTER TABLE pedido DROP COLUMN condiciones_aceptadas_por;
-- Como la dejó la 0023: NOT VALID
ALTER TABLE pedido DROP CONSTRAINT pedido_pago_con_condiciones;
ALTER TABLE pedido ADD CONSTRAINT pedido_pago_con_condiciones
    CHECK (pagado_en IS NULL OR condiciones_aceptadas_en IS NOT NULL) NOT VALID;

-- (a)
DROP FUNCTION app_paga_pedido();

SELECT set_config('app.rol', '', true);
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

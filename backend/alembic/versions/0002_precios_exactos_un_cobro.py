"""ADR-027: precios exactos y un solo cobro del total confirmado.

Reemplaza en el esquema la autorización con margen y la captura diferida del ADR-006:

- pedido: montos exactos (productos + un envío único = total), la confirmación del total
  y su vencimiento, y la marca del pago. Ciclo de estados sin recaudación, autorización
  ni captura pendiente.
- pedido_linea: el precio pagado queda fijo (trigger), sin precio real ni sustitución por
  otra marca. Registra la reasignación al mismo producto en otro comercio y la devolución.
- cargo y participacion: monto cobrado y monto devuelto (devuelto <= cobrado), sin margen,
  autorizado ni capturado.
- transaccion_pasarela.tipo: venta y anulación.
- RLS: el comercio ve el pedido solo cuando está pagado y enviado.

Los scripts de backend/db no se tocan: son la migración 0001. Todo va aquí con SQL.

Las tablas tienen RLS forzado y el dueño también queda sujeto a él. Para convertir filas
existentes la migración fija app.rol = 'operacion' solo dentro de su transacción.

downgrade() deja el esquema como en 0001 (mismos nombres, tipos, nulos, valores por omisión,
CHECK, índices, políticas y triggers). PostgreSQL no reordena columnas: las columnas
restauradas quedan al final de la tabla. Lo verifica tests/test_migraciones.py.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    # Igual que en 0001: el SQL llega tal cual al driver, sin interpretar ':' ni '%'.
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


# Estados del pedido antes del pago, después del pago, y 'cancelado', que puede ser de los dos
_PEDIDO_ANTES_DEL_PAGO = "'borrador', 'total_confirmado', 'vencido'"
_PEDIDO_PAGADO = (
    "'pagado', 'enviado_a_comercio', 'preparando', 'listo_retiro', 'asignado', 'sin_repartidor', "
    "'retirado', 'en_ruta', 'entregado', 'no_entregado', 'reprogramado', 'cerrado', 'cancelado_con_devolucion'"
)

UPGRADE = f"""
SELECT set_config('app.rol', 'operacion', true);

-- =============================================================================
-- pedido · montos exactos, total confirmado con vencimiento y marca de pago
-- =============================================================================
ALTER TABLE pedido DROP CONSTRAINT pedido_estado_check;
ALTER TABLE pedido
    ADD COLUMN subtotal_productos  bigint NOT NULL DEFAULT 0 CHECK (subtotal_productos >= 0),
    ADD COLUMN costo_envio         bigint NOT NULL DEFAULT 0 CHECK (costo_envio >= 0),   -- uno por pedido
    ADD COLUMN total               bigint NOT NULL DEFAULT 0 CHECK (total >= 0),         -- con IVA
    ADD COLUMN total_confirmado_en timestamptz,   -- stock y precios confirmados
    ADD COLUMN total_vence_en      timestamptz,   -- 15 minutos después (ADR-027); lo fija el dominio
    ADD COLUMN pagado_en           timestamptz;   -- desde aquí el precio queda fijo

UPDATE pedido SET
    subtotal_productos = coalesce(total_real, total_autorizado, total_estimado),
    total              = coalesce(total_real, total_autorizado, total_estimado),
    estado = CASE estado
        WHEN 'pendiente_recaudacion' THEN 'total_confirmado'
        WHEN 'autorizado'            THEN 'pagado'
        WHEN 'expirado'              THEN 'vencido'
        WHEN 'requiere_decision'     THEN 'preparando'
        WHEN 'captura_pendiente'     THEN 'entregado'
        WHEN 'incobrable'            THEN 'cerrado'
        ELSE estado END;
UPDATE pedido SET total_confirmado_en = creado_en, total_vence_en = creado_en + interval '15 minutes'
 WHERE estado NOT IN ('borrador', 'cancelado');
UPDATE pedido SET pagado_en = creado_en WHERE estado IN ({_PEDIDO_PAGADO});

ALTER TABLE pedido DROP COLUMN total_estimado, DROP COLUMN total_autorizado, DROP COLUMN total_real;

ALTER TABLE pedido
    ADD CONSTRAINT pedido_estado_check CHECK (estado IN (
        'borrador', 'total_confirmado', 'vencido', 'pagado', 'enviado_a_comercio',
        'preparando', 'listo_retiro', 'asignado', 'sin_repartidor',
        'retirado', 'en_ruta', 'entregado', 'no_entregado', 'reprogramado',
        'cerrado', 'cancelado', 'cancelado_con_devolucion')),
    -- Un solo cobro del total exacto: productos más un envío único
    ADD CONSTRAINT pedido_total_exacto CHECK (total = subtotal_productos + costo_envio),
    ADD CONSTRAINT pedido_total_vigencia CHECK (
        (total_confirmado_en IS NULL) = (total_vence_en IS NULL)
        AND (total_vence_en IS NULL OR total_vence_en > total_confirmado_en)),
    ADD CONSTRAINT pedido_total_confirmado_positivo CHECK (total_confirmado_en IS NULL OR total > 0),
    ADD CONSTRAINT pedido_pago_confirmado CHECK (pagado_en IS NULL OR total_confirmado_en IS NOT NULL),
    -- Antes del pago no hay marca de pago; después, siempre. 'cancelado' puede ser de los dos
    ADD CONSTRAINT pedido_estado_pago CHECK (CASE
        WHEN estado IN ({_PEDIDO_ANTES_DEL_PAGO}) THEN pagado_en IS NULL
        WHEN estado IN ({_PEDIDO_PAGADO}) THEN pagado_en IS NOT NULL
        ELSE true END),
    ADD CONSTRAINT pedido_estado_confirmado CHECK (
        estado NOT IN ('total_confirmado', 'vencido') OR total_confirmado_en IS NOT NULL);

DROP INDEX pedido_comercio_dia_ix;
CREATE INDEX pedido_comercio_dia_ix ON pedido (comercio_id, estado, creado_en)
    WHERE estado NOT IN ('borrador', 'total_confirmado', 'vencido', 'pagado', 'cerrado', 'cancelado');

-- El comercio ve sus pedidos recién cuando están pagados y enviados
ALTER POLICY pedido_comercio_ver ON pedido USING (
    comercio_id = app_comercio() AND pagado_en IS NOT NULL
    AND estado NOT IN ('borrador', 'total_confirmado', 'vencido', 'pagado'));
ALTER POLICY pedido_comercio_actualizar ON pedido USING (
    comercio_id = app_comercio() AND pagado_en IS NOT NULL
    AND estado NOT IN ('borrador', 'total_confirmado', 'vencido', 'pagado'));

-- =============================================================================
-- pedido_linea · precio pagado fijo, reasignación al mismo producto y devolución
-- =============================================================================
ALTER TABLE pedido_linea DROP CONSTRAINT pedido_linea_estado_linea_check;
ALTER TABLE pedido_linea DROP CONSTRAINT pedido_linea_no_autosustituye;
UPDATE pedido_linea SET estado_linea = CASE estado_linea
    WHEN 'requiere_decision' THEN 'faltante'
    WHEN 'sustituida'        THEN 'eliminada'
    ELSE estado_linea END;
ALTER TABLE pedido_linea DROP COLUMN precio_real, DROP COLUMN sustituto_de_linea_id;
ALTER TABLE pedido_linea RENAME COLUMN precio_snapshot TO precio_unitario;
ALTER TABLE pedido_linea RENAME CONSTRAINT pedido_linea_precio_snapshot_check TO pedido_linea_precio_unitario_check;

ALTER TABLE pedido_linea
    ADD COLUMN monto_devuelto       bigint NOT NULL DEFAULT 0 CHECK (monto_devuelto >= 0),
    ADD COLUMN devuelta_en          timestamptz,
    ADD COLUMN oferta_reasignada_id uuid REFERENCES oferta(id),       -- el mismo producto en otro comercio
    ADD COLUMN precio_reasignado    bigint CHECK (precio_reasignado > 0),   -- la diferencia la asume MATU
    ADD COLUMN reasignada_en        timestamptz;
ALTER TABLE pedido_linea
    ADD CONSTRAINT pedido_linea_estado_linea_check CHECK (estado_linea IN
        ('pendiente', 'sin_stock', 'preparada', 'faltante', 'devuelta', 'eliminada')),
    ADD CONSTRAINT pedido_linea_devolucion_tope CHECK (monto_devuelto <= cantidad * precio_unitario),
    ADD CONSTRAINT pedido_linea_devuelta CHECK (
        (estado_linea = 'devuelta') = (devuelta_en IS NOT NULL)
        AND (estado_linea = 'devuelta') = (monto_devuelto > 0)),
    ADD CONSTRAINT pedido_linea_reasignacion CHECK (
        (oferta_reasignada_id IS NULL) = (precio_reasignado IS NULL)
        AND (oferta_reasignada_id IS NULL) = (reasignada_en IS NULL)),
    ADD CONSTRAINT pedido_linea_reasigna_otra_oferta CHECK (oferta_reasignada_id IS DISTINCT FROM oferta_id);

-- Nunca otra marca: la oferta original y la reasignada son del producto de la línea
CREATE FUNCTION pedido_linea_mismo_producto() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM oferta o WHERE o.id = NEW.oferta_id AND o.producto_id = NEW.producto_id) THEN
        RAISE EXCEPTION 'la oferta de la línea es de otro producto' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.oferta_reasignada_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM oferta o WHERE o.id = NEW.oferta_reasignada_id AND o.producto_id = NEW.producto_id) THEN
        RAISE EXCEPTION 'la reasignación es del mismo producto, nunca de otra marca' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- Con el pedido pagado, sus líneas no cambian de producto, cantidad ni precio, y no se
-- agregan ni se quitan. Lo que no se entrega se devuelve (monto_devuelto), no se edita.
CREATE FUNCTION pedido_linea_pagada_fija() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF TG_OP = 'INSERT' THEN
        IF EXISTS (SELECT 1 FROM pedido p WHERE p.id = NEW.pedido_id AND p.pagado_en IS NOT NULL) THEN
            RAISE EXCEPTION 'el pedido ya está pagado: no se agregan líneas' USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF EXISTS (SELECT 1 FROM pedido p WHERE p.id = OLD.pedido_id AND p.pagado_en IS NOT NULL) THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'el pedido ya está pagado: la línea se devuelve, no se borra'
                USING ERRCODE = 'check_violation';
        END IF;
        IF (NEW.pedido_id, NEW.oferta_id, NEW.producto_id, NEW.cantidad, NEW.precio_unitario)
           IS DISTINCT FROM (OLD.pedido_id, OLD.oferta_id, OLD.producto_id, OLD.cantidad, OLD.precio_unitario) THEN
            RAISE EXCEPTION 'el precio pagado queda fijo' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;

CREATE TRIGGER pedido_linea_mismo_producto BEFORE INSERT OR UPDATE ON pedido_linea
    FOR EACH ROW EXECUTE FUNCTION pedido_linea_mismo_producto();
CREATE TRIGGER pedido_linea_pagada_fija BEFORE INSERT OR UPDATE OR DELETE ON pedido_linea
    FOR EACH ROW EXECUTE FUNCTION pedido_linea_pagada_fija();

-- =============================================================================
-- cargo · un cobro del total exacto y lo devuelto
-- =============================================================================
ALTER TABLE cargo DROP CONSTRAINT cargo_estado_check, DROP CONSTRAINT cargo_captura_tope;
ALTER TABLE cargo
    ADD COLUMN monto_cobrado  bigint NOT NULL DEFAULT 0 CHECK (monto_cobrado >= 0),
    ADD COLUMN monto_devuelto bigint NOT NULL DEFAULT 0 CHECK (monto_devuelto >= 0);
UPDATE cargo SET monto_cobrado = CASE
    WHEN estado IN ('capturado', 'reembolsado_parcial') THEN monto_capturado
    WHEN estado IN ('completo', 'revertido') THEN monto_autorizado
    ELSE 0 END;
UPDATE cargo SET
    monto_devuelto = CASE WHEN estado = 'revertido' THEN monto_cobrado ELSE 0 END,
    estado = CASE
        WHEN estado IN ('creado', 'recaudando', 'redistribuyendo') THEN 'pendiente'
        WHEN monto_cobrado = 0 THEN 'rechazado'
        WHEN estado = 'revertido' THEN 'anulado'
        ELSE 'pagado' END;
ALTER TABLE cargo ALTER COLUMN estado SET DEFAULT 'pendiente';
ALTER TABLE cargo DROP COLUMN monto_objetivo, DROP COLUMN margen_bp, DROP COLUMN monto_autorizado,
                  DROP COLUMN monto_capturado, DROP COLUMN recaudacion_expira_en;
ALTER TABLE cargo
    ADD CONSTRAINT cargo_estado_check CHECK (estado IN
        ('pendiente', 'pagado', 'rechazado', 'devuelto_parcial', 'anulado')),
    ADD CONSTRAINT cargo_devolucion_tope CHECK (monto_devuelto <= monto_cobrado),
    ADD CONSTRAINT cargo_estado_montos CHECK (CASE estado
        WHEN 'pendiente'        THEN monto_cobrado = 0 AND monto_devuelto = 0
        WHEN 'rechazado'        THEN monto_cobrado = 0 AND monto_devuelto = 0
        WHEN 'pagado'           THEN monto_cobrado > 0 AND monto_devuelto = 0
        WHEN 'devuelto_parcial' THEN monto_devuelto > 0 AND monto_devuelto < monto_cobrado
        WHEN 'anulado'          THEN monto_cobrado > 0 AND monto_devuelto = monto_cobrado
        ELSE false END);

-- =============================================================================
-- participacion · se mantiene (una por cargo con un solo pagador), con los mismos montos
-- =============================================================================
ALTER TABLE participacion DROP CONSTRAINT participacion_estado_check, DROP CONSTRAINT participacion_captura_tope;
ALTER TABLE participacion
    ADD COLUMN monto_cobrado  bigint NOT NULL DEFAULT 0 CHECK (monto_cobrado >= 0),
    ADD COLUMN monto_devuelto bigint NOT NULL DEFAULT 0 CHECK (monto_devuelto >= 0);
UPDATE participacion SET monto_cobrado = CASE
    WHEN estado = 'capturada' THEN monto_capturado
    WHEN estado IN ('autorizada', 'revertida') THEN monto_autorizado
    ELSE 0 END;
UPDATE participacion SET
    monto_devuelto = CASE WHEN estado = 'revertida' THEN monto_cobrado ELSE 0 END,
    estado = CASE
        WHEN estado IN ('pendiente', 'autorizando') THEN 'pendiente'
        WHEN monto_cobrado = 0 THEN 'rechazada'
        WHEN estado = 'revertida' THEN 'anulada'
        ELSE 'pagada' END;
ALTER TABLE participacion DROP COLUMN monto_comprometido, DROP COLUMN monto_autorizado, DROP COLUMN monto_capturado;
ALTER TABLE participacion
    ADD CONSTRAINT participacion_estado_check CHECK (estado IN
        ('pendiente', 'pagada', 'rechazada', 'devuelta_parcial', 'anulada')),
    ADD CONSTRAINT participacion_devolucion_tope CHECK (monto_devuelto <= monto_cobrado),
    ADD CONSTRAINT participacion_estado_montos CHECK (CASE estado
        WHEN 'pendiente'        THEN monto_cobrado = 0 AND monto_devuelto = 0
        WHEN 'rechazada'        THEN monto_cobrado = 0 AND monto_devuelto = 0
        WHEN 'pagada'           THEN monto_cobrado > 0 AND monto_devuelto = 0
        WHEN 'devuelta_parcial' THEN monto_devuelto > 0 AND monto_devuelto < monto_cobrado
        WHEN 'anulada'          THEN monto_cobrado > 0 AND monto_devuelto = monto_cobrado
        ELSE false END);

-- =============================================================================
-- transaccion_pasarela · venta normal de Webpay Plus y su anulación (total o parcial)
-- =============================================================================
ALTER TABLE transaccion_pasarela DROP CONSTRAINT transaccion_pasarela_tipo_check;
UPDATE transaccion_pasarela SET tipo = CASE WHEN tipo = 'reversa' THEN 'anulacion' ELSE 'venta' END;
ALTER TABLE transaccion_pasarela
    ADD CONSTRAINT transaccion_pasarela_tipo_check CHECK (tipo IN ('venta', 'anulacion'));

SELECT set_config('app.rol', '', true);
"""

DOWNGRADE = """
SELECT set_config('app.rol', 'operacion', true);

-- =============================================================================
-- transaccion_pasarela
-- =============================================================================
ALTER TABLE transaccion_pasarela DROP CONSTRAINT transaccion_pasarela_tipo_check;
UPDATE transaccion_pasarela SET tipo = CASE WHEN tipo = 'anulacion' THEN 'reversa' ELSE 'autorizacion' END;
ALTER TABLE transaccion_pasarela
    ADD CONSTRAINT transaccion_pasarela_tipo_check CHECK (tipo IN ('autorizacion', 'ampliacion', 'captura', 'reversa'));

-- =============================================================================
-- participacion (antes que pedido: toma el total del pedido)
-- =============================================================================
ALTER TABLE participacion DROP CONSTRAINT participacion_estado_check,
    DROP CONSTRAINT participacion_devolucion_tope, DROP CONSTRAINT participacion_estado_montos;
ALTER TABLE participacion
    ADD COLUMN monto_comprometido bigint CHECK (monto_comprometido > 0),
    ADD COLUMN monto_autorizado   bigint NOT NULL DEFAULT 0 CHECK (monto_autorizado >= 0),
    ADD COLUMN monto_capturado    bigint NOT NULL DEFAULT 0 CHECK (monto_capturado >= 0);
UPDATE participacion pa SET
    monto_comprometido = greatest(pa.monto_cobrado, 1, coalesce((
        SELECT p.total * pa.porcentaje_bp / 10000 FROM cargo c JOIN pedido p ON p.id = c.pedido_id
         WHERE c.id = pa.cargo_id), 0)),
    monto_autorizado = pa.monto_cobrado,
    monto_capturado  = CASE WHEN pa.estado IN ('pagada', 'devuelta_parcial') THEN pa.monto_cobrado ELSE 0 END,
    estado = CASE pa.estado
        WHEN 'pagada'           THEN 'capturada'
        WHEN 'devuelta_parcial' THEN 'capturada'
        WHEN 'anulada'          THEN 'revertida'
        ELSE pa.estado END;
ALTER TABLE participacion ALTER COLUMN monto_comprometido SET NOT NULL;
ALTER TABLE participacion DROP COLUMN monto_cobrado, DROP COLUMN monto_devuelto;
ALTER TABLE participacion
    ADD CONSTRAINT participacion_estado_check CHECK (estado IN ('pendiente', 'autorizando',
        'autorizada', 'rechazada', 'vencida', 'capturada', 'revertida')),
    ADD CONSTRAINT participacion_captura_tope CHECK (monto_capturado <= monto_autorizado);

-- =============================================================================
-- cargo
-- =============================================================================
ALTER TABLE cargo DROP CONSTRAINT cargo_estado_check,
    DROP CONSTRAINT cargo_devolucion_tope, DROP CONSTRAINT cargo_estado_montos;
ALTER TABLE cargo
    ADD COLUMN monto_objetivo        bigint CHECK (monto_objetivo > 0),
    ADD COLUMN margen_bp             integer NOT NULL DEFAULT 1500 CHECK (margen_bp BETWEEN 0 AND 5000),
    ADD COLUMN monto_autorizado      bigint NOT NULL DEFAULT 0 CHECK (monto_autorizado >= 0),
    ADD COLUMN monto_capturado       bigint NOT NULL DEFAULT 0 CHECK (monto_capturado >= 0),
    ADD COLUMN recaudacion_expira_en timestamptz;
UPDATE cargo c SET
    monto_objetivo = greatest(c.monto_cobrado, 1,
        coalesce((SELECT p.total FROM pedido p WHERE p.id = c.pedido_id), 0)),
    monto_autorizado = c.monto_cobrado,
    monto_capturado  = CASE WHEN c.estado IN ('pagado', 'devuelto_parcial') THEN c.monto_cobrado ELSE 0 END,
    recaudacion_expira_en = c.creado_en,
    estado = CASE c.estado
        WHEN 'pendiente'        THEN 'creado'
        WHEN 'pagado'           THEN 'capturado'
        WHEN 'rechazado'        THEN 'fallido'
        WHEN 'devuelto_parcial' THEN 'reembolsado_parcial'
        WHEN 'anulado'          THEN 'revertido'
        ELSE c.estado END;
ALTER TABLE cargo ALTER COLUMN monto_objetivo SET NOT NULL,
                  ALTER COLUMN recaudacion_expira_en SET NOT NULL,
                  ALTER COLUMN estado SET DEFAULT 'creado';
ALTER TABLE cargo DROP COLUMN monto_cobrado, DROP COLUMN monto_devuelto;
ALTER TABLE cargo
    ADD CONSTRAINT cargo_estado_check CHECK (estado IN ('creado', 'recaudando',
        'redistribuyendo', 'completo', 'fallido', 'capturado', 'revertido', 'reembolsado_parcial')),
    ADD CONSTRAINT cargo_captura_tope CHECK (monto_capturado <= monto_autorizado);

-- =============================================================================
-- pedido_linea
-- =============================================================================
DROP TRIGGER pedido_linea_pagada_fija ON pedido_linea;
DROP TRIGGER pedido_linea_mismo_producto ON pedido_linea;
DROP FUNCTION pedido_linea_pagada_fija();
DROP FUNCTION pedido_linea_mismo_producto();
ALTER TABLE pedido_linea DROP CONSTRAINT pedido_linea_estado_linea_check,
    DROP CONSTRAINT pedido_linea_devolucion_tope, DROP CONSTRAINT pedido_linea_devuelta,
    DROP CONSTRAINT pedido_linea_reasignacion, DROP CONSTRAINT pedido_linea_reasigna_otra_oferta;
UPDATE pedido_linea SET estado_linea = CASE estado_linea
    WHEN 'devuelta'  THEN 'faltante'
    WHEN 'sin_stock' THEN 'eliminada'
    ELSE estado_linea END;
ALTER TABLE pedido_linea DROP COLUMN monto_devuelto, DROP COLUMN devuelta_en, DROP COLUMN oferta_reasignada_id,
                         DROP COLUMN precio_reasignado, DROP COLUMN reasignada_en;
ALTER TABLE pedido_linea RENAME CONSTRAINT pedido_linea_precio_unitario_check TO pedido_linea_precio_snapshot_check;
ALTER TABLE pedido_linea RENAME COLUMN precio_unitario TO precio_snapshot;
ALTER TABLE pedido_linea
    ADD COLUMN precio_real           bigint CHECK (precio_real >= 0),
    ADD COLUMN sustituto_de_linea_id uuid REFERENCES pedido_linea(id);
ALTER TABLE pedido_linea
    ADD CONSTRAINT pedido_linea_estado_linea_check CHECK (estado_linea IN
        ('pendiente', 'preparada', 'faltante', 'requiere_decision', 'sustituida', 'eliminada')),
    ADD CONSTRAINT pedido_linea_no_autosustituye CHECK (sustituto_de_linea_id IS DISTINCT FROM id);

-- =============================================================================
-- pedido
-- =============================================================================
ALTER POLICY pedido_comercio_ver ON pedido USING (
    comercio_id = app_comercio()
    AND estado NOT IN ('borrador', 'pendiente_recaudacion', 'autorizado', 'expirado'));
ALTER POLICY pedido_comercio_actualizar ON pedido USING (
    comercio_id = app_comercio()
    AND estado NOT IN ('borrador', 'pendiente_recaudacion', 'autorizado', 'expirado'));

DROP INDEX pedido_comercio_dia_ix;

ALTER TABLE pedido DROP CONSTRAINT pedido_estado_check, DROP CONSTRAINT pedido_total_exacto,
    DROP CONSTRAINT pedido_total_vigencia, DROP CONSTRAINT pedido_total_confirmado_positivo,
    DROP CONSTRAINT pedido_pago_confirmado, DROP CONSTRAINT pedido_estado_pago,
    DROP CONSTRAINT pedido_estado_confirmado;
ALTER TABLE pedido
    ADD COLUMN total_estimado   bigint NOT NULL DEFAULT 0 CHECK (total_estimado >= 0),
    ADD COLUMN total_autorizado bigint CHECK (total_autorizado >= 0),
    ADD COLUMN total_real       bigint CHECK (total_real >= 0);
UPDATE pedido SET
    total_estimado   = total,
    total_autorizado = CASE WHEN pagado_en IS NOT NULL THEN total END,
    estado = CASE estado
        WHEN 'total_confirmado' THEN 'pendiente_recaudacion'
        WHEN 'pagado'           THEN 'autorizado'
        WHEN 'vencido'          THEN 'expirado'
        ELSE estado END;
ALTER TABLE pedido DROP COLUMN subtotal_productos, DROP COLUMN costo_envio, DROP COLUMN total,
                   DROP COLUMN total_confirmado_en, DROP COLUMN total_vence_en, DROP COLUMN pagado_en;
ALTER TABLE pedido ADD CONSTRAINT pedido_estado_check CHECK (estado IN (
    'borrador', 'pendiente_recaudacion', 'autorizado', 'expirado', 'enviado_a_comercio',
    'preparando', 'requiere_decision', 'listo_retiro', 'asignado', 'sin_repartidor',
    'retirado', 'en_ruta', 'entregado', 'no_entregado', 'reprogramado',
    'captura_pendiente', 'incobrable', 'cerrado', 'cancelado', 'cancelado_con_devolucion'));

CREATE INDEX pedido_comercio_dia_ix ON pedido (comercio_id, estado, creado_en)
    WHERE estado NOT IN ('borrador', 'cerrado', 'cancelado', 'expirado');

SELECT set_config('app.rol', '', true);
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

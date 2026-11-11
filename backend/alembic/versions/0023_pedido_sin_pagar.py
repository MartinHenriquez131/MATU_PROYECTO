"""MATU-61: el pedido sin pagar (carrito, total confirmado y cancelar), la dirección y la autorización de pedidos.

Cadena: 0022 (MATU-74) -> 0023. down_revision = "0022".

Decisiones 188 a 219 de docs/api/README.md, decisiones D1 a D12 de Jorge (revisión previa del analista) y C1 a C9.

a) direccion.version (el ETag de PUT y DELETE …/direccion, decisiones 189 y 216) y CHECK de lat y lng nulas en
   direccion y pedido_entrega (C8: «No guardamos su ubicación en el mapa»). Antes del CHECK se vacían. La copia
   de la entrega suma region y telefono_origen (celular_cuenta o escrito, decisión 203).
b) comercio.ficticio boolean NOT NULL DEFAULT true (D9).
c) app_escribe_pedido() (admin o cuidador activo) y app_ve_entrega() (admin, cuidador o pagador activo): los roles
   de C3 en la base.
d) pedido: sale destinatario_nombre_pila (C16); comercio_id deja de ser obligatorio (D7: un registro por comercio en
   pedido_comercio); condiciones_version, condiciones_aceptadas_en y condiciones_huella, juntas o ninguna, y el
   CHECK de que no hay pagado_en sin condiciones_aceptadas_en (D6). Ese CHECK va NOT VALID: alcanza a toda fila
   nueva o cambiada, y no a los pedidos pagados que ya existieran (no los hay fuera de las pruebas de migración).
   pedido_sin_pagar_uq: un solo pedido sin pagar (borrador, total_confirmado o vencido) por persona (C4).
e) pedido_comercio (D7, R8): un registro por comercio dentro del pedido, con su referencia opaca (C22). Lleva
   grupo_id, como acceso_relevo, para que sus políticas no consulten pedido: así la política del comercio sobre
   pedido puede mirar pedido_comercio sin recursión. RLS forzado. El comercio ve su registro, y por él sus líneas y
   el pedido, recién con enviado_en (MATU-63 lo fija); nunca la entrega, las transiciones ni las otras líneas.
f) pedido_linea: pedido_comercio_id, el precio y la oferta del carrito (precio_carrito, oferta_carrito_id; C15) y
   la copia de retracto_pierde_al_abrir al confirmar (C3). Un trigger completa los del carrito con los de la línea
   si no vienen, y pedido_linea_mismo_producto exige que la oferta del carrito sea del mismo producto.
g) regla_sustitucion queda fija con el pedido pagado (C12): trigger regla_sustitucion_pagada_fija.
h) Políticas por operación y por rol (C13, y las FOR ALL que la 0020 dejó para MATU-61): pedido_familia,
   pedido_operacion, entrega_familia, linea_hereda, regla_hereda, transicion_hereda e idempotencia_familia. Leen
   todos los miembros del grupo (C3), salvo la entrega, que no ve el observador; escriben admin y cuidador
   (app_escribe_pedido). Sin política de DELETE para la familia en pedido, y la entrega, las líneas, las reglas y
   las partes por comercio las borran admin y cuidador. pedido_comercio_ver y pedido_comercio_actualizar pasan a
   mirar pedido_comercio. Las políticas TO matu_owner existentes no se tocan; se agregan las de la conservación.
i) idempotencia guarda solo el estado HTTP y el id del pedido (D5): sale respuesta, entra pedido_id (ON DELETE
   CASCADE). Leen los del grupo (para detectar la clave de otra cuenta), escribe solo la cuenta dueña.
j) plan_reposicion_linea.perfil_consumo_id ON DELETE SET NULL (D3): borrar perfiles ya no falla por una reposición.
k) pedido_transicion: motivo de una lista cerrada (C19), ON DELETE CASCADE desde pedido, y el trigger de solo
   inserción deja borrar solo dentro de la cascada de un pedido que ya no está (D5).
l) pedido_conservar(limite, ahora), SECURITY DEFINER, dueño matu_owner, solo para matu_scheduler y con
   app.rol = 'operacion' (D5): borra los pedidos no pagados (borrador, total confirmado, vencido o cancelado sin
   pago) sin cambios desde limite, que debe ser de 30 días o más, y las claves de idempotencia vencidas.

backend/db/*.sql no se tocan. downgrade() deja el esquema como en 0022; si queda un pedido sin comercio_id (los
de MATU-61), el downgrade falla en SET NOT NULL y no borra nada.

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


DEL_GRUPO_ESCRIBE = "grupo_id = app_grupo() AND (SELECT app_escribe_pedido())"
PEDIDO_DEL_GRUPO = "SELECT 1 FROM pedido p WHERE p.id = {tabla}.pedido_id AND p.grupo_id = app_grupo()"
ESTADOS_NO_ENVIADOS = "('borrador', 'total_confirmado', 'vencido', 'pagado')"
MOTIVOS = "('total_vencio', 'familia_cancela', 'familia_cambia_carrito', 'autorizacion_retirada', 'persona_borrada')"


def _escribe(tabla: str) -> str:
    return f"EXISTS ({PEDIDO_DEL_GRUPO.format(tabla=tabla)}) AND (SELECT app_escribe_pedido())"


UPGRADE = f"""
SELECT set_config('app.rol', 'operacion', true);

-- (a) La dirección: versión y sin ubicación (C8)
ALTER TABLE direccion ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE direccion ADD CONSTRAINT direccion_version_positiva CHECK (version > 0);
UPDATE direccion SET lat = NULL, lng = NULL WHERE lat IS NOT NULL OR lng IS NOT NULL;
ALTER TABLE direccion ADD CONSTRAINT direccion_sin_ubicacion CHECK (lat IS NULL AND lng IS NULL);
UPDATE pedido_entrega SET lat = NULL, lng = NULL WHERE lat IS NOT NULL OR lng IS NOT NULL;
ALTER TABLE pedido_entrega ADD CONSTRAINT pedido_entrega_sin_ubicacion CHECK (lat IS NULL AND lng IS NULL);
-- La copia lleva la región, como la dirección, y de dónde salió el teléfono (decisión 203)
ALTER TABLE pedido_entrega ADD COLUMN region text NOT NULL DEFAULT 'Metropolitana';
ALTER TABLE pedido_entrega ADD COLUMN telefono_origen text NOT NULL DEFAULT 'escrito';
ALTER TABLE pedido_entrega ADD CONSTRAINT pedido_entrega_telefono_origen
    CHECK (telefono_origen IN ('celular_cuenta', 'escrito'));

-- (b) D9
ALTER TABLE comercio ADD COLUMN ficticio boolean NOT NULL DEFAULT true;

-- (c) Los roles de C3
CREATE FUNCTION app_escribe_pedido() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT EXISTS (SELECT 1 FROM membresia m
                  WHERE m.grupo_id = app_grupo() AND m.usuario_id = app_usuario()
                    AND m.estado = 'activa' AND m.rol IN ('admin', 'cuidador')) $$;
CREATE FUNCTION app_ve_entrega() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT EXISTS (SELECT 1 FROM membresia m
                  WHERE m.grupo_id = app_grupo() AND m.usuario_id = app_usuario()
                    AND m.estado = 'activa' AND m.rol IN ('admin', 'cuidador', 'pagador')) $$;

-- (d) pedido
ALTER TABLE pedido DROP COLUMN destinatario_nombre_pila;
ALTER TABLE pedido ALTER COLUMN comercio_id DROP NOT NULL;
ALTER TABLE pedido ADD COLUMN condiciones_version text;
ALTER TABLE pedido ADD COLUMN condiciones_aceptadas_en timestamptz;
ALTER TABLE pedido ADD COLUMN condiciones_huella text;
ALTER TABLE pedido ADD CONSTRAINT pedido_condiciones_completas CHECK (
    (condiciones_version IS NULL) = (condiciones_aceptadas_en IS NULL)
    AND (condiciones_version IS NULL) = (condiciones_huella IS NULL));
ALTER TABLE pedido ADD CONSTRAINT pedido_condiciones_huella CHECK (condiciones_huella ~ '^[0-9a-f]{{64}}$');
ALTER TABLE pedido ADD CONSTRAINT pedido_pago_con_condiciones
    CHECK (pagado_en IS NULL OR condiciones_aceptadas_en IS NOT NULL) NOT VALID;
-- C4: un solo pedido sin pagar por persona
CREATE UNIQUE INDEX pedido_sin_pagar_uq ON pedido (persona_cuidada_id)
    WHERE estado IN ('borrador', 'total_confirmado', 'vencido');

-- (e) Un registro por comercio dentro del pedido (D7)
CREATE TABLE pedido_comercio (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    grupo_id    uuid NOT NULL REFERENCES grupo_familiar(id),
    pedido_id   uuid NOT NULL REFERENCES pedido(id) ON DELETE CASCADE,
    comercio_id uuid NOT NULL REFERENCES comercio(id),
    referencia  text NOT NULL UNIQUE CHECK (length(referencia) BETWEEN 16 AND 64),
    enviado_en  timestamptz,
    creado_en   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pedido_comercio_uq UNIQUE (pedido_id, comercio_id)
);
CREATE INDEX pedido_comercio_comercio_ix ON pedido_comercio (comercio_id) WHERE enviado_en IS NOT NULL;
ALTER TABLE pedido_comercio ENABLE ROW LEVEL SECURITY;
ALTER TABLE pedido_comercio FORCE ROW LEVEL SECURITY;
CREATE FUNCTION pedido_comercio_mismo_grupo() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pedido p WHERE p.id = NEW.pedido_id AND p.grupo_id = NEW.grupo_id) THEN
        RAISE EXCEPTION 'la parte por comercio es del grupo de su pedido' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER pedido_comercio_mismo_grupo BEFORE INSERT OR UPDATE ON pedido_comercio
    FOR EACH ROW EXECUTE FUNCTION pedido_comercio_mismo_grupo();
CREATE POLICY pedido_comercio_familia_leer ON pedido_comercio FOR SELECT USING (grupo_id = app_grupo());
CREATE POLICY pedido_comercio_familia_crear ON pedido_comercio FOR INSERT WITH CHECK ({DEL_GRUPO_ESCRIBE});
CREATE POLICY pedido_comercio_familia_borrar ON pedido_comercio FOR DELETE USING ({DEL_GRUPO_ESCRIBE});
CREATE POLICY pedido_comercio_propio ON pedido_comercio FOR SELECT
    USING (comercio_id = app_comercio() AND enviado_en IS NOT NULL);
CREATE POLICY pedido_comercio_operacion_leer ON pedido_comercio FOR SELECT USING (app_rol() = 'operacion');
GRANT SELECT, INSERT, DELETE ON pedido_comercio TO matu_app;

-- (f) Líneas: la parte por comercio, el carrito y la copia del retracto
ALTER TABLE pedido_linea ADD COLUMN pedido_comercio_id uuid REFERENCES pedido_comercio(id) ON DELETE SET NULL;
ALTER TABLE pedido_linea ADD COLUMN precio_carrito bigint;
ALTER TABLE pedido_linea ADD COLUMN oferta_carrito_id uuid REFERENCES oferta(id);
ALTER TABLE pedido_linea ADD COLUMN retracto_pierde_al_abrir boolean;
UPDATE pedido_linea SET precio_carrito = precio_unitario, oferta_carrito_id = oferta_id;
ALTER TABLE pedido_linea ALTER COLUMN precio_carrito SET NOT NULL;
ALTER TABLE pedido_linea ALTER COLUMN oferta_carrito_id SET NOT NULL;
ALTER TABLE pedido_linea ADD CONSTRAINT pedido_linea_precio_carrito_positivo CHECK (precio_carrito > 0);
CREATE FUNCTION pedido_linea_carrito_por_omision() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    NEW.precio_carrito := COALESCE(NEW.precio_carrito, NEW.precio_unitario);
    NEW.oferta_carrito_id := COALESCE(NEW.oferta_carrito_id, NEW.oferta_id);
    RETURN NEW;
END $$;
CREATE TRIGGER pedido_linea_carrito_por_omision BEFORE INSERT ON pedido_linea
    FOR EACH ROW EXECUTE FUNCTION pedido_linea_carrito_por_omision();
CREATE OR REPLACE FUNCTION pedido_linea_mismo_producto() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM oferta o WHERE o.id = NEW.oferta_id AND o.producto_id = NEW.producto_id) THEN
        RAISE EXCEPTION 'la oferta de la línea es de otro producto' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.oferta_reasignada_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM oferta o WHERE o.id = NEW.oferta_reasignada_id AND o.producto_id = NEW.producto_id) THEN
        RAISE EXCEPTION 'la reasignación es del mismo producto, nunca de otra marca' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.oferta_carrito_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM oferta o WHERE o.id = NEW.oferta_carrito_id AND o.producto_id = NEW.producto_id) THEN
        RAISE EXCEPTION 'la oferta del carrito es del mismo producto' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- (g) C12: la regla de faltante queda fija con el pedido pagado
CREATE FUNCTION regla_sustitucion_pagada_fija() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF EXISTS (SELECT 1 FROM pedido p
               WHERE p.id = COALESCE(NEW.pedido_id, OLD.pedido_id) AND p.pagado_en IS NOT NULL) THEN
        RAISE EXCEPTION 'el pedido ya está pagado: la regla de faltante queda fija' USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.pedido_id IS DISTINCT FROM OLD.pedido_id AND EXISTS (
        SELECT 1 FROM pedido p WHERE p.id = OLD.pedido_id AND p.pagado_en IS NOT NULL) THEN
        RAISE EXCEPTION 'el pedido ya está pagado: la regla de faltante queda fija' USING ERRCODE = 'check_violation';
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;
CREATE TRIGGER regla_sustitucion_pagada_fija BEFORE INSERT OR UPDATE OR DELETE ON regla_sustitucion
    FOR EACH ROW EXECUTE FUNCTION regla_sustitucion_pagada_fija();

-- (h) Políticas por operación y por rol
DROP POLICY pedido_familia ON pedido;
DROP POLICY pedido_operacion ON pedido;
DROP POLICY pedido_comercio_ver ON pedido;
DROP POLICY pedido_comercio_actualizar ON pedido;
CREATE POLICY pedido_familia_leer ON pedido FOR SELECT USING (grupo_id = app_grupo());
CREATE POLICY pedido_familia_crear ON pedido FOR INSERT WITH CHECK ({DEL_GRUPO_ESCRIBE});
CREATE POLICY pedido_familia_editar ON pedido FOR UPDATE USING ({DEL_GRUPO_ESCRIBE}) WITH CHECK ({DEL_GRUPO_ESCRIBE});
CREATE POLICY pedido_operacion_leer ON pedido FOR SELECT USING (app_rol() = 'operacion');
CREATE POLICY pedido_comercio_ver ON pedido FOR SELECT USING (
    pagado_en IS NOT NULL AND estado NOT IN {ESTADOS_NO_ENVIADOS}
    AND EXISTS (SELECT 1 FROM pedido_comercio pc WHERE pc.pedido_id = pedido.id
                AND pc.comercio_id = app_comercio() AND pc.enviado_en IS NOT NULL));
CREATE POLICY pedido_comercio_actualizar ON pedido FOR UPDATE USING (
    pagado_en IS NOT NULL AND estado NOT IN {ESTADOS_NO_ENVIADOS}
    AND EXISTS (SELECT 1 FROM pedido_comercio pc WHERE pc.pedido_id = pedido.id
                AND pc.comercio_id = app_comercio() AND pc.enviado_en IS NOT NULL));
-- D5: la conservación, solo matu_owner dentro de pedido_conservar
CREATE POLICY pedido_conservacion_borrar ON pedido FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion' AND pagado_en IS NULL);

DROP POLICY entrega_familia ON pedido_entrega;
CREATE POLICY entrega_familia_leer ON pedido_entrega FOR SELECT
    USING (EXISTS ({PEDIDO_DEL_GRUPO.format(tabla="pedido_entrega")}) AND (SELECT app_ve_entrega()));
CREATE POLICY entrega_familia_crear ON pedido_entrega FOR INSERT WITH CHECK ({_escribe("pedido_entrega")});
CREATE POLICY entrega_familia_editar ON pedido_entrega FOR UPDATE
    USING ({_escribe("pedido_entrega")}) WITH CHECK ({_escribe("pedido_entrega")});
CREATE POLICY entrega_familia_borrar ON pedido_entrega FOR DELETE USING ({_escribe("pedido_entrega")});

DROP POLICY linea_hereda ON pedido_linea;
CREATE POLICY linea_leer ON pedido_linea FOR SELECT USING (
    app_repartidor() IS NULL AND app_comercio() IS NULL
    AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = pedido_linea.pedido_id));
CREATE POLICY linea_comercio_ver ON pedido_linea FOR SELECT USING (
    EXISTS (SELECT 1 FROM pedido_comercio pc WHERE pc.id = pedido_linea.pedido_comercio_id
            AND pc.comercio_id = app_comercio() AND pc.enviado_en IS NOT NULL));
CREATE POLICY linea_crear ON pedido_linea FOR INSERT WITH CHECK ({_escribe("pedido_linea")});
CREATE POLICY linea_editar ON pedido_linea FOR UPDATE
    USING ({_escribe("pedido_linea")}) WITH CHECK ({_escribe("pedido_linea")});
CREATE POLICY linea_borrar ON pedido_linea FOR DELETE USING ({_escribe("pedido_linea")});

DROP POLICY regla_hereda ON regla_sustitucion;
CREATE POLICY regla_leer ON regla_sustitucion FOR SELECT USING (
    app_repartidor() IS NULL AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = regla_sustitucion.pedido_id));
CREATE POLICY regla_crear ON regla_sustitucion FOR INSERT WITH CHECK ({_escribe("regla_sustitucion")});
CREATE POLICY regla_editar ON regla_sustitucion FOR UPDATE
    USING ({_escribe("regla_sustitucion")}) WITH CHECK ({_escribe("regla_sustitucion")});
CREATE POLICY regla_borrar ON regla_sustitucion FOR DELETE USING ({_escribe("regla_sustitucion")});

DROP POLICY transicion_hereda ON pedido_transicion;
CREATE POLICY transicion_leer ON pedido_transicion FOR SELECT USING (
    app_comercio() IS NULL AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = pedido_transicion.pedido_id));
CREATE POLICY transicion_crear ON pedido_transicion FOR INSERT WITH CHECK ({_escribe("pedido_transicion")});

-- (i) idempotencia: solo el estado y el id del pedido (D5)
ALTER TABLE idempotencia DROP COLUMN respuesta;
ALTER TABLE idempotencia ADD COLUMN pedido_id uuid REFERENCES pedido(id) ON DELETE CASCADE;
DROP POLICY idempotencia_familia ON idempotencia;
CREATE POLICY idempotencia_leer ON idempotencia FOR SELECT USING (grupo_id = app_grupo());
CREATE POLICY idempotencia_crear ON idempotencia FOR INSERT
    WITH CHECK (grupo_id = app_grupo() AND usuario_id = app_usuario());
CREATE POLICY idempotencia_editar ON idempotencia FOR UPDATE
    USING (grupo_id = app_grupo() AND usuario_id = app_usuario())
    WITH CHECK (grupo_id = app_grupo() AND usuario_id = app_usuario());
CREATE POLICY idempotencia_conservacion ON idempotencia FOR SELECT TO matu_owner USING (app_rol() = 'operacion');
CREATE POLICY idempotencia_conservacion_borrar ON idempotencia FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion');

-- (j) D3
ALTER TABLE plan_reposicion_linea DROP CONSTRAINT plan_reposicion_linea_perfil_consumo_id_fkey;
ALTER TABLE plan_reposicion_linea ADD CONSTRAINT plan_reposicion_linea_perfil_consumo_id_fkey
    FOREIGN KEY (perfil_consumo_id) REFERENCES perfil_consumo(id) ON DELETE SET NULL;

-- (k) La línea de tiempo: lista cerrada de motivos (C19) y se borra solo con su pedido (D5)
ALTER TABLE pedido_transicion ADD CONSTRAINT pedido_transicion_motivo
    CHECK (motivo IS NULL OR motivo IN {MOTIVOS});
ALTER TABLE pedido_transicion DROP CONSTRAINT pedido_transicion_pedido_id_fkey;
ALTER TABLE pedido_transicion ADD CONSTRAINT pedido_transicion_pedido_id_fkey
    FOREIGN KEY (pedido_id) REFERENCES pedido(id) ON DELETE CASCADE;
CREATE FUNCTION transicion_solo_insercion() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    -- Solo en la cascada del borrado de su pedido (pedido_conservar): el pedido ya no está
    IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1
       AND NOT EXISTS (SELECT 1 FROM pedido p WHERE p.id = OLD.pedido_id) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'tabla de solo inserción' USING ERRCODE = 'insufficient_privilege';
END $$;
DROP TRIGGER transicion_solo_insercion ON pedido_transicion;
CREATE TRIGGER transicion_solo_insercion BEFORE UPDATE OR DELETE ON pedido_transicion
    FOR EACH ROW EXECUTE FUNCTION transicion_solo_insercion();

-- (l) D5: lo no pagado se borra a los 30 días
CREATE FUNCTION pedido_conservar(limite timestamptz, ahora timestamptz)
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
       AND actualizado_en <= limite;
    GET DIAGNOSTICS pedidos = ROW_COUNT;
    DELETE FROM public.idempotencia WHERE expira_en <= ahora;
    GET DIAGNOSTICS idempotencias = ROW_COUNT;
    RETURN NEXT;
END $$;
REVOKE ALL ON FUNCTION pedido_conservar(timestamptz, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION pedido_conservar(timestamptz, timestamptz) TO matu_scheduler;

SELECT set_config('app.rol', '', true);
"""

DOWNGRADE = f"""
SELECT set_config('app.rol', 'operacion', true);

-- (l)
DROP FUNCTION pedido_conservar(timestamptz, timestamptz);

-- (k)
DROP TRIGGER transicion_solo_insercion ON pedido_transicion;
CREATE TRIGGER transicion_solo_insercion BEFORE UPDATE OR DELETE ON pedido_transicion
    FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion();
DROP FUNCTION transicion_solo_insercion();
ALTER TABLE pedido_transicion DROP CONSTRAINT pedido_transicion_pedido_id_fkey;
ALTER TABLE pedido_transicion ADD CONSTRAINT pedido_transicion_pedido_id_fkey
    FOREIGN KEY (pedido_id) REFERENCES pedido(id);
ALTER TABLE pedido_transicion DROP CONSTRAINT pedido_transicion_motivo;

-- (j)
ALTER TABLE plan_reposicion_linea DROP CONSTRAINT plan_reposicion_linea_perfil_consumo_id_fkey;
ALTER TABLE plan_reposicion_linea ADD CONSTRAINT plan_reposicion_linea_perfil_consumo_id_fkey
    FOREIGN KEY (perfil_consumo_id) REFERENCES perfil_consumo(id);

-- (i)
DROP POLICY idempotencia_conservacion_borrar ON idempotencia;
DROP POLICY idempotencia_conservacion ON idempotencia;
DROP POLICY idempotencia_editar ON idempotencia;
DROP POLICY idempotencia_crear ON idempotencia;
DROP POLICY idempotencia_leer ON idempotencia;
CREATE POLICY idempotencia_familia ON idempotencia USING (grupo_id = app_grupo());
ALTER TABLE idempotencia DROP COLUMN pedido_id;
ALTER TABLE idempotencia ADD COLUMN respuesta jsonb;

-- (h)
DROP POLICY transicion_crear ON pedido_transicion;
DROP POLICY transicion_leer ON pedido_transicion;
CREATE POLICY transicion_hereda ON pedido_transicion
    USING (EXISTS (SELECT 1 FROM pedido p WHERE p.id = pedido_transicion.pedido_id));

DROP POLICY regla_borrar ON regla_sustitucion;
DROP POLICY regla_editar ON regla_sustitucion;
DROP POLICY regla_crear ON regla_sustitucion;
DROP POLICY regla_leer ON regla_sustitucion;
CREATE POLICY regla_hereda ON regla_sustitucion USING (
    app_repartidor() IS NULL AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = regla_sustitucion.pedido_id));

DROP POLICY linea_borrar ON pedido_linea;
DROP POLICY linea_editar ON pedido_linea;
DROP POLICY linea_crear ON pedido_linea;
DROP POLICY linea_comercio_ver ON pedido_linea;
DROP POLICY linea_leer ON pedido_linea;
CREATE POLICY linea_hereda ON pedido_linea USING (
    app_repartidor() IS NULL AND EXISTS (SELECT 1 FROM pedido p WHERE p.id = pedido_linea.pedido_id));

DROP POLICY entrega_familia_borrar ON pedido_entrega;
DROP POLICY entrega_familia_editar ON pedido_entrega;
DROP POLICY entrega_familia_crear ON pedido_entrega;
DROP POLICY entrega_familia_leer ON pedido_entrega;
CREATE POLICY entrega_familia ON pedido_entrega
    USING (EXISTS ({PEDIDO_DEL_GRUPO.format(tabla="pedido_entrega")}));

-- Antes de devolver comercio_id NOT NULL y sus políticas: el comercio de la primera parte o línea
UPDATE pedido SET comercio_id = COALESCE(
    (SELECT pc.comercio_id FROM pedido_comercio pc WHERE pc.pedido_id = pedido.id ORDER BY pc.creado_en, pc.id
      LIMIT 1),
    (SELECT o.comercio_id FROM pedido_linea l JOIN oferta o ON o.id = l.oferta_carrito_id
      WHERE l.pedido_id = pedido.id ORDER BY l.creado_en, l.id LIMIT 1))
 WHERE comercio_id IS NULL;

DROP POLICY pedido_conservacion_borrar ON pedido;
DROP POLICY pedido_comercio_actualizar ON pedido;
DROP POLICY pedido_comercio_ver ON pedido;
DROP POLICY pedido_operacion_leer ON pedido;
DROP POLICY pedido_familia_editar ON pedido;
DROP POLICY pedido_familia_crear ON pedido;
DROP POLICY pedido_familia_leer ON pedido;
CREATE POLICY pedido_familia ON pedido USING (grupo_id = app_grupo());
CREATE POLICY pedido_operacion ON pedido USING (app_rol() = 'operacion');
CREATE POLICY pedido_comercio_ver ON pedido FOR SELECT USING (
    comercio_id = app_comercio() AND pagado_en IS NOT NULL AND estado NOT IN {ESTADOS_NO_ENVIADOS});
CREATE POLICY pedido_comercio_actualizar ON pedido FOR UPDATE USING (
    comercio_id = app_comercio() AND pagado_en IS NOT NULL AND estado NOT IN {ESTADOS_NO_ENVIADOS});

-- (g)
DROP TRIGGER regla_sustitucion_pagada_fija ON regla_sustitucion;
DROP FUNCTION regla_sustitucion_pagada_fija();

-- (f)
CREATE OR REPLACE FUNCTION pedido_linea_mismo_producto() RETURNS trigger LANGUAGE plpgsql AS
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
DROP TRIGGER pedido_linea_carrito_por_omision ON pedido_linea;
DROP FUNCTION pedido_linea_carrito_por_omision();
ALTER TABLE pedido_linea DROP COLUMN retracto_pierde_al_abrir;
ALTER TABLE pedido_linea DROP COLUMN oferta_carrito_id;
ALTER TABLE pedido_linea DROP COLUMN precio_carrito;
ALTER TABLE pedido_linea DROP COLUMN pedido_comercio_id;

-- (e)
DROP TABLE pedido_comercio;
DROP FUNCTION pedido_comercio_mismo_grupo();

-- (d)
DROP INDEX pedido_sin_pagar_uq;
ALTER TABLE pedido DROP CONSTRAINT pedido_pago_con_condiciones;
ALTER TABLE pedido DROP CONSTRAINT pedido_condiciones_huella;
ALTER TABLE pedido DROP CONSTRAINT pedido_condiciones_completas;
ALTER TABLE pedido DROP COLUMN condiciones_huella;
ALTER TABLE pedido DROP COLUMN condiciones_aceptadas_en;
ALTER TABLE pedido DROP COLUMN condiciones_version;
ALTER TABLE pedido ALTER COLUMN comercio_id SET NOT NULL;
ALTER TABLE pedido ADD COLUMN destinatario_nombre_pila text NOT NULL DEFAULT '';
ALTER TABLE pedido ALTER COLUMN destinatario_nombre_pila DROP DEFAULT;

-- (c)
DROP FUNCTION app_ve_entrega();
DROP FUNCTION app_escribe_pedido();

-- (b)
ALTER TABLE comercio DROP COLUMN ficticio;

-- (a)
ALTER TABLE pedido_entrega DROP CONSTRAINT pedido_entrega_telefono_origen;
ALTER TABLE pedido_entrega DROP COLUMN telefono_origen;
ALTER TABLE pedido_entrega DROP COLUMN region;
ALTER TABLE pedido_entrega DROP CONSTRAINT pedido_entrega_sin_ubicacion;
ALTER TABLE direccion DROP CONSTRAINT direccion_sin_ubicacion;
ALTER TABLE direccion DROP CONSTRAINT direccion_version_positiva;
ALTER TABLE direccion DROP COLUMN version;

SELECT set_config('app.rol', '', true);
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

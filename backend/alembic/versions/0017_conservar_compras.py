"""MATU-51: las compras declaradas se conservan 90 días (decisiones 145 y 146).

Cadena: 0016 (MATU-44) -> 0017. down_revision = "0016".

a) quiebre_conservar(limite_alertas, limite_eventos, ahora) borra además las reposicion con origen
   'declarada' y registrada_en <= limite_alertas (90 días, decisión A de Jorge del 07-11), y devuelve un
   cuarto contador, reposiciones. Cambiar el RETURNS TABLE exige DROP y CREATE: se repiten el REVOKE de
   PUBLIC y el GRANT EXECUTE a matu_app. Los controles no cambian: app.rol = 'operacion', 90 y 30 días,
   ahora no futuro, SECURITY DEFINER, dueño matu_owner y search_path fijo.

b) reposicion_conservacion (SELECT) y reposicion_conservacion_borrar (DELETE), solo para matu_owner y solo
   con app.rol = 'operacion', porque matu_owner está sujeto a RLS forzado (como alerta_conservacion de la
   0011). Lo de la familia no cambia: matu_app sigue sin UPDATE ni DELETE en reposicion y la política
   reposicion_pedido no se toca (decisión C de Jorge).

reposicion.cantidad_unidades solo tiene CHECK (cantidad_unidades > 0), sin tope: acepta envases ×
unidades_por_envase (hasta 100.000, el tope del stock) y no se cambia. backend/db/*.sql no se tocan.
downgrade() deja el esquema como en 0016.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


FIRMA = "quiebre_conservar(timestamptz, timestamptz, timestamptz)"

_CONTROLES = """
BEGIN
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
"""

# El cuerpo de quiebre_conservar de 0014, para el downgrade
CONSERVAR_0014 = (
    """
CREATE FUNCTION quiebre_conservar(limite_alertas timestamptz, limite_eventos timestamptz, ahora timestamptz)
    RETURNS TABLE (alertas integer, eventos integer, notificaciones integer)
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$"""
    + _CONTROLES
    + """    RETURN NEXT;
END
$$;
"""
)

CONSERVAR_0017 = (
    """
CREATE FUNCTION quiebre_conservar(limite_alertas timestamptz, limite_eventos timestamptz, ahora timestamptz)
    RETURNS TABLE (alertas integer, eventos integer, notificaciones integer, reposiciones integer)
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$"""
    + _CONTROLES
    + """    -- MATU-51 (decisión A de Jorge, 145): las compras declaradas a los 90 días de registrada_en. Las de
    -- pedido_matu siguen mientras exista el perfil
    DELETE FROM public.reposicion WHERE origen = 'declarada' AND registrada_en <= limite_alertas;
    GET DIAGNOSTICS reposiciones = ROW_COUNT;
    RETURN NEXT;
END
$$;
"""
)

PERMISOS = f"""
REVOKE ALL ON FUNCTION {FIRMA} FROM PUBLIC;
GRANT EXECUTE ON FUNCTION {FIRMA} TO matu_app;
"""

UPGRADE = (
    f"""
-- (b) La conservación ve y borra las reposiciones, solo con app.rol = 'operacion'
CREATE POLICY reposicion_conservacion ON reposicion FOR SELECT TO matu_owner USING (app_rol() = 'operacion');
CREATE POLICY reposicion_conservacion_borrar ON reposicion FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion');

-- (a) quiebre_conservar con el cuarto contador
DROP FUNCTION {FIRMA};
"""
    + CONSERVAR_0017
    + PERMISOS
)

DOWNGRADE = (
    f"""
DROP FUNCTION {FIRMA};
"""
    + CONSERVAR_0014
    + PERMISOS
    + """
DROP POLICY reposicion_conservacion_borrar ON reposicion;
DROP POLICY reposicion_conservacion ON reposicion;
"""
)


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

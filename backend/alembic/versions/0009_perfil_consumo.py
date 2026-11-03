"""MATU-36: perfil de consumo con versión, autor, segunda barrera por rol y conservación (RF-10, RF-11).

a) perfil_consumo.version integer NOT NULL DEFAULT 1 (decisión 41): el ETag "v<version>" del PATCH.

b) perfil_consumo.actualizado_por uuid, quién guardó la última vez (decisión 70, pedido del diseñador):
   el 412 del PATCH dice "Carmen cambió este insumo" en vez de "Otra persona", como la ficha de MATU-13.
   ON DELETE SET NULL: borrar una cuenta no borra el consumo de la familia.

c) CHECK de exactamente uno de producto_id y nombre_libre (antes admitía los dos) y
   char_length(nombre_libre) BETWEEN 1 AND 60 (decisión 38).

d) Segunda barrera por rol en RLS (decisión 68). perfil_familia (FOR ALL) se separa en:
   - perfil_leer (SELECT): el grupo del contexto, como antes, salvo con app.rol = 'operacion'. Leen
     los cuatro roles de la familia y el worker de MATU-37 (app.rol = 'sistema' con app.grupo_id).
   - perfil_crear, perfil_editar y perfil_borrar (INSERT, UPDATE, DELETE): el grupo del contexto y
     app_escribe_consumo(), una membresía activa de admin o cuidador de app.usuario_id en ese grupo.
     Un pagador o un observador con contexto válido no escribe ni con SQL directo.
   Operación no ve ninguna fila de perfil_consumo.

e) Conservación (decisión 67): consumo_conservar(limite, ahora), SECURITY DEFINER, dueño matu_owner,
   search_path fijo, EXECUTE solo para matu_app, que exige app.rol = 'operacion', igual que
   iam_conservar (0008). Borra los perfiles (activos o no) de las personas sin autorización no revocada
   para consumo y cuya última revocación es igual o anterior a limite. limite debe ser al menos 90 días
   anterior a ahora, y ahora no puede pasar de now() + 5 minutos: la función misma no deja borrar antes
   de los 90 días. Solo borra y devuelve un contador. Las reposiciones y alertas caen por ON DELETE
   CASCADE. matu_owner está sujeto a RLS (FORCE): perfil_conservacion y perfil_conservacion_borrar le
   dejan leer y borrar, solo a él y solo con app.rol = 'operacion'.

backend/db/*.sql no se tocan: son el esquema de 0001, igual que en 0004 a 0008.

downgrade() deja el esquema como en 0008. Las filas con nombre_libre y producto_id a la vez no
pueden existir con 0009, así que el CHECK de 0001 se restituye sin convertir nada. Se pierden version
y actualizado_por.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    # Igual que en 0001 a 0008: el SQL llega tal cual al driver, sin interpretar ':' ni '%'.
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


UPGRADE = """
-- (a) y (b) Versión y autor
ALTER TABLE perfil_consumo ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE perfil_consumo ADD CONSTRAINT perfil_consumo_version CHECK (version >= 1);
ALTER TABLE perfil_consumo ADD COLUMN actualizado_por uuid REFERENCES usuario(id) ON DELETE SET NULL;
COMMENT ON COLUMN perfil_consumo.version IS 'MATU-36: suma 1 en cada escritura; el ETag es "v<version>"';
COMMENT ON COLUMN perfil_consumo.actualizado_por IS 'MATU-36: quién guardó la última vez (decisión 70)';

-- (c) Exactamente uno de producto_id y nombre_libre, y nombre_libre de 1 a 60 caracteres
ALTER TABLE perfil_consumo DROP CONSTRAINT perfil_consumo_producto;
ALTER TABLE perfil_consumo ADD CONSTRAINT perfil_consumo_producto
    CHECK ((producto_id IS NULL) <> (nombre_libre IS NULL));
ALTER TABLE perfil_consumo ADD CONSTRAINT perfil_consumo_nombre_libre CHECK (
    nombre_libre IS NULL OR char_length(nombre_libre) BETWEEN 1 AND 60);

-- (d) Lectura para el grupo, escritura solo para admin y cuidador
CREATE FUNCTION app_escribe_consumo() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT EXISTS (SELECT 1 FROM membresia m
                  WHERE m.grupo_id = app_grupo() AND m.usuario_id = app_usuario()
                    AND m.estado = 'activa' AND m.rol IN ('admin', 'cuidador')) $$;

DROP POLICY perfil_familia ON perfil_consumo;
CREATE POLICY perfil_leer ON perfil_consumo FOR SELECT
    USING (grupo_id = app_grupo() AND app_rol() IS DISTINCT FROM 'operacion');
CREATE POLICY perfil_crear ON perfil_consumo FOR INSERT
    WITH CHECK (grupo_id = app_grupo() AND app_escribe_consumo());
CREATE POLICY perfil_editar ON perfil_consumo FOR UPDATE
    USING (grupo_id = app_grupo() AND app_escribe_consumo())
    WITH CHECK (grupo_id = app_grupo() AND app_escribe_consumo());
CREATE POLICY perfil_borrar ON perfil_consumo FOR DELETE
    USING (grupo_id = app_grupo() AND app_escribe_consumo());

-- (e) Conservación
CREATE POLICY perfil_conservacion ON perfil_consumo FOR SELECT TO matu_owner USING (app_rol() = 'operacion');
CREATE POLICY perfil_conservacion_borrar ON perfil_consumo FOR DELETE TO matu_owner
    USING (app_rol() = 'operacion');

CREATE FUNCTION consumo_conservar(limite timestamptz, ahora timestamptz) RETURNS integer
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    n integer := 0;
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'consumo_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '90 days' THEN
        RAISE EXCEPTION 'el consumo se conserva 90 días' USING ERRCODE = 'invalid_parameter_value';
    END IF;

    DELETE FROM public.perfil_consumo p
     WHERE NOT EXISTS (
               SELECT 1 FROM public.consentimiento c
                WHERE c.persona_cuidada_id = p.persona_cuidada_id AND c.finalidad = 'consumo'
                  AND c.revocado_en IS NULL)
       AND (SELECT max(c.revocado_en) FROM public.consentimiento c
             WHERE c.persona_cuidada_id = p.persona_cuidada_id AND c.finalidad = 'consumo') <= limite;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END
$$;
REVOKE ALL ON FUNCTION consumo_conservar(timestamptz, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION consumo_conservar(timestamptz, timestamptz) TO matu_app;
"""

DOWNGRADE = """
DROP FUNCTION consumo_conservar(timestamptz, timestamptz);
DROP POLICY perfil_conservacion_borrar ON perfil_consumo;
DROP POLICY perfil_conservacion ON perfil_consumo;

DROP POLICY perfil_borrar ON perfil_consumo;
DROP POLICY perfil_editar ON perfil_consumo;
DROP POLICY perfil_crear ON perfil_consumo;
DROP POLICY perfil_leer ON perfil_consumo;
CREATE POLICY perfil_familia ON perfil_consumo FOR ALL USING (grupo_id = app_grupo());
DROP FUNCTION app_escribe_consumo();

ALTER TABLE perfil_consumo DROP CONSTRAINT perfil_consumo_nombre_libre;
ALTER TABLE perfil_consumo DROP CONSTRAINT perfil_consumo_producto;
ALTER TABLE perfil_consumo ADD CONSTRAINT perfil_consumo_producto
    CHECK (producto_id IS NOT NULL OR nombre_libre IS NOT NULL);

ALTER TABLE perfil_consumo DROP COLUMN actualizado_por;
ALTER TABLE perfil_consumo DROP CONSTRAINT perfil_consumo_version;
ALTER TABLE perfil_consumo DROP COLUMN version;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

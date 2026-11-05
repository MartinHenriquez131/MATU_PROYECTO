"""MATU-50: las seis secciones complementarias de la ficha (ADR-028, RF-03).

Contrato: docs/api/propuestos/ficha-ampliada.openapi.yaml (MATU-49), nota de esquema de
docs/api/README.md, sección "MATU-49 (propuesto)". No hay tablas nuevas.

a) plan_seccion.tipo suma quien_es, comunicacion y remedios. No se quita ningún valor: horarios y
   actividades quedan en el CHECK aunque la API ya no los escriba.
b) acceso_relevo.secciones_permitidas suma los mismos tres, o compartir comunicacion, quien_es o
   remedios fallaría en la base.
c) plan_seccion.creado_en (timestamptz NOT NULL), cuándo nació la fila. Quitar una sección borra la
   fila; volver a agregarla crea otra, con creado_en nuevo. Un trigger lo deja fijo en los UPDATE: editar
   no cambia cuándo nació. Las filas que ya existen toman el instante de la migración (ADD COLUMN …
   DEFAULT now() las llena sin pasar por RLS; matu_owner no ve las filas de plan_seccion, que no tiene
   política de operación, así que no se pueden copiar desde actualizado_en con un UPDATE). No cambia lo
   que ve ningún relevo: la regla de (d) no se aplica a los tres campos base, y antes de esta migración
   la API no dejaba escribir ni compartir secciones complementarias.
d) seccion_relevo: el relevo ve una sección complementaria solo si está en secciones_permitidas y nació
   antes de su acceso o en el mismo instante (plan_seccion.creado_en <= acceso_relevo.creado_en). Los tres
   campos base no cambian: se ven aunque se hayan escrito después (decisión de Jorge del 03-11, lectura
   estricta de "un acceso no ve secciones agregadas después de crearlo").
e) auditoria.detalle admite además 'seccion' (el tipo de una sección complementaria, en plan.editar y
   plan.quitar_seccion) y 'secciones' (la lista de tipos mostrados al relevo, en relevo.abrir). Solo los
   seis tipos, nunca texto.
f) seccion_familia (FOR ALL con app_puede_ver_plan()) se separa por operación, como perfil_consumo en la
   0009 (decisión 102, aprobada por Jorge el 03-11): seccion_leer (FOR SELECT) para quien puede ver el
   plan, también el pagador con puede_ver_plan; seccion_crear, seccion_editar y seccion_borrar solo con
   app_escribe_plan(), una membresía activa de admin o cuidador en el grupo del contexto. Así un pagador
   con puede_ver_plan no escribe ni borra secciones ni con SQL directo, igual que en la API.
g) plan_familia (FOR ALL con app_puede_ver_plan()) se separa igual (decisión 103, aprobada por Jorge el
   03-11): plan_leer (FOR SELECT) para quien puede ver el plan; plan_crear (INSERT) y plan_editar (UPDATE)
   con app_escribe_plan(). Ninguna política de DELETE, y REVOKE DELETE ON plan_cuidado FROM matu_app:
   ninguna ruta borra un plan, y borrarlo arrastraría por ON DELETE CASCADE sus secciones y sus accesos
   de relevo sin pasar por las políticas de esas tablas. Borrar un plan es de la historia de borrado.

downgrade() vuelve al esquema de la 0012 (en estas tablas, el mismo de la 0011):
- Si quedan filas de plan_seccion con los tipos nuevos, o accesos que los comparten, se detiene con un
  error y no borra nada (no se pierden datos sin aviso). Hay que quitarlas antes a mano.
- La auditoría no se borra ni se cambia (es de solo inserción y se conserva 3 años). Si hay filas con
  los detalles nuevos, el CHECK anterior vuelve como NOT VALID: rige para las filas nuevas y deja las
  existentes como están. En una base sin esas filas vuelve validado, igual que en la 0011.
- matu_owner está sujeto a RLS forzado y no ve esas filas: un SELECT no las encontraría. Por eso no se
  buscan; se intenta agregar el CHECK anterior, cuya validación sí revisa todas las filas, y se captura
  check_violation.

down_revision "0012": se escribió sobre la 0011 y, al fusionar con MATU-57 (PR #39, que agrega la 0012
sobre la 0011), se encadenó después de la 0012 sin cambiar el SQL, que no depende de ella.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


_TIPOS_0011 = (
    "'rutina', 'horarios', 'manejo_situaciones', 'preferencias', 'actividades', 'red_apoyo', 'alimentacion',"
    " 'movilidad'"
)
_TIPOS_NUEVOS = "'quien_es', 'comunicacion', 'remedios'"
_COMPLEMENTARIAS = "'quien_es', 'preferencias', 'alimentacion', 'movilidad', 'comunicacion', 'remedios'"
_COMPLEMENTARIAS_JSON = '["quien_es", "preferencias", "alimentacion", "movilidad", "comunicacion", "remedios"]'

_DETALLE_0008 = """
    detalle IS NULL OR (
        jsonb_typeof(detalle) = 'object'
        AND (detalle - 'sesiones_revocadas') = '{}'::jsonb
        AND (NOT detalle ? 'sesiones_revocadas'
             OR (jsonb_typeof(detalle -> 'sesiones_revocadas') = 'number'
                 AND (detalle ->> 'sesiones_revocadas') ~ '^[0-9]{1,6}$')))"""

# Escribe en una sección: el plan es del grupo del contexto y quien escribe es admin o cuidador activo
_SECCION_ESCRIBE = (
    "EXISTS (SELECT 1 FROM plan_cuidado p WHERE p.id = plan_seccion.plan_id AND p.grupo_id = app_grupo())"
    " AND (SELECT app_escribe_plan())"
)

UPGRADE = f"""
-- (a) y (b) Los tres tipos nuevos de ADR-028
ALTER TABLE plan_seccion DROP CONSTRAINT plan_seccion_tipo_check;
ALTER TABLE plan_seccion ADD CONSTRAINT plan_seccion_tipo_check CHECK (tipo IN ({_TIPOS_0011}, {_TIPOS_NUEVOS}));

ALTER TABLE acceso_relevo DROP CONSTRAINT acceso_relevo_secciones_permitidas_check;
ALTER TABLE acceso_relevo ADD CONSTRAINT acceso_relevo_secciones_permitidas_check CHECK (
    cardinality(secciones_permitidas) > 0 AND
    secciones_permitidas <@ ARRAY[{_TIPOS_0011}, {_TIPOS_NUEVOS}]);

-- (c) Cuándo nació la fila. Las existentes toman el instante de la migración (ver el docstring)
ALTER TABLE plan_seccion ADD COLUMN creado_en timestamptz NOT NULL DEFAULT now();
COMMENT ON COLUMN plan_seccion.creado_en IS
    'MATU-50: cuándo nació la fila. Fijo en los UPDATE (trigger plan_seccion_creado_fijo). Un acceso de relevo'
    ' no ve una sección complementaria nacida después de él (política seccion_relevo)';

CREATE FUNCTION plan_seccion_creado_fijo() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.creado_en := OLD.creado_en;
    RETURN NEW;
END $$;
CREATE TRIGGER plan_seccion_creado_fijo BEFORE UPDATE ON plan_seccion
    FOR EACH ROW EXECUTE FUNCTION plan_seccion_creado_fijo();

-- (d) El relevo no ve una sección complementaria agregada después de su acceso
DROP POLICY seccion_relevo ON plan_seccion;
CREATE POLICY seccion_relevo ON plan_seccion FOR SELECT USING (
    app_rol() = 'relevo' AND EXISTS (
        SELECT 1 FROM acceso_relevo a WHERE a.id = app_acceso_relevo()
          AND a.plan_id = plan_seccion.plan_id AND plan_seccion.tipo = ANY (a.secciones_permitidas)
          AND (plan_seccion.tipo IN ('rutina', 'manejo_situaciones', 'red_apoyo')
               OR plan_seccion.creado_en <= a.creado_en)));

-- (e) Detalle de la auditoría: el tipo de una sección y la lista de tipos mostrados, nunca texto
ALTER TABLE auditoria DROP CONSTRAINT auditoria_detalle_acotado;
ALTER TABLE auditoria ADD CONSTRAINT auditoria_detalle_acotado CHECK (
    detalle IS NULL OR (
        jsonb_typeof(detalle) = 'object'
        AND (detalle - 'sesiones_revocadas' - 'seccion' - 'secciones') = '{{}}'::jsonb
        AND (NOT detalle ? 'sesiones_revocadas'
             OR (jsonb_typeof(detalle -> 'sesiones_revocadas') = 'number'
                 AND (detalle ->> 'sesiones_revocadas') ~ '^[0-9]{{1,6}}$'))
        AND (NOT detalle ? 'seccion'
             OR (jsonb_typeof(detalle -> 'seccion') = 'string'
                 AND (detalle ->> 'seccion') IN ({_COMPLEMENTARIAS})))
        AND (NOT detalle ? 'secciones'
             OR (jsonb_typeof(detalle -> 'secciones') = 'array'
                 AND jsonb_array_length(detalle -> 'secciones') <= 6
                 AND (detalle -> 'secciones') <@ '{_COMPLEMENTARIAS_JSON}'::jsonb))));
COMMENT ON COLUMN auditoria.detalle IS
    'MATU-38: sesiones_revocadas (entero). MATU-50: seccion (un tipo) y secciones (lista de tipos) de las'
    ' secciones complementarias. Nunca texto libre, el email ni su huella (decisión 64)';

-- (f) Leer y escribir las secciones por separado (decisión 102): escriben solo admin y cuidador
CREATE FUNCTION app_escribe_plan() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT EXISTS (SELECT 1 FROM membresia m
                  WHERE m.grupo_id = app_grupo() AND m.usuario_id = app_usuario()
                    AND m.estado = 'activa' AND m.rol IN ('admin', 'cuidador')) $$;

DROP POLICY seccion_familia ON plan_seccion;
CREATE POLICY seccion_leer ON plan_seccion FOR SELECT USING (EXISTS (
    SELECT 1 FROM plan_cuidado p WHERE p.id = plan_seccion.plan_id
      AND p.grupo_id = app_grupo() AND (SELECT app_puede_ver_plan())));
CREATE POLICY seccion_crear ON plan_seccion FOR INSERT WITH CHECK ({_SECCION_ESCRIBE});
CREATE POLICY seccion_editar ON plan_seccion FOR UPDATE USING ({_SECCION_ESCRIBE}) WITH CHECK ({_SECCION_ESCRIBE});
CREATE POLICY seccion_borrar ON plan_seccion FOR DELETE USING ({_SECCION_ESCRIBE});

-- (g) El plan: leer quien lo ve, crear y editar admin y cuidador, borrar nadie (decisión 103)
DROP POLICY plan_familia ON plan_cuidado;
CREATE POLICY plan_leer ON plan_cuidado FOR SELECT
    USING (grupo_id = app_grupo() AND (SELECT app_puede_ver_plan()));
CREATE POLICY plan_crear ON plan_cuidado FOR INSERT
    WITH CHECK (grupo_id = app_grupo() AND (SELECT app_escribe_plan()));
CREATE POLICY plan_editar ON plan_cuidado FOR UPDATE
    USING (grupo_id = app_grupo() AND (SELECT app_escribe_plan()))
    WITH CHECK (grupo_id = app_grupo() AND (SELECT app_escribe_plan()));
REVOKE DELETE ON plan_cuidado FROM matu_app;
"""

DOWNGRADE = f"""
-- (g) La política y el permiso de la 0001
GRANT DELETE ON plan_cuidado TO matu_app;
DROP POLICY plan_editar ON plan_cuidado;
DROP POLICY plan_crear ON plan_cuidado;
DROP POLICY plan_leer ON plan_cuidado;
CREATE POLICY plan_familia ON plan_cuidado FOR ALL
    USING (grupo_id = app_grupo() AND (SELECT app_puede_ver_plan()));

-- (f) La política de la 0001: FOR ALL para quien puede ver el plan
DROP POLICY seccion_borrar ON plan_seccion;
DROP POLICY seccion_editar ON plan_seccion;
DROP POLICY seccion_crear ON plan_seccion;
DROP POLICY seccion_leer ON plan_seccion;
DROP FUNCTION app_escribe_plan();
CREATE POLICY seccion_familia ON plan_seccion FOR ALL USING (EXISTS (
    SELECT 1 FROM plan_cuidado p WHERE p.id = plan_seccion.plan_id
      AND p.grupo_id = app_grupo() AND (SELECT app_puede_ver_plan())));

-- Primero los CHECK de los tipos: si quedan filas con los tipos nuevos, se detiene sin borrar nada.
-- La validación revisa todas las filas aunque matu_owner no las vea por RLS
DO $$
BEGIN
    ALTER TABLE plan_seccion DROP CONSTRAINT plan_seccion_tipo_check;
    ALTER TABLE plan_seccion ADD CONSTRAINT plan_seccion_tipo_check CHECK (tipo IN ({_TIPOS_0011}));
    ALTER TABLE acceso_relevo DROP CONSTRAINT acceso_relevo_secciones_permitidas_check;
    ALTER TABLE acceso_relevo ADD CONSTRAINT acceso_relevo_secciones_permitidas_check CHECK (
        cardinality(secciones_permitidas) > 0 AND
        secciones_permitidas <@ ARRAY[{_TIPOS_0011}]);
EXCEPTION WHEN check_violation THEN
    RAISE EXCEPTION 'MATU-50: hay secciones quien_es, comunicacion o remedios, o accesos que las comparten.'
        ' Quítalas antes de bajar de la 0013: el downgrade no borra datos';
END $$;

-- La auditoría no se toca: con detalles de secciones, el CHECK de la 0008 vuelve NOT VALID
ALTER TABLE auditoria DROP CONSTRAINT auditoria_detalle_acotado;
DO $$
BEGIN
    BEGIN
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_detalle_acotado CHECK ({_DETALLE_0008});
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'MATU-50: la auditoría tiene detalles de secciones; el CHECK de la 0008 vuelve NOT VALID';
        ALTER TABLE auditoria ADD CONSTRAINT auditoria_detalle_acotado CHECK ({_DETALLE_0008}) NOT VALID;
    END;
END $$;
COMMENT ON COLUMN auditoria.detalle IS
    'MATU-38: solo sesiones_revocadas (entero). Nunca texto libre, el email ni su huella (decisión 64)';

DROP POLICY seccion_relevo ON plan_seccion;
CREATE POLICY seccion_relevo  ON plan_seccion FOR SELECT USING (
    app_rol() = 'relevo' AND EXISTS (
        SELECT 1 FROM acceso_relevo a WHERE a.id = app_acceso_relevo()
          AND a.plan_id = plan_seccion.plan_id AND plan_seccion.tipo = ANY (a.secciones_permitidas)));

DROP TRIGGER plan_seccion_creado_fijo ON plan_seccion;
DROP FUNCTION plan_seccion_creado_fijo();
ALTER TABLE plan_seccion DROP COLUMN creado_en;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

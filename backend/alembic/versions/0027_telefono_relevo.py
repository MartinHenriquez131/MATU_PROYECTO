"""MATU-46: el teléfono del relevo se borra a los 30 días, y al tiro si se borra a la persona (decisiones 25 y 26).

Cadena: 0026 (MATU-42) -> 0027. Revisión previa del analista normativo (docs/legal/revision-previa-matu-46.md,
sección 2) y decisiones 332 en adelante de docs/api/README.md, sección «MATU-46». Con D-46-3 a) y D-46-4 c) de Jorge.
Todo el SQL de políticas, permisos, triggers y CHECK va aquí; backend/db/*.sql no se toca.

Upgrade:

a) acceso_relevo.otorgado_a_telefono pierde el NOT NULL. Entra telefono_borrado_en (timestamptz), con el CHECK
   acceso_relevo_telefono_borrado: el teléfono está vacío si y solo si hay un instante de borrado (D-46-4 c).
b) Trigger acceso_relevo_telefono (BEFORE UPDATE, para todos los roles, también el dueño y el superusuario): un
   teléfono solo se vacía, una vez. Nunca cambia por otro ni vuelve, y telefono_borrado_en no cambia una vez fijado.
   Los RAISE no llevan el valor.
c) Las políticas de la tarea, TO matu_owner y con app.rol = 'operacion', como clave_destruccion de la 0016:
   acceso_conservacion_leer (SELECT) y acceso_conservacion (UPDATE, la fila nueva queda sin teléfono). Nada nuevo
   para matu_app en lectura (C10).
d) relevo_conservar(limite, ahora), SECURITY DEFINER, dueño matu_owner, search_path fijo, EXECUTE solo para
   matu_scheduler (C9): exige app.rol = 'operacion', un ahora que no esté en el futuro y un límite de al menos
   30 días. Vacía solo el teléfono (C11) de los accesos cuyo fin, LEAST(expira_en, revocado_en), es anterior o igual
   al límite: un acceso bloqueado o en pausa cuenta desde su vencimiento (C1 y C2). Es idempotente (C12) y devuelve
   solo un contador (C4).
e) matu_app recibe UPDATE de otorgado_a_telefono y telefono_borrado_en (D-46-3 a): el borrado de la persona vacía el
   teléfono en su misma transacción. RLS lo limita al admin y al cuidador (acceso_familia_cortar, 0020), y el
   trigger b) solo deja vaciarlo.

downgrade() deja el esquema como la 0026. Se detiene con un mensaje claro si algún teléfono ya se borró, como la
0018: nunca inventa un teléfono. SET NOT NULL valida todas las filas sin pasar por RLS.

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


UPGRADE = """
-- (a) El teléfono puede quedar vacío, y entonces se sabe cuándo se vació
ALTER TABLE acceso_relevo ALTER COLUMN otorgado_a_telefono DROP NOT NULL;
ALTER TABLE acceso_relevo ADD COLUMN telefono_borrado_en timestamptz;
ALTER TABLE acceso_relevo ADD CONSTRAINT acceso_relevo_telefono_borrado
    CHECK ((otorgado_a_telefono IS NULL) = (telefono_borrado_en IS NOT NULL));
COMMENT ON COLUMN acceso_relevo.telefono_borrado_en IS
    'Cuándo se borró el teléfono del relevo: 30 días después del fin del acceso, o al borrar a la persona (MATU-46)';

-- (b) Un teléfono solo se vacía, una vez, y nunca cambia ni vuelve. Vale para todos los roles
CREATE FUNCTION acceso_relevo_telefono_solo_se_borra() RETURNS trigger LANGUAGE plpgsql AS
$$
BEGIN
    IF NEW.otorgado_a_telefono IS DISTINCT FROM OLD.otorgado_a_telefono AND NEW.otorgado_a_telefono IS NOT NULL THEN
        RAISE EXCEPTION 'el teléfono del relevo solo se borra' USING ERRCODE = 'check_violation';
    END IF;
    IF OLD.telefono_borrado_en IS NOT NULL AND NEW.telefono_borrado_en IS DISTINCT FROM OLD.telefono_borrado_en THEN
        RAISE EXCEPTION 'el borrado del teléfono no cambia' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER acceso_relevo_telefono BEFORE UPDATE ON acceso_relevo
    FOR EACH ROW EXECUTE FUNCTION acceso_relevo_telefono_solo_se_borra();

-- (c) La tarea ve y vacía como matu_owner, solo con app.rol = 'operacion'
CREATE POLICY acceso_conservacion_leer ON acceso_relevo FOR SELECT TO matu_owner USING (app_rol() = 'operacion');
CREATE POLICY acceso_conservacion ON acceso_relevo FOR UPDATE TO matu_owner
    USING (app_rol() = 'operacion') WITH CHECK (app_rol() = 'operacion' AND otorgado_a_telefono IS NULL);

-- (d) El teléfono se borra 30 días después de que el acceso vence o se corta, lo que ocurra primero
CREATE FUNCTION relevo_conservar(limite timestamptz, ahora timestamptz) RETURNS integer
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS
$$
DECLARE
    borrados integer;
BEGIN
    IF public.app_rol() IS DISTINCT FROM 'operacion' THEN
        RAISE EXCEPTION 'relevo_conservar exige app.rol = operacion' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF ahora IS NULL OR ahora > now() + interval '5 minutes' THEN
        RAISE EXCEPTION 'ahora no puede estar en el futuro' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF limite IS NULL OR limite > ahora - interval '30 days' THEN
        RAISE EXCEPTION 'el teléfono del relevo se conserva 30 días' USING ERRCODE = 'invalid_parameter_value';
    END IF;
    -- LEAST ignora el nulo: sin corte, cuenta el vencimiento. Un acceso bloqueado o en pausa, también
    UPDATE public.acceso_relevo a SET otorgado_a_telefono = NULL, telefono_borrado_en = ahora
     WHERE a.otorgado_a_telefono IS NOT NULL AND LEAST(a.expira_en, a.revocado_en) <= limite;
    GET DIAGNOSTICS borrados = ROW_COUNT;
    RETURN borrados;
END
$$;
REVOKE ALL ON FUNCTION relevo_conservar(timestamptz, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION relevo_conservar(timestamptz, timestamptz) TO matu_scheduler;

-- (e) El borrado de la persona vacía el teléfono al tiro (D-46-3 a). El trigger (b) solo deja vaciarlo
GRANT UPDATE (otorgado_a_telefono, telefono_borrado_en) ON acceso_relevo TO matu_app;
"""

DOWNGRADE = """
-- Primero, lo que puede fallar: con un teléfono borrado no se vuelve al NOT NULL, y nada se inventa
DO $$ BEGIN
    BEGIN
        ALTER TABLE acceso_relevo ALTER COLUMN otorgado_a_telefono SET NOT NULL;
    EXCEPTION WHEN not_null_violation THEN
        RAISE EXCEPTION 'la 0027 no baja: hay accesos de relevo con el teléfono ya borrado, y la 0026 lo exige.'
            ' MATU nunca inventa un teléfono' USING ERRCODE = 'not_null_violation';
    END;
END $$;

-- (e) y (d)
REVOKE UPDATE (otorgado_a_telefono, telefono_borrado_en) ON acceso_relevo FROM matu_app;
DROP FUNCTION relevo_conservar(timestamptz, timestamptz);

-- (c)
DROP POLICY acceso_conservacion ON acceso_relevo;
DROP POLICY acceso_conservacion_leer ON acceso_relevo;

-- (b)
DROP TRIGGER acceso_relevo_telefono ON acceso_relevo;
DROP FUNCTION acceso_relevo_telefono_solo_se_borra();

-- (a)
ALTER TABLE acceso_relevo DROP CONSTRAINT acceso_relevo_telefono_borrado;
ALTER TABLE acceso_relevo DROP COLUMN telefono_borrado_en;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

"""MATU-11: una clave de datos destruida no resucita.

El borrado criptográfico (modelo de datos, sección 6) es dejar dek_cifrada_con_kek en NULL y
destruida_en con valor, en la misma sentencia (CHECK clave_datos_destruccion). Esta migración cierra
los dos caminos por los que matu_app podría devolverle una clave a la persona:

- Borrar la fila destruida: sin fila, la persona quedaría en "todavía no existe" y la escritura
  siguiente crearía una DEK nueva. matu_app pierde DELETE sobre clave_datos.
- Actualizar la fila destruida para ponerle una DEK otra vez, o quitarle destruida_en. Un trigger
  BEFORE UPDATE deja la fila destruida inmutable: no vuelve a tener DEK, no cambia de persona ni
  de grupo, y la marca de destrucción no se mueve.

Quedan intactos el paso de vigente a destruida (lo prueba test_borrado_criptografico_es_explicito)
y el UNIQUE de persona_cuidada_id, que impide insertar otra clave para la misma persona.

Los scripts de backend/db no se tocan: son la migración 0001, como en la 0002. Todo va aquí con SQL.

downgrade() deja el esquema como en 0002. Lo verifica tests/test_migraciones.py.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    # Igual que en 0001 y 0002: el SQL llega tal cual al driver, sin interpretar ':' ni '%'.
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


UPGRADE = """
-- La clave de datos no se borra: se destruye (dek NULL + destruida_en), y la fila se queda
REVOKE DELETE ON clave_datos FROM matu_app;

-- Una clave destruida no vuelve a tener DEK: la fila queda fija. Aplica a todo rol, también al dueño.
CREATE FUNCTION clave_datos_destruida_fija() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN
    IF OLD.destruida_en IS NOT NULL AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'la clave de datos fue destruida: no vuelve a tener clave'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER clave_datos_destruida_fija BEFORE UPDATE ON clave_datos
    FOR EACH ROW EXECUTE FUNCTION clave_datos_destruida_fija();
"""

DOWNGRADE = """
DROP TRIGGER clave_datos_destruida_fija ON clave_datos;
DROP FUNCTION clave_datos_destruida_fija();
GRANT DELETE ON clave_datos TO matu_app;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

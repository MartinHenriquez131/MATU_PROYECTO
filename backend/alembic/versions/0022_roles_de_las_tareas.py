"""MATU-74 (hallazgos H2 a H5 de Martín, 09-11): las tareas con sus propios roles y operación sin los avisos.

Cadena: 0021 (MATU-75) -> 0022. down_revision = "0021".

a) C4 · notificacion_operacion (db/02_rls.sql) dejaba a matu_app con app.rol = 'operacion' leer los avisos de
   todos los grupos, y el registro de tratamientos dice «operación nunca». Se borra. quiebre_conservar (0011,
   0014 y 0017) es SECURITY DEFINER como matu_owner, y matu_owner está sujeto a RLS (FORCE): veía las
   notificaciones a borrar gracias a esa política, que era PUBLIC. La reemplaza notificacion_conservacion,
   FOR SELECT TO matu_owner con app.rol = 'operacion', igual que alerta_conservacion (0011). Con
   notificacion_conservacion_borrar (DELETE, 0011) la función sigue borrando lo que cumplió 90 días.

b) H2 / C13 · las funciones de las tareas pasan de matu_app a los roles de 00_roles.sql, que existen desde la
   0001 con LOGIN, NOSUPERUSER y NOBYPASSRLS:
   - matu_scheduler ejecuta plan_destruir_claves (0016), consumo_conservar (0009), iam_conservar (0008) y
     quiebre_conservar. Ya enumeraba los grupos activos (SELECT (id, estado) y la política grupo_scheduler).
   - matu_publisher ejecuta outbox_tomar, outbox_publicado, outbox_reintentar y outbox_posponer (0014).
   - A matu_app se le revoca EXECUTE de las ocho: ninguna ruta de la API ni el borrado de MATU-72 las llama.
   El cuerpo de las funciones no cambia. La llamada sigue fijando app.rol = 'operacion': lo exigen el chequeo
   de cada función y las políticas TO matu_owner con que la función ve y borra (alerta_conservacion,
   notificacion_conservacion y las de 0008, 0009, 0016 y 0017). Quién puede llamar lo decide el GRANT, que
   ahora es solo del rol de la tarea; session_user no se usa, porque no agrega nada que el GRANT no dé y
   rompería las pruebas, que entran como superusuario con SET ROLE.

c) Un solo camino al outbox: matu_publisher pierde SELECT y UPDATE sobre evento_outbox y SELECT e INSERT sobre
   evento_consumido (03_permisos.sql). Las funciones son SECURITY DEFINER y no los necesitan, y evento_consumido
   lo escribe el consumidor de avisos, que trabaja como matu_app con app.rol = 'sistema'.

Lo que no cambia: los atributos de los roles (los fija 00_roles.sql, y matu_owner no puede cambiarlos), sus
membresías, ALTER DEFAULT PRIVILEGES (solo nombra a matu_app), el USAGE sobre public de los dos roles y lo que
matu_scheduler tenía sobre grupo_familiar. backend/db/*.sql no se tocan.

downgrade() deja el esquema y los permisos como en 0021. Lo verifica tests/test_migraciones.py.

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCIONES_SCHEDULER = (
    "plan_destruir_claves(timestamptz, timestamptz)",
    "consumo_conservar(timestamptz, timestamptz)",
    "iam_conservar(timestamptz, timestamptz, timestamptz)",
    "quiebre_conservar(timestamptz, timestamptz, timestamptz)",
)
FUNCIONES_PUBLISHER = (
    "outbox_tomar(integer, timestamptz, uuid)",
    "outbox_publicado(bigint, timestamptz)",
    "outbox_reintentar(bigint, timestamptz, timestamptz)",
    "outbox_posponer(bigint, timestamptz, timestamptz)",
)


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


def _pasar(funciones: Sequence[str], de: str, a: str) -> str:
    return "\n".join(
        f"REVOKE EXECUTE ON FUNCTION {f} FROM {de};\nGRANT EXECUTE ON FUNCTION {f} TO {a};" for f in funciones
    )


UPGRADE = f"""
-- (a) C4: operación ya no lee los avisos; la conservación sigue viéndolos como matu_owner
DROP POLICY notificacion_operacion ON notificacion;
CREATE POLICY notificacion_conservacion ON notificacion FOR SELECT TO matu_owner
    USING (app_rol() = 'operacion');

-- (b) Las funciones de las tareas, solo para el rol de cada tarea
{_pasar(FUNCIONES_SCHEDULER, "matu_app", "matu_scheduler")}
{_pasar(FUNCIONES_PUBLISHER, "matu_app", "matu_publisher")}

-- (c) Un solo camino al outbox: las funciones
REVOKE ALL ON evento_outbox FROM matu_publisher;
REVOKE ALL ON evento_consumido FROM matu_publisher;
"""

DOWNGRADE = f"""
GRANT SELECT, UPDATE ON evento_outbox TO matu_publisher;
GRANT SELECT, INSERT ON evento_consumido TO matu_publisher;

{_pasar(FUNCIONES_PUBLISHER, "matu_publisher", "matu_app")}
{_pasar(FUNCIONES_SCHEDULER, "matu_scheduler", "matu_app")}

DROP POLICY notificacion_conservacion ON notificacion;
CREATE POLICY notificacion_operacion ON notificacion FOR SELECT USING (app_rol() = 'operacion');
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

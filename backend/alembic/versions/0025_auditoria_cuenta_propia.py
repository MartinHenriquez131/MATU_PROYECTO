"""MATU-55: «Dónde entraste», la persona lee la auditoría de su propia cuenta (RF-37, Ley 21.719).

Cadena: 0024 (MATU-62) -> 0025. Decisiones 257, 258, 266, 267 y 271 de docs/api/README.md, sección MATU-55.

Upgrade, en este orden:

1. Política auditoria_cuenta_propia (FOR SELECT, decisión 257). Se suma con OR a auditoria_familia y
   auditoria_aperturas_relevo. Solo filas sin grupo, y de dos formas:
   - las que la persona hizo con su sesión: actor_tipo = 'usuario' y actor_ref = app_usuario(). actor_tipo se exige
     porque actor_ref es polimórfico (con el relevo es el id del acceso);
   - el pedido de un código de recuperación, que va con actor sistema y la persona como entidad. Se nombra la acción:
     cuenta.recuperar_verificar_fallido también va con actor sistema y la misma entidad, y no se muestra (D1).
   Sin app.usuario_id (relevo, sistema u operación) no se ve ninguna fila. sesion.inicio_fallido, sin actor ni
   entidad, no la ve nadie.
2. Índice auditoria_cuenta_ix (actor_ref, ocurrido_en DESC) WHERE grupo_id IS NULL, para la primera rama (decisión
   267). La segunda usa auditoria_entidad_ix, que ya existe.
3. CHECK auditoria_cuenta_acotada (decisión 258): una fila sin grupo es siempre de una acción de la cuenta
   (ACCIONES_DE_CUENTA de app/shared/auditoria.py, las 13 de MATU-38 y MATU-57 más avisos.preferencia). Así la política
   del punto 1 nunca abre una fila de la ficha o del consumo escrita sin grupo por error. NOT VALID y después VALIDATE:
   una fila que lo rompa hace fallar la migración con el nombre del CHECK. tests/test_migraciones.py verifica que la
   lista es la misma de ACCIONES_DE_CUENTA.
4. DROP COLUMN ip (decisión 266, D7): nunca se escribió (decisión 27 de MATU-09) y ningún código, vista ni función la
   usa. COMMENT ON TABLE auditoria lo deja dicho.

Sin columnas nuevas, sin tocar auditoria_detalle_acotado ni los permisos: matu_app ya lee auditoria y no la actualiza
ni la borra.

downgrade() en orden inverso: la columna ip vuelve como inet nula al final de la tabla (nunca tuvo datos), y se borran
el CHECK, el índice y la política. backend/db/*.sql no se tocan.

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ejecutar(sql: str) -> None:
    contexto = op.get_context()
    if contexto.as_sql:
        contexto.impl.static_output(sql)
        return
    with op.get_bind().connection.cursor() as cursor:
        cursor.execute(sql)


# Las acciones de la cuenta (ACCIONES_DE_CUENTA, decisión 258). Escritas aquí y no importadas: una migración no cambia
# cuando cambia el código. tests/test_migraciones.py verifica que es la misma lista
ACCIONES_DE_CUENTA_0025 = (
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
)
_LISTA = ", ".join(f"'{accion}'" for accion in ACCIONES_DE_CUENTA_0025)

UPGRADE = f"""
-- 1. La persona lee su propia auditoría de la cuenta (decisión 257)
CREATE POLICY auditoria_cuenta_propia ON auditoria FOR SELECT USING (
    grupo_id IS NULL AND (
        (actor_tipo = 'usuario' AND actor_ref = app_usuario())
        OR (actor_tipo = 'sistema' AND accion = 'cuenta.recuperar_solicitar'
            AND entidad = 'usuario' AND entidad_id = app_usuario())));

-- 2. El índice de la primera rama (decisión 267)
CREATE INDEX auditoria_cuenta_ix ON auditoria (actor_ref, ocurrido_en DESC) WHERE grupo_id IS NULL;

-- 3. Una fila sin grupo es siempre de la cuenta (decisión 258)
ALTER TABLE auditoria ADD CONSTRAINT auditoria_cuenta_acotada
    CHECK (grupo_id IS NOT NULL OR accion IN ({_LISTA})) NOT VALID;
ALTER TABLE auditoria VALIDATE CONSTRAINT auditoria_cuenta_acotada;

-- 4. La IP no se guarda (decisión 266, D7)
ALTER TABLE auditoria DROP COLUMN ip;
COMMENT ON TABLE auditoria IS
    'Auditoría de solo inserción (MATU-14). Sin IP ni agente de usuario (decisión 27 de MATU-09; la columna ip se'
    ' borró en la 0025, MATU-55). Sin grupo, solo las acciones de la cuenta (auditoria_cuenta_acotada), que la persona'
    ' lee con auditoria_cuenta_propia';
"""

DOWNGRADE = """
COMMENT ON TABLE auditoria IS NULL;
ALTER TABLE auditoria ADD COLUMN ip inet;
ALTER TABLE auditoria DROP CONSTRAINT auditoria_cuenta_acotada;
DROP INDEX auditoria_cuenta_ix;
DROP POLICY auditoria_cuenta_propia ON auditoria;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

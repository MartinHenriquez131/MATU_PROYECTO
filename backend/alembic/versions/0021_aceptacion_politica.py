"""MATU-75: la aceptación de la política de privacidad al crear la cuenta.

Cadena: 0020 (MATU-47 y MATU-66) -> 0021. down_revision = "0020".

Tabla aceptacion_politica (decisión D2 de Jorge, decisión 178 del contrato), de solo agregar: una fila por
aceptación, con la versión y la huella (SHA-256 del texto exacto que se mostró) que estampa el servidor, y cuándo.
No guarda la IP ni el navegador.

- RLS forzada. Políticas por operación y por rol, como dejó la 0020, sin ninguna FOR ALL:
  - aceptacion_propia_leer (SELECT) y aceptacion_propia_crear (INSERT): la cuenta del contexto, solo las suyas.
  - aceptacion_operacion_leer (SELECT): operación las lee para soporte, y no las crea, cambia ni borra.
- matu_app tiene solo SELECT e INSERT. Sin UPDATE ni DELETE: nadie las cambia ni las borra desde la aplicación. El
  trigger aceptacion_politica_inalterable (rechazar_modificacion de 0001) lo impide además a todo rol, también al
  dueño, salvo el borrado: queda para la conservación que decida la consulta legal (CL-49).
- usuario_id sin ON DELETE CASCADE, como dispositivo, sesion_refresh y consentimiento, que tampoco caen con la cuenta
  (solo indice_credencial lo hace). La aceptación es respaldo de qué se informó, como el consentimiento: borrar la
  cuenta no la arrastra sin aviso. Cuánto se guarda después de eliminar la cuenta lo dice la consulta legal
  (CL-49); hoy ninguna ruta borra cuentas.
- version con la forma de POLITICA_VERSION (MAYOR.MENOR) y huella de 64 caracteres hexadecimales en minúscula.
- Índice por usuario y fecha: «Tu cuenta» lee la última.

Las cuentas que ya existen quedan sin registro: no se completan con la 0.10 (D2).

Lo que no cambia: las políticas TO matu_owner y todo lo que dejó la 0020. backend/db/*.sql no se tocan.

downgrade() deja el esquema como en 0020. Lo verifica tests/test_migraciones.py.

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
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
CREATE TABLE aceptacion_politica (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id  uuid NOT NULL REFERENCES usuario(id),
    version     text NOT NULL CONSTRAINT aceptacion_politica_version_forma CHECK (version ~ '^[0-9]+\\.[0-9]+$'),
    huella      text NOT NULL CONSTRAINT aceptacion_politica_huella_forma CHECK (huella ~ '^[0-9a-f]{64}$'),
    aceptada_en timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX aceptacion_politica_usuario_ix ON aceptacion_politica (usuario_id, aceptada_en DESC);

ALTER TABLE aceptacion_politica ENABLE ROW LEVEL SECURITY;
ALTER TABLE aceptacion_politica FORCE ROW LEVEL SECURITY;
CREATE POLICY aceptacion_propia_leer ON aceptacion_politica FOR SELECT USING (usuario_id = app_usuario());
CREATE POLICY aceptacion_propia_crear ON aceptacion_politica FOR INSERT WITH CHECK (usuario_id = app_usuario());
CREATE POLICY aceptacion_operacion_leer ON aceptacion_politica FOR SELECT USING (app_rol() = 'operacion');

-- Solo agregar: ni UPDATE para nadie, ni DELETE para la aplicación
CREATE TRIGGER aceptacion_politica_inalterable BEFORE UPDATE ON aceptacion_politica
    FOR EACH ROW EXECUTE FUNCTION rechazar_modificacion();

-- Los privilegios por omisión de 03_permisos.sql dan a matu_app SELECT, INSERT, UPDATE y DELETE en toda tabla nueva:
-- se quitan y quedan solo SELECT e INSERT
REVOKE ALL ON aceptacion_politica FROM PUBLIC, matu_app;
GRANT SELECT, INSERT ON aceptacion_politica TO matu_app;
"""

DOWNGRADE = """
DROP TABLE aceptacion_politica;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

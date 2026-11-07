"""MATU-60: unidades por envase en el perfil de consumo, para la lista de insumos (RF-15, ADR-031).

Cadena: 0014 (MATU-41) -> 0015.

- perfil_consumo.unidades_por_envase integer NULL (decisión 121 de docs/api/README.md): cuántas unidades
  trae cada envase, en la unidad del insumo. Opcional: NULL cuando la familia no lo anotó. Describe el
  envase, no a la persona. La lista de insumos lo usa para sugerir envases enteros, y nunca lee
  producto.unidades_por_envase del catálogo (capa 3, decisión 104).
- CHECK perfil_consumo_envase: NULL o de 1 a 10.000, el mismo tope de tasa_unidades (decisión 43).

RLS no cambia: las políticas de la 0009 (perfil_leer, perfil_crear, perfil_editar y perfil_borrar)
deciden filas y ya cubren la columna, y matu_app no tiene permisos por columna. La conservación tampoco
cambia: el dato se borra con su fila (decisiones 69 y 70).

downgrade() quita el CHECK y la columna, y con ella los valores anotados. Deja el esquema como en 0014.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
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
ALTER TABLE perfil_consumo ADD COLUMN unidades_por_envase integer NULL;
ALTER TABLE perfil_consumo ADD CONSTRAINT perfil_consumo_envase
    CHECK (unidades_por_envase IS NULL OR unidades_por_envase BETWEEN 1 AND 10000);
COMMENT ON COLUMN perfil_consumo.unidades_por_envase IS
    'Unidades por envase en la unidad del insumo, opcional (MATU-60, decisión 121). Lo usa la lista de insumos';
"""

DOWNGRADE = """
ALTER TABLE perfil_consumo DROP CONSTRAINT perfil_consumo_envase;
ALTER TABLE perfil_consumo DROP COLUMN unidades_por_envase;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

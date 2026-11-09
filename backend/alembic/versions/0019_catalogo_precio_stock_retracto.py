"""MATU-59: el catálogo con precio exacto, stock por oferta y el retracto por producto (decisión 169).

Cadena: 0018 (MATU-72) -> 0019.

- oferta.precio_referencia pasa a oferta.precio: el precio exacto en pesos enteros, con IVA (ADR-027). Ya no
  es referencial (el comentario «referencial, ADR-011» de 0001 queda atrás). Sigue siendo bigint NOT NULL con
  CHECK (precio > 0); el CHECK se renombra a oferta_precio_check. pedido_linea no lee esta columna: guarda su
  propio precio_unitario (0002), así que sus triggers no cambian.
- oferta.stock integer NOT NULL DEFAULT 0, CHECK (stock >= 0): cuántas unidades tiene el comercio. Lo escribe
  operación o el comercio de la oferta (las políticas de 0001 no cambian). La API del catálogo muestra solo si
  hay (stock > 0), nunca la cantidad (decisión 161).
- producto.retracto_pierde_al_abrir boolean NOT NULL DEFAULT false: lo pone operación por producto, no se
  infiere de la categoría (D2 de Jorge). true en higiene y uso personal: el retracto no aplica si se abre el
  sello.

RLS no cambia: oferta_lectura y producto_lectura (SELECT USING true), oferta_comercio (UPDATE de sus ofertas)
y *_operacion (ALL) de 0001 ya cubren las columnas nuevas, y matu_app no tiene permisos por columna.

downgrade() quita stock y retracto_pierde_al_abrir con sus valores, y devuelve precio a precio_referencia con
su CHECK de 0001. Deja el esquema como en 0018.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
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
ALTER TABLE oferta RENAME COLUMN precio_referencia TO precio;
ALTER TABLE oferta RENAME CONSTRAINT oferta_precio_referencia_check TO oferta_precio_check;
COMMENT ON COLUMN oferta.precio IS
    'Precio exacto en pesos enteros, con IVA (ADR-027, MATU-59). Nunca neto ni referencial';

ALTER TABLE oferta ADD COLUMN stock integer NOT NULL DEFAULT 0;
ALTER TABLE oferta ADD CONSTRAINT oferta_stock_check CHECK (stock >= 0);
COMMENT ON COLUMN oferta.stock IS
    'Unidades que tiene el comercio (MATU-59). El catálogo muestra solo si hay, nunca la cantidad';

ALTER TABLE producto ADD COLUMN retracto_pierde_al_abrir boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN producto.retracto_pierde_al_abrir IS
    'true si el retracto no aplica al abrir el sello (higiene y uso personal). Lo pone operación (MATU-59, D2)';
"""

DOWNGRADE = """
ALTER TABLE producto DROP COLUMN retracto_pierde_al_abrir;

ALTER TABLE oferta DROP CONSTRAINT oferta_stock_check;
ALTER TABLE oferta DROP COLUMN stock;

COMMENT ON COLUMN oferta.precio IS NULL;
ALTER TABLE oferta RENAME CONSTRAINT oferta_precio_check TO oferta_precio_referencia_check;
ALTER TABLE oferta RENAME COLUMN precio TO precio_referencia;
"""


def upgrade() -> None:
    _ejecutar(UPGRADE)


def downgrade() -> None:
    _ejecutar(DOWNGRADE)

"""La capa 3 bloqueada, para probar que la API vive sin ella (MATU-40, ADR-002).

PAQUETES_CAPA_3 son los paquetes que se pueden quitar sin que las capas 1 y 2 se enteren, y que el
intérprete aparte hace fallar al importarse: catalog, ordering, payments, fulfillment y settlement, y los
que solo existen por ellos según las flechas de la sección 6.3 (replenishment y rx llegan a ordering).
Sus routers van en ROUTERS_CAPA_3 de app/main.py.

catalog es capa 3 y se puede quitar (decisión 104 de docs/api/README.md, Jorge, 04-11, MATU-40; modelo
de datos, sección 3.1, y arquitectura, sección 7.4). Las capas 1 y 2 nunca lo importan: sin convenio, el
insumo se anota con nombre_libre (ADR-002), y desde el sprint 4 consumption usa el catálogo solo por el
puerto opcional CatalogoComercio (ADR-027), cuyo adaptador vive en la capa 3. En el esquema, la única
llave declarada de las capas 1 y 2 hacia la capa 3 es perfil_consumo.producto_id → producto, anulable.

bloquear() instala un buscador de importaciones que hace fallar cualquier import de esos paquetes, como
si sus carpetas se hubieran borrado. No se llama al importar este archivo: lo usa el plugin
tests/sin_capa3.py en un intérprete aparte, nunca en el proceso de pytest que corre las demás pruebas.
"""

import sys
from collections.abc import Sequence
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from types import ModuleType

PAQUETES_CAPA_3 = tuple(
    f"app.modules.{m}"
    # MATU-63: backoffice tiene hoy solo la vista del comercio, operación del despacho y la familia después de pagar
    for m in ("catalog", "ordering", "payments", "fulfillment", "settlement", "replenishment", "rx", "backoffice")
)


def es_de_la_capa_3(nombre: str, paquetes: Sequence[str] = PAQUETES_CAPA_3) -> bool:
    return any(nombre == p or nombre.startswith(p + ".") for p in paquetes)


class BloqueoCapa3(MetaPathFinder):
    """Rechaza importar la capa 3, aunque sus archivos existan."""

    def find_spec(
        self, fullname: str, path: Sequence[str] | None = None, target: ModuleType | None = None
    ) -> ModuleSpec | None:
        if es_de_la_capa_3(fullname):
            raise ModuleNotFoundError(f"La capa 3 está quitada en esta prueba: {fullname}", name=fullname)
        return None


def bloquear() -> None:
    """Quita la capa 3 del intérprete: lo ya importado se olvida y lo nuevo falla al importarse."""
    if not any(isinstance(b, BloqueoCapa3) for b in sys.meta_path):
        sys.meta_path.insert(0, BloqueoCapa3())
    for nombre in [n for n in sys.modules if es_de_la_capa_3(n)]:
        del sys.modules[nombre]

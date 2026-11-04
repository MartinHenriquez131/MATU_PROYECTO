"""La capa 3 bloqueada, para probar que la API vive sin ella (MATU-40, ADR-002).

PAQUETES_CAPA_3 son los paquetes que el intérprete aparte hace fallar al importarse: ordering, payments,
fulfillment y settlement, y los que solo existen por ellos según las flechas de la sección 6.3
(replenishment y rx llegan a ordering).

catalog también se trata como capa 3 (modelo de datos, sección 3.1, y arquitectura, sección 7.4), en
MODULOS_CON_ROUTERS_CAPA_3: sus routers van en ROUTERS_CAPA_3, y si algo que app.main carga lo importa,
aunque sea consumption, test_app_main_no_llega_a_la_capa_3 falla. No está en PAQUETES_CAPA_3 solo
porque test_paquetes_bloqueados_siguen_las_flechas lo prohíbe mientras la flecha consumption → catalog
siga en test_arquitectura.py. Si catalog es capa 3 quitable o una dependencia de la capa 2 lo decide
el equipo (pendiente, MATU-40). En el esquema, la única llave declarada de las capas 1 y 2 hacia catalog
es perfil_consumo.producto_id → producto: anulable, con nombre_libre cuando no hay catálogo (ADR-002).

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
    f"app.modules.{m}" for m in ("ordering", "payments", "fulfillment", "settlement", "replenishment", "rx")
)

# Los routers de catalog son de la capa 3 aunque su paquete no se bloquee (ver arriba)
MODULOS_CON_ROUTERS_CAPA_3 = (*PAQUETES_CAPA_3, "app.modules.catalog")


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

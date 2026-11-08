"""Puertos del catálogo (ADR-021, ADR-027).

CatalogoComercio es la frontera con los comercios: por él entran los precios y el stock, y sale la consulta de
stock (decisión 168). Hoy no hay convenio, así que su único adaptador es CatalogoComercioSimulado
(infrastructure/catalogo_simulado.py), sin red. Cuando exista un convenio, se agrega un adaptador real sin tocar
quien lo usa.

consultar_stock recibe solo el comercio y la consulta: ningún parámetro lleva la sesión, el grupo, la persona
ni la petición (condición 4.4). Lo verifica tests/modules/catalog/test_consulta_stock_dominio.py.
"""

import uuid
from typing import Protocol

from app.modules.catalog.domain.catalogo import FilaOferta
from app.modules.catalog.domain.consulta_stock import ConsultaStock, RespuestaStock


class CatalogoComercio(Protocol):
    @property
    def precios_de_ejemplo(self) -> bool:
        """true si el adaptador es simulado: los precios son de ejemplo y la pantalla lo rotula."""
        ...

    def consultar_stock(self, comercio_id: uuid.UUID, consulta: ConsultaStock) -> RespuestaStock:
        """Cuánto de cada línea tiene el comercio. La respuesta trae la misma referencia de la consulta."""
        ...


class RepositorioCatalogo(Protocol):
    """La lectura de las ofertas publicadas (RepositorioCatalogoSQL, infrastructure/repositorio_catalogo.py)."""

    def ofertas_publicadas(self) -> list[FilaOferta]:
        """Una fila por oferta disponible de un comercio activo, de un producto y una categoría activos."""
        ...

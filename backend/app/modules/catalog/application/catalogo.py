"""Casos de uso del catálogo (MATU-59, RF-20).

- leer_catalogo: la vista para la familia. El stock se lee de oferta, nunca con una consulta en vivo al comercio
  por cada persona que mira (condición 4.6). Es una lectura pura: sin auditoría ni eventos (condición 3).
- consultar_stock: arma una ConsultaStock nueva, con su referencia aleatoria, y la envía por el puerto. La usará
  la confirmación del pedido (MATU-61); hoy solo la prueban las pruebas del módulo.
"""

import uuid
from collections.abc import Iterable

from app.modules.catalog.application.ports import CatalogoComercio, RepositorioCatalogo
from app.modules.catalog.domain.catalogo import Catalogo, armar_catalogo
from app.modules.catalog.domain.consulta_stock import RespuestaStock, nueva_consulta


class RespuestaAjena(RuntimeError):
    """El comercio respondió con otra referencia: la respuesta no es de esta consulta."""


def leer_catalogo(repositorio: RepositorioCatalogo, comercios: CatalogoComercio) -> Catalogo:
    return armar_catalogo(repositorio.ofertas_publicadas(), precios_de_ejemplo=comercios.precios_de_ejemplo)


def consultar_stock(
    comercios: CatalogoComercio, comercio_id: uuid.UUID, lineas: Iterable[tuple[uuid.UUID, int]]
) -> RespuestaStock:
    consulta = nueva_consulta(lineas)
    respuesta = comercios.consultar_stock(comercio_id, consulta)
    if respuesta.referencia != consulta.referencia:
        raise RespuestaAjena("la respuesta del comercio no corresponde a la consulta")
    return respuesta

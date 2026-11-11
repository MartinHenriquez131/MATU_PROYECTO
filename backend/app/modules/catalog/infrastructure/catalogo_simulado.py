"""El adaptador simulado de CatalogoComercio (MATU-59, ADR-027, condición 4.7).

No hace llamadas de red: responde con las existencias que recibe al crearse, por (comercio, producto). Sin
existencias anotadas, el comercio no tiene el producto. Sus logs guardan solo la cantidad de líneas: ni los
productos, ni las cantidades, ni el comercio, ni la referencia.

Mientras sea el adaptador en uso, precios_de_ejemplo es true y la pantalla rotula los precios (D1).
"""

import logging
import uuid
from collections.abc import Callable, Mapping

from app.modules.catalog.domain.consulta_stock import ConsultaStock, LineaDisponible, RespuestaStock

log = logging.getLogger("matu.catalog.simulado")


class CatalogoComercioSimulado:
    def __init__(self, existencias: Mapping[tuple[uuid.UUID, uuid.UUID], int] | None = None) -> None:
        self._existencias = dict(existencias or {})

    @property
    def precios_de_ejemplo(self) -> bool:
        return True

    def consultar_stock(self, comercio_id: uuid.UUID, consulta: ConsultaStock) -> RespuestaStock:
        log.info("consulta de stock simulada lineas=%d", len(consulta.lineas))
        lineas = tuple(
            LineaDisponible(
                producto_id=linea.producto_id,
                disponible=max(0, min(linea.cantidad, self._existencias.get((comercio_id, linea.producto_id), 0))),
            )
            for linea in consulta.lineas
        )
        return RespuestaStock(referencia=consulta.referencia, lineas=lineas)


class CatalogoComercioDesdeOfertas:
    """El simulado con las existencias de la tabla oferta (MATU-61): sin convenio, lo que «tiene» un comercio es el
    stock de su oferta publicada. Lee solo (comercio, producto, stock) del comercio consultado y responde como el
    simulado: sin red, sin precios y sin nada de quien pregunta. Lo usa la confirmación del pedido."""

    def __init__(self, existencias_de: Callable[[list[uuid.UUID]], Mapping[tuple[uuid.UUID, uuid.UUID], int]]) -> None:
        self._existencias_de = existencias_de

    @property
    def precios_de_ejemplo(self) -> bool:
        return True

    def consultar_stock(self, comercio_id: uuid.UUID, consulta: ConsultaStock) -> RespuestaStock:
        return CatalogoComercioSimulado(self._existencias_de([comercio_id])).consultar_stock(comercio_id, consulta)

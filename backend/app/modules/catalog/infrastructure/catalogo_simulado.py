"""El adaptador simulado de CatalogoComercio (MATU-59, ADR-027, condición 4.7).

No hace llamadas de red: responde con las existencias que recibe al crearse, por (comercio, producto). Sin
existencias anotadas, el comercio no tiene el producto. Sus logs guardan solo la cantidad de líneas: ni los
productos, ni las cantidades, ni el comercio, ni la referencia.

Mientras sea el adaptador en uso, precios_de_ejemplo es true y la pantalla rotula los precios (D1).
"""

import logging
import uuid
from collections.abc import Mapping

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

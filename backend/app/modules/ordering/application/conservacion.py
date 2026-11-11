"""La conservación de lo no pagado (MATU-61, D5).

Los pedidos que nunca se pagaron (borrador, total confirmado, vencido o cancelado sin pago) se borran 30 días después
de su último cambio, con sus líneas, reglas, partes por comercio, entrega y línea de tiempo. Las claves de
idempotencia se borran al vencer (24 horas). Nada justifica guardarlos 2 años (revisión previa, punto 12).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.shared.puertos import Reloj

DIAS_NO_PAGADOS = 30
PLAZO_NO_PAGADOS = timedelta(days=DIAS_NO_PAGADOS)


@dataclass(frozen=True)
class ResultadoConservacionPedidos:
    pedidos_borrados: int
    claves_borradas: int


class UnidadConservacionPedidos(Protocol):
    def conservar(self, limite: datetime, ahora: datetime) -> tuple[int, int]:
        """Llama a pedido_conservar(limite, ahora). Devuelve (pedidos, claves) borrados."""
        ...


def limite_no_pagados(ahora: datetime) -> datetime:
    return ahora - PLAZO_NO_PAGADOS


def conservar(unidad: UnidadConservacionPedidos, reloj: Reloj) -> ResultadoConservacionPedidos:
    ahora = reloj.ahora()
    pedidos, claves = unidad.conservar(limite_no_pagados(ahora), ahora)
    return ResultadoConservacionPedidos(pedidos_borrados=pedidos, claves_borradas=claves)

"""El retracto de un pedido entregado (MATU-63, R3; D-63-9 y D-63-10). Puro: sin I/O ni reloj.

- Plazo (D-63-9 c): 10 días hábiles desde la entrega, contados en la fecha de Chile, de lunes a viernes, hasta el fin
  del décimo. Es lo más protector mientras la CL-71 siga abierta. [PENDIENTE: los feriados, CL-71]
- Monto: cantidad × precio pagado de cada producto devuelto.
- Envío (D-63-10): con las condiciones 0.1 y 0.2 se devuelve siempre (a), una sola vez por pedido; desde la 0.3, solo
  si con este retracto vuelve todo lo entregado (b).
- H3 y H8 (cierre del analista): una línea admite varios retractos mientras queden unidades entregadas sin pedir. Lo
  pedido en un retracto rechazado no se vuelve a pedir (el sello ya se abrió) y no cuenta como devuelto.
- H2: el retracto pedido por correo vale 90 días desde la entrega (CL-54, mientras tanto).
- La devolución se hace al recibir el producto con el sello intacto, a la misma tarjeta, y antes de 45 días desde la
  solicitud (después, el plazo de anulación de Transbank no alcanza y lo resuelve operación por otro medio).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ZONA_CHILE = ZoneInfo("America/Santiago")
DIAS_HABILES = 10
PLAZO_POR_CORREO = timedelta(days=90)
PLAZO_ANULACION = timedelta(days=45)
# Las condiciones que prometían devolver el envío en todo retracto (condiciones-pedido 0.2, §9)
CONDICIONES_ENVIO_SIEMPRE = frozenset({"0.1", "0.2"})


class RetractoInvalido(ValueError):
    """La solicitud no cabe: fuera de plazo, sin productos, o más de lo entregado."""


def plazo_retracto(entregado_en: datetime) -> datetime:
    """El último instante para pedir el retracto: el fin del décimo día hábil después de la entrega, en Chile."""
    dia: date = entregado_en.astimezone(ZONA_CHILE).date()
    habiles = 0
    while habiles < DIAS_HABILES:
        dia += timedelta(days=1)
        if dia.weekday() < 5:
            habiles += 1
    fin = datetime.combine(dia + timedelta(days=1), time(0, 0), tzinfo=ZONA_CHILE)
    return fin - timedelta(microseconds=1)


def plazo_por_correo(entregado_en: datetime) -> datetime:
    """H2: el retracto que la familia pide por correo, hasta 90 días desde la entrega (CL-54)."""
    return entregado_en + PLAZO_POR_CORREO


def en_plazo(entregado_en: datetime, ahora: datetime) -> bool:
    return ahora <= plazo_retracto(entregado_en)


@dataclass(frozen=True)
class LineaRetractable:
    """``ya_pedidas``: lo pedido en retractos anteriores, también los rechazados. ``vigentes``: lo pedido en los que no
    se rechazaron (devueltos o por resolver)."""

    id: str
    entregadas: int
    precio_unitario: int
    ya_pedidas: int = 0
    vigentes: int = 0

    @property
    def disponibles(self) -> int:
        return self.entregadas - self.ya_pedidas


def validar(lineas: Mapping[str, LineaRetractable], pedidas: Mapping[str, int]) -> None:
    if not pedidas:
        raise RetractoInvalido("sin productos")
    for linea_id, cantidad in pedidas.items():
        linea = lineas.get(linea_id)
        if linea is None or cantidad < 1 or cantidad > linea.disponibles:
            raise RetractoInvalido("producto no retractable")


def monto_productos(lineas: Mapping[str, LineaRetractable], pedidas: Mapping[str, int]) -> int:
    return sum(lineas[linea_id].precio_unitario * cantidad for linea_id, cantidad in pedidas.items())


def incluye_envio(
    condiciones_version: str | None,
    lineas: Sequence[LineaRetractable],
    pedidas: Mapping[str, int],
    envio_ya_devuelto: bool,
) -> bool:
    """Si este retracto devuelve también el envío (D-63-10). Desde la 0.3, solo si después de este retracto queda
    devuelto (devuelto o por resolver, nunca lo rechazado) todo lo entregado (H8)."""
    if envio_ya_devuelto:
        return False
    if condiciones_version in CONDICIONES_ENVIO_SIEMPRE:
        return True
    entregadas = [linea for linea in lineas if linea.entregadas > 0]
    return bool(entregadas) and all(
        linea.vigentes + pedidas.get(linea.id, 0) == linea.entregadas for linea in entregadas
    )


def anulacion_a_tiempo(solicitado_en: datetime, ahora: datetime) -> bool:
    return ahora - solicitado_en <= PLAZO_ANULACION

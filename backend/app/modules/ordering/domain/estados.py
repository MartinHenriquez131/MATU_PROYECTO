"""Los estados del pedido y sus transiciones (arquitectura 8.1 y 12.3; decisiones 204 y 208; C1 y C9 de Jorge).

Los 17 estados son los del CHECK de pedido (migración 0002). Las 25 transiciones son las de la arquitectura 8.1 más
tres de Jorge: volver a confirmar un total vigente (``total_confirmado → total_confirmado``, C1) y «Cambiar el
pedido» desde el total vigente o vencido (``total_confirmado → borrador``, C1, y ``vencido → borrador``, C9), y la de
MATU-62: ``vencido → pagado``, solo con una venta del mismo total y el mismo total_confirmado_en (regla 2 de D-62-4,
decisión 242). Un pago aprobado de un total que ya no es el del pedido no mueve el estado (regla 3). La prueba recorre
los 17 × 17 = 289 pares.

``asignado`` y ``sin_repartidor`` no tienen transiciones (fase 2). ``cancelado``, ``cancelado_con_devolucion`` y
``cerrado`` son terminales. El vencimiento lo dice el Reloj (decisión 204): un total confirmado con ``total_vence_en``
cumplido se informa como ``vencido`` aunque la fila diga todavía ``total_confirmado``.
"""

from datetime import datetime, timedelta
from enum import StrEnum


class Estado(StrEnum):
    BORRADOR = "borrador"
    TOTAL_CONFIRMADO = "total_confirmado"
    VENCIDO = "vencido"
    PAGADO = "pagado"
    ENVIADO_A_COMERCIO = "enviado_a_comercio"
    PREPARANDO = "preparando"
    LISTO_RETIRO = "listo_retiro"
    ASIGNADO = "asignado"
    SIN_REPARTIDOR = "sin_repartidor"
    RETIRADO = "retirado"
    EN_RUTA = "en_ruta"
    ENTREGADO = "entregado"
    NO_ENTREGADO = "no_entregado"
    REPROGRAMADO = "reprogramado"
    CERRADO = "cerrado"
    CANCELADO = "cancelado"
    CANCELADO_CON_DEVOLUCION = "cancelado_con_devolucion"


E = Estado

TRANSICIONES: frozenset[tuple[Estado, Estado]] = frozenset(
    {
        # Antes de pagar (MATU-61)
        (E.BORRADOR, E.TOTAL_CONFIRMADO),
        (E.BORRADOR, E.CANCELADO),
        (E.TOTAL_CONFIRMADO, E.VENCIDO),
        (E.TOTAL_CONFIRMADO, E.TOTAL_CONFIRMADO),  # C1: volver a confirmar un total vigente
        (E.TOTAL_CONFIRMADO, E.BORRADOR),  # C1: «Cambiar el pedido»
        (E.TOTAL_CONFIRMADO, E.CANCELADO),
        (E.TOTAL_CONFIRMADO, E.PAGADO),  # MATU-62
        (E.VENCIDO, E.TOTAL_CONFIRMADO),  # «Volver a confirmar» (C23)
        (E.VENCIDO, E.BORRADOR),  # C9: «Cambiar el pedido» con el total vencido
        (E.VENCIDO, E.CANCELADO),
        (E.VENCIDO, E.PAGADO),  # MATU-62: el pago tardío del mismo total se respeta (D-62-4, regla 2)
        # Después de pagar (MATU-62 y MATU-63)
        (E.PAGADO, E.ENVIADO_A_COMERCIO),
        (E.PAGADO, E.CANCELADO_CON_DEVOLUCION),
        (E.ENVIADO_A_COMERCIO, E.PREPARANDO),
        (E.ENVIADO_A_COMERCIO, E.CANCELADO_CON_DEVOLUCION),
        (E.PREPARANDO, E.LISTO_RETIRO),
        (E.PREPARANDO, E.CANCELADO_CON_DEVOLUCION),
        (E.LISTO_RETIRO, E.RETIRADO),
        (E.RETIRADO, E.EN_RUTA),
        (E.EN_RUTA, E.ENTREGADO),
        (E.EN_RUTA, E.NO_ENTREGADO),
        (E.ENTREGADO, E.CERRADO),
        (E.NO_ENTREGADO, E.REPROGRAMADO),
        (E.NO_ENTREGADO, E.CANCELADO_CON_DEVOLUCION),
        (E.REPROGRAMADO, E.EN_RUTA),
    }
)

TERMINALES = frozenset({E.CANCELADO, E.CANCELADO_CON_DEVOLUCION, E.CERRADO})
# Fase 2: sin transiciones todavía
SIN_TRANSICIONES = frozenset({E.ASIGNADO, E.SIN_REPARTIDOR})

# Los que no se pagaron: el pedido en curso (C4) y lo que se cancela sin costo
SIN_PAGAR = frozenset({E.BORRADOR, E.TOTAL_CONFIRMADO, E.VENCIDO})

# El total confirmado vale 15 minutos (ADR-027)
VIGENCIA_TOTAL = timedelta(minutes=15)


class Motivo(StrEnum):
    """pedido_transicion.motivo, una lista cerrada (C19). None al confirmar."""

    TOTAL_VENCIO = "total_vencio"
    FAMILIA_CANCELA = "familia_cancela"
    FAMILIA_CAMBIA_CARRITO = "familia_cambia_carrito"
    AUTORIZACION_RETIRADA = "autorizacion_retirada"
    PERSONA_BORRADA = "persona_borrada"
    # MATU-62 (decisión 242): total_confirmado o vencido → pagado, con actor sistema
    PAGO_APROBADO = "pago_aprobado"


class TransicionInvalida(Exception):
    """El estado del pedido no permite la acción. La API responde 409 estado-pedido con el estado visible."""

    def __init__(self, estado: Estado) -> None:
        super().__init__("el estado del pedido no permite la acción")
        self.estado = estado


def permitida(desde: Estado, hacia: Estado) -> bool:
    return (desde, hacia) in TRANSICIONES


def exigir(desde: Estado, hacia: Estado) -> None:
    if not permitida(desde, hacia):
        raise TransicionInvalida(desde)


def vencio(estado: Estado, total_vence_en: datetime | None, ahora: datetime) -> bool:
    """Si un total confirmado ya venció según el Reloj (decisión 204)."""
    return estado is Estado.TOTAL_CONFIRMADO and total_vence_en is not None and total_vence_en <= ahora


def estado_visible(estado: Estado, total_vence_en: datetime | None, ahora: datetime) -> Estado:
    """El estado que se informa: ``vencido`` si el total confirmado ya venció, aunque la fila no lo diga todavía."""
    return Estado.VENCIDO if vencio(estado, total_vence_en, ahora) else estado


def vigencia_segundos(estado: Estado, total_vence_en: datetime | None, ahora: datetime) -> int | None:
    """Los segundos que le quedan al total según el Reloj (C23): None sin total confirmado, 0 si venció."""
    if estado not in (Estado.TOTAL_CONFIRMADO, Estado.VENCIDO) or total_vence_en is None:
        return None
    restante = int((total_vence_en - ahora).total_seconds())
    return max(0, min(restante, int(VIGENCIA_TOTAL.total_seconds())))

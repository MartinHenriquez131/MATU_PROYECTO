"""El cargo del pedido y sus montos (ADR-027; decisiones 228, 239 y 243).

Un cargo por pedido (D-62-11): nace al tocar «Pagar» y se reutiliza si está pendiente o rechazado. Se cobra una sola
vez el total confirmado, y la única devolución es la anulación, total o parcial, a la misma tarjeta. Lo devuelto nunca
supera lo cobrado (arquitectura 12.4, caso 9). Montos en pesos enteros, sin punto flotante.

Las 25 combinaciones de los 5 estados: 7 transiciones válidas y 18 que lanzan. ``anulado`` es terminal. La
participación sigue los mismos estados en femenino. La migración 0024 repite la tabla en el trigger cargo_pago_atado.
"""

from enum import StrEnum


class EstadoCargo(StrEnum):
    PENDIENTE = "pendiente"
    PAGADO = "pagado"
    RECHAZADO = "rechazado"
    DEVUELTO_PARCIAL = "devuelto_parcial"
    ANULADO = "anulado"


class EstadoParticipacion(StrEnum):
    PENDIENTE = "pendiente"
    PAGADA = "pagada"
    RECHAZADA = "rechazada"
    DEVUELTA_PARCIAL = "devuelta_parcial"
    ANULADA = "anulada"


C = EstadoCargo

TRANSICIONES_CARGO: frozenset[tuple[EstadoCargo, EstadoCargo]] = frozenset(
    {
        (C.PENDIENTE, C.PAGADO),
        (C.PENDIENTE, C.RECHAZADO),
        # Un intento nuevo reutiliza el cargo (D-62-11)
        (C.RECHAZADO, C.PENDIENTE),
        (C.PAGADO, C.DEVUELTO_PARCIAL),
        (C.PAGADO, C.ANULADO),
        # Otra devolución parcial que no completa el total
        (C.DEVUELTO_PARCIAL, C.DEVUELTO_PARCIAL),
        (C.DEVUELTO_PARCIAL, C.ANULADO),
    }
)

# El mismo nombre de estado en la participación
PARTICIPACION_DE: dict[EstadoCargo, EstadoParticipacion] = {
    C.PENDIENTE: EstadoParticipacion.PENDIENTE,
    C.PAGADO: EstadoParticipacion.PAGADA,
    C.RECHAZADO: EstadoParticipacion.RECHAZADA,
    C.DEVUELTO_PARCIAL: EstadoParticipacion.DEVUELTA_PARCIAL,
    C.ANULADO: EstadoParticipacion.ANULADA,
}

# Un pedido con cargo en estos estados ya se cobró (aunque después se devuelva)
CON_COBRO = frozenset({C.PAGADO, C.DEVUELTO_PARCIAL, C.ANULADO})


class TransicionCargoInvalida(Exception):
    """El cargo no pasa de ese estado a ese otro."""

    def __init__(self, desde: EstadoCargo, hacia: EstadoCargo) -> None:
        super().__init__("el cargo no pasa de ese estado a ese otro")
        self.desde = desde
        self.hacia = hacia


class DevolucionInvalida(ValueError):
    """La devolución es de cero o menos, o lo devuelto superaría lo cobrado (arquitectura 12.4, caso 9)."""


def permitida(desde: EstadoCargo, hacia: EstadoCargo) -> bool:
    return (desde, hacia) in TRANSICIONES_CARGO


def exigir(desde: EstadoCargo, hacia: EstadoCargo) -> None:
    if not permitida(desde, hacia):
        raise TransicionCargoInvalida(desde, hacia)


def estado_tras_devolver(estado: EstadoCargo, cobrado: int, devuelto: int, monto: int) -> EstadoCargo:
    """El estado del cargo después de devolver ``monto`` más (anulación total o parcial, a la misma tarjeta).

    ``devuelto + monto`` igual a lo cobrado deja el cargo ``anulado``; menos, ``devuelto_parcial``. Lanza
    DevolucionInvalida si ``monto`` no es positivo o si lo devuelto superaría lo cobrado, y TransicionCargoInvalida si
    el cargo no está cobrado."""
    if monto <= 0:
        raise DevolucionInvalida("se devuelve un monto positivo")
    if devuelto + monto > cobrado:
        raise DevolucionInvalida("lo devuelto no supera lo cobrado")
    hacia = C.ANULADO if devuelto + monto == cobrado else C.DEVUELTO_PARCIAL
    exigir(estado, hacia)
    return hacia

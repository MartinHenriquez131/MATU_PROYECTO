"""«Tus pedidos» (MATU-92): el estado que ve la familia y la conservación de lo pagado. Puro: sin I/O ni reloj.

- El estado del pedido para la familia agrupa los 13 estados después del pago con las llaves de ``lenguaje.md`` 38:
  ``listo_retiro``, ``asignado``, ``sin_repartidor`` y ``retirado`` se leen «Listo para salir», y ``entregado`` y
  ``cerrado``, «Entregado». Cada grupo se nombra con su primer estado, así que la llave es siempre un estado real.
  Lo que no se pagó (borrador, total confirmado, vencido y cancelado) no es de «Tus pedidos».
- El estado de cada parte es el suyo (``enviada``, ``preparando``, ``lista``, ``retirada`` o ``cancelada``), con los
  textos de la familia en la pantalla (C16), y ``cancelada_por`` dice si fue porque el comercio no tenía nada
  (``faltante``) o porque se canceló el pedido (``pedido``, R15).
- Conservación (D-92-2, CL-28 ampliada): un pedido pagado se guarda 2 años desde su cierre, la entrega o la
  cancelación con devolución. Un pedido en curso no tiene cierre y no vence. Es **la** regla: la usan la lista, el
  detalle y, cuando lleguen, la copia de MATU-54 y el borrado de MATU-89 (C27).
"""

from datetime import datetime
from enum import StrEnum

from app.modules.ordering.domain.estados import Estado

E = Estado


class EstadoFamilia(StrEnum):
    PAGADO = "pagado"
    ENVIADO_A_COMERCIO = "enviado_a_comercio"
    PREPARANDO = "preparando"
    LISTO_RETIRO = "listo_retiro"
    EN_RUTA = "en_ruta"
    ENTREGADO = "entregado"
    NO_ENTREGADO = "no_entregado"
    REPROGRAMADO = "reprogramado"
    CANCELADO_CON_DEVOLUCION = "cancelado_con_devolucion"


F = EstadoFamilia

MAPA_FAMILIA: dict[Estado, EstadoFamilia] = {
    E.PAGADO: F.PAGADO,
    E.ENVIADO_A_COMERCIO: F.ENVIADO_A_COMERCIO,
    E.PREPARANDO: F.PREPARANDO,
    E.LISTO_RETIRO: F.LISTO_RETIRO,
    E.ASIGNADO: F.LISTO_RETIRO,
    E.SIN_REPARTIDOR: F.LISTO_RETIRO,
    E.RETIRADO: F.LISTO_RETIRO,
    E.EN_RUTA: F.EN_RUTA,
    E.ENTREGADO: F.ENTREGADO,
    E.CERRADO: F.ENTREGADO,
    E.NO_ENTREGADO: F.NO_ENTREGADO,
    E.REPROGRAMADO: F.REPROGRAMADO,
    E.CANCELADO_CON_DEVOLUCION: F.CANCELADO_CON_DEVOLUCION,
}


class NoEsUnPedidoPagado(ValueError):
    """El estado es de un pedido sin pagar: no va en «Tus pedidos»."""


def estado_para_la_familia(estado: Estado) -> EstadoFamilia:
    try:
        return MAPA_FAMILIA[estado]
    except KeyError:
        raise NoEsUnPedidoPagado(estado.value) from None


# --- Las partes -------------------------------------------------------------------------------------------------

ESTADOS_PARTE = frozenset({"enviada", "preparando", "lista", "retirada", "cancelada"})
MOTIVO_FALTANTE = "producto_faltante"


class CanceladaPor(StrEnum):
    FALTANTE = "faltante"
    PEDIDO = "pedido"


def cancelada_por(estado_parte: str, motivo_cancelacion: str | None) -> CanceladaPor | None:
    """None si la parte no está cancelada. ``producto_faltante`` (el comercio no tenía nada, O3 de MATU-63) es
    ``faltante``; cualquier otro motivo (``familia_cancela``, R15, también por correo) es ``pedido``."""
    if estado_parte not in ESTADOS_PARTE:
        raise ValueError("estado de parte desconocido")
    if estado_parte != "cancelada":
        return None
    return CanceladaPor.FALTANTE if motivo_cancelacion == MOTIVO_FALTANTE else CanceladaPor.PEDIDO


# --- Conservación (D-92-2) --------------------------------------------------------------------------------------

ANIOS_PEDIDO_PAGADO = 2


def cierre_del_pedido(
    estado: Estado, entregado_en: datetime | None, cancelado_en: datetime | None, pagado_en: datetime | None
) -> datetime | None:
    """La entrega o la cancelación con devolución. Sin el instante de la cancelación, el pago: más temprano, más
    protector. None mientras el pedido sigue en curso."""
    if entregado_en is not None:
        return entregado_en
    if estado is Estado.CANCELADO_CON_DEVOLUCION:
        return cancelado_en if cancelado_en is not None else pagado_en
    return None


def _sumar_anios(instante: datetime, anios: int) -> datetime:
    try:
        return instante.replace(year=instante.year + anios)
    except ValueError:  # 29 de febrero: el 28, el día antes
        return instante.replace(year=instante.year + anios, month=2, day=28)


def conservar_hasta(cierre: datetime) -> datetime:
    return _sumar_anios(cierre, ANIOS_PEDIDO_PAGADO)


def vencido(cierre: datetime | None, ahora: datetime) -> bool:
    """Si ya pasaron los 2 años desde el cierre. Lo vencido no se muestra (C27) y espera el borrado (MATU-89)."""
    return cierre is not None and ahora >= conservar_hasta(cierre)

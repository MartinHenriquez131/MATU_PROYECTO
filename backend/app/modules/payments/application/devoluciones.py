"""Las devoluciones a la misma tarjeta (ADR-027; arquitectura 12.4, casos 3, 4 y 9; decisiones 223 y 239).

La única devolución es la anulación en Webpay, total o parcial, a la misma tarjeta con que se pagó. Nunca otra marca ni
otro medio: si un producto no se entrega, se anula su precio pagado, el mismo día.

- devolver_linea: la anulación parcial de una línea pagada que no se entrega. Una línea se devuelve una sola vez, y lo
  devuelto nunca supera lo cobrado (caso 9; también la base: transaccion_linea_devuelta_uq y transaccion_pago_atado).
- devolver_todo: la anulación de todo lo que queda cobrado, envío incluido (caso 4: no se entrega nada, o se cancela
  antes de que preparen).
- reintentar: una anulación que falló (D-62-6). Antes de volver a llamar a refund se pregunta el status: si el saldo ya
  bajó, la anulación se hizo y no se repite. Así nunca se devuelve dos veces.

MATU-62 deja estos casos de uso y su prueba con la PasarelaFalsa; los dispara el seguimiento (MATU-63, decisión 223),
que es dueño del estado del pedido después de pagar (``cancelado_con_devolucion``).
"""

import uuid
from datetime import datetime

from app.modules.payments.application.cobro import (
    EstadoAnulacion,
    anulacion_lista,
    anular,
    cargo_con_saldo,
    intentar_anulacion,
)
from app.modules.payments.application.ports import PasarelaNoDisponible, PasarelaRechazo, PasarelaWebpay, Unidad
from app.modules.payments.domain.cargo import CON_COBRO, DevolucionInvalida
from app.modules.payments.domain.venta import Anulacion, EstadoVenta, MotivoAnulacion, Venta


class SinPagoQueDevolver(LookupError):
    """El pedido no tiene una venta aprobada y vigente que anular."""


def _venta_pagada(unidad: Unidad, pedido_id: uuid.UUID) -> tuple[Venta, list[Anulacion]]:
    repo = unidad.repositorio
    cargo = repo.cargo_de(pedido_id, bloquear=True)
    if cargo is None or cargo.estado not in CON_COBRO:
        raise SinPagoQueDevolver()
    venta = next(
        (
            v
            for v in repo.ventas(cargo.id)
            if v.estado is EstadoVenta.APROBADA and not v.anulada_por_pago_tardio
        ),
        None,
    )
    if venta is None:
        raise SinPagoQueDevolver()
    return venta, repo.anulaciones(cargo.id)


def devolver_linea(
    unidad: Unidad, pasarela: PasarelaWebpay, pedido_id: uuid.UUID, linea_id: uuid.UUID, ahora: datetime
) -> EstadoAnulacion:
    """Anula el precio pagado de una línea que no se entrega (cantidad × precio_unitario, el precio fijo). Lanza
    DevolucionInvalida si la línea ya se devolvió o está en curso, o si lo devuelto superaría lo cobrado."""
    repo = unidad.repositorio
    venta, anulaciones = _venta_pagada(unidad, pedido_id)
    linea = next((x for x in repo.lineas_pagadas(pedido_id) if x.id == linea_id), None)
    if linea is None or linea.salio:
        raise SinPagoQueDevolver()
    if linea.monto_devuelto > 0 or any(a.pedido_linea_id == linea_id for a in anulaciones):
        raise DevolucionInvalida("una línea se devuelve una sola vez")
    cargo = repo.cargo(venta.cargo_id, bloquear=True)
    assert cargo is not None
    en_curso = sum(a.monto for a in anulaciones if not a.hecha and a.motivo is not MotivoAnulacion.PAGO_TARDIO)
    if linea.subtotal > cargo_con_saldo(cargo) - en_curso:
        raise DevolucionInvalida("lo devuelto no supera lo cobrado")
    return anular(unidad, pasarela, venta, linea.subtotal, MotivoAnulacion.PRODUCTO_NO_ENTREGADO, ahora, linea_id)


def devolver_todo(
    unidad: Unidad, pasarela: PasarelaWebpay, pedido_id: uuid.UUID, ahora: datetime
) -> EstadoAnulacion:
    """Anula todo lo que queda cobrado, envío incluido (caso 4)."""
    repo = unidad.repositorio
    venta, anulaciones = _venta_pagada(unidad, pedido_id)
    cargo = repo.cargo(venta.cargo_id, bloquear=True)
    assert cargo is not None
    en_curso = sum(a.monto for a in anulaciones if not a.hecha and a.motivo is not MotivoAnulacion.PAGO_TARDIO)
    saldo = cargo_con_saldo(cargo) - en_curso
    if saldo <= 0:
        raise DevolucionInvalida("no queda nada cobrado que devolver")
    return anular(unidad, pasarela, venta, saldo, MotivoAnulacion.CANCELACION, ahora)


def _saldo_libre(unidad: Unidad, venta: Venta, anulaciones: list[Anulacion]) -> int:
    cargo = unidad.repositorio.cargo(venta.cargo_id, bloquear=True)
    assert cargo is not None
    en_curso = sum(a.monto for a in anulaciones if not a.hecha and a.motivo is not MotivoAnulacion.PAGO_TARDIO)
    return cargo_con_saldo(cargo) - en_curso


def devolver_de_linea(
    unidad: Unidad,
    pasarela: PasarelaWebpay,
    pedido_id: uuid.UUID,
    linea_id: uuid.UUID,
    monto: int,
    motivo: MotivoAnulacion,
    ahora: datetime,
    retracto_id: uuid.UUID | None = None,
) -> EstadoAnulacion:
    """MATU-63 (D-63-8 y D-63-10): anula una parte del precio pagado de una línea, por lo que faltó
    (producto_no_entregado) o por un retracto. Una anulación por línea y motivo (transaccion_linea_devuelta_uq de la
    0029), y lo devuelto de la línea nunca supera lo pagado por ella ni lo cobrado."""
    repo = unidad.repositorio
    venta, anulaciones = _venta_pagada(unidad, pedido_id)
    linea = next((x for x in repo.lineas_pagadas(pedido_id) if x.id == linea_id), None)
    if linea is None or linea.salio or monto <= 0:
        raise SinPagoQueDevolver()
    if any(a.pedido_linea_id == linea_id and a.motivo is motivo for a in anulaciones):
        raise DevolucionInvalida("una línea se devuelve una vez por motivo")
    en_curso_linea = sum(a.monto for a in anulaciones if a.pedido_linea_id == linea_id and not a.hecha)
    if linea.monto_devuelto + en_curso_linea + monto > linea.subtotal:
        raise DevolucionInvalida("lo devuelto no supera lo pagado por la línea")
    if monto > _saldo_libre(unidad, venta, anulaciones):
        raise DevolucionInvalida("lo devuelto no supera lo cobrado")
    return anular(unidad, pasarela, venta, monto, motivo, ahora, linea_id, retracto_id=retracto_id)


def devolver_envio_de_retracto(
    unidad: Unidad,
    pasarela: PasarelaWebpay,
    pedido_id: uuid.UUID,
    monto: int,
    retracto_id: uuid.UUID,
    ahora: datetime,
) -> EstadoAnulacion:
    """MATU-63 (D-63-10): el envío de un retracto, una sola vez por retracto (transaccion_envio_retracto_uq)."""
    venta, anulaciones = _venta_pagada(unidad, pedido_id)
    if any(a.retracto_id == retracto_id and a.pedido_linea_id is None for a in anulaciones):
        raise DevolucionInvalida("el envío del retracto ya se devolvió")
    if monto <= 0 or monto > _saldo_libre(unidad, venta, anulaciones):
        raise DevolucionInvalida("lo devuelto no supera lo cobrado")
    return anular(unidad, pasarela, venta, monto, MotivoAnulacion.RETRACTO, ahora, retracto_id=retracto_id)


def reintentar(
    unidad: Unidad, pasarela: PasarelaWebpay, anulacion_id: uuid.UUID, ahora: datetime
) -> EstadoAnulacion | None:
    """La conciliación reintenta una anulación que no terminó (D-62-6). Pregunta el status primero: si el saldo de la
    venta ya muestra esta anulación, la da por hecha sin llamar a refund. None si no hay nada que hacer."""
    repo = unidad.repositorio
    anulacion = repo.anulacion(anulacion_id, bloquear=True)
    if anulacion is None or anulacion.hecha:
        return None
    venta = repo.venta(anulacion.venta_id, bloquear=True)
    if venta is None or venta.token is None:
        return None
    hechas = sum(a.monto for a in repo.anulaciones(venta.cargo_id) if a.venta_id == venta.id and a.hecha)
    try:
        estado = pasarela.consultar(venta.token)
    except (PasarelaNoDisponible, PasarelaRechazo):
        return EstadoAnulacion.EN_CURSO
    if estado.balance is not None and estado.balance == venta.monto - hechas - anulacion.monto:
        return anulacion_lista(unidad, anulacion, ahora)
    if estado.status in ("NULLIFIED", "REVERSED") and venta.monto - hechas == anulacion.monto:
        return anulacion_lista(unidad, anulacion, ahora)
    return intentar_anulacion(unidad, pasarela, venta, anulacion, ahora)

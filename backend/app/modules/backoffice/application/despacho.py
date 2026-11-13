"""Lo que hace el sistema después de cada acción del comercio, de operación o de la familia sobre un pedido pagado
(MATU-63; D-63-2, D-63-8, D-63-10 y D-63-11).

backoffice orquesta fulfillment (el estado del pedido y sus partes) y payments (la devolución a la misma tarjeta): ni
fulfillment ni payments se importan entre sí (tests/test_arquitectura.py). Todo corre en **una** transacción del
sistema o de operación, con el grupo del pedido y sin cuenta: nunca en la sesión del comercio (D-63-8).

- ``llevar``: el pedido sigue a sus partes (``avance``) y se devuelve lo que faltó, por unidades, el mismo día. Si no se
  entrega ningún producto, se devuelve todo con el envío y el pedido queda cancelado_con_devolucion (O3). Es
  idempotente: la tarea ``despacho`` la repite con lo que quedó pendiente (despacho_pendiente).
- ``cancelar_pagado`` (R15): el admin cancela mientras ningún comercio empezó a preparar. Bloquea el pedido como
  comercio_preparar, cancela las partes y devuelve todo, envío incluido.
- ``resolver_retracto``: operación recibe el producto y devuelve por línea, y el envío si corresponde.

Logs: nada. Una devolución que no se puede hacer ahora queda para la tarea (la línea sigue sin devolver).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.fulfillment.application.ports import RepositorioDespacho
from app.modules.fulfillment.domain.despacho import EstadoParte, Paso, avance, cancelable_despues_de_pagar
from app.modules.payments.application import devoluciones
from app.modules.payments.application.cobro import alertar
from app.modules.payments.application.ports import PasarelaWebpay, Unidad
from app.modules.payments.domain.cargo import DevolucionInvalida
from app.modules.payments.domain.venta import MotivoAnulacion
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria

PRODUCTO_FALTANTE = "ProductoFaltante"
PEDIDO_CANCELADO = "PedidoCanceladoConDevolucion"
DEVUELTAS_PARA_CERRAR = frozenset({EstadoParte.LISTA, EstadoParte.RETIRADA, EstadoParte.CANCELADA})


@dataclass(frozen=True)
class UnidadDespacho:
    despacho: RepositorioDespacho
    pagos: Unidad


class NoCancelable(Exception):
    """R15: algún comercio ya empezó a preparar, o el pedido ya no está pagado y en curso."""


def _auditar_devolucion(u: UnidadDespacho, grupo_id: uuid.UUID, persona_id: uuid.UUID, pedido_id: uuid.UUID) -> None:
    u.pagos.registro.registrar(
        EntradaAuditoria(
            grupo_id=grupo_id,
            actor_tipo=ActorTipo.SISTEMA,
            actor_ref=None,
            accion=AccionAuditoria.PAGO_DEVOLVER,
            entidad=EntidadAuditoria.PEDIDO,
            entidad_id=pedido_id,
            persona_cuidada_id=persona_id,
        )
    )


def _devolver_todo(u: UnidadDespacho, pasarela: PasarelaWebpay | None, pedido_id: uuid.UUID, ahora: datetime) -> bool:
    if pasarela is None:
        alertar("devolucion_sin_pasarela")
        return False
    try:
        devoluciones.devolver_todo(u.pagos, pasarela, pedido_id, ahora)
    except (DevolucionInvalida, devoluciones.SinPagoQueDevolver):
        return False
    return True


def llevar(
    u: UnidadDespacho,
    pasarela: PasarelaWebpay | None,
    pedido_id: uuid.UUID,
    ahora: datetime,
    comercio_id: uuid.UUID | None = None,
) -> list[Paso]:
    """El estado del pedido según sus partes, y las devoluciones de lo que faltó. ``comercio_id``: el comercio cuya
    acción lo provocó, que la línea de tiempo nombra como actor (D-63-12)."""
    d = u.despacho
    pedido = d.pedido(pedido_id, bloquear=True)
    if pedido is None or pedido.pagado_en is None:
        return []
    partes = [p for p in d.partes(pedido_id) if p.enviado_en is not None]
    pasos = avance(pedido.estado, [p.estado for p in partes])
    for paso in pasos:
        if paso.por_comercio and comercio_id is not None:
            actor_tipo, actor_ref = "comercio", comercio_id
        else:
            actor_tipo, actor_ref = "sistema", None
        d.cambiar_estado(pedido_id, paso.desde, paso.hacia, actor_tipo, actor_ref, paso.motivo, ahora)
    if pasos and pasos[-1].hacia == "cancelado_con_devolucion":
        # O3 y D-63-8: no se entrega ningún producto. Se devuelve todo, envío incluido
        if _devolver_todo(u, pasarela, pedido_id, ahora):
            _auditar_devolucion(u, pedido.grupo_id, pedido.persona_id, pedido_id)
        d.emitir(PEDIDO_CANCELADO, pedido_id, pedido.grupo_id, ahora)
        return pasos
    if pedido.estado == "cancelado_con_devolucion":
        return pasos
    cerradas = {p.id for p in partes if p.estado in DEVUELTAS_PARA_CERRAR}
    devolvio = False
    for linea in d.lineas(pedido_id):
        if linea.parte_id not in cerradas or linea.unidades_faltantes == 0:
            continue
        if linea.monto_devuelto >= linea.monto_faltante:
            continue
        if pasarela is None:
            alertar("devolucion_sin_pasarela")
            break
        try:
            devoluciones.devolver_de_linea(
                u.pagos, pasarela, pedido_id, linea.id, linea.monto_faltante, MotivoAnulacion.PRODUCTO_NO_ENTREGADO,
                ahora,
            )
        except (DevolucionInvalida, devoluciones.SinPagoQueDevolver):
            # Ya hay una anulación de esta línea (en curso o hecha): la conciliación la termina
            continue
        devolvio = True
    if devolvio:
        _auditar_devolucion(u, pedido.grupo_id, pedido.persona_id, pedido_id)
        d.emitir(PRODUCTO_FALTANTE, pedido_id, pedido.grupo_id, ahora)
    return pasos


def cancelar_pagado(
    u: UnidadDespacho,
    pasarela: PasarelaWebpay | None,
    pedido_id: uuid.UUID,
    usuario_id: uuid.UUID,
    ahora: datetime,
) -> None:
    """R15 (D-63-11). Lanza NoCancelable si algún comercio empezó a preparar. El pedido se bloquea con FOR UPDATE, la
    misma fila que bloquea comercio_preparar: una de las dos espera a la otra."""
    d = u.despacho
    pedido = d.pedido(pedido_id, bloquear=True)
    if pedido is None or pedido.pagado_en is None:
        raise NoCancelable()
    partes = d.partes(pedido_id)
    if not cancelable_despues_de_pagar(pedido.estado, [p.estado for p in partes]):
        raise NoCancelable()
    d.cancelar_partes(pedido_id, "familia_cancela", ahora)
    d.cambiar_estado(
        pedido_id, pedido.estado, "cancelado_con_devolucion", "usuario", usuario_id, "familia_cancela", ahora
    )
    u.pagos.registro.registrar(
        EntradaAuditoria(
            grupo_id=pedido.grupo_id,
            actor_tipo=ActorTipo.USUARIO,
            actor_ref=usuario_id,
            accion=AccionAuditoria.PEDIDO_CANCELAR,
            entidad=EntidadAuditoria.PEDIDO,
            entidad_id=pedido_id,
            persona_cuidada_id=pedido.persona_id,
        )
    )
    if _devolver_todo(u, pasarela, pedido_id, ahora):
        _auditar_devolucion(u, pedido.grupo_id, pedido.persona_id, pedido_id)
    d.emitir(PEDIDO_CANCELADO, pedido_id, pedido.grupo_id, ahora)

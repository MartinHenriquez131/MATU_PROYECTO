"""El retracto (MATU-63, R3; D-63-9 y D-63-10). La pantalla es de MATU-92; aquí la regla, la ruta y la devolución.

- solicitar: el admin, o quien pagó si sigue en el grupo (lo exige también la base, retracto_familia_crear), por
  producto, sobre lo entregado y no pedido antes, dentro de los 10 días hábiles desde la entrega.
- resolver: operación recibe el producto con el sello intacto y devuelve a la misma tarjeta (motivo retracto), por
  línea, y el envío si este retracto lo incluye. Antes de 45 días desde la solicitud.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.payments.application import devoluciones
from app.modules.payments.application.ports import PasarelaWebpay, Unidad
from app.modules.payments.domain import retracto as reglas
from app.modules.payments.domain.venta import MotivoAnulacion
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria


@dataclass(frozen=True)
class PedidoEntregado:
    id: uuid.UUID
    persona_id: uuid.UUID
    estado: str
    entregado_en: datetime | None
    costo_envio: int
    condiciones_version: str | None


@dataclass(frozen=True)
class Retracto:
    id: uuid.UUID
    grupo_id: uuid.UUID
    pedido_id: uuid.UUID
    solicitado_en: datetime
    plazo_hasta: datetime
    incluye_envio: bool
    estado: str


class RepositorioRetractos(Protocol):
    """Implementación: RepositorioRetractosSQL (infrastructure/repositorio_retractos.py)."""

    def pedido(self, pedido_id: uuid.UUID) -> PedidoEntregado | None: ...

    def lineas_pedidas(self, pedido_id: uuid.UUID) -> set[uuid.UUID]: ...

    def envio_pedido(self, pedido_id: uuid.UUID) -> bool: ...

    def crear(self, retracto: "Retracto", por: uuid.UUID, lineas: dict[uuid.UUID, int]) -> None: ...

    def retracto(self, retracto_id: uuid.UUID, *, bloquear: bool = False) -> "Retracto | None": ...

    def lineas_de(self, retracto_id: uuid.UUID) -> dict[uuid.UUID, int]: ...

    def resolver(self, retracto_id: uuid.UUID, estado: str, en: datetime, por: uuid.UUID) -> bool: ...


class SinPedidoEntregado(LookupError):
    """El pedido no es del grupo o no se entregó (404)."""


class FueraDePlazo(Exception):
    """Pasaron los 10 días hábiles (409)."""

    def __init__(self, plazo: datetime) -> None:
        super().__init__("fuera de plazo")
        self.plazo = plazo


class RetractoNoResoluble(Exception):
    """Ya se resolvió, o pasaron los 45 días para anular (409)."""


def solicitar(
    unidad: Unidad,
    retractos: RepositorioRetractos,
    grupo_id: uuid.UUID,
    pedido_id: uuid.UUID,
    usuario_id: uuid.UUID,
    pedidas: dict[uuid.UUID, int],
    ahora: datetime,
) -> Retracto:
    pedido = retractos.pedido(pedido_id)
    if pedido is None or pedido.entregado_en is None:
        raise SinPedidoEntregado()
    plazo = reglas.plazo_retracto(pedido.entregado_en)
    if ahora > plazo:
        raise FueraDePlazo(plazo)
    ya = retractos.lineas_pedidas(pedido_id)
    lineas = {
        str(x.id): reglas.LineaRetractable(
            id=str(x.id),
            entregadas=x.cantidad - x.unidades_faltantes,
            precio_unitario=x.precio_unitario,
            ya_pedida=x.id in ya,
        )
        for x in unidad.repositorio.lineas_pagadas(pedido_id)
        if not x.salio
    }
    por_id = {str(k): v for k, v in pedidas.items()}
    reglas.validar(lineas, por_id)
    retracto = Retracto(
        id=uuid.uuid4(),
        grupo_id=grupo_id,
        pedido_id=pedido_id,
        solicitado_en=ahora,
        plazo_hasta=plazo,
        incluye_envio=reglas.incluye_envio(
            pedido.condiciones_version, list(lineas.values()), por_id, retractos.envio_pedido(pedido_id)
        ),
        estado="solicitado",
    )
    retractos.crear(retracto, usuario_id, pedidas)
    unidad.registro.registrar(
        EntradaAuditoria(
            grupo_id=grupo_id,
            actor_tipo=ActorTipo.USUARIO,
            actor_ref=usuario_id,
            accion=AccionAuditoria.PEDIDO_RETRACTO_SOLICITAR,
            entidad=EntidadAuditoria.RETRACTO,
            entidad_id=retracto.id,
            persona_cuidada_id=pedido.persona_id,
        )
    )
    return retracto


def monto_de(unidad: Unidad, retractos: RepositorioRetractos, retracto: Retracto) -> int:
    """Lo que devuelve un retracto: sus productos a precio pagado, más el envío si lo incluye."""
    precios = {x.id: x.precio_unitario for x in unidad.repositorio.lineas_pagadas(retracto.pedido_id)}
    productos = sum(precios[linea] * cantidad for linea, cantidad in retractos.lineas_de(retracto.id).items())
    pedido = retractos.pedido(retracto.pedido_id)
    envio = pedido.costo_envio if pedido is not None and retracto.incluye_envio else 0
    return productos + envio


def resolver(
    unidad: Unidad,
    retractos: RepositorioRetractos,
    pasarela: PasarelaWebpay,
    retracto_id: uuid.UUID,
    devolver: bool,
    operador_id: uuid.UUID,
    ahora: datetime,
) -> Retracto:
    retracto = retractos.retracto(retracto_id, bloquear=True)
    if retracto is None:
        raise SinPedidoEntregado()
    if retracto.estado != "solicitado" or (devolver and not reglas.anulacion_a_tiempo(retracto.solicitado_en, ahora)):
        raise RetractoNoResoluble()
    pedido = retractos.pedido(retracto.pedido_id)
    assert pedido is not None
    if devolver:
        precios = {x.id: x.precio_unitario for x in unidad.repositorio.lineas_pagadas(retracto.pedido_id)}
        for linea_id, cantidad in retractos.lineas_de(retracto.id).items():
            devoluciones.devolver_de_linea(
                unidad, pasarela, retracto.pedido_id, linea_id, cantidad * precios[linea_id],
                MotivoAnulacion.RETRACTO, ahora, retracto_id=retracto.id,
            )
        if retracto.incluye_envio and pedido.costo_envio > 0:
            devoluciones.devolver_envio_de_retracto(
                unidad, pasarela, retracto.pedido_id, pedido.costo_envio, retracto.id, ahora
            )
    retractos.resolver(retracto.id, "devuelto" if devolver else "rechazado", ahora, operador_id)
    unidad.registro.registrar(
        EntradaAuditoria(
            grupo_id=retracto.grupo_id,
            actor_tipo=ActorTipo.OPERACION,
            actor_ref=operador_id,
            accion=AccionAuditoria.RETRACTO_RESOLVER,
            entidad=EntidadAuditoria.RETRACTO,
            entidad_id=retracto.id,
            persona_cuidada_id=pedido.persona_id,
        )
    )
    resuelto = retractos.retracto(retracto.id)
    assert resuelto is not None
    return resuelto

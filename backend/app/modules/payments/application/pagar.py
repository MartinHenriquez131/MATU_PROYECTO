"""POST /v1/pedidos/{pedido_id}/pagar (decisiones 224 a 230; D-62-8, D-62-11, D-62-12, D-62-15 y D-62-16).

Pagan admin y pagador (D-62-8). Con el pedido bloqueado y un solo instante del Reloj:

1. 409 estado-pedido si el total no está vigente (D-62-15: con el total vencido, ``vencido``, sin llamar a la
   pasarela ni crear la venta, y el pedido no cambia).
2. 409 pago-en-curso si el cargo tiene una venta iniciada vigente o autorizando (D-62-4, regla 1).
3. 412 si If-Match no es el etag que la pantalla mostró (decisión 226): nunca se cobra un total que quien paga no vio.
4. 409 condiciones-cambiaron si la versión o la huella no son las publicadas (decisión 227).
5. Guarda la aceptación (versión, huella, instante y quién), crea o reutiliza el cargo y la participación de quien
   paga, llama a create de Webpay con el total del pedido (el cuerpo no trae montos) y guarda la venta con su token.
6. Si Webpay no responde: la venta queda en error (no es un pago en curso), el cargo pendiente y no se cobró nada
   (PagoNoIniciado, 503).

Registra pago.iniciar, sin montos ni datos de la pasarela (decisión 244). No sube la versión del pedido.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from app.modules.ordering.application.pedidos import Actor, exigir_version
from app.modules.ordering.domain.estados import Estado, TransicionInvalida, estado_visible
from app.modules.ordering.domain.pedido import Pedido
from app.modules.payments.application.ports import (
    Cargo,
    Participacion,
    PasarelaNoDisponible,
    PasarelaRechazo,
    PasarelaWebpay,
    RepositorioPagos,
)
from app.modules.payments.domain import cargo as reglas_cargo
from app.modules.payments.domain.cargo import EstadoCargo, EstadoParticipacion
from app.modules.payments.domain.venta import (
    EstadoVenta,
    Venta,
    en_curso,
    nueva_clave_pasarela,
    nuevo_buy_order,
    nuevo_session_id,
)
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import RegistroAuditoria


class PagoEnCurso(Exception):
    """409 pago-en-curso (D-62-4, regla 1): ya hay una venta en curso para este pedido."""


class CondicionesCambiaron(Exception):
    """409 condiciones-cambiaron (decisión 227), con la versión vigente."""

    def __init__(self, version_vigente: str) -> None:
        super().__init__("las condiciones del pedido cambiaron")
        self.version_vigente = version_vigente


class PagoNoIniciado(Exception):
    """503 pasarela-no-disponible: Webpay no respondió. La venta quedó en error y no se cobró nada."""


class SinPasarela(Exception):
    """503 pasarela-no-disponible: la pasarela no está configurada (PASARELA_PAGO vacía)."""


@dataclass(frozen=True)
class Aceptacion:
    """Lo que trae el cuerpo de pagar: la versión y la huella de las condiciones que la pantalla mostró."""

    version: str
    huella: str


@dataclass(frozen=True)
class Inicio:
    venta: Venta
    url: str | None
    token: str | None


def hay_pago_en_curso(repositorio: RepositorioPagos, pedido_id: uuid.UUID, ahora: datetime, vida: timedelta) -> bool:
    cargo = repositorio.cargo_de(pedido_id)
    return cargo is not None and any(en_curso(v, ahora, vida) for v in repositorio.ventas(cargo.id))


def pagar(
    actor: Actor,
    pedido: Pedido,
    if_match: str,
    aceptacion: Aceptacion,
    vigentes: Aceptacion,
    ahora: datetime,
    vida: timedelta,
    return_url: str,
    repositorio: RepositorioPagos,
    pasarela: PasarelaWebpay | None,
    registro: RegistroAuditoria,
) -> Inicio:
    """``pedido`` llega bloqueado y ya verificado: del grupo, de un rol que paga y con despacho vigente (404 y 403)."""
    visible = estado_visible(pedido.estado, pedido.total_vence_en, ahora)
    if visible is not Estado.TOTAL_CONFIRMADO or pedido.total is None or pedido.total_confirmado_en is None:
        raise TransicionInvalida(visible)
    cargo = repositorio.cargo_de(pedido.id, bloquear=True)
    if cargo is not None and any(en_curso(v, ahora, vida) for v in repositorio.ventas(cargo.id)):
        raise PagoEnCurso()
    exigir_version(pedido, if_match)
    if (aceptacion.version, aceptacion.huella) != (vigentes.version, vigentes.huella):
        raise CondicionesCambiaron(vigentes.version)
    if pasarela is None:
        raise SinPasarela()

    repositorio.aceptar_condiciones(pedido.id, aceptacion.version, aceptacion.huella, ahora, actor.usuario_id)
    if cargo is None:
        cargo = Cargo(id=uuid.uuid4(), pedido_id=pedido.id, estado=EstadoCargo.PENDIENTE)
        repositorio.crear_cargo(cargo, ahora)
    elif cargo.estado is EstadoCargo.RECHAZADO:
        reglas_cargo.exigir(cargo.estado, EstadoCargo.PENDIENTE)
        cargo = replace(cargo, estado=EstadoCargo.PENDIENTE)
        repositorio.guardar_cargo(cargo)
    elif cargo.estado is not EstadoCargo.PENDIENTE:
        # Un cargo cobrado con el pedido sin pagar no debería existir: no se cobra otra vez
        raise TransicionInvalida(visible)

    participacion = repositorio.participacion_de(cargo.id, actor.usuario_id)
    if participacion is None:
        participacion = Participacion(
            id=uuid.uuid4(), cargo_id=cargo.id, usuario_id=actor.usuario_id, estado=EstadoParticipacion.PENDIENTE
        )
        repositorio.crear_participacion(participacion)
    elif participacion.estado is EstadoParticipacion.RECHAZADA:
        participacion = replace(participacion, estado=EstadoParticipacion.PENDIENTE)
        repositorio.guardar_participacion(participacion)

    venta = Venta(
        id=uuid.uuid4(),
        cargo_id=cargo.id,
        participacion_id=participacion.id,
        usuario_id=actor.usuario_id,
        estado=EstadoVenta.INICIADA,
        monto=pedido.total,
        total_confirmado_en=pedido.total_confirmado_en,
        token=None,
        buy_order=nuevo_buy_order(),
        session_id=nuevo_session_id(),
        creado_en=ahora,
    )
    try:
        inicio = pasarela.crear(venta.buy_order, venta.session_id or "", venta.monto, return_url)
    except (PasarelaNoDisponible, PasarelaRechazo):
        repositorio.insertar_venta(replace(venta, estado=EstadoVenta.ERROR), nueva_clave_pasarela())
        raise PagoNoIniciado() from None
    venta = replace(venta, token=inicio.token)
    repositorio.insertar_venta(venta, nueva_clave_pasarela())
    registro.registrar(
        EntradaAuditoria(
            grupo_id=actor.grupo_id,
            actor_tipo=ActorTipo.USUARIO,
            actor_ref=actor.usuario_id,
            accion=AccionAuditoria.PAGO_INICIAR,
            entidad=EntidadAuditoria.CARGO,
            entidad_id=cargo.id,
            request_id=actor.request_id,
        )
    )
    return Inicio(venta=venta, url=inicio.url, token=inicio.token)


def repetir(venta: Venta, pasarela: PasarelaWebpay | None, ahora: datetime, vida: timedelta) -> Inicio:
    """La misma Idempotency-Key con el mismo cuerpo (decisión 229): la venta de esa clave tal como está ahora. Mientras
    siga iniciada y vigente, la misma url y el mismo token; si ya terminó, los dos en None."""
    if venta.estado is EstadoVenta.INICIADA and en_curso(venta, ahora, vida) and pasarela is not None:
        return Inicio(venta=venta, url=pasarela.url_formulario, token=venta.token)
    return Inicio(venta=venta, url=None, token=None)

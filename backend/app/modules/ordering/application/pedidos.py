"""Casos de uso del pedido sin pagar (MATU-61; decisiones 193 a 209 y 218; C1 a C9 de Jorge).

Todo corre en la transacción de la petición (sesion_de_grupo) y con un solo instante del Reloj. Una escritura
bloquea la fila del pedido (FOR UPDATE) y, si su total confirmado ya venció, guarda primero la transición
``total_confirmado → vencido`` (actor sistema, motivo total_vencio, en el instante del vencimiento, decisión 204).

MATU-62 (D-62-4, regla 1; decisión 230): mientras el pedido tiene un pago en curso (una venta iniciada vigente o
autorizando), confirmar, «Cambiar el pedido», ajustar las líneas, cambiar las reglas o el teléfono responden 409
pago-en-curso, después del 403 y de la idempotencia y antes de estado-pedido y del 412. Cancelar, el retiro de
despacho y el borrado de la persona no se bloquean: si la venta se aprueba después, se anula completa (regla 3).

Auditoría (D12), sin contenido: pedido.crear, pedido.confirmar, pedido.cancelar y pedido.regla_faltante. Ajustar las
líneas, cambiar el teléfono y «Cambiar el pedido» no se auditan. Nada del pedido va a los logs ni a los errores.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from app.modules.catalog.application.catalogo import consultar_stock
from app.modules.catalog.application.ports import CatalogoComercio
from app.modules.ordering.application.ports import (
    Autorizacion,
    DireccionPersona,
    RepositorioPedidos,
    Transicion,
)
from app.modules.ordering.domain.estados import (
    SIN_PAGAR,
    Estado,
    Motivo,
    TransicionInvalida,
    estado_visible,
    exigir,
    vencio,
)
from app.modules.ordering.domain.pedido import (
    Entrega,
    LineaPedida,
    Pedido,
    ReglaPedida,
    aplicar_confirmacion,
    armar_carrito,
    armar_reglas,
    confirmar_lineas,
    lineas_por_consultar,
    puede_escribir,
    puede_leer,
    vence_en,
    volver_al_carrito,
)
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.celular import normalizar_celular
from app.shared.puertos import RegistroAuditoria

ORIGEN_CELULAR_CUENTA = "celular_cuenta"
ORIGEN_ESCRITO = "escrito"


class PedidoNoEncontrado(LookupError):
    """Otro grupo, inexistente, de una persona eliminada, o un rol que no alcanza. La API responde 404."""


class SinAutorizacionPedidos(Exception):
    """La persona no tiene la autorización despacho vigente (403, C21). ``revision_vencida`` distingue el tipo."""

    def __init__(self, revision_vencida: bool) -> None:
        super().__init__("falta la autorización de pedidos")
        self.revision_vencida = revision_vencida


class PedidoAbierto(Exception):
    """La persona ya tiene un pedido sin pagar (409 pedido-abierto, C4)."""

    def __init__(self, pedido_id: uuid.UUID) -> None:
        super().__init__("la persona ya tiene un pedido sin pagar")
        self.pedido_id = pedido_id


class VersionDesactualizada(Exception):
    """If-Match no es el etag vigente (412 con el pedido en ``actual``)."""

    def __init__(self, actual: Pedido) -> None:
        super().__init__("el pedido cambió")
        self.actual = actual


class PagoEnCurso(Exception):
    """Hay un pago en curso para este pedido (409 pago-en-curso, D-62-4 regla 1). No dice quién paga."""


class PedidoVacio(Exception):
    """Confirmar sin líneas (409 pedido-vacio)."""


class SinDireccion(Exception):
    """La persona no tiene dirección de entrega (409 sin-direccion, C7)."""


class TelefonoRequerido(Exception):
    """Ni en el cuerpo, ni en el pedido, ni un celular verificado de quien confirma (422 telefono_requerido)."""


class CelularInvalido(Exception):
    """El teléfono no es un celular chileno (422 celular_invalido)."""


@dataclass(frozen=True)
class Actor:
    usuario_id: uuid.UUID
    grupo_id: uuid.UUID
    rol: str
    request_id: str | None = None


# --- Lectura -------------------------------------------------------------------------------------------------------


def leer(actor: Actor, pedido_id: uuid.UUID, repositorio: RepositorioPedidos) -> Pedido:
    """El pedido para cualquiera de los cuatro roles (C3). La API elige la proyección. No se audita (decisión 52)."""
    if not puede_leer(actor.rol):
        raise PedidoNoEncontrado()
    pedido = repositorio.cargar(pedido_id)
    if pedido is None:
        raise PedidoNoEncontrado()
    return pedido


def en_curso(actor: Actor, persona_id: uuid.UUID, repositorio: RepositorioPedidos) -> Pedido:
    """El pedido sin pagar de la persona (C4), o PedidoNoEncontrado."""
    if not puede_leer(actor.rol) or not repositorio.persona_del_grupo(persona_id):
        raise PedidoNoEncontrado()
    pedido_id = repositorio.en_curso(persona_id)
    if pedido_id is None:
        raise PedidoNoEncontrado()
    return leer(actor, pedido_id, repositorio)


# --- Quién escribe -------------------------------------------------------------------------------------------------


def exigir_escritura(
    actor: Actor, persona_id: uuid.UUID, ahora: datetime, repositorio: RepositorioPedidos, *, pide_autorizacion: bool
) -> None:
    """admin y cuidador (404 a los demás) y, salvo al cancelar, la autorización despacho vigente (403, C21)."""
    if not puede_escribir(actor.rol):
        raise PedidoNoEncontrado()
    autorizacion = repositorio.autorizacion_despacho(persona_id, ahora)
    if autorizacion is None:
        raise PedidoNoEncontrado()
    if pide_autorizacion and autorizacion is not Autorizacion.VIGENTE:
        raise SinAutorizacionPedidos(revision_vencida=autorizacion is Autorizacion.REVISION_VENCIDA)


def pedido_para_escribir(
    actor: Actor,
    pedido_id: uuid.UUID,
    ahora: datetime,
    repositorio: RepositorioPedidos,
    *,
    pide_autorizacion: bool = True,
) -> Pedido:
    """El pedido bloqueado, si el actor lo puede escribir. Orden: 404 y 403."""
    if not puede_escribir(actor.rol):
        raise PedidoNoEncontrado()
    pedido = repositorio.cargar(pedido_id, bloquear=True)
    if pedido is None:
        raise PedidoNoEncontrado()
    exigir_escritura(actor, pedido.persona_id, ahora, repositorio, pide_autorizacion=pide_autorizacion)
    return pedido


def exigir_version(pedido: Pedido, if_match: str) -> None:
    if if_match.strip() != pedido.etag:
        raise VersionDesactualizada(pedido)


def exigir_sin_pago_en_curso(pedido: Pedido, ahora: datetime, repositorio: RepositorioPedidos) -> None:
    """D-62-4, regla 1: los cambios voluntarios esperan el resultado del pago en curso."""
    if repositorio.pago_en_curso(pedido.id, ahora):
        raise PagoEnCurso()


def _auditar(actor: Actor, accion: AccionAuditoria, pedido_id: uuid.UUID, registro: RegistroAuditoria) -> None:
    registro.registrar(
        EntradaAuditoria(
            grupo_id=actor.grupo_id,
            actor_tipo=ActorTipo.USUARIO,
            actor_ref=actor.usuario_id,
            accion=accion,
            entidad=EntidadAuditoria.PEDIDO,
            entidad_id=pedido_id,
            request_id=actor.request_id,
        )
    )


def _registrar_vencimiento(pedido: Pedido, ahora: datetime, repositorio: RepositorioPedidos) -> Pedido:
    """Decisión 204: si el total venció según el Reloj, se guarda la transición en el instante del vencimiento."""
    if not vencio(pedido.estado, pedido.total_vence_en, ahora):
        return pedido
    assert pedido.total_vence_en is not None
    repositorio.transicion(
        pedido.id,
        Transicion(Estado.TOTAL_CONFIRMADO, Estado.VENCIDO, None, Motivo.TOTAL_VENCIO, pedido.total_vence_en),
    )
    return replace(pedido, estado=Estado.VENCIDO)


def _transicion(
    actor: Actor | None,
    pedido: Pedido,
    hacia: Estado,
    motivo: Motivo | None,
    ahora: datetime,
    repositorio: RepositorioPedidos,
) -> None:
    exigir(pedido.estado, hacia)
    repositorio.transicion(
        pedido.id, Transicion(pedido.estado, hacia, None if actor is None else actor.usuario_id, motivo, ahora)
    )


# --- Crear y ajustar el carrito ------------------------------------------------------------------------------------


def crear(
    actor: Actor,
    persona_id: uuid.UUID,
    pedidas: Sequence[LineaPedida],
    ahora: datetime,
    costo_envio: int,
    repositorio: RepositorioPedidos,
    registro: RegistroAuditoria,
) -> Pedido:
    """El borrador con sus líneas (decisión 196). Orden: 404, 403, 422 del carrito y 409 pedido-abierto."""
    exigir_escritura(actor, persona_id, ahora, repositorio, pide_autorizacion=True)
    ofertas = repositorio.ofertas(p.oferta_id for p in pedidas)
    lineas = armar_carrito(pedidas, ofertas)
    abierto = repositorio.en_curso(persona_id)
    if abierto is not None:
        raise PedidoAbierto(abierto)
    pedido = Pedido(
        id=uuid.uuid4(),
        grupo_id=actor.grupo_id,
        persona_id=persona_id,
        estado=Estado.BORRADOR,
        version=1,
        costo_envio=costo_envio,
        total_confirmado_en=None,
        total_vence_en=None,
        creado_en=ahora,
        actualizado_en=ahora,
    )
    if not repositorio.crear(pedido, lineas, actor.usuario_id):
        # Otra petición creó uno entre la lectura y el INSERT (pedido_sin_pagar_uq)
        otro = repositorio.en_curso(persona_id)
        raise PedidoAbierto(otro if otro is not None else pedido.id)
    _auditar(actor, AccionAuditoria.PEDIDO_CREAR, pedido.id, registro)
    creado = repositorio.cargar(pedido.id)
    assert creado is not None
    return creado


def reemplazar_lineas(
    actor: Actor,
    pedido: Pedido,
    pedidas: Sequence[LineaPedida],
    if_match: str,
    ahora: datetime,
    repositorio: RepositorioPedidos,
) -> Pedido:
    """PUT …/lineas (decisión 199). Solo en borrador. Orden: 422 del carrito, 412 y 409."""
    ofertas = repositorio.ofertas(p.oferta_id for p in pedidas)
    lineas = armar_carrito(pedidas, ofertas, pedido.lineas)
    exigir_sin_pago_en_curso(pedido, ahora, repositorio)
    exigir_version(pedido, if_match)
    pedido = _registrar_vencimiento(pedido, ahora, repositorio)
    if pedido.estado is not Estado.BORRADOR:
        raise TransicionInvalida(pedido.estado)
    repositorio.reemplazar_carrito(pedido, lineas, ahora)
    return _recargar(pedido.id, repositorio)


def reemplazar_reglas(
    actor: Actor,
    pedido: Pedido,
    pedidas: Sequence[ReglaPedida],
    if_match: str,
    ahora: datetime,
    repositorio: RepositorioPedidos,
    registro: RegistroAuditoria,
) -> Pedido:
    """PUT …/reglas-faltante (decisión 200, RF-21). En borrador, total confirmado y vencido; no cambia el total ni
    el plazo. Registra pedido.regla_faltante, sin las acciones. Orden: 422, 412 y 409."""
    reglas = armar_reglas(pedidas, (linea.producto.id for linea in pedido.lineas))
    exigir_sin_pago_en_curso(pedido, ahora, repositorio)
    exigir_version(pedido, if_match)
    pedido = _registrar_vencimiento(pedido, ahora, repositorio)
    if pedido.estado not in SIN_PAGAR:
        raise TransicionInvalida(pedido.estado)
    lineas = tuple(replace(linea, regla=reglas[linea.producto.id]) for linea in pedido.lineas)
    repositorio.guardar(replace(pedido, lineas=lineas, version=pedido.version + 1))
    _auditar(actor, AccionAuditoria.PEDIDO_REGLA_FALTANTE, pedido.id, registro)
    return _recargar(pedido.id, repositorio)


# --- Confirmar, cambiar y cancelar ---------------------------------------------------------------------------------


def _telefono(escrito: str | None, pedido: Pedido, repositorio: RepositorioPedidos) -> tuple[str, str]:
    if escrito is not None:
        normalizado = normalizar_celular(escrito)
        if normalizado is None:
            raise CelularInvalido()
        return normalizado, ORIGEN_ESCRITO
    if pedido.entrega is not None:
        return pedido.entrega.telefono, pedido.entrega.telefono_origen
    propio = repositorio.celular_verificado()
    if propio is None:
        raise TelefonoRequerido()
    return propio, ORIGEN_CELULAR_CUENTA


def _entrega(direccion: DireccionPersona, telefono: str, origen: str) -> Entrega:
    return Entrega(
        calle=direccion.calle,
        numero=direccion.numero,
        depto=direccion.depto,
        comuna=direccion.comuna,
        region=direccion.region,
        referencia=direccion.referencia,
        telefono=telefono,
        telefono_origen=origen,
    )


def confirmar(
    actor: Actor,
    pedido: Pedido,
    telefono_escrito: str | None,
    ahora: datetime,
    costo_envio: int,
    repositorio: RepositorioPedidos,
    comercios: CatalogoComercio,
    registro: RegistroAuditoria,
) -> Pedido:
    """POST …/confirmar (decisiones 201 a 205; C1 y C5). Desde borrador, vencido o un total vigente, que se
    reemplaza con 15 minutos nuevos. Orden: 422 del teléfono, 409 estado-pedido, pedido-vacio, sin-direccion y
    nada-disponible. No crea el cargo (frontera con MATU-62)."""
    telefono, origen = _telefono(telefono_escrito, pedido, repositorio)
    exigir_sin_pago_en_curso(pedido, ahora, repositorio)
    pedido = _registrar_vencimiento(pedido, ahora, repositorio)
    if pedido.estado not in SIN_PAGAR:
        raise TransicionInvalida(pedido.estado)
    if not pedido.lineas:
        raise PedidoVacio()
    direccion = repositorio.direccion_de(pedido.persona_id)
    if direccion is None:
        raise SinDireccion()

    # Al volver a confirmar se consulta todo el carrito, también lo que salió la vez anterior (decisión 202)
    carrito = volver_al_carrito(pedido.lineas)
    ofertas = repositorio.ofertas_de_productos(linea.producto.id for linea in carrito)
    hay: dict[tuple[uuid.UUID, uuid.UUID], bool] = {}
    for comercio_id, lineas in lineas_por_consultar(carrito, ofertas).items():
        respuesta = consultar_stock(comercios, comercio_id, lineas)
        pedidas = dict(lineas)
        for disponible in respuesta.lineas:
            hay[(comercio_id, disponible.producto_id)] = disponible.disponible >= pedidas.get(disponible.producto_id, 0)
    confirmadas = confirmar_lineas(carrito, ofertas, hay)

    _transicion(actor, pedido, Estado.TOTAL_CONFIRMADO, None, ahora, repositorio)
    confirmado = replace(
        pedido,
        estado=Estado.TOTAL_CONFIRMADO,
        version=pedido.version + 1,
        costo_envio=costo_envio,
        total_confirmado_en=ahora,
        total_vence_en=vence_en(ahora),
        lineas=aplicar_confirmacion(replace(pedido, lineas=carrito), confirmadas),
        entrega=_entrega(direccion, telefono, origen),
    )
    repositorio.guardar(confirmado, rehacer_partes=True)
    _auditar(actor, AccionAuditoria.PEDIDO_CONFIRMAR, pedido.id, registro)
    return _recargar(pedido.id, repositorio)


def cambiar_contacto(
    actor: Actor,
    pedido: Pedido,
    telefono_escrito: str,
    if_match: str,
    ahora: datetime,
    repositorio: RepositorioPedidos,
) -> Pedido:
    """PUT …/contacto (decisión 203). En total confirmado y vencido; no toca el total ni el plazo. Orden: 422, 412
    y 409."""
    telefono = normalizar_celular(telefono_escrito)
    if telefono is None:
        raise CelularInvalido()
    exigir_sin_pago_en_curso(pedido, ahora, repositorio)
    exigir_version(pedido, if_match)
    pedido = _registrar_vencimiento(pedido, ahora, repositorio)
    if pedido.estado not in (Estado.TOTAL_CONFIRMADO, Estado.VENCIDO) or pedido.entrega is None:
        raise TransicionInvalida(pedido.estado)
    entrega = replace(pedido.entrega, telefono=telefono, telefono_origen=ORIGEN_ESCRITO)
    repositorio.guardar(replace(pedido, entrega=entrega, version=pedido.version + 1))
    return _recargar(pedido.id, repositorio)


def cambiar_pedido(actor: Actor, pedido: Pedido, ahora: datetime, repositorio: RepositorioPedidos) -> Pedido:
    """POST …/cambiar (decisión 218; C1 y C9): de vuelta al carrito desde el total vigente o vencido. Descarta el
    total, las partes por comercio y la copia de la entrega. No se audita."""
    exigir_sin_pago_en_curso(pedido, ahora, repositorio)
    pedido = _registrar_vencimiento(pedido, ahora, repositorio)
    if pedido.estado not in (Estado.TOTAL_CONFIRMADO, Estado.VENCIDO):
        raise TransicionInvalida(pedido.estado)
    _transicion(actor, pedido, Estado.BORRADOR, Motivo.FAMILIA_CAMBIA_CARRITO, ahora, repositorio)
    borrador = replace(
        pedido,
        estado=Estado.BORRADOR,
        version=pedido.version + 1,
        total_confirmado_en=None,
        total_vence_en=None,
        lineas=volver_al_carrito(pedido.lineas),
        entrega=None,
    )
    repositorio.guardar(borrador, rehacer_partes=True)
    return _recargar(pedido.id, repositorio)


def cancelar(
    actor: Actor,
    pedido: Pedido,
    ahora: datetime,
    repositorio: RepositorioPedidos,
    registro: RegistroAuditoria,
    motivo: Motivo = Motivo.FAMILIA_CANCELA,
) -> Pedido:
    """POST …/cancelar (decisión 206): sin pagar, a cancelado, sin costo, y se borra la copia de la entrega. No pide
    la autorización despacho. Registra pedido.cancelar."""
    pedido = _registrar_vencimiento(pedido, ahora, repositorio)
    if pedido.estado not in SIN_PAGAR:
        raise TransicionInvalida(pedido.estado)
    _transicion(actor, pedido, Estado.CANCELADO, motivo, ahora, repositorio)
    repositorio.guardar(replace(pedido, estado=Estado.CANCELADO, version=pedido.version + 1, entrega=None))
    _auditar(actor, AccionAuditoria.PEDIDO_CANCELAR, pedido.id, registro)
    return _recargar(pedido.id, repositorio)


def cancelar_sin_pagar_de(
    actor: Actor,
    persona_id: uuid.UUID,
    ahora: datetime,
    motivo: Motivo,
    repositorio: RepositorioPedidos,
    registro: RegistroAuditoria,
) -> int:
    """El efecto del retiro de despacho y del borrado de la persona (D1 y D2): los pedidos sin pagar pasan a
    cancelado y se borra su entrega, en la misma transacción. Los pagados siguen su plazo. Devuelve cuántos."""
    cancelados = 0
    for pedido_id in repositorio.sin_pagar_de(persona_id):
        pedido = repositorio.cargar(pedido_id, bloquear=True)
        if pedido is None or pedido.estado not in SIN_PAGAR:
            continue
        cancelar(actor, pedido, ahora, repositorio, registro, motivo)
        cancelados += 1
    return cancelados


def _recargar(pedido_id: uuid.UUID, repositorio: RepositorioPedidos) -> Pedido:
    pedido = repositorio.cargar(pedido_id)
    assert pedido is not None
    return pedido


def visible(pedido: Pedido, ahora: datetime) -> Estado:
    return estado_visible(pedido.estado, pedido.total_vence_en, ahora)

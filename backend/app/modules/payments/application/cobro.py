"""Cerrar una venta con lo que dice Transbank, y anular a la misma tarjeta (arquitectura 8.4; D-62-4 a D-62-6;
decisiones 232, 233, 239 y 242 a 244).

Lo usan la vuelta (POST /v1/pagos/retorno), la conciliación y las devoluciones. Todo corre en **una sola transacción**
con el grupo de la venta y app.rol = 'sistema': el cambio de estado, el pedido, el cargo, la auditoría y el evento del
outbox quedan juntos o no quedan (arquitectura 8.4, defensa 3). La venta llega bloqueada (FOR UPDATE): dos vueltas
del mismo token hacen un solo commit y dejan un solo cobro.

Logs: solo el evento de una alerta a operación, sin ningún identificador ni dato del pago (decisión 247).
"""

import logging
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from app.modules.payments.application.ports import (
    Cargo,
    PasarelaNoDisponible,
    PasarelaRechazo,
    PasarelaWebpay,
    PedidoCobro,
    Unidad,
)
from app.modules.payments.domain import cargo as reglas_cargo
from app.modules.payments.domain.cargo import PARTICIPACION_DE, EstadoCargo, EstadoParticipacion
from app.modules.payments.domain.venta import (
    ALERTA_TRAS,
    Anulacion,
    Decision,
    EstadoVenta,
    MotivoAnulacion,
    MotivoCierre,
    RespuestaTransaccion,
    ResultadoPago,
    Venta,
    anulacion_hecha,
    aprobada,
    codigo_autorizacion,
    cuotas,
    decidir_aprobacion,
    en_curso,
    final_sin_cobro,
    monto_coincide,
    nueva_clave_pasarela,
    nueva_referencia,
    nuevo_buy_order,
    resultado_de,
    tipo_tarjeta,
    ultimos4,
)
from app.modules.payments.events import PAGO_ANULADO, PEDIDO_PAGADO
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria

log = logging.getLogger("matu.payments")

MOTIVO_PAGO_APROBADO = "pago_aprobado"
MOTIVO_TOTAL_VENCIO = "total_vencio"


class EstadoAnulacion(StrEnum):
    """ResultadoRetorno.anulacion y Devolucion.estado."""

    EN_CURSO = "en_curso"
    HECHA = "hecha"


@dataclass(frozen=True)
class Cierre:
    resultado: ResultadoPago
    anulacion: EstadoAnulacion | None = None


PENDIENTE = Cierre(ResultadoPago.PENDIENTE)


def _auditar(unidad: Unidad, pedido: PedidoCobro, accion: AccionAuditoria, cargo_id: uuid.UUID) -> None:
    unidad.registro.registrar(
        EntradaAuditoria(
            grupo_id=pedido.grupo_id,
            actor_tipo=ActorTipo.SISTEMA,
            actor_ref=None,
            accion=accion,
            entidad=EntidadAuditoria.CARGO,
            entidad_id=cargo_id,
            # MATU-54 (0028): la persona del pedido
            persona_cuidada_id=pedido.persona_id,
        )
    )


def alertar(evento: str) -> None:
    """Una alerta a operación (D-62-6, arquitectura 12.4, caso 7): solo el nombre del evento, sin ids ni montos."""
    log.warning("alerta a operacion", extra={"evento": evento})


# --- Commit y status ----------------------------------------------------------------------------------------------


def confirmar(
    unidad: Unidad,
    pasarela: PasarelaWebpay,
    venta: Venta,
    ahora: datetime,
    vida: timedelta,
    motivo_sin_cobro: MotivoCierre = MotivoCierre.NO_APROBADA,
) -> Cierre:
    """La venta (bloqueada, iniciada o autorizando) pasa a autorizando y se hace el commit (D-62-5). Sin respuesta,
    queda autorizando y la cierra la conciliación: ``pendiente``. Si Transbank rechaza el commit (el token venció o
    nadie pagó), se pregunta el status antes de cerrar."""
    token = venta.token
    assert token is not None
    venta = replace(venta, estado=EstadoVenta.AUTORIZANDO, commit_intentado_en=ahora)
    unidad.repositorio.guardar_venta(venta)
    try:
        respuesta = pasarela.confirmar(token)
    except PasarelaNoDisponible:
        _alertar_si_tarda(venta, ahora)
        return PENDIENTE
    except PasarelaRechazo:
        try:
            respuesta = pasarela.consultar(token)
        except PasarelaNoDisponible:
            _alertar_si_tarda(venta, ahora)
            return PENDIENTE
        except PasarelaRechazo:
            return rechazar(unidad, venta, motivo_sin_cobro, ahora, vida)
        if not aprobada(respuesta):
            return rechazar(unidad, venta, motivo_sin_cobro, ahora, vida)
    return cerrar(unidad, pasarela, venta, respuesta, ahora, vida, motivo_sin_cobro)


def consultar_y_cerrar(
    unidad: Unidad, pasarela: PasarelaWebpay, venta: Venta, ahora: datetime, vida: timedelta, motivo: MotivoCierre
) -> Cierre | None:
    """La persona salió de Webpay o se acabó el tiempo del formulario: **sin commit**, se pregunta el status. Si no está
    aprobada, se cierra sin cobro con ``motivo``. None si Webpay no responde (la venta sigue iniciada)."""
    assert venta.token is not None
    try:
        respuesta = pasarela.consultar(venta.token)
    except PasarelaNoDisponible:
        return None
    except PasarelaRechazo:
        return rechazar(unidad, venta, motivo, ahora, vida)
    if aprobada(respuesta):
        return cerrar(unidad, pasarela, venta, respuesta, ahora, vida, motivo)
    return rechazar(unidad, venta, motivo, ahora, vida)


def cerrar(
    unidad: Unidad,
    pasarela: PasarelaWebpay,
    venta: Venta,
    respuesta: RespuestaTransaccion,
    ahora: datetime,
    vida: timedelta,
    motivo_sin_cobro: MotivoCierre = MotivoCierre.NO_APROBADA,
) -> Cierre:
    """Con la respuesta de commit o status: aprobada, sin cobro, o todavía sin resultado."""
    if aprobada(respuesta):
        return aprobar(unidad, pasarela, venta, respuesta, ahora, vida)
    if final_sin_cobro(respuesta) or respuesta.status == "INITIALIZED":
        return rechazar(unidad, venta, motivo_sin_cobro, ahora, vida)
    _alertar_si_tarda(venta, ahora)
    return PENDIENTE


def _alertar_si_tarda(venta: Venta, ahora: datetime) -> None:
    if ahora - venta.creado_en >= ALERTA_TRAS:
        alertar("pago_sin_respuesta")


# --- Aprobada: reglas 2 y 3 de D-62-4 -----------------------------------------------------------------------------


def aprobar(
    unidad: Unidad,
    pasarela: PasarelaWebpay,
    venta: Venta,
    respuesta: RespuestaTransaccion,
    ahora: datetime,
    vida: timedelta,
) -> Cierre:
    repo = unidad.repositorio
    venta = replace(
        venta,
        estado=EstadoVenta.APROBADA,
        cerrada_en=ahora,
        motivo_cierre=None,
        tipo_tarjeta=tipo_tarjeta(respuesta.payment_type_code),
        ultimos4=ultimos4(respuesta.card_last4),
        cuotas=cuotas(respuesta.installments_number),
        codigo_autorizacion=codigo_autorizacion(respuesta.authorization_code),
    )
    cargo = repo.cargo(venta.cargo_id, bloquear=True)
    assert cargo is not None
    pedido = repo.pedido(cargo.pedido_id, bloquear=True)
    assert pedido is not None
    decision = decidir_aprobacion(
        estado_pedido=pedido.estado,
        total=pedido.total,
        total_confirmado_en=pedido.total_confirmado_en,
        total_vence_en=pedido.total_vence_en,
        pagado_en=pedido.pagado_en,
        venta=venta,
        ahora=ahora,
        monto_aprobado=respuesta.amount,
    )
    if decision is Decision.ANULAR:
        # Regla 3: aprobada y, en el mismo momento, la anulación total a la misma tarjeta. El pedido no cambia. También
        # si Transbank aprobó otro monto (observación 2): se anula todo lo que cobró, con el motivo de la regla 3
        cobrado = venta.monto
        if not monto_coincide(respuesta.amount, venta):
            alertar("monto_distinto")
            cobrado = respuesta.amount or venta.monto
        venta = replace(venta, anulacion_total=True, anulada_por_pago_tardio=True)
        repo.guardar_venta(venta)
        estado = anular(
            unidad, pasarela, venta, venta.monto, MotivoAnulacion.PAGO_TARDIO, ahora, monto_pasarela=cobrado
        )
        _cerrar_cargo_sin_cobro(unidad, venta, ahora, vida)
        _auditar(unidad, pedido, AccionAuditoria.PAGO_ANULAR, cargo.id)
        repo.emitir(PAGO_ANULADO, pedido.id, ahora)
        return Cierre(ResultadoPago.ANULADO, estado)

    # Regla 2: se respeta el mismo total, también si venció mientras se pagaba (vencido → pagado)
    repo.guardar_venta(venta)
    desde = pedido.estado
    if desde == "total_confirmado" and decision is Decision.RESPETAR_TARDIO:
        assert pedido.total_vence_en is not None
        # Decisión 204: el vencimiento se guarda en el instante en que ocurrió
        repo.transicion(pedido.id, "total_confirmado", "vencido", MOTIVO_TOTAL_VENCIO, pedido.total_vence_en)
        desde = "vencido"
    repo.transicion(pedido.id, desde, "pagado", MOTIVO_PAGO_APROBADO, ahora)
    repo.marcar_pagado(pedido.id, ahora, nueva_referencia(repo.referencias()))
    if cargo.estado is EstadoCargo.RECHAZADO:
        # Otra venta de este cargo se cerró sin cobro mientras esta seguía en Webpay
        reglas_cargo.exigir(cargo.estado, EstadoCargo.PENDIENTE)
        cargo = replace(cargo, estado=EstadoCargo.PENDIENTE)
        repo.guardar_cargo(cargo)
    reglas_cargo.exigir(cargo.estado, EstadoCargo.PAGADO)
    repo.guardar_cargo(replace(cargo, estado=EstadoCargo.PAGADO, monto_cobrado=venta.monto))
    participacion = repo.participacion(venta.participacion_id)
    assert participacion is not None
    if participacion.estado is EstadoParticipacion.RECHAZADA:
        participacion = replace(participacion, estado=EstadoParticipacion.PENDIENTE)
        repo.guardar_participacion(participacion)
    repo.guardar_participacion(replace(participacion, estado=EstadoParticipacion.PAGADA, monto_cobrado=venta.monto))
    repo.emitir(PEDIDO_PAGADO, pedido.id, ahora)
    _auditar(unidad, pedido, AccionAuditoria.PAGO_APROBAR, cargo.id)
    resultado = ResultadoPago.APROBADO_TARDIO if decision is Decision.RESPETAR_TARDIO else ResultadoPago.APROBADO
    return Cierre(resultado)


# --- Sin cobro ----------------------------------------------------------------------------------------------------


def rechazar(unidad: Unidad, venta: Venta, motivo: MotivoCierre, ahora: datetime, vida: timedelta) -> Cierre:
    """La venta se cierra sin cobro. El cargo pasa a rechazado si no le queda otra venta en curso (decisión 233)."""
    venta = replace(venta, estado=EstadoVenta.RECHAZADA, motivo_cierre=motivo, cerrada_en=ahora)
    unidad.repositorio.guardar_venta(venta)
    _cerrar_cargo_sin_cobro(unidad, venta, ahora, vida)
    resultado = resultado_de(venta)
    assert resultado is not None
    return Cierre(resultado)


def _cerrar_cargo_sin_cobro(unidad: Unidad, venta: Venta, ahora: datetime, vida: timedelta) -> None:
    repo = unidad.repositorio
    cargo = repo.cargo(venta.cargo_id, bloquear=True)
    assert cargo is not None
    otras = [v for v in repo.ventas(cargo.id) if v.id != venta.id and en_curso(v, ahora, vida)]
    if cargo.estado is EstadoCargo.PENDIENTE and not otras:
        reglas_cargo.exigir(cargo.estado, EstadoCargo.RECHAZADO)
        repo.guardar_cargo(replace(cargo, estado=EstadoCargo.RECHAZADO))
    participacion = repo.participacion(venta.participacion_id)
    if (
        participacion is not None
        and participacion.estado is EstadoParticipacion.PENDIENTE
        and not any(v.participacion_id == participacion.id for v in otras)
    ):
        repo.guardar_participacion(replace(participacion, estado=EstadoParticipacion.RECHAZADA))


# --- Anular a la misma tarjeta (ADR-027) --------------------------------------------------------------------------


def anular(
    unidad: Unidad,
    pasarela: PasarelaWebpay,
    venta: Venta,
    monto: int,
    motivo: MotivoAnulacion,
    ahora: datetime,
    pedido_linea_id: uuid.UUID | None = None,
    monto_pasarela: int | None = None,
    retracto_id: uuid.UUID | None = None,
) -> EstadoAnulacion:
    """Registra la anulación **antes** de llamar a Transbank (arquitectura 8.4) y la intenta. Si falla, queda para
    la conciliación, que la reintenta sin devolver dos veces (D-62-6).

    ``monto_pasarela`` (observación 2): lo que se pide anular a Transbank cuando aprobó un monto distinto del de la
    venta. El registro guarda como mucho el monto de la venta (transaccion_pago_atado); un reintento usa ese
    registro."""
    anulacion = Anulacion(
        id=uuid.uuid4(),
        venta_id=venta.id,
        cargo_id=venta.cargo_id,
        participacion_id=venta.participacion_id,
        monto=monto,
        motivo=motivo,
        estado=EstadoVenta.INICIADA,
        solicitada_en=ahora,
        buy_order=nuevo_buy_order(),
        pedido_linea_id=pedido_linea_id,
        retracto_id=retracto_id,
    )
    unidad.repositorio.insertar_anulacion(anulacion, nueva_clave_pasarela())
    return intentar_anulacion(unidad, pasarela, venta, anulacion, ahora, monto_pasarela)


def intentar_anulacion(
    unidad: Unidad,
    pasarela: PasarelaWebpay,
    venta: Venta,
    anulacion: Anulacion,
    ahora: datetime,
    monto_pasarela: int | None = None,
) -> EstadoAnulacion:
    assert venta.token is not None
    try:
        respuesta = pasarela.anular(venta.token, monto_pasarela or anulacion.monto)
    except (PasarelaNoDisponible, PasarelaRechazo):
        return _anulacion_fallida(unidad, anulacion, ahora)
    if not anulacion_hecha(respuesta):
        return _anulacion_fallida(unidad, anulacion, ahora)
    return anulacion_lista(unidad, anulacion, ahora)


def _anulacion_fallida(unidad: Unidad, anulacion: Anulacion, ahora: datetime) -> EstadoAnulacion:
    anulacion = replace(anulacion, estado=EstadoVenta.ERROR, intentos=anulacion.intentos + 1)
    unidad.repositorio.guardar_anulacion(anulacion)
    if ahora - anulacion.solicitada_en >= ALERTA_TRAS or anulacion.intentos >= 3:
        alertar("anulacion_sin_hacer")
    return EstadoAnulacion.EN_CURSO


def anulacion_lista(unidad: Unidad, anulacion: Anulacion, ahora: datetime) -> EstadoAnulacion:
    """La anulación quedó hecha en Transbank: se guarda y, salvo la de un pago tardío (que no es parte del cargo,
    decisión 239), baja lo cobrado del cargo y de la participación, y marca la línea devuelta."""
    repo = unidad.repositorio
    anulacion = replace(anulacion, estado=EstadoVenta.APROBADA, hecha_en=ahora, intentos=anulacion.intentos + 1)
    repo.guardar_anulacion(anulacion)
    if anulacion.motivo is MotivoAnulacion.PAGO_TARDIO:
        return EstadoAnulacion.HECHA
    cargo = repo.cargo(anulacion.cargo_id, bloquear=True)
    assert cargo is not None
    hacia = reglas_cargo.estado_tras_devolver(cargo.estado, cargo.monto_cobrado, cargo.monto_devuelto, anulacion.monto)
    repo.guardar_cargo(replace(cargo, estado=hacia, monto_devuelto=cargo.monto_devuelto + anulacion.monto))
    participacion = repo.participacion(anulacion.participacion_id)
    if participacion is not None and participacion.monto_cobrado > 0:
        repo.guardar_participacion(
            replace(
                participacion,
                estado=PARTICIPACION_DE[hacia],
                monto_devuelto=participacion.monto_devuelto + anulacion.monto,
            )
        )
    if anulacion.pedido_linea_id is not None:
        repo.devolver_linea(anulacion.pedido_linea_id, anulacion.monto, ahora)
    return EstadoAnulacion.HECHA


def cargo_con_saldo(cargo: Cargo) -> int:
    """Lo cobrado que todavía no se devuelve."""
    return cargo.monto_cobrado - cargo.monto_devuelto

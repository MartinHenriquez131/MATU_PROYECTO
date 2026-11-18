"""Casos de uso del segundo factor de operación (MATU-81, C26 a C32).

1. ``crear_desafio``: después de la contraseña correcta de una cuenta de operación (MfaRequerido), un desafío de 256
   bits que vale 5 minutos. A Redis llega solo su SHA-256 y la cuenta. No se crea sesión ni cookie.
2. ``verificar``: POST /v1/sesiones/mfa. Orden: el desafío (DesafioVencido), los fallos de la cuenta (MfaAgotado, sin
   mirar el código), el secreto (iam_mfa_secreto, descifrado con la KEK y el AAD de la cuenta), el código en la ventana
   de ±1 paso (CodigoIncorrecto, suma un fallo y audita sesion.mfa_fallido) y el paso no usado (CodigoUsado). Con el
   código correcto: borra el desafío (una sola vez), borra los fallos, audita sesion.mfa_correcto y abre la sesión con
   la marca del segundo factor (abrir_sesion, que audita sesion.iniciar).

Nada de esto se registra en un log: ni el desafío, ni el código, ni el secreto, ni la URI, ni las huellas.
"""

import secrets
import uuid

from app.modules.iam.application.ports import (
    AlmacenMfa,
    CifradorMfa,
    DesafioGuardado,
    EmisorTokens,
    SecretoMfaInvalido,
    SecretosMfa,
    UnidadIam,
)
from app.modules.iam.application.sesiones import SesionAbierta, abrir_sesion
from app.modules.iam.domain.demora import huella
from app.modules.iam.domain.mfa import (
    BYTES_DESAFIO,
    PASO_SEGUNDOS,
    VENTANA_FALLOS,
    VENTANA_PASOS,
    VIDA_DESAFIO,
    FallosMfa,
    huella_desafio,
    paso_que_coincide,
)
from app.shared.auditoria import AccionAuditoria, ActorTipo, EntidadAuditoria, EntradaAuditoria
from app.shared.puertos import Reloj

PREFIJO_CUENTA_MFA = "mfa-cuenta"


class DesafioVencido(Exception):
    """El desafío no existe, venció o ya se usó: se vuelve a la contraseña."""


class MfaAgotado(Exception):
    """5 códigos fallidos de la cuenta en la ventana. Lleva cuántos segundos faltan."""

    def __init__(self, segundos: int) -> None:
        super().__init__("mfa agotado")
        self.segundos = segundos


class CodigoIncorrecto(Exception):
    def __init__(self, restantes: int) -> None:
        super().__init__("codigo incorrecto")
        self.restantes = restantes


class CodigoUsado(Exception):
    """El código es del paso que ya abrió una sesión (anti-repetición, C32)."""


def huella_cuenta(pepper_limites: bytes, usuario_id: uuid.UUID) -> str:
    """La clave de los fallos y del último paso en Redis: HMAC de la cuenta, nunca su id."""
    return huella(pepper_limites, PREFIJO_CUENTA_MFA, str(usuario_id))


def crear_desafio(*, usuario_id: uuid.UUID, almacen: AlmacenMfa, reloj: Reloj) -> tuple[str, DesafioGuardado]:
    """El desafío en claro (solo para la respuesta) y lo guardado."""
    desafio = secrets.token_urlsafe(BYTES_DESAFIO)
    guardado = DesafioGuardado(usuario_id=usuario_id, expira_en=reloj.ahora() + VIDA_DESAFIO)
    almacen.guardar_desafio(huella_desafio(desafio), guardado)
    return desafio, guardado


def _auditar(unidad: UnidadIam, usuario_id: uuid.UUID, accion: AccionAuditoria, request_id: str | None) -> None:
    with unidad.transaccion(usuario_id) as tx:
        tx.auditoria.registrar(
            EntradaAuditoria(
                grupo_id=None,
                actor_tipo=ActorTipo.USUARIO,
                actor_ref=usuario_id,
                accion=accion,
                entidad=EntidadAuditoria.USUARIO,
                entidad_id=usuario_id,
                request_id=request_id,
            )
        )


def verificar(
    *,
    desafio: str,
    codigo: str,
    agente_usuario: str | None,
    refresh_presentado: str | None,
    pepper_limites: bytes,
    almacen: AlmacenMfa,
    cifrador: CifradorMfa,
    secretos: SecretosMfa,
    unidad: UnidadIam,
    emisor: EmisorTokens,
    reloj: Reloj,
    request_id: str | None,
) -> SesionAbierta:
    """Lanza DesafioVencido, MfaAgotado, CodigoIncorrecto, CodigoUsado o ContadoresNoDisponibles (503)."""
    clave = huella_desafio(desafio)
    guardado = almacen.leer_desafio(clave)
    ahora = reloj.ahora()
    if guardado is None or guardado.expira_en <= ahora:
        raise DesafioVencido()
    usuario_id = guardado.usuario_id
    cuenta = huella_cuenta(pepper_limites, usuario_id)
    fallos = almacen.leer_fallos(cuenta)
    if fallos.agotados:
        almacen.borrar_desafio(clave)
        raise MfaAgotado(fallos.segundos_restantes)

    cifrado = secretos.secreto_cifrado(usuario_id)
    paso: int | None = None
    if cifrado is not None:
        try:
            paso = paso_que_coincide(cifrador.descifrar(cifrado, usuario_id), codigo, ahora)
        except SecretoMfaInvalido:
            paso = None
    if paso is None:
        sumados: FallosMfa = almacen.sumar_fallo(cuenta, int(VENTANA_FALLOS.total_seconds()))
        _auditar(unidad, usuario_id, AccionAuditoria.SESION_MFA_FALLIDO, request_id)
        if sumados.agotados:
            almacen.borrar_desafio(clave)
            raise MfaAgotado(sumados.segundos_restantes)
        raise CodigoIncorrecto(sumados.restantes)
    # El paso vive lo que dura la ventana de ±1 y un poco más
    if not almacen.usar_paso(cuenta, paso, PASO_SEGUNDOS * (2 * VENTANA_PASOS + 2)):
        raise CodigoUsado()
    if not almacen.borrar_desafio(clave):
        raise DesafioVencido()
    almacen.borrar_fallos(cuenta)
    _auditar(unidad, usuario_id, AccionAuditoria.SESION_MFA_CORRECTO, request_id)
    return abrir_sesion(
        usuario_id=usuario_id,
        agente_usuario=agente_usuario,
        refresh_presentado=refresh_presentado,
        unidad=unidad,
        emisor=emisor,
        reloj=reloj,
        request_id=request_id,
        mfa_en=ahora,
    )

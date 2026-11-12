"""Casos de uso de la invitación al grupo (MATU-42, RF-38, decisiones 293 a 301 y 308).

Quien administra crea, ve y anula invitaciones con la sesión del grupo. La persona invitada las presenta, verifica y
acepta sin app.grupo_id, con las funciones SECURITY DEFINER de la 0026 (puerto CanjeInvitaciones).

Nada de esto registra en los logs el token, el código, sus huellas ni la IP (C24).
"""

import base64
import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.care_circle.application.ports_grupo import (
    Aceptacion,
    CanjeInvitaciones,
    CredencialesInvitacion,
    InvitacionListada,
    NuevaInvitacion,
    Presentacion,
    RepositorioInvitaciones,
    Verificacion,
)
from app.modules.care_circle.domain.invitaciones import (
    ESTADOS_SIN_USAR,
    Anulacion,
    EstadoInvitacion,
    ResultadoCanje,
    anulacion,
    estado,
    expira_en,
    nombre_pila,
)
from app.modules.care_circle.domain.miembros import ROL_ADMIN, ROLES
from app.shared.puertos import Reloj


class NoEncontrado(LookupError):
    """El rol no alcanza, o la invitación no existe o es de otro grupo. La API responde 404, nunca 403."""


class InvitacionCerrada(Exception):
    """La invitación ya se usó o venció: 409 invitacion-cerrada con su estado (P8)."""

    def __init__(self, estado_actual: EstadoInvitacion) -> None:
        super().__init__("la invitación ya está cerrada")
        self.estado = estado_actual


class CodigoNoVerificable(Exception):
    """Falta PEPPER_PIN: la verificación y la aceptación responden 503 sin contar el intento (decisión 297)."""


@dataclass(frozen=True)
class Actor:
    """Quien actúa en el grupo, tomado de sesion_de_grupo."""

    usuario_id: uuid.UUID
    grupo_id: uuid.UUID
    rol: str
    request_id: str | None = None


@dataclass(frozen=True)
class InvitacionCreada:
    id: uuid.UUID
    rol: str
    token: str
    codigo: str
    creada_en: datetime
    expira_en: datetime


def texto_del_token(token: bytes) -> str:
    """base64url sin relleno, como el token del relevo: lo que va después de # en el enlace."""
    return base64.urlsafe_b64encode(token).rstrip(b"=").decode("ascii")


def exigir_admin(actor: Actor) -> None:
    if actor.rol != ROL_ADMIN:
        raise NoEncontrado()


def crear_invitacion(
    rol: str,
    actor: Actor,
    repositorio: RepositorioInvitaciones,
    credenciales: CredencialesInvitacion,
    reloj: Reloj,
) -> InvitacionCreada:
    """Una invitación de un solo uso que vence a los 7 días (D-42-3), con el nombre de pila de quien invita copiado.

    Solo admin (NoEncontrado si no). El token y el código salen una sola vez, en la respuesta (P9).
    """
    exigir_admin(actor)
    if rol not in ROLES:
        raise ValueError("rol desconocido")
    nombre = repositorio.nombre_usuario(actor.usuario_id)
    pila = nombre_pila(nombre or "")
    if not pila:
        raise NoEncontrado()
    ahora = reloj.ahora()
    invitacion_id = uuid.uuid4()
    token = credenciales.token()
    codigo = credenciales.codigo()
    vence = expira_en(ahora)
    repositorio.crear(
        NuevaInvitacion(
            id=invitacion_id,
            grupo_id=actor.grupo_id,
            rol=rol,
            invitado_por=actor.usuario_id,
            nombre_pila_invita=pila,
            token_hash=credenciales.huella_token(token),
            codigo_hash=credenciales.huella_codigo(invitacion_id, codigo),
            creada_en=ahora,
            expira_en=vence,
            request_id=actor.request_id,
        )
    )
    return InvitacionCreada(
        id=invitacion_id, rol=rol, token=texto_del_token(token), codigo=codigo, creada_en=ahora, expira_en=vence
    )


def listar_invitaciones(
    actor: Actor, repositorio: RepositorioInvitaciones, ahora: datetime
) -> list[tuple[InvitacionListada, EstadoInvitacion]]:
    """Las sin usar (pendientes y bloqueadas), de la más nueva a la más antigua (C10, P7). Solo admin."""
    exigir_admin(actor)
    con_estado = [(i, estado(i.vida, ahora)) for i in repositorio.listar(ahora)]
    return [(i, e) for i, e in con_estado if e in ESTADOS_SIN_USAR]


def anular_invitacion(
    invitacion_id: uuid.UUID, actor: Actor, repositorio: RepositorioInvitaciones, reloj: Reloj
) -> None:
    """Anula una pendiente o bloqueada. Ya anulada: nada. Usada o vencida: InvitacionCerrada (decisión 308)."""
    exigir_admin(actor)
    invitacion = repositorio.para_anular(invitacion_id)
    if invitacion is None:
        raise NoEncontrado()
    ahora = reloj.ahora()
    estado_actual = estado(invitacion.vida, ahora)
    decision = anulacion(estado_actual)
    if decision is Anulacion.CERRADA:
        raise InvitacionCerrada(estado_actual)
    if decision is Anulacion.ANULAR:
        repositorio.anular(invitacion, ahora, actor.usuario_id, actor.request_id)


def anular_las_de(
    invitado_por: uuid.UUID, actor: Actor, repositorio: RepositorioInvitaciones, ahora: datetime
) -> int:
    """Anula las invitaciones sin usar de quien deja de administrar (decisión 307). Devuelve cuántas."""
    pendientes = repositorio.sin_usar_de(invitado_por, ahora)
    for invitacion in pendientes:
        repositorio.anular(invitacion, ahora, actor.usuario_id, actor.request_id)
    return len(pendientes)


# --- La persona invitada -------------------------------------------------------------------------------


def presentar(token_hash: bytes | None, canje: CanjeInvitaciones, reloj: Reloj) -> Presentacion:
    """Quién invita, el rol y el vencimiento, o el estado que impide seguir (decisión 299)."""
    if token_hash is None:
        return Presentacion(resultado=ResultadoCanje.NO_DISPONIBLE)
    return canje.presentar(token_hash, reloj.ahora())


def _huella_del_codigo(
    token_hash: bytes,
    codigo: str,
    canje: CanjeInvitaciones,
    credenciales: CredencialesInvitacion | None,
    ahora: datetime,
) -> bytes | Presentacion:
    """La huella del código, o la presentación que impide seguir (410, 423), o CodigoNoVerificable sin PEPPER_PIN.

    El HMAC lleva el id de la invitación (separación de dominio, decisión 297), que sale de indice_token.
    """
    invitacion_id = canje.invitacion_de(token_hash)
    if invitacion_id is None:
        return Presentacion(resultado=ResultadoCanje.NO_DISPONIBLE)
    if credenciales is None:
        # Paso 7: sin PEPPER_PIN, 503 solo si la invitación todavía sirve; si no, su 410 o 423
        presentacion = canje.presentar(token_hash, ahora)
        if presentacion.resultado is ResultadoCanje.OK:
            raise CodigoNoVerificable()
        return presentacion
    return credenciales.huella_codigo(invitacion_id, codigo)


def verificar(
    token_hash: bytes | None,
    codigo: str,
    canje: CanjeInvitaciones,
    credenciales: CredencialesInvitacion | None,
    reloj: Reloj,
    request_id: str | None,
) -> Verificacion:
    """Verifica el código sin unir a nadie (P1, P3). Cuenta los intentos y bloquea en el 5.º (C30)."""
    if token_hash is None:
        return Verificacion(resultado=ResultadoCanje.NO_DISPONIBLE)
    ahora = reloj.ahora()
    huella = _huella_del_codigo(token_hash, codigo, canje, credenciales, ahora)
    if isinstance(huella, Presentacion):
        return Verificacion(resultado=huella.resultado, nombre_pila_invita=huella.nombre_pila_invita)
    return canje.verificar(token_hash, huella, ahora, request_id)


def aceptar(
    token_hash: bytes | None,
    codigo: str,
    canje: CanjeInvitaciones,
    credenciales: CredencialesInvitacion | None,
    reloj: Reloj,
    request_id: str | None,
) -> Aceptacion:
    """Une a la cuenta al grupo con el rol de la invitación, un solo uso (C22). Lo mismo que verificar, y además
    ya-eres-parte (C27)."""
    if token_hash is None:
        return Aceptacion(resultado=ResultadoCanje.NO_DISPONIBLE)
    ahora = reloj.ahora()
    huella = _huella_del_codigo(token_hash, codigo, canje, credenciales, ahora)
    if isinstance(huella, Presentacion):
        if huella.resultado is ResultadoCanje.USADA:
            # Usada: la función distingue si fue esta misma cuenta (409 ya-eres-parte). No cuenta como intento
            return canje.aceptar(token_hash, b"\x00" * 32, ahora, request_id)
        return Aceptacion(resultado=huella.resultado, nombre_pila_invita=huella.nombre_pila_invita)
    return canje.aceptar(token_hash, huella, ahora, request_id)

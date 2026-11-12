"""Reglas puras de la invitación al grupo (MATU-42, RF-38, decisiones 293 a 301 y 308).

Sin I/O ni reloj: el instante llega por argumento. El token y el código los genera la infraestructura; aquí solo
se decide su vida.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

# D-42-3: 7 días exactos según el Reloj. El CHECK invitacion_vigencia de la base fija el mismo máximo
VIGENCIA = timedelta(days=7)
# C30: el 5.º código incorrecto bloquea la invitación
INTENTOS_MAXIMOS = 5
# C31, P9: 20 invitaciones por admin y grupo en 24 horas
TOPE_INVITACIONES = 20
VENTANA_TOPE = timedelta(hours=24)
# D-42-6: las cerradas se borran a los 30 días
CONSERVACION = timedelta(days=30)
LARGO_CODIGO = 4


class EstadoInvitacion(StrEnum):
    """El estado de una invitación, en el orden del contrato (decisión 299)."""

    ANULADA = "anulada"
    USADA = "usada"
    VENCIDA = "vencida"
    BLOQUEADA = "bloqueada"
    PENDIENTE = "pendiente"


# Lo que la lista de quien administra muestra (C10, P7): las que todavía pueden cerrarse o anularse
ESTADOS_SIN_USAR = frozenset({EstadoInvitacion.PENDIENTE, EstadoInvitacion.BLOQUEADA})


class ResultadoCanje(StrEnum):
    """Lo que responden las funciones SQL de la persona invitada (migración 0026, (e))."""

    NO_DISPONIBLE = "no_disponible"
    USADA = "usada"
    VENCIDA = "vencida"
    BLOQUEADA = "bloqueada"
    CODIGO_INCORRECTO = "codigo_incorrecto"
    YA_ERES_PARTE = "ya_eres_parte"
    OK = "ok"


# Los type de los 410 (decisión 300)
TIPO_410: dict[ResultadoCanje, str] = {
    ResultadoCanje.NO_DISPONIBLE: "invitacion-no-disponible",
    ResultadoCanje.USADA: "invitacion-usada",
    ResultadoCanje.VENCIDA: "invitacion-vencida",
}


@dataclass(frozen=True)
class VidaInvitacion:
    expira_en: datetime
    aceptada_en: datetime | None
    revocada_en: datetime | None
    bloqueada_en: datetime | None


def expira_en(creada_en: datetime) -> datetime:
    return creada_en + VIGENCIA


def estado(vida: VidaInvitacion, ahora: datetime) -> EstadoInvitacion:
    """Anulada, usada, vencida, bloqueada o pendiente, en ese orden."""
    if vida.revocada_en is not None:
        return EstadoInvitacion.ANULADA
    if vida.aceptada_en is not None:
        return EstadoInvitacion.USADA
    if vida.expira_en <= ahora:
        return EstadoInvitacion.VENCIDA
    if vida.bloqueada_en is not None:
        return EstadoInvitacion.BLOQUEADA
    return EstadoInvitacion.PENDIENTE


class Anulacion(StrEnum):
    """Qué hace DELETE …/invitaciones/{id} (decisión 308)."""

    ANULAR = "anular"
    YA_ANULADA = "ya_anulada"
    CERRADA = "cerrada"


def anulacion(estado_actual: EstadoInvitacion) -> Anulacion:
    """Pendiente o bloqueada: se anula. Ya anulada: 204 sin cambios. Usada o vencida: 409 invitacion-cerrada."""
    if estado_actual in ESTADOS_SIN_USAR:
        return Anulacion.ANULAR
    if estado_actual is EstadoInvitacion.ANULADA:
        return Anulacion.YA_ANULADA
    return Anulacion.CERRADA


def nombre_pila(nombre: str) -> str:
    """La primera palabra del nombre de quien invita: lo único suyo que ve la persona invitada antes del código
    (C1, D-42-4 a), como nombre_pila_comparte del relevo."""
    partes = nombre.split()
    return partes[0][:100] if partes else ""


def url_invitacion(origen_web: str, token: str) -> str:
    """`{ORIGEN_WEB}/invitacion#<token>`: el token en el fragmento, que nunca llega al servidor (C21)."""
    return f"{origen_web}/invitacion#{token}"


def codigo_valido(codigo: str) -> bool:
    return len(codigo) == LARGO_CODIGO and codigo.isascii() and codigo.isdigit()


def tope_superado(conteo: int) -> bool:
    return conteo > TOPE_INVITACIONES

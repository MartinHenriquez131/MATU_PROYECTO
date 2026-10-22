"""Reglas puras de la sesión: cuánto dura el acceso y cuándo vence (MATU-05a, RF-37).

Sin I/O ni reloj del sistema: la hora llega desde afuera (puerto Reloj), y la firma del token es
un puerto (application/ports.py), porque necesita una librería fuera de la biblioteca estándar.
"""

from datetime import datetime, timedelta

# El access token dura 15 minutos (backlog v1.3, MATU-05a). No es configurable.
DURACION_ACCESO = timedelta(minutes=15)

# Solo una cuenta en este estado inicia sesión (columna usuario.estado)
ESTADO_ACTIVO = "activo"


class CredencialesInvalidas(Exception):
    """Email o contraseña incorrectos, o una cuenta que no puede iniciar sesión.

    Nunca dice cuál de los casos ocurrió, ni lleva el email en su mensaje.
    """


class TokenInvalido(Exception):
    """El token no sirve: firma, algoritmo, formato o vencimiento. Nunca lleva el token."""


def _exigir_zona(instante: datetime) -> None:
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("El instante debe tener zona horaria")


def vencimiento(emitido_en: datetime) -> datetime:
    """El instante en que vence un access token emitido en emitido_en."""
    _exigir_zona(emitido_en)
    return emitido_en + DURACION_ACCESO


def esta_vigente(exp: datetime, ahora: datetime) -> bool:
    """True mientras ahora sea anterior a exp. En el instante exacto de exp el token ya venció."""
    _exigir_zona(exp)
    _exigir_zona(ahora)
    return ahora < exp


def puede_iniciar_sesion(estado: str) -> bool:
    """Solo una cuenta activa inicia sesión. Bloqueada o eliminada, no."""
    return estado == ESTADO_ACTIVO

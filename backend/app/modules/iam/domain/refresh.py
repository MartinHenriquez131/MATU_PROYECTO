"""Reglas puras del refresh rotativo (MATU-38, RF-37; arquitectura 11.6; decisiones 39, 51 y 57).

Sin I/O ni reloj del sistema: la hora llega desde afuera (puerto Reloj).

- El refresh son 256 bits aleatorios en base64url (43 caracteres). La base guarda su SHA-256.
- Ventana deslizante (decisión 57 de Jorge): cada token vence 30 días después de emitirse, y cada
  renovación emite uno nuevo con emitido_en = ahora. La familia no tiene un vencimiento propio.
- Cada token sirve una vez. Presentar uno ya usado es reutilización: se revoca toda la familia.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

DURACION_REFRESH = timedelta(days=30)
# Max-Age de la cookie, en segundos: la vida de cada token
MAX_AGE_REFRESH = int(DURACION_REFRESH.total_seconds())
BYTES_REFRESH = 32

NOMBRE_COOKIE = "__Secure-matu-refresh"
RUTA_COOKIE = "/v1/sesiones"

# Valores de sesion_refresh.motivo_revocacion que usa MATU-38
MOTIVO_LOGOUT = "logout"
MOTIVO_REUTILIZACION = "reutilizacion"
MOTIVO_DISPOSITIVO = "dispositivo"

_FORMA_REFRESH = re.compile(r"[A-Za-z0-9_-]{43}")


def _exigir_zona(instante: datetime) -> None:
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("El instante debe tener zona horaria")


def tiene_forma_de_refresh(valor: str | None) -> bool:
    """True si el valor tiene la forma de un refresh: 43 caracteres base64url, sin relleno."""
    return valor is not None and _FORMA_REFRESH.fullmatch(valor) is not None


def huella_refresh(refresh: str) -> bytes:
    """SHA-256 del refresh: lo único que se guarda (sesion_refresh e indice_token)."""
    return hashlib.sha256(refresh.encode("ascii")).digest()


def vencimiento_refresh(emitido_en: datetime) -> datetime:
    """Ventana deslizante: el token vence 30 días después de emitirse, sin tope de la familia."""
    _exigir_zona(emitido_en)
    return emitido_en + DURACION_REFRESH


@dataclass(frozen=True)
class EstadoRefresh:
    """Lo que la renovación necesita saber del token presentado, leído de la base."""

    expira_en: datetime
    usado_en: datetime | None
    revocado_en: datetime | None
    dispositivo_revocado: bool
    cuenta_activa: bool


class Veredicto(Enum):
    VIGENTE = "vigente"
    RECHAZADO = "rechazado"
    REUTILIZACION = "reutilizacion"


def evaluar_renovacion(estado: EstadoRefresh, ahora: datetime) -> Veredicto:
    """Decide qué hacer con un refresh presentado para renovar.

    Orden: revocado, dispositivo revocado o cuenta no activa → RECHAZADO; vencido (expira_en igual o
    anterior a ahora) → RECHAZADO; ya usado → REUTILIZACION (se revoca la familia); si no, VIGENTE.
    Un token ya revocado nunca dispara otra revocación: su familia ya está cerrada.
    """
    _exigir_zona(ahora)
    _exigir_zona(estado.expira_en)
    if estado.revocado_en is not None or estado.dispositivo_revocado or not estado.cuenta_activa:
        return Veredicto.RECHAZADO
    if estado.expira_en <= ahora:
        return Veredicto.RECHAZADO
    if estado.usado_en is not None:
        return Veredicto.REUTILIZACION
    return Veredicto.VIGENTE


def sigue_vigente(estado: EstadoRefresh, ahora: datetime) -> bool:
    """True si el token serviría para renovar ahora. El inicio de sesión lo usa para decidir si
    reutiliza el dispositivo de la cookie."""
    return evaluar_renovacion(estado, ahora) is Veredicto.VIGENTE

"""Reglas puras del límite por IP (MATU-25, decisiones 27, 29 y 114). Sin I/O ni reloj del sistema.

- Un contador por ruta y por huella de la IP, en una ventana FIJA de una hora: la ventana empieza con
  la primera petición y no se alarga con las siguientes. La hora la lleva el vencimiento de la clave
  en Redis, no el Reloj.
- La huella es HMAC-SHA-256(PEPPER_LIMITES, "<prefijo>:<ip>"). Cada contador tiene su prefijo, así la
  misma IP deja huellas distintas en cada contador y en la demora de la entrada (MATU-38): ni la IP ni
  una huella que sirva para cruzar contadores llegan a Redis.
- Se cuenta toda petición con un cuerpo JSON válido, también la que después responde 422 por sus
  campos o 410: el límite se evalúa antes de validar los campos. Un cuerpo que no es JSON válido
  responde 422 sin contar (no crea cuenta, no prueba PIN, no revela emails) (decisión 114).
"""

import hashlib
import hmac
import math
from dataclasses import dataclass
from datetime import timedelta

VENTANA = timedelta(hours=1)


def huella(pepper: bytes, prefijo: str, valor: str) -> str:
    """HMAC-SHA-256(pepper, "<prefijo>:<valor>") en hex. Sin el pepper no se revierte con un diccionario."""
    if not pepper:
        raise ValueError("El pepper no puede estar vacío")
    return hmac.new(pepper, f"{prefijo}:{valor}".encode(), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class LimitePorIp:
    """Cuántas peticiones admite una IP en la ventana, y el prefijo propio de su huella."""

    prefijo: str
    maximo: int
    ventana: timedelta = VENTANA

    def __post_init__(self) -> None:
        if not self.prefijo or ":" in self.prefijo:
            raise ValueError("El prefijo no puede estar vacío ni llevar dos puntos")
        if self.maximo < 1:
            raise ValueError("El máximo debe ser al menos 1")
        if self.ventana.total_seconds() < 1:
            raise ValueError("La ventana debe durar al menos un segundo")

    @property
    def ventana_segundos(self) -> int:
        return math.ceil(self.ventana.total_seconds())


# RF-37: crear cuenta. Mitiga que el 409 revela si un email existe (riesgo aceptado de MATU-04)
LIMITE_REGISTRO = LimitePorIp("usuarios-ip", 5)
# RF-06: canjear el enlace y el PIN (decisión 29)
LIMITE_CANJE = LimitePorIp("canje-ip", 10)
# RF-06: presentación del relevo, más alto por CGNAT (decisión 29)
LIMITE_PRESENTACION = LimitePorIp("presentacion-ip", 30)

# MATU-42 (C29, decisión 301): la presentación de la invitación, 30 por hora, y un contador común de canje para la
# verificación y la aceptación, 20 por hora (una unión legítima usa dos llamadas; decisión 324)
LIMITE_PRESENTACION_INVITACION = LimitePorIp("presentacion-invitacion-ip", 30)
LIMITE_CANJE_INVITACION = LimitePorIp("canje-invitacion-ip", 20)

LIMITES = (LIMITE_REGISTRO, LIMITE_CANJE, LIMITE_PRESENTACION, LIMITE_PRESENTACION_INVITACION, LIMITE_CANJE_INVITACION)


def excedido(conteo: int, limite: LimitePorIp) -> bool:
    """Si la petición número ``conteo`` de la ventana pasa del máximo."""
    return conteo > limite.maximo


def retry_after(ttl_segundos: int, limite: LimitePorIp) -> int:
    """Segundos del Retry-After: lo que le queda a la ventana, entre 1 y su duración."""
    return max(1, min(ttl_segundos, limite.ventana_segundos))

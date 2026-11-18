"""El segundo factor de las cuentas de operación (MATU-81, C26 a C32; arquitectura 11.6).

Reglas puras, sin I/O ni reloj del sistema: el instante llega desde afuera (puerto Reloj).

- TOTP según RFC 6238 sobre HOTP (RFC 4226): HMAC-SHA1, 6 cifras, pasos de 30 segundos y una ventana de ±1 paso.
  Sin dependencias nuevas: hmac y hashlib de la biblioteca estándar, probados con los vectores del RFC.
- El secreto tiene 160 bits (20 bytes), como recomienda el RFC 4226. Se muestra una sola vez, dentro de la URI
  otpauth del alta, en base32 sin relleno.
- Un paso ya usado no se acepta de nuevo (anti-repetición): quien verifica guarda el último paso aceptado.
- La entrada en dos pasos: el desafío vale 5 minutos y la sesión de operación 12 horas desde el segundo factor, sin
  la ventana deslizante de 30 días. Se permiten 5 códigos fallidos por cuenta en una ventana de 15 minutos.
"""

import base64
import hashlib
import hmac
import re
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import quote

CIFRAS = 6
PASO_SEGUNDOS = 30
VENTANA_PASOS = 1
BYTES_SECRETO = 20

VIDA_DESAFIO = timedelta(minutes=5)
DURACION_SESION_OPERACION = timedelta(hours=12)
FALLOS_PERMITIDOS = 5
VENTANA_FALLOS = timedelta(minutes=15)
BYTES_DESAFIO = 32

EMISOR = "MATU"
ETIQUETA = "MATU:operacion"

_FORMA_CODIGO = re.compile(r"[0-9]{6}")
_FORMA_DESAFIO = re.compile(r"[A-Za-z0-9_-]{43}")


def _exigir_zona(instante: datetime) -> None:
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("El instante debe tener zona horaria")


def hotp(secreto: bytes, contador: int, cifras: int = CIFRAS, algoritmo: str = "sha1") -> str:
    """RFC 4226, sección 5.3: el código del contador, con el truncado dinámico."""
    if contador < 0:
        raise ValueError("El contador no puede ser negativo")
    resumen = hmac.new(secreto, struct.pack(">Q", contador), algoritmo).digest()
    corte = resumen[-1] & 0x0F
    binario = struct.unpack(">I", resumen[corte:corte + 4])[0] & 0x7FFFFFFF
    return f"{binario % 10**cifras:0{cifras}d}"


def paso_de(instante: datetime) -> int:
    """El paso TOTP (T) de un instante: segundos Unix divididos en pasos de 30 (RFC 6238, sección 4.2)."""
    _exigir_zona(instante)
    return int(instante.timestamp()) // PASO_SEGUNDOS


def totp(secreto: bytes, instante: datetime, cifras: int = CIFRAS, algoritmo: str = "sha1") -> str:
    return hotp(secreto, paso_de(instante), cifras, algoritmo)


def tiene_forma_de_codigo(codigo: str) -> bool:
    return _FORMA_CODIGO.fullmatch(codigo) is not None


def tiene_forma_de_desafio(desafio: str) -> bool:
    return _FORMA_DESAFIO.fullmatch(desafio) is not None


def paso_que_coincide(secreto: bytes, codigo: str, ahora: datetime) -> int | None:
    """El paso, dentro de la ventana de ±1, cuyo código es ``codigo``, o None. Compara en tiempo constante y recorre
    toda la ventana aunque ya haya coincidido."""
    if not tiene_forma_de_codigo(codigo):
        return None
    actual = paso_de(ahora)
    encontrado: int | None = None
    for paso in range(actual - VENTANA_PASOS, actual + VENTANA_PASOS + 1):
        if hmac.compare_digest(hotp(secreto, paso), codigo) and encontrado is None:
            encontrado = paso
    return encontrado


def secreto_en_base32(secreto: bytes) -> str:
    return base64.b32encode(secreto).decode("ascii").rstrip("=")


def uri_otpauth(secreto: bytes) -> str:
    """La URI que se muestra una sola vez en el alta (Key Uri Format de Google Authenticator). La etiqueta no lleva
    el correo ni el nombre de nadie."""
    return (
        f"otpauth://totp/{quote(ETIQUETA)}?secret={secreto_en_base32(secreto)}&issuer={EMISOR}"
        f"&algorithm=SHA1&digits={CIFRAS}&period={PASO_SEGUNDOS}"
    )


def aad_secreto(usuario_id: object) -> bytes:
    """Los datos asociados del cifrado del secreto (C26): ``mfa:<usuario_id>``. Un secreto copiado a otra cuenta no
    se descifra."""
    return f"mfa:{usuario_id}".encode("ascii")


def huella_desafio(desafio: str) -> str:
    """Lo único que se guarda del desafío (C29): su SHA-256 en hexadecimal."""
    return hashlib.sha256(desafio.encode("ascii")).hexdigest()


def vence_la_sesion(mfa_en: datetime) -> datetime:
    _exigir_zona(mfa_en)
    return mfa_en + DURACION_SESION_OPERACION


def sesion_vigente(mfa_en: datetime | None, ahora: datetime) -> bool:
    """C30 y C31: la marca existe y no pasaron 12 horas desde el segundo factor."""
    return mfa_en is not None and ahora < vence_la_sesion(mfa_en)


@dataclass(frozen=True)
class FallosMfa:
    conteo: int
    segundos_restantes: int

    @property
    def agotados(self) -> bool:
        return self.conteo >= FALLOS_PERMITIDOS

    @property
    def restantes(self) -> int:
        return max(0, FALLOS_PERMITIDOS - self.conteo)


SIN_FALLOS = FallosMfa(0, 0)

"""La clave VAPID de Web Push (RFC 8292), MATU-55 (decisión 262).

VAPID_CLAVE_PRIVADA es el escalar privado P-256 de 32 bytes en base64url sin relleno. La pública se deriva de ella: el
punto sin comprimir de 65 bytes (empieza con 0x04) en base64url sin relleno, 87 caracteres que empiezan con «B». Es la
que el navegador recibe como applicationServerKey.

La privada nunca sale de aquí: ni en un mensaje de error, ni en un log, ni en una respuesta. Los errores son fijos.
"""

import base64
import binascii

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

LARGO_PRIVADA = 32


class ClaveVapidInvalida(ValueError):
    """El valor no es un escalar P-256 válido en base64url. El mensaje nunca lleva el valor."""

    def __init__(self) -> None:
        super().__init__("VAPID_CLAVE_PRIVADA debe ser una clave privada P-256 de 32 bytes en base64url sin relleno")


def _b64url(crudo: bytes) -> str:
    return base64.urlsafe_b64encode(crudo).rstrip(b"=").decode("ascii")


def _desde_b64url(texto: str) -> bytes:
    if not texto or "=" in texto or any(c.isspace() for c in texto):
        raise ClaveVapidInvalida()
    try:
        return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))
    except (binascii.Error, ValueError):
        raise ClaveVapidInvalida() from None


def _privada(texto: str) -> ec.EllipticCurvePrivateKey:
    crudo = _desde_b64url(texto)
    # Que vuelva a codificarse igual: rechaza caracteres sobrantes que b64decode ignora
    if len(crudo) != LARGO_PRIVADA or _b64url(crudo) != texto:
        raise ClaveVapidInvalida()
    try:
        return ec.derive_private_key(int.from_bytes(crudo, "big"), ec.SECP256R1())
    except ValueError:
        # Cero o mayor que el orden de la curva
        raise ClaveVapidInvalida() from None


def validar_clave_privada(texto: str) -> None:
    """Lanza ClaveVapidInvalida si el texto no es una clave privada P-256 válida."""
    _privada(texto)


def clave_publica(texto_privada: str) -> str:
    """La clave pública de la privada, en base64url sin relleno (87 caracteres, empieza con «B»)."""
    punto = _privada(texto_privada).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64url(punto)


def generar_clave_privada() -> str:
    """Una clave privada nueva, en el formato de VAPID_CLAVE_PRIVADA. Solo la usa backend/scripts/generar_vapid.py."""
    privada = ec.generate_private_key(ec.SECP256R1())
    return _b64url(privada.private_numbers().private_value.to_bytes(LARGO_PRIVADA, "big"))

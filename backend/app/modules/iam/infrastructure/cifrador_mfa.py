"""El secreto TOTP de una cuenta de operación, cifrado con la KEK (MATU-81, C26).

AES-256-GCM con la KEK de 32 bytes (KEK_ENTORNO, la misma de la ficha y con las mismas restricciones: solo con
ENTORNO local, pruebas o staging y CUSTODIA_KEK=entorno_sintetico) y el AAD ``mfa:<usuario_id>``. Lo guardado es
``kek_version (1 byte) || nonce (12) || cifrado con su etiqueta (20 + 16)``. Un nonce al azar por cifrado: el secreto
se cifra una vez por alta.

Nunca se registra ni sale en un error: SecretoMfaInvalido lleva un mensaje fijo. El repr oculta la clave.
"""

import base64
import binascii
import secrets
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Configuracion
from app.modules.iam.application.ports import MfaNoDisponible, SecretoMfaInvalido
from app.modules.iam.domain.mfa import aad_secreto

LARGO_NONCE = 12
LARGO_KEK = 32


class CifradorMfaKek:
    __slots__ = ("_kek", "_version")

    def __init__(self, kek: bytes, kek_version: int) -> None:
        if len(kek) != LARGO_KEK:
            raise MfaNoDisponible("la KEK no tiene 32 bytes")
        if not 1 <= kek_version <= 255:
            raise ValueError("KEK_VERSION fuera del rango del secreto de MFA")
        self._kek = kek
        self._version = kek_version

    def __repr__(self) -> str:
        return f"CifradorMfaKek(kek_version={self._version})"

    __str__ = __repr__

    def cifrar(self, secreto: bytes, usuario_id: uuid.UUID) -> bytes:
        nonce = secrets.token_bytes(LARGO_NONCE)
        cifrado = AESGCM(self._kek).encrypt(nonce, secreto, aad_secreto(usuario_id))
        return bytes([self._version]) + nonce + cifrado

    def descifrar(self, cifrado: bytes, usuario_id: uuid.UUID) -> bytes:
        if len(cifrado) < 1 + LARGO_NONCE + 16 or cifrado[0] != self._version:
            raise SecretoMfaInvalido("el secreto de MFA no corresponde a la KEK configurada")
        secreto: bytes | None
        try:
            secreto = AESGCM(self._kek).decrypt(cifrado[1:1 + LARGO_NONCE], cifrado[1 + LARGO_NONCE:],
                                                aad_secreto(usuario_id))
        except InvalidTag:
            secreto = None
        if secreto is None:
            raise SecretoMfaInvalido("el secreto de MFA no corresponde a la KEK configurada")
        return secreto


def cifrador_de(config: Configuracion) -> CifradorMfaKek | None:
    """El cifrador con la KEK de la configuración, o None si la custodia está apagada (la entrada de operación responde
    503 y el alta no corre). La configuración ya validó el entorno y el largo de la KEK."""
    if config.custodia_kek != "entorno_sintetico" or config.kek_entorno is None:
        return None
    try:
        kek = base64.b64decode(config.kek_entorno.get_secret_value(), validate=True)
    except (binascii.Error, ValueError):
        kek = b""
    if len(kek) != LARGO_KEK:
        return None
    return CifradorMfaKek(kek, config.kek_version)

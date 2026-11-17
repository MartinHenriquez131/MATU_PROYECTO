"""Las notas de operación cifradas (MATU-81, opción B de Jorge del 17-11, decisión 471).

Lo que el equipo de MATU anota de un pedido (la ``descripcion`` y la ``resolucion`` de una incidencia) se guarda cifrado
con AES-256-GCM y una clave propia de las notas (DEK), una vigente por persona cuidada, guardada en ``clave_notas``
envuelta con la misma KEK de la ficha. Nunca con ``clave_datos``: operación no alcanza la clave de la ficha
(arquitectura §11.2 y defecto 2 de la §12.8). Vive en shared porque la usan backoffice (la consola) y payments (la copia
de los datos), y ninguno de los dos importa care_plan.

- AAD = ``incidencia:<id>:descripcion`` o ``incidencia:<id>:resolucion``. Mover un texto cifrado a otra incidencia o al
  otro campo cambia el AAD y no se descifra.
- Lo guardado es ``nonce (12) || texto cifrado con su etiqueta (16)``. Un nonce al azar por cifrado.
- La DEK se envuelve con AES Key Wrap (RFC 3394) y la KEK de la configuración, como CustodiaKekEntorno de care_plan:
  40 bytes en ``clave_notas.dek_cifrada_con_kek``. La KEK solo existe con ``CUSTODIA_KEK=entorno_sintetico`` (local,
  pruebas o staging; la configuración no carga en otro entorno).
- El largo de 1 a 500 caracteres se valida aquí, sobre el texto, antes de cifrar (la base valida el largo cifrado).
- Ningún error lleva el texto, la clave ni un valor recibido: los mensajes son fijos. El repr oculta la KEK.
"""

import base64
import binascii
import secrets
import uuid
from typing import Literal

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.keywrap import InvalidUnwrap, aes_key_unwrap, aes_key_wrap

from app.core.config import Configuracion, obtener_configuracion

LARGO_MINIMO_NOTA = 1
LARGO_MAXIMO_NOTA = 500
LARGO_DEK = 32
LARGO_KEK = 32
LARGO_NONCE = 12
LARGO_TAG = 16

Campo = Literal["descripcion", "resolucion"]


class NotaInvalida(ValueError):
    """La nota no tiene de 1 a 500 caracteres. El mensaje es fijo: nunca lleva el texto."""

    def __init__(self) -> None:
        super().__init__("la nota debe tener de 1 a 500 caracteres")


class NotasNoDisponibles(RuntimeError):
    """No hay KEK para las notas, o no envuelve la clave nueva. El mensaje es fijo."""

    def __init__(self) -> None:
        super().__init__("las notas de operación no se pueden cifrar")


def validar_nota(texto: str) -> str:
    """El texto, si tiene de 1 a 500 caracteres. Si no, NotaInvalida."""
    if not LARGO_MINIMO_NOTA <= len(texto) <= LARGO_MAXIMO_NOTA:
        raise NotaInvalida()
    return texto


def aad_nota(incidencia_id: uuid.UUID, campo: Campo) -> bytes:
    if campo not in ("descripcion", "resolucion"):
        raise ValueError("campo desconocido")
    return f"incidencia:{incidencia_id}:{campo}".encode("ascii")


def cifrar_nota(dek: bytes, incidencia_id: uuid.UUID, campo: Campo, texto: str) -> bytes:
    """``nonce || cifrado``, con el texto ya validado (1 a 500 caracteres)."""
    validar_nota(texto)
    nonce = secrets.token_bytes(LARGO_NONCE)
    return nonce + AESGCM(dek).encrypt(nonce, texto.encode("utf-8"), aad_nota(incidencia_id, campo))


def descifrar_nota(dek: bytes | None, incidencia_id: uuid.UUID, campo: Campo, cifrado: bytes | None) -> str | None:
    """El texto, o None si no hay clave (destruida o sin custodia), no hay cifrado, o no corresponde (alterado, movido
    o de otra clave). Nunca lanza: la nota se muestra como no disponible."""
    if dek is None or cifrado is None or len(cifrado) < LARGO_NONCE + LARGO_TAG + 1:
        return None
    try:
        claro = AESGCM(dek).decrypt(cifrado[:LARGO_NONCE], cifrado[LARGO_NONCE:], aad_nota(incidencia_id, campo))
    except (InvalidTag, ValueError):
        return None
    try:
        return claro.decode("utf-8")
    except UnicodeDecodeError:
        return None


class CustodiaNotas:
    """Envuelve y desenvuelve la clave de las notas con la KEK. Una sola versión, la de la configuración."""

    __slots__ = ("_kek", "_kek_version")

    def __init__(self, kek: bytes, kek_version: int) -> None:
        if len(kek) != LARGO_KEK:
            raise NotasNoDisponibles()
        if kek_version < 1:
            raise ValueError("KEK_VERSION debe ser un entero positivo")
        self._kek = kek
        self._kek_version = kek_version

    def __repr__(self) -> str:
        return f"CustodiaNotas(kek_version={self._kek_version})"

    __str__ = __repr__

    @property
    def kek_version(self) -> int:
        return self._kek_version

    def nueva_dek(self) -> tuple[bytes, bytes]:
        """Una DEK nueva al azar y su envoltura con la KEK (40 bytes)."""
        dek = secrets.token_bytes(LARGO_DEK)
        return dek, aes_key_wrap(self._kek, dek)

    def desenvolver(self, envuelta: bytes, kek_version: int) -> bytes | None:
        """La DEK, o None si es de otra versión de KEK o no corresponde a esta. Nunca lanza."""
        if kek_version != self._kek_version:
            return None
        try:
            dek = aes_key_unwrap(self._kek, envuelta)
        except (InvalidUnwrap, ValueError):
            return None
        return dek if len(dek) == LARGO_DEK else None


def custodia_notas_de(config: Configuracion) -> CustodiaNotas | None:
    """La custodia con la KEK de la configuración, o None si está apagada. La configuración ya validó el entorno y el
    largo de la KEK (como cifrador_de del segundo factor)."""
    if config.custodia_kek != "entorno_sintetico" or config.kek_entorno is None:
        return None
    try:
        kek = base64.b64decode(config.kek_entorno.get_secret_value(), validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(kek) != LARGO_KEK:
        return None
    return CustodiaNotas(kek, config.kek_version)


def obtener_custodia_notas() -> CustodiaNotas | None:
    """Dependencia de FastAPI de la consola y de la copia de los datos. Las pruebas la sobreescriben."""
    return custodia_notas_de(obtener_configuracion())

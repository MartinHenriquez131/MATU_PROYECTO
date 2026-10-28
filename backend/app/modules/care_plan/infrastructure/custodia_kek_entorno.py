"""Adaptador del puerto CustodiaClaves con la KEK en una variable de entorno (decisión D-A de Jorge, 28-10).

**Desvío explícito del ADR-016, solo para el semestre y solo con datos sintéticos.**

Limitación (arquitectura 11.4): el sobre-cifrado protege la ficha porque la clave maestra (KEK) vive
FUERA del servidor de aplicación, en una custodia que solo envuelve y desenvuelve. Aquí la KEK vive en
el entorno del mismo proceso que guarda las DEK envueltas: quien obtenga a la vez la base y el
entorno del servidor puede descifrar todas las fichas. Por eso este adaptador:

(a) Solo se construye con ENTORNO en {local, pruebas}, una lista permitida y no una prohibida: con
    produccion o cualquier otro valor lanza CustodiaNoPermitida, y la configuración ya impide que la
    API arranque (app/core/config.py).
(b) Se enciende explícitamente con CUSTODIA_KEK=entorno_sintetico. Sin KEK configurada, las rutas
    de la ficha responden 503 y fallan cerradas: nunca se genera una KEK al arrancar ni se usa el
    doble de pruebas (api/dependencias.py).
(c) La KEK son 32 bytes aleatorios en base64 (KEK_ENTORNO), como SecretStr, con largo validado y
    distinta de JWT_CLAVE y PEPPER_EMAIL. No sale del adaptador: no hay método que la devuelva, el
    repr la oculta y ningún error ni log la incluye. Nunca va en el repositorio ni en docker-compose;
    .env.example solo tiene un marcador.
(d) La versión de la KEK es fija y viene de la configuración (KEK_VERSION, 1 por omisión). Si la
    clave cambia sin cambiar la versión, desenvolver falla con DekCifradaInvalida, que el cifrador
    traduce a un error genérico: nunca se crea una DEK nueva (CifradorAesGcm, MATU-11).
(e) Al construirse (al arrancar la API) registra un WARNING fijo, sin la clave.

Envoltura: AES Key Wrap (RFC 3394, NIST SP 800-38F) con la KEK de 256 bits, no AES-GCM. Razones:
- Es el algoritmo hecho para envolver claves: determinista y sin nonce, así que no hay nonce que
  generar, guardar ni arriesgar a repetir con la misma KEK (en GCM, repetirlo rompe la autenticación).
- Trae su propio control de integridad (el valor inicial de 64 bits): una DEK envuelta alterada, o
  desenvuelta con otra KEK, falla con InvalidUnwrap y nunca entrega bytes erróneos.
- Lo que GCM ofrece de más, los datos asociados (AAD), no aplica: el puerto envolver(dek) no recibe
  contexto, y la versión de la KEK ya elige la clave.
La DEK de 32 bytes envuelta ocupa 40 bytes (dek_cifrada_con_kek).
"""

import base64
import binascii
import logging

from cryptography.hazmat.primitives.keywrap import InvalidUnwrap, aes_key_unwrap, aes_key_wrap
from pydantic import SecretStr

from app.modules.care_plan.application.ports import DekCifradaInvalida, DekEnvuelta, KekNoDisponible
from app.modules.care_plan.domain.cifrado import LARGO_DEK

log = logging.getLogger("matu.care_plan.custodia")

# Lista permitida, no prohibida: un entorno nuevo queda fuera hasta que se decida lo contrario
ENTORNOS_PERMITIDOS = frozenset({"local", "pruebas"})

LARGO_KEK = 32  # AES-256

AVISO_ARRANQUE = "KEK en variable de entorno: solo datos sintéticos"


class CustodiaNoPermitida(RuntimeError):
    """La custodia con KEK en variable de entorno no se construye en este entorno."""

    def __init__(self) -> None:
        super().__init__("la KEK en variable de entorno solo se admite con ENTORNO local o pruebas")


class KekInvalida(ValueError):
    """La KEK configurada no son 32 bytes en base64. El mensaje es fijo: nunca lleva la clave."""

    def __init__(self) -> None:
        super().__init__("KEK_ENTORNO debe ser una clave de 32 bytes aleatorios en base64")


def decodificar_kek(kek: SecretStr) -> bytes | None:
    """Los 32 bytes de la KEK, o None si no es base64 estricto o no tiene 32 bytes.

    No lanza: quien llama decide el error, con un mensaje fijo y fuera de un bloque except, para que
    ninguna excepción de base64 (que puede llevar parte del valor) quede encadenada.
    """
    try:
        crudo = base64.b64decode(kek.get_secret_value(), validate=True)
    except (binascii.Error, ValueError):
        return None
    return crudo if len(crudo) == LARGO_KEK else None


class CustodiaKekEntorno:
    """CustodiaClaves con una sola versión de KEK, leída de la configuración. Ver el docstring del módulo."""

    # Sin __dict__: ni vars() ni un volcado del objeto muestran la clave
    __slots__ = ("_kek", "_kek_version")

    def __init__(self, kek: SecretStr, *, kek_version: int, entorno: str) -> None:
        if entorno not in ENTORNOS_PERMITIDOS:
            raise CustodiaNoPermitida()
        if kek_version < 1:
            raise ValueError("KEK_VERSION debe ser un entero positivo")
        if decodificar_kek(kek) is None:
            raise KekInvalida()
        # Se guarda como SecretStr y se decodifica en cada uso: el repr de SecretStr la oculta
        self._kek = kek
        self._kek_version = kek_version
        log.warning(AVISO_ARRANQUE)

    def __repr__(self) -> str:
        return f"CustodiaKekEntorno(kek_version={self._kek_version})"

    __str__ = __repr__

    def _clave(self) -> bytes:
        clave = decodificar_kek(self._kek)
        if clave is None:  # pragma: no cover - validada al construir
            raise KekNoDisponible("la KEK no está disponible")
        return clave

    def envolver(self, dek: bytes) -> DekEnvuelta:
        if len(dek) != LARGO_DEK:
            raise ValueError(f"La DEK debe tener {LARGO_DEK} bytes")
        return DekEnvuelta(dek_cifrada=aes_key_wrap(self._clave(), dek), kek_version=self._kek_version)

    def desenvolver(self, dek_cifrada: bytes, kek_version: int) -> bytes:
        if kek_version != self._kek_version:
            # Otra versión de KEK nunca se reemplaza por la vigente: sería otra clave
            raise KekNoDisponible("la versión de KEK pedida no está en esta custodia")
        dek: bytes | None
        try:
            dek = aes_key_unwrap(self._clave(), dek_cifrada)
        except (InvalidUnwrap, ValueError):
            dek = None
        if dek is None or len(dek) != LARGO_DEK:
            # La KEK cambió sin cambiar KEK_VERSION, o la DEK envuelta fue alterada
            raise DekCifradaInvalida("la DEK cifrada no corresponde a la KEK configurada")
        return dek

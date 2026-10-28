"""Adaptador del puerto CifradorSecciones con AES-256-GCM (MATU-11, ADR-014, ADR-016).

Cada sección se cifra con la DEK de la persona cuidada, que se guarda envuelta con la KEK de la
custodia (puerto CustodiaClaves) en clave_datos.

- Nonce: 12 bytes de os.urandom en cada escritura. Nunca un contador ni el reloj.
- AAD: plan_id ‖ tipo (domain/cifrado.py).
- La DEK en claro es una variable local de cada llamada: no hay caché, ni Redis, ni contexto de
  petición, y nunca se serializa.
- Los errores de la biblioteca y de la custodia se traducen a errores de dominio con mensaje fijo,
  y se lanzan fuera del bloque except: la excepción original no queda encadenada ni como causa
  ni como contexto (un UnicodeDecodeError, por ejemplo, lleva los bytes que no pudo leer).
- Los logs solo dicen qué pasó, con un mensaje fijo: nunca el texto, la DEK ni identificadores.
"""

import logging
import os
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.modules.care_plan.application.ports import (
    CustodiaClaves,
    DekCifradaInvalida,
    DekEnvuelta,
    KekNoDisponible,
    RepositorioClaves,
)
from app.modules.care_plan.domain.cifrado import (
    LARGO_DEK,
    LARGO_NONCE,
    LARGO_TAG,
    ClaveGuardada,
    ClaveNoDisponible,
    SeccionCifrada,
    SeccionIlegible,
    clave_para_escribir,
    clave_para_leer,
    datos_asociados,
)

log = logging.getLogger("matu.care_plan.cifrado")


class CifradorAesGcm:
    """Se arma por petición, con el repositorio de la sesión de esa petición: así crear la DEK y
    escribir la primera sección quedan en la misma transacción."""

    def __init__(self, custodia: CustodiaClaves, claves: RepositorioClaves) -> None:
        self._custodia = custodia
        self._claves = claves

    def cifrar(
        self, *, grupo_id: uuid.UUID, persona_cuidada_id: uuid.UUID, plan_id: uuid.UUID, tipo: str, texto: str
    ) -> SeccionCifrada:
        aad = datos_asociados(plan_id, tipo)
        clave = clave_para_escribir(self._claves.obtener(persona_cuidada_id, para_escribir=True))
        if clave is None:
            dek, kek_version = self._crear_dek(grupo_id, persona_cuidada_id)
        else:
            dek, kek_version = self._desenvolver(clave), clave.kek_version
        nonce = os.urandom(LARGO_NONCE)
        sellado = AESGCM(dek).encrypt(nonce, texto.encode("utf-8"), aad)
        # cryptography devuelve el texto cifrado seguido del tag de 16 bytes
        return SeccionCifrada(
            contenido_cifrado=sellado[:-LARGO_TAG],
            nonce=nonce,
            tag_auth=sellado[-LARGO_TAG:],
            kek_version=kek_version,
        )

    def descifrar(
        self, *, persona_cuidada_id: uuid.UUID, plan_id: uuid.UUID, tipo: str, seccion: SeccionCifrada
    ) -> str:
        aad = datos_asociados(plan_id, tipo)
        clave = clave_para_leer(self._claves.obtener(persona_cuidada_id))
        # Se descifra con la DEK vigente de clave_datos. seccion.kek_version solo registra con qué
        # versión de KEK estaba envuelta al escribir: la DEK no cambia cuando la KEK rota.
        texto = _abrir(self._desenvolver(clave), seccion, aad)
        if texto is None:
            log.warning("sección ilegible")
            raise SeccionIlegible()
        return texto

    def _crear_dek(self, grupo_id: uuid.UUID, persona_cuidada_id: uuid.UUID) -> tuple[bytes, int]:
        """Primera escritura de la ficha: genera la DEK, la envuelve y la guarda.

        Si otra transacción la creó primero, se usa la de ella (vigente) o se falla (destruida):
        nunca quedan dos DEK para la misma persona.
        """
        dek = AESGCM.generate_key(bit_length=LARGO_DEK * 8)
        envuelta: DekEnvuelta | None
        try:
            envuelta = self._custodia.envolver(dek)
        except KekNoDisponible:
            envuelta = None
        if envuelta is None:
            log.warning("la custodia no envolvió la clave de datos")
            raise ClaveNoDisponible()
        if self._claves.crear(grupo_id, persona_cuidada_id, envuelta):
            log.info("clave de datos creada")
            return dek, envuelta.kek_version
        ganadora = clave_para_escribir(self._claves.obtener(persona_cuidada_id, para_escribir=True))
        if ganadora is None:
            # crear() no escribió porque había una fila, y ahora no se ve: no se inventa otra
            raise ClaveNoDisponible()
        return self._desenvolver(ganadora), ganadora.kek_version

    def _desenvolver(self, clave: ClaveGuardada) -> bytes:
        if clave.dek_cifrada is None:  # clave_para_escribir y clave_para_leer ya lo descartan
            raise ClaveNoDisponible()
        dek: bytes | None
        try:
            dek = self._custodia.desenvolver(clave.dek_cifrada, clave.kek_version)
        except (KekNoDisponible, DekCifradaInvalida):
            dek = None
        if dek is None or len(dek) != LARGO_DEK:
            log.warning("la custodia no desenvolvió la clave de datos")
            raise ClaveNoDisponible()
        return dek


def _abrir(dek: bytes, seccion: SeccionCifrada, aad: bytes) -> str | None:
    """El texto de la sección, o None si no se autentica (alterada, movida o de otra clave)."""
    try:
        return AESGCM(dek).decrypt(seccion.nonce, seccion.contenido_cifrado + seccion.tag_auth, aad).decode("utf-8")
    except (InvalidTag, UnicodeDecodeError):
        return None

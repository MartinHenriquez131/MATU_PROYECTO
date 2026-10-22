"""Doble del puerto CustodiaClaves.

No cifra: guarda cada DEK en memoria, bajo la versión de KEK vigente, detrás de un
identificador aleatorio que hace de "DEK cifrada". Basta para probar el contrato del
sobre-cifrado (ida y vuelta, rotación de la KEK y borrado criptográfico) sin un servicio
de custodia. Solo existe en las pruebas.
"""

import secrets

from app.modules.care_plan.application.ports import DekCifradaInvalida, DekEnvuelta, KekNoDisponible

LARGO_DEK = 32  # AES-256


class CustodiaEnMemoria:
    def __init__(self) -> None:
        self._ultima_version = 1
        self._version_vigente: int | None = 1
        # versión de KEK → (DEK cifrada → DEK)
        self._por_version: dict[int, dict[bytes, bytes]] = {1: {}}

    @property
    def version_vigente(self) -> int | None:
        return self._version_vigente

    def envolver(self, dek: bytes) -> DekEnvuelta:
        if len(dek) != LARGO_DEK:
            raise ValueError(f"La DEK debe tener {LARGO_DEK} bytes")
        if self._version_vigente is None:
            raise KekNoDisponible("No hay una versión de KEK vigente")
        dek_cifrada = secrets.token_bytes(LARGO_DEK + 16)
        self._por_version[self._version_vigente][dek_cifrada] = bytes(dek)
        return DekEnvuelta(dek_cifrada=dek_cifrada, kek_version=self._version_vigente)

    def desenvolver(self, dek_cifrada: bytes, kek_version: int) -> bytes:
        deks = self._por_version.get(kek_version)
        if deks is None:
            raise KekNoDisponible(f"La versión {kek_version} de la KEK no existe o fue destruida")
        try:
            return deks[dek_cifrada]
        except KeyError:
            raise DekCifradaInvalida(f"La DEK cifrada no corresponde a la versión {kek_version}") from None

    def rotar(self) -> int:
        """Crea una nueva versión de KEK y la deja vigente. Las anteriores siguen desenvolviendo."""
        self._ultima_version += 1
        self._por_version[self._ultima_version] = {}
        self._version_vigente = self._ultima_version
        return self._ultima_version

    def destruir(self, kek_version: int) -> None:
        """Destruye una versión de KEK: todo lo que envolvió queda ilegible para siempre."""
        if kek_version not in self._por_version:
            raise KekNoDisponible(f"La versión {kek_version} de la KEK no existe o fue destruida")
        del self._por_version[kek_version]
        if self._version_vigente == kek_version:
            self._version_vigente = None

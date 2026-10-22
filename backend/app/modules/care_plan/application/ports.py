"""Puertos del módulo care_plan (ADR-021).

CustodiaClaves es el primer nivel del sobre-cifrado de la ficha (arquitectura 11.4, ADR-014
y ADR-016): la clave maestra (KEK) vive fuera del servidor de aplicación y solo se usa para
envolver y desenvolver la clave de datos (DEK) de cada persona cuidada. La DEK envuelta y la
versión de KEK que la envolvió se guardan en clave_datos (dek_cifrada_con_kek, kek_version).

Implementaciones: CustodiaEnMemoria (tests/dobles). El adaptador real llega cuando se decida
el proveedor de custodia (ADR-019).
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DekEnvuelta:
    """Una DEK cifrada con la KEK, tal como se guarda en clave_datos."""

    dek_cifrada: bytes
    kek_version: int


class KekNoDisponible(Exception):
    """La versión de KEK pedida no existe o fue destruida.

    Nunca se responde generando una clave de reemplazo: eso rompería el borrado criptográfico.
    """


class DekCifradaInvalida(Exception):
    """La DEK cifrada no corresponde a la versión de KEK indicada, o fue alterada."""


class CustodiaClaves(Protocol):
    """Custodia de la clave maestra. La KEK nunca sale de la custodia: solo envuelve y desenvuelve."""

    def envolver(self, dek: bytes) -> DekEnvuelta:
        """Cifra la DEK con la versión vigente de la KEK y devuelve la DEK cifrada con esa versión.

        Lanza KekNoDisponible si no hay una KEK vigente.
        """
        ...

    def desenvolver(self, dek_cifrada: bytes, kek_version: int) -> bytes:
        """Descifra la DEK con la versión de KEK con que fue envuelta.

        Lanza KekNoDisponible si esa versión no existe o fue destruida, y DekCifradaInvalida
        si la DEK cifrada no corresponde a esa versión.
        """
        ...

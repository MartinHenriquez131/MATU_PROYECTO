"""Doble del puerto RepositorioClaves: las filas de clave_datos en un diccionario.

Reproduce lo que el adaptador SQL hereda de la base: una fila por persona (UNIQUE de
persona_cuidada_id, crear() devuelve False si ya existe) y la DEK NULL junto con la marca de
destrucción. destruir() existe solo aquí, para las pruebas: la aplicación no tiene cómo destruir
una clave todavía (lo deciden Jorge y Martín más adelante).
"""

import uuid
from dataclasses import dataclass

from app.modules.care_plan.application.ports import DekEnvuelta
from app.modules.care_plan.domain.cifrado import ClaveGuardada


@dataclass
class FilaClave:
    grupo_id: uuid.UUID
    dek_cifrada: bytes | None
    kek_version: int


class RepositorioClavesEnMemoria:
    def __init__(self) -> None:
        self.filas: dict[uuid.UUID, FilaClave] = {}
        self.creaciones = 0

    def obtener(self, persona_cuidada_id: uuid.UUID, *, para_escribir: bool = False) -> ClaveGuardada | None:
        fila = self.filas.get(persona_cuidada_id)
        if fila is None:
            return None
        return ClaveGuardada(kek_version=fila.kek_version, dek_cifrada=fila.dek_cifrada)

    def crear(self, grupo_id: uuid.UUID, persona_cuidada_id: uuid.UUID, envuelta: DekEnvuelta) -> bool:
        if persona_cuidada_id in self.filas:
            return False
        self.filas[persona_cuidada_id] = FilaClave(grupo_id, envuelta.dek_cifrada, envuelta.kek_version)
        self.creaciones += 1
        return True

    def destruir(self, persona_cuidada_id: uuid.UUID) -> None:
        """Borrado criptográfico: la DEK envuelta se pierde y la fila se queda."""
        self.filas[persona_cuidada_id].dek_cifrada = None

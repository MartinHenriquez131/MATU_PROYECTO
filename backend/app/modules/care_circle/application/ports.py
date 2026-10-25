"""Puertos del módulo care_circle (ADR-021)."""

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class NuevoGrupo:
    id: uuid.UUID
    nombre: str
    creado_por: uuid.UUID


@dataclass(frozen=True)
class GrupoDelUsuario:
    """Un grupo en el que el usuario tiene una membresía activa, con su rol en él."""

    id: uuid.UUID
    nombre: str
    rol: str


class RepositorioGrupos(Protocol):
    """Persistencia de grupo_familiar y membresia.

    Implementación: RepositorioGruposSQL (infrastructure/repositorio_grupos.py).
    """

    def crear(self, grupo: NuevoGrupo) -> None:
        """Guarda el grupo y la membresía admin activa de su creador en una sola transacción.

        Si la membresía falla, no queda el grupo: la excepción sigue y la transacción se deshace.
        """
        ...

    def listar(self, usuario_id: uuid.UUID) -> list[GrupoDelUsuario]:
        """Los grupos donde el usuario tiene una membresía activa, del más antiguo al más nuevo."""
        ...

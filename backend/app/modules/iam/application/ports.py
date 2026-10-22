"""Puertos del módulo iam (ADR-021)."""

import uuid
from dataclasses import dataclass
from typing import Protocol


class HasherContrasenas(Protocol):
    """Hash de contraseñas con Argon2id (arquitectura, sección 11.6).

    Implementación: HasherArgon2id (infrastructure/hasher_argon2.py).
    """

    def hashear(self, contrasena: str) -> str:
        """Devuelve el hash en formato PHC ($argon2id$...), con su sal y sus parámetros."""
        ...

    def verificar(self, hash_guardado: str, contrasena: str) -> bool:
        """True si la contraseña corresponde al hash. Nunca lanza por una contraseña incorrecta."""
        ...


@dataclass(frozen=True)
class NuevoUsuario:
    id: uuid.UUID
    nombre: str
    email: str
    password_hash: str
    email_hash: bytes


class RepositorioUsuarios(Protocol):
    """Persistencia de usuario e indice_credencial.

    Implementación: RepositorioUsuariosSQL (infrastructure/repositorio_usuarios.py).
    """

    def crear(self, usuario: NuevoUsuario) -> None:
        """Guarda el usuario y su fila de indice_credencial en una sola transacción.

        Lanza EmailYaRegistrado si el email ya tiene una cuenta. En ese caso no queda nada guardado.
        """
        ...

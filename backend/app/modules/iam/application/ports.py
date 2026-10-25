"""Puertos del módulo iam (ADR-021)."""

import uuid
from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class CredencialGuardada:
    """Lo que el login necesita de una cuenta: su id, el hash de su contraseña y su estado."""

    usuario_id: uuid.UUID
    password_hash: str
    estado: str


class RepositorioUsuarios(Protocol):
    """Persistencia de usuario e indice_credencial.

    Implementación: RepositorioUsuariosSQL (infrastructure/repositorio_usuarios.py).
    """

    def crear(self, usuario: NuevoUsuario) -> None:
        """Guarda el usuario y su fila de indice_credencial en una sola transacción.

        Lanza EmailYaRegistrado si el email ya tiene una cuenta. En ese caso no queda nada guardado.
        """
        ...

    def buscar_credencial(self, email_hash: bytes) -> CredencialGuardada | None:
        """Resuelve el usuario por indice_credencial y lee su hash y su estado.

        Primero busca en indice_credencial (sin RLS) y después fija app.usuario_id para leer la
        fila de usuario, que la política usuario_propio solo muestra a su dueño. None si el email
        no tiene cuenta.
        """
        ...


@dataclass(frozen=True)
class ClaimsAcceso:
    """Los claims de un access token ya verificado. Los instantes van con zona horaria UTC."""

    sub: uuid.UUID
    iat: datetime
    exp: datetime


class EmisorTokens(Protocol):
    """Firma y lectura de los access tokens (JWT HS256).

    Implementación: EmisorJWT (infrastructure/tokens_jwt.py).
    """

    def emitir(self, usuario_id: uuid.UUID, emitido_en: datetime, expira_en: datetime) -> str:
        """Devuelve el token firmado con sub, iat y exp."""
        ...

    def leer(self, token: str) -> ClaimsAcceso:
        """Verifica firma, algoritmo y formato, y devuelve los claims.

        No decide el vencimiento: eso lo hace validar_acceso con el Reloj. Lanza TokenInvalido
        si la firma, el algoritmo o el formato fallan.
        """
        ...

"""Adaptador del puerto HasherContrasenas con argon2-cffi.

Usa los parámetros por omisión de argon2-cffi, que siguen el perfil recomendado de bajo uso
de memoria del RFC 9106 (Argon2id, 3 pasadas, 64 MiB, 4 hilos). El hash guarda sus
parámetros, así que subirlos más adelante no invalida las contraseñas ya guardadas.
"""

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError


class HasherArgon2id:
    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self._hasher = hasher or PasswordHasher(type=Type.ID)

    def hashear(self, contrasena: str) -> str:
        return self._hasher.hash(contrasena)

    def verificar(self, hash_guardado: str, contrasena: str) -> bool:
        try:
            return self._hasher.verify(hash_guardado, contrasena)
        except (VerificationError, InvalidHashError):
            return False

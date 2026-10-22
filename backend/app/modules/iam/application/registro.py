"""Caso de uso: crear una cuenta (MATU-04, RF-37)."""

import uuid
from dataclasses import dataclass

from app.modules.iam.application.ports import HasherContrasenas, NuevoUsuario, RepositorioUsuarios
from app.modules.iam.domain.credenciales import indice_email, normalizar_email


@dataclass(frozen=True)
class CuentaCreada:
    id: uuid.UUID
    nombre: str
    email: str


def registrar_usuario(
    *,
    nombre: str,
    email: str,
    contrasena: str,
    pepper: bytes,
    hasher: HasherContrasenas,
    repositorio: RepositorioUsuarios,
) -> CuentaCreada:
    """Crea la cuenta y su fila de indice_credencial.

    El identificador se genera aquí y no en la base: la política RLS de usuario exige que la
    fila nueva sea la del usuario en contexto (id = app.usuario_id), y para fijar ese contexto
    hay que conocer el id antes del INSERT.

    Lanza EmailYaRegistrado si el email ya tiene una cuenta.
    """
    email_normalizado = normalizar_email(email)
    nuevo = NuevoUsuario(
        id=uuid.uuid4(),
        nombre=nombre.strip(),
        email=email_normalizado,
        password_hash=hasher.hashear(contrasena),
        email_hash=indice_email(pepper, email_normalizado),
    )
    repositorio.crear(nuevo)
    return CuentaCreada(id=nuevo.id, nombre=nuevo.nombre, email=nuevo.email)

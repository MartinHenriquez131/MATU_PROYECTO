"""Casos de uso: crear el grupo familiar y listar los grupos del usuario (MATU-06, RF-38)."""

import uuid
from dataclasses import dataclass

from app.modules.care_circle.application.ports import GrupoDelUsuario, NuevoGrupo, RepositorioGrupos
from app.modules.care_circle.domain.grupos import ROL_FUNDADOR, normalizar_nombre


@dataclass(frozen=True)
class GrupoCreado:
    id: uuid.UUID
    nombre: str
    rol: str


def crear_grupo(usuario_id: uuid.UUID, nombre: str, repositorio: RepositorioGrupos) -> GrupoCreado:
    """Crea el grupo y deja a quien lo crea como admin, en la misma transacción.

    El identificador se genera aquí y no en la base: con RLS, un INSERT ... RETURNING del grupo
    devuelve cero filas mientras no exista la membresía, y la membresía necesita ese id.

    Lanza NombreGrupoInvalido si el nombre, sin espacios en los extremos, no tiene 1 a 80 caracteres.
    """
    nuevo = NuevoGrupo(id=uuid.uuid4(), nombre=normalizar_nombre(nombre), creado_por=usuario_id)
    repositorio.crear(nuevo)
    return GrupoCreado(id=nuevo.id, nombre=nuevo.nombre, rol=ROL_FUNDADOR)


def listar_grupos(usuario_id: uuid.UUID, repositorio: RepositorioGrupos) -> list[GrupoDelUsuario]:
    """Los grupos donde el usuario es miembro activo, y ningún otro."""
    return repositorio.listar(usuario_id)

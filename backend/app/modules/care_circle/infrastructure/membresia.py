"""Consultas de membresía que la API necesita antes de entregar un contexto de grupo."""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

_MEMBRESIA_ACTIVA = text(
    "SELECT rol, puede_ver_plan FROM membresia"
    " WHERE grupo_id = :grupo_id AND usuario_id = :usuario_id AND estado = 'activa'"
)


@dataclass(frozen=True)
class MembresiaActiva:
    rol: str
    # Permiso explícito del pagador para ver el plan de cuidado (MATU-12). Siempre False para los
    # demás roles: el CHECK membresia_permiso_plan lo amarra al rol pagador.
    puede_ver_plan: bool


def membresia_activa(sesion: Session, usuario_id: uuid.UUID, grupo_id: uuid.UUID) -> MembresiaActiva | None:
    """La membresía activa del usuario en el grupo, o None si no es miembro activo.

    Corre dentro del contexto de sesion_tenant, con app.usuario_id ya fijado: la política
    membresia_propia deja ver las membresías propias. Un grupo inexistente, una membresía
    suspendida o retirada y la ausencia de membresía dan el mismo None.
    """
    fila = sesion.execute(_MEMBRESIA_ACTIVA, {"grupo_id": grupo_id, "usuario_id": usuario_id}).first()
    if fila is None:
        return None
    return MembresiaActiva(rol=str(fila.rol), puede_ver_plan=bool(fila.puede_ver_plan))


def rol_activo(sesion: Session, usuario_id: uuid.UUID, grupo_id: uuid.UUID) -> str | None:
    """El rol del usuario en el grupo si es miembro activo, o None si no lo es."""
    membresia = membresia_activa(sesion, usuario_id, grupo_id)
    return None if membresia is None else membresia.rol

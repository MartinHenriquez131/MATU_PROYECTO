"""Consultas de membresía que la API necesita antes de entregar un contexto de grupo."""

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

_ROL_ACTIVO = text(
    "SELECT rol FROM membresia WHERE grupo_id = :grupo_id AND usuario_id = :usuario_id AND estado = 'activa'"
)


def rol_activo(sesion: Session, usuario_id: uuid.UUID, grupo_id: uuid.UUID) -> str | None:
    """El rol del usuario en el grupo si es miembro activo, o None si no lo es.

    Corre dentro del contexto de sesion_tenant, con app.usuario_id ya fijado: la política
    membresia_propia deja ver las membresías propias. Un grupo inexistente, una membresía
    suspendida o retirada y la ausencia de membresía dan el mismo None.
    """
    fila = sesion.execute(_ROL_ACTIVO, {"grupo_id": grupo_id, "usuario_id": usuario_id}).first()
    return None if fila is None else str(fila.rol)


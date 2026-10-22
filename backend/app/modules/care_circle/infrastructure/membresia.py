"""Consultas de membresía que la API necesita antes de entregar un contexto de grupo."""

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

_MIEMBRO_ACTIVO = text(
    "SELECT 1 FROM membresia WHERE grupo_id = :grupo_id AND usuario_id = :usuario_id AND estado = 'activa'"
)


def es_miembro_activo(sesion: Session, usuario_id: uuid.UUID, grupo_id: uuid.UUID) -> bool:
    """True si el usuario es miembro activo del grupo.

    Corre dentro del contexto de sesion_tenant, con app.usuario_id ya fijado: la política
    membresia_propia deja ver las membresías propias. Un grupo inexistente, una membresía
    suspendida o retirada y la ausencia de membresía dan el mismo False.
    """
    fila = sesion.execute(_MIEMBRO_ACTIVO, {"grupo_id": grupo_id, "usuario_id": usuario_id}).first()
    return fila is not None

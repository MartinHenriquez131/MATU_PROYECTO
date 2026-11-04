"""El puerto RepositorioPreferencias sobre PostgreSQL (MATU-41, decisión 111).

Corre en la sesión del propio usuario (sesion_de_usuario: solo app.usuario_id). preferencia_propia deja
leer y escribir solo las filas de esa persona; membresia_propia, solo sus membresías. Sin política nueva.
"""

import uuid
from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.notifications.domain.aviso import CANALES, Canal

_GUARDADAS = text(
    "SELECT canal, activo FROM preferencia_notificacion"
    " WHERE usuario_id = :usuario AND tipo_evento = :tipo AND canal IN ('correo', 'push')"
)
_ROLES = text("SELECT DISTINCT rol FROM membresia WHERE usuario_id = :usuario AND estado = 'activa'")
_GUARDAR = text(
    "INSERT INTO preferencia_notificacion (usuario_id, tipo_evento, canal, activo)"
    " VALUES (:usuario, :tipo, :canal, :activo)"
    " ON CONFLICT (usuario_id, tipo_evento, canal) DO UPDATE SET activo = EXCLUDED.activo"
)


class RepositorioPreferenciasSQL:
    def __init__(self, sesion: Session) -> None:
        self._sesion = sesion

    def __repr__(self) -> str:
        return "RepositorioPreferenciasSQL()"

    def guardadas(self, usuario_id: uuid.UUID, tipo_evento: str) -> dict[Canal, bool]:
        filas = self._sesion.execute(_GUARDADAS, {"usuario": usuario_id, "tipo": tipo_evento}).all()
        return {Canal(f.canal): bool(f.activo) for f in filas}

    def roles_activos(self, usuario_id: uuid.UUID) -> set[str]:
        return {str(f.rol) for f in self._sesion.execute(_ROLES, {"usuario": usuario_id}).all()}

    def guardar(self, usuario_id: uuid.UUID, tipo_evento: str, valores: Mapping[Canal, bool]) -> None:
        self._sesion.execute(
            _GUARDAR,
            [
                {"usuario": usuario_id, "tipo": tipo_evento, "canal": canal.value, "activo": valores[canal]}
                for canal in CANALES
            ],
        )

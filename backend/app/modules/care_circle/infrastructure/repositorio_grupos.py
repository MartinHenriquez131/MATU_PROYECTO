"""Adaptador SQL del puerto RepositorioGrupos (MATU-06, RF-38)."""

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import sesion_tenant
from app.modules.care_circle.application.ports import GrupoDelUsuario, NuevoGrupo
from app.modules.care_circle.domain.grupos import ROL_FUNDADOR

# Sin RETURNING: con RLS, la fila nueva aún no es visible para el creador por grupo_mis_grupos, y
# el id ya se conoce porque lo generó la aplicación
_INSERTAR_GRUPO = text("INSERT INTO grupo_familiar (id, nombre, creado_por) VALUES (:id, :nombre, :creado_por)")

# El estado queda en su valor por omisión, 'activa'
_INSERTAR_MEMBRESIA = text("INSERT INTO membresia (grupo_id, usuario_id, rol) VALUES (:grupo_id, :usuario_id, :rol)")

# Filtra por membresía activa de forma explícita: la política grupo_creador_ver deja ver al creador
# su grupo aunque se haya retirado de él, y ese grupo no debe aparecer en su lista
_LISTAR = text(
    "SELECT g.id, g.nombre, m.rol FROM grupo_familiar g"
    " JOIN membresia m ON m.grupo_id = g.id"
    " WHERE m.usuario_id = :usuario_id AND m.estado = 'activa'"
    " ORDER BY g.creado_en, g.id"
)


class RepositorioGruposSQL:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def crear(self, grupo: NuevoGrupo) -> None:
        # Una sola transacción con app.usuario_id del creador. grupo_crear exige
        # creado_por = app_usuario(), y membresia_fundador exige que el grupo sea suyo y el rol
        # admin. Si la membresía falla, sesion_tenant hace rollback y no queda el grupo.
        with sesion_tenant(self._fabrica, usuario_id=grupo.creado_por) as sesion:
            self._insertar_grupo(sesion, grupo)
            self._insertar_membresia(sesion, grupo)

    def listar(self, usuario_id: uuid.UUID) -> list[GrupoDelUsuario]:
        with sesion_tenant(self._fabrica, usuario_id=usuario_id) as sesion:
            filas = sesion.execute(_LISTAR, {"usuario_id": usuario_id}).all()
        return [GrupoDelUsuario(id=f.id, nombre=f.nombre, rol=f.rol) for f in filas]

    def _insertar_grupo(self, sesion: Session, grupo: NuevoGrupo) -> None:
        sesion.execute(_INSERTAR_GRUPO, {"id": grupo.id, "nombre": grupo.nombre, "creado_por": grupo.creado_por})

    def _insertar_membresia(self, sesion: Session, grupo: NuevoGrupo) -> None:
        sesion.execute(_INSERTAR_MEMBRESIA, {"grupo_id": grupo.id, "usuario_id": grupo.creado_por, "rol": ROL_FUNDADOR})

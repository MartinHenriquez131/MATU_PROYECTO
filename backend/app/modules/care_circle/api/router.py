"""Rutas de care_circle: crear el grupo familiar y listar los grupos del usuario (MATU-06, RF-38).

No usan X-Grupo-Id: crear un grupo y listar los propios no dependen de un grupo en contexto.
El nombre del grupo nunca se registra en los logs.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import obtener_fabrica_sesiones
from app.modules.care_circle.api.esquemas import GrupoRespuesta, SolicitudGrupo
from app.modules.care_circle.application.grupos import crear_grupo, listar_grupos
from app.modules.care_circle.application.ports import RepositorioGrupos
from app.modules.care_circle.infrastructure.repositorio_grupos import RepositorioGruposSQL
from app.modules.iam.api.dependencias import UsuarioActual, usuario_actual

router = APIRouter(tags=["grupos"])


def obtener_repositorio_grupos(
    fabrica: Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)],
) -> RepositorioGrupos:
    return RepositorioGruposSQL(fabrica)


@router.post("/grupos", status_code=status.HTTP_201_CREATED, response_model=GrupoRespuesta)
def crear(
    solicitud: SolicitudGrupo,
    usuario: Annotated[UsuarioActual, Depends(usuario_actual)],
    repositorio: Annotated[RepositorioGrupos, Depends(obtener_repositorio_grupos)],
) -> GrupoRespuesta:
    grupo = crear_grupo(usuario.id, solicitud.nombre, repositorio)
    return GrupoRespuesta(id=grupo.id, nombre=grupo.nombre, rol=grupo.rol)


@router.get("/grupos", response_model=list[GrupoRespuesta])
def listar(
    usuario: Annotated[UsuarioActual, Depends(usuario_actual)],
    repositorio: Annotated[RepositorioGrupos, Depends(obtener_repositorio_grupos)],
) -> list[GrupoRespuesta]:
    return [GrupoRespuesta(id=g.id, nombre=g.nombre, rol=g.rol) for g in listar_grupos(usuario.id, repositorio)]

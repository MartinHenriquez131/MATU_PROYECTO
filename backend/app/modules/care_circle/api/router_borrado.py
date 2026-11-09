"""Borrar los datos de la persona al tiro, cuando se pide (MATU-72, decisiones 149 a 157).

    POST /v1/personas-cuidadas/{persona_id}/borrado    admin y cuidador. 200

Contrato: docs/api/openapi.json y docs/api/README.md (decisiones 149 a 157). Sin cuerpo, con X-Grupo-Id. Orden
de evaluación: 401, 404 (membresía, rol, persona que no es UUID, no es del grupo o se eliminó sin borrado), 409
ya-borrada y 200. Cache-Control: no-store en todas las respuestas, por el middleware de /v1/personas-cuidadas/.

Todo corre en una sola transacción (sesion_de_grupo) y con un solo instante (RelojDetenido, decisión 124): la
marca de la persona, las revocaciones con motivo borrado, el corte de los enlaces, la clave destruida, las
secciones y los insumos borrados y su auditoría. Los efectos en la ficha y el consumo son los del retiro
(infrastructure/efectos_retiro.py). Nada de la persona va a los logs: ni su id, ni los contadores (C5).
"""

import logging
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.errores import ErrorMATU
from app.modules.care_circle.api.dependencias import ContextoGrupo, SesionDeGrupo
from app.modules.care_circle.api.router_autorizaciones import (
    Efectos,
    RegistroDep,
    RelojDep,
    Retiros,
)
from app.modules.care_circle.application.borrado import (
    RepositorioBorrado,
    RolSinPermisoBorrado,
    SolicitudBorrado,
    borrar_persona,
)
from app.modules.care_circle.application.retiro import EfectoNoDisponible
from app.modules.care_circle.domain.borrado import PersonaNoEncontrada, YaBorrada, puede_borrar
from app.modules.care_circle.infrastructure.repositorio_borrado import RepositorioBorradoSQL

log = logging.getLogger("matu.care_circle.borrado")

router = APIRouter(tags=["personas cuidadas"])

RUTA_BORRADO = "/personas-cuidadas/{persona_id}/borrado"

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}


class BorradoPersona(BaseModel):
    """Respuesta del borrado (decisión 152). Sin el nombre ni nada de la persona: los contadores van solo aquí."""

    model_config = ConfigDict(extra="forbid")

    persona_id: uuid.UUID
    borrado_en: datetime = Field(description="El instante del borrado, el mismo de toda su auditoría")
    enlaces_cortados: int = Field(ge=0, description="Accesos de relevo cortados: vigentes, bloqueados y en pausa")
    autorizaciones_retiradas: int = Field(ge=0, description="Autorizaciones no revocadas que se retiraron")


def contexto_que_borra(contexto: SesionDeGrupo) -> ContextoGrupo:
    """Borran admin y cuidador (D1). pagador y observador reciben 404, nunca 403."""
    if not puede_borrar(contexto.rol):
        raise ErrorMATU(404)
    return contexto


def obtener_repositorio_borrado(contexto: SesionDeGrupo, registro: RegistroDep) -> RepositorioBorrado:
    return RepositorioBorradoSQL(contexto.sesion, contexto.grupo_id, registro)


@router.post(
    RUTA_BORRADO,
    response_model=BorradoPersona,
    responses={
        401: {"description": "Falta el access token, o es inválido o vencido", **_PROBLEMA},
        404: {
            "description": "No miembro, rol que no alcanza (pagador u observador), persona de otro grupo, inexistente"
            " o eliminada sin borrado",
            **_PROBLEMA,
        },
        409: {"description": "/errores/ya-borrada: los datos de la persona ya se borraron", **_PROBLEMA},
    },
    summary="Borrar al tiro todo lo guardado de la persona y sacarla de MATU",
)
def borrar(
    request: Request,
    contexto: Annotated[ContextoGrupo, Depends(contexto_que_borra)],
    persona_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})],
    repositorio: Annotated[RepositorioBorrado, Depends(obtener_repositorio_borrado)],
    retiros: Retiros,
    efectos: Efectos,
    reloj: RelojDep,
) -> BorradoPersona:
    try:
        persona = uuid.UUID(persona_id)
    except ValueError:
        raise ErrorMATU(404) from None
    try:
        resultado = borrar_persona(
            SolicitudBorrado(
                usuario_id=contexto.usuario_id,
                rol=contexto.rol,
                persona_id=persona,
                request_id=getattr(request.state, "request_id", None),
            ),
            reloj,
            repositorio,
            retiros,
            efectos,
        )
    except (RolSinPermisoBorrado, PersonaNoEncontrada):
        raise ErrorMATU(404) from None
    except YaBorrada:
        raise ErrorMATU(409, tipo="ya-borrada", detalle="Los datos de esta persona ya se borraron") from None
    except EfectoNoDisponible:
        log.error("falta el efecto del borrado de una finalidad")
        raise ErrorMATU(500) from None
    return BorradoPersona(
        persona_id=resultado.persona_id,
        borrado_en=resultado.borrado_en,
        enlaces_cortados=resultado.enlaces_cortados,
        autorizaciones_retiradas=resultado.autorizaciones_retiradas,
    )

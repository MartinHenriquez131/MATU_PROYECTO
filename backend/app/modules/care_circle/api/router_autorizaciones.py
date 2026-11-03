"""Autorización para calcular cuándo se acaban los insumos (MATU-36, decisión 37).

    POST /v1/personas-cuidadas/{persona_id}/consentimientos   admin y cuidador. 201

Contrato: docs/api/openapi.json (antes propuestos/app-familia.openapi.yaml). Orden de evaluación:
401, 404 (membresía, rol, persona), 422 (cuerpo y reglas de la calidad), 409 y 201. El rol y la
persona se verifican en dependencias, antes de validar el cuerpo: un observador recibe 404 aunque
su cuerpo sea inválido. Registra consentimiento.otorgar, sin la referencia al documento.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, Request, Response, status
from pydantic import BaseModel, ConfigDict

from app.core.errores import ErrorMATU
from app.modules.care_circle.api.dependencias import ContextoGrupo, SesionDeGrupo
from app.modules.care_circle.api.esquemas_personas import (
    AvisoMostradoEntrada,
    AvisoVista,
    ConsentimientoVista,
    ReferenciaDocumento,
)
from app.modules.care_circle.api.router_personas import obtener_politica_version
from app.modules.care_circle.application.autorizaciones import (
    AutorizacionVigente,
    RepositorioAutorizaciones,
    RolSinPermisoAutorizacion,
    SolicitudAutorizacion,
    otorgar_autorizacion_consumo,
)
from app.modules.care_circle.domain.personas import (
    AvisoMostrado,
    CalidadOtorgante,
    OtorgamientoInvalido,
    puede_dar_de_alta,
)
from app.modules.care_circle.infrastructure.autorizacion import persona_con_autorizacion
from app.modules.care_circle.infrastructure.repositorio_autorizaciones import RepositorioAutorizacionesSQL
from app.modules.iam.api.dependencias import obtener_reloj
from app.shared.auditoria_sql import RegistroAuditoriaSql
from app.shared.puertos import Reloj

router = APIRouter(tags=["autorizaciones"])

RUTA = "/personas-cuidadas/{persona_id}/consentimientos"

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_ERRORES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Falta el access token, o es inválido o vencido", **_PROBLEMA},
    404: {"description": "No miembro, rol que no alcanza, persona de otro grupo o inexistente", **_PROBLEMA},
    409: {"description": "/errores/autorizacion-vigente: ya hay una autorización no revocada", **_PROBLEMA},
    422: {"description": "Cuerpo inválido o una combinación que no cumple las reglas de la calidad", **_PROBLEMA},
}


class SolicitudAutorizacionEntrada(BaseModel):
    """Cuerpo de la autorización. Solo ``finalidad: consumo``. Un campo extra responde 422."""

    model_config = ConfigDict(extra="forbid")

    finalidad: Literal["consumo"]
    calidad_otorgante: CalidadOtorgante
    referencia_documento: ReferenciaDocumento | None = None
    aviso: AvisoMostradoEntrada | None = None


class AutorizacionCreada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consentimiento: ConsentimientoVista
    aviso: AvisoVista | None


@dataclass(frozen=True)
class PersonaParaAutorizar:
    contexto: ContextoGrupo
    persona_id: uuid.UUID


def persona_para_autorizar(
    contexto: SesionDeGrupo, persona_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})]
) -> PersonaParaAutorizar:
    """Dan la autorización admin y cuidador; la persona debe ser del grupo. Si no, 404."""
    if not puede_dar_de_alta(contexto.rol):
        raise ErrorMATU(404)
    try:
        persona = uuid.UUID(persona_id)
    except ValueError:
        raise ErrorMATU(404) from None
    if persona_con_autorizacion(contexto.sesion, contexto.grupo_id, persona) is None:
        raise ErrorMATU(404)
    return PersonaParaAutorizar(contexto, persona)


def obtener_repositorio_autorizaciones(
    contexto: SesionDeGrupo, reloj: Annotated[Reloj, Depends(obtener_reloj)]
) -> RepositorioAutorizaciones:
    registro = RegistroAuditoriaSql(contexto.sesion, reloj)
    return RepositorioAutorizacionesSQL(contexto.sesion, contexto.grupo_id, registro)


@router.post(
    RUTA,
    status_code=status.HTTP_201_CREATED,
    response_model=AutorizacionCreada,
    responses=_ERRORES,
    summary="Dar la autorización para calcular cuándo se acaban los insumos",
)
def otorgar(
    request: Request,
    response: Response,
    autorizar: Annotated[PersonaParaAutorizar, Depends(persona_para_autorizar)],
    solicitud: SolicitudAutorizacionEntrada,
    repositorio: Annotated[RepositorioAutorizaciones, Depends(obtener_repositorio_autorizaciones)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    version_politica: Annotated[str, Depends(obtener_politica_version)],
) -> AutorizacionCreada:
    contexto = autorizar.contexto
    aviso = solicitud.aviso
    try:
        resultado = otorgar_autorizacion_consumo(
            SolicitudAutorizacion(
                usuario_id=contexto.usuario_id,
                grupo_id=contexto.grupo_id,
                rol=contexto.rol,
                persona_id=autorizar.persona_id,
                calidad_otorgante=solicitud.calidad_otorgante,
                referencia_documento=solicitud.referencia_documento,
                aviso=None if aviso is None else AvisoMostrado(id=aviso.id, version=aviso.version),
                request_id=getattr(request.state, "request_id", None),
            ),
            version_politica,
            reloj,
            repositorio,
        )
    except RolSinPermisoAutorizacion:  # pragma: no cover - la dependencia ya lo verificó
        raise ErrorMATU(404) from None
    except OtorgamientoInvalido as error:
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[{"campo": error.campo, "mensaje": error.mensaje, "tipo": "regla_calidad_otorgante"}],
        ) from None
    except AutorizacionVigente:
        raise ErrorMATU(
            409,
            tipo="autorizacion-vigente",
            detalle="Esta persona ya tiene la autorización para calcular sus insumos",
        ) from None

    response.headers["Cache-Control"] = "no-store"
    nueva = resultado.autorizacion
    a = resultado.aviso
    return AutorizacionCreada(
        consentimiento=ConsentimientoVista(
            id=nueva.id,
            calidad_otorgante=solicitud.calidad_otorgante,
            finalidad=nueva.finalidad,
            version_politica=nueva.version_politica,
            otorgado_en=nueva.otorgado_en,
            revision_vence_en=nueva.revision_vence_en,
        ),
        aviso=None
        if a is None
        else AvisoVista(id=a.id, version=a.version, titulo=a.titulo, parrafos=list(a.parrafos), sha256=a.sha256),
    )

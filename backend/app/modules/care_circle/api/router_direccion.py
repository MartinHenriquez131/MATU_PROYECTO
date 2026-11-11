"""La dirección de entrega de la persona (MATU-61, D4, C6 y C8; decisiones 189 a 191, 216 y 219).

    PUT    /v1/personas-cuidadas/{persona_id}/direccion    admin y cuidador. 200 con ETag
    DELETE /v1/personas-cuidadas/{persona_id}/direccion    admin y cuidador. 204

Vive en care_circle y existe siempre, también con la capa 3 apagada. No pide la autorización de pedidos (C8). La
lectura va en la persona (GET /v1/grupos/{grupo_id}/personas-cuidadas), con su etag (decisión 190).

Orden del PUT: 401, 404 (rol y persona), 428, 422 (cabeceras y cuerpo), 412 y 200. Del DELETE: 401, 404, 428, 404 sin
dirección, 412 y 204. Cache-Control: no-store (prefijo /v1/personas-cuidadas/ en app.main). Registra
direccion.cambiar sin el contenido (D12). Nada de la dirección va a los logs: ni en los errores, que nombran el campo.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Request, Response, status
from pydantic import BaseModel, ConfigDict

from app.core.errores import ErrorMATU
from app.modules.care_circle.api.dependencias import ContextoGrupo, SesionDeGrupo
from app.modules.care_circle.api.esquemas_personas import DireccionVista, Texto20, Texto40, Texto60, Texto120, Texto200
from app.modules.care_circle.api.router_autorizaciones import RegistroDep, RelojDep
from app.modules.care_circle.application.direccion import (
    Desactualizada,
    PersonaSinAcceso,
    RepositorioDireccion,
    SolicitudDireccion,
    guardar_direccion,
    vaciar_direccion,
)
from app.modules.care_circle.application.ports import DatosDireccion
from app.modules.care_circle.domain.direccion import (
    FaltaPrecondicion,
    Precondicion,
    PrecondicionInvalida,
    SinDireccion,
    etag_de,
    exigir_forma_precondicion,
    puede_cambiar_direccion,
)
from app.modules.care_circle.infrastructure.repositorio_direccion import RepositorioDireccionSQL

router = APIRouter(tags=["direccion"])

RUTA = "/personas-cuidadas/{persona_id}/direccion"

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_ERRORES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Falta el access token, o es inválido o vencido", **_PROBLEMA},
    404: {
        "description": "No miembro, rol que no alcanza (pagador u observador), persona de otro grupo, inexistente o"
        " eliminada; al vaciar, también la persona sin dirección",
        **_PROBLEMA,
    },
    412: {"description": "/errores/version-desactualizada, con la dirección vigente en actual", **_PROBLEMA},
    428: {"description": "/errores/falta-version: falta If-Match (o If-None-Match: * la primera vez)", **_PROBLEMA},
}
_DETALLE_428 = "Falta la versión de la dirección: If-None-Match: * la primera vez, If-Match con su etag después"


class DireccionEntrada(BaseModel):
    """Cuerpo de PUT …/direccion: los campos y largos de DireccionNueva del alta. Sin lat ni lng (C8): un campo
    extra responde 422. Reemplaza la dirección completa."""

    model_config = ConfigDict(extra="forbid")

    etiqueta: Texto40 = "Casa"
    calle: Texto120
    numero: Texto20
    depto: Texto20 | None = None
    comuna: Texto60
    region: Texto60 = "Metropolitana"
    referencia: Texto200 | None = None


@dataclass(frozen=True)
class PersonaDeLaDireccion:
    contexto: ContextoGrupo
    persona_id: uuid.UUID


def persona_de_la_direccion(
    contexto: SesionDeGrupo, persona_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})]
) -> PersonaDeLaDireccion:
    """404 antes de mirar las cabeceras y el cuerpo: el rol que no alcanza y un id que no es UUID."""
    if not puede_cambiar_direccion(contexto.rol):
        raise ErrorMATU(404)
    try:
        return PersonaDeLaDireccion(contexto, uuid.UUID(persona_id))
    except ValueError:
        raise ErrorMATU(404) from None


def _falta_version() -> ErrorMATU:
    return ErrorMATU(428, detalle=_DETALLE_428)


def precondicion_de_guardar(
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
) -> Precondicion:
    """428 y 422 de las cabeceras, antes de validar el cuerpo. El 412 lo decide el caso de uso."""
    precondicion = Precondicion(if_match=if_match, if_none_match=if_none_match)
    try:
        exigir_forma_precondicion(precondicion)
    except FaltaPrecondicion:
        raise _falta_version() from None
    except PrecondicionInvalida:
        raise ErrorMATU(
            422,
            detalle="Revisa las cabeceras indicadas",
            errores=[{"campo": "If-None-Match", "mensaje": "solo *, y sin If-Match", "tipo": "precondicion"}],
        ) from None
    return precondicion


def if_match_de_vaciar(if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> str:
    if if_match is None or not if_match.strip() or if_match.strip() == "*":
        raise _falta_version()
    return if_match


def obtener_repositorio_direccion(contexto: SesionDeGrupo) -> RepositorioDireccion:
    return RepositorioDireccionSQL(contexto.sesion, contexto.grupo_id)


Persona = Annotated[PersonaDeLaDireccion, Depends(persona_de_la_direccion)]
Repositorio = Annotated[RepositorioDireccion, Depends(obtener_repositorio_direccion)]


def _vista(d: DatosDireccion) -> DireccionVista:
    return DireccionVista(
        etiqueta=d.etiqueta,
        calle=d.calle,
        numero=d.numero,
        depto=d.depto,
        comuna=d.comuna,
        region=d.region,
        referencia=d.referencia,
        etag=etag_de(d.version),
    )


def _desactualizada(error: Desactualizada) -> ErrorMATU:
    return ErrorMATU(
        412,
        detalle="Otra persona cambió la dirección. Revisa la vigente",
        headers={"ETag": etag_de(error.actual.version)},
        extension={"actual": _vista(error.actual).model_dump(mode="json")},
    )


def _solicitud(request: Request, persona: PersonaDeLaDireccion) -> SolicitudDireccion:
    contexto = persona.contexto
    return SolicitudDireccion(
        usuario_id=contexto.usuario_id,
        grupo_id=contexto.grupo_id,
        rol=contexto.rol,
        persona_id=persona.persona_id,
        request_id=getattr(request.state, "request_id", None),
    )


@router.put(
    RUTA,
    response_model=DireccionVista,
    responses={
        **_ERRORES,
        422: {"description": "Cuerpo o cabeceras inválidos (nombra el campo, nunca el valor)", **_PROBLEMA},
    },
    summary="Guardar o cambiar la dirección de entrega de la persona",
    description=(
        "MATU-61 (D4, decisiones 189 a 191 y 219). admin y cuidador; el resto, 404. If-None-Match: * la primera vez, "
        "If-Match con el etag después (428 sin ninguna, 422 las dos juntas, 412 con actual). Sin lat ni lng. Cambia "
        "la dirección de esa persona y solo de ella. No pide la autorización de pedidos (C8). Registra "
        "direccion.cambiar sin el contenido. Cache-Control: no-store"
    ),
)
def guardar(
    request: Request,
    response: Response,
    persona: Persona,
    precondicion: Annotated[Precondicion, Depends(precondicion_de_guardar)],
    cuerpo: DireccionEntrada,
    repositorio: Repositorio,
    registro: RegistroDep,
    reloj: RelojDep,
) -> DireccionVista:
    datos = DatosDireccion(
        etiqueta=cuerpo.etiqueta,
        calle=cuerpo.calle,
        numero=cuerpo.numero,
        depto=cuerpo.depto,
        comuna=cuerpo.comuna,
        region=cuerpo.region,
        referencia=cuerpo.referencia,
    )
    try:
        guardada = guardar_direccion(_solicitud(request, persona), precondicion, datos, reloj, repositorio, registro)
    except PersonaSinAcceso:
        raise ErrorMATU(404) from None
    except Desactualizada as error:
        raise _desactualizada(error) from None
    response.headers["ETag"] = etag_de(guardada.version)
    response.headers["Cache-Control"] = "no-store"
    return _vista(guardada)


@router.delete(
    RUTA,
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORES,
    summary="Vaciar la dirección de entrega de la persona",
    description=(
        "MATU-61 (C6, decisiones 216 y 219). admin y cuidador; el resto, 404. If-Match obligatorio (428 sin él o con "
        "*, 412 con actual). Sin dirección, 404. La persona queda sin dirección y la fila se borra si nadie más la "
        "usa. No pide la autorización de pedidos (C8). Registra direccion.cambiar sin el contenido. Cache-Control: "
        "no-store"
    ),
)
def vaciar(
    request: Request,
    persona: Persona,
    if_match: Annotated[str, Depends(if_match_de_vaciar)],
    repositorio: Repositorio,
    registro: RegistroDep,
) -> Response:
    try:
        vaciar_direccion(_solicitud(request, persona), if_match, repositorio, registro)
    except (PersonaSinAcceso, SinDireccion):
        raise ErrorMATU(404) from None
    except Desactualizada as error:
        raise _desactualizada(error) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})

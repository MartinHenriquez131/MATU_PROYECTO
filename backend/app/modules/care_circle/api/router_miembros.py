"""Quiénes forman el grupo, sus roles y salir (MATU-42 y MATU-53, RF-38). Contrato: invitar-familiar.openapi.yaml.

    GET    /v1/grupos/{grupo_id}/miembros                  todo miembro activo
    PATCH  /v1/grupos/{grupo_id}/miembros/{membresia_id}   solo admin, con If-Match
    DELETE /v1/grupos/{grupo_id}/miembros/{membresia_id}   solo admin; la propia es salir
    POST   /v1/grupos/{grupo_id}/salida                    todo miembro activo

Un grupo ajeno, un rol que no alcanza, un id que no es UUID o una membresía retirada responden 404, nunca 403. Sacar,
salir y dejar de ser admin o cuidador cortan los enlaces de relevo que la persona compartió (decisión 305).
Cache-Control: no-store en todas las respuestas (prefijo /v1/grupos en app.main). No se registra el nombre de nadie.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Response

from app.core.errores import ErrorMATU
from app.modules.care_circle.api.dependencias_grupo import ActorAdmin, ActorDelGrupo, PuertosDelGrupo
from app.modules.care_circle.api.esquemas_grupo import (
    ListaMiembros,
    MiembroVista,
    ResultadoCambioMiembro,
    ResultadoSalida,
    SolicitudCambioMiembro,
)
from app.modules.care_circle.application.invitaciones import Actor, NoEncontrado
from app.modules.care_circle.application.miembros import (
    MiembroVisto,
    NoPuedeSalirDelGrupo,
    Puertos,
    UltimoAdmin,
    VersionDesactualizada,
    cambiar_miembro,
    destino_del_cambio,
    listar_miembros,
    sacar_miembro,
    salir_del_grupo,
)
from app.modules.care_circle.application.ports_grupo import MiembroGuardado
from app.modules.care_circle.domain.miembros import FaltaVersion, NoPuedeSalir, PermisoSoloPagador, etag

router = APIRouter(prefix="/grupos/{grupo_id}", tags=["miembros"])

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_404: dict[int | str, dict[str, Any]] = {
    401: {"description": "no-autenticado o token-invalido", **_PROBLEMA},
    404: {"description": "Grupo ajeno, rol que no alcanza, o membresía inexistente, retirada o ajena", **_PROBLEMA},
}
_409_SALIR: dict[int | str, dict[str, Any]] = {
    409: {"description": "ultimo-admin o unica-persona. No cambia nada", **_PROBLEMA}
}
_EXITO: dict[str, Any] = {
    "headers": {"Cache-Control": {"description": "no-store", "schema": {"type": "string"}}}
}
_TEXTO_ULTIMO_ADMIN = "El grupo necesita alguien que lo administre. Primero da ese rol a otra persona"
_TEXTO_UNICA_PERSONA = "Eres la única persona del grupo"


def _vista(m: MiembroVisto) -> MiembroVista:
    return MiembroVista(
        id=m.id,
        nombre=m.nombre,
        rol=m.rol,  # type: ignore[arg-type]
        puede_ver_plan=m.puede_ver_plan,
        unido_en=m.unido_en,
        eres_tu=m.eres_tu,
        etag=etag(m.version),
        enlaces_vigentes=m.enlaces_vigentes,
    )


def _no_puede_salir(error: NoPuedeSalirDelGrupo) -> ErrorMATU:
    texto = _TEXTO_UNICA_PERSONA if error.motivo is NoPuedeSalir.UNICA_PERSONA else _TEXTO_ULTIMO_ADMIN
    return ErrorMATU(409, tipo=error.motivo.value, detalle=texto)


def _membresia(membresia_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(membresia_id)
    except ValueError:
        raise ErrorMATU(404) from None


def miembro_destino(
    actor: ActorAdmin,
    puertos: PuertosDelGrupo,
    membresia_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})],
) -> MiembroGuardado:
    """El 404 del PATCH antes de If-Match y del cuerpo. La membresía queda bloqueada hasta el final."""
    try:
        return destino_del_cambio(_membresia(membresia_id), actor, puertos)
    except NoEncontrado:
        raise ErrorMATU(404) from None


def version_pedida(if_match: Annotated[str | None, Header(alias="If-Match")] = None) -> str:
    """428 falta-version antes del cuerpo (decisión 303). La forma la revisa el caso de uso: otra es 412."""
    if if_match is None or not if_match.strip() or if_match.strip() == "*":
        raise ErrorMATU(428, detalle="Falta la versión de la membresía: If-Match con su etag")
    return if_match


@router.get(
    "/miembros",
    response_model=ListaMiembros,
    operation_id="listarMiembros",
    responses={200: _EXITO, **_404},
    summary="Quiénes forman el grupo",
    description="MATU-42 (decisión 302). Todo miembro activo. Sin email, celular ni usuario_id. No se audita.",
)
def listar(actor: ActorDelGrupo, puertos: PuertosDelGrupo) -> ListaMiembros:
    return ListaMiembros(miembros=[_vista(m) for m in listar_miembros(actor, puertos)])


@router.patch(
    "/miembros/{membresia_id}",
    response_model=ResultadoCambioMiembro,
    operation_id="cambiarMiembro",
    responses={
        200: {"headers": {**_EXITO["headers"], "ETag": {"description": '"v<version>"', "schema": {"type": "string"}}}},
        **_404,
        409: {"description": "ultimo-admin: el grupo quedaría sin nadie que lo administre", **_PROBLEMA},
        412: {"description": "version-desactualizada, con la membresía vigente en actual", **_PROBLEMA},
        422: {"description": "Cuerpo inválido, o permiso_solo_pagador", **_PROBLEMA},
        428: {"description": "falta-version: sin If-Match, vacío o *", **_PROBLEMA},
    },
    summary="Cambiar el rol de alguien o el permiso del pagador para ver la ficha",
    description=(
        "MATU-42 (decisiones 303 a 305 y 307). Solo admin. Dejar de ser admin o cuidador corta los enlaces de relevo"
        " que compartió; dejar de ser admin anula sus invitaciones sin usar. Orden: 401, 404, 428, 422, 412, 409, 200."
    ),
)
def cambiar(
    response: Response,
    destino: Annotated[MiembroGuardado, Depends(miembro_destino)],
    if_match: Annotated[str, Depends(version_pedida)],
    solicitud: SolicitudCambioMiembro,
    actor: ActorAdmin,
    puertos: PuertosDelGrupo,
) -> ResultadoCambioMiembro:
    try:
        miembro, cortados = cambiar_miembro(destino, if_match, solicitud.rol, solicitud.puede_ver_plan, actor, puertos)
    except FaltaVersion:
        raise ErrorMATU(428, detalle="Falta la versión de la membresía: If-Match con su etag") from None
    except PermisoSoloPagador:
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[
                {"campo": "puede_ver_plan", "mensaje": "solo se da a quien paga", "tipo": "permiso_solo_pagador"}
            ],
        ) from None
    except VersionDesactualizada as error:
        raise ErrorMATU(
            412,
            detalle="Otra persona cambió esta membresía. Revisa la vigente",
            headers={"ETag": etag(error.actual.version)},
            extension={"actual": _vista(error.actual).model_dump(mode="json")},
        ) from None
    except UltimoAdmin:
        raise ErrorMATU(409, tipo="ultimo-admin", detalle=_TEXTO_ULTIMO_ADMIN) from None
    except NoEncontrado:
        raise ErrorMATU(404) from None
    response.headers["ETag"] = etag(miembro.version)
    return ResultadoCambioMiembro(miembro=_vista(miembro), enlaces_cortados=cortados)


def _retiro(funcion: Any, *argumentos: Any) -> ResultadoSalida:
    try:
        return ResultadoSalida(enlaces_cortados=funcion(*argumentos))
    except NoEncontrado:
        raise ErrorMATU(404) from None
    except NoPuedeSalirDelGrupo as error:
        raise _no_puede_salir(error) from None


@router.delete(
    "/miembros/{membresia_id}",
    response_model=ResultadoSalida,
    operation_id="sacarMiembro",
    responses={200: _EXITO, **_404, **_409_SALIR},
    summary="Sacar a alguien del grupo",
    description=(
        "MATU-42 (decisiones 305 a 307). Solo admin. Corta sus enlaces de relevo, anula sus invitaciones si era admin y"
        " deja la membresía retirada. La propia membresía es salir. No es idempotente: una retirada es 404."
    ),
)
def sacar(
    actor: ActorAdmin,
    puertos: PuertosDelGrupo,
    membresia_id: Annotated[str, Path(json_schema_extra={"format": "uuid"})],
) -> ResultadoSalida:
    return _retiro(sacar_miembro, _membresia(membresia_id), actor, puertos)


@router.post(
    "/salida",
    response_model=ResultadoSalida,
    operation_id="salirDelGrupo",
    responses={200: _EXITO, **_404, **_409_SALIR},
    summary="Salir del grupo por cuenta propia",
    description=(
        "MATU-42 (D-42-13). Todo miembro activo. Corta sus enlaces de relevo, anula sus invitaciones si era admin y"
        " deja la membresía retirada. 409 ultimo-admin o unica-persona."
    ),
)
def salir(actor: ActorDelGrupo, puertos: PuertosDelGrupo) -> ResultadoSalida:
    return _retiro(_salir, actor, puertos)


def _salir(actor: Actor, puertos: Puertos) -> int:
    return salir_del_grupo(actor, puertos)

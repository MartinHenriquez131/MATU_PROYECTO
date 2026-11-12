"""Rutas de las secciones complementarias de la ficha (MATU-50, ADR-028, RF-03).
Contrato: docs/api/propuestos/ficha-ampliada.openapi.yaml (MATU-49).

    PUT    /v1/personas-cuidadas/{persona_id}/plan/secciones/{seccion}   admin y cuidador. 201 agregada, 200 editada
    DELETE /v1/personas-cuidadas/{persona_id}/plan/secciones/{seccion}   admin y cuidador. 204 quitada

Orden de evaluación, el mismo de la ficha: 401, 404 (grupo, rol, persona, sección), 403 (consentimiento),
503 (custodia), 422 (cuerpo y texto, después cabeceras) y al final la precondición (428 o 412).

- PUT: exactamente una de ``If-None-Match: *`` (agregar) o ``If-Match: "<etag>"`` (editar). Sin ninguna, o
  con ``If-Match: *``, 428; con las dos, 422. Texto vacío o solo espacios, 422 ``vacio``; más de 500
  caracteres (800 en remedios), 422 ``largo_maximo``.
- DELETE: ``If-Match`` obligatorio (428 sin él o con ``*``), ``If-None-Match`` responde 422. Borra la fila.
- 412 con ``actual``: la sección vigente descifrada, o null si no está. Se devuelve como respuesta, no
  como excepción, para que la transacción confirme el plan.leer de esa lectura.
- Registra plan.editar o plan.quitar_seccion con el tipo de la sección, nunca el texto.

Ni el texto ni nada derivado de él llega a los logs: la línea de la petición lleva la plantilla de la
ruta; los errores del cifrado tienen mensaje fijo; y un 422 nombra el campo, nunca el valor. Toda
respuesta lleva Cache-Control: no-store.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.errores import ErrorMATU, respuesta_problema
from app.modules.care_plan.api.dependencias import (
    SeccionAutorizada,
    cifrador_para_seccion,
    obtener_auditoria_ficha,
    obtener_repositorio_ficha,
    seccion_para_escribir,
)
from app.modules.care_plan.api.esquemas import (
    AutorVista,
    ProblemaFaltaVersionVista,
    ProblemaVersionSeccionVista,
    SeccionGuardadaVista,
    SolicitudSeccion,
)
from app.modules.care_plan.api.router import estado_seccion
from app.modules.care_plan.application.ficha import PeticionFicha, PlanNoDisponible
from app.modules.care_plan.application.ports import AuditoriaFicha, CifradorSecciones, RepositorioFicha
from app.modules.care_plan.application.secciones import SeccionEnConflicto, guardar_seccion, quitar_seccion
from app.modules.care_plan.domain.cifrado import ClaveDestruida, ClaveNoDisponible, ErrorCifrado
from app.modules.care_plan.domain.ficha import (
    FaltaPrecondicion,
    PrecondicionInvalida,
    etag,
    precondicion_de,
)
from app.modules.care_plan.domain.secciones import (
    TextoSeccionInvalido,
    precondicion_para_quitar,
    validar_texto_seccion,
)
from app.modules.iam.api.dependencias import obtener_reloj
from app.shared.puertos import Reloj

log = logging.getLogger("matu.care_plan.secciones")

router = APIRouter(tags=["ficha"])

RUTA_SECCION = "/personas-cuidadas/{persona_id}/plan/secciones/{seccion}"

NO_STORE = "no-store"

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_X_REQUEST_ID: dict[str, Any] = {
    "description": "Identificador de la petición (UUID), el mismo request_id de los logs y del problema",
    "schema": {"type": "string", "format": "uuid"},
}
_NO_STORE: dict[str, Any] = {
    "description": "La respuesta puede llevar texto de la ficha y no se guarda en ninguna caché",
    "schema": {"type": "string", "const": NO_STORE},
}
_ETAG: dict[str, Any] = {
    "description": 'Versión de la sección recién guardada, por ejemplo "v2". Se envía tal cual en el próximo If-Match',
    "schema": {"type": "string"},
}
_ETAG_ACTUAL: dict[str, Any] = {
    "description": "Versión actual de la sección. Ausente si la sección no está",
    "required": False,
    "schema": {"type": "string"},
}
_CABECERAS_GUARDADO: dict[str, Any] = {"X-Request-ID": _X_REQUEST_ID, "ETag": _ETAG, "Cache-Control": _NO_STORE}


def _esquema_en_linea(modelo: type[BaseModel]) -> dict[str, Any]:
    """El esquema del problema para el OpenAPI, con referencias a componentes que ya registra la ficha
    (FichaVista registra EstadoSeccionVista y AutorVista). Así no queda un $ref colgando."""
    esquema = modelo.model_json_schema(ref_template="#/components/schemas/{model}", mode="serialization")
    anidados = set(esquema.pop("$defs", {}))
    if not anidados <= {"EstadoSeccionVista", "AutorVista"}:
        raise ValueError("el problema usa un modelo que la ficha no registra en el OpenAPI")
    return esquema


_EJEMPLO_412: dict[str, Any] = {
    "type": "/errores/version-desactualizada",
    "title": "Otra persona cambió esta sección",
    "status": 412,
    "detail": "Esta sección ya no está. Vuelve a abrir la ficha",
    "errores": [],
    "request_id": "9b2f4c1e-0000-4000-8000-0000000000f2",
    "actual": None,
}
_EJEMPLO_428: dict[str, Any] = {
    "type": "/errores/falta-version",
    "title": "Falta la versión del contenido",
    "status": 428,
    "detail": "Vuelve a abrir la sección y guarda de nuevo",
    "errores": [],
    "request_id": "9b2f4c1e-0000-4000-8000-0000000000f3",
}

_ERRORES_COMUNES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Falta el access token, o es inválido o vencido", **_PROBLEMA},
    403: {"description": "Sin consentimiento vigente para plan_cuidado, o revisión anual vencida", **_PROBLEMA},
    404: {
        "description": (
            "No miembro, rol que no alcanza, persona de otro grupo o inexistente, o una sección que no es una de"
            " las seis (también un campo base). Nunca 403"
        ),
        **_PROBLEMA,
    },
    412: {
        "description": (
            "Otra persona se adelantó: la sección cambió, ya estaba agregada (If-None-Match: *) o no está (If-Match"
            " sobre una sección nunca agregada o ya quitada: `actual` null). `actual` trae la sección vigente para"
            " que la persona decida: no hay fusión automática (ADR-015). Leer `actual` queda auditado como plan.leer"
        ),
        "headers": {"X-Request-ID": _X_REQUEST_ID, "ETag": _ETAG_ACTUAL, "Cache-Control": _NO_STORE},
        "content": {
            "application/problem+json": {
                "schema": _esquema_en_linea(ProblemaVersionSeccionVista),
                "example": _EJEMPLO_412,
            }
        },
    },
    428: {
        "description": "Falta If-Match (o If-None-Match: * al agregar), o vino If-Match vacío o *",
        "headers": {"X-Request-ID": _X_REQUEST_ID, "Cache-Control": _NO_STORE},
        "content": {
            "application/problem+json": {
                "schema": _esquema_en_linea(ProblemaFaltaVersionVista),
                "example": _EJEMPLO_428,
            }
        },
    },
    500: {"description": "Error inesperado o sección ilegible, sin el texto", **_PROBLEMA},
    503: {"description": "La custodia de la clave maestra no está configurada", **_PROBLEMA},
}

_RESPUESTAS_PUT: dict[int | str, dict[str, Any]] = {
    **_ERRORES_COMUNES,
    200: {"description": "Sección editada, con If-Match", "headers": _CABECERAS_GUARDADO},
    201: {
        "description": "Sección agregada, con If-None-Match: *",
        "model": SeccionGuardadaVista,
        "headers": _CABECERAS_GUARDADO,
    },
    422: {
        "description": (
            "Cuerpo inválido: `texto` falta, no es texto, trae caracteres de control (tipo value_error), está vacío o"
            " solo con espacios (tipo vacio) o supera 500 caracteres, 800 en remedios (tipo largo_maximo); o hay un"
            " campo extra. También If-Match e If-None-Match a la vez (precondicion_doble) o If-None-Match distinto"
            " de * (precondicion_invalida). errores[] nombra el campo o la cabecera, nunca el valor"
        ),
        "headers": {"X-Request-ID": _X_REQUEST_ID},
        **_PROBLEMA,
    },
}

_RESPUESTAS_DELETE: dict[int | str, dict[str, Any]] = {
    **_ERRORES_COMUNES,
    204: {"description": "Sección quitada: su fila se borró", "headers": {"Cache-Control": _NO_STORE}},
    422: {
        "description": "Vino If-None-Match: quitar solo admite If-Match (tipo precondicion_invalida)",
        "headers": {"X-Request-ID": _X_REQUEST_ID},
        **_PROBLEMA,
    },
}

_DESCRIPCION_PUT = """Agrega o edita **una** sección complementaria (ADR-028). Mismo patrón que un campo de la
ficha (MATU-13), con exactamente una cabecera:

| Situación | Cabecera | Si otra persona se adelantó |
|---|---|---|
| La sección no está agregada | `If-None-Match: *` | 412 con lo que esa persona guardó |
| La sección ya está | `If-Match: "<etag leído>"` | 412 con el contenido actual |

- Sin ninguna, o con `If-Match` vacío o `*`, **428**. Con las dos, **422**.
- `If-Match` sobre una sección que no está (nunca agregada, o quitada): **412** con `actual: null`.
- `texto` vacío o solo espacios: **422** `vacio`. Una sección no se vacía: se quita con `DELETE`.
- Más de 500 caracteres (800 en `remedios`): **422** `largo_maximo`.
- `seccion` fuera de las seis (incluidos `rutina`, `horarios`, `actividades` y `red_apoyo`): **404**.

La primera escritura crea el plan y la clave de datos de la persona si no existían. **201** si se agregó,
**200** si se editó. Escriben `admin` y `cuidador`. Registra `plan.editar` con el tipo de la sección, sin el
texto; el 412, `plan.leer`. Las secciones no cuentan para la completitud.
"""

_DESCRIPCION_DELETE = """Quita una sección complementaria **borrando su fila**: el texto cifrado deja de
existir. Exige `If-Match: "<etag leído>"`, para no borrar lo que otra persona acaba de escribir:

- Sin `If-Match`, o con `If-Match` vacío o `*`: **428**. `If-None-Match`: **422**.
- ETag distinto del actual: **412** con el contenido actual.
- La sección no está (nunca agregada, o ya quitada): **412** con `actual: null`. No es 404, para que la
  pantalla distinga "ya la quitó otra persona" de "no tienes acceso".
- **204** sin cuerpo.

Registra `plan.quitar_seccion` con el tipo de la sección, sin el texto. Un acceso de relevo que la compartía
deja de mostrarla; si se vuelve a agregar, ese acceso no la ve.
"""

_MENSAJES_PRECONDICION = {
    "precondicion_doble": "envía If-Match o If-None-Match, no las dos",
    "precondicion_invalida": "If-None-Match solo admite *, y quitar una sección solo admite If-Match",
}


def _peticion(request: Request, autorizada: SeccionAutorizada) -> PeticionFicha:
    return PeticionFicha(
        grupo_id=autorizada.ficha.contexto.grupo_id,
        usuario_id=autorizada.ficha.contexto.usuario_id,
        persona_cuidada_id=autorizada.ficha.persona_id,
        request_id=getattr(request.state, "request_id", None),
    )


def _error_cifrado(error: ErrorCifrado) -> ErrorMATU:
    """Igual que en la ficha: clave destruida 404, custodia sin la DEK 503, sección ilegible 500. Sin texto."""
    log.warning("la sección no se pudo cifrar o descifrar", extra={"tipo_error": type(error).__name__})
    if isinstance(error, ClaveDestruida):
        return ErrorMATU(404)
    if isinstance(error, ClaveNoDisponible):
        return ErrorMATU(503, detalle="La ficha no está disponible en este momento. Cita el request_id si lo reportas")
    return ErrorMATU(500, detalle="No pudimos abrir la ficha. Cita el request_id si lo reportas")


def _error_precondicion(error: PrecondicionInvalida) -> ErrorMATU:
    return ErrorMATU(
        422,
        detalle="Revisa los campos indicados",
        errores=[{"campo": error.cabecera, "mensaje": _MENSAJES_PRECONDICION[error.tipo], "tipo": error.tipo}],
    )


def _falta_version() -> ErrorMATU:
    return ErrorMATU(
        428, detalle="Vuelve a abrir la sección y guarda de nuevo", headers={"Cache-Control": NO_STORE}
    )


def _version_desactualizada(request: Request, conflicto: SeccionEnConflicto) -> JSONResponse:
    """412 con la sección vigente o null. El texto va solo en el cuerpo, nunca en un log."""
    actual = conflicto.actual
    cabeceras = {"Cache-Control": NO_STORE}
    if actual is None:
        detalle = "Esta sección ya no está. Vuelve a abrir la ficha"
        cuerpo_actual = None
    else:
        assert actual.version is not None
        quien = (actual.actualizado_por.nombre if actual.actualizado_por is not None else None) or "Otra persona"
        detalle = f"{quien} guardó esta sección mientras la editabas. Revisa su versión antes de guardar la tuya"
        cabeceras["ETag"] = etag(actual.version)
        cuerpo_actual = estado_seccion(actual).model_dump(mode="json")
    return respuesta_problema(
        request,
        status.HTTP_412_PRECONDITION_FAILED,
        titulo="Otra persona cambió esta sección",
        detalle=detalle,
        headers=cabeceras,
        extension={"actual": cuerpo_actual},
    )


@router.put(
    RUTA_SECCION,
    response_model=SeccionGuardadaVista,
    responses=_RESPUESTAS_PUT,
    summary="Agregar o editar una sección complementaria",
    description=_DESCRIPCION_PUT,
    operation_id="guardarSeccionFicha",
    openapi_extra={"x-matu-historia": "MATU-50", "x-matu-auditoria": "plan.editar"},
)
def guardar(
    request: Request,
    response: Response,
    autorizada: Annotated[SeccionAutorizada, Depends(seccion_para_escribir)],
    cifrador: Annotated[CifradorSecciones, Depends(cifrador_para_seccion)],
    repositorio: Annotated[RepositorioFicha, Depends(obtener_repositorio_ficha)],
    auditoria: Annotated[AuditoriaFicha, Depends(obtener_auditoria_ficha)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    solicitud: SolicitudSeccion,
    if_match: Annotated[
        str | None,
        Header(
            alias="If-Match",
            description=(
                'ETag de la sección tal como se leyó, por ejemplo "v2". Obligatorio si la sección ya está. Vacío o *'
                " responde 428"
            ),
        ),
    ] = None,
    if_none_match: Annotated[
        str | None,
        Header(
            alias="If-None-Match",
            description="Solo *, para agregar una sección que no está. Otro valor, o junto con If-Match, responde 422",
        ),
    ] = None,
) -> SeccionGuardadaVista | JSONResponse:
    try:
        texto = validar_texto_seccion(autorizada.seccion, solicitud.texto)
    except TextoSeccionInvalido as error:
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[{"campo": "texto", "mensaje": error.mensaje, "tipo": error.tipo}],
        ) from None
    try:
        precondicion = precondicion_de(if_match, if_none_match)
    except PrecondicionInvalida as error:
        raise _error_precondicion(error) from None
    except FaltaPrecondicion:
        raise _falta_version() from None
    try:
        guardada = guardar_seccion(
            _peticion(request, autorizada), autorizada.seccion, texto, precondicion, repositorio, cifrador, auditoria,
            reloj,
        )
    except ErrorCifrado as error:
        raise _error_cifrado(error) from None
    except PlanNoDisponible:
        log.error("no se pudo crear ni leer el plan de cuidado")
        raise ErrorMATU(500, detalle="No pudimos guardar la ficha. Cita el request_id si lo reportas") from None
    if isinstance(guardada, SeccionEnConflicto):
        return _version_desactualizada(request, guardada)

    estado = guardada.estado
    assert estado.texto is not None and estado.version is not None
    assert estado.actualizado_por is not None and estado.actualizado_en is not None
    etag_nuevo = etag(estado.version)
    response.status_code = status.HTTP_201_CREATED if guardada.creada else status.HTTP_200_OK
    response.headers["ETag"] = etag_nuevo
    response.headers["Cache-Control"] = NO_STORE
    return SeccionGuardadaVista(
        seccion=guardada.seccion,
        texto=estado.texto,
        etag=etag_nuevo,
        actualizado_por=AutorVista(
            id=estado.actualizado_por.id,
            nombre=estado.actualizado_por.nombre,
            autor_activo=estado.actualizado_por.activo,
        ),
        actualizado_en=estado.actualizado_en,
    )


@router.delete(
    RUTA_SECCION,
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=_RESPUESTAS_DELETE,
    summary="Quitar una sección complementaria",
    description=_DESCRIPCION_DELETE,
    operation_id="quitarSeccionFicha",
    openapi_extra={"x-matu-historia": "MATU-50", "x-matu-auditoria": "plan.quitar_seccion"},
)
def quitar(
    request: Request,
    autorizada: Annotated[SeccionAutorizada, Depends(seccion_para_escribir)],
    cifrador: Annotated[CifradorSecciones, Depends(cifrador_para_seccion)],
    repositorio: Annotated[RepositorioFicha, Depends(obtener_repositorio_ficha)],
    auditoria: Annotated[AuditoriaFicha, Depends(obtener_auditoria_ficha)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    if_match: Annotated[
        str | None,
        Header(
            alias="If-Match",
            description=(
                'ETag de la sección tal como se leyó, por ejemplo "v2". Obligatorio. Vacío o * responde 428.'
                " If-None-Match no se admite al quitar: responde 422"
            ),
        ),
    ] = None,
) -> Response:
    # If-None-Match no se declara como parámetro (el contrato solo declara If-Match), pero se rechaza
    try:
        precondicion = precondicion_para_quitar(if_match, request.headers.get("If-None-Match"))
    except PrecondicionInvalida as error:
        raise _error_precondicion(error) from None
    except FaltaPrecondicion:
        raise _falta_version() from None
    try:
        conflicto = quitar_seccion(
            _peticion(request, autorizada), autorizada.seccion, precondicion, repositorio, cifrador, auditoria, reloj
        )
    except ErrorCifrado as error:
        raise _error_cifrado(error) from None
    if conflicto is not None:
        return _version_desactualizada(request, conflicto)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": NO_STORE})

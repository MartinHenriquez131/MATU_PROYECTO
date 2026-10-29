"""Rutas de la ficha de relevo (MATU-12, RF-02). Contrato: docs/api/propuestos/ficha.openapi.yaml.

    GET /v1/personas-cuidadas/{persona_id}/plan/ficha           admin, cuidador y pagador con puede_ver_plan. 200
    PUT /v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}   admin y cuidador. 201 si se crea, 200 si se actualiza

El rol, la persona, el campo, el consentimiento y la custodia se verifican en las dependencias
(api/dependencias.py), antes de leer el cuerpo. Después el cuerpo (422) y recién entonces la
precondición, paso 8 del orden del contrato (MATU-13, RF-04, ADR-015):
- Sin If-Match ni If-None-Match, o con If-Match: *, 428 /errores/falta-version.
- Las dos a la vez, o If-None-Match distinto de *, 422 (errores[] nombra la cabecera, no el valor).
- If-Match desactualizado, If-Match sobre un campo nunca escrito, o If-None-Match: * sobre un campo
  que ya existe: 412 /errores/version-desactualizada con ``campo`` y ``actual`` (el contenido
  vigente, descifrado). El 412 se devuelve como respuesta, no como excepción, para que la
  transacción confirme el plan.leer que registra esa lectura (MATU-14). No hay fusión automática.
La auditoría plan.leer y plan.editar es de MATU-14, sobre RegistroAuditoria.

Ni el texto ni nada derivado de él llega a los logs: la línea de la petición lleva la plantilla de la
ruta, el usuario y el grupo; los errores del cifrado tienen mensajes fijos; y un 422 nombra el campo,
nunca el valor. Las respuestas con texto llevan Cache-Control: no-store.
"""

import logging
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.errores import ErrorMATU, respuesta_problema
from app.modules.care_plan.api.dependencias import (
    CampoAutorizado,
    FichaAutorizada,
    campo_para_escribir,
    cifrador_para_escribir,
    cifrador_para_leer,
    ficha_para_leer,
    obtener_auditoria_ficha,
    obtener_repositorio_ficha,
)
from app.modules.care_plan.api.esquemas import (
    AutorVista,
    CampoGuardadoVista,
    CamposVista,
    Completitud,
    EstadoCampoVista,
    FichaVista,
    ProblemaFaltaVersionVista,
    ProblemaVersionVista,
    SolicitudCampo,
)
from app.modules.care_plan.application.ficha import (
    CampoEnConflicto,
    PeticionFicha,
    PlanNoDisponible,
    VacioSinCrear,
    guardar_campo,
    leer_ficha,
)
from app.modules.care_plan.application.ports import AuditoriaFicha, CifradorSecciones, RepositorioFicha
from app.modules.care_plan.domain.cifrado import ClaveDestruida, ClaveNoDisponible, ErrorCifrado
from app.modules.care_plan.domain.ficha import (
    Autor,
    CampoFicha,
    EstadoCampo,
    FaltaPrecondicion,
    PrecondicionInvalida,
    etag,
    precondicion_de,
)
from app.modules.iam.api.dependencias import obtener_reloj
from app.shared.puertos import Reloj

log = logging.getLogger("matu.care_plan.ficha")

router = APIRouter(tags=["ficha"])

RUTA_FICHA = "/personas-cuidadas/{persona_id}/plan/ficha"
RUTA_CAMPO = RUTA_FICHA + "/{campo}"

NO_STORE = "no-store"

# Respuestas de error que se declaran en el OpenAPI generado, como en el contrato
_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_ERRORES_LECTURA: dict[int | str, dict[str, Any]] = {
    401: {"description": "Falta el access token, o es inválido o vencido", **_PROBLEMA},
    403: {"description": "Sin consentimiento vigente para plan_cuidado, o revisión anual vencida", **_PROBLEMA},
    404: {"description": "No miembro, rol que no alcanza, persona de otro grupo o inexistente", **_PROBLEMA},
    500: {"description": "Error inesperado o sección ilegible, sin el texto", **_PROBLEMA},
    503: {"description": "La custodia de la clave maestra no está configurada", **_PROBLEMA},
}


def _esquema_en_linea(modelo: type[BaseModel]) -> dict[str, Any]:
    """El esquema del modelo para el OpenAPI, con referencias a componentes que ya registra la ficha.

    Solo admite modelos anidados que FichaVista ya registra (EstadoCampoVista y AutorVista): así no
    queda un $ref colgando.
    """
    esquema = modelo.model_json_schema(ref_template="#/components/schemas/{model}", mode="serialization")
    anidados = set(esquema.pop("$defs", {}))
    if not anidados <= {"EstadoCampoVista", "AutorVista"}:
        raise ValueError("el problema usa un modelo que la ficha no registra en el OpenAPI")
    return esquema


_X_REQUEST_ID: dict[str, Any] = {
    "description": "Identificador de la petición (UUID), el mismo request_id de los logs y del problema",
    "schema": {"type": "string", "format": "uuid"},
}
_NO_STORE: dict[str, Any] = {
    "description": "La respuesta lleva texto de la ficha y no se guarda en ninguna caché",
    "schema": {"type": "string", "const": NO_STORE},
}
_ETAG: dict[str, Any] = {
    "description": 'Versión del campo recién guardado, por ejemplo "v4". Se envía tal cual en el próximo If-Match',
    "schema": {"type": "string"},
}
_ETAG_ACTUAL: dict[str, Any] = {
    "description": "Versión actual del campo. Ausente si el campo nunca se escribió",
    "required": False,
    "schema": {"type": "string"},
}
_CABECERAS_GUARDADO: dict[str, Any] = {"X-Request-ID": _X_REQUEST_ID, "ETag": _ETAG, "Cache-Control": _NO_STORE}

_EJEMPLO_412: dict[str, Any] = {
    "type": "/errores/version-desactualizada",
    "title": "Otra persona cambió este contenido",
    "status": 412,
    "detail": "Pedro guardó este campo mientras lo editabas. Revisa su versión antes de guardar la tuya",
    "errores": [],
    "request_id": "9b2f4c1e-0000-4000-8000-0000000000e4",
    "campo": "rutina",
    "actual": {
        "texto": "8:00 se levanta y toma desayuno en la cocina.\n13:00 almuerza con Pedro los domingos.",
        "etag": '"v4"',
        "actualizado_por": {"id": "0c4b5a10-0000-4000-8000-00000000000d", "nombre": "Pedro"},
        "actualizado_en": "2026-10-30T18:01:00Z",
    },
}
_EJEMPLO_428: dict[str, Any] = {
    "type": "/errores/falta-version",
    "title": "Falta la versión del contenido",
    "status": 428,
    "detail": "Vuelve a abrir el campo y guarda de nuevo",
    "errores": [],
    "request_id": "9b2f4c1e-0000-4000-8000-0000000000e6",
}

_ERRORES_ESCRITURA: dict[int | str, dict[str, Any]] = {
    **_ERRORES_LECTURA,
    200: {"description": "Campo actualizado, con If-Match", "headers": _CABECERAS_GUARDADO},
    201: {
        "description": "Campo creado: primera escritura, con If-None-Match: *",
        "model": CampoGuardadoVista,
        "headers": _CABECERAS_GUARDADO,
    },
    412: {
        "description": (
            "Otra persona guardó el campo después de que lo leíste (If-Match desactualizado), lo creó antes que"
            " tú (If-None-Match: * sobre un campo que ya existe), o enviaste If-Match sobre un campo que nunca se"
            " escribió (actual.etag null). `actual` trae el contenido vigente para que la persona decida: no hay"
            " fusión automática (ADR-015). Leer `actual` queda auditado como plan.leer"
        ),
        "headers": {"X-Request-ID": _X_REQUEST_ID, "ETag": _ETAG_ACTUAL, "Cache-Control": _NO_STORE},
        "content": {
            "application/problem+json": {"schema": _esquema_en_linea(ProblemaVersionVista), "example": _EJEMPLO_412}
        },
    },
    422: {
        "description": (
            "Cuerpo inválido (texto falta, supera 500 caracteres o trae caracteres de control, o hay un campo"
            " extra); llegaron If-Match e If-None-Match a la vez (tipo precondicion_doble); If-None-Match distinto"
            " de * (tipo precondicion_invalida); o texto vacío con If-None-Match: * (tipo vacio_sin_crear)."
            " errores[] nombra el campo o la cabecera, nunca el valor"
        ),
        "headers": {"X-Request-ID": _X_REQUEST_ID},
        **_PROBLEMA,
    },
    428: {
        "description": "La escritura no fue condicional: faltan If-Match e If-None-Match, o vino If-Match vacío o *",
        "headers": {"X-Request-ID": _X_REQUEST_ID},
        "content": {
            "application/problem+json": {
                "schema": _esquema_en_linea(ProblemaFaltaVersionVista),
                "example": _EJEMPLO_428,
            }
        },
    },
}

_DESCRIPCION_PUT = """Escribe **un** campo. Toda escritura es condicional (MATU-13, ADR-015) y lleva exactamente una
de dos cabeceras:

| Situación | Cabecera | Si otra persona se adelantó |
|---|---|---|
| El campo nunca se escribió (`etag: null` en la lectura) | `If-None-Match: *` | 412 con lo que ella guardó |
| El campo ya existe | `If-Match: "<etag leído>"` | 412 con el contenido actual |

- Sin ninguna, o con `If-Match` vacío o `*`, responde **428**.
- `If-Match` sobre un campo que nunca se escribió responde **412** con `actual.etag: null`.
- Las dos a la vez, o `If-None-Match` distinto de `*`, responde **422**.
- `texto` vacío con `If-Match` vacía el campo, que conserva su `etag`. Con `If-None-Match: *`, **422**
  `vacio_sin_crear`.

Orden de evaluación: 401, 404 (grupo, rol, persona, campo), 403 (consentimiento), 503 (custodia), 422 (cuerpo
y cabeceras) y al final la precondición (428 o 412). Responde **201** si creó el campo y **200** si lo
actualizó. Escriben `admin` y `cuidador`. Registra `plan.editar`; el 412, `plan.leer`.
"""

_MENSAJES_PRECONDICION = {
    "precondicion_doble": "envía If-Match o If-None-Match, no las dos",
    "precondicion_invalida": "If-None-Match solo admite *",
}


def _peticion(request: Request, ficha: FichaAutorizada) -> PeticionFicha:
    return PeticionFicha(
        grupo_id=ficha.contexto.grupo_id,
        usuario_id=ficha.contexto.usuario_id,
        persona_cuidada_id=ficha.persona_id,
        request_id=getattr(request.state, "request_id", None),
    )


def _error_cifrado(error: ErrorCifrado) -> ErrorMATU:
    """Traduce un error del cifrado sin el texto ni la clave: todos tienen mensaje fijo.

    - Clave destruida (borrado criptográfico): 404, como una persona eliminada.
    - La custodia no envolvió o no desenvolvió la DEK (por ejemplo, la KEK cambió sin cambiar su
      versión): 503 genérico. Nunca se crea una DEK nueva.
    - Sección ilegible (alterada o movida) o clave inexistente con secciones guardadas: 500 genérico.
    """
    log.warning("la ficha no se pudo cifrar o descifrar", extra={"tipo_error": type(error).__name__})
    if isinstance(error, ClaveDestruida):
        return ErrorMATU(404)
    if isinstance(error, ClaveNoDisponible):
        return ErrorMATU(503, detalle="La ficha no está disponible en este momento. Cita el request_id si lo reportas")
    return ErrorMATU(500, detalle="No pudimos abrir la ficha. Cita el request_id si lo reportas")


def _completitud(valor: int) -> Completitud:
    # domain.ficha.completitud solo devuelve 0, 33, 67 o 100; el esquema lo vuelve a validar
    return cast(Completitud, valor)


def _autor(autor: Autor | None) -> AutorVista | None:
    return None if autor is None else AutorVista(id=autor.id, nombre=autor.nombre)


def _estado(campo: EstadoCampo) -> EstadoCampoVista:
    return EstadoCampoVista(
        texto=campo.texto,
        etag=None if campo.version is None else etag(campo.version),
        actualizado_por=_autor(campo.actualizado_por),
        actualizado_en=campo.actualizado_en,
    )


@router.get(RUTA_FICHA, response_model=FichaVista, responses=_ERRORES_LECTURA)
def leer(
    request: Request,
    response: Response,
    ficha: Annotated[FichaAutorizada, Depends(ficha_para_leer)],
    cifrador: Annotated[CifradorSecciones, Depends(cifrador_para_leer)],
    repositorio: Annotated[RepositorioFicha, Depends(obtener_repositorio_ficha)],
    auditoria: Annotated[AuditoriaFicha, Depends(obtener_auditoria_ficha)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> FichaVista:
    try:
        resultado = leer_ficha(_peticion(request, ficha), repositorio, cifrador, auditoria, reloj)
    except ErrorCifrado as error:
        raise _error_cifrado(error) from None
    response.headers["Cache-Control"] = NO_STORE
    campos = resultado.campos
    return FichaVista(
        persona_id=resultado.persona_cuidada_id,
        completitud=_completitud(resultado.completitud),
        actualizado_en=resultado.actualizado_en,
        campos=CamposVista(
            rutina=_estado(campos[CampoFicha.RUTINA]),
            manejo_situaciones=_estado(campos[CampoFicha.MANEJO_SITUACIONES]),
            red_apoyo=_estado(campos[CampoFicha.RED_APOYO]),
        ),
    )


def _version_desactualizada(request: Request, conflicto: CampoEnConflicto) -> JSONResponse:
    """412 con el contenido vigente (contrato, decisión 8). Se devuelve, no se lanza: así se confirma
    la transacción con el plan.leer de esa lectura. El texto va solo en el cuerpo, nunca en un log."""
    actual = conflicto.actual
    if actual.version is None:
        detalle = "Este campo no tiene una versión guardada. Vuelve a abrirlo antes de guardar"
    else:
        quien = actual.actualizado_por.nombre if actual.actualizado_por is not None else "Otra persona"
        detalle = f"{quien} guardó este campo mientras lo editabas. Revisa su versión antes de guardar la tuya"
    cabeceras = {"Cache-Control": NO_STORE}
    if actual.version is not None:
        cabeceras["ETag"] = etag(actual.version)
    return respuesta_problema(
        request,
        status.HTTP_412_PRECONDITION_FAILED,
        detalle=detalle,
        headers=cabeceras,
        extension={"campo": conflicto.campo.value, "actual": _estado(actual).model_dump(mode="json")},
    )


@router.put(
    RUTA_CAMPO,
    response_model=CampoGuardadoVista,
    responses=_ERRORES_ESCRITURA,
    summary="Guardar un campo de la ficha",
    description=_DESCRIPCION_PUT,
)
def guardar(
    request: Request,
    response: Response,
    autorizado: Annotated[CampoAutorizado, Depends(campo_para_escribir)],
    cifrador: Annotated[CifradorSecciones, Depends(cifrador_para_escribir)],
    repositorio: Annotated[RepositorioFicha, Depends(obtener_repositorio_ficha)],
    auditoria: Annotated[AuditoriaFicha, Depends(obtener_auditoria_ficha)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    solicitud: SolicitudCampo,
    if_match: Annotated[
        str | None,
        Header(
            alias="If-Match",
            description=(
                'ETag del campo tal como se leyó, por ejemplo "v3". Obligatorio si el campo ya existe. Un solo'
                " valor, comparado en forma fuerte: otro valor no coincide y responde 412. Vacío o * responde 428"
            ),
        ),
    ] = None,
    if_none_match: Annotated[
        str | None,
        Header(
            alias="If-None-Match",
            description=(
                "Solo *, en la primera escritura de un campo que nunca se escribió. Otro valor responde 422,"
                " y enviarla junto con If-Match también"
            ),
        ),
    ] = None,
) -> CampoGuardadoVista | JSONResponse:
    try:
        precondicion = precondicion_de(if_match, if_none_match)
    except PrecondicionInvalida as error:
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[{"campo": error.cabecera, "mensaje": _MENSAJES_PRECONDICION[error.tipo], "tipo": error.tipo}],
        ) from None
    except FaltaPrecondicion:
        raise ErrorMATU(428, detalle="Vuelve a abrir el campo y guarda de nuevo") from None
    try:
        guardado = guardar_campo(
            _peticion(request, autorizado.ficha),
            autorizado.campo,
            solicitud.texto,
            precondicion,
            repositorio,
            cifrador,
            auditoria,
            reloj,
        )
    except VacioSinCrear:
        raise ErrorMATU(
            422,
            detalle="Revisa los campos indicados",
            errores=[{"campo": "texto", "mensaje": "un campo que nunca se escribió no se crea vacío",
                      "tipo": "vacio_sin_crear"}],
        ) from None
    except ErrorCifrado as error:
        raise _error_cifrado(error) from None
    except PlanNoDisponible:
        log.error("no se pudo crear ni leer el plan de cuidado")
        raise ErrorMATU(500, detalle="No pudimos guardar la ficha. Cita el request_id si lo reportas") from None
    if isinstance(guardado, CampoEnConflicto):
        return _version_desactualizada(request, guardado)

    estado = guardado.estado
    assert estado.version is not None and estado.actualizado_por is not None and estado.actualizado_en is not None
    etag_nuevo = etag(estado.version)
    response.status_code = status.HTTP_201_CREATED if guardado.creado else status.HTTP_200_OK
    response.headers["ETag"] = etag_nuevo
    response.headers["Cache-Control"] = NO_STORE
    return CampoGuardadoVista(
        campo=guardado.campo.value,
        texto=estado.texto,
        etag=etag_nuevo,
        actualizado_por=AutorVista(id=estado.actualizado_por.id, nombre=estado.actualizado_por.nombre),
        actualizado_en=estado.actualizado_en,
        completitud=_completitud(guardado.completitud),
    )

"""Rutas de la ficha de relevo (MATU-12, RF-02). Contrato: docs/api/propuestos/ficha.openapi.yaml.

    GET /v1/personas-cuidadas/{persona_id}/plan/ficha           admin, cuidador y pagador con puede_ver_plan. 200
    PUT /v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}   admin y cuidador. 201 si se crea, 200 si se actualiza

El rol, la persona, el campo, el consentimiento y la custodia se verifican en las dependencias
(api/dependencias.py), antes de leer el cuerpo. Queda fuera de MATU-12, y el contrato lo promete:
- If-Match / If-None-Match con 412 y 428 (MATU-13). El ETag de cada campo ya se devuelve.
- La auditoría plan.leer y plan.editar (MATU-14). Ya se llama al puerto AuditoriaFicha.

Ni el texto ni nada derivado de él llega a los logs: la línea de la petición lleva la plantilla de la
ruta, el usuario y el grupo; los errores del cifrado tienen mensajes fijos; y un 422 nombra el campo,
nunca el valor. Las respuestas con texto llevan Cache-Control: no-store.
"""

import logging
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.errores import ErrorMATU
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
    SolicitudCampo,
)
from app.modules.care_plan.application.ficha import (
    PeticionFicha,
    PlanNoDisponible,
    VacioSinCrear,
    guardar_campo,
    leer_ficha,
)
from app.modules.care_plan.application.ports import AuditoriaFicha, CifradorSecciones, RepositorioFicha
from app.modules.care_plan.domain.cifrado import ClaveDestruida, ClaveNoDisponible, ErrorCifrado
from app.modules.care_plan.domain.ficha import Autor, CampoFicha, EstadoCampo, etag
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
    503: {"description": "La custodia de la clave maestra no está configurada", **_PROBLEMA},
}
_ERRORES_ESCRITURA: dict[int | str, dict[str, Any]] = {
    **_ERRORES_LECTURA,
    201: {"description": "Campo creado: primera escritura", "model": CampoGuardadoVista},
    422: {"description": "Cuerpo inválido. errores[] nombra el campo, nunca el valor", **_PROBLEMA},
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


@router.put(RUTA_CAMPO, response_model=CampoGuardadoVista, responses=_ERRORES_ESCRITURA)
def guardar(
    request: Request,
    response: Response,
    autorizado: Annotated[CampoAutorizado, Depends(campo_para_escribir)],
    cifrador: Annotated[CifradorSecciones, Depends(cifrador_para_escribir)],
    repositorio: Annotated[RepositorioFicha, Depends(obtener_repositorio_ficha)],
    auditoria: Annotated[AuditoriaFicha, Depends(obtener_auditoria_ficha)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
    solicitud: SolicitudCampo,
) -> CampoGuardadoVista:
    try:
        guardado = guardar_campo(
            _peticion(request, autorizado.ficha),
            autorizado.campo,
            solicitud.texto,
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

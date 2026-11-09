"""GET /v1/politica (MATU-75): la política de privacidad vigente, pública.

Condiciones del analista normativo: sin sesión, sin cookies, sin auditoría y sin registrar quién la lee. La línea de
log de la petición es la de toda ruta (método, plantilla, estado y duración); el texto nunca va a un log.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.config import obtener_configuracion
from app.core.errores import ErrorMATU
from app.modules.iam.api.esquemas import PoliticaVista
from app.modules.iam.api.sesion_web import PROBLEMA
from app.modules.iam.application.politica import politica_vigente
from app.modules.iam.domain.politica import PoliticaNoDisponible, PoliticaVigente
from app.modules.iam.infrastructure.textos_politica import texto_publicado

log = logging.getLogger("matu.iam")

router = APIRouter(tags=["politica"])

DETALLE_NO_DISPONIBLE = (
    "La política de privacidad no está disponible en este momento. Cita el request_id si lo reportas"
)


def obtener_politica_vigente() -> PoliticaVigente | None:
    """La política vigente según la configuración, o None si no se puede servir (el motivo va al log, sin valores).

    No lanza: cada ruta decide. GET /v1/politica y POST /v1/usuarios responden 503 con None, después de validar el
    cuerpo, y el resto de la API no depende de ella.
    """
    configuracion = obtener_configuracion()
    try:
        politica = politica_vigente(
            version=configuracion.politica_version,
            actualizada_en=configuracion.politica_actualizada_en,
            correo=configuracion.correo_privacidad,
            texto_de=texto_publicado,
        )
    except PoliticaNoDisponible as error:
        log.error("politica no disponible: %s", error.motivo)
        return None
    if politica.correo_contacto is not None and politica.correo_contacto not in politica.texto:
        # La pantalla mostraría un correo en «Tu cuenta» y otro en la política. Se publica igual (el texto está
        # completo), y el aviso queda en el log sin el valor. tests/modules/iam/test_politica.py lo verifica con el
        # valor de .env.example
        log.warning("CORREO_PRIVACIDAD no aparece en el texto de la política")
    return politica


PoliticaDep = Annotated[PoliticaVigente | None, Depends(obtener_politica_vigente)]


def politica_o_503(politica: PoliticaVigente | None) -> PoliticaVigente:
    if politica is None:
        raise ErrorMATU(503, detalle=DETALLE_NO_DISPONIBLE)
    return politica


@router.get(
    "/politica",
    response_model=PoliticaVista,
    description=(
        "La política de privacidad vigente (MATU-75): versión, fecha, huella y texto en Markdown. Pública: sin"
        " sesión, sin cookies y sin auditoría. La huella es el SHA-256 del texto exacto que se entrega, y es la que"
        " POST /v1/usuarios acepta en huella_politica. correo_contacto es CORREO_PRIVACIDAD, o null. Cache-Control:"
        " no-cache (decisión 175). 503 si falta POLITICA_VERSION o POLITICA_ACTUALIZADA_EN, si la versión no tiene un"
        " texto publicado con su huella, o si el texto todavía tiene un marcador (decisión 174)."
    ),
    responses={
        200: {
            "headers": {
                "Cache-Control": {"description": "no-cache: se revalida cada vez", "schema": {"type": "string"}}
            }
        },
        503: {"description": "La política no se puede servir. El motivo va al log, nunca a la respuesta", **PROBLEMA},
    },
)
def ver_politica(respuesta: Response, politica: PoliticaDep) -> PoliticaVista:
    vigente = politica_o_503(politica)
    respuesta.headers["Cache-Control"] = "no-cache"
    return PoliticaVista(
        version=vigente.version,
        actualizada_en=vigente.actualizada_en,
        huella=vigente.huella,
        texto=vigente.texto,
        correo_contacto=vigente.correo_contacto,
    )

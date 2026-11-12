"""GET /v1/condiciones-pedido (MATU-61, D6, R13; decisión 207): las condiciones del pedido vigentes, públicas.

Como GET /v1/politica (decisiones 173 a 175): sin sesión, sin cookies, sin auditoría y sin registrar quién las lee.
MATU-62 (decisión 240): ?version= entrega una versión publicada alguna vez (la que aceptó quien pagó); otra, 404; con
otro formato, 422. Es un número de versión, no un dato de nadie.
Cache-Control: no-cache, no no-store: no tienen datos de nadie. Es capa 3: va en ROUTERS_CAPA_3.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Query, Response

from app.core.errores import ErrorMATU
from app.modules.ordering.api.esquemas import CondicionesPedidoVista
from app.modules.ordering.infrastructure.condiciones import (
    VERSION_VIGENTE,
    CondicionesNoDisponibles,
    VersionNoPublicada,
    condiciones_de,
)

router = APIRouter(tags=["condiciones"])

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}


@router.get(
    "/condiciones-pedido",
    response_model=CondicionesPedidoVista,
    responses={
        200: {
            "headers": {
                "Cache-Control": {"description": "no-cache: se revalida cada vez", "schema": {"type": "string"}}
            }
        },
        404: {"description": "MATU-62: esa versión nunca se publicó", **_PROBLEMA},
        422: {"description": "MATU-62: version no tiene la forma MAYOR.MENOR", **_PROBLEMA},
        503: {"description": "El texto publicado no está o no calza con su huella", **_PROBLEMA},
    },
    summary="Las condiciones del pedido vigentes, con su versión y su huella",
    description=(
        "MATU-61 (decisión 207, D6). Pública: sin sesión, sin cookies y sin auditoría. La huella es el SHA-256 del"
        " texto exacto que se entrega, la que el resumen del pedido muestra. Versión propia, separada de la política."
        " Cache-Control: no-cache. MATU-62 (decisión 240): con ?version=, una versión publicada alguna vez. Capa 3"
    ),
)
def ver_condiciones(
    respuesta: Response,
    version: Annotated[str | None, Query(pattern=r"^[0-9]+\.[0-9]+$", max_length=9)] = None,
) -> CondicionesPedidoVista:
    try:
        vigentes = condiciones_de(version or VERSION_VIGENTE)
    except VersionNoPublicada:
        raise ErrorMATU(404) from None
    except CondicionesNoDisponibles:
        raise ErrorMATU(503, detalle="Las condiciones del pedido no están disponibles en este momento") from None
    respuesta.headers["Cache-Control"] = "no-cache"
    return CondicionesPedidoVista(
        version=vigentes.version, actualizada_en=vigentes.actualizada_en, huella=vigentes.huella, texto=vigentes.texto
    )

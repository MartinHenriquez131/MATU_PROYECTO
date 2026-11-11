"""Ruta del catálogo (MATU-59, RF-20, decisiones 158 a 167 de docs/api/README.md). Contrato: docs/api/openapi.json.

    GET /v1/catalogo    cualquier sesión de familia (access token). 200

Es capa 3: va en ROUTERS_CAPA_3 de app/main.py y se monta solo con CAPA3_HABILITADA. Pide solo el access token
(usuario_actual, de iam): el catálogo es general, sin X-Grupo-Id, grupo ni persona, y catalog no importa
care_circle (FLECHAS de tests/test_arquitectura.py). El relevo no tiene access token: su sesión es la cookie de
/v1/relevo/, así que aquí recibe 401. Orden: 401 y 200.

Lectura pura: sin auditoría (condición 3), sin eventos, sin parámetros de consulta y sin texto libre en la URL.
Nada del catálogo va a los logs: la línea de la petición lleva la plantilla de la ruta.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.modules.catalog.api.esquemas import (
    Catalogo,
    CategoriaCatalogo,
    OfertaCatalogo,
    ProductoCatalogo,
)
from app.modules.catalog.application.catalogo import leer_catalogo
from app.modules.catalog.application.ports import CatalogoComercio, RepositorioCatalogo
from app.modules.catalog.domain import catalogo as dominio
from app.modules.catalog.infrastructure.catalogo_simulado import CatalogoComercioSimulado
from app.modules.catalog.infrastructure.repositorio_catalogo import RepositorioCatalogoSQL
from app.modules.iam.api.dependencias import SesionDeUsuario

router = APIRouter(tags=["catálogo"])

RUTA = "/catalogo"

# Decisión 165: general (igual para todos), pero detrás de una sesión. private para que ninguna caché compartida
# lo guarde; 60 segundos para que el stock mostrado no quede viejo
CACHE_CATALOGO = "private, max-age=60"

_PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}
_401 = {
    "description": "Falta el access token, o es inválido o vencido. También la sesión del relevo, que no tiene uno",
    **_PROBLEMA,
}


def obtener_catalogo_comercio() -> CatalogoComercio:
    """El adaptador de CatalogoComercio. Hoy, el simulado (sin convenio). Las pruebas lo pueden sobreescribir."""
    return CatalogoComercioSimulado()


def obtener_repositorio_catalogo(sesion: SesionDeUsuario) -> RepositorioCatalogo:
    return RepositorioCatalogoSQL(sesion)


def _vista(catalogo: dominio.Catalogo) -> Catalogo:
    return Catalogo(
        precios_de_ejemplo=catalogo.precios_de_ejemplo,
        categorias=[
            CategoriaCatalogo(
                id=categoria.id,
                nombre=categoria.nombre,
                orden=categoria.orden,
                productos=[
                    ProductoCatalogo(
                        id=producto.id,
                        nombre=producto.nombre,
                        presentacion=producto.presentacion,
                        unidad=producto.unidad,
                        unidades_por_envase=producto.unidades_por_envase,
                        retracto_pierde_al_abrir=producto.retracto_pierde_al_abrir,
                        comercios=[
                            OfertaCatalogo(
                                oferta_id=oferta.oferta_id,
                                comercio_id=oferta.comercio_id,
                                nombre_fantasia=oferta.nombre_fantasia,
                                precio=oferta.precio,
                                disponible=oferta.disponible,
                                ficticio=oferta.ficticio,
                            )
                            for oferta in producto.comercios
                        ],
                    )
                    for producto in categoria.productos
                ],
            )
            for categoria in catalogo.categorias
        ],
    )


@router.get(
    RUTA,
    response_model=Catalogo,
    responses={401: _401},
    summary="Ver el catálogo",
    description=(
        "El catálogo curado (MATU-59, RF-20, ADR-027): categorías con sus productos y, por producto, cada comercio"
        " con su precio exacto en pesos enteros con IVA y si hay stock (disponible), nunca la cantidad (decisión 161),"
        " por nombre_fantasia y nunca por precio. Entran"
        " solo productos con al menos una oferta publicada de un comercio activo. Del comercio viajan solo"
        " comercio_id y nombre_fantasia. precios_de_ejemplo es true mientras no haya convenio. Lo ve cualquier"
        " sesión de familia, sin X-Grupo-Id y sin autorización de consumo ni de pedidos; el relevo no (401). Sin"
        " parámetros de consulta. No se audita. Cache-Control: private, max-age=60. Es capa 3: existe solo con"
        " CAPA3_HABILITADA=true"
    ),
)
def ver_catalogo(
    response: Response,
    repositorio: Annotated[RepositorioCatalogo, Depends(obtener_repositorio_catalogo)],
    comercios: Annotated[CatalogoComercio, Depends(obtener_catalogo_comercio)],
) -> Catalogo:
    catalogo = leer_catalogo(repositorio, comercios)
    response.headers["Cache-Control"] = CACHE_CATALOGO
    return _vista(catalogo)

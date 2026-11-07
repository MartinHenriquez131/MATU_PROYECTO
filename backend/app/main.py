"""Punto de entrada de la API de MATU.

Ejecutar desde backend/:

    uvicorn app.main:app --reload

Cada historia registra su router aquí, con el prefijo /v1. Para no chocar entre ramas,
agrega una sola línea por router en el bloque marcado.

Los routers de la capa 3, el despacho (catalog, ordering, payments, fulfillment, settlement y lo que
dependa de ellos), no se importan arriba: van en ROUTERS_CAPA_3 y se montan solo con CAPA3_HABILITADA
(MATU-40, ADR-002). Así la API arranca sin la capa 3, aunque sus paquetes no existan.
tests/test_capa3_desacoplable.py lo verifica.
"""

import importlib
import logging
from typing import TextIO

from fastapi import APIRouter, FastAPI

from app.core.cabeceras import CABECERAS_RELEVO, PREFIJO_RELEVO, MiddlewareCabecerasPrefijo
from app.core.config import ENTORNOS_DOCUMENTACION, obtener_configuracion
from app.core.errores import registrar_manejadores
from app.core.logs import MiddlewareRequestId, configurar_logs
from app.core.web import montar_app_familia, montar_pagina_relevo
from app.modules.care_circle.api.router import router as router_grupos
from app.modules.care_circle.api.router_autorizaciones import router as router_autorizaciones
from app.modules.care_circle.api.router_personas import router as router_personas
from app.modules.care_circle.domain.personas import FINALIDAD_CONSUMO, FINALIDAD_PLAN_CUIDADO
from app.modules.care_circle.infrastructure.efectos_retiro import registrar_efecto
from app.modules.care_plan.api.dependencias import preparar_custodia
from app.modules.care_plan.api.router import router as router_ficha
from app.modules.care_plan.api.router_relevo import router as router_relevo
from app.modules.care_plan.api.router_relevo_publico import router as router_relevo_publico
from app.modules.care_plan.api.router_secciones import router as router_secciones
from app.modules.care_plan.infrastructure.efecto_retiro import EfectoRetiroFicha
from app.modules.consumption.api.router import router as router_consumo
from app.modules.consumption.api.router_alertas import router as router_alertas
from app.modules.consumption.api.router_lista import router as router_lista
from app.modules.consumption.infrastructure.efecto_retiro import EfectoRetiroConsumo
from app.modules.iam.api.router import router as router_iam
from app.modules.iam.api.router_recuperacion import router as router_recuperacion
from app.modules.iam.api.router_sesiones import router as router_sesiones
from app.modules.notifications.api.router import router as router_avisos

log = logging.getLogger("matu.api.arranque")

router_salud = APIRouter(tags=["salud"])

# Routers de la capa 3 (MATU-40, ADR-002), como "paquete.del.router:atributo". Se importan al armar la
# app y solo con CAPA3_HABILITADA: nunca en el nivel superior de este archivo. Hoy está vacío porque la
# capa 3 todavía no tiene routers. Ejemplo: "app.modules.ordering.api.router:router"
ROUTERS_CAPA_3: tuple[str, ...] = ()


@router_salud.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok"}


def incluir_capa_3(app: FastAPI) -> None:
    """Monta los routers de ROUTERS_CAPA_3 con el prefijo /v1. Solo se llama con CAPA3_HABILITADA."""
    for referencia in ROUTERS_CAPA_3:
        modulo, _, atributo = referencia.partition(":")
        app.include_router(getattr(importlib.import_module(modulo), atributo), prefix="/v1")


def crear_app(stream_logs: TextIO | None = None) -> FastAPI:
    config = obtener_configuracion()
    configurar_logs(config.log_nivel, stream_logs)
    # MATU-25 (decisión 105, (j)): el arranque registra el entorno, y nada más de la configuración. Sin
    # "entorno=staging" en el log, un despliegue de staging no se da por bueno. Va en WARNING para que se
    # vea aunque LOG_NIVEL=WARNING: el despliegue siempre deja la marca
    log.warning("entorno=%s", config.entorno)
    # MATU-12: la custodia de la KEK se arma al arrancar. Si está encendida fuera de su lista permitida,
    # la API no arranca; si está encendida, deja un WARNING (decisión D-A)
    preparar_custodia()
    # MATU-44 (decisión 124): lo que corta el retiro de cada autorización. care_circle no importa care_plan
    # ni consumption: aquí se arman. Sin el efecto de una finalidad, su retiro falla cerrado
    registrar_efecto(FINALIDAD_PLAN_CUIDADO, EfectoRetiroFicha)
    registrar_efecto(FINALIDAD_CONSUMO, EfectoRetiroConsumo)

    # MATU-58 (decisión 115): /docs y /openapi.json solo en local y pruebas. En staging y produccion no
    # existen y responden 404 RFC 7807, sin caer en la app de familia
    documentacion = config.entorno in ENTORNOS_DOCUMENTACION
    app = FastAPI(
        title="MATU API",
        version="0.1.0",
        docs_url="/docs" if documentacion else None,
        redoc_url=None,
        openapi_url="/openapi.json" if documentacion else None,
    )
    registrar_manejadores(app)
    # MATU-19 (C11): no-store, no-referrer y noindex en toda respuesta bajo /v1/relevo/, también errores
    app.add_middleware(MiddlewareCabecerasPrefijo, prefijo=PREFIJO_RELEVO, cabeceras=CABECERAS_RELEVO)
    # MATU-38: no-store en toda respuesta de sesión y dispositivos, también en los 401, 422 y 429
    # MATU-36: también bajo /v1/personas-cuidadas/ (autorización, consumo y ficha), en los 403 y 404
    # MATU-57: también la recuperación del acceso y la cuenta. MATU-41: la preferencia de avisos (/v1/yo/)
    for prefijo in (
        "/v1/sesiones", "/v1/dispositivos", "/v1/personas-cuidadas/", "/v1/recuperacion", "/v1/cuenta", "/v1/yo/"
    ):
        app.add_middleware(MiddlewareCabecerasPrefijo, prefijo=prefijo, cabeceras={"Cache-Control": "no-store"})
    app.add_middleware(MiddlewareRequestId)

    # Routers por historia (una línea cada uno)
    app.include_router(router_salud, prefix="/v1")
    app.include_router(router_iam, prefix="/v1")
    app.include_router(router_sesiones, prefix="/v1")
    app.include_router(router_recuperacion, prefix="/v1")
    app.include_router(router_grupos, prefix="/v1")
    app.include_router(router_personas, prefix="/v1")
    app.include_router(router_ficha, prefix="/v1")
    app.include_router(router_secciones, prefix="/v1")
    app.include_router(router_relevo, prefix="/v1")
    app.include_router(router_relevo_publico, prefix="/v1")
    app.include_router(router_autorizaciones, prefix="/v1")
    # Antes que router_consumo: por-acabarse, alertas y lista (MATU-60) son rutas fijas que {perfil_id} capturaría
    app.include_router(router_alertas, prefix="/v1")
    app.include_router(router_lista, prefix="/v1")
    app.include_router(router_consumo, prefix="/v1")
    app.include_router(router_avisos, prefix="/v1")

    # MATU-40 (ADR-002): la capa 3 se monta aparte y solo si está habilitada. Las capas 1 y 2, arriba,
    # nunca dependen de ella
    if config.capa3_habilitada:
        incluir_capa_3(app)

    # MATU-23: la página /r y sus /assets, después de las rutas de la API para no taparlas
    montar_pagina_relevo(app, config.web_dist)
    # MATU-58: la app de familia en toda ruta GET o HEAD que no sea de la API, /r, /assets ni la
    # documentación. Es el destino por omisión del enrutador: no tapa ninguna ruta, ni las de después
    montar_app_familia(app, config.web_dist)

    return app


app = crear_app()

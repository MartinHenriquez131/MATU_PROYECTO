"""Punto de entrada de la API de MATU.

Ejecutar desde backend/:

    uvicorn app.main:app --reload

Cada historia registra su router aquí, con el prefijo /v1. Para no chocar entre ramas,
agrega una sola línea por router en el bloque marcado.
"""

from typing import TextIO

from fastapi import APIRouter, FastAPI

from app.core.config import obtener_configuracion
from app.core.errores import registrar_manejadores
from app.core.logs import MiddlewareRequestId, configurar_logs
from app.modules.care_circle.api.router import router as router_grupos
from app.modules.care_circle.api.router_personas import router as router_personas
from app.modules.care_plan.api.dependencias import preparar_custodia
from app.modules.care_plan.api.router import router as router_ficha
from app.modules.iam.api.router import router as router_iam

router_salud = APIRouter(tags=["salud"])


@router_salud.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok"}


def crear_app(stream_logs: TextIO | None = None) -> FastAPI:
    config = obtener_configuracion()
    configurar_logs(config.log_nivel, stream_logs)
    # MATU-12: la custodia de la KEK se arma al arrancar. Si está encendida fuera de local o pruebas,
    # la API no arranca; si está encendida, deja un WARNING (decisión D-A)
    preparar_custodia()

    documentacion = config.entorno != "produccion"
    app = FastAPI(
        title="MATU API",
        version="0.1.0",
        docs_url="/docs" if documentacion else None,
        redoc_url=None,
        openapi_url="/openapi.json" if documentacion else None,
    )
    registrar_manejadores(app)
    app.add_middleware(MiddlewareRequestId)

    # Routers por historia (una línea cada uno)
    app.include_router(router_salud, prefix="/v1")
    app.include_router(router_iam, prefix="/v1")
    app.include_router(router_grupos, prefix="/v1")
    app.include_router(router_personas, prefix="/v1")
    app.include_router(router_ficha, prefix="/v1")

    return app


app = crear_app()

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
from app.modules.care_circle.api.router_borrado import router as router_borrado
from app.modules.care_circle.api.router_direccion import router as router_direccion
from app.modules.care_circle.api.router_invitaciones import router as router_invitaciones
from app.modules.care_circle.api.router_invitaciones import router_publico as router_invitacion_publica
from app.modules.care_circle.api.router_miembros import router as router_miembros
from app.modules.care_circle.api.router_personas import router as router_personas
from app.modules.care_circle.domain.personas import FINALIDAD_CONSUMO, FINALIDAD_DESPACHO, FINALIDAD_PLAN_CUIDADO
from app.modules.care_circle.infrastructure.efectos_retiro import registrar_efecto
from app.modules.care_circle.infrastructure.enlaces_relevo import registrar_enlaces
from app.modules.care_plan.api.dependencias import preparar_custodia
from app.modules.care_plan.api.router import router as router_ficha
from app.modules.care_plan.api.router_relevo import router as router_relevo
from app.modules.care_plan.api.router_relevo_publico import router as router_relevo_publico
from app.modules.care_plan.api.router_secciones import router as router_secciones
from app.modules.care_plan.infrastructure.efecto_retiro import EfectoRetiroFicha
from app.modules.care_plan.infrastructure.enlaces_otorgados import EnlacesOtorgados
from app.modules.consumption.api.router import router as router_consumo
from app.modules.consumption.api.router_alertas import router as router_alertas
from app.modules.consumption.api.router_lista import router as router_lista
from app.modules.consumption.api.router_reposicion import router as router_reposicion
from app.modules.consumption.infrastructure.efecto_retiro import EfectoRetiroConsumo
from app.modules.iam.api.router import router as router_iam
from app.modules.iam.api.router_ingresos import router as router_ingresos
from app.modules.iam.api.router_politica import router as router_politica
from app.modules.iam.api.router_recuperacion import router as router_recuperacion
from app.modules.iam.api.router_sesiones import router as router_sesiones
from app.modules.notifications.api.router import router as router_avisos

log = logging.getLogger("matu.api.arranque")

router_salud = APIRouter(tags=["salud"])

# Routers de la capa 3 (MATU-40, ADR-002), como "paquete.del.router:atributo". Se importan al armar la
# app y solo con CAPA3_HABILITADA: nunca en el nivel superior de este archivo. MATU-59 agrega el catálogo
# (GET /v1/catalogo, decisión 167)
ROUTERS_CAPA_3: tuple[str, ...] = (
    "app.modules.catalog.api.router:router",
    # MATU-61: el pedido sin pagar y las condiciones del pedido (decisión 188)
    "app.modules.ordering.api.router:router",
    "app.modules.ordering.api.router_condiciones:router",
    # MATU-62: pagar y las lecturas del pago (decisión 241)
    "app.modules.payments.api.router:router",
)

# MATU-62 (D-62-17, decisión 241): la vuelta de Webpay no se apaga con CAPA3_HABILITADA. Un pago que el banco ya aprobó
# se registra o se anula igual. Se importa al armar la app, nunca arriba, y se monta si su paquete existe: con la capa 3
# quitada de verdad (tests/capa3.py) no está y la API arranca igual. Como ("paquete:atributo", prefijo)
ROUTERS_PAGO_SIEMPRE: tuple[tuple[str, str], ...] = (
    ("app.modules.payments.api.router_retorno:router", "/v1"),
    ("app.modules.payments.api.router_retorno:router_formulario", ""),
)

# MATU-61 (C2, decisión 217): el efecto del retiro de despacho y del borrado sobre los pedidos, como
# "finalidad=paquete:clase". Se importa solo con CAPA3_HABILITADA, igual que ROUTERS_CAPA_3
EFECTOS_CAPA_3: tuple[tuple[str, str], ...] = (
    (FINALIDAD_DESPACHO, "app.modules.ordering.infrastructure.efecto_retiro:EfectoRetiroPedidos"),
)


@router_salud.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok"}


def incluir_capa_3(app: FastAPI) -> None:
    """Monta los routers de ROUTERS_CAPA_3 con el prefijo /v1 y registra los efectos de EFECTOS_CAPA_3. Solo se
    llama con CAPA3_HABILITADA."""
    for referencia in ROUTERS_CAPA_3:
        modulo, _, atributo = referencia.partition(":")
        app.include_router(getattr(importlib.import_module(modulo), atributo), prefix="/v1")
    for finalidad, referencia in EFECTOS_CAPA_3:
        modulo, _, atributo = referencia.partition(":")
        registrar_efecto(finalidad, getattr(importlib.import_module(modulo), atributo))


def incluir_vuelta_del_pago(app: FastAPI) -> None:
    """Monta ROUTERS_PAGO_SIEMPRE con la capa 3 encendida o apagada. Si un paquete de la app no está (la capa 3
    quitada), no la monta y lo deja en el log; cualquier otro error de importación sube."""
    for referencia, prefijo in ROUTERS_PAGO_SIEMPRE:
        modulo, _, atributo = referencia.partition(":")
        try:
            importado = importlib.import_module(modulo)
        except ModuleNotFoundError as error:
            if error.name and error.name.startswith("app.modules."):
                log.warning("la vuelta del pago no se monta: falta su paquete")
                return
            raise
        app.include_router(getattr(importado, atributo), prefix=prefijo)


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
    # MATU-42 (decisión 305): sacar, salir y dejar de compartir cortan los enlaces de relevo de esa persona. care_circle
    # no importa care_plan: se arma aquí. Sin él, esas rutas fallan cerradas
    registrar_enlaces(EnlacesOtorgados)

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
    # MATU-42 (C23): las rutas de la persona invitada, como las del relevo: no-store, no-referrer y noindex
    app.add_middleware(MiddlewareCabecerasPrefijo, prefijo="/v1/invitaciones/", cabeceras=CABECERAS_RELEVO)
    # MATU-38: no-store en toda respuesta de sesión y dispositivos, también en los 401, 422 y 429
    # MATU-36: también bajo /v1/personas-cuidadas/ (autorización, consumo y ficha), en los 403 y 404
    # MATU-57: también la recuperación del acceso y la cuenta. MATU-41: la preferencia de avisos (/v1/yo/)
    # MATU-61 (C17): el pedido, también sus errores. La dirección ya va bajo /v1/personas-cuidadas/
    for prefijo in (
        "/v1/sesiones", "/v1/dispositivos", "/v1/personas-cuidadas/", "/v1/recuperacion", "/v1/cuenta", "/v1/yo/",
        "/v1/pedidos", "/v1/pagos",
        # MATU-42 (decisión 315): el grupo, sus miembros y sus invitaciones, también los errores
        "/v1/grupos",
    ):
        app.add_middleware(MiddlewareCabecerasPrefijo, prefijo=prefijo, cabeceras={"Cache-Control": "no-store"})
    app.add_middleware(MiddlewareRequestId)

    # Routers por historia (una línea cada uno)
    app.include_router(router_salud, prefix="/v1")
    app.include_router(router_iam, prefix="/v1")
    # MATU-75: la política de privacidad vigente, pública y sin sesión
    app.include_router(router_politica, prefix="/v1")
    app.include_router(router_sesiones, prefix="/v1")
    app.include_router(router_recuperacion, prefix="/v1")
    app.include_router(router_grupos, prefix="/v1")
    app.include_router(router_personas, prefix="/v1")
    app.include_router(router_ficha, prefix="/v1")
    app.include_router(router_secciones, prefix="/v1")
    app.include_router(router_relevo, prefix="/v1")
    app.include_router(router_relevo_publico, prefix="/v1")
    app.include_router(router_autorizaciones, prefix="/v1")
    app.include_router(router_borrado, prefix="/v1")
    # MATU-61: la dirección de la persona es de care_circle y existe también sin la capa 3 (C8)
    app.include_router(router_direccion, prefix="/v1")
    # MATU-42: invitar, la persona invitada y quiénes forman el grupo
    app.include_router(router_invitaciones, prefix="/v1")
    app.include_router(router_invitacion_publica, prefix="/v1")
    app.include_router(router_miembros, prefix="/v1")
    # Antes que router_consumo: por-acabarse, alertas y lista (MATU-60) son rutas fijas que {perfil_id} capturaría
    app.include_router(router_alertas, prefix="/v1")
    app.include_router(router_lista, prefix="/v1")
    app.include_router(router_consumo, prefix="/v1")
    app.include_router(router_reposicion, prefix="/v1")
    app.include_router(router_avisos, prefix="/v1")
    # MATU-55: «Dónde entraste», los últimos ingresos de la propia cuenta
    app.include_router(router_ingresos, prefix="/v1")

    # MATU-40 (ADR-002): la capa 3 se monta aparte y solo si está habilitada. Las capas 1 y 2, arriba,
    # nunca dependen de ella
    if config.capa3_habilitada:
        incluir_capa_3(app)
    # MATU-62 (D-62-17): la vuelta de Webpay, también con la capa 3 apagada
    incluir_vuelta_del_pago(app)

    # MATU-23: la página /r y sus /assets, después de las rutas de la API para no taparlas
    montar_pagina_relevo(app, config.web_dist)
    # MATU-58: la app de familia en toda ruta GET o HEAD que no sea de la API, /r, /assets ni la
    # documentación. Es el destino por omisión del enrutador: no tapa ninguna ruta, ni las de después
    montar_app_familia(app, config.web_dist)

    return app


app = crear_app()

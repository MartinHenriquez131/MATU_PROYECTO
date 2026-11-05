"""La aplicación web servida por la API, en el mismo origen y sin CORS (MATU-23, MATU-58, ADR-026).

Página del relevo (MATU-23). GET /r responde el index.html del build de web/ (el fragmento #token nunca
llega al servidor) con Cache-Control: no-store, Referrer-Policy: no-referrer y X-Robots-Tag: noindex
(decisión D6). El HTML trae su propia Content-Security-Policy en una etiqueta meta, que se entrega intacta.

App de familia (MATU-58, decisión 115). La app enruta en el navegador con la History API
(web/src/familia/ruteo.ts), así que el servidor entrega el mismo index.html en cualquier ruta suya:
todo GET o HEAD que no sea de la API ni de las demás piezas servidas aquí (ver es_ruta_de_la_app). No se
copia la lista de rutas de ruteo.ts, que crece con cada pantalla. Si la ruta es un archivo que existe en
la carpeta del build (favicon, manifest, service worker), se entrega ese archivo, sin salir nunca de ella.
Las respuestas llevan las cabeceras de la página del relevo, con Cache-Control: no-cache en vez de
no-store, y Content-Security-Policy: frame-ancestors 'none', que en una etiqueta meta no tiene efecto.

El respaldo no es una ruta: es el destino por omisión del enrutador (Router.default de Starlette), al que
llega una petición solo cuando ninguna ruta coincide, ni siquiera en parte. Así no tapa ninguna ruta, se
registre antes o después; un método no permitido en /v1 sigue en 405 y la redirección de la barra final
no cambia. Para lo que no es de la app (una ruta /v1 inexistente, /docs fuera de local y pruebas, un POST),
el respaldo llama al 404 original del enrutador: 404 /errores/no-encontrado en RFC 7807.

Los archivos de /assets se sirven con StaticFiles y su caché normal (ETag y Last-Modified): sus
nombres llevan el hash del contenido.

Si la carpeta del build no existe, por ejemplo en el CI, que no hace build, la API arranca igual: /r y
las rutas de la app responden 404 RFC 7807 con sus cabeceras, y /assets no se monta.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.types import Receive, Scope, Send

from app.core.cabeceras import CABECERAS_APP, CABECERAS_RELEVO
from app.core.errores import respuesta_problema

RUTA_PAGINA_RELEVO = "/r"

# Lo que nunca es de la app de familia (decisión 115). Un prefijo cubre la ruta exacta y lo que cuelga de
# ella como segmento: /v1 y /v1/…, pero no /v1x. /r y /openapi.json se excluyen como rutas exactas, con o
# sin barra final: /r/algo o /registro, por ejemplo, serían de la app
PREFIJOS_FUERA_DE_LA_APP: tuple[str, ...] = ("/v1", "/assets", "/docs")
RUTAS_FUERA_DE_LA_APP: frozenset[str] = frozenset({RUTA_PAGINA_RELEVO, "/openapi.json"})


def es_ruta_de_la_app(ruta: str) -> bool:
    """True si el servidor debe responder la ruta con la app de familia.

    La barra final no cambia la respuesta: /openapi.json/ tampoco es de la app, e /insumos/ sí.
    """
    if (ruta.rstrip("/") or "/") in RUTAS_FUERA_DE_LA_APP:
        return False
    return not any(ruta == prefijo or ruta.startswith(prefijo + "/") for prefijo in PREFIJOS_FUERA_DE_LA_APP)


def archivo_del_build(web_dist: Path, ruta: str) -> Path | None:
    """El archivo de la carpeta del build que corresponde a la ruta, o None.

    Nunca sale de la carpeta: la ruta resuelta (con .. y enlaces simbólicos ya aplicados) tiene que
    quedar dentro de ella. Una ruta con barra invertida o un byte nulo no se resuelve.
    """
    if not ruta or "\\" in ruta or "\x00" in ruta:
        return None
    try:
        base = web_dist.resolve()
        candidato = (base / ruta.lstrip("/")).resolve()
    except (OSError, ValueError):
        return None
    if not candidato.is_relative_to(base) or not candidato.is_file():
        return None
    return candidato


def montar_pagina_relevo(app: FastAPI, web_dist: Path) -> None:
    indice = web_dist / "index.html"
    assets = web_dist / "assets"

    @app.get(RUTA_PAGINA_RELEVO, include_in_schema=False)
    def pagina_relevo(request: Request) -> Response:
        # Se revisa en cada petición: un build hecho con la API arriba queda disponible sin reiniciar
        if not indice.is_file():
            return respuesta_problema(
                request,
                404,
                detalle="La página del relevo no está disponible en este servidor",
                headers=CABECERAS_RELEVO,
            )
        return FileResponse(indice, media_type="text/html; charset=utf-8", headers=CABECERAS_RELEVO)

    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")


def _ruta(scope: Scope) -> str:
    # La ruta sin el root_path, como la compara el enrutador
    ruta = str(scope["path"])
    raiz = str(scope.get("root_path", ""))
    if raiz and ruta.startswith(raiz):
        return ruta[len(raiz) :] or "/"
    return ruta


def montar_app_familia(app: FastAPI, web_dist: Path) -> None:
    indice = web_dist / "index.html"
    no_encontrado = app.router.default

    def pagina_app(request: Request, ruta: str) -> Response:
        # Como /r, se revisa en cada petición
        if not indice.is_file():
            return respuesta_problema(
                request, 404, detalle="La aplicación no está disponible en este servidor", headers=CABECERAS_APP
            )
        archivo = archivo_del_build(web_dist, ruta)
        if archivo is not None and archivo != indice.resolve():
            return FileResponse(archivo, headers=CABECERAS_APP)
        return FileResponse(indice, media_type="text/html; charset=utf-8", headers=CABECERAS_APP)

    async def respaldo(scope: Scope, receive: Receive, send: Send) -> None:
        ruta = _ruta(scope) if scope["type"] == "http" else ""
        if scope["type"] != "http" or scope["method"] not in ("GET", "HEAD") or not es_ruta_de_la_app(ruta):
            await no_encontrado(scope, receive, send)
            return
        # Las revisiones de la carpeta tocan el disco: fuera del bucle de eventos, como una ruta síncrona
        respuesta = await run_in_threadpool(pagina_app, Request(scope, receive), ruta)
        await respuesta(scope, receive, send)

    app.router.default = respaldo

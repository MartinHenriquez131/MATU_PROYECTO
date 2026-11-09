"""La aplicación web servida por la API, en el mismo origen y sin CORS (MATU-23, MATU-58, ADR-026).

Página del relevo (MATU-23). GET /r responde el index.html del build de web/ (el fragmento #token nunca
llega al servidor) con Cache-Control: no-store, Referrer-Policy: no-referrer y X-Robots-Tag: noindex
(decisión D6), y desde MATU-58 con Content-Security-Policy: frame-ancestors 'none' (decisión 115). El HTML
trae su propia Content-Security-Policy en una etiqueta meta, que se entrega intacta.

App de familia (MATU-58, decisión 115). La app enruta en el navegador con la History API
(web/src/familia/ruteo.ts), así que el servidor entrega el mismo index.html en cualquier ruta suya:
todo GET o HEAD que no sea de la API ni de las demás piezas servidas aquí (ver es_ruta_de_la_app). No se
copia la lista de rutas de ruteo.ts, que crece con cada pantalla. Si la ruta es un archivo que existe en
la carpeta del build (favicon, manifest, service worker), se entrega ese archivo, sin salir nunca de ella.
Las respuestas llevan las cabeceras de la página del relevo, con Cache-Control: no-cache en vez de
no-store, y las dos llevan Content-Security-Policy: frame-ancestors 'none', que en una etiqueta meta no
tiene efecto.

El respaldo no es una ruta: es el destino por omisión del enrutador (Router.default de Starlette), al que
llega una petición solo cuando ninguna ruta coincide, ni siquiera en parte. Así no tapa ninguna ruta, se
registre antes o después; un método no permitido en /v1 sigue en 405 y la redirección de la barra final
no cambia. Para lo que no es de la app (una ruta /v1 inexistente, /docs fuera de local y pruebas, un POST),
el respaldo llama al 404 original del enrutador: 404 /errores/no-encontrado en RFC 7807.

El version.json del build (MATU-67, decisión 172). La app lo pide para saber si hay una versión nueva, así
que se entrega con Cache-Control: no-store (CABECERAS_VERSION) en vez de no-cache, y nunca con el index.html
de respaldo: si el archivo no está en el build (desarrollo sin build, o el CI), responde 404 RFC 7807 con
esas cabeceras, aunque el index.html exista. No lleva datos de nadie, no pide sesión y no se audita.

Lo que no es una pantalla responde 404 RFC 7807, no el index.html: una ruta con un segmento oculto
(que empieza con punto, como .vite/manifest.json, también bajo /assets) y una ruta cuyo último segmento
tiene extensión (/favicon.ico) sin archivo en el build.

Los archivos de /assets se sirven con StaticFiles y su caché normal (ETag y Last-Modified): sus
nombres llevan el hash del contenido. El Content-Type de .js, .mjs, .css, .svg, .json y .webmanifest se
fija aquí (TIPOS_DEL_BUILD): en Windows mimetypes lo toma del registro, que puede decir text/plain para
.js, y el navegador rechaza un módulo con ese tipo y deja la página en blanco.

Si la carpeta del build no existe, por ejemplo en el CI, que no hace build, la API arranca igual: /r y
las rutas de la app responden 404 RFC 7807 con sus cabeceras, y /assets no se monta.
"""

import mimetypes
from pathlib import Path, PurePosixPath

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.types import Receive, Scope, Send

from app.core.cabeceras import CABECERAS_APP, CABECERAS_PAGINA_RELEVO, CABECERAS_VERSION
from app.core.errores import respuesta_problema

RUTA_PAGINA_RELEVO = "/r"
# El identificador del build, en la raíz de la carpeta del build (MATU-67, decisión 172)
RUTA_VERSION = "/version.json"

# Los tipos de los archivos del build, sin depender del sistema operativo (en Windows, del registro)
TIPOS_DEL_BUILD: dict[str, str] = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
}

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


def registrar_tipos_del_build() -> None:
    for extension, tipo in TIPOS_DEL_BUILD.items():
        mimetypes.add_type(tipo, extension)


def _segmentos(ruta: str) -> list[str]:
    return [segmento for segmento in ruta.split("/") if segmento]


def es_ruta_oculta(ruta: str) -> bool:
    """True si algún segmento empieza con punto: .vite/, .env, .git/ o .. nunca se sirven."""
    return any(segmento.startswith(".") for segmento in _segmentos(ruta))


def parece_archivo(ruta: str) -> bool:
    """True si el último segmento tiene extensión (favicon.ico). Las pantallas de la app no la tienen."""
    segmentos = _segmentos(ruta)
    return bool(segmentos) and PurePosixPath(segmentos[-1]).suffix != ""


def archivo_del_build(web_dist: Path, ruta: str) -> Path | None:
    """El archivo de la carpeta del build que corresponde a la ruta, o None.

    Nunca sale de la carpeta: la ruta resuelta (con .. y enlaces simbólicos ya aplicados) tiene que
    quedar dentro de ella. Una ruta con barra invertida, un byte nulo o un segmento oculto no se resuelve.
    """
    if not ruta or "\\" in ruta or "\x00" in ruta or es_ruta_oculta(ruta):
        return None
    try:
        base = web_dist.resolve()
        candidato = (base / ruta.lstrip("/")).resolve()
    except (OSError, ValueError):
        return None
    if not candidato.is_relative_to(base) or not candidato.is_file():
        return None
    return candidato


class ArchivosDelBuild(StaticFiles):
    """StaticFiles sin archivos ocultos: /assets/.algo responde 404 como un archivo que no existe."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        if es_ruta_oculta(path.replace("\\", "/")):
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)


def montar_pagina_relevo(app: FastAPI, web_dist: Path) -> None:
    indice = web_dist / "index.html"
    assets = web_dist / "assets"
    registrar_tipos_del_build()

    @app.get(RUTA_PAGINA_RELEVO, include_in_schema=False)
    def pagina_relevo(request: Request) -> Response:
        # Se revisa en cada petición: un build hecho con la API arriba queda disponible sin reiniciar
        if not indice.is_file():
            return respuesta_problema(
                request,
                404,
                detalle="La página del relevo no está disponible en este servidor",
                headers=CABECERAS_PAGINA_RELEVO,
            )
        return FileResponse(indice, media_type="text/html; charset=utf-8", headers=CABECERAS_PAGINA_RELEVO)

    if assets.is_dir():
        app.mount("/assets", ArchivosDelBuild(directory=assets), name="assets")


def _ruta(scope: Scope) -> str:
    # La ruta sin el root_path, como la compara el enrutador
    ruta = str(scope["path"])
    raiz = str(scope.get("root_path", ""))
    if raiz and ruta.startswith(raiz):
        return ruta[len(raiz) :] or "/"
    return ruta


def montar_app_familia(app: FastAPI, web_dist: Path) -> None:
    indice = web_dist / "index.html"
    registrar_tipos_del_build()
    no_encontrado = app.router.default

    def version(request: Request) -> Response:
        # Sin el index.html de respaldo: un 200 con HTML haría creer a la app que hay una versión nueva
        archivo = archivo_del_build(web_dist, RUTA_VERSION)
        if archivo is None:
            return respuesta_problema(request, 404, headers=CABECERAS_VERSION)
        return FileResponse(archivo, media_type="application/json", headers=CABECERAS_VERSION)

    def pagina_app(request: Request, ruta: str) -> Response:
        # Como /r, se revisa en cada petición
        if (ruta.rstrip("/") or "/") == RUTA_VERSION:
            return version(request)
        if not indice.is_file():
            return respuesta_problema(
                request, 404, detalle="La aplicación no está disponible en este servidor", headers=CABECERAS_APP
            )
        if es_ruta_oculta(ruta):
            return respuesta_problema(request, 404, headers=CABECERAS_APP)
        archivo = archivo_del_build(web_dist, ruta)
        if archivo is not None and archivo != indice.resolve():
            return FileResponse(archivo, headers=CABECERAS_APP)
        # Un archivo que no está en el build no es una pantalla: 404, no el index.html
        if archivo is None and parece_archivo(ruta):
            return respuesta_problema(request, 404, headers=CABECERAS_APP)
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

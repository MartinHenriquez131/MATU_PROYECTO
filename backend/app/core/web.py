"""La página del relevo servida por la API, en el mismo origen y sin CORS (MATU-23, ADR-026).

GET /r responde el index.html del build de web/ (el fragmento #token nunca llega al servidor) con
Cache-Control: no-store, Referrer-Policy: no-referrer y X-Robots-Tag: noindex (decisión D6). El HTML
trae su propia Content-Security-Policy en una etiqueta meta, que se entrega intacta.

Los archivos de /assets se sirven con StaticFiles y su caché normal (ETag y Last-Modified): sus
nombres llevan el hash del contenido.

Si la carpeta del build no existe, por ejemplo en el CI, que no hace build, la API arranca igual:
/r responde 404 RFC 7807 con las mismas cabeceras y /assets no se monta.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.core.cabeceras import CABECERAS_RELEVO
from app.core.errores import respuesta_problema

RUTA_PAGINA_RELEVO = "/r"


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

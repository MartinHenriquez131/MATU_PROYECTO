"""Cabeceras fijas para todas las respuestas bajo un prefijo, también las de error (MATU-19, C11).

Las rutas públicas del relevo (/v1/relevo/) responden siempre con Cache-Control: no-store,
Referrer-Policy: no-referrer y X-Robots-Tag: noindex. Un middleware las pone incluso en un 422 de
validación, un 500 o un 404 de ruta inexistente, que no pasan por el código de la ruta.

Aquí viven también las cabeceras de las páginas que sirve app/core/web.py (MATU-23 y MATU-58).
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PREFIJO_RELEVO = "/v1/relevo/"

# Las de toda página servida por la API: sin Referer hacia otros sitios y fuera de los buscadores
CABECERAS_PAGINA = {
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex",
}

CABECERAS_RELEVO = {
    "Cache-Control": "no-store",
    **CABECERAS_PAGINA,
}

# Ninguna página de la API se puede incrustar en otro sitio (MATU-58, decisión 115). frame-ancestors solo
# vale como cabecera: en la etiqueta meta del build se ignora. Se suma a la CSP de la etiqueta meta sin
# aflojarla, porque el navegador aplica las dos
SIN_INCRUSTAR = {"Content-Security-Policy": "frame-ancestors 'none'"}

# La página del relevo, /r: las del relevo y sin incrustar, para que la página del PIN no quede dentro de
# otro sitio. Las respuestas de /v1/relevo/ siguen con CABECERAS_RELEVO, sin la CSP
CABECERAS_PAGINA_RELEVO = {
    **CABECERAS_RELEVO,
    **SIN_INCRUSTAR,
}

# La app de familia (MATU-58, decisión 115): las de la página del relevo, con no-cache en vez de
# no-store (el index.html no trae datos y se revalida en cada visita, para no quedar con un build viejo)
CABECERAS_APP = {
    **CABECERAS_PAGINA,
    "Cache-Control": "no-cache",
    **SIN_INCRUSTAR,
}

# El version.json del build (MATU-67, decisión 172): las de la app con no-store en vez de no-cache. La app lo
# pide cada cierto tiempo para saber si hay una versión nueva, y ni el navegador ni un proxy deben guardarlo
CABECERAS_VERSION = {
    **CABECERAS_APP,
    "Cache-Control": "no-store",
}


class MiddlewareCabecerasPrefijo:
    def __init__(self, app: ASGIApp, prefijo: str, cabeceras: dict[str, str]) -> None:
        self.app = app
        self.prefijo = prefijo
        self.cabeceras = cabeceras

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not str(scope.get("path", "")).startswith(self.prefijo):
            await self.app(scope, receive, send)
            return

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                destino = MutableHeaders(scope=mensaje)
                for clave, valor in self.cabeceras.items():
                    destino[clave] = valor
            await send(mensaje)

        await self.app(scope, receive, enviar)

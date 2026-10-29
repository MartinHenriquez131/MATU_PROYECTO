"""Cabeceras fijas para todas las respuestas bajo un prefijo, también las de error (MATU-19, C11).

Las rutas públicas del relevo (/v1/relevo/) responden siempre con Cache-Control: no-store,
Referrer-Policy: no-referrer y X-Robots-Tag: noindex. Un middleware las pone incluso en un 422 de
validación, un 500 o un 404 de ruta inexistente, que no pasan por el código de la ruta.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PREFIJO_RELEVO = "/v1/relevo/"

CABECERAS_RELEVO = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex",
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

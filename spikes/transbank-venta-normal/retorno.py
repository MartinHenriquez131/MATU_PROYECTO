"""Servidor mínimo en localhost:8000 que muestra el token del retorno de Webpay (spike MATU-62).

Uso: python retorno.py  (déjalo abierto en otra ventana de Git Bash; Ctrl+C para cerrarlo)
- token_ws: el pago volvió bien, sigue con «python vn.py confirmar TOKEN».
- TBK_TOKEN: el pago se anuló en Webpay; empieza el caso con una orden nueva.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


class Retorno(BaseHTTPRequestHandler):
    def _responder(self, params: dict[str, list[str]]) -> None:
        token = params.get("token_ws", [""])[0]
        anulado = params.get("TBK_TOKEN", [""])[0]
        if token:
            texto = f"Pago devuelto. Token: {token}"
        elif anulado:
            texto = f"Pago ANULADO en Webpay (TBK_TOKEN {anulado}). Empieza con una orden nueva."
        else:
            texto = "Retorno sin token."
        print(texto, flush=True)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write((texto + "\nVuelve a la consola.\n").encode())

    def do_GET(self) -> None:
        self._responder(parse_qs(urlparse(self.path).query))

    def do_POST(self) -> None:
        largo = int(self.headers.get("Content-Length", 0))
        self._responder(parse_qs(self.rfile.read(largo).decode()))

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    print(
        "Esperando el retorno de Webpay en http://localhost:8000/retorno ...",
        flush=True,
    )
    HTTPServer(("127.0.0.1", 8000), Retorno).serve_forever()

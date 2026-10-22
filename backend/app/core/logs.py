"""Logs estructurados en JSON, correlacionados por request_id.

Reglas (arquitectura, secciones 11.6 y 13; prompt de agentes, política 6):
- Cada línea es un objeto JSON con ts, nivel, logger, mensaje y request_id.
- Solo se registran los campos de CAMPOS_PERMITIDOS. Nunca el cuerpo de la petición, las
  cabeceras, el query string, tokens, PIN ni texto de la ficha.
- De una excepción se registra el tipo y la traza, no su mensaje: los errores de la base
  pueden traer valores de las filas.
- El log de acceso de uvicorn se apaga, porque incluye el query string. Lo reemplaza la
  línea "peticion" del middleware, que registra la plantilla de la ruta (/v1/grupos/{grupo_id}),
  nunca el path real, y el usuario y el grupo cuando la petición los fijó.
- Los clientes HTTP (httpx, urllib3) quedan en WARNING por la misma razón. Y si uno de ellos, o
  cualquier logger que no sea de MATU, registra una URL, se le quita el query string y el fragmento.
"""

import json
import logging
import re
import sys
import time
import traceback
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TextIO

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_actual: ContextVar[str | None] = ContextVar("request_id", default=None)

# Campos extra que un log puede llevar. Lo que no está aquí no se escribe.
# usuario_id y grupo_id los fijan las dependencias de iam y care_circle en request.state.
CAMPOS_PERMITIDOS = ("metodo", "ruta", "estado", "duracion_ms", "tipo_error", "usuario_id", "grupo_id")

# Lo que se registra en "ruta" cuando la petición no calzó con ninguna ruta (404 de ruta inexistente)
SIN_RUTA = "sin-ruta"

log = logging.getLogger("matu.api")

# Una URL absoluta o un path, seguidos de ?query o #fragmento. Se conserva solo la parte previa.
_URL_CON_QUERY = re.compile(r"(?P<base>(?:https?://|/)[^\s?#\"'<>]*)[?#][^\s\"'<>]*")


def _sin_query(mensaje: str) -> str:
    return _URL_CON_QUERY.sub(r"\g<base>", mensaje)


def _mensaje(record: logging.LogRecord) -> str:
    mensaje = record.getMessage()
    # Los logs de MATU ya cuidan lo que escriben. Los de terceros (urllib3, httpx) pueden traer
    # una URL con un token en el query string.
    if record.name.startswith("matu"):
        return mensaje
    return _sin_query(mensaje)


class FormateadorJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        datos: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": _mensaje(record),
            "request_id": request_id_actual.get(),
        }
        for campo in CAMPOS_PERMITIDOS:
            if hasattr(record, campo):
                datos[campo] = getattr(record, campo)
        if record.exc_info and record.exc_info[0] is not None:
            datos.setdefault("tipo_error", record.exc_info[0].__name__)
            # format_tb entrega solo los marcos, sin la línea final con el mensaje
            datos["traza"] = "".join(traceback.format_tb(record.exc_info[2]))
        return json.dumps(datos, ensure_ascii=False, default=str)


def configurar_logs(nivel: str = "INFO", stream: TextIO | None = None) -> None:
    manejador = logging.StreamHandler(stream or sys.stdout)
    manejador.setFormatter(FormateadorJSON())

    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(nivel)

    for nombre in ("uvicorn", "uvicorn.error"):
        uv = logging.getLogger(nombre)
        uv.handlers = []
        uv.propagate = True
    logging.getLogger("uvicorn.access").disabled = True

    # Los clientes HTTP registran la URL completa, con su query string, en INFO o DEBUG.
    # Se suben a WARNING para que una llamada saliente (Transbank, correo) no deje tokens en el log.
    for nombre in ("httpx", "httpx2", "httpcore", "urllib3", "requests"):
        logging.getLogger(nombre).setLevel(logging.WARNING)


def _request_id_entrante(scope: Scope) -> str | None:
    """Acepta un X-Request-ID entrante solo si es un UUID, para que nadie inyecte texto en los logs."""
    for clave, valor in scope.get("headers", []):
        if clave == b"x-request-id":
            try:
                return str(uuid.UUID(valor.decode("latin-1")))
            except ValueError:
                return None
    return None


def _plantilla_ruta(scope: Scope) -> str:
    """La plantilla de la ruta que atendió la petición (/v1/grupos/{grupo_id}), sin valores reales.

    Según la versión de FastAPI, scope["route"].path trae el prefijo del router (/v1) o no lo trae.
    Si no lo trae, el prefijo es la parte del path que queda antes de lo que calza la ruta. Los
    prefijos de MATU son fijos, así que esa parte nunca trae un valor de la petición.
    """
    ruta = scope.get("route")
    plantilla = getattr(ruta, "path", None)
    if not isinstance(plantilla, str):
        return SIN_RUTA
    patron = getattr(ruta, "path_regex", None)
    path = scope.get("path", "")
    if not isinstance(patron, re.Pattern) or patron.match(path):
        return plantilla
    for indice, caracter in enumerate(path):
        if caracter == "/" and indice > 0 and patron.match(path[indice:]):
            return path[:indice] + plantilla
    return plantilla


class MiddlewareRequestId:
    """Asigna un request_id a cada petición, lo devuelve en X-Request-ID y registra una línea
    por petición con método, plantilla de la ruta, estado, duración y, si la petición los fijó,
    usuario_id y grupo_id."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id_entrante(scope) or str(uuid.uuid4())
        estado_peticion = scope.setdefault("state", {})
        estado_peticion["request_id"] = request_id
        token = request_id_actual.set(request_id)
        estado = 500
        inicio = time.perf_counter()

        async def enviar(mensaje: Message) -> None:
            nonlocal estado
            if mensaje["type"] == "http.response.start":
                estado = mensaje["status"]
                MutableHeaders(scope=mensaje)["X-Request-ID"] = request_id
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        except Exception:
            log.exception("error no controlado")
            raise
        finally:
            extra = {
                "metodo": scope.get("method"),
                "ruta": _plantilla_ruta(scope),
                "estado": estado,
                "duracion_ms": round((time.perf_counter() - inicio) * 1000, 1),
            }
            for campo in ("usuario_id", "grupo_id"):
                if campo in estado_peticion:
                    extra[campo] = estado_peticion[campo]
            log.info("peticion", extra=extra)
            request_id_actual.reset(token)

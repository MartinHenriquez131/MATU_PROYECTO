"""Logs estructurados en JSON, correlacionados por request_id.

Reglas (arquitectura, secciones 11.6 y 13; prompt de agentes, política 6):
- Cada línea es un objeto JSON con ts, nivel, logger, mensaje y request_id.
- Solo se registran los campos de CAMPOS_PERMITIDOS. Nunca el cuerpo de la petición, las
  cabeceras, el query string, tokens, PIN ni texto de la ficha.
- De una excepción se registra el tipo y la traza, no su mensaje: los errores de la base
  pueden traer valores de las filas.
- El log de acceso de uvicorn se apaga, porque incluye el query string. Lo reemplaza la
  línea "peticion" del middleware, que registra solo la ruta.
"""

import json
import logging
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
# MATU-02 llenará usuario_id y grupo_id cuando fije el contexto de tenant.
CAMPOS_PERMITIDOS = ("metodo", "ruta", "estado", "duracion_ms", "tipo_error", "usuario_id", "grupo_id")

log = logging.getLogger("matu.api")


class FormateadorJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        datos: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
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


def _request_id_entrante(scope: Scope) -> str | None:
    """Acepta un X-Request-ID entrante solo si es un UUID, para que nadie inyecte texto en los logs."""
    for clave, valor in scope.get("headers", []):
        if clave == b"x-request-id":
            try:
                return str(uuid.UUID(valor.decode("latin-1")))
            except ValueError:
                return None
    return None


class MiddlewareRequestId:
    """Asigna un request_id a cada petición, lo devuelve en X-Request-ID y registra una línea
    por petición con método, ruta, estado y duración."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id_entrante(scope) or str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
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
            log.info(
                "peticion",
                extra={
                    "metodo": scope.get("method"),
                    "ruta": scope.get("path"),
                    "estado": estado,
                    "duracion_ms": round((time.perf_counter() - inicio) * 1000, 1),
                },
            )
            request_id_actual.reset(token)

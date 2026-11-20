"""Errores de la API en formato RFC 7807 (application/problem+json).

Cada respuesta de error lleva type, title, status, detail y errores[] (arquitectura,
sección 9.1), más request_id para que quien reporte un problema pueda citarlo.

Dos reglas de privacidad:
- Un 422 lista qué campo falló y por qué, pero nunca el valor recibido. El valor puede
  ser una contraseña o el texto de la ficha.
- Un 500 no expone el mensaje de la excepción. Los mensajes de la base pueden incluir
  valores de las filas, por ejemplo un email duplicado.

MATU-80 (K1 del TESTER del 20-11): si el pool de conexiones está lleno y una petición espera más de
DB_POOL_TIMEOUT, la API responde 503 /errores/servicio-no-disponible con Retry-After, en vez del 500
genérico. El tiempo se agota al pedir la conexión, antes de empezar la transacción que la necesitaba:
esa transacción no corrió ni hizo commit. Una petición puede abrir varias transacciones seguidas (por
ejemplo, la vuelta de Webpay busca la venta y después la cierra), y las que ya hicieron commit quedan
hechas. Por eso el 503 no promete que la petición no escribió nada: reintentarla sigue las mismas reglas
que repetir cualquier petición (Idempotency-Key, ETag o el token de la venta, en las rutas que los usan).

Los type son URI relativas bajo /errores/. El catálogo definitivo de type de la ficha y del
relevo lo fija el contrato de MATU-09.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import TimeoutError as PoolAgotado
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.cabeceras import CABECERAS_RELEVO, PREFIJO_RELEVO

TIPO_PROBLEMA = "application/problem+json"

log = logging.getLogger("matu.api")

# MATU-80 (K1): los segundos que pide esperar el 503 del pool lleno. Corto: el pool se libera en cuanto termina la
# petición que tiene la conexión
RETRY_AFTER_POOL_S = 5
DETALLE_POOL_AGOTADO = "MATU no está disponible en este momento. Vuelve a intentarlo en unos minutos."

TITULOS: dict[int, str] = {
    400: "Petición inválida",
    401: "No autenticado",
    403: "Sin permiso",
    404: "No encontrado",
    405: "Método no permitido",
    409: "Conflicto",
    410: "Ya no está disponible",
    412: "Otra persona cambió este contenido",
    415: "Formato no soportado",
    422: "Datos inválidos",
    423: "Bloqueado",
    428: "Falta la versión del contenido",
    429: "Demasiadas peticiones",
    500: "Error interno",
    503: "Servicio no disponible",
}

TIPOS: dict[int, str] = {
    400: "peticion-invalida",
    401: "no-autenticado",
    403: "sin-permiso",
    404: "no-encontrado",
    405: "metodo-no-permitido",
    409: "conflicto",
    410: "no-disponible",
    412: "version-desactualizada",
    415: "formato-no-soportado",
    422: "validacion",
    423: "bloqueado",
    428: "falta-version",
    429: "demasiadas-peticiones",
    500: "error-interno",
    503: "servicio-no-disponible",
}


def _titulo(status: int) -> str:
    if status in TITULOS:
        return TITULOS[status]
    try:
        return HTTPStatus(status).phrase
    except ValueError:
        return "Error"


def _tipo(status: int) -> str:
    return "/errores/" + TIPOS.get(status, "error")


class ErrorMATU(Exception):
    """Error de negocio que la API responde como problema RFC 7807.

    Ejemplo: ``raise ErrorMATU(409, tipo="email-registrado", detalle="Ese email ya tiene una cuenta")``
    """

    def __init__(
        self,
        status: int,
        *,
        tipo: str | None = None,
        titulo: str | None = None,
        detalle: str | None = None,
        errores: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
        extension: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(titulo or _titulo(status))
        self.status = status
        self.tipo = "/errores/" + tipo if tipo else _tipo(status)
        self.titulo = titulo or _titulo(status)
        self.detalle = detalle
        self.errores = errores or []
        self.headers = headers
        # Miembros de extensión del problema (RFC 7807, 3.2), por ejemplo intentos_restantes
        self.extension = extension or {}


def respuesta_problema(
    request: Request,
    status: int,
    *,
    tipo: str | None = None,
    titulo: str | None = None,
    detalle: str | None = None,
    errores: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
    extension: dict[str, Any] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    cuerpo: dict[str, Any] = {
        "type": tipo or _tipo(status),
        "title": titulo or _titulo(status),
        "status": status,
        "detail": detalle,
        "errores": errores or [],
        "request_id": request_id,
    }
    for clave, valor in (extension or {}).items():
        cuerpo.setdefault(clave, valor)
    cabeceras = dict(headers or {})
    if request_id:
        cabeceras["X-Request-ID"] = request_id
    return JSONResponse(cuerpo, status_code=status, media_type=TIPO_PROBLEMA, headers=cabeceras)


def _campo(loc: tuple[Any, ...] | list[Any]) -> str:
    # ("body", "direccion", "comuna") → "direccion.comuna"
    partes = [str(p) for p in loc]
    if partes and partes[0] in {"body", "query", "path", "header", "cookie"}:
        partes = partes[1:]
    return ".".join(partes) or "cuerpo"


async def _manejar_error_matu(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErrorMATU)
    return respuesta_problema(
        request,
        exc.status,
        tipo=exc.tipo,
        titulo=exc.titulo,
        detalle=exc.detalle,
        errores=exc.errores,
        headers=exc.headers,
        extension=exc.extension,
    )


async def _manejar_http(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    # El detail de Starlette es la frase en inglés ("Not Found"). No aporta y se omite.
    return respuesta_problema(request, exc.status_code, headers=dict(exc.headers or {}))


async def _manejar_validacion(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Se copian solo el campo, el mensaje y el tipo. Nunca "input" ni "ctx", que traen el valor.
    errores = [
        {"campo": _campo(e.get("loc", ())), "mensaje": str(e.get("msg", "")), "tipo": str(e.get("type", ""))}
        for e in exc.errors()
    ]
    return respuesta_problema(request, 422, detalle="Revisa los campos indicados", errores=errores)


async def _manejar_pool_agotado(request: Request, exc: Exception) -> JSONResponse:
    # MATU-80 (K1): sin el mensaje de SQLAlchemy (nombra el tamaño del pool, nunca datos, pero no aporta), solo el
    # evento. La línea de la petición del MiddlewareRequestId lleva el request_id y el estado 503
    assert isinstance(exc, PoolAgotado)
    log.warning("pool de conexiones agotado", extra={"evento": "pool_agotado"})
    return respuesta_problema(
        request,
        503,
        detalle=DETALLE_POOL_AGOTADO,
        headers={"Retry-After": str(RETRY_AFTER_POOL_S), "Cache-Control": "no-store"},
    )


async def _manejar_inesperado(request: Request, exc: Exception) -> JSONResponse:
    # El MiddlewareRequestId ya registró la traza, con su request_id y sin el mensaje.
    # Este manejador corre en ServerErrorMiddleware, por fuera de los demás middlewares: las cabeceras del
    # relevo (MATU-19, C11) se ponen aquí. Un 500 nunca se guarda en caché.
    cabeceras = {"Cache-Control": "no-store"}
    if request.url.path.startswith(PREFIJO_RELEVO):
        cabeceras.update(CABECERAS_RELEVO)
    return respuesta_problema(
        request, 500, detalle="Ocurrió un error inesperado. Cita el request_id si lo reportas", headers=cabeceras
    )


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(ErrorMATU, _manejar_error_matu)
    app.add_exception_handler(StarletteHTTPException, _manejar_http)
    app.add_exception_handler(RequestValidationError, _manejar_validacion)
    app.add_exception_handler(PoolAgotado, _manejar_pool_agotado)
    app.add_exception_handler(Exception, _manejar_inesperado)

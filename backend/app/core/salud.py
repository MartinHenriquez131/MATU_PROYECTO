"""GET /v1/salud: la API responde y alcanza la base y Redis (MATU-79).

- La base: ``SELECT 1`` como matu_app, con la misma DATABASE_URL de la app, en una conexión aparte y sin pool
  (``NullPool``), con ``connect_timeout`` y ``statement_timeout`` de TIEMPO_LIMITE_S. El pool de la app no tiene
  tiempo límite de conexión: una base caída dejaría la comprobación colgada. ``SELECT 1`` no lee ninguna tabla, así
  que no necesita contexto de tenant (sesion_tenant) y no ve datos de nadie.
- Redis: ``PING`` con la REDIS_URL de la app, con el mismo tiempo límite para conectar y para responder.
- 200 ``{"estado": "ok"}`` si las dos responden. 503 RFC 7807 si alguna falla, con un ``detail`` fijo: nunca la
  cadena de conexión, el nombre del host ni el mensaje del driver, y nunca qué componente falló.
- El log de una falla dice qué componente y el tipo de la excepción, nunca su mensaje: el de psycopg o redis puede
  traer el host, el usuario o la cadena de conexión.
- Las comprobaciones son una dependencia (``obtener_comprobaciones``): las pruebas la reemplazan por dobles para
  simular una caída.
"""

import logging
from collections.abc import Callable, Sequence
from functools import lru_cache
from typing import Annotated

import redis
from fastapi import APIRouter, Depends
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import obtener_configuracion
from app.core.errores import ErrorMATU

log = logging.getLogger("matu.salud")

# Segundos que espera cada comprobación, para conectar y para responder
TIEMPO_LIMITE_S = 2

DETALLE_503 = "MATU no está disponible en este momento. Cita el request_id si lo reportas"

# (nombre del componente para el log, comprobación que lanza una excepción si el componente no responde)
Comprobacion = tuple[str, Callable[[], None]]


@lru_cache
def _engine_salud() -> Engine:
    url = obtener_configuracion().database_url
    if not url:
        raise RuntimeError("Falta DATABASE_URL")
    return create_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "connect_timeout": TIEMPO_LIMITE_S,
            "options": f"-c statement_timeout={TIEMPO_LIMITE_S * 1000}",
        },
    )


def comprobar_base() -> None:
    with _engine_salud().connect() as conexion:
        conexion.execute(text("SELECT 1")).scalar_one()


def comprobar_redis() -> None:
    cliente = redis.Redis.from_url(
        obtener_configuracion().redis_url, socket_timeout=TIEMPO_LIMITE_S, socket_connect_timeout=TIEMPO_LIMITE_S
    )
    try:
        if not cliente.ping():
            raise RuntimeError("PING sin respuesta")
    finally:
        cliente.close()


def obtener_comprobaciones() -> Sequence[Comprobacion]:
    """Dependencia de FastAPI con las comprobaciones de /v1/salud. Las pruebas la sobreescriben."""
    return (("base", comprobar_base), ("redis", comprobar_redis))


RESPUESTAS_SALUD: dict[int | str, dict[str, object]] = {
    200: {"description": "La API responde y alcanza la base y Redis"},
    503: {
        "description": (
            "servicio-no-disponible: la base o Redis no responden dentro del tiempo límite. El problema no dice cuál"
            " ni trae detalle interno"
        ),
        "content": {"application/problem+json": {}},
    },
}

router = APIRouter(tags=["salud"])


@router.get("/salud", responses=RESPUESTAS_SALUD)
def salud(comprobaciones: Annotated[Sequence[Comprobacion], Depends(obtener_comprobaciones)]) -> dict[str, str]:
    """Comprueba la base (`SELECT 1`) y Redis (`PING`), cada una con un tiempo límite de 2 segundos. Responde sin
    datos: 200 si las dos responden y 503 si alguna falla."""
    fallo = False
    for componente, comprobar in comprobaciones:
        try:
            comprobar()
        except Exception as error:  # noqa: BLE001 - cualquier falla es "no disponible"; el mensaje no se registra
            log.warning("salud: %s no responde (%s)", componente, type(error).__name__)
            fallo = True
    if fallo:
        raise ErrorMATU(503, detalle=DETALLE_503, headers={"Cache-Control": "no-store"})
    return {"estado": "ok"}

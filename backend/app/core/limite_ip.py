"""Límite por IP en la API, con Redis (MATU-25, decisiones 27, 29 y 114).

    POST /v1/usuarios            5 por hora   prefijo usuarios-ip
    POST /v1/relevo/canje        10 por hora  prefijo canje-ip
    POST /v1/relevo/presentacion 30 por hora  prefijo presentacion-ip

Cada ruta declara ``dependencies=[Depends(limite_por_ip(LIMITE_…))]``. La dependencia corre antes de
validar los campos del cuerpo, así el 429 va antes del 422 de validación (orden de evaluación del
contrato). Un cuerpo que no es JSON válido responde 422 antes, sin contar: FastAPI lo parsea antes de
resolver las dependencias (decisión 114).

- La IP es ``request.client.host``. Detrás del proxy de Railway la fija MiddlewareProxy
  (app/core/proxy.py, armado en app/servidor.py) desde X-Forwarded-For, solo si la conexión viene de
  FORWARDED_ALLOW_IPS, y con PROXY_SALTOS=N toma ``xff[-(N+1)]``: la que queda justo a la izquierda de
  los N servidores de borde, nunca la primera de la lista. Con una lista corta o mal formada cuenta la
  IP del socket. Un X-Forwarded-For de cualquier otro origen se ignora. Esta dependencia no lee cabeceras.
- La clave es ``matu:limite:<prefijo>:<huella>``: la huella HMAC de la IP con PEPPER_LIMITES y el
  prefijo del contador. La IP nunca llega a Redis, a un log, a la auditoría ni al 429.
- Ventana fija: un script Lua, atómico, hace INCR y fija el vencimiento solo en el primer incremento.
  Los siguientes no lo renuevan. Si la clave quedara sin vencimiento, el mismo script se lo pone:
  ninguna clave vive para siempre.
- Falla cerrada: sin PEPPER_LIMITES o sin Redis, 503, igual que la entrada de MATU-38.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Protocol

import redis
from fastapi import Depends, Request

from app.core.config import obtener_configuracion
from app.core.errores import ErrorMATU
from app.shared.limite_ip import LimitePorIp, excedido, huella, retry_after

log = logging.getLogger("matu.limite_ip")

PREFIJO_CLAVE = "matu:limite:"

DETALLE_429 = "Espera un rato antes de volver a intentarlo"
DETALLE_503 = "No se puede atender esta petición en este momento. Cita el request_id si lo reportas"

# Respuestas que agrega cada ruta limitada a su OpenAPI
RESPUESTAS_LIMITE: dict[int | str, dict[str, object]] = {
    429: {
        "description": "demasiadas-peticiones: se superó el límite por IP de la ruta, en una ventana fija de 1 hora",
        "headers": {
            "Retry-After": {
                "description": "Segundos que faltan para que se abra la ventana, de 1 a 3600",
                "schema": {"type": "integer"},
            }
        },
        "content": {"application/problem+json": {}},
    },
    503: {
        "description": "Redis no responde o falta PEPPER_LIMITES: el límite por IP falla cerrado",
        "content": {"application/problem+json": {}},
    },
}

# INCR; si es el primero (o la clave no tiene vencimiento), EXPIRE. Devuelve {conteo, ttl}.
# Un incremento posterior no toca el TTL: la ventana es fija.
_SCRIPT_VENTANA_FIJA = """
local conteo = redis.call('INCR', KEYS[1])
local ttl = redis.call('TTL', KEYS[1])
if conteo == 1 or ttl < 0 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
  ttl = tonumber(ARGV[1])
end
return {conteo, ttl}
"""


class ContadorNoDisponible(Exception):
    """Redis no responde. La ruta responde 503 y falla cerrada. Nunca lleva la clave."""


@dataclass(frozen=True)
class Conteo:
    """Cuántas peticiones van en la ventana, contando esta, y cuántos segundos le quedan."""

    conteo: int
    ttl_segundos: int


class ContadorVentana(Protocol):
    """Suma una petición a la clave, en una ventana fija que empieza con la primera.

    Implementaciones: ContadorVentanaRedis (aquí) y ContadorVentanaEnMemoria (tests/dobles).
    """

    def sumar(self, clave: str, ventana_segundos: int) -> Conteo: ...


class ContadorVentanaRedis:
    def __init__(self, cliente: "redis.Redis") -> None:
        self._redis = cliente
        self._script = cliente.register_script(_SCRIPT_VENTANA_FIJA)

    def __repr__(self) -> str:
        return "ContadorVentanaRedis()"

    def sumar(self, clave: str, ventana_segundos: int) -> Conteo:
        try:
            conteo, ttl = self._script(keys=[clave], args=[ventana_segundos])
        except redis.RedisError:
            raise ContadorNoDisponible from None
        return Conteo(int(conteo), int(ttl))


def clave_de(limite: LimitePorIp, huella_ip: str) -> str:
    return f"{PREFIJO_CLAVE}{limite.prefijo}:{huella_ip}"


# --- Dependencias --------------------------------------------------------------------------------------


def obtener_pepper_limites() -> bytes | None:
    """La llave de las huellas del límite por IP y de la demora de la entrada (MATU-38). None si falta:
    la ruta responde 503. Las pruebas la sobreescriben."""
    pepper = obtener_configuracion().pepper_limites
    return None if pepper is None else pepper.get_secret_value().encode("utf-8")


@lru_cache
def _contador_redis() -> ContadorVentana:
    return ContadorVentanaRedis(redis.Redis.from_url(obtener_configuracion().redis_url, socket_timeout=2))


def obtener_contador_ventana() -> ContadorVentana:
    """El contador del límite por IP en Redis. Las pruebas lo sobreescriben con ContadorVentanaEnMemoria."""
    return _contador_redis()


def ip_del_cliente(request: Request) -> str:
    """La IP del cliente, ya resuelta por MiddlewareProxy desde un proxy de confianza. Solo para su huella."""
    return request.client.host if request.client else "desconocida"


def limite_por_ip(limite: LimitePorIp) -> Callable[..., None]:
    """La dependencia de FastAPI que cuenta la petición y responde 429 o 503."""

    def verificar_limite_ip(
        request: Request,
        pepper: Annotated[bytes | None, Depends(obtener_pepper_limites)],
        contador: Annotated[ContadorVentana, Depends(obtener_contador_ventana)],
    ) -> None:
        if pepper is None:
            log.error("falta PEPPER_LIMITES: el límite por IP falla cerrado")
            raise ErrorMATU(503, detalle=DETALLE_503)
        clave = clave_de(limite, huella(pepper, limite.prefijo, ip_del_cliente(request)))
        try:
            resultado = contador.sumar(clave, limite.ventana_segundos)
        except ContadorNoDisponible:
            log.error("Redis no responde: el límite por IP falla cerrado")
            raise ErrorMATU(503, detalle=DETALLE_503) from None
        if excedido(resultado.conteo, limite):
            raise ErrorMATU(
                429,
                detalle=DETALLE_429,
                headers={"Retry-After": str(retry_after(resultado.ttl_segundos, limite))},
            )

    verificar_limite_ip.__name__ = f"limite_ip_{limite.prefijo.replace('-', '_')}"
    return verificar_limite_ip

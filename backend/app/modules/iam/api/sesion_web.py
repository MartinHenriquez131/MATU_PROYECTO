"""Piezas web de la sesión de MATU-38: la cookie del refresh y las dependencias de la unidad y de los
contadores de la entrada.

La cookie se lee de request.cookies y nunca se registra. Se arma a mano (y no con set_cookie) para
fijar exactamente los atributos del contrato.
"""

from functools import lru_cache
from typing import Annotated, Any

import redis
from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import obtener_configuracion
from app.core.db import obtener_fabrica_sesiones
from app.modules.iam.api.dependencias import obtener_reloj
from app.modules.iam.application.ports import ContadoresEntrada, UnidadIam
from app.modules.iam.domain.refresh import MAX_AGE_REFRESH, NOMBRE_COOKIE, RUTA_COOKIE
from app.modules.iam.infrastructure.contadores_redis import ContadoresEntradaRedis
from app.modules.iam.infrastructure.repositorio_sesiones import UnidadIamSql
from app.shared.puertos import Reloj

PROBLEMA: dict[str, Any] = {"content": {"application/problem+json": {}}}

_ATRIBUTOS = f"Path={RUTA_COOKIE}; HttpOnly; Secure; SameSite=Strict"
BORRAR_COOKIE = f"{NOMBRE_COOKIE}=; Max-Age=0; {_ATRIBUTOS}"


def valor_cookie(refresh: str) -> str:
    return f"{NOMBRE_COOKIE}={refresh}; Max-Age={MAX_AGE_REFRESH}; {_ATRIBUTOS}"


def fijar_cookie(respuesta: Response, refresh: str) -> None:
    respuesta.headers["Set-Cookie"] = valor_cookie(refresh)


def borrar_cookie(respuesta: Response) -> None:
    respuesta.headers["Set-Cookie"] = BORRAR_COOKIE


def cookie_refresh(request: Request) -> str | None:
    return request.cookies.get(NOMBRE_COOKIE)


def request_id(request: Request) -> str | None:
    valor = getattr(request.state, "request_id", None)
    return valor if isinstance(valor, str) else None


def obtener_pepper_limites() -> bytes | None:
    """La llave de las huellas de la demora. None si falta: la entrada responde 503."""
    pepper = obtener_configuracion().pepper_limites
    return None if pepper is None else pepper.get_secret_value().encode("utf-8")


@lru_cache
def _contadores_redis() -> ContadoresEntrada:
    return ContadoresEntradaRedis(redis.Redis.from_url(obtener_configuracion().redis_url, socket_timeout=2))


def obtener_contadores() -> ContadoresEntrada:
    """Los contadores de la entrada en Redis. Las pruebas la sobreescriben con ContadoresEnMemoria."""
    return _contadores_redis()


def obtener_unidad(
    fabrica: Annotated[sessionmaker[Session], Depends(obtener_fabrica_sesiones)],
    reloj: Annotated[Reloj, Depends(obtener_reloj)],
) -> UnidadIam:
    return UnidadIamSql(fabrica, reloj)


PepperLimitesDep = Annotated[bytes | None, Depends(obtener_pepper_limites)]
ContadoresDep = Annotated[ContadoresEntrada, Depends(obtener_contadores)]
UnidadDep = Annotated[UnidadIam, Depends(obtener_unidad)]

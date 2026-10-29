"""Sesiones de relevo en Redis (MATU-19, condiciones C9 y C10 del analista normativo).

- El id de sesión es ``secrets.token_urlsafe(32)``: 256 bits. Va solo en la cookie.
- La clave en Redis es el SHA-256 del id, nunca el id: una copia de Redis no sirve como cookie.
- El valor es solo el id del acceso. Nada de la ficha, del relevo ni del token.
- El TTL es el Max-Age de la cookie, en el mismo SET … EX.
- Si Redis no responde, SesionesNoDisponibles: la API responde 503 y falla cerrada. Nunca se registra
  el id ni la clave.
"""

import hashlib
import secrets
import uuid

import redis

from app.modules.care_plan.application.ports import SesionesNoDisponibles

PREFIJO = "matu:relevo:sesion:"
BYTES_SESION = 32


def clave_de(sesion_id: str) -> str:
    return PREFIJO + hashlib.sha256(sesion_id.encode("utf-8")).hexdigest()


class SesionesRelevoRedis:
    def __init__(self, cliente: "redis.Redis") -> None:
        self._redis = cliente

    def __repr__(self) -> str:
        return "SesionesRelevoRedis()"

    def crear(self, acceso_id: uuid.UUID, segundos: int) -> str:
        sesion_id = secrets.token_urlsafe(BYTES_SESION)
        try:
            self._redis.set(clave_de(sesion_id), str(acceso_id), ex=segundos)
        except redis.RedisError:
            raise SesionesNoDisponibles from None
        return sesion_id

    def acceso_de(self, sesion_id: str) -> uuid.UUID | None:
        try:
            valor = self._redis.get(clave_de(sesion_id))
        except redis.RedisError:
            raise SesionesNoDisponibles from None
        if valor is None:
            return None
        try:
            return uuid.UUID(valor.decode("ascii") if isinstance(valor, bytes) else str(valor))
        except ValueError:
            return None

    def descartar(self, sesion_id: str) -> None:
        try:
            self._redis.delete(clave_de(sesion_id))
        except redis.RedisError:
            raise SesionesNoDisponibles from None

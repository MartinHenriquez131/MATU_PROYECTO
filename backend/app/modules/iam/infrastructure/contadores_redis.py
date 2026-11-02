"""Contadores de la demora progresiva de la entrada en Redis (MATU-38, decisión 49).

- La clave es la huella HMAC (nunca la IP ni el email): matu:entrada:<huella>.
- El valor es un hash con fallos y el instante del último fallo (segundos epoch del Reloj).
- La ventana vence a la hora del primer fallo: EXPIRE … NX, que solo fija el TTL si no tenía.
- Si Redis no responde, ContadoresNoDisponibles: la API responde 503 y falla cerrada. Nunca se
  registra la huella.
"""

from datetime import UTC, datetime

import redis

from app.modules.iam.application.ports import ContadoresNoDisponibles
from app.modules.iam.domain.demora import SIN_FALLOS, VENTANA_CONTADOR, ContadorFallos

PREFIJO = "matu:entrada:"
_VENTANA_SEGUNDOS = int(VENTANA_CONTADOR.total_seconds())


def clave_de(huella: str) -> str:
    return PREFIJO + huella


def _texto(valor: object) -> str | None:
    if valor is None:
        return None
    return valor.decode("ascii") if isinstance(valor, bytes) else str(valor)


class ContadoresEntradaRedis:
    def __init__(self, cliente: "redis.Redis") -> None:
        self._redis = cliente

    def __repr__(self) -> str:
        return "ContadoresEntradaRedis()"

    def leer(self, huella: str) -> ContadorFallos:
        try:
            fallos, ultimo = self._redis.hmget(clave_de(huella), ["fallos", "ultimo"])
        except redis.RedisError:
            raise ContadoresNoDisponibles from None
        texto_fallos, texto_ultimo = _texto(fallos), _texto(ultimo)
        if texto_fallos is None or texto_ultimo is None:
            return SIN_FALLOS
        try:
            return ContadorFallos(int(texto_fallos), datetime.fromtimestamp(float(texto_ultimo), UTC))
        except (ValueError, OverflowError, OSError):
            return SIN_FALLOS

    def sumar_fallo(self, huella: str, ahora: datetime) -> None:
        clave = clave_de(huella)
        try:
            tuberia = self._redis.pipeline(transaction=True)
            tuberia.hincrby(clave, "fallos", 1)
            tuberia.hset(clave, "ultimo", repr(ahora.timestamp()))
            tuberia.expire(clave, _VENTANA_SEGUNDOS, nx=True)
            tuberia.execute()
        except redis.RedisError:
            raise ContadoresNoDisponibles from None

    def borrar(self, huella: str) -> None:
        try:
            self._redis.delete(clave_de(huella))
        except redis.RedisError:
            raise ContadoresNoDisponibles from None

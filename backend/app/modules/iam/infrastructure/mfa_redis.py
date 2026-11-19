"""El segundo factor en Redis (MATU-81, C29 y C32).

- Desafío: hash matu:mfa:desafio:<SHA-256 del desafío> con la cuenta y su vencimiento (epoch del Reloj), con TTL de
  Redis hasta el vencimiento. El desafío en claro nunca llega a Redis.
- Fallos: matu:mfa:fallos:<huella HMAC de la cuenta>, INCR con EXPIRE … NX (la ventana vence a la hora del primer
  fallo).
- Anti-repetición: matu:mfa:paso:<huella>, el último paso aceptado. Un script Lua lo compara y lo guarda en un paso.
- Si Redis no responde, ContadoresNoDisponibles (503). Nunca se registra una clave ni una huella.
"""

import uuid
from datetime import UTC, datetime

import redis

from app.modules.iam.application.ports import ContadoresNoDisponibles, DesafioGuardado
from app.modules.iam.domain.mfa import SIN_FALLOS, FallosMfa

PREFIJO_DESAFIO = "matu:mfa:desafio:"
PREFIJO_FALLOS = "matu:mfa:fallos:"
PREFIJO_PASO = "matu:mfa:paso:"

_SUMAR = (
    "local n = redis.call('incr', KEYS[1]) redis.call('expire', KEYS[1], ARGV[1], 'NX')"
    " return {n, redis.call('ttl', KEYS[1])}"
)
_USAR_PASO = (
    "local ultimo = tonumber(redis.call('get', KEYS[1]) or '-1')"
    " if tonumber(ARGV[1]) <= ultimo then return 0 end"
    " redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2]) return 1"
)


def _texto(valor: object) -> str | None:
    if valor is None:
        return None
    return valor.decode("ascii") if isinstance(valor, bytes) else str(valor)


class AlmacenMfaRedis:
    def __init__(self, cliente: "redis.Redis") -> None:
        self._redis = cliente

    def __repr__(self) -> str:
        return "AlmacenMfaRedis()"

    def guardar_desafio(self, huella: str, desafio: DesafioGuardado) -> None:
        llave = PREFIJO_DESAFIO + huella
        try:
            tuberia = self._redis.pipeline(transaction=True)
            tuberia.hset(
                llave, mapping={"usuario": str(desafio.usuario_id), "expira": repr(desafio.expira_en.timestamp())}
            )
            tuberia.expireat(llave, int(desafio.expira_en.timestamp()) + 1)
            tuberia.execute()
        except redis.RedisError:
            raise ContadoresNoDisponibles from None

    def leer_desafio(self, huella: str) -> DesafioGuardado | None:
        try:
            usuario, expira = self._redis.hmget(PREFIJO_DESAFIO + huella, ["usuario", "expira"])
        except redis.RedisError:
            raise ContadoresNoDisponibles from None
        texto_usuario, texto_expira = _texto(usuario), _texto(expira)
        if texto_usuario is None or texto_expira is None:
            return None
        try:
            return DesafioGuardado(uuid.UUID(texto_usuario), datetime.fromtimestamp(float(texto_expira), UTC))
        except (ValueError, OverflowError, OSError):
            return None

    def borrar_desafio(self, huella: str) -> bool:
        try:
            return bool(self._redis.delete(PREFIJO_DESAFIO + huella))
        except redis.RedisError:
            raise ContadoresNoDisponibles from None

    def leer_fallos(self, cuenta: str) -> FallosMfa:
        llave = PREFIJO_FALLOS + cuenta
        try:
            tuberia = self._redis.pipeline(transaction=True)
            tuberia.get(llave)
            tuberia.ttl(llave)
            valor, ttl = tuberia.execute()
        except redis.RedisError:
            raise ContadoresNoDisponibles from None
        texto = _texto(valor)
        return SIN_FALLOS if texto is None else FallosMfa(int(texto), max(0, int(ttl)))

    def sumar_fallo(self, cuenta: str, ventana_segundos: int) -> FallosMfa:
        try:
            n, ttl = self._redis.eval(_SUMAR, 1, PREFIJO_FALLOS + cuenta, ventana_segundos)  # type: ignore[no-untyped-call]
        except redis.RedisError:
            raise ContadoresNoDisponibles from None
        return FallosMfa(int(n), max(0, int(ttl)))

    def borrar_fallos(self, cuenta: str) -> None:
        try:
            self._redis.delete(PREFIJO_FALLOS + cuenta)
        except redis.RedisError:
            raise ContadoresNoDisponibles from None

    def usar_paso(self, cuenta: str, paso: int, vida_segundos: int) -> bool:
        try:
            return bool(self._redis.eval(_USAR_PASO, 1, PREFIJO_PASO + cuenta, paso, vida_segundos))  # type: ignore[no-untyped-call]
        except redis.RedisError:
            raise ContadoresNoDisponibles from None

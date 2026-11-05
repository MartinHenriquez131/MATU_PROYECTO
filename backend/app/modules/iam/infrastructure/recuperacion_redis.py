"""Códigos de MATU-57 y contadores de envíos en Redis (decisiones 83 y 84).

- Código: hash matu:codigo:<clave> con la huella, el vencimiento (epoch del Reloj), el canal y los
  intentos. TTL de Redis hasta el vencimiento. La clave es la huella del usuario, nunca el email.
- Envíos: dos hashes por huella, matu:envios:h:<huella> (ventana de una hora) y matu:envios:d:<huella>
  (un día), con cuántos y el inicio de la ventana (EXPIRE … NX), y el último envío en el de la hora.
- Si Redis no responde, ContadoresNoDisponibles. Nunca se registra una clave ni una huella.
"""

from datetime import UTC, datetime

import redis

from app.modules.iam.application.ports import ContadoresNoDisponibles
from app.modules.iam.domain.recuperacion import (
    SIN_ENVIOS,
    VENTANA_DIA,
    VENTANA_HORA,
    Canal,
    CodigoGuardado,
    EnviosRecientes,
)

PREFIJO_CODIGO = "matu:codigo:"
PREFIJO_HORA = "matu:envios:h:"
PREFIJO_DIA = "matu:envios:d:"

_SUMAR_INTENTO = (
    "if redis.call('exists', KEYS[1]) == 1 then return redis.call('hincrby', KEYS[1], 'intentos', 1)"
    " else return 0 end"
)


def _texto(valor: object) -> str | None:
    if valor is None:
        return None
    return valor.decode("ascii") if isinstance(valor, bytes) else str(valor)


def _instante(valor: object) -> datetime | None:
    texto = _texto(valor)
    if texto is None:
        return None
    try:
        return datetime.fromtimestamp(float(texto), UTC)
    except (ValueError, OverflowError, OSError):
        return None


class AlmacenCodigosRedis:
    def __init__(self, cliente: "redis.Redis") -> None:
        self._redis = cliente

    def __repr__(self) -> str:
        return "AlmacenCodigosRedis()"

    def guardar(self, clave: str, codigo: CodigoGuardado) -> None:
        llave = PREFIJO_CODIGO + clave
        try:
            tuberia = self._redis.pipeline(transaction=True)
            tuberia.delete(llave)
            tuberia.hset(
                llave,
                mapping={
                    "huella": codigo.huella,
                    "expira": repr(codigo.expira_en.timestamp()),
                    "canal": codigo.canal.value,
                    "intentos": 0,
                },
            )
            tuberia.expireat(llave, int(codigo.expira_en.timestamp()) + 1)
            tuberia.execute()
        except redis.RedisError:
            raise ContadoresNoDisponibles from None

    def leer(self, clave: str) -> CodigoGuardado | None:
        try:
            huella, expira, canal = self._redis.hmget(PREFIJO_CODIGO + clave, ["huella", "expira", "canal"])
        except redis.RedisError:
            raise ContadoresNoDisponibles from None
        texto_huella, instante, texto_canal = _texto(huella), _instante(expira), _texto(canal)
        if texto_huella is None or instante is None or texto_canal not in {c.value for c in Canal}:
            return None
        return CodigoGuardado(huella=texto_huella, expira_en=instante, canal=Canal(texto_canal))

    def sumar_intento(self, clave: str) -> int:
        llave = PREFIJO_CODIGO + clave
        try:
            # Atómico: un código que vence entre la lectura y la suma no deja una llave sin TTL
            return int(self._redis.eval(_SUMAR_INTENTO, 1, llave))  # type: ignore[no-untyped-call]
        except redis.RedisError:
            raise ContadoresNoDisponibles from None

    def consumir(self, clave: str) -> bool:
        try:
            return bool(self._redis.delete(PREFIJO_CODIGO + clave))
        except redis.RedisError:
            raise ContadoresNoDisponibles from None


class ContadoresEnvioRedis:
    def __init__(self, cliente: "redis.Redis") -> None:
        self._redis = cliente

    def __repr__(self) -> str:
        return "ContadoresEnvioRedis()"

    def leer(self, huella: str) -> EnviosRecientes:
        try:
            hora = self._redis.hmget(PREFIJO_HORA + huella, ["n", "inicio", "ultimo"])
            dia = self._redis.hmget(PREFIJO_DIA + huella, ["n", "inicio"])
        except redis.RedisError:
            raise ContadoresNoDisponibles from None
        en_hora, en_dia = _texto(hora[0]), _texto(dia[0])
        if en_hora is None and en_dia is None:
            return SIN_ENVIOS
        return EnviosRecientes(
            ultimo=_instante(hora[2]),
            en_hora=int(en_hora or 0),
            inicio_hora=_instante(hora[1]),
            en_dia=int(en_dia or 0),
            inicio_dia=_instante(dia[1]),
        )

    def sumar(self, huella: str, ahora: datetime) -> None:
        momento = repr(ahora.timestamp())
        try:
            tuberia = self._redis.pipeline(transaction=True)
            for prefijo, ventana in ((PREFIJO_HORA, VENTANA_HORA), (PREFIJO_DIA, VENTANA_DIA)):
                llave = prefijo + huella
                tuberia.hincrby(llave, "n", 1)
                tuberia.hsetnx(llave, "inicio", momento)
                tuberia.expire(llave, int(ventana.total_seconds()), nx=True)
            tuberia.hset(PREFIJO_HORA + huella, "ultimo", momento)
            tuberia.execute()
        except redis.RedisError:
            raise ContadoresNoDisponibles from None

"""MATU-81 · El almacén del segundo factor en el Redis local (C29 y C32). Se salta sin Redis."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import redis

from app.core.config import obtener_configuracion
from app.modules.iam.application.ports import ContadoresNoDisponibles, DesafioGuardado
from app.modules.iam.infrastructure.mfa_redis import PREFIJO_DESAFIO, PREFIJO_FALLOS, PREFIJO_PASO, AlmacenMfaRedis


def _cliente() -> "redis.Redis | None":
    cliente = redis.Redis.from_url(obtener_configuracion().redis_url.get_secret_value(), socket_timeout=1)
    try:
        cliente.ping()
    except redis.RedisError:
        return None
    return cliente


CLIENTE = _cliente()
pytestmark = [pytest.mark.rf("RF-37"), pytest.mark.skipif(CLIENTE is None, reason="Redis no disponible")]


def test_desafio_fallos_y_paso_en_redis() -> None:
    assert CLIENTE is not None
    almacen = AlmacenMfaRedis(CLIENTE)
    huella, cuenta = secrets.token_hex(32), secrets.token_hex(32)
    usuario = uuid.uuid4()
    try:
        almacen.guardar_desafio(huella, DesafioGuardado(usuario, datetime.now(UTC) + timedelta(minutes=5)))
        assert 0 < CLIENTE.ttl(PREFIJO_DESAFIO + huella) <= 302
        leido = almacen.leer_desafio(huella)
        assert leido is not None and leido.usuario_id == usuario
        # Solo la cuenta y el vencimiento: nunca el desafío en claro
        assert set(CLIENTE.hkeys(PREFIJO_DESAFIO + huella)) == {b"usuario", b"expira"}
        assert almacen.borrar_desafio(huella) is True and almacen.borrar_desafio(huella) is False
        assert almacen.leer_fallos(cuenta).conteo == 0
        for n in range(1, 6):
            assert almacen.sumar_fallo(cuenta, 900).conteo == n
        fallos = almacen.leer_fallos(cuenta)
        assert fallos.agotados and 0 < fallos.segundos_restantes <= 900
        almacen.borrar_fallos(cuenta)
        assert almacen.leer_fallos(cuenta).conteo == 0
        assert almacen.usar_paso(cuenta, 100, 120) is True
        assert almacen.usar_paso(cuenta, 100, 120) is False and almacen.usar_paso(cuenta, 99, 120) is False
        assert almacen.usar_paso(cuenta, 101, 120) is True
    finally:
        CLIENTE.delete(PREFIJO_DESAFIO + huella, PREFIJO_FALLOS + cuenta, PREFIJO_PASO + cuenta)


def test_sin_redis_lanza_contadores_no_disponibles() -> None:
    almacen = AlmacenMfaRedis(redis.Redis(host="127.0.0.1", port=1, socket_timeout=0.2))
    with pytest.raises(ContadoresNoDisponibles):
        almacen.leer_desafio("x")
    with pytest.raises(ContadoresNoDisponibles):
        almacen.sumar_fallo("x", 900)

"""MATU-57 · Adaptadores de códigos y envíos en el Redis local (decisiones 83 y 84). Se salta sin Redis."""

import secrets
from datetime import UTC, datetime, timedelta

import pytest
import redis

from app.core.config import obtener_configuracion
from app.modules.iam.domain.recuperacion import SIN_ENVIOS, Canal, codigo_nuevo
from app.modules.iam.infrastructure.recuperacion_redis import (
    PREFIJO_CODIGO,
    PREFIJO_DIA,
    PREFIJO_HORA,
    AlmacenCodigosRedis,
    ContadoresEnvioRedis,
)


def _cliente() -> "redis.Redis | None":
    cliente = redis.Redis.from_url(obtener_configuracion().redis_url, socket_timeout=1)
    try:
        cliente.ping()
    except redis.RedisError:
        return None
    return cliente


CLIENTE = _cliente()
pytestmark = [pytest.mark.rf("RF-37"), pytest.mark.skipif(CLIENTE is None, reason="Redis no disponible")]


def test_codigo_con_ttl_intentos_y_un_solo_uso() -> None:
    assert CLIENTE is not None
    almacen = AlmacenCodigosRedis(CLIENTE)
    clave = secrets.token_hex(32)
    ahora = datetime.now(UTC)
    try:
        assert almacen.leer(clave) is None and almacen.sumar_intento(clave) == 0
        almacen.guardar(clave, codigo_nuevo("h" * 64, Canal.SMS, ahora))
        assert 0 < CLIENTE.ttl(PREFIJO_CODIGO + clave) <= 601
        leido = almacen.leer(clave)
        assert leido is not None and leido.huella == "h" * 64 and leido.canal is Canal.SMS
        assert almacen.sumar_intento(clave) == 1
        # Uno nuevo reemplaza al anterior, con sus intentos en cero
        almacen.guardar(clave, codigo_nuevo("g" * 64, Canal.CORREO, ahora))
        assert almacen.sumar_intento(clave) == 1
        assert almacen.consumir(clave) is True
        assert almacen.consumir(clave) is False
        assert almacen.sumar_intento(clave) == 0 and not CLIENTE.exists(PREFIJO_CODIGO + clave)
    finally:
        CLIENTE.delete(PREFIJO_CODIGO + clave)


def test_envios_con_ventanas_de_hora_y_dia() -> None:
    assert CLIENTE is not None
    envios = ContadoresEnvioRedis(CLIENTE)
    huella = secrets.token_hex(32)
    primero = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
    try:
        assert envios.leer(huella) == SIN_ENVIOS
        envios.sumar(huella, primero)
        envios.sumar(huella, primero + timedelta(minutes=2))
        leido = envios.leer(huella)
        assert (leido.en_hora, leido.en_dia) == (2, 2)
        assert leido.inicio_hora == primero and leido.ultimo == primero + timedelta(minutes=2)
        assert 0 < CLIENTE.ttl(PREFIJO_HORA + huella) <= 3600
        assert 3600 < CLIENTE.ttl(PREFIJO_DIA + huella) <= 86400
    finally:
        CLIENTE.delete(PREFIJO_HORA + huella, PREFIJO_DIA + huella)

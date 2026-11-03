"""MATU-38 · Adaptador ContadoresEntradaRedis contra el Redis local (decisión 49). Se salta si no hay Redis."""

import secrets
from datetime import UTC, datetime

import pytest
import redis

from app.core.config import obtener_configuracion
from app.modules.iam.application.ports import ContadoresNoDisponibles
from app.modules.iam.domain.demora import SIN_FALLOS
from app.modules.iam.infrastructure.contadores_redis import PREFIJO, ContadoresEntradaRedis


def _cliente() -> "redis.Redis | None":
    cliente = redis.Redis.from_url(obtener_configuracion().redis_url, socket_timeout=1)
    try:
        cliente.ping()
    except redis.RedisError:
        return None
    return cliente


CLIENTE = _cliente()
pytestmark = [pytest.mark.rf("RF-37"), pytest.mark.skipif(CLIENTE is None, reason="Redis no disponible")]


def test_cuenta_fallos_bajo_la_huella_con_ventana_de_una_hora() -> None:
    assert CLIENTE is not None
    contadores = ContadoresEntradaRedis(CLIENTE)
    huella = secrets.token_hex(32)
    primero = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    segundo = datetime(2026, 11, 2, 12, 5, 30, tzinfo=UTC)
    try:
        assert contadores.leer(huella) == SIN_FALLOS
        contadores.sumar_fallo(huella, primero)
        ttl_inicial = CLIENTE.ttl(PREFIJO + huella)
        contadores.sumar_fallo(huella, segundo)
        leido = contadores.leer(huella)
        assert (leido.fallos, leido.ultimo_fallo) == (2, segundo)
        # La ventana es desde el primer fallo: el segundo no la alarga
        assert 0 < CLIENTE.ttl(PREFIJO + huella) <= ttl_inicial <= 3600
        # La clave es la huella: nada más que fallos y último
        assert set(CLIENTE.hkeys(PREFIJO + huella)) == {b"fallos", b"ultimo"}
        contadores.borrar(huella)
        assert contadores.leer(huella) == SIN_FALLOS
    finally:
        CLIENTE.delete(PREFIJO + huella)


def test_sin_redis_falla_cerrado() -> None:
    caido = ContadoresEntradaRedis(redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2))
    ahora = datetime(2026, 11, 2, tzinfo=UTC)
    for llamada in (lambda: caido.leer("h"), lambda: caido.sumar_fallo("h", ahora), lambda: caido.borrar("h")):
        with pytest.raises(ContadoresNoDisponibles):
            llamada()

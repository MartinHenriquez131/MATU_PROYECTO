"""MATU-25 · ContadorVentanaRedis contra el Redis local: ventana fija y ninguna clave sin vencimiento.

Se salta si no hay Redis (el pipeline lo tiene). El doble en memoria lo reemplaza en las pruebas de la API.
"""

import secrets

import pytest
import redis

from app.core.config import obtener_configuracion
from app.core.limite_ip import ContadorNoDisponible, ContadorVentanaRedis, clave_de
from app.shared.limite_ip import LIMITE_CANJE, LIMITE_PRESENTACION, LIMITE_REGISTRO, huella

IP = "198.51.100.77"  # sintética (RFC 5737)


def _cliente() -> "redis.Redis | None":
    cliente = redis.Redis.from_url(obtener_configuracion().redis_url, socket_timeout=1)
    try:
        cliente.ping()
    except redis.RedisError:
        return None
    return cliente


CLIENTE = _cliente()
pytestmark = [pytest.mark.rf("RF-37"), pytest.mark.skipif(CLIENTE is None, reason="Redis no disponible")]


def _clave_unica() -> str:
    return clave_de(LIMITE_REGISTRO, huella(secrets.token_bytes(32), LIMITE_REGISTRO.prefijo, IP))


def test_el_primer_incremento_fija_una_hora_y_los_siguientes_no_la_renuevan() -> None:
    assert CLIENTE is not None
    contador = ContadorVentanaRedis(CLIENTE)
    clave = _clave_unica()
    try:
        primero = contador.sumar(clave, 3600)
        assert primero.conteo == 1
        assert 3590 <= primero.ttl_segundos <= 3600
        assert 3590 <= CLIENTE.ttl(clave) <= 3600
        # Se acorta el vencimiento a mano: si un incremento lo renovara, volvería a 3600
        CLIENTE.expire(clave, 120)
        segundo = contador.sumar(clave, 3600)
        assert segundo.conteo == 2
        assert 0 < segundo.ttl_segundos <= 120
        assert 0 < CLIENTE.ttl(clave) <= 120
    finally:
        CLIENTE.delete(clave)


def test_una_clave_sin_vencimiento_recibe_uno() -> None:
    assert CLIENTE is not None
    contador = ContadorVentanaRedis(CLIENTE)
    clave = _clave_unica()
    try:
        CLIENTE.set(clave, 7)  # sin EX: no debería existir, pero si existe, no vive para siempre
        assert CLIENTE.ttl(clave) == -1
        resultado = contador.sumar(clave, 3600)
        assert resultado.conteo == 8
        assert 3590 <= CLIENTE.ttl(clave) <= 3600
    finally:
        CLIENTE.delete(clave)


def test_la_clave_lleva_el_prefijo_y_la_huella_nunca_la_ip() -> None:
    pepper = secrets.token_bytes(32)
    claves = {clave_de(lim, huella(pepper, lim.prefijo, IP)) for lim in (LIMITE_REGISTRO, LIMITE_CANJE,
                                                                         LIMITE_PRESENTACION)}
    assert len(claves) == 3
    for clave in claves:
        assert IP not in clave
        assert clave.startswith("matu:limite:")
    assert any(c.startswith("matu:limite:canje-ip:") for c in claves)


def test_sin_redis_falla_cerrado() -> None:
    caido = ContadorVentanaRedis(redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2))
    with pytest.raises(ContadorNoDisponible):
        caido.sumar("matu:limite:usuarios-ip:x", 3600)

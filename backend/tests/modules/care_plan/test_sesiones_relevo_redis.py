"""MATU-19 · Adaptador SesionesRelevoRedis contra el Redis local (C9 y C10). Se salta si no hay Redis."""

import hashlib
import uuid

import pytest
import redis

from app.core.config import obtener_configuracion
from app.modules.care_plan.application.ports import SesionesNoDisponibles
from app.modules.care_plan.infrastructure.sesiones_relevo_redis import PREFIJO, SesionesRelevoRedis


def _cliente() -> "redis.Redis | None":
    cliente = redis.Redis.from_url(obtener_configuracion().redis_url, socket_timeout=1)
    try:
        cliente.ping()
    except redis.RedisError:
        return None
    return cliente


CLIENTE = _cliente()
pytestmark = [pytest.mark.rf("RF-06"), pytest.mark.skipif(CLIENTE is None, reason="Redis no disponible")]


def test_guarda_solo_el_acceso_bajo_la_huella_del_id_con_ttl() -> None:
    assert CLIENTE is not None
    sesiones = SesionesRelevoRedis(CLIENTE)
    acceso = uuid.uuid4()
    sesion_id = sesiones.crear(acceso, 120)
    try:
        assert len(sesion_id) >= 43  # 256 bits
        clave = PREFIJO + hashlib.sha256(sesion_id.encode()).hexdigest()
        assert CLIENTE.get(clave) == str(acceso).encode()
        assert 0 < CLIENTE.ttl(clave) <= 120
        assert CLIENTE.get(PREFIJO + sesion_id) is None and not CLIENTE.keys(f"*{sesion_id}*")
        assert sesiones.acceso_de(sesion_id) == acceso
        assert sesiones.acceso_de("otra") is None
    finally:
        sesiones.descartar(sesion_id)
    assert sesiones.acceso_de(sesion_id) is None


def test_sin_redis_falla_cerrado() -> None:
    caido = SesionesRelevoRedis(redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2))
    with pytest.raises(SesionesNoDisponibles):
        caido.crear(uuid.uuid4(), 60)
    with pytest.raises(SesionesNoDisponibles):
        caido.acceso_de("x")

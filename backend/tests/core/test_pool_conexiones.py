"""MATU-80 · K1 del TESTER de Martín del 20-11: el pool de conexiones se configura, y lleno responde 503.

Con 50 usuarios en k6, la API respondía 500 con «sqlalchemy.pool … TimeoutError»: app/core/db.py creaba el motor sin
configurar el pool (5 conexiones más 10 de desborde, 30 s de espera). Desde K1:

- DB_POOL_SIZE, DB_MAX_OVERFLOW y DB_POOL_TIMEOUT (Configuracion) fijan el pool del motor de la API y de las tareas,
  con 10, 20 y 10 s por omisión;
- con el pool lleno más de DB_POOL_TIMEOUT, la petición responde 503 RFC 7807 con Retry-After, sin datos, y el log deja
  solo el evento.

Las pruebas de configuración leen solo el entorno que fijan, nunca el .env del equipo.
"""

import io
import json
import secrets
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.exc import TimeoutError as PoolAgotado
from sqlalchemy.orm import sessionmaker

from app import tareas
from app.core import db
from app.core.config import Configuracion, obtener_configuracion
from app.core.db import obtener_fabrica_sesiones, opciones_pool
from app.core.errores import DETALLE_POOL_AGOTADO, RETRY_AFTER_POOL_S, TIPO_PROBLEMA
from app.main import crear_app
from app.modules.iam.api.dependencias import obtener_clave_jwt
from app.modules.payments.infrastructure.pasarela import obtener_pasarela
from tests.base_datos import requiere_base

pytestmark = [pytest.mark.rf("RNF-05")]

# Sin contraseña: detect-secrets no la confunde con un secreto, y crear el engine no conecta
URL_SINTETICA = "postgresql+psycopg://u@db.invalid/x"
VARIABLES = ("DB_POOL_SIZE", "DB_MAX_OVERFLOW", "DB_POOL_TIMEOUT")


class ConfiguracionSinArchivo(Configuracion):
    model_config = SettingsConfigDict(env_file=None)


@pytest.fixture
def sin_env(configuracion_sin_env: None) -> None:
    """La configuración sin el .env del equipo (tests/conftest.py)."""


@pytest.fixture
def engine_de_la_api_sin_cache() -> Iterator[None]:
    # MATU-80 (RNF-05): también la fábrica, que guarda el engine. Si no, la API sigue con el engine anterior y las
    # pruebas que vienen después miran uno que la API ya no usa
    db.obtener_engine.cache_clear()
    db.fabrica_sesiones.cache_clear()
    yield
    db.obtener_engine.cache_clear()
    db.fabrica_sesiones.cache_clear()


# --- La configuración -------------------------------------------------------------------------------------------


def test_por_omision_el_pool_es_de_10_mas_20_con_10_segundos(sin_env: None) -> None:
    config = ConfiguracionSinArchivo()
    assert (config.db_pool_size, config.db_max_overflow, config.db_pool_timeout) == (10, 20, 10)


def test_el_pool_se_lee_del_entorno(sin_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_POOL_SIZE", "15")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "5")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "3")
    config = ConfiguracionSinArchivo()
    assert (config.db_pool_size, config.db_max_overflow, config.db_pool_timeout) == (15, 5, 3)


def test_vacias_valen_lo_de_omision(sin_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    # DB_POOL_SIZE= en el .env o en Railway: como no definida
    for variable in VARIABLES:
        monkeypatch.setenv(variable, "")
    config = ConfiguracionSinArchivo()
    assert (config.db_pool_size, config.db_max_overflow, config.db_pool_timeout) == (10, 20, 10)


@pytest.mark.parametrize(
    ("variable", "valor"),
    [
        ("DB_POOL_SIZE", "0"),
        ("DB_POOL_SIZE", "51"),
        ("DB_MAX_OVERFLOW", "-1"),
        ("DB_MAX_OVERFLOW", "51"),
        ("DB_POOL_TIMEOUT", "0"),
        ("DB_POOL_TIMEOUT", "61"),
        ("DB_POOL_SIZE", "diez"),
    ],
)
def test_un_valor_fuera_de_rango_no_carga(
    sin_env: None, monkeypatch: pytest.MonkeyPatch, variable: str, valor: str
) -> None:
    # Fuera de rango, la API no arranca: nunca un pool de 0 conexiones ni uno que se coma las 100 de Railway
    monkeypatch.setenv(variable, valor)
    with pytest.raises(ValidationError) as error:
        ConfiguracionSinArchivo()
    assert variable.lower() in str(error.value)


# --- Los motores --------------------------------------------------------------------------------------------------


def test_opciones_pool_lleva_la_configuracion_el_pre_ping_y_los_parametros_ocultos() -> None:
    config = obtener_configuracion().model_copy(update={"db_pool_size": 4, "db_max_overflow": 6, "db_pool_timeout": 2})
    assert opciones_pool(config) == {
        "pool_size": 4,
        "max_overflow": 6,
        "pool_timeout": 2,
        "pool_pre_ping": True,
        "hide_parameters": True,
    }


def test_el_engine_de_la_api_usa_el_pool_configurado(
    monkeypatch: pytest.MonkeyPatch, engine_de_la_api_sin_cache: None
) -> None:
    config = obtener_configuracion().model_copy(
        update={
            "database_url": SecretStr(URL_SINTETICA),
            "db_pool_size": 12,
            "db_max_overflow": 7,
            "db_pool_timeout": 4,
        }
    )
    monkeypatch.setattr(db, "obtener_configuracion", lambda: config)
    pool = db.obtener_engine().pool
    assert pool.size() == 12  # type: ignore[attr-defined]
    assert pool._max_overflow == 7  # type: ignore[attr-defined]
    assert pool._timeout == 4  # type: ignore[attr-defined]
    assert pool._pre_ping is True


@pytest.mark.parametrize("rol", [None, tareas.ROL_SCHEDULER, tareas.ROL_PUBLISHER])
def test_los_engines_de_las_tareas_usan_el_pool_configurado(rol: str | None) -> None:
    config = obtener_configuracion().model_copy(
        update={"database_url": SecretStr(URL_SINTETICA), "db_pool_size": 3, "db_max_overflow": 2, "db_pool_timeout": 5}
    )
    if rol is None:
        fabrica = tareas.fabrica_tareas(config)
    else:
        fabrica_rol = tareas.fabrica_de_rol(f"postgresql+psycopg://{rol}@db.invalid/x", rol, config)
        assert fabrica_rol is not None
        fabrica = fabrica_rol
    engine = fabrica.kw["bind"]
    assert (engine.pool.size(), engine.pool._max_overflow, engine.pool._timeout) == (3, 2, 5)
    assert engine.pool._pre_ping is True
    assert engine.hide_parameters is True


# --- Con el pool lleno: 503 con Retry-After ---------------------------------------------------------------------


def _lineas(salida: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip()]


def test_el_pool_agotado_responde_503_rfc7807_con_retry_after() -> None:
    salida = io.StringIO()
    app = crear_app(stream_logs=salida)

    @app.get("/prueba/pool-lleno")
    def pool_lleno() -> None:
        # El mensaje de SQLAlchemy, como el de verdad: nunca llega a la respuesta ni al log
        raise PoolAgotado("QueuePool limit of size 10 overflow 20 reached, connection timed out, timeout 10.00")

    with TestClient(app, raise_server_exceptions=False) as cliente:
        r = cliente.get("/prueba/pool-lleno")

    assert r.status_code == 503
    assert r.headers["content-type"].startswith(TIPO_PROBLEMA)
    assert r.headers["Retry-After"] == str(RETRY_AFTER_POOL_S)
    assert r.headers["Cache-Control"] == "no-store"
    cuerpo = r.json()
    assert cuerpo["type"] == "/errores/servicio-no-disponible"
    assert cuerpo["status"] == 503
    assert cuerpo["detail"] == DETALLE_POOL_AGOTADO
    assert cuerpo["request_id"] == r.headers["X-Request-ID"]
    assert "QueuePool" not in r.text
    lineas = _lineas(salida)
    [aviso] = [linea for linea in lineas if linea.get("evento") == "pool_agotado"]
    assert (aviso["nivel"], aviso["request_id"]) == ("WARNING", cuerpo["request_id"])
    [peticion] = [linea for linea in lineas if linea["mensaje"] == "peticion"]
    assert peticion["estado"] == 503
    assert "QueuePool" not in salida.getvalue()
    assert "traza" not in salida.getvalue()


@requiere_base
def test_con_el_pool_lleno_la_vuelta_de_webpay_responde_503_y_despues_vuelve() -> None:
    """Contra PostgreSQL, con un pool de una conexión y 1 s de espera: con la conexión ocupada, una ruta de verdad
    (POST /v1/pagos/retorno, que abre una transacción para buscar la venta) responde 503; libre, responde lo de
    siempre (404, el token no es de ninguna venta).

    Solo la base es real. La clave JWT y la pasarela son las de la prueba: la sesión opcional de la vuelta lee la
    clave antes de abrir la base, y sin JWT_CLAVE en el entorno (el CI no la define) respondía 500 por eso y no por el
    pool (CI del PR #128). El 503 se reconoce además por el evento pool_agotado del log."""
    url = obtener_configuracion().database_url.get_secret_value()
    assert url
    engine = create_engine(url, pool_size=1, max_overflow=0, pool_timeout=1, pool_pre_ping=True, hide_parameters=True)
    fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    salida = io.StringIO()
    app = crear_app(stream_logs=salida)
    app.dependency_overrides[obtener_fabrica_sesiones] = lambda: fabrica
    clave = secrets.token_hex(32).encode()
    app.dependency_overrides[obtener_clave_jwt] = lambda: clave
    app.dependency_overrides[obtener_pasarela] = lambda: None
    cuerpo = {"token_ws": secrets.token_hex(32)}
    try:
        with TestClient(app, raise_server_exceptions=False) as cliente:
            ocupada = engine.connect()
            try:
                inicio = time.perf_counter()
                lleno = cliente.post("/v1/pagos/retorno", json=cuerpo)
                espera = time.perf_counter() - inicio
            finally:
                ocupada.close()
            libre = cliente.post("/v1/pagos/retorno", json=cuerpo)
    finally:
        engine.dispose()

    errores = [linea.get("tipo_error") for linea in _lineas(salida) if linea.get("tipo_error")]
    assert lleno.status_code == 503, f"errores no controlados: {errores}"
    assert [linea for linea in _lineas(salida) if linea.get("evento") == "pool_agotado"]
    assert lleno.headers["Retry-After"] == str(RETRY_AFTER_POOL_S)
    assert lleno.json()["type"] == "/errores/servicio-no-disponible"
    assert 1 <= espera < 5  # esperó DB_POOL_TIMEOUT, no los 30 s de antes
    assert libre.status_code == 404

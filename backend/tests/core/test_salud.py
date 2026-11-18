"""MATU-79: GET /v1/salud comprueba la base (SELECT 1) y Redis (PING), y responde sin datos.

Los tres casos con dobles de las comprobaciones (las dos bien, la base caída y Redis caído), y el camino real contra
la base de pruebas y el Redis local o del pipeline. La falla nunca deja en la respuesta ni en el log el mensaje del
driver, la cadena de conexión ni qué componente falló (en la respuesta).
"""

import io
import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient

from app.core import salud
from app.core.salud import DETALLE_503, TIEMPO_LIMITE_S, obtener_comprobaciones
from app.main import crear_app
from tests.base_datos import requiere_base

PROBLEMA = "application/problem+json"
# Lo que diría un driver: host, usuario, contraseña y base. Nada de esto puede salir en la respuesta ni en el log
MENSAJE_DEL_DRIVER = "connection to server at db.interno (10.0.0.9), port 5432 failed: password=sintetica-123 matu_app"


@dataclass
class Salud:
    cliente: TestClient
    logs: io.StringIO
    llamadas: list[str] = field(default_factory=list)

    def lineas_log(self) -> list[dict[str, object]]:
        return [json.loads(linea) for linea in self.logs.getvalue().splitlines() if linea.strip()]


def _bien(nombre: str, llamadas: list[str]) -> Callable[[], None]:
    def comprobar() -> None:
        llamadas.append(nombre)

    return comprobar


def _caida(nombre: str, llamadas: list[str]) -> Callable[[], None]:
    def comprobar() -> None:
        llamadas.append(nombre)
        raise ConnectionError(MENSAJE_DEL_DRIVER)

    return comprobar


@pytest.fixture
def con_dobles(request: pytest.FixtureRequest) -> Iterator[Salud]:
    """La app con dobles de las dos comprobaciones. ``request.param`` dice cuál cae: None, "base" o "redis"."""
    cae = request.param
    salida = io.StringIO()
    app = crear_app(stream_logs=salida)
    entorno = Salud(cliente=TestClient(app, raise_server_exceptions=False), logs=salida)
    comprobaciones = tuple(
        (nombre, (_caida if nombre == cae else _bien)(nombre, entorno.llamadas)) for nombre in ("base", "redis")
    )
    app.dependency_overrides[obtener_comprobaciones] = lambda: comprobaciones
    with entorno.cliente:
        yield entorno


def _sin_detalle_interno(texto: str) -> None:
    for fragmento in (MENSAJE_DEL_DRIVER, "db.interno", "10.0.0.9", "5432", "sintetica-123", "matu_app"):
        assert fragmento not in texto


@pytest.mark.rf("MATU-79")
@pytest.mark.parametrize("con_dobles", [None], indirect=True)
def test_salud_con_la_base_y_redis_responde_200_sin_datos(con_dobles: Salud) -> None:
    respuesta = con_dobles.cliente.get("/v1/salud")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}
    assert con_dobles.llamadas == ["base", "redis"]
    assert not [linea for linea in con_dobles.lineas_log() if linea["logger"] == "matu.salud"]


@pytest.mark.rf("MATU-79")
@pytest.mark.parametrize("con_dobles", ["base", "redis"], indirect=True)
def test_salud_con_un_componente_caido_responde_503_rfc_7807_sin_detalle(con_dobles: Salud) -> None:
    respuesta = con_dobles.cliente.get("/v1/salud")

    assert respuesta.status_code == 503
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert respuesta.headers["Cache-Control"] == "no-store"
    cuerpo = respuesta.json()
    assert cuerpo == {
        "type": "/errores/servicio-no-disponible",
        "title": "Servicio no disponible",
        "status": 503,
        "detail": DETALLE_503,
        "errores": [],
        "request_id": respuesta.headers["X-Request-ID"],
    }
    # La respuesta no dice cuál falló ni trae el mensaje del driver
    _sin_detalle_interno(respuesta.text)
    assert "base" not in respuesta.text and "redis" not in respuesta.text.lower()
    # Se comprueban las dos aunque la primera falle
    assert con_dobles.llamadas == ["base", "redis"]


@pytest.mark.rf("MATU-79")
@pytest.mark.parametrize("con_dobles", ["base", "redis"], indirect=True)
def test_el_log_de_la_falla_dice_el_componente_y_el_tipo_sin_el_mensaje(
    con_dobles: Salud, request: pytest.FixtureRequest
) -> None:
    con_dobles.cliente.get("/v1/salud")

    lineas = [linea for linea in con_dobles.lineas_log() if linea["logger"] == "matu.salud"]
    cae = request.node.callspec.params["con_dobles"]
    assert [linea["mensaje"] for linea in lineas] == [f"salud: {cae} no responde (ConnectionError)"]
    assert lineas[0]["nivel"] == "WARNING"
    assert lineas[0]["request_id"]
    _sin_detalle_interno(con_dobles.logs.getvalue())


# --- Las comprobaciones reales --------------------------------------------------------------------------------------


@pytest.mark.rf("MATU-79")
@requiere_base
def test_salud_real_alcanza_la_base_y_redis() -> None:
    with TestClient(crear_app(stream_logs=io.StringIO())) as cliente:
        respuesta = cliente.get("/v1/salud")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


@pytest.mark.rf("MATU-79")
def test_redis_que_no_escucha_responde_503_dentro_del_tiempo_limite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un Redis que no escucha (puerto 1 de la propia máquina) cae enseguida: 503 y sin colgarse. La base se
    reemplaza por un doble para que la prueba no dependa de ella."""
    from app.core import config

    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    config.obtener_configuracion.cache_clear()
    try:
        app = crear_app(stream_logs=io.StringIO())
        app.dependency_overrides[obtener_comprobaciones] = lambda: (
            ("base", lambda: None),
            ("redis", salud.comprobar_redis),
        )
        with TestClient(app, raise_server_exceptions=False) as cliente:
            inicio = time.monotonic()
            respuesta = cliente.get("/v1/salud")
            demora = time.monotonic() - inicio
    finally:
        config.obtener_configuracion.cache_clear()

    assert respuesta.status_code == 503
    assert respuesta.json()["detail"] == DETALLE_503
    assert "127.0.0.1" not in respuesta.text
    assert demora < TIEMPO_LIMITE_S + 2


@pytest.mark.rf("MATU-79")
def test_la_conexion_de_la_base_tiene_tiempo_limite_y_no_usa_el_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """La comprobación de la base usa la DATABASE_URL de la app (matu_app) con connect_timeout y statement_timeout,
    sin pool: una base caída no la deja colgada."""
    from sqlalchemy.pool import NullPool

    from app.core import config

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://matu_app:sintetica@127.0.0.1:1/matu_wt_salud")
    config.obtener_configuracion.cache_clear()
    salud._engine_salud.cache_clear()
    try:
        engine = salud._engine_salud()
        assert isinstance(engine.pool, NullPool)
        assert engine.url.username == "matu_app"
        inicio = time.monotonic()
        with pytest.raises(Exception) as error:
            salud.comprobar_base()
        demora = time.monotonic() - inicio
    finally:
        salud._engine_salud.cache_clear()
        config.obtener_configuracion.cache_clear()

    assert demora < TIEMPO_LIMITE_S + 2
    assert error.type.__name__ == "OperationalError"

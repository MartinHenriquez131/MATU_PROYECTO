"""MATU-80 · K2 del TESTER de Martín del 20-11: las conexiones de MATU abren su sesión con el JIT de PostgreSQL apagado.

Con 10 usuarios en k6, la vuelta de Webpay tardaba unos 22 s de mediana sin que se agotara el pool ni hubiera
bloqueos. La causa medida en matu_wt62: las políticas RLS de transaccion_pasarela se expanden en un plan de más de 200
subplanes, y con unas 300 ventas su costo estimado supera jit_above_cost. PostgreSQL compilaba entonces cada consulta
con LLVM, 2,5 a 7 s por consulta (lo que el plan llama «Emission»), contra 15 a 25 ms sin JIT.

Las primeras pruebas miran las opciones de cada motor sin conectarse. Las últimas abren una conexión de verdad, como
matu_app, con el motor de la API y con el de las tareas, y le preguntan a PostgreSQL. Sin el arreglo, SHOW jit
responde on, el valor por omisión del servidor.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import SecretStr
from sqlalchemy import text

from app import tareas
from app.core import db
from app.core.config import obtener_configuracion
from app.core.db import OPCIONES_SESION, argumentos_conexion, sesion_tenant
from tests.base_datos import requiere_base

pytestmark = [pytest.mark.rf("RNF-05")]

# Sin contraseña: detect-secrets no la confunde con un secreto, y crear el engine no conecta
URL_SINTETICA = "postgresql+psycopg://u@db.invalid/x"

# MATU-80 (RNF-05): además del JIT apagado, el plan genérico y las consultas preparadas desde la primera vez
ARGUMENTOS = {"options": "-c jit=off -c plan_cache_mode=force_generic_plan", "prepare_threshold": 0}


@pytest.fixture
def engine_de_la_api_sin_cache() -> Iterator[None]:
    db.obtener_engine.cache_clear()
    db.fabrica_sesiones.cache_clear()
    yield
    db.obtener_engine.cache_clear()
    db.fabrica_sesiones.cache_clear()


def test_las_opciones_de_la_sesion_apagan_el_jit() -> None:
    assert OPCIONES_SESION == "-c jit=off -c plan_cache_mode=force_generic_plan"
    assert argumentos_conexion() == ARGUMENTOS
    assert argumentos_conexion(7) == {**ARGUMENTOS, "connect_timeout": 7}


def test_el_engine_de_la_api_abre_las_conexiones_sin_jit(
    monkeypatch: pytest.MonkeyPatch, engine_de_la_api_sin_cache: None
) -> None:
    recibido: dict[str, Any] = {}

    def crear(url: str, **opciones: Any) -> None:
        recibido.update(opciones)

    config = obtener_configuracion().model_copy(update={"database_url": SecretStr(URL_SINTETICA)})
    monkeypatch.setattr(db, "obtener_configuracion", lambda: config)
    monkeypatch.setattr(db, "create_engine", crear)
    db.obtener_engine()
    assert recibido["connect_args"] == ARGUMENTOS


@requiere_base
def test_la_sesion_de_la_api_tiene_el_jit_apagado(engine_de_la_api_sin_cache: None) -> None:
    with sesion_tenant(db.fabrica_sesiones(), rol="sistema") as sesion:
        assert sesion.execute(text("SELECT current_user")).scalar_one() == "matu_app"
        assert sesion.execute(text("SHOW jit")).scalar_one() == "off"
        assert sesion.execute(text("SHOW plan_cache_mode")).scalar_one() == "force_generic_plan"
    db.obtener_engine().dispose()


@requiere_base
def test_la_sesion_de_las_tareas_tiene_el_jit_apagado() -> None:
    fabrica = tareas.fabrica_tareas(obtener_configuracion())
    try:
        with sesion_tenant(fabrica, rol="sistema") as sesion:
            assert sesion.execute(text("SELECT current_user")).scalar_one() == "matu_app"
            assert sesion.execute(text("SHOW jit")).scalar_one() == "off"
            assert sesion.execute(text("SHOW plan_cache_mode")).scalar_one() == "force_generic_plan"
            assert sesion.connection().connection.dbapi_connection.prepare_threshold == 0  # type: ignore[union-attr]
    finally:
        fabrica.kw["bind"].dispose()

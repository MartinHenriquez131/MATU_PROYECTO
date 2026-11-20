"""MATU-80 (RNF-05) · La vuelta de Webpay contra PostgreSQL: cuánto escribe y que sus planes se reutilizan sin cruzar
familias. Corre como matu_app, con RLS (migración 0024), con el engine de la API (app/core/db.py).

Las consultas de transaccion_pasarela se planifican con más de 200 subplanes por sus políticas RLS, unos 100 ms cada
una. La vuelta era lenta por planificarlas cada vez. Ahora:

- la vuelta aprobada escribe la venta dos veces, no tres (la marca del retorno va en el UPDATE de autorizando);
- cada conexión prepara la consulta la primera vez y usa su plan genérico desde ahí (PREPARAR_DESDE y
  plan_cache_mode en app/core/db.py);
- el mismo plan, en la misma conexión, con el contexto de otra familia, no ve la venta de la primera: las políticas
  van dentro del plan y leen el contexto al ejecutar.
"""

import uuid
from typing import Any

import psycopg
import pytest
from sqlalchemy import Engine, event, text

from app.core.db import obtener_fabrica_sesiones
from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa
from app.modules.payments.infrastructure.repositorio_pagos import _VENTA_ID
from tests.base_datos import DSN, requiere_base
from tests.modules.ordering.conftest import EntornoPedido
from tests.modules.payments.conftest import pagar, pedido_confirmado, sin_sesion_volver

pytestmark = [pytest.mark.rf("RNF-05"), requiere_base]

_CONTEXTO = text("SELECT set_config('app.grupo_id', :grupo, true), set_config('app.rol', 'sistema', true)")
_PREPARADA = text(
    "SELECT generic_plans, custom_plans FROM pg_prepared_statements WHERE statement LIKE :inicio || '%'"
    " AND statement LIKE '%t.id = $1'"
)


def _engine_de_la_api() -> Engine:
    """El engine de la fábrica que usa la API (obtener_fabrica_sesiones). No se pide a obtener_engine: otra prueba puede
    haber limpiado su caché sin la de fabrica_sesiones, y la API seguiría con el engine anterior."""
    engine = obtener_fabrica_sesiones().kw["bind"]
    assert isinstance(engine, Engine)
    return engine


def _venta_pagada(e: EntornoPedido, pasarela: PasarelaFalsa) -> tuple[uuid.UUID, uuid.UUID]:
    """Una familia con su pedido pagado. Devuelve el grupo y la venta."""
    familia, pedido = pedido_confirmado(e)
    token = pagar(e, familia, pedido).json()["token"]
    pasarela.pagar(token)
    assert sin_sesion_volver(e, {"token_ws": token}).json()["resultado"] == "aprobado"
    with psycopg.connect(DSN) as cx:
        fila = cx.execute("SELECT id FROM transaccion_pasarela WHERE token = %s", (token,)).fetchone()
    assert fila is not None
    return familia.grupo.id, fila[0]


def test_la_vuelta_aprobada_escribe_la_venta_dos_veces(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    familia, pedido = pedido_confirmado(e)
    token = pagar(e, familia, pedido).json()["token"]
    pasarela_falsa.pagar(token)
    escrituras: list[str] = []

    def anotar(_c: Any, _cur: Any, sentencia: str, *_: Any) -> None:
        if sentencia.startswith("UPDATE transaccion_pasarela"):
            escrituras.append(sentencia)

    engine = _engine_de_la_api()
    event.listen(engine, "before_cursor_execute", anotar)
    try:
        vuelta = sin_sesion_volver(e, {"token_ws": token})
    finally:
        event.remove(engine, "before_cursor_execute", anotar)

    assert vuelta.status_code == 200 and vuelta.json()["resultado"] == "aprobado", vuelta.text
    assert len(escrituras) == 2
    # La marca del retorno (decisión 245) quedó guardada igual
    with psycopg.connect(DSN) as cx:
        fila = cx.execute(
            "SELECT estado, retorno_recibido_en IS NOT NULL, commit_intentado_en IS NOT NULL FROM transaccion_pasarela"
            " WHERE token = %s",
            (token,),
        ).fetchone()
    assert fila == ("aprobada", True, True)


def test_el_plan_de_la_venta_se_reutiliza_y_no_cruza_familias(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa
) -> None:
    e = entorno_pedido
    grupo_a, venta_a = _venta_pagada(e, pasarela_falsa)
    grupo_b, venta_b = _venta_pagada(e, pasarela_falsa)

    # Una conexión nueva, tres transacciones: el plan que se prepara con la familia A sirve a la B
    engine = _engine_de_la_api()
    engine.dispose()
    with engine.connect() as conexion:
        with conexion.begin():
            conexion.execute(_CONTEXTO, {"grupo": str(grupo_a)})
            assert conexion.execute(_VENTA_ID, {"id": venta_a}).first() is not None
        with conexion.begin():
            conexion.execute(_CONTEXTO, {"grupo": str(grupo_b)})
            assert conexion.execute(_VENTA_ID, {"id": venta_a}).first() is None, "la familia B vio la venta de la A"
            assert conexion.execute(_VENTA_ID, {"id": venta_b}).first() is not None
        with conexion.begin():
            planes = conexion.execute(_PREPARADA, {"inicio": _VENTA_ID.text.split(" FROM ")[0]}).all()

    # Preparada desde la primera vez y con el plan genérico las tres: ningún plan a la medida
    assert planes == [(3, 0)]


def test_la_conexion_de_la_api_usa_el_plan_generico() -> None:
    with _engine_de_la_api().connect() as conexion:
        assert conexion.execute(text("SHOW plan_cache_mode")).scalar_one() == "force_generic_plan"
        assert conexion.connection.dbapi_connection.prepare_threshold == 0  # type: ignore[union-attr]

"""MATU-36 · Conservación del consumo contra PostgreSQL (decisión 70).

El consumo de una persona (activo o no) se borra 90 días después de que termina su autorización para
consumo. La tarea corre como matu_app con app.rol = 'operacion' y llama a consumo_conservar (0009).
El Reloj es un RelojFijo en el instante real: la función rechaza un ahora futuro.
"""

from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from sqlalchemy.exc import DBAPIError

from app.modules.consumption.application.conservacion import conservar
from app.modules.consumption.infrastructure.tarea_conservacion import ConservacionConsumoSql
from tests.base_datos import DSN, fabrica_scheduler, requiere_base
from tests.dobles.reloj_fijo import RelojFijo
from tests.fabricas import Fabrica

pytestmark = [requiere_base, pytest.mark.rf("RF-10")]


def _existe(perfil: object) -> bool:
    with psycopg.connect(DSN) as cx:
        return cx.execute("SELECT 1 FROM perfil_consumo WHERE id = %s", (perfil,)).fetchone() is not None


def test_borra_a_los_90_dias_de_terminar_la_autorizacion(fabrica: Fabrica) -> None:
    reloj = RelojFijo(datetime.now(UTC))
    ahora = reloj.ahora()

    vieja = fabrica.familia(miembros=())
    fabrica.autorizacion_consumo(
        vieja.persona, otorgante=vieja.admin, otorgado_en=ahora - timedelta(days=200),
        revocado_en=ahora - timedelta(days=91),
    )
    borrables = [fabrica.perfil_consumo(vieja.persona), fabrica.perfil_consumo(vieja.persona, activo=False)]

    reciente = fabrica.familia(miembros=())
    fabrica.autorizacion_consumo(
        reciente.persona, otorgante=reciente.admin, otorgado_en=ahora - timedelta(days=200),
        revocado_en=ahora - timedelta(days=89),
    )
    dentro_del_plazo = fabrica.perfil_consumo(reciente.persona)

    renovada = fabrica.familia(miembros=())
    fabrica.autorizacion_consumo(
        renovada.persona, otorgante=renovada.admin, otorgado_en=ahora - timedelta(days=300),
        revocado_en=ahora - timedelta(days=200),
    )
    fabrica.autorizacion_consumo(renovada.persona, otorgante=renovada.admin, otorgado_en=ahora - timedelta(days=100))
    con_autorizacion_vigente = fabrica.perfil_consumo(renovada.persona)

    resultado = conservar(unidad=ConservacionConsumoSql(fabrica_scheduler()), reloj=reloj)

    assert resultado.perfiles_borrados >= 2
    assert not any(_existe(p) for p in borrables)
    assert _existe(dentro_del_plazo)
    assert _existe(con_autorizacion_vigente)


def test_la_funcion_no_borra_antes_de_90_dias(fabrica: Fabrica) -> None:
    ahora = datetime.now(UTC)
    unidad = ConservacionConsumoSql(fabrica_scheduler())
    with pytest.raises(DBAPIError):
        unidad.conservar(ahora - timedelta(days=89), ahora)

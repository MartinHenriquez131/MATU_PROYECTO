"""MATU-44 · La ficha se destruye 90 días después del retiro (D3, decisiones 128 a 130), contra PostgreSQL.

El reloj de la API parte 91 días antes de la hora real: el retiro queda en el pasado y la tarea puede correr
con un «ahora» que no pasa de now() de la base, como exige plan_destruir_claves. Solo datos sintéticos.
"""

import logging
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from app.core.db import fabrica_sesiones
from app.modules.care_plan.api.dependencias import obtener_pepper_pin
from app.modules.care_plan.infrastructure.tarea_destruccion import ejecutar
from tests.base_datos import DSN, requiere_base
from tests.dobles.reloj_fijo import RelojFijo
from tests.fabricas import FamiliaCreada
from tests.modules.care_plan.conftest import EntornoFicha

pytestmark = [requiere_base, pytest.mark.rf("RF-02")]

RUTINA = "08:00 se levanta y toma desayuno en la cocina. Marca sintética de destrucción"
RUTA = "/v1/personas-cuidadas/{}/consentimientos"
INICIO = (datetime.now(UTC) - timedelta(days=91)).replace(microsecond=0)


@pytest.fixture
def reloj_fijo() -> RelojFijo:
    return RelojFijo(INICIO)


@pytest.fixture(autouse=True)
def pepper_pin(entorno_ficha: EntornoFicha) -> Iterator[None]:
    """Compartir exige PEPPER_PIN (sin él, 503). Un pepper sintético por prueba, como en MATU-19: no depende
    del .env de quien corre las pruebas ni del CI."""
    entorno_ficha.app.dependency_overrides[obtener_pepper_pin] = lambda: secrets.token_bytes(32)
    yield
    entorno_ficha.app.dependency_overrides.pop(obtener_pepper_pin, None)


def _una(sql: str, *parametros: Any) -> tuple[Any, ...] | None:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchone()


def _familia(entorno: EntornoFicha) -> FamiliaCreada:
    familia = entorno.familia()
    entorno.fabrica.ficha(familia.persona, actualizado_por=familia.admin.id, custodia=entorno.custodia,
                          textos={"rutina": RUTINA})
    return familia


def _post(entorno: EntornoFicha, familia: FamiliaCreada, sufijo: str = "", json: Any = None) -> Any:
    return entorno.iam.cliente.post(RUTA.format(familia.persona.id) + sufijo, json=json,
                                    headers=entorno._cabeceras(familia.admin, familia.grupo.id))


def _retirar(entorno: EntornoFicha, familia: FamiliaCreada) -> Any:
    return _post(entorno, familia, "/plan_cuidado/retiro")


def _autorizar(entorno: EntornoFicha, familia: FamiliaCreada) -> Any:
    return _post(entorno, familia, json={"finalidad": "plan_cuidado", "calidad_otorgante": "titular"})


def _avanzar(entorno: EntornoFicha, delta: timedelta) -> None:
    """El reloj de la API avanza y los access tokens de 15 minutos vencen: se vuelve a entrar."""
    entorno.iam.reloj.avanzar(delta)
    entorno.tokens.clear()


def _clave(familia: FamiliaCreada) -> tuple[Any, ...] | None:
    return _una("SELECT dek_cifrada_con_kek IS NULL, destruida_en FROM clave_datos WHERE persona_cuidada_id = %s",
                familia.persona.id)


def _destrucciones(familia: FamiliaCreada) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute("SELECT actor_tipo, actor_ref, entidad, detalle FROM auditoria"
                          " WHERE accion = 'clave.destruir' AND grupo_id = %s", (familia.grupo.id,)).fetchall()


def _tarea(instante: datetime) -> int:
    return ejecutar(fabrica_sesiones(), RelojFijo(instante)).claves_destruidas


def test_a_los_89_dias_no_y_a_los_90_si_y_es_idempotente(entorno_ficha: EntornoFicha) -> None:
    familia = _familia(entorno_ficha)
    assert _retirar(entorno_ficha, familia).status_code == 200

    _tarea(INICIO + timedelta(days=89))
    assert _clave(familia) == (False, None)

    _tarea(INICIO + timedelta(days=90))
    assert _clave(familia) == (True, INICIO + timedelta(days=90))
    _tarea(INICIO + timedelta(days=90, hours=1))
    assert _clave(familia) == (True, INICIO + timedelta(days=90))
    assert _destrucciones(familia) == [("sistema", None, "clave_datos", None)]
    # CL-6: no queda ninguna fila cifrada de la persona, ni sus metadatos
    assert _una("SELECT count(*) FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
                " WHERE p.persona_cuidada_id = %s", familia.persona.id) == (0,)
    assert _una("SELECT completitud_pct FROM plan_cuidado WHERE persona_cuidada_id = %s", familia.persona.id) == (0,)

    # La vista lo dice según el Reloj de la API: desde el día 90 está borrada
    _avanzar(entorno_ficha, timedelta(days=90))
    estado = entorno_ficha.iam.cliente.get(RUTA.format(familia.persona.id),
                                           headers=entorno_ficha._cabeceras(familia.admin, familia.grupo.id))
    plan = estado.json()["autorizaciones"][0]
    assert (plan["estado"], plan["borrada"]) == ("borrada", True)
    assert plan["borrado_en"].startswith((INICIO + timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S"))


def _claves(familia: FamiliaCreada) -> list[tuple[Any, ...]]:
    """(destruida, destruida_en) de cada clave de la persona, la más antigua primero."""
    with psycopg.connect(DSN) as cx:
        return cx.execute("SELECT dek_cifrada_con_kek IS NULL, destruida_en FROM clave_datos"
                          " WHERE persona_cuidada_id = %s ORDER BY creada_en", (familia.persona.id,)).fetchall()


def _ficha_en_blanco_que_se_escribe_y_se_comparte(entorno: EntornoFicha, familia: FamiliaCreada) -> None:
    """P8: 0 de 3, nada de lo anterior, se escribe con una clave nueva y se comparte."""
    ficha = entorno.leer(familia.admin, familia.grupo.id, familia.persona.id)
    assert ficha.status_code == 200, ficha.text
    cuerpo = ficha.json()
    assert cuerpo["completitud"] == 0 and RUTINA not in ficha.text
    assert all(c["texto"] is None for c in cuerpo["campos"].values()) and not cuerpo["secciones"]
    assert _una("SELECT count(*) FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
                " WHERE p.persona_cuidada_id = %s", familia.persona.id) == (0,)

    nuevo = "Desayuna a las 09:00. Texto nuevo sintético"
    escrita = entorno.escribir(familia.admin, familia.grupo.id, familia.persona.id, "rutina", {"texto": nuevo})
    assert escrita.status_code == 201, escrita.text
    claves = _claves(familia)
    assert [destruida for destruida, _ in claves] == [True, False]  # la destruida sigue destruida, y hay otra
    releida = entorno.leer(familia.admin, familia.grupo.id, familia.persona.id).json()
    assert releida["campos"]["rutina"]["texto"] == nuevo and releida["completitud"] == 33
    compartida = entorno.iam.cliente.post(
        f"/v1/personas-cuidadas/{familia.persona.id}/plan/accesos-relevo",
        headers=entorno._cabeceras(familia.admin, familia.grupo.id),
        json={"nombre_relevo": "Rosa", "telefono_relevo": "+56 9 5555 0137", "motivo": "otro",
              "relevo_informado": True},
    )
    assert compartida.status_code == 201, compartida.text


def test_tras_destruida_volver_a_autorizar_empieza_en_blanco(entorno_ficha: EntornoFicha) -> None:
    familia = _familia(entorno_ficha)
    assert _retirar(entorno_ficha, familia).status_code == 200
    _tarea(INICIO + timedelta(days=90))
    sin = entorno_ficha.leer(familia.admin, familia.grupo.id, familia.persona.id)
    assert sin.status_code == 403 and RUTINA not in sin.text
    _avanzar(entorno_ficha, timedelta(days=90, minutes=5))

    assert _autorizar(entorno_ficha, familia).status_code == 201

    _ficha_en_blanco_que_se_escribe_y_se_comparte(entorno_ficha, familia)
    cab = entorno_ficha._cabeceras(familia.admin, familia.grupo.id)
    plan = entorno_ficha.iam.cliente.get(RUTA.format(familia.persona.id), headers=cab).json()["autorizaciones"][0]
    assert (plan["estado"], plan["borrada"]) == ("vigente", True)


def test_la_clave_destruida_con_la_autorizacion_de_antes_sigue_en_404(entorno_ficha: EntornoFicha) -> None:
    """La regla de MATU-11 sigue igual sin una autorización nueva: destruida la clave, la ficha da 404 y no hay otra."""
    familia = _familia(entorno_ficha)
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = now()"
                   " WHERE persona_cuidada_id = %s", (familia.persona.id,))
    for respuesta in (
        entorno_ficha.leer(familia.admin, familia.grupo.id, familia.persona.id),
        entorno_ficha.escribir(familia.admin, familia.grupo.id, familia.persona.id, "red_apoyo", {"texto": "Hija"}),
    ):
        assert respuesta.status_code == 404 and RUTINA not in respuesta.text
    assert len(_claves(familia)) == 1


def test_una_autorizacion_antes_del_dia_90_lo_evita(entorno_ficha: EntornoFicha) -> None:
    familia = _familia(entorno_ficha)
    assert _retirar(entorno_ficha, familia).status_code == 200
    _avanzar(entorno_ficha, timedelta(days=89))
    assert _autorizar(entorno_ficha, familia).status_code == 201

    _tarea(INICIO + timedelta(days=90))

    assert _clave(familia) == (False, None)
    ficha = entorno_ficha.leer(familia.admin, familia.grupo.id, familia.persona.id)
    assert ficha.status_code == 200 and ficha.json()["campos"]["rutina"]["texto"] == RUTINA


def test_autorizar_despues_del_dia_90_destruye_aunque_la_tarea_no_haya_corrido(entorno_ficha: EntornoFicha) -> None:
    familia = _familia(entorno_ficha)
    assert _retirar(entorno_ficha, familia).status_code == 200
    _avanzar(entorno_ficha, timedelta(days=90, minutes=1))

    assert _autorizar(entorno_ficha, familia).status_code == 201

    assert _claves(familia) == [(True, INICIO + timedelta(days=90, minutes=1))]
    assert _destrucciones(familia) == [("sistema", None, "clave_datos", None)]
    _ficha_en_blanco_que_se_escribe_y_se_comparte(entorno_ficha, familia)


def test_otra_persona_no_se_destruye_y_el_log_lleva_solo_el_contador(
    entorno_ficha: EntornoFicha, caplog: pytest.LogCaptureFixture
) -> None:
    retirada, intacta = _familia(entorno_ficha), _familia(entorno_ficha)
    assert _retirar(entorno_ficha, retirada).status_code == 200
    with caplog.at_level(logging.INFO, logger="matu.care_plan.destruccion"):
        _tarea(INICIO + timedelta(days=90))
    assert _clave(intacta) == (False, None)
    # A la otra persona no se le borra nada: su sección sigue y se lee
    assert _una("SELECT count(*) FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
                " WHERE p.persona_cuidada_id = %s", intacta.persona.id) == (1,)
    leida = entorno_ficha.leer(intacta.admin, intacta.grupo.id, intacta.persona.id)
    assert leida.status_code == 200 and leida.json()["campos"]["rutina"]["texto"] == RUTINA
    mensajes = [r.getMessage() for r in caplog.records if r.name == "matu.care_plan.destruccion"]
    assert len(mensajes) == 1 and mensajes[0].startswith("destruccion de fichas retiradas: ")
    for texto in (mensajes[0], entorno_ficha.iam.texto_log()):
        assert RUTINA not in texto and str(retirada.persona.id) not in mensajes[0]
        assert retirada.persona.nombre not in texto

"""MATU-45 · Ver quién abrió la ficha, por la API y contra PostgreSQL (RF-08).

Usa el entorno de MATU-19 (test_abrir_relevo_api): la familia comparte por su ruta y el relevo
presenta, canjea y abre la ficha por las rutas públicas, que escriben la auditoría real. Después la
familia lista GET /plan/aperturas. El reloj avanza un segundo entre acciones para fijar el orden.
Solo datos sintéticos.
"""

import json
import logging
import uuid
from datetime import timedelta
from typing import Any

import pytest

from tests.base_datos import requiere_base
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.care_plan import test_abrir_relevo_api as abrir
from tests.modules.care_plan.test_abrir_relevo_api import PROBLEMA, EntornoAbrir

entorno = abrir.entorno
reloj_fijo = abrir.reloj_fijo

pytestmark = [requiere_base, pytest.mark.rf("RF-08")]

RUTA_APERTURAS = "/v1/personas-cuidadas/{}/plan/aperturas"
TELEFONO = "+56955550137"


def _aperturas(entorno: EntornoAbrir, usuario: UsuarioCreado | None, grupo: Any, persona: Any, **query: Any) -> Any:
    return entorno.ficha.iam.cliente.get(
        RUTA_APERTURAS.format(persona), params=query, headers=entorno.ficha._cabeceras(usuario, grupo)
    )


def _paso(entorno: EntornoAbrir) -> None:
    entorno.reloj.avanzar(timedelta(seconds=1))


def _malo(pin: str) -> str:
    return "0000" if pin != "0000" else "1111"


def _rosa_abre(entorno: EntornoAbrir, familia: FamiliaCreada) -> tuple[uuid.UUID, str, str]:
    """Rosa abre la página, se equivoca una vez de PIN y abre la ficha (el ejemplo del contrato)."""
    acceso_id, token, pin = entorno.compartir(familia)
    _paso(entorno)
    assert entorno.presentar(token).status_code == 200
    _paso(entorno)
    assert entorno.canjear(token, _malo(pin)).status_code == 401
    _paso(entorno)
    assert entorno.abrir(token, pin).status_code == 200
    return acceso_id, token, pin


def _lista(respuesta: Any) -> dict[str, Any]:
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["cache-control"] == "no-store"
    cuerpo: dict[str, Any] = respuesta.json()
    assert set(cuerpo) == {"items", "siguiente_cursor"}
    return cuerpo


def _tipos(respuesta: Any) -> list[str]:
    return [i["tipo"] for i in _lista(respuesta)["items"]]


# --- Camino feliz ----------------------------------------------------------------------------------------


def test_la_familia_ve_presentacion_pin_incorrecto_y_apertura(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = _rosa_abre(entorno, familia)

    cuerpo = _lista(_aperturas(entorno, familia.admin, familia.grupo.id, familia.persona.id))
    assert [i["tipo"] for i in cuerpo["items"]] == ["apertura", "pin_incorrecto", "presentacion"]
    assert cuerpo["siguiente_cursor"] is None
    for item in cuerpo["items"]:
        assert set(item) == {"ocurrido_en", "tipo", "acceso"}
        assert item["acceso"] == {"id": str(acceso_id), "nombre_relevo": "Rosa"}
    instantes = [i["ocurrido_en"] for i in cuerpo["items"]]
    assert instantes == sorted(instantes, reverse=True) and len(set(instantes)) == 3
    # Nunca el teléfono, el token, la IP ni el request_id
    texto = json.dumps(cuerpo)
    for prohibido in (TELEFONO, "5555 0137", token, "request_id", '"ip"'):
        assert prohibido not in texto


def test_el_canje_y_lo_de_la_familia_no_se_listan(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    acceso_id, token, pin = entorno.compartir(familia)
    assert entorno.canjear(token, pin).status_code == 204  # relevo.canje, sin abrir la ficha
    # relevo.compartir y relevo.revocar son de la familia; plan.leer, de un miembro
    assert entorno.ficha.leer(familia.admin, familia.grupo.id, familia.persona.id).status_code == 200
    revocado = entorno.ficha.iam.cliente.delete(
        f"/v1/accesos-relevo/{acceso_id}", headers=entorno.ficha._cabeceras(familia.admin, familia.grupo.id)
    )
    assert revocado.status_code == 204
    assert _tipos(_aperturas(entorno, familia.admin, familia.grupo.id, familia.persona.id)) == []


def test_cinco_pin_incorrectos_muestran_el_bloqueo(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    _, token, pin = entorno.compartir(familia)
    for _ in range(5):
        _paso(entorno)
        entorno.canjear(token, _malo(pin))
    tipos = _tipos(_aperturas(entorno, familia.admin, familia.grupo.id, familia.persona.id))
    assert tipos.count("pin_incorrecto") == 5 and tipos.count("bloqueo") == 1
    assert len(tipos) == 6


def test_sin_plan_lista_vacia_y_no_crea_el_plan(entorno: EntornoAbrir) -> None:
    familia = entorno.ficha.familia()
    assert _tipos(_aperturas(entorno, familia.admin, familia.grupo.id, familia.persona.id)) == []
    assert abrir._una("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", familia.persona.id) == (0,)


def test_pagina_con_cursor(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    _rosa_abre(entorno, familia)

    primera = _lista(_aperturas(entorno, familia.admin, familia.grupo.id, familia.persona.id, limite=2))
    assert [i["tipo"] for i in primera["items"]] == ["apertura", "pin_incorrecto"]
    assert primera["siguiente_cursor"]
    segunda = _lista(_aperturas(
        entorno, familia.admin, familia.grupo.id, familia.persona.id, limite=2, cursor=primera["siguiente_cursor"]
    ))
    assert [i["tipo"] for i in segunda["items"]] == ["presentacion"]
    assert segunda["siguiente_cursor"] is None


def test_mismo_instante_no_repite_ni_pierde_filas(entorno: EntornoAbrir) -> None:
    """Sin avanzar el reloj, las filas empatan en ocurrido_en: el cursor desempata por id."""
    familia = entorno.familia_con_ficha()
    _, token, _ = entorno.compartir(familia)
    for _ in range(3):
        assert entorno.presentar(token).status_code == 200
    vistos: list[dict[str, Any]] = []
    query: dict[str, Any] = {"limite": 1}
    for _ in range(5):
        pagina = _lista(_aperturas(entorno, familia.admin, familia.grupo.id, familia.persona.id, **query))
        vistos += pagina["items"]
        if pagina["siguiente_cursor"] is None:
            break
        query = {"limite": 1, "cursor": pagina["siguiente_cursor"]}
    assert [i["tipo"] for i in vistos] == ["presentacion"] * 3


# --- Roles y aislamiento ---------------------------------------------------------------------------------


@pytest.mark.parametrize("etiqueta", ["cuidador", "pagador_con_plan"])
def test_cuidador_y_pagador_con_plan_tambien_ven(entorno: EntornoAbrir, etiqueta: str) -> None:
    familia = entorno.familia_con_ficha()
    _rosa_abre(entorno, familia)
    usuario = familia.miembros[etiqueta].usuario
    tipos = _tipos(_aperturas(entorno, usuario, familia.grupo.id, familia.persona.id))
    assert tipos == ["apertura", "pin_incorrecto", "presentacion"]


@pytest.mark.parametrize("etiqueta", ["pagador", "observador"])
def test_otros_roles_404(entorno: EntornoAbrir, etiqueta: str) -> None:
    familia = entorno.familia_con_ficha()
    _rosa_abre(entorno, familia)
    respuesta = _aperturas(entorno, familia.miembros[etiqueta].usuario, familia.grupo.id, familia.persona.id)
    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"] == PROBLEMA
    assert respuesta.json()["type"] == "/errores/no-encontrado"


def test_otro_grupo_no_ve_las_aperturas_404(entorno: EntornoAbrir) -> None:
    a, b = entorno.familia_con_ficha(), entorno.familia_con_ficha()
    _rosa_abre(entorno, b)
    for respuesta in (
        _aperturas(entorno, a.admin, a.grupo.id, b.persona.id),
        _aperturas(entorno, a.admin, b.grupo.id, b.persona.id),
        _aperturas(entorno, a.admin, a.grupo.id, "no-es-uuid"),
        _aperturas(entorno, a.admin, None, b.persona.id),
    ):
        assert respuesta.status_code == 404, respuesta.text
        assert respuesta.headers["content-type"] == PROBLEMA
    # Y su propia lista no trae nada de la otra familia
    assert _tipos(_aperturas(entorno, a.admin, a.grupo.id, a.persona.id)) == []


def test_sin_token_401(entorno: EntornoAbrir) -> None:
    familia = entorno.familia_con_ficha()
    respuesta = _aperturas(entorno, None, familia.grupo.id, familia.persona.id)
    assert respuesta.status_code == 401
    assert respuesta.headers["content-type"] == PROBLEMA


# --- Camino de error de la consulta ----------------------------------------------------------------------


@pytest.mark.parametrize("query", [
    {"cursor": "no-es-un-cursor"}, {"cursor": "x" * 201}, {"limite": 0}, {"limite": 101}, {"limite": "diez"},
])
def test_consulta_invalida_422(entorno: EntornoAbrir, query: dict[str, Any]) -> None:
    familia = entorno.familia_con_ficha()
    respuesta = _aperturas(entorno, familia.admin, familia.grupo.id, familia.persona.id, **query)
    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == PROBLEMA
    assert respuesta.json()["errores"]


def test_los_logs_no_llevan_nombre_telefono_ni_token(
    entorno: EntornoAbrir, caplog: pytest.LogCaptureFixture
) -> None:
    familia = entorno.familia_con_ficha()
    _, token, _ = _rosa_abre(entorno, familia)
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        _lista(_aperturas(entorno, familia.admin, familia.grupo.id, familia.persona.id))
    registros = " ".join(r.getMessage() + json.dumps(vars(r), default=str) for r in caplog.records)
    for prohibido in (TELEFONO, token, "Rosa"):
        assert prohibido not in registros

"""MATU-50 · Compartir secciones complementarias con un relevo, por la API y contra PostgreSQL (ADR-028, RF-03).

POST …/plan/accesos-relevo con ``secciones_adicionales`` (``campos`` deprecado), GET /v1/relevo/ficha con
``secciones`` y GET …/plan/aperturas con los tipos mostrados. Usa el entorno de MATU-19
(test_abrir_relevo_api): reloj desde la hora real, porque las políticas RLS del relevo usan now().

Las secciones se agregan por la API (su creado_en sale del mismo Reloj que el del acceso). Solo datos
sintéticos.
"""

import json
import secrets
import uuid
from datetime import timedelta
from typing import Any

import psycopg
import pytest

from app.modules.care_plan.api.dependencias import obtener_auditoria_ficha
from tests.base_datos import DSN, requiere_base
from tests.fabricas import FamiliaCreada
from tests.modules.care_plan import test_abrir_relevo_api as abrir
from tests.modules.care_plan.test_abrir_relevo_api import RUTA_ACCESOS, EntornoAbrir
from tests.modules.care_plan.test_secciones_api import _delete, _put

entorno = abrir.entorno
reloj_fijo = abrir.reloj_fijo

pytestmark = [requiere_base, pytest.mark.rf("RF-03")]

BASE = ["rutina", "manejo_situaciones", "red_apoyo"]


def _marca(nombre: str) -> str:
    return f"{nombre} sintético {secrets.token_hex(5)}"


def _agregar(entorno: EntornoAbrir, familia: FamiliaCreada, seccion: str, texto: str) -> None:
    respuesta = _put(entorno.ficha, familia.admin, familia.grupo.id, familia.persona.id, seccion, {"texto": texto},
                     If_None_Match="*")
    assert respuesta.status_code == 201, respuesta.text


def _crear(entorno: EntornoAbrir, familia: FamiliaCreada, **cambios: Any) -> Any:
    cuerpo: dict[str, Any] = {
        "nombre_relevo": "Rosa", "telefono_relevo": "+56 9 5555 0137", "motivo": "fin_de_semana_fuera",
        "relevo_informado": True,
    }
    cuerpo.update(cambios)
    return entorno.ficha.iam.cliente.post(
        RUTA_ACCESOS.format(familia.persona.id), json=cuerpo,
        headers=entorno.ficha._cabeceras(familia.admin, familia.grupo.id),
    )


def _permitidas(acceso_id: uuid.UUID | str) -> list[str]:
    with psycopg.connect(DSN) as cx:
        fila = cx.execute("SELECT secciones_permitidas FROM acceso_relevo WHERE id = %s", (str(acceso_id),)).fetchone()
    assert fila is not None
    return list(fila[0])


def _accesos(entorno: EntornoAbrir, familia: FamiliaCreada) -> int:
    with psycopg.connect(DSN) as cx:
        fila = cx.execute("SELECT count(*) FROM acceso_relevo WHERE grupo_id = %s", (familia.grupo.id,)).fetchone()
    assert fila is not None
    return int(fila[0])


def _familia_con_secciones(entorno: EntornoAbrir) -> tuple[FamiliaCreada, dict[str, str]]:
    familia = entorno.familia_con_ficha()
    textos = {s: _marca(s) for s in ("quien_es", "comunicacion", "remedios")}
    for seccion, texto in textos.items():
        _agregar(entorno, familia, seccion, texto)
    return familia, textos


# --- Compartir ------------------------------------------------------------------------------------------


def test_sin_secciones_adicionales_van_solo_los_tres_campos_y_remedios_no(entorno: EntornoAbrir) -> None:
    familia, textos = _familia_con_secciones(entorno)

    creado = _crear(entorno, familia)
    assert creado.status_code == 201, creado.text
    assert creado.json()["campos"] == BASE and creado.json()["secciones_adicionales"] == []
    assert _permitidas(creado.json()["id"]) == BASE

    _, token, pin = entorno.compartir(familia, campos_anteriores=None)
    ficha = entorno.abrir(token, pin)
    assert ficha.status_code == 200, ficha.text
    cuerpo = ficha.json()
    assert set(cuerpo["campos"]) == set(BASE)  # los tres, aunque manejo_situaciones esté vacío
    assert cuerpo["campos"]["manejo_situaciones"] == {"texto": None}
    assert cuerpo["secciones"] == []
    for texto in textos.values():
        assert texto not in ficha.text


def test_el_relevo_ve_solo_las_secciones_compartidas_en_orden(entorno: EntornoAbrir) -> None:
    familia, textos = _familia_con_secciones(entorno)
    entorno.ficha.app.dependency_overrides.pop(obtener_auditoria_ficha, None)

    acceso_id, token, pin = entorno.compartir(
        familia, campos_anteriores=None, secciones_adicionales=["remedios", "comunicacion"]
    )
    assert _permitidas(acceso_id) == [*BASE, "comunicacion", "remedios"]

    ficha = entorno.abrir(token, pin)
    assert ficha.status_code == 200, ficha.text
    assert ficha.json()["secciones"] == [
        {"tipo": "comunicacion", "texto": textos["comunicacion"]},
        {"tipo": "remedios", "texto": textos["remedios"]},
    ]
    assert textos["quien_es"] not in ficha.text

    # relevo.abrir guarda los tipos mostrados, sin texto
    with psycopg.connect(DSN) as cx:
        [(detalle,)] = cx.execute(
            "SELECT detalle FROM auditoria WHERE actor_ref = %s AND accion = 'relevo.abrir'", (acceso_id,)
        ).fetchall()
    assert detalle == {"secciones": ["comunicacion", "remedios"]}

    # La familia ve en las aperturas qué secciones se mostraron
    aperturas = entorno.ficha.iam.cliente.get(
        f"/v1/personas-cuidadas/{familia.persona.id}/plan/aperturas",
        headers=entorno.ficha._cabeceras(familia.admin, familia.grupo.id),
    )
    assert aperturas.status_code == 200, aperturas.text
    items = aperturas.json()["items"]
    assert [(i["tipo"], i.get("secciones")) for i in items] == [("apertura", ["comunicacion", "remedios"])]
    texto_aperturas = json.dumps(aperturas.json())
    for texto in textos.values():
        assert texto not in texto_aperturas

    # Y la lista de accesos devuelve los campos y las secciones compartidas
    lista = entorno.ficha.iam.cliente.get(
        RUTA_ACCESOS.format(familia.persona.id), headers=entorno.ficha._cabeceras(familia.admin, familia.grupo.id)
    )
    [item] = lista.json()["items"]
    assert (item["campos"], item["secciones_adicionales"]) == (BASE, ["comunicacion", "remedios"])


def test_campos_deprecado_con_los_tres_se_acepta_y_se_ignora(entorno: EntornoAbrir) -> None:
    familia, _ = _familia_con_secciones(entorno)
    creado = _crear(entorno, familia, campos=["red_apoyo", "rutina", "manejo_situaciones"],
                    secciones_adicionales=["quien_es"])
    assert creado.status_code == 201, creado.text
    assert creado.json()["campos"] == BASE and creado.json()["secciones_adicionales"] == ["quien_es"]


@pytest.mark.parametrize(
    ("cambios", "campo", "tipo"),
    [
        ({"campos": ["rutina", "red_apoyo"]}, "campos", "campos_base_obligatorios"),
        ({"campos": ["rutina"]}, "campos", "campos_base_obligatorios"),
        ({"campos": []}, "campos", "campos_base_obligatorios"),
        ({"campos": None}, "campos", "campos_base_obligatorios"),
        ({"campos": ["rutina", "rutina", "red_apoyo"]}, "campos", "campos_base_obligatorios"),
        ({"secciones_adicionales": ["remedios", "remedios"]}, "secciones_adicionales", "duplicado"),
        ({"secciones_adicionales": ["rutina"]}, "secciones_adicionales.0", "enum"),
        ({"secciones_adicionales": ["preferencias"]}, "secciones_adicionales", "seccion_no_agregada"),
    ],
)
def test_422_al_compartir(
    entorno: EntornoAbrir, cambios: dict[str, Any], campo: str, tipo: str
) -> None:
    familia, _ = _familia_con_secciones(entorno)
    respuesta = _crear(entorno, familia, **cambios)
    assert respuesta.status_code == 422, respuesta.text
    errores = respuesta.json()["errores"]
    assert (campo, tipo) in [(e["campo"], e["tipo"]) for e in errores], errores
    assert _accesos(entorno, familia) == 0


def test_422_si_no_hay_plan_y_se_pide_una_seccion(entorno: EntornoAbrir) -> None:
    familia = entorno.ficha.familia()
    respuesta = _crear(entorno, familia, secciones_adicionales=["remedios"])
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"][0]["tipo"] == "seccion_no_agregada"
    with psycopg.connect(DSN) as cx:
        fila = cx.execute("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s",
                          (familia.persona.id,)).fetchone()
    assert fila == (0,)


# --- Después de compartir --------------------------------------------------------------------------------


def test_editar_una_seccion_compartida_si_se_ve(entorno: EntornoAbrir) -> None:
    familia, _ = _familia_con_secciones(entorno)
    _, token, pin = entorno.compartir(familia, campos_anteriores=None, secciones_adicionales=["comunicacion"])
    entorno.reloj.avanzar(timedelta(minutes=1))
    nuevo = _marca("comunicacion editada")
    editada = _put(entorno.ficha, familia.admin, familia.grupo.id, familia.persona.id, "comunicacion",
                   {"texto": nuevo}, If_Match='"v1"')
    assert editada.status_code == 200, editada.text
    assert entorno.abrir(token, pin).json()["secciones"] == [{"tipo": "comunicacion", "texto": nuevo}]


def test_quitada_no_se_ve_y_vuelta_a_agregar_tampoco(entorno: EntornoAbrir) -> None:
    """Decisión de Jorge del 03-11: un acceso no ve secciones agregadas después de crearlo."""
    familia, textos = _familia_con_secciones(entorno)
    _, token, pin = entorno.compartir(
        familia, campos_anteriores=None, secciones_adicionales=["comunicacion", "remedios"]
    )
    assert entorno.canjear(token, pin).status_code == 204

    # Se quita remedios: el relevo deja de verla
    assert _delete(entorno.ficha, familia.admin, familia.grupo.id, familia.persona.id, "remedios",
                   If_Match='"v1"').status_code == 204
    ficha = entorno.leer()
    assert [s["tipo"] for s in ficha.json()["secciones"]] == ["comunicacion"]
    assert textos["remedios"] not in ficha.text

    # Se vuelve a agregar más tarde: es otra fila, posterior al acceso, y el relevo no la ve
    entorno.reloj.avanzar(timedelta(minutes=1))
    otra = _marca("remedios de nuevo")
    _agregar(entorno, familia, "remedios", otra)
    ficha = entorno.leer()
    assert ficha.status_code == 200
    assert [s["tipo"] for s in ficha.json()["secciones"]] == ["comunicacion"]
    assert otra not in ficha.text

    # Un acceso nuevo sí la ve
    _, token2, pin2 = entorno.compartir(familia, campos_anteriores=None, secciones_adicionales=["remedios"])
    assert entorno.abrir(token2, pin2).json()["secciones"] == [{"tipo": "remedios", "texto": otra}]


def test_un_acceso_anterior_a_matu_50_no_ve_secciones(entorno: EntornoAbrir) -> None:
    familia, textos = _familia_con_secciones(entorno)
    acceso_id, token, pin = entorno.compartir(familia)  # como antes de MATU-50: rutina y manejo_situaciones
    ficha = entorno.abrir(token, pin)
    assert ficha.json()["secciones"] == []
    assert set(ficha.json()["campos"]) == {"rutina", "manejo_situaciones"}
    lista = entorno.ficha.iam.cliente.get(
        RUTA_ACCESOS.format(familia.persona.id), headers=entorno.ficha._cabeceras(familia.admin, familia.grupo.id)
    )
    [item] = [i for i in lista.json()["items"] if i["id"] == str(acceso_id)]
    assert (item["campos"], item["secciones_adicionales"]) == (["rutina", "manejo_situaciones"], [])
    for texto in textos.values():
        assert texto not in ficha.text

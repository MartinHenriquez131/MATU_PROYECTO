"""MATU-50 · Las seis secciones complementarias de la ficha por la API, contra PostgreSQL (ADR-028, RF-03).

PUT y DELETE …/plan/secciones/{seccion} y la propiedad ``secciones`` de GET …/plan/ficha. Contrato:
docs/api/propuestos/ficha-ampliada.openapi.yaml. Mismo entorno que la ficha (conftest de care_plan):
CustodiaEnMemoria, RelojFijo y el espía de la auditoría, que las pruebas de RF-08 quitan para usar la real.

Solo datos sintéticos.
"""

import logging
import secrets
import uuid
from datetime import timedelta
from typing import Any

import psycopg
import pytest

from app.modules.care_plan.api.dependencias import obtener_auditoria_ficha, obtener_custodia
from tests.base_datos import DSN, requiere_base
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.care_plan.conftest import EntornoFicha

pytestmark = [requiere_base, pytest.mark.rf("RF-03")]

PROBLEMA = "application/problem+json"
RUTA = "/v1/personas-cuidadas/{}/plan/secciones/{}"
SECCIONES = ("quien_es", "preferencias", "alimentacion", "movilidad", "comunicacion", "remedios")
CLAVES_ESTADO = {"texto", "etag", "actualizado_por", "actualizado_en"}


def _texto(seccion: str) -> str:
    # Una marca única por prueba, para buscarla en la base y en los logs
    return f"Texto sintético de {seccion} {secrets.token_hex(6)}"


def _put(
    entorno: EntornoFicha, usuario: UsuarioCreado | None, grupo: Any, persona: Any, seccion: str, cuerpo: Any,
    **cabeceras: str,
) -> Any:
    encabezados = entorno._cabeceras(usuario, grupo)
    encabezados.update({k.replace("_", "-"): v for k, v in cabeceras.items()})
    return entorno.iam.cliente.put(RUTA.format(persona, seccion), json=cuerpo, headers=encabezados)


def _delete(
    entorno: EntornoFicha, usuario: UsuarioCreado | None, grupo: Any, persona: Any, seccion: str, **cabeceras: str
) -> Any:
    encabezados = entorno._cabeceras(usuario, grupo)
    encabezados.update({k.replace("_", "-"): v for k, v in cabeceras.items()})
    return entorno.iam.cliente.delete(RUTA.format(persona, seccion), headers=encabezados)


def _agregar(entorno: EntornoFicha, familia: FamiliaCreada, seccion: str, texto: str) -> Any:
    respuesta = _put(
        entorno, familia.admin, familia.grupo.id, familia.persona.id, seccion, {"texto": texto}, If_None_Match="*"
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta


def _problema(respuesta: Any, status: int, tipo: str) -> dict[str, Any]:
    assert respuesta.status_code == status, respuesta.text
    assert respuesta.headers["content-type"] == PROBLEMA
    assert respuesta.headers["cache-control"] == "no-store"
    cuerpo: dict[str, Any] = respuesta.json()
    assert cuerpo["type"] == f"/errores/{tipo}"
    return cuerpo


def _filas(sql: str, *parametros: Any) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchall()


def _seccion_en_base(persona: uuid.UUID, tipo: str) -> tuple[Any, ...] | None:
    filas = _filas(
        "SELECT s.id, s.version, s.contenido_cifrado, s.creado_en, s.actualizado_en FROM plan_seccion s"
        " JOIN plan_cuidado p ON p.id = s.plan_id WHERE p.persona_cuidada_id = %s AND s.tipo = %s",
        persona, tipo,
    )
    return filas[0] if filas else None


# --- Camino feliz: agregar, leer, editar y quitar ---------------------------------------------------------


def test_agregar_leer_editar_y_quitar_una_seccion(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    cuidador = familia.miembros["cuidador"].usuario
    texto = _texto("comunicacion")

    # Una ficha sin nada: secciones vacío, sin plan ni clave
    vacia = entorno_ficha.leer(familia.admin, grupo, persona)
    assert vacia.status_code == 200 and vacia.json()["secciones"] == {}

    # Agregar con If-None-Match: * responde 201 con ETag, crea el plan y la clave
    agregada = _put(entorno_ficha, cuidador, grupo, persona, "comunicacion", {"texto": f"  {texto}\r\n"},
                    If_None_Match="*")
    assert agregada.status_code == 201, agregada.text
    assert agregada.headers["etag"] == '"v1"'
    assert agregada.headers["cache-control"] == "no-store"
    assert agregada.json() == {
        "seccion": "comunicacion",
        "texto": texto,
        "etag": '"v1"',
        "actualizado_por": {"id": str(cuidador.id), "nombre": cuidador.nombre},
        "actualizado_en": "2026-10-20T12:00:00Z",
    }

    # En la base: cifrada, nunca en claro
    fila = _seccion_en_base(persona, "comunicacion")
    assert fila is not None and fila[1] == 1
    assert texto.encode() not in bytes(fila[2]) and texto.split()[-1].encode() not in bytes(fila[2])

    # La ficha trae solo la sección agregada, y la completitud sigue contando solo los tres campos
    leida = entorno_ficha.leer(familia.admin, grupo, persona).json()
    assert set(leida["secciones"]) == {"comunicacion"}
    assert set(leida["secciones"]["comunicacion"]) == CLAVES_ESTADO
    assert leida["secciones"]["comunicacion"]["texto"] == texto
    assert leida["secciones"]["comunicacion"]["etag"] == '"v1"'
    assert leida["completitud"] == 0 and leida["actualizado_en"] is None

    # Editar con If-Match responde 200 y sube la versión; creado_en no cambia
    otro = _texto("comunicacion")
    editada = _put(entorno_ficha, familia.admin, grupo, persona, "comunicacion", {"texto": otro}, If_Match='"v1"')
    assert editada.status_code == 200, editada.text
    assert editada.headers["etag"] == '"v2"' and editada.json()["texto"] == otro
    despues = _seccion_en_base(persona, "comunicacion")
    assert despues is not None and despues[1] == 2 and despues[3] == fila[3]

    # Quitar con If-Match borra la fila: 204 sin cuerpo
    quitada = _delete(entorno_ficha, cuidador, grupo, persona, "comunicacion", If_Match='"v2"')
    assert quitada.status_code == 204, quitada.text
    assert quitada.content == b""
    assert quitada.headers["cache-control"] == "no-store"
    assert _seccion_en_base(persona, "comunicacion") is None
    assert entorno_ficha.leer(familia.admin, grupo, persona).json()["secciones"] == {}

    # La auditoría (espía) vio dos ediciones y una quita, con el tipo, sin texto
    assert [e.campo for e in entorno_ficha.auditoria.ediciones_seccion] == ["comunicacion", "comunicacion"]
    [(evento, seccion_id)] = entorno_ficha.auditoria.quitadas
    assert evento.campo == "comunicacion" and seccion_id == fila[0]
    assert entorno_ficha.auditoria.ediciones == []  # ningún campo base


def test_las_seis_secciones_y_sus_maximos(entorno_ficha: EntornoFicha) -> None:
    """Ida y vuelta por la API de cada una de las seis, con su máximo: el texto leído es el guardado."""
    familia = entorno_ficha.familia()
    textos: dict[str, str] = {}
    for seccion in SECCIONES:
        maximo = 800 if seccion == "remedios" else 500
        marca = f"{seccion} {secrets.token_hex(4)}\nÑandú y café "
        textos[seccion] = (marca + "a" * maximo)[:maximo]
        agregada = _agregar(entorno_ficha, familia, seccion, textos[seccion])
        assert agregada.json()["texto"] == textos[seccion]
    leida = entorno_ficha.leer(familia.admin, familia.grupo.id, familia.persona.id).json()
    assert list(leida["secciones"]) == list(SECCIONES)  # en el orden de ADR-028
    assert {s: e["texto"] for s, e in leida["secciones"].items()} == textos
    assert leida["completitud"] == 0
    # Cada una quedó cifrada con su propio AAD: ninguna fila tiene su texto en claro
    for seccion, texto in textos.items():
        fila = _seccion_en_base(familia.persona.id, seccion)
        assert fila is not None and texto.split("\n")[0].encode() not in bytes(fila[2])


def test_la_seccion_convive_con_los_campos_base(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    rutina = entorno_ficha.escribir(familia.admin, grupo, persona, "rutina", {"texto": "08:00 desayuno"})
    assert rutina.status_code == 201
    _agregar(entorno_ficha, familia, "quien_es", _texto("quien_es"))
    leida = entorno_ficha.leer(familia.admin, grupo, persona).json()
    assert leida["completitud"] == 33
    assert set(leida["campos"]) == {"rutina", "manejo_situaciones", "red_apoyo"}
    assert set(leida["secciones"]) == {"quien_es"}
    # Quitar la sección no toca el campo base
    assert _delete(entorno_ficha, familia.admin, grupo, persona, "quien_es", If_Match='"v1"').status_code == 204
    assert entorno_ficha.leer(familia.admin, grupo, persona).json()["campos"]["rutina"]["texto"] == "08:00 desayuno"


def test_el_pagador_con_plan_lee_las_secciones(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    texto = _texto("preferencias")
    _agregar(entorno_ficha, familia, "preferencias", texto)
    pagador = familia.miembros["pagador_con_plan"].usuario
    leida = entorno_ficha.leer(pagador, familia.grupo.id, familia.persona.id)
    assert leida.status_code == 200 and leida.json()["secciones"]["preferencias"]["texto"] == texto
    # Pero no escribe ni quita: 404
    no = _put(entorno_ficha, pagador, familia.grupo.id, familia.persona.id, "quien_es", {"texto": "x"},
              If_None_Match="*")
    _problema(no, 404, "no-encontrado")
    _problema(_delete(entorno_ficha, pagador, familia.grupo.id, familia.persona.id, "preferencias", If_Match='"v1"'),
              404, "no-encontrado")


# --- 412: otra persona se adelantó ---------------------------------------------------------------------


def test_412_con_if_match_desactualizado_trae_la_seccion_actual(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    _agregar(entorno_ficha, familia, "alimentacion", "Primera")
    cuidador = familia.miembros["cuidador"].usuario
    assert _put(entorno_ficha, cuidador, grupo, persona, "alimentacion", {"texto": "De Pedro"},
                If_Match='"v1"').status_code == 200

    tarde = _put(entorno_ficha, familia.admin, grupo, persona, "alimentacion", {"texto": "Mía"}, If_Match='"v1"')
    cuerpo = _problema(tarde, 412, "version-desactualizada")
    assert cuerpo["title"] == "Otra persona cambió esta sección"
    assert cuerpo["actual"]["texto"] == "De Pedro" and cuerpo["actual"]["etag"] == '"v2"'
    assert cuerpo["actual"]["actualizado_por"]["id"] == str(cuidador.id)
    assert tarde.headers["etag"] == '"v2"'
    # Nada se escribió, y la lectura de actual quedó auditada como plan.leer
    fila = _seccion_en_base(persona, "alimentacion")
    assert fila is not None and fila[1] == 2
    assert len(entorno_ficha.auditoria.lecturas) == 1


def test_412_al_agregar_una_seccion_que_ya_esta(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    _agregar(entorno_ficha, familia, "movilidad", "Usa bastón")
    otra = _put(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, "movilidad", {"texto": "Otra"},
                If_None_Match="*")
    assert _problema(otra, 412, "version-desactualizada")["actual"]["texto"] == "Usa bastón"


@pytest.mark.parametrize("con_plan", [False, True])
def test_412_con_if_match_sobre_una_seccion_que_no_esta(entorno_ficha: EntornoFicha, con_plan: bool) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    if con_plan:
        _agregar(entorno_ficha, familia, "quien_es", "Le dicen Tere")
    respuesta = _put(entorno_ficha, familia.admin, grupo, persona, "remedios", {"texto": "x"}, If_Match='"v1"')
    cuerpo = _problema(respuesta, 412, "version-desactualizada")
    assert cuerpo["actual"] is None
    assert "etag" not in respuesta.headers
    # Sin plan, no lo crea ni crea la clave
    planes = _filas("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", persona)
    assert planes == [(1 if con_plan else 0,)]


def test_412_al_quitar_una_seccion_ya_quitada_o_desactualizada(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    _agregar(entorno_ficha, familia, "remedios", "Desayuno: 1 pastilla blanca")
    assert _put(entorno_ficha, familia.admin, grupo, persona, "remedios", {"texto": "Noche: 1 pastilla rosada"},
                If_Match='"v1"').status_code == 200

    # ETag viejo: 412 con el contenido actual y no se borra
    viejo = _delete(entorno_ficha, familia.admin, grupo, persona, "remedios", If_Match='"v1"')
    assert _problema(viejo, 412, "version-desactualizada")["actual"]["texto"] == "Noche: 1 pastilla rosada"
    assert _seccion_en_base(persona, "remedios") is not None

    # Se quita, y quitarla otra vez es 412 con actual null, no 404
    assert _delete(entorno_ficha, familia.admin, grupo, persona, "remedios", If_Match='"v2"').status_code == 204
    otra_vez = _delete(entorno_ficha, familia.admin, grupo, persona, "remedios", If_Match='"v2"')
    assert _problema(otra_vez, 412, "version-desactualizada")["actual"] is None
    # Nunca agregada: también 412 con actual null
    nunca = _delete(entorno_ficha, familia.admin, grupo, persona, "quien_es", If_Match='"v1"')
    assert _problema(nunca, 412, "version-desactualizada")["actual"] is None


def test_quitar_y_volver_a_agregar_crea_otra_fila(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    _agregar(entorno_ficha, familia, "quien_es", "Primera")
    antes = _seccion_en_base(persona, "quien_es")
    assert _delete(entorno_ficha, familia.admin, grupo, persona, "quien_es", If_Match='"v1"').status_code == 204
    entorno_ficha.iam.reloj.avanzar(timedelta(minutes=5))
    vuelta = _agregar(entorno_ficha, familia, "quien_es", "Segunda")
    assert vuelta.headers["etag"] == '"v1"'
    despues = _seccion_en_base(persona, "quien_es")
    assert antes is not None and despues is not None
    assert despues[0] != antes[0] and despues[3] > antes[3]


# --- 428 y 422 de las cabeceras ---------------------------------------------------------------------------


@pytest.mark.parametrize("cabeceras", [{}, {"If_Match": "*"}, {"If_Match": ""}])
def test_428_al_escribir_sin_precondicion(entorno_ficha: EntornoFicha, cabeceras: dict[str, str]) -> None:
    familia = entorno_ficha.familia()
    respuesta = _put(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, "quien_es",
                     {"texto": "Le dicen Tere"}, **cabeceras)
    _problema(respuesta, 428, "falta-version")
    assert _filas("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", familia.persona.id) == [(0,)]


@pytest.mark.parametrize("cabeceras", [{}, {"If_Match": "*"}, {"If_Match": " "}])
def test_428_al_quitar_sin_if_match(entorno_ficha: EntornoFicha, cabeceras: dict[str, str]) -> None:
    familia = entorno_ficha.familia()
    _agregar(entorno_ficha, familia, "quien_es", "Le dicen Tere")
    respuesta = _delete(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, "quien_es", **cabeceras)
    _problema(respuesta, 428, "falta-version")
    assert _seccion_en_base(familia.persona.id, "quien_es") is not None


def test_422_con_las_dos_cabeceras_o_if_none_match_invalido(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    dos = _put(entorno_ficha, familia.admin, grupo, persona, "quien_es", {"texto": "x"}, If_Match='"v1"',
               If_None_Match="*")
    assert [(e["campo"], e["tipo"]) for e in _problema(dos, 422, "validacion")["errores"]] == [
        ("If-None-Match", "precondicion_doble")]
    otro = _put(entorno_ficha, familia.admin, grupo, persona, "quien_es", {"texto": "x"}, If_None_Match='"v1"')
    assert _problema(otro, 422, "validacion")["errores"][0]["tipo"] == "precondicion_invalida"


@pytest.mark.parametrize("if_match", [None, '"v1"'])
def test_422_al_quitar_con_if_none_match(entorno_ficha: EntornoFicha, if_match: str | None) -> None:
    familia = entorno_ficha.familia()
    _agregar(entorno_ficha, familia, "quien_es", "Le dicen Tere")
    cabeceras = {"If_None_Match": "*"} | ({} if if_match is None else {"If_Match": if_match})
    respuesta = _delete(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, "quien_es", **cabeceras)
    assert _problema(respuesta, 422, "validacion")["errores"][0]["campo"] == "If-None-Match"
    assert _seccion_en_base(familia.persona.id, "quien_es") is not None


# --- 422 del texto -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seccion", "cuerpo", "tipo"),
    [
        ("quien_es", {"texto": ""}, "vacio"),
        ("quien_es", {"texto": "   \n  "}, "vacio"),
        ("comunicacion", {"texto": "x" * 501}, "largo_maximo"),
        ("remedios", {"texto": "x" * 801}, "largo_maximo"),
        ("preferencias", {"texto": "Hola\x07"}, "value_error"),
        ("preferencias", {"texto": 5}, "string_type"),
        ("preferencias", {}, "missing"),
        ("preferencias", {"texto": "ok", "extra": "no"}, "extra_forbidden"),
    ],
)
def test_422_del_texto_nombra_el_campo_sin_el_valor(
    entorno_ficha: EntornoFicha, seccion: str, cuerpo: dict[str, Any], tipo: str
) -> None:
    familia = entorno_ficha.familia()
    for cabeceras in ({"If_None_Match": "*"}, {"If_Match": '"v1"'}):
        respuesta = _put(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, seccion, cuerpo,
                         **cabeceras)
        errores = _problema(respuesta, 422, "validacion")["errores"]
        assert tipo in [e["tipo"] for e in errores], errores
        if isinstance(cuerpo.get("texto"), str) and cuerpo["texto"].strip():
            assert cuerpo["texto"][:30] not in respuesta.text
    assert _filas("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", familia.persona.id) == [(0,)]


def test_remedios_admite_800_y_las_demas_500(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    _agregar(entorno_ficha, familia, "remedios", "r" * 800)
    largo = _put(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, "quien_es", {"texto": "q" * 501},
                 If_None_Match="*")
    error = _problema(largo, 422, "validacion")["errores"][0]
    assert (error["campo"], error["tipo"]) == ("texto", "largo_maximo") and "500" in error["mensaje"]


# --- 404, 403 y 503 -------------------------------------------------------------------------------------


@pytest.mark.parametrize("seccion", ["rutina", "manejo_situaciones", "red_apoyo", "horarios", "actividades", "notas"])
def test_404_si_no_es_una_de_las_seis(entorno_ficha: EntornoFicha, seccion: str) -> None:
    familia = entorno_ficha.familia()
    put = _put(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, seccion, {"texto": "x"},
               If_None_Match="*")
    _problema(put, 404, "no-encontrado")
    _problema(_delete(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, seccion, If_Match='"v1"'),
              404, "no-encontrado")


def test_404_desde_otro_grupo_nunca_403(entorno_ficha: EntornoFicha) -> None:
    """La familia B no lee, no agrega ni quita las secciones de la persona de A."""
    a = entorno_ficha.familia()
    b = entorno_ficha.familia()
    texto = _texto("remedios")
    _agregar(entorno_ficha, a, "remedios", texto)

    # Con su propio grupo, sobre la persona de A
    for respuesta in (
        _put(entorno_ficha, b.admin, b.grupo.id, a.persona.id, "remedios", {"texto": "x"}, If_Match='"v1"'),
        _put(entorno_ficha, b.admin, b.grupo.id, a.persona.id, "quien_es", {"texto": "x"}, If_None_Match="*"),
        _delete(entorno_ficha, b.admin, b.grupo.id, a.persona.id, "remedios", If_Match='"v1"'),
        entorno_ficha.leer(b.admin, b.grupo.id, a.persona.id),
    ):
        _problema(respuesta, 404, "no-encontrado")
        assert texto not in respuesta.text
    # Con el grupo de A, sin ser miembro
    _problema(_delete(entorno_ficha, b.admin, a.grupo.id, a.persona.id, "remedios", If_Match='"v1"'),
              404, "no-encontrado")
    fila = _seccion_en_base(a.persona.id, "remedios")
    assert fila is not None and fila[1] == 1


@pytest.mark.parametrize("rol", ["pagador", "observador"])
def test_404_para_roles_que_no_escriben(entorno_ficha: EntornoFicha, rol: str) -> None:
    familia = entorno_ficha.familia()
    _agregar(entorno_ficha, familia, "quien_es", "Le dicen Tere")
    usuario = familia.miembros[rol].usuario
    _problema(_put(entorno_ficha, usuario, familia.grupo.id, familia.persona.id, "quien_es", {"texto": "x"},
                   If_Match='"v1"'), 404, "no-encontrado")
    _problema(_delete(entorno_ficha, usuario, familia.grupo.id, familia.persona.id, "quien_es", If_Match='"v1"'),
              404, "no-encontrado")


def test_401_sin_token(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    _problema(_put(entorno_ficha, None, familia.grupo.id, familia.persona.id, "quien_es", {"texto": "x"},
                   If_None_Match="*"), 401, "no-autenticado")


def test_403_sin_consentimiento_no_crea_nada(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia(con_consentimiento=False)
    respuesta = _put(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, "quien_es",
                     {"texto": "Le dicen Tere"}, If_None_Match="*")
    _problema(respuesta, 403, "sin-consentimiento")
    _problema(_delete(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, "quien_es",
                      If_Match='"v1"'), 403, "sin-consentimiento")
    assert _filas("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", familia.persona.id) == [(0,)]


def test_503_sin_custodia(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    entorno_ficha.app.dependency_overrides[obtener_custodia] = lambda: None
    respuesta = _put(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, "quien_es",
                     {"texto": "Le dicen Tere"}, If_None_Match="*")
    _problema(respuesta, 503, "servicio-no-disponible")
    _problema(_delete(entorno_ficha, familia.admin, familia.grupo.id, familia.persona.id, "quien_es",
                      If_Match='"v1"'), 503, "servicio-no-disponible")


# --- Auditoría real y logs (RF-08) --------------------------------------------------------------------------


def _auditoria(request_id: str) -> list[tuple[Any, ...]]:
    return _filas(
        "SELECT accion, entidad, entidad_id, detalle, actor_ref FROM auditoria WHERE request_id = %s", request_id
    )


@pytest.mark.rf("RF-08")
def test_editar_y_quitar_quedan_auditados_con_el_tipo_sin_el_texto(entorno_ficha: EntornoFicha) -> None:
    entorno_ficha.app.dependency_overrides.pop(obtener_auditoria_ficha, None)
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    texto = _texto("remedios")

    agregada = _agregar(entorno_ficha, familia, "remedios", texto)
    fila = _seccion_en_base(persona, "remedios")
    assert fila is not None
    [editar] = _auditoria(agregada.headers["x-request-id"])
    assert editar == ("plan.editar", "plan_seccion", fila[0], {"seccion": "remedios"}, familia.admin.id)

    quitada = _delete(entorno_ficha, familia.admin, grupo, persona, "remedios", If_Match='"v1"')
    assert quitada.status_code == 204
    [quitar] = _auditoria(quitada.headers["x-request-id"])
    assert quitar == ("plan.quitar_seccion", "plan_seccion", fila[0], {"seccion": "remedios"}, familia.admin.id)

    # 412: la lectura de actual es plan.leer
    conflicto = _delete(entorno_ficha, familia.admin, grupo, persona, "remedios", If_Match='"v1"')
    assert conflicto.status_code == 412
    assert [f[0] for f in _auditoria(conflicto.headers["x-request-id"])] == ["plan.leer"]
    for f in (editar, quitar):
        assert texto not in repr(f)


@pytest.mark.rf("RF-08")
def test_logs_sin_el_texto_de_las_secciones(entorno_ficha: EntornoFicha, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    texto = _texto("remedios")
    largo = "Demasiado largo " + secrets.token_hex(6) + " " + "x" * 800

    _agregar(entorno_ficha, familia, "remedios", texto)
    assert entorno_ficha.leer(familia.admin, grupo, persona).status_code == 200
    assert _put(entorno_ficha, familia.admin, grupo, persona, "remedios", {"texto": largo},
                If_Match='"v1"').status_code == 422
    assert _put(entorno_ficha, familia.admin, grupo, persona, "remedios", {"texto": "otra"},
                If_Match='"v9"').status_code == 412
    assert _delete(entorno_ficha, familia.admin, grupo, persona, "remedios", If_Match='"v1"').status_code == 204

    salida = entorno_ficha.iam.texto_log()
    assert '"ruta": "/v1/personas-cuidadas/{persona_id}/plan/secciones/{seccion}"' in salida
    for prohibido in (texto, texto.split()[-1], largo[:30]):
        assert prohibido not in caplog.text
        assert prohibido not in salida
        for registro in caplog.records:
            assert not any(prohibido in repr(v) for v in vars(registro).values())

"""MATU-12 · Completar la ficha de relevo, por la API y contra PostgreSQL (RF-02).

Corren como matu_app, con cuentas sembradas por las fábricas e iniciadas por POST /v1/sesiones. La
custodia es CustodiaEnMemoria (override) y la auditoría un espía del puerto de MATU-14. Lo que quedó
en la base se revisa como superusuario.

Contrato: docs/api/propuestos/ficha.openapi.yaml. Fuera de alcance: If-Match / If-None-Match con
412 y 428 (MATU-13) y la fila de auditoria (MATU-14).

Solo textos sintéticos: Carmen cuida a María y los teléfonos son de la serie 5555.
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import obtener_fabrica_sesiones
from app.modules.care_plan.api.dependencias import obtener_auditoria_ficha, obtener_custodia, obtener_registro_auditoria
from tests.base_datos import DSN, requiere_base
from tests.dobles.custodia_en_memoria import CustodiaEnMemoria
from tests.dobles.registro_auditoria_en_memoria import RegistroAuditoriaEnMemoria
from tests.fabricas import FamiliaCreada
from tests.modules.care_plan.conftest import EntornoFicha

pytestmark = requiere_base

PROBLEMA = "application/problem+json"
CAMPOS = ("rutina", "manejo_situaciones", "red_apoyo")
CLAVES_CAMPO = {"texto", "etag", "actualizado_por", "actualizado_en"}
CLAVES_GUARDADO = {"campo", "texto", "etag", "actualizado_por", "actualizado_en", "completitud"}
NUNCA_ESCRITO = {"texto": None, "etag": None, "actualizado_por": None, "actualizado_en": None}

# El instante del RelojFijo de las pruebas (tests/conftest.py)
AHORA = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def _texto(campo: str) -> str:
    """Un texto sintético con una marca única, para buscarlo en la base, los logs y las respuestas."""
    marca = secrets.token_hex(6)
    textos = {
        "rutina": f"08:00 Despierta. Le gusta que abran la cortina primero. Marca {marca}",
        "manejo_situaciones": f"Le hace bien que le tomen la mano y le hablen de su pueblo. Marca {marca}",
        "red_apoyo": f"Rodrigo, su hijo: +56 9 5555 0102. Marca {marca}",
    }
    return textos[campo]


def _una(sql: str, *parametros: Any) -> tuple[Any, ...] | None:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchone()


def _contar(sql: str, *parametros: Any) -> int:
    fila = _una(sql, *parametros)
    assert fila is not None
    return int(fila[0])


def _planes(persona_id: uuid.UUID) -> int:
    return _contar("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", persona_id)


def _claves(persona_id: uuid.UUID) -> int:
    return _contar("SELECT count(*) FROM clave_datos WHERE persona_cuidada_id = %s", persona_id)


def _texto_en_claro_en_la_base(persona_id: uuid.UUID, texto: str) -> int:
    """Cuántas columnas del plan, de sus secciones o del outbox contienen el texto en claro."""
    patron = texto.encode("utf-8")
    with psycopg.connect(DSN) as cx:
        secciones = cx.execute(
            "SELECT s.contenido_cifrado FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
            " WHERE p.persona_cuidada_id = %s",
            (persona_id,),
        ).fetchall()
        planes = cx.execute(
            "SELECT p::text FROM plan_cuidado p WHERE p.persona_cuidada_id = %s", (persona_id,)
        ).fetchall()
        outbox = cx.execute("SELECT payload::text FROM evento_outbox").fetchall()
    return (
        sum(1 for (contenido,) in secciones if patron in bytes(contenido))
        + sum(1 for (fila,) in planes if texto in fila)
        + sum(1 for (fila,) in outbox if texto in fila)
    )


def _sin_problema_con_texto(respuesta: Any, texto: str) -> None:
    assert texto not in respuesta.text


# --- Criterios 1 y 3: tres campos, cada uno por separado; el plan nace en la primera escritura -----


@pytest.mark.rf("RF-02")
def test_ficha_tres_campos(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    admin, persona = familia.admin, familia.persona

    # Dada una persona sin ficha, leerla devuelve los tres campos vacíos y no crea el plan
    vacia = entorno_ficha.leer(admin, familia.grupo.id, persona.id)
    assert vacia.status_code == 200, vacia.text
    assert vacia.headers["cache-control"] == "no-store"
    assert vacia.json() == {
        "persona_id": str(persona.id),
        "completitud": 0,
        "actualizado_en": None,
        "campos": {campo: NUNCA_ESCRITO for campo in CAMPOS},
    }
    assert _planes(persona.id) == 0
    assert _claves(persona.id) == 0

    # Cuando se escribe cada campo por separado
    textos = {campo: _texto(campo) for campo in CAMPOS}
    for campo in CAMPOS:
        respuesta = entorno_ficha.escribir(admin, familia.grupo.id, persona.id, campo, {"texto": textos[campo]})

        # Entonces cada primera escritura responde 201 con su ETag, en la cabecera y en el cuerpo
        assert respuesta.status_code == 201, respuesta.text
        cuerpo = respuesta.json()
        assert set(cuerpo) == CLAVES_GUARDADO
        assert cuerpo["campo"] == campo
        assert cuerpo["texto"] == textos[campo]
        assert cuerpo["etag"] == respuesta.headers["etag"] == '"v1"'
        assert respuesta.headers["cache-control"] == "no-store"
        # El autor lleva id y nombre, nunca el email
        assert cuerpo["actualizado_por"] == {"id": str(admin.id), "nombre": admin.nombre}
        assert admin.email not in respuesta.text

    # El plan nació una sola vez, en la primera escritura, en modo ficha_relevo, con una sola DEK
    assert _una("SELECT modo FROM plan_cuidado WHERE persona_cuidada_id = %s", persona.id) == ("ficha_relevo",)
    assert _planes(persona.id) == 1
    assert _claves(persona.id) == 1
    # Tres secciones, cifradas: ningún texto queda en claro en la base
    assert _contar(
        "SELECT count(*) FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id WHERE p.persona_cuidada_id = %s",
        persona.id,
    ) == 3
    for texto in textos.values():
        assert _texto_en_claro_en_la_base(persona.id, texto) == 0

    # Y quien puede leer ve los tres, con su ETag y su autor
    for lector in (admin, familia.miembros["cuidador"].usuario, familia.miembros["pagador_con_plan"].usuario):
        ficha = entorno_ficha.leer(lector, familia.grupo.id, persona.id)
        assert ficha.status_code == 200, ficha.text
        cuerpo = ficha.json()
        assert cuerpo["completitud"] == 100
        for campo in CAMPOS:
            assert set(cuerpo["campos"][campo]) == CLAVES_CAMPO
            assert cuerpo["campos"][campo]["texto"] == textos[campo]
            assert cuerpo["campos"][campo]["etag"] == '"v1"'
            assert cuerpo["campos"][campo]["actualizado_por"] == {"id": str(admin.id), "nombre": admin.nombre}
        assert admin.email not in ficha.text


@pytest.mark.rf("RF-02")
def test_actualizar_un_campo_responde_200_y_sube_la_version(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    cuidador = familia.miembros["cuidador"].usuario
    primero = entorno_ficha.escribir(cuidador, familia.grupo.id, familia.persona.id, "rutina", {"texto": "Primera"})
    assert primero.status_code == 201

    segundo = entorno_ficha.escribir(cuidador, familia.grupo.id, familia.persona.id, "rutina", {"texto": "Segunda"})

    assert segundo.status_code == 200, segundo.text
    assert segundo.json()["etag"] == segundo.headers["etag"] == '"v2"'
    assert segundo.json()["actualizado_por"]["id"] == str(cuidador.id)
    leida = entorno_ficha.leer(familia.admin, familia.grupo.id, familia.persona.id).json()
    assert leida["campos"]["rutina"]["texto"] == "Segunda"
    assert leida["campos"]["rutina"]["etag"] == '"v2"'
    # Los otros campos no se tocaron
    assert leida["campos"]["red_apoyo"] == NUNCA_ESCRITO


@pytest.mark.rf("RF-02")
def test_texto_se_normaliza_y_cuenta_500_sin_los_extremos(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id

    con_saltos = entorno_ficha.escribir(
        familia.admin, grupo, persona, "rutina", {"texto": "  08:00 Despierta\r\n13:00 Almuerza  "}
    )
    justo = entorno_ficha.escribir(familia.admin, grupo, persona, "red_apoyo", {"texto": "   " + "a" * 500 + "\n  "})

    assert con_saltos.status_code == 201
    assert con_saltos.json()["texto"] == "08:00 Despierta\n13:00 Almuerza"
    assert justo.status_code == 201
    assert len(justo.json()["texto"]) == 500


@pytest.mark.rf("RF-02")
@pytest.mark.parametrize(
    ("cuerpo", "tipo"),
    [
        ({"texto": "a" * 501}, "string_too_long"),
        ({"texto": "Le gusta\tla radio"}, "value_error"),
        ({"texto": 5}, "string_type"),
        ({}, "missing"),
        ({"texto": "Hola", "diagnostico": "x"}, "extra_forbidden"),
    ],
    ids=["mas-de-500", "caracter-de-control", "no-es-texto", "sin-texto", "campo-extra"],
)
def test_cuerpo_invalido_422_sin_repetir_el_valor(
    entorno_ficha: EntornoFicha, cuerpo: dict[str, Any], tipo: str
) -> None:
    familia = entorno_ficha.familia()

    respuesta = entorno_ficha.escribir(familia.admin, familia.grupo.id, familia.persona.id, "rutina", cuerpo)

    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == PROBLEMA
    problema = respuesta.json()
    assert problema["type"] == "/errores/validacion"
    assert tipo in {e["tipo"] for e in problema["errores"]}
    if isinstance(cuerpo.get("texto"), str):
        assert cuerpo["texto"] not in respuesta.text
    # Un cuerpo inválido no crea nada
    assert _planes(familia.persona.id) == 0
    assert _claves(familia.persona.id) == 0


@pytest.mark.rf("RF-02")
def test_vacio_en_un_campo_nunca_escrito_422_sin_crear_nada(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()

    respuesta = entorno_ficha.escribir(familia.admin, familia.grupo.id, familia.persona.id, "rutina", {"texto": "   "})

    assert respuesta.status_code == 422
    assert respuesta.json()["errores"] == [
        {"campo": "texto", "mensaje": "un campo que nunca se escribió no se crea vacío", "tipo": "vacio_sin_crear"}
    ]
    assert _planes(familia.persona.id) == 0
    assert _claves(familia.persona.id) == 0
    assert entorno_ficha.auditoria.ediciones == []


@pytest.mark.rf("RF-02")
def test_vaciar_un_campo_conserva_su_etag_y_queda_sin_completar(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    escrito = entorno_ficha.escribir(familia.admin, grupo, persona, "red_apoyo", {"texto": _texto("red_apoyo")})
    assert escrito.status_code == 201

    vaciado = entorno_ficha.escribir(familia.admin, grupo, persona, "red_apoyo", {"texto": ""})

    assert vaciado.status_code == 200, vaciado.text
    assert vaciado.json()["texto"] is None
    assert vaciado.json()["etag"] == '"v2"'
    assert vaciado.json()["completitud"] == 0
    campo = entorno_ficha.leer(familia.admin, grupo, persona).json()["campos"]["red_apoyo"]
    assert campo["texto"] is None
    assert campo["etag"] == '"v2"'


# --- Criterio 2: quién lee y quién escribe ----------------------------------------------------------


@pytest.mark.rf("RF-02")
def test_observador_404(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    observador = familia.miembros["observador"].usuario

    lectura = entorno_ficha.leer(observador, familia.grupo.id, familia.persona.id)
    escritura = entorno_ficha.escribir(observador, familia.grupo.id, familia.persona.id, "rutina", {"texto": "Hola"})
    # Con un cuerpo inválido también 404: el rol se revisa antes que el cuerpo
    invalido = entorno_ficha.escribir(observador, familia.grupo.id, familia.persona.id, "rutina", {"texto": "a" * 501})

    for respuesta in (lectura, escritura, invalido):
        assert respuesta.status_code == 404
        assert respuesta.headers["content-type"] == PROBLEMA
        assert respuesta.json()["type"] == "/errores/no-encontrado"
    assert _planes(familia.persona.id) == 0
    assert entorno_ficha.auditoria.lecturas == entorno_ficha.auditoria.ediciones == []


@pytest.mark.rf("RF-02")
def test_pagador_sin_permiso_404(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    pagador = familia.miembros["pagador"].usuario
    con_permiso = familia.miembros["pagador_con_plan"].usuario
    grupo, persona = familia.grupo.id, familia.persona.id

    # El pagador sin puede_ver_plan no lee ni escribe
    assert entorno_ficha.leer(pagador, grupo, persona).status_code == 404
    assert entorno_ficha.escribir(pagador, grupo, persona, "rutina", {"texto": "Hola"}).status_code == 404
    # El pagador con puede_ver_plan lee, pero tampoco escribe
    assert entorno_ficha.leer(con_permiso, grupo, persona).status_code == 200
    escritura = entorno_ficha.escribir(con_permiso, grupo, persona, "rutina", {"texto": "Hola"})
    assert escritura.status_code == 404
    assert escritura.json()["type"] == "/errores/no-encontrado"
    assert _planes(persona) == 0


@pytest.mark.rf("RF-02")
def test_cuidador_escribe_y_lee(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    cuidador = familia.miembros["cuidador"].usuario

    escritura = entorno_ficha.escribir(cuidador, familia.grupo.id, familia.persona.id, "manejo_situaciones",
                                       {"texto": _texto("manejo_situaciones")})

    assert escritura.status_code == 201
    assert entorno_ficha.leer(cuidador, familia.grupo.id, familia.persona.id).json()["completitud"] == 33


@pytest.mark.rf("RF-02")
def test_persona_de_otro_grupo_404(entorno_ficha: EntornoFicha) -> None:
    # Dadas dos familias, con la ficha de la segunda ya escrita
    a, b = entorno_ficha.familia(), entorno_ficha.familia()
    texto = _texto("rutina")
    assert entorno_ficha.escribir(b.admin, b.grupo.id, b.persona.id, "rutina", {"texto": texto}).status_code == 201

    # Cuando el admin de la primera la pide con su propio grupo, o con el grupo ajeno
    con_su_grupo = entorno_ficha.leer(a.admin, a.grupo.id, b.persona.id)
    con_grupo_ajeno = entorno_ficha.leer(a.admin, b.grupo.id, b.persona.id)
    escritura = entorno_ficha.escribir(a.admin, a.grupo.id, b.persona.id, "rutina", {"texto": "Otro"})

    # Entonces 404, nunca 403, y nada del texto
    for respuesta in (con_su_grupo, con_grupo_ajeno, escritura):
        assert respuesta.status_code == 404
        assert texto not in respuesta.text
    assert _contar(
        "SELECT version FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
        " WHERE p.persona_cuidada_id = %s AND s.tipo = 'rutina'",
        b.persona.id,
    ) == 1


@pytest.mark.rf("RF-02")
@pytest.mark.parametrize(
    ("persona", "campo", "grupo"),
    [
        ("no-es-uuid", "rutina", "propio"),
        ("otra-persona", "rutina", "propio"),
        ("propia", "diagnostico", "propio"),
        ("propia", "rutina", None),
        ("propia", "rutina", "no-es-uuid"),
    ],
    ids=["persona-no-uuid", "persona-inexistente", "campo-desconocido", "sin-x-grupo-id", "grupo-no-uuid"],
)
def test_ruta_o_grupo_invalidos_404(entorno_ficha: EntornoFicha, persona: str, campo: str, grupo: str | None) -> None:
    familia = entorno_ficha.familia()
    persona_ruta = {"propia": str(familia.persona.id), "otra-persona": str(uuid.uuid4())}.get(persona, persona)
    grupo_cabecera = str(familia.grupo.id) if grupo == "propio" else grupo

    escritura = entorno_ficha.escribir(familia.admin, grupo_cabecera, persona_ruta, campo, {"texto": "Hola"})
    lectura = entorno_ficha.leer(familia.admin, grupo_cabecera, persona_ruta)

    assert escritura.status_code == 404
    assert escritura.json()["type"] == "/errores/no-encontrado"
    if campo == "rutina":
        assert lectura.status_code == 404
    assert _planes(familia.persona.id) == 0


@pytest.mark.rf("RF-02")
def test_sin_token_401(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()

    lectura = entorno_ficha.leer(None, familia.grupo.id, familia.persona.id)
    escritura = entorno_ficha.escribir(None, familia.grupo.id, familia.persona.id, "rutina", {"texto": "Hola"})

    for respuesta in (lectura, escritura):
        assert respuesta.status_code == 401
        assert respuesta.headers["www-authenticate"] == "Bearer"
    assert _planes(familia.persona.id) == 0


# --- Criterio 4: completitud ---------------------------------------------------------------------------


@pytest.mark.rf("RF-02")
def test_completitud_por_campo(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id

    def guardar(campo: str, texto: str) -> int:
        respuesta = entorno_ficha.escribir(familia.admin, grupo, persona, campo, {"texto": texto})
        assert respuesta.status_code in (200, 201), respuesta.text
        guardada = _una("SELECT completitud_pct FROM plan_cuidado WHERE persona_cuidada_id = %s", persona)
        leida = entorno_ficha.leer(familia.admin, grupo, persona).json()["completitud"]
        # La respuesta, la base y la lectura dicen lo mismo
        assert guardada == (respuesta.json()["completitud"],)
        assert leida == respuesta.json()["completitud"]
        return int(respuesta.json()["completitud"])

    assert entorno_ficha.leer(familia.admin, grupo, persona).json()["completitud"] == 0
    assert guardar("rutina", _texto("rutina")) == 33
    assert guardar("manejo_situaciones", _texto("manejo_situaciones")) == 67
    assert guardar("red_apoyo", _texto("red_apoyo")) == 100
    # Vaciar un campo baja la completitud, y volver a escribirlo la sube
    assert guardar("manejo_situaciones", "") == 67
    assert guardar("manejo_situaciones", _texto("manejo_situaciones")) == 100


# --- Criterio 5 y decisión D-B: consentimiento y revisión anual --------------------------------------


@pytest.mark.rf("RF-02")
def test_sin_consentimiento_403(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia(con_consentimiento=False)
    grupo, persona = familia.grupo.id, familia.persona.id

    lectura = entorno_ficha.leer(familia.admin, grupo, persona)
    escritura = entorno_ficha.escribir(familia.admin, grupo, persona, "rutina", {"texto": _texto("rutina")})
    # El consentimiento se revisa antes que el cuerpo: también 403 con un texto de más de 500
    invalido = entorno_ficha.escribir(familia.admin, grupo, persona, "rutina", {"texto": "a" * 501})

    for respuesta in (lectura, escritura, invalido):
        assert respuesta.status_code == 403
        assert respuesta.headers["content-type"] == PROBLEMA
        problema = respuesta.json()
        assert problema["type"] == "/errores/sin-consentimiento"
        assert problema["errores"] == []
        assert problema["request_id"] == respuesta.headers["x-request-id"]
    # Sin consentimiento no queda ni el plan ni la clave de datos, y nada se audita
    assert _planes(persona) == 0
    assert _claves(persona) == 0
    assert entorno_ficha.auditoria.lecturas == entorno_ficha.auditoria.ediciones == []


@pytest.mark.rf("RF-02")
def test_consentimiento_revocado_403(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(
            "UPDATE consentimiento SET revocado_en = %s WHERE id = %s", (AHORA, familia.persona.consentimiento_id)
        )

    respuesta = entorno_ficha.leer(familia.admin, familia.grupo.id, familia.persona.id)

    assert respuesta.status_code == 403
    assert respuesta.json()["type"] == "/errores/sin-consentimiento"


def _familia_cuidador_de_hecho(entorno: EntornoFicha, otorgado_en: datetime) -> FamiliaCreada:
    fabrica = entorno.fabrica
    admin = fabrica.usuario()
    grupo = fabrica.grupo(admin=admin)
    persona = fabrica.persona_cuidada(grupo, calidad="cuidador_de_hecho", otorgado_en=otorgado_en)
    return FamiliaCreada(grupo=grupo, admin=admin, miembros={}, persona=persona, ficha=None)


@pytest.mark.rf("RF-02")
def test_revision_vencida_403(entorno_ficha: EntornoFicha) -> None:
    # Dado un consentimiento de cuidador de hecho cuya revisión anual venció un día antes del reloj
    vencida = _familia_cuidador_de_hecho(entorno_ficha, AHORA - timedelta(days=366))
    assert _una("SELECT revision_vence_en < %s FROM consentimiento WHERE id = %s", AHORA,
                vencida.persona.consentimiento_id) == (True,)

    lectura = entorno_ficha.leer(vencida.admin, vencida.grupo.id, vencida.persona.id)
    escritura = entorno_ficha.escribir(vencida.admin, vencida.grupo.id, vencida.persona.id, "rutina",
                                       {"texto": _texto("rutina")})

    # Entonces 403 con su propio type, distinto de sin-consentimiento, y nada creado
    for respuesta in (lectura, escritura):
        assert respuesta.status_code == 403
        assert respuesta.headers["content-type"] == PROBLEMA
        problema = respuesta.json()
        assert problema["type"] == "/errores/revision-vencida"
        assert problema["type"] != "/errores/sin-consentimiento"
    assert _planes(vencida.persona.id) == 0
    assert _claves(vencida.persona.id) == 0

    # Y con la revisión todavía vigente (vence en una hora) se lee y se escribe
    vigente = _familia_cuidador_de_hecho(entorno_ficha, AHORA - timedelta(days=365) + timedelta(hours=1))
    assert entorno_ficha.leer(vigente.admin, vigente.grupo.id, vigente.persona.id).status_code == 200
    assert entorno_ficha.escribir(vigente.admin, vigente.grupo.id, vigente.persona.id, "rutina",
                                  {"texto": "Hola"}).status_code == 201


@pytest.mark.rf("RF-02")
def test_revision_vence_con_el_reloj(entorno_ficha: EntornoFicha) -> None:
    # La vigencia la decide el puerto Reloj, no la hora del sistema ni now() de la base
    familia = _familia_cuidador_de_hecho(entorno_ficha, AHORA - timedelta(days=365) + timedelta(hours=1))
    assert entorno_ficha.leer(familia.admin, familia.grupo.id, familia.persona.id).status_code == 200

    entorno_ficha.iam.reloj.avanzar(timedelta(hours=1))
    # El access token dura 15 minutos con el mismo reloj: se inicia sesión de nuevo
    entorno_ficha.tokens.clear()

    respuesta = entorno_ficha.leer(familia.admin, familia.grupo.id, familia.persona.id)
    assert respuesta.status_code == 403
    assert respuesta.json()["type"] == "/errores/revision-vencida"


# --- Criterio 7 y decisión D-A: el cifrado real y la custodia --------------------------------------------


@pytest.mark.rf("RF-02")
def test_ficha_de_la_fabrica_se_lee_por_la_api(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    textos = {"rutina": _texto("rutina"), "red_apoyo": _texto("red_apoyo")}
    ficha = entorno_ficha.fabrica.ficha(
        familia.persona, textos=textos, custodia=entorno_ficha.custodia, actualizado_por=familia.admin.id
    )
    assert ficha.campos == ("rutina", "red_apoyo")

    leida = entorno_ficha.leer(familia.miembros["cuidador"].usuario, familia.grupo.id, familia.persona.id).json()

    assert leida["completitud"] == 67
    assert leida["campos"]["rutina"]["texto"] == textos["rutina"]
    assert leida["campos"]["red_apoyo"]["texto"] == textos["red_apoyo"]
    assert leida["campos"]["manejo_situaciones"] == NUNCA_ESCRITO
    for texto in textos.values():
        assert _texto_en_claro_en_la_base(familia.persona.id, texto) == 0


@pytest.mark.rf("RF-02")
def test_sin_custodia_503_y_falla_cerrada(entorno_ficha: EntornoFicha) -> None:
    # Sin KEK configurada, la ficha no se lee ni se escribe, y no se crea nada
    entorno_ficha.app.dependency_overrides[obtener_custodia] = lambda: None
    familia = entorno_ficha.familia()

    lectura = entorno_ficha.leer(familia.admin, familia.grupo.id, familia.persona.id)
    escritura = entorno_ficha.escribir(familia.admin, familia.grupo.id, familia.persona.id, "rutina",
                                       {"texto": _texto("rutina")})

    for respuesta in (lectura, escritura):
        assert respuesta.status_code == 503
        assert respuesta.headers["content-type"] == PROBLEMA
        assert respuesta.json()["type"] == "/errores/servicio-no-disponible"
    assert _planes(familia.persona.id) == 0
    assert _claves(familia.persona.id) == 0


@pytest.mark.rf("RF-02")
def test_otra_kek_bajo_la_misma_version_es_error_generico_sin_dek_nueva(entorno_ficha: EntornoFicha) -> None:
    # Dada una ficha escrita con una custodia
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    texto = _texto("rutina")
    assert entorno_ficha.escribir(familia.admin, grupo, persona, "rutina", {"texto": texto}).status_code == 201
    dek_antes = _una("SELECT dek_cifrada_con_kek FROM clave_datos WHERE persona_cuidada_id = %s", persona)

    # Cuando la API pasa a otra custodia con la misma versión de KEK (la clave cambió sin cambiar la versión)
    entorno_ficha.app.dependency_overrides[obtener_custodia] = lambda: CustodiaEnMemoria()
    lectura = entorno_ficha.leer(familia.admin, grupo, persona)
    escritura = entorno_ficha.escribir(familia.admin, grupo, persona, "red_apoyo", {"texto": _texto("red_apoyo")})

    # Entonces error genérico, sin el texto, y la DEK de la persona no cambia ni se duplica
    for respuesta in (lectura, escritura):
        assert respuesta.status_code == 503
        assert texto not in respuesta.text
    assert _claves(persona) == 1
    assert _una("SELECT dek_cifrada_con_kek FROM clave_datos WHERE persona_cuidada_id = %s", persona) == dek_antes


@pytest.mark.rf("RF-02")
def test_clave_destruida_404_sin_clave_nueva(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    escrito = entorno_ficha.escribir(familia.admin, grupo, persona, "rutina", {"texto": _texto("rutina")})
    assert escrito.status_code == 201
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(
            "UPDATE clave_datos SET dek_cifrada_con_kek = NULL, destruida_en = %s WHERE persona_cuidada_id = %s",
            (AHORA, persona),
        )

    assert entorno_ficha.leer(familia.admin, grupo, persona).status_code == 404
    assert entorno_ficha.escribir(familia.admin, grupo, persona, "red_apoyo", {"texto": "Hola"}).status_code == 404
    assert _una("SELECT dek_cifrada_con_kek IS NULL FROM clave_datos WHERE persona_cuidada_id = %s", persona) == (True,)


# --- Punto de enganche de la auditoría (MATU-14) ----------------------------------------------------------


@pytest.mark.rf("RF-02")
def test_lectura_y_escritura_llaman_a_la_auditoria(entorno_ficha: EntornoFicha) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    cuidador = familia.miembros["cuidador"].usuario

    escrita = entorno_ficha.escribir(cuidador, grupo, persona, "red_apoyo", {"texto": _texto("red_apoyo")})
    entorno_ficha.leer(familia.admin, grupo, persona)

    plan = _una("SELECT id FROM plan_cuidado WHERE persona_cuidada_id = %s", persona)
    assert plan is not None
    [edicion] = entorno_ficha.auditoria.ediciones
    [lectura] = entorno_ficha.auditoria.lecturas
    assert (edicion.grupo_id, edicion.usuario_id, edicion.persona_cuidada_id, edicion.plan_id, edicion.campo) == (
        grupo, cuidador.id, persona, plan[0], "red_apoyo"
    )
    assert edicion.request_id == escrita.headers["x-request-id"]
    assert edicion.ocurrido_en == AHORA
    assert (lectura.usuario_id, lectura.plan_id, lectura.campo) == (familia.admin.id, plan[0], None)
    # Solo identificadores: ningún campo del evento lleva texto
    assert all(isinstance(v, uuid.UUID | str | datetime | type(None)) for v in vars(edicion).values())


# --- Criterio 6: ningún log con el texto -------------------------------------------------------------------


def _texto_en_registros(caplog: pytest.LogCaptureFixture, texto: str) -> list[str]:
    """Los registros cuyo mensaje, argumentos o atributos extra contienen el texto."""
    encontrados = []
    for registro in caplog.records:
        if texto in registro.getMessage() or any(texto in repr(valor) for valor in vars(registro).values()):
            encontrados.append(registro.name)
    return encontrados


@pytest.mark.rf("RF-02")
def test_log_sin_texto_de_ficha(entorno_ficha: EntornoFicha, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    textos = {campo: _texto(campo) for campo in CAMPOS}
    largo = "Texto demasiado largo " + secrets.token_hex(6) + " " + "x" * 500

    # Camino feliz: escribir los tres campos y leerlos
    for campo in CAMPOS:
        assert entorno_ficha.escribir(familia.admin, grupo, persona, campo, {"texto": textos[campo]}).status_code == 201
    assert entorno_ficha.leer(familia.admin, grupo, persona).status_code == 200

    # 422 por más de 500 caracteres: errores[] nombra el campo, nunca el valor
    invalido = entorno_ficha.escribir(familia.admin, grupo, persona, "rutina", {"texto": largo})
    assert invalido.status_code == 422
    assert [(e["campo"], e["tipo"]) for e in invalido.json()["errores"]] == [("texto", "string_too_long")]
    assert largo[:40] not in invalido.text

    # Fallo al descifrar: una sección alterada en la base responde un 500 genérico
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute(
            "UPDATE plan_seccion SET tag_auth = %s WHERE tipo = 'rutina'"
            " AND plan_id = (SELECT id FROM plan_cuidado WHERE persona_cuidada_id = %s)",
            (secrets.token_bytes(16), persona),
        )
    ilegible = entorno_ficha.leer(familia.admin, grupo, persona)
    assert ilegible.status_code == 500
    assert ilegible.json()["type"] == "/errores/error-interno"
    for texto in textos.values():
        assert texto not in ilegible.text

    # Entonces se registró algo (no pasa en vacío), pero ningún log tiene el texto
    assert any(r.name == "matu.api" for r in caplog.records)
    assert any(r.name == "matu.care_plan.cifrado" and r.getMessage() == "sección ilegible" for r in caplog.records)
    salida = entorno_ficha.iam.texto_log()
    assert '"ruta": "/v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}"' in salida
    for texto in (*textos.values(), largo[:40]):
        assert texto not in caplog.text
        assert _texto_en_registros(caplog, texto) == []
        assert texto not in salida
    # Ni el texto de la marca suelta (por si se registrara cortado)
    for texto in textos.values():
        marca = texto.rsplit(" ", 1)[-1]
        assert marca not in caplog.text
        assert marca not in salida


# --- MATU-14 · Auditoría real de lectura y escritura (RF-08) ------------------------------------------------


def _auditoria_real(entorno_ficha: EntornoFicha) -> None:
    """Quita el espía: la ruta usa AuditoriaFichaRegistro sobre RegistroAuditoriaSql."""
    entorno_ficha.app.dependency_overrides.pop(obtener_auditoria_ficha, None)


def _filas_auditoria(request_id: str) -> list[tuple[Any, ...]]:
    with psycopg.connect(DSN) as cx:
        return cx.execute(
            "SELECT grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id, motivo, ip, ocurrido_en"
            " FROM auditoria WHERE request_id = %s",
            (request_id,),
        ).fetchall()


@requiere_base
@pytest.mark.rf("RF-08")
def test_escritura_queda_auditada(entorno_ficha: EntornoFicha) -> None:
    _auditoria_real(entorno_ficha)
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    cuidador = familia.miembros["cuidador"].usuario
    texto = _texto("rutina")

    respuesta = entorno_ficha.escribir(cuidador, grupo, persona, "rutina", {"texto": texto})

    assert respuesta.status_code == 201
    seccion = _una(
        "SELECT s.id FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
        " WHERE p.persona_cuidada_id = %s AND s.tipo = 'rutina'",
        persona,
    )
    assert seccion is not None
    [fila] = _filas_auditoria(respuesta.headers["x-request-id"])
    assert fila[:8] == (grupo, "usuario", cuidador.id, "plan.editar", "plan_seccion", seccion[0], None, None)
    assert fila[8] == AHORA
    # Ninguna columna lleva el texto, el ETag ni la versión
    assert texto not in repr(fila) and respuesta.headers.get("etag", "§") not in repr(fila)


@requiere_base
@pytest.mark.rf("RF-08")
def test_lectura_queda_auditada(entorno_ficha: EntornoFicha) -> None:
    _auditoria_real(entorno_ficha)
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    texto = _texto("red_apoyo")
    assert entorno_ficha.escribir(familia.admin, grupo, persona, "red_apoyo", {"texto": texto}).status_code == 201

    respuesta = entorno_ficha.leer(familia.admin, grupo, persona)

    assert respuesta.status_code == 200
    plan = _una("SELECT id FROM plan_cuidado WHERE persona_cuidada_id = %s", persona)
    assert plan is not None
    [fila] = _filas_auditoria(respuesta.headers["x-request-id"])
    assert fila[:8] == (grupo, "usuario", familia.admin.id, "plan.leer", "plan_cuidado", plan[0], None, None)
    assert texto not in repr(fila)


@pytest.mark.rf("RF-08")
@pytest.mark.parametrize("accion", ["leer", "escribir"])
def test_si_la_auditoria_falla_no_se_devuelve_el_texto(entorno_ficha: EntornoFicha, accion: str) -> None:
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    texto = _texto("rutina")
    if accion == "leer":
        assert entorno_ficha.escribir(familia.admin, grupo, persona, "rutina", {"texto": texto}).status_code == 201
    _auditoria_real(entorno_ficha)
    registro = RegistroAuditoriaEnMemoria()
    registro.fallar_con(RuntimeError("la base rechazó la fila"))
    entorno_ficha.app.dependency_overrides[obtener_registro_auditoria] = lambda: registro
    try:
        try:
            if accion == "leer":
                respuesta = entorno_ficha.leer(familia.admin, grupo, persona)
            else:
                respuesta = entorno_ficha.escribir(familia.admin, grupo, persona, "rutina", {"texto": texto})
        except RuntimeError:
            respuesta = None
    finally:
        entorno_ficha.app.dependency_overrides.pop(obtener_registro_auditoria, None)

    if respuesta is not None:
        assert respuesta.status_code == 500
        assert texto not in respuesta.text
    assert registro.entradas == ()
    if accion == "escribir":
        # La escritura se deshizo: ni plan ni sección
        assert _planes(persona) == 0


def _commit_que_falla(sesion: Session) -> None:
    raise RuntimeError("el commit falló")


@pytest.mark.rf("RF-08")
def test_si_el_commit_falla_no_se_entrega_la_ficha(entorno_ficha: EntornoFicha) -> None:
    """Regresión: Depends(sesion_de_grupo, scope="function") cierra la transacción antes de responder."""
    _auditoria_real(entorno_ficha)
    familia = entorno_ficha.familia()
    grupo, persona = familia.grupo.id, familia.persona.id
    texto = _texto("rutina")
    assert entorno_ficha.escribir(familia.admin, grupo, persona, "rutina", {"texto": texto}).status_code == 201

    overrides = entorno_ficha.app.dependency_overrides
    previo = overrides.get(obtener_fabrica_sesiones)
    real = (previo or obtener_fabrica_sesiones)()
    fallida = sessionmaker(bind=real.kw["bind"])
    event.listen(fallida, "before_commit", _commit_que_falla)
    overrides[obtener_fabrica_sesiones] = lambda: fallida
    try:
        respuesta = entorno_ficha.leer(familia.admin, grupo, persona)
    finally:
        if previo is None:
            overrides.pop(obtener_fabrica_sesiones, None)
        else:
            overrides[obtener_fabrica_sesiones] = previo

    assert respuesta.status_code == 500
    assert texto not in respuesta.text

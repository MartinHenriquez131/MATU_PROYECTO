"""MATU-13 · Editar sin pisar lo que escribió otro (RF-04, ADR-015), por la API y contra PostgreSQL.

Dos miembros de la misma familia, creados por las fábricas de MATU-30: la admin (Carmen) y el
cuidador. Corren como matu_app; lo que quedó en la base se revisa como superusuario.

Contrato: docs/api/openapi.json (PUT …/plan/ficha/{campo}): If-Match / If-None-Match, 412
/errores/version-desactualizada con ``campo`` y ``actual``, y 428 /errores/falta-version.
La concurrencia real se prueba con dos hilos por la API y, de forma determinista, con dos
conexiones al repositorio: la comparación es atómica en la base.

Solo textos sintéticos, con una marca única para buscarlos en la base, las respuestas y los logs.
"""

import logging
import secrets
import threading
import uuid
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.core.db import obtener_fabrica_sesiones, sesion_tenant
from app.modules.care_plan.api.dependencias import obtener_auditoria_ficha
from app.modules.care_plan.domain.cifrado import SeccionCifrada
from app.modules.care_plan.infrastructure.repositorio_ficha import RepositorioFichaSQL
from tests.base_datos import DSN, requiere_base
from tests.fabricas import FamiliaCreada, UsuarioCreado
from tests.modules.care_plan.conftest import RUTA_FICHA, EntornoFicha

pytestmark = [requiere_base, pytest.mark.rf("RF-04")]

PROBLEMA = "application/problem+json"
SIN_VERSION = {"If-None-Match": "*"}


def _texto(quien: str) -> str:
    return f"08:00 Despierta. Le gusta que abran la cortina primero. Escribió {quien}. Marca {secrets.token_hex(6)}"


def _si_coincide(version: int) -> dict[str, str]:
    return {"If-Match": f'"v{version}"'}


def _una(sql: str, *parametros: Any) -> tuple[Any, ...] | None:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchone()


def _seccion(persona: uuid.UUID, campo: str) -> tuple[Any, ...] | None:
    """(version, actualizado_por) de la sección, como superusuario."""
    return _una(
        "SELECT s.version, s.actualizado_por FROM plan_seccion s JOIN plan_cuidado p ON p.id = s.plan_id"
        " WHERE p.persona_cuidada_id = %s AND s.tipo = %s",
        persona,
        campo,
    )


def _contar(sql: str, *parametros: Any) -> int:
    fila = _una(sql, *parametros)
    assert fila is not None
    return int(fila[0])


def _dos_miembros(entorno: EntornoFicha) -> tuple[FamiliaCreada, UsuarioCreado, UsuarioCreado]:
    familia = entorno.familia()
    return familia, familia.admin, familia.miembros["cuidador"].usuario


def _texto_guardado(entorno: EntornoFicha, familia: FamiliaCreada, campo: str) -> Any:
    return entorno.leer(familia.admin, familia.grupo.id, familia.persona.id).json()["campos"][campo]


def _es_412(respuesta: Any, campo: str) -> dict[str, Any]:
    assert respuesta.status_code == 412, respuesta.text
    assert respuesta.headers["content-type"] == PROBLEMA
    assert respuesta.headers["cache-control"] == "no-store"
    problema: dict[str, Any] = respuesta.json()
    assert problema["type"] == "/errores/version-desactualizada"
    assert problema["status"] == 412
    assert problema["title"] == "Otra persona cambió este contenido"
    assert problema["errores"] == []
    assert problema["request_id"] == respuesta.headers["x-request-id"]
    assert problema["campo"] == campo
    assert set(problema["actual"]) == {"texto", "etag", "actualizado_por", "actualizado_en"}
    return problema


# --- Criterio 2: If-Match desactualizado, 412 con el contenido actual -------------------------------------


def test_if_match_desactualizado_412(entorno_ficha: EntornoFicha) -> None:
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    primero = entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("Carmen")}, SIN_VERSION)
    assert primero.status_code == 201
    leido = primero.json()["etag"]
    assert leido == '"v1"'

    # Los dos leyeron "v1". Guarda primero el cuidador
    del_cuidador = _texto("el cuidador")
    gana = entorno_ficha.escribir(cuidador, grupo, persona, "rutina", {"texto": del_cuidador}, {"If-Match": leido})
    assert gana.status_code == 200
    assert gana.json()["etag"] == '"v2"'

    # La admin guarda con su "v1" desactualizado: 412 con lo que guardó el cuidador
    de_la_admin = _texto("Carmen otra vez")
    pierde = entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": de_la_admin}, {"If-Match": leido})

    problema = _es_412(pierde, "rutina")
    assert problema["actual"]["texto"] == del_cuidador
    assert problema["actual"]["etag"] == '"v2"' == pierde.headers["etag"]
    assert problema["actual"]["actualizado_por"] == {"id": str(cuidador.id), "nombre": cuidador.nombre}
    assert problema["actual"]["actualizado_en"] is not None
    assert problema["detail"].startswith(cuidador.nombre)
    assert de_la_admin not in pierde.text
    # Nada se escribió: ni el texto de la admin, ni una versión nueva, ni una edición auditada
    assert _seccion(persona, "rutina") == (2, cuidador.id)
    assert _texto_guardado(entorno_ficha, familia, "rutina")["texto"] == del_cuidador
    assert len(entorno_ficha.auditoria.ediciones) == 2


def test_412_no_fusiona_y_la_persona_decide(entorno_ficha: EntornoFicha) -> None:
    """Criterio 5: sin fusión automática. Quien perdió vuelve a guardar con el ETag del 412."""
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    assert entorno_ficha.escribir(admin, grupo, persona, "red_apoyo", {"texto": _texto("Carmen")}).status_code == 201
    del_cuidador = _texto("el cuidador")
    assert entorno_ficha.escribir(
        cuidador, grupo, persona, "red_apoyo", {"texto": del_cuidador}, _si_coincide(1)
    ).status_code == 200
    de_la_admin = _texto("Carmen otra vez")
    pierde = entorno_ficha.escribir(admin, grupo, persona, "red_apoyo", {"texto": de_la_admin}, _si_coincide(1))
    actual = _es_412(pierde, "red_apoyo")["actual"]
    # El contenido vigente es exactamente el del cuidador, sin nada de la admin mezclado
    assert actual["texto"] == del_cuidador

    # "Dejar la mía": la admin guarda con el ETag que trajo el 412
    elige = entorno_ficha.escribir(
        admin, grupo, persona, "red_apoyo", {"texto": de_la_admin}, {"If-Match": actual["etag"]}
    )

    assert elige.status_code == 200
    assert elige.json()["texto"] == de_la_admin
    assert elige.json()["etag"] == '"v3"'


def test_dos_campos_distintos_no_chocan(entorno_ficha: EntornoFicha) -> None:
    """El ETag es por campo (contrato, decisión 2): editar campos distintos nunca da 412."""
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("Carmen")}).status_code == 201
    assert entorno_ficha.escribir(cuidador, grupo, persona, "red_apoyo", {"texto": _texto("él")}).status_code == 201
    assert entorno_ficha.escribir(
        admin, grupo, persona, "rutina", {"texto": _texto("C")}, _si_coincide(1)
    ).status_code == 200
    assert entorno_ficha.escribir(
        cuidador, grupo, persona, "red_apoyo", {"texto": _texto("él")}, _si_coincide(1)
    ).status_code == 200


# --- Criterio 3: sin If-Match, o con If-Match: *, 428 -------------------------------------------------


@pytest.mark.parametrize("cabeceras", [None, {"If-Match": "*"}], ids=["sin_cabeceras", "if_match_comodin"])
def test_sin_if_match_428(entorno_ficha: EntornoFicha, cabeceras: dict[str, str] | None) -> None:
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("Carmen")}).status_code == 201
    texto = _texto("el cuidador")

    respuesta = entorno_ficha.escribir(cuidador, grupo, persona, "rutina", {"texto": texto}, cabeceras)

    assert respuesta.status_code == 428, respuesta.text
    assert respuesta.headers["content-type"] == PROBLEMA
    problema = respuesta.json()
    assert problema["type"] == "/errores/falta-version"
    assert problema["title"] == "Falta la versión del contenido"
    assert problema["request_id"] == respuesta.headers["x-request-id"]
    assert texto not in respuesta.text
    assert _seccion(persona, "rutina") == (1, admin.id)
    assert len(entorno_ficha.auditoria.ediciones) == 1


def test_if_match_comodin_428(entorno_ficha: EntornoFicha) -> None:
    """``If-Match: *`` no protege de pisar a otro: 428 también sobre un campo nunca escrito."""
    familia, admin, _ = _dos_miembros(entorno_ficha)
    respuesta = entorno_ficha.escribir(
        admin, familia.grupo.id, familia.persona.id, "rutina", {"texto": _texto("Carmen")}, {"If-Match": "*"}
    )
    assert respuesta.status_code == 428
    assert respuesta.json()["type"] == "/errores/falta-version"
    assert _contar("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", familia.persona.id) == 0


def test_sin_cabeceras_en_un_campo_nuevo_428_sin_crear_nada(entorno_ficha: EntornoFicha) -> None:
    familia, admin, _ = _dos_miembros(entorno_ficha)
    persona = familia.persona.id

    respuesta = entorno_ficha.escribir(admin, familia.grupo.id, persona, "rutina", {"texto": _texto("Carmen")}, None)

    assert respuesta.status_code == 428
    assert _contar("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", persona) == 0
    assert _contar("SELECT count(*) FROM clave_datos WHERE persona_cuidada_id = %s", persona) == 0
    assert entorno_ficha.auditoria.lecturas == entorno_ficha.auditoria.ediciones == []


# --- Criterio 4: primera escritura con If-None-Match: * -------------------------------------------------


def test_primera_escritura_concurrente_412(entorno_ficha: EntornoFicha) -> None:
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    # Los dos vieron el campo sin escribir (etag null). Guarda primero la admin
    de_la_admin = _texto("Carmen")
    primera = entorno_ficha.escribir(admin, grupo, persona, "red_apoyo", {"texto": de_la_admin}, SIN_VERSION)
    assert primera.status_code == 201

    del_cuidador = _texto("el cuidador")
    segunda = entorno_ficha.escribir(cuidador, grupo, persona, "red_apoyo", {"texto": del_cuidador}, SIN_VERSION)

    problema = _es_412(segunda, "red_apoyo")
    assert problema["actual"]["texto"] == de_la_admin
    assert problema["actual"]["etag"] == '"v1"' == segunda.headers["etag"]
    assert problema["actual"]["actualizado_por"] == {"id": str(admin.id), "nombre": admin.nombre}
    assert del_cuidador not in segunda.text
    assert _seccion(persona, "red_apoyo") == (1, admin.id)
    assert _contar("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", persona) == 1


def test_if_match_sobre_un_campo_nunca_escrito_412_con_etag_null(entorno_ficha: EntornoFicha) -> None:
    familia, admin, _ = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id

    # Sin plan: no lo crea, ni la clave de datos
    sin_plan = entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("Carmen")}, _si_coincide(1))

    problema = _es_412(sin_plan, "rutina")
    assert problema["actual"] == {"texto": None, "etag": None, "actualizado_por": None, "actualizado_en": None}
    assert "etag" not in sin_plan.headers
    assert _contar("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", persona) == 0
    assert _contar("SELECT count(*) FROM clave_datos WHERE persona_cuidada_id = %s", persona) == 0

    # Con plan, pero ese campo nunca se escribió
    assert entorno_ficha.escribir(admin, grupo, persona, "red_apoyo", {"texto": _texto("Carmen")}).status_code == 201
    con_plan = entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("Carmen")}, _si_coincide(1))
    assert _es_412(con_plan, "rutina")["actual"]["etag"] is None
    assert _seccion(persona, "rutina") is None


@pytest.mark.parametrize("if_match", ['W/"v1"', '"v9"', '"1"', '"v1", "v2"'])
def test_if_match_que_no_coincide_en_forma_fuerte_412(entorno_ficha: EntornoFicha, if_match: str) -> None:
    familia, admin, _ = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("Carmen")}).status_code == 201

    respuesta = entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("C")}, {"If-Match": if_match})

    assert _es_412(respuesta, "rutina")["actual"]["etag"] == '"v1"'
    assert _seccion(persona, "rutina") == (1, admin.id)


def test_vacio_con_if_none_match_422_aunque_el_campo_exista(entorno_ficha: EntornoFicha) -> None:
    """Contrato, decisión 6: se decide con la cabecera y el cuerpo, sin leer la base."""
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("Carmen")}).status_code == 201

    respuesta = entorno_ficha.escribir(cuidador, grupo, persona, "rutina", {"texto": "  "}, SIN_VERSION)

    assert respuesta.status_code == 422
    assert [e["tipo"] for e in respuesta.json()["errores"]] == ["vacio_sin_crear"]
    assert entorno_ficha.auditoria.lecturas == []


@pytest.mark.parametrize(
    ("cabeceras", "tipo"),
    [
        ({"If-Match": '"v1"', "If-None-Match": "*"}, "precondicion_doble"),
        ({"If-None-Match": '"v1"'}, "precondicion_invalida"),
    ],
)
def test_cabeceras_de_precondicion_invalidas_422(
    entorno_ficha: EntornoFicha, cabeceras: dict[str, str], tipo: str
) -> None:
    familia, admin, _ = _dos_miembros(entorno_ficha)
    respuesta = entorno_ficha.escribir(
        admin, familia.grupo.id, familia.persona.id, "rutina", {"texto": _texto("Carmen")}, cabeceras
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["type"] == "/errores/validacion"
    [error] = respuesta.json()["errores"]
    assert (error["campo"], error["tipo"]) == ("If-None-Match", tipo)
    assert '"v1"' not in respuesta.text


def test_cuerpo_invalido_va_antes_que_la_precondicion(entorno_ficha: EntornoFicha) -> None:
    """Orden del contrato: el cuerpo (paso 7, 422) antes que la precondición (paso 8, 428)."""
    familia, admin, _ = _dos_miembros(entorno_ficha)
    respuesta = entorno_ficha.escribir(admin, familia.grupo.id, familia.persona.id, "rutina", {"texto": 7}, None)
    assert respuesta.status_code == 422


def test_rol_y_consentimiento_van_antes_que_la_precondicion(entorno_ficha: EntornoFicha) -> None:
    """404 (rol) y 403 (consentimiento) antes del 428: la precondición no revela nada."""
    familia = entorno_ficha.familia()
    observador = entorno_ficha.escribir(
        familia.miembros["observador"].usuario, familia.grupo.id, familia.persona.id, "rutina", {"texto": "x"}, None
    )
    assert observador.status_code == 404
    sin_consentimiento = entorno_ficha.familia(con_consentimiento=False)
    respuesta = entorno_ficha.escribir(
        sin_consentimiento.admin, sin_consentimiento.grupo.id, sin_consentimiento.persona.id, "rutina",
        {"texto": "x"}, None,
    )
    assert respuesta.status_code == 403


def test_vaciar_con_if_match(entorno_ficha: EntornoFicha) -> None:
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("Carmen")}).status_code == 201

    vaciado = entorno_ficha.escribir(cuidador, grupo, persona, "rutina", {"texto": ""}, _si_coincide(1))

    assert vaciado.status_code == 200, vaciado.text
    assert vaciado.json()["texto"] is None
    assert vaciado.json()["etag"] == '"v2"' == vaciado.headers["etag"]
    assert vaciado.json()["completitud"] == 0
    # Vaciado conserva su etag: se vuelve a escribir con If-Match, no con If-None-Match
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": "x"}, SIN_VERSION).status_code == 412
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": "x"}, _si_coincide(2)).status_code == 200


# --- El 412 registra plan.leer (contrato, decisión 8; MATU-14) ---------------------------------------------


def test_412_registra_plan_leer(entorno_ficha: EntornoFicha) -> None:
    entorno_ficha.app.dependency_overrides.pop(obtener_auditoria_ficha, None)
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    texto = _texto("Carmen")
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": texto}).status_code == 201

    respuesta = entorno_ficha.escribir(cuidador, grupo, persona, "rutina", {"texto": _texto("él")}, _si_coincide(7))

    _es_412(respuesta, "rutina")
    plan = _una("SELECT id FROM plan_cuidado WHERE persona_cuidada_id = %s", persona)
    assert plan is not None
    with psycopg.connect(DSN) as cx:
        filas = cx.execute(
            "SELECT grupo_id, actor_tipo, actor_ref, accion, entidad, entidad_id FROM auditoria WHERE request_id = %s",
            (respuesta.headers["x-request-id"],),
        ).fetchall()
    # Una sola fila: la lectura del contenido actual, sin plan.editar, sin texto ni ETag
    assert filas == [(grupo, "usuario", cuidador.id, "plan.leer", "plan_cuidado", plan[0])]
    assert texto not in repr(filas) and '"v1"' not in repr(filas)


def test_412_con_auditoria_espia(entorno_ficha: EntornoFicha) -> None:
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("Carmen")}).status_code == 201

    respuesta = entorno_ficha.escribir(cuidador, grupo, persona, "rutina", {"texto": _texto("él")}, SIN_VERSION)

    assert respuesta.status_code == 412
    [lectura] = entorno_ficha.auditoria.lecturas
    assert (lectura.usuario_id, lectura.persona_cuidada_id, lectura.campo) == (cuidador.id, persona, None)
    assert lectura.request_id == respuesta.headers["x-request-id"]
    assert len(entorno_ficha.auditoria.ediciones) == 1


# --- Logs sin texto (CLAUDE.md, agente 2, punto 5) ------------------------------------------------------------


def test_log_sin_texto_en_412_y_428(entorno_ficha: EntornoFicha, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    guardado, rechazado, sin_version = _texto("Carmen"), _texto("el cuidador"), _texto("nadie")
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": guardado}).status_code == 201

    conflicto = entorno_ficha.escribir(cuidador, grupo, persona, "rutina", {"texto": rechazado}, SIN_VERSION)
    falta = entorno_ficha.escribir(cuidador, grupo, persona, "rutina", {"texto": sin_version}, None)

    assert (conflicto.status_code, falta.status_code) == (412, 428)
    # El 412 lleva el texto guardado en el cuerpo (para la pantalla), pero ningún log lo tiene
    assert guardado in conflicto.text
    salida = entorno_ficha.iam.texto_log()
    assert '"ruta": "/v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}"' in salida
    for texto in (guardado, rechazado, sin_version):
        marca = texto.rsplit(" ", 1)[-1]
        assert marca not in caplog.text
        assert marca not in salida
        assert all(marca not in repr(vars(r)) for r in caplog.records)


# --- Criterio 2 y 4, con concurrencia real: exactamente una gana ----------------------------------------------


def _carrera(entorno: EntornoFicha, cabeceras: dict[str, str], *usuarios: UsuarioCreado, persona: uuid.UUID,
             grupo: uuid.UUID) -> list[int]:
    """Dos PUT al mismo campo desde dos hilos, cada uno con su cliente, soltados a la vez."""
    barrera = threading.Barrier(len(usuarios))
    estados: list[int] = []
    errores: list[BaseException] = []
    ruta = RUTA_FICHA.format(persona) + "/rutina"
    tokens = {u.id: entorno.token(u) for u in usuarios}

    def escribir(usuario: UsuarioCreado) -> None:
        try:
            with TestClient(entorno.app) as cliente:
                barrera.wait(timeout=10)
                respuesta = cliente.put(
                    ruta,
                    json={"texto": _texto(usuario.nombre)},
                    headers={"Authorization": f"Bearer {tokens[usuario.id]}", "X-Grupo-Id": str(grupo), **cabeceras},
                )
            estados.append(respuesta.status_code)
        except BaseException as error:  # noqa: BLE001 - se informa en el hilo principal
            errores.append(error)

    hilos = [threading.Thread(target=escribir, args=(u,)) for u in usuarios]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=60)
    assert errores == []
    return sorted(estados)


def test_dos_escrituras_simultaneas_con_el_mismo_if_match_gana_una(entorno_ficha: EntornoFicha) -> None:
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("Carmen")}).status_code == 201

    estados = _carrera(entorno_ficha, _si_coincide(1), admin, cuidador, persona=persona, grupo=grupo)

    assert estados == [200, 412]
    seccion = _seccion(persona, "rutina")
    assert seccion is not None and seccion[0] == 2


def test_dos_primeras_escrituras_simultaneas_gana_una(entorno_ficha: EntornoFicha) -> None:
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id

    estados = _carrera(entorno_ficha, SIN_VERSION, admin, cuidador, persona=persona, grupo=grupo)

    assert estados == [201, 412]
    assert _seccion(persona, "rutina") is not None
    assert _contar("SELECT count(*) FROM plan_cuidado WHERE persona_cuidada_id = %s", persona) == 1


def _cifrada_falsa() -> SeccionCifrada:
    # El repositorio nunca descifra: basta un contenido opaco con la forma de una sección
    return SeccionCifrada(
        contenido_cifrado=secrets.token_bytes(8), nonce=secrets.token_bytes(12), tag_auth=secrets.token_bytes(16),
        kek_version=1,
    )


def test_update_condicional_es_atomico_con_la_fila_bloqueada(entorno_ficha: EntornoFicha) -> None:
    """Determinista: A actualiza sin confirmar; B, con la misma versión, espera el bloqueo y, cuando
    A confirma, PostgreSQL reevalúa el WHERE y B no escribe nada."""
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    assert entorno_ficha.escribir(admin, grupo, persona, "rutina", {"texto": _texto("Carmen")}).status_code == 201
    plan = _una("SELECT id FROM plan_cuidado WHERE persona_cuidada_id = %s", persona)
    assert plan is not None
    fabrica = (entorno_ficha.app.dependency_overrides.get(obtener_fabrica_sesiones) or obtener_fabrica_sesiones)()
    ahora = entorno_ficha.iam.reloj.ahora()
    resultado_b: list[int | None] = []
    b_empezo = threading.Event()

    def escritura_b() -> None:
        with sesion_tenant(fabrica, usuario_id=cuidador.id, grupo_id=grupo) as sesion:
            b_empezo.set()
            resultado_b.append(
                RepositorioFichaSQL(sesion, grupo).actualizar_seccion_si_version(
                    plan[0], "rutina", _cifrada_falsa(), 1, cuidador.id, ahora
                )
            )

    with sesion_tenant(fabrica, usuario_id=admin.id, grupo_id=grupo) as sesion_a:
        nueva_a = RepositorioFichaSQL(sesion_a, grupo).actualizar_seccion_si_version(
            plan[0], "rutina", _cifrada_falsa(), 1, admin.id, ahora
        )
        hilo = threading.Thread(target=escritura_b)
        hilo.start()
        assert b_empezo.wait(timeout=10)
        hilo.join(timeout=0.5)
        # B sigue esperando el bloqueo de A
        assert hilo.is_alive()
    hilo.join(timeout=10)

    assert nueva_a == 2
    assert resultado_b == [None]
    assert _seccion(persona, "rutina") == (2, admin.id)


def test_insert_de_la_primera_escritura_es_atomico(entorno_ficha: EntornoFicha) -> None:
    """Dos INSERT del mismo campo: el segundo espera al primero y, al confirmarse, no escribe (412, no 500)."""
    familia, admin, cuidador = _dos_miembros(entorno_ficha)
    grupo, persona = familia.grupo.id, familia.persona.id
    # Crea el plan con otro campo
    assert entorno_ficha.escribir(admin, grupo, persona, "red_apoyo", {"texto": _texto("Carmen")}).status_code == 201
    plan = _una("SELECT id FROM plan_cuidado WHERE persona_cuidada_id = %s", persona)
    assert plan is not None
    fabrica = (entorno_ficha.app.dependency_overrides.get(obtener_fabrica_sesiones) or obtener_fabrica_sesiones)()
    ahora = entorno_ficha.iam.reloj.ahora()
    resultado_b: list[bool] = []

    def escritura_b() -> None:
        with sesion_tenant(fabrica, usuario_id=cuidador.id, grupo_id=grupo) as sesion:
            resultado_b.append(
                RepositorioFichaSQL(sesion, grupo).insertar_seccion(
                    plan[0], "rutina", _cifrada_falsa(), cuidador.id, ahora
                )
            )

    with sesion_tenant(fabrica, usuario_id=admin.id, grupo_id=grupo) as sesion_a:
        creada_a = RepositorioFichaSQL(sesion_a, grupo).insertar_seccion(
            plan[0], "rutina", _cifrada_falsa(), admin.id, ahora
        )
        hilo = threading.Thread(target=escritura_b)
        hilo.start()
        hilo.join(timeout=0.5)
        assert hilo.is_alive()
    hilo.join(timeout=10)

    assert creada_a is True
    assert resultado_b == [False]
    assert _seccion(persona, "rutina") == (1, admin.id)

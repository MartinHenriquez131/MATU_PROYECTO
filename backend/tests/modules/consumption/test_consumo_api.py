"""MATU-36 · Autorización y perfil de consumo por la API, contra PostgreSQL (RF-10, RF-11).

Corren como matu_app con cuentas sembradas por las fábricas. Lo que quedó en la base se revisa como
superusuario. Solo datos sintéticos.
"""

import logging
import uuid
from datetime import timedelta
from typing import Any

import psycopg
import pytest

from tests.base_datos import DSN, requiere_base
from tests.modules.consumption.conftest import EntornoConsumo

pytestmark = requiere_base

PROBLEMA = "application/problem+json"
AVISO = {"id": "aviso_cuidador_de_hecho", "version": "1.1"}


def _una(sql: str, *parametros: Any) -> tuple[Any, ...] | None:
    with psycopg.connect(DSN) as cx:
        return cx.execute(sql, parametros).fetchone()


def _acciones(grupo: uuid.UUID) -> list[str]:
    with psycopg.connect(DSN) as cx:
        filas = cx.execute("SELECT accion FROM auditoria WHERE grupo_id = %s ORDER BY id", (grupo,)).fetchall()
    return [f[0] for f in filas]


# --- Autorización ----------------------------------------------------------------------------------


@pytest.mark.rf("RF-10")
def test_sin_autorizacion_todas_las_rutas_responden_403_con_finalidad(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia(con_autorizacion=False)
    perfil = e.fabrica.perfil_consumo(familia.persona)
    for metodo, sufijo in [
        ("GET", ""),
        ("POST", ""),
        ("GET", f"/{perfil}"),
        ("PATCH", f"/{perfil}"),
        ("DELETE", f"/{perfil}"),
        ("POST", f"/{perfil}/desactivar"),
        ("POST", f"/{perfil}/activar"),
    ]:
        respuesta = e.pedir(metodo, familia.admin, familia, sufijo, json={"stock_unidades": 1})
        assert respuesta.status_code == 403, (metodo, sufijo)
        cuerpo = respuesta.json()
        assert cuerpo["type"] == "/errores/sin-consentimiento" and cuerpo["finalidad"] == "consumo"
        assert respuesta.headers["Cache-Control"] == "no-store"


@pytest.mark.rf("RF-10")
def test_dar_la_autorizacion_y_luego_crear(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia(con_autorizacion=False)
    cuidadora = familia.miembros["cuidador"].usuario
    respuesta = e.iam.cliente.post(
        f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos",
        json={"finalidad": "consumo", "calidad_otorgante": "cuidador_de_hecho", "aviso": AVISO},
        headers=e.cabeceras(cuidadora, familia.grupo.id),
    )
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["consentimiento"]["finalidad"] == "consumo"
    assert cuerpo["consentimiento"]["revision_vence_en"] is not None
    assert cuerpo["aviso"]["id"] == "aviso_cuidador_de_hecho"
    fila = _una(
        "SELECT evidencia -> 'declaracion' ->> 'id' FROM consentimiento WHERE id = %s",
        cuerpo["consentimiento"]["id"],
    )
    assert fila == ("declaracion_consumo_cuidador_de_hecho",)
    assert "consentimiento.otorgar" in _acciones(familia.grupo.id)
    # Ya vigente: 409
    otra = e.iam.cliente.post(
        f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos",
        json={"finalidad": "consumo", "calidad_otorgante": "titular"},
        headers=e.cabeceras(familia.admin, familia.grupo.id),
    )
    assert otra.status_code == 409 and otra.json()["type"] == "/errores/autorizacion-vigente"
    assert e.crear(cuidadora, familia).status_code == 201


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize("rol", ["pagador", "observador"])
def test_pagador_y_observador_no_dan_la_autorizacion(entorno_consumo: EntornoConsumo, rol: str) -> None:
    e = entorno_consumo
    familia = e.familia(con_autorizacion=False)
    respuesta = e.iam.cliente.post(
        f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos",
        json={"finalidad": "consumo", "calidad_otorgante": "titular"},
        headers=e.cabeceras(familia.miembros[rol].usuario, familia.grupo.id),
    )
    assert respuesta.status_code == 404


@pytest.mark.rf("RF-10")
def test_autorizacion_con_finalidad_distinta_es_422(entorno_consumo: EntornoConsumo) -> None:
    """Desde MATU-44 (decisión 128) se acepta también plan_cuidado: con la del alta vigente, 409. Otra, 422."""
    e = entorno_consumo
    familia = e.familia(con_autorizacion=False)

    def pedir(finalidad: str) -> Any:
        return e.iam.cliente.post(
            f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos",
            json={"finalidad": finalidad, "calidad_otorgante": "titular"},
            headers=e.cabeceras(familia.admin, familia.grupo.id),
        )

    assert pedir("despacho").status_code == 422
    vigente = pedir("plan_cuidado")
    assert vigente.status_code == 409 and vigente.json()["type"] == "/errores/autorizacion-vigente"


@pytest.mark.rf("RF-10")
def test_revision_vencida_es_403_propio(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia(con_autorizacion=False)
    e.fabrica.autorizacion_consumo(
        familia.persona, otorgante=familia.admin, calidad="cuidador_de_hecho", otorgado_en=e.iam.reloj.ahora()
    )
    assert e.pedir("GET", familia.admin, familia).status_code == 200
    e.iam.reloj.avanzar(timedelta(days=366))
    e.tokens.clear()
    respuesta = e.pedir("GET", familia.admin, familia)
    assert respuesta.status_code == 403
    assert respuesta.json()["type"] == "/errores/revision-vencida" and respuesta.json()["finalidad"] == "consumo"


# --- Camino feliz ------------------------------------------------------------------------------------


@pytest.mark.rf("RF-11")
def test_crear_ver_listar_editar_desactivar_activar_eliminar(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    cuidadora = familia.miembros["cuidador"].usuario
    creado = e.crear(cuidadora, familia, dias_aviso=5)
    assert creado.status_code == 201, creado.text
    perfil = creado.json()
    # RelojFijo: 20-10-2026 12:00 UTC = 09:00 en Santiago
    assert perfil["stock_medido_en"] == "2026-10-20" and perfil["fecha_quiebre_estimada"] == "2026-10-26"
    assert perfil["dias_restantes"] == 6 and perfil["etag"] == '"v1"' and perfil["producto"] is None
    assert perfil["actualizado_por"]["id"] == str(cuidadora.id)
    assert creado.headers["ETag"] == '"v1"' and creado.headers["Cache-Control"] == "no-store"
    assert creado.headers["Location"].endswith(f"/consumo/{perfil['id']}")
    assert "grupo_id" not in perfil

    ruta = f"/{perfil['id']}"
    assert e.pedir("GET", familia.admin, familia, ruta).json()["id"] == perfil["id"]
    lista = e.pedir("GET", familia.miembros["observador"].usuario, familia)
    assert lista.status_code == 200 and [p["id"] for p in lista.json()["items"]] == [perfil["id"]]

    editado = e.pedir("PATCH", familia.admin, familia, ruta, json={"stock_unidades": 20}, If_Match='"v1"')
    assert editado.status_code == 200, editado.text
    assert editado.json()["etag"] == '"v2"' and editado.json()["fecha_quiebre_estimada"] == "2026-10-25"

    desactivado = e.pedir("POST", familia.admin, familia, ruta + "/desactivar")
    assert desactivado.status_code == 200 and desactivado.json()["activo"] is False
    assert e.pedir("GET", familia.admin, familia).json()["items"] == []
    todos = e.pedir("GET", familia.admin, familia, params={"activo": "todos"}).json()["items"]
    assert [p["activo"] for p in todos] == [False]
    inactivos = e.pedir("GET", familia.admin, familia, params={"activo": "false"}).json()["items"]
    assert len(inactivos) == 1

    activado = e.pedir("POST", cuidadora, familia, ruta + "/activar")
    assert activado.status_code == 200 and activado.json()["activo"] is True and activado.json()["etag"] == '"v4"'

    borrado = e.pedir("DELETE", cuidadora, familia, ruta)
    assert borrado.status_code == 204
    assert _una("SELECT 1 FROM perfil_consumo WHERE id = %s", perfil["id"]) is None
    assert e.pedir("GET", familia.admin, familia, ruta).status_code == 404
    assert _acciones(familia.grupo.id) == [
        "consumo.crear", "consumo.editar", "consumo.desactivar", "consumo.activar", "consumo.eliminar",
    ]


@pytest.mark.rf("RF-10")
def test_eliminar_borra_tambien_sus_alertas(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    with psycopg.connect(DSN, autocommit=True) as cx:
        cx.execute("INSERT INTO alerta_quiebre (perfil_id, fecha_prevista) VALUES (%s, '2026-10-26')", (perfil,))
    assert e.pedir("DELETE", familia.admin, familia, f"/{perfil}").status_code == 204
    assert _una("SELECT 1 FROM alerta_quiebre WHERE perfil_id = %s", perfil) is None


# --- Errores -------------------------------------------------------------------------------------------


@pytest.mark.rf("RF-10")
def test_otro_grupo_es_404(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    nuestra = e.familia()
    ajena = e.familia()
    perfil_ajeno = e.fabrica.perfil_consumo(ajena.persona)
    # La persona de otro grupo
    assert e.pedir("GET", nuestra.admin, nuestra, persona=ajena.persona.id).status_code == 404
    # El perfil de otra persona bajo nuestra persona
    assert e.pedir("GET", nuestra.admin, nuestra, f"/{perfil_ajeno}").status_code == 404
    assert e.pedir("DELETE", nuestra.admin, nuestra, f"/{perfil_ajeno}").status_code == 404
    assert e.pedir("GET", nuestra.admin, nuestra, "/no-es-uuid").status_code == 404
    assert _una("SELECT 1 FROM perfil_consumo WHERE id = %s", perfil_ajeno) == (1,)


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize("rol", ["pagador", "observador"])
def test_pagador_y_observador_leen_pero_no_escriben(entorno_consumo: EntornoConsumo, rol: str) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    miembro = familia.miembros[rol].usuario
    assert e.pedir("GET", miembro, familia).status_code == 200
    assert e.pedir("GET", miembro, familia, f"/{perfil}").status_code == 200
    assert e.crear(miembro, familia).status_code == 404
    editar = e.pedir("PATCH", miembro, familia, f"/{perfil}", json={"stock_unidades": 1}, If_Match='"v1"')
    assert editar.status_code == 404
    for sufijo in ("/desactivar", "/activar"):
        assert e.pedir("POST", miembro, familia, f"/{perfil}{sufijo}").status_code == 404
    assert e.pedir("DELETE", miembro, familia, f"/{perfil}").status_code == 404
    assert _una("SELECT version FROM perfil_consumo WHERE id = %s", perfil) == (1,)


@pytest.mark.rf("RF-10")
def test_412_trae_el_actual_y_quien_guardo_y_428_sin_if_match(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    cuidadora = familia.miembros["cuidador"].usuario
    perfil = e.crear(familia.admin, familia).json()
    ruta = f"/{perfil['id']}"
    assert e.pedir("PATCH", cuidadora, familia, ruta, json={"stock_unidades": 18}, If_Match='"v1"').status_code == 200
    conflicto = e.pedir("PATCH", familia.admin, familia, ruta, json={"stock_unidades": 20}, If_Match='"v1"')
    assert conflicto.status_code == 412
    assert conflicto.headers["content-type"].startswith(PROBLEMA) and conflicto.headers["ETag"] == '"v2"'
    actual = conflicto.json()["actual"]
    assert actual["stock_unidades"] == 18 and actual["etag"] == '"v2"'
    assert actual["actualizado_por"] == {
        "id": str(cuidadora.id), "nombre": cuidadora.nombre.split()[0], "autor_activo": True}
    assert cuidadora.nombre.split()[0] in conflicto.json()["detail"]
    for valor in (None, "", "*"):
        if valor is None:
            respuesta = e.pedir("PATCH", familia.admin, familia, ruta, json={"stock_unidades": 20})
        else:
            respuesta = e.pedir("PATCH", familia.admin, familia, ruta, json={"stock_unidades": 20}, If_Match=valor)
        assert respuesta.status_code == 428 and respuesta.json()["type"] == "/errores/falta-version"
    # Un valor que no es un ETag de MATU nunca coincide: 412, no 422
    assert e.pedir("PATCH", familia.admin, familia, ruta, json={"dias_aviso": 1}, If_Match="basura").status_code == 412


@pytest.mark.rf("RF-10")
def test_perfil_inactivo_no_se_edita(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona, activo=False)
    respuesta = e.pedir("PATCH", familia.admin, familia, f"/{perfil}", json={"dias_aviso": 1}, If_Match='"v1"')
    assert respuesta.status_code == 409 and respuesta.json()["type"] == "/errores/perfil-inactivo"


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize(
    ("cuerpo", "campo", "tipo"),
    [
        ({"nombre_libre": "x" * 61}, "nombre_libre", "string_too_long"),
        ({"nombre_libre": "Pañal\nadulto M"}, "nombre_libre", "value_error"),
        ({"nombre_libre": "Pañal\tM"}, "nombre_libre", "value_error"),
        ({"nombre_libre": None}, "nombre_libre", "producto_o_nombre"),
        ({"stock_medido_en": "2026-10-01"}, "stock_medido_en", "extra_forbidden"),
        ({"tasa_dias": 91}, "tasa_dias", "less_than_equal"),
        ({"stock_unidades": 100_000, "tasa_unidades": 1, "tasa_dias": 90}, "stock_unidades", "cobertura_maxima"),
    ],
)
def test_crear_con_cuerpo_invalido_es_422_sin_repetir_el_valor(
    entorno_consumo: EntornoConsumo, cuerpo: dict[str, Any], campo: str, tipo: str
) -> None:
    e = entorno_consumo
    familia = e.familia()
    respuesta = e.crear(familia.admin, familia, **cuerpo)
    assert respuesta.status_code == 422, respuesta.text
    [error] = [x for x in respuesta.json()["errores"] if x["campo"] == campo]
    assert error["tipo"] == tipo
    if isinstance(cuerpo.get("nombre_libre"), str):
        assert cuerpo["nombre_libre"] not in respuesta.text
    assert _una("SELECT 1 FROM perfil_consumo WHERE grupo_id = %s", familia.grupo.id) is None


@pytest.mark.rf("RF-10")
@pytest.mark.parametrize(
    ("cuerpo", "tipo"),
    [({}, "cuerpo_vacio"), ({"stock_unidades": None}, "null_no_admitido"), ({"activo": False}, "extra_forbidden"),
     ({"nombre_libre": "Pañal\r\nM"}, "value_error")],
)
def test_editar_con_cuerpo_invalido_es_422(entorno_consumo: EntornoConsumo, cuerpo: dict[str, Any], tipo: str) -> None:
    e = entorno_consumo
    familia = e.familia()
    perfil = e.fabrica.perfil_consumo(familia.persona)
    respuesta = e.pedir("PATCH", familia.admin, familia, f"/{perfil}", json=cuerpo, If_Match='"v1"')
    assert respuesta.status_code == 422 and respuesta.json()["errores"][0]["tipo"] == tipo


@pytest.mark.rf("RF-10")
def test_activo_invalido_y_cursor_invalido_son_422(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    assert e.pedir("GET", familia.admin, familia, params={"activo": "quizas"}).status_code == 422
    assert e.pedir("GET", familia.admin, familia, params={"cursor": "%%%"}).status_code == 422


@pytest.mark.rf("RF-11")
def test_lista_paginada_por_fecha(entorno_consumo: EntornoConsumo) -> None:
    e = entorno_consumo
    familia = e.familia()
    ids = [e.fabrica.perfil_consumo(familia.persona, stock_unidades=s) for s in (40, 8, 24)]
    primera = e.pedir("GET", familia.admin, familia, params={"limite": 2}).json()
    assert [p["id"] for p in primera["items"]] == [str(ids[1]), str(ids[2])]
    segunda = e.pedir("GET", familia.admin, familia, params={"limite": 2, "cursor": primera["siguiente_cursor"]}).json()
    assert [p["id"] for p in segunda["items"]] == [str(ids[0])] and segunda["siguiente_cursor"] is None


# --- Logs ----------------------------------------------------------------------------------------------


@pytest.mark.rf("RF-10")
def test_nombre_libre_nunca_va_a_los_logs(entorno_consumo: EntornoConsumo, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    e = entorno_consumo
    familia = e.familia()
    marca = f"Toallitas marca {uuid.uuid4().hex[:8]}"
    creado = e.crear(familia.admin, familia, nombre_libre=marca)
    assert creado.status_code == 201
    ruta = f"/{creado.json()['id']}"
    e.pedir("PATCH", familia.admin, familia, ruta, json={"nombre_libre": marca + " 2"}, If_Match='"v1"')
    e.pedir("PATCH", familia.admin, familia, ruta, json={"nombre_libre": marca + "\n"}, If_Match='"v1"')
    e.crear(familia.admin, familia, nombre_libre=marca + "\nx")
    for registro in caplog.records:
        assert marca not in registro.getMessage()
        assert marca not in str(registro.__dict__)
    assert marca not in e.iam.texto_log()
    with psycopg.connect(DSN) as cx:
        filas = cx.execute("SELECT * FROM auditoria WHERE grupo_id = %s", (familia.grupo.id,)).fetchall()
    assert filas and marca not in str(filas)

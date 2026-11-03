"""MATU-36 · Las rutas del consumo con dobles, sin base (RF-10, RF-11).

Sobreescribe las dependencias de autorización, repositorio, auditoría y reloj: prueba la capa HTTP
(códigos, cabeceras, 412 con quien guardó, 428, 409, 422 sin repetir el valor, activo=todos, cursor,
204) y que nombre_libre nunca llega a los logs. El orden con la base y RLS lo prueban
test_consumo_api.py y test_aislamiento.py.
"""

import io
import logging
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.modules.consumption.api.dependencias import (
    ConsumoAutorizado,
    consumo_para_escribir,
    consumo_para_leer,
    obtener_registro_auditoria_consumo,
    obtener_repositorio_perfiles,
)
from app.modules.iam.api.dependencias import obtener_reloj
from tests.dobles.registro_auditoria_en_memoria import RegistroAuditoriaEnMemoria
from tests.dobles.reloj_fijo import RelojFijo
from tests.modules.consumption.test_perfiles_aplicacion import (
    AHORA,
    CARMEN,
    GRUPO,
    PERSONA,
    RepositorioEnMemoria,
)

pytestmark = pytest.mark.rf("RF-10")

RUTA = f"/v1/personas-cuidadas/{PERSONA}/consumo"


class Contexto:
    grupo_id = GRUPO
    usuario_id = CARMEN


class Entorno:
    def __init__(self) -> None:
        self.repo = RepositorioEnMemoria()
        self.auditoria = RegistroAuditoriaEnMemoria()
        self.reloj = RelojFijo(AHORA)
        self.logs = io.StringIO()
        app = crear_app(self.logs)
        autorizado = ConsumoAutorizado(contexto=Contexto(), persona_id=PERSONA)  # type: ignore[arg-type]
        app.dependency_overrides[consumo_para_leer] = lambda: autorizado
        app.dependency_overrides[consumo_para_escribir] = lambda: autorizado
        app.dependency_overrides[obtener_repositorio_perfiles] = lambda: self.repo
        app.dependency_overrides[obtener_registro_auditoria_consumo] = lambda: self.auditoria
        app.dependency_overrides[obtener_reloj] = lambda: self.reloj
        self.cliente = TestClient(app, raise_server_exceptions=False)

    def crear(self, **cuerpo: Any) -> Any:
        base: dict[str, Any] = {"nombre_libre": "Pañal adulto M", "tasa_unidades": 4, "stock_unidades": 24}
        base.update(cuerpo)
        return self.cliente.post(RUTA, json=base)


@pytest.fixture
def e() -> Iterator[Entorno]:
    entorno = Entorno()
    with entorno.cliente:
        yield entorno


def test_crear_responde_201_con_etag_location_y_no_store(e: Entorno) -> None:
    respuesta = e.crear(tasa_dias=2)
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["fecha_quiebre_estimada"] == "2026-11-12" and cuerpo["dias_restantes"] == 12
    assert cuerpo["actualizado_por"] == {"id": str(CARMEN), "nombre": "Carmen"}
    assert respuesta.headers["ETag"] == '"v1"' and respuesta.headers["Cache-Control"] == "no-store"
    assert respuesta.headers["Location"] == f"{RUTA}/{cuerpo['id']}"


@pytest.mark.parametrize(
    ("cuerpo", "campo", "tipo"),
    [
        ({"nombre_libre": "x" * 61}, "nombre_libre", "string_too_long"),
        ({"nombre_libre": "Pañal\nadulto"}, "nombre_libre", "value_error"),
        ({"nombre_libre": None}, "nombre_libre", "producto_o_nombre"),
        ({"producto_id": str(uuid.uuid4())}, "nombre_libre", "producto_o_nombre"),
        ({"grupo_id": str(GRUPO)}, "grupo_id", "extra_forbidden"),
        ({"unidad": "caja"}, "unidad", "enum"),
        ({"stock_unidades": 100_000, "tasa_unidades": 1, "tasa_dias": 90}, "stock_unidades", "cobertura_maxima"),
    ],
)
def test_crear_422_nombra_el_campo_sin_el_valor(e: Entorno, cuerpo: dict[str, Any], campo: str, tipo: str) -> None:
    respuesta = e.crear(**cuerpo)
    assert respuesta.status_code == 422
    errores = respuesta.json()["errores"]
    assert any(x["campo"] == campo and x["tipo"] == tipo for x in errores), errores
    assert "adulto" not in respuesta.text.replace("Pañal adulto M", "") and "x" * 61 not in respuesta.text
    assert e.repo.perfiles == {}


def test_la_app_puede_enviar_sobre_y_la_api_acepta_ml_y_g(e: Entorno) -> None:
    for unidad in ("unidad", "sobre", "ml", "g"):
        assert e.crear(unidad=unidad).json()["unidad"] == unidad


def test_patch_412_trae_actual_y_quien_guardo(e: Entorno) -> None:
    perfil = e.crear().json()
    ruta = f"{RUTA}/{perfil['id']}"
    assert e.cliente.patch(ruta, json={"stock_unidades": 18}, headers={"If-Match": '"v1"'}).status_code == 200
    conflicto = e.cliente.patch(ruta, json={"stock_unidades": 20}, headers={"If-Match": '"v1"'})
    assert conflicto.status_code == 412
    assert conflicto.headers["ETag"] == '"v2"' and conflicto.headers["Cache-Control"] == "no-store"
    cuerpo = conflicto.json()
    assert cuerpo["type"] == "/errores/version-desactualizada"
    assert cuerpo["actual"]["stock_unidades"] == 18 and cuerpo["actual"]["actualizado_por"]["nombre"] == "Carmen"
    assert cuerpo["detail"].startswith("Carmen ")


@pytest.mark.parametrize("cabeceras", [{}, {"If-Match": ""}, {"If-Match": "*"}])
def test_patch_sin_if_match_es_428(e: Entorno, cabeceras: dict[str, str]) -> None:
    perfil = e.crear().json()
    respuesta = e.cliente.patch(f"{RUTA}/{perfil['id']}", json={"dias_aviso": 3}, headers=cabeceras)
    assert respuesta.status_code == 428 and respuesta.json()["type"] == "/errores/falta-version"


@pytest.mark.parametrize(
    ("cuerpo", "tipo"),
    [({}, "cuerpo_vacio"), ({"tasa_dias": None}, "null_no_admitido"), ({"producto_id": str(uuid.uuid4())},
                                                                          "extra_forbidden")],
)
def test_patch_cuerpo_invalido_es_422(e: Entorno, cuerpo: dict[str, Any], tipo: str) -> None:
    perfil = e.crear().json()
    respuesta = e.cliente.patch(f"{RUTA}/{perfil['id']}", json=cuerpo, headers={"If-Match": '"v1"'})
    assert respuesta.status_code == 422 and respuesta.json()["errores"][0]["tipo"] == tipo


def test_desactivar_activar_eliminar_y_filtro_todos(e: Entorno) -> None:
    perfil = e.crear().json()
    ruta = f"{RUTA}/{perfil['id']}"
    assert e.cliente.post(ruta + "/desactivar").json()["activo"] is False
    assert e.cliente.post(ruta + "/desactivar").json()["etag"] == '"v2"'
    inactivo = e.cliente.patch(ruta, json={"dias_aviso": 1}, headers={"If-Match": '"v2"'})
    assert inactivo.status_code == 409 and inactivo.json()["type"] == "/errores/perfil-inactivo"
    assert e.cliente.get(RUTA).json()["items"] == []
    assert len(e.cliente.get(RUTA, params={"activo": "todos"}).json()["items"]) == 1
    assert len(e.cliente.get(RUTA, params={"activo": "false"}).json()["items"]) == 1
    assert e.cliente.get(RUTA, params={"activo": "quizas"}).status_code == 422
    assert e.cliente.post(ruta + "/activar").json()["activo"] is True
    borrado = e.cliente.delete(ruta)
    assert borrado.status_code == 204 and borrado.content == b""
    assert e.cliente.get(ruta).status_code == 404
    assert e.cliente.get(f"{RUTA}/no-es-uuid").status_code == 404


def test_cursor(e: Entorno) -> None:
    for stock in (40, 8, 24):
        e.crear(stock_unidades=stock)
    primera = e.cliente.get(RUTA, params={"limite": 2}).json()
    assert [p["stock_unidades"] for p in primera["items"]] == [8, 24]
    segunda = e.cliente.get(RUTA, params={"limite": 2, "cursor": primera["siguiente_cursor"]}).json()
    assert [p["stock_unidades"] for p in segunda["items"]] == [40] and segunda["siguiente_cursor"] is None
    assert e.cliente.get(RUTA, params={"cursor": "%%%"}).status_code == 422
    assert e.cliente.get(RUTA, params={"limite": 101}).status_code == 422


def test_nombre_libre_no_aparece_en_los_logs(e: Entorno, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    marca = f"Toallitas {uuid.uuid4().hex[:8]}"
    perfil = e.crear(nombre_libre=marca).json()
    ruta = f"{RUTA}/{perfil['id']}"
    e.cliente.patch(ruta, json={"nombre_libre": marca + " 2"}, headers={"If-Match": '"v1"'})
    e.cliente.patch(ruta, json={"nombre_libre": marca + " 3"}, headers={"If-Match": '"v1"'})  # 412
    e.crear(nombre_libre=marca + "\nx")  # 422
    e.crear(nombre_libre=marca + "y" * 60)  # 422
    for registro in caplog.records:
        assert marca not in registro.getMessage() and marca not in str(registro.__dict__)
    assert marca not in e.logs.getvalue()
    assert e.logs.getvalue()  # la línea de la petición sí se registró
    assert all(marca not in repr(x) for x in e.auditoria.entradas)

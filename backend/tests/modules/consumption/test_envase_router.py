"""MATU-60 · unidades_por_envase en las rutas del perfil, con dobles y sin base (RF-14, decisión 121).

Crear con y sin el dato, el PATCH que lo fija y que lo borra con null (la única excepción a
null_no_admitido), que cambiarlo no toca la medición, el 422 fuera de rango sin repetir el valor y que sigue
exigiendo If-Match. Lo mismo contra PostgreSQL está en test_lista_api.py.
"""

from typing import Any

import pytest

from tests.modules.consumption.test_consumo_router import RUTA, Entorno, e  # noqa: F401

pytestmark = pytest.mark.rf("RF-14")

V1 = '"v1"'


def test_crear_sin_envase_lo_devuelve_null_y_con_envase_lo_guarda(e: Entorno) -> None:  # noqa: F811
    assert e.crear().json()["unidades_por_envase"] is None
    assert e.crear(nombre_libre="Toallitas", unidades_por_envase=None).json()["unidades_por_envase"] is None
    creado = e.crear(nombre_libre="Crema", unidad="ml", unidades_por_envase=250)
    assert creado.status_code == 201 and creado.json()["unidades_por_envase"] == 250


def test_patch_fija_el_envase_y_null_lo_borra(e: Entorno) -> None:  # noqa: F811
    perfil = e.crear().json()
    ruta = f"{RUTA}/{perfil['id']}"
    puesto = e.cliente.patch(ruta, json={"unidades_por_envase": 20}, headers={"If-Match": V1})
    assert puesto.status_code == 200, puesto.text
    cuerpo = puesto.json()
    assert cuerpo["unidades_por_envase"] == 20 and cuerpo["etag"] == '"v2"' and puesto.headers["ETag"] == '"v2"'
    # Cambiar solo el envase no vuelve a anclar la medición ni la fecha
    assert (cuerpo["stock_medido_en"], cuerpo["fecha_quiebre_estimada"]) == (
        perfil["stock_medido_en"],
        perfil["fecha_quiebre_estimada"],
    )
    # Otro campo sin el envase lo conserva
    otro = e.cliente.patch(ruta, json={"dias_aviso": 3}, headers={"If-Match": '"v2"'})
    assert otro.json()["unidades_por_envase"] == 20
    borrado = e.cliente.patch(ruta, json={"unidades_por_envase": None}, headers={"If-Match": '"v3"'})
    assert borrado.status_code == 200 and borrado.json()["unidades_por_envase"] is None
    assert borrado.json()["etag"] == '"v4"'


@pytest.mark.parametrize(
    ("valor", "tipo"),
    [(0, "greater_than_equal"), (10_001, "less_than_equal"), (2.5, "int_from_float"), ("muchos", "int_parsing")],
)
def test_envase_fuera_de_rango_es_422_sin_el_valor(e: Entorno, valor: Any, tipo: str) -> None:  # noqa: F811
    perfil = e.crear().json()
    respuesta = e.cliente.patch(f"{RUTA}/{perfil['id']}", json={"unidades_por_envase": valor}, headers={"If-Match": V1})
    assert respuesta.status_code == 422
    [error] = respuesta.json()["errores"]
    assert (error["campo"], error["tipo"]) == ("unidades_por_envase", tipo)
    assert str(valor) not in respuesta.text.replace(respuesta.json()["request_id"] or "", "")
    creado = e.crear(nombre_libre="Toallitas", unidades_por_envase=valor)
    assert creado.status_code == 422 and creado.json()["errores"][0]["campo"] == "unidades_por_envase"
    # Nada cambió: sigue en la versión 1 y sin envase
    assert e.cliente.get(f"{RUTA}/{perfil['id']}").json()["etag"] == V1


def test_el_null_sigue_rechazado_en_los_demas_campos_aunque_venga_el_envase(e: Entorno) -> None:  # noqa: F811
    perfil = e.crear().json()
    respuesta = e.cliente.patch(
        f"{RUTA}/{perfil['id']}", json={"unidades_por_envase": None, "tasa_dias": None}, headers={"If-Match": V1}
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["errores"][0] == {
        "campo": "tasa_dias",
        "mensaje": "no admite null: omite el campo si no cambia",
        "tipo": "null_no_admitido",
    }


@pytest.mark.parametrize("cabeceras", [{}, {"If-Match": "*"}])
def test_el_envase_tambien_exige_if_match(e: Entorno, cabeceras: dict[str, str]) -> None:  # noqa: F811
    perfil = e.crear().json()
    ruta = f"{RUTA}/{perfil['id']}"
    respuesta = e.cliente.patch(ruta, json={"unidades_por_envase": 20}, headers=cabeceras)
    assert respuesta.status_code == 428
    conflicto = e.cliente.patch(ruta, json={"unidades_por_envase": 20}, headers={"If-Match": '"v9"'})
    assert conflicto.status_code == 412 and conflicto.json()["actual"]["unidades_por_envase"] is None

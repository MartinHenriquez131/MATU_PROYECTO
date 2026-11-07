"""MATU-51 · docs/api/openapi.json coincide con la API en «Compré» y «Me quedan N». Sin base.

Si una de las rutas cambia sin volver a exportar openapi.json, falla. Fija además lo que pidió el analista:
la cantidad viaja solo en el cuerpo (condición 11), el cuerpo no admite fecha (condición 3), no hay ruta de
historial de compras (condición 4) y los topes del ajuste de Jorge del 07-11 (decisión 137).
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-11")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
BASE = "/v1/personas-cuidadas/{persona_id}/consumo"
COMPRE = BASE + "/{perfil_id}/reponer"
QUEDAN = BASE + "/{perfil_id}/recontar"
RUTAS = (COMPRE, QUEDAN)
COMPONENTES = ("SolicitudReposicion", "SolicitudRecuento", "InsumoPorAcabarseVista")


@pytest.fixture(scope="module")
def app() -> Any:
    return crear_app(io.StringIO())


def test_openapi_json_coincide_con_la_api(app: Any) -> None:
    esquema = app.openapi()
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    for ruta in RUTAS:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in COMPONENTES:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre]


def test_las_rutas_no_estan_en_el_propuesto() -> None:
    texto = (DOCS / "propuestos" / "app-familia.openapi.yaml").read_text(encoding="utf-8")
    rutas = {linea.strip().rstrip(":") for linea in texto.splitlines() if linea.startswith("  /v1/")}
    assert rutas.isdisjoint(RUTAS)


@pytest.mark.parametrize("ruta", RUTAS)
def test_solo_post_con_if_match_y_sin_parametros_de_consulta(app: Any, ruta: str) -> None:
    operaciones = app.openapi()["paths"][ruta]
    assert set(operaciones) == {"post"}
    operacion = operaciones["post"]
    assert {p["in"] for p in operacion["parameters"]} == {"path", "header"}
    assert {p["name"] for p in operacion["parameters"] if p["in"] == "path"} == {"persona_id", "perfil_id"}
    assert operacion["requestBody"]["required"] is True
    assert {"200", "401", "403", "404", "409", "412", "422", "428"} <= set(operacion["responses"])
    respuesta = operacion["responses"]["200"]["content"]["application/json"]["schema"]
    assert respuesta == {"$ref": "#/components/schemas/InsumoPorAcabarseVista"}


def test_los_topes_de_la_compra_y_del_recuento(app: Any) -> None:
    esquemas = app.openapi()["components"]["schemas"]
    compra = esquemas["SolicitudReposicion"]
    assert set(compra["properties"]) == {"envases", "cantidad"} and compra["additionalProperties"] is False
    [envases] = [t for t in compra["properties"]["envases"]["anyOf"] if t.get("type") == "integer"]
    [cantidad] = [t for t in compra["properties"]["cantidad"]["anyOf"] if t.get("type") == "integer"]
    assert (envases["minimum"], envases["maximum"]) == (1, 99)
    assert (cantidad["minimum"], cantidad["maximum"]) == (1, 10_000)
    # Decisión 147: «Ya lo resolví» acepta lo mismo, con los mismos topes
    assert esquemas["SolicitudResolver"]["properties"] == compra["properties"]
    assert esquemas["SolicitudResolver"].get("required", []) == []
    recuento = esquemas["SolicitudRecuento"]
    assert recuento["required"] == ["stock_unidades"] and recuento["additionalProperties"] is False
    stock = recuento["properties"]["stock_unidades"]
    assert (stock["minimum"], stock["maximum"]) == (0, 100_000)


def test_no_hay_ruta_de_historial_de_compras(app: Any) -> None:
    rutas = app.openapi()["paths"]
    assert not [r for r in rutas if "reposicion" in r or "compras" in r]
    # Ninguna respuesta del contrato expone la tabla reposicion
    assert "reposicion" not in {k.lower() for k in app.openapi()["components"]["schemas"]}

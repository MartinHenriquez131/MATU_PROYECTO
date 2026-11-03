"""MATU-37 · docs/api/openapi.json coincide con la API en «Se acaban pronto» y las alertas. Sin base.

Si una de estas rutas cambia sin volver a exportar openapi.json, falla. Y las rutas ya no están en el
contrato propuesto. Además fija el orden de registro: las rutas fijas antes que {perfil_id}.
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-12")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
BASE = "/v1/personas-cuidadas/{persona_id}/consumo"
RUTAS = (
    BASE + "/por-acabarse",
    BASE + "/alertas",
    BASE + "/alertas/{alerta_id}/descartar",
    BASE + "/{perfil_id}/resolver",
)
COMPONENTES = (
    "InsumoPorAcabarseVista",
    "ListaPorAcabarse",
    "AlertaVista",
    "ListaAlertas",
    "SolicitudResolver",
    "EstadoAlerta",
)


@pytest.fixture(scope="module")
def app() -> Any:
    return crear_app(io.StringIO())


def test_openapi_json_coincide_con_la_api_en_las_alertas(app: Any) -> None:
    esquema = app.openapi()
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    for ruta in RUTAS:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in COMPONENTES:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre]


def test_las_rutas_implementadas_salen_del_propuesto() -> None:
    texto = (DOCS / "propuestos" / "app-familia.openapi.yaml").read_text(encoding="utf-8")
    rutas = {linea.strip().rstrip(":") for linea in texto.splitlines() if linea.startswith("  /v1/")}
    assert rutas.isdisjoint(RUTAS)


def test_las_rutas_fijas_van_antes_que_perfil_id(app: Any) -> None:
    # El orden de paths en el esquema es el de registro (app.routes agrupa los routers incluidos)
    orden = list(app.openapi()["paths"])
    assert orden.index(BASE + "/por-acabarse") < orden.index(BASE + "/{perfil_id}")
    assert orden.index(BASE + "/alertas") < orden.index(BASE + "/{perfil_id}")


def test_el_item_trae_avisando_y_alerta_id_y_cantidad_es_opcional(app: Any) -> None:
    esquemas = app.openapi()["components"]["schemas"]
    assert {"avisando", "alerta_id"} <= set(esquemas["InsumoPorAcabarseVista"]["required"])
    resolver = esquemas["SolicitudResolver"]
    assert resolver.get("required", []) == [] and resolver["additionalProperties"] is False
    [entero] = [t for t in resolver["properties"]["cantidad"]["anyOf"] if t.get("type") == "integer"]
    assert (entero["minimum"], entero["maximum"]) == (1, 9999)


def test_resolver_exige_if_match_y_declara_412_y_428(app: Any) -> None:
    operacion = app.openapi()["paths"][BASE + "/{perfil_id}/resolver"]["post"]
    assert {"412", "428"} <= set(operacion["responses"])
    [cabecera] = [p for p in operacion["parameters"] if p["in"] == "header" and p["name"] == "If-Match"]
    assert "etag" in cabecera["description"]
    propiedades = operacion["responses"]["412"]["content"]["application/problem+json"]["schema"]["properties"]
    assert propiedades["actual"]["$ref"] == "#/components/schemas/PerfilConsumoVista"

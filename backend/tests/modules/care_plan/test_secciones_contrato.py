"""MATU-50 · El OpenAPI de la ficha ampliada declara lo del contrato propuesto (ADR-028, RF-03). Sin base.

Y docs/api/openapi.json coincide con lo que expone la API en las rutas que tocó MATU-50: si una cambia,
hay que volver a exportarlo (docs/api/README.md). Contrato: docs/api/propuestos/ficha-ampliada.openapi.yaml.
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-03")

RUTA_SECCION = "/v1/personas-cuidadas/{persona_id}/plan/secciones/{seccion}"
RUTAS = (
    RUTA_SECCION,
    "/v1/personas-cuidadas/{persona_id}/plan/ficha",
    "/v1/personas-cuidadas/{persona_id}/plan/accesos-relevo",
    "/v1/relevo/ficha",
    "/v1/personas-cuidadas/{persona_id}/plan/aperturas",
)
ESQUEMAS = (
    "SeccionComplementaria", "SolicitudSeccion", "EstadoSeccionVista", "SeccionGuardadaVista", "FichaVista",
    "SolicitudAccesoVista", "AccesoCreadoVista", "AccesoResumenVista", "FichaRelevoVista", "SeccionRelevoVista",
    "AperturaVista",
)
SEIS = ["quien_es", "preferencias", "alimentacion", "movilidad", "comunicacion", "remedios"]
ARCHIVO = Path(__file__).resolve().parents[4] / "docs" / "api" / "openapi.json"


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api(esquema: dict[str, Any]) -> None:
    exportado = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    for ruta in RUTAS:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in ESQUEMAS:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre], nombre


def test_las_seis_secciones_en_el_orden_del_contrato(esquema: dict[str, Any]) -> None:
    assert esquema["components"]["schemas"]["SeccionComplementaria"]["enum"] == SEIS
    parametros = {p["name"]: p for p in esquema["paths"][RUTA_SECCION]["put"]["parameters"]}
    assert parametros["seccion"]["schema"]["enum"] == SEIS


def test_put_y_delete_de_una_seccion(esquema: dict[str, Any]) -> None:
    put = esquema["paths"][RUTA_SECCION]["put"]
    delete = esquema["paths"][RUTA_SECCION]["delete"]
    assert (put["operationId"], delete["operationId"]) == ("guardarSeccionFicha", "quitarSeccionFicha")
    assert set(put["responses"]) == {"200", "201", "401", "403", "404", "412", "422", "428", "500", "503"}
    assert set(delete["responses"]) == {"204", "401", "403", "404", "412", "422", "428", "500", "503"}
    assert {p["name"] for p in put["parameters"]} >= {"If-Match", "If-None-Match"}
    # El contrato declara solo If-Match en el DELETE; If-None-Match se rechaza con 422 sin declararse
    assert "If-None-Match" not in {p["name"] for p in delete["parameters"]}
    assert put["x-matu-auditoria"] == "plan.editar" and delete["x-matu-auditoria"] == "plan.quitar_seccion"
    problema = put["responses"]["412"]["content"]["application/problem+json"]["schema"]
    assert problema["properties"]["actual"]["anyOf"] == [
        {"$ref": "#/components/schemas/EstadoSeccionVista"}, {"type": "null"}
    ]
    texto = esquema["components"]["schemas"]["SolicitudSeccion"]["properties"]["texto"]
    assert (texto["minLength"], texto["maxLength"]) == (1, 800)


def test_cambios_aditivos_y_el_campo_deprecado(esquema: dict[str, Any]) -> None:
    componentes = esquema["components"]["schemas"]
    assert "secciones" in componentes["FichaVista"]["required"]
    assert set(componentes["EstadoSeccionVista"]["required"]) == {"texto", "etag", "actualizado_por", "actualizado_en"}
    solicitud = componentes["SolicitudAccesoVista"]
    assert solicitud["properties"]["campos"]["deprecated"] is True
    assert "campos" not in solicitud["required"] and "secciones_adicionales" not in solicitud["required"]
    assert solicitud["properties"]["secciones_adicionales"]["maxItems"] == 6
    for nombre in ("AccesoCreadoVista", "AccesoResumenVista"):
        assert {"campos", "secciones_adicionales"} <= set(componentes[nombre]["required"])
    assert "secciones" in componentes["FichaRelevoVista"]["required"]
    assert set(componentes["SeccionRelevoVista"]["properties"]) == {"tipo", "texto"}
    assert "secciones" not in componentes["AperturaVista"]["required"]

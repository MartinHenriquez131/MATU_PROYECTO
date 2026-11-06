"""MATU-41 · docs/api/openapi.json coincide con lo que expone la API en /v1/yo/avisos (RF-39). Sin base.

Si la ruta o su esquema cambian, hay que volver a exportarlos (docs/api/README.md, decisión 111).
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-39")

RUTA = "/v1/yo/avisos"
ARCHIVO = Path(__file__).resolve().parents[4] / "docs" / "api" / "openapi.json"


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api_en_yo_avisos(esquema: dict[str, Any]) -> None:
    exportado = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    assert exportado["paths"][RUTA] == esquema["paths"][RUTA], "vuelve a exportar /v1/yo/avisos"
    nombre = "PreferenciaAvisosVista"
    assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre]


def test_contrato_de_yo_avisos(esquema: dict[str, Any]) -> None:
    ruta = esquema["paths"][RUTA]
    assert set(ruta) == {"get", "put"}
    assert ruta["get"]["operationId"] == "leerPreferenciaAvisos"
    assert ruta["put"]["operationId"] == "guardarPreferenciaAvisos"
    assert set(ruta["get"]["responses"]) == {"200", "401"}
    assert set(ruta["put"]["responses"]) == {"200", "401", "422"}
    # Sin parámetros: siempre la del usuario autenticado
    assert "parameters" not in ruta["get"] and "parameters" not in ruta["put"]
    vista = esquema["components"]["schemas"]["PreferenciaAvisosVista"]
    assert set(vista["properties"]) == {"correo", "push"} and set(vista["required"]) == {"correo", "push"}
    assert vista["additionalProperties"] is False
    assert {p["type"] for p in vista["properties"].values()} == {"boolean"}

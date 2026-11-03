"""MATU-45 · docs/api/openapi.json coincide con lo que expone la API en /plan/aperturas (RF-08). Sin base.

Si la ruta o sus esquemas cambian, hay que volver a exportarlos (docs/api/README.md).
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-08")

RUTA = "/v1/personas-cuidadas/{persona_id}/plan/aperturas"
ESQUEMAS = ("ListaAperturasVista", "AperturaVista", "AccesoDeAperturaVista", "TipoApertura")
ARCHIVO = Path(__file__).resolve().parents[4] / "docs" / "api" / "openapi.json"


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api_en_aperturas(esquema: dict[str, Any]) -> None:
    exportado = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    assert exportado["paths"][RUTA] == esquema["paths"][RUTA], "vuelve a exportar /plan/aperturas"
    for nombre in ESQUEMAS:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre]


def test_contrato_de_aperturas(esquema: dict[str, Any]) -> None:
    get = esquema["paths"][RUTA]["get"]
    assert get["operationId"] == "listarAperturasRelevo"
    assert set(get["responses"]) == {"200", "401", "404", "422"}
    assert get["responses"]["200"]["headers"]["Cache-Control"]["schema"]["const"] == "no-store"
    parametros = {p["name"]: p for p in get["parameters"]}
    assert parametros["limite"]["schema"] == {
        "type": "integer", "maximum": 100, "minimum": 1, "default": 20, "title": "Limite"
    }
    tipo = esquema["components"]["schemas"]["TipoApertura"]
    assert tipo["enum"] == ["presentacion", "apertura", "pin_incorrecto", "bloqueo"]
    acceso = esquema["components"]["schemas"]["AccesoDeAperturaVista"]
    assert set(acceso["properties"]) == {"id", "nombre_relevo"}  # nunca el teléfono

"""MATU-13 · El OpenAPI del PUT de la ficha declara el 412 y el 428 como el contrato (RF-04). Sin base.

Y docs/api/openapi.json coincide con lo que expone la API en las rutas de la ficha: si una cambia,
hay que volver a exportarlo (docs/api/README.md).
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-04")

RUTA_CAMPO = "/v1/personas-cuidadas/{persona_id}/plan/ficha/{campo}"
RUTAS_FICHA = ("/v1/personas-cuidadas/{persona_id}/plan/ficha", RUTA_CAMPO)
ARCHIVO = Path(__file__).resolve().parents[4] / "docs" / "api" / "openapi.json"


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_412_declara_problema_version_con_actual(esquema: dict[str, Any]) -> None:
    respuesta = esquema["paths"][RUTA_CAMPO]["put"]["responses"]["412"]
    contenido = respuesta["content"]["application/problem+json"]
    propiedades = contenido["schema"]["properties"]
    assert propiedades["type"]["const"] == "/errores/version-desactualizada"
    assert propiedades["status"]["const"] == 412
    assert propiedades["actual"]["$ref"] == "#/components/schemas/EstadoCampoVista"
    assert {"campo", "actual", "type", "title", "status", "detail", "errores", "request_id"} <= set(
        contenido["schema"]["required"]
    )
    assert contenido["example"]["actual"]["etag"] == '"v4"'
    assert set(respuesta["headers"]) == {"X-Request-ID", "ETag", "Cache-Control"}
    # El $ref resuelve: EstadoCampoVista es nullable en sus cuatro campos
    estado = esquema["components"]["schemas"]["EstadoCampoVista"]
    assert set(estado["properties"]) == {"texto", "etag", "actualizado_por", "actualizado_en"}


def test_428_declara_falta_version(esquema: dict[str, Any]) -> None:
    respuesta = esquema["paths"][RUTA_CAMPO]["put"]["responses"]["428"]
    contenido = respuesta["content"]["application/problem+json"]
    assert contenido["schema"]["properties"]["type"]["const"] == "/errores/falta-version"
    assert contenido["schema"]["properties"]["status"]["const"] == 428
    assert contenido["example"]["type"] == "/errores/falta-version"
    assert "X-Request-ID" in respuesta["headers"]


@pytest.mark.parametrize("codigo", ["200", "201"])
def test_guardado_declara_etag_y_no_store(esquema: dict[str, Any], codigo: str) -> None:
    cabeceras = esquema["paths"][RUTA_CAMPO]["put"]["responses"][codigo]["headers"]
    assert set(cabeceras) == {"X-Request-ID", "ETag", "Cache-Control"}
    assert cabeceras["Cache-Control"]["schema"]["const"] == "no-store"


def test_cabeceras_de_precondicion_documentadas(esquema: dict[str, Any]) -> None:
    put = esquema["paths"][RUTA_CAMPO]["put"]
    parametros = {p["name"]: p for p in put["parameters"]}
    assert "428" in parametros["If-Match"]["description"]
    assert "422" in parametros["If-None-Match"]["description"]
    assert put["description"].startswith("Escribe **un** campo")


def test_openapi_json_coincide_con_la_api_en_la_ficha(esquema: dict[str, Any]) -> None:
    exportado = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    for ruta in RUTAS_FICHA:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in ("EstadoCampoVista", "AutorVista", "CampoGuardadoVista", "FichaVista", "SolicitudCampo"):
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre]
    # Las rutas del relevo siguen en propuestos/
    assert not any("relevo" in ruta for ruta in exportado["paths"])

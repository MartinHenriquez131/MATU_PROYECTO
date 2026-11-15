"""MATU-106 · docs/api/openapi.json coincide con lo que expone la API en la presentación y el canje (RF-06). Sin base.

Si una de las dos rutas o sus esquemas cambian, hay que volver a exportarlos (docs/api/README.md, decisión 406).
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-06")

PRESENTACION = "/v1/relevo/presentacion"
CANJE = "/v1/relevo/canje"
ESQUEMAS = ("SolicitudPresentacionVista", "SolicitudCanjeVista", "PresentacionVista")
CABECERAS = {"X-Request-ID", "Cache-Control", "Referrer-Policy", "X-Robots-Tag"}
DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
ARCHIVO = DOCS / "openapi.json"
PROPUESTO = DOCS / "propuestos" / "relevo.openapi.yaml"


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api_en_presentacion_y_canje(esquema: dict[str, Any]) -> None:
    exportado = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    for ruta in (PRESENTACION, CANJE):
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in ESQUEMAS:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre], nombre


def test_las_rutas_salieron_del_propuesto() -> None:
    texto = PROPUESTO.read_text(encoding="utf-8")
    assert f"  {PRESENTACION}:" not in texto
    assert f"  {CANJE}:" not in texto


def test_contrato_de_la_presentacion(esquema: dict[str, Any]) -> None:
    post = esquema["paths"][PRESENTACION]["post"]
    assert post["operationId"] == "presentarRelevo"
    assert post["security"] == []
    respuestas = post["responses"]
    assert set(respuestas) == {"200", "410", "422", "423", "429", "503"}
    for codigo, respuesta in respuestas.items():
        assert CABECERAS <= set(respuesta["headers"]), codigo
        assert respuesta["headers"]["Cache-Control"]["schema"]["const"] == "no-store"
    exito = respuestas["200"]["content"]["application/json"]["schema"]
    assert exito == {"$ref": "#/components/schemas/PresentacionVista"}
    # Decisión 28: antes del PIN solo salen los dos nombres de pila
    presentacion = esquema["components"]["schemas"]["PresentacionVista"]
    assert set(presentacion["properties"]) == {"nombre_pila_comparte", "nombre_pila"}
    assert presentacion["additionalProperties"] is False
    assert esquema["components"]["schemas"]["SolicitudPresentacionVista"]["required"] == ["token"]


def test_contrato_del_canje(esquema: dict[str, Any]) -> None:
    post = esquema["paths"][CANJE]["post"]
    assert post["operationId"] == "canjearRelevo"
    assert post["security"] == []
    respuestas = post["responses"]
    assert set(respuestas) == {"204", "401", "410", "422", "423", "429", "503"}
    for codigo, respuesta in respuestas.items():
        assert CABECERAS <= set(respuesta["headers"]), codigo
    assert "content" not in respuestas["204"]
    assert "Set-Cookie" in respuestas["204"]["headers"]
    pin = respuestas["401"]["content"]["application/problem+json"]["schema"]["properties"]
    assert pin["type"]["const"] == "/errores/pin-incorrecto"
    assert pin["intentos_restantes"] == {
        "type": "integer", "minimum": 1, "maximum": 4, "description": "Intentos que quedan antes del bloqueo"
    }
    tipos_410 = respuestas["410"]["content"]["application/problem+json"]["schema"]["properties"]["type"]["enum"]
    assert set(tipos_410) == {
        "/errores/relevo-vencido",
        "/errores/relevo-revocado",
        "/errores/relevo-no-disponible",
        "/errores/relevo-pausado",
    }
    solicitud = esquema["components"]["schemas"]["SolicitudCanjeVista"]
    assert solicitud["properties"]["pin"]["pattern"] == "^[0-9]{4}$"


@pytest.mark.parametrize("ruta", [PRESENTACION, CANJE])
def test_el_limite_declara_retry_after(esquema: dict[str, Any], ruta: str) -> None:
    cabecera = esquema["paths"][ruta]["post"]["responses"]["429"]["headers"]["Retry-After"]
    assert cabecera["schema"] == {"type": "integer", "minimum": 1, "maximum": 3600}


@pytest.mark.parametrize("ruta", [PRESENTACION, CANJE])
def test_las_cabeceras_declaradas_son_las_que_responde_la_api(esquema: dict[str, Any], ruta: str) -> None:
    """Un cuerpo que no es JSON responde 422 antes del límite y de la base (decisión 114): sin Redis ni base."""
    declaradas = esquema["paths"][ruta]["post"]["responses"]["422"]["headers"]
    with TestClient(crear_app(io.StringIO())) as cliente:
        respuesta = cliente.post(ruta, content=b"{no-es-json", headers={"Content-Type": "application/json"})
    assert respuesta.status_code == 422
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.json()["type"] == "/errores/validacion"
    for nombre in CABECERAS:
        assert nombre in respuesta.headers, nombre
        const = declaradas[nombre]["schema"].get("const")
        if const is not None:
            assert respuesta.headers[nombre] == const, nombre

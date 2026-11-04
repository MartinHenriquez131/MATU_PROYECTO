"""MATU-38 · docs/api/openapi.json coincide con la API en las rutas de la sesión y los dispositivos, y
esas rutas ya no están en propuestos/app-familia.openapi.yaml (docs/api/README.md). Sin base (RF-37)."""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-37")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
RUTAS = (
    "/v1/sesiones",
    "/v1/sesiones/renovar",
    "/v1/sesiones/cerrar",
    "/v1/dispositivos",
    "/v1/dispositivos/{dispositivo_id}",
    "/v1/dispositivos/actual/push",
)
COMPONENTES = ("SesionRespuesta", "SolicitudSesion", "DispositivoVista", "ListaDispositivos", "SolicitudPush")


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api_en_la_sesion(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    for ruta in RUTAS:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in COMPONENTES:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre]


def test_las_rutas_implementadas_salen_del_propuesto() -> None:
    # Sin PyYAML (no es dependencia del backend): las rutas son las claves de 2 espacios bajo paths
    lineas = (DOCS / "propuestos" / "app-familia.openapi.yaml").read_text(encoding="utf-8").splitlines()
    rutas = {linea.strip().rstrip(":") for linea in lineas if linea.startswith("  /v1/")}
    # Desde MATU-37 el propuesto ya no tiene rutas: todas pasaron a openapi.json
    assert not set(RUTAS) & rutas


def test_la_api_declara_los_codigos_del_contrato(esquema: dict[str, Any]) -> None:
    codigos = {
        ("/v1/sesiones", "post"): {"200", "401", "422", "429", "503"},
        ("/v1/sesiones/renovar", "post"): {"200", "401", "422"},
        ("/v1/sesiones/cerrar", "post"): {"204", "422"},
        ("/v1/dispositivos", "get"): {"200", "401"},
        ("/v1/dispositivos/{dispositivo_id}", "delete"): {"204", "401", "404"},
        ("/v1/dispositivos/actual/push", "put"): {"204", "401", "404", "422"},
        ("/v1/dispositivos/actual/push", "delete"): {"204", "401", "404"},
    }
    for (ruta, metodo), esperados in codigos.items():
        assert esperados <= set(esquema["paths"][ruta][metodo]["responses"]), (ruta, metodo)
    # El push_token es solo de escritura y nunca sale en la vista de un dispositivo
    assert "push_token" not in esquema["components"]["schemas"]["DispositivoVista"]["properties"]
    assert esquema["components"]["schemas"]["SolicitudPush"]["properties"]["push_token"]["writeOnly"] is True

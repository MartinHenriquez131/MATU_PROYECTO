"""MATU-57 · docs/api/openapi.json coincide con la API en la recuperación y la cuenta. Sin base (RF-37)."""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-37")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
RUTAS = (
    "/v1/recuperacion/codigo",
    "/v1/recuperacion/contrasena",
    "/v1/cuenta",
    "/v1/cuenta/celular/codigo",
    "/v1/cuenta/celular/verificar",
)
COMPONENTES = ("SolicitudCodigoRecuperacion", "SolicitudCambioContrasena", "SolicitudVerificarCelular", "CuentaVista")


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    for ruta in RUTAS:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in COMPONENTES:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre]


def test_la_api_declara_los_codigos_del_contrato(esquema: dict[str, Any]) -> None:
    codigos = {
        ("/v1/recuperacion/codigo", "post"): {"202", "422", "503"},
        ("/v1/recuperacion/contrasena", "post"): {"204", "422", "429", "503"},
        ("/v1/cuenta", "get"): {"200", "401"},
        ("/v1/cuenta/celular/codigo", "post"): {"202", "401", "409", "429", "503"},
        ("/v1/cuenta/celular/verificar", "post"): {"204", "401", "422", "429", "503"},
    }
    for (ruta, metodo), esperados in codigos.items():
        assert esperados <= set(esquema["paths"][ruta][metodo]["responses"]), (ruta, metodo)
    # Pedir el código no tiene 429: responde igual exista o no la cuenta (decisión 84)
    assert "429" not in esquema["paths"]["/v1/recuperacion/codigo"]["post"]["responses"]
    # Nunca se pide el celular para recuperar, y la cuenta nunca lo muestra completo
    assert set(esquema["components"]["schemas"]["SolicitudCodigoRecuperacion"]["properties"]) == {"email", "canal"}
    assert "telefono" not in esquema["components"]["schemas"]["CuentaVista"]["properties"]

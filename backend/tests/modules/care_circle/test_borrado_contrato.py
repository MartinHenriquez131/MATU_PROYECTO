"""MATU-72 · docs/api/openapi.json coincide con la API en el borrado de la persona. Sin base.

Si la ruta o su esquema cambian sin volver a exportar openapi.json, falla. Además: la respuesta trae solo lo de la
decisión 152 de docs/api/README.md, sin nada de la persona, y la ruta no tiene cuerpo (decisión 149).
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-01")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
BORRADO = "/v1/personas-cuidadas/{persona_id}/borrado"


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    assert exportado["paths"][BORRADO] == esquema["paths"][BORRADO], f"vuelve a exportar {BORRADO}"
    assert exportado["components"]["schemas"]["BorradoPersona"] == esquema["components"]["schemas"]["BorradoPersona"]


def test_ruta_metodo_codigos_y_sin_cuerpo(esquema: dict[str, Any]) -> None:
    assert set(esquema["paths"][BORRADO]) == {"post"}
    borrado = esquema["paths"][BORRADO]["post"]
    assert {"200", "401", "404", "409"} <= set(borrado["responses"])
    assert "403" not in borrado["responses"]  # un recurso que no alcanza es 404, nunca 403
    assert "requestBody" not in borrado
    assert {p["name"] for p in borrado["parameters"]} == {"persona_id", "X-Grupo-Id"}


def test_la_respuesta_trae_solo_los_contadores(esquema: dict[str, Any]) -> None:
    respuesta = esquema["components"]["schemas"]["BorradoPersona"]
    campos = {"persona_id", "borrado_en", "enlaces_cortados", "autorizaciones_retiradas"}
    assert set(respuesta["properties"]) == set(respuesta["required"]) == campos
    assert respuesta["additionalProperties"] is False


def test_la_ruta_esta_en_el_readme() -> None:
    texto = (DOCS / "README.md").read_text(encoding="utf-8")
    assert "| `POST /v1/personas-cuidadas/{persona_id}/borrado` | MATU-72" in texto
    for numero in range(149, 158):
        assert f"\n{numero}. **" in texto, numero

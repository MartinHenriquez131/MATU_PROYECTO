"""MATU-107 · El contrato de C14: `permitido` en PushActualVista y el 409 push-no-permitido del PUT, exportados en
docs/api/openapi.json (decisión 404 de docs/api/README.md). La lista nunca aparece en el contrato. Sin base."""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-39")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
RUTA = "/v1/dispositivos/actual/push"


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


@pytest.fixture(scope="module")
def exportado() -> dict[str, Any]:
    return json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_push_actual_vista_suma_permitido_y_sigue_cerrada(esquema: dict[str, Any], exportado: dict[str, Any]) -> None:
    for fuente in (esquema, exportado):
        vista = fuente["components"]["schemas"]["PushActualVista"]
        assert vista["additionalProperties"] is False
        assert vista["properties"]["permitido"]["type"] == "boolean"
        assert set(vista["required"]) == {"clave_publica", "permitido", "registrado", "envio_simulado"}


def test_el_put_documenta_el_409_y_el_delete_no(esquema: dict[str, Any], exportado: dict[str, Any]) -> None:
    for fuente in (esquema, exportado):
        operaciones = fuente["paths"][RUTA]
        assert set(operaciones["put"]["responses"]) == {"204", "401", "404", "409", "422"}
        assert "push-no-permitido" in operaciones["put"]["responses"]["409"]["description"]
        assert "application/problem+json" in operaciones["put"]["responses"]["409"]["content"]
        assert "409" not in operaciones["delete"]["responses"]
        assert set(operaciones["get"]["responses"]) == {"200", "401", "404"}


def test_el_contrato_no_nombra_la_variable_ni_la_lista(exportado: dict[str, Any]) -> None:
    texto = json.dumps(exportado, ensure_ascii=False)
    assert "PUSH_CUENTAS_PERMITIDAS" not in texto and "push_cuentas_permitidas" not in texto


def test_la_decision_404_queda_en_el_readme() -> None:
    texto = (DOCS / "README.md").read_text(encoding="utf-8")
    assert "404. **C14 pasa a ser un control técnico.**" in texto

"""MATU-55 · docs/api/openapi.json coincide con la API en las rutas de «Dónde entraste», y el propuesto quedó marcado
como implementado (docs/api/README.md, decisiones 252 a 284). Sin base (RF-37)."""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-37")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
RUTAS = ("/v1/yo/ingresos", "/v1/dispositivos/actual/push", "/v1/dispositivos", "/v1/yo/avisos")
COMPONENTES = ("UltimosIngresosVista", "EventoCuentaVista", "DispositivoEventoVista", "PushActualVista",
               "DispositivoVista")
# Lo que nunca sale en un evento ni en la configuración de push (C3, decisiones 256 y 261)
PROHIBIDOS = {"id", "request_id", "actor_ref", "entidad_id", "detalle", "familia_id", "grupo_id", "ip", "plataforma",
              "push_token", "endpoint", "clave_privada", "accion"}


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api_en_donde_entraste(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    for ruta in RUTAS:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in COMPONENTES:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre], nombre


def test_codigos_y_operaciones_del_contrato(esquema: dict[str, Any]) -> None:
    ingresos = esquema["paths"]["/v1/yo/ingresos"]["get"]
    assert ingresos["operationId"] == "verIngresosPropios"
    assert set(ingresos["responses"]) == {"200", "401"}
    # Sin parámetros: ni usuario, ni fecha, ni página, ni X-Grupo-Id (C2)
    assert "parameters" not in ingresos
    push = esquema["paths"]["/v1/dispositivos/actual/push"]["get"]
    assert push["operationId"] == "verPushActual"
    assert set(push["responses"]) == {"200", "401", "404"}
    for operacion in (ingresos, push):
        assert operacion["responses"]["200"]["headers"]["Cache-Control"]["description"] == "no-store"


def test_los_esquemas_no_tienen_campos_prohibidos_y_son_cerrados(esquema: dict[str, Any]) -> None:
    esquemas = esquema["components"]["schemas"]
    for nombre in ("UltimosIngresosVista", "EventoCuentaVista", "DispositivoEventoVista", "PushActualVista"):
        assert esquemas[nombre]["additionalProperties"] is False, nombre
        assert not set(esquemas[nombre]["properties"]) & PROHIBIDOS, nombre
    assert set(esquemas["EventoCuentaVista"]["properties"]) == {"tipo", "ocurrido_en", "dispositivo"}
    assert set(esquemas["DispositivoEventoVista"]["properties"]) == {"nombre", "clase", "actual"}
    assert set(esquemas["EventoCuentaVista"]["required"]) == {"tipo", "ocurrido_en", "dispositivo"}
    assert esquemas["EventoCuentaVista"]["properties"]["tipo"]["enum"] == [
        "entraste", "saliste", "cerraste_en_dispositivo", "salida_por_seguridad", "contrasena_cambiada",
        "celular_confirmado", "codigo_recuperacion_pedido", "avisos_cambiados", "avisos_activados",
        "avisos_desactivados"]
    # C5 y C7: clase y push_activo en cada dispositivo, sin el endpoint
    vista = esquemas["DispositivoVista"]
    assert {"clase", "push_activo"} <= set(vista["required"]) and "push_token" not in vista["properties"]
    assert vista["properties"]["clase"]["enum"] == ["telefono", "computador", "otro"]


def test_el_propuesto_queda_como_implementado() -> None:
    texto = (DOCS / "propuestos" / "donde-entraste.openapi.yaml").read_text(encoding="utf-8")
    assert "version: 0.1.0-implementado" in texto
    assert "**Implementado en MATU-55 (12-11): manda `docs/api/openapi.json`.**" in texto

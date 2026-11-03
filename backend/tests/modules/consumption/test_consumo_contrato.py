"""MATU-36 · docs/api/openapi.json coincide con la API en la autorización y el consumo. Sin base.

Si una de estas rutas cambia sin volver a exportar openapi.json, falla (docs/api/README.md). Y las
rutas implementadas ya no están en el contrato propuesto.
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-10")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
RUTAS = (
    "/v1/personas-cuidadas/{persona_id}/consentimientos",
    "/v1/personas-cuidadas/{persona_id}/consumo",
    "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}",
    "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/desactivar",
    "/v1/personas-cuidadas/{persona_id}/consumo/{perfil_id}/activar",
)
COMPONENTES = (
    "SolicitudAutorizacionEntrada",
    "AutorizacionCreada",
    "SolicitudPerfil",
    "SolicitudEdicionPerfil",
    "PerfilConsumoVista",
    "ListaPerfiles",
    "ProductoResumen",
    "AutorPerfilVista",
    "UnidadConsumo",
)


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api_en_el_consumo(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    for ruta in RUTAS:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in COMPONENTES:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre]


def test_las_rutas_implementadas_salen_del_propuesto() -> None:
    lineas = (DOCS / "propuestos" / "app-familia.openapi.yaml").read_text(encoding="utf-8").splitlines()
    rutas = {linea.strip().rstrip(":") for linea in lineas if linea.startswith("  /v1/")}
    assert rutas.isdisjoint(RUTAS)


def test_el_412_trae_el_perfil_actual_con_quien_guardo(esquema: dict[str, Any]) -> None:
    respuesta = esquema["paths"][RUTAS[2]]["patch"]["responses"]["412"]
    propiedades = respuesta["content"]["application/problem+json"]["schema"]["properties"]
    assert propiedades["actual"]["$ref"] == "#/components/schemas/PerfilConsumoVista"
    assert "actualizado_por" in esquema["components"]["schemas"]["PerfilConsumoVista"]["required"]


def test_la_lista_acepta_activo_todos(esquema: dict[str, Any]) -> None:
    [activo] = [p for p in esquema["paths"][RUTAS[1]]["get"]["parameters"] if p["name"] == "activo"]
    assert activo["schema"]["enum"] == ["true", "false", "todos"] and activo["schema"]["default"] == "true"


def test_pagador_y_observador_no_tienen_campos_extra_en_el_cuerpo(esquema: dict[str, Any]) -> None:
    for nombre in ("SolicitudPerfil", "SolicitudEdicionPerfil", "SolicitudAutorizacionEntrada"):
        assert esquema["components"]["schemas"][nombre]["additionalProperties"] is False

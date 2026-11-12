"""MATU-44 · docs/api/openapi.json coincide con la API en el retiro y el estado de las autorizaciones. Sin base.

Si las rutas o sus esquemas cambian sin volver a exportar openapi.json, falla. Además: salieron del contrato
propuesto, y los esquemas traen solo lo de las decisiones 123 a 128 de docs/api/README.md.
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-02")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
RUTA = "/v1/personas-cuidadas/{persona_id}/consentimientos"
RETIRO = RUTA + "/{finalidad}/retiro"
COMPONENTES = ("AutorizacionVista", "AutorizacionesPersona", "RetiroAutorizacion", "EstadoVista",
               "SolicitudAutorizacionEntrada", "AutorizacionVistaResumen", "AutorizacionesPersonaResumen")


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    for ruta in (RUTA, RETIRO):
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in COMPONENTES:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre], nombre


def test_salieron_del_propuesto() -> None:
    texto = (DOCS / "propuestos" / "app-familia.openapi.yaml").read_text(encoding="utf-8")
    rutas = {linea.strip().rstrip(":") for linea in texto.splitlines() if linea.startswith("  /v1/")}
    assert RETIRO not in rutas and RUTA not in rutas
    for fragmento in ("x-matu-operaciones-que-se-suman:", "CambioSolicitudAutorizacionEntrada:", "YaRetirada:",
                      "AutorizacionVista:"):
        assert fragmento not in texto


def test_rutas_metodos_y_codigos(esquema: dict[str, Any]) -> None:
    assert set(esquema["paths"][RUTA]) == {"get", "post"}
    assert set(esquema["paths"][RETIRO]) == {"post"}
    assert {"200", "401", "404"} <= set(esquema["paths"][RUTA]["get"]["responses"])
    retiro = esquema["paths"][RETIRO]["post"]
    assert {"200", "401", "404", "409"} <= set(retiro["responses"])
    assert "requestBody" not in retiro
    [finalidad] = [p for p in retiro["parameters"] if p["name"] == "finalidad"]
    assert finalidad["schema"]["enum"] == ["plan_cuidado", "consumo", "despacho"]


def test_el_post_acepta_plan_cuidado(esquema: dict[str, Any]) -> None:
    entrada = esquema["components"]["schemas"]["SolicitudAutorizacionEntrada"]
    assert set(entrada["properties"]["finalidad"]["enum"]) == {"consumo", "plan_cuidado", "despacho"}  # MATU-61 (D1)


def test_la_vista_trae_solo_lo_acordado(esquema: dict[str, Any]) -> None:
    vista = esquema["components"]["schemas"]["AutorizacionVista"]
    campos = {"finalidad", "estado", "id", "calidad_otorgante", "otorgado_en", "revision_vence_en", "revocado_en",
              "borrado_en", "borrada"}
    # MATU-42 (decisión 311): solo admin y cuidador saben si la dio alguien que ya no está
    assert set(vista["properties"]) == set(vista["required"]) == campos | {"autorizo_alguien_que_ya_no_esta"}
    assert vista["additionalProperties"] is False
    assert set(esquema["components"]["schemas"]["EstadoVista"]["enum"]) == {
        "vigente", "revision_vencida", "retirada", "borrada", "sin_autorizar"}
    resumen = esquema["components"]["schemas"]["AutorizacionVistaResumen"]
    assert set(resumen["properties"]) == set(resumen["required"]) == campos - {"calidad_otorgante"}
    assert resumen["additionalProperties"] is False
    respuesta = esquema["paths"][RUTA]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert {r["$ref"].rsplit("/", 1)[1] for r in respuesta["anyOf"]} == {
        "AutorizacionesPersona", "AutorizacionesPersonaResumen"}
    retiro = esquema["components"]["schemas"]["RetiroAutorizacion"]
    campos = {"autorizacion", "enlaces_cortados", "pedidos_cancelados"}  # pedidos_cancelados: MATU-61
    assert set(retiro["properties"]) == set(retiro["required"]) == campos

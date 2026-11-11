"""MATU-60 · docs/api/openapi.json coincide con la API en la lista de insumos y unidades_por_envase. Sin base.

Si la ruta o sus esquemas cambian sin volver a exportar openapi.json, falla. Además: la ruta ya no está en el
contrato propuesto, va antes que {perfil_id}, la respuesta trae solo {fecha, items} con los siete campos de
la línea, y el perfil suma unidades_por_envase (decisiones 116 a 122 de docs/api/README.md).
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest

from app.main import crear_app

pytestmark = pytest.mark.rf("RF-15")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
BASE = "/v1/personas-cuidadas/{persona_id}/consumo"
RUTA = BASE + "/lista"
COMPONENTES = ("ListaInsumos", "LineaListaInsumos")
CON_ENVASE = ("SolicitudPerfil", "SolicitudEdicionPerfil", "PerfilConsumoVista", "InsumoPorAcabarseVista")


@pytest.fixture(scope="module")
def esquema() -> dict[str, Any]:
    return crear_app(io.StringIO()).openapi()


def test_openapi_json_coincide_con_la_api_en_la_lista(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    assert exportado["paths"][RUTA] == esquema["paths"][RUTA], "vuelve a exportar la lista"
    for nombre in COMPONENTES + CON_ENVASE:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre], nombre


def test_la_lista_sale_del_propuesto_y_no_quedan_sus_fragmentos() -> None:
    texto = (DOCS / "propuestos" / "app-familia.openapi.yaml").read_text(encoding="utf-8")
    rutas = {linea.strip().rstrip(":") for linea in texto.splitlines() if linea.startswith("  /v1/")}
    assert RUTA not in rutas
    for fragmento in ("CambioSolicitudPerfil:", "CambioPerfilConsumoVista:", "LineaListaInsumos:", "ListaInsumos:"):
        assert f"    {fragmento}" not in texto


def test_la_lista_va_antes_que_perfil_id_y_solo_tiene_get(esquema: dict[str, Any]) -> None:
    orden = list(esquema["paths"])
    assert orden.index(RUTA) < orden.index(BASE + "/{perfil_id}")
    assert set(esquema["paths"][RUTA]) == {"get"}
    # No hay exportación ni enlace (decisión 122)
    assert not any("exportar" in ruta or "lista-reposicion" in ruta for ruta in esquema["paths"])


def test_la_respuesta_trae_solo_fecha_e_items_con_los_siete_campos(esquema: dict[str, Any]) -> None:
    esquemas = esquema["components"]["schemas"]
    lista, linea = esquemas["ListaInsumos"], esquemas["LineaListaInsumos"]
    assert set(lista["properties"]) == set(lista["required"]) == {"fecha", "items"}
    campos = {
        "perfil_id",
        "nombre",
        "unidad",
        "dias_restantes",
        "unidades_sugeridas",
        "unidades_por_envase",
        "envases_sugeridos",
        # MATU-61 (decisión 215)
        "producto_id",
    }
    assert set(linea["properties"]) == set(linea["required"]) == campos
    assert lista["additionalProperties"] is False and linea["additionalProperties"] is False
    unidades = linea["properties"]["unidades_sugeridas"]
    assert (unidades["minimum"], unidades["maximum"]) == (1, 300_000)


def test_la_lista_no_tiene_parametros_de_consulta_ni_cuerpo(esquema: dict[str, Any]) -> None:
    operacion = esquema["paths"][RUTA]["get"]
    assert "requestBody" not in operacion
    assert {p["in"] for p in operacion["parameters"]} <= {"path", "header"}
    assert {"200", "401", "403", "404"} <= set(operacion["responses"])


@pytest.mark.rf("RF-14")
def test_el_perfil_suma_unidades_por_envase_de_1_a_10000(esquema: dict[str, Any]) -> None:
    esquemas = esquema["components"]["schemas"]
    for nombre in CON_ENVASE:
        propiedad = esquemas[nombre]["properties"]["unidades_por_envase"]
        assert {"type": "null"} in propiedad["anyOf"], nombre
    for nombre in ("SolicitudPerfil", "SolicitudEdicionPerfil"):
        [entero] = [
            t for t in esquemas[nombre]["properties"]["unidades_por_envase"]["anyOf"] if t.get("type") == "integer"
        ]
        assert (entero["minimum"], entero["maximum"]) == (1, 10_000)
        assert "unidades_por_envase" not in esquemas[nombre].get("required", [])
    # En la lectura siempre viene, null si no se anotó
    assert "unidades_por_envase" in esquemas["PerfilConsumoVista"]["required"]
    assert "unidades_por_envase" in esquemas["InsumoPorAcabarseVista"]["required"]

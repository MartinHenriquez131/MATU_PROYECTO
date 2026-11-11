"""MATU-61 · docs/api/openapi.json coincide con la API en las rutas del pedido y de la dirección. Sin base.

El pedido es capa 3: el esquema se toma de la API con CAPA3_HABILITADA=true. Además: ninguna ruta lleva parámetros de
consulta (C17: nada del pedido en la URL), y ninguna vista trae grupo_id, creado_por, el nombre de la persona, lat,
lng ni la referencia opaca de los comercios.
"""

import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.rf("RF-21")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
RUTAS = (
    "/v1/personas-cuidadas/{persona_id}/direccion",
    "/v1/personas-cuidadas/{persona_id}/pedidos",
    "/v1/personas-cuidadas/{persona_id}/pedido-en-curso",
    "/v1/pedidos/{pedido_id}",
    "/v1/pedidos/{pedido_id}/lineas",
    "/v1/pedidos/{pedido_id}/reglas-faltante",
    "/v1/pedidos/{pedido_id}/confirmar",
    "/v1/pedidos/{pedido_id}/contacto",
    "/v1/pedidos/{pedido_id}/cambiar",
    "/v1/pedidos/{pedido_id}/cancelar",
    "/v1/condiciones-pedido",
)
VISTAS = ("PedidoVista", "PedidoVistaObservador", "LineaPedido", "EntregaVista", "ComercioVista", "DireccionVista")
NUNCA = {"grupo_id", "creado_por", "nombre_pila", "lat", "lng", "referencia_comercio", "destinatario_nombre_pila"}


@pytest.fixture(scope="module")
def esquema() -> Iterator[dict[str, Any]]:
    from app.core import config
    from app.main import crear_app

    with pytest.MonkeyPatch.context() as parche:
        parche.setenv("CAPA3_HABILITADA", "true")
        config.obtener_configuracion.cache_clear()
        try:
            yield crear_app(io.StringIO()).openapi()
        finally:
            config.obtener_configuracion.cache_clear()


def test_openapi_json_coincide_con_la_api(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    for ruta in RUTAS:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in VISTAS:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre], nombre


def test_sin_parametros_de_consulta_ni_datos_de_mas(esquema: dict[str, Any]) -> None:
    for ruta in RUTAS:
        for operacion in esquema["paths"][ruta].values():
            assert all(p["in"] != "query" for p in operacion.get("parameters", [])), ruta
    for nombre in VISTAS:
        assert not set(esquema["components"]["schemas"][nombre]["properties"]) & NUNCA, nombre
    assert set(esquema["paths"]["/v1/personas-cuidadas/{persona_id}/direccion"]) == {"put", "delete"}


def test_la_linea_trae_su_oferta_y_los_post_no_declaran_412(esquema: dict[str, Any]) -> None:
    """Decisión 222 y P3 del QA."""
    linea = esquema["components"]["schemas"]["LineaPedido"]
    assert "oferta_id" in linea["properties"] and "oferta_id" in linea["required"]
    for ruta in (
        "/v1/personas-cuidadas/{persona_id}/pedidos",
        "/v1/pedidos/{pedido_id}/confirmar",
        "/v1/pedidos/{pedido_id}/cambiar",
        "/v1/pedidos/{pedido_id}/cancelar",
    ):
        assert "412" not in esquema["paths"][ruta]["post"]["responses"], ruta

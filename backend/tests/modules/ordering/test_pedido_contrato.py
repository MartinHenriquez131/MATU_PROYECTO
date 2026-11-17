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

from tests.modules.ordering.conftest import MONTOS_PARA_EL_OBSERVADOR

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
VISTAS = (
    "PedidoVista", "PedidoVistaObservador", "LineaPedido", "LineaPedidoObservador", "CambioDeLineaObservador",
    "EntregaVista", "ComercioVista", "DireccionVista",
)
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


# MATU-62 (decisión 240): ?version= es un número de versión, no un dato de nadie
CONSULTAS_PERMITIDAS = {
    ("/v1/condiciones-pedido", "version"),
    # MATU-92: el GET de la misma ruta es «Tus pedidos», paginada (cursor opaco, sin datos de nadie)
    ("/v1/personas-cuidadas/{persona_id}/pedidos", "cursor"),
    ("/v1/personas-cuidadas/{persona_id}/pedidos", "limite"),
}


def test_sin_parametros_de_consulta_ni_datos_de_mas(esquema: dict[str, Any]) -> None:
    for ruta in RUTAS:
        for operacion in esquema["paths"][ruta].values():
            consultas = {(ruta, p["name"]) for p in operacion.get("parameters", []) if p["in"] == "query"}
            assert consultas <= CONSULTAS_PERMITIDAS, ruta
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


# --- MATU-113 (decisión 472): el observador no ve montos ---------------------------------------------------------

CAMPOS_OBSERVADOR = {
    "id", "persona_cuidada_id", "estado", "precios_de_ejemplo", "lineas", "salieron", "total_confirmado_en",
    "vence_en", "pagado_en", "ventana_entrega", "creado_en", "actualizado_en",
}
CAMPOS_LINEA_OBSERVADOR = {"id", "producto", "cantidad", "comercio", "regla_faltante", "retracto_pierde_al_abrir",
                           "cambio"}


def _propiedades(esquema: dict[str, Any], nombre: str, vistos: set[str] | None = None) -> set[str]:
    """Las propiedades del componente y de todos los que referencia, a cualquier profundidad."""
    vistos = set() if vistos is None else vistos
    if nombre in vistos:
        return set()
    vistos.add(nombre)
    componente = esquema["components"]["schemas"][nombre]
    propias = set(componente.get("properties", {}))
    for referido in {p.split('"')[0] for p in json.dumps(componente).split("#/components/schemas/")[1:]}:
        propias |= _propiedades(esquema, referido, vistos)
    return propias


@pytest.mark.rf("RF-25")
def test_matu113_la_vista_del_observador_tiene_sus_claves_exactas_y_ningun_monto(esquema: dict[str, Any]) -> None:
    componentes = esquema["components"]["schemas"]
    vista = componentes["PedidoVistaObservador"]
    assert set(vista["properties"]) == CAMPOS_OBSERVADOR
    assert vista["additionalProperties"] is False
    assert vista["properties"]["lineas"]["items"]["$ref"].endswith("/LineaPedidoObservador")
    linea = componentes["LineaPedidoObservador"]
    assert set(linea["properties"]) == CAMPOS_LINEA_OBSERVADOR and linea["additionalProperties"] is False
    assert set(componentes["CambioDeLineaObservador"]["properties"]) == {"comercio_antes"}
    profundas = _propiedades(esquema, "PedidoVistaObservador")
    assert not profundas & MONTOS_PARA_EL_OBSERVADOR, profundas & MONTOS_PARA_EL_OBSERVADOR
    # La vista completa sigue con sus montos
    assert {"subtotal_productos", "costo_envio", "total"} <= set(componentes["PedidoVista"]["properties"])
    assert {"precio_unitario", "subtotal"} <= set(componentes["LineaPedido"]["properties"])

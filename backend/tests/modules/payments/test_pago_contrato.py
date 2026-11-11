"""MATU-62 · docs/api/openapi.json coincide con la API en las rutas del pago, y lo que nunca sale. Sin base.

El pago es capa 3: el esquema se toma con CAPA3_HABILITADA=true. Ninguna vista del pago trae el buy_order, el
session_id, la respuesta de Transbank, el número de tarjeta ni grupo_id (decisión 247); la vuelta sí trae grupo_id,
solo con sesión (decisión 234).
"""

import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.rf("RF-25")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
RUTAS = (
    "/v1/pedidos/{pedido_id}/pagar",
    "/v1/pedidos/{pedido_id}/pago",
    "/v1/personas-cuidadas/{persona_id}/pedido-pagado",
    "/v1/pagos/retorno",
)
VISTAS = (
    "SolicitudPago",
    "InicioPago",
    "SolicitudRetorno",
    "ResultadoRetorno",
    "PagoVista",
    "PagoVistaObservador",
    "Comprobante",
    "Devolucion",
    "Tarjeta",
    "IntentoPago",
    "CorreoComprobante",
    "PedidoVista",
    "LineaPedido",
)
NUNCA = {"buy_order", "session_id", "payload_respuesta", "numero_tarjeta", "card_number", "idempotency_key"}


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


def test_ninguna_vista_del_pago_trae_lo_que_nunca_sale(esquema: dict[str, Any]) -> None:
    for nombre in VISTAS:
        propiedades = set(esquema["components"]["schemas"][nombre].get("properties", {}))
        assert not propiedades & NUNCA, nombre
    for nombre in ("PagoVista", "PagoVistaObservador", "Comprobante", "InicioPago"):
        assert "grupo_id" not in esquema["components"]["schemas"][nombre]["properties"], nombre
    assert set(esquema["components"]["schemas"]["PagoVistaObservador"]["properties"]) == {"pedido_id", "estado"}


def test_pagar_declara_sus_codigos_y_la_vuelta_no_responde_401(esquema: dict[str, Any]) -> None:
    pagar = esquema["paths"]["/v1/pedidos/{pedido_id}/pagar"]["post"]
    assert {"201", "401", "403", "404", "409", "412", "422", "428", "503"} <= set(pagar["responses"])
    retorno = esquema["paths"]["/v1/pagos/retorno"]["post"]
    assert "401" not in retorno["responses"] and {"200", "404", "422"} <= set(retorno["responses"])
    # Las lecturas no llevan parámetros de consulta: nada del pago en la URL
    for ruta in RUTAS:
        for operacion in esquema["paths"][ruta].values():
            assert all(p["in"] != "query" for p in operacion.get("parameters", [])), ruta


@pytest.mark.parametrize("vista", ["PagoVista", "ResultadoRetorno"])
def test_pago_de_prueba_va_tambien_fuera_del_comprobante(esquema: dict[str, Any], vista: str) -> None:
    """Decisión 248: el sello «Pago de prueba» de un pago anulado, que no tiene comprobante (diseño 7.9)."""
    componente = esquema["components"]["schemas"][vista]
    assert componente["properties"]["pago_de_prueba"]["type"] == "boolean"
    assert "pago_de_prueba" in componente["required"]
    assert "pago_de_prueba" not in esquema["components"]["schemas"]["PagoVistaObservador"]["properties"]


def test_pago_de_prueba_es_true_salvo_con_la_pasarela_de_produccion() -> None:
    from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa
    from app.modules.payments.infrastructure.pasarela_transbank import PasarelaTransbank

    assert PasarelaFalsa().pago_de_prueba is True
    assert PasarelaTransbank(produccion=False).pago_de_prueba is True
    produccion = PasarelaTransbank(produccion=True, codigo_comercio="000000000000", llave="llave-sintetica-de-prueba")
    assert produccion.pago_de_prueba is False


def test_el_comprobante_lleva_el_sello_del_piloto_y_la_version_aceptada(esquema: dict[str, Any]) -> None:
    comprobante = esquema["components"]["schemas"]["Comprobante"]["properties"]
    for campo in ("pago_de_prueba", "precios_de_ejemplo", "condiciones", "tardio", "referencia", "pagaste_tu"):
        assert campo in comprobante, campo
    assert comprobante["vendedor"]["const"] == "MATU, piloto académico, sin persona jurídica"

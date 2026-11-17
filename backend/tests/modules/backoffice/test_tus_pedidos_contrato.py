"""MATU-92 · docs/api/openapi.json coincide con la API en «Tus pedidos», y ninguna vista de la familia trae el código de
retiro, la referencia de la parte ni nada de la cuenta del encargado (C15); la del observador, ningún monto (C3, C5).
Sin base, como test_contrato_comercio.py."""

import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.rf("RF-20"), pytest.mark.rf("RF-25")]

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
RUTAS = (
    "/v1/personas-cuidadas/{persona_id}/pedidos",
    "/v1/pedidos/{pedido_id}/seguimiento",
    "/v1/pedidos/{pedido_id}/retractos",
    "/v1/pedidos/{pedido_id}/cancelar-con-devolucion",
    "/v1/pedidos/{pedido_id}/pago",
    "/v1/pedidos/{pedido_id}",
)
# Las respuestas de la familia sobre un pedido pagado
VISTAS_DE_LA_FAMILIA = (
    "ListaPedidosPagados", "ListaPedidosPagadosObservador", "SeguimientoPedido", "RetractosDelPedido",
    "RetractoVistaFamilia", "EstadoPedidoVista", "PagoVista", "PagoVistaObservador",
)
NUNCA_A_LA_FAMILIA = {
    "codigo", "codigo_hash", "codigo_generado_en", "codigo_expira_en", "codigo_usado_en", "codigo_intentos",
    "codigo_bloqueado_en", "estado_codigo", "referencia_parte", "pedido_comercio_id", "parte_id", "usuario_comercio",
    "encargado", "encargado_id", "comercio_id", "solicitado_por", "resuelto_por", "grupo_id", "buy_order",
}
MONTOS = {"total", "devuelto", "devuelto_todo", "monto", "costo_envio", "precio_pagado", "precio_unitario", "subtotal"}
NO_PARA_EL_OBSERVADOR = MONTOS | {
    "referencia", "entregado_en", "cancelado_en", "partes", "puede_cancelar", "puede_arrepentirse", "cancelar_motivo",
    "arrepentirse_motivo", "plazo_hasta", "plazo_correo_hasta",
}


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


def _propiedades(esquema: dict[str, Any], nombre: str, vistos: set[str] | None = None) -> set[str]:
    """Todas las propiedades del componente y de los que referencia, recursivamente."""
    vistos = set() if vistos is None else vistos
    if nombre in vistos:
        return set()
    vistos.add(nombre)
    componente = esquema["components"]["schemas"][nombre]
    propias = set(componente.get("properties", {}))
    texto = json.dumps(componente)
    for referido in {p.split('"')[0] for p in texto.split("#/components/schemas/")[1:]}:
        propias |= _propiedades(esquema, referido, vistos)
    return propias


def test_openapi_json_coincide_con_la_api(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    for ruta in RUTAS:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    nombres: set[str] = set()
    for nombre in VISTAS_DE_LA_FAMILIA:
        _propiedades(esquema, nombre, nombres)
    for nombre in nombres:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre], nombre


@pytest.mark.parametrize("nombre", VISTAS_DE_LA_FAMILIA)
def test_c15_ninguna_vista_de_la_familia_trae_el_codigo_ni_la_parte_del_comercio(
    esquema: dict[str, Any], nombre: str
) -> None:
    propiedades = _propiedades(esquema, nombre)
    assert not propiedades & NUNCA_A_LA_FAMILIA, propiedades & NUNCA_A_LA_FAMILIA
    # codigo_autorizacion es el de Transbank en el comprobante de quien pagó (D-62-2), no el código de retiro
    assert not any(p.startswith("codigo_") for p in propiedades - {"codigo_autorizacion"})
    # La parte del pedido no trae su referencia opaca
    assert "referencia" not in esquema["components"]["schemas"]["ParteDelPedido"]["properties"]


def test_c3_c5_la_vista_del_observador_no_trae_montos_ni_acciones(esquema: dict[str, Any]) -> None:
    propiedades = _propiedades(esquema, "ListaPedidosPagadosObservador")
    assert not propiedades & NO_PARA_EL_OBSERVADOR, propiedades & NO_PARA_EL_OBSERVADOR
    fila = esquema["components"]["schemas"]["PedidoPagadoFilaObservador"]
    assert set(fila["properties"]) == {
        "pedido_id", "pagado_en", "estado", "productos", "resumen_productos", "productos_borrados"}
    assert fila["properties"]["estado"]["const"] == "pagado"


def test_las_vistas_son_estrictas_y_dicen_sus_codigos(esquema: dict[str, Any]) -> None:
    for nombre in ("PedidoPagadoFila", "PedidoPagadoFilaObservador", "SeguimientoPedido", "RetractosDelPedido",
                   "RetractoVistaFamilia", "ParteDelPedido"):
        assert esquema["components"]["schemas"][nombre].get("additionalProperties") is False, nombre
    lista = esquema["paths"]["/v1/personas-cuidadas/{persona_id}/pedidos"]["get"]["responses"]
    assert {"200", "401", "404", "422"} <= set(lista)
    retracto = esquema["paths"]["/v1/pedidos/{pedido_id}/retractos"]["post"]
    assert {"201", "401", "404", "409", "422", "428"} <= set(retracto["responses"])
    assert "Idempotency-Key" in {p["name"] for p in retracto["parameters"]}
    cancelar = esquema["paths"]["/v1/pedidos/{pedido_id}/cancelar-con-devolucion"]["post"]
    assert {"200", "404", "409", "428", "503"} <= set(cancelar["responses"])
    assert "Idempotency-Key" in {p["name"] for p in cancelar["parameters"]}


def test_c13_la_devolucion_admite_el_retracto(esquema: dict[str, Any]) -> None:
    motivo = esquema["components"]["schemas"]["Devolucion"]["properties"]["motivo"]
    assert set(motivo["enum"]) == {"pago_tardio", "producto_no_entregado", "cancelacion", "retracto"}


def test_los_motivos_son_los_de_la_especificacion(esquema: dict[str, Any]) -> None:
    """O1 del diseño (D6): la pantalla elige el texto con el motivo, nunca con el rol."""
    fila = esquema["components"]["schemas"]["PedidoPagadoFila"]["properties"]
    cancelar = {v for x in fila["cancelar_motivo"]["anyOf"] for v in x.get("enum", [])}
    arrepentirse = {v for x in fila["arrepentirse_motivo"]["anyOf"] for v in x.get("enum", [])}
    assert cancelar == {"rol", "ya_se_prepara", "cancelado"}
    assert arrepentirse == {"rol", "sin_entregar", "plazo_app_vencido", "plazo_vencido", "nada_disponible"}

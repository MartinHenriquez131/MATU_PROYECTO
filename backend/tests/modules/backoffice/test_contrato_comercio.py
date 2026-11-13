"""MATU-63 · docs/api/openapi.json coincide con la API en las rutas del comercio, de operación y de la familia
después de pagar, y la proyección del comercio no trae nada de la familia (D-63-1, R6 y R7). Sin base."""

import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.rf("RF-26"), pytest.mark.rf("R7")]

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
PREFIJOS = ("/v1/comercio", "/v1/operacion")
DE_LA_FAMILIA = ("/v1/pedidos/{pedido_id}/cancelar-con-devolucion", "/v1/pedidos/{pedido_id}/retractos")
VISTAS_DEL_COMERCIO = (
    "ComercioDeLaCuenta", "ListaPartes", "ParteResumen", "ParteVista", "LineaComercioVista", "ProductoLinea",
    "ResultadoCodigoVista", "ListaProductos", "ProductoDelComercio", "SolicitudMarca", "SolicitudCodigo",
    "SolicitudProducto",
)
# D-63-1: lo que la proyección del comercio nunca trae
NUNCA_AL_COMERCIO = {
    "pedido_id", "grupo_id", "persona_cuidada_id", "persona_id", "creado_por", "condiciones_version",
    "condiciones_huella", "condiciones_aceptadas_por", "total", "subtotal_productos", "costo_envio",
    "precio_unitario", "precio_carrito", "monto_devuelto", "oferta_carrito_id", "codigo_hash", "codigo",
    "transiciones", "entrega", "direccion", "telefono", "telefono_contacto", "nombre_pila", "comuna",
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


def _rutas(esquema: dict[str, Any]) -> list[str]:
    return [r for r in esquema["paths"] if r.startswith(PREFIJOS) or r in DE_LA_FAMILIA]


def test_openapi_json_coincide_con_la_api(esquema: dict[str, Any]) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    rutas = _rutas(esquema)
    assert len(rutas) == 18
    for ruta in rutas:
        assert exportado["paths"][ruta] == esquema["paths"][ruta], f"vuelve a exportar {ruta}"
    for nombre in VISTAS_DEL_COMERCIO:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre], nombre


def test_la_proyeccion_del_comercio_no_trae_nada_de_la_familia(esquema: dict[str, Any]) -> None:
    for nombre in VISTAS_DEL_COMERCIO:
        if nombre == "SolicitudCodigo":
            continue
        propiedades = set(esquema["components"]["schemas"][nombre].get("properties", {}))
        assert not propiedades & NUNCA_AL_COMERCIO, nombre


def test_el_codigo_va_solo_en_el_cuerpo_y_nada_en_la_url(esquema: dict[str, Any]) -> None:
    validar = esquema["paths"]["/v1/comercio/partes/{parte_id}/validar-codigo"]["post"]
    assert {p["name"] for p in validar["parameters"]} == {"parte_id"}
    assert {"200", "404", "422", "429", "503"} <= set(validar["responses"])
    for ruta in _rutas(esquema):
        for operacion in esquema["paths"][ruta].values():
            assert all(p["in"] != "query" for p in operacion.get("parameters", [])), ruta


def test_las_acciones_declaran_sus_codigos(esquema: dict[str, Any]) -> None:
    for accion in ("preparar", "listo"):
        respuestas = esquema["paths"][f"/v1/comercio/partes/{{parte_id}}/{accion}"]["post"]["responses"]
        assert {"200", "401", "403", "404", "409", "412"} <= set(respuestas), accion
    cancelar = esquema["paths"]["/v1/pedidos/{pedido_id}/cancelar-con-devolucion"]["post"]["responses"]
    assert {"200", "404", "409", "503"} <= set(cancelar)
    retracto = esquema["paths"]["/v1/pedidos/{pedido_id}/retractos"]["post"]["responses"]
    assert {"201", "404", "409", "422"} <= set(retracto)


def test_la_sesion_dice_el_tipo_de_cuenta_y_nada_mas(esquema: dict[str, Any]) -> None:
    """O1: familia o comercio, sin el comercio ni otro dato de la cuenta."""
    propiedades = esquema["components"]["schemas"]["SesionRespuesta"]["properties"]
    assert propiedades["tipo_cuenta"]["enum"] == ["familia", "comercio"]
    assert set(propiedades) == {"access_token", "token_type", "expira_en", "tipo_cuenta"}


def test_el_motivo_de_cancelacion_es_uno_de_dos_y_nada_mas(esquema: dict[str, Any]) -> None:
    """Decisión 430: el comercio sabe si no tenía ninguno o si canceló la familia; ni quién ni otro motivo."""
    for nombre in ("ParteResumen", "ParteVista"):
        motivo = esquema["components"]["schemas"][nombre]["properties"]["motivo_cancelacion"]
        valores = {x.get("const") or tuple(x.get("enum", ())) for x in motivo["anyOf"]} - {None}
        assert {"producto_faltante", "cancelada_por_familia"} == {v for x in valores for v in (
            x if isinstance(x, tuple) else (x,))}, nombre
        assert "motivo_cancelacion" in esquema["components"]["schemas"][nombre]["required"], nombre

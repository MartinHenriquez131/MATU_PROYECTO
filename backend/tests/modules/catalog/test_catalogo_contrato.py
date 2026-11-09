"""MATU-59 · docs/api/openapi.json coincide con la API en GET /v1/catalogo (decisiones 158 a 167). Sin base.

El catálogo es capa 3: el esquema se toma de la API con CAPA3_HABILITADA=true. Además: los campos exactos de cada
esquema, ninguno del comercio ni la marca (condición 3), sin parámetros de consulta (sin texto libre en la URL) y
solo 200 y 401.
"""

import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.rf("RF-20")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
RUTA = "/v1/catalogo"
ESQUEMAS = {
    "Catalogo": {"precios_de_ejemplo", "categorias"},
    "CategoriaCatalogo": {"id", "nombre", "orden", "productos"},
    "ProductoCatalogo": {
        "id", "nombre", "presentacion", "unidad", "unidades_por_envase", "retracto_pierde_al_abrir", "comercios",
    },
    "OfertaCatalogo": {"oferta_id", "comercio_id", "nombre_fantasia", "precio", "disponible"},
}
# Lo que nunca viaja en el catálogo (condición 3 y N4 del diseñador)
NUNCA = {"marca", "razon_social", "rut", "direccion", "telefono", "comuna", "stock"}


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

    assert exportado["paths"][RUTA] == esquema["paths"][RUTA], f"vuelve a exportar {RUTA}"
    for nombre in ESQUEMAS:
        assert exportado["components"]["schemas"][nombre] == esquema["components"]["schemas"][nombre], nombre


def test_campos_exactos_y_cerrados(esquema: dict[str, Any]) -> None:
    for nombre, campos in ESQUEMAS.items():
        definicion = esquema["components"]["schemas"][nombre]
        assert set(definicion["properties"]) == set(definicion["required"]) == campos, nombre
        assert definicion["additionalProperties"] is False, nombre


def test_nunca_marca_ni_datos_del_comercio(esquema: dict[str, Any]) -> None:
    campos = {c for nombre in ESQUEMAS for c in esquema["components"]["schemas"][nombre]["properties"]}

    assert campos & NUNCA == set()


def test_precio_en_pesos_enteros_y_disponible_booleano(esquema: dict[str, Any]) -> None:
    oferta = esquema["components"]["schemas"]["OfertaCatalogo"]["properties"]

    assert oferta["precio"]["type"] == "integer" and oferta["precio"]["exclusiveMinimum"] == 0
    assert oferta["disponible"]["type"] == "boolean"


def test_solo_get_sin_parametros_con_200_y_401(esquema: dict[str, Any]) -> None:
    assert set(esquema["paths"][RUTA]) == {"get"}
    operacion = esquema["paths"][RUTA]["get"]

    assert "parameters" not in operacion
    assert set(operacion["responses"]) == {"200", "401"}


def test_sin_la_capa_3_no_esta_en_la_api() -> None:
    from app.core import config
    from app.main import crear_app

    with pytest.MonkeyPatch.context() as parche:
        parche.setenv("CAPA3_HABILITADA", "false")
        config.obtener_configuracion.cache_clear()
        try:
            assert RUTA not in crear_app(io.StringIO()).openapi()["paths"]
        finally:
            config.obtener_configuracion.cache_clear()


def test_la_ruta_y_las_decisiones_estan_en_el_readme() -> None:
    texto = (DOCS / "README.md").read_text(encoding="utf-8")

    assert "| `GET /v1/catalogo` | MATU-59" in texto
    for numero in range(158, 171):
        assert f"\n{numero}. **" in texto, numero

"""MATU-59 · GET /v1/catalogo contra PostgreSQL (RF-20, decisiones 158 a 167).

Camino feliz para los cuatro roles, lo que entra y lo que no, el orden, sin datos del comercio, Cache-Control,
sin auditoría ni logs del contenido, y los caminos de error: sin sesión, token inválido y el relevo (401).
"""

import io
import secrets
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.modules.care_plan.api.router_relevo_publico import COOKIE as COOKIE_RELEVO
from tests.base_datos import DSN, requiere_base
from tests.modules.catalog.conftest import CatalogoSintetico, EntornoCatalogo

pytestmark = [pytest.mark.rf("RF-20"), requiere_base]

PROHIBIDOS = ("marca", "razon_social", "rut", "direccion", "telefono", "comuna", "stock")


def _mias(cuerpo: dict[str, Any], catalogo: CatalogoSintetico) -> list[dict[str, Any]]:
    suyas = {str(i) for i in catalogo.categorias.values()}
    return [c for c in cuerpo["categorias"] if c["id"] in suyas]


def _claves(valor: Any) -> set[str]:
    if isinstance(valor, dict):
        return set(valor) | {c for v in valor.values() for c in _claves(v)}
    if isinstance(valor, list):
        return {c for v in valor for c in _claves(v)}
    return set()


@pytest.mark.parametrize("rol", ["admin", "cuidador", "pagador", "observador"])
def test_los_cuatro_roles_ven_el_catalogo(
    entorno_catalogo: EntornoCatalogo, catalogo_sintetico: CatalogoSintetico, rol: str
) -> None:
    familia = entorno_catalogo.familia()
    usuario = familia.admin if rol == "admin" else familia.miembros[rol].usuario

    respuesta = entorno_catalogo.ver(usuario)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["Cache-Control"] == "private, max-age=60"
    assert respuesta.json()["precios_de_ejemplo"] is True
    assert len(_mias(respuesta.json(), catalogo_sintetico)) == 2


def test_lo_que_entra_con_su_precio_disponible_y_orden(
    entorno_catalogo: EntornoCatalogo, catalogo_sintetico: CatalogoSintetico
) -> None:
    c, s = catalogo_sintetico, catalogo_sintetico.sufijo

    cuerpo = entorno_catalogo.ver(entorno_catalogo.familia().admin).json()

    assert _mias(cuerpo, c) == [
        {
            "id": str(c.categorias["higiene"]),
            "nombre": f"Categoría higiene {s}",
            "orden": 1,
            "productos": [
                {
                    "id": str(c.productos["bolsa"]),
                    "nombre": f"Producto bolsa {s}",
                    "presentacion": "Paquete de 30 unidades",
                    "unidad": "unidad",
                    "unidades_por_envase": 30,
                    "retracto_pierde_al_abrir": False,
                    "comercios": [
                        {"oferta_id": str(c.ofertas[("bolsa", "uno")]), "comercio_id": str(c.comercios["uno"]),
                         "nombre_fantasia": f"Almacén El Ejemplo {s}", "precio": 15990, "disponible": False},
                        {"oferta_id": str(c.ofertas[("bolsa", "dos")]), "comercio_id": str(c.comercios["dos"]),
                         "nombre_fantasia": f"Bodega La Muestra {s}", "precio": 16490, "disponible": False},
                    ],
                },
                {
                    "id": str(c.productos["panal"]),
                    "nombre": f"Producto panal {s}",
                    "presentacion": "Paquete de 30 unidades",
                    "unidad": "unidad",
                    "unidades_por_envase": 30,
                    "retracto_pierde_al_abrir": True,
                    # Por nombre de fantasía: la Bodega es más barata y va segunda
                    "comercios": [
                        {"oferta_id": str(c.ofertas[("panal", "uno")]), "comercio_id": str(c.comercios["uno"]),
                         "nombre_fantasia": f"Almacén El Ejemplo {s}", "precio": 12990, "disponible": True},
                        {"oferta_id": str(c.ofertas[("panal", "dos")]), "comercio_id": str(c.comercios["dos"]),
                         "nombre_fantasia": f"Bodega La Muestra {s}", "precio": 9990, "disponible": False},
                    ],
                },
            ],
        },
        {
            "id": str(c.categorias["piel"]),
            "nombre": f"Categoría piel {s}",
            "orden": 2,
            "productos": [
                {
                    "id": str(c.productos["crema"]),
                    "nombre": f"Producto crema {s}",
                    "presentacion": "Paquete de 30 unidades",
                    "unidad": "unidad",
                    "unidades_por_envase": 30,
                    "retracto_pierde_al_abrir": True,
                    "comercios": [
                        {"oferta_id": str(c.ofertas[("crema", "dos")]), "comercio_id": str(c.comercios["dos"]),
                         "nombre_fantasia": f"Bodega La Muestra {s}", "precio": 7290, "disponible": True},
                    ],
                },
            ],
        },
    ]
    # Ni la oferta no publicada, ni el comercio suspendido, ni el producto sin ofertas, inactivo o de una
    # categoría inactiva
    texto = str(cuerpo)
    for clave in ("no_publicado", "solo_suspendido", "sin_ofertas", "inactivo", "de_inactiva"):
        assert str(c.productos[clave]) not in texto
    assert str(c.categorias["inactiva"]) not in texto
    assert str(c.comercios["suspendido"]) not in texto


def test_la_respuesta_no_trae_marca_ni_datos_del_comercio(
    entorno_catalogo: EntornoCatalogo, catalogo_sintetico: CatalogoSintetico
) -> None:
    respuesta = entorno_catalogo.ver(entorno_catalogo.familia().admin)

    assert _claves(respuesta.json()).isdisjoint(PROHIBIDOS)
    for privado in [*catalogo_sintetico.privados, "Marca de ejemplo"]:
        assert privado not in respuesta.text


def test_no_audita_ni_registra_el_contenido(
    entorno_catalogo: EntornoCatalogo, catalogo_sintetico: CatalogoSintetico
) -> None:
    admin = entorno_catalogo.familia().admin
    entorno_catalogo.token(admin)
    with psycopg.connect(DSN) as cx:
        antes = cx.execute("SELECT count(*) FROM auditoria WHERE actor_ref = %s", (admin.id,)).fetchone()

    assert entorno_catalogo.ver(admin).status_code == 200

    with psycopg.connect(DSN) as cx:
        despues = cx.execute("SELECT count(*) FROM auditoria WHERE actor_ref = %s", (admin.id,)).fetchone()
    assert despues == antes
    log = entorno_catalogo.iam.texto_log()
    assert "/v1/catalogo" in log
    assert catalogo_sintetico.sufijo not in log


def test_sin_sesion_responde_401(entorno_catalogo: EntornoCatalogo) -> None:
    respuesta = entorno_catalogo.ver()

    assert respuesta.status_code == 401
    assert respuesta.headers["content-type"].startswith("application/problem+json")
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


def test_token_invalido_responde_401(entorno_catalogo: EntornoCatalogo) -> None:
    respuesta = entorno_catalogo.ver(Authorization="Bearer no-es-un-token")

    assert respuesta.status_code == 401
    assert respuesta.json()["type"].endswith("token-invalido")


def test_el_relevo_no_entra(entorno_catalogo: EntornoCatalogo) -> None:
    # La sesión del relevo es su cookie, sin access token: el catálogo no la acepta
    entorno_catalogo.iam.cliente.cookies.set(COOKIE_RELEVO, "sesion-de-relevo-sintetica")
    try:
        respuesta = entorno_catalogo.ver()
    finally:
        entorno_catalogo.iam.cliente.cookies.clear()

    assert respuesta.status_code == 401


@pytest.mark.parametrize(("habilitada", "codigo"), [("true", 401), ("false", 404)])
def test_solo_existe_con_la_capa_3_habilitada(
    monkeypatch: pytest.MonkeyPatch, habilitada: str, codigo: int
) -> None:
    from app.core import config
    from app.main import crear_app

    monkeypatch.setenv("CAPA3_HABILITADA", habilitada)
    # El 401 se arma después de leer la clave JWT: en el pipeline no hay .env
    monkeypatch.setenv("JWT_CLAVE", secrets.token_hex(32))
    config.obtener_configuracion.cache_clear()
    try:
        cliente = TestClient(crear_app(stream_logs=io.StringIO()), raise_server_exceptions=False)
        assert cliente.get("/v1/catalogo").status_code == codigo
    finally:
        config.obtener_configuracion.cache_clear()

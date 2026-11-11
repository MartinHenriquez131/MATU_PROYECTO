"""MATU-62 · La vuelta de Webpay por HTTP (decisiones 231 a 235). Sin base: el pago en memoria y la PasarelaFalsa.

- POST /v1/pagos/retorno: pública, sin 401, sin montos ni tarjeta, idempotente por token, 404 para lo que no es de
  MATU, 422 sin ninguno de los cuatro campos, y en el log solo el caso (decisión 235).
- POST /insumos/pedido/pago: 303 a la pantalla con los cuatro campos válidos en el fragmento, sin query, con no-store
  y no-referrer; fuera de openapi.json.
"""

import io
import json
import logging
import secrets
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.db import obtener_fabrica_sesiones
from app.main import crear_app
from app.modules.iam.api.dependencias import obtener_clave_jwt, obtener_reloj
from app.modules.payments.api.router_retorno import obtener_abrir_grupo, obtener_resolver
from app.modules.payments.infrastructure.pasarela import obtener_pasarela
from tests.modules.payments.test_casos_pago import TOTAL, Escena

pytestmark = pytest.mark.rf("RF-25")

RUTA = "/v1/pagos/retorno"
CLAVES = {
    "resultado", "ya_registrado", "anulacion", "volver_a_preguntar_en", "grupo_id", "persona_cuidada_id", "pedido_id",
    "pago_de_prueba",
}


class _SinBase:
    """La fábrica de sesiones de la API: sin sesión de la familia, la vuelta no la abre."""

    def __call__(self, **_: Any) -> Any:
        raise AssertionError("la vuelta sin sesión no abre la base de la familia")


@pytest.fixture
def escena() -> Escena:
    return Escena()


@pytest.fixture
def api(escena: Escena) -> Iterator[tuple[TestClient, io.StringIO]]:
    salida = io.StringIO()
    app = crear_app(stream_logs=salida)
    app.dependency_overrides[obtener_resolver] = lambda: escena.sistema.resolver
    app.dependency_overrides[obtener_abrir_grupo] = lambda: escena.sistema.abrir
    app.dependency_overrides[obtener_pasarela] = lambda: escena.pasarela
    app.dependency_overrides[obtener_reloj] = lambda: escena.reloj
    app.dependency_overrides[obtener_fabrica_sesiones] = lambda: _SinBase()
    clave = secrets.token_hex(32).encode()
    app.dependency_overrides[obtener_clave_jwt] = lambda: clave
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente, salida


def _lineas(salida: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(x) for x in salida.getvalue().splitlines() if x.strip()]


def test_aprobado_sin_sesion_sin_montos_ni_tarjeta_y_el_log_solo_con_el_caso(
    escena: Escena, api: tuple[TestClient, io.StringIO]
) -> None:
    cliente, salida = api
    venta = escena.pagar().venta
    assert venta.token is not None
    escena.pasarela.pagar(venta.token)

    respuesta = cliente.post(RUTA, json={"token_ws": venta.token})

    assert respuesta.status_code == 200
    assert respuesta.headers["Cache-Control"] == "no-store"
    cuerpo = respuesta.json()
    assert set(cuerpo) == CLAVES
    assert cuerpo == {
        "resultado": "aprobado",
        "ya_registrado": False,
        "anulacion": None,
        "volver_a_preguntar_en": None,
        "grupo_id": None,
        "persona_cuidada_id": None,
        "pedido_id": None,
        "pago_de_prueba": True,
    }
    assert str(TOTAL) not in respuesta.text and "2032" not in respuesta.text
    assert escena.p.estado == "pagado"
    # Decisión 235: ni el token, ni el buy_order, ni el session_id, ni la respuesta de Transbank en los logs
    texto = salida.getvalue()
    for secreto in (venta.token, venta.buy_order, venta.session_id or "-", "AUTHORIZED", "2032"):
        assert secreto not in texto
    [linea] = [x for x in _lineas(salida) if x.get("ruta") == RUTA]
    assert (linea["caso"], linea["estado"]) == ("commit", 200)


def test_repetido_no_llama_a_transbank_y_un_token_invalido_no_es_un_401(
    escena: Escena, api: tuple[TestClient, io.StringIO]
) -> None:
    cliente, salida = api
    token = escena.pagado()
    llamadas = list(escena.pasarela.llamadas)

    respuesta = cliente.post(RUTA, json={"token_ws": token}, headers={"Authorization": "Bearer no-es-un-token"})

    assert respuesta.status_code == 200
    assert (respuesta.json()["resultado"], respuesta.json()["ya_registrado"]) == ("aprobado", True)
    assert escena.pasarela.llamadas == llamadas
    assert [x["caso"] for x in _lineas(salida) if x.get("ruta") == RUTA] == ["repetido"]


def test_pendiente_dice_cuando_volver_a_preguntar(escena: Escena, api: tuple[TestClient, io.StringIO]) -> None:
    cliente, _ = api
    venta = escena.pagar().venta
    assert venta.token is not None
    escena.pasarela.pagar(venta.token)
    escena.pasarela.caida = True
    cuerpo = cliente.post(RUTA, json={"token_ws": venta.token}).json()
    assert (cuerpo["resultado"], cuerpo["volver_a_preguntar_en"]) == ("pendiente", 15)


def test_salio_de_webpay_por_los_nombres_de_transbank(escena: Escena, api: tuple[TestClient, io.StringIO]) -> None:
    cliente, salida = api
    venta = escena.pagar().venta
    cuerpo = {"TBK_TOKEN": venta.token, "TBK_ORDEN_COMPRA": venta.buy_order, "TBK_ID_SESION": venta.session_id}
    respuesta = cliente.post(RUTA, json=cuerpo)
    assert (respuesta.status_code, respuesta.json()["resultado"]) == (200, "abandonado")
    assert [x["caso"] for x in _lineas(salida) if x.get("ruta") == RUTA] == ["usuario_salio"]


def test_lo_que_no_es_de_matu_es_404_sin_repetir_el_valor(escena: Escena, api: tuple[TestClient, io.StringIO]) -> None:
    cliente, salida = api
    escena.pagar()
    llamadas = list(escena.pasarela.llamadas)
    valor = "token-que-no-es-de-matu"
    respuesta = cliente.post(RUTA, json={"token_ws": valor})
    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"].startswith("application/problem+json")
    assert valor not in respuesta.text and valor not in salida.getvalue()
    assert escena.pasarela.llamadas == llamadas
    assert [x["caso"] for x in _lineas(salida) if x.get("ruta") == RUTA] == ["desconocido"]


@pytest.mark.parametrize(
    "cuerpo",
    [{}, {"token_ws": ""}, {"token_ws": "con espacio"}, {"token_ws": "a" * 129}, {"TBK_ORDEN_COMPRA": "o" * 27},
     {"otro": "valor-extra-sintetico"}, {"token_ws": "<script>"}],
    ids=["vacio", "token-vacio", "espacio", "largo", "orden-larga", "campo-extra", "caracteres"],
)
def test_422_sin_campos_validos_y_sin_repetir_el_valor(
    cuerpo: dict[str, str], api: tuple[TestClient, io.StringIO]
) -> None:
    cliente, salida = api
    respuesta = cliente.post(RUTA, json=cuerpo)
    assert respuesta.status_code == 422
    for valor in cuerpo.values():
        if valor:
            assert valor not in respuesta.text and valor not in salida.getvalue()


# --- POST /insumos/pedido/pago -------------------------------------------------------------------------------------


def _formulario(cliente: TestClient, cuerpo: str) -> Any:
    return cliente.post(
        "/insumos/pedido/pago",
        content=cuerpo,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


@pytest.mark.parametrize(
    ("cuerpo", "location"),
    [
        ("token_ws=abc_DEF-123", "/insumos/pedido/pago#token_ws=abc_DEF-123"),
        (
            "TBK_TOKEN=t1&TBK_ORDEN_COMPRA=o1&TBK_ID_SESION=s1",
            "/insumos/pedido/pago#TBK_TOKEN=t1&TBK_ORDEN_COMPRA=o1&TBK_ID_SESION=s1",
        ),
        ("token_ws=abc&nombre=Mar%C3%ADa&email=x%40y.cl", "/insumos/pedido/pago#token_ws=abc"),
        ("token_ws=%3Cscript%3E", "/insumos/pedido/pago"),
        ("TBK_ORDEN_COMPRA=" + "o" * 27, "/insumos/pedido/pago"),
        ("token_ws=a&token_ws=b", "/insumos/pedido/pago"),
        ("", "/insumos/pedido/pago"),
    ],
    ids=["token", "tbk", "descarta-otros", "caracteres", "largo", "repetido", "vacio"],
)
def test_el_post_de_transbank_es_un_303_a_la_pantalla_con_el_fragmento(
    cuerpo: str, location: str, api: tuple[TestClient, io.StringIO]
) -> None:
    cliente, salida = api
    respuesta = _formulario(cliente, cuerpo)
    assert respuesta.status_code == 303
    assert respuesta.headers["location"] == location
    assert "?" not in respuesta.headers["location"]
    assert respuesta.headers["cache-control"] == "no-store"
    assert respuesta.headers["referrer-policy"] == "no-referrer"
    # No registra el cuerpo: ni los valores ni los nombres de los campos
    texto = salida.getvalue()
    assert "abc" not in texto and "TBK_TOKEN" not in texto and "Mar" not in texto


def test_el_post_de_transbank_no_llama_a_transbank_ni_esta_en_openapi(
    escena: Escena, api: tuple[TestClient, io.StringIO]
) -> None:
    cliente, _ = api
    venta = escena.pagar().venta
    llamadas = list(escena.pasarela.llamadas)
    _formulario(cliente, f"token_ws={venta.token}")
    assert escena.pasarela.llamadas == llamadas and escena.ventas()[0].estado.value == "iniciada"
    assert "/insumos/pedido/pago" not in cliente.get("/openapi.json").json()["paths"]


# --- Decisión 235: la vuelta por la dirección no deja el token en los logs ------------------------------------------

TOKEN_SINTETICO = "abcdef0123456789" * 4


@pytest.fixture
def app_con_dist(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, io.StringIO]]:
    """La app de familia con un build sintético: GET /insumos/pedido/pago entrega su index.html."""
    from app.core import config

    (tmp_path / "index.html").write_text("<!doctype html><title>MATU</title>", encoding="utf-8")
    monkeypatch.setenv("WEB_DIST", str(tmp_path))
    config.obtener_configuracion.cache_clear()
    salida = io.StringIO()
    try:
        app = crear_app(stream_logs=salida)
    finally:
        config.obtener_configuracion.cache_clear()
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente, salida


def test_el_get_de_la_pantalla_con_token_ws_no_lo_deja_en_los_logs(
    app_con_dist: tuple[TestClient, io.StringIO], caplog: pytest.LogCaptureFixture
) -> None:
    cliente, salida = app_con_dist
    with caplog.at_level(logging.DEBUG):
        respuesta = cliente.get(f"/insumos/pedido/pago?token_ws={TOKEN_SINTETICO}")
    assert respuesta.status_code == 200 and "MATU" in respuesta.text
    assert TOKEN_SINTETICO not in salida.getvalue()
    assert all(TOKEN_SINTETICO not in r.getMessage() and TOKEN_SINTETICO not in str(r.__dict__) for r in caplog.records)
    lineas = [x for x in _lineas(salida) if x.get("mensaje") == "peticion"]
    assert lineas and all("?" not in str(x.get("ruta")) for x in lineas)


def test_el_post_de_transbank_con_tbk_no_deja_los_valores_en_los_logs(
    api: tuple[TestClient, io.StringIO], caplog: pytest.LogCaptureFixture
) -> None:
    cliente, salida = api
    orden, sesion = "orden" + TOKEN_SINTETICO[:20], "sesion" + TOKEN_SINTETICO[:30]
    with caplog.at_level(logging.DEBUG):
        respuesta = _formulario(
            cliente, f"TBK_TOKEN={TOKEN_SINTETICO}&TBK_ORDEN_COMPRA={orden}&TBK_ID_SESION={sesion}"
        )
    assert respuesta.status_code == 303 and TOKEN_SINTETICO in respuesta.headers["location"]
    for valor in (TOKEN_SINTETICO, orden, sesion):
        assert valor not in salida.getvalue()
        assert all(valor not in r.getMessage() and valor not in str(r.__dict__) for r in caplog.records)

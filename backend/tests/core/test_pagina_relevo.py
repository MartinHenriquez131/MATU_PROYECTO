"""La API sirve la página del relevo en /r desde un build falso en tmp_path (MATU-23, D6)."""

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.main import crear_app

HTML = (
    '<!doctype html><html lang="es-CL"><head>'
    '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'" />'
    '</head><body><div id="raiz"></div><script type="module" src="/assets/index-abc123.js"></script>'
    "</body></html>"
)
JS = "console.log('relevo sintetico')"
CABECERAS = {"cache-control": "no-store", "referrer-policy": "no-referrer", "x-robots-tag": "noindex"}


def _cliente(monkeypatch: pytest.MonkeyPatch, web_dist: Path) -> Iterator[TestClient]:
    monkeypatch.setenv("ENTORNO", "pruebas")
    monkeypatch.setenv("WEB_DIST", str(web_dist))
    config.obtener_configuracion.cache_clear()
    try:
        yield TestClient(crear_app(io.StringIO()))
    finally:
        config.obtener_configuracion.cache_clear()


@pytest.fixture
def con_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(HTML, encoding="utf-8")
    (dist / "assets" / "index-abc123.js").write_text(JS, encoding="utf-8")
    yield from _cliente(monkeypatch, dist)


@pytest.fixture
def sin_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield from _cliente(monkeypatch, tmp_path / "no-existe")


@pytest.mark.rf("RF-06")
def test_r_sirve_el_html_con_las_tres_cabeceras_y_su_csp(con_dist: TestClient) -> None:
    respuesta = con_dist.get("/r")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    for clave, valor in CABECERAS.items():
        assert respuesta.headers[clave] == valor
    # La CSP del build se entrega intacta
    assert respuesta.text == HTML


@pytest.mark.rf("RF-06")
def test_un_asset_se_sirve_con_su_cache_normal(con_dist: TestClient) -> None:
    respuesta = con_dist.get("/assets/index-abc123.js")
    assert respuesta.status_code == 200
    assert respuesta.text == JS
    assert "etag" in respuesta.headers
    assert respuesta.headers.get("cache-control") != "no-store"


@pytest.mark.rf("RF-06")
def test_un_asset_inexistente_responde_404(con_dist: TestClient) -> None:
    assert con_dist.get("/assets/no-existe.js").status_code == 404


@pytest.mark.rf("RF-06")
def test_sin_dist_la_api_arranca_y_r_responde_404_problem_json(sin_dist: TestClient) -> None:
    respuesta = sin_dist.get("/r")
    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"].startswith("application/problem+json")
    assert respuesta.json()["status"] == 404
    for clave, valor in CABECERAS.items():
        assert respuesta.headers[clave] == valor
    assert sin_dist.get("/v1/salud").json() == {"estado": "ok"}


@pytest.mark.rf("RF-06")
@pytest.mark.parametrize("fixture", ["con_dist", "sin_dist"])
def test_el_montaje_no_tapa_la_api_ni_la_documentacion(fixture: str, request: pytest.FixtureRequest) -> None:
    cliente: TestClient = request.getfixturevalue(fixture)
    assert cliente.get("/v1/salud").json() == {"estado": "ok"}
    assert cliente.get("/docs").status_code == 200
    assert "/v1/relevo/presentacion" in cliente.get("/openapi.json").json()["paths"]
    assert "/r" not in cliente.get("/openapi.json").json()["paths"]
    # Una ruta del relevo responde la API (422 por cuerpo vacío), no la página
    relevo = cliente.post("/v1/relevo/presentacion", json={})
    assert relevo.status_code == 422
    assert relevo.headers["content-type"].startswith("application/problem+json")

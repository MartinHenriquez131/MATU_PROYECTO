"""La API entrega la app de familia en sus rutas desde un build falso en tmp_path (MATU-58, decisión 115).

La app enruta en el navegador (web/src/familia/ruteo.ts): toda ruta GET o HEAD que no sea de la API, /r,
/assets ni la documentación responde el index.html. Las rutas de la API responden como antes. Y /docs y
/openapi.json solo existen en local y pruebas. Un archivo oculto, o una ruta con extensión que no está en el
build, responde 404, y los .js y .css llevan su tipo aunque el sistema diga otro.

RF-37 es la sesión y la cuenta de la app de familia, que estas rutas sirven.
"""

import io
import mimetypes
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import config
from app.core.config import ENTORNOS_DOCUMENTACION
from app.core.web import archivo_del_build, es_ruta_de_la_app, es_ruta_oculta, parece_archivo
from app.main import crear_app
from app.modules.care_plan.api import dependencias

HTML = (
    '<!doctype html><html lang="es-CL"><head>'
    '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'" />'
    '</head><body><div id="raiz"></div><script type="module" src="/assets/index-abc123.js"></script>'
    "</body></html>"
)
JS = "console.log('app sintetica')"
CSS = "body { margin: 0 }"
MANIFIESTO = '{"name": "MATU sintetico"}'
AJENO = "fuera del build, sintetico"
CABECERAS_APP = {
    "cache-control": "no-cache",
    "referrer-policy": "no-referrer",
    "x-robots-tag": "noindex",
    "content-security-policy": "frame-ancestors 'none'",
}
CABECERAS_RELEVO = {"cache-control": "no-store", "referrer-policy": "no-referrer", "x-robots-tag": "noindex"}
PROBLEMA = "application/problem+json"
RUTAS_APP = ["/", "/entrar", "/insumos", "/ficha/su-dia", "/entrar/recuperar/codigo", "/una-pantalla-futura"]

Fabricar = Callable[..., TestClient]


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    carpeta = tmp_path / "dist"
    (carpeta / "assets").mkdir(parents=True)
    (carpeta / "index.html").write_text(HTML, encoding="utf-8")
    (carpeta / "assets" / "index-abc123.js").write_text(JS, encoding="utf-8")
    (carpeta / "assets" / "index-abc123.css").write_text(CSS, encoding="utf-8")
    (carpeta / "manifest.webmanifest").write_text(MANIFIESTO, encoding="utf-8")
    # Archivos ocultos del build, como el manifiesto de Vite: nunca se sirven
    (carpeta / ".vite").mkdir()
    (carpeta / ".vite" / "manifest.json").write_text("{}", encoding="utf-8")
    (carpeta / "assets" / ".oculto.js").write_text(JS, encoding="utf-8")
    # Junto a la carpeta del build, nunca dentro: no se puede alcanzar desde una ruta
    (tmp_path / "ajeno.txt").write_text(AJENO, encoding="utf-8")
    return carpeta


@pytest.fixture
def fabricar(configuracion_sin_env: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[Fabricar]:
    """Arma la API con un ENTORNO y una carpeta del build, sin el .env del equipo ni la custodia."""

    def _fabricar(web_dist: Path, entorno: str = "pruebas") -> TestClient:
        monkeypatch.setenv("ENTORNO", entorno)
        monkeypatch.setenv("POLITICA_VERSION", "0.10")
        monkeypatch.setenv("WEB_DIST", str(web_dist))
        config.obtener_configuracion.cache_clear()
        dependencias.custodia_configurada.cache_clear()
        return TestClient(crear_app(io.StringIO()))

    try:
        yield _fabricar
    finally:
        config.obtener_configuracion.cache_clear()
        dependencias.custodia_configurada.cache_clear()


@pytest.fixture
def con_dist(fabricar: Fabricar, dist: Path) -> TestClient:
    return fabricar(dist)


@pytest.fixture
def sin_dist(fabricar: Fabricar, tmp_path: Path) -> TestClient:
    return fabricar(tmp_path / "no-existe")


def _cabeceras(respuesta: httpx.Response, esperadas: dict[str, str]) -> None:
    for clave, valor in esperadas.items():
        assert respuesta.headers[clave] == valor, clave


def _problema_404(respuesta: httpx.Response) -> None:
    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    if respuesta.request.method != "HEAD":
        assert respuesta.json()["type"] == "/errores/no-encontrado"


# --- Las rutas de la app entregan el index.html ------------------------------------------------------


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("ruta", RUTAS_APP)
def test_las_rutas_de_la_app_entregan_el_index_con_sus_cabeceras(con_dist: TestClient, ruta: str) -> None:
    # Esta prueba falla sin MATU-58: /, /entrar e /insumos respondían 404 RFC 7807
    respuesta = con_dist.get(ruta)
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    _cabeceras(respuesta, CABECERAS_APP)
    # La CSP del build se entrega intacta en su etiqueta meta
    assert respuesta.text == HTML


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("ruta", RUTAS_APP)
def test_head_de_las_rutas_de_la_app_responde_200_sin_cuerpo(con_dist: TestClient, ruta: str) -> None:
    respuesta = con_dist.head(ruta)
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/html")
    _cabeceras(respuesta, CABECERAS_APP)
    assert respuesta.content == b""


@pytest.mark.rf("RF-37")
def test_la_barra_final_tambien_entrega_el_index(con_dist: TestClient) -> None:
    # ruteo.ts quita la barra final, así que /insumos/ es la misma pantalla
    respuesta = con_dist.get("/insumos/", follow_redirects=False)
    assert respuesta.status_code == 200
    assert respuesta.text == HTML


@pytest.mark.rf("RF-37")
def test_un_archivo_de_la_raiz_del_build_se_entrega_tal_cual(con_dist: TestClient) -> None:
    respuesta = con_dist.get("/manifest.webmanifest")
    assert respuesta.status_code == 200
    assert respuesta.text == MANIFIESTO
    assert not respuesta.headers["content-type"].startswith("text/html")
    _cabeceras(respuesta, CABECERAS_APP)


@pytest.mark.rf("RF-37")
def test_index_html_pedido_por_su_nombre_lleva_las_cabeceras_de_la_app(con_dist: TestClient) -> None:
    respuesta = con_dist.get("/index.html")
    assert respuesta.status_code == 200
    assert respuesta.text == HTML
    _cabeceras(respuesta, CABECERAS_APP)


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize(
    "ruta",
    [
        "/..%2Fajeno.txt",
        "/..%2F..%2Fajeno.txt",
        "/%2E%2E%2Fajeno.txt",
        "/assets%2F..%2F..%2Fajeno.txt",
        "/..%5Cajeno.txt",
    ],
)
def test_una_ruta_con_punto_punto_nunca_sale_del_build(con_dist: TestClient, ruta: str) -> None:
    respuesta = con_dist.get(ruta)
    assert AJENO not in respuesta.text
    # Un segmento .. es oculto, y ajeno.txt tiene extensión: 404, ni el archivo ni el index.html
    assert respuesta.status_code == 404
    assert HTML not in respuesta.text


@pytest.mark.rf("RF-37")
def test_archivo_del_build_solo_devuelve_archivos_de_adentro(dist: Path) -> None:
    assert archivo_del_build(dist, "manifest.webmanifest") == (dist / "manifest.webmanifest").resolve()
    assert archivo_del_build(dist, "assets/index-abc123.js") == (dist / "assets" / "index-abc123.js").resolve()
    ajeno = dist.parent / "ajeno.txt"
    for ruta in ["../ajeno.txt", "assets/../../ajeno.txt", str(ajeno), str(ajeno).replace("\\", "/")]:
        assert archivo_del_build(dist, ruta) is None, ruta
    # Carpetas, vacíos, barra invertida, byte nulo y ocultos
    for ruta in ["", "assets", "..\\ajeno.txt", "manifest.webmanifest\x00", ".vite/manifest.json", "assets/.oculto.js"]:
        assert archivo_del_build(dist, ruta) is None, repr(ruta)


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("ruta", ["/favicon.ico", "/sw.js", "/ficha/foto.png", "/favicon.ico/", "/robots.txt"])
def test_una_ruta_con_extension_que_no_esta_en_el_build_responde_404(con_dist: TestClient, ruta: str) -> None:
    # H2 de la QA: antes respondía 200 con el index.html
    for respuesta in (con_dist.get(ruta), con_dist.head(ruta)):
        _problema_404(respuesta)
        _cabeceras(respuesta, CABECERAS_APP)
        assert HTML not in respuesta.text


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize(
    "ruta", ["/.vite/manifest.json", "/.vite", "/.vite/", "/.env", "/ficha/.algo", "/assets/.oculto.js"]
)
def test_un_archivo_oculto_del_build_nunca_se_sirve(con_dist: TestClient, ruta: str) -> None:
    # H4 de la QA: /.vite/manifest.json se servía tal cual
    respuesta = con_dist.get(ruta)
    assert respuesta.status_code == 404
    assert respuesta.headers["content-type"].startswith(PROBLEMA)
    assert HTML not in respuesta.text
    assert JS not in respuesta.text


@pytest.mark.rf("RF-37")
def test_los_assets_js_y_css_llevan_su_tipo_aunque_el_sistema_diga_otro(fabricar: Fabricar, dist: Path) -> None:
    # H1 de la QA: en Windows mimetypes toma el tipo del registro y .js puede salir text/plain, que el
    # navegador rechaza para un módulo. Aquí se simula ese registro antes de crear la app
    for extension in (".js", ".css", ".webmanifest"):
        mimetypes.add_type("text/plain", extension)
    try:
        cliente = fabricar(dist)
        tipos = {
            "/assets/index-abc123.js": "text/javascript",
            "/assets/index-abc123.css": "text/css",
            "/manifest.webmanifest": "application/manifest+json",
        }
        for ruta, tipo in tipos.items():
            respuesta = cliente.get(ruta)
            assert respuesta.status_code == 200
            assert respuesta.headers["content-type"].split(";")[0] == tipo, ruta
    finally:
        mimetypes.add_type("text/javascript", ".js")
        mimetypes.add_type("text/css", ".css")
        mimetypes.add_type("application/manifest+json", ".webmanifest")


@pytest.mark.rf("RF-37")
def test_ruta_oculta_y_ruta_que_parece_archivo() -> None:
    for ruta in ["/.vite/manifest.json", "/a/.b", "/..", "/.env", "assets/.x.js"]:
        assert es_ruta_oculta(ruta), ruta
    for ruta in ["/", "/entrar", "/ficha/su-dia", "/assets/index-abc123.js", "/a.b/c"]:
        assert not es_ruta_oculta(ruta), ruta
    for ruta in ["/favicon.ico", "/ficha/foto.png", "/sw.js/", "/manifest.webmanifest"]:
        assert parece_archivo(ruta), ruta
    for ruta in ["/", "/entrar", "/ficha/su-dia", "/a.b/c", "/entrar/recuperar/codigo"]:
        assert not parece_archivo(ruta), ruta


@pytest.mark.rf("RF-37")
def test_el_respaldo_solo_reconoce_las_rutas_de_la_app() -> None:
    for ruta in ["/", "/entrar", "/insumos", "/ficha/su-dia", "/registro", "/rr", "/v1x", "/r/algo", "/docsx"]:
        assert es_ruta_de_la_app(ruta), ruta
    for ruta in ["/v1", "/v1/", "/v1/salud", "/r", "/r/", "/assets", "/assets/x.js", "/docs", "/docs/oauth2-redirect"]:
        assert not es_ruta_de_la_app(ruta), ruta
    for ruta in ["/openapi.json", "/openapi.json/"]:
        assert not es_ruta_de_la_app(ruta), ruta


# --- Lo demás no cambia ------------------------------------------------------------------------------


@pytest.mark.rf("RF-06")
def test_r_sigue_igual(con_dist: TestClient) -> None:
    respuesta = con_dist.get("/r")
    assert respuesta.status_code == 200
    assert respuesta.text == HTML
    _cabeceras(respuesta, CABECERAS_RELEVO)
    # Desde MATU-58 tampoco se puede incrustar (decisión 115)
    assert respuesta.headers["content-security-policy"] == "frame-ancestors 'none'"
    # /r/ redirige a /r, como antes, y HEAD /r sigue sin estar permitido
    barra = con_dist.get("/r/", follow_redirects=False)
    assert barra.status_code == 307
    assert barra.headers["location"].endswith("/r")
    assert con_dist.head("/r").status_code == 405


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("ruta", ["/v1/no-existe", "/v1", "/v1/personas-cuidadas/x/no-existe"])
def test_una_ruta_v1_inexistente_sigue_en_404_problem_json(con_dist: TestClient, ruta: str) -> None:
    _problema_404(con_dist.get(ruta))
    _problema_404(con_dist.head(ruta))


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize(("metodo", "ruta"), [("GET", "/v1/sesiones"), ("PUT", "/v1/salud"), ("HEAD", "/v1/sesiones")])
def test_un_metodo_no_permitido_en_v1_sigue_en_405(con_dist: TestClient, metodo: str, ruta: str) -> None:
    respuesta = con_dist.request(metodo, ruta)
    assert respuesta.status_code == 405
    assert respuesta.headers["content-type"].startswith(PROBLEMA)


@pytest.mark.rf("RF-37")
def test_la_api_y_su_barra_final_no_cambian(con_dist: TestClient) -> None:
    assert con_dist.get("/v1/salud").json() == {"estado": "ok"}
    barra = con_dist.get("/v1/salud/", follow_redirects=False)
    assert barra.status_code == 307
    assert barra.headers["location"].endswith("/v1/salud")


@pytest.mark.rf("RF-37")
def test_una_ruta_registrada_despues_no_queda_tapada(fabricar: Fabricar, dist: Path) -> None:
    # El respaldo es el destino por omisión del enrutador, no una ruta comodín: lo que se registre después
    # de crear la app (las pruebas lo hacen, y un router nuevo podría) responde lo suyo
    cliente = fabricar(dist)
    app = cliente.app
    assert isinstance(app, FastAPI)

    @app.get("/prueba-despues/{item}")
    def ruta_despues(item: str) -> dict[str, str]:
        return {"item": item}

    assert cliente.get("/prueba-despues/x").json() == {"item": "x"}
    assert cliente.post("/prueba-despues/x").status_code == 405
    assert cliente.get("/otra").text == HTML


@pytest.mark.rf("RF-37")
def test_otro_metodo_en_una_ruta_de_la_app_sigue_en_404(con_dist: TestClient) -> None:
    # El respaldo solo atiende GET y HEAD: un POST a /entrar responde como antes
    _problema_404(con_dist.post("/entrar", json={}))


@pytest.mark.rf("RF-37")
def test_un_asset_se_entrega_y_uno_inexistente_no_cae_en_el_index(con_dist: TestClient) -> None:
    respuesta = con_dist.get("/assets/index-abc123.js")
    assert respuesta.status_code == 200
    assert respuesta.text == JS
    assert "etag" in respuesta.headers
    assert respuesta.headers.get("cache-control") not in ("no-store", "no-cache")
    falta = con_dist.get("/assets/no-existe.js")
    assert falta.status_code == 404
    assert HTML not in falta.text


@pytest.mark.rf("RF-37")
def test_sin_dist_la_api_arranca_y_la_app_responde_404_problem_json(sin_dist: TestClient) -> None:
    for ruta in ["/", "/entrar", "/insumos"]:
        respuesta = sin_dist.get(ruta)
        _problema_404(respuesta)
        _cabeceras(respuesta, CABECERAS_APP)
    _problema_404(sin_dist.get("/assets/index-abc123.js"))
    assert sin_dist.get("/v1/salud").json() == {"estado": "ok"}


# --- La documentación solo en local y pruebas --------------------------------------------------------


@pytest.mark.rf("RF-37")
def test_la_lista_de_entornos_con_documentacion() -> None:
    assert ENTORNOS_DOCUMENTACION == {"local", "pruebas"}


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("entorno", ["staging", "produccion"])
@pytest.mark.parametrize("ruta", ["/docs", "/docs/", "/openapi.json", "/openapi.json/", "/docs/oauth2-redirect"])
def test_la_documentacion_responde_404_en_staging_y_produccion(
    fabricar: Fabricar, dist: Path, entorno: str, ruta: str
) -> None:
    # Esta prueba falla sin MATU-58 en staging: /docs y /openapi.json respondían 200
    cliente = fabricar(dist, entorno)
    respuesta = cliente.get(ruta)
    # El 404 de la API, no el index.html de la app
    _problema_404(respuesta)
    assert HTML not in respuesta.text
    # La app sí se entrega en ese entorno
    assert cliente.get("/insumos").text == HTML


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("entorno", ["local", "pruebas"])
def test_la_documentacion_responde_200_en_local_y_pruebas(fabricar: Fabricar, dist: Path, entorno: str) -> None:
    cliente = fabricar(dist, entorno)
    docs = cliente.get("/docs")
    assert docs.status_code == 200
    assert HTML not in docs.text
    esquema = cliente.get("/openapi.json")
    assert esquema.status_code == 200
    assert "/v1/salud" in esquema.json()["paths"]
    # El respaldo no aparece en el contrato
    assert "/{ruta}" not in esquema.json()["paths"]


# --- El version.json del build (MATU-67, decisión 172) -----------------------------------------------

VERSION = '{"version": "sintetica-abc123"}'
CABECERAS_VERSION = {**CABECERAS_APP, "cache-control": "no-store"}


@pytest.fixture
def dist_con_version(dist: Path) -> Path:
    (dist / "version.json").write_text(VERSION, encoding="utf-8")
    return dist


@pytest.mark.rf("RF-37")
@pytest.mark.parametrize("ruta", ["/version.json", "/version.json/"])
def test_version_json_se_entrega_con_no_store(fabricar: Fabricar, dist_con_version: Path, ruta: str) -> None:
    # Esta prueba falla sin MATU-67: se entregaba con no-cache, como cualquier archivo de la raíz del build
    cliente = fabricar(dist_con_version)
    respuesta = cliente.get(ruta)
    assert respuesta.status_code == 200
    assert respuesta.text == VERSION
    assert respuesta.headers["content-type"].split(";")[0] == "application/json"
    _cabeceras(respuesta, CABECERAS_VERSION)
    cabeza = cliente.head(ruta)
    assert cabeza.status_code == 200
    assert cabeza.content == b""
    _cabeceras(cabeza, CABECERAS_VERSION)


@pytest.mark.rf("RF-37")
def test_version_json_no_pide_sesion(fabricar: Fabricar, dist_con_version: Path) -> None:
    # Sin cookie ni access token, y con uno inválido, responde igual: no pasa por ninguna dependencia de sesión
    cliente = fabricar(dist_con_version)
    cliente.cookies.clear()
    assert cliente.get("/version.json").text == VERSION
    respuesta = cliente.get("/version.json", headers={"Authorization": "Bearer no-es-un-token"})
    assert respuesta.status_code == 200
    assert respuesta.text == VERSION


@pytest.mark.rf("RF-37")
def test_sin_version_json_responde_404_y_no_el_index(con_dist: TestClient) -> None:
    # El build existe con su index.html, pero sin version.json (desarrollo sin build nuevo)
    for respuesta in (con_dist.get("/version.json"), con_dist.head("/version.json")):
        _problema_404(respuesta)
        _cabeceras(respuesta, CABECERAS_VERSION)
        assert HTML not in respuesta.text


@pytest.mark.rf("RF-37")
def test_sin_build_version_json_responde_404(sin_dist: TestClient) -> None:
    respuesta = sin_dist.get("/version.json")
    _problema_404(respuesta)
    _cabeceras(respuesta, CABECERAS_VERSION)


@pytest.mark.rf("RF-37")
def test_con_version_json_los_demas_archivos_no_cambian_su_cache(fabricar: Fabricar, dist_con_version: Path) -> None:
    cliente = fabricar(dist_con_version)
    for ruta in ["/", "/insumos", "/index.html"]:
        indice = cliente.get(ruta)
        assert indice.text == HTML
        _cabeceras(indice, CABECERAS_APP)
    _cabeceras(cliente.get("/manifest.webmanifest"), CABECERAS_APP)
    asset = cliente.get("/assets/index-abc123.js")
    assert asset.status_code == 200
    assert "etag" in asset.headers
    assert asset.headers.get("cache-control") not in ("no-store", "no-cache")
    _cabeceras(cliente.get("/r"), CABECERAS_RELEVO)
    # Un version.json fuera de la raíz no es el del build: sigue la regla de los archivos que no están
    _problema_404(cliente.get("/ficha/version.json"))

"""MATU-25 · La IP del cliente detrás del borde de Railway, con PROXY_SALTOS (decisión 114, punto 7).

Hallazgo de Martín en staging (05-11): Railway entrega ``X-Forwarded-For: <cliente>, <borde>`` y el borde se
turna entre varios servidores. Con el algoritmo de Uvicorn el límite contaba por servidor de borde. Con
PROXY_SALTOS=N la IP es ``xff[-(N+1)]``, nunca la primera de la lista, y ante una lista corta o mal formada
cuenta la IP del socket.

Pruebas unitarias de la selección, de la clase de cada elemento y del middleware ASGI, sin la API. Solo IP
sintéticas: de documentación (RFC 5737, RFC 3849), privadas y del espacio compartido (RFC 6598).
"""

import asyncio
from typing import Any

import pytest
from starlette.types import Receive, Scope, Send
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.proxy import (
    SALTOS_MAXIMOS,
    MiddlewareProxy,
    clase_de,
    elementos_xff,
    es_de_confianza,
    ip_tras_saltos,
    redes_de,
)

pytestmark = pytest.mark.rf("RF-37")

RAILWAY = ["100.64.0.0/10"]
PROXY = "100.64.0.7"
CLIENTE = "203.0.113.9"
BORDE_1 = "198.51.100.1"
BORDE_2 = "198.51.100.2"
CLIENTE_12 = "203.0.113.12"


# --- La selección: xff[-(N+1)] -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("elementos", "saltos", "esperada"),
    [
        ([CLIENTE, BORDE_1], 1, CLIENTE),
        ([CLIENTE, BORDE_2], 1, CLIENTE),
        # Railway concatena lo que mandó el cliente: la falsa queda a la izquierda y no se toma
        (["198.51.100.77", CLIENTE, BORDE_1], 1, CLIENTE),
        (["192.0.2.1", "192.0.2.2", CLIENTE, BORDE_1], 1, CLIENTE),
        # Lo que queda a la izquierda de la cola se ignora por completo, sea lo que sea (P2-1 de la QA):
        # una basura antepuesta no manda al cliente al contador compartido del proxy
        (["basura", CLIENTE_12, BORDE_1], 1, CLIENTE_12),
        (["", f"{CLIENTE_12}:80", "[2001:db8::9]:443", "basura", CLIENTE, BORDE_1], 1, CLIENTE),
        (["basura", CLIENTE, "198.51.100.50", BORDE_1], 2, CLIENTE),
        (["basura", CLIENTE], 0, CLIENTE),
        ([CLIENTE, "198.51.100.50", BORDE_1], 2, CLIENTE),
        ([CLIENTE], 0, CLIENTE),
        ([CLIENTE, BORDE_1], 0, BORDE_1),
        # Normalizada: una misma IPv6 escrita de dos formas es una sola
        (["2001:DB8:0:0::9", BORDE_1], 1, "2001:db8::9"),
    ],
)
def test_ip_tras_saltos_toma_la_que_queda_a_la_izquierda_de_los_saltos(
    elementos: list[str], saltos: int, esperada: str
) -> None:
    assert ip_tras_saltos(elementos, saltos) == esperada


@pytest.mark.parametrize(
    ("elementos", "saltos"),
    [
        # Menos saltos que IP: la lista no alcanza, cuenta el socket
        ([BORDE_1], 1),
        ([], 1),
        ([], 0),
        ([CLIENTE, BORDE_1], 2),
        ([CLIENTE, "198.51.100.50", BORDE_1], SALTOS_MAXIMOS),
        # Mal formada dentro de la cola (el cliente y los saltos)
        (["basura", BORDE_1], 1),
        ([CLIENTE_12, "basura"], 1),
        (["192.0.2.1", CLIENTE_12, "basura"], 1),
        ([CLIENTE, "basura", BORDE_1], 2),
        ([f"{CLIENTE}:443", BORDE_1], 1),
        (["[2001:db8::9]:443", BORDE_1], 1),
        (["", BORDE_1], 1),
        ([CLIENTE, "", BORDE_1], 1),
        ([CLIENTE, "203.0.113.256"], 1),
    ],
)
def test_ip_tras_saltos_con_lista_corta_o_mal_formada_no_elige(elementos: list[str], saltos: int) -> None:
    assert ip_tras_saltos(elementos, saltos) is None


def test_ip_tras_saltos_no_acepta_saltos_negativos() -> None:
    with pytest.raises(ValueError):
        ip_tras_saltos([CLIENTE], -1)


def test_elementos_xff_une_varias_cabeceras_en_orden() -> None:
    assert elementos_xff([]) == []
    assert elementos_xff([b""]) == [""]
    assert elementos_xff([f" {CLIENTE} ,{BORDE_1}".encode()]) == [CLIENTE, BORDE_1]
    assert elementos_xff([b"192.0.2.1", f"{CLIENTE}, {BORDE_1}".encode()]) == ["192.0.2.1", CLIENTE, BORDE_1]


@pytest.mark.parametrize(
    ("elemento", "clase"),
    [
        ("100.64.0.7", "interna"),
        ("100.127.255.254", "interna"),
        ("10.1.2.3", "privada"),
        ("192.168.0.10", "privada"),
        ("127.0.0.1", "privada"),
        ("fd12::1", "privada"),
        # Las de documentación no son globales
        (CLIENTE, "privada"),
        ("2001:db8::9", "privada"),
        # Un resolvedor público conocido, no la IP de una persona
        ("8.8.8.8", "publica"),
        ("2001:4860:4860::8888", "publica"),
        ("basura", "invalida"),
        ("", "invalida"),
        (f"{CLIENTE}:443", "invalida"),
    ],
)
def test_clase_de_cada_elemento(elemento: str, clase: str) -> None:
    assert clase_de(elemento) == clase


def test_es_de_confianza_solo_ips_dentro_de_las_redes() -> None:
    redes = redes_de(RAILWAY + ["10.0.0.5"])
    assert es_de_confianza(PROXY, redes)
    assert es_de_confianza("10.0.0.5", redes)
    assert not es_de_confianza("10.0.0.6", redes)
    assert not es_de_confianza(CLIENTE, redes)
    assert not es_de_confianza("testclient", redes)
    assert not es_de_confianza(None, redes)
    assert not es_de_confianza("", redes)


# --- El middleware ASGI --------------------------------------------------------------------------------


def _scope(socket: str | None, *cabeceras: tuple[str, str], tipo: str = "http") -> dict[str, Any]:
    return {
        "type": tipo,
        "scheme": "http" if tipo == "http" else "ws",
        "client": (socket, 40000) if socket is not None else None,
        "headers": [(nombre.lower().encode("latin-1"), valor.encode("latin-1")) for nombre, valor in cabeceras],
    }


def _pasar(middleware_de: Any, scope: dict[str, Any]) -> dict[str, Any]:
    """Pasa el scope por el middleware y devuelve el scope que vio la app."""
    vistos: list[dict[str, Any]] = []

    async def app(scope_app: Scope, receive: Receive, send: Send) -> None:
        vistos.append(dict(scope_app))

    async def receive() -> Any:
        return {"type": "http.request"}

    async def send(mensaje: Any) -> None:
        pass

    asyncio.run(middleware_de(app)(scope, receive, send))
    return vistos[0]


def _matu(saltos: int, redes: list[str] | None = None) -> Any:
    return lambda app: MiddlewareProxy(app, redes=redes or RAILWAY, saltos=saltos)


@pytest.mark.parametrize(
    "xff", [f"{CLIENTE}, {BORDE_1}", f"198.51.100.77, {CLIENTE}, {BORDE_2}", f"basura, {CLIENTE}, {BORDE_1}"]
)
def test_con_un_salto_el_cliente_es_el_que_queda_antes_del_borde(xff: str) -> None:
    visto = _pasar(_matu(1), _scope(PROXY, ("X-Forwarded-For", xff)))
    assert visto["client"] == (CLIENTE, 0)


@pytest.mark.parametrize(
    "cabeceras",
    [
        (),
        (("X-Forwarded-For", BORDE_1),),
        (("X-Forwarded-For", ""),),
        (("X-Forwarded-For", f"{CLIENTE}, basura"),),
        (("X-Forwarded-For", f"basura, {BORDE_1}"),),
        (("X-Forwarded-For", f"{CLIENTE}:5000, {BORDE_1}"),),
    ],
)
def test_con_un_salto_y_lista_corta_o_mal_formada_cuenta_el_socket(cabeceras: tuple[tuple[str, str], ...]) -> None:
    visto = _pasar(_matu(1), _scope(PROXY, *cabeceras))
    assert visto["client"] == (PROXY, 40000)


@pytest.mark.parametrize("saltos", [0, 1, 2])
def test_un_origen_no_confiable_ignora_x_forwarded_for_y_x_forwarded_proto(saltos: int) -> None:
    cabeceras = (("X-Forwarded-For", f"192.0.2.1, {CLIENTE}, {BORDE_1}"), ("X-Forwarded-Proto", "https"))
    for socket in (CLIENTE, "10.0.0.5", "testclient", None):
        visto = _pasar(_matu(saltos), _scope(socket, *cabeceras))
        assert visto["client"] == ((socket, 40000) if socket is not None else None)
        assert visto["scheme"] == "http"


def test_con_un_salto_x_forwarded_proto_como_uvicorn() -> None:
    assert _pasar(_matu(1), _scope(PROXY, ("X-Forwarded-Proto", "https")))["scheme"] == "https"
    assert _pasar(_matu(1), _scope(PROXY, ("X-Forwarded-Proto", "https"), tipo="websocket"))["scheme"] == "wss"
    assert _pasar(_matu(1), _scope(PROXY, ("X-Forwarded-Proto", "gopher")))["scheme"] == "http"
    assert _pasar(_matu(1), _scope(PROXY, ("X-Forwarded-Proto", "http"), ("X-Forwarded-Proto", "https")))[
        "scheme"
    ] == "https"


def test_lifespan_pasa_sin_cambios() -> None:
    scope = {"type": "lifespan"}
    assert _pasar(_matu(1), scope) == {"type": "lifespan"}


def test_saltos_fuera_de_rango_no_arma_el_middleware() -> None:
    for saltos in (-1, SALTOS_MAXIMOS + 1):
        with pytest.raises(ValueError):
            MiddlewareProxy(lambda *_: None, redes=RAILWAY, saltos=saltos)  # type: ignore[arg-type,return-value]


CASOS_UVICORN = [
    (PROXY, ()),
    (PROXY, (("X-Forwarded-For", f"{CLIENTE}, {BORDE_1}"),)),
    (PROXY, (("X-Forwarded-For", f"192.0.2.250, {CLIENTE}"),)),
    (PROXY, (("X-Forwarded-For", f"{CLIENTE}, 100.64.0.3"),)),
    (PROXY, (("X-Forwarded-For", "100.64.0.3, 100.64.0.4"),)),
    (PROXY, (("X-Forwarded-For", f"{CLIENTE}:5000"),)),
    (PROXY, (("X-Forwarded-For", "basura"),)),
    (PROXY, (("X-Forwarded-For", ""),)),
    (PROXY, (("X-Forwarded-For", "192.0.2.1"), ("X-Forwarded-For", CLIENTE))),
    (PROXY, (("X-Forwarded-Proto", "https"), ("X-Forwarded-For", CLIENTE))),
    (PROXY, (("X-Forwarded-Proto", "ftp"),)),
    (CLIENTE, (("X-Forwarded-For", "192.0.2.1"), ("X-Forwarded-Proto", "https"))),
    ("testclient", (("X-Forwarded-For", "192.0.2.1"),)),
    (None, (("X-Forwarded-For", "192.0.2.1"),)),
]


@pytest.mark.parametrize(("socket", "cabeceras"), CASOS_UVICORN)
@pytest.mark.parametrize("tipo", ["http", "websocket"])
def test_con_cero_saltos_el_resultado_es_el_de_uvicorn(
    socket: str | None, cabeceras: tuple[tuple[str, str], ...], tipo: str
) -> None:
    # PROXY_SALTOS=0 es el comportamiento de antes, exacto: el mismo ProxyHeadersMiddleware de Uvicorn
    matu = _pasar(_matu(0), _scope(socket, *cabeceras, tipo=tipo))
    uvicorn_de_antes = lambda app: ProxyHeadersMiddleware(app, trusted_hosts=RAILWAY)  # noqa: E731
    antes = _pasar(uvicorn_de_antes, _scope(socket, *cabeceras, tipo=tipo))
    assert (matu["client"], matu["scheme"]) == (antes["client"], antes["scheme"])

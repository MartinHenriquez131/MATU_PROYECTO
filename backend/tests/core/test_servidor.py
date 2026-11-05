"""MATU-25 · Arranque detrás del proxy: FORWARDED_ALLOW_IPS acotado, nunca '*' (decisión de Jorge, PR #27 P2-1),
y PROXY_SALTOS de 0 a 5 (decisión 114, punto 7)."""

from typing import Any, cast

import pytest
import uvicorn
from starlette.types import Receive, Scope, Send
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.proxy import MiddlewareProxy
from app.servidor import (
    ConfiguracionProxyInvalida,
    app_detras_del_proxy,
    ips_de_confianza,
    main,
    parametros_uvicorn,
    puerto,
    saltos_de_proxy,
)

pytestmark = pytest.mark.rf("RF-37")


@pytest.mark.parametrize("valor", [None, "", "   ", ","])
def test_sin_valor_solo_confia_en_127_0_0_1(valor: str | None) -> None:
    assert ips_de_confianza(valor) == ["127.0.0.1"]


def test_acepta_ips_y_redes_cidr_separadas_por_comas() -> None:
    assert ips_de_confianza("10.0.0.5, 100.64.0.0/10,fd12::/16") == ["10.0.0.5", "100.64.0.0/10", "fd12::/16"]


@pytest.mark.parametrize("valor", ["*", "10.0.0.1,*", "0.0.0.0/0", "::/0", "10.0.0.1, ::/0", "proxy.railway", "10.0.0"])
def test_rechaza_comodin_red_total_o_basura_sin_repetir_el_valor(valor: str) -> None:
    with pytest.raises(ConfiguracionProxyInvalida) as error:
        ips_de_confianza(valor)
    assert "FORWARDED_ALLOW_IPS" in str(error.value)
    assert valor not in str(error.value) or valor == "*"


async def _app_vacia(scope: Scope, receive: Receive, send: Send) -> None:
    pass


def test_parametros_de_uvicorn_con_proxy_y_sin_log_de_acceso() -> None:
    entorno = {"PORT": "8123", "FORWARDED_ALLOW_IPS": "10.0.0.5"}
    parametros = parametros_uvicorn(entorno)
    assert parametros["port"] == 8123
    # El proxy lo resuelve MiddlewareProxy con FORWARDED_ALLOW_IPS: el de Uvicorn queda apagado
    assert parametros["proxy_headers"] is False
    envuelta = app_detras_del_proxy(_app_vacia, entorno)
    assert [str(red) for red in envuelta.redes] == ["10.0.0.5/32"]
    assert envuelta.saltos == 0
    assert envuelta.diagnostico is False
    # uvicorn.access sigue apagado: sin log de acceso ni log_config que lo reactive
    assert parametros["access_log"] is False
    assert parametros["log_config"] is None


def test_uvicorn_no_agrega_su_proxy_encima_del_de_matu() -> None:
    # Con los dos, el X-Forwarded-For se leería dos veces y Uvicorn reescribiría la IP antes que MATU
    entorno = {"FORWARDED_ALLOW_IPS": "100.64.0.0/10", "PROXY_SALTOS": "1"}
    config = uvicorn.Config(app_detras_del_proxy(_app_vacia, entorno), **parametros_uvicorn(entorno))
    config.load()
    assert not isinstance(config.loaded_app, ProxyHeadersMiddleware)
    assert isinstance(config.loaded_app, MiddlewareProxy)
    assert cast(MiddlewareProxy, config.loaded_app).saltos == 1


def test_sin_variables_puerto_8000_y_proxy_local() -> None:
    parametros = parametros_uvicorn({})
    envuelta = app_detras_del_proxy(_app_vacia, {})
    assert (parametros["port"], [str(red) for red in envuelta.redes], envuelta.saltos) == (8000, ["127.0.0.1/32"], 0)


@pytest.mark.parametrize(("valor", "saltos"), [(None, 0), ("", 0), ("  ", 0), ("0", 0), ("1", 1), (" 2 ", 2), ("5", 5)])
def test_proxy_saltos_de_0_a_5_y_vacio_es_0(valor: str | None, saltos: int) -> None:
    assert saltos_de_proxy(valor) == saltos


@pytest.mark.parametrize("valor", ["6", "9", "10", "-1", "+1", "01", "1.0", "uno", "1,2", "１"])
def test_proxy_saltos_invalido_no_arranca_y_no_repite_el_valor(valor: str) -> None:
    with pytest.raises(ConfiguracionProxyInvalida) as error:
        saltos_de_proxy(valor)
    assert "PROXY_SALTOS" in str(error.value)
    assert valor not in str(error.value)


def test_app_detras_del_proxy_valida_proxy_saltos() -> None:
    with pytest.raises(ConfiguracionProxyInvalida):
        app_detras_del_proxy(_app_vacia, {"FORWARDED_ALLOW_IPS": "100.64.0.0/10", "PROXY_SALTOS": "7"})


@pytest.mark.parametrize("valor", ["0", "70000", "ochenta"])
def test_puerto_invalido_no_arranca(valor: str) -> None:
    with pytest.raises(ValueError):
        puerto(valor)


def _arrancar(monkeypatch: pytest.MonkeyPatch, variables: dict[str, str]) -> dict[str, Any]:
    """Corre servidor.main() con uvicorn.run reemplazado: devuelve la app y los parámetros que recibió."""
    from app.core import config

    llamada: dict[str, Any] = {}

    def run_falso(app: Any, **parametros: Any) -> None:
        llamada.update(app=app, parametros=parametros)

    monkeypatch.setattr(uvicorn, "run", run_falso)
    for nombre, valor in variables.items():
        monkeypatch.setenv(nombre, valor)
    config.obtener_configuracion.cache_clear()
    try:
        main()
    finally:
        config.obtener_configuracion.cache_clear()
    return llamada


def test_el_arranque_envuelve_la_app_con_proxy_saltos_y_el_diagnostico(
    monkeypatch: pytest.MonkeyPatch, configuracion_sin_env: None
) -> None:
    llamada = _arrancar(
        monkeypatch, {"FORWARDED_ALLOW_IPS": "100.64.0.0/10", "PROXY_SALTOS": "1", "DIAGNOSTICO_PROXY": "true"}
    )
    envuelta = llamada["app"]
    assert isinstance(envuelta, MiddlewareProxy)
    assert ([str(red) for red in envuelta.redes], envuelta.saltos, envuelta.diagnostico) == (
        ["100.64.0.0/10"], 1, True
    )
    assert llamada["parametros"]["proxy_headers"] is False


def test_el_arranque_sin_variables_del_proxy_queda_como_antes(
    monkeypatch: pytest.MonkeyPatch, configuracion_sin_env: None
) -> None:
    for nombre in ("FORWARDED_ALLOW_IPS", "PROXY_SALTOS"):
        monkeypatch.delenv(nombre, raising=False)
    envuelta = _arrancar(monkeypatch, {})["app"]
    assert ([str(red) for red in envuelta.redes], envuelta.saltos, envuelta.diagnostico) == (["127.0.0.1/32"], 0, False)


@pytest.mark.parametrize(
    "variables", [{"PROXY_SALTOS": "6"}, {"PROXY_SALTOS": "uno"}, {"FORWARDED_ALLOW_IPS": "*"}]
)
def test_el_arranque_con_una_variable_del_proxy_invalida_no_llega_a_uvicorn(
    monkeypatch: pytest.MonkeyPatch, configuracion_sin_env: None, variables: dict[str, str]
) -> None:
    with pytest.raises(ConfiguracionProxyInvalida):
        _arrancar(monkeypatch, variables)

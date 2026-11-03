"""MATU-25 · Arranque detrás del proxy: FORWARDED_ALLOW_IPS acotado, nunca '*' (decisión de Jorge, PR #27 P2-1)."""

import pytest

from app.servidor import ConfiguracionProxyInvalida, ips_de_confianza, parametros_uvicorn, puerto

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


def test_parametros_de_uvicorn_con_proxy_y_sin_log_de_acceso() -> None:
    parametros = parametros_uvicorn({"PORT": "8123", "FORWARDED_ALLOW_IPS": "10.0.0.5"})
    assert parametros["port"] == 8123
    assert parametros["proxy_headers"] is True
    assert parametros["forwarded_allow_ips"] == ["10.0.0.5"]
    # uvicorn.access sigue apagado: sin log de acceso ni log_config que lo reactive
    assert parametros["access_log"] is False
    assert parametros["log_config"] is None


def test_sin_variables_puerto_8000_y_proxy_local() -> None:
    parametros = parametros_uvicorn({})
    assert (parametros["port"], parametros["forwarded_allow_ips"]) == (8000, ["127.0.0.1"])


@pytest.mark.parametrize("valor", ["0", "70000", "ochenta"])
def test_puerto_invalido_no_arranca(valor: str) -> None:
    with pytest.raises(ValueError):
        puerto(valor)

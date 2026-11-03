"""MATU-25 · Detrás del proxy, cada persona cuenta con su IP (decisión de Jorge, PR #27 P2-1).

La app se envuelve exactamente como en staging: uvicorn.Config con los parámetros de app/servidor.py y
config.load(), que agrega el ProxyHeadersMiddleware de Uvicorn con FORWARDED_ALLOW_IPS. El TestClient fija
la IP del socket (el proxy o un cliente directo).

- Dos personas tras el proxy de confianza no comparten el contador del límite por IP ni la demora
  progresiva de la entrada (MATU-38).
- Un X-Forwarded-For enviado desde una IP que no es de confianza se ignora: cuenta la IP del socket.

Solo IP sintéticas de documentación (RFC 5737) y de redes privadas.
"""

from collections.abc import Iterator
from datetime import timedelta
from typing import Any, cast

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.limite_ip import clave_de
from app.modules.iam.domain.demora import PREFIJO_IP
from app.servidor import parametros_uvicorn
from app.shared.limite_ip import LIMITE_REGISTRO, huella
from tests.modules.iam.conftest import EntornoIam, requiere_base

pytestmark = pytest.mark.rf("RF-37")

PROXY = "10.0.0.5"
ANA = "198.51.100.1"
BETO = "198.51.100.2"
EXTRANO = "203.0.113.9"


def _cliente(entorno: EntornoIam, socket_ip: str, forwarded_allow_ips: str | None) -> TestClient:
    variables = {"PORT": "8080"}
    if forwarded_allow_ips is not None:
        variables["FORWARDED_ALLOW_IPS"] = forwarded_allow_ips
    config = uvicorn.Config(cast(FastAPI, entorno.cliente.app), **parametros_uvicorn(variables))
    config.load()
    return TestClient(config.loaded_app, client=(socket_ip, 40000), raise_server_exceptions=False)


@pytest.fixture
def clientes(entorno_iam: EntornoIam) -> Iterator[dict[str, TestClient]]:
    clientes = {
        "proxy": _cliente(entorno_iam, PROXY, PROXY),
        "directo": _cliente(entorno_iam, EXTRANO, PROXY),
        "proxy_sin_configurar": _cliente(entorno_iam, PROXY, None),
    }
    yield clientes
    for cliente in clientes.values():
        cliente.close()


def _registrar(cliente: TestClient, xff: str) -> Any:
    return cliente.post("/v1/usuarios", json={}, headers={"X-Forwarded-For": xff})


def _clave(entorno: EntornoIam, ip: str) -> str:
    return clave_de(LIMITE_REGISTRO, huella(entorno.pepper_limites, LIMITE_REGISTRO.prefijo, ip))


def _conteos(entorno: EntornoIam) -> dict[str, int]:
    assert entorno.limite_ip is not None
    return {clave: conteo for clave, (conteo, _) in entorno.limite_ip.datos.items()}


def test_dos_personas_tras_el_proxy_no_comparten_el_limite(
    entorno_iam: EntornoIam, clientes: dict[str, TestClient]
) -> None:
    proxy = clientes["proxy"]
    for _ in range(5):
        assert _registrar(proxy, ANA).status_code == 422
    assert _registrar(proxy, ANA).status_code == 429
    # Beto, tras el mismo proxy, sigue con su propio contador
    assert _registrar(proxy, BETO).status_code == 422
    assert _conteos(entorno_iam) == {_clave(entorno_iam, ANA): 6, _clave(entorno_iam, BETO): 1}


def test_con_varios_saltos_cuenta_la_ip_que_entrego_el_proxy(
    entorno_iam: EntornoIam, clientes: dict[str, TestClient]
) -> None:
    # Ana antepone una IP inventada: Uvicorn toma la última que no es de confianza, la que vio el proxy
    assert _registrar(clientes["proxy"], f"192.0.2.250, {ANA}").status_code == 422
    assert _conteos(entorno_iam) == {_clave(entorno_iam, ANA): 1}


def test_un_x_forwarded_for_de_un_cliente_no_confiable_se_ignora(
    entorno_iam: EntornoIam, clientes: dict[str, TestClient]
) -> None:
    directo = clientes["directo"]
    # Cambia el X-Forwarded-For en cada intento para parecer otra persona: no le sirve
    for numero in range(5):
        assert _registrar(directo, f"198.51.100.{100 + numero}").status_code == 422
    assert _registrar(directo, BETO).status_code == 429
    assert _conteos(entorno_iam) == {_clave(entorno_iam, EXTRANO): 6}


def test_sin_forwarded_allow_ips_el_proxy_no_es_de_confianza_y_cuenta_su_ip(
    entorno_iam: EntornoIam, clientes: dict[str, TestClient]
) -> None:
    # Por omisión (127.0.0.1) se ignora el X-Forwarded-For: más estricto, nunca más permisivo
    sin_configurar = clientes["proxy_sin_configurar"]
    assert _registrar(sin_configurar, ANA).status_code == 422
    assert _registrar(sin_configurar, BETO).status_code == 422
    assert _conteos(entorno_iam) == {_clave(entorno_iam, PROXY): 2}


CONTRASENA_INCORRECTA = "incorrecta-1"  # pragma: allowlist secret


def _entrar(cliente: TestClient, xff: str, email: str) -> Any:
    return cliente.post(
        "/v1/sesiones", json={"email": email, "contrasena": CONTRASENA_INCORRECTA}, headers={"X-Forwarded-For": xff}
    )


@requiere_base
def test_dos_personas_tras_el_proxy_no_comparten_la_demora_de_la_entrada(
    entorno_iam: EntornoIam, clientes: dict[str, TestClient]
) -> None:
    # 21 fallos de Ana en la ventana (umbral de la IP: 20): Ana espera 30 s
    huella_ana = huella(entorno_iam.pepper_limites, PREFIJO_IP, ANA)
    for _ in range(21):
        entorno_iam.contadores.sumar_fallo(huella_ana, entorno_iam.reloj.ahora())
    entorno_iam.reloj.avanzar(timedelta(seconds=1))

    proxy = clientes["proxy"]
    ana = _entrar(proxy, ANA, "ana.sintetica@ejemplo.cl")
    assert ana.status_code == 429
    assert ana.headers["retry-after"] == "29"
    # Beto, tras el mismo proxy y con otro email, no hereda la espera de Ana
    assert _entrar(proxy, BETO, "beto.sintetico@ejemplo.cl").status_code == 401
    # Y quien conecta directo no puede hacerse pasar por Beto ni por Ana: cuenta su propia IP
    assert _entrar(clientes["directo"], ANA, "otro.sintetico@ejemplo.cl").status_code == 401
    huella_beto = huella(entorno_iam.pepper_limites, PREFIJO_IP, BETO)
    huella_extrano = huella(entorno_iam.pepper_limites, PREFIJO_IP, EXTRANO)
    assert entorno_iam.contadores.leer(huella_beto).fallos == 1
    assert entorno_iam.contadores.leer(huella_extrano).fallos == 1
    assert entorno_iam.contadores.leer(huella_ana).fallos == 21

"""MATU-25 · Detrás del proxy, cada persona cuenta con su IP (decisión de Jorge, PR #27 P2-1).

La app se envuelve exactamente como en staging: app_detras_del_proxy (MiddlewareProxy con
FORWARDED_ALLOW_IPS y PROXY_SALTOS) dentro de uvicorn.Config con los parámetros de app/servidor.py y
config.load(). El TestClient fija la IP del socket (el proxy o un cliente directo).

- Dos personas tras el proxy de confianza no comparten el contador del límite por IP ni la demora
  progresiva de la entrada (MATU-38).
- Un X-Forwarded-For enviado desde una IP que no es de confianza se ignora: cuenta la IP del socket.
- PROXY_SALTOS=1 (decisión 114, punto 7, hallazgo de Martín del 05-11): Railway entrega
  ``<cliente>, <borde>`` y el borde se turna. Cuenta el cliente, no el borde, y una IP falsa antepuesta
  no cambia nada. Con PROXY_SALTOS=0 (las primeras pruebas) todo sigue como antes.
- El diagnóstico (DIAGNOSTICO_PROXY) registra cantidades y clases, nunca una IP.

Solo IP sintéticas de documentación (RFC 5737, RFC 3849), de redes privadas y del espacio compartido.
"""

import json
from collections.abc import Iterator
from datetime import timedelta
from typing import Any, cast

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.limite_ip import clave_de
from app.modules.iam.domain.demora import PREFIJO_IP
from app.servidor import app_detras_del_proxy, parametros_uvicorn
from app.shared.limite_ip import LIMITE_REGISTRO, huella
from tests.modules.iam.conftest import EntornoIam, requiere_base

pytestmark = pytest.mark.rf("RF-37")

PROXY = "10.0.0.5"
ANA = "198.51.100.1"
BETO = "198.51.100.2"
EXTRANO = "203.0.113.9"


def _cliente(
    entorno: EntornoIam,
    socket_ip: str,
    forwarded_allow_ips: str | None,
    proxy_saltos: str | None = None,
    diagnostico: bool = False,
) -> TestClient:
    variables = {"PORT": "8080"}
    if forwarded_allow_ips is not None:
        variables["FORWARDED_ALLOW_IPS"] = forwarded_allow_ips
    if proxy_saltos is not None:
        variables["PROXY_SALTOS"] = proxy_saltos
    app = app_detras_del_proxy(cast(FastAPI, entorno.cliente.app), variables, diagnostico)
    config = uvicorn.Config(app, **parametros_uvicorn(variables))
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


# --- PROXY_SALTOS=1: detrás del borde de Railway (decisión 114, punto 7) --------------------------------

RED_RAILWAY = "100.64.0.0/10"
PROXY_RAILWAY = "100.64.0.7"
CLIENTE = "203.0.113.9"
OTRO_CLIENTE = "203.0.113.10"
BORDE_1 = "198.51.100.1"
BORDE_2 = "198.51.100.2"


@pytest.fixture
def railway(entorno_iam: EntornoIam) -> Iterator[dict[str, TestClient]]:
    clientes = {
        "proxy": _cliente(entorno_iam, PROXY_RAILWAY, RED_RAILWAY, "1"),
        "directo": _cliente(entorno_iam, CLIENTE, RED_RAILWAY, "1"),
        "diagnostico": _cliente(entorno_iam, PROXY_RAILWAY, RED_RAILWAY, "1", diagnostico=True),
        "diagnostico_directo": _cliente(entorno_iam, CLIENTE, RED_RAILWAY, "1", diagnostico=True),
    }
    yield clientes
    for cliente in clientes.values():
        cliente.close()


def test_con_un_salto_los_bordes_que_se_turnan_no_reparten_el_limite(
    entorno_iam: EntornoIam, railway: dict[str, TestClient]
) -> None:
    # El hallazgo de Martín: con el borde a la derecha, cada borde llevaba su propio contador
    bordes = [BORDE_1, BORDE_2]
    for intento in range(5):
        assert _registrar(railway["proxy"], f"{CLIENTE}, {bordes[intento % 2]}").status_code == 422
    sexto = _registrar(railway["proxy"], f"{CLIENTE}, {bordes[5 % 2]}")
    assert sexto.status_code == 429
    assert "retry-after" in sexto.headers
    assert _conteos(entorno_iam) == {_clave(entorno_iam, CLIENTE): 6}


def test_con_un_salto_una_ip_falsa_antepuesta_no_cambia_el_contador(
    entorno_iam: EntornoIam, railway: dict[str, TestClient]
) -> None:
    # Si Railway concatena lo que manda el cliente, la primera de la lista es inventada: nunca se toma
    for intento in range(5):
        assert _registrar(railway["proxy"], f"198.51.100.{77 + intento}, {CLIENTE}, {BORDE_1}").status_code == 422
    assert _registrar(railway["proxy"], f"198.51.100.99, {CLIENTE}, {BORDE_1}").status_code == 429
    assert _conteos(entorno_iam) == {_clave(entorno_iam, CLIENTE): 6}


def test_con_un_salto_dos_clientes_tras_el_mismo_borde_no_comparten_el_limite(
    entorno_iam: EntornoIam, railway: dict[str, TestClient]
) -> None:
    for _ in range(5):
        assert _registrar(railway["proxy"], f"{CLIENTE}, {BORDE_1}").status_code == 422
    assert _registrar(railway["proxy"], f"{CLIENTE}, {BORDE_1}").status_code == 429
    assert _registrar(railway["proxy"], f"{OTRO_CLIENTE}, {BORDE_1}").status_code == 422
    assert _conteos(entorno_iam) == {_clave(entorno_iam, CLIENTE): 6, _clave(entorno_iam, OTRO_CLIENTE): 1}


@pytest.mark.parametrize("xff", [BORDE_1, "", f"basura, {CLIENTE}, {BORDE_1}", f"{CLIENTE}:5000, {BORDE_1}"])
def test_con_un_salto_y_menos_ip_que_saltos_o_mal_formada_cuenta_el_proxy(
    entorno_iam: EntornoIam, railway: dict[str, TestClient], xff: str
) -> None:
    # Lo más estricto: la IP del socket, que comparten todos los que llegan así
    assert _registrar(railway["proxy"], xff).status_code == 422
    assert _conteos(entorno_iam) == {_clave(entorno_iam, PROXY_RAILWAY): 1}


def test_con_un_salto_un_origen_no_confiable_cuenta_su_socket(
    entorno_iam: EntornoIam, railway: dict[str, TestClient]
) -> None:
    directo = railway["directo"]
    for intento in range(5):
        assert _registrar(directo, f"198.51.100.{100 + intento}, {BORDE_1}").status_code == 422
    assert _registrar(directo, f"{OTRO_CLIENTE}, {BORDE_1}").status_code == 429
    assert _conteos(entorno_iam) == {_clave(entorno_iam, CLIENTE): 6}


@requiere_base
def test_con_un_salto_la_demora_de_la_entrada_cuenta_al_cliente(
    entorno_iam: EntornoIam, railway: dict[str, TestClient]
) -> None:
    # La demora de MATU-38 lee la misma IP que fija el middleware, no la del borde
    proxy = railway["proxy"]
    assert _entrar(proxy, f"{CLIENTE}, {BORDE_1}", "ana.sintetica@ejemplo.cl").status_code == 401
    assert _entrar(proxy, f"192.0.2.7, {CLIENTE}, {BORDE_2}", "beto.sintetico@ejemplo.cl").status_code == 401
    assert entorno_iam.contadores.leer(huella(entorno_iam.pepper_limites, PREFIJO_IP, CLIENTE)).fallos == 2
    for borde in (BORDE_1, BORDE_2):
        assert entorno_iam.contadores.leer(huella(entorno_iam.pepper_limites, PREFIJO_IP, borde)).fallos == 0


# --- El diagnóstico (DIAGNOSTICO_PROXY): condiciones 1 y 3 del analista normativo -------------------------

# Cada IP usada, completa y truncada: ninguna aparece en el log
IP_PROHIBIDAS = (
    CLIENTE, OTRO_CLIENTE, BORDE_1, BORDE_2, PROXY_RAILWAY, "198.51.100.77",
    "203.0.113", "198.51.100", "100.64.0", "2001:db8", "basura",
)


def _lineas_diagnostico(entorno: EntornoIam) -> list[dict[str, Any]]:
    lineas = [json.loads(linea) for linea in entorno.salida_logs.getvalue().splitlines() if linea.strip()]
    return [linea for linea in lineas if linea["mensaje"] == "diagnostico_proxy"]


def test_el_diagnostico_registra_cantidades_y_clases_sin_ninguna_ip(
    entorno_iam: EntornoIam, railway: dict[str, TestClient]
) -> None:
    diagnostico = railway["diagnostico"]
    respuestas = [
        _registrar(diagnostico, f"{CLIENTE}, {BORDE_1}"),
        _registrar(diagnostico, f"198.51.100.77, {CLIENTE}, {BORDE_2}"),
        # Mal formada: con puerto, basura, IPv6 entre corchetes y un elemento vacío
        _registrar(diagnostico, f"{CLIENTE}:443, basura, [2001:db8::9]:443, , {BORDE_1}"),
        diagnostico.post("/v1/usuarios", json={}),
    ]
    assert [respuesta.status_code for respuesta in respuestas] == [422, 422, 422, 422]

    salida = entorno_iam.salida_logs.getvalue()
    for prohibida in IP_PROHIBIDAS:
        assert prohibida not in salida
    assert "forwarded" not in salida.lower()

    lineas = _lineas_diagnostico(entorno_iam)
    resumen = [
        (linea["xff_cabeceras"], linea["xff_elementos"], linea["xff_clases"], linea["ip_contada"]) for linea in lineas
    ]
    assert resumen == [
        (1, 2, ["privada", "privada"], "xff"),
        (1, 3, ["privada", "privada", "privada"], "xff"),
        (1, 5, ["invalida", "invalida", "invalida", "invalida", "privada"], "socket"),
        (0, 0, [], "socket"),
    ]
    campos = {"ts", "nivel", "logger", "mensaje", "request_id", "xff_cabeceras", "xff_elementos", "xff_clases",
              "proxy_saltos", "ip_contada"}
    for linea, respuesta in zip(lineas, respuestas, strict=True):
        # Sin usuario_id ni grupo_id: solo estos campos
        assert set(linea) == campos
        assert linea["proxy_saltos"] == 1
        assert linea["nivel"] == "WARNING"
        # El request_id de la petición, para cruzarla con su línea "peticion"
        assert linea["request_id"] == respuesta.headers["x-request-id"]


def test_el_diagnostico_no_registra_ip_ni_con_una_cabecera_larga(
    entorno_iam: EntornoIam, railway: dict[str, TestClient]
) -> None:
    xff = ", ".join(f"203.0.113.{numero}" for numero in range(1, 40)) + f", {BORDE_1}"
    assert _registrar(railway["diagnostico"], xff).status_code == 422
    salida = entorno_iam.salida_logs.getvalue()
    assert "203.0.113" not in salida
    assert "198.51.100" not in salida
    (linea,) = _lineas_diagnostico(entorno_iam)
    assert linea["xff_elementos"] == 40
    assert len(linea["xff_clases"]) == 10


def test_el_diagnostico_no_registra_peticiones_de_origen_no_confiable(
    entorno_iam: EntornoIam, railway: dict[str, TestClient]
) -> None:
    assert _registrar(railway["diagnostico_directo"], f"{OTRO_CLIENTE}, {BORDE_1}").status_code == 422
    assert _lineas_diagnostico(entorno_iam) == []


def test_sin_diagnostico_no_hay_linea_ni_ip(entorno_iam: EntornoIam, railway: dict[str, TestClient]) -> None:
    assert _registrar(railway["proxy"], f"{CLIENTE}, {BORDE_1}").status_code == 422
    assert _lineas_diagnostico(entorno_iam) == []
    salida = entorno_iam.salida_logs.getvalue()
    assert CLIENTE not in salida
    assert BORDE_1 not in salida

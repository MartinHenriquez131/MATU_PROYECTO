"""MATU-25 · Límite por IP de POST /v1/usuarios por la API: 5 por hora, ventana fija, 429 y 503 (RF-37).

El contador es ContadorVentanaEnMemoria con el reloj de la prueba (el pipeline no tiene Redis); el script
de Redis tiene su propia prueba (tests/core/test_limite_ip_redis.py). Las peticiones con cuerpo inválido
cuentan igual: el límite se evalúa antes de validar, así estas pruebas no necesitan la base.
"""

import json
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI

from app.core.limite_ip import clave_de, obtener_contador_ventana, obtener_pepper_limites
from app.shared.limite_ip import LIMITE_CANJE, LIMITE_PRESENTACION, LIMITE_REGISTRO, huella
from tests.dobles.contador_ventana_en_memoria import ContadorVentanaEnMemoria
from tests.modules.iam.conftest import EntornoIam, requiere_base

pytestmark = pytest.mark.rf("RF-37")

DOCS = Path(__file__).resolve().parents[4] / "docs" / "api"
IP_TESTCLIENT = "testclient"  # la IP del socket del TestClient
PROBLEMA = "application/problem+json"


def _registrar_invalido(entorno: EntornoIam) -> Any:
    return entorno.cliente.post("/v1/usuarios", json={})


def _limite(entorno: EntornoIam) -> ContadorVentanaEnMemoria:
    assert entorno.limite_ip is not None
    return entorno.limite_ip


def _assert_429(respuesta: Any, retry: str) -> dict[str, Any]:
    assert respuesta.status_code == 429, respuesta.text
    assert respuesta.headers["content-type"] == PROBLEMA
    assert respuesta.headers["retry-after"] == retry
    cuerpo: dict[str, Any] = respuesta.json()
    assert cuerpo["type"] == "/errores/demasiadas-peticiones"
    assert cuerpo["status"] == 429
    assert set(cuerpo) == {"type", "title", "status", "detail", "errores", "request_id"}
    return cuerpo


@requiere_base
def test_registro_dentro_del_limite_crea_la_cuenta_y_cuenta_bajo_la_huella(
    entorno_iam: EntornoIam, email_sintetico: str, contrasena_sintetica: str
) -> None:
    respuesta = entorno_iam.registrar(nombre="Carmen Prueba", email=email_sintetico, contrasena=contrasena_sintetica)
    assert respuesta.status_code == 201, respuesta.text
    esperada = clave_de(LIMITE_REGISTRO, huella(entorno_iam.pepper_limites, "usuarios-ip", IP_TESTCLIENT))
    assert list(_limite(entorno_iam).datos) == [esperada]
    assert _limite(entorno_iam).datos[esperada][0] == 1


def test_sexta_cuenta_en_la_hora_429_antes_de_validar(entorno_iam: EntornoIam) -> None:
    for _ in range(5):
        assert _registrar_invalido(entorno_iam).status_code == 422
    entorno_iam.reloj.avanzar(timedelta(minutes=10))
    cuerpo = _assert_429(_registrar_invalido(entorno_iam), str(50 * 60))
    # Ni la IP ni la huella en el cuerpo, las cabeceras ni el log
    huella_ip = huella(entorno_iam.pepper_limites, "usuarios-ip", IP_TESTCLIENT)
    assert IP_TESTCLIENT not in str(cuerpo)
    assert huella_ip not in entorno_iam.texto_log()
    assert IP_TESTCLIENT not in entorno_iam.texto_log()


def test_ventana_fija_un_intento_tardio_no_la_alarga(entorno_iam: EntornoIam) -> None:
    assert _registrar_invalido(entorno_iam).status_code == 422
    entorno_iam.reloj.avanzar(timedelta(minutes=59))
    for _ in range(4):
        assert _registrar_invalido(entorno_iam).status_code == 422
    # El 6.º, al minuto 59, ve que a la ventana le queda un minuto: la abrió el 1.º, no el 5.º
    _assert_429(_registrar_invalido(entorno_iam), "60")
    entorno_iam.reloj.avanzar(timedelta(seconds=59))
    _assert_429(_registrar_invalido(entorno_iam), "1")
    # A la hora del primero se abre una ventana nueva, aunque hubo intentos hace un segundo
    entorno_iam.reloj.avanzar(timedelta(seconds=1))
    assert _registrar_invalido(entorno_iam).status_code == 422
    [(conteo, _)] = _limite(entorno_iam).datos.values()
    assert conteo == 1


def test_los_contadores_de_registro_canje_y_presentacion_son_separados(entorno_iam: EntornoIam) -> None:
    for _ in range(5):
        _registrar_invalido(entorno_iam)
    _assert_429(_registrar_invalido(entorno_iam), "3600")
    # El registro agotado no toca el canje ni la presentación (cuerpo vacío: 422, no 429)
    assert entorno_iam.cliente.post("/v1/relevo/canje", json={}).status_code == 422
    assert entorno_iam.cliente.post("/v1/relevo/presentacion", json={}).status_code == 422
    pepper = entorno_iam.pepper_limites
    claves = {
        clave_de(lim, huella(pepper, lim.prefijo, IP_TESTCLIENT))
        for lim in (LIMITE_REGISTRO, LIMITE_CANJE, LIMITE_PRESENTACION)
    }
    assert set(_limite(entorno_iam).datos) == claves


def test_canje_diez_y_presentacion_treinta_por_hora(entorno_iam: EntornoIam) -> None:
    for _ in range(10):
        assert entorno_iam.cliente.post("/v1/relevo/canje", json={}).status_code == 422
    canje = entorno_iam.cliente.post("/v1/relevo/canje", json={})
    _assert_429(canje, "3600")
    # El 429 del relevo lleva las cabeceras del relevo (C11)
    assert canje.headers["cache-control"] == "no-store"
    assert canje.headers["referrer-policy"] == "no-referrer"
    for _ in range(30):
        assert entorno_iam.cliente.post("/v1/relevo/presentacion", json={}).status_code == 422
    _assert_429(entorno_iam.cliente.post("/v1/relevo/presentacion", json={}), "3600")


@pytest.mark.parametrize("ruta", ["/v1/usuarios", "/v1/relevo/canje", "/v1/relevo/presentacion"])
def test_sin_redis_503_falla_cerrado(entorno_iam: EntornoIam, ruta: str) -> None:
    caido = ContadorVentanaEnMemoria(entorno_iam.reloj, caido=True)
    cast(FastAPI, entorno_iam.cliente.app).dependency_overrides[obtener_contador_ventana] = lambda: caido
    respuesta = entorno_iam.cliente.post(ruta, json={})
    assert respuesta.status_code == 503
    assert respuesta.headers["content-type"] == PROBLEMA
    assert "Redis no responde: el límite por IP falla cerrado" in entorno_iam.texto_log()


@pytest.mark.parametrize("ruta", ["/v1/usuarios", "/v1/relevo/canje", "/v1/relevo/presentacion"])
def test_sin_pepper_limites_503_falla_cerrado(entorno_iam: EntornoIam, ruta: str) -> None:
    cast(FastAPI, entorno_iam.cliente.app).dependency_overrides[obtener_pepper_limites] = lambda: None
    respuesta = entorno_iam.cliente.post(ruta, json={"email": f"x.{uuid.uuid4().hex[:6]}@ejemplo.cl"})
    assert respuesta.status_code == 503
    assert respuesta.headers["content-type"] == PROBLEMA
    assert _limite(entorno_iam).datos == {}


def test_el_contrato_declara_429_y_503_en_las_tres_rutas(entorno_iam: EntornoIam) -> None:
    rutas = entorno_iam.cliente.get("/openapi.json").json()["paths"]
    for ruta in ("/v1/usuarios", "/v1/relevo/canje", "/v1/relevo/presentacion"):
        respuestas = rutas[ruta]["post"]["responses"]
        assert {"429", "503"} <= set(respuestas), ruta
        assert "Retry-After" in respuestas["429"]["headers"]
        # Ninguna de las tres lleva token, PIN ni IP en path o query
        assert all(p["in"] not in ("path", "query") for p in rutas[ruta]["post"].get("parameters", []))


def test_openapi_json_coincide_con_la_api_en_el_registro(entorno_iam: EntornoIam) -> None:
    exportado = json.loads((DOCS / "openapi.json").read_text(encoding="utf-8"))
    esquema = entorno_iam.cliente.get("/openapi.json").json()
    assert exportado["paths"]["/v1/usuarios"] == esquema["paths"]["/v1/usuarios"], "vuelve a exportar /v1/usuarios"


def test_un_cuerpo_que_no_es_json_responde_422_sin_contar(entorno_iam: EntornoIam) -> None:
    """Decisión 106: FastAPI parsea el cuerpo antes de las dependencias. Ese 422 no crea cuenta ni prueba
    un PIN, así que no cuenta en el límite; un JSON válido con campos inválidos sí cuenta."""
    malformado = {"content": b"{no-es-json", "headers": {"Content-Type": "application/json"}}
    for ruta in ("/v1/usuarios", "/v1/relevo/canje", "/v1/relevo/presentacion"):
        assert entorno_iam.cliente.post(ruta, **malformado).status_code == 422  # type: ignore[arg-type]
    assert _limite(entorno_iam).datos == {}
    assert _registrar_invalido(entorno_iam).status_code == 422
    assert len(_limite(entorno_iam).datos) == 1

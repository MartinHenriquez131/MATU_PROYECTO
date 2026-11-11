"""MATU-61 · GET /v1/condiciones-pedido (D6, R13; decisión 207). Sin base.

La huella se calcula sobre el texto desde «## 1. Quién vende» hasta el final de docs/legal/condiciones-pedido.md
(decisión de Jorge del 11-11), y es el texto que se entrega.
"""

import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errores import registrar_manejadores
from app.modules.ordering.api.router_condiciones import router
from app.modules.ordering.infrastructure.condiciones import PUBLICADAS, VERSION_VIGENTE, condiciones_vigentes

pytestmark = pytest.mark.rf("RF-21")


def test_el_texto_empieza_en_la_seccion_1_y_calza_con_su_huella() -> None:
    vigentes = condiciones_vigentes()
    assert vigentes.texto.startswith("## 1. Quién vende\n")
    assert "# Condiciones del pedido" not in vigentes.texto
    assert vigentes.huella == hashlib.sha256(vigentes.texto.encode("utf-8")).hexdigest() == PUBLICADAS["0.1"][1]
    assert vigentes.version == VERSION_VIGENTE == "0.1"
    for parte in (
        "Nunca lo cambiamos por otra marca ni por otro producto",
        "24 y 48 horas hábiles",
        "cuidaconmatu@gmail.com",
    ):
        assert parte in vigentes.texto


def test_la_ruta_es_publica_y_se_revalida() -> None:
    app = FastAPI()
    registrar_manejadores(app)
    app.include_router(router, prefix="/v1")
    respuesta = TestClient(app).get("/v1/condiciones-pedido")
    assert respuesta.status_code == 200
    assert respuesta.headers["Cache-Control"] == "no-cache"
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"version", "actualizada_en", "huella", "texto"}
    assert cuerpo["huella"] == condiciones_vigentes().huella

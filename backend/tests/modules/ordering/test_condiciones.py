"""MATU-61 y MATU-62 · GET /v1/condiciones-pedido (D6, R13; decisiones 207 y 240). Sin base.

La huella se calcula sobre el texto desde «## 1. Quién vende» hasta el final de docs/legal/condiciones-pedido.md
(decisión de Jorge del 11-11), y es el texto que se entrega. Con MATU-62 la vigente es la 0.2 (segunda revisión previa
del analista, 5.3), con la frase del piloto dentro de la huella (decisión 221); la 0.1 sigue publicada para quien la
aceptó (?version=0.1).
"""

import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errores import registrar_manejadores
from app.modules.ordering.api.router_condiciones import router
from app.modules.ordering.infrastructure.condiciones import (
    PUBLICADAS,
    VERSION_VIGENTE,
    VersionNoPublicada,
    condiciones_de,
    condiciones_vigentes,
)

pytestmark = pytest.mark.rf("RF-21")


def _cliente() -> TestClient:
    app = FastAPI()
    registrar_manejadores(app)
    app.include_router(router, prefix="/v1")
    return TestClient(app)


def test_el_texto_empieza_en_la_seccion_1_y_calza_con_su_huella() -> None:
    vigentes = condiciones_vigentes()
    assert vigentes.texto.startswith("## 1. Quién vende\n")
    assert "# Condiciones del pedido" not in vigentes.texto
    assert vigentes.huella == hashlib.sha256(vigentes.texto.encode("utf-8")).hexdigest() == PUBLICADAS["0.2"][1]
    assert vigentes.version == VERSION_VIGENTE == "0.2"
    for parte in (
        "Nunca lo cambiamos por otra marca ni por otro producto",
        "24 y 48 horas hábiles",
        "cuidaconmatu@gmail.com",
    ):
        assert parte in vigentes.texto


@pytest.mark.rf("RF-25")
def test_la_0_2_trae_el_pago_y_la_frase_del_piloto_dentro_de_la_huella() -> None:
    """Decisión 221 y segunda revisión previa, 5.3: el piloto, quién paga, el pago en curso, el pago tardío, la
    anulación si el pedido cambió y qué pasa si no se puede devolver, todo dentro del texto con huella."""
    texto = condiciones_vigentes().texto
    for parte in (
        "Los pagos son de prueba: ocurren en el ambiente de prueba de Transbank y no se cobra dinero real.",
        "El comprobante no es una boleta.",
        "Pagan quien administra el grupo y quien paga. Quien paga acepta estas condiciones.",
        "MATU no ve los datos de tu tarjeta.",
        "Mientras un pago está en curso, nadie del grupo puede cambiar el pedido. Sí se puede cancelar.",
        "respetamos ese total",
        "anulamos el cobro completo el mismo día, a la misma tarjeta",
        "Nunca te pedimos los datos de tu tarjeta ni de tu banco por mensaje.",
        "Guardamos qué versión de estas condiciones aceptaste, quién la aceptó, cuándo",
        # P-62-5: el comprobante queda en MATU y en el piloto no se envía por correo
        "un comprobante, que queda guardado en MATU",
        "En el piloto, el comprobante no se envía por correo.",
    ):
        assert parte in texto, parte
    # Las secciones van del 1 al 13, sin las remisiones «igual que la versión 0.1» del borrador
    assert "igual que la" not in texto
    assert "te lo enviamos al correo" not in texto
    assert [f"## {n}." for n in range(1, 14)] == [linea[: len(f"## {n}.")] for n, linea in enumerate(
        (x for x in texto.splitlines() if x.startswith("## ")), start=1)]


def test_la_0_1_sigue_publicada_con_su_huella() -> None:
    anterior = condiciones_de("0.1")
    assert anterior.huella == PUBLICADAS["0.1"][1] == hashlib.sha256(anterior.texto.encode("utf-8")).hexdigest()
    assert "Los pagos son de prueba" not in anterior.texto
    with pytest.raises(VersionNoPublicada):
        condiciones_de("9.9")


def test_la_ruta_es_publica_y_se_revalida() -> None:
    respuesta = _cliente().get("/v1/condiciones-pedido")
    assert respuesta.status_code == 200
    assert respuesta.headers["Cache-Control"] == "no-cache"
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"version", "actualizada_en", "huella", "texto"}
    assert cuerpo["huella"] == condiciones_vigentes().huella
    assert cuerpo["version"] == "0.2"


@pytest.mark.rf("RF-25")
@pytest.mark.parametrize(("consulta", "codigo", "version"), [
    ("?version=0.1", 200, "0.1"),
    ("?version=0.2", 200, "0.2"),
    ("?version=0.3", 404, None),
    ("?version=uno", 422, None),
    ("?version=0.1.2", 422, None),
])
def test_version_entrega_la_aceptada_y_no_otra(consulta: str, codigo: int, version: str | None) -> None:
    """Decisión 240: el comprobante enlaza a la versión aceptada. Otra, 404; otra forma, 422, sin repetir el valor."""
    respuesta = _cliente().get("/v1/condiciones-pedido" + consulta)
    assert respuesta.status_code == codigo
    if version is not None:
        assert respuesta.json()["version"] == version
        assert respuesta.json()["huella"] == PUBLICADAS[version][1]
    else:
        assert "uno" not in respuesta.text and "0.1.2" not in respuesta.text

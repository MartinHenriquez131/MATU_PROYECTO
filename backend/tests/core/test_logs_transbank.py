"""MATU-62 (cierre del analista, observación 1): el token de Transbank no llega al log por un tercero. Sin base."""

import io
import json
import logging

import pytest

from app.core.logs import configurar_logs

pytestmark = pytest.mark.rf("RF-25")

TOKEN = "01ab" * 16  # sintético, con la forma de un token de 64 caracteres


@pytest.fixture
def salida() -> io.StringIO:
    stream = io.StringIO()
    configurar_logs("DEBUG", stream)
    return stream


def test_urllib3_queda_en_error_y_transbank_en_warning(salida: io.StringIO) -> None:
    assert logging.getLogger("urllib3").getEffectiveLevel() == logging.ERROR
    assert logging.getLogger("transbank").getEffectiveLevel() == logging.WARNING
    logging.getLogger("urllib3.connectionpool").warning("Retrying ... /transactions/%s", TOKEN)
    logging.getLogger("transbank").info("commit %s", TOKEN)
    assert TOKEN not in salida.getvalue()


@pytest.mark.parametrize(
    "ruta",
    [
        f"PUT /rswebpaytransaction/api/webpay/v1.2/transactions/{TOKEN} HTTP/1.1",
        f"https://webpay3gint.transbank.cl/rswebpaytransaction/api/webpay/v1.2/transactions/{TOKEN}/refunds",
        f"GET /transactions/{TOKEN}?x=1",
    ],
)
def test_la_ruta_de_la_transaccion_se_enmascara_en_los_mensajes_de_terceros(salida: io.StringIO, ruta: str) -> None:
    logging.getLogger("tercero.cliente").error("fallo %s", ruta)
    [linea] = [json.loads(x) for x in salida.getvalue().splitlines() if x.strip()]
    assert TOKEN not in linea["mensaje"] and "/transactions/***" in linea["mensaje"]

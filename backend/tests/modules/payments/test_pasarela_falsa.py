"""MATU-62 · La PasarelaFalsa responde como Transbank en venta normal (informe de Martín del 10-11, H4). Sin base.

Si la falsa no respondiera como Transbank, las pruebas de los nueve casos (arquitectura 12.4) pasarían contra algo que
no existe. Los montos son los de la prueba en integración: $57.460 y una anulación parcial de $8.990.
"""

import pytest

from app.modules.payments.application.ports import PasarelaNoDisponible, PasarelaRechazo
from app.modules.payments.infrastructure.pasarela_falsa import URL_FALSA, PasarelaFalsa

pytestmark = pytest.mark.rf("RF-25")

TOTAL = 57460
PARCIAL = 8990


def _pagada(*, debito: bool = False) -> tuple[PasarelaFalsa, str]:
    pasarela = PasarelaFalsa()
    inicio = pasarela.crear("orden-sintetica-1", "sesion-sintetica", TOTAL, "https://localhost/insumos/pedido/pago")
    assert inicio.url == URL_FALSA and len(inicio.token) == 64
    pasarela.pagar(inicio.token, debito=debito, ultimos4="7763" if debito else "2032")
    return pasarela, inicio.token


@pytest.mark.parametrize("debito", [False, True], ids=["credito", "debito"])
def test_commit_aprobado_con_credito_y_con_debito(debito: bool) -> None:
    pasarela, token = _pagada(debito=debito)
    respuesta = pasarela.confirmar(token)
    assert (respuesta.status, respuesta.response_code, respuesta.amount) == ("AUTHORIZED", 0, TOTAL)
    assert respuesta.payment_type_code == ("VD" if debito else "VN")
    assert respuesta.card_last4 == ("7763" if debito else "2032")
    assert respuesta.authorization_code is not None and len(respuesta.authorization_code) <= 6


def test_un_commit_repetido_no_falla_y_devuelve_la_misma_transaccion() -> None:
    """Caso 4 de la estrategia 10.2: el segundo commit no da error y deja un solo cobro."""
    pasarela, token = _pagada()
    primero = pasarela.confirmar(token)
    segundo = pasarela.confirmar(token)
    assert segundo == primero
    assert pasarela.cobrado(token) == TOTAL


def test_la_anulacion_parcial_deja_partially_nullified_con_el_saldo() -> None:
    """H4: después de una anulación parcial, el status es PARTIALLY_NULLIFIED con balance."""
    pasarela, token = _pagada(debito=True)
    pasarela.confirmar(token)
    anulacion = pasarela.anular(token, PARCIAL)
    assert (anulacion.type, anulacion.response_code, anulacion.balance) == ("NULLIFIED", 0, TOTAL - PARCIAL)
    estado = pasarela.consultar(token)
    assert (estado.status, estado.balance) == ("PARTIALLY_NULLIFIED", 48470)
    assert pasarela.cobrado(token) == 48470


def test_anular_todo_el_mismo_dia_es_una_reversa_y_nunca_mas_que_el_saldo() -> None:
    pasarela, token = _pagada()
    pasarela.confirmar(token)
    assert pasarela.anular(token, TOTAL).type == "REVERSED"
    assert (pasarela.consultar(token).status, pasarela.consultar(token).balance) == ("NULLIFIED", 0)
    with pytest.raises(PasarelaRechazo):
        pasarela.anular(token, 1)


def test_rechazada_por_el_banco_y_token_sin_pagar() -> None:
    pasarela = PasarelaFalsa()
    rechazada = pasarela.crear("orden-sintetica-2", "sesion", TOTAL, "https://localhost/x").token
    pasarela.pagar(rechazada, aprobada=False)
    assert pasarela.confirmar(rechazada).status == "FAILED"
    assert pasarela.cobrado(rechazada) == 0
    sin_pagar = pasarela.crear("orden-sintetica-3", "sesion", TOTAL, "https://localhost/x").token
    assert pasarela.consultar(sin_pagar).status == "INITIALIZED"
    with pytest.raises(PasarelaRechazo):
        pasarela.confirmar(sin_pagar)
    with pytest.raises(PasarelaRechazo):
        pasarela.confirmar("token-que-no-existe")


def test_caida_toda_llamada_falla_sin_cambiar_nada() -> None:
    pasarela, token = _pagada()
    pasarela.caida = True
    for llamada in (lambda: pasarela.confirmar(token), lambda: pasarela.consultar(token)):
        with pytest.raises(PasarelaNoDisponible):
            llamada()
    pasarela.caida = False
    assert pasarela.confirmar(token).status == "AUTHORIZED"


def test_su_repr_no_lleva_tokens() -> None:
    pasarela, token = _pagada()
    assert token not in repr(pasarela)

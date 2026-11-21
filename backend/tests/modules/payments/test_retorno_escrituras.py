"""MATU-80 (RNF-05) · Cuántas veces escribe la vuelta de Webpay la venta, sin base.

Cada escritura de una venta es un UPDATE de transaccion_pasarela, la tabla más cara de planificar por sus políticas
RLS. La vuelta con token_ws la escribía tres veces: la marca del retorno (decisión 245), autorizando y el cierre. Las
tres van en la misma transacción, así que la marca viaja ahora en el UPDATE de autorizando que hace cobro.confirmar.

Estas pruebas fijan las dos cosas: que el commit escribe la venta dos veces, y que la marca del retorno queda igual en
todos los casos, también cuando Webpay no responde.
"""

from collections.abc import Iterator

import pytest

from app.modules.payments.domain.venta import EstadoVenta, ResultadoPago, Venta
from tests.dobles.pagos_en_memoria import RepositorioPagosEnMemoria
from tests.modules.payments.test_casos_pago import AHORA, Escena

pytestmark = pytest.mark.rf("RNF-05")


@pytest.fixture
def escrituras(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Venta]]:
    """Cada venta que guarda el repositorio en memoria, en orden."""
    guardadas: list[Venta] = []
    original = RepositorioPagosEnMemoria.guardar_venta

    def guardar(self: RepositorioPagosEnMemoria, venta: Venta) -> None:
        guardadas.append(venta)
        original(self, venta)

    monkeypatch.setattr(RepositorioPagosEnMemoria, "guardar_venta", guardar)
    yield guardadas


def _venta(escena: Escena) -> Venta:
    (venta,) = escena.ventas()
    return venta


def test_el_commit_aprobado_escribe_la_venta_dos_veces_con_la_marca_en_la_primera(escrituras: list[Venta]) -> None:
    escena = Escena()
    token = escena.pagar().token
    assert token is not None
    escena.pasarela.pagar(token)
    escrituras.clear()

    resultado = escena.volver(token_ws=token)

    assert resultado.resultado is ResultadoPago.APROBADO
    assert [v.estado for v in escrituras] == [EstadoVenta.AUTORIZANDO, EstadoVenta.APROBADA]
    assert all(v.retorno_recibido_en == AHORA for v in escrituras)
    assert _venta(escena).retorno_recibido_en == AHORA


def test_si_webpay_no_responde_al_commit_queda_autorizando_con_la_marca(escrituras: list[Venta]) -> None:
    escena = Escena()
    token = escena.pagar().token
    assert token is not None
    escena.pasarela.pagar(token)
    escena.pasarela.caida = True
    escrituras.clear()

    resultado = escena.volver(token_ws=token)

    assert resultado.resultado is ResultadoPago.PENDIENTE
    assert [v.estado for v in escrituras] == [EstadoVenta.AUTORIZANDO]
    venta = _venta(escena)
    assert (venta.estado, venta.retorno_recibido_en, venta.commit_intentado_en) == (
        EstadoVenta.AUTORIZANDO,
        AHORA,
        AHORA,
    )


def test_si_salio_de_webpay_y_no_responde_la_marca_se_guarda_igual(escrituras: list[Venta]) -> None:
    escena = Escena()
    token = escena.pagar().token
    assert token is not None
    escena.pasarela.caida = True
    escrituras.clear()

    resultado = escena.volver(TBK_TOKEN=token)

    assert resultado.resultado is ResultadoPago.ABANDONADO
    assert [v.estado for v in escrituras] == [EstadoVenta.INICIADA]
    venta = _venta(escena)
    assert (venta.estado, venta.retorno_recibido_en) == (EstadoVenta.INICIADA, AHORA)


def test_la_segunda_vuelta_no_cambia_la_marca_de_la_primera(escrituras: list[Venta]) -> None:
    escena = Escena()
    token = escena.pagar().token
    assert token is not None
    escena.pasarela.pagar(token)
    escena.volver(token_ws=token)
    escrituras.clear()

    repetida = escena.volver(token_ws=token)

    assert repetida.ya_registrado and escrituras == []
    assert _venta(escena).retorno_recibido_en == AHORA

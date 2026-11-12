"""MATU-62 · Las reglas de la venta y del pago tardío (D-62-4, D-62-5, D-62-12; decisiones 228 a 233 y 236). Sin base.

Toda regla nueva del dominio del pago tiene aquí su prueba: la venta atada al total (reglas 2 y 3), el resultado de cada
intento, lo que se lee de Transbank (sin distinguir el medio), la vuelta, el pago en curso, el reintento del commit y
los identificadores aleatorios.
"""

import re
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.payments.domain.venta import (
    ESPERA_ENTRE_COMMITS,
    LARGO_BUY_ORDER,
    VIGENCIA_TOTAL,
    CasoRetorno,
    Decision,
    EstadoVenta,
    MotivoCierre,
    RespuestaAnulacion,
    RespuestaTransaccion,
    ResultadoPago,
    TipoTarjeta,
    Venta,
    anulacion_hecha,
    aprobada,
    clasificar_retorno,
    codigo_autorizacion,
    cuotas,
    decidir_aprobacion,
    en_curso,
    final_sin_cobro,
    nueva_clave_pasarela,
    nueva_referencia,
    nuevo_buy_order,
    nuevo_session_id,
    puede_reintentar_commit,
    resultado_de,
    tipo_tarjeta,
    ultimos4,
)

pytestmark = pytest.mark.rf("RF-25")

CONFIRMADO = datetime(2026, 11, 12, 14, 2, 11, tzinfo=UTC)
VIDA = timedelta(minutes=8)  # VIDA_VENTA_WEBPAY_MINUTOS por omisión (MATU-94)


def _venta(**cambios: object) -> Venta:
    base = Venta(
        id=uuid.uuid4(),
        cargo_id=uuid.uuid4(),
        participacion_id=uuid.uuid4(),
        usuario_id=uuid.uuid4(),
        estado=EstadoVenta.INICIADA,
        monto=57460,
        total_confirmado_en=CONFIRMADO,
        token="t" * 64,
        buy_order="b" * 26,
        session_id="s" * 40,
        creado_en=CONFIRMADO + timedelta(minutes=2),
    )
    from dataclasses import replace

    return replace(base, **cambios)  # type: ignore[arg-type]


def _decidir(venta: Venta, ahora: datetime, **pedido: object) -> Decision:
    datos: dict[str, object] = {
        "estado_pedido": "total_confirmado",
        "total": 57460,
        "total_confirmado_en": CONFIRMADO,
        "total_vence_en": CONFIRMADO + VIGENCIA_TOTAL,
        "pagado_en": None,
    }
    datos.update(pedido)
    return decidir_aprobacion(venta=venta, ahora=ahora, **datos)  # type: ignore[arg-type]


# --- D-62-4, reglas 2 y 3 -------------------------------------------------------------------------------------------


def test_regla_2_el_mismo_total_vigente_se_respeta() -> None:
    assert _decidir(_venta(), CONFIRMADO + timedelta(minutes=5)) is Decision.RESPETAR


@pytest.mark.parametrize(
    ("estado", "minutos"),
    [("vencido", 20), ("total_confirmado", 15), ("total_confirmado", 40)],
    ids=["la-fila-dice-vencido", "justo-al-vencer", "la-fila-no-alcanzo-a-decirlo"],
)
def test_regla_2_el_mismo_total_vencido_mientras_se_pagaba_se_respeta(estado: str, minutos: int) -> None:
    """Ley 19.496, art. 12: el pago que se hizo con el total vigente se respeta (vencido → pagado)."""
    assert _decidir(_venta(), CONFIRMADO + timedelta(minutes=minutos), estado_pedido=estado) is Decision.RESPETAR_TARDIO


@pytest.mark.parametrize(
    "pedido",
    [
        {"total_confirmado_en": CONFIRMADO + timedelta(minutes=3)},  # se volvió a confirmar (C1)
        {"total": 57461},  # otro monto
        {"estado_pedido": "borrador", "total_confirmado_en": None, "total_vence_en": None},  # «Cambiar el pedido»
        {"estado_pedido": "cancelado"},  # cancelado, también por el retiro de despacho o el borrado
        {"estado_pedido": "pagado", "pagado_en": CONFIRMADO + timedelta(minutes=4)},  # ya lo pagó otra venta
    ],
    ids=["otro-total-confirmado", "otro-monto", "volvio-al-carrito", "cancelado", "ya-pagado"],
)
def test_regla_3_un_total_que_ya_no_es_el_del_pedido_se_anula(pedido: dict[str, object]) -> None:
    assert _decidir(_venta(), CONFIRMADO + timedelta(minutes=5), **pedido) is Decision.ANULAR


# --- Resultados ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cambios", "esperado"),
    [
        ({}, ResultadoPago.EN_WEBPAY),
        ({"estado": EstadoVenta.AUTORIZANDO}, ResultadoPago.PENDIENTE),
        ({"estado": EstadoVenta.APROBADA, "cerrada_en": CONFIRMADO + timedelta(minutes=6)}, ResultadoPago.APROBADO),
        (
            {"estado": EstadoVenta.APROBADA, "cerrada_en": CONFIRMADO + timedelta(minutes=16)},
            ResultadoPago.APROBADO_TARDIO,
        ),
        (
            {"estado": EstadoVenta.APROBADA, "anulacion_total": True, "anulada_por_pago_tardio": True},
            ResultadoPago.ANULADO,
        ),
        ({"estado": EstadoVenta.RECHAZADA, "motivo_cierre": MotivoCierre.NO_APROBADA}, ResultadoPago.NO_APROBADO),
        ({"estado": EstadoVenta.RECHAZADA, "motivo_cierre": MotivoCierre.USUARIO_SALIO}, ResultadoPago.ABANDONADO),
        (
            {"estado": EstadoVenta.RECHAZADA, "motivo_cierre": MotivoCierre.FORMULARIO_VENCIDO},
            ResultadoPago.TIEMPO_AGOTADO,
        ),
        ({"estado": EstadoVenta.ERROR}, None),
    ],
)
def test_el_resultado_de_cada_venta(cambios: dict[str, object], esperado: ResultadoPago | None) -> None:
    assert resultado_de(_venta(**cambios)) == esperado


def test_una_cancelacion_despues_de_pagar_no_hace_anulado_al_intento() -> None:
    """La anulación total de MATU-63 (cancelación) deja el intento aprobado; solo la regla 3 lo hace anulado."""
    venta = _venta(estado=EstadoVenta.APROBADA, cerrada_en=CONFIRMADO + timedelta(minutes=5), anulacion_total=True)
    assert resultado_de(venta) is ResultadoPago.APROBADO


# --- Lo que trae Transbank: ningún cálculo distingue el medio (12.4, caso 2) ----------------------------------------


def test_aprobada_es_authorized_con_codigo_0_y_tambien_despues_de_anular() -> None:
    assert aprobada(RespuestaTransaccion("AUTHORIZED", 0, 57460))
    assert aprobada(RespuestaTransaccion("PARTIALLY_NULLIFIED", 0, 57460, balance=48470))  # H4
    assert not aprobada(RespuestaTransaccion("AUTHORIZED", -1, 57460))
    assert not aprobada(RespuestaTransaccion("FAILED", -1, 57460))
    assert not aprobada(RespuestaTransaccion("INITIALIZED", None, 57460))
    assert final_sin_cobro(RespuestaTransaccion("FAILED", -1, 57460))
    assert final_sin_cobro(RespuestaTransaccion("AUTHORIZED", -3, 57460))
    assert not final_sin_cobro(RespuestaTransaccion("INITIALIZED", None, 57460))


def test_credito_y_debito_cobran_igual_y_solo_cambia_el_texto() -> None:
    credito = RespuestaTransaccion("AUTHORIZED", 0, 57460, payment_type_code="VN")
    debito = RespuestaTransaccion("AUTHORIZED", 0, 57460, payment_type_code="VD")
    assert aprobada(credito) == aprobada(debito)
    assert tipo_tarjeta("VD") is TipoTarjeta.DEBITO
    assert tipo_tarjeta("VP") is TipoTarjeta.PREPAGO
    for codigo in ("VN", "VC", "SI", "S2", "NC", None):
        assert tipo_tarjeta(codigo) is TipoTarjeta.CREDITO


def test_de_la_tarjeta_solo_los_ultimos_4_y_las_cuotas() -> None:
    assert ultimos4("2032") == "2032"
    assert ultimos4("XXXXXXXXXXXX7763") == "7763"
    assert ultimos4("12a4") is None
    assert ultimos4(None) is None
    assert cuotas(0) == 0 and cuotas(3) == 3 and cuotas(49) is None and cuotas(None) is None
    assert codigo_autorizacion(" 1617 ") == "1617"
    assert codigo_autorizacion("12345678") == "123456"


def test_la_anulacion_hecha_es_reversed_o_nullified_con_codigo_0() -> None:
    assert anulacion_hecha(RespuestaAnulacion("REVERSED", None))
    assert anulacion_hecha(RespuestaAnulacion("NULLIFIED", 0, balance=48470, nullified_amount=8990))
    assert not anulacion_hecha(RespuestaAnulacion("NULLIFIED", -1))


# --- La vuelta, el pago en curso y el reintento --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("token_ws", "tbk_token", "orden", "sesion", "caso"),
    [
        ("t", None, None, None, CasoRetorno.COMMIT),
        (None, "t", "o", "s", CasoRetorno.USUARIO_SALIO),
        ("t", "t", "o", "s", CasoRetorno.USUARIO_SALIO),  # error en el formulario: nunca commit
        (None, None, "o", "s", CasoRetorno.FORMULARIO_VENCIDO),
        (None, None, "o", None, CasoRetorno.DESCONOCIDO),
        (None, None, None, "s", CasoRetorno.DESCONOCIDO),
        (None, None, None, None, CasoRetorno.DESCONOCIDO),
    ],
)
def test_clasificar_la_vuelta(
    token_ws: str | None, tbk_token: str | None, orden: str | None, sesion: str | None, caso: CasoRetorno
) -> None:
    assert clasificar_retorno(token_ws, tbk_token, orden, sesion) is caso


def test_pago_en_curso_dura_la_vida_de_la_venta_o_mientras_se_autoriza() -> None:
    venta = _venta()
    assert en_curso(venta, venta.creado_en + VIDA - timedelta(seconds=1), VIDA)
    assert not en_curso(venta, venta.creado_en + VIDA, VIDA)
    assert en_curso(_venta(estado=EstadoVenta.AUTORIZANDO), venta.creado_en + timedelta(hours=3), VIDA)
    for estado in (EstadoVenta.APROBADA, EstadoVenta.RECHAZADA, EstadoVenta.ERROR):
        assert not en_curso(_venta(estado=estado), venta.creado_en, VIDA)


def test_un_commit_sin_respuesta_se_reintenta_cada_10_segundos_como_mucho() -> None:
    assert ESPERA_ENTRE_COMMITS == timedelta(seconds=10)
    assert puede_reintentar_commit(None, CONFIRMADO)
    assert not puede_reintentar_commit(CONFIRMADO, CONFIRMADO + timedelta(seconds=9))
    assert puede_reintentar_commit(CONFIRMADO, CONFIRMADO + timedelta(seconds=10))


# --- Identificadores aleatorios ------------------------------------------------------------------------------------


def test_buy_order_y_session_id_aleatorios_dentro_de_los_limites_de_transbank() -> None:
    ordenes = {nuevo_buy_order() for _ in range(200)}
    assert len(ordenes) == 200
    assert all(re.fullmatch(r"[0-9a-f]{26}", o) and len(o) == LARGO_BUY_ORDER for o in ordenes)
    assert all(len(nuevo_session_id()) <= 61 for _ in range(10))
    assert nueva_clave_pasarela() != nueva_clave_pasarela()


def test_la_referencia_es_corta_unica_en_el_grupo_y_alarga_si_no_hay_libre() -> None:
    assert re.fullmatch(r"[0-9]{4}", nueva_referencia(set()))
    # Con las de 4 cifras ocupadas por el azar fijo, pasa a 5
    siempre_cero = lambda _n: 0  # noqa: E731
    assert nueva_referencia({"1000"}, siempre_cero) == "10000"
    assert nueva_referencia({"1000", "10000"}, siempre_cero) == "100000"
    with pytest.raises(RuntimeError):
        nueva_referencia({"1000", "10000", "100000"}, siempre_cero)


@pytest.mark.parametrize("monto", [57459, 57461, 1])
def test_un_monto_aprobado_distinto_del_de_la_venta_nunca_se_da_por_pagado(monto: int) -> None:
    """Observación 2 del cierre del analista: nunca se cobra distinto de lo que la familia vio."""
    assert _decidir(_venta(), CONFIRMADO + timedelta(minutes=5)) is Decision.RESPETAR
    assert decidir_aprobacion(
        estado_pedido="total_confirmado",
        total=57460,
        total_confirmado_en=CONFIRMADO,
        total_vence_en=CONFIRMADO + VIGENCIA_TOTAL,
        pagado_en=None,
        venta=_venta(),
        ahora=CONFIRMADO + timedelta(minutes=5),
        monto_aprobado=monto,
    ) is Decision.ANULAR

"""MATU-76 · Reglas puras del aviso del pedido: canales, correo de dinero, revisión antes de enviar y textos (RF-39).

Sin base. D-76-3: el correo de una anulación, un faltante o una cancelación con devolución no se apaga. C6 y C7: un
solo texto para todos los eventos, con dos pies, sin datos del pedido.
"""

import pytest

from app.modules.backoffice.application import despacho
from app.modules.notifications.domain.aviso import (
    EVENTOS_DE_DINERO,
    EVENTOS_DEL_PEDIDO,
    PAGO_ANULADO,
    PEDIDO_CANCELADO_CON_DEVOLUCION,
    PEDIDO_ENTREGADO,
    PEDIDO_NO_ENTREGADO,
    PLANTILLA_PEDIDO,
    PRODUCTO_FALTANTE,
    TIPO_AVISO_POR_PLANTILLA,
    TIPO_EVENTO_PEDIDO,
    TIPO_EVENTO_QUIEBRE,
    Canal,
    CodigoAviso,
    canal_del_pedido_activo,
    canales_del_pedido,
    motivo_omision_pedido,
)
from app.modules.notifications.domain.mensaje import (
    ASUNTO_PEDIDO,
    CUERPO_PEDIDO,
    PIE_PEDIDO,
    PIE_PEDIDO_DINERO,
    correo_pedido,
)
from app.modules.payments import events as eventos_pago

pytestmark = pytest.mark.rf("RF-39")

ORIGEN = "https://matu.example"
C, P = Canal.CORREO, Canal.PUSH


def test_los_tipos_coinciden_con_los_que_emiten_payments_y_backoffice() -> None:
    # notifications no importa a quien emite (regla 4 y capa 3): el texto del outbox es el contrato
    assert PAGO_ANULADO == eventos_pago.PAGO_ANULADO
    assert PRODUCTO_FALTANTE == despacho.PRODUCTO_FALTANTE
    assert PEDIDO_CANCELADO_CON_DEVOLUCION == despacho.PEDIDO_CANCELADO
    assert PEDIDO_ENTREGADO == despacho.PEDIDO_ENTREGADO
    assert PEDIDO_NO_ENTREGADO == despacho.PEDIDO_NO_ENTREGADO == "PedidoNoEntregado"
    assert eventos_pago.PEDIDO_PAGADO not in EVENTOS_DEL_PEDIDO
    assert EVENTOS_DE_DINERO == {PAGO_ANULADO, PRODUCTO_FALTANTE, PEDIDO_CANCELADO_CON_DEVOLUCION}


def test_la_preferencia_del_pedido_es_otra_que_la_del_insumo() -> None:
    assert TIPO_EVENTO_PEDIDO == "pedido" != TIPO_EVENTO_QUIEBRE
    assert TIPO_AVISO_POR_PLANTILLA == {"quiebre_proximo": "insumo", PLANTILLA_PEDIDO: "pedido"}


@pytest.mark.parametrize(
    ("dinero", "preferencias", "esperado"),
    [
        # Sin fila, activo por los dos canales, sea cual sea el rol (C3)
        (False, {}, (C, P)),
        (True, {}, (C, P)),
        # Apagado el correo: «Entregado» no va por correo; el de dinero sí (D-76-3)
        (False, {C: False}, (P,)),
        (True, {C: False}, (C, P)),
        # El push siempre sigue la preferencia
        (True, {C: False, P: False}, (C,)),
        (False, {C: False, P: False}, ()),
    ],
)
def test_canales_del_pedido(dinero: bool, preferencias: dict[Canal, bool], esperado: tuple[Canal, ...]) -> None:
    assert canales_del_pedido(dinero=dinero, preferencias=preferencias) == esperado


def test_canal_del_pedido_activo() -> None:
    assert canal_del_pedido_activo(C, dinero=True, preferencia=False)
    assert not canal_del_pedido_activo(C, dinero=False, preferencia=False)
    assert not canal_del_pedido_activo(P, dinero=True, preferencia=False)
    assert canal_del_pedido_activo(P, dinero=False, preferencia=None)


def test_la_revision_del_pedido_no_mira_autorizacion() -> None:
    assert motivo_omision_pedido(miembro_activo=True, canal_activo=True, con_destino=True) is None
    assert motivo_omision_pedido(miembro_activo=False, canal_activo=True, con_destino=True) is (
        CodigoAviso.MIEMBRO_INACTIVO
    )
    assert motivo_omision_pedido(miembro_activo=True, canal_activo=False, con_destino=True) is CodigoAviso.SIN_DESTINO
    assert motivo_omision_pedido(miembro_activo=True, canal_activo=True, con_destino=False) is CodigoAviso.SIN_DESTINO
    # Nunca sin_autorizacion ni alerta_cerrada (C2)
    resultados = {
        motivo_omision_pedido(miembro_activo=m, canal_activo=c, con_destino=d)
        for m in (True, False) for c in (True, False) for d in (True, False)
    }
    assert resultados == {None, CodigoAviso.MIEMBRO_INACTIVO, CodigoAviso.SIN_DESTINO}


def test_textos_del_correo_del_pedido() -> None:
    correo = correo_pedido(ORIGEN, dinero=False)
    assert correo.remitente == "MATU" and correo.texto_enlace == "Abrir MATU"
    assert correo.asunto == ASUNTO_PEDIDO == "MATU: hay una novedad en un pedido"
    assert correo.cuerpo == CUERPO_PEDIDO == "Hay una novedad en un pedido. Abre la app para verla."
    assert correo.pie == PIE_PEDIDO == (
        "Te llega este correo porque pagaste un pedido en MATU. Para dejar de recibir estos avisos por correo, entra a"
        " MATU y desactívalos en Tu cuenta."
    )
    dinero = correo_pedido(ORIGEN, dinero=True)
    assert (dinero.asunto, dinero.cuerpo) == (correo.asunto, correo.cuerpo)
    assert dinero.pie == PIE_PEDIDO_DINERO == (
        "Te llega este correo porque pagaste un pedido en MATU. Como es sobre tu dinero, te llega aunque hayas"
        " desactivado los avisos por correo."
    )


def test_el_pie_de_dinero_no_ofrece_apagar_lo_que_no_se_apaga() -> None:
    # C7
    assert "desactívalos" not in PIE_PEDIDO_DINERO and "Para dejar de recibir" not in PIE_PEDIDO_DINERO


@pytest.mark.parametrize("dinero", [False, True])
def test_el_correo_del_pedido_no_lleva_datos_del_pedido(dinero: bool) -> None:
    correo = correo_pedido(ORIGEN, dinero=dinero)
    texto = (correo.asunto + correo.texto_plano() + correo.html()).lower()
    # C6 y H3: ni productos, ni montos, ni comercio, ni referencia, ni código; nunca «te devolvimos»
    for prohibido in ("$", "devolvimos", "código", "codigo", "referencia", "comercio", "pañal", "total"):
        assert prohibido not in texto
    assert correo.enlace == "https://matu.example/"
    assert correo.html().count("href=") == 1 and "<img" not in correo.html()
    assert "novedad" not in repr(correo) and "matu.example" not in repr(correo)

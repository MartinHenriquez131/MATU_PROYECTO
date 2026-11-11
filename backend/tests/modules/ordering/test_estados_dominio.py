"""MATU-61 · Estados y transiciones del pedido (arquitectura 8.1 y 12.3; decisiones 204 y 208; C1 y C9).

La prueba de las 289 combinaciones: cada par (desde, hacia) de los 17 estados es permitido exactamente si está en la
tabla de la decisión 208. Sin base.
"""

from datetime import UTC, datetime, timedelta
from itertools import product

import pytest

from app.modules.ordering.domain.estados import (
    SIN_PAGAR,
    SIN_TRANSICIONES,
    TERMINALES,
    TRANSICIONES,
    VIGENCIA_TOTAL,
    Estado,
    Motivo,
    TransicionInvalida,
    estado_visible,
    exigir,
    permitida,
    vigencia_segundos,
)

pytestmark = pytest.mark.rf("RF-21")

E = Estado
# La tabla de la decisión 208, escrita aparte del dominio: si alguien agrega o quita una transición, falla
ESPERADAS = {
    (E.BORRADOR, E.TOTAL_CONFIRMADO),
    (E.BORRADOR, E.CANCELADO),
    (E.TOTAL_CONFIRMADO, E.VENCIDO),
    (E.TOTAL_CONFIRMADO, E.TOTAL_CONFIRMADO),
    (E.TOTAL_CONFIRMADO, E.BORRADOR),
    (E.TOTAL_CONFIRMADO, E.CANCELADO),
    (E.TOTAL_CONFIRMADO, E.PAGADO),
    (E.VENCIDO, E.TOTAL_CONFIRMADO),
    (E.VENCIDO, E.BORRADOR),
    (E.VENCIDO, E.CANCELADO),
    (E.PAGADO, E.ENVIADO_A_COMERCIO),
    (E.PAGADO, E.CANCELADO_CON_DEVOLUCION),
    (E.ENVIADO_A_COMERCIO, E.PREPARANDO),
    (E.ENVIADO_A_COMERCIO, E.CANCELADO_CON_DEVOLUCION),
    (E.PREPARANDO, E.LISTO_RETIRO),
    (E.PREPARANDO, E.CANCELADO_CON_DEVOLUCION),
    (E.LISTO_RETIRO, E.RETIRADO),
    (E.RETIRADO, E.EN_RUTA),
    (E.EN_RUTA, E.ENTREGADO),
    (E.EN_RUTA, E.NO_ENTREGADO),
    (E.ENTREGADO, E.CERRADO),
    (E.NO_ENTREGADO, E.REPROGRAMADO),
    (E.NO_ENTREGADO, E.CANCELADO_CON_DEVOLUCION),
    (E.REPROGRAMADO, E.EN_RUTA),
}

PARES = list(product(Estado, Estado))
AHORA = datetime(2026, 11, 20, 14, 5, tzinfo=UTC)


def test_son_los_17_estados_del_check_de_pedido() -> None:
    assert {e.value for e in Estado} == {
        "borrador",
        "total_confirmado",
        "vencido",
        "pagado",
        "enviado_a_comercio",
        "preparando",
        "listo_retiro",
        "asignado",
        "sin_repartidor",
        "retirado",
        "en_ruta",
        "entregado",
        "no_entregado",
        "reprogramado",
        "cerrado",
        "cancelado",
        "cancelado_con_devolucion",
    }
    assert len(PARES) == 289


@pytest.mark.parametrize(("desde", "hacia"), PARES, ids=[f"{d.value}->{h.value}" for d, h in PARES])
def test_las_289_combinaciones(desde: Estado, hacia: Estado) -> None:
    esperado = (desde, hacia) in ESPERADAS
    assert permitida(desde, hacia) is esperado
    if esperado:
        exigir(desde, hacia)
    else:
        with pytest.raises(TransicionInvalida) as error:
            exigir(desde, hacia)
        assert error.value.estado is desde


def test_son_24_transiciones_y_las_de_jorge_estan() -> None:
    assert TRANSICIONES == ESPERADAS and len(TRANSICIONES) == 24
    # C1: volver a confirmar un total vigente y «Cambiar el pedido»; C9: «Cambiar el pedido» con el total vencido
    assert {(E.TOTAL_CONFIRMADO, E.TOTAL_CONFIRMADO), (E.TOTAL_CONFIRMADO, E.BORRADOR), (E.VENCIDO, E.BORRADOR)} <= (
        TRANSICIONES
    )


def test_la_familia_cancela_sin_costo_solo_antes_de_pagar() -> None:
    """R15 y C6 del analista: sin pagar va a cancelado; desde preparando la familia no cancela."""
    assert {d for d, h in TRANSICIONES if h is E.CANCELADO} == set(SIN_PAGAR)
    assert not permitida(E.PREPARANDO, E.CANCELADO)
    assert not permitida(E.PAGADO, E.CANCELADO)


def test_un_pedido_pagado_nunca_vuelve_a_un_estado_sin_pagar() -> None:
    pagados = set(Estado) - set(SIN_PAGAR) - {E.CANCELADO}
    assert not any(permitida(d, h) for d in pagados for h in SIN_PAGAR)


def test_terminales_y_fase_2_sin_salidas() -> None:
    for estado in TERMINALES | SIN_TRANSICIONES:
        assert not any(permitida(estado, h) for h in Estado), estado


def test_todo_estado_es_alcanzable_desde_borrador_salvo_los_de_la_fase_2() -> None:
    alcanzados = {E.BORRADOR}
    pendientes = [E.BORRADOR]
    while pendientes:
        actual = pendientes.pop()
        for d, h in TRANSICIONES:
            if d is actual and h not in alcanzados:
                alcanzados.add(h)
                pendientes.append(h)
    assert set(Estado) - alcanzados == set(SIN_TRANSICIONES)


def test_los_motivos_son_la_lista_cerrada_de_c19() -> None:
    assert {m.value for m in Motivo} == {
        "total_vencio",
        "familia_cancela",
        "familia_cambia_carrito",
        "autorizacion_retirada",
        "persona_borrada",
    }


def test_el_total_vence_a_los_15_minutos_segun_el_reloj() -> None:
    vence = AHORA + VIGENCIA_TOTAL
    assert VIGENCIA_TOTAL == timedelta(minutes=15)
    assert estado_visible(E.TOTAL_CONFIRMADO, vence, AHORA) is E.TOTAL_CONFIRMADO
    assert estado_visible(E.TOTAL_CONFIRMADO, vence, vence - timedelta(seconds=1)) is E.TOTAL_CONFIRMADO
    # Justo a los 15 minutos ya venció (decisión 204: total_vence_en <= ahora)
    assert estado_visible(E.TOTAL_CONFIRMADO, vence, vence) is E.VENCIDO
    assert estado_visible(E.BORRADOR, None, vence) is E.BORRADOR


def test_vigencia_en_segundos_para_el_aviso_de_los_2_minutos() -> None:
    vence = AHORA + VIGENCIA_TOTAL
    assert vigencia_segundos(E.TOTAL_CONFIRMADO, vence, AHORA) == 900
    assert vigencia_segundos(E.TOTAL_CONFIRMADO, vence, vence - timedelta(minutes=2)) == 120
    assert vigencia_segundos(E.VENCIDO, vence, vence + timedelta(minutes=1)) == 0
    assert vigencia_segundos(E.BORRADOR, None, AHORA) is None

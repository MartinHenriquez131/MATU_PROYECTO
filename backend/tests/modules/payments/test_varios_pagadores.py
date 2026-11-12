"""MATU-62 · Los cinco casos de recaudación entre varios pagadores y la prueba de propiedad del prorrateo, en skip.

Arquitectura 12.4 (último párrafo) y estrategia de pruebas 6.2: el reparto del gasto entre varios pagadores (RF-22 a
RF-24) salió del semestre con el segundo recorte (arquitectura 15.3 y ADR-007), y sus casos quedan escritos y en skip
para activarse en la fase 2 sin volver a diseñarlos. La tabla participacion ya admite varias filas por cargo
(participacion_uq, es_respaldo y participacion_un_respaldo_uq), y el ADR-027 dejó el cobro único: en la fase 2 cada
participante paga su parte con su propia venta normal, y el respaldo cubre lo que falte.

Los documentos no enumeran los cinco casos uno a uno. Se escribieron desde lo que nombran el ADR-007 y la sección 8.3
(autorizaciones independientes, plazo de recaudación, redistribución sobre el respaldo y prorrateo por resto mayor) y
RF-22 a RF-24. Al activarlos, se confirman contra la arquitectura de ese momento.
"""

import pytest

pytestmark = pytest.mark.skip(reason="RF-22 a RF-25: fase 2, prioridad 1 (decisión de Jorge del 11-11)")


@pytest.mark.rf("RF-22")
def test_el_total_se_reparte_entre_los_participantes_y_cada_uno_paga_su_parte() -> None:
    """RF-22: con dos o más participantes, cada uno paga su parte del total confirmado con su propia venta, y la suma
    de las partes es exactamente el total, al peso. Ninguno paga más de lo que le corresponde."""


@pytest.mark.rf("RF-23")
def test_cada_participante_paga_de_forma_independiente_dentro_del_plazo() -> None:
    """RF-23: el pago de un participante no depende del de los otros. Si uno no aprueba, los demás conservan lo pagado
    hasta que vence el plazo de recaudación, y el pedido no queda pagado mientras falte una parte."""


@pytest.mark.rf("RF-24")
def test_al_vencer_el_plazo_el_faltante_lo_cubre_primero_el_respaldo() -> None:
    """RF-24: vencido el plazo con una parte sin pagar, el faltante se redistribuye y lo cubre primero el participante
    marcado como respaldo (es_respaldo, uno por cargo). Cubierto el total, el pedido queda pagado una sola vez."""


@pytest.mark.rf("RF-24")
def test_si_nadie_cubre_el_faltante_se_anula_lo_pagado_y_el_pedido_no_se_paga() -> None:
    """RF-24: si al vencer el plazo ni el respaldo cubre el faltante, no se cobra un total incompleto: se anula
    completo lo que cada participante pagó, a su misma tarjeta, y el pedido vuelve a vencido."""


@pytest.mark.rf("RF-25")
def test_una_devolucion_se_reparte_entre_quienes_pagaron_sin_superar_lo_de_cada_uno() -> None:
    """RF-25 con varios pagadores: una devolución (un producto que no se entrega, o el total) se reparte entre las
    participaciones con el mismo prorrateo y a la tarjeta de cada una. A nadie se le devuelve más de lo que pagó, y la
    suma de lo devuelto nunca supera lo cobrado."""


@pytest.mark.rf("RF-22")
def test_propiedad_prorratear_300_casos_exacto_al_peso_y_por_mayor_resto() -> None:
    """Estrategia 6.2 y arquitectura 8.3: sobre 300 casos generados, para cualquier total y cualquier reparto,
    prorratear(total, participaciones) suma exactamente el total, al peso, en enteros (divmod, sin coma flotante);
    nadie paga más de lo comprometido; y la prueba falla si se invierte el criterio del mayor resto (el peso que sobra
    va a quien tiene el resto mayor, después al respaldo y después por id)."""

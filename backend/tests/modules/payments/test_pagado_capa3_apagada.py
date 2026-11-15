"""MATU-105 · Con la capa 3 apagada, retirar despacho y borrar a la persona no tocan un pedido pagado (CL-44).

Complementa a tests/modules/ordering/test_pedido_capa3_apagada.py, que prueba que lo no pagado se cancela: aquí el
pedido ya se pagó y debe quedar intacto, con su estado, su total, su entrega y su cargo. Los pagados siguen su plazo
(app/modules/ordering/infrastructure/efecto_retiro.py). El pedido se paga con la capa encendida, como lo dejó la
familia, y después se apaga igual que en la prueba de lo no pagado.

Falla si el efecto cancela o modifica lo pagado: por ejemplo, si cancelar_sin_pagar_de deja de filtrar por SIN_PAGAR.
"""

from typing import Any

import psycopg
import pytest

from app.main import registrar_efectos_capa_3
from app.modules.care_circle.api.router_autorizaciones import finalidades_activas
from app.modules.care_circle.domain.retiro import finalidades_retirables
from app.modules.care_circle.infrastructure import efectos_retiro
from app.modules.payments.infrastructure.pasarela_falsa import PasarelaFalsa
from tests.base_datos import DSN, requiere_base
from tests.fabricas import FamiliaCreada
from tests.modules.ordering.conftest import COSTO_ENVIO, EntornoPedido
from tests.modules.payments.conftest import pagar, pedido_confirmado, sin_sesion_volver

pytestmark = [pytest.mark.rf("RF-21"), pytest.mark.rf("RF-25"), requiere_base]

TOTAL = 2 * 12990 + COSTO_ENVIO


def _foto(pedido_id: str) -> dict[str, Any]:
    """Lo que no debe cambiar: estado y total del pedido, su entrega, su cargo y sus transiciones."""
    with psycopg.connect(DSN) as cx:
        pedido = cx.execute("SELECT estado, total, pagado_en FROM pedido WHERE id = %s", (pedido_id,)).fetchone()
        entregas = cx.execute("SELECT count(*) FROM pedido_entrega WHERE pedido_id = %s", (pedido_id,)).fetchone()
        cargos = cx.execute(
            "SELECT estado, monto_cobrado FROM cargo WHERE pedido_id = %s ORDER BY id", (pedido_id,)
        ).fetchall()
        transiciones = cx.execute(
            "SELECT desde, hacia, motivo FROM pedido_transicion WHERE pedido_id = %s ORDER BY id", (pedido_id,)
        ).fetchall()
    return {
        "pedido": tuple(pedido) if pedido else None,
        "entregas": entregas[0] if entregas else None,
        "cargos": [tuple(c) for c in cargos],
        "transiciones": [tuple(t) for t in transiciones],
    }


def _pagado_y_apagar(
    e: EntornoPedido, pasarela: PasarelaFalsa, monkeypatch: pytest.MonkeyPatch
) -> tuple[FamiliaCreada, str, dict[str, Any]]:
    familia, pedido = pedido_confirmado(e)
    inicio = pagar(e, familia, pedido)
    assert inicio.status_code == 201, inicio.text
    pasarela.pagar(inicio.json()["token"])
    vuelta = sin_sesion_volver(e, {"token_ws": inicio.json()["token"]}, e.token(familia.admin))
    assert vuelta.status_code == 200 and vuelta.json()["resultado"] == "aprobado", vuelta.text

    antes = _foto(pedido["id"])
    assert antes["pedido"][:2] == ("pagado", TOTAL) and antes["pedido"][2] is not None
    assert antes["entregas"] == 1 and antes["cargos"] == [("pagado", TOTAL)]

    # La capa 3 se apaga: dos finalidades activas, y el efecto registrado como en crear_app con la capa apagada
    e.iam.cliente.app.dependency_overrides[finalidades_activas] = lambda: finalidades_retirables(False)  # type: ignore[attr-defined]
    monkeypatch.delitem(efectos_retiro._FABRICAS, "despacho")
    registrar_efectos_capa_3(False)
    assert "despacho" in efectos_retiro.finalidades_registradas()
    return familia, pedido["id"], antes


def test_con_la_capa_3_apagada_retirar_despacho_no_toca_lo_pagado(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa, monkeypatch: pytest.MonkeyPatch
) -> None:
    e = entorno_pedido
    familia, pedido_id, antes = _pagado_y_apagar(e, pasarela_falsa, monkeypatch)

    retiro = e.pedir(
        "POST", f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos/despacho/retiro", familia.admin, familia
    )

    assert retiro.status_code == 200, retiro.text
    assert retiro.json()["pedidos_cancelados"] == 0
    assert _foto(pedido_id) == antes


def test_con_la_capa_3_apagada_borrar_a_la_persona_no_toca_lo_pagado(
    entorno_pedido: EntornoPedido, pasarela_falsa: PasarelaFalsa, monkeypatch: pytest.MonkeyPatch
) -> None:
    e = entorno_pedido
    familia, pedido_id, antes = _pagado_y_apagar(e, pasarela_falsa, monkeypatch)

    borrado = e.pedir("POST", f"/v1/personas-cuidadas/{familia.persona.id}/borrado", familia.admin, familia)

    assert borrado.status_code == 200, borrado.text
    assert _foto(pedido_id) == antes

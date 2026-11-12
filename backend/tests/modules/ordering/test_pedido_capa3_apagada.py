"""MATU-94 · Con la capa 3 apagada, retirar despacho y borrar a la persona cancelan lo no pagado (decisión 250).

P2-1 de la revisión de MATU-61: el efecto de despacho se registraba solo con CAPA3_HABILITADA, y con la capa apagada
el pedido sin pagar y su copia de la entrega (dirección y teléfono) quedaban hasta 30 días. La política (§4 y §10) y
el registro de tratamientos (entrada 2) prometen cancelarlos sin costo en la misma transacción.

El pedido se crea con la capa encendida (como lo dejó la familia) y después se apaga: finalidades_activas vuelve a
las dos de las capas 1 y 2, y el efecto se registra como lo hace crear_app con CAPA3_HABILITADA=false. Las dos pruebas
fallan sin la corrección: el retiro respondía 404 y el borrado no tocaba el pedido.
"""

from typing import Any

import psycopg
import pytest

from app.main import registrar_efectos_capa_3
from app.modules.care_circle.api.router_autorizaciones import finalidades_activas
from app.modules.care_circle.domain.retiro import finalidades_retirables
from app.modules.care_circle.infrastructure import efectos_retiro
from tests.base_datos import DSN, requiere_base
from tests.fabricas import FamiliaCreada
from tests.modules.ordering.conftest import EntornoPedido

pytestmark = [pytest.mark.rf("RF-21"), requiere_base]


def _pedido_sin_pagar_y_apagar(entorno: EntornoPedido, monkeypatch: pytest.MonkeyPatch) -> tuple[FamiliaCreada, str]:
    familia = entorno.lista_para_pedir(entorno.fabrica.familia())
    entorno.hay("panal", "uno")
    creado = entorno.crear(familia, [{"oferta_id": entorno.oferta("panal", "uno"), "cantidad": 2}])
    assert creado.status_code == 201, creado.text
    confirmado = entorno.confirmar(familia, creado.json()["id"])
    assert confirmado.status_code == 200, confirmado.text
    assert _entregas(creado.json()["id"]) == 1

    # La capa 3 se apaga: dos finalidades activas, y el efecto registrado como en crear_app con la capa apagada
    entorno.iam.cliente.app.dependency_overrides[finalidades_activas] = lambda: finalidades_retirables(False)  # type: ignore[attr-defined]
    monkeypatch.delitem(efectos_retiro._FABRICAS, "despacho")
    registrar_efectos_capa_3(False)
    assert "despacho" in efectos_retiro.finalidades_registradas()
    return familia, creado.json()["id"]


def _entregas(pedido_id: str) -> int:
    with psycopg.connect(DSN) as cx:
        fila = cx.execute("SELECT count(*) FROM pedido_entrega WHERE pedido_id = %s", (pedido_id,)).fetchone()
    assert fila is not None
    return int(fila[0])


def _estado_y_motivo(pedido_id: str) -> tuple[Any, Any]:
    with psycopg.connect(DSN) as cx:
        estado = cx.execute("SELECT estado FROM pedido WHERE id = %s", (pedido_id,)).fetchone()
        motivo = cx.execute(
            "SELECT motivo FROM pedido_transicion WHERE pedido_id = %s ORDER BY id DESC LIMIT 1", (pedido_id,)
        ).fetchone()
    assert estado is not None and motivo is not None
    return estado[0], motivo[0]


def test_con_la_capa_3_apagada_retirar_despacho_cancela_lo_no_pagado(
    entorno_pedido: EntornoPedido, monkeypatch: pytest.MonkeyPatch
) -> None:
    e = entorno_pedido
    familia, pedido_id = _pedido_sin_pagar_y_apagar(e, monkeypatch)
    ruta = f"/v1/personas-cuidadas/{familia.persona.id}/consentimientos"

    retiro = e.pedir("POST", ruta + "/despacho/retiro", familia.admin, familia)

    assert retiro.status_code == 200, retiro.text
    assert retiro.json()["pedidos_cancelados"] == 1 and retiro.json()["enlaces_cortados"] == 0
    assert _estado_y_motivo(pedido_id) == ("cancelado", "autorizacion_retirada")
    assert _entregas(pedido_id) == 0
    # La vista trae despacho porque tiene un registro, sin «Volver a autorizar», y no se otorga (decisión 251)
    vista = e.pedir("GET", ruta, familia.admin, familia).json()
    assert [(a["finalidad"], a["se_puede_otorgar"]) for a in vista["autorizaciones"]] == [
        ("plan_cuidado", True), ("consumo", True), ("despacho", False)]
    assert vista["autorizaciones"][2]["estado"] == "retirada"
    assert e.autorizar_pedidos(familia).status_code == 422
    # Una segunda vez, ya retirada
    assert e.pedir("POST", ruta + "/despacho/retiro", familia.admin, familia).status_code == 409


def test_con_la_capa_3_apagada_borrar_a_la_persona_cancela_lo_no_pagado(
    entorno_pedido: EntornoPedido, monkeypatch: pytest.MonkeyPatch
) -> None:
    e = entorno_pedido
    familia, pedido_id = _pedido_sin_pagar_y_apagar(e, monkeypatch)

    borrado = e.pedir("POST", f"/v1/personas-cuidadas/{familia.persona.id}/borrado", familia.admin, familia)

    assert borrado.status_code == 200, borrado.text
    assert _estado_y_motivo(pedido_id) == ("cancelado", "persona_borrada")
    assert _entregas(pedido_id) == 0

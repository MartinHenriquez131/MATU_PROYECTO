"""MATU-80 · Recorrido 5 de MATU-64: armar el pedido desde la lista y pagar el total exacto.

La familia anota un insumo del catálogo, la lista le sugiere cuántos envases comprar, elige el comercio en el catálogo,
arma el pedido con eso, confirma el total (precios exactos con IVA más un solo envío, ADR-027) y lo paga en venta
normal con la PasarelaFalsa: nunca Transbank. Webpay la devuelve a MATU sin la sesión, y en «Tus pedidos» el pedido
aparece pagado por el total que vio. Solo datos sintéticos.
"""

import pytest

from tests.base_datos import requiere_base
from tests.e2e.conftest import Recorrido

pytestmark = [
    requiere_base,
    pytest.mark.e2e,
    pytest.mark.rf("RF-14"),
    pytest.mark.rf("RF-20"),
    pytest.mark.rf("RF-25"),
]


def test_recorrido_pedido_y_pago(recorrido: Recorrido) -> None:
    r = recorrido
    f = r.familia()

    # Dado una familia con su lista, cuando arma el pedido desde ella y lo paga
    pedido, token, total = r.pagar_desde_la_lista(f)

    # Entonces el total confirmado es el que vio: 4 envases (96 pañales para 30 días) a $12.990 más un envío
    assert total == 4 * 12990 + 3990
    assert pedido["total"] == total
    # Y la pasarela cobró una sola vez ese total, ni un peso más
    assert r.d.pasarela.cobrado(token) == total
    assert [tx.monto for tx in r.d.pasarela.transacciones.values()] == [total]

    # Y en «Tus pedidos» aparece pagado, con ese total y sin nada devuelto
    [fila] = r.tus_pedidos(f)
    assert (fila["pedido_id"], fila["estado"]) == (pedido["id"], "pagado")
    assert (fila["total"], fila["devuelto"]) == (total, 0)
    assert [(x["cantidad"]) for x in fila["productos"]] == [4]

    # Y volver de Webpay otra vez no cobra de nuevo
    otra = r.iam.cliente.post("/v1/pagos/retorno", json={"token_ws": token})
    assert otra.status_code == 200, otra.text
    assert r.d.pasarela.cobrado(token) == total
    assert [x["estado"] for x in r.tus_pedidos(f)] == ["pagado"]

    # Y el token de la venta no llega a los logs
    assert token not in r.logs()

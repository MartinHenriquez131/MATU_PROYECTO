"""Eventos del pedido.

MATU-61 no publica eventos (decisión 211): el pedido sin pagar no avisa a nadie, y productos, cantidades, montos,
dirección y teléfono nunca van al outbox. Los eventos del pago y del despacho (PedidoPagado, PedidoEnviado) llegan con
MATU-62 y MATU-63, solo con identificadores (payload_solo_identificadores).
"""

"""Eventos del pago (arquitectura 8.4 y 8.6). Van al outbox en la misma transacción que el cambio de estado, solo con
identificadores (payload_solo_identificadores): ni montos, ni la tarjeta, ni el token, ni el buy_order.

- PedidoPagado: el pedido quedó pagado (regla 2 de D-62-4, también tardío). Lo consumirá el despacho (MATU-63).
- PagoAnulado: se anuló completo un pago tardío (regla 3) o, en MATU-63, una cancelación. Lo consumirá el aviso a la
  familia (MATU-41), que hoy no tiene consumidor: el publicador lo marca publicado.
"""

PEDIDO_PAGADO = "PedidoPagado"
PAGO_ANULADO = "PagoAnulado"

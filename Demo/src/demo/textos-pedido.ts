// Textos del pedido con precio exacto (ADR-027). Aprobados por Jorge el 26/10/2026: definitivos.
// Están todos aquí para cambiarlos en un minuto si hace falta.

/** Cuántos minutos vale el total confirmado. Decidido por Jorge: 15 minutos. */
export const VIGENCIA_MINUTOS = 15

/** Quién vende y quién emite la boleta. */
export const QUIEN_VENDE = 'Te vende MATU. Recibes una sola boleta por el total, con el envío incluido.'

/** La devolución excepcional, cuando un producto no llega. */
export const DEVOLUCION = 'Si un producto no llega, te devolvemos su precio el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco.'

/** Cuándo se puede no pedir o cancelar sin costo. */
export const CANCELAR =
  'Puedes no pedir sin costo antes de pagar. Después de pagar, puedes cancelar sin costo mientras la farmacia no empiece a preparar tu pedido.'

/** Qué pasa si al retirar falta un producto. */
export const SI_FALTA_ALGO = `Si al retirar falta un producto, lo buscamos en otro comercio en convenio. Es el mismo producto, no otra marca, y pagas lo mismo: la diferencia la pone MATU. ${DEVOLUCION}`

/** Las condiciones del pedido, el resumen que se acepta con la casilla. */
export const CONDICIONES = [
  'Te vende MATU y recibes una sola boleta por el total, con el envío incluido.',
  'Los precios incluyen IVA.',
  'Pagas lo mismo aunque retiremos un producto en otro local.',
  'Si un producto no llega, te devolvemos su precio el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco.',
  'Puedes cancelar sin costo mientras la farmacia no empiece a preparar tu pedido.',
]

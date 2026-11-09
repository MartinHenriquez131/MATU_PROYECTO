// Textos del catálogo (MATU-59, especificación docs/diseno/matu-59-catalogo.md v1.0, sección 7).
// [lenguaje 27]: aprobados por Jorge el 08-11 para lenguaje.md, sección 27 «Catálogo (MATU-59)».
// Sin «stock», «Desde», «oferta», «comprar», «pedir», «carro» ni términos de lenguaje 3.2.
import { miles } from './textoLista'

export const CATALOGO = {
  titulo: 'Catálogo', // [lenguaje 27] pestaña, h1 y <title>
  bajada: 'Productos que usan las familias que cuidan. Mirar no te compromete a nada.', // [lenguaje 27]
  avisoTitulo: 'Precios de ejemplo.', // [lenguaje 27]
  aviso: 'MATU todavía no tiene convenio con comercios, y en esta demo no se cobra dinero real.', // [lenguaje 27]
  precioDeEjemplo: 'Precio de ejemplo', // [lenguaje 27]
  ivaIncluido: 'IVA incluido', // [lenguaje 27]
  /** [lenguaje 27] Una vez por tarjeta, en el nombre del comercio (N2). */
  comercio: (nombre: string) => `${nombre} (comercio ficticio)`,
  hay: (nombre: string) => `Hay en ${nombre}`, // [lenguaje 27]
  noHay: (nombre: string) => `No hay en ${nombre} por ahora`, // [lenguaje 27]
  noDisponible: 'Por ahora no está disponible', // [lenguaje 27]
  notaStock: 'Lo que hay se confirma antes de pagar.', // [lenguaje 27]
  notaEnvio: 'El envío se suma al pedido, una sola vez por pedido.', // [lenguaje 27]
  retractoTitulo: 'Derecho a retracto:', // [lenguaje 27], en negrita
  retracto: 'tienes 10 días desde que lo recibes.', // [lenguaje 27]
  retractoSello: 'No aplica si abres el sello del producto.', // [lenguaje 27], con retracto_pierde_al_abrir
  vacio: 'Todavía no hay productos en el catálogo.', // [lenguaje 27]
  apagado: 'El catálogo no está disponible por ahora.', // aprobado por Jorge el 08-11: la capa 3 apagada responde 404
  errCarga: 'No pudimos traer el catálogo. Revisa tu conexión e inténtalo de nuevo.', // [lenguaje 27]
}

/** «$12.990»: pesos enteros, punto de miles y sin decimales. */
export const pesos = (n: number) => `$${miles(n)}`

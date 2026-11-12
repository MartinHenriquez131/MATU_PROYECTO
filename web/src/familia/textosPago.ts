// Textos del pago (MATU-62, especificación docs/diseno/matu-62-pago.md v1.0, sección 12), que entran
// a lenguaje.md, sección nueva «Pago (MATU-62)». Tal cual. Regla de la sección: se paga en Webpay, la
// página de Transbank, y MATU no ve la tarjeta. Se dice «no se hizo», «saliste sin pagar» y «no se
// cobró nada», nunca «rechazado» ni «fallido». El documento se llama «Comprobante», nunca «Boleta».
// Todos los precios llevan el IVA incluido: «Total» y «Total pagado», nunca «con IVA». Nunca se
// muestra `title`, `detail` ni `mensaje` de la API.

export const PAGO = {
  // 4: antes de pagar
  antesDeWebpay: 'Te llevamos a Webpay, la página de pago de Transbank. MATU no ve los datos de tu tarjeta.',
  /** «Pagar $57.460»: el monto va aparte, en `cifras`. */
  pagar: 'Pagar',
  pagando: 'Pagando…',
  abriendoWebpay: 'Abriendo Webpay…',
  pagaQuien: 'Pagan quien administra el grupo y quien paga.',
  /** [L 31] La casilla sin marcar al tocar «Pagar». */
  marcaLaCasilla: 'Marca que leíste y aceptas las condiciones para pagar.',
  errWebpay: 'Webpay no responde ahora. No se cobró nada. Inténtalo en unos minutos.',
  errRed: 'No pudimos abrir Webpay. Revisa tu conexión y vuelve a intentarlo. No se cobró nada.',
  condicionesCambiaron: 'Las condiciones del pedido cambiaron. Léelas de nuevo y marca la casilla para pagar.',

  // 6: pago en curso
  enCursoCambiar: 'Hay un pago en curso para este pedido. Espera su resultado antes de cambiarlo.',
  enCursoCambiarCierre: 'Si alguien salió de Webpay sin terminar, se cierra solo en menos de 15 minutos.',
  enCursoPagar: 'Ya hay un pago en curso para este pedido. Espera su resultado antes de intentar de nuevo.',
  enCursoPagarCierre: 'Si saliste de Webpay sin terminar, se cierra solo en menos de 15 minutos.',
  revisarDeNuevo: 'Revisar de nuevo',
  revisando: 'Revisando…',
  sigueEnCurso: 'Todavía hay un pago en curso.',
  pagoTermino: 'El pago terminó. Te mostramos cómo quedó el pedido.',
  cancelarConPago: 'Hay un pago en curso. Si Transbank lo aprueba, lo anulamos completo el mismo día, a la misma tarjeta.',
  canceladoConPago: 'Cancelamos el pedido. Si el pago en curso se aprueba, lo anulamos completo el mismo día.',
  retirarConPago: 'Si hay un pago en curso y se aprueba, lo anulamos completo el mismo día.',

  // 7: la vuelta
  confirmandoTitulo: 'Estamos confirmando tu pago',
  noCierres: 'No cierres esta pantalla.',
  tarda: 'Todavía no tenemos la respuesta de Transbank. Si pagaste, no pagues de nuevo: te avisamos aquí apenas la tengamos, en menos de 15 minutos.',
  revisarAhora: 'Revisar ahora',
  sigueSinRespuesta: 'Todavía no tenemos la respuesta.',
  irATuPedido: 'Ir a tu pedido',
  noSeHizoTitulo: 'El pago no se hizo',
  noSeHizo: 'Transbank no lo aprobó y no se cobró nada. Puedes intentarlo con otra tarjeta mientras el total siga vigente.',
  intentarDeNuevo: 'Intentar de nuevo',
  salisteTitulo: 'Saliste de Webpay sin pagar',
  tiempoTitulo: 'Se acabó el tiempo para pagar en Webpay',
  noSeCobro: 'No se cobró nada.',
  yaRegistrado: 'Este pago ya está registrado. No se cobró dos veces.',
  sinSesion: 'Para ver el comprobante y tu pedido, entra a MATU.',
  entrar: 'Entrar',

  // 7.4: pagaste
  pagasteTitulo: 'Pagaste tu pedido',
  /** «Pagaste $57.460 una sola vez. Es el total que viste antes de pagar.», partido para la cifra. */
  pagasteAntes: 'Pagaste',
  pagasteDespues: 'una sola vez. Es el total que viste antes de pagar.',
  comprobante: 'Comprobante',
  pedidoRef: (referencia: string) => `Pedido ${referencia}`,
  aLas: 'a las',
  envio: 'Envío (uno por pedido)',
  totalPagado: 'Total pagado',
  pagado: 'Pagado',
  tarjeta: (tipo: 'credito' | 'debito' | 'prepago') => (tipo === 'debito' ? 'Tarjeta de débito terminada en' : tipo === 'prepago' ? 'Tarjeta de prepago terminada en' : 'Tarjeta de crédito terminada en'),
  enCuotas: (n: number) => `, en ${n} cuotas`,
  codigo: 'Código de autorización',
  otraPersona: 'Lo pagó otra persona de tu grupo.',
  selloTitulo: 'Pago de prueba. No se cobró dinero real.',
  selloResto: 'Este comprobante no es una boleta.',
  datosTitulo: 'Datos del pedido',
  vende: 'Vende: MATU, piloto académico, sin persona jurídica.',
  entrega: (ventana: string) => `Entrega: ${ventana}`,
  condicionesAceptadas: (version: string) => `Condiciones aceptadas: versión ${version}, el`,
  condicionesVersion: (version: string) => `Condiciones del pedido, versión ${version} (se abre en otra pestaña)`,
  garantiasTitulo: 'Lo que te garantizamos',
  retractoTitulo: 'Derecho a retracto:',
  retracto: 'tienes 10 días desde que lo recibes.',
  siNoLlega: 'Si un producto no llega, te devolvemos su precio el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco.',
  puedeCancelar: 'Quien administra el grupo puede cancelar sin costo mientras el comercio no empiece a preparar.',
  algoNoEsta: '¿Algo no está bien? Escríbenos a',
  correoEnviado: 'Te enviamos este comprobante a',
  correoPiloto: 'En el piloto, el comprobante no se envía por correo. Imprímelo o guárdalo en PDF si lo necesitas.',
  imprimir: 'Imprimir o guardar en PDF',
  tardio: 'Tu pago llegó después de que venció el total, y lo respetamos: pagaste',
  tardioCierre: ', el precio que aceptaste.',

  // 7.7: devoluciones
  devolvimosTuya: (producto: string | null) => (producto ? `por ${producto}` : 'por tu pedido completo'),
  devolvimosAntes: 'Devolvimos',
  aTuTarjeta: 'a tu tarjeta terminada en',
  aLaTarjeta: 'a la tarjeta con que se pagó',
  cuandoTuBanco: 'Cuándo lo ves en tu cuenta depende de tu banco.',
  cuandoElBanco: 'Cuándo se ve en la cuenta depende del banco.',
  devolviendoAntes: 'Estamos devolviendo',
  aTuTarjetaSola: 'a tu tarjeta.',
  devolviendoTuya: 'Si no se completa hoy, te escribimos. MATU nunca te pide los datos de tu banco por mensaje.',
  devolviendoAjena: 'Si no se completa hoy, le escribimos a quien pagó. MATU nunca pide los datos de un banco por mensaje.',
  renglonDevolvimos: (producto: string | null) => `Devolvimos: ${producto ?? 'tu pedido completo'}`,
  pagasteEnTotal: 'Pagaste en total',

  // 7.9: pago tardío anulado
  anulamosTitulo: 'Anulamos tu pago',
  anulandoTitulo: 'Estamos anulando tu pago',
  anuladoAntes: 'El pedido cambió o se canceló mientras pagabas.',
  anulamosMonto: 'Anulamos tu pago de',
  completoATuTarjeta: 'completo, a tu tarjeta terminada en',
  devolviendoTotal: 'Estamos devolviendo',
  selloSolo: 'Pago de prueba. No se cobró dinero real.',

  // 8: el pedido pagado en la pestaña «Pedido»
  pagadoTitulo: 'Pedido pagado',
  totalPagadoDos: 'Total pagado:',
  verComprobante: 'Ver el comprobante',
}

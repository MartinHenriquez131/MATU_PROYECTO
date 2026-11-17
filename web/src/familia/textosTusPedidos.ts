// Textos de «Tus pedidos» (MATU-92, especificación docs/diseno/matu-92-tus-pedidos.md v1.1, sección
// 9), que entran a lenguaje.md, sección 38 «Tus pedidos (MATU-92)», por aprobar por Jorge. Tal cual.
// Reglas de la sección: nunca «código de retiro», «rechazado», «fallido», «stock», «reserva» ni «con
// IVA», y nunca «10 días» sin «hábiles» (C20 y C26). Las cifras (montos, fechas, referencias) las
// pone la pantalla en `cifras`; aquí van las frases que las rodean. Nunca se muestra `title`,
// `detail` ni `mensaje` de la API.

export const TUS_PEDIDOS = {
  // 2 y 3: la pestaña, la lista y su `<title>`
  titulo: 'Tus pedidos', // [L 38]
  bajada: (pila: string) => `Los pedidos pagados de ${pila}, de los últimos 2 años.`, // [L 38]
  vacio: (pila: string) => `Todavía no hay pedidos pagados para ${pila}.`, // [L 38]
  irATuPedido: 'Ir a tu pedido', // [L 31]
  pedidoRef: (referencia: string) => `Pedido ${referencia}`, // [L 38]
  totalPagado: 'Total pagado:', // [L 38]
  devuelto: 'Devuelto:', // [NUEVO]
  /** O5: «Pañal adulto M x30 y 2 productos más». */
  masProductos: (primero: string, otros: number) => (otros <= 0 ? primero : otros === 1 ? `${primero} y 1 producto más` : `${primero} y ${otros} productos más`), // [NUEVO]
  verMas: 'Ver más pedidos', // [NUEVO]
  cargandoMas: 'Cargando más…', // [NUEVO]
  errMas: 'No pudimos traer más pedidos. Revisa tu conexión y vuelve a intentarlo.', // [NUEVO]
  apagado: 'Tus pedidos no están disponibles por ahora.', // [NUEVO]
  errLista: 'No pudimos traer tus pedidos. Revisa tu conexión y vuelve a intentarlo.', // [L 38]
  /** 3.4: el [AJUSTE] sin «Pagado ·», que ya dice la etiqueta de cada fila. */
  observador: (pila: string) => `Quien administra el grupo, quien cuida a ${pila} y quien paga ven el detalle.`, // [L 38] [AJUSTE]
  productosBorrados: 'De este pedido guardamos solo lo que se pagó y lo que se devolvió.', // [L 38]

  // 2.3 y 2.4: el bloque al final de «Pedido» y el comprobante de la vuelta
  verTodos: 'Ver todos tus pedidos', // [NUEVO]
  verComoVa: 'Ver cómo va tu pedido', // [NUEVO]

  // 4.2: el estado del pedido
  estado: {
    pagado: 'Pagado',
    pagadoExplicacion: 'Lo estamos enviando al comercio. Puede tardar unos minutos.',
    enviado: 'Enviado al comercio',
    preparando: 'En preparación',
    listo: 'Listo para salir',
    enCamino: 'En camino',
    entregadoEl: 'Entregado el',
    noEntregado: 'No pudimos entregarlo',
    noEntregadoExplicacion: 'Te escribimos para coordinar otra entrega o devolverte el total.',
    reprogramado: 'Entrega reprogramada',
    reprogramadoExplicacion: 'Te avisamos cuando salga de nuevo.',
    cancelado: 'Cancelado',
    /** «Devolvimos $22.980, envío incluido, a la tarjeta con que se pagó.», partido para la cifra. */
    devolvimosAntes: 'Devolvimos',
    /** D2: mientras la devolución sigue en curso. */
    devolviendoAntes: 'Estamos devolviendo',
    envioIncluidoTarjeta: ', envío incluido, a la tarjeta con que se pagó.',
  },

  // 4.1: el detalle
  volverALista: 'Volver a tus pedidos', // [NUEVO]
  pagadoEl: 'Pagado el', // [NUEVO]
  aLas: 'a las',

  // 4.3: cómo va
  comoVa: 'Cómo va', // [NUEVO]
  de: (comercio: string) => `De ${comercio}`, // [L 38]
  /** Decisión 438: `nombre_fantasia` es null si el comercio dejó de estar activo. */
  deUnComercio: 'De un comercio', // [NUEVO]
  ficticio: '(comercio ficticio)', // [L 31]
  faltaron: (n: number) => `Faltaron ${n}`, // [NUEVO]
  parte: {
    enviada: 'Enviado al comercio',
    preparando: 'En preparación',
    lista: 'Listo para salir',
    retirada: 'Salió del comercio', // [NUEVO]
    faltante: 'No tenía estos productos', // [NUEVO]
    cancelada: 'Cancelado',
  },

  // 4.4: dinero devuelto
  dineroDevuelto: 'Dinero devuelto', // [NUEVO] (D5)
  el: 'El', // [NUEVO] «El 12/11/2026»
  faltaronDe: (n: number, producto: string) => `Faltaron ${n} de ${producto}.`, // [L 36] · [L 38]
  teDevolvimos: 'Te devolvimos', // [L 36] (D3)
  devolvimos: 'Devolvimos', // [L 32]
  aTuTarjeta: 'a tu tarjeta terminada en',
  aLaTarjeta: 'a la tarjeta con que se pagó',
  porProducto: (producto: string) => `por ${producto}`,
  porTodo: 'por tu pedido completo', // [L 32]
  cuandoTuBanco: 'Cuándo lo ves en tu cuenta depende de tu banco.',
  cuandoElBanco: 'Cuándo se ve en la cuenta depende del banco.',
  devolvimosEnvio: 'Devolvimos el envío:', // [L 38] (C13)
  estamosDevolviendo: 'Estamos devolviendo', // [L 32]
  aTuTarjetaSola: 'a tu tarjeta.',
  enCursoTuya: 'Si no se completa hoy, te escribimos. MATU nunca te pide los datos de tu banco por mensaje.', // [L 32]
  enCursoAjena: 'Si no se completa hoy, le escribimos a quien pagó. MATU nunca pide los datos de un banco por mensaje.', // [L 32]

  // 4.5: productos para devolver
  paraDevolver: 'Productos para devolver', // [NUEVO]
  devolucionPedida: 'Devolución pedida', // [L 38]
  devueltoEl: 'Devuelto el', // [L 38]
  noSeAcepto: 'No se aceptó la devolución', // [L 38]
  /** «Te devolvemos $26.490 cuando recibamos los productos con su sello cerrado.», partido para la cifra. */
  teDevolvemos: 'Te devolvemos', // [L 38]
  cuandoRecibamos: 'cuando recibamos los productos con su sello cerrado.', // [L 38]
  tambienEnvio: 'También te devolvemos el envío.', // [L 38]
  siTienesDudas: 'Si tienes dudas, escríbenos a', // [L 38]
  laPidioOtra: 'La pidió otra persona de tu grupo.', // [NUEVO]
  porCorreoTuya: 'Esta devolución la pediste por correo. La registró el equipo de MATU.', // [L 38]
  porCorreoAjena: 'Esta devolución se pidió por correo. La registró el equipo de MATU.', // [AJUSTE] (D4)

  // 4.6.1: arrepentirme de la compra
  arrepentirme: 'Arrepentirme de la compra', // [L 36]
  puedesHastaAntes: 'Puedes hacerlo hasta el', // [L 36]
  puedesHastaDespues: 'Pasamos a buscar los productos sin costo y te devolvemos su precio a la misma tarjeta cuando los recibimos con su sello cerrado.', // [L 36]
  siDevuelvesTodo: 'Si devuelves todo, también el envío.', // [L 36], solo si las condiciones lo incluyen (C9)
  arrepentirseRol: 'Pueden arrepentirse de la compra quien administra el grupo y quien la pagó.', // [L 38]
  nadaDisponible: 'Ya pediste devolver todos los productos de este pedido.', // [NUEVO]
  /** C22: «El plazo para arrepentirte desde la aplicación terminó el {fecha}. Si todavía quieres…». */
  plazoAppAntes: 'El plazo para arrepentirte desde la aplicación terminó el', // [L 38]
  plazoAppDespues: 'Si todavía quieres devolver productos, o tienes un problema con el pedido, escríbenos a', // [L 38]
  plazoAntes: 'El plazo para arrepentirte terminó el', // [L 38]
  plazoDespues: 'Si tienes un problema con el pedido, escríbenos a', // [L 38]

  // 4.6.2: cancelar el pedido
  cancelar: 'Cancelar el pedido', // [L 36]
  puedesCancelar: 'Puedes cancelarlo sin costo mientras el comercio no empiece a prepararlo.', // [NUEVO]
  cancelarRol: 'Solo quien administra el grupo puede cancelar un pedido pagado, mientras el comercio no empiece a prepararlo.', // [L 38]

  // 4.9: los estados del detalle
  errDetalle: 'No pudimos traer tu pedido. Revisa tu conexión e inténtalo de nuevo.', // [L 31]
  errComprobante: 'No pudimos traer el comprobante. Revisa tu conexión y vuelve a intentarlo.', // [NUEVO]
  noEncontrado: 'No encontramos este pedido.', // [L 31]

  // 5: la pantalla de arrepentirse
  volverAlPedido: (referencia: string) => `Volver al pedido ${referencia}`, // [NUEVO]
  elige: 'Elige qué productos devuelves', // [NUEVO]
  recibiste: 'Recibiste', // [NUEVO] «Recibiste 2. Pagaste $12.990 cada uno.»
  pagaste: 'Pagaste',
  cadaUno: 'cada uno.',
  sello: 'Si abres el sello, ya no se puede devolver.', // [L 38]
  yaPediste: (n: number) => `Ya pediste devolver ${n}.`, // [NUEVO]
  cuantos: '¿Cuántos devuelves?', // [NUEVO]
  unoMenos: (producto: string) => `Uno menos: ${producto}`, // [NUEVO]
  unoMas: (producto: string) => `Uno más: ${producto}`, // [NUEVO]
  hasta: (n: number) => `Puedes devolver hasta ${n}.`, // [NUEVO]
  yaTodos: 'Ya pediste devolver todos.', // [NUEVO]
  errRango: (n: number) => `Escribe un número de 0 a ${n}.`, // [NUEVO]
  loQueVas: 'Lo que vas a devolver', // [NUEVO]
  nadaElegido: 'Todavía no eliges ningún producto.', // [NUEVO]
  vasADevolver: 'Vas a devolver:', // [L 38] [AJUSTE] en lista
  devolverEstos: 'Devolver estos productos', // [L 38]
  enviando: 'Enviando…', // [L 38]
  noVolver: 'No, volver', // [L 38]
  errNadaElegido: 'Elige al menos un producto y cuántos devuelves.', // [L 38]
  hechoRetracto: 'Recibimos tu pedido de devolución. Te escribimos para coordinar el retiro.', // [L 36]
  errRetracto: 'No pudimos enviar tu pedido de devolución. Revisa tu conexión y vuelve a intentarlo. Lo que elegiste sigue aquí.', // [NUEVO]
  yaSePidio: 'Otra persona de tu grupo ya pidió devolver algunos de estos productos.', // [NUEVO], en negrita
  yaSePidioResto: 'Te mostramos lo que todavía puedes devolver. Revisa lo que elegiste antes de enviarlo.', // [NUEVO]

  // 6: el diálogo de cancelar
  cancelarPregunta: '¿Cancelar este pedido?', // [L 38]
  /** «Te devolvemos $57.460, envío incluido, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco.» */
  cancelarMontoAntes: 'Te devolvemos', // [L 38]
  cancelarMontoDespues: ', envío incluido, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco.', // [L 38]
  selloPrueba: 'Pago de prueba. No se cobró dinero real.', // [L 32]
  seguir: 'Seguir con el pedido', // [L 38]
  cancelando: 'Cancelando…', // [L 38]
  /** «Cancelamos el pedido. Estamos devolviendo {total} a la tarjeta con que se pagó.» */
  canceladoAntes: 'Cancelamos el pedido. Estamos devolviendo', // [L 38]
  canceladoDespues: 'a la tarjeta con que se pagó.', // [L 38]
  yaCancelado: 'Este pedido ya se canceló. Te mostramos cómo quedó.', // [L 38]
  yaSePrepara: 'Ya están preparando tu pedido, así que no se puede cancelar. Cuando llegue, puedes arrepentirte de la compra.', // [L 36]
  errCancelar: 'No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.', // [L 31]
  /** Sin la última frase: la pantalla no pudo volver a leer el pedido, así que no sabe si sigue igual. */
  errCancelarSinLeer: 'No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo.', // [L 31] sin «Todo sigue como estaba.»
} as const

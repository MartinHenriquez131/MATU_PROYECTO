// Textos del pedido (MATU-61, especificación docs/diseno/matu-61-pedido.md v1.1, sección 15), que
// entran a lenguaje.md, sección 31 «Pedido (MATU-61)». Tal cual. Regla de la sección: en la app se
// dice «tu pedido», nunca «carro» ni «carrito»; «lo que hay» y «que haya», nunca «stock». Todos los
// precios llevan el IVA incluido (JC-IVA): el total se llama «Total», e «IVA» solo va en «Precio de
// ejemplo · IVA incluido». Nunca se muestra `title`, `detail` ni `mensaje` de la API.
import type { Calidad } from '../compartido/api/familia'

/** «Pedidos autorizados.», el comienzo de las notas de llegada de 7.3. */
const AUTORIZADOS = 'Pedidos autorizados.'

export const PEDIDO = {
  pestana: 'Pedido',

  // 4: la autorización
  autTitulo: 'Antes de pedir, un permiso',
  autExplicacion: 'Para pedir desde MATU, primero autoriza los pedidos. Sin esta autorización igual puedes imprimir o compartir la lista.',
  autAparte: 'Es un permiso aparte del de su ficha y del de sus insumos.',
  volverAlCatalogo: 'Volver al catálogo',
  volverALista: 'Volver a la lista de insumos',
  autBoton: 'Autorizar los pedidos',
  autEnviando: 'Autorizando…',
  autError: 'No pudimos guardar la autorización. Revisa lo que elegiste y vuelve a intentarlo.',
  autorizadosConProducto: (producto: string) => `${AUTORIZADOS} Agregamos «${producto}» a tu pedido.`,
  autorizados: AUTORIZADOS,
  autorizadosDesdePestana: `${AUTORIZADOS} Agrega productos desde el catálogo o desde tu lista de insumos.`,
  faltaAutTitulo: (pila: string) => `Falta la autorización de pedidos para ${pila}.`,
  faltaAut: (pila: string) => `Sin ella no se pueden hacer pedidos desde MATU. Pídele a quien administra el grupo o a quien cuida a ${pila} que la dé.`,
  renovarTitulo: (pila: string) => `Hay que renovar la autorización de los pedidos de ${pila}.`,
  renovar: 'Se renueva una vez al año. Mientras tanto no se pueden hacer pedidos, pero tu pedido sigue guardado.',
  renovarBoton: 'Renovar la autorización',
  renovarPide: (pila: string) => `Pídele a quien administra el grupo o a quien cuida a ${pila} que la renueve.`,

  // 5: el catálogo
  agregar: 'Agregar al pedido',
  agregando: 'Agregando…',
  agregarDe: (producto: string, comercio: string) => `Agregar al pedido: ${producto}, de ${comercio}`,
  enTuPedido: 'En tu pedido',
  verTuPedido: 'Ver tu pedido',
  agregamos: (producto: string) => `Agregamos «${producto}» a tu pedido.`,
  errAgregar: 'No pudimos agregarlo. Revisa tu conexión y vuelve a intentarlo.',

  // 6: la lista de insumos
  listaFrase: 'Los productos de esta lista que están en el catálogo se pueden pedir con MATU. Antes de pagar ves el total.',
  pedirLista: 'Pedir estos productos',
  pidiendoLista: 'Agregando a tu pedido…',
  agregamosDeLista: (n: number) => (n === 1 ? 'Agregamos 1 producto de tu lista a tu pedido.' : `Agregamos ${n} productos de tu lista a tu pedido.`),
  yaEstaba: (producto: string) => `${producto} ya estaba en tu pedido: dejamos la cantidad de la lista.`,
  fueraDelCatalogo: (nombres: string[]) =>
    nombres.length === 1 ? `${nombres[0]} no está en el catálogo y no va en el pedido.` : `No están en el catálogo y no van en el pedido: ${nombres.join(', ')}.`,

  // 7: tu pedido
  titulo: 'Tu pedido',
  bajada: 'Revisa los productos y cuántos quieres. Antes de pagar confirmamos que haya.',
  nuncaOtraMarca: 'Nunca lo cambiamos por otra marca ni por otro producto.',
  comercio: (nombre: string, ficticio: boolean) => `De ${nombre}${ficticio ? ' (comercio ficticio)' : ''}`,
  cadaUno: 'cada uno',
  precioDeEjemploIva: 'Precio de ejemplo · IVA incluido',
  ivaIncluido: 'IVA incluido',
  cantidad: 'Cantidad',
  quitarUno: (producto: string) => `Quitar uno: ${producto}`,
  agregarUno: (producto: string) => `Agregar uno: ${producto}`,
  enTuLista: (cantidad: string) => `En tu lista: ${cantidad}`,
  errCantidad: 'Escribe una cantidad de 1 a 99.',
  errGuardarCantidad: 'No pudimos guardar la cantidad. Revisa tu conexión y vuelve a intentarlo.',
  subtotal: 'Subtotal:',
  siFalta: 'Si falta este producto',
  otroComercio: 'Buscarlo en otro comercio',
  otroComercioDetalle: 'El mismo producto. Pagas lo mismo.',
  quitar: 'Sacarlo del pedido y devolverme su precio',
  errRegla: 'No pudimos guardar qué hacer si falta. Revisa tu conexión y vuelve a intentarlo.',
  siFaltaOtro: 'Si falta: lo buscamos en otro comercio.',
  siFaltaQuitar: 'Si falta: lo sacamos y te devolvemos su precio.',
  retractoTitulo: 'Derecho a retracto:',
  retracto: 'tienes 10 días desde que lo recibes.',
  retractoSello: 'No aplica si abres el sello del producto.',
  sacar: 'Sacar del pedido',
  sacarDe: (producto: string) => `Sacar del pedido: ${producto}`,
  sacamos: (producto: string) => `Sacamos «${producto}» del pedido.`,
  errSacar: 'No pudimos sacarlo. Revisa tu conexión y vuelve a intentarlo.',

  // 7.8: la entrega
  entrega: 'Entrega',
  direccion: 'Dirección',
  sinDireccion: 'Todavía no hay una dirección de entrega.',
  agregarDireccion: 'Agregar la dirección',
  cambiarDireccion: 'Cambiar dirección',
  telefono: 'Teléfono de contacto',
  tuCelular: '(tu celular)',
  cambiarTelefono: 'Cambiar teléfono',
  llegaEntre: (ventana: string) => `Llega entre ${ventana.replace(/^Entre /, '')}.`,
  telefonoAyuda: 'Para que quien entrega pueda avisarte. Si es el de otra persona, avísale.',
  guardarTelefono: 'Guardar el teléfono',
  guardando: 'Guardando…',
  cancelar: 'Cancelar',
  guardamosTelefono: 'Guardamos el teléfono.',
  errTelefono: 'Escribe un celular de Chile, por ejemplo +56 9 5555 0137.',

  // 7.9: el pie
  productos: 'Productos:',
  envioAlConfirmar: 'El envío y el total los ves al confirmar que haya cada producto.',
  verTotal: 'Ver el total',
  confirmando: 'Confirmando…',
  confirmandoEstado: 'Estamos confirmando que haya cada producto…',
  cancelarPedido: 'Cancelar pedido',
  errSinDireccion: 'Agrega la dirección de entrega para ver el total.',
  yaConfirmaste: 'Ya confirmaste el total. Para cambiar algo, toca «Cambiar el pedido».',

  // 7.10: vacío
  vacio: 'Tu pedido está vacío. Agrega productos desde el catálogo o desde tu lista de insumos.',
  irAlCatalogo: 'Ir al catálogo',
  irALista: 'Ir a la lista de insumos',
  vacioLector: (pila: string) => `Todavía no hay un pedido para ${pila}.`,

  // 7.2: pagador y observador
  quienPuede: (pila: string) => `Quien administra el grupo o quien cuida a ${pila} puede cambiar el pedido y ver el total.`,
  verResumen: 'Ver el resumen',
  vencidoPagador: 'Pasaron 15 minutos y el total venció. Pídele a quien armó el pedido que lo vuelva a confirmar.',

  // 7.3: al llegar
  guardamosDireccion: 'Guardamos la dirección.',
  vaciamosDireccion: 'Vaciamos la dirección.',
  yaPuedesCambiar: 'Ya puedes cambiar tu pedido. Cuando termines, toca «Ver el total» para confirmarlo de nuevo.',
  dejasteLaSuya: 'Dejaste la dirección que guardó otra persona de tu grupo.',

  // 8: la dirección
  dirTitulo: '¿Dónde lo entregamos?',
  dirAyuda: 'La usamos solo para entregar tus pedidos. Ningún comercio la ve.',
  dirGuardamosPara: (pila: string) => `La guardamos para los próximos pedidos de ${pila}.`,
  calle: 'Calle',
  numero: 'Número',
  depto: 'Depto (opcional)',
  comuna: 'Comuna',
  referencia: 'Referencia (opcional)',
  referenciaAyuda: 'Por ejemplo: portón verde. No escribas datos de salud.',
  guardarDireccion: 'Guardar la dirección',
  errCalle: 'Escribe la calle.',
  errNumero: 'Escribe el número. Si no tiene, escribe S/N.',
  errComuna: 'Escribe la comuna.',
  errReferencia: 'La referencia admite hasta 200 caracteres. Acórtala un poco.',
  errDireccion: 'No pudimos guardar la dirección. Revisa los datos y vuelve a intentarlo.',
  volverATuPedido: 'Volver a tu pedido',
  volverAAntesDePagar: 'Volver a antes de pagar',
  volverAGrupo: 'Volver a Grupo familiar',
  conflictoTitulo: 'Otra persona de tu grupo cambió la dirección mientras la cambiabas.',
  conflictoTexto: 'No guardamos la tuya encima de la suya. Elige cuál dejar.',
  laQueGuardo: 'La que guardó',
  laTuya: 'La tuya, sin guardar',
  guardarLaMia: 'Guardar la mía',
  dejarLaSuya: 'Dejar la que guardó',

  // 8.7: vaciar la dirección
  vaciarFrase: 'Si no quieres que MATU la guarde, puedes vaciarla. Para el próximo pedido habrá que escribirla de nuevo.',
  vaciar: 'Vaciar la dirección',
  vaciarDe: (pila: string) => `Vaciar la dirección de entrega de ${pila}`,
  vaciarPregunta: (pila: string) => `¿Vaciar la dirección de entrega de ${pila}?`,
  vaciarTexto: 'La borramos de MATU. Para el próximo pedido habrá que escribirla de nuevo.',
  dejarla: 'Dejarla como está',
  vaciando: 'Vaciando…',
  errVaciar: 'No pudimos vaciar la dirección. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.',
  vaciarConflicto: 'Otra persona de tu grupo cambió la dirección mientras la revisabas. Revisa cómo quedó antes de vaciarla.',

  // 9: antes de pagar
  resTitulo: 'Antes de pagar',
  resBajada: 'Confirmamos que hay cada producto. El total, con el envío, es', // [CAMBIA] L 31 (MATU-109 D5b)
  cambiarFrase: 'Si cambias algo, antes de pagar confirmamos el total de nuevo.',
  cambiarPedido: 'Cambiar el pedido',
  abriendo: 'Abriendo tu pedido…',
  errCambiar: 'No pudimos abrir tu pedido para cambiarlo. Revisa tu conexión y vuelve a intentarlo. El total sigue confirmado.',
  cambiosTitulo: 'Cambió desde tu pedido',
  salio: (producto: string) => `Ya no hay ${producto}. Salió del pedido.`,
  ahoraLoPrepara: (producto: string, comercio: string, ficticio: boolean) => `Ahora ${producto} lo prepara ${comercio}${ficticio ? ' (comercio ficticio)' : ''}.`,
  cambioPrecioAntes: (producto: string) => `Cambió el precio de ${producto}: antes`,
  ahora: 'ahora',
  cambioPrecio: 'Cambió el precio',
  otroComercioEtiqueta: 'Otro comercio',
  productosTitulo: 'Productos',
  boletaTitulo: 'Tu pedido',
  productosN: (n: number) => `Productos (${n})`,
  envio: 'Envío (uno por pedido)',
  total: 'Total',
  /** MATU-109 D5: bajo el total de la boleta. Sin la palabra IVA, que cumple lenguaje.md 31 tal como está. */
  totalAyuda: 'Son los precios finales. El envío es uno solo, por todo el pedido.', // [NUEVO] MATU-109 D5
  valeHasta: 'Este total vale hasta las',
  cobro: 'Se cobra una sola vez este total, con crédito o con débito. No hay reserva ni cobros después.',
  quedan2: 'Quedan 2 minutos para pagar este total.',
  volverAConfirmar: 'Volver a confirmar',
  confirmamosDeNuevo: (hora: string) => `Confirmamos de nuevo. Este total vale hasta las ${hora}.`,
  revisaLoQueCambio: 'Revisa lo que cambió antes de pagar.',
  vencio: 'Venció',
  vencioALas: 'Este total venció a las',
  vencido: 'Pasaron 15 minutos y el total venció. Vuelve a confirmar para ver lo que hay y su precio.',
  entregaVentana: (ventana: string) => `Entrega: ${ventana}`,
  telefonoDe: 'Teléfono de contacto:',
  siFaltaTitulo: 'Si falta un producto',
  siFaltaTexto:
    'Si al retirar falta un producto, lo buscamos en otro comercio y pagas lo mismo. Si nadie lo tiene, o elegiste sacarlo, anulamos su cobro el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco.',
  quienVende: 'Quién vende',
  vende: (vendedor: string, boleta: string) => `Vende: ${vendedor}. ${boleta}.`,
  reclamosAntes: 'Reclamos: escríbenos a ',
  condiciones: 'Condiciones del pedido (se abre en otra pestaña)',
  acepto: 'Leí y acepto las condiciones del pedido.',
  noPagar: 'No pagar no tiene costo.',

  // 10: cancelar
  cancelarPregunta: '¿Cancelar este pedido?',
  cancelarTexto: 'No tiene costo.',
  seguir: 'Seguir con el pedido',
  cancelando: 'Cancelando…',
  cancelamos: 'Cancelamos el pedido. No se cobró nada.',
  errCancelar: 'No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.',
  yaCancelado: 'Otra persona de tu grupo ya canceló este pedido.',

  // 11: errores
  errCarga: 'No pudimos traer tu pedido. Revisa tu conexión e inténtalo de nuevo.',
  errConfirmar: 'No pudimos confirmar el total. Revisa tu conexión y vuelve a intentarlo. Tu pedido sigue aquí.',
  nadaDisponible: 'Ahora ningún comercio tiene estos productos. No hay nada que pagar. Tu pedido sigue aquí para intentarlo más tarde.',
  cambioMientras: 'Este pedido cambió mientras lo revisabas. Te mostramos cómo quedó.',
  noEncontrado: 'No encontramos este pedido.',
  irATuPedido: 'Ir a tu pedido',
  apagado: 'El pedido no está disponible por ahora.',

  // 9.8: la página de las condiciones
  condTitulo: 'Condiciones del pedido',
  condDocumento: 'Condiciones del pedido · MATU',
}

/**
 * [D1, política 0.12, sección 5] Las declaraciones `declaracion_pedidos_<calidad>`, tal cual: su
 * huella SHA-256 viaja en `huella_declaracion` y el backend la compara con la de su texto (decisión
 * 221). Cambiar una palabra es publicar otra versión de la política, y el backend la rechaza.
 */
const CUERPO_PEDIDOS =
  'a guardar los pedidos de sus insumos, con los productos, la dirección de entrega, el teléfono de contacto y lo que se pagó, para preparar, entregar y responder por cada pedido, y a enviar al comercio que lo prepara solo los productos y las cantidades, según la política de privacidad vigente.'

export const DECLARACION_PEDIDOS: Record<Calidad, string> = {
  titular: `Declaro que la persona que cuido me dijo hoy, en persona, que autoriza a MATU ${CUERPO_PEDIDOS} Yo solo registro su decisión.`,
  representante_legal: `Declaro que soy representante legal de la persona que cuido y que la referencia que indico corresponde al documento que lo acredita. Como su representante, autorizo a MATU ${CUERPO_PEDIDOS}`,
  cuidador_de_hecho: `Declaro que cuido a esta persona y que no soy su representante legal. Autorizo a MATU ${CUERPO_PEDIDOS} Leí el aviso sobre el límite de esta autorización.`,
}

/** SHA-256 en hexadecimal minúscula del texto en UTF-8, como `huella()` del backend. */
export async function huellaDe(texto: string): Promise<string> {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(texto))
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, '0')).join('')
}

/** 12: el bloque de Grupo familiar y su confirmación. */
export const GRUPO_PEDIDOS = {
  titulo: 'Permiso para pedir sus insumos',
  sinAutorizar: 'Sin permiso todavía. Se pide la primera vez que haces un pedido.',
  retirarDe: (pila: string) => `Retirar la autorización de los pedidos de ${pila}`,
  volverDe: (pila: string) => `Volver a autorizar los pedidos de ${pila}`,
  verDireccion: 'Ver la dirección de entrega',
  verDireccionDe: (pila: string) => `Ver la dirección de entrega de ${pila}`,
  pregunta: (pila: string) => `¿Retirar la autorización de los pedidos de ${pila}?`,
  puntos: (pila: string) => [
    { texto: `Ya no se pueden hacer pedidos para ${pila} desde MATU, desde ahora.` },
    { texto: 'Cancelamos sin costo los pedidos sin pagar y borramos la dirección y el teléfono que se copiaron en ellos.', fuerte: true },
    // MATU-62 (6.4) [A5.4]: siempre, sin depender de que haya un pago en curso.
    { texto: 'Si hay un pago en curso y se aprueba, lo anulamos completo el mismo día.' },
    { texto: 'Los pedidos ya pagados siguen hasta que se entreguen.' },
    { texto: `La dirección de entrega de ${pila} queda guardada para cuando vuelvas a autorizar. Puedes vaciarla cuando quieras.` },
    { texto: 'La lista de insumos se puede seguir imprimiendo y compartiendo.' },
    { texto: 'Su ficha, sus insumos y los enlaces de relevo no cambian.' },
  ],
  retirada: (pila: string) => `Autorización retirada. Ya no se pueden hacer pedidos para ${pila}.`,
  autorizada: (pila: string) => `Pedidos autorizados. Ya puedes hacer pedidos para ${pila}.`,
}

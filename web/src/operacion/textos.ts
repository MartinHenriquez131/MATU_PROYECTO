// Textos de la consola de operación (MATU-81), tal cual los da la especificación del diseñador
// (docs/diseno/matu-81-operacion.md v1.1). Marcas de origen: [A81] el analista, [L nn] lenguaje.md,
// [C63] la consola del comercio, [E39] Entrar de MATU-39, [NUEVO] del diseñador (Jorge aprueba) y
// [FRONTEND] un texto que la especificación no trae y que este archivo propone (va en el informe).
// Nunca nombres de personas, direcciones, grupos, correos, la tarjeta ni el código de retiro. Sin
// «token», «sesión», «stock», «inválido», «rechazado» ni «fallido».
import { ENTRAR as ENTRAR_FAMILIA, GENERAL } from '../familia/textos'
import { pesos } from '../familia/textosCatalogo'
import { MOTIVO_RECHAZO_FAMILIA } from '../familia/textosTusPedidos'
import type {
  AccionPedido,
  AnulacionVista,
  EstadoIncidencia,
  MotivoRechazo,
  ParteDetalle,
  TipoIncidencia,
  VentaVista,
} from '../compartido/api/operacion'

export const ESPACIO_DURO = String.fromCharCode(0xa0)
const minutos = (n: number) => (n === 1 ? `1${ESPACIO_DURO}minuto` : `${n}${ESPACIO_DURO}minutos`)

/** 2.1: el `<title>` de cada ruta. El del pedido no lleva la referencia (C7). [NUEVO] */
export const TITULO_OPERACION = {
  entrar: 'Entrar a operación · MATU',
  pedidos: 'Pedidos · Operación · MATU',
  pedido: 'Pedido · Operación · MATU',
  retractos: 'Retractos · Operación · MATU',
  incidencias: 'Incidencias · Operación · MATU',
  cobros: 'Cobros · Operación · MATU',
  catalogo: 'Catálogo · Operación · MATU',
}

/** 2.2 y 3: el marco. [NUEVO] salvo «Salir» [E39]. */
export const MARCO = {
  consola: 'Operación de MATU',
  equipo: 'Equipo de MATU',
  vale: (hora: string) => `Tu entrada vale hasta las ${hora}.`,
  salir: 'Salir',
  secciones: 'Secciones de operación',
  pedidos: 'Pedidos',
  retractos: 'Retractos',
  incidencias: 'Incidencias',
  cobros: 'Cobros',
  catalogo: 'Catálogo',
  rotuloTitulo: 'Datos de prueba.',
  rotuloTexto: 'Estos pedidos, pagos y comercios son inventados. Los pagos son del ambiente de prueba de Transbank.',
  privacidad: 'Aquí no ves a quién cuida la familia ni dónde vive. Abrir un pedido queda registrado, y la familia lo ve en la copia de sus datos.',
  volverAIntentar: GENERAL.volverAIntentar, // [L 26]
  /** [L 8] sin «Lo que escribiste sigue aquí.». */
  errorAlCargar: GENERAL.errorAlCargar,
  /** [L 8] completo. */
  error: GENERAL.error,
  actualizado: (hora: string) => `Actualizado a las ${hora}.`, // [C63]
  actualizar: 'Actualizar', // [C63]
  actualizando: 'Actualizando…', // [C63]
}

/** 4: Entrar al equipo de MATU. */
export const ENTRAR = {
  titulo: 'Entrar a operación', // [NUEVO]
  bajada: 'Para el equipo de MATU. Después de la contraseña te pedimos el código de tu teléfono.', // [NUEVO]
  correo: ENTRAR_FAMILIA.correo, // [E39]
  contrasena: ENTRAR_FAMILIA.contrasena, // [E39]
  seguir: 'Seguir', // [NUEVO]
  revisando: 'Revisando…', // [NUEVO]
  faltan: ENTRAR_FAMILIA.faltan, // [E39]
  aLaFamiliaAntes: '¿No eres del equipo? Entra en la ', // [NUEVO]
  aLaFamiliaEnlace: 'app de MATU para familias', // [NUEVO]
  aLaFamiliaDespues: '.',
  credenciales: ENTRAR_FAMILIA.credenciales, // [E39]
  espera: (n: number) => `Hubo varios intentos de entrar. Espera ${minutos(n)}.`, // [C63] 4.3
  noDisponible: ENTRAR_FAMILIA.noDisponible, // [E39] [L 9.1]
  otraTitulo: 'Esta cuenta no es del equipo de MATU.', // [NUEVO]
  otraTexto: 'Si atiendes un comercio, entra en la entrada del comercio. Si cuidas a alguien, entra en la app para familias.', // [NUEVO]
  codigoTitulo: 'Escribe el código de tu teléfono', // [NUEVO]
  codigoBajada: 'Ábrelo en la aplicación de códigos de tu teléfono. Cambia cada 30 segundos.', // [NUEVO]
  codigoEtiqueta: 'Código de 6 números', // [NUEVO]
  plazo: (hora: string) => `Tienes hasta las ${hora} para escribirlo.`, // [NUEVO]
  entrar: ENTRAR_FAMILIA.boton, // [E39]
  entrando: ENTRAR_FAMILIA.enviando, // [E39]
  volver: 'Volver a la contraseña', // [NUEVO]
  menosDeSeis: 'Escribe los 6 números del código.', // [C63] 7.2
  noCoincideTitulo: 'Ese código no coincide.', // [NUEVO]
  noCoincideTexto: 'Revisa que sea el de MATU en tu aplicación y escribe el que se ve ahora.', // [NUEVO]
  bloqueadoTitulo: 'Hubo 5 códigos que no coinciden.', // [NUEVO]
  bloqueadoTexto: (n: number) => `Espera ${minutos(n)} y vuelve a entrar con tu contraseña. Si perdiste tu teléfono, pide que te den de alta de nuevo.`, // [NUEVO]
  vencioTitulo: 'Pasaron más de 5 minutos.', // [NUEVO]
  vencioTexto: 'Vuelve a escribir tu contraseña para pedir otro código.', // [NUEVO]
  sinRedisTitulo: 'No podemos revisar el código ahora.', // [NUEVO]
  sinRedisTexto: 'Vuelve a intentarlo en unos minutos.', // [NUEVO]
  red: GENERAL.errorAlCargar, // [L 8], sin «Lo que escribiste sigue aquí.»
  vencida: 'Tu entrada venció. Vuelve a entrar con tu contraseña y el código de tu teléfono.', // [NUEVO]
  salio: ENTRAR_FAMILIA.salio, // [E39]
}

/** 5.5: las palabras del estado del pedido. [NUEVO] */
export const ESTADO_PEDIDO: Record<string, string> = {
  pagado: 'Pagado',
  enviado_a_comercio: 'En el comercio',
  preparando: 'En preparación',
  listo_retiro: 'Listo para retirar',
  retirado: 'Por despachar',
  asignado: 'Sin repartidor',
  sin_repartidor: 'Sin repartidor',
  en_ruta: 'En camino',
  entregado: 'Entregado',
  cerrado: 'Entregado',
  no_entregado: 'No se entregó',
  reprogramado: 'Reprogramado',
  cancelado: 'Cancelado',
  cancelado_con_devolucion: 'Cancelado',
}

/** 5: Pedidos. */
export const PEDIDOS = {
  titulo: 'Pedidos',
  buscarEtiqueta: 'Referencia del pedido', // [NUEVO]
  buscar: 'Buscar', // [NUEVO]
  buscando: 'Buscando…', // [NUEVO]
  buscarVacio: 'Escribe la referencia del pedido.', // [NUEVO]
  mostrando: (ref: string) => `Mostrando el pedido ${ref}.`, // [NUEVO]
  verTodos: 'Ver todos', // [NUEVO]
  sinResultado: (ref: string) => `No hay un pedido con la referencia ${ref}. Revisa que esté bien escrita.`, // [NUEVO]
  mostrar: 'Mostrar', // [NUEVO]
  porAtender: 'Por atender',
  enCamino: 'En camino',
  conProblema: 'Con problema',
  cerrados: 'Cerrados',
  cancelados: 'Cancelados',
  todos: 'Todos',
  pedido: 'Pedido',
  partes: (n: number) => (n === 1 ? '1 parte' : `${n} partes`),
  pagadoEl: (dia: string, hora: string) => `Pagado el ${dia} a las ${hora}`,
  incidenciaAbierta: 'Incidencia abierta', // [NUEVO]
  devolucionSinTerminar: 'Devolución sin terminar', // [NUEVO]
  verMas: 'Ver más pedidos', // [FRONTEND] del esquema 5.1
  cargando: 'Cargando los pedidos…', // [C63]
  vacio: (chip: string) => `No hay pedidos en «${chip}».`, // [NUEVO]
  vacioPorAtender: 'Cuando se pague uno, aparece aquí.', // [NUEVO]
  errorAlTraer: 'No pudimos traer los pedidos. Revisa tu conexión y vuelve a intentarlo.', // [C63]
  elige: 'Elige un pedido de la lista para ver sus partes, su pago y lo que pasó.', // [FRONTEND] del esquema 5.2
}

/** 6: Un pedido. */
export const PEDIDO = {
  volverPedidos: 'Volver a los pedidos',
  volverCobros: 'Volver a los cobros', // [NUEVO] 10
  titulo: (ref: string) => `Pedido ${ref}`,
  pagadoEl: (fecha: string, hora: string) => `Pagado el ${fecha} a las ${hora}`,
  partes: 'Partes', // [NUEVO]
  parte: 'Parte',
  ficticio: '(comercio ficticio)', // [L 11]
  faltanDe: (n: number, de: number) => `Faltan ${n} de ${de}`, // [C63] 6.5
  devuelto: 'Devuelto', // [NUEVO]
  devolucionEnCurso: 'Devolución en curso', // [NUEVO]
  cambio: 'Este pedido cambió mientras lo veías. Te mostramos cómo quedó. Revisa si todavía hace falta.', // [NUEVO]
  yaNoEsta: 'Este pedido ya no está disponible.', // [NUEVO]
  cargando: 'Cargando el pedido…', // [FRONTEND] del molde de [C63]
  sinTransbank: 'No pudimos hablar con Transbank. El pedido no cambió. Vuelve a intentarlo en unos minutos.', // [NUEVO]
  devolucionNoSalio: (ref: string, monto: number) => `Cancelaste el pedido ${ref}. La devolución de ${pesos(monto)} no salió todavía: revísala en «Cobros».`, // [NUEVO]
  error: GENERAL.errorAlCargar, // [L 8], sin «Lo que escribiste sigue aquí.»
}

/** 6.3: el estado de la parte, con las palabras del comercio. [C63] 5.4 */
export const ESTADO_PARTE: Record<ParteDetalle['estado'], string> = {
  enviada: 'Por preparar',
  preparando: 'Preparando',
  lista: 'Listo para retirar',
  retirada: 'Retirado',
  cancelada: 'Cancelado',
}

/** 6.3: el estado de una línea. [NUEVO] */
export const ESTADO_LINEA = {
  porMarcar: 'Por marcar',
  loTiene: 'Lo tiene',
  falto: 'Faltó',
  devuelto: 'Devuelto',
}

/** 6.5: los diálogos de cada acción. Todos [NUEVO]. `monto` es `monto_a_devolver` de la API. */
export const ACCIONES: Record<
  AccionPedido,
  { boton: string; titulo: (ref: string) => string; texto: string; destacado: (monto: number) => string; ocupado: string; seguir: string; hecho: (ref: string, monto: number) => string }
> = {
  en_camino: {
    boton: 'Marcar en camino',
    titulo: (ref) => `¿Marcar en camino el pedido ${ref}?`,
    texto: 'La familia ve que su pedido salió a entregarse.',
    destacado: (m) => (m > 0 ? `Se devuelven ${pesos(m)} a la misma tarjeta.` : 'No se devuelve dinero.'),
    ocupado: 'Marcando…',
    seguir: 'Volver al pedido',
    hecho: (ref) => `Marcaste en camino el pedido ${ref}.`,
  },
  entregado: {
    boton: 'Marcar entregado',
    titulo: (ref) => `¿Marcar entregado el pedido ${ref}?`,
    texto: 'Hazlo solo cuando el pedido ya esté en manos de quien lo recibe. Esto no se deshace.',
    destacado: (m) => (m > 0 ? `Se devuelven ${pesos(m)} a la misma tarjeta, por lo que faltó.` : 'No se devuelve dinero.'),
    ocupado: 'Marcando…',
    seguir: 'Volver al pedido',
    hecho: (ref) => `Marcaste entregado el pedido ${ref}.`,
  },
  no_entregado: {
    boton: 'Marcar no entregado',
    titulo: (ref) => `¿Marcar no entregado el pedido ${ref}?`,
    texto: 'Hazlo si nadie pudo recibirlo. Después puedes cancelarlo con devolución.',
    destacado: (m) => (m > 0 ? `Se devuelven ${pesos(m)} a la misma tarjeta.` : 'No se devuelve dinero ahora.'),
    ocupado: 'Marcando…',
    seguir: 'Volver al pedido',
    hecho: (ref) => `Marcaste no entregado el pedido ${ref}.`,
  },
  cancelar_con_devolucion: {
    boton: 'Cancelar con devolución',
    titulo: (ref) => `¿Cancelar con devolución el pedido ${ref}?`,
    texto: 'Se cancelan todas sus partes y los comercios ven que no deben prepararlas. Esto no se deshace.',
    destacado: (m) => (m > 0 ? `Se devuelven ${pesos(m)} a la misma tarjeta con que se pagó, envío incluido.` : 'No se devuelve dinero.'),
    ocupado: 'Cancelando…',
    seguir: 'No cancelar',
    hecho: (ref, m) => `Cancelaste el pedido ${ref}. Estamos devolviendo ${pesos(m)} a la misma tarjeta.`,
  },
}

/** 6.4: el código de retiro. Todos [NUEVO]. */
export const CODIGO = {
  sinCodigo: 'Código de retiro: todavía no hay uno.',
  vigente: 'Código de retiro: hay uno vigente.',
  vencido: 'Código de retiro: venció.',
  bloqueado: 'Código de retiro: se bloqueó por demasiados intentos en el comercio.',
  usado: 'Código de retiro: ya se usó.',
  cuandoEsteListo: 'Código de retiro: cuando el comercio lo tenga listo.',
  generar: 'Generar el código',
  generarNuevo: 'Generar un código nuevo',
  generando: 'Generando…',
  tituloGenerar: (ref: string) => `¿Generar el código de retiro de la parte ${ref}?`,
  tituloNuevo: (ref: string) => `¿Generar un código nuevo para la parte ${ref}?`,
  texto: 'Lo verás una sola vez. Tenlo a mano para dárselo a quien va a retirar el pedido.',
  anteriorDejaDeServir: 'El código anterior deja de servir. Si ya se lo diste a alguien, avísale que use el nuevo.',
  seguir: 'Volver al pedido',
  titulo: (ref: string) => `Código de retiro · Parte ${ref}`,
  paraLector: (codigo: string) => `Código: ${codigo.split('').join(' ')}`,
  vence: (fecha: string, hora: string) => `Vence el ${fecha} a las ${hora}.`,
  daselo: (comercio: string) => `Dáselo a quien va a retirar el pedido en ${comercio}.`,
  soloAhora: 'Solo lo verás ahora. Si generas otro, este deja de servir.',
  yaLoTengo: 'Ya lo tengo',
  cambio: 'Esta parte cambió mientras la veías. Te mostramos cómo quedó.',
  noPudimos: 'No pudimos generar el código. Vuelve a intentarlo en unos minutos.',
  error: GENERAL.errorAlCargar, // [L 8], sin «Lo que escribiste sigue aquí.»
}

/** 6.6: lo que pasó. */
export const LINEA_TIEMPO = {
  titulo: 'Lo que pasó', // [NUEVO]
  deA: (desde: string, hacia: string) => `de ${desde} a ${hacia}`,
  actor: { familia: 'La familia', operacion: 'Equipo de MATU', sistema: 'MATU, de forma automática' } as const, // [NUEVO]
  motivo: {
    total_vencio: 'Venció el total',
    familia_cancela: 'La familia lo canceló',
    familia_cambia_carrito: 'La familia cambió el pedido',
    autorizacion_retirada: 'Se retiró la autorización de pedidos',
    persona_borrada: 'La familia borró los datos',
    pago_aprobado: 'Transbank aprobó el pago',
    producto_faltante: 'Faltaron todos los productos',
  } as Record<string, string>, // [NUEVO]
  // [FRONTEND] Los hechos de la línea de tiempo que no son un cambio de estado del pedido (decisión 456).
  parte: (comercio: string, estado: string) => `Parte de ${comercio}: ${estado}`,
  cobro: (monto: number) => `Transbank aprobó el pago de ${pesos(monto)}`,
  anulacion: (monto: number, estado: string) => `Devolución de ${pesos(monto)}: ${estado}`,
  retractoPedido: 'La familia pidió un retracto',
  retractoDevuelto: 'Retracto: se devolvió el dinero',
  retractoSinDevolucion: 'Retracto: sin devolución',
  incidenciaAbierta: 'Se anotó una incidencia',
  incidenciaResuelta: 'Se resolvió una incidencia',
  vacio: 'Todavía no hay nada que mostrar.',
}

/** 7: el pago del pedido. [NUEVO] */
export const PAGO = {
  titulo: 'Pago',
  totalConfirmado: 'Total confirmado',
  cobrado: 'Cobrado',
  nadaTodavia: 'Nada todavía',
  devuelto: 'Devuelto',
  quedaCobrado: 'Queda cobrado',
  venta: 'Venta',
  ordenDeCompra: 'Orden de compra',
  devoluciones: 'Devoluciones',
  revisionTitulo: 'Este pago necesita revisión.',
  revisionTexto: 'Lo cobrado o lo devuelto no calza con el total confirmado. Anota una incidencia si todavía no hay una.',
  anotar: 'Anotar una incidencia',
  cargando: 'Cargando el pago…',
  error: 'No pudimos traer el pago de este pedido. Vuelve a intentarlo.',
}

export const ESTADO_VENTA: Record<VentaVista['estado'], string> = {
  iniciada: 'Iniciada',
  autorizando: 'Esperando a Transbank',
  aprobada: 'Aprobada',
  rechazada: 'No aprobada',
  error: 'Sin respuesta clara',
}

export const MOTIVO_ANULACION: Record<AnulacionVista['motivo'], string> = {
  pago_tardio: 'Pago tardío',
  producto_no_entregado: 'Producto no entregado',
  cancelacion: 'Cancelación',
  retracto: 'Retracto',
}

export const ESTADO_ANULACION: Record<AnulacionVista['estado'], string> = {
  hecha: 'Hecha',
  en_curso: 'En curso',
  rechazada: 'Sin terminar',
}

/** 8: Retractos. */
export const RETRACTOS = {
  titulo: 'Retractos',
  fila: (ref: string) => `Retracto del pedido ${ref}`,
  porLaApp: 'Por la app',
  porCorreo: 'Por correo',
  pedidoEl: (dia: string) => `Pedido el ${dia}`,
  responderAntes: (fecha: string) => `Responder antes del ${fecha}`,
  vencio: (fecha: string) => `El plazo venció el ${fecha}.`,
  vacio: 'No hay retractos por resolver.',
  vacioEn: (chip: string) => `No hay retractos en «${chip}».`, // [NUEVO] 8.2
  hayMas: 'Hay más de 200 retractos aquí. Mostramos los primeros 200.', // [NUEVO] 8.2 v1.1; hay_mas (decisión 466)
  cargando: 'Cargando los retractos…', // [FRONTEND] del molde de [C63]
  errorAlTraer: 'No pudimos traer los retractos. Revisa tu conexión y vuelve a intentarlo.', // [FRONTEND] del molde de [C63]
  elige: 'Elige un retracto de la lista para ver sus productos y resolverlo.', // [FRONTEND]
  volver: 'Volver a los retractos', // [FRONTEND]
  porResolver: 'Por resolver',
  devuelto: 'Devuelto',
  devueltos: 'Devueltos', // [NUEVO] chip de 8.2
  sinDevolucion: 'Sin devolución',
  productos: 'Productos que devuelve',
  incluyeEnvio: (si: boolean) => `Incluye el envío: ${si ? 'sí' : 'no'}`,
  seDevolverian: 'Se devolverían',
  devolver: (monto: number) => `Devolver ${pesos(monto)}`,
  noDevolver: 'No devolver',
  verPedido: 'Ver el pedido',
  resueltoEl: (fecha: string, hora: string) => `Resuelto el ${fecha} a las ${hora}.`, // [NUEVO] 8.3
  porQue: '¿Por qué no se devuelve?',
  motivo: { sello_abierto: 'El sello del producto se abrió.', producto_no_recibido: 'MATU no recibió el producto de vuelta.' } as Record<MotivoRechazo, string>,
  laFamiliaVe: 'La familia ve este motivo.',
  cancelar: 'Cancelar',
  eligeMotivo: 'Elige por qué no se devuelve.',
  devolverTitulo: (monto: number) => `¿Devolver ${pesos(monto)} por este retracto?`,
  esDelPedido: (ref: string) => `Es el retracto del pedido ${ref}. Esto no se deshace.`,
  devolverDestacado: (monto: number) => `Se devuelven ${pesos(monto)} a la misma tarjeta con que se pagó.`,
  devolviendo: 'Devolviendo…',
  volverAlRetracto: 'Volver al retracto',
  devolvisteHecho: (monto: number, ref: string) => `Devolviste ${pesos(monto)} por el retracto del pedido ${ref}. Cuándo se ve en la cuenta depende del banco.`,
  noDevolverTitulo: '¿No devolver el dinero de este retracto?',
  /** O3 del analista: `{motivo}` es el texto exacto que lee la familia, no el de la consola. */
  noDevolverDestacado: (motivo: MotivoRechazo) => `No se devuelve dinero. La familia ve el motivo: ${MOTIVO_RECHAZO_FAMILIA[motivo]}`,
  guardando: 'Guardando…',
  respondisteHecho: (ref: string) => `Respondiste el retracto del pedido ${ref} sin devolver dinero.`,
  cambio: 'Este retracto cambió mientras lo veías. Te mostramos cómo quedó.',
  sinTransbank: 'No pudimos hablar con Transbank. No se devolvió nada. Vuelve a intentarlo en unos minutos.',
  error: GENERAL.errorAlCargar, // [L 8], sin «Lo que escribiste sigue aquí.»
  /** 8.5 */
  seccion: 'Retractos',
  registrar: 'Registrar un retracto por correo',
  plazoVence: (fecha: string) => `El plazo vence el ${fecha}.`,
  correo: 'Correo de quien lo pidió',
  correoAyuda: 'Escríbelo tal como viene en el correo. Tiene que ser de quien administra el grupo de este pedido.',
  queProductos: '¿Qué productos devuelve?',
  cuantos: '¿Cuántos?',
  registrarBoton: 'Registrar el retracto',
  registrando: 'Registrando…',
  registrado: (ref: string) => `Registraste el retracto del pedido ${ref}. Resuélvelo en «Retractos».`,
  irARetractos: 'Ir a Retractos',
  sinCorreo: 'Escribe el correo de quien lo pidió.',
  correoMalo: 'Escribe un correo, por ejemplo nombre@example.com.',
  ningunProducto: 'Elige al menos un producto.',
  noEsAdminTitulo: 'Ese correo no es de quien administra el grupo de este pedido.',
  noEsAdminTexto: 'Revisa el correo. Si lo mandó otra persona, respóndele que lo pida quien administra.',
  fueraDePlazo: (fecha: string) => `Este pedido ya no tiene plazo de retracto: venció el ${fecha}.`,
  noRetractable: 'Elige productos que se entregaron, hasta lo que queda por devolver.', // [FRONTEND] 422 producto-no-retractable, también con unidades ya pedidas en otro retracto
  /** [NUEVO] MATU-114, 429 demasiados-intentos (§40, 8.5, P3): los minutos de `Retry-After` hacia arriba; sin la cabecera, la frase de L 7.3 («unos minutos»). */
  muchosIntentos: (n: number | null) =>
    `Hiciste muchos intentos con correos que no corresponden. ${n === null ? 'Vuelve a intentarlo en unos minutos.' : `Espera ${minutos(n)} antes de volver a intentar.`}`,
  noDisponible: ENTRAR_FAMILIA.noDisponible, // [L 9.1] MATU-114, 503: sin el servicio no se busca el correo
}

/** 9: Incidencias. */
export const INCIDENCIAS = {
  titulo: 'Incidencias',
  abiertas: 'Abiertas',
  enGestion: 'En gestión',
  resueltas: 'Resueltas',
  pedido: (ref: string) => `Pedido ${ref}`,
  anotadaEl: (dia: string, hora: string) => `Anotada el ${dia} a las ${hora}`,
  vacioAbiertas: 'No hay incidencias abiertas.',
  vacio: (chip: string) => `No hay incidencias en «${chip}».`,
  cargando: 'Cargando las incidencias…', // [FRONTEND] del molde de [C63]
  errorAlTraer: 'No pudimos traer las incidencias. Revisa tu conexión y vuelve a intentarlo.', // [FRONTEND] del molde de [C63]
  elige: 'Elige una incidencia de la lista para leerla y resolverla.', // [FRONTEND]
  volver: 'Volver a las incidencias', // [FRONTEND]
  verPedido: 'Ver el pedido',
  nota: 'Nota',
  /** Decisión 471: la clave de las notas se destruyó con los datos de la persona. Texto aprobado por Jorge el 17-11. */
  notaNoDisponible: 'La nota ya no está disponible: se borró con los datos de la persona.',
  laTienesTu: 'La tienes tú.',
  comoSeResolvio: 'Cómo se resolvió',
  resueltaEl: (fecha: string, hora: string) => `Resuelta el ${fecha} a las ${hora}.`,
  resolver: 'Resolver',
  pasarAGestion: 'Pasar a en gestión',
  quedoEnGestion: 'La incidencia quedó en gestión.',
  // MATU-128 (C8 del cierre del analista): qué no lleva y quién la lee, como en el contrato.
  ayuda: 'No escribas nombres, RUT, teléfonos, correos, datos de salud ni la dirección, ni quién de la familia reclamó. La leen quien pagó el pedido y quien administra o cuida.', // [A81, C11, C8]
  contador: (n: number) => `${n} de 500 caracteres`, // [L, textos.ts]
  anotarTitulo: 'Anotar una incidencia',
  quePaso: '¿Qué pasó?',
  guardar: 'Guardar la incidencia',
  guardando: 'Guardando…',
  cancelar: 'Cancelar',
  anotaste: (ref: string) => `Anotaste la incidencia en el pedido ${ref}.`,
  eligeQuePaso: 'Elige qué pasó.',
  notaVacia: 'Escribe qué pasó, sin nombres ni datos de salud.',
  muyLarga: 'La nota admite hasta 500 caracteres. Acórtala un poco para guardarla.',
  /** MATU-128 (C8): el 422 nota-con-contacto al anotar. */
  conContacto: 'La nota no puede llevar correos, teléfonos ni RUT. Quítalos para guardarla.',
  /** MATU-128 (revisión visual, P3): el mismo 422 al resolver, porque el campo se llama «Cómo se resolvió». */
  conContactoResolucion: 'Lo que escribas aquí no puede llevar correos, teléfonos ni RUT. Quítalos para guardarlo.',
  soloPagados: 'Solo se anotan incidencias de pedidos pagados.',
  marcarResuelta: 'Marcar resuelta',
  sinResolucion: 'Escribe cómo se resolvió, sin nombres ni datos de salud.',
  marcasteResuelta: 'Marcaste resuelta la incidencia.',
  otraPersona: 'Otra persona del equipo cambió esta incidencia mientras la veías. Te mostramos cómo quedó. Lo que escribiste sigue aquí.',
  /** El de arriba cuando lo escrito se descarta porque ya quedó resuelta. */
  otraPersonaSinTexto: 'Otra persona del equipo cambió esta incidencia mientras la veías. Te mostramos cómo quedó.',
  yaEstabaResuelta: 'Ya estaba resuelta.',
  error: GENERAL.error, // [L 8] completo
  errorAlCargar: GENERAL.errorAlCargar,
}

/** 9.1: el estado de una incidencia. [NUEVO] */
export const ESTADO_INCIDENCIA: Record<EstadoIncidencia, string> = { abierta: 'Abierta', en_gestion: 'En gestión', resuelta: 'Resuelta' }

/** 9.4: los tipos, palabras de la consola. [NUEVO] */
export const TIPO_INCIDENCIA: Record<TipoIncidencia, string> = {
  faltante: 'Falta un producto',
  entrega_fallida: 'No se pudo entregar',
  reclamo_familia: 'Reclamo de la familia',
  cobro_sin_respuesta: 'Cobro sin respuesta',
  devolucion_pendiente: 'Devolución pendiente',
  otro: 'Otra cosa',
}

/** 10: Cobros por revisar. [NUEVO] */
export const COBROS = {
  titulo: 'Cobros',
  bajada: 'Ventas sin respuesta y devoluciones sin terminar. Aquí no ves la tarjeta ni el código de autorización.',
  ventas: (n: number) => `Ventas sin respuesta (${n})`,
  anulaciones: (n: number) => `Devoluciones sin terminar (${n})`,
  sinVentas: 'No hay ventas sin respuesta.',
  sinAnulaciones: 'No hay devoluciones sin terminar.',
  pedido: (ref: string) => `Pedido ${ref}`,
  ordenDeCompra: (bo: string) => `Orden de compra ${bo}`,
  iniciada: (hora: string, n: number) => `Iniciada a las ${hora}, hace ${minutos(n)}`,
  desde: (hora: string) => `Desde las ${hora}`,
  cargando: 'Cargando los cobros…',
  errorAlTraer: 'No pudimos traer los cobros. Revisa tu conexión y vuelve a intentarlo.',
}

/** 11: Catálogo de prueba. */
export const CATALOGO = {
  titulo: 'Catálogo',
  aviso: 'El precio nuevo vale solo para los pedidos que se confirmen desde ahora. Los confirmados y los pagados mantienen su precio.', // [NUEVO]
  soloPrueba: 'Solo puedes cambiar los comercios de prueba.', // [NUEVO]
  ficticio: '(comercio ficticio)', // [L 11]
  noEsDePrueba: 'Este comercio no es de prueba: aquí no se cambia.', // [NUEVO]
  ivaIncluido: 'IVA incluido', // [NUEVO]
  tiene: 'Tiene', // [NUEVO]
  seOfrece: 'Se ofrece', // [C63]
  noSeOfrece: 'No se ofrece', // [C63]
  cambiar: 'Cambiar', // [NUEVO]
  precioEtiqueta: 'Precio, con IVA incluido', // [NUEVO]
  seVeraComo: (precio: string) => `Se verá como ${precio}.`, // [NUEVO]
  cuantos: '¿Cuántos tiene?', // [NUEVO]
  seOfreceEnMatu: 'Se ofrece en MATU', // [NUEVO]
  guardar: 'Guardar', // [L 5.4]
  guardando: 'Guardando…', // [L 5.4]
  cancelar: 'Cancelar',
  dialogoTitulo: (producto: string, precio: number) => `¿Cambiar el precio de ${producto} a ${pesos(precio)}?`, // [NUEVO]
  dialogoTexto: (antes: number) => `Antes era ${pesos(antes)}.`, // [NUEVO]
  dialogoDestacado: 'Vale solo para los pedidos que se confirmen desde ahora.', // [NUEVO]
  cambiarPrecio: 'Cambiar el precio', // [NUEVO]
  volverAEditar: 'Volver a editar', // [NUEVO]
  guardado: (producto: string, precio: number, n: number) => `Guardado: ${producto} a ${pesos(precio)}, tiene ${n}.`, // [NUEVO]
  errPrecio: 'Escribe el precio en pesos, mayor que 0, sin decimales. Por ejemplo, 12990.', // [NUEVO]
  errNumero: 'Escribe un número, desde 0.', // [C63] 8.4
  errMaximo: 'Escribe un número hasta 9.999.', // [C63] 8.4
  otraPersona: 'Otra persona cambió este producto mientras lo editabas. Te mostramos cómo quedó.', // [C63] 8.4
  noSePuede: 'Este producto no se puede cambiar aquí: su comercio no es de prueba.', // [NUEVO]
  error: GENERAL.error, // [L 8] completo
  cargando: 'Cargando el catálogo…', // [NUEVO]
  vacio: 'No hay comercios de prueba con productos.', // [NUEVO]
  errorAlTraer: 'No pudimos traer el catálogo. Revisa tu conexión y vuelve a intentarlo.', // [NUEVO]
}

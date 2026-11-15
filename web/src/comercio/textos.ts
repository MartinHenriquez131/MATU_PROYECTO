// Textos de la consola del comercio (MATU-63), tal cual los da la especificación del diseñador
// (docs/diseno/matu-63-comercio.md v1.0, secciones 3 a 8 y 12). Marcas de origen: [A45] el
// analista, [AJUSTE] un [A45] cambiado por el diseñador, [L nn] lenguaje.md, [E39] Entrar de
// MATU-39 y [NUEVO] del diseñador, que Jorge aprueba. Nunca nombres de personas, direcciones,
// montos del pedido ni el código de retiro. Sin «stock», «reserva», «sesión» ni «inválido».
import { ENTRAR as ENTRAR_FAMILIA, GENERAL } from '../familia/textos'

export const ESPACIO_DURO = String.fromCharCode(0xa0)
const minutos = (n: number) => (n === 1 ? `1${ESPACIO_DURO}minuto` : `${n}${ESPACIO_DURO}minutos`)

export const MARCO_COMERCIO = {
  consola: 'Pedidos de MATU',
  ficticio: '(comercio ficticio)', // [L 11]
  salir: 'Salir',
  secciones: 'Secciones del comercio',
  pedidosDeHoy: 'Pedidos de hoy',
  tusProductos: 'Tus productos',
}

/** 2.1: el `<title>` de cada ruta. */
export const TITULO_COMERCIO = {
  entrar: 'Entrar como comercio · MATU',
  pedidos: (nombre: string) => `Pedidos de hoy · ${nombre} · MATU`,
  pedido: (ref: string) => `Pedido ${ref} · MATU`,
  productos: (nombre: string) => `Tus productos · ${nombre} · MATU`,
  sinNombre: 'Pedidos de MATU · MATU',
}

/** 4: Entrar como comercio. */
export const ENTRAR_COMERCIO = {
  titulo: 'Entrar como comercio', // [NUEVO]
  bajada: 'Para quien atiende un comercio que trabaja con MATU.', // [NUEVO]
  correo: ENTRAR_FAMILIA.correo, // [E39]
  contrasena: ENTRAR_FAMILIA.contrasena, // [E39]
  boton: ENTRAR_FAMILIA.boton, // [E39]
  enviando: ENTRAR_FAMILIA.enviando, // [E39]
  faltan: ENTRAR_FAMILIA.faltan, // [E39]
  olvido: (contacto: string) => `¿Olvidaste tu contraseña? Avisa a MATU: ${contacto}.`, // [NUEVO] O2 // pragma: allowlist secret
  aLaFamiliaAntes: '¿Cuidas a alguien? Entra en la ', // [NUEVO]
  aLaFamiliaEnlace: 'app de MATU para familias', // [NUEVO]
  aLaFamiliaDespues: '.',
  credenciales: ENTRAR_FAMILIA.credenciales, // [E39]
  /** [E39] sin «pídele ayuda a alguien de tu familia» [AJUSTE]. */
  espera: (n: number) => `Hubo varios intentos de entrar. Espera ${minutos(n)}.`,
  vencida: ENTRAR_FAMILIA.vencida, // [L 8]
  salio: ENTRAR_FAMILIA.salio, // [E39]
  familiaTitulo: 'Esta cuenta es de la app para familias.', // [NUEVO] O1
  familiaTexto: 'Para ver los pedidos de un comercio, entra con la cuenta del comercio.', // [NUEVO]
  inactivaTitulo: 'Esta cuenta de comercio no está activa.', // [NUEVO]
  inactivaTexto: (contacto: string) => `Avisa a MATU: ${contacto}.`, // [NUEVO]
  noDisponible: ENTRAR_FAMILIA.noDisponible, // [E39] [L 9.1]
  error: GENERAL.error, // [L 8]
}

/** 5: Pedidos de hoy. */
export const PEDIDOS = {
  titulo: 'Pedidos de hoy',
  privacidad: 'Aquí ves solo los productos. MATU no te muestra de quién es el pedido ni a dónde va.', // [A45]
  actualizado: (hora: string) => `Actualizado a las ${hora}.`,
  actualizar: 'Actualizar',
  actualizando: 'Actualizando…',
  pedido: 'Pedido',
  productos: (n: number) => (n === 1 ? '1 producto' : `${n} productos`),
  grupoPorPreparar: 'Por preparar',
  grupoPreparando: 'Preparando',
  grupoListos: 'Listos para retirar',
  grupoRetirados: 'Retirados',
  grupoCancelados: 'Cancelados',
  conNumero: (texto: string, n: number) => `${texto} (${n})`,
  prepararAntes: (hora: string) => `Preparar antes de las ${hora}`,
  prepararAntesDel: (fecha: string, hora: string) => `Preparar antes del ${fecha}, ${hora}`,
  eraPara: (hora: string) => `Era para las ${hora}.`,
  eraParaDel: (fecha: string, hora: string) => `Era para el ${fecha}, ${hora}.`,
  esperandoRetiro: 'Esperando retiro',
  retiradoA: (hora: string) => `Retirado a las ${hora}`,
  noLoPrepares: 'No lo prepares.',
  elige: 'Elige un pedido de la lista para prepararlo.',
  llegoUno: (ref: string) => `Llegó un pedido nuevo: ${ref}.`, // [NUEVO]
  llegaron: (n: number) => `Llegaron ${n} pedidos nuevos.`, // [NUEVO]
  seCancelo: (ref: string) => `El pedido ${ref} se canceló. No lo prepares.`,
  cargando: 'Cargando los pedidos…',
  vacioTitulo: 'No hay pedidos por preparar.', // [A45]
  vacioTexto: 'Cuando llegue uno, aparece aquí.', // [NUEVO]
  errorAlTraer: 'No pudimos traer los pedidos. Revisa tu conexión y vuelve a intentarlo.', // [NUEVO]
  volverAIntentar: GENERAL.volverAIntentar, // [L 26]
  rotuloTitulo: 'Comercio de prueba.', // [A45]
  rotuloPedidos: 'Estos pedidos son inventados.', // [A45]
  pie: (contacto: string) => `¿Algo no calza? Avisa a MATU: ${contacto}.`, // [NUEVO] O2
}

/** 6: Un pedido. */
export const PEDIDO_COMERCIO = {
  volver: 'Volver a los pedidos',
  titulo: (ref: string) => `Pedido ${ref}`,
  estadoPorPreparar: 'Por preparar',
  estadoPreparando: 'Preparando',
  estadoListo: 'Listo para retirar',
  estadoRetirado: 'Retirado',
  estadoCancelado: 'Cancelado',
  llego: (hora: string) => `Llegó a las ${hora}`,
  productosTitulo: 'Productos',
  marca: 'Marca si tienes cada uno.',
  loTengo: 'Lo tengo', // [A45]
  noLoTengo: 'No lo tengo', // [A45]
  noLoCambies: 'No lo cambies por otra marca ni por otro producto. MATU se encarga del resto.', // [A45]
  cuantosFaltan: '¿Cuántos te faltan?', // [AJUSTE]
  pedidoLleva: (n: number) => `El pedido lleva ${n}.`, // [NUEVO]
  noPudimosGuardar: 'No pudimos guardar lo que marcaste. Vuelve a intentarlo.', // [NUEVO]
  despuesDeListo: 'Después de marcarlo listo ya no puedes cambiar lo que marcaste.', // [NUEVO]
  marcaCada: 'Marca cada producto: si lo tienes o no.', // [NUEVO]
  empezar: 'Empezar a preparar', // [A45]
  empezando: 'Empezando…', // [NUEVO]
  listo: 'Listo para retirar', // [A45]
  guardando: 'Guardando…', // [L 5.4]
  ningunoBoton: 'Avisar que no tengo ninguno', // [NUEVO] O3
  tocaEmpezar: 'Toca «Empezar a preparar» cuando vayas a buscar los productos.', // [NUEVO]
  faltanDe: (n: number, de: number) => `Faltan ${n} de ${de}`, // [NUEVO]
  listoTitulo: 'Pedido listo para retirar.', // [NUEVO]
  listoTexto: 'MATU le avisa a quien viene a buscarlo.', // [NUEVO]
  retiradoTitulo: 'Pedido retirado.', // [NUEVO]
  retiradoTexto: (hora: string) => `Se retiró a las ${hora}.`, // [NUEVO]
  canceladoTitulo: 'Este pedido se canceló. No lo prepares.', // [A45]
  canceladoTexto: 'Si ya sacaste productos, vuelve a dejarlos en su lugar.', // [NUEVO]
  canceladoNinguno: 'Avisaste que no tienes ninguno de estos productos. MATU se encarga del resto.', // [NUEVO] O3
  cambio: 'Este pedido cambió mientras lo veías. Te mostramos cómo quedó.', // [NUEVO] con [L 31]
  yaNoEsta: 'Este pedido ya no está en tu lista.', // [NUEVO]
  /** [L 8] sin «Lo que escribiste sigue aquí.»: no escribió nada. */
  error: GENERAL.errorAlCargar,
  cargando: 'Cargando el pedido…',
}

/** 7: Revisar el código de retiro. */
export const CODIGO_RETIRO = {
  titulo: 'Código de retiro',
  instruccion: 'Pide el código de retiro a quien viene a buscar el pedido y escríbelo aquí.',
  etiqueta: 'Código de retiro (6 números)', // [A45]
  faltan: 'Escribe los 6 números del código.', // [NUEVO]
  boton: 'Revisar código', // [A45]
  revisando: 'Revisando…', // [NUEVO]
  correctoTitulo: (ref: string) => `Código correcto. Entrega el pedido ${ref}.`, // [A45]
  correctoTexto: 'Entrega estos productos:', // [NUEVO]
  noEsTitulo: 'Ese código no es el de este pedido.', // [A45]
  noEsAntes: 'No entregues el pedido todavía. ', // [AJUSTE]
  /** El número va en negrita, como en el PIN: [antes, número, después]. */
  quedan: (n: number): [string, string, string] => (n === 1 ? ['Te queda ', '1 intento', '.'] : ['Te quedan ', `${n} intentos`, '.']),
  bloqueadoTitulo: 'El código se bloqueó por demasiados intentos.', // [AJUSTE]
  bloqueadoTexto: (contacto: string) => `No entregues el pedido. Avisa a MATU: ${contacto}.`, // [AJUSTE]
  vencidoTitulo: 'Este código venció.', // [AJUSTE]
  vencidoTexto: (contacto: string) => `No entregues el pedido todavía. Avisa a MATU para que le den un código nuevo a quien viene a buscarlo: ${contacto}.`, // [AJUSTE]
  usadoTitulo: 'Este pedido ya se retiró.', // [AJUSTE]
  usadoTexto: 'No lo entregues de nuevo.', // [AJUSTE]
  canceladaTitulo: 'Este pedido se canceló. No lo prepares.', // [AJUSTE]
  canceladaTexto: 'No lo entregues. Si ya lo preparaste, vuelve a dejar los productos en su lugar.', // [AJUSTE]
  esperaTitulo: 'Hubo muchos intentos con códigos en poco tiempo.', // [NUEVO]
  esperaTexto: (n: number) => `Espera ${minutos(n)} y vuelve a intentarlo.`, // [NUEVO]
  redTitulo: 'No pudimos revisar el código.', // [NUEVO]
  redTexto: 'Revisa tu conexión y vuelve a intentarlo. No entregues el pedido hasta ver «Código correcto».', // [NUEVO] con [L 8]
  sinCodigo: (contacto: string) => `Todavía no hay un código para este pedido. Avisa a MATU: ${contacto}.`, // [NUEVO]
}

/** 8: Tus productos. */
export const PRODUCTOS = {
  titulo: 'Tus productos',
  bajada: 'Aquí dices cuántos tienes y si los ofreces en MATU. El precio lo cambia MATU.',
  precioDeEjemplo: 'Precio de ejemplo', // [L 11]
  tienes: 'Tienes',
  apartados: 'Apartados',
  disponibles: 'Disponibles',
  sinDisponibles: 'Sin disponibles', // [NUEVO]
  loOfreces: 'Lo ofreces en MATU',
  noSeOfrece: 'No se ofrece', // [NUEVO]
  apartadoSigue: 'Lo apartado sigue apartado.', // [NUEVO]
  cambiar: 'Cambiar cuántos tienes',
  cuantosAhora: '¿Cuántos tienes ahora?',
  ayuda: 'Cuenta todo lo que tienes para vender, también lo apartado que todavía no preparas.',
  guardar: 'Guardar',
  guardando: 'Guardando…', // [L 5.4]
  cancelar: 'Cancelar',
  guardado: (n: number, producto: string) => `Guardado: tienes ${n} de ${producto}.`, // [NUEVO]
  menosQueApartados: 'Tienes menos de los que ya están apartados para pedidos. Al preparar, marca «No lo tengo» en lo que falte.', // [NUEVO]
  errNumero: 'Escribe un número, desde 0.', // [NUEVO]
  errMaximo: 'Escribe un número hasta 9.999.', // [NUEVO]
  otraPersona: 'Otra persona cambió este producto mientras lo editabas. Te mostramos cómo quedó.', // [NUEVO] con [L 6.2]
  error: GENERAL.error, // [L 8]
  noPudimosGuardar: PEDIDO_COMERCIO.noPudimosGuardar,
  cargando: 'Cargando tus productos…', // [NUEVO]
  vacioTitulo: 'Todavía no tienes productos en MATU.', // [NUEVO]
  vacioTexto: (contacto: string) => `Avisa a MATU para agregarlos: ${contacto}.`, // [NUEVO]
  errorAlTraer: 'No pudimos traer tus productos. Revisa tu conexión y vuelve a intentarlo.', // [NUEVO]
  volverAIntentar: GENERAL.volverAIntentar, // [L 26]
  rotuloTitulo: 'Comercio de prueba.', // [A45]
  rotuloTexto: 'Estos productos y precios son de ejemplo.', // [AJUSTE]
}

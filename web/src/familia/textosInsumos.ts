// Textos de «Insumos» (especificación docs/diseno/matu-36-insumos.md, versión 1.0). Marcas:
//   [APROBADO 02-11] / [APROBADO 03-11]  aprobados por Jorge, pendientes de entrar a lenguaje.md
//   [alta]       los del paso de la autorización del alta (MATU-07)
//   [lenguaje X] docs/lenguaje.md, sección X
//   [aprobado por Jorge el 03-11]  de la especificación (sección 7.1), con «guardado» y «errNombreLargo» ajustados
// Nunca se muestra `title`, `detail` ni `mensaje` de la API. Ninguna palabra de lenguaje 3.2.
import type { Calidad } from '../compartido/api/familia'
import type { Unidad } from '../compartido/api/consumo'
import { miles } from './textoLista'

/** Declaraciones del permiso para el consumo, tal cual (especificación 7.2, aprobadas el 03-11). */
export const DECLARACION_CONSUMO: Record<Calidad, string> = {
  titular:
    'Declaro que la persona que cuido me dijo hoy, en persona, que autoriza a MATU a guardar qué insumos usa, cuánto usa y cuánto queda, y a calcular cuándo se acaban y avisarme cuando se esté por acabar, según la política de privacidad vigente. Yo solo registro su decisión.',
  representante_legal:
    'Declaro que soy representante legal de la persona que cuido y que la referencia que indico corresponde al documento que lo acredita. Como su representante, autorizo a MATU a guardar qué insumos usa, cuánto usa y cuánto queda, y a calcular cuándo se acaban y avisarme cuando se esté por acabar, según la política de privacidad vigente.',
  cuidador_de_hecho:
    'Declaro que cuido a esta persona y que no soy su representante legal. Autorizo a MATU a guardar qué insumos usa, cuánto usa y cuánto queda, y a calcular cuándo se acaban y avisarme cuando se esté por acabar, según la política de privacidad vigente. Leí el aviso sobre el límite de esta autorización.',
}

/**
 * «4», «1 sobre», «2 sobres», «15 ml», «5.000 ml», «30 g»: con punto de miles, como `cantidadEnTexto`.
 * Entre la cifra y la unidad va un espacio duro (U+00A0): al cortar la línea no quedan separadas.
 */
export function cantidad(n: number, unidad: Unidad): string {
  if (unidad === 'sobre') return `${miles(n)}\u00A0${n === 1 ? 'sobre' : 'sobres'}`
  if (unidad === 'ml') return `${miles(n)}\u00A0ml`
  if (unidad === 'g') return `${miles(n)}\u00A0g`
  return miles(n)
}

export const INSUMOS = {
  titulo: 'Insumos',
  cargando: 'Cargando los insumos…', // [aprobado por Jorge el 03-11]
  documentoNuevo: 'Anotar un insumo', // [aprobado por Jorge el 03-11] <title>
  documentoCambiar: 'Cambiar un insumo', // [aprobado por Jorge el 03-11] <title>

  // 3.1 Permiso
  permisoTitulo: 'Antes de calcular, un permiso', // [aprobado por Jorge el 03-11]
  /** Primera frase [APROBADO 02-11], el resto [aprobado por Jorge el 03-11]. */
  permisoBajada: (pila: string) =>
    `Para avisarte antes de que se acabe algo, MATU guarda qué insumos usa ${pila}, cuánto usa y cuánto queda. Es un permiso aparte del de su ficha.`,
  permisoLeyenda: 'Doy este permiso porque…', // [alta]
  permisoBoton: 'Acepto y continúo', // [alta]
  permisoEnviando: 'Guardando el permiso…', // [alta]
  permisoGuardado: 'Permiso guardado. Ahora anota el primer insumo.', // [aprobado por Jorge el 03-11]
  errCalidad: 'Elige en qué calidad das el permiso.', // [alta]
  errPermiso: 'No pudimos guardar el permiso. Revisa lo que elegiste y vuelve a intentarlo.', // [aprobado por Jorge el 03-11]

  // 3.1.3 y 3.1.4
  faltaPermisoTitulo: (pila: string) => `Falta el permiso para calcular los insumos de ${pila}.`, // [aprobado por Jorge el 03-11]
  faltaPermiso: (pila: string) =>
    `Sin él no podemos mostrar cuándo se acaban. Pídele a quien administra el grupo o a quien cuida a ${pila} que lo registre.`, // [aprobado por Jorge el 03-11]
  renovarTitulo: (pila: string) => `Hay que renovar la autorización de los insumos de ${pila}.`, // [aprobado por Jorge el 03-11, desde lenguaje 6.4b]
  renovar: 'Se renueva una vez al año. Mientras tanto, no podemos calcular ni mostrar sus insumos, pero lo que anotaste sigue guardado.',
  renovarPide: 'Pídele a quien administra el grupo que la renueve.', // [lenguaje 6.4b]

  // 3.2 Lista
  // MATU-51 (especificación 7, [CAMBIA] lenguaje 13.1): dice dónde se anota.
  notaCorta: 'Es un cálculo con lo que anotaste. Si compraste o te quedan menos, anótalo con «Compré» o «Me quedan».',
  notaCortaLector: 'Es un cálculo con lo que anotó la familia.', // [aprobado por Jorge el 03-11] observador y pagador
  comoTitulo: 'Cómo calculamos', // [aprobado por Jorge el 03-11]
  // MATU-51 (especificación 7, [CAMBIA] lenguaje 16): desde MATU-51 la familia puede anotar la compra.
  comoLector: (pila: string) =>
    `Dividimos lo que quedaba por lo que se usa, y contamos los días desde que la familia lo anotó. Si compraron y no lo anotaron, no lo sabe. Tampoco sabe si cambió lo que usa ${pila}.`, // observador y pagador
  // MATU-51 (especificación 7, [ANALISTA] [CAMBIA] lenguaje 18).
  como: (pila: string) =>
    `Dividimos lo que quedaba por lo que se usa, y contamos los días desde que lo anotaste. Si compraste o cambió lo que queda, anótalo con «Compré» o «Me quedan». No sabe si cambió lo que usa ${pila}.`,
  anotar: 'Anotar un insumo', // [aprobado por Jorge el 03-11]
  cambiar: 'Cambiar',
  cambiarDe: (nombre: string) => `Cambiar ${nombre}`,
  verMas: 'Ver más', // [aprobado por Jorge el 03-11]
  cargandoMas: 'Cargando…',
  /** [APROBADO 02-11] */
  alcanzaDias: 'Alcanza para', // + {n} + «días» / «día»
  seAcabaHoy: 'Se acaba hoy',
  puedeQueNo: 'Puede que ya no quede',
  hastaEl: 'hasta el', // [aprobado por Jorge el 03-11]
  seAcababa: 'Según lo anotado, se acababa el', // [aprobado por Jorge el 03-11]
  usa: (n: number, cada: number, unidad: Unidad) =>
    cada === 1 ? `Usa ${cantidad(n, unidad)} al día.` : `Usa ${cantidad(n, unidad)} cada ${cada} días.`, // [aprobado por Jorge el 03-11]
  quedaban: (n: number, unidad: Unidad) => `Quedaban ${cantidad(n, unidad)} el`, // + fecha [aprobado por Jorge el 03-11]
  quedanHoy: (n: number, unidad: Unidad) => `${n === 1 ? 'Queda' : 'Quedan'} ${cantidad(n, unidad)} hoy.`, // [aprobado por Jorge el 03-11]

  // 3.3 Vacío
  vacioTitulo: (pila: string) => `Aún no sabemos qué usa ${pila}`, // [demo]
  vacio: 'Cuéntanos de un solo producto, el que más te preocupa. Con eso ya te podemos avisar antes de que se acabe.', // [demo]
  vacioLectorTitulo: 'Todavía no hay insumos anotados', // [aprobado por Jorge el 03-11]
  vacioLector: 'Cuando alguien de tu grupo anote uno, aparece aquí.', // [aprobado por Jorge el 03-11]

  // 3.4 Formulario
  cambiarBajada: 'Cambiar lo anotado', // [aprobado por Jorge el 03-11]
  volver: 'Volver a los insumos', // [aprobado por Jorge el 03-11]
  nombre: '¿Qué insumo es?', // [aprobado por Jorge el 03-11]
  nombreAyuda: 'Por ejemplo: «Toallitas húmedas». Sin remedios ni para qué se usa.', // [APROBADO 02-11]
  contador: (n: number) => `${n} de 60`,
  unidadLeyenda: '¿Cómo se cuenta?', // [aprobado por Jorge el 03-11]
  unidades: [
    { valor: 'unidad' as const, texto: 'Por unidad' },
    { valor: 'sobre' as const, texto: 'Por sobre' },
  ],
  unidadFija: (u: Unidad) =>
    ({ unidad: 'Se cuenta por unidad.', sobre: 'Se cuenta por sobre.', ml: 'Se cuenta en ml.', g: 'Se cuenta en gramos.' })[u], // [aprobado por Jorge el 03-11]
  frecuenciaLeyenda: '¿Cada cuánto se usa?', // [aprobado por Jorge el 03-11]
  frecuencias: [
    { valor: 'diario' as const, texto: 'Todos los días' },
    { valor: 'cada' as const, texto: 'Cada algunos días' },
  ],
  cadaCuantos: '¿Cada cuántos días?', // [aprobado por Jorge el 03-11]
  sufijoDias: 'días',
  uso: (pila: string, cada: number | null) => (cada ? `¿Cuántos usa ${pila} cada ${cada} días?` : `¿Cuántos usa ${pila} al día?`), // [aprobado por Jorge el 03-11]
  sufijoUso: (unidad: Unidad, cada: number | null) => {
    const u = unidad === 'sobre' ? 'sobres ' : unidad === 'ml' ? 'ml ' : unidad === 'g' ? 'g ' : ''
    return cada ? `${u}cada ${cada} días` : `${u}al día`
  },
  stock: '¿Cuántos quedan hoy, más o menos?', // [aprobado por Jorge el 03-11]
  stockAyuda: (fecha: string, n: string) => `El ${fecha} anotaste ${n}. Escribe cuántos quedan hoy, o déjalo en blanco si no lo sabes.`, // [aprobado por Jorge el 03-11]
  sufijoStock: (unidad: Unidad) => ({ unidad: 'unidades', sobre: 'sobres', ml: 'ml', g: 'g' })[unidad],
  aviso: '¿Con cuántos días de anticipación te avisamos?', // [aprobado por Jorge el 03-11]
  avisoAyuda: 'Si pones 0, te avisamos el mismo día.', // [aprobado por Jorge el 03-11]
  sufijoAviso: 'días antes',
  menos: (campo: string) => `Uno menos: ${campo}`,
  mas: (campo: string) => `Uno más: ${campo}`,
  previa: (n: number) => (n <= 0 ? 'Así, se acaba hoy.' : n === 1 ? 'Así, alcanza para 1 día, hasta el' : `Así, alcanza para ${n} días, hasta el`), // [aprobado por Jorge el 03-11]
  guardar: 'Guardar',
  guardando: 'Guardando…', // [lenguaje 5.4]
  cancelar: 'Cancelar',
  sinCambios: 'No había cambios.', // [aprobado por Jorge el 03-11]
  /** [aprobado por Jorge el 03-11] Guardamos «{nombre}». Alcanza para… */
  guardado: (nombre: string) => `Guardamos «${nombre}».`,

  // 3.4.3 Validación [aprobado por Jorge el 03-11]
  errNombre: 'Escribe el nombre del insumo.',
  errUso: 'Escribe cuántos usa, al menos 1.',
  errUsoMax: 'Escribe un número hasta 10.000.',
  errCada: 'Escribe un número de 2 a 90.',
  errStock: 'Escribe cuántos quedan. Si no queda nada, escribe 0.',
  errStockMax: 'Escribe un número hasta 100.000.',
  errAviso: 'Escribe un número de 0 a 60.',

  // 3.4.5 Errores de la API [aprobado por Jorge el 03-11]
  errNombreLargo: 'El nombre admite hasta 60 caracteres. Acórtalo un poco.',
  errNombreLinea: 'Escribe el nombre en una sola línea.',
  errCobertura: 'Con esos números alcanzaría para más de 10 años. Revisa cuánto queda y cuánto se usa.',
  errNoAdmitido: 'Ese producto no se puede seguir en MATU.',
  errOtro422: 'No pudimos guardar. Revisa los datos y vuelve a intentarlo.',
  errDuplicado: 'Ese producto ya está anotado. Búscalo en la lista y cámbialo ahí.',
  inactivoTitulo: 'Ya no se está siguiendo este insumo.',
  inactivo: 'Alguien desmarcó «Seguir» mientras lo cambiabas. Para cambiarlo, vuelve a marcar «Seguir» en la lista.',
  faltaVersionTitulo: 'No pudimos guardar este insumo.', // [lenguaje 6.3, adaptado]
  faltaVersion: 'Vuelve a abrirlo y guarda de nuevo. Lo que escribiste sigue aquí.',

  // 3.5 Conflicto [aprobado por Jorge el 03-11, desde lenguaje 6.2]
  conflictoTitulo: (autor: string, nombre: string) => `${autor} cambió «${nombre}» mientras lo cambiabas`,
  otraPersona: 'Otra persona', // [lenguaje 6.2]
  conflicto: 'No guardamos lo tuyo encima de lo suyo. Elige qué dejar.',
  loQueGuardo: 'Lo que guardó',
  loTuyo: 'Lo tuyo, sin guardar',
  cambio: '(cambió)',
  guardarLoMio: 'Guardar lo mío',
  dejarLoSuyo: 'Dejar lo que guardó',
  dejasteLoSuyo: (autor: string | null) => `Dejaste lo que guardó ${autor ?? 'la otra persona'}.`, // [aprobado por Jorge el 03-11]
  avisaAntes: (n: number) => `Te avisamos ${n === 1 ? '1 día' : `${n} días`} antes.`,
  nombreEs: (n: string) => `Se llama «${n}».`,

  // 3.6 Seguir y eliminar [aprobado por Jorge el 03-11]
  seguir: 'Seguir',
  sinSeguir: 'Sin seguir',
  sinSeguirLinea: 'No calculamos ni avisamos mientras no lo sigues.',
  dejasteDeSeguir: (n: string) => `Dejaste de seguir «${n}». Lo anotado sigue guardado.`,
  volvisteASeguir: (n: string) => `Volviste a seguir «${n}». Si cambió cuánto queda, anótalo.`,
  eliminarDe: (n: string) => `Eliminar ${n}`,
  eliminarTitulo: (n: string) => `¿Eliminar «${n}»?`,
  eliminarTexto: 'Se borra todo lo anotado de este insumo y no se puede recuperar.',
  eliminarAlternativa: 'Si solo quieres dejar de calcularlo por un tiempo, desmarca «Seguir».',
  eliminar: 'Eliminar',
  eliminando: 'Eliminando…',
  eliminaste: (n: string) => `Eliminaste «${n}».`,
  errRedSinEscrito: 'No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo.', // [lenguaje 8]
  volverAlInicio: 'Volver al inicio',
}

/** Línea principal según `dias_restantes` (3.2.1). La cifra, con punto de miles («2.000»). */
export function lineaDias(n: number): { texto: string; cifra: string | null; resto: string } {
  if (n < 0) return { texto: INSUMOS.puedeQueNo, cifra: null, resto: '' }
  if (n === 0) return { texto: INSUMOS.seAcabaHoy, cifra: null, resto: '' }
  return { texto: INSUMOS.alcanzaDias, cifra: miles(n), resto: n === 1 ? 'día' : 'días' }
}

/** El mismo texto en una sola cadena, para avisos. */
export const diasEnTexto = (n: number) => {
  const l = lineaDias(n)
  return l.cifra === null ? `${l.texto}.` : `${l.texto} ${l.cifra} ${l.resto}.`
}

/**
 * MATU-37 «Se acaban pronto» (especificación docs/diseno/matu-37-alertas.md, sección 7). Nunca
 * «quiebre», «stock» ni «reponer», y nunca se ofrece comprar ni pedir: «compraste» solo pregunta
 * por lo ya hecho.
 */
export const ALERTAS = {
  titulo: 'Se acaban pronto', // aprobado por Jorge el 03-11
  tituloCuantos: (n: number) => `Se acaban pronto (${n})`, // más de 3, aprobado por Jorge el 03-11
  fechaEstimada: 'Fecha estimada:', // [APROBADO] (decisión de Jorge) + {fecha}
  nota: 'Es una estimación con lo que anotaste.', // aprobado por Jorge el 03-11
  notaLector: 'Es una estimación con lo que anotó la familia.', // pagador y observador, aprobado por Jorge el 07-11 (MATU-51)
  marca: 'Te estamos avisando', // aprobado por Jorge el 03-11
  boton: 'Ya lo resolví', // [APROBADO]
  botonDe: (nombre: string) => `Ya lo resolví: ${nombre}`, // aprobado por Jorge el 03-11
  /** MATU-51 3.8: con envase conocido pregunta en envases, como «Compré» (decisión A2 de Jorge). */
  preguntaEnvases: '¿Compraste? ¿Cuántos envases?',
  ayudaEnvases: 'Si no compraste, déjalo en 0 y solo dejamos de avisarte.',
  pregunta: (unidad: Unidad) =>
    unidad === 'sobre' ? '¿Compraste? ¿Cuántos sobres?' : unidad === 'ml' ? '¿Compraste? ¿Cuántos ml?' : unidad === 'g' ? '¿Compraste? ¿Cuántos gramos?' : '¿Compraste? ¿Cuántos?', // aprobado por Jorge el 03-11
  ayuda: 'Si no compraste, déjalo en blanco y solo dejamos de avisarte.', // aprobado por Jorge el 03-11
  guardando: 'Guardando…', // aprobado por Jorge el 03-11
  volver: 'Volver', // aprobado por Jorge el 03-11
  okCantidad: (c: string, nombre: string, n: number) => `Anotamos tu compra de ${nombre}: ${c}. Ahora alcanza para ${n} ${n === 1 ? 'día' : 'días'}.`, // aprobado por Jorge el 03-11
  okCantidadSinDias: (c: string, nombre: string) => `Anotamos tu compra de ${nombre}: ${c}. Si te quedan menos, cámbialo en la lista.`, // aprobado por Jorge el 03-11
  okSinCantidad: (nombre: string) => `Listo. No te avisaremos de nuevo por ${nombre} hasta que cambie la fecha estimada.`, // aprobado por Jorge el 03-11
  errCerrada: 'Alguien de tu familia ya resolvió este aviso.', // aprobado por Jorge el 03-11
  errConflicto: (autor: string, nombre: string) => `${autor} cambió «${nombre}» mientras lo resolvías. Revisa cómo quedó y vuelve a intentarlo.`, // aprobado por Jorge el 03-11
  errNoEsta: 'Este aviso ya no está. Puede que el insumo se haya cambiado o eliminado.', // aprobado por Jorge el 03-11
  errRol: 'Solo quien administra o cuida puede resolver un aviso.', // aprobado por Jorge el 03-11
  // MATU-51 3.8 ([CAMBIA] lenguaje 17, decisión A2): el tope pasa a 10.000 y con envase va de 0 a 99.
  errCantidad: 'Escribe un número de 1 a 10.000, o déjalo en blanco.',
  errCantidadEnvases: 'Escribe un número de 0 a 99. Si no compraste, déjalo en 0.',
  errRed: 'No pudimos guardar. Revisa tu conexión y vuelve a intentarlo.', // aprobado por Jorge el 03-11
  verComoQuedo: 'Ver cómo quedó', // aprobado por Jorge el 03-11
  errCarga: 'No pudimos ver qué se acaba pronto.', // aprobado por Jorge el 03-11
}

/**
 * MATU-51 «Compré» y «Me quedan» (especificación docs/diseno/matu-51-compre-me-quedan.md v1.2,
 * secciones 8 y 11, que entran a lenguaje.md 23). Nunca «quiebre», «stock», «reponer» ni
 * «reposición», y nunca se ofrece comprar: «Compré» habla de lo ya hecho. Los días y la fecha de la
 * confirmación salen de la respuesta de la API.
 */
export const REGISTRO = {
  compre: 'Compré',
  meQuedan: 'Me quedan',
  compreDe: (nombre: string) => `Compré: ${nombre}`,
  meQuedanDe: (nombre: string) => `Me quedan: ${nombre}`,
  preguntaEnvases: '¿Cuántos envases compraste?',
  pregunta: (unidad: Unidad) =>
    unidad === 'sobre' ? '¿Cuántos sobres compraste?' : unidad === 'ml' ? '¿Cuántos ml compraste?' : unidad === 'g' ? '¿Cuántos gramos compraste?' : '¿Cuántos compraste?',
  ayudaCompre: 'Lo sumamos a lo que calculamos que queda hoy.',
  anotarCompra: 'Anotar la compra',
  preguntaQuedan: '¿Cuántos quedan hoy, más o menos?', // [L 18]
  ayudaQuedan: 'Reemplaza lo que calculábamos. Si no queda nada, escribe 0.',
  anotarQueda: 'Anotar lo que queda',
  guardando: 'Guardando…', // [L 17]
  volver: 'Volver', // [L 17]

  /** «Compra anotada para «{nombre}»: {cantidad}.» y lo que sigue según los días (8). */
  compraAnotada: (nombre: string, cant: string) => `Compra anotada para «${nombre}»: ${cant}.`,
  quedaAnotado: (nombre: string, cant: string) => `Anotamos lo que queda de «${nombre}»: ${cant}.`,
  ahoraAlcanza: (n: number) => `Ahora alcanza para ${n === 1 ? '1 día' : `${n} días`}, hasta el`, // + {fecha}.
  alcanza: (n: number) => `Alcanza para ${n === 1 ? '1 día' : `${n} días`}, hasta el`, // + {fecha}.
  seAcabaHoy: 'Así, se acaba hoy.',
  puedeQueNo: 'Según lo anotado, puede que ya no quede.',
  noQueda: (nombre: string) => `Anotamos que no queda «${nombre}». Cuando compres, anótalo con «Compré».`,

  // Errores del campo (5.4 y 8)
  errVacioEnvases: 'Escribe cuántos envases compraste, al menos 1.',
  errVacio: 'Escribe cuántos compraste, al menos 1.',
  errTopeEnvases: 'Escribe un número de 1 a 99 envases.',
  errTope: 'Escribe un número hasta 10.000.', // [L 18]
  errStockMaximo: (sufijo: string) => `Con esa compra quedarían más de 100.000 ${sufijo}. Revisa cuántos compraste.`,
  errVacioQuedan: 'Escribe cuántos quedan. Si no queda nada, escribe 0.', // [L 18]
  errTopeQuedan: 'Escribe un número hasta 100.000.', // [L 18]
  errCoberturaCompre: 'Con esa compra alcanzaría para más de 10 años. Revisa cuántos compraste.',
  errCoberturaQuedan: 'Con esa cantidad alcanzaría para más de 10 años. Revisa cuántos quedan.',

  // Errores del panel (5.5 y 8)
  errOtro422: 'No pudimos guardar. Revisa los datos y vuelve a intentarlo.', // [L 18]
  errRed: 'No pudimos guardar. Revisa tu conexión y vuelve a intentarlo.', // [L 17]
  errNoEsta: 'Este insumo ya no está. Puede que alguien de tu familia lo haya eliminado.',
  errInactivo: (nombre: string) => `Alguien de tu familia dejó de seguir «${nombre}» mientras lo anotabas. No anotamos nada. Si quieres anotarlo, vuelve a marcar «Seguir».`,
  errConflicto: (autor: string, nombre: string) => `${autor} cambió «${nombre}» mientras lo anotabas. Revisa cómo quedó y vuelve a intentarlo.`,
  errFaltaVersion: 'No pudimos guardar este insumo. Vuelve a abrirlo y guarda de nuevo. Lo que escribiste sigue aquí.', // [L 18]
  verComoQuedo: 'Ver cómo quedó', // [L 17]
}

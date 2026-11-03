// Textos de «Insumos» (especificación docs/diseno/matu-36-insumos.md, versión 1.0). Marcas:
//   [APROBADO 02-11] / [APROBADO 03-11]  aprobados por Jorge, pendientes de entrar a lenguaje.md
//   [alta]       los del paso de la autorización del alta (MATU-07)
//   [lenguaje X] docs/lenguaje.md, sección X
//   [PROPUESTO]  de la especificación, pendiente de lenguaje.md (sección 7.1)
// Nunca se muestra `title`, `detail` ni `mensaje` de la API. Ninguna palabra de lenguaje 3.2.
import type { Calidad } from '../compartido/api/familia'
import type { Unidad } from '../compartido/api/consumo'

/** Declaraciones del permiso para el consumo, tal cual (especificación 7.2, aprobadas el 03-11). */
export const DECLARACION_CONSUMO: Record<Calidad, string> = {
  titular:
    'Declaro que la persona que cuido me dijo hoy, en persona, que autoriza a MATU a guardar qué insumos usa, cuánto usa y cuánto queda, y a calcular cuándo se acaban, según la política de privacidad vigente. Yo solo registro su decisión.',
  representante_legal:
    'Declaro que soy representante legal de la persona que cuido y que la referencia que indico corresponde al documento que lo acredita. Como su representante, autorizo a MATU a guardar qué insumos usa, cuánto usa y cuánto queda, y a calcular cuándo se acaban, según la política de privacidad vigente.',
  cuidador_de_hecho:
    'Declaro que cuido a esta persona y que no soy su representante legal. Autorizo a MATU a guardar qué insumos usa, cuánto usa y cuánto queda, y a calcular cuándo se acaban, según la política de privacidad vigente. Leí el aviso sobre el límite de esta autorización.',
}

/** «4», «1 sobre», «2 sobres», «15 ml», «30 g». */
export function cantidad(n: number, unidad: Unidad): string {
  if (unidad === 'sobre') return `${n} ${n === 1 ? 'sobre' : 'sobres'}`
  if (unidad === 'ml') return `${n} ml`
  if (unidad === 'g') return `${n} g`
  return String(n)
}

export const INSUMOS = {
  titulo: 'Insumos',
  cargando: 'Cargando los insumos…', // [PROPUESTO]
  documentoNuevo: 'Anotar un insumo', // [PROPUESTO] <title>
  documentoCambiar: 'Cambiar un insumo', // [PROPUESTO] <title>

  // 3.1 Permiso
  permisoTitulo: 'Antes de calcular, un permiso', // [PROPUESTO]
  /** Primera frase [APROBADO 02-11], el resto [PROPUESTO]. */
  permisoBajada: (pila: string) =>
    `Para avisarte antes de que se acabe algo, MATU guarda qué insumos usa ${pila}, cuánto usa y cuánto queda. Es un permiso aparte del de su ficha.`,
  permisoLeyenda: 'Doy este permiso porque…', // [alta]
  permisoBoton: 'Acepto y continúo', // [alta]
  permisoEnviando: 'Guardando el permiso…', // [alta]
  permisoGuardado: 'Permiso guardado. Ahora anota el primer insumo.', // [PROPUESTO]
  errCalidad: 'Elige en qué calidad das el permiso.', // [alta]
  errPermiso: 'No pudimos guardar el permiso. Revisa lo que elegiste y vuelve a intentarlo.', // [PROPUESTO]

  // 3.1.3 y 3.1.4
  faltaPermisoTitulo: (pila: string) => `Falta el permiso para calcular los insumos de ${pila}.`, // [PROPUESTO]
  faltaPermiso: (pila: string) =>
    `Sin él no podemos mostrar cuándo se acaban. Pídele a quien administra el grupo o a quien cuida a ${pila} que lo registre.`, // [PROPUESTO]
  renovarTitulo: (pila: string) => `Hay que renovar la autorización de los insumos de ${pila}.`, // [PROPUESTO, desde lenguaje 6.4b]
  renovar: 'Se renueva una vez al año. Mientras tanto, no podemos calcular ni mostrar sus insumos, pero lo que anotaste sigue guardado.',
  renovarPide: 'Pídele a quien administra el grupo que la renueve.', // [lenguaje 6.4b]

  // 3.2 Lista
  notaCorta: 'Es un cálculo con lo que anotaste. Si compraste o te quedan menos, anótalo.', // [APROBADO 02-11]
  notaCortaLector: 'Es un cálculo con lo que anotó la familia.', // [PROPUESTO] observador y pagador
  comoTitulo: 'Cómo calculamos', // [PROPUESTO]
  comoLector: (pila: string) =>
    `Dividimos lo que quedaba por lo que se usa, y contamos los días desde que la familia lo anotó. No sabe si compraron ni si cambió lo que usa ${pila}.`, // [PROPUESTO] observador y pagador
  como: (pila: string) =>
    `Dividimos lo que quedaba por lo que se usa, y contamos los días desde que lo anotaste. No sabe si compraste ni si cambió lo que usa ${pila}.`, // [PROPUESTO]
  anotar: 'Anotar un insumo', // [PROPUESTO]
  cambiar: 'Cambiar',
  cambiarDe: (nombre: string) => `Cambiar ${nombre}`,
  verMas: 'Ver más', // [PROPUESTO]
  cargandoMas: 'Cargando…',
  /** [APROBADO 02-11] */
  alcanzaDias: 'Alcanza para', // + {n} + «días» / «día»
  seAcabaHoy: 'Se acaba hoy',
  puedeQueNo: 'Puede que ya no quede',
  hastaEl: 'hasta el', // [PROPUESTO]
  seAcababa: 'Según lo anotado, se acababa el', // [PROPUESTO]
  usa: (n: number, cada: number, unidad: Unidad) =>
    cada === 1 ? `Usa ${cantidad(n, unidad)} al día.` : `Usa ${cantidad(n, unidad)} cada ${cada} días.`, // [PROPUESTO]
  quedaban: (n: number, unidad: Unidad) => `Quedaban ${cantidad(n, unidad)} el`, // + fecha [PROPUESTO]
  quedanHoy: (n: number, unidad: Unidad) => `Quedan ${cantidad(n, unidad)} hoy.`, // [PROPUESTO]

  // 3.3 Vacío
  vacioTitulo: (pila: string) => `Aún no sabemos qué usa ${pila}`, // [demo]
  vacio: 'Cuéntanos de un solo producto, el que más te preocupa. Con eso ya te podemos avisar antes de que se acabe.', // [demo]
  vacioLectorTitulo: 'Todavía no hay insumos anotados', // [PROPUESTO]
  vacioLector: 'Cuando alguien de tu grupo anote uno, aparece aquí.', // [PROPUESTO]

  // 3.4 Formulario
  cambiarBajada: 'Cambiar lo anotado', // [PROPUESTO]
  volver: 'Volver a los insumos', // [PROPUESTO]
  nombre: '¿Qué insumo es?', // [PROPUESTO]
  nombreAyuda: 'Por ejemplo: «Toallitas húmedas». Sin remedios ni para qué se usa.', // [APROBADO 02-11]
  contador: (n: number) => `${n} de 60`,
  unidadLeyenda: '¿Cómo se cuenta?', // [PROPUESTO]
  unidades: [
    { valor: 'unidad' as const, texto: 'Por unidad' },
    { valor: 'sobre' as const, texto: 'Por sobre' },
  ],
  unidadFija: (u: Unidad) =>
    ({ unidad: 'Se cuenta por unidad.', sobre: 'Se cuenta por sobre.', ml: 'Se cuenta en ml.', g: 'Se cuenta en gramos.' })[u], // [PROPUESTO]
  frecuenciaLeyenda: '¿Cada cuánto se usa?', // [PROPUESTO]
  frecuencias: [
    { valor: 'diario' as const, texto: 'Todos los días' },
    { valor: 'cada' as const, texto: 'Cada algunos días' },
  ],
  cadaCuantos: '¿Cada cuántos días?', // [PROPUESTO]
  sufijoDias: 'días',
  uso: (pila: string, cada: number | null) => (cada ? `¿Cuántos usa ${pila} cada ${cada} días?` : `¿Cuántos usa ${pila} al día?`), // [PROPUESTO]
  sufijoUso: (unidad: Unidad, cada: number | null) => {
    const u = unidad === 'sobre' ? 'sobres ' : unidad === 'ml' ? 'ml ' : unidad === 'g' ? 'g ' : ''
    return cada ? `${u}cada ${cada} días` : `${u}al día`
  },
  stock: '¿Cuántos quedan hoy, más o menos?', // [PROPUESTO]
  stockAyuda: (fecha: string, n: string) => `El ${fecha} anotaste ${n}. Escribe cuántos quedan hoy, o déjalo en blanco si no lo sabes.`, // [PROPUESTO]
  sufijoStock: (unidad: Unidad) => ({ unidad: 'unidades', sobre: 'sobres', ml: 'ml', g: 'g' })[unidad],
  aviso: '¿Con cuántos días de anticipación te avisamos?', // [PROPUESTO]
  avisoAyuda: 'Si pones 0, te avisamos el mismo día.', // [PROPUESTO]
  sufijoAviso: 'días antes',
  menos: (campo: string) => `Uno menos: ${campo}`,
  mas: (campo: string) => `Uno más: ${campo}`,
  previa: (n: number) => (n <= 0 ? 'Así, se acaba hoy.' : n === 1 ? 'Así, alcanza para 1 día, hasta el' : `Así, alcanza para ${n} días, hasta el`), // [PROPUESTO]
  guardar: 'Guardar',
  guardando: 'Guardando…', // [lenguaje 5.4]
  cancelar: 'Cancelar',
  sinCambios: 'No había cambios.', // [PROPUESTO]
  /** [PROPUESTO] «{nombre}» guardado. Alcanza para… */
  guardado: (nombre: string) => `«${nombre}» guardado.`,

  // 3.4.3 Validación [PROPUESTO]
  errNombre: 'Escribe el nombre del insumo.',
  errUso: 'Escribe cuántos usa, al menos 1.',
  errUsoMax: 'Escribe un número hasta 10.000.',
  errCada: 'Escribe un número de 2 a 90.',
  errStock: 'Escribe cuántos quedan. Si no queda nada, escribe 0.',
  errStockMax: 'Escribe un número hasta 100.000.',
  errAviso: 'Escribe un número de 0 a 60.',

  // 3.4.5 Errores de la API [PROPUESTO]
  errNombreLargo: 'El nombre admite hasta 60 letras. Acórtalo un poco.',
  errNombreLinea: 'Escribe el nombre en una sola línea.',
  errCobertura: 'Con esos números alcanzaría para más de 10 años. Revisa cuánto queda y cuánto se usa.',
  errNoAdmitido: 'Ese producto no se puede seguir en MATU.',
  errOtro422: 'No pudimos guardar. Revisa los datos y vuelve a intentarlo.',
  errDuplicado: 'Ese producto ya está anotado. Búscalo en la lista y cámbialo ahí.',
  inactivoTitulo: 'Ya no se está siguiendo este insumo.',
  inactivo: 'Alguien desmarcó «Seguir» mientras lo cambiabas. Para cambiarlo, vuelve a marcar «Seguir» en la lista.',
  faltaVersionTitulo: 'No pudimos guardar este insumo.', // [lenguaje 6.3, adaptado]
  faltaVersion: 'Vuelve a abrirlo y guarda de nuevo. Lo que escribiste sigue aquí.',

  // 3.5 Conflicto [PROPUESTO, desde lenguaje 6.2]
  conflictoTitulo: (autor: string, nombre: string) => `${autor} cambió «${nombre}» mientras lo cambiabas`,
  otraPersona: 'Otra persona', // [lenguaje 6.2]
  conflicto: 'No guardamos lo tuyo encima de lo suyo. Elige qué dejar.',
  loQueGuardo: 'Lo que guardó',
  loTuyo: 'Lo tuyo, sin guardar',
  cambio: '(cambió)',
  guardarLoMio: 'Guardar lo mío',
  dejarLoSuyo: 'Dejar lo que guardó',
  dejasteLoSuyo: (autor: string | null) => `Dejaste lo que guardó ${autor ?? 'la otra persona'}.`, // [PROPUESTO]
  avisaAntes: (n: number) => `Te avisamos ${n === 1 ? '1 día' : `${n} días`} antes.`,
  nombreEs: (n: string) => `Se llama «${n}».`,

  // 3.6 Seguir y eliminar [PROPUESTO]
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

/** Línea principal según `dias_restantes` (3.2.1). */
export function lineaDias(n: number): { texto: string; cifra: number | null; resto: string } {
  if (n < 0) return { texto: INSUMOS.puedeQueNo, cifra: null, resto: '' }
  if (n === 0) return { texto: INSUMOS.seAcabaHoy, cifra: null, resto: '' }
  return { texto: INSUMOS.alcanzaDias, cifra: n, resto: n === 1 ? 'día' : 'días' }
}

/** El mismo texto en una sola cadena, para avisos. */
export const diasEnTexto = (n: number) => {
  const l = lineaDias(n)
  return l.cifra === null ? `${l.texto}.` : `${l.texto} ${l.cifra} ${l.resto}.`
}

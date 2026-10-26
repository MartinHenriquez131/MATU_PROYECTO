// Datos sintéticos de la demo. Ninguna persona real: Carmen cuida a María, Rosa la
// reemplaza y Rodrigo es su hijo. Los textos vienen del prototipo v1.1 y de la política
// de privacidad v0.9.
import type { Apoyo, Calidad, CampoId, Insumo } from './tipos'

export const CAMPOS: CampoId[] = ['su_dia', 'si_se_altera', 'a_quien_llamar']

export const TEXTO_CAMPO: Record<
  CampoId,
  { titulo: string; pregunta: string; ejemplo: string; dictado: string }
> = {
  su_dia: {
    titulo: 'Su día',
    pregunta: '¿Cómo es un día normal para ella? Puedes contar un día bueno o uno difícil.',
    ejemplo: 'Por ejemplo: «08:00 Despierta. Le gusta que abran la cortina primero». Si empiezas con la hora, lo mostramos como línea de tiempo.',
    dictado:
      '08:00 Despierta sola. Le gusta que abran la cortina primero.\n08:30 Desayuno. Té con leche tibio, nunca caliente.\n13:00 Almuerzo. Come mejor si alguien la acompaña.\n16:00 Siesta corta, máximo una hora.\n20:00 Once liviana y su programa de radio.',
  },
  si_se_altera: {
    titulo: 'Si se altera',
    pregunta: '¿Qué la calma cuando se angustia o se desorienta?',
    ejemplo: 'Por ejemplo: «Le hace bien que le tomen la mano y le hablen de su pueblo».',
    dictado:
      'Bajar las persianas y poner la radio bajito. No hablarle fuerte. Si pregunta por su marido, no corregirla: decirle que salió y ya vuelve.',
  },
  a_quien_llamar: {
    titulo: 'A quién llamar',
    pregunta: '¿A quién llamar si algo pasa y no te ubican?',
    ejemplo: 'Por ejemplo: «Rodrigo, su hijo: +56 9 5555 0102».',
    dictado:
      'Carmen, yo: +56 9 8765 4321\nRodrigo, su hijo: +56 9 5555 0102\nJuana, vecina del 302: tiene llave',
  },
}

export const MAX_CARACTERES = 500

export const TEXTO_RODRIGO =
  'Bajar las persianas. Si sigue inquieta, llamar a la nieta para que le hable un rato.'

export const APOYOS: { valor: Apoyo; texto: string }[] = [
  { valor: 'autovalente_con_supervision', texto: 'Se maneja sola, con supervisión' },
  { valor: 'apoyo_parcial', texto: 'Necesita apoyo en varias cosas' },
  { valor: 'apoyo_total', texto: 'Necesita apoyo en todo' },
]

export const CALIDADES: { valor: Calidad; texto: string; detalle: string; declaracion: string }[] = [
  {
    valor: 'titular',
    texto: 'Ella lo autoriza y yo lo registro',
    detalle: 'María decide por sí misma y tú anotas su decisión.',
    declaracion:
      'Declaro que la persona que cuido me dijo hoy, en persona, que autoriza a MATU a guardar su ficha de relevo y a compartirla con el relevo que elija el grupo, según la política de privacidad vigente. Yo solo registro su decisión.',
  },
  {
    valor: 'representante_legal',
    texto: 'Soy su representante legal',
    detalle: 'Tienes un nombramiento legal para representarla.',
    declaracion:
      'Declaro que soy representante legal de la persona que cuido y que la referencia que indico corresponde al documento que lo acredita. Como su representante, autorizo a MATU a guardar su ficha de relevo y a compartirla con el relevo que elija el grupo, según la política de privacidad vigente.',
  },
  {
    valor: 'cuidador_de_hecho',
    texto: 'La cuido, sin representación legal',
    detalle: 'La cuidas en el día a día, sin un nombramiento legal.',
    declaracion:
      'Declaro que cuido a esta persona y que no soy su representante legal. Autorizo a MATU a guardar su ficha de relevo y a compartirla con el relevo que elija el grupo, según la política de privacidad vigente. Leí el aviso sobre el límite de esta autorización.',
  },
]

/** Texto exacto del aviso `aviso_cuidador_de_hecho`, versión 1.0 (política v0.9, sección 5). */
export const AVISO_CUIDADOR = {
  id: 'aviso_cuidador_de_hecho',
  version: '1.0',
  titulo: 'Aviso: tu autorización tiene un límite',
  parrafos: [
    'Declaraste que cuidas a esta persona y que no eres su representante legal. Con esa declaración puedes organizar su cuidado en MATU, pero tu autorización no equivale a la de la propia persona ni a la de su representante legal. MATU no puede comprobar lo que declaras. Por eso deja registrado que la autorización la diste tú, como cuidadora o cuidador de hecho, con la fecha y la versión de la política.',
    'Te pedimos tres cosas: anota solo lo necesario para su cuidado, cuéntale qué guardas en MATU si puede comprenderlo, y respeta lo que ella decida. Ella o su representante legal pueden pedir en cualquier momento que se borren sus datos.',
    'En 12 meses te pediremos confirmar que sigues a cargo de su cuidado.',
  ],
}

export const COMERCIO = {
  nombre: 'Farmacia Los Aromos',
  /** La primera vez en cada pantalla: no pudimos confirmar que no exista un comercio con ese nombre. */
  nombreFicticio: 'Farmacia Los Aromos (comercio ficticio)',
  ventana: 'entre 17:00 y 18:00',
}

/** El otro local en convenio, donde se retira el mismo producto si falta (fase 2 del ADR-027, simulado). */
export const OTRO_COMERCIO = {
  nombre: 'Farmacia Piedra Azul',
  nombreFicticio: 'Farmacia Piedra Azul (comercio ficticio)',
}

/** Envío, uno por pedido. De ejemplo, cubierto por el rótulo de precios de ejemplo. */
export const ENVIO = 2_990

/**
 * Insumos con su consumo declarado y su precio en Farmacia Los Aromos. Con los sugeridos, la lista
 * suma $60.000 en productos, $62.990 con el envío (especificación del ADR-027, sección 1).
 */
export function insumosIniciales(): Insumo[] {
  return [
    {
      id: 'panal-m',
      corto: 'los pañales',
      nombre: 'Pañal adulto talla M',
      presentacion: 'x30',
      unidad: 'pañales',
      preguntaDia: '¿Cuántos usa al día?',
      porDia: 4,
      quedan: 24,
      tamanoPaquete: 30,
      precio: 13_990,
      declarado: true,
    },
    {
      id: 'toallitas',
      corto: 'las toallitas',
      nombre: 'Toallitas húmedas',
      presentacion: 'x80',
      unidad: 'toallitas',
      preguntaDia: '¿Cuántas usa al día?',
      porDia: 7,
      quedan: 77,
      tamanoPaquete: 80,
      precio: 4_990,
      declarado: true,
    },
    {
      id: 'suplemento',
      corto: 'el suplemento',
      nombre: 'Suplemento vainilla',
      presentacion: 'x12',
      unidad: 'botellitas',
      preguntaDia: '¿Cuántas toma al día?',
      porDia: 1,
      quedan: 15,
      tamanoPaquete: 12,
      precio: 27_030,
      declarado: true,
    },
    {
      id: 'crema',
      corto: 'la crema',
      nombre: 'Crema protectora',
      presentacion: '200 g',
      unidad: 'usos',
      preguntaDia: '¿Cuántas veces al día se la aplican?',
      porDia: 2,
      quedan: 80,
      tamanoPaquete: 80,
      precio: 6_490,
      declarado: true,
    },
    {
      id: 'guantes',
      corto: 'los guantes',
      nombre: 'Guantes desechables',
      presentacion: 'x100',
      unidad: 'guantes',
      preguntaDia: '¿Cuántos usan al día?',
      porDia: 6,
      quedan: 50,
      tamanoPaquete: 100,
      precio: 5_990,
      declarado: false,
    },
    {
      id: 'sabanillas',
      corto: 'las sabanillas',
      nombre: 'Sabanillas desechables',
      presentacion: 'x10',
      unidad: 'sabanillas',
      preguntaDia: '¿Cuántas usan al día?',
      porDia: 1,
      quedan: 10,
      tamanoPaquete: 10,
      precio: 7_490,
      declarado: false,
    },
  ]
}

/** Al confirmar el stock: lo que ningún comercio en convenio tiene hoy. */
export const SIN_STOCK_HOY = new Set(['toallitas'])
/** Al confirmar el stock: precios unitarios que cambiaron desde la lista. */
export const PRECIO_CONFIRMADO: Record<string, number> = { suplemento: 26_490 }
/** Después de pagar: precio del mismo producto en el otro local. La diferencia la pone MATU. */
export const PRECIO_OTRO_COMERCIO: Record<string, number> = { suplemento: 27_590 }
/** Lo que el comercio ve apartado antes del pago: una referencia opaca, sin número de pedido. */
export const REF_APARTADO = 'K41M'

export const PEDIDO_NUMERO = 4821
export const CODIGO_RETIRO = '4729'
export const PIN_DEMO = '4821'

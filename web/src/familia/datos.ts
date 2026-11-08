// Datos fijos de la app de la familia, copiados de la demo aprobada (Demo/src/demo/datos.ts), que
// los tomó del prototipo v1.1 y de la política de privacidad, sección 5. Las claves del contrato
// (`rutina`, `manejo_situaciones`, `red_apoyo`) se nombran en la URL con la etiqueta visible.
import type { Calidad, CampoApi } from '../compartido/api/familia'
import { TITULO_SECCION, type SeccionApi } from '../compartido/secciones'
import type { Ruta } from './ruteo'

export const MAX_CARACTERES = 500
export const AVISO_CONTADOR = 450

export interface Campo {
  api: CampoApi
  ruta: Ruta
  titulo: string
  pregunta: (pila: string) => string
  ejemplo: string
}

/** Lenguaje 5.1 a 5.3. */
export const CAMPOS: readonly Campo[] = [
  {
    api: 'rutina',
    ruta: '/ficha/su-dia',
    titulo: 'Su día',
    pregunta: (pila) => `¿Cómo es un día normal para ${pila}? Puedes contar un día bueno o uno difícil.`,
    ejemplo: 'Por ejemplo: «08:00 Despierta. Le gusta que abran la cortina primero». Si empiezas con la hora, lo mostramos como línea de tiempo.',
  },
  {
    api: 'manejo_situaciones',
    ruta: '/ficha/si-se-altera',
    titulo: 'Si se altera',
    pregunta: (pila) => `¿Qué calma a ${pila} cuando se angustia?`,
    ejemplo: 'Por ejemplo: «Le hace bien que le tomen la mano y le hablen de su pueblo».',
  },
  {
    api: 'red_apoyo',
    ruta: '/ficha/a-quien-llamar',
    titulo: 'A quién llamar',
    pregunta: () => '¿A quién llamar si algo pasa y no te ubican?',
    ejemplo: 'Por ejemplo: «Rodrigo, su hijo: +56 9 5555 0102».',
  },
]

export const campoDeRuta = (r: string) => CAMPOS.find((c) => c.ruta === r) ?? null

/** Una sección complementaria en la app de la familia (especificación MATU-49, sección 2). */
export interface Seccion {
  api: SeccionApi
  ruta: Ruta
  titulo: string
  /** La `label` del editor. Nunca se muestra al relevo (D5). */
  pregunta: string
  /** El texto entre «», sin «Por ejemplo: ». Nunca se muestra al relevo (D5). */
  ejemplo: string
  /** Lleva la ayuda de alergias (Comer y beber, Sus remedios). */
  alergias: boolean
}

/** Lenguaje 14.1, en el orden fijo de ADR-028. Rutas: especificación 2 [PROPUESTO]. */
export const SECCIONES: readonly Seccion[] = [
  {
    api: 'quien_es',
    ruta: '/ficha/quien-es',
    titulo: TITULO_SECCION.quien_es,
    pregunta: '¿Qué le gustaría que supiera de esta persona alguien que recién la conoce?',
    ejemplo: 'Le dicen Tito. Fue profesor de música en Talca. Su nieta Sofía le visita los domingos y tiene un gato, el Pelusa.',
    alergias: false,
  },
  {
    api: 'preferencias',
    ruta: '/ficha/lo-que-le-hace-bien',
    titulo: TITULO_SECCION.preferencias,
    pregunta: '¿Qué le alegra, le entretiene o le calma?',
    ejemplo: 'Le gustan los boleros y conversar de fútbol. Ve las noticias a las 9 de la noche.',
    alergias: false,
  },
  {
    api: 'alimentacion',
    ruta: '/ficha/comer-y-beber',
    titulo: TITULO_SECCION.alimentacion,
    pregunta: '¿Qué le gusta comer y cómo se le sirve?',
    ejemplo: 'Toma té con poca azúcar. Prefiere la comida picada en trozos chicos y el pan blando.',
    alergias: true,
  },
  {
    api: 'movilidad',
    ruta: '/ficha/moverse-y-descansar',
    titulo: TITULO_SECCION.movilidad,
    pregunta: '¿Cómo se le ayuda a moverse, levantarse y descansar?',
    ejemplo: 'Camina con bastón dentro de la casa. Para levantarse, ofrécele el brazo derecho. Duerme siesta después de almuerzo.',
    alergias: false,
  },
  {
    api: 'comunicacion',
    ruta: '/ficha/como-hablarle',
    titulo: TITULO_SECCION.comunicacion,
    pregunta: '¿Qué ayuda a que se entiendan?',
    ejemplo: 'Usa audífono en el oído izquierdo. Háblale de frente y despacio. Si algo le molesta, se toca la frente.',
    alergias: false,
  },
  {
    api: 'remedios',
    ruta: '/ficha/sus-remedios',
    titulo: TITULO_SECCION.remedios,
    pregunta: '¿Qué remedios toma y a qué hora, tal como se los da la familia?',
    ejemplo: '8:00 con el desayuno: 1 pastilla blanca de la caja azul. 20:00: 1 pastilla de la caja verde.',
    alergias: true,
  },
]

export const seccionDeRuta = (r: string) => SECCIONES.find((s) => s.ruta === r) ?? null

export type Apoyo = 'autovalente_con_supervision' | 'apoyo_parcial' | 'apoyo_total'

export const APOYOS: { valor: Apoyo; texto: string }[] = [
  { valor: 'autovalente_con_supervision', texto: 'Se maneja con autonomía, con supervisión' },
  { valor: 'apoyo_parcial', texto: 'Necesita apoyo en varias cosas' },
  { valor: 'apoyo_total', texto: 'Necesita apoyo en todo' },
]

/**
 * Las tres calidades y sus declaraciones (política v0.10, sección 5). Donde la demo dice «Ella» o
 * «María», va el nombre de pila. El género de «decide por sí misma» y «representarla» quedó
 * resuelto el 03-11 con redacción neutra (lenguaje 5).
 */
export const CALIDADES: { valor: Calidad; texto: (pila: string) => string; detalle: (pila: string) => string; declaracion: string }[] = [
  {
    valor: 'titular',
    texto: (pila) => `${pila} lo autoriza y yo lo registro`,
    detalle: (pila) => `${pila} decide por su cuenta y tú registras su decisión.`, // [aprobado por Jorge el 08-11]
    declaracion:
      'Declaro que la persona que cuido me dijo hoy, en persona, que autoriza a MATU a guardar su ficha de relevo, incluidas las secciones adicionales y sus remedios si se agregan, y a compartirla con el relevo que elija el grupo, según la política de privacidad vigente. Yo solo registro su decisión.',
  },
  {
    valor: 'representante_legal',
    texto: () => 'Soy su representante legal',
    detalle: () => 'Tienes un nombramiento legal para representar a esta persona.',
    declaracion:
      'Declaro que soy representante legal de la persona que cuido y que la referencia que indico corresponde al documento que lo acredita. Como su representante, autorizo a MATU a guardar su ficha de relevo, incluidas las secciones adicionales y sus remedios si se agregan, y a compartirla con el relevo que elija el grupo, según la política de privacidad vigente.',
  },
  {
    valor: 'cuidador_de_hecho',
    texto: () => 'Cuido a esta persona, pero no soy su representante legal', // decisión de Jorge
    detalle: () => 'Cuidas a esta persona en el día a día, sin un nombramiento legal.',
    declaracion:
      'Declaro que cuido a esta persona y que no soy su representante legal. Autorizo a MATU a guardar su ficha de relevo, incluidas las secciones adicionales y sus remedios si se agregan, y a compartirla con el relevo que elija el grupo, según la política de privacidad vigente. Leí el aviso sobre el límite de esta autorización.',
  },
]

/** Texto exacto del aviso `aviso_cuidador_de_hecho`, versión 1.1 (política, sección 5). */
export const AVISO_CUIDADOR = {
  id: 'aviso_cuidador_de_hecho',
  version: '1.1',
  titulo: 'Aviso: tu autorización tiene un límite',
  parrafos: [
    'Declaraste que cuidas a esta persona y que no eres su representante legal. Con esa declaración puedes organizar su cuidado en MATU, pero tu autorización no equivale a la de la propia persona ni a la de su representante legal. MATU no puede comprobar lo que declaras. Por eso deja registrado que la autorización la diste tú, como cuidadora o cuidador de hecho, con la fecha y la versión de la política.',
    'Te pedimos tres cosas: anota solo lo necesario para su cuidado, cuéntale qué guardas en MATU si puede comprenderlo, y respeta lo que esa persona decida. La persona o su representante legal pueden pedir en cualquier momento que se borren sus datos.',
    'En 12 meses te pediremos confirmar que sigues a cargo de su cuidado.',
  ],
} as const

/** El mismo patrón del backend (`backend/app/shared/celular.py`): 9 y ocho dígitos, con o sin +56. */
export const PATRON_CELULAR = /^(\+?56 ?)?9( ?[0-9]){8}$/

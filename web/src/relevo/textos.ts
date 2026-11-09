// Todos los textos que ve quien abre el enlace. Salen de docs/lenguaje.md (secciones 5, 7, 8 y 11)
// y de docs/diseno/matu-23-pagina-relevo.md. Desde MATU-68 cada texto lleva la sección de
// lenguaje.md de donde sale: no se cambian por otros.
// Nunca: "relevo", "token", "sesión", "canje", "revocado", "inválido", ni un código de error.
import type { CampoFicha } from '../compartido/api/relevo'
import { RUTA_PRIVACIDAD } from '../compartido/textosPolitica'

export const TITULO_DOCUMENTO = 'Ficha de cuidado compartida · MATU' // [lenguaje 7.1] 2.5
export const tituloDocumentoDeEstado = (titulo: string) => `${titulo.replace(/\.$/, '')} · MATU` // [lenguaje 7.1] 2.5

export const CABECERA = { marca: 'MATU', pagina: 'Ficha de cuidado compartida' } // lenguaje 7.1

export const CARGANDO = {
  enlace: 'Abriendo el enlace…', // [lenguaje 7.1]
  ficha: 'Abriendo la ficha…', // [lenguaje 7.1]
}

// lenguaje 7.1
export const PIN = {
  titulo: (comparte: string, pila: string) => `${comparte} te compartió la ficha de ${pila}`,
  bajada: 'Escribe el PIN de cuatro números que te dictaron por teléfono.',
  etiqueta: 'PIN',
  boton: 'Ver la ficha',
  botonOcupado: 'Abriendo la ficha…', // [lenguaje 7.1]
  pie: 'No necesitas cuenta ni instalar nada. Al entrar, el enlace se borra de la barra de direcciones.',
  // lenguaje 7.3 y 8
  incompleto: 'El PIN tiene 4 números. Revisa que estén todos.',
  incorrectoInicio: 'Ese PIN no es.',
  incorrectoRevisa: 'Revisa los cuatro números que te dictaron.',
  /** Con espacio duro (`\u00A0`): «3» e «intentos» no se separan al cortar la línea. */
  intentos: (n: number) => (n === 1 ? '1\u00A0intento' : `${n}\u00A0intentos`),
  teQuedan: (n: number) => (n === 1 ? 'Te queda' : 'Te quedan'),
  incorrectoFin: 'Después, el enlace se bloquea.',
}

// lenguaje 8, "Cualquier otro". Sin "Lo que escribiste sigue aquí" donde Rosa no escribió nada.
export const ERROR = {
  titulo: 'No pudimos completar esto.', // [lenguaje 8]
  conexion: 'Revisa tu conexión y vuelve a intentarlo.', // [lenguaje 8]
  escrito: 'Lo que escribiste sigue aquí.',
  reintentar: 'Volver a intentar', // [lenguaje 26]
}

// lenguaje 7.5, con el correo de contacto desde la política 0.11 (D7, MATU-75). Se corta en tres
// párrafos solo para presentarlo, sin cambiar una palabra.
export const AVISO = {
  titulo: 'Tus datos en MATU', // [lenguaje 7.5]
  parrafos: [
    'MATU guarda tu nombre y tu teléfono, que anotó quien te compartió la ficha, para enviarte el enlace y poder contactarte. Tu teléfono se borra 30 días después de que el enlace vence o se corta.',
    'También registra cada vez que abres el enlace o la ficha y cada PIN incorrecto, con la fecha y la hora. La familia que te compartió la ficha puede ver ese registro con tu nombre. Lo guardamos 3 años.',
    'Responsables de tus datos: Jorge Espinoza y Martín Henríquez. Puedes pedir ver, corregir o borrar tus datos escribiendo a cuidaconmatu@gmail.com.',
  ],
  politica: 'Política de privacidad (se abre en otra pestaña)', // [lenguaje 7.5]
}

/**
 * MATU-75: la política de privacidad, pública, en otra pestaña. Sin fragmento: el `#<token>` del
 * relevo nunca viaja a /privacidad, y esa página no lee el fragmento.
 */
export const RUTA_POLITICA = RUTA_PRIVACIDAD

// lenguaje 7.2
export const QUE_HAGO = {
  titulo: '¿Qué hago?',
  pedirOtro: 'Pídele a quien te envió el enlace uno nuevo.',
  revisar: 'Pídele a quien te envió el enlace que lo revise.', // lenguaje 7.3 (D3, decisión de Martín 28/10)
}

// lenguaje 7.4
export const FICHA = {
  encabezado: 'Ficha de cuidado de',
  vigenciaInicio: 'Puedes verla hasta el',
  vigenciaMedio: 'a las',
  actualizar: 'Actualizar',
  actualizando: 'Actualizando…', // [lenguaje 7.4]
  actualizada: (hora: string) => `Ficha actualizada a las ${hora}.`, // [lenguaje 7.4]
  soloPuede: (comparte: string) => `Solo ${comparte} puede cambiar esta ficha.`,
  sinCompletar: 'Sin completar', // lenguaje 5.4
  columna: 'Sobre esta ficha', // [lenguaje 7.4] aria-label
}

/** Orden fijo de los campos en la hoja (lenguaje 5). */
export const ORDEN_CAMPOS: CampoFicha[] = ['rutina', 'manejo_situaciones', 'red_apoyo']

/**
 * D2 · Lo que acompaña a cada campo en la hoja del relevo. Decisión de Martín del 28/10: pregunta
 * guía y ejemplo (lenguaje 5.1 a 5.3), con la mitigación de la especificación 3.11.3.
 *
 * Cambiada por Jorge el 09/11: el relevo ve solo la pregunta guía. En «A quién llamar» el ejemplo
 * «+56 9 5555 0102» quedaba justo debajo del teléfono real, y en una crisis se podía llamar al
 * número de ejemplo. El ejemplo es para quien escribe la ficha (el editor de la familia lo sigue
 * mostrando), no para quien la lee.
 */
export const MOSTRAR_EJEMPLO: boolean = false

export const CAMPOS: Record<CampoFicha, { etiqueta: string; pregunta: (pila: string) => string; ejemplo: string }> = {
  rutina: {
    etiqueta: 'Su día',
    pregunta: (pila) => `¿Cómo es un día normal para ${pila}? Puedes contar un día bueno o uno difícil.`,
    ejemplo: 'Por ejemplo: «08:00 Despierta. Le gusta que abran la cortina primero». Si empiezas con la hora, lo mostramos como línea de tiempo.',
  },
  manejo_situaciones: {
    etiqueta: 'Si se altera',
    pregunta: (pila) => `¿Qué calma a ${pila} cuando se angustia?`,
    ejemplo: 'Por ejemplo: «Le hace bien que le tomen la mano y le hablen de su pueblo».',
  },
  red_apoyo: {
    etiqueta: 'A quién llamar',
    pregunta: () => '¿A quién llamar si algo pasa y no te ubican?',
    ejemplo: 'Por ejemplo: «Rodrigo, su hijo: +56 9 5555 0102».',
  },
}

/** Entre el número y «minuto(s)» va un espacio duro (`\u00A0`): al cortar la línea no se separan. */
export const ESPERA = {
  minutos: (m: number | null) =>
    m === null
      ? 'Vuelve a intentarlo en unos minutos.' // [lenguaje 7.3]
      : m === 1
        ? 'Vuelve a intentarlo en 1\u00A0minuto.' // [lenguaje 7.3]
        : `Vuelve a intentarlo en ${m}\u00A0minutos.`,
}

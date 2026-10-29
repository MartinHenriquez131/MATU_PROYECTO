// Todos los textos que ve quien abre el enlace. Salen de docs/lenguaje.md (secciones 5, 7, 8 y 11)
// y de docs/diseno/matu-23-pagina-relevo.md. Los marcados [PROPUESTO] esperan la aprobación de
// Jorge para entrar a lenguaje.md (especificación, sección 7): no se cambian por otros.
// Nunca: "relevo", "token", "sesión", "canje", "revocado", "inválido", ni un código de error.
import type { CampoFicha } from '../compartido/api/relevo'

export const TITULO_DOCUMENTO = 'Ficha de cuidado compartida · MATU' // [PROPUESTO] 2.5
export const tituloDocumentoDeEstado = (titulo: string) => `${titulo.replace(/\.$/, '')} · MATU` // [PROPUESTO] 2.5

export const CABECERA = { marca: 'MATU', pagina: 'Ficha de cuidado compartida' } // lenguaje 7.1

export const CARGANDO = {
  enlace: 'Abriendo el enlace…', // [PROPUESTO]
  ficha: 'Abriendo la ficha…', // [PROPUESTO]
}

// lenguaje 7.1
export const PIN = {
  titulo: (comparte: string, pila: string) => `${comparte} te compartió la ficha de ${pila}`,
  bajada: 'Escribe el PIN de cuatro números que te dictaron por teléfono.',
  etiqueta: 'PIN',
  boton: 'Ver la ficha',
  botonOcupado: 'Abriendo la ficha…', // [PROPUESTO]
  pie: 'No necesitas cuenta ni instalar nada. Al entrar, el enlace se borra de la barra de direcciones.',
  // lenguaje 7.3 y 8
  incompleto: 'El PIN tiene 4 números. Revisa que estén todos.',
  incorrectoInicio: 'Ese PIN no es.',
  incorrectoRevisa: 'Revisa los cuatro números que te dictaron.',
  intentos: (n: number) => (n === 1 ? '1 intento' : `${n} intentos`),
  teQuedan: (n: number) => (n === 1 ? 'Te queda' : 'Te quedan'),
  incorrectoFin: 'Después, el enlace se bloquea.',
}

// lenguaje 8, "Cualquier otro". Sin "Lo que escribiste sigue aquí" donde Rosa no escribió nada.
export const ERROR = {
  titulo: 'No pudimos completar esto.', // [PROPUESTO como título]
  conexion: 'Revisa tu conexión y vuelve a intentarlo.', // [PROPUESTO sin la última frase]
  escrito: 'Lo que escribiste sigue aquí.',
  reintentar: 'Volver a intentar', // [PROPUESTO]
}

// lenguaje 7.5, variante sin correo (D4). Se corta en tres párrafos solo para presentarlo.
export const AVISO = {
  titulo: 'Tus datos en MATU', // [PROPUESTO]
  parrafos: [
    'MATU guarda tu nombre y tu teléfono, que anotó quien te compartió la ficha, para enviarte el enlace y poder contactarte. Tu teléfono se borra 30 días después de que el enlace vence o se corta.',
    'También registra cada vez que abres el enlace o la ficha y cada PIN incorrecto, y guarda ese registro 3 años, para saber a quién se compartió.',
    'Responsables de tus datos: Jorge Espinoza y Martín Henríquez. Puedes pedir ver, corregir o borrar tus datos.',
  ],
  politica: 'Política de privacidad (se abre en otra pestaña)', // [PROPUESTO]
}

/**
 * D5: la política de privacidad todavía no tiene ruta en web/. Mientras sea `null`, el enlace no
 * se muestra (nunca un href="#"). Cuando el orquestador fije la ruta, se escribe aquí.
 */
export const RUTA_POLITICA: string | null = null

// lenguaje 7.2
export const QUE_HAGO = {
  titulo: '¿Qué hago?',
  pedirOtro: 'Pídele a quien te envió el enlace uno nuevo.',
  revisar: 'Pídele a quien te envió el enlace que lo revise.', // [PROPUESTO] D3, decisión de Martín 28/10
}

// lenguaje 7.4
export const FICHA = {
  encabezado: 'Ficha de cuidado de',
  vigenciaInicio: 'Puedes verla hasta el',
  vigenciaMedio: 'a las',
  actualizar: 'Actualizar',
  actualizando: 'Actualizando…', // [PROPUESTO]
  actualizada: (hora: string) => `Ficha actualizada a las ${hora}.`, // [PROPUESTO]
  soloPuede: (comparte: string) => `Solo ${comparte} puede cambiar esta ficha.`,
  sinCompletar: 'Sin completar', // lenguaje 5.4
  columna: 'Sobre esta ficha', // [PROPUESTO] aria-label
}

/** Orden fijo de los campos en la hoja (lenguaje 5). */
export const ORDEN_CAMPOS: CampoFicha[] = ['rutina', 'manejo_situaciones', 'red_apoyo']

/**
 * D2 · Lo que acompaña a cada campo en la hoja del relevo. Decisión de Martín del 28/10: pregunta
 * guía y ejemplo (lenguaje 5.1 a 5.3), con la mitigación de la especificación 3.11.3: el ejemplo va
 * después del contenido, separado por un borde, en gris y nunca como enlace.
 *
 * Si se decide mostrar solo la pregunta guía, basta con poner `MOSTRAR_EJEMPLO = false`.
 */
export const MOSTRAR_EJEMPLO = true

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

export const ESPERA = {
  minutos: (m: number | null) =>
    m === null
      ? 'Vuelve a intentarlo en unos minutos.' // [PROPUESTO]
      : m === 1
        ? 'Vuelve a intentarlo en 1 minuto.' // [PROPUESTO]
        : `Vuelve a intentarlo en ${m} minutos.`,
}

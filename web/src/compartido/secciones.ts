// Las seis secciones complementarias de la ficha (ADR-028), lo que comparten la app de la familia y
// la página del relevo: el orden fijo, el título, el tope y el aviso de Sus remedios. Textos de
// docs/lenguaje.md, sección 14 (MATU-49, aprobados por Jorge el 03-11). Contrato:
// docs/api/openapi.json (MATU-50), tipos en familia.openapi.ts.
import type { components } from './api/familia.openapi'

export type SeccionApi = components['schemas']['SeccionComplementaria']

/** Orden fijo en toda la app y en la página del relevo, sin importar cuándo se agregó cada una. */
export const ORDEN_SECCIONES: readonly SeccionApi[] = ['quien_es', 'preferencias', 'alimentacion', 'movilidad', 'comunicacion', 'remedios']

/** [lenguaje 14.1] */
export const TITULO_SECCION: Record<SeccionApi, string> = {
  quien_es: 'Quién es',
  preferencias: 'Lo que le hace bien',
  alimentacion: 'Comer y beber',
  movilidad: 'Moverse y descansar',
  comunicacion: 'Cómo hablarle',
  remedios: 'Sus remedios',
}

/** Máximo en caracteres (contrato): 500, y 800 en Sus remedios. */
export const topeDe = (s: SeccionApi) => (s === 'remedios' ? 800 : 500)
/** El contador pasa a `atenta` al 90 % del tope (450 o 720). */
export const avisoDe = (s: SeccionApi) => (topeDe(s) * 9) / 10

/** [lenguaje 14.2] Siempre a la vista, en los cuatro lugares (especificación 5). */
export const AVISO_REMEDIOS = 'Esto lo escribe la familia. No reemplaza la indicación del médico.'

export const esSeccion = (x: string): x is SeccionApi => (ORDEN_SECCIONES as readonly string[]).includes(x)

/** Ordena según la tabla de ADR-028 y quita repetidos y valores desconocidos. */
export const ordenar = (lista: readonly string[]): SeccionApi[] => ORDEN_SECCIONES.filter((s) => lista.includes(s))

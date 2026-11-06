// Cliente HTTP de MATU. La API sirve la aplicación desde el mismo origen (ADR-026): las rutas son
// relativas (/v1/...), sin CORS, y la cookie HttpOnly del relevo viaja sola con `withCredentials`.
// Nunca se registra ni se guarda el cuerpo de una petición o de una respuesta.
import axios, { isAxiosError } from 'axios'
import type { components } from './relevo.openapi'

export const api = axios.create({
  baseURL: '/',
  withCredentials: true,
  timeout: 20_000,
  headers: { Accept: 'application/json' },
})

export type Problema = components['schemas']['Problema']

/** Lo que la pantalla necesita de un error: nunca `title`, `detail`, `mensaje` ni `request_id`. */
export interface FalloApi {
  /** `null` = sin respuesta (red caída o tiempo agotado). */
  status: number | null
  /** `type` del problema RFC 7807, o `null` si la respuesta no lo trae. */
  tipo: string | null
  /** Campos de `errores[]` de un 422 (solo el nombre del campo). */
  campos: string[]
  /** `errores[]` de un 422 con su `tipo` (por ejemplo `string_too_long`), nunca el `mensaje`. */
  errores: { campo: string; tipo: string }[]
  /** `intentos_restantes` de `/errores/pin-incorrecto`. */
  intentosRestantes: number | null
  /** Cabecera `Retry-After` en segundos, si viene y es un entero. */
  reintentarEnSegundos: number | null
}

export function leerFallo(error: unknown): FalloApi {
  const vacio: FalloApi = { status: null, tipo: null, campos: [], errores: [], intentosRestantes: null, reintentarEnSegundos: null }
  if (!isAxiosError(error) || !error.response) return vacio
  const { status, data, headers } = error.response
  const cuerpo = (data && typeof data === 'object' ? data : {}) as Partial<Problema> & { intentos_restantes?: unknown }
  const errores = Array.isArray(cuerpo.errores) ? cuerpo.errores : []
  const retry = Number.parseInt(String(headers?.['retry-after'] ?? ''), 10)
  return {
    status,
    tipo: typeof cuerpo.type === 'string' ? cuerpo.type : null,
    campos: errores.map((e) => (e && typeof e.campo === 'string' ? e.campo : '')).filter(Boolean),
    errores: errores
      .filter((e) => e && typeof e.campo === 'string')
      .map((e) => ({ campo: String(e.campo), tipo: typeof (e as { tipo?: unknown }).tipo === 'string' ? String((e as { tipo?: unknown }).tipo) : '' })),
    intentosRestantes: typeof cuerpo.intentos_restantes === 'number' ? cuerpo.intentos_restantes : null,
    reintentarEnSegundos: Number.isFinite(retry) && retry > 0 ? retry : null,
  }
}

/**
 * Segundos que se esperan si un 429 llega sin `Retry-After`. El contrato la exige en todo 429
 * (`docs/api/openapi.json`); sin ella se toma el mínimo de la frase aprobada, «1 minuto».
 */
export const ESPERA_SIN_CABECERA = 60

/**
 * Minutos de un 429 para el texto: `Retry-After` en segundos hacia arriba, mínimo 1. Solo el número:
 * cada pantalla conserva su texto (lenguaje 7.3 el relevo, 13.3 entrar y crear cuenta, 19 recuperar
 * y el celular). El texto del límite por IP es solo de crear cuenta.
 */
export const minutosDeEspera = (segundos: number) => Math.max(1, Math.ceil(segundos / 60))

/** Un 429: cuánto esperar y los minutos del texto. `null` si el fallo no es un 429. */
export function esperaDe(f: FalloApi): { segundos: number; minutos: number } | null {
  if (f.status !== 429) return null
  const segundos = f.reintentarEnSegundos ?? ESPERA_SIN_CABECERA
  return { segundos, minutos: minutosDeEspera(segundos) }
}

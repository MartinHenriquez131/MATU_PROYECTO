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
  /** `intentos_restantes` de `/errores/pin-incorrecto`. */
  intentosRestantes: number | null
  /** Cabecera `Retry-After` en segundos, si viene y es un entero. */
  reintentarEnSegundos: number | null
}

export function leerFallo(error: unknown): FalloApi {
  const vacio: FalloApi = { status: null, tipo: null, campos: [], intentosRestantes: null, reintentarEnSegundos: null }
  if (!isAxiosError(error) || !error.response) return vacio
  const { status, data, headers } = error.response
  const cuerpo = (data && typeof data === 'object' ? data : {}) as Partial<Problema> & { intentos_restantes?: unknown }
  const errores = Array.isArray(cuerpo.errores) ? cuerpo.errores : []
  const retry = Number.parseInt(String(headers?.['retry-after'] ?? ''), 10)
  return {
    status,
    tipo: typeof cuerpo.type === 'string' ? cuerpo.type : null,
    campos: errores.map((e) => (e && typeof e.campo === 'string' ? e.campo : '')).filter(Boolean),
    intentosRestantes: typeof cuerpo.intentos_restantes === 'number' ? cuerpo.intentos_restantes : null,
    reintentarEnSegundos: Number.isFinite(retry) && retry > 0 ? retry : null,
  }
}

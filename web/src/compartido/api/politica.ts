// La política de privacidad vigente (MATU-75, contrato docs/api/README.md, decisiones 173 a 175).
// `GET /v1/politica` es pública: va sin sesión, sin token, sin grupo y sin cookies. Por eso tiene su
// propio cliente y no usa `apiFamilia` (que agrega el token) ni `api` (que manda la cookie del relevo).
//
// Con XMLHttpRequest, una petición al mismo origen manda las cookies aunque `withCredentials` sea
// `false`. Con `fetch` y `credentials: 'omit'` no las manda nunca: por eso este cliente usa el
// adaptador `fetch` de Axios, que convierte `withCredentials: false` en `credentials: 'omit'`.
import axios from 'axios'
import type { components } from './familia.openapi'

export type Politica = components['schemas']['PoliticaVista']
export type PoliticaAceptada = components['schemas']['PoliticaAceptadaVista']

export const apiPublica = axios.create({
  baseURL: '/',
  adapter: 'fetch',
  withCredentials: false,
  timeout: 20_000,
  headers: { Accept: 'application/json' },
})

/** `GET /v1/politica`: 200 con la versión, la fecha, la huella, el texto y el correo, o 503. */
export async function leerPolitica(): Promise<Politica> {
  return (await apiPublica.get<Politica>('/v1/politica', { withCredentials: false })).data
}

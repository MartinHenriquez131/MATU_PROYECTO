// La entrada de la familia en el cliente (especificación MATU-39, sección 6; contrato, decisiones
// 39 a 51).
//
// 1. El access token vive solo en esta variable del módulo. Nunca en localStorage, sessionStorage,
//    IndexedDB, la URL ni una cookie legible. Al recargar se pierde, y la app lo vuelve a pedir con
//    la cookie HttpOnly del refresh (`POST /v1/sesiones/renovar`).
// 2. Ante un 401 `token-invalido` o `no-autenticado`, renueva una vez y repite la petición.
// 3. La renovación va serializada entre pestañas con `navigator.locks` (decisión 51): el refresh
//    rota en cada uso y uno ya usado revoca toda la familia, así que dos pestañas no pueden
//    renovar a la vez con la misma cookie. Dentro de una pestaña, una sola renovación en vuelo.
// 4. `BroadcastChannel('matu-entrada')` avisa "renovado" y "salio" a las otras pestañas. Los
//    mensajes nunca llevan el token.
import axios, { isAxiosError, type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { leerFallo } from './cliente'
import type { components } from './familia.openapi'

type SesionRespuesta = components['schemas']['SesionRespuesta']

const CLIENTE = { 'X-MATU-Cliente': 'web' } as const

let accessToken: string | null = null
let grupoActual: string | null = null

/** Cliente de la app de la familia: mismo origen, con el token y el grupo elegidos en memoria. */
export const apiFamilia = axios.create({
  baseURL: '/',
  withCredentials: true,
  timeout: 20_000,
  headers: { Accept: 'application/json' },
})

// ---------------------------------------------------------------- avisos a la app

type Suceso = 'vencida' | 'salio'
const oyentes = new Set<(s: Suceso) => void>()

/** La app se entera de que la entrada venció o de que otra pestaña salió. */
export function escucharSesion(fn: (s: Suceso) => void): () => void {
  oyentes.add(fn)
  return () => oyentes.delete(fn)
}
const avisar = (s: Suceso) => oyentes.forEach((fn) => fn(s))

const canal: BroadcastChannel | null = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel('matu-entrada')

// Cuántas veces otra pestaña renovó. La cookie rotada la guarda el navegador, así que la pestaña
// que entra al lock después renueva con la cookie nueva, nunca con la anterior.
let renovacionesAjenas = 0
/** Para el doble y la revisión: cuántas renovaciones de otras pestañas vio esta. */
export const renovacionesDeOtrasPestanas = () => renovacionesAjenas

canal?.addEventListener('message', (e: MessageEvent<unknown>) => {
  if (e.data === 'renovado') renovacionesAjenas += 1
  if (e.data === 'salio') {
    olvidarTodo()
    avisar('salio')
  }
})

// ---------------------------------------------------------------- estado en memoria

export const hayToken = () => accessToken !== null

/** Fija el grupo de `X-Grupo-Id` (o lo quita con `null`). */
export function fijarGrupo(id: string | null) {
  grupoActual = id
}

function olvidarTodo() {
  accessToken = null
  grupoActual = null
}

// ---------------------------------------------------------------- renovar

/** Corre `fn` con el lock entre pestañas si el navegador lo tiene; si no, directo. */
async function conLock<T>(fn: () => Promise<T>): Promise<T> {
  const locks = typeof navigator !== 'undefined' ? navigator.locks : undefined
  if (!locks) return fn()
  return locks.request('matu-renovar', fn) as Promise<T>
}

let enVuelo: Promise<boolean> | null = null

/**
 * `POST /v1/sesiones/renovar`. `true` si hay token nuevo; `false` si la entrada venció (401
 * `sesion-expirada`). Un fallo de red o 5xx se propaga: no es lo mismo que haber vencido.
 * Las peticiones que esperan el lock esperan, no fallan.
 */
export function renovar(): Promise<boolean> {
  if (enVuelo) return enVuelo
  enVuelo = conLock(async () => {
    try {
      const r = await axios.post<SesionRespuesta>('/v1/sesiones/renovar', null, {
        baseURL: '/',
        withCredentials: true,
        timeout: 20_000,
        headers: { ...CLIENTE, Accept: 'application/json' },
      })
      accessToken = r.data.access_token
      canal?.postMessage('renovado')
      return true
    } catch (e) {
      if (isAxiosError(e) && e.response?.status === 401) {
        olvidarTodo()
        return false
      }
      throw e
    }
  }).finally(() => {
    enVuelo = null
  })
  return enVuelo
}

// ---------------------------------------------------------------- entrar y salir

/** `POST /v1/sesiones`. Guarda el access token en memoria; la cookie del refresh la fija la API. */
export async function entrar(email: string, contrasena: string): Promise<void> {
  const r = await apiFamilia.post<SesionRespuesta>('/v1/sesiones', { email, contrasena }, { headers: { ...CLIENTE } })
  accessToken = r.data.access_token
}

/**
 * `POST /v1/sesiones/cerrar`. Pase lo que pase (204, error o sin red), borra todo lo que está en
 * memoria y avisa a las otras pestañas (especificación 2.4).
 */
export async function salir(): Promise<void> {
  try {
    await apiFamilia.post('/v1/sesiones/cerrar', null, { headers: { ...CLIENTE } })
  } catch {
    // Salir es local de todos modos.
  } finally {
    olvidarTodo()
    canal?.postMessage('salio')
  }
}

// ---------------------------------------------------------------- interceptores

apiFamilia.interceptors.request.use((config) => {
  if (accessToken) config.headers.set('Authorization', `Bearer ${accessToken}`)
  if (grupoActual && !config.headers.has('X-Grupo-Id')) config.headers.set('X-Grupo-Id', grupoActual)
  return config
})

const RENUEVA = new Set(['/errores/token-invalido', '/errores/no-autenticado'])
const esDeSesiones = (url: string | undefined) => !!url && url.startsWith('/v1/sesiones')

type ConfigReintento = InternalAxiosRequestConfig & { _matuReintento?: boolean }

apiFamilia.interceptors.response.use(undefined, async (error: unknown) => {
  if (!isAxiosError(error) || !error.response || error.response.status !== 401) throw error
  const config = error.config as ConfigReintento | undefined
  if (!config || esDeSesiones(config.url)) throw error
  const f = leerFallo(error)
  // Un 401 sin `type` conocido se trata igual: lo único que lo arregla es renovar.
  if (f.tipo && !RENUEVA.has(f.tipo)) throw error
  if (config._matuReintento) {
    avisar('vencida')
    throw error
  }
  const ok = await renovar()
  if (!ok) {
    avisar('vencida')
    throw marcarVencida(error)
  }
  config._matuReintento = true
  config.headers.delete('Authorization')
  return apiFamilia.request(config)
})

/** Un error que ya avisó "vencida": la pantalla no muestra un segundo mensaje. */
export const VENCIDA = Symbol('matu-entrada-vencida')
function marcarVencida(e: AxiosError) {
  Object.defineProperty(e, VENCIDA, { value: true })
  return e
}
export const esVencida = (e: unknown) => !!e && typeof e === 'object' && VENCIDA in e

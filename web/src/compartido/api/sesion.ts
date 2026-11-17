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
/**
 * MATU-63 (decisión 408): de qué tipo es la cuenta que entró, según la última respuesta de
 * `/v1/sesiones` o `/renovar`. Una cuenta de comercio va a `/comercio`; una de familia, a la app.
 */
export type TipoCuenta = SesionRespuesta['tipo_cuenta']
let tipoCuenta: TipoCuenta | null = null
/**
 * MATU-81 (decisión 451): hasta cuándo vale la entrada de una cuenta de operación (12 horas desde el
 * segundo factor, sin ventana deslizante). `null` en las demás cuentas. Solo en memoria.
 */
let sesionVenceEn: string | null = null

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

/** MATU-63: el tipo de la cuenta que entró, o `null` sin entrada. Sin el campo, `familia` (su valor por omisión). */
export const tipoDeCuenta = (): TipoCuenta | null => (accessToken === null ? null : tipoCuenta)

/** MATU-81: el vencimiento de la entrada de operación (`sesion_vence_en`), o `null`. */
export const venceLaEntrada = (): string | null => (accessToken === null ? null : sesionVenceEn)

/** Fija el grupo de `X-Grupo-Id` (o lo quita con `null`). */
export function fijarGrupo(id: string | null) {
  grupoActual = id
}

function olvidarTodo() {
  accessToken = null
  grupoActual = null
  tipoCuenta = null
  sesionVenceEn = null
}

/** Lo que guarda cada respuesta de `/v1/sesiones`, `/renovar` y `/mfa`. */
function guardar(r: SesionRespuesta): TipoCuenta {
  accessToken = r.access_token
  tipoCuenta = r.tipo_cuenta ?? 'familia'
  sesionVenceEn = r.sesion_vence_en ?? null
  return tipoCuenta
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
      guardar(r.data)
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

/**
 * `POST /v1/sesiones`. Guarda el access token en memoria; la cookie del refresh la fija la API.
 * MATU-63: devuelve el tipo de la cuenta (`familia` o `comercio`).
 */
export async function entrar(email: string, contrasena: string): Promise<TipoCuenta> {
  const r = await apiFamilia.post<SesionRespuesta>('/v1/sesiones', { email, contrasena }, { headers: { ...CLIENTE } })
  return guardar(r.data)
}

/** MATU-81 (decisión 450): el desafío del segundo paso. Vive solo en la memoria de la pantalla. */
export interface DesafioMfa {
  desafio: string
  /** `desafio_expira_en`, 5 minutos. */
  expiraEn: string
}

/**
 * MATU-81: `POST /v1/sesiones` desde la entrada de operación. Con la contraseña de una cuenta de
 * operación, la API responde 401 `mfa-requerido` con el desafío y sin tokens: se devuelve el
 * desafío. Con otra cuenta, entra como siempre y devuelve su tipo. Los demás fallos se propagan.
 */
export async function entrarConSegundoFactor(email: string, contrasena: string): Promise<{ tipo: TipoCuenta } | DesafioMfa> {
  try {
    return { tipo: await entrar(email, contrasena) }
  } catch (e) {
    const cuerpo = isAxiosError(e) && e.response?.status === 401 ? (e.response.data as { type?: unknown; desafio?: unknown; desafio_expira_en?: unknown } | undefined) : undefined
    if (cuerpo && typeof cuerpo.type === 'string' && cuerpo.type.endsWith('/mfa-requerido') && typeof cuerpo.desafio === 'string' && typeof cuerpo.desafio_expira_en === 'string')
      return { desafio: cuerpo.desafio, expiraEn: cuerpo.desafio_expira_en }
    throw e
  }
}

/**
 * MATU-81: el 401 `mfa-requerido` de `POST /v1/sesiones`, es decir, la contraseña es de una cuenta de
 * operación que entró por la puerta de la familia o del comercio. La pantalla lleva a `/operacion/entrar`
 * y la persona vuelve a escribir su contraseña allá: el desafío se descarta, nunca va a la URL.
 */
export function esCuentaDeOperacion(error: unknown): boolean {
  const cuerpo = isAxiosError(error) && error.response?.status === 401 ? (error.response.data as { type?: unknown } | undefined) : undefined
  return !!cuerpo && typeof cuerpo.type === 'string' && cuerpo.type.endsWith('/mfa-requerido')
}

/** MATU-81: `POST /v1/sesiones/mfa` con el desafío y las 6 cifras. Guarda la entrada como `/v1/sesiones`. */
export async function entrarConCodigo(desafio: string, codigo: string): Promise<TipoCuenta> {
  const r = await apiFamilia.post<SesionRespuesta>('/v1/sesiones/mfa', { desafio, codigo }, { headers: { ...CLIENTE } })
  return guardar(r.data)
}

/**
 * MATU-81 (4.4): cierra una entrada que no corresponde a esta consola (una cuenta de familia o de
 * comercio en la entrada de operación, o la de operación que perdió el segundo factor), sin avisar a
 * las otras pestañas ni mostrar «Saliste». Nunca lanza.
 */
export async function cerrarSinAvisar(): Promise<void> {
  try {
    await apiFamilia.post('/v1/sesiones/cerrar', null, { headers: { ...CLIENTE } })
  } catch {
    // Es local de todos modos.
  } finally {
    olvidarTodo()
  }
}

/**
 * `POST /v1/sesiones/cerrar`. Pase lo que pase (204, error o sin red), borra todo lo que está en
 * memoria y avisa a las otras pestañas (especificación 2.4). MATU-55 (recomendación del analista):
 * después borra también la suscripción de avisos de este navegador.
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
  await olvidarSuscripcionPush()
}

/**
 * MATU-55: al salir, la inscripción de avisos del navegador se borra (el servidor ya borró el
 * endpoint al cerrar la sesión, decisión 47). Sin service worker o sin `PushManager` no hace nada, y
 * si falla, la salida sigue igual: nunca lanza.
 */
export async function olvidarSuscripcionPush(): Promise<void> {
  try {
    if (typeof navigator === 'undefined' || !('serviceWorker' in navigator) || !navigator.serviceWorker) return
    if (typeof window === 'undefined' || !('PushManager' in window)) return
    const registro = await navigator.serviceWorker.getRegistration('/')
    const sub = await registro?.pushManager.getSubscription()
    await sub?.unsubscribe()
  } catch {
    // No bloquea la salida.
  }
}

// ---------------------------------------------------------------- interceptores

// MATU-42 (decisión 291): las rutas de la persona invitada no llevan `X-Grupo-Id`, porque el grupo
// sale de la invitación. La presentación y la verificación son públicas: tampoco llevan la entrada.
const SIN_GRUPO = /^\/v1\/invitaciones\//
const PUBLICAS = new Set(['/v1/invitaciones/presentacion', '/v1/invitaciones/verificacion'])

apiFamilia.interceptors.request.use((config) => {
  const url = config.url ?? ''
  if (accessToken && !PUBLICAS.has(url)) config.headers.set('Authorization', `Bearer ${accessToken}`)
  if (grupoActual && !config.headers.has('X-Grupo-Id') && !SIN_GRUPO.test(url)) config.headers.set('X-Grupo-Id', grupoActual)
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

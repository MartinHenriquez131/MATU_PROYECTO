// MATU-55 (especificación 3.4, decisión de Jorge D6 = a): los avisos en este teléfono son una
// suscripción de Web Push real, con el envío simulado en el servidor. El permiso del navegador se
// pide solo cuando la persona toca «Activar en este…», nunca al cargar.
//
// MATU no guarda nada en el navegador: la suscripción la guarda el propio navegador, y a la API solo
// va su endpoint (`PUT /v1/dispositivos/actual/push`). El service worker es `/sw.js` (web/public).
import { borrarPushActual, guardarPushActual, type PushActual } from '../compartido/api/familia'

export const RUTA_SW = '/sw.js'

/**
 * Los estados de la tabla 3.4. El orden en que se decide es E, D, F, C y después A o B: en un iPhone
 * sin instalar manda E; si falta el soporte, D; sin clave pública, F.
 */
export type EstadoPush = 'ios-sin-instalar' | 'sin-soporte' | 'sin-clave' | 'bloqueado' | 'activados' | 'sin-activar'

/** `serviceWorker`, `PushManager` y `Notification`: los tres, o el navegador no recibe avisos (D). */
export function haySoporte(): boolean {
  return typeof navigator !== 'undefined' && 'serviceWorker' in navigator && !!navigator.serviceWorker && typeof window !== 'undefined' && 'PushManager' in window && 'Notification' in window
}

/** iPhone o iPad. iPadOS se presenta como Mac, y se distingue por la pantalla táctil. */
export function esIos(): boolean {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent ?? ''
  return /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && (navigator.maxTouchPoints ?? 0) > 1)
}

/** La app abierta desde la pantalla de inicio (ADR-026): `display-mode: standalone` o `navigator.standalone`. */
export function estaInstalada(): boolean {
  if (typeof window === 'undefined') return false
  const enInicio = typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches
  return enInicio || (navigator as Navigator & { standalone?: boolean }).standalone === true
}

/** La clave VAPID del contrato (base64url sin relleno) en bytes, para `applicationServerKey`. */
export function bytesDeClave(clave: string): Uint8Array<ArrayBuffer> {
  const b64 = clave.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (clave.length % 4)) % 4)
  const bin = atob(b64)
  const bytes = new Uint8Array(new ArrayBuffer(bin.length))
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return bytes
}

/** Si la suscripción se hizo con esta clave. Un navegador que no expone la clave se da por bueno. */
function mismaClave(sub: PushSubscription, clave: Uint8Array): boolean {
  const k = sub.options?.applicationServerKey
  if (!k) return true
  const a = new Uint8Array(k)
  return a.length === clave.length && a.every((b, i) => b === clave[i])
}

/** La suscripción que ya tiene este navegador, sin registrar el service worker si no existe. */
async function suscripcionActual(): Promise<PushSubscription | null> {
  const reg = await navigator.serviceWorker.getRegistration('/')
  return (await reg?.pushManager.getSubscription()) ?? null
}

/** El estado de este teléfono, con lo que dice el servidor y lo que dice el navegador. No pide permiso. */
export async function estadoPush(servidor: PushActual): Promise<EstadoPush> {
  if (esIos() && !estaInstalada()) return 'ios-sin-instalar'
  if (!haySoporte()) return 'sin-soporte'
  if (!servidor.clave_publica) return 'sin-clave'
  if (Notification.permission === 'denied') return 'bloqueado'
  if (!servidor.registrado) return 'sin-activar'
  try {
    const sub = await suscripcionActual()
    return sub && mismaClave(sub, bytesDeClave(servidor.clave_publica)) ? 'activados' : 'sin-activar'
  } catch {
    return 'sin-activar'
  }
}

export type ResultadoActivar = 'activados' | 'sin-elegir' | 'bloqueado'

/**
 * Pide el permiso (solo aquí), registra `/sw.js`, se suscribe con la clave pública y manda el
 * endpoint. Si el `PUT` falla, borra la suscripción para que no quede a medias y vuelve a lanzar el
 * error. Cerrar el aviso del navegador sin elegir es `sin-elegir`; «Bloquear», `bloqueado`.
 */
export async function activarPush(clave: string): Promise<ResultadoActivar> {
  let permiso = Notification.permission
  if (permiso !== 'granted') permiso = await Notification.requestPermission()
  if (permiso === 'denied') return 'bloqueado'
  if (permiso !== 'granted') return 'sin-elegir'
  await navigator.serviceWorker.register(RUTA_SW, { scope: '/' })
  const reg = await navigator.serviceWorker.ready
  const llave = bytesDeClave(clave)
  let sub = await reg.pushManager.getSubscription()
  if (sub && !mismaClave(sub, llave)) {
    await sub.unsubscribe()
    sub = null
  }
  sub ??= await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: llave })
  try {
    await guardarPushActual(sub.endpoint)
  } catch (e) {
    await sub.unsubscribe().catch(() => false)
    throw e
  }
  return 'activados'
}

/**
 * Primero el `DELETE` y después la suscripción del navegador: si el `DELETE` falla, todo sigue como
 * estaba (estado A, 3.4). Si después falla borrar la del navegador, el servidor ya no tiene el endpoint.
 */
export async function desactivarPush(): Promise<void> {
  await borrarPushActual()
  try {
    const sub = await suscripcionActual()
    await sub?.unsubscribe()
  } catch {
    // El servidor ya no envía a este teléfono: lo que quede en el navegador no recibe nada.
  }
}

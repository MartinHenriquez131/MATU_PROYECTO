// MATU-55: datos sintéticos de «Dónde entraste» y de los avisos, y una API falsa que responde por
// ruta («MÉTODO expresión» → respuesta, una lista que se recorre en orden, o una función). Lo que no
// calza responde 404. Devuelve las peticiones con su cuerpo. Nombres de navegador de ejemplo.
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { vi } from 'vitest'
import type { Cuenta, Dispositivo, EventoCuenta, PushActual } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'

/** El instante fijo de las pruebas: 12/11/2026 a las 12:00 de Chile (UTC−3 en verano). */
export const AHORA = new Date('2026-11-12T15:00:00Z')
/** Solo `Date` es falso: los temporizadores siguen reales para userEvent y los focos. */
export function fijarAhora() {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(AHORA)
}
const antes = (min: number) => new Date(AHORA.getTime() - min * 60_000).toISOString()

export const ID_ACTUAL = '3c9d4e20-0000-4000-8000-0000000005d1'
export const ID_PC = '3c9d4e20-0000-4000-8000-0000000005d2'
export const ID_IPAD = '3c9d4e20-0000-4000-8000-0000000005d3'

export const ACTUAL: Dispositivo = { id: ID_ACTUAL, plataforma: 'web', nombre: 'Chrome en Android', clase: 'telefono', creado_en: antes(60 * 24 * 10), ultimo_uso_en: antes(106), actual: true, push_activo: false }
/** Ayer a las 18:40 de Chile. */
export const PC: Dispositivo = { id: ID_PC, plataforma: 'web', nombre: 'Chrome en Windows', clase: 'computador', creado_en: antes(60 * 24 * 30), ultimo_uso_en: '2026-11-11T21:40:00Z', actual: false, push_activo: false }
/** Sin último uso: se muestra `creado_en`, el 01/11/2026 a las 09:05. */
export const IPAD: Dispositivo = { id: ID_IPAD, plataforma: 'web', nombre: 'Safari en iPad', clase: 'otro', creado_en: '2026-11-01T12:05:00Z', ultimo_uso_en: null, actual: false, push_activo: false }

const ev = (tipo: EventoCuenta['tipo'], ocurrido_en: string, dispositivo: EventoCuenta['dispositivo'] = null): EventoCuenta => ({ tipo, ocurrido_en, dispositivo })
const AQUI = { nombre: 'Chrome en Android', clase: 'telefono' as const, actual: true }
const EL_PC = { nombre: 'Chrome en Windows', clase: 'computador' as const, actual: false }

/** Hoy a las 10:14 y 09:02, ayer a las 21:15 y 19:00, el lunes 09/11 y el 01/11, del más nuevo al más viejo. */
export const EVENTOS: EventoCuenta[] = [
  ev('entraste', '2026-11-12T13:14:00Z', AQUI),
  ev('codigo_recuperacion_pedido', '2026-11-12T12:02:00Z'),
  ev('contrasena_cambiada', '2026-11-12T00:15:00Z'),
  ev('salida_por_seguridad', '2026-11-11T22:00:00Z', EL_PC),
  ev('cerraste_en_dispositivo', '2026-11-09T15:00:00Z', EL_PC),
  ev('saliste', '2026-11-09T14:00:00Z', null),
  ev('avisos_activados', '2026-11-01T15:00:00Z', AQUI),
]

export const CUENTA: Cuenta = {
  id: '3c9d4e20-0000-4000-8000-0000000005c1',
  nombre: 'Carmen',
  email: 'carmen@example.org',
  celular_enmascarado: '+56 9 •••• ••37',
  celular_verificado: true,
  celular_canal: 'sms',
  politica_aceptada: null,
}

/** Una clave VAPID sintética con la forma del contrato: «B» y 86 caracteres base64url (65 bytes). */
export const CLAVE = `B${'A'.repeat(86)}`
export const PUSH_LIBRE: PushActual = { clave_publica: CLAVE, permitido: true, registrado: false, envio_simulado: true }

export interface Respuesta {
  status: number
  cuerpo?: unknown
}
export interface Pedida {
  metodo: string
  ruta: string
  cuerpo: unknown
}
type Manejador = Respuesta | Respuesta[] | ((p: Pedida) => Respuesta | Promise<Respuesta>)

export const problema = (status: number, tipo = 'interno'): Respuesta => ({ status, cuerpo: { type: `/errores/${tipo}`, title: 'Texto de la API que no se muestra', status } })

/** La API por ruta, con las lecturas y escrituras de MATU-55 por omisión. */
export function apiCuenta(rutas: Record<string, Manejador> = {}) {
  const pedidas: Pedida[] = []
  const vistas = new Map<string, number>()
  const base: Record<string, Manejador> = {
    'GET ^/v1/cuenta$': { status: 200, cuerpo: CUENTA },
    'GET ^/v1/dispositivos$': { status: 200, cuerpo: { items: [ACTUAL, PC, IPAD] } },
    'GET ^/v1/yo/ingresos$': { status: 200, cuerpo: { eventos: EVENTOS, hay_mas: false } },
    'GET ^/v1/yo/avisos$': { status: 200, cuerpo: { correo: true, push: true } },
    'PUT ^/v1/yo/avisos$': (p) => ({ status: 200, cuerpo: p.cuerpo }),
    'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: PUSH_LIBRE },
    'PUT ^/v1/dispositivos/actual/push$': { status: 204 },
    'DELETE ^/v1/dispositivos/actual/push$': { status: 204 },
    'DELETE ^/v1/dispositivos/': { status: 204 },
  }
  const todas = { ...base, ...rutas }
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const metodo = (config.method ?? 'get').toUpperCase()
    const ruta = config.url ?? ''
    const cuerpo = typeof config.data === 'string' && config.data ? JSON.parse(config.data) : (config.data ?? null)
    const p: Pedida = { metodo, ruta, cuerpo }
    pedidas.push(p)
    // Las rutas propias de la prueba van primero: pisan a las de omisión.
    const clave = [...Object.keys(rutas), ...Object.keys(base)].find((k) => {
      const [m, ...e] = k.split(' ')
      return m === metodo && new RegExp(e.join(' ')).test(ruta)
    })
    const h = clave ? todas[clave] : problema(404, 'no-encontrado')
    let r: Respuesta
    if (Array.isArray(h)) {
      const n = vistas.get(clave!) ?? 0
      vistas.set(clave!, n + 1)
      r = h[Math.min(n, h.length - 1)]
    } else r = typeof h === 'function' ? await h(p) : h
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return { pedidas, de: (m: string, r: string) => pedidas.filter((x) => x.metodo === m && x.ruta === r) }
}

/** jsdom no trae `showModal` ni `close`. */
export function dialogoDeJsdom() {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.removeAttribute('open')
  }
}

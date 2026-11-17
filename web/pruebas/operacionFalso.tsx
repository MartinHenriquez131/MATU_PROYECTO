// La API de la consola de operación para las pruebas de MATU-81: el cliente real (`apiFamilia`, con
// sus interceptores y `leerFallo`) sobre el doble de doble/operacion.ts, el mismo que responde en
// `npm run dev`. Solo datos sintéticos: una cuenta de operación inventada con un código fijo, comercios
// de prueba y pedidos inventados.
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { vi } from 'vitest'
import { crearConsola, crearMfa, type ModoOperacion, type RespuestaDoble } from '../doble/operacion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { apiFamilia } from '../src/compartido/api/sesion'

export { CODIGO_MFA, CODIGO_RETIRO_DE_EJEMPLO, CORREO_ADMIN_DE_EJEMPLO, ID_OPERACION } from '../doble/operacion'

/** La cuenta de operación sintética de las pruebas (y del doble de `npm run dev`). */
export const CORREO_OPERACION = 'operacion@example.com'
export const CLAVE = 'contrasena-ejemplo' // pragma: allowlist secret
/** El reloj del servidor en las pruebas: 17/11/2026, 14:20 de Chile (17:20 UTC). */
export const AHORA = new Date('2026-11-17T17:20:00Z')

export interface Peticion {
  linea: string
  cuerpo: unknown
  ifMatch: string | null
  query: string
}

/** Responde antes que el doble. Recibe la consola del doble para cambiar una respuesta suya. */
export type Sobre = (linea: string, cuerpo: unknown, consola: ReturnType<typeof crearConsola>) => RespuestaDoble | undefined

/**
 * Monta la API. `tipo` es el de la cuenta en `/renovar` (`null`: la cookie venció). `sobre` responde
 * antes que el doble, para los errores de cada prueba. Con la contraseña de `operacion@example.com`,
 * `POST /v1/sesiones` responde el desafío; con `familia@example.com` entra una cuenta de familia.
 */
export function apiOperacion({ tipo = 'operacion', modo = 'operacion', sobre }: { tipo?: 'operacion' | 'familia' | null; modo?: ModoOperacion; sobre?: Sobre } = {}) {
  const peticiones: Peticion[] = []
  const consola = crearConsola({ ahora: () => AHORA, modo })
  const mfa = crearMfa()
  const vence = () => new Date(Date.now() + 12 * 3_600_000).toISOString()
  const sesion = (t: 'operacion' | 'familia' | 'comercio') => ({
    access_token: 'token-sintetico',
    token_type: 'bearer',
    expira_en: 900,
    tipo_cuenta: t,
    sesion_vence_en: t === 'operacion' ? vence() : null,
  })
  const responder = (config: InternalAxiosRequestConfig, r: RespuestaDoble): AxiosResponse => {
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: { date: AHORA.toUTCString(), ...(r.cabeceras ?? {}) }, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  axios.defaults.adapter = async (config) =>
    tipo === null ? responder(config, { status: 401, cuerpo: { type: '/errores/sesion-expirada', status: 401 } }) : responder(config, { status: 200, cuerpo: sesion(tipo) })
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const ruta = config.url ?? ''
    const linea = `${(config.method ?? 'get').toUpperCase()} ${ruta}`
    const cuerpo = typeof config.data === 'string' && config.data ? (JSON.parse(config.data) as unknown) : null
    const ifMatch = config.headers?.get?.('If-Match')
    const query = new URLSearchParams(Object.entries((config.params ?? {}) as Record<string, string>))
    peticiones.push({ linea, cuerpo, ifMatch: typeof ifMatch === 'string' ? ifMatch : null, query: query.toString() })
    const especial = sobre?.(linea, cuerpo, consola)
    if (especial) return responder(config, especial)
    if (linea === 'POST /v1/sesiones') {
      const c = cuerpo as { email: string; contrasena: string }
      if (c.contrasena !== CLAVE) return responder(config, { status: 401, cuerpo: { type: '/errores/credenciales-invalidas', status: 401 } })
      if (c.email === CORREO_OPERACION) return responder(config, mfa.desafiar(c.email))
      return responder(config, { status: 200, cuerpo: sesion(c.email.startsWith('comercio') ? 'comercio' : 'familia') })
    }
    if (linea === 'POST /v1/sesiones/mfa') {
      const r = mfa.verificar(cuerpo)
      return responder(config, 'email' in r ? { status: 200, cuerpo: sesion('operacion') } : r)
    }
    if (linea === 'POST /v1/sesiones/cerrar') return responder(config, { status: 204 })
    const r = consola.atender({ metodo: (config.method ?? 'get').toUpperCase(), ruta, query, cuerpo, ifMatch: typeof ifMatch === 'string' ? ifMatch : null })
    return responder(config, r ?? { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404 } })
  }
  return { peticiones, consola, lineas: () => peticiones.map((x) => x.linea) }
}

/** Anota lo que se escribiría en el almacenamiento del navegador: nada de la consola va ahí. */
export function vigilarAlmacenamiento() {
  const escrito: string[] = []
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string, valor: string) {
    escrito.push(`${clave}=${valor}`)
  })
  return escrito
}

/** La app con las regiones vivas antes, como en main.tsx. */
export function conRegionesVivas(pantalla: ReactElement) {
  render(
    <>
      <RegionesVivas />
      {pantalla}
    </>,
  )
  return { amable: document.querySelector<HTMLElement>('[aria-live="polite"]')!, urgente: document.querySelector<HTMLElement>('[aria-live="assertive"]')! }
}

/** La hora de Chile `HH:MM` de un instante. */
export const horaDeChile = (iso: string) =>
  new Intl.DateTimeFormat('es-CL', { timeZone: 'America/Santiago', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(iso))


/** jsdom no trae `showModal` ni `close`: el diálogo se abre y se cierra con el atributo `open`. */
export function dialogoDeJsdom() {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.hasAttribute('open')) return
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
}

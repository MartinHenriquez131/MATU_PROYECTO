// Las tres rutas públicas del relevo (contrato docs/api/propuestos/relevo.openapi.yaml).
// El token viaja solo en el cuerpo de un POST, nunca en la URL ni en una cabecera.
import { api } from './cliente'
import type { components } from './relevo.openapi'

export type Presentacion = components['schemas']['Presentacion']
export type FichaRelevo = components['schemas']['FichaRelevo']
export type CampoFicha = components['schemas']['CampoFicha']
type SolicitudPresentacion = components['schemas']['SolicitudPresentacion']
type SolicitudCanje = components['schemas']['SolicitudCanje']

/** POST /v1/relevo/presentacion: los dos nombres de pila, antes del PIN. */
export async function presentar(token: string): Promise<Presentacion> {
  const cuerpo: SolicitudPresentacion = { token }
  const r = await api.post<Presentacion>('/v1/relevo/presentacion', cuerpo)
  return r.data
}

/** POST /v1/relevo/canje: 204 con la cookie de sesión de relevo. */
export async function canjear(token: string, pin: string): Promise<void> {
  const cuerpo: SolicitudCanje = { token, pin }
  await api.post('/v1/relevo/canje', cuerpo)
}

/** GET /v1/relevo/ficha: con la cookie. */
export async function leerFicha(): Promise<FichaRelevo> {
  const r = await api.get<FichaRelevo>('/v1/relevo/ficha')
  return r.data
}

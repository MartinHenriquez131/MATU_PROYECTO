// Rutas de la app de la familia (contrato docs/api/openapi.json, tipos en familia.openapi.ts,
// regenerados con `npm run contrato:familia`). El grupo viaja en `X-Grupo-Id` y el token en
// `Authorization`, los dos desde la memoria de sesion.ts. Nunca se registra un cuerpo.
import { isAxiosError } from 'axios'
import { apiFamilia } from './sesion'
import type { components } from './familia.openapi'

type S = components['schemas']

/** `POST /v1/usuarios`, con el celular (`telefono`, decisión 65). */
export type SolicitudRegistro = S['SolicitudRegistro']
export type CuentaCreada = S['CuentaCreadaRespuesta']
/** `GET /v1/grupos`, con `puede_ver_plan` para el pagador (D3). */
export type Grupo = S['GrupoRespuesta']
export type Rol = 'admin' | 'cuidador' | 'pagador' | 'observador'
export type PersonaCompleta = S['PersonaVistaCompleta']
export type PersonaListada = S['PersonaVistaCompleta'] | S['PersonaVistaPagador'] | S['PersonaVistaObservador']
/** `etiqueta` y `region` tienen valor por omisión en el contrato («Casa», «Metropolitana»): no se piden en este sprint. */
type DireccionNueva = Omit<S['DireccionNueva'], 'etiqueta' | 'region'> & Partial<Pick<S['DireccionNueva'], 'etiqueta' | 'region'>>
export type SolicitudPersona = Omit<S['SolicitudPersona'], 'direccion'> & { direccion?: DireccionNueva | null }
export type PersonaCreada = S['PersonaCreada']
export type Calidad = S['CalidadOtorgante']
export type Ficha = S['FichaVista']
export type EstadoCampo = S['EstadoCampoVista']
export type CampoGuardado = S['CampoGuardadoVista']
export type CampoApi = keyof S['CamposVista']

/** Un rol que no se reconoce se trata como `observador` (especificación 2.2). */
export function rolDe(g: Grupo | null | undefined): Rol {
  const r = g?.rol
  return r === 'admin' || r === 'cuidador' || r === 'pagador' ? r : 'observador'
}

export const nombrePilaDe = (p: PersonaListada) => ('nombre_pila' in p && p.nombre_pila ? p.nombre_pila : p.nombre)

export async function crearCuenta(cuerpo: SolicitudRegistro): Promise<CuentaCreada> {
  return (await apiFamilia.post<CuentaCreada>('/v1/usuarios', cuerpo)).data
}

export async function listarGrupos(): Promise<Grupo[]> {
  return (await apiFamilia.get<Grupo[]>('/v1/grupos')).data
}

export async function crearGrupo(nombre: string): Promise<Grupo> {
  const cuerpo: S['SolicitudGrupo'] = { nombre }
  return (await apiFamilia.post<Grupo>('/v1/grupos', cuerpo)).data
}

export async function listarPersonas(grupoId: string): Promise<PersonaListada[]> {
  const r = await apiFamilia.get<PersonaListada[]>(`/v1/grupos/${encodeURIComponent(grupoId)}/personas-cuidadas`, {
    headers: { 'X-Grupo-Id': grupoId },
  })
  return r.data
}

export async function registrarPersona(grupoId: string, cuerpo: SolicitudPersona): Promise<PersonaCreada> {
  const r = await apiFamilia.post<PersonaCreada>(`/v1/grupos/${encodeURIComponent(grupoId)}/personas-cuidadas`, cuerpo, {
    headers: { 'X-Grupo-Id': grupoId },
  })
  return r.data
}

export async function leerFicha(personaId: string): Promise<Ficha> {
  return (await apiFamilia.get<Ficha>(`/v1/personas-cuidadas/${encodeURIComponent(personaId)}/plan/ficha`)).data
}

/**
 * `PUT …/plan/ficha/{campo}`: siempre condicional. Con `etag` manda `If-Match`; sin él (campo nunca
 * escrito), `If-None-Match: *`. Devuelve el campo guardado con su `ETag`.
 */
export async function guardarCampo(personaId: string, campo: CampoApi, texto: string, etag: string | null): Promise<CampoGuardado> {
  const cuerpo: S['SolicitudCampo'] = { texto }
  const r = await apiFamilia.put<CampoGuardado>(`/v1/personas-cuidadas/${encodeURIComponent(personaId)}/plan/ficha/${campo}`, cuerpo, {
    headers: etag ? { 'If-Match': etag } : { 'If-None-Match': '*' },
  })
  const cabecera = r.headers?.etag
  return { ...r.data, etag: typeof cabecera === 'string' && cabecera ? cabecera : r.data.etag }
}

/** El contenido de un 412 `version-desactualizada`: lo vigente y su `ETag`. */
export interface Conflicto {
  actual: EstadoCampo
  /** `ETag` de la respuesta 412, o `actual.etag`; `null` si el campo nunca se escribió. */
  etag: string | null
}

export function leerConflicto(error: unknown): Conflicto | null {
  if (!isAxiosError(error) || error.response?.status !== 412) return null
  const cuerpo = error.response.data as { actual?: EstadoCampo } | undefined
  const actual: EstadoCampo = cuerpo?.actual ?? { texto: null, etag: null, actualizado_por: null, actualizado_en: null }
  const cabecera = error.response.headers?.etag
  return { actual, etag: typeof cabecera === 'string' && cabecera ? cabecera : actual.etag }
}

/** `GET …/plan/aperturas` (MATU-45): lo que hicieron los relevos, del más reciente al más antiguo. */
export type Apertura = S['AperturaVista']
export type TipoApertura = S['TipoApertura']
export type ListaAperturas = S['ListaAperturasVista']

export async function listarAperturas(personaId: string, cursor: string | null = null, limite = 20): Promise<ListaAperturas> {
  const params: { limite: number; cursor?: string } = { limite }
  if (cursor) params.cursor = cursor
  return (await apiFamilia.get<ListaAperturas>(`/v1/personas-cuidadas/${encodeURIComponent(personaId)}/plan/aperturas`, { params })).data
}

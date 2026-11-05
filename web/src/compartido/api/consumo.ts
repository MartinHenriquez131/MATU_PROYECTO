// Rutas del consumo (MATU-36, contrato docs/api/openapi.json): la lista, crear, cambiar con
// `If-Match`, seguir y dejar de seguir, eliminar, y la autorización con finalidad `consumo`.
// Nada de esto se guarda en el navegador ni va en la URL salvo los ids del contrato.
import { isAxiosError } from 'axios'
import { apiFamilia } from './sesion'
import type { components } from './familia.openapi'

type S = components['schemas']

export type Perfil = S['PerfilConsumoVista']
export type Unidad = S['UnidadConsumo']
export type SolicitudPerfil = S['SolicitudPerfil']
export type SolicitudEdicion = S['SolicitudEdicionPerfil']
export type SolicitudAutorizacion = S['SolicitudAutorizacionEntrada']
export type AutorizacionCreada = S['AutorizacionCreada']

const base = (personaId: string) => `/v1/personas-cuidadas/${encodeURIComponent(personaId)}/consumo`

/** Una página de la lista con los insumos que se siguen y los que no (`activo=todos`, decisión 69). */
export async function listarConsumo(personaId: string, cursor: string | null): Promise<S['ListaPerfiles']> {
  const params: Record<string, string> = { activo: 'todos' }
  if (cursor) params.cursor = cursor
  return (await apiFamilia.get<S['ListaPerfiles']>(base(personaId), { params })).data
}

export async function crearPerfil(personaId: string, cuerpo: SolicitudPerfil): Promise<Perfil> {
  return (await apiFamilia.post<Perfil>(base(personaId), cuerpo)).data
}

/** `PATCH` siempre condicional: solo los campos que cambiaron, con el `ETag` leído. */
export async function editarPerfil(personaId: string, perfilId: string, cuerpo: SolicitudEdicion, etag: string): Promise<Perfil> {
  const r = await apiFamilia.patch<Perfil>(`${base(personaId)}/${encodeURIComponent(perfilId)}`, cuerpo, { headers: { 'If-Match': etag } })
  return r.data
}

export async function seguirPerfil(personaId: string, perfilId: string, seguir: boolean): Promise<Perfil> {
  const accion = seguir ? 'activar' : 'desactivar'
  return (await apiFamilia.post<Perfil>(`${base(personaId)}/${encodeURIComponent(perfilId)}/${accion}`)).data
}

export async function eliminarPerfil(personaId: string, perfilId: string): Promise<void> {
  await apiFamilia.delete(`${base(personaId)}/${encodeURIComponent(perfilId)}`)
}

export async function autorizarConsumo(personaId: string, cuerpo: SolicitudAutorizacion): Promise<AutorizacionCreada> {
  return (await apiFamilia.post<AutorizacionCreada>(`/v1/personas-cuidadas/${encodeURIComponent(personaId)}/consentimientos`, cuerpo)).data
}

/** El perfil vigente de un 412 `version-desactualizada`. */
export function leerConflictoPerfil(error: unknown): Perfil | null {
  if (!isAxiosError(error) || error.response?.status !== 412) return null
  const cuerpo = error.response.data as { actual?: Perfil } | undefined
  return cuerpo?.actual ?? null
}

/** El nombre visible del insumo: `nombre_libre`, o el del producto cuando exista el catálogo. */
export const nombreDe = (p: Perfil) => p.nombre_libre ?? p.producto?.nombre ?? ''

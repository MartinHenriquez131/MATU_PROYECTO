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

// ---------------------------------------------------------------- MATU-37: lo que se acaba pronto

export type PorAcabarse = S['InsumoPorAcabarseVista']

/** Los insumos dentro de su ventana de aviso, con `avisando` y `alerta_id` (decisión 74). */
export async function listarPorAcabarse(personaId: string): Promise<PorAcabarse[]> {
  return (await apiFamilia.get<S['ListaPorAcabarse']>(`${base(personaId)}/por-acabarse`)).data.items
}

/** Lo comprado: exactamente uno de `envases` (1 a 99) o `cantidad` (1 a 10.000), decisiones 137 y 147. */
export type LoComprado = { envases: number } | { cantidad: number }

/**
 * «Ya lo resolví» por perfil (decisiones 76 y 147): cierra el aviso de la fecha estimada actual
 * aunque la alerta aún no exista. Sin lo comprado (`null`) va sin cuerpo y solo descarta: «no
 * compré» nunca es `cantidad: 0` ni `envases: 0`, que responden 422. Con lo comprado, el backend lo
 * suma a lo que estima que queda hoy y devuelve el insumo recalculado.
 */
export async function resolverAviso(personaId: string, perfilId: string, etag: string, comprado: LoComprado | null): Promise<PorAcabarse> {
  const cuerpo = comprado ?? undefined
  // Siempre condicional (decisión 80): el `etag` del ítem de `por-acabarse`, tal cual. Un 412 no suma nada.
  return (await apiFamilia.post<PorAcabarse>(`${base(personaId)}/${encodeURIComponent(perfilId)}/resolver`, cuerpo, { headers: { 'If-Match': etag } })).data
}

// ---------------------------------------------------------------- MATU-60: la lista de insumos

export type ListaInsumos = S['ListaInsumos']
export type LineaListaInsumos = S['LineaListaInsumos']

/**
 * La lista de hoy (`GET …/consumo/lista`, decisiones 116 a 122): sin paginación, sin cuerpo y sin
 * consulta. Se pide cada vez que se abre la pantalla y nunca se guarda. Lo que la familia cambia,
 * agrega o quita en la pantalla nunca llega al servidor.
 */
export async function verListaInsumos(personaId: string): Promise<ListaInsumos> {
  return (await apiFamilia.get<ListaInsumos>(`${base(personaId)}/lista`)).data
}

// ---------------------------------------------------------------- MATU-51: «Compré» y «Me quedan»

/**
 * «Compré» (`POST …/{perfil_id}/reponer`, decisiones 136 a 141): suma lo comprado a lo que MATU
 * estima que queda hoy. Siempre con `If-Match` (412 sin sumar nada, 428 sin él). La cantidad va solo
 * en el cuerpo, nunca una fecha: la pone el servidor.
 */
export async function anotarCompra(personaId: string, perfilId: string, etag: string, comprado: LoComprado): Promise<PorAcabarse> {
  const cuerpo: S['SolicitudReposicion'] = comprado
  return (await apiFamilia.post<PorAcabarse>(`${base(personaId)}/${encodeURIComponent(perfilId)}/reponer`, cuerpo, { headers: { 'If-Match': etag } })).data
}

/** «Me quedan» (`POST …/{perfil_id}/recontar`, decisión 139): lo que queda hoy, de 0 a 100.000, con `If-Match`. */
export async function anotarLoQueQueda(personaId: string, perfilId: string, etag: string, quedan: number): Promise<PorAcabarse> {
  const cuerpo: S['SolicitudRecuento'] = { stock_unidades: quedan }
  return (await apiFamilia.post<PorAcabarse>(`${base(personaId)}/${encodeURIComponent(perfilId)}/recontar`, cuerpo, { headers: { 'If-Match': etag } })).data
}

// El catálogo curado (MATU-59, contrato docs/api/openapi.json, decisiones 158 a 170 de
// docs/api/README.md). Una sola lectura, sin parámetros. Es general: no lleva grupo ni persona,
// así que la petición no manda `X-Grupo-Id` (decisión 159). Nada se guarda en el navegador.
import { apiFamilia } from './sesion'
import type { components } from './familia.openapi'

type S = components['schemas']

export type Catalogo = S['Catalogo']
export type CategoriaCatalogo = S['CategoriaCatalogo']
export type ProductoCatalogo = S['ProductoCatalogo']
export type OfertaCatalogo = S['OfertaCatalogo']

/**
 * `GET /v1/catalogo`. El interceptor de sesion.ts pone `X-Grupo-Id` solo si la petición no lo trae:
 * con `false`, Axios lo cuenta como presente y no lo envía.
 */
export async function verCatalogo(): Promise<Catalogo> {
  return (await apiFamilia.get<Catalogo>('/v1/catalogo', { headers: { 'X-Grupo-Id': false } })).data
}

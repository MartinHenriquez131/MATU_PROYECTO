// La consola del comercio contra el contrato (docs/api/openapi.json, decisiones 407 a 425 de
// docs/api/README.md). Usa el cliente de la familia: la misma entrada en memoria, la renovación
// con la cookie y ningún `X-Grupo-Id` (el comercio nunca elige un grupo). El código de retiro va
// solo en el cuerpo de `validar-codigo`: nunca en la URL, un log ni el almacenamiento del navegador.
import type { AxiosResponse } from 'axios'
import { apiFamilia } from './sesion'
import type { components } from './familia.openapi'

type S = components['schemas']
/**
 * Decisión 430: el motivo de una parte cancelada. Está en docs/api/openapi.json, pero los tipos
 * generados todavía no lo traen: regenerarlos arrastra el cambio de la copia de MATU-54 (decisión
 * 427), que pide textos nuevos de «Tus datos». Hasta entonces se suma aquí, opcional.
 */
export type MotivoCancelacion = 'producto_faltante' | 'cancelada_por_familia' | null
type ConMotivo = { motivo_cancelacion?: MotivoCancelacion }
export type ComercioDeLaCuenta = S['ComercioDeLaCuenta']
export type ParteResumen = S['ParteResumen'] & ConMotivo
export type ParteVista = S['ParteVista'] & ConMotivo
export type LineaComercio = S['LineaComercioVista']
export type EstadoParte = ParteResumen['estado']
export type EstadoCodigo = ParteResumen['estado_codigo']
export type ResultadoCodigo = S['ResultadoCodigoVista']
export type ProductoDelComercio = S['ProductoDelComercio']
export type SolicitudMarca = S['SolicitudMarca']
export type SolicitudProducto = S['SolicitudProducto']

/** Una parte con el `ETag` de su versión, para el `If-Match` de la acción siguiente. */
export interface ParteConVersion {
  parte: ParteVista
  etag: string | null
}

const etagDe = (r: AxiosResponse) => {
  const v = r.headers?.etag
  return typeof v === 'string' && v ? v : null
}

/**
 * La hora del servidor según la cabecera `Date` (5.4, «atrasada»): nunca el reloj del teléfono solo.
 * `null` si la respuesta no la trae o no se puede leer.
 */
const fechaDe = (r: AxiosResponse) => {
  const v = r.headers?.date
  const d = typeof v === 'string' ? new Date(v) : null
  return d && !Number.isNaN(d.getTime()) ? d : null
}

const conVersion = (r: AxiosResponse<ParteVista>): ParteConVersion => ({ parte: r.data, etag: etagDe(r) })
const siCalza = (etag: string | null) => (etag ? { headers: { 'If-Match': etag } } : {})

/** `GET /v1/comercio`: el nombre, si es de prueba y el contacto de «Avisa a MATU» (O2). */
export async function verComercio(): Promise<ComercioDeLaCuenta> {
  return (await apiFamilia.get<ComercioDeLaCuenta>('/v1/comercio')).data
}

/** `GET /v1/comercio/partes`: las abiertas y las cerradas hoy, con la hora del servidor. */
export async function listarPartes(): Promise<{ partes: ParteResumen[]; fecha: Date | null }> {
  const r = await apiFamilia.get<S['ListaPartes']>('/v1/comercio/partes')
  return { partes: r.data.partes, fecha: fechaDe(r) }
}

export async function verParte(id: string): Promise<ParteConVersion> {
  return conVersion(await apiFamilia.get<ParteVista>(`/v1/comercio/partes/${id}`))
}

/** «Empezar a preparar»: de `enviada` a `preparando`. 409 `estado-parte`, 412 `version-desactualizada`. */
export async function prepararParte(id: string, etag: string | null): Promise<ParteConVersion> {
  return conVersion(await apiFamilia.post<ParteVista>(`/v1/comercio/partes/${id}/preparar`, null, siCalza(etag)))
}

/** «Lo tengo» o «No lo tengo», repetible mientras la parte esté `preparando` (O4). */
export async function marcarLinea(id: string, lineaId: string, marca: SolicitudMarca, etag: string | null): Promise<ParteConVersion> {
  return conVersion(await apiFamilia.put<ParteVista>(`/v1/comercio/partes/${id}/lineas/${lineaId}`, marca, siCalza(etag)))
}

/** «Listo para retirar». 422 `lineas-pendientes`; sin ninguno, la parte queda `cancelada` (O3). */
export async function marcarLista(id: string, etag: string | null): Promise<ParteConVersion> {
  return conVersion(await apiFamilia.post<ParteVista>(`/v1/comercio/partes/${id}/listo`, null, siCalza(etag)))
}

/** El código solo en el cuerpo (D-63-4). 429 `demasiados-intentos` con `Retry-After`, 503. */
export async function validarCodigo(id: string, codigo: string): Promise<ResultadoCodigo> {
  return (await apiFamilia.post<ResultadoCodigo>(`/v1/comercio/partes/${id}/validar-codigo`, { codigo })).data
}

export async function listarProductos(): Promise<ProductoDelComercio[]> {
  return (await apiFamilia.get<S['ListaProductos']>('/v1/comercio/productos')).data.productos
}

/** Cambia cuántos tiene (0 a 9.999) o si lo ofrece. Nunca el precio (D-63-2). 412 con otra versión. */
export async function cambiarProducto(ofertaId: string, cambios: SolicitudProducto, etag: string): Promise<ProductoDelComercio> {
  return (await apiFamilia.patch<ProductoDelComercio>(`/v1/comercio/productos/${ofertaId}`, cambios, siCalza(etag))).data
}

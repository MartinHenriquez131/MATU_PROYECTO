// La consola de operación contra el contrato (docs/api/openapi.json, decisiones 449 a 465 de
// docs/api/README.md). Usa el cliente de la familia: la misma entrada en memoria, la renovación con
// la cookie y ningún `X-Grupo-Id`. La referencia de la búsqueda va solo en el cuerpo (C7) y el
// correo del retracto por correo también (D-81-9): nunca en una ruta, un parámetro ni un log.
import { isAxiosError, type AxiosResponse } from 'axios'
import { apiFamilia } from './sesion'
import type { components } from './familia.openapi'

type S = components['schemas']
export type PedidoOperacion = S['PedidoOperacion']
export type PedidoDetalle = S['PedidoDetalle']
export type ParteDetalle = S['ParteDetalle']
export type LineaDetalle = S['LineaDetalle']
export type EventoLineaTiempo = S['EventoLineaTiempo']
export type AccionDisponible = S['AccionDisponible']
export type AccionPedido = AccionDisponible['accion']
export type EstadoPedido = PedidoDetalle['estado']
export type CodigoGenerado = S['CodigoGenerado']
export type CobroPedido = S['CobroPedido']
export type VentaVista = S['VentaVista']
export type AnulacionVista = S['AnulacionVista']
export type CobrosPendientes = S['CobrosPendientes']
export type RetractoOperacion = S['RetractoOperacion']
export type MotivoRechazo = NonNullable<S['SolicitudResolverRetracto']['motivo']>
export type LineaRetracto = S['LineaRetracto']
export type IncidenciaVista = S['IncidenciaVista']
export type TipoIncidencia = IncidenciaVista['tipo']
export type EstadoIncidencia = IncidenciaVista['estado']
export type SolicitudEditarIncidencia = S['SolicitudEditarIncidencia']
export type OfertaConsola = S['OfertaConsola']
export type SolicitudOferta = S['SolicitudOferta']

/** 5.4 (P4): los seis grupos de la lista, el parámetro `grupo` de `GET /v1/operacion/pedidos`. */
export type GrupoPedidos = 'por_atender' | 'en_camino' | 'con_problema' | 'cerrados' | 'cancelados' | 'todos'

/**
 * La hora del servidor según la cabecera `Date` («hace {n} minutos», «Responder antes del»): nunca
 * el reloj del teléfono solo. `null` si la respuesta no la trae.
 */
const fechaDe = (r: AxiosResponse) => {
  const v = r.headers?.date
  const d = typeof v === 'string' ? new Date(v) : null
  return d && !Number.isNaN(d.getTime()) ? d : null
}
const etagDe = (r: AxiosResponse) => {
  const v = r.headers?.etag
  return typeof v === 'string' && v ? v : null
}

/** El `type` de un problema RFC 7807 es `/errores/<nombre>`. */
export const esProblema = (tipo: string | null, nombre: string) => !!tipo && (tipo === `/errores/${nombre}` || tipo.endsWith(`/${nombre}`))

/** Un campo numérico o de texto de la extensión de un problema (`minutos_espera`, `plazo_hasta`). */
export function extensionDe(error: unknown, campo: string): unknown {
  if (!isAxiosError(error) || !error.response?.data || typeof error.response.data !== 'object') return undefined
  return (error.response.data as Record<string, unknown>)[campo]
}

export interface ListaPedidos {
  pedidos: PedidoOperacion[]
  hayMas: boolean
  fecha: Date | null
}

/** `GET /v1/operacion/pedidos?grupo=`: los pagados del grupo, del pago más reciente al más antiguo. */
export async function listarPedidos(grupo: GrupoPedidos): Promise<ListaPedidos> {
  const r = await apiFamilia.get<S['ListaPedidosOperacion']>('/v1/operacion/pedidos', { params: { grupo } })
  return { pedidos: r.data.pedidos, hayMas: r.data.hay_mas ?? false, fecha: fechaDe(r) }
}

/** C7: la referencia va en el cuerpo, nunca en la URL. Sin resultado, una lista vacía. */
export async function buscarPedido(referencia: string): Promise<ListaPedidos> {
  const r = await apiFamilia.post<S['ListaPedidosOperacion']>('/v1/operacion/pedidos/buscar', { referencia })
  return { pedidos: r.data.pedidos, hayMas: false, fecha: fechaDe(r) }
}

/** El detalle, con la hora del servidor. El servidor lo registra como `operacion.pedido_ver` (C9). */
export async function verPedido(id: string): Promise<{ pedido: PedidoDetalle; fecha: Date | null }> {
  const r = await apiFamilia.get<PedidoDetalle>(`/v1/operacion/pedidos/${id}`)
  return { pedido: r.data, fecha: fechaDe(r) }
}

export async function verCobro(id: string): Promise<CobroPedido> {
  return (await apiFamilia.get<CobroPedido>(`/v1/operacion/pedidos/${id}/cobro`)).data
}

const RUTA_ACCION: Record<AccionPedido, string> = {
  en_camino: 'en-camino',
  entregado: 'entregado',
  no_entregado: 'no-entregado',
  cancelar_con_devolucion: 'cancelar-con-devolucion',
}

/** 6.5: la acción del pedido. 409 `estado-pedido` o `no-cancelable`; 503 al cancelar sin Transbank. */
export async function hacerAccion(id: string, accion: AccionPedido): Promise<void> {
  await apiFamilia.post(`/v1/operacion/pedidos/${id}/${RUTA_ACCION[accion]}`, null)
}

/** 6.4: el código de retiro, una sola vez (201, `no-store`), con la hora del servidor para su vencimiento. */
export async function generarCodigo(parteId: string): Promise<{ codigo: CodigoGenerado; fecha: Date | null }> {
  const r = await apiFamilia.post<CodigoGenerado>(`/v1/operacion/partes/${parteId}/codigo`, null)
  return { codigo: r.data, fecha: fechaDe(r) }
}

export async function cobrosPendientes(): Promise<{ cobros: CobrosPendientes; fecha: Date | null }> {
  const r = await apiFamilia.get<CobrosPendientes>('/v1/operacion/cobros/pendientes')
  return { cobros: r.data, fecha: fechaDe(r) }
}

/** `GET /v1/operacion/retractos`: los que esperan respuesta. */
export async function listarRetractos(): Promise<{ retractos: RetractoOperacion[]; fecha: Date | null }> {
  const r = await apiFamilia.get<S['ListaRetractosOperacion']>('/v1/operacion/retractos')
  return { retractos: r.data.retractos, fecha: fechaDe(r) }
}

export async function verRetracto(id: string): Promise<RetractoOperacion> {
  return (await apiFamilia.get<RetractoOperacion>(`/v1/operacion/retractos/${id}`)).data
}

/** 8.4: «Devolver» sin motivo; «No devolver» (`rechazar`) con uno de la lista cerrada (C24). */
export async function resolverRetracto(id: string, decision: 'devolver' | 'rechazar', motivo: MotivoRechazo | null): Promise<RetractoOperacion> {
  const cuerpo = decision === 'rechazar' ? { decision, motivo } : { decision }
  return (await apiFamilia.post<RetractoOperacion>(`/v1/operacion/retractos/${id}/resolver`, cuerpo)).data
}

/** 8.5 (D-81-9): el correo de quien lo pidió, solo en el cuerpo. 422 `solicitante-invalido`, 409 `fuera-de-plazo`. */
export async function registrarRetractoPorCorreo(pedidoId: string, correo: string, lineas: LineaRetracto[]): Promise<RetractoOperacion> {
  return (await apiFamilia.post<RetractoOperacion>(`/v1/operacion/pedidos/${pedidoId}/retractos`, { lineas, correo_solicitante: correo })).data
}

export async function listarIncidencias(estado: EstadoIncidencia | null): Promise<IncidenciaVista[]> {
  const r = await apiFamilia.get<S['ListaIncidencias']>('/v1/operacion/incidencias', estado ? { params: { estado } } : {})
  return r.data.incidencias
}

/** El `If-Match` de una incidencia: el `ETag` de la respuesta o, desde la lista, `"i{version}"` (P7). */
export const etagIncidencia = (i: IncidenciaVista) => `"i${i.version}"`

export async function verIncidencia(id: string): Promise<{ incidencia: IncidenciaVista; etag: string }> {
  const r = await apiFamilia.get<IncidenciaVista>(`/v1/operacion/incidencias/${id}`)
  return { incidencia: r.data, etag: etagDe(r) ?? etagIncidencia(r.data) }
}

/** 9.3: solo en un pedido pagado (C12). Sin asignarla: quien opera la toma con «Pasar a en gestión». */
export async function crearIncidencia(pedidoId: string, tipo: TipoIncidencia, descripcion: string): Promise<IncidenciaVista> {
  return (await apiFamilia.post<IncidenciaVista>(`/v1/operacion/pedidos/${pedidoId}/incidencias`, { tipo, descripcion, asignarme: false })).data
}

/** 9.3: con `If-Match` obligatorio. 412 `version-desactualizada`, 409 `incidencia-resuelta`, 422 `falta-resolucion`. */
export async function editarIncidencia(id: string, cambios: SolicitudEditarIncidencia, etag: string): Promise<{ incidencia: IncidenciaVista; etag: string }> {
  const r = await apiFamilia.patch<IncidenciaVista>(`/v1/operacion/incidencias/${id}`, cambios, { headers: { 'If-Match': etag } })
  return { incidencia: r.data, etag: etagDe(r) ?? etagIncidencia(r.data) }
}

export async function verCatalogo(): Promise<OfertaConsola[]> {
  return (await apiFamilia.get<S['CatalogoConsola']>('/v1/operacion/catalogo')).data.ofertas
}

/** 11.3 (C1 a C4): solo un comercio ficticio, con `If-Match` (la `version` de la oferta). 409 `comercio-real`, 412. */
export async function cambiarOferta(id: string, cambios: SolicitudOferta, version: string): Promise<OfertaConsola> {
  return (await apiFamilia.patch<OfertaConsola>(`/v1/operacion/ofertas/${id}`, cambios, { headers: { 'If-Match': version } })).data
}

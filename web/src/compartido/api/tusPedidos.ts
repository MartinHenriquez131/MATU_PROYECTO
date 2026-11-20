// «Tus pedidos» (MATU-92, capa 3; contrato docs/api/openapi.json y decisiones 436 a 448 de
// docs/api/README.md): la lista de los pedidos pagados de una persona, el seguimiento de uno, los
// productos para devolver (R3) y cancelar un pedido pagado (R15).
//
// - Lo que se puede hacer lo decide el servidor (`puede_cancelar`, `puede_arrepentirse` y su motivo,
//   C7): la pantalla no lo deduce del rol.
// - Sin interfaz optimista (C10): arrepentirse y cancelar esperan la respuesta.
// - Las dos escrituras llevan `Idempotency-Key` (C8). La crea quien llama, una por intento, y la
//   reutiliza en el reintento después de un error de red. Vive solo en la memoria de la página.
// - Nada de esto va a localStorage, sessionStorage, la URL ni `history.state`.
import { apiFamilia } from './sesion'
import type { components } from './familia.openapi'

type S = components['schemas']

export type FilaPedido = S['PedidoPagadoFila']
export type FilaObservador = S['PedidoPagadoFilaObservador']
/** MATU-116 (C5): la fila del observador en un pedido que pagó, la de quien paga con `vista: 'pagaste'`. */
export type FilaPagaste = S['PedidoPagadoFilaPagaste']
export type ListaPedidos = S['ListaPedidosPagados'] | S['ListaPedidosPagadosObservador']
export type EstadoFamilia = FilaPedido['estado']
export type Seguimiento = S['SeguimientoPedido'] | S['SeguimientoPedidoPagaste']
export type ParteDelPedido = S['ParteDelPedido']
export type Retractos = S['RetractosDelPedido']
export type LineaParaRetracto = S['LineaParaRetracto']
export type RetractoFamilia = S['RetractoVistaFamilia']
export type LineaRetracto = S['LineaRetracto']
export type EstadoPedidoVista = S['EstadoPedidoVista']
export type MotivoCancelar = FilaPedido['cancelar_motivo']
export type MotivoArrepentirse = FilaPedido['arrepentirse_motivo']
/** MATU-128: una cosa que anotó el equipo de MATU, con los siete campos del contrato y nada más. */
export type CosaAnotada = S['CosaAnotadaVista']

/**
 * La fila de quien ve el pago trae la referencia; la del observador, no (decisión 436). MATU-116 (C10):
 * en la lista del observador cada fila trae `vista`, y la forma la decide ese dato del servidor, nunca
 * el rol en memoria: `pagaste` es la fila de quien paga y `se_informa` la de MATU-113.
 */
export const esFilaCompleta = (f: FilaPedido | FilaObservador | FilaPagaste): f is FilaPedido | FilaPagaste =>
  'vista' in f ? f.vista === 'pagaste' : 'referencia' in f && typeof (f as FilaPedido).referencia === 'string'

/** MATU-116 (T1): la fila que la API marca como pagada por quien lee. Solo la trae la lista del observador. */
export const esFilaPagaste = (f: FilaPedido | FilaObservador | FilaPagaste): f is FilaPagaste => 'vista' in f && f.vista === 'pagaste'

const enc = encodeURIComponent

/** Las filas por página. El contrato admite de 1 a 100 y da 20 por omisión. */
export const POR_PAGINA = 20

/**
 * `GET /v1/personas-cuidadas/{id}/pedidos` (decisión 436): del más reciente al más antiguo, con
 * cursor opaco. Lo vencido no viene (C27): la pantalla no filtra nada.
 */
export async function listarPedidos(personaId: string, cursor: string | null = null, limite = POR_PAGINA): Promise<ListaPedidos> {
  const params: Record<string, string | number> = { limite }
  if (cursor) params.cursor = cursor
  return (await apiFamilia.get<ListaPedidos>(`/v1/personas-cuidadas/${enc(personaId)}/pedidos`, { params })).data
}

/** `GET /v1/pedidos/{id}/seguimiento` (decisión 438). El observador recibe 404, salvo en un pedido que pagó (MATU-116). */
export async function leerSeguimiento(pedidoId: string): Promise<Seguimiento> {
  return (await apiFamilia.get<Seguimiento>(`/v1/pedidos/${enc(pedidoId)}/seguimiento`)).data
}

/**
 * `GET /v1/pedidos/{id}/lo-que-paso` (MATU-128, decisión 484), con `X-Grupo-Id` del interceptor. Quién
 * la recibe lo decide el servidor con quién pagó el pedido, nunca el rol: 404 a quien no lo pagó, 503
 * si hay algo anotado y falta la clave. Ordenadas por `anotado_en`; vacía si no hay nada anotado.
 */
export async function leerLoQuePaso(pedidoId: string): Promise<CosaAnotada[]> {
  return (await apiFamilia.get<S['LoQuePasoDelPedido']>(`/v1/pedidos/${enc(pedidoId)}/lo-que-paso`)).data.lo_que_paso
}

/** `GET /v1/pedidos/{id}/retractos` (decisión 442). Solo de un pedido entregado: si no, 404. */
export async function leerRetractos(pedidoId: string): Promise<Retractos> {
  return (await apiFamilia.get<Retractos>(`/v1/pedidos/${enc(pedidoId)}/retractos`)).data
}

/** `POST /v1/pedidos/{id}/retractos` (decisiones 444, 445 y 447): 201 con el retracto y su monto. Sin motivo (C9). */
export async function pedirRetracto(pedidoId: string, lineas: LineaRetracto[], clave: string): Promise<RetractoFamilia> {
  const cuerpo: S['SolicitudRetracto'] = { lineas }
  return (await apiFamilia.post<RetractoFamilia>(`/v1/pedidos/${enc(pedidoId)}/retractos`, cuerpo, { headers: { 'Idempotency-Key': clave } })).data
}

/** `POST /v1/pedidos/{id}/cancelar-con-devolucion` (decisiones 444 y 446). 409 `estado-pedido` si ya se canceló. */
export async function cancelarConDevolucion(pedidoId: string, clave: string): Promise<EstadoPedidoVista> {
  return (await apiFamilia.post<EstadoPedidoVista>(`/v1/pedidos/${enc(pedidoId)}/cancelar-con-devolucion`, undefined, { headers: { 'Idempotency-Key': clave } })).data
}

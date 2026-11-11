// El pedido de la familia (MATU-61, RF-21, ADR-027, capa 3; contrato docs/api/openapi.json y
// decisiones 188 a 221 de docs/api/README.md). El carrito vive en el servidor como borrador (C18):
// nada del pedido, la dirección ni el teléfono va a localStorage, sessionStorage, la URL ni
// `history.state`. El id del pedido solo viaja en las rutas de la API, nunca en la del navegador.
//
// Sin interfaz optimista en lo que mueve dinero: confirmar, cambiar y cancelar esperan la respuesta.
// Los POST llevan `Idempotency-Key`, una por toque (decisión 195); los PUT, `If-Match` con el `etag`.
import { isAxiosError } from 'axios'
import { apiFamilia } from './sesion'
import { apiPublica } from './politica'
import type { components } from './familia.openapi'

type S = components['schemas']

export type PedidoVista = S['PedidoVista']
export type PedidoObservador = S['PedidoVistaObservador']
/** Lo que ve cada rol: `PedidoVista` (admin, cuidador y pagador) o la del observador, sin entrega ni resumen. */
export type Pedido = PedidoVista | PedidoObservador
export type LineaPedido = S['LineaPedido']
export type LineaSalida = S['LineaSalida']
export type Regla = S['Regla']
export type LineaSolicitud = S['LineaSolicitud']
export type ReglaProducto = S['ReglaProducto']
export type EntregaVista = S['EntregaVista']
export type DireccionVista = S['DireccionVista']
/** `etiqueta` y `region` tienen valor por omisión: la pantalla no los pide (diseño 8.2). */
export type DireccionEntrada = Omit<S['DireccionEntrada'], 'etiqueta' | 'region'> & Partial<Pick<S['DireccionEntrada'], 'etiqueta' | 'region'>>
export type CondicionesPedido = S['CondicionesPedidoVista']

/** La vista completa trae `etag`, `entrega` y `resumen`; la del observador no (decisión 198). */
export const esVistaCompleta = (p: Pedido): p is PedidoVista => 'etag' in p && typeof (p as PedidoVista).etag === 'string'

/** Una clave por toque: un UUID v4 cumple el formato de la decisión 195 (16 a 64 de `[A-Za-z0-9_-]`). */
export const nuevaClave = () => crypto.randomUUID()

const enc = encodeURIComponent
const rutaPersona = (personaId: string) => `/v1/personas-cuidadas/${enc(personaId)}`
const rutaPedido = (pedidoId: string) => `/v1/pedidos/${enc(pedidoId)}`

/**
 * `GET …/pedido-en-curso` (decisión 197, C4): el pedido sin pagar de la persona, con la vista de su
 * rol, o `null` si no tiene uno (404). Con la capa 3 apagada la ruta tampoco existe: quien llama sabe
 * por el catálogo si la capa está encendida.
 */
export async function leerPedidoEnCurso(personaId: string): Promise<Pedido | null> {
  try {
    return (await apiFamilia.get<Pedido>(`${rutaPersona(personaId)}/pedido-en-curso`)).data
  } catch (x) {
    if (isAxiosError(x) && x.response?.status === 404) return null
    throw x
  }
}

/** `POST …/pedidos` (decisión 196): el borrador con sus líneas. 409 `pedido-abierto` si ya hay uno. */
export async function crearPedido(personaId: string, lineas: LineaSolicitud[]): Promise<PedidoVista> {
  const cuerpo: S['SolicitudPedido'] = { lineas }
  return (await apiFamilia.post<PedidoVista>(`${rutaPersona(personaId)}/pedidos`, cuerpo, { headers: { 'Idempotency-Key': nuevaClave() } })).data
}

/** `PUT …/lineas` (decisión 199): reemplaza todas las líneas del borrador. Admite `[]`. */
export async function reemplazarLineas(pedidoId: string, lineas: LineaSolicitud[], etag: string): Promise<PedidoVista> {
  const cuerpo: S['SolicitudLineas'] = { lineas }
  return (await apiFamilia.put<PedidoVista>(`${rutaPedido(pedidoId)}/lineas`, cuerpo, { headers: { 'If-Match': etag } })).data
}

/** `PUT …/reglas-faltante` (decisión 200, RF-21): `otro_comercio` o `quitar`, nunca otra marca. */
export async function reemplazarReglas(pedidoId: string, reglas: ReglaProducto[], etag: string): Promise<PedidoVista> {
  const cuerpo: S['SolicitudReglasFaltante'] = { reglas }
  return (await apiFamilia.put<PedidoVista>(`${rutaPedido(pedidoId)}/reglas-faltante`, cuerpo, { headers: { 'If-Match': etag } })).data
}

/**
 * `POST …/confirmar` (decisiones 201 a 205, C1): desde `borrador`, `vencido` o un total vigente, que
 * se reemplaza con 15 minutos nuevos. El teléfono escrito viaja aquí; sin él, el que ya tenía el
 * pedido o el celular verificado de quien confirma.
 */
export async function confirmarPedido(pedidoId: string, telefono: string | null): Promise<PedidoVista> {
  const cuerpo: S['SolicitudConfirmar'] = telefono ? { telefono_contacto: telefono } : {}
  return (await apiFamilia.post<PedidoVista>(`${rutaPedido(pedidoId)}/confirmar`, cuerpo, { headers: { 'Idempotency-Key': nuevaClave() } })).data
}

/** `PUT …/contacto` (decisión 203): el teléfono desde el resumen, sin tocar el total ni el plazo. */
export async function cambiarContacto(pedidoId: string, telefono: string, etag: string): Promise<PedidoVista> {
  const cuerpo: S['SolicitudContacto'] = { telefono_contacto: telefono }
  return (await apiFamilia.put<PedidoVista>(`${rutaPedido(pedidoId)}/contacto`, cuerpo, { headers: { 'If-Match': etag } })).data
}

/** `POST …/cambiar` (decisión 218, C1 y C9): de `total_confirmado` o `vencido` a `borrador`, sin perder las líneas. */
export async function volverABorrador(pedidoId: string): Promise<PedidoVista> {
  return (await apiFamilia.post<PedidoVista>(`${rutaPedido(pedidoId)}/cambiar`, undefined, { headers: { 'Idempotency-Key': nuevaClave() } })).data
}

/** `POST …/cancelar` (decisión 206): sin cuerpo y sin costo. 409 `estado-pedido` si ya se canceló. */
export async function cancelarPedido(pedidoId: string): Promise<PedidoVista> {
  return (await apiFamilia.post<PedidoVista>(`${rutaPedido(pedidoId)}/cancelar`, undefined, { headers: { 'Idempotency-Key': nuevaClave() } })).data
}

/** El pedido vigente de un 412 `version-desactualizada` (`actual`). */
export function leerConflictoPedido(error: unknown): PedidoVista | null {
  if (!isAxiosError(error) || error.response?.status !== 412) return null
  const actual = (error.response.data as { actual?: PedidoVista } | undefined)?.actual
  return actual && Array.isArray(actual.lineas) ? actual : null
}

/** El `pedido_id` de un 409 `pedido-abierto` (decisión 196). */
export function pedidoAbiertoDe(error: unknown): string | null {
  if (!isAxiosError(error) || error.response?.status !== 409) return null
  const id = (error.response.data as { pedido_id?: unknown } | undefined)?.pedido_id
  return typeof id === 'string' ? id : null
}

// ---------------------------------------------------------------- la dirección de la persona (D4, C6, C8)

/**
 * `PUT …/direccion` (decisiones 189 a 191): siempre condicional. Con `etag`, `If-Match`; sin él (la
 * persona no tiene una), `If-None-Match: *`. No pide la autorización de pedidos (C8).
 */
export async function guardarDireccion(personaId: string, direccion: DireccionEntrada, etag: string | null): Promise<DireccionVista> {
  const r = await apiFamilia.put<DireccionVista>(`${rutaPersona(personaId)}/direccion`, direccion, {
    headers: etag ? { 'If-Match': etag } : { 'If-None-Match': '*' },
  })
  return r.data
}

/** `DELETE …/direccion` (decisión 216): 204. 404 si ya no había una; 412 con `actual` si cambió. */
export async function vaciarDireccion(personaId: string, etag: string): Promise<void> {
  await apiFamilia.delete(`${rutaPersona(personaId)}/direccion`, { headers: { 'If-Match': etag } })
}

/** La dirección vigente de un 412 de la dirección. */
export function leerConflictoDireccion(error: unknown): DireccionVista | null {
  if (!isAxiosError(error) || error.response?.status !== 412) return null
  const actual = (error.response.data as { actual?: DireccionVista | null } | undefined)?.actual
  return actual && typeof actual.calle === 'string' ? actual : null
}

// ---------------------------------------------------------------- las condiciones del pedido (D6)

/** `GET /v1/condiciones-pedido` (decisión 207): pública, sin sesión y sin cookies, como la política. */
export async function leerCondiciones(): Promise<CondicionesPedido> {
  return (await apiPublica.get<CondicionesPedido>('/v1/condiciones-pedido', { withCredentials: false })).data
}

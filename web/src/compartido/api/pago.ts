// El pago del pedido con Webpay Plus (MATU-62, ADR-027, capa 3; contrato docs/api/openapi.json y
// decisiones 223 a 247 de docs/api/README.md).
//
// - Sin interfaz optimista: pagar, la vuelta y el comprobante esperan la respuesta del servidor.
// - El token de Transbank, la `url` de Webpay, la `Idempotency-Key` y el resultado viven solo en la
//   memoria de la página. Nunca en localStorage, sessionStorage, la URL ni `history.state` (C18).
// - Los montos vienen del servidor, en pesos enteros. La pantalla no calcula el total.
import { isAxiosError } from 'axios'
import { apiFamilia } from './sesion'
import type { components } from './familia.openapi'

type S = components['schemas']

export type InicioPago = S['InicioPago']
export type SolicitudRetorno = S['SolicitudRetorno']
export type ResultadoRetorno = S['ResultadoRetorno']
export type ResultadoPago = ResultadoRetorno['resultado']
export type PagoVista = S['PagoVista']
export type PagoObservador = S['PagoVistaObservador']
export type Pago = PagoVista | PagoObservador
export type Comprobante = S['Comprobante']
export type Devolucion = S['Devolucion']
export type Tarjeta = S['Tarjeta']

/** La vista del observador trae solo `estado: pagado | sin_pagar` (decisión 236). */
export const esPagoCompleto = (p: Pago): p is PagoVista => 'pago_en_curso' in p

const enc = encodeURIComponent

/**
 * `POST /v1/pedidos/{id}/pagar` (decisiones 224 a 230). `If-Match` con el `etag` del pedido que se
 * mostró (nunca se cobra un total que quien paga no vio) y una `Idempotency-Key` por toque, que
 * repite solo el reintento de un 409 `idempotencia-en-curso`. El cuerpo no lleva montos.
 */
export async function pagarPedido(pedidoId: string, etag: string, condiciones: { version: string; huella: string }, clave: string): Promise<InicioPago> {
  const cuerpo: S['SolicitudPago'] = { acepta_condiciones: true, condiciones: { version: condiciones.version, huella: condiciones.huella } }
  const r = await apiFamilia.post<InicioPago>(`/v1/pedidos/${enc(pedidoId)}/pagar`, cuerpo, { headers: { 'Idempotency-Key': clave, 'If-Match': etag } })
  return r.data
}

/**
 * `POST /v1/pagos/retorno` (decisiones 231 a 235): pública, con la sesión si la hay y **sin**
 * `X-Grupo-Id` (`false` hace que Axios no la envíe y que el interceptor no la ponga). Idempotente por
 * token: se repite con el mismo cuerpo mientras el resultado sea `pendiente`.
 */
export async function enviarRetorno(cuerpo: SolicitudRetorno): Promise<ResultadoRetorno> {
  const r = await apiFamilia.post<ResultadoRetorno>('/v1/pagos/retorno', cuerpo, { headers: { 'X-Grupo-Id': false } })
  return r.data
}

/** `GET /v1/pedidos/{id}/pago` (decisión 236): el estado, las devoluciones y el comprobante, con la vista del rol. */
export async function leerPago(pedidoId: string): Promise<Pago> {
  return (await apiFamilia.get<Pago>(`/v1/pedidos/${enc(pedidoId)}/pago`)).data
}

/** `GET /v1/personas-cuidadas/{id}/pedido-pagado` (decisión 237): el último pagado, o `null` si no hay (404). */
export async function leerPedidoPagado(personaId: string): Promise<Pago | null> {
  try {
    return (await apiFamilia.get<Pago>(`/v1/personas-cuidadas/${enc(personaId)}/pedido-pagado`)).data
  } catch (x) {
    if (isAxiosError(x) && x.response?.status === 404) return null
    throw x
  }
}

/**
 * 4.5, paso 3: la navegación a Webpay. Un formulario `POST` a la `url` de Transbank con `token_ws`,
 * enviado en la misma pestaña: una navegación de página completa, sin `iframe` ni ventana nueva. El
 * token no se escribe en la dirección de MATU ni se guarda en ningún lado.
 */
export function irAWebpay(url: string, token: string) {
  const form = document.createElement('form')
  form.method = 'post'
  form.action = url
  form.target = '_self'
  form.hidden = true
  const campo = document.createElement('input')
  campo.type = 'hidden'
  campo.name = 'token_ws'
  campo.value = token
  form.appendChild(campo)
  document.body.appendChild(form)
  form.submit()
}

// La vuelta de Webpay en la memoria de la página (MATU-62, especificación 2.1, 7.1 y 11; decisiones
// 231 a 234). Solo variables de este módulo: nada va a localStorage, sessionStorage, la URL ni
// `history.state`, y todo se pierde al recargar.
//
// 1. `capturarRetorno` corre en main.tsx antes de dibujar nada: si la dirección es la `return_url`
//    (`/insumos/pedido/pago`) y trae los valores de Transbank en la query (vuelta por GET) o en el
//    fragmento (vuelta por POST, que el servidor convierte en un 303), los lee y los borra de
//    inmediato con `history.replaceState`. Así el token no queda en el historial, en una captura ni
//    en una pestaña compartida, y el «Atrás» no vuelve a una dirección con él.
// 2. La pantalla de la vuelta manda esos valores a `POST /v1/pagos/retorno` y guarda aquí el último
//    resultado: si después cambia la persona elegida (y con ella la pantalla se monta de nuevo), no
//    repite el retorno, que respondería «ya registrado».
// 3. «Ver el comprobante» (sección 8) deja aquí el pago que se va a mostrar.
import type { PagoVista, ResultadoRetorno, SolicitudRetorno } from '../compartido/api/pago'

export const RUTA_PAGO = '/insumos/pedido/pago'

/** Los cuatro campos de Transbank, con el largo máximo del contrato (`SolicitudRetorno`). */
const CAMPOS: Record<keyof SolicitudRetorno, number> = { token_ws: 128, TBK_TOKEN: 128, TBK_ORDEN_COMPRA: 26, TBK_ID_SESION: 61 }
const VALOR = /^[A-Za-z0-9_-]+$/

interface Vuelta {
  cuerpo: SolicitudRetorno
  /** `Date.now()` al llegar: «Te avisamos aquí» pregunta sola hasta 15 minutos después (7.3). */
  llegada: number
  resultado: ResultadoRetorno | null
}

let vuelta: Vuelta | null = null
let comprobante: { personaId: string; pago: PagoVista } | null = null

/** Lee los valores de Transbank de una query o un fragmento, sin nada más. `null` si no trae ninguno válido. */
export function leerValores(texto: string): SolicitudRetorno | null {
  const p = new URLSearchParams(texto.replace(/^[?#]/, ''))
  const cuerpo: SolicitudRetorno = {}
  for (const [campo, largo] of Object.entries(CAMPOS) as [keyof SolicitudRetorno, number][]) {
    const v = p.get(campo)
    if (v && v.length <= largo && VALOR.test(v)) cuerpo[campo] = v
  }
  return Object.keys(cuerpo).length ? cuerpo : null
}

/**
 * Antes de cualquier otra cosa: si la dirección es la de la vuelta y trae algo en la query o en el
 * fragmento, lo guarda en memoria (solo los campos de Transbank válidos) y deja la dirección limpia.
 */
export function capturarRetorno(loc: Location = window.location) {
  if (loc.pathname.replace(/\/+$/, '') !== RUTA_PAGO) return
  if (!loc.search && !loc.hash) return
  const cuerpo = leerValores(loc.search) ?? leerValores(loc.hash)
  window.history.replaceState(null, '', RUTA_PAGO)
  if (cuerpo) vuelta = { cuerpo, llegada: Date.now(), resultado: null }
}

export const hayVuelta = () => vuelta !== null
export const leerVuelta = (): Readonly<Vuelta> | null => vuelta
export function guardarResultado(r: ResultadoRetorno) {
  if (vuelta) vuelta = { ...vuelta, resultado: r }
}
/** La vuelta terminó (la persona salió de la pantalla): un «Ver el comprobante» posterior no la repite. */
export function olvidarVuelta() {
  vuelta = null
}

export function fijarComprobante(personaId: string, pago: PagoVista) {
  comprobante = { personaId, pago }
}
export function tomarComprobante(personaId: string | null): PagoVista | null {
  const c = comprobante && comprobante.personaId === personaId ? comprobante.pago : null
  return c
}
export function olvidarComprobante() {
  comprobante = null
}

/** Para las pruebas. */
export function olvidarTodoElPago() {
  vuelta = null
  comprobante = null
}

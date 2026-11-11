// Agregar al pedido desde el catálogo (5) y desde la lista (6), y leer los errores del pedido por su
// `type` (sección 11, nunca por `title` ni `detail`). Sin interfaz optimista: el carrito cambia con
// la respuesta de la API. Un solo pedido sin pagar por persona (C4): si no hay, se crea el borrador;
// si lo hay, se reemplazan sus líneas con `If-Match`.
import type { ProductoCatalogo } from '../compartido/api/catalogo'
import { leerFallo } from '../compartido/api/cliente'
import {
  crearPedido,
  esVistaCompleta,
  leerConflictoPedido,
  leerPedidoEnCurso,
  pedidoAbiertoDe,
  reemplazarLineas,
  type PedidoVista,
} from '../compartido/api/pedido'
import type { IntencionPedido } from './estado'
import { esTipo } from './insumosComun'
import { lineasParaGuardar } from './pedidoComun'
import { PEDIDO } from './textosPedido'

/** El 403 de los pedidos (decisión 194): sin la autorización `despacho`, o con su revisión vencida. */
export function permisoPedidoDe(x: unknown): 'sin-autorizacion' | 'revision-vencida' | null {
  const f = leerFallo(x)
  if (f.status !== 403) return null
  return esTipo(f.tipo, 'revision-vencida') ? 'revision-vencida' : 'sin-autorizacion'
}

/** 409 `estado-pedido` o 412: otra persona lo canceló, lo confirmó o lo cambió (11.2). */
export function cambioAjeno(x: unknown): boolean {
  const f = leerFallo(x)
  return f.status === 412 || (f.status === 409 && esTipo(f.tipo, 'estado-pedido'))
}

/** El pedido ya no está en borrador: no se le pueden agregar productos sin «Cambiar el pedido». */
export class PedidoNoEditable extends Error {
  constructor() {
    super('el pedido no está en borrador')
  }
}

/** Una línea de `LineaListaInsumos` ya no tiene su oferta en el catálogo. */
export class OfertaFuera extends Error {
  constructor() {
    super('oferta fuera del catálogo')
  }
}

export interface Nueva {
  producto_id: string
  oferta_id: string
  cantidad: number
}

/**
 * Agrega `nuevas` al pedido en curso de la persona. Lee el pedido justo antes (otra persona pudo
 * crearlo o cambiarlo), y reintenta una vez si se cruzó con otra (409 `pedido-abierto` o 412).
 * Devuelve el pedido y los productos que ya estaban (O4: quedan con la cantidad nueva).
 */
export async function agregarAlPedido(personaId: string, nuevas: Nueva[], productos: Map<string, ProductoCatalogo>): Promise<{ pedido: PedidoVista; yaEstaban: string[] }> {
  for (let intento = 0; ; intento++) {
    const actual = await leerPedidoEnCurso(personaId)
    if (!actual) {
      try {
        return { pedido: await crearPedido(personaId, nuevas.map(({ oferta_id, cantidad }) => ({ oferta_id, cantidad }))), yaEstaban: [] }
      } catch (x) {
        if (intento === 0 && pedidoAbiertoDe(x)) continue
        throw x
      }
    }
    if (!esVistaCompleta(actual) || actual.estado !== 'borrador') throw new PedidoNoEditable()
    const yaEstaban = nuevas.filter((n) => actual.lineas.some((l) => l.producto.id === n.producto_id)).map((n) => n.producto_id)
    const lineas = lineasParaGuardar(actual.lineas, productos, { nuevas })
    if (!lineas) throw new OfertaFuera()
    try {
      return { pedido: await reemplazarLineas(actual.id, lineas, actual.etag), yaEstaban }
    } catch (x) {
      if (intento === 0 && leerConflictoPedido(x)) continue
      throw x
    }
  }
}

/**
 * 6.4: los párrafos de la nota al llegar desde la lista: cuántos pasaron, cuáles ya estaban (O4) y
 * cuáles no están en el catálogo. Lo agregado a mano se nombra igual: no está en el catálogo.
 */
export function parrafosDeLista(i: Pick<IntencionPedido, 'agregar' | 'fuera'>, yaEstaban: string[]): string[] {
  const parrafos: string[] = []
  if (i.agregar.length) parrafos.push(PEDIDO.agregamosDeLista(i.agregar.length))
  for (const a of i.agregar) if (yaEstaban.includes(a.producto_id)) parrafos.push(PEDIDO.yaEstaba(a.nombre))
  if (i.fuera.length) parrafos.push(PEDIDO.fueraDelCatalogo(i.fuera))
  return parrafos
}

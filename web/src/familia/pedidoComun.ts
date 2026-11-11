// Funciones puras del pedido (MATU-61, especificación 6.3, 7.4, 7.5 y 9.2). Sin I/O ni reloj: las
// prueba pruebas/pedidoComun.test.ts. El pedido no calcula el total, el envío ni el vencimiento:
// la única cuenta de la pantalla es la suma «Productos» del carrito (sección 14).
import type { Catalogo, OfertaCatalogo, ProductoCatalogo } from '../compartido/api/catalogo'
import type { DireccionVista, EntregaVista, LineaPedido, LineaSolicitud, Pedido, Regla } from '../compartido/api/pedido'
import { cantidadEnTexto, sufijoCantidad, type UnidadLinea } from './textoLista'

export const CANTIDAD_MIN = 1
export const CANTIDAD_MAX = 99

/** Los productos del catálogo por id. */
export function productosDe(catalogo: Catalogo | null): Map<string, ProductoCatalogo> {
  const m = new Map<string, ProductoCatalogo>()
  for (const c of catalogo?.categorias ?? []) for (const p of c.productos) m.set(p.id, p)
  return m
}

/** O3: el comercio de una línea que viene de la lista es la primera oferta con «Hay», en el orden del catálogo, nunca por precio. */
export function primeraOferta(producto: ProductoCatalogo): OfertaCatalogo | null {
  return producto.comercios.find((o) => o.disponible) ?? producto.comercios[0] ?? null
}

export const enRango = (n: number | null): n is number => n !== null && Number.isInteger(n) && n >= CANTIDAD_MIN && n <= CANTIDAD_MAX
const acotar = (n: number) => Math.max(CANTIDAD_MIN, Math.min(CANTIDAD_MAX, n))

/** Una línea de la lista de insumos tal como se ve en pantalla (MATU-60). */
export interface LineaDeLista {
  /** El número que se ve en el campo (válido). */
  cantidad: number
  unidad: UnidadLinea
  /** Unidades por envase si la línea va en envases, o `null`. */
  envase: number | null
}

/**
 * 6.3: la cantidad que se ve en la lista, en envases del catálogo. Las unidades de la línea divididas
 * por `unidades_por_envase` del producto, hacia arriba y entre 1 y 99. Si el producto no tiene
 * envase o la unidad no coincide (ml contra unidades), pasa 1 y `exacta` es `false`.
 */
export function cantidadDesdeLista(l: LineaDeLista, producto: Pick<ProductoCatalogo, 'unidad' | 'unidades_por_envase'>): { cantidad: number; exacta: boolean } {
  const unidades = l.envase !== null && l.unidad !== 'envase' ? l.cantidad * l.envase : l.cantidad
  const porEnvase = producto.unidades_por_envase
  if (l.unidad === 'envase' || l.unidad !== producto.unidad || !Number.isFinite(porEnvase) || porEnvase <= 0) return { cantidad: 1, exacta: false }
  return { cantidad: acotar(Math.ceil(unidades / porEnvase)), exacta: true }
}

/** «6 envases de 20 unidades», el texto de «En tu lista: …» (MATU-60 4.5). */
export const enTuListaTexto = (l: LineaDeLista) => cantidadEnTexto(l.cantidad, l.unidad, l.envase)

/** 7.5 (O11 b): el sufijo de la cantidad en envases del catálogo. Sin datos del envase, «envases». */
export function sufijoDelPedido(n: number, producto: { unidad?: UnidadLinea; unidades_por_envase?: number | null }): string {
  if (!producto.unidad || !producto.unidades_por_envase || producto.unidades_por_envase <= 0) return n === 1 ? 'envase' : 'envases'
  return sufijoCantidad(n, producto.unidad, producto.unidades_por_envase)
}

/**
 * Las líneas para `PUT …/lineas`: las del pedido con su propio `oferta_id` (decisión 222: la oferta
 * del carrito, que el backend acepta aunque haya dejado de estar publicada), con `cantidades`
 * cambiadas por producto, sin `sacar` y con `nuevas` al final (o reemplazando la de su producto).
 */
export function lineasParaGuardar(
  lineas: readonly LineaPedido[],
  { cantidades = {}, sacar = null, nuevas = [] }: { cantidades?: Record<string, number>; sacar?: string | null; nuevas?: (LineaSolicitud & { producto_id: string })[] } = {},
): LineaSolicitud[] {
  const salida: LineaSolicitud[] = []
  const nuevasPorProducto = new Map(nuevas.map((n) => [n.producto_id, n]))
  for (const l of lineas) {
    if (l.producto.id === sacar) continue
    const nueva = nuevasPorProducto.get(l.producto.id)
    if (nueva) {
      // O4: un producto que ya estaba queda en una sola línea, en su comercio, con la cantidad nueva.
      salida.push({ oferta_id: l.oferta_id, cantidad: nueva.cantidad })
      nuevasPorProducto.delete(l.producto.id)
      continue
    }
    salida.push({ oferta_id: l.oferta_id, cantidad: cantidades[l.producto.id] ?? l.cantidad })
  }
  for (const n of nuevasPorProducto.values()) salida.push({ oferta_id: n.oferta_id, cantidad: n.cantidad })
  return salida
}

/** Las reglas de todo el pedido para `PUT …/reglas-faltante`, con la de un producto cambiada. */
export const reglasConCambio = (lineas: readonly LineaPedido[], productoId: string, accion: Regla) =>
  lineas.map((l) => ({ producto_id: l.producto.id, accion: l.producto.id === productoId ? accion : l.regla_faltante }))

/** «Los Aromos 123, depto 4, La Reina»: sin «depto» si no hay. */
export function direccionEnTexto(d: Pick<DireccionVista | EntregaVista, 'calle' | 'numero' | 'depto' | 'comuna'>): string {
  const depto = d.depto?.trim()
  return [`${d.calle.trim()} ${d.numero.trim()}`, depto ? `depto ${depto}` : '', d.comuna.trim()].filter(Boolean).join(', ')
}

/**
 * «+56 9 5555 0177», el formato de DISENO.md 2 para un celular en E.164 (`+56955550177`). Lo que no
 * calza (un número ya enmascarado) va tal cual.
 */
export function telefonoEnTexto(t: string): string {
  if (/[^\d\s+-]/.test(t)) return t
  const m = /^(?:56)?9(\d{4})(\d{4})$/.exec(t.replace(/\D/g, ''))
  return m ? `+56 9 ${m[1]} ${m[2]}` : t
}

/** Lo que cambió del total confirmado, para saber si la casilla se desmarca (9.5). */
export function huellaDelTotal(p: Pedido): string {
  return JSON.stringify([p.total, p.lineas.map((l) => [l.producto.id, l.cantidad, l.precio_unitario, l.comercio.id]), p.salieron.map((s) => s.producto.id)])
}

/** 9.2: cada línea con un cambio, y los que salieron. */
export const hayCambios = (p: Pedido) => p.salieron.length > 0 || p.lineas.some((l) => l.cambio && (l.cambio.precio_antes !== null || l.cambio.comercio_antes !== null))

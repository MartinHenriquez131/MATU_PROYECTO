// Reglas puras de «Tus pedidos» (MATU-92): la fecha y la hora de Chile, el plazo, la vista previa del
// monto que se devuelve y lo que se elige devolver. Sin I/O ni estado: se prueban solas.
import { fechaYHoraDeChile } from '../compartido/fechas'
import type { LineaParaRetracto, Retractos } from '../compartido/api/tusPedidos'

/** La fecha y la hora de Chile de un instante del contrato, o `null` si no es una fecha. */
export function enChile(iso: string | null | undefined): { fecha: string; hora: string } | null {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? null : fechaYHoraDeChile(d)
}

/**
 * El plazo (O6 y C19): `plazo_hasta` es el fin del día hábil en Chile, así que se muestra solo la
 * fecha. Si vence a otra hora que las 23:59, también la hora.
 */
export function plazoEnChile(iso: string | null | undefined): { fecha: string; hora: string | null } | null {
  const c = enChile(iso)
  if (!c) return null
  return { fecha: c.fecha, hora: c.hora === '23:59' ? null : c.hora }
}

/** Lo elegido para devolver, por línea: el texto del campo, tal como se escribió. */
export type Elegidas = Record<string, string>

/** El número de un campo, o `null` si está vacío o no es un entero. */
export const numeroDe = (v: string | undefined): number | null => (v === undefined || v.trim() === '' || !/^\d+$/.test(v.trim()) ? null : Number.parseInt(v, 10))

/** Si el campo de una línea está fuera de 0 a lo disponible (o vacío). */
export const fueraDeRango = (l: LineaParaRetracto, v: string | undefined) => {
  const n = numeroDe(v)
  return n === null || n < 0 || n > l.disponibles
}

/** Las líneas con una cantidad válida mayor que 0, con su cantidad. */
export function elegidas(lineas: LineaParaRetracto[], cant: Elegidas): { linea: LineaParaRetracto; cantidad: number }[] {
  return lineas.flatMap((l) => {
    const n = numeroDe(cant[l.linea_id])
    return n !== null && n > 0 && n <= l.disponibles ? [{ linea: l, cantidad: n }] : []
  })
}

/**
 * C9 (cierre del analista): las versiones de las condiciones en que el envío se devuelve en cualquier
 * retracto, una sola vez. Es la misma lista del backend (`CONDICIONES_ENVIO_SIEMPRE`,
 * payments/domain/retracto.py). Desde la 0.3, solo si se devuelve todo lo entregado.
 */
export const CONDICIONES_ENVIO_SIEMPRE: ReadonlySet<string> = new Set(['0.1', '0.2'])

/** Si un retracto anterior (pedido o devuelto, nunca el no aceptado) ya incluyó el envío. */
export const envioYaDevuelto = (datos: Pick<Retractos, 'retractos'>) => datos.retractos.some((r) => r.incluye_envio && r.estado !== 'rechazado')

/**
 * O2 y D7: la vista previa de lo que se devuelve, en pesos enteros: `cantidad × precio_pagado` de lo
 * elegido, y el envío con la regla del backend (`incluye_envio`, D-63-10):
 * - nunca si ya se devolvió;
 * - con las condiciones 0.1 o 0.2, en cualquier retracto con algo elegido;
 * - sin versión (`null`), igual que la 0.1 y la 0.2 (MATU-112 H1);
 * - desde la 0.3, solo si lo elegido completa todo lo disponible.
 * `incluye_envio_si_todo` es falso cuando el servidor ya no devolvería el envío: también manda.
 * Solo para mostrar antes de enviar: el monto que manda es el que devuelve el `POST`.
 */
export function vistaPrevia(
  datos: Pick<Retractos, 'lineas' | 'costo_envio' | 'incluye_envio_si_todo' | 'condiciones_version' | 'retractos'>,
  cant: Elegidas,
): { productos: number; conEnvio: boolean; total: number } {
  const lista = elegidas(datos.lineas, cant)
  const productos = lista.reduce((t, e) => t + e.cantidad * e.linea.precio_pagado, 0)
  const conDisponible = datos.lineas.filter((l) => l.disponibles > 0)
  const todo = conDisponible.length > 0 && conDisponible.every((l) => numeroDe(cant[l.linea_id]) === l.disponibles)
  // MATU-112 H1: un pedido sin versión de condiciones también devuelve el envío siempre, como la 0.1 y la 0.2.
  const siempre = datos.condiciones_version === null || CONDICIONES_ENVIO_SIEMPRE.has(datos.condiciones_version)
  const conEnvio = datos.incluye_envio_si_todo && !envioYaDevuelto(datos) && (siempre ? lista.length > 0 : todo)
  return { productos, conEnvio, total: productos + (conEnvio ? datos.costo_envio : 0) }
}

/**
 * 5.7: después de que otra persona pidió devolver algunos de los mismos productos, cada cantidad
 * elegida baja a lo que todavía se puede devolver. Nunca sube.
 */
export function bajarAlDisponible(lineas: LineaParaRetracto[], cant: Elegidas): Elegidas {
  const nuevas: Elegidas = {}
  for (const l of lineas) {
    if (l.disponibles <= 0) continue
    const n = numeroDe(cant[l.linea_id])
    nuevas[l.linea_id] = String(n === null ? 0 : Math.min(n, l.disponibles))
  }
  return nuevas
}

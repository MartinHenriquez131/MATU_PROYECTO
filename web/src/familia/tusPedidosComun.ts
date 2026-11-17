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
 * O2 y D7: la vista previa de lo que se devuelve, en pesos enteros: `cantidad × precio_pagado` de lo
 * elegido, y el envío si lo elegido completa todo lo que todavía se puede devolver y las condiciones
 * lo incluyen (`incluye_envio_si_todo`). Solo para mostrar antes de enviar: el monto que manda es el
 * que devuelve el `POST`.
 */
export function vistaPrevia(datos: Pick<Retractos, 'lineas' | 'costo_envio' | 'incluye_envio_si_todo'>, cant: Elegidas): { productos: number; conEnvio: boolean; total: number } {
  const lista = elegidas(datos.lineas, cant)
  const productos = lista.reduce((t, e) => t + e.cantidad * e.linea.precio_pagado, 0)
  const conDisponible = datos.lineas.filter((l) => l.disponibles > 0)
  const todo = conDisponible.length > 0 && conDisponible.every((l) => numeroDe(cant[l.linea_id]) === l.disponibles)
  const conEnvio = todo && datos.incluye_envio_si_todo
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

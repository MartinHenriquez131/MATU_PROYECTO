// Los teléfonos dentro del texto que escribió la familia (especificación MATU-23, 3.11.4). Solo
// sirve para dibujarlos sin partir: nunca cambia un carácter del texto, nunca los vuelve enlaces.
// Los dos patrones van tal cual los dejó el diseñador, probados contra las tablas de 3.11.4.

/** Celulares chilenos con o sin 56, y fijos con 56. Separadores: espacio, guion o nada. */
export const TELEFONO =
  /(?<![\d+$])(?:\+?56[ -]?(?:9[ -]?\d{4}[ -]?\d{4}|2[ -]?\d{4}[ -]?\d{4}|[3-8]\d[ -]?\d{3}[ -]?\d{4})|9[ -]?\d{4}[ -]?\d{4})(?![\d]|[.,]\d)/g

/** [1] prefijo · [2] separador tal como se escribió (espacio, guion o nada) · [3] el resto. */
export const PARTES = /^(\+?56[ -]?(?:[29]|[3-8]\d)|9)([ -]?)(.+)$/

export type Trozo = { tipo: 'texto'; texto: string } | { tipo: 'telefono'; prefijo: string; separador: string; resto: string }

/** Las partes de un número que ya calzó con `TELEFONO`. */
export function partesDeTelefono(numero: string): { prefijo: string; separador: string; resto: string } | null {
  const m = PARTES.exec(numero)
  return m ? { prefijo: m[1], separador: m[2], resto: m[3] } : null
}

/**
 * Corta una línea en texto y teléfonos. Juntar los trozos, en orden, da exactamente la línea
 * (`prefijo + separador + resto` es lo que calzó).
 */
export function trozosConTelefonos(linea: string): Trozo[] {
  const trozos: Trozo[] = []
  let desde = 0
  for (const m of linea.matchAll(TELEFONO)) {
    const partes = partesDeTelefono(m[0])
    if (!partes) continue
    const i = m.index ?? 0
    if (i > desde) trozos.push({ tipo: 'texto', texto: linea.slice(desde, i) })
    trozos.push({ tipo: 'telefono', ...partes })
    desde = i + m[0].length
  }
  if (desde < linea.length || !trozos.length) trozos.push({ tipo: 'texto', texto: linea.slice(desde) })
  return trozos
}

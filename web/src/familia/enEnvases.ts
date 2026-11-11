// MATU-84 (especificación docs/diseno/matu-84-me-quedan-envases.md v1.1, secciones 3, 4.4 y 10):
// contar lo que queda en envases enteros más unos sueltos. Funciones puras: la API sigue recibiendo
// unidades (`stock_unidades`, de 0 a 100.000), y la pantalla manda `envases × u + sueltos`. Nunca se
// guardan los envases ni los sueltos por separado.
import type { Unidad } from '../compartido/api/consumo'

export const TOTAL_MAX = 100_000
export const ENVASE_MAX = 10_000

/** D2: solo unidades y sobres se cuentan en envases. ml y g siguen como siempre. */
export const seCuentaEnEnvases = (unidad: Unidad) => unidad === 'unidad' || unidad === 'sobre'

/** D6: un envase de 1 unidad se trata como si no hubiera envase. */
export const envaseUtil = (u: number | null | undefined): number | null => (u != null && u > 1 ? u : null)

const numero = (v: string): number | null => (v.trim() === '' ? null : Number.parseInt(v, 10))

/** El envase escrito, si está de 1 a 10.000; si no, `null`. */
export function envaseValido(v: string): number | null {
  const n = numero(v)
  return n !== null && n >= 1 && n <= ENVASE_MAX ? n : null
}

/**
 * El total con los vacíos en 0, o `null` si los dos están vacíos. Sin envase válido cuenta solo los
 * sueltos (4.2: mientras el envase falta, el resultado cuenta solo los sueltos).
 */
export function totalDe(envases: string, sueltos: string, u: number | null): number | null {
  const e = numero(envases)
  const s = numero(sueltos)
  if (e === null && s === null) return null
  return (u === null ? 0 : (e ?? 0) * u) + (s ?? 0)
}

/** El tope de «Envases enteros»: ⌊100.000 / u⌋, o 100.000 sin envase. */
export const maxEnvases = (u: number | null) => (u === null ? TOTAL_MAX : Math.floor(TOTAL_MAX / u))

/**
 * De sueltos a envases (3): con el envase conocido se reparte (65 con 20 son 3 y 5); sin él, el
 * número pasa entero a sueltos y «Envases enteros» queda vacío. Vacío deja los dos vacíos.
 */
export function repartir(valor: string, u: number | null): { envases: string; sueltos: string } {
  const n = numero(valor)
  if (n === null) return { envases: '', sueltos: '' }
  if (u === null) return { envases: '', sueltos: String(n) }
  return { envases: String(Math.floor(n / u)), sueltos: String(n % u) }
}

/** De envases a sueltos (3): el campo único recibe el total, o vacío si los dos estaban vacíos. */
export function juntar(envases: string, sueltos: string, u: number | null): string {
  const t = totalDe(envases, sueltos, u)
  return t === null ? '' : String(t)
}

/**
 * El total que se muestra (1.2, 4.1 y 4.2): `null` si los dos están vacíos, o si hay envases enteros
 * y falta un envase válido, porque la cuenta no se puede hacer. Nunca «no queda nada» con envases a la vista.
 */
export function totalVisible(envases: string, sueltos: string, u: number | null): number | null {
  const e = numero(envases)
  if (u === null && e !== null && e > 0) return null
  return totalDe(envases, sueltos, u)
}

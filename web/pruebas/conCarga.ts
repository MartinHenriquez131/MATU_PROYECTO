// MATU-119: las esperas de las pruebas cuando la máquina está cargada (la suite en paralelo con otra
// suite, o el CI lento). La receta de MATU-108 (compreMeQuedan), en un solo lugar para los archivos
// que la usan. Ninguna cambia lo que se verifica: solo cuánto se espera.
import { configure, getConfig } from '@testing-library/react'
import { afterAll, beforeAll, vi } from 'vitest'

/** Lo que esperan `findBy` y `waitFor` (el valor por omisión es 1 s). */
export const ESPERA_MS = 5_000
/** El tope de cada prueba del archivo (vitest.config.ts tiene 15 s para todas). */
export const TOPE_PRUEBA_MS = 30_000

/**
 * Sube las esperas del archivo a 5 s y cada prueba a 30 s, y las restaura al terminar. Se llama una
 * vez, arriba del archivo, antes de los `describe`: el tope de cada prueba se lee al declararla.
 */
export function plazosConCarga() {
  vi.setConfig({ testTimeout: TOPE_PRUEBA_MS })
  const esperaAnterior = getConfig().asyncUtilTimeout
  beforeAll(() => configure({ asyncUtilTimeout: ESPERA_MS }))
  afterAll(() => {
    configure({ asyncUtilTimeout: esperaAnterior })
    vi.resetConfig()
  })
}

/**
 * Para buscar un aviso por su texto fuera de las regiones vivas (`RegionesVivas`). La región repite el
 * texto del aviso 50 ms después de que aparece (`anunciar`), a propósito: sin carga la búsqueda llega
 * antes y encuentra uno; con carga llega después y encuentra dos («Found multiple elements»). Así se
 * busca siempre el aviso que se ve; lo que se anuncia se verifica aparte, en la región.
 */
export const fueraDeRegiones = { ignore: 'script, style, [aria-live]' } as const

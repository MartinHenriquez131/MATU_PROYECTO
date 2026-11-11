// Se carga antes de cada archivo de prueba: los matchers de jest-dom (toBeInvalid,
// toHaveAccessibleDescription, toHaveFocus…) y la limpieza del DOM y de los anuncios entre pruebas.
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import { olvidarAnuncios } from '../src/compartido/ui/Anuncios'

// H5 del 09-11: las pantallas mueven el foco con un `setTimeout` de 0 a 80 ms que nadie cancela
// (`enfocar` y `mostrar` de Insumos, el foco tras un 422…). Si una prueba termina antes de que
// corra, el temporizador queda vivo: corre en la prueba siguiente, o después de que Vitest cierra
// jsdom y borra `document` de los globales, y entonces falla con «ReferenceError: document is not
// defined», atribuido al archivo aunque todas sus pruebas pasaron (compreMeQuedan en el CI).
// Aquí se anotan los temporizadores cortos pendientes, y después de cada prueba se espera a que
// corran sobre el DOM ya vacío (no encuentran nada y no hacen nada). Los largos (el minuto de
// «Enviar otro código») los cancela la pantalla al desmontarse y no se esperan.
const LARGO_MS = 1_000
const pendientes = new Set<unknown>()
const setTimeoutReal = globalThis.setTimeout
const clearTimeoutReal = globalThis.clearTimeout

globalThis.setTimeout = ((fn: (...a: unknown[]) => void, ms?: number, ...args: unknown[]) => {
  if (typeof fn !== 'function' || (ms ?? 0) > LARGO_MS) return setTimeoutReal(fn, ms, ...args)
  const id = setTimeoutReal(() => {
    pendientes.delete(id)
    fn(...args)
  }, ms)
  pendientes.add(id)
  return id
}) as typeof setTimeout

globalThis.clearTimeout = ((id?: Parameters<typeof clearTimeout>[0]) => {
  pendientes.delete(id)
  clearTimeoutReal(id)
}) as typeof clearTimeout

/** Espera a que corran los temporizadores cortos pendientes, también los que agendan las promesas que terminan mientras tanto. */
async function esperarTemporizadores() {
  const limite = Date.now() + 2 * LARGO_MS
  let vacios = 0
  while (vacios < 2 && Date.now() < limite) {
    await new Promise((listo) => setTimeoutReal(listo, pendientes.size ? 10 : 0))
    vacios = pendientes.size ? 0 : vacios + 1
  }
}

afterEach(async () => {
  cleanup()
  olvidarAnuncios()
  window.history.replaceState(null, '', '/')
  await esperarTemporizadores()
})

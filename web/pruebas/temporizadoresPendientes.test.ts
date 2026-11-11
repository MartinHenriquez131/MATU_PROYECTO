// H5 del 09-11: un `setTimeout` corto que la pantalla no cancela (el foco de `enfocar`) no puede
// sobrevivir a su prueba: correría en la siguiente o después de que Vitest cierra jsdom, con
// «ReferenceError: document is not defined». preparacion.ts espera a que corra. Las dos pruebas
// van en orden: la segunda comprueba lo que dejó la primera.
import { describe, expect, it } from 'vitest'
import { enfocar } from '../src/familia/insumosComun'

let corrio = false

describe('Temporizadores pendientes al terminar una prueba', () => {
  it('una prueba termina con un foco agendado y sin esperarlo', () => {
    window.setTimeout(() => {
      corrio = true
    }, 80)
    enfocar('titulo-pagina', 80)
  })

  it('antes de la prueba siguiente ya corrió, sobre el DOM vacío', () => {
    expect(corrio).toBe(true)
  })
})

// MATU-51, revisión visual (P2): la lista y el conflicto decían «5000 ml» y «2000 días» mientras la
// confirmación dice «5.000 ml». Los números de «Insumos» usan el mismo punto de miles que
// `cantidadEnTexto` (textoLista.ts). Datos sintéticos.
import { describe, expect, it } from 'vitest'
import { diasEnTexto, INSUMOS, lineaDias } from '../src/familia/textosInsumos'

describe('Punto de miles en los textos de Insumos', () => {
  it('lo que se usa, lo que quedaba y lo que queda hoy', () => {
    expect(INSUMOS.usa(5000, 1, 'ml')).toBe('Usa 5.000 ml al día.')
    expect(INSUMOS.usa(2000, 3, 'unidad')).toBe('Usa 2.000 cada 3 días.')
    expect(INSUMOS.quedaban(5000, 'ml')).toBe('Quedaban 5.000 ml el')
    expect(INSUMOS.quedanHoy(5000, 'g')).toBe('Quedan 5.000 g hoy.')
    expect(INSUMOS.quedanHoy(2000, 'sobre')).toBe('Quedan 2.000 sobres hoy.')
  })

  it('bajo 1.000, sin punto', () => {
    expect(INSUMOS.quedanHoy(1, 'sobre')).toBe('Queda 1 sobre hoy.')
    expect(INSUMOS.usa(999, 1, 'unidad')).toBe('Usa 999 al día.')
  })

  it('la cifra de los días', () => {
    expect(lineaDias(2000).cifra).toBe('2.000')
    expect(diasEnTexto(2000)).toBe('Alcanza para 2.000 días.')
    expect(lineaDias(5).cifra).toBe('5')
    expect(lineaDias(0).cifra).toBeNull()
  })
})

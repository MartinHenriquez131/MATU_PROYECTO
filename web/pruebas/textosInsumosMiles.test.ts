// MATU-51, revisión visual (P2): la lista y el conflicto decían «5000 ml» y «2000 días» mientras la
// confirmación dice «5.000 ml». Los números de «Insumos» usan el mismo punto de miles que
// `cantidadEnTexto` (textoLista.ts). Datos sintéticos.
import { describe, expect, it } from 'vitest'
import { diasEnTexto, INSUMOS, lineaDias } from '../src/familia/textosInsumos'

describe('Punto de miles en los textos de Insumos', () => {
  it('lo que se usa, lo que quedaba y lo que queda hoy', () => {
    expect(INSUMOS.usa(5000, 1, 'ml')).toBe('Usa 5.000\u00A0ml al día.')
    expect(INSUMOS.usa(2000, 3, 'unidad')).toBe('Usa 2.000 cada 3 días.')
    expect(INSUMOS.quedaban(5000, 'ml')).toBe('Quedaban 5.000\u00A0ml el')
    expect(INSUMOS.quedanHoy(5000, 'g')).toBe('Quedan 5.000\u00A0g hoy.')
    expect(INSUMOS.quedanHoy(2000, 'sobre')).toBe('Quedan 2.000\u00A0sobres hoy.')
  })

  it('bajo 1.000, sin punto', () => {
    expect(INSUMOS.quedanHoy(1, 'sobre')).toBe('Queda 1\u00A0sobre hoy.')
    expect(INSUMOS.usa(999, 1, 'unidad')).toBe('Usa 999 al día.')
  })

  it('la cifra de los días', () => {
    expect(lineaDias(2000).cifra).toBe('2.000')
    expect(diasEnTexto(2000)).toBe('Alcanza para 2.000 días.')
    expect(lineaDias(5).cifra).toBe('5')
    expect(lineaDias(0).cifra).toBeNull()
  })

  // Segunda revisión visual (P3): «5.000» al final de una línea y «ml hoy» en la siguiente. La cifra
  // y su unidad van unidas por un espacio duro; la redacción aprobada no cambia.
  it('la cifra y su unidad, con un espacio duro y nunca uno común', () => {
    for (const texto of [INSUMOS.quedanHoy(5000, 'ml'), INSUMOS.usa(15, 1, 'g'), INSUMOS.quedaban(2, 'sobre'), INSUMOS.quedanHoy(1, 'sobre')]) {
      expect(texto).toMatch(/\d\u00A0(ml|g|sobres?)\b/)
      expect(texto).not.toMatch(/\d (ml|g|sobres?)\b/)
    }
    expect(INSUMOS.quedanHoy(5000, 'ml').replace(/\u00A0/g, ' ')).toBe('Quedan 5.000 ml hoy.')
    expect(INSUMOS.usa(4, 1, 'unidad')).toBe('Usa 4 al día.')
  })
})

// H3 del 09-11 (opción B de Jorge): a 320 px con el texto al 200 %, el celular enmascarado se
// repartía por cualquier espacio. La pantalla une «+56 9» y «•••• ••37» con espacios duros (U+00A0)
// y deja un solo espacio común, entre los dos bloques. Sin tocar la API. Solo datos sintéticos.
import { describe, expect, it } from 'vitest'
import { celularEnPantalla } from '../src/familia/celularEnPantalla'

describe('celularEnPantalla', () => {
  it('convierte el formato de la API: dos bloques con espacio duro, y un solo corte posible entre ellos', () => {
    const texto = celularEnPantalla('+56 9 •••• ••37')
    expect(texto).toBe('+56 9 •••• ••37')
    expect(texto.split(' ')).toEqual(['+56 9', '•••• ••37'])
    // La redacción no cambia: solo el tipo de espacio.
    expect(texto.replace(/ /g, ' ')).toBe('+56 9 •••• ••37')
  })

  it.each([
    ['otros dígitos finales', '+56 9 •••• ••05', '+56 9 •••• ••05'],
    ['otro código de país', '+1 9 •••• ••12', '+1 9 •••• ••12'],
  ])('con %s, la misma forma', (_, entrada, salida) => {
    expect(celularEnPantalla(entrada)).toBe(salida)
  })

  it.each([
    ['vacío', ''],
    ['sin enmascarar', '+56 9 1234 5637'],
    ['sin espacios', '+569••••••37'],
    ['con un espacio de más', '+56  9 •••• ••37'],
    ['con texto después', '+56 9 •••• ••37 (sms)'],
    ['ya convertido', '+56 9 •••• ••37'],
  ])('si no tiene la forma esperada (%s), lo devuelve tal cual', (_, entrada) => {
    expect(celularEnPantalla(entrada)).toBe(entrada)
  })
})

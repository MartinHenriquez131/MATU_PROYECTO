// Revisión visual del #51, P3: en las esperas, el número y «minuto(s)» van unidos por un espacio
// duro (U+00A0) para que no queden en líneas distintas al cortar. La redacción no cambia.
import { describe, expect, it } from 'vitest'
import { CELULAR, ENTRAR, ESPERA_CONEXION, RECUPERAR } from '../src/familia/textos'
import { ESPERA } from '../src/relevo/textos'

const esperas: [string, (m: number) => string][] = [
  ['ESPERA_CONEXION.texto', ESPERA_CONEXION.texto],
  ['ENTRAR.espera', ENTRAR.espera],
  ['CELULAR.espera', CELULAR.espera],
  ['RECUPERAR.esperaCodigo', RECUPERAR.esperaCodigo],
  ['relevo ESPERA.minutos', (m) => ESPERA.minutos(m)],
]

describe('Espacio duro entre los minutos y su número', () => {
  it.each(esperas)('%s: «1\u00A0minuto» y «2\u00A0minutos», nunca con un espacio común', (_, texto) => {
    expect(texto(1)).toContain('1\u00A0minuto')
    expect(texto(2)).toContain('2\u00A0minutos')
    expect(texto(1)).not.toMatch(/\d minuto/)
    expect(texto(2)).not.toMatch(/\d minuto/)
  })

  it('la redacción aprobada no cambia: solo el espacio', () => {
    expect(ESPERA_CONEXION.texto(2).replace(/\u00A0/g, ' ')).toBe('Hubo muchos intentos desde esta conexión. Vuelve a intentarlo en 2 minutos.')
    expect(ENTRAR.espera(1).replace(/\u00A0/g, ' ')).toBe('Hubo varios intentos de entrar. Espera 1 minuto.')
    expect(CELULAR.espera(2).replace(/\u00A0/g, ' ')).toBe('Ya pediste varios códigos. Espera 2 minutos y vuelve a intentarlo.')
    expect(RECUPERAR.esperaCodigo(1).replace(/\u00A0/g, ' ')).toBe('Hubo varios intentos con ese código. Pide uno nuevo en 1 minuto.')
  })
})

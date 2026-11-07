// Revisión visual del #51, P3: en las esperas, el número y «minuto(s)» van unidos por un espacio
// duro (U+00A0) para que no queden en líneas distintas al cortar. La redacción no cambia.
import { describe, expect, it } from 'vitest'
import { CELULAR, ENTRAR, ESPERA_CONEXION, RECUPERAR } from '../src/familia/textos'
import { ESPERA, PIN } from '../src/relevo/textos'
import { armarLista, cantidadEnTexto, textoDeLista } from '../src/familia/textoLista'
import { enPantalla } from '../src/familia/textosInsumos'

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

describe('Espacio duro en los intentos del PIN (revisión visual del #53, P3)', () => {
  it('«1\u00A0intento» y «3\u00A0intentos», nunca con un espacio común', () => {
    expect(PIN.intentos(1)).toBe('1\u00A0intento')
    expect(PIN.intentos(3)).toBe('3\u00A0intentos')
    expect(PIN.intentos(3)).not.toMatch(/\d intento/)
  })
})

describe('Espacio duro tras la cifra, solo en pantalla (tercera revisión visual del #51, P3)', () => {
  it('enPantalla cambia el espacio después de cada cifra y nada más', () => {
    expect(enPantalla(cantidadEnTexto(6, 'unidad', 20))).toBe('6\u00A0envases de 20\u00A0unidades')
    expect(enPantalla(cantidadEnTexto(1200, 'unidad', null))).toBe('1.200\u00A0unidades')
    expect(enPantalla(cantidadEnTexto(2, 'ml', 250))).toBe('2\u00A0envases de 250\u00A0ml')
  })

  it('la lista que se exporta sigue con el espacio común (sección 7.2)', () => {
    const texto = textoDeLista(armarLista('2026-11-06', [{ nombre: 'Pañal adulto talla M', cantidad: 6, unidad: 'unidad', envase: 20 }]))
    expect(texto).toContain('- Pañal adulto talla M: 6 envases de 20 unidades')
    expect(texto).not.toContain('\u00A0')
  })
})

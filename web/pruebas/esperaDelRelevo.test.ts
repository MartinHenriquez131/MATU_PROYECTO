// (d) La página del relevo calcula los minutos de un 429 desde `Retry-After`, redondeados hacia
// arriba y nunca menos de 1 (lenguaje.md, sección 7.3).
import { describe, expect, it } from 'vitest'
import type { FalloApi } from '../src/compartido/api/cliente'
import { clasificar } from '../src/relevo/estados'
import { ESPERA } from '../src/relevo/textos'

const espera = (reintentarEnSegundos: number | null): FalloApi => ({
  status: 429,
  tipo: '/errores/demasiadas-peticiones',
  campos: [],
  errores: [],
  intentosRestantes: null,
  reintentarEnSegundos,
})

describe('Relevo: minutos de espera desde Retry-After', () => {
  it.each([
    [1, 1],
    [60, 1],
    [61, 2],
    [600, 10],
  ])('%i segundos son %i minutos', (segundos, minutos) => {
    expect(clasificar(espera(segundos), 'canje')).toEqual({ clase: 'estado', estado: 'espera', minutos })
  })

  it('sin la cabecera, no inventa minutos', () => {
    expect(clasificar(espera(null), 'presentacion')).toEqual({ clase: 'estado', estado: 'espera', minutos: null })
  })

  it('el texto va en singular con 1 y sin número si no hay cabecera', () => {
    // Con espacio duro entre el número y «minuto(s)» (revisión visual del #51, P3).
    expect(ESPERA.minutos(1)).toBe('Vuelve a intentarlo en 1\u00A0minuto.')
    expect(ESPERA.minutos(2)).toBe('Vuelve a intentarlo en 2\u00A0minutos.')
    expect(ESPERA.minutos(null)).toBe('Vuelve a intentarlo en unos minutos.')
  })
})

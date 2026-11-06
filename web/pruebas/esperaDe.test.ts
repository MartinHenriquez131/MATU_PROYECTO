// PR #51: el único cálculo de la espera de un 429 (compartido/api/cliente.ts). Minutos = `Retry-After`
// en segundos hacia arriba, mínimo 1. Sin la cabecera, 60 s («1 minuto», lenguaje.md 13.3).
import { describe, expect, it } from 'vitest'
import { ESPERA_SIN_CABECERA, esperaDe, minutosDeEspera, type FalloApi } from '../src/compartido/api/cliente'

const fallo = (status: number | null, reintentarEnSegundos: number | null): FalloApi => ({
  status,
  tipo: status === 429 ? '/errores/demasiadas-peticiones' : null,
  campos: [],
  errores: [],
  intentosRestantes: null,
  reintentarEnSegundos,
})

describe('minutosDeEspera', () => {
  it.each([
    [1, 1],
    [59, 1],
    [60, 1],
    [61, 2],
    [120, 2],
    [121, 3],
    [600, 10],
  ])('%i segundos son %i minutos', (segundos, minutos) => {
    expect(minutosDeEspera(segundos)).toBe(minutos)
  })
})

describe('esperaDe', () => {
  it('un 429 con Retry-After 61 espera 61 segundos y dice 2 minutos', () => {
    expect(esperaDe(fallo(429, 61))).toEqual({ segundos: 61, minutos: 2 })
  })

  it('un 429 sin Retry-After espera 60 segundos y dice 1 minuto', () => {
    expect(ESPERA_SIN_CABECERA).toBe(60)
    expect(esperaDe(fallo(429, null))).toEqual({ segundos: 60, minutos: 1 })
  })

  it.each([[422], [500], [null]])('con status %s no hay espera', (status) => {
    expect(esperaDe(fallo(status, 61))).toBeNull()
  })
})

// MATU-57 (especificación del diseñador): en modo `angosto` (texto al 200% en 320 px) la tarjeta de
// «Tu cuenta» no se desborda. La etiqueta de estado oculta su ícono (la palabra basta: el estado nunca
// va solo por color) y el número enmascarado puede partirse. jsdom no mide: se afirman las clases.
// Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Cuenta } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { TuCuenta } from '../src/familia/Cuenta'
import { responderCon } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'
import { responderPolitica } from './politicaFalsa'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa(),
}))

const CUENTA: Cuenta = {
  id: '3c9d4e20-0000-4000-8000-0000000000c2',
  nombre: 'Carmen',
  email: 'carmen@example.org',
  celular_enmascarado: '+56 9 •••• ••37',
  celular_verificado: true,
  celular_canal: 'sms',
  politica_aceptada: { version: '0.11', huella: 'a'.repeat(64), aceptada_en: '2026-11-09T15:00:00Z' },
}

describe('«Tu cuenta» en modo angosto (MATU-57)', () => {
  it.each([
    [true, 'Confirmado'],
    [false, 'Sin confirmar'],
  ])('celular_verificado=%s: la etiqueta «%s» oculta su ícono con angosto:hidden', async (verificado, palabra) => {
    responderCon(apiFamilia, { status: 200, cuerpo: { ...CUENTA, celular_verificado: verificado } })
    responderPolitica()
    render(<TuCuenta />)

    const etiqueta = await screen.findByText(palabra)
    const icono = etiqueta.querySelector('svg')
    expect(icono).not.toBeNull()
    expect(icono).toHaveClass('angosto:hidden')
  })

  it('el número de la tarjeta puede partirse en angosto y la tarjeta achica su relleno', async () => {
    responderCon(apiFamilia, { status: 200, cuerpo: CUENTA })
    responderPolitica()
    render(<TuCuenta />)

    const numero = await screen.findByText('+56 9 •••• ••37')
    // H3 del 09-11: cada bloque junto, con espacio duro; solo se corta entre «+56 9» y «•••• ••37».
    expect(numero.textContent).toBe('+56 9 •••• ••37')
    expect(numero).toHaveClass('angosto:whitespace-normal')
    expect(numero).not.toHaveClass('whitespace-nowrap')
    expect(numero.closest('dl')).toHaveClass('px-4', 'angosto:px-2')
  })
})

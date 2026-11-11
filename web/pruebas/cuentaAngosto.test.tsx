// MATU-57 (especificación del diseñador): en modo `angosto` (texto al 200% en 320 px) la tarjeta de
// «Tu cuenta» no se desborda. La etiqueta de estado oculta su ícono (la palabra basta: el estado nunca
// va solo por color) y el número enmascarado puede partirse. jsdom no mide: se afirman las clases.
// H2 del 09-11: «Confirma tu celular» tiene su propia prueba en angosto, en sus dos pasos.
// Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Cuenta } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { ConfirmarCelular, TuCuenta } from '../src/familia/Cuenta'
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

describe('«Confirma tu celular» en modo angosto (H2 del 09-11)', () => {
  const SIN_CONFIRMAR: Cuenta = { ...CUENTA, celular_verificado: false }
  const ENMASCARADO = '+56 9 •••• ••37'

  /** El texto de un botón: la celda se encoge, baja por palabras y sin guionado (H1). */
  const sinSalirse = (texto: HTMLElement) => {
    expect(texto).toHaveClass('max-w-full', 'break-words')
    expect(texto.className).not.toMatch(/hyphens|overflow-wrap:anywhere|wrap-anywhere|break-all/)
    expect(texto.parentElement).toHaveClass('min-w-0', 'grid-cols-[minmax(0,1fr)]')
    expect(texto.closest('button')).toHaveClass('max-w-full')
  }

  it('al pedir: el número puede partirse, solo entre sus dos bloques, y «Enviar código» no se sale', async () => {
    responderCon(apiFamilia, { status: 200, cuerpo: SIN_CONFIRMAR })
    render(<ConfirmarCelular />)

    const numero = await screen.findByText('+56 9 •••• ••37')
    expect(numero.tagName).toBe('P')
    expect(numero.textContent).toBe(ENMASCARADO)
    expect(numero).toHaveClass('cifras', 'angosto:whitespace-normal')
    expect(numero).not.toHaveClass('whitespace-nowrap')
    sinSalirse(screen.getByText('Enviar código'))
  })

  it('con el código enviado: el número del aviso y «¿No te llegó? Enviar otro código» no se salen', async () => {
    responderCon(apiFamilia, { status: 200, cuerpo: SIN_CONFIRMAR }, { status: 202 })
    render(<ConfirmarCelular />)
    const u = userEvent.setup({ delay: null })
    await u.click(await screen.findByRole('button', { name: 'Enviar código' }))

    const aviso = await screen.findByText(/^Te enviamos un código al/)
    const numero = aviso.querySelector('span')!
    expect(numero.textContent).toBe(ENMASCARADO)
    expect(numero).toHaveClass('angosto:whitespace-normal')
    expect(aviso).toHaveTextContent('Te enviamos un código al +56 9 •••• ••37.')

    sinSalirse(screen.getByText('¿No te llegó? Enviar otro código'))
    sinSalirse(screen.getByText('Confirmar'))
  })
})

// MATU-53 (2.1 y 4.4): con una invitación en memoria, crear la cuenta vuelve a «Te unes a…» y no a
// «Ponle nombre a tu grupo», y crear cuenta y entrar muestran la nota de arriba. Datos sintéticos.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { CrearCuenta, Entrar } from '../src/familia/Alta'
import { responderCon } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'
import { responderPolitica } from './politicaFalsa'

const INVITACION = {
  token: 'TokenSinteticoDeInvitacion0123456789abcdefghij', // pragma: allowlist secret
  presentacion: { nombre_pila_invita: 'Carmen', rol: 'cuidador', expira_en: '2026-11-20T00:30:00Z' },
  codigo: '4729',
  verificacion: { nombre_pila_invita: 'Carmen', rol: 'cuidador', expira_en: '2026-11-20T00:30:00Z', grupo: 'Familia Soto', personas: ['María'] },
}

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

beforeEach(() => {
  window.history.replaceState(null, '', '/crear-cuenta')
  responderPolitica()
})

describe('Crear la cuenta desde una invitación', () => {
  it('la nota de arriba y, al crearla, vuelve a /invitacion', async () => {
    contexto = familiaFalsa({ invitacion: INVITACION } as never)
    responderCon(apiFamilia, { status: 201, cuerpo: { id: 'x', nombre: 'Rodrigo Soto', email: 'rodrigo.prueba@example.com', access_token: 'token-sintetico' } })
    render(<CrearCuenta />)
    const nota = screen.getByText('Después de esto vuelves a la invitación de Carmen.')
    expect(nota).toBeVisible()
    // Arriba del formulario.
    expect(nota.compareDocumentPosition(document.querySelector('form')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    const u = userEvent.setup()
    await u.type(screen.getByLabelText('Tu nombre'), 'Rodrigo Soto')
    await u.type(screen.getByLabelText('Tu correo'), 'rodrigo.prueba@example.com')
    await u.type(screen.getByLabelText('Tu celular'), '+56 9 5555 0102')
    await u.type(screen.getByLabelText('Una contraseña'), 'contrasena-ejemplo') // pragma: allowlist secret
    await u.click(screen.getByRole('checkbox', { name: /Leí y acepto la política de privacidad/ }))
    await u.click(screen.getByRole('button', { name: 'Crear cuenta' }))
    await waitFor(() => expect(window.location.pathname).toBe('/invitacion'))
  })

  it('sin invitación, sin la nota', () => {
    contexto = familiaFalsa({ invitacion: null } as never)
    render(<CrearCuenta />)
    expect(screen.queryByText(/vuelves a la invitación/)).toBeNull()
  })

  it('Entrar muestra la nota', () => {
    window.history.replaceState(null, '', '/entrar')
    contexto = familiaFalsa({ invitacion: INVITACION, destino: '/invitacion' } as never)
    render(<Entrar />)
    expect(screen.getByText('Después de esto vuelves a la invitación de Carmen.')).toBeVisible()
  })
})

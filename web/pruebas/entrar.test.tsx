// Entrar (MATU-57, especificación 4): (c) el 429 se anuncia con `role="status"` y el texto de
// lenguaje.md, sección 13.3, y (d) los minutos salen de `Retry-After` redondeados hacia arriba,
// en singular con 1. Datos sintéticos.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { Entrar } from '../src/familia/Alta'
import { responderCon } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa(),
}))

async function entrarCon429(cabeceras: Record<string, string>) {
  responderCon(apiFamilia, { status: 429, cuerpo: { type: '/errores/demasiadas-peticiones', status: 429 }, cabeceras })
  render(<Entrar />)
  const u = userEvent.setup()
  await u.type(screen.getByLabelText('Tu correo'), 'ana.prueba@example.com')
  await u.type(screen.getByLabelText('Tu contraseña'), 'contrasena-ejemplo') // pragma: allowlist secret
  await u.click(screen.getByRole('button', { name: 'Entrar' }))
  return screen.findByRole('status')
}

describe('Entrar con un 429', () => {
  it('Retry-After 61 se anuncia con role status: «Espera 2 minutos.»', async () => {
    const aviso = await entrarCon429({ 'retry-after': '61' })
    expect(aviso).toHaveTextContent('Hubo varios intentos de entrar. Espera 2 minutos.')
    expect(aviso).toHaveTextContent('Recupera tu cuenta')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    // El botón espera, sin cuenta regresiva.
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeDisabled()
  })

  it('Retry-After 60 se escribe en singular: «Espera 1 minuto.»', async () => {
    const aviso = await entrarCon429({ 'retry-after': '60' })
    expect(aviso).toHaveTextContent('Hubo varios intentos de entrar. Espera 1 minuto.')
  })

  it('sin Retry-After, espera 1 minuto', async () => {
    const aviso = await entrarCon429({})
    expect(aviso).toHaveTextContent('Hubo varios intentos de entrar. Espera 1 minuto.')
  })
})

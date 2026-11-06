// Crear cuenta (especificación MATU-39, 3.2): (b) el foco va al primer campo con error, al validar
// en la pantalla y tras un 422 de la API, y (c) el error general se anuncia con `role="alert"` y
// el texto de lenguaje.md, sección 8, por la región viva urgente que existe desde el primer render
// (revisión visual del #51, P2-3). Datos sintéticos.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { CrearCuenta } from '../src/familia/Alta'
import { problema422, responderCon } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'
import { conRegiones } from './regiones'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa(),
}))

async function llenarYEnviar() {
  const u = userEvent.setup()
  await u.type(screen.getByLabelText('Tu nombre'), 'Ana Prueba')
  await u.type(screen.getByLabelText('Tu correo'), 'ana.prueba@example.com')
  await u.type(screen.getByLabelText('Tu celular'), '+56 9 5555 0137')
  await u.type(screen.getByLabelText('Una contraseña'), 'contrasena-ejemplo') // pragma: allowlist secret
  await u.click(screen.getByRole('button', { name: 'Crear cuenta' }))
}

describe('Crear cuenta', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/crear-cuenta')
  })

  it('al enviar vacío, el foco va al primer campo con error', async () => {
    const pedidas = responderCon(apiFamilia, { status: 201 })
    render(<CrearCuenta />)

    await userEvent.setup().click(screen.getByRole('button', { name: 'Crear cuenta' }))

    const nombre = screen.getByLabelText('Tu nombre')
    await waitFor(() => expect(nombre).toHaveFocus())
    expect(nombre).toHaveAccessibleDescription(expect.stringContaining('Escribe tu nombre.'))
    expect(screen.getByLabelText('Tu correo')).toBeInvalid()
    expect(pedidas).toEqual([])
  })

  it('tras un 422, el foco va al primer campo con error, en el orden de la pantalla', async () => {
    // La API nombra primero la contraseña, pero en la pantalla el correo va antes.
    const pedidas = responderCon(apiFamilia, {
      status: 422,
      cuerpo: problema422({ campo: 'contrasena', tipo: 'string_too_short' }, { campo: 'email', tipo: 'value_error' }),
    })
    render(<CrearCuenta />)

    await llenarYEnviar()

    const correo = screen.getByLabelText('Tu correo')
    await waitFor(() => expect(correo).toHaveFocus())
    expect(correo).toBeInvalid()
    expect(correo).toHaveAccessibleDescription('Revisa tu correo.')
    expect(screen.getByLabelText('Una contraseña')).toHaveAccessibleDescription(
      expect.stringContaining('La contraseña necesita entre 10 y 128 caracteres.'),
    )
    // Nunca el `mensaje` de la API.
    expect(screen.queryByText(/texto de la API/)).not.toBeInTheDocument()
    expect(pedidas).toEqual(['POST /v1/usuarios'])
  })

  it('un error del servidor se anuncia con role alert y el texto de lenguaje.md, y lo escrito sigue ahí', async () => {
    responderCon(apiFamilia, { status: 500, cuerpo: { type: '/errores/interno', status: 500 } })
    const { urgente } = conRegiones(<CrearCuenta />)

    await llenarYEnviar()

    await waitFor(() =>
      expect(urgente).toHaveTextContent('No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo. Lo que escribiste sigue aquí.'),
    )
    expect(screen.getByLabelText('Tu correo')).toHaveValue('ana.prueba@example.com')
  })
})

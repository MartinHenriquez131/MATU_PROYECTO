// PR #51 (P2-1 y P3-1 de la prueba en el teléfono): crear cuenta con el 429 del límite por IP de
// MATU-25 y con el 422 `dominio_no_permitido` de staging. Los textos van tal cual en lenguaje.md,
// sección 13.3 (aprobados por Jorge el 05-11). Fallan sin la corrección: antes, el 429 caía en el
// error general y el dominio decía «Revisa tu correo.». Datos sintéticos.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { CrearCuenta } from '../src/familia/Alta'
import { problema422, responderCon } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa(),
}))

async function llenarYEnviar() {
  const u = userEvent.setup()
  await u.type(screen.getByLabelText('Tu nombre'), 'Ana Prueba')
  await u.type(screen.getByLabelText('Tu correo'), 'ana.prueba@example.org')
  await u.type(screen.getByLabelText('Tu celular'), '+56 9 5555 0137')
  await u.type(screen.getByLabelText('Una contraseña'), 'contrasena-ejemplo') // pragma: allowlist secret
  await u.click(screen.getByRole('button', { name: 'Crear cuenta' }))
}

const demasiadas = (cabeceras: Record<string, string>) => ({
  status: 429,
  cuerpo: { type: '/errores/demasiadas-peticiones', status: 429 },
  cabeceras,
})

describe('Crear cuenta con el 429 por IP', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/crear-cuenta')
  })

  it.each<{ caso: string; cabeceras: Record<string, string>; final: string }>([
    { caso: 'Retry-After 61', cabeceras: { 'retry-after': '61' }, final: 'en 2 minutos.' },
    { caso: 'Retry-After 60', cabeceras: { 'retry-after': '60' }, final: 'en 1 minuto.' },
    { caso: 'sin Retry-After', cabeceras: {}, final: 'en 1 minuto.' },
  ])('$caso se anuncia con role status: «…$final»', async ({ cabeceras, final }) => {
    responderCon(apiFamilia, demasiadas(cabeceras))
    render(<CrearCuenta />)

    await llenarYEnviar()

    const aviso = await screen.findByRole('status')
    expect(aviso).toHaveTextContent('Espera un momento')
    expect(aviso).toHaveTextContent(`Hubo muchos intentos desde esta conexión. Vuelve a intentarlo ${final}`)
    // Nunca el error general de la conexión.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText(/Revisa tu conexión/)).not.toBeInTheDocument()
  })

  it('el botón sigue habilitado y con el foco, y lo escrito sigue ahí', async () => {
    responderCon(apiFamilia, demasiadas({ 'retry-after': '61' }))
    render(<CrearCuenta />)

    await llenarYEnviar()

    await screen.findByRole('status')
    const boton = screen.getByRole('button', { name: 'Crear cuenta' })
    expect(boton).toBeEnabled()
    expect(boton).toHaveFocus()
    expect(screen.getByLabelText('Tu correo')).toHaveValue('ana.prueba@example.org')
  })
})

describe('Crear cuenta con un correo de un dominio no permitido (staging)', () => {
  it('el texto va bajo el campo del correo, asociado, inválido y con el foco', async () => {
    responderCon(apiFamilia, { status: 422, cuerpo: problema422({ campo: 'email', tipo: 'dominio_no_permitido' }) })
    render(<CrearCuenta />)

    await llenarYEnviar()

    const correo = screen.getByLabelText('Tu correo')
    await waitFor(() => expect(correo).toHaveFocus())
    expect(correo).toHaveAttribute('aria-invalid', 'true')
    expect(correo).toHaveAccessibleDescription('En este ambiente de prueba usa un correo terminado en @example.com.')
    expect(screen.getByText('En este ambiente de prueba usa un correo terminado en @example.com.')).toBeVisible()
    expect(screen.queryByText('Revisa tu correo.')).not.toBeInTheDocument()
  })

  it('otro 422 del correo sigue diciendo «Revisa tu correo.»', async () => {
    responderCon(apiFamilia, { status: 422, cuerpo: problema422({ campo: 'email', tipo: 'value_error' }) })
    render(<CrearCuenta />)

    await llenarYEnviar()

    const correo = screen.getByLabelText('Tu correo')
    await waitFor(() => expect(correo).toHaveFocus())
    expect(correo).toHaveAccessibleDescription('Revisa tu correo.')
  })
})

// MATU-75 (especificación 2; contrato, decisiones 176 y 177): Crear cuenta con la casilla obligatoria
// de la política, la huella que se mostró y el 409 `politica-cambio`. Solo datos sintéticos.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { CrearCuenta } from '../src/familia/Alta'
import type { RespuestaFalsa } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'
import { HUELLA_DE_PRUEBA, HUELLA_NUEVA, POLITICA_DE_PRUEBA, responderPolitica } from './politicaFalsa'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa(),
}))

const CASILLA = { name: 'Leí y acepto la política de privacidad (se abre en otra pestaña).' }

/**
 * Como `responderCon`, pero guarda el cuerpo de cada `POST /v1/usuarios` y responde en orden solo a
 * esa ruta. Lo demás (entrar después del 201) responde 500: la prueba no llega tan lejos.
 */
function responderAlta(...respuestas: RespuestaFalsa[]) {
  const cuerpos: Record<string, unknown>[] = []
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const alta = config.url === '/v1/usuarios'
    const r = alta ? respuestas[Math.min(cuerpos.length, respuestas.length - 1)] : { status: 500 }
    if (alta) cuerpos.push(JSON.parse(String(config.data ?? '{}')) as Record<string, unknown>)
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return cuerpos
}

async function llenar({ marcar = true } = {}) {
  const u = userEvent.setup()
  await u.type(screen.getByLabelText('Tu nombre'), 'Ana Prueba')
  await u.type(screen.getByLabelText('Tu correo'), 'ana.prueba@example.org')
  await u.type(screen.getByLabelText('Tu celular'), '+56 9 5555 0137')
  await u.type(screen.getByLabelText('Una contraseña'), 'contrasena-ejemplo') // pragma: allowlist secret
  if (marcar) await u.click(screen.getByRole('checkbox', CASILLA))
  return u
}

const enviar = (u: ReturnType<typeof userEvent.setup>) => u.click(screen.getByRole('button', { name: 'Crear cuenta' }))

describe('Crear cuenta: la casilla de la política', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/crear-cuenta')
  })

  it('llega sin marcar, con el enlace a /privacidad en otra pestaña dentro de la etiqueta', () => {
    responderPolitica()
    render(<CrearCuenta />)

    const casilla = screen.getByRole('checkbox', CASILLA)
    expect(casilla).not.toBeChecked()
    expect(casilla).not.toBeRequired()
    const enlace = screen.getByRole('link', { name: 'política de privacidad (se abre en otra pestaña)' })
    expect(enlace).toHaveAttribute('href', '/privacidad')
    expect(enlace).toHaveAttribute('target', '_blank')
    expect(enlace).toHaveAttribute('rel', 'noopener noreferrer')
    expect(casilla.closest('label')).toContainElement(enlace)
  })

  it('el enlace de la frase lleva el área táctil en un ::after, sin relleno vertical (v0.2, sección 7)', () => {
    responderPolitica()
    render(<CrearCuenta />)
    const enlace = screen.getByRole('link', { name: 'política de privacidad (se abre en otra pestaña)' })
    const clases = enlace.className.split(/\s+/)
    // −0,875 rem arriba y abajo más la línea de 17 px: unos 51 px de alto, como un botón.
    expect(clases).toEqual(expect.arrayContaining(['relative', 'after:absolute', 'after:inset-x-0', 'after:-inset-y-3.5', "after:content-['']"]))
    // Sin `py-*`: el contorno del foco sigue al texto y no tacha los renglones vecinos.
    expect(clases.some((c) => /^py-/.test(c))).toBe(false)
  })

  it('la casilla va arriba con py-3 en la etiqueta, sin depender del ancho (v0.3, 2.4)', () => {
    responderPolitica()
    render(<CrearCuenta />)
    const casilla = screen.getByRole('checkbox', CASILLA)
    expect(casilla).toHaveClass('mt-0.5')
    const etiqueta = casilla.closest('label') as HTMLElement
    expect(etiqueta).toHaveClass('items-start', 'py-3', 'min-h-12')
    // Sin variantes de ancho: a 1280 px `MarcoAlta` mide 615 px y nunca activaba `@2xl`.
    expect([...etiqueta.classList, ...casilla.classList].some((c) => c.startsWith('@'))).toBe(false)
  })

  it('tocar el enlace no marca la casilla; tocar el texto fuera del enlace sí', async () => {
    responderPolitica()
    render(<CrearCuenta />)
    const casilla = screen.getByRole('checkbox', CASILLA)
    const enlace = screen.getByRole('link', { name: 'política de privacidad (se abre en otra pestaña)' })
    // jsdom no abre pestañas: se evita la navegación sin tocar lo que hace la etiqueta.
    enlace.addEventListener('click', (e) => e.preventDefault())

    await userEvent.click(enlace)
    expect(casilla).not.toBeChecked()

    await userEvent.click(screen.getByText(/Leí y acepto la/))
    expect(casilla).toBeChecked()
  })

  it('es obligatoria: sin marcar no se envía, el error va junto a la casilla y, si es el único, con el foco; al marcarla se va', async () => {
    responderPolitica()
    const cuerpos = responderAlta({ status: 201 })
    render(<CrearCuenta />)
    const u = await llenar({ marcar: false })

    await enviar(u)

    const casilla = screen.getByRole('checkbox', CASILLA)
    await waitFor(() => expect(casilla).toHaveFocus())
    expect(casilla).toBeInvalid()
    expect(casilla).toHaveAccessibleDescription('Para crear tu cuenta, marca que leíste la política de privacidad.')
    expect(cuerpos).toEqual([])

    await u.click(casilla)

    expect(casilla).toBeChecked()
    expect(casilla).not.toBeInvalid()
    expect(screen.queryByText('Para crear tu cuenta, marca que leíste la política de privacidad.')).not.toBeInTheDocument()
  })

  it('envía acepta_politica: true y la huella que mostró GET /v1/politica', async () => {
    const politica = responderPolitica()
    const cuerpos = responderAlta({ status: 201, cuerpo: { id: 'x', nombre: 'Ana Prueba', email: 'ana.prueba@example.org' } })
    render(<CrearCuenta />)
    const u = await llenar()

    await enviar(u)

    await waitFor(() => expect(cuerpos.length).toBeGreaterThan(0))
    expect(cuerpos[0]).toMatchObject({ acepta_politica: true, huella_politica: HUELLA_DE_PRUEBA, email: 'ana.prueba@example.org' })
    expect(politica[0]).toBe('GET /v1/politica')
  })

  it('un 422 de acepta_politica se muestra junto a la casilla', async () => {
    responderPolitica()
    responderAlta({
      status: 422,
      cuerpo: { type: '/errores/validacion', status: 422, errores: [{ campo: 'acepta_politica', tipo: 'politica_no_aceptada', mensaje: 'texto de la API' }] },
    })
    render(<CrearCuenta />)
    const u = await llenar()

    await enviar(u)

    const casilla = screen.getByRole('checkbox', CASILLA)
    await waitFor(() => expect(casilla).toHaveFocus())
    expect(casilla).toHaveAccessibleDescription('Para crear tu cuenta, marca que leíste la política de privacidad.')
    expect(screen.queryByText(/texto de la API/)).not.toBeInTheDocument()
  })

  it('409 politica-cambio: aviso atento, la casilla desmarcada y con el foco, la huella se vuelve a pedir y lo escrito sigue', async () => {
    const politica = responderPolitica({ status: 200, cuerpo: POLITICA_DE_PRUEBA }, { status: 200, cuerpo: { ...POLITICA_DE_PRUEBA, huella: HUELLA_NUEVA } })
    const cuerpos = responderAlta(
      { status: 409, cuerpo: { type: '/errores/politica-cambio', title: 'Conflicto', status: 409, detail: 'DETAIL', errores: [] } },
      { status: 201, cuerpo: { id: 'x', nombre: 'Ana Prueba', email: 'ana.prueba@example.org' } },
    )
    render(<CrearCuenta />)
    const u = await llenar()

    await enviar(u)

    const titulo = await screen.findByText('Actualizamos la política de privacidad.')
    // P2 de la revisión visual (v0.2, 2.5): en modo angosto el ícono va en la línea del título, así
    // «Actualizamos» usa todo el ancho y no se parte por dentro a 320 px con el texto al 200 %.
    const enLinea = [...titulo.querySelectorAll('span')].find((e) => e.classList.contains('angosto:inline-flex'))
    expect(enLinea?.querySelector('svg')).not.toBeNull()
    expect(screen.getByText('Cambió mientras creabas tu cuenta. Léela de nuevo y vuelve a marcar la casilla.')).toBeInTheDocument()
    const casilla = screen.getByRole('checkbox', CASILLA)
    expect(casilla).not.toBeChecked()
    await waitFor(() => expect(casilla).toHaveFocus())
    await waitFor(() => expect(politica).toHaveLength(2))
    expect(screen.getByLabelText('Tu correo')).toHaveValue('ana.prueba@example.org')
    // No es el aviso del correo registrado.
    expect(screen.queryByText('Ese correo ya tiene una cuenta')).not.toBeInTheDocument()

    // Vuelve a marcar y a enviar: va la huella nueva.
    await u.click(casilla)
    await enviar(u)

    await waitFor(() => expect(cuerpos).toHaveLength(2))
    expect(cuerpos[1]).toMatchObject({ acepta_politica: true, huella_politica: HUELLA_NUEVA })
  })

  it('el 409 email-registrado sigue mostrando su aviso', async () => {
    responderPolitica()
    responderAlta({ status: 409, cuerpo: { type: '/errores/email-registrado', status: 409 } })
    render(<CrearCuenta />)
    const u = await llenar()

    await enviar(u)

    expect(await screen.findByText('Ese correo ya tiene una cuenta')).toBeInTheDocument()
    expect(screen.queryByText('Actualizamos la política de privacidad.')).not.toBeInTheDocument()
    expect(screen.getByRole('checkbox', CASILLA)).toBeChecked()
  })

  it('sin la política al abrir ni al enviar, la cuenta no se envía sin huella (decisión 182): error general, la casilla como estaba, y al reintentar va la huella', async () => {
    const caida = { status: 503, cuerpo: { type: '/errores/servicio-no-disponible', status: 503 } }
    // Al abrir: 503. Justo antes de enviar: 503. Al reintentar: la política llega.
    const politica = responderPolitica(caida, caida, { status: 200, cuerpo: POLITICA_DE_PRUEBA })
    const cuerpos = responderAlta({ status: 201, cuerpo: { id: 'x', nombre: 'Ana Prueba', email: 'ana.prueba@example.org' } })
    render(<CrearCuenta />)
    const u = await llenar()

    await enviar(u)

    expect(await screen.findByText(/Lo que escribiste sigue aquí/)).toBeInTheDocument()
    expect(politica).toEqual(['GET /v1/politica', 'GET /v1/politica'])
    expect(cuerpos).toEqual([])
    expect(screen.getByRole('checkbox', CASILLA)).toBeChecked()
    expect(screen.getByLabelText('Tu correo')).toHaveValue('ana.prueba@example.org')

    // El reintento es el mismo botón: vuelve a pedir la política y, con ella, envía la huella.
    await enviar(u)

    await waitFor(() => expect(cuerpos).toHaveLength(1))
    expect(politica).toHaveLength(3)
    expect(cuerpos[0]).toMatchObject({ acepta_politica: true, huella_politica: HUELLA_DE_PRUEBA })
  })
})

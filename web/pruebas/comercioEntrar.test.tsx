// MATU-63, especificación 2 y 4: entrar como comercio, la cuenta de familia en la consola (O1) y la
// de comercio en la app de la familia, la cuenta inactiva (403) y los errores de entrar. Solo datos
// sintéticos.
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AppComercio } from '../src/comercio/AppComercio'
import { AppFamilia } from '../src/familia/AppFamilia'
import { irA } from '../src/compartido/irA'
import { apiComercio, conRegionesVivas as conRegiones, vigilarAlmacenamiento } from './comercioFalso'
import { responderPolitica } from './politicaFalsa'

vi.mock('../src/compartido/irA', () => ({ irA: vi.fn() }))

const u = () => userEvent.setup({ delay: null })
const CLAVE = 'contrasena-ejemplo' // pragma: allowlist secret

function abrir(ruta: string) {
  window.history.replaceState(null, '', ruta)
  return conRegiones(<AppComercio />)
}

async function entrarCon(usuario: ReturnType<typeof u>) {
  await usuario.type(screen.getByLabelText('Tu correo'), 'encargado@example.com')
  await usuario.type(screen.getByLabelText('Tu contraseña'), CLAVE)
  await usuario.click(screen.getByRole('button', { name: 'Entrar' }))
}

describe('Entrar como comercio', () => {
  it('sin entrada, /comercio lleva a /comercio/entrar con su título y el distintivo del piloto', async () => {
    apiComercio({ tipo: null })
    abrir('/comercio')
    expect(await screen.findByRole('heading', { level: 1, name: 'Entrar como comercio' })).toBeVisible()
    expect(window.location.pathname).toBe('/comercio/entrar')
    expect(document.title).toBe('Entrar como comercio · MATU')
    expect(screen.getByText('Para quien atiende un comercio que trabaja con MATU.')).toBeVisible()
    expect(screen.getByText('Piloto académico')).toBeVisible()
    // 4.1: el olvido es una frase, sin enlace; a la familia, un enlace a /entrar.
    expect(screen.queryByRole('link', { name: /Olvidaste/ })).toBeNull()
    expect(screen.getByText(/¿Olvidaste tu contraseña\? Avisa a MATU:/)).toBeVisible()
    expect(screen.getByRole('link', { name: 'app de MATU para familias' })).toHaveAttribute('href', '/entrar')
  })

  it('una cuenta de comercio entra y llega a «Pedidos de hoy»; el foco va al h1', async () => {
    const almacen = vigilarAlmacenamiento()
    apiComercio({ tipo: null })
    abrir('/comercio/entrar')
    const usuario = u()
    await screen.findByRole('heading', { level: 1, name: 'Entrar como comercio' })
    apiComercio({ tipo: 'comercio' })
    await entrarCon(usuario)
    const h1 = await screen.findByRole('heading', { level: 1, name: 'Pedidos de hoy' })
    expect(window.location.pathname).toBe('/comercio')
    await waitFor(() => expect(h1).toHaveFocus())
    await waitFor(() => expect(document.title).toBe('Pedidos de hoy · Almacén El Ejemplo · MATU'))
    expect(almacen).toEqual([])
  })

  it('vuelve a la ruta pedida antes de entrar', async () => {
    apiComercio({ tipo: null })
    abrir('/comercio/productos')
    await screen.findByRole('heading', { level: 1, name: 'Entrar como comercio' })
    apiComercio({ tipo: 'comercio' })
    await entrarCon(u())
    expect(await screen.findByRole('heading', { level: 1, name: 'Tus productos' })).toBeVisible()
    expect(window.location.pathname).toBe('/comercio/productos')
  })

  it('O1: una cuenta de familia ve el aviso y no entra a la consola', async () => {
    apiComercio({ tipo: null })
    const { amable } = abrir('/comercio/entrar')
    await screen.findByRole('heading', { level: 1, name: 'Entrar como comercio' })
    const api = apiComercio({ tipo: 'familia' })
    await entrarCon(u())
    await waitFor(() => expect(amable).toHaveTextContent('Esta cuenta es de la app para familias. Para ver los pedidos de un comercio, entra con la cuenta del comercio.'))
    expect(window.location.pathname).toBe('/comercio/entrar')
    expect(api.lineas()).not.toContain('GET /v1/comercio')
  })

  it('O1: al abrir con una entrada de familia, el mismo aviso en Entrar', async () => {
    apiComercio({ tipo: 'familia' })
    abrir('/comercio')
    expect(await screen.findByText('Esta cuenta es de la app para familias.')).toBeVisible()
    expect(window.location.pathname).toBe('/comercio/entrar')
  })

  it('403 al entrar: «Esta cuenta de comercio no está activa.» con el contacto', async () => {
    apiComercio({ tipo: null })
    const { amable } = abrir('/comercio/entrar')
    await screen.findByRole('heading', { level: 1, name: 'Entrar como comercio' })
    apiComercio({ tipo: 'comercio', sobre: (l) => (l === 'GET /v1/comercio' ? { status: 403, cuerpo: { type: '/errores/comercio-inactivo', status: 403 } } : undefined) })
    await entrarCon(u())
    await waitFor(() => expect(amable).toHaveTextContent('Esta cuenta de comercio no está activa.'))
    // O2: sin el comercio, el correo de contacto de MATU (compartido/contacto.ts).
    expect(screen.getByText('Avisa a MATU: cuidaconmatu@gmail.com.')).toBeVisible()
  })

  it('401: el correo o la contraseña no coinciden, por la región urgente', async () => {
    apiComercio({ tipo: null })
    const { urgente } = abrir('/comercio/entrar')
    await screen.findByRole('heading', { level: 1, name: 'Entrar como comercio' })
    apiComercio({ tipo: null, sobre: (l) => (l === 'POST /v1/sesiones' ? { status: 401, cuerpo: { type: '/errores/credenciales-invalidas', status: 401 } } : undefined) })
    await entrarCon(u())
    await waitFor(() => expect(urgente).toHaveTextContent('El correo o la contraseña no coinciden. Revísalos y vuelve a intentarlo.'))
  })

  it('429: espera sin «pídele ayuda a alguien de tu familia» y el botón con aria-disabled', async () => {
    apiComercio({ tipo: null })
    const { amable } = abrir('/comercio/entrar')
    await screen.findByRole('heading', { level: 1, name: 'Entrar como comercio' })
    const api = apiComercio({
      tipo: null,
      sobre: (l) => (l === 'POST /v1/sesiones' ? { status: 429, cuerpo: { type: '/errores/demasiadas-peticiones', status: 429 }, cabeceras: { 'retry-after': '120' } } : undefined),
    })
    const usuario = u()
    await entrarCon(usuario)
    await waitFor(() => expect(amable.textContent?.replace(/ /g, ' ')).toBe('Hubo varios intentos de entrar. Espera 2 minutos.'))
    const boton = screen.getByRole('button', { name: 'Entrar' })
    expect(boton).toHaveAttribute('aria-disabled', 'true')
    await usuario.click(boton)
    expect(api.lineas().filter((l) => l === 'POST /v1/sesiones')).toHaveLength(1)
  })

  it('sin datos no envía: «Escribe tu correo y tu contraseña.»', async () => {
    apiComercio({ tipo: null })
    abrir('/comercio/entrar')
    await screen.findByRole('heading', { level: 1, name: 'Entrar como comercio' })
    const api = apiComercio({ tipo: null })
    await u().click(screen.getByRole('button', { name: 'Entrar' }))
    expect(screen.getByText('Escribe tu correo y tu contraseña.')).toBeVisible()
    expect(api.lineas()).toEqual([])
  })
})

describe('O1 en la app de la familia', () => {
  it('una cuenta de comercio que entra por /entrar va sola a /comercio, sin pedir los grupos', async () => {
    responderPolitica()
    apiComercio({ tipo: null })
    window.history.replaceState(null, '', '/entrar')
    conRegiones(<AppFamilia />)
    await screen.findByRole('heading', { level: 1, name: 'Entrar' })
    const api = apiComercio({ tipo: 'comercio' })
    await entrarCon(u())
    await waitFor(() => expect(irA).toHaveBeenCalledWith('/comercio'))
    expect(api.lineas()).not.toContain('GET /v1/grupos')
  })

  it('al abrir la app de la familia con una entrada de comercio, va a /comercio', async () => {
    responderPolitica()
    const api = apiComercio({ tipo: 'comercio' })
    window.history.replaceState(null, '', '/')
    conRegiones(<AppFamilia />)
    await waitFor(() => expect(irA).toHaveBeenCalledWith('/comercio', { reemplazar: true }))
    expect(api.lineas()).not.toContain('GET /v1/grupos')
  })
})

// Revisión visual del #51, P2-3: los avisos se anuncian aunque el foco siga en el botón. Llegan a
// una región viva que existía antes del aviso (main.tsx la monta en el primer render), con el título
// y el texto que se ven, sin los botones, y una sola vez: el aviso visible ya no lleva el rol.
// Fallan sin la corrección: antes la nota entraba al DOM ya con `role="status"` y su texto, y la
// región quedaba vacía. Datos sintéticos.
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { anunciar, RegionesVivas, textoParaLeer } from '../src/compartido/ui/Anuncios'
import { CrearCuenta } from '../src/familia/Alta'
import { AvisoDeLlegada } from '../src/familia/Ficha'
import { PantallaPin } from '../src/relevo/PantallaPin'
import { responderCon } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'
import { conRegiones } from './regiones'

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

async function crearCuentaCon(respuesta: Parameters<typeof responderCon>[1]) {
  responderCon(apiFamilia, respuesta)
  const regiones = conRegiones(<CrearCuenta />)
  const u = userEvent.setup()
  await u.type(screen.getByLabelText('Tu nombre'), 'Ana Prueba')
  await u.type(screen.getByLabelText('Tu correo'), 'ana.prueba@example.com')
  await u.type(screen.getByLabelText('Tu celular'), '+56 9 5555 0137')
  await u.type(screen.getByLabelText('Una contraseña'), 'contrasena-ejemplo') // pragma: allowlist secret
  await u.click(screen.getByRole('button', { name: 'Crear cuenta' }))
  return regiones
}

describe('Avisos de la app de la familia', () => {
  it('el 429 se anuncia en la región amable con título y texto, una vez, y el foco sigue en el botón', async () => {
    const { amable, urgente } = await crearCuentaCon({
      status: 429,
      cuerpo: { type: '/errores/demasiadas-peticiones', status: 429 },
      cabeceras: { 'retry-after': '61' },
    })

    await waitFor(() =>
      expect(amable.textContent).toBe('Espera un momento. Hubo muchos intentos desde esta conexión. Vuelve a intentarlo en 2\u00A0minutos.'),
    )
    // Una sola región con el rol: la nota visible no se anuncia otra vez.
    expect(screen.getAllByRole('status')).toEqual([amable])
    expect(screen.getByText('Espera un momento')).toBeVisible()
    expect(urgente).toBeEmptyDOMElement()
    expect(screen.getByRole('button', { name: 'Crear cuenta' })).toHaveFocus()
  })

  it('el 409 se anuncia sin el texto de su botón', async () => {
    const { amable } = await crearCuentaCon({ status: 409, cuerpo: { type: '/errores/email-registrado', status: 409 } })

    await waitFor(() => expect(amable.textContent).toBe('Ese correo ya tiene una cuenta. Entra con tu contraseña, o usa otro correo.'))
    expect(screen.getByRole('button', { name: 'Entrar con ese correo' })).toBeVisible()
  })

  it('el error general va a la región urgente, una vez', async () => {
    const { amable, urgente } = await crearCuentaCon({ status: 500, cuerpo: { type: '/errores/interno', status: 500 } })

    await waitFor(() =>
      expect(urgente.textContent).toBe('No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo. Lo que escribiste sigue aquí.'),
    )
    expect(screen.getAllByRole('alert')).toEqual([urgente])
    expect(amable).toBeEmptyDOMElement()
  })

  it('el aviso de llegada (guardado, conflicto resuelto) se anuncia al abrir la ficha', async () => {
    contexto = familiaFalsa({ aviso: { titulo: 'Dejaste «Su día» como lo guardó Rodrigo.' } })
    const { amable } = conRegiones(<AvisoDeLlegada />)
    contexto = familiaFalsa()

    await waitFor(() => expect(amable.textContent).toBe('Dejaste «Su día» como lo guardó Rodrigo.'))
  })
})

describe('Avisos de la página del relevo', () => {
  it('el PIN incompleto se anuncia en la región urgente y el campo sigue con el foco', async () => {
    const onCanjear = vi.fn()
    const { urgente } = conRegiones(<PantallaPin presentacion={{ nombre_pila_comparte: 'Carmen', nombre_pila: 'María' }} onCanjear={onCanjear} />)
    const u = userEvent.setup()

    await u.type(screen.getByLabelText(/PIN/), '12')
    await u.click(screen.getByRole('button', { name: 'Ver la ficha' }))

    await waitFor(() => expect(urgente.textContent).toBe('El PIN tiene 4 números. Revisa que estén todos.'))
    expect(screen.getAllByRole('alert')).toEqual([urgente])
    expect(onCanjear).not.toHaveBeenCalled()
  })
})

describe('Las regiones vivas', () => {
  it('existen vacías desde el primer render', () => {
    render(<RegionesVivas />)
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite')
    expect(screen.getByRole('alert')).toBeEmptyDOMElement()
    expect(screen.getByRole('alert')).toHaveAttribute('aria-live', 'assertive')
  })

  it('el mismo texto se vuelve a anunciar: la región se vacía y se llena de nuevo', async () => {
    render(<RegionesVivas />)
    const amable = screen.getByRole('status')
    act(() => anunciar('Guardamos los cambios.'))
    await waitFor(() => expect(amable.textContent).toBe('Guardamos los cambios.'))

    act(() => anunciar('Guardamos los cambios.'))
    expect(amable).toBeEmptyDOMElement()
    await waitFor(() => expect(amable.textContent).toBe('Guardamos los cambios.'))
  })

  it('el texto que se lee es el que se ve, sin íconos ni botones, con un punto entre título y cuerpo', () => {
    const nota = document.createElement('div')
    nota.innerHTML =
      '<svg aria-hidden="true"></svg><div><p>Espera un momento</p><div><span class="block">Hubo varios intentos.</span><a href="/x">Recupera tu cuenta</a><button>Entrar</button></div></div>'
    expect(textoParaLeer(nota)).toBe('Espera un momento. Hubo varios intentos. Recupera tu cuenta.')
  })
})

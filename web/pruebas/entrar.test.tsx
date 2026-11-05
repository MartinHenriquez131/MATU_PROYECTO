// Entrar (MATU-57, especificación 4): (c) el 429 se anuncia con `role="status"` y el texto de
// lenguaje.md, sección 13.3, y (d) los minutos salen de `Retry-After` redondeados hacia arriba,
// en singular con 1. Desde la revisión visual del #51 (P2-3), el anuncio va por la región viva
// amable que existe desde el primer render, y el aviso visible no repite el rol. Desde la del #53
// (P3), el botón espera con `aria-disabled` y conserva el foco: con `disabled` el foco caía en el
// cuerpo de la página. Datos sintéticos.
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { Entrar } from '../src/familia/Alta'
import { responderCon } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'
import { conRegiones } from './regiones'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa(),
}))

async function entrarCon429(cabeceras: Record<string, string>) {
  const pedidas = responderCon(apiFamilia, { status: 429, cuerpo: { type: '/errores/demasiadas-peticiones', status: 429 }, cabeceras })
  const regiones = conRegiones(<Entrar />)
  const u = userEvent.setup()
  await u.type(screen.getByLabelText('Tu correo'), 'ana.prueba@example.com')
  await u.type(screen.getByLabelText('Tu contraseña'), 'contrasena-ejemplo') // pragma: allowlist secret
  await u.click(screen.getByRole('button', { name: 'Entrar' }))
  await waitFor(() => expect(regiones.amable).not.toBeEmptyDOMElement())
  return { ...regiones, u, pedidas }
}

describe('Entrar con un 429', () => {
  it('Retry-After 61 se anuncia con role status: «Espera 2 minutos.»', async () => {
    const { amable, urgente } = await entrarCon429({ 'retry-after': '61' })
    expect(amable).toHaveTextContent('Hubo varios intentos de entrar. Espera 2 minutos.')
    // El enlace a recuperar sigue en el aviso visible.
    expect(screen.getByRole('link', { name: 'Recupera tu cuenta' })).toBeVisible()
    expect(urgente).toBeEmptyDOMElement()
  })

  it('el botón espera sin cuenta regresiva, conserva el foco y no vuelve a enviar', async () => {
    const { u, pedidas } = await entrarCon429({ 'retry-after': '61' })
    const boton = screen.getByRole('button', { name: 'Entrar' })
    expect(boton).toHaveAttribute('aria-disabled', 'true')
    // Sin `disabled`: el navegador le quita el foco a un botón `disabled` (jsdom no lo hace, por
    // eso se comprueba aparte; el recorrido en Chrome lo muestra).
    expect(boton).toBeEnabled()
    expect(boton).toHaveFocus()
    expect(document.activeElement).not.toBe(document.body)

    await u.click(boton)
    await u.keyboard('{Enter}')
    expect(pedidas).toEqual(['POST /v1/sesiones'])
  })

  it('Retry-After 60 se escribe en singular: «Espera 1 minuto.»', async () => {
    const { amable } = await entrarCon429({ 'retry-after': '60' })
    expect(amable).toHaveTextContent('Hubo varios intentos de entrar. Espera 1 minuto.')
  })

  it('sin Retry-After, espera 1 minuto', async () => {
    const { amable } = await entrarCon429({})
    expect(amable).toHaveTextContent('Hubo varios intentos de entrar. Espera 1 minuto.')
  })
})

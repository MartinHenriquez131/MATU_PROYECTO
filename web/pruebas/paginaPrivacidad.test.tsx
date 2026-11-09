// MATU-75 (especificación 1, condiciones del analista): /privacidad es pública. Pide `GET /v1/politica`
// sin cookies ni token, no toca la sesión de la familia, muestra la versión y la fecha, el índice, y
// el error en tono neutro cuando la política no está publicada (503). Solo datos sintéticos.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { describe, expect, it } from 'vitest'
import { apiPublica } from '../src/compartido/api/politica'
import { apiFamilia } from '../src/compartido/api/sesion'
import { PaginaPrivacidad } from '../src/privacidad/PaginaPrivacidad'
import { responderCon } from './apiFalsa'
import { POLITICA_DE_PRUEBA, responderPolitica } from './politicaFalsa'

describe('La página /privacidad', () => {
  it('pide la política sin credenciales: adaptador fetch con credentials omit, sin token ni grupo, y nada de la familia', async () => {
    // `withCredentials: false` con el adaptador `fetch` es `credentials: 'omit'`: ni la cookie del
    // mismo origen viaja. Con XMLHttpRequest, la cookie del mismo origen viajaría igual.
    expect(apiPublica.defaults.adapter).toBe('fetch')
    expect(apiPublica.defaults.withCredentials).toBe(false)
    const familia = responderCon(apiFamilia, { status: 200 })
    const vistas: InternalAxiosRequestConfig[] = []
    apiPublica.defaults.adapter = async (config) => {
      vistas.push(config)
      return { data: POLITICA_DE_PRUEBA, status: 200, statusText: '', headers: {}, config, request: {} } as AxiosResponse
    }
    render(<PaginaPrivacidad />)

    await screen.findByText('Un resumen de prueba.')
    expect(vistas.length).toBeGreaterThan(0)
    for (const c of vistas) {
      expect(`${c.method} ${c.url}`).toBe('get /v1/politica')
      expect(c.withCredentials).toBe(false)
      expect(c.headers.Authorization).toBeUndefined()
      expect(c.headers['X-Grupo-Id']).toBeUndefined()
    }
    expect(familia).toEqual([])
  })

  it('muestra el título, la versión con su fecha DD/MM/AAAA, el índice y el título del documento', async () => {
    responderPolitica()
    render(<PaginaPrivacidad />)

    expect(screen.getByRole('heading', { level: 1, name: 'Política de privacidad' })).toBeInTheDocument()
    expect(await screen.findByText(/Versión/)).toHaveTextContent('Versión 0.11 · actualizada el 09/11/2026')
    expect(document.title).toBe('Política de privacidad · MATU')
    // Los dos índices tienen los mismos enlaces: el `details` del teléfono y la columna de pantalla ancha.
    const indices = screen.getAllByRole('navigation', { name: 'Índice' })
    expect(indices).toHaveLength(2)
    for (const n of indices) {
      expect(within(n).getAllByRole('link').map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
        ['En un minuto', '#en-un-minuto'],
        ['1. Una sección', '#seccion-1'],
      ])
    }
    // Sin «Entrar», «Salir» ni ningún botón: la página solo se lee.
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('«Volver al índice» abre el índice y deja el foco en su summary', async () => {
    responderPolitica()
    const { container } = render(<PaginaPrivacidad />)
    await screen.findByText('Un resumen de prueba.')
    const indice = container.querySelector('details#indice') as HTMLDetailsElement
    expect(indice.open).toBe(false)

    await userEvent.click(screen.getAllByRole('link', { name: 'Volver al índice' })[1])

    expect(indice.open).toBe(true)
    expect(indice.querySelector('summary')).toHaveFocus()
    expect(window.location.hash).toBe('')
  })

  it('sin publicar (503): el error neutro con «Volver a intentar», el título sigue, y al reintentar abre', async () => {
    const pedidas = responderPolitica({ status: 503, cuerpo: { type: '/errores/servicio-no-disponible', status: 503 } }, { status: 200, cuerpo: POLITICA_DE_PRUEBA })
    render(<PaginaPrivacidad />)

    const error = await screen.findByText(/Revisa tu conexión/)
    expect(error.closest('[data-aviso="alert"]')).toHaveTextContent('No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo.')
    expect(screen.getByRole('heading', { level: 1, name: 'Política de privacidad' })).toBeInTheDocument()
    expect(screen.queryByText(/DETAIL|TITLE/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Volver a intentar' }))

    expect(await screen.findByText('Un resumen de prueba.')).toBeInTheDocument()
    expect(pedidas.every((p) => p === 'GET /v1/politica')).toBe(true)
  })

  it('deja el fragmento de la dirección como estaba: no lo limpia ni lo usa', async () => {
    window.history.replaceState(null, '', '/privacidad#ejemplo-tres-campos')
    responderPolitica()
    render(<PaginaPrivacidad />)
    await screen.findByText('Un resumen de prueba.')
    expect(window.location.hash).toBe('#ejemplo-tres-campos')
  })
})

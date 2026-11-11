// MATU-62 con la app de la familia entera (estado real, regla de ruta y marco): la vuelta de Webpay
// con la sesión recuperada, sin ella (7.10) y la ruta del comprobante para el observador (2.1).
// Solo datos sintéticos.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, describe, expect, it } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { AppFamilia } from '../src/familia/AppFamilia'
import { capturarRetorno, olvidarTodoElPago } from '../src/familia/vueltaPago'
import { autorizaciones, CATALOGO, CUENTA, DIRECCION, PEDIDO_ID, PERSONA_ID, type Respuesta } from './pedidoFalso'
import { GRUPO_ID, pago, retorno, TOKEN } from './pagoFalso'

const MARIA = { id: PERSONA_ID, nombre: 'María Soto', nombre_pila: 'María', nivel_apoyo: 'apoyo_parcial', direccion: DIRECCION, consentimiento: null }

afterEach(() => olvidarTodoElPago())

function apiApp(rol: Rol, { sesion = true, conSesionEnRetorno = true } = {}) {
  const pedidas: { linea: string; cabeceras: Record<string, unknown> }[] = []
  const responder = (config: InternalAxiosRequestConfig, r: Respuesta): AxiosResponse => {
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  axios.defaults.adapter = async (config) =>
    responder(config, sesion ? { status: 200, cuerpo: { access_token: 'token-sintetico', token_type: 'bearer', expires_in: 900 } } : { status: 401, cuerpo: { type: '/errores/sesion-expirada', status: 401 } })
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const linea = `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`
    pedidas.push({ linea, cabeceras: config.headers.toJSON() as Record<string, unknown> })
    const no = { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404 } }
    if (linea === 'GET /v1/grupos') return responder(config, { status: 200, cuerpo: [{ id: GRUPO_ID, nombre: 'Familia Soto', rol, puede_ver_plan: true }] })
    if (linea === `GET /v1/grupos/${GRUPO_ID}/personas-cuidadas`) return responder(config, { status: 200, cuerpo: [MARIA] })
    if (linea === 'GET /v1/catalogo') return responder(config, { status: 200, cuerpo: CATALOGO })
    if (linea === 'GET /v1/cuenta') return responder(config, { status: 200, cuerpo: CUENTA })
    if (/\/consentimientos$/.test(linea)) return responder(config, { status: 200, cuerpo: autorizaciones('vigente') })
    if (linea === 'POST /v1/pagos/retorno')
      return responder(config, { status: 200, cuerpo: conSesionEnRetorno && sesion ? retorno() : retorno({ grupo_id: null, persona_cuidada_id: null, pedido_id: null }) })
    if (linea === `GET /v1/pedidos/${PEDIDO_ID}/pago`) return responder(config, { status: 200, cuerpo: pago() })
    return responder(config, no)
  }
  return pedidas
}

function abrirApp(ruta: string) {
  window.history.replaceState(null, '', ruta)
  // Lo que hace main.tsx antes de dibujar.
  capturarRetorno()
  return render(
    <>
      <RegionesVivas />
      <AppFamilia />
    </>,
  )
}

describe('La vuelta de Webpay en la app', () => {
  it('con la sesión recuperada: la dirección limpia, «Pagaste tu pedido · MATU», el foco en el h1 y «Pedido» activa', async () => {
    const pedidas = apiApp('admin')
    abrirApp(`/insumos/pedido/pago?token_ws=${TOKEN}`)
    expect(window.location.search).toBe('')
    const h1 = await screen.findByRole('heading', { level: 1, name: 'Pagaste tu pedido' }, { timeout: 5000 })
    await waitFor(() => expect(document.title).toBe('Pagaste tu pedido · MATU'))
    await waitFor(() => expect(h1).toHaveFocus())
    expect(within(screen.getByRole('navigation', { name: 'Vistas de Insumos' })).getByRole('link', { name: 'Pedido' })).toHaveAttribute('aria-current', 'page')
    const r = pedidas.find((p) => p.linea === 'POST /v1/pagos/retorno')!
    expect(r.cabeceras.Authorization).toBe('Bearer token-sintetico')
    expect(r.cabeceras).not.toHaveProperty('X-Grupo-Id')
    expect(window.location.pathname).toBe('/insumos/pedido/pago')
  })

  it('7.10: sin la sesión, el resultado en el marco simple, sin pestañas ni montos, y «Entrar» lleva a entrar', async () => {
    apiApp('admin', { sesion: false })
    abrirApp(`/insumos/pedido/pago?token_ws=${TOKEN}`)
    expect(await screen.findByRole('heading', { level: 1, name: 'Pagaste tu pedido' }, { timeout: 5000 })).toBeVisible()
    expect(screen.getByText('Para ver el comprobante y tu pedido, entra a MATU.')).toBeVisible()
    expect(screen.queryByRole('navigation', { name: 'Vistas de Insumos' })).toBeNull()
    expect(document.body.textContent).not.toMatch(/\$/)
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    await waitFor(() => expect(window.location.pathname).toBe('/entrar'))
  })

  it('sin sesión y sin vuelta, la ruta del comprobante pide entrar', async () => {
    apiApp('admin', { sesion: false })
    abrirApp('/insumos/pedido/pago')
    await waitFor(() => expect(window.location.pathname).toBe('/entrar'), { timeout: 5000 })
  })

  it('2.1: el observador que llega al comprobante sin vuelta va a «Tu pedido»', async () => {
    apiApp('observador')
    abrirApp('/insumos/pedido/pago')
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'), { timeout: 5000 })
  })
})

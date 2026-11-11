// MATU-61 con la app de la familia entera (estado real, regla de ruta, barra y encabezado): las rutas
// del pedido con su <title> y el foco en el h1, la pestaña «Pedido» solo con la capa 3, las
// redirecciones por rol (2.1) y el cambio de persona desde el resumen (2.3). Solo datos sintéticos.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { describe, expect, it } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { AppFamilia } from '../src/familia/AppFamilia'
import { autorizaciones, CATALOGO, confirmado, CUENTA, DIRECCION, PERSONA_ID, type Respuesta } from './pedidoFalso'

const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g1'
const MARIA = { id: PERSONA_ID, nombre: 'María Soto', nombre_pila: 'María', nivel_apoyo: 'apoyo_parcial', direccion: DIRECCION, consentimiento: null }
const PEDRO = { id: '3c9d4e20-0000-4000-8000-0000000000bb', nombre: 'Pedro Rojas', nombre_pila: 'Pedro', nivel_apoyo: 'apoyo_parcial', direccion: null, consentimiento: null }

function apiApp(rol: Rol, { capa3 = true, personas = [MARIA] } = {}) {
  const pedidas: string[] = []
  const responder = (config: InternalAxiosRequestConfig, r: Respuesta): AxiosResponse => {
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  axios.defaults.adapter = async (config) => responder(config, { status: 200, cuerpo: { access_token: 'token-sintetico', token_type: 'bearer', expires_in: 900 } })
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const linea = `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`
    pedidas.push(linea)
    const no = { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404 } }
    if (linea === 'GET /v1/grupos') return responder(config, { status: 200, cuerpo: [{ id: GRUPO_ID, nombre: 'Familia Soto', rol, puede_ver_plan: true }] })
    if (linea === `GET /v1/grupos/${GRUPO_ID}/personas-cuidadas`) return responder(config, { status: 200, cuerpo: personas })
    if (linea === 'GET /v1/catalogo') return responder(config, capa3 ? { status: 200, cuerpo: CATALOGO } : no)
    if (linea === 'GET /v1/cuenta') return responder(config, { status: 200, cuerpo: CUENTA })
    if (/\/consentimientos$/.test(linea)) return responder(config, { status: 200, cuerpo: autorizaciones() })
    if (linea === `GET /v1/personas-cuidadas/${PERSONA_ID}/pedido-en-curso`) return responder(config, capa3 ? { status: 200, cuerpo: confirmado() } : no)
    if (/\/consumo/.test(linea)) return responder(config, { status: 200, cuerpo: { items: [], siguiente_cursor: null } })
    return responder(config, no)
  }
  return pedidas
}

function abrirApp(ruta: string) {
  window.history.replaceState(null, '', ruta)
  return render(
    <>
      <RegionesVivas />
      <AppFamilia />
    </>,
  )
}
const pestanas = () => within(screen.getByRole('navigation', { name: 'Vistas de Insumos' }))

describe('El pedido en la app de la familia', () => {
  it('admin en /insumos/pedido: «Tu pedido · MATU», Insumos activa, «Pedido» al final y el foco en el h1', async () => {
    const pedidas = apiApp('admin')
    abrirApp('/insumos/pedido')
    const h1 = await screen.findByRole('heading', { level: 1, name: 'Tu pedido' }, { timeout: 5000 })
    await waitFor(() => expect(document.title).toBe('Tu pedido · MATU'))
    await waitFor(() => expect(h1).toHaveFocus())
    expect(within(screen.getByRole('navigation', { name: /secciones/i })).getByRole('link', { name: /Insumos/ })).toHaveAttribute('aria-current', 'page')
    expect(pestanas().getAllByRole('link').map((a) => a.textContent)).toEqual(['Insumos', 'Lista de insumos', 'Catálogo', 'Pedido'])
    expect(pestanas().getByRole('link', { name: 'Pedido' })).toHaveAttribute('aria-current', 'page')
    // El pedido pide el catálogo una vez y fija la capa 3: no hay una segunda pregunta.
    expect(pedidas.filter((p) => p === 'GET /v1/catalogo')).toHaveLength(1)
  })

  it('en /insumos con la capa 3 encendida aparece «Pedido»; con la capa 3 apagada, no', async () => {
    apiApp('admin')
    const { unmount } = abrirApp('/insumos')
    await waitFor(() => expect(pestanas().getAllByRole('link').map((a) => a.textContent)).toContain('Pedido'), { timeout: 5000 })
    unmount()
    apiApp('admin', { capa3: false })
    abrirApp('/insumos')
    await screen.findByRole('navigation', { name: 'Vistas de Insumos' }, { timeout: 5000 })
    await new Promise((r) => setTimeout(r, 200))
    expect(pestanas().getAllByRole('link').map((a) => a.textContent)).not.toContain('Pedido')
  })

  it.each<[Rol, string]>([
    ['pagador', '/insumos/pedido/direccion'],
    ['observador', '/insumos/pedido/direccion'],
    ['observador', '/insumos/pedido/resumen'],
  ])('%s en %s llega a «Tu pedido»', async (rol, ruta) => {
    apiApp(rol)
    abrirApp(ruta)
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'), { timeout: 5000 })
    expect(await screen.findByRole('heading', { level: 1, name: 'Tu pedido' })).toBeVisible()
  })

  it('el pagador abre el resumen: «Antes de pagar · MATU»', async () => {
    apiApp('pagador')
    abrirApp('/insumos/pedido/resumen')
    expect(await screen.findByRole('heading', { level: 1, name: 'Antes de pagar' }, { timeout: 5000 })).toBeVisible()
    await waitFor(() => expect(document.title).toBe('Antes de pagar · MATU'))
  })

  it('2.3: cambiar de persona desde el resumen lleva a «Tu pedido» de la otra persona, sin su id en la URL', async () => {
    apiApp('admin', { personas: [MARIA, PEDRO] })
    abrirApp('/insumos/pedido/resumen')
    await screen.findByRole('heading', { level: 1, name: 'Antes de pagar' }, { timeout: 5000 })
    await userEvent.click(within(screen.getByRole('banner')).getByRole('button', { name: /María Soto/ }))
    await userEvent.click(screen.getByRole('radio', { name: /Pedro Rojas/ }))
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
    expect(await screen.findByRole('heading', { level: 1, name: 'Tu pedido' })).toBeVisible()
    expect(window.location.href).not.toContain(PEDRO.id)
  })
})

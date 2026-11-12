// MATU-61 con la app de la familia entera (estado real, regla de ruta, barra y encabezado): las rutas
// del pedido con su <title> y el foco en el h1, la pestaña «Pedido» solo con la capa 3, las
// redirecciones por rol (2.1) y el cambio de persona desde el resumen (2.3). Solo datos sintéticos.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeAll, describe, expect, it } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { AppFamilia } from '../src/familia/AppFamilia'
import { respuestaDelGrupo } from './miembrosFalsos'
import { autorizaciones, CATALOGO, confirmado, CUENTA, DIRECCION, PERSONA_ID, type Respuesta } from './pedidoFalso'

const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g1'
const MARIA = { id: PERSONA_ID, nombre: 'María Soto', nombre_pila: 'María', nivel_apoyo: 'apoyo_parcial', direccion: DIRECCION, consentimiento: null }
const PEDRO = { id: '3c9d4e20-0000-4000-8000-0000000000bb', nombre: 'Pedro Rojas', nombre_pila: 'Pedro', nivel_apoyo: 'apoyo_parcial', direccion: null, consentimiento: null }

function apiApp(
  rol: Rol,
  { capa3 = true, personas = [MARIA] as object[], despacho = 'vigente' as Parameters<typeof autorizaciones>[0], pedido = confirmado() as object | null, demora = 0 } = {},
) {
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
    // `demora`: la red de verdad tarda, y el h1 de «Cargando» alcanza a recibir el foco de la ruta.
    if (demora && linea.startsWith('GET') && /\/consentimientos$/.test(linea)) await new Promise((r) => setTimeout(r, demora))
    if (/\/consentimientos$/.test(linea)) return responder(config, { status: 200, cuerpo: autorizaciones(despacho, capa3) })
    // La dirección se vacía también con la capa 3 apagada: su ruta se monta siempre (C8, decisión 251).
    if (linea === `DELETE /v1/personas-cuidadas/${PERSONA_ID}/direccion`) return responder(config, { status: 204 })
    if (linea === `GET /v1/personas-cuidadas/${PERSONA_ID}/pedido-en-curso`) return responder(config, capa3 && pedido ? { status: 200, cuerpo: pedido } : no)
    // Sin la autorización de pedidos, crear el pedido responde 403 (decisión 194).
    if (linea === `POST /v1/personas-cuidadas/${PERSONA_ID}/pedidos` && despacho !== 'vigente') return responder(config, { status: 403, cuerpo: { type: '/errores/sin-autorizacion', status: 403 } })
    if (/\/consumo/.test(linea)) return responder(config, { status: 200, cuerpo: { items: [], siguiente_cursor: null } })
    // MATU-42/53: Grupo familiar pide quiénes lo forman; con un 404 la app entiende que la sacaron del grupo.
    const delGrupo = respuestaDelGrupo(linea)
    if (delGrupo) return responder(config, delGrupo)
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

describe('Revisión visual de MATU-61', () => {
  it('P2-2: «Agregar al pedido» sin la autorización lleva a «Antes de pedir, un permiso» con el foco en su h1', async () => {
    apiApp('admin', { despacho: 'sin_autorizar', pedido: null, demora: 150 })
    abrirApp('/insumos/catalogo')
    const agregar = (await screen.findAllByRole('button', { name: /^Agregar al pedido: Pañal adulto M x30/ }, { timeout: 5000 }))[0]
    await userEvent.click(agregar)
    const h1 = await screen.findByRole('heading', { level: 1, name: 'Antes de pedir, un permiso' }, { timeout: 5000 })
    expect(window.location.pathname).toBe('/insumos/pedido')
    await waitFor(() => expect(h1).toHaveFocus())
    expect(document.activeElement).not.toBe(document.body)
  })

  it('P2-3: al entrar directo a la dirección, pregunta por la capa 3 y muestra «Pedido» activa', async () => {
    const pedidas = apiApp('admin')
    abrirApp('/insumos/pedido/direccion')
    await screen.findByRole('navigation', { name: 'Vistas de Insumos' }, { timeout: 5000 })
    await waitFor(() => expect(pestanas().getAllByRole('link').map((a) => a.textContent)).toEqual(['Insumos', 'Lista de insumos', 'Catálogo', 'Pedido']))
    expect(pestanas().getByRole('link', { name: 'Pedido' })).toHaveAttribute('aria-current', 'page')
    expect(pedidas.filter((p) => p === 'GET /v1/catalogo')).toHaveLength(1)
  })

  it('P2-3: con la capa 3 apagada, la dirección no muestra «Pedido»', async () => {
    const pedidas = apiApp('admin', { capa3: false })
    abrirApp('/insumos/pedido/direccion')
    await screen.findByRole('navigation', { name: 'Vistas de Insumos' }, { timeout: 5000 })
    await waitFor(() => expect(pedidas).toContain('GET /v1/catalogo'))
    await new Promise((r) => setTimeout(r, 100))
    expect(pestanas().getAllByRole('link').map((a) => a.textContent)).not.toContain('Pedido')
  })
})

describe('MATU-94 (decisión 251, C8): la dirección con la capa 3 apagada', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
      this.setAttribute('open', '')
    }
    HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
      if (!this.hasAttribute('open')) return
      this.removeAttribute('open')
      this.dispatchEvent(new Event('close'))
    }
  })

  it('desde Grupo familiar, con los pedidos retirados: «Ver la dirección» la abre, se ve y se vacía, y vuelve con su nota', async () => {
    const pedidas = apiApp('admin', { capa3: false, despacho: 'retirada' })
    abrirApp('/grupo')
    const bloque = within(await screen.findByRole('region', { name: 'Permiso para pedir sus insumos' }, { timeout: 5000 }))
    expect(bloque.queryByRole('button', { name: /Volver a autorizar/ })).toBeNull()
    await userEvent.click(bloque.getByRole('button', { name: 'Ver la dirección de entrega de María' }))
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido/direccion'))
    expect(await screen.findByDisplayValue('Los Aromos', {}, { timeout: 5000 })).toBeVisible()
    expect(screen.getByDisplayValue('La Reina')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Vaciar la dirección de entrega de María' }))
    await userEvent.click(within(screen.getByRole('dialog', { name: '¿Vaciar la dirección de entrega de María?' })).getByRole('button', { name: 'Vaciar la dirección' }))
    await waitFor(() => expect(window.location.pathname).toBe('/grupo'))
    expect((await screen.findAllByText('Vaciamos la dirección.', {}, { timeout: 5000 }))[0]).toBeVisible()
    expect(pedidas).toContain(`DELETE /v1/personas-cuidadas/${PERSONA_ID}/direccion`)
  })
})

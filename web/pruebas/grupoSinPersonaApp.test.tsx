// MATU-53 (decisión del orquestador del 12-11, por delegación de Jorge): Grupo familiar se alcanza sin
// persona registrada, para todos los roles, para ver quiénes forman el grupo y poder salir. Las demás
// rutas siguen la regla de MATU-39 5.4. Con la app entera (la regla de ruta y el estado real). Datos
// sintéticos, los de `sin-persona-pagador@` y `miembros-sin-persona@` del doble.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeAll, describe, expect, it } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { AppFamilia } from '../src/familia/AppFamilia'
import type { RespuestaFalsa } from './apiFalsa'
import { miembroDePrueba } from './miembrosFalsos'

const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g1'

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

/** Un grupo sin personas, con la cuenta en `rol`, Carmen que administra y Rosa que cuida. */
function apiSinPersona(rol: Rol) {
  let fuera = false
  const pedidas: string[] = []
  const responder = (config: InternalAxiosRequestConfig, r: RespuestaFalsa): AxiosResponse => {
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  axios.defaults.adapter = async (config) => responder(config, { status: 200, cuerpo: { access_token: 'token-sintetico', token_type: 'bearer', expires_in: 900 } })
  const miembros = [
    miembroDePrueba({ id: 'm-yo', nombre: 'Rodrigo Soto', rol, eres_tu: true, puede_ver_plan: rol === 'pagador' ? false : null, enlaces_vigentes: 0 }),
    miembroDePrueba({ id: 'm-carmen', nombre: 'Carmen Soto', rol: 'admin', eres_tu: false }),
    miembroDePrueba({ id: 'm-rosa', nombre: 'Rosa Pérez', rol: 'cuidador', eres_tu: false }),
  ]
  if (rol === 'admin') miembros[1] = { ...miembros[1], rol: 'admin' }
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const linea = `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`
    pedidas.push(linea)
    if (linea === 'GET /v1/grupos') return responder(config, { status: 200, cuerpo: fuera ? [] : [{ id: GRUPO_ID, nombre: 'Familia Soto', rol, puede_ver_plan: false }] })
    if (linea === `GET /v1/grupos/${GRUPO_ID}/personas-cuidadas`) return responder(config, { status: 200, cuerpo: [] })
    if (linea === `GET /v1/grupos/${GRUPO_ID}/miembros`) return responder(config, { status: 200, cuerpo: { miembros } })
    if (linea === `GET /v1/grupos/${GRUPO_ID}/invitaciones`) return responder(config, { status: 200, cuerpo: { invitaciones: [] } })
    if (linea === `POST /v1/grupos/${GRUPO_ID}/salida`) return (fuera = true), responder(config, { status: 200, cuerpo: { enlaces_cortados: 0 } })
    if (linea === 'GET /v1/catalogo') return responder(config, { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404 } })
    return responder(config, { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404 } })
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

const salirDelGrupo = () => screen.findByRole('region', { name: 'Salir del grupo' }, { timeout: 5000 })

describe('Grupo familiar sin persona registrada', () => {
  it.each(['pagador', 'observador'] as const)('el %s abre /grupo: quiénes forman el grupo y «Salir del grupo», sin autorizaciones ni «Borrar sus datos»', async (rol) => {
    apiSinPersona(rol)
    abrirApp('/grupo')
    expect(await screen.findByRole('region', { name: 'Quiénes forman el grupo' }, { timeout: 5000 })).toBeInTheDocument()
    const salir = within(await salirDelGrupo())
    expect(await salir.findByRole('button', { name: 'Salir del grupo' })).toBeVisible()
    expect(window.location.pathname).toBe('/grupo')
    expect(screen.queryByText(/Todavía no hay nadie registrado/)).toBeNull()
    expect(screen.queryByRole('region', { name: 'Borrar sus datos' })).toBeNull()
    expect(screen.queryByText(/Permiso para/)).toBeNull()
    expect(screen.queryByText(/No encontramos/)).toBeNull()
    // 5.10 (v1.3): la bajada sin persona registrada.
    expect(screen.getByText('Quiénes forman Familia Soto. Todavía no registran a la persona que cuidan.')).toBeVisible()
    expect(screen.queryByText(/a quién cuidan y qué permisos dieron/)).toBeNull()
  })

  it('salir funciona: sin el punto de la ficha (5.10), y sin grupos lleva a crear uno con el aviso', async () => {
    const pedidas = apiSinPersona('pagador')
    abrirApp('/grupo')
    await userEvent.click(await within(await salirDelGrupo()).findByRole('button', { name: 'Salir del grupo' }))
    const d = within(screen.getByRole('dialog'))
    expect(d.queryByText(/Lo que escribiste en la ficha/)).toBeNull()
    await userEvent.click(d.getByRole('button', { name: 'Salir del grupo' }))
    await waitFor(() => expect(window.location.pathname).toBe('/empezar/grupo'))
    expect(await screen.findByText('Saliste de Familia Soto.')).toBeVisible()
    expect(pedidas).toContain(`POST /v1/grupos/${GRUPO_ID}/salida`)
  })

  it('quien administra abre /grupo y conserva «Invitar a alguien», que lleva a /grupo/invitar', async () => {
    apiSinPersona('admin')
    abrirApp('/grupo')
    await userEvent.click(await screen.findByRole('button', { name: 'Invitar a alguien' }, { timeout: 5000 }))
    await waitFor(() => expect(window.location.pathname).toBe('/grupo/invitar'))
    expect(await screen.findByRole('heading', { level: 1, name: 'Invitar a alguien al grupo' })).toBeVisible()
  })

  it('las demás rutas siguen como antes: quien administra va a «¿A quién cuidas?» y quien paga ve que no hay nadie', async () => {
    apiSinPersona('admin')
    const { unmount } = abrirApp('/ficha')
    await waitFor(() => expect(window.location.pathname).toBe('/empezar/persona'), { timeout: 5000 })
    unmount()
    apiSinPersona('pagador')
    abrirApp('/insumos')
    expect(await screen.findByText(/Todavía no hay nadie registrado en Familia Soto/, {}, { timeout: 5000 })).toBeVisible()
    expect(window.location.pathname).toBe('/insumos')
  })
})

// MATU-54 con la app entera (la regla de ruta y el estado real): las entradas en Grupo familiar
// (sección 2) y en Tu cuenta (sección 4), la persona en memoria y no en la ruta, los títulos de la
// pestaña sin nombres, y el foco de vuelta al botón que abrió la página. Solo datos sintéticos.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { AppFamilia } from '../src/familia/AppFamilia'
import type { RespuestaFalsa } from './apiFalsa'
import { copiaCuenta, copiaPersona, dialogoDeJsdom, GRUPO_ID, MARIA } from './misDatosFalso'
import { miembroDePrueba } from './miembrosFalsos'
import { responderPolitica } from './politicaFalsa'

beforeAll(() => dialogoDeJsdom())

let escrituras: string[] = []
beforeEach(() => {
  escrituras = []
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
  responderPolitica()
})

const vigente = (finalidad: string) => ({
  finalidad,
  estado: 'vigente',
  id: '3c9d4e20-0000-4000-8000-0000000054c1',
  otorgado_en: '2026-11-04T15:00:00Z',
  revision_vence_en: null,
  revocado_en: null,
  borrado_en: null,
  borrada: false,
})

/** La API de la familia con María, en `rol`. Devuelve las peticiones («MÉTODO ruta»). */
function api(rol: Rol) {
  const pedidas: string[] = []
  const responder = (config: InternalAxiosRequestConfig, r: RespuestaFalsa & { texto?: string }): AxiosResponse => {
    const respuesta: AxiosResponse = { data: r.texto ?? r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  axios.defaults.adapter = async (config) => responder(config, { status: 200, cuerpo: { access_token: 'token-sintetico', token_type: 'bearer', expires_in: 900 } })
  const persona = rol === 'observador' ? { id: MARIA.id, nombre: MARIA.nombre } : { ...MARIA, nivel_apoyo: 'apoyo_parcial', direccion: null, consentimiento: null }
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const linea = `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`
    pedidas.push(linea)
    if (linea === 'GET /v1/grupos') return responder(config, { status: 200, cuerpo: [{ id: GRUPO_ID, nombre: 'Familia Soto', rol, puede_ver_plan: false }] })
    if (linea === `GET /v1/grupos/${GRUPO_ID}/personas-cuidadas`) return responder(config, { status: 200, cuerpo: [persona] })
    if (linea === `GET /v1/grupos/${GRUPO_ID}/miembros`) return responder(config, { status: 200, cuerpo: { miembros: [miembroDePrueba({ rol })] } })
    if (linea === `GET /v1/grupos/${GRUPO_ID}/invitaciones`) return responder(config, { status: 200, cuerpo: { invitaciones: [] } })
    if (linea === `GET /v1/personas-cuidadas/${MARIA.id}/consentimientos`) return responder(config, { status: 200, cuerpo: { autorizaciones: [vigente('plan_cuidado'), vigente('consumo')] } })
    if (/plan\/accesos-relevo$/.test(linea)) return responder(config, { status: 200, cuerpo: { items: [], siguiente_cursor: null } })
    if (linea === `GET /v1/personas-cuidadas/${MARIA.id}/datos`)
      return responder(config, { status: 200, texto: JSON.stringify(copiaPersona()), cabeceras: { 'content-disposition': 'inline; filename="matu-datos-2026-11-12.json"' } })
    if (linea === 'GET /v1/yo/datos') return responder(config, { status: 200, texto: JSON.stringify(copiaCuenta()), cabeceras: { 'content-disposition': 'inline; filename="matu-cuenta-2026-11-12.json"' } })
    if (linea === 'GET /v1/cuenta')
      return responder(config, { status: 200, cuerpo: { id: 'c1', nombre: 'Carmen', email: 'carmen@example.org', celular_enmascarado: null, celular_verificado: false, celular_canal: 'sms', politica_aceptada: null } })
    if (linea === 'GET /v1/yo/avisos') return responder(config, { status: 200, cuerpo: { correo: true, push: false } })
    if (linea === 'GET /v1/dispositivos/actual/push') return responder(config, { status: 200, cuerpo: { clave_publica: null, permitido: true, registrado: false, envio_simulado: true } })
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

const u = () => userEvent.setup({ delay: null })
const verDatos = () => screen.findByRole('button', { name: 'Ver los datos de María' }, { timeout: 5000 })

describe('«Datos de María» desde Grupo familiar (2)', () => {
  it('admin: el bloque va entre los permisos y «Borrar sus datos», en secundario; abre /grupo/datos sin el id', async () => {
    api('admin')
    abrirApp('/grupo')
    const boton = await verDatos()
    expect(boton.className).not.toContain('bg-turquesa')
    expect(boton).toHaveAttribute('id', `datos-${MARIA.id}`)
    const persona = screen.getByRole('region', { name: MARIA.nombre })
    const titulos = within(persona).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)
    expect(titulos.slice(-2)).toEqual(['Datos de María', 'Borrar sus datos'])
    expect(screen.getByText('Todo lo que MATU guarda de María. Si María o su representante legal te lo pide, puedes mostrárselo o darle una copia.')).toBeInTheDocument()

    await u().click(boton)
    expect(await screen.findByRole('heading', { level: 1, name: 'Datos de María' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/grupo/datos')
    expect(window.location.href).not.toContain(MARIA.id)
    expect(document.title).toBe('Datos guardados · MATU')
    expect(await screen.findByRole('button', { name: 'Descargar en un archivo' })).toBeInTheDocument()
    expect(escrituras).toEqual([])
  })

  it('al volver, el foco va a «Ver los datos de María» cuando Grupo familiar ya lo pintó', async () => {
    const pedidas = api('admin')
    abrirApp('/grupo')
    await u().click(await verDatos())
    await screen.findByRole('button', { name: 'Descargar en un archivo' })
    expect(pedidas.filter((p) => p.endsWith('/datos'))).toHaveLength(1)
    await u().click(screen.getByRole('button', { name: 'Volver a Grupo familiar' }))
    expect(window.location.pathname).toBe('/grupo')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Ver los datos de María' })).toHaveFocus(), { timeout: 5000 })
    expect(document.title).toBe('Grupo familiar · MATU')
  })

  it('al recargar /grupo/datos no hay persona en memoria: vuelve a Grupo familiar sin pedir la copia', async () => {
    const pedidas = api('admin')
    abrirApp('/grupo/datos')
    await verDatos()
    expect(window.location.pathname).toBe('/grupo')
    expect(pedidas.some((p) => p.endsWith('/datos'))).toBe(false)
  })

  it.each(['pagador', 'observador'] as const)('%s: la frase de quién puede, sin botón, y /grupo/datos lo devuelve a Grupo familiar', async (rol) => {
    const pedidas = api(rol)
    abrirApp('/grupo')
    // El observador no recibe `nombre_pila`: como «Borrar sus datos», la frase usa el nombre que llega.
    const pila = rol === 'observador' ? MARIA.nombre : 'María'
    expect(await screen.findByText(`Los puede ver quien administra el grupo o quien cuida a ${pila}.`, {}, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Ver los datos de/ })).toBeNull()
    window.history.pushState(null, '', '/grupo/datos')
    window.dispatchEvent(new PopStateEvent('popstate'))
    await waitFor(() => expect(window.location.pathname).toBe('/grupo'))
    expect(pedidas.some((p) => p.endsWith('/datos'))).toBe(false)
  })
})

describe('«Tus datos» desde Tu cuenta (4)', () => {
  it('la tarjeta va después de «Dónde entraste», en secundario; abre /cuenta/datos y al volver el foco va a «Ver tus datos»', async () => {
    const pedidas = api('pagador')
    abrirApp('/cuenta')
    const boton = await screen.findByRole('button', { name: 'Ver tus datos' }, { timeout: 5000 })
    expect(boton.className).not.toContain('bg-turquesa')
    const h2 = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(h2.indexOf('Tus datos')).toBe(h2.indexOf('Dónde entraste') + 1)
    expect(screen.getByText('Ver y descargar lo que MATU guarda de tu cuenta.')).toBeInTheDocument()
    // «Tu cuenta» no pide la copia: solo «Tus datos».
    expect(pedidas.some((p) => p.endsWith('/datos'))).toBe(false)

    await u().click(boton)
    expect(await screen.findByRole('button', { name: 'Descargar en un archivo' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/cuenta/datos')
    expect(document.title).toBe('Tus datos · MATU')
    expect(pedidas.filter((p) => p === 'GET /v1/yo/datos')).toHaveLength(1)

    await u().click(screen.getByRole('button', { name: 'Volver a tu cuenta' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Ver tus datos' })).toHaveFocus(), { timeout: 5000 })
    expect(window.location.pathname).toBe('/cuenta')
  })
})

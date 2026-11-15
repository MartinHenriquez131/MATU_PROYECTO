// «Cambiar {insumo}» con la app de la familia entera (P1 de la revisión visual de MATU-109, que venía
// de MATU-53): en /insumos la regla de ruta ponía `<AvisoDeLlegada />` junto a `<Insumos />` y en
// /insumos/cambiar solo `<Insumos />`. La forma del árbol cambiaba, React remontaba Insumos, se
// perdía el insumo en edición y la pantalla volvía a /insumos sin abrir el formulario. Ahora las
// rutas de Insumos tienen la misma forma: «Cambiar» abre el formulario y se puede guardar. Datos sintéticos.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { AppFamilia } from '../src/familia/AppFamilia'
import type { RespuestaFalsa } from './apiFalsa'

const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g1'
const MARIA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María', nivel_apoyo: 'apoyo_parcial' }
const BASE = `/v1/personas-cuidadas/${MARIA.id}/consumo`

const hoy = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Santiago', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
const sumar = (iso: string, n: number) => {
  const [a, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(a, m - 1, d + n)).toISOString().slice(0, 10)
}

const TOALLITAS = {
  id: '3c9d4e20-0000-4000-8000-0000000000c2',
  producto: null,
  nombre_libre: 'Toallitas húmedas',
  unidad: 'unidad',
  tasa_unidades: 3,
  tasa_dias: 1,
  stock_unidades: 30,
  stock_medido_en: '2026-11-04',
  dias_aviso: 7,
  fecha_quiebre_estimada: sumar(hoy, 10),
  dias_restantes: 10,
  activo: true,
  actualizado_por: { id: 'u1', nombre: 'Carmen' },
  unidades_por_envase: null,
  etag: '"v1"',
}

beforeEach(() => {
  for (const s of [localStorage, sessionStorage]) s.clear()
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {})
})

function apiApp() {
  const escritas: { linea: string; cuerpo: unknown; ifMatch: unknown }[] = []
  const responder = (config: InternalAxiosRequestConfig, r: RespuestaFalsa): AxiosResponse => {
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  axios.defaults.adapter = async (config) => responder(config, { status: 200, cuerpo: { access_token: 'token-sintetico', token_type: 'bearer', expires_in: 900 } })
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const linea = `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`
    if (linea === 'GET /v1/grupos') return responder(config, { status: 200, cuerpo: [{ id: GRUPO_ID, nombre: 'Familia Rojas', rol: 'cuidador', puede_ver_plan: true }] })
    if (linea === `GET /v1/grupos/${GRUPO_ID}/personas-cuidadas`) return responder(config, { status: 200, cuerpo: [MARIA] })
    if (linea === `GET ${BASE}`) return responder(config, { status: 200, cuerpo: { items: [TOALLITAS], siguiente_cursor: null } })
    if (linea === `GET ${BASE}/por-acabarse`) return responder(config, { status: 200, cuerpo: { items: [] } })
    if (linea === `PATCH ${BASE}/${TOALLITAS.id}`) {
      const cuerpo = typeof config.data === 'string' ? JSON.parse(config.data) : config.data
      escritas.push({ linea, cuerpo, ifMatch: config.headers?.['If-Match'] })
      return responder(config, { status: 200, cuerpo: { ...TOALLITAS, ...cuerpo, etag: '"v2"' } })
    }
    return responder(config, { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404 } })
  }
  return escritas
}

describe('«Cambiar» un insumo en la app entera', () => {
  it('abre el formulario en /insumos/cambiar y se puede guardar', async () => {
    const escritas = apiApp()
    window.history.replaceState(null, '', '/insumos')
    render(
      <>
        <RegionesVivas />
        <AppFamilia />
      </>,
    )
    const u = userEvent.setup()
    await u.click(await screen.findByRole('button', { name: 'Cambiar Toallitas húmedas' }, { timeout: 5000 }))
    // El formulario se abre y la ruta se queda en /insumos/cambiar (antes volvía a /insumos).
    const guardar = await screen.findByRole('button', { name: 'Guardar' })
    expect(window.location.pathname).toBe('/insumos/cambiar')
    const campo = screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })
    await u.type(campo, '12')
    await u.click(guardar)
    await waitFor(() => expect(escritas).toHaveLength(1))
    expect(escritas[0]).toMatchObject({ linea: `PATCH ${BASE}/${TOALLITAS.id}`, ifMatch: '"v1"' })
    expect(escritas[0].cuerpo).toMatchObject({ stock_unidades: 12 })
    await waitFor(() => expect(window.location.pathname).toBe('/insumos'))
    expect(await screen.findByText(/Guardamos «Toallitas húmedas»\./)).toBeInTheDocument()
  })
})

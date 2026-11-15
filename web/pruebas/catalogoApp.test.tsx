// MATU-59 con la app de la familia entera (estado real, regla de ruta, barra y encabezado): los cuatro
// roles llegan a /insumos/catalogo, con Insumos activa en la barra y «Catálogo · MATU» de título, y
// cambiar de persona deja la ruta en el catálogo (N1, especificación 2.2). Solo datos sintéticos.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { AppFamilia } from '../src/familia/AppFamilia'
import type { RespuestaFalsa } from './apiFalsa'

const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g1'
const MARIA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María', nivel_apoyo: 'apoyo_parcial' }
const PEDRO = { id: '3c9d4e20-0000-4000-8000-0000000000bb', nombre: 'Pedro Rojas', nombre_pila: 'Pedro', nivel_apoyo: 'apoyo_parcial' }

const CATALOGO = {
  precios_de_ejemplo: true,
  categorias: [
    {
      id: '3c9d4e20-0000-4000-8000-0000000000d1',
      nombre: 'Higiene y cuidado personal',
      orden: 1,
      productos: [
        {
          id: '3c9d4e20-0000-4000-8000-0000000000d2',
          nombre: 'Pañal adulto M x30',
          presentacion: 'Paquete de 30 unidades',
          unidad: 'unidad',
          unidades_por_envase: 30,
          retracto_pierde_al_abrir: true,
          comercios: [{ oferta_id: '3c9d4e20-0000-4000-8000-0000000000d3', comercio_id: '3c9d4e20-0000-4000-8000-0000000000d4', nombre_fantasia: 'Almacén El Ejemplo', precio: 12990, disponible: true }],
        },
      ],
    },
  ],
}

let escrituras: string[] = []
beforeEach(() => {
  escrituras = []
  for (const s of [localStorage, sessionStorage]) s.clear()
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
})

/** La API: entrar con la cookie, un grupo con el rol pedido, sus personas y el catálogo. Lo demás, 404. */
function apiApp(rol: Rol, personas: (typeof MARIA)[]) {
  const pedidas: { linea: string; grupo: boolean }[] = []
  const responder = (config: InternalAxiosRequestConfig, r: RespuestaFalsa): AxiosResponse => {
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  axios.defaults.adapter = async (config) => responder(config, { status: 200, cuerpo: { access_token: 'token-sintetico', token_type: 'bearer', expires_in: 900 } })
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const linea = `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`
    pedidas.push({ linea, grupo: 'X-Grupo-Id' in (config.headers.toJSON() as object) })
    if (linea === 'GET /v1/grupos') return responder(config, { status: 200, cuerpo: [{ id: GRUPO_ID, nombre: 'Familia Rojas', rol, puede_ver_plan: true }] })
    if (linea === `GET /v1/grupos/${GRUPO_ID}/personas-cuidadas`) return responder(config, { status: 200, cuerpo: personas })
    if (linea === 'GET /v1/catalogo') return responder(config, { status: 200, cuerpo: CATALOGO })
    return responder(config, { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404 } })
  }
  return pedidas
}

function abrirApp() {
  window.history.replaceState(null, '', '/insumos/catalogo')
  return render(
    <>
      <RegionesVivas />
      <AppFamilia />
    </>,
  )
}

describe('El catálogo en la app de la familia', () => {
  it('MATU-107 (42-H2): la barra del teléfono marca la sección activa con el indicador turquesa y el rótulo en tinta, sin negrita', async () => {
    apiApp('admin', [MARIA])
    abrirApp()
    await screen.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' }, { timeout: 5000 })
    const barra = screen.getByRole('navigation', { name: /secciones/i })
    const enlaces = within(barra).getAllByRole('link')
    expect(enlaces.length).toBeGreaterThan(1)
    for (const a of enlaces) {
      const clases = a.className.split(/\s+/)
      // 1.4: 17 px heredados desde 21 rem, text-sm solo en estrecho; relative para el indicador.
      expect(clases).not.toContain('telefono:text-sm')
      expect(clases).toContain('estrecho:text-sm')
      expect(clases).toContain('relative')
      const indicador = a.querySelector('span.bg-turquesa')
      if (a.getAttribute('aria-current') === 'page') {
        expect(clases).toEqual(expect.arrayContaining(['telefono:font-normal', 'telefono:text-tinta']))
        expect(indicador).not.toBeNull()
        expect(indicador).toHaveAttribute('aria-hidden')
        expect(indicador!.className.split(/\s+/)).toEqual(expect.arrayContaining(['hidden', 'telefono:block', 'absolute', 'top-0', 'h-1', 'w-8', 'rounded-b-full']))
        expect(a.querySelector('svg')!.getAttribute('class')).toMatch(/\btext-turquesa\b/)
      } else {
        expect(indicador).toBeNull()
      }
    }
    expect(enlaces.filter((a) => a.getAttribute('aria-current') === 'page')).toHaveLength(1)
  })

  it.each<Rol>(['admin', 'cuidador', 'pagador', 'observador'])('%s llega a /insumos/catalogo, con Insumos activa en la barra', async (rol) => {
    const pedidas = apiApp(rol, [MARIA])
    abrirApp()
    expect(await screen.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' }, { timeout: 5000 })).toBeVisible()
    expect(window.location.pathname).toBe('/insumos/catalogo')
    expect(screen.getByRole('heading', { level: 1, name: 'Catálogo' })).toBeVisible()
    await waitFor(() => expect(document.title).toBe('Catálogo · MATU'))
    const barra = screen.getByRole('navigation', { name: /secciones/i })
    expect(within(barra).getByRole('link', { name: /Insumos/ })).toHaveAttribute('aria-current', 'page')
    // El catálogo, sin X-Grupo-Id ni pedidos de consumo de la persona.
    const catalogo = pedidas.filter((p) => p.linea === 'GET /v1/catalogo')
    expect(catalogo).toHaveLength(1)
    expect(catalogo[0].grupo).toBe(false)
    expect(pedidas.some((p) => /\/consumo/.test(p.linea))).toBe(false)
    expect(escrituras).toEqual([])
  })

  it('cambiar de persona en el catálogo deja la ruta en /insumos/catalogo', async () => {
    apiApp('admin', [MARIA, PEDRO])
    abrirApp()
    await screen.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' }, { timeout: 5000 })
    await userEvent.click(within(screen.getByRole('banner')).getByRole('button', { name: /María Soto/ }))
    await userEvent.click(screen.getByRole('radio', { name: /Pedro Rojas/ }))
    await waitFor(() => expect(within(screen.getByRole('banner')).getByRole('button', { name: /Pedro Rojas/ })).toBeVisible())
    expect(window.location.pathname).toBe('/insumos/catalogo')
    expect(await screen.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })).toBeVisible()
    expect(window.location.href).not.toContain(PEDRO.id)
  })
})

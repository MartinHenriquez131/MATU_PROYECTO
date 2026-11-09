// MATU-67: el aviso de versión nueva (especificación docs/diseno/matu-67-aviso-version.md y textos
// aprobados por Jorge el 09-11, tal cual). Cuándo revisa (volver a la pestaña, cada 15 minutos, sin
// caché), cuándo aparece y cuándo espera (campo de texto, alta, /compartir/listo), que nunca recarga
// sola, «Recargar» con algo sin guardar en una sección y en un insumo, «Más tarde» y sus 15 minutos,
// el anuncio por `status` y el relevo. Con temporizadores falsos. Datos sintéticos.
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api as apiRelevo } from '../src/compartido/api/cliente'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { Boton } from '../src/compartido/ui/Boton'
import { CADA_MS, navegador, olvidarVersion, useRevisarVersion } from '../src/compartido/version'
import { MarcoAlta } from '../src/familia/Alta'
import { SECCIONES } from '../src/familia/datos'
import { EditorDeSeccion } from '../src/familia/EditorSeccion'
import { Insumos } from '../src/familia/Insumos'
import { Compartir } from '../src/familia/Compartir'
import { MarcoSimple, ShellFamilia } from '../src/familia/Shell'
import { Marco, Titulo } from '../src/relevo/Marco'
import { PaginaRelevo } from '../src/relevo/PaginaRelevo'
import { familiaFalsa } from './familiaFalsa'

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

const TITULO = 'Hay una versión nueva de MATU.'
const BAJADA_FAMILIA = 'Recarga cuando termines lo que estás haciendo.'
const BAJADA_RELEVO = 'Recarga cuando termines de leer.'
const ANUNCIO_FAMILIA = `${TITULO} ${BAJADA_FAMILIA}`

const PERSONA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María' }
const GRUPO = { id: '3c9d4e20-0000-4000-8000-0000000000bb', nombre: 'Familia Soto', rol: 'cuidador', puede_ver_plan: true }

/** Lo que responde `/version.json`: una versión, un estado de error o una falla de red. */
let respuesta: { version?: unknown; status?: number; red?: boolean }
const fetchFalso = vi.fn(async (url: string, init?: RequestInit) => {
  void url
  void init
  if (respuesta.red) throw new TypeError('Failed to fetch')
  const status = respuesta.status ?? 200
  return { ok: status < 400, status, json: async () => ({ version: respuesta.version }) } as Response
})

let visible: DocumentVisibilityState = 'visible'
let recargar: ReturnType<typeof vi.fn<() => void>>
let escrituras: string[]

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  olvidarVersion()
  respuesta = { version: 'otra-version' }
  fetchFalso.mockClear()
  vi.stubGlobal('fetch', fetchFalso)
  visible = 'visible'
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => visible })
  recargar = vi.fn<() => void>()
  vi.spyOn(navegador, 'recargar').mockImplementation(recargar)
  escrituras = []
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
  contexto = familiaFalsa({ rol: 'cuidador', persona: PERSONA, personaId: PERSONA.id, personas: [PERSONA], grupos: [], grupo: GRUPO, sinGuardar: { current: null } } as never)
  window.history.replaceState(null, '', '/ficha')
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

/** Sale de la pestaña y vuelve: la app revisa `/version.json`. */
async function volverALaPestana() {
  visible = 'hidden'
  await act(async () => {
    document.dispatchEvent(new Event('visibilitychange'))
  })
  visible = 'visible'
  await act(async () => {
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
  })
  // Lo que se anuncia llega a la región 50 ms después.
  await act(async () => {
    await vi.advanceTimersByTimeAsync(60)
  })
}

const aviso = () => document.querySelector('[data-aviso-version]') as HTMLElement | null
const amable = () => screen.getByRole('status')
const urgente = () => screen.getByRole('alert')

/** Como main.tsx: las regiones vivas y la app, que revisa la versión. */
function App({ children }: { children: ReactNode }) {
  useRevisarVersion()
  return <>{children}</>
}

function montar(pantalla: ReactNode) {
  return render(
    <>
      <RegionesVivas />
      <App>{pantalla}</App>
    </>,
  )
}

const enShell = (hijos: ReactNode = <Titulo>Ficha de relevo</Titulo>) => montar(<ShellFamilia>{hijos}</ShellFamilia>)

// ---------------------------------------------------------------- cuándo revisa

describe('Cuándo revisa', () => {
  it('al volver a la pestaña y cada 15 minutos mientras está visible, siempre sin caché', async () => {
    respuesta = { version: 'prueba' }
    enShell()
    expect(fetchFalso).not.toHaveBeenCalled()

    await volverALaPestana()
    expect(fetchFalso).toHaveBeenCalledTimes(1)
    expect(fetchFalso.mock.calls[0][0]).toBe('/version.json')
    expect(fetchFalso.mock.calls[0][1]).toMatchObject({ cache: 'no-store' })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(CADA_MS)
    })
    expect(fetchFalso).toHaveBeenCalledTimes(2)
    expect(fetchFalso.mock.calls[1][1]).toMatchObject({ cache: 'no-store' })

    // Con la pestaña oculta no revisa.
    visible = 'hidden'
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
      await vi.advanceTimersByTimeAsync(CADA_MS * 2)
    })
    expect(fetchFalso).toHaveBeenCalledTimes(2)
  })

  it('con la misma versión no hay aviso', async () => {
    respuesta = { version: 'prueba' }
    enShell()
    await volverALaPestana()
    expect(fetchFalso).toHaveBeenCalled()
    expect(aviso()).toBeNull()
    expect(screen.queryByText(TITULO)).toBeNull()
  })

  it('con una versión distinta aparece el aviso, en el flujo de la barra, y nunca recarga solo', async () => {
    enShell()
    await volverALaPestana()
    const caja = aviso()!
    expect(caja).not.toBeNull()
    expect(caja).toHaveTextContent(TITULO)
    expect(caja).toHaveTextContent(BAJADA_FAMILIA)
    // 2.1: dentro del `aside`, después de las secciones; nunca en `main`.
    const aside = caja.closest('aside')!
    expect(aside).not.toBeNull()
    expect(screen.getByRole('navigation', { name: 'Secciones' }).compareDocumentPosition(caja) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(caja.closest('main')).toBeNull()
    expect(caja).toHaveClass('basis-full')
    // 3: la apariencia de `Nota` rocío con borde, sin sombra ni posición propia.
    const nota = caja.firstElementChild!
    expect(nota).toHaveClass('bg-rocio', 'border-l-4', 'border-turquesa', 'rounded-xl')
    expect(caja.outerHTML).not.toMatch(/\b(fixed|absolute|sticky|shadow)/)
    // «Recargar» secundario y «Más tarde» de texto; ninguno es macizo.
    expect(within(caja).getByRole('button', { name: 'Recargar' })).toHaveClass('ring-turquesa/80')
    expect(within(caja).getByRole('button', { name: 'Recargar' })).not.toHaveClass('bg-turquesa')
    expect(within(caja).getByRole('button', { name: 'Más tarde' })).toHaveClass('underline')
    // No toma el foco.
    expect(caja.contains(document.activeElement)).toBe(false)

    // Ninguna revisión ni el tiempo recargan.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(CADA_MS * 3)
    })
    await volverALaPestana()
    expect(recargar).not.toHaveBeenCalled()
    // Nada en el navegador ni en la URL.
    expect(escrituras).toEqual([])
    expect(window.location.pathname + window.location.search + window.location.hash).toBe('/ficha')
  })

  it.each([
    ['falla la red', { red: true }],
    ['responde un error', { status: 503 }],
    ['trae un identificador vacío', { version: '' }],
    ['trae un identificador mal formado', { version: '<script>' }],
    ['no trae identificador', { version: undefined }],
  ])('si %s, no hay aviso ni nada en la consola', async (_, r) => {
    const consola = vi.spyOn(console, 'error')
    respuesta = r
    enShell()
    await volverALaPestana()
    expect(fetchFalso).toHaveBeenCalled()
    expect(aviso()).toBeNull()
    expect(amable()).toBeEmptyDOMElement()
    expect(urgente()).toBeEmptyDOMElement()
    expect(consola).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------- anuncio, Recargar y Más tarde

describe('El aviso', () => {
  it('se anuncia una vez por la región `status`, sin los botones, y no otra vez al cambiar de pantalla', async () => {
    const { rerender } = enShell()
    await volverALaPestana()
    expect(amable()).toHaveTextContent(ANUNCIO_FAMILIA)
    expect(amable().textContent).toBe(ANUNCIO_FAMILIA)
    expect(urgente()).toBeEmptyDOMElement()

    // Otra versión más nueva mientras está a la vista: no cambia ni se vuelve a anunciar.
    respuesta = { version: 'otra-mas' }
    // Cambia de pantalla: de la barra a `MarcoSimple`, y vuelve. El aviso sigue, sin anunciarse.
    const anuncios: string[] = []
    const observador = new MutationObserver(() => anuncios.push(amable().textContent ?? ''))
    observador.observe(amable(), { childList: true, characterData: true, subtree: true })
    rerender(
      <>
        <RegionesVivas />
        <App>
          <MarcoSimple>
            <Titulo>Abriendo MATU</Titulo>
          </MarcoSimple>
        </App>
      </>,
    )
    await volverALaPestana()
    // 2.2: en `MarcoSimple`, primero en `main`, antes del título.
    const caja = aviso()!
    expect(caja.closest('main')).not.toBeNull()
    expect(caja).toHaveClass('mb-6')
    expect(caja.compareDocumentPosition(screen.getByRole('heading', { name: 'Abriendo MATU' })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // Sin fundido la segunda vez: ya estaba.
    expect(caja.firstElementChild).not.toHaveClass('animate-aparecer')
    observador.disconnect()
    expect(anuncios).toEqual([])
  })

  it('«Recargar» recarga y dice «Recargando…»', async () => {
    enShell()
    await volverALaPestana()
    const boton = within(aviso()!).getByRole('button', { name: 'Recargar' })
    fireEvent.click(boton)
    expect(recargar).toHaveBeenCalledTimes(1)
    expect(boton).toHaveAttribute('aria-busy', 'true')
    expect(boton).toHaveTextContent('Recargando…')
  })

  it('«Más tarde» lo oculta, deja el foco en el título, lo retira de la región y no vuelve antes de 15 minutos', async () => {
    enShell()
    await volverALaPestana()
    expect(amable()).toHaveTextContent(ANUNCIO_FAMILIA)

    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Más tarde' }))
    expect(aviso()).toBeNull()
    expect(screen.getByRole('heading', { name: 'Ficha de relevo' })).toHaveFocus()
    expect(amable()).toBeEmptyDOMElement()
    expect(recargar).not.toHaveBeenCalled()

    // A los 10 minutos, una revisión que sigue viendo la versión nueva: todavía no.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10 * 60 * 1000)
    })
    await volverALaPestana()
    expect(fetchFalso).toHaveBeenCalled()
    expect(aviso()).toBeNull()
    // A los 14 minutos y medio, tampoco.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4.5 * 60 * 1000)
    })
    await volverALaPestana()
    expect(aviso()).toBeNull()

    // Pasados los 15 minutos, la próxima revisión lo trae de vuelta, y se anuncia otra vez.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60 * 1000)
    })
    await volverALaPestana()
    expect(aviso()).not.toBeNull()
    expect(amable()).toHaveTextContent(ANUNCIO_FAMILIA)
    // Solo en memoria.
    expect(escrituras).toEqual([])
  })

  it('después de «Más tarde», también vuelve en una revisión de cada 15 minutos, sin volver a la pestaña', async () => {
    enShell()
    await volverALaPestana()
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Más tarde' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(CADA_MS + 1000)
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(CADA_MS)
    })
    expect(aviso()).not.toBeNull()
  })
})

// ---------------------------------------------------------------- 4.2 cuándo espera

describe('Cuándo espera', () => {
  it('con el foco en un campo de texto espera; pasar a otro campo no cuenta; aparece al salir a un botón', async () => {
    enShell(
      <>
        <Titulo>Ficha de relevo</Titulo>
        <label>
          Nombre <input type="text" />
        </label>
        <label>
          Nota <textarea />
        </label>
        <button type="button">Otro botón</button>
      </>,
    )
    const nombre = screen.getByRole('textbox', { name: 'Nombre' })
    act(() => nombre.focus())
    await volverALaPestana()
    expect(fetchFalso).toHaveBeenCalled()
    expect(aviso()).toBeNull()
    expect(amable()).toBeEmptyDOMElement()

    act(() => screen.getByRole('textbox', { name: 'Nota' }).focus())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60)
    })
    expect(aviso()).toBeNull()

    act(() => screen.getByRole('button', { name: 'Otro botón' }).focus())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60)
    })
    expect(aviso()).not.toBeNull()
    expect(amable()).toHaveTextContent(ANUNCIO_FAMILIA)
    // Ya a la vista, volver a un campo no lo quita.
    act(() => nombre.focus())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60)
    })
    expect(aviso()).not.toBeNull()
  })

  it('en `/compartir/listo` no aparece; aparece al salir de esa pantalla', async () => {
    window.history.replaceState(null, '', '/compartir/listo')
    const { rerender } = enShell()
    await volverALaPestana()
    expect(fetchFalso).toHaveBeenCalled()
    expect(aviso()).toBeNull()
    expect(amable()).toBeEmptyDOMElement()

    window.history.pushState(null, '', '/compartir/enlaces')
    rerender(
      <>
        <RegionesVivas />
        <App>
          <ShellFamilia>
            <Titulo>Enlaces</Titulo>
          </ShellFamilia>
        </App>
      </>,
    )
    await act(async () => {
      window.dispatchEvent(new PopStateEvent('popstate'))
      await vi.advanceTimersByTimeAsync(60)
    })
    expect(aviso()).not.toBeNull()
    expect(amable()).toHaveTextContent(ANUNCIO_FAMILIA)
  })

  it('en el alta no aparece; aparece en la pantalla siguiente', async () => {
    window.history.replaceState(null, '', '/empezar/persona')
    const { rerender } = montar(
      <MarcoAlta paso={2}>
        <Titulo>¿A quién cuidas?</Titulo>
      </MarcoAlta>,
    )
    await volverALaPestana()
    expect(fetchFalso).toHaveBeenCalled()
    expect(aviso()).toBeNull()
    expect(amable()).toBeEmptyDOMElement()

    window.history.replaceState(null, '', '/ficha')
    rerender(
      <>
        <RegionesVivas />
        <App>
          <ShellFamilia>
            <Titulo>Ficha de relevo</Titulo>
          </ShellFamilia>
        </App>
      </>,
    )
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60)
    })
    expect(aviso()).not.toBeNull()
    expect(amable()).toHaveTextContent(ANUNCIO_FAMILIA)
  })
})

// ---------------------------------------------------------------- 4.3 Recargar con algo sin guardar

type Adaptador = (config: InternalAxiosRequestConfig) => { status: number; cuerpo?: unknown }
function apiDeFamilia(responder: Adaptador) {
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const r = responder(config)
    const res: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, res)
    return res
  }
}

const hoyIso = new Date().toISOString().slice(0, 10)
const perfilFalso = (id: string, nombre: string, cambios: Record<string, unknown> = {}) => ({
  id: `3c9d4e20-0000-4000-8000-0000000000${id}`,
  producto: null,
  nombre_libre: nombre,
  unidad: 'unidad',
  tasa_unidades: 3,
  tasa_dias: 1,
  stock_unidades: 30,
  stock_medido_en: hoyIso,
  dias_aviso: 7,
  fecha_quiebre_estimada: hoyIso,
  dias_restantes: 10,
  activo: true,
  actualizado_por: { id: 'u1', nombre: 'Carmen' },
  unidades_por_envase: null,
  etag: '"v1"',
  ...cambios,
})
const TOALLITAS = perfilFalso('c2', 'Toallitas húmedas')
const PANAL = perfilFalso('c1', 'Pañal adulto talla M', { unidades_por_envase: 20, stock_unidades: 6, dias_restantes: 2 })

/** Insumos dentro de la barra, con la lista y «Se acaban pronto» (el pañal, avisando). */
async function insumos(perfiles = [TOALLITAS, PANAL]) {
  window.history.replaceState(null, '', '/insumos')
  const bloque = perfiles.filter((p) => p === PANAL).map((p) => ({ ...p, avisando: true, alerta_id: '3c9d4e20-0000-4000-8000-00000000a001' }))
  apiDeFamilia((config) => {
    if (config.url?.endsWith('/consumo/por-acabarse')) return { status: 200, cuerpo: { items: bloque } }
    if (config.url?.endsWith('/consumo')) return { status: 200, cuerpo: { items: perfiles, siguiente_cursor: null } }
    return { status: 500 }
  })
  enShell(<Insumos />)
  if (perfiles.length) await screen.findByRole('button', { name: `Compré: ${perfiles[0].nombre_libre}` })
}

/** Toca «Recargar» y deja pasar el anuncio. */
async function tocarRecargar() {
  fireEvent.click(within(aviso()!).getByRole('button', { name: 'Recargar' }))
  await act(async () => {
    await vi.advanceTimersByTimeAsync(60)
  })
}

describe('«Recargar» con algo sin guardar', () => {
  it('en una sección de la ficha: no recarga, pasa a `atenta` con el nombre de la sección y el foco en «Seguir escribiendo»', async () => {
    const seccion = SECCIONES.find((s) => s.api === 'quien_es')!
    window.history.replaceState(null, '', seccion.ruta)
    const ficha = {
      persona_id: PERSONA.id,
      rutina: { texto: null, etag: null, actualizado_en: null, actualizado_por: null },
      manejo_situaciones: { texto: null, etag: null, actualizado_en: null, actualizado_por: null },
      red_apoyo: { texto: null, etag: null, actualizado_en: null, actualizado_por: null },
      secciones: {},
      completitud: 0,
    }
    contexto = familiaFalsa({ ...contexto, ficha } as never)
    apiDeFamilia(() => ({ status: 500 }))
    enShell(<EditorDeSeccion seccion={seccion} />)
    await volverALaPestana()
    expect(aviso()).not.toBeNull()

    const campo = document.getElementById('seccion-texto') as HTMLTextAreaElement
    fireEvent.change(campo, { target: { value: 'Le dicen Tito.' } })
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Recargar' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60)
    })
    expect(recargar).not.toHaveBeenCalled()

    const caja = aviso()!
    const nota = caja.firstElementChild!
    expect(nota).toHaveClass('bg-atenta-fondo', 'border-atenta')
    expect(caja).toHaveTextContent(`Lo que escribiste en «${seccion.titulo}» no se guardó.`)
    expect(caja).toHaveTextContent('Si recargas ahora, se pierde.')
    expect(caja).not.toHaveTextContent(TITULO)
    const seguir = within(caja).getByRole('button', { name: 'Seguir escribiendo' })
    expect(seguir).toHaveFocus()
    expect(seguir).toHaveClass('ring-turquesa/80')
    expect(within(caja).getByRole('button', { name: 'Recargar igual' })).toHaveClass('text-pronto')
    expect(urgente()).toHaveTextContent(`Lo que escribiste en «${seccion.titulo}» no se guardó. Si recargas ahora, se pierde.`)

    // «Seguir escribiendo»: vuelve al aviso normal, sin anunciarlo, con el foco en el campo.
    const anuncioPrevio = amable().textContent
    fireEvent.click(seguir)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60)
    })
    expect(campo).toHaveFocus()
    expect(campo).toHaveValue('Le dicen Tito.')
    expect(aviso()).toHaveTextContent(TITULO)
    expect(urgente()).toBeEmptyDOMElement()
    expect(amable().textContent).toBe(anuncioPrevio)

    // «Recargar igual» sí recarga.
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Recargar' }))
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Recargar igual' }))
    expect(recargar).toHaveBeenCalledTimes(1)
    expect(within(aviso()!).getByRole('button', { name: /Recargar igual|Recargando…/ })).toHaveAttribute('aria-busy', 'true')
  })

  it('en «Compré» de un insumo: no recarga y nombra solo el insumo; sin cambios, recarga', async () => {
    await insumos()
    await volverALaPestana()
    expect(aviso()).not.toBeNull()

    // Abrir el panel sin escribir nada no es «sin guardar».
    fireEvent.click(screen.getByRole('button', { name: 'Compré: Toallitas húmedas' }))
    const panel = await screen.findByRole('group', { name: /compraste/ })
    const campo = within(panel).getByRole('textbox')
    // El panel lleva el foco a su campo a los 40 ms (MATU-51, 4).
    await waitFor(() => expect(campo).toHaveFocus())
    expect(contexto.sinGuardar.current?.()).toBeNull()
    fireEvent.change(campo, { target: { value: '12' } })
    await tocarRecargar()
    expect(recargar).not.toHaveBeenCalled()
    expect(aviso()).toHaveTextContent('Lo que anotaste de «Toallitas húmedas» no se guardó.')
    expect(within(aviso()!).getByRole('button', { name: 'Seguir escribiendo' })).toHaveFocus()

    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Seguir escribiendo' }))
    expect(campo).toHaveFocus()
    expect(campo).toHaveValue('12')

    // Vuelve a dejarlo como estaba: ya no hay nada sin guardar y «Recargar» recarga.
    fireEvent.change(campo, { target: { value: '' } })
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Recargar' }))
    expect(recargar).toHaveBeenCalledTimes(1)
  })

  it('en «Me quedan» de un insumo: el mismo título, con solo el nombre', async () => {
    await insumos()
    await volverALaPestana()
    fireEvent.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    const panel = await screen.findByRole('group', { name: /quedan/i })
    const campo = within(panel).getByRole('textbox')
    await waitFor(() => expect(campo).toHaveFocus())
    fireEvent.change(campo, { target: { value: '4' } })
    await tocarRecargar()
    expect(recargar).not.toHaveBeenCalled()
    expect(aviso()).toHaveTextContent('Lo que anotaste de «Toallitas húmedas» no se guardó.')
  })

  it('en «Ya lo resolví»: no recarga y nombra solo el insumo', async () => {
    await insumos()
    await volverALaPestana()
    fireEvent.click(screen.getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' }))
    const campo = await screen.findByRole('textbox', { name: '¿Compraste? ¿Cuántos envases?' })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60)
    })
    expect(campo).toHaveValue('1')
    // Solo abrirlo, con el 1 de partida, no es «sin guardar».
    expect(contexto.sinGuardar.current?.()).toBeNull()
    fireEvent.change(campo, { target: { value: '2' } })
    await tocarRecargar()
    expect(recargar).not.toHaveBeenCalled()
    expect(aviso()).toHaveTextContent('Lo que anotaste de «Pañal adulto talla M» no se guardó.')
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Seguir escribiendo' }))
    expect(campo).toHaveFocus()
  })

  it('en el editor de un insumo: no recarga y nombra solo el insumo', async () => {
    await insumos()
    await volverALaPestana()
    fireEvent.click(screen.getByRole('button', { name: 'Cambiar Toallitas húmedas' }))
    const envase = await screen.findByRole('textbox', { name: '¿Cuántas unidades trae cada envase?' })
    expect(contexto.sinGuardar.current?.()).toBeNull()
    fireEvent.change(envase, { target: { value: '10' } })
    await tocarRecargar()
    expect(recargar).not.toHaveBeenCalled()
    expect(aviso()).toHaveTextContent('Lo que anotaste de «Toallitas húmedas» no se guardó.')
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Seguir escribiendo' }))
    expect(envase).toHaveFocus()
  })

  it('en «Anotar un insumo»: sin nombre, el título genérico; con nombre, el del insumo', async () => {
    await insumos([])
    const anotar = await screen.findAllByRole('button', { name: 'Anotar un insumo' })
    await volverALaPestana()
    fireEvent.click(anotar[0])
    const nombre = await screen.findByRole('textbox', { name: '¿Qué insumo es?' })
    const envase = screen.getByRole('textbox', { name: '¿Cuántas unidades trae cada envase?' })
    fireEvent.change(envase, { target: { value: '10' } })
    await tocarRecargar()
    expect(recargar).not.toHaveBeenCalled()
    expect(aviso()).toHaveTextContent('Hay algo que escribiste y no se guardó.')
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Seguir escribiendo' }))
    expect(envase).toHaveFocus()

    fireEvent.change(nombre, { target: { value: 'Gasas' } })
    await tocarRecargar()
    expect(recargar).not.toHaveBeenCalled()
    expect(aviso()).toHaveTextContent('Lo que anotaste de «Gasas» no se guardó.')
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Seguir escribiendo' }))
    expect(nombre).toHaveFocus()
  })

  it('en el formulario de Compartir (nombre, teléfono o días): no recarga, con el título genérico', async () => {
    window.history.replaceState(null, '', '/compartir')
    const campo = (texto: string) => ({ texto, etag: '"v1"', actualizado_en: null, actualizado_por: null })
    const ficha = { persona_id: PERSONA.id, campos: { rutina: campo('8:00 Desayuno.'), manejo_situaciones: campo('Hablarle despacio.'), red_apoyo: campo('Carmen.') }, secciones: {}, completitud: 100 }
    contexto = familiaFalsa({ ...contexto, ficha } as never)
    apiDeFamilia(() => ({ status: 500 }))
    enShell(<Compartir />)
    const nombre = await screen.findByRole('textbox', { name: '¿Quién te va a reemplazar?' })
    await volverALaPestana()
    expect(contexto.sinGuardar.current?.()).toBeNull()

    fireEvent.change(nombre, { target: { value: 'Rosa' } })
    await tocarRecargar()
    expect(recargar).not.toHaveBeenCalled()
    expect(aviso()).toHaveTextContent('Hay algo que escribiste y no se guardó.')
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Seguir escribiendo' }))
    expect(nombre).toHaveFocus()

    fireEvent.change(nombre, { target: { value: '' } })
    const telefono = screen.getByRole('textbox', { name: /Su teléfono/ })
    fireEvent.change(telefono, { target: { value: '+56 9 5555 0141' } })
    expect(contexto.sinGuardar.current?.()).not.toBeNull()
    fireEvent.change(telefono, { target: { value: '' } })
    expect(contexto.sinGuardar.current?.()).toBeNull()
  })

  it('al pasar a «sin guardar», la pantalla baja hasta la caja y después el foco va a «Seguir escribiendo» sin desplazar', async () => {
    const pasos: string[] = []
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      writable: true,
      value: function (this: Element, opciones?: ScrollIntoViewOptions) {
        if (this.hasAttribute('data-aviso-version')) pasos.push(`desplazar ${JSON.stringify(opciones)}`)
      },
    })
    const enfocar = vi.spyOn(HTMLElement.prototype, 'focus').mockImplementation(function (this: HTMLElement, opciones?: FocusOptions) {
      if (this.textContent === 'Seguir escribiendo') pasos.push(`foco ${JSON.stringify(opciones)}`)
    })
    contexto.sinGuardar.current = () => ({ texto: 'algo', donde: 'Quién es' })
    enShell()
    await volverALaPestana()
    await tocarRecargar()
    expect(pasos).toEqual(['desplazar {"block":"start","behavior":"smooth"}', 'foco {"preventScroll":true}'])
    enfocar.mockRestore()

    // Con movimiento reducido, inmediato.
    pasos.length = 0
    vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} }))
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Seguir escribiendo' }))
    await tocarRecargar()
    expect(pasos[0]).toBe('desplazar {"block":"start","behavior":"instant"}')
    delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView
  })

  it('en «Lo que escribiste no se guardó» (`textoPerdido`) el aviso espera; aparece en la pantalla siguiente', async () => {
    contexto = familiaFalsa({ ...contexto, textoPerdido: 'Le dicen Tito.' } as never)
    const { rerender } = montar(
      <MarcoSimple>
        <Titulo>Lo que escribiste no se guardó</Titulo>
      </MarcoSimple>,
    )
    await volverALaPestana()
    expect(fetchFalso).toHaveBeenCalled()
    expect(aviso()).toBeNull()
    expect(amable()).toBeEmptyDOMElement()

    contexto = familiaFalsa({ ...contexto, textoPerdido: null } as never)
    rerender(
      <>
        <RegionesVivas />
        <App>
          <MarcoSimple>
            <Titulo>Entrar</Titulo>
          </MarcoSimple>
        </App>
      </>,
    )
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60)
    })
    expect(aviso()).not.toBeNull()
    expect(amable()).toHaveTextContent(ANUNCIO_FAMILIA)
  })

  it('sin saber dónde, el título genérico', async () => {
    contexto.sinGuardar.current = () => ({ texto: 'algo' })
    enShell()
    await volverALaPestana()
    await tocarRecargar()
    expect(recargar).not.toHaveBeenCalled()
    expect(aviso()).toHaveTextContent('Hay algo que escribiste y no se guardó.')
  })
})

// ---------------------------------------------------------------- el relevo

describe('En el relevo', () => {
  it('aparece primero en `main`, al ancho de la columna, con la bajada del relevo, y espera en el campo del PIN', async () => {
    montar(
      <Marco ocupado={false}>
        <div className="mx-auto flex max-w-xl flex-col items-center gap-6 text-center">
          <Titulo>Escribe el PIN</Titulo>
          <label>
            PIN <input id="pin" type="text" inputMode="numeric" />
          </label>
          <button type="button">Abrir la ficha</button>
        </div>
      </Marco>,
    )
    const pin = screen.getByRole('textbox', { name: 'PIN' })
    act(() => pin.focus())
    await volverALaPestana()
    expect(fetchFalso).toHaveBeenCalled()
    expect(aviso()).toBeNull()

    act(() => screen.getByRole('button', { name: 'Abrir la ficha' }).focus())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60)
    })
    const caja = aviso()!
    expect(caja).not.toBeNull()
    expect(caja.parentElement!.tagName).toBe('MAIN')
    expect(caja.parentElement!.firstElementChild).toBe(caja)
    expect(caja).toHaveClass('mx-auto', 'max-w-xl', 'mb-6')
    expect(caja).toHaveTextContent(TITULO)
    expect(caja).toHaveTextContent(BAJADA_RELEVO)
    expect(caja).not.toHaveTextContent(BAJADA_FAMILIA)
    expect(amable()).toHaveTextContent(`${TITULO} ${BAJADA_RELEVO}`)
    expect(caja.contains(document.activeElement)).toBe(false)

    fireEvent.click(within(caja).getByRole('button', { name: 'Recargar' }))
    expect(recargar).toHaveBeenCalledTimes(1)
  })

  it('en la ficha el aviso toma el ancho de la grilla (`max-w-6xl`); en el PIN y los estados, la columna (`max-w-xl`)', async () => {
    const { rerender } = montar(
      <Marco ocupado={false}>
        <Titulo>Escribe el PIN</Titulo>
      </Marco>,
    )
    await volverALaPestana()
    expect(aviso()).toHaveClass('mx-auto', 'max-w-xl')
    expect(aviso()).not.toHaveClass('max-w-6xl')
    rerender(
      <>
        <RegionesVivas />
        <App>
          <Marco ocupado={false} anchoDelAviso="grilla">
            <Titulo>Ficha de María</Titulo>
          </Marco>
        </App>
      </>,
    )
    expect(aviso()).toHaveClass('mx-auto', 'max-w-6xl')
    expect(aviso()).not.toHaveClass('max-w-xl')
    // La caja queda a la izquierda dentro de la grilla: `Nota` no se centra.
    expect(aviso()!.firstElementChild).not.toHaveClass('mx-auto')
  })

  it('la página del relevo revisa la versión ella misma, y «Más tarde» deja el foco en su título', async () => {
    window.history.replaceState(null, '', '/r')
    apiRelevo.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
      const res: AxiosResponse = { data: { type: '/errores/no-autenticado', status: 401 }, status: 401, statusText: '', headers: {}, config, request: {} }
      throw new AxiosError('HTTP 401', AxiosError.ERR_BAD_REQUEST, config, {}, res)
    }
    render(
      <>
        <RegionesVivas />
        <PaginaRelevo />
      </>,
    )
    await waitFor(() => expect(document.getElementById('titulo-pagina')).not.toBeNull())
    await volverALaPestana()
    const caja = aviso()!
    expect(caja).not.toBeNull()
    expect(caja).toHaveTextContent(BAJADA_RELEVO)
    fireEvent.click(within(caja).getByRole('button', { name: 'Más tarde' }))
    expect(aviso()).toBeNull()
    expect(document.getElementById('titulo-pagina')).toHaveFocus()
    expect(recargar).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------- Boton secundario (revisión visual del 09-11)

describe('El botón secundario', () => {
  it('lleva el anillo `turquesa/80` y el relleno angosto `px-2` en toda la app', () => {
    render(<Boton variante="secundario">Seguir escribiendo</Boton>)
    const boton = screen.getByRole('button', { name: 'Seguir escribiendo' })
    expect(boton).toHaveClass('ring-turquesa/80', 'angosto:px-2', 'px-5')
    expect(boton).not.toHaveClass('ring-turquesa/70')
    expect(boton).not.toHaveClass('angosto:px-3')
  })
})

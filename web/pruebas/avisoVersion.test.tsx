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
import { CADA_MS, navegador, olvidarVersion, useRevisarVersion } from '../src/compartido/version'
import { MarcoAlta } from '../src/familia/Alta'
import { SECCIONES } from '../src/familia/datos'
import { EditorDeSeccion } from '../src/familia/EditorSeccion'
import { Insumos } from '../src/familia/Insumos'
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
    expect(within(caja).getByRole('button', { name: 'Recargar' })).toHaveClass('ring-turquesa/70')
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
    expect(seguir).toHaveClass('ring-turquesa/70')
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

  it('en «Compré» de un insumo: no recarga y nombra el formulario; sin cambios, recarga', async () => {
    window.history.replaceState(null, '', '/insumos')
    const hoy = new Date().toISOString().slice(0, 10)
    const toallitas = {
      id: '3c9d4e20-0000-4000-8000-0000000000c2',
      producto: null,
      nombre_libre: 'Toallitas húmedas',
      unidad: 'unidad',
      tasa_unidades: 3,
      tasa_dias: 1,
      stock_unidades: 30,
      stock_medido_en: hoy,
      dias_aviso: 7,
      fecha_quiebre_estimada: hoy,
      dias_restantes: 10,
      activo: true,
      actualizado_por: { id: 'u1', nombre: 'Carmen' },
      unidades_por_envase: null,
      etag: '"v1"',
    }
    apiDeFamilia((config) => {
      if (config.url?.endsWith('/consumo/por-acabarse')) return { status: 200, cuerpo: { items: [] } }
      if (config.url?.endsWith('/consumo')) return { status: 200, cuerpo: { items: [toallitas], siguiente_cursor: null } }
      return { status: 500 }
    })
    enShell(<Insumos />)
    await screen.findByRole('button', { name: 'Compré: Toallitas húmedas' })
    await volverALaPestana()
    expect(aviso()).not.toBeNull()

    // Abrir el panel sin escribir nada no es «sin guardar».
    fireEvent.click(screen.getByRole('button', { name: 'Compré: Toallitas húmedas' }))
    const panel = await screen.findByRole('group', { name: /¿Cuántas unidades compraste\?|compraste/ })
    const campo = within(panel).getByRole('textbox')
    // El panel lleva el foco a su campo a los 40 ms (MATU-51, 4).
    await waitFor(() => expect(campo).toHaveFocus())
    fireEvent.change(campo, { target: { value: '12' } })
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Recargar' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60)
    })
    expect(recargar).not.toHaveBeenCalled()
    expect(aviso()).toHaveTextContent('Lo que escribiste en «Compré: Toallitas húmedas» no se guardó.')
    expect(within(aviso()!).getByRole('button', { name: 'Seguir escribiendo' })).toHaveFocus()

    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Seguir escribiendo' }))
    expect(campo).toHaveFocus()
    expect(campo).toHaveValue('12')

    // Vuelve a dejarlo como estaba: ya no hay nada sin guardar y «Recargar» recarga.
    fireEvent.change(campo, { target: { value: '' } })
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Recargar' }))
    expect(recargar).toHaveBeenCalledTimes(1)
  })

  it('en «Anotar un insumo»: no recarga y nombra el formulario', async () => {
    window.history.replaceState(null, '', '/insumos')
    apiDeFamilia((config) => {
      if (config.url?.endsWith('/consumo/por-acabarse')) return { status: 200, cuerpo: { items: [] } }
      if (config.url?.endsWith('/consumo')) return { status: 200, cuerpo: { items: [], siguiente_cursor: null } }
      return { status: 500 }
    })
    enShell(<Insumos />)
    const anotar = await screen.findAllByRole('button', { name: 'Anotar un insumo' })
    await volverALaPestana()
    fireEvent.click(anotar[0])
    const nombre = await screen.findByRole('textbox', { name: '¿Qué insumo es?' })
    fireEvent.change(nombre, { target: { value: 'Gasas' } })
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Recargar' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60)
    })
    expect(recargar).not.toHaveBeenCalled()
    expect(aviso()).toHaveTextContent('Lo que escribiste en «Anotar un insumo» no se guardó.')
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Seguir escribiendo' }))
    expect(nombre).toHaveFocus()
  })

  it('sin nombre del lugar, el título genérico; el texto que «no se guardó» tras vencer la entrada también cuenta', async () => {
    contexto = familiaFalsa({ ...contexto, textoPerdido: 'Le dicen Tito.' } as never)
    montar(
      <MarcoSimple>
        <Titulo>Lo que escribiste no se guardó</Titulo>
      </MarcoSimple>,
    )
    await volverALaPestana()
    fireEvent.click(within(aviso()!).getByRole('button', { name: 'Recargar' }))
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

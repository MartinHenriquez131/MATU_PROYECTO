// MATU-84: «Me quedan» y el alta y la edición del insumo, también en envases (especificación
// docs/diseno/matu-84-me-quedan-envases.md v1.3). El panel con envase abre sin teclado (D4), la
// cuenta en vivo sin región viva, `recontar` con el total, un solo `PATCH` si se anota el envase en
// el panel (D5), el cambio de modo sin perder lo escrito, ml y g sin enlace (D2), el envase de 1
// (D6), «Compré» igual y el formulario con el campo del envase dentro del bloque (D3). Textos [L 30]
// tal cual. Datos sintéticos.
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { fechaCorta } from '../src/compartido/fechas'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { Insumos } from '../src/familia/Insumos'
import { problema422, type RespuestaFalsa } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'

const PERSONA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María' }
let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

const hoy = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Santiago', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
const sumar = (iso: string, n: number) => {
  const [a, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(a, m - 1, d + n)).toISOString().slice(0, 10)
}

const BASE = `/v1/personas-cuidadas/${PERSONA.id}/consumo`

type Perfil = Record<string, unknown> & { id: string; etag: string; nombre_libre: string }

const perfil = (id: string, nombre: string, cambios: Partial<Perfil> = {}): Perfil => ({
  id: `3c9d4e20-0000-4000-8000-0000000000${id}`,
  producto: null,
  nombre_libre: nombre,
  unidad: 'unidad',
  tasa_unidades: 4,
  tasa_dias: 1,
  stock_unidades: 24,
  stock_medido_en: '2026-11-04',
  dias_aviso: 7,
  fecha_quiebre_estimada: sumar(hoy, 6),
  dias_restantes: 6,
  activo: true,
  actualizado_por: { id: 'u1', nombre: 'Carmen' },
  unidades_por_envase: null,
  etag: '"v1"',
  ...cambios,
})

// Pañal con 20 por envase, toallitas sin envase, champú en sobres con 10 por caja, guantes con
// envase de 1, crema en ml con envase y talco en gramos.
const PANAL = perfil('c1', 'Pañal adulto talla M', { unidades_por_envase: 20 })
const TOALLITAS = perfil('c2', 'Toallitas húmedas', { tasa_unidades: 3, stock_unidades: 6 })
const CHAMPU = perfil('c3', 'Champú en sobre', { unidad: 'sobre', tasa_unidades: 1, stock_unidades: 30, unidades_por_envase: 10 })
const GUANTES = perfil('c4', 'Guantes desechables', { unidades_por_envase: 1 })
const CREMA = perfil('c5', 'Crema humectante', { unidad: 'ml', tasa_unidades: 50, tasa_dias: 7, stock_unidades: 500, unidades_por_envase: 250 })
const TALCO = perfil('c6', 'Talco', { unidad: 'g', tasa_unidades: 10, stock_unidades: 300 })
const TODOS = [PANAL, TOALLITAS, CHAMPU, GUANTES, CREMA, TALCO]

interface Pedida {
  linea: string
  cuerpo: unknown
  ifMatch: string | undefined
}

function api(escribir: (p: Pedida) => RespuestaFalsa) {
  const pedidas: Pedida[] = []
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const metodo = (config.method ?? 'get').toUpperCase()
    const p: Pedida = {
      linea: `${metodo} ${config.url ?? ''}`,
      cuerpo: typeof config.data === 'string' && config.data ? JSON.parse(config.data) : undefined,
      ifMatch: (config.headers?.['If-Match'] as string | undefined) ?? undefined,
    }
    pedidas.push(p)
    let r: RespuestaFalsa
    if (p.linea === `GET ${BASE}/por-acabarse`) r = { status: 200, cuerpo: { items: [] } }
    else if (p.linea === `GET ${BASE}`) r = { status: 200, cuerpo: { items: TODOS, siguiente_cursor: null } }
    else r = escribir(p)
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return pedidas
}

let escrituras: string[]

beforeEach(() => {
  contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol: 'cuidador' } as never)
  window.history.replaceState(null, '', '/insumos')
  escrituras = []
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
})

async function abrir(escribir: (p: Pedida) => RespuestaFalsa = () => ({ status: 500, cuerpo: { type: '/errores/error-interno', status: 500 } })) {
  const pedidas = api(escribir)
  render(
    <>
      <RegionesVivas />
      <Insumos />
    </>,
  )
  const u = userEvent.setup()
  await screen.findByRole('button', { name: 'Me quedan: Pañal adulto talla M' })
  return { pedidas, u }
}

const escritas = (pedidas: Pedida[]) => pedidas.filter((p) => !p.linea.startsWith('GET'))
const fila = (p: Perfil) => document.getElementById(`insumo-${p.id}`)!
const grupo = () => screen.getByRole('group', { name: '¿Cuántos quedan hoy, más o menos?' })
const envasesEnteros = () => screen.getByRole('textbox', { name: 'Envases enteros' })
const campoEnvase = () => screen.getByRole('textbox', { name: '¿Cuántas unidades trae cada envase?' })
const macizos = () => screen.getAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className))
const ok = (p: Perfil, cambios: Partial<Perfil> = {}): RespuestaFalsa => ({ status: 200, cuerpo: { ...p, stock_medido_en: hoy, etag: '"v2"', ...cambios } })

// ---------------------------------------------------------------- panel con envase guardado

describe('«Me quedan» con envase guardado (4.1)', () => {
  it('si la persona ya tocó un campo del panel antes de los 40 ms, el foco no se le quita y no se pierde lo escrito', async () => {
    const { pedidas, u } = await abrir()
    // Sin depender de la velocidad de la máquina: el temporizador de 40 ms con que el panel toma el
    // foco (D4) se retiene y corre entre el «5» y el «000», como pasó en el CI, más lento: quedaba «5».
    const original = window.setTimeout
    const retenidos: (() => void)[] = []
    const espia = vi.spyOn(window, 'setTimeout').mockImplementation(((fn: () => void, ms?: number) =>
      ms === 40 ? (retenidos.push(fn), 0) : original(fn, ms)) as typeof window.setTimeout)
    try {
      await u.click(screen.getByRole('button', { name: 'Me quedan: Pañal adulto talla M' }))
      await waitFor(() => expect(retenidos.length).toBeGreaterThan(0))
      await u.click(envasesEnteros())
      await u.keyboard('5')
      act(() => retenidos.splice(0).forEach((fn) => fn()))
      await u.keyboard('000')
    } finally {
      espia.mockRestore()
    }
    expect(envasesEnteros()).toHaveValue('5000')
    expect(envasesEnteros()).toHaveFocus()
    expect(grupo()).toHaveTextContent('En total, quedan unas 100.000 unidades.')
    expect(escritas(pedidas)).toEqual([])
  })


  it('abre en envases, vacío y con el foco en el panel, sin teclado (D4, criterio 1)', async () => {
    const { u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Pañal adulto talla M' }))
    await waitFor(() => expect(grupo()).toHaveFocus())
    // El foco no está en un campo: el teclado del teléfono no se abre.
    expect(document.activeElement?.tagName).not.toBe('INPUT')
    expect(envasesEnteros()).toHaveValue('')
    expect(screen.getByRole('textbox', { name: 'Unidades sueltas' })).toHaveValue('')
    expect(envasesEnteros()).toHaveAccessibleDescription('Cuenta los envases enteros y, a ojo, lo suelto. Reemplaza lo que calculábamos.')
    expect(grupo()).toHaveTextContent('envases de 20 unidades')
    // El envase ya está guardado: no se pide otra vez, y sin total todavía.
    expect(screen.queryByRole('textbox', { name: '¿Cuántas unidades trae cada envase?' })).toBeNull()
    expect(grupo()).not.toHaveTextContent('En total')
    expect(screen.queryByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })).toBeNull()
    // «Contar sueltos» bajo «Volver», y el único macizo es «Anotar lo que queda» (criterio 10).
    const enlace = within(grupo()).getByRole('button', { name: 'Contar sueltos' })
    expect(within(grupo()).getByRole('button', { name: 'Volver' }).compareDocumentPosition(enlace) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(enlace).toHaveClass('min-h-12', 'underline', 'self-start')
    expect(enlace).not.toHaveClass('bg-turquesa')
    expect(macizos()).toEqual([within(grupo()).getByRole('button', { name: 'Anotar lo que queda' })])
  })

  it('«+» dos veces y cinco: «En total, quedan unas 45 unidades.» y `recontar` con 45 (criterio 2)', async () => {
    const fecha = sumar(hoy, 11)
    const { pedidas, u } = await abrir(() => ok(PANAL, { stock_unidades: 45, fecha_quiebre_estimada: fecha, dias_restantes: 11, avisando: false, alerta_id: null }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Pañal adulto talla M' }))
    const mas = screen.getByRole('button', { name: 'Uno más: Envases enteros' })
    await u.click(mas)
    await u.click(mas)
    expect(grupo()).toHaveTextContent('envases de 20 unidades')
    for (let i = 0; i < 5; i++) await u.click(screen.getByRole('button', { name: 'Uno más: Unidades sueltas' }))
    expect(screen.getByRole('textbox', { name: 'Unidades sueltas' })).toHaveValue('5')
    const total = screen.getByText(/^En total, quedan unas/)
    expect(total).toHaveTextContent('En total, quedan unas 45 unidades.')
    // Sin región viva: el total va en la descripción del botón (8).
    expect(total.closest('[aria-live]')).toBeNull()
    expect(total).not.toHaveAttribute('role')
    const confirmar = screen.getByRole('button', { name: 'Anotar lo que queda' })
    expect(confirmar).toHaveAccessibleDescription('En total, quedan unas 45 unidades.')

    await u.click(confirmar)
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0]).toEqual({ linea: `POST ${BASE}/${PANAL.id}/recontar`, cuerpo: { stock_unidades: 45 }, ifMatch: '"v1"' })
    const hecho = await waitFor(() => document.getElementById(`hecho-${PANAL.id}`)!)
    // La confirmación en la unidad del insumo, sin la frase del envase, que ya estaba guardado (4.5).
    expect(hecho).toHaveTextContent(`Anotamos lo que queda de «Pañal adulto talla M»: 45 unidades. Alcanza para 11 días, hasta el ${fechaCorta(fecha)}.`)
    expect(hecho).not.toHaveTextContent('También anotamos')
    expect(escrituras).toEqual([])
    expect(window.location.pathname + window.location.search + window.location.hash).toBe('/insumos')
  })

  it('con un solo campo el otro vale 0; «−» en vacío deja 0 y «no queda nada» (criterio 3)', async () => {
    const { pedidas, u } = await abrir(() => ok(PANAL, { stock_unidades: 40 }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Pañal adulto talla M' }))
    await u.click(screen.getByRole('button', { name: 'Uno menos: Envases enteros' }))
    expect(envasesEnteros()).toHaveValue('0')
    expect(grupo()).toHaveTextContent('En total, no queda nada.')
    await u.click(screen.getByRole('button', { name: 'Uno más: Envases enteros' }))
    await u.click(screen.getByRole('button', { name: 'Uno más: Envases enteros' }))
    expect(grupo()).toHaveTextContent('En total, quedan unas 40 unidades.')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0].cuerpo).toEqual({ stock_unidades: 40 })
  })

  it('los dos vacíos: el error bajo «Envases enteros», con el foco, y nada se envía (criterio 3)', async () => {
    const { pedidas, u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Pañal adulto talla M' }))
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    expect(envasesEnteros()).toBeInvalid()
    expect(envasesEnteros()).toHaveAccessibleDescription(/Escribe cuántos quedan\. Si no queda nada, escribe 0\.$/)
    await waitFor(() => expect(envasesEnteros()).toHaveFocus())
    expect(escritas(pedidas)).toEqual([])
  })

  it('el total sobre 100.000: el error bajo «Envases enteros» y nada se envía', async () => {
    const { pedidas, u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Pañal adulto talla M' }))
    await u.type(envasesEnteros(), '5000')
    await u.type(screen.getByRole('textbox', { name: 'Unidades sueltas' }), '1')
    expect(grupo()).toHaveTextContent('En total, quedan unas 100.001 unidades.')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    expect(envasesEnteros()).toHaveAccessibleDescription(/Con eso quedarían más de 100\.000 unidades\. Revisa cuántos envases y sueltos anotaste\.$/)
    await waitFor(() => expect(envasesEnteros()).toHaveFocus())
    expect(escritas(pedidas)).toEqual([])
  })

  it('«+» no pasa de ⌊100.000 / u⌋ envases', async () => {
    const { u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Pañal adulto talla M' }))
    await u.type(envasesEnteros(), '5000')
    await u.click(screen.getByRole('button', { name: 'Uno más: Envases enteros' }))
    expect(envasesEnteros()).toHaveValue('5000')
  })

  it('422 cobertura_maxima: el error bajo «Envases enteros», con lo escrito', async () => {
    const { u } = await abrir(() => ({ status: 422, cuerpo: problema422({ campo: 'stock_unidades', tipo: 'cobertura_maxima' }) }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Pañal adulto talla M' }))
    await u.type(envasesEnteros(), '3')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    await waitFor(() => expect(envasesEnteros()).toBeInvalid())
    expect(envasesEnteros()).toHaveAccessibleDescription(/Con esa cantidad alcanzaría para más de 10 años\. Revisa cuántos quedan\.$/)
    await waitFor(() => expect(envasesEnteros()).toHaveFocus())
    expect(envasesEnteros()).toHaveValue('3')
    expect(document.body).not.toHaveTextContent('texto de la API')
  })

  it('en sobres: «Sobres sueltos», «envases de 10 sobres» y «quedan unos 12 sobres»', async () => {
    const { pedidas, u } = await abrir(() => ok(CHAMPU, { stock_unidades: 12 }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Champú en sobre' }))
    await u.click(screen.getByRole('button', { name: 'Uno más: Envases enteros' }))
    expect(grupo()).toHaveTextContent('envase de 10 sobres')
    await u.type(screen.getByRole('textbox', { name: 'Sobres sueltos' }), '2')
    expect(grupo()).toHaveTextContent('En total, quedan unos 12 sobres.')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0].cuerpo).toEqual({ stock_unidades: 12 })
  })
})

// ---------------------------------------------------------------- cambio de modo

describe('Cambiar de modo sin perder lo escrito (3, criterio 5)', () => {
  it('«Contar sueltos» lleva el total al campo único; «Contar en envases» con 65 deja 3 y 5', async () => {
    const { pedidas, u } = await abrir(() => ok(PANAL, { stock_unidades: 65 }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Pañal adulto talla M' }))
    await u.type(envasesEnteros(), '2')
    await u.type(screen.getByRole('textbox', { name: 'Unidades sueltas' }), '3')
    await u.click(screen.getByRole('button', { name: 'Contar sueltos' }))
    const unico = screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })
    expect(unico).toHaveValue('43')
    await waitFor(() => expect(unico).toHaveFocus())
    expect(unico).toHaveAccessibleDescription('Reemplaza lo que calculábamos. Si no queda nada, escribe 0.')
    // El envase sigue guardado: «Contar en envases» vuelve sin pedirlo.
    await u.clear(unico)
    await u.type(unico, '65')
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await waitFor(() => expect(envasesEnteros()).toHaveFocus())
    expect(envasesEnteros()).toHaveValue('3')
    expect(screen.getByRole('textbox', { name: 'Unidades sueltas' })).toHaveValue('5')
    expect(screen.queryByRole('button', { name: 'Contar en envases' })).toBeNull()
    expect(grupo()).toHaveTextContent('En total, quedan unas 65 unidades.')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0]).toEqual({ linea: `POST ${BASE}/${PANAL.id}/recontar`, cuerpo: { stock_unidades: 65 }, ifMatch: '"v1"' })
  })

  it('los dos vacíos vuelven a un campo vacío', async () => {
    const { u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Pañal adulto talla M' }))
    await u.click(screen.getByRole('button', { name: 'Contar sueltos' }))
    expect(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })).toHaveValue('')
  })
})

// ---------------------------------------------------------------- panel sin envase

describe('«Me quedan» sin envase (4.2)', () => {
  it('abre como siempre, con el foco en el campo y «Contar en envases» debajo', async () => {
    const { u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    const unico = screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })
    await waitFor(() => expect(unico).toHaveFocus())
    const enlace = within(grupo()).getByRole('button', { name: 'Contar en envases' })
    expect(enlace).toHaveClass('min-h-12', 'underline')
    expect(unico.compareDocumentPosition(enlace) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(macizos()).toEqual([within(grupo()).getByRole('button', { name: 'Anotar lo que queda' })])
  })

  it('«Contar en envases» pide el envase con el foco; el número pasa a sueltos; un solo `PATCH` con los dos (criterio 4, D5)', async () => {
    const fecha = sumar(hoy, 15)
    const { pedidas, u } = await abrir(() => ok(TOALLITAS, { stock_unidades: 45, unidades_por_envase: 20, fecha_quiebre_estimada: fecha, dias_restantes: 15 }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    await u.type(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' }), '5')
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))

    await waitFor(() => expect(campoEnvase()).toHaveFocus())
    expect(campoEnvase()).toHaveAccessibleDescription('Lo guardamos para la próxima vez y para la lista.')
    expect(campoEnvase()).toHaveAttribute('inputmode', 'numeric')
    expect(envasesEnteros()).toHaveValue('')
    expect(screen.getByRole('textbox', { name: 'Unidades sueltas' })).toHaveValue('5')
    // Mientras falta el envase, el sufijo dice solo «envases» y el total cuenta solo los sueltos.
    const sufijo = () => envasesEnteros().parentElement!.textContent
    expect(sufijo()).toBe('envases')
    expect(grupo()).toHaveTextContent('En total, quedan unas 5 unidades.')
    // El campo del envase va antes de los dos contadores.
    expect(campoEnvase().compareDocumentPosition(envasesEnteros()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

    await u.type(campoEnvase(), '20')
    expect(sufijo()).toBe('envases de 20 unidades')
    await u.click(screen.getByRole('button', { name: 'Uno más: Envases enteros' }))
    await u.click(screen.getByRole('button', { name: 'Uno más: Envases enteros' }))
    expect(grupo()).toHaveTextContent('En total, quedan unas 45 unidades.')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))

    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)).toEqual([{ linea: `PATCH ${BASE}/${TOALLITAS.id}`, cuerpo: { stock_unidades: 45, unidades_por_envase: 20 }, ifMatch: '"v1"' }])
    const hecho = await waitFor(() => document.getElementById(`hecho-${TOALLITAS.id}`)!)
    expect(hecho).toHaveTextContent(
      `Anotamos lo que queda de «Toallitas húmedas»: 45 unidades. Alcanza para 15 días, hasta el ${fechaCorta(fecha)}. También anotamos que cada envase trae 20 unidades.`,
    )
    await waitFor(() => expect(hecho).toHaveFocus())
    // La fila sale de la respuesta, y el bloque se pide otra vez para la marca (4.4).
    expect(fila(TOALLITAS)).toHaveTextContent('Alcanza para 15 días')
    expect(pedidas.filter((p) => p.linea === `GET ${BASE}/por-acabarse`).length).toBeGreaterThanOrEqual(2)
    expect(escrituras).toEqual([])
  })

  it('el envase vacío con envases enteros: el error bajo el envase, con el foco, y nada se envía', async () => {
    const { pedidas, u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.click(screen.getByRole('button', { name: 'Uno más: Envases enteros' }))
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    expect(campoEnvase()).toBeInvalid()
    expect(campoEnvase()).toHaveAccessibleDescription('Lo guardamos para la próxima vez y para la lista. Escribe cuántas unidades trae cada envase.')
    await waitFor(() => expect(campoEnvase()).toHaveFocus())
    expect(escritas(pedidas)).toEqual([])
  })

  it('1.2: con envases enteros y sin envase válido no hay total, ni en la descripción del botón (criterio 14)', async () => {
    const { u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    const confirmar = screen.getByRole('button', { name: 'Anotar lo que queda' })
    await u.click(screen.getByRole('button', { name: 'Uno más: Envases enteros' }))
    expect(grupo()).not.toHaveTextContent('En total')
    expect(confirmar).not.toHaveAttribute('aria-describedby')
    // Fuera de rango, igual.
    await u.type(campoEnvase(), '0')
    expect(grupo()).not.toHaveTextContent('En total')
    // Con el envase válido aparece, y con envases en 0 y sin envase cuenta los sueltos.
    await u.clear(campoEnvase())
    await u.type(campoEnvase(), '20')
    expect(grupo()).toHaveTextContent('En total, quedan unas 20 unidades.')
    expect(confirmar).toHaveAccessibleDescription('En total, quedan unas 20 unidades.')
    await u.clear(campoEnvase())
    await u.click(screen.getByRole('button', { name: 'Uno menos: Envases enteros' }))
    expect(envasesEnteros()).toHaveValue('0')
    expect(grupo()).toHaveTextContent('En total, no queda nada.')
  })

  it('P3: los dos enlaces van alineados a la izquierda', async () => {
    const { u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    expect(screen.getByRole('button', { name: 'Contar en envases' })).toHaveClass('text-left')
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    expect(screen.getByRole('button', { name: 'Contar sueltos' })).toHaveClass('text-left')
  })

  it('el envase fuera de rango: «Escribe un número de 1 a 10.000.»', async () => {
    const { pedidas, u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.type(campoEnvase(), '0')
    await u.type(screen.getByRole('textbox', { name: 'Unidades sueltas' }), '4')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    expect(campoEnvase()).toHaveAccessibleDescription(/Escribe un número de 1 a 10\.000\.$/)
    expect(escritas(pedidas)).toEqual([])
  })

  it('solo sueltos y sin envase: `recontar`, sin `PATCH`', async () => {
    const { pedidas, u } = await abrir(() => ok(TOALLITAS, { stock_unidades: 4 }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.type(screen.getByRole('textbox', { name: 'Unidades sueltas' }), '4')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0]).toEqual({ linea: `POST ${BASE}/${TOALLITAS.id}/recontar`, cuerpo: { stock_unidades: 4 }, ifMatch: '"v1"' })
  })

  it('el 422 del `PATCH` en `unidades_por_envase` va bajo el campo del envase', async () => {
    const { u } = await abrir(() => ({ status: 422, cuerpo: problema422({ campo: 'unidades_por_envase', tipo: 'less_than_equal' }) }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.type(campoEnvase(), '20')
    await u.click(screen.getByRole('button', { name: 'Uno más: Envases enteros' }))
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    await waitFor(() => expect(campoEnvase()).toBeInvalid())
    expect(campoEnvase()).toHaveAccessibleDescription(/Escribe un número de 1 a 10\.000\.$/)
    await waitFor(() => expect(campoEnvase()).toHaveFocus())
    expect(document.body).not.toHaveTextContent('texto de la API')
  })

  it('«Contar sueltos» descarta el envase escrito, que no se guardó, y lleva el total', async () => {
    const { pedidas, u } = await abrir(() => ok(TOALLITAS, { stock_unidades: 25 }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.type(campoEnvase(), '20')
    await u.type(envasesEnteros(), '1')
    await u.type(screen.getByRole('textbox', { name: 'Unidades sueltas' }), '5')
    await u.click(screen.getByRole('button', { name: 'Contar sueltos' }))
    expect(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })).toHaveValue('25')
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    expect(campoEnvase()).toHaveValue('')
    await u.click(screen.getByRole('button', { name: 'Contar sueltos' }))
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0].linea).toBe(`POST ${BASE}/${TOALLITAS.id}/recontar`)
    expect(escritas(pedidas)[0].cuerpo).toEqual({ stock_unidades: 25 })
  })

  it('D6: con envase de 1 abre como sin envase, y el campo del envase va vacío', async () => {
    const { u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Guantes desechables' }))
    await waitFor(() => expect(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })).toHaveFocus())
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    expect(campoEnvase()).toHaveValue('')
  })

  it.each([
    [CREMA, 'ml'],
    [TALCO, 'g'],
  ])('D2: en $1 no hay «Contar en envases» y sigue en la unidad (criterio 9)', async (p, unidad) => {
    const { u } = await abrir()
    await u.click(screen.getByRole('button', { name: `Me quedan: ${p.nombre_libre}` }))
    const unico = screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })
    await waitFor(() => expect(unico).toHaveFocus())
    expect(grupo()).toHaveTextContent(unidad)
    expect(screen.queryByRole('button', { name: 'Contar en envases' })).toBeNull()
    expect(screen.queryByRole('textbox', { name: 'Envases enteros' })).toBeNull()
  })
})

// ---------------------------------------------------------------- «Compré» igual

describe('«Compré» sigue igual', () => {
  it('con envase: en envases, en 1, con el foco en el panel y sin los enlaces nuevos', async () => {
    const { pedidas, u } = await abrir(() => ({ status: 200, cuerpo: { ...PANAL, stock_unidades: 44, etag: '"v2"', avisando: false, alerta_id: null } }))
    await u.click(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' }))
    const panel = screen.getByRole('group', { name: '¿Cuántos envases compraste?' })
    await waitFor(() => expect(panel).toHaveFocus())
    expect(within(panel).getByRole('textbox', { name: '¿Cuántos envases compraste?' })).toHaveValue('1')
    expect(within(panel).queryByRole('button', { name: /^Contar/ })).toBeNull()
    expect(within(panel).queryByRole('textbox', { name: 'Envases enteros' })).toBeNull()
    await u.click(within(panel).getByRole('button', { name: 'Anotar la compra' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0]).toEqual({ linea: `POST ${BASE}/${PANAL.id}/reponer`, cuerpo: { envases: 1 }, ifMatch: '"v1"' })
  })

  it('sin envase: en la unidad del insumo y sin «Contar en envases»', async () => {
    const { u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Compré: Toallitas húmedas' }))
    const campo = screen.getByRole('textbox', { name: '¿Cuántos compraste?' })
    await waitFor(() => expect(campo).toHaveFocus())
    expect(screen.queryByRole('button', { name: /^Contar/ })).toBeNull()
  })
})

// ---------------------------------------------------------------- el formulario

async function abrirFormulario(ruta: '/insumos/nuevo' | { cambiar: Perfil }, escribir: (p: Pedida) => RespuestaFalsa = () => ({ status: 500 })) {
  const pedidas = api(escribir)
  if (typeof ruta === 'string') window.history.replaceState(null, '', ruta)
  render(
    <>
      <RegionesVivas />
      <Insumos />
    </>,
  )
  const u = userEvent.setup()
  if (typeof ruta === 'string') await screen.findByRole('textbox', { name: '¿Qué insumo es?' })
  else await u.click(await screen.findByRole('button', { name: `Cambiar ${ruta.cambiar.nombre_libre}` }))
  return { pedidas, u }
}

const envases = () => screen.getAllByRole('textbox', { name: '¿Cuántas unidades trae cada envase?' })

describe('El alta (5.1)', () => {
  it('se ve como hoy hasta tocar «Contar en envases»; después el envase está en el bloque, una sola vez (criterio 6)', async () => {
    const { pedidas, u } = await abrirFormulario('/insumos/nuevo', () => ({ status: 201, cuerpo: { ...TOALLITAS, id: '3c9d4e20-0000-4000-8000-0000000000d1', nombre_libre: 'Gasas', stock_unidades: 65, unidades_por_envase: 20 } }))
    await u.type(screen.getByRole('textbox', { name: '¿Qué insumo es?' }), 'Gasas')
    const unico = screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })
    // Como hoy: el envase al final, después del aviso.
    expect(envases()).toHaveLength(1)
    const aviso = screen.getByRole('textbox', { name: '¿Con cuántos días de anticipación te avisamos?' })
    expect(aviso.compareDocumentPosition(envases()[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(envases()[0]).toHaveAccessibleDescription('Si lo anotas, la lista sugiere envases enteros. Puedes dejarlo en blanco.')

    await u.type(unico, '65')
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    // D3: el envase sube al bloque de lo que queda, con el foco, y nunca aparece dos veces.
    expect(envases()).toHaveLength(1)
    const envase = envases()[0]
    await waitFor(() => expect(envase).toHaveFocus())
    expect(envase).toHaveAccessibleDescription('Lo guardamos para la próxima vez y para la lista.')
    const bloque = screen.getByRole('group', { name: '¿Cuántos quedan hoy, más o menos?' })
    expect(bloque).toContainElement(envase)
    expect(envase.compareDocumentPosition(aviso) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(envasesEnteros()).toHaveAccessibleDescription('Cuenta los envases enteros y, a ojo, lo suelto.')
    expect(screen.getByRole('textbox', { name: 'Unidades sueltas' })).toHaveValue('65')

    await u.type(envase, '20')
    await u.clear(screen.getByRole('textbox', { name: 'Unidades sueltas' }))
    await u.type(screen.getByRole('textbox', { name: 'Unidades sueltas' }), '5')
    await u.type(envasesEnteros(), '3')
    expect(bloque).toHaveTextContent('En total, quedan unas 65 unidades.')
    // La vista previa usa el total (criterio 8): 65 / 1 al día.
    // La vista previa visible (el anuncio sr-only llega a los 500 ms y no se cuenta aquí).
    expect(screen.getByText(/^Así, alcanza para 65 días/, { selector: 'p' })).toBeInTheDocument()
    // «Guardar» sigue siendo el único macizo (criterio 10).
    expect(macizos()).toEqual([screen.getByRole('button', { name: 'Guardar' })])

    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0].linea).toBe(`POST ${BASE}`)
    expect(escritas(pedidas)[0].cuerpo).toMatchObject({ nombre_libre: 'Gasas', stock_unidades: 65, unidades_por_envase: 20 })
  })

  it('«Contar sueltos» lleva el total y el envase escrito vuelve al final con su valor', async () => {
    const { u } = await abrirFormulario('/insumos/nuevo')
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.type(envases()[0], '20')
    await u.type(envasesEnteros(), '2')
    await u.type(screen.getByRole('textbox', { name: 'Unidades sueltas' }), '1')
    await u.click(screen.getByRole('button', { name: 'Contar sueltos' }))
    const unico = screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })
    expect(unico).toHaveValue('41')
    await waitFor(() => expect(unico).toHaveFocus())
    expect(envases()).toHaveLength(1)
    expect(envases()[0]).toHaveValue('20')
    const aviso = screen.getByRole('textbox', { name: '¿Con cuántos días de anticipación te avisamos?' })
    expect(aviso.compareDocumentPosition(envases()[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('los dos vacíos al anotar: el error bajo «Envases enteros»; sin envase con envases: el error bajo el envase', async () => {
    const { pedidas, u } = await abrirFormulario('/insumos/nuevo')
    await u.type(screen.getByRole('textbox', { name: '¿Qué insumo es?' }), 'Gasas')
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(envasesEnteros()).toHaveAccessibleDescription(/Escribe cuántos quedan\. Si no queda nada, escribe 0\.$/)
    expect(envasesEnteros()).toHaveFocus()

    await u.type(envasesEnteros(), '2')
    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(envases()[0]).toHaveAccessibleDescription(/Escribe cuántas unidades trae cada envase\.$/)
    expect(envases()[0]).toHaveFocus()
    expect(escritas(pedidas)).toEqual([])
  })

  it('1.2: en el alta, con envases enteros y sin envase, no hay total (criterio 14)', async () => {
    const { u } = await abrirFormulario('/insumos/nuevo')
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.type(envasesEnteros(), '3')
    const bloque = screen.getByRole('group', { name: '¿Cuántos quedan hoy, más o menos?' })
    expect(bloque).not.toHaveTextContent('En total')
    await u.type(envases()[0], '20')
    expect(bloque).toHaveTextContent('En total, quedan unas 60 unidades.')
  })

  it('1.3: la vista previa se oculta con 1 envase y sin envase, y vuelve con el envase en 20 (criterio 8)', async () => {
    const { u } = await abrirFormulario('/insumos/nuevo')
    const previa = () => screen.queryByText(/^Así, /, { selector: 'p' })
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.click(screen.getByRole('button', { name: 'Uno más: Envases enteros' }))
    expect(envasesEnteros()).toHaveValue('1')
    expect(previa()).toBeNull()
    await u.type(envases()[0], '20')
    // 20 unidades a 1 al día.
    expect(previa()).toHaveTextContent(/^Así, alcanza para 20 días, hasta el/)
  })

  it('el total sobre 100.000 no se envía', async () => {
    const { pedidas, u } = await abrirFormulario('/insumos/nuevo')
    await u.type(screen.getByRole('textbox', { name: '¿Qué insumo es?' }), 'Gasas')
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.type(envases()[0], '10000')
    await u.type(envasesEnteros(), '11')
    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(envasesEnteros()).toHaveAccessibleDescription(/Con eso quedarían más de 100\.000 unidades\. Revisa cuántos envases y sueltos anotaste\.$/)
    expect(escritas(pedidas)).toEqual([])
  })
})

describe('La edición (5.2)', () => {
  it('con envase guardado: abre en envases con el envase a la vista y los dos vacíos; guardar así no cambia lo que queda (criterio 7)', async () => {
    const { pedidas, u } = await abrirFormulario({ cambiar: PANAL })
    expect(envasesEnteros()).toHaveValue('')
    expect(screen.getByRole('textbox', { name: 'Unidades sueltas' })).toHaveValue('')
    expect(envases()).toHaveLength(1)
    expect(envases()[0]).toHaveValue('20')
    expect(screen.getByRole('group', { name: '¿Cuántos quedan hoy, más o menos?' })).toContainElement(envases()[0])
    expect(envasesEnteros()).toHaveAccessibleDescription(
      `El ${fechaCorta('2026-11-04')} anotaste 24. Escribe cuántos quedan hoy, o déjalo en blanco si no lo sabes. Cuenta los envases enteros y, a ojo, lo suelto.`,
    )
    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByText('No había cambios.')).toBeInTheDocument()
    expect(escritas(pedidas)).toEqual([])
  })

  it('con envase guardado: el `PATCH` lleva el total, y el envase solo si cambió', async () => {
    const { pedidas, u } = await abrirFormulario({ cambiar: PANAL }, () => ok(PANAL, { stock_unidades: 47 }))
    await u.type(envasesEnteros(), '2')
    await u.type(screen.getByRole('textbox', { name: 'Unidades sueltas' }), '7')
    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0]).toEqual({ linea: `PATCH ${BASE}/${PANAL.id}`, cuerpo: { stock_unidades: 47 }, ifMatch: '"v1"' })
  })

  it('sin envase: abre en sueltos, con «Contar en envases» y el envase al final', async () => {
    await abrirFormulario({ cambiar: TOALLITAS })
    expect(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })).toHaveValue('')
    expect(screen.getByRole('button', { name: 'Contar en envases' })).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Envases enteros' })).toBeNull()
  })

  it('D6: con envase de 1 abre en sueltos, y el envase muestra 1 al final', async () => {
    await abrirFormulario({ cambiar: GUANTES })
    expect(screen.queryByRole('textbox', { name: 'Envases enteros' })).toBeNull()
    expect(envases()[0]).toHaveValue('1')
  })

  it('D2: en ml no hay «Contar en envases» (criterio 9)', async () => {
    await abrirFormulario({ cambiar: CREMA })
    expect(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Contar en envases' })).toBeNull()
    expect(screen.queryByRole('textbox', { name: 'Envases enteros' })).toBeNull()
  })
})

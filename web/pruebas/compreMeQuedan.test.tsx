// MATU-51: «Compré» y «Me quedan» en cada fila de Insumos, y «Ya lo resolví» en envases
// (especificación docs/diseno/matu-51-compre-me-quedan.md v1.2, contrato decisiones 136 a 148).
// Los cuerpos y el If-Match, sin interfaz optimista, cada error de la tabla de 5.4 y 5.5, el foco,
// los roles y «Sin seguir» sin botones, «Ya lo resolví» con envases y con 0 (sin cuerpo), un solo
// panel abierto a la vez y A5. Textos de la especificación, secciones 8 y 11, tal cual. Datos sintéticos.
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

type Perfil = Record<string, unknown> & { id: string; etag: string; activo: boolean; dias_restantes: number }

const perfil = (id: string, nombre: string, cambios: Partial<Perfil> = {}): Perfil => ({
  id: `3c9d4e20-0000-4000-8000-0000000000${id}`,
  producto: null,
  nombre_libre: nombre,
  unidad: 'unidad',
  tasa_unidades: 4,
  tasa_dias: 1,
  stock_unidades: 24,
  stock_medido_en: hoy,
  dias_aviso: 7,
  fecha_quiebre_estimada: sumar(hoy, 6),
  dias_restantes: 6,
  activo: true,
  actualizado_por: { id: 'u1', nombre: 'Carmen' },
  unidades_por_envase: null,
  etag: '"v1"',
  ...cambios,
})

// Pañal con 20 por envase y avisando; toallitas sin envase y avisando; champú en sobres; crema en ml; uno sin seguir.
const PANAL = perfil('c1', 'Pañal adulto talla M', { unidades_por_envase: 20 })
const TOALLITAS = perfil('c2', 'Toallitas húmedas', { tasa_unidades: 3, stock_unidades: 6, fecha_quiebre_estimada: sumar(hoy, 2), dias_restantes: 2 })
const CHAMPU = perfil('c3', 'Champú en sobre', { unidad: 'sobre', tasa_unidades: 1, stock_unidades: 30, fecha_quiebre_estimada: sumar(hoy, 30), dias_restantes: 30 })
const CREMA = perfil('c4', 'Crema humectante', { unidad: 'ml', tasa_unidades: 50, tasa_dias: 7, stock_unidades: 500, fecha_quiebre_estimada: sumar(hoy, 70), dias_restantes: 70 })
const SIN_SEGUIR = perfil('c5', 'Toallas de papel', { activo: false })

const enBloque = (p: Perfil, avisando = true) => ({ ...p, avisando, alerta_id: avisando ? '3c9d4e20-0000-4000-8000-00000000a001' : null })

interface Pedida {
  linea: string
  cuerpo: unknown
  ifMatch: string | undefined
}

/**
 * La API de Insumos: la lista y `por-acabarse` salen de `estado`, que cada prueba puede cambiar, y
 * las escrituras van a `escribir`. Devuelve todas las peticiones, con su cuerpo y su If-Match.
 */
function api(escribir: (p: Pedida) => RespuestaFalsa | Promise<RespuestaFalsa>, estado: { perfiles: Perfil[]; bloque: Perfil[] }) {
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
    if (p.linea === `GET ${BASE}/por-acabarse`) r = { status: 200, cuerpo: { items: estado.bloque.map((x) => enBloque(x)) } }
    else if (p.linea === `GET ${BASE}`) r = { status: 200, cuerpo: { items: estado.perfiles, siguiente_cursor: null } }
    else r = await escribir(p)
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return pedidas
}

const problema = (status: number, tipo: string, extra: Record<string, unknown> = {}): RespuestaFalsa => ({
  status,
  cuerpo: { type: `/errores/${tipo}`, title: 'TEXTO DE LA API QUE NO SE MUESTRA', detail: 'NO SE MUESTRA', status, ...extra },
})

let estado: { perfiles: Perfil[]; bloque: Perfil[] }
let escrituras: string[]

beforeEach(() => {
  contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol: 'cuidador' } as never)
  window.history.replaceState(null, '', '/insumos')
  estado = { perfiles: [PANAL, TOALLITAS, CHAMPU, CREMA, SIN_SEGUIR], bloque: [PANAL, TOALLITAS] }
  escrituras = []
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
})

async function abrir(escribir: (p: Pedida) => RespuestaFalsa | Promise<RespuestaFalsa> = () => problema(500, 'error-interno')) {
  const pedidas = api(escribir, estado)
  render(
    <>
      <RegionesVivas />
      <Insumos />
    </>,
  )
  const u = userEvent.setup()
  await screen.findByRole('button', { name: 'Compré: Pañal adulto talla M' })
  return { pedidas, u }
}

const escritas = (pedidas: Pedida[]) => pedidas.filter((p) => !p.linea.startsWith('GET'))
const fila = (nombre: string) => document.getElementById(`insumo-${[PANAL, TOALLITAS, CHAMPU, CREMA, SIN_SEGUIR].find((p) => p.nombre_libre === nombre)!.id}`)!
/** Los botones macizos (`turquesa`) de la pantalla: siempre uno solo (criterio visual 1 y A5). */
const macizos = () => screen.getAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className))
const anotarInsumo = () => screen.getByRole('button', { name: 'Anotar un insumo' })

/** Una respuesta que se resuelve cuando la prueba lo dice: para ver «Guardando…» y que nada cambie antes. */
function diferida() {
  let soltar: (r: RespuestaFalsa) => void = () => {}
  const promesa = new Promise<RespuestaFalsa>((ok) => (soltar = ok))
  return { promesa, soltar }
}

// ---------------------------------------------------------------- «Compré»

describe('«Compré»', () => {
  it('en envases: abre en 1 con el foco en el panel, «+» lo deja en 2, envía `envases` con If-Match y sin interfaz optimista', async () => {
    const espera = diferida()
    const { pedidas, u } = await abrir(() => espera.promesa)
    expect(macizos()).toEqual([anotarInsumo()])

    await u.click(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' }))
    const panel = screen.getByRole('group', { name: '¿Cuántos envases compraste?' })
    await waitFor(() => expect(panel).toHaveFocus())
    const campo = within(panel).getByRole('textbox', { name: '¿Cuántos envases compraste?' })
    expect(campo).toHaveValue('1')
    expect(campo).toHaveAccessibleDescription('Lo sumamos a lo que calculamos que queda hoy.')
    expect(panel).toHaveTextContent('envase de 20 unidades')
    // Los dos botones se van mientras el panel está abierto.
    expect(screen.queryByRole('button', { name: 'Compré: Pañal adulto talla M' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Me quedan: Pañal adulto talla M' })).toBeNull()

    await u.click(within(panel).getByRole('button', { name: 'Uno más: ¿Cuántos envases compraste?' }))
    expect(campo).toHaveValue('2')
    expect(panel).toHaveTextContent('envases de 20 unidades')
    // A5: con el panel abierto, el único macizo es su confirmar.
    expect(macizos()).toEqual([within(panel).getByRole('button', { name: 'Anotar la compra' })])

    await u.click(within(panel).getByRole('button', { name: 'Anotar la compra' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0]).toEqual({ linea: `POST ${BASE}/${PANAL.id}/reponer`, cuerpo: { envases: 2 }, ifMatch: '"v1"' })

    // Enviando: «Guardando…», «Volver» deshabilitado, el campo de solo lectura y la fila igual.
    const confirmar = within(panel).getByRole('button', { name: /Anotar la compra|Guardando…/ })
    expect(confirmar).toHaveAttribute('aria-busy', 'true')
    expect(confirmar).toHaveTextContent('Guardando…')
    expect(within(panel).getByRole('button', { name: 'Volver' })).toBeDisabled()
    expect(campo).toHaveAttribute('readonly')
    expect(fila('Pañal adulto talla M')).toHaveTextContent('Alcanza para 6 días')
    expect(fila('Pañal adulto talla M')).toHaveTextContent('Te estamos avisando')

    const fecha = sumar(hoy, 16)
    estado.bloque = [TOALLITAS]
    espera.soltar({ status: 200, cuerpo: enBloque({ ...PANAL, stock_unidades: 64, fecha_quiebre_estimada: fecha, dias_restantes: 16, etag: '"v2"' }, false), cabeceras: { etag: '"v2"' } })

    const confirmacion = await waitFor(() => {
      const el = document.getElementById(`hecho-${PANAL.id}`)
      expect(el).not.toBeNull()
      return el!
    })
    expect(confirmacion).toHaveAttribute('role', 'status')
    expect(confirmacion).toHaveTextContent(`Compra anotada para «Pañal adulto talla M»: 2 envases de 20 unidades. Ahora alcanza para 16 días, hasta el ${fechaCorta(fecha)}.`)
    // Espacio duro tras cada cifra, solo en pantalla (tercera revisión visual, P3).
    expect(confirmacion.textContent).toContain('2 envases de 20 unidades')
    await waitFor(() => expect(confirmacion).toHaveFocus())
    // La confirmación va dentro de la fila, que ya no está avisando y dice lo de la respuesta.
    expect(fila('Pañal adulto talla M')).toContainElement(confirmacion)
    expect(fila('Pañal adulto talla M')).toHaveTextContent('Alcanza para 16 días')
    expect(fila('Pañal adulto talla M')).not.toHaveTextContent('Te estamos avisando')
    expect(screen.getByRole('region', { name: 'Se acaban pronto' })).not.toHaveTextContent('Pañal adulto talla M')
    // Panel cerrado: vuelven los botones y «Anotar un insumo» vuelve a ser el macizo.
    expect(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' })).toBeInTheDocument()
    expect(macizos()).toEqual([anotarInsumo()])
    // Nada en el navegador ni en la URL.
    expect(escrituras).toEqual([])
    expect(window.location.pathname + window.location.search + window.location.hash).toBe('/insumos')
    expect(window.history.state).toBeNull()
  })

  it('en la unidad del insumo: abre vacío con el foco en el campo y envía `cantidad`', async () => {
    const fecha = sumar(hoy, 33)
    const { pedidas, u } = await abrir(() => ({ status: 200, cuerpo: enBloque({ ...CHAMPU, stock_unidades: 33, fecha_quiebre_estimada: fecha, dias_restantes: 33, etag: '"v2"' }, false) }))
    await u.click(screen.getByRole('button', { name: 'Compré: Champú en sobre' }))
    const campo = screen.getByRole('textbox', { name: '¿Cuántos sobres compraste?' })
    await waitFor(() => expect(campo).toHaveFocus())
    expect(campo).toHaveValue('')
    expect(screen.getByRole('group', { name: '¿Cuántos sobres compraste?' })).toHaveTextContent('sobres')

    await u.type(campo, '3')
    await u.keyboard('{Enter}')
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0]).toEqual({ linea: `POST ${BASE}/${CHAMPU.id}/reponer`, cuerpo: { cantidad: 3 }, ifMatch: '"v1"' })
    const hecho = await waitFor(() => document.getElementById(`hecho-${CHAMPU.id}`)!)
    expect(hecho).toHaveTextContent(`Compra anotada para «Champú en sobre»: 3 sobres. Ahora alcanza para 33 días, hasta el ${fechaCorta(fecha)}.`)
    await waitFor(() => expect(hecho).toHaveFocus())
  })

  it('las etiquetas sin envase: unidades, ml', async () => {
    const { u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Compré: Toallitas húmedas' }))
    expect(screen.getByRole('textbox', { name: '¿Cuántos compraste?' })).toHaveValue('')
    await u.click(screen.getByRole('button', { name: 'Compré: Crema humectante' }))
    expect(screen.getByRole('group', { name: '¿Cuántos ml compraste?' })).toHaveTextContent('ml')
  })

  it('valida en la pantalla antes de enviar: vacío y sobre 99 envases', async () => {
    const { pedidas, u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' }))
    const envases = screen.getByRole('textbox', { name: '¿Cuántos envases compraste?' })
    await u.clear(envases)
    await u.click(screen.getByRole('button', { name: 'Anotar la compra' }))
    expect(envases).toBeInvalid()
    expect(envases).toHaveAccessibleDescription('Lo sumamos a lo que calculamos que queda hoy. Escribe cuántos envases compraste, al menos 1.')
    await waitFor(() => expect(envases).toHaveFocus())
    await u.type(envases, '100')
    await u.click(screen.getByRole('button', { name: 'Anotar la compra' }))
    expect(envases).toHaveAccessibleDescription(/Escribe un número de 1 a 99 envases\.$/)
    expect(escritas(pedidas)).toEqual([])
  })

  it('valida en la pantalla antes de enviar: sin envase, vacío y sobre 10.000', async () => {
    const { pedidas, u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Compré: Toallitas húmedas' }))
    const unidades = screen.getByRole('textbox', { name: '¿Cuántos compraste?' })
    await u.click(screen.getByRole('button', { name: 'Anotar la compra' }))
    expect(unidades).toHaveAccessibleDescription(/Escribe cuántos compraste, al menos 1\.$/)
    await u.type(unidades, '10001')
    await u.click(screen.getByRole('button', { name: 'Anotar la compra' }))
    expect(unidades).toHaveAccessibleDescription(/Escribe un número hasta 10\.000\.$/)
    expect(escritas(pedidas)).toEqual([])
  })
})

// ---------------------------------------------------------------- «Me quedan»

describe('«Me quedan»', () => {
  it('con 0: abre vacío con el foco en el campo, envía `stock_unidades: 0` y dice que no queda', async () => {
    const { pedidas, u } = await abrir(() => ({ status: 200, cuerpo: enBloque({ ...TOALLITAS, stock_unidades: 0, fecha_quiebre_estimada: hoy, dias_restantes: 0, etag: '"v2"' }) }))
    // MATU-84: sin envase, en la unidad del insumo (con envase, ver envasesMeQuedan.test.tsx).
    await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    const campo = screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })
    await waitFor(() => expect(campo).toHaveFocus())
    expect(campo).toHaveValue('')
    expect(campo).toHaveAccessibleDescription('Reemplaza lo que calculábamos. Si no queda nada, escribe 0.')
    expect(screen.getByRole('group', { name: '¿Cuántos quedan hoy, más o menos?' })).toHaveTextContent('unidades')

    // Vacío no se envía.
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    expect(campo).toHaveAccessibleDescription(/Escribe cuántos quedan\. Si no queda nada, escribe 0\.$/)
    // «−» con el campo vacío deja 0.
    await u.click(screen.getByRole('button', { name: 'Uno menos: ¿Cuántos quedan hoy, más o menos?' }))
    expect(campo).toHaveValue('0')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))

    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0]).toEqual({ linea: `POST ${BASE}/${TOALLITAS.id}/recontar`, cuerpo: { stock_unidades: 0 }, ifMatch: '"v1"' })
    const hecho = await waitFor(() => document.getElementById(`hecho-${TOALLITAS.id}`)!)
    expect(hecho).toHaveTextContent('Anotamos que no queda «Toallitas húmedas». Cuando compres, anótalo con «Compré».')
    await waitFor(() => expect(hecho).toHaveFocus())
    expect(fila('Toallitas húmedas')).toHaveTextContent('Se acaba hoy')
  })

  it('con un número: «Anotamos lo que queda…» con los días y la fecha de la respuesta; 1 día en singular', async () => {
    const fecha = sumar(hoy, 1)
    const { u } = await abrir(() => ({ status: 200, cuerpo: enBloque({ ...CHAMPU, stock_unidades: 1, fecha_quiebre_estimada: fecha, dias_restantes: 1, etag: '"v2"' }) }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Champú en sobre' }))
    await u.type(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' }), '1')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    const hecho = await waitFor(() => document.getElementById(`hecho-${CHAMPU.id}`)!)
    expect(hecho).toHaveTextContent(`Anotamos lo que queda de «Champú en sobre»: 1 sobre. Alcanza para 1 día, hasta el ${fechaCorta(fecha)}.`)
  })

  it('sobre 100.000 no se envía', async () => {
    const { pedidas, u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
    const campo = screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' })
    await u.type(campo, '100001')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    expect(campo).toHaveAccessibleDescription(/Escribe un número hasta 100\.000\.$/)
    expect(escritas(pedidas)).toEqual([])
  })
})

// ---------------------------------------------------------------- errores (5.4 y 5.5)

describe('Errores de «Compré» y «Me quedan»', () => {
  const enCampo: [string, 'compre' | 'quedan', RespuestaFalsa, string][] = [
    ['422 stock_maximo', 'compre', { status: 422, cuerpo: problema422({ campo: 'envases', tipo: 'stock_maximo' }) }, 'Con esa compra quedarían más de 100.000 unidades. Revisa cuántos compraste.'],
    ['422 cobertura_maxima de «Compré»', 'compre', { status: 422, cuerpo: problema422({ campo: 'envases', tipo: 'cobertura_maxima' }) }, 'Con esa compra alcanzaría para más de 10 años. Revisa cuántos compraste.'],
    ['422 de rango en envases', 'compre', { status: 422, cuerpo: problema422({ campo: 'envases', tipo: 'less_than_equal' }) }, 'Escribe un número de 1 a 99 envases.'],
    ['422 cobertura_maxima de «Me quedan»', 'quedan', { status: 422, cuerpo: problema422({ campo: 'stock_unidades', tipo: 'cobertura_maxima' }) }, 'Con esa cantidad alcanzaría para más de 10 años. Revisa cuántos quedan.'],
    ['422 de rango en stock_unidades', 'quedan', { status: 422, cuerpo: problema422({ campo: 'stock_unidades', tipo: 'less_than_equal' }) }, 'Escribe un número hasta 100.000.'],
  ]
  it.each(enCampo)('%s: el error bajo el campo, con el foco, y el panel abierto con lo escrito', async (_, tipo, respuesta, texto) => {
    const { u } = await abrir(() => respuesta)
    if (tipo === 'compre') {
      await u.click(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' }))
      await u.click(screen.getByRole('button', { name: 'Anotar la compra' }))
    } else {
      await u.click(screen.getByRole('button', { name: 'Me quedan: Toallitas húmedas' }))
      await u.type(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' }), '90000')
      await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    }
    const campo = screen.getByRole('textbox', { name: tipo === 'compre' ? '¿Cuántos envases compraste?' : '¿Cuántos quedan hoy, más o menos?' })
    await waitFor(() => expect(campo).toBeInvalid())
    expect(campo).toHaveAccessibleDescription(new RegExp(`${texto.replace(/[.?]/g, '\\$&')}$`))
    await waitFor(() => expect(campo).toHaveFocus())
    expect(campo).toHaveValue(tipo === 'compre' ? '1' : '90000')
    expect(document.body).not.toHaveTextContent('NO SE MUESTRA')
  })

  it('«Ya lo resolví» con stock_maximo usa el texto de «Compré»', async () => {
    const { u } = await abrir(() => ({ status: 422, cuerpo: problema422({ campo: 'envases', tipo: 'stock_maximo' }) }))
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' }))
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' }))
    const campo = screen.getByRole('textbox', { name: '¿Compraste? ¿Cuántos envases?' })
    await waitFor(() => expect(campo).toHaveAccessibleDescription(/Con esa compra quedarían más de 100\.000 unidades\. Revisa cuántos compraste\.$/))
  })

  const enPanel: [string, RespuestaFalsa, string][] = [
    ['422 envases_o_cantidad', { status: 422, cuerpo: problema422({ campo: 'cantidad', tipo: 'envases_o_cantidad' }) }, 'No pudimos guardar. Revisa los datos y vuelve a intentarlo.'],
    ['422 sin_unidades_por_envase', { status: 422, cuerpo: problema422({ campo: 'envases', tipo: 'sin_unidades_por_envase' }) }, 'No pudimos guardar. Revisa los datos y vuelve a intentarlo.'],
    ['428 falta-version', problema(428, 'falta-version'), 'No pudimos guardar este insumo. Vuelve a abrirlo y guarda de nuevo. Lo que escribiste sigue aquí.'],
    ['red (503)', problema(503, 'no-disponible'), 'No pudimos guardar. Revisa tu conexión y vuelve a intentarlo.'],
  ]
  it.each(enPanel)('%s: el mensaje en el panel, con el foco, el panel abierto y sin reintentar solo', async (_, respuesta, texto) => {
    const { pedidas, u } = await abrir(() => respuesta)
    await u.click(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' }))
    await u.click(screen.getByRole('button', { name: 'Uno más: ¿Cuántos envases compraste?' }))
    await u.click(screen.getByRole('button', { name: 'Anotar la compra' }))
    const falla = await waitFor(() => document.getElementById(`falla-compre-${PANAL.id}`)!)
    expect(falla).toHaveAttribute('role', 'alert')
    expect(falla).toHaveTextContent(texto)
    await waitFor(() => expect(falla).toHaveFocus())
    expect(within(falla).queryByRole('button', { name: 'Ver cómo quedó' })).toBeNull()
    expect(screen.getByRole('textbox', { name: '¿Cuántos envases compraste?' })).toHaveValue('2')
    expect(screen.getByRole('button', { name: 'Anotar la compra' })).not.toHaveAttribute('aria-busy')
    expect(escritas(pedidas)).toHaveLength(1)
    expect(document.body).not.toHaveTextContent('NO SE MUESTRA')
  })

  it('404: cierra el panel, recarga la lista y el mensaje va arriba con el foco', async () => {
    const { pedidas, u } = await abrir(() => {
      estado.perfiles = estado.perfiles.filter((p) => p.id !== CHAMPU.id)
      return problema(404, 'no-encontrado')
    })
    const listasAntes = pedidas.filter((p) => p.linea === `GET ${BASE}`).length
    await u.click(screen.getByRole('button', { name: 'Compré: Champú en sobre' }))
    await u.type(screen.getByRole('textbox', { name: '¿Cuántos sobres compraste?' }), '2')
    await u.click(screen.getByRole('button', { name: 'Anotar la compra' }))
    const aviso = await waitFor(() => {
      const el = document.getElementById('aviso-insumos')
      expect(el).toHaveTextContent('Este insumo ya no está. Puede que alguien de tu familia lo haya eliminado.')
      return el!
    })
    expect(aviso).toHaveAttribute('role', 'alert')
    await waitFor(() => expect(aviso).toHaveFocus())
    await waitFor(() => expect(screen.queryByText('Champú en sobre')).toBeNull())
    expect(pedidas.filter((p) => p.linea === `GET ${BASE}`).length).toBe(listasAntes + 1)
    expect(screen.queryByRole('group')).toBeNull()
  })

  it('409 perfil-inactivo: el mensaje y «Ver cómo quedó», que deja la fila en «Sin seguir» sin botones y el foco en su «Seguir»', async () => {
    const { u } = await abrir(() => {
      estado.perfiles = estado.perfiles.map((p) => (p.id === PANAL.id ? { ...p, activo: false, etag: '"v2"' } : p))
      estado.bloque = [TOALLITAS]
      return problema(409, 'perfil-inactivo')
    })
    await u.click(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' }))
    await u.click(screen.getByRole('button', { name: 'Anotar la compra' }))
    const falla = await waitFor(() => document.getElementById(`falla-compre-${PANAL.id}`)!)
    expect(falla).toHaveTextContent('Alguien de tu familia dejó de seguir «Pañal adulto talla M» mientras lo anotabas. No anotamos nada. Si quieres anotarlo, vuelve a marcar «Seguir».')
    await waitFor(() => expect(falla).toHaveFocus())

    await u.click(within(falla).getByRole('button', { name: 'Ver cómo quedó' }))
    const seguir = document.getElementById(`seguir-${PANAL.id}`) as HTMLInputElement
    await waitFor(() => expect(seguir).not.toBeChecked())
    await waitFor(() => expect(document.getElementById(`seguir-${PANAL.id}`)).toHaveFocus())
    expect(screen.getByRole('region', { name: 'Sin seguir' })).toContainElement(fila('Pañal adulto talla M'))
    expect(screen.queryByRole('button', { name: 'Compré: Pañal adulto talla M' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Me quedan: Pañal adulto talla M' })).toBeNull()
  })

  it('412: «{autor} cambió … mientras lo anotabas» con «Ver cómo quedó», sin sumar nada', async () => {
    const actual = { ...CHAMPU, stock_unidades: 12, etag: '"v2"', actualizado_por: { id: 'u2', nombre: 'Rodrigo' } }
    const { pedidas, u } = await abrir(() => ({ ...problema(412, 'version-desactualizada', { actual }), cabeceras: { etag: '"v2"' } }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Champú en sobre' }))
    await u.type(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' }), '20')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    const falla = await waitFor(() => document.getElementById(`falla-quedan-${CHAMPU.id}`)!)
    expect(falla).toHaveTextContent('Rodrigo cambió «Champú en sobre» mientras lo anotabas. Revisa cómo quedó y vuelve a intentarlo.')
    await waitFor(() => expect(falla).toHaveFocus())
    // No se suma ni se reemplaza nada: la fila sigue como estaba.
    expect(fila('Champú en sobre')).toHaveTextContent('Quedan 30 sobres hoy.')

    estado.perfiles = estado.perfiles.map((p) => (p.id === CHAMPU.id ? actual : p))
    await u.click(within(falla).getByRole('button', { name: 'Ver cómo quedó' }))
    await waitFor(() => expect(fila('Champú en sobre')).toHaveTextContent('Quedan 12 sobres hoy.'))
    await waitFor(() => expect(fila('Champú en sobre')).toHaveFocus())
    expect(escritas(pedidas)).toHaveLength(1)
  })

  it('403 revision-vencida: la pantalla pasa al estado de permiso, con el foco en su título', async () => {
    const { u } = await abrir(() => problema(403, 'revision-vencida', { finalidad: 'consumo' }))
    await u.click(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' }))
    await u.click(screen.getByRole('button', { name: 'Anotar la compra' }))
    expect(await screen.findByText('Hay que renovar la autorización de los insumos de María.')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: 'Insumos' })).toHaveFocus())
    expect(screen.queryByRole('button', { name: /^Compré/ })).toBeNull()
  })
})

// ---------------------------------------------------------------- roles y «Sin seguir»

describe('Quién ve los botones', () => {
  it.each(['pagador', 'observador'] as const)('%s: ni «Compré» ni «Me quedan» en el DOM', async (rol) => {
    contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol } as never)
    api(() => problema(500, 'error-interno'), estado)
    render(<Insumos />)
    await screen.findByText('Pañal adulto talla M', { selector: 'span' })
    expect(screen.queryAllByRole('button', { name: /^(Compré|Me quedan)/ })).toEqual([])
    expect(document.body).not.toHaveTextContent(/Compré|Me quedan/)
    // La nota de «Cómo calculamos» para quien no anota no cambia de sentido; la corta, a 360 px.
    expect(screen.getByText('Es un cálculo con lo que anotó la familia.')).toBeInTheDocument()
  })

  it('admin y cuidador: los dos botones en cada insumo que se sigue, ninguno en «Sin seguir»', async () => {
    await abrir()
    for (const nombre of ['Pañal adulto talla M', 'Toallitas húmedas', 'Champú en sobre', 'Crema humectante']) {
      expect(within(fila(nombre)).getByRole('button', { name: `Compré: ${nombre}` })).toHaveTextContent(/^Compré$/)
      expect(within(fila(nombre)).getByRole('button', { name: `Me quedan: ${nombre}` })).toHaveTextContent(/^Me quedan$/)
    }
    expect(within(fila('Toallas de papel')).queryAllByRole('button', { name: /^(Compré|Me quedan)/ })).toEqual([])
    expect(screen.getByText('Es un cálculo con lo que anotaste. Si compraste o te quedan menos, anótalo con «Compré» o «Me quedan».')).toBeInTheDocument()
  })
})

describe('La nota de «Se acaban pronto» según el rol', () => {
  it.each([
    ['admin', 'Es una estimación con lo que anotaste.'],
    ['cuidador', 'Es una estimación con lo que anotaste.'],
    ['pagador', 'Es una estimación con lo que anotó la familia.'],
    ['observador', 'Es una estimación con lo que anotó la familia.'],
  ] as const)('%s: «%s»', async (rol, nota) => {
    contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol } as never)
    api(() => problema(500, 'error-interno'), estado)
    render(<Insumos />)
    await screen.findByRole('heading', { name: 'Se acaban pronto' })
    expect(screen.getByText(nota)).toBeInTheDocument()
    const otra = nota === 'Es una estimación con lo que anotaste.' ? 'Es una estimación con lo que anotó la familia.' : 'Es una estimación con lo que anotaste.'
    expect(screen.queryByText(otra)).toBeNull()
  })
})

// ---------------------------------------------------------------- «Ya lo resolví» (3.8)

// MATU-68 (docs/diseno/matu-68-ajustes.md, 1.2): una sola medida de casilla en toda la app, `size-6`
// (1,5 rem), como las de Compartir. La etiqueta de una línea va con `items-center`: sin `mt-0.5`.
describe('La casilla «Seguir»', () => {
  it('mide size-6, sin size-5 ni mt-0.5, dentro de su etiqueta de 48 px', async () => {
    await abrir()
    const seguir = document.getElementById(`seguir-${PANAL.id}`)!
    expect(seguir).toHaveAttribute('type', 'checkbox')
    expect(seguir).toHaveClass('size-6', 'shrink-0', 'accent-turquesa')
    expect(seguir).not.toHaveClass('size-5')
    expect(seguir).not.toHaveClass('mt-0.5')
    expect(seguir.closest('label')).toHaveClass('min-h-12', 'items-center', 'gap-3')
  })
})

describe('«Ya lo resolví» en envases', () => {
  // MATU-68 (docs/diseno/matu-68-ajustes.md, 2.3): en `angosto` los dos botones del panel van uno bajo
  // otro y a todo el ancho, con el relleno de su variante (`angosto:px-3` del principal y `angosto:px-2` del secundario, desde la revisión visual de MATU-67). Antes «Ya lo
  // resolví» llevaba `angosto:px-0.5!`, que dejaba 4 px entre el texto y el borde. jsdom no mide: la
  // prueba comprueba las clases.
  it('en angosto la fila va en columna y los dos botones a todo el ancho, sin achicar el relleno', async () => {
    const { u } = await abrir(() => ({ status: 200, cuerpo: enBloque(PANAL, false) }))
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' }))
    const panel = screen.getByRole('group', { name: '¿Compraste? ¿Cuántos envases?' })
    const boton = within(panel).getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' })
    const volver = within(panel).getByRole('button', { name: 'Volver' })
    expect(boton.parentElement).toBe(volver.parentElement)
    expect(boton.parentElement).toHaveClass('flex', 'flex-wrap', 'gap-3', 'angosto:flex-col', 'angosto:items-stretch')
    // Cada uno con el relleno angosto de su variante: el principal `px-3`, el secundario `px-2`.
    expect(boton).toHaveClass('angosto:w-full', 'angosto:px-3')
    expect(volver).toHaveClass('angosto:w-full', 'angosto:px-2')
    for (const b of [boton, volver]) expect(b.className).not.toMatch(/px-0\.5|\bp[xse]?-[\d.]+!/)
  })

  it('con envase: abre en 1 con el foco en el panel y envía `envases`', async () => {
    const { pedidas, u } = await abrir(() => ({ status: 200, cuerpo: enBloque({ ...PANAL, stock_unidades: 64, dias_restantes: 16, fecha_quiebre_estimada: sumar(hoy, 16), etag: '"v2"' }, false) }))
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' }))
    const panel = screen.getByRole('group', { name: '¿Compraste? ¿Cuántos envases?' })
    await waitFor(() => expect(panel).toHaveFocus())
    const campo = within(panel).getByRole('textbox')
    expect(campo).toHaveValue('1')
    expect(campo).toHaveAccessibleDescription('Si no compraste, déjalo en 0 y solo dejamos de avisarte.')
    expect(panel).toHaveTextContent('envase de 20 unidades')
    expect(macizos()).toEqual([within(panel).getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' })])

    await u.click(within(panel).getByRole('button', { name: 'Uno más: ¿Compraste? ¿Cuántos envases?' }))
    expect(panel).toHaveTextContent('envases de 20 unidades')
    estado.bloque = [TOALLITAS]
    await u.click(within(panel).getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0]).toEqual({ linea: `POST ${BASE}/${PANAL.id}/resolver`, cuerpo: { envases: 2 }, ifMatch: '"v1"' })
    const ok = await waitFor(() => document.getElementById('aviso-alertas')!)
    expect(ok).toHaveTextContent('Anotamos tu compra de Pañal adulto talla M: 2 envases de 20 unidades. Ahora alcanza para 16 días.')
    expect(ok.textContent).toContain('2 envases de 20 unidades')
  })

  it('con envase y 0: un toque en «−» y confirmar va sin cuerpo y solo descarta', async () => {
    const { pedidas, u } = await abrir(() => ({ status: 200, cuerpo: enBloque(PANAL, false) }))
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' }))
    const panel = screen.getByRole('group', { name: '¿Compraste? ¿Cuántos envases?' })
    await u.click(within(panel).getByRole('button', { name: 'Uno menos: ¿Compraste? ¿Cuántos envases?' }))
    expect(within(panel).getByRole('textbox')).toHaveValue('0')
    // El − no baja de 0.
    await u.click(within(panel).getByRole('button', { name: 'Uno menos: ¿Compraste? ¿Cuántos envases?' }))
    expect(within(panel).getByRole('textbox')).toHaveValue('0')
    estado.bloque = [TOALLITAS]
    await u.click(within(panel).getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0]).toEqual({ linea: `POST ${BASE}/${PANAL.id}/resolver`, cuerpo: undefined, ifMatch: '"v1"' })
    expect(await waitFor(() => document.getElementById('aviso-alertas')!)).toHaveTextContent(
      'Listo. No te avisaremos de nuevo por Pañal adulto talla M hasta que cambie la fecha estimada.',
    )
  })

  it('con envase sobre 99: el error de 0 a 99 y nada se envía', async () => {
    const { pedidas, u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' }))
    const campo = screen.getByRole('textbox', { name: '¿Compraste? ¿Cuántos envases?' })
    await u.clear(campo)
    await u.type(campo, '100')
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Pañal adulto talla M' }))
    expect(campo).toHaveAccessibleDescription(/Escribe un número de 0 a 99\. Si no compraste, déjalo en 0\.$/)
    expect(escritas(pedidas)).toEqual([])
  })

  it('sin envase: vacío con el foco en el campo; en blanco va sin cuerpo, con un número envía `cantidad`, sobre 10.000 no se envía', async () => {
    const { pedidas, u } = await abrir(() => ({ status: 200, cuerpo: enBloque({ ...TOALLITAS, stock_unidades: 30, dias_restantes: 10, etag: '"v2"' }, false) }))
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Toallitas húmedas' }))
    const campo = screen.getByRole('textbox', { name: '¿Compraste? ¿Cuántos?' })
    await waitFor(() => expect(campo).toHaveFocus())
    expect(campo).toHaveValue('')
    expect(campo).toHaveAccessibleDescription('Si no compraste, déjalo en blanco y solo dejamos de avisarte.')
    await u.type(campo, '10001')
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Toallitas húmedas' }))
    expect(campo).toHaveAccessibleDescription(/Escribe un número de 1 a 10\.000, o déjalo en blanco\.$/)
    expect(escritas(pedidas)).toEqual([])

    await u.clear(campo)
    await u.type(campo, '24')
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Toallitas húmedas' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0].cuerpo).toEqual({ cantidad: 24 })
    expect(await waitFor(() => document.getElementById('aviso-alertas')!)).toHaveTextContent('Anotamos tu compra de Toallitas húmedas: 24 unidades. Ahora alcanza para 10 días.')
  })

  it('sin envase y en blanco: va sin cuerpo', async () => {
    const { pedidas, u } = await abrir(() => ({ status: 200, cuerpo: enBloque(TOALLITAS, false) }))
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Toallitas húmedas' }))
    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Toallitas húmedas' }))
    await waitFor(() => expect(escritas(pedidas)).toHaveLength(1))
    expect(escritas(pedidas)[0].cuerpo).toBeUndefined()
  })
})

// ---------------------------------------------------------------- un panel a la vez y A5

describe('Un solo panel abierto en toda la pantalla', () => {
  it('abrir otro cierra el anterior sin guardar; «Volver» y Escape devuelven el foco al botón que lo abrió', async () => {
    const { pedidas, u } = await abrir()
    await u.click(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' }))
    expect(screen.getAllByRole('group')).toHaveLength(1)

    await u.click(screen.getByRole('button', { name: 'Me quedan: Champú en sobre' }))
    expect(screen.getAllByRole('group')).toHaveLength(1)
    expect(screen.getByRole('group', { name: '¿Cuántos quedan hoy, más o menos?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' })).toBeInTheDocument()
    expect(macizos()).toEqual([screen.getByRole('button', { name: 'Anotar lo que queda' })])

    await u.click(screen.getByRole('button', { name: 'Ya lo resolví: Toallitas húmedas' }))
    expect(screen.getAllByRole('group')).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Me quedan: Champú en sobre' })).toBeInTheDocument()
    expect(anotarInsumo().className).not.toMatch(/\bbg-turquesa\b/)

    // Escape cierra y devuelve el foco a «Ya lo resolví».
    fireEvent.keyDown(screen.getByRole('textbox', { name: '¿Compraste? ¿Cuántos?' }), { key: 'Escape' })
    expect(screen.queryAllByRole('group')).toEqual([])
    await waitFor(() => expect(screen.getByRole('button', { name: 'Ya lo resolví: Toallitas húmedas' })).toHaveFocus())
    expect(macizos()).toEqual([anotarInsumo()])

    // «Volver» devuelve el foco a «Me quedan» de esa fila.
    await u.click(screen.getByRole('button', { name: 'Me quedan: Crema humectante' }))
    await u.click(screen.getByRole('button', { name: 'Volver' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Me quedan: Crema humectante' })).toHaveFocus())
    expect(escritas(pedidas)).toEqual([])
  })

  it('abrir un panel borra la confirmación anterior', async () => {
    const { u } = await abrir(() => ({ status: 200, cuerpo: enBloque({ ...CHAMPU, stock_unidades: 40, dias_restantes: 40, fecha_quiebre_estimada: sumar(hoy, 40), etag: '"v2"' }, false) }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Champú en sobre' }))
    await u.type(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' }), '40')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    await waitFor(() => expect(document.getElementById(`hecho-${CHAMPU.id}`)).not.toBeNull())
    await u.click(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' }))
    expect(document.getElementById(`hecho-${CHAMPU.id}`)).toBeNull()
  })

  it('mientras guarda, no se abre otro panel ni Escape lo cierra', async () => {
    const espera = diferida()
    const { u } = await abrir(() => espera.promesa)
    await u.click(screen.getByRole('button', { name: 'Compré: Pañal adulto talla M' }))
    await u.click(screen.getByRole('button', { name: 'Anotar la compra' }))
    await u.click(screen.getByRole('button', { name: 'Compré: Champú en sobre' }))
    fireEvent.keyDown(screen.getByRole('textbox', { name: '¿Cuántos envases compraste?' }), { key: 'Escape' })
    expect(screen.getByRole('group', { name: '¿Cuántos envases compraste?' })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: '¿Cuántos sobres compraste?' })).toBeNull()
    espera.soltar(problema(503, 'no-disponible'))
    await waitFor(() => expect(document.getElementById(`falla-compre-${PANAL.id}`)).not.toBeNull())
  })
})

// Segunda revisión visual (P1): a 320 px con el texto al 200 %, la fecha de la confirmación se
// cortaba («01/05/202»). En `angosto:` el ícono se oculta, como el de la previa, y deja su ancho a la
// fecha. jsdom no mide: la prueba comprueba las clases. El estado sigue dicho con texto, no solo color.
describe('La confirmación en angosto', () => {
  it('el ícono se oculta en angosto y la fecha sigue entera y sin partirse', async () => {
    const fecha = sumar(hoy, 1)
    const { u } = await abrir(() => ({ status: 200, cuerpo: enBloque({ ...CHAMPU, stock_unidades: 1, fecha_quiebre_estimada: fecha, dias_restantes: 1, etag: '"v2"' }) }))
    await u.click(screen.getByRole('button', { name: 'Me quedan: Champú en sobre' }))
    await u.type(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' }), '1')
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    const hecho = await waitFor(() => document.getElementById(`hecho-${CHAMPU.id}`)!)

    const icono = hecho.querySelector('svg')!
    expect(icono).toHaveAttribute('aria-hidden')
    expect(icono).toHaveClass('angosto:hidden')
    expect(within(hecho).getByText(`${fechaCorta(fecha)}.`)).toHaveClass('whitespace-nowrap')
    expect(hecho).toHaveTextContent(/^Anotamos lo que queda de/)
  })
})

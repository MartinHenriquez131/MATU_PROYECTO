// MATU-128: «Lo que pasó con tu pedido» en el detalle de «Tus pedidos» (especificación
// docs/diseno/matu-128-lo-que-paso.md v1.0). La pantalla pide la ruta siempre y pinta lo que responde,
// nunca según el rol ni `vista`: 200 con cosas anotadas, 200 vacío, 404, 503 (N1), red o 500 (N2),
// el reintento (N3 y el foco) y el aviso N4 en la región viva, una sola vez y solo si llega tarde.
// Nada en el almacenamiento del navegador ni en la URL. Solo datos sintéticos.
import { act, cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { fijarGrupo } from '../src/compartido/api/sesion'
import type { CosaAnotada } from '../src/compartido/api/tusPedidos'
import type { PedidoElegido } from '../src/familia/estado'
import { PantallaTusPedidos } from '../src/familia/TusPedidos'
import { plazosConCarga } from './conCarga'
import { familiaFalsa } from './familiaFalsa'
import { comprobante, devolucion, GRUPO_ID, pago } from './pagoFalso'
import { apiPedido, conRegionesGlobales, NO_ENCONTRADO, persona, PERSONA_ID, problema, type Pedida, type Respuesta } from './pedidoFalso'
import { PEDIDO_2, retractos, seguimientoEntregado } from './tusPedidosFalso'

plazosConCarga()

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

let escrituras: string[] = []
beforeEach(() => {
  fijarGrupo(GRUPO_ID)
  escrituras = []
  for (const s of [localStorage, sessionStorage]) s.clear()
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
})

const DETALLE = '/insumos/tus-pedidos/pedido'
const ELEGIDO: PedidoElegido = { personaId: PERSONA_ID, pedidoId: PEDIDO_2, referencia: '4790' }
const TITULO = 'Lo que pasó con tu pedido'
const N1 = 'Por ahora no podemos revisar si anotamos algo sobre este pedido. Vuelve a intentarlo en unos minutos.'
const N2 = 'No pudimos revisar si anotamos algo sobre este pedido. Revisa tu conexión y vuelve a intentarlo.'
const N3 = 'No hay nada anotado sobre este pedido.'
const N4 = 'Más abajo está lo que pasó con tu pedido.'

function abrir(rol: Rol) {
  window.history.replaceState(null, '', DETALLE)
  const p = persona()
  const vista = rol === 'observador' || rol === 'pagador' ? { id: p.id, nombre: p.nombre } : p
  contexto = familiaFalsa({ persona: vista, personas: [vista], personaId: PERSONA_ID, grupoId: GRUPO_ID, rol, capa3: true, pedidoElegido: ELEGIDO, elegir: vi.fn(async () => {}), fijar: vi.fn() } as never)
  return conRegionesGlobales(<PantallaTusPedidos />)
}

/** Lo que anotó el equipo: «Faltó un producto», resuelto, y «No se pudo entregar», en revisión (especificación 4.1). */
const COSAS: CosaAnotada[] = [
  // 11:24 del 30/10 y 12:00 del 31/10 en Chile (UTC-3).
  { tipo: 'faltante', estado: 'resuelta', anotado_en: '2026-10-30T14:24:00Z', resuelto_en: '2026-10-31T15:00:00Z', nota: 'La farmacia no tenía una de las bolsas de pañales.', resolucion: 'devolvimos su precio a tu tarjeta.', nota_disponible: true },
  { tipo: 'entrega_fallida', estado: 'en_gestion', anotado_en: '2026-10-31T13:00:00Z', resuelto_en: null, nota: 'No había nadie en la casa a la hora de la entrega.', resolucion: null, nota_disponible: true },
]

type Manejador = Respuesta | ((p: Pedida) => Respuesta | Promise<Respuesta>)
const RUTA_LQP = 'GET /lo-que-paso$'

/** El entregado 4790 con su comprobante y lo devuelto, y `lo-que-paso` como se pida. */
function api(loQuePaso: Manejador | null, extra: Record<string, Manejador> = {}) {
  const c = comprobante({ referencia: '4790' })
  const devoluciones = [devolucion({ monto: 5290, ultimos4: '4051', hecha_en: '2026-11-04T19:00:00Z' })]
  return apiPedido(
    {
      'GET /seguimiento$': { status: 200, cuerpo: seguimientoEntregado() },
      'GET /pago$': { status: 200, cuerpo: pago({ pedido_id: PEDIDO_2, comprobante: { ...c, devoluciones }, devoluciones }) },
      'GET /retractos$': { status: 200, cuerpo: retractos() },
      ...(loQuePaso ? { [RUTA_LQP]: loQuePaso } : {}),
      ...extra,
    },
    { pedido: null },
  )
}
const con = (items: CosaAnotada[]): Respuesta => ({ status: 200, cuerpo: { lo_que_paso: items } })
const listo = () => screen.findByRole('heading', { level: 2, name: 'Cómo va' })
/** La región viva del detalle (7), distinta de las globales (`aria-live`). */
const region = () => document.querySelector<HTMLElement>('[role="status"].sr-only:not([aria-live])')!
const sigue = (a: Element, b: Element) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

function diferido() {
  let soltar: (r: Respuesta) => void = () => {}
  const promesa = new Promise<Respuesta>((r) => (soltar = r))
  return { manejador: () => promesa, soltar }
}

describe('MATU-128: «Lo que pasó con tu pedido» en el detalle', () => {
  it('200 con cosas anotadas: entre «Cómo va» y «Dinero devuelto», h2 y h3, estado con ícono y palabra, la fecha sin la hora', async () => {
    const a = api(con(COSAS))
    abrir('pagador')
    const h2 = await screen.findByRole('heading', { level: 2, name: TITULO })
    expect(h2).toHaveClass('titular', 'text-2xl')
    const seccion = h2.closest('section')!
    expect(seccion).toHaveAttribute('aria-labelledby', h2.id)
    // 2: el orden de la historia.
    expect(sigue(screen.getByRole('heading', { level: 2, name: 'Cómo va' }), h2)).toBe(true)
    expect(sigue(h2, screen.getByRole('heading', { level: 2, name: 'Dinero devuelto' }))).toBe(true)

    const [faltante, entrega] = within(seccion).getAllByRole('listitem')
    expect(faltante).toHaveClass('rounded-xl', 'bg-hoja', 'ring-1', 'ring-linea', 'min-w-0')
    expect(within(faltante).getByRole('heading', { level: 3, name: 'Faltó un producto' })).toBeVisible()
    const resuelto = within(faltante).getByText('Resuelto').closest('span.inline-flex')!
    expect(resuelto).toHaveClass('bg-ok-fondo')
    expect(resuelto.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-circle-check/)
    expect(resuelto.querySelector('svg')).toHaveAttribute('aria-hidden')
    // E1: «Lo anotamos el 30/10/2026.», sin «a las».
    expect(within(faltante).getByText(/^Lo anotamos el/)).toHaveTextContent(/^Lo anotamos el 30\/10\/2026\.$/)
    expect(within(faltante).getByText('30/10/2026')).toHaveClass('cifras')
    expect(within(faltante).getByText('30/10/2026').closest('time')).toHaveAttribute('dateTime', COSAS[0].anotado_en)
    expect(within(faltante).getByText('La farmacia no tenía una de las bolsas de pañales.')).toHaveClass('break-words', 'max-w-prose')
    expect(within(faltante).getByText('Cómo se resolvió:').tagName).toBe('B')
    expect(within(faltante).getByText('Cómo se resolvió:').parentElement).toHaveTextContent('Cómo se resolvió: devolvimos su precio a tu tarjeta.')
    expect(within(faltante).getByText(/^Se resolvió el/)).toHaveTextContent(/^Se resolvió el 31\/10\/2026\.$/)

    expect(within(entrega).getByRole('heading', { level: 3, name: 'No se pudo entregar' })).toBeVisible()
    const revisando = within(entrega).getByText('MATU lo está revisando').closest('span.inline-flex')!
    expect(revisando).toHaveClass('bg-tinta/7')
    expect(revisando.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-hourglass/)
    expect(within(entrega).queryByText('Cómo se resolvió:')).toBeNull()
    expect(within(entrega).queryByText(/^Se resolvió el/)).toBeNull()

    expect(document.body.textContent).not.toMatch(/a las \d{2}:\d{2}\.|incidente|incidencia|nota del equipo/i)
    // La ruta del contrato, con el grupo en `X-Grupo-Id`.
    const g = a.pedidas.find((p) => p.ruta.endsWith('/lo-que-paso'))!
    expect(g.ruta).toBe(`/v1/pedidos/${PEDIDO_2}/lo-que-paso`)
    expect(g.cabeceras['X-Grupo-Id']).toBe(GRUPO_ID)
  })

  it('en el orden que trae la API, y un tipo desconocido como «Otra cosa»', async () => {
    api(con([COSAS[1], { ...COSAS[0], tipo: 'que_no_conocemos' as never }]))
    abrir('pagador')
    const seccion = (await screen.findByRole('heading', { level: 2, name: TITULO })).closest('section')!
    expect(within(seccion).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['No se pudo entregar', 'Otra cosa'])
  })

  it('decisión 471: con `nota_disponible: false`, el tipo, el estado y las fechas, y la frase en vez de la nota', async () => {
    api(con([{ ...COSAS[0], nota: null, resolucion: null, nota_disponible: false }]))
    abrir('pagador')
    const fila = within((await screen.findByRole('heading', { level: 2, name: TITULO })).closest('section')!).getByRole('listitem')
    expect(within(fila).getByRole('heading', { level: 3, name: 'Faltó un producto' })).toBeVisible()
    expect(within(fila).getByText('Resuelto')).toBeVisible()
    expect(within(fila).getByText('La nota ya no está disponible: se borró con los datos de la persona.')).toHaveClass('text-tenue')
    expect(within(fila).queryByText('Cómo se resolvió:')).toBeNull()
    expect(within(fila).getByText(/^Lo anotamos el/)).toBeVisible()
    expect(within(fila).getByText(/^Se resolvió el/)).toBeVisible()
  })

  it('E4: 200 con la lista vacía: ni bloque, ni frase, ni aviso', async () => {
    const a = api(con([]))
    abrir('pagador')
    await listo()
    await waitFor(() => expect(a.pedidas.some((p) => p.ruta.endsWith('/lo-que-paso'))).toBe(true))
    await act(async () => {})
    expect(screen.queryByRole('heading', { name: TITULO })).toBeNull()
    expect(screen.queryByText(N3)).toBeNull()
    expect(screen.queryByText(N1)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Volver a intentar' })).toBeNull()
    expect(region()).toHaveTextContent('')
  })

  it('C5: no decide por el rol: «Paga» que no pagó este pedido recibe 404 y no ve nada', async () => {
    const a = api(NO_ENCONTRADO)
    abrir('pagador')
    await listo()
    await waitFor(() => expect(a.pedidas.some((p) => p.ruta.endsWith('/lo-que-paso'))).toBe(true))
    await act(async () => {})
    expect(screen.queryByRole('heading', { name: TITULO })).toBeNull()
    expect(screen.queryByText(/anotamos|anotado/)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Volver a intentar' })).toBeNull()
    expect(region()).toHaveTextContent('')
    // El resto del detalle, igual.
    expect(screen.getByRole('heading', { level: 2, name: 'Dinero devuelto' })).toBeVisible()
  })

  it.each(['admin', 'cuidador', 'pagador', 'observador'] as const)('C5: con %s, la pantalla pide la ruta y pinta lo que responde (200 o 404)', async (rol) => {
    for (const [respuesta, ve] of [
      [con(COSAS), true],
      [NO_ENCONTRADO, false],
    ] as const) {
      const a = api(respuesta)
      abrir(rol)
      await listo()
      await waitFor(() => expect(a.pedidas.filter((p) => p.ruta.endsWith('/lo-que-paso'))).toHaveLength(1))
      if (ve) expect(await screen.findByRole('heading', { level: 2, name: TITULO })).toBeVisible()
      else {
        await act(async () => {})
        expect(screen.queryByRole('heading', { name: TITULO })).toBeNull()
      }
      cleanup()
    }
  })

  it('MATU-116 y 8.14: quien «Se informa» y pagó (`vista: pagaste`) ve el bloque igual', async () => {
    api(con(COSAS), { 'GET /seguimiento$': { status: 200, cuerpo: seguimientoEntregado({ puede_cancelar: false, cancelar_motivo: 'rol' }) } })
    abrir('observador')
    expect(await screen.findByRole('heading', { level: 2, name: TITULO })).toBeVisible()
    expect(screen.getAllByRole('heading', { level: 3, name: /^(Faltó un producto|No se pudo entregar)$/ })).toHaveLength(2)
  })

  it('503: N1 con «Volver a intentar» secundario, sin el h2 y sin rol; el resto del detalle completo', async () => {
    api(problema(503, 'servicio-no-disponible'))
    abrir('pagador')
    const texto = await screen.findByText(N1)
    const nota = texto.closest('.bg-rocio')!
    expect(nota).not.toHaveAttribute('data-aviso')
    expect(nota.querySelector('.lucide-clock')).not.toBeNull()
    const boton = within(nota as HTMLElement).getByRole('button', { name: 'Volver a intentar' })
    expect(boton.className).not.toMatch(/\bbg-turquesa\b/)
    expect(screen.queryByRole('heading', { name: TITULO })).toBeNull()
    expect(document.body.textContent).not.toMatch(/se borró|no está disponible/)
    expect(screen.getByRole('heading', { level: 2, name: 'Cómo va' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 2, name: 'Dinero devuelto' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 2, name: 'Comprobante' })).toBeVisible()
    expect(sigue(screen.getByRole('heading', { level: 2, name: 'Cómo va' }), nota)).toBe(true)
    expect(sigue(nota, screen.getByRole('heading', { level: 2, name: 'Dinero devuelto' }))).toBe(true)
    expect(region()).toHaveTextContent('')
  })

  it.each([
    ['500', (): Respuesta => ({ status: 500 })],
    [
      'sin red',
      (): Respuesta => {
        throw new AxiosError('Network Error', AxiosError.ERR_NETWORK)
      },
    ],
  ])('%s: N2 con el ícono de la nube, sin el h2', async (_, manejador) => {
    api(manejador)
    abrir('pagador')
    const nota = (await screen.findByText(N2)).closest('.bg-rocio')!
    expect(nota.querySelector('.lucide-cloud-off')).not.toBeNull()
    expect(within(nota as HTMLElement).getByRole('button', { name: 'Volver a intentar' })).toBeVisible()
    expect(screen.queryByRole('heading', { name: TITULO })).toBeNull()
    expect(screen.queryByText(N1)).toBeNull()
  })

  it('reintento sin nada anotado: N3 recibe el foco; nada se anuncia', async () => {
    let n = 0
    api(() => (n++ === 0 ? problema(503, 'servicio-no-disponible') : con([])))
    abrir('pagador')
    await screen.findByText(N1)
    await userEvent.click(screen.getByRole('button', { name: 'Volver a intentar' }))
    const n3 = await screen.findByText(N3)
    expect(n3.tagName).toBe('P')
    expect(n3).toHaveClass('text-base', 'text-tenue')
    await waitFor(() => expect(n3).toHaveFocus())
    expect(screen.queryByText(N1)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Volver a intentar' })).toBeNull()
    expect(screen.queryByRole('heading', { name: TITULO })).toBeNull()
    expect(region()).toHaveTextContent('')
  })

  it('reintento con cosas anotadas: el bloque, y el foco va a su h2; «Cargando…» mientras tanto', async () => {
    let n = 0
    const segunda = diferido()
    api(() => (n++ === 0 ? { status: 500 } : segunda.manejador()))
    abrir('pagador')
    await screen.findByText(N2)
    await userEvent.click(screen.getByRole('button', { name: 'Volver a intentar' }))
    expect(await screen.findByRole('button', { name: /Cargando…/ })).toBeVisible()
    await act(async () => segunda.soltar(con(COSAS)))
    const h2 = await screen.findByRole('heading', { level: 2, name: TITULO })
    await waitFor(() => expect(h2).toHaveFocus())
    expect(screen.queryByText(N2)).toBeNull()
    // Después de un reintento, el foco ya dice dónde está: N4 no se suma.
    expect(region()).toHaveTextContent('')
  })

  it('7: si el bloque llega después de que se ve el detalle, N4 una sola vez y el foco no se mueve', async () => {
    const lento = diferido()
    const a = api(lento.manejador)
    abrir('pagador')
    await listo()
    const caja = region()
    expect(caja).toHaveTextContent('')
    let veces = 0
    const observador = new MutationObserver(() => {
      if (caja.textContent === N4) veces++
    })
    observador.observe(caja, { childList: true, characterData: true, subtree: true })
    await waitFor(() => expect(document.activeElement?.id).toBe('titulo-pagina'))
    const foco = document.activeElement
    await act(async () => lento.soltar(con(COSAS)))
    expect(await screen.findByRole('heading', { level: 2, name: TITULO })).toBeVisible()
    await waitFor(() => expect(caja).toHaveTextContent(N4))
    expect(document.activeElement).toBe(foco)
    // 4.9: al volver a la pestaña se lee de nuevo, sin anunciar otra vez.
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    await waitFor(() => expect(a.pedidas.filter((p) => p.ruta.endsWith('/lo-que-paso')).length).toBeGreaterThanOrEqual(2))
    await act(async () => {})
    observador.disconnect()
    expect(veces).toBe(1)
    expect(caja).toHaveTextContent(N4)
    expect(document.activeElement).toBe(foco)
  })

  it('7: si llega junto con el seguimiento, es parte de la página: no se anuncia', async () => {
    api(con(COSAS))
    abrir('pagador')
    expect(await screen.findByRole('heading', { level: 2, name: TITULO })).toBeVisible()
    await act(async () => {})
    expect(region()).toHaveTextContent('')
  })

  it('nada al almacenamiento del navegador ni a la URL, en ningún estado', async () => {
    for (const r of [con(COSAS), con([]), NO_ENCONTRADO, problema(503, 'servicio-no-disponible')]) {
      api(r)
      abrir('pagador')
      await listo()
      await act(async () => {})
      cleanup()
    }
    expect(escrituras).toEqual([])
    for (const s of [localStorage, sessionStorage]) expect(s.length).toBe(0)
    expect(window.location.pathname).toBe(DETALLE)
    expect(window.location.search + window.location.hash).toBe('')
    expect(window.history.state).toBeNull()
  })
})

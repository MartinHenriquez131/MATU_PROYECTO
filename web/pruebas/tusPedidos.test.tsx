// MATU-92: «Tus pedidos» (especificación docs/diseno/matu-92-tus-pedidos.md v1.1). La lista por rol y
// la del observador, el vacío, el error y «Ver más»; el detalle con las partes, los faltantes y el
// dinero devuelto; que nunca aparece un código; arrepentirse (elegir, vista previa, 201, ya pedido,
// red); el plazo; cancelar (confirmar, 409 `estado-pedido`, 409 `ya-se-prepara`, red) y la
// `Idempotency-Key` reutilizada. Sin interfaz optimista: cada estado es lo que respondió la API falsa.
// Solo datos sintéticos.
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { fijarGrupo } from '../src/compartido/api/sesion'
import type { PedidoElegido } from '../src/familia/estado'
import { PantallaTusPedidos } from '../src/familia/TusPedidos'
import { vistaPrevia, bajarAlDisponible, plazoEnChile } from '../src/familia/tusPedidosComun'
import { familiaFalsa } from './familiaFalsa'
import { apiPedido, conRegionesGlobales, NO_ENCONTRADO, PEDIDO_ID, persona, PERSONA_ID, problema, type Pedida, type Respuesta } from './pedidoFalso'
import { comprobante, comprobanteAjeno, devolucion, GRUPO_ID, pago, PANAL_C, SUPLEMENTO_C } from './pagoFalso'
import {
  entregado,
  fila,
  filaObservador,
  LINEA_PANAL,
  LINEA_SUPLEMENTO,
  lineaParaRetracto,
  lista,
  PEDIDO_2,
  PEDIDO_3,
  retracto,
  retractos,
  seguimiento,
  seguimientoEntregado,
} from './tusPedidosFalso'
import { fueraDeRegiones, plazosConCarga } from './conCarga'

// MATU-119: con la máquina cargada, abrir la lista y el detalle pasaba el segundo de las esperas o los 15 s de tope.
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
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})

const LISTA = '/insumos/tus-pedidos'
const DETALLE = '/insumos/tus-pedidos/pedido'
const ARREPENTIRME = '/insumos/tus-pedidos/arrepentirme'
const ELEGIDO_1: PedidoElegido = { personaId: PERSONA_ID, pedidoId: PEDIDO_ID, referencia: '4821' }
const ELEGIDO_2: PedidoElegido = { personaId: PERSONA_ID, pedidoId: PEDIDO_2, referencia: '4790' }

/** La pantalla con el contexto de cada rol. `fijar` cambia el contexto, como lo haría ProveedorFamilia. */
function abrir(rol: Rol, ruta: string, elegido: PedidoElegido | null = null) {
  window.history.replaceState(null, '', ruta)
  const p = persona()
  const vista = rol === 'observador' || rol === 'pagador' ? { id: p.id, nombre: p.nombre } : p
  contexto = familiaFalsa({
    persona: vista,
    personas: [vista],
    personaId: PERSONA_ID,
    grupoId: GRUPO_ID,
    rol,
    capa3: true,
    pedidoElegido: elegido,
    elegir: vi.fn(async () => {}),
    fijar: vi.fn((c: Record<string, unknown>) => {
      contexto = { ...contexto, ...c } as typeof contexto
    }),
  } as never)
  return conRegionesGlobales(<PantallaTusPedidos />)
}

type Rutas = Record<string, Respuesta | ((p: Pedida) => Respuesta | Promise<Respuesta>)>
const api = (r: Rutas) => apiPedido(r, { pedido: null })
/** El nombre accesible, con un espacio después de cada coma (jsdom recorta el del separador `sr-only`). */
const conComas = (texto: string) => new RegExp(`^${texto.replace(/[.*+?^${}()|[\]\\$]/g, '\\$&').replace(/([,.]) /g, '$1\\s?')}$`)
const macizos = () => screen.queryAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className))
const h1 = (nombre: string | RegExp) => screen.findByRole('heading', { level: 1, name: nombre })
const claves = (pedidas: Pedida[], fin: string) => pedidas.filter((p) => p.metodo === 'POST' && p.ruta.endsWith(fin)).map((p) => p.cabeceras['Idempotency-Key'])

// ---------------------------------------------------------------- la lista

describe('La lista (3)', () => {
  it('admin: cada pedido es un botón con su texto en orden, el estado con palabra e ícono, el total y lo devuelto', async () => {
    const a = api({
      'GET /personas-cuidadas/[^/]+/pedidos$': {
        status: 200,
        cuerpo: lista([fila(), entregado({ resumen_productos: { primero: 'Pañal adulto M x30', otros: 2 } }), fila({ pedido_id: PEDIDO_3, referencia: '4655', pagado_en: '2026-10-20T15:00:00Z', estado: 'cancelado_con_devolucion', total: 22980, devuelto: 22980, devuelto_todo: true, puede_cancelar: false, cancelar_motivo: 'cancelado' })]),
      },
    })
    abrir('admin', LISTA)
    expect(await h1('Tus pedidos')).toBeVisible()
    expect(screen.getByText('Los pedidos pagados de María, de los últimos 2 años.')).toBeVisible()
    const filas = await screen.findAllByRole('button', { name: /^Pedido \d+/ })
    expect(filas).toHaveLength(3)
    expect(filas[0]).toHaveAccessibleName(conComas('Pedido 4821, 11/11/2026, Pagado, Lo estamos enviando al comercio. Puede tardar unos minutos. Total pagado: $57.460'))
    // P3-1: sin la coma de más después de la frase, y el «·» no se lee.
    expect(filas[0].textContent).not.toContain('.,')
    for (const f of filas) for (const s of f.querySelectorAll('span')) if (s.textContent === '\u00a0·\u00a0') expect(s).toHaveAttribute('aria-hidden')
    expect(filas[0].querySelector('svg')!.getAttribute('class')).toMatch(/lucide-check/)
    expect(filas[1]).toHaveAccessibleName(conComas('Pedido 4790, 02/11/2026, Entregado el 04/11/2026, Pañal adulto M x30 y 2 productos más, Total pagado: $31.980, Devuelto: $5.290'))
    expect(filas[2]).toHaveTextContent('Devolvimos $22.980, envío incluido, a la tarjeta con que se pagó.')
    // Sin flecha ni ChevronRight, y ningún macizo en la lista.
    for (const f of filas) expect(f.querySelector('.lucide-chevron-right')).toBeNull()
    expect(macizos()).toEqual([])
    // La pestaña «Tus pedidos», activa.
    expect(screen.getByRole('link', { name: 'Tus pedidos' })).toHaveAttribute('aria-current', 'page')
    const g = a.pedidas.find((p) => p.ruta.endsWith('/pedidos'))!
    expect(g.ruta).toBe(`/v1/personas-cuidadas/${PERSONA_ID}/pedidos`)
  })

  it('el cancelado con la devolución en curso dice «Estamos devolviendo» (D2)', async () => {
    api({ 'GET /pedidos$': { status: 200, cuerpo: lista([fila({ estado: 'cancelado_con_devolucion', total: 22980, devuelto: 0, devuelto_todo: false })]) } })
    abrir('cuidador', LISTA)
    expect(await screen.findByRole('button', { name: /Pedido 4821/ })).toHaveTextContent('Estamos devolviendo $22.980, envío incluido, a la tarjeta con que se pagó.')
  })

  it('tocar una fila abre el detalle con el pedido en memoria, sin id en la dirección', async () => {
    api({ 'GET /pedidos$': { status: 200, cuerpo: lista([fila()]) } })
    abrir('admin', LISTA)
    await userEvent.click(await screen.findByRole('button', { name: /Pedido 4821/ }))
    expect(contexto.pedidoElegido).toEqual(ELEGIDO_1)
    expect(window.location.pathname).toBe(DETALLE)
    expect(window.location.href).not.toContain(PEDIDO_ID)
    expect(window.location.search + window.location.hash).toBe('')
    expect(escrituras).toEqual([])
  })

  it('observador (D-92-1, C3): la fecha, «Pagado» y los productos, en una fila que no se abre', async () => {
    api({ 'GET /pedidos$': { status: 200, cuerpo: lista([filaObservador(), filaObservador({ pedido_id: PEDIDO_2, productos: [], productos_borrados: true, resumen_productos: null })]) } })
    abrir('observador', LISTA)
    expect(await screen.findByText('Quien administra el grupo, quien cuida a María y quien paga ven el detalle.')).toBeVisible()
    const ul = screen.getByRole('list', { name: 'Tus pedidos' })
    const filas = within(ul).getAllByRole('listitem').filter((li) => li.parentElement === ul)
    expect(filas).toHaveLength(2)
    expect(within(ul).queryAllByRole('button')).toEqual([])
    expect(filas[0]).toHaveTextContent('11/11/2026')
    expect(within(filas[0]).getByText('Pagado')).toBeVisible()
    expect(within(filas[0]).getByText(/Pañal adulto M x30/).closest('li')).toHaveTextContent('2 × Pañal adulto M x30')
    expect(filas[1]).toHaveTextContent('De este pedido guardamos solo lo que se pagó y lo que se devolvió.')
    expect(ul).not.toHaveTextContent(/Pedido 4821|Total pagado|\$|Lo estamos enviando/)
  })

  it('vacío: el texto con el nombre de pila, e «Ir a tu pedido» solo para admin y cuidador', async () => {
    api({ 'GET /pedidos$': { status: 200, cuerpo: lista([]) } })
    abrir('admin', LISTA)
    expect(await screen.findByText('Todavía no hay pedidos pagados para María.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Ir a tu pedido' })).toBeVisible()
  })

  it('vacío para quien paga: sin «Ir a tu pedido»', async () => {
    api({ 'GET /pedidos$': { status: 200, cuerpo: lista([]) } })
    abrir('pagador', LISTA)
    expect(await screen.findByText('Todavía no hay pedidos pagados para María.')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Ir a tu pedido' })).toBeNull()
  })

  it('error al traer: se anuncia, «Volver a intentar» es el único macizo y vuelve a pedir', async () => {
    let n = 0
    api({ 'GET /pedidos$': () => (n++ === 0 ? { status: 500 } : { status: 200, cuerpo: lista([fila()]) }) })
    const { urgente } = abrir('admin', LISTA)
    const texto = 'No pudimos traer tus pedidos. Revisa tu conexión y vuelve a intentarlo.'
    expect(await screen.findByText(texto, { selector: ':not([aria-live])' })).toBeVisible()
    await waitFor(() => expect(urgente).toHaveTextContent(texto))
    expect(macizos().map((b) => b.textContent)).toEqual(['Volver a intentar'])
    await userEvent.click(screen.getByRole('button', { name: 'Volver a intentar' }))
    expect(await screen.findByRole('button', { name: /Pedido 4821/ })).toBeVisible()
  })

  it('«Ver más pedidos» pide con el cursor, suma las filas y lleva el foco a la primera nueva', async () => {
    const a = api({
      'GET /pedidos$': (p) => {
        void p
        const pedidas = a.pedidas.filter((x) => x.ruta.endsWith('/pedidos'))
        return pedidas.length === 1 ? { status: 200, cuerpo: lista([fila()], 'cursor-2') } : { status: 200, cuerpo: lista([entregado()]) }
      },
    })
    abrir('admin', LISTA)
    const mas = await screen.findByRole('button', { name: 'Ver más pedidos' })
    expect(mas.className).not.toMatch(/\bbg-turquesa\b/)
    await userEvent.click(mas)
    const nueva = await screen.findByRole('button', { name: /Pedido 4790/ })
    await waitFor(() => expect(nueva).toHaveFocus())
    expect(screen.queryByRole('button', { name: 'Ver más pedidos' })).toBeNull()
  })

  it('«Ver más» sin conexión: el error bajo el botón y las filas siguen', async () => {
    let n = 0
    api({ 'GET /pedidos$': () => (n++ === 0 ? { status: 200, cuerpo: lista([fila()], 'cursor-2') } : { status: 503 }) })
    const { urgente } = abrir('admin', LISTA)
    await userEvent.click(await screen.findByRole('button', { name: 'Ver más pedidos' }))
    const texto = 'No pudimos traer más pedidos. Revisa tu conexión y vuelve a intentarlo.'
    expect(await screen.findByText(texto, { selector: ':not([aria-live])' })).toBeVisible()
    await waitFor(() => expect(urgente).toHaveTextContent(texto))
    expect(screen.getByRole('button', { name: /Pedido 4821/ })).toBeVisible()
  })

  it('la segunda página va con el cursor en la consulta', async () => {
    const a = api({ 'GET /pedidos$': () => ({ status: 200, cuerpo: lista([fila()], 'cursor-2') }) })
    abrir('admin', LISTA)
    await userEvent.click(await screen.findByRole('button', { name: 'Ver más pedidos' }))
    await waitFor(() => expect(a.pedidas.filter((p) => p.ruta.endsWith('/pedidos'))).toHaveLength(2))
  })
})

// ---------------------------------------------------------------- el detalle

/** El detalle del 4790 entregado, con su pago y sus retractos. */
function rutasDelEntregado(extra: Rutas = {}, { tuyo = true } = {}): Rutas {
  const c = tuyo ? comprobante({ referencia: '4790' }) : comprobanteAjeno({ referencia: '4790' })
  const devoluciones = [
    devolucion({ monto: 5290, ultimos4: tuyo ? '4051' : null, hecha_en: '2026-11-04T19:00:00Z' }),
    devolucion({ producto: null, monto: 3990, ultimos4: tuyo ? '4051' : null, hecha_en: '2026-11-05T19:00:00Z' }),
    devolucion({ motivo: 'retracto', producto: PANAL_C, monto: 12990, estado: 'en_curso', hecha_en: null, ultimos4: tuyo ? '4051' : null }),
  ]
  return {
    'GET /seguimiento$': { status: 200, cuerpo: seguimientoEntregado() },
    'GET /pago$': { status: 200, cuerpo: pago({ pedido_id: PEDIDO_2, comprobante: { ...c, devoluciones }, devoluciones }) },
    'GET /retractos$': { status: 200, cuerpo: retractos() },
    ...extra,
  }
}

describe('El detalle (4)', () => {
  it('quien pagó: el estado, cómo va por comercio con lo que faltó, el dinero devuelto y el comprobante', async () => {
    api(rutasDelEntregado())
    abrir('pagador', DETALLE, ELEGIDO_2)
    await screen.findByRole('heading', { level: 2, name: 'Cómo va' })
    expect(await h1('Pedido 4790')).toBeVisible()
    expect(document.title).toBe('Pedido 4790 · MATU')
    expect(screen.getByText(/^Pagado el/)).toHaveTextContent('Pagado el 02/11/2026 a las 16:41')
    expect(screen.getAllByText(/Entregado el/)[0]).toHaveTextContent('Entregado el 04/11/2026')

    const parte = screen.getByRole('heading', { level: 3, name: /^De Almacén El Ejemplo\s\(comercio ficticio\):?$/ }).closest('li')!
    expect(within(parte).getByText('Salió del comercio').querySelector('svg')!.getAttribute('class')).toMatch(/lucide-package-check/)
    expect(within(parte).getByText('Faltaron 1').querySelector('svg')!.getAttribute('class')).toMatch(/lucide-package-x/)
    expect(parte).toHaveTextContent('3 × Suplemento vainilla x12')

    const devuelto = within(screen.getByRole('heading', { level: 2, name: 'Dinero devuelto' }).closest('section')!)
    const items = devuelto.getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Faltaron 1 de Suplemento vainilla x12. Te devolvimos $5.290 a tu tarjeta terminada en 4051. Cuándo lo ves en tu cuenta depende de tu banco.')
    expect(items[0]).toHaveTextContent('El 04/11/2026')
    expect(items[1]).toHaveTextContent('Devolvimos el envío: $3.990.')
    expect(items[2]).toHaveTextContent('Estamos devolviendo $12.990 a tu tarjeta. Si no se completa hoy, te escribimos.')
    expect(items[2]).not.toHaveTextContent(/El \d/)

    expect(screen.getByRole('heading', { level: 2, name: 'Comprobante' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Imprimir o guardar en PDF' })).toBeVisible()
    // En el detalle no hay nada en turquesa macizo (7.1).
    expect(macizos()).toEqual([])
  })

  it('quien no pagó (C17): «a la tarjeta con que se pagó», sin los últimos 4', async () => {
    api(rutasDelEntregado({}, { tuyo: false }))
    abrir('cuidador', DETALLE, ELEGIDO_2)
    const devuelto = within((await screen.findByRole('heading', { level: 2, name: 'Dinero devuelto' })).closest('section')!)
    const items = devuelto.getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('Faltaron 1 de Suplemento vainilla x12. Devolvimos $5.290 a la tarjeta con que se pagó. Cuándo se ve en la cuenta depende del banco.')
    expect(items[2]).toHaveTextContent('Estamos devolviendo $12.990 a la tarjeta con que se pagó. Si no se completa hoy, le escribimos a quien pagó.')
    expect(document.body).not.toHaveTextContent('4051')
  })

  it('los productos para devolver: pedida, devuelta, no aceptada, de otra persona y por correo', async () => {
    api(
      rutasDelEntregado({
        'GET /retractos$': {
          status: 200,
          cuerpo: retractos({
            retractos: [
              retracto({ incluye_envio: true, monto: 30480 }),
              retracto({ id: 'r2', estado: 'devuelto', resuelto_en: '2026-11-08T15:00:00Z', es_tuyo: false }),
              retracto({ id: 'r3', estado: 'rechazado', origen: 'correo', es_tuyo: false }),
            ],
          }),
        },
      }),
    )
    abrir('admin', DETALLE, ELEGIDO_2)
    const s = within((await screen.findByRole('heading', { level: 2, name: 'Productos para devolver' })).closest('section')!)
    const [pedida, devuelta, rechazada] = s.getAllByRole('listitem').filter((li) => li.parentElement?.parentElement?.tagName === 'SECTION')
    expect(within(pedida).getByText('Devolución pedida')).toBeVisible()
    expect(pedida).toHaveTextContent('Te devolvemos $30.480, envío incluido, cuando recibamos los productos con su sello cerrado.')
    expect(pedida).not.toHaveTextContent('También te devolvemos el envío.')
    expect(devuelta).toHaveTextContent('Devuelto el 08/11/2026')
    expect(devuelta).toHaveTextContent('La pidió otra persona de tu grupo.')
    expect(rechazada).toHaveTextContent('No se aceptó la devolución')
    expect(within(rechazada).getByRole('link', { name: 'cuidaconmatu@gmail.com' })).toHaveAttribute('href', 'mailto:cuidaconmatu@gmail.com')
    expect(rechazada).toHaveTextContent('Esta devolución se pidió por correo. La registró el equipo de MATU.')
    // C26: la palabra del contrato no se muestra.
    expect(document.body).not.toHaveTextContent(/rechaz/i)
  })

  it('D-63-5 y C15: nunca aparece un código, aunque llegue por un defecto del contrato', async () => {
    const conCodigo = { ...seguimientoEntregado(), codigo_retiro: '482173', partes: seguimientoEntregado().partes.map((p) => ({ ...p, codigo: '482173', referencia: 'PARTE-REF-9' })) }
    api(rutasDelEntregado({ 'GET /seguimiento$': { status: 200, cuerpo: conCodigo } }, { tuyo: false }))
    abrir('admin', DETALLE, ELEGIDO_2)
    await screen.findByRole('heading', { level: 2, name: 'Cómo va' })
    expect(document.body).not.toHaveTextContent(/482173|PARTE-REF-9/)
    expect(document.body).not.toHaveTextContent(/código de retiro/i)
    expect(document.body.innerHTML).not.toMatch(/482173|PARTE-REF-9/)
  })

  it('un pedido con los productos borrados (C28) muestra el texto en vez de las partes', async () => {
    api({
      'GET /seguimiento$': { status: 200, cuerpo: seguimiento({ estado: 'cancelado_con_devolucion', partes: [], productos_borrados: true, devuelto_todo: true, puede_cancelar: false, cancelar_motivo: 'cancelado' }) },
      'GET /pago$': { status: 200, cuerpo: pago() },
    })
    abrir('admin', DETALLE, ELEGIDO_1)
    expect(await screen.findByText('De este pedido guardamos solo lo que se pagó y lo que se devolvió.')).toBeVisible()
    expect(screen.queryByRole('heading', { name: 'Cancelar el pedido' })).toBeNull()
  })

  it('falla solo el comprobante: el detalle se ve, con la nota y «Volver a intentar»', async () => {
    let n = 0
    api(rutasDelEntregado({ 'GET /pago$': () => (n++ === 0 ? { status: 500 } : { status: 200, cuerpo: pago({ pedido_id: PEDIDO_2 }) }) }))
    abrir('admin', DETALLE, ELEGIDO_2)
    expect(await screen.findByText('No pudimos traer el comprobante. Revisa tu conexión y vuelve a intentarlo. Tampoco pudimos mostrar lo que se devolvió.', { selector: ':not([aria-live])' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 2, name: 'Cómo va' })).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Volver a intentar' }))
    expect(await screen.findByRole('heading', { level: 2, name: 'Comprobante' })).toBeVisible()
  })

  it('error al traer: el h1 con la referencia, el aviso y «Volver a intentar»', async () => {
    api({ 'GET /seguimiento$': { status: 500 } })
    abrir('admin', DETALLE, ELEGIDO_1)
    expect(await h1('Pedido 4821')).toBeVisible()
    expect(await screen.findByText('No pudimos traer tu pedido. Revisa tu conexión e inténtalo de nuevo.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Volver a intentar' })).toBeVisible()
  })

  it('404: «No encontramos este pedido.» y «Volver a tus pedidos»', async () => {
    api({ 'GET /seguimiento$': NO_ENCONTRADO, 'GET /pedidos$': { status: 200, cuerpo: lista([]) } })
    abrir('admin', DETALLE, ELEGIDO_1)
    expect(await screen.findByText('No encontramos este pedido.')).toBeVisible()
    const volver = screen.getAllByRole('button', { name: 'Volver a tus pedidos' })
    await userEvent.click(volver[volver.length - 1])
    expect(window.location.pathname).toBe(LISTA)
  })
})

// ---------------------------------------------------------------- 4.6.1 el plazo

describe('Arrepentirse en el detalle: lo dice el servidor (4.6.1, O1, C22)', () => {
  it('con `puede_arrepentirse`: la fecha, la ayuda con el envío y el botón secundario', async () => {
    api(rutasDelEntregado())
    abrir('pagador', DETALLE, ELEGIDO_2)
    const s = within((await screen.findByRole('heading', { level: 2, name: 'Arrepentirme de la compra' })).closest('section')!)
    expect(s.getByText(/^Puedes hacerlo hasta el/)).toHaveTextContent(
      'Puedes hacerlo hasta el 18/11/2026. Pasamos a buscar los productos sin costo y te devolvemos su precio a la misma tarjeta cuando los recibimos con su sello cerrado. Si devuelves todo, también el envío.',
    )
    const b = s.getByRole('button', { name: 'Arrepentirme de la compra' })
    expect(b.className).not.toMatch(/\bbg-turquesa\b/)
    await userEvent.click(b)
    expect(window.location.pathname).toBe(ARREPENTIRME)
  })

  it('hasta los 90 días (`plazo_app_vencido`): la frase con el correo y sin botón', async () => {
    api(rutasDelEntregado({ 'GET /seguimiento$': { status: 200, cuerpo: seguimientoEntregado({ puede_arrepentirse: false, arrepentirse_motivo: 'plazo_app_vencido' }) } }))
    abrir('admin', DETALLE, ELEGIDO_2)
    const s = within((await screen.findByRole('heading', { level: 2, name: 'Arrepentirme de la compra' })).closest('section')!)
    expect(s.getByText(/^El plazo para arrepentirte desde la aplicación/)).toHaveTextContent(
      'El plazo para arrepentirte desde la aplicación terminó el 18/11/2026. Si todavía quieres devolver productos, o tienes un problema con el pedido, escríbenos a cuidaconmatu@gmail.com.',
    )
    expect(s.getByRole('link', { name: 'cuidaconmatu@gmail.com' })).toHaveAttribute('href', 'mailto:cuidaconmatu@gmail.com')
    // P1-1 y P1-2: a 320 px con el texto al 200 %, el título y el correo se parten en vez de salirse.
    expect(s.getByRole('link', { name: 'cuidaconmatu@gmail.com' }).className).toContain('[overflow-wrap:anywhere]')
    const h2 = screen.getByRole('heading', { level: 2, name: 'Arrepentirme de la compra' })
    expect(h2.className).toContain('[overflow-wrap:anywhere]')
    expect(h2.className).toContain('angosto:text-xl')
    expect(s.queryByRole('button')).toBeNull()
  })

  it('después de los 90 días (`plazo_vencido`): solo el reclamo', async () => {
    api(rutasDelEntregado({ 'GET /seguimiento$': { status: 200, cuerpo: seguimientoEntregado({ puede_arrepentirse: false, arrepentirse_motivo: 'plazo_vencido' }) } }))
    abrir('admin', DETALLE, ELEGIDO_2)
    const s = within((await screen.findByRole('heading', { level: 2, name: 'Arrepentirme de la compra' })).closest('section')!)
    // C22 (H1 del cierre): después de los 90 días, la fecha es la de `plazo_correo_hasta`, no la de la app.
    expect(s.getByText(/^El plazo para arrepentirte terminó/)).toHaveTextContent('El plazo para arrepentirte terminó el 02/02/2027 a las 15:00. Si tienes un problema con el pedido, escríbenos a cuidaconmatu@gmail.com.')
    expect(s.getByText(/^El plazo para arrepentirte terminó/)).not.toHaveTextContent('18/11/2026')
    expect(s.queryByRole('button')).toBeNull()
  })

  it.each([
    ['rol', 'Pueden arrepentirse de la compra quien administra el grupo y quien la pagó.'],
    ['nada_disponible', 'Ya se pidió devolver todos los productos de este pedido.'],
  ] as const)('motivo %s: la frase, sin botón', async (motivo, texto) => {
    api(rutasDelEntregado({ 'GET /seguimiento$': { status: 200, cuerpo: seguimientoEntregado({ puede_arrepentirse: false, arrepentirse_motivo: motivo }) } }))
    abrir('cuidador', DETALLE, ELEGIDO_2)
    expect(await screen.findByText(texto, { selector: ':not([aria-live])' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Arrepentirme de la compra' })).toBeNull()
  })

  it('sin entregar: no hay bloque de arrepentirse ni se piden los retractos', async () => {
    const a = api({ 'GET /seguimiento$': { status: 200, cuerpo: seguimiento() }, 'GET /pago$': { status: 200, cuerpo: pago() } })
    abrir('admin', DETALLE, ELEGIDO_1)
    await screen.findByRole('heading', { level: 2, name: 'Cómo va' })
    expect(screen.queryByRole('heading', { name: 'Arrepentirme de la compra' })).toBeNull()
    expect(a.pedidas.some((p) => p.ruta.endsWith('/retractos'))).toBe(false)
  })
})

// ---------------------------------------------------------------- 5 arrepentirme

describe('Arrepentirme de la compra (5)', () => {
  it('elegir: empieza en 0, la vista previa a precio pagado, el sello y el envío si se elige todo', async () => {
    api({ 'GET /retractos$': { status: 200, cuerpo: retractos() } })
    abrir('pagador', ARREPENTIRME, ELEGIDO_2)
    expect(await h1('Arrepentirme de la compra')).toBeVisible()
    expect(await screen.findByText('Todavía no eliges ningún producto.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Volver al pedido 4790' })).toBeVisible()
    const panal = screen.getByRole('textbox', { name: '¿Cuántos devuelves? Pañal adulto M x30' })
    expect(panal).toHaveValue('0')
    expect(panal).toHaveAccessibleDescription('Puedes devolver hasta 2.')
    expect(screen.getAllByText('Recibiste 2. Pagaste $12.990 cada uno.')[0]).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: 'Uno más: Pañal adulto M x30' }))
    const resumen = within(screen.getByRole('heading', { level: 2, name: 'Lo que vas a devolver' }).closest('section')!)
    expect(resumen.getByRole('listitem')).toHaveTextContent('1 × Pañal adulto M x30')
    expect(resumen.getByText(/^Te devolvemos/)).toHaveTextContent('Te devolvemos $12.990 cuando recibamos los productos con su sello cerrado.')
    expect(resumen.getByText('Si abres el sello, ya no se puede devolver.')).toBeVisible()
    expect(resumen.queryByText('También te devolvemos el envío.')).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: 'Uno más: Pañal adulto M x30' }))
    await userEvent.click(screen.getByRole('button', { name: 'Uno más: Suplemento vainilla x12' }))
    await userEvent.click(screen.getByRole('button', { name: 'Uno más: Suplemento vainilla x12' }))
    // P3-3: con todo elegido, el monto ya lleva el envío y lo dice en la misma frase.
    expect(resumen.getByText(/^Te devolvemos/)).toHaveTextContent('Te devolvemos $82.950, envío incluido, cuando recibamos los productos con su sello cerrado.')
    expect(resumen.queryByText('También te devolvemos el envío.')).toBeNull()
    // El único macizo es «Devolver estos productos».
    expect(macizos()).toHaveLength(1)
    expect(macizos()[0]).toHaveAccessibleName('Devolver estos productos')
  })

  it('C9: con las condiciones 0.2, un retracto parcial ya dice «, envío incluido,» con el envío sumado', async () => {
    api({ 'GET /retractos$': { status: 200, cuerpo: retractos({ condiciones_version: '0.2' }) } })
    abrir('pagador', ARREPENTIRME, ELEGIDO_2)
    await userEvent.click(await screen.findByRole('button', { name: 'Uno más: Pañal adulto M x30' }))
    const resumen = within(screen.getByRole('heading', { level: 2, name: 'Lo que vas a devolver' }).closest('section')!)
    expect(resumen.getByText(/^Te devolvemos/)).toHaveTextContent('Te devolvemos $16.980, envío incluido, cuando recibamos los productos con su sello cerrado.')
  })

  it('nada elegido: el error sobre el botón, anunciado, y el foco al primer campo', async () => {
    const a = api({ 'GET /retractos$': { status: 200, cuerpo: retractos() } })
    const { urgente } = abrir('admin', ARREPENTIRME, ELEGIDO_2)
    await userEvent.click(await screen.findByRole('button', { name: 'Devolver estos productos' }))
    const texto = 'Elige al menos un producto y cuántos devuelves.'
    expect(screen.getByText(texto, { selector: ':not([aria-live])' })).toBeVisible()
    await waitFor(() => expect(urgente).toHaveTextContent(texto))
    await waitFor(() => expect(screen.getByRole('textbox', { name: /Pañal/ })).toHaveFocus())
    expect(a.escrituras()).toEqual([])
  })

  it('fuera de rango: el error bajo el campo, `aria-invalid`, y no se envía', async () => {
    const a = api({ 'GET /retractos$': { status: 200, cuerpo: retractos() } })
    abrir('admin', ARREPENTIRME, ELEGIDO_2)
    const campo = await screen.findByRole('textbox', { name: /Suplemento/ })
    await userEvent.clear(campo)
    await userEvent.type(campo, '7')
    await userEvent.tab()
    expect(await screen.findByText('Escribe un número de 0 a 2.')).toBeVisible()
    expect(campo).toHaveAttribute('aria-invalid', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Devolver estos productos' }))
    expect(a.escrituras()).toEqual([])
  })

  it('201: envía solo lo elegido con la clave, va al detalle con la nota, y manda el monto del POST', async () => {
    let pedido = false
    const a = api({
      'GET /retractos$': () => ({ status: 200, cuerpo: retractos(pedido ? { retractos: [] } : {}) }),
      'POST /retractos$': () => {
        pedido = true
        // El monto del servidor manda, aunque la vista previa diga otro.
        return { status: 201, cuerpo: retracto({ monto: 26000 }) }
      },
      ...rutasDelEntregado({ 'GET /retractos$': () => ({ status: 200, cuerpo: retractos() }) }),
    })
    const { amable } = abrir('pagador', ARREPENTIRME, ELEGIDO_2)
    await userEvent.click(await screen.findByRole('button', { name: 'Uno más: Suplemento vainilla x12' }))
    await userEvent.click(screen.getByRole('button', { name: 'Devolver estos productos' }))
    await waitFor(() => expect(window.location.pathname).toBe(DETALLE))
    const post = a.pedidas.find((p) => p.metodo === 'POST')!
    expect(post.cuerpo).toEqual({ lineas: [{ linea_id: LINEA_SUPLEMENTO, cantidad: 1 }] })
    expect(String(post.cabeceras['Idempotency-Key'])).toMatch(/^[A-Za-z0-9_-]{16,64}$/)
    expect(post.cuerpo).not.toHaveProperty('motivo')
    // MATU-119: la nota que se ve, no su copia en la región viva, que llega 50 ms después.
    expect(await screen.findByText('Recibimos tu pedido de devolución. Te escribimos para coordinar el retiro.', fueraDeRegiones)).toBeVisible()
    // MATU-121: y se anuncia en la región amable, para quien usa lector de pantalla.
    await waitFor(() => expect(amable).toHaveTextContent('Recibimos tu pedido de devolución. Te escribimos para coordinar el retiro.'))
    const s = within((await screen.findByRole('heading', { level: 2, name: 'Productos para devolver' })).closest('section')!)
    expect(s.getByText(/^Te devolvemos/)).toHaveTextContent('Te devolvemos $26.000 cuando')
    expect(escrituras).toEqual([])
  })

  it('P1-4: después del 201, el foco queda en el h1 del detalle cuando termina de recargar, y no cae al body', async () => {
    const lento = (r: Respuesta) => () => new Promise<Respuesta>((ok) => window.setTimeout(() => ok(r), 80))
    api({
      ...rutasDelEntregado(),
      'GET /seguimiento$': lento({ status: 200, cuerpo: seguimientoEntregado() }),
      'POST /retractos$': { status: 201, cuerpo: retracto() },
    })
    abrir('pagador', ARREPENTIRME, ELEGIDO_2)
    await userEvent.click(await screen.findByRole('button', { name: 'Uno más: Suplemento vainilla x12' }))
    await userEvent.click(screen.getByRole('button', { name: 'Devolver estos productos' }))
    await waitFor(() => expect(window.location.pathname).toBe(DETALLE))
    // Lo que hace AppFamilia al cambiar de ruta: el foco al h1 de «Cargando».
    screen.getByRole('heading', { level: 1, name: 'Pedido 4790' }).focus()
    await screen.findByRole('heading', { level: 2, name: 'Cómo va' })
    const titulo = screen.getByRole('heading', { level: 1, name: 'Pedido 4790' })
    await waitFor(() => expect(titulo).toHaveFocus())
    await act(() => new Promise((ok) => window.setTimeout(ok, 900)))
    expect(document.activeElement).toBe(titulo)
  })

  it('P2-1: una línea que no se recibió (entregadas 0) no se muestra', async () => {
    api({ 'GET /retractos$': { status: 200, cuerpo: retractos({ lineas: [lineaParaRetracto(), lineaParaRetracto({ linea_id: LINEA_SUPLEMENTO, producto: SUPLEMENTO_C, entregadas: 0, disponibles: 0 })] }) } })
    abrir('admin', ARREPENTIRME, ELEGIDO_2)
    expect(await screen.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })).toBeVisible()
    expect(screen.queryByRole('heading', { level: 3, name: 'Suplemento vainilla x12' })).toBeNull()
  })

  it.each([
    ['422 producto-no-retractable', problema(422, 'producto-no-retractable')],
    ['409 de lo ya pedido', problema(409, 'producto-no-retractable')],
  ])('%s (C8): vuelve a leer, baja lo elegido y avisa con el foco', async (_, error) => {
    let leidas = 0
    const a = api({
      'GET /retractos$': () => {
        leidas++
        return { status: 200, cuerpo: retractos(leidas > 1 ? { lineas: [lineaParaRetracto({ disponibles: 1, ya_pedidas: 1 }), lineaParaRetracto({ linea_id: LINEA_SUPLEMENTO, producto: SUPLEMENTO_C, disponibles: 2, precio_pagado: 26490, retracto_pierde_al_abrir: false })] } : {}) }
      },
      'POST /retractos$': error,
    })
    abrir('admin', ARREPENTIRME, ELEGIDO_2)
    const mas = await screen.findByRole('button', { name: 'Uno más: Pañal adulto M x30' })
    await userEvent.click(mas)
    await userEvent.click(mas)
    await userEvent.click(screen.getByRole('button', { name: 'Devolver estos productos' }))
    const nota = (await screen.findByText('Otra persona de tu grupo ya pidió devolver algunos de estos productos.')).closest('[data-aviso]')!
    expect(nota).toHaveAttribute('data-aviso', 'alert')
    await waitFor(() => expect(nota).toHaveFocus())
    expect(screen.getByRole('textbox', { name: /Pañal/ })).toHaveValue('1')
    expect(screen.getByText('Ya se pidió devolver 1.')).toBeVisible()
    expect(document.body).not.toHaveTextContent('Ya pediste')
    expect(window.location.pathname).toBe(ARREPENTIRME)
    expect(a.pedidas.filter((p) => p.ruta.endsWith('/retractos') && p.metodo === 'GET')).toHaveLength(2)
  })

  it('409 fuera-de-plazo: va al detalle, que lo explica', async () => {
    api({ 'GET /retractos$': { status: 200, cuerpo: retractos() }, 'POST /retractos$': problema(409, 'fuera-de-plazo') })
    abrir('admin', ARREPENTIRME, ELEGIDO_2)
    await userEvent.click(await screen.findByRole('button', { name: 'Uno más: Pañal adulto M x30' }))
    await userEvent.click(screen.getByRole('button', { name: 'Devolver estos productos' }))
    await waitFor(() => expect(window.location.pathname).toBe(DETALLE))
  })

  it('red: lo elegido sigue, el foco se queda en el botón, y el reintento usa la misma clave; cambiar lo elegido usa otra', async () => {
    let n = 0
    const a = api({ 'GET /retractos$': { status: 200, cuerpo: retractos() }, 'POST /retractos$': () => (n++ < 2 ? { status: 503 } : { status: 201, cuerpo: retracto() }) })
    const { urgente } = abrir('admin', ARREPENTIRME, ELEGIDO_2)
    await userEvent.click(await screen.findByRole('button', { name: 'Uno más: Pañal adulto M x30' }))
    const enviar = screen.getByRole('button', { name: 'Devolver estos productos' })
    await userEvent.click(enviar)
    const texto = 'No pudimos enviar tu pedido de devolución. Revisa tu conexión y vuelve a intentarlo. Lo que elegiste sigue aquí.'
    expect(await screen.findByText(texto, { selector: ':not([aria-live])' })).toBeVisible()
    await waitFor(() => expect(urgente).toHaveTextContent(texto))
    expect(enviar).toHaveFocus()
    expect(screen.getByRole('textbox', { name: /Pañal/ })).toHaveValue('1')
    await userEvent.click(enviar)
    await waitFor(() => expect(claves(a.pedidas, '/retractos')).toHaveLength(2))
    const [k1, k2] = claves(a.pedidas, '/retractos')
    expect(k2).toBe(k1)
    // Otra elección es otro intento: otra clave.
    await userEvent.click(screen.getByRole('button', { name: 'Uno más: Pañal adulto M x30' }))
    await userEvent.click(enviar)
    await waitFor(() => expect(claves(a.pedidas, '/retractos')).toHaveLength(3))
    expect(claves(a.pedidas, '/retractos')[2]).not.toBe(k1)
  })

  it('sin `puede_arrepentirse` al abrir: va al detalle', async () => {
    api({ 'GET /retractos$': { status: 200, cuerpo: retractos({ puede_arrepentirse: false, arrepentirse_motivo: 'plazo_app_vencido' }) } })
    abrir('admin', ARREPENTIRME, ELEGIDO_2)
    await waitFor(() => expect(window.location.pathname).toBe(DETALLE))
  })
})

// ---------------------------------------------------------------- 6 cancelar

/** El pedido 4821 recién pagado, que todavía se puede cancelar; después de cancelar, cancelado. */
function rutasParaCancelar(cancelar: Rutas[string], { cancelado = (): boolean => false } = {}) {
  return {
    'GET /seguimiento$': () => ({
      status: 200,
      cuerpo: cancelado()
        ? seguimiento({ estado: 'cancelado_con_devolucion', puede_cancelar: false, cancelar_motivo: 'cancelado', devuelto_todo: false, partes: seguimiento().partes.map((p) => ({ ...p, estado: 'cancelada' as const, cancelada_por: 'pedido' as const })) })
        : seguimiento(),
    }),
    'GET /pago$': { status: 200, cuerpo: pago() },
    'POST /cancelar-con-devolucion$': cancelar,
  } satisfies Rutas
}

describe('Cancelar el pedido pagado (6)', () => {
  it('sin `puede_cancelar`, con el motivo `rol`: la frase, sin botón', async () => {
    api({ 'GET /seguimiento$': { status: 200, cuerpo: seguimiento({ puede_cancelar: false, cancelar_motivo: 'rol' }) }, 'GET /pago$': { status: 200, cuerpo: pago() } })
    abrir('cuidador', DETALLE, ELEGIDO_1)
    expect(await screen.findByText('Solo quien administra el grupo puede cancelar un pedido pagado, mientras el comercio no empiece a prepararlo.')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Cancelar el pedido' })).toBeNull()
  })

  it('confirmar: el monto del servidor y el sello; nada cambia antes de la respuesta; después, la nota con el foco', async () => {
    let soltar: (r: Respuesta) => void = () => {}
    let cancelado = false
    const a = api(
      rutasParaCancelar(
        () =>
          new Promise<Respuesta>((r) => {
            soltar = (x) => {
              cancelado = true
              r(x)
            }
          }),
        { cancelado: () => cancelado },
      ),
    )
    const { amable } = abrir('admin', DETALLE, ELEGIDO_1)
    const abrirDialogo = await screen.findByRole('button', { name: 'Cancelar el pedido' })
    expect(abrirDialogo.className).not.toMatch(/\bbg-turquesa\b/)
    await userEvent.click(abrirDialogo)
    const d = within(screen.getByRole('dialog', { name: '¿Cancelar este pedido?' }))
    expect(screen.getByRole('dialog')).toHaveAccessibleDescription(
      'Te devolvemos $57.460, envío incluido, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco. Pago de prueba. No se cobró dinero real.',
    )
    await userEvent.click(d.getByRole('button', { name: 'Cancelar el pedido' }))
    // C10: sin interfaz optimista.
    expect(d.getByRole('button', { name: /Cancelar el pedido|Cancelando/ })).toHaveAttribute('aria-busy', 'true')
    expect(screen.getAllByText('Pagado').length).toBeGreaterThan(0)
    expect(screen.queryByText('Cancelado')).toBeNull()
    await act(async () => soltar({ status: 200, cuerpo: { pedido_id: PEDIDO_ID, estado: 'cancelado_con_devolucion' } }))
    // MATU-119: la nota que se ve, no su copia en la región amable, que llega 50 ms después.
    const nota = (await screen.findByText(/^Cancelamos el pedido/, fueraDeRegiones)).closest('[data-aviso]')!
    // MATU-121: y se anuncia en la región amable, para quien usa lector de pantalla.
    await waitFor(() => expect(amable).toHaveTextContent('Cancelamos el pedido. Estamos devolviendo $57.460 a la tarjeta con que se pagó.'))
    expect(nota).toHaveTextContent('Cancelamos el pedido. Estamos devolviendo $57.460 a la tarjeta con que se pagó.')
    expect(nota).toHaveAttribute('data-aviso', 'status')
    await waitFor(() => expect(nota).toHaveFocus())
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getAllByText('Cancelado').length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: 'Cancelar el pedido' })).toBeNull()
    expect(String(a.pedidas.find((p) => p.metodo === 'POST')!.cabeceras['Idempotency-Key'])).toMatch(/^[A-Za-z0-9_-]{16,64}$/)
  })

  it('409 `estado-pedido` (C11): cierra, vuelve a leer y dice que ya se canceló', async () => {
    let cancelado = false
    api(
      rutasParaCancelar(
        () => {
          cancelado = true
          return problema(409, 'estado-pedido', { estado: 'cancelado_con_devolucion' })
        },
        { cancelado: () => cancelado },
      ),
    )
    abrir('admin', DETALLE, ELEGIDO_1)
    await userEvent.click(await screen.findByRole('button', { name: 'Cancelar el pedido' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancelar el pedido' }))
    const nota = (await screen.findByText('Este pedido ya se canceló. Te mostramos cómo quedó.')).closest('[data-aviso]')!
    expect(nota).toHaveAttribute('data-aviso', 'status')
    await waitFor(() => expect(nota).toHaveFocus())
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('409 `ya-se-prepara`: cierra y avisa con `alert` y el foco', async () => {
    api(rutasParaCancelar(problema(409, 'ya-se-prepara')))
    abrir('admin', DETALLE, ELEGIDO_1)
    await userEvent.click(await screen.findByRole('button', { name: 'Cancelar el pedido' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancelar el pedido' }))
    const nota = (await screen.findByText('Ya están preparando tu pedido, así que no se puede cancelar. Cuando llegue, puedes arrepentirte de la compra.')).closest('[data-aviso]')!
    expect(nota).toHaveAttribute('data-aviso', 'alert')
    await waitFor(() => expect(nota).toHaveFocus())
  })

  it('red: vuelve a leer antes de decir «Todo sigue como estaba»; el reintento usa la misma clave', async () => {
    let n = 0
    const a = api(rutasParaCancelar(() => (n++ === 0 ? { status: 503 } : { status: 200, cuerpo: { pedido_id: PEDIDO_ID, estado: 'cancelado_con_devolucion' } }), { cancelado: () => n > 1 }))
    const { amable } = abrir('admin', DETALLE, ELEGIDO_1)
    await userEvent.click(await screen.findByRole('button', { name: 'Cancelar el pedido' }))
    const confirmar = within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancelar el pedido' })
    await userEvent.click(confirmar)
    const dialogo = screen.getByRole('dialog')
    expect(await within(dialogo).findByText('No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.')).toBeVisible()
    // Leyó el pedido después del error y antes de decirlo.
    const orden = a.pedidas.map((p) => `${p.metodo} ${p.ruta.split('/').pop()}`)
    expect(orden.slice(orden.indexOf('POST cancelar-con-devolucion'))).toContain('GET seguimiento')
    await userEvent.click(confirmar)
    expect(await screen.findByText(/^Cancelamos el pedido/, fueraDeRegiones)).toBeVisible()
    // MATU-121: y se anuncia en la región amable, para quien usa lector de pantalla.
    await waitFor(() => expect(amable).toHaveTextContent('Cancelamos el pedido. Estamos devolviendo $57.460 a la tarjeta con que se pagó.'))
    const [k1, k2] = claves(a.pedidas, '/cancelar-con-devolucion')
    expect(k1).toBeTruthy()
    expect(k2).toBe(k1)
  })

  it('red, pero el pedido ya quedó cancelado al volver a leer: como el 200', async () => {
    let enviado = false
    api(
      rutasParaCancelar(
        () => {
          enviado = true
          return { status: 502 }
        },
        { cancelado: () => enviado },
      ),
    )
    const { amable } = abrir('admin', DETALLE, ELEGIDO_1)
    await userEvent.click(await screen.findByRole('button', { name: 'Cancelar el pedido' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancelar el pedido' }))
    expect(await screen.findByText(/^Cancelamos el pedido/, fueraDeRegiones)).toBeVisible()
    // MATU-121: y se anuncia en la región amable, para quien usa lector de pantalla.
    await waitFor(() => expect(amable).toHaveTextContent('Cancelamos el pedido. Estamos devolviendo $57.460 a la tarjeta con que se pagó.'))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('«Seguir con el pedido» cierra sin cancelar y devuelve el foco al botón', async () => {
    const a = api(rutasParaCancelar({ status: 200, cuerpo: {} }))
    abrir('admin', DETALLE, ELEGIDO_1)
    await userEvent.click(await screen.findByRole('button', { name: 'Cancelar el pedido' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Seguir con el pedido' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Cancelar el pedido' })).toHaveFocus())
    expect(a.escrituras()).toEqual([])
  })
})

// ---------------------------------------------------------------- reglas puras

describe('Reglas puras (O2, O6, 5.7)', () => {
  const datos = retractos()
  it('la vista previa suma a precio pagado, en enteros, y el envío solo si se devuelve todo', () => {
    expect(vistaPrevia(datos, { [LINEA_PANAL]: '1', [LINEA_SUPLEMENTO]: '0' })).toEqual({ productos: 12990, conEnvio: false, total: 12990 })
    expect(vistaPrevia(datos, { [LINEA_PANAL]: '2', [LINEA_SUPLEMENTO]: '2' })).toEqual({ productos: 78960, conEnvio: true, total: 82950 })
    expect(vistaPrevia({ ...datos, incluye_envio_si_todo: false }, { [LINEA_PANAL]: '2', [LINEA_SUPLEMENTO]: '2' }).conEnvio).toBe(false)
    // Fuera de rango no cuenta.
    expect(vistaPrevia(datos, { [LINEA_PANAL]: '9' }).total).toBe(0)
  })
  it('C9: con la 0.1, la 0.2 o sin versión, el envío vuelve en un retracto parcial, una sola vez; con la 0.3, solo con todo', () => {
    const v02 = retractos({ condiciones_version: '0.2' })
    expect(vistaPrevia(v02, { [LINEA_PANAL]: '1', [LINEA_SUPLEMENTO]: '0' })).toEqual({ productos: 12990, conEnvio: true, total: 16980 })
    expect(vistaPrevia(retractos({ condiciones_version: '0.1' }), { [LINEA_PANAL]: '1' }).conEnvio).toBe(true)
    // Nada elegido: no hay envío que devolver.
    expect(vistaPrevia(v02, {}).conEnvio).toBe(false)
    // Ya se devolvió en un retracto anterior (pedido o devuelto); el no aceptado no cuenta.
    expect(vistaPrevia({ ...v02, retractos: [retracto({ incluye_envio: true })] }, { [LINEA_PANAL]: '1' }).conEnvio).toBe(false)
    expect(vistaPrevia({ ...v02, retractos: [retracto({ incluye_envio: true, estado: 'devuelto' })] }, { [LINEA_PANAL]: '1' }).conEnvio).toBe(false)
    expect(vistaPrevia({ ...v02, retractos: [retracto({ incluye_envio: true, estado: 'rechazado' })] }, { [LINEA_PANAL]: '1' }).conEnvio).toBe(true)
    // El servidor dice que ya no lo devolvería.
    expect(vistaPrevia({ ...v02, incluye_envio_si_todo: false }, { [LINEA_PANAL]: '1' }).conEnvio).toBe(false)
    // La 0.3: solo con todo.
    expect(vistaPrevia(retractos({ condiciones_version: '0.3' }), { [LINEA_PANAL]: '1' }).conEnvio).toBe(false)
    expect(vistaPrevia(retractos({ condiciones_version: '0.3' }), { [LINEA_PANAL]: '2', [LINEA_SUPLEMENTO]: '2' }).conEnvio).toBe(true)
    // MATU-112 H1: sin versión, como la 0.1 y la 0.2 (siempre, una sola vez).
    const sinVersion = retractos({ condiciones_version: null })
    expect(vistaPrevia(sinVersion, { [LINEA_PANAL]: '1' })).toEqual({ productos: 12990, conEnvio: true, total: 16980 })
    expect(vistaPrevia({ ...sinVersion, retractos: [retracto({ incluye_envio: true })] }, { [LINEA_PANAL]: '1' }).conEnvio).toBe(false)
  })
  it('bajar al disponible nunca sube una cantidad', () => {
    const lineas = [lineaParaRetracto({ disponibles: 1 }), lineaParaRetracto({ linea_id: LINEA_SUPLEMENTO, disponibles: 2 })]
    expect(bajarAlDisponible(lineas, { [LINEA_PANAL]: '2', [LINEA_SUPLEMENTO]: '1' })).toEqual({ [LINEA_PANAL]: '1', [LINEA_SUPLEMENTO]: '1' })
  })
  it('el plazo de las 23:59 de Chile va sin hora; a otra hora, con ella', () => {
    expect(plazoEnChile('2026-11-19T02:59:59.999999Z')).toEqual({ fecha: '18/11/2026', hora: null })
    expect(plazoEnChile('2026-11-18T21:00:00Z')).toEqual({ fecha: '18/11/2026', hora: '18:00' })
  })
})

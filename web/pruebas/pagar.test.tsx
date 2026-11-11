// MATU-62: «Pagar {total}» en el resumen (especificación docs/diseno/matu-62-pago.md v1.0, secciones
// 4 a 6 y 8), el pago en curso en el pedido y en el resumen, el diálogo de cancelar con un pago en
// curso y el bloque «Pedido pagado». Sin interfaz optimista: cada estado es lo que respondió la API
// falsa. Solo datos sintéticos.
import { cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { fijarGrupo } from '../src/compartido/api/sesion'
import { PantallaPedido } from '../src/familia/Pedido'
import { olvidarTodoElPago, tomarComprobante } from '../src/familia/vueltaPago'
import { familiaFalsa } from './familiaFalsa'
import { apiPedido, borrador, confirmado, conRegionesGlobales, enOrden, NO_ENCONTRADO, PEDIDO_ID, persona, PERSONA_ID, problema, type Pedida } from './pedidoFalso'
import { comprobanteAjeno, GRUPO_ID, pago, TOKEN } from './pagoFalso'

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

const URL_WEBPAY = 'https://webpay3gint.transbank.cl/webpayserver/initTransaction'
let enviados: HTMLFormElement[] = []
let escrituras: string[] = []

beforeEach(() => {
  fijarGrupo(GRUPO_ID)
  enviados = []
  escrituras = []
  for (const s of [localStorage, sessionStorage]) s.clear()
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
  // jsdom no navega: el formulario a Webpay se anota en vez de enviarse.
  HTMLFormElement.prototype.submit = function (this: HTMLFormElement) {
    enviados.push(this)
  }
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})
afterEach(() => {
  olvidarTodoElPago()
  document.querySelectorAll('form[hidden]').forEach((f) => f.remove())
})

function abrir(rol: Rol = 'admin', ruta: '/insumos/pedido/resumen' | '/insumos/pedido' = '/insumos/pedido/resumen') {
  window.history.replaceState(null, '', ruta)
  const p = persona()
  const vista = rol === 'observador' ? { id: p.id, nombre: p.nombre } : rol === 'pagador' ? { id: p.id, nombre: p.nombre, direccion: p.direccion } : p
  contexto = familiaFalsa({ persona: vista, personas: [vista], personaId: PERSONA_ID, grupoId: GRUPO_ID, rol, capa3: true, intencionPedido: null, llegadaPedido: null, direccionDesdeGrupo: false } as never)
  return conRegionesGlobales(<PantallaPedido />)
}

const titulo = () => screen.findByRole('heading', { level: 1, name: 'Antes de pagar' })
const casilla = () => screen.getByRole('checkbox', { name: 'Leí y acepto las condiciones del pedido.' })
const pagar = () => screen.getByRole('button', { name: 'Pagar $34.260' })
const macizos = () => screen.getAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className))
const pagos = (pedidas: Pedida[]) => pedidas.filter((p) => p.metodo === 'POST' && p.ruta.endsWith('/pagar'))
const INICIO = { intento_id: '3c9d4e20-0000-4000-8000-0000000000f1', estado: 'iniciada', monto: 34260, total_confirmado_en: '2026-11-11T19:30:00Z', url: URL_WEBPAY, token: TOKEN }

describe('Antes de pagar: «Pagar {total}» (4)', () => {
  it('4.1: la frase de Webpay entre la casilla y «Pagar», que la describe; el candado y el total en cifras; nunca deshabilitado', async () => {
    apiPedido({}, { pedido: confirmado() })
    abrir()
    await titulo()
    const frase = screen.getByText('Te llevamos a Webpay, la página de pago de Transbank. MATU no ve los datos de tu tarjeta.')
    expect(frase.className).toMatch(/\btext-base\b/)
    expect(frase.className).toMatch(/\btext-tenue\b/)
    expect(casilla().compareDocumentPosition(frase) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(frase.compareDocumentPosition(pagar()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(pagar()).toHaveAccessibleDescription(frase.textContent!)
    expect(pagar()).not.toBeDisabled()
    expect(pagar()).not.toHaveAttribute('aria-disabled')
    expect(pagar().querySelector('svg')!.getAttribute('class')).toMatch(/lucide-lock/)
    expect(pagar().querySelector('.cifras')).toHaveTextContent('$34.260')
    // El mismo total en la bajada, la boleta y el botón (criterio 2).
    expect(screen.getByText(/El total es/).closest('p')).toHaveTextContent('$34.260')
    expect(within(screen.getByRole('region', { name: 'Tu pedido' })).getByText('Total').closest('p')).toHaveTextContent('$34.260')
  })

  it('4.5.1: sin la casilla, el error bajo ella y el foco en ella, sin llamar a la API', async () => {
    const api = apiPedido({}, { pedido: confirmado() })
    abrir()
    await titulo()
    await userEvent.click(pagar())
    expect(screen.getByText('Marca que leíste y aceptas las condiciones para pagar.')).toBeVisible()
    await waitFor(() => expect(casilla()).toHaveFocus())
    expect(casilla()).toHaveAccessibleDescription('Marca que leíste y aceptas las condiciones para pagar.')
    expect(api.escrituras()).toEqual([])
    // Al marcarla, el error se va.
    await userEvent.click(casilla())
    expect(screen.queryByText('Marca que leíste y aceptas las condiciones para pagar.')).toBeNull()
  })

  it('4.5.2 y 4.5.3: «Pagando…» y «Abriendo Webpay…», y un formulario POST a Webpay con token_ws en la misma pestaña; nada en la URL ni en el navegador', async () => {
    let soltar: () => void = () => {}
    const api = apiPedido(
      {
        'POST /pagar$': () =>
          new Promise((listo) => {
            soltar = () => listo({ status: 201, cuerpo: INICIO })
          }),
      },
      { pedido: confirmado() },
    )
    abrir()
    await titulo()
    await userEvent.click(casilla())
    await userEvent.click(pagar())
    expect(await screen.findByText('Abriendo Webpay…')).toHaveAttribute('role', 'status')
    const boton = screen.getByRole('button', { name: /Pagar \$34\.260|Pagando…/ })
    expect(boton).toHaveAttribute('aria-busy', 'true')
    soltar()
    await waitFor(() => expect(enviados).toHaveLength(1))
    const form = enviados[0]
    expect(form.method).toBe('post')
    expect(form.action).toBe(URL_WEBPAY)
    expect(form.target).not.toBe('_blank')
    expect(form.querySelectorAll('input')).toHaveLength(1)
    expect(form.querySelector('input')).toMatchObject({ type: 'hidden', name: 'token_ws', value: TOKEN })
    expect(document.querySelector('iframe')).toBeNull()
    // El contrato: If-Match con el etag que se mostró, una clave por toque y las condiciones que se vieron.
    const [p] = pagos(api.pedidas)
    expect(p.ruta).toBe(`/v1/pedidos/${PEDIDO_ID}/pagar`)
    expect(p.cabeceras['If-Match']).toBe('p2')
    expect(String(p.cabeceras['Idempotency-Key'])).toMatch(/^[A-Za-z0-9_-]{16,64}$/)
    expect(p.cabeceras['X-Grupo-Id']).toBe(GRUPO_ID)
    expect(p.cuerpo).toEqual({ acepta_condiciones: true, condiciones: { version: '0.1', huella: 'a'.repeat(64) } })
    // C18: nada del pago en la dirección, en el historial ni en el almacenamiento.
    expect(window.location.href).not.toMatch(/token|tbk/i)
    expect(window.history.state).toBeNull()
    expect(escrituras).toEqual([])
  })

  it('4.6: Webpay no responde (503): la nota sobre el botón, con el foco; el botón vuelve a «Pagar»', async () => {
    apiPedido({ 'POST /pagar$': { ...problema(503, 'pasarela-no-disponible'), cabeceras: { 'retry-after': '60' } } }, { pedido: confirmado() })
    const { urgente } = abrir()
    await titulo()
    await userEvent.click(casilla())
    await userEvent.click(pagar())
    const nota = (await screen.findByText('Webpay no responde ahora. No se cobró nada. Inténtalo en unos minutos.')).closest('[data-aviso]')!
    await waitFor(() => expect(nota).toHaveFocus())
    await waitFor(() => expect(urgente).toHaveTextContent('Webpay no responde ahora.'))
    expect(nota.compareDocumentPosition(pagar()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(nota.className).not.toMatch(/pronto/)
    expect(pagar()).not.toHaveAttribute('aria-busy')
    expect(enviados).toEqual([])
  })

  it('4.6: sin conexión, o un 422 o 428 (defecto de la pantalla): «No pudimos abrir Webpay…»', async () => {
    for (const r of [problema(500, 'interno'), problema(428, 'falta-version'), problema(422, 'idempotencia-reutilizada')]) {
      apiPedido({ 'POST /pagar$': r }, { pedido: confirmado() })
      abrir()
      await titulo()
      await userEvent.click(casilla())
      await userEvent.click(pagar())
      expect(await screen.findByText('No pudimos abrir Webpay. Revisa tu conexión y vuelve a intentarlo. No se cobró nada.')).toBeVisible()
      cleanup()
    }
  })

  it('4.6 y D-62-15: el total venció (409 `estado-pedido` vencido): el estado vencido, sin casilla ni «Pagar»', async () => {
    apiPedido({ 'POST /pagar$': problema(409, 'estado-pedido', { estado: 'vencido' }) }, { pedido: confirmado() })
    abrir()
    await titulo()
    await userEvent.click(casilla())
    await userEvent.click(pagar())
    const aviso = await screen.findByText('Pasaron 15 minutos y el total venció. Vuelve a confirmar para ver lo que hay y su precio.')
    await waitFor(() => expect(aviso.closest('[tabindex="-1"]')).toHaveFocus())
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(screen.queryByRole('button', { name: /Pagar/ })).toBeNull()
    expect(macizos()).toEqual([screen.getByRole('button', { name: 'Volver a confirmar' })])
  })

  it('4.6: el pedido cambió (412): la nota de 11.2 bajo la bajada y el pedido como quedó', async () => {
    const actual = confirmado({ etag: 'p3', vence_en: '2026-11-11T20:00:00Z' })
    apiPedido({ 'POST /pagar$': problema(412, 'version-desactualizada', { actual }) }, { pedido: confirmado() })
    abrir()
    await titulo()
    await userEvent.click(casilla())
    await userEvent.click(pagar())
    const nota = await screen.findByText('Este pedido cambió mientras lo revisabas. Te mostramos cómo quedó.')
    await waitFor(() => expect(nota.closest('[data-aviso]')).toHaveFocus())
    expect(screen.getByRole('region', { name: 'Tu pedido' })).toHaveTextContent('Este total vale hasta las 17:00.')
    expect(enviados).toEqual([])
  })

  it('4.6: las condiciones cambiaron (409): la casilla se desmarca con su error y el foco, y se vuelve a leer el resumen', async () => {
    const nuevas = confirmado({ resumen: { ...confirmado().resumen!, condiciones: { version: '0.2', huella: 'c'.repeat(64), enlace: '/v1/condiciones-pedido' } } })
    const api = apiPedido(
      { 'POST /pagar$': problema(409, 'condiciones-cambiaron', { version_vigente: '0.2' }), 'GET /pedido-en-curso$': enOrden({ status: 200, cuerpo: confirmado() }, { status: 200, cuerpo: nuevas }) },
      { pedido: confirmado() },
    )
    abrir()
    await titulo()
    await userEvent.click(casilla())
    await userEvent.click(pagar())
    expect(await screen.findByText('Las condiciones del pedido cambiaron. Léelas de nuevo y marca la casilla para pagar.')).toBeVisible()
    expect(casilla()).not.toBeChecked()
    await waitFor(() => expect(casilla()).toHaveFocus())
    await waitFor(() => expect(api.pedidas.filter((p) => p.ruta.endsWith('/pedido-en-curso'))).toHaveLength(2))
    // El segundo intento manda la versión nueva.
    await userEvent.click(casilla())
    await userEvent.click(pagar())
    await waitFor(() => expect(pagos(api.pedidas)).toHaveLength(2))
    expect((pagos(api.pedidas)[1].cuerpo as { condiciones: { version: string } }).condiciones.version).toBe('0.2')
  })

  it('4.6: un 409 `idempotencia-en-curso` se repite una vez con la misma clave', async () => {
    const api = apiPedido({ 'POST /pagar$': enOrden(problema(409, 'idempotencia-en-curso'), { status: 201, cuerpo: INICIO }) }, { pedido: confirmado() })
    abrir()
    await titulo()
    await userEvent.click(casilla())
    await userEvent.click(pagar())
    await waitFor(() => expect(enviados).toHaveLength(1), { timeout: 5000 })
    const [a, b] = pagos(api.pedidas)
    expect(a.cabeceras['Idempotency-Key']).toBe(b.cabeceras['Idempotency-Key'])
    expect(screen.queryByText(/No pudimos abrir Webpay/)).toBeNull()
  })

  it('cada toque de «Pagar» lleva una clave nueva', async () => {
    const api = apiPedido({ 'POST /pagar$': problema(503, 'pasarela-no-disponible') }, { pedido: confirmado() })
    abrir()
    await titulo()
    await userEvent.click(casilla())
    await userEvent.click(pagar())
    await screen.findByText(/Webpay no responde ahora/)
    await userEvent.click(pagar())
    await waitFor(() => expect(pagos(api.pedidas)).toHaveLength(2))
    const [a, b] = pagos(api.pedidas)
    expect(a.cabeceras['Idempotency-Key']).not.toBe(b.cabeceras['Idempotency-Key'])
  })
})

describe('Quién paga (D-62-8 y D-62-14)', () => {
  it('4.2: el cuidador ve «Pagan quien administra el grupo y quien paga.» en lugar de la casilla, la frase y «Pagar», sin macizo', async () => {
    apiPedido({}, { pedido: confirmado() })
    abrir('cuidador')
    await titulo()
    expect(screen.getByText('Pagan quien administra el grupo y quien paga.')).toBeVisible()
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(screen.queryByText(/Te llevamos a Webpay/)).toBeNull()
    expect(screen.queryByRole('button', { name: /Pagar/ })).toBeNull()
    expect(macizos()).toEqual([])
    expect(screen.getByRole('link', { name: 'Condiciones del pedido (se abre en otra pestaña)' })).toBeVisible()
    expect(screen.getByText('No pagar no tiene costo.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Cancelar pedido' })).toBeVisible()
  })

  it('5: el pagador ve la casilla y «Pagar», y el aviso de los 2 minutos sin «Volver a confirmar»', async () => {
    apiPedido({}, { pedido: confirmado({ vigencia_segundos: 60 }) })
    abrir('pagador')
    await titulo()
    expect(casilla()).toBeVisible()
    expect(pagar()).toBeVisible()
    expect(await screen.findByText('Quedan 2 minutos para pagar este total.')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Volver a confirmar' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Cancelar pedido' })).toBeNull()
  })

  it('5: con el total vencido, el pagador no ve casilla, frase ni «Pagar», y ningún macizo', async () => {
    apiPedido({}, { pedido: confirmado({ estado: 'vencido', vigencia_segundos: 0 }) })
    abrir('pagador')
    await titulo()
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(screen.queryByText(/Te llevamos a Webpay/)).toBeNull()
    expect(screen.queryByRole('button', { name: /Pagar/ })).toBeNull()
    expect(macizos()).toEqual([])
  })
})

describe('Pago en curso (6)', () => {
  it('6.2: el admin en el resumen, sin casilla, «Pagar», aviso de los 2 minutos ni «Volver a confirmar»; «Cancelar pedido» sigue', async () => {
    apiPedido({}, { pedido: confirmado({ pago_en_curso: true, vigencia_segundos: 60 }) })
    abrir()
    await titulo()
    expect(screen.getByText('Ya hay un pago en curso para este pedido. Espera su resultado antes de intentar de nuevo.')).toBeVisible()
    expect(screen.getByText('Si saliste de Webpay sin terminar, se cierra solo en menos de 15 minutos.')).toBeVisible()
    const nota = screen.getByText(/Ya hay un pago en curso/).closest('[data-aviso], div.rounded-xl')!
    expect(nota.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-credit-card/)
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(screen.queryByRole('button', { name: /Pagar/ })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Volver a confirmar' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Cambiar el pedido' })).toBeNull()
    expect(screen.queryByText('Quedan 2 minutos para pagar este total.')).toBeNull()
    expect(macizos()).toEqual([])
    expect(screen.getByRole('button', { name: 'Cancelar pedido' })).toBeVisible()
  })

  it('6.1: el cuidador en el resumen ve la nota de quien quiere cambiar', async () => {
    apiPedido({}, { pedido: confirmado({ pago_en_curso: true }) })
    abrir('cuidador')
    await titulo()
    expect(screen.getByText('Hay un pago en curso para este pedido. Espera su resultado antes de cambiarlo.')).toBeVisible()
    expect(screen.getByText('Si alguien salió de Webpay sin terminar, se cierra solo en menos de 15 minutos.')).toBeVisible()
    expect(screen.queryByText('Pagan quien administra el grupo y quien paga.')).toBeNull()
  })

  it('6.1: en el pedido, sin controles ni «Ver el total»; «Ver el resumen» secundario y «Cancelar pedido»', async () => {
    apiPedido({}, { pedido: confirmado({ pago_en_curso: true }) })
    abrir('admin', '/insumos/pedido')
    await screen.findByRole('heading', { level: 1, name: 'Tu pedido' })
    expect(await screen.findByText('Hay un pago en curso para este pedido. Espera su resultado antes de cambiarlo.')).toBeVisible()
    expect(screen.queryByText('Ya confirmaste el total. Para cambiar algo, toca «Cambiar el pedido».')).toBeNull()
    expect(screen.queryByRole('button', { name: /Ver el total|Cambiar el pedido|Sacar/ })).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.getByRole('button', { name: 'Ver el resumen' }).className).not.toMatch(/\bbg-turquesa\b/)
    expect(macizos()).toEqual([])
    expect(screen.getByRole('button', { name: 'Cancelar pedido' })).toBeVisible()
  })

  it('6.1 y criterio 13: un 409 `pago-en-curso` al cambiar la cantidad muestra la nota con el foco y deja la pantalla sin controles', async () => {
    const api = apiPedido({ 'PUT /lineas$': problema(409, 'pago-en-curso'), 'GET /pedido-en-curso$': enOrden({ status: 200, cuerpo: borrador() }, { status: 200, cuerpo: confirmado({ pago_en_curso: true }) }) })
    const { urgente } = abrir('admin', '/insumos/pedido')
    const campo = await screen.findByRole('textbox', { name: 'Cantidad Pañal adulto M x30' })
    await userEvent.clear(campo)
    await userEvent.type(campo, '3')
    await userEvent.tab()
    const nota = (await screen.findByText('Hay un pago en curso para este pedido. Espera su resultado antes de cambiarlo.')).closest('[data-aviso]')!
    await waitFor(() => expect(nota).toHaveFocus())
    await waitFor(() => expect(urgente).toHaveTextContent('Hay un pago en curso para este pedido.'))
    await waitFor(() => expect(screen.queryByRole('textbox')).toBeNull())
    expect(api.escrituras().map((x) => x.ruta)).toEqual([`/v1/pedidos/${PEDIDO_ID}/lineas`])
  })

  it('6.1: «Revisar de nuevo» anuncia si sigue, y si terminó redibuja y lo dice', async () => {
    apiPedido({
      'GET /pedido-en-curso$': enOrden({ status: 200, cuerpo: confirmado({ pago_en_curso: true }) }, { status: 200, cuerpo: confirmado({ pago_en_curso: true }) }, { status: 200, cuerpo: confirmado() }),
    })
    const { amable } = abrir('admin', '/insumos/pedido')
    const revisar = await screen.findByRole('button', { name: 'Revisar de nuevo' })
    expect(revisar.className).not.toMatch(/\bbg-turquesa\b/)
    await userEvent.click(revisar)
    await waitFor(() => expect(amable).toHaveTextContent('Todavía hay un pago en curso.'))
    await userEvent.click(screen.getByRole('button', { name: 'Revisar de nuevo' }))
    await waitFor(() => expect(amable).toHaveTextContent('El pago terminó. Te mostramos cómo quedó el pedido.'))
    expect(screen.queryByText(/Hay un pago en curso/)).toBeNull()
    expect(screen.getByText('Ya confirmaste el total. Para cambiar algo, toca «Cambiar el pedido».')).toBeVisible()
  })

  it('6.3: el diálogo de cancelar suma el párrafo en negrita, y la nota dice que se anula si se aprueba', async () => {
    apiPedido({ 'POST /cancelar$': { status: 200, cuerpo: confirmado({ estado: 'cancelado' }) } }, { pedido: confirmado({ pago_en_curso: true }) })
    abrir()
    await titulo()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar pedido' }))
    const dialogo = screen.getByRole('dialog', { name: '¿Cancelar este pedido?' })
    const parrafo = within(dialogo).getByText('Hay un pago en curso. Si Transbank lo aprueba, lo anulamos completo el mismo día, a la misma tarjeta.')
    expect(parrafo.className).toMatch(/\bfont-bold\b/)
    expect(dialogo).toHaveAccessibleDescription('No tiene costo. Hay un pago en curso. Si Transbank lo aprueba, lo anulamos completo el mismo día, a la misma tarjeta.')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    expect((await screen.findAllByText('Cancelamos el pedido. Si el pago en curso se aprueba, lo anulamos completo el mismo día.'))[0]).toBeVisible()
    expect(screen.queryByText('Cancelamos el pedido. No se cobró nada.')).toBeNull()
  })

  it('6.3: sin pago en curso, el diálogo de siempre', async () => {
    apiPedido({}, { pedido: confirmado() })
    abrir()
    await titulo()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar pedido' }))
    const dialogo = screen.getByRole('dialog', { name: '¿Cancelar este pedido?' })
    expect(dialogo).toHaveAccessibleDescription('No tiene costo.')
    expect(within(dialogo).queryByText(/Hay un pago en curso/)).toBeNull()
  })

  it('4.6: un 409 `pago-en-curso` al pagar muestra 6.2 con el foco', async () => {
    apiPedido({ 'POST /pagar$': problema(409, 'pago-en-curso') }, { pedido: confirmado() })
    abrir('pagador')
    await titulo()
    await userEvent.click(casilla())
    await userEvent.click(pagar())
    const nota = (await screen.findByText('Ya hay un pago en curso para este pedido. Espera su resultado antes de intentar de nuevo.')).closest('[data-aviso]')!
    await waitFor(() => expect(nota).toHaveFocus())
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(screen.queryByRole('button', { name: /Pagar/ })).toBeNull()
  })
})

describe('El pedido pagado en «Pedido» (8)', () => {
  it('admin: al final, «Pedido pagado», «Pagado», la referencia, la fecha y el total; «Ver el comprobante» lo lleva en memoria', async () => {
    apiPedido({ 'GET /pedido-pagado$': { status: 200, cuerpo: pago() } }, { pedido: borrador() })
    abrir('admin', '/insumos/pedido')
    const bloque = within((await screen.findByRole('heading', { level: 2, name: 'Pedido pagado' })).closest('section')!)
    expect(bloque.getByText('Pagado').querySelector('svg')!.getAttribute('class')).toMatch(/lucide-check/)
    expect(bloque.getByText(/Pedido 4821/)).toHaveTextContent('Pedido 4821 · 11/11/2026 a las 16:41')
    expect(bloque.getByText('Total pagado:').closest('p')).toHaveTextContent('Total pagado: $57.460')
    const ver = bloque.getByRole('button', { name: 'Ver el comprobante' })
    expect(ver.className).not.toMatch(/\bbg-turquesa\b/)
    // Va después del carrito.
    const carrito = screen.getByRole('heading', { level: 2, name: 'Pañal adulto M x30' })
    expect(carrito.compareDocumentPosition(ver) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    await userEvent.click(ver)
    expect(window.location.pathname).toBe('/insumos/pedido/pago')
    expect(window.location.search + window.location.hash).toBe('')
    expect(tomarComprobante(PERSONA_ID)?.comprobante?.referencia).toBe('4821')
  })

  it('también con el pedido vacío, y quien no pagó lo ve igual (sin tarjeta)', async () => {
    apiPedido({ 'GET /pedido-pagado$': { status: 200, cuerpo: pago({ comprobante: comprobanteAjeno() }) } }, { pedido: null })
    abrir('cuidador', '/insumos/pedido')
    expect(await screen.findByRole('heading', { level: 2, name: 'Pedido pagado' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Ver el comprobante' })).toBeVisible()
  })

  it('observador: solo «Pedido pagado» y «Pagado» (D-62-2)', async () => {
    apiPedido({ 'GET /pedido-pagado$': { status: 200, cuerpo: { pedido_id: PEDIDO_ID, estado: 'pagado' } } }, { pedido: null })
    abrir('observador', '/insumos/pedido')
    const bloque = within((await screen.findByRole('heading', { level: 2, name: 'Pedido pagado' })).closest('section')!)
    expect(bloque.getByText('Pagado')).toBeVisible()
    expect(bloque.queryByText(/Pedido 4821|Total pagado|\$/)).toBeNull()
    expect(bloque.queryByRole('button')).toBeNull()
  })

  it('sin pedido pagado (404) no hay bloque', async () => {
    apiPedido({ 'GET /pedido-pagado$': NO_ENCONTRADO }, { pedido: borrador() })
    abrir('admin', '/insumos/pedido')
    await screen.findByRole('heading', { level: 2, name: 'Pañal adulto M x30' })
    expect(screen.queryByRole('heading', { name: 'Pedido pagado' })).toBeNull()
  })
})

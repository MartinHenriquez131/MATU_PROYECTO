// MATU-62: la vuelta de Webpay y el comprobante (especificación docs/diseno/matu-62-pago.md v1.0,
// secciones 2, 7 y 10). La dirección se limpia antes de todo, «Estamos confirmando tu pago», la
// respuesta que tarda, los siete resultados, el comprobante para quien pagó y para quien no, las
// devoluciones, el retorno repetido, la vuelta sin sesión y la recarga. Solo datos sintéticos.
import { act, cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { fijarGrupo } from '../src/compartido/api/sesion'
import { PantallaPago, VueltaSinSesion } from '../src/familia/Pago'
import { capturarRetorno, fijarComprobante, hayVuelta, leerValores, leerVuelta, olvidarTodoElPago } from '../src/familia/vueltaPago'
import { familiaFalsa } from './familiaFalsa'
import { apiPedido, confirmado, conRegionesGlobales, enOrden, NO_ENCONTRADO, PEDIDO_ID, persona, PERSONA_ID, problema, type Respuesta } from './pedidoFalso'
import { comprobante, comprobanteAjeno, devolucion, GRUPO_ID, OTRA_PERSONA_ID, OTRO_GRUPO_ID, pago, retorno, TOKEN } from './pagoFalso'

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
afterEach(() => {
  olvidarTodoElPago()
  vi.useRealTimers()
})

/** Llega desde Webpay: la dirección con lo que trae Transbank, y main.tsx la captura. */
function volverDeWebpay(resto = `?token_ws=${TOKEN}`) {
  window.history.replaceState(null, '', `/insumos/pedido/pago${resto}`)
  capturarRetorno()
}

function abrir(rol: Rol = 'admin', cambios: Record<string, unknown> = {}) {
  const p = persona()
  contexto = familiaFalsa({ persona: p, personas: [p], personaId: PERSONA_ID, grupoId: GRUPO_ID, rol, capa3: true, elegir: vi.fn(async () => {}), salir: vi.fn(async () => {}), ...cambios } as never)
  return conRegionesGlobales(<PantallaPago />)
}

const h1 = (nombre: string) => screen.findByRole('heading', { level: 1, name: nombre })
const rutas = (r: Record<string, Respuesta | ((...a: never[]) => Respuesta | Promise<Respuesta>)>) => apiPedido(r as never, { pedido: confirmado() })
const macizos = () => screen.queryAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className))

describe('La dirección de la vuelta (7.1, P1, criterio 6)', () => {
  it('la query con token_ws se lee y se borra con replaceState antes de todo, sin dejar una entrada en el historial', () => {
    const largo = window.history.length
    volverDeWebpay()
    expect(window.location.pathname).toBe('/insumos/pedido/pago')
    expect(window.location.search).toBe('')
    expect(window.location.hash).toBe('')
    expect(window.history.length).toBe(largo)
    expect(window.history.state).toBeNull()
    expect(leerVuelta()?.cuerpo).toEqual({ token_ws: TOKEN })
  })

  it('el fragmento del 303 con TBK_*, solo los cuatro campos de Transbank y con su formato', () => {
    volverDeWebpay('#TBK_TOKEN=abc123&TBK_ORDEN_COMPRA=orden-1&TBK_ID_SESION=sesion_1&otro=x')
    expect(window.location.hash).toBe('')
    expect(leerVuelta()?.cuerpo).toEqual({ TBK_TOKEN: 'abc123', TBK_ORDEN_COMPRA: 'orden-1', TBK_ID_SESION: 'sesion_1' })
    expect(leerValores('?token_ws=<script>&TBK_ORDEN_COMPRA=' + 'x'.repeat(27))).toBeNull()
  })

  it('sin valores de Transbank la dirección igual queda limpia y no hay vuelta; en otra ruta no se toca', () => {
    volverDeWebpay('?otro=1')
    expect(window.location.search).toBe('')
    expect(hayVuelta()).toBe(false)
    window.history.replaceState(null, '', '/insumos/pedido?token_ws=abc')
    capturarRetorno()
    expect(window.location.search).toBe('?token_ws=abc')
    expect(hayVuelta()).toBe(false)
  })
})

describe('Estamos confirmando tu pago (7.2 y 7.3)', () => {
  it('7.2: el título, «No cierres esta pantalla.» en una región ocupada, sin animación, sin macizo y sin el aviso del piloto', async () => {
    rutas({ 'POST ^/v1/pagos/retorno$': () => new Promise<Respuesta>(() => {}) })
    volverDeWebpay()
    abrir()
    expect(await h1('Estamos confirmando tu pago')).toBeVisible()
    const texto = screen.getByText('No cierres esta pantalla.')
    expect(texto.className).toMatch(/\btext-lg\b/)
    expect(texto.closest('[aria-busy="true"]')).not.toBeNull()
    expect(document.querySelector('.animate-spin, .animate-pulse, .animate-bounce')).toBeNull()
    expect(macizos()).toEqual([])
    expect(screen.queryByText('Precios de ejemplo.')).toBeNull()
    expect(document.title).toBe('Estamos confirmando tu pago · MATU')
  })

  it('7.1: manda lo que trajo la dirección a POST /v1/pagos/retorno, sin X-Grupo-Id', async () => {
    const api = rutas({ 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno() }, 'GET /pago$': { status: 200, cuerpo: pago() } })
    volverDeWebpay()
    abrir()
    await h1('Pagaste tu pedido')
    const r = api.pedidas.find((p) => p.ruta === '/v1/pagos/retorno')!
    expect(r.metodo).toBe('POST')
    expect(r.cuerpo).toEqual({ token_ws: TOKEN })
    expect(r.cabeceras).not.toHaveProperty('X-Grupo-Id')
    expect(api.pedidas.filter((p) => p.ruta === '/v1/pagos/retorno')).toHaveLength(1)
  })

  it('7.3: pasados 10 segundos sin respuesta, la nota de que tarda, sin botón de pagar', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    rutas({ 'POST ^/v1/pagos/retorno$': () => new Promise<Respuesta>(() => {}) })
    volverDeWebpay()
    abrir()
    await h1('Estamos confirmando tu pago')
    expect(screen.queryByText(/Todavía no tenemos la respuesta de Transbank/)).toBeNull()
    await act(async () => {
      vi.advanceTimersByTime(10_000)
    })
    expect(await screen.findByText('Todavía no tenemos la respuesta de Transbank. Si pagaste, no pagues de nuevo: te avisamos aquí apenas la tengamos, en menos de 15 minutos.')).toBeVisible()
    expect(screen.queryByRole('button', { name: /Pagar|Intentar/ })).toBeNull()
  })

  it('7.3: `pendiente`, «Revisar ahora» anuncia si sigue igual, y cuando llega el resultado cambian el h1 y el título y el foco va al h1', async () => {
    const api = rutas({
      'POST ^/v1/pagos/retorno$': enOrden(
        { status: 200, cuerpo: retorno({ resultado: 'pendiente', volver_a_preguntar_en: 15 }) },
        { status: 200, cuerpo: retorno({ resultado: 'pendiente', volver_a_preguntar_en: 15 }) },
        { status: 200, cuerpo: retorno() },
      ),
      'GET /pago$': { status: 200, cuerpo: pago() },
    })
    volverDeWebpay()
    const { amable } = abrir()
    const nota = await screen.findByText(/Todavía no tenemos la respuesta de Transbank/)
    expect(nota.closest('[data-aviso]')).toHaveAttribute('data-aviso', 'status')
    expect(nota.closest('[data-aviso]')!.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-clock/)
    const revisar = screen.getByRole('button', { name: 'Revisar ahora' })
    expect(revisar.className).not.toMatch(/\bbg-turquesa\b/)
    expect(screen.getByRole('button', { name: 'Ir a tu pedido' })).toBeVisible()
    await userEvent.click(revisar)
    await waitFor(() => expect(amable).toHaveTextContent('Todavía no tenemos la respuesta.'))
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Estamos confirmando tu pago')
    await userEvent.click(screen.getByRole('button', { name: 'Revisar ahora' }))
    const titulo = await h1('Pagaste tu pedido')
    await waitFor(() => expect(titulo).toHaveFocus())
    expect(document.title).toBe('Pagaste tu pedido · MATU')
    // Siempre el mismo cuerpo: el retorno es idempotente por token.
    expect(new Set(api.pedidas.filter((p) => p.ruta === '/v1/pagos/retorno').map((p) => JSON.stringify(p.cuerpo)))).toEqual(new Set([JSON.stringify({ token_ws: TOKEN })]))
  })

  it('7.3: sin red, la nota de que tarda (el retorno se reintenta)', async () => {
    rutas({ 'POST ^/v1/pagos/retorno$': problema(503, 'servicio-no-disponible') })
    volverDeWebpay()
    abrir()
    expect(await screen.findByText(/Todavía no tenemos la respuesta de Transbank/)).toBeVisible()
  })

  it('valores que no son de ninguna venta (404): va a «Tu pedido» y olvida la vuelta', async () => {
    rutas({ 'POST ^/v1/pagos/retorno$': NO_ENCONTRADO })
    volverDeWebpay()
    abrir()
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
    expect(hayVuelta()).toBe(false)
  })
})

describe('Pagaste tu pedido: el comprobante (7.4 y 7.5)', () => {
  async function comprobanteDe(c = comprobante(), r = retorno(), rol: Rol = 'admin') {
    const api = rutas({ 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: r }, 'GET /pago$': { status: 200, cuerpo: pago({ comprobante: c }) } })
    volverDeWebpay()
    const regiones = abrir(rol)
    await h1('Pagaste tu pedido')
    return { api, ...regiones, boleta: within(screen.getByRole('region', { name: 'Comprobante Pedido 4821' })) }
  }

  it('el título, la bajada con la misma cifra, el aviso del piloto una vez, y ningún macizo', async () => {
    await comprobanteDe()
    expect(screen.getByText(/Pagaste/, { selector: 'p' })).toHaveTextContent('Pagaste $57.460 una sola vez. Es el total que viste antes de pagar.')
    expect(screen.getAllByText('Precios de ejemplo.')).toHaveLength(1)
    expect(macizos()).toEqual([])
    const baldosa = screen.getByRole('heading', { level: 1 }).previousElementSibling!
    expect(baldosa.className).toMatch(/\bbg-ok-fondo\b/)
    expect(baldosa.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-circle-check/)
  })

  it('7.5.1: la referencia, la fecha, los productos, el envío, «Total pagado», «Pagado», la tarjeta de débito y el código', async () => {
    const { boleta } = await comprobanteDe()
    expect(boleta.getByRole('heading', { level: 2, name: 'Comprobante' })).toBeVisible()
    expect(boleta.getByText('Pedido 4821')).toBeVisible()
    expect(boleta.getByText(/a las/).closest('p')).toHaveTextContent('11/11/2026 a las 16:41')
    expect(boleta.getByText('Pañal adulto M x30').nextElementSibling).toHaveTextContent('2 × $12.990$25.980')
    expect(boleta.getByText('Envío (uno por pedido)').closest('p')).toHaveTextContent('$3.990')
    expect(boleta.getByText('Total pagado').closest('p')).toHaveTextContent('Total pagado$57.460')
    expect(boleta.getByText('Total pagado').closest('p')!.className).toMatch(/\btext-2xl\b/)
    expect(boleta.getByText('Pagado').querySelector('svg')!.getAttribute('class')).toMatch(/lucide-check/)
    expect(boleta.getByText(/Tarjeta de débito terminada en/)).toHaveTextContent('Tarjeta de débito terminada en 4051')
    expect(boleta.getByText(/Código de autorización/)).toHaveTextContent('Código de autorización 123456')
    expect(boleta.queryByText('Lo pagó otra persona de tu grupo.')).toBeNull()
  })

  it('7.5.2 y criterio 10: el sello del piloto dentro del comprobante, antes de los productos, con la primera frase en negrita', async () => {
    const { boleta } = await comprobanteDe()
    const sello = boleta.getByText('Pago de prueba. No se cobró dinero real.')
    expect(sello.tagName).toBe('STRONG')
    expect(sello.closest('p')).toHaveTextContent('Pago de prueba. No se cobró dinero real. Este comprobante no es una boleta.')
    expect(sello.compareDocumentPosition(boleta.getByText('Pañal adulto M x30')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // La hoja impresa, fuera de #raiz, con el sello arriba.
    const hoja = document.querySelector('[data-impresion]')!
    expect(hoja.textContent).toMatch(/^Comprobante · Pedido 4821.*Pago de prueba\. No se cobró dinero real\. Este comprobante no es una boleta\..*Pañal adulto M x30/)
    expect(hoja.className).toMatch(/\bhidden\b/)
  })

  it('criterio 11: «Comprobante», nunca «Boleta»; ni «IVA», «rechazado», «fallido», «inválido» ni «token»', async () => {
    await comprobanteDe()
    expect(screen.queryByRole('heading', { name: /Boleta/i })).toBeNull()
    const texto = document.body.textContent ?? ''
    expect(texto).not.toMatch(/IVA|rechaz|fallid|inválid|token|reserva|monto real/i)
    expect(texto.match(/boleta/gi)).toEqual(['boleta', 'boleta'])
  })

  it('7.5.3: datos del pedido, la versión aceptada con su enlace, y lo que te garantizamos', async () => {
    await comprobanteDe()
    const datos = within(screen.getByRole('region', { name: 'Datos del pedido' }))
    expect(datos.getByText('Vende: MATU, piloto académico, sin persona jurídica.')).toBeVisible()
    expect(datos.getByText('Entrega: Entre 24 y 48 horas hábiles')).toBeVisible()
    expect(datos.getByText(/Condiciones aceptadas/)).toHaveTextContent('Condiciones aceptadas: versión 0.2, el 11/11/2026')
    const enlace = datos.getByRole('link', { name: 'Condiciones del pedido, versión 0.2 (se abre en otra pestaña)' })
    expect(enlace).toHaveAttribute('href', '/condiciones-pedido?version=0.2')
    expect(enlace).toHaveAttribute('target', '_blank')
    expect(enlace.className).toMatch(/\bmin-h-12\b/)
    const garantias = within(screen.getByRole('region', { name: 'Lo que te garantizamos' }))
    expect(garantias.getAllByRole('listitem').map((l) => l.textContent)).toEqual([
      'Derecho a retracto: tienes 10 días desde que lo recibes.',
      'Si un producto no llega, te devolvemos su precio el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco.',
      'Quien administra el grupo puede cancelar sin costo mientras el comercio no empiece a preparar.',
      '¿Algo no está bien? Escríbenos a cuidaconmatu@gmail.com.',
    ])
    expect(garantias.getByRole('link', { name: 'cuidaconmatu@gmail.com' })).toHaveAttribute('href', 'mailto:cuidaconmatu@gmail.com')
  })

  it('7.5.4 y 7.5.5: en el piloto no promete correo; «Imprimir o guardar en PDF» llama a print; «Ir a tu pedido»', async () => {
    const imprimir = vi.spyOn(window, 'print').mockImplementation(() => {})
    await comprobanteDe()
    expect(screen.getByText('En el piloto, el comprobante no se envía por correo. Imprímelo o guárdalo en PDF si lo necesitas.')).toBeVisible()
    expect(screen.queryByText(/Te enviamos este comprobante/)).toBeNull()
    expect(document.body.textContent).not.toContain('carmen@example.com')
    const boton = screen.getByRole('button', { name: 'Imprimir o guardar en PDF' })
    expect(boton.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-printer/)
    await userEvent.click(boton)
    expect(imprimir).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: 'Ir a tu pedido' }))
    expect(window.location.pathname).toBe('/insumos/pedido')
  })

  it('7.4.2 y criterio 24: el comprobante va antes que los datos del pedido en el DOM', async () => {
    const { boleta } = await comprobanteDe()
    const datos = screen.getByRole('heading', { level: 2, name: 'Datos del pedido' })
    expect(boleta.getByText('Pedido 4821').compareDocumentPosition(datos) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('D-62-2 y criterio 9: quien no pagó lee «Lo pagó otra persona de tu grupo.», sin tarjeta, código ni correo', async () => {
    const { boleta } = await comprobanteDe(comprobanteAjeno(), retorno(), 'admin')
    expect(boleta.getByText('Lo pagó otra persona de tu grupo.')).toBeVisible()
    expect(boleta.queryByText(/Tarjeta de|Código de autorización/)).toBeNull()
    expect(screen.queryByText(/En el piloto, el comprobante no se envía|Te enviamos/)).toBeNull()
  })

  it('P5: crédito en cuotas, «Tarjeta de crédito terminada en 4051, en 3 cuotas»', async () => {
    const { boleta } = await comprobanteDe(comprobante({ tarjeta: { tipo: 'credito', ultimos4: '4051', cuotas: 3 } }))
    expect(boleta.getByText(/Tarjeta de crédito/)).toHaveTextContent('Tarjeta de crédito terminada en 4051, en 3 cuotas')
  })

  it('crédito sin cuotas (0 o 1), sin «en n cuotas»', async () => {
    const { boleta } = await comprobanteDe(comprobante({ tarjeta: { tipo: 'credito', ultimos4: '4051', cuotas: 1 } }))
    expect(boleta.getByText(/Tarjeta de crédito/)).toHaveTextContent(/^Tarjeta de crédito terminada en 4051$/)
  })

  it('7.6: el pago tardío respetado, una nota rocío bajo la bajada y antes del aviso del piloto', async () => {
    await comprobanteDe(comprobante({ tardio: true }), retorno({ resultado: 'aprobado_tardio' }))
    const nota = screen.getByText(/Tu pago llegó después de que venció el total/).closest('p')!
    expect(nota).toHaveTextContent('Tu pago llegó después de que venció el total, y lo respetamos: pagaste $57.460, el precio que aceptaste.')
    expect(nota.closest('.bg-rocio')).not.toBeNull()
    expect(nota.compareDocumentPosition(screen.getByText('Precios de ejemplo.')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('7.8: el retorno repetido suma «Este pago ya está registrado. No se cobró dos veces.»', async () => {
    await comprobanteDe(comprobante(), retorno({ ya_registrado: true }))
    expect(screen.getByText('Este pago ya está registrado. No se cobró dos veces.')).toBeVisible()
  })

  it('7.7 y criterio 18: una devolución hecha resta exacto y una en curso no; cada una con su nota', async () => {
    const c = comprobante({ devoluciones: [devolucion(), devolucion({ monto: 1000, producto: { ...devolucion().producto!, nombre: 'Toallitas húmedas x80' }, estado: 'en_curso', hecha_en: null, solicitada_en: '2026-11-12T16:00:00Z' })] })
    const { boleta } = await comprobanteDe(c)
    expect(screen.getByText(/Devolvimos/, { selector: 'p' })).toHaveTextContent(
      'Devolvimos $26.490 a tu tarjeta terminada en 4051, por Suplemento vainilla x12. Cuándo lo ves en tu cuenta depende de tu banco.',
    )
    expect(screen.getByText(/Estamos devolviendo/, { selector: 'p' })).toHaveTextContent(
      'Estamos devolviendo $1.000 a tu tarjeta. Si no se completa hoy, te escribimos. MATU nunca te pide los datos de tu banco por mensaje.',
    )
    expect(boleta.getByText('Devolvimos: Suplemento vainilla x12').closest('p')).toHaveTextContent('−$26.490')
    expect(boleta.queryByText(/Devolvimos: Toallitas/)).toBeNull()
    expect(boleta.getByText('Pagaste en total').closest('p')).toHaveTextContent('Pagaste en total$30.970')
    expect(boleta.getByText('Total pagado').closest('p')).toHaveTextContent('$57.460')
  })

  it('7.7: para quien no pagó, «a la tarjeta con que se pagó» y «le escribimos a quien pagó»; el pedido completo', async () => {
    const c = comprobanteAjeno({
      devoluciones: [devolucion({ ultimos4: null, producto: null, monto: 57460 }), devolucion({ ultimos4: null, estado: 'en_curso', hecha_en: null, solicitada_en: '2026-11-12T16:00:00Z' })],
    })
    await comprobanteDe(c)
    expect(screen.getByText(/^Devolvimos/, { selector: 'p' })).toHaveTextContent('Devolvimos $57.460 a la tarjeta con que se pagó, por tu pedido completo. Cuándo se ve en la cuenta depende del banco.')
    expect(screen.getByText(/Estamos devolviendo/, { selector: 'p' })).toHaveTextContent(
      'Estamos devolviendo $26.490 a la tarjeta con que se pagó. Si no se completa hoy, le escribimos a quien pagó. MATU nunca pide los datos de un banco por mensaje.',
    )
    expect(document.body.textContent).not.toContain('4051')
  })
})

describe('Los otros resultados (7.9, 7.11 y 7.12)', () => {
  it('7.11: no aprobado con el total vigente: el plazo e «Intentar de nuevo», único macizo, que lleva al resumen', async () => {
    rutas({ 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno({ resultado: 'no_aprobado' }) } })
    volverDeWebpay()
    abrir()
    await h1('El pago no se hizo')
    expect(screen.getByText('Transbank no lo aprobó y no se cobró nada. Puedes intentarlo con otra tarjeta mientras el total siga vigente.')).toBeVisible()
    expect(screen.getByText(/Este total vale hasta las/)).toHaveTextContent('Este total vale hasta las 16:45.')
    const intentar = screen.getByRole('button', { name: 'Intentar de nuevo' })
    expect(macizos()).toEqual([intentar])
    const baldosa = screen.getByRole('heading', { level: 1 }).previousElementSibling!
    expect(baldosa.className).not.toMatch(/pronto/)
    expect(baldosa.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-credit-card/)
    expect(screen.queryByText('Precios de ejemplo.')).toBeNull()
    await userEvent.click(intentar)
    expect(window.location.pathname).toBe('/insumos/pedido/resumen')
  })

  it('7.11 y criterio 16: con el total vencido, el admin ve «Volver a confirmar», que confirma y lleva al resumen', async () => {
    const api = apiPedido(
      { 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno({ resultado: 'no_aprobado' }) }, 'POST /confirmar$': { status: 200, cuerpo: confirmado({ etag: 'p3' }) } },
      { pedido: confirmado({ estado: 'vencido', vigencia_segundos: 0 }) },
    )
    volverDeWebpay()
    abrir()
    await h1('El pago no se hizo')
    expect(screen.getByText(/Este total venció a las/)).toHaveTextContent('Este total venció a las 16:45.')
    expect(screen.queryByRole('button', { name: 'Intentar de nuevo' })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Volver a confirmar' }))
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido/resumen'))
    expect(api.escrituras().map((x) => x.ruta)).toContain(`/v1/pedidos/${PEDIDO_ID}/confirmar`)
  })

  it('7.11: con el total vencido, el pagador lee que se lo pida a quien armó el pedido, sin macizo', async () => {
    apiPedido({ 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno({ resultado: 'no_aprobado' }) } }, { pedido: confirmado({ estado: 'vencido', vigencia_segundos: 0 }) })
    volverDeWebpay()
    abrir('pagador')
    await h1('El pago no se hizo')
    expect(screen.getByText('Pasaron 15 minutos y el total venció. Pídele a quien armó el pedido que lo vuelva a confirmar.')).toBeVisible()
    expect(macizos()).toEqual([])
    expect(screen.getByRole('button', { name: 'Ir a tu pedido' })).toBeVisible()
  })

  it('7.12: «Saliste de Webpay sin pagar» y «Se acabó el tiempo para pagar en Webpay», con «No se cobró nada.»', async () => {
    for (const [resultado, titulo] of [
      ['abandonado', 'Saliste de Webpay sin pagar'],
      ['tiempo_agotado', 'Se acabó el tiempo para pagar en Webpay'],
    ] as const) {
      rutas({ 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno({ resultado }) } })
      volverDeWebpay('?TBK_TOKEN=abc')
      abrir()
      await h1(titulo)
      expect(screen.getByText('No se cobró nada.')).toBeVisible()
      expect(screen.getByRole('button', { name: 'Intentar de nuevo' })).toBeVisible()
      cleanup()
      olvidarTodoElPago()
    }
  })

  it('7.9: el pago tardío anulado, con el monto y la tarjeta, el sello sin «boleta», baldosa atenta y sin macizo', async () => {
    const anulacion = devolucion({ motivo: 'pago_tardio', producto: null, monto: 57460 })
    rutas({
      'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno({ resultado: 'anulado', anulacion: 'hecha' }) },
      'GET /pago$': { status: 200, cuerpo: pago({ estado: 'no_aprobado', comprobante: null, devoluciones: [anulacion] }) },
    })
    volverDeWebpay()
    abrir()
    await h1('Anulamos tu pago')
    expect(screen.getByText(/El pedido cambió o se canceló/)).toHaveTextContent(
      'El pedido cambió o se canceló mientras pagabas. Anulamos tu pago de $57.460 completo, a tu tarjeta terminada en 4051. Cuándo lo ves en tu cuenta depende de tu banco.',
    )
    expect(screen.getByText('Pago de prueba. No se cobró dinero real.')).toBeVisible()
    expect(document.body.textContent).not.toMatch(/boleta/i)
    const baldosa = screen.getByRole('heading', { level: 1 }).previousElementSibling!
    expect(baldosa.className).toMatch(/\bbg-atenta-fondo\b/)
    expect(baldosa.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-undo-2/)
    expect(macizos()).toEqual([])
    expect(screen.getByRole('button', { name: 'Ir a tu pedido' }).className).toMatch(/ring-turquesa/)
  })

  it('7.9: la anulación en curso, «Estamos anulando tu pago»', async () => {
    const anulacion = devolucion({ motivo: 'pago_tardio', producto: null, monto: 57460, estado: 'en_curso', hecha_en: null })
    rutas({
      'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno({ resultado: 'anulado', anulacion: 'en_curso' }) },
      'GET /pago$': { status: 200, cuerpo: pago({ estado: 'pendiente', comprobante: null, devoluciones: [anulacion] }) },
    })
    volverDeWebpay()
    abrir()
    await h1('Estamos anulando tu pago')
    expect(screen.getByText(/El pedido cambió o se canceló/)).toHaveTextContent(
      'El pedido cambió o se canceló mientras pagabas. Estamos devolviendo $57.460 a tu tarjeta terminada en 4051. Si no se completa hoy, te escribimos. MATU nunca te pide los datos de tu banco por mensaje.',
    )
  })
})

describe('La persona y la sesión (7.1 y 7.10)', () => {
  it('7.1: si el pedido es de otra persona u otro grupo, los fija en memoria', async () => {
    rutas({ 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno({ grupo_id: OTRO_GRUPO_ID, persona_cuidada_id: OTRA_PERSONA_ID }) } })
    volverDeWebpay()
    abrir()
    await waitFor(() => expect(contexto.elegir).toHaveBeenCalledWith(OTRO_GRUPO_ID, OTRA_PERSONA_ID))
    // La vuelta queda con su resultado: la pantalla nueva no repite el retorno.
    expect(leerVuelta()?.resultado?.resultado).toBe('aprobado')
  })

  it('2.2: si después se elige otra persona en el encabezado, va a «Tu pedido» y olvida la vuelta, sin volver a fijar', async () => {
    rutas({ 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno({ grupo_id: OTRO_GRUPO_ID, persona_cuidada_id: OTRA_PERSONA_ID }) } })
    volverDeWebpay()
    abrir()
    await waitFor(() => expect(contexto.elegir).toHaveBeenCalledTimes(1))
    cleanup()
    // La pantalla se monta de nuevo con una persona que no es la del pedido (la eligió quien mira).
    abrir()
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
    expect(contexto.elegir).not.toHaveBeenCalled()
    expect(hayVuelta()).toBe(false)
  })

  it('7.10: con la sesión de otra cuenta (ids en null), el resultado sin montos y «Entrar», único macizo', async () => {
    rutas({ 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno({ grupo_id: null, persona_cuidada_id: null, pedido_id: null }) } })
    volverDeWebpay()
    abrir()
    await h1('Pagaste tu pedido')
    expect(screen.getByText('Para ver el comprobante y tu pedido, entra a MATU.')).toBeVisible()
    expect(document.body.textContent).not.toMatch(/\$/)
    const entrar = screen.getByRole('button', { name: 'Entrar' })
    expect(macizos()).toEqual([entrar])
    await userEvent.click(entrar)
    expect(contexto.fijar).toHaveBeenCalledWith({ destino: '/insumos/pedido' })
    expect(contexto.salir).toHaveBeenCalled()
    await waitFor(() => expect(window.location.pathname).toBe('/entrar'))
  })

  it('7.10: sin sesión, en el marco simple: «Estamos confirmando…», el resultado y «Entrar»', async () => {
    rutas({ 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno({ resultado: 'no_aprobado', grupo_id: null, persona_cuidada_id: null, pedido_id: null }) } })
    volverDeWebpay()
    contexto = familiaFalsa({ fase: 'fuera', fijar: vi.fn(), salir: vi.fn() } as never)
    conRegionesGlobales(<VueltaSinSesion />)
    expect(await h1('El pago no se hizo')).toBeVisible()
    expect(screen.getByText('Transbank no lo aprobó y no se cobró nada. Puedes intentarlo con otra tarjeta mientras el total siga vigente.')).toBeVisible()
    expect(screen.queryByRole('navigation')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(contexto.salir).not.toHaveBeenCalled()
    expect(window.location.pathname).toBe('/entrar')
    expect(hayVuelta()).toBe(false)
  })

  it('7.10: sin sesión y pendiente, la nota de que tarda (no pagar de nuevo)', async () => {
    rutas({ 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno({ resultado: 'pendiente', volver_a_preguntar_en: 15, grupo_id: null, persona_cuidada_id: null, pedido_id: null }) } })
    volverDeWebpay()
    contexto = familiaFalsa({ fase: 'fuera', fijar: vi.fn(), salir: vi.fn() } as never)
    conRegionesGlobales(<VueltaSinSesion />)
    expect(await screen.findByText(/Si pagaste, no pagues de nuevo/)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeVisible()
  })
})

describe('Sin vuelta: «Ver el comprobante» y la recarga (2.1)', () => {
  it('con el pago en memoria, lo muestra sin pedir nada', async () => {
    const api = rutas({})
    window.history.replaceState(null, '', '/insumos/pedido/pago')
    fijarComprobante(PERSONA_ID, pago())
    abrir()
    expect(await h1('Pagaste tu pedido')).toBeVisible()
    expect(api.pedidas.filter((p) => p.ruta.includes('pag'))).toEqual([])
    expect(screen.queryByText('Este pago ya está registrado. No se cobró dos veces.')).toBeNull()
  })

  it('al recargar, lee el último pedido pagado de la persona', async () => {
    const api = rutas({ 'GET /pedido-pagado$': { status: 200, cuerpo: pago() } })
    window.history.replaceState(null, '', '/insumos/pedido/pago')
    abrir()
    expect(await h1('Pagaste tu pedido')).toBeVisible()
    expect(api.pedidas.map((p) => p.ruta)).toContain(`/v1/personas-cuidadas/${PERSONA_ID}/pedido-pagado`)
  })

  it('al recargar sin pedido pagado (404), va a «Tu pedido»', async () => {
    rutas({ 'GET /pedido-pagado$': NO_ENCONTRADO })
    window.history.replaceState(null, '', '/insumos/pedido/pago')
    abrir()
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
  })

  it('C18: nada del pago en localStorage, sessionStorage, la URL ni history.state', async () => {
    rutas({ 'POST ^/v1/pagos/retorno$': { status: 200, cuerpo: retorno() }, 'GET /pago$': { status: 200, cuerpo: pago() } })
    volverDeWebpay()
    abrir()
    await h1('Pagaste tu pedido')
    expect(escrituras).toEqual([])
    expect(window.location.href).not.toMatch(/token|tbk|4821/i)
    expect(window.history.state).toBeNull()
  })
})

// MATU-55 (especificación docs/diseno/matu-55-donde-entraste.md v1.1, sección 3): «Tu cuenta» con la
// entrada a «Dónde entraste», las casillas de avisos y «Este teléfono» con Web Push, sobre un
// navegador simulado (permiso, service worker y suscripción). Solo datos sintéticos.
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AvisosCuenta } from '../src/familia/AvisosCuenta'
import { TuCuenta } from '../src/familia/Cuenta'
import { bytesDeClave } from '../src/familia/push'
import { salir } from '../src/compartido/api/sesion'
import { ACTUAL, apiCuenta, CLAVE, PC, problema, PUSH_LIBRE, type Respuesta } from './dondeEntrasteFalso'
import { familiaFalsa } from './familiaFalsa'
import { responderPolitica } from './politicaFalsa'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa(),
}))

const u = () => userEvent.setup({ delay: null })

// ---------------------------------------------------------------- el navegador simulado

const ANDROID = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36'
const IPHONE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'
const UA_ORIGINAL = navigator.userAgent

interface Opciones {
  soporte?: boolean
  pushManager?: boolean
  permiso?: NotificationPermission
  /** Lo que elige la persona en el aviso del navegador. */
  eleccion?: NotificationPermission
  /** La suscripción que ya tiene el navegador, con su clave. */
  suscritoCon?: string | null
  ua?: string
  instalada?: boolean
}

function navegador({ soporte = true, pushManager = soporte, permiso = 'default', eleccion = 'granted', suscritoCon = null, ua = ANDROID, instalada = false }: Opciones = {}) {
  const pasos: string[] = []
  let sub: PushSubscription | null = null
  const suscripcion = (clave: Uint8Array) => {
    const s = {
      endpoint: 'https://push.example.org/envio/sintetico-123',
      options: { applicationServerKey: clave.buffer, userVisibleOnly: true },
      unsubscribe: vi.fn(async () => {
        pasos.push('unsubscribe')
        sub = null
        return true
      }),
    } as unknown as PushSubscription
    return s
  }
  if (suscritoCon) sub = suscripcion(bytesDeClave(suscritoCon))
  const pushManagerFalso = {
    getSubscription: vi.fn(async () => sub),
    subscribe: vi.fn(async (o: PushSubscriptionOptionsInit) => {
      pasos.push('subscribe')
      sub = suscripcion(new Uint8Array(o.applicationServerKey as ArrayBuffer))
      return sub
    }),
  }
  const registro = { pushManager: pushManagerFalso }
  const sw = {
    register: vi.fn(async (url: string) => {
      pasos.push(`register ${url}`)
      return registro
    }),
    ready: Promise.resolve(registro),
    getRegistration: vi.fn(async () => registro),
  }
  const notificacion = {
    permission: permiso,
    requestPermission: vi.fn(async () => {
      pasos.push('requestPermission')
      notificacion.permission = eleccion
      return eleccion
    }),
  }
  Object.defineProperty(navigator, 'userAgent', { value: ua, configurable: true })
  Object.defineProperty(navigator, 'standalone', { value: instalada, configurable: true })
  if (soporte) {
    Object.defineProperty(navigator, 'serviceWorker', { value: sw, configurable: true })
    vi.stubGlobal('Notification', notificacion)
    Object.defineProperty(window, 'Notification', { value: notificacion, configurable: true, writable: true })
  }
  if (pushManager) Object.defineProperty(window, 'PushManager', { value: function PushManager() {}, configurable: true, writable: true })
  return { pasos, sw, pushManager: pushManagerFalso, notificacion, suscripcion: () => sub }
}

function sinNavegadorSimulado() {
  for (const [o, k] of [
    [navigator, 'serviceWorker'],
    [navigator, 'standalone'],
    [window, 'PushManager'],
    [window, 'Notification'],
  ] as const)
    if (Object.getOwnPropertyDescriptor(o, k)) delete (o as unknown as Record<string, unknown>)[k]
  Object.defineProperty(navigator, 'userAgent', { value: UA_ORIGINAL, configurable: true })
  vi.unstubAllGlobals()
}

beforeEach(() => sinNavegadorSimulado())
afterEach(() => sinNavegadorSimulado())

/** Una respuesta que la prueba suelta cuando quiere: para ver «Guardando…» y «Activando…». */
function enEspera() {
  let soltar!: (r: Respuesta) => void
  const promesa = new Promise<Respuesta>((r) => (soltar = r))
  return { manejador: () => promesa, soltar }
}

const bloque = () => screen.getByRole('heading', { level: 3 }).parentElement as HTMLElement

// ---------------------------------------------------------------- 3.3 las preferencias

describe('Avisos: las casillas (3.3)', () => {
  it('el fieldset con su leyenda h2, la ayuda y «Vale para todos tus grupos.» en negrita en su descripción', async () => {
    navegador()
    apiCuenta()
    render(<AvisosCuenta />)
    const grupo = await screen.findByRole('group', { name: 'Avisos cuando un insumo se está acabando' })
    expect(within(grupo).getByRole('heading', { level: 2, name: 'Avisos cuando un insumo se está acabando' })).toBeInTheDocument()
    expect(grupo).toHaveAccessibleDescription('Te avisamos cuando un insumo se esté acabando. El aviso no dice cuál ni de quién. Vale para todos tus grupos.')
    expect(screen.getByText('Vale para todos tus grupos.')).toHaveClass('font-bold')
    expect(await screen.findByRole('checkbox', { name: 'Por correo' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'En tus teléfonos' })).toBeChecked()
    expect(screen.queryByText('En este teléfono')).toBeNull()
  })

  it('cada casilla se guarda al marcarla, sin interfaz optimista: «Guardando…» hasta el 200, y después «Guardamos tus avisos.»', async () => {
    navegador()
    const espera = enEspera()
    const api = apiCuenta({ 'PUT ^/v1/yo/avisos$': espera.manejador })
    render(<AvisosCuenta />)
    const correo = await screen.findByRole('checkbox', { name: 'Por correo' })
    await u().click(correo)

    expect(await screen.findByText('Guardando…')).toBeInTheDocument()
    expect(correo).toHaveAttribute('aria-busy', 'true')
    // 1.2: `aria-disabled`, no `disabled`: el foco se queda en la casilla mientras guarda.
    expect(correo).not.toBeDisabled()
    expect(correo).toHaveAttribute('aria-disabled', 'true')
    // v1.3 (3.3): con el foco del teclado no se apaga, para que su anillo conserve 3:1.
    expect(correo).toHaveClass('aria-disabled:not-focus-visible:opacity-60')
    expect(correo).not.toHaveClass('aria-disabled:opacity-60')
    const telefonos = screen.getByRole('checkbox', { name: 'En tus teléfonos' })
    expect(telefonos).toHaveAttribute('aria-disabled', 'true')
    expect(correo).toHaveFocus()
    // Mientras guarda, otro toque no pide nada y la casilla no cambia.
    await u().click(telefonos)
    expect(api.de('PUT', '/v1/yo/avisos')).toHaveLength(1)
    expect(telefonos).toBeChecked()
    expect(api.de('PUT', '/v1/yo/avisos')[0].cuerpo).toEqual({ correo: false, push: true })

    espera.soltar({ status: 200, cuerpo: { correo: false, push: true } })
    expect(await screen.findByText('Guardamos tus avisos.')).toBeInTheDocument()
    expect(screen.queryByText('Guardando…')).toBeNull()
    expect(correo).not.toBeChecked()
    expect(correo).not.toHaveAttribute('aria-disabled')
    // Criterio 16: el foco vuelve a la casilla. El efecto pasivo puede correr después del texto, así que se espera;
    // que llegue sin temporizadores lo prueba el bloque «El foco después del render».
    await vi.waitFor(() => expect(correo).toHaveFocus())
    expect(document.activeElement).not.toBe(document.body)
  })

  it('error o sin red: la casilla vuelve a lo de antes, el error y el foco en ella', async () => {
    navegador()
    apiCuenta({ 'PUT ^/v1/yo/avisos$': problema(500) })
    render(<AvisosCuenta />)
    const correo = await screen.findByRole('checkbox', { name: 'Por correo' })
    await u().click(correo)
    const error = await screen.findByText('No pudimos guardar. Revisa tu conexión y vuelve a intentarlo.')
    expect(error.closest('[data-aviso]')).toHaveAttribute('data-aviso', 'alert')
    expect(correo).toBeChecked()
    await vi.waitFor(() => expect(correo).toHaveFocus())
    expect(document.activeElement).not.toBe(document.body)
  })

  it('E4: al desmarcar «En tus teléfonos», el bloque del teléfono se oculta y la inscripción no se borra', async () => {
    navegador({ permiso: 'granted', suscritoCon: CLAVE })
    const api = apiCuenta({ 'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { ...PUSH_LIBRE, registrado: true } } })
    render(<AvisosCuenta />)
    expect(await screen.findByText('Activados')).toBeVisible()
    await u().click(screen.getByRole('checkbox', { name: 'En tus teléfonos' }))
    await screen.findByText('Guardamos tus avisos.')
    expect(screen.getByText('Activados').closest('[hidden]')).not.toBeNull()
    expect(api.pedidas.filter((p) => p.ruta === '/v1/dispositivos/actual/push' && p.metodo !== 'GET')).toHaveLength(0)

    await u().click(screen.getByRole('checkbox', { name: 'En tus teléfonos' }))
    await vi.waitFor(() => expect(screen.getByText('Activados').closest('[hidden]')).toBeNull())
    expect(screen.getByRole('button', { name: 'Desactivar en este teléfono' })).toBeInTheDocument()
  })

  it('error al cargar: la nota y «Volver a intentar», sin casillas inventadas', async () => {
    navegador()
    apiCuenta({ 'GET ^/v1/yo/avisos$': [problema(500), { status: 200, cuerpo: { correo: false, push: false } }] })
    render(<AvisosCuenta />)
    expect(await screen.findByText('No pudimos traer tus avisos. Revisa tu conexión e inténtalo de nuevo.')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).toBeNull()
    await u().click(screen.getByRole('button', { name: 'Volver a intentar' }))
    expect(await screen.findByRole('checkbox', { name: 'Por correo' })).not.toBeChecked()
  })

  it('la nota del piloto, una vez, en `atenta` con Info; también si falla la lectura del push; no con envío real', async () => {
    navegador()
    apiCuenta({ 'GET ^/v1/dispositivos/actual/push$': problema(500) })
    const { unmount } = render(<AvisosCuenta />)
    const piloto = await screen.findAllByText('En el piloto los avisos se prueban sin enviarse: no te llegará nada.')
    expect(piloto).toHaveLength(1)
    const nota = piloto[0].closest('.bg-atenta-fondo')!
    expect(nota.querySelector('svg.lucide-info')).not.toBeNull()
    unmount()

    apiCuenta({ 'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { ...PUSH_LIBRE, envio_simulado: false } } })
    render(<AvisosCuenta />)
    await screen.findByText('Sin activar')
    expect(screen.queryByText(/En el piloto los avisos/)).toBeNull()
  })
})

// ---------------------------------------------------------------- 3.4 los estados de este teléfono

describe('Este teléfono: los estados (3.4)', () => {
  it('B: «Sin activar», la ayuda y «Activar en este teléfono»; el permiso no se pide al cargar', async () => {
    const n = navegador()
    apiCuenta()
    render(<AvisosCuenta />)
    expect(await screen.findByRole('heading', { level: 3, name: 'Este teléfono' })).toBeInTheDocument()
    const etiqueta = await screen.findByText('Sin activar')
    expect(etiqueta.querySelector('svg.lucide-circle')).not.toBeNull()
    expect(screen.getByText('Al activarlos, tu navegador anota una dirección de avisos en el servicio de su fabricante, y MATU la guarda hasta que los desactives o salgas. En el piloto, MATU no le envía nada a ese servicio.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Activar en este teléfono' })).toBeInTheDocument()
    expect(n.notificacion.requestPermission).not.toHaveBeenCalled()
    expect(n.sw.register).not.toHaveBeenCalled()
  })

  it('A: registrado y con la suscripción de la misma clave, «Activados» con Check y «Desactivar en este teléfono»', async () => {
    navegador({ permiso: 'granted', suscritoCon: CLAVE })
    apiCuenta({ 'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { ...PUSH_LIBRE, registrado: true } } })
    render(<AvisosCuenta />)
    const etiqueta = await screen.findByText('Activados')
    expect(etiqueta.querySelector('svg.lucide-check')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Desactivar en este teléfono' })).toBeInTheDocument()
  })

  it('registrado sin suscripción en el navegador, o con otra clave: B', async () => {
    navegador({ permiso: 'granted', suscritoCon: `B${'B'.repeat(86)}` })
    apiCuenta({ 'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { ...PUSH_LIBRE, registrado: true } } })
    render(<AvisosCuenta />)
    expect(await screen.findByRole('button', { name: 'Activar en este teléfono' })).toBeInTheDocument()
  })

  it('C: el navegador no deja; «Sin activar» y la nota, sin botón', async () => {
    navegador({ permiso: 'denied' })
    apiCuenta()
    render(<AvisosCuenta />)
    expect(await screen.findByText('Tu navegador no deja que MATU te avise. Puedes cambiarlo en los ajustes del navegador.')).toBeInTheDocument()
    expect(screen.getByText('Sin activar')).toBeInTheDocument()
    expect(within(bloque()).queryByRole('button')).toBeNull()
  })

  it('D: sin soporte, «Este navegador no puede recibir avisos. Puedes recibirlos por correo.», sin etiqueta ni botón', async () => {
    navegador({ soporte: false })
    apiCuenta()
    render(<AvisosCuenta />)
    expect(await screen.findByText('Este navegador no puede recibir avisos. Puedes recibirlos por correo.')).toBeInTheDocument()
    expect(screen.queryByText('Sin activar')).toBeNull()
    expect(within(bloque()).queryByRole('button')).toBeNull()
  })

  it('F: clave_publica null con soporte, el texto sin «clave» y sin «Activar»', async () => {
    navegador()
    apiCuenta({ 'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { ...PUSH_LIBRE, clave_publica: null } } })
    render(<AvisosCuenta />)
    expect(await screen.findByText('Por ahora no se pueden activar los avisos en este teléfono. Puedes recibirlos por correo.')).toBeInTheDocument()
    expect(bloque().textContent).not.toMatch(/clave/i)
    expect(within(bloque()).queryByRole('button')).toBeNull()
    expect(screen.queryByText('Sin activar')).toBeNull()
  })

  it('F en un computador: «en este computador»; sin soporte, manda D', async () => {
    navegador()
    apiCuenta({
      'GET ^/v1/dispositivos$': { status: 200, cuerpo: { items: [{ ...PC, actual: true }] } },
      'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { ...PUSH_LIBRE, clave_publica: null } },
    })
    const { unmount } = render(<AvisosCuenta />)
    expect(await screen.findByText('Por ahora no se pueden activar los avisos en este computador. Puedes recibirlos por correo.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: 'Este computador' })).toBeInTheDocument()
    unmount()

    sinNavegadorSimulado()
    navegador({ soporte: false })
    apiCuenta({ 'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { ...PUSH_LIBRE, clave_publica: null } } })
    render(<AvisosCuenta />)
    expect(await screen.findByText(/Este navegador no puede recibir avisos/)).toBeInTheDocument()
  })

  it('E: iPhone sin agregar a la pantalla de inicio, los tres pasos con el ícono Compartir y sin «Activar»; manda sobre F', async () => {
    navegador({ ua: IPHONE, soporte: false })
    apiCuenta({ 'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { ...PUSH_LIBRE, clave_publica: null } } })
    render(<AvisosCuenta />)
    expect(await screen.findByText('En iPhone, primero agrega MATU a tu pantalla de inicio.')).toBeInTheDocument()
    const pasos = within(bloque()).getAllByRole('listitem')
    expect(pasos.map((p) => p.textContent)).toEqual(['Toca Compartir  en Safari.', 'Elige «Agregar a inicio».', 'Abre MATU desde su ícono y vuelve a Tu cuenta.'])
    expect(within(pasos[0]).getByRole('img', { name: 'Compartir' })).toHaveClass('size-5')
    // P1 de la revisión 1.2: a 320 px con el 200 % el ícono de la nota va en la línea del título
    // (`iconoEnLinea`), para que el título use todo el ancho. jsdom no mide: se afirma la estructura.
    const titulo = screen.getByText('En iPhone, primero agrega MATU a tu pantalla de inicio.')
    expect(titulo.querySelector('span[class*="angosto:inline-flex"] svg')).not.toBeNull()
    expect(titulo.closest('.bg-rocio')!.querySelector(':scope > span[class*="angosto:hidden"]')).not.toBeNull()
    expect(within(bloque()).queryByRole('button')).toBeNull()
  })

  it('iPhone ya instalado sin PushManager (iOS anterior a 16.4): D', async () => {
    navegador({ ua: IPHONE, instalada: true, soporte: false })
    apiCuenta()
    render(<AvisosCuenta />)
    expect(await screen.findByText(/Este navegador no puede recibir avisos/)).toBeInTheDocument()
    expect(screen.queryByText(/En iPhone, primero/)).toBeNull()
  })

  it('error al leer el push: la nota y «Volver a intentar»; las casillas siguen funcionando', async () => {
    navegador()
    apiCuenta({ 'GET ^/v1/dispositivos/actual/push$': [problema(500), { status: 200, cuerpo: PUSH_LIBRE }] })
    render(<AvisosCuenta />)
    expect(await screen.findByText('No pudimos ver los avisos de este teléfono. Revisa tu conexión e inténtalo de nuevo.')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Por correo' })).toBeEnabled()
    await u().click(within(bloque()).getByRole('button', { name: 'Volver a intentar' }))
    expect(await screen.findByRole('button', { name: 'Activar en este teléfono' })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------- 3.4 activar y desactivar

describe('Este teléfono: activar y desactivar (3.4, D6-a)', () => {
  it('activar: el permiso al tocar, /sw.js, la suscripción con la clave pública, el PUT del endpoint y el estado A', async () => {
    const n = navegador()
    const espera = enEspera()
    const api = apiCuenta({ 'PUT ^/v1/dispositivos/actual/push$': espera.manejador })
    render(<AvisosCuenta />)
    const activar = await screen.findByRole('button', { name: 'Activar en este teléfono' })
    await u().click(activar)

    await vi.waitFor(() => expect(api.de('PUT', '/v1/dispositivos/actual/push')).toHaveLength(1))
    expect(activar).toHaveAttribute('aria-busy', 'true')
    expect(activar).toHaveTextContent('Activando…')
    espera.soltar({ status: 204 })

    expect(await screen.findByText('Activaste los avisos en este teléfono.')).toBeInTheDocument()
    expect(screen.getByText('Activados')).toBeInTheDocument()
    // Criterio 16 (sin temporizadores: lo prueba el bloque «El foco después del render»).
    await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Desactivar en este teléfono' })).toHaveFocus())
    expect(n.pasos).toEqual(['requestPermission', 'register /sw.js', 'subscribe'])
    const opciones = n.pushManager.subscribe.mock.calls[0][0]
    expect(opciones.userVisibleOnly).toBe(true)
    expect(Array.from(new Uint8Array(opciones.applicationServerKey as ArrayBuffer))).toEqual(Array.from(bytesDeClave(CLAVE)))
    expect(new Uint8Array(opciones.applicationServerKey as ArrayBuffer)).toHaveLength(65)
    expect(api.de('PUT', '/v1/dispositivos/actual/push')[0].cuerpo).toEqual({ push_token: 'https://push.example.org/envio/sintetico-123' })
  })

  it('con el permiso ya concedido no se vuelve a pedir', async () => {
    const n = navegador({ permiso: 'granted' })
    apiCuenta()
    render(<AvisosCuenta />)
    await u().click(await screen.findByRole('button', { name: 'Activar en este teléfono' }))
    await screen.findByText('Activados')
    expect(n.notificacion.requestPermission).not.toHaveBeenCalled()
  })

  it('cierra el aviso del navegador sin elegir: sigue en B, «No activamos los avisos…» y sin suscripción', async () => {
    const n = navegador({ eleccion: 'default' })
    const api = apiCuenta()
    render(<AvisosCuenta />)
    const activar = await screen.findByRole('button', { name: 'Activar en este teléfono' })
    await u().click(activar)
    expect(await screen.findByText('No activamos los avisos. Puedes volver a intentarlo.')).toBeInTheDocument()
    expect(screen.getByText('Sin activar')).toBeInTheDocument()
    await vi.waitFor(() => expect(activar).toHaveFocus())
    expect(n.pushManager.subscribe).not.toHaveBeenCalled()
    expect(api.de('PUT', '/v1/dispositivos/actual/push')).toHaveLength(0)
  })

  it('elige «Bloquear»: pasa a C y el foco va a su nota', async () => {
    navegador({ eleccion: 'denied' })
    apiCuenta()
    render(<AvisosCuenta />)
    await u().click(await screen.findByRole('button', { name: 'Activar en este teléfono' }))
    const nota = await screen.findByText('Tu navegador no deja que MATU te avise. Puedes cambiarlo en los ajustes del navegador.')
    await vi.waitFor(() => expect(nota.closest('[tabindex="-1"]')).toHaveFocus())
    expect(screen.queryByRole('button', { name: /Activar en este/ })).toBeNull()
  })

  it('falla el PUT: sigue en B, la suscripción del navegador se borra y el error', async () => {
    const n = navegador()
    apiCuenta({ 'PUT ^/v1/dispositivos/actual/push$': problema(500) })
    render(<AvisosCuenta />)
    const activar = await screen.findByRole('button', { name: 'Activar en este teléfono' })
    await u().click(activar)
    const error = await screen.findByText('No pudimos activar los avisos. Revisa tu conexión y vuelve a intentarlo.')
    expect(error.closest('[data-aviso]')).toHaveAttribute('data-aviso', 'alert')
    expect(n.pasos).toEqual(['requestPermission', 'register /sw.js', 'subscribe', 'unsubscribe'])
    expect(n.suscripcion()).toBeNull()
    expect(screen.getByText('Sin activar')).toBeInTheDocument()
    await vi.waitFor(() => expect(activar).toHaveFocus())
  })

  it('desactivar: primero el DELETE y después la suscripción; pasa a B y el foco a «Activar…»', async () => {
    const n = navegador({ permiso: 'granted', suscritoCon: CLAVE })
    const api = apiCuenta({ 'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { ...PUSH_LIBRE, registrado: true } } })
    render(<AvisosCuenta />)
    await u().click(await screen.findByRole('button', { name: 'Desactivar en este teléfono' }))
    expect(await screen.findByText('Desactivaste los avisos en este teléfono.')).toBeInTheDocument()
    expect(api.de('DELETE', '/v1/dispositivos/actual/push')).toHaveLength(1)
    expect(n.pasos).toEqual(['unsubscribe'])
    await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Activar en este teléfono' })).toHaveFocus())
  })

  it('falla el DELETE: sigue en A, el error, y la suscripción del navegador no se toca', async () => {
    const n = navegador({ permiso: 'granted', suscritoCon: CLAVE })
    apiCuenta({
      'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { ...PUSH_LIBRE, registrado: true } },
      'DELETE ^/v1/dispositivos/actual/push$': problema(503),
    })
    render(<AvisosCuenta />)
    const desactivar = await screen.findByRole('button', { name: 'Desactivar en este teléfono' })
    await u().click(desactivar)
    expect(await screen.findByText('No pudimos desactivar los avisos. Revisa tu conexión y vuelve a intentarlo.')).toBeInTheDocument()
    expect(screen.getByText('Activados')).toBeInTheDocument()
    expect(n.pasos).toEqual([])
    await vi.waitFor(() => expect(desactivar).toHaveFocus())
  })
})

// ---------------------------------------------------------------- 3.1, 3.2 y 3.5 «Tu cuenta»

describe('«Tu cuenta» con MATU-55', () => {
  it('los rótulos del dl en 17 px, «Dónde entraste» con su botón, los avisos, y sin «Cambiar mi contraseña» ni turquesa macizo', async () => {
    navegador()
    window.history.replaceState(null, '', '/cuenta')
    const guardar = vi.spyOn(Storage.prototype, 'setItem')
    apiCuenta()
    responderPolitica()
    const { container } = render(<TuCuenta />)
    await screen.findByText('carmen@example.org')
    for (const rotulo of ['Tu correo', 'Tu celular', 'Política de privacidad']) expect(screen.getByText(rotulo, { selector: 'dt' })).toHaveClass('text-base')

    const donde = screen.getByRole('region', { name: 'Dónde entraste' })
    expect(donde).toHaveTextContent('Los teléfonos y computadores donde entraste, y tus últimos ingresos.')
    await screen.findByText('Sin activar')
    expect(screen.getByRole('group', { name: 'Avisos cuando un insumo se está acabando' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Cambiar mi contraseña/ })).toBeNull()
    expect(container.innerHTML).not.toMatch(/text-(xs|sm)\b|text-\[/)
    expect(container.innerHTML).not.toMatch(/\bbg-turquesa\b/)

    await u().click(within(donde).getByRole('button', { name: 'Ver dónde entraste' }))
    expect(window.location.pathname).toBe('/cuenta/donde-entraste')
    expect(guardar).not.toHaveBeenCalled()
  })

  it('la entrada a «Dónde entraste» no pide nada a la API', async () => {
    navegador({ soporte: false })
    const api = apiCuenta()
    responderPolitica()
    render(<TuCuenta />)
    await screen.findByText(/Este navegador no puede recibir avisos/)
    expect(api.de('GET', '/v1/yo/ingresos')).toHaveLength(0)
    // La única lectura de dispositivos es la de la clase del actual (E1), para «Este teléfono».
    expect(api.de('GET', '/v1/dispositivos')).toHaveLength(1)
    expect(screen.getByRole('heading', { level: 3, name: `Este ${ACTUAL.clase === 'telefono' ? 'teléfono' : ''}` })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------- criterio 16: el foco, en el render

describe('El foco después del render, sin temporizadores (P1 de la revisión 1.2, criterio 16)', () => {
  // Mientras la respuesta llega, los `setTimeout` de 0 ms no corren: si el foco se moviera con un
  // temporizador (lo que en el navegador lo dejaba en el body), la prueba lo nota. El foco tiene que
  // llegar con el render, en un efecto.
  async function soltarSinTemporizadores(soltar: () => void) {
    const real = window.setTimeout
    const espia = vi.spyOn(window, 'setTimeout').mockImplementation(((fn: () => void, ms?: number) => (ms ? real(fn, ms) : 0)) as never)
    try {
      await act(async () => soltar())
    } finally {
      espia.mockRestore()
    }
  }
  it('activar: al terminar, el foco ya está en «Desactivar en este teléfono»', async () => {
    navegador({ permiso: 'granted' })
    const espera = enEspera()
    const api = apiCuenta({ 'PUT ^/v1/dispositivos/actual/push$': espera.manejador })
    render(<AvisosCuenta />)
    await u().click(await screen.findByRole('button', { name: 'Activar en este teléfono' }))
    await vi.waitFor(() => expect(api.de('PUT', '/v1/dispositivos/actual/push')).toHaveLength(1))
    await soltarSinTemporizadores(() => espera.soltar({ status: 204 }))
    expect(screen.getByRole('button', { name: 'Desactivar en este teléfono' })).toHaveFocus()
  })

  it('desactivar: al terminar, el foco ya está en «Activar en este teléfono»', async () => {
    navegador({ permiso: 'granted', suscritoCon: CLAVE })
    const espera = enEspera()
    const api = apiCuenta({
      'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { ...PUSH_LIBRE, registrado: true } },
      'DELETE ^/v1/dispositivos/actual/push$': espera.manejador,
    })
    render(<AvisosCuenta />)
    await u().click(await screen.findByRole('button', { name: 'Desactivar en este teléfono' }))
    await vi.waitFor(() => expect(api.de('DELETE', '/v1/dispositivos/actual/push')).toHaveLength(1))
    await soltarSinTemporizadores(() => espera.soltar({ status: 204 }))
    expect(screen.getByRole('button', { name: 'Activar en este teléfono' })).toHaveFocus()
  })

  it.each([
    ['bien', { status: 200, cuerpo: { correo: false, push: true } }],
    ['con error', problema(500)],
  ])('guardar una casilla %s: el foco sigue en la casilla, nunca en el body', async (_, respuesta) => {
    navegador()
    const espera = enEspera()
    apiCuenta({ 'PUT ^/v1/yo/avisos$': espera.manejador })
    render(<AvisosCuenta />)
    const correo = await screen.findByRole('checkbox', { name: 'Por correo' })
    await u().click(correo)
    await soltarSinTemporizadores(() => espera.soltar(respuesta))
    expect(correo).toHaveFocus()
    expect(document.activeElement).not.toBe(document.body)
  })
})

// ---------------------------------------------------------------- P3: un mensaje a la vez

describe('Avisos: los mensajes no se acumulan (P3 de la revisión 1.2)', () => {
  it('guardar una casilla borra «Activaste…», y desactivar borra «Guardamos tus avisos.»', async () => {
    navegador({ permiso: 'granted' })
    apiCuenta()
    render(<AvisosCuenta />)
    await u().click(await screen.findByRole('button', { name: 'Activar en este teléfono' }))
    expect(await screen.findByText('Activaste los avisos en este teléfono.')).toBeInTheDocument()

    await u().click(screen.getByRole('checkbox', { name: 'Por correo' }))
    expect(await screen.findByText('Guardamos tus avisos.')).toBeInTheDocument()
    expect(screen.queryByText('Activaste los avisos en este teléfono.')).toBeNull()

    await u().click(screen.getByRole('button', { name: 'Desactivar en este teléfono' }))
    expect(await screen.findByText('Desactivaste los avisos en este teléfono.')).toBeInTheDocument()
    expect(screen.queryByText('Guardamos tus avisos.')).toBeNull()
  })

  it('un error del teléfono también se borra al guardar una casilla', async () => {
    navegador({ permiso: 'granted' })
    apiCuenta({ 'PUT ^/v1/dispositivos/actual/push$': problema(500) })
    render(<AvisosCuenta />)
    await u().click(await screen.findByRole('button', { name: 'Activar en este teléfono' }))
    expect(await screen.findByText('No pudimos activar los avisos. Revisa tu conexión y vuelve a intentarlo.')).toBeInTheDocument()
    await u().click(screen.getByRole('checkbox', { name: 'Por correo' }))
    await screen.findByText('Guardamos tus avisos.')
    expect(screen.queryByText(/No pudimos activar los avisos/)).toBeNull()
  })
})

// ---------------------------------------------------------------- «Salir» borra la inscripción del navegador

describe('«Salir» borra la suscripción de avisos de este navegador (recomendación del analista)', () => {
  it('después del cierre en el servidor: getSubscription y unsubscribe', async () => {
    const n = navegador({ permiso: 'granted', suscritoCon: CLAVE })
    apiCuenta({
      'POST ^/v1/sesiones/cerrar$': () => {
        n.pasos.push('POST /v1/sesiones/cerrar')
        return { status: 204 }
      },
    })
    await salir()
    expect(n.pasos).toEqual(['POST /v1/sesiones/cerrar', 'unsubscribe'])
    expect(n.suscripcion()).toBeNull()
  })

  it('si el cierre en el servidor falla, igual sale y borra la suscripción', async () => {
    const n = navegador({ permiso: 'granted', suscritoCon: CLAVE })
    apiCuenta({ 'POST ^/v1/sesiones/cerrar$': problema(503) })
    await expect(salir()).resolves.toBeUndefined()
    expect(n.pasos).toEqual(['unsubscribe'])
  })

  it('si borrar la suscripción falla, la salida no se bloquea', async () => {
    const n = navegador({ permiso: 'granted', suscritoCon: CLAVE })
    n.pushManager.getSubscription.mockRejectedValueOnce(new Error('sin acceso'))
    apiCuenta({ 'POST ^/v1/sesiones/cerrar$': { status: 204 } })
    await expect(salir()).resolves.toBeUndefined()
  })

  it('sin service worker o sin PushManager no hace nada', async () => {
    navegador({ soporte: false })
    const api = apiCuenta({ 'POST ^/v1/sesiones/cerrar$': { status: 204 } })
    await expect(salir()).resolves.toBeUndefined()
    expect(api.de('POST', '/v1/sesiones/cerrar')).toHaveLength(1)

    sinNavegadorSimulado()
    const n = navegador({ permiso: 'granted', suscritoCon: CLAVE, pushManager: false })
    apiCuenta({ 'POST ^/v1/sesiones/cerrar$': { status: 204 } })
    await salir()
    expect(n.sw.getRegistration).not.toHaveBeenCalled()
    expect(n.pasos).toEqual([])
  })
})

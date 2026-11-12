// MATU-42 y MATU-53: la página de la persona invitada, `/invitacion#<token>` (especificación
// docs/diseno/matu-53-invitar-grupo.md v1.1, secciones 2.1 y 4). La presentación, el código (corto,
// incorrecto con n y con 1 intento, bloqueo), el fragmento que se limpia, sin cuenta, confirmar,
// unirse, «No quiero unirme», los estados que no siguen y que nada vaya al almacenamiento del
// navegador. Solo datos sintéticos.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import type { InvitacionEnMemoria } from '../src/familia/estado'
import { NotaVuelvesALaInvitacion, PaginaInvitacion } from '../src/familia/Invitacion'
import type { RespuestaFalsa } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'

const TOKEN = 'TokenSinteticoDeInvitacion0123456789abcdefghij'
const GRUPO_NUEVO = '3c9d4e20-0000-4000-8000-0000000000n1'
const PRESENTACION = { nombre_pila_invita: 'Carmen', rol: 'cuidador', expira_en: '2026-11-20T00:30:00Z' }
const VERIFICACION = { ...PRESENTACION, grupo: 'Familia Soto', personas: ['María'] }

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

let escrituras: string[] = []
beforeEach(() => {
  escrituras = []
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
})

interface Pedida {
  linea: string
  cuerpo?: Record<string, unknown>
  grupo: unknown
  autorizacion: unknown
}

/** La API de mentira, por ruta. Devuelve las peticiones con sus cabeceras de grupo y de entrada. */
function api(atender: (p: Pedida) => RespuestaFalsa | Promise<RespuestaFalsa>) {
  const pedidas: Pedida[] = []
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const p: Pedida = {
      linea: `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`,
      cuerpo: typeof config.data === 'string' && config.data ? JSON.parse(config.data) : undefined,
      grupo: config.headers?.get?.('X-Grupo-Id'),
      autorizacion: config.headers?.get?.('Authorization'),
    }
    pedidas.push(p)
    const r = await atender(p)
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return pedidas
}

const problema = (status: number, tipo: string, extra: Record<string, unknown> = {}): RespuestaFalsa => ({
  status,
  cuerpo: { type: `/errores/${tipo}`, title: 'TEXTO DE LA API QUE NO SE MUESTRA', status, ...extra },
})

/** La API de siempre: presentación y verificación bien; la aceptación, lo que diga cada prueba. */
function apiInvitacion({ verificar, aceptar }: { verificar?: (p: Pedida) => RespuestaFalsa; aceptar?: (p: Pedida) => RespuestaFalsa } = {}) {
  return api((p) => {
    if (p.linea === 'POST /v1/invitaciones/presentacion') return { status: 200, cuerpo: PRESENTACION }
    if (p.linea === 'POST /v1/invitaciones/verificacion') return verificar ? verificar(p) : p.cuerpo?.codigo === '4729' ? { status: 200, cuerpo: VERIFICACION } : problema(422, 'codigo-incorrecto', { intentos_restantes: 3 })
    if (p.linea === 'POST /v1/invitaciones/aceptacion')
      return aceptar ? aceptar(p) : { status: 201, cuerpo: { grupo_id: GRUPO_NUEVO, membresia_id: 'm1', grupo: 'Familia Soto', rol: 'cuidador', puede_ver_plan: false } }
    if (p.linea === 'GET /v1/cuenta') return { status: 200, cuerpo: { id: 'u1', nombre: 'Rodrigo Soto', email: 'no-se-muestra@example.com' } }
    return problema(404, 'no-encontrado')
  })
}

function abrir({ hash = TOKEN, fase = 'fuera', invitacion = null, ...cambios }: { hash?: string | null; fase?: string; invitacion?: InvitacionEnMemoria | null } & Record<string, unknown> = {}) {
  window.history.replaceState(null, '', hash === null ? '/invitacion' : `/invitacion#${hash}`)
  contexto = familiaFalsa({ fase, invitacion, capa3: false, elegir: vi.fn(async () => {}), ...cambios } as never)
  return render(
    <>
      <RegionesVivas />
      <PaginaInvitacion />
    </>,
  )
}

const h1 = () => screen.getByRole('heading', { level: 1 })
const campo = () => screen.getByRole('textbox', { name: 'Código' })

async function escribirCodigo(codigo: string) {
  const u = userEvent.setup()
  await u.clear(campo())
  if (codigo) await u.type(campo(), codigo)
  await u.click(screen.getByRole('button', { name: 'Seguir' }))
}

/** Lo que el contexto recibió como invitación en memoria, en orden. */
const memorias = () =>
  vi
    .mocked(contexto.fijar)
    .mock.calls.map(([c]) => c)
    .filter((c) => 'invitacion' in c)
    .map((c) => c.invitacion)

// ---------------------------------------------------------------- 4.2 y 4.3

describe('La presentación y el código', () => {
  it('abre con el token del fragmento: solo el nombre de pila de quien invita, el rol en infinitivo y el vencimiento', async () => {
    const pedidas = apiInvitacion()
    abrir()
    expect(await screen.findByRole('heading', { level: 1, name: 'Carmen te invita a su grupo de cuidado en MATU, para cuidar.' })).toBeVisible()
    await waitFor(() => expect(h1()).toHaveFocus())
    expect(screen.getByText('Escribe el código que te dijo.')).toBeVisible()
    expect(campo()).toHaveAttribute('inputmode', 'numeric')
    expect(campo()).toHaveAttribute('autocomplete', 'one-time-code')
    expect(campo()).toHaveAttribute('maxlength', '4')
    expect(screen.getByText(/^Vale hasta el/)).toHaveTextContent('Vale hasta el 19/11/2026 a las 21:30.')
    // C1: ni el grupo ni la persona cuidada antes del código.
    expect(document.body.textContent).not.toMatch(/Familia Soto|María/)
    expect(screen.getByText('Invitación a un grupo de cuidado')).toBeVisible()
    expect(document.title).toBe('Invitación a un grupo de cuidado · MATU')
    // El token va solo en el cuerpo; sin X-Grupo-Id ni la entrada (pública).
    expect(pedidas).toEqual([{ linea: 'POST /v1/invitaciones/presentacion', cuerpo: { token: TOKEN }, grupo: undefined, autorizacion: undefined }])
    // Mientras se escribe el código, el fragmento queda: recargar vuelve a abrirla (2.1).
    expect(window.location.hash).toBe(`#${TOKEN}`)
    expect(memorias()[0]).toEqual({ token: TOKEN, presentacion: null, codigo: null, verificacion: null })
  })

  it('con menos de 4 números no pide nada: el mensaje bajo el campo y el foco en el campo', async () => {
    const pedidas = apiInvitacion()
    abrir()
    await screen.findByRole('textbox', { name: 'Código' })
    await escribirCodigo('47')
    await waitFor(() => expect(campo()).toHaveFocus())
    expect(campo()).toHaveAccessibleDescription('El código tiene 4 números. Revisa que estén todos.')
    expect(campo()).toBeInvalid()
    expect(pedidas.filter((p) => p.linea.endsWith('verificacion'))).toEqual([])
  })

  it('admite pegar «47 29» y «47-29»', async () => {
    apiInvitacion()
    abrir()
    await screen.findByRole('textbox', { name: 'Código' })
    campo().focus()
    await userEvent.paste('47-29')
    expect(campo()).toHaveValue('4729')
  })

  it.each([
    [3, 'Ese código no es. Te quedan 3 intentos. Después, la invitación se bloquea.'],
    [1, 'Ese código no es. Te queda 1 intento. Después, la invitación se bloquea.'],
  ])('un código malo con %i intentos: el mensaje, el campo vacío y el foco en el campo', async (n, texto) => {
    apiInvitacion({ verificar: () => problema(422, 'codigo-incorrecto', { intentos_restantes: n }) })
    abrir()
    await screen.findByRole('textbox', { name: 'Código' })
    await escribirCodigo('1111')
    expect(await screen.findByText('Ese código no es.')).toBeVisible()
    await waitFor(() => expect(campo()).toHaveFocus())
    expect(campo()).toHaveAccessibleDescription(texto)
    expect(campo()).toHaveValue('')
    expect(screen.getByText('Ese código no es.').tagName).toBe('B')
    expect(window.location.hash).toBe(`#${TOKEN}`)
  })

  it('el quinto código malo (423) bloquea: «Pídele a Carmen una nueva.», el fragmento se limpia y la invitación sale de la memoria', async () => {
    apiInvitacion({ verificar: () => problema(423, 'invitacion-bloqueada', { nombre_pila_invita: 'Carmen' }) })
    abrir()
    await screen.findByRole('textbox', { name: 'Código' })
    await escribirCodigo('1111')
    expect(await screen.findByRole('heading', { level: 1, name: 'Esta invitación se bloqueó' })).toBeVisible()
    await waitFor(() => expect(h1()).toHaveFocus())
    expect(screen.getByText('El código se escribió mal cinco veces. Por seguridad, ya no sirve.')).toBeVisible()
    expect(screen.getByText('¿Qué hago?')).toBeVisible()
    expect(screen.getByText('Pídele a Carmen una nueva.')).toBeVisible()
    expect(window.location.hash).toBe('')
    expect(window.location.pathname).toBe('/invitacion')
    expect(memorias().at(-1)).toBeNull()
    expect(document.title).toBe('Esta invitación se bloqueó · MATU')
    expect(screen.queryByText(/TEXTO DE LA API/)).toBeNull()
  })

  it('el código bien: limpia el fragmento con replaceState y, sin sesión, pide crear la cuenta o entrar', async () => {
    const reemplazos = vi.spyOn(window.history, 'replaceState')
    const pedidas = apiInvitacion()
    abrir()
    await screen.findByRole('textbox', { name: 'Código' })
    await escribirCodigo('4729')
    expect(await screen.findByRole('heading', { level: 1, name: 'Para unirte, crea tu cuenta o entra con la que tienes.' })).toBeVisible()
    await waitFor(() => expect(h1()).toHaveFocus())
    expect(screen.getByText('Te trae de vuelta aquí para terminar de unirte.')).toBeVisible()
    expect(window.location.hash).toBe('')
    // `null` como estado: nada del token ni del código en `history.state`.
    expect(reemplazos).toHaveBeenCalledWith(null, '', '/invitacion')
    expect(window.history.state).toBeNull()
    expect(pedidas.at(-1)).toEqual({ linea: 'POST /v1/invitaciones/verificacion', cuerpo: { token: TOKEN, codigo: '4729' }, grupo: undefined, autorizacion: undefined })
    expect(memorias().at(-1)).toEqual({ token: TOKEN, presentacion: PRESENTACION, codigo: '4729', verificacion: VERIFICACION })

    await userEvent.click(screen.getByRole('button', { name: 'Entrar con mi cuenta' }))
    expect(contexto.fijar).toHaveBeenCalledWith({ destino: '/invitacion' })
    expect(window.location.pathname).toBe('/entrar')
    expect(escrituras).toEqual([])
  })

  it('«Crear mi cuenta» lleva al alta sin el fragmento en la dirección', async () => {
    apiInvitacion()
    abrir()
    await screen.findByRole('textbox', { name: 'Código' })
    await escribirCodigo('4729')
    await userEvent.click(await screen.findByRole('button', { name: 'Crear mi cuenta' }))
    expect(window.location.pathname).toBe('/crear-cuenta')
    expect(window.location.hash).toBe('')
  })
})

// ---------------------------------------------------------------- 4.5 y 4.6

const EN_MEMORIA: InvitacionEnMemoria = { token: TOKEN, presentacion: PRESENTACION as never, codigo: '4729', verificacion: VERIFICACION as never }

describe('Confirmar y unirse', () => {
  it('con sesión y la invitación en memoria (vuelve del alta): «Te unes a…», el rol, las notas y quién se une', async () => {
    const pedidas = apiInvitacion()
    abrir({ hash: null, fase: 'dentro', invitacion: EN_MEMORIA })
    expect(h1()).toHaveTextContent('Te unes a Familia Soto. Cuidan a María.')
    await waitFor(() => expect(h1()).toHaveFocus())
    expect(screen.getByText('Tu rol: Cuida.')).toBeVisible()
    expect(screen.getByText('Ve y cambia la ficha y los insumos, y comparte la ficha con quien te reemplaza.')).toBeVisible()
    expect(screen.getByText('Las personas del grupo verán tu nombre. No verán tu correo ni tu celular.')).toBeVisible()
    expect(screen.getByText('Lo que veas sobre María es para su cuidado. No lo compartas fuera del grupo.')).toBeVisible()
    expect(screen.getByRole('link', { name: /Política de privacidad/ })).toHaveAttribute('target', '_blank')
    expect(await screen.findByText('Te unes como Rodrigo Soto.')).toBeVisible()
    expect(document.body.textContent).not.toContain('no-se-muestra@example.com')
    expect(pedidas.map((p) => p.linea)).toEqual(['GET /v1/cuenta'])
  })

  it('«Unirme al grupo»: la aceptación sin X-Grupo-Id, sin interfaz optimista, y la app elige el grupo nuevo con el aviso', async () => {
    let soltar: () => void = () => {}
    const pedidas = apiInvitacion({
      aceptar: () => ({ status: 201, cuerpo: { grupo_id: GRUPO_NUEVO, membresia_id: 'm1', grupo: 'Familia Soto', rol: 'cuidador', puede_ver_plan: false } }),
    })
    const alEntrar = vi.fn(() => new Promise<void>((r) => (soltar = r)))
    abrir({ hash: null, fase: 'dentro', invitacion: EN_MEMORIA, alEntrar })
    await userEvent.click(screen.getByRole('button', { name: 'Unirme al grupo' }))
    // Mientras espera, el botón dice el gerundio y la app no cambia de grupo.
    expect(screen.getByRole('button', { name: /Unirme al grupo/ })).toHaveAttribute('aria-busy', 'true')
    expect(contexto.elegir).not.toHaveBeenCalled()
    soltar()
    await waitFor(() => expect(contexto.elegir).toHaveBeenCalledWith(GRUPO_NUEVO, null))
    expect(contexto.fijar).toHaveBeenCalledWith({ aviso: { titulo: 'Ya eres parte de Familia Soto.', tono: 'ok', enfocar: true } })
    expect(window.location.pathname).toBe('/')
    const aceptacion = pedidas.find((p) => p.linea === 'POST /v1/invitaciones/aceptacion')!
    expect(aceptacion.cuerpo).toEqual({ token: TOKEN, codigo: '4729' })
    expect(aceptacion.grupo).toBeUndefined()
    expect(memorias()).toContain(null)
  })

  it('«No quiero unirme» no llama al servidor y olvida la invitación', async () => {
    const pedidas = apiInvitacion()
    abrir({ hash: null, fase: 'dentro', invitacion: EN_MEMORIA })
    await userEvent.click(screen.getByRole('button', { name: 'No quiero unirme' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'No te uniste al grupo' })).toBeVisible()
    expect(screen.getByText(/^Si cambias de opinión/)).toHaveTextContent('Si cambias de opinión, vuelve a abrir el enlace antes del 19/11/2026.')
    expect(screen.getByRole('button', { name: 'Ir a MATU' })).toBeVisible()
    expect(pedidas.filter((p) => p.linea.includes('aceptacion'))).toEqual([])
    expect(memorias().at(-1)).toBeNull()
  })

  it('409 ya-eres-parte: «Ya eres parte de este grupo» y «Ir a MATU» elige ese grupo', async () => {
    apiInvitacion({ aceptar: () => problema(409, 'ya-eres-parte', { grupo_id: GRUPO_NUEVO }) })
    abrir({ hash: null, fase: 'dentro', invitacion: EN_MEMORIA })
    await userEvent.click(screen.getByRole('button', { name: 'Unirme al grupo' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Ya eres parte de este grupo' })).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Ir a MATU' }))
    await waitFor(() => expect(window.location.pathname).toBe('/'))
    expect(contexto.elegir).toHaveBeenCalledWith(GRUPO_NUEVO, null)
  })

  it('sin la persona cuidada registrada, y con varias personas', async () => {
    apiInvitacion()
    const { unmount } = abrir({ hash: null, fase: 'dentro', invitacion: { ...EN_MEMORIA, verificacion: { ...VERIFICACION, personas: [] } as never } })
    expect(h1()).toHaveTextContent('Te unes a Familia Soto. Todavía no registran a la persona que cuidan.')
    unmount()
    abrir({ hash: null, fase: 'dentro', invitacion: { ...EN_MEMORIA, verificacion: { ...VERIFICACION, rol: 'observador', personas: ['María', 'Pedro', 'Elena'] } as never } })
    expect(h1()).toHaveTextContent('Te unes a Familia Soto. Cuidan a María, Pedro y Elena.')
    expect(screen.getByText('Tu rol: Se informa.')).toBeVisible()
    expect(screen.getByText('Ve el nombre de María, Pedro y Elena y sus insumos. No ve la ficha.')).toBeVisible()
  })

  it('pregunta por la capa 3 para describir «Paga» como en /grupo/invitar (v1.2)', async () => {
    apiInvitacion()
    const conocerCapa3 = vi.fn()
    abrir({ hash: null, fase: 'dentro', invitacion: { ...EN_MEMORIA, verificacion: { ...VERIFICACION, rol: 'pagador' } as never }, capa3: null, conocerCapa3 })
    await waitFor(() => expect(conocerCapa3).toHaveBeenCalled())
  })

  it('el título parte por sílabas un nombre largo (hyphens-auto)', () => {
    apiInvitacion()
    abrir({ hash: null, fase: 'dentro', invitacion: EN_MEMORIA })
    expect(h1()).toHaveClass('hyphens-auto', 'break-words')
  })

  it('sin sesión y con la invitación en memoria, vuelve a pedir la cuenta', () => {
    apiInvitacion()
    abrir({ hash: null, fase: 'fuera', invitacion: EN_MEMORIA })
    expect(h1()).toHaveTextContent('Para unirte, crea tu cuenta o entra con la que tienes.')
  })
})

// ---------------------------------------------------------------- 4.7 y 4.8

describe('Los estados que no siguen', () => {
  it.each([
    ['invitacion-vencida', 410, 'Esta invitación venció', 'Las invitaciones duran 7 días, y esta ya terminó.'],
    ['invitacion-usada', 410, 'Esta invitación ya se usó', 'Cada invitación sirve una sola vez.'],
    ['invitacion-no-disponible', 410, 'Esta invitación no está disponible', 'Puede que se haya copiado incompleta o que ya no exista. Revisa que la abriste completa desde el mensaje.'],
  ] as const)('%s: título, texto, «¿Qué hago?» y el fragmento limpio', async (tipo, status, titulo, texto) => {
    api(() => problema(status, tipo))
    abrir()
    expect(await screen.findByRole('heading', { level: 1, name: titulo })).toBeVisible()
    await waitFor(() => expect(h1()).toHaveFocus())
    expect(screen.getByText(texto)).toBeVisible()
    expect(screen.getByText('Pídele una nueva a quien te invitó.')).toBeVisible()
    expect(window.location.hash).toBe('')
    expect(document.title).toBe(`${titulo} · MATU`)
  })

  it('423 en la presentación sin el nombre: «Pídele una nueva a quien te invitó.»', async () => {
    api(() => problema(423, 'invitacion-bloqueada'))
    abrir()
    expect(await screen.findByRole('heading', { level: 1, name: 'Esta invitación se bloqueó' })).toBeVisible()
    expect(screen.getByText('Pídele una nueva a quien te invitó.')).toBeVisible()
  })

  it('429: «Espera un momento» con los minutos, y el fragmento se queda', async () => {
    api(() => ({ ...problema(429, 'demasiadas-peticiones'), cabeceras: { 'retry-after': '120' } }))
    abrir()
    expect(await screen.findByRole('heading', { level: 1, name: 'Espera un momento' })).toBeVisible()
    // El número y «minutos» van con un espacio duro: al cortar la línea no se separan.
    expect(screen.getByText(/^Hubo muchos intentos/).textContent).toBe('Hubo muchos intentos desde esta conexión. Vuelve a intentarlo en 2 minutos.')
    expect(window.location.hash).toBe(`#${TOKEN}`)
  })

  it('sin red: «Volver a intentar» repite la presentación', async () => {
    let falla = true
    const pedidas = api((p) => (falla ? { status: 503, cuerpo: { type: '/errores/servicio-no-disponible', status: 503 } } : p.linea.endsWith('presentacion') ? { status: 200, cuerpo: PRESENTACION } : problema(404, 'no-encontrado')))
    abrir()
    expect(await screen.findByRole('heading', { level: 1, name: 'No pudimos completar esto.' })).toBeVisible()
    expect(screen.getByText('Revisa tu conexión y vuelve a intentarlo.')).toBeVisible()
    falla = false
    await userEvent.click(screen.getByRole('button', { name: 'Volver a intentar' }))
    expect(await screen.findByRole('heading', { level: 1, name: /Carmen te invita/ })).toBeVisible()
    expect(pedidas.map((p) => p.linea)).toEqual(['POST /v1/invitaciones/presentacion', 'POST /v1/invitaciones/presentacion'])
  })

  it('sin red al verificar: «Volver a intentar» repite la verificación con el código escrito', async () => {
    let falla = true
    const pedidas = apiInvitacion({ verificar: () => (falla ? { status: 500, cuerpo: { type: '/errores/error-interno', status: 500 } } : { status: 200, cuerpo: VERIFICACION }) })
    abrir()
    await screen.findByRole('textbox', { name: 'Código' })
    await escribirCodigo('4729')
    expect(await screen.findByRole('heading', { level: 1, name: 'No pudimos completar esto.' })).toBeVisible()
    falla = false
    await userEvent.click(screen.getByRole('button', { name: 'Volver a intentar' }))
    expect(await screen.findByRole('heading', { level: 1, name: /Para unirte/ })).toBeVisible()
    expect(pedidas.filter((p) => p.linea.endsWith('verificacion')).map((p) => p.cuerpo)).toEqual([
      { token: TOKEN, codigo: '4729' },
      { token: TOKEN, codigo: '4729' },
    ])
  })

  it('410 al unirse (venció mientras creaba la cuenta) lleva a la misma tabla', async () => {
    apiInvitacion({ aceptar: () => problema(410, 'invitacion-vencida') })
    abrir({ hash: null, fase: 'dentro', invitacion: EN_MEMORIA })
    await userEvent.click(screen.getByRole('button', { name: 'Unirme al grupo' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Esta invitación venció' })).toBeVisible()
  })

  it('sin fragmento ni nada en memoria: «Vuelve a abrir el enlace», sin botón y sin pedir nada', async () => {
    const pedidas = api(() => problema(404, 'no-encontrado'))
    abrir({ hash: null })
    expect(h1()).toHaveTextContent('Vuelve a abrir el enlace')
    expect(screen.getByText('Vuelve a abrir el enlace que te enviaron.')).toBeVisible()
    expect(screen.queryByRole('button')).toBeNull()
    expect(pedidas).toEqual([])
  })

  it('cada estado tiene su ícono y su título: nunca solo color', async () => {
    api(() => problema(410, 'invitacion-usada'))
    abrir()
    const titulo = await screen.findByRole('heading', { level: 1, name: 'Esta invitación ya se usó' })
    const baldosa = titulo.closest('div')!.parentElement!.querySelector('[aria-hidden] svg')
    expect(baldosa).not.toBeNull()
  })
})

describe('Crear la cuenta o entrar con una invitación en memoria', () => {
  it('la nota «Después de esto vuelves a la invitación de Carmen.»', () => {
    contexto = familiaFalsa({ invitacion: EN_MEMORIA } as never)
    render(<NotaVuelvesALaInvitacion />)
    expect(screen.getByText('Después de esto vuelves a la invitación de Carmen.')).toBeVisible()
  })

  it('sin invitación, nada', () => {
    contexto = familiaFalsa({ invitacion: null } as never)
    const { container } = render(<NotaVuelvesALaInvitacion />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('El marco', () => {
  it('sin la navegación de la app: solo la marca, el rótulo y el distintivo del piloto', async () => {
    apiInvitacion()
    abrir()
    await screen.findByRole('textbox', { name: 'Código' })
    expect(screen.queryByRole('navigation')).toBeNull()
    expect(within(screen.getByRole('banner')).getByText('Piloto académico')).toBeVisible()
  })
})

// MATU-72: borrar los datos de la persona al tiro, desde Grupo familiar (especificación
// docs/diseno/matu-72-borrar-datos.md v1.1 con A1, A2 y A3; contrato decisiones 149 a 157). El bloque por
// rol, la casilla que habilita «Borrar todo», el foco en «No borrar», el envío sin cuerpo, «Borrando…»
// con Esc bloqueado, red, 409, 404, «No borrar» y lo que se saca de la memoria. Textos de
// lenguaje.md, sección 24, tal cual. Solo datos sintéticos.
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AutorizacionVista, Rol } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { BORRADOR_VACIO } from '../src/familia/estado'
import { GrupoFamiliar } from '../src/familia/Grupo'
import type { RespuestaFalsa } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'
import { respuestaDelGrupo } from './miembrosFalsos'

const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g1'
const MARIA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María' }
const PEDRO = { id: '3c9d4e20-0000-4000-8000-0000000000bb', nombre: 'Pedro Soto', nombre_pila: 'Pedro' }

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

// jsdom no trae `showModal` ni `close`.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.hasAttribute('open')) return
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})

let escrituras: string[] = []
beforeEach(() => {
  escrituras = []
  window.history.replaceState(null, '', '/grupo')
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
})

// ---------------------------------------------------------------- la API de mentira, por ruta

interface Pedida {
  linea: string
  cuerpo?: unknown
  /** Lo que salió en `data`, tal cual: un POST sin cuerpo no lleva nada. */
  data: unknown
  grupo?: string
}
type Atender = (p: Pedida) => RespuestaFalsa | Promise<RespuestaFalsa>

function api(atender: Atender) {
  const pedidas: Pedida[] = []
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const p: Pedida = {
      linea: `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`,
      cuerpo: typeof config.data === 'string' && config.data ? JSON.parse(config.data) : undefined,
      data: config.data,
      grupo: config.headers?.get?.('X-Grupo-Id') as string | undefined,
    }
    // MATU-53: quiénes forman el grupo, que Grupo familiar pide aparte (miembrosFalsos.ts).
    const delGrupo = respuestaDelGrupo(p.linea)
    if (!delGrupo) pedidas.push(p)
    const r = delGrupo ?? (await atender(p))
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return pedidas
}

const problema = (status: number, tipo: string): RespuestaFalsa => ({ status, cuerpo: { type: `/errores/${tipo}`, title: 'TEXTO DE LA API QUE NO SE MUESTRA', status } })
const RED: RespuestaFalsa = { status: 503, cuerpo: { type: '/errores/no-disponible', status: 503 } }

const vista = (finalidad: 'plan_cuidado' | 'consumo', estado: AutorizacionVista['estado'], extra: Partial<AutorizacionVista> = {}): AutorizacionVista => ({
  finalidad,
  estado,
  id: estado === 'sin_autorizar' ? null : '3c9d4e20-0000-4000-8000-0000000000c1',
  otorgado_en: estado === 'sin_autorizar' ? null : '2026-11-04T15:00:00Z',
  revision_vence_en: null,
  revocado_en: null,
  borrado_en: null,
  borrada: false,
  se_puede_otorgar: true,
  ...extra,
})
const VIGENTES = [vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')]
const RETIRADA = { revocado_en: '2026-11-06T15:00:00Z', borrado_en: '2027-02-04T15:00:00Z' }

const acceso = (i: number) => ({
  id: `3c9d4e20-0000-4000-8000-00000000e00${i}`,
  nombre_relevo: `Rosa ${i}`,
  telefono_relevo: null,
  campos: [],
  secciones_adicionales: [],
  motivo: 'reemplazo',
  estado: 'vigente',
  creado_en: '2026-11-05T12:00:00Z',
  expira_en: '2026-11-08T12:00:00Z',
  revocado_en: null,
  usos: 0,
  ultimo_uso_en: null,
  otorgado_por: null,
})

const hecho = (n: number, id = MARIA.id): RespuestaFalsa => ({
  status: 200,
  cuerpo: { persona_id: id, borrado_en: '2026-11-08T15:00:00Z', enlaces_cortados: n, autorizaciones_retiradas: 2 },
})

function apiGrupo(
  autorizaciones: Record<string, AutorizacionVista[]>,
  { enlaces = 2, borrado, personas = [MARIA] }: { enlaces?: number | RespuestaFalsa; borrado?: Atender; personas?: (typeof MARIA)[] } = {},
) {
  return api((p) => {
    if (p.linea === `GET /v1/grupos/${GRUPO_ID}/personas-cuidadas`) return { status: 200, cuerpo: personas }
    const m = /^GET \/v1\/personas-cuidadas\/([^/]+)\/consentimientos$/.exec(p.linea)
    if (m && autorizaciones[m[1]]) return { status: 200, cuerpo: { autorizaciones: autorizaciones[m[1]] } }
    if (/^GET \/v1\/personas-cuidadas\/[^/]+\/plan\/accesos-relevo$/.test(p.linea))
      return typeof enlaces === 'number' ? { status: 200, cuerpo: { items: Array.from({ length: enlaces }, (_, i) => acceso(i)), siguiente_cursor: null } } : enlaces
    if (/^POST \/v1\/personas-cuidadas\/[^/]+\/borrado$/.test(p.linea) && borrado) return borrado(p)
    return problema(404, 'no-encontrado')
  })
}

function abrirGrupo(rol: Rol, cambios: Record<string, unknown> = {}) {
  contexto = familiaFalsa({
    grupo: { id: GRUPO_ID, nombre: 'Familia Soto', rol, puede_ver_plan: rol === 'pagador' },
    rol,
    persona: MARIA,
    personaId: MARIA.id,
    personas: [MARIA],
    borrador: BORRADOR_VACIO,
    reautorizar: null,
    aviso: null,
    ...cambios,
  } as never)
  const { container } = render(
    <>
      <RegionesVivas />
      <GrupoFamiliar />
    </>,
  )
  return within(container)
}

const dialogo = () => screen.getByRole('dialog')
const parrafosDialogo = () => [...dialogo().querySelectorAll(`[id="${dialogo().getAttribute('aria-describedby')}"] p`)] as HTMLElement[]
const casilla = () => within(dialogo()).getByRole('checkbox', { name: 'Entiendo que esto no se puede deshacer.' })
const borrarTodo = () => within(dialogo()).getByRole('button', { name: 'Borrar todo' })
const noBorrar = () => within(dialogo()).getByRole('button', { name: 'No borrar' })

async function abrirConfirmacion(pantalla: ReturnType<typeof abrirGrupo>, pila = 'María') {
  await userEvent.click(await pantalla.findByRole('button', { name: `Borrar los datos de ${pila}` }))
  return dialogo()
}

function diferida() {
  let soltar!: (r: RespuestaFalsa) => void
  const promesa = new Promise<RespuestaFalsa>((ok) => (soltar = ok))
  return { promesa, soltar }
}

// ---------------------------------------------------------------- 2 el bloque

describe('El bloque «Borrar sus datos», por rol', () => {
  it.each(['admin', 'cuidador'] as const)('el %s ve el título, la explicación y el botón, al final de la persona y fuera de la grilla', async (rol) => {
    apiGrupo({ [MARIA.id]: VIGENTES })
    const pantalla = abrirGrupo(rol)
    const seccion = await pantalla.findByRole('region', { name: 'Borrar sus datos' })
    expect(within(seccion).getByRole('heading', { level: 3, name: 'Borrar sus datos' })).toBeVisible()
    expect(
      within(seccion).getByText('Si María o su representante legal lo pide, o si ya no usan MATU para cuidar a María, puedes borrar todo lo guardado. No se puede deshacer.'),
    ).toBeVisible()
    const boton = within(seccion).getByRole('button', { name: 'Borrar los datos de María' })
    // A1: sin `aria-label`, el nombre accesible es el texto visible.
    expect(boton).not.toHaveAttribute('aria-label')
    expect(boton).toHaveTextContent('Borrar los datos de María')
    expect(boton).toHaveAttribute('id', `borrar-${MARIA.id}`)
    // 2.3 y 8.1-8.2: de contorno `peligro`, nunca macizo; sin fondo ni anillo, detrás de una línea.
    expect(boton).toHaveClass('ring-pronto', 'bg-hoja')
    expect(boton).not.toHaveClass('bg-pronto')
    expect(seccion).toHaveClass('border-t', 'border-linea', 'pt-6', 'mt-4')
    expect(seccion.className).not.toMatch(/\bbg-|\bring-|rounded/)
    // Lo último de la sección de la persona, y no dentro de la grilla de los permisos.
    const persona = pantalla.getByRole('region', { name: 'María Soto' })
    expect(persona.lastElementChild).toBe(seccion)
    expect(seccion.closest('.grid')).toBeNull()
    // MATU-53 (10.1): el único turquesa macizo es «Invitar a alguien», solo para admin.
    await waitFor(() => expect([...document.querySelectorAll('.bg-turquesa')].map((b) => b.textContent)).toEqual(rol === 'admin' ? ['Invitar a alguien'] : []))
  })

  it.each(['pagador', 'observador'] as const)('el %s ve solo el título y quién puede (A2), sin botón ni «puedes borrar»', async (rol) => {
    apiGrupo({ [MARIA.id]: VIGENTES })
    const pantalla = abrirGrupo(rol)
    const seccion = await pantalla.findByRole('region', { name: 'Borrar sus datos' })
    expect(within(seccion).getByText('Puede borrarlos quien administra el grupo o quien cuida a María.')).toHaveClass('text-tenue')
    expect(within(seccion).queryByRole('button')).toBeNull()
    expect(pantalla.queryByText(/puedes borrar/)).toBeNull()
    expect(pantalla.queryByRole('button', { name: /Borrar/ })).toBeNull()
  })

  it('A3: con Pedro, la explicación y el párrafo 4 no dan por hecho el género de la persona', async () => {
    apiGrupo({ [PEDRO.id]: VIGENTES }, { personas: [PEDRO] })
    const pantalla = abrirGrupo('admin', { persona: PEDRO, personaId: PEDRO.id, personas: [PEDRO] })
    const seccion = await pantalla.findByRole('region', { name: 'Borrar sus datos' })
    expect(
      within(seccion).getByText('Si Pedro o su representante legal lo pide, o si ya no usan MATU para cuidar a Pedro, puedes borrar todo lo guardado. No se puede deshacer.'),
    ).toBeVisible()
    await abrirConfirmacion(pantalla, 'Pedro')
    expect(parrafosDialogo()[3]).toHaveTextContent(
      /^Pedro sale de MATU\. Si después quieren volver a usar MATU, hay que registrar a Pedro de nuevo, y todo empieza en blanco\.$/,
    )
    const todo = `${seccion.textContent ?? ''} ${dialogo().textContent ?? ''}`
    expect(todo).not.toMatch(/\b(ella|cuidarla|registrarla|la cuidan)\b/)
  })

  it('se ve también con los permisos retirados, y una vez por persona', async () => {
    apiGrupo(
      { [MARIA.id]: [vista('plan_cuidado', 'retirada', RETIRADA), vista('consumo', 'retirada', RETIRADA)], [PEDRO.id]: VIGENTES },
      { personas: [MARIA, PEDRO] },
    )
    const pantalla = abrirGrupo('admin')
    expect(await pantalla.findByRole('button', { name: 'Borrar los datos de María' })).toBeVisible()
    expect(pantalla.getByRole('button', { name: 'Borrar los datos de Pedro' })).toBeVisible()
    expect(pantalla.getAllByRole('region', { name: 'Borrar sus datos' })).toHaveLength(2)
  })
})

// ---------------------------------------------------------------- 3 la confirmación

describe('La confirmación de borrar', () => {
  it('abre con el foco en «No borrar», los siete párrafos y «Borrar todo» con aria-disabled hasta marcar la casilla', async () => {
    const pedidas = apiGrupo({ [MARIA.id]: VIGENTES }, { enlaces: 2, borrado: () => hecho(2) })
    const pantalla = abrirGrupo('admin')
    const d = await abrirConfirmacion(pantalla)

    expect(d).toHaveAccessibleName('¿Borrar todo lo guardado de María?')
    expect(d).toHaveAccessibleDescription(/^Esto no se puede deshacer\. Borramos ahora su ficha/)
    expect(noBorrar()).toHaveFocus()
    expect(within(d).getByRole('heading', { level: 2 })).toHaveAttribute('tabindex', '-1')

    expect(parrafosDialogo().map((p) => p.textContent)).toEqual([
      'Esto no se puede deshacer.',
      'Borramos ahora su ficha, con todas sus secciones, y los insumos y las compras anotadas. Nadie los podrá recuperar, tampoco el equipo de MATU.',
      'Se cortan ahora todos sus enlaces de relevo. Hoy abren 2. Quien tenga la ficha abierta deja de verla cuando vuelva a mirarla. No recibe aviso.',
      'María sale de MATU. Si después quieren volver a usar MATU, hay que registrar a María de nuevo, y todo empieza en blanco.',
      'Guardamos, sin nada de lo escrito, el registro de las autorizaciones, de los enlaces y de quién abrió la ficha, por los plazos de la política de privacidad.',
      'Lo borrado sigue en las copias de respaldo hasta que vencen, y nadie las usa para ver datos.',
      'Una lista que ya imprimiste o compartiste no se borra: quedó fuera de MATU.',
    ])
    // 3.1 y 8.7: solo el primero en negrita, los tres últimos en `tenue`.
    expect(parrafosDialogo().filter((p) => p.classList.contains('font-bold')).map((p) => p.textContent)).toEqual(['Esto no se puede deshacer.'])
    expect(parrafosDialogo().map((p) => p.classList.contains('text-tenue'))).toEqual([false, false, false, false, true, true, true])

    // Sin marcar al abrir. «Borrar todo» con `aria-disabled` (no `disabled`) y tocarlo no envía nada.
    expect(casilla()).not.toBeChecked()
    expect(borrarTodo()).toHaveAttribute('aria-disabled', 'true')
    expect(borrarTodo()).not.toBeDisabled()
    await userEvent.click(borrarTodo())
    expect(pedidas.some((p) => p.linea.endsWith('/borrado'))).toBe(false)
    expect(d).toHaveAttribute('open')
    expect(borrarTodo()).toHaveFocus()

    // Orden del DOM: casilla, error, «Borrar todo», «No borrar».
    const controles = [...d.querySelectorAll('input, button, [role="alert"]')]
    expect(controles).toEqual([casilla(), within(d).getByRole('alert'), borrarTodo(), noBorrar()])

    await userEvent.click(casilla())
    expect(casilla()).toBeChecked()
    expect(borrarTodo()).not.toHaveAttribute('aria-disabled')
    // Si se desmarca, vuelve a quedar deshabilitado.
    await userEvent.click(casilla())
    expect(borrarTodo()).toHaveAttribute('aria-disabled', 'true')
    expect(escrituras).toEqual([])
  })

  it('«Borrar todo» deshabilitado cambia de forma con los tokens hoja, tenue y borde, sin opacity', async () => {
    apiGrupo({ [MARIA.id]: VIGENTES })
    await abrirConfirmacion(abrirGrupo('admin'))
    expect(borrarTodo()).toHaveClass(
      'bg-pronto',
      'text-papel',
      'aria-disabled:bg-hoja',
      'aria-disabled:text-tenue',
      'aria-disabled:ring-2',
      'aria-disabled:ring-inset',
      'aria-disabled:ring-borde',
      'aria-disabled:cursor-not-allowed',
    )
    expect(borrarTodo().className).not.toMatch(/aria-disabled:opacity/)
    // 3.1: la caja con su cuerpo que se desplaza y el pie fijo; en modo angosto se desplaza todo.
    const cuerpo = parrafosDialogo()[0].closest('.overflow-y-auto')!
    expect(cuerpo).toHaveClass('min-h-0', 'flex-1', 'angosto:overflow-visible')
    expect(casilla().closest('.border-t')).toHaveClass('border-linea')
    // La casilla con la medida única de MATU-68 y toda la fila como área táctil.
    expect(casilla()).toHaveClass('size-6', 'accent-turquesa')
    expect(casilla().closest('label')).toHaveClass('min-h-12', 'cursor-pointer')
  })

  it.each([
    ['vigente con 1 enlace', [vista('plan_cuidado', 'vigente')], 1, 'Hoy abre 1.'],
    ['vigente con 0 enlaces', [vista('plan_cuidado', 'vigente')], 0, 'Hoy ningún enlace abre.'],
    ['por renovar', [vista('plan_cuidado', 'revision_vencida', { revision_vence_en: '2026-10-01T15:00:00Z' })], 2, 'Hoy ningún enlace abre.'],
    ['retirada', [vista('plan_cuidado', 'retirada', RETIRADA)], 2, 'Hoy ningún enlace abre.'],
    // R3 (1.1): sin autorizar nunca hubo enlaces; el dato se conoce y es cero, no se omite.
    ['sin autorizar', [vista('plan_cuidado', 'sin_autorizar')], 0, 'Hoy ningún enlace abre.'],
  ] as const)('«Hoy abren» con la ficha %s: «%s»', async (_caso, [ficha], n, frase) => {
    apiGrupo({ [MARIA.id]: [ficha, vista('consumo', 'vigente')] }, { enlaces: n })
    await abrirConfirmacion(abrirGrupo('cuidador'))
    expect(parrafosDialogo()[2]).toHaveTextContent(
      `Se cortan ahora todos sus enlaces de relevo. ${frase} Quien tenga la ficha abierta deja de verla cuando vuelva a mirarla. No recibe aviso.`,
    )
  })

  it('sin el conteo omite «Hoy abren», y no pide nada nuevo al abrir', async () => {
    const pedidas = apiGrupo({ [MARIA.id]: VIGENTES }, { enlaces: RED })
    const pantalla = abrirGrupo('admin')
    await pantalla.findByRole('button', { name: 'Borrar los datos de María' })
    const antes = pedidas.length
    await abrirConfirmacion(pantalla)
    expect(parrafosDialogo()[2]).toHaveTextContent(
      /^Se cortan ahora todos sus enlaces de relevo\. Quien tenga la ficha abierta deja de verla cuando vuelva a mirarla\. No recibe aviso\.$/,
    )
    expect(pedidas.length).toBe(antes)
  })

  it('sin la vista de la ficha omite «Hoy abren», aunque haya conteo', async () => {
    apiGrupo({ [MARIA.id]: [vista('consumo', 'vigente')] }, { enlaces: 2 })
    await abrirConfirmacion(abrirGrupo('admin'))
    expect(parrafosDialogo()[2]).toHaveTextContent(
      /^Se cortan ahora todos sus enlaces de relevo\. Quien tenga la ficha abierta deja de verla cuando vuelva a mirarla\. No recibe aviso\.$/,
    )
  })

  it('en curso: «Borrando…», sin cuerpo, y ni «No borrar», ni la casilla, ni uno o dos Esc cambian nada', async () => {
    const respuesta = diferida()
    const pedidas = apiGrupo({ [MARIA.id]: VIGENTES }, { borrado: () => respuesta.promesa })
    const pantalla = abrirGrupo('admin')
    const d = await abrirConfirmacion(pantalla)
    await userEvent.click(casilla())
    // En curso su nombre suma «Borrando…»: se toma el botón antes.
    const boton = borrarTodo()
    await userEvent.click(boton)

    expect(boton).toHaveAttribute('aria-busy', 'true')
    expect(within(boton).getByText('Borrando…')).toBeVisible()
    // Sin interfaz optimista: la persona sigue en la pantalla y en la memoria mientras espera.
    expect(pantalla.getByRole('region', { name: 'María Soto' })).toBeInTheDocument()
    expect(contexto.fijar).not.toHaveBeenCalledWith(expect.objectContaining({ personas: expect.anything() }))

    expect(noBorrar()).toHaveAttribute('aria-disabled', 'true')
    await userEvent.click(noBorrar())
    expect(casilla()).toHaveAttribute('aria-disabled', 'true')
    await userEvent.click(casilla())
    expect(casilla()).toBeChecked()
    fireEvent(d, new Event('cancel', { cancelable: true }))
    expect(d).toHaveAttribute('open')
    // El segundo Esc de Chrome cierra aunque el primero se anuló: se vuelve a abrir, foco al botón.
    noBorrar().focus()
    d.removeAttribute('open')
    fireEvent(d, new Event('close'))
    expect(d).toHaveAttribute('open')
    expect(boton).toHaveFocus()

    const borrados = pedidas.filter((p) => p.linea.endsWith('/borrado'))
    expect(borrados).toHaveLength(1)
    // Decisión 149: POST sin cuerpo, con el grupo en X-Grupo-Id (lo pone el interceptor de sesion.ts).
    expect(borrados[0].linea).toBe(`POST /v1/personas-cuidadas/${MARIA.id}/borrado`)
    expect(borrados[0].data).toBeUndefined()
    expect(borrados[0].cuerpo).toBeUndefined()

    await act(async () => respuesta.soltar(hecho(3)))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('sin conexión: el error en el pie, la casilla sigue marcada, todo sigue igual y se reintenta', async () => {
    let veces = 0
    apiGrupo({ [MARIA.id]: VIGENTES }, { borrado: () => (++veces === 1 ? RED : hecho(2)) })
    const pantalla = abrirGrupo('admin')
    const d = await abrirConfirmacion(pantalla)
    const region = within(d).getByRole('alert')
    expect(region).toBeEmptyDOMElement()
    await userEvent.click(casilla())
    await userEvent.click(borrarTodo())
    await waitFor(() => expect(region).toHaveTextContent('No pudimos borrar los datos. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.'))
    // En el pie, a la vista: entre la casilla y los botones.
    expect(region.closest('.border-t')).toBe(casilla().closest('.border-t'))
    expect(d).toHaveAttribute('open')
    expect(casilla()).toBeChecked()
    expect(borrarTodo()).not.toHaveAttribute('aria-busy')
    expect(borrarTodo()).toHaveFocus()
    expect(pantalla.getByRole('region', { name: 'María Soto' })).toBeInTheDocument()
    expect(contexto.fijar).not.toHaveBeenCalled()
    expect(pantalla.queryByText(/TEXTO DE LA API/)).toBeNull()

    await userEvent.click(borrarTodo())
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(veces).toBe(2)
  })

  it('P3: al mostrar el error trae la región entera a la vista, con «nearest», y el foco sigue en «Borrar todo»', async () => {
    const llevar = vi.fn()
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = llevar
    try {
      apiGrupo({ [MARIA.id]: VIGENTES }, { borrado: () => RED })
      const d = await abrirConfirmacion(abrirGrupo('admin'))
      const region = within(d).getByRole('alert')
      await userEvent.click(casilla())
      await userEvent.click(borrarTodo())
      await waitFor(() => expect(region).not.toBeEmptyDOMElement())
      await waitFor(() => expect(llevar).toHaveBeenCalledWith({ block: 'nearest' }))
      expect(llevar.mock.contexts.at(-1)).toBe(region)
      expect(borrarTodo()).toHaveFocus()
    } finally {
      Element.prototype.scrollIntoView = original
    }
  })

  it('404: cierra y Grupo familiar vuelve a cargar, sin decir por qué, con el foco en el título', async () => {
    let borrada = false
    const pedidas = api((p) => {
      if (p.linea.endsWith('/personas-cuidadas')) return { status: 200, cuerpo: borrada ? [] : [MARIA] }
      if (p.linea.endsWith('/consentimientos')) return { status: 200, cuerpo: { autorizaciones: VIGENTES } }
      if (p.linea.endsWith('/borrado')) return (borrada = true), problema(404, 'no-encontrado')
      return { status: 200, cuerpo: { items: [], siguiente_cursor: null } }
    })
    const pantalla = abrirGrupo('admin')
    // `Pagina` pone el `h1` de la pantalla.
    await abrirConfirmacion(pantalla)
    await userEvent.click(casilla())
    await userEvent.click(borrarTodo())
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    await waitFor(() => expect(pantalla.getByRole('heading', { level: 1, name: 'Grupo familiar' })).toHaveFocus())
    expect(pedidas.filter((p) => p.linea.endsWith('/personas-cuidadas'))).toHaveLength(2)
    expect(pantalla.queryByText(/TEXTO DE LA API/)).toBeNull()
    expect(contexto.fijar).not.toHaveBeenCalledWith(expect.objectContaining({ aviso: expect.anything() }))
  })

  it('«No borrar» y Esc cierran sin pedir nada, y el foco vuelve al botón que abrió; la casilla no se recuerda', async () => {
    const pedidas = apiGrupo({ [MARIA.id]: VIGENTES })
    const pantalla = abrirGrupo('admin')
    const abrir = await pantalla.findByRole('button', { name: 'Borrar los datos de María' })
    await userEvent.click(abrir)
    await userEvent.click(casilla())
    await userEvent.click(noBorrar())
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(abrir).toHaveFocus())

    await userEvent.click(abrir)
    expect(casilla()).not.toBeChecked()
    fireEvent(dialogo(), new Event('cancel', { cancelable: true }))
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(abrir).toHaveFocus())
    expect(pedidas.some((p) => p.linea.endsWith('/borrado'))).toBe(false)
    expect(contexto.fijar).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------- 4 la persona sale de la app

describe('Después del borrado, la persona sale de la memoria', () => {
  it('la única persona: en una sola llamada a fijar sale de personas, ficha, autorización, intención y borrador, con la nota de hecho', async () => {
    apiGrupo({ [MARIA.id]: VIGENTES }, { enlaces: 1, borrado: () => hecho(3) })
    const pantalla = abrirGrupo('admin', {
      ficha: { campos: {} },
      autorizacion: 'sin-consentimiento',
      reautorizar: { personaId: MARIA.id, finalidad: 'plan_cuidado', vista: null },
      borrador: { nombre: 'María Soto', pila: 'María', apoyo: null },
    })
    await abrirConfirmacion(pantalla)
    await userEvent.click(casilla())
    await userEvent.click(borrarTodo())
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    const conPersonas = vi.mocked(contexto.fijar).mock.calls.filter(([c]) => 'personas' in c)
    expect(conPersonas).toEqual([
      [
        {
          personas: [],
          personaId: null,
          ficha: null,
          autorizacion: null,
          reautorizar: null,
          borrador: BORRADOR_VACIO,
          // 4.3: «Cortamos {n}» es el de la respuesta (3), no el conteo de la confirmación (1).
          aviso: { titulo: 'Borramos los datos de María. Cortamos 3 enlaces.', tono: 'ok', enfocar: false },
        },
      ],
    ])
    // La sección de la persona ya no está en Grupo familiar.
    expect(pantalla.queryByRole('region', { name: 'María Soto' })).toBeNull()
    expect(escrituras).toEqual([])
    expect(window.location.href).not.toContain(MARIA.id)
  })

  it.each([
    [1, 'Borramos los datos de María. Cortamos 1 enlace.'],
    [0, 'Borramos los datos de María. No había enlaces que abrieran.'],
  ])('con %i enlaces cortados la nota dice «%s»', async (n, texto) => {
    apiGrupo({ [MARIA.id]: VIGENTES }, { borrado: () => hecho(n) })
    await abrirConfirmacion(abrirGrupo('cuidador'))
    await userEvent.click(casilla())
    await userEvent.click(borrarTodo())
    await waitFor(() => expect(contexto.fijar).toHaveBeenCalledWith(expect.objectContaining({ aviso: { titulo: texto, tono: 'ok', enfocar: false } })))
  })

  it('con otra persona elegida que queda: solo sale la borrada, el borrador ajeno sigue y la nota recibe el foco en /grupo', async () => {
    const borradorAjeno = { nombre: 'Juana Pérez', pila: 'Juana', apoyo: null }
    apiGrupo({ [MARIA.id]: VIGENTES, [PEDRO.id]: VIGENTES }, { personas: [PEDRO, MARIA], borrado: () => hecho(2) })
    const pantalla = abrirGrupo('admin', { persona: PEDRO, personaId: PEDRO.id, personas: [PEDRO, MARIA], borrador: borradorAjeno, ficha: { campos: {} } })
    await abrirConfirmacion(pantalla)
    await userEvent.click(casilla())
    await userEvent.click(borrarTodo())
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())

    expect(contexto.fijar).toHaveBeenCalledWith({
      personas: [PEDRO],
      aviso: { titulo: 'Borramos los datos de María. Cortamos 2 enlaces.', tono: 'ok', enfocar: true },
    })
    expect(pantalla.queryByRole('region', { name: 'María Soto' })).toBeNull()
    expect(pantalla.getByRole('region', { name: 'Pedro Soto' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/grupo')
  })

  it('409 ya-borrada: cierra y la persona sale igual, con la nota de que otra persona ya la borró', async () => {
    apiGrupo({ [MARIA.id]: VIGENTES }, { borrado: () => problema(409, 'ya-borrada') })
    const pantalla = abrirGrupo('admin')
    await abrirConfirmacion(pantalla)
    await userEvent.click(casilla())
    await userEvent.click(borrarTodo())
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(contexto.fijar).toHaveBeenCalledWith(
      expect.objectContaining({ personas: [], personaId: null, aviso: { titulo: 'Otra persona de tu grupo ya borró los datos de María.', tono: 'rocio', enfocar: false } }),
    )
    expect(pantalla.queryByRole('region', { name: 'María Soto' })).toBeNull()
    expect(pantalla.queryByText(/TEXTO DE LA API/)).toBeNull()
  })

  it('otro 409 no es «ya borrada»: se queda en el diálogo con el error y no saca a nadie', async () => {
    apiGrupo({ [MARIA.id]: VIGENTES }, { borrado: () => problema(409, 'otra-cosa') })
    const pantalla = abrirGrupo('admin')
    const d = await abrirConfirmacion(pantalla)
    await userEvent.click(casilla())
    await userEvent.click(borrarTodo())
    await waitFor(() => expect(within(d).getByRole('alert')).toHaveTextContent(/^No pudimos borrar los datos\./))
    expect(contexto.fijar).not.toHaveBeenCalled()
  })
})

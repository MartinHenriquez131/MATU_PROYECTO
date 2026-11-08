// MATU-44: Grupo familiar, retirar una autorización y volver a autorizar (especificación
// docs/diseno/matu-44-retirar-autorizacion.md v1.1, contrato decisiones 123 a 135). Los estados por
// rol, la confirmación (0, 1 y n enlaces, por renovar, 409 y error de red), el foco, volver a
// autorizar dentro y después de los 90 días, la ficha sin autorización y el aviso de Enlaces. Textos
// de lenguaje.md, sección 22, tal cual. Solo datos sintéticos.
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AutorizacionVista, Rol } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { Enlaces } from '../src/familia/Compartir'
import { Bloqueada } from '../src/familia/Ficha'
import { AutorizarFicha, AutorizarInsumos, GrupoFamiliar } from '../src/familia/Grupo'
import { ShellFamilia } from '../src/familia/Shell'
import type { RespuestaFalsa } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'

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
  // Como el navegador: `close` cierra y avisa con el evento `close`.
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
  params?: Record<string, unknown>
  cuerpo?: unknown
}
type Atender = (p: Pedida) => RespuestaFalsa | Promise<RespuestaFalsa>

/** Responde según el método y la ruta. Devuelve las peticiones (sin registrar nada fuera de la prueba). */
function api(atender: Atender) {
  const pedidas: Pedida[] = []
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const p: Pedida = {
      linea: `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`,
      params: config.params as Record<string, unknown> | undefined,
      cuerpo: typeof config.data === 'string' && config.data ? JSON.parse(config.data) : undefined,
    }
    pedidas.push(p)
    const r = await atender(p)
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
  otorgado_en: estado === 'sin_autorizar' ? null : finalidad === 'plan_cuidado' ? '2026-11-04T15:00:00Z' : '2026-11-05T15:00:00Z',
  revision_vence_en: null,
  revocado_en: null,
  borrado_en: null,
  borrada: false,
  ...extra,
})
const RETIRADA = { revocado_en: '2026-11-06T15:00:00Z', borrado_en: '2027-02-04T15:00:00Z' }
const BORRADA = { revocado_en: '2026-07-01T15:00:00Z', borrado_en: '2026-09-29T15:00:00Z', borrada: true }

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

/** Lo que responde la API de Grupo familiar: personas, sus dos autorizaciones y sus enlaces. */
function apiGrupo(
  autorizaciones: Record<string, AutorizacionVista[] | RespuestaFalsa>,
  { enlaces = 2, retiro, personas = [MARIA] }: { enlaces?: number | RespuestaFalsa; retiro?: Atender; personas?: typeof MARIA[] } = {},
) {
  return api((p) => {
    if (p.linea === `GET /v1/grupos/${GRUPO_ID}/personas-cuidadas`) return { status: 200, cuerpo: personas }
    const m = /^GET \/v1\/personas-cuidadas\/([^/]+)\/consentimientos$/.exec(p.linea)
    if (m) {
      const a = autorizaciones[m[1]]
      return Array.isArray(a) ? { status: 200, cuerpo: { autorizaciones: a.map((x) => ({ ...x, calidad_otorgante: 'titular' })) } } : a
    }
    if (/^GET \/v1\/personas-cuidadas\/[^/]+\/plan\/accesos-relevo$/.test(p.linea))
      return typeof enlaces === 'number' ? { status: 200, cuerpo: { items: Array.from({ length: enlaces }, (_, i) => acceso(i)), siguiente_cursor: null } } : enlaces
    if (/\/retiro$/.test(p.linea) && retiro) return retiro(p)
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

/** Un párrafo por su texto completo, aunque la fecha vaya en su propio `span`. */
const parrafo = (texto: string) => screen.getByText((_, el) => el?.tagName === 'P' && el.textContent === texto)
const bloque = (titulo: string) => screen.getByRole('region', { name: titulo })
const dialogo = () => screen.getByRole('dialog')

// ---------------------------------------------------------------- 3 Grupo familiar por rol

describe('Grupo familiar, por rol y por estado', () => {
  it('admin con los dos permisos autorizados: el título, los dos bloques, sus fechas y los botones con su nombre', async () => {
    const pedidas = apiGrupo({ [MARIA.id]: [vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')] })
    const pantalla = abrirGrupo('admin')
    expect(await pantalla.findByText('Permiso para guardar su ficha')).toBeVisible()
    expect(pantalla.getByRole('heading', { level: 1, name: 'Grupo familiar' })).toBeVisible()
    expect(pantalla.getByText('A quién cuidan en Familia Soto y qué permisos dieron.')).toBeVisible()
    expect(pantalla.getByRole('heading', { level: 2, name: 'María Soto' })).toBeVisible()

    expect(within(bloque('Permiso para guardar su ficha')).getByText(/^Autorizada el/)).toHaveTextContent('Autorizada el 04/11/2026.')
    expect(within(bloque('Permiso para calcular sus insumos')).getByText(/^Autorizado el/)).toHaveTextContent('Autorizado el 05/11/2026.')

    const retirarFicha = pantalla.getByRole('button', { name: 'Retirar la autorización de la ficha de María' })
    expect(retirarFicha).toHaveTextContent('Retirar la autorización')
    expect(pantalla.getByRole('button', { name: 'Retirar la autorización de los insumos de María' })).toBeVisible()
    // 6.2: ningún elemento en turquesa macizo en Grupo familiar.
    expect(document.querySelector('.bg-turquesa')).toBeNull()
    // P2: la calidad de quien autorizó nunca se muestra, aunque la API la mande al admin.
    expect(pantalla.queryByText(/titular|representante|de hecho/i)).toBeNull()

    expect(pedidas.map((p) => p.linea)).toEqual([
      `GET /v1/grupos/${GRUPO_ID}/personas-cuidadas`,
      `GET /v1/personas-cuidadas/${MARIA.id}/consentimientos`,
      `GET /v1/personas-cuidadas/${MARIA.id}/plan/accesos-relevo`,
    ])
    expect(pedidas[2].params).toEqual({ limite: 100, estado: 'vigente' })
    expect(escrituras).toEqual([])
  })

  it('cada estado con su frase y su botón: por renovar, retirada, ya borrada y sin autorizar', async () => {
    apiGrupo(
      {
        [MARIA.id]: [vista('plan_cuidado', 'revision_vencida', { otorgado_en: '2025-10-01T15:00:00Z', revision_vence_en: '2026-10-01T15:00:00Z' }), vista('consumo', 'retirada', RETIRADA)],
        [PEDRO.id]: [vista('plan_cuidado', 'borrada', BORRADA), vista('consumo', 'sin_autorizar')],
      },
      { personas: [MARIA, PEDRO] },
    )
    const pantalla = abrirGrupo('cuidador')
    const maria = within(await pantalla.findByRole('region', { name: 'María Soto' }))
    const pedro = within(pantalla.getByRole('region', { name: 'Pedro Soto' }))

    const fichaMaria = within(maria.getByRole('region', { name: 'Permiso para guardar su ficha' }))
    expect(fichaMaria.getByText(/^Autorizada el/)).toHaveTextContent('Autorizada el 01/10/2025. Hay que renovarla desde el 01/10/2026.')
    // P6: con la revisión vencida también se retira. P5: sin botón de renovar.
    expect(fichaMaria.getByRole('button', { name: 'Retirar la autorización de la ficha de María' })).toBeVisible()
    expect(pantalla.queryByRole('button', { name: /renovar/i })).toBeNull()

    const insumosMaria = within(maria.getByRole('region', { name: 'Permiso para calcular sus insumos' }))
    expect(insumosMaria.getByText(/^Autorización retirada el/)).toHaveTextContent(
      'Autorización retirada el 06/11/2026. Si no vuelves a autorizar, lo guardado se borra el 04/02/2027.',
    )
    expect(insumosMaria.getByRole('button', { name: 'Volver a autorizar los insumos de María' })).toHaveTextContent('Volver a autorizar')

    const fichaPedro = within(pedro.getByRole('region', { name: 'Permiso para guardar su ficha' }))
    expect(fichaPedro.getByText(/^Autorización retirada el/)).toHaveTextContent('Autorización retirada el 01/07/2026. Lo guardado se borró el 29/09/2026.')
    // 3.3 (revisión del 07-11): en modo angosto el ícono va en la primera línea de la frase.
    const estado = fichaPedro.getByText(/^Autorización retirada el/).closest('p')!
    expect(estado).toHaveClass('flex', 'angosto:block')
    expect(estado.querySelector('svg')).toHaveClass('angosto:inline', 'angosto:mr-1.5', 'angosto:align-middle')
    // 3.4 (revisión del 07-11): cada punto final va dentro del `cifras` de su fecha.
    expect([...fichaPedro.getByText(/^Autorización retirada el/).querySelectorAll('.cifras')].map((c) => c.textContent)).toEqual(['01/07/2026.', '29/09/2026.'])
    expect([...fichaMaria.getByText(/^Autorizada el/).querySelectorAll('.cifras')].map((c) => c.textContent)).toEqual(['01/10/2025.', '01/10/2026.'])
    expect(fichaPedro.getByRole('button', { name: 'Volver a autorizar la ficha de Pedro' })).toBeVisible()

    const insumosPedro = within(pedro.getByRole('region', { name: 'Permiso para calcular sus insumos' }))
    expect(insumosPedro.getByText('Sin permiso todavía. Se pide al anotar el primer insumo.')).toBeVisible()
    expect(insumosPedro.queryByRole('button')).toBeNull()

    // 9.3: la retirada y la borrada con borde punteado sobre papel; la vigente, con anillo sobre hoja.
    expect(maria.getByRole('region', { name: 'Permiso para calcular sus insumos' })).toHaveClass('border-dashed', 'bg-papel')
    expect(maria.getByRole('region', { name: 'Permiso para guardar su ficha' })).toHaveClass('ring-linea', 'bg-hoja')
  })

  it.each(['pagador', 'observador'] as const)('el %s ve el estado y las fechas, sin botones, sin la calidad y sin pedir los enlaces', async (rol) => {
    const pedidas = apiGrupo({ [MARIA.id]: [vista('plan_cuidado', 'vigente'), vista('consumo', 'retirada', RETIRADA)] })
    const pantalla = abrirGrupo(rol)
    const ficha = within(await pantalla.findByRole('region', { name: 'Permiso para guardar su ficha' }))
    expect(ficha.getByText(/^Autorizada el/)).toHaveTextContent('Autorizada el 04/11/2026.')
    expect(ficha.getByText('Puede retirarla quien administra el grupo o quien cuida a María.')).toBeVisible()
    const insumos = within(pantalla.getByRole('region', { name: 'Permiso para calcular sus insumos' }))
    expect(insumos.getByText(/^Autorización retirada el/)).toHaveTextContent(
      'Autorización retirada el 06/11/2026. Si nadie vuelve a autorizar, lo guardado se borra el 04/02/2027.',
    )
    expect(insumos.getByText('Puede volver a autorizarla quien administra el grupo o quien cuida a María.')).toBeVisible()
    expect(pantalla.queryByRole('button')).toBeNull()
    expect(pantalla.queryByText(/titular|representante|de hecho/i)).toBeNull()
    expect(pedidas.some((p) => p.linea.includes('accesos-relevo'))).toBe(false)
  })

  it.each(['admin', 'observador'] as const)('retirada sin `borrado_en`: el %s ve solo «Autorización retirada el {fecha}.», sin texto de reserva', async (rol) => {
    apiGrupo({ [MARIA.id]: [vista('plan_cuidado', 'retirada', { revocado_en: RETIRADA.revocado_en }), vista('consumo', 'vigente')] })
    const pantalla = abrirGrupo(rol)
    const ficha = within(await pantalla.findByRole('region', { name: 'Permiso para guardar su ficha' }))
    expect(ficha.getByText(/^Autorización retirada el/).closest('p')).toHaveTextContent(/^Autorización retirada el 06\/11\/2026\.$/)
    expect(pantalla.queryByText(/90 días|se borra/)).toBeNull()
  })

  it('si no se pueden traer los permisos, lo dice y deja intentar de nuevo', async () => {
    let falla = true
    api((p) => {
      if (p.linea.endsWith('/personas-cuidadas')) return falla ? RED : { status: 200, cuerpo: [MARIA] }
      if (p.linea.endsWith('/consentimientos')) return { status: 200, cuerpo: { autorizaciones: [vista('plan_cuidado', 'vigente'), vista('consumo', 'sin_autorizar')] } }
      return { status: 200, cuerpo: { items: [], siguiente_cursor: null } }
    })
    const pantalla = abrirGrupo('admin')
    expect(await pantalla.findByText('No pudimos traer los permisos. Revisa tu conexión e inténtalo de nuevo.')).toBeVisible()
    falla = false
    await userEvent.click(pantalla.getByRole('button', { name: 'Intentar de nuevo' }))
    expect(await pantalla.findByText('Permiso para guardar su ficha')).toBeVisible()
  })

  it('una persona con 404 sale de la lista', async () => {
    apiGrupo({ [MARIA.id]: [vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')], [PEDRO.id]: problema(404, 'no-encontrado') }, { personas: [MARIA, PEDRO] })
    const pantalla = abrirGrupo('admin')
    expect(await pantalla.findByRole('heading', { level: 2, name: 'María Soto' })).toBeVisible()
    expect(pantalla.queryByText('Pedro Soto')).toBeNull()
  })

  it('muestra la confirmación de volver a autorizar al llegar de 5.1 o 5.2', async () => {
    apiGrupo({ [MARIA.id]: [vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')] })
    const pantalla = abrirGrupo('admin', { aviso: { titulo: 'Autorización registrada. Ya puedes ver y cambiar la ficha de María.', tono: 'ok' } })
    expect(pantalla.getByText('Autorización registrada. Ya puedes ver y cambiar la ficha de María.')).toBeVisible()
    expect(contexto.fijar).toHaveBeenCalledWith({ aviso: null })
  })
})

// ---------------------------------------------------------------- 4 la confirmación

/** Una respuesta que la prueba suelta cuando quiere: para ver «Retirando…». */
function diferida() {
  let soltar!: (r: RespuestaFalsa) => void
  const promesa = new Promise<RespuestaFalsa>((ok) => (soltar = ok))
  return { promesa, soltar }
}

const textosDialogo = () => within(dialogo()).getAllByRole('listitem').map((li) => li.textContent)

describe('La confirmación de retirar', () => {
  it('la ficha con 2 enlaces: foco en la pregunta, el texto, «Retirando…» sin Esc ni «No retirar», y la confirmación con el foco', async () => {
    const respuesta = diferida()
    const pedidas = apiGrupo(
      { [MARIA.id]: [vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')] },
      { enlaces: 2, retiro: () => respuesta.promesa },
    )
    const pantalla = abrirGrupo('admin')
    await userEvent.click(await pantalla.findByRole('button', { name: 'Retirar la autorización de la ficha de María' }))

    const d = dialogo()
    expect(d).toHaveAccessibleName('¿Retirar la autorización de la ficha de María?')
    expect(within(d).getByRole('heading', { level: 2 })).toHaveFocus()
    expect(textosDialogo()).toEqual([
      'Nadie del grupo podrá ver ni cambiar su ficha.',
      'Se cortan ahora todos sus enlaces de relevo. Hoy abren 2. Si alguien tiene la ficha abierta, se le cierra cuando vuelva a mirarla. No recibe aviso.',
      'Un enlace cortado no vuelve a abrir, aunque autorices de nuevo.',
      'Lo escrito queda guardado sin que nadie lo vea. Si no vuelves a autorizar en 90 días, se borra.',
      'La autorización de los insumos no cambia.',
    ])
    // Solo lo que no vuelve va en negrita.
    expect(within(d).getAllByRole('listitem').filter((li) => li.classList.contains('font-bold')).map((li) => li.textContent)).toEqual([
      'Un enlace cortado no vuelve a abrir, aunque autorices de nuevo.',
    ])
    expect(d).toHaveAccessibleDescription(/^Nadie del grupo podrá ver ni cambiar su ficha\./)

    const confirmar = within(d).getByRole('button', { name: 'Retirar la autorización' })
    expect(confirmar).toHaveClass('bg-pronto', 'text-papel')
    await userEvent.click(confirmar)
    expect(confirmar).toHaveAttribute('aria-busy', 'true')
    expect(within(confirmar).getByText('Retirando…')).toBeVisible()
    // Sin interfaz optimista: el bloque sigue igual mientras espera.
    expect(within(bloque('Permiso para guardar su ficha')).getByText(/^Autorizada el/)).toBeVisible()

    // 4.4: mientras tanto, ni Esc ni «No retirar» cierran.
    const noRetirar = within(d).getByRole('button', { name: 'No retirar' })
    expect(noRetirar).toHaveAttribute('aria-disabled', 'true')
    await userEvent.click(noRetirar)
    fireEvent(d, new Event('cancel', { cancelable: true }))
    expect(d).toHaveAttribute('open')
    expect(pedidas.filter((p) => p.linea.endsWith('/retiro'))).toHaveLength(1)

    // Revisión del 07-11 (P2): un segundo Esc en Chrome cierra el diálogo aunque el primero se anuló.
    // Con la petición en curso, vuelve a abrirse con el foco en el botón.
    noRetirar.focus()
    d.removeAttribute('open')
    fireEvent(d, new Event('close'))
    expect(d).toHaveAttribute('open')
    expect(confirmar).toHaveFocus()

    await act(async () =>
      respuesta.soltar({ status: 200, cuerpo: { autorizacion: { ...vista('plan_cuidado', 'retirada', RETIRADA), calidad_otorgante: 'titular' }, enlaces_cortados: 3 } }),
    )
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(pedidas.find((p) => p.linea.endsWith('/retiro'))).toEqual({ linea: `POST /v1/personas-cuidadas/${MARIA.id}/consentimientos/plan_cuidado/retiro`, params: undefined, cuerpo: undefined })

    // 3.5: «Cortamos {n}» es el de la respuesta, no el conteo de la pantalla. El bloque no cambió de lugar.
    const ficha = within(bloque('Permiso para guardar su ficha'))
    const nota = ficha.getByText('Autorización retirada. Cortamos 3 enlaces.').closest('[data-aviso]')
    await waitFor(() => expect(nota).toHaveFocus())
    expect(ficha.getByText(/^Autorización retirada el/)).toHaveTextContent('Autorización retirada el 06/11/2026. Si no vuelves a autorizar, lo guardado se borra el 04/02/2027.')
    expect(ficha.getByRole('button', { name: 'Volver a autorizar la ficha de María' })).toBeVisible()
    // 4.5: la ficha sale de la memoria.
    expect(contexto.fijar).toHaveBeenCalledWith({ ficha: null, autorizacion: 'sin-consentimiento' })
    expect(escrituras).toEqual([])
  })

  it.each([
    [1, 'Hoy abre 1.', 'Autorización retirada. Cortamos 1 enlace.'],
    [0, 'Hoy ningún enlace abre.', 'Autorización retirada. No había enlaces que abrieran.'],
  ])('con %i enlaces dice «%s» y después «%s»', async (n, hoy, hecho) => {
    apiGrupo(
      { [MARIA.id]: [vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')] },
      { enlaces: n, retiro: () => ({ status: 200, cuerpo: { autorizacion: vista('plan_cuidado', 'retirada', RETIRADA), enlaces_cortados: n } }) },
    )
    const pantalla = abrirGrupo('admin')
    await userEvent.click(await pantalla.findByRole('button', { name: 'Retirar la autorización de la ficha de María' }))
    expect(textosDialogo()[1]).toBe(`Se cortan ahora todos sus enlaces de relevo. ${hoy} Si alguien tiene la ficha abierta, se le cierra cuando vuelva a mirarla. No recibe aviso.`)
    await userEvent.click(within(dialogo()).getByRole('button', { name: 'Retirar la autorización' }))
    expect(await pantalla.findByText(hecho)).toBeVisible()
  })

  it('sin el conteo omite «Hoy abren», y sin el permiso de los insumos omite el último punto', async () => {
    apiGrupo({ [MARIA.id]: [vista('plan_cuidado', 'vigente'), vista('consumo', 'sin_autorizar')] }, { enlaces: RED })
    const pantalla = abrirGrupo('admin')
    await userEvent.click(await pantalla.findByRole('button', { name: 'Retirar la autorización de la ficha de María' }))
    expect(textosDialogo()).toEqual([
      'Nadie del grupo podrá ver ni cambiar su ficha.',
      'Se cortan ahora todos sus enlaces de relevo. Si alguien tiene la ficha abierta, se le cierra cuando vuelva a mirarla. No recibe aviso.',
      'Un enlace cortado no vuelve a abrir, aunque autorices de nuevo.',
      'Lo escrito queda guardado sin que nadie lo vea. Si no vuelves a autorizar en 90 días, se borra.',
    ])
  })

  it('con la revisión vencida (P6) los enlaces están en pausa y se retira igual', async () => {
    const pedidas = apiGrupo(
      { [MARIA.id]: [vista('plan_cuidado', 'revision_vencida', { otorgado_en: '2025-10-01T15:00:00Z', revision_vence_en: '2026-10-01T15:00:00Z' }), vista('consumo', 'vigente')] },
      { enlaces: 2, retiro: () => ({ status: 200, cuerpo: { autorizacion: vista('plan_cuidado', 'retirada', RETIRADA), enlaces_cortados: 2 } }) },
    )
    const pantalla = abrirGrupo('cuidador')
    await userEvent.click(await pantalla.findByRole('button', { name: 'Retirar la autorización de la ficha de María' }))
    expect(textosDialogo()[1]).toContain('Hoy están en pausa 2.')
    expect(textosDialogo()[1]).not.toContain('Hoy abren')
    await userEvent.click(within(dialogo()).getByRole('button', { name: 'Retirar la autorización' }))
    expect(await pantalla.findByText('Autorización retirada. Cortamos 2 enlaces.')).toBeVisible()
    expect(pedidas.some((p) => p.linea.endsWith('/plan_cuidado/retiro'))).toBe(true)
  })

  it('los insumos: el texto con la lista ya impresa (P7) en negrita, y la confirmación sin tocar la ficha en memoria', async () => {
    const pedidas = apiGrupo(
      { [MARIA.id]: [vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')] },
      { retiro: () => ({ status: 200, cuerpo: { autorizacion: vista('consumo', 'retirada', RETIRADA), enlaces_cortados: 0 } }) },
    )
    const pantalla = abrirGrupo('admin')
    await userEvent.click(await pantalla.findByRole('button', { name: 'Retirar la autorización de los insumos de María' }))
    expect(dialogo()).toHaveAccessibleName('¿Retirar la autorización de los insumos de María?')
    expect(textosDialogo()).toEqual([
      'Dejamos de calcular cuándo se acaban y de avisar, desde ahora. Tampoco avisamos al resto del grupo.',
      'Nadie del grupo podrá ver los insumos anotados.',
      'Lo anotado queda guardado sin que nadie lo vea. Si no vuelves a autorizar en 90 días, se borra.',
      'Una lista que ya imprimiste o compartiste no se borra: quedó fuera de MATU.',
      'Su ficha y los enlaces de relevo no cambian.',
    ])
    expect(within(dialogo()).getByText('Una lista que ya imprimiste o compartiste no se borra: quedó fuera de MATU.')).toHaveClass('font-bold')
    await userEvent.click(within(dialogo()).getByRole('button', { name: 'Retirar la autorización' }))
    const nota = (await pantalla.findByText('Autorización retirada. Ya no calculamos ni avisamos por los insumos de María.')).closest('[data-aviso]')
    await waitFor(() => expect(nota).toHaveFocus())
    expect(pedidas.some((p) => p.linea === `POST /v1/personas-cuidadas/${MARIA.id}/consentimientos/consumo/retiro`)).toBe(true)
    expect(contexto.fijar).not.toHaveBeenCalledWith(expect.objectContaining({ ficha: null }))
  })

  it('409 ya-retirada: cierra, vuelve a pedir el estado y avisa que otra persona la retiró', async () => {
    let retirada = false
    const pedidas = api((p) => {
      if (p.linea.endsWith('/personas-cuidadas')) return { status: 200, cuerpo: [MARIA] }
      if (p.linea.endsWith('/consentimientos'))
        return { status: 200, cuerpo: { autorizaciones: [retirada ? vista('plan_cuidado', 'retirada', RETIRADA) : vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')] } }
      if (p.linea.endsWith('/retiro')) return (retirada = true), problema(409, 'ya-retirada')
      return { status: 200, cuerpo: { items: [], siguiente_cursor: null } }
    })
    const pantalla = abrirGrupo('admin')
    await userEvent.click(await pantalla.findByRole('button', { name: 'Retirar la autorización de la ficha de María' }))
    await userEvent.click(within(dialogo()).getByRole('button', { name: 'Retirar la autorización' }))
    const nota = (await pantalla.findByText('Otra persona de tu grupo ya retiró esta autorización.')).closest('[data-aviso]')
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(nota).toHaveFocus())
    expect(within(bloque('Permiso para guardar su ficha')).getByText(/^Autorización retirada el/)).toBeVisible()
    expect(pedidas.filter((p) => p.linea.endsWith('/consentimientos'))).toHaveLength(2)
    expect(pantalla.queryByText(/TEXTO DE LA API/)).toBeNull()
  })

  it('sin conexión: el error en la región del diálogo, todo sigue como estaba y se puede reintentar', async () => {
    let veces = 0
    apiGrupo(
      { [MARIA.id]: [vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')] },
      { retiro: () => (++veces === 1 ? RED : { status: 200, cuerpo: { autorizacion: vista('plan_cuidado', 'retirada', RETIRADA), enlaces_cortados: 2 } }) },
    )
    const pantalla = abrirGrupo('admin')
    await userEvent.click(await pantalla.findByRole('button', { name: 'Retirar la autorización de la ficha de María' }))
    const d = dialogo()
    const region = within(d).getByRole('alert')
    expect(region).toBeEmptyDOMElement()
    const confirmar = within(d).getByRole('button', { name: 'Retirar la autorización' })
    await userEvent.click(confirmar)
    await waitFor(() =>
      expect(region).toHaveTextContent('No pudimos retirar la autorización. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.'),
    )
    expect(d).toHaveAttribute('open')
    expect(confirmar).not.toHaveAttribute('aria-busy')
    expect(confirmar).toHaveFocus()
    expect(within(bloque('Permiso para guardar su ficha')).getByText(/^Autorizada el/)).toBeVisible()
    await userEvent.click(confirmar)
    expect(await pantalla.findByText('Autorización retirada. Cortamos 2 enlaces.')).toBeVisible()
  })

  it('«No retirar» y Esc cierran sin pedir nada, y el foco vuelve al botón que abrió', async () => {
    const pedidas = apiGrupo({ [MARIA.id]: [vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')] })
    const pantalla = abrirGrupo('admin')
    const abrir = await pantalla.findByRole('button', { name: 'Retirar la autorización de los insumos de María' })
    await userEvent.click(abrir)
    await userEvent.click(within(dialogo()).getByRole('button', { name: 'No retirar' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(abrir).toHaveFocus())

    await userEvent.click(abrir)
    fireEvent(dialogo(), new Event('cancel', { cancelable: true }))
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(abrir).toHaveFocus())
    expect(pedidas.some((p) => p.linea.endsWith('/retiro'))).toBe(false)
  })
})

// ---------------------------------------------------------------- 5 volver a autorizar

describe('Volver a autorizar', () => {
  it('desde Grupo familiar elige a la persona en memoria y va a la subruta, sin su id en la URL', async () => {
    apiGrupo({ [MARIA.id]: [vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')], [PEDRO.id]: [vista('plan_cuidado', 'retirada', RETIRADA), vista('consumo', 'vigente')] }, { personas: [MARIA, PEDRO] })
    const pantalla = abrirGrupo('admin')
    await userEvent.click(await pantalla.findByRole('button', { name: 'Volver a autorizar la ficha de Pedro' }))
    expect(window.location.pathname).toBe('/grupo/autorizar-ficha')
    expect(window.location.href).not.toContain(PEDRO.id)
    expect(contexto.fijar).toHaveBeenCalledWith({
      personaId: PEDRO.id,
      ficha: null,
      autorizacion: null,
      reautorizar: { personaId: PEDRO.id, finalidad: 'plan_cuidado', vista: vista('plan_cuidado', 'retirada', RETIRADA) },
    })
  })

  function abrirAutorizar(pantalla: 'ficha' | 'insumos', v: AutorizacionVista | null, atender: Atender) {
    const pedidas = api(atender)
    contexto = familiaFalsa({
      grupo: { id: GRUPO_ID, nombre: 'Familia Soto', rol: 'admin' },
      rol: 'admin',
      persona: MARIA,
      personaId: MARIA.id,
      reautorizar: { personaId: MARIA.id, finalidad: pantalla === 'ficha' ? 'plan_cuidado' : 'consumo', vista: v },
    } as never)
    window.history.replaceState(null, '', pantalla === 'ficha' ? '/grupo/autorizar-ficha' : '/grupo/autorizar-insumos')
    render(
      <>
        <RegionesVivas />
        {pantalla === 'ficha' ? <AutorizarFicha /> : <AutorizarInsumos />}
      </>,
    )
    return pedidas
  }

  it('la ficha dentro de los 90 días: lo escrito vuelve, ninguna calidad elegida y el POST con plan_cuidado', async () => {
    const pedidas = abrirAutorizar('ficha', vista('plan_cuidado', 'retirada', RETIRADA), () => ({ status: 201, cuerpo: {} }))
    expect(screen.getByRole('heading', { level: 1, name: 'Permiso para guardar su ficha' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Volver a Grupo familiar' })).toBeVisible()
    expect(screen.getByText('Al autorizar de nuevo, vuelve lo que estaba escrito. Los enlaces que se cortaron no vuelven a abrir.')).toBeVisible()
    expect(screen.getAllByRole('radio').every((r) => !(r as HTMLInputElement).checked)).toBe(true)
    // Sin ninguna lectura: la vista llegó desde Grupo familiar.
    expect(pedidas).toEqual([])

    const boton = screen.getByRole('button', { name: 'Acepto y vuelvo a autorizar' })
    await userEvent.click(boton)
    expect(await screen.findByText('Elige quién da la autorización.')).toBeVisible()
    await userEvent.click(screen.getByRole('radio', { name: /María lo autoriza y yo lo registro/ }))
    await userEvent.click(boton)
    await waitFor(() => expect(window.location.pathname).toBe('/grupo'))
    expect(pedidas).toEqual([
      { linea: `POST /v1/personas-cuidadas/${MARIA.id}/consentimientos`, params: undefined, cuerpo: { finalidad: 'plan_cuidado', calidad_otorgante: 'titular', referencia_documento: null, aviso: null } },
    ])
    expect(contexto.fijar).toHaveBeenCalledWith({
      ficha: null,
      autorizacion: null,
      reautorizar: null,
      aviso: { titulo: 'Autorización registrada. Ya puedes ver y cambiar la ficha de María.', tono: 'ok' },
    })
  })

  it('la ficha después de los 90 días (P8) empieza en blanco, y lo dice antes y después', async () => {
    abrirAutorizar('ficha', vista('plan_cuidado', 'borrada', BORRADA), () => ({ status: 201, cuerpo: {} }))
    const frase = parrafo('Lo escrito antes se borró el 29/09/2026. La ficha empieza en blanco.')
    expect(frase).toBeVisible()
    // 3.4 (revisión del 07-11): el punto va pegado a la fecha, en el mismo `cifras`.
    expect(frase.querySelector('.cifras')).toHaveTextContent(/^29\/09\/2026\.$/)
    await userEvent.click(screen.getByRole('radio', { name: /Cuido a esta persona/ }))
    // Revisión del 07-11 (P2): en modo angosto el ícono del aviso va en la línea del título.
    const aviso = screen.getByRole('heading', { level: 2, name: 'Aviso: tu autorización tiene un límite' })
    expect(aviso).toHaveClass('angosto:block')
    expect(aviso.querySelector('svg')).toHaveClass('angosto:inline')
    await userEvent.click(screen.getByRole('checkbox', { name: 'Leí el aviso y lo acepto' }))
    await userEvent.click(screen.getByRole('button', { name: 'Acepto y vuelvo a autorizar' }))
    await waitFor(() => expect(window.location.pathname).toBe('/grupo'))
    expect(contexto.fijar).toHaveBeenCalledWith(expect.objectContaining({ aviso: { titulo: 'Autorización registrada. La ficha de María empieza en blanco.', tono: 'ok' } }))
  })

  it('desde la ficha, sin la vista, la pide; 409 vuelve con «otra persona ya volvió a autorizar»; 422 avisa', async () => {
    let post = 0
    const pedidas = abrirAutorizar('ficha', null, (p) => {
      if (p.linea.startsWith('GET')) return { status: 200, cuerpo: { autorizaciones: [vista('plan_cuidado', 'retirada', RETIRADA), vista('consumo', 'vigente')] } }
      return ++post === 1 ? { status: 422, cuerpo: { type: '/errores/validacion', status: 422, errores: [{ campo: 'calidad_otorgante', tipo: 'enum', mensaje: 'NO' }] } } : problema(409, 'autorizacion-vigente')
    })
    expect(await screen.findByText('Al autorizar de nuevo, vuelve lo que estaba escrito. Los enlaces que se cortaron no vuelven a abrir.')).toBeVisible()
    expect(pedidas[0].linea).toBe(`GET /v1/personas-cuidadas/${MARIA.id}/consentimientos`)
    await userEvent.click(screen.getByRole('radio', { name: /María lo autoriza/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Acepto y vuelvo a autorizar' }))
    expect(await screen.findByText('No pudimos guardar la autorización. Revisa lo que elegiste y vuelve a intentarlo.')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Acepto y vuelvo a autorizar' }))
    await waitFor(() => expect(window.location.pathname).toBe('/grupo'))
    expect(contexto.fijar).toHaveBeenCalledWith(expect.objectContaining({ aviso: { titulo: 'Otra persona de tu grupo ya volvió a autorizar.', tono: 'rocio' } }))
  })

  it.each([
    ['ficha', 'Permiso para guardar su ficha', 'plan_cuidado'],
    ['insumos', 'Antes de calcular, un permiso', 'consumo'],
  ] as const)('desde el aviso, la %s carga con su propio h1, que conserva el foco al llegar la vista (revisión P2)', async (pantalla, titulo, finalidad) => {
    const respuesta = diferida()
    abrirAutorizar(pantalla, null, () => respuesta.promesa)
    const h1 = screen.getByRole('heading', { level: 1 })
    expect(h1).toHaveAccessibleName(titulo)
    expect(screen.queryByRole('heading', { name: 'Grupo familiar' })).toBeNull()
    h1.focus()
    const otra = finalidad === 'plan_cuidado' ? 'consumo' : 'plan_cuidado'
    await act(async () =>
      respuesta.soltar({
        status: 200,
        cuerpo: { autorizaciones: finalidad === 'plan_cuidado' ? [vista(finalidad, 'retirada', RETIRADA), vista(otra, 'vigente')] : [vista(otra, 'vigente'), vista(finalidad, 'retirada', RETIRADA)] },
      }),
    )
    expect(await screen.findByRole('radio', { name: /María lo autoriza/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toBe(h1)
    expect(h1).toHaveFocus()
  })

  it('si la ficha ya no está retirada, vuelve a Grupo familiar', async () => {
    abrirAutorizar('ficha', null, () => ({ status: 200, cuerpo: { autorizaciones: [vista('plan_cuidado', 'vigente'), vista('consumo', 'vigente')] } }))
    await waitFor(() => expect(window.location.pathname).toBe('/grupo'))
  })

  it.each([
    ['retirada', RETIRADA, 'Si vuelves a dar el permiso antes del 04/02/2027, vuelve lo que estaba anotado.', 'Permiso guardado. Volvió lo que estaba anotado.'],
    ['borrada', BORRADA, 'Lo anotado antes se borró el 29/09/2026. Hay que anotar los insumos de nuevo.', 'Permiso guardado. Ahora anota el primer insumo.'],
  ] as const)('los insumos en %s: la frase de estado, el permiso de MATU-36 y la confirmación', async (estado, fechas, frase, hecho) => {
    const pedidas = abrirAutorizar('insumos', vista('consumo', estado, fechas), () => ({ status: 201, cuerpo: {} }))
    expect(screen.getByRole('heading', { level: 1, name: 'Antes de calcular, un permiso' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Volver a Grupo familiar' })).toBeVisible()
    expect(parrafo(frase)).toBeVisible()
    await userEvent.click(screen.getByRole('radio', { name: /María lo autoriza/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Acepto y continúo' }))
    await waitFor(() => expect(window.location.pathname).toBe('/grupo'))
    expect(pedidas.map((p) => p.cuerpo)).toEqual([{ finalidad: 'consumo', calidad_otorgante: 'titular', referencia_documento: null, aviso: null }])
    expect(contexto.fijar).toHaveBeenCalledWith({ reautorizar: null, aviso: { titulo: hecho, tono: 'ok' } })
  })
})

// ---------------------------------------------------------------- 4.5 la ficha y Enlaces después del retiro

describe('Después de retirar la ficha', () => {
  function abrirFicha(rol: Rol) {
    contexto = familiaFalsa({ rol, persona: MARIA, personaId: MARIA.id, grupo: { id: GRUPO_ID, nombre: 'Familia Soto', rol, puede_ver_plan: true } } as never)
    render(<Bloqueada bloqueo="sin-consentimiento" />)
  }

  it.each(['admin', 'cuidador'] as const)('el %s ve «La puedes volver a autorizar desde Grupo familiar.» y el botón secundario', async (rol) => {
    abrirFicha(rol)
    expect(screen.getByText('Falta la autorización para usar la ficha de María.')).toBeVisible()
    expect(screen.getByText(/^Sin ella no podemos/)).toHaveTextContent('Sin ella no podemos guardar ni mostrar la ficha. La puedes volver a autorizar desde Grupo familiar.')
    const boton = screen.getByRole('button', { name: 'Volver a autorizar' })
    expect(boton).toHaveClass('ring-turquesa/70')
    await userEvent.click(boton)
    expect(contexto.fijar).toHaveBeenCalledWith({ reautorizar: { personaId: MARIA.id, finalidad: 'plan_cuidado', vista: null } })
    expect(window.location.pathname).toBe('/grupo/autorizar-ficha')
  })

  it('el pagador ve el texto de siempre, sin botón', () => {
    abrirFicha('pagador')
    expect(screen.getByText(/^Sin ella no podemos/)).toHaveTextContent('Sin ella no podemos guardar ni mostrar la ficha. Pídele a quien administra el grupo que la registre.')
    expect(screen.queryByRole('button')).toBeNull()
  })

  function abrirEnlaces(rol: Rol, autorizacion: 'sin-consentimiento' | 'revision-vencida', estado: 'revocado' | 'vigente') {
    const a = { ...acceso(1), estado, revocado_en: estado === 'revocado' ? '2026-11-06T15:00:00Z' : null }
    api((p) => {
      if (p.linea.endsWith('/plan/accesos-relevo')) return { status: 200, cuerpo: { items: p.params?.estado === 'vigente' ? (estado === 'vigente' ? [a] : []) : [a], siguiente_cursor: null } }
      if (p.linea.endsWith('/plan/ficha')) return problema(403, autorizacion)
      return { status: 200, cuerpo: { items: [], siguiente_cursor: null } }
    })
    contexto = familiaFalsa({ rol, persona: MARIA, personaId: MARIA.id, autorizacion, grupo: { id: GRUPO_ID, nombre: 'Familia Soto', rol, puede_ver_plan: true } } as never)
    render(
      <>
        <RegionesVivas />
        <Enlaces />
      </>,
    )
  }

  /**
   * Revisión del 07-11 (P1): a 320 px con el texto al 200 % la nota se salía 3 px. En modo angosto
   * el ícono va en la primera línea del título y el de al lado se oculta, como en `MensajeError`.
   */
  function iconoEnLaLineaDelTitulo(titulo: string) {
    const p = screen.getByText(titulo)
    const enLinea = p.querySelector(':scope > span > svg')?.parentElement
    expect(enLinea).toHaveClass('hidden', 'angosto:inline-flex')
    const nota = p.closest('.flex.max-w-prose')!
    expect(nota.querySelector(':scope > span.contents')).toHaveClass('angosto:hidden')
  }

  it('Enlaces con la autorización retirada: la nota de corte, sin «En pausa» ni nota atenta, y el enlace a los permisos', async () => {
    abrirEnlaces('admin', 'sin-consentimiento', 'revocado')
    expect(await screen.findByText('Se retiró la autorización de la ficha.')).toBeVisible()
    expect(screen.getByText('Los enlaces se cortaron y no vuelven a abrir.')).toBeVisible()
    expect(screen.queryByText('En pausa')).toBeNull()
    expect(screen.queryByText(/Mientras no se renueve/)).toBeNull()
    expect(document.querySelector('.bg-atenta-fondo')).toBeNull()
    expect(screen.getByText('Cortado')).toBeVisible()
    iconoEnLaLineaDelTitulo('Se retiró la autorización de la ficha.')
    await userEvent.click(screen.getByRole('button', { name: 'Ver los permisos en Grupo familiar' }))
    expect(window.location.pathname).toBe('/grupo')
  })

  it('el pagador ve la nota de corte sin el enlace a los permisos', async () => {
    abrirEnlaces('pagador', 'sin-consentimiento', 'revocado')
    expect(await screen.findByText('Se retiró la autorización de la ficha.')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Ver los permisos en Grupo familiar' })).toBeNull()
  })

  it('Enlaces con la autorización por renovar: la pausa de 9.1 y «En pausa» en el enlace vigente', async () => {
    abrirEnlaces('admin', 'revision-vencida', 'vigente')
    expect(
      await screen.findByText('Mientras no se renueve la autorización, ningún enlace abre. Cuando se renueve, vuelven a abrir los que no hayan vencido.'),
    ).toBeVisible()
    expect(screen.getByText('En pausa')).toBeVisible()
    expect(screen.queryByText('Se retiró la autorización de la ficha.')).toBeNull()
    iconoEnLaLineaDelTitulo('Mientras no se renueve la autorización, ningún enlace abre. Cuando se renueve, vuelven a abrir los que no hayan vencido.')
  })
})

// ---------------------------------------------------------------- 2.1 la barra

describe('La barra de secciones', () => {
  it('suma Grupo familiar como cuarta sección, para todos los roles, marcada en sus subrutas', () => {
    window.history.replaceState(null, '', '/grupo/autorizar-insumos')
    contexto = familiaFalsa({ rol: 'observador', persona: MARIA, personas: [MARIA], grupos: [], grupo: { id: GRUPO_ID, nombre: 'Familia Soto', rol: 'observador' } } as never)
    render(
      <ShellFamilia>
        <p>contenido</p>
      </ShellFamilia>,
    )
    const barra = within(screen.getByRole('navigation', { name: 'Secciones' }))
    const enlaces = barra.getAllByRole('link')
    expect(enlaces.map((a) => a.getAttribute('href'))).toEqual(['/insumos', '/grupo'])
    expect(barra.getByRole('link', { name: /Grupo familiar/ })).toHaveAttribute('aria-current', 'page')
    expect(barra.getByText('Grupo')).toBeInTheDocument()
  })

  it('con las cuatro secciones, el teléfono las pone en cuatro columnas', () => {
    window.history.replaceState(null, '', '/grupo')
    contexto = familiaFalsa({ rol: 'admin', persona: MARIA, personas: [MARIA], grupos: [], grupo: { id: GRUPO_ID, nombre: 'Familia Soto', rol: 'admin' } } as never)
    render(
      <ShellFamilia>
        <p>contenido</p>
      </ShellFamilia>,
    )
    const barra = screen.getByRole('navigation', { name: 'Secciones' })
    expect(within(barra).getAllByRole('link').map((a) => a.getAttribute('href'))).toEqual(['/ficha', '/insumos', '/compartir', '/grupo'])
    expect(barra.querySelector('ul')).toHaveClass('telefono:grid-cols-4')
  })
})

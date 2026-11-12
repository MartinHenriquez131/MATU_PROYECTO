// MATU-42 y MATU-53: quiénes forman el grupo, las invitaciones sin usar, cambiar el rol, el permiso del
// pagador, sacar y salir (especificación docs/diseno/matu-53-invitar-grupo.md v1.1, secciones 5 a 7).
// Sin interfaz optimista, `If-Match` con el etag, el 412 a la vista, los 409 `ultimo-admin` y
// `unica-persona`, los 404, el foco después del render y el aviso de D-42-9. Solo datos sintéticos.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AutorizacionVista, InvitacionPendiente, Miembro, Rol } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { GrupoFamiliar } from '../src/familia/Grupo'
import type { RespuestaFalsa } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'
import { miembroDePrueba } from './miembrosFalsos'

const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g1'
const MARIA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María' }

const CARMEN = miembroDePrueba({ id: 'm-carmen', nombre: 'Carmen Soto', rol: 'admin', eres_tu: true, unido_en: '2026-11-02T15:00:00Z', enlaces_vigentes: 1 })
const TOMAS = miembroDePrueba({ id: 'm-tomas', nombre: 'Tomás Soto', rol: 'admin', eres_tu: false, unido_en: '2026-11-03T15:00:00Z', enlaces_vigentes: 0 })
const RODRIGO = miembroDePrueba({ id: 'm-rodrigo', nombre: 'Rodrigo Soto', rol: 'pagador', puede_ver_plan: false, eres_tu: false, unido_en: '2026-11-08T15:00:00Z', enlaces_vigentes: 0 })
const ROSA = miembroDePrueba({ id: 'm-rosa', nombre: 'Rosa Pérez', rol: 'cuidador', eres_tu: false, unido_en: '2026-11-10T15:00:00Z', enlaces_vigentes: 2, etag: '"v3"' })
const INVITACION: InvitacionPendiente = {
  id: 'inv-1',
  rol: 'observador',
  estado: 'pendiente',
  creada_en: '2026-11-11T15:00:00Z',
  expira_en: '2026-11-20T00:30:00Z',
  invitada_por: { nombre: 'Carmen', autor_activo: true, eres_tu: true },
}
const vigente = (finalidad: 'plan_cuidado' | 'consumo', extra: Partial<AutorizacionVista> = {}): AutorizacionVista => ({
  finalidad,
  estado: 'vigente',
  id: `a-${finalidad}`,
  otorgado_en: '2026-11-04T15:00:00Z',
  revision_vence_en: null,
  revocado_en: null,
  borrado_en: null,
  borrada: false,
  ...extra,
})

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

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

interface Pedida {
  linea: string
  cuerpo?: Record<string, unknown>
  ifMatch: unknown
  grupo: unknown
}
type Atender = (p: Pedida) => RespuestaFalsa | null | Promise<RespuestaFalsa | null>

const problema = (status: number, tipo: string, extra: Record<string, unknown> = {}): RespuestaFalsa => ({
  status,
  cuerpo: { type: `/errores/${tipo}`, title: 'TEXTO DE LA API QUE NO SE MUESTRA', status, ...extra },
})
const RED: RespuestaFalsa = { status: 503, cuerpo: { type: '/errores/servicio-no-disponible', status: 503 } }

/**
 * La API de Grupo familiar: María con sus dos autorizaciones, los miembros y las invitaciones. `atender`
 * responde primero; si devuelve `null`, responde lo de siempre.
 */
function api({
  miembros = [CARMEN, TOMAS, RODRIGO, ROSA],
  invitaciones = [INVITACION],
  autorizaciones = [vigente('plan_cuidado'), vigente('consumo')],
  rolPropio = 'admin' as Rol,
  atender = () => null,
}: { miembros?: Miembro[]; invitaciones?: InvitacionPendiente[]; autorizaciones?: AutorizacionVista[]; rolPropio?: Rol; atender?: Atender } = {}) {
  const pedidas: Pedida[] = []
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const p: Pedida = {
      linea: `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`,
      cuerpo: typeof config.data === 'string' && config.data ? JSON.parse(config.data) : undefined,
      ifMatch: config.headers?.get?.('If-Match'),
      grupo: config.headers?.get?.('X-Grupo-Id'),
    }
    pedidas.push(p)
    const propia = await atender(p)
    const r: RespuestaFalsa =
      propia ??
      (p.linea === `GET /v1/grupos/${GRUPO_ID}/personas-cuidadas`
        ? { status: 200, cuerpo: [MARIA] }
        : p.linea.endsWith('/consentimientos')
          ? { status: 200, cuerpo: { autorizaciones } }
          : p.linea.endsWith('/plan/accesos-relevo')
            ? { status: 200, cuerpo: { items: [], siguiente_cursor: null } }
            : p.linea === `GET /v1/grupos/${GRUPO_ID}/miembros`
              ? { status: 200, cuerpo: { miembros } }
              : p.linea === `GET /v1/grupos/${GRUPO_ID}/invitaciones`
                ? { status: 200, cuerpo: { invitaciones } }
                : p.linea === 'GET /v1/grupos'
                  ? { status: 200, cuerpo: [{ id: GRUPO_ID, nombre: 'Familia Soto', rol: rolPropio, puede_ver_plan: false }] }
                  : problema(404, 'no-encontrado'))
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return pedidas
}

function abrir(rol: Rol = 'admin', cambios: Record<string, unknown> = {}) {
  contexto = familiaFalsa({
    grupo: { id: GRUPO_ID, nombre: 'Familia Soto', rol, puede_ver_plan: false },
    rol,
    persona: MARIA,
    personaId: MARIA.id,
    personas: [MARIA],
    reautorizar: null,
    aviso: null,
    capa3: true,
    conocerCapa3: vi.fn(),
    ...cambios,
  } as never)
  return render(
    <>
      <RegionesVivas />
      <GrupoFamiliar />
    </>,
  )
}

const lista = () => screen.getByRole('region', { name: 'Quiénes forman el grupo' })
/** La fila de una persona: la que empieza con su nombre. */
const fila = (nombre: string) => {
  const li = within(lista())
    .getAllByRole('listitem')
    .find((x) => x.querySelector('p')?.textContent?.startsWith(nombre))
  if (!li) throw new Error(`Sin fila para ${nombre}`)
  return li
}
const dialogo = () => screen.getByRole('dialog')
const enDialogo = () => within(dialogo())

// ---------------------------------------------------------------- 5 la lista

describe('Quiénes forman el grupo', () => {
  it('admin: la lista con el rol en palabra, «(tú)», la fecha, el permiso del pagador y las acciones con su nombre', async () => {
    const pedidas = api()
    abrir('admin')
    expect(await screen.findByText('Rosa Pérez')).toBeVisible()
    expect(screen.getByText('Quiénes forman Familia Soto, a quién cuidan y qué permisos dieron.')).toBeVisible()
    const carmen = within(fila('Carmen Soto'))
    expect(carmen.getByText('(tú)')).toHaveClass('font-normal')
    expect(carmen.getByText('Administra el grupo')).toBeVisible()
    expect(carmen.getByText(/^Se unió el/)).toHaveTextContent('Se unió el 02/11/2026.')
    // Hay otra persona que administra: «Cambiar tu rol», y nunca «Sacar del grupo» en la fila propia.
    expect(carmen.getByRole('button', { name: 'Cambiar tu rol' })).toBeVisible()
    expect(carmen.queryByRole('button', { name: /Sacar/ })).toBeNull()

    const rodrigo = within(fila('Rodrigo Soto'))
    expect(rodrigo.getByText('Paga')).toBeVisible()
    expect(rodrigo.getByText('No ve la ficha')).toBeVisible()
    expect(rodrigo.getByRole('button', { name: 'Cambiar lo que puede hacer Rodrigo Soto' })).toHaveTextContent('Cambiar lo que puede hacer')
    expect(rodrigo.getByRole('button', { name: 'Dejar que vea la ficha a Rodrigo Soto' })).toBeVisible()
    const sacar = rodrigo.getByRole('button', { name: 'Sacar del grupo a Rodrigo Soto' })
    expect(sacar).toHaveTextContent('Sacar del grupo')
    expect(sacar).toHaveClass('text-pronto')
    expect(within(fila('Rosa Pérez')).getByText('Cuida')).toBeVisible()
    expect(within(fila('Rosa Pérez')).queryByText(/ve la ficha/)).toBeNull()

    // 10.1: el único turquesa macizo es «Invitar a alguien».
    const macizos = [...document.querySelectorAll('.bg-turquesa')]
    expect(macizos.map((b) => b.textContent)).toEqual(['Invitar a alguien'])
    await userEvent.click(macizos[0] as HTMLElement)
    expect(window.location.pathname).toBe('/grupo/invitar')

    // 10.10: nunca un correo ni un celular.
    expect(document.body.textContent).not.toMatch(/@|\+56/)
    expect(pedidas.find((p) => p.linea.endsWith('/miembros'))?.grupo).toBe(GRUPO_ID)
  })

  it('las invitaciones sin usar: el rol, el vencimiento con la hora y quién la creó; la de alguien que ya no está', async () => {
    api({ invitaciones: [INVITACION, { ...INVITACION, id: 'inv-2', rol: 'cuidador', invitada_por: { nombre: null, autor_activo: false, eres_tu: false } }] })
    abrir('admin')
    const bloque = within(await screen.findByRole('region', { name: 'Invitaciones sin usar' }))
    expect(bloque.getByText(/^Se informa ·/)).toHaveTextContent('Se informa · vence el 19/11/2026 a las 21:30.')
    expect(bloque.getByText('La creó Carmen.')).toBeVisible()
    expect(bloque.getByText('La creó alguien que ya no está en el grupo.')).toBeVisible()
    expect(bloque.getAllByRole('button', { name: 'Anular la invitación' })[0]).toHaveAccessibleDescription('Se informa · vence el 19/11/2026 a las 21:30.')
  })

  it('sin invitaciones, el bloque no aparece', async () => {
    api({ invitaciones: [] })
    abrir('admin')
    await screen.findByText('Rosa Pérez')
    expect(screen.queryByRole('region', { name: 'Invitaciones sin usar' })).toBeNull()
  })

  it.each(['cuidador', 'observador'] as const)('el %s ve la lista sin botones, sin invitar ni invitaciones, y quién puede', async (rol) => {
    const pedidas = api({ miembros: [CARMEN, { ...ROSA, eres_tu: rol === 'cuidador' }, RODRIGO].map((m) => ({ ...m, eres_tu: m === CARMEN ? false : m.eres_tu })) })
    abrir(rol)
    expect(await screen.findByText('Solo quien administra el grupo invita, cambia los roles y saca a alguien.')).toBeVisible()
    expect(within(lista()).queryByRole('button')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Invitar a alguien' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Invitaciones sin usar' })).toBeNull()
    // C9: el permiso del pagador solo lo ve el pagador en su fila (y quien administra).
    expect(screen.queryByText('No ve la ficha')).toBeNull()
    expect(pedidas.some((p) => p.linea.endsWith('/invitaciones'))).toBe(false)
    expect(document.querySelector('.bg-turquesa')).toBeNull()
  })

  it('el pagador ve «Puede ver la ficha» con el ícono, solo en su fila', async () => {
    api({ miembros: [{ ...CARMEN, eres_tu: false }, { ...RODRIGO, eres_tu: true, puede_ver_plan: true }] })
    abrir('pagador')
    const propia = within(await waitFor(() => fila('Rodrigo Soto')))
    expect(propia.getByText('Puede ver la ficha')).toBeVisible()
    expect(propia.getByText('Puede ver la ficha').querySelector('svg')).toHaveClass('text-ok')
  })

  it('la única persona que administra: la frase en su fila y en «Salir del grupo», sin «Cambiar tu rol» ni el botón de salir', async () => {
    api({ miembros: [CARMEN, RODRIGO, ROSA] })
    abrir('admin')
    const carmen = within(await waitFor(() => fila('Carmen Soto')))
    expect(carmen.getByText('Eres la única persona que administra el grupo. Para dejar ese rol, primero dáselo a otra persona.')).toHaveClass('text-tenue')
    expect(carmen.queryByRole('button')).toBeNull()
    const salir = within(screen.getByRole('region', { name: 'Salir del grupo' }))
    expect(salir.getByText('Eres la única persona que administra Familia Soto. Para salir, primero da ese rol a otra persona.')).toBeVisible()
    expect(salir.queryByRole('button')).toBeNull()
  })

  it('sola en el grupo: «Por ahora solo estás tú…» y la frase que lleva a «Borrar sus datos»', async () => {
    api({ miembros: [CARMEN], invitaciones: [] })
    abrir('admin')
    expect(await screen.findByText('Por ahora solo estás tú. Invita a quien cuida contigo.')).toBeVisible()
    const salir = within(screen.getByRole('region', { name: 'Salir del grupo' }))
    expect(
      salir.getByText('Eres la única persona de Familia Soto, así que no puedes salir. Si ya no usan MATU para cuidar a María, puedes borrar sus datos en «Borrar sus datos», más arriba.'),
    ).toBeVisible()
  })

  it('si la lista falla: el error con «Volver a intentar», y las personas cuidadas se ven igual', async () => {
    let falla = true
    api({ atender: (p) => (p.linea.endsWith('/miembros') && falla ? RED : null) })
    abrir('admin')
    expect(await screen.findByText('No pudimos traer quiénes forman el grupo. Revisa tu conexión e inténtalo de nuevo.')).toBeVisible()
    expect(await screen.findByRole('region', { name: 'Permiso para guardar su ficha' })).toBeVisible()
    falla = false
    await userEvent.click(screen.getByRole('button', { name: 'Volver a intentar' }))
    expect(await screen.findByText('Rosa Pérez')).toBeVisible()
  })

  it('404 al pedir la lista (me sacaron): vuelve a pedir los grupos y sigue la regla de la app', async () => {
    api({ atender: (p) => (p.linea.endsWith('/miembros') ? problema(404, 'no-encontrado') : null) })
    abrir('admin')
    await waitFor(() => expect(contexto.alEntrar).toHaveBeenCalled())
    await waitFor(() => expect(window.location.pathname).toBe('/'))
  })
})

// ---------------------------------------------------------------- 6 cambiar el rol

describe('Cambiar el rol', () => {
  async function abrirCambio(nombre: string) {
    await userEvent.click(await screen.findByRole('button', { name: `Cambiar lo que puede hacer ${nombre}` }))
    return dialogo()
  }

  it('el diálogo: foco en el título, el rol actual con «Ahora» y «Guardar el cambio» deshabilitado con su razón', async () => {
    api()
    abrir('admin')
    await abrirCambio('Rosa Pérez')
    const titulo = enDialogo().getByRole('heading', { level: 2, name: 'Cambiar lo que puede hacer Rosa Pérez' })
    await waitFor(() => expect(titulo).toHaveFocus())
    expect(enDialogo().getByRole('radio', { name: 'Cuida' })).toBeChecked()
    expect(enDialogo().getByRole('radio', { name: 'Cuida' })).toHaveAccessibleDescription(expect.stringContaining('Ahora'))
    const guardar = enDialogo().getByRole('button', { name: 'Guardar el cambio' })
    expect(guardar).toHaveAttribute('aria-disabled', 'true')
    expect(guardar).toHaveAccessibleDescription('Elige otro rol para guardar.')
  })

  it('pierde la ficha: la nota con los enlaces que se cortan, el botón pronto, If-Match y, al guardar, la nota bajo la fila con el foco', async () => {
    const pedidas = api({
      atender: (p) =>
        p.linea === `PATCH /v1/grupos/${GRUPO_ID}/miembros/m-rosa`
          ? { status: 200, cuerpo: { miembro: { ...ROSA, rol: 'pagador', puede_ver_plan: false, enlaces_vigentes: 0, etag: '"v4"' }, enlaces_cortados: 2 }, cabeceras: { etag: '"v4"' } }
          : null,
    })
    abrir('admin')
    await abrirCambio('Rosa Pérez')
    await userEvent.click(enDialogo().getByRole('radio', { name: 'Paga' }))
    const nota = enDialogo().getByText('Rosa Pérez dejará de ver la ficha. Se cortan 2 enlaces de relevo que compartió.')
    expect(nota.closest('[aria-live="polite"]')).not.toBeNull()
    expect(enDialogo().getByText('Como paga, no verá la ficha hasta que le des permiso.')).toBeVisible()
    const guardar = enDialogo().getByRole('button', { name: 'Guardar el cambio' })
    expect(guardar).toHaveClass('bg-pronto')
    expect(guardar).not.toHaveClass('bg-turquesa')
    await userEvent.click(guardar)
    const hecho = await screen.findByText('Ahora Rosa Pérez paga. Cortamos 2 enlaces.')
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(hecho.closest('[data-aviso]')).toHaveFocus())
    expect(hecho.closest('li')).toBe(fila('Rosa Pérez'))
    expect(within(fila('Rosa Pérez')).getByText('Paga')).toBeVisible()
    const patch = pedidas.find((p) => p.linea.startsWith('PATCH'))!
    expect(patch.ifMatch).toBe('"v3"')
    expect(patch.cuerpo).toEqual({ rol: 'pagador' })
    expect(escrituras).toEqual([])
  })

  it('sin interfaz optimista: mientras guarda, la fila no cambia y dice «Guardando el cambio…»', async () => {
    let soltar: () => void = () => {}
    api({
      atender: async (p): Promise<RespuestaFalsa | null> => {
        if (!p.linea.startsWith('PATCH')) return null
        await new Promise<void>((r) => (soltar = r))
        return { status: 200, cuerpo: { miembro: { ...ROSA, rol: 'observador' }, enlaces_cortados: 0 } }
      },
    })
    abrir('admin')
    await abrirCambio('Rosa Pérez')
    await userEvent.click(enDialogo().getByRole('radio', { name: 'Se informa' }))
    await userEvent.click(enDialogo().getByRole('button', { name: 'Guardar el cambio' }))
    expect(enDialogo().getByRole('button', { name: /Guardar el cambio/ })).toHaveAttribute('aria-busy', 'true')
    expect(within(fila('Rosa Pérez')).getByText('Cuida')).toBeVisible()
    soltar()
    expect(await screen.findByText('Ahora Rosa Pérez se informa.')).toBeVisible()
  })

  it('pasa a «Administra el grupo»: la advertencia con el nombre y el botón principal', async () => {
    api()
    abrir('admin')
    await abrirCambio('Rosa Pérez')
    await userEvent.click(enDialogo().getByRole('radio', { name: 'Administra el grupo' }))
    expect(enDialogo().getByText('Rosa Pérez podrá invitar, cambiar permisos y sacar a otras personas, también a ti.')).toBeVisible()
    expect(enDialogo().getByRole('button', { name: 'Guardar el cambio' })).toHaveClass('bg-turquesa')
  })

  it('412: el diálogo se queda, «Ahora» va al rol vigente y lo elegido se pierde', async () => {
    api({ atender: (p) => (p.linea.startsWith('PATCH') ? problema(412, 'version-desactualizada', { actual: { ...ROSA, rol: 'observador', etag: '"v4"' } }) : null) })
    abrir('admin')
    await abrirCambio('Rosa Pérez')
    await userEvent.click(enDialogo().getByRole('radio', { name: 'Paga' }))
    await userEvent.click(enDialogo().getByRole('button', { name: 'Guardar el cambio' }))
    expect(
      await enDialogo().findByText('Otra persona del grupo cambió lo que puede hacer Rosa Pérez mientras lo mirabas. Ahora Rosa Pérez se informa. Revisa y vuelve a elegir.'),
    ).toBeVisible()
    expect(enDialogo().getByRole('radio', { name: 'Se informa' })).toBeChecked()
    expect(enDialogo().getByRole('radio', { name: 'Se informa' })).toHaveAccessibleDescription(expect.stringContaining('Ahora'))
    expect(enDialogo().getByText(/Otra persona del grupo cambió/).closest('[role="alert"]')).not.toBeNull()
    expect(screen.getByRole('dialog')).toBeVisible()
  })

  it('409 ultimo-admin: el mensaje dentro del diálogo, que no se cierra, y la lista se vuelve a pedir', async () => {
    const pedidas = api({ atender: (p) => (p.linea.startsWith('PATCH') ? problema(409, 'ultimo-admin') : null) })
    abrir('admin')
    await userEvent.click(await screen.findByRole('button', { name: 'Cambiar tu rol' }))
    expect(enDialogo().getByRole('heading', { level: 2, name: 'Cambiar tu rol' })).toBeVisible()
    await userEvent.click(enDialogo().getByRole('radio', { name: 'Cuida' }))
    expect(enDialogo().getByText('Dejarás de administrar el grupo. Para volver a hacerlo, otra persona que administra tendrá que dártelo.')).toBeVisible()
    await userEvent.click(enDialogo().getByRole('button', { name: 'Guardar el cambio' }))
    expect(await enDialogo().findByText('El grupo necesita alguien que lo administre. Primero da ese rol a otra persona.')).toBeVisible()
    await waitFor(() => expect(pedidas.filter((p) => p.linea.endsWith('/miembros') && p.linea.startsWith('GET'))).toHaveLength(2))
  })

  it('sin red: «No pudimos guardar el cambio. Todo sigue como estaba.»', async () => {
    api({ atender: (p) => (p.linea.startsWith('PATCH') ? RED : null) })
    abrir('admin')
    await abrirCambio('Rosa Pérez')
    await userEvent.click(enDialogo().getByRole('radio', { name: 'Paga' }))
    await userEvent.click(enDialogo().getByRole('button', { name: 'Guardar el cambio' }))
    expect(await enDialogo().findByText('No pudimos guardar el cambio. Todo sigue como estaba.')).toBeVisible()
    expect(within(fila('Rosa Pérez')).getByText('Cuida')).toBeVisible()
  })

  it('404: el diálogo se cierra y la nota dice que ya no estaba, con el foco', async () => {
    let fuera = false
    api({
      miembros: [CARMEN, TOMAS, RODRIGO, ROSA],
      atender: (p) => {
        if (p.linea.startsWith('PATCH')) return (fuera = true), problema(404, 'no-encontrado')
        if (fuera && p.linea.endsWith('/miembros')) return { status: 200, cuerpo: { miembros: [CARMEN, TOMAS, RODRIGO] } }
        return null
      },
    })
    abrir('admin')
    await abrirCambio('Rosa Pérez')
    await userEvent.click(enDialogo().getByRole('radio', { name: 'Paga' }))
    await userEvent.click(enDialogo().getByRole('button', { name: 'Guardar el cambio' }))
    const nota = await screen.findByText('Esa persona ya no estaba en el grupo.')
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(nota.closest('[data-aviso]')).toHaveFocus())
    expect(within(lista()).queryByText('Rosa Pérez')).toBeNull()
  })

  it('404 porque otra persona me bajó de rol: «Ya no administras el grupo.» y el rol nuevo en memoria', async () => {
    api({ rolPropio: 'cuidador', atender: (p) => (p.linea.startsWith('PATCH') ? problema(404, 'no-encontrado') : null) })
    abrir('admin')
    await abrirCambio('Rosa Pérez')
    await userEvent.click(enDialogo().getByRole('radio', { name: 'Paga' }))
    await userEvent.click(enDialogo().getByRole('button', { name: 'Guardar el cambio' }))
    expect(await screen.findByText('Ya no administras el grupo.')).toBeVisible()
    expect(contexto.fijar).toHaveBeenCalledWith({ grupos: [expect.objectContaining({ rol: 'cuidador' })] })
  })

  it('«No cambiar» cierra sin pedir nada y el foco vuelve al botón que lo abrió', async () => {
    const pedidas = api()
    abrir('admin')
    const boton = await screen.findByRole('button', { name: 'Cambiar lo que puede hacer Rosa Pérez' })
    await userEvent.click(boton)
    await userEvent.click(enDialogo().getByRole('button', { name: 'No cambiar' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(boton).toHaveFocus())
    expect(pedidas.some((p) => p.linea.startsWith('PATCH'))).toBe(false)
  })
})

// ---------------------------------------------------------------- 6.7 el permiso del pagador

describe('El permiso del pagador para ver la ficha', () => {
  it('dar: la pregunta, lo que podrá hacer, el PATCH con If-Match y «Ahora Rodrigo Soto puede ver la ficha.»', async () => {
    const pedidas = api({
      atender: (p) => (p.linea.startsWith('PATCH') ? { status: 200, cuerpo: { miembro: { ...RODRIGO, puede_ver_plan: true, etag: '"v2"' }, enlaces_cortados: 0 } } : null),
    })
    abrir('admin')
    await userEvent.click(await screen.findByRole('button', { name: 'Dejar que vea la ficha a Rodrigo Soto' }))
    expect(enDialogo().getByRole('heading', { level: 2, name: '¿Dejar que Rodrigo Soto vea la ficha?' })).toBeVisible()
    expect(enDialogo().getByText('Podrá leer la ficha de María y ver sus enlaces de relevo. No podrá cambiarla ni compartirla.')).toBeVisible()
    expect(enDialogo().getByRole('button', { name: 'No por ahora' })).toBeVisible()
    await userEvent.click(enDialogo().getByRole('button', { name: 'Dejar que vea la ficha' }))
    expect(await screen.findByText('Ahora Rodrigo Soto puede ver la ficha.')).toBeVisible()
    expect(within(fila('Rodrigo Soto')).getByText('Puede ver la ficha')).toBeVisible()
    const patch = pedidas.find((p) => p.linea.startsWith('PATCH'))!
    expect(patch.cuerpo).toEqual({ puede_ver_plan: true })
    expect(patch.ifMatch).toBe('"v1"')
  })

  it('quitar: el botón pronto y «Rodrigo Soto ya no ve la ficha.»', async () => {
    const conFicha = { ...RODRIGO, puede_ver_plan: true }
    api({
      miembros: [CARMEN, TOMAS, conFicha, ROSA],
      atender: (p) => (p.linea.startsWith('PATCH') ? { status: 200, cuerpo: { miembro: { ...conFicha, puede_ver_plan: false }, enlaces_cortados: 0 } } : null),
    })
    abrir('admin')
    await userEvent.click(await screen.findByRole('button', { name: 'Quitarle la ficha a Rodrigo Soto' }))
    expect(enDialogo().getByText('Rodrigo Soto dejará de ver la ficha desde ahora.')).toBeVisible()
    const quitar = enDialogo().getByRole('button', { name: 'Quitarle la ficha' })
    expect(quitar).toHaveClass('bg-pronto')
    await userEvent.click(quitar)
    expect(await screen.findByText('Rodrigo Soto ya no ve la ficha.')).toBeVisible()
  })

  it('412: el conflicto con el valor vigente y, si ya está como se quería, sin botón para confirmar', async () => {
    api({ atender: (p) => (p.linea.startsWith('PATCH') ? problema(412, 'version-desactualizada', { actual: { ...RODRIGO, puede_ver_plan: true, etag: '"v2"' } }) : null) })
    abrir('admin')
    await userEvent.click(await screen.findByRole('button', { name: 'Dejar que vea la ficha a Rodrigo Soto' }))
    await userEvent.click(enDialogo().getByRole('button', { name: 'Dejar que vea la ficha' }))
    expect(await enDialogo().findByText(/^Otra persona del grupo cambió lo que puede hacer Rodrigo Soto/)).toBeVisible()
    expect(enDialogo().queryByRole('button', { name: 'Dejar que vea la ficha' })).toBeNull()
    expect(enDialogo().getByRole('button', { name: 'No por ahora' })).toBeVisible()
  })
})

// ---------------------------------------------------------------- 7.1 sacar

describe('Sacar a alguien', () => {
  it('la confirmación con los puntos, el botón pronto, y la nota arriba de la lista con el foco', async () => {
    const pedidas = api({ atender: (p) => (p.linea === `DELETE /v1/grupos/${GRUPO_ID}/miembros/m-rosa` ? { status: 200, cuerpo: { enlaces_cortados: 2 } } : null) })
    abrir('admin')
    await userEvent.click(await screen.findByRole('button', { name: 'Sacar del grupo a Rosa Pérez' }))
    expect(enDialogo().getByRole('heading', { level: 2, name: '¿Sacar a Rosa Pérez del grupo?' })).toBeVisible()
    const puntos = enDialogo().getAllByRole('listitem').map((li) => li.textContent)
    expect(puntos).toEqual([
      'Dejará de verlo ahora.',
      'Se cortan 2 enlaces de relevo que compartió.',
      'Lo que escribió en la ficha queda.',
      'Para volver, tendrías que invitar a Rosa Pérez de nuevo.',
    ])
    expect(enDialogo().getByText('Se cortan 2 enlaces de relevo que compartió.')).toHaveClass('font-bold')
    const boton = enDialogo().getByRole('button', { name: 'Sacar del grupo' })
    expect(boton).toHaveClass('bg-pronto')
    await userEvent.click(boton)
    const nota = await screen.findByText('Rosa Pérez ya no está en el grupo. Cortamos 2 enlaces.')
    await waitFor(() => expect(nota.closest('[data-aviso]')).toHaveFocus())
    expect(within(lista()).queryByText('Rosa Pérez')).toBeNull()
    expect(pedidas.filter((p) => p.linea.startsWith('DELETE'))).toHaveLength(1)
  })

  it('sin enlaces: «No tiene enlaces de relevo que abran ahora.»', async () => {
    api()
    abrir('admin')
    await userEvent.click(await screen.findByRole('button', { name: 'Sacar del grupo a Rodrigo Soto' }))
    expect(enDialogo().getByText('No tiene enlaces de relevo que abran ahora.')).toBeVisible()
  })

  it('sin red: el error con su nombre, y la persona sigue en la lista', async () => {
    api({ atender: (p) => (p.linea.startsWith('DELETE') ? RED : null) })
    abrir('admin')
    await userEvent.click(await screen.findByRole('button', { name: 'Sacar del grupo a Rosa Pérez' }))
    await userEvent.click(enDialogo().getByRole('button', { name: 'Sacar del grupo' }))
    expect(await enDialogo().findByText('No pudimos sacar a Rosa Pérez del grupo. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.')).toBeVisible()
    expect(within(lista()).getByText('Rosa Pérez')).toBeVisible()
  })
})

// ---------------------------------------------------------------- 5.4 anular

describe('Anular una invitación', () => {
  it('confirma y la fila sale, con «Invitación anulada.» y el foco', async () => {
    const pedidas = api({ atender: (p) => (p.linea === `DELETE /v1/grupos/${GRUPO_ID}/invitaciones/inv-1` ? { status: 204 } : null) })
    abrir('admin')
    await userEvent.click(await screen.findByRole('button', { name: 'Anular la invitación' }))
    expect(enDialogo().getByRole('button', { name: 'Anular la invitación' })).toHaveClass('bg-pronto')
    await userEvent.click(enDialogo().getByRole('button', { name: 'Anular la invitación' }))
    const nota = await screen.findByText('Invitación anulada.')
    await waitFor(() => expect(nota.closest('[data-aviso]')).toHaveFocus())
    expect(screen.queryByText(/^Se informa ·/)).toBeNull()
    expect(pedidas.filter((p) => p.linea.startsWith('DELETE'))).toHaveLength(1)
  })

  it('409 invitacion-cerrada: dice que ya se usó y vuelve a pedir la lista', async () => {
    api({ atender: (p) => (p.linea.startsWith('DELETE') ? problema(409, 'invitacion-cerrada', { estado: 'usada' }) : null) })
    abrir('admin')
    await userEvent.click(await screen.findByRole('button', { name: 'Anular la invitación' }))
    await userEvent.click(enDialogo().getByRole('button', { name: 'Anular la invitación' }))
    expect(await screen.findByText('Esa invitación ya se usó.')).toBeVisible()
  })
})

// ---------------------------------------------------------------- 7.2 y 7.3 salir

describe('Salir del grupo', () => {
  it('la sección al final, el diálogo con «Hoy abren 1.», y al salir la app vuelve a pedir los grupos con el aviso', async () => {
    const pedidas = api({ atender: (p) => (p.linea === `POST /v1/grupos/${GRUPO_ID}/salida` ? { status: 200, cuerpo: { enlaces_cortados: 1 } } : null) })
    abrir('admin')
    const seccion = within(await screen.findByRole('region', { name: 'Salir del grupo' }))
    expect(seccion.getByText('Dejarás de ver Familia Soto y se cortan los enlaces de relevo que compartiste.')).toBeVisible()
    const abrirSalir = await seccion.findByRole('button', { name: 'Salir del grupo' })
    expect(abrirSalir).toHaveClass('ring-pronto')
    await userEvent.click(abrirSalir)
    expect(enDialogo().getByRole('heading', { level: 2, name: '¿Salir de Familia Soto?' })).toBeVisible()
    expect(enDialogo().getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Dejarás de verlo ahora.',
      'Se cortan los enlaces de relevo que compartiste. Hoy abre 1.',
      'Lo que escribiste en la ficha queda, porque es parte del cuidado de María.',
      'Para volver, alguien que administra el grupo tiene que invitarte de nuevo.',
    ])
    expect(enDialogo().getByRole('button', { name: 'Quedarme' })).toBeVisible()
    await userEvent.click(enDialogo().getByRole('button', { name: 'Salir del grupo' }))
    await waitFor(() => expect(window.location.pathname).toBe('/'))
    expect(contexto.alEntrar).toHaveBeenCalled()
    expect(contexto.fijar).toHaveBeenCalledWith({ aviso: { titulo: 'Saliste de Familia Soto. Cortamos 1 enlace.', tono: 'ok' } })
    expect(pedidas.find((p) => p.linea.endsWith('/salida'))?.grupo).toBe(GRUPO_ID)
  })

  it('409 unica-persona: la frase de 7.3 y, al cerrar, el foco va a «Borrar los datos de María»', async () => {
    api({ atender: (p) => (p.linea.endsWith('/salida') ? problema(409, 'unica-persona') : null) })
    abrir('admin')
    await userEvent.click(await within(await screen.findByRole('region', { name: 'Salir del grupo' })).findByRole('button', { name: 'Salir del grupo' }))
    await userEvent.click(enDialogo().getByRole('button', { name: 'Salir del grupo' }))
    expect(await enDialogo().findByText(/^Eres la única persona de Familia Soto, así que no puedes salir\./)).toBeVisible()
    expect(enDialogo().queryByRole('button', { name: 'Salir del grupo' })).toBeNull()
    await userEvent.click(enDialogo().getByRole('button', { name: 'Quedarme' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Borrar los datos de María' })).toHaveFocus())
  })

  it('409 ultimo-admin: «El grupo necesita alguien que lo administre…»', async () => {
    api({ atender: (p) => (p.linea.endsWith('/salida') ? problema(409, 'ultimo-admin') : null) })
    abrir('admin')
    await userEvent.click(await within(await screen.findByRole('region', { name: 'Salir del grupo' })).findByRole('button', { name: 'Salir del grupo' }))
    await userEvent.click(enDialogo().getByRole('button', { name: 'Salir del grupo' }))
    expect(await enDialogo().findByText('El grupo necesita alguien que lo administre. Primero da ese rol a otra persona.')).toBeVisible()
  })

  it('sin red: «Sigues en el grupo.»', async () => {
    api({ atender: (p) => (p.linea.endsWith('/salida') ? RED : null) })
    abrir('cuidador')
    await userEvent.click(await within(await screen.findByRole('region', { name: 'Salir del grupo' })).findByRole('button', { name: 'Salir del grupo' }))
    await userEvent.click(enDialogo().getByRole('button', { name: 'Salir del grupo' }))
    expect(await enDialogo().findByText('No pudimos sacarte del grupo. Revisa tu conexión y vuelve a intentarlo. Sigues en el grupo.')).toBeVisible()
    expect(contexto.alEntrar).not.toHaveBeenCalled()
  })

  it('«Quedarme» cierra sin pedir nada y el foco vuelve a «Salir del grupo»', async () => {
    const pedidas = api()
    abrir('cuidador')
    const boton = await within(await screen.findByRole('region', { name: 'Salir del grupo' })).findByRole('button', { name: 'Salir del grupo' })
    await userEvent.click(boton)
    await userEvent.click(enDialogo().getByRole('button', { name: 'Quedarme' }))
    await waitFor(() => expect(boton).toHaveFocus())
    expect(pedidas.some((p) => p.linea.endsWith('/salida'))).toBe(false)
  })

  it('nunca «Salir» solo: siempre «Salir del grupo»', async () => {
    api()
    abrir('admin')
    await screen.findByRole('region', { name: 'Salir del grupo' })
    for (const b of screen.getAllByRole('button')) expect(b.textContent?.trim()).not.toBe('Salir')
  })
})

// ---------------------------------------------------------------- 5.6 el aviso de D-42-9

describe('La autorización que dio alguien que ya no está (D-42-9)', () => {
  it.each(['admin', 'cuidador'] as const)('el %s ve la nota bajo el estado, sin botón para renovar', async (rol) => {
    api({ autorizaciones: [vigente('plan_cuidado', { autorizo_alguien_que_ya_no_esta: true }), vigente('consumo')] })
    abrir(rol)
    const ficha = within(await screen.findByRole('region', { name: 'Permiso para guardar su ficha' }))
    expect(ficha.getByText('La autorización la dio alguien que ya no está en el grupo. Sigue vigente.')).toBeVisible()
    expect(ficha.queryByRole('button', { name: /renov/i })).toBeNull()
    expect(within(screen.getByRole('region', { name: 'Permiso para calcular sus insumos' })).queryByText(/ya no está en el grupo/)).toBeNull()
  })

  it('con el campo en false, o para el pagador, no aparece', async () => {
    api({ autorizaciones: [vigente('plan_cuidado', { autorizo_alguien_que_ya_no_esta: false }), vigente('consumo')] })
    const { unmount } = abrir('admin')
    await screen.findByRole('region', { name: 'Permiso para guardar su ficha' })
    expect(screen.queryByText(/La autorización la dio alguien/)).toBeNull()
    unmount()
    api({ autorizaciones: [vigente('plan_cuidado', { autorizo_alguien_que_ya_no_esta: true }), vigente('consumo')] })
    abrir('pagador')
    await screen.findByRole('region', { name: 'Permiso para guardar su ficha' })
    expect(screen.queryByText(/La autorización la dio alguien/)).toBeNull()
  })
})

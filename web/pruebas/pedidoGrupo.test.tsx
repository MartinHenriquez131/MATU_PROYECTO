// MATU-61: Grupo familiar con el permiso para pedir (especificación 12, decisión 192, C2, C6 y C8).
// El tercer bloque en sus cuatro estados, la confirmación de retirar con sus puntos, «Volver a
// autorizar» y «Ver la dirección de entrega». Con la capa 3 apagada, el bloque no viene (dos ítems).
// Solo datos sintéticos.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { fijarGrupo } from '../src/compartido/api/sesion'
import { AutorizarPedidosDesdeGrupo, GrupoFamiliar } from '../src/familia/Grupo'
import { DECLARACION_PEDIDOS, huellaDe } from '../src/familia/textosPedido'
import { familiaFalsa } from './familiaFalsa'
import { apiPedido, autorizaciones, conRegionesGlobales, DIRECCION, persona, PERSONA_ID } from './pedidoFalso'

const GRUPO = { id: '3c9d4e20-0000-4000-8000-0000000000g1', nombre: 'Familia Soto', rol: 'admin', puede_ver_plan: true }

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

function abrir(rol: Rol, despacho: Parameters<typeof autorizaciones>[0], { conDireccion = true, rutas = {} as Parameters<typeof apiPedido>[0] } = {}) {
  window.history.replaceState(null, '', '/grupo')
  fijarGrupo(GRUPO.id)
  const p = persona(conDireccion ? DIRECCION : null)
  const vista = rol === 'observador' ? { id: p.id, nombre: p.nombre } : rol === 'pagador' ? { id: p.id, nombre: p.nombre, direccion: p.direccion } : p
  const api = apiPedido({ [`GET /v1/grupos/${GRUPO.id}/personas-cuidadas$`]: { status: 200, cuerpo: [vista] }, 'GET /accesos-relevo$': { status: 200, cuerpo: { items: [], siguiente_cursor: null } }, ...rutas }, { despacho })
  const fijar = vi.fn()
  contexto = familiaFalsa({ grupo: { ...GRUPO, rol }, rol, personas: [vista], personaId: PERSONA_ID, persona: vista, fijar, reautorizar: null } as never)
  return { ...conRegionesGlobales(<GrupoFamiliar />), api, fijar }
}

const bloque = async () => within(await screen.findByRole('region', { name: 'Permiso para pedir sus insumos' }))

describe('El permiso para pedir sus insumos (12.1)', () => {
  it('vigente: «Autorizado el…», «Retirar la autorización» y «Ver la dirección de entrega», con la persona en el nombre accesible', async () => {
    abrir('admin', 'vigente')
    const b = await bloque()
    expect(b.getByText(/^Autorizado el/).closest('p')).toHaveTextContent('Autorizado el 09/11/2026.')
    expect(b.getByRole('button', { name: 'Retirar la autorización de los pedidos de María' })).toHaveTextContent('Retirar la autorización')
    expect(b.getByRole('button', { name: 'Ver la dirección de entrega de María' })).toHaveTextContent('Ver la dirección de entrega')
  })

  it('por renovar: «Hay que renovarlo desde el…»', async () => {
    abrir('admin', 'revision_vencida')
    const b = await bloque()
    expect(b.getByText(/^Autorizado el/).closest('p')).toHaveTextContent('Autorizado el 09/11/2026. Hay que renovarlo desde el 01/11/2026.')
  })

  it('retirada: sin la frase del borrado a los 90 días, con «Volver a autorizar» y la dirección que se conserva (C6)', async () => {
    const { fijar } = abrir('admin', 'retirada')
    const b = await bloque()
    expect(b.getByText(/^Autorización retirada el/).closest('p')).toHaveTextContent(/^Autorización retirada el 10\/11\/2026\.$/)
    expect(b.getByRole('button', { name: 'Volver a autorizar los pedidos de María' })).toBeVisible()
    await userEvent.click(b.getByRole('button', { name: 'Ver la dirección de entrega de María' }))
    expect(fijar).toHaveBeenCalledWith({ direccionDesdeGrupo: true })
    expect(window.location.pathname).toBe('/insumos/pedido/direccion')
  })

  it('sin autorizar: «Sin permiso todavía. Se pide la primera vez que haces un pedido.», sin botones', async () => {
    abrir('admin', 'sin_autorizar')
    const b = await bloque()
    expect(b.getByText('Sin permiso todavía. Se pide la primera vez que haces un pedido.')).toBeVisible()
    expect(b.queryByRole('button')).toBeNull()
  })

  it('sin dirección guardada no hay «Ver la dirección de entrega»', async () => {
    abrir('admin', 'vigente', { conDireccion: false })
    const b = await bloque()
    expect(b.queryByRole('button', { name: /Ver la dirección/ })).toBeNull()
  })

  it.each<Rol>(['pagador', 'observador'])('%s: sin botones, con quién puede retirarla', async (rol) => {
    abrir(rol, 'vigente')
    const b = await bloque()
    expect(b.queryByRole('button')).toBeNull()
    expect(b.getByText('Puede retirarla quien administra el grupo o quien cuida a María Soto.')).toBeVisible()
  })

  it('con la capa 3 apagada la API trae dos autorizaciones y no hay bloque de pedidos', async () => {
    abrir('admin', 'vigente', { rutas: { 'GET /consentimientos$': { status: 200, cuerpo: { autorizaciones: autorizaciones().autorizaciones.slice(0, 2) } } } })
    await screen.findByRole('region', { name: 'Permiso para calcular sus insumos' })
    expect(screen.queryByRole('region', { name: 'Permiso para pedir sus insumos' })).toBeNull()
  })
})

describe('Retirar el permiso de los pedidos (12.2)', () => {
  it('la confirmación con sus seis puntos, el de los pedidos sin pagar en negrita, y la nota después', async () => {
    const { api } = abrir('admin', 'vigente', {
      rutas: { 'POST /consentimientos/despacho/retiro$': { status: 200, cuerpo: { autorizacion: autorizaciones('retirada').autorizaciones[2], enlaces_cortados: 0, pedidos_cancelados: 1 } } },
    })
    const b = await bloque()
    await userEvent.click(b.getByRole('button', { name: 'Retirar la autorización de los pedidos de María' }))
    const dialogo = screen.getByRole('dialog', { name: '¿Retirar la autorización de los pedidos de María?' })
    const puntos = within(dialogo).getAllByRole('listitem')
    expect(puntos.map((p) => p.textContent)).toEqual([
      'Ya no se pueden hacer pedidos para María desde MATU, desde ahora.',
      'Cancelamos sin costo los pedidos sin pagar y borramos la dirección y el teléfono que se copiaron en ellos.',
      'Los pedidos ya pagados siguen hasta que se entreguen.',
      'La dirección de entrega de María queda guardada para cuando vuelvas a autorizar. Puedes vaciarla cuando quieras.',
      'La lista de insumos se puede seguir imprimiendo y compartiendo.',
      'Su ficha, sus insumos y los enlaces de relevo no cambian.',
    ])
    expect(puntos[1].className).toMatch(/font-bold/)
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Retirar la autorización' }))
    expect((await screen.findAllByText('Autorización retirada. Ya no se pueden hacer pedidos para María.'))[0]).toBeVisible()
    expect(api.escrituras().map((x) => `${x.metodo} ${x.ruta}`)).toEqual([`POST /v1/personas-cuidadas/${PERSONA_ID}/consentimientos/despacho/retiro`])
  })
})

describe('Volver a autorizar los pedidos (12.4)', () => {
  it('la pantalla de 4.1 con «Volver a Grupo familiar»; al autorizar vuelve con su nota', async () => {
    window.history.replaceState(null, '', '/grupo/autorizar-pedidos')
    fijarGrupo(GRUPO.id)
    const api = apiPedido({ 'POST /consentimientos$': { status: 201, cuerpo: {} } }, { despacho: 'retirada' })
    const fijar = vi.fn()
    const vistaRetirada = autorizaciones('retirada').autorizaciones[2]
    contexto = familiaFalsa({ grupo: GRUPO, rol: 'admin', personas: [persona()], personaId: PERSONA_ID, persona: persona(), fijar, reautorizar: { personaId: PERSONA_ID, finalidad: 'despacho', vista: vistaRetirada } } as never)
    conRegionesGlobales(<AutorizarPedidosDesdeGrupo />)
    expect(screen.getByRole('heading', { level: 1, name: 'Antes de pedir, un permiso' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Volver a Grupo familiar' })).toBeVisible()
    await userEvent.click(screen.getByRole('radio', { name: /María lo autoriza y yo lo registro/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Autorizar los pedidos' }))
    await waitFor(() => expect(window.location.pathname).toBe('/grupo'))
    expect(api.escrituras()[0].cuerpo).toMatchObject({ finalidad: 'despacho', calidad_otorgante: 'titular', huella_declaracion: await huellaDe(DECLARACION_PEDIDOS.titular) })
    expect(fijar).toHaveBeenCalledWith({ reautorizar: null, aviso: { titulo: 'Pedidos autorizados. Ya puedes hacer pedidos para María.', tono: 'ok' } })
  })
})

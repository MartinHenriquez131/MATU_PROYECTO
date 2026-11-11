// MATU-61: «¿Dónde lo entregamos?» (especificación 8 y 12.1, C8): los campos sin región ni mapa,
// la ayuda de la referencia antes del campo, la validación al guardar, `If-None-Match: *` la primera
// vez e `If-Match` después, el 412 con las dos direcciones, y vaciarla con su diálogo, también desde
// Grupo familiar. Solo datos sintéticos.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fijarGrupo } from '../src/compartido/api/sesion'
import { PantallaPedido } from '../src/familia/Pedido'
import { familiaFalsa } from './familiaFalsa'
import { apiPedido, conRegionesGlobales, DIRECCION, enOrden, persona, PERSONA_ID, problema } from './pedidoFalso'

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

beforeEach(() => {
  fijarGrupo('3c9d4e20-0000-4000-8000-0000000000g1')
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.removeAttribute('open')
  }
})

function abrir(direccion: typeof DIRECCION | null, desdeGrupo = false) {
  window.history.replaceState(null, '', '/insumos/pedido/direccion')
  const p = persona(direccion)
  const fijar = vi.fn()
  contexto = familiaFalsa({ persona: p, personas: [p], personaId: PERSONA_ID, rol: 'cuidador', capa3: true, fijar, direccionDesdeGrupo: desdeGrupo } as never)
  return { ...conRegionesGlobales(<PantallaPedido />), fijar }
}

const SEGUNDA = { ...DIRECCION, numero: '125', depto: null, referencia: null, etag: 'v2' }

describe('¿Dónde lo entregamos? (8)', () => {
  it('los cinco campos, sin región, mapa ni ubicación; la ayuda de la referencia antes del campo', async () => {
    apiPedido({})
    abrir(null)
    expect(screen.getByRole('heading', { level: 1, name: '¿Dónde lo entregamos?' })).toBeVisible()
    expect(screen.getByText('La usamos solo para entregar tus pedidos. Ningún comercio la ve. La guardamos para los próximos pedidos de María.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Volver a tu pedido' })).toBeVisible()
    expect(screen.getAllByRole<HTMLInputElement>('textbox').map((c) => c.labels?.[0]?.textContent)).toEqual(['Calle', 'Número', 'Depto (opcional)', 'Comuna', 'Referencia (opcional)'])
    const referencia = screen.getByRole('textbox', { name: 'Referencia (opcional)' })
    expect(referencia).toHaveAccessibleDescription('Por ejemplo: portón verde. No escribas datos de salud.')
    const ayuda = screen.getByText('Por ejemplo: portón verde. No escribas datos de salud.')
    expect(ayuda.compareDocumentPosition(referencia) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByRole('textbox', { name: 'Calle' })).toHaveAttribute('autocomplete', 'address-line1')
    expect(screen.getByRole('textbox', { name: 'Referencia (opcional)' })).toHaveAttribute('maxlength', '200')
    expect(document.body.textContent).not.toMatch(/Región|Metropolitana|mapa|ubicación/i)
    // Sin dirección guardada no hay «Vaciar la dirección».
    expect(screen.queryByRole('button', { name: /Vaciar/ })).toBeNull()
    expect(screen.getAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className)).map((b) => b.textContent)).toEqual(['Guardar la direcciónGuardando…'])
  })

  it('valida al guardar, con el foco en el primer error, y no envía nada', async () => {
    const api = apiPedido({})
    abrir(null)
    await userEvent.click(screen.getByRole('button', { name: 'Guardar la dirección' }))
    expect(screen.getByRole('textbox', { name: 'Calle' })).toHaveAccessibleDescription('Escribe la calle.')
    expect(screen.getByRole('textbox', { name: 'Número' })).toHaveAccessibleDescription('Escribe el número. Si no tiene, escribe S/N.')
    expect(screen.getByRole('textbox', { name: 'Comuna' })).toHaveAccessibleDescription('Escribe la comuna.')
    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Calle' })).toHaveFocus())
    expect(api.escrituras()).toEqual([])
  })

  it('la primera vez con If-None-Match: *, sin etiqueta ni región, y vuelve a «Tu pedido» con «Guardamos la dirección.»', async () => {
    const api = apiPedido({ 'PUT /direccion$': { status: 200, cuerpo: { ...DIRECCION } } })
    const { fijar } = abrir(null)
    await userEvent.type(screen.getByRole('textbox', { name: 'Calle' }), 'Los Aromos')
    await userEvent.type(screen.getByRole('textbox', { name: 'Número' }), '123')
    await userEvent.type(screen.getByRole('textbox', { name: 'Comuna' }), 'La Reina')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar la dirección' }))
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
    const put = api.escrituras()[0]
    expect(put.ruta).toBe(`/v1/personas-cuidadas/${PERSONA_ID}/direccion`)
    expect(put.cabeceras['If-None-Match']).toBe('*')
    expect(put.cabeceras['If-Match']).toBeUndefined()
    expect(put.cuerpo).toEqual({ calle: 'Los Aromos', numero: '123', depto: null, comuna: 'La Reina', referencia: null })
    expect(fijar).toHaveBeenCalledWith({ personas: [expect.objectContaining({ direccion: DIRECCION })] })
    expect((await screen.findAllByText('Guardamos la dirección.'))[0]).toBeVisible()
  })

  it('al cambiar una guardada, If-Match con su etag, y reenvía su etiqueta y su región', async () => {
    const api = apiPedido({ 'PUT /direccion$': { status: 200, cuerpo: { ...DIRECCION, etag: 'v2' } } })
    abrir(DIRECCION)
    expect(screen.getByRole('textbox', { name: 'Calle' })).toHaveValue('Los Aromos')
    await userEvent.clear(screen.getByRole('textbox', { name: 'Depto (opcional)' }))
    await userEvent.click(screen.getByRole('button', { name: 'Guardar la dirección' }))
    await waitFor(() => expect(api.escrituras()).toHaveLength(1))
    expect(api.escrituras()[0].cabeceras['If-Match']).toBe('v1')
    expect(api.escrituras()[0].cuerpo).toEqual({ etiqueta: 'Casa', region: 'Metropolitana', calle: 'Los Aromos', numero: '123', depto: null, comuna: 'La Reina', referencia: 'Portón verde' })
  })

  it('8.5: otra persona la cambió (412): las dos a la vista, el aviso con el foco, y «Guardar la mía» con el etag nuevo', async () => {
    const api = apiPedido({ 'PUT /direccion$': enOrden(problema(412, 'version-desactualizada', { actual: SEGUNDA }), { status: 200, cuerpo: { ...DIRECCION, etag: 'v3' } }) })
    const { urgente } = abrir(DIRECCION)
    await userEvent.click(screen.getByRole('button', { name: 'Guardar la dirección' }))
    await waitFor(() => expect(urgente).toHaveTextContent('Otra persona de tu grupo cambió la dirección mientras la cambiabas.'))
    expect(screen.getByText('No guardamos la tuya encima de la suya. Elige cuál dejar.')).toBeVisible()
    expect(within(screen.getByRole('heading', { name: 'La que guardó' }).parentElement!).getByText('Los Aromos 125, La Reina')).toBeVisible()
    expect(within(screen.getByRole('heading', { name: 'La tuya, sin guardar' }).parentElement!).getByText('Los Aromos 123, depto 4, La Reina')).toBeVisible()
    await waitFor(() => expect(document.activeElement?.textContent).toContain('Otra persona de tu grupo cambió la dirección'))
    // 13.1: con el conflicto, «Guardar la mía» es el único macizo.
    expect(screen.getAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className))).toEqual([screen.getByRole('button', { name: 'Guardar la mía' })])
    await userEvent.click(screen.getByRole('button', { name: 'Guardar la mía' }))
    await waitFor(() => expect(api.escrituras()).toHaveLength(2))
    expect(api.escrituras()[1].cabeceras['If-Match']).toBe('v2')
  })

  it('«Dejar la que guardó» vuelve a «Tu pedido» con su nota', async () => {
    apiPedido({ 'PUT /direccion$': problema(412, 'version-desactualizada', { actual: SEGUNDA }) })
    abrir(DIRECCION)
    await userEvent.click(screen.getByRole('button', { name: 'Guardar la dirección' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Dejar la que guardó' }))
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
    expect((await screen.findAllByText('Dejaste la dirección que guardó otra persona de tu grupo.'))[0]).toBeVisible()
  })
})

describe('Vaciar la dirección (8.7, JC6)', () => {
  it('separada por el borde, en rojo sin fondo, con su diálogo; «Dejarla como está» devuelve el foco', async () => {
    const api = apiPedido({})
    abrir(DIRECCION)
    expect(screen.getByText('Si no quieres que MATU la guarde, puedes vaciarla. Para el próximo pedido habrá que escribirla de nuevo.')).toBeVisible()
    const vaciar = screen.getByRole('button', { name: 'Vaciar la dirección de entrega de María' })
    expect(vaciar).toHaveTextContent('Vaciar la dirección')
    expect(vaciar.className).toMatch(/\btext-pronto\b/)
    expect(vaciar.className).not.toMatch(/\bbg-/)
    expect(vaciar.parentElement!.className).toMatch(/border-t border-linea/)
    await userEvent.click(vaciar)
    const dialogo = screen.getByRole('dialog', { name: '¿Vaciar la dirección de entrega de María?' })
    expect(dialogo).toHaveAccessibleDescription('La borramos de MATU. Para el próximo pedido habrá que escribirla de nuevo.')
    expect(within(dialogo).getByRole('heading')).toHaveFocus()
    expect(within(dialogo).getByRole('button', { name: 'Vaciar la dirección' }).className).toMatch(/\bbg-pronto\b/)
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Dejarla como está' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Vaciar la dirección de entrega de María' })).toHaveFocus())
    expect(api.escrituras()).toEqual([])
  })

  it('vacía con If-Match y vuelve a «Tu pedido» con «Vaciamos la dirección.»', async () => {
    const api = apiPedido({ 'DELETE /direccion$': { status: 204 } })
    const { fijar } = abrir(DIRECCION)
    await userEvent.click(screen.getByRole('button', { name: 'Vaciar la dirección de entrega de María' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Vaciar la dirección' }))
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
    expect(api.escrituras()[0]).toMatchObject({ metodo: 'DELETE', ruta: `/v1/personas-cuidadas/${PERSONA_ID}/direccion` })
    expect(api.escrituras()[0].cabeceras['If-Match']).toBe('v1')
    expect(fijar).toHaveBeenCalledWith({ personas: [expect.objectContaining({ direccion: null })] })
    expect((await screen.findAllByText('Vaciamos la dirección.'))[0]).toBeVisible()
  })

  it('sin conexión: el error en el diálogo y todo sigue como estaba', async () => {
    apiPedido({ 'DELETE /direccion$': problema(503, 'servicio-no-disponible') })
    abrir(DIRECCION)
    await userEvent.click(screen.getByRole('button', { name: 'Vaciar la dirección de entrega de María' }))
    const dialogo = screen.getByRole('dialog')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Vaciar la dirección' }))
    expect(await within(dialogo).findByText('No pudimos vaciar la dirección. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.')).toBeVisible()
    expect(window.location.pathname).toBe('/insumos/pedido/direccion')
  })

  it('412: cierra el diálogo y muestra cómo quedó, con el aviso', async () => {
    apiPedido({ 'DELETE /direccion$': problema(412, 'version-desactualizada', { actual: SEGUNDA }) })
    const { urgente } = abrir(DIRECCION)
    await userEvent.click(screen.getByRole('button', { name: 'Vaciar la dirección de entrega de María' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Vaciar la dirección' }))
    await waitFor(() => expect(urgente).toHaveTextContent('Otra persona de tu grupo cambió la dirección mientras la revisabas. Revisa cómo quedó antes de vaciarla.'))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.getByRole('textbox', { name: 'Número' })).toHaveValue('125')
  })

  it('12.1 y C8: desde Grupo familiar, «Volver a Grupo familiar», y al vaciar vuelve allá con su nota', async () => {
    apiPedido({ 'DELETE /direccion$': { status: 204 } })
    const { fijar } = abrir(DIRECCION, true)
    expect(screen.getByRole('button', { name: 'Volver a Grupo familiar' })).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Vaciar la dirección de entrega de María' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Vaciar la dirección' }))
    await waitFor(() => expect(window.location.pathname).toBe('/grupo'))
    expect(fijar).toHaveBeenCalledWith({ aviso: { titulo: 'Vaciamos la dirección.', tono: 'ok' } })
  })
})

// MATU-113: quien «Se informa» (el observador) ve el pedido sin montos (especificación
// docs/diseno/matu-113-observador-sin-montos.md, secciones 2 y 6). En borrador, con el total
// confirmado y vencido: ningún «$», ningún NaN, sin «Derecho a retracto» ni el aviso del piloto, con
// la etiqueta del estado y el pie de quién ve los precios. La vista se elige por la forma de la
// respuesta: una vista sin etag que igual trae montos tampoco los muestra. Solo datos sintéticos.
import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { fijarGrupo } from '../src/compartido/api/sesion'
import { PantallaPedido } from '../src/familia/Pedido'
import { familiaFalsa } from './familiaFalsa'
import { ALMACEN, apiPedido, BODEGA, borrador, confirmado, linea, PANAL, persona, PERSONA_ID, TOALLITAS, vistaObservador, conRegionesGlobales } from './pedidoFalso'
import { filaObservador, lista } from './tusPedidosFalso'

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

let escrituras: string[] = []
beforeEach(() => {
  escrituras = []
  for (const s of [localStorage, sessionStorage]) s.clear()
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
  fijarGrupo('3c9d4e20-0000-4000-8000-0000000000g1')
})

function abrir(rol: Rol = 'observador') {
  window.history.replaceState(null, '', '/insumos/pedido')
  const p = persona()
  const vista = rol === 'observador' ? { id: p.id, nombre: p.nombre } : p
  contexto = familiaFalsa({ persona: vista, personas: [vista], personaId: PERSONA_ID, rol, capa3: true, intencionPedido: null, llegadaPedido: null, direccionDesdeGrupo: false } as never)
  return conRegionesGlobales(<PantallaPedido />)
}

/** El pañal con «Buscarlo en otro comercio» y las toallitas con «Sacarlo del pedido». */
const lineas = [linea(PANAL, ALMACEN, 2, 12990), linea(TOALLITAS, BODEGA, 1, 4290, { regla_faltante: 'quitar' })]
const vencido = () => ({ ...confirmado({ lineas }), estado: 'vencido' as const })
const cargado = () => screen.findByRole('heading', { level: 2, name: 'Pañal adulto M x30' })
const lineaDe = (nombre: string) => screen.getByRole('heading', { level: 2, name: nombre }).closest('li')!

/** Lo que nunca aparece para quien «Se informa» (6.1 a 6.3 y 6.8). */
function sinMontos() {
  const texto = document.body.textContent ?? ''
  expect(texto).not.toContain('$')
  expect(texto).not.toMatch(/NaN|IVA|Precio de ejemplo|cada uno|Subtotal|Productos:|te devolvemos|observador/i)
  expect(texto).not.toContain('Derecho a retracto')
  expect(texto).not.toContain('Precios de ejemplo.')
  expect(texto).not.toContain('puede cambiar el pedido y ver el total')
  expect(screen.queryByRole('region', { name: 'Entrega' })).toBeNull()
  expect(screen.queryAllByRole('button')).toEqual([])
}

describe('«Pedido» para quien «Se informa» (MATU-113, 2)', () => {
  it.each([
    ['borrador', () => borrador({ lineas }), 'Sin confirmar', /lucide-shopping-basket/],
    ['total confirmado', () => confirmado({ lineas }), 'Falta pagarlo', /lucide-clock/],
    ['vencido', vencido, 'Hay que confirmarlo de nuevo', /lucide-hourglass/],
  ] as const)('%s: ningún monto, la etiqueta del estado y el pie de quién ve los precios', async (_nombre, pedido, etiqueta, icono) => {
    apiPedido({}, { pedido: vistaObservador(pedido()) })
    abrir()
    await cargado()
    expect(screen.getByText('Lo que se va a pedir para María.')).toBeVisible()
    // 2.4: una sola etiqueta, con ícono y palabra; solo «Hay que confirmarlo de nuevo» en atenta.
    const e = screen.getByText(etiqueta)
    expect(e.querySelector('svg')!.getAttribute('class')).toMatch(icono)
    expect(e.className).toMatch(etiqueta === 'Hay que confirmarlo de nuevo' ? /\btext-atenta\b/ : /\btext-tenue\b/)
    expect(screen.getByText('Los precios y el total los ven quien administra el grupo, quien cuida a María y quien paga.')).toBeVisible()
    sinMontos()
  })

  it('cada línea: nombre, presentación, comercio ficticio, cantidad con su sufijo y «Si falta» según la regla', async () => {
    apiPedido({}, { pedido: vistaObservador(borrador({ lineas })) })
    abrir()
    await cargado()
    const panal = within(lineaDe('Pañal adulto M x30'))
    expect(panal.getByText('Paquete de 30 unidades')).toBeVisible()
    expect(panal.getByText('De Almacén El Ejemplo (comercio ficticio)')).toBeVisible()
    expect(panal.getByText('envases de 30 unidades').closest('p')).toHaveTextContent('2 envases de 30 unidades')
    expect(panal.getByText('Si falta: lo buscamos en otro comercio.')).toBeVisible()
    expect(within(lineaDe('Toallitas húmedas x80')).getByText('Si falta: lo sacamos del pedido.')).toBeVisible()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByRole('radio')).toBeNull()
  })

  it('una vista sin etag que igual trae montos (contrato viejo o defecto) se pinta sin ellos y sin NaN', async () => {
    const conMontos = confirmado({ lineas }) as Partial<ReturnType<typeof confirmado>>
    delete conMontos.etag
    apiPedido({}, { pedido: conMontos as never })
    abrir()
    await cargado()
    expect(screen.getByText('Falta pagarlo')).toBeVisible()
    sinMontos()
  })

  it('al final, la fila de «Tus pedidos» con «Pagado el…» y el estado real, sin montos', async () => {
    apiPedido({ 'GET /pedidos$': { status: 200, cuerpo: lista([filaObservador({ estado: 'en_ruta' })]) } }, { pedido: vistaObservador(borrador({ lineas })) })
    abrir()
    const bloque = within((await screen.findByRole('heading', { level: 2, name: 'Tus pedidos' })).closest('section')!)
    expect(bloque.getByText('Pagado el').closest('p')).toHaveTextContent('Pagado el 11/11/2026')
    expect(bloque.getByText('En camino')).toBeVisible()
    sinMontos()
  })

  it('nada del pedido en el navegador ni en la URL', async () => {
    apiPedido({}, { pedido: vistaObservador(borrador({ lineas })) })
    abrir()
    await cargado()
    expect(escrituras).toEqual([])
    expect(window.location.pathname).toBe('/insumos/pedido')
    expect(window.location.search + window.location.hash).toBe('')
  })

  it('6.13: el admin sigue viendo los precios, «Productos:», el retracto y el aviso del piloto', async () => {
    apiPedido({}, { pedido: borrador({ lineas }) })
    abrir('admin')
    await cargado()
    expect(within(lineaDe('Pañal adulto M x30')).getByText('$12.990')).toBeVisible()
    expect(screen.getByText('Productos:')).toBeVisible()
    expect(screen.getAllByText('Derecho a retracto:').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Precios de ejemplo.')).toHaveLength(1)
    expect(screen.queryByText('Lo que se va a pedir para María.')).toBeNull()
  })
})

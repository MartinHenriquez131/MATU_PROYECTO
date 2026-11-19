// MATU-112 (H12 y el NO CUMPLE de la analista): ni «Tu pedido» ni «Antes de pagar» prometen
// «Pagas lo mismo». Los textos siguen las condiciones del pedido 0.3, §5, y lenguaje.md 31.
// Solo datos sintéticos.
import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fijarGrupo } from '../src/compartido/api/sesion'
import { PantallaPedido } from '../src/familia/Pedido'
import { familiaFalsa } from './familiaFalsa'
import { PEDIDO } from '../src/familia/textosPedido'
import { ALMACEN, apiPedido, BODEGA, confirmado, conRegionesGlobales, linea, PANAL, persona, PERSONA_ID, TOALLITAS } from './pedidoFalso'

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

function abrir(ruta: string) {
  window.history.replaceState(null, '', ruta)
  const p = persona()
  contexto = familiaFalsa({ persona: p, personas: [p], personaId: PERSONA_ID, rol: 'admin', capa3: true, intencionPedido: null, llegadaPedido: null, direccionDesdeGrupo: false } as never)
  return conRegionesGlobales(<PantallaPedido />)
}

const PROMESAS_VIEJAS = [/pagas lo mismo/i, /lo buscamos en otro comercio y pagas lo mismo/i, /Si al retirar falta un producto/]

describe('MATU-112: «Si falta» sin «Pagas lo mismo»', () => {
  it('«Tu pedido»: «Buscarlo en otro comercio» dice que el precio se ve antes de pagar', async () => {
    apiPedido({})
    abrir('/insumos/pedido')
    await screen.findByRole('heading', { level: 2, name: 'Pañal adulto M x30' })
    expect(screen.getAllByText('El mismo producto. Si cambia el precio, lo ves antes de pagar.').length).toBeGreaterThan(0)
    const texto = document.body.textContent ?? ''
    for (const vieja of PROMESAS_VIEJAS) expect(texto).not.toMatch(vieja)
  })

  it('«Antes de pagar»: «Si falta un producto» dice que se anula el cobro el mismo día', async () => {
    apiPedido({}, { pedido: confirmado() })
    abrir('/insumos/pedido/resumen')
    await screen.findByRole('heading', { level: 1, name: 'Antes de pagar' })
    const siFalta = screen.getByRole('region', { name: 'Si falta un producto' })
    expect(
      within(siFalta).getByText(
        'Durante el piloto, si falta un producto después de pagar, anulamos su cobro el mismo día, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco.',
      ),
    ).toBeVisible()
    const texto = document.body.textContent ?? ''
    for (const vieja of PROMESAS_VIEJAS) expect(texto).not.toMatch(vieja)
  })
})

// MATU-115 (2, decisión de Jorge del 17-11): buscar en otro comercio solo vale antes de pagar. Sacar el
// producto y devolver su precio vale antes y después, y no cambia.
describe('MATU-115: «Si falta antes de pagar»', () => {
  const lineas = [linea(PANAL, ALMACEN, 2, 12990), linea(TOALLITAS, BODEGA, 1, 4290, { regla_faltante: 'quitar' })]
  const VIEJO = 'Si falta: lo buscamos en otro comercio.'
  const NUEVO = 'Si falta antes de pagar: lo buscamos en otro comercio.'

  it('el texto, y los de «Sacarlo del pedido» sin cambios', () => {
    expect(PEDIDO.siFaltaOtro).toBe(NUEVO)
    expect(PEDIDO.siFaltaQuitar).toBe('Si falta: lo sacamos y te devolvemos su precio.')
    expect(PEDIDO.siFaltaQuitarSeInforma).toBe('Si falta: lo sacamos del pedido.')
  })

  it.each([
    ['el carrito con el total confirmado', '/insumos/pedido', 2, 'Pedido'],
    ['el resumen antes de pagar', '/insumos/pedido/resumen', 1, 'Antes de pagar'],
  ] as const)('%s: cada línea con «Buscarlo en otro comercio» lo dice; ninguna dice el texto viejo', async (_, ruta, nivel, titulo) => {
    apiPedido({}, { pedido: confirmado({ lineas }) })
    abrir(ruta)
    if (nivel === 1) await screen.findByRole('heading', { level: 1, name: titulo })
    else await screen.findByRole('heading', { level: 2, name: 'Pañal adulto M x30' })
    expect(screen.getAllByText(NUEVO)).toHaveLength(1)
    expect(screen.getAllByText('Si falta: lo sacamos y te devolvemos su precio.')).toHaveLength(1)
    expect(document.body.textContent).not.toContain(VIEJO)
  })
})

// MATU-112 (H12 y el NO CUMPLE de la analista): ni «Tu pedido» ni «Antes de pagar» prometen
// «Pagas lo mismo». Los textos siguen las condiciones del pedido 0.3, §5, y lenguaje.md 31.
// Solo datos sintéticos.
import { screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fijarGrupo } from '../src/compartido/api/sesion'
import { PantallaPedido } from '../src/familia/Pedido'
import { familiaFalsa } from './familiaFalsa'
import { apiPedido, confirmado, conRegionesGlobales, persona, PERSONA_ID } from './pedidoFalso'

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

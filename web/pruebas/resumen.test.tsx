// MATU-61: «Antes de pagar» (especificación 9, C1, C15, C23 y C25). El total y su hora, lo que cambió,
// los productos con su retracto, la boleta («Tu pedido», nunca «Boleta»), el aviso de los 2 minutos sin
// cuenta regresiva, el total vencido sin casilla ni «Pagar», «Volver a confirmar», «Cambiar el pedido»,
// el pagador y las condiciones. Solo datos sintéticos.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { fijarGrupo } from '../src/compartido/api/sesion'
import { PantallaPedido } from '../src/familia/Pedido'
import { familiaFalsa } from './familiaFalsa'
import { ALMACEN, apiPedido, BODEGA, borrador, confirmado, conRegionesGlobales, linea, PANAL, PEDIDO_ID, persona, PERSONA_ID, problema, TOALLITAS, BOLSA } from './pedidoFalso'

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

function abrir(rol: Rol = 'admin') {
  window.history.replaceState(null, '', '/insumos/pedido/resumen')
  const p = persona()
  const vista = rol === 'pagador' ? { id: p.id, nombre: p.nombre, direccion: p.direccion } : p
  contexto = familiaFalsa({ persona: vista, personas: [vista], personaId: PERSONA_ID, rol, capa3: true } as never)
  return conRegionesGlobales(<PantallaPedido />)
}

/** Un total confirmado con un producto que salió, uno con otro precio y uno de otro comercio (9.2). */
function conCambios() {
  return confirmado({
    lineas: [
      linea(PANAL, ALMACEN, 2, 12450, { cambio: { precio_antes: 12990, comercio_antes: null } }),
      linea(TOALLITAS, ALMACEN, 3, 4290, { cambio: { precio_antes: null, comercio_antes: BODEGA }, regla_faltante: 'quitar' }),
    ],
    salieron: [{ producto: { id: BOLSA.id, nombre: BOLSA.nombre, presentacion: BOLSA.presentacion, unidad: 'unidad', unidades_por_envase: 10 }, cantidad: 1, comercio: ALMACEN }],
  })
}
const titulo = () => screen.findByRole('heading', { level: 1, name: 'Antes de pagar' })

describe('Antes de pagar, con el total vigente', () => {
  it('el mismo total en la bajada y en la boleta, «Total» sin IVA, la hora y el cobro único', async () => {
    apiPedido({}, { pedido: confirmado() })
    abrir()
    await titulo()
    // 2 pañales de 12.990 y 1 toallita de 4.290, más 3.990 de envío.
    expect(screen.getByText(/Confirmamos que hay cada producto. El total es/).closest('p')).toHaveTextContent('Confirmamos que hay cada producto. El total es $34.260.')
    const boleta = screen.getByRole('region', { name: 'Tu pedido' })
    expect(within(boleta).getByText('Productos (2)').closest('p')).toHaveTextContent('Productos (2)$30.270')
    expect(within(boleta).getByText('Envío (uno por pedido)').closest('p')).toHaveTextContent('$3.990')
    expect(within(boleta).getByText('Total').closest('p')).toHaveTextContent('Total$34.260')
    expect(within(boleta).getByText('Este total vale hasta las', { exact: false })).toHaveTextContent('Este total vale hasta las 16:45.')
    expect(within(boleta).getByText('Se cobra una sola vez este total, con crédito o con débito. No hay reserva ni cobros después.')).toBeVisible()
    // JC-IVA y 16.20: «IVA» solo en la marca del precio de ejemplo de la línea… que el resumen no lleva; nunca «Boleta» de título.
    const texto = document.body.textContent ?? ''
    expect(texto).not.toMatch(/IVA/)
    expect(screen.queryByRole('heading', { name: /Boleta/ })).toBeNull()
    expect(texto).toContain('En este piloto no se emite boleta.')
    expect(screen.getAllByText('Precios de ejemplo.')).toHaveLength(1)
  })

  it('9.9 y MATU-62 (4): «Pagar {total}» es el único macizo turquesa; la casilla, las condiciones y la salida sin costo', async () => {
    apiPedido({}, { pedido: confirmado() })
    abrir()
    await titulo()
    const pagar = screen.getByRole('button', { name: 'Pagar $34.260' })
    expect(screen.getAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className))).toEqual([pagar])
    const enlace = screen.getByRole('link', { name: 'Condiciones del pedido (se abre en otra pestaña)' })
    expect(enlace).toHaveAttribute('href', '/condiciones-pedido')
    expect(enlace).toHaveAttribute('target', '_blank')
    const casilla = screen.getByRole('checkbox', { name: 'Leí y acepto las condiciones del pedido.' })
    expect(casilla).not.toBeChecked()
    // El enlace va antes que la casilla.
    expect(enlace.compareDocumentPosition(casilla) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    await userEvent.click(casilla)
    expect(casilla).toBeChecked()
    expect(screen.getByText('No pagar no tiene costo.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Cancelar pedido' })).toBeVisible()
  })

  it('C1: los productos con cantidad, precio, subtotal, «Si falta» y el retracto, y la entrega, si falta, quién vende y reclamos', async () => {
    apiPedido({}, { pedido: confirmado() })
    abrir()
    await titulo()
    const productos = screen.getByRole('region', { name: 'Productos' })
    const panal = within(within(productos).getByRole('heading', { level: 3, name: 'Pañal adulto M x30' }).closest('li')!)
    expect(panal.getByText('De Almacén El Ejemplo (comercio ficticio)')).toBeVisible()
    expect(panal.getByText('×', { exact: false }).closest('p')).toHaveTextContent('2 × $12.990')
    expect(panal.getByText('Subtotal:').closest('p')).toHaveTextContent('Subtotal: $25.980')
    expect(panal.getByText('Si falta: lo buscamos en otro comercio.')).toBeVisible()
    expect(panal.getByText('Derecho a retracto:').closest('p')!.className).toMatch(/\btext-lg\b/)
    const entrega = screen.getByRole('region', { name: 'Entrega' })
    expect(within(entrega).getByText('Entrega: Entre 24 y 48 horas hábiles')).toBeVisible()
    expect(within(entrega).getByText('Los Aromos 123, depto 4, La Reina')).toBeVisible()
    expect(within(entrega).getByText('Teléfono de contacto:', { exact: false })).toHaveTextContent('Teléfono de contacto: +56 9 •••• ••37 (tu celular)')
    expect(within(screen.getByRole('region', { name: 'Si falta un producto' })).getByText(/Si al retirar falta un producto, lo buscamos en otro comercio y pagas lo mismo./)).toBeVisible()
    const vende = screen.getByRole('region', { name: 'Quién vende' })
    expect(within(vende).getByText('Vende: MATU, piloto académico, sin persona jurídica. En este piloto no se emite boleta.')).toBeVisible()
    expect(within(vende).getByRole('link', { name: 'cuidaconmatu@gmail.com' })).toHaveAttribute('href', 'mailto:cuidaconmatu@gmail.com')
    // 16.22: «Cambiar el pedido» después de los productos y antes de la entrega, secundario y con su frase.
    const cambiar = screen.getByRole('button', { name: 'Cambiar el pedido' })
    expect(cambiar).toHaveAccessibleDescription('Si cambias algo, antes de pagar confirmamos el total de nuevo.')
    expect(cambiar.className).not.toMatch(/\bbg-turquesa\b/)
    expect(within(productos).getByRole('button', { name: 'Cambiar el pedido' })).toBe(cambiar)
    expect(cambiar.compareDocumentPosition(entrega) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('9.2: lo que cambió, todo junto arriba y en cada línea con palabra e ícono; lo que salió no está en «Productos»', async () => {
    apiPedido({}, { pedido: conCambios() })
    const { amable } = abrir()
    await titulo()
    expect(screen.getByText('Cambió desde tu pedido')).toBeVisible()
    expect(screen.getByText('Ya no hay Bolsa colectora x10. Salió del pedido.')).toBeVisible()
    expect(screen.getByText('Ahora Toallitas húmedas x80 lo prepara Almacén El Ejemplo (comercio ficticio).')).toBeVisible()
    expect(screen.getByText(/Cambió el precio de Pañal adulto M x30: antes/).closest('li')).toHaveTextContent('Cambió el precio de Pañal adulto M x30: antes $12.990, ahora $12.450.')
    await waitFor(() => expect(amable).toHaveTextContent('Cambió desde tu pedido'))
    const productos = screen.getByRole('region', { name: 'Productos' })
    expect(within(productos).queryByText('Bolsa colectora x10')).toBeNull()
    const panal = within(within(productos).getByRole('heading', { level: 3, name: 'Pañal adulto M x30' }).closest('li')!)
    expect(panal.getByText('Cambió el precio').querySelector('svg')!.getAttribute('class')).toMatch(/lucide-arrow-down-up/)
    const toallitas = within(within(productos).getByRole('heading', { level: 3, name: 'Toallitas húmedas x80' }).closest('li')!)
    expect(toallitas.getByText('Otro comercio').querySelector('svg')!.getAttribute('class')).toMatch(/lucide-store/)
    expect(toallitas.getByText('Si falta: lo sacamos y te devolvemos su precio.')).toBeVisible()
    // Nunca se tacha el precio de antes.
    expect(document.querySelector('s, del, .line-through')).toBeNull()
  })

  it('9.5: con menos de 2 minutos, el aviso una vez, sin cuenta regresiva, y «Volver a confirmar» da una hora nueva', async () => {
    const nuevo = confirmado({ vence_en: '2026-11-11T20:00:00Z', vigencia_segundos: 900, etag: 'p3' })
    const api = apiPedido({ 'POST /confirmar$': { status: 200, cuerpo: nuevo } }, { pedido: confirmado({ vigencia_segundos: 60 }) })
    const { amable } = abrir()
    await titulo()
    const aviso = await screen.findByText('Quedan 2 minutos para pagar este total.')
    expect(aviso).toBeVisible()
    await waitFor(() => expect(amable).toHaveTextContent('Quedan 2 minutos para pagar este total.'))
    const boton = screen.getByRole('button', { name: 'Volver a confirmar' })
    expect(boton.className).not.toMatch(/\bbg-turquesa\b/)
    await userEvent.click(boton)
    await waitFor(() => expect(amable).toHaveTextContent('Confirmamos de nuevo. Este total vale hasta las 17:00.'))
    expect(screen.getByRole('region', { name: 'Tu pedido' })).toHaveTextContent('Este total vale hasta las 17:00.')
    expect(screen.queryByText('Quedan 2 minutos para pagar este total.')).toBeNull()
    expect(api.escrituras().map((x) => x.ruta)).toEqual([`/v1/pedidos/${PEDIDO_ID}/confirmar`])
    expect(window.location.pathname).toBe('/insumos/pedido/resumen')
  })

  it('9.5: si al volver a confirmar cambió algo, la casilla se desmarca y se pide revisar', async () => {
    apiPedido({ 'POST /confirmar$': { status: 200, cuerpo: conCambios() } }, { pedido: confirmado({ vigencia_segundos: 30 }) })
    const { amable } = abrir()
    await titulo()
    await userEvent.click(screen.getByRole('checkbox', { name: 'Leí y acepto las condiciones del pedido.' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Volver a confirmar' }))
    await waitFor(() => expect(amable).toHaveTextContent('Revisa lo que cambió antes de pagar.'))
    expect(screen.getByRole('checkbox', { name: 'Leí y acepto las condiciones del pedido.' })).not.toBeChecked()
  })
})

describe('El total vencido (9.6)', () => {
  it('«Venció» en la boleta, sin casilla, condiciones ni «Pagar», y «Volver a confirmar» como único macizo', async () => {
    apiPedido({}, { pedido: confirmado({ estado: 'vencido', vigencia_segundos: 0 }) })
    abrir()
    await titulo()
    const boleta = screen.getByRole('region', { name: 'Tu pedido' })
    expect(within(boleta).getByText('Venció').querySelector('svg')!.getAttribute('class')).toMatch(/lucide-clock/)
    expect(within(boleta).getByText('Este total venció a las', { exact: false })).toHaveTextContent('Este total venció a las 16:45.')
    // Los montos siguen a la vista, sin opacidad.
    expect(within(boleta).getByText('Total').closest('p')).toHaveTextContent('$34.260')
    expect(boleta.outerHTML).not.toMatch(/opacity/)
    expect(screen.getAllByText('Pasaron 15 minutos y el total venció. Vuelve a confirmar para ver lo que hay y su precio.')[0]).toBeVisible()
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(screen.queryByRole('link', { name: /Condiciones del pedido/ })).toBeNull()
    expect(screen.getAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className))).toEqual([screen.getByRole('button', { name: 'Volver a confirmar' })])
    expect(screen.getByText('No pagar no tiene costo.')).toBeVisible()
  })

  it('cuando vence a la vista, el foco que estaba en la casilla pasa al aviso', async () => {
    apiPedido({}, { pedido: confirmado({ vigencia_segundos: 1 }) })
    abrir()
    await titulo()
    const casilla = screen.getByRole('checkbox', { name: 'Leí y acepto las condiciones del pedido.' })
    casilla.focus()
    await waitFor(() => expect(screen.queryByRole('checkbox')).toBeNull(), { timeout: 3000 })
    await waitFor(() => expect(document.activeElement?.textContent).toContain('Pasaron 15 minutos y el total venció.'))
  })

  it('el pagador: el aviso pide que lo vuelva a confirmar quien armó el pedido, sin botones', async () => {
    apiPedido({}, { pedido: confirmado({ estado: 'vencido', vigencia_segundos: 0 }) })
    abrir('pagador')
    await titulo()
    expect(screen.getAllByText('Pasaron 15 minutos y el total venció. Pídele a quien armó el pedido que lo vuelva a confirmar.')[0]).toBeVisible()
    expect(screen.queryByRole('button', { name: /Volver a confirmar|Cambiar|Cancelar/ })).toBeNull()
  })
})

describe('Cambiar el pedido (9.12)', () => {
  it('vuelve al carrito en borrador, sin diálogo, con la nota y los controles', async () => {
    const api = apiPedido({ 'POST /cambiar$': { status: 200, cuerpo: { ...borrador(), etag: 'p3' } } }, { pedido: confirmado() })
    abrir()
    await titulo()
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar el pedido' }))
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(await screen.findByRole('textbox', { name: 'Cantidad Pañal adulto M x30' })).toBeVisible()
    expect(screen.getAllByText('Ya puedes cambiar tu pedido. Cuando termines, toca «Ver el total» para confirmarlo de nuevo.')[0]).toBeVisible()
    expect(String(api.escrituras()[0].cabeceras['Idempotency-Key'])).toMatch(/^[A-Za-z0-9_-]{16,64}$/)
  })

  it('sin conexión: el error bajo el botón y el resumen sigue igual', async () => {
    apiPedido({ 'POST /cambiar$': problema(503, 'servicio-no-disponible') }, { pedido: confirmado() })
    abrir()
    await titulo()
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar el pedido' }))
    expect(await screen.findByText('No pudimos abrir tu pedido para cambiarlo. Revisa tu conexión y vuelve a intentarlo. El total sigue confirmado.')).toBeVisible()
    expect(window.location.pathname).toBe('/insumos/pedido/resumen')
  })

  it('el pagador no ve «Cambiar el pedido», «Cambiar dirección», «Cambiar teléfono» ni «Cancelar pedido»', async () => {
    apiPedido({}, { pedido: confirmado() })
    abrir('pagador')
    await titulo()
    expect(screen.queryByRole('button', { name: /Cambiar|Cancelar pedido/ })).toBeNull()
    expect(screen.queryByText('Si cambias algo, antes de pagar confirmamos el total de nuevo.')).toBeNull()
  })
})

describe('El resumen sin un total confirmado', () => {
  it('con el pedido en borrador, lleva a «Tu pedido»', async () => {
    apiPedido({}, { pedido: borrador() })
    abrir()
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
    expect(await screen.findByRole('heading', { level: 1, name: 'Tu pedido' })).toBeVisible()
  })
})

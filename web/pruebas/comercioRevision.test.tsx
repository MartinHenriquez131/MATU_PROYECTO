// MATU-63, revisión visual del diseñador (13-11): cada corrección con una prueba que falla sin ella.
// P1: el foco tras elegir una parte, «Listo para retirar», O3, los resultados del código y la nota de
// productos; P2: la leyenda dentro de la línea, «Marca cada producto…» anunciado, el foco en cada
// resultado del código, «cancelada» sin 6.8, «Sin disponibles» bajo las cifras y el foco al guardar;
// P3: la leyenda sin `mb-2` y `Volver` alineado a la izquierda. Solo datos sintéticos.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppComercio } from '../src/comercio/AppComercio'
import type { ParteVista } from '../src/compartido/api/comercio'
import { apiComercio, conRegionesVivas, ID, partesDeEjemplo } from './comercioFalso'
import type { RespuestaFalsa } from './apiFalsa'

const u = () => userEvent.setup({ delay: null })
const CAMPO = 'Código de retiro (6 números)'
/** Deja correr los temporizadores y los renders pendientes. */
const asentar = () => new Promise((r) => setTimeout(r, 60))

async function abrirParte(referencia: string, sobre?: (l: string, c: unknown) => RespuestaFalsa | undefined, partes?: ParteVista[]) {
  const api = apiComercio({ sobre, partes })
  window.history.replaceState(null, '', '/comercio')
  const regiones = conRegionesVivas(<AppComercio />)
  await screen.findByRole('heading', { level: 2, name: /Por preparar/ }, { timeout: 5000 })
  const usuario = u()
  await usuario.click(screen.getByRole('button', { name: new RegExp(`Pedido ${referencia}`) }))
  await screen.findByRole('heading', { level: 2, name: 'Productos' }, { timeout: 5000 })
  await asentar()
  return { api, usuario, ...regiones }
}

/**
 * En Chrome, el `setTimeout(…, 0)` con que la pantalla movía el foco corría antes de que React pintara
 * la nota (o con el `h1` de «cargando» todavía montado), y el foco caía en `body`. jsdom con `act`
 * pinta antes, y lo escondía. Aquí un temporizador de 0 ms corre en el acto, como en el navegador:
 * el foco tiene que llegar por un efecto, cuando el elemento ya existe.
 */
beforeEach(() => {
  const real = globalThis.setTimeout
  const inmediato = ((fn: (...a: unknown[]) => void, ms?: number, ...a: unknown[]) => {
    if (!ms) {
      fn(...a)
      return 0
    }
    return real(fn, ms, ...a)
  }) as typeof setTimeout
  vi.spyOn(globalThis, 'setTimeout').mockImplementation(inmediato)
  if (window.setTimeout !== globalThis.setTimeout) vi.spyOn(window, 'setTimeout').mockImplementation(inmediato)
})

const linea = (texto: RegExp) => screen.getByRole('group', { name: texto })
const notaCon = (texto: string) => screen.getByText(texto).closest('[tabindex="-1"]')

describe('P1', () => {
  it('1: al elegir una parte, el foco queda en el h1 del pedido ya cargado (no en body)', async () => {
    await abrirParte('R8T2WQ')
    const h1 = screen.getByRole('heading', { level: 1, name: 'Pedido R8T2WQ' })
    expect(document.activeElement).not.toBe(document.body)
    expect(h1).toHaveFocus()
  })

  it('2: «Listo para retirar» deja el foco en la nota «Pedido listo para retirar.»', async () => {
    const { usuario } = await abrirParte('H6N3VD')
    await usuario.click(within(linea(/Pañal adulto M x30/)).getByRole('radio', { name: 'Lo tengo' }))
    await usuario.click(within(linea(/Suplemento vainilla x12/)).getByRole('radio', { name: 'Lo tengo' }))
    await usuario.click(screen.getByRole('button', { name: 'Listo para retirar' }))
    await screen.findByText('Pedido listo para retirar.')
    await asentar()
    expect(notaCon('Pedido listo para retirar.')).toHaveFocus()
  })

  it('3: O3 se anuncia y deja el foco en la nota de cancelado', async () => {
    const { usuario, amable } = await abrirParte('H6N3VD')
    await usuario.click(within(linea(/Pañal adulto M x30/)).getByRole('radio', { name: 'No lo tengo' }))
    await usuario.click(within(linea(/Suplemento vainilla x12/)).getByRole('radio', { name: 'No lo tengo' }))
    await usuario.click(screen.getByRole('button', { name: 'Avisar que no tengo ninguno' }))
    await waitFor(() =>
      expect(amable).toHaveTextContent('Este pedido se canceló. No lo prepares. Avisaste que no tienes ninguno de estos productos. MATU se encarga del resto.'),
    )
    await asentar()
    expect(notaCon('Este pedido se canceló. No lo prepares.')).toHaveFocus()
  })

  it('3: con `motivo_cancelacion` de la API (decisión 430), el texto de O3 aunque las líneas no digan faltante', async () => {
    const partes = partesDeEjemplo().map((p) => (p.id === ID.cancelada ? { ...p, motivo_cancelacion: 'producto_faltante' as const } : p))
    await abrirParte('Z5V7NQ', undefined, partes)
    expect(screen.getByText('Avisaste que no tienes ninguno de estos productos. MATU se encarga del resto.')).toBeVisible()
  })

  it.each([
    ['correcto', 'Código correcto. Entrega el pedido P5Q8ZA.', { estado: 'retirada', estado_codigo: 'usado' }],
    ['vencido', 'Este código venció.', {}],
    ['usado', 'Este pedido ya se retiró.', { estado: 'retirada' }],
    ['cancelada', 'Este pedido se canceló. No lo prepares.', { estado: 'cancelada' }],
    ['bloqueado', 'El código se bloqueó por demasiados intentos.', {}],
  ] as const)('4: «%s» quita el campo y el foco queda en su nota', async (tipo, titulo, cambio) => {
    const parte = { ...partesDeEjemplo().find((p) => p.id === ID.lista)!, ...cambio }
    const { usuario } = await abrirParte('P5Q8ZA', (l) => (l.endsWith('/validar-codigo') ? { status: 200, cuerpo: { resultado: tipo, intentos_restantes: 0, parte } } : undefined))
    await usuario.type(screen.getByLabelText(CAMPO), '123456')
    await usuario.click(screen.getByRole('button', { name: 'Revisar código' }))
    await screen.findByText(titulo)
    await asentar()
    expect(screen.queryByLabelText(CAMPO)).toBeNull()
    expect(notaCon(titulo)).toHaveFocus()
  })

  it('5: la fila de un producto tiene la columna derecha fija, para que la nota no aplaste la izquierda', async () => {
    apiComercio()
    window.history.replaceState(null, '', '/comercio/productos')
    conRegionesVivas(<AppComercio />)
    const h2 = await screen.findByRole('heading', { level: 2, name: 'Suplemento vainilla x12' })
    const fila = h2.closest('article')!
    expect(fila).toHaveClass('@xl/main:grid-cols-[minmax(0,1fr)_18rem]')
    expect(fila.className).not.toContain('_auto]')
  })
})

describe('P2', () => {
  it('6 y 12: la leyenda va dentro de la tarjeta (float-left w-full, sin mb-2) y el anillo de error no mueve el contenido', async () => {
    const { usuario } = await abrirParte('H6N3VD')
    const grupo = linea(/Suplemento vainilla x12/)
    const leyenda = grupo.querySelector('legend')!
    expect(leyenda).toHaveClass('float-left', 'w-full')
    expect(leyenda).not.toHaveClass('mb-2')
    await usuario.click(screen.getByRole('button', { name: 'Listo para retirar' }))
    const sin = linea(/Pañal adulto M x30/)
    expect(sin).toHaveClass('ring-pronto', '@3xl/main:-mx-3', '@3xl/main:px-3')
  })

  it('7: «Marca cada producto…» se anuncia por la región urgente en cada intento y describe la línea sin marcar', async () => {
    const { usuario, urgente } = await abrirParte('H6N3VD')
    await usuario.click(screen.getByRole('button', { name: 'Listo para retirar' }))
    await waitFor(() => expect(urgente).toHaveTextContent('Marca cada producto: si lo tienes o no.'))
    expect(linea(/Pañal adulto M x30/)).toHaveAccessibleDescription(/Marca cada producto: si lo tienes o no\./)
  })

  it.each([
    ['no es', { status: 200, cuerpo: { resultado: 'no_es', intentos_restantes: 3, parte: partesDeEjemplo().find((p) => p.id === ID.lista) } }, 'Ese código no es el de este pedido.'],
    ['red', { status: 500, cuerpo: { type: '/errores/interno', status: 500 } }, 'No pudimos revisar el código.'],
    ['429', { status: 429, cuerpo: { type: '/errores/demasiados-intentos', status: 429 }, cabeceras: { 'retry-after': '120' } }, 'Hubo muchos intentos con códigos en poco tiempo.'],
  ] as const)('8: «%s»: el foco queda en la nota y el campo sigue con lo escrito', async (_, respuesta, titulo) => {
    const { usuario } = await abrirParte('P5Q8ZA', (l) => (l.endsWith('/validar-codigo') ? (respuesta as RespuestaFalsa) : undefined))
    await usuario.type(screen.getByLabelText(CAMPO), '111222')
    await usuario.click(screen.getByRole('button', { name: 'Revisar código' }))
    await screen.findByText(titulo)
    await asentar()
    expect(notaCon(titulo)).toHaveFocus()
    expect(screen.getByLabelText(CAMPO)).toHaveValue('111222')
  })

  it('9: el código «cancelada» muestra solo su nota, sin la de 6.8', async () => {
    const parte = { ...partesDeEjemplo().find((p) => p.id === ID.lista)!, estado: 'cancelada' as const }
    const { usuario } = await abrirParte('P5Q8ZA', (l) => (l.endsWith('/validar-codigo') ? { status: 200, cuerpo: { resultado: 'cancelada', intentos_restantes: 0, parte } } : undefined))
    await usuario.type(screen.getByLabelText(CAMPO), '123456')
    await usuario.click(screen.getByRole('button', { name: 'Revisar código' }))
    await screen.findByText('No lo entregues. Si ya lo preparaste, vuelve a dejar los productos en su lugar.')
    expect(screen.getAllByText('Este pedido se canceló. No lo prepares.')).toHaveLength(1)
    expect(screen.queryByText('Si ya sacaste productos, vuelve a dejarlos en su lugar.')).toBeNull()
  })

  it('10: «Sin disponibles» va bajo las cifras, fuera del dl', async () => {
    apiComercio()
    window.history.replaceState(null, '', '/comercio/productos')
    conRegionesVivas(<AppComercio />)
    const h2 = await screen.findByRole('heading', { level: 2, name: 'Toallitas húmedas x80' })
    const etiqueta = within(h2.closest('article')!).getByText('Sin disponibles')
    expect(etiqueta.closest('dl')).toBeNull()
    expect(within(h2.closest('article')!).getAllByRole('definition').map((d) => d.textContent)).toEqual(['0', '0', '0'])
  })

  it('11: «Guardar» deja el foco en «Cambiar cuántos tienes» de esa fila', async () => {
    apiComercio()
    window.history.replaceState(null, '', '/comercio/productos')
    conRegionesVivas(<AppComercio />)
    const h2 = await screen.findByRole('heading', { level: 2, name: 'Pañal adulto M x30' })
    const fila = h2.closest('article')!
    const usuario = u()
    await usuario.click(within(fila).getByRole('button', { name: 'Cambiar cuántos tienes' }))
    await usuario.click(within(fila).getByRole('button', { name: 'Guardar' }))
    await within(fila).findByRole('button', { name: 'Cambiar cuántos tienes' })
    await asentar()
    expect(within(fila).getByRole('button', { name: 'Cambiar cuántos tienes' })).toHaveFocus()
  })
})

describe('Especificación v1.1', () => {
  it('7.3: «ya retirado» no agrega la nota 6.7; la hora va en su propia nota', async () => {
    const parte = { ...partesDeEjemplo().find((p) => p.id === ID.lista)!, estado: 'retirada' as const, retirada_en: '2026-11-13T17:25:00Z' }
    const { usuario } = await abrirParte('P5Q8ZA', (l) => (l.endsWith('/validar-codigo') ? { status: 200, cuerpo: { resultado: 'usado', intentos_restantes: 0, parte } } : undefined))
    await usuario.type(screen.getByLabelText(CAMPO), '123456')
    await usuario.click(screen.getByRole('button', { name: 'Revisar código' }))
    await screen.findByText('Este pedido ya se retiró.')
    expect(screen.queryByText('Pedido retirado.')).toBeNull()
    expect(screen.getByText(/Se retiró a las 14:25\./)).toBeVisible()
  })

  it('8.2: la nota «Tienes menos…» va en su propia fila, a todo el ancho', async () => {
    apiComercio()
    window.history.replaceState(null, '', '/comercio/productos')
    conRegionesVivas(<AppComercio />)
    const h2 = await screen.findByRole('heading', { level: 2, name: 'Suplemento vainilla x12' })
    const fila = h2.closest('article')!
    const nota = within(fila).getByText(/Tienes menos de los que ya están apartados/)
    const celda = [...fila.children].find((c) => c.contains(nota))!
    expect(celda).toHaveClass('@xl/main:col-span-2')
  })
})

describe('Segunda revisión (P3)', () => {
  it('«ya retirado» con la parte todavía «lista»: se vuelve a pedir y la Etiqueta dice «Retirado», sin la nota 6.7', async () => {
    const lista = partesDeEjemplo().find((p) => p.id === ID.lista)!
    const { api, usuario } = await abrirParte('P5Q8ZA', (l) => (l.endsWith('/validar-codigo') ? { status: 200, cuerpo: { resultado: 'usado', intentos_restantes: 0, parte: lista } } : undefined))
    Object.assign(api.estado.partes.find((p) => p.id === ID.lista)!, { estado: 'retirada', estado_codigo: 'usado', retirada_en: '2026-11-13T17:25:00Z' })
    await usuario.type(screen.getByLabelText(CAMPO), '123456')
    await usuario.click(screen.getByRole('button', { name: 'Revisar código' }))
    await screen.findByText('Este pedido ya se retiró.')
    expect(await screen.findByText('Retirado', { selector: 'span' })).toBeVisible()
    expect(screen.getByText('Este pedido ya se retiró.')).toBeVisible()
    expect(screen.queryByText('Pedido retirado.')).toBeNull()
  })

  it('con varias líneas sin marcar, «Marca cada producto…» describe a todas', async () => {
    const { usuario } = await abrirParte('H6N3VD')
    await usuario.click(screen.getByRole('button', { name: 'Listo para retirar' }))
    await screen.findByText('Marca cada producto: si lo tienes o no.')
    expect(linea(/Pañal adulto M x30/)).toHaveAccessibleDescription(/Marca cada producto/)
    expect(linea(/Suplemento vainilla x12/)).toHaveAccessibleDescription(/Marca cada producto/)
    // Al marcar una, deja de describirla.
    await usuario.click(within(linea(/Suplemento vainilla x12/)).getByRole('radio', { name: 'Lo tengo' }))
    expect(linea(/Suplemento vainilla x12/)).not.toHaveAccessibleDescription(/Marca cada producto/)
  })
})

describe('P3', () => {
  it('13: «Volver a los pedidos» alinea su texto a la izquierda', async () => {
    await abrirParte('R8T2WQ')
    expect(screen.getByRole('button', { name: 'Volver a los pedidos' })).toHaveClass('text-left')
  })
})

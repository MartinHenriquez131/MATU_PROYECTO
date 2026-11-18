// MATU-76 (especificación docs/diseno/matu-76-avisos-pedido.md, sección 2): «Tu cuenta» con las tres
// tarjetas de avisos. A, los insumos; B, «Avisos de tus pedidos», con la nota fija del dinero en el
// `aria-describedby` de «Por correo», y C, «Este teléfono», como tarjeta propia con la regla E4 ampliada.
// Las dos preferencias se guardan por separado con el mismo `PUT /v1/yo/avisos` (decisión 473). Solo datos sintéticos.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AvisosCuenta } from '../src/familia/AvisosCuenta'
import { TuCuenta } from '../src/familia/Cuenta'
import { apiCuenta, problema, type Respuesta } from './dondeEntrasteFalso'
import { familiaFalsa } from './familiaFalsa'
import { responderPolitica } from './politicaFalsa'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa(),
}))

const u = () => userEvent.setup({ delay: null })
const INSUMO = 'Avisos cuando un insumo se está acabando'
const PEDIDO = 'Avisos de tus pedidos'
const DINERO = 'Si es sobre tu dinero, como una devolución, un producto que faltó o una cancelación, el correo te llega igual.'
const PILOTO = 'En el piloto los avisos se prueban sin enviarse: no te llegará nada.'

const grupo = (nombre: string) => screen.getByRole('group', { name: nombre })
const casilla = (g: string, nombre: string) => within(grupo(g)).getByRole('checkbox', { name: nombre })
const listo = () => screen.findAllByRole('checkbox')
/** La tarjeta C, con su h2. */
const tarjetaC = () => screen.getByRole('heading', { level: 2, name: /^Este (teléfono|computador|navegador)$/ }).closest('section') as HTMLElement

function enEspera() {
  let soltar!: (r: Respuesta) => void
  const promesa = new Promise<Respuesta>((r) => (soltar = r))
  return { manejador: () => promesa, soltar }
}

/** Un servidor con memoria, como el de verdad: sin `pedido` en el cuerpo, la del pedido no cambia. */
function servidor(inicial = { correo: true, push: true, pedido: { correo: true, push: true } }) {
  let actual = inicial
  return {
    'GET ^/v1/yo/avisos$': () => ({ status: 200, cuerpo: actual }),
    'PUT ^/v1/yo/avisos$': (p: { cuerpo?: unknown }) => {
      const c = p.cuerpo as typeof actual & { pedido?: typeof actual.pedido }
      actual = { correo: c.correo, push: c.push, pedido: c.pedido ?? actual.pedido }
      return { status: 200, cuerpo: actual }
    },
  }
}

describe('MATU-76: la tarjeta B, «Avisos de tus pedidos» (2.5)', () => {
  it('su leyenda h2, la ayuda y el alcance en la descripción del grupo; «Por correo» y «En tus teléfonos»', async () => {
    apiCuenta()
    render(<AvisosCuenta />)
    await listo()
    const b = grupo(PEDIDO)
    expect(within(b).getByRole('heading', { level: 2, name: PEDIDO })).toHaveClass('text-xl', 'font-bold')
    expect(b).toHaveAccessibleDescription('Te avisamos cuando hay una novedad en un pedido que pagaste. El aviso no dice qué pedido ni qué productos. Vale para todos tus grupos.')
    expect(within(b).getAllByRole('checkbox').map((c) => c.closest('label')!.textContent)).toEqual(['Por correo', 'En tus teléfonos'])
    for (const c of within(b).getAllByRole('checkbox')) expect(c.closest('label')).toHaveClass('min-h-12')
  })

  it('la nota del dinero está bajo «Por correo», en su aria-describedby, sin ícono ni color propio, marcada o no', async () => {
    apiCuenta(servidor())
    render(<AvisosCuenta />)
    await listo()
    const correo = casilla(PEDIDO, 'Por correo')
    expect(correo).toBeChecked()
    expect(correo).toHaveAccessibleDescription(DINERO)
    const nota = screen.getByText(DINERO)
    expect(nota.tagName).toBe('P')
    expect(nota).toHaveClass('ps-9', 'text-base', 'text-tenue')
    expect(nota.className).not.toMatch(/\bbg-|\bborder|\btext-(atenta|pronto|ok|turquesa)\b/)
    expect(nota.querySelector('svg')).toBeNull()
    // Justo después de la etiqueta de «Por correo».
    expect(correo.closest('label')!.nextElementSibling).toBe(nota)
    // La casilla «Por correo» de la A no la tiene.
    expect(casilla(INSUMO, 'Por correo')).not.toHaveAccessibleDescription(DINERO)

    await u().click(correo)
    await within(grupo(PEDIDO)).findByText('Guardamos tus avisos.')
    expect(correo).not.toBeChecked()
    expect(screen.getByText(DINERO)).toBeVisible()
    expect(correo).toHaveAccessibleDescription(DINERO)
    // 7: ningún control deshabilitado para el correo del dinero.
    expect(within(grupo(PEDIDO)).getAllByRole('checkbox')).toHaveLength(2)
    expect(document.querySelector('input:disabled')).toBeNull()
  })

  it('17: ningún texto nombra el código de retiro, el comercio ni la referencia, ni dice «te devolvimos»', async () => {
    apiCuenta()
    const { container } = render(<AvisosCuenta />)
    await listo()
    expect(container.textContent).not.toMatch(/c[oó]digo de retiro|comercio|referencia|te devolvimos|faltante/i)
  })
})

describe('MATU-76: las dos preferencias se guardan por separado (2.6, decisión 473)', () => {
  it('tocar la B manda las dos con `pedido`; tocar la A, sin `pedido`, y la B no cambia', async () => {
    const api = apiCuenta(servidor())
    render(<AvisosCuenta />)
    await listo()
    await u().click(casilla(PEDIDO, 'Por correo'))
    await within(grupo(PEDIDO)).findByText('Guardamos tus avisos.')
    expect(api.de('PUT', '/v1/yo/avisos')[0].cuerpo).toEqual({ correo: true, push: true, pedido: { correo: false, push: true } })

    await u().click(casilla(INSUMO, 'En tus teléfonos'))
    await within(grupo(INSUMO)).findByText('Guardamos tus avisos.')
    expect(api.de('PUT', '/v1/yo/avisos')[1].cuerpo).toEqual({ correo: true, push: false })
    expect(casilla(PEDIDO, 'Por correo')).not.toBeChecked()
    expect(casilla(PEDIDO, 'En tus teléfonos')).toBeChecked()
    expect(casilla(INSUMO, 'Por correo')).toBeChecked()
    expect(casilla(INSUMO, 'En tus teléfonos')).not.toBeChecked()
    // 9 y P3: «Guardamos tus avisos.» solo en la tarjeta tocada; el de la B se borró al tocar la A.
    expect(within(grupo(PEDIDO)).queryByText('Guardamos tus avisos.')).toBeNull()
    expect(screen.getAllByText('Guardamos tus avisos.')).toHaveLength(1)
  })

  it('mientras guarda la B, las cuatro casillas con aria-disabled, aria-busy en la tocada y «Guardando…» solo en la B', async () => {
    const espera = enEspera()
    const api = apiCuenta({ 'PUT ^/v1/yo/avisos$': espera.manejador })
    render(<AvisosCuenta />)
    await listo()
    const telefonos = casilla(PEDIDO, 'En tus teléfonos')
    await u().click(telefonos)
    expect(await within(grupo(PEDIDO)).findByText('Guardando…')).toBeInTheDocument()
    expect(within(grupo(INSUMO)).queryByText('Guardando…')).toBeNull()
    const todas = screen.getAllByRole('checkbox')
    expect(todas).toHaveLength(4)
    for (const c of todas) {
      expect(c).toHaveAttribute('aria-disabled', 'true')
      expect(c).not.toBeDisabled()
      expect(c).toHaveClass('aria-disabled:not-focus-visible:opacity-60')
    }
    expect(todas.filter((c) => c.getAttribute('aria-busy') === 'true')).toEqual([telefonos])
    // Otro toque, en la otra tarjeta, no pide nada.
    await u().click(casilla(INSUMO, 'Por correo'))
    expect(api.de('PUT', '/v1/yo/avisos')).toHaveLength(1)

    espera.soltar({ status: 200, cuerpo: { correo: true, push: true, pedido: { correo: true, push: false } } })
    expect(await within(grupo(PEDIDO)).findByText('Guardamos tus avisos.')).toBeInTheDocument()
    expect(telefonos).not.toBeChecked()
    await vi.waitFor(() => expect(telefonos).toHaveFocus())
  })

  it('error al guardar la B: el error en la B, la casilla vuelve a lo de antes y el foco se queda en ella', async () => {
    apiCuenta({ 'PUT ^/v1/yo/avisos$': problema(500) })
    render(<AvisosCuenta />)
    await listo()
    const correo = casilla(PEDIDO, 'Por correo')
    await u().click(correo)
    const error = await within(grupo(PEDIDO)).findByText('No pudimos guardar. Revisa tu conexión y vuelve a intentarlo.')
    expect(error.closest('[data-aviso]')).toHaveAttribute('data-aviso', 'alert')
    expect(within(grupo(INSUMO)).queryByText(/No pudimos guardar/)).toBeNull()
    expect(correo).toBeChecked()
    await vi.waitFor(() => expect(correo).toHaveFocus())
  })

  it('cargando: las dos tarjetas sin casillas ni nota del dinero, y sin tarjeta C', async () => {
    apiCuenta({ 'GET ^/v1/yo/avisos$': () => new Promise<Respuesta>(() => {}) })
    render(<AvisosCuenta />)
    await screen.findByRole('group', { name: PEDIDO })
    expect(screen.queryByRole('checkbox')).toBeNull()
    expect(screen.queryByText(DINERO)).toBeNull()
    expect(screen.queryByRole('heading', { name: /^Este / })).toBeNull()
  })

  it('P3 de la revisión: mientras carga, «Cargando…» se ve en A y en B, pero hay un solo role="status", el de la A', async () => {
    apiCuenta({ 'GET ^/v1/yo/avisos$': () => new Promise<Respuesta>(() => {}) })
    render(<AvisosCuenta />)
    await vi.waitFor(() => expect(screen.getAllByText('Cargando…')).toHaveLength(2))
    const estados = screen.getAllByRole('status')
    expect(estados).toHaveLength(1)
    expect(grupo(INSUMO)).toContainElement(estados[0])
    expect(within(grupo(PEDIDO)).getByText('Cargando…')).not.toHaveAttribute('role')
  })
})

describe('MATU-76: la tarjeta C, «Este teléfono» (2.1 y 2.7)', () => {
  it.each([
    ['solo la del insumo', true, false],
    ['solo la del pedido', false, true],
    ['las dos', true, true],
  ])('se ve con %s «En tus teléfonos» marcada', async (_, insumo, pedido) => {
    apiCuenta({ 'GET ^/v1/yo/avisos$': { status: 200, cuerpo: { correo: true, push: insumo, pedido: { correo: true, push: pedido } } } })
    render(<AvisosCuenta />)
    await listo()
    const c = await vi.waitFor(() => tarjetaC())
    expect(c.closest('[hidden]')).toBeNull()
  })

  it('con las dos desmarcadas no se ve, y al marcar la del pedido vuelve', async () => {
    apiCuenta(servidor({ correo: true, push: false, pedido: { correo: true, push: false } }))
    render(<AvisosCuenta />)
    await listo()
    await vi.waitFor(() => expect(screen.queryByRole('heading', { name: /^Este / })).toBeNull())
    await u().click(casilla(PEDIDO, 'En tus teléfonos'))
    await within(grupo(PEDIDO)).findByText('Guardamos tus avisos.')
    await vi.waitFor(() => expect(tarjetaC().closest('[hidden]')).toBeNull())
  })

  it('una tarjeta propia: section con h2, su ayuda, la misma superficie, sin border-l-4 ni ps-4; fuera de la A', async () => {
    apiCuenta()
    render(<AvisosCuenta />)
    await listo()
    const c = await vi.waitFor(() => tarjetaC())
    expect(c.tagName).toBe('SECTION')
    expect(c).toHaveAccessibleName(/^Este /)
    expect(within(c).getByRole('heading', { level: 2 })).toHaveClass('text-xl', 'font-bold')
    expect(within(c).getByText('Aquí te llegan los avisos que marcaste «En tus teléfonos», si los activas.')).toHaveClass('text-base', 'text-tenue')
    expect(c).toHaveClass('bg-hoja', 'rounded-xl', 'ring-1', 'ring-linea', 'px-4', 'py-4', 'max-w-xl')
    expect(c.className).not.toMatch(/border-l-4|\bps-4\b/)
    expect(within(grupo(INSUMO)).queryByRole('heading', { name: /^Este / })).toBeNull()
    expect(within(grupo(INSUMO)).queryByText(PILOTO)).toBeNull()
  })

  it('en G (fuera del equipo del piloto) la ayuda de C no se muestra', async () => {
    apiCuenta({ 'GET ^/v1/dispositivos/actual/push$': { status: 200, cuerpo: { clave_publica: `B${'A'.repeat(86)}`, permitido: false, registrado: false, envio_simulado: true } } })
    render(<AvisosCuenta />)
    await screen.findByText('En el piloto, los avisos en el teléfono solo se prueban en los teléfonos del equipo de MATU.')
    expect(screen.queryByText(/Aquí te llegan los avisos/)).toBeNull()
  })
})

describe('MATU-76: «Tu cuenta» con las tres tarjetas (criterios 1 a 4 y 14)', () => {
  it('A, B y C en orden, con mt-6 entre ellas y la nota del piloto una sola vez, al final', async () => {
    window.history.replaceState(null, '', '/cuenta')
    const guardar = vi.spyOn(Storage.prototype, 'setItem')
    apiCuenta()
    responderPolitica()
    const { container } = render(<TuCuenta />)
    await listo()
    await vi.waitFor(() => tarjetaC())
    const a = grupo(INSUMO).parentElement!
    const b = grupo(PEDIDO).parentElement!
    const c = tarjetaC().parentElement!
    expect(a.nextElementSibling).toBe(b)
    expect(b.nextElementSibling).toBe(c)
    expect(b).toHaveClass('mt-6')
    expect(c).toHaveClass('mt-6')
    for (const t of [a, b]) expect(t).toHaveClass('bg-hoja', 'rounded-xl', 'ring-1', 'ring-linea', 'px-4', 'py-4', 'max-w-xl')
    const piloto = screen.getAllByText(PILOTO)
    expect(piloto).toHaveLength(1)
    expect(c.nextElementSibling!.contains(piloto[0])).toBe(true)
    expect(container.innerHTML).not.toMatch(/\bbg-pino\b|\bbg-turquesa\b/)
    expect(container.innerHTML).not.toMatch(/text-(xs|sm)\b|text-\[/)
    expect(guardar).not.toHaveBeenCalled()
    expect(window.location.pathname + window.location.search + window.location.hash).toBe('/cuenta')
  })
})

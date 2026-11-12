// MATU-54 (5.5 y decisión del orquestador): «Dónde entraste» muestra «Pediste una copia de tus datos»
// con el ícono Download y la cola de solo la hora, cuando `/v1/yo/ingresos` lo manda. Datos sintéticos.
import { render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DondeEntraste } from '../src/familia/DondeEntraste'
import { apiCuenta, dialogoDeJsdom, fijarAhora } from './dondeEntrasteFalso'
import { familiaFalsa } from './familiaFalsa'
import { responderPolitica } from './politicaFalsa'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa({ salir: vi.fn() } as never),
}))

beforeEach(() => {
  fijarAhora()
  dialogoDeJsdom()
})
afterEach(() => {
  vi.useRealTimers()
})

describe('«Dónde entraste»: la copia pedida (5.5)', () => {
  it('«Pediste una copia de tus datos», con Download en `rocio` y solo la hora', async () => {
    apiCuenta({
      'GET ^/v1/yo/ingresos$': { status: 200, cuerpo: { eventos: [{ tipo: 'pediste_una_copia', ocurrido_en: '2026-11-12T13:14:00Z', dispositivo: null }], hay_mas: false } },
    })
    responderPolitica()
    render(<DondeEntraste />)
    const ingresos = screen.getByRole('region', { name: 'Últimos ingresos' })
    const linea = (await within(ingresos).findByText('Pediste una copia de tus datos')).closest('li')!
    expect(linea).toHaveTextContent('Pediste una copia de tus datosa las 10:14')
    const circulo = linea.querySelector('span[aria-hidden]')!
    expect(circulo).toHaveClass('bg-rocio')
    expect(circulo.querySelector('svg.lucide-download')).not.toBeNull()
  })
})

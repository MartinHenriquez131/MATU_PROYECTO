// MATU-76 (especificación docs/diseno/matu-76-avisos-pedido.md, sección 4): «Tus datos» con «Tus
// avisos» en dos grupos con su h3, la frase del dinero cuando «Por correo» de pedidos está en «No», y
// el tipo de cada aviso enviado («Aviso de insumo» o «Aviso de pedido»), antes del canal. Datos sintéticos.
import { StrictMode } from 'react'
import { render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CopiaDatosCuenta } from '../src/compartido/api/misDatos'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { TusDatos } from '../src/familia/TusDatos'
import { familiaFalsa } from './familiaFalsa'
import { apiCopia, copiaComoRespuesta, copiaCuenta, dialogoDeJsdom, fijarAhora } from './misDatosFalso'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa({ fijar: vi.fn(), anunciar: vi.fn() } as never),
}))

beforeEach(() => {
  fijarAhora()
  dialogoDeJsdom()
  window.history.replaceState(null, '', '/cuenta/datos')
})
afterEach(() => {
  vi.useRealTimers()
})

const DINERO = 'El correo sobre tu dinero te llega igual.'

function abrir(copia: CopiaDatosCuenta) {
  apiCopia(copiaComoRespuesta(copia, 'matu-cuenta-2026-11-12.json'))
  render(
    <StrictMode>
      <RegionesVivas />
      <TusDatos />
    </StrictMode>,
  )
  return screen.findByRole('button', { name: 'Descargar en un archivo' })
}
const bloque = (nombre: string) => screen.getByRole('region', { name: nombre })
const preferencia = (correo: boolean, push: boolean, pedidoCorreo: boolean, pedidoPush: boolean) => ({ correo, push, pedido: { correo: pedidoCorreo, push: pedidoPush } })

describe('MATU-76: «Tus avisos» en dos grupos (4.1)', () => {
  it('cada grupo con su h3 y sus dos filas; con «Por correo» de pedidos en No, la frase del dinero', async () => {
    await abrir(copiaCuenta({ preferencia_avisos: preferencia(true, true, false, true) }))
    const b = bloque('Tus avisos')
    expect(within(b).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['Cuando un insumo se está acabando', 'De tus pedidos'])
    for (const h of within(b).getAllByRole('heading', { level: 3 })) expect(h).toHaveClass('text-lg', 'font-bold')
    expect(b).toHaveTextContent(
      'Cuando un insumo se está acabandoPor correoSíEn tus teléfonosSíDe tus pedidosPor correoNoEn tus teléfonosSíEl correo sobre tu dinero te llega igual.Puedes cambiarlos en Tu cuenta.',
    )
    expect(within(b).getByText(DINERO)).toHaveClass('text-base', 'text-tenue')
  })

  it('con «Por correo» de pedidos en Sí, sin la frase del dinero; el «No» del insumo tampoco la trae', async () => {
    await abrir(copiaCuenta({ preferencia_avisos: preferencia(false, false, true, false) }))
    const b = bloque('Tus avisos')
    expect(within(b).queryByText(DINERO)).toBeNull()
    expect(b).toHaveTextContent('Cuando un insumo se está acabandoPor correoNoEn tus teléfonosNoDe tus pedidosPor correoSíEn tus teléfonosNoPuedes cambiarlos en Tu cuenta.')
  })
})

describe('MATU-76: el tipo de cada aviso enviado (4.2, D-76-6)', () => {
  it('«Aviso de insumo» o «Aviso de pedido» antes del canal; un tipo desconocido se omite', async () => {
    await abrir(
      copiaCuenta({
        avisos_enviados: [
          { tipo: 'pedido', creado_en: '2026-11-10T08:00:00-03:00', enviado_en: '2026-11-10T08:00:05-03:00', canal: 'correo', resultado: 'en_el_piloto_no_salio' },
          { tipo: 'insumo', creado_en: '2026-11-09T08:00:00-03:00', enviado_en: null, canal: 'push', resultado: 'no_salio' },
          { tipo: 'otro' as never, creado_en: '2026-11-08T08:00:00-03:00', enviado_en: null, canal: 'correo', resultado: 'pendiente' },
        ],
      }),
    )
    const lineas = within(bloque('Avisos que te enviamos')).getAllByRole('listitem')
    expect(lineas.map((l) => l.textContent)).toEqual([
      '10/11/2026 a las 08:00 · Aviso de pedido · Por correo · En el piloto no salió',
      '09/11/2026 a las 08:00 · Aviso de insumo · En tus teléfonos · No salió',
      '08/11/2026 a las 08:00 · Por correo · Todavía no sale',
    ])
    // El ícono sigue diciendo el resultado, no el tipo.
    expect(lineas[0].querySelector('svg.lucide-circle-dashed')).not.toBeNull()
    expect(lineas[1].querySelector('svg.lucide-x')).not.toBeNull()
    expect(bloque('Avisos que te enviamos').textContent).not.toMatch(/c[oó]digo de retiro|comercio|te devolvimos/i)
  })
})

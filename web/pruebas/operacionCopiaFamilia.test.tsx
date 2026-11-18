// MATU-81 (D-81-4, D-81-5, C15, decisión 461): en la copia de los datos de la familia, cada pedido
// muestra «Lo que pasó con tu pedido» con lo que el equipo anotó y cómo se resolvió, sin quién lo
// anotó; el historial dice «El equipo de MATU revisó el pedido {referencia}». Nunca «incidente» ni
// «incidencia». Solo datos sintéticos.
import { configure, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CopiaDatosPersona } from '../src/compartido/api/misDatos'
import { DatosDePersona } from '../src/familia/DatosPersona'
import { familiaFalsa } from './familiaFalsa'
import { antes, apiCopia, copiaComoRespuesta, copiaPersona, dialogoDeJsdom, fijarAhora, hecho, MARIA } from './misDatosFalso'
import { responderPolitica } from './politicaFalsa'

// Con la suite completa en paralelo, montar la consola puede tardar más que el segundo por omisión.
configure({ asyncUtilTimeout: 5000 })

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa({ datosDe: MARIA.id, personas: [MARIA], fijar: vi.fn(), anunciar: vi.fn() } as never),
}))

beforeEach(() => {
  fijarAhora()
  dialogoDeJsdom()
  responderPolitica()
})
afterEach(() => {
  vi.useRealTimers()
})

const MATU = { tipo: 'matu' as const, nombre: null, activo: null }

type LoQuePasoCopia = NonNullable<CopiaDatosPersona['pedidos']>[number]['lo_que_paso'][number]

function conLoQuePaso(items?: LoQuePasoCopia[]): CopiaDatosPersona {
  const base = copiaPersona()
  const [primero, ...resto] = base.pedidos ?? []
  return copiaPersona({
    pedidos: [
      {
        ...primero,
        lo_que_paso: items ?? [
          { tipo: 'faltante', estado: 'resuelta', anotado_en: antes(1, 30), resuelto_en: antes(0, 30), nota: 'El comercio avisó que faltó la crema.', resolucion: 'Se devolvió la crema a la misma tarjeta.', nota_disponible: true },
          { tipo: 'entrega_fallida', estado: 'en_gestion', anotado_en: antes(0, 10), resuelto_en: null, nota: 'Nadie pudo recibir el pedido.', resolucion: null, nota_disponible: true },
        ],
      },
      ...resto,
    ],
    historial: {
      alcance: 'todo',
      hechos: [{ ...hecho('matu_reviso_el_pedido', antes(0, 5), MATU), referencia: '4821' }, hecho('matu_reviso_el_pedido', antes(0, 6), MATU)],
      hay_hechos_sin_asociar: false,
    },
  })
}

async function abrir(c: CopiaDatosPersona) {
  apiCopia(copiaComoRespuesta(c, 'matu-datos-2026-11-17.json'))
  render(<DatosDePersona />)
  await screen.findByRole('button', { name: 'Descargar en un archivo' })
}

describe('MATU-81 en la copia de los datos de la familia', () => {
  it('MATU-115 (P3 de Martín): sin resolución (vacía), «Cómo se resolvió:» no aparece; con resolución, sí', async () => {
    await abrir(
      conLoQuePaso([
        { tipo: 'faltante', estado: 'resuelta', anotado_en: antes(1, 30), resuelto_en: antes(0, 30), nota: 'El comercio avisó que faltó la crema.', resolucion: 'Se devolvió la crema a la misma tarjeta.', nota_disponible: true },
        { tipo: 'otro', estado: 'resuelta', anotado_en: antes(1, 20), resuelto_en: antes(0, 20), nota: 'Una nota sintética.', resolucion: '  ', nota_disponible: true },
      ]),
    )
    const seccion = screen.getByRole('heading', { level: 4, name: 'Lo que pasó con tu pedido' }).closest('section')!
    const [con, sin] = within(seccion).getAllByRole('listitem')
    expect(within(con).getByText('Cómo se resolvió:')).toBeVisible()
    expect(within(sin).queryByText('Cómo se resolvió:')).toBeNull()
    expect(within(sin).getByText(/^Se resolvió el/)).toBeVisible()
  })

  it('«Lo que pasó con tu pedido»: el tipo, el estado con ícono y palabra, cuándo, la nota y cómo se resolvió', async () => {
    await abrir(conLoQuePaso())
    const titulo = screen.getByRole('heading', { level: 4, name: 'Lo que pasó con tu pedido' })
    const seccion = titulo.closest('section')!
    expect(within(seccion).getByText('Faltó un producto')).toBeVisible()
    expect(within(seccion).getByText('Resuelto')).toBeVisible()
    expect(within(seccion).getByText('Resuelto').previousElementSibling).toHaveClass('lucide-circle-check')
    expect(within(seccion).getByText('El comercio avisó que faltó la crema.')).toBeVisible()
    expect(within(seccion).getByText('Se devolvió la crema a la misma tarjeta.', { exact: false })).toBeVisible()
    expect(within(seccion).getByText('Cómo se resolvió:')).toBeVisible()
    expect(within(seccion).getByText('No se pudo entregar')).toBeVisible()
    expect(within(seccion).getByText('MATU lo está revisando')).toBeVisible()
    expect(within(seccion).getAllByText(/^Lo anotamos el/)).toHaveLength(2)
    expect(within(seccion).getAllByText(/^Se resolvió el/)).toHaveLength(1)
    expect(within(seccion).queryByText(/ya no está disponible/)).toBeNull()
    expect(document.body.textContent).not.toMatch(/incidente|incidencia/i)
  })

  it('decisión 471: sin la clave de las notas, «La nota ya no está disponible…» en vez de la nota y la resolución', async () => {
    await abrir(
      conLoQuePaso([
        { tipo: 'faltante', estado: 'resuelta', anotado_en: antes(1, 30), resuelto_en: antes(0, 30), nota: null, resolucion: null, nota_disponible: false },
        { tipo: 'entrega_fallida', estado: 'en_gestion', anotado_en: antes(0, 10), resuelto_en: null, nota: 'Nadie pudo recibir el pedido.', resolucion: null, nota_disponible: true },
      ]),
    )
    const seccion = screen.getByRole('heading', { level: 4, name: 'Lo que pasó con tu pedido' }).closest('section')!
    const [borrada, vigente] = within(seccion).getAllByRole('listitem')
    expect(within(borrada).getByText('Faltó un producto')).toBeVisible()
    expect(within(borrada).getByText('La nota ya no está disponible: se borró con los datos de la persona.')).toBeVisible()
    expect(within(borrada).queryByText('Cómo se resolvió:')).toBeNull()
    expect(within(borrada).getAllByText(/^Se resolvió el/)).toHaveLength(1)
    expect(within(vigente).getByText('Nadie pudo recibir el pedido.')).toBeVisible()
    expect(within(vigente).queryByText(/ya no está disponible/)).toBeNull()
  })

  it('sin nada anotado, el pedido no muestra la sección', async () => {
    await abrir(copiaPersona())
    expect(screen.queryByRole('heading', { name: 'Lo que pasó con tu pedido' })).toBeNull()
  })

  it('el historial: «El equipo de MATU revisó el pedido 4821» en cifras, sin nombre, y la general sin referencia', async () => {
    await abrir(conLoQuePaso())
    const historial = screen.getByRole('region', { name: 'Quién abrió o editó la ficha' })
    const lineas = within(historial).getAllByRole('listitem')
    const conRef = lineas.find((li) => li.textContent?.includes('El equipo de MATU revisó el pedido 4821'))!
    expect(conRef).toBeTruthy()
    expect(within(conRef).getByText('4821')).toHaveClass('cifras')
    expect(conRef.querySelector('.lucide-headset')).not.toBeNull()
    expect(conRef.textContent).not.toContain('·')
    expect(lineas.some((li) => li.textContent?.includes('El equipo de MATU revisó un pedido'))).toBe(true)
    expect(historial.textContent).not.toMatch(/incidente|incidencia/i)
  })
})

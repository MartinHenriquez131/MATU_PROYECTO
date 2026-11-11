// Revisión visual de MATU-61 (P2-1): el detalle de cada opción de «quién da el permiso» va en
// `text-base` (17 px), nunca en `text-sm` (14,9 px). Es el mismo `GrupoOpciones` en tres pantallas:
// la autorización de pedidos (MATU-61), el permiso de los insumos (MATU-36) y la autorización del
// alta (3.5.2). Falla sin `detalleGrande` en cualquiera de las tres. Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { DeclaracionFicha, useDeclaracionFicha } from '../src/familia/Alta'
import { Permiso } from '../src/familia/Insumos'
import { responderCon } from './apiFalsa'

const DETALLES = [
  'María decide por su cuenta y tú registras su decisión.',
  'Tienes un nombramiento legal para representar a esta persona.',
  'Cuidas a esta persona en el día a día, sin un nombramiento legal.',
]

function esperarDetallesGrandes() {
  for (const texto of DETALLES) {
    const detalle = screen.getByText(texto)
    expect(detalle).toHaveClass('text-base')
    expect(detalle).not.toHaveClass('text-sm')
  }
}

function AltaDePrueba() {
  const d = useDeclaracionFicha()
  return <DeclaracionFicha pila="María" d={d} />
}

describe('El detalle de las opciones de quién da el permiso, en 17 px (P2-1)', () => {
  it.each<['consumo' | 'despacho', string]>([
    ['despacho', 'la autorización de pedidos'],
    ['consumo', 'el permiso de los insumos'],
  ])('%s: %s', (finalidad) => {
    responderCon(apiFamilia, { status: 201 })
    render(<Permiso finalidad={finalidad} pila="María" personaId="3c9d4e20-0000-4000-8000-0000000000aa" onListo={vi.fn()} onNoEncontrado={vi.fn()} />)
    esperarDetallesGrandes()
  })

  it('la autorización del alta', () => {
    render(<AltaDePrueba />)
    esperarDetallesGrandes()
  })
})

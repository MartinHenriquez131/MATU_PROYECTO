// MATU-68 (0f0f562): el error de la calidad del permiso de insumos dice «Elige quién da el permiso.»
// (lenguaje 13.2), igual que el alta dice «Elige quién da la autorización.». En la pantalla no se
// puede provocar: `Permiso` empieza con «Cuido a esta persona…» elegida (preselección aprobada en
// MATU-36 y confirmada en MATU-44) y un radio no se puede desmarcar. Por eso la prueba fija dos
// cosas: que la pantalla abre con una calidad elegida, de modo que «Acepto y continúo» nunca muestra
// ese error, y que el texto es el aprobado. Falla con el texto viejo, «Elige en qué calidad das el
// permiso.». Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { Permiso } from '../src/familia/Insumos'
import { INSUMOS } from '../src/familia/textosInsumos'
import { responderCon } from './apiFalsa'

describe('El permiso de insumos: quién da el permiso', () => {
  it('el error de la calidad es el de lenguaje 13.2', () => {
    expect(INSUMOS.errCalidad).toBe('Elige quién da el permiso.')
  })

  it('abre con una calidad elegida: «Acepto y continúo» pide el aviso, no la calidad, y no envía nada', async () => {
    const pedidas = responderCon(apiFamilia, { status: 201 })
    render(<Permiso pila="María" personaId="3c9d4e20-0000-4000-8000-0000000000aa" onListo={vi.fn()} onNoEncontrado={vi.fn()} />)

    expect(screen.getByRole('radio', { name: /Cuido a esta persona/ })).toBeChecked()
    await userEvent.click(screen.getByRole('button', { name: 'Acepto y continúo' }))

    expect(screen.getByRole('checkbox', { name: 'Leí el aviso y lo acepto' })).toBeInvalid()
    expect(screen.queryByText(INSUMOS.errCalidad)).not.toBeInTheDocument()
    expect(pedidas).toEqual([])
  })
})

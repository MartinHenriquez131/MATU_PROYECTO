// MATU-51, revisión visual (P2): a 320 px con el texto al 200 %, el texto oculto «Guardando…»
// reservaba su ancho sin partirse y el botón se cortaba. jsdom no mide, así que la prueba comprueba
// las clases que lo resuelven: la columna puede encogerse bajo su contenido (`minmax(0,1fr)`) y los
// dos textos se parten en cualquier punto (`overflow-wrap: anywhere`).
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Boton } from '../src/compartido/ui/Boton'

describe('Boton con texto de espera', () => {
  it('la celda de los dos textos se encoge y los dos se parten', () => {
    render(<Boton textoOcupado="Guardando…">Ya lo resolví</Boton>)

    const texto = screen.getByText('Ya lo resolví')
    const espera = screen.getByText('Guardando…')
    const celda = texto.parentElement as HTMLElement

    expect(celda).toBe(espera.parentElement)
    expect(celda).toHaveClass('grid', 'min-w-0', 'grid-cols-[minmax(0,1fr)]')
    for (const s of [texto, espera]) {
      expect(s).toHaveClass('[overflow-wrap:anywhere]')
      expect(s).not.toHaveClass('break-words')
    }
  })
})

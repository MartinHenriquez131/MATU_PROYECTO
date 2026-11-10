// MATU-51, revisión visual (P2): a 320 px con el texto al 200 %, el texto oculto «Guardando…»
// reservaba su ancho sin partirse y el botón se cortaba. jsdom no mide, así que la prueba comprueba
// las clases que lo resuelven: la columna puede encogerse bajo su contenido (`minmax(0,1fr)`) y los
// dos textos se parten. Corrección del 10-11 (H1 de Martín, opción A de Jorge): con `break-words` y
// sin guionado, las palabras bajan enteras y solo se corta la que por sí sola no cabe.
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
      expect(s).toHaveClass('break-words')
      expect(s).not.toHaveClass('[overflow-wrap:anywhere]')
      expect(s).not.toHaveClass('hyphens-auto')
    }
  })

  // H1 del 09-11: con `hyphens-auto`, «¿No te llegó? Enviar otro código» quedaba «En-/viar» a 320 px
  // con el texto al 200 %. Ninguna variante guiona ni parte en cualquier punto.
  it.each(['principal', 'secundario', 'texto', 'peligro', 'textoPeligro', 'peligroPrincipal'] as const)(
    '%s: el texto baja palabra por palabra, sin guionado',
    (variante) => {
      render(
        <Boton variante={variante} textoOcupado="Enviando…">
          ¿No te llegó? Enviar otro código
        </Boton>,
      )
      for (const s of [screen.getByText('¿No te llegó? Enviar otro código'), screen.getByText('Enviando…')]) {
        // Sin `max-w-full`, el texto centrado mide lo que su palabra más larga y se sale de la celda.
        expect(s).toHaveClass('break-words', 'max-w-full')
        expect(s.className).not.toMatch(/hyphens|overflow-wrap:anywhere|wrap-anywhere|break-all/)
        expect(s.parentElement).toHaveClass('min-w-0', 'grid-cols-[minmax(0,1fr)]')
      }
    },
  )

  // Segunda revisión visual (P3): con «Ya lo resolví» en dos líneas, «Guardando…» quedaba pegado
  // arriba de la celda. La celda centra los dos textos en los dos ejes.
  it('la celda centra el texto de espera cuando conserva la altura de dos líneas', () => {
    render(<Boton ocupado textoOcupado="Guardando…">Ya lo resolví</Boton>)

    const celda = screen.getByText('Guardando…').parentElement as HTMLElement
    expect(celda).toHaveClass('grid', 'place-items-center')
  })
})

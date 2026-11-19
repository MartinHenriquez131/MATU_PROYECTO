// MATU-121 v2 (docs/diseno/matu-121-nota-icono.md, sección 8): a 320 px con el texto al 200 %, `Volver`
// era `inline-flex` con el chevron en su columna, y «Volver a corregir los datos de María» quedaba de a
// una palabra por línea con la flecha flotando a media altura. En el modo angosto el botón pasa a
// `inline-block` y el chevron va en línea, como en `MensajeError`. Fuera de `angosto:` nada cambia.
// jsdom no mide: se afirma la estructura, con el patrón de avisosCuenta.test.tsx. Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Volver } from '../src/familia/ui'

const TEXTO = 'Volver a corregir los datos de María'

describe('MATU-121 v2: el chevron de Volver va en línea en el modo angosto', () => {
  it('el botón pasa a inline-block en angosto y el chevron lleva sus clases de línea', () => {
    render(<Volver onClick={() => {}}>{TEXTO}</Volver>)
    const boton = screen.getByRole('button', { name: TEXTO })
    expect(boton).toHaveClass('angosto:inline-block')
    const chevron = boton.querySelector(':scope > svg.lucide-chevron-left') as SVGElement
    expect(chevron).not.toBeNull()
    expect(chevron).toHaveAttribute('aria-hidden')
    expect(chevron).toHaveClass('size-5', 'shrink-0', 'angosto:me-1', 'angosto:inline', 'angosto:align-middle')
    // El chevron va primero, al comienzo de la primera línea; el texto no cambia.
    expect(boton.firstElementChild).toBe(chevron)
    expect(boton.textContent).toBe(TEXTO)
  })

  it('fuera de angosto sigue igual: inline-flex, centrado, gap-1 y el área táctil de min-h-12', () => {
    render(<Volver onClick={() => {}}>{TEXTO}</Volver>)
    const boton = screen.getByRole('button', { name: TEXTO })
    expect(boton).toHaveClass(
      'inline-flex',
      'min-h-12',
      'items-center',
      'gap-1',
      'self-start',
      'rounded-lg',
      'pr-2',
      'text-left',
      'font-bold',
      'text-turquesa',
      'hover:underline',
    )
    expect(boton).toHaveAttribute('type', 'button')
  })
})

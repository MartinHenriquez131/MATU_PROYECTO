// Decisión de Jorge del 09-11 (cambia D2): la hoja del relevo ya no muestra el «Por ejemplo» bajo
// cada campo. En «A quién llamar» el ejemplo «+56 9 5555 0102» quedaba justo debajo del teléfono
// real y, en una crisis, se podía llamar al número equivocado. La pregunta guía se mantiene.
// Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { FichaRelevo } from '../src/compartido/api/relevo'
import { PantallaFicha } from '../src/relevo/PantallaFicha'

const PREGUNTAS = [
  '¿Cómo es un día normal para Elena? Puedes contar un día bueno o uno difícil.',
  '¿Qué calma a Elena cuando se angustia?',
  '¿A quién llamar si algo pasa?', // 3.11.5: el relevo no lleva «y no te ubican»
]

function ficha(campos: FichaRelevo['campos']): FichaRelevo {
  return {
    nombre_pila: 'Elena',
    nombre_pila_comparte: 'Carmen',
    vence_en: '2026-11-10T20:00:00Z',
    campos,
    secciones: [],
  }
}

const LLENOS: FichaRelevo['campos'] = {
  rutina: { texto: '08:00 Desayuno con té.' },
  manejo_situaciones: { texto: 'Le hace bien escuchar boleros.' },
  red_apoyo: { texto: 'Carmen, su hija: +56 9 5555 0137' },
}

function sinEjemplos() {
  expect(screen.queryAllByText(/Por ejemplo/)).toHaveLength(0)
  expect(screen.queryAllByText(/5555 0102/)).toHaveLength(0)
  for (const s of document.querySelectorAll('section')) expect(s).not.toHaveAttribute('aria-describedby')
  for (const p of PREGUNTAS) expect(screen.getByText(p)).toBeInTheDocument()
}

describe('la hoja del relevo no muestra los ejemplos', () => {
  it('con los tres campos llenos', () => {
    render(<PantallaFicha ficha={ficha(LLENOS)} onActualizar={async () => 'ok'} />)
    sinEjemplos()
    // 3.11.4: el teléfono va en su propio bloque, así que el texto se busca en el párrafo entero.
    expect(screen.getByText((_, el) => el?.tagName === 'P' && el.textContent === 'Carmen, su hija: +56 9 5555 0137')).toBeInTheDocument()
  })

  it('con un campo vacío', () => {
    render(<PantallaFicha ficha={ficha({ ...LLENOS, red_apoyo: { texto: null } })} onActualizar={async () => 'ok'} />)
    sinEjemplos()
    expect(screen.getByText('Sin completar')).toBeInTheDocument()
  })
})

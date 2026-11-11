// Tarjeta «Relevo: el teléfono escrito en la ficha no se parte, y "A quién llamar" le habla a quien
// reemplaza» (especificación MATU-23, 3.11.5, 10/11/2026). En el relevo la pregunta le habla a quien
// reemplaza; el editor de la familia, donde escribe Carmen, no cambia. Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { FichaRelevo } from '../src/compartido/api/relevo'
import { CAMPOS as CAMPOS_FAMILIA } from '../src/familia/datos'
import { PantallaFicha } from '../src/relevo/PantallaFicha'

function ficha(texto: string | null): FichaRelevo {
  return { nombre_pila: 'Elena', nombre_pila_comparte: 'Carmen', vence_en: '2026-11-12T20:00:00Z', campos: { red_apoyo: { texto } }, secciones: [] }
}

const seccion = () => screen.getByRole('heading', { level: 2, name: 'A quién llamar' }).closest('section') as HTMLElement

describe('3.11.5 · la pregunta de «A quién llamar»', () => {
  it.each([['con texto', 'Rodrigo, su hijo: +56 9 5555 0141'], ['sin completar', null]])('el relevo le habla a quien reemplaza, %s', (_, texto) => {
    render(<PantallaFicha ficha={ficha(texto)} onActualizar={async () => 'ok'} />)
    expect(seccion().querySelector('h2 + p')?.textContent).toBe('¿A quién llamar si algo pasa?')
    expect(document.body.textContent).not.toMatch(/no te ubican/)
    for (const el of document.querySelectorAll('[aria-label], [aria-description]'))
      expect(`${el.getAttribute('aria-label')} ${el.getAttribute('aria-description')}`).not.toMatch(/no te ubican/)
  })

  it('el editor de la familia sigue con «y no te ubican»', () => {
    expect(CAMPOS_FAMILIA.find((c) => c.api === 'red_apoyo')?.pregunta('Elena')).toBe('¿A quién llamar si algo pasa y no te ubican?')
  })
})

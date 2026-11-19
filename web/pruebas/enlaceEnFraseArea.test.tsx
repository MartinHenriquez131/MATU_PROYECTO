// MATU-127 (docs/diseno/matu-126-enlaces-correo.md, 11.2 y 9.2): el área táctil de `EnlaceEnFrase` es
// un `span` en línea, sin posición, con `py-3.5`, que envuelve al `span relative z-1` del texto. Así
// cada renglón de un enlace partido tiene su propio pedazo de área (con la caja absoluta de MATU-126
// quedaba en 0 px de ancho). `jsdom` no mide: se verifica la estructura. Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EnlaceEnFrase } from '../src/compartido/ui/Enlaces'

const CORREO = 'correo.sintetico@ejemplo.cl'
const POSICION_O_CAJA = ['absolute', 'relative', 'inline-block', 'inline-flex', 'block']

describe('EnlaceEnFrase · área táctil por renglón (MATU-127)', () => {
  it('tiene una sola área: un span hijo directo del enlace, en línea, con py-3.5 y sin aria-hidden', () => {
    render(
      <p>
        Pídelo a <EnlaceEnFrase href={`mailto:${CORREO}`}>{CORREO}</EnlaceEnFrase>.
      </p>,
    )
    const enlace = screen.getByRole('link', { name: CORREO })
    const areas = enlace.querySelectorAll('[data-area-tactil]')
    expect(areas).toHaveLength(1)
    const area = areas[0]
    expect(area.tagName).toBe('SPAN')
    expect(area.parentElement).toBe(enlace)
    expect(enlace.children).toHaveLength(1)
    expect(area).toHaveClass('py-3.5')
    // En línea y sin posición: con una caja el enlace dejaría de partirse con la frase (11.2, 3).
    const clases = area.className.split(/\s+/)
    for (const clase of POSICION_O_CAJA) expect(clases).not.toContain(clase)
    expect(clases.some((c) => /^-?inset/.test(c))).toBe(false)
    // Con aria-hidden el enlace se quedaría sin nombre: el área ahora contiene el texto.
    expect(area).not.toHaveAttribute('aria-hidden')
    // El `a` sigue con `relative` y sin relleno vertical ni seudoelemento: el foco sigue al texto.
    expect(enlace).toHaveClass('relative')
    expect(enlace.className).not.toMatch(/(^|\s)(py-|after:)/)
  })

  it('el área envuelve al span relative z-1 del texto, y el nombre del enlace aparece una vez', () => {
    render(<EnlaceEnFrase href="/insumos/pedido">Ver tu pedido</EnlaceEnFrase>)
    const enlaces = screen.getAllByRole('link', { name: 'Ver tu pedido' })
    expect(enlaces).toHaveLength(1)
    const enlace = enlaces[0]
    expect(enlace).toHaveAccessibleName('Ver tu pedido')
    const area = enlace.querySelector('[data-area-tactil]') as HTMLElement
    expect(area.children).toHaveLength(1)
    const texto = area.firstElementChild as HTMLElement
    expect(texto.tagName).toBe('SPAN')
    expect(texto).toHaveClass('relative', 'z-1')
    expect(texto).toHaveTextContent('Ver tu pedido')
    // El área tiene el mismo texto que el enlace, y copiar la frase no agrega nada.
    expect(area.textContent).toBe(enlace.textContent)
    expect(enlace.textContent).toBe('Ver tu pedido')
  })

  it('un mailto: lleva [overflow-wrap:anywhere] en el enlace sin que la pantalla lo pida; otro destino no', () => {
    render(
      <>
        <EnlaceEnFrase href={`mailto:${CORREO}`}>{CORREO}</EnlaceEnFrase>
        <EnlaceEnFrase href={`MAILTO:otro.${CORREO}`}>{`otro.${CORREO}`}</EnlaceEnFrase>
        <EnlaceEnFrase href="https://ejemplo.cl" otraPestana>
          Un sitio de ejemplo (se abre en otra pestaña)
        </EnlaceEnFrase>
      </>,
    )
    expect(screen.getByRole('link', { name: CORREO })).toHaveClass('[overflow-wrap:anywhere]')
    expect(screen.getByRole('link', { name: `otro.${CORREO}` })).toHaveClass('[overflow-wrap:anywhere]')
    expect(screen.getByRole('link', { name: /Un sitio de ejemplo/ })).not.toHaveClass('[overflow-wrap:anywhere]')
  })

  it('la clase que pasa la pantalla se suma a la del componente', () => {
    render(
      <EnlaceEnFrase href={`mailto:${CORREO}`} className="text-base">
        {CORREO}
      </EnlaceEnFrase>,
    )
    expect(screen.getByRole('link', { name: CORREO })).toHaveClass('relative', 'text-base', '[overflow-wrap:anywhere]')
  })
})

// MATU-126 (docs/diseno/matu-126-enlaces-correo.md, 3 y 9.2): el área táctil de `EnlaceEnFrase` es un
// `span` vacío y `aria-hidden` que se puede medir, y el texto va encima de toda área (`z-1`), para que
// el área de un enlace no le quite sus letras al del renglón de arriba. `jsdom` no mide: se verifica
// la estructura. Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EnlaceEnFrase } from '../src/compartido/ui/Enlaces'

const CORREO = 'correo.sintetico@ejemplo.cl'

describe('EnlaceEnFrase · área táctil medible (MATU-126)', () => {
  it('tiene una sola área, vacía y aria-hidden, absoluta y 0,875 rem más alta arriba y abajo', () => {
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
    expect(area).toHaveAttribute('aria-hidden', 'true')
    expect(area).toBeEmptyDOMElement()
    expect(area).toHaveClass('absolute', 'inset-x-0', '-inset-y-3.5')
    // Sin z-index: queda en `auto`, debajo del texto de cualquier enlace (DISENO.md, «Capas»).
    expect(area.className).not.toMatch(/(^|\s)z-/)
    // Sin relleno vertical en el enlace ni seudoelemento: el contorno de foco sigue al texto.
    expect(enlace).toHaveClass('relative')
    expect(enlace.className).not.toMatch(/(^|\s)(py-|after:)/)
  })

  it('el texto va en un span relative z-1, después del área, y el nombre del enlace es solo el texto', () => {
    render(<EnlaceEnFrase href="/insumos/pedido">Ver tu pedido</EnlaceEnFrase>)
    const enlace = screen.getByRole('link', { name: 'Ver tu pedido' })
    expect(enlace).toHaveAccessibleName('Ver tu pedido')
    const [area, texto] = Array.from(enlace.children)
    expect(area).toHaveAttribute('data-area-tactil')
    expect(texto.tagName).toBe('SPAN')
    expect(texto).toHaveClass('relative', 'z-1')
    expect(texto).toHaveTextContent('Ver tu pedido')
    expect(enlace.children).toHaveLength(2)
    // Copiar la frase no agrega nada: todo el texto del enlace es el del span de arriba.
    expect(enlace.textContent).toBe('Ver tu pedido')
  })

  it('un mailto: lleva [overflow-wrap:anywhere] sin que la pantalla lo pida; otro destino no', () => {
    render(
      <>
        <EnlaceEnFrase href={`mailto:${CORREO}`}>{CORREO}</EnlaceEnFrase>
        <EnlaceEnFrase href="https://ejemplo.cl" otraPestana>
          Un sitio de ejemplo (se abre en otra pestaña)
        </EnlaceEnFrase>
      </>,
    )
    expect(screen.getByRole('link', { name: CORREO })).toHaveClass('[overflow-wrap:anywhere]')
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

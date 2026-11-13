// MATU-107 (especificación v3, sección 6): en el modo `angosto` la `Etiqueta` oculta su figura y deja
// solo la palabra, para que «Bloqueado» no se corte. Fuera de `angosto` no cambia nada. jsdom no aplica
// Tailwind: se verifica la clase del componente y que la figura sea hijo directo. Solo datos sintéticos.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { render, screen } from '@testing-library/react'
import { Check, Lock } from 'lucide-react'
import { describe, expect, it } from 'vitest'
import { Etiqueta } from '../src/familia/ui'

const raiz = join(dirname(fileURLToPath(import.meta.url)), '../src')

describe('MATU-107 (6): la Etiqueta sin figura en el modo angosto', () => {
  it('el span oculta en angosto todo svg hijo directo; la palabra queda, y fuera de angosto el svg sigue', () => {
    render(
      <Etiqueta tono="atenta">
        <Lock aria-hidden className="size-4" />
        Bloqueado
      </Etiqueta>,
    )
    const etiqueta = screen.getByText('Bloqueado')
    expect(etiqueta.className.split(/\s+/)).toContain('angosto:[&>svg]:hidden')
    // Ninguna otra clase oculta la figura fuera de angosto: solo la variante.
    expect(etiqueta.className.split(/\s+/).filter((c) => /hidden/.test(c))).toEqual(['angosto:[&>svg]:hidden'])
    const figura = etiqueta.querySelector(':scope > svg')
    expect(figura).not.toBeNull()
    expect(figura!.getAttribute('class')).not.toMatch(/hidden/)
    expect(etiqueta).toHaveTextContent('Bloqueado')
  })

  it('el estado del celular de «Tu cuenta» deja el angosto:hidden en el componente', () => {
    const cuenta = readFileSync(join(raiz, 'familia/Cuenta.tsx'), 'utf-8')
    const estado = cuenta.slice(cuenta.indexOf('function EstadoCelular'), cuenta.indexOf('export function useCorreoPrivacidad'))
    expect(estado).toMatch(/<Check aria-hidden className="size-4"/)
    expect(estado).toMatch(/<Circle aria-hidden className="size-3.5"/)
    expect(estado).not.toMatch(/angosto:hidden/)
    // Sigue siendo hijo directo de la Etiqueta, como pide la regla.
    render(
      <Etiqueta tono="ok">
        <Check aria-hidden className="size-4" strokeWidth={3} />
        Confirmado
      </Etiqueta>,
    )
    expect(screen.getByText('Confirmado').querySelector(':scope > svg.lucide-check')).not.toBeNull()
  })
})

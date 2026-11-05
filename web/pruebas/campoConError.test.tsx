// (a) Un error de campo queda asociado al campo: `aria-invalid` y `aria-describedby` hacia el
// texto del error, además de la ayuda (estrategia de pruebas, sección 7).
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CampoTexto } from '../src/familia/ui'

describe('CampoTexto', () => {
  it('con error, el campo queda inválido y describe la ayuda y el error', () => {
    render(<CampoTexto etiqueta="Tu correo" ayuda="Lo usas para entrar." error="Revisa tu correo." />)

    const campo = screen.getByLabelText('Tu correo')
    expect(campo).toHaveAttribute('aria-invalid', 'true')
    expect(campo).toBeInvalid()
    expect(campo).toHaveAccessibleDescription('Lo usas para entrar. Revisa tu correo.')
    // El error se ve en la página, no solo en la descripción.
    expect(screen.getByText('Revisa tu correo.')).toBeVisible()
  })

  it('sin error, no queda inválido y describe solo la ayuda', () => {
    render(<CampoTexto etiqueta="Tu correo" ayuda="Lo usas para entrar." />)

    const campo = screen.getByLabelText('Tu correo')
    expect(campo).not.toHaveAttribute('aria-invalid')
    expect(campo).toHaveAccessibleDescription('Lo usas para entrar.')
  })
})

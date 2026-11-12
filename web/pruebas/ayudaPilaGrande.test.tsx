// Revisión visual de MATU-61: en «¿A quién cuidas?» (/empezar/persona), la ayuda «Es el nombre que
// verá quien te reemplace.» va en `text-base` (17 px), no en `text-sm` (14,9 px). Desde MATU-93
// es lo que hace `CampoTexto` por omisión (antes, la prop `ayudaGrande`). Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AQuien } from '../src/familia/Alta'
import { familiaFalsa } from './familiaFalsa'

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

describe('¿A quién cuidas?: la ayuda de cómo le dicen', () => {
  it('va en 17 px y describe su campo', () => {
    contexto = familiaFalsa({ borrador: { nombre: '', pila: '', apoyo: null } } as never)
    window.history.replaceState(null, '', '/empezar/persona')
    render(<AQuien />)
    const ayuda = screen.getByText('Es el nombre que verá quien te reemplace.')
    expect(ayuda).toHaveClass('text-base')
    expect(ayuda).not.toHaveClass('text-sm')
    expect(document.getElementById(ayuda.id.replace(/-a$/, ''))).toHaveAccessibleDescription('Es el nombre que verá quien te reemplace.')
  })
})

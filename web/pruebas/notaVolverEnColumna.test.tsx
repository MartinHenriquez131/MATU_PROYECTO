// MATU-121 (docs/diseno/matu-121-nota-icono.md, 3.3 y 8; H2 del QA): en «Autoriza el registro», cuando
// la API rechaza un dato del paso 1, la nota empieza con un `Volver` que trae su propio chevron. Esa nota
// lleva `iconoEnLinea={false}` (Alta.tsx): su ícono se queda en la columna también en el modo angosto, y
// el chevron del botón va en línea. Si alguien quita la propiedad, el ícono de la nota pasaría a flotar
// sobre el botón y esta prueba falla. jsdom no mide: se afirma la estructura, con el patrón de
// notaIconoAngosto.test.tsx. Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { Autorizacion } from '../src/familia/Alta'
import { problema422, responderCon } from './apiFalsa'
import { plazosConCarga } from './conCarga'
import { familiaFalsa } from './familiaFalsa'

plazosConCarga()

const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000121g1'

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

describe('MATU-121: la nota «Volver a corregir» deja su ícono en la columna', () => {
  it('tras un 422 del paso 1, el ícono de la nota va en su columna y no en línea; el chevron de Volver, en línea', async () => {
    contexto = familiaFalsa({ borrador: { nombre: 'María Soto', pila: 'María', apoyo: 'apoyo_total' }, grupoId: GRUPO_ID, personas: [] } as never)
    window.history.replaceState(null, '', '/empezar/autorizacion')
    responderCon(apiFamilia, { status: 422, cuerpo: problema422({ campo: 'nombre_pila', tipo: 'string_too_long' }) })
    render(<Autorizacion />)

    const u = userEvent.setup()
    await u.click(screen.getByRole('radio', { name: /María lo autoriza y yo lo registro/ }))
    await u.click(screen.getByRole('button', { name: 'Acepto y registro a María' }))

    const boton = await screen.findByRole('button', { name: 'Volver a corregir los datos de María' })
    const nota = boton.closest('.flex.max-w-prose') as HTMLElement
    expect(nota).not.toBeNull()
    expect(nota).toHaveClass('bg-pronto-fondo')

    // El ícono de la nota es hijo directo: en su columna, sin el `contents angosto:hidden` del modo en línea.
    const icono = nota.querySelector(':scope > svg.lucide-circle-alert')
    expect(icono).not.toBeNull()
    expect(icono).toHaveAttribute('aria-hidden')
    expect(nota.querySelector(':scope > span.contents')).toBeNull()
    expect(nota.querySelector('[class*="angosto:hidden"]')).toBeNull()
    // Ninguna copia flotante al comienzo del texto: un solo dibujo de la nota.
    expect(nota.querySelector('[class*="angosto:float-start"]')).toBeNull()
    expect(nota.querySelector('.leading-relaxed')).not.toHaveClass('angosto:flow-root')
    expect(nota.querySelectorAll('svg.lucide-circle-alert')).toHaveLength(1)

    // El botón empieza el cuerpo, y su chevron es el que va en línea (sección 8).
    expect(nota.querySelector('.leading-relaxed')!.firstElementChild).toBe(boton)
    expect(boton).toHaveClass('min-h-12', 'angosto:inline-block')
    expect(boton.querySelector(':scope > svg.lucide-chevron-left')).toHaveClass('angosto:inline', 'angosto:align-middle')
  })
})

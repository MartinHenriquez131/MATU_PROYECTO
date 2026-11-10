// MATU-57, P2 del diseñador: a 320 px con el texto al 200 %, la nota «Lo que declaras» partía
// «representante» a la mitad porque el ícono iba al lado del título. Con `iconoEnLinea`, en modo
// angosto el ícono va en la primera línea del título (`hidden angosto:inline-flex`) y el ícono del
// costado se oculta (`contents angosto:hidden`). La prueba cubre las tres pantallas de permiso: la
// declaración de la ficha (alta y grupo usan `DeclaracionFicha`) y el permiso de insumos. Falla sin
// el cambio: el título no tiene ícono propio y el del costado no se oculta. Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DeclaracionFicha, useDeclaracionFicha } from '../src/familia/Alta'
import { Permiso } from '../src/familia/Insumos'
import { AUTORIZACION } from '../src/familia/textos'

function iconoEnLaLineaDelTitulo() {
  const p = screen.getByText(AUTORIZACION.declaras)
  const enLinea = p.querySelector(':scope > span > svg')?.parentElement
  expect(enLinea).toHaveClass('hidden', 'angosto:inline-flex')
  const nota = p.closest('.flex.max-w-prose')!
  expect(nota.querySelector(':scope > span.contents')).toHaveClass('angosto:hidden')
}

function Declaracion() {
  const d = useDeclaracionFicha()
  return <DeclaracionFicha pila="María" d={d} />
}

describe('La nota «Lo que declaras» lleva el ícono en línea', () => {
  it('en la autorización de la ficha (alta y grupo)', async () => {
    render(<Declaracion />)
    await userEvent.click(screen.getByRole('radio', { name: /María lo autoriza y yo lo registro/ }))
    iconoEnLaLineaDelTitulo()
  })

  it('en el permiso de insumos', () => {
    render(<Permiso pila="María" personaId="3c9d4e20-0000-4000-8000-0000000000aa" onListo={vi.fn()} onNoEncontrado={vi.fn()} />)
    iconoEnLaLineaDelTitulo()
  })
})

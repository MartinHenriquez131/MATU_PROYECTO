// MATU-57 (revisión visual, P2): en la forma lista de `GrupoOpciones`, a 320 px con el texto al 200 %
// el texto junto al indicador partía palabras. DISENO.md (sección 6, «Opción (radio) y chip», opción C):
// en angosto el texto va bajo el indicador. jsdom no mide: se comprueban las clases. Datos sintéticos.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GrupoOpciones } from '../src/familia/ui'

describe('La opción de forma lista en angosto', () => {
  it('pone el texto bajo el indicador, con menos separación y relleno', () => {
    render(
      <GrupoOpciones
        leyenda="¿Con qué frecuencia?"
        nombre="frecuencia"
        valor={null}
        onCambio={() => {}}
        opciones={[
          { valor: 'diaria', texto: 'Todos los días' },
          { valor: 'semanal', texto: 'Una vez a la semana' },
        ]}
      />,
    )
    const etiqueta = screen.getByRole('radio', { name: 'Todos los días' }).closest('label')
    expect(etiqueta).toHaveClass('angosto:flex-col', 'angosto:gap-2', 'angosto:px-3')
    // Fuera de angosto no cambia.
    expect(etiqueta).toHaveClass('flex', 'items-start', 'gap-3', 'px-4', 'py-3')
  })
})

// Las regiones vivas de main.tsx, montadas antes de la pantalla como en la app. Se devuelven antes
// de cualquier acción: así cada prueba comprueba que el aviso llega a una región que ya existía.
import type { ReactElement } from 'react'
import { render, screen } from '@testing-library/react'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'

export function conRegiones(pantalla: ReactElement) {
  render(
    <>
      <RegionesVivas />
      {pantalla}
    </>,
  )
  return { amable: screen.getByRole('status'), urgente: screen.getByRole('alert') }
}

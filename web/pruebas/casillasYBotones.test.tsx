// MATU-68 (docs/diseno/matu-68-ajustes.md, criterios 1 y 4): una sola medida de casilla en la app de
// familia, `size-6`, y ningún botón con el relleno achicado a mano (`px-0.5` o un relleno con `!`).
// jsdom no mide: se comprueban las clases del aviso de cuidador de hecho y el texto de web/src/familia.
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AvisoCuidadorDeHecho } from '../src/familia/ui'

const carpeta = join(dirname(fileURLToPath(import.meta.url)), '../src/familia/')
const fuentes = readdirSync(carpeta)
  .filter((f) => f.endsWith('.tsx'))
  .map((f) => ({ archivo: f, texto: readFileSync(join(carpeta, f), 'utf-8') }))

/** Cada elemento JSX completo (`<input …>` o `<Boton …>`), con sus atributos aunque ocupen varias líneas. */
function elementos(texto: string, etiqueta: string) {
  // `=>` de las funciones flecha no cierra el elemento.
  return [...texto.matchAll(new RegExp(`<${etiqueta}\\b(?:=>|[^>])*>`, 'g'))].map((m) => m[0])
}

describe('Las casillas de la app de familia', () => {
  it('«Leí el aviso y lo acepto» mide size-6, sin size-5 ni mt-0.5, y en angosto se alinea con la primera línea', () => {
    render(<AvisoCuidadorDeHecho idTitulo="aviso-t" idError="aviso-e" leido={false} error={false} onLeido={() => {}} />)
    const casilla = screen.getByRole('checkbox')
    expect(casilla).toHaveClass('size-6', 'shrink-0', 'accent-turquesa')
    expect(casilla).not.toHaveClass('size-5')
    expect(casilla).not.toHaveClass('mt-0.5')
    expect(casilla.closest('label')).toHaveClass('min-h-12', 'items-center')
    // Revisión visual de MATU-68 (P3): en 320 px con el texto al 200 % la etiqueta ocupa varias
    // líneas, y la casilla va con la primera (DISENO.md). Fuera de `angosto` no cambia.
    expect(casilla).toHaveClass('angosto:mt-0.5')
    expect(casilla.closest('label')).toHaveClass('angosto:items-start')
  })

  it('ninguna casilla nativa visible de web/src/familia lleva size-5', () => {
    const casillas = fuentes.flatMap(({ archivo, texto }) =>
      elementos(texto, 'input')
        .filter((e) => /type="checkbox"/.test(e) && !/sr-only/.test(e))
        .map((e) => ({ archivo, e })),
    )
    expect(casillas.length).toBeGreaterThanOrEqual(4)
    for (const { archivo, e } of casillas) {
      expect(e, archivo).toMatch(/\bsize-6\b/)
      expect(e, archivo).not.toMatch(/\bsize-5\b/)
    }
  })
})

describe('Los botones de la app de familia', () => {
  it('ningún botón lleva px-0.5 ni un relleno con `!`', () => {
    const botones = fuentes.flatMap(({ archivo, texto }) => [...elementos(texto, 'Boton'), ...elementos(texto, 'button')].map((e) => ({ archivo, e })))
    expect(botones.length).toBeGreaterThan(20)
    for (const { archivo, e } of botones) {
      expect(e, archivo).not.toMatch(/\bpx-0\.5\b/)
      expect(e, archivo).not.toMatch(/(?:^|[\s"'`:])p[xyselrtb]?-[\w.[\]]+!/)
    }
  })
})

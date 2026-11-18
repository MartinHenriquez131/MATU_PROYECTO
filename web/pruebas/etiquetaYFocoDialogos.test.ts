// MATU-117 (docs/diseno/matu-117-etiqueta-y-foco.md): la etiqueta de estado y el distintivo
// del piloto usan `rounded-2xl`, no `rounded-full`, para que con varios renglones no se vean
// como un óvalo; y los títulos que reciben el foco inicial de DialogoGrupo, DialogoRetirar y
// DialogoConfirmar no llevan `outline-none`, para que el foco base se vea con el teclado.
// jsdom no aplica :focus-visible ni mide radios, así que se leen las fuentes, igual que en
// veloDialogos.test.ts.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const raiz = join(dirname(fileURLToPath(import.meta.url)), '..', 'src')
const leer = (ruta: string) => readFileSync(join(raiz, ruta), 'utf-8')

/** El cuerpo de una función, desde su declaración hasta la siguiente función de primer nivel. */
function cuerpo(texto: string, nombre: string): string {
  const inicio = texto.search(new RegExp(`^(export )?function ${nombre}\\b`, 'm'))
  expect(inicio, `no se encontró la función ${nombre}`).toBeGreaterThanOrEqual(0)
  const resto = texto.slice(inicio + 1)
  const fin = resto.search(/^(export )?(function|const) /m)
  return fin < 0 ? texto.slice(inicio) : texto.slice(inicio, inicio + 1 + fin)
}

/** Las clases del primer elemento `<etiqueta` del texto. */
function clasesDe(texto: string, etiqueta: string): string[] {
  const m = texto.match(new RegExp(`<${etiqueta}\\b[^>]*?className=\\{?["\`]([^"\`]*)["\`]`))
  expect(m, `no se encontró <${etiqueta} con className`).not.toBeNull()
  return m![1].split(/\s+/)
}

describe('La forma de la etiqueta y del distintivo (MATU-117, 1)', () => {
  it.each([
    ['Etiqueta', 'familia/ui.tsx'],
    ['DistintivoPiloto', 'compartido/ui/Marca.tsx'],
  ])('%s usa rounded-2xl y no rounded-full', (nombre, ruta) => {
    const clases = clasesDe(cuerpo(leer(ruta), nombre), 'span')
    expect(clases).toContain('rounded-2xl')
    expect(clases).not.toContain('rounded-full')
  })
})

describe('El foco inicial de los diálogos (MATU-117, 2)', () => {
  it.each([
    ['DialogoGrupo', 'familia/PiezasInvitar.tsx'],
    ['DialogoRetirar', 'familia/Grupo.tsx'],
    ['DialogoConfirmar', 'familia/DialogoConfirmar.tsx'],
  ])('el título de %s recibe el foco y no lleva outline-none', (nombre, ruta) => {
    const f = cuerpo(leer(ruta), nombre)
    const h2 = f.match(/<h2\b[^>]*>/)
    expect(h2).not.toBeNull()
    expect(h2![0]).toContain('tabIndex={-1}')
    const clases = clasesDe(h2![0], 'h2')
    expect(clases).not.toContain('outline-none')
    expect(clases.some((c) => /(^|:)(outline|focus)/.test(c))).toBe(false)
  })
})

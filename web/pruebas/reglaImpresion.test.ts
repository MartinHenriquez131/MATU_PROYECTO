// MATU-60, 8.4 (y ADR-029): la regla de impresión de web/src/index.css. Deja fuera del papel
// toda la app en todas las pantallas, también la ficha con Ctrl+P, y en las que no tienen hoja
// de impresión deja «Esta pantalla no se imprime.». jsdom no imprime ni aplica `@media print`,
// así que se prueba el texto del CSS: copiado tal cual de la especificación, y con lo que cierra
// el hueco aunque la especificación cambie de forma.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const leer = (ruta: string) => readFileSync(fileURLToPath(new URL(ruta, import.meta.url)), 'utf-8').replace(/\r\n/g, '\n')
const css = leer('../src/index.css')
const especificacion = leer('../../docs/diseno/matu-60-lista-insumos.md')

/** Sin comentarios y con los espacios juntos, para comparar reglas y no el formato. */
const compacto = (t: string) =>
  t
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\s+/g, ' ')
    .replace(/\s*([{}:;,>()])\s*/g, '$1')
    .trim()

/** Los bloques de primer nivel del CSS (sin comentarios): su cabecera y lo de dentro. */
function primerNivel(texto: string): { cabecera: string; dentro: string }[] {
  const t = texto.replace(/\/\*[\s\S]*?\*\//g, '')
  const bloques: { cabecera: string; dentro: string }[] = []
  let desde = 0
  let nivel = 0
  let abre = -1
  for (let j = 0; j < t.length; j++) {
    if (t[j] === ';' && nivel === 0) desde = j + 1
    else if (t[j] === '{' && nivel++ === 0) abre = j
    else if (t[j] === '}' && --nivel === 0) {
      bloques.push({ cabecera: t.slice(desde, abre).trim(), dentro: t.slice(abre + 1, j) })
      desde = j + 1
    }
  }
  return bloques
}

/** Lo de dentro de cada `@media print` sin capa: si estuviera en @layer, una utilidad de Tailwind lo ganaría. */
const printSinCapa = (texto: string) =>
  primerNivel(texto)
    .filter((b) => b.cabecera === '@media print')
    .map((b) => compacto(b.dentro))

describe('La regla de impresión (8.4)', () => {
  it('el final de index.css es el bloque de la sección 8.4, tal cual', () => {
    const seccion = especificacion.slice(especificacion.indexOf('### 8.4 '), especificacion.indexOf('### 8.5 '))
    const bloque = /```css\n([\s\S]*?)```/.exec(seccion)?.[1]
    expect(bloque, 'la sección 8.4 trae un bloque css').toBeTruthy()
    const inicio = css.indexOf(bloque!.split('\n')[0])
    expect(inicio, 'index.css trae el comienzo del bloque de 8.4').toBeGreaterThanOrEqual(0)
    expect(css.slice(inicio).trimEnd()).toBe(bloque!.trimEnd())
  })

  it('fuera de @layer, oculta todo hijo de body que no es la hoja, y el diálogo modal', () => {
    const ocultar = printSinCapa(css).find((b) => b.includes('body>:not([data-impresion])'))
    expect(ocultar, 'un @media print sin capa con body > :not([data-impresion])').toBeDefined()
    expect(ocultar).toContain('body>:not([data-impresion]),:modal{display:none;}')
  })

  it('fuera de @layer, en una pantalla sin hoja, deja «Esta pantalla no se imprime.»', () => {
    const todo = printSinCapa(css).join(' ')
    expect(todo).toContain("body:not(:has(>[data-impresion]))::before{content:'Esta pantalla no se imprime.';display:block;")
  })
})

// MATU-93 (P2 del diseñador): en Firefox, `calc(1.75rem - 1px)` dentro de `repeating-linear-gradient`
// pintaba franjas en vez de una raya de 1 px. `renglones` usa un `linear-gradient` simple con un
// tile de 1.75rem, que calza con el `leading-7` de la hoja, y no toca `background` (borraría el
// `bg-hoja`). jsdom no aplica Tailwind ni los degradados, así que se lee el texto del CSS y de los .tsx.
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const src = join(dirname(fileURLToPath(import.meta.url)), '../src')
const css = readFileSync(join(src, 'index.css'), 'utf-8').replace(/\r\n/g, '\n').replace(/\/\*[\s\S]*?\*\//g, '')
const cuerpo = css.match(/@utility renglones\s*\{([^}]*)\}/)?.[1] ?? ''

function archivos(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? archivos(join(dir, e.name)) : /\.tsx$/.test(e.name) ? [join(dir, e.name)] : [],
  )
}

describe('MATU-93: los renglones de la hoja', () => {
  it('existe la utilidad', () => {
    expect(cuerpo).not.toBe('')
  })

  it('no usa repeating-linear-gradient ni calc con rem', () => {
    expect(cuerpo).not.toMatch(/repeating-linear-gradient/)
    expect(cuerpo).not.toMatch(/calc\([^)]*rem/)
  })

  it('una raya de 1 px en un tile de 1.75rem, con propiedades separadas', () => {
    expect(cuerpo).toMatch(/background-image:\s*linear-gradient\(/)
    expect(cuerpo).toMatch(/calc\(100% - 1px\)/)
    expect(cuerpo).toMatch(/background-size:\s*100% 1\.75rem;/)
    expect(cuerpo).not.toMatch(/(^|[^-])background:/)
  })

  it('cada uso de renglones lleva leading-7 (1.75rem), para que el texto calce con las rayas', () => {
    const sinLeading: string[] = []
    for (const ruta of archivos(src))
      readFileSync(ruta, 'utf-8')
        .split(/\r?\n/)
        .forEach((linea, i) => {
          if (/className=.*(?<![\w-])renglones(?![\w-])/.test(linea) && !/(?<![\w-])leading-7(?![\w-])/.test(linea))
            sinLeading.push(`${ruta}:${i + 1}`)
        })
    expect(sinLeading).toEqual([])
  })
})

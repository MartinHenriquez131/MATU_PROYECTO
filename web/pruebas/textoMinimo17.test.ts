// MATU-93: ningún texto de la app queda bajo 17 px (1 rem, `text-base`). `text-sm` (14,9 px) y
// `text-xs` no se usan en ningún componente. La única excepción aprobada por el diseñador son los
// rótulos de la barra inferior del teléfono (`telefono:text-sm` en Shell.tsx, anotada en
// Demo/DISENO.md). jsdom no aplica Tailwind, así que se lee el texto de cada .ts y .tsx de web/src.
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const raiz = join(dirname(fileURLToPath(import.meta.url)), '../src')

/** La lista blanca: archivo y la clase exacta que puede usar. */
const EXCEPCIONES: Record<string, string[]> = { 'familia/Shell.tsx': ['telefono:text-sm'] }

function archivos(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? archivos(join(dir, e.name)) : /\.tsx?$/.test(e.name) ? [join(dir, e.name)] : [],
  )
}

/** Las clases de tamaño bajo 1 rem que aparecen en el texto, con su variante (`telefono:`, `md:`…). */
const PEQUENAS = /(?<![\w-])((?:[\w@/-]+:)*text-(?:sm|xs|2xs))(?![\w-])/g

describe('MATU-93: ningún texto bajo 17 px', () => {
  const lista = archivos(raiz)

  it('encuentra los componentes', () => {
    expect(lista.length).toBeGreaterThan(10)
  })

  it('ningún archivo usa text-sm ni text-xs, salvo la barra inferior del teléfono', () => {
    const hallazgos: string[] = []
    for (const ruta of lista) {
      const nombre = relative(raiz, ruta).replace(/\\/g, '/')
      const permitidas = EXCEPCIONES[nombre] ?? []
      readFileSync(ruta, 'utf-8')
        .split(/\r?\n/)
        .forEach((linea, i) => {
          for (const m of linea.matchAll(PEQUENAS)) if (!permitidas.includes(m[1])) hallazgos.push(`${nombre}:${i + 1} ${m[1]}`)
        })
    }
    expect(hallazgos).toEqual([])
  })

  it('la excepción sigue en Shell.tsx una sola vez', () => {
    const shell = readFileSync(join(raiz, 'familia/Shell.tsx'), 'utf-8')
    expect(shell.match(/telefono:text-sm/g)).toHaveLength(1)
  })
})

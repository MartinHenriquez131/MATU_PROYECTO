// MATU-93: ningún texto de la app queda bajo 17 px (1 rem, `text-base`). `text-sm` (14,9 px) y
// `text-xs` no se usan en ningún componente. La única excepción aprobada por el diseñador son los
// rótulos de la barra inferior del teléfono cuando la app mide entre 16 y 21 rem (`estrecho:text-sm` en
// Shell.tsx, MATU-107 1.4; desde 21 rem van a 17 px). Anotada en Demo/DISENO.md. Tampoco hay tamaños arbitrarios bajo 17 px ni `fontSize` a mano en un estilo.
// jsdom no aplica Tailwind, así que se lee el texto de cada .ts y .tsx de web/src.
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const raiz = join(dirname(fileURLToPath(import.meta.url)), '../src')

/** La lista blanca: archivo y la clase exacta que puede usar. */
const EXCEPCIONES: Record<string, string[]> = { 'familia/Shell.tsx': ['estrecho:text-sm'] }

function archivos(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? archivos(join(dir, e.name)) : /\.tsx?$/.test(e.name) ? [join(dir, e.name)] : [],
  )
}


/** Las clases de tamaño bajo 1 rem que aparecen en el texto, con su variante (`telefono:`, `md:`…). */
const PEQUENAS = /(?<![\w-])((?:[\w@/-]+:)*text-(?:sm|xs|2xs))(?![\w-])/g

/** Los tamaños arbitrarios de Tailwind con número y unidad: `text-[14px]`, `md:text-[length:0.8rem]`. */
const ARBITRARIAS = /(?<![\w-])((?:[\w@/-]+:)*text-\[(?:length:)?(\d*\.?\d+)(px|rem|em|%)\])/g

/** 1 rem es 17 px (`html { font-size: 106.25% }`); em y % se miden contra el texto que los rodea. */
const bajo17 = (valor: number, unidad: string) =>
  unidad === 'px' ? valor < 17 : unidad === '%' ? valor < 100 : valor < 1

/** El tamaño escrito a mano en un estilo en línea: `style={{ fontSize: … }}` o `font-size:` en un texto. */
const A_MANO = /\bfontSize\s*:|font-size\s*:/g

type Hallazgo = (linea: string) => string[]

/** Recorre cada línea de cada archivo y junta `archivo:línea lo-encontrado`. */
function buscar(lista: string[], hallar: (nombre: string) => Hallazgo): string[] {
  const hallazgos: string[] = []
  for (const ruta of lista) {
    const nombre = relative(raiz, ruta).replace(/\\/g, '/')
    const enLinea = hallar(nombre)
    readFileSync(ruta, 'utf-8')
      .split(/\r?\n/)
      .forEach((linea, i) => {
        for (const h of enLinea(linea)) hallazgos.push(`${nombre}:${i + 1} ${h}`)
      })
  }
  return hallazgos
}

describe('MATU-93: ningún texto bajo 17 px', () => {
  const lista = archivos(raiz)

  it('encuentra los componentes', () => {
    expect(lista.length).toBeGreaterThan(10)
  })

  it('ningún archivo usa text-sm ni text-xs, salvo la barra inferior del teléfono', () => {
    const hallazgos = buscar(lista, (nombre) => {
      const permitidas = EXCEPCIONES[nombre] ?? []
      return (linea) => [...linea.matchAll(PEQUENAS)].map((m) => m[1]).filter((c) => !permitidas.includes(c))
    })
    expect(hallazgos).toEqual([])
  })

  it('ningún archivo usa un tamaño arbitrario bajo 17 px (text-[14px], text-[0.8rem], text-[0.9em])', () => {
    const hallazgos = buscar(lista, () => (linea) =>
      [...linea.matchAll(ARBITRARIAS)].filter((m) => bajo17(Number(m[2]), m[3])).map((m) => m[1]),
    )
    expect(hallazgos).toEqual([])
  })

  it('ningún archivo escribe el tamaño a mano en un estilo (fontSize, font-size)', () => {
    const hallazgos = buscar(lista, () => (linea) => [...linea.matchAll(A_MANO)].map((m) => m[0]))
    expect(hallazgos).toEqual([])
  })

  it('los patrones reconocen lo que buscan', () => {
    const arbitrarias = (t: string) => [...t.matchAll(ARBITRARIAS)].filter((m) => bajo17(Number(m[2]), m[3])).map((m) => m[1])
    expect(arbitrarias('a text-[0.8rem] text-[14px] md:text-[0.9em] text-[length:16px] b')).toEqual([
      'text-[0.8rem]',
      'text-[14px]',
      'md:text-[0.9em]',
      'text-[length:16px]',
    ])
    expect(arbitrarias('text-[17px] text-[1rem] text-[1.25rem] text-[#fff] text-[var(--x)]')).toEqual([])
    expect('style={{ fontSize: 12 }}'.match(A_MANO)).toHaveLength(1)
    expect('getComputedStyle(el).fontSize'.match(A_MANO)).toBeNull()
  })

  it('la excepción sigue en Shell.tsx una sola vez', () => {
    const shell = readFileSync(join(raiz, 'familia/Shell.tsx'), 'utf-8')
    expect(shell.match(/estrecho:text-sm/g)).toHaveLength(1)
    // MATU-107 (42-H2): desde 21 rem el rótulo de la barra hereda text-base.
    expect(shell).not.toMatch(/telefono:text-sm/)
    const css = readFileSync(join(raiz, 'index.css'), 'utf-8')
    expect(css).toMatch(/@custom-variant estrecho \{\s*@media \(width < 40rem\) \{\s*@container app \(16rem <= width < 21rem\)/)
  })
})

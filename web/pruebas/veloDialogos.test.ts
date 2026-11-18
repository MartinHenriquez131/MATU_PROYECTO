// MATU-103: el velo de los diálogos oscurece la página en los dos temas. Con `tinta/40` el
// fondo se aclaraba en tema oscuro, porque `tinta` es clara ahí. Todo `<dialog>` modal usa
// `backdrop:bg-velo` (sin /NN) y `ring-1 ring-linea` (docs/diseno/matu-103-velo-dialogos.md).
// jsdom no pinta ::backdrop, así que se leen las fuentes, igual que en coloresRepetidos.test.ts.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const raiz = join(dirname(fileURLToPath(import.meta.url)), '..', 'src')

function fuentes(dir: string): string[] {
  return readdirSync(dir).flatMap((nombre) => {
    const ruta = join(dir, nombre)
    if (statSync(ruta).isDirectory()) return fuentes(ruta)
    return /\.(tsx?|jsx?)$/.test(nombre) ? [ruta] : []
  })
}

const archivos = fuentes(raiz).map((ruta) => ({
  ruta: ruta.slice(raiz.length + 1).split(sep).join('/'),
  texto: readFileSync(ruta, 'utf-8'),
}))

/** Cada clase `backdrop:` de las fuentes, con su archivo. */
const backdrops = archivos.flatMap(({ ruta, texto }) =>
  [...texto.matchAll(/backdrop:[^\s"'`]+/g)].map((m) => ({ ruta, clase: m[0] })),
)

describe('El velo de los diálogos (MATU-103)', () => {
  it('hay diálogos con velo', () => {
    expect(backdrops.length).toBeGreaterThan(0)
  })

  it('ningún diálogo usa backdrop:bg-tinta', () => {
    expect(backdrops.filter((b) => b.clase.startsWith('backdrop:bg-tinta'))).toEqual([])
  })

  it('todo backdrop: es exactamente backdrop:bg-velo, sin /NN', () => {
    expect(backdrops.filter((b) => b.clase !== 'backdrop:bg-velo')).toEqual([])
  })

  it('toda clase con backdrop:bg-velo lleva ring-1 ring-linea', () => {
    const sinBorde = archivos.flatMap(({ ruta, texto }) =>
      [...texto.matchAll(/className="([^"]*backdrop:bg-velo[^"]*)"/g)]
        .filter((m) => !/(^|\s)ring-1(\s|$)/.test(m[1]) || !/(^|\s)ring-linea(\s|$)/.test(m[1]))
        .map(() => ruta),
    )
    expect(sinBorde).toEqual([])
  })
})

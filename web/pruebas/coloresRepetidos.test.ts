// MATU-60 (H2 de la revisión): web/src/index.css repite colores a mano porque CSS no deja
// compartir un bloque. El tema claro de @theme se repite en el @media print, y el tema oscuro
// va dos veces, en :root[data-tema='oscuro'] y en @media (prefers-color-scheme: dark). Esta
// prueba vigila que las copias digan lo mismo. jsdom no aplica esas reglas, así que se lee el
// texto del CSS, igual que en reglaImpresion.test.ts.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const leer = (ruta: string) => readFileSync(fileURLToPath(new URL(ruta, import.meta.url)), 'utf-8').replace(/\r\n/g, '\n')
const css = leer('../src/index.css').replace(/\/\*[\s\S]*?\*\//g, '')

type Bloque = { cabecera: string; dentro: string }

/** Los bloques de un nivel del CSS: su cabecera y lo de dentro, con sus bloques hijos. */
function bloques(texto: string): Bloque[] {
  const lista: Bloque[] = []
  let desde = 0
  let nivel = 0
  let abre = -1
  for (let j = 0; j < texto.length; j++) {
    if (texto[j] === ';' && nivel === 0) desde = j + 1
    else if (texto[j] === '{' && nivel++ === 0) abre = j
    else if (texto[j] === '}' && --nivel === 0) {
      lista.push({ cabecera: texto.slice(desde, abre).replace(/\s+/g, ' ').trim(), dentro: texto.slice(abre + 1, j) })
      desde = j + 1
    }
  }
  return lista
}

/** Lo de dentro de un bloque sin sus bloques hijos (en @theme, sin los @keyframes). */
const sinHijos = (dentro: string) => {
  let t = dentro
  for (const b of bloques(dentro)) t = t.replace(b.dentro, '')
  return t
}

/** Las variables --color-* del bloque, con su valor tal cual. */
function colores(dentro: string): Map<string, string> {
  const mapa = new Map<string, string>()
  for (const m of sinHijos(dentro).matchAll(/(--color-[\w-]+)\s*:\s*([^;]+);/g)) mapa.set(m[1], m[2].trim().toLowerCase())
  return mapa
}

/** Solo las que tienen un valor literal en hexadecimal (no los derivados con color-mix). */
const hex = (mapa: Map<string, string>) => new Map([...mapa].filter(([, v]) => /^#[0-9a-f]{3,8}$/.test(v)))

const primerNivel = bloques(css)
const uno = (lista: Bloque[], cumple: (b: Bloque) => boolean, nombre: string) => {
  const hallados = lista.filter(cumple)
  if (hallados.length !== 1) throw new Error(`index.css debería tener un solo bloque ${nombre} y tiene ${hallados.length}`)
  return hallados[0]
}

const tema = hex(colores(uno(primerNivel, (b) => b.cabecera === '@theme', '@theme').dentro))

const impresion = uno(
  primerNivel
    .filter((b) => b.cabecera === '@media print')
    .flatMap((b) => bloques(b.dentro))
    .filter((b) => b.cabecera.includes(":root[data-tema='oscuro']")),
  () => true,
  "@media print con :root[data-tema='oscuro']",
)
const colImpresion = colores(impresion.dentro)

const oscuro = colores(uno(primerNivel, (b) => b.cabecera === ":root[data-tema='oscuro']", ":root[data-tema='oscuro']").dentro)
const sistema = uno(
  primerNivel.filter((b) => b.cabecera === '@media (prefers-color-scheme: dark)').flatMap((b) => bloques(b.dentro)),
  (b) => b.cabecera === ":root:not([data-tema='claro'])",
  "@media (prefers-color-scheme: dark) con :root:not([data-tema='claro'])",
)
const colSistema = colores(sistema.dentro)

describe('Los colores repetidos de index.css', () => {
  it('se leen los bloques', () => {
    expect(tema.size, '@theme trae colores en hexadecimal').toBeGreaterThan(0)
    expect(colImpresion.size, 'el @media print trae colores').toBeGreaterThan(0)
    expect(oscuro.size, "el :root[data-tema='oscuro'] trae colores").toBeGreaterThan(0)
  })

  it('al imprimir, cada color es el mismo de @theme', () => {
    const errores: string[] = []
    for (const [nombre, valor] of colImpresion) {
      const delTema = tema.get(nombre)
      if (delTema === undefined) errores.push(`${nombre} está en el @media print y no está en @theme con un valor hexadecimal`)
      else if (delTema !== valor) errores.push(`${nombre} vale ${valor} en el @media print y ${delTema} en @theme`)
    }
    expect(errores, errores.join('\n')).toEqual([])
  })

  it('al imprimir, vuelve al claro cada color de @theme que el tema oscuro cambia', () => {
    const errores: string[] = []
    for (const nombre of new Set([...oscuro.keys(), ...colSistema.keys()]))
      if (tema.has(nombre) && !colImpresion.has(nombre))
        errores.push(`${nombre} cambia en el tema oscuro y falta en el @media print (debe valer ${tema.get(nombre)}, como en @theme)`)
    expect(errores, errores.join('\n')).toEqual([])
  })

  it("el tema oscuro es igual en :root[data-tema='oscuro'] y en prefers-color-scheme: dark", () => {
    const errores: string[] = []
    const a = ":root[data-tema='oscuro']"
    const b = '@media (prefers-color-scheme: dark)'
    for (const [nombre, valor] of oscuro) {
      const otro = colSistema.get(nombre)
      if (otro === undefined) errores.push(`${nombre} está en ${a} y falta en ${b}`)
      else if (otro !== valor) errores.push(`${nombre} vale ${valor} en ${a} y ${otro} en ${b}`)
    }
    for (const nombre of colSistema.keys())
      if (!oscuro.has(nombre)) errores.push(`${nombre} está en ${b} y falta en ${a}`)
    expect(errores, errores.join('\n')).toEqual([])
  })
})

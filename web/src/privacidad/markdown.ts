// Un lector de Markdown chico y propio para la política de privacidad (MATU-75, especificación 1.7
// y 1.8). Convierte el texto en una lista de bloques que `Documento.tsx` dibuja como elementos de
// React. Nunca produce HTML: el texto queda siempre como texto, y un `<script>` o cualquier etiqueta
// que traiga se ve tal cual, con sus signos. Sin dependencias.
//
// Entiende lo que usa la política: títulos (`##` y `###`), párrafos, listas con viñetas y numeradas,
// `**negrita**`, `*cursiva*`, citas (`>`), `---`, `` `código` ``, tablas y enlaces. Un enlace solo es
// enlace si va a `mailto:`, a `https:` o a un ancla de la misma página (`#…`); con otro destino se
// muestra solo su texto. El texto no se reemplaza ni se corrige.

export type Linea =
  | { tipo: 'texto'; texto: string }
  | { tipo: 'negrita'; hijos: Linea[] }
  | { tipo: 'cursiva'; hijos: Linea[] }
  | { tipo: 'codigo'; texto: string }
  | { tipo: 'enlace'; href: string; destino: 'correo' | 'externo' | 'ancla'; hijos: Linea[] }

export type Titulo = { tipo: 'titulo'; nivel: 2 | 3; id: string; texto: string; hijos: Linea[] }

export type Bloque =
  | Titulo
  | { tipo: 'parrafo'; hijos: Linea[] }
  | { tipo: 'lista'; ordenada: boolean; inicio: number; items: Linea[][] }
  | { tipo: 'cita'; bloques: Bloque[] }
  | { tipo: 'separador' }
  | { tipo: 'tabla'; encabezados: Linea[][]; filas: Linea[][][] }
  | { tipo: 'bloqueCodigo'; texto: string }

/** Un título de primer nivel (`##`) y lo que le sigue, hasta el próximo. */
export interface Seccion {
  titulo: Titulo | null
  bloques: Bloque[]
}

// ---------------------------------------------------------------- en línea

const ESCAPABLES = '\\`*_{}[]()#+-.!|>'

function cerrarTexto(salida: Linea[], texto: string) {
  if (!texto) return
  const ultimo = salida[salida.length - 1]
  if (ultimo?.tipo === 'texto') ultimo.texto += texto
  else salida.push({ tipo: 'texto', texto })
}

function destinoDe(href: string): 'correo' | 'externo' | 'ancla' | null {
  if (/^mailto:[^\s<>"]+$/i.test(href)) return 'correo'
  if (/^https:\/\/[^\s<>"]+$/i.test(href)) return 'externo'
  if (/^#[A-Za-z0-9-]+$/.test(href)) return 'ancla'
  return null
}

/** El texto de un párrafo, un ítem o una celda, en partes. */
export function leerEnLinea(texto: string): Linea[] {
  const salida: Linea[] = []
  let suelto = ''
  let i = 0
  while (i < texto.length) {
    const c = texto[i]
    if (c === '\\' && i + 1 < texto.length && ESCAPABLES.includes(texto[i + 1])) {
      suelto += texto[i + 1]
      i += 2
      continue
    }
    if (c === '`') {
      const fin = texto.indexOf('`', i + 1)
      if (fin > i + 1) {
        cerrarTexto(salida, suelto)
        suelto = ''
        salida.push({ tipo: 'codigo', texto: texto.slice(i + 1, fin) })
        i = fin + 1
        continue
      }
    }
    if (c === '*' && texto[i + 1] === '*') {
      const fin = texto.indexOf('**', i + 2)
      if (fin > i + 2 && !/\s/.test(texto[i + 2]) && !/\s/.test(texto[fin - 1])) {
        cerrarTexto(salida, suelto)
        suelto = ''
        salida.push({ tipo: 'negrita', hijos: leerEnLinea(texto.slice(i + 2, fin)) })
        i = fin + 2
        continue
      }
    }
    if (c === '*' && texto[i + 1] !== '*' && texto[i + 1] !== undefined && !/\s/.test(texto[i + 1])) {
      // Una cursiva cierra en el siguiente `*` solo, pegado al texto.
      let fin = -1
      for (let k = i + 2; k < texto.length; k++) {
        if (texto[k] !== '*') continue
        if (texto[k + 1] === '*') {
          k += 1
          continue
        }
        if (!/\s/.test(texto[k - 1])) {
          fin = k
          break
        }
      }
      if (fin > i + 1) {
        cerrarTexto(salida, suelto)
        suelto = ''
        salida.push({ tipo: 'cursiva', hijos: leerEnLinea(texto.slice(i + 1, fin)) })
        i = fin + 1
        continue
      }
    }
    if (c === '[') {
      // El destino admite un nivel de paréntesis, como `https://…/Ley_(Chile)`.
      const m = /^\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)/.exec(texto.slice(i))
      if (m) {
        cerrarTexto(salida, suelto)
        suelto = ''
        const destino = destinoDe(m[2])
        const hijos = leerEnLinea(m[1])
        if (destino) salida.push({ tipo: 'enlace', href: m[2], destino, hijos })
        else hijos.forEach((h) => (h.tipo === 'texto' ? cerrarTexto(salida, h.texto) : salida.push(h)))
        i += m[0].length
        continue
      }
    }
    suelto += c
    i += 1
  }
  cerrarTexto(salida, suelto)
  return salida
}

/** El texto de unas partes, sin marcas: para el índice y los `id`. */
export function textoPlano(partes: Linea[]): string {
  return partes.map((p) => (p.tipo === 'texto' || p.tipo === 'codigo' ? p.texto : textoPlano(p.hijos))).join('')
}

// ---------------------------------------------------------------- bloques

const TITULO = /^(#{1,6})\s+(.*?)\s*#*\s*$/
const SEPARADOR = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/
const CITA = /^\s{0,3}>/
const VINETA = /^\s{0,3}[-*+]\s+(.*)$/
const NUMERO = /^\s{0,3}(\d{1,9})[.)]\s+(.*)$/
const CERCO = /^\s{0,3}```/
const FILA_SEPARADORA = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/

const enBlanco = (l: string) => !l.trim()

function celdas(linea: string): string[] {
  let l = linea.trim()
  if (l.startsWith('|')) l = l.slice(1)
  if (l.endsWith('|') && !l.endsWith('\\|')) l = l.slice(0, -1)
  const salida: string[] = []
  let actual = ''
  for (let i = 0; i < l.length; i++) {
    if (l[i] === '\\' && l[i + 1] === '|') {
      actual += '|'
      i += 1
    } else if (l[i] === '|') {
      salida.push(actual.trim())
      actual = ''
    } else actual += l[i]
  }
  salida.push(actual.trim())
  return salida
}

const esTabla = (lineas: string[], i: number) => lineas[i].includes('|') && i + 1 < lineas.length && FILA_SEPARADORA.test(lineas[i + 1]) && lineas[i + 1].includes('-')

const empiezaBloque = (lineas: string[], i: number) => {
  const l = lineas[i]
  return TITULO.test(l) || SEPARADOR.test(l) || CITA.test(l) || VINETA.test(l) || NUMERO.test(l) || CERCO.test(l) || esTabla(lineas, i)
}

function leerBloques(lineas: string[]): Bloque[] {
  const bloques: Bloque[] = []
  let i = 0
  while (i < lineas.length) {
    const l = lineas[i]
    if (enBlanco(l)) {
      i += 1
      continue
    }
    if (CERCO.test(l)) {
      const cuerpo: string[] = []
      i += 1
      while (i < lineas.length && !CERCO.test(lineas[i])) cuerpo.push(lineas[i++])
      i += 1
      bloques.push({ tipo: 'bloqueCodigo', texto: cuerpo.join('\n') })
      continue
    }
    const titulo = TITULO.exec(l)
    if (titulo) {
      const hijos = leerEnLinea(titulo[2])
      bloques.push({ tipo: 'titulo', nivel: titulo[1].length <= 2 ? 2 : 3, id: '', texto: textoPlano(hijos), hijos })
      i += 1
      continue
    }
    if (SEPARADOR.test(l)) {
      bloques.push({ tipo: 'separador' })
      i += 1
      continue
    }
    if (CITA.test(l)) {
      const adentro: string[] = []
      while (i < lineas.length && CITA.test(lineas[i])) adentro.push(lineas[i++].replace(/^\s{0,3}> ?/, ''))
      bloques.push({ tipo: 'cita', bloques: leerBloques(adentro) })
      continue
    }
    if (esTabla(lineas, i)) {
      const encabezados = celdas(l).map(leerEnLinea)
      const filas: Linea[][][] = []
      i += 2
      while (i < lineas.length && !enBlanco(lineas[i]) && lineas[i].includes('|')) {
        const fila = celdas(lineas[i++])
        // Cada fila tiene tantas celdas como encabezados: las que faltan quedan vacías.
        filas.push(encabezados.map((_, c) => leerEnLinea(fila[c] ?? '')))
      }
      bloques.push({ tipo: 'tabla', encabezados, filas })
      continue
    }
    const vineta = VINETA.exec(l)
    const numero = NUMERO.exec(l)
    if (vineta || numero) {
      const ordenada = !vineta
      const patron = ordenada ? NUMERO : VINETA
      const items: string[] = []
      while (i < lineas.length) {
        const m = patron.exec(lineas[i])
        if (m) {
          items.push(ordenada ? m[2] : m[1])
          i += 1
          continue
        }
        if (enBlanco(lineas[i])) {
          // Una lista con líneas en blanco entre sus ítems sigue si el próximo es del mismo tipo.
          let j = i
          while (j < lineas.length && enBlanco(lineas[j])) j += 1
          if (j < lineas.length && patron.test(lineas[j])) {
            i = j
            continue
          }
          break
        }
        if (empiezaBloque(lineas, i)) break
        // Continuación del ítem en la línea siguiente.
        items[items.length - 1] += ` ${lineas[i].trim()}`
        i += 1
      }
      bloques.push({ tipo: 'lista', ordenada, inicio: numero ? Number(numero[1]) : 1, items: items.map(leerEnLinea) })
      continue
    }
    const parrafo: string[] = []
    while (i < lineas.length && !enBlanco(lineas[i]) && (parrafo.length === 0 || !empiezaBloque(lineas, i))) parrafo.push(lineas[i++].trim())
    bloques.push({ tipo: 'parrafo', hijos: leerEnLinea(parrafo.join(' ')) })
  }
  return bloques
}

// ---------------------------------------------------------------- anclas y secciones

/** «5. La autorización…» → `seccion-5`; «En un minuto» → `en-un-minuto`. */
function slug(texto: string): string {
  return (
    texto
      .normalize('NFD')
      .replace(/\p{M}/gu, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'seccion'
  )
}

function ponerAnclas(bloques: Bloque[]) {
  const usados = new Set<string>()
  const unico = (base: string) => {
    let id = base
    for (let n = 2; usados.has(id); n++) id = `${base}-${n}`
    usados.add(id)
    return id
  }
  let padre = ''
  for (const b of bloques) {
    if (b.tipo !== 'titulo') continue
    if (b.nivel === 2) {
      const numero = /^(\d+)\.\s/.exec(b.texto)
      b.id = unico(numero ? `seccion-${numero[1]}` : slug(b.texto))
      padre = b.id
    } else b.id = unico(padre ? `${padre}-${slug(b.texto)}` : slug(b.texto))
  }
}

/** El texto de la política en secciones, cada una con su título `##` (la primera puede no tenerlo). */
export function leerMarkdown(texto: string): Seccion[] {
  const bloques = leerBloques(texto.replace(/\r\n?/g, '\n').split('\n'))
  ponerAnclas(bloques)
  const secciones: Seccion[] = []
  for (const b of bloques) {
    if (b.tipo === 'titulo' && b.nivel === 2) secciones.push({ titulo: b, bloques: [] })
    else {
      if (!secciones.length) secciones.push({ titulo: null, bloques: [] })
      secciones[secciones.length - 1].bloques.push(b)
    }
  }
  return secciones
}

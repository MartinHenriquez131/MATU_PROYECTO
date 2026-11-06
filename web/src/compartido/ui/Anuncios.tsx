// Avisos que se anuncian a los lectores de pantalla (revisión visual del #51, P2-3).
//
// Un elemento que entra al DOM ya con `role="status"` o `role="alert"` y su texto no siempre se
// anuncia: VoiceOver y Chrome pueden callarlo si la región no existía antes del cambio, sobre todo
// con el foco en el botón que se acaba de tocar. Por eso los avisos de la app de la familia y del
// relevo se anuncian en dos regiones vivas que existen desde el primer render (`RegionesVivas`,
// montadas en main.tsx): una amable (`status`) y una urgente (`alert`). El aviso visible ya no
// lleva el rol, así que se anuncia una sola vez, y lo que se lee es lo mismo que se ve.
//
// Nada de esto se guarda: el texto vive en memoria y se borra cuando el aviso deja la pantalla.
import { useEffect, useRef, useSyncExternalStore, type HTMLAttributes, type ReactNode, type Ref, type RefObject } from 'react'

/** `status`: se lee cuando el lector termina lo que está diciendo. `alert`: interrumpe. */
export type Urgencia = 'status' | 'alert'

const URGENCIAS: Urgencia[] = ['status', 'alert']
/** Lo que se muestra en cada región. Se vacía antes de cada anuncio para que el mismo texto se repita. */
let estado: Record<Urgencia, string> = { status: '', alert: '' }
const cola: Record<Urgencia, string[]> = { status: [], alert: [] }
const reloj: Record<Urgencia, number | undefined> = { status: undefined, alert: undefined }
const oyentes = new Set<() => void>()

function fijar(u: Urgencia, texto: string) {
  if (estado[u] === texto) return
  estado = { ...estado, [u]: texto }
  oyentes.forEach((o) => o())
}

/**
 * Anuncia `texto`. La región se vacía y se llena 50 ms después: así el lector nota el cambio aunque
 * el texto sea el mismo de antes. Los avisos que llegan juntos se leen juntos, en orden.
 */
export function anunciar(texto: string, urgencia: Urgencia = 'status') {
  const t = texto.trim()
  if (!t) return
  if (!cola[urgencia].includes(t)) cola[urgencia].push(t)
  window.clearTimeout(reloj[urgencia])
  fijar(urgencia, '')
  reloj[urgencia] = window.setTimeout(() => {
    reloj[urgencia] = undefined
    fijar(urgencia, cola[urgencia].join(' '))
    cola[urgencia] = []
  }, 50)
}

/** El aviso dejó la pantalla: su texto sale de la cola y de la región, para no quedar leíble al final. */
export function retirar(texto: string) {
  const t = texto.trim()
  if (!t) return
  for (const u of URGENCIAS) {
    cola[u] = cola[u].filter((x) => x !== t)
    if (estado[u] === t) fijar(u, '')
  }
}

/** Vacía las regiones y la cola. Lo usan las pruebas entre un caso y otro. */
export function olvidarAnuncios() {
  for (const u of URGENCIAS) {
    window.clearTimeout(reloj[u])
    reloj[u] = undefined
    cola[u] = []
  }
  estado = { status: '', alert: '' }
  oyentes.forEach((o) => o())
}

const suscribir = (o: () => void) => {
  oyentes.add(o)
  return () => oyentes.delete(o)
}
const leerEstado = () => estado

/** Las dos regiones vivas, vacías desde el primer render. Van una sola vez, en main.tsx. */
export function RegionesVivas() {
  const e = useSyncExternalStore(suscribir, leerEstado, leerEstado)
  return (
    <>
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {e.status}
      </div>
      <div role="alert" aria-live="assertive" aria-atomic="true" className="sr-only">
        {e.alert}
      </div>
    </>
  )
}

const BLOQUES = new Set(['P', 'DIV', 'LI', 'UL', 'OL', 'H1', 'H2', 'H3', 'H4', 'SECTION'])

/**
 * El texto de un aviso tal como se ve: sin íconos (`aria-hidden`) ni botones, que son acciones y no
 * parte del mensaje. Cada bloque (título, cuerpo) se separa con un punto si no termina en uno.
 */
export function textoParaLeer(raiz: Element): string {
  const partes: string[] = []
  let linea = ''
  const cerrar = () => {
    // Entre dos elementos va un espacio (un `<span class="block">` seguido de un enlace se ve en dos
    // líneas); el que queda antes de un signo o después de uno de apertura sobra. El espacio duro
    // de los minutos se conserva.
    const t = linea
      .replace(/[^\S\u00A0]+/g, ' ')
      .replace(/ ([.,;:!?…»)])/g, '$1')
      .replace(/([«(¿¡]) /g, '$1')
      .trim()
    if (t) partes.push(t)
    linea = ''
  }
  const recorrer = (n: Node) => {
    if (n.nodeType === Node.TEXT_NODE) {
      linea += n.textContent ?? ''
      return
    }
    if (!(n instanceof Element)) return
    if (n.getAttribute('aria-hidden') === 'true' || n.tagName === 'BUTTON') return
    const bloque = BLOQUES.has(n.tagName)
    if (bloque) cerrar()
    else linea += ' '
    n.childNodes.forEach(recorrer)
    if (bloque) cerrar()
    else linea += ' '
  }
  raiz.childNodes.forEach(recorrer)
  cerrar()
  return partes.map((p) => (/[.!?:;…»)]$/.test(p) ? p : `${p}.`)).join(' ')
}

/**
 * Anuncia el texto del elemento al aparecer y cada vez que cambia, y lo retira al salir. Sin
 * `urgencia`, no hace nada: el mismo componente sirve para notas que no se anuncian.
 */
export function useAnunciarAlMostrar(ref: RefObject<Element | null>, urgencia: Urgencia | undefined) {
  const ultimo = useRef('')
  useEffect(() => {
    if (!urgencia || !ref.current) return
    const texto = textoParaLeer(ref.current)
    if (texto === ultimo.current) return
    retirar(ultimo.current)
    ultimo.current = texto
    anunciar(texto, urgencia)
  })
  useEffect(
    () => () => {
      retirar(ultimo.current)
      ultimo.current = ''
    },
    [],
  )
}

type Etiqueta = 'div' | 'p'

/**
 * Un aviso que aparece en una pantalla ya abierta: se ve igual que antes y se anuncia por las
 * regiones vivas. Reemplaza a `<div role="alert">` y `<p role="status">` cuando se montan ya
 * con su texto.
 */
export function Anunciado({
  urgencia,
  como = 'div',
  children,
  ...resto
}: HTMLAttributes<HTMLElement> & { urgencia: Urgencia; como?: Etiqueta; children: ReactNode }) {
  const ref = useRef<HTMLElement | null>(null)
  useAnunciarAlMostrar(ref, urgencia)
  const Tag = como
  return (
    <Tag data-aviso={urgencia} ref={ref as Ref<never>} {...resto}>
      {children}
    </Tag>
  )
}

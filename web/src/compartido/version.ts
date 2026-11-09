// MATU-67: saber si hay una versión nueva de la app (especificación docs/diseno/matu-67-aviso-version.md,
// sección 4). El build deja `version.json` con el identificador de la versión, y el mismo
// identificador va dentro del bundle (`__MATU_VERSION__`, vite.config.ts). La app pide
// `/version.json` sin caché al volver a la pestaña y cada 15 minutos mientras está visible; si el
// identificador es otro, el aviso queda pendiente. Si la revisión falla, no pasa nada visible.
//
// Todo vive en memoria: nada en localStorage, sessionStorage ni en la URL. Nunca recarga sola: solo
// el botón del aviso llama a `navegador.recargar()`.
import { useEffect, useSyncExternalStore } from 'react'

/** El identificador de la versión que corre, el mismo que el build escribe en version.json. */
export const VERSION_ACTUAL: string = __MATU_VERSION__

/** Cada cuánto se revisa mientras la pestaña está visible, y lo mínimo que espera tras «Más tarde» (D4). */
export const CADA_MS = 15 * 60 * 1000

/** Un identificador válido: corto y sin nada raro. Vacío o mal formado se ignora (4.6). */
const BIEN_FORMADO = /^[A-Za-z0-9._-]{1,64}$/

/**
 * `nada`: no hay versión nueva, o se dejó para más tarde. `pendiente`: hay una, pero el aviso espera
 * a que la persona salga del campo o de la pantalla que la retiene (4.2). `visible`: ya se mostró y
 * queda a la vista al cambiar de pantalla, sin volver a anunciarse.
 */
export type FaseVersion = 'nada' | 'pendiente' | 'visible'

let fase: FaseVersion = 'nada'
let pospuestoEn: number | null = null
let anunciado = false
const oyentes = new Set<() => void>()

function cambiar(f: FaseVersion) {
  if (fase === f) return
  fase = f
  oyentes.forEach((o) => o())
}

/** Lo que el navegador hace al tocar «Recargar». Es un objeto para que las pruebas lo puedan espiar. */
export const navegador = {
  recargar: () => window.location.reload(),
}

/**
 * Pide `/version.json` y, si trae otro identificador, deja el aviso pendiente. Después de «Más
 * tarde», no vuelve antes de 15 minutos. Cualquier falla (red, estado, JSON) se ignora en silencio.
 */
export async function revisarVersion(): Promise<void> {
  let nueva: unknown
  try {
    const r = await fetch('/version.json', { cache: 'no-store', credentials: 'same-origin', headers: { Accept: 'application/json' } })
    if (!r.ok) return
    nueva = ((await r.json()) as { version?: unknown } | null)?.version
  } catch {
    return
  }
  if (typeof nueva !== 'string' || !BIEN_FORMADO.test(nueva) || nueva === VERSION_ACTUAL) return
  if (fase !== 'nada') return
  if (pospuestoEn !== null && Date.now() - pospuestoEn < CADA_MS) return
  cambiar('pendiente')
}

/** El aviso pendiente pasa a la pantalla. Lo llama el aviso cuando ya no tiene que esperar. */
export function mostrarAviso() {
  if (fase === 'pendiente') cambiar('visible')
}

/** «Más tarde»: el aviso se va y vuelve en la próxima revisión, nunca antes de 15 minutos. */
export function posponerAviso() {
  pospuestoEn = Date.now()
  anunciado = false
  cambiar('nada')
}

/** El aviso se anuncia una sola vez, aunque cambie de pantalla (4.1). */
export function yaAnunciado() {
  return anunciado
}
export function marcarAnunciado() {
  anunciado = true
}

/** Vuelve a cero. Lo usan las pruebas entre un caso y otro. */
export function olvidarVersion() {
  fase = 'nada'
  pospuestoEn = null
  anunciado = false
  oyentes.forEach((o) => o())
}

const suscribir = (o: () => void) => {
  oyentes.add(o)
  return () => oyentes.delete(o)
}
const leer = () => fase

export function useFaseVersion(): FaseVersion {
  return useSyncExternalStore(suscribir, leer, leer)
}

/**
 * Revisa al volver a la pestaña y cada 15 minutos mientras está visible. Va una vez por app, en
 * `AppFamilia` y en `PaginaRelevo`. Al abrir no revisa: la app recién cargada ya es la última.
 */
export function useRevisarVersion() {
  useEffect(() => {
    let reloj: number | undefined
    const arrancar = () => {
      window.clearInterval(reloj)
      reloj = window.setInterval(() => void revisarVersion(), CADA_MS)
    }
    const alCambiar = () => {
      if (document.visibilityState === 'visible') {
        void revisarVersion()
        arrancar()
      } else window.clearInterval(reloj)
    }
    if (document.visibilityState === 'visible') arrancar()
    document.addEventListener('visibilitychange', alCambiar)
    return () => {
      window.clearInterval(reloj)
      document.removeEventListener('visibilitychange', alCambiar)
    }
  }, [])
}

/** Lo que hay sin guardar en un formulario, para no recargar encima (4.3 y G1). */
export interface SinGuardar {
  /** Lo escrito, si es texto de la ficha: se muestra si la entrada vence (5.7 de MATU-39). */
  texto: string
  /** Dónde está, para el título del aviso. Sin nombre, el título genérico. */
  donde?: string | null
  /** El título completo, cuando el de «Lo que escribiste en…» no calza (Insumos). Manda sobre `donde`. */
  titulo?: string | null
  /** El id del campo que recibe el foco con «Seguir escribiendo». */
  foco?: string | null
}

export type FuenteSinGuardar = () => SinGuardar | null

/**
 * Registra lo que un formulario tiene sin guardar en la ref del contexto. Si ya había otro
 * registrado (un panel abierto y un formulario a la vez), los dos se consultan. Devuelve la limpieza.
 */
export function registrarSinGuardar(ref: { current: FuenteSinGuardar | null } | null | undefined, fuente: FuenteSinGuardar) {
  if (!ref) return undefined
  let fuentes = registradas.get(ref)
  if (!fuentes) registradas.set(ref, (fuentes = new Set()))
  const lista = fuentes
  lista.add(fuente)
  // La última registrada se consulta primero: es la que la persona tiene a la vista.
  ref.current = () => {
    for (const f of [...lista].reverse()) {
      const s = f()
      if (s) return s
    }
    return null
  }
  return () => {
    lista.delete(fuente)
    if (!lista.size) ref.current = null
  }
}
const registradas = new WeakMap<object, Set<FuenteSinGuardar>>()

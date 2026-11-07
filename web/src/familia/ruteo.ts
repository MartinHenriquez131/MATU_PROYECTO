// Ruteo mínimo con la History API, sin dependencias. Las rutas nunca llevan nombres, ids de persona
// ni texto de la ficha (especificación 1): el grupo y la persona elegidos viven en memoria.
import { useSyncExternalStore } from 'react'

export type Ruta =
  | '/'
  | '/crear-cuenta'
  | '/entrar'
  | '/entrar/recuperar'
  | '/entrar/recuperar/codigo'
  | '/cuenta'
  | '/cuenta/celular'
  | '/empezar/grupo'
  | '/empezar/persona'
  | '/empezar/autorizacion'
  | '/ficha'
  | '/ficha/su-dia'
  | '/ficha/si-se-altera'
  | '/ficha/a-quien-llamar'
  | '/ficha/quien-la-vio'
  | '/ficha/quien-es'
  | '/ficha/lo-que-le-hace-bien'
  | '/ficha/comer-y-beber'
  | '/ficha/moverse-y-descansar'
  | '/ficha/como-hablarle'
  | '/ficha/sus-remedios'
  | '/insumos'
  | '/insumos/nuevo'
  | '/insumos/cambiar'
  | '/insumos/lista'
  | '/compartir'
  | '/compartir/listo'
  | '/compartir/enlaces'
  | '/grupo'
  | '/grupo/autorizar-ficha'
  | '/grupo/autorizar-insumos'

export const RUTAS: readonly Ruta[] = [
  '/',
  '/crear-cuenta',
  '/entrar',
  '/entrar/recuperar',
  '/entrar/recuperar/codigo',
  '/cuenta',
  '/cuenta/celular',
  '/empezar/grupo',
  '/empezar/persona',
  '/empezar/autorizacion',
  '/ficha',
  '/ficha/su-dia',
  '/ficha/si-se-altera',
  '/ficha/a-quien-llamar',
  '/ficha/quien-la-vio',
  '/ficha/quien-es',
  '/ficha/lo-que-le-hace-bien',
  '/ficha/comer-y-beber',
  '/ficha/moverse-y-descansar',
  '/ficha/como-hablarle',
  '/ficha/sus-remedios',
  '/insumos',
  '/insumos/nuevo',
  '/insumos/cambiar',
  '/insumos/lista',
  '/compartir',
  '/compartir/listo',
  '/compartir/enlaces',
  '/grupo',
  '/grupo/autorizar-ficha',
  '/grupo/autorizar-insumos',
]

/** Las que se ven sin haber entrado. */
export const PUBLICAS: ReadonlySet<Ruta> = new Set(['/crear-cuenta', '/entrar', '/entrar/recuperar', '/entrar/recuperar/codigo'])

const oyentes = new Set<() => void>()
const avisar = () => oyentes.forEach((fn) => fn())
if (typeof window !== 'undefined') window.addEventListener('popstate', avisar)

const leer = () => window.location.pathname.replace(/\/+$/, '') || '/'

export function useRuta(): string {
  return useSyncExternalStore(
    (fn) => {
      oyentes.add(fn)
      return () => oyentes.delete(fn)
    },
    leer,
  )
}

/** Cambia de ruta. Con `reemplazar` no deja una entrada nueva en el historial (redirecciones). */
export function navegar(ruta: Ruta, { reemplazar = false }: { reemplazar?: boolean } = {}) {
  if (leer() === ruta) {
    avisar()
    return
  }
  if (reemplazar) window.history.replaceState(null, '', ruta)
  else window.history.pushState(null, '', ruta)
  avisar()
}

export const esRuta = (r: string): r is Ruta => (RUTAS as readonly string[]).includes(r)

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
  | '/cuenta/donde-entraste'
  | '/cuenta/datos'
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
  | '/insumos/catalogo'
  | '/insumos/pedido'
  | '/insumos/pedido/direccion'
  | '/insumos/pedido/resumen'
  | '/insumos/pedido/pago'
  | '/compartir'
  | '/compartir/listo'
  | '/compartir/enlaces'
  | '/grupo'
  | '/grupo/autorizar-ficha'
  | '/grupo/autorizar-insumos'
  | '/grupo/autorizar-pedidos'
  | '/grupo/datos'
  | '/grupo/invitar'
  | '/grupo/invitar/listo'
  | '/invitacion'

/**
 * MATU-63 (especificación 2.1): las rutas de la consola del comercio, otra raíz de main.tsx. Usan el
 * mismo `navegar` y `useRuta`. Nunca llevan ids ni la referencia: la parte elegida vive en memoria.
 */
export type RutaComercio = '/comercio' | '/comercio/entrar' | '/comercio/pedido' | '/comercio/productos'

export const RUTAS: readonly Ruta[] = [
  '/',
  '/crear-cuenta',
  '/entrar',
  '/entrar/recuperar',
  '/entrar/recuperar/codigo',
  '/cuenta',
  '/cuenta/celular',
  '/cuenta/donde-entraste',
  '/cuenta/datos',
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
  '/insumos/catalogo',
  '/insumos/pedido',
  '/insumos/pedido/direccion',
  '/insumos/pedido/resumen',
  '/insumos/pedido/pago',
  '/compartir',
  '/compartir/listo',
  '/compartir/enlaces',
  '/grupo',
  '/grupo/autorizar-ficha',
  '/grupo/autorizar-insumos',
  '/grupo/autorizar-pedidos',
  '/grupo/datos',
  '/grupo/invitar',
  '/grupo/invitar/listo',
  '/invitacion',
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
export function navegar(ruta: Ruta | RutaComercio, { reemplazar = false }: { reemplazar?: boolean } = {}) {
  if (leer() === ruta) {
    avisar()
    return
  }
  if (reemplazar) window.history.replaceState(null, '', ruta)
  else window.history.pushState(null, '', ruta)
  avisar()
}

export const esRuta = (r: string): r is Ruta => (RUTAS as readonly string[]).includes(r)

import { useSyncExternalStore } from 'react'

const consulta = '(prefers-reduced-motion: reduce)'

function suscribir(cb: () => void) {
  const m = window.matchMedia(consulta)
  m.addEventListener('change', cb)
  return () => m.removeEventListener('change', cb)
}

/** true si la persona pidió menos movimiento en su sistema. */
export function useMovimientoReducido(): boolean {
  return useSyncExternalStore(suscribir, () => window.matchMedia(consulta).matches, () => false)
}

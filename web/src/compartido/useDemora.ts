// Lo que carga rápido no muestra nada (especificación MATU-39, 3.1 y 5.1). Vive en compartido/
// desde MATU-75: la página pública /privacidad lo usa sin cargar la app de la familia.
import { useEffect, useState } from 'react'

/** `true` pasados 400 ms. */
export function useDemora(ms = 400) {
  const [ver, setVer] = useState(false)
  useEffect(() => {
    const t = window.setTimeout(() => setVer(true), ms)
    return () => window.clearTimeout(t)
  }, [ms])
  return ver
}

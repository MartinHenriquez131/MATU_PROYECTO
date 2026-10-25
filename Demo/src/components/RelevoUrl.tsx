// La URL del relevo es /r#<token>. El fragmento no viaja al servidor; después del canje se
// limpia con history.replaceState para que el token no quede en el historial del teléfono.
// Es el único dato que la demo pone en la URL.
import { useEffect } from 'react'
import { useDemo } from '../demo/estado'

const esWeb = () => location.protocol === 'http:' || location.protocol === 'https:'

/** Carpeta desde donde se sirve la demo, para que funcione también fuera de la raíz. */
function raiz(): URL {
  const u = new URL(location.href)
  u.hash = ''
  u.search = ''
  if (u.pathname.endsWith('/r')) u.pathname = u.pathname.slice(0, -1)
  else u.pathname = u.pathname.replace(/[^/]*$/, '')
  return u
}

export function rutaDeRelevo(): boolean {
  return esWeb() && location.pathname.endsWith('/r')
}

export function leerTokenDelFragmento(): string | null {
  const t = location.hash.slice(1)
  return /^[A-Za-z0-9_-]{20,}$/.test(t) ? t : null
}

export function RelevoUrl() {
  const { s } = useDemo()
  const { rol } = s
  const { token, urlLimpia } = s.relevo
  useEffect(() => {
    if (rol === 'relevo' && token && !urlLimpia) {
      const destino = esWeb() ? `${new URL('r', raiz()).pathname}#${token}` : `#${token}`
      if (location.hash.slice(1) !== token) history.pushState(null, '', destino)
      return
    }
    if (rol === 'relevo' && urlLimpia) {
      history.replaceState(null, '', esWeb() ? new URL('r', raiz()).pathname : location.pathname)
      return
    }
    if (location.hash || rutaDeRelevo()) history.replaceState(null, '', esWeb() ? raiz().pathname : location.pathname)
  }, [rol, token, urlLimpia])
  return null
}

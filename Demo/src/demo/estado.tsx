// Contexto de la demo. El estado vive solo en memoria de React: dos ventanas no se
// sincronizan y al recargar se parte de cero, a propósito.
import { createContext, useContext, useReducer, type ReactNode } from 'react'
import { estadoInicial } from './logica'
import type { Estado, Rol } from './tipos'

export type Cambio = (s: Estado) => Estado

interface ContextoDemo {
  s: Estado
  haz: (cambio: Cambio) => void
}

const Contexto = createContext<ContextoDemo | null>(null)

function aplicar(s: Estado, cambio: Cambio): Estado {
  return cambio(s)
}

export function ProveedorDemo({ children, rol, token }: { children: ReactNode; rol: Rol; token: string | null }) {
  const [s, haz] = useReducer(aplicar, null, () => estadoInicial(rol, token))
  return <Contexto value={{ s, haz }}>{children}</Contexto>
}

export function useDemo(): ContextoDemo {
  const c = useContext(Contexto)
  if (!c) throw new Error('useDemo fuera de ProveedorDemo')
  return c
}

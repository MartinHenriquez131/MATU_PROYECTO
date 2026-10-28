// Estado del presentador: no es parte de MATU ni del estado de la demo. "Reiniciar demo" no lo
// toca, y nada de esto se guarda en el navegador.
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type Tema = 'sistema' | 'claro' | 'oscuro'

interface ContextoPresentador {
  cajon: boolean
  setCajon: (v: boolean | ((x: boolean) => boolean)) => void
  presentacion: boolean
  setPresentacion: (v: boolean | ((x: boolean) => boolean)) => void
  atajos: boolean
  setAtajos: (v: boolean) => void
  tema: Tema
  setTema: (t: Tema) => void
}

const Contexto = createContext<ContextoPresentador | null>(null)

export function ProveedorPresentador({ children }: { children: ReactNode }) {
  const [cajon, setCajon] = useState(false)
  const [presentacion, setPresentacion] = useState(false)
  const [atajos, setAtajos] = useState(true)
  const [tema, setTema] = useState<Tema>('sistema')

  useEffect(() => {
    const raiz = document.documentElement
    if (tema === 'sistema') delete raiz.dataset.tema
    else raiz.dataset.tema = tema
  }, [tema])

  return (
    <Contexto value={{ cajon, setCajon, presentacion, setPresentacion, atajos, setAtajos, tema, setTema }}>{children}</Contexto>
  )
}

export function usePresentador(): ContextoPresentador {
  const c = useContext(Contexto)
  if (!c) throw new Error('usePresentador fuera de ProveedorPresentador')
  return c
}

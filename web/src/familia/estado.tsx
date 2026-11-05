// Estado de la app de la familia, solo en memoria (especificación 1 y 6): la entrada, los grupos,
// las personas, la ficha y lo escrito en el alta. Nada va a localStorage, sessionStorage ni la URL.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  listarGrupos,
  listarPersonas,
  rolDe,
  type Ficha,
  type Grupo,
  type PersonaListada,
  type Rol,
} from '../compartido/api/familia'
import { escucharSesion, fijarGrupo, renovar, salir as cerrarSesion } from '../compartido/api/sesion'
import type { Apoyo } from './datos'
import { navegar, type Ruta } from './ruteo'

export type Fase = 'cargando' | 'fuera' | 'dentro' | 'error'
export type AvisoEntrar = 'vencida' | 'salio' | 'clave-cambiada' | null

/** Lo escrito en «¿A quién cuidas?», que vive en memoria hasta el POST de la autorización. */
export interface BorradorPersona {
  nombre: string
  pila: string
  apoyo: Apoyo | null
  calle: string
  numero: string
  comuna: string
  depto: string
}
export const BORRADOR_VACIO: BorradorPersona = { nombre: '', pila: '', apoyo: null, calle: '', numero: '', comuna: '', depto: '' }

interface Estado {
  fase: Fase
  grupos: Grupo[]
  grupoId: string | null
  personas: PersonaListada[]
  personaId: string | null
  ficha: Ficha | null
  avisoEntrar: AvisoEntrar
  /** Correo para «Entrar con ese correo» (3.2), en memoria. */
  correo: string
  borrador: BorradorPersona
  /** Ruta pedida antes de entrar, para volver a ella (1). */
  destino: Ruta | null
  /** Nota de una sola vez al llegar a una pantalla (guardado, conflicto resuelto). */
  aviso: { titulo: string; texto?: string } | null
  /** 5.7: la entrada venció con texto sin guardar. */
  textoPerdido: string | null
  /** MATU-57 5.1: desde dónde se abrió «Confirma tu celular» (la primera entrada ofrece «Ahora no»). */
  celularDesde: 'primera' | 'cuenta'
}

interface Contexto extends Estado {
  grupo: Grupo | null
  persona: PersonaListada | null
  rol: Rol
  cargar: () => Promise<void>
  alEntrar: () => Promise<void>
  salir: () => Promise<void>
  elegir: (grupoId: string, personaId: string | null) => Promise<void>
  fijar: (cambios: Partial<Estado>) => void
  anunciar: (texto: string) => void
  /** El editor registra aquí lo que tiene sin guardar (5.7). */
  sinGuardar: React.RefObject<(() => string | null) | null>
}

const Ctx = createContext<Contexto | null>(null)

export function useFamilia(): Contexto {
  const c = useContext(Ctx)
  if (!c) throw new Error('useFamilia fuera de ProveedorFamilia')
  return c
}

const INICIAL: Estado = {
  fase: 'cargando',
  grupos: [],
  grupoId: null,
  personas: [],
  personaId: null,
  ficha: null,
  avisoEntrar: null,
  correo: '',
  borrador: BORRADOR_VACIO,
  destino: null,
  aviso: null,
  textoPerdido: null,
  celularDesde: 'cuenta',
}

export function ProveedorFamilia({ children }: { children: ReactNode }) {
  const [s, setS] = useState<Estado>(INICIAL)
  const [anuncio, setAnuncio] = useState('')
  const sinGuardar = useRef<(() => string | null) | null>(null)

  const fijar = useCallback((cambios: Partial<Estado>) => setS((x) => ({ ...x, ...cambios })), [])

  const anunciar = useCallback((texto: string) => {
    setAnuncio('')
    window.setTimeout(() => setAnuncio(texto), 50)
  }, [])

  /** Pide grupos y personas, y elige el primer grupo y la primera persona (2.3). */
  const alEntrar = useCallback(async () => {
    const grupos = await listarGrupos()
    const g = grupos[0] ?? null
    fijarGrupo(g?.id ?? null)
    const personas = g ? await listarPersonas(g.id) : []
    setS((x) => ({ ...x, fase: 'dentro', grupos, grupoId: g?.id ?? null, personas, personaId: personas[0]?.id ?? null, ficha: null, avisoEntrar: null }))
  }, [])

  /** 3.1: al abrir o recargar, renovar con la cookie. */
  const cargar = useCallback(async () => {
    setS((x) => ({ ...x, fase: 'cargando' }))
    try {
      const ok = await renovar()
      if (!ok) return setS((x) => ({ ...x, fase: 'fuera' }))
      await alEntrar()
    } catch {
      setS((x) => ({ ...x, fase: 'error' }))
    }
  }, [alEntrar])

  const olvidar = useCallback((aviso: AvisoEntrar, textoPerdido: string | null = null) => {
    fijarGrupo(null)
    setS((x) => ({ ...INICIAL, fase: 'fuera', avisoEntrar: aviso, destino: x.destino, textoPerdido }))
  }, [])

  const salir = useCallback(async () => {
    await cerrarSesion()
    olvidar('salio')
    navegar('/entrar')
  }, [olvidar])

  const elegir = useCallback(async (grupoId: string, personaId: string | null) => {
    fijarGrupo(grupoId)
    const lista = await listarPersonas(grupoId)
    setS((x) => ({ ...x, grupoId, personas: lista, personaId: personaId ?? lista[0]?.id ?? null, ficha: null }))
  }, [])

  useEffect(() => {
    void cargar()
  }, [cargar])

  useEffect(
    () =>
      escucharSesion((suceso) => {
        if (suceso === 'salio') {
          olvidar('salio')
          navegar('/entrar')
          return
        }
        // Venció: si el editor tiene texto sin guardar, se muestra antes de ir a entrar (5.7).
        const texto = sinGuardar.current?.() ?? null
        olvidar('vencida', texto && texto.trim() ? texto : null)
        if (!texto || !texto.trim()) navegar('/entrar')
      }),
    [olvidar],
  )

  const valor = useMemo<Contexto>(() => {
    const grupo = s.grupos.find((g) => g.id === s.grupoId) ?? null
    return {
      ...s,
      grupo,
      persona: s.personas.find((p) => p.id === s.personaId) ?? null,
      rol: rolDe(grupo),
      cargar,
      alEntrar,
      salir,
      elegir,
      fijar,
      anunciar,
      sinGuardar,
    }
  }, [s, cargar, alEntrar, salir, elegir, fijar, anunciar])

  return (
    <Ctx.Provider value={valor}>
      {children}
      <div aria-live="polite" className="sr-only">
        {anuncio}
      </div>
    </Ctx.Provider>
  )
}

/** Qué secciones ve cada rol (2.2 y 5.8). */
export function puedeVerFicha(rol: Rol, grupo: Grupo | null): boolean {
  if (rol === 'admin' || rol === 'cuidador') return true
  if (rol === 'pagador') return grupo?.puede_ver_plan === true
  return false
}
export const puedeEditar = (rol: Rol) => rol === 'admin' || rol === 'cuidador'
export const puedeCompartir = puedeEditar

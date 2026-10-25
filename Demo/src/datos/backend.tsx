// Elige el adaptador al arrancar: si GET /v1/salud responde, modo real; si no, simulado.
// La demo nunca se rompe frente al público: ante una falla de red se ofrece seguir en simulado.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { ApiMatu, Llamada, Modo } from './api'
import { adaptadorReal, hayBackend } from './real'
import { adaptadorSimulado } from './simulado'

export type Deteccion = 'detectando' | Modo
export type MotivoSimulado = 'sin-backend' | 'archivo-unico' | 'por-falla' | null

interface Credenciales {
  nombre: string
  email: string
  contrasena: string
}

interface ContextoBackend {
  modo: Deteccion
  motivo: MotivoSimulado
  api: ApiMatu
  llamadas: Llamada[]
  /** Datos de la cuenta creada en esta sesión, solo en memoria, para entrar sin reescribirlos. */
  credenciales: Credenciales | null
  recordar: (c: Credenciales) => void
  grupoId: string | null
  fijarGrupo: (id: string | null) => void
  pasarASimulado: () => Promise<ApiMatu>
  reintentarReal: () => Promise<boolean>
  olvidarSesion: () => void
}

const Contexto = createContext<ContextoBackend | null>(null)

// build:single no tiene servidor: siempre simulado.
const ARCHIVO_UNICO = import.meta.env.MODE === 'single'

// Una sola consulta al arrancar. Con StrictMode el efecto corre dos veces en desarrollo y la
// consola mostraba dos 502 de /v1/salud en vez de uno.
let deteccionInicial: Promise<boolean> | null = null

export function ProveedorBackend({ children }: { children: ReactNode }) {
  const [llamadas, setLlamadas] = useState<Llamada[]>([])
  const seq = useRef(0)
  const anotar = useCallback((l: Omit<Llamada, 'id'>) => {
    seq.current += 1
    const nueva = { ...l, id: seq.current }
    setLlamadas((xs) => [nueva, ...xs].slice(0, 8))
  }, [])

  const real = useMemo(() => adaptadorReal(anotar), [anotar])
  const simuladoRef = useRef<ApiMatu>(adaptadorSimulado())
  const [modo, setModo] = useState<Deteccion>(ARCHIVO_UNICO ? 'simulado' : 'detectando')
  const [motivo, setMotivo] = useState<MotivoSimulado>(ARCHIVO_UNICO ? 'archivo-unico' : null)
  const [credenciales, setCredenciales] = useState<Credenciales | null>(null)
  const [grupoId, setGrupoId] = useState<string | null>(null)

  useEffect(() => {
    if (ARCHIVO_UNICO) return
    let vivo = true
    deteccionInicial ??= hayBackend(anotar)
    deteccionInicial.then((ok) => {
      if (!vivo) return
      setModo(ok ? 'real' : 'simulado')
      setMotivo(ok ? null : 'sin-backend')
    })
    return () => {
      vivo = false
    }
  }, [anotar])

  const pasarASimulado = useCallback(async () => {
    const sim = adaptadorSimulado()
    // Si ya había una cuenta en esta sesión, la simulada parte con la misma, para no repetir pasos.
    if (credenciales) {
      await sim.crearCuenta(credenciales.nombre, credenciales.email, credenciales.contrasena).catch(() => undefined)
      await sim.iniciarSesion(credenciales.email, credenciales.contrasena).catch(() => undefined)
    }
    simuladoRef.current = sim
    real.cerrar()
    setGrupoId(null)
    setModo('simulado')
    setMotivo('por-falla')
    return sim
  }, [credenciales, real])

  const reintentarReal = useCallback(async () => {
    if (ARCHIVO_UNICO) return false
    const ok = await hayBackend(anotar)
    if (ok) {
      setModo('real')
      setMotivo(null)
      setGrupoId(null)
    }
    return ok
  }, [anotar])

  const olvidarSesion = useCallback(() => {
    real.cerrar()
    simuladoRef.current = adaptadorSimulado()
    setCredenciales(null)
    setGrupoId(null)
  }, [real])

  const fijarGrupo = setGrupoId

  const valor: ContextoBackend = {
    modo,
    motivo,
    api: modo === 'real' ? real : simuladoRef.current,
    llamadas,
    credenciales,
    recordar: setCredenciales,
    grupoId,
    fijarGrupo,
    pasarASimulado,
    reintentarReal,
    olvidarSesion,
  }
  return <Contexto value={valor}>{children}</Contexto>
}

export function useBackend(): ContextoBackend {
  const c = useContext(Contexto)
  if (!c) throw new Error('useBackend fuera de ProveedorBackend')
  return c
}

// Estado de la consola del comercio (MATU-63), solo en memoria: la entrada, el comercio de la cuenta
// y la parte elegida. Nada va a localStorage, sessionStorage, la URL ni `history.state`.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { leerFallo } from '../compartido/api/cliente'
import { verComercio, type ComercioDeLaCuenta } from '../compartido/api/comercio'
import { escucharSesion, renovar, salir as cerrarSesion, tipoDeCuenta } from '../compartido/api/sesion'
import { CORREO_CONTACTO } from '../compartido/contacto'
import { navegar, type RutaComercio } from '../familia/ruteo'

export type FaseComercio = 'cargando' | 'fuera' | 'dentro' | 'inactiva' | 'error'
/** 4.3: el aviso arriba de Entrar. `familia` es O1; `inactiva`, el 403 al entrar. */
export type AvisoEntrarComercio = 'vencida' | 'salio' | 'familia' | 'inactiva' | null

interface EstadoComercio {
  fase: FaseComercio
  comercio: ComercioDeLaCuenta | null
  avisoEntrar: AvisoEntrarComercio
  /** 2.1: la ruta pedida antes de entrar, sin la parte elegida. */
  destino: RutaComercio | null
  /** 2.1: la parte elegida, nunca en la URL. Al recargar no existe y `/comercio/pedido` vuelve a `/comercio`. */
  parteId: string | null
}

interface ContextoComercio extends EstadoComercio {
  /** O2: el contacto de operación del piloto. Sin el del comercio, el correo de contacto de MATU. */
  contacto: string
  cargar: () => Promise<void>
  /** Después de `POST /v1/sesiones` de una cuenta de comercio: pide el comercio. */
  alEntrar: () => Promise<'dentro' | 'inactiva'>
  salir: () => Promise<void>
  fijar: (cambios: Partial<EstadoComercio>) => void
  /** 5.7: un 403 `comercio-inactivo` en cualquier vista. */
  quedoInactiva: () => void
}

const Ctx = createContext<ContextoComercio | null>(null)

export function useComercio(): ContextoComercio {
  const c = useContext(Ctx)
  if (!c) throw new Error('useComercio fuera de ProveedorComercio')
  return c
}

const INICIAL: EstadoComercio = { fase: 'cargando', comercio: null, avisoEntrar: null, destino: null, parteId: null }

export function ProveedorComercio({ children }: { children: ReactNode }) {
  const [s, setS] = useState<EstadoComercio>(INICIAL)
  const fijar = useCallback((cambios: Partial<EstadoComercio>) => setS((x) => ({ ...x, ...cambios })), [])

  const alEntrar = useCallback(async (): Promise<'dentro' | 'inactiva'> => {
    try {
      const comercio = await verComercio()
      setS((x) => ({ ...x, fase: 'dentro', comercio, avisoEntrar: null }))
      return 'dentro'
    } catch (e) {
      const f = leerFallo(e)
      if (f.status === 403) return 'inactiva'
      throw e
    }
  }, [])

  /** Al abrir o recargar: renovar con la cookie y pedir el comercio de la cuenta. */
  const cargar = useCallback(async () => {
    setS((x) => ({ ...x, fase: 'cargando' }))
    try {
      if (!(await renovar())) return setS((x) => ({ ...x, fase: 'fuera' }))
      // O1: una entrada de familia no ve la consola; nunca se dice si el correo existe.
      if (tipoDeCuenta() !== 'comercio') return setS((x) => ({ ...x, fase: 'fuera', avisoEntrar: 'familia' }))
      const r = await alEntrar()
      if (r === 'inactiva') setS((x) => ({ ...x, fase: 'inactiva' }))
    } catch (e) {
      // 404: la cuenta ya no es de un comercio (decisión 409).
      if (leerFallo(e).status === 404) return setS((x) => ({ ...x, fase: 'fuera', avisoEntrar: 'familia' }))
      setS((x) => ({ ...x, fase: 'error' }))
    }
  }, [alEntrar])

  const olvidar = useCallback((aviso: AvisoEntrarComercio) => {
    setS((x) => ({ ...INICIAL, fase: 'fuera', avisoEntrar: aviso, destino: aviso === 'vencida' ? x.destino : null }))
  }, [])

  const salir = useCallback(async () => {
    await cerrarSesion()
    olvidar('salio')
    navegar('/comercio/entrar')
  }, [olvidar])

  const quedoInactiva = useCallback(() => setS((x) => ({ ...x, fase: 'inactiva', parteId: null })), [])

  useEffect(() => {
    void cargar()
  }, [cargar])

  useEffect(
    () =>
      escucharSesion((suceso) => {
        olvidar(suceso === 'salio' ? 'salio' : 'vencida')
        navegar('/comercio/entrar', { reemplazar: true })
      }),
    [olvidar],
  )

  const valor = useMemo<ContextoComercio>(
    () => ({ ...s, contacto: s.comercio?.contacto || CORREO_CONTACTO, cargar, alEntrar, salir, fijar, quedoInactiva }),
    [s, cargar, alEntrar, salir, fijar, quedoInactiva],
  )
  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>
}

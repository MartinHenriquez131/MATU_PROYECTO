// Estado de la consola de operación (MATU-81), solo en memoria: la entrada, hasta cuándo vale y lo
// elegido (el pedido, el retracto y la incidencia). Nada va a localStorage, sessionStorage, la URL,
// `history.state` ni el `<title>` (C7, C18, C20). El desafío del segundo factor y el código de retiro
// viven en la memoria de su pantalla, no aquí.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { leerFallo } from '../compartido/api/cliente'
import { esProblema } from '../compartido/api/operacion'
import { cerrarSinAvisar, escucharSesion, esVencida, renovar, salir as cerrarSesion, tipoDeCuenta, venceLaEntrada } from '../compartido/api/sesion'
import { navegar, type RutaOperacion } from '../familia/ruteo'

export type FaseOperacion = 'cargando' | 'fuera' | 'dentro' | 'error'
/** 4.4: el aviso arriba de Entrar. `otra` es una cuenta de familia o de comercio. */
export type AvisoEntrarOperacion = 'vencida' | 'salio' | 'otra' | null
/** De qué lista vino el pedido abierto: cambia la pestaña activa y el «Volver» (2.1 y 10). */
export type OrigenPedido = '/operacion' | '/operacion/cobros'

interface EstadoOperacion {
  fase: FaseOperacion
  avisoEntrar: AvisoEntrarOperacion
  /** 2.1: la ruta pedida antes de entrar, sin lo elegido. */
  destino: RutaOperacion | null
  /** 3 (C31): `sesion_vence_en` de la respuesta de la entrada. */
  venceEn: string | null
  pedidoId: string | null
  origen: OrigenPedido
  retractoId: string | null
  incidenciaId: string | null
}

interface ContextoOperacion extends EstadoOperacion {
  cargar: () => Promise<void>
  /** Después de `POST /v1/sesiones/mfa`: la entrada ya trae la marca del segundo factor. */
  alEntrar: () => void
  salir: () => Promise<void>
  fijar: (cambios: Partial<EstadoOperacion>) => void
  /**
   * Un fallo de cualquier pantalla: `true` si ya se resolvió aquí (la entrada venció, perdió el
   * segundo factor, o la cuenta no es de operación). Con `lista`, un 404 es la cuenta (5.7); en un
   * detalle, un 404 es lo pedido y lo resuelve la pantalla.
   */
  fallo: (error: unknown, lista?: boolean) => boolean
}

const PRIVADAS: readonly RutaOperacion[] = ['/operacion', '/operacion/pedido', '/operacion/retractos', '/operacion/incidencias', '/operacion/cobros', '/operacion/catalogo']

/** 2.1: la ruta a la que se vuelve después de entrar. Del pedido se vuelve a la lista: lo elegido no se guarda. */
export function rutaSinElegido(ruta: string): RutaOperacion | null {
  const r = ruta.replace(/\/+$/, '') || '/'
  if (!(PRIVADAS as readonly string[]).includes(r)) return null
  return r === '/operacion/pedido' ? '/operacion' : (r as RutaOperacion)
}

const Ctx = createContext<ContextoOperacion | null>(null)

export function useOperacion(): ContextoOperacion {
  const c = useContext(Ctx)
  if (!c) throw new Error('useOperacion fuera de ProveedorOperacion')
  return c
}

const INICIAL: EstadoOperacion = {
  fase: 'cargando',
  avisoEntrar: null,
  destino: null,
  venceEn: null,
  pedidoId: null,
  origen: '/operacion',
  retractoId: null,
  incidenciaId: null,
}

export function ProveedorOperacion({ children }: { children: ReactNode }) {
  const [s, setS] = useState<EstadoOperacion>(INICIAL)
  const fijar = useCallback((cambios: Partial<EstadoOperacion>) => setS((x) => ({ ...x, ...cambios })), [])

  const alEntrar = useCallback(() => setS((x) => ({ ...x, fase: 'dentro', avisoEntrar: null, venceEn: venceLaEntrada() })), [])

  /** Al abrir o recargar: renovar con la cookie. Solo una cuenta de operación con su marca entra. */
  const cargar = useCallback(async () => {
    setS((x) => ({ ...x, fase: 'cargando' }))
    try {
      if (!(await renovar())) return setS((x) => ({ ...x, fase: 'fuera' }))
      // 4.4: una entrada de familia o de comercio no ve la consola; nunca se dice si el correo existe.
      if (tipoDeCuenta() !== 'operacion') return setS((x) => ({ ...x, fase: 'fuera', avisoEntrar: 'otra' }))
      setS((x) => ({ ...x, fase: 'dentro', venceEn: venceLaEntrada() }))
    } catch {
      setS((x) => ({ ...x, fase: 'error' }))
    }
  }, [])

  /** Se olvida todo lo elegido. `vencida` conserva la ruta (sin lo elegido) para volver a ella después de entrar. */
  const olvidar = useCallback((aviso: AvisoEntrarOperacion) => {
    const aqui = rutaSinElegido(window.location.pathname)
    setS((x) => ({ ...INICIAL, fase: 'fuera', avisoEntrar: aviso, destino: aviso === 'vencida' ? (aqui ?? x.destino) : null }))
  }, [])

  const salir = useCallback(async () => {
    await cerrarSesion()
    olvidar('salio')
    navegar('/operacion/entrar')
  }, [olvidar])

  const fallo = useCallback(
    (error: unknown, lista = false): boolean => {
      if (esVencida(error)) return true
      const f = leerFallo(error)
      // 5.7 (C30): sin la marca del segundo factor o pasadas las 12 horas, a la contraseña.
      if (f.status === 401 && esProblema(f.tipo, 'mfa-requerido')) {
        void cerrarSinAvisar()
        olvidar('vencida')
        navegar('/operacion/entrar', { reemplazar: true })
        return true
      }
      // 5.7: un 404 de una lista es que la cuenta no es de operación.
      if (lista && f.status === 404) {
        void cerrarSinAvisar()
        olvidar('otra')
        navegar('/operacion/entrar', { reemplazar: true })
        return true
      }
      return false
    },
    [olvidar],
  )

  useEffect(() => {
    void cargar()
  }, [cargar])

  useEffect(
    () =>
      escucharSesion((suceso) => {
        olvidar(suceso === 'salio' ? 'salio' : 'vencida')
        navegar('/operacion/entrar', { reemplazar: true })
      }),
    [olvidar],
  )

  // C31: a la hora en que vence la entrada (12 horas desde el código), se vuelve a la contraseña sin
  // esperar a que una petición responda 401. Lo elegido y el código de retiro se borran con ella.
  const { fase, venceEn } = s
  useEffect(() => {
    if (fase !== 'dentro' || !venceEn) return
    const espera = new Date(venceEn).getTime() - Date.now()
    if (!Number.isFinite(espera)) return
    const t = window.setTimeout(
      () => {
        void cerrarSinAvisar()
        olvidar('vencida')
        navegar('/operacion/entrar', { reemplazar: true })
      },
      Math.max(0, Math.min(espera, 2 ** 31 - 1)),
    )
    return () => window.clearTimeout(t)
  }, [fase, venceEn, olvidar])

  const valor = useMemo<ContextoOperacion>(() => ({ ...s, cargar, alEntrar, salir, fijar, fallo }), [s, cargar, alEntrar, salir, fijar, fallo])
  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>
}

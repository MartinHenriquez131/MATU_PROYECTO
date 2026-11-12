// Estado de la app de la familia, solo en memoria (especificación 1 y 6): la entrada, los grupos,
// las personas, la ficha y lo escrito en el alta. Nada va a localStorage, sessionStorage ni la URL.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  listarGrupos,
  listarPersonas,
  rolDe,
  type AutorizacionVista,
  type Ficha,
  type Finalidad,
  type Grupo,
  type PersonaListada,
  type PresentacionInvitacion,
  type Rol,
  type VerificacionInvitacion,
} from '../compartido/api/familia'
import { verCatalogo } from '../compartido/api/catalogo'
import { leerFallo } from '../compartido/api/cliente'
import { anunciar as anunciarEnRegion } from '../compartido/ui/Anuncios'
import type { FuenteSinGuardar } from '../compartido/version'
import { escucharSesion, fijarGrupo, renovar, salir as cerrarSesion } from '../compartido/api/sesion'
import type { Apoyo } from './datos'
import { navegar, type Ruta } from './ruteo'

export type Fase = 'cargando' | 'fuera' | 'dentro' | 'error'
/** Un botón en la nota de llegada (MATU-48 2.3: «Compartir con un relevo», «Crear un enlace nuevo»). */
export interface AccionAviso {
  texto: string
  ruta: Ruta
  variante: 'principal' | 'secundario' | 'texto'
}
export type AvisoEntrar = 'vencida' | 'salio' | 'clave-cambiada' | null

/**
 * MATU-61 (4): lo que se quería agregar al pedido cuando faltaba la autorización, desde el catálogo
 * (un producto de un comercio) o desde la lista (sus líneas). Vive solo en memoria y se hace al
 * autorizar; nunca va a la URL ni al almacenamiento del navegador (C18).
 */
export interface IntencionPedido {
  personaId: string
  desde: 'catalogo' | 'lista'
  agregar: { producto_id: string; nombre: string; oferta_id: string; cantidad: number; deLista: string | null }[]
  /** Los nombres de la lista que no están en el catálogo (6.4). */
  fuera: string[]
}

/** MATU-61 (6.4 y 7.3): la nota al llegar a «Tu pedido», hasta salir de la pantalla. */
export interface LlegadaPedido {
  personaId: string
  tono: 'ok' | 'rocio'
  parrafos: string[]
  /** «En tu lista: …» de las líneas que vinieron de la lista, por producto (7.4). */
  deLista: Record<string, string>
}

/** Lo escrito en «¿A quién cuidas?», que vive en memoria hasta el POST de la autorización. */
export interface BorradorPersona {
  nombre: string
  pila: string
  apoyo: Apoyo | null
}
export const BORRADOR_VACIO: BorradorPersona = { nombre: '', pila: '', apoyo: null }

/**
 * MATU-53 (2.1): la invitación que se está abriendo en `/invitacion`. El token sale del fragmento y el
 * código de lo que se escribió; los dos viven solo aquí, en memoria, mientras la persona crea su cuenta
 * o entra (que son navegaciones de la misma app, sin recargar). Nunca van al almacenamiento del
 * navegador, a `history.state`, al `<title>` ni a la URL.
 */
export interface InvitacionEnMemoria {
  token: string
  presentacion: PresentacionInvitacion | null
  /** El código, después de verificarlo (4.3). La aceptación lo vuelve a mandar. */
  codigo: string | null
  verificacion: VerificacionInvitacion | null
}

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
  /**
   * `enfocar` (MATU-72 4.3): la nota recibe el foco al mostrarse. Solo cuando la pantalla no cambia de
   * ruta y el control que se tocó ya no existe; si cambia, el foco va al `h1` (regla de ruta).
   */
  aviso: { titulo: string; texto?: string; tono?: 'ok' | 'rocio'; accion?: AccionAviso; enfocar?: boolean } | null
  /** 5.7: la entrada venció con texto sin guardar. */
  textoPerdido: string | null
  /**
   * MATU-48 (decisión 33): lo último que la API dijo de la autorización de la persona elegida, por
   * un 403 de la ficha o de compartir. `null` = vigente o no se sabe. Con ella vencida o sin
   * registrar, los enlaces que la API lista como `vigente` están en pausa.
   */
  autorizacion: Autorizacion
  /** MATU-57 5.1: desde dónde se abrió «Confirma tu celular» (la primera entrada ofrece «Ahora no»). */
  celularDesde: 'primera' | 'cuenta'
  /**
   * MATU-44 2.1: qué se va a volver a autorizar, de la persona elegida. Lo fija «Volver a autorizar»
   * (en Grupo familiar o en el aviso de la ficha) y lo vacían las dos pantallas al salir. Con `vista`
   * (lo que mostraba Grupo familiar) la pantalla no la vuelve a pedir. Al recargar no existe y la
   * subruta vuelve a `/grupo`. Solo en memoria.
   */
  reautorizar: { personaId: string; finalidad: Finalidad; vista: AutorizacionVista | null } | null
  /**
   * MATU-61 (2.2): si la capa 3 está encendida (el catálogo responde), `false` si responde 404, y
   * `null` mientras no se sabe. Sin la capa 3 no se ven «Pedido», «Agregar al pedido» ni «Pedir
   * estos productos».
   */
  capa3: boolean | null
  intencionPedido: IntencionPedido | null
  llegadaPedido: LlegadaPedido | null
  /** MATU-61 (12.1): «Ver la dirección de entrega» de Grupo familiar; la dirección vuelve allá. */
  direccionDesdeGrupo: boolean
  /** MATU-53 (2.1): la invitación que se está abriendo. */
  invitacion: InvitacionEnMemoria | null
  /**
   * MATU-54 (1): de qué persona es «Datos de…» (`/grupo/datos`). Lo fija «Ver los datos de…» en Grupo
   * familiar; la ruta no lleva el id. Al recargar no existe y la ruta vuelve a `/grupo`.
   */
  datosDe: string | null
  /**
   * MATU-54 (2 y 4): el `id` del botón que abrió una página, para devolverle el foco al volver. La
   * pantalla de destino lo enfoca cuando ya lo pintó, y lo vacía; mientras tanto, la regla de ruta no
   * lleva el foco al `h1`.
   */
  focoAlVolver: string | null
}
export type Autorizacion = 'sin-consentimiento' | 'revision-vencida' | null

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
  /** MATU-61: pregunta una vez si la capa 3 está encendida (`GET /v1/catalogo`). */
  conocerCapa3: () => void
  /**
   * Los formularios registran aquí lo que tienen sin guardar, con `registrarSinGuardar`: el editor de
   * la ficha (5.7) y, desde MATU-67, los de Insumos. Lo consultan el vencimiento de la entrada (que
   * muestra `texto`, si es de la ficha) y «Recargar» del aviso de versión nueva.
   */
  sinGuardar: React.RefObject<FuenteSinGuardar | null>
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
  autorizacion: null,
  celularDesde: 'cuenta',
  reautorizar: null,
  capa3: null,
  intencionPedido: null,
  llegadaPedido: null,
  direccionDesdeGrupo: false,
  invitacion: null,
  datosDe: null,
  focoAlVolver: null,
}

export function ProveedorFamilia({ children }: { children: ReactNode }) {
  const [s, setS] = useState<Estado>(INICIAL)
  const sinGuardar = useRef<FuenteSinGuardar | null>(null)

  const fijar = useCallback((cambios: Partial<Estado>) => setS((x) => ({ ...x, ...cambios })), [])

  /** Por la región viva amable de main.tsx, la misma de los avisos (compartido/ui/Anuncios). */
  const anunciar = useCallback((texto: string) => anunciarEnRegion(texto, 'status'), [])

  // MATU-61 (2.2): el catálogo dice si la capa 3 está encendida. Se pregunta una vez; un error que no
  // es 404 deja `null` y se vuelve a preguntar la próxima vez.
  const preguntando = useRef(false)
  const conocerCapa3 = useCallback(() => {
    if (preguntando.current) return
    preguntando.current = true
    verCatalogo()
      .then(() => setS((x) => ({ ...x, capa3: true })))
      .catch((e: unknown) => {
        if (leerFallo(e).status === 404) setS((x) => ({ ...x, capa3: false }))
      })
      .finally(() => {
        preguntando.current = false
      })
  }, [])

  /** Pide grupos y personas, y elige el primer grupo y la primera persona (2.3). */
  const alEntrar = useCallback(async () => {
    const grupos = await listarGrupos()
    const g = grupos[0] ?? null
    fijarGrupo(g?.id ?? null)
    const personas = g ? await listarPersonas(g.id) : []
    setS((x) => ({ ...x, fase: 'dentro', grupos, grupoId: g?.id ?? null, personas, personaId: personas[0]?.id ?? null, ficha: null, avisoEntrar: null, autorizacion: null }))
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
    // MATU-53 (2.1): si la entrada vence a mitad de una invitación, la invitación sigue en memoria. Al
    // salir a propósito (o desde otra pestaña) se olvida: el teléfono puede ser de otra persona.
    setS((x) => ({ ...INICIAL, fase: 'fuera', avisoEntrar: aviso, destino: x.destino, textoPerdido, invitacion: aviso === 'vencida' ? x.invitacion : null }))
  }, [])

  const salir = useCallback(async () => {
    await cerrarSesion()
    olvidar('salio')
    navegar('/entrar')
  }, [olvidar])

  const elegir = useCallback(async (grupoId: string, personaId: string | null) => {
    fijarGrupo(grupoId)
    const lista = await listarPersonas(grupoId)
    setS((x) => ({ ...x, grupoId, personas: lista, personaId: personaId ?? lista[0]?.id ?? null, ficha: null, autorizacion: null }))
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
        const texto = sinGuardar.current?.()?.texto ?? null
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
      conocerCapa3,
      sinGuardar,
    }
  }, [s, cargar, alEntrar, salir, elegir, fijar, anunciar, conocerCapa3])

  return (
    <Ctx.Provider value={valor}>
      {children}
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

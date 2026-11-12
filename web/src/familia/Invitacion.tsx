// La página de la persona invitada, `/invitacion#<token>` (MATU-42 y MATU-53, especificación
// docs/diseno/matu-53-invitar-grupo.md v1.1, secciones 2.1 y 4). Contrato: `POST /v1/invitaciones/
// presentacion`, `…/verificacion` (sin sesión) y `…/aceptacion` (con sesión), decisiones 298 a 301.
//
// - Es una ruta de la app de la familia, sin el `Shell`: así crear la cuenta o entrar son navegaciones
//   de la misma app y la invitación sigue en memoria (`invitacion` de estado.tsx).
// - El token viaja en el fragmento. Se lee al abrir y se limpia con `history.replaceState` al verificar
//   el código, al tocar «Crear mi cuenta» o «Entrar con mi cuenta», y al llegar a un estado que no
//   sigue (410, 423). Mientras se escribe el código queda, para que recargar la vuelva a abrir.
// - El token y el código viven solo en memoria: nunca en el almacenamiento del navegador, en
//   `history.state`, en la query, en el `<title>` ni en un registro.
// - Sin interfaz optimista: unirse espera la respuesta.
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { CalendarX2, CircleCheck, CloudOff, Hourglass, Link2, Link2Off, Lock, MailOpen, UserRound } from 'lucide-react'
import { isAxiosError } from 'axios'
import { esperaDe, leerFallo } from '../compartido/api/cliente'
import { aceptarInvitacion, leerCuenta, presentarInvitacion, verificarInvitacion, type PresentacionInvitacion } from '../compartido/api/familia'
import { esVencida } from '../compartido/api/sesion'
import { Boton } from '../compartido/ui/Boton'
import { EnlacePoliticaSolo } from '../compartido/ui/Enlaces'
import { DistintivoPiloto, Logo } from '../compartido/ui/Marca'
import { CampoCodigo } from './Codigo'
import { useDemora } from './Estados'
import { useFamilia, type InvitacionEnMemoria } from './estado'
import { esTipo } from './insumosComun'
import { FechaYHora, SoloFecha } from './PiezasInvitar'
import { navegar } from './ruteo'
import { AvisoVersionFamilia } from './Shell'
import { descripcionRol, INVITACION as T, teInvita } from './textosInvitar'
import { Acciones, Nota, Titulo } from './ui'

const RUTA = '/invitacion'

/** Quita el token de la barra de direcciones sin dejar una entrada con él en el historial (2.1). */
function limpiarFragmento() {
  if (window.location.hash) window.history.replaceState(null, '', RUTA)
}

/** El token del fragmento, tal cual. Un fragmento vacío no es un token. */
const tokenDelFragmento = () => {
  const t = window.location.hash.replace(/^#/, '').trim()
  return t || null
}

type Estado = 'vencida' | 'usada' | 'no-disponible' | 'bloqueada' | 'ya-eres-parte' | 'espera' | 'red' | 'sin-token'
type Paso =
  | { tipo: 'abriendo' }
  | { tipo: 'codigo' }
  | { tipo: 'cuenta' }
  | { tipo: 'confirmar' }
  | { tipo: 'no-unido'; expira: string | null }
  | { tipo: 'estado'; estado: Estado; nombre?: string | null; minutos?: number; grupoId?: string | null }

type Ultima = 'presentar' | 'verificar' | 'aceptar'

/** Un miembro de extensión del problema RFC 7807 (`nombre_pila_invita` del 423, `grupo_id` del 409). */
const extension = (x: unknown, campo: string): string | null => {
  if (!isAxiosError(x)) return null
  const v = (x.response?.data as Record<string, unknown> | undefined)?.[campo]
  return typeof v === 'string' && v.trim() ? v : null
}

const TITULO_ESTADO: Record<Estado, string> = {
  vencida: T.vencida.titulo,
  usada: T.usada.titulo,
  'no-disponible': T.noDisponible.titulo,
  bloqueada: T.bloqueada.titulo,
  'ya-eres-parte': T.yaEresParte,
  espera: T.espera.titulo,
  red: T.red.titulo,
  'sin-token': T.sinToken.titulo,
}

/** El paso al abrir: con el fragmento, la presentación; sin él, lo que haya en memoria (4.8). */
function pasoInicial(memoria: InvitacionEnMemoria | null, dentro: boolean, token: string | null): Paso {
  if (token) return memoria?.token === token && memoria.presentacion && !memoria.verificacion ? { tipo: 'codigo' } : { tipo: 'abriendo' }
  if (memoria?.verificacion && memoria.codigo) return dentro ? { tipo: 'confirmar' } : { tipo: 'cuenta' }
  return { tipo: 'estado', estado: 'sin-token' }
}

export function PaginaInvitacion() {
  const { invitacion, fase, fijar, alEntrar, elegir } = useFamilia()
  const dentro = fase === 'dentro'
  const [token] = useState(tokenDelFragmento)
  const [paso, setPaso] = useState<Paso>(() => pasoInicial(invitacion ?? null, dentro, token))
  // La invitación de esta página, también en la memoria de la app para volver desde el alta (2.1).
  const memoria = useRef<InvitacionEnMemoria | null>(invitacion ?? null)
  const guardar = useCallback(
    (m: InvitacionEnMemoria | null) => {
      memoria.current = m
      fijar({ invitacion: m })
    },
    [fijar],
  )
  const [codigo, setCodigo] = useState('')
  const [errorCodigo, setErrorCodigo] = useState<ReactNode>(null)
  const [ocupado, setOcupado] = useState(false)
  const ultima = useRef<Ultima>('presentar')
  const campo = useRef<HTMLInputElement>(null)
  // El foco tras validar el código: después del render que muestra el error (sin `setTimeout`).
  const [enfocarCampo, setEnfocarCampo] = useState(0)
  useEffect(() => {
    if (enfocarCampo) campo.current?.focus()
  }, [enfocarCampo])

  // 4.1: cada paso cambia el contenido de la misma página y el foco va a su `h1`.
  const claveDePaso = paso.tipo === 'estado' ? `estado-${paso.estado}` : paso.tipo
  useEffect(() => {
    document.getElementById('titulo-pagina')?.focus()
  }, [claveDePaso])

  // 2.1: el título de la pestaña nunca lleva nombres ni el token. En un estado que no sigue, el suyo.
  useEffect(() => {
    const titulo = paso.tipo === 'estado' ? TITULO_ESTADO[paso.estado] : paso.tipo === 'no-unido' ? T.noTeUniste : T.tituloPestana
    document.title = `${titulo} · MATU`
  }, [paso])

  /** Un estado que no sigue (410, 423, 409 `ya-eres-parte`): se olvida la invitación y el fragmento. */
  const terminar = useCallback(
    (p: Extract<Paso, { tipo: 'estado' }>) => {
      limpiarFragmento()
      guardar(null)
      setCodigo('')
      setPaso(p)
    },
    [guardar],
  )

  /** 4.7: lo que no es del código. `false` si no lo reconoce (lo atiende quien llama). */
  const manejar = useCallback(
    (x: unknown, desde: Ultima) => {
      ultima.current = desde
      const f = leerFallo(x)
      if (f.status === 410)
        return terminar({ tipo: 'estado', estado: esTipo(f.tipo, 'invitacion-vencida') ? 'vencida' : esTipo(f.tipo, 'invitacion-usada') ? 'usada' : 'no-disponible' })
      if (f.status === 423)
        return terminar({ tipo: 'estado', estado: 'bloqueada', nombre: extension(x, 'nombre_pila_invita') ?? memoria.current?.presentacion?.nombre_pila_invita ?? null })
      if (f.status === 409 && esTipo(f.tipo, 'ya-eres-parte')) return terminar({ tipo: 'estado', estado: 'ya-eres-parte', grupoId: extension(x, 'grupo_id') })
      const espera = esperaDe(f)
      if (espera) return setPaso({ tipo: 'estado', estado: 'espera', minutos: espera.minutos })
      // Un token mal formado (422 en la presentación) es una invitación que no existe (C28).
      if (f.status === 422 && desde === 'presentar') return terminar({ tipo: 'estado', estado: 'no-disponible' })
      setPaso({ tipo: 'estado', estado: 'red' })
    },
    [terminar],
  )

  const presentar = useCallback(async () => {
    const t = memoria.current?.token ?? token
    if (!t) return
    setPaso({ tipo: 'abriendo' })
    try {
      const p = await presentarInvitacion(t)
      guardar({ token: t, presentacion: p, codigo: null, verificacion: null })
      setPaso({ tipo: 'codigo' })
    } catch (x) {
      manejar(x, 'presentar')
    }
  }, [token, guardar, manejar])

  // Al abrir con el fragmento: la invitación pasa a memoria y se pide la presentación.
  useEffect(() => {
    if (!token) return
    if (memoria.current?.token === token && memoria.current.presentacion && !memoria.current.verificacion) return
    guardar({ token, presentacion: null, codigo: null, verificacion: null })
    void presentar()
    // Solo al abrir.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Si la sesión venció a mitad de la confirmación, falta entrar otra vez (2.1).
  useEffect(() => {
    if (paso.tipo === 'confirmar' && !dentro) setPaso({ tipo: 'cuenta' })
  }, [paso.tipo, dentro])

  /** 4.3: un error del código, bajo el campo, con el foco en el campo. */
  const errorDelCodigo = (texto: ReactNode) => {
    setErrorCodigo(texto)
    setEnfocarCampo((n) => n + 1)
  }

  const verificar = async () => {
    const m = memoria.current
    if (ocupado || !m) return
    setErrorCodigo(null)
    if (codigo.length !== 4) return errorDelCodigo(T.codigoCorto)
    setOcupado(true)
    try {
      const v = await verificarInvitacion(m.token, codigo)
      limpiarFragmento()
      guardar({ ...m, codigo, verificacion: v })
      setPaso(dentro ? { tipo: 'confirmar' } : { tipo: 'cuenta' })
    } catch (x) {
      const f = leerFallo(x)
      if (f.status === 422 && esTipo(f.tipo, 'codigo-incorrecto')) {
        setCodigo('')
        setPaso({ tipo: 'codigo' })
        return errorDelCodigo(<CodigoMalo intentos={f.intentosRestantes} />)
      }
      if (f.status === 422 && f.campos.includes('codigo')) {
        setPaso({ tipo: 'codigo' })
        return errorDelCodigo(T.codigoCorto)
      }
      manejar(x, 'verificar')
    } finally {
      setOcupado(false)
    }
  }

  const aceptar = async () => {
    const m = memoria.current
    if (ocupado || !m?.codigo) return
    setOcupado(true)
    try {
      const u = await aceptarInvitacion(m.token, m.codigo)
      guardar(null)
      // 4.6: la app vuelve a pedir los grupos, elige el nuevo y lleva a su inicio, con el aviso.
      await alEntrar()
      await elegir(u.grupo_id, null)
      fijar({ aviso: { titulo: T.yaEresParteDe(u.grupo), tono: 'ok', enfocar: true } })
      navegar('/', { reemplazar: true })
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 422 && esTipo(f.tipo, 'codigo-incorrecto')) {
        // El código ya no sirve (otra persona lo probó mientras tanto): vuelve a pedirlo.
        guardar({ ...m, codigo: null, verificacion: null })
        setCodigo('')
        setPaso({ tipo: 'codigo' })
        return errorDelCodigo(<CodigoMalo intentos={f.intentosRestantes} />)
      }
      manejar(x, 'aceptar')
    } finally {
      setOcupado(false)
    }
  }

  /** 4.7: «Volver a intentar» repite la última petición; el código escrito sigue en memoria. */
  const reintentar = () => {
    if (ultima.current === 'presentar') return void presentar()
    if (ultima.current === 'aceptar') return void aceptar()
    void verificar()
  }

  const p = memoria.current?.presentacion ?? null
  const v = memoria.current?.verificacion ?? null
  let cuerpo: ReactNode
  if (paso.tipo === 'abriendo') cuerpo = <Abriendo />
  else if (paso.tipo === 'codigo' && p)
    cuerpo = (
      <PasoCodigo
        p={p}
        codigo={codigo}
        onCodigo={(c) => {
          setCodigo(c)
          if (errorCodigo) setErrorCodigo(null)
        }}
        error={errorCodigo}
        ocupado={ocupado}
        campo={campo}
        onSeguir={() => void verificar()}
      />
    )
  else if (paso.tipo === 'cuenta' && p)
    cuerpo = (
      <PasoCuenta
        onCrear={() => {
          limpiarFragmento()
          navegar('/crear-cuenta')
        }}
        onEntrar={() => {
          limpiarFragmento()
          fijar({ destino: RUTA })
          navegar('/entrar')
        }}
      />
    )
  else if (paso.tipo === 'confirmar' && v)
    cuerpo = (
      <PasoConfirmar
        v={v}
        ocupado={ocupado}
        onUnirme={() => void aceptar()}
        onNoQuiero={() => {
          // P12: no llama al servidor. La invitación sigue hasta que vence o se anula.
          const expira = v.expira_en
          guardar(null)
          setPaso({ tipo: 'no-unido', expira })
        }}
      />
    )
  else if (paso.tipo === 'no-unido') cuerpo = <NoUnido expira={paso.expira} dentro={dentro} />
  else if (paso.tipo === 'estado')
    cuerpo = (
      <PantallaEstado
        paso={paso}
        ocupado={ocupado}
        onReintentar={reintentar}
        onIrAMatu={async () => {
          if (paso.grupoId) await elegir(paso.grupoId, null).catch(() => {})
          navegar('/', { reemplazar: true })
        }}
      />
    )
  else cuerpo = <PantallaEstado paso={{ tipo: 'estado', estado: 'sin-token' }} ocupado={false} onReintentar={reintentar} onIrAMatu={() => navegar('/')} />

  return (
    <MarcoInvitacion ocupado={paso.tipo === 'abriendo' || ocupado}>
      <div className="mx-auto flex max-w-xl flex-col gap-6">{cuerpo}</div>
    </MarcoInvitacion>
  )
}

/** 2.1: el marco público, con la forma del de `relevo/Marco.tsx`: sin navegación ni selector de persona. */
function MarcoInvitacion({ ocupado, children }: { ocupado: boolean; children: ReactNode }) {
  return (
    <>
      <header className="border-b border-linea bg-hoja">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 angosto:px-2 @3xl/app:px-10 py-3">
          <span className="flex items-center gap-2.5">
            <Logo className="size-8" />
            <span className="titular text-xl">MATU</span>
          </span>
          <span className="text-tenue">{T.rotulo}</span>
          <DistintivoPiloto className="ms-auto" />
        </div>
      </header>
      <main id="contenido" tabIndex={-1} aria-busy={ocupado || undefined} className="@container/main flex-1 px-4 angosto:px-2 @3xl/app:px-10 pt-6 @3xl/app:pt-14 pb-16 outline-none">
        <AvisoVersionFamilia className="mx-auto mb-6 max-w-xl" />
        {children}
      </main>
    </>
  )
}

function Abriendo() {
  const ver = useDemora()
  return (
    <p role="status" className="text-lg text-tenue">
      {ver ? T.abriendo : ''}
    </p>
  )
}

const TONO_BALDOSA = {
  rocio: 'bg-rocio text-turquesa',
  neutro: 'bg-tinta/7 text-tenue',
  atenta: 'bg-atenta-fondo text-atenta',
  pronto: 'bg-pronto-fondo text-pronto',
  ok: 'bg-ok-fondo text-ok',
} as const

/** La baldosa del momento: decorativa, el título dice lo mismo (nunca solo color). */
function Baldosa({ icono: Icono, tono }: { icono: typeof MailOpen; tono: keyof typeof TONO_BALDOSA }) {
  return (
    <span aria-hidden className={`grid size-14 @md/main:size-18 shrink-0 place-items-center rounded-2xl ${TONO_BALDOSA[tono]}`}>
      <Icono className="size-8 @md/main:size-10" />
    </span>
  )
}

// 7 (v1.2): con `hyphens-auto` un nombre largo se parte por sílabas, no a mitad de cualquier letra.
const TITULO = 'text-3xl @2xl/main:text-4xl break-words hyphens-auto'

/** «Ese código no es. Te quedan {n} intentos. Después, la invitación se bloquea.», la primera oración en negrita. */
function CodigoMalo({ intentos }: { intentos: number | null }) {
  return (
    <>
      <b>{T.noEs}</b>
      {intentos !== null && intentos > 0 ? T.quedan(intentos) : ''}
    </>
  )
}

// ---------------------------------------------------------------- 4.2 y 4.3

function PasoCodigo({
  p,
  codigo,
  onCodigo,
  error,
  ocupado,
  campo,
  onSeguir,
}: {
  p: PresentacionInvitacion
  codigo: string
  onCodigo: (c: string) => void
  error: ReactNode
  ocupado: boolean
  campo: React.RefObject<HTMLInputElement | null>
  onSeguir: () => void
}) {
  return (
    <>
      <Baldosa icono={MailOpen} tono="rocio" />
      {/* C1: antes del código, solo el nombre de pila de quien invita, el rol y el vencimiento. */}
      <Titulo className={TITULO}>{teInvita(p.nombre_pila_invita, p.rol)}</Titulo>
      <form
        noValidate
        className="flex flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault()
          onSeguir()
        }}
      >
        <p className="text-base">{T.escribeElCodigo}</p>
        <CampoCodigo ref={campo} etiqueta={T.codigo} largo={4} valor={codigo} onCambio={onCodigo} error={error} disabled={ocupado} />
        <Acciones>
          <Boton type="submit" ocupado={ocupado} textoOcupado={T.revisando}>
            {T.seguir}
          </Boton>
        </Acciones>
      </form>
      <p className="text-base text-tenue">
        <FechaYHora iso={p.expira_en} partes={T.valeHasta} />
      </p>
    </>
  )
}

// ---------------------------------------------------------------- 4.4

function PasoCuenta({ onCrear, onEntrar }: { onCrear: () => void; onEntrar: () => void }) {
  return (
    <>
      <Titulo className={TITULO}>{T.cuentaTitulo}</Titulo>
      <p className="text-base text-tenue">{T.cuentaTexto}</p>
      <Acciones>
        <Boton onClick={onCrear}>{T.crearCuenta}</Boton>
        <Boton variante="secundario" onClick={onEntrar}>
          {T.entrar}
        </Boton>
      </Acciones>
    </>
  )
}

/** 4.4: arriba del formulario de crear cuenta o entrar, con una invitación en memoria. */
export function NotaVuelvesALaInvitacion() {
  const { invitacion } = useFamilia()
  const nombre = invitacion?.verificacion?.nombre_pila_invita ?? invitacion?.presentacion?.nombre_pila_invita
  if (!invitacion?.verificacion || !nombre) return null
  return (
    <Nota tono="rocio" icono={<MailOpen aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
      {T.vuelves(nombre)}
    </Nota>
  )
}

// ---------------------------------------------------------------- 4.5

function PasoConfirmar({
  v,
  ocupado,
  onUnirme,
  onNoQuiero,
}: {
  v: NonNullable<InvitacionEnMemoria['verificacion']>
  ocupado: boolean
  onUnirme: () => void
  onNoQuiero: () => void
}) {
  const { capa3, conocerCapa3 } = useFamilia()
  const [yo, setYo] = useState<string | null>(null)
  // 5 (v1.2): «Paga» se describe igual que en /grupo/invitar: con los pedidos solo con la capa 3.
  useEffect(() => {
    if (capa3 === null) conocerCapa3?.()
  }, [capa3, conocerCapa3])
  // «Te unes como {tu nombre}.» sirve en un teléfono compartido. Si no se puede pedir, no aparece.
  useEffect(() => {
    let vivo = true
    leerCuenta()
      .then((c) => vivo && setYo(c.nombre))
      .catch(() => {})
    return () => {
      vivo = false
    }
  }, [])
  return (
    <>
      <Titulo className={TITULO}>{T.teUnes(v.grupo, v.personas)}</Titulo>
      <div className="flex flex-col gap-1">
        <p className="text-lg font-bold">{T.tuRol(v.rol)}</p>
        <p className="text-base">{descripcionRol(v.rol, { capa3: capa3 === true, pilas: v.personas })}</p>
      </div>
      <div className="flex flex-col gap-3">
        <Nota tono="rocio" icono={<UserRound aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
          {T.verasNombre}
        </Nota>
        <Nota tono="rocio" icono={<Lock aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
          {T.confidencial(v.personas)}
        </Nota>
      </div>
      <EnlacePoliticaSolo />
      {yo && <p className="text-base text-tenue break-words">{T.teUnesComo(yo)}</p>}
      <Acciones>
        <Boton ocupado={ocupado} textoOcupado={T.uniendo} onClick={onUnirme}>
          {T.unirme}
        </Boton>
        <Boton variante="texto" aria-disabled={ocupado || undefined} onClick={() => !ocupado && onNoQuiero()}>
          {T.noQuiero}
        </Boton>
      </Acciones>
    </>
  )
}

function NoUnido({ expira, dentro }: { expira: string | null; dentro: boolean }) {
  return (
    <>
      <Titulo className={TITULO}>{T.noTeUniste}</Titulo>
      {expira && (
        <p className="text-base">
          {T.siCambias} <SoloFecha iso={expira} />
        </p>
      )}
      {dentro && (
        <Acciones>
          <Boton variante="secundario" onClick={() => navegar('/')}>
            {T.irAMatu}
          </Boton>
        </Acciones>
      )}
    </>
  )
}

// ---------------------------------------------------------------- 4.7 y 4.8

function PantallaEstado({
  paso,
  ocupado,
  onReintentar,
  onIrAMatu,
}: {
  paso: Extract<Paso, { tipo: 'estado' }>
  ocupado: boolean
  onReintentar: () => void
  onIrAMatu: () => void
}) {
  const d: { icono: typeof MailOpen; tono: keyof typeof TONO_BALDOSA; texto?: string; queHago?: string; boton?: ReactNode } = (() => {
    switch (paso.estado) {
      case 'vencida':
        return { icono: CalendarX2, tono: 'atenta', texto: T.vencida.texto, queHago: T.pideOtra }
      case 'usada':
        return { icono: CircleCheck, tono: 'neutro', texto: T.usada.texto, queHago: T.pideOtra }
      case 'no-disponible':
        return { icono: Link2Off, tono: 'neutro', texto: T.noDisponible.texto, queHago: T.pideOtra }
      case 'bloqueada':
        return { icono: Lock, tono: 'pronto', texto: T.bloqueada.texto, queHago: paso.nombre ? T.pideleA(paso.nombre) : T.pideOtra }
      case 'ya-eres-parte':
        return {
          icono: CircleCheck,
          tono: 'ok',
          boton: (
            <Boton variante="secundario" onClick={onIrAMatu}>
              {T.irAMatu}
            </Boton>
          ),
        }
      case 'espera':
        return { icono: Hourglass, tono: 'atenta', texto: T.espera.texto(paso.minutos ?? 1) }
      case 'red':
        return {
          icono: CloudOff,
          tono: 'atenta',
          texto: T.red.texto,
          boton: (
            <Boton ocupado={ocupado} onClick={onReintentar}>
              {T.volverAIntentar}
            </Boton>
          ),
        }
      default:
        return { icono: Link2, tono: 'rocio', texto: T.sinToken.texto }
    }
  })()
  return (
    <>
      <Baldosa icono={d.icono} tono={d.tono} />
      <div className="flex flex-col gap-2">
        <Titulo className={TITULO}>{TITULO_ESTADO[paso.estado]}</Titulo>
        {d.texto && <p className="text-lg text-tenue">{d.texto}</p>}
      </div>
      {d.queHago && (
        <div className="rounded-xl bg-rocio px-4 angosto:px-2 py-3">
          <p className="font-bold">{T.queHago}</p>
          <p className="text-base font-bold">{d.queHago}</p>
        </div>
      )}
      {d.boton && <Acciones>{d.boton}</Acciones>}
    </>
  )
}

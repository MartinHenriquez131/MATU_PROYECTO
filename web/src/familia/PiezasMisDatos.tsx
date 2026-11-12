// Piezas comunes de «Datos de {nombre}» y «Tus datos» (MATU-54, especificación
// docs/diseno/matu-54-mis-datos.md v1.1): pedir la copia una sola vez, sus estados, el panel de
// descarga con «Antes de descargar», los bloques, el índice, los 90 días y «Ver más», y las líneas del
// historial. El texto de la respuesta vive solo en la memoria de la página que lo pidió.
import { Fragment, useCallback, useEffect, useId, useRef, useState, type ReactNode, type Ref } from 'react'
import {
  BadgeCheck,
  Bell,
  BellOff,
  CircleCheck,
  CirclePause,
  CirclePlay,
  CircleX,
  ClipboardCheck,
  Clock,
  CreditCard,
  Download,
  Eraser,
  Eye,
  Lock,
  MapPin,
  Package,
  PackageMinus,
  PackagePlus,
  PencilLine,
  Replace,
  Share2,
  ShieldCheck,
  ShieldOff,
  ShoppingBag,
  ShoppingCart,
  Trash2,
  Undo2,
  Unlink,
  WifiOff,
  type LucideIcon,
} from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { guardarArchivo, type Copia, type HechoCopia, type PersonaNombrada, type TipoHecho } from '../compartido/api/misDatos'
import { esVencida } from '../compartido/api/sesion'
import { diaRelativoDeChile, fechaCorta, fechaYHoraDeChile } from '../compartido/fechas'
import { POLITICA } from '../compartido/textosPolitica'
import { Boton } from '../compartido/ui/Boton'
import { EnlaceEnFrase } from '../compartido/ui/Enlaces'
import { IndiceAncho, IndiceDesplegable, type EntradaIndice } from '../compartido/ui/Indice'
import { TITULO_SECCION } from '../compartido/secciones'
import { CAMPOS } from './datos'
import { DialogoConfirmar } from './DialogoConfirmar'
import { useDemora } from './Estados'
import { useFamilia } from './estado'
import { GENERAL, QUIEN } from './textos'
import { FRASE_HECHO, MIS_DATOS as T } from './textosMisDatos'
import { Nota } from './ui'

// ---------------------------------------------------------------- pedir la copia

export type EstadoCopia<D> =
  | { estado: 'cargando' }
  | { estado: 'lista'; copia: Copia<D> }
  /** Sin red, 5xx, una respuesta que no se puede leer y, en «Tus datos», un 404 (5.6). */
  | { estado: 'error' }
  /** 503 `servicio-no-disponible`: no es la conexión de la persona. */
  | { estado: 'no-disponible' }
  /** 429 `tope-copias`, con la hora en que se puede volver a pedir, o `null` sin `Retry-After`. */
  | { estado: 'tope'; hora: string | null }
  /** 404 de «Datos de…»: la persona ya no es accesible para esta cuenta. */
  | { estado: 'no-encontrado' }

/** La hora de `Retry-After` sumada a la de la respuesta, hacia arriba al minuto: antes, daría otro 429. */
export function horaDeReintento(segundos: number, ahora = Date.now()): string {
  const listo = Math.ceil((ahora + segundos * 1000) / 60_000) * 60_000
  return fechaYHoraDeChile(new Date(listo)).hora
}

function estadoDeFallo<D>(x: unknown, con404: boolean): EstadoCopia<D> | null {
  // 401: la entrada venció y la app ya lleva a entrar. La página no dice nada más.
  if (esVencida(x)) return null
  const f = leerFallo(x)
  if (f.status === 429) return { estado: 'tope', hora: f.reintentarEnSegundos ? horaDeReintento(f.reintentarEnSegundos) : null }
  if (f.status === 503) return { estado: 'no-disponible' }
  if (f.status === 404 && con404) return { estado: 'no-encontrado' }
  return { estado: 'error' }
}

/**
 * Abrir la página es pedir una copia (P1): una sola petición por visita. En desarrollo, `StrictMode`
 * monta los efectos dos veces; la petición que ya salió se reutiliza y no se pide (ni se cuenta en el
 * límite) una segunda copia. Volver a la página es otra visita: otra copia.
 */
export function useCopia<D>(pedir: () => Promise<Copia<D>>, con404: boolean) {
  const [estado, setEstado] = useState<EstadoCopia<D>>({ estado: 'cargando' })
  const pedirRef = useRef(pedir)
  const enCurso = useRef<Promise<EstadoCopia<D> | null> | null>(null)
  const vivo = useRef(true)

  const lanzar = useCallback(() => {
    const p = pedirRef.current().then(
      (copia): EstadoCopia<D> => ({ estado: 'lista', copia }),
      (x: unknown) => estadoDeFallo<D>(x, con404),
    )
    enCurso.current = p
    return p
  }, [con404])

  useEffect(() => {
    vivo.current = true
    const p = enCurso.current ?? lanzar()
    void p.then((r) => {
      if (vivo.current && r && enCurso.current === p) setEstado(r)
    })
    return () => {
      vivo.current = false
    }
  }, [lanzar])

  const reintentar = useCallback(() => {
    setEstado({ estado: 'cargando' })
    const p = lanzar()
    void p.then((r) => {
      if (vivo.current && r && enCurso.current === p) setEstado(r)
    })
  }, [lanzar])

  return { estado, reintentar }
}

// ---------------------------------------------------------------- estados de la página (3.6)

export const ID_AVISO_COPIA = 'aviso-copia'

export function Cargando() {
  const ver = useDemora()
  return (
    <p role="status" className="text-tenue">
      {ver ? GENERAL.cargando : ''}
    </p>
  )
}

/**
 * El error, el 503, el 429 (sin «Volver a intentar», que daría otro 429) y el 404. La nota recibe el
 * foco al aparecer, en un efecto, cuando ya está pintada.
 */
export function AvisoDeCarga({ e, reintentar }: { e: EstadoCopia<unknown>; reintentar: () => void }) {
  useEffect(() => {
    document.getElementById(ID_AVISO_COPIA)?.focus()
  }, [])
  if (e.estado === 'tope')
    return (
      <Nota id={ID_AVISO_COPIA} tono="atenta" rol="alert" enfocable icono={<Clock aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
        {e.hora ? (
          <>
            {T.tope[0]}
            <span className="cifras">
              {e.hora}
              {T.tope[1]}
            </span>
          </>
        ) : (
          T.topeSinHora
        )}
      </Nota>
    )
  if (e.estado === 'no-encontrado')
    return (
      <Nota id={ID_AVISO_COPIA} tono="rocio" enfocable icono={<Lock aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
        {GENERAL.noEncontrado}
      </Nota>
    )
  return (
    <div className="flex max-w-prose flex-col items-start gap-4">
      <Nota id={ID_AVISO_COPIA} tono="pronto" rol="alert" enfocable icono={<WifiOff aria-hidden className="mt-0.5 size-5 shrink-0 text-pronto" />}>
        {e.estado === 'no-disponible' ? T.errNoDisponible : T.errCarga}
      </Nota>
      <Boton variante="secundario" onClick={reintentar}>
        {GENERAL.volverAIntentar}
      </Boton>
    </div>
  )
}

// ---------------------------------------------------------------- fechas

const valido = (iso: string | null | undefined): iso is string => !!iso && !Number.isNaN(new Date(iso).getTime())

/**
 * «12/11/2026 a las 10:14», en dos `cifras` dentro de un `<time>`. `fin` va pegado a la hora, en su
 * `cifras`: en modo angosto el punto no baja solo a un renglón.
 */
export function FechaHora({ iso, fin = '' }: { iso: string | null | undefined; fin?: string }) {
  if (!valido(iso)) return null
  const { fecha, hora } = fechaYHoraDeChile(new Date(iso))
  return (
    <time dateTime={iso}>
      <span className="cifras">{fecha}</span> {T.aLas}{' '}
      <span className="cifras">
        {hora}
        {fin}
      </span>
    </time>
  )
}

/** Solo el día de un instante: «02/11/2026». */
export function DiaDeInstante({ iso, fin = '' }: { iso: string | null | undefined; fin?: string }) {
  if (!valido(iso)) return null
  return (
    <time dateTime={iso} className="cifras">
      {fechaYHoraDeChile(new Date(iso)).fecha}
      {fin}
    </time>
  )
}

/** Un `Dia` del contrato (`AAAA-MM-DD`): «02/11/2026», sin pasar por la zona horaria. */
export function Dia({ dia, fin = '' }: { dia: string | null | undefined; fin?: string }) {
  if (!dia) return null
  return (
    <time dateTime={dia} className="cifras">
      {fechaCorta(dia)}
      {fin}
    </time>
  )
}

/** Una frase con una fecha y hora en medio: `[antes, después]`. El después va pegado a la hora. */
export function ConFechaHora({ partes: [antes, despues], iso }: { partes: readonly [string, string]; iso: string | null | undefined }) {
  return (
    <>
      {antes}
      <FechaHora iso={iso} fin={despues} />
    </>
  )
}

export function ConDia({ partes: [antes, despues], dia }: { partes: readonly [string, string]; dia: string | null | undefined }) {
  return (
    <>
      {antes}
      <Dia dia={dia} fin={despues} />
    </>
  )
}

/** Quien salió del grupo (MATU-53 5.7): con el mismo peso del nombre al que reemplaza. */
export const nombreDe = (p: PersonaNombrada | null | undefined, mayuscula = false) => p?.nombre ?? (mayuscula ? T.yaNoEstaMayuscula : T.yaNoEsta)

// ---------------------------------------------------------------- 90 días (3.4.9 y 3.4.10)

const NOVENTA_DIAS_MS = 90 * 24 * 60 * 60 * 1000

/**
 * Lo de los últimos 90 días contados desde que se generó la copia, en el orden del servidor, y si la
 * respuesta trae algo anterior (Q18). Lo anterior no se muestra (D-54-9): va en el archivo.
 */
export function enNoventaDias<I>(items: I[], instante: (i: I) => string | null | undefined, generadoEn: string): { dentro: I[]; hayAnterior: boolean } {
  const corte = new Date(generadoEn).getTime() - NOVENTA_DIAS_MS
  const dentro: I[] = []
  let hayAnterior = false
  for (const i of items) {
    const iso = instante(i)
    if (!valido(iso)) continue
    if (new Date(iso).getTime() >= corte) dentro.push(i)
    else hayAnterior = true
  }
  return { dentro, hayAnterior }
}

export function FraseNoventa({ hayAnterior }: { hayAnterior: boolean }) {
  return <p className="max-w-prose text-base text-tenue">{hayAnterior ? T.noventaConMas : T.noventaSinMas}</p>
}

/**
 * «Ver más» (3.4.10): muestra `paso` más desde la misma respuesta, sin pedir nada. El foco va a la
 * primera línea nueva después de pintarse, y se anuncia cuántas se agregaron.
 */
export function useVerMas(total: number, paso: number) {
  const { anunciar } = useFamilia()
  const [visibles, setVisibles] = useState(Math.min(paso, total))
  const [nueva, setNueva] = useState<number | null>(null)
  const enfocar = useRef(false)
  const nodo = useRef<HTMLLIElement | null>(null)
  // La primera línea nueva toma el foco cuando React la inserta (su ref), y el efecto queda de
  // respaldo si ya estaba. Sin `setTimeout`: en las pruebas, solo con el efecto el foco a veces se
  // quedaba en «Ver más» (la ref aún no apuntaba a la línea cuando el efecto corría).
  const alInsertar = useCallback((li: HTMLLIElement | null) => {
    nodo.current = li
    if (li && enfocar.current) {
      enfocar.current = false
      li.focus()
    }
  }, [])
  useEffect(() => {
    if (!enfocar.current || !nodo.current) return
    enfocar.current = false
    nodo.current.focus()
  }, [visibles])
  const mas = () => {
    const n = Math.min(paso, total - visibles)
    if (n <= 0) return
    enfocar.current = true
    setNueva(visibles)
    setVisibles(visibles + n)
    anunciar(QUIEN.seAgregaron(n))
  }
  const foco = (i: number): Ref<HTMLLIElement> | undefined => (i === nueva ? alInsertar : undefined)
  return { visibles: Math.min(visibles, total), hayMas: visibles < total, mas, foco }
}

export function BotonVerMas({ onClick }: { onClick: () => void }) {
  return (
    <Boton variante="secundario" className="self-start" onClick={onClick}>
      {T.verMas}
    </Boton>
  )
}

/** Las líneas agrupadas por día de Chile, con un `h3` por día: «Hoy», «Ayer», «El sábado», «El 24/10/2026». */
export function PorDia<I>({ items, instante, linea }: { items: I[]; instante: (i: I) => string; linea: (i: I, indice: number) => ReactNode }) {
  const ahora = new Date()
  const grupos: { dia: string; desde: number; lineas: I[] }[] = []
  items.forEach((it, i) => {
    const dia = diaRelativoDeChile(new Date(instante(it)), ahora)
    const ultimo = grupos[grupos.length - 1]
    if (ultimo && ultimo.dia === dia) ultimo.lineas.push(it)
    else grupos.push({ dia, desde: i, lineas: [it] })
  })
  return (
    <div className="flex max-w-prose flex-col">
      {grupos.map((g, n) => (
        <Fragment key={`${g.dia}-${g.desde}`}>
          <h3 className={`text-lg font-bold ${n ? 'mt-6' : ''}`}>{g.dia}</h3>
          <ol className="flex flex-col">{g.lineas.map((it, j) => linea(it, g.desde + j))}</ol>
        </Fragment>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------- 3.4.9 la línea del historial

const ICONO_HECHO: Record<TipoHecho, LucideIcon> = {
  abrio_la_ficha: Eye,
  edito_la_ficha: PencilLine,
  quito_una_seccion: Eraser,
  ficha_borrada: Trash2,
  dio_una_autorizacion: ShieldCheck,
  retiro_una_autorizacion: ShieldOff,
  compartio_la_ficha: Share2,
  corto_un_enlace: Unlink,
  agrego_un_insumo: PackagePlus,
  edito_un_insumo: Package,
  dejo_de_seguir_un_insumo: CirclePause,
  volvio_a_seguir_un_insumo: CirclePlay,
  quito_un_insumo: PackageMinus,
  anoto_una_compra: ShoppingBag,
  aviso_de_insumo: Bell,
  descarto_un_aviso: BellOff,
  resolvio_un_aviso: CircleCheck,
  cambio_la_direccion: MapPin,
  creo_un_pedido: ShoppingCart,
  confirmo_un_pedido: ClipboardCheck,
  cancelo_un_pedido: CircleX,
  cambio_que_hacer_si_falta: Replace,
  inicio_un_pago: CreditCard,
  pago_aprobado: BadgeCheck,
  pago_anulado: Undo2,
  pidio_una_copia: Download,
}

/** Un `tipo` que el cliente no conoce no se muestra, y la pantalla no se rompe. */
export const seMuestraHecho = (h: HechoCopia): h is HechoCopia & { tipo: TipoHecho } => Object.hasOwn(FRASE_HECHO, h.tipo) && valido(h.ocurrido_en)

/** El nombre de L 14.1 del campo o de la sección de un hecho de la ficha, o `null`. */
function objetoDe(h: HechoCopia): string | null {
  if (h.campo) return CAMPOS.find((c) => c.api === h.campo)?.titulo ?? null
  if (h.seccion) return TITULO_SECCION[h.seccion] ?? null
  return null
}

/** `LineaHistorial`: el molde de `LineaIngreso` (MATU-55, 2.5), con la cola «a las {HH:MM} · {nombre}». */
export function LineaHistorial({ h, foco }: { h: HechoCopia & { tipo: TipoHecho }; foco?: Ref<HTMLLIElement> }) {
  const Icono = ICONO_HECHO[h.tipo]
  const { fecha, hora } = fechaYHoraDeChile(new Date(h.ocurrido_en))
  // MATU no lleva nombre: la frase ya dice quién. Quien salió del grupo, «alguien que ya no está…».
  const cola = h.quien.tipo === 'matu' ? '' : ` · ${h.quien.nombre ?? T.yaNoEsta}`
  return (
    <li ref={foco} tabIndex={foco ? -1 : undefined} className="flex items-start gap-3 border-b border-linea py-3 outline-none last:border-0 angosto:flex-col angosto:gap-2">
      <span aria-hidden className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-rocio text-turquesa">
        <Icono className="size-5" />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="font-bold leading-snug break-words">{FRASE_HECHO[h.tipo](objetoDe(h))}</span>
        <span className="text-base text-tenue tabular-nums break-words">
          {T.aLas}{' '}
          <time dateTime={h.ocurrido_en} title={`${fecha} ${hora}`} className="cifras">
            {hora}
          </time>
          {cola}
        </span>
      </span>
    </li>
  )
}

// ---------------------------------------------------------------- bloques e índice

/** Las superficies de los bloques (3.4): `hoja` con anillo, filas separadas por `linea`. */
export const SUPERFICIE = 'flex min-w-0 flex-col divide-y divide-linea rounded-xl bg-hoja px-4 angosto:px-2 ring-1 ring-linea'

/** Un bloque con su `h2`. El `h2` recibe el foco desde el índice; la URL no cambia (C26). */
export function Bloque({ id, titulo, children }: { id: string; titulo: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-t`} className="flex min-w-0 scroll-mt-6 flex-col gap-3">
      <h2 id={`${id}-t`} tabIndex={-1} className="text-xl font-bold leading-snug break-words outline-none">
        {titulo}
      </h2>
      {children}
    </section>
  )
}

/** Un bloque sin filas: una frase, sin ícono ni botón (3.6). */
export function Vacio({ children }: { children: ReactNode }) {
  return <p className="max-w-prose text-base text-tenue">{children}</p>
}

const irA = (id: string) => document.getElementById(`${id}-t`)?.focus()

/** El índice de /privacidad (P11) y los bloques, con la grilla de MATU-75 en pantalla ancha (3.3). */
export function CuerpoConIndice({ entradas, children }: { entradas: EntradaIndice[]; children: ReactNode }) {
  return (
    <>
      <IndiceDesplegable titulo={POLITICA.indice} entradas={entradas} alElegir={irA} id="indice-datos" className="mt-8" />
      <div className="mt-8 grid grid-cols-1 gap-10 @4xl/main:grid-cols-[var(--container-xs)_minmax(0,1fr)] @4xl/main:gap-16">
        <IndiceAncho titulo={POLITICA.indice} entradas={entradas} alElegir={irA} idTitulo="indice-datos-ancho-t" />
        <div className="flex min-w-0 flex-col gap-10">{children}</div>
      </div>
    </>
  )
}

/** «… escribe a {correo} …»: el correo de la política en `EnlaceEnFrase`. Sin correo, `sinCorreo`. */
export function FraseConCorreo({ partes: [antes, despues], correo, sinCorreo = null }: { partes: readonly [string, string]; correo: string | null; sinCorreo?: ReactNode }) {
  if (!correo) return <>{sinCorreo}</>
  return (
    <>
      {antes}
      <EnlaceEnFrase href={`mailto:${correo}`} className="[overflow-wrap:anywhere]">
        {correo}
      </EnlaceEnFrase>
      {despues}
    </>
  )
}

// ---------------------------------------------------------------- 3.7 el panel de descarga

/**
 * El panel: qué es el archivo, los 90 días y el único macizo de la página. «Descargar en un archivo»
 * siempre abre «Antes de descargar» (C11), y «Descargar» guarda los mismos caracteres que llegaron, sin
 * volver a la API. «Te entregamos el archivo» y no «Descargaste»: el navegador no confirma que se guardó.
 */
export function PanelDescarga({ copia, texto, destacado }: { copia: Copia<unknown>; texto: string; destacado?: string }) {
  const uid = useId()
  const [abierto, setAbierto] = useState(false)
  const [entregado, setEntregado] = useState(false)
  const boton = useRef<HTMLButtonElement>(null)
  const nota = `${uid}-ok`
  const devolver = useRef(false)

  // Sin `setTimeout`: el foco se da cuando React ya quitó el diálogo o ya pintó la nota.
  useEffect(() => {
    if (abierto || !devolver.current) return
    devolver.current = false
    boton.current?.focus()
  }, [abierto])
  useEffect(() => {
    if (entregado) document.getElementById(nota)?.focus()
  }, [entregado, nota])

  return (
    <div className="flex max-w-xl flex-col items-start gap-3 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea">
      <p id={`${uid}-a`} className="max-w-prose text-base">
        {T.ayudaArchivo}
      </p>
      <p className="max-w-prose text-base text-tenue">{T.ayudaNoventa}</p>
      <Boton
        ref={boton}
        variante="principal"
        icono={<Download aria-hidden className="size-5" />}
        aria-describedby={`${uid}-a`}
        className="angosto:self-stretch"
        onClick={() => {
          setEntregado(false)
          setAbierto(true)
        }}
      >
        {T.descargarEnArchivo}
      </Boton>
      {entregado && (
        <Nota id={nota} tono="ok" rol="status" enfocable>
          {T.entregado}
        </Nota>
      )}
      {abierto && (
        <DialogoConfirmar
          titulo={T.dialogoTitulo}
          texto={texto}
          destacado={destacado}
          confirmar={T.descargar}
          confirmando={T.descargar}
          seguir={T.noDescargar}
          error={T.errArchivo}
          variante="principal"
          icono={<Download aria-hidden className="size-5" />}
          onConfirmar={async () => {
            try {
              guardarArchivo(copia.texto, copia.nombreArchivo)
            } catch {
              return false
            }
            setAbierto(false)
            setEntregado(true)
            return true
          }}
          onCerrar={() => {
            devolver.current = true
            setAbierto(false)
          }}
        />
      )}
    </div>
  )
}

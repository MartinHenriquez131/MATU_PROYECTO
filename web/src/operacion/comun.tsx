// Piezas que comparten las pantallas de la consola de operación (MATU-81): las etiquetas de estado
// (siempre ícono y palabra, nunca solo el color), la fila de una cola, el foco después de montar, la
// hora del servidor y la columna de la cola con su detalle. Ningún color ni tamaño fuera del tema.
import { useCallback, useEffect, useReducer, useRef, type ReactNode } from 'react'
import {
  Ban,
  Check,
  ChevronRight,
  Circle,
  CircleCheck,
  Clock,
  Contrast,
  Package,
  PackageCheck,
  PackageX,
  TriangleAlert,
  Truck,
  type LucideIcon,
} from 'lucide-react'
import type { AnulacionVista, EstadoIncidencia, ParteDetalle, VentaVista } from '../compartido/api/operacion'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { pesos } from '../familia/textosCatalogo'
import { Etiqueta } from '../familia/ui'
import { ESTADO_ANULACION, ESTADO_INCIDENCIA, ESTADO_PARTE, ESTADO_PEDIDO, ESTADO_VENTA } from './textos'

export { pesos }

type Tono = 'neutro' | 'ok' | 'activo' | 'atenta'
const ICONO = 'size-5 shrink-0'

/** Una `Etiqueta` con su ícono (hijo directo, se oculta en `angosto`) y su palabra. */
export function EtiquetaCon({ Icono, tono, texto, className = '' }: { Icono: LucideIcon; tono: Tono; texto: string; className?: string }) {
  return (
    <Etiqueta tono={tono} className={className}>
      <Icono aria-hidden className={ICONO} />
      <span className="min-w-0">{texto}</span>
    </Etiqueta>
  )
}

/** 5.5: el estado del pedido. */
const TONO_PEDIDO: Record<string, [LucideIcon, Tono]> = {
  pagado: [Circle, 'neutro'],
  enviado_a_comercio: [Circle, 'neutro'],
  preparando: [Contrast, 'neutro'],
  listo_retiro: [PackageCheck, 'atenta'],
  retirado: [Package, 'atenta'],
  asignado: [TriangleAlert, 'atenta'],
  sin_repartidor: [TriangleAlert, 'atenta'],
  en_ruta: [Truck, 'activo'],
  entregado: [PackageCheck, 'ok'],
  cerrado: [PackageCheck, 'ok'],
  no_entregado: [PackageX, 'atenta'],
  reprogramado: [Clock, 'neutro'],
  cancelado: [Ban, 'neutro'],
  cancelado_con_devolucion: [Ban, 'neutro'],
}

export const palabraPedido = (estado: string) => ESTADO_PEDIDO[estado] ?? null

export function EtiquetaPedido({ estado, className = '' }: { estado: string; className?: string }) {
  const palabra = palabraPedido(estado)
  const t = TONO_PEDIDO[estado]
  if (!palabra || !t) return null
  return <EtiquetaCon Icono={t[0]} tono={t[1]} texto={palabra} className={className} />
}

/** 6.3: el estado de la parte, con las palabras y los íconos del comercio ([C63] 5.4). */
const TONO_PARTE: Record<ParteDetalle['estado'], [LucideIcon, Tono]> = {
  enviada: [Circle, 'atenta'],
  preparando: [Contrast, 'neutro'],
  lista: [PackageCheck, 'ok'],
  retirada: [CircleCheck, 'neutro'],
  cancelada: [Ban, 'neutro'],
}

export function EtiquetaParte({ estado }: { estado: ParteDetalle['estado'] }) {
  const [Icono, tono] = TONO_PARTE[estado]
  return <EtiquetaCon Icono={Icono} tono={tono} texto={ESTADO_PARTE[estado]} />
}

/** 7: el estado de la venta. Sin «rechazada» ni «error» en pantalla. */
const TONO_VENTA: Record<VentaVista['estado'], [LucideIcon, Tono]> = {
  iniciada: [Circle, 'neutro'],
  autorizando: [Clock, 'atenta'],
  aprobada: [Check, 'ok'],
  rechazada: [Ban, 'neutro'],
  error: [TriangleAlert, 'atenta'],
}

export function EtiquetaVenta({ estado }: { estado: VentaVista['estado'] }) {
  const [Icono, tono] = TONO_VENTA[estado]
  return <EtiquetaCon Icono={Icono} tono={tono} texto={ESTADO_VENTA[estado]} />
}

/** 7: el estado de una devolución. `rechazada` en la API es «Sin terminar» en pantalla. */
const TONO_ANULACION: Record<AnulacionVista['estado'], [LucideIcon, Tono]> = {
  hecha: [Check, 'ok'],
  en_curso: [Clock, 'atenta'],
  rechazada: [TriangleAlert, 'atenta'],
}

export function EtiquetaAnulacion({ estado }: { estado: AnulacionVista['estado'] }) {
  const [Icono, tono] = TONO_ANULACION[estado]
  return <EtiquetaCon Icono={Icono} tono={tono} texto={ESTADO_ANULACION[estado]} />
}

/** 9.1: el estado de una incidencia. */
const TONO_INCIDENCIA: Record<EstadoIncidencia, [LucideIcon, Tono]> = {
  abierta: [Circle, 'atenta'],
  en_gestion: [Contrast, 'activo'],
  resuelta: [CircleCheck, 'ok'],
}

export function EtiquetaIncidencia({ estado }: { estado: EstadoIncidencia }) {
  const [Icono, tono] = TONO_INCIDENCIA[estado]
  return <EtiquetaCon Icono={Icono} tono={tono} texto={ESTADO_INCIDENCIA[estado]} />
}

/** Fecha y hora de Chile de un instante del contrato. `dia` es `DD/MM`. */
export function enChile(iso: string): { fecha: string; dia: string; hora: string } {
  const { fecha, hora } = fechaYHoraDeChile(new Date(iso))
  return { fecha, dia: fecha.slice(0, 5), hora }
}

/** El monto en pesos dentro de `cifras`. */
export function Monto({ n, signo = '' }: { n: number; signo?: string }) {
  return (
    <span className="cifras">
      {signo}
      {pesos(n)}
    </span>
  )
}

/** 5.3: la fila de una cola, un botón de ancho completo. Elegida: `aria-current`, `rocio` y la flecha. */
export function FilaCola({ elegida, nombre, onElegir, primera, children }: { elegida: boolean; nombre: string; onElegir: () => void; primera: ReactNode; children?: ReactNode }) {
  return (
    <button
      type="button"
      aria-current={elegida ? 'true' : undefined}
      aria-label={nombre}
      onClick={onElegir}
      className={`flex min-h-12 w-full flex-col items-start gap-0.5 rounded-xl px-4 angosto:px-2 py-3 text-left ${
        elegida ? 'bg-rocio ring-2 ring-turquesa' : 'bg-hoja ring-1 ring-linea hover:ring-borde'
      }`}
    >
      {/* Revisión visual (P3): el chevron va fuera del `flex-wrap`, para que nunca baje a una línea sola. */}
      <span className="flex w-full items-start gap-x-3 font-bold">
        <span className="flex min-w-0 flex-1 flex-wrap items-center justify-between gap-x-3 gap-y-1">{primera}</span>
        {elegida && <ChevronRight aria-hidden className="mt-0.5 ml-auto size-5 shrink-0" />}
      </span>
      {children}
    </button>
  )
}

/** Lo que pide atención en una fila: `TriangleAlert` y palabra, en `atenta`. */
export function Atencion({ children }: { children: ReactNode }) {
  return (
    <span className="flex items-start gap-1.5 font-bold text-atenta">
      <TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0" />
      <span className="min-w-0">{children}</span>
    </span>
  )
}

/**
 * El foco va a un elemento cuando ya está montado (P1 de la revisión de MATU-63): el efecto corre
 * después de cada render y espera a que el elemento exista. Nunca termina en `body`. El pedido pendiente
 * va en una referencia (MATU-79): soltarlo no necesita otro render.
 */
export function useFocoAlMontar() {
  const foco = useRef<{ id: string; selector?: string } | null>(null)
  const [, repintar] = useReducer((n: number) => n + 1, 0)
  useEffect(() => {
    if (!foco.current) return
    const el = document.getElementById(foco.current.id)
    const objetivo = foco.current.selector ? el?.querySelector<HTMLElement>(foco.current.selector) : el
    if (!objetivo) return
    objetivo.focus()
    foco.current = null
  })
  return useCallback((id: string, selector?: string) => {
    foco.current = { id, selector }
    repintar()
  }, [])
}

/** La hora del servidor (cabecera `Date` de la última respuesta), nunca el reloj del teléfono solo. */
export function useAhora() {
  const desfase = useRef(0)
  const fijarFecha = useCallback((fecha: Date | null) => {
    if (fecha) desfase.current = fecha.getTime() - Date.now()
  }, [])
  const ahora = useCallback(() => new Date(Date.now() + desfase.current), [])
  return { ahora, fijarFecha }
}

/** 5.6: cada 60 segundos con la pestaña visible y al volver a ella. Nunca mueve el foco. */
export function useAlDia(traer: () => void, activo = true) {
  useEffect(() => {
    if (!activo) return
    const t = window.setInterval(() => {
      if (document.visibilityState === 'visible') traer()
    }, 60_000)
    const alVolver = () => {
      if (document.visibilityState === 'visible') traer()
    }
    document.addEventListener('visibilitychange', alVolver)
    return () => {
      window.clearInterval(t)
      document.removeEventListener('visibilitychange', alVolver)
    }
  }, [traer, activo])
}

/** La grilla de la consola del comercio: la cola de 19 rem y el detalle desde 48 rem de `main`. */
export const GRILLA = 'grid grid-cols-1 items-start gap-x-8 gap-y-8 @3xl/main:grid-cols-[19rem_minmax(0,1fr)]'
/** El cuadro del detalle en pantalla ancha. */
export const CUADRO_DETALLE = 'min-w-0 @container/detalle @3xl/main:rounded-xl @3xl/main:bg-hoja @3xl/main:px-8 @3xl/main:py-5 @3xl/main:ring-1 @3xl/main:ring-linea'
/** El cuadro vacío del detalle, solo en ancho. */
export const CUADRO_VACIO = 'hidden rounded-xl bg-hoja px-6 py-6 ring-1 ring-linea @3xl/main:block'

/** El `textarea` de `EditorSeccion`, con su contador de 500. */
export function AreaTexto({
  id,
  etiqueta,
  valor,
  onCambio,
  describe,
  error,
  contador,
}: {
  id: string
  etiqueta: string
  valor: string
  onCambio: (v: string) => void
  /** Los ids de la ayuda (antes del campo) y del error. */
  describe: string
  error: boolean
  contador: (n: number) => string
}) {
  const cerca = valor.length >= 450
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="font-bold">
        {etiqueta}
      </label>
      <textarea
        id={id}
        rows={4}
        maxLength={500}
        autoComplete="off"
        value={valor}
        onChange={(e) => onCambio(e.target.value)}
        aria-invalid={error || undefined}
        aria-describedby={`${describe} ${id}-cuenta`}
        className={`min-h-32 w-full resize-y rounded-xl bg-hoja px-4 py-3 text-lg ring-2 ring-inset focus-visible:ring-turquesa ${error ? 'ring-pronto' : 'ring-borde'}`}
      />
      <p id={`${id}-cuenta`} aria-live={cerca ? 'polite' : undefined} className={`flex items-center gap-1.5 text-base ${cerca ? 'font-bold text-atenta' : 'text-tenue'}`}>
        {cerca && <TriangleAlert aria-hidden className="size-5 shrink-0" />}
        <span className="min-w-0">
          <span className="cifras">{valor.length}</span> {contador(valor.length).replace(/^\d+ /, '')}
        </span>
      </p>
    </div>
  )
}

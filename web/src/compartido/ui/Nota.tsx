// `Nota` de la app de la familia (familia/ui.tsx), aquí para que la use también el relevo: el aviso
// de versión nueva (MATU-67, especificación 3 y G4) se ve igual en las dos apps. Sin cambios.
import { useRef, type ReactNode } from 'react'
import { CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react'
import { useAnunciarAlMostrar } from './Anuncios'

type TonoNota = 'rocio' | 'atenta' | 'pronto' | 'ok'
const FONDO_NOTA: Record<TonoNota, string> = { rocio: 'bg-rocio', atenta: 'bg-atenta-fondo', pronto: 'bg-pronto-fondo', ok: 'bg-ok-fondo' }
const ICONO_NOTA: Record<TonoNota, ReactNode> = {
  rocio: <Info aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />,
  atenta: <TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />,
  pronto: <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-pronto" />,
  ok: <CircleCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-ok" />,
}

/**
 * Nota con ícono propio por tono: nunca solo el color. `borde` agrega la línea izquierda de los avisos grandes.
 * Con `rol`, la nota es un aviso: se anuncia por las regiones vivas (compartido/ui/Anuncios),
 * `status` amable y `alert` urgente, y no lleva el rol para no leerse dos veces. En modo angosto
 * los rellenos se achican, para que el título no se parta dentro de una palabra (#51, P2-1).
 */
export function Nota({
  titulo,
  children,
  tono = 'rocio',
  icono,
  rol,
  borde = false,
  className = '',
  id,
  enfocable = false,
  iconoEnLinea = false,
}: {
  titulo?: ReactNode
  children?: ReactNode
  tono?: TonoNota
  icono?: ReactNode
  rol?: 'status' | 'alert'
  borde?: boolean
  className?: string
  id?: string
  /** MATU-44 3.5: la nota recibe el foco tras una acción. No es un control: sin contorno. */
  enfocable?: boolean
  /**
   * MATU-44 (revisión del 07-11): en modo angosto el ícono va en la primera línea del título, como
   * en `MensajeError`, para que el título use todo el ancho y una palabra larga no se salga.
   */
  iconoEnLinea?: boolean
}) {
  const linea = borde ? { rocio: 'border-l-4 border-turquesa', atenta: 'border-l-4 border-atenta', pronto: 'border-l-4 border-pronto', ok: 'border-l-4 border-ok' }[tono] : ''
  const ref = useRef<HTMLDivElement>(null)
  useAnunciarAlMostrar(ref, rol)
  return (
    <div
      ref={ref}
      id={id}
      data-aviso={rol}
      tabIndex={enfocable ? -1 : undefined}
      className={`flex max-w-prose gap-3 angosto:gap-2 rounded-xl px-4 angosto:px-2 py-3 ${FONDO_NOTA[tono]} ${linea} ${enfocable ? 'outline-none' : ''} ${className}`}
    >
      {iconoEnLinea && titulo ? <span className="contents angosto:hidden">{icono ?? ICONO_NOTA[tono]}</span> : (icono ?? ICONO_NOTA[tono])}
      <div className="min-w-0">
        {titulo && (
          <p className="mb-0.5 font-bold">
            {iconoEnLinea && <span className="hidden angosto:me-1.5 angosto:inline-flex angosto:align-middle">{icono ?? ICONO_NOTA[tono]}</span>}
            {titulo}
          </p>
        )}
        {children && <div className="text-base leading-relaxed">{children}</div>}
      </div>
    </div>
  )
}

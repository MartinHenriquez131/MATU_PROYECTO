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
  iconoEnLinea = true,
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
   * en `MensajeError`, para que el título use todo el ancho y una palabra larga no se salga. Sin
   * título (MATU-54), en la primera línea del texto.
   *
   * MATU-121 (docs/diseno/matu-121-nota-icono.md): es el valor por omisión, en los cuatro tonos y con
   * `borde`. En línea el ícono mide siempre `size-5`, sin margen superior; sin título flota al comienzo
   * del texto, así sirve con texto suelto y con párrafos. Una nota sin título cuyo cuerpo empieza con
   * un botón o un enlace lleva `iconoEnLinea={false}`. Fuera del modo angosto no cambia nada.
   */
  iconoEnLinea?: boolean
}) {
  const linea = borde ? { rocio: 'border-l-4 border-turquesa', atenta: 'border-l-4 border-atenta', pronto: 'border-l-4 border-pronto', ok: 'border-l-4 border-ok' }[tono] : ''
  const ref = useRef<HTMLDivElement>(null)
  useAnunciarAlMostrar(ref, rol)
  // Sin título ni texto no hay línea donde ponerlo: el ícono se queda en su columna.
  const enLinea = iconoEnLinea && Boolean(titulo || children)
  const flota = enLinea && !titulo
  const dibujo = icono ?? ICONO_NOTA[tono]
  return (
    <div
      ref={ref}
      id={id}
      data-aviso={rol}
      tabIndex={enfocable ? -1 : undefined}
      className={`flex max-w-prose gap-3 angosto:gap-2 rounded-xl px-4 angosto:px-2 py-3 ${FONDO_NOTA[tono]} ${linea} ${enfocable ? 'outline-none' : ''} ${className}`}
    >
      {enLinea ? <span className="contents angosto:hidden">{dibujo}</span> : dibujo}
      <div className="min-w-0">
        {titulo && (
          <p className="mb-0.5 font-bold">
            {enLinea && <span className="hidden angosto:me-1.5 angosto:inline-flex angosto:align-middle angosto:[&>svg]:size-5 angosto:[&>svg]:mt-0">{dibujo}</span>}
            {titulo}
          </p>
        )}
        {children && (
          <div className={`text-base leading-relaxed ${flota ? 'angosto:flow-root' : ''}`}>
            {/* MATU-54 (1.2, P1-2) y MATU-121: sin título, el ícono flota al comienzo del texto en modo angosto. */}
            {flota && (
              <span className="hidden angosto:block angosto:float-start angosto:me-1.5 angosto:mt-0.75 angosto:leading-none angosto:[&>svg]:size-5 angosto:[&>svg]:mt-0">{dibujo}</span>
            )}
            {children}
          </div>
        )}
      </div>
    </div>
  )
}

// Botones de MATU (especificación MATU-23, sección 5). Al ancho de su texto, 48 px o más de alto
// (`min-h-12` = 51 px con la raíz de 17 px) y nunca deshabilitados: la validación ocurre al enviar.
import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variante = 'principal' | 'secundario'

const VARIANTES: Record<Variante, string> = {
  principal: 'bg-turquesa text-papel hover:brightness-110 active:brightness-95',
  secundario: 'bg-hoja text-turquesa ring-2 ring-inset ring-turquesa/70 hover:bg-rocio active:bg-rocio',
}

export function Boton({
  variante = 'principal',
  icono,
  ocupado = false,
  textoOcupado,
  className = '',
  children,
  onClick,
  ...resto
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: Variante
  icono?: ReactNode
  /** Mientras pide algo: conserva su ancho, dice el gerundio y no envía otra vez. */
  ocupado?: boolean
  textoOcupado?: string
}) {
  return (
    <button
      type="button"
      aria-busy={ocupado || undefined}
      onClick={(e) => {
        if (ocupado) {
          e.preventDefault()
          return
        }
        onClick?.(e)
      }}
      className={`inline-flex min-h-12 max-w-full items-center justify-center gap-2 rounded-xl px-5 angosto:px-3 py-2.5 font-bold leading-tight ${VARIANTES[variante]} ${className}`}
      {...resto}
    >
      {icono && <span className="contents angosto:hidden">{icono}</span>}
      {/* Los dos textos ocupan la misma celda: el botón mide lo que el más largo y no salta. */}
      <span className="grid min-w-0">
        <span className={`col-start-1 row-start-1 break-words hyphens-auto ${ocupado && textoOcupado ? 'invisible' : ''}`}>{children}</span>
        {textoOcupado && (
          <span className={`col-start-1 row-start-1 break-words hyphens-auto ${ocupado ? '' : 'invisible'}`} aria-hidden={!ocupado || undefined}>
            {textoOcupado}
          </span>
        )}
      </span>
    </button>
  )
}

// Piezas que comparten «Insumos» (MATU-36 y MATU-37) y la «Lista de insumos» (MATU-60): el campo
// numérico con − y +, el ancho de dos columnas y la lectura del 403 del consumo. Extraídas de
// Insumos.tsx sin cambiar cómo se ven (especificación MATU-60, 4.4).
import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { Minus, Plus } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { INSUMOS } from './textosInsumos'
import { MensajeError } from './ui'

export const esTipo = (tipo: string | null, nombre: string) => !!tipo && tipo.endsWith(`/errores/${nombre}`)

/** El 403 del consumo, si lo es. */
export function permisoDe(x: unknown): 'sin-consentimiento' | 'revision-vencida' | null {
  const f = leerFallo(x)
  if (f.status !== 403) return null
  return esTipo(f.tipo, 'revision-vencida') ? 'revision-vencida' : 'sin-consentimiento'
}

/** `true` cuando el contenido mide 48 rem o más (`@3xl/main`): dos columnas (MATU-36 2.3, MATU-60 2.3). */
export function useAncho() {
  const ref = useRef<HTMLDivElement>(null)
  const [ancho, setAncho] = useState(false)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const medir = () => {
      const rem = Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
      setAncho(el.clientWidth >= 48 * rem)
    }
    medir()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(medir)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return { ref, ancho }
}

export const enfocar = (id: string, ms = 40) => window.setTimeout(() => document.getElementById(id)?.focus(), ms)

export const soloDigitos = (v: string, largo = 6) => v.replace(/[^0-9]/g, '').slice(0, largo)
export const entero = (v: string) => (v.trim() === '' ? null : Number.parseInt(v, 10))
export const unaLinea = (v: string) => v.replace(/[\r\n]+/g, ' ')

/**
 * Campo de texto numérico con − y + (`Stepper` de MATU-36). Con `nombradoPor`, el campo se nombra
 * con la etiqueta y ese id (la lista: «Cantidad, Pañal adulto talla M», MATU-60 4.4), y los
 * botones pueden traer su propio nombre para el lector.
 */
export function Stepper({
  id,
  etiqueta,
  ayuda,
  sufijo,
  valor,
  onCambio,
  min,
  max,
  error,
  nombradoPor,
  textoMenos,
  textoMas,
}: {
  id: string
  etiqueta: string
  ayuda?: ReactNode
  sufijo?: string
  valor: string
  onCambio: (v: string) => void
  min: number
  max: number
  error?: string | null
  nombradoPor?: string
  textoMenos?: string
  textoMas?: string
}) {
  const describe = [ayuda ? `${id}-a` : '', error ? `${id}-e` : ''].filter(Boolean).join(' ') || undefined
  const paso = (d: number) => {
    const n = entero(valor)
    const base = n === null ? (d > 0 ? min - 1 : min + 1) : n
    onCambio(String(Math.max(min, Math.min(max, base + d))))
  }
  const claseBoton = 'grid size-12 shrink-0 place-items-center rounded-xl bg-hoja text-turquesa ring-2 ring-inset ring-turquesa/70 hover:bg-rocio active:bg-rocio'
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label id={`${id}-l`} htmlFor={id} className="font-bold">
        {etiqueta}
      </label>
      {ayuda && (
        <span id={`${id}-a`} className="text-base text-tenue">
          {ayuda}
        </span>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className={claseBoton} aria-label={textoMenos ?? INSUMOS.menos(etiqueta)} onClick={() => paso(-1)}>
          <Minus aria-hidden className="size-5" />
        </button>
        <input
          id={id}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          autoComplete="off"
          value={valor}
          aria-labelledby={nombradoPor ? `${id}-l ${nombradoPor}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={describe}
          onChange={(e) => onCambio(soloDigitos(e.target.value))}
          className={`cifras min-h-12 w-24 rounded-xl bg-hoja px-2 py-2 text-center text-xl ring-2 ring-inset focus-visible:ring-turquesa ${error ? 'ring-pronto' : 'ring-borde'}`}
        />
        <button type="button" className={claseBoton} aria-label={textoMas ?? INSUMOS.mas(etiqueta)} onClick={() => paso(1)}>
          <Plus aria-hidden className="size-5" />
        </button>
        {sufijo && <span className="text-base text-tenue">{sufijo}</span>}
      </div>
      {error && <MensajeError id={`${id}-e`}>{error}</MensajeError>}
    </div>
  )
}

// Piezas de interfaz compartidas. Objetivos táctiles de 48 px o más, foco visible y
// estado dicho con palabra además de color.
import { useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'
import { Minus, Plus } from 'lucide-react'
import { ETIQUETA_NIVEL, type Nivel } from '../demo/calculos'

type Variante = 'primario' | 'secundario' | 'suave' | 'texto'

const VARIANTES: Record<Variante, string> = {
  primario: 'bg-pino text-papel shadow-[0_1px_0_rgb(0_0_0/0.12),0_6px_16px_-8px_var(--color-pino)] hover:brightness-110 active:brightness-95',
  secundario: 'bg-hoja text-pino ring-2 ring-inset ring-pino/70 hover:bg-rocio',
  suave: 'bg-rocio text-pino hover:brightness-[0.97]',
  texto: 'text-pino underline-offset-4 hover:underline',
}

export function Boton({
  variante = 'primario',
  icono,
  className = '',
  children,
  ...resto
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante; icono?: ReactNode }) {
  return (
    <button
      type="button"
      className={`inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl px-4 py-2.5 text-center font-bold leading-tight transition-[filter,background-color] disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTES[variante]} ${className}`}
      {...resto}
    >
      {icono}
      <span className="min-w-0 break-words">{children}</span>
    </button>
  )
}

export function Fila({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`flex flex-wrap gap-2.5 [&>*]:min-w-[min(100%,9rem)] [&>*]:flex-1 ${className}`}>{children}</div>
}

export function Tarjeta({
  children,
  className = '',
  tono = 'hoja',
}: {
  children: ReactNode
  className?: string
  tono?: 'hoja' | 'pronto' | 'ok' | 'atenta' | 'rocio' | 'borde'
}) {
  const t = {
    hoja: 'bg-hoja shadow-[0_1px_2px_rgb(0_0_0/0.05)] ring-1 ring-linea',
    pronto: 'bg-pronto-fondo ring-1 ring-pronto/25',
    ok: 'bg-ok-fondo ring-1 ring-ok/25',
    atenta: 'bg-atenta-fondo ring-1 ring-atenta/25',
    rocio: 'bg-rocio',
    borde: 'bg-transparent border-2 border-dashed border-linea',
  }[tono]
  return <div className={`flex flex-col gap-2 rounded-[1.35rem] p-4 ${t} ${className}`}>{children}</div>
}

const ESTILO_NIVEL: Record<Nivel, string> = {
  pronto: 'bg-pronto-fondo text-pronto',
  atenta: 'bg-atenta-fondo text-atenta',
  tranquila: 'bg-ok-fondo text-ok',
}

export function EtiquetaNivel({ nivel }: { nivel: Nivel }) {
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-sm font-bold ${ESTILO_NIVEL[nivel]}`}>
      <span aria-hidden className="size-2 rounded-full bg-current" />
      {ETIQUETA_NIVEL[nivel]}
    </span>
  )
}

export function Etiqueta({ children, tono = 'neutro' }: { children: ReactNode; tono?: 'neutro' | 'ok' | 'pronto' | 'atenta' | 'pino' }) {
  const t = {
    neutro: 'bg-tinta/[0.07] text-tenue',
    ok: 'bg-ok-fondo text-ok',
    pronto: 'bg-pronto-fondo text-pronto',
    atenta: 'bg-atenta-fondo text-atenta',
    pino: 'bg-rocio text-pino',
  }[tono]
  return <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-0.5 text-sm font-bold ${t}`}>{children}</span>
}

/** Barra de avance de la ficha, por campos. */
export function BarraCampos({ hechos, total = 3 }: { hechos: number; total?: number }) {
  return (
    <div className="flex gap-1.5" role="img" aria-label={`${hechos} de ${total} campos listos`}>
      {Array.from({ length: total }, (_, i) => (
        <span
          key={i}
          className={`h-2.5 flex-1 rounded-full transition-colors duration-500 ${i < hechos ? 'bg-pino' : 'bg-tinta/10'}`}
        />
      ))}
    </div>
  )
}

/** Barra de días restantes: llena = 30 días o más. */
export function BarraDias({ dias, nivel }: { dias: number; nivel: Nivel }) {
  const pct = Math.max(4, Math.min(100, Math.round((Math.min(dias, 30) / 30) * 100)))
  const color = { pronto: 'bg-pronto', atenta: 'bg-atenta', tranquila: 'bg-ok' }[nivel]
  return (
    <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-tinta/[0.08]" aria-hidden>
      <div className={`h-full rounded-full ${color} transition-[width] duration-700 ease-[var(--ease-calma)]`} style={{ width: `${pct}%` }} />
      {/* marca de los 7 días, cuando avisamos */}
      <span className="absolute inset-y-0 w-0.5 bg-hoja" style={{ left: `${(7 / 30) * 100}%` }} />
    </div>
  )
}

export function Stepper({
  etiqueta,
  valor,
  onCambio,
  min = 0,
  max = 999,
  paso = 1,
  unidad,
  ayuda,
}: {
  etiqueta: string
  valor: number
  onCambio: (v: number) => void
  min?: number
  max?: number
  paso?: number
  unidad?: string
  ayuda?: string
}) {
  const id = useId()
  const btn =
    'grid size-13 shrink-0 place-items-center rounded-2xl bg-hoja text-pino ring-2 ring-inset ring-pino/60 hover:bg-rocio disabled:opacity-40'
  return (
    <div className="flex flex-col gap-2">
      <span id={id} className="font-bold">
        {etiqueta}
      </span>
      <div className="flex flex-wrap items-center gap-3" role="group" aria-labelledby={id}>
        <button type="button" className={btn} aria-label={`Menos: ${etiqueta}`} disabled={valor <= min} onClick={() => onCambio(Math.max(min, valor - paso))}>
          <Minus aria-hidden className="size-6" strokeWidth={2.5} />
        </button>
        <output aria-live="polite" className="cifras min-w-[3ch] text-center text-[1.9rem] font-bold leading-none">
          {valor}
        </output>
        <button type="button" className={btn} aria-label={`Más: ${etiqueta}`} disabled={valor >= max} onClick={() => onCambio(Math.min(max, valor + paso))}>
          <Plus aria-hidden className="size-6" strokeWidth={2.5} />
        </button>
        {unidad && <span className="text-tenue">{unidad}</span>}
      </div>
      {ayuda && <span className="text-sm text-tenue">{ayuda}</span>}
    </div>
  )
}

export function GrupoOpciones<T extends string>({
  leyenda,
  opciones,
  valor,
  onCambio,
  nombre,
}: {
  leyenda: string
  opciones: { valor: T; texto: string; detalle?: string }[]
  valor: T | null
  onCambio: (v: T) => void
  nombre: string
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 font-bold">{leyenda}</legend>
      {opciones.map((o) => {
        const on = o.valor === valor
        return (
          <label
            key={o.valor}
            className={`flex min-h-13 cursor-pointer items-center gap-3 rounded-2xl px-4 py-3 ring-2 ring-inset transition-colors has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pino ${
              on ? 'bg-rocio ring-pino' : 'bg-hoja ring-linea hover:ring-pino/40'
            }`}
          >
            <input type="radio" name={nombre} className="peer sr-only" checked={on} onChange={() => onCambio(o.valor)} />
            <span
              aria-hidden
              className={`grid size-6 shrink-0 place-items-center rounded-full ring-2 ring-inset ${on ? 'ring-pino' : 'ring-tenue/60'}`}
            >
              {on && <span className="size-3 rounded-full bg-pino" />}
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="font-bold leading-snug">{o.texto}</span>
              {o.detalle && <span className="text-sm text-tenue">{o.detalle}</span>}
            </span>
          </label>
        )
      })}
    </fieldset>
  )
}

export function Chip({ activo, onClick, children }: { activo: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={activo}
      onClick={onClick}
      className={`inline-flex min-h-12 items-center gap-1.5 rounded-full px-4 py-2 font-bold ring-2 ring-inset transition-colors ${
        activo ? 'bg-pino text-papel ring-pino' : 'bg-hoja text-tenue ring-linea hover:ring-pino/40'
      }`}
    >
      {children}
    </button>
  )
}

export function CampoTexto({
  etiqueta,
  ayuda,
  error,
  ...resto
}: InputHTMLAttributes<HTMLInputElement> & { etiqueta: string; ayuda?: string; error?: string | null }) {
  const id = useId()
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="font-bold">
        {etiqueta}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={ayuda || error ? `${id}-a` : undefined}
        className={`min-h-13 w-full min-w-0 rounded-2xl bg-hoja px-4 py-3 ring-2 ring-inset outline-none placeholder:text-tenue/80 focus-visible:ring-pino ${
          error ? 'ring-pronto' : 'ring-linea'
        }`}
        {...resto}
      />
      {(ayuda || error) && (
        <span id={`${id}-a`} className={`text-sm ${error ? 'font-bold text-pronto' : 'text-tenue'}`}>
          {error ?? ayuda}
        </span>
      )}
    </div>
  )
}

export function Nota({ titulo, children, tono = 'rocio' }: { titulo?: string; children: ReactNode; tono?: 'rocio' | 'atenta' | 'pronto' }) {
  const t = { rocio: 'bg-rocio', atenta: 'bg-atenta-fondo', pronto: 'bg-pronto-fondo' }[tono]
  return (
    <div className={`rounded-2xl px-4 py-3 ${t}`}>
      {titulo && <p className="mb-1 font-bold">{titulo}</p>}
      <div className="text-[0.95rem] leading-relaxed">{children}</div>
    </div>
  )
}

export function Sello({ children, tono = 'pino' }: { children: ReactNode; tono?: 'pino' | 'suave' | 'pronto' }) {
  const t = {
    pino: 'bg-pino text-papel',
    suave: 'bg-rocio text-pino',
    pronto: 'bg-pronto-fondo text-pronto',
  }[tono]
  return <div className={`mx-auto grid size-18 place-items-center rounded-[1.6rem] ${t}`}>{children}</div>
}

export function Logo({ className = 'size-10', claro = false }: { className?: string; claro?: boolean }) {
  return (
    <svg viewBox="0 0 48 48" className={className} role="img" aria-label="MATU">
      <rect width="48" height="48" rx="14" className={claro ? 'fill-papel' : 'fill-pino'} />
      <path
        d="M11 23.5 24 12l13 11.5"
        fill="none"
        className={claro ? 'stroke-pino' : 'stroke-papel'}
        strokeWidth="3.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M24 35.4 15.3 25.3a4.45 4.45 0 0 1 8.7-1.6 4.45 4.45 0 0 1 8.7 1.6z" className="fill-miel" />
    </svg>
  )
}

export function Separador() {
  return <hr className="border-0 border-t border-dashed border-linea" />
}

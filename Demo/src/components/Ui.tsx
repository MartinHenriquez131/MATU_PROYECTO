// Piezas de interfaz compartidas. Objetivos de 48 px o más, foco visible y estado dicho con
// palabra y con forma, además de color.
import { useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'
import { Check, Heart, Minus, Plus } from 'lucide-react'
import { ETIQUETA_NIVEL, type Nivel } from '../demo/calculos'

type Variante = 'primario' | 'secundario' | 'suave' | 'texto'

const VARIANTES: Record<Variante, string> = {
  primario: 'bg-pino text-papel hover:brightness-110 active:brightness-95',
  secundario: 'bg-hoja text-pino ring-2 ring-inset ring-pino/70 hover:bg-rocio',
  suave: 'bg-rocio text-pino hover:brightness-95',
  texto: 'text-pino underline underline-offset-4 decoration-pino/40 hover:decoration-pino px-1',
}

export function Boton({
  variante = 'primario',
  icono,
  ancho = false,
  className = '',
  children,
  ...resto
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante; icono?: ReactNode; ancho?: boolean }) {
  return (
    <button
      type="button"
      className={`inline-flex min-h-12 max-w-full items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-left font-bold leading-tight transition-[filter,background-color] disabled:cursor-not-allowed disabled:opacity-50 ${ancho ? 'w-full' : ''} ${VARIANTES[variante]} ${className}`}
      {...resto}
    >
      {icono}
      <span className="min-w-0 break-words">{children}</span>
    </button>
  )
}

/** Fila de acciones: a la izquierda, bajo lo que confirman, y se envuelve si no cabe. */
export function Acciones({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`flex flex-wrap items-center gap-3 ${className}`}>{children}</div>
}

/**
 * La hoja del refrigerador: la única superficie con sombra de la demo, con su imán de miel.
 * Se ve igual en el inicio, al editar, en la página del relevo y para imprimir.
 */
export function Hoja({
  children,
  inclinada = false,
  className = '',
  etiqueta,
}: {
  children: ReactNode
  inclinada?: boolean
  className?: string
  etiqueta?: string
}) {
  return (
    <div
      className={`relative pt-3 ${inclinada ? '@3xl/app:-rotate-1' : ''} ${className}`}
      role={etiqueta ? 'group' : undefined}
      aria-label={etiqueta}
    >
      <span
        aria-hidden
        className="absolute top-0 left-1/2 z-10 size-7 -translate-x-1/2 rounded-full bg-miel shadow-md"
      />
      <div className="rounded-sm bg-hoja px-4 @3xl:px-9 pt-7 pb-6 shadow-xl ring-1 ring-linea/60">
        {children}
      </div>
    </div>
  )
}

/** Forma del chip según el nivel: lleno, a medias o vacío. El estado no depende solo del color. */
function FormaNivel({ nivel }: { nivel: Nivel }) {
  if (nivel === 'pronto') return <span aria-hidden className="size-2.5 rounded-full bg-current" />
  if (nivel === 'atenta')
    return (
      <span aria-hidden className="grid size-2.5 place-items-center rounded-full border-2 border-current">
        <span className="size-0.5 rounded-full bg-current" />
      </span>
    )
  return <span aria-hidden className="size-2.5 rounded-full border-2 border-current" />
}

const ESTILO_NIVEL: Record<Nivel, string> = {
  pronto: 'bg-pronto-fondo text-pronto',
  atenta: 'bg-atenta-fondo text-atenta',
  tranquila: 'bg-ok-fondo text-ok',
}

export function EtiquetaNivel({ nivel }: { nivel: Nivel }) {
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-base font-bold ${ESTILO_NIVEL[nivel]}`}>
      <FormaNivel nivel={nivel} />
      {ETIQUETA_NIVEL[nivel]}
    </span>
  )
}

export type Tono = 'neutro' | 'ok' | 'pronto' | 'atenta' | 'pino'

export function Etiqueta({ children, tono = 'neutro' }: { children: ReactNode; tono?: Tono }) {
  const t = {
    neutro: 'bg-tinta/7 text-tenue',
    ok: 'bg-ok-fondo text-ok',
    pronto: 'bg-pronto-fondo text-pronto',
    atenta: 'bg-atenta-fondo text-atenta',
    pino: 'bg-rocio text-pino',
  }[tono]
  return <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-base font-bold ${t}`}>{children}</span>
}

/** Avance de la ficha, por campos: tres tramos, no un porcentaje. */
export function BarraCampos({ hechos, total = 3, className = '' }: { hechos: number; total?: number; className?: string }) {
  return (
    <div className={`flex gap-1.5 ${className}`} role="img" aria-label={`${hechos} de ${total} campos listos`}>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={`h-2.5 flex-1 rounded-full transition-colors duration-500 ${i < hechos ? 'bg-pino' : 'bg-tinta/10'}`} />
      ))}
    </div>
  )
}

export const HORIZONTE_DIAS = 30
export const posicionDia = (dias: number) => `${(Math.min(dias, HORIZONTE_DIAS) / HORIZONTE_DIAS) * 100}%`

/** Barra de días restantes sobre un horizonte de 30 días, con la marca del aviso a los 7. */
export function BarraDias({ dias, nivel, grosor = 'h-3' }: { dias: number; nivel: Nivel; grosor?: string }) {
  const pct = Math.max(2, Math.min(100, (Math.min(dias, HORIZONTE_DIAS) / HORIZONTE_DIAS) * 100))
  const color = { pronto: 'bg-pronto', atenta: 'bg-atenta', tranquila: 'bg-ok' }[nivel]
  return (
    <div className={`relative w-full rounded-full bg-tinta/8 ${grosor}`} aria-hidden>
      <div className={`h-full rounded-full ${color} transition-[width] duration-700 ease-calma`} style={{ width: `${pct}%` }} />
      {dias > HORIZONTE_DIAS && (
        <span className="absolute top-1/2 right-0 size-0 -translate-y-1/2 translate-x-full border-y-6 border-l-8 border-y-transparent border-l-ok" />
      )}
      <span className="absolute -inset-y-1 w-0.5 rounded-full bg-tinta/45" style={{ left: posicionDia(7) }} />
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
    'grid size-12 shrink-0 place-items-center rounded-xl bg-hoja text-pino ring-2 ring-inset ring-pino/70 hover:bg-rocio disabled:opacity-40'
  return (
    <div className="flex flex-col gap-2">
      <span id={id} className="font-bold">
        {etiqueta}
      </span>
      <div className="flex flex-wrap items-center gap-3" role="group" aria-labelledby={id}>
        <button type="button" className={btn} aria-label={`Menos: ${etiqueta}`} disabled={valor <= min} onClick={() => onCambio(Math.max(min, valor - paso))}>
          <Minus aria-hidden className="size-5" strokeWidth={2.5} />
        </button>
        <output aria-live="polite" className="cifras min-w-8 text-center text-3xl font-bold leading-none">
          {valor}
        </output>
        <button type="button" className={btn} aria-label={`Más: ${etiqueta}`} disabled={valor >= max} onClick={() => onCambio(Math.min(max, valor + paso))}>
          <Plus aria-hidden className="size-5" strokeWidth={2.5} />
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
  columnas = false,
  ayuda,
}: {
  leyenda: string
  opciones: { valor: T; texto: string; detalle?: string }[]
  valor: T | null
  onCambio: (v: T) => void
  nombre: string
  /** En varias columnas cuando hay ancho. */
  columnas?: boolean
  ayuda?: ReactNode
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 font-bold">{leyenda}</legend>
      {ayuda && <div className="-mt-1 mb-1 text-base text-tenue">{ayuda}</div>}
      <div className={`grid gap-2 ${columnas ? '@2xl:grid-cols-3' : ''}`}>
        {opciones.map((o) => {
          const on = o.valor === valor
          return (
            <label
              key={o.valor}
              className={`flex min-h-13 cursor-pointer items-start gap-3 rounded-xl px-4 py-3 ring-2 ring-inset transition-colors has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-pino ${
                on ? 'bg-rocio ring-pino' : 'bg-hoja ring-borde hover:ring-pino/40'
              }`}
            >
              <input type="radio" name={nombre} className="sr-only" checked={on} onChange={() => onCambio(o.valor)} />
              <span aria-hidden className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full ring-2 ring-inset ${on ? 'ring-pino' : 'ring-tenue'}`}>
                {on && <span className="size-3 rounded-full bg-pino" />}
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="font-bold leading-snug">{o.texto}</span>
                {o.detalle && <span className="text-sm text-tenue">{o.detalle}</span>}
              </span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

export function Chip({ activo, onClick, children }: { activo: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={activo}
      onClick={onClick}
      className={`inline-flex min-h-12 max-w-full items-center gap-2 rounded-full px-4 py-2 font-bold ring-2 ring-inset transition-colors ${
        activo ? 'bg-rocio text-pino ring-pino' : 'bg-hoja text-tenue ring-borde hover:ring-pino/40'
      }`}
    >
      <span aria-hidden className={`grid size-5 shrink-0 place-items-center rounded-sm ring-2 ring-inset ${activo ? 'ring-pino' : 'ring-tenue'}`}>
        {activo && <Check className="size-4 text-pino" strokeWidth={3} />}
      </span>
      <span className="min-w-0 break-words">{children}</span>
    </button>
  )
}

export function CampoTexto({
  etiqueta,
  ayuda,
  error,
  className = '',
  grande = false,
  ...resto
}: InputHTMLAttributes<HTMLInputElement> & { etiqueta: string; ayuda?: string; error?: string | null; grande?: boolean }) {
  const id = useId()
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="font-bold">
        {etiqueta}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={ayuda || error ? `${id}-a` : undefined}
        className={`min-h-12 w-full min-w-0 rounded-xl bg-hoja px-4 py-2.5 ring-2 ring-inset placeholder:text-tenue/80 focus-visible:ring-pino ${
          error ? 'ring-pronto' : 'ring-borde'
        } ${grande ? 'cifras text-2xl font-bold' : ''}`}
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

export function Nota({ titulo, children, tono = 'rocio', icono }: { titulo?: string; children: ReactNode; tono?: 'rocio' | 'atenta' | 'pronto' | 'ok'; icono?: ReactNode }) {
  const t = { rocio: 'bg-rocio', atenta: 'bg-atenta-fondo', pronto: 'bg-pronto-fondo', ok: 'bg-ok-fondo' }[tono]
  return (
    <div className={`flex gap-3 rounded-xl px-4 py-3 ${t}`}>
      {icono}
      <div className="min-w-0">
        {titulo && <p className="mb-0.5 font-bold">{titulo}</p>}
        <div className="text-base leading-relaxed">{children}</div>
      </div>
    </div>
  )
}

/** Error de un formulario: qué pasó y cómo seguir. */
export function MensajeError({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <p id={id} role="alert" className="font-bold text-pronto">
      {children}
    </p>
  )
}

/**
 * Logo de MATU: un corazón blanco dentro de un círculo del color de marca (directriz de Jorge).
 * El color sale del token `pino`: si el diseñador cambia la paleta, el logo cambia con ella.
 * `claro` invierte el círculo para usarlo sobre un fondo de marca.
 */
export function Logo({ className = 'size-10', claro = false }: { className?: string; claro?: boolean }) {
  return (
    <span aria-hidden className={`grid shrink-0 place-items-center rounded-full ${claro ? 'bg-white' : 'bg-marca'} ${className}`}>
      <Heart className={`size-3/5 ${claro ? 'fill-marca text-marca' : 'fill-white text-white'}`} strokeWidth={2} />
    </span>
  )
}

/** Marca con nombre: el logo y "MATU" en la cara de los titulares. */
export function Marca({ claro = false, className = '' }: { claro?: boolean; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <Logo claro={claro} className="size-9 shrink-0" />
      <span className="titular text-xl">MATU</span>
    </span>
  )
}

/** Título de una sección dentro de una página. */
export function Subtitulo({ children, id, className = '' }: { children: ReactNode; id?: string; className?: string }) {
  return (
    <h2 id={id} className={`text-xl font-bold leading-snug ${className}`}>
      {children}
    </h2>
  )
}

/** Renglón de una cuenta: concepto, puntos guía y monto alineado. */
export function Renglon({ texto, monto, fuerte = false, nota, tono }: { texto: ReactNode; monto: string; fuerte?: boolean; nota?: ReactNode; tono?: 'ok' | 'tenue' }) {
  return (
    <div className={`flex flex-col ${fuerte ? 'font-bold' : ''}`}>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="min-w-0 shrink">{texto}</span>
        <span aria-hidden className="min-w-4 flex-1 -translate-y-1 border-b-2 border-dotted border-tinta/20" />
        <span className={`cifras ml-auto shrink-0 ${fuerte ? 'text-xl' : ''} ${tono === 'ok' ? 'text-ok' : tono === 'tenue' ? 'text-tenue' : ''}`}>{monto}</span>
      </div>
      {nota && <span className="text-sm font-normal text-tenue">{nota}</span>}
    </div>
  )
}

// Piezas de interfaz de la app de la familia, copiadas de la demo aprobada (Demo/src/components/
// Ui.tsx, HojaFicha.tsx y TextoFicha.tsx; Demo/src/familia/Shell.tsx). Cambios: `pino` es
// `turquesa`, el borde de los controles es `borde`, el error lleva ícono y `Volver` mide 48 px.
import { useId, type InputHTMLAttributes, type ReactNode } from 'react'
import { Check, ChevronLeft, Circle, CircleAlert, Minus, Plus, TriangleAlert } from 'lucide-react'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { AVISO_CUIDADOR, CAMPOS } from './datos'
import { AUTORIZACION, FICHA } from './textos'
import { navegar, type Ruta } from './ruteo'
import type { CampoApi } from '../compartido/api/familia'
import { AVISO_REMEDIOS, TITULO_SECCION, type SeccionApi } from '../compartido/secciones'
export { Nota } from '../compartido/ui/Nota'

export function Acciones({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`flex flex-wrap items-center gap-x-5 gap-y-3 ${className}`}>{children}</div>
}

/** Título de cada pantalla: recibe el foco al cambiar de ruta (2.6). */
export function Titulo({ children, className = 'text-3xl @2xl/main:text-4xl' }: { children: ReactNode; className?: string }) {
  return (
    <h1 id="titulo-pagina" tabIndex={-1} className={`titular angosto:text-2xl outline-none ${className}`}>
      {children}
    </h1>
  )
}

export function Pagina({ titulo, bajada, antes, children }: { titulo: ReactNode; bajada?: ReactNode; antes?: ReactNode; children?: ReactNode }) {
  return (
    <>
      <div className="mb-7 flex flex-col gap-3">
        {antes}
        <div>
          <Titulo>{titulo}</Titulo>
          {bajada && <p className="mt-1.5 max-w-prose text-base text-tenue">{bajada}</p>}
        </div>
      </div>
      {children}
    </>
  )
}

/** Enlace de vuelta, de texto, 48 px en todos los tamaños. */
export function Volver({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="inline-flex min-h-12 items-center gap-1 self-start rounded-lg pr-2 font-bold text-turquesa hover:underline">
      <ChevronLeft aria-hidden className="size-5 shrink-0" />
      {children}
    </button>
  )
}

/**
 * En modo angosto el ícono va en la primera línea del texto, como una letra más: el texto usa todo
 * el ancho y un correo largo no se parte (revisión visual del #51, P2-2).
 */
export function MensajeError({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <p id={id} className="flex gap-1.5 angosto:block font-bold text-pronto">
      <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 angosto:mt-0 angosto:mr-1.5 angosto:inline angosto:align-middle" />
      <span className="min-w-0">{children}</span>
    </p>
  )
}

export function CampoTexto({
  etiqueta,
  ayuda,
  error,
  className = '',
  junto,
  ayudaGrande = false,
  ...resto
}: InputHTMLAttributes<HTMLInputElement> & {
  etiqueta: string
  ayuda?: ReactNode
  error?: string | null
  junto?: ReactNode
  /** MATU-48: la ayuda en `text-base` (nada relevante bajo 1 rem). */
  ayudaGrande?: boolean
}) {
  const id = useId()
  const describe = [ayuda ? `${id}-a` : '', error ? `${id}-e` : ''].filter(Boolean).join(' ') || undefined
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="font-bold">
        {etiqueta}
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <input
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={describe}
          className={`min-h-12 w-full min-w-0 flex-1 basis-40 rounded-xl bg-hoja px-4 py-2.5 ring-2 ring-inset placeholder:text-tenue disabled:opacity-60 focus-visible:ring-turquesa ${
            error ? 'ring-pronto' : 'ring-borde'
          }`}
          {...resto}
        />
        {junto}
      </div>
      {ayuda && (
        <span id={`${id}-a`} className={`${ayudaGrande ? 'text-base' : 'text-sm'} text-tenue`}>
          {ayuda}
        </span>
      )}
      {error && <MensajeError id={`${id}-e`}>{error}</MensajeError>}
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
  error,
  forma = 'lista',
  children,
}: {
  leyenda: string
  opciones: { valor: T; texto: string; detalle?: string }[]
  valor: T | null
  onCambio: (v: T) => void
  nombre: string
  columnas?: boolean
  error?: string | null
  /**
   * `chips` (de la demo, Demo/src/components/Ui.tsx): opción única con la piel del chip y un
   * indicador redondo con punto. Con `columnas`, 2 + 2 desde 20 rem; en angosto, una columna.
   */
  forma?: 'lista' | 'chips'
  children?: ReactNode
}) {
  const id = useId()
  if (forma === 'chips')
    return (
      <fieldset className="flex min-w-0 flex-col gap-2" aria-describedby={error ? `${id}-e` : undefined}>
        <legend className="mb-2 font-bold">{leyenda}</legend>
        <div className={columnas ? 'grid grid-cols-1 gap-2 @xs/main:grid-cols-2 angosto:grid-cols-1' : 'flex flex-wrap gap-2 angosto:flex-col'}>
          {opciones.map((o) => {
            const on = o.valor === valor
            return (
              <label
                key={o.valor}
                className={`${columnas ? 'flex w-full' : 'inline-flex max-w-full'} min-h-12 cursor-pointer items-center gap-2 rounded-full angosto:rounded-xl px-4 angosto:px-3 py-2 font-bold ring-2 ring-inset has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-turquesa ${
                  on ? 'bg-rocio text-turquesa ring-turquesa' : error ? 'bg-hoja text-tenue ring-pronto' : 'bg-hoja text-tenue ring-borde hover:ring-turquesa/40'
                }`}
              >
                <input type="radio" name={nombre} className="sr-only" checked={on} onChange={() => onCambio(o.valor)} />
                <span aria-hidden className={`grid size-5 shrink-0 place-items-center rounded-full ring-2 ring-inset ${on ? 'ring-turquesa' : 'ring-tenue'}`}>
                  {on && <span className="size-2.5 rounded-full bg-turquesa" />}
                </span>
                <span className="min-w-0 break-words hyphens-auto">{o.texto}</span>
              </label>
            )
          })}
        </div>
        {error && <MensajeError id={`${id}-e`}>{error}</MensajeError>}
        {children}
      </fieldset>
    )
  return (
    <fieldset className={`flex flex-col gap-2 ${columnas ? '' : 'max-w-xl'}`} aria-describedby={error ? `${id}-e` : undefined}>
      <legend className="mb-2 font-bold">{leyenda}</legend>
      <div className={`grid grid-cols-1 gap-2 ${columnas ? '@2xl/main:grid-cols-3' : ''}`}>
        {opciones.map((o) => {
          const on = o.valor === valor
          return (
            <label
              key={o.valor}
              className={`flex min-h-12 cursor-pointer items-start gap-3 angosto:flex-col angosto:gap-2 rounded-xl px-4 angosto:px-3 py-3 ring-2 ring-inset has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-turquesa ${
                on ? 'bg-rocio ring-turquesa' : error ? 'bg-hoja ring-pronto' : 'bg-hoja ring-borde hover:ring-turquesa/40'
              }`}
            >
              <input type="radio" name={nombre} className="sr-only" checked={on} onChange={() => onCambio(o.valor)} />
              <span aria-hidden className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full ring-2 ring-inset ${on ? 'ring-turquesa' : 'ring-tenue'}`}>
                {on && <span className="size-3 rounded-full bg-turquesa" />}
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="font-bold leading-snug">{o.texto}</span>
                {o.detalle && <span className="text-sm text-tenue">{o.detalle}</span>}
              </span>
            </label>
          )
        })}
      </div>
      {error && <MensajeError id={`${id}-e`}>{error}</MensajeError>}
      {children}
    </fieldset>
  )
}

/**
 * El aviso `aviso_cuidador_de_hecho` con su casilla, el mismo en la autorización de la ficha (alta y
 * MATU-44 5.1) y en el permiso de los insumos (MATU-36 3.1). En modo angosto el ícono va en la
 * primera línea del título, como en `MensajeError`: a 320 px con el texto al 200 % el título se
 * salía 2 px (revisión de MATU-44 del 07-11).
 */
export function AvisoCuidadorDeHecho({
  idTitulo,
  idError,
  leido,
  error,
  onLeido,
}: {
  idTitulo: string
  idError: string
  leido: boolean
  error: boolean
  onLeido: (leido: boolean) => void
}) {
  return (
    <section aria-labelledby={idTitulo} className="border-l-4 border-atenta bg-atenta-fondo">
      <h2 id={idTitulo} className="flex items-start gap-2 angosto:block px-5 angosto:px-2 pt-4 text-lg font-bold">
        <TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta angosto:mt-0 angosto:mr-1.5 angosto:inline angosto:align-middle" />
        <span className="min-w-0">{AVISO_CUIDADOR.titulo}</span>
      </h2>
      <div className="flex max-w-prose flex-col gap-2.5 px-5 angosto:px-2 pt-2 pb-4 leading-relaxed">
        {AVISO_CUIDADOR.parrafos.map((p) => (
          <p key={p.slice(0, 24)}>{p}</p>
        ))}
      </div>
      <label className="flex min-h-12 cursor-pointer items-center angosto:items-start gap-3 border-t border-linea bg-hoja/60 px-5 angosto:px-2 py-3 font-bold">
        <input
          type="checkbox"
          checked={leido}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? idError : undefined}
          onChange={(e) => onLeido(e.target.checked)}
          className="size-6 shrink-0 accent-turquesa angosto:mt-0.5"
        />
        {AUTORIZACION.leido}
      </label>
      {error && (
        <div className="px-5 angosto:px-2 pb-3">
          <MensajeError id={idError}>{AUTORIZACION.errLeido}</MensajeError>
        </div>
      )}
    </section>
  )
}

const TONO_ETIQUETA = { neutro: 'bg-tinta/7 text-tenue', ok: 'bg-ok-fondo text-ok', activo: 'bg-rocio text-turquesa', atenta: 'bg-atenta-fondo text-atenta' } as const

/** Siempre con ícono y palabra: el tono es un refuerzo, nunca lo único (MATU-48 4.5 y 5.3). */
export function Etiqueta({ children, tono = 'neutro' }: { children: ReactNode; tono?: keyof typeof TONO_ETIQUETA }) {
  const t = TONO_ETIQUETA[tono]
  return <span className={`inline-flex max-w-full shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-base font-bold ${t}`}>{children}</span>
}

/** Avance de la ficha, por campos: tres tramos, siempre con el texto al lado. */
export function BarraCampos({ hechos, className = '' }: { hechos: number; className?: string }) {
  return (
    <div aria-hidden className={`flex gap-1.5 ${className}`}>
      {[0, 1, 2].map((i) => (
        <span key={i} className={`h-2.5 flex-1 rounded-full ${i < hechos ? 'bg-turquesa' : 'bg-tinta/10'}`} />
      ))}
    </div>
  )
}

/** «hoy, HH:MM» o «DD/MM/AAAA, HH:MM», en la hora de Chile. Cada parte en su `cifras`. */
export function Cuando({ iso, className = '' }: { iso: string; className?: string }) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const { fecha, hora } = fechaYHoraDeChile(d)
  const hoy = fechaYHoraDeChile(new Date()).fecha === fecha
  return (
    <span className={`tabular-nums ${className}`}>
      <span className="cifras">{hoy ? 'hoy,' : `${fecha},`}</span> <span className="cifras">{hora}</span>
    </span>
  )
}

export const horaDe = (iso: string | null | undefined) => (iso && !Number.isNaN(new Date(iso).getTime()) ? fechaYHoraDeChile(new Date(iso)).hora : '')

/** La completitud del contrato (0, 33, 67, 100) en campos listos. */
export const camposListos = (completitud: number) => Math.max(0, Math.min(3, Math.round((completitud * 3) / 100)))

// ---------- La hoja de la ficha (HojaFicha y TextoFicha de la demo) ----------

export function Hoja({ children, etiqueta }: { children: ReactNode; etiqueta?: string }) {
  return (
    <div className="relative pt-3" role={etiqueta ? 'group' : undefined} aria-label={etiqueta}>
      <span aria-hidden className="absolute top-0 left-1/2 z-10 size-7 -translate-x-1/2 rounded-full bg-miel shadow-md" />
      <div className="rounded-sm bg-hoja px-4 angosto:px-2 @3xl/main:px-9 pt-7 pb-6 shadow-xl ring-1 ring-linea">{children}</div>
    </div>
  )
}

const HORA = /^\s*(\d{1,2})[:.](\d{2})\s*[-–·]?\s*(.*)$/

function separarHoras(texto: string): { hora: string; texto: string }[] | null {
  const lineas = texto.split('\n').map((l) => l.trim()).filter(Boolean)
  const conHora = lineas.map((l) => HORA.exec(l))
  if (!conHora.some(Boolean)) return null
  return lineas.map((l, i) => {
    const m = conHora[i]
    return m ? { hora: `${m[1].padStart(2, '0')}:${m[2]}`, texto: m[3] } : { hora: '', texto: l }
  })
}

/** Texto de un campo: siempre como texto, nunca HTML. "Su día" con horas, en línea de tiempo. */
export function TextoCampo({ texto }: { texto: string | null }) {
  if (!texto || !texto.trim()) return <p className="text-tenue italic">{FICHA.sinCompletar}</p>
  const horas = separarHoras(texto)
  if (horas)
    return (
      <div className="relative">
        <span aria-hidden className="absolute top-2 bottom-2 left-18 w-0.5 angosto:hidden rounded-full bg-miel/45" />
        <ol className="flex flex-col gap-3 pl-1">
          {horas.map((it, i) => (
            <li key={i} className="relative flex items-start gap-3 angosto:flex-col angosto:gap-1">
              <span className="cifras w-13 shrink-0 pt-px text-right angosto:w-auto angosto:text-left font-bold text-turquesa">{it.hora}</span>
              <span aria-hidden className="relative z-10 mt-1.5 angosto:hidden size-3 shrink-0 rounded-full bg-miel ring-4 ring-hoja" />
              <span className="min-w-0 break-words">{it.texto}</span>
            </li>
          ))}
        </ol>
      </div>
    )
  return (
    <div className="renglones leading-7">
      {texto.split('\n').map((l, i) => (
        <p key={i} className="break-words">
          {l || ' '}
        </p>
      ))}
    </div>
  )
}

export interface SeccionEnHoja {
  api: SeccionApi
  texto: string
}

export function HojaFicha({
  pila,
  textos,
  escribiendo,
  secciones = [],
}: {
  pila: string
  textos: Record<CampoApi, string | null>
  escribiendo?: CampoApi | null
  /** Las secciones agregadas, ya en el orden fijo (MATU-49, 3.2). */
  secciones?: SeccionEnHoja[]
}) {
  return (
    <Hoja etiqueta={`Hoja de la ficha de ${pila}`}>
      <p className="titular text-2xl @2xl/main:text-4xl angosto:text-xl">{FICHA.hojaDe(pila)}</p>
      {CAMPOS.map((c) => (
        <section key={c.api} className={`mt-5 ${escribiendo === c.api ? '-ml-3 border-l-4 border-miel pl-2' : ''}`}>
          <h3 className="mb-1 text-lg font-bold text-turquesa">{c.titulo}</h3>
          <TextoCampo texto={textos[c.api]} />
        </section>
      ))}
      <SeccionesEnHoja secciones={secciones} />
    </Hoja>
  )
}

/** 4.2: la hoja del editor de una sección muestra solo esa sección, como la verá el relevo. */
export function HojaSeccion({ pila, seccion, texto }: { pila: string; seccion: SeccionApi; texto: string }) {
  return (
    <Hoja etiqueta={`Hoja de la ficha de ${pila}`}>
      <p className="titular text-2xl @2xl/main:text-4xl angosto:text-xl">{FICHA.hojaDe(pila)}</p>
      {/* Sin campos arriba, la sección no lleva la línea separadora. */}
      <SeccionesEnHoja secciones={[{ api: seccion, texto }]} escribiendo sinSeparador />
    </Hoja>
  )
}

/** MATU-49, 7.1: tras los tres campos, una línea y cada sección con su título. Sin pregunta ni ejemplo. */
function SeccionesEnHoja({ secciones, escribiendo = false, sinSeparador = false }: { secciones: SeccionEnHoja[]; escribiendo?: boolean; sinSeparador?: boolean }) {
  if (!secciones.length) return null
  return (
    <div className={sinSeparador ? 'mt-5' : 'mt-8 border-t border-linea pt-6'}>
      {secciones.map((s, i) => (
        <section key={s.api} className={`${i ? 'mt-6' : ''} ${escribiendo ? '-ml-3 border-l-4 border-miel pl-2' : ''}`}>
          <h3 className="mb-1 text-lg font-bold text-turquesa">{TITULO_SECCION[s.api]}</h3>
          {s.api === 'remedios' && <AvisoRemedios className="mt-2 mb-2" />}
          <TextoSeccion texto={s.texto} className="renglones leading-7" />
        </section>
      ))}
    </div>
  )
}

/** 5.2: el aviso de Sus remedios en la tarjeta y en la hoja. Texto en la página, nunca tooltip. */
export function AvisoRemedios({ className = '', id }: { className?: string; id?: string }) {
  return (
    <p id={id} className={`border-s-4 border-atenta ps-3 text-base ${className}`}>
      {AVISO_REMEDIOS}
    </p>
  )
}

const HORAS_EN_TEXTO = /(\d{1,2}[:.]\d{2})/

/**
 * El texto de una sección, tal cual, renglón por renglón, con las horas en `cifras` (5.6). Nunca
 * como línea de tiempo ni como HTML.
 */
export function TextoSeccion({ texto, recortar = false, className = '' }: { texto: string; recortar?: boolean; className?: string }) {
  const partes = texto.split(HORAS_EN_TEXTO)
  return (
    <p className={`break-words whitespace-pre-line ${recortar ? 'line-clamp-3' : ''} ${className}`}>
      {partes.map((p, i) =>
        i % 2 ? (
          <span key={i} className="cifras">
            {p}
          </span>
        ) : (
          p
        ),
      )}
    </p>
  )
}

export function Listo({ listo }: { listo: boolean }) {
  return (
    <Etiqueta tono={listo ? 'ok' : 'neutro'}>
      {listo ? <Check aria-hidden className="size-4" strokeWidth={3} /> : <Circle aria-hidden className="size-3.5" strokeWidth={2.5} />}
      {listo ? FICHA.listo : FICHA.falta}
    </Etiqueta>
  )
}

// ---------------------------------------------------------------- MATU-48

/**
 * Las vistas de una sección (de `Pestanas` de Demo/src/familia/Shell.tsx), como enlaces. La activa
 * lleva borde inferior de 3 px y negrita, no solo color, y `aria-current`.
 */
export function Pestanas({ etiqueta, items }: { etiqueta: string; items: { texto: string; ruta: Ruta; activa: boolean }[] }) {
  return (
    <nav aria-label={etiqueta} className="border-b border-linea">
      <ul className="-mb-px flex flex-wrap gap-x-1">
        {items.map((t) => (
          <li key={t.ruta}>
            <a
              href={t.ruta}
              aria-current={t.activa ? 'page' : undefined}
              onClick={(e) => {
                e.preventDefault()
                navegar(t.ruta)
              }}
              className={`inline-flex min-h-12 items-center border-b-3 px-3 font-bold ${t.activa ? 'border-turquesa text-turquesa' : 'border-transparent text-tenue hover:text-tinta'}`}
            >
              {t.texto}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}

/** De la demo (Demo/src/components/Ui.tsx), con `turquesa` y la ayuda en `text-base`. */
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
  const btn = 'grid size-12 shrink-0 place-items-center rounded-xl bg-hoja text-turquesa ring-2 ring-inset ring-turquesa/80 hover:bg-rocio disabled:opacity-40'
  return (
    <div className="flex flex-col gap-2">
      <span id={id} className="font-bold">
        {etiqueta}
      </span>
      <div className="flex flex-wrap items-center gap-3" role="group" aria-labelledby={id} aria-describedby={ayuda ? `${id}-a` : undefined}>
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
      {ayuda && (
        <span id={`${id}-a`} className="text-base text-tenue">
          {ayuda}
        </span>
      )}
    </div>
  )
}

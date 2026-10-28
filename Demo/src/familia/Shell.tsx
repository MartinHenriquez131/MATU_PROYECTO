// Marco de la app de la familia: barra lateral persistente, encabezado con la persona cuidada y
// quien está conectada, y el contenido en columnas. Bajo 56 rem de ancho la barra lateral pasa
// a ser una fila arriba y las columnas se apilan: es el mismo layout, angosto.
import type { ReactNode } from 'react'
import { ChevronLeft, ClipboardList, House, Package, ShoppingBag, UsersRound } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { completados, nombrePila, pantallaFamilia, pilaFamilia, volverHasta } from '../demo/logica'
import { diaDeLaSemana, diasRestantes, fmtFecha, fmtHora, nivel } from '../demo/calculos'
import type { Estado, PantallaFamiliaId } from '../demo/tipos'
import { Marca } from '../components/Ui'

export type Seccion = 'inicio' | 'ficha' | 'insumos' | 'pedidos' | 'grupo'

export const SECCION_DE: Partial<Record<PantallaFamiliaId, Seccion>> = {
  inicio: 'inicio',
  ficha: 'ficha',
  completar: 'ficha',
  guardado: 'ficha',
  compartir: 'ficha',
  'enlace-pin': 'ficha',
  'quien-vio': 'ficha',
  enlaces: 'ficha',
  imprimir: 'ficha',
  conflicto: 'ficha',
  'se-acaba': 'insumos',
  declarar: 'insumos',
  agregar: 'insumos',
  'ya-compre': 'insumos',
  reponer: 'insumos',
  exportar: 'insumos',
  pedido: 'pedidos',
  rechazado: 'pedidos',
  seguimiento: 'pedidos',
  entregado: 'pedidos',
  grupo: 'grupo',
}

/** Cómo se nombra cada pantalla en "Volver a…". */
const NOMBRE: Partial<Record<PantallaFamiliaId, string>> = {
  bienvenida: 'la bienvenida',
  cuenta: 'Crear cuenta',
  entrar: 'Entrar',
  'a-quien': '¿A quién cuidas?',
  inicio: 'Inicio',
  ficha: 'la ficha',
  completar: 'el campo',
  compartir: 'Compartir',
  'quien-vio': 'Quién la vio',
  enlaces: 'Enlaces',
  imprimir: 'Para imprimir',
  'se-acaba': 'Insumos',
  reponer: 'la lista de reposición',
  pedido: 'tu pedido',
  seguimiento: 'el pedido',
  grupo: 'Grupo familiar',
}

function destinoPedidos(s: Estado): PantallaFamiliaId {
  const e = s.pedido?.estado
  if (e === 'confirmando' || e === 'apartado') return 'pedido'
  return e === 'entregado' ? 'entregado' : 'seguimiento'
}

/** `corto` es el rótulo de la barra inferior del teléfono (ESPEC-ADR-027, 7.6.1). */
const SECCIONES: { id: Seccion; texto: string; corto: string; Icono: typeof House; destino: (s: Estado) => PantallaFamiliaId }[] = [
  { id: 'inicio', texto: 'Inicio', corto: 'Inicio', Icono: House, destino: () => 'inicio' },
  { id: 'ficha', texto: 'Ficha de relevo', corto: 'Ficha', Icono: ClipboardList, destino: () => 'ficha' },
  { id: 'insumos', texto: 'Insumos', corto: 'Insumos', Icono: Package, destino: () => 'se-acaba' },
  { id: 'pedidos', texto: 'Pedidos', corto: 'Pedidos', Icono: ShoppingBag, destino: destinoPedidos },
  { id: 'grupo', texto: 'Grupo familiar', corto: 'Grupo', Icono: UsersRound, destino: () => 'grupo' },
]

type EstadoPista = { tipo: 'campos'; hechos: number } | { tipo: 'pronto' } | { tipo: 'curso' } | null

function estadoPista(s: Estado, seccion: Seccion): EstadoPista {
  if (seccion === 'ficha') {
    const h = completados(s)
    return h < 3 ? { tipo: 'campos', hechos: h } : null
  }
  if (seccion === 'insumos') {
    const pronto = s.insumos.filter((i) => i.declarado && nivel(diasRestantes(i)) === 'pronto').length
    return pronto ? { tipo: 'pronto' } : null
  }
  if (seccion === 'pedidos') {
    const e = s.pedido?.estado
    return e && ['pagado', 'preparando', 'listo', 'en_camino'].includes(e) ? { tipo: 'curso' } : null
  }
  return null
}

/**
 * Una pista de estado junto a cada sección: siempre con palabra. En el teléfono la palabra queda
 * para el lector de pantalla y se ve un punto sobre el ícono (`PuntoPista`).
 */
function Pista({ pista }: { pista: EstadoPista }) {
  if (!pista) return null
  if (pista.tipo === 'campos') return <span className="cifras text-base text-tenue telefono:sr-only angosto:basis-full angosto:ps-8">{pista.hechos} de 3</span>
  if (pista.tipo === 'pronto')
    return (
      <span className="inline-flex items-center gap-1 text-base font-bold text-pronto telefono:sr-only angosto:basis-full angosto:ps-8">
        <span aria-hidden className="size-2 rounded-full bg-current" />
        Pronto
      </span>
    )
  return <span className="text-base font-bold text-pino telefono:sr-only angosto:basis-full angosto:ps-8">En curso</span>
}

/** El punto sobre el ícono de la barra inferior: hay pista o no la hay, además del color. */
function PuntoPista({ pista }: { pista: EstadoPista }) {
  if (!pista) return null
  return (
    <span
      aria-hidden
      className={`absolute -top-0.5 -right-1 hidden size-2.5 rounded-full bg-current telefono:block ${pista.tipo === 'pronto' ? 'text-pronto' : 'text-pino'}`}
    />
  )
}

function Navegacion() {
  const { s, haz } = useDemo()
  const actual = SECCION_DE[pantallaFamilia(s).id]
  return (
    <nav
      aria-label="Secciones"
      className="telefono:fixed telefono:inset-x-0 telefono:bottom-0 telefono:z-20 telefono:border-t telefono:border-linea telefono:bg-hoja telefono:px-1 telefono:py-1"
    >
      <ul className="flex flex-wrap gap-1 @4xl/app:flex-col telefono:grid telefono:grid-cols-5 telefono:gap-1">
        {SECCIONES.map(({ id, texto, corto, Icono, destino }) => {
          const on = actual === id
          const pista = estadoPista(s, id)
          return (
            <li key={id} className="max-w-full min-w-0">
              <button
                type="button"
                aria-current={on ? 'page' : undefined}
                onClick={() => haz((x) => pilaFamilia(x, [destino(x)]))}
                className={`flex min-h-11 w-full flex-wrap items-center gap-x-3 gap-y-0.5 rounded-xl px-3 py-1 text-left @4xl/app:flex-nowrap telefono:min-h-14 telefono:flex-col telefono:flex-nowrap telefono:justify-center telefono:gap-0.5 telefono:px-1 telefono:text-center telefono:text-sm telefono:leading-tight ${
                  on ? 'bg-hoja font-bold text-pino ring-1 ring-linea telefono:bg-rocio telefono:ring-0' : 'text-tinta hover:bg-tinta/6'
                }`}
              >
                <span className="relative grid shrink-0">
                  <Icono aria-hidden className="size-5 shrink-0" strokeWidth={on ? 2.4 : 2} />
                  <PuntoPista pista={pista} />
                </span>
                <span className="min-w-0 flex-1 break-words @4xl/app:whitespace-nowrap telefono:flex-none">
                  <span className="telefono:hidden">{texto}</span>
                  <span className="hidden telefono:inline">{corto}</span>
                </span>
                <Pista pista={pista} />
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

function Encabezado() {
  const { s } = useDemo()
  const p = s.persona
  const nombre = s.cuenta?.nombre || 'Carmen'
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-linea px-4 @3xl:px-11 py-3">
      <p className="min-w-0">
        <span className="block text-sm text-tenue">Cuidas a</span>
        <span className="block text-lg font-bold leading-tight">{p?.nombre ?? nombrePila(s)}</span>
      </p>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
        <p className="text-base text-tenue tabular-nums">
          {diaDeLaSemana(s.ahora)} {fmtFecha(s.ahora)}, {fmtHora(s.ahora)}
        </p>
        <p className="flex items-center gap-2">
          <span aria-hidden className="grid size-9 place-items-center rounded-full bg-rocio font-bold text-pino">
            {nombre.slice(0, 1).toUpperCase()}
          </span>
          <span>
            <span className="sr-only">Conectada: </span>
            <span className="font-bold">{nombre}</span>
          </span>
        </p>
      </div>
    </header>
  )
}

export function ShellFamilia({ children }: { children: ReactNode }) {
  return (
    <div className="grid flex-1 @4xl/app:grid-cols-[16.5rem_minmax(0,1fr)]">
      <aside className="border-b border-linea px-3 py-3 telefono:py-2 @4xl/app:border-r @4xl/app:border-b-0 @4xl/app:py-5">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 @4xl/app:sticky @4xl/app:top-4 @4xl/app:flex-col @4xl/app:items-stretch @4xl/app:gap-7">
          <Marca className="px-2" />
          <Navegacion />
        </div>
      </aside>
      <div className="flex min-w-0 flex-col">
        <Encabezado />
        <main id="contenido" tabIndex={-1} className="@container/main flex-1 px-4 angosto:px-2 @3xl:px-11 pt-6 pb-16 telefono:pb-36 outline-none">
          <div className="mx-auto max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  )
}

// ---------- piezas de una página ----------

export function Pestanas({ items }: { items: { texto: string; activa: boolean; ir: () => void }[] }) {
  return (
    <nav aria-label="Vistas de esta sección" className="border-b border-linea">
      <ul className="-mb-px flex flex-wrap gap-x-1">
        {items.map((t) => (
          <li key={t.texto}>
            <button
              type="button"
              aria-current={t.activa ? 'page' : undefined}
              onClick={t.ir}
              className={`min-h-12 border-b-3 px-3 font-bold ${t.activa ? 'border-pino text-pino' : 'border-transparent text-tenue hover:text-tinta'}`}
            >
              {t.texto}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}

/** "Volver a…" con el nombre de la pantalla anterior de la pila. */
export function Volver() {
  const { s, haz } = useDemo()
  const pila = s.nav.familia
  if (pila.length < 2) return null
  const anterior = pila[pila.length - 2]
  return (
    <button
      type="button"
      onClick={() => haz((x) => volverHasta(x, pila.length - 2))}
      className="inline-flex min-h-10 telefono:min-h-12 items-center gap-1 self-start rounded-lg pr-2 font-bold text-pino hover:underline"
    >
      <ChevronLeft aria-hidden className="size-5" />
      Volver a {NOMBRE[anterior.id] ?? 'la pantalla anterior'}
    </button>
  )
}

export function Pagina({
  titulo,
  bajada,
  volver = false,
  pestanas,
  children,
}: {
  titulo: string
  bajada?: ReactNode
  volver?: boolean
  pestanas?: ReactNode
  children: ReactNode
}) {
  return (
    <>
      <div className="mb-7 flex flex-col gap-3">
        {volver && <Volver />}
        <div>
          <h1 id="titulo-pagina" tabIndex={-1} className="titular text-3xl @2xl:text-4xl outline-none">
            {titulo}
          </h1>
          {bajada && <p className="mt-1.5 max-w-prose text-base text-tenue">{bajada}</p>}
        </div>
        {pestanas}
      </div>
      {children}
    </>
  )
}

/** Dos columnas desde 46 rem de contenido: lo que se hace a la izquierda, el resultado a la derecha. */
export function Columnas({ children, izquierda = 'equilibrada' }: { children: ReactNode; izquierda?: 'equilibrada' | 'ancha' | 'angosta' }) {
  const g = {
    equilibrada: '@2xl/main:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]',
    ancha: '@2xl/main:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]',
    angosta: '@2xl/main:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]',
  }[izquierda]
  return <div className={`grid grid-cols-1 items-start gap-x-6 @3xl:gap-x-16 gap-y-10 ${g}`}>{children}</div>
}

/** Una columna que es contenedor: sus piezas se acomodan a su propio ancho. */
export function Columna({ children, className = '', etiqueta }: { children: ReactNode; className?: string; etiqueta?: string }) {
  return (
    <section aria-label={etiqueta} className={`@container flex min-w-0 flex-col gap-5 ${className}`}>
      {children}
    </section>
  )
}

// Esqueleto de cada pantalla: encabezado con volver, cuerpo con desplazamiento y pie
// con las acciones al alcance del pulgar.
import { useEffect, useRef, type ReactNode } from 'react'
import { ChevronLeft, ClipboardList, House, Package, ShoppingBag } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { pantallaFamilia, pilaFamilia, volver } from '../demo/logica'
import type { PantallaFamiliaId } from '../demo/tipos'

let primeraPantalla = true

export function Pantalla({
  titulo,
  children,
  pie,
  sinVolver = false,
  encabezado,
  cuerpoClase = '',
}: {
  titulo: string
  children: ReactNode
  pie?: ReactNode
  sinVolver?: boolean
  encabezado?: ReactNode
  cuerpoClase?: string
}) {
  const { s, haz } = useDemo()
  const h1 = useRef<HTMLHeadingElement>(null)
  const pila = s.rol === 'comercio' ? s.nav.comercio : s.nav.familia
  const puedeVolver = !sinVolver && pila.length > 1

  // Al cambiar de pantalla, el foco va al título: así un lector de pantalla anuncia dónde está.
  useEffect(() => {
    if (primeraPantalla) {
      primeraPantalla = false
      return
    }
    h1.current?.focus({ preventScroll: true })
  }, [])

  return (
    <div className="flex h-full min-h-0 flex-col">
      {encabezado ?? (
        <header className="flex min-h-15 shrink-0 items-center gap-1 border-b border-linea bg-hoja/90 px-2 backdrop-blur">
          {puedeVolver ? (
            <button
              type="button"
              onClick={() => haz(volver)}
              aria-label="Volver"
              className="grid size-12 shrink-0 place-items-center rounded-full text-pino hover:bg-rocio"
            >
              <ChevronLeft aria-hidden className="size-7" />
            </button>
          ) : (
            <span className="w-3" />
          )}
          <h1 ref={h1} tabIndex={-1} className="min-w-0 py-2 font-display text-[1.2rem] font-bold leading-tight tracking-[-0.01em] outline-none">
            {titulo}
          </h1>
        </header>
      )}
      {encabezado && (
        <h1 ref={h1} tabIndex={-1} className="sr-only">
          {titulo}
        </h1>
      )}
      <div className={`min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pt-5 pb-6 ${cuerpoClase}`}>
        <div className="flex flex-col gap-4">{children}</div>
      </div>
      {pie && <div className="flex shrink-0 flex-col gap-2.5 border-t border-linea bg-hoja px-5 pt-3 pb-4">{pie}</div>}
      <BarraPestanas />
    </div>
  )
}

const PESTANAS: { id: PantallaFamiliaId; texto: string; Icono: typeof House; raices: PantallaFamiliaId[] }[] = [
  { id: 'inicio', texto: 'Inicio', Icono: House, raices: ['inicio'] },
  { id: 'ficha', texto: 'Ficha', Icono: ClipboardList, raices: ['ficha'] },
  { id: 'se-acaba', texto: 'Insumos', Icono: Package, raices: ['se-acaba'] },
  { id: 'reponer', texto: 'Pedido', Icono: ShoppingBag, raices: ['reponer', 'seguimiento', 'entregado'] },
]

function BarraPestanas() {
  const { s, haz } = useDemo()
  if (s.rol !== 'familia' || s.nav.familia.length !== 1) return null
  const actual = pantallaFamilia(s).id
  if (!PESTANAS.some((p) => p.raices.includes(actual))) return null
  const destinoPedido = (): PantallaFamiliaId => {
    const e = s.pedido?.estado
    if (!e || e === 'borrador') return 'reponer'
    return e === 'entregado' ? 'entregado' : 'seguimiento'
  }
  return (
    <nav aria-label="Secciones" className="shrink-0 border-t border-linea bg-hoja px-2 pt-1 pb-2">
      <ul className="flex">
        {PESTANAS.map(({ id, texto, Icono, raices }) => {
          const on = raices.includes(actual)
          return (
            <li key={id} className="min-w-0 flex-1">
              <button
                type="button"
                aria-current={on ? 'page' : undefined}
                onClick={() => haz((x) => pilaFamilia(x, [id === 'reponer' ? destinoPedido() : id]))}
                className={`flex min-h-14 w-full flex-col items-center justify-center gap-0.5 rounded-2xl px-1 text-[0.8rem] font-bold ${
                  on ? 'text-pino' : 'text-tenue hover:text-tinta'
                }`}
              >
                <span className={`grid h-8 w-14 max-w-full place-items-center rounded-full transition-colors ${on ? 'bg-rocio' : ''}`}>
                  <Icono aria-hidden className="size-5.5" strokeWidth={on ? 2.4 : 2} />
                </span>
                <span className="max-w-full truncate">{texto}</span>
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

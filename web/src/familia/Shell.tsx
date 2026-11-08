// El esqueleto de la app de la familia (especificación 2), copiado de `ShellFamilia` y
// `Navegacion` de la demo (Demo/src/familia/Shell.tsx). Cambios: tres secciones, el distintivo del
// piloto, la persona con su selector y «Salir»; sin fecha ni «Conectada: Carmen» (D5). MATU-44 (P1)
// suma Grupo familiar, la cuarta sección, visible para todos los roles.
import { useId, useState, type ReactNode } from 'react'
import { ChevronDown, ClipboardList, LogOut, Package, Share2, UserRound, Users } from 'lucide-react'
import { Boton } from '../compartido/ui/Boton'
import { DistintivoPiloto, Marca } from '../compartido/ui/Marca'
import { listarPersonas, nombrePilaDe } from '../compartido/api/familia'
import { camposListos } from './ui'
import { puedeCompartir, puedeVerFicha, useFamilia } from './estado'
import { navegar, useRuta, type Ruta } from './ruteo'
import { CUENTA_PROPIA, MARCO } from './textos'
import { GRUPO_FAMILIAR } from './textosGrupo'

type Seccion = 'ficha' | 'insumos' | 'compartir' | 'grupo'

const SECCIONES: { id: Seccion; texto: string; corto: string; Icono: typeof Package; ruta: Ruta }[] = [
  { id: 'ficha', texto: 'Ficha de relevo', corto: 'Ficha', Icono: ClipboardList, ruta: '/ficha' },
  { id: 'insumos', texto: 'Insumos', corto: 'Insumos', Icono: Package, ruta: '/insumos' },
  { id: 'compartir', texto: 'Compartir', corto: 'Compartir', Icono: Share2, ruta: '/compartir' },
  { id: 'grupo', texto: GRUPO_FAMILIAR.titulo, corto: GRUPO_FAMILIAR.corto, Icono: Users, ruta: '/grupo' },
]

const seccionDe = (ruta: string): Seccion | null =>
  ruta.startsWith('/ficha')
    ? 'ficha'
    : ruta.startsWith('/insumos')
      ? 'insumos'
      : ruta.startsWith('/compartir')
        ? 'compartir'
        : ruta === '/grupo' || ruta.startsWith('/grupo/')
          ? 'grupo'
          : null

/** Pista de la sección, siempre con palabra. En el teléfono queda para el lector de pantalla. */
function Pista({ seccion }: { seccion: Seccion }) {
  const { ficha } = useFamilia()
  // La pista de Insumos la pone MATU-36.
  if (seccion !== 'ficha' || !ficha) return null
  return <span className="cifras text-base text-tenue telefono:sr-only angosto:basis-full angosto:ps-8">{camposListos(ficha.completitud)} de 3</span>
}

function Navegacion() {
  const ruta = useRuta()
  const { rol, grupo } = useFamilia()
  const actual = seccionDe(ruta)
  const visibles = SECCIONES.filter((s) => (s.id === 'ficha' ? puedeVerFicha(rol, grupo) : s.id === 'compartir' ? puedeCompartir(rol) : true))
  const columnas = { 1: 'telefono:grid-cols-1', 2: 'telefono:grid-cols-2', 3: 'telefono:grid-cols-3', 4: 'telefono:grid-cols-4' }[visibles.length] ?? 'telefono:grid-cols-4'
  return (
    <nav
      aria-label={MARCO.secciones}
      className="telefono:fixed telefono:inset-x-0 telefono:bottom-0 telefono:z-20 telefono:border-t telefono:border-linea telefono:bg-hoja telefono:px-1 telefono:py-1"
    >
      <ul className={`flex flex-wrap gap-1 angosto:flex-col @4xl/app:flex-col telefono:grid ${columnas} telefono:gap-1`}>
        {visibles.map(({ id, texto, corto, Icono, ruta: destino }) => {
          const on = actual === id
          return (
            <li key={id} className="max-w-full min-w-0">
              <a
                href={destino}
                aria-current={on ? 'page' : undefined}
                onClick={(e) => {
                  e.preventDefault()
                  navegar(destino)
                }}
                className={`flex min-h-12 w-full flex-wrap items-center gap-x-3 gap-y-0.5 rounded-xl px-3 py-1 text-left @4xl/app:flex-nowrap telefono:min-h-14 telefono:flex-col telefono:flex-nowrap telefono:justify-center telefono:gap-0.5 telefono:px-1 telefono:text-center telefono:text-sm telefono:leading-tight ${
                  on ? 'bg-hoja font-bold text-turquesa ring-1 ring-linea telefono:bg-rocio telefono:ring-0' : 'text-tinta hover:bg-tinta/6'
                }`}
              >
                <Icono aria-hidden className="size-5 shrink-0" strokeWidth={on ? 2.4 : 2} />
                <span className="flex-1 @4xl/app:whitespace-nowrap telefono:flex-none">
                  <span className="telefono:hidden">{texto}</span>
                  <span className="hidden telefono:inline">{corto}</span>
                </span>
                <Pista seccion={id} />
              </a>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

/** 2.3: con más de un grupo o persona, un botón que abre una lista en el flujo de la página. */
function Persona() {
  const { grupos, grupo, persona, personas, rol, elegir } = useFamilia()
  const [abierto, setAbierto] = useState(false)
  const [listas, setListas] = useState<Record<string, typeof personas>>({})
  const id = useId()
  const ruta = useRuta()
  if (!persona) return null
  const varios = grupos.length > 1 || personas.length > 1

  const abrir = async () => {
    if (abierto) return setAbierto(false)
    setAbierto(true)
    // Las personas de los otros grupos se piden al abrir (con su propio X-Grupo-Id).
    if (grupos.length > 1) {
      const pares = await Promise.all(grupos.map(async (g) => [g.id, g.id === grupo?.id ? personas : await listarPersonas(g.id).catch(() => [])] as const))
      setListas(Object.fromEntries(pares))
    }
  }

  const cambiar = async (grupoId: string, personaId: string) => {
    setAbierto(false)
    await elegir(grupoId, personaId)
    const seccion = seccionDe(ruta)
    // MATU-59 (2.2): el catálogo no cambia con la persona, así que la ruta se mantiene.
    if (ruta === '/insumos/catalogo') navegar('/insumos/catalogo', { reemplazar: true })
    else navegar(seccion === 'ficha' ? '/ficha' : seccion === 'compartir' ? '/compartir' : seccion === 'insumos' ? '/insumos' : seccion === 'grupo' ? '/grupo' : '/', { reemplazar: true })
    window.setTimeout(() => document.getElementById('titulo-pagina')?.focus(), 0)
  }

  const opciones = (grupoId: string, lista: typeof personas, rolGrupo: string) => (
    <div className="flex flex-col gap-2">
      {lista.map((p) => {
        const on = p.id === persona.id && grupoId === grupo?.id
        return (
          <label
            key={p.id}
            className={`flex min-h-12 cursor-pointer items-start gap-3 rounded-xl px-4 py-2.5 ring-2 ring-inset has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-turquesa ${
              on ? 'bg-rocio ring-turquesa' : 'bg-hoja ring-borde'
            }`}
          >
            <input type="radio" name={`${id}-persona`} className="sr-only" checked={on} onChange={() => void cambiar(grupoId, p.id)} />
            <span aria-hidden className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full ring-2 ring-inset ${on ? 'ring-turquesa' : 'ring-tenue'}`}>
              {on && <span className="size-3 rounded-full bg-turquesa" />}
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="font-bold">{p.nombre}</span>
              {(rolGrupo === 'admin' || rolGrupo === 'cuidador') && 'nombre_pila' in p && (
                <span className="text-sm text-tenue">{MARCO.leDicen(nombrePilaDe(p))}</span>
              )}
            </span>
          </label>
        )
      })}
    </div>
  )

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <p className="min-w-0">
        <span className="block text-sm text-tenue">{MARCO.cuidasA}</span>
        {varios ? (
          <button
            type="button"
            aria-expanded={abierto}
            aria-controls={`${id}-lista`}
            onClick={() => void abrir()}
            className="inline-flex min-h-12 max-w-full items-center gap-1.5 rounded-lg text-left text-lg font-bold leading-tight hover:underline"
          >
            <span className="min-w-0 break-words">{persona.nombre}</span>
            <ChevronDown aria-hidden className={`size-5 shrink-0 ${abierto ? 'rotate-180' : ''}`} />
          </button>
        ) : (
          <span className="block text-lg font-bold leading-tight">{persona.nombre}</span>
        )}
      </p>
      {varios && abierto && (
        <div id={`${id}-lista`} className="flex max-w-md flex-col gap-4 pb-2">
          {grupos.length > 1
            ? grupos.map((g) => (
                <fieldset key={g.id} className="flex flex-col gap-2">
                  <legend className="mb-1 font-bold">{g.nombre}</legend>
                  {/* MATU-72 4.1: el grupo elegido, siempre desde la memoria: una persona borrada no queda en la lista pedida al abrir. */}
                  {opciones(g.id, g.id === grupo?.id ? personas : (listas[g.id] ?? []), g.rol)}
                </fieldset>
              ))
            : opciones(grupo!.id, personas, rol)}
        </div>
      )}
    </div>
  )
}

function Encabezado() {
  const { salir, fijar } = useFamilia()
  const ruta = useRuta()
  const enCuenta = ruta.startsWith('/cuenta')
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-linea px-4 angosto:px-2 @3xl/app:px-11 py-3">
      <Persona />
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
        <span className="hidden @4xl/app:contents">
          <DistintivoPiloto />
        </span>
        {/* MATU-57 D5: «Tu cuenta», con el celular y su confirmación. */}
        <a
          href="/cuenta"
          aria-current={enCuenta ? 'page' : undefined}
          onClick={(e) => {
            e.preventDefault()
            fijar({ celularDesde: 'cuenta' })
            navegar('/cuenta')
          }}
          className={`inline-flex min-h-12 items-center gap-2 rounded-xl px-3 font-bold text-turquesa ${enCuenta ? 'bg-rocio' : 'underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa'}`}
        >
          <UserRound aria-hidden className="size-5 shrink-0 angosto:hidden" />
          {CUENTA_PROPIA.menu}
        </a>
        <Boton variante="texto" icono={<LogOut aria-hidden className="size-5" />} onClick={() => void salir()}>
          {MARCO.salir}
        </Boton>
      </div>
    </header>
  )
}

export function ShellFamilia({ children }: { children: ReactNode }) {
  return (
    <div className="grid flex-1 @4xl/app:grid-cols-[16.5rem_minmax(0,1fr)]">
      <a href="#contenido" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-30 focus:rounded-lg focus:bg-hoja focus:px-4 focus:py-3 focus:font-bold">
        {MARCO.saltar}
      </a>
      <aside className="border-b border-linea bg-papel px-3 py-3 telefono:py-2 @4xl/app:border-r @4xl/app:border-b-0 @4xl/app:py-5">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 @4xl/app:sticky @4xl/app:top-4 @4xl/app:flex-col @4xl/app:items-stretch @4xl/app:gap-7">
          <span className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <Marca className="px-2" />
            <DistintivoPiloto className="@4xl/app:hidden" />
          </span>
          <Navegacion />
        </div>
      </aside>
      <div className="flex min-w-0 flex-col">
        <Encabezado />
        <main id="contenido" tabIndex={-1} className="@container/main flex-1 px-4 angosto:px-2 @3xl/app:px-11 pt-6 pb-16 telefono:pb-36 outline-none">
          <div className="mx-auto max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  )
}

/** Marco mientras abre la app (3.1): marca y distintivo, sin navegación. */
export function MarcoSimple({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-linea px-4 angosto:px-2 @3xl/app:px-11 py-3">
        <Marca />
        <DistintivoPiloto className="ms-auto" />
      </header>
      <main id="contenido" tabIndex={-1} className="@container/main flex-1 px-4 angosto:px-2 @3xl/app:px-11 pt-6 pb-16 outline-none">
        <div className="mx-auto max-w-7xl">{children}</div>
      </main>
    </>
  )
}


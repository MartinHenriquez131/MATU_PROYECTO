// Marco común (especificación 2.1 y 2.2): cabecera no fija con la marca, el nombre de la página y
// el distintivo del piloto, y el `main` donde va la pantalla del momento. Sin pie ni navegación.
import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { DistintivoPiloto, Logo } from '../compartido/ui/Marca'
import { CABECERA } from './textos'

export function Marco({ ocupado, children }: { ocupado: boolean; children: ReactNode }) {
  return (
    <>
      <header className="border-b border-linea bg-hoja">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 angosto:px-2 @3xl/app:px-10 py-3">
          <span className="flex items-center gap-2.5">
            <Logo className="size-8" />
            <span className="titular text-xl">{CABECERA.marca}</span>
          </span>
          <span className="text-tenue">{CABECERA.pagina}</span>
          <DistintivoPiloto className="ms-auto" />
        </div>
      </header>
      <main
        id="contenido"
        tabIndex={-1}
        aria-busy={ocupado || undefined}
        className="@container/main px-4 angosto:px-2 @3xl/app:px-10 pt-6 @3xl/app:pt-14 pb-16 outline-none"
      >
        {children}
      </main>
    </>
  )
}

/** Patrón "una sola columna centrada" (2.3). */
export function Columna({ children }: { children: ReactNode }) {
  return <div className="mx-auto flex max-w-xl flex-col items-center gap-6 text-center">{children}</div>
}

const TONOS_BALDOSA = {
  rocio: 'bg-rocio text-turquesa',
  neutra: 'bg-tinta/7 text-tenue',
  pronto: 'bg-pronto-fondo text-pronto',
}

/** Baldosa del momento: decorativa, el título dice lo mismo. */
export function Baldosa({ icono: Icono, tono }: { icono: LucideIcon; tono: keyof typeof TONOS_BALDOSA }) {
  return (
    <span className={`grid size-14 @md/main:size-18 place-items-center rounded-2xl ${TONOS_BALDOSA[tono]}`}>
      <Icono aria-hidden className="size-8 @md/main:size-10" />
    </span>
  )
}

/** Título de cada pantalla: recibe el foco al cambiar de momento (2.4). */
export function Titulo({ children }: { children: ReactNode }) {
  return (
    <h1 id="titulo-pagina" tabIndex={-1} className="titular text-3xl @2xl/main:text-5xl angosto:text-2xl outline-none">
      {children}
    </h1>
  )
}

// El índice de /privacidad (MATU-75, especificación docs/diseno/matu-75-privacidad.md), sacado a un
// componente por MATU-54 (especificación 6) para usarlo también en «Datos de…» y «Tus datos». Las
// clases no cambian: en el teléfono y con el texto al 200 % es un `details` cerrado; en pantalla
// ancha, una columna fija que sigue a la vista.
//
// Con `alElegir`, el enlace no cambia la dirección: la pantalla lleva la vista y el foco a la
// sección (en la app, nada de lo que se ve va a la URL, C26). Sin él, el ancla del navegador.
import type { Ref } from 'react'
import { ChevronDown } from 'lucide-react'

export interface EntradaIndice {
  id: string
  texto: string
}

export function ListaIndice({ entradas, alElegir }: { entradas: EntradaIndice[]; alElegir?: (id: string) => void }) {
  return (
    // `role="list"`: Safari quita la semántica de lista cuando no hay viñetas.
    <ul role="list" className="flex flex-col">
      {entradas.map((e) => (
        <li key={e.id}>
          <a
            href={`#${e.id}`}
            onClick={
              alElegir
                ? (ev) => {
                    ev.preventDefault()
                    alElegir(e.id)
                  }
                : undefined
            }
            className="flex min-h-12 items-center rounded-lg px-3 angosto:px-2 py-2 text-base leading-snug text-turquesa hover:bg-rocio hover:underline"
          >
            {e.texto}
          </a>
        </li>
      ))}
    </ul>
  )
}

/** Teléfono y texto al 200 %: el índice cerrado, que se abre al tocarlo. */
export function IndiceDesplegable({
  titulo,
  entradas,
  alElegir,
  detalles,
  resumen,
  id = 'indice',
  className = 'mt-6',
}: {
  titulo: string
  entradas: EntradaIndice[]
  alElegir?: (id: string) => void
  detalles?: Ref<HTMLDetailsElement>
  resumen?: Ref<HTMLElement>
  id?: string
  className?: string
}) {
  return (
    <details id={id} ref={detalles} className={`group ${className} rounded-xl bg-hoja ring-1 ring-linea @4xl/main:hidden`}>
      <summary
        ref={resumen}
        className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-2 px-4 angosto:px-2 font-bold text-turquesa [&::-webkit-details-marker]:hidden"
      >
        {titulo}
        <ChevronDown aria-hidden className="size-5 shrink-0 group-open:rotate-180" />
      </summary>
      <nav aria-label={titulo} className="px-4 angosto:px-2 pb-3">
        <ListaIndice entradas={entradas} alElegir={alElegir} />
      </nav>
    </details>
  )
}

/** Pantalla ancha: columna fija a la izquierda, que sigue a la vista al desplazarse. */
export function IndiceAncho({ titulo, entradas, alElegir, idTitulo = 'indice-ancho-t' }: { titulo: string; entradas: EntradaIndice[]; alElegir?: (id: string) => void; idTitulo?: string }) {
  return (
    <nav aria-labelledby={idTitulo} className="sticky top-6 hidden max-h-[calc(100dvh-3rem)] self-start overflow-y-auto [scrollbar-width:thin] @4xl/main:block">
      <h2 id={idTitulo} className="px-3 text-base font-bold text-tenue">
        {titulo}
      </h2>
      <ListaIndice entradas={entradas} alElegir={alElegir} />
    </nav>
  )
}

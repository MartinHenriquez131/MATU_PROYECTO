// El contenido de un campo (3.11.2). Siempre como texto, nunca como HTML. Los teléfonos no se
// vuelven enlaces.
import { CircleDashed } from 'lucide-react'
import { FICHA } from './textos'

// Una línea que empieza con una hora: 8:00, 08:00 u 8.00, con o sin guion después.
const HORA = /^\s*(\d{1,2})[:.](\d{2})\s*[-–·]?\s*(.*)$/

export function separarHoras(texto: string): { hora: string; texto: string }[] | null {
  const lineas = texto
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
  const conHora = lineas.map((l) => HORA.exec(l))
  if (!conHora.some(Boolean)) return null
  return lineas.map((l, i) => {
    const m = conHora[i]
    return m ? { hora: `${m[1].padStart(2, '0')}:${m[2]}`, texto: m[3] } : { hora: '', texto: l }
  })
}

export function TextoCampo({ texto }: { texto: string | null }) {
  if (texto === null || !texto.trim()) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-tinta/7 px-2.5 py-0.5 text-base font-bold text-tenue">
        <CircleDashed aria-hidden className="size-4 shrink-0" />
        {FICHA.sinCompletar}
      </span>
    )
  }
  const horas = separarHoras(texto)
  if (horas) return <LineaDeTiempo items={horas} />
  return (
    <div className="renglones max-w-prose text-lg leading-7">
      {texto.split('\n').map((l, i) =>
        l.trim() ? (
          <p key={i}>{l}</p>
        ) : (
          // Un renglón en blanco del texto se respeta como renglón en blanco.
          <p key={i} aria-hidden>
            {' '}
          </p>
        ),
      )}
    </div>
  )
}

function LineaDeTiempo({ items }: { items: { hora: string; texto: string }[] }) {
  return (
    <div className="relative">
      <span aria-hidden className="absolute top-2 bottom-2 left-18 w-0.5 rounded-full bg-miel/45" />
      <ol className="flex flex-col gap-3 pl-1">
        {items.map((it, i) => (
          <li key={i} className="relative flex items-start gap-3">
            <span className="cifras w-13 shrink-0 pt-px text-right font-bold text-turquesa">{it.hora}</span>
            <span aria-hidden className="relative z-10 mt-1.5 size-3 shrink-0 rounded-full bg-miel ring-4 ring-hoja" />
            <span className="min-w-0 text-lg">{it.texto}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

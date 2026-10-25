// Cómo se muestra el texto de un campo: "Su día" con horas se vuelve línea de tiempo.
const HORA = /^\s*(\d{1,2})[:.](\d{2})\s*[-–·]?\s*(.*)$/

export function separarHoras(texto: string): { hora: string; texto: string }[] | null {
  const lineas = texto.split('\n').map((l) => l.trim()).filter(Boolean)
  const conHora = lineas.map((l) => HORA.exec(l))
  if (!conHora.some(Boolean)) return null
  return lineas.map((l, i) => {
    const m = conHora[i]
    return m ? { hora: `${m[1].padStart(2, '0')}:${m[2]}`, texto: m[3] } : { hora: '', texto: l }
  })
}

export function LineaDeTiempo({ items }: { items: { hora: string; texto: string }[] }) {
  return (
    <div className="relative">
      <span aria-hidden className="absolute top-2 bottom-2 left-[4.5rem] w-0.5 rounded-full bg-miel/45" />
      <ol className="flex flex-col gap-3 pl-1">
      {items.map((it, i) => (
        <li key={i} className="relative flex items-start gap-3">
          <span className="cifras w-[3.2rem] shrink-0 pt-px text-right font-bold text-pino">{it.hora}</span>
          <span aria-hidden className="relative z-10 mt-1.5 size-3 shrink-0 rounded-full bg-miel ring-4 ring-hoja" />
          <span className="min-w-0 break-words">{it.texto}</span>
        </li>
      ))}
      </ol>
    </div>
  )
}

/** Texto de un campo. En la hoja, el texto corrido va sobre renglones; "Su día" con horas, en línea de tiempo. */
export function TextoCampo({ texto, vacio = 'Sin completar', renglones = false }: { texto: string; vacio?: string; renglones?: boolean }) {
  if (!texto.trim()) return <p className="text-tenue italic">{vacio}</p>
  const horas = separarHoras(texto)
  if (horas) return <LineaDeTiempo items={horas} />
  return (
    <div className={renglones ? 'renglones leading-[1.75rem]' : 'flex flex-col gap-1.5'}>
      {texto.split('\n').map((l, i) => (
        <p key={i} className="break-words">
          {l}
        </p>
      ))}
    </div>
  )
}

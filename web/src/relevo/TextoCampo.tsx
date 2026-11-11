// El contenido de un campo (3.11.2). Siempre como texto, nunca como HTML. Los teléfonos no se
// vuelven enlaces, pero no se parten (3.11.4).
import { CircleDashed } from 'lucide-react'
import { Fragment, type ReactNode } from 'react'
import { trozosConTelefonos } from './telefonos'
import { FICHA } from './textos'

/**
 * 3.11.4: cada teléfono reconocido va en un `inline-block` con dos `cifras`, el prefijo y el resto.
 * Baja entero de renglón y, solo si es más ancho que un renglón, se corta entre esas dos partes,
 * en el espacio de la familia o en el `<wbr>` que va tras un guion o donde no hay separador.
 * No agrega ni quita caracteres: el `textContent` es la línea tal cual. Sin `tel:` ni `aria-*`.
 */
export function ConTelefonos({ texto, pintarTexto = (t) => t }: { texto: string; pintarTexto?: (t: string) => ReactNode }) {
  return trozosConTelefonos(texto).map((t, i) =>
    t.tipo === 'texto' ? (
      <Fragment key={i}>{pintarTexto(t.texto)}</Fragment>
    ) : (
      <span key={i} className="inline-block max-w-full tabular-nums">
        {/* La puntuación pegada va dentro de las cifras: el renglón no se corta entre el número y
            su «(» o su «).» (3.11.4 v1.3). Firefox no corta tras un guion seguido de un dígito
            (UAX 14, LB25): el <wbr> da el corte, sin agregar un carácter. */}
        <span className="cifras">
          {t.abre}
          {t.prefijo}
        </span>
        {t.separador}
        {t.separador !== ' ' && <wbr />}
        <span className="cifras">
          {t.resto}
          {t.cierra}
        </span>
      </span>
    ),
  )
}

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
          <p key={i}>
            <ConTelefonos texto={l} />
          </p>
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

const HORAS_EN_TEXTO = /(\d{1,2}[:.]\d{2})/

/**
 * Una sección complementaria (MATU-49, 7.1 y 5.6): el texto tal cual, renglón por renglón, nunca
 * como línea de tiempo ni como HTML. Las horas van en `cifras` para que no se partan.
 */
export function TextoSeccion({ texto }: { texto: string }) {
  return (
    <div className="renglones max-w-prose text-lg leading-7">
      {texto.split('\n').map((l, i) =>
        l.trim() ? (
          <p key={i}>
            {/* Primero los teléfonos: una hora no cae dentro de uno, porque el patrón no acepta : ni . */}
            <ConTelefonos
              texto={l}
              pintarTexto={(t) =>
                t.split(HORAS_EN_TEXTO).map((p, j) =>
                  j % 2 ? (
                    <span key={j} className="cifras">
                      {p}
                    </span>
                  ) : (
                    p
                  ),
                )
              }
            />
          </p>
        ) : (
          <p key={i} aria-hidden>
            {' '}
          </p>
        ),
      )}
    </div>
  )
}

function LineaDeTiempo({ items }: { items: { hora: string; texto: string }[] }) {
  return (
    <div className="relative">
      <span aria-hidden className="absolute top-2 bottom-2 left-18 w-0.5 angosto:hidden rounded-full bg-miel/45" />
      <ol className="flex flex-col gap-3 pl-1">
        {items.map((it, i) => (
          <li key={i} className="relative flex items-start gap-3 angosto:flex-col angosto:gap-1">
            <span className="cifras w-13 shrink-0 pt-px text-right angosto:w-auto angosto:text-left font-bold text-turquesa">{it.hora}</span>
            <span aria-hidden className="relative z-10 mt-1.5 angosto:hidden size-3 shrink-0 rounded-full bg-miel ring-4 ring-hoja" />
            <span className="min-w-0 text-lg">
              <ConTelefonos texto={it.texto} />
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

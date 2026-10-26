// El contenido de la hoja de la ficha: igual en la vista previa, al compartir, para imprimir y en
// la página del relevo. Solo cambia el encabezado.
import type { ReactNode } from 'react'
import { CAMPOS, TEXTO_CAMPO } from '../demo/datos'
import type { CampoId } from '../demo/tipos'
import { Hoja } from './Ui'
import { TextoCampo } from './TextoFicha'

export function HojaFicha({
  encabezado,
  textos,
  campos = CAMPOS,
  escribiendo,
  vacio = 'Sin completar',
  pie,
  etiqueta,
  inclinada = false,
}: {
  encabezado: ReactNode
  textos: Record<CampoId, string>
  campos?: CampoId[]
  /** El campo que se está editando: se marca en la hoja mientras se escribe. */
  escribiendo?: CampoId | null
  vacio?: string
  pie?: ReactNode
  etiqueta?: string
  inclinada?: boolean
}) {
  const visibles = CAMPOS.filter((c) => campos.includes(c))
  return (
    <Hoja etiqueta={etiqueta} inclinada={inclinada}>
      {encabezado}
      {visibles.length === 0 && <p className="mt-4 text-tenue italic">No hay campos para mostrar.</p>}
      {visibles.map((c) => (
        <section
          key={c}
          className={`mt-5 ${escribiendo === c ? '-ml-3 border-l-4 border-miel pl-2' : ''}`}
          aria-label={escribiendo === c ? `${TEXTO_CAMPO[c].titulo}, mientras escribes` : undefined}
        >
          <h3 className="mb-1 text-lg font-bold text-pino">{TEXTO_CAMPO[c].titulo}</h3>
          <TextoCampo renglones texto={textos[c]} vacio={vacio} />
        </section>
      ))}
      {pie}
    </Hoja>
  )
}

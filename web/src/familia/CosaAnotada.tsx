// MATU-128 (especificación docs/diseno/matu-128-lo-que-paso.md v1.0, sección 3): una cosa que el equipo
// de MATU anotó de un pedido, como la leen la familia en «Datos de» (MATU-81) y quien pagó en «Tus
// pedidos». Cada pantalla pone su título y su lista; esta pieza pinta solo la fila.
//
// - El tipo es el de la ruta nueva (`CosaAnotadaVista`), con los siete campos y nada de la copia.
//   `LoQuePasoCopia` tiene los mismos siete, así que «Datos de» la usa sin cambiar su contrato.
// - Sin quién lo anotó: el contrato no lo trae. El estado lleva ícono y palabra (nunca solo el color).
// - E1 (H3): las fechas van sin la hora, como dice `lenguaje.md` 39, también en «Datos de».
import { CircleCheck, Hourglass } from 'lucide-react'
import type { CosaAnotada as Cosa } from '../compartido/api/tusPedidos'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { MIS_DATOS } from './textosMisDatos'
import { Etiqueta } from './ui'

const L = MIS_DATOS.loQuePaso

/**
 * `tarjeta`: la de «Tus pedidos» (4.3), con el tipo en `h3` y la tarjeta de «Cómo va». `copia`: la de
 * «Datos de», como estaba (MATU-81 y MATU-115), con el tipo en negrita dentro del pedido de la copia.
 */
type Variante = 'tarjeta' | 'copia'

const CLASES: Record<Variante, { fila: string; icono: string; etiqueta: string; fecha: string; texto: string }> = {
  tarjeta: {
    fila: 'flex min-w-0 flex-col items-start gap-2 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea',
    icono: 'size-4 shrink-0',
    etiqueta: '',
    fecha: 'text-base text-tenue',
    texto: 'max-w-prose text-base',
  },
  // MATU-115 (P1 del diseñador): sin `items-start`, que dejaba la nota más ancha que la tarjeta a 320 px
  // con el texto al 200 % (WCAG 1.4.10); la etiqueta se alinea con `self-start` (MATU-54 3.4).
  copia: {
    fila: 'flex min-w-0 flex-col gap-1',
    icono: 'size-3.5 shrink-0',
    etiqueta: 'self-start',
    fecha: 'text-base text-tenue',
    texto: 'text-base',
  },
}

/** «Lo anotamos el 30/10/2026.»: el día en hora de Chile, sin la hora (E1). Nada si la fecha no sirve. */
function ConFecha({ partes: [antes, despues], iso }: { partes: readonly [string, string]; iso: string | null | undefined }) {
  if (!iso || Number.isNaN(new Date(iso).getTime())) return null
  return (
    <>
      {antes}
      <time dateTime={iso}>
        <span className="cifras">{fechaYHoraDeChile(new Date(iso)).fecha}</span>
      </time>
      {despues}
    </>
  )
}

export function CosaAnotada({ x, variante }: { x: Cosa; variante: Variante }) {
  const c = CLASES[variante]
  const resuelto = x.estado === 'resuelta'
  const tipo = L.tipo[x.tipo] ?? L.tipo.otro
  const Fecha = variante === 'tarjeta' ? 'p' : 'span'
  return (
    <li className={c.fila}>
      {variante === 'tarjeta' ? <h3 className="max-w-full break-words text-lg font-bold">{tipo}</h3> : <span className="font-bold break-words">{tipo}</span>}
      <Etiqueta tono={resuelto && variante === 'tarjeta' ? 'ok' : 'neutro'} className={c.etiqueta}>
        {resuelto ? <CircleCheck aria-hidden className={c.icono} /> : <Hourglass aria-hidden className={c.icono} />}
        <span className="min-w-0">{resuelto ? L.resuelto : L.revisando}</span>
      </Etiqueta>
      <Fecha className={c.fecha}>
        <ConFecha partes={L.anotado} iso={x.anotado_en} />
      </Fecha>
      {x.nota_disponible === false ? (
        <p className={`${c.texto} text-tenue`}>{L.notaNoDisponible}</p>
      ) : (
        <>
          {x.nota && <p className={`${c.texto} whitespace-pre-line break-words`}>{x.nota}</p>}
          {x.resolucion?.trim() && (
            <p className={`${c.texto} whitespace-pre-line break-words`}>
              <b>{L.comoSeResolvio}</b> {x.resolucion}
            </p>
          )}
        </>
      )}
      {x.resuelto_en && (
        <Fecha className={c.fecha}>
          <ConFecha partes={L.resueltoEl} iso={x.resuelto_en} />
        </Fecha>
      )}
    </li>
  )
}

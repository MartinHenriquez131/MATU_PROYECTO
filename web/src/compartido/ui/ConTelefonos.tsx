// Los teléfonos escritos en la ficha, sin partir (especificación MATU-23, 3.11.4). Lo usan la página
// del relevo y la hoja de la familia, que se dibuja igual en el inicio, al editar y en el relevo
// (Demo/DISENO.md, sección 1). Los teléfonos no se vuelven enlaces.
import { Fragment, type ReactNode } from 'react'
import { trozosConTelefonos } from '../telefonos'

/**
 * 3.11.4: cada teléfono reconocido va en un `inline-block` con dos `cifras`, el prefijo y el resto.
 * Baja entero de renglón y, solo si es más ancho que un renglón, se corta entre esas dos partes,
 * en el espacio de la familia o en el `<wbr>` que va tras un guion o donde no hay separador.
 * No agrega ni quita caracteres: el `textContent` es el texto tal cual. Sin `tel:` ni `aria-*`.
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

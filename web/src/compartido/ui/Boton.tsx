// Botones de MATU (especificación MATU-23, sección 5). Al ancho de su texto, 48 px o más de alto
// (`min-h-12` = 51 px con la raíz de 17 px). La validación ocurre al enviar; solo se deshabilitan
// donde la especificación lo pide (429 de Entrar, dictado mientras se guarda). El de Entrar usa
// `aria-disabled` y no `disabled`: un botón `disabled` pierde el foco y lo deja en el cuerpo de la
// página justo cuando aparece el aviso. Con `aria-disabled` (y las mismas clases de `disabled`, en
// Alta.tsx) se ve y se anuncia igual, conserva el foco, y la pantalla ignora el envío mientras espera.
import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'

type Variante = 'principal' | 'secundario' | 'texto' | 'peligro' | 'textoPeligro' | 'peligroPrincipal'

const VARIANTES: Record<Variante, string> = {
  principal: 'px-5 angosto:px-3 bg-turquesa text-papel hover:brightness-110 active:brightness-95',
  // MATU-67, revisión visual del 09-11: anillo al 80 % (3,60:1 sobre `rocio`; al 70 % daba 2,91) y
  // relleno angosto de 2, para que «Seguir escribiendo» no se corte a 320 px con el texto al 200 %.
  secundario: 'px-5 angosto:px-2 bg-hoja text-turquesa ring-2 ring-inset ring-turquesa/80 hover:bg-rocio active:bg-rocio',
  // De la demo (Ui.tsx): texto subrayado, sin fondo y sin relleno a los lados: se alinea con el
  // texto de la página. Mide 48 px de alto igual que los otros.
  texto: 'px-0 text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa',
  // MATU-49, sección 8: lo que borra. Secundario con texto y anillo `pronto`, foco `pronto`.
  // Nunca macizo: borrar no es la acción principal de ninguna pantalla.
  peligro: 'px-5 angosto:px-3 bg-hoja text-pronto ring-2 ring-inset ring-pronto hover:bg-pronto-fondo active:bg-pronto-fondo focus-visible:outline-pronto',
  // «Quitar «…»» (4.5): de texto, como `texto`, en `pronto`.
  textoPeligro: 'px-0 text-pronto underline underline-offset-4 decoration-pronto/40 hover:decoration-pronto focus-visible:outline-pronto',
  // MATU-44 4.1: la confirmación de lo que no se deshace, dentro de un diálogo. Macizo `pronto`, con
  // la forma del principal y el foco base `turquesa` sobre `hoja` (el botón de eliminar de MATU-36).
  peligroPrincipal: 'px-5 angosto:px-3 bg-pronto text-papel hover:brightness-110 active:brightness-95',
}

const BASE = 'inline-flex min-h-12 max-w-full items-center justify-center gap-2 rounded-xl py-2.5 font-bold leading-tight'

/** Las clases de un botón, para un enlace que se ve como botón (por ejemplo, `tel:` en Enlaces). */
export const claseBoton = (variante: Variante = 'principal') => `${BASE} ${VARIANTES[variante]}`

export function Boton({
  variante = 'principal',
  icono,
  ocupado = false,
  textoOcupado,
  className = '',
  children,
  onClick,
  ...resto
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: Variante
  icono?: ReactNode
  /** Mientras pide algo: conserva su ancho, dice el gerundio y no envía otra vez. */
  ocupado?: boolean
  textoOcupado?: string
  /** React 19: `ref` es una prop más; va al <button> con el resto (foco de vuelta, MATU-49 4.5). */
  ref?: Ref<HTMLButtonElement>
}) {
  return (
    <button
      type="button"
      aria-busy={ocupado || undefined}
      onClick={(e) => {
        if (ocupado) {
          e.preventDefault()
          return
        }
        onClick?.(e)
      }}
      className={`${BASE} disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTES[variante]} ${className}`}
      {...resto}
    >
      {icono && <span className="contents angosto:hidden">{icono}</span>}
      {/* Los dos textos ocupan la misma celda: el botón mide lo que el más largo y no salta. Cada
          texto queda al centro de la celda, que conserva la altura del más alto. */}
      <span className="grid min-w-0 grid-cols-[minmax(0,1fr)] place-items-center">
        <span className={`col-start-1 row-start-1 [overflow-wrap:anywhere] hyphens-auto ${ocupado && textoOcupado ? 'invisible' : ''}`}>{children}</span>
        {textoOcupado && (
          <span className={`col-start-1 row-start-1 [overflow-wrap:anywhere] hyphens-auto ${ocupado ? '' : 'invisible'}`} aria-hidden={!ocupado || undefined}>
            {textoOcupado}
          </span>
        )}
      </span>
    </button>
  )
}

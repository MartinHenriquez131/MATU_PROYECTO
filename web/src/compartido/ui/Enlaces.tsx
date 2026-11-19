// Enlaces de MATU-75 (Demo/DISENO.md, sección 6, «Enlace dentro de una frase»; especificación
// docs/diseno/matu-75-privacidad.md, secciones 4, 5.3 y 7).
import type { MouseEventHandler, ReactNode } from 'react'
import { FileText } from 'lucide-react'
import { POLITICA, RUTA_PRIVACIDAD } from '../textosPolitica'

/**
 * Un enlace en medio de una frase: en línea (no `inline-flex`), para que baje de renglón con la
 * frase. El área táctil es un `span` en línea, sin posición y con `py-3.5` (`data-area-tactil`,
 * MATU-127, docs/diseno/matu-126-enlaces-correo.md, 11.2), que envuelve al texto: se parte con la
 * frase y cada renglón tiene su propio pedazo de área, de unos 51 px de alto, sin mover los
 * renglones. Se mide con `getClientRects`, renglón por renglón. No lleva `aria-hidden`, porque
 * contiene el texto. El contorno del foco es el del `a` y sigue al texto. El texto va en un `span`
 * `relative z-1`, encima de toda área: el área de un enlace nunca le quita sus letras a otro en el
 * renglón de arriba (3.3); por eso el `a` conserva `relative` (11.2). Un `mailto:` lleva `[overflow-wrap:anywhere]`
 * por su cuenta, para que un correo largo no desborde a 320 px (7). Sin ícono. Si abre otra
 * pestaña, su texto ya termina en «(se abre en otra pestaña)».
 */
export function EnlaceEnFrase({
  href,
  otraPestana = false,
  className = '',
  children,
  id,
  onClick,
}: {
  href: string
  otraPestana?: boolean
  className?: string
  children: ReactNode
  /** MATU-61 (5.2): «Ver tu pedido» recibe el foco al agregar y navega dentro de la app. */
  id?: string
  onClick?: MouseEventHandler<HTMLAnchorElement>
}) {
  // Igual que `destinoDe` de privacidad/markdown.ts: «mailto:» sin distinguir mayúsculas.
  const correo = /^mailto:/i.test(href)
  return (
    <a
      id={id}
      onClick={onClick}
      href={href}
      target={otraPestana ? '_blank' : undefined}
      rel={otraPestana ? 'noopener noreferrer' : undefined}
      className={[
        'relative font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa',
        correo ? '[overflow-wrap:anywhere]' : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <span data-area-tactil className="py-3.5">
        <span className="relative z-1">{children}</span>
      </span>
    </a>
  )
}

/** «política de privacidad (se abre en otra pestaña)», dentro de una frase. Sin ancla. */
export function EnlacePoliticaEnFrase() {
  return (
    <EnlaceEnFrase href={RUTA_PRIVACIDAD} otraPestana>
      {POLITICA.enlaceEnFrase}
    </EnlaceEnFrase>
  )
}

/**
 * «Política de privacidad (se abre en otra pestaña)», solo, con `FileText`: el del relevo
 * (`AvisoDatos`) y el de «Tu cuenta». 48 px de alto.
 */
export function EnlacePoliticaSolo() {
  return (
    <a
      href={RUTA_PRIVACIDAD}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex min-h-12 items-start py-3 gap-2 self-start font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa active:decoration-turquesa"
    >
      {/* Junto al primer renglón cuando el texto se parte (revisión visual v0.2, P3). */}
      <FileText aria-hidden className="mt-0.5 size-5 shrink-0" />
      {POLITICA.enlaceSolo}
    </a>
  )
}

/** Autorizaciones (3.3): el último párrafo de «Lo que declaras». */
export function LeePoliticaAntesDeAutorizar() {
  return (
    <p className="mt-3 max-w-prose">
      {POLITICA.autorizarAntes}
      <EnlacePoliticaEnFrase />
      {POLITICA.autorizarDespues}
    </p>
  )
}

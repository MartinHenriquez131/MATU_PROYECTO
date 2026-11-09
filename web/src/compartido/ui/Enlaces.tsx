// Enlaces de MATU-75 (Demo/DISENO.md, sección 6, «Enlace dentro de una frase»; especificación
// docs/diseno/matu-75-privacidad.md, secciones 4, 5.3 y 7).
import type { ReactNode } from 'react'
import { FileText } from 'lucide-react'
import { POLITICA, RUTA_PRIVACIDAD } from '../textosPolitica'

/**
 * Un enlace en medio de una frase: en línea (no `inline-flex`), para que baje de renglón con la
 * frase. El área táctil va en un `::after` (especificación v0.2, sección 7): agranda lo que se toca
 * hasta unos 51 px sin mover los renglones, y el contorno del foco sigue al texto sin tachar los
 * renglones vecinos. Sin ícono. Si abre otra pestaña, su texto ya termina en «(se abre en otra pestaña)».
 */
export function EnlaceEnFrase({
  href,
  otraPestana = false,
  className = '',
  children,
}: {
  href: string
  otraPestana?: boolean
  className?: string
  children: ReactNode
}) {
  return (
    <a
      href={href}
      target={otraPestana ? '_blank' : undefined}
      rel={otraPestana ? 'noopener noreferrer' : undefined}
      className={`relative font-bold text-turquesa after:absolute after:inset-x-0 after:-inset-y-3.5 after:content-['']  underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa ${className}`}
    >
      {children}
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

// La marca de MATU: el círculo `marca` con el corazón blanco y el nombre en la cara de titulares.
import { Heart } from 'lucide-react'

export function Logo({ className = 'size-8' }: { className?: string }) {
  return (
    <span aria-hidden className={`grid shrink-0 place-items-center rounded-full bg-marca ${className}`}>
      <Heart className="size-3/5 fill-white text-white" strokeWidth={2} />
    </span>
  )
}

/** Distintivo del piloto (lenguaje 11): visible siempre, se parte por la frase y no se abrevia. */
export function DistintivoPiloto({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex max-w-full items-center gap-2 rounded-full bg-tinta/7 px-3 py-1 text-base font-bold text-tenue ${className}`}>
      <span aria-hidden className="size-2.5 shrink-0 rounded-full bg-miel" />
      <span className="min-w-0">
        <span className="inline-block">Piloto académico</span> <span className="inline-block">con datos de prueba</span>
      </span>
    </span>
  )
}

/** Marca con nombre (demo, `Marca` de Ui.tsx): el logo y "MATU" en la cara de los titulares. */
export function Marca({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <Logo className="size-9" />
      <span className="titular text-xl">MATU</span>
    </span>
  )
}

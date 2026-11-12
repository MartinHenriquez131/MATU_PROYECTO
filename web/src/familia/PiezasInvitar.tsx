// Piezas comunes de MATU-42 y MATU-53 (especificación docs/diseno/matu-53-invitar-grupo.md): la fecha
// con su hora en dos `cifras`, y el diálogo de confirmación de MATU-44 4.1 que usan los cinco diálogos
// del grupo (6.1). Sin animación y sin valores escritos a mano: todo sale de los tokens.
import { useEffect, useId, useRef, type ReactNode } from 'react'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { Boton } from '../compartido/ui/Boton'
import { Acciones } from './ui'

/** «{antes} {fecha} {entre} {hora}{fin}», con la fecha y la hora cada una en su `cifras` (9). */
export function FechaYHora({ iso, partes, fin = '.' }: { iso: string; partes: readonly [string, string]; fin?: string }) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const { fecha, hora } = fechaYHoraDeChile(d)
  return (
    <>
      {partes[0]} <span className="cifras">{fecha}</span> {partes[1]}{' '}
      <span className="cifras">
        {hora}
        {fin}
      </span>
    </>
  )
}

/** Solo la fecha, DD/MM/AAAA, con el signo que la sigue dentro de su `cifras`. */
export function SoloFecha({ iso, fin = '.' }: { iso: string; fin?: string }) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return (
    <span className="cifras">
      {fechaYHoraDeChile(d).fecha}
      {fin}
    </span>
  )
}

/** El botón de texto que cierra un diálogo: conserva el foco con `aria-disabled` mientras pide. */
const CLASE_NO = 'inline-flex min-h-12 items-center px-2 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa aria-disabled:cursor-not-allowed aria-disabled:opacity-60'

/**
 * El diálogo de MATU-44 4.1 (`DialogoRetirar`): `<dialog>` modal con `showModal()`, el foco inicial al
 * `h2` (en un efecto, después de montar), la región `role="alert"` montada vacía y, mientras la
 * petición está en curso, Esc y el botón de texto no hacen nada. Un segundo Esc cierra el diálogo en
 * Chrome aunque el primero se anuló: con la petición en curso se vuelve a abrir.
 */
export function DialogoGrupo({
  titulo,
  children,
  error,
  confirmar,
  cancelar,
  ocupado,
  enCurso,
  onCancelar,
}: {
  titulo: string
  children?: ReactNode
  /** Lo que va en la región `role="alert"`. */
  error: ReactNode
  /** Sin `confirmar`, el diálogo solo tiene el botón de texto (por ejemplo, tras un 412 que deja la acción sin sentido). */
  confirmar?: {
    texto: string
    textoOcupado: string
    variante: 'principal' | 'peligroPrincipal'
    onClick: () => void
    /** Sigue enfocable y se anuncia deshabilitado (6.3: «Elige otro rol para guardar.»). */
    deshabilitado?: boolean
    /** Id de lo que explica por qué está deshabilitado. */
    describe?: string
    junto?: ReactNode
  }
  cancelar: string
  ocupado: boolean
  /** La petición ya salió: el diálogo no se cierra (ver `DialogoRetirar`). */
  enCurso: React.RefObject<boolean>
  onCancelar: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const h2 = useRef<HTMLHeadingElement>(null)
  const boton = useRef<HTMLButtonElement>(null)
  const uid = useId()

  useEffect(() => {
    const d = ref.current
    if (d && !d.open) d.showModal()
    h2.current?.focus()
  }, [])

  const cancelarSiSePuede = () => {
    if (enCurso.current) return
    if (ref.current?.open) ref.current.close()
    onCancelar()
  }

  return (
    <dialog
      ref={ref}
      aria-labelledby={`${uid}-t`}
      aria-describedby={children ? `${uid}-d` : undefined}
      onCancel={(e) => {
        e.preventDefault()
        cancelarSiSePuede()
      }}
      onClose={() => {
        if (!enCurso.current || !ref.current || ref.current.open) return
        ref.current.showModal()
        boton.current?.focus()
      }}
      className="m-auto w-[calc(100%-2rem)] angosto:w-[calc(100%-1rem)] max-w-lg max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-2xl bg-hoja p-6 angosto:px-2 angosto:py-4 text-tinta backdrop:bg-tinta/40"
    >
      <div className="flex flex-col gap-4">
        <h2 ref={h2} id={`${uid}-t`} tabIndex={-1} className="text-xl font-bold break-words outline-none">
          {titulo}
        </h2>
        {children && (
          <div id={`${uid}-d`} className="flex max-w-prose flex-col gap-4 text-base leading-relaxed">
            {children}
          </div>
        )}
        {/* Con `showModal` lo de fuera queda inerte, también las regiones vivas de main.tsx: el error
            usa su propia región, montada vacía con el diálogo. */}
        <div role="alert" className="empty:-mb-4">
          {error}
        </div>
        <Acciones>
          {confirmar && (
            <Boton
              ref={boton}
              variante={confirmar.variante}
              ocupado={ocupado}
              textoOcupado={confirmar.textoOcupado}
              aria-disabled={confirmar.deshabilitado || undefined}
              aria-describedby={confirmar.describe}
              // El principal no trae estilo para `aria-disabled` (el `peligroPrincipal` sí): el de Entrar.
              className={confirmar.variante === 'principal' ? 'aria-disabled:cursor-not-allowed aria-disabled:opacity-60' : undefined}
              onClick={() => {
                if (!confirmar.deshabilitado) confirmar.onClick()
              }}
            >
              {confirmar.texto}
            </Boton>
          )}
          {confirmar?.junto}
          <button type="button" aria-disabled={ocupado || undefined} onClick={cancelarSiSePuede} className={CLASE_NO}>
            {cancelar}
          </button>
        </Acciones>
      </div>
    </dialog>
  )
}

/** Una lista de puntos de una confirmación (7.1 y 7.2): lo que no vuelve, en negrita. */
export function Puntos({ puntos }: { puntos: { texto: string; fuerte?: boolean }[] }) {
  return (
    <ul className="flex list-disc flex-col gap-2 ps-5 marker:text-tenue">
      {puntos.map((p) => (
        <li key={p.texto} className={p.fuerte ? 'font-bold' : undefined}>
          {p.texto}
        </li>
      ))}
    </ul>
  )
}

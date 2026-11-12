// El diálogo de MATU-44 4.1 (`<dialog>` modal con `showModal()`, `max-w-md`, el foco inicial en el
// título, la región de error vacía y sin animación). Nació para el pedido (MATU-61, secciones 8.7 y
// 10: «Cancelar pedido» y «Vaciar la dirección») y MATU-55 (2.6) lo sacó del pedido para «Cerrar en
// ese teléfono», sin cambiar sus clases. La petición ya salida no se cancela con Esc.
import { useEffect, useId, useRef, useState } from 'react'
import { Boton } from '../compartido/ui/Boton'
import { Acciones, MensajeError } from './ui'

export function DialogoConfirmar({
  titulo,
  texto,
  destacado,
  confirmar,
  confirmando,
  seguir,
  error,
  onConfirmar,
  onCerrar,
}: {
  titulo: string
  texto: string
  /** MATU-62 (6.3): un párrafo en negrita, lo único del diálogo que dice que puede moverse dinero. */
  destacado?: string
  /** El botón macizo `pronto`: lo que no se deshace, con el mismo verbo del título. */
  confirmar: string
  confirmando: string
  /** «Seguir con el pedido», «Dejarla como está» o «Dejarlo abierto»: cierra sin hacer nada. */
  seguir: string
  error: string
  /** Hace la acción. Devuelve `true` si cerró (bien o con un caso que se resuelve fuera), `false` si falló. */
  onConfirmar: () => Promise<boolean>
  /** Cerrar sin hacer nada (Esc o «seguir»): la pantalla devuelve el foco al botón que lo abrió. */
  onCerrar: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const tituloRef = useRef<HTMLHeadingElement>(null)
  const confirmarRef = useRef<HTMLButtonElement>(null)
  const uid = useId()
  const [ocupado, setOcupado] = useState(false)
  const [falla, setFalla] = useState(false)
  const enCurso = useRef(false)

  useEffect(() => {
    const d = ref.current
    if (d && !d.open) d.showModal()
    tituloRef.current?.focus()
  }, [])

  const cerrar = () => {
    enCurso.current = false
    if (ref.current?.open) ref.current.close()
  }

  const hacer = async () => {
    if (enCurso.current) return
    enCurso.current = true
    setOcupado(true)
    setFalla(false)
    let listo = false
    try {
      listo = await onConfirmar()
    } catch {
      listo = false
    } finally {
      enCurso.current = false
      setOcupado(false)
    }
    if (listo) cerrar()
    else setFalla(true)
  }

  const cancelar = () => {
    if (enCurso.current) return
    cerrar()
    onCerrar()
  }

  return (
    <dialog
      ref={ref}
      aria-labelledby={`${uid}-t`}
      aria-describedby={destacado ? `${uid}-d ${uid}-x` : `${uid}-d`}
      onCancel={(e) => {
        e.preventDefault()
        cancelar()
      }}
      // MATU-44 4.4: Chrome deja anular solo un `cancel` por toque. Con la petición en curso, el
      // diálogo se vuelve a abrir para que el error no quede en un diálogo cerrado.
      onClose={() => {
        if (!enCurso.current || !ref.current || ref.current.open) return
        ref.current.showModal()
        confirmarRef.current?.focus()
      }}
      className="m-auto w-[calc(100%-2rem)] angosto:w-[calc(100%-1rem)] max-w-md max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-2xl bg-hoja p-6 angosto:px-2 angosto:py-4 text-tinta backdrop:bg-tinta/40"
    >
      <div className="flex flex-col gap-4">
        <h2 ref={tituloRef} id={`${uid}-t`} tabIndex={-1} className="text-xl font-bold break-words outline-none">
          {titulo}
        </h2>
        <p id={`${uid}-d`} className="max-w-prose text-base">
          {texto}
        </p>
        {destacado && (
          <p id={`${uid}-x`} className="max-w-prose text-base font-bold">
            {destacado}
          </p>
        )}
        {/* Con `showModal` lo de fuera queda inerte, también las regiones vivas: el error usa su propia región. */}
        <div role="alert" className="empty:-mb-4">
          {falla && <MensajeError>{error}</MensajeError>}
        </div>
        <Acciones>
          <Boton ref={confirmarRef} variante="peligroPrincipal" ocupado={ocupado} textoOcupado={confirmando} onClick={() => void hacer()}>
            {confirmar}
          </Boton>
          <button
            type="button"
            aria-disabled={ocupado || undefined}
            onClick={cancelar}
            className="inline-flex min-h-12 items-center px-2 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
          >
            {seguir}
          </button>
        </Acciones>
      </div>
    </dialog>
  )
}

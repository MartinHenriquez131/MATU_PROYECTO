// Piezas compartidas de MATU-57 (especificación 3 y 7): el campo del código de 6 números y la
// espera de un 429 sin cuenta regresiva. El código vive solo en el estado del formulario.
import { useEffect, useId, useState, type ClipboardEvent, type Ref } from 'react'
import { ESPERA_SIN_CABECERA, minutosDeEspera } from '../compartido/api/cliente'
import { MensajeError } from './ui'

/** Solo los números, hasta 6: acepta pegar «123 456» o «123-456». */
export const limpiarCodigo = (texto: string) => texto.replace(/\D/g, '').slice(0, 6)

/** Un solo input, nunca seis cajas: teclado numérico y autocompletado del SMS. */
export function CampoCodigo({
  etiqueta,
  valor,
  onCambio,
  error,
  disabled,
  ref,
}: {
  etiqueta: string
  valor: string
  onCambio: (v: string) => void
  error?: string | null
  disabled?: boolean
  ref?: Ref<HTMLInputElement>
}) {
  const id = useId()
  const pegar = (e: ClipboardEvent<HTMLInputElement>) => {
    // `maxLength` cortaría «123-456» antes de limpiarlo: se limpia aquí.
    e.preventDefault()
    onCambio(limpiarCodigo(e.clipboardData.getData('text')))
  }
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="font-bold">
        {etiqueta}
      </label>
      <input
        ref={ref}
        id={id}
        name="codigo"
        type="text"
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9]*"
        maxLength={6}
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck={false}
        disabled={disabled}
        value={valor}
        onChange={(e) => onCambio(limpiarCodigo(e.target.value))}
        onPaste={pegar}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-e` : undefined}
        className={`min-h-12 w-full max-w-60 min-w-0 rounded-xl bg-hoja px-4 py-2 text-2xl font-bold tracking-widest tabular-nums ring-2 ring-inset disabled:opacity-60 focus-visible:ring-turquesa ${
          error ? 'ring-pronto' : 'ring-borde'
        }`}
      />
      {error && <MensajeError id={`${id}-e`}>{error}</MensajeError>}
    </div>
  )
}

/** Un 429: los minutos para el texto y si todavía hay que esperar. Sin cuenta regresiva. */
export function useEspera() {
  const [hasta, setHasta] = useState(0)
  const [esperando, setEsperando] = useState(false)
  useEffect(() => {
    if (!hasta) return
    setEsperando(true)
    const t = window.setTimeout(() => setEsperando(false), Math.max(0, hasta - Date.now()))
    return () => window.clearTimeout(t)
  }, [hasta])
  const esperar = (segundos: number | null) => {
    const s = segundos ?? ESPERA_SIN_CABECERA
    setHasta(Date.now() + s * 1000)
    return minutosDeEspera(s)
  }
  return { esperando, esperar }
}

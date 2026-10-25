import { useState } from 'react'
import { CloudOff } from 'lucide-react'
import { ErrorApi, type ApiMatu } from './api'
import { useBackend } from './backend'
import { Boton } from '../components/Ui'

/** Corre una llamada a la API con estado de espera y un error con texto humano. */
export function useLlamada() {
  const b = useBackend()
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState<ErrorApi | null>(null)

  const correr = async (fn: (api: ApiMatu) => Promise<void>, api: ApiMatu = b.api) => {
    setOcupado(true)
    setError(null)
    try {
      await fn(api)
    } catch (e) {
      setError(e instanceof ErrorApi ? e : new ErrorApi('red', 'Algo no respondió. Puedes seguir en modo simulado.'))
    } finally {
      setOcupado(false)
    }
  }

  /** Cambia al adaptador simulado y repite la misma acción, sin perder lo escrito. */
  const seguirSimulado = async (fn: (api: ApiMatu) => Promise<void>) => {
    const sim = await b.pasarASimulado()
    await correr(fn, sim)
  }

  return { ocupado, error, correr, seguirSimulado, limpiar: () => setError(null) }
}

/** Falla de red dicha con calma, con una salida: seguir en simulado. */
export function AvisoFalla({ error, onSimulado }: { error: ErrorApi | null; onSimulado: () => void }) {
  if (!error) return null
  if (!error.puedeSimular) {
    return (
      <p role="alert" className="font-bold text-pronto">
        {error.message}
      </p>
    )
  }
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-2xl bg-atenta-fondo px-4 py-3">
      <p className="flex gap-2">
        <CloudOff aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />
        <span>
          <b>El servidor de MATU no respondió.</b> Lo que escribiste sigue aquí. Puedes seguir la demo con datos simulados.
        </span>
      </p>
      <Boton variante="secundario" onClick={onSimulado}>
        Seguir en modo simulado
      </Boton>
    </div>
  )
}

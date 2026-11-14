// Revisar el código de retiro (especificación MATU-63, sección 7). El encargado lo escribe y nunca
// lo ve: el código vive solo en el estado de este campo y en el cuerpo de la petición, y se borra al
// recibir un resultado que cierra la revisión. Nunca va a la URL, a un aviso ni al almacenamiento.
import { useEffect, useId, useRef, useState, type ClipboardEvent, type FormEvent } from 'react'
import { esperaDe, leerFallo } from '../compartido/api/cliente'
import { validarCodigo, type LineaComercio, type ParteVista, type ResultadoCodigo } from '../compartido/api/comercio'
import { esVencida } from '../compartido/api/sesion'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { Acciones, MensajeError } from '../familia/ui'
import { aEntregar, CantidadProducto, horaChile } from './comun'
import { CODIGO_RETIRO as T, PEDIDO_COMERCIO } from './textos'

/** Lo que se muestra de una revisión. `vivo`: vino de una acción, se anuncia y recibe el foco. */
export type Resultado =
  | { tipo: ResultadoCodigo['resultado']; intentos: number; lineas: LineaComercio[]; vivo: boolean; n: number }
  | { tipo: 'espera'; minutos: number; vivo: true; n: number }
  | { tipo: 'red'; vivo: true; n: number }

/** Los resultados después de los que el campo ya no se muestra. */
export const CIERRA = new Set<Resultado['tipo']>(['correcto', 'bloqueado', 'vencido', 'usado', 'cancelada', 'sin_codigo'])

export const ID_RESULTADO = 'resultado-codigo'

/** Solo los números, y los primeros 6 (como el PIN, `PantallaPin.tsx`). */
const limpiar = (t: string) => t.replace(/\D/g, '').slice(0, 6)

/** 7.3: cada resultado es una `Nota` con título, que recibe el foco. Una `key` nueva en cada intento. */
export function NotaResultado({ r, referencia, contacto, retiradaEn = null }: { r: Resultado; referencia: string; contacto: string; retiradaEn?: string | null }) {
  const comun = { id: ID_RESULTADO, enfocable: r.vivo, iconoEnLinea: true } as const
  const rolUrgente = r.vivo ? ('alert' as const) : undefined
  switch (r.tipo) {
    case 'correcto': {
      const entregar = r.lineas.filter((l) => aEntregar(l) > 0)
      return (
        <Nota {...comun} tono="ok" rol={r.vivo ? 'status' : undefined} titulo={T.correctoTitulo(referencia)}>
          <p>{T.correctoTexto}</p>
          <ul className="mt-1 list-disc ps-6">
            {entregar.map((l) => (
              <li key={l.id}>
                <CantidadProducto linea={l} unidades={aEntregar(l)} />
              </li>
            ))}
          </ul>
        </Nota>
      )
    }
    case 'no_es': {
      const [antes, numero, despues] = T.quedan(r.intentos)
      return (
        <Nota {...comun} tono="pronto" rol={rolUrgente} titulo={T.noEsTitulo}>
          {T.noEsAntes}
          {antes}
          <b className="font-bold">{numero}</b>
          {despues}
        </Nota>
      )
    }
    case 'bloqueado':
      return (
        <Nota {...comun} tono="pronto" rol={rolUrgente} titulo={T.bloqueadoTitulo}>
          <span className="break-words">{T.bloqueadoTexto(contacto)}</span>
        </Nota>
      )
    case 'vencido':
      return (
        <Nota {...comun} tono="atenta" rol={rolUrgente} titulo={T.vencidoTitulo}>
          <span className="break-words">{T.vencidoTexto(contacto)}</span>
        </Nota>
      )
    case 'usado':
      return (
        <Nota {...comun} tono="atenta" rol={rolUrgente} titulo={T.usadoTitulo}>
          {T.usadoTexto}
          {/* v1.1 (7.3): sin la nota 6.7; si el contrato trae la hora, va aquí. */}
          {retiradaEn && <span className="cifras whitespace-normal"> {PEDIDO_COMERCIO.retiradoTexto(horaChile(retiradaEn))}</span>}
        </Nota>
      )
    case 'cancelada':
      return (
        <Nota {...comun} tono="pronto" rol={rolUrgente} titulo={T.canceladaTitulo}>
          {T.canceladaTexto}
        </Nota>
      )
    case 'sin_codigo':
      return (
        <Nota {...comun} tono="atenta" rol={rolUrgente}>
          <span className="break-words">{T.sinCodigo(contacto)}</span>
        </Nota>
      )
    case 'espera':
      return (
        <Nota {...comun} tono="atenta" rol="status" titulo={T.esperaTitulo}>
          {T.esperaTexto(r.minutos)}
        </Nota>
      )
    case 'red':
      return (
        <Nota {...comun} tono="pronto" rol="alert" titulo={T.redTitulo}>
          {T.redTexto}
        </Nota>
      )
  }
}

/**
 * 7.2: el campo y «Revisar código». `onResultado` recibe cada resultado y, si la API la devuelve, la
 * parte como quedó. El resultado lo muestra el detalle, encima del campo, para que siga a la vista
 * cuando el campo desaparece.
 */
export function CampoCodigo({
  parte,
  resultado,
  onResultado,
  onInactiva,
}: {
  parte: ParteVista
  resultado: Resultado | null
  onResultado: (r: Resultado, parte: ParteVista | null) => void
  onInactiva: () => void
}) {
  const id = useId()
  const [codigo, setCodigo] = useState('')
  const [corto, setCorto] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [esperando, setEsperando] = useState(false)
  const campo = useRef<HTMLInputElement>(null)
  const n = useRef(0)
  const noEs = resultado?.tipo === 'no_es'

  // 429: el botón vuelve a servir cuando pasa el tiempo, sin cuenta regresiva.
  const espera = resultado?.tipo === 'espera' ? resultado : null
  useEffect(() => {
    if (!espera) return
    setEsperando(true)
    const t = window.setTimeout(() => setEsperando(false), espera.minutos * 60_000)
    return () => window.clearTimeout(t)
  }, [espera])

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado || esperando) return
    if (codigo.length !== 6) {
      setCorto(true)
      campo.current?.focus()
      return
    }
    setCorto(false)
    setOcupado(true)
    try {
      const r = await validarCodigo(parte.id, codigo)
      const nuevo: Resultado = { tipo: r.resultado, intentos: r.intentos_restantes, lineas: r.parte.lineas, vivo: true, n: ++n.current }
      if (r.resultado === 'no_es') campo.current?.setSelectionRange(0, codigo.length)
      else setCodigo('')
      onResultado(nuevo, r.parte)
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 403) return onInactiva()
      const espera = esperaDe(f)
      if (espera) return onResultado({ tipo: 'espera', minutos: espera.minutos, vivo: true, n: ++n.current }, null)
      // 422: no son 6 cifras (no cuenta como intento).
      if (f.status === 422) {
        setCorto(true)
        campo.current?.focus()
        return
      }
      onResultado({ tipo: 'red', vivo: true, n: ++n.current }, null)
    } finally {
      setOcupado(false)
    }
  }

  const pegar = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault()
    setCodigo(limpiar(e.clipboardData.getData('text')))
  }

  const describe = [`${id}-i`, resultado ? ID_RESULTADO : '', corto ? `${id}-e` : ''].filter(Boolean).join(' ')
  return (
    <form noValidate className="flex max-w-md flex-col gap-4" onSubmit={(e) => void enviar(e)}>
      <p id={`${id}-i`} className="max-w-prose text-base">
        {T.instruccion}
      </p>
      <div className="flex flex-col gap-2">
        <label htmlFor={`${id}-c`} className="font-bold">
          {T.etiqueta}
        </label>
        <input
          ref={campo}
          id={`${id}-c`}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          enterKeyHint="done"
          spellCheck={false}
          maxLength={6}
          readOnly={ocupado}
          value={codigo}
          onChange={(e) => setCodigo(limpiar(e.target.value))}
          onPaste={pegar}
          aria-invalid={noEs || corto ? true : undefined}
          aria-describedby={describe}
          className={`digitos min-h-16 w-full max-w-72 rounded-xl bg-hoja text-center text-3xl angosto:text-2xl font-bold tracking-widest ring-2 ring-inset ${
            noEs || corto ? 'text-pronto ring-pronto' : 'ring-borde focus-visible:ring-turquesa'
          }`}
        />
        {corto && <MensajeError id={`${id}-e`}>{T.faltan}</MensajeError>}
      </div>
      <Acciones>
        <Boton
          type="submit"
          ocupado={ocupado}
          textoOcupado={T.revisando}
          aria-disabled={esperando || undefined}
          className="aria-disabled:cursor-not-allowed aria-disabled:opacity-60 aria-disabled:focus-visible:outline-tinta"
        >
          {T.boton}
        </Boton>
      </Acciones>
    </form>
  )
}

// Quién te la mandó y el PIN (3.2), con sus mensajes (3.3) y el aviso «Tus datos en MATU» (3.2.1).
// Sin interfaz optimista: la pantalla espera la respuesta del canje antes de cambiar.
import { useRef, useState, type ClipboardEvent, type FormEvent } from 'react'
import { CircleAlert, FileText, KeyRound, ShieldCheck } from 'lucide-react'
import type { Presentacion } from '../compartido/api/relevo'
import { Boton } from '../compartido/ui/Boton'
import { Baldosa, Columna, Titulo } from './Marco'
import { AVISO, ERROR, PIN, RUTA_POLITICA } from './textos'

/** Lo que devuelve el canje a esta pantalla. `salio` = la página ya pasó a otro momento. */
export type ResultadoCanje = { tipo: 'salio' } | { tipo: 'incorrecto'; intentos: number } | { tipo: 'incompleto' } | { tipo: 'conexion' }

type Mensaje = Exclude<ResultadoCanje, { tipo: 'salio' }>

const soloDigitos = (v: string) => v.replace(/\D/g, '').slice(0, 4)

export function PantallaPin({ presentacion, onCanjear }: { presentacion: Presentacion; onCanjear: (pin: string) => Promise<ResultadoCanje> }) {
  const [pin, setPin] = useState('')
  const [mensaje, setMensaje] = useState<Mensaje | null>(null)
  // Cada mensaje nuevo se monta de nuevo para que el lector de pantalla lo anuncie, aunque repita.
  const [vez, setVez] = useState(0)
  const [canjeando, setCanjeando] = useState(false)
  const enviando = useRef(false)
  const campo = useRef<HTMLInputElement>(null)

  const mostrar = (m: Mensaje) => {
    setMensaje(m)
    setVez((n) => n + 1)
  }

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (enviando.current) return
    if (pin.length !== 4) {
      mostrar({ tipo: 'incompleto' })
      campo.current?.focus()
      return
    }
    enviando.current = true
    setCanjeando(true)
    const r = await onCanjear(pin)
    enviando.current = false
    if (r.tipo === 'salio') {
      // Después del 204 el PIN no queda en ninguna parte: la pantalla se desmonta.
      setPin('')
      return
    }
    setCanjeando(false)
    mostrar(r)
    if (r.tipo === 'incorrecto' || r.tipo === 'incompleto') {
      // Los dígitos quedan escritos y seleccionados: si Rosa escribe, los reemplaza.
      campo.current?.focus()
      campo.current?.select()
    }
  }

  const pegar = (e: ClipboardEvent<HTMLInputElement>) => {
    // Así se puede pegar "4 8 2 1" aunque el campo admita 4 caracteres.
    e.preventDefault()
    setPin(soloDigitos(e.clipboardData.getData('text')))
  }

  const conError = mensaje?.tipo === 'incorrecto' || mensaje?.tipo === 'incompleto'

  return (
    <Columna>
      <Baldosa icono={KeyRound} tono={conError ? 'pronto' : 'rocio'} />
      <div className="flex flex-col items-center gap-2">
        <Titulo>{PIN.titulo(presentacion.nombre_pila_comparte, presentacion.nombre_pila)}</Titulo>
        <p id="pin-bajada" className="max-w-md text-lg text-tenue">
          {PIN.bajada}
        </p>
      </div>
      <form noValidate onSubmit={enviar} className="flex w-full flex-col items-center gap-3">
        <label htmlFor="pin" className="font-bold">
          {PIN.etiqueta}
        </label>
        <input
          ref={campo}
          id="pin"
          name="pin"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          enterKeyHint="go"
          maxLength={4}
          value={pin}
          onChange={(e) => setPin(soloDigitos(e.target.value))}
          onPaste={pegar}
          aria-invalid={conError || undefined}
          aria-describedby={mensaje ? 'pin-bajada pin-mensaje' : 'pin-bajada'}
          className={`digitos min-h-18 w-full max-w-60 rounded-xl bg-hoja text-center text-5xl angosto:text-3xl font-bold tracking-widest ring-2 ring-inset focus-visible:ring-turquesa ${
            conError ? 'text-pronto ring-pronto' : 'ring-borde'
          }`}
        />
        {mensaje && <MensajePin key={vez} mensaje={mensaje} />}
        <Boton type="submit" ocupado={canjeando} textoOcupado={PIN.botonOcupado}>
          {PIN.boton}
        </Boton>
      </form>
      <p className="max-w-md text-base text-tenue">{PIN.pie}</p>
      <AvisoDatos />
    </Columna>
  )
}

function MensajePin({ mensaje }: { mensaje: Mensaje }) {
  if (mensaje.tipo === 'incompleto') {
    return (
      <p id="pin-mensaje" role="alert" className="max-w-md text-base font-bold text-pronto">
        {PIN.incompleto}
      </p>
    )
  }
  if (mensaje.tipo === 'incorrecto') {
    return (
      <p id="pin-mensaje" role="alert" className="max-w-md text-base text-tinta">
        <b className="font-bold text-pronto">{PIN.incorrectoInicio}</b> {PIN.incorrectoRevisa} {PIN.teQuedan(mensaje.intentos)}{' '}
        <b className="font-bold">{PIN.intentos(mensaje.intentos)}</b>. {PIN.incorrectoFin}
      </p>
    )
  }
  // Sin conexión o 5xx: Rosa no hizo nada mal y no se perdió nada. No va en `pronto`.
  return (
    <p id="pin-mensaje" role="alert" className="flex max-w-md items-start justify-center gap-2 text-base text-tinta">
      <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-tenue" />
      <span>
        <b className="font-bold">{ERROR.titulo}</b> {ERROR.conexion} {ERROR.escrito}
      </span>
    </p>
  )
}

/** Lenguaje 7.5, sin acordeón: Rosa lo lee antes de entrar. */
function AvisoDatos() {
  return (
    <section aria-labelledby="aviso-datos-t" className="flex w-full max-w-md flex-col gap-3 border-t border-linea pt-5 text-start">
      <h2 id="aviso-datos-t" className="flex items-center gap-2 text-base font-bold">
        <ShieldCheck aria-hidden className="size-5 shrink-0 text-turquesa" />
        {AVISO.titulo}
      </h2>
      {AVISO.parrafos.map((p) => (
        <p key={p} className="text-base leading-relaxed text-tenue">
          {p}
        </p>
      ))}
      {RUTA_POLITICA && (
        <a
          href={RUTA_POLITICA}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex min-h-12 items-center gap-2 self-start font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa active:decoration-turquesa"
        >
          <FileText aria-hidden className="size-5 shrink-0" />
          {AVISO.politica}
        </a>
      )}
    </section>
  )
}

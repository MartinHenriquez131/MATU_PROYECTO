// Dictar en vez de escribir (especificación 3.7.1, decisión de Jorge del 03-11). Usa el
// reconocimiento de voz del navegador (Web Speech API) en es-CL. Si el navegador no lo tiene, el
// botón no aparece. Lo dictado se agrega al final del texto y nunca se guarda solo: la persona lo
// revisa y toca «Guardar». Ningún texto dictado ni audio se guarda en el navegador.
import { useCallback, useEffect, useRef, useState } from 'react'
import { Mic, MicOff, Square } from 'lucide-react'
import { FICHA } from './textos'

// Tipos mínimos: TypeScript no trae los de SpeechRecognition.
interface ResultadoVoz {
  isFinal: boolean
  0: { transcript: string }
}
interface EventoVoz {
  resultIndex: number
  results: ArrayLike<ResultadoVoz>
}
interface Reconocedor {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((e: EventoVoz) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort: () => void
}
type ConstructorReconocedor = new () => Reconocedor

function constructorDeVoz(): ConstructorReconocedor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { SpeechRecognition?: ConstructorReconocedor; webkitSpeechRecognition?: ConstructorReconocedor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

/** Une lo dictado al final, con un espacio si hace falta, sin pasar del tope. */
function agregar(base: string, dictado: string, tope: number): string {
  const limpio = dictado.trim()
  if (!limpio) return base
  const sep = base && !/\s$/.test(base) ? ' ' : ''
  return (base + sep + limpio).slice(0, tope)
}

export function useDictado({ texto, onTexto, tope }: { texto: string; onTexto: (t: string) => void; tope: number }) {
  const Voz = constructorDeVoz()
  const [escuchando, setEscuchando] = useState(false)
  const [fallo, setFallo] = useState(false)
  const rec = useRef<Reconocedor | null>(null)
  // Lo que había antes de empezar y lo ya confirmado: lo provisorio se ve, pero se recalcula.
  const base = useRef('')
  const textoActual = useRef(texto)
  textoActual.current = texto

  const detener = useCallback(() => {
    rec.current?.stop()
  }, [])

  const empezar = useCallback(() => {
    if (!Voz || rec.current) return
    setFallo(false)
    const r = new Voz()
    r.lang = 'es-CL'
    r.continuous = true
    r.interimResults = true
    base.current = textoActual.current
    r.onresult = (e) => {
      let final = ''
      let provisorio = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i]
        if (res.isFinal) final += res[0].transcript
        else provisorio += res[0].transcript
      }
      if (final) base.current = agregar(base.current, final, tope)
      const visible = agregar(base.current, provisorio, tope)
      onTexto(visible)
      if (visible.length >= tope) r.stop()
    }
    r.onerror = () => setFallo(true)
    r.onend = () => {
      rec.current = null
      setEscuchando(false)
      onTexto(base.current)
    }
    rec.current = r
    try {
      r.start()
      setEscuchando(true)
    } catch {
      rec.current = null
      setFallo(true)
    }
  }, [Voz, onTexto, tope])

  // Se detiene al salir de la pantalla.
  useEffect(() => () => rec.current?.abort(), [])

  return { disponible: !!Voz, escuchando, fallo, empezar, detener }
}

export function BotonDictar({ d, deshabilitado }: { d: ReturnType<typeof useDictado>; deshabilitado: boolean }) {
  if (!d.disponible) return null
  return (
    <div className="flex flex-col items-start gap-1.5">
      <button
        type="button"
        aria-pressed={d.escuchando}
        disabled={deshabilitado}
        onClick={() => (d.escuchando ? d.detener() : d.empezar())}
        className={`inline-flex min-h-12 min-w-12 max-w-full items-center justify-center gap-2 rounded-xl px-5 angosto:px-3 py-2.5 font-bold leading-tight text-turquesa disabled:cursor-not-allowed disabled:opacity-60 ${
          d.escuchando ? 'bg-rocio ring-2 ring-inset ring-turquesa' : 'bg-hoja ring-2 ring-inset ring-turquesa/80 hover:bg-rocio'
        }`}
      >
        {d.escuchando ? (
          <>
            <span aria-hidden className="size-2.5 shrink-0 rounded-full bg-turquesa motion-safe:animate-[aparecer_900ms_ease-in-out_infinite_alternate]" />
            <span>{FICHA.escuchando}</span>
            <Square aria-hidden className="size-4 shrink-0" />
            <span>{FICHA.detener}</span>
          </>
        ) : (
          <>
            {d.fallo ? <MicOff aria-hidden className="size-5 shrink-0" /> : <Mic aria-hidden className="size-5 shrink-0" />}
            <span>{FICHA.dictar}</span>
          </>
        )}
      </button>
      <p role="status" className="text-base text-tenue">
        {d.fallo && !d.escuchando ? FICHA.sinMicrofono : ''}
      </p>
    </div>
  )
}

// La página del relevo: lo que ve Rosa al abrir /r#<token>. Pública, sin cuenta y sin navegación,
// centrada en la hoja. El PIN se bloquea al quinto error (MATU-19).
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Clock3, KeyRound, RefreshCw } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { accesoDelRelevo, canjear, nombrePila, relevoRevalida } from '../demo/logica'
import { MAX_INTENTOS_PIN, fmtFecha, fmtHora } from '../demo/calculos'
import type { CampoId } from '../demo/tipos'
import { leerTokenDelFragmento } from '../components/RelevoUrl'
import { Boton, Logo, MensajeError, Nota } from '../components/Ui'
import { HojaFicha } from '../components/HojaFicha'

function MarcoRelevo({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b border-linea bg-hoja">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-1 px-4 @3xl:px-10 py-3">
          <span className="flex items-center gap-2.5">
            <Logo className="size-8" />
            <span className="titular text-xl">MATU</span>
          </span>
          <span className="text-tenue">Ficha de cuidado compartida</span>
        </div>
      </header>
      <main id="contenido" tabIndex={-1} className="@container/main px-4 @3xl:px-10 pt-6 @3xl:pt-14 pb-16 outline-none">
        {children}
      </main>
    </div>
  )
}

export function RelevoApp() {
  const { s, haz } = useDemo()
  // Cada vez que se abre la página, se vuelve a consultar: si cortaron el enlace, ya no abre.
  useEffect(() => {
    haz(relevoRevalida)
  }, [haz])
  return (
    <MarcoRelevo>
      {s.relevo.fase === 'ficha' ? <RelevoFicha /> : s.relevo.fase === 'no_disponible' ? <NoDisponible /> : <RelevoPin />}
    </MarcoRelevo>
  )
}

function RelevoPin() {
  const { s, haz } = useDemo()
  const [pin, setPin] = useState('')
  const [corto, setCorto] = useState(false)
  const campo = useRef<HTMLInputElement>(null)
  const a = accesoDelRelevo(s)
  const quien = s.cuenta?.nombre || 'Carmen'
  const quedan = a ? MAX_INTENTOS_PIN - a.intentosFallidos : 0
  const error = s.relevo.pinErroneo
  const entrar = () => {
    if (pin.length !== 4) {
      setCorto(true)
      campo.current?.focus()
      return
    }
    setCorto(false)
    const token = leerTokenDelFragmento() ?? s.relevo.token
    haz((x) => canjear(x, token, pin))
    setPin('')
    campo.current?.focus()
  }
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-6 text-center">
      <span className={`grid size-18 place-items-center rounded-2xl ${error ? 'bg-pronto-fondo text-pronto' : 'bg-rocio text-pino'}`}>
        <KeyRound aria-hidden className="size-10" />
      </span>
      <div className="flex flex-col gap-2">
        <h1 id="titulo-pagina" tabIndex={-1} className="titular text-3xl @2xl:text-5xl outline-none">
          {quien} te compartió la ficha de {nombrePila(s)}
        </h1>
        <p className="text-lg text-tenue">Escribe el PIN de cuatro números que te dio por teléfono.</p>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          entrar()
        }}
        className="flex w-full flex-col items-center gap-3"
      >
        <label htmlFor="pin-relevo" className="font-bold">
          PIN
        </label>
        <input
          ref={campo}
          id="pin-relevo"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]*"
          maxLength={4}
          value={pin}
          aria-invalid={error || corto ? true : undefined}
          aria-describedby={error ? 'pin-error' : corto ? 'pin-corto' : undefined}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
          className={`digitos min-h-18 w-full max-w-60 rounded-xl bg-hoja pl-2 text-center text-5xl font-bold tracking-widest ring-2 ring-inset focus-visible:ring-pino ${
            error || corto ? 'text-pronto ring-pronto' : 'ring-borde'
          }`}
        />
        {corto && <MensajeError id="pin-corto">El PIN tiene 4 números. Revisa que estén todos.</MensajeError>}
        {error && !corto && (
          <p id="pin-error" role="alert" className="max-w-md">
            <b className="text-pronto">Ese PIN no es.</b> Revisa los cuatro números que te dio {quien}. Te {quedan === 1 ? 'queda' : 'quedan'}{' '}
            <b>
              {quedan} {quedan === 1 ? 'intento' : 'intentos'}
            </b>
            ; después el enlace se bloquea.
          </p>
        )}
        <Boton type="submit" className="mt-1">
          Ver la ficha
        </Boton>
      </form>
      <p className="max-w-md text-base text-tenue">No necesitas cuenta ni instalar nada. Al entrar, el enlace se borra de la barra de direcciones.</p>
    </div>
  )
}

function RelevoFicha() {
  const { s, haz } = useDemo()
  const a = accesoDelRelevo(s)
  if (!a) return <NoDisponible />
  const quien = s.cuenta?.nombre || 'Carmen'
  const pila = nombrePila(s)
  const textos: Record<CampoId, string> = {
    su_dia: s.ficha.su_dia.texto,
    si_se_altera: s.ficha.si_se_altera.texto,
    a_quien_llamar: s.ficha.a_quien_llamar.texto,
  }
  return (
    <div className="mx-auto grid max-w-6xl items-start gap-8 @4xl/main:grid-cols-[minmax(0,1fr)_17rem]">
      <div className="@container mx-auto w-full max-w-3xl @4xl/main:order-none">
        <HojaFicha
          etiqueta={`Ficha de ${pila}`}
          textos={textos}
          campos={a.campos}
          encabezado={
            <div className="border-b-2 border-tinta pb-3">
              <p className="text-tenue">Ficha de cuidado de</p>
              <h1 id="titulo-pagina" tabIndex={-1} className="titular text-4xl @2xl:text-6xl leading-none outline-none">
                {pila}
              </h1>
            </div>
          }
        />
      </div>
      <aside aria-label="Sobre esta ficha" className="order-first flex flex-col gap-4 @4xl/main:sticky @4xl/main:top-6 @4xl/main:order-none">
        <p className="flex items-start gap-2">
          <Clock3 aria-hidden className="mt-0.5 size-5 shrink-0 text-pino" />
          <span>
            {quien} te la compartió. Puedes verla hasta el <b className="cifras">{fmtFecha(a.venceMin)}</b> a las <b className="cifras">{fmtHora(a.venceMin)}</b>.
          </span>
        </p>
        <Boton variante="secundario" className="self-start" icono={<RefreshCw aria-hidden className="size-5" />} onClick={() => haz(relevoRevalida)}>
          Actualizar
        </Boton>
        <p className="text-base text-tenue">Solo {quien} puede cambiar esta ficha.</p>
      </aside>
    </div>
  )
}

function NoDisponible() {
  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-5 text-center">
      <span className="grid size-18 place-items-center rounded-2xl bg-tinta/7 text-tenue">
        <Clock3 aria-hidden className="size-10" />
      </span>
      <h1 id="titulo-pagina" tabIndex={-1} role="alert" className="titular text-3xl @2xl:text-5xl outline-none">
        Este enlace ya no está disponible
      </h1>
      <p className="text-base text-tenue">Puede que haya vencido, que lo hayan cortado o que el PIN se haya escrito mal varias veces.</p>
      <div className="w-full text-left">
        <Nota titulo="¿Qué hago?">Pídele a quien te envió el enlace uno nuevo.</Nota>
      </div>
    </div>
  )
}

// La página del relevo: lo que ve Rosa al abrir el enlace, sin cuenta y sin instalar nada.
import { useEffect, useState } from 'react'
import { Clock3, KeyRound, Lock, RefreshCw } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { accesoDelRelevo, canjear, nombrePila, relevoRevalida } from '../demo/logica'
import { CAMPOS, TEXTO_CAMPO } from '../demo/datos'
import { MAX_INTENTOS_PIN, fmtFecha, fmtHora } from '../demo/calculos'
import { leerTokenDelFragmento } from '../components/RelevoUrl'
import { Pantalla } from '../components/Pantalla'
import { Boton, Hoja, Nota, Sello } from '../components/Ui'
import { TextoCampo } from '../components/TextoFicha'

function EncabezadoWeb({ titulo }: { titulo: string }) {
  const { s } = useDemo()
  const url = s.relevo.urlLimpia || !s.relevo.token ? 'matu.cl/r' : `matu.cl/r#${s.relevo.token.slice(0, 10)}…`
  return (
    <header className="shrink-0 border-b border-linea bg-hoja">
      <div className="px-3 pt-2">
        <p className="flex min-h-9 items-center gap-2 rounded-full bg-tinta/[0.06] px-3 text-[0.85rem] text-tenue" aria-label={`Dirección: ${url}`}>
          <Lock aria-hidden className="size-3.5 shrink-0" />
          <span className="min-w-0 truncate">{url}</span>
        </p>
      </div>
      <p className="px-5 py-3 font-display text-[1.2rem] font-bold" aria-hidden>
        {titulo}
      </p>
    </header>
  )
}

export function RelevoApp() {
  const { s, haz } = useDemo()
  // Cada vez que se abre la página, se vuelve a consultar: si cortaron el enlace, ya no abre.
  useEffect(() => {
    haz(relevoRevalida)
  }, [haz])
  if (s.relevo.fase === 'ficha') return <RelevoFicha />
  if (s.relevo.fase === 'no_disponible') return <NoDisponible />
  return <RelevoPin />
}

function RelevoPin() {
  const { s, haz } = useDemo()
  const [pin, setPin] = useState('')
  const [corto, setCorto] = useState(false)
  const a = accesoDelRelevo(s)
  const quien = s.cuenta?.nombre || 'Carmen'
  const quedan = a ? MAX_INTENTOS_PIN - a.intentosFallidos : 0
  const entrar = () => {
    if (pin.length !== 4) return setCorto(true)
    setCorto(false)
    const token = leerTokenDelFragmento() ?? s.relevo.token
    haz((x) => canjear(x, token, pin))
    setPin('')
  }
  const error = s.relevo.pinErroneo
  return (
    <Pantalla titulo="Ficha de cuidado" sinVolver encabezado={<EncabezadoWeb titulo="Ficha de cuidado" />} pie={<Boton onClick={entrar}>Ver la ficha</Boton>}>
      <div className="flex flex-col items-start gap-3 pt-2">
        <Sello tono={error ? 'pronto' : 'suave'}>
          <KeyRound aria-hidden className="size-9" />
        </Sello>
        {error ? (
          <>
            <p className="font-display text-[1.5rem] leading-tight font-bold">Ese PIN no es</p>
            <p role="alert">
              Revisa los cuatro números que te dio {quien}. Te {quedan === 1 ? 'queda' : 'quedan'}{' '}
              <b>
                {quedan} {quedan === 1 ? 'intento' : 'intentos'}
              </b>
              .
            </p>
          </>
        ) : (
          <>
            <p className="font-display text-[1.5rem] leading-tight font-bold">
              {quien} te compartió la ficha de {nombrePila(s)}
            </p>
            <p className="text-tenue">Escribe el PIN que te dio por teléfono.</p>
          </>
        )}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault()
          entrar()
        }}
        className="flex flex-col items-start gap-2"
      >
        <label htmlFor="pin-relevo" className="font-bold">
          PIN de 4 números
        </label>
        <input
          id="pin-relevo"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]*"
          maxLength={4}
          value={pin}
          aria-invalid={error || corto ? true : undefined}
          aria-describedby={corto ? 'pin-corto' : undefined}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
          className={`digitos min-h-16 w-full max-w-[13rem] rounded-2xl bg-hoja text-center text-[2.2rem] font-bold tracking-[0.45em] ring-2 ring-inset outline-none focus-visible:ring-pino ${
            error || corto ? 'text-pronto ring-pronto' : 'ring-linea'
          }`}
        />
        {corto && (
          <p id="pin-corto" className="font-bold text-pronto">
            El PIN tiene 4 números.
          </p>
        )}
      </form>
      <p className="text-sm text-tenue">No necesitas cuenta ni instalar nada. Al entrar, el enlace se borra de la barra de direcciones.</p>
    </Pantalla>
  )
}

function RelevoFicha() {
  const { s, haz } = useDemo()
  const a = accesoDelRelevo(s)
  if (!a) return <NoDisponible />
  const quien = s.cuenta?.nombre || 'Carmen'
  const pila = nombrePila(s)
  return (
    <Pantalla
      titulo={`Ficha de ${pila}`}
      sinVolver
      encabezado={<EncabezadoWeb titulo={`Ficha de ${pila}`} />}
      pie={
        <Boton variante="secundario" icono={<RefreshCw aria-hidden className="size-5" />} onClick={() => haz(relevoRevalida)}>
          Actualizar
        </Boton>
      }
    >
      <p className="flex items-start gap-2 rounded-2xl bg-rocio px-4 py-3 text-[0.95rem]">
        <Clock3 aria-hidden className="mt-0.5 size-5 shrink-0 text-pino" />
        <span>
          {quien} te la compartió. Puedes verla hasta el <b className="cifras">{fmtFecha(a.venceMin)}</b> a las <b className="cifras">{fmtHora(a.venceMin)}</b>.
        </span>
      </p>
      <Hoja etiqueta={`Ficha de ${pila}`}>
        <h2 className="font-display text-[1.9rem] leading-none font-extrabold tracking-[-0.03em]">{pila}</h2>
        {CAMPOS.filter((c) => a.campos.includes(c)).map((c) => (
          <section key={c} className="mt-4">
            <h3 className="mb-1 text-[1.1rem] font-bold text-pino">{TEXTO_CAMPO[c].titulo}</h3>
            <TextoCampo renglones texto={s.ficha[c].texto} />
          </section>
        ))}
      </Hoja>
      <p className="text-[0.95rem] text-tenue">Solo {quien} puede cambiar esta ficha.</p>
    </Pantalla>
  )
}

function NoDisponible() {
  return (
    <Pantalla titulo="Ficha de cuidado" sinVolver encabezado={<EncabezadoWeb titulo="Ficha de cuidado" />}>
      <div className="flex flex-col items-start gap-3 pt-6">
        <Sello tono="suave">
          <Clock3 aria-hidden className="size-9" />
        </Sello>
        <p role="alert" className="font-display text-[1.5rem] leading-tight font-bold">
          Este enlace ya no está disponible
        </p>
        <p className="text-tenue">Puede que haya vencido, que lo hayan cortado o que el PIN se haya escrito mal varias veces.</p>
      </div>
      <Nota titulo="¿Qué hago?">Pídele a quien te envió el enlace uno nuevo.</Nota>
    </Pantalla>
  )
}

// Entrar al equipo de MATU (especificación MATU-81, sección 4): dos pasos en la misma ruta. El paso 1
// es el de Entrar del comercio (los campos, el 429 con `aria-disabled` y el foco que se queda en el
// botón) con «Seguir». El paso 2 pide las 6 cifras del teléfono. La contraseña se borra al pasar al
// paso 2, y el desafío vive solo en la memoria de esta pantalla: al recargar se vuelve al paso 1.
import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { esperaDe, leerFallo, minutosDeEspera } from '../compartido/api/cliente'
import { esProblema, extensionDe } from '../compartido/api/operacion'
import { cerrarSinAvisar, entrarConCodigo, entrarConSegundoFactor, type DesafioMfa } from '../compartido/api/sesion'
import { Boton } from '../compartido/ui/Boton'
import { EnlaceEnFrase } from '../compartido/ui/Enlaces'
import { BotonMostrar } from '../familia/Alta'
import { navegar } from '../familia/ruteo'
import { Acciones, CampoTexto, MensajeError, Nota, Titulo } from '../familia/ui'
import { enChile, useFocoAlMontar } from './comun'
import { useOperacion } from './estado'
import { MarcoEntrar } from './Marco'
import { ENTRAR as T } from './textos'

type FallaClave = { tipo: 'faltan' | 'credenciales' | 'no-disponible' | 'red' } | { tipo: 'espera'; minutos: number; hasta: number }
type ResultadoCodigo = { tipo: 'no-coincide' | 'sin-redis' | 'red'; n: number } | { tipo: 'bloqueado'; minutos: number; hasta: number; n: number }

const ID_NOTA_CLAVE = 'nota-entrar'
const ID_RESULTADO = 'resultado-codigo'

/** 4.2: se quitan los que no son números y se toman los primeros 6 ([C63] 7.2). */
const soloCifras = (v: string) => v.replace(/\D/g, '').slice(0, 6)

export function EntrarOperacion() {
  const { avisoEntrar, destino, alEntrar, fijar } = useOperacion()
  const [email, setEmail] = useState('')
  const [clave, setClave] = useState('')
  const [ver, setVer] = useState(false)
  const [falla, setFalla] = useState<FallaClave | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [esperando, setEsperando] = useState(false)
  /** 4.4: el desafío venció y se volvió al paso 1: la nota recibe el foco. */
  const [vencio, setVencio] = useState(0)
  const [desafio, setDesafio] = useState<DesafioMfa | null>(null)
  const pedirFoco = useFocoAlMontar()

  useEffect(() => {
    if (falla?.tipo !== 'espera') return
    setEsperando(true)
    const t = window.setTimeout(() => setEsperando(false), Math.max(0, falla.hasta - Date.now()))
    return () => window.clearTimeout(t)
  }, [falla])

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado || esperando) return
    if (!email.trim() || !clave) return setFalla({ tipo: 'faltan' })
    setFalla(null)
    setVencio(0)
    setOcupado(true)
    try {
      const r = await entrarConSegundoFactor(email.trim(), clave)
      // 4.2: con el desafío, la contraseña sale de la memoria y el paso 1 se desmonta.
      setClave('')
      setVer(false)
      if ('desafio' in r) {
        fijar({ avisoEntrar: null })
        setDesafio(r)
        pedirFoco('titulo-pagina')
        return
      }
      // 4.4: una cuenta de familia o de comercio. Su entrada se cierra; la pantalla no dice si el correo existe.
      await cerrarSinAvisar()
      fijar({ avisoEntrar: 'otra' })
      pedirFoco(ID_NOTA_CLAVE)
    } catch (x) {
      const f = leerFallo(x)
      const espera = esperaDe(f)
      if (f.status === 401) setFalla({ tipo: 'credenciales' })
      else if (espera) setFalla({ tipo: 'espera', minutos: espera.minutos, hasta: Date.now() + espera.segundos * 1000 })
      else if (f.status === 503) setFalla({ tipo: 'no-disponible' })
      else setFalla({ tipo: 'red' })
    } finally {
      setOcupado(false)
    }
  }

  const volverALaClave = (motivo: 'volver' | 'vencio') => {
    setDesafio(null)
    if (motivo === 'vencio') {
      setVencio((n) => n + 1)
      pedirFoco(ID_NOTA_CLAVE)
    } else pedirFoco('titulo-pagina')
  }

  const listo = () => {
    alEntrar()
    const ir = destino ?? '/operacion'
    fijar({ destino: null, avisoEntrar: null })
    navegar(ir, { reemplazar: true })
  }

  if (desafio) return <PasoCodigo desafio={desafio} onVolver={volverALaClave} onListo={listo} />

  return (
    <MarcoEntrar>
      <div className="flex flex-col gap-2">
        <Titulo className="text-3xl">{T.titulo}</Titulo>
        <p className="max-w-prose text-lg text-tenue">{T.bajada}</p>
      </div>
      {vencio > 0 ? (
        <Nota key={`v${vencio}`} id={ID_NOTA_CLAVE} enfocable tono="atenta" rol="status" titulo={T.vencioTitulo}>
          {T.vencioTexto}
        </Nota>
      ) : avisoEntrar === 'otra' ? (
        <Nota id={ID_NOTA_CLAVE} enfocable tono="atenta" rol="status" titulo={T.otraTitulo}>
          {T.otraTexto}
        </Nota>
      ) : avisoEntrar === 'vencida' || avisoEntrar === 'salio' ? (
        <Nota tono="rocio" rol="status">
          {avisoEntrar === 'vencida' ? T.vencida : T.salio}
        </Nota>
      ) : null}
      {falla?.tipo === 'espera' && (
        <Nota tono="atenta" rol="status">
          {T.espera(falla.minutos)}
        </Nota>
      )}
      {falla?.tipo === 'no-disponible' && (
        <Nota tono="pronto" rol="alert">
          {T.noDisponible}
        </Nota>
      )}
      {falla?.tipo === 'red' && (
        <Nota tono="pronto" rol="alert">
          {T.red}
        </Nota>
      )}
      <form noValidate className="flex flex-col gap-5" onSubmit={(e) => void enviar(e)}>
        <CampoTexto etiqueta={T.correo} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" maxLength={254} />
        <CampoTexto
          etiqueta={T.contrasena}
          type={ver ? 'text' : 'password'}
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          autoComplete="current-password"
          maxLength={128}
          junto={<BotonMostrar visible={ver} onCambio={() => setVer((v) => !v)} />}
        />
        {falla?.tipo === 'faltan' && <MensajeError>{T.faltan}</MensajeError>}
        {falla?.tipo === 'credenciales' && (
          <Nota tono="pronto" rol="alert">
            {T.credenciales}
          </Nota>
        )}
        <Acciones>
          <Boton
            type="submit"
            ocupado={ocupado}
            textoOcupado={T.revisando}
            aria-disabled={esperando || undefined}
            className="aria-disabled:cursor-not-allowed aria-disabled:opacity-60 aria-disabled:focus-visible:outline-tinta"
          >
            {T.seguir}
          </Boton>
        </Acciones>
      </form>
      <p className="max-w-prose">
        {T.aLaFamiliaAntes}
        <EnlaceEnFrase href="/entrar">{T.aLaFamiliaEnlace}</EnlaceEnFrase>
        {T.aLaFamiliaDespues}
      </p>
    </MarcoEntrar>
  )
}

/** 4.2 y 4.4: el paso del código del teléfono. */
function PasoCodigo({ desafio, onVolver, onListo }: { desafio: DesafioMfa; onVolver: (motivo: 'volver' | 'vencio') => void; onListo: () => void }) {
  const uid = useId()
  const [codigo, setCodigo] = useState('')
  const [menos, setMenos] = useState(false)
  const [resultado, setResultado] = useState<ResultadoCodigo | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [bloqueado, setBloqueado] = useState(false)
  const campo = useRef<HTMLInputElement>(null)
  const pedirFoco = useFocoAlMontar()
  const intento = useRef(0)

  useEffect(() => {
    if (resultado?.tipo !== 'bloqueado') return
    setBloqueado(true)
    const t = window.setTimeout(() => setBloqueado(false), Math.max(0, resultado.hasta - Date.now()))
    return () => window.clearTimeout(t)
  }, [resultado])

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado || resultado?.tipo === 'bloqueado') return
    if (codigo.length !== 6) {
      setMenos(true)
      campo.current?.focus()
      return
    }
    setMenos(false)
    setOcupado(true)
    const n = ++intento.current
    try {
      await entrarConCodigo(desafio.desafio, codigo)
      onListo()
    } catch (x) {
      const f = leerFallo(x)
      if (f.status === 401 && esProblema(f.tipo, 'desafio-vencido')) return onVolver('vencio')
      // C32: un código ya usado se ve igual que uno que no coincide.
      if (f.status === 401) {
        setResultado({ tipo: 'no-coincide', n })
        window.setTimeout(() => campo.current?.setSelectionRange(0, campo.current.value.length), 0)
      } else if (f.status === 429) {
        const extra = extensionDe(x, 'minutos_espera')
        const minutos = typeof extra === 'number' && extra > 0 ? extra : minutosDeEspera(f.reintentarEnSegundos ?? 60)
        setResultado({ tipo: 'bloqueado', minutos, hasta: Date.now() + (f.reintentarEnSegundos ?? minutos * 60) * 1000, n })
      } else if (f.status === 503) setResultado({ tipo: 'sin-redis', n })
      else setResultado({ tipo: 'red', n })
      pedirFoco(ID_RESULTADO)
    } finally {
      setOcupado(false)
    }
  }

  const { hora } = enChile(desafio.expiraEn)
  const describe = [`${uid}-b`, `${uid}-p`, resultado ? ID_RESULTADO : '', menos ? `${uid}-e` : ''].filter(Boolean).join(' ')
  const noCoincide = resultado?.tipo === 'no-coincide'

  return (
    <MarcoEntrar>
      <div className="flex flex-col gap-2">
        <Titulo className="text-3xl">{T.codigoTitulo}</Titulo>
        <p id={`${uid}-b`} className="max-w-prose text-lg text-tenue">
          {T.codigoBajada}
        </p>
      </div>
      {resultado && (
        <div key={resultado.n}>
          {resultado.tipo === 'no-coincide' && (
            <Nota id={ID_RESULTADO} enfocable tono="pronto" rol="alert" titulo={T.noCoincideTitulo}>
              {T.noCoincideTexto}
            </Nota>
          )}
          {resultado.tipo === 'bloqueado' && (
            <Nota id={ID_RESULTADO} enfocable tono="atenta" rol="alert" titulo={T.bloqueadoTitulo}>
              {T.bloqueadoTexto(resultado.minutos)}
            </Nota>
          )}
          {resultado.tipo === 'sin-redis' && (
            <Nota id={ID_RESULTADO} enfocable tono="pronto" rol="alert" titulo={T.sinRedisTitulo}>
              {T.sinRedisTexto}
            </Nota>
          )}
          {resultado.tipo === 'red' && (
            <Nota id={ID_RESULTADO} enfocable tono="pronto" rol="alert">
              {T.red}
            </Nota>
          )}
        </div>
      )}
      <form noValidate className="flex flex-col gap-3" onSubmit={(e) => void enviar(e)}>
        {resultado?.tipo !== 'bloqueado' && (
          <>
            <label htmlFor={`${uid}-c`} className="font-bold">
              {T.codigoEtiqueta}
            </label>
            <input
              ref={campo}
              id={`${uid}-c`}
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              enterKeyHint="go"
              spellCheck={false}
              maxLength={12}
              value={codigo}
              onChange={(e) => {
                setCodigo(soloCifras(e.target.value))
                setMenos(false)
              }}
              aria-invalid={noCoincide || menos || undefined}
              aria-describedby={describe}
              className={`digitos min-h-16 w-full max-w-72 rounded-xl bg-hoja text-center text-3xl angosto:text-2xl font-bold tracking-widest ring-2 ring-inset focus-visible:ring-turquesa ${
                noCoincide ? 'text-pronto ring-pronto' : 'ring-borde'
              }`}
            />
            {menos && <MensajeError id={`${uid}-e`}>{T.menosDeSeis}</MensajeError>}
          </>
        )}
        <p id={`${uid}-p`} className="cifras text-base whitespace-normal text-tenue">
          {T.plazo(hora)}
        </p>
        <Acciones className="mt-2">
          {resultado?.tipo !== 'bloqueado' && (
            <Boton type="submit" ocupado={ocupado} textoOcupado={T.entrando}>
              {T.entrar}
            </Boton>
          )}
          <Boton
            variante="texto"
            aria-disabled={bloqueado || undefined}
            className="aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
            onClick={() => {
              if (!bloqueado) onVolver('volver')
            }}
          >
            {T.volver}
          </Boton>
        </Acciones>
      </form>
    </MarcoEntrar>
  )
}

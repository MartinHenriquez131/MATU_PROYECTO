// «Tu cuenta» y «Confirma tu celular» (especificación MATU-57, sección 5). El celular llega
// enmascarado desde `GET /v1/cuenta` y nunca se guarda fuera de la memoria de la pantalla. SMS o
// WhatsApp se elige una vez, al confirmar (campo `canal`, decisión de Jorge del 03-11).
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { flushSync } from 'react-dom'
import { Check, Circle } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { confirmarCelular, leerCuenta, pedirCodigoCelular, type CanalCelular, type Cuenta } from '../compartido/api/familia'
import { leerPolitica, type PoliticaAceptada } from '../compartido/api/politica'
import { esVencida } from '../compartido/api/sesion'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { POLITICA } from '../compartido/textosPolitica'
import { Boton } from '../compartido/ui/Boton'
import { EnlaceEnFrase, EnlacePoliticaSolo } from '../compartido/ui/Enlaces'
import { CampoCodigo, useEspera } from './Codigo'
import { useDemora } from './Estados'
import { useFamilia } from './estado'
import { navegar } from './ruteo'
import { Acciones, Etiqueta, GrupoOpciones, Nota, Pagina, Volver } from './ui'
import { CELULAR, CUENTA_PROPIA, GENERAL, RECUPERAR } from './textos'

type Carga = { estado: 'cargando' } | { estado: 'error' } | { estado: 'lista'; cuenta: Cuenta }

function useCuenta() {
  const [carga, setCarga] = useState<Carga>({ estado: 'cargando' })
  const cargar = useCallback(async () => {
    setCarga({ estado: 'cargando' })
    try {
      setCarga({ estado: 'lista', cuenta: await leerCuenta() })
    } catch (x) {
      if (!esVencida(x)) setCarga({ estado: 'error' })
    }
  }, [])
  useEffect(() => {
    void cargar()
  }, [cargar])
  return { carga, cargar }
}

function Cargando() {
  const ver = useDemora()
  return (
    <p role="status" className="text-tenue">
      {ver ? GENERAL.cargando : ''}
    </p>
  )
}

function ErrorCarga({ reintentar }: { reintentar: () => void }) {
  return (
    <div className="flex flex-col items-start gap-4">
      <Nota tono="pronto" rol="alert">
        {GENERAL.errorAlCargar}
      </Nota>
      <Boton variante="secundario" onClick={reintentar}>
        {GENERAL.volverAIntentar}
      </Boton>
    </div>
  )
}

function EstadoCelular({ verificado }: { verificado: boolean }) {
  // El estado va con palabra, nunca solo con color.
  return verificado ? (
    <Etiqueta tono="ok">
      <Check aria-hidden className="size-4" strokeWidth={3} />
      {CUENTA_PROPIA.confirmado}
    </Etiqueta>
  ) : (
    <Etiqueta>
      <Circle aria-hidden className="size-3.5" strokeWidth={2.5} />
      {CUENTA_PROPIA.sinConfirmar}
    </Etiqueta>
  )
}

// ---------------------------------------------------------------- MATU-75: la política aceptada

/**
 * El correo de contacto (`correo_contacto` de `GET /v1/politica`, pública y sin cookies). `null`
 * mientras no llega, si no está configurado o si la petición falla: el párrafo no se muestra.
 */
function useCorreoPrivacidad() {
  const [correo, setCorreo] = useState<string | null>(null)
  useEffect(() => {
    let vigente = true
    leerPolitica()
      .then((p) => vigente && setCorreo(p.correo_contacto ?? null))
      .catch(() => {})
    return () => {
      vigente = false
    }
  }, [])
  return correo
}

/** La fila «Política de privacidad» (especificación 5.3), con o sin registro, y el enlace. */
function FilaPolitica({ aceptada }: { aceptada: PoliticaAceptada | null | undefined }) {
  const instante = aceptada ? new Date(aceptada.aceptada_en) : null
  const fecha = instante && !Number.isNaN(instante.getTime()) ? fechaYHoraDeChile(instante).fecha : null
  return (
    <div className="flex flex-col gap-2 py-4">
      <dt className="text-sm text-tenue">{POLITICA.fila}</dt>
      <dd className="flex flex-col items-start gap-2 text-base">
        {aceptada && fecha ? (
          <p>
            {POLITICA.aceptasteAntes} <span className="cifras font-bold">{aceptada.version}</span> {POLITICA.aceptasteEl}{' '}
            <span className="cifras font-bold">{fecha}</span>.
          </p>
        ) : (
          <p className="text-tinta">{POLITICA.sinRegistro}</p>
        )}
        <EnlacePoliticaSolo />
      </dd>
    </div>
  )
}

/** Cómo pedir (5.3): fuera del `dl`, con el correo en `mailto:` sin asunto ni cuerpo. */
function ComoPedir({ correo }: { correo: string | null }) {
  if (!correo) return null
  return (
    <p className="mt-6 max-w-xl text-base leading-relaxed text-tinta">
      {POLITICA.comoPedirAntes}
      <EnlaceEnFrase href={`mailto:${correo}`} className="[overflow-wrap:anywhere]">
        {correo}
      </EnlaceEnFrase>
      {POLITICA.comoPedirDespues}
    </p>
  )
}

// ---------------------------------------------------------------- 5.2 Tu cuenta (D5)

export function TuCuenta() {
  const { fijar } = useFamilia()
  const { carga, cargar } = useCuenta()
  const correo = useCorreoPrivacidad()
  return (
    <Pagina titulo={CUENTA_PROPIA.titulo} bajada={CUENTA_PROPIA.bajada}>
      {carga.estado === 'cargando' && <Cargando />}
      {carga.estado === 'error' && <ErrorCarga reintentar={() => void cargar()} />}
      {carga.estado === 'lista' && (
        <>
          <dl className="flex max-w-xl flex-col divide-y divide-linea rounded-xl bg-hoja px-4 ring-1 ring-linea">
            <div className="flex flex-col gap-0.5 py-4">
              <dt className="text-sm text-tenue">{CUENTA_PROPIA.correo}</dt>
              <dd className="font-bold break-words">{carga.cuenta.email}</dd>
            </div>
            <div className="flex flex-col gap-2 py-4">
              <dt className="text-sm text-tenue">{CUENTA_PROPIA.celular}</dt>
              {carga.cuenta.celular_enmascarado ? (
                <dd className="flex flex-col items-start gap-3">
                  <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="cifras text-lg font-bold whitespace-nowrap">{carga.cuenta.celular_enmascarado}</span>
                    <EstadoCelular verificado={carga.cuenta.celular_verificado} />
                  </span>
                  {!carga.cuenta.celular_verificado && (
                    <Boton
                      variante="secundario"
                      onClick={() => {
                        fijar({ celularDesde: 'cuenta' })
                        navegar('/cuenta/celular')
                      }}
                    >
                      {CUENTA_PROPIA.confirmar}
                    </Boton>
                  )}
                </dd>
              ) : (
                <dd className="text-tenue">{CUENTA_PROPIA.sinCelular}</dd>
              )}
            </div>
            <FilaPolitica aceptada={carga.cuenta.politica_aceptada} />
          </dl>
          <ComoPedir correo={correo} />
        </>
      )}
    </Pagina>
  )
}

// ---------------------------------------------------------------- 5.1 Confirma tu celular

type Paso = 'pedir' | 'confirmar' | 'listo'
type Falla = { tipo: 'espera'; minutos: number } | { tipo: 'no-envio' | 'red' | 'sin-celular' } | null

export function ConfirmarCelular() {
  const { celularDesde } = useFamilia()
  const primera = celularDesde === 'primera'
  const { carga, cargar } = useCuenta()
  const [paso, setPaso] = useState<Paso>('pedir')
  const [canal, setCanal] = useState<CanalCelular | null>(null)
  const [codigo, setCodigo] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [falla, setFalla] = useState<Falla>(null)
  const [ocupado, setOcupado] = useState(false)
  const [reenvioEn, setReenvioEn] = useState(false)
  const { esperando, esperar } = useEspera()
  const campo = useRef<HTMLInputElement>(null)
  const listo = useRef<HTMLDivElement>(null)

  const cuenta = carga.estado === 'lista' ? carga.cuenta : null
  const canalElegido = canal ?? cuenta?.celular_canal ?? 'sms'

  // Ya confirmado, o sin celular, desde la primera entrada: no hay nada que ofrecer.
  useEffect(() => {
    if (!cuenta || paso !== 'pedir') return
    if (cuenta.celular_verificado || !cuenta.celular_enmascarado) {
      if (primera) navegar('/', { reemplazar: true })
      else if (cuenta.celular_verificado) navegar('/cuenta', { reemplazar: true })
    }
  }, [cuenta, paso, primera])

  // 6.6: «Enviar otro código» espera 60 s, sin cuenta regresiva.
  useEffect(() => {
    if (!reenvioEn) return
    const t = window.setTimeout(() => setReenvioEn(false), 60_000)
    return () => window.clearTimeout(t)
  }, [reenvioEn])

  const salir = () => navegar(primera ? '/' : '/cuenta')

  const enviarCodigo = async () => {
    if (ocupado || esperando) return
    setFalla(null)
    setOcupado(true)
    try {
      await pedirCodigoCelular()
      setCodigo('')
      setError(null)
      setReenvioEn(true)
      setPaso('confirmar')
      window.setTimeout(() => campo.current?.focus(), 0)
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 409 && f.tipo === '/errores/celular-verificado') terminar()
      else if (f.status === 409) setFalla({ tipo: 'sin-celular' })
      else if (f.status === 429) setFalla({ tipo: 'espera', minutos: esperar(f.reintentarEnSegundos) })
      else if (f.status === 503) setFalla({ tipo: 'no-envio' })
      else setFalla({ tipo: 'red' })
    } finally {
      setOcupado(false)
    }
  }

  const terminar = () => {
    setPaso('listo')
    window.setTimeout(() => listo.current?.focus(), 0)
  }

  const confirmar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado || esperando) return
    setFalla(null)
    if (codigo.length !== 6) {
      setError(CELULAR.errCodigoCorto)
      return campo.current?.focus()
    }
    setError(null)
    setOcupado(true)
    try {
      await confirmarCelular(codigo, canalElegido)
      terminar()
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      // Tras un `await`, React puede confirmar el estado después del setTimeout del foco: flushSync deja
      // el campo con `aria-invalid` y su mensaje antes de enfocarlo (como en Crear cuenta).
      if (f.status === 422 && f.tipo === '/errores/codigo-invalido') {
        flushSync(() => {
          setCodigo('')
          setError(CELULAR.errCodigo)
        })
        window.setTimeout(() => campo.current?.focus(), 0)
      } else if (f.status === 422) {
        flushSync(() => setError(CELULAR.errCodigoCorto))
        window.setTimeout(() => campo.current?.focus(), 0)
      } else if (f.status === 429) setFalla({ tipo: 'espera', minutos: esperar(f.reintentarEnSegundos) })
      else if (f.status === 503) setFalla({ tipo: 'no-envio' })
      else setFalla({ tipo: 'red' })
    } finally {
      setOcupado(false)
    }
  }

  const ahoraNo = primera && paso !== 'listo' && (
    <Boton variante="texto" onClick={salir}>
      {CELULAR.ahoraNo}
    </Boton>
  )

  const avisos = falla && (
    <Nota tono={falla.tipo === 'espera' || falla.tipo === 'sin-celular' ? 'atenta' : 'pronto'} rol={falla.tipo === 'espera' ? 'status' : 'alert'}>
      {falla.tipo === 'espera'
        ? CELULAR.espera(falla.minutos)
        : falla.tipo === 'no-envio'
          ? CELULAR.noEnvio
          : falla.tipo === 'sin-celular'
            ? CUENTA_PROPIA.sinCelular
            : GENERAL.error}
    </Nota>
  )

  return (
    <Pagina
      titulo={CELULAR.titulo}
      antes={!primera && <Volver onClick={salir}>{CUENTA_PROPIA.volver}</Volver>}
      bajada={paso !== 'listo' ? <span className="text-tinta">{CELULAR.explicacion}</span> : undefined}
    >
      <div className="flex max-w-xl flex-col gap-6">
        {carga.estado === 'cargando' && <Cargando />}
        {carga.estado === 'error' && <ErrorCarga reintentar={() => void cargar()} />}
        {cuenta && !cuenta.celular_enmascarado && !primera && (
          <Nota tono="atenta" rol="status">
            {CUENTA_PROPIA.sinCelular}
          </Nota>
        )}

        {cuenta?.celular_enmascarado && paso === 'pedir' && (
          <>
            <div className="flex flex-col gap-0.5">
              <p className="font-bold">{CELULAR.tuCelular}</p>
              <p className="cifras text-lg whitespace-nowrap">{cuenta.celular_enmascarado}</p>
            </div>
            <GrupoOpciones
              leyenda={CELULAR.canal}
              nombre="canal-celular"
              valor={canalElegido}
              onCambio={setCanal}
              opciones={[
                { valor: 'sms', texto: CELULAR.sms },
                { valor: 'whatsapp', texto: CELULAR.whatsapp },
              ]}
            />
            {avisos}
            <Acciones>
              <Boton ocupado={ocupado} textoOcupado={CELULAR.enviando} disabled={esperando} onClick={() => void enviarCodigo()}>
                {CELULAR.enviar}
              </Boton>
              {ahoraNo}
            </Acciones>
          </>
        )}

        {cuenta?.celular_enmascarado && paso === 'confirmar' && (
          <>
            <Nota tono="rocio" rol="status">
              {CELULAR.enviado}<span className="whitespace-nowrap">{cuenta.celular_enmascarado}</span>.
            </Nota>
            <form noValidate className="flex flex-col gap-5" onSubmit={(e) => void confirmar(e)}>
              <CampoCodigo ref={campo} etiqueta={RECUPERAR.codigo} valor={codigo} onCambio={setCodigo} error={error} />
              {avisos}
              <Acciones>
                <Boton type="submit" ocupado={ocupado} textoOcupado={CELULAR.confirmando} disabled={esperando}>
                  {CELULAR.confirmar}
                </Boton>
              </Acciones>
            </form>
            <div className="flex flex-col items-start gap-1">
              <Boton variante="texto" className="justify-start! text-left" disabled={reenvioEn || esperando || ocupado} onClick={() => void enviarCodigo()}>
                {CELULAR.otro}
              </Boton>
              {reenvioEn && <p className="text-sm text-tenue">{CELULAR.enUnMinuto}</p>}
              {ahoraNo}
            </div>
          </>
        )}

        {paso === 'listo' && (
          <div ref={listo} tabIndex={-1} className="flex flex-col items-start gap-5 outline-none">
            <Nota tono="ok" rol="status">
              {CELULAR.listo}
            </Nota>
            <Boton onClick={salir}>{primera ? CELULAR.irAFicha : CUENTA_PROPIA.volver}</Boton>
          </div>
        )}
      </div>
    </Pagina>
  )
}

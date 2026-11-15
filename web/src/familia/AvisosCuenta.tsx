// «Avisos cuando un insumo se está acabando» en «Tu cuenta» (MATU-55, especificación 3.3 y 3.4): las
// dos casillas de `PUT /v1/yo/avisos`, que valen para todos los grupos, y debajo de «En tus
// teléfonos», este teléfono (`GET /v1/dispositivos/actual/push` y la suscripción del navegador).
// Cada casilla se guarda al marcarla y queda en «Guardando…» hasta el 200 (E3). El permiso de avisos
// del navegador se pide solo al tocar «Activar en este…» (D6-a). Nada se guarda en el navegador.
import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Check, Circle, Info, Share } from 'lucide-react'
import { guardarAvisos, leerAvisos, leerPushActual, listarDispositivos, type ClaseDispositivo, type PreferenciaAvisos, type PushActual } from '../compartido/api/familia'
import { leerFallo } from '../compartido/api/cliente'
import { esVencida } from '../compartido/api/sesion'
import { Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { useDemora } from './Estados'
import { activarPush, desactivarPush, estadoPush, type EstadoPush } from './push'
import { Etiqueta, MensajeError, Nota } from './ui'
import { GENERAL } from './textos'
import { AVISOS, DONDE, PUSH, sustantivo } from './textosDondeEntraste'

type Canal = keyof PreferenciaAvisos
type Carga<T> = { estado: 'cargando' } | { estado: 'error' } | { estado: 'lista'; datos: T }

const esPreferencia = (p: unknown): p is PreferenciaAvisos =>
  !!p && typeof p === 'object' && typeof (p as PreferenciaAvisos).correo === 'boolean' && typeof (p as PreferenciaAvisos).push === 'boolean'
const esPush = (p: unknown): p is PushActual => !!p && typeof p === 'object' && typeof (p as PushActual).registrado === 'boolean'

function Cargando() {
  const ver = useDemora()
  return (
    <p role="status" className="text-tenue">
      {ver ? GENERAL.cargando : ''}
    </p>
  )
}

function ErrorLectura({ texto, reintentar }: { texto: string; reintentar: () => void }) {
  return (
    <div className="flex max-w-prose flex-col items-start gap-4">
      <Nota tono="pronto" rol="alert">
        {texto}
      </Nota>
      <Boton variante="secundario" onClick={reintentar}>
        {GENERAL.volverAIntentar}
      </Boton>
    </div>
  )
}

/** Una lectura que se pide al montar, con su validación. Sin interfaz optimista. */
function useLectura<T>(leer: () => Promise<unknown>, valida: (x: unknown) => x is T) {
  const [carga, setCarga] = useState<Carga<T>>({ estado: 'cargando' })
  const vivo = useRef(true)
  const cargar = useCallback(async () => {
    setCarga({ estado: 'cargando' })
    try {
      const x = await leer()
      if (vivo.current) setCarga(valida(x) ? { estado: 'lista', datos: x } : { estado: 'error' })
    } catch (e) {
      if (vivo.current && !esVencida(e)) setCarga({ estado: 'error' })
    }
    // `leer` y `valida` no cambian entre renders: se leen una vez.
  }, [])
  useEffect(() => {
    vivo.current = true
    void cargar()
    return () => {
      vivo.current = false
    }
  }, [cargar])
  return { carga, cargar }
}

/**
 * E1: la clase del dispositivo actual, de `GET /v1/dispositivos`. `undefined` mientras no llega; si
 * falla, `null`, y el sustantivo es «navegador», que vale para cualquiera.
 */
function useClaseActual() {
  const [clase, setClase] = useState<ClaseDispositivo | null | undefined>(undefined)
  useEffect(() => {
    let vivo = true
    listarDispositivos()
      .then((items) => vivo && setClase((Array.isArray(items) ? items.find((d) => d.actual)?.clase : null) ?? null))
      .catch(() => vivo && setClase(null))
    return () => {
      vivo = false
    }
  }, [])
  return clase
}

// ---------------------------------------------------------------- 3.3 las preferencias

export function AvisosCuenta() {
  const uid = useId()
  const preferencia = useLectura<PreferenciaAvisos>(leerAvisos, esPreferencia)
  const push = useLectura<PushActual>(leerPushActual, esPush)
  const clase = useClaseActual()
  const [guardada, setGuardada] = useState<PreferenciaAvisos | null>(null)
  const [pendiente, setPendiente] = useState<{ canal: Canal; valor: boolean } | null>(null)
  const [aviso, setAviso] = useState<'guardando' | 'guardado' | 'error' | null>(null)
  const casillas = useRef<Partial<Record<Canal, HTMLInputElement | null>>>({})
  // 1.2 (criterio 16): el foco vuelve a la casilla después del render que termina de guardar.
  const [focoCasilla, setFocoCasilla] = useState<{ canal: Canal } | null>(null)
  // P3: cada bloque borra el mensaje del otro. Sube cuando se toca una casilla.
  const [casillaTocada, setCasillaTocada] = useState(0)

  useEffect(() => {
    if (focoCasilla) casillas.current[focoCasilla.canal]?.focus()
  }, [focoCasilla])

  const base = guardada ?? (preferencia.carga.estado === 'lista' ? preferencia.carga.datos : null)
  const ver = base && pendiente ? { ...base, [pendiente.canal]: pendiente.valor } : base

  const cambiar = async (canal: Canal, valor: boolean) => {
    if (!base || pendiente) return
    setPendiente({ canal, valor })
    setAviso('guardando')
    setCasillaTocada((n) => n + 1)
    try {
      const r = await guardarAvisos({ ...base, [canal]: valor })
      setGuardada(esPreferencia(r) ? r : { ...base, [canal]: valor })
      setAviso('guardado')
    } catch (e) {
      if (esVencida(e)) return setAviso(null)
      // 422 solo puede pasar por un defecto: se trata como el error. La casilla vuelve a lo de antes.
      setAviso('error')
    } finally {
      setPendiente(null)
      setFocoCasilla({ canal })
    }
  }

  // 8 de la sección 6: la nota del piloto se ve mientras `envio_simulado` sea `true`, y también si la lectura falla.
  const piloto = push.carga.estado !== 'lista' || push.carga.datos.envio_simulado

  const casilla = (canal: Canal, texto: string) => (
    <label className="flex min-h-12 cursor-pointer items-center gap-3 angosto:items-start font-bold has-aria-disabled:cursor-not-allowed">
      <input
        ref={(n) => {
          casillas.current[canal] = n
        }}
        type="checkbox"
        checked={ver?.[canal] ?? false}
        // 1.2: `aria-disabled` y no `disabled`, que saca el foco de la casilla y lo deja en el body.
        aria-disabled={pendiente !== null || undefined}
        aria-busy={pendiente?.canal === canal || undefined}
        onChange={(e) => {
          if (pendiente === null) void cambiar(canal, e.target.checked)
        }}
        className="size-6 shrink-0 accent-turquesa aria-disabled:not-focus-visible:opacity-60 angosto:mt-0.5"
      />
      {texto}
    </label>
  )

  return (
    <div className="max-w-xl rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea">
    <fieldset aria-describedby={`${uid}-a ${uid}-g`} className="flex min-w-0 flex-col gap-3">
      <legend className="pb-3">
        <h2 className="text-xl font-bold leading-snug">{AVISOS.leyenda}</h2>
      </legend>
      <p id={`${uid}-a`} className="max-w-prose text-base text-tenue">
        {AVISOS.ayuda}
      </p>
      <p id={`${uid}-g`} className="text-base font-bold">
        {AVISOS.alcance}
      </p>

      {preferencia.carga.estado === 'cargando' && <Cargando />}
      {preferencia.carga.estado === 'error' && <ErrorLectura texto={AVISOS.errCargar} reintentar={() => void preferencia.cargar()} />}
      {ver && (
        <div className="flex flex-col gap-1">
          {casilla('correo', AVISOS.correo)}
          {casilla('push', AVISOS.push)}
          {/* E4: al desmarcar «En tus teléfonos», el bloque se oculta y la inscripción no se borra. */}
          <div hidden={!ver.push}>
            <EsteTelefono push={push.carga} clase={clase} reintentar={() => void push.cargar()} casillaTocada={casillaTocada} onAccion={() => setAviso(null)} />
          </div>
          {aviso === 'guardando' && (
            <Anunciado urgencia="status" como="p" className="mt-2 text-base text-tenue">
              {AVISOS.guardando}
            </Anunciado>
          )}
          {aviso === 'guardado' && (
            <Anunciado urgencia="status" como="p" className="mt-2 text-base">
              {AVISOS.guardado}
            </Anunciado>
          )}
          {aviso === 'error' && (
            <Anunciado urgencia="alert" className="mt-2">
              <MensajeError>{AVISOS.errGuardar}</MensajeError>
            </Anunciado>
          )}
        </div>
      )}

      {piloto && (
        <Nota tono="atenta" icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />} className="mt-2">
          {AVISOS.piloto}
        </Nota>
      )}
    </fieldset>
    </div>
  )
}

// ---------------------------------------------------------------- 3.4 este teléfono

const ID_ACTIVAR = 'push-activar'
const ID_DESACTIVAR = 'push-desactivar'
const ID_BLOQUEADO = 'push-bloqueado'
const ID_NO_PERMITIDO = 'push-no-permitido'

/** MATU-107 (2.3): el `PUT` responde 409 `push-no-permitido` si la regla cambió entre la lectura y el toque. */
const esNoPermitido = (e: unknown) => {
  const f = leerFallo(e)
  return f.status === 409 && f.tipo === '/errores/push-no-permitido'
}

export function EsteTelefono({
  push,
  clase,
  reintentar,
  casillaTocada = 0,
  onAccion,
}: {
  push: Carga<PushActual>
  clase: ClaseDispositivo | null | undefined
  reintentar: () => void
  /** P3: sube al tocar una casilla, y entonces se borra el mensaje de este bloque. */
  casillaTocada?: number
  /** P3: al activar o desactivar, el bloque de las casillas borra el suyo. */
  onAccion?: () => void
}) {
  const [estado, setEstado] = useState<EstadoPush | null>(null)
  const [ocupado, setOcupado] = useState<'activar' | 'desactivar' | null>(null)
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // MATU-107 (2.3): tras el 409, la nota G se anuncia una vez por `status`. Al cargar en G, no.
  const [anunciarG, setAnunciarG] = useState(false)
  // 1.2 (criterio 16): el foco va al botón que aparece, o a la nota de C, después del render.
  const [foco, setFoco] = useState<{ id: string } | null>(null)
  useEffect(() => {
    if (foco) document.getElementById(foco.id)?.focus()
  }, [foco])
  useEffect(() => {
    if (!casillaTocada) return
    setMensaje(null)
    setError(null)
  }, [casillaTocada])
  const s = sustantivo(clase)

  const datos = push.estado === 'lista' ? push.datos : null
  useEffect(() => {
    if (!datos) return setEstado(null)
    let vivo = true
    void estadoPush(datos).then((e) => vivo && setEstado(e))
    return () => {
      vivo = false
    }
  }, [datos])

  const activar = async () => {
    if (!datos?.clave_publica || ocupado) return
    setOcupado('activar')
    setMensaje(null)
    setError(null)
    onAccion?.()
    try {
      const r = await activarPush(datos.clave_publica)
      if (r === 'activados') {
        setEstado('activados')
        setMensaje(PUSH.activaste(s))
        setFoco({ id: ID_DESACTIVAR })
      } else if (r === 'bloqueado') {
        setEstado('bloqueado')
        setFoco({ id: ID_BLOQUEADO })
      } else setMensaje(PUSH.noActivamos)
    } catch (e) {
      if (esVencida(e)) return
      // 2.3: sin MensajeError. `activarPush` ya borró la suscripción del navegador; pasa a G con el foco en la nota.
      if (esNoPermitido(e)) {
        setEstado('no-permitido')
        setAnunciarG(true)
        setFoco({ id: ID_NO_PERMITIDO })
      } else setError(PUSH.errActivar)
    } finally {
      setOcupado(null)
    }
  }

  const desactivar = async () => {
    if (ocupado) return
    setOcupado('desactivar')
    setMensaje(null)
    setError(null)
    onAccion?.()
    try {
      await desactivarPush()
      // 2.2, caso borde: sin permiso, queda solo la nota G y el foco va a ella.
      const sinPermiso = estado === 'no-permitido-inscrito'
      setEstado(sinPermiso ? 'no-permitido' : 'sin-activar')
      setMensaje(PUSH.desactivaste(s))
      setFoco({ id: sinPermiso ? ID_NO_PERMITIDO : ID_ACTIVAR })
    } catch (e) {
      if (!esVencida(e)) setError(PUSH.errDesactivar)
    } finally {
      setOcupado(null)
    }
  }

  const avisos = (
    <>
      {mensaje && (
        <Anunciado urgencia="status" como="p" className="text-base">
          {mensaje}
        </Anunciado>
      )}
      {error && (
        <Anunciado urgencia="alert">
          <MensajeError>{error}</MensajeError>
        </Anunciado>
      )}
    </>
  )

  let cuerpo
  if (push.estado === 'error') cuerpo = <ErrorLectura texto={PUSH.errCargar(s)} reintentar={reintentar} />
  else if (!estado || clase === undefined) cuerpo = <Cargando />
  // MATU-107, estado G (2.2): manda sobre los demás. Sin Etiqueta ni «Activar», y el permiso nunca se pide.
  else if (estado === 'no-permitido' || estado === 'no-permitido-inscrito')
    cuerpo = (
      <>
        <Nota id={ID_NO_PERMITIDO} tono="rocio" iconoEnLinea enfocable rol={anunciarG ? 'status' : undefined}>
          {PUSH.noPermitido}
        </Nota>
        {estado === 'no-permitido-inscrito' && (
          <Boton id={ID_DESACTIVAR} variante="secundario" className="angosto:self-stretch" ocupado={ocupado === 'desactivar'} textoOcupado={PUSH.desactivando} onClick={() => void desactivar()}>
            {PUSH.desactivar(s)}
          </Boton>
        )}
        {avisos}
      </>
    )
  else if (estado === 'ios-sin-instalar')
    cuerpo = (
      <Nota tono="rocio" titulo={PUSH.iosTitulo} iconoEnLinea>
        <ol className="list-decimal ps-5">
          <li>
            {PUSH.iosPaso1[0]} <Share role="img" aria-label={PUSH.iosCompartir} className="inline size-5 align-text-bottom" /> {PUSH.iosPaso1[1]}
          </li>
          <li>{PUSH.iosPaso2}</li>
          <li>{PUSH.iosPaso3}</li>
        </ol>
      </Nota>
    )
  else if (estado === 'sin-soporte')
    cuerpo = (
      <Nota tono="rocio">
        {PUSH.sinSoporte} {PUSH.porCorreo}
      </Nota>
    )
  else if (estado === 'sin-clave') cuerpo = <Nota tono="rocio">{PUSH.sinClave(s)}</Nota>
  else
    cuerpo = (
      <>
        {estado === 'activados' ? (
          <Etiqueta tono="ok">
            <Check aria-hidden className="size-4 shrink-0" strokeWidth={3} />
            {PUSH.activados}
          </Etiqueta>
        ) : (
          <Etiqueta>
            <Circle aria-hidden className="size-3.5 shrink-0" strokeWidth={2.5} />
            {PUSH.sinActivar}
          </Etiqueta>
        )}
        {estado === 'sin-activar' && <p className="max-w-prose text-base text-tenue">{PUSH.ayudaActivar}</p>}
        {estado === 'bloqueado' && (
          <Nota id={ID_BLOQUEADO} tono="atenta" enfocable>
            {PUSH.bloqueado}
          </Nota>
        )}
        {estado === 'activados' && (
          <Boton id={ID_DESACTIVAR} variante="secundario" className="angosto:self-stretch" ocupado={ocupado === 'desactivar'} textoOcupado={PUSH.desactivando} onClick={() => void desactivar()}>
            {PUSH.desactivar(s)}
          </Boton>
        )}
        {estado === 'sin-activar' && (
          <Boton id={ID_ACTIVAR} variante="secundario" className="angosto:self-stretch" ocupado={ocupado === 'activar'} textoOcupado={PUSH.activando} onClick={() => void activar()}>
            {PUSH.activar(s)}
          </Boton>
        )}
        {avisos}
      </>
    )

  return (
    <div className="mt-1 flex flex-col items-start gap-3 border-l-4 border-linea ps-4 angosto:ps-2">
      {/* Mientras no se sabe la clase (E1), sin título: no se dice «navegador» para corregirlo después. */}
      {clase !== undefined && <h3 className="text-lg font-bold">{DONDE.este(clase)}</h3>}
      {cuerpo}
    </div>
  )
}

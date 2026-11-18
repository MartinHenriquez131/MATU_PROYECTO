// Los avisos en «Tu cuenta» (MATU-55, especificación 3.3 y 3.4, y MATU-76, especificación 2), en tres
// tarjetas: A, «Avisos cuando un insumo se está acabando»; B, «Avisos de tus pedidos», con la nota fija
// del dinero (D-76-3), y C, «Este teléfono» (`GET /v1/dispositivos/actual/push` y la suscripción del
// navegador), que sirve para los dos tipos. Las dos preferencias llegan en el mismo `GET /v1/yo/avisos`
// y valen para todos los grupos. Cada casilla se guarda al marcarla con el `PUT` y queda en
// «Guardando…» hasta el 200 (E3). El aviso del teléfono es siempre el mismo texto genérico, que pone
// `web/public/sw.js` (D-76-1 a). El permiso de avisos del navegador se pide solo al tocar «Activar en
// este…» (D6-a). Nada se guarda en el navegador.
import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Check, Circle, Info, Share } from 'lucide-react'
import { guardarAvisos, leerAvisos, leerPushActual, listarDispositivos, type ClaseDispositivo, type PreferenciaAvisos, type PushActual, type SolicitudAvisos } from '../compartido/api/familia'
import { leerFallo } from '../compartido/api/cliente'
import { esVencida } from '../compartido/api/sesion'
import { Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { useDemora } from './Estados'
import { activarPush, desactivarPush, estadoPush, type EstadoPush } from './push'
import { Etiqueta, MensajeError, Nota } from './ui'
import { GENERAL } from './textos'
import { AVISOS, AVISOS_PEDIDO, DONDE, PUSH, sustantivo } from './textosDondeEntraste'

/** La tarjeta A (insumo) o la B (pedido). */
type Tarjeta = 'insumo' | 'pedido'
type Canal = 'correo' | 'push'
type Casilla = `${Tarjeta}.${Canal}`
type Carga<T> = { estado: 'cargando' } | { estado: 'error' } | { estado: 'lista'; datos: T }

const esCanales = (p: unknown): p is { correo: boolean; push: boolean } =>
  !!p && typeof p === 'object' && typeof (p as PreferenciaAvisos).correo === 'boolean' && typeof (p as PreferenciaAvisos).push === 'boolean'
const esPreferencia = (p: unknown): p is PreferenciaAvisos => esCanales(p) && esCanales((p as PreferenciaAvisos).pedido)
const valorDe = (p: PreferenciaAvisos, t: Tarjeta, c: Canal) => (t === 'insumo' ? p[c] : p.pedido[c])
const conValor = (p: PreferenciaAvisos, t: Tarjeta, c: Canal, v: boolean): PreferenciaAvisos =>
  t === 'insumo' ? { ...p, [c]: v } : { ...p, pedido: { ...p.pedido, [c]: v } }
const esPush = (p: unknown): p is PushActual => !!p && typeof p === 'object' && typeof (p as PushActual).registrado === 'boolean'

/** `anunciar` en `false` cuando otra tarjeta ya anuncia la misma espera (MATU-76, P3 de la revisión: un solo anuncio). */
function Cargando({ anunciar = true }: { anunciar?: boolean }) {
  const ver = useDemora()
  return (
    <p role={anunciar ? 'status' : undefined} className="text-tenue">
      {ver ? GENERAL.cargando : ''}
    </p>
  )
}

/** `anunciar` en `false` cuando otra tarjeta ya anuncia el mismo error (MATU-76, 2.6: un solo anuncio). */
function ErrorLectura({ texto, reintentar, anunciar = true }: { texto: string; reintentar: () => void; anunciar?: boolean }) {
  return (
    <div className="flex max-w-prose flex-col items-start gap-4">
      <Nota tono="pronto" rol={anunciar ? 'alert' : undefined}>
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

// ---------------------------------------------------------------- 3.3 y MATU-76 (2.5): las preferencias

const TARJETA = 'max-w-xl rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea'

export function AvisosCuenta() {
  const uid = useId()
  const preferencia = useLectura<PreferenciaAvisos>(leerAvisos, esPreferencia)
  const push = useLectura<PushActual>(leerPushActual, esPush)
  const clase = useClaseActual()
  const [guardada, setGuardada] = useState<PreferenciaAvisos | null>(null)
  const [pendiente, setPendiente] = useState<{ tarjeta: Tarjeta; canal: Canal; valor: boolean } | null>(null)
  // MATU-76 (2.6): los estados de guardar van solo en la tarjeta de la casilla que se tocó.
  const [aviso, setAviso] = useState<{ tarjeta: Tarjeta; estado: 'guardando' | 'guardado' | 'error' } | null>(null)
  const casillas = useRef<Partial<Record<Casilla, HTMLInputElement | null>>>({})
  // 1.2 (criterio 16): el foco vuelve a la casilla después del render que termina de guardar.
  const [focoCasilla, setFocoCasilla] = useState<{ casilla: Casilla } | null>(null)
  // P3: cada bloque borra el mensaje del otro. Sube cuando se toca una casilla.
  const [casillaTocada, setCasillaTocada] = useState(0)

  useEffect(() => {
    if (focoCasilla) casillas.current[focoCasilla.casilla]?.focus()
  }, [focoCasilla])

  const base = guardada ?? (preferencia.carga.estado === 'lista' ? preferencia.carga.datos : null)
  const ver = base && pendiente ? conValor(base, pendiente.tarjeta, pendiente.canal, pendiente.valor) : base

  const cambiar = async (tarjeta: Tarjeta, canal: Canal, valor: boolean) => {
    if (!base || pendiente) return
    setPendiente({ tarjeta, canal, valor })
    setAviso({ tarjeta, estado: 'guardando' })
    setCasillaTocada((n) => n + 1)
    const nueva = conValor(base, tarjeta, canal, valor)
    // Las dos preferencias se guardan por separado: al tocar la A, el `PUT` va sin `pedido` y la del
    // pedido no cambia (decisión 473). `correo` y `push` del insumo van siempre, porque son obligatorios.
    const solicitud: SolicitudAvisos = tarjeta === 'insumo' ? { correo: nueva.correo, push: nueva.push } : { correo: nueva.correo, push: nueva.push, pedido: nueva.pedido }
    try {
      const r = await guardarAvisos(solicitud)
      setGuardada(esPreferencia(r) ? r : nueva)
      setAviso({ tarjeta, estado: 'guardado' })
    } catch (e) {
      if (esVencida(e)) return setAviso(null)
      // 422 solo puede pasar por un defecto: se trata como el error. La casilla vuelve a lo de antes.
      setAviso({ tarjeta, estado: 'error' })
    } finally {
      setPendiente(null)
      setFocoCasilla({ casilla: `${tarjeta}.${canal}` })
    }
  }

  // 8 de la sección 6: la nota del piloto se ve mientras `envio_simulado` sea `true`, y también si la lectura falla.
  const piloto = push.carga.estado !== 'lista' || push.carga.datos.envio_simulado

  const casilla = (tarjeta: Tarjeta, canal: Canal, texto: string, describe?: string) => {
    const clave: Casilla = `${tarjeta}.${canal}`
    return (
      <label className="flex min-h-12 cursor-pointer items-center gap-3 angosto:items-start font-bold has-aria-disabled:cursor-not-allowed">
        <input
          ref={(n) => {
            casillas.current[clave] = n
          }}
          type="checkbox"
          checked={ver ? valorDe(ver, tarjeta, canal) : false}
          aria-describedby={describe}
          // 1.2: `aria-disabled` y no `disabled`, que saca el foco de la casilla y lo deja en el body.
          // MATU-76 (2.6): las cuatro a la vez, porque el `PUT` lleva las dos preferencias juntas.
          aria-disabled={pendiente !== null || undefined}
          aria-busy={(pendiente?.tarjeta === tarjeta && pendiente.canal === canal) || undefined}
          onChange={(e) => {
            if (pendiente === null) void cambiar(tarjeta, canal, e.target.checked)
          }}
          className="size-6 shrink-0 accent-turquesa aria-disabled:not-focus-visible:opacity-60 angosto:mt-0.5"
        />
        {texto}
      </label>
    )
  }

  const tarjeta = (t: Tarjeta) => {
    const id = `${uid}-${t}`
    const titulo = t === 'insumo' ? AVISOS.leyenda : AVISOS_PEDIDO.leyenda
    const ayuda = t === 'insumo' ? AVISOS.ayuda : AVISOS_PEDIDO.ayuda
    const estado = aviso?.tarjeta === t ? aviso.estado : null
    return (
      <div className={`${t === 'pedido' ? 'mt-6 ' : ''}${TARJETA}`}>
        <fieldset aria-describedby={`${id}-a ${id}-g`} className="flex min-w-0 flex-col gap-3">
          <legend className="pb-3">
            <h2 className="text-xl font-bold leading-snug">{titulo}</h2>
          </legend>
          <p id={`${id}-a`} className="max-w-prose text-base text-tenue">
            {ayuda}
          </p>
          <p id={`${id}-g`} className="text-base font-bold">
            {AVISOS.alcance}
          </p>

          {/* La espera también se anuncia una sola vez, desde la A; en la B se ve el mismo texto, sin rol. */}
          {preferencia.carga.estado === 'cargando' && <Cargando anunciar={t === 'insumo'} />}
          {/* 2.6: el error de carga se anuncia una sola vez, desde la A. Cualquiera de los dos botones vuelve a leer las dos. */}
          {preferencia.carga.estado === 'error' && <ErrorLectura texto={AVISOS.errCargar} anunciar={t === 'insumo'} reintentar={() => void preferencia.cargar()} />}
          {ver && (
            <div className="flex flex-col gap-1">
              {casilla(t, 'correo', AVISOS.correo, t === 'pedido' ? `${id}-dinero` : undefined)}
              {/* 2.5: la nota del dinero, siempre visible, alineada con el texto de la etiqueta (24 px de la casilla y 12 del gap). */}
              {t === 'pedido' && (
                <p id={`${id}-dinero`} className="max-w-prose ps-9 text-base text-tenue">
                  {AVISOS_PEDIDO.dinero}
                </p>
              )}
              {casilla(t, 'push', AVISOS.push)}
              {estado === 'guardando' && (
                <Anunciado urgencia="status" como="p" className="mt-2 text-base text-tenue">
                  {AVISOS.guardando}
                </Anunciado>
              )}
              {estado === 'guardado' && (
                <Anunciado urgencia="status" como="p" className="mt-2 text-base">
                  {AVISOS.guardado}
                </Anunciado>
              )}
              {estado === 'error' && (
                <Anunciado urgencia="alert" className="mt-2">
                  <MensajeError>{AVISOS.errGuardar}</MensajeError>
                </Anunciado>
              )}
            </div>
          )}
        </fieldset>
      </div>
    )
  }

  return (
    <>
      {tarjeta('insumo')}
      {tarjeta('pedido')}
      {/* E4, ampliada en MATU-76 (2.1): la tarjeta C se ve si al menos una «En tus teléfonos» está marcada.
          Con las dos desmarcadas se oculta y la inscripción no se borra. Mientras la preferencia carga o falla, no se ve. */}
      {ver && (
        <div hidden={!(ver.push || ver.pedido.push)} className="mt-6">
          <EsteTelefono push={push.carga} clase={clase} reintentar={() => void push.cargar()} casillaTocada={casillaTocada} onAccion={() => setAviso(null)} />
        </div>
      )}
      {/* Una sola vez, después de la última tarjeta de avisos. */}
      {piloto && (
        <div className="mt-6 max-w-xl">
          <Nota tono="atenta" icono={<Info aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
            {AVISOS.piloto}
          </Nota>
        </div>
      )}
    </>
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
  const tituloId = useId()

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

  // MATU-76 (2.7): una tarjeta propia, con su h2 y su ayuda, salvo en G, donde la nota ya lo dice todo.
  const enG = estado === 'no-permitido' || estado === 'no-permitido-inscrito'
  return (
    <section aria-labelledby={clase !== undefined ? tituloId : undefined} className={`flex flex-col items-start gap-3 ${TARJETA}`}>
      {/* Mientras no se sabe la clase (E1), sin título: no se dice «navegador» para corregirlo después. */}
      {clase !== undefined && (
        <h2 id={tituloId} className="text-xl font-bold leading-snug">
          {DONDE.este(clase)}
        </h2>
      )}
      {!enG && <p className="max-w-prose text-base text-tenue">{PUSH.ayudaTarjeta}</p>}
      {cuerpo}
    </section>
  )
}

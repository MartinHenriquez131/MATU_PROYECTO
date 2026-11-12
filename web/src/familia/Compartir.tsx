// Compartir la ficha con un relevo y cortar el acceso (MATU-48, docs/diseno/matu-48-compartir.md),
// copiado de `Compartir`, `EnlacePin` y `Enlaces` de la demo (Demo/src/familia/Ficha.tsx). Contrato:
// `POST` y `GET …/plan/accesos-relevo` y `DELETE /v1/accesos-relevo/{id}` (docs/api/openapi.json).
//
// Datos sensibles en el cliente (CLAUDE.md, agente 3, punto 5):
// - El nombre y el teléfono del relevo viven solo en el estado del formulario; los campos parten
//   vacíos y con `autoComplete="off"`.
// - El PIN y la URL del 201 pasan a `/compartir/listo` en memoria (`entregarCreado`) y quedan solo en
//   el estado de esa pantalla: nunca en el almacenamiento del navegador, la URL, `history.state`,
//   `document.title` ni la región `aria-live` global. Al salir o recargar, se pierden.
// - Lo que se envía o se copia es la URL, nunca el PIN. Sin servicios de terceros (nada de `wa.me`).
// - Ningún error se registra en la consola: los de Axios llevan el cuerpo (nombre, teléfono, PIN).
// - Ningún control para imprimir, descargar ni exportar la ficha (ADR-029).
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { CircleAlert, CircleCheck, CirclePause, Clock3, CloudOff, Copy, KeyRound, Link2, Phone, Send, ShieldAlert, TimerOff, Unlink } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import {
  cortarAcceso,
  crearAcceso,
  leerFicha,
  listarAccesos,
  listarAperturas,
  nombrePilaDe,
  type AccesoCreado,
  type AccesoResumen,
  type Apertura,
  type CampoApi,
  type MotivoAcceso,
} from '../compartido/api/familia'
import { esVencida } from '../compartido/api/sesion'
import { fechaYHoraDeChile, finDeSemanaDeChile, restante } from '../compartido/fechas'
import { ordenar, TITULO_SECCION } from '../compartido/secciones'
import { Boton, claseBoton } from '../compartido/ui/Boton'
import { registrarSinGuardar } from '../compartido/version'
import { CAMPOS, PATRON_CELULAR } from './datos'
import { useDemora } from './Estados'
import { puedeCompartir, useFamilia } from './estado'
import { AvisoBloqueo, bloqueoDe, ErrorAlCargar, SinAcceso, useFicha } from './Ficha'
import { ErrorAperturas, LineaApertura } from './QuienLaVio'
import { navegar, type Ruta } from './ruteo'
import { seccionesEnHoja } from './Secciones'
import { ConfirmacionRemedios, ElegirSecciones, seccionesAgregadas, useEleccionSecciones } from './SeccionesCompartir'
import { COMPARTIR as T, COMPARTIR_SECCIONES, FICHA, GENERAL, loQueVeAcceso, QUIEN } from './textos'
import { nombreDeAutor } from './autor'
import { GRUPO_FAMILIAR } from './textosGrupo'
import { Acciones, CampoTexto, Etiqueta, GrupoOpciones, HojaFicha, MensajeError, Nota, Pagina, Pestanas, Stepper, Titulo } from './ui'

const HORA = 3_600_000
const DIA = 24 * HORA

/** Las dos vistas de la sección (2.2). `/compartir/listo` no las lleva. */
function PestanasCompartir({ activa }: { activa: Ruta }) {
  return (
    <Pestanas
      etiqueta={T.vistas}
      items={[
        { texto: T.titulo, ruta: '/compartir', activa: activa === '/compartir' },
        { texto: T.enlaces, ruta: '/compartir/enlaces', activa: activa === '/compartir/enlaces' },
      ]}
    />
  )
}

function Cargando() {
  const ver = useDemora()
  return (
    <p role="status" className="text-tenue">
      {ver ? GENERAL.cargando : ''}
    </p>
  )
}

/** «{antes}{fecha}{medio}{hora}{despues}», con la fecha y la hora de Chile en `cifras`. */
function FechaHora({ iso, partes, negrita = false }: { iso: string | Date; partes: readonly [string, string, string]; negrita?: boolean }) {
  const d = typeof iso === 'string' ? new Date(iso) : iso
  if (Number.isNaN(d.getTime())) return null
  const { fecha, hora } = fechaYHoraDeChile(d)
  const Cifra = negrita ? 'b' : 'span'
  return (
    <>
      {partes[0]}
      <Cifra className="cifras">{fecha}</Cifra>
      {partes[1]}
      <Cifra className="cifras">{hora}</Cifra>
      {partes[2]}
    </>
  )
}

// ---------------------------------------------------------------- 3. Crear un enlace

type Vigencia = '24h' | 'finde' | 'dias'
const VIGENCIAS: { valor: Vigencia; texto: string }[] = (['24h', 'finde', 'dias'] as const).map((v) => ({ valor: v, texto: T.vigencias[v] }))
const MOTIVOS: { valor: MotivoAcceso; texto: string }[] = (Object.keys(T.motivos) as MotivoAcceso[]).map((m) => ({ valor: m, texto: T.motivos[m] }))

/** 3.5: el vencimiento, en el momento de calcularlo. Con 30 días se resta un minuto (relojes). */
function venceDe(vigencia: Vigencia, dias: number, ahora: Date): Date {
  if (vigencia === '24h') return new Date(ahora.getTime() + DIA)
  if (vigencia === 'finde') return finDeSemanaDeChile(ahora)
  return new Date(ahora.getTime() + dias * DIA - (dias >= 30 ? 60_000 : 0))
}

export function Compartir() {
  const { ficha, persona, personaId } = useFamilia()
  const { carga, pedir } = useFicha()
  const antes = <PestanasCompartir activa="/compartir" />
  if (carga.tipo === 'bloqueo' && carga.bloqueo === 'sin-acceso') return <SinAcceso />
  let cuerpo: ReactNode = null
  if (carga.tipo === 'cargando') cuerpo = <Cargando />
  else if (carga.tipo === 'red') cuerpo = <ErrorAlCargar reintentar={() => void pedir()} />
  // 3.6: sin autorización no se crea nada, pero «Enlaces» sigue disponible (decisión 18).
  else if (carga.tipo === 'bloqueo' && carga.bloqueo !== 'sin-acceso') cuerpo = <AvisoBloqueo bloqueo={carga.bloqueo} />
  if (cuerpo || !ficha || !personaId)
    return (
      <Pagina titulo={T.titulo} bajada={T.bajada} antes={antes}>
        {cuerpo}
      </Pagina>
    )
  return (
    <Pagina titulo={T.titulo} bajada={T.bajada} antes={antes}>
      <Formulario key={personaId} personaId={personaId} pila={persona ? nombrePilaDe(persona) : ''} />
    </Pagina>
  )
}

type Errores = Partial<Record<'nombre' | 'telefono' | 'avise' | 'vigencia', string>>
type Falla = 'seccion' | 'no-encontrado' | 'no-disponible' | 'red' | null

const ID_NOMBRE = 'compartir-nombre'
const ID_TELEFONO = 'compartir-telefono'
const ID_AVISE = 'compartir-avise'

const DIAS_INICIALES = 3

function Formulario({ personaId, pila }: { personaId: string; pila: string }) {
  const { ficha, fijar, sinGuardar } = useFamilia()
  const eleccion = useEleccionSecciones()
  const [nombre, setNombre] = useState('')
  const [telefono, setTelefono] = useState('')
  const [vigencia, setVigencia] = useState<Vigencia>('24h')
  const [dias, setDias] = useState(DIAS_INICIALES)
  const [motivo, setMotivo] = useState<MotivoAcceso>('salgo_unas_horas')
  const [avise, setAvise] = useState(false)
  const [errores, setErrores] = useState<Errores>({})
  const [confirmar, setConfirmar] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [falla, setFalla] = useState<Falla>(null)
  const [bloqueo, setBloqueo] = useState<'sin-consentimiento' | 'revision-vencida' | 'sin-acceso' | null>(null)

  // MATU-67 (revisión visual del 09-11): con el nombre, el teléfono o los días cambiados, «Recargar»
  // del aviso de versión nueva pregunta antes, con el título genérico.
  const datos = useRef({ nombre, telefono, dias })
  datos.current = { nombre, telefono, dias }
  useEffect(
    () =>
      registrarSinGuardar(sinGuardar, () => {
        const d = datos.current
        if (!d.nombre && !d.telefono && d.dias === DIAS_INICIALES) return null
        // Los campos se ubican por su `name`; «Seguir escribiendo» pide el id del que cambió.
        const nombreDelCampo = d.nombre ? ID_NOMBRE : d.telefono ? ID_TELEFONO : null
        return { texto: '', foco: nombreDelCampo ? (document.querySelector(`[name="${nombreDelCampo}"]`)?.id ?? null) : null }
      }),
    [sinGuardar],
  )

  const quien = nombre.trim() || T.quienTeReemplaza
  const vence = venceDe(vigencia, dias, new Date())
  const agregadas = seccionesAgregadas(ficha)
  const vacios = CAMPOS.filter((c) => !ficha?.campos[c.api]?.texto?.trim()).map((c) => c.titulo)
  const textos = Object.fromEntries(CAMPOS.map((c) => [c.api, ficha?.campos[c.api]?.texto ?? null])) as Record<CampoApi, string | null>
  const hoja = seccionesEnHoja(ficha).filter((s) => eleccion.paraEnviar.includes(s.api))

  /** Al enviar, nunca mientras escribe. El foco va al primer campo con error (3.5). */
  const validar = () => {
    const e: Errores = {}
    if (!nombre.trim()) e.nombre = T.errNombre
    if (!PATRON_CELULAR.test(telefono.trim())) e.telefono = T.errTelefono
    if (!avise) e.avise = T.errAvise(quien)
    setErrores(e)
    const primero = e.nombre ? ID_NOMBRE : e.telefono ? ID_TELEFONO : e.avise ? ID_AVISE : null
    if (primero) window.setTimeout(() => document.querySelector<HTMLInputElement>(`[name="${primero}"]`)?.focus(), 0)
    return !primero
  }

  const enviar = async () => {
    if (ocupado) return
    setOcupado(true)
    setFalla(null)
    try {
      const creado = await crearAcceso(personaId, {
        nombre_relevo: nombre.trim(),
        telefono_relevo: telefono.trim(),
        secciones_adicionales: eleccion.paraEnviar,
        expira_en: venceDe(vigencia, dias, new Date()).toISOString(),
        motivo,
        relevo_informado: true,
      })
      entregarCreado(creado)
      // «Atrás» no vuelve al formulario lleno: no se crea un segundo enlace sin querer (3.5).
      navegar('/compartir/listo', { reemplazar: true })
    } catch (e) {
      setConfirmar(false)
      if (esVencida(e)) return
      const f = leerFallo(e)
      if (f.status === 403) {
        const b = f.tipo === '/errores/revision-vencida' ? 'revision-vencida' : 'sin-consentimiento'
        fijar({ autorizacion: b })
        return setBloqueo(b)
      }
      if (f.status === 404) return setFalla('no-encontrado')
      if (f.status === 503) return setFalla('no-disponible')
      if (f.status !== 422) return setFalla('red')
      // 422: por `errores[].campo` y `.tipo`, nunca el `mensaje` de la API.
      const campo = (c: string) => c.split('.').pop() ?? c
      const nuevos: Errores = {}
      let seccion = false
      for (const x of f.errores) {
        const c = campo(x.campo)
        if (c === 'nombre_relevo') nuevos.nombre = T.errNombre
        else if (c === 'telefono_relevo') nuevos.telefono = T.errTelefono
        else if (c === 'relevo_informado') nuevos.avise = T.errAvise(quien)
        else if (c === 'expira_en') nuevos.vigencia = x.tipo === 'vigencia_pasada' ? T.errPasada : T.errMaxima
        else if (c === 'secciones_adicionales' && x.tipo === 'seccion_no_agregada') seccion = true
      }
      if (seccion) {
        setFalla('seccion')
        // Se vuelve a leer la ficha; lo elegido que sigue existiendo queda marcado.
        try {
          const nueva = await leerFicha(personaId)
          fijar({ ficha: nueva })
          const siguen = seccionesAgregadas(nueva)
          eleccion.setElegidas(eleccion.elegidas.filter((s) => siguen.includes(s)))
          if (!siguen.includes('remedios')) eleccion.setRemedios(false)
        } catch {
          // Si no se pudo leer, la nota ya pide revisar y volver a crear el enlace.
        }
      } else if (!Object.keys(nuevos).length) setFalla('red')
      setErrores(nuevos)
      const primero = nuevos.nombre ? ID_NOMBRE : nuevos.telefono ? ID_TELEFONO : nuevos.avise ? ID_AVISE : nuevos.vigencia ? 'vigencia' : null
      if (primero) window.setTimeout(() => document.querySelector<HTMLInputElement>(`[name="${primero}"]`)?.focus(), 0)
    } finally {
      setOcupado(false)
    }
  }

  const crear = () => {
    if (ocupado) return
    setFalla(null)
    if (!validar()) return
    // 3.5.1: con Sus remedios, primero la confirmación; nada se pide a la API todavía.
    if (eleccion.remedios) return setConfirmar(true)
    void enviar()
  }

  if (bloqueo === 'sin-acceso') return <SinAcceso />
  if (bloqueo) return <AvisoBloqueo bloqueo={bloqueo} />

  const nota =
    falla === 'seccion' ? (
      <Nota tono="atenta" rol="alert">
        {T.errSeccion}
      </Nota>
    ) : falla ? (
      <Nota tono="pronto" rol="alert">
        {falla === 'no-encontrado' ? GENERAL.noEncontrado : falla === 'no-disponible' ? T.noDisponible : GENERAL.error}
      </Nota>
    ) : null

  return (
    <div className="grid grid-cols-1 items-start gap-10 @4xl/main:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
      <section aria-label="Datos del enlace" className="flex max-w-3xl min-w-0 flex-col gap-7">
        <div className="grid grid-cols-1 items-start gap-4 @2xl/main:grid-cols-2">
          <CampoTexto
            etiqueta={T.nombre}
            name={ID_NOMBRE}
            value={nombre}
            maxLength={60}
            autoComplete="off"
            ayuda={T.nombreAyuda}
            ayudaGrande
            error={errores.nombre}
            onChange={(e) => {
              setNombre(e.target.value)
              setConfirmar(false)
            }}
          />
          <CampoTexto
            etiqueta={T.telefono}
            name={ID_TELEFONO}
            type="tel"
            inputMode="tel"
            value={telefono}
            autoComplete="off"
            ayuda={T.telefonoAyuda}
            ayudaGrande
            error={errores.telefono}
            onChange={(e) => setTelefono(e.target.value)}
          />
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          <ElegirSecciones
            agregadas={agregadas}
            elegidas={eleccion.elegidas}
            onElegidas={eleccion.setElegidas}
            remedios={eleccion.remedios}
            onRemedios={(v) => {
              eleccion.setRemedios(v)
              if (!v) setConfirmar(false)
            }}
          />
          {vacios.length > 0 && <p className="max-w-prose text-base text-tenue">{T.vacios(vacios, quien)}</p>}
          <p className="max-w-prose text-base text-tenue">{T.recordatorio(pila)}</p>
        </div>

        <GrupoOpciones
          forma="chips"
          leyenda={T.hastaCuando}
          nombre="vigencia"
          opciones={VIGENCIAS}
          valor={vigencia}
          error={errores.vigencia}
          onCambio={(v) => {
            setVigencia(v)
            setConfirmar(false)
            setErrores((x) => ({ ...x, vigencia: undefined }))
          }}
        >
          {vigencia === 'dias' && (
            <Stepper
              etiqueta={T.cuantosDias}
              valor={dias}
              min={1}
              max={30}
              unidad={T.dias}
              ayuda={T.hasta30}
              onCambio={(n) => {
                setDias(n)
                setConfirmar(false)
                setErrores((x) => ({ ...x, vigencia: undefined }))
              }}
            />
          )}
          <p className="flex items-start gap-2" aria-live="polite">
            <Clock3 aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />
            <span className="min-w-0">
              <FechaHora iso={vence} partes={T.vence} negrita />
            </span>
          </p>
        </GrupoOpciones>

        <GrupoOpciones forma="chips" leyenda={T.paraQue} nombre="motivo" opciones={MOTIVOS} valor={motivo} onCambio={setMotivo} />

        {/* Decisión 34: obligatoria; sin marcar no se pide nada a la API. Desmarcada en cada visita. */}
        <div className="flex flex-col gap-2">
          <label
            htmlFor={ID_AVISE}
            className={`flex min-h-12 cursor-pointer items-start gap-3 angosto:flex-col angosto:gap-2 rounded border bg-hoja p-4 angosto:p-2 ${errores.avise ? 'border-pronto' : 'border-borde'}`}
          >
            <input
              id={ID_AVISE}
              name={ID_AVISE}
              type="checkbox"
              checked={avise}
              aria-invalid={errores.avise ? true : undefined}
              aria-describedby={errores.avise ? `${ID_AVISE}-e` : undefined}
              onChange={(e) => {
                setAvise(e.target.checked)
                if (e.target.checked) setErrores((x) => ({ ...x, avise: undefined }))
              }}
              className="mt-0.5 size-6 shrink-0 accent-turquesa"
            />
            <span className="min-w-0 font-bold break-words">{T.avise(quien)}</span>
          </label>
          {errores.avise && <MensajeError id={`${ID_AVISE}-e`}>{errores.avise}</MensajeError>}
        </div>

        {nota}
        {confirmar ? (
          <ConfirmacionRemedios
            nombre={quien}
            vence={vence}
            ocupado={ocupado}
            onSi={() => void enviar()}
            onNo={() => {
              eleccion.setRemedios(false)
              setConfirmar(false)
            }}
          />
        ) : (
          <Acciones>
            <Boton icono={<Link2 aria-hidden className="size-5" />} ocupado={ocupado} textoOcupado={T.creando} onClick={crear}>
              {T.crear}
            </Boton>
          </Acciones>
        )}
      </section>

      <section aria-labelledby="vera-t" className="flex max-w-prose min-w-0 flex-col gap-5 self-start @4xl/main:sticky @4xl/main:top-4 @4xl/main:max-w-none">
        <h2 id="vera-t" className="text-xl font-bold leading-snug break-words">
          {T.loQueVera(quien)}
        </h2>
        <HojaFicha pila={pila} textos={textos} secciones={hoja} />
      </section>
    </div>
  )
}

// ---------------------------------------------------------------- 4. El PIN, una sola vez

/** El 201 pasa de `/compartir` a `/compartir/listo` solo en memoria, y una sola vez. */
let creadoPendiente: AccesoCreado | null = null
function entregarCreado(a: AccesoCreado) {
  creadoPendiente = a
}

export function EnlaceListo() {
  // El estado de esta pantalla es el único lugar donde vive el PIN. Recargar lo pierde (4.6).
  const [creado] = useState(() => creadoPendiente)
  useEffect(() => {
    creadoPendiente = null
  }, [])
  return creado ? <PinUnaVez a={creado} /> : <PinPerdido />
}

function PinPerdido() {
  return (
    <div className="flex max-w-prose flex-col gap-5">
      <Titulo>{T.creado}</Titulo>
      <Nota tono="rocio" titulo={T.pinPerdidoTitulo} icono={<KeyRound aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
        {T.pinPerdido}
      </Nota>
      <Acciones>
        <Boton icono={<Link2 aria-hidden className="size-5" />} onClick={() => navegar('/compartir')}>
          {T.crearNuevo}
        </Boton>
        <Boton variante="secundario" onClick={() => navegar('/compartir/enlaces')}>
          {T.verEnlaces}
        </Boton>
      </Acciones>
    </div>
  )
}

/** La URL cortada: origen, `/r#` y los seis primeros caracteres del token. Nunca el token completo. */
export function urlCorta(url: string) {
  const [base, token = ''] = url.split('#')
  return `${base.replace(/^https?:\/\//, '')}#${token.slice(0, 6)}…`
}

function PinUnaVez({ a }: { a: AccesoCreado }) {
  const nombre = a.nombre_relevo
  const puedeEnviar = typeof navigator !== 'undefined' && typeof navigator.share === 'function'
  const [copia, setCopia] = useState<'ok' | 'fallo' | null>(null)
  const [dictaselo, resto] = T.dictaselo(nombre)
  const titulos = ordenar(a.secciones_adicionales).map((s) => TITULO_SECCION[s])
  const camposAcceso = CAMPOS.filter((c) => a.campos.includes(c.api)).map((c) => c.titulo)

  const enviar = async () => {
    try {
      await navigator.share({ text: T.mensaje(nombre, a.url) })
    } catch {
      // Cerrar la hoja de compartir (AbortError) no es un error. Nada se registra.
    }
  }
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(a.url)
      setCopia('ok')
    } catch {
      setCopia('fallo')
    }
  }

  return (
    <div className="grid grid-cols-1 items-start gap-x-10 gap-y-7 @3xl/main:grid-cols-2">
      {/* En el teléfono: título, PIN, enviar (D5). En ancho: título y enviar a la izquierda, PIN a la derecha. */}
      <div className="flex min-w-0 flex-col gap-3 @3xl/main:col-start-1 @3xl/main:row-start-1">
        <div className="flex items-center gap-4 angosto:flex-col angosto:items-start angosto:gap-3">
          <span aria-hidden className="grid size-16 shrink-0 place-items-center rounded-2xl bg-rocio text-turquesa">
            <svg viewBox="0 0 24 24" className="size-9" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" pathLength={1} strokeDasharray="1" className="animate-trazo" />
              <path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" pathLength={1} strokeDasharray="1" className="animate-trazo [animation-delay:250ms]" />
            </svg>
          </span>
          <div className="min-w-0">
            <Titulo className="text-3xl break-words">{T.creadoPara(nombre)}</Titulo>
            <p className="mt-1 text-tenue">
              <FechaHora iso={a.expira_en} partes={T.vence} />
            </p>
          </div>
        </div>
      </div>

      <section
        aria-labelledby="pin-t"
        className="flex min-w-0 max-w-lg flex-col gap-4 rounded-xl bg-rocio px-6 py-6 angosto:px-2 @3xl/main:col-start-2 @3xl/main:row-span-2 @3xl/main:row-start-1"
      >
        <h2 id="pin-t" className="flex items-center gap-2 text-xl font-bold">
          <KeyRound aria-hidden className="size-5 shrink-0 text-turquesa" />
          {T.pinTitulo}
        </h2>
        <p role="img" aria-label={`PIN: ${a.pin.split('').join(' ')}`} className="flex justify-center gap-3 angosto:gap-1.5">
          {a.pin.split('').map((d, i) => (
            <span
              key={i}
              aria-hidden
              className="digitos grid h-22 w-17 place-items-center rounded-xl bg-hoja text-6xl leading-none font-bold text-turquesa animate-digito telefono:w-auto telefono:min-w-0 telefono:flex-1 angosto:h-16 angosto:w-auto angosto:min-w-0 angosto:flex-1 angosto:text-3xl"
              style={{ animationDelay: `${600 + i * 160}ms` }}
            >
              {d}
            </span>
          ))}
        </p>
        <p className="text-base">
          <b>{dictaselo}</b>
          {resto}
        </p>
        <p className="flex gap-2 border-t border-linea pt-4 text-base">
          <Phone aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />
          <span className="min-w-0">{T.cuentale(nombre)}</span>
        </p>
      </section>

      <div className="flex min-w-0 flex-col gap-4 @3xl/main:col-start-1 @3xl/main:row-start-2">
        <p className="flex min-w-0 items-center gap-2 border-y border-linea py-3 text-tenue">
          <Link2 aria-hidden className="size-5 shrink-0 text-turquesa" />
          <span className="min-w-0 truncate">{urlCorta(a.url)}</span>
        </p>
        <Acciones>
          {puedeEnviar && (
            <Boton icono={<Send aria-hidden className="size-5" />} onClick={() => void enviar()}>
              {T.enviar}
            </Boton>
          )}
          <Boton variante={puedeEnviar ? 'secundario' : 'principal'} icono={<Copy aria-hidden className="size-5" />} onClick={() => void copiar()}>
            {T.copiar}
          </Boton>
          <Boton variante="texto" onClick={() => navegar('/compartir/enlaces')}>
            {T.verEnlaces}
          </Boton>
        </Acciones>
        <div role="status">
          {copia === 'ok' && (
            <p className="flex gap-2 text-base">
              <CircleCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-ok" />
              <span className="min-w-0">{T.copiado(nombre)}</span>
            </p>
          )}
          {copia === 'fallo' && puedeEnviar && <MensajeError>{T.noCopiado}</MensajeError>}
        </div>
        {/* Sin compartir del sistema y sin portapapeles: el único caso en que la URL se ve completa. */}
        {copia === 'fallo' && !puedeEnviar && (
          <CampoTexto etiqueta={T.enlacePara(nombre)} readOnly value={a.url} autoComplete="off" onFocus={(e) => e.currentTarget.select()} />
        )}
        <div className="flex max-w-prose flex-col gap-1 text-base text-tenue">
          <p>{loQueVeAcceso(camposAcceso, titulos)}</p>
          {titulos.length < 6 && <p>{COMPARTIR_SECCIONES.despues(nombre)}</p>}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- 5. Enlaces

type Carga = 'cargando' | 'lista' | 'red' | 'sin-acceso'

export function Enlaces() {
  const { personaId, rol, anunciar, autorizacion, fijar } = useFamilia()
  const gestiona = puedeCompartir(rol)
  // Decisión 33: con la autorización por renovar, ningún enlace abre aunque la API lo liste como
  // `vigente`. Retirada (MATU-44, decisión 135), la API ya los cortó: no hay pausa, hay corte.
  const enPausa = autorizacion === 'revision-vencida'
  const [carga, setCarga] = useState<Carga>('cargando')
  const [activos, setActivos] = useState<AccesoResumen[]>([])
  const [anteriores, setAnteriores] = useState<AccesoResumen[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [paginas, setPaginas] = useState(0)
  const [masCargando, setMasCargando] = useState(false)
  const [masFallo, setMasFallo] = useState(false)
  const primeraNueva = useRef<string | null>(null)

  const primera = useCallback(async () => {
    if (!personaId) return
    setCarga('cargando')
    setMasFallo(false)
    try {
      const [vigentes, todos] = await Promise.all([listarAccesos(personaId, { estado: 'vigente', limite: 100 }), listarAccesos(personaId, { limite: 20 })])
      setActivos(vigentes.items)
      setAnteriores(todos.items.filter((x) => x.estado !== 'vigente'))
      setCursor(todos.siguiente_cursor)
      setPaginas(1)
      setCarga('lista')
    } catch (e) {
      if (esVencida(e)) return
      // 404: sin acceso, sin decir por qué. 422 (cursor) y el resto: como error al cargar (5.7).
      setCarga(leerFallo(e).status === 404 ? 'sin-acceso' : 'red')
    }
  }, [personaId])

  useEffect(() => {
    void primera()
  }, [primera])

  // Decisión 33: una lectura de la ficha al abrir, la misma de Ficha.tsx, para saber si los enlaces
  // están en pausa también al llegar directo. Si falla por red, la lista se muestra igual.
  useEffect(() => {
    if (!personaId) return
    let vivo = true
    leerFicha(personaId)
      .then((f) => vivo && fijar({ ficha: f, autorizacion: null }))
      .catch((e) => {
        if (!vivo || esVencida(e)) return
        const b = bloqueoDe(e)
        if (b === 'sin-consentimiento' || b === 'revision-vencida') fijar({ autorizacion: b })
      })
    return () => {
      vivo = false
    }
  }, [personaId, fijar])

  const mas = async () => {
    if (!personaId || !cursor || masCargando) return
    setMasCargando(true)
    setMasFallo(false)
    try {
      const r = await listarAccesos(personaId, { cursor, limite: 20 })
      const nuevos = r.items.filter((x) => x.estado !== 'vigente' && !anteriores.some((y) => y.id === x.id))
      primeraNueva.current = nuevos[0]?.id ?? null
      setAnteriores((x) => [...x, ...nuevos])
      setCursor(r.siguiente_cursor)
      setPaginas((n) => n + 1)
      anunciar(T.seAgregaron(nuevos.length))
    } catch (e) {
      if (esVencida(e)) return
      if (leerFallo(e).status === 404) return setCarga('sin-acceso')
      setMasFallo(true)
    } finally {
      setMasCargando(false)
    }
  }

  // 5.5: el foco va a la primera tarjeta nueva.
  useEffect(() => {
    if (!primeraNueva.current) return
    document.getElementById(`enlace-${primeraNueva.current}`)?.focus()
    primeraNueva.current = null
  }, [anteriores])

  if (carga === 'sin-acceso') return <SinAcceso />

  const antes = gestiona ? <PestanasCompartir activa="/compartir/enlaces" /> : undefined
  const vacio = carga === 'lista' && !activos.length && !anteriores.length

  let lista: ReactNode
  if (carga === 'cargando') lista = <Cargando />
  else if (carga === 'red')
    lista = (
      <div className="flex max-w-prose flex-col items-start gap-4">
        <Nota tono="atenta" rol="alert" icono={<CloudOff aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
          {T.errListar}
        </Nota>
        <Boton variante="secundario" onClick={() => void primera()}>
          {T.intentar}
        </Boton>
      </div>
    )
  else if (vacio)
    lista = (
      <div className="flex max-w-prose flex-col items-start gap-4">
        <Nota tono="rocio" icono={<Link2 aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
          {T.sinEnlaces}
        </Nota>
        {gestiona && (
          <Boton icono={<Link2 aria-hidden className="size-5" />} onClick={() => navegar('/compartir')}>
            {T.crearNuevo}
          </Boton>
        )}
      </div>
    )
  else
    lista = (
      <>
        {autorizacion === 'revision-vencida' && <AvisoPausa />}
        {autorizacion === 'sin-consentimiento' && <AvisoRetirada gestiona={gestiona} />}
        <section aria-labelledby="abren-t" className="flex flex-col gap-3">
          <h2 id="abren-t" className="text-xl font-bold leading-snug">
            {T.abrenAhora}
          </h2>
          {activos.length ? (
            <ul className="flex flex-col gap-3">
              {activos.map((a) => (
                <TarjetaEnlace key={a.id} a={a} gestiona={gestiona} enPausa={enPausa} recargar={() => void primera()} />
              ))}
            </ul>
          ) : (
            <p className="text-base text-tenue">{T.ninguno}</p>
          )}
        </section>
        {anteriores.length > 0 && (
          <section aria-labelledby="no-abren-t" className="flex flex-col gap-3">
            <h2 id="no-abren-t" className="text-xl font-bold leading-snug">
              {T.yaNoAbren}
            </h2>
            <ul className="flex flex-col gap-3">
              {anteriores.map((a) => (
                <TarjetaEnlace key={a.id} a={a} gestiona={gestiona} enPausa={enPausa} recargar={() => void primera()} />
              ))}
            </ul>
          </section>
        )}
        {masFallo ? (
          <div className="flex max-w-prose flex-col items-start gap-4">
            <Nota tono="atenta" rol="alert" icono={<CloudOff aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
              {T.errListar}
            </Nota>
            <Boton variante="secundario" onClick={() => void mas()}>
              {T.intentar}
            </Boton>
          </div>
        ) : cursor ? (
          <Boton variante="secundario" className="self-start" ocupado={masCargando} textoOcupado={GENERAL.cargando} onClick={() => void mas()}>
            {T.anteriores}
          </Boton>
        ) : paginas > 1 ? (
          <p className="text-tenue">{T.noHayMas}</p>
        ) : null}
        {gestiona && (
          <Boton variante="secundario" className="self-start" icono={<Link2 aria-hidden className="size-5" />} onClick={() => navegar('/compartir')}>
            {T.crearNuevo}
          </Boton>
        )}
      </>
    )

  return (
    <Pagina titulo={T.enlaces} bajada={T.enlacesBajada} antes={antes}>
      <div className="grid grid-cols-1 items-start gap-10 @3xl/main:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-7">{lista}</div>
        <UltimasAperturasEnlaces />
      </div>
    </Pagina>
  )
}

/** Decisión 33 y lenguaje 9.1: la autorización por renovar, arriba de la lista, con lo que pide 6.4b. */
function AvisoPausa() {
  return (
    <Nota tono="atenta" borde iconoEnLinea titulo={T.pausa} icono={<ShieldAlert aria-hidden className="mt-0.5 size-6 shrink-0 text-atenta" />}>
      {FICHA.revisionPide}
    </Nota>
  )
}

/**
 * MATU-44 4.5: la autorización retirada. Los enlaces ya se cortaron y no vuelven: no es `atenta`,
 * porque no hay nada que hacer para que abran. Admin y cuidador pueden ir a ver los permisos.
 */
function AvisoRetirada({ gestiona }: { gestiona: boolean }) {
  return (
    <div className="flex flex-col items-start gap-1">
      <Nota tono="rocio" borde iconoEnLinea titulo={GRUPO_FAMILIAR.enlacesRetiradaTitulo} icono={<Unlink aria-hidden className="mt-0.5 size-6 shrink-0 text-turquesa" />}>
        {GRUPO_FAMILIAR.enlacesRetirada}
      </Nota>
      {gestiona && (
        <Boton variante="texto" onClick={() => navegar('/grupo')}>
          {GRUPO_FAMILIAR.verPermisos}
        </Boton>
      )}
    </div>
  )
}

const BORDE: Record<AccesoResumen['estado'], string> = {
  vigente: 'border-turquesa',
  bloqueado: 'border-atenta',
  vencido: 'border-linea',
  revocado: 'border-linea',
}

/** Cuatro estados, cada uno con ícono distinto y palabra (5.3). */
function EstadoEnlace({ a, enPausa }: { a: AccesoResumen; enPausa: boolean }) {
  if (a.estado === 'vigente' && enPausa)
    return (
      <Etiqueta tono="atenta">
        <CirclePause aria-hidden className="size-4 shrink-0" />
        {T.enPausa}
      </Etiqueta>
    )
  if (a.estado === 'vigente')
    return (
      <Etiqueta tono="activo">
        <Clock3 aria-hidden className="size-4 shrink-0" />
        <span className="min-w-0">
          {T.activoVence} <span className="cifras">{restante(new Date(a.expira_en), new Date())}</span>
        </span>
      </Etiqueta>
    )
  if (a.estado === 'bloqueado')
    return (
      <Etiqueta tono="atenta">
        <CircleAlert aria-hidden className="size-4 shrink-0" />
        {T.estados.bloqueado}
      </Etiqueta>
    )
  return (
    <Etiqueta>
      {a.estado === 'vencido' ? <TimerOff aria-hidden className="size-4 shrink-0" /> : <Unlink aria-hidden className="size-4 shrink-0" />}
      {T.estados[a.estado]}
    </Etiqueta>
  )
}

function Detalle({ a }: { a: AccesoResumen }) {
  if (a.estado === 'bloqueado') return <>{T.detalleBloqueado}</>
  if (a.estado === 'revocado' && a.revocado_en) return <FechaHora iso={a.revocado_en} partes={T.loCortaron} />
  if (a.estado === 'revocado') return null
  if (a.estado === 'vencido') return <FechaHora iso={a.expira_en} partes={T.vencio} />
  return (
    <>
      {a.otorgado_por ? `${T.loCreo(nombreDeAutor(a.otorgado_por) ?? '')} ` : ''}
      <FechaHora iso={a.expira_en} partes={T.vence} />
    </>
  )
}

/** Una tarjeta (5.3). Cortar no es optimista: la tarjeta cambia solo con el 204 (5.4). */
function TarjetaEnlace({ a: inicial, gestiona, enPausa, recargar }: { a: AccesoResumen; gestiona: boolean; enPausa: boolean; recargar: () => void }) {
  const [a, setA] = useState(inicial)
  const [cortando, setCortando] = useState(false)
  const [cortado, setCortado] = useState(false)
  const [falla, setFalla] = useState<'red' | 'no-encontrado' | null>(null)
  const confirmacion = useRef<HTMLDivElement>(null)

  useEffect(() => setA(inicial), [inicial])
  useEffect(() => {
    if (cortado) confirmacion.current?.focus()
  }, [cortado])

  const cortar = async () => {
    if (cortando) return
    setCortando(true)
    setFalla(null)
    try {
      await cortarAcceso(a.id)
      setA((x) => ({ ...x, estado: 'revocado', revocado_en: x.revocado_en ?? new Date().toISOString() }))
      setCortado(true)
    } catch (e) {
      if (esVencida(e)) return
      if (leerFallo(e).status === 404) {
        setFalla('no-encontrado')
        recargar()
      } else setFalla('red')
    } finally {
      setCortando(false)
    }
  }

  const titulos = ordenar(a.secciones_adicionales).map((s) => TITULO_SECCION[s])
  const camposAcceso = CAMPOS.filter((c) => a.campos.includes(c.api)).map((c) => c.titulo)
  const ve = loQueVeAcceso(camposAcceso, titulos)
  // Decisión 31: el teléfono solo viene para admin y cuidador. Nunca se muestra; solo `tel:`.
  const conTelefono = gestiona && 'telefono_relevo' in a
  const telefono = conTelefono ? a.telefono_relevo : null

  return (
    <li
      id={`enlace-${a.id}`}
      tabIndex={-1}
      aria-busy={cortando || undefined}
      className={`flex min-w-0 flex-col gap-2 border-l-4 bg-hoja px-4 angosto:px-2 py-3.5 outline-none focus-visible:outline-3 focus-visible:outline-turquesa ${a.estado === 'vigente' && enPausa ? 'border-atenta' : BORDE[a.estado]}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="min-w-0 text-lg font-bold break-words">{a.nombre_relevo}</h3>
        <EstadoEnlace a={a} enPausa={enPausa} />
      </div>
      <p className="max-w-prose text-base text-tenue">
        {ve} {T.motivos[a.motivo]}.
      </p>
      <p className="max-w-prose text-base text-tenue tabular-nums">
        <Detalle a={a} />
      </p>
      {cortado && (
        <div ref={confirmacion} tabIndex={-1} role="status" className="rounded-xl">
          <Nota tono="ok" titulo={T.cortado(a.nombre_relevo)}>
            {T.cortadoAbierta(a.nombre_relevo)}
          </Nota>
        </div>
      )}
      {falla && (
        <Nota tono="pronto" rol="alert">
          {falla === 'red' ? T.errCortar : GENERAL.noEncontrado}
        </Nota>
      )}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
        {gestiona && a.estado === 'vigente' && !cortado && (
          <Boton
            variante="secundario"
            icono={<Unlink aria-hidden className="size-5" />}
            ocupado={cortando}
            textoOcupado={T.cortando}
            onClick={() => void cortar()}
          >
            {T.cortar(a.nombre_relevo)}
          </Boton>
        )}
        {conTelefono &&
          (telefono ? (
            <a href={`tel:${telefono.replace(/\s+/g, '')}`} className={claseBoton('texto')}>
              <Phone aria-hidden className="size-5 shrink-0 angosto:hidden" />
              <span className="min-w-0 break-words">{T.llamar(a.nombre_relevo)}</span>
            </a>
          ) : (
            <p className="text-base text-tenue">{T.sinTelefono}</p>
          ))}
        <Boton variante="texto" onClick={() => navegar('/ficha/quien-la-vio')}>
          {T.verCuando}
        </Boton>
      </div>
    </li>
  )
}

/** 5.6: las cuatro aperturas más recientes; si fallan, no afectan la lista de enlaces. */
function UltimasAperturasEnlaces() {
  const { personaId } = useFamilia()
  const [items, setItems] = useState<Apertura[] | null>(null)
  const [fallo, setFallo] = useState(false)
  const pedir = useCallback(() => {
    if (!personaId) return () => {}
    let vivo = true
    setFallo(false)
    listarAperturas(personaId, null, 4)
      .then((r) => vivo && setItems(r.items.filter((x) => !Number.isNaN(new Date(x.ocurrido_en).getTime()))))
      .catch((e) => {
        if (vivo && !esVencida(e)) setFallo(true)
      })
    return () => {
      vivo = false
    }
  }, [personaId])
  useEffect(() => pedir(), [pedir])
  return (
    <section aria-labelledby="ultimas-enlaces-t" className="flex min-w-0 flex-col gap-2">
      <h2 id="ultimas-enlaces-t" className="text-xl font-bold leading-snug">
        {QUIEN.ultimas}
      </h2>
      {fallo ? (
        <ErrorAperturas reintentar={() => void pedir()} />
      ) : items === null ? (
        <Cargando />
      ) : items.length === 0 ? (
        <p className="text-base text-tenue">{QUIEN.vacio}</p>
      ) : (
        <>
          <ol className="flex flex-col">
            {items.map((x, i) => (
              <LineaApertura key={`${x.acceso.id}-${x.ocurrido_en}-${x.tipo}-${i}`} a={x} sinAbrir={false} completa notas={false} />
            ))}
          </ol>
          <Boton variante="texto" className="self-start" onClick={() => navegar('/ficha/quien-la-vio')}>
            {QUIEN.verTodo}
          </Boton>
        </>
      )}
    </section>
  )
}

// Crear cuenta, entrar y la primera visita (especificación 3.2 a 3.5), copiados de `MarcoAlta`,
// `Cuenta`, `Entrar`, `AQuien` y `Permiso` de la demo (Demo/src/familia/Alta.tsx). Cambios: los
// campos empiezan vacíos, el panel es `hoja` con borde (no `pino` macizo), cuatro pasos, el
// celular obligatorio, «correo» en vez de «email» y «autorización» en vez de «permiso».
import { useCallback, useEffect, useId, useRef, useState, type FormEvent, type ReactNode, type Ref } from 'react'
import { flushSync } from 'react-dom'
import { Check, Eye, EyeOff, ShieldCheck } from 'lucide-react'
import { esperaDe, leerFallo } from '../compartido/api/cliente'
import { crearCuenta, crearGrupo, nombrePilaDe, registrarPersona, type Calidad, type SolicitudPersona } from '../compartido/api/familia'
import { leerPolitica } from '../compartido/api/politica'
import { entrar, esVencida, fijarGrupo } from '../compartido/api/sesion'
import { POLITICA } from '../compartido/textosPolitica'
import { Boton } from '../compartido/ui/Boton'
import { EnlacePoliticaEnFrase, LeePoliticaAntesDeAutorizar } from '../compartido/ui/Enlaces'
import { DistintivoPiloto, Marca } from '../compartido/ui/Marca'
import { APOYOS, AVISO_CUIDADOR, CALIDADES, PATRON_CELULAR } from './datos'
import { BORRADOR_VACIO, useFamilia } from './estado'
import { AvisoDeLlegada } from './Ficha'
import { NotaVuelvesALaInvitacion } from './Invitacion'
import { navegar, type Ruta } from './ruteo'
import { Acciones, AvisoCuidadorDeHecho, CampoTexto, GrupoOpciones, MensajeError, Nota, Titulo, Volver } from './ui'
import { AUTORIZACION, CUENTA, ENTRAR, ESPERA_CONEXION, FRASE, GENERAL, GRUPO, PASOS, PERSONA, pasoDe } from './textos'

// ---------------------------------------------------------------- marco

export function MarcoAlta({ paso, children }: { paso?: 1 | 2 | 3 | 4; children: ReactNode }) {
  return (
    <div className="grid flex-1 @4xl/app:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <aside className="flex flex-col gap-8 border-b border-linea bg-hoja px-5 angosto:px-2 @3xl/app:px-14 py-4 @4xl/app:border-r @4xl/app:border-b-0 @4xl/app:py-12">
        <span className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Marca />
          <DistintivoPiloto />
        </span>
        <div className="hidden flex-col gap-8 @4xl/app:flex">
          <p className="titular max-w-md text-2xl @2xl/app:text-4xl">{FRASE}</p>
          {paso && (
            <ol className="flex flex-col gap-3" aria-label="Pasos para empezar">
              {PASOS.map((t, i) => {
                const n = i + 1
                const estado = n < paso ? 'hecho' : n === paso ? 'ahora' : 'falta'
                return (
                  <li key={t} aria-current={estado === 'ahora' ? 'step' : undefined} className="flex items-center gap-3">
                    <span
                      aria-hidden
                      className={`grid size-9 shrink-0 place-items-center rounded-full font-bold ${
                        estado === 'hecho' ? 'bg-turquesa text-papel' : estado === 'ahora' ? 'text-turquesa ring-3 ring-inset ring-turquesa' : 'text-tenue ring-2 ring-inset ring-borde'
                      }`}
                    >
                      {estado === 'hecho' ? <Check className="size-5" strokeWidth={3} /> : n}
                    </span>
                    <span className={estado === 'ahora' ? 'font-bold' : ''}>
                      {t}
                      {estado === 'hecho' && <span className="sr-only">, hecho</span>}
                      {estado === 'ahora' && <span className="sr-only">, ahora</span>}
                    </span>
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      </aside>
      <main id="contenido" tabIndex={-1} className="@container/main px-5 angosto:px-2 @3xl/app:px-18 pt-6 pb-16 @3xl/app:py-14 outline-none">
        <div className="flex max-w-3xl flex-col gap-6">{children}</div>
      </main>
    </div>
  )
}

export function Encabezado({ paso, bajada, antes, children }: { paso?: number; bajada?: ReactNode; antes?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      {antes}
      {paso && <p className="font-bold text-tenue">{pasoDe(paso)}</p>}
      <Titulo className="text-3xl @2xl/main:text-5xl">{children}</Titulo>
      {bajada && <p className="max-w-prose text-base text-tenue">{bajada}</p>}
    </div>
  )
}

/** Enlace de texto que cambia de ruta sin recargar. */
export function EnlaceRuta({ a, children, antes }: { a: Ruta; children: ReactNode; antes?: () => void }) {
  return (
    <a
      href={a}
      onClick={(e) => {
        e.preventDefault()
        antes?.()
        navegar(a)
      }}
      className="inline-flex min-h-12 items-center font-bold text-turquesa underline underline-offset-4"
    >
      {children}
    </a>
  )
}

export function BotonMostrar({ visible, onCambio }: { visible: boolean; onCambio: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={visible}
      onClick={onCambio}
      className="inline-flex min-h-12 items-center gap-2 rounded-xl px-3 font-bold text-turquesa ring-2 ring-inset ring-turquesa/80 hover:bg-rocio"
    >
      {visible ? <EyeOff aria-hidden className="size-5" /> : <Eye aria-hidden className="size-5" />}
      {visible ? CUENTA.ocultar : CUENTA.mostrar}
    </button>
  )
}

/** Lleva el foco al primer campo con error (se marca con `aria-invalid`). */
export function enfocarPrimerError(form: HTMLFormElement | null) {
  window.setTimeout(() => form?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(), 0)
}

// ---------------------------------------------------------------- 3.2 Crear cuenta

type ErroresCuenta = Partial<Record<'nombre' | 'email' | 'celular' | 'contrasena' | 'politica', string>>

/**
 * MATU-75 (especificación 2.4): la casilla nativa de la política, sin marcar al llegar. El enlace va
 * dentro de la etiqueta: tocarlo abre la política en otra pestaña y no marca la casilla, porque es
 * contenido interactivo. El nombre accesible de la casilla es la frase entera.
 */
function CasillaPolitica({
  marcada,
  onCambio,
  error,
  ref,
}: {
  marcada: boolean
  onCambio: (v: boolean) => void
  error?: string
  ref: Ref<HTMLInputElement>
}) {
  const id = useId()
  return (
    <div className="flex flex-col gap-1.5">
      <label className="flex min-h-12 max-w-xl cursor-pointer items-start gap-3 py-3 text-base leading-relaxed">
        <input
          ref={ref}
          type="checkbox"
          checked={marcada}
          onChange={(e) => onCambio(e.target.checked)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-e` : undefined}
          className="mt-0.5 size-6 shrink-0 accent-turquesa"
        />
        <span className="min-w-0">
          {POLITICA.casillaAntes}
          <EnlacePoliticaEnFrase />
          {POLITICA.casillaDespues}
        </span>
      </label>
      {error && <MensajeError id={`${id}-e`}>{error}</MensajeError>}
    </div>
  )
}

export function CrearCuenta() {
  const { alEntrar, fijar, anunciar, invitacion } = useFamilia()
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [celular, setCelular] = useState('')
  const [clave, setClave] = useState('')
  const [ver, setVer] = useState(false)
  const [acepta, setAcepta] = useState(false)
  const [errores, setErrores] = useState<ErroresCuenta>({})
  // 'politica-cambio': el 409 de una huella que ya no es la vigente (J3).
  const [falla, setFalla] = useState<'registrado' | 'politica-cambio' | 'red' | null>(null)
  // 429 del límite por IP (lenguaje 13.3). El botón sigue habilitado (la especificación solo deshabilita
  // el de «Entrar») y el foco no se pierde; otro intento antes de tiempo vuelve a traer los minutos.
  const [minutos, setMinutos] = useState<number | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const form = useRef<HTMLFormElement>(null)
  const casilla = useRef<HTMLInputElement>(null)
  // La huella de la política que se mostró (decisión 177): se pide al abrir la pantalla, sin cookies.
  // Vive solo en la memoria de la pantalla.
  const huella = useRef<string | null>(null)

  const pedirHuella = useCallback(async (): Promise<string | null> => {
    huella.current = null
    try {
      huella.current = (await leerPolitica()).huella
    } catch {
      // Sin conexión al pedir la huella: el formulario se ve igual y se vuelve a pedir al enviar.
    }
    return huella.current
  }, [])

  useEffect(() => {
    void pedirHuella()
  }, [pedirHuella])

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado) return
    const err: ErroresCuenta = {}
    if (!nombre.trim()) err.nombre = CUENTA.errNombre
    if (!email.includes('@')) err.email = CUENTA.errCorreo
    if (!PATRON_CELULAR.test(celular.trim())) err.celular = CUENTA.errCelular
    if (clave.length < 10) err.contrasena = CUENTA.errContrasenaCorta
    if (!acepta) err.politica = POLITICA.errCasilla
    setErrores(err)
    setFalla(null)
    setMinutos(null)
    if (Object.keys(err).length) return enfocarPrimerError(form.current)
    setOcupado(true)
    try {
      const huellaPolitica = huella.current ?? (await pedirHuella())
      if (!huellaPolitica) {
        setFalla('red')
        return
      }
      await crearCuenta({
        nombre: nombre.trim(),
        email: email.trim(),
        telefono: celular.trim(),
        contrasena: clave,
        acepta_politica: true,
        huella_politica: huellaPolitica,
      })
      // La API no entra sola: se entra con lo mismo.
      await entrar(email.trim(), clave)
      await alEntrar()
      anunciar(CUENTA.creada)
      // MATU-53 (2.1): con una invitación en memoria, vuelve a «Te unes a…», nunca a crear un grupo.
      navegar(invitacion?.verificacion ? '/invitacion' : '/empezar/grupo', { reemplazar: true })
    } catch (x) {
      const f = leerFallo(x)
      const espera = esperaDe(f)
      if (espera) setMinutos(espera.minutos)
      else if (f.status === 409 && f.tipo === '/errores/politica-cambio') {
        // J3: la política cambió mientras se creaba la cuenta. La casilla se desmarca, se vuelve a
        // pedir la huella y el foco va a la casilla. Lo escrito sigue en los campos.
        flushSync(() => {
          setAcepta(false)
          setFalla('politica-cambio')
        })
        void pedirHuella()
        window.setTimeout(() => casilla.current?.focus(), 0)
      } else if (f.status === 409) setFalla('registrado')
      else if (f.status === 422 && f.errores.length) {
        const e422: ErroresCuenta = {}
        for (const { campo, tipo } of f.errores) {
          if (campo === 'nombre') e422.nombre = CUENTA.err422Nombre
          else if (campo === 'email') e422.email = tipo === 'dominio_no_permitido' ? CUENTA.errDominio : CUENTA.errCorreo
          else if (campo === 'telefono') e422.celular = CUENTA.errCelular
          else if (campo === 'contrasena') e422.contrasena = CUENTA.err422Contrasena
          else if (campo === 'acepta_politica') e422.politica = POLITICA.errCasilla
          // Una huella mal formada no la escribió nadie: se vuelve a pedir y queda el error general.
          else if (campo === 'huella_politica') void pedirHuella()
        }
        // Tras un `await`, React puede confirmar el estado después del setTimeout de enfocarPrimerError:
        // flushSync deja el campo con `aria-invalid` antes de buscarlo.
        flushSync(() => setErrores(e422))
        if (Object.keys(e422).length) enfocarPrimerError(form.current)
        else setFalla('red')
      } else setFalla('red')
    } finally {
      setOcupado(false)
    }
  }

  return (
    <MarcoAlta paso={1}>
      <NotaVuelvesALaInvitacion />
      <Encabezado paso={1} bajada={CUENTA.bajada}>
        {CUENTA.titulo}
      </Encabezado>
      <form ref={form} noValidate className="flex flex-col gap-5" onSubmit={(e) => void enviar(e)}>
        <CampoTexto
          etiqueta={CUENTA.nombre}
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          autoComplete="given-name"
          maxLength={100}
          ayuda={CUENTA.nombreAyuda}
          error={errores.nombre}
          className="max-w-md"
        />
        <div className="grid gap-5 @2xl/main:grid-cols-2">
          <CampoTexto etiqueta={CUENTA.correo} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" maxLength={254} error={errores.email} />
          <CampoTexto
            etiqueta={CUENTA.celular}
            type="tel"
            inputMode="tel"
            required
            placeholder={CUENTA.celularEjemplo}
            value={celular}
            onChange={(e) => setCelular(e.target.value)}
            autoComplete="tel"
            ayuda={CUENTA.celularAyuda}
            error={errores.celular}
          />
        </div>
        <CampoTexto
          etiqueta={CUENTA.contrasena}
          type={ver ? 'text' : 'password'}
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          autoComplete="new-password"
          minLength={10}
          maxLength={128}
          ayuda={CUENTA.contrasenaAyuda}
          error={errores.contrasena}
          className="max-w-md"
          junto={<BotonMostrar visible={ver} onCambio={() => setVer((v) => !v)} />}
        />
        <CasillaPolitica
          ref={casilla}
          marcada={acepta}
          error={errores.politica}
          onCambio={(v) => {
            setAcepta(v)
            // Al marcarla, el error se quita en ese momento.
            if (v) setErrores((x) => ({ ...x, politica: undefined }))
          }}
        />
        {falla === 'politica-cambio' && (
          <Nota tono="atenta" titulo={POLITICA.cambioTitulo} rol="status" iconoEnLinea>
            {POLITICA.cambioTexto}
          </Nota>
        )}
        {falla === 'registrado' && (
          <Nota tono="atenta" titulo={CUENTA.registradoTitulo} rol="status">
            <div className="flex flex-col items-start gap-2">
              <span>{CUENTA.registradoTexto}</span>
              <Boton
                variante="secundario"
                onClick={() => {
                  fijar({ correo: email.trim() })
                  navegar('/entrar')
                }}
              >
                {CUENTA.registradoBoton}
              </Boton>
            </div>
          </Nota>
        )}
        {falla === 'red' && (
          <Nota tono="pronto" rol="alert">
            {GENERAL.error}
          </Nota>
        )}
        {minutos !== null && (
          <Nota tono="atenta" titulo={ESPERA_CONEXION.titulo} rol="status">
            {ESPERA_CONEXION.texto(minutos)}
          </Nota>
        )}
        <Acciones>
          <Boton type="submit" ocupado={ocupado} textoOcupado={CUENTA.enviando}>
            {CUENTA.boton}
          </Boton>
        </Acciones>
      </form>
      <p className="flex flex-wrap items-center gap-x-2">
        {CUENTA.yaTienes} <EnlaceRuta a="/entrar">{CUENTA.irAEntrar}</EnlaceRuta>
      </p>
    </MarcoAlta>
  )
}

// ---------------------------------------------------------------- 3.3 Entrar

type FallaEntrar = { tipo: 'faltan' | 'credenciales' | 'no-disponible' | 'red' } | { tipo: 'espera'; minutos: number; hasta: number }

export function Entrar() {
  const { avisoEntrar, correo, destino, alEntrar, fijar } = useFamilia()
  const [email, setEmail] = useState(correo)
  const [clave, setClave] = useState('')
  const [ver, setVer] = useState(false)
  const [falla, setFalla] = useState<FallaEntrar | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const [esperando, setEsperando] = useState(false)

  // 429: el botón vuelve a habilitarse solo cuando pasa el tiempo, sin cuenta regresiva.
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
    setOcupado(true)
    try {
      await entrar(email.trim(), clave)
      await alEntrar()
      fijar({ correo: '', destino: null, avisoEntrar: null })
      navegar(destino ?? '/', { reemplazar: true })
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

  return (
    <MarcoAlta>
      <NotaVuelvesALaInvitacion />
      <Encabezado>{ENTRAR.titulo}</Encabezado>
      {avisoEntrar === 'clave-cambiada' ? (
        <Nota tono="ok" rol="status">
          {ENTRAR.claveCambiada}
        </Nota>
      ) : (
        avisoEntrar && (
          <Nota tono="rocio" rol="status">
            {avisoEntrar === 'vencida' ? ENTRAR.vencida : ENTRAR.salio}
          </Nota>
        )
      )}
      {falla?.tipo === 'espera' && (
        <Nota tono="atenta" rol="status">
          <span className="block">{ENTRAR.espera(falla.minutos)}</span>
          {/* MATU-57 4: el enlace sigue activo mientras «Entrar» espera. */}
          <EnlaceRuta a="/entrar/recuperar" antes={() => fijar({ correo: email.trim() })}>
            {ENTRAR.esperaRecuperar}
          </EnlaceRuta>
        </Nota>
      )}
      {falla?.tipo === 'no-disponible' && (
        <Nota tono="pronto" rol="alert">
          {ENTRAR.noDisponible}
        </Nota>
      )}
      {falla?.tipo === 'red' && (
        <Nota tono="pronto" rol="alert">
          {GENERAL.error}
        </Nota>
      )}
      <form noValidate className="flex flex-col gap-5" onSubmit={(e) => void enviar(e)}>
        <CampoTexto etiqueta={ENTRAR.correo} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" maxLength={254} className="max-w-md" />
        <CampoTexto
          etiqueta={ENTRAR.contrasena}
          type={ver ? 'text' : 'password'}
          value={clave}
          onChange={(e) => setClave(e.target.value)}
          autoComplete="current-password"
          maxLength={128}
          className="max-w-md"
          junto={<BotonMostrar visible={ver} onCambio={() => setVer((v) => !v)} />}
        />
        {/* MATU-57 4: el correo escrito pasa en memoria, nunca en la URL. */}
        <p className="-mt-3">
          <EnlaceRuta a="/entrar/recuperar" antes={() => fijar({ correo: email.trim() })}>
            {ENTRAR.olvidaste}
          </EnlaceRuta>
        </p>
        {falla?.tipo === 'faltan' && <MensajeError>{ENTRAR.faltan}</MensajeError>}
        {falla?.tipo === 'credenciales' && (
          <Nota tono="pronto" rol="alert">
            {ENTRAR.credenciales}
          </Nota>
        )}
        <Acciones>
          {/* 429: espera con `aria-disabled` para que el foco siga en el botón (Boton.tsx); `enviar` no envía. */}
          <Boton type="submit" ocupado={ocupado} textoOcupado={ENTRAR.enviando} aria-disabled={esperando || undefined}
            className="aria-disabled:cursor-not-allowed aria-disabled:opacity-60 aria-disabled:focus-visible:outline-tinta"
          >
            {ENTRAR.boton}
          </Boton>
        </Acciones>
      </form>
      <p className="flex flex-wrap items-center gap-x-2">
        {ENTRAR.noTienes} <EnlaceRuta a="/crear-cuenta">{ENTRAR.irACrear}</EnlaceRuta>
      </p>
    </MarcoAlta>
  )
}

// ---------------------------------------------------------------- 3.4 Crear el grupo

export function CrearGrupo() {
  const { fijar, grupos } = useFamilia()
  const [nombre, setNombre] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [red, setRed] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const form = useRef<HTMLFormElement>(null)

  // Con un grupo ya creado, esta pantalla no crea un segundo.
  useEffect(() => {
    if (grupos.length) navegar('/empezar/persona', { reemplazar: true })
  }, [grupos.length])

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado) return
    setRed(false)
    if (!nombre.trim()) {
      setError(GRUPO.errVacio)
      return enfocarPrimerError(form.current)
    }
    setError(null)
    setOcupado(true)
    try {
      const g = await crearGrupo(nombre.trim())
      fijarGrupo(g.id)
      fijar({ grupos: [g], grupoId: g.id, personas: [], personaId: null })
      navegar('/empezar/persona')
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 422) {
        setError(GRUPO.errVacio)
        enfocarPrimerError(form.current)
      } else setRed(true)
    } finally {
      setOcupado(false)
    }
  }

  return (
    <MarcoAlta paso={2}>
      {/* MATU-53 (7.2): «Saliste de {grupo}.» cuando no queda otro grupo. */}
      <AvisoDeLlegada className="" />
      <Encabezado paso={2} bajada={GRUPO.bajada}>
        {GRUPO.titulo}
      </Encabezado>
      <form ref={form} noValidate className="flex flex-col gap-5" onSubmit={(e) => void enviar(e)}>
        <CampoTexto
          etiqueta={GRUPO.campo}
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          autoComplete="off"
          maxLength={60}
          ayuda={GRUPO.ayuda}
          error={error}
          className="max-w-xl"
        />
        {red && (
          <Nota tono="pronto" rol="alert">
            {GENERAL.error}
          </Nota>
        )}
        <Acciones>
          <Boton type="submit" ocupado={ocupado} textoOcupado={GRUPO.enviando}>
            {GRUPO.boton}
          </Boton>
        </Acciones>
      </form>
    </MarcoAlta>
  )
}

// ---------------------------------------------------------------- 3.5.1 ¿A quién cuidas?

export function AQuien() {
  const { borrador, fijar } = useFamilia()
  const [b, setB] = useState(borrador)
  const [error, setError] = useState<'nombres' | 'apoyo' | null>(null)
  const cambia = (k: keyof typeof b) => (e: { target: { value: string } }) => setB((x) => ({ ...x, [k]: e.target.value }))
  const form = useRef<HTMLFormElement>(null)

  const seguir = (e: FormEvent) => {
    e.preventDefault()
    if (!b.nombre.trim() || !b.pila.trim()) setError('nombres')
    else if (!b.apoyo) setError('apoyo')
    else {
      setError(null)
      fijar({ borrador: b })
      return navegar('/empezar/autorizacion')
    }
    enfocarPrimerError(form.current)
  }

  return (
    <MarcoAlta paso={3}>
      <Encabezado paso={3}>{PERSONA.titulo}</Encabezado>
      {/* MATU-72 4.3: «Borramos los datos de…» al llegar sin personas, después de borrar. */}
      <AvisoDeLlegada className="" />
      <form ref={form} noValidate className="flex flex-col gap-6" onSubmit={seguir}>
        <div className="grid gap-5 @2xl/main:grid-cols-2">
          <CampoTexto
            etiqueta={PERSONA.nombre}
            value={b.nombre}
            onChange={cambia('nombre')}
            autoComplete="off"
            maxLength={120}
            error={error === 'nombres' && !b.nombre.trim() ? PERSONA.errNombres : null}
          />
          <CampoTexto
            etiqueta={PERSONA.pila}
            value={b.pila}
            onChange={cambia('pila')}
            autoComplete="off"
            maxLength={60}
            ayuda={PERSONA.pilaAyuda}
            error={error === 'nombres' && !b.pila.trim() ? PERSONA.errNombres : null}
          />
        </div>
        <GrupoOpciones
          leyenda={PERSONA.apoyo}
          nombre="apoyo"
          opciones={APOYOS}
          valor={b.apoyo}
          onCambio={(v) => setB((x) => ({ ...x, apoyo: v }))}
          columnas
          error={error === 'apoyo' ? PERSONA.errApoyo : null}
        />
        <p className="flex max-w-prose gap-2 rounded-xl bg-rocio px-4 py-3">
          <ShieldCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />
          <span>{PERSONA.sinDiagnostico}</span>
        </p>
        <Acciones>
          <Boton type="submit">{PERSONA.boton}</Boton>
        </Acciones>
      </form>
    </MarcoAlta>
  )
}

// ---------------------------------------------------------------- 3.5.2 La autorización

const CAMPOS_PASO_1 = /^(nombre|nombre_pila|nivel_apoyo)$/

/** Lo que declara quien autoriza la ficha: el cuerpo de `POST …/personas-cuidadas` y de `POST …/consentimientos`. */
export interface Otorgamiento {
  calidad_otorgante: Calidad
  referencia_documento: string | null
  aviso: { id: string; version: string } | null
}

/**
 * Las declaraciones de la autorización de la ficha (3.5.2), sin el marco: la calidad (ninguna
 * preseleccionada), la referencia, el aviso del cuidador de hecho con su casilla y «Lo que declaras».
 * Las usan el alta y volver a autorizar (MATU-44 5.1), sin cambiar una palabra.
 */
export function useDeclaracionFicha() {
  const [calidad, setCalidad] = useState<Calidad | null>(null)
  const [leido, setLeido] = useState(false)
  const [referencia, setReferencia] = useState('')
  const [error, setError] = useState<'calidad' | 'referencia' | 'leido' | null>(null)
  /** Valida al enviar. Devuelve el cuerpo, o `null` con el error a la vista. */
  const validar = (): Otorgamiento | null => {
    let falta: 'calidad' | 'referencia' | 'leido' | null = null
    if (!calidad) falta = 'calidad'
    else if (calidad === 'representante_legal' && !referencia.trim()) falta = 'referencia'
    else if (calidad === 'cuidador_de_hecho' && !leido) falta = 'leido'
    setError(falta)
    if (falta || !calidad) return null
    return {
      calidad_otorgante: calidad,
      referencia_documento: calidad === 'representante_legal' ? referencia.trim() : null,
      aviso: calidad === 'cuidador_de_hecho' ? { id: AVISO_CUIDADOR.id, version: AVISO_CUIDADOR.version } : null,
    }
  }
  return { calidad, setCalidad, leido, setLeido, referencia, setReferencia, error, setError, validar }
}

export function DeclaracionFicha({ pila, d }: { pila: string; d: ReturnType<typeof useDeclaracionFicha> }) {
  const { calidad, setCalidad, leido, setLeido, referencia, setReferencia, error, setError } = d
  const elegida = CALIDADES.find((c) => c.valor === calidad)
  return (
    <>
      <GrupoOpciones
        leyenda={AUTORIZACION.leyenda}
        nombre="calidad"
        valor={calidad}
        columnas
        error={error === 'calidad' ? AUTORIZACION.errCalidad : null}
        onCambio={(v) => {
          setCalidad(v)
          setError(null)
        }}
        opciones={CALIDADES.map((c) => ({ valor: c.valor, texto: c.texto(pila), detalle: c.detalle(pila) }))}
      />

      {calidad === 'representante_legal' && (
        <CampoTexto
          etiqueta={AUTORIZACION.referencia}
          value={referencia}
          onChange={(e) => setReferencia(e.target.value)}
          ayuda={AUTORIZACION.referenciaAyuda}
          autoComplete="off"
          maxLength={200}
          className="max-w-xl"
          error={error === 'referencia' ? AUTORIZACION.errReferencia : null}
        />
      )}

      {calidad === 'cuidador_de_hecho' && (
        <AvisoCuidadorDeHecho
          idTitulo="aviso-t"
          idError="leido-e"
          leido={leido}
          error={error === 'leido'}
          onLeido={(v) => {
            setLeido(v)
            setError(null)
          }}
        />
      )}

      {elegida && (
        <Nota tono="rocio" titulo={AUTORIZACION.declaras} iconoEnLinea>
          <p className="max-w-prose">{elegida.declaracion}</p>
          <LeePoliticaAntesDeAutorizar />
        </Nota>
      )}
    </>
  )
}

export function Autorizacion() {
  const { borrador, grupoId, fijar, anunciar, personas } = useFamilia()
  const pila = borrador.pila.trim()
  const d = useDeclaracionFicha()
  const [falla, setFalla] = useState<'paso1' | 'no-encontrado' | 'red' | null>(null)
  const [ocupado, setOcupado] = useState(false)

  // Sin lo del paso 1 (por ejemplo, recargó la página), se vuelve a escribir.
  useEffect(() => {
    if (!pila) navegar('/empezar/persona', { reemplazar: true })
  }, [pila])

  const aceptar = async () => {
    if (ocupado) return
    setFalla(null)
    const otorgamiento = d.validar()
    if (!otorgamiento) return
    if (!grupoId) return setFalla('no-encontrado')
    // La persona y la autorización van en la misma petición: nada se guarda antes de autorizar.
    // Sin dirección (decisión de Jorge del 08-11, minimización): se pedirá con el primer pedido (MATU-61).
    const cuerpo: SolicitudPersona = {
      nombre: borrador.nombre.trim(),
      nombre_pila: pila,
      nivel_apoyo: borrador.apoyo ?? 'apoyo_parcial',
      ...otorgamiento,
    }
    setOcupado(true)
    try {
      const p = await registrarPersona(grupoId, cuerpo)
      const vista = { id: p.id, nombre: p.nombre, nombre_pila: p.nombre_pila, nivel_apoyo: p.nivel_apoyo, direccion: p.direccion, consentimiento: p.consentimiento }
      fijar({ personas: [...personas, vista], personaId: p.id, ficha: null, borrador: BORRADOR_VACIO })
      anunciar(AUTORIZACION.registrada(nombrePilaDe(vista)))
      // MATU-57 5.1 (D4): en la primera entrada se ofrece confirmar el celular, con «Ahora no».
      fijar({ celularDesde: 'primera' })
      navegar('/cuenta/celular', { reemplazar: true })
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 404) setFalla('no-encontrado')
      else if (f.status === 422 && f.campos.some((c) => CAMPOS_PASO_1.test(c))) setFalla('paso1')
      else if (f.status === 422 && f.campos.includes('referencia_documento')) d.setError('referencia')
      else setFalla('red')
    } finally {
      setOcupado(false)
    }
  }

  if (!pila) return null

  return (
    <MarcoAlta paso={4}>
      <Encabezado paso={4} bajada={AUTORIZACION.bajada(pila)} antes={<Volver onClick={() => navegar('/empezar/persona')}>{AUTORIZACION.volver}</Volver>}>
        {AUTORIZACION.titulo}
      </Encabezado>
      <DeclaracionFicha pila={pila} d={d} />
      {falla === 'paso1' && (
        <Nota tono="pronto" rol="alert">
          <Volver onClick={() => navegar('/empezar/persona')}>{AUTORIZACION.volverACorregir(pila)}</Volver>
        </Nota>
      )}
      {falla === 'no-encontrado' && (
        <Nota tono="pronto" rol="alert">
          {GENERAL.noEncontrado}
        </Nota>
      )}
      {falla === 'red' && (
        <Nota tono="pronto" rol="alert">
          {GENERAL.error}
        </Nota>
      )}
      <Acciones>
        <Boton onClick={() => void aceptar()} ocupado={ocupado} textoOcupado={AUTORIZACION.enviando(pila)}>
          {AUTORIZACION.boton(pila)}
        </Boton>
      </Acciones>
    </MarcoAlta>
  )
}

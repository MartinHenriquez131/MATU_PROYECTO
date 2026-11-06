// Crear cuenta, entrar y la primera visita (especificación 3.2 a 3.5), copiados de `MarcoAlta`,
// `Cuenta`, `Entrar`, `AQuien` y `Permiso` de la demo (Demo/src/familia/Alta.tsx). Cambios: los
// campos empiezan vacíos, el panel es `hoja` con borde (no `pino` macizo), cuatro pasos, el
// celular obligatorio, «correo» en vez de «email» y «autorización» en vez de «permiso».
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { Check, Eye, EyeOff, ShieldCheck, TriangleAlert } from 'lucide-react'
import { esperaDe, leerFallo } from '../compartido/api/cliente'
import { crearCuenta, crearGrupo, nombrePilaDe, registrarPersona, type Calidad, type SolicitudPersona } from '../compartido/api/familia'
import { entrar, esVencida, fijarGrupo } from '../compartido/api/sesion'
import { Boton } from '../compartido/ui/Boton'
import { DistintivoPiloto, Marca } from '../compartido/ui/Marca'
import { APOYOS, AVISO_CUIDADOR, CALIDADES, PATRON_CELULAR } from './datos'
import { BORRADOR_VACIO, useFamilia } from './estado'
import { navegar, type Ruta } from './ruteo'
import { Acciones, CampoTexto, GrupoOpciones, MensajeError, Nota, Titulo, Volver } from './ui'
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
      className="inline-flex min-h-12 items-center gap-2 rounded-xl px-3 font-bold text-turquesa ring-2 ring-inset ring-turquesa/70 hover:bg-rocio"
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

type ErroresCuenta = Partial<Record<'nombre' | 'email' | 'celular' | 'contrasena', string>>

export function CrearCuenta() {
  const { alEntrar, fijar, anunciar } = useFamilia()
  const [nombre, setNombre] = useState('')
  const [email, setEmail] = useState('')
  const [celular, setCelular] = useState('')
  const [clave, setClave] = useState('')
  const [ver, setVer] = useState(false)
  const [errores, setErrores] = useState<ErroresCuenta>({})
  const [falla, setFalla] = useState<'registrado' | 'red' | null>(null)
  // 429 del límite por IP (lenguaje 13.3). El botón sigue habilitado (la especificación solo deshabilita
  // el de «Entrar») y el foco no se pierde; otro intento antes de tiempo vuelve a traer los minutos.
  const [minutos, setMinutos] = useState<number | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const form = useRef<HTMLFormElement>(null)

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado) return
    const err: ErroresCuenta = {}
    if (!nombre.trim()) err.nombre = CUENTA.errNombre
    if (!email.includes('@')) err.email = CUENTA.errCorreo
    if (!PATRON_CELULAR.test(celular.trim())) err.celular = CUENTA.errCelular
    if (clave.length < 10) err.contrasena = CUENTA.errContrasenaCorta
    setErrores(err)
    setFalla(null)
    setMinutos(null)
    if (Object.keys(err).length) return enfocarPrimerError(form.current)
    setOcupado(true)
    try {
      await crearCuenta({ nombre: nombre.trim(), email: email.trim(), telefono: celular.trim(), contrasena: clave })
      // La API no entra sola: se entra con lo mismo.
      await entrar(email.trim(), clave)
      await alEntrar()
      anunciar(CUENTA.creada)
      navegar('/empezar/grupo', { reemplazar: true })
    } catch (x) {
      const f = leerFallo(x)
      const espera = esperaDe(f)
      if (espera) setMinutos(espera.minutos)
      else if (f.status === 409) setFalla('registrado')
      else if (f.status === 422 && f.errores.length) {
        const e422: ErroresCuenta = {}
        for (const { campo, tipo } of f.errores) {
          if (campo === 'nombre') e422.nombre = CUENTA.err422Nombre
          else if (campo === 'email') e422.email = tipo === 'dominio_no_permitido' ? CUENTA.errDominio : CUENTA.errCorreo
          else if (campo === 'telefono') e422.celular = CUENTA.errCelular
          else if (campo === 'contrasena') e422.contrasena = CUENTA.err422Contrasena
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
          <Boton type="submit" ocupado={ocupado} textoOcupado={ENTRAR.enviando} disabled={esperando}>
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
  const [error, setError] = useState<'nombres' | 'apoyo' | 'direccion' | null>(null)
  const algunaDireccion = !!(b.calle.trim() || b.numero.trim() || b.comuna.trim() || b.depto.trim())
  const direccionCompleta = !!(b.calle.trim() && b.numero.trim() && b.comuna.trim())
  const cambia = (k: keyof typeof b) => (e: { target: { value: string } }) => setB((x) => ({ ...x, [k]: e.target.value }))
  const form = useRef<HTMLFormElement>(null)

  const seguir = (e: FormEvent) => {
    e.preventDefault()
    if (!b.nombre.trim() || !b.pila.trim()) setError('nombres')
    else if (!b.apoyo) setError('apoyo')
    else if (algunaDireccion && !direccionCompleta) setError('direccion')
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
        <fieldset className="flex flex-col gap-3">
          <legend className="font-bold">{PERSONA.direccion}</legend>
          <p className="-mt-1 text-base text-tenue">{PERSONA.direccionAyuda}</p>
          <div className="grid gap-4 @2xl/main:grid-cols-[minmax(0,2fr)_minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <CampoTexto etiqueta={PERSONA.calle} value={b.calle} onChange={cambia('calle')} autoComplete="off" maxLength={120} aria-invalid={error === 'direccion' && !b.calle.trim() ? true : undefined} />
            <CampoTexto etiqueta={PERSONA.numero} value={b.numero} onChange={cambia('numero')} autoComplete="off" maxLength={20} aria-invalid={error === 'direccion' && !b.numero.trim() ? true : undefined} />
            <CampoTexto etiqueta={PERSONA.comuna} value={b.comuna} onChange={cambia('comuna')} autoComplete="off" maxLength={60} aria-invalid={error === 'direccion' && !b.comuna.trim() ? true : undefined} />
          </div>
          <CampoTexto etiqueta={PERSONA.depto} value={b.depto} onChange={cambia('depto')} autoComplete="off" maxLength={20} className="max-w-48" />
          {error === 'direccion' && <MensajeError>{PERSONA.errDireccion}</MensajeError>}
        </fieldset>
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

const CAMPOS_PASO_1 = /^(nombre|nombre_pila|nivel_apoyo|direccion(\..*)?)$/

export function Autorizacion() {
  const { borrador, grupoId, fijar, anunciar, personas } = useFamilia()
  const pila = borrador.pila.trim()
  const [calidad, setCalidad] = useState<Calidad | null>(null)
  const [leido, setLeido] = useState(false)
  const [referencia, setReferencia] = useState('')
  const [error, setError] = useState<'calidad' | 'referencia' | 'leido' | null>(null)
  const [falla, setFalla] = useState<'paso1' | 'no-encontrado' | 'red' | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const elegida = CALIDADES.find((c) => c.valor === calidad)

  // Sin lo del paso 1 (por ejemplo, recargó la página), se vuelve a escribir.
  useEffect(() => {
    if (!pila) navegar('/empezar/persona', { reemplazar: true })
  }, [pila])

  const aceptar = async () => {
    if (ocupado) return
    setFalla(null)
    if (!calidad) return setError('calidad')
    if (calidad === 'representante_legal' && !referencia.trim()) return setError('referencia')
    if (calidad === 'cuidador_de_hecho' && !leido) return setError('leido')
    setError(null)
    if (!grupoId) return setFalla('no-encontrado')
    const conDireccion = borrador.calle.trim() && borrador.numero.trim() && borrador.comuna.trim()
    const cuerpo: SolicitudPersona = {
      nombre: borrador.nombre.trim(),
      nombre_pila: pila,
      nivel_apoyo: borrador.apoyo ?? 'apoyo_parcial',
      calidad_otorgante: calidad,
      referencia_documento: calidad === 'representante_legal' ? referencia.trim() : null,
      aviso: calidad === 'cuidador_de_hecho' ? { id: AVISO_CUIDADOR.id, version: AVISO_CUIDADOR.version } : null,
      direccion: conDireccion
        ? { calle: borrador.calle.trim(), numero: borrador.numero.trim(), comuna: borrador.comuna.trim(), depto: borrador.depto.trim() || null }
        : null,
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
      else if (f.status === 422 && f.campos.includes('referencia_documento')) setError('referencia')
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
        <section aria-labelledby="aviso-t" className="border-l-4 border-atenta bg-atenta-fondo">
          <h2 id="aviso-t" className="flex items-start gap-2 px-5 angosto:px-2 pt-4 text-lg font-bold">
            <TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />
            {AVISO_CUIDADOR.titulo}
          </h2>
          <div className="flex max-w-prose flex-col gap-2.5 px-5 angosto:px-2 pt-2 pb-4 leading-relaxed">
            {AVISO_CUIDADOR.parrafos.map((p) => (
              <p key={p.slice(0, 24)}>{p}</p>
            ))}
          </div>
          <label className="flex min-h-12 cursor-pointer items-center gap-3 border-t border-linea bg-hoja/60 px-5 angosto:px-2 py-3 font-bold">
            <input
              type="checkbox"
              checked={leido}
              aria-invalid={error === 'leido' ? true : undefined}
              aria-describedby={error === 'leido' ? 'leido-e' : undefined}
              onChange={(e) => {
                setLeido(e.target.checked)
                setError(null)
              }}
              className="size-5 shrink-0 accent-turquesa"
            />
            {AUTORIZACION.leido}
          </label>
          {error === 'leido' && (
            <div className="px-5 angosto:px-2 pb-3">
              <MensajeError id="leido-e">{AUTORIZACION.errLeido}</MensajeError>
            </div>
          )}
        </section>
      )}

      {elegida && (
        <Nota tono="rocio" titulo={AUTORIZACION.declaras}>
          <p className="max-w-prose">{elegida.declaracion}</p>
        </Nota>
      )}
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

// El alta, antes de tener cuenta: a la izquierda el panel de MATU con los pasos; a la derecha el
// formulario. Cuenta, sesión, grupo y persona son reales si hay backend (capa híbrida).
import { useState, type ReactNode } from 'react'
import { Check, ClipboardList, Link2, Package, ShieldCheck } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { avisar, crearCuenta, darPermiso, entrar, guardarPersona, ir, pantallaFamilia } from '../demo/logica'
import { APOYOS, AVISO_CUIDADOR, CALIDADES } from '../demo/datos'
import type { Apoyo, Calidad, Persona } from '../demo/tipos'
import type { ApiMatu } from '../datos/api'
import type { DireccionVista, PersonaListada } from '../datos/contrato'
import { useBackend } from '../datos/backend'
import { CUENTA_EJEMPLO } from '../datos/simulado'
import { AvisoFalla, useLlamada } from '../datos/useLlamada'
import { Acciones, Boton, CampoTexto, GrupoOpciones, Hoja, Marca, MensajeError, Nota } from '../components/Ui'
import { Volver } from './Shell'

const azar = (n: number) => Array.from(crypto.getRandomValues(new Uint8Array(n)), (b) => (b % 10).toString()).join('')

function direccionLegible(d: DireccionVista | null): string {
  return d ? `${d.calle} ${d.numero}, ${d.comuna}` : ''
}

function personaDesdeApi(p: PersonaListada): Persona | null {
  if (!('nombre_pila' in p)) return null
  return {
    nombre: p.nombre,
    nombrePila: p.nombre_pila,
    apoyo: p.nivel_apoyo,
    direccion: direccionLegible(p.direccion),
    partes: p.direccion ? { calle: p.direccion.calle, numero: p.direccion.numero, comuna: p.direccion.comuna } : null,
    idReal: p.id,
  }
}

const PASOS = ['Tu cuenta', 'A quién cuidas', 'El permiso']

function MarcoAlta({ paso, children, panel }: { paso?: 1 | 2 | 3; children: ReactNode; panel?: ReactNode }) {
  return (
    <div className="grid flex-1 @4xl/app:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <aside className="relative flex flex-col gap-8 overflow-hidden bg-pino px-5 @3xl:px-14 py-6 @3xl:py-12 text-papel">
        <Marca claro />
        {panel ?? (
          <>
            <p className="titular max-w-md text-2xl @2xl:text-4xl">Que el cuidado no dependa de una sola persona.</p>
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
                          estado === 'hecho' ? 'bg-papel text-pino' : estado === 'ahora' ? 'ring-3 ring-papel ring-inset' : 'ring-2 ring-papel/45 ring-inset'
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
          </>
        )}
      </aside>
      <main id="contenido" tabIndex={-1} className="@container/main px-5 @3xl:px-18 py-6 @3xl:py-14 outline-none">
        <div className="flex max-w-3xl flex-col gap-6">{children}</div>
      </main>
    </div>
  )
}

function Titulo({ paso, children, bajada }: { paso?: number; children: ReactNode; bajada?: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <Volver />
      {paso && <p className="font-bold text-tenue">Paso {paso} de 3</p>}
      <h1 id="titulo-pagina" tabIndex={-1} className="titular text-3xl @2xl:text-5xl outline-none">
        {children}
      </h1>
      {bajada && <p className="max-w-prose text-base text-tenue">{bajada}</p>}
    </div>
  )
}

// ---------- Bienvenida ----------

export function Bienvenida() {
  const { haz } = useDemo()
  return (
    <MarcoAlta
      panel={
        <>
          <h1 id="titulo-pagina" tabIndex={-1} className="titular max-w-md text-4xl @2xl:text-6xl outline-none">
            Que el cuidado no dependa de una sola persona.
          </h1>
          <div aria-hidden className="mt-auto max-w-md -rotate-2 text-tinta">
            <Hoja>
              <p className="titular text-3xl">Ficha de María</p>
              <p className="mt-3 mb-1 font-bold text-pino">Su día</p>
              <ul className="renglones leading-7">
                <li>
                  <span className="cifras font-bold text-pino">08:00</span> Despierta sola. Abrir la cortina primero.
                </li>
                <li>
                  <span className="cifras font-bold text-pino">08:30</span> Té con leche tibio, nunca caliente.
                </li>
              </ul>
              <p className="mt-3 mb-1 font-bold text-pino">Si se altera</p>
              <p className="renglones leading-7">Bajar las persianas y poner la radio bajito.</p>
            </Hoja>
          </div>
        </>
      }
    >
      <h2 className="text-xl font-bold">MATU ordena lo que hoy está en tu cabeza</h2>
      <ul className="flex flex-col gap-5">
        {[
          { Icono: ClipboardList, t: 'La ficha de relevo', d: 'Su día, qué la calma y a quién llamar. Tres campos cortos, para que quien te reemplace sepa qué hacer.' },
          { Icono: Link2, t: 'Un enlace con PIN', d: 'La compartes con quien te reemplaza, solo lo que tú elijas y hasta cuándo tú digas. Lo puedes cortar en cualquier momento.' },
          { Icono: Package, t: 'Antes de que se acabe', d: 'Te avisa cuándo se acaban los pañales y los demás insumos. Si quieres, la farmacia los lleva y paga una sola persona.' },
        ].map(({ Icono, t, d }) => (
          <li key={t} className="flex gap-4">
            <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-rocio text-pino">
              <Icono aria-hidden className="size-6" />
            </span>
            <span>
              <span className="block text-lg font-bold">{t}</span>
              <span className="text-tenue">{d}</span>
            </span>
          </li>
        ))}
      </ul>
      <Acciones className="pt-2">
        <Boton onClick={() => haz((s) => ir(s, 'cuenta'))}>Empezar</Boton>
        <Boton variante="secundario" onClick={() => haz((s) => ir(s, 'entrar'))}>
          Ya tengo cuenta
        </Boton>
      </Acciones>
    </MarcoAlta>
  )
}

// ---------- Cuenta y sesión ----------

export function Cuenta() {
  const { haz } = useDemo()
  const b = useBackend()
  const ll = useLlamada()
  const [nombre, setNombre] = useState('Carmen')
  // Email y contraseña sintéticos y distintos en cada sesión, para no chocar con un 409 al repetir la demo.
  const [email, setEmail] = useState(() => `carmen.${azar(4)}@correo.ejemplo`)
  const [clave, setClave] = useState(() => `demo-${azar(8)}`)
  const [local, setLocal] = useState<string | null>(null)

  const accion = async (api: ApiMatu) => {
    const cuenta = await api.crearCuenta(nombre.trim(), email.trim(), clave)
    await api.iniciarSesion(email.trim(), clave)
    b.recordar({ nombre: cuenta.nombre, email: cuenta.email, contrasena: clave })
    haz((s) => avisar(crearCuenta(s, cuenta.nombre, cuenta.email, api.modo === 'real'), 'Cuenta creada.'))
  }
  const enviar = () => {
    if (!nombre.trim() || !email.includes('@')) return setLocal('Revisa tu nombre y tu email.')
    if (clave.length < 10) return setLocal('La contraseña necesita al menos 10 caracteres.')
    setLocal(null)
    void ll.correr(accion)
  }
  const campos = ll.error?.campos ?? {}
  return (
    <MarcoAlta paso={1}>
      <Titulo paso={1} bajada="Para empezar te pedimos solo esto.">
        Crea tu cuenta
      </Titulo>
      <form
        className="flex flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault()
          enviar()
        }}
      >
        <CampoTexto etiqueta="Tu nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="off" error={campos.nombre} className="max-w-md" />
        <div className="grid gap-5 @2xl:grid-cols-2">
          <CampoTexto etiqueta="Tu email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" error={campos.email} />
          <CampoTexto
            etiqueta="Una contraseña"
            type="password"
            value={clave}
            onChange={(e) => setClave(e.target.value)}
            autoComplete="new-password"
            ayuda="Al menos 10 caracteres."
            error={local ?? campos.contrasena}
          />
        </div>
        {ll.error?.status === 409 ? (
          <Nota tono="atenta" titulo="Ese email ya tiene una cuenta">
            <div className="flex flex-col items-start gap-2">
              <span>Entra con tu contraseña, o usa otro email.</span>
              <Boton variante="secundario" onClick={() => haz((s) => ir(s, 'entrar'))}>
                Entrar con ese email
              </Boton>
            </div>
          </Nota>
        ) : (
          !Object.keys(campos).length && <AvisoFalla error={ll.error} onSimulado={() => void ll.seguirSimulado(accion)} />
        )}
        <Acciones>
          <Boton type="submit" disabled={ll.ocupado}>
            {ll.ocupado ? 'Creando la cuenta…' : 'Crear cuenta'}
          </Boton>
        </Acciones>
      </form>
    </MarcoAlta>
  )
}

export function Entrar() {
  const { haz } = useDemo()
  const b = useBackend()
  const ll = useLlamada()
  const sugerida = b.credenciales ?? (b.api.modo === 'simulado' ? { nombre: CUENTA_EJEMPLO.nombre, email: CUENTA_EJEMPLO.email, contrasena: CUENTA_EJEMPLO.clave } : null)
  const [email, setEmail] = useState(sugerida?.email ?? '')
  const [clave, setClave] = useState(sugerida?.contrasena ?? '')

  const accion = async (api: ApiMatu) => {
    const e = email.trim().toLowerCase()
    await api.iniciarSesion(e, clave)
    const grupos = await api.listarGrupos()
    let persona: Persona | null = null
    let calidad: Calidad | null = null
    if (grupos[0]) {
      api.elegirGrupo(grupos[0].id)
      b.fijarGrupo(grupos[0].id)
      const personas = await api.listarPersonas()
      const primera = personas.find((p) => 'nombre_pila' in p)
      if (primera) {
        persona = personaDesdeApi(primera)
        calidad = 'consentimiento' in primera ? (primera.consentimiento?.calidad_otorgante ?? null) : null
      }
    }
    // La API no devuelve el nombre al iniciar sesión: se usa el de la cuenta creada en esta sesión.
    const nombre = b.credenciales?.email === e ? b.credenciales.nombre : e === CUENTA_EJEMPLO.email ? CUENTA_EJEMPLO.nombre : ''
    haz((s) => entrar(s, e, nombre, api.modo === 'real', persona, calidad))
  }
  return (
    <MarcoAlta>
      <Titulo bajada="Tu sesión dura 15 minutos y no queda guardada en este computador.">Entrar</Titulo>
      <form
        className="flex flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault()
          if (email && clave) void ll.correr(accion)
        }}
      >
        <div className="grid gap-5 @2xl:grid-cols-2">
          <CampoTexto etiqueta="Tu email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" />
          <CampoTexto etiqueta="Tu contraseña" type="password" value={clave} onChange={(e) => setClave(e.target.value)} autoComplete="current-password" />
        </div>
        <AvisoFalla error={ll.error} onSimulado={() => void ll.seguirSimulado(accion)} />
        <Acciones>
          <Boton type="submit" disabled={ll.ocupado || !email || !clave}>
            {ll.ocupado ? 'Entrando…' : 'Entrar'}
          </Boton>
          <Boton variante="texto" onClick={() => haz((s) => ir(s, 'cuenta'))}>
            No tengo cuenta
          </Boton>
        </Acciones>
      </form>
    </MarcoAlta>
  )
}

// ---------- ¿A quién cuidas? ----------

export function AQuien() {
  const { s, haz } = useDemo()
  const [nombre, setNombre] = useState(s.persona?.nombre ?? 'María Soto')
  const [pila, setPila] = useState(s.persona?.nombrePila ?? 'María')
  const [apoyo, setApoyo] = useState<Apoyo | null>(s.persona?.apoyo ?? 'apoyo_parcial')
  const [calle, setCalle] = useState(s.persona?.partes?.calle ?? '')
  const [numero, setNumero] = useState(s.persona?.partes?.numero ?? '')
  const [comuna, setComuna] = useState(s.persona?.partes?.comuna ?? '')
  const [error, setError] = useState<string | null>(null)
  const algunaDireccion = !!(calle.trim() || numero.trim() || comuna.trim())
  const direccionCompleta = !!(calle.trim() && numero.trim() && comuna.trim())

  const seguir = () => {
    if (!nombre.trim() || !pila.trim() || !apoyo) return setError('Escribe su nombre y cómo le dicen para seguir.')
    if (algunaDireccion && !direccionCompleta) return setError('Completa calle, número y comuna, o deja los tres vacíos.')
    const partes = direccionCompleta ? { calle: calle.trim(), numero: numero.trim(), comuna: comuna.trim() } : null
    haz((x) =>
      guardarPersona(x, {
        nombre: nombre.trim(),
        nombrePila: pila.trim(),
        apoyo,
        direccion: partes ? `${partes.calle} ${partes.numero}, ${partes.comuna}` : '',
        partes,
        idReal: null,
      }),
    )
  }
  return (
    <MarcoAlta paso={2}>
      <Titulo paso={2}>¿A quién cuidas?</Titulo>
      <form
        className="flex flex-col gap-6"
        onSubmit={(e) => {
          e.preventDefault()
          seguir()
        }}
      >
        <div className="grid gap-5 @2xl:grid-cols-2">
          <CampoTexto etiqueta="¿Cómo se llama?" value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="off" maxLength={120} />
          <CampoTexto etiqueta="¿Cómo le dicen?" value={pila} onChange={(e) => setPila(e.target.value)} autoComplete="off" maxLength={60} ayuda="Es el nombre que verá quien te reemplace." />
        </div>
        <GrupoOpciones leyenda="¿Cuánto apoyo necesita en el día a día?" nombre="apoyo" opciones={APOYOS} valor={apoyo} onCambio={setApoyo} columnas />
        <fieldset className="flex flex-col gap-3">
          <legend className="font-bold">¿Dónde vive? Puedes dejarlo para después</legend>
          <p className="-mt-1 text-base text-tenue">La pedimos recién con el primer pedido. La ficha no la usa.</p>
          <div className="grid gap-4 @2xl:grid-cols-[minmax(0,2fr)_minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <CampoTexto etiqueta="Calle" value={calle} onChange={(e) => setCalle(e.target.value)} autoComplete="off" maxLength={120} />
            <CampoTexto etiqueta="Número" value={numero} onChange={(e) => setNumero(e.target.value)} autoComplete="off" maxLength={20} />
            <CampoTexto etiqueta="Comuna" value={comuna} onChange={(e) => setComuna(e.target.value)} autoComplete="off" maxLength={60} />
          </div>
        </fieldset>
        <p className="flex max-w-prose gap-2 bg-rocio px-4 py-3">
          <ShieldCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-pino" />
          <span>No te preguntamos qué enfermedad tiene. No lo necesitamos y no lo guardamos.</span>
        </p>
        {error && <MensajeError>{error}</MensajeError>}
        <Acciones>
          <Boton type="submit">Continuar</Boton>
        </Acciones>
      </form>
    </MarcoAlta>
  )
}

// ---------- Permiso (MATU-07) ----------

export function Permiso() {
  const { s, haz } = useDemo()
  const b = useBackend()
  const ll = useLlamada()
  const pila = s.persona?.nombrePila || 'María'
  const [calidad, setCalidad] = useState<Calidad | null>('cuidador_de_hecho')
  const [leido, setLeido] = useState(false)
  const [referencia, setReferencia] = useState('')
  const [error, setError] = useState<string | null>(null)
  const elegida = CALIDADES.find((c) => c.valor === calidad)

  const accion = (c: Calidad) => async (api: ApiMatu) => {
    const p = s.persona
    if (!p) return
    // La persona y su consentimiento se guardan juntos, o no se guarda nada (MATU-07).
    let grupoId = api.modo === b.api.modo ? b.grupoId : null
    if (!grupoId) {
      const g = await api.crearGrupo(`Cuidado de ${p.nombrePila}`)
      grupoId = g.id
      b.fijarGrupo(g.id)
    }
    api.elegirGrupo(grupoId)
    const r = await api.darDeAlta({
      nombre: p.nombre,
      nombre_pila: p.nombrePila,
      nivel_apoyo: p.apoyo,
      calidad_otorgante: c,
      referencia_documento: c === 'representante_legal' ? referencia.trim() : null,
      aviso: c === 'cuidador_de_hecho' ? { id: AVISO_CUIDADOR.id, version: AVISO_CUIDADOR.version } : null,
      direccion: p.partes ? { calle: p.partes.calle, numero: p.partes.numero, comuna: p.partes.comuna } : null,
    })
    const idReal = api.modo === 'real' ? r.id : null
    haz((x) => darPermiso({ ...x, persona: x.persona ? { ...x.persona, idReal } : x.persona }, c, referencia.trim()))
  }

  const aceptar = () => {
    if (!calidad) return setError('Elige en qué calidad das el permiso.')
    if (calidad === 'representante_legal' && !referencia.trim()) return setError('Escribe la referencia del documento que te nombra representante.')
    if (calidad === 'cuidador_de_hecho' && !leido) return setError('Marca que leíste el aviso para seguir.')
    setError(null)
    void ll.correr(accion(calidad))
  }

  return (
    <MarcoAlta paso={3}>
      <Titulo paso={3} bajada={`Lo que anotes sobre el cuidado de ${pila} es información sensible. Para guardarla necesitamos saber en qué calidad nos das permiso.`}>
        Un permiso necesario
      </Titulo>
      <GrupoOpciones
        leyenda="Doy este permiso porque…"
        nombre="calidad"
        valor={calidad}
        columnas
        onCambio={(v) => {
          setCalidad(v)
          setError(null)
          ll.limpiar()
        }}
        opciones={CALIDADES.map((c) => ({ valor: c.valor, texto: c.texto.replace('Ella', pila), detalle: c.detalle.replace('María', pila) }))}
      />

      {calidad === 'representante_legal' && (
        <CampoTexto
          etiqueta="Referencia del documento"
          value={referencia}
          onChange={(e) => setReferencia(e.target.value)}
          placeholder="Por ejemplo: resolución y fecha"
          maxLength={200}
          className="max-w-xl"
          error={(error && !referencia.trim() ? error : null) ?? ll.error?.campos.referencia_documento}
        />
      )}

      {calidad === 'cuidador_de_hecho' && (
        <section aria-labelledby="aviso-t" className="border-l-4 border-atenta bg-atenta-fondo">
          <h2 id="aviso-t" className="px-5 pt-4 text-lg font-bold">
            {AVISO_CUIDADOR.titulo}
          </h2>
          <div className="flex max-w-prose flex-col gap-2.5 px-5 pt-2 pb-4 leading-relaxed">
            {AVISO_CUIDADOR.parrafos.map((p) => (
              <p key={p.slice(0, 24)}>{p}</p>
            ))}
          </div>
          <label className="flex min-h-12 cursor-pointer items-center gap-3 border-t border-atenta/25 bg-hoja/60 px-5 py-3 font-bold">
            <input
              type="checkbox"
              checked={leido}
              onChange={(e) => {
                setLeido(e.target.checked)
                setError(null)
              }}
              className="size-5 shrink-0 accent-pino"
            />
            Leí el aviso y lo acepto
          </label>
        </section>
      )}

      {elegida && (
        <Nota titulo="Lo que declaras">
          <p className="max-w-prose">{elegida.declaracion}</p>
        </Nota>
      )}
      {error && calidad !== 'representante_legal' && <MensajeError>{error}</MensajeError>}
      <AvisoFalla error={ll.error} onSimulado={() => calidad && void ll.seguirSimulado(accion(calidad))} />
      <Acciones>
        <Boton onClick={aceptar} disabled={ll.ocupado}>
          {ll.ocupado ? 'Guardando el permiso…' : 'Acepto y continúo'}
        </Boton>
      </Acciones>
    </MarcoAlta>
  )
}

/** Las pantallas del alta, por id. */
export function Alta() {
  const { s } = useDemo()
  switch (pantallaFamilia(s).id) {
    case 'cuenta':
      return <Cuenta />
    case 'entrar':
      return <Entrar />
    case 'a-quien':
      return <AQuien />
    case 'permiso':
      return <Permiso />
    default:
      return <Bienvenida />
  }
}

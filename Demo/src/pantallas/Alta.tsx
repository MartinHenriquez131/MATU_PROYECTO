import { useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { useDemo } from '../demo/estado'
import { avisar, conFamilia, crearCuenta, darPermiso, entrar, guardarPersona, ir, pilaFamilia } from '../demo/logica'
import { APOYOS, AVISO_CUIDADOR, CALIDADES } from '../demo/datos'
import type { Apoyo, Calidad, Persona } from '../demo/tipos'
import type { ApiMatu } from '../datos/api'
import type { DireccionVista, PersonaListada } from '../datos/contrato'
import { useBackend } from '../datos/backend'
import { AvisoFalla, useLlamada } from '../datos/useLlamada'
import { Pantalla } from '../components/Pantalla'
import { Boton, CampoTexto, GrupoOpciones, Hoja, Logo, Nota } from '../components/Ui'

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

export function Bienvenida() {
  const { haz } = useDemo()
  const { modo } = useBackend()
  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-pino text-papel">
      {/* Lo propio de MATU asoma desde arriba: la hoja de la ficha, sujeta con su imán. */}
      <div aria-hidden className="pointer-events-none absolute top-7 -right-12 w-[17rem] rotate-[5deg] text-tinta">
        <Hoja>
          <p className="font-display text-[1.45rem] leading-tight font-extrabold tracking-[-0.02em]">Ficha de María</p>
          <ul className="renglones mt-2 leading-[1.75rem]">
            <li>Su día</li>
            <li>Si se altera</li>
            <li>A quién llamar</li>
          </ul>
          <div className="mt-3 flex gap-1.5">
            <span className="h-2.5 flex-1 rounded-full bg-pino" />
            <span className="h-2.5 flex-1 rounded-full bg-pino" />
            <span className="h-2.5 flex-1 rounded-full bg-tinta/10" />
          </div>
        </Hoja>
      </div>
      <div className="relative flex flex-1 flex-col justify-end gap-5 px-7 pb-8">
        <Logo claro className="size-20" />
        <h1 className="font-display text-[3.2rem] leading-[0.95] font-extrabold tracking-[-0.03em]">MATU</h1>
        <p className="max-w-[17rem] text-[1.35rem] leading-snug">Que el cuidado no dependa de una sola persona.</p>
      </div>
      <div className="relative flex flex-col gap-2 px-6 pb-7">
        <button
          type="button"
          onClick={() => haz((s) => ir(s, 'cuenta'))}
          className="min-h-13 rounded-2xl bg-papel px-4 font-bold text-pino hover:brightness-95"
        >
          Empezar
        </button>
        <button
          type="button"
          onClick={() => haz((s) => (modo === 'real' ? ir(s, 'entrar') : pilaFamilia(conFamilia(s), ['inicio'])))}
          className="min-h-12 rounded-2xl px-4 font-bold underline-offset-4 hover:underline"
        >
          Ya tengo cuenta
        </button>
      </div>
    </div>
  )
}

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
    <Pantalla
      titulo="Crea tu cuenta"
      pie={
        <Boton onClick={enviar} disabled={ll.ocupado}>
          {ll.ocupado ? 'Creando la cuenta…' : 'Crear cuenta'}
        </Boton>
      }
    >
      <p className="text-tenue">Para empezar te pedimos solo esto.</p>
      <CampoTexto etiqueta="Tu nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="off" error={campos.nombre} />
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
      {ll.error?.status === 409 ? (
        <Nota tono="atenta" titulo="Ese email ya tiene una cuenta">
          <div className="flex flex-col gap-2">
            <span>Entra con tu contraseña, o usa otro email.</span>
            <Boton variante="secundario" onClick={() => haz((s) => ir(s, 'entrar'))}>
              Entrar con ese email
            </Boton>
          </div>
        </Nota>
      ) : (
        !Object.keys(campos).length && <AvisoFalla error={ll.error} onSimulado={() => void ll.seguirSimulado(accion)} />
      )}
    </Pantalla>
  )
}

export function Entrar() {
  const { haz } = useDemo()
  const b = useBackend()
  const ll = useLlamada()
  const [email, setEmail] = useState(b.credenciales?.email ?? '')
  const [clave, setClave] = useState(b.credenciales?.contrasena ?? '')

  const accion = async (api: ApiMatu) => {
    await api.iniciarSesion(email.trim(), clave)
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
    const nombre = b.credenciales?.email === email.trim().toLowerCase() ? b.credenciales.nombre : ''
    haz((s) => entrar(s, email.trim().toLowerCase(), nombre, api.modo === 'real', persona, calidad))
  }
  return (
    <Pantalla
      titulo="Entrar"
      pie={
        <Boton onClick={() => void ll.correr(accion)} disabled={ll.ocupado || !email || !clave}>
          {ll.ocupado ? 'Entrando…' : 'Entrar'}
        </Boton>
      }
    >
      <CampoTexto etiqueta="Tu email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" />
      <CampoTexto etiqueta="Tu contraseña" type="password" value={clave} onChange={(e) => setClave(e.target.value)} autoComplete="current-password" />
      <p className="text-[0.95rem] text-tenue">Tu sesión dura 15 minutos y no queda guardada en este teléfono.</p>
      <AvisoFalla error={ll.error} onSimulado={() => void ll.seguirSimulado(accion)} />
    </Pantalla>
  )
}

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
    if (!nombre.trim() || !pila.trim() || !apoyo) return setError('Falta su nombre o cómo le dicen.')
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
    <Pantalla titulo="¿A quién cuidas?" pie={<Boton onClick={seguir}>Continuar</Boton>}>
      <CampoTexto etiqueta="¿Cómo se llama?" value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="off" maxLength={120} />
      <CampoTexto
        etiqueta="¿Cómo le dicen?"
        value={pila}
        onChange={(e) => setPila(e.target.value)}
        autoComplete="off"
        maxLength={60}
        ayuda="Es el nombre que verá quien te reemplace."
      />
      <GrupoOpciones leyenda="¿Cuánto apoyo necesita en el día a día?" nombre="apoyo" opciones={APOYOS} valor={apoyo} onCambio={setApoyo} />
      <fieldset className="flex flex-col gap-3">
        <legend className="font-bold">¿Dónde vive? Puedes dejarlo para después</legend>
        <p className="-mt-1 text-[0.95rem] text-tenue">La pedimos recién con el primer pedido. La ficha no la usa.</p>
        <CampoTexto etiqueta="Calle" value={calle} onChange={(e) => setCalle(e.target.value)} autoComplete="off" maxLength={120} />
        <div className="flex flex-wrap gap-3 [&>*]:min-w-[min(100%,7rem)] [&>*]:flex-1">
          <CampoTexto etiqueta="Número" value={numero} onChange={(e) => setNumero(e.target.value)} autoComplete="off" maxLength={20} />
          <CampoTexto etiqueta="Comuna" value={comuna} onChange={(e) => setComuna(e.target.value)} autoComplete="off" maxLength={60} />
        </div>
      </fieldset>
      <p className="flex gap-2 rounded-2xl bg-rocio px-4 py-3 text-[0.95rem]">
        <ShieldCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-pino" />
        <span>No te preguntamos qué enfermedad tiene. No lo necesitamos y no lo guardamos.</span>
      </p>
      {error && (
        <p role="alert" className="font-bold text-pronto">
          {error}
        </p>
      )}
    </Pantalla>
  )
}

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
    if (calidad === 'representante_legal' && !referencia.trim())
      return setError('Escribe la referencia del documento que te nombra representante.')
    if (calidad === 'cuidador_de_hecho' && !leido) return setError('Marca que leíste el aviso para seguir.')
    setError(null)
    void ll.correr(accion(calidad))
  }

  return (
    <Pantalla
      titulo="Un permiso necesario"
      pie={
        <Boton onClick={aceptar} disabled={ll.ocupado}>
          {ll.ocupado ? 'Guardando…' : 'Acepto y continúo'}
        </Boton>
      }
    >
      <p>
        Lo que anotes sobre el cuidado de {pila} es información sensible. Para guardarla necesitamos saber en qué calidad nos das
        permiso.
      </p>
      <GrupoOpciones
        leyenda="Doy este permiso porque…"
        nombre="calidad"
        valor={calidad}
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
          error={(error && !referencia.trim() ? error : null) ?? ll.error?.campos.referencia_documento}
        />
      )}

      {calidad === 'cuidador_de_hecho' && (
        <section aria-labelledby="aviso-t" className="overflow-hidden rounded-[1.35rem] bg-atenta-fondo ring-1 ring-atenta/30">
          <h2 id="aviso-t" className="px-4 pt-4 font-display text-[1.1rem] font-bold">
            {AVISO_CUIDADOR.titulo}
          </h2>
          <div className="flex flex-col gap-2.5 px-4 pt-2 pb-3 text-[0.95rem] leading-relaxed">
            {AVISO_CUIDADOR.parrafos.map((p) => (
              <p key={p.slice(0, 20)}>{p}</p>
            ))}
          </div>
          <label className="flex min-h-13 cursor-pointer items-center gap-3 border-t border-atenta/25 bg-hoja/60 px-4 py-3 font-bold">
            <input
              type="checkbox"
              checked={leido}
              onChange={(e) => {
                setLeido(e.target.checked)
                setError(null)
              }}
              className="size-6 shrink-0 accent-[var(--color-pino)]"
            />
            Leí el aviso y lo acepto
          </label>
        </section>
      )}

      {elegida && (
        <Nota titulo="Lo que declaras">
          <p>{elegida.declaracion}</p>
        </Nota>
      )}
      {error && (
        <p role="alert" className="font-bold text-pronto">
          {error}
        </p>
      )}
      <AvisoFalla error={ll.error} onSimulado={() => calidad && void ll.seguirSimulado(accion(calidad))} />
    </Pantalla>
  )
}

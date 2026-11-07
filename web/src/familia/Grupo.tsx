// Grupo familiar, retirar una autorización y volver a autorizar (MATU-44, especificación
// docs/diseno/matu-44-retirar-autorizacion.md v1.1). Contrato: `GET …/consentimientos`,
// `POST …/consentimientos/{finalidad}/retiro` y `POST …/consentimientos` (decisiones 123 a 135).
//
// - Sin interfaz optimista: el bloque cambia solo con la respuesta de la API, y el retiro espera.
// - La pantalla no suma 90 días ni decide qué se borró: `estado`, `borrado_en` y `borrada` los da la API.
// - Nunca muestra la calidad de quien autorizó (familia.ts la descarta al leer).
// - Nada se guarda en el navegador ni en la URL: al volver a `/grupo` se pide todo de nuevo. Después
//   de retirar la ficha, la que estaba en memoria se descarta.
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { CloudOff, Hourglass, Lock, ShieldCheck, ShieldOff, ShieldQuestion } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import {
  autorizar,
  leerAutorizaciones,
  listarAccesos,
  listarPersonas,
  nombrePilaDe,
  retirarAutorizacion,
  type AutorizacionVista,
  type Finalidad,
  type PersonaListada,
} from '../compartido/api/familia'
import { esVencida } from '../compartido/api/sesion'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { Boton } from '../compartido/ui/Boton'
import { DeclaracionFicha, useDeclaracionFicha } from './Alta'
import { useDemora } from './Estados'
import { puedeEditar, useFamilia } from './estado'
import { AvisoDeLlegada, ErrorAlCargar, SinAcceso } from './Ficha'
import { esTipo } from './insumosComun'
import { Permiso } from './Insumos'
import { navegar } from './ruteo'
import { AUTORIZACION, GENERAL } from './textos'
import { GRUPO_FAMILIAR as T } from './textosGrupo'
import { Acciones, MensajeError, Nota, Pagina, Titulo, Volver } from './ui'

/** Con la autorización vigente o por renovar: hay algo que retirar. */
const autorizada = (v: AutorizacionVista | undefined) => v?.estado === 'vigente' || v?.estado === 'revision_vencida'
/** Retirada o ya borrada: se puede volver a autorizar. */
const retirada = (v: AutorizacionVista | undefined) => v?.estado === 'retirada' || v?.estado === 'borrada'
/** Lo guardado ya no vuelve (decisión 127: `borrada` aunque la tarea todavía no haya corrido). */
const seBorro = (v: AutorizacionVista) => v.estado === 'borrada' || v.borrada

/** DD/MM/AAAA en la hora de Chile, en su `cifras`. */
function Fecha({ iso }: { iso: string | null }) {
  if (!iso || Number.isNaN(new Date(iso).getTime())) return null
  return <span className="cifras">{fechaYHoraDeChile(new Date(iso)).fecha}</span>
}
const fechaTexto = (iso: string | null) => (iso && !Number.isNaN(new Date(iso).getTime()) ? fechaYHoraDeChile(new Date(iso)).fecha : '')

// ---------------------------------------------------------------- 3 Grupo familiar

interface DatosPersona {
  persona: PersonaListada
  /** `[plan_cuidado, consumo]`, en el orden del contrato. */
  vistas: AutorizacionVista[]
  /** 2.2: cuántos enlaces hay hoy. `null` si no se pidió o falló: la confirmación omite la frase. */
  enlaces: number | null
}

type AvisoBloque = { tono: 'ok' | 'rocio'; texto: string }
const claveDe = (personaId: string, finalidad: Finalidad) => `${personaId}-${finalidad}`

export function GrupoFamiliar() {
  const { grupo, rol, personaId: elegidaId, fijar, reautorizar } = useFamilia()
  const editor = puedeEditar(rol)
  const [carga, setCarga] = useState<'cargando' | 'lista' | 'red'>('cargando')
  const [datos, setDatos] = useState<DatosPersona[]>([])
  const [avisos, setAvisos] = useState<Record<string, AvisoBloque>>({})
  const [retirando, setRetirando] = useState<{ datos: DatosPersona; finalidad: Finalidad } | null>(null)
  const enfocarAviso = useRef<string | null>(null)

  // 2.1: la intención de volver a autorizar dura solo hasta volver aquí.
  useEffect(() => {
    if (reautorizar) fijar({ reautorizar: null })
  }, [reautorizar, fijar])

  const cargar = useCallback(async () => {
    if (!grupo) return
    setCarga('cargando')
    try {
      const personas = await listarPersonas(grupo.id)
      const lista = await Promise.all(
        personas.map(async (persona): Promise<DatosPersona | null> => {
          try {
            const vistas = await leerAutorizaciones(persona.id)
            let enlaces: number | null = null
            if (editor && autorizada(vistas[0])) {
              enlaces = await listarAccesos(persona.id, { estado: 'vigente', limite: 100 })
                .then((r) => r.items.length)
                .catch(() => null)
            }
            return { persona, vistas, enlaces }
          } catch (x) {
            // 3.7: una persona con 404 sale de la lista.
            if (leerFallo(x).status === 404) return null
            throw x
          }
        }),
      )
      setDatos(lista.filter((d): d is DatosPersona => d !== null))
      setCarga('lista')
    } catch (x) {
      if (esVencida(x)) return
      setCarga('red')
    }
  }, [grupo, editor])

  useEffect(() => {
    void cargar()
  }, [cargar])

  // 3.5: la confirmación recibe el foco cuando ya está en la pantalla.
  useEffect(() => {
    const id = enfocarAviso.current
    if (!id) return
    enfocarAviso.current = null
    document.getElementById(`aviso-${id}`)?.focus()
  }, [avisos])

  const conAviso = (clave: string, aviso: AvisoBloque) => {
    enfocarAviso.current = clave
    setAvisos((x) => ({ ...x, [clave]: aviso }))
  }

  const cambiarVista = (personaId: string, vista: AutorizacionVista) =>
    setDatos((xs) => xs.map((d) => (d.persona.id === personaId ? { ...d, vistas: d.vistas.map((v) => (v.finalidad === vista.finalidad ? vista : v)) } : d)))

  const alRetirar = (d: DatosPersona, finalidad: Finalidad, vista: AutorizacionVista, cortados: number) => {
    setRetirando(null)
    cambiarVista(d.persona.id, vista)
    // 4.5: la ficha que estaba en memoria sale, y la app sabe que se retiró (decisión 131).
    if (finalidad === 'plan_cuidado' && d.persona.id === elegidaId) fijar({ ficha: null, autorizacion: 'sin-consentimiento' })
    const pila = nombrePilaDe(d.persona)
    conAviso(claveDe(d.persona.id, finalidad), { tono: 'ok', texto: finalidad === 'plan_cuidado' ? T.retiradaFicha(cortados) : T.retiradaInsumos(pila) })
  }

  const alYaRetirada = async (d: DatosPersona, finalidad: Finalidad) => {
    setRetirando(null)
    if (finalidad === 'plan_cuidado' && d.persona.id === elegidaId) fijar({ ficha: null, autorizacion: 'sin-consentimiento' })
    try {
      const vistas = await leerAutorizaciones(d.persona.id)
      setDatos((xs) => xs.map((x) => (x.persona.id === d.persona.id ? { ...x, vistas } : x)))
    } catch (x) {
      if (esVencida(x)) return
      if (leerFallo(x).status === 404) return void cargar()
    }
    conAviso(claveDe(d.persona.id, finalidad), { tono: 'rocio', texto: T.yaRetirada })
  }

  const alNoEncontrado = () => {
    setRetirando(null)
    void cargar().then(() => document.getElementById('titulo-pagina')?.focus())
  }

  const volverAAutorizar = (d: DatosPersona, finalidad: Finalidad, vista: AutorizacionVista) => {
    // 2.1: la persona se elige en memoria, como en el selector del encabezado (es del mismo grupo, así
    // que no hay que pedir la lista otra vez). La ruta no lleva su id. Elegirla, fijar la intención y
    // cambiar de ruta van juntos: Grupo familiar no se vuelve a dibujar con la intención a medias.
    const otra = d.persona.id !== elegidaId
    flushSync(() => {
      fijar({ ...(otra ? { personaId: d.persona.id, ficha: null, autorizacion: null } : {}), reautorizar: { personaId: d.persona.id, finalidad, vista } })
      navegar(finalidad === 'plan_cuidado' ? '/grupo/autorizar-ficha' : '/grupo/autorizar-insumos')
    })
  }

  let cuerpo: ReactNode
  if (carga === 'cargando') cuerpo = <Cargando />
  else if (carga === 'red')
    cuerpo = (
      <div className="flex max-w-prose flex-col items-start gap-4">
        <Nota tono="atenta" rol="alert" icono={<CloudOff aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
          {T.errCargar}
        </Nota>
        <Boton variante="secundario" onClick={() => void cargar()}>
          {T.intentar}
        </Boton>
      </div>
    )
  else if (!datos.length)
    cuerpo = (
      <Nota tono="rocio" icono={<Lock aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
        {GENERAL.noEncontrado}
      </Nota>
    )
  else
    cuerpo = (
      <div className="flex flex-col gap-10">
        {datos.map((d) => (
          <section key={d.persona.id} aria-labelledby={`persona-${d.persona.id}`} className="flex flex-col gap-4">
            <h2 id={`persona-${d.persona.id}`} className="text-xl font-bold break-words">
              {d.persona.nombre}
            </h2>
            <div className="grid grid-cols-1 items-start gap-6 @3xl/main:grid-cols-2">
              {d.vistas.map((v) => (
                <Bloque
                  key={v.finalidad}
                  vista={v}
                  pila={nombrePilaDe(d.persona)}
                  personaId={d.persona.id}
                  editor={editor}
                  aviso={avisos[claveDe(d.persona.id, v.finalidad)] ?? null}
                  onRetirar={() => setRetirando({ datos: d, finalidad: v.finalidad })}
                  onVolver={() => volverAAutorizar(d, v.finalidad, v)}
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    )

  return (
    <Pagina titulo={T.titulo} bajada={grupo ? T.bajada(grupo.nombre) : undefined}>
      <div className="max-w-5xl">
        <AvisoDeLlegada />
        {cuerpo}
      </div>
      {retirando && (
        <DialogoRetirar
          datos={retirando.datos}
          finalidad={retirando.finalidad}
          onCancelar={() => {
            const id = `retirar-${claveDe(retirando.datos.persona.id, retirando.finalidad)}`
            setRetirando(null)
            window.setTimeout(() => document.getElementById(id)?.focus(), 0)
          }}
          onRetirada={(r) => alRetirar(retirando.datos, retirando.finalidad, r.autorizacion, r.enlaces_cortados)}
          onYaRetirada={() => void alYaRetirada(retirando.datos, retirando.finalidad)}
          onNoEncontrado={alNoEncontrado}
        />
      )}
    </Pagina>
  )
}

/** 3.7: «Cargando…» pasados 400 ms, en lugar de las secciones. */
function Cargando() {
  const ver = useDemora()
  return (
    <p role="status" className="text-tenue">
      {ver ? T.cargando : ''}
    </p>
  )
}

// ---------------------------------------------------------------- 3.3 a 3.6 un bloque

/** 3.4: cada estado con su ícono distinto y su frase, nunca solo color. */
function EstadoBloque({ v, editor }: { v: AutorizacionVista; editor: boolean }) {
  const ficha = v.finalidad === 'plan_cuidado'
  const icono = 'mt-0.5 size-5 shrink-0'
  let Icono = ShieldQuestion
  let tono = 'text-tenue'
  let frase: ReactNode
  if (v.estado === 'vigente') {
    Icono = ShieldCheck
    tono = 'text-ok'
    frase = (
      <>
        {ficha ? T.autorizadaFicha : T.autorizadoInsumos} <Fecha iso={v.otorgado_en} />.
      </>
    )
  } else if (v.estado === 'revision_vencida') {
    Icono = Hourglass
    tono = 'text-atenta'
    frase = (
      <>
        {ficha ? T.autorizadaFicha : T.autorizadoInsumos} <Fecha iso={v.otorgado_en} />. {ficha ? T.renovarFicha : T.renovarInsumos}{' '}
        <Fecha iso={v.revision_vence_en} />.
      </>
    )
  } else if (v.estado === 'retirada') {
    Icono = ShieldOff
    frase = (
      <>
        {T.retiradaEl} <Fecha iso={v.revocado_en} />.{' '}
        {v.borrado_en ? (
          <>
            {editor ? T.siNoVuelves : T.siNadieVuelve} <Fecha iso={v.borrado_en} />.
          </>
        ) : (
          T.siNoVuelvesSinFecha
        )}
      </>
    )
  } else if (v.estado === 'borrada') {
    Icono = ShieldOff
    frase = (
      <>
        {T.retiradaEl} <Fecha iso={v.revocado_en} />. {T.seBorro} <Fecha iso={v.borrado_en} />.
      </>
    )
  } else frase = T.sinAutorizar
  return (
    <p className="flex gap-2 text-base">
      <Icono aria-hidden className={`${icono} ${tono}`} />
      <span className="min-w-0">{frase}</span>
    </p>
  )
}

function Bloque({
  vista: v,
  pila,
  personaId,
  editor,
  aviso,
  onRetirar,
  onVolver,
}: {
  vista: AutorizacionVista
  pila: string
  personaId: string
  editor: boolean
  aviso: AvisoBloque | null
  onRetirar: () => void
  onVolver: () => void
}) {
  const clave = claveDe(personaId, v.finalidad)
  const ficha = v.finalidad === 'plan_cuidado'
  const conBorde = autorizada(v) ? 'bg-hoja ring-1 ring-linea' : 'bg-papel border-2 border-dashed border-borde'
  return (
    <section aria-labelledby={`bloque-${clave}`} className={`flex min-w-0 flex-col gap-3 rounded-xl px-4 angosto:px-2 py-4 ${conBorde}`}>
      <h3 id={`bloque-${clave}`} className="text-lg font-bold break-words">
        {ficha ? T.tituloFicha : T.tituloInsumos}
      </h3>
      {aviso && (
        <Nota id={`aviso-${clave}`} tono={aviso.tono} rol="status" enfocable>
          {aviso.texto}
        </Nota>
      )}
      <EstadoBloque v={v} editor={editor} />
      {editor && autorizada(v) && (
        <Boton id={`retirar-${clave}`} variante="peligro" className="self-start" aria-label={ficha ? T.retirarFichaDe(pila) : T.retirarInsumosDe(pila)} onClick={onRetirar}>
          {T.retirar}
        </Boton>
      )}
      {editor && retirada(v) && (
        <Boton id={`volver-${clave}`} variante="secundario" className="self-start" aria-label={ficha ? T.volverFichaDe(pila) : T.volverInsumosDe(pila)} onClick={onVolver}>
          {T.volverAAutorizar}
        </Boton>
      )}
      {!editor && autorizada(v) && <p className="text-base text-tenue">{T.puedeRetirarla(pila)}</p>}
      {!editor && retirada(v) && <p className="text-base text-tenue">{T.puedeVolverAAutorizarla(pila)}</p>}
    </section>
  )
}

// ---------------------------------------------------------------- 4 la confirmación

function DialogoRetirar({
  datos,
  finalidad,
  onCancelar,
  onRetirada,
  onYaRetirada,
  onNoEncontrado,
}: {
  datos: DatosPersona
  finalidad: Finalidad
  onCancelar: () => void
  onRetirada: (r: { autorizacion: AutorizacionVista; enlaces_cortados: number }) => void
  onYaRetirada: () => void
  onNoEncontrado: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const titulo = useRef<HTMLHeadingElement>(null)
  const uid = useId()
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState(false)
  // La petición ya salió: «No retirar» y Esc no la cancelan (4.4).
  const enCurso = useRef(false)
  const pila = nombrePilaDe(datos.persona)
  const [vFicha, vInsumos] = datos.vistas
  const ficha = finalidad === 'plan_cuidado'

  useEffect(() => {
    const d = ref.current
    if (d && !d.open) d.showModal()
    // 4.4: el foco en el título, para que la pregunta se lea y se vea primero.
    titulo.current?.focus()
  }, [])

  const cerrar = () => {
    if (ref.current?.open) ref.current.close()
  }

  const retirar = async () => {
    if (enCurso.current) return
    enCurso.current = true
    setOcupado(true)
    setError(false)
    try {
      const r = await retirarAutorizacion(datos.persona.id, finalidad)
      cerrar()
      onRetirada(r)
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 409 && esTipo(f.tipo, 'ya-retirada')) {
        cerrar()
        return onYaRetirada()
      }
      if (f.status === 404) {
        cerrar()
        return onNoEncontrado()
      }
      setError(true)
    } finally {
      enCurso.current = false
      setOcupado(false)
    }
  }

  const cancelar = () => {
    if (enCurso.current) return
    cerrar()
    onCancelar()
  }

  // 4.3: «Hoy abren {n}», o «Hoy están en pausa {n}» con la revisión vencida. Sin conteo, se omite.
  const conteo = datos.enlaces === null ? '' : vFicha?.estado === 'revision_vencida' ? T.hoyEnPausa(datos.enlaces) : T.hoyAbren(datos.enlaces)
  const puntos: { texto: string; fuerte?: boolean }[] = ficha
    ? [
        { texto: T.fichaNadie },
        { texto: [T.fichaSeCortan, conteo, T.fichaAbierta].filter(Boolean).join(' ') },
        { texto: T.fichaNoVuelve, fuerte: true },
        { texto: T.fichaGuardado },
        ...(autorizada(vInsumos) ? [{ texto: T.fichaInsumosNoCambia }] : []),
      ]
    : [
        { texto: T.insumosDejamos },
        { texto: T.insumosNadie },
        { texto: T.insumosGuardado },
        { texto: T.insumosLista, fuerte: true },
        { texto: T.insumosFichaNoCambia },
      ]

  return (
    <dialog
      ref={ref}
      aria-labelledby={`${uid}-t`}
      aria-describedby={`${uid}-d`}
      onCancel={(e) => {
        e.preventDefault()
        cancelar()
      }}
      className="m-auto w-[calc(100%-2rem)] angosto:w-[calc(100%-1rem)] max-w-lg max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-2xl bg-hoja p-6 angosto:px-2 angosto:py-4 text-tinta backdrop:bg-tinta/40"
    >
      <div className="flex flex-col gap-4">
        <h2 ref={titulo} id={`${uid}-t`} tabIndex={-1} className="text-xl font-bold break-words outline-none">
          {ficha ? T.preguntaFicha(pila) : T.preguntaInsumos(pila)}
        </h2>
        <ul id={`${uid}-d`} className="flex max-w-prose list-disc flex-col gap-2 ps-5 text-base leading-relaxed marker:text-tenue">
          {puntos.map((p) => (
            <li key={p.texto} className={p.fuerte ? 'font-bold' : undefined}>
              {p.texto}
            </li>
          ))}
        </ul>
        {/* Con `showModal` lo de fuera queda inerte, también las regiones vivas de main.tsx: el
            error usa su propia región, montada vacía con el diálogo (como eliminar, MATU-36). */}
        <div role="alert" className="empty:-mb-4">
          {error && <MensajeError>{T.errRetirar}</MensajeError>}
        </div>
        <Acciones>
          <Boton variante="peligroPrincipal" ocupado={ocupado} textoOcupado={T.retirando} onClick={() => void retirar()}>
            {T.retirar}
          </Boton>
          <button
            type="button"
            aria-disabled={ocupado || undefined}
            onClick={cancelar}
            className="inline-flex min-h-12 items-center px-2 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
          >
            {T.noRetirar}
          </button>
        </Acciones>
      </div>
    </dialog>
  )
}

// ---------------------------------------------------------------- 5 volver a autorizar

/** La vista de la autorización a volver a dar: la de Grupo familiar o, desde la ficha, una lectura nueva. */
function useVistaAReautorizar(finalidad: Finalidad) {
  const { reautorizar, personaId } = useFamilia()
  const inicial = reautorizar?.finalidad === finalidad && reautorizar.personaId === personaId ? reautorizar.vista : null
  const [vista, setVista] = useState<AutorizacionVista | null>(inicial)
  const [falla, setFalla] = useState<'red' | 'no-encontrado' | null>(null)

  const pedir = useCallback(async () => {
    if (!personaId) return
    setFalla(null)
    try {
      const vistas = await leerAutorizaciones(personaId)
      setVista(vistas.find((v) => v.finalidad === finalidad) ?? null)
    } catch (x) {
      if (esVencida(x)) return
      setFalla(leerFallo(x).status === 404 ? 'no-encontrado' : 'red')
    }
  }, [personaId, finalidad])

  useEffect(() => {
    if (!inicial) void pedir()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 2.1: sin una autorización retirada o borrada, no hay nada que volver a dar.
  useEffect(() => {
    if (vista && !retirada(vista)) navegar('/grupo', { reemplazar: true })
  }, [vista])

  return { vista, falla, pedir }
}

function CargandoVista({ falla, pedir }: { falla: 'red' | 'no-encontrado' | null; pedir: () => void }) {
  if (falla === 'no-encontrado') return <SinAcceso />
  if (falla === 'red')
    return (
      <Pagina titulo={T.titulo}>
        <ErrorAlCargar reintentar={pedir} />
      </Pagina>
    )
  return (
    <Pagina titulo={T.titulo}>
      <Cargando />
    </Pagina>
  )
}

function VolverAGrupo() {
  return <Volver onClick={() => navegar('/grupo')}>{T.volverAGrupo}</Volver>
}

/** El aviso de 5.3 tiene que estar en memoria antes de que se monte `/grupo`. */
function volverConAviso(cambios: Parameters<ReturnType<typeof useFamilia>['fijar']>[0], fijar: ReturnType<typeof useFamilia>['fijar']) {
  flushSync(() => fijar(cambios))
  navegar('/grupo')
}

/** 5.1: el cuerpo de la autorización del alta, sin su marco, en el esqueleto de la app. */
export function AutorizarFicha() {
  const { persona, personaId, fijar } = useFamilia()
  const { vista, falla: fallaVista, pedir } = useVistaAReautorizar('plan_cuidado')
  const d = useDeclaracionFicha()
  const [falla, setFalla] = useState<'422' | 'red' | 'no-encontrado' | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const pila = persona ? nombrePilaDe(persona) : ''

  if (!vista || !retirada(vista)) return <CargandoVista falla={fallaVista} pedir={() => void pedir()} />
  if (falla === 'no-encontrado') return <SinAcceso />
  const enBlanco = seBorro(vista)

  const aceptar = async () => {
    if (ocupado || !personaId) return
    setFalla(null)
    const otorgamiento = d.validar()
    if (!otorgamiento) return
    setOcupado(true)
    try {
      await autorizar(personaId, { finalidad: 'plan_cuidado', ...otorgamiento })
      // 5.3: la ficha se vuelve a pedir al abrirla; la de antes ya no está en memoria.
      volverConAviso({ ficha: null, autorizacion: null, reautorizar: null, aviso: { titulo: enBlanco ? T.registradaFichaEnBlanco(pila) : T.registradaFicha(pila), tono: 'ok' } }, fijar)
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 409 && esTipo(f.tipo, 'autorizacion-vigente')) {
        return volverConAviso({ ficha: null, autorizacion: null, reautorizar: null, aviso: { titulo: T.yaAutorizada, tono: 'rocio' } }, fijar)
      }
      if (f.status === 404) return setFalla('no-encontrado')
      if (f.status === 422 && f.campos.includes('referencia_documento')) return d.setError('referencia')
      setFalla(f.status === 422 ? '422' : 'red')
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <VolverAGrupo />
        <Titulo className="text-3xl @2xl/main:text-5xl">{AUTORIZACION.titulo}</Titulo>
        <p className="max-w-prose text-base text-tenue">{AUTORIZACION.bajada(pila)}</p>
        <p className="max-w-prose text-base">{enBlanco ? T.fichaSeBorro(fechaTexto(vista.borrado_en)) : T.fichaVuelve}</p>
      </div>
      <DeclaracionFicha pila={pila} d={d} />
      {falla === '422' && (
        <Nota tono="pronto" rol="alert">
          {T.errAutorizar}
        </Nota>
      )}
      {falla === 'red' && (
        <Nota tono="pronto" rol="alert">
          {GENERAL.error}
        </Nota>
      )}
      <Acciones>
        <Boton onClick={() => void aceptar()} ocupado={ocupado} textoOcupado={T.fichaEnviando}>
          {T.fichaBoton}
        </Boton>
      </Acciones>
    </div>
  )
}

/** 5.2: el permiso de los insumos de MATU-36, sin cambiarlo, con la vuelta y la frase de estado. */
export function AutorizarInsumos() {
  const { persona, personaId, fijar } = useFamilia()
  const { vista, falla, pedir } = useVistaAReautorizar('consumo')
  const [noEncontrado, setNoEncontrado] = useState(false)
  const pila = persona ? nombrePilaDe(persona) : ''

  if (!vista || !retirada(vista)) return <CargandoVista falla={falla} pedir={() => void pedir()} />
  if (noEncontrado)
    return (
      <Pagina titulo={T.titulo}>
        <Nota tono="rocio" icono={<Lock aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
          {GENERAL.noEncontrado}
        </Nota>
      </Pagina>
    )
  const enBlanco = seBorro(vista)
  const fecha = fechaTexto(vista.borrado_en)

  return (
    <Permiso
      pila={pila}
      personaId={personaId}
      antes=<VolverAGrupo />
      frase={<p className="max-w-prose text-base">{enBlanco ? T.insumosSeBorro(fecha) : T.insumosVuelve(fecha)}</p>}
      onListo={(yaVigente) => {
        volverConAviso(
          { reautorizar: null, aviso: yaVigente ? { titulo: T.yaAutorizada, tono: 'rocio' } : { titulo: enBlanco ? T.guardadoInsumosEnBlanco : T.guardadoInsumos, tono: 'ok' } },
          fijar,
        )
      }}
      onNoEncontrado={() => setNoEncontrado(true)}
    />
  )
}

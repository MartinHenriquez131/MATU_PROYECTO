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
  borrarPersona,
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
import { BORRADOR_VACIO, puedeEditar, useFamilia, type BorradorPersona } from './estado'
import { AvisoDeLlegada, ErrorAlCargar, SinAcceso } from './Ficha'
import { esTipo } from './insumosComun'
import { Permiso } from './Insumos'
import { navegar } from './ruteo'
import { AUTORIZACION, GENERAL } from './textos'
import { BORRAR_DATOS as B, GRUPO_FAMILIAR as T } from './textosGrupo'
import { GRUPO_PEDIDOS as P } from './textosPedido'
import { Acciones, MensajeError, Nota, Pagina, Titulo, Volver } from './ui'

/** Con la autorización vigente o por renovar: hay algo que retirar. */
const autorizada = (v: AutorizacionVista | undefined) => v?.estado === 'vigente' || v?.estado === 'revision_vencida'
/** Retirada o ya borrada: se puede volver a autorizar. */
const retirada = (v: AutorizacionVista | undefined) => v?.estado === 'retirada' || v?.estado === 'borrada'
/** Lo guardado ya no vuelve (decisión 127: `borrada` aunque la tarea todavía no haya corrido). */
const seBorro = (v: AutorizacionVista) => v.estado === 'borrada' || v.borrada

/**
 * DD/MM/AAAA en la hora de Chile, en su `cifras`, con el signo que la sigue (`fin`) dentro del mismo
 * `cifras`: si queda fuera, en modo angosto el punto baja solo a un renglón (3.4, revisión del 07-11).
 */
function Fecha({ iso, fin = '' }: { iso: string | null; fin?: string }) {
  if (!iso || Number.isNaN(new Date(iso).getTime())) return null
  return (
    <span className="cifras">
      {fechaYHoraDeChile(new Date(iso)).fecha}
      {fin}
    </span>
  )
}

/** Una frase de textosGrupo con una fecha: `[antes, pegado a la fecha, después]`. */
function ConFecha({ partes: [antes, pegado, despues], iso }: { partes: readonly [string, string, string]; iso: string | null }) {
  return (
    <>
      {antes}
      <Fecha iso={iso} fin={pegado} />
      {despues}
    </>
  )
}

// ---------------------------------------------------------------- 3 Grupo familiar

interface DatosPersona {
  persona: PersonaListada
  /** `[plan_cuidado, consumo]`, en el orden del contrato, y `despacho` con la capa 3 (MATU-61, C2). */
  vistas: AutorizacionVista[]
  /** 2.2: cuántos enlaces hay hoy. `null` si no se pidió o falló: la confirmación omite la frase. */
  enlaces: number | null
}

type AvisoBloque = { tono: 'ok' | 'rocio'; texto: string }
const claveDe = (personaId: string, finalidad: Finalidad) => `${personaId}-${finalidad}`

/** MATU-72 4.1: el borrador del alta tiene el nombre de la persona borrada. */
function borradorDe(b: BorradorPersona, p: PersonaListada) {
  const igual = (a: string, x: string | null | undefined) => !!a.trim() && !!x && a.trim().toLocaleLowerCase('es-CL') === x.trim().toLocaleLowerCase('es-CL')
  const pila = 'nombre_pila' in p ? p.nombre_pila : null
  return igual(b.nombre, p.nombre) || igual(b.pila, pila) || igual(b.pila, p.nombre) || igual(b.nombre, pila)
}

export function GrupoFamiliar() {
  const { grupo, rol, personaId: elegidaId, personas: enMemoria, borrador, fijar, reautorizar } = useFamilia()
  const editor = puedeEditar(rol)
  const [carga, setCarga] = useState<'cargando' | 'lista' | 'red'>('cargando')
  const [datos, setDatos] = useState<DatosPersona[]>([])
  const [avisos, setAvisos] = useState<Record<string, AvisoBloque>>({})
  const [retirando, setRetirando] = useState<{ datos: DatosPersona; finalidad: Finalidad } | null>(null)
  const [borrando, setBorrando] = useState<DatosPersona | null>(null)
  // MATU-72 4.3: la nota de llegada se vuelve a montar para mostrar la del borrado sin cambiar de ruta.
  const [llegada, setLlegada] = useState(0)
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
    const texto = finalidad === 'plan_cuidado' ? T.retiradaFicha(cortados) : finalidad === 'despacho' ? P.retirada(pila) : T.retiradaInsumos(pila)
    conAviso(claveDe(d.persona.id, finalidad), { tono: 'ok', texto })
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
    setBorrando(null)
    void cargar().then(() => document.getElementById('titulo-pagina')?.focus())
  }

  /**
   * MATU-72 4.1 y 4.2: con el 200 o el 409 la persona sale de toda la memoria en una sola llamada a
   * `fijar`. Si no queda nadie, la regla de MATU-39 5.4 lleva a `/empezar/persona`; si quedan otras,
   * Grupo familiar sigue sin su sección y el foco va a la nota. Su nombre solo sigue en la nota.
   */
  const sacarDeLaApp = (d: DatosPersona, aviso: AvisoBloque) => {
    const id = d.persona.id
    const quedan = enMemoria.filter((p) => p.id !== id)
    const era = id === elegidaId
    flushSync(() => {
      setBorrando(null)
      setDatos((xs) => xs.filter((x) => x.persona.id !== id))
      setAvisos((xs) => Object.fromEntries(Object.entries(xs).filter(([clave]) => !clave.startsWith(`${id}-`))))
      setLlegada((n) => n + 1)
      fijar({
        personas: quedan,
        ...(era ? { personaId: quedan[0]?.id ?? null, ficha: null, autorizacion: null } : {}),
        ...(reautorizar?.personaId === id ? { reautorizar: null } : {}),
        ...(borradorDe(borrador, d.persona) ? { borrador: BORRADOR_VACIO } : {}),
        aviso: { titulo: aviso.texto, tono: aviso.tono, enfocar: quedan.length > 0 },
      })
    })
  }

  const volverAAutorizar = (d: DatosPersona, finalidad: Finalidad, vista: AutorizacionVista) => {
    // 2.1: la persona se elige en memoria, como en el selector del encabezado (es del mismo grupo, así
    // que no hay que pedir la lista otra vez). La ruta no lleva su id. Elegirla, fijar la intención y
    // cambiar de ruta van juntos: Grupo familiar no se vuelve a dibujar con la intención a medias.
    const otra = d.persona.id !== elegidaId
    flushSync(() => {
      fijar({ ...(otra ? { personaId: d.persona.id, ficha: null, autorizacion: null } : {}), reautorizar: { personaId: d.persona.id, finalidad, vista } })
      navegar(finalidad === 'plan_cuidado' ? '/grupo/autorizar-ficha' : finalidad === 'despacho' ? '/grupo/autorizar-pedidos' : '/grupo/autorizar-insumos')
    })
  }

  /** MATU-61 (12.1, C8): la dirección de entrega de la persona, para verla o vaciarla aunque se haya retirado el permiso. */
  const verDireccion = (d: DatosPersona) => {
    const otra = d.persona.id !== elegidaId
    flushSync(() => {
      fijar({ ...(otra ? { personaId: d.persona.id, ficha: null, autorizacion: null } : {}), direccionDesdeGrupo: true })
      navegar('/insumos/pedido/direccion')
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
                  conDireccion={v.finalidad === 'despacho' && 'direccion' in d.persona && !!d.persona.direccion}
                  onVerDireccion={() => verDireccion(d)}
                />
              ))}
            </div>
            <BloqueBorrar persona={d.persona} editor={editor} onBorrar={() => setBorrando(d)} />
          </section>
        ))}
      </div>
    )

  return (
    <Pagina titulo={T.titulo} bajada={grupo ? T.bajada(grupo.nombre) : undefined}>
      <div className="max-w-5xl">
        <AvisoDeLlegada key={llegada} />
        {cuerpo}
      </div>
      {borrando && (
        <DialogoBorrar
          datos={borrando}
          onCancelar={() => {
            const id = `borrar-${borrando.persona.id}`
            setBorrando(null)
            window.setTimeout(() => document.getElementById(id)?.focus(), 0)
          }}
          onBorrada={(r) => sacarDeLaApp(borrando, { tono: 'ok', texto: B.hecho(nombrePilaDe(borrando.persona), r.enlaces_cortados) })}
          onYaBorrada={() => sacarDeLaApp(borrando, { tono: 'rocio', texto: B.yaBorrada(nombrePilaDe(borrando.persona)) })}
          onNoEncontrado={alNoEncontrado}
        />
      )}
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
  // MATU-61 (12.1): los pedidos no guardan nada que se borre a los 90 días: la retirada va sin esa frase.
  const pedidos = v.finalidad === 'despacho'
  // 3.3 (revisión del 07-11): en modo angosto el ícono va en la primera línea, como en `MensajeError`.
  const icono = 'mt-0.5 size-5 shrink-0 angosto:mt-0 angosto:mr-1.5 angosto:inline angosto:align-middle'
  let Icono = ShieldQuestion
  let tono = 'text-tenue'
  let frase: ReactNode
  if (v.estado === 'vigente') {
    Icono = ShieldCheck
    tono = 'text-ok'
    frase = (
      <>
        {ficha ? T.autorizadaFicha : T.autorizadoInsumos} <Fecha iso={v.otorgado_en} fin="." />
      </>
    )
  } else if (v.estado === 'revision_vencida') {
    Icono = Hourglass
    tono = 'text-atenta'
    frase = (
      <>
        {ficha ? T.autorizadaFicha : T.autorizadoInsumos} <Fecha iso={v.otorgado_en} fin="." /> {ficha ? T.renovarFicha : T.renovarInsumos}{' '}
        <Fecha iso={v.revision_vence_en} fin="." />
      </>
    )
  } else if (v.estado === 'retirada') {
    Icono = ShieldOff
    frase = (
      <>
        {T.retiradaEl} <Fecha iso={v.revocado_en} fin="." />
        {/* El dominio siempre entrega `borrado_en` con `retirada`. Si no llega, solo la primera oración. */}
        {v.borrado_en && !pedidos && (
          <>
            {' '}
            {editor ? T.siNoVuelves : T.siNadieVuelve} <Fecha iso={v.borrado_en} fin="." />
          </>
        )}
      </>
    )
  } else if (v.estado === 'borrada') {
    Icono = ShieldOff
    frase = (
      <>
        {T.retiradaEl} <Fecha iso={v.revocado_en} fin="." /> {T.seBorro} <Fecha iso={v.borrado_en} fin="." />
      </>
    )
  } else frase = pedidos ? P.sinAutorizar : T.sinAutorizar
  return (
    <p className="flex gap-2 angosto:block text-base">
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
  conDireccion = false,
  onVerDireccion,
}: {
  vista: AutorizacionVista
  pila: string
  personaId: string
  editor: boolean
  aviso: AvisoBloque | null
  onRetirar: () => void
  onVolver: () => void
  conDireccion?: boolean
  onVerDireccion?: () => void
}) {
  const clave = claveDe(personaId, v.finalidad)
  const ficha = v.finalidad === 'plan_cuidado'
  const pedidos = v.finalidad === 'despacho'
  const titulo = ficha ? T.tituloFicha : pedidos ? P.titulo : T.tituloInsumos
  const conBorde = autorizada(v) ? 'bg-hoja ring-1 ring-linea' : 'bg-papel border-2 border-dashed border-borde'
  return (
    <section aria-labelledby={`bloque-${clave}`} className={`flex min-w-0 flex-col gap-3 rounded-xl px-4 angosto:px-2 py-4 ${conBorde}`}>
      <h3 id={`bloque-${clave}`} className="text-lg font-bold break-words">
        {titulo}
      </h3>
      {aviso && (
        <Nota id={`aviso-${clave}`} tono={aviso.tono} rol="status" enfocable>
          {aviso.texto}
        </Nota>
      )}
      <EstadoBloque v={v} editor={editor} />
      {editor && autorizada(v) && (
        <Boton id={`retirar-${clave}`} variante="peligro" className="self-start" aria-label={ficha ? T.retirarFichaDe(pila) : pedidos ? P.retirarDe(pila) : T.retirarInsumosDe(pila)} onClick={onRetirar}>
          {T.retirar}
        </Boton>
      )}
      {editor && retirada(v) && (
        <Boton id={`volver-${clave}`} variante="secundario" className="self-start" aria-label={ficha ? T.volverFichaDe(pila) : pedidos ? P.volverDe(pila) : T.volverInsumosDe(pila)} onClick={onVolver}>
          {T.volverAAutorizar}
        </Boton>
      )}
      {/* 12.1 (O12, C8): con una dirección guardada, para verla o vaciarla aunque se haya retirado el permiso. */}
      {editor && pedidos && conDireccion && v.estado !== 'sin_autorizar' && (
        <Boton variante="texto" className="self-start" aria-label={P.verDireccionDe(pila)} onClick={onVerDireccion}>
          {P.verDireccion}
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
  const confirmar = useRef<HTMLButtonElement>(null)
  const uid = useId()
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState(false)
  // La petición ya salió: «No retirar» y Esc no la cancelan (4.4).
  const enCurso = useRef(false)
  const pila = nombrePilaDe(datos.persona)
  const [vFicha, vInsumos] = datos.vistas
  const ficha = finalidad === 'plan_cuidado'
  const pedidos = finalidad === 'despacho'

  useEffect(() => {
    const d = ref.current
    if (d && !d.open) d.showModal()
    // 4.4: el foco en el título, para que la pregunta se lea y se vea primero.
    titulo.current?.focus()
  }, [])

  /** Cerrar a propósito: primero se marca que ya no hay petición en curso (ver `onClose`). */
  const cerrar = () => {
    enCurso.current = false
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
  const puntos: { texto: string; fuerte?: boolean }[] = pedidos
    ? P.puntos(pila)
    : ficha
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
      // 4.4 (revisión del 07-11): Chrome deja anular solo un `cancel` por cada toque, y un segundo
      // Esc cierra el diálogo igual. Con la petición en curso se vuelve a abrir y el foco vuelve al
      // botón: si no, un error de red quedaría en un diálogo cerrado.
      onClose={() => {
        if (!enCurso.current || !ref.current || ref.current.open) return
        ref.current.showModal()
        confirmar.current?.focus()
      }}
      className="m-auto w-[calc(100%-2rem)] angosto:w-[calc(100%-1rem)] max-w-lg max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-2xl bg-hoja p-6 angosto:px-2 angosto:py-4 text-tinta backdrop:bg-tinta/40"
    >
      <div className="flex flex-col gap-4">
        <h2 ref={titulo} id={`${uid}-t`} tabIndex={-1} className="text-xl font-bold break-words outline-none">
          {ficha ? T.preguntaFicha(pila) : pedidos ? P.pregunta(pila) : T.preguntaInsumos(pila)}
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
          <Boton ref={confirmar} variante="peligroPrincipal" ocupado={ocupado} textoOcupado={T.retirando} onClick={() => void retirar()}>
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

// ---------------------------------------------------------------- MATU-72: borrar sus datos

/**
 * 2.3: al final de la sección de la persona, detrás de una línea, sin fondo ni anillo. Se ve en todo
 * estado de los permisos. A1: el botón sin `aria-label` (su nombre es el texto visible). A2: pagador y
 * observador ven solo el título y quién puede.
 */
function BloqueBorrar({ persona, editor, onBorrar }: { persona: PersonaListada; editor: boolean; onBorrar: () => void }) {
  const pila = nombrePilaDe(persona)
  const id = `borrar-titulo-${persona.id}`
  return (
    <section aria-labelledby={id} className="mt-4 flex flex-col gap-3 border-t border-linea pt-6">
      <h3 id={id} className="text-lg font-bold break-words">
        {B.titulo}
      </h3>
      {editor ? (
        <>
          <p className="max-w-prose text-base">{B.explicacion(pila)}</p>
          <Boton id={`borrar-${persona.id}`} variante="peligro" className="self-start" onClick={onBorrar}>
            {B.boton(pila)}
          </Boton>
        </>
      ) : (
        <p className="text-base text-tenue">{B.quienPuede(pila)}</p>
      )}
    </section>
  )
}

/**
 * 3.5: «Hoy abren {n}.» con la ficha vigente y el conteo de Grupo familiar; sin conteo se omite. Por
 * renovar, retirada o borrada, ningún enlace abre (en pausa o ya cortados). Sin autorizar (R3, 1.1)
 * nunca se pudo crear un enlace: el dato se conoce y es cero. Solo se omite cuando no se sabe: falta
 * el conteo o la vista de la ficha.
 */
function hoyAbrenAlBorrar(d: DatosPersona): string {
  const estado = d.vistas.find((v) => v.finalidad === 'plan_cuidado')?.estado
  if (estado === undefined) return ''
  if (estado === 'vigente') return d.enlaces === null ? '' : T.hoyAbren(d.enlaces)
  return T.hoyAbren(0)
}

function DialogoBorrar({
  datos,
  onCancelar,
  onBorrada,
  onYaBorrada,
  onNoEncontrado,
}: {
  datos: DatosPersona
  onCancelar: () => void
  onBorrada: (r: { enlaces_cortados: number }) => void
  onYaBorrada: () => void
  onNoEncontrado: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const cuerpo = useRef<HTMLDivElement>(null)
  const confirmar = useRef<HTMLButtonElement>(null)
  const noBorrar = useRef<HTMLButtonElement>(null)
  const regionError = useRef<HTMLDivElement>(null)
  const uid = useId()
  // 3.6: sin marcar al abrir, siempre; no se recuerda entre aperturas (el diálogo se monta de nuevo).
  const [entiendo, setEntiendo] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState(false)
  // La petición ya salió: «No borrar», la casilla y Esc no hacen nada (3.6, MATU-44 4.4).
  const enCurso = useRef(false)
  const pila = nombrePilaDe(datos.persona)

  useEffect(() => {
    const d = ref.current
    if (d && !d.open) d.showModal()
    // 3.3: el foco en «No borrar», sin desplazar: lo primero que se ve es la pregunta.
    noBorrar.current?.focus({ preventScroll: true })
    if (d) d.scrollTop = 0
    if (cuerpo.current) cuerpo.current.scrollTop = 0
  }, [])

  // P3 (revisión del 08-11): en modo angosto el pie se desplaza con el cuerpo, y el error puede quedar
  // cortado. Se trae entero a la vista; el foco sigue en «Borrar todo». Fuera de ese modo el pie es
  // fijo y el error ya se ve: con `nearest` no se mueve nada.
  useEffect(() => {
    if (error) regionError.current?.scrollIntoView?.({ block: 'nearest' })
  }, [error])

  const cerrar = () => {
    enCurso.current = false
    if (ref.current?.open) ref.current.close()
  }

  const borrar = async () => {
    if (enCurso.current || !entiendo) return
    enCurso.current = true
    setOcupado(true)
    setError(false)
    try {
      const r = await borrarPersona(datos.persona.id)
      cerrar()
      onBorrada(r)
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 409 && esTipo(f.tipo, 'ya-borrada')) {
        cerrar()
        return onYaBorrada()
      }
      if (f.status === 404) {
        cerrar()
        return onNoEncontrado()
      }
      // Red o 5xx: el borrado es una sola transacción, todo sigue como estaba. La casilla sigue marcada.
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

  const parrafos: { texto: string; tono?: 'fuerte' | 'tenue' }[] = [
    { texto: B.noSeDeshace, tono: 'fuerte' },
    { texto: B.borramosFicha },
    { texto: [B.seCortan, hoyAbrenAlBorrar(datos), B.fichaAbierta].filter(Boolean).join(' ') },
    { texto: B.saleDeMatu(pila) },
    { texto: B.guardamos, tono: 'tenue' },
    { texto: B.respaldo, tono: 'tenue' },
    { texto: B.lista, tono: 'tenue' },
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
      // MATU-44 4.4: un segundo Esc cierra el diálogo aunque el primero se anuló. Con la petición en
      // curso se vuelve a abrir y el foco vuelve al botón.
      onClose={() => {
        if (!enCurso.current || !ref.current || ref.current.open) return
        ref.current.showModal()
        confirmar.current?.focus()
      }}
      className="m-auto w-[calc(100%-2rem)] angosto:w-[calc(100%-1rem)] max-w-lg max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-2xl bg-hoja text-tinta backdrop:bg-tinta/40"
    >
      {/* 3.1: el cuerpo se desplaza y el pie queda fijo. El `flex` va en este envoltorio y no en el
          `<dialog>`: en el diálogo pisaría el `display: none` de cerrado. En modo angosto el pie deja
          de ser fijo y se desplaza todo junto, en la caja. */}
      <div className="flex max-h-[calc(100dvh-2rem)] flex-col angosto:block angosto:max-h-none">
        <div ref={cuerpo} className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto angosto:overflow-visible px-6 pt-6 pb-4 angosto:px-2 angosto:pt-4">
          <h2 id={`${uid}-t`} tabIndex={-1} className="text-xl font-bold break-words outline-none">
            {B.pregunta(pila)}
          </h2>
          <div id={`${uid}-d`} className="flex max-w-prose flex-col gap-3 text-base leading-relaxed">
            {parrafos.map((p) => (
              <p key={p.texto} className={p.tono === 'fuerte' ? 'font-bold' : p.tono === 'tenue' ? 'text-tenue' : undefined}>
                {p.texto}
              </p>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-3 border-t border-linea px-6 pt-4 pb-6 angosto:px-2 angosto:pb-4">
          {/* 3.1: el trato de la casilla del aviso del cuidador de hecho, con la medida única de MATU-68
              (`size-6`; en angosto va con la primera línea). */}
          <label className="flex min-h-12 cursor-pointer items-center angosto:items-start gap-3 font-bold">
            <input
              type="checkbox"
              checked={entiendo}
              aria-disabled={ocupado || undefined}
              onChange={(e) => {
                if (!enCurso.current) setEntiendo(e.target.checked)
              }}
              className="size-6 shrink-0 accent-turquesa angosto:mt-0.5"
            />
            {B.casilla}
          </label>
          {/* Con `showModal` lo de fuera queda inerte: el error usa su propia región, montada vacía. */}
          <div ref={regionError} role="alert" className="empty:hidden">
            {error && <MensajeError>{B.errBorrar}</MensajeError>}
          </div>
          <Acciones>
            <Boton
              ref={confirmar}
              variante="peligroPrincipal"
              aria-disabled={!entiendo || undefined}
              ocupado={ocupado}
              textoOcupado={B.borrando}
              onClick={() => void borrar()}
            >
              {B.borrarTodo}
            </Boton>
            <button
              ref={noBorrar}
              type="button"
              aria-disabled={ocupado || undefined}
              onClick={cancelar}
              className="inline-flex min-h-12 items-center px-2 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
            >
              {B.noBorrar}
            </button>
          </Acciones>
        </div>
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

/** Mientras llega la vista (5.1): «Cargando…» o el error al cargar, bajo el título de la pantalla. */
function EsperaVista({ falla, pedir }: { falla: 'red' | 'no-encontrado' | null; pedir: () => void }) {
  return falla === 'red' ? <ErrorAlCargar reintentar={pedir} /> : <Cargando />
}

function VolverAGrupo() {
  return <Volver onClick={() => navegar('/grupo')}>{T.volverAGrupo}</Volver>
}

/** El aviso de 5.3 tiene que estar en memoria antes de que se monte `/grupo`. */
function volverConAviso(cambios: Parameters<ReturnType<typeof useFamilia>['fijar']>[0], fijar: ReturnType<typeof useFamilia>['fijar']) {
  flushSync(() => fijar(cambios))
  navegar('/grupo')
}

/**
 * 5.1: el cuerpo de la autorización del alta, sin su marco, en el esqueleto de la app. Mientras
 * llega la vista, el `h1` ya es el de esta pantalla y es el mismo elemento al terminar: así el foco
 * de la regla de ruta no se pierde (revisión del 07-11).
 */
export function AutorizarFicha() {
  const { persona, personaId, fijar } = useFamilia()
  const { vista, falla: fallaVista, pedir } = useVistaAReautorizar('plan_cuidado')
  const d = useDeclaracionFicha()
  const [falla, setFalla] = useState<'422' | 'red' | 'no-encontrado' | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const pila = persona ? nombrePilaDe(persona) : ''

  if (fallaVista === 'no-encontrado' || falla === 'no-encontrado') return <SinAcceso />
  const lista = vista && retirada(vista) ? vista : null
  const enBlanco = lista ? seBorro(lista) : false

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
        {lista && (
          <>
            <p className="max-w-prose text-base text-tenue">{AUTORIZACION.bajada(pila)}</p>
            <p className="max-w-prose text-base">{enBlanco ? <ConFecha partes={T.fichaSeBorro} iso={lista.borrado_en} /> : T.fichaVuelve}</p>
          </>
        )}
      </div>
      {!lista ? (
        <EsperaVista falla={fallaVista} pedir={() => void pedir()} />
      ) : (
        <>
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
        </>
      )}
    </div>
  )
}

/** 5.2: el permiso de los insumos de MATU-36, sin cambiarlo, con la vuelta y la frase de estado. */
export function AutorizarInsumos() {
  const { persona, personaId, fijar } = useFamilia()
  const { vista, falla, pedir } = useVistaAReautorizar('consumo')
  const [noEncontrado, setNoEncontrado] = useState(false)
  const pila = persona ? nombrePilaDe(persona) : ''

  if (noEncontrado || falla === 'no-encontrado')
    return (
      <Pagina titulo={T.titulo}>
        <Nota tono="rocio" icono={<Lock aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
          {GENERAL.noEncontrado}
        </Nota>
      </Pagina>
    )
  const lista = vista && retirada(vista) ? vista : null
  const enBlanco = lista ? seBorro(lista) : false

  return (
    <Permiso
      pila={pila}
      personaId={personaId}
      antes={<VolverAGrupo />}
      frase={lista ? <p className="max-w-prose text-base"><ConFecha partes={enBlanco ? T.insumosSeBorro : T.insumosVuelve} iso={lista.borrado_en} /></p> : undefined}
      cargando={lista ? undefined : <EsperaVista falla={falla} pedir={() => void pedir()} />}
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

/** MATU-61 (12.4): el permiso de los pedidos de 4.1, con «Volver a Grupo familiar» y sin frase de estado. */
export function AutorizarPedidosDesdeGrupo() {
  const { persona, personaId, fijar } = useFamilia()
  const { vista, falla, pedir } = useVistaAReautorizar('despacho')
  const [noEncontrado, setNoEncontrado] = useState(false)
  const pila = persona ? nombrePilaDe(persona) : ''

  if (noEncontrado || falla === 'no-encontrado')
    return (
      <Pagina titulo={T.titulo}>
        <Nota tono="rocio" icono={<Lock aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />}>
          {GENERAL.noEncontrado}
        </Nota>
      </Pagina>
    )
  const lista = vista && retirada(vista) ? vista : null

  return (
    <Permiso
      finalidad="despacho"
      pila={pila}
      personaId={personaId}
      antes={<VolverAGrupo />}
      cargando={lista ? undefined : <EsperaVista falla={falla} pedir={() => void pedir()} />}
      onListo={(yaVigente) => {
        volverConAviso({ reautorizar: null, aviso: yaVigente ? { titulo: T.yaAutorizada, tono: 'rocio' } : { titulo: P.autorizada(pila), tono: 'ok' } }, fijar)
      }}
      onNoEncontrado={() => setNoEncontrado(true)}
    />
  )
}

// Incidencias (especificación MATU-81, sección 9): lo que el equipo anota de un pedido y cómo se
// resolvió, sabiendo que la familia lo puede leer (C11 y D-81-4). La nota no va en la fila (la lista
// no expone texto libre). Cambiar una incidencia usa `If-Match`: un 412 vuelve a pedirla y conserva
// lo escrito. Ningún texto de la nota va a un anuncio, la URL ni el almacenamiento.
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { TriangleAlert } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import {
  crearIncidencia,
  editarIncidencia,
  esProblema,
  etagIncidencia,
  listarIncidencias,
  verIncidencia,
  type EstadoIncidencia,
  type IncidenciaVista,
  type TipoIncidencia,
} from '../compartido/api/operacion'
import { anunciar } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { useDemora } from '../compartido/useDemora'
import { navegar } from '../familia/ruteo'
import { Acciones, GrupoOpciones, MensajeError, Titulo, Volver } from '../familia/ui'
import { AreaTexto, CUADRO_DETALLE, CUADRO_VACIO, enChile, EtiquetaIncidencia, FilaCola, GRILLA, useAlDia, useFocoAlMontar } from './comun'
import { useOperacion } from './estado'
import { AvisoPrivacidad, RotuloPiloto } from './Marco'
import { INCIDENCIAS as T, MARCO, PEDIDOS, TIPO_INCIDENCIA } from './textos'

const CHIPS: { valor: EstadoIncidencia; texto: string }[] = [
  { valor: 'abierta', texto: T.abiertas },
  { valor: 'en_gestion', texto: T.enGestion },
  { valor: 'resuelta', texto: T.resueltas },
]
const TIPOS = Object.keys(TIPO_INCIDENCIA) as TipoIncidencia[]
const ID_NOTA = 'nota-de-la-incidencia'

/** 9.3 (C11): la ayuda va antes del campo, en `atenta`, y en su `aria-describedby`. */
function AyudaNota({ id }: { id: string }) {
  return (
    <Nota id={id} tono="atenta" borde icono={<TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
      {T.ayuda}
    </Nota>
  )
}

export function PantallaIncidencias() {
  const { incidenciaId, fijar, fallo } = useOperacion()
  const [estado, setEstado] = useState<EstadoIncidencia>('abierta')
  const [lista, setLista] = useState<IncidenciaVista[] | null>(null)
  const [error, setError] = useState(false)
  const pedirFoco = useFocoAlMontar()
  const verCargando = useDemora(1000)

  const traer = useCallback(async () => {
    try {
      setLista(await listarIncidencias(estado))
      setError(false)
    } catch (x) {
      if (!fallo(x, true)) setError(true)
    }
  }, [estado, fallo])

  useEffect(() => {
    void traer()
  }, [traer])
  useAlDia(() => void traer())

  const t = (iso: string) => new Date(iso).getTime()
  // 9.1: la más antigua primero; en «Resueltas», la más reciente.
  const ordenadas = [...(lista ?? [])].sort((a, b) => (estado === 'resuelta' ? t(b.creada_en) - t(a.creada_en) : t(a.creada_en) - t(b.creada_en)))
  const chip = CHIPS.find((c) => c.valor === estado)!.texto

  return (
    <div className="flex flex-col gap-8">
      <div className={`${incidenciaId ? 'hidden @3xl/main:flex' : 'flex'} flex-col gap-2`}>
        {incidenciaId ? <p className="titular text-3xl angosto:text-2xl">{T.titulo}</p> : <Titulo className="text-3xl">{T.titulo}</Titulo>}
        <AvisoPrivacidad />
      </div>
      <div className={GRILLA}>
        <div className={`${incidenciaId ? 'hidden @3xl/main:flex' : 'flex'} min-w-0 flex-col gap-5`} aria-busy={lista === null || undefined}>
          <GrupoOpciones forma="chips" leyenda={PEDIDOS.mostrar} nombre="estado-incidencias" opciones={CHIPS} valor={estado} onCambio={setEstado} />
          {error && (
            <div className="flex flex-col items-start gap-3">
              <Nota tono="pronto" rol="alert">
                {T.errorAlTraer}
              </Nota>
              <Boton variante="secundario" onClick={() => void traer()}>
                {MARCO.volverAIntentar}
              </Boton>
            </div>
          )}
          {lista === null && !error && <p className="text-tenue">{verCargando ? T.cargando : ''}</p>}
          {lista && ordenadas.length === 0 && <p className="text-xl font-bold">{estado === 'abierta' ? T.vacioAbiertas : T.vacio(chip)}</p>}
          {ordenadas.length > 0 && (
            <ul className="flex flex-col gap-2">
              {ordenadas.map((i) => {
                const { dia, hora } = enChile(i.creada_en)
                const ref = i.referencia ?? ''
                return (
                  <li key={i.id}>
                    <FilaCola
                      elegida={i.id === incidenciaId}
                      nombre={[TIPO_INCIDENCIA[i.tipo], CHIPS.find((c) => c.valor === i.estado)?.texto, T.pedido(ref), T.anotadaEl(dia, hora)].filter(Boolean).join(', ')}
                      onElegir={() => fijar({ incidenciaId: i.id })}
                      primera={
                        <>
                          <span className="min-w-0">{TIPO_INCIDENCIA[i.tipo]}</span>
                          <EtiquetaIncidencia estado={i.estado} />
                        </>
                      }
                    >
                      <span>
                        {T.pedido('').trimEnd()} <span className="digitos break-words">{ref}</span>
                      </span>
                      <span className="cifras whitespace-normal text-tenue">{T.anotadaEl(dia, hora)}</span>
                    </FilaCola>
                  </li>
                )
              })}
            </ul>
          )}
          <RotuloPiloto />
        </div>
        {incidenciaId ? (
          <section className={CUADRO_DETALLE}>
            <DetalleIncidencia
              key={incidenciaId}
              id={incidenciaId}
              onVolver={() => {
                fijar({ incidenciaId: null })
                pedirFoco('titulo-pagina')
              }}
              onCambio={() => void traer()}
            />
          </section>
        ) : (
          <div className={CUADRO_VACIO}>
            <p className="text-lg text-tenue">{T.elige}</p>
          </div>
        )}
      </div>
    </div>
  )
}

function DetalleIncidencia({ id, onVolver, onCambio }: { id: string; onVolver: () => void; onCambio: () => void }) {
  const { fallo, fijar } = useOperacion()
  const [i, setI] = useState<IncidenciaVista | null>(null)
  const [noEsta, setNoEsta] = useState(false)
  const [errorCarga, setErrorCarga] = useState(false)
  const etag = useRef<string>('')
  const [resolviendo, setResolviendo] = useState(false)
  const [texto, setTexto] = useState('')
  const [sinTexto, setSinTexto] = useState(false)
  const [ocupado, setOcupado] = useState<'gestion' | 'resolver' | null>(null)
  const [nota, setNota] = useState<{ tono: 'ok' | 'atenta' | 'pronto'; texto: string; n: number } | null>(null)
  const contador = useRef(0)
  const pedirFoco = useFocoAlMontar()
  const verCargando = useDemora(1000)

  const primera = useRef(true)
  const cargar = useCallback(async (): Promise<IncidenciaVista | null> => {
    try {
      const r = await verIncidencia(id)
      etag.current = r.etag
      setI(r.incidencia)
      setErrorCarga(false)
      // 2.1: elegir también es llegar: el foco va al `h1` del detalle cuando termina de cargar.
      if (primera.current) {
        primera.current = false
        pedirFoco('titulo-pagina')
      }
      return r.incidencia
    } catch (x) {
      if (!fallo(x)) {
        if (leerFallo(x).status === 404) setNoEsta(true)
        else setErrorCarga(true)
      }
      return null
    }
  }, [id, fallo, pedirFoco])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const avisar = (tono: 'ok' | 'atenta' | 'pronto', t: string) => {
    setNota({ tono, texto: t, n: ++contador.current })
    pedirFoco(ID_NOTA)
  }

  /** 9.3: 412 (otra persona la cambió) o 409 (ya estaba resuelta): se vuelve a pedir y se conserva lo escrito. */
  const conflicto = async () => {
    const nueva = await cargar()
    onCambio()
    if (nueva?.estado === 'resuelta') {
      setResolviendo(false)
      setTexto('')
      avisar('atenta', `${T.otraPersonaSinTexto} ${T.yaEstabaResuelta}`)
    } else avisar('atenta', T.otraPersona)
  }

  const pasarAGestion = async () => {
    if (!i || ocupado) return
    setOcupado('gestion')
    try {
      const r = await editarIncidencia(i.id, { estado: 'en_gestion', asignacion: 'a_mi' }, etag.current || etagIncidencia(i))
      etag.current = r.etag
      setI(r.incidencia)
      onCambio()
      anunciar(T.quedoEnGestion, 'status')
      pedirFoco('incidencia-resolver')
    } catch (x) {
      if (fallo(x)) return
      const f = leerFallo(x)
      if (f.status === 412 || f.status === 409) await conflicto()
      else avisar('pronto', T.errorAlCargar)
    } finally {
      setOcupado(null)
    }
  }

  const resolver = async (e: FormEvent) => {
    e.preventDefault()
    if (!i || ocupado) return
    if (!texto.trim()) {
      setSinTexto(true)
      pedirFoco('incidencia-resolucion')
      return
    }
    setSinTexto(false)
    setOcupado('resolver')
    try {
      const r = await editarIncidencia(i.id, { estado: 'resuelta', resolucion: texto.trim() }, etag.current || etagIncidencia(i))
      etag.current = r.etag
      setI(r.incidencia)
      setResolviendo(false)
      setTexto('')
      onCambio()
      avisar('ok', T.marcasteResuelta)
    } catch (x) {
      if (fallo(x)) return
      const f = leerFallo(x)
      if (f.status === 412 || f.status === 409) await conflicto()
      else if (f.status === 422 && esProblema(f.tipo, 'falta-resolucion')) setSinTexto(true)
      else avisar('pronto', T.error)
    } finally {
      setOcupado(null)
    }
  }

  const volverATexto = <Volver onClick={onVolver}>{T.volver}</Volver>
  if (noEsta || errorCarga || !i)
    return (
      <div className="flex flex-col items-start gap-4">
        <div className="@3xl/main:hidden">{volverATexto}</div>
        {errorCarga ? (
          <>
            <Nota tono="pronto" rol="alert">
              {T.errorAlCargar}
            </Nota>
            <Boton variante="secundario" onClick={() => void cargar()}>
              {MARCO.volverAIntentar}
            </Boton>
          </>
        ) : noEsta ? null : (
          <p className="text-tenue">{verCargando ? T.cargando : ''}</p>
        )}
      </div>
    )

  const anotada = enChile(i.creada_en)
  const resuelta = i.resuelta_en ? enChile(i.resuelta_en) : null
  const ref = i.referencia ?? ''

  return (
    <div className="flex flex-col gap-6">
      <div className="@3xl/main:hidden">{volverATexto}</div>
      <div className="flex flex-col items-start gap-2">
        <Titulo className="text-3xl">{TIPO_INCIDENCIA[i.tipo]}</Titulo>
        <EtiquetaIncidencia estado={i.estado} />
        <p className="flex flex-wrap items-center gap-x-2">
          <span>
            {T.pedido('').trimEnd()} <span className="digitos break-words">{ref}</span>
          </span>
          <span aria-hidden>·</span>
          <Boton
            variante="texto"
            onClick={() => {
              fijar({ pedidoId: i.pedido_id, origen: '/operacion' })
              navegar('/operacion/pedido')
            }}
          >
            {T.verPedido}
          </Boton>
        </p>
        <p className="cifras text-base whitespace-normal text-tenue">{T.anotadaEl(anotada.fecha, anotada.hora)}</p>
        {i.asignada_a_mi && <p className="text-base">{T.laTienesTu}</p>}
      </div>
      {nota && (
        <div key={nota.n}>
          <Nota id={ID_NOTA} enfocable tono={nota.tono} rol={nota.tono === 'pronto' ? 'alert' : 'status'}>
            {nota.texto}
          </Nota>
        </div>
      )}
      <section aria-labelledby="incidencia-nota" className="flex flex-col gap-1">
        <h2 id="incidencia-nota" className="text-lg font-bold">
          {T.nota}
        </h2>
        <p className="max-w-prose whitespace-pre-line break-words">{i.descripcion}</p>
      </section>
      {i.estado === 'resuelta' ? (
        <section aria-labelledby="incidencia-resuelta" className="flex flex-col gap-1">
          <h2 id="incidencia-resuelta" className="text-lg font-bold">
            {T.comoSeResolvio}
          </h2>
          {i.resolucion && <p className="max-w-prose whitespace-pre-line break-words">{i.resolucion}</p>}
          {resuelta && <p className="cifras text-base whitespace-normal text-tenue">{T.resueltaEl(resuelta.fecha, resuelta.hora)}</p>}
        </section>
      ) : resolviendo ? (
        <form noValidate onSubmit={(e) => void resolver(e)} className="flex flex-col gap-3">
          <AyudaNota id="ayuda-resolucion" />
          <div id="incidencia-resolucion">
            <AreaTexto
              id="incidencia-resolucion-texto"
              etiqueta={T.comoSeResolvio}
              valor={texto}
              onCambio={(v) => {
                setTexto(v)
                setSinTexto(false)
              }}
              describe={sinTexto ? 'ayuda-resolucion resolucion-error' : 'ayuda-resolucion'}
              error={sinTexto}
              contador={T.contador}
            />
          </div>
          {sinTexto && <MensajeError id="resolucion-error">{T.sinResolucion}</MensajeError>}
          <Acciones>
            <Boton type="submit" ocupado={ocupado === 'resolver'} textoOcupado={T.guardando}>
              {T.marcarResuelta}
            </Boton>
            <Boton
              variante="texto"
              onClick={() => {
                setResolviendo(false)
                setSinTexto(false)
                pedirFoco('incidencia-resolver')
              }}
            >
              {T.cancelar}
            </Boton>
          </Acciones>
        </form>
      ) : (
        <Acciones>
          <Boton
            id="incidencia-resolver"
            onClick={() => {
              setResolviendo(true)
              pedirFoco('incidencia-resolucion', 'textarea')
            }}
          >
            {T.resolver}
          </Boton>
          {i.estado === 'abierta' && (
            <Boton variante="secundario" ocupado={ocupado === 'gestion'} textoOcupado={T.guardando} onClick={() => void pasarAGestion()}>
              {T.pasarAGestion}
            </Boton>
          )}
        </Acciones>
      )}
      <div className="@3xl/main:hidden">
        <RotuloPiloto />
      </div>
    </div>
  )
}

// ----------------------------------------------------------------- 9.3 anotar, en el pedido

export function AnotarIncidencia({
  pedidoId,
  tipoInicial,
  onListo,
  onCancelar,
}: {
  pedidoId: string
  tipoInicial: TipoIncidencia | null
  onListo: (i: IncidenciaVista) => void
  onCancelar: () => void
}) {
  const { fallo } = useOperacion()
  const [tipo, setTipo] = useState<TipoIncidencia | null>(tipoInicial)
  const [texto, setTexto] = useState('')
  const [errores, setErrores] = useState<{ tipo?: boolean; texto?: 'vacia' | 'larga' }>({})
  const [falla, setFalla] = useState<{ texto: string; n: number } | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const contador = useRef(0)
  const pedirFoco = useFocoAlMontar()

  // 9.3: al abrir, el foco va a la primera opción de «¿Qué pasó?», o a la ya elegida si viene del pago (7).
  useEffect(() => {
    pedirFoco('anotar-tipo', tipoInicial ? 'input[type="radio"]:checked' : 'input[type="radio"]')
  }, [pedirFoco, tipoInicial])

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado) return
    const err = { tipo: !tipo, texto: texto.trim() ? undefined : ('vacia' as const) }
    setErrores(err)
    setFalla(null)
    if (err.tipo) return pedirFoco('anotar-tipo', 'input[type="radio"]')
    if (err.texto) return pedirFoco('anotar-nota', 'textarea')
    setOcupado(true)
    try {
      onListo(await crearIncidencia(pedidoId, tipo!, texto.trim()))
    } catch (x) {
      if (fallo(x)) return
      const f = leerFallo(x)
      if (f.status === 422 && f.errores.some((c) => c.campo === 'descripcion')) {
        setErrores({ texto: 'larga' })
        pedirFoco('anotar-nota', 'textarea')
      } else if (f.status === 404 || f.status === 409 || f.status === 422) setFalla({ texto: T.soloPagados, n: ++contador.current })
      else setFalla({ texto: T.error, n: ++contador.current })
    } finally {
      setOcupado(false)
    }
  }

  const describe = ['ayuda-anotar', errores.texto ? 'anotar-nota-error' : ''].filter(Boolean).join(' ')
  return (
    <form noValidate onSubmit={(e) => void enviar(e)} aria-labelledby="anotar-titulo" className="flex flex-col gap-4 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea">
      <h3 id="anotar-titulo" className="font-bold">
        {T.anotarTitulo}
      </h3>
      <GrupoOpciones
        id="anotar-tipo"
        leyenda={T.quePaso}
        nombre={`tipo-${pedidoId}`}
        opciones={TIPOS.map((t) => ({ valor: t, texto: TIPO_INCIDENCIA[t] }))}
        valor={tipo}
        onCambio={(v) => {
          setTipo(v)
          setErrores((x) => ({ ...x, tipo: false }))
        }}
        error={errores.tipo ? T.eligeQuePaso : null}
      />
      <AyudaNota id="ayuda-anotar" />
      <div id="anotar-nota">
        <AreaTexto
          id="anotar-nota-texto"
          etiqueta={T.nota}
          valor={texto}
          onCambio={(v) => {
            setTexto(v)
            setErrores((x) => ({ ...x, texto: undefined }))
          }}
          describe={describe}
          error={!!errores.texto}
          contador={T.contador}
        />
      </div>
      {errores.texto && <MensajeError id="anotar-nota-error">{errores.texto === 'vacia' ? T.notaVacia : T.muyLarga}</MensajeError>}
      {falla && (
        <div key={falla.n}>
          <Nota tono={falla.texto === T.soloPagados ? 'atenta' : 'pronto'} rol="alert">
            {falla.texto}
          </Nota>
        </div>
      )}
      <Acciones>
        <Boton type="submit" ocupado={ocupado} textoOcupado={T.guardando}>
          {T.guardar}
        </Boton>
        <Boton variante="texto" onClick={onCancelar}>
          {T.cancelar}
        </Boton>
      </Acciones>
    </form>
  )
}

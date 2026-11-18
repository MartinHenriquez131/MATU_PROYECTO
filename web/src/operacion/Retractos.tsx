// Retractos (especificación MATU-81, sección 8): los chips «Por resolver», «Devueltos» y «Sin devolución»
// (decisión 466); los por resolver con el plazo más cercano primero, y el elegido con sus productos y el
// monto. «Devolver» y «No devolver» piden confirmar y dicen el monto (C22 y C24); el monto es el de la API. El retracto elegido vive en memoria.
// También el formulario del retracto que llegó por correo (8.5): el correo va solo en el cuerpo, se
// borra de la memoria y del campo con cualquier respuesta del servidor, y nunca se lista a nadie (C25).
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Ban, Circle, Mail, Undo2 } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import {
  esProblema,
  extensionDe,
  listarRetractos,
  registrarRetractoPorCorreo,
  resolverRetracto,
  verRetracto,
  type EstadoRetracto,
  type MotivoRechazo,
  type PedidoDetalle,
  type RetractoOperacion,
} from '../compartido/api/operacion'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { useDemora } from '../compartido/useDemora'
import { DialogoConfirmar } from '../familia/DialogoConfirmar'
import { navegar } from '../familia/ruteo'
import { Acciones, CampoTexto, GrupoOpciones, MensajeError, Stepper, Titulo, Volver } from '../familia/ui'
import { Atencion, CUADRO_DETALLE, CUADRO_VACIO, enChile, EtiquetaCon, FilaCola, GRILLA, Monto, pesos, useAhora, useAlDia, useFocoAlMontar } from './comun'
import { useOperacion } from './estado'
import { AvisoPrivacidad, RotuloPiloto } from './Marco'
import { ESPACIO_DURO, MARCO, PEDIDOS, RETRACTOS as T } from './textos'

const DIA = 86_400_000
const ID_NOTA = 'nota-del-retracto'
/** 8.2: los chips, cada uno un `estado` de la consulta. */
const CHIPS: { valor: EstadoRetracto; texto: string }[] = [
  { valor: 'solicitado', texto: T.porResolver },
  { valor: 'devuelto', texto: T.devueltos },
  { valor: 'rechazado', texto: T.sinDevolucion },
]

/** 8.2: el plazo de la fila, en `atenta` con 2 días o menos, o vencido. */
export function plazoDe(r: RetractoOperacion, ahora: Date): { texto: string; atenta: boolean } | null {
  if (r.estado !== 'solicitado') return null
  const hasta = new Date(r.plazo_hasta)
  const { fecha } = enChile(r.plazo_hasta)
  if (hasta.getTime() < ahora.getTime()) return { texto: T.vencio(fecha), atenta: true }
  return { texto: T.responderAntes(fecha), atenta: hasta.getTime() - ahora.getTime() <= 2 * DIA }
}

export function EtiquetaRetracto({ estado }: { estado: RetractoOperacion['estado'] }) {
  if (estado === 'devuelto') return <EtiquetaCon Icono={Undo2} tono="ok" texto={T.devuelto} />
  if (estado === 'rechazado') return <EtiquetaCon Icono={Ban} tono="neutro" texto={T.sinDevolucion} />
  return <EtiquetaCon Icono={Circle} tono="atenta" texto={T.porResolver} />
}

export function PantallaRetractos() {
  const { retractoId, fijar, fallo } = useOperacion()
  const [estado, setEstado] = useState<EstadoRetracto>('solicitado')
  const [lista, setLista] = useState<RetractoOperacion[] | null>(null)
  const [hayMas, setHayMas] = useState(false)
  const [error, setError] = useState(false)
  const { ahora, fijarFecha } = useAhora()
  const pedirFoco = useFocoAlMontar()
  const verCargando = useDemora(1000)

  const traer = useCallback(async () => {
    try {
      const r = await listarRetractos([estado])
      fijarFecha(r.fecha)
      setLista(r.retractos)
      setHayMas(r.hayMas)
      setError(false)
    } catch (x) {
      if (!fallo(x, true)) setError(true)
    }
  }, [estado, fijarFecha, fallo])

  useEffect(() => {
    void traer()
  }, [traer])
  useAlDia(() => void traer())

  // 2.1: elegir también es llegar; el detalle enfoca su `h1` cuando termina de cargar.
  const elegir = (id: string) => fijar({ retractoId: id })
  // 8.2: los por resolver, el plazo más cercano primero; los resueltos, en el orden del servidor (el más reciente).
  const ordenados = estado === 'solicitado' ? [...(lista ?? [])].sort((a, b) => new Date(a.plazo_hasta).getTime() - new Date(b.plazo_hasta).getTime()) : (lista ?? [])
  const chip = CHIPS.find((c) => c.valor === estado)!.texto

  return (
    <div className="flex flex-col gap-8">
      <div className={`${retractoId ? 'hidden @3xl/main:flex' : 'flex'} flex-col gap-2`}>
        {retractoId ? <p className="titular text-3xl angosto:text-2xl">{T.titulo}</p> : <Titulo className="text-3xl">{T.titulo}</Titulo>}
        <AvisoPrivacidad />
      </div>
      <div className={GRILLA}>
        <div className={`${retractoId ? 'hidden @3xl/main:flex' : 'flex'} min-w-0 flex-col gap-5`} aria-busy={lista === null || undefined}>
          <GrupoOpciones
            forma="chips"
            leyenda={PEDIDOS.mostrar}
            nombre="estado-retractos"
            opciones={CHIPS}
            valor={estado}
            onCambio={(v) => {
              setLista(null)
              setHayMas(false)
              setEstado(v)
            }}
          />
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
          {lista && ordenados.length === 0 && <p className="text-xl font-bold">{estado === 'solicitado' ? T.vacio : T.vacioEn(chip)}</p>}
          {ordenados.length > 0 && (
            <ul className="flex flex-col gap-2">
              {ordenados.map((r) => {
                const plazo = plazoDe(r, ahora())
                const ref = r.referencia ?? ''
                const origen = r.origen === 'correo' ? T.porCorreo : T.porLaApp
                const pedidoEl = T.pedidoEl(enChile(r.solicitado_en).dia)
                return (
                  <li key={r.id}>
                    <FilaCola
                      elegida={r.id === retractoId}
                      nombre={[T.fila(ref), pesos(r.monto), origen, pedidoEl, plazo?.texto.replace(/\.$/, '')].filter(Boolean).join(', ')}
                      onElegir={() => elegir(r.id)}
                      primera={
                        <span className="min-w-0">
                          {T.fila('').trimEnd()} <span className="digitos break-words">{ref}</span>
                        </span>
                      }
                    >
                      <span className="flex flex-wrap items-center gap-x-1.5">
                        <Monto n={r.monto} /> ·
                        {r.origen === 'correo' && <Mail aria-hidden className="size-5 shrink-0 text-tenue" />}
                        <span className="text-tenue">{origen}</span>
                      </span>
                      <span className="cifras whitespace-normal text-tenue">{pedidoEl}</span>
                      {plazo && (plazo.atenta ? <Atencion>{plazo.texto}</Atencion> : <span className="cifras whitespace-normal text-tenue">{plazo.texto}</span>)}
                    </FilaCola>
                  </li>
                )
              })}
            </ul>
          )}
          {lista && hayMas && <p className="max-w-prose text-base text-tenue">{T.hayMas}</p>}
          <RotuloPiloto />
        </div>
        {retractoId ? (
          <section className={CUADRO_DETALLE}>
            <DetalleRetracto
              key={retractoId}
              id={retractoId}
              onVolver={() => {
                fijar({ retractoId: null })
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

type Paso = { tipo: 'devolver' } | { tipo: 'rechazar'; motivo: MotivoRechazo } | null

function DetalleRetracto({ id, onVolver, onCambio }: { id: string; onVolver: () => void; onCambio: () => void }) {
  const { fallo, fijar } = useOperacion()
  const [r, setR] = useState<RetractoOperacion | null>(null)
  const [noEsta, setNoEsta] = useState(false)
  const [errorCarga, setErrorCarga] = useState(false)
  const [motivoAbierto, setMotivoAbierto] = useState(false)
  const [motivo, setMotivo] = useState<MotivoRechazo | null>(null)
  const [sinMotivo, setSinMotivo] = useState(false)
  const [paso, setPaso] = useState<Paso>(null)
  const [errorDialogo, setErrorDialogo] = useState(T.error)
  const [nota, setNota] = useState<{ tono: 'ok' | 'atenta'; texto: string; n: number } | null>(null)
  const contador = useRef(0)
  const pedirFoco = useFocoAlMontar()
  const verCargando = useDemora(1000)

  const primera = useRef(true)
  const cargar = useCallback(async () => {
    try {
      setR(await verRetracto(id))
      setErrorCarga(false)
      if (primera.current) {
        primera.current = false
        pedirFoco('titulo-pagina')
      }
    } catch (x) {
      if (fallo(x)) return
      if (leerFallo(x).status === 404) setNoEsta(true)
      else setErrorCarga(true)
    }
  }, [id, fallo, pedirFoco])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const avisar = (tono: 'ok' | 'atenta', texto: string) => {
    setNota({ tono, texto, n: ++contador.current })
    pedirFoco(ID_NOTA)
  }

  const volverATexto = <Volver onClick={onVolver}>{T.volver}</Volver>

  if (noEsta || errorCarga || !r)
    return (
      <div className="flex flex-col items-start gap-4">
        <div className="@3xl/main:hidden">{volverATexto}</div>
        {errorCarga ? (
          <>
            <Nota tono="pronto" rol="alert">
              {T.error}
            </Nota>
            <Boton variante="secundario" onClick={() => void cargar()}>
              {MARCO.volverAIntentar}
            </Boton>
          </>
        ) : noEsta ? (
          <Nota tono="atenta" rol="status">
            {T.cambio}
          </Nota>
        ) : (
          <p className="text-tenue">{verCargando ? T.cargando : ''}</p>
        )}
      </div>
    )

  const ref = r.referencia ?? ''
  const { dia } = enChile(r.solicitado_en)
  const plazo = enChile(r.plazo_hasta)

  const resolver = async (p: NonNullable<Paso>): Promise<boolean> => {
    setErrorDialogo(T.error)
    try {
      const nuevo = await resolverRetracto(r.id, p.tipo, p.tipo === 'rechazar' ? p.motivo : null)
      setPaso(null)
      setR(nuevo)
      setMotivoAbierto(false)
      onCambio()
      avisar('ok', p.tipo === 'devolver' ? T.devolvisteHecho(r.monto, ref) : T.respondisteHecho(ref))
      return true
    } catch (x) {
      if (fallo(x)) return true
      const f = leerFallo(x)
      if (f.status === 409 || f.status === 404) {
        setPaso(null)
        setMotivoAbierto(false)
        await cargar()
        onCambio()
        avisar('atenta', T.cambio)
        return true
      }
      if (f.status === 503) setErrorDialogo(T.sinTransbank)
      return false
    }
  }

  const pedirNoDevolver = () => {
    if (!motivo) {
      setSinMotivo(true)
      pedirFoco('motivo-rechazo', 'input[type="radio"]')
      return
    }
    setPaso({ tipo: 'rechazar', motivo })
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="@3xl/main:hidden">{volverATexto}</div>
      <div className="flex flex-col items-start gap-2">
        <Titulo className="text-3xl">
          {T.fila('').trimEnd()} <span className="digitos break-words">{ref}</span>
        </Titulo>
        <EtiquetaRetracto estado={r.estado} />
        <p className="flex flex-wrap items-center gap-x-1.5 text-base text-tenue">
          <span className="cifras whitespace-normal">{T.pedidoEl(dia)}</span> ·{r.origen === 'correo' && <Mail aria-hidden className="size-5 shrink-0" />}
          <span>{r.origen === 'correo' ? T.porCorreo : T.porLaApp}</span>
        </p>
        {r.estado === 'solicitado' && <p className="cifras font-bold whitespace-normal">{T.responderAntes(plazo.fecha)}</p>}
      </div>
      {nota && (
        <div key={nota.n}>
          <Nota id={ID_NOTA} enfocable tono={nota.tono} rol="status">
            {nota.texto}
          </Nota>
        </div>
      )}
      <section aria-labelledby="retracto-productos" className="flex flex-col gap-2">
        <h2 id="retracto-productos" className="text-xl font-bold">
          {T.productos}
        </h2>
        <ul className="flex flex-col divide-y divide-linea">
          {r.lineas.map((l) => (
            <li key={l.linea_id} className="flex flex-col gap-0.5 py-2">
              <span className="font-bold break-words">
                <span className="cifras">{`${l.cantidad}${ESPACIO_DURO}×`}</span> {l.producto}
              </span>
              <span className="text-base text-tenue break-words">{l.presentacion}</span>
              <Monto n={l.monto} />
            </li>
          ))}
        </ul>
        <p className="text-base">{T.incluyeEnvio(r.incluye_envio)}</p>
        <p className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 border-t-2 border-tinta pt-2 text-lg font-bold angosto:grid-cols-1">
          <span>{T.seDevolverian}</span>
          <Monto n={r.monto} />
        </p>
      </section>
      {r.estado !== 'solicitado' && r.resuelto_en && <p className="cifras whitespace-normal">{T.resueltoEl(enChile(r.resuelto_en).fecha, enChile(r.resuelto_en).hora)}</p>}
      {r.estado === 'rechazado' && r.motivo_rechazo && <p className="max-w-prose">{T.motivo[r.motivo_rechazo]}</p>}
      {r.estado === 'solicitado' && (
        <div className="flex flex-col gap-4">
          {!motivoAbierto ? (
            <Acciones>
              <Boton id="retracto-devolver" icono={<Undo2 aria-hidden className="size-5" />} onClick={() => setPaso({ tipo: 'devolver' })}>
                {T.devolver(r.monto)}
              </Boton>
              <Boton
                id="retracto-no-devolver"
                variante="secundario"
                onClick={() => {
                  setMotivoAbierto(true)
                  pedirFoco('motivo-rechazo', 'input[type="radio"]')
                }}
              >
                {T.noDevolver}
              </Boton>
            </Acciones>
          ) : (
            <div className="flex flex-col gap-3">
              <GrupoOpciones
                id="motivo-rechazo"
                leyenda={T.porQue}
                nombre={`motivo-${r.id}`}
                opciones={(['sello_abierto', 'producto_no_recibido'] as const).map((m) => ({ valor: m, texto: T.motivo[m] }))}
                valor={motivo}
                onCambio={(v) => {
                  setMotivo(v)
                  setSinMotivo(false)
                }}
                error={sinMotivo ? T.eligeMotivo : null}
              >
                <p className="text-base text-tenue">{T.laFamiliaVe}</p>
              </GrupoOpciones>
              <Acciones>
                <Boton id="retracto-confirmar-no" variante="peligroPrincipal" icono={<Ban aria-hidden className="size-5" />} onClick={pedirNoDevolver}>
                  {T.noDevolver}
                </Boton>
                <Boton
                  variante="texto"
                  onClick={() => {
                    setMotivoAbierto(false)
                    setMotivo(null)
                    setSinMotivo(false)
                    pedirFoco('retracto-no-devolver')
                  }}
                >
                  {T.cancelar}
                </Boton>
              </Acciones>
            </div>
          )}
        </div>
      )}
      <Boton
        variante="texto"
        className="self-start"
        onClick={() => {
          fijar({ pedidoId: r.pedido_id, origen: '/operacion' })
          navegar('/operacion/pedido')
        }}
      >
        {T.verPedido}
      </Boton>
      <div className="@3xl/main:hidden">
        <RotuloPiloto />
      </div>
      {paso && (
        <DialogoConfirmar
          titulo={paso.tipo === 'devolver' ? T.devolverTitulo(r.monto) : T.noDevolverTitulo}
          texto={T.esDelPedido(ref)}
          destacado={paso.tipo === 'devolver' ? T.devolverDestacado(r.monto) : T.noDevolverDestacado(paso.motivo)}
          confirmar={paso.tipo === 'devolver' ? T.devolver(r.monto) : T.noDevolver}
          confirmando={paso.tipo === 'devolver' ? T.devolviendo : T.guardando}
          seguir={T.volverAlRetracto}
          error={errorDialogo}
          variante={paso.tipo === 'devolver' ? 'principal' : 'peligroPrincipal'}
          icono={paso.tipo === 'devolver' ? <Undo2 aria-hidden className="size-5" /> : <Ban aria-hidden className="size-5" />}
          onConfirmar={() => resolver(paso)}
          onCerrar={() => {
            const p = paso
            setPaso(null)
            pedirFoco(p.tipo === 'devolver' ? 'retracto-devolver' : 'retracto-confirmar-no')
          }}
        />
      )}
    </div>
  )
}

// ----------------------------------------------------------------- 8.5 el retracto por correo

type FalloCorreo = { tipo: 'no-es-admin' | 'no-retractable' | 'red' } | { tipo: 'fuera-de-plazo'; fecha: string }
const CORREO_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function RetractoPorCorreo({ pedido, onListo, onCancelar }: { pedido: PedidoDetalle; onListo: (r: RetractoOperacion) => void; onCancelar: () => void }) {
  const { fallo } = useOperacion()
  const [correo, setCorreo] = useState('')
  const [errorCorreo, setErrorCorreo] = useState<string | null>(null)
  const [ninguno, setNinguno] = useState(false)
  const [falla, setFalla] = useState<FalloCorreo | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const intento = useRef(0)
  const [n, setN] = useState(0)
  const pedirFoco = useFocoAlMontar()
  /** 8.5: las líneas que se entregaron, con lo entregado como máximo. Las que faltaron ya se devolvieron. */
  const lineas = pedido.lineas
    .filter((l) => l.estado_linea !== 'eliminada' && l.estado_linea !== 'devuelta')
    .map((l) => ({ l, max: Math.max(0, l.cantidad - Math.min(l.cantidad, l.unidades_faltantes)) }))
    .filter((x) => x.max > 0)
  const [cantidades, setCantidades] = useState<Record<string, number>>({})

  useEffect(() => {
    pedirFoco('retracto-correo-campo', 'input')
  }, [pedirFoco])

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (ocupado) return
    const c = correo.trim()
    const elegidas = lineas.filter((x) => (cantidades[x.l.id] ?? 0) > 0).map((x) => ({ linea_id: x.l.id, cantidad: cantidades[x.l.id] }))
    const err = !c ? T.sinCorreo : !CORREO_VALIDO.test(c) ? T.correoMalo : null
    setErrorCorreo(err)
    setNinguno(elegidas.length === 0)
    setFalla(null)
    if (err) return pedirFoco('retracto-correo-campo', 'input')
    if (!elegidas.length) return pedirFoco('retracto-lineas', 'button:not(:disabled)')
    setOcupado(true)
    setN(++intento.current)
    try {
      const r = await registrarRetractoPorCorreo(pedido.id, c, elegidas)
      setCorreo('')
      onListo(r)
    } catch (x) {
      if (fallo(x)) return
      const f = leerFallo(x)
      // 8.5 (D-81-9): con cualquier respuesta del servidor, el correo se borra; sin respuesta, se conserva.
      if (f.status !== null && f.status < 500) setCorreo('')
      if (f.status === 422 && esProblema(f.tipo, 'solicitante-invalido')) {
        setFalla({ tipo: 'no-es-admin' })
        pedirFoco('retracto-correo-campo', 'input')
      } else if (f.status === 422) setFalla({ tipo: 'no-retractable' })
      // Se admiten varios retractos por pedido: pedir unidades ya pedidas en otro también es el 422 de arriba.
      else if (f.status === 409) {
        const hasta = extensionDe(x, 'plazo_hasta')
        setFalla({ tipo: 'fuera-de-plazo', fecha: enChile(typeof hasta === 'string' ? hasta : (pedido.retracto_plazo_hasta ?? new Date().toISOString())).fecha })
      } else setFalla({ tipo: 'red' })
    } finally {
      setOcupado(false)
    }
  }

  const plazo = pedido.retracto_plazo_hasta ? enChile(pedido.retracto_plazo_hasta).fecha : null

  return (
    <form noValidate onSubmit={(e) => void enviar(e)} aria-labelledby="retracto-correo-titulo" className="flex flex-col gap-4 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea">
      <div className="flex flex-col gap-1">
        <h3 id="retracto-correo-titulo" className="font-bold">
          {T.registrar}
        </h3>
        {plazo && <p className="cifras text-base whitespace-normal text-tenue">{T.plazoVence(plazo)}</p>}
      </div>
      {falla && falla.tipo !== 'red' && (
        <div key={n}>
          {falla.tipo === 'no-es-admin' ? (
            <Nota tono="atenta" rol="alert" titulo={T.noEsAdminTitulo}>
              {T.noEsAdminTexto}
            </Nota>
          ) : (
            <Nota tono="atenta" rol="alert">
              {falla.tipo === 'fuera-de-plazo' ? T.fueraDePlazo(falla.fecha) : T.noRetractable}
            </Nota>
          )}
        </div>
      )}
      <div id="retracto-correo-campo">
        <CampoTexto
          etiqueta={T.correo}
          type="email"
          value={correo}
          onChange={(e) => {
            setCorreo(e.target.value)
            setErrorCorreo(null)
          }}
          autoComplete="off"
          spellCheck={false}
          maxLength={254}
          ayuda={T.correoAyuda}
          error={errorCorreo}
        />
      </div>
      <fieldset id="retracto-lineas" className="flex flex-col gap-4">
        <legend className="mb-2 font-bold">{T.queProductos}</legend>
        {lineas.map(({ l, max }) => (
          <fieldset key={l.id} className="flex flex-col gap-1">
            <legend className="mb-1 font-bold break-words">
              <span className="cifras">{`${max}${ESPACIO_DURO}×`}</span> {l.producto}
            </legend>
            <Stepper etiqueta={T.cuantos} valor={cantidades[l.id] ?? 0} min={0} max={max} onCambio={(v) => setCantidades((c) => ({ ...c, [l.id]: v }))} />
          </fieldset>
        ))}
      </fieldset>
      {ninguno && <MensajeError>{T.ningunProducto}</MensajeError>}
      {falla?.tipo === 'red' && (
        <div key={n}>
          <Nota tono="pronto" rol="alert">
            {MARCO.error}
          </Nota>
        </div>
      )}
      <Acciones>
        <Boton type="submit" ocupado={ocupado} textoOcupado={T.registrando}>
          {T.registrarBoton}
        </Boton>
        <Boton variante="texto" onClick={onCancelar}>
          {T.cancelar}
        </Boton>
      </Acciones>
    </form>
  )
}

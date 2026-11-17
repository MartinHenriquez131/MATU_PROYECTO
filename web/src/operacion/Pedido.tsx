// Un pedido (especificación MATU-81, sección 6): las partes con sus productos y el código de retiro,
// la acción que sigue con su confirmación, el pago, lo que pasó, las incidencias y los retractos.
// Abrirlo pide el detalle y el cobro, que el servidor registra como `operacion.pedido_ver` (C9): no
// se vuelven a pedir por el refresco de la lista, solo al abrir, después de una acción, tras un 409.
// Sin interfaz optimista: cada acción espera la respuesta. El monto de cada confirmación es el
// `monto_a_devolver` de la API; aquí no se calcula ni se resta ningún monto (C22).
import { useCallback, useEffect, useRef, useState } from 'react'
import { Check as CheckIcono, Circle as CirculoIcono, Cog, Headset, KeyRound, PackageCheck, PackageX, Store, Truck, Undo2, Users, type LucideIcon } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import {
  generarCodigo,
  hacerAccion,
  listarIncidencias,
  listarRetractos,
  verCobro,
  verPedido,
  type AccionDisponible,
  type CobroPedido,
  type EventoLineaTiempo,
  type IncidenciaVista,
  type LineaDetalle,
  type ParteDetalle,
  type PedidoDetalle,
  type RetractoOperacion,
  type TipoIncidencia,
} from '../compartido/api/operacion'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { useDemora } from '../compartido/useDemora'
import { DialogoConfirmar } from '../familia/DialogoConfirmar'
import { navegar } from '../familia/ruteo'
import { Acciones, Titulo, Volver } from '../familia/ui'
import { Pago } from './Cobro'
import { enChile, EtiquetaCon, EtiquetaIncidencia, EtiquetaParte, EtiquetaPedido, Monto, palabraPedido, useAhora, useFocoAlMontar } from './comun'
import { useOperacion, type OrigenPedido } from './estado'
import { AnotarIncidencia } from './Incidencias'
import { RotuloPiloto } from './Marco'
import { RetractoPorCorreo } from './Retractos'
import { ACCIONES, CODIGO, ESPACIO_DURO, MARCO, ESTADO_ANULACION, ESTADO_LINEA, ESTADO_PARTE, INCIDENCIAS, LINEA_TIEMPO, MOTIVO_ANULACION, PEDIDO as T, RETRACTOS, TIPO_INCIDENCIA } from './textos'

const ID_NOTA = 'nota-del-pedido'
const ID_CODIGO = 'codigo-de-retiro'
const idBotonAccion = (a: string) => `accion-${a}`
const idBotonCodigo = (parteId: string) => `codigo-${parteId}`

type NotaPedido = { tono: 'ok' | 'atenta' | 'pronto'; texto: string; n: number; irARetractos?: string }
type Formulario = { tipo: 'incidencia'; tipoInicial: TipoIncidencia | null } | { tipo: 'retracto' } | null
interface CodigoVisible {
  parte: ParteDetalle
  codigo: string
  expiraEn: string
}

export function DetallePedido({ pedidoId, origen, onCambio, conRotulo }: { pedidoId: string; origen: OrigenPedido; onCambio: () => void; conRotulo: 'siempre' | 'angosto' }) {
  const { fallo, fijar } = useOperacion()
  const [pedido, setPedido] = useState<PedidoDetalle | null>(null)
  const [noEsta, setNoEsta] = useState(false)
  const [errorCarga, setErrorCarga] = useState(false)
  const [cobro, setCobro] = useState<CobroPedido | null>(null)
  const [cobroFallo, setCobroFallo] = useState(false)
  const [incidencias, setIncidencias] = useState<IncidenciaVista[]>([])
  const [retractos, setRetractos] = useState<RetractoOperacion[]>([])
  const [nota, setNota] = useState<NotaPedido | null>(null)
  const [accion, setAccion] = useState<AccionDisponible | null>(null)
  const [parteCodigo, setParteCodigo] = useState<ParteDetalle | null>(null)
  const [errorDialogo, setErrorDialogo] = useState<string>(T.error)
  /** 6.4 (C20): el código, solo aquí, en la memoria de esta pantalla. Se borra al desmontarla. */
  const [codigo, setCodigo] = useState<CodigoVisible | null>(null)
  const [formulario, setFormulario] = useState<Formulario>(null)
  const { ahora, fijarFecha } = useAhora()
  const pedirFoco = useFocoAlMontar()
  const verCargando = useDemora(1000)
  const contador = useRef(0)
  /** Una acción quedó sin respuesta (red): pudo haberse hecho, así que el pedido se vuelve a pedir al cerrar. */
  const sinRespuesta = useRef(false)
  const primera = useRef(true)

  const avisar = useCallback(
    (tono: NotaPedido['tono'], texto: string, extra: Partial<NotaPedido> = {}) => {
      setNota({ tono, texto, n: ++contador.current, ...extra })
      pedirFoco(ID_NOTA)
    },
    [pedirFoco],
  )

  const traerCobro = useCallback(async (): Promise<CobroPedido | null> => {
    try {
      const c = await verCobro(pedidoId)
      setCobro(c)
      setCobroFallo(false)
      return c
    } catch (x) {
      if (!fallo(x)) setCobroFallo(true)
      return null
    }
  }, [pedidoId, fallo])

  /** El pedido y su cobro; además, las incidencias y los retractos por resolver de este pedido. */
  const cargar = useCallback(async (): Promise<{ pedido: PedidoDetalle | null; cobro: CobroPedido | null }> => {
    const deCobro = traerCobro()
    void listarIncidencias(null)
      .then((l) => setIncidencias(l.filter((i) => i.pedido_id === pedidoId)))
      .catch(() => undefined)
    void listarRetractos()
      .then((r) => setRetractos(r.retractos.filter((x) => x.pedido_id === pedidoId)))
      .catch(() => undefined)
    try {
      const r = await verPedido(pedidoId)
      fijarFecha(r.fecha)
      setPedido(r.pedido)
      setErrorCarga(false)
      // 2.1: llegar al pedido (o elegir otro en pantalla ancha): el foco va a su `h1` cuando ya está.
      if (primera.current) {
        primera.current = false
        pedirFoco('titulo-pagina')
      }
      return { pedido: r.pedido, cobro: await deCobro }
    } catch (x) {
      if (!fallo(x)) {
        if (leerFallo(x).status === 404) setNoEsta(true)
        else setErrorCarga(true)
      }
      return { pedido: null, cobro: await deCobro }
    }
  }, [pedidoId, traerCobro, fijarFecha, fallo, pedirFoco])

  useEffect(() => {
    void cargar()
  }, [cargar])

  // 6.4: el código desaparece a la hora en que vence (la hora del servidor, cabecera `Date`).
  useEffect(() => {
    if (!codigo) return
    const espera = new Date(codigo.expiraEn).getTime() - ahora().getTime()
    const t = window.setTimeout(() => setCodigo(null), Math.max(0, Math.min(espera, 2 ** 31 - 1)))
    return () => window.clearTimeout(t)
  }, [codigo, ahora])

  const volver = () => {
    fijar({ pedidoId: null })
    navegar(origen)
  }

  if (noEsta)
    return (
      <div className="flex flex-col items-start gap-4">
        <Nota tono="atenta" rol="status">
          {T.yaNoEsta}
        </Nota>
        <Boton variante="texto" onClick={volver}>
          {origen === '/operacion/cobros' ? T.volverCobros : T.volverPedidos}
        </Boton>
      </div>
    )
  if (!pedido)
    return (
      <div className="flex flex-col items-start gap-4" aria-busy={!errorCarga || undefined}>
        {errorCarga ? (
          <>
            <Nota tono="pronto" rol="alert">
              {T.error}
            </Nota>
            <Boton variante="secundario" onClick={() => void cargar()}>
              {MARCO.volverAIntentar}
            </Boton>
          </>
        ) : (
          <p className="text-tenue">{verCargando ? T.cargando : ''}</p>
        )}
      </div>
    )

  const ref = pedido.referencia ?? ''
  const pagado = enChile(pedido.pagado_en)

  // ----------------------------------------------------------------- 6.5 las acciones
  const confirmarAccion = async (a: AccionDisponible): Promise<boolean> => {
    setErrorDialogo(T.error)
    try {
      await hacerAccion(pedido.id, a.accion)
      setAccion(null)
      const r = await cargar()
      onCambio()
      // 6.5: si la devolución de la cancelación quedó sin terminar, la nota lo dice y manda a «Cobros».
      const sinTerminar = a.accion === 'cancelar_con_devolucion' && r.cobro?.anulaciones.some((x) => x.estado === 'rechazada')
      avisar('ok', sinTerminar ? T.devolucionNoSalio(ref, a.monto_a_devolver) : ACCIONES[a.accion].hecho(ref, a.monto_a_devolver))
      return true
    } catch (x) {
      if (fallo(x)) return true
      const f = leerFallo(x)
      if (f.status === 409) {
        setAccion(null)
        await cargar()
        onCambio()
        avisar('atenta', T.cambio)
        return true
      }
      if (f.status === 404) {
        setAccion(null)
        setNoEsta(true)
        return true
      }
      if (f.status === 503 && a.accion === 'cancelar_con_devolucion') setErrorDialogo(T.sinTransbank)
      else if (f.status === null || f.status >= 500) sinRespuesta.current = true
      return false
    }
  }

  const cerrarAccion = () => {
    const a = accion
    setAccion(null)
    if (sinRespuesta.current) {
      sinRespuesta.current = false
      void cargar()
    }
    if (a) pedirFoco(idBotonAccion(a.accion))
  }

  // ----------------------------------------------------------------- 6.4 el código de retiro
  const confirmarCodigo = async (parte: ParteDetalle): Promise<boolean> => {
    setErrorDialogo(CODIGO.error)
    try {
      const r = await generarCodigo(parte.id)
      fijarFecha(r.fecha)
      setParteCodigo(null)
      setCodigo({ parte, codigo: r.codigo.codigo, expiraEn: r.codigo.expira_en })
      pedirFoco(`${ID_CODIGO}-titulo`)
      void cargar()
      return true
    } catch (x) {
      if (fallo(x)) return true
      const f = leerFallo(x)
      if (f.status === 409) {
        setParteCodigo(null)
        await cargar()
        avisar('atenta', CODIGO.cambio)
        return true
      }
      if (f.status === 404) {
        setParteCodigo(null)
        setNoEsta(true)
        return true
      }
      if (f.status === 503) {
        setParteCodigo(null)
        avisar('pronto', CODIGO.noPudimos)
        return true
      }
      return false
    }
  }

  const lineasDe = (p: ParteDetalle) => pedido.lineas.filter((l) => l.parte_id === p.id && l.estado_linea !== 'eliminada')
  const principales = pedido.acciones.filter((a) => a.accion === 'en_camino' || a.accion === 'entregado')
  const otras = pedido.acciones.filter((a) => a.accion === 'no_entregado' || a.accion === 'cancelar_con_devolucion')
  const conAcciones = !formulario && pedido.acciones.length > 0

  const abrirIncidencia = (tipoInicial: TipoIncidencia | null) => {
    setFormulario({ tipo: 'incidencia', tipoInicial })
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="@3xl/main:hidden">
        <Volver onClick={volver}>{origen === '/operacion/cobros' ? T.volverCobros : T.volverPedidos}</Volver>
      </div>
      {origen === '/operacion/cobros' && (
        <div className="hidden @3xl/main:block">
          <Volver onClick={volver}>{T.volverCobros}</Volver>
        </div>
      )}
      {/* 6.2: el `h1` y la etiqueta a la izquierda, las acciones a la derecha. */}
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="flex min-w-0 flex-col items-start gap-2">
          <Titulo className="text-3xl">
            {T.titulo('').trimEnd()} <span className="digitos break-words">{ref}</span>
          </Titulo>
          <EtiquetaPedido estado={pedido.estado} />
          <p className="cifras text-base whitespace-normal text-tenue">{T.pagadoEl(pagado.fecha, pagado.hora)}</p>
        </div>
        {conAcciones && (
          <Acciones>
            {principales.map((a) => (
              <Boton key={a.accion} id={idBotonAccion(a.accion)} icono={<IconoAccion a={a.accion} />} onClick={() => setAccion(a)}>
                {ACCIONES[a.accion].boton}
              </Boton>
            ))}
            {otras.map((a) => (
              <Boton
                key={a.accion}
                id={idBotonAccion(a.accion)}
                variante={a.accion === 'cancelar_con_devolucion' ? 'peligro' : 'secundario'}
                icono={<IconoAccion a={a.accion} />}
                onClick={() => setAccion(a)}
              >
                {ACCIONES[a.accion].boton}
              </Boton>
            ))}
          </Acciones>
        )}
      </div>

      {nota && (
        <div key={nota.n} className="flex flex-col items-start gap-2">
          <Nota id={ID_NOTA} enfocable tono={nota.tono} rol={nota.tono === 'pronto' ? 'alert' : 'status'}>
            {nota.texto}
          </Nota>
          {nota.irARetractos && (
            <Boton
              variante="texto"
              onClick={() => {
                fijar({ retractoId: nota.irARetractos ?? null })
                navegar('/operacion/retractos')
              }}
            >
              {RETRACTOS.irARetractos}
            </Boton>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-x-10 gap-y-8 @4xl/detalle:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex min-w-0 flex-col gap-8">
          <section aria-labelledby="partes-titulo" className="flex flex-col gap-4">
            <h2 id="partes-titulo" className="text-xl font-bold">
              {T.partes}
            </h2>
            {pedido.partes.map((p) => (
              <Parte
                key={p.id}
                parte={p}
                lineas={lineasDe(p)}
                codigo={codigo?.parte.id === p.id ? codigo : null}
                onGenerar={() => setParteCodigo(p)}
                onYaLoTengo={() => {
                  setCodigo(null)
                  pedirFoco(idBotonCodigo(p.id))
                }}
              />
            ))}
          </section>

          <section aria-labelledby="incidencias-titulo" className="flex flex-col gap-3">
            <h2 id="incidencias-titulo" className="text-xl font-bold">
              {INCIDENCIAS.titulo}
            </h2>
            {incidencias.length > 0 && (
              <ul className="flex flex-col gap-2">
                {incidencias.map((i) => (
                  <li key={i.id}>
                    <button
                      type="button"
                      onClick={() => {
                        fijar({ incidenciaId: i.id })
                        navegar('/operacion/incidencias')
                      }}
                      className="flex min-h-12 w-full flex-wrap items-center justify-between gap-x-3 gap-y-1 rounded-xl bg-hoja px-4 angosto:px-2 py-3 text-left font-bold ring-1 ring-linea hover:ring-borde"
                    >
                      <span className="min-w-0">{TIPO_INCIDENCIA[i.tipo]}</span>
                      <EtiquetaIncidencia estado={i.estado} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {formulario?.tipo === 'incidencia' ? (
              <AnotarIncidencia
                pedidoId={pedido.id}
                tipoInicial={formulario.tipoInicial}
                onCancelar={() => {
                  setFormulario(null)
                  pedirFoco('abrir-incidencia')
                }}
                onListo={(i) => {
                  setFormulario(null)
                  setIncidencias((l) => [...l, i])
                  onCambio()
                  avisar('ok', INCIDENCIAS.anotaste(ref))
                }}
              />
            ) : (
              <Boton id="abrir-incidencia" variante="secundario" className="self-start" onClick={() => abrirIncidencia(null)}>
                {INCIDENCIAS.anotarTitulo}
              </Boton>
            )}
          </section>

          <section aria-labelledby="retractos-titulo" className="flex flex-col gap-3">
            <h2 id="retractos-titulo" className="text-xl font-bold">
              {RETRACTOS.seccion}
            </h2>
            {retractos.length > 0 && (
              <ul className="flex flex-col gap-2">
                {retractos.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => {
                        fijar({ retractoId: r.id })
                        navegar('/operacion/retractos')
                      }}
                      className="flex min-h-12 w-full flex-col items-start gap-0.5 rounded-xl bg-hoja px-4 angosto:px-2 py-3 text-left ring-1 ring-linea hover:ring-borde"
                    >
                      <span className="font-bold">
                        {RETRACTOS.fila('').trimEnd()} <span className="digitos">{r.referencia ?? ref}</span>
                      </span>
                      <span>
                        <Monto n={r.monto} /> · {r.origen === 'correo' ? RETRACTOS.porCorreo : RETRACTOS.porLaApp}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {formulario?.tipo === 'retracto' ? (
              <RetractoPorCorreo
                pedido={pedido}
                onCancelar={() => {
                  setFormulario(null)
                  pedirFoco('abrir-retracto')
                }}
                onListo={(r) => {
                  setFormulario(null)
                  setRetractos((l) => [...l, r])
                  onCambio()
                  avisar('ok', RETRACTOS.registrado(ref), { irARetractos: r.id })
                }}
              />
            ) : (
              pedido.retracto_plazo_hasta && (
                <Boton id="abrir-retracto" variante="secundario" className="self-start" onClick={() => setFormulario({ tipo: 'retracto' })}>
                  {RETRACTOS.registrar}
                </Boton>
              )
            )}
          </section>
        </div>

        <div className="flex min-w-0 flex-col gap-8">
          <Pago
            cobro={cobro}
            fallo={cobroFallo}
            onReintentar={() => void traerCobro()}
            onAnotar={formulario ? undefined : abrirIncidencia}
          />
          <LineaDeTiempo eventos={pedido.linea_de_tiempo} />
        </div>
      </div>

      <div className={conRotulo === 'angosto' ? '@3xl/main:hidden' : ''}>
        <RotuloPiloto />
      </div>

      {accion && (
        <DialogoConfirmar
          titulo={ACCIONES[accion.accion].titulo(ref)}
          texto={ACCIONES[accion.accion].texto}
          destacado={ACCIONES[accion.accion].destacado(accion.monto_a_devolver)}
          confirmar={ACCIONES[accion.accion].boton}
          confirmando={ACCIONES[accion.accion].ocupado}
          seguir={ACCIONES[accion.accion].seguir}
          error={errorDialogo}
          variante={accion.accion === 'en_camino' || accion.accion === 'entregado' ? 'principal' : 'peligroPrincipal'}
          icono={<IconoAccion a={accion.accion} />}
          onConfirmar={() => confirmarAccion(accion)}
          onCerrar={cerrarAccion}
        />
      )}
      {parteCodigo && (
        <DialogoConfirmar
          titulo={parteCodigo.estado_codigo === 'sin_codigo' ? CODIGO.tituloGenerar(parteCodigo.referencia) : CODIGO.tituloNuevo(parteCodigo.referencia)}
          texto={CODIGO.texto}
          destacado={parteCodigo.estado_codigo === 'sin_codigo' ? undefined : CODIGO.anteriorDejaDeServir}
          confirmar={parteCodigo.estado_codigo === 'sin_codigo' ? CODIGO.generar : CODIGO.generarNuevo}
          confirmando={CODIGO.generando}
          seguir={CODIGO.seguir}
          error={errorDialogo}
          variante="principal"
          icono={<KeyRound aria-hidden className="size-5" />}
          onConfirmar={() => confirmarCodigo(parteCodigo)}
          onCerrar={() => {
            const p = parteCodigo
            setParteCodigo(null)
            pedirFoco(idBotonCodigo(p.id))
          }}
        />
      )}
    </div>
  )
}

const ICONO_ACCION: Record<AccionDisponible['accion'], LucideIcon> = {
  en_camino: Truck,
  entregado: PackageCheck,
  no_entregado: PackageX,
  cancelar_con_devolucion: Undo2,
}
function IconoAccion({ a }: { a: AccionDisponible['accion'] }) {
  const Icono = ICONO_ACCION[a]
  return <Icono aria-hidden className="size-5" />
}

// ----------------------------------------------------------------- 6.3 una parte

function Parte({
  parte,
  lineas,
  codigo,
  onGenerar,
  onYaLoTengo,
}: {
  parte: ParteDetalle
  lineas: LineaDetalle[]
  codigo: CodigoVisible | null
  onGenerar: () => void
  onYaLoTengo: () => void
}) {
  const idTitulo = `parte-${parte.id}`
  return (
    <section aria-labelledby={idTitulo} className="flex flex-col gap-2 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea @3xl/main:rounded-none @3xl/main:bg-transparent @3xl/main:px-0 @3xl/main:py-0 @3xl/main:pt-4 @3xl/main:ring-0 @3xl/main:border-t @3xl/main:border-linea">
      <h3 id={idTitulo} className="font-bold break-words">
        {parte.comercio.nombre_fantasia} {parte.comercio.ficticio && <span className="inline-block">{T.ficticio}</span>}
      </h3>
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span>
          {T.parte} <span className="digitos">{parte.referencia}</span>
        </span>
        <EtiquetaParte estado={parte.estado} />
      </p>
      <ul className="flex flex-col divide-y divide-linea">
        {lineas.map((l) => (
          <Linea key={l.id} l={l} />
        ))}
      </ul>
      {codigo ? <CodigoUnaVez c={codigo} onYaLoTengo={onYaLoTengo} /> : <RenglonCodigo parte={parte} onGenerar={onGenerar} />}
    </section>
  )
}

function estadoLinea(l: LineaDetalle): { texto: string; tono: 'neutro' | 'ok'; Icono: LucideIcon } {
  if (l.estado_linea === 'preparada') return { texto: ESTADO_LINEA.loTiene, tono: 'ok', Icono: CheckIcono }
  if (l.estado_linea === 'faltante' || l.estado_linea === 'sin_stock') return { texto: ESTADO_LINEA.falto, tono: 'neutro', Icono: PackageX }
  if (l.estado_linea === 'devuelta') return { texto: ESTADO_LINEA.devuelto, tono: 'neutro', Icono: Undo2 }
  return { texto: ESTADO_LINEA.porMarcar, tono: 'neutro', Icono: CirculoIcono }
}

function Linea({ l }: { l: LineaDetalle }) {
  const e = estadoLinea(l)
  const faltan = l.unidades_faltantes > 0 ? Math.min(l.cantidad, l.unidades_faltantes) : l.estado_linea === 'faltante' || l.estado_linea === 'devuelta' ? l.cantidad : 0
  return (
    <li className="flex flex-col gap-1 py-3">
      <span className="font-bold break-words">
        <span className="cifras">{`${l.cantidad}${ESPACIO_DURO}×`}</span> {l.producto}
      </span>
      <span className="text-base text-tenue break-words">{l.presentacion}</span>
      <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Monto n={l.subtotal} />
        <EtiquetaCon Icono={e.Icono} tono={e.tono} texto={e.texto} />
      </span>
      {faltan > 0 && (
        <span className="text-base text-tenue">
          <span className="cifras">{T.faltanDe(faltan, l.cantidad)}</span>
          {l.devolucion === 'hecha' ? ` · ${T.devuelto}` : l.devolucion === 'en_curso' ? ` · ${T.devolucionEnCurso}` : ''}
        </span>
      )}
    </li>
  )
}

/** 6.4: el renglón del código según su estado. */
function RenglonCodigo({ parte, onGenerar }: { parte: ParteDetalle; onGenerar: () => void }) {
  let texto: string | null = null
  let boton: string | null = null
  if (parte.estado_codigo === 'usado') texto = CODIGO.usado
  else if (parte.estado === 'lista') {
    texto = { sin_codigo: CODIGO.sinCodigo, vigente: CODIGO.vigente, vencido: CODIGO.vencido, bloqueado: CODIGO.bloqueado }[parte.estado_codigo]
    boton = parte.estado_codigo === 'sin_codigo' ? CODIGO.generar : CODIGO.generarNuevo
  } else if (parte.estado !== 'cancelada') texto = CODIGO.cuandoEsteListo
  if (!texto) return null
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-linea pt-3 text-base">
      <span className="flex min-w-0 items-start gap-2">
        <KeyRound aria-hidden className="mt-0.5 size-5 shrink-0 text-tenue" />
        <span className="min-w-0">{texto}</span>
      </span>
      {boton && (
        <Boton id={idBotonCodigo(parte.id)} variante="secundario" onClick={onGenerar}>
          {boton}
        </Boton>
      )}
    </p>
  )
}

/**
 * 6.4 (C20): el código, una sola vez. Sin botón de copiar, con `select-none` en los dígitos, y nunca
 * en un `title`, una región viva ni un anuncio. El lector lo lee por la etiqueta de su imagen.
 */
function CodigoUnaVez({ c, onYaLoTengo }: { c: CodigoVisible; onYaLoTengo: () => void }) {
  const vence = enChile(c.expiraEn)
  return (
    <section aria-labelledby={`${ID_CODIGO}-titulo`} className="flex flex-col gap-3 rounded-xl bg-rocio px-5 angosto:px-2 py-5">
      <h3 id={`${ID_CODIGO}-titulo`} tabIndex={-1} className="flex items-start gap-2 font-bold break-words outline-none">
        <KeyRound aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />
        <span className="min-w-0">{CODIGO.titulo(c.parte.referencia)}</span>
      </h3>
      <p role="img" aria-label={CODIGO.paraLector(c.codigo)} className="flex flex-wrap gap-x-6 select-none">
        <span aria-hidden className="digitos text-6xl angosto:text-3xl font-bold tracking-widest text-turquesa">
          {c.codigo.slice(0, 3)}
        </span>
        <span aria-hidden className="digitos text-6xl angosto:text-3xl font-bold tracking-widest text-turquesa">
          {c.codigo.slice(3)}
        </span>
      </p>
      <p className="cifras font-bold whitespace-normal">{CODIGO.vence(vence.fecha, vence.hora)}</p>
      <p className="text-base break-words">{CODIGO.daselo(c.parte.comercio.nombre_fantasia)}</p>
      <p className="text-base">{CODIGO.soloAhora}</p>
      <div className="border-t border-linea pt-2">
        <Boton variante="texto" onClick={onYaLoTengo}>
          {CODIGO.yaLoTengo}
        </Boton>
      </div>
    </section>
  )
}

// ----------------------------------------------------------------- 6.6 lo que pasó

const ICONO_ACTOR: Record<EventoLineaTiempo['actor_tipo'], LucideIcon> = { familia: Users, comercio: Store, operacion: Headset, sistema: Cog }

/** La frase de un hecho, o `null` si la pantalla no la conoce (no se muestra). */
function fraseDe(e: EventoLineaTiempo): { frase: string; leer?: string; motivo?: string } | null {
  if (e.tipo === 'estado') {
    const hacia = e.hacia ? palabraPedido(e.hacia) : null
    if (!hacia) return null
    const desde = e.desde ? palabraPedido(e.desde) : null
    const motivo = e.motivo ? LINEA_TIEMPO.motivo[e.motivo] : undefined
    return desde ? { frase: `${desde} → ${hacia}`, leer: LINEA_TIEMPO.deA(desde, hacia), motivo } : { frase: hacia, motivo }
  }
  if (e.tipo === 'parte') {
    const estado = e.hacia && e.hacia in ESTADO_PARTE ? ESTADO_PARTE[e.hacia as ParteDetalle['estado']] : null
    return estado && e.comercio ? { frase: LINEA_TIEMPO.parte(e.comercio, estado) } : null
  }
  if (e.tipo === 'cobro') return e.monto !== null ? { frase: LINEA_TIEMPO.cobro(e.monto) } : null
  if (e.tipo === 'anulacion') {
    const estado = e.hacia && e.hacia in ESTADO_ANULACION ? ESTADO_ANULACION[e.hacia as keyof typeof ESTADO_ANULACION] : null
    if (!estado || e.monto === null) return null
    const motivo = e.motivo && e.motivo in MOTIVO_ANULACION ? MOTIVO_ANULACION[e.motivo as keyof typeof MOTIVO_ANULACION] : undefined
    return { frase: LINEA_TIEMPO.anulacion(e.monto, estado), motivo }
  }
  if (e.tipo === 'retracto') {
    if (e.hacia === 'solicitado') return { frase: LINEA_TIEMPO.retractoPedido }
    const motivo = e.motivo && e.motivo in RETRACTOS.motivo ? RETRACTOS.motivo[e.motivo as keyof typeof RETRACTOS.motivo] : undefined
    if (e.hacia === 'devuelto') return { frase: LINEA_TIEMPO.retractoDevuelto }
    if (e.hacia === 'rechazado') return { frase: LINEA_TIEMPO.retractoSinDevolucion, motivo }
    return null
  }
  if (e.tipo === 'incidencia') {
    const motivo = e.motivo && e.motivo in TIPO_INCIDENCIA ? TIPO_INCIDENCIA[e.motivo as TipoIncidencia] : undefined
    if (e.hacia === 'abierta') return { frase: LINEA_TIEMPO.incidenciaAbierta, motivo }
    if (e.hacia === 'resuelta') return { frase: LINEA_TIEMPO.incidenciaResuelta, motivo }
  }
  return null
}

/** C6: el actor en palabras, nunca el nombre de una persona. */
const actorDe = (e: EventoLineaTiempo) => (e.actor_tipo === 'comercio' ? (e.comercio ?? '') : LINEA_TIEMPO.actor[e.actor_tipo])

function LineaDeTiempo({ eventos }: { eventos: EventoLineaTiempo[] }) {
  const lista = [...eventos]
    .sort((a, b) => new Date(b.en).getTime() - new Date(a.en).getTime())
    .map((e) => ({ e, f: fraseDe(e) }))
    .filter((x): x is { e: EventoLineaTiempo; f: NonNullable<ReturnType<typeof fraseDe>> } => x.f !== null)
  return (
    <section aria-labelledby="linea-tiempo-titulo" className="flex flex-col gap-3">
      <h2 id="linea-tiempo-titulo" className="text-xl font-bold">
        {LINEA_TIEMPO.titulo}
      </h2>
      {lista.length === 0 ? (
        <p className="text-tenue">{LINEA_TIEMPO.vacio}</p>
      ) : (
        <ol className="flex flex-col">
          {lista.map(({ e, f }, i) => {
            const { dia, hora } = enChile(e.en)
            const Icono = ICONO_ACTOR[e.actor_tipo]
            return (
              <li key={`${e.en}-${i}`} className="flex gap-3 border-b border-linea py-2 angosto:flex-col angosto:gap-1">
                <span className="cifras shrink-0 whitespace-normal text-tenue">{`${dia} ${hora}`}</span>
                <span className="flex min-w-0 flex-col">
                  <span className="font-bold break-words">
                    {f.leer ? (
                      <>
                        <span aria-hidden>{f.frase}</span>
                        <span className="sr-only">{f.leer}</span>
                      </>
                    ) : (
                      f.frase
                    )}
                  </span>
                  {f.motivo && <span className="text-base text-tenue">{f.motivo}</span>}
                  <span className="flex items-center gap-1.5 text-base text-tenue">
                    <Icono aria-hidden className="size-5 shrink-0 text-tenue" />
                    <span className="min-w-0 break-words">{actorDe(e)}</span>
                  </span>
                </span>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}

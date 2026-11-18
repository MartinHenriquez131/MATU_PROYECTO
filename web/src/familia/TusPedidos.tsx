// «Tus pedidos» (MATU-92, capa 3; especificación docs/diseno/matu-92-tus-pedidos.md v1.1). Una sola
// pantalla para las tres rutas: `/insumos/tus-pedidos` (la lista, 3), `/insumos/tus-pedidos/pedido`
// (el detalle, 4) y `/insumos/tus-pedidos/arrepentirme` (5). El diálogo de cancelar (6) va en el detalle.
//
// - El pedido elegido vive en memoria (`pedidoElegido`, estado.tsx): las rutas no llevan ids, y nada
//   de un pedido va a localStorage, sessionStorage, la URL ni `history.state`.
// - Lo que se puede hacer lo dice el servidor (`puede_cancelar`, `puede_arrepentirse` y su motivo, C7):
//   la pantalla nunca lo deduce del rol que tiene en memoria.
// - Sin interfaz optimista (C10): arrepentirse y cancelar esperan la respuesta. Ante un error de red,
//   cancelar vuelve a leer el pedido antes de decir «Todo sigue como estaba».
// - La `Idempotency-Key` se crea una vez por intento y se reutiliza en el reintento (C8).
// - Nunca se muestra el código de retiro, la referencia de la parte ni un campo `codigo_*` (D-63-5, C15):
//   la pantalla solo pinta los campos que nombra, y el contrato no los trae.
// - Los montos son los del servidor. La única cuenta es la vista previa de lo que se devuelve (O2, D7).
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import {
  Ban,
  CalendarClock,
  Check,
  CircleCheck,
  CircleX,
  Clock,
  CloudOff,
  PackageCheck,
  PackageOpen,
  PackageX,
  Printer,
  SearchX,
  Store,
  Truck,
  Undo2,
  type LucideIcon,
} from 'lucide-react'
import { verCatalogo } from '../compartido/api/catalogo'
import { leerFallo } from '../compartido/api/cliente'
import { nombrePilaDe, type PersonaListada } from '../compartido/api/familia'
import { esPagoCompleto, leerPago, type Comprobante, type Devolucion, type PagoVista } from '../compartido/api/pago'
import { nuevaClave } from '../compartido/api/pedido'
import { esVencida } from '../compartido/api/sesion'
import {
  cancelarConDevolucion,
  esFilaCompleta,
  leerRetractos,
  leerSeguimiento,
  listarPedidos,
  pedirRetracto,
  type EstadoFamilia,
  type FilaObservador,
  type FilaPedido,
  type ListaPedidos,
  type ParteDelPedido,
  type RetractoFamilia,
  type Retractos,
  type Seguimiento,
} from '../compartido/api/tusPedidos'
import { CORREO_CONTACTO } from '../compartido/contacto'
import { anunciar, Anunciado } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { EnlaceEnFrase } from '../compartido/ui/Enlaces'
import { DialogoConfirmar } from './DialogoConfirmar'
import { puedeEditar, useFamilia, type PedidoElegido } from './estado'
import { useDemora } from './Estados'
import { enfocar, esTipo, Stepper } from './insumosComun'
import { PestanasInsumos } from './Insumos'
import { ComprobanteBoleta, DatosDelPedido, Garantias, HojaComprobante } from './Pago'
import { AvisoPiloto, UnaColumna } from './PiezasPedido'
import { navegar, RUTA_ARREPENTIRME, RUTA_DETALLE_PEDIDO, RUTA_TUS_PEDIDOS, useRuta } from './ruteo'
import { GENERAL } from './textos'
import { pesos } from './textosCatalogo'
import { PAGO } from './textosPago'
import { TUS_PEDIDOS as T } from './textosTusPedidos'
import { bajarAlDisponible, elegidas, enChile, fueraDeRango, plazoEnChile, vistaPrevia, type Elegidas } from './tusPedidosComun'
import { Acciones, Etiqueta, MensajeError, Nota, Titulo, Volver } from './ui'

/** La lista se vuelve a pedir cada 60 segundos mientras algún pedido esté en `pagado` (3.5, H8). */
const CADA_MS = 60_000
const ID_NOTA_DETALLE = 'nota-tus-pedidos'
const ID_CANCELAR = 'cancelar-con-devolucion'
const ID_YA_SE_PIDIO = 'ya-se-pidio'
const idFila = (pedidoId: string) => `fila-${pedidoId}`
const idCampo = (lineaId: string) => `devolver-${lineaId}`

const pilaDe = (p: PersonaListada | null) => (p ? (nombrePilaDe(p).trim().split(/\s+/)[0] ?? '') : '')
const mailto = `mailto:${CORREO_CONTACTO}`

/** Separa las partes de una fila para el lector («Pedido 4821, 11/11/2026, Pagado, …»). No se ve. */
const Sep = () => <span className="sr-only">, </span>
/** P3-1: después de una frase que ya termina en punto, solo un espacio: sin la coma de más («minutos., Total»). */
const Espacio = () => <span className="sr-only"> </span>
/** La cola «·» de DISENO.md 2: se ve y no se lee. En `angosto` se oculta y lo que sigue baja de renglón. */
const Punto = () => (
  <span aria-hidden className="angosto:hidden">
    {' · '}
  </span>
)

// ---------------------------------------------------------------- el estado del pedido (4.2)

type Tono = 'ok' | 'neutro' | 'atenta'
interface EstadoVisible {
  tono: Tono
  Icono: LucideIcon
  texto: ReactNode
  explicacion: ReactNode | null
}

/**
 * La palabra y el ícono del estado para la familia (C16), sin la explicación. El turquesa no marca
 * ningún estado. MATU-113 (3.3): es lo único que ve quien «Se informa», que nunca recibe montos.
 */
function estadoSinExplicacion(estado: EstadoFamilia, entregadoEn: string | null): Omit<EstadoVisible, 'explicacion'> {
  const e = T.estado
  switch (estado) {
    case 'pagado':
      return { tono: 'ok', Icono: Check, texto: e.pagado }
    case 'enviado_a_comercio':
      return { tono: 'neutro', Icono: Store, texto: e.enviado }
    case 'preparando':
      return { tono: 'neutro', Icono: PackageOpen, texto: e.preparando }
    case 'listo_retiro':
      return { tono: 'neutro', Icono: PackageCheck, texto: e.listo }
    case 'en_ruta':
      return { tono: 'neutro', Icono: Truck, texto: e.enCamino }
    case 'entregado': {
      const c = enChile(entregadoEn)
      return {
        tono: 'ok',
        Icono: CircleCheck,
        texto: c ? (
          <span className="min-w-0">
            {e.entregadoEl} <span className="cifras">{c.fecha}</span>
          </span>
        ) : (
          e.entregadoEl.replace(/ el$/, '')
        ),
      }
    }
    case 'no_entregado':
      return { tono: 'atenta', Icono: PackageX, texto: e.noEntregado }
    case 'reprogramado':
      return { tono: 'atenta', Icono: CalendarClock, texto: e.reprogramado }
    case 'cancelado_con_devolucion':
      return { tono: 'neutro', Icono: Ban, texto: e.cancelado }
  }
}

/** La palabra, el ícono y la explicación del estado, para quien ve el pago. */
function estadoVisible(f: Pick<FilaPedido, 'estado' | 'entregado_en' | 'devuelto_todo' | 'total'>): EstadoVisible {
  const e = T.estado
  const base = estadoSinExplicacion(f.estado, f.entregado_en)
  switch (f.estado) {
    case 'pagado':
      return { ...base, explicacion: e.pagadoExplicacion }
    case 'no_entregado':
      return { ...base, explicacion: e.noEntregadoExplicacion }
    case 'reprogramado':
      return { ...base, explicacion: e.reprogramadoExplicacion }
    case 'cancelado_con_devolucion':
      // D2: «Devolvimos» cuando la anulación está hecha; mientras sigue en curso, «Estamos devolviendo».
      return {
        ...base,
        explicacion: (
          <>
            {f.devuelto_todo ? e.devolvimosAntes : e.devolviendoAntes} <span className="cifras font-bold">{pesos(f.total)}</span>
            {e.envioIncluidoTarjeta}
          </>
        ),
      }
    default:
      return { ...base, explicacion: null }
  }
}

function EtiquetaEstado({ estado }: { estado: Omit<EstadoVisible, 'explicacion'> }) {
  const { Icono } = estado
  return (
    <Etiqueta tono={estado.tono} className="flex-wrap">
      <Icono aria-hidden className="size-4 shrink-0" />
      {estado.texto}
    </Etiqueta>
  )
}

/** MATU-113 (2.4 y 3.3): la etiqueta del estado sin la explicación, para quien «Se informa». */
export function EtiquetaSinExplicacion({ estado, entregadoEn }: { estado: EstadoFamilia; entregadoEn: string | null }) {
  return <EtiquetaEstado estado={estadoSinExplicacion(estado, entregadoEn)} />
}

// ---------------------------------------------------------------- la pantalla

export function PantallaTusPedidos() {
  const ruta = useRuta()
  const { pedidoElegido } = useFamilia()
  /** 5.6: el retracto recién pedido, para la nota del detalle y su monto (el del `POST`, D7). */
  const [hecho, setHecho] = useState<{ pedidoId: string; retracto: RetractoFamilia } | null>(null)

  // La nota de «Hecho» dura hasta salir de la pantalla: al volver a la lista se olvida.
  useEffect(() => {
    if (ruta === RUTA_TUS_PEDIDOS) setHecho(null)
  }, [ruta])

  if (ruta === RUTA_TUS_PEDIDOS) return <Lista />
  // AppFamilia lleva a la lista sin el pedido en memoria (2.1).
  if (!pedidoElegido) return null
  const recien = hecho && hecho.pedidoId === pedidoElegido.pedidoId ? hecho.retracto : null
  if (ruta === RUTA_ARREPENTIRME)
    return (
      <Arrepentirme
        key={pedidoElegido.pedidoId}
        elegido={pedidoElegido}
        alPedir={(retracto) => {
          setHecho({ pedidoId: pedidoElegido.pedidoId, retracto })
          navegar(RUTA_DETALLE_PEDIDO)
        }}
      />
    )
  return <Detalle key={pedidoElegido.pedidoId} elegido={pedidoElegido} recien={recien} />
}

function Cargando({ className = 'mt-2' }: { className?: string }) {
  const ver = useDemora()
  return (
    <div aria-busy="true" className={className}>
      <p role="status" className="text-lg text-tenue">
        {ver ? GENERAL.cargando : ''}
      </p>
    </div>
  )
}

function ErrorAlTraer({ texto, onReintentar }: { texto: string; onReintentar: () => void }) {
  return (
    <UnaColumna tono="neutro" icono={<CloudOff aria-hidden className="size-9" />}>
      <Anunciado urgencia="alert" como="p" className="max-w-prose text-lg">
        {texto}
      </Anunciado>
      <Boton onClick={onReintentar}>{GENERAL.volverAIntentar}</Boton>
    </UnaColumna>
  )
}

function NoEncontrado() {
  return (
    <UnaColumna tono="neutro" icono={<SearchX aria-hidden className="size-9" />}>
      <p className="max-w-prose text-lg">{T.noEncontrado}</p>
      <Boton variante="secundario" onClick={() => navegar(RUTA_TUS_PEDIDOS)}>
        {T.volverALista}
      </Boton>
    </UnaColumna>
  )
}

// ---------------------------------------------------------------- 3: la lista

type Fila = FilaPedido | FilaObservador
type CargaLista = 'cargando' | 'listo' | 'red' | 'apagado'

/** Junta una página nueva con la que se ve: las filas que ya estaban se actualizan en su lugar. */
function juntar(antes: Fila[], nuevas: Fila[]): Fila[] {
  const porId = new Map(nuevas.map((f) => [f.pedido_id, f]))
  const vistas = new Set(antes.map((f) => f.pedido_id))
  return [...nuevas.filter((f) => !vistas.has(f.pedido_id)), ...antes.map((f) => porId.get(f.pedido_id) ?? f)]
}

function Lista() {
  const { persona, personaId, rol, capa3, fijar, grupoId, elegir } = useFamilia()
  const pila = pilaDe(persona)
  const [carga, setCarga] = useState<CargaLista>(capa3 === false ? 'apagado' : 'cargando')
  const [filas, setFilas] = useState<Fila[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [mas, setMas] = useState<'no' | 'cargando' | 'red'>('no')

  const cargar = useCallback(
    async (silencioso = false) => {
      if (!personaId) return
      if (!silencioso) setCarga('cargando')
      try {
        const r = await listarPedidos(personaId)
        if (capa3 !== true) fijar({ capa3: true })
        if (silencioso) setFilas((antes) => juntar(antes, r.items))
        else {
          setFilas(r.items)
          setCursor(r.siguiente_cursor)
        }
        setCarga('listo')
      } catch (x) {
        if (esVencida(x)) return
        if (silencioso) return
        if (leerFallo(x).status !== 404) return setCarga('red')
        // 3.5: con la capa 3 apagada la ruta no existe. Si el catálogo responde, el 404 es de la
        // persona (de otro grupo, eliminada o quien salió, C1 y C4): se vuelven a pedir las personas.
        try {
          await verCatalogo()
        } catch (y) {
          if (leerFallo(y).status === 404) {
            fijar({ capa3: false })
            return setCarga('apagado')
          }
          return setCarga('red')
        }
        if (grupoId) await elegir(grupoId, null).catch(() => undefined)
        navegar('/', { reemplazar: true })
      }
    },
    [personaId, capa3, fijar, grupoId, elegir],
  )

  useEffect(() => {
    if (capa3 !== false) void cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personaId])

  // 3.5 «Al día»: al volver a la pestaña y cada 60 s mientras algún pedido esté en `pagado`. Sin
  // anunciar y sin mover el foco ni el desplazamiento.
  const enPagado = filas.some((f) => f.estado === 'pagado' && esFilaCompleta(f))
  useEffect(() => {
    if (carga !== 'listo') return
    const alVolver = () => {
      if (document.visibilityState === 'visible') void cargar(true)
    }
    document.addEventListener('visibilitychange', alVolver)
    const reloj = enPagado ? window.setInterval(() => document.visibilityState === 'visible' && void cargar(true), CADA_MS) : undefined
    return () => {
      document.removeEventListener('visibilitychange', alVolver)
      window.clearInterval(reloj)
    }
  }, [carga, enPagado, cargar])

  const verMas = async () => {
    if (!personaId || !cursor || mas === 'cargando') return
    setMas('cargando')
    try {
      const r = await listarPedidos(personaId, cursor)
      const vistas = new Set(filas.map((f) => f.pedido_id))
      const nuevas = r.items.filter((f) => !vistas.has(f.pedido_id))
      setFilas((antes) => [...antes, ...nuevas])
      setCursor(r.siguiente_cursor)
      setMas('no')
      // Al llegar, el foco va a la primera fila nueva, que se lee, sin otro anuncio.
      if (nuevas[0]) enfocar(idFila(nuevas[0].pedido_id), 40)
    } catch (x) {
      if (esVencida(x)) return
      setMas('red')
      anunciar(T.errMas, 'alert')
    }
  }

  const abrir = (f: FilaPedido) => {
    if (!personaId) return
    fijar({ pedidoElegido: { personaId, pedidoId: f.pedido_id, referencia: f.referencia } })
    navegar(RUTA_DETALLE_PEDIDO)
  }

  const observador = filas.some((f) => !esFilaCompleta(f))
  const encabezado = (
    <>
      <PestanasInsumos activa="/insumos/tus-pedidos" />
      <div className="max-w-3xl">
        <Titulo>{T.titulo}</Titulo>
        <p className="mt-1.5 max-w-prose text-base text-tenue">{T.bajada(pila)}</p>
        {carga === 'listo' && observador && <p className="mt-1.5 max-w-prose text-base text-tenue">{T.observador(pila)}</p>}
      </div>
    </>
  )

  let contenido: ReactNode
  if (carga === 'apagado')
    contenido = (
      <UnaColumna tono="neutro" icono={<Store aria-hidden className="size-9" />}>
        <p className="max-w-prose text-lg">{T.apagado}</p>
      </UnaColumna>
    )
  else if (carga === 'cargando') contenido = <Cargando />
  else if (carga === 'red') contenido = <ErrorAlTraer texto={T.errLista} onReintentar={() => void cargar()} />
  else if (!filas.length)
    contenido = (
      <div className="mt-2 flex flex-col items-start gap-3">
        <p className="max-w-prose text-xl font-bold">{T.vacio(pila)}</p>
        {puedeEditar(rol) && (
          <Boton variante="texto" onClick={() => navegar('/insumos/pedido')}>
            {T.irATuPedido}
          </Boton>
        )}
      </div>
    )
  else
    contenido = (
      <div className="mt-2 flex max-w-3xl flex-col items-start gap-4">
        <ul aria-labelledby="titulo-pagina" aria-busy={mas === 'cargando' || undefined} className="flex w-full flex-col gap-3">
          {filas.map((f) => (esFilaCompleta(f) ? <FilaDelPedido key={f.pedido_id} fila={f} onAbrir={() => abrir(f)} /> : <FilaDelObservador key={f.pedido_id} fila={f} />))}
        </ul>
        {cursor && (
          <Boton variante="secundario" ocupado={mas === 'cargando'} textoOcupado={T.cargandoMas} onClick={() => void verMas()}>
            {T.verMas}
          </Boton>
        )}
        {mas === 'red' && <MensajeError>{T.errMas}</MensajeError>}
      </div>
    )

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {encabezado}
      {contenido}
    </div>
  )
}

/**
 * 3.3: la fila de quien ve el pago, un `button` del ancho de la lista que abre el detalle. Su nombre
 * accesible es su texto, en orden. Sin `ChevronRight` ni flecha (DISENO.md 5).
 */
export function FilaDelPedido({ fila: f, onAbrir }: { fila: FilaPedido; onAbrir: () => void }) {
  const estado = estadoVisible(f)
  const dia = enChile(f.pagado_en)?.fecha ?? ''
  const resumen = !f.productos_borrados && f.resumen_productos ? T.masProductos(f.resumen_productos.primero, f.resumen_productos.otros) : null
  return (
    <li className="min-w-0">
      <button
        id={idFila(f.pedido_id)}
        type="button"
        onClick={onAbrir}
        className="grid min-h-12 w-full grid-cols-1 justify-items-start gap-y-1.5 rounded-xl bg-hoja px-4 angosto:px-2 py-3 text-left ring-1 ring-linea hover:ring-borde @2xl/main:grid-cols-[minmax(0,1fr)_auto] @2xl/main:gap-x-6 @2xl/main:gap-y-1"
      >
        <span className="block min-w-0 break-words text-lg font-bold @2xl/main:col-start-1">
          {T.pedidoRef('')}
          <span className="cifras">{f.referencia}</span>
          <Punto />
          <Sep />
          <span className="cifras angosto:block">{dia}</span>
        </span>
        <span className="flex min-w-0 max-w-full flex-col items-start gap-1.5 @2xl/main:col-start-1 @2xl/main:flex-row @2xl/main:flex-wrap @2xl/main:items-baseline @2xl/main:gap-x-3">
          <Sep />
          <EtiquetaEstado estado={estado} />
          {estado.explicacion && (
            <>
              <Sep />
              <span className="block max-w-prose text-base text-tenue">{estado.explicacion}</span>
            </>
          )}
        </span>
        {resumen && (
          <span className="block max-w-prose break-words text-base @2xl/main:col-start-1">
            {estado.explicacion ? <Espacio /> : <Sep />}
            {resumen}
          </span>
        )}
        <span className="block text-base @2xl/main:col-start-2 @2xl/main:row-start-1 @2xl/main:text-right">
          {estado.explicacion && !resumen ? <Espacio /> : <Sep />}
          {T.totalPagado} <span className="cifras font-bold">{pesos(f.total)}</span>
          {f.devuelto > 0 && (
            <>
              <Punto />
              <Sep />
              <span className="angosto:block">
                {T.devuelto} <span className="cifras">{pesos(f.devuelto)}</span>
              </span>
            </>
          )}
        </span>
      </button>
    </li>
  )
}

/**
 * 3.4, corregida por MATU-113 (3.2 y 3.3): la fila de quien «Se informa». «Pagado el {fecha}», el
 * estado real con su ícono y su palabra, sin la explicación, y los productos. Ningún monto. No se abre.
 */
export function FilaDelObservador({ fila: f }: { fila: FilaObservador }) {
  const dia = enChile(f.pagado_en)?.fecha ?? ''
  return (
    <li className="flex min-w-0 flex-col items-start gap-1.5 rounded-xl bg-hoja px-4 angosto:px-2 py-3 ring-1 ring-linea">
      <p className="text-lg font-bold">
        {T.pagadoEl} <span className="cifras">{dia}</span>
      </p>
      <EtiquetaSinExplicacion estado={f.estado} entregadoEn={f.entregado_en} />
      {f.productos_borrados ? (
        <p className="max-w-prose text-base">{T.productosBorrados}</p>
      ) : (
        <ul className="list-disc ps-5 text-base marker:text-tenue">
          {f.productos.map((p) => (
            <li key={p.producto.id} className="break-words">
              <span className="cifras">{p.cantidad}</span> × {p.producto.nombre}
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

/**
 * 2.3 (reemplaza a MATU-62 8): al final de «Pedido», el pedido pagado más reciente, que abre el
 * detalle, y «Ver todos tus pedidos» si hay más de uno. Sin macizo: no compite con «Ver el total».
 */
export function BloqueTusPedidos({ lista }: { lista: ListaPedidos }) {
  const { personaId, fijar } = useFamilia()
  const f = lista.items[0]
  if (!f) return null
  const abrir = (x: FilaPedido) => {
    if (!personaId) return
    fijar({ pedidoElegido: { personaId, pedidoId: x.pedido_id, referencia: x.referencia } })
    navegar(RUTA_DETALLE_PEDIDO)
  }
  return (
    <section aria-labelledby="tus-pedidos-t" className="mt-10 flex flex-col items-start gap-3 border-t border-linea pt-6">
      <h2 id="tus-pedidos-t" className="titular text-2xl">
        {T.titulo}
      </h2>
      <ul aria-labelledby="tus-pedidos-t" className="flex w-full max-w-3xl flex-col gap-3">
        {esFilaCompleta(f) ? <FilaDelPedido fila={f} onAbrir={() => abrir(f)} /> : <FilaDelObservador fila={f} />}
      </ul>
      {(lista.items.length > 1 || lista.siguiente_cursor) && (
        <Boton variante="texto" onClick={() => navegar(RUTA_TUS_PEDIDOS)}>
          {T.verTodos}
        </Boton>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- 4: el detalle

type CargaDetalle = 'cargando' | 'listo' | 'red' | 'no-encontrado'
type NotaDetalle = 'cancelado' | 'ya-cancelado' | 'ya-se-prepara'

function Detalle({ elegido, recien }: { elegido: PedidoElegido; recien: RetractoFamilia | null }) {
  const { pedidoId, referencia } = elegido
  const [carga, setCarga] = useState<CargaDetalle>('cargando')
  const [seg, setSeg] = useState<Seguimiento | null>(null)
  const [pago, setPago] = useState<(PagoVista & { comprobante: Comprobante }) | null>(null)
  const [pagoFalla, setPagoFalla] = useState(false)
  const [reintentandoPago, setReintentandoPago] = useState(false)
  const [retractos, setRetractos] = useState<Retractos | null>(null)
  const [dialogo, setDialogo] = useState(false)
  const [nota, setNota] = useState<NotaDetalle | null>(null)
  const [errCancelar, setErrCancelar] = useState<string>(T.errCancelar)
  /** C8: una clave por intento de cancelar, que se reutiliza si se vuelve a tocar después de un error de red. */
  const claveCancelar = useRef<string | null>(null)

  // 2.1: el `<title>` repite el `h1`.
  useEffect(() => {
    document.title = `${T.pedidoRef(referencia)} · MATU`
  }, [referencia])

  const leerElPago = useCallback(async () => {
    try {
      const p = await leerPago(pedidoId)
      setPago(esPagoCompleto(p) && p.comprobante ? (p as PagoVista & { comprobante: Comprobante }) : null)
      setPagoFalla(false)
    } catch (x) {
      if (esVencida(x)) return
      setPagoFalla(true)
    }
  }, [pedidoId])

  /** El seguimiento y el pago a la vez; los productos para devolver, solo de un pedido entregado. */
  const cargar = useCallback(
    async (silencioso = false) => {
      if (!silencioso) setCarga('cargando')
      const [s] = await Promise.allSettled([leerSeguimiento(pedidoId), leerElPago()])
      if (s.status === 'rejected') {
        if (esVencida(s.reason) || silencioso) return
        return setCarga(leerFallo(s.reason).status === 404 ? 'no-encontrado' : 'red')
      }
      const actual = s.value
      if (actual.entregado_en) {
        try {
          setRetractos(await leerRetractos(pedidoId))
        } catch (x) {
          if (esVencida(x)) return
          // Lo que se pidió devolver no es lo principal del detalle: si no llega, se ve lo demás.
          if (leerFallo(x).status === 404) setRetractos(null)
        }
      } else setRetractos(null)
      setSeg(actual)
      setCarga('listo')
    },
    [pedidoId, leerElPago],
  )

  useEffect(() => {
    void cargar()
  }, [cargar])

  // 4.9 «Al día»: al volver a la pestaña, sin anunciar y sin mover el foco.
  useEffect(() => {
    const alVolver = () => {
      if (document.visibilityState === 'visible' && !dialogo) void cargar(true)
    }
    document.addEventListener('visibilitychange', alVolver)
    return () => document.removeEventListener('visibilitychange', alVolver)
  }, [cargar, dialogo])

  // 6.3: las notas de cancelar reciben el foco cuando ya se pintaron con lo nuevo; nunca queda en `body`.
  useEffect(() => {
    if (nota) enfocar(ID_NOTA_DETALLE, 60)
  }, [nota])

  // P1-4 (y 4.1, 5.6): el `h1` de «Cargando» se reemplaza por el del detalle cuando termina la lectura
  // (seguimiento, pago y retractos). Si el foco quedó ahí o cayó al `body`, lo recibe el `h1` nuevo.
  const cargaAntes = useRef<CargaDetalle>(carga)
  useEffect(() => {
    const venia = cargaAntes.current
    cargaAntes.current = carga
    if (venia !== 'cargando' || carga === 'cargando') return
    const activo = document.activeElement
    if (activo === null || activo === document.body || activo.id === 'titulo-pagina' || !activo.isConnected) enfocar('titulo-pagina', 0)
  }, [carga])

  const reintentarPago = async () => {
    if (reintentandoPago) return
    setReintentandoPago(true)
    await leerElPago()
    setReintentandoPago(false)
  }

  /** Lo que vale después de un resultado del servidor: vuelve a leer y muestra la nota. */
  const despues = async (n: NotaDetalle) => {
    claveCancelar.current = null
    await cargar(true)
    setDialogo(false)
    setNota(n)
  }

  /** 6.3: sin interfaz optimista. `true` si el diálogo se cierra. */
  const confirmarCancelar = async (): Promise<boolean> => {
    const clave = claveCancelar.current ?? (claveCancelar.current = nuevaClave())
    try {
      await cancelarConDevolucion(pedidoId, clave)
      await despues('cancelado')
      return true
    } catch (x) {
      if (esVencida(x)) return true
      const f = leerFallo(x)
      if (f.status === 409 && esTipo(f.tipo, 'estado-pedido')) return await despues('ya-cancelado'), true
      if (f.status === 409 && esTipo(f.tipo, 'ya-se-prepara')) return await despues('ya-se-prepara'), true
      if (f.status === 403 || f.status === 404) {
        claveCancelar.current = null
        setDialogo(false)
        setCarga('no-encontrado')
        return true
      }
      // Red, 5xx o la misma clave todavía en curso: antes de decir algo, se vuelve a leer el pedido.
      try {
        const s = await leerSeguimiento(pedidoId)
        if (s.estado === 'cancelado_con_devolucion') return await despues('cancelado'), true
        setErrCancelar(T.errCancelar)
      } catch (y) {
        if (esVencida(y)) return true
        setErrCancelar(T.errCancelarSinLeer)
      }
      return false
    }
  }

  const encabezadoCorto = (
    <>
      <PestanasInsumos activa="/insumos/tus-pedidos" />
      <Volver onClick={() => navegar(RUTA_TUS_PEDIDOS)}>{T.volverALista}</Volver>
      <Titulo>
        {T.pedidoRef('')}
        <span className="cifras">{referencia}</span>
      </Titulo>
    </>
  )

  if (carga === 'cargando' || !seg)
    return (
      <div className="flex min-w-0 flex-col gap-3">
        {encabezadoCorto}
        {carga === 'red' ? <ErrorAlTraer texto={T.errDetalle} onReintentar={() => void cargar()} /> : carga === 'no-encontrado' ? <NoEncontrado /> : <Cargando />}
      </div>
    )
  if (carga === 'red' || carga === 'no-encontrado')
    return (
      <div className="flex min-w-0 flex-col gap-3">
        {encabezadoCorto}
        {carga === 'red' ? <ErrorAlTraer texto={T.errDetalle} onReintentar={() => void cargar()} /> : <NoEncontrado />}
      </div>
    )

  const estado = estadoVisible(seg)
  const pagadoEl = enChile(seg.pagado_en)
  const c = pago?.comprobante ?? null
  const devoluciones = (pago?.devoluciones ?? []).filter((d) => d.motivo !== 'pago_tardio')
  const pedidas = conRecien(retractos?.retractos ?? [], recien)
  const notaVista = recien ? (
    <Nota id={ID_NOTA_DETALLE} tono="ok" rol="status" enfocable className="animate-aparecer">
      <p>{T.hechoRetracto}</p>
    </Nota>
  ) : nota === 'cancelado' ? (
    <Nota id={ID_NOTA_DETALLE} tono="ok" rol="status" enfocable className="animate-aparecer">
      <p>
        {T.canceladoAntes} <span className="cifras font-bold">{pesos(seg.total)}</span> {T.canceladoDespues}
      </p>
    </Nota>
  ) : nota === 'ya-cancelado' ? (
    <Nota id={ID_NOTA_DETALLE} tono="rocio" rol="status" enfocable className="animate-aparecer">
      <p>{T.yaCancelado}</p>
    </Nota>
  ) : nota === 'ya-se-prepara' ? (
    <Nota id={ID_NOTA_DETALLE} tono="atenta" rol="alert" enfocable className="animate-aparecer">
      <p>{T.yaSePrepara}</p>
    </Nota>
  ) : null

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <PestanasInsumos activa="/insumos/tus-pedidos" />
      <Volver onClick={() => navegar(RUTA_TUS_PEDIDOS)}>{T.volverALista}</Volver>
      <div className="flex min-w-0 flex-col items-start gap-3">
        <Titulo>
          {T.pedidoRef('')}
          <span className="cifras">{seg.referencia}</span>
        </Titulo>
        <div className="flex flex-col items-start gap-2 @xl/main:flex-row @xl/main:flex-wrap @xl/main:items-center @xl/main:gap-x-4">
          {pagadoEl && (
            <p className="text-base text-tenue">
              {T.pagadoEl} <span className="cifras">{pagadoEl.fecha}</span> {T.aLas} <span className="cifras">{pagadoEl.hora}</span>
            </p>
          )}
          <EtiquetaEstado estado={estado} />
        </div>
        {estado.explicacion && <p className="max-w-prose text-lg">{estado.explicacion}</p>}
        {notaVista}
        {c?.precios_de_ejemplo && <AvisoPiloto />}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-x-10 gap-y-10 @3xl/main:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="flex min-w-0 flex-col gap-10 @3xl/main:col-start-1 @3xl/main:row-start-1">
          <ComoVa seg={seg} />
          {devoluciones.length > 0 && <DineroDevuelto devoluciones={devoluciones} seg={seg} />}
          {pedidas.length > 0 && <ParaDevolver retractos={pedidas} />}
          <BloqueArrepentirme seg={seg} retractos={retractos} />
          <BloqueCancelar seg={seg} onAbrir={() => setDialogo(true)} />
        </div>
        {/* 4.8: el comprobante va al final del DOM y, desde @3xl/main, a la derecha y pegajoso. */}
        <div className="flex min-w-0 flex-col gap-10 @3xl/main:col-start-2 @3xl/main:row-start-1 @3xl/main:sticky @3xl/main:top-6 @3xl/main:max-h-[calc(100dvh-3rem)] @3xl/main:self-start @3xl/main:overflow-y-auto [scrollbar-width:thin]">
          {c ? (
            <>
              <ComprobanteBoleta c={c} />
              <DatosDelPedido c={c} />
              <Garantias c={c} />
              <Acciones className="angosto:flex-col angosto:items-stretch">
                <Boton variante="secundario" icono={<Printer aria-hidden className="size-5 shrink-0" />} onClick={() => window.print()}>
                  {PAGO.imprimir}
                </Boton>
              </Acciones>
              <HojaComprobante c={c} />
            </>
          ) : (
            pagoFalla && (
              <Nota tono="atenta" icono={<CloudOff aria-hidden className="mt-0.5 size-5 shrink-0 text-atenta" />}>
                <Anunciado urgencia="alert" como="p">
                  {T.errComprobante} {T.errComprobanteDevuelto}
                </Anunciado>
                <Boton variante="secundario" className="mt-3" ocupado={reintentandoPago} textoOcupado={GENERAL.cargando} onClick={() => void reintentarPago()}>
                  {GENERAL.volverAIntentar}
                </Boton>
              </Nota>
            )
          )}
        </div>
      </div>

      {dialogo && (
        <DialogoConfirmar
          titulo={T.cancelarPregunta}
          texto={
            <>
              {T.cancelarMontoAntes} <span className="cifras font-bold">{pesos(seg.total)}</span>
              {T.cancelarMontoDespues}
            </>
          }
          nota={pago?.pago_de_prueba ? T.selloPrueba : undefined}
          confirmar={T.cancelar}
          confirmando={T.cancelando}
          seguir={T.seguir}
          error={errCancelar}
          onConfirmar={confirmarCancelar}
          onCerrar={() => {
            setDialogo(false)
            enfocar(ID_CANCELAR, 0)
          }}
        />
      )}
    </div>
  )
}

/** El retracto recién pedido manda con su monto (el del `POST`, D7), aunque la lectura no lo traiga todavía. */
function conRecien(lista: RetractoFamilia[], recien: RetractoFamilia | null): RetractoFamilia[] {
  if (!recien) return lista
  return lista.some((r) => r.id === recien.id) ? lista.map((r) => (r.id === recien.id ? recien : r)) : [recien, ...lista]
}

// ---------------------------------------------------------------- 4.3 cómo va

const ESTADO_PARTE: Record<ParteDelPedido['estado'], { Icono: LucideIcon; texto: string }> = {
  enviada: { Icono: Store, texto: T.parte.enviada },
  preparando: { Icono: PackageOpen, texto: T.parte.preparando },
  lista: { Icono: PackageCheck, texto: T.parte.lista },
  retirada: { Icono: PackageCheck, texto: T.parte.retirada },
  cancelada: { Icono: Ban, texto: T.parte.cancelada },
}

function ComoVa({ seg }: { seg: Seguimiento }) {
  if (!seg.productos_borrados && !seg.partes.length) return null
  return (
    <section aria-labelledby="como-va-t" className="flex min-w-0 flex-col gap-3">
      <h2 id="como-va-t" className="titular text-2xl">
        {T.comoVa}
      </h2>
      {seg.productos_borrados ? (
        <p className="max-w-prose text-lg">{T.productosBorrados}</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {seg.partes.map((p, i) => {
            const e = p.estado === 'cancelada' && p.cancelada_por === 'faltante' ? { Icono: PackageX, texto: T.parte.faltante } : ESTADO_PARTE[p.estado]
            return (
              <li key={`${p.comercio.nombre_fantasia ?? 'comercio'}-${i}`} className="flex min-w-0 flex-col items-start gap-2 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea">
                <h3 className="max-w-full break-words text-lg font-bold">
                  {p.comercio.nombre_fantasia ? T.de(p.comercio.nombre_fantasia) : T.deUnComercio}
                  {p.comercio.ficticio && (
                    <>
                      {' '}
                      <span className="inline-block">{T.ficticio}</span>
                    </>
                  )}
                  <span className="sr-only">:</span>
                </h3>
                <Etiqueta tono="neutro">
                  <e.Icono aria-hidden className="size-4 shrink-0" />
                  {e.texto}
                </Etiqueta>
                <ul className="w-full divide-y divide-linea">
                  {p.lineas.map((l) => (
                    <li key={l.linea_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-base">
                      <span className="min-w-0 break-words">
                        <span className="cifras">{l.cantidad}</span> × {l.producto.nombre}
                      </span>
                      {l.unidades_faltantes > 0 && (
                        <Etiqueta tono="neutro">
                          <PackageX aria-hidden className="size-4 shrink-0" />
                          {T.faltaron(l.unidades_faltantes)}
                        </Etiqueta>
                      )}
                    </li>
                  ))}
                </ul>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- 4.4 dinero devuelto

/** Cuántas unidades faltaron de un producto, según las partes (`unidades_faltantes`). */
function faltaronDe(seg: Seguimiento, productoId: string): number {
  return seg.partes.flatMap((p) => p.lineas).find((l) => l.producto.id === productoId && l.unidades_faltantes > 0)?.unidades_faltantes ?? 0
}

/**
 * La frase de una devolución (4.4). «a tu tarjeta terminada en {ultimos4}» solo si `ultimos4` llega,
 * o sea, solo para quien pagó (C17). Si no llega, la columna de quien no pagó. No hay otra regla.
 */
function FraseDevolucion({ d, seg }: { d: Devolucion; seg: Seguimiento }) {
  const monto = <span className="cifras font-bold">{pesos(d.monto)}</span>
  const u4 = d.ultimos4
  const tarjeta = u4 ? (
    <>
      {T.aTuTarjeta} <span className="cifras">{u4}</span>
    </>
  ) : (
    T.aLaTarjeta
  )
  const banco = u4 ? T.cuandoTuBanco : T.cuandoElBanco
  if (d.estado === 'en_curso')
    return (
      <>
        {T.estamosDevolviendo} {monto} {u4 ? T.aTuTarjetaSola : `${T.aLaTarjeta}.`} {u4 ? T.enCursoTuya : T.enCursoAjena}
      </>
    )
  if (d.motivo === 'cancelacion')
    return (
      <>
        {T.devolvimos} {monto} {tarjeta}, {T.porTodo}. {banco}
      </>
    )
  if (!d.producto)
    return (
      <>
        {T.devolvimosEnvio} {monto}.
      </>
    )
  const faltaron = d.motivo === 'producto_no_entregado' ? faltaronDe(seg, d.producto.id) : 0
  if (faltaron > 0)
    return (
      <>
        {T.faltaronDe(faltaron, d.producto.nombre)} {u4 ? T.teDevolvimos : T.devolvimos} {monto} {tarjeta}. {banco}
      </>
    )
  return (
    <>
      {T.devolvimos} {monto} {tarjeta}, {T.porProducto(d.producto.nombre)}. {banco}
    </>
  )
}

function DineroDevuelto({ devoluciones, seg }: { devoluciones: Devolucion[]; seg: Seguimiento }) {
  return (
    <section aria-labelledby="devuelto-t" className="flex min-w-0 flex-col gap-3">
      <h2 id="devuelto-t" className="titular text-2xl">
        {T.dineroDevuelto}
      </h2>
      <ul className="divide-y divide-linea border-y border-linea">
        {devoluciones.map((d) => {
          const hecha = d.estado === 'hecha'
          const cuando = hecha ? enChile(d.hecha_en) : null
          return (
            <li key={`${d.solicitada_en}-${d.monto}-${d.producto?.id ?? d.motivo}`} className="flex max-w-prose gap-3 py-3 text-base">
              <Undo2 aria-hidden className={`mt-0.5 size-5 shrink-0 ${hecha ? 'text-ok' : 'text-atenta'}`} />
              <div className="min-w-0">
                <p className="break-words">
                  <FraseDevolucion d={d} seg={seg} />
                </p>
                {cuando && (
                  <p className="text-base text-tenue">
                    {T.el} <span className="cifras">{cuando.fecha}</span>
                  </p>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// ---------------------------------------------------------------- 4.5 productos para devolver

function ParaDevolver({ retractos }: { retractos: RetractoFamilia[] }) {
  return (
    <section aria-labelledby="para-devolver-t" className="flex min-w-0 flex-col gap-3">
      <h2 id="para-devolver-t" className="titular text-2xl">
        {T.paraDevolver}
      </h2>
      <ul className="flex flex-col gap-3">
        {retractos.map((r) => {
          const resuelto = enChile(r.resuelto_en)
          return (
            <li key={r.id} className="flex min-w-0 flex-col items-start gap-2 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea">
              {r.estado === 'solicitado' ? (
                <Etiqueta tono="neutro">
                  <Clock aria-hidden className="size-4 shrink-0" />
                  {T.devolucionPedida}
                </Etiqueta>
              ) : r.estado === 'devuelto' ? (
                <Etiqueta tono="ok" className="flex-wrap">
                  <CircleCheck aria-hidden className="size-4 shrink-0" />
                  <span className="min-w-0">
                    {resuelto ? (
                      <>
                        {T.devueltoEl} <span className="cifras">{resuelto.fecha}</span>
                      </>
                    ) : (
                      T.devueltoEl.replace(/ el$/, '')
                    )}
                  </span>
                </Etiqueta>
              ) : (
                // La palabra del contrato para este estado nunca se muestra (C26).
                <Etiqueta tono="neutro">
                  <CircleX aria-hidden className="size-4 shrink-0" />
                  {T.noSeAcepto}
                </Etiqueta>
              )}
              <ul className="text-base">
                {r.lineas.map((l) => (
                  <li key={l.linea_id} className="break-words">
                    <span className="cifras">{l.cantidad}</span> × {l.producto.nombre}
                  </li>
                ))}
              </ul>
              {r.estado === 'solicitado' && (
                <p className="max-w-prose text-base">
                  {T.teDevolvemos} <span className="cifras font-bold">{pesos(r.monto)}</span>
                  {r.incluye_envio ? `${T.envioIncluido} ` : ' '}
                  {T.cuandoRecibamos}
                </p>
              )}
              {r.estado === 'rechazado' && r.motivo_rechazo && <p className="max-w-prose text-base">{T.motivoRechazo[r.motivo_rechazo]}</p>}
              {r.estado === 'rechazado' && (
                <p className="max-w-prose text-base">
                  {T.siTienesDudas} <EnlaceEnFrase href={mailto} className="[overflow-wrap:anywhere]">
          {CORREO_CONTACTO}
        </EnlaceEnFrase>.
                </p>
              )}
              {!r.es_tuyo && <p className="max-w-prose text-base text-tenue">{T.laPidioOtra}</p>}
              {r.origen === 'correo' && <p className="max-w-prose text-base text-tenue">{r.es_tuyo ? T.porCorreoTuya : T.porCorreoAjena}</p>}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// ---------------------------------------------------------------- 4.6 lo que se puede hacer

/** «hasta el 18/11/2026» y, si el plazo no vence a las 23:59, «a las 18:00» (O6). */
function FechaDelPlazo({ iso }: { iso: string | null }) {
  const p = plazoEnChile(iso)
  if (!p) return null
  return (
    <>
      <span className="cifras">{p.fecha}</span>
      {p.hora && (
        <>
          {' '}
          {T.aLas} <span className="cifras">{p.hora}</span>
        </>
      )}
    </>
  )
}

/** 4.6.1: con el motivo que dice el servidor (O1, D6). `sin_entregar` no muestra nada. */
function BloqueArrepentirme({ seg, retractos }: { seg: Seguimiento; retractos: Retractos | null }) {
  const motivo = seg.arrepentirse_motivo
  if (!seg.puede_arrepentirse && (motivo === null || motivo === 'sin_entregar')) return null
  let cuerpo: ReactNode
  if (seg.puede_arrepentirse)
    cuerpo = (
      <>
        <p className="max-w-prose text-base">
          {T.puedesHastaAntes} <FechaDelPlazo iso={seg.plazo_hasta} />. {T.puedesHastaDespues}
          {retractos?.incluye_envio_si_todo && ` ${T.siDevuelvesTodo}`}
        </p>
        <Boton variante="secundario" onClick={() => navegar(RUTA_ARREPENTIRME)}>
          {T.arrepentirme}
        </Boton>
      </>
    )
  else if (motivo === 'rol') cuerpo = <p className="max-w-prose text-base">{T.arrepentirseRol}</p>
  else if (motivo === 'nada_disponible') cuerpo = <p className="max-w-prose text-base">{T.nadaDisponible}</p>
  else
    cuerpo = (
      <p className="max-w-prose text-base">
        {/* C22 (H1 del cierre): el plazo de la app termina en `plazo_hasta`; el del correo, a los 90 días (`plazo_correo_hasta`). */}
        {motivo === 'plazo_app_vencido' ? T.plazoAppAntes : T.plazoAntes} <FechaDelPlazo iso={motivo === 'plazo_app_vencido' ? seg.plazo_hasta : seg.plazo_correo_hasta} />. {motivo === 'plazo_app_vencido' ? T.plazoAppDespues : T.plazoDespues}{' '}
        <EnlaceEnFrase href={mailto} className="[overflow-wrap:anywhere]">
          {CORREO_CONTACTO}
        </EnlaceEnFrase>.
      </p>
    )
  return (
    <section aria-labelledby="arrepentirme-t" className="flex min-w-0 flex-col items-start gap-3">
      <h2 id="arrepentirme-t" className="titular max-w-full text-2xl angosto:text-xl [overflow-wrap:anywhere]">
        {T.arrepentirme}
      </h2>
      {cuerpo}
    </section>
  )
}

/** 4.6.2: solo con `puede_cancelar` (C10). `ya_se_prepara` y `cancelado` no muestran nada: lo dice el estado. */
function BloqueCancelar({ seg, onAbrir }: { seg: Seguimiento; onAbrir: () => void }) {
  if (!seg.puede_cancelar && seg.cancelar_motivo !== 'rol') return null
  return (
    <section aria-labelledby="cancelar-t" className="flex min-w-0 flex-col items-start gap-3">
      <h2 id="cancelar-t" className="titular max-w-full text-2xl angosto:text-xl [overflow-wrap:anywhere]">
        {T.cancelar}
      </h2>
      {seg.puede_cancelar ? (
        <>
          <p className="max-w-prose text-base">{T.puedesCancelar}</p>
          <Boton id={ID_CANCELAR} variante="peligro" onClick={onAbrir}>
            {T.cancelar}
          </Boton>
        </>
      ) : (
        <p className="max-w-prose text-base">{T.cancelarRol}</p>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- 5: arrepentirme de la compra

type CargaRetracto = 'cargando' | 'listo' | 'red' | 'no-encontrado'

function Arrepentirme({ elegido, alPedir }: { elegido: PedidoElegido; alPedir: (r: RetractoFamilia) => void }) {
  const { pedidoId, referencia } = elegido
  const [carga, setCarga] = useState<CargaRetracto>('cargando')
  const [datos, setDatos] = useState<Retractos | null>(null)
  const [cant, setCant] = useState<Elegidas>({})
  const [errores, setErrores] = useState<Record<string, string>>({})
  const [errGeneral, setErrGeneral] = useState<'nada' | 'red' | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [yaSePidio, setYaSePidio] = useState(false)
  /** C8: una clave por intento. Se reutiliza en el reintento y se olvida si cambia lo elegido. */
  const clave = useRef<string | null>(null)
  const volver = () => navegar(RUTA_DETALLE_PEDIDO)

  /** Lee lo que se puede devolver. Sin `puede_arrepentirse`, el detalle lo explica (5.8). */
  const leer = useCallback(async (): Promise<Retractos | null> => {
    const r = await leerRetractos(pedidoId)
    if (!r.puede_arrepentirse || !r.lineas.some((l) => l.disponibles > 0)) {
      navegar(RUTA_DETALLE_PEDIDO, { reemplazar: true })
      return null
    }
    setDatos(r)
    return r
  }, [pedidoId])

  const cargar = useCallback(async () => {
    setCarga('cargando')
    try {
      const r = await leer()
      if (!r) return
      setCant(bajarAlDisponible(r.lineas, {}))
      setCarga('listo')
    } catch (x) {
      if (esVencida(x)) return
      setCarga(leerFallo(x).status === 404 ? 'no-encontrado' : 'red')
    }
  }, [leer])

  useEffect(() => {
    void cargar()
  }, [cargar])

  // 5.7: la nota recibe el foco cuando ya se pintó.
  useEffect(() => {
    if (yaSePidio) enfocar(ID_YA_SE_PIDIO, 60)
  }, [yaSePidio])

  const cambiar = (lineaId: string, v: string) => {
    if (enviando) return
    clave.current = null
    setCant((c) => ({ ...c, [lineaId]: v }))
    if (errores[lineaId]) setErrores(({ [lineaId]: _, ...resto }) => resto)
    if (errGeneral) setErrGeneral(null)
  }

  const revisarCampo = (lineaId: string) => {
    const l = datos?.lineas.find((x) => x.linea_id === lineaId)
    if (l && fueraDeRango(l, cant[lineaId])) setErrores((e) => ({ ...e, [lineaId]: T.errRango(l.disponibles) }))
  }

  /** 5.7: otra persona pidió devolver algunos de los mismos productos. Se baja lo elegido y se avisa. */
  const yaPedido = async () => {
    clave.current = null
    try {
      const r = await leer()
      if (!r) return
      setCant((c) => bajarAlDisponible(r.lineas, c))
      setErrores({})
      setYaSePidio(false)
      window.setTimeout(() => setYaSePidio(true), 0)
    } catch (x) {
      if (esVencida(x)) return
      setErrGeneral('red')
      anunciar(T.errRetracto, 'alert')
    }
  }

  const enviar = async () => {
    if (enviando || !datos) return
    const conDisponible = datos.lineas.filter((l) => l.disponibles > 0)
    const errs: Record<string, string> = {}
    for (const l of conDisponible) if (fueraDeRango(l, cant[l.linea_id])) errs[l.linea_id] = T.errRango(l.disponibles)
    setErrores(errs)
    const conError = conDisponible.find((l) => errs[l.linea_id])
    if (conError) {
      setErrGeneral(null)
      return void enfocar(idCampo(conError.linea_id), 0)
    }
    const lista = elegidas(datos.lineas, cant)
    if (!lista.length) {
      setErrGeneral('nada')
      anunciar(T.errNadaElegido, 'alert')
      if (conDisponible[0]) enfocar(idCampo(conDisponible[0].linea_id), 0)
      return
    }
    const k = clave.current ?? (clave.current = nuevaClave())
    setEnviando(true)
    setErrGeneral(null)
    try {
      const r = await pedirRetracto(
        pedidoId,
        lista.map((e) => ({ linea_id: e.linea.linea_id, cantidad: e.cantidad })),
        k,
      )
      clave.current = null
      alPedir(r)
    } catch (x) {
      if (esVencida(x)) return
      const f = leerFallo(x)
      if (f.status === 404) {
        clave.current = null
        return setCarga('no-encontrado')
      }
      // El plazo venció mientras elegía: el detalle muestra 4.6.1 con lo que diga el servidor.
      if (f.status === 409 && esTipo(f.tipo, 'fuera-de-plazo')) {
        clave.current = null
        return volver()
      }
      // Ya se pidió (C8): el contrato responde 422 `producto-no-retractable` cuando otra solicitud ganó
      // la carrera. Un 409 que no es del plazo ni de la clave en curso se trata igual.
      if ((f.status === 422 && esTipo(f.tipo, 'producto-no-retractable')) || (f.status === 409 && !esTipo(f.tipo, 'idempotencia-en-curso'))) return void (await yaPedido())
      // Red, 5xx o la misma clave todavía en curso: lo elegido sigue aquí y la clave se reutiliza.
      setErrGeneral('red')
      anunciar(T.errRetracto, 'alert')
    } finally {
      setEnviando(false)
    }
  }

  const encabezado = (
    <>
      <PestanasInsumos activa="/insumos/tus-pedidos" />
      <Volver onClick={volver}>{T.volverAlPedido(referencia)}</Volver>
      <div className="max-w-3xl">
        <Titulo>{T.arrepentirme}</Titulo>
        {datos && carga === 'listo' && (
          <p className="mt-1.5 max-w-prose text-lg">
            {T.puedesHastaAntes} <FechaDelPlazo iso={datos.plazo_hasta} />. {T.puedesHastaDespues}
            {datos.incluye_envio_si_todo && ` ${T.siDevuelvesTodo}`}
          </p>
        )}
      </div>
    </>
  )

  if (carga !== 'listo' || !datos)
    return (
      <div className="flex min-w-0 flex-col gap-3">
        {encabezado}
        {carga === 'red' ? <ErrorAlTraer texto={T.errDetalle} onReintentar={() => void cargar()} /> : carga === 'no-encontrado' ? <NoEncontrado /> : <Cargando />}
      </div>
    )

  const previa = vistaPrevia(datos, cant)
  const lista = elegidas(datos.lineas, cant)
  const pierde = lista.some((e) => e.linea.retracto_pierde_al_abrir)

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {encabezado}
      <div className="mt-4 grid grid-cols-1 gap-x-10 gap-y-8 @3xl/main:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-labelledby="elige-t" className="flex min-w-0 flex-col gap-3">
          {yaSePidio && (
            <Nota id={ID_YA_SE_PIDIO} tono="atenta" rol="alert" enfocable className="animate-aparecer">
              <p>
                <strong className="font-bold">{T.yaSePidio}</strong> {T.yaSePidioResto}
              </p>
            </Nota>
          )}
          <h2 id="elige-t" className="text-xl font-bold">
            {T.elige}
          </h2>
          <ul className="flex flex-col gap-3">
            {/* P2-1: lo que no se recibió no se puede devolver, y no se muestra. */}
            {datos.lineas.filter((l) => l.entregadas > 0).map((l) => {
              const id = idCampo(l.linea_id)
              return (
                <li key={l.linea_id} className="grid min-w-0 grid-cols-1 gap-y-3 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea">
                  <h3 id={`${id}-p`} className="break-words text-xl font-bold">
                    {l.producto.nombre}
                  </h3>
                  <p className="text-base tabular-nums">
                    {T.recibiste} {l.entregadas}. {T.pagaste} {pesos(l.precio_pagado)} {T.cadaUno}
                  </p>
                  {l.retracto_pierde_al_abrir && <p className="max-w-prose text-lg font-bold">{T.sello}</p>}
                  {l.ya_pedidas > 0 && <p className="text-base text-tenue">{T.yaSePidioN(l.ya_pedidas)}</p>}
                  {l.disponibles > 0 ? (
                    <div className="flex min-w-0 flex-col gap-1.5">
                      <Stepper
                        id={id}
                        etiqueta={T.cuantos}
                        valor={cant[l.linea_id] ?? '0'}
                        onCambio={(v) => cambiar(l.linea_id, v)}
                        min={0}
                        max={l.disponibles}
                        error={errores[l.linea_id] ?? null}
                        nombradoPor={`${id}-p`}
                        textoMenos={T.unoMenos(l.producto.nombre)}
                        textoMas={T.unoMas(l.producto.nombre)}
                        soloLectura={enviando}
                        describe={`${id}-h`}
                        seleccionarAlEnfocar
                        onSalir={() => revisarCampo(l.linea_id)}
                      />
                      <p id={`${id}-h`} className="text-base text-tenue">
                        {T.hasta(l.disponibles)}
                      </p>
                    </div>
                  ) : (
                    <p className="text-base">{T.yaTodos}</p>
                  )}
                </li>
              )
            })}
          </ul>
        </section>

        <div className="flex min-w-0 flex-col items-start gap-4 @3xl/main:sticky @3xl/main:top-6 @3xl/main:self-start">
          {/* 5.4: el contenedor de la boleta de MATU-61 9.4. Cambia sin región viva: el campo ya dice el número. */}
          <section
            aria-labelledby="lo-que-vas-t"
            className="relative w-full rounded-t-lg bg-hoja px-4 angosto:px-2 @3xl/main:px-7 pt-5 pb-8 ring-1 ring-linea [mask:radial-gradient(circle_at_50%_100%,transparent_0.42rem,var(--color-tinta)_0.45rem)_bottom/1.1rem_100%_repeat-x]"
          >
            <h2 id="lo-que-vas-t" className="mb-3 text-xl font-bold">
              {T.loQueVas}
            </h2>
            {lista.length === 0 ? (
              <p className="text-lg text-tenue">{T.nadaElegido}</p>
            ) : (
              <div className="flex flex-col gap-3">
                <p className="text-lg font-bold">{T.vasADevolver}</p>
                <ul className="list-disc ps-5 text-lg marker:text-tenue">
                  {lista.map((e) => (
                    <li key={e.linea.linea_id} className="break-words">
                      <span className="cifras">{e.cantidad}</span> × {e.linea.producto.nombre}
                    </li>
                  ))}
                </ul>
                <p className="max-w-prose text-lg">
                  {T.teDevolvemos} <span className="cifras font-bold">{pesos(previa.total)}</span>
                  {previa.conEnvio ? `${T.envioIncluido} ` : ' '}
                  {T.cuandoRecibamos}
                </p>
                {pierde && <p className="text-lg font-bold">{T.sello}</p>}
              </div>
            )}
          </section>
          {errGeneral && <MensajeError>{errGeneral === 'nada' ? T.errNadaElegido : T.errRetracto}</MensajeError>}
          <Acciones className="angosto:flex-col angosto:items-stretch">
            <Boton ocupado={enviando} textoOcupado={T.enviando} onClick={() => void enviar()}>
              {T.devolverEstos}
            </Boton>
            <Boton variante="texto" onClick={volver}>
              {T.noVolver}
            </Boton>
          </Acciones>
        </div>
      </div>
    </div>
  )
}

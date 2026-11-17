// Pedidos (especificación MATU-81, sección 5) y un pedido (6): las dos rutas son una sola pantalla.
// La lista se conserva al elegir uno, y en pantalla ancha la cola queda a la izquierda del detalle.
// Buscar es un POST con la referencia en el cuerpo (C7), y con un resultado no se abre solo: abrir un
// pedido queda registrado (C9) y eso lo decide quien opera. La lista no se audita.
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Search } from 'lucide-react'
import { buscarPedido, listarPedidos, type GrupoPedidos, type PedidoOperacion } from '../compartido/api/operacion'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { useDemora } from '../compartido/useDemora'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { navegar } from '../familia/ruteo'
import { GrupoOpciones, MensajeError, Titulo } from '../familia/ui'
import { Atencion, CUADRO_DETALLE, CUADRO_VACIO, enChile, EtiquetaPedido, FilaCola, GRILLA, Monto, palabraPedido, pesos, useAhora, useAlDia } from './comun'
import { useOperacion } from './estado'
import { AvisoPrivacidad, RotuloPiloto } from './Marco'
import { DetallePedido } from './Pedido'
import { MARCO, PEDIDOS as T } from './textos'

const CHIPS: { valor: GrupoPedidos; texto: string }[] = [
  { valor: 'por_atender', texto: T.porAtender },
  { valor: 'en_camino', texto: T.enCamino },
  { valor: 'con_problema', texto: T.conProblema },
  { valor: 'cerrados', texto: T.cerrados },
  { valor: 'cancelados', texto: T.cancelados },
  { valor: 'todos', texto: T.todos },
]
const POR_PAGINA = 20

const atencion = (p: PedidoOperacion) => p.incidencia_abierta || p.devolucion_sin_terminar
const t = (iso: string) => new Date(iso).getTime()

/** 5.3: lo que pide atención primero, después el pago más antiguo; en Cerrados y Cancelados, el más reciente. */
export function ordenarPedidos(grupo: GrupoPedidos, lista: PedidoOperacion[]) {
  const recientes = grupo === 'cerrados' || grupo === 'cancelados'
  return [...lista].sort((a, b) => {
    if (atencion(a) !== atencion(b)) return atencion(a) ? -1 : 1
    return recientes ? t(b.pagado_en) - t(a.pagado_en) : t(a.pagado_en) - t(b.pagado_en)
  })
}

export function PantallaPedidos({ ruta }: { ruta: '/operacion' | '/operacion/pedido' }) {
  const { pedidoId, fijar, fallo } = useOperacion()
  const [grupo, setGrupo] = useState<GrupoPedidos>('por_atender')
  const [lista, setLista] = useState<PedidoOperacion[] | null>(null)
  const [actualizado, setActualizado] = useState<string | null>(null)
  const [error, setError] = useState(false)
  const [actualizando, setActualizando] = useState(false)
  const [referencia, setReferencia] = useState('')
  const [vacio, setVacio] = useState(false)
  const [buscando, setBuscando] = useState(false)
  const [busqueda, setBusqueda] = useState<{ ref: string; pedidos: PedidoOperacion[]; n: number } | null>(null)
  const [visibles, setVisibles] = useState(POR_PAGINA)
  const { ahora, fijarFecha } = useAhora()
  const verCargando = useDemora(1000)
  const enPedido = ruta === '/operacion/pedido'

  const traer = useCallback(async () => {
    try {
      const r = await listarPedidos(grupo)
      fijarFecha(r.fecha)
      setLista(r.pedidos)
      setActualizado(fechaYHoraDeChile(ahora()).hora)
      setError(false)
    } catch (x) {
      if (fallo(x, true)) return
      setError(true)
    }
  }, [grupo, fijarFecha, ahora, fallo])

  useEffect(() => {
    void traer()
  }, [traer])
  // 5.6: una búsqueda no se refresca sola.
  useAlDia(() => void traer(), !busqueda)

  const actualizar = async () => {
    setActualizando(true)
    await traer()
    setActualizando(false)
  }

  const buscar = async (e: FormEvent) => {
    e.preventDefault()
    if (buscando) return
    const ref = referencia.trim()
    if (!ref) return setVacio(true)
    setVacio(false)
    setBuscando(true)
    try {
      const r = await buscarPedido(ref)
      fijarFecha(r.fecha)
      setBusqueda((b) => ({ ref, pedidos: r.pedidos, n: (b?.n ?? 0) + 1 }))
      setError(false)
    } catch (x) {
      if (!fallo(x, true)) setError(true)
    } finally {
      setBuscando(false)
    }
  }

  const verTodos = () => {
    setBusqueda(null)
    setReferencia('')
    void traer()
  }

  const elegir = (id: string) => {
    fijar({ pedidoId: id, origen: '/operacion' })
    if (enPedido && id === pedidoId) return
    // 2.1: elegir otra fila en pantalla ancha también es llegar: el detalle enfoca su `h1` al cargar.
    navegar('/operacion/pedido')
  }

  const mostrados = useMemo(() => (busqueda ? busqueda.pedidos : ordenarPedidos(grupo, lista ?? [])), [busqueda, grupo, lista])
  const chip = CHIPS.find((c) => c.valor === grupo)!.texto

  const alDia = (
    <p className="flex flex-wrap items-center gap-x-3 text-base text-tenue">
      {actualizado && <span className="cifras whitespace-normal">{MARCO.actualizado(actualizado)}</span>}
      <Boton variante="texto" ocupado={actualizando} textoOcupado={MARCO.actualizando} onClick={() => void actualizar()}>
        {MARCO.actualizar}
      </Boton>
    </p>
  )

  const cola = (
    <div className={`${enPedido ? 'hidden @3xl/main:flex' : 'flex'} min-w-0 flex-col gap-5`} aria-busy={lista === null || undefined}>
      <form role="search" noValidate className="flex flex-col gap-1.5" onSubmit={(e) => void buscar(e)}>
        <label htmlFor="buscar-referencia" className="font-bold">
          {T.buscarEtiqueta}
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <input
            id="buscar-referencia"
            value={referencia}
            onChange={(e) => {
              setReferencia(e.target.value)
              setVacio(false)
            }}
            autoComplete="off"
            spellCheck={false}
            maxLength={64}
            aria-invalid={vacio || undefined}
            aria-describedby={vacio ? 'buscar-referencia-error' : undefined}
            className={`digitos min-h-12 w-full min-w-0 flex-1 basis-40 rounded-xl bg-hoja px-4 py-2.5 ring-2 ring-inset focus-visible:ring-turquesa ${vacio ? 'ring-pronto' : 'ring-borde'}`}
          />
          <Boton type="submit" variante="secundario" icono={<Search aria-hidden className="size-5" />} ocupado={buscando} textoOcupado={T.buscando}>
            {T.buscar}
          </Boton>
        </div>
        {vacio && <MensajeError id="buscar-referencia-error">{T.buscarVacio}</MensajeError>}
      </form>
      {busqueda ? (
        <div key={busqueda.n} className="flex flex-col items-start gap-2">
          {busqueda.pedidos.length === 0 ? (
            <Nota tono="rocio" rol="status">
              <span className="break-words">{T.sinResultado(busqueda.ref)}</span>
            </Nota>
          ) : (
            <p className="break-words">{T.mostrando(busqueda.ref)}</p>
          )}
          <Boton variante="texto" onClick={verTodos}>
            {T.verTodos}
          </Boton>
        </div>
      ) : (
        <>
          <GrupoOpciones
            forma="chips"
            leyenda={T.mostrar}
            nombre="grupo-pedidos"
            opciones={CHIPS}
            valor={grupo}
            onCambio={(v) => {
              setGrupo(v)
              setVisibles(POR_PAGINA)
            }}
          />
          {alDia}
        </>
      )}
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
      {lista === null && !error && !busqueda && <p className="text-tenue">{verCargando ? T.cargando : ''}</p>}
      {(lista !== null || busqueda) && mostrados.length === 0 && !busqueda && (
        <div className="flex flex-col gap-1">
          <p className="text-xl font-bold">{T.vacio(chip)}</p>
          {grupo === 'por_atender' && <p className="text-tenue">{T.vacioPorAtender}</p>}
        </div>
      )}
      {mostrados.length > 0 && (
        <ul className="flex flex-col gap-2">
          {mostrados.slice(0, visibles).map((p) => (
            <li key={p.id}>
              <FilaPedido p={p} elegida={enPedido && p.id === pedidoId} onElegir={() => elegir(p.id)} />
            </li>
          ))}
        </ul>
      )}
      {mostrados.length > visibles && (
        <Boton variante="secundario" className="self-start" onClick={() => setVisibles((n) => n + POR_PAGINA)}>
          {T.verMas}
        </Boton>
      )}
      <RotuloPiloto />
    </div>
  )

  return (
    <div className="flex flex-col gap-8">
      {!enPedido && (
        <div className="flex flex-col gap-2">
          <Titulo className="text-3xl">{T.titulo}</Titulo>
          <AvisoPrivacidad />
        </div>
      )}
      <div className={GRILLA}>
        {cola}
        {enPedido && pedidoId ? (
          <section className={CUADRO_DETALLE}>
            <DetallePedido key={pedidoId} pedidoId={pedidoId} origen="/operacion" conRotulo="angosto" onCambio={() => void traer()} />
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

/** 5.3: la fila de un pedido. Ningún dato de la familia, ni el comercio. */
function FilaPedido({ p, elegida, onElegir }: { p: PedidoOperacion; elegida: boolean; onElegir: () => void }) {
  const { dia, hora } = enChile(p.pagado_en)
  const palabra = palabraPedido(p.estado)
  const nombre = [
    `${T.pedido} ${p.referencia ?? ''}`.trim(),
    palabra,
    pesos(p.total_confirmado),
    T.partes(p.numero_partes),
    T.pagadoEl(dia, hora),
    p.incidencia_abierta ? T.incidenciaAbierta : null,
    p.devolucion_sin_terminar ? T.devolucionSinTerminar : null,
  ]
    .filter(Boolean)
    .join(', ')
  return (
    <FilaCola
      elegida={elegida}
      nombre={nombre}
      onElegir={onElegir}
      primera={
        <>
          <span className="min-w-0">
            {T.pedido} <span className="digitos break-words">{p.referencia}</span>
          </span>
          <EtiquetaPedido estado={p.estado} />
        </>
      }
    >
      <span>
        <Monto n={p.total_confirmado} /> · {T.partes(p.numero_partes)}
      </span>
      <span className="cifras whitespace-normal text-tenue">{T.pagadoEl(dia, hora)}</span>
      {p.incidencia_abierta && <Atencion>{T.incidenciaAbierta}</Atencion>}
      {p.devolucion_sin_terminar && <Atencion>{T.devolucionSinTerminar}</Atencion>}
    </FilaCola>
  )
}

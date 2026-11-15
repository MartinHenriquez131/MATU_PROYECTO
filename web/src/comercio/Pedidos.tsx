// Pedidos de hoy y un pedido (especificación MATU-63, secciones 5 y 6). Las dos rutas son una sola
// pantalla: la lista se conserva al elegir una parte, y en pantalla ancha la cola queda a la
// izquierda del detalle. La lista se vuelve a pedir cada minuto con la pestaña visible.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ChevronRight, ShieldCheck, TriangleAlert } from 'lucide-react'
import { leerFallo } from '../compartido/api/cliente'
import { listarPartes, type EstadoParte, type ParteResumen, type ParteVista } from '../compartido/api/comercio'
import { esVencida } from '../compartido/api/sesion'
import { anunciar } from '../compartido/ui/Anuncios'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { useDemora } from '../compartido/useDemora'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { navegar } from '../familia/ruteo'
import { Titulo } from '../familia/ui'
import { enCurso, horaChile, IconoEstado, plazo } from './comun'
import { useComercio } from './estado'
import { Pie, RotuloPiloto } from './Marco'
import { DetallePedido } from './Pedido'
import { PEDIDOS as T, TITULO_COMERCIO } from './textos'

const CADA = 60_000

/** 5.4: los grupos, en este orden. Un grupo sin partes no se muestra. */
const GRUPOS: { estado: EstadoParte; texto: string }[] = [
  { estado: 'enviada', texto: T.grupoPorPreparar },
  { estado: 'preparando', texto: T.grupoPreparando },
  { estado: 'lista', texto: T.grupoListos },
  { estado: 'retirada', texto: T.grupoRetirados },
  { estado: 'cancelada', texto: T.grupoCancelados },
]

/** 5.3: por «preparar antes de», la más temprana primero; retirados y cancelados, el más reciente primero. */
function ordenar(estado: EstadoParte, partes: ParteResumen[]) {
  const t = (iso: string | null | undefined) => (iso ? new Date(iso).getTime() : 0)
  if (estado === 'retirada') return [...partes].sort((a, b) => t(b.retirada_en) - t(a.retirada_en))
  if (estado === 'cancelada') return [...partes].sort((a, b) => t(b.cancelada_en) - t(a.cancelada_en))
  return [...partes].sort((a, b) => t(a.preparar_antes_de) - t(b.preparar_antes_de))
}

/** Lo que cambió de una parte por una acción del detalle, en su fila. */
const resumenDe = (p: ParteVista): ParteResumen => {
  const { lineas, ...resto } = p
  return { ...resto, numero_lineas: lineas.length }
}

export function PantallaPedidos({ ruta }: { ruta: '/comercio' | '/comercio/pedido' }) {
  const { parteId, fijar, quedoInactiva } = useComercio()
  const [partes, setPartes] = useState<ParteResumen[] | null>(null)
  const [actualizado, setActualizado] = useState<string | null>(null)
  const [error, setError] = useState(false)
  const [actualizando, setActualizando] = useState(false)
  const desfase = useRef(0)
  const conocidas = useRef<Set<string> | null>(null)
  const verCargando = useDemora(1000)
  const enPedido = ruta === '/comercio/pedido'

  const ahora = useCallback(() => new Date(Date.now() + desfase.current), [])

  const traer = useCallback(async () => {
    try {
      const r = await listarPartes()
      if (r.fecha) desfase.current = r.fecha.getTime() - Date.now()
      // 5.5: lo que llegó a «Por preparar» desde la vez anterior se anuncia una vez.
      const antes = conocidas.current
      if (antes) {
        const nuevas = r.partes.filter((p) => p.estado === 'enviada' && !antes.has(p.id))
        if (nuevas.length === 1) anunciar(T.llegoUno(nuevas[0].referencia), 'status')
        else if (nuevas.length > 1) anunciar(T.llegaron(nuevas.length), 'status')
      }
      conocidas.current = new Set(r.partes.map((p) => p.id))
      setPartes(r.partes)
      setActualizado(fechaYHoraDeChile(ahora()).hora)
      setError(false)
    } catch (x) {
      if (esVencida(x)) return
      if (leerFallo(x).status === 403) return quedoInactiva()
      setError(true)
    }
  }, [ahora, quedoInactiva])

  // 5.5: al abrir, cada minuto con la pestaña visible y al volver a ella. Nunca mueve el foco.
  useEffect(() => {
    void traer()
    const t = window.setInterval(() => {
      if (document.visibilityState === 'visible') void traer()
    }, CADA)
    const alVolver = () => {
      if (document.visibilityState === 'visible') void traer()
    }
    document.addEventListener('visibilitychange', alVolver)
    return () => {
      window.clearInterval(t)
      document.removeEventListener('visibilitychange', alVolver)
    }
  }, [traer])

  // 2.1: sin la parte elegida (al recargar) o si ya no viene en la lista, a `/comercio`.
  useEffect(() => {
    if (!enPedido) return
    if (!parteId || (partes && !partes.some((p) => p.id === parteId))) {
      fijar({ parteId: null })
      navegar('/comercio', { reemplazar: true })
    }
  }, [enPedido, parteId, partes, fijar])

  const actualizar = async () => {
    setActualizando(true)
    await traer()
    setActualizando(false)
  }

  const elegir = (id: string) => {
    fijar({ parteId: id })
    if (enPedido && id === parteId) return
    navegar('/comercio/pedido')
    // 2.1: elegir otra parte en pantalla ancha también es llegar: el foco va al `h1` del pedido.
    if (enPedido) window.setTimeout(() => document.getElementById('titulo-pagina')?.focus(), 0)
  }

  const alCambiar = useCallback((p: ParteVista) => setPartes((lista) => lista?.map((x) => (x.id === p.id ? resumenDe(p) : x)) ?? lista), [])

  const elegida = enPedido && partes ? partes.find((p) => p.id === parteId) : undefined

  // 2.1: «Pedido K4M7XP · MATU». La referencia va en el título, nunca en la URL.
  const referencia = elegida?.referencia
  useLayoutEffect(() => {
    if (enPedido && referencia) document.title = TITULO_COMERCIO.pedido(referencia)
  }, [enPedido, referencia])

  const privacidad = (
    <p className="flex max-w-prose gap-2 text-base text-tenue">
      <ShieldCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-turquesa" />
      <span className="min-w-0">{T.privacidad}</span>
    </p>
  )
  const alDia = (
    <p className="flex flex-wrap items-center gap-x-3 text-base text-tenue">
      {actualizado && <span className="cifras whitespace-normal">{T.actualizado(actualizado)}</span>}
      <Boton variante="texto" ocupado={actualizando} textoOcupado={T.actualizando} onClick={() => void actualizar()}>
        {T.actualizar}
      </Boton>
    </p>
  )

  const cola = (
    <div className={`${enPedido ? 'hidden @3xl/main:flex' : 'flex'} min-w-0 flex-col gap-6`} aria-busy={partes === null || undefined}>
      {enPedido && (
        <div className="flex flex-col gap-1">
          {privacidad}
          {alDia}
        </div>
      )}
      {error && (
        <div className="flex flex-col items-start gap-3">
          <Nota tono="pronto" rol="alert">
            {T.errorAlTraer}
          </Nota>
          <Boton variante="secundario" onClick={() => void traer()}>
            {T.volverAIntentar}
          </Boton>
        </div>
      )}
      {partes === null && !error && <p className="text-tenue">{verCargando ? T.cargando : ''}</p>}
      {partes && <Grupos partes={partes} elegidaId={elegida?.id ?? null} ahora={ahora()} onElegir={elegir} />}
      <RotuloPiloto texto={T.rotuloPedidos} />
      <Pie />
    </div>
  )

  return (
    <div className="flex flex-col gap-8">
      {!enPedido && (
        <div className="flex flex-col gap-2">
          <Titulo className="text-3xl">{T.titulo}</Titulo>
          {privacidad}
          {alDia}
        </div>
      )}
      <div className="grid grid-cols-1 items-start gap-x-8 gap-y-8 @3xl/main:grid-cols-[19rem_minmax(0,1fr)]">
        {cola}
        {enPedido && parteId ? (
          <section className="min-w-0 @3xl/main:rounded-xl @3xl/main:bg-hoja @3xl/main:px-8 @3xl/main:py-5 @3xl/main:ring-1 @3xl/main:ring-linea">
            <DetallePedido key={parteId} parteId={parteId} resumen={elegida} ahora={ahora} onCambio={alCambiar} />
          </section>
        ) : (
          <div className="hidden rounded-xl bg-hoja px-6 py-6 ring-1 ring-linea @3xl/main:block">
            <p className="text-lg text-tenue">{T.elige}</p>
          </div>
        )}
      </div>
    </div>
  )
}

/** 5.4: los grupos de la cola, con su `h2` (ícono, palabra y número). */
function Grupos({ partes, elegidaId, ahora, onElegir }: { partes: ParteResumen[]; elegidaId: string | null; ahora: Date; onElegir: (id: string) => void }) {
  const abiertas = partes.some((p) => p.estado === 'enviada' || p.estado === 'preparando' || p.estado === 'lista')
  return (
    <div className="flex flex-col gap-6">
      {!abiertas && (
        <div className="flex flex-col gap-1">
          <p className="text-xl font-bold">{T.vacioTitulo}</p>
          <p className="text-tenue">{T.vacioTexto}</p>
        </div>
      )}
      {GRUPOS.map(({ estado, texto }) => {
        const del = ordenar(
          estado,
          partes.filter((p) => p.estado === estado),
        )
        if (!del.length) return null
        return (
          <section key={estado} aria-labelledby={`grupo-${estado}`} className="flex flex-col gap-2">
            {/* En modo angosto el ícono va en la primera línea, como una letra más (MensajeError). */}
            <h2 id={`grupo-${estado}`} className="flex items-center gap-2 angosto:block text-xl font-bold break-words">
              <span className="contents angosto:me-1.5 angosto:inline-flex angosto:align-middle">
                <IconoEstado estado={estado} />
              </span>
              <span className="min-w-0">{T.conNumero(texto, del.length)}</span>
            </h2>
            <ul className="flex flex-col gap-2">
              {del.map((p) => (
                <li key={p.id}>
                  <Fila parte={p} elegida={p.id === elegidaId} ahora={ahora} onElegir={() => onElegir(p.id)} />
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}

/** 5.3: la fila de la cola, un botón de ancho completo con tres líneas. */
function Fila({ parte, elegida, ahora, onElegir }: { parte: ParteResumen; elegida: boolean; ahora: Date; onElegir: () => void }) {
  const productos = T.productos(parte.numero_lineas)
  let tercera: { texto: string; clase: string; atrasada?: boolean } | null = null
  if (enCurso(parte.estado)) {
    const p = plazo(parte.preparar_antes_de, ahora)
    tercera = p.atrasada ? { texto: p.texto, clase: 'font-bold text-atenta', atrasada: true } : { texto: p.texto, clase: 'text-tenue' }
  } else if (parte.estado === 'lista') tercera = { texto: T.esperandoRetiro, clase: 'text-tenue' }
  else if (parte.estado === 'retirada') tercera = parte.retirada_en ? { texto: T.retiradoA(horaChile(parte.retirada_en)), clase: 'text-tenue' } : null
  else tercera = { texto: T.noLoPrepares, clase: 'font-bold' }
  const nombre = [`${T.pedido} ${parte.referencia}`, productos, tercera?.texto.replace(/\.$/, '')].filter(Boolean).join(', ')
  return (
    <button
      type="button"
      aria-current={elegida ? 'true' : undefined}
      aria-label={nombre}
      onClick={onElegir}
      className={`flex min-h-12 w-full flex-col items-start gap-0.5 rounded-xl px-4 angosto:px-2 py-3 text-left ${
        elegida ? 'bg-rocio ring-2 ring-turquesa' : 'bg-hoja ring-1 ring-linea hover:ring-borde'
      }`}
    >
      <span className="flex w-full items-center gap-2 font-bold">
        <span className="min-w-0">
          {T.pedido} <span className="digitos">{parte.referencia}</span>
        </span>
        {elegida && <ChevronRight aria-hidden className="ms-auto size-5 shrink-0" />}
      </span>
      <span>{productos}</span>
      {tercera && (
        <span className={`flex items-start gap-1.5 ${tercera.clase}`}>
          {tercera.atrasada && <TriangleAlert aria-hidden className="mt-0.5 size-5 shrink-0" />}
          <span className="cifras whitespace-normal">{tercera.texto}</span>
        </span>
      )}
    </button>
  )
}

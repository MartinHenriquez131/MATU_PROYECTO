// Cobros por revisar (especificación MATU-81, sección 10): las ventas sin respuesta por más de 15
// minutos y las devoluciones sin terminar. Sin acciones (C19): cada fila abre el pedido, donde está el
// pago completo, con la pestaña «Cobros» activa y «Volver a los cobros». No se audita.
import { useCallback, useEffect, useState } from 'react'
import { Clock, Undo2 } from 'lucide-react'
import { cobrosPendientes, type CobrosPendientes } from '../compartido/api/operacion'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { Boton } from '../compartido/ui/Boton'
import { Nota } from '../compartido/ui/Nota'
import { useDemora } from '../compartido/useDemora'
import { navegar } from '../familia/ruteo'
import { Titulo } from '../familia/ui'
import { CUADRO_DETALLE, enChile, EtiquetaAnulacion, FilaCola, Monto, pesos, useAhora, useAlDia, useFocoAlMontar } from './comun'
import { useOperacion } from './estado'
import { RotuloPiloto } from './Marco'
import { DetallePedido } from './Pedido'
import { COBROS as T, ESTADO_ANULACION, MARCO, MOTIVO_ANULACION } from './textos'

/** Decisión 467: `en_curso` es la «En curso» de 7 y `sin_terminar`, la «Sin terminar» (la `rechazada` de 7). */
const ID_REINTENTAR = 'reintentar-cobros'
const COMO_ANULACION = { en_curso: 'en_curso', sin_terminar: 'rechazada' } as const

export function PantallaCobros({ ruta }: { ruta: '/operacion/cobros' | '/operacion/pedido' }) {
  const { pedidoId } = useOperacion()
  if (ruta === '/operacion/pedido' && pedidoId)
    return (
      <section className={`${CUADRO_DETALLE} max-w-5xl`}>
        <DetallePedido key={pedidoId} pedidoId={pedidoId} origen="/operacion/cobros" conRotulo="siempre" onCambio={() => undefined} />
      </section>
    )
  return <ListaCobros />
}

function ListaCobros() {
  const { fijar, fallo } = useOperacion()
  const [cobros, setCobros] = useState<CobrosPendientes | null>(null)
  const [error, setError] = useState(false)
  const [actualizado, setActualizado] = useState<string | null>(null)
  const [actualizando, setActualizando] = useState(false)
  const { ahora, fijarFecha } = useAhora()
  const verCargando = useDemora(1000)
  const pedirFoco = useFocoAlMontar()

  /** `false` si quedó el error de la lista a la vista. */
  const traer = useCallback(async (): Promise<boolean> => {
    try {
      const r = await cobrosPendientes()
      fijarFecha(r.fecha)
      setCobros(r.cobros)
      setActualizado(fechaYHoraDeChile(ahora()).hora)
      setError(false)
      return true
    } catch (x) {
      if (fallo(x, true)) return true
      setError(true)
      return false
    }
  }, [fijarFecha, ahora, fallo])

  useEffect(() => {
    void traer()
  }, [traer])
  useAlDia(() => void traer())

  const abrir = (id: string) => {
    fijar({ pedidoId: id, origen: '/operacion/cobros' })
    navegar('/operacion/pedido')
  }

  const ventas = cobros?.ventas_sin_respuesta ?? []
  const anulaciones = cobros?.anulaciones_sin_terminar ?? []

  return (
    <div className="flex max-w-3xl flex-col gap-8">
      <div className="flex flex-col gap-2">
        <Titulo className="text-3xl">{T.titulo}</Titulo>
        <p className="max-w-prose text-base text-tenue">{T.bajada}</p>
        <p className="flex flex-wrap items-center gap-x-3 text-base text-tenue">
          {actualizado && <span className="cifras whitespace-normal">{MARCO.actualizado(actualizado)}</span>}
          {/* Revisión visual (P3): con el error a la vista, «Volver a intentar» es la única forma de pedirla otra vez. */}
          {!error && (
            <Boton
              variante="texto"
              ocupado={actualizando}
              textoOcupado={MARCO.actualizando}
              onClick={async () => {
                setActualizando(true)
                const bien = await traer()
                setActualizando(false)
                // «Actualizar» se quita con el error: el foco pasa a «Volver a intentar».
                if (!bien) pedirFoco(ID_REINTENTAR)
              }}
            >
              {MARCO.actualizar}
            </Boton>
          )}
        </p>
      </div>
      {error && (
        <div className="flex flex-col items-start gap-3">
          <Nota tono="pronto" rol="alert">
            {T.errorAlTraer}
          </Nota>
          <Boton id={ID_REINTENTAR} variante="secundario" onClick={() => void traer()}>
            {MARCO.volverAIntentar}
          </Boton>
        </div>
      )}
      {!cobros && !error && <p className="text-tenue">{verCargando ? T.cargando : ''}</p>}
      {cobros && (
        <>
          <section aria-labelledby="cobros-ventas" className="flex flex-col gap-2">
            <h2 id="cobros-ventas" className="flex items-center gap-2 angosto:block text-xl font-bold break-words">
              <span className="contents angosto:me-1.5 angosto:inline-flex angosto:align-middle">
                <Clock aria-hidden className="size-5 shrink-0 text-atenta" />
              </span>
              <span className="min-w-0">{T.ventas(ventas.length)}</span>
            </h2>
            {ventas.length === 0 ? (
              <p className="text-tenue">{T.sinVentas}</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {ventas.map((v) => {
                  const { hora } = enChile(v.creada_en)
                  const hace = Math.max(0, Math.floor((ahora().getTime() - new Date(v.creada_en).getTime()) / 60_000))
                  const ref = v.referencia ?? ''
                  return (
                    <li key={`${v.pedido_id}-${v.buy_order}`}>
                      <FilaCola
                        elegida={false}
                        nombre={[T.pedido(ref), pesos(v.monto), T.ordenDeCompra(v.buy_order), T.iniciada(hora, hace)].join(', ')}
                        onElegir={() => abrir(v.pedido_id)}
                        primera={
                          <>
                            <span className="min-w-0">
                              {T.pedido('').trimEnd()} <span className="digitos break-words">{ref}</span>
                            </span>
                            <Monto n={v.monto} />
                          </>
                        }
                      >
                        <span className="text-tenue break-words">
                          {T.ordenDeCompra('').trimEnd()} <span className="digitos">{v.buy_order}</span>
                        </span>
                        <span className="cifras font-bold whitespace-normal text-atenta">{T.iniciada(hora, hace)}</span>
                      </FilaCola>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>
          <section aria-labelledby="cobros-anulaciones" className="flex flex-col gap-2">
            <h2 id="cobros-anulaciones" className="flex items-center gap-2 angosto:block text-xl font-bold break-words">
              <span className="contents angosto:me-1.5 angosto:inline-flex angosto:align-middle">
                <Undo2 aria-hidden className="size-5 shrink-0 text-atenta" />
              </span>
              <span className="min-w-0">{T.anulaciones(anulaciones.length)}</span>
            </h2>
            {anulaciones.length === 0 ? (
              <p className="text-tenue">{T.sinAnulaciones}</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {anulaciones.map((a, i) => {
                  const { hora } = enChile(a.creada_en)
                  const ref = a.referencia ?? ''
                  return (
                    <li key={`${a.pedido_id}-${i}`}>
                      <FilaCola
                        elegida={false}
                        nombre={[T.pedido(ref), pesos(a.monto), MOTIVO_ANULACION[a.motivo], T.desde(hora), ESTADO_ANULACION[COMO_ANULACION[a.estado]]].join(', ')}
                        onElegir={() => abrir(a.pedido_id)}
                        primera={
                          <>
                            <span className="min-w-0">
                              {T.pedido('').trimEnd()} <span className="digitos break-words">{ref}</span>
                            </span>
                            <Monto n={a.monto} />
                          </>
                        }
                      >
                        <span>{MOTIVO_ANULACION[a.motivo]}</span>
                        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                          <span className="cifras whitespace-normal text-tenue">{T.desde(hora)}</span>
                          <EtiquetaAnulacion estado={COMO_ANULACION[a.estado]} />
                        </span>
                      </FilaCola>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>
        </>
      )}
      <RotuloPiloto />
    </div>
  )
}

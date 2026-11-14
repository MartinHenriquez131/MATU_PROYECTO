// Piezas que comparten la cola y el detalle de la consola del comercio (MATU-63, secciones 5 y 6).
import type { ReactNode } from 'react'
import { Ban, CircleCheck, Circle, Contrast, PackageCheck } from 'lucide-react'
import type { EstadoParte, LineaComercio } from '../compartido/api/comercio'
import { fechaYHoraDeChile } from '../compartido/fechas'
import { ESPACIO_DURO, PEDIDO_COMERCIO, PEDIDOS } from './textos'

/** La hora de Chile de un instante del contrato, `HH:MM`. */
export const horaChile = (iso: string) => fechaYHoraDeChile(new Date(iso)).hora

/**
 * 5.4: «Preparar antes de las HH:MM», o «Era para las HH:MM.» si ya pasó. Con otra fecha que la de
 * hoy, también la fecha. `ahora` sale de la cabecera `Date` de la última respuesta (MATU-61 O11).
 */
export function plazo(iso: string, ahora: Date): { texto: string; atrasada: boolean } {
  const limite = new Date(iso)
  const { fecha, hora } = fechaYHoraDeChile(limite)
  const hoy = fechaYHoraDeChile(ahora).fecha === fecha
  const atrasada = limite.getTime() < ahora.getTime()
  if (atrasada) return { texto: hoy ? PEDIDOS.eraPara(hora) : PEDIDOS.eraParaDel(fecha, hora), atrasada }
  return { texto: hoy ? PEDIDOS.prepararAntes(hora) : PEDIDOS.prepararAntesDel(fecha, hora), atrasada }
}

/** Lo que una parte todavía está por preparar: el plazo importa (y puede atrasarse). */
export const enCurso = (e: EstadoParte) => e === 'enviada' || e === 'preparando'

const ICONO = 'size-5 shrink-0'

/** 5.4 y 6.3: el ícono de cada estado, siempre junto a su palabra. */
export function IconoEstado({ estado, enEtiqueta = false }: { estado: EstadoParte; enEtiqueta?: boolean }) {
  const clase = enEtiqueta ? 'size-4 shrink-0' : ICONO
  switch (estado) {
    case 'enviada':
      return <Circle aria-hidden className={`${clase} text-atenta`} strokeWidth={2.5} />
    case 'preparando':
      return <Contrast aria-hidden className={`${clase} ${enEtiqueta ? '' : 'text-tenue'}`} />
    case 'lista':
      return <PackageCheck aria-hidden className={`${clase} text-ok`} />
    case 'retirada':
      return <CircleCheck aria-hidden className={`${clase} ${enEtiqueta ? '' : 'text-tenue'}`} />
    case 'cancelada':
      return <Ban aria-hidden className={`${clase} ${enEtiqueta ? '' : 'text-tenue'}`} />
  }
}

/** 6.3: la palabra y el tono de la `Etiqueta` de cada estado. */
export const ETIQUETA_ESTADO: Record<EstadoParte, { texto: string; tono: 'atenta' | 'neutro' | 'ok' }> = {
  enviada: { texto: PEDIDO_COMERCIO.estadoPorPreparar, tono: 'atenta' },
  preparando: { texto: PEDIDO_COMERCIO.estadoPreparando, tono: 'neutro' },
  lista: { texto: PEDIDO_COMERCIO.estadoListo, tono: 'ok' },
  retirada: { texto: PEDIDO_COMERCIO.estadoRetirado, tono: 'neutro' },
  cancelada: { texto: PEDIDO_COMERCIO.estadoCancelado, tono: 'neutro' },
}

/** 6.4: «2 × Pañal adulto M x30», con la cantidad en `cifras` y el × pegado. */
export function CantidadProducto({ linea, unidades }: { linea: LineaComercio; unidades?: number }): ReactNode {
  return (
    <>
      <span className="cifras">{`${unidades ?? linea.cantidad}${ESPACIO_DURO}×`}</span> {linea.producto.nombre}
    </>
  )
}

/** Cuántos envases de una línea faltan. Una línea `faltante` sin el número es que faltan todos (decisión 413). */
export const faltanDe = (l: LineaComercio) =>
  l.estado_linea === 'faltante' || l.estado_linea === 'devuelta' ? Math.min(l.cantidad, l.unidades_faltantes > 0 ? l.unidades_faltantes : l.cantidad) : 0

/** Cuántos envases de una línea se entregan: la cantidad menos lo que falta. */
export const aEntregar = (l: LineaComercio) => l.cantidad - faltanDe(l)

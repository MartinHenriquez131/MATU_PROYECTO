// MATU-92: datos sintéticos de «Tus pedidos», con los nombres del contrato (PedidoPagadoFila,
// SeguimientoPedido, RetractosDelPedido, RetractoVistaFamilia). Montos de la especificación (57.460,
// 31.980, 22.980, 5.290). Comercios ficticios y ningún código de retiro: el contrato no los trae.
import type { FilaObservador, FilaPedido, LineaParaRetracto, RetractoFamilia, Retractos, Seguimiento } from '../src/compartido/api/tusPedidos'
import { PANAL_C, SUPLEMENTO_C } from './pagoFalso'
import { PEDIDO_ID } from './pedidoFalso'

export const PEDIDO_2 = '3c9d4e20-0000-4000-8000-0000000000p2'
export const PEDIDO_3 = '3c9d4e20-0000-4000-8000-0000000000p3'
export const LINEA_PANAL = '3c9d4e20-0000-4000-8000-0000000000l1'
export const LINEA_SUPLEMENTO = '3c9d4e20-0000-4000-8000-0000000000l2'
export const RETRACTO_ID = '3c9d4e20-0000-4000-8000-0000000000r1'

export function fila(cambios: Partial<FilaPedido> = {}): FilaPedido {
  return {
    pedido_id: PEDIDO_ID,
    referencia: '4821',
    // 16:41 en Chile (UTC-3 en noviembre).
    pagado_en: '2026-11-11T19:41:00Z',
    estado: 'pagado',
    entregado_en: null,
    cancelado_en: null,
    productos: [{ producto: PANAL_C, cantidad: 2 }],
    resumen_productos: null,
    productos_borrados: false,
    total: 57460,
    devuelto: 0,
    devuelto_todo: false,
    puede_cancelar: true,
    cancelar_motivo: null,
    puede_arrepentirse: false,
    arrepentirse_motivo: 'sin_entregar',
    plazo_hasta: null,
    plazo_correo_hasta: null,
    ...cambios,
  }
}

/** Entregado el 04/11/2026 (15:00 en Chile), con el plazo hasta el 18/11/2026 a las 23:59 de Chile. */
export const entregado = (cambios: Partial<FilaPedido> = {}): FilaPedido =>
  fila({
    pedido_id: PEDIDO_2,
    referencia: '4790',
    pagado_en: '2026-11-02T19:41:00Z',
    estado: 'entregado',
    entregado_en: '2026-11-04T18:00:00Z',
    total: 31980,
    devuelto: 5290,
    devuelto_todo: false,
    puede_cancelar: false,
    cancelar_motivo: 'ya_se_prepara',
    puede_arrepentirse: true,
    arrepentirse_motivo: null,
    plazo_hasta: '2026-11-19T02:59:59.999999Z',
    plazo_correo_hasta: '2027-02-02T18:00:00Z',
    ...cambios,
  })

export const filaObservador = (cambios: Partial<FilaObservador> = {}): FilaObservador => ({
  pedido_id: PEDIDO_ID,
  pagado_en: '2026-11-11T19:41:00Z',
  estado: 'pagado',
  entregado_en: null,
  productos: [
    { producto: PANAL_C, cantidad: 2 },
    { producto: SUPLEMENTO_C, cantidad: 1 },
  ],
  resumen_productos: { primero: PANAL_C.nombre, otros: 1 },
  productos_borrados: false,
  ...cambios,
})

export function seguimiento(cambios: Partial<Seguimiento> = {}): Seguimiento {
  const { productos: _p, resumen_productos: _r, ...base } = fila()
  return {
    ...base,
    partes: [
      {
        comercio: { nombre_fantasia: 'Almacén El Ejemplo', ficticio: true },
        estado: 'enviada',
        cancelada_por: null,
        lineas: [{ linea_id: LINEA_PANAL, producto: PANAL_C, cantidad: 2, unidades_faltantes: 0 }],
      },
    ],
    ...cambios,
  }
}

/** El pedido 4790 entregado, con un suplemento que faltó (1 de 3). */
export function seguimientoEntregado(cambios: Partial<Seguimiento> = {}): Seguimiento {
  const { productos: _p, resumen_productos: _r, ...base } = entregado()
  return {
    ...base,
    partes: [
      {
        comercio: { nombre_fantasia: 'Almacén El Ejemplo', ficticio: true },
        estado: 'retirada',
        cancelada_por: null,
        lineas: [
          { linea_id: LINEA_PANAL, producto: PANAL_C, cantidad: 2, unidades_faltantes: 0 },
          { linea_id: LINEA_SUPLEMENTO, producto: SUPLEMENTO_C, cantidad: 3, unidades_faltantes: 1 },
        ],
      },
    ],
    ...cambios,
  }
}

export const lineaParaRetracto = (cambios: Partial<LineaParaRetracto> = {}): LineaParaRetracto => ({
  linea_id: LINEA_PANAL,
  producto: PANAL_C,
  entregadas: 2,
  ya_pedidas: 0,
  disponibles: 2,
  precio_pagado: 12990,
  retracto_pierde_al_abrir: true,
  ...cambios,
})

export function retractos(cambios: Partial<Retractos> = {}): Retractos {
  return {
    plazo_hasta: '2026-11-19T02:59:59.999999Z',
    plazo_correo_hasta: '2027-02-02T18:00:00Z',
    puede_arrepentirse: true,
    arrepentirse_motivo: null,
    // La 0.3: el envío solo si se devuelve todo. La 0.2 (siempre) va en su prueba.
    condiciones_version: '0.3',
    costo_envio: 3990,
    incluye_envio_si_todo: true,
    lineas: [
      lineaParaRetracto(),
      lineaParaRetracto({ linea_id: LINEA_SUPLEMENTO, producto: SUPLEMENTO_C, entregadas: 2, ya_pedidas: 0, disponibles: 2, precio_pagado: 26490, retracto_pierde_al_abrir: false }),
    ],
    retractos: [],
    ...cambios,
  }
}

export const retracto = (cambios: Partial<RetractoFamilia> = {}): RetractoFamilia => ({
  id: RETRACTO_ID,
  pedido_id: PEDIDO_2,
  estado: 'solicitado',
  solicitado_en: '2026-11-06T15:00:00Z',
  plazo_hasta: '2026-11-19T02:59:59.999999Z',
  incluye_envio: false,
  monto: 26490,
  origen: 'app',
  lineas: [{ linea_id: LINEA_SUPLEMENTO, producto: SUPLEMENTO_C, cantidad: 1, monto: 26490 }],
  resuelto_en: null,
  es_tuyo: true,
  ...cambios,
})

/** La lista de quien ve el pago, o la del observador. */
export const lista = (items: (FilaPedido | FilaObservador)[], siguiente_cursor: string | null = null) => ({ items, siguiente_cursor })

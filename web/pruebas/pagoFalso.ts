// MATU-62: datos sintéticos del pago, con los nombres del contrato (PagoVista, Comprobante,
// ResultadoRetorno). Montos de la especificación (57.460 = 53.470 + 3.990). Ningún token es de
// Transbank y ninguna tarjeta es real: los últimos 4 son de ejemplo.
import type { Comprobante, Devolucion, PagoVista, ResultadoRetorno } from '../src/compartido/api/pago'
import { PEDIDO_ID, PERSONA_ID } from './pedidoFalso'

export const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g1'
export const OTRO_GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g2'
export const OTRA_PERSONA_ID = '3c9d4e20-0000-4000-8000-0000000000bb'
// Un token sintético de baja entropía: no es de Transbank.
export const TOKEN = 't'.repeat(64)

const producto = (id: string, nombre: string) => ({ id, nombre, presentacion: nombre, unidad: 'unidad' as const, unidades_por_envase: 1 })
export const PANAL_C = producto('3c9d4e20-0000-4000-8000-0000000000d1', 'Pañal adulto M x30')
export const SUPLEMENTO_C = producto('3c9d4e20-0000-4000-8000-0000000000d4', 'Suplemento vainilla x12')
export const TOALLITAS_C = producto('3c9d4e20-0000-4000-8000-0000000000d2', 'Toallitas húmedas x80')

export function comprobante(cambios: Partial<Comprobante> = {}): Comprobante {
  return {
    referencia: '4821',
    // 16:41 en Chile (UTC-3 en noviembre).
    pagado_en: '2026-11-11T19:41:00Z',
    lineas: [
      { producto: PANAL_C, cantidad: 2, precio_unitario: 12990, subtotal: 25980 },
      { producto: SUPLEMENTO_C, cantidad: 1, precio_unitario: 26490, subtotal: 26490 },
      { producto: TOALLITAS_C, cantidad: 1, precio_unitario: 1000, subtotal: 1000 },
    ],
    subtotal_productos: 53470,
    costo_envio: 3990,
    total: 57460,
    pagaste_tu: true,
    tarjeta: { tipo: 'debito', ultimos4: '4051', cuotas: 0 },
    codigo_autorizacion: '123456',
    vendedor: 'MATU, piloto académico, sin persona jurídica',
    ventana_entrega: 'Entre 24 y 48 horas hábiles',
    canal_reclamo: 'cuidaconmatu@gmail.com',
    condiciones: { version: '0.2', aceptadas_en: '2026-11-11T19:38:00Z', huella: 'b'.repeat(64), enlace: '/v1/condiciones-pedido?version=0.2' },
    tardio: false,
    devoluciones: [],
    precios_de_ejemplo: true,
    pago_de_prueba: true,
    correo: { destino: 'carmen@example.com', enviado: false },
    ...cambios,
  }
}

/** Lo que ve quien no pagó (D-62-2): sin tarjeta, código ni correo. */
export const comprobanteAjeno = (cambios: Partial<Comprobante> = {}) => comprobante({ pagaste_tu: false, tarjeta: null, codigo_autorizacion: null, correo: null, ...cambios })

export function pago(cambios: Partial<PagoVista> = {}): PagoVista {
  const c = cambios.comprobante === undefined ? comprobante() : cambios.comprobante
  return {
    pedido_id: PEDIDO_ID,
    estado: 'aprobado',
    pago_en_curso: false,
    pago_de_prueba: true,
    intento: { id: '3c9d4e20-0000-4000-8000-0000000000f1', resultado: 'aprobado', iniciado_en: '2026-11-11T19:38:00Z', cerrado_en: '2026-11-11T19:41:00Z', es_tuyo: true },
    devoluciones: c?.devoluciones ?? [],
    ...cambios,
    comprobante: c,
  }
}

export const devolucion = (cambios: Partial<Devolucion> = {}): Devolucion => ({
  motivo: 'producto_no_entregado',
  monto: 26490,
  producto: SUPLEMENTO_C,
  estado: 'hecha',
  solicitada_en: '2026-11-12T15:00:00Z',
  hecha_en: '2026-11-12T15:05:00Z',
  ultimos4: '4051',
  ...cambios,
})

export const retorno = (cambios: Partial<ResultadoRetorno> = {}): ResultadoRetorno => ({
  resultado: 'aprobado',
  ya_registrado: false,
  anulacion: null,
  volver_a_preguntar_en: null,
  grupo_id: GRUPO_ID,
  persona_cuidada_id: PERSONA_ID,
  pedido_id: PEDIDO_ID,
  pago_de_prueba: true,
  ...cambios,
})

// MATU-61: datos sintéticos del pedido y una API falsa que responde por ruta. Cada prueba arma sus
// respuestas con `rutas` (método y expresión de la ruta) y lee lo que salió en `pedidas`, con sus
// cabeceras y su cuerpo. Comercios y productos ficticios; el celular de ejemplo de lenguaje.md.
import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { createElement, Fragment } from 'react'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { apiFamilia } from '../src/compartido/api/sesion'
import type { PedidoVista } from '../src/compartido/api/pedido'

export const PERSONA_ID = '3c9d4e20-0000-4000-8000-0000000000aa'
export const PEDIDO_ID = '3c9d4e20-0000-4000-8000-0000000000p1'
export const ALMACEN = { id: '3c9d4e20-0000-4000-8000-0000000000e1', nombre_fantasia: 'Almacén El Ejemplo', ficticio: true }
export const BODEGA = { id: '3c9d4e20-0000-4000-8000-0000000000e2', nombre_fantasia: 'Bodega La Muestra', ficticio: true }

export const DIRECCION = { etiqueta: 'Casa', calle: 'Los Aromos', numero: '123', depto: '4', comuna: 'La Reina', region: 'Metropolitana', referencia: 'Portón verde', etag: 'v1' }
export const persona = (direccion: typeof DIRECCION | null = DIRECCION) => ({
  id: PERSONA_ID,
  nombre: 'María Soto',
  nombre_pila: 'María',
  nivel_apoyo: 'apoyo_parcial',
  direccion,
  consentimiento: null,
})

const producto = (id: string, nombre: string, presentacion: string, unidades: number, retracto: boolean) => ({ id, nombre, presentacion, unidad: 'unidad' as const, unidades_por_envase: unidades, retracto_pierde_al_abrir: retracto })
export const PANAL = producto('3c9d4e20-0000-4000-8000-0000000000d1', 'Pañal adulto M x30', 'Paquete de 30 unidades', 30, true)
export const TOALLITAS = producto('3c9d4e20-0000-4000-8000-0000000000d2', 'Toallitas húmedas x80', 'Paquete de 80 unidades', 80, true)
export const BOLSA = producto('3c9d4e20-0000-4000-8000-0000000000d3', 'Bolsa colectora x10', 'Caja de 10 unidades', 10, false)

export const OFERTAS = {
  panalAlmacen: '3c9d4e20-0000-4000-8000-0000000000o1',
  panalBodega: '3c9d4e20-0000-4000-8000-0000000000o2',
  toallitasBodega: '3c9d4e20-0000-4000-8000-0000000000o3',
  bolsaAlmacen: '3c9d4e20-0000-4000-8000-0000000000o4',
}
const oferta = (id: string, c: typeof ALMACEN, precio: number, disponible: boolean) => ({ oferta_id: id, comercio_id: c.id, nombre_fantasia: c.nombre_fantasia, precio, disponible, ficticio: true })

export const CATALOGO = {
  precios_de_ejemplo: true,
  categorias: [
    {
      id: '3c9d4e20-0000-4000-8000-0000000000k1',
      nombre: 'Higiene y cuidado personal',
      orden: 1,
      productos: [
        { ...PANAL, comercios: [oferta(OFERTAS.panalAlmacen, ALMACEN, 12990, true), oferta(OFERTAS.panalBodega, BODEGA, 13490, false)] },
        { ...TOALLITAS, comercios: [oferta(OFERTAS.toallitasBodega, BODEGA, 4290, true)] },
        { ...BOLSA, comercios: [oferta(OFERTAS.bolsaAlmacen, ALMACEN, 15990, false)] },
      ],
    },
  ],
}

type Producto = typeof PANAL
/** Decisión 222: la oferta del carrito de una línea, la del catálogo si está, o una sintética. */
const ofertaDeLinea = (p: Producto, comercio: typeof ALMACEN) =>
  CATALOGO.categorias.flatMap((c) => c.productos).find((x) => x.id === p.id)?.comercios.find((o) => o.comercio_id === comercio.id)?.oferta_id ?? `oferta-${p.id}-${comercio.id}`

export const linea = (p: Producto, comercio: typeof ALMACEN, cantidad: number, precio: number, extra: Partial<PedidoVista['lineas'][number]> = {}): PedidoVista['lineas'][number] => ({
  id: `linea-${p.id}`,
  oferta_id: ofertaDeLinea(p, comercio),
  producto: { id: p.id, nombre: p.nombre, presentacion: p.presentacion, unidad: p.unidad, unidades_por_envase: p.unidades_por_envase },
  cantidad,
  comercio,
  precio_unitario: precio,
  subtotal: cantidad * precio,
  regla_faltante: 'otro_comercio',
  retracto_pierde_al_abrir: p.retracto_pierde_al_abrir,
  cambio: null,
  ...extra,
})

/** Un borrador con el pañal (2) y las toallitas (1), o lo que se le pase. */
export function borrador(cambios: Partial<PedidoVista> = {}): PedidoVista {
  const lineas = cambios.lineas ?? [linea(PANAL, ALMACEN, 2, 12990), linea(TOALLITAS, BODEGA, 1, 4290)]
  const subtotal = lineas.reduce((t, l) => t + l.subtotal, 0)
  return {
    id: PEDIDO_ID,
    persona_cuidada_id: PERSONA_ID,
    estado: 'borrador',
    etag: 'p1',
    precios_de_ejemplo: true,
    lineas,
    salieron: [],
    comercios: [],
    subtotal_productos: subtotal,
    costo_envio: 3990,
    total: null,
    total_confirmado_en: null,
    vence_en: null,
    vigencia_segundos: null,
    ventana_entrega: 'Entre 24 y 48 horas hábiles',
    entrega: null,
    resumen: null,
    creado_en: '2026-11-11T15:00:00Z',
    actualizado_en: '2026-11-11T15:00:00Z',
    ...cambios,
  }
}

/** El mismo pedido con el total confirmado: vale hasta las 16:45 de Chile (19:45 UTC en noviembre). */
export function confirmado(cambios: Partial<PedidoVista> = {}): PedidoVista {
  const b = borrador(cambios)
  return {
    ...b,
    estado: 'total_confirmado',
    etag: 'p2',
    total: b.subtotal_productos + 3990,
    total_confirmado_en: '2026-11-11T19:30:00Z',
    vence_en: '2026-11-11T19:45:00Z',
    vigencia_segundos: 900,
    entrega: { calle: 'Los Aromos', numero: '123', depto: '4', comuna: 'La Reina', region: 'Metropolitana', referencia: 'Portón verde', telefono_contacto: '+56 9 •••• ••37', telefono_origen: 'celular_cuenta', telefono_es_tuyo: true },
    resumen: {
      vendedor: 'MATU, piloto académico, sin persona jurídica',
      boleta: 'En este piloto no se emite boleta',
      ventana_entrega: 'Entre 24 y 48 horas hábiles',
      canal_reclamo: 'cuidaconmatu@gmail.com',
      condiciones: { version: '0.1', huella: 'a'.repeat(64), enlace: '/v1/condiciones-pedido' },
    },
    ...cambios,
  }
}

export const autorizaciones = (despacho: 'vigente' | 'revision_vencida' | 'sin_autorizar' | 'retirada' = 'vigente') => ({
  autorizaciones: (['plan_cuidado', 'consumo', 'despacho'] as const).map((finalidad) => ({
    finalidad,
    estado: finalidad === 'despacho' ? despacho : 'vigente',
    id: finalidad === 'despacho' && despacho === 'sin_autorizar' ? null : `aut-${finalidad}`,
    calidad_otorgante: null,
    otorgado_en: despacho === 'sin_autorizar' && finalidad === 'despacho' ? null : '2026-11-09T15:00:00Z',
    revision_vence_en: despacho === 'revision_vencida' && finalidad === 'despacho' ? '2026-11-01T15:00:00Z' : null,
    revocado_en: despacho === 'retirada' && finalidad === 'despacho' ? '2026-11-10T15:00:00Z' : null,
    borrado_en: null,
    borrada: false,
  })),
})

export const CUENTA = { id: 'cuenta-1', nombre: 'Carmen', email: 'carmen@example.com', celular_enmascarado: '+56 9 •••• ••37', celular_verificado: true, celular_canal: 'sms', politica_aceptada: null }

export interface Pedida {
  metodo: string
  ruta: string
  cabeceras: Record<string, unknown>
  cuerpo: unknown
}
export interface Respuesta {
  status: number
  cuerpo?: unknown
  cabeceras?: Record<string, string>
}
type Manejador = Respuesta | ((p: Pedida) => Respuesta | Promise<Respuesta>)

export const problema = (status: number, tipo: string, extra: Record<string, unknown> = {}): Respuesta => ({ status, cuerpo: { type: `/errores/${tipo}`, title: 'Texto de la API que no se muestra', status, ...extra } })
export const NO_ENCONTRADO = problema(404, 'no-encontrado')

/**
 * La API por ruta: `rutas` son pares «MÉTODO expresión» → respuesta (o función). Lo que no calza,
 * 404. Las lecturas comunes del pedido vienen por omisión y se pisan con `rutas`.
 */
export function apiPedido(rutas: Record<string, Manejador>, { pedido = borrador() as PedidoVista | null, despacho = 'vigente' as Parameters<typeof autorizaciones>[0] } = {}) {
  const pedidas: Pedida[] = []
  const base: Record<string, Manejador> = {
    'GET /consentimientos$': { status: 200, cuerpo: autorizaciones(despacho) },
    'GET /pedido-en-curso$': pedido ? { status: 200, cuerpo: pedido } : NO_ENCONTRADO,
    'GET ^/v1/catalogo$': { status: 200, cuerpo: CATALOGO },
    'GET ^/v1/cuenta$': { status: 200, cuerpo: CUENTA },
  }
  const todas = { ...base, ...rutas }
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const metodo = (config.method ?? 'get').toUpperCase()
    const ruta = config.url ?? ''
    const cuerpo = typeof config.data === 'string' && config.data ? JSON.parse(config.data) : (config.data ?? null)
    const p: Pedida = { metodo, ruta, cabeceras: config.headers.toJSON() as Record<string, unknown>, cuerpo }
    pedidas.push(p)
    const clave = Object.keys(todas).find((k) => {
      const [m, ...e] = k.split(' ')
      return m === metodo && new RegExp(e.join(' ')).test(ruta)
    })
    const h = clave ? todas[clave] : NO_ENCONTRADO
    const r = typeof h === 'function' ? await h(p) : h
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return { pedidas, escrituras: () => pedidas.filter((x) => x.metodo !== 'GET') }
}

/** Una respuesta tras otra en la misma ruta; la última se repite. */
export function enOrden(...respuestas: Respuesta[]): (p: Pedida) => Respuesta {
  let i = 0
  return () => respuestas[Math.min(i++, respuestas.length - 1)]
}

/**
 * Las regiones vivas de main.tsx antes de la pantalla. Se buscan por `aria-live`: la pantalla del
 * pedido también tiene un `role="status"` propio («Cargando…», «Estamos confirmando…»).
 */
export function conRegionesGlobales(pantalla: ReactElement) {
  const { container } = render(createElement(Fragment, null, createElement(RegionesVivas), pantalla))
  return {
    amable: container.querySelector<HTMLElement>('[aria-live="polite"][aria-atomic="true"]')!,
    urgente: container.querySelector<HTMLElement>('[aria-live="assertive"][aria-atomic="true"]')!,
  }
}

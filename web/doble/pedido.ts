// Doble del pedido (MATU-61, contrato docs/api/openapi.json, decisiones 188 a 221) para desarrollo:
// la autorización `despacho`, la dirección con `If-Match`, el carrito, «Si falta», confirmar con 15
// minutos, cambiar, cancelar y las condiciones públicas. Igual que el resto del doble, responde por
// HTTP de verdad, vive en memoria y no entra al build. Datos sintéticos: comercios ficticios.
//
// MATU-62 (decisiones 223 a 248): `pagar`, `…/pago`, `…/pedido-pagado`, `POST /v1/pagos/retorno`, el
// 409 `pago-en-curso` y una página falsa de Webpay (`/__doble/webpay`) donde se elige qué pasa con
// el pago. Ninguna tarjeta es real: Transbank no existe aquí.
import { randomUUID } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { catalogoDoble } from './catalogo'

type Rol = 'admin' | 'cuidador' | 'pagador' | 'observador'
type Regla = 'otro_comercio' | 'quitar'
type Responder = {
  json: (res: ServerResponse, status: number, cuerpo: unknown) => void
  problema: (res: ServerResponse, status: number, tipo: string, extra?: Record<string, unknown>) => void
}

/** Lo que el doble necesita de la persona de familia.ts: su id y su dirección (con `etag`). */
export interface PersonaPedido {
  id: string
  direccion: Record<string, unknown> | null
}
/** Lo que el doble necesita de la cuenta. */
export interface UsuarioPedido {
  id: string
  telefono: string | null
  celularVerificado: boolean
  modo?: string
}

interface Linea {
  id: string
  producto_id: string
  oferta_id: string
  cantidad: number
  precio_carrito: number
  regla: Regla
  /** Al confirmar: el comercio y el precio confirmados. */
  confirmada?: { comercio_id: string; precio: number }
}
interface Pedido {
  id: string
  persona_id: string
  estado: 'borrador' | 'total_confirmado' | 'cancelado' | 'pagado'
  version: number
  lineas: Linea[]
  salieron: { producto_id: string; cantidad: number; comercio_id: string }[]
  vence: number | null
  confirmado_en: string | null
  telefono: { numero: string; origen: 'celular_cuenta' | 'escrito'; de: string } | null
  entrega: Record<string, unknown> | null
  creado_en: string
  actualizado_en: string
  /** MATU-62: el pago aprobado, si lo hay. */
  pagado?: Pagado
  /** MATU-62: las anulaciones de este pedido (también la de un pago tardío que no lo pagó). */
  devoluciones?: DevolucionDoble[]
}
type EstadoDespacho = 'no' | 'vigente' | 'vencida' | 'retirada'
interface Despacho {
  estado: EstadoDespacho
  otorgado_en: string | null
  revocado_en: string | null
}

const COSTO_ENVIO = 3990
const VIGENCIA_MS = 15 * 60_000
const VENTANA = 'Entre 24 y 48 horas hábiles'
const CANAL_RECLAMO = 'cuidaconmatu@gmail.com'
const hace = (min: number) => new Date(Date.now() - min * 60_000).toISOString()

const despachos = new Map<string, Despacho>()
const pedidos = new Map<string, Pedido>()
/** El pedido en curso de cada persona (C4: uno sin pagar por persona). */
const enCurso = new Map<string, string>()
const conflictosDireccion = new Set<string>()

// ---------------------------------------------------------------- el catálogo como lo ve el pedido

interface OfertaDoble {
  oferta_id: string
  comercio_id: string
  nombre_fantasia: string
  precio: number
  disponible: boolean
  ficticio?: boolean
}
interface ProductoDoble {
  id: string
  nombre: string
  presentacion: string
  unidad: string
  unidades_por_envase: number
  retracto_pierde_al_abrir: boolean
  comercios: OfertaDoble[]
}
const productos = (): ProductoDoble[] => catalogoDoble().categorias.flatMap((c) => c.productos as ProductoDoble[])
const productoDe = (id: string) => productos().find((p) => p.id === id)
const ofertaDe = (ofertaId: string) => {
  for (const p of productos()) for (const o of p.comercios) if (o.oferta_id === ofertaId) return { producto: p, oferta: o }
  return null
}
const comercioDe = (id: string) => {
  for (const p of productos()) for (const o of p.comercios) if (o.comercio_id === id) return { id, nombre_fantasia: o.nombre_fantasia, ficticio: o.ficticio ?? true }
  return { id, nombre_fantasia: 'Comercio de ejemplo', ficticio: true }
}

/** El id de un producto del catálogo del doble por el comienzo de su nombre (las semillas lo usan). */
export const productoDelCatalogo = (nombre: string) => productos().find((p) => p.nombre.startsWith(nombre))?.id ?? null

// ---------------------------------------------------------------- semillas

/** La autorización `despacho` de una persona para una cuenta de ejemplo. */
export function sembrarDespacho(personaId: string, estado: EstadoDespacho) {
  const otorgado = estado === 'no' ? null : estado === 'vencida' ? hace(400 * 24 * 60) : hace(2 * 24 * 60)
  despachos.set(personaId, { estado, otorgado_en: otorgado, revocado_en: estado === 'retirada' ? hace(24 * 60) : null })
}

/** Un pedido de ejemplo en borrador con estos productos (por nombre), o ya confirmado. */
export function sembrarPedido(personaId: string, productosPorNombre: [string, number, Regla?][], confirmado = false) {
  const lineas: Linea[] = []
  for (const [nombre, cantidad, regla] of productosPorNombre) {
    const p = productos().find((x) => x.nombre.startsWith(nombre))
    const o = p?.comercios.find((x) => x.disponible) ?? p?.comercios[0]
    if (!p || !o) continue
    lineas.push({ id: randomUUID(), producto_id: p.id, oferta_id: o.oferta_id, cantidad, precio_carrito: o.precio, regla: regla ?? 'otro_comercio' })
  }
  const ahora = new Date().toISOString()
  const pedido: Pedido = { id: randomUUID(), persona_id: personaId, estado: 'borrador', version: 1, lineas, salieron: [], vence: null, confirmado_en: null, telefono: null, entrega: null, creado_en: ahora, actualizado_en: ahora }
  if (confirmado) {
    for (const l of pedido.lineas) l.confirmada = { comercio_id: ofertaDe(l.oferta_id)!.oferta.comercio_id, precio: l.precio_carrito }
    pedido.estado = 'total_confirmado'
    pedido.vence = Date.now() + VIGENCIA_MS
    pedido.confirmado_en = ahora
    pedido.telefono = { numero: '+56955550137', origen: 'celular_cuenta', de: 'otra-cuenta' }
    pedido.entrega = { calle: 'Los Aromos', numero: '123', depto: '4', comuna: 'La Reina', region: 'Metropolitana', referencia: 'Portón verde' }
  }
  pedidos.set(pedido.id, pedido)
  enCurso.set(personaId, pedido.id)
}

// ---------------------------------------------------------------- vistas

const vencido = (p: Pedido) => p.estado === 'total_confirmado' && p.vence !== null && p.vence <= Date.now()
const estadoDe = (p: Pedido) => (vencido(p) ? 'vencido' : p.estado)
const etagDe = (p: Pedido) => `"p${p.version}"`
const enmascarar = (tel: string) => `+56 9 •••• ••${tel.slice(-2)}`

function vistaLinea(l: Linea, confirmada: boolean) {
  const producto = productoDe(l.producto_id)!
  const carrito = ofertaDe(l.oferta_id)!.oferta
  const comercioId = confirmada && l.confirmada ? l.confirmada.comercio_id : carrito.comercio_id
  const precio = confirmada && l.confirmada ? l.confirmada.precio : l.precio_carrito
  const cambio =
    confirmada && l.confirmada && (l.confirmada.precio !== l.precio_carrito || l.confirmada.comercio_id !== carrito.comercio_id)
      ? { precio_antes: l.confirmada.precio !== l.precio_carrito ? l.precio_carrito : null, comercio_antes: l.confirmada.comercio_id !== carrito.comercio_id ? comercioDe(carrito.comercio_id) : null }
      : null
  return {
    id: l.id,
    // Decisión 222: la oferta del carrito, que la pantalla reenvía en PUT …/lineas.
    oferta_id: l.oferta_id,
    producto: { id: producto.id, nombre: producto.nombre, presentacion: producto.presentacion, unidad: producto.unidad, unidades_por_envase: producto.unidades_por_envase },
    cantidad: l.cantidad,
    comercio: comercioDe(comercioId),
    precio_unitario: precio,
    subtotal: precio * l.cantidad,
    regla_faltante: l.regla,
    retracto_pierde_al_abrir: producto.retracto_pierde_al_abrir,
    cambio,
    devolucion: null,
  }
}

function vista(p: Pedido, rol: Rol, u: UsuarioPedido) {
  const confirmada = p.estado === 'total_confirmado' || p.estado === 'pagado'
  const vigente = p.estado === 'total_confirmado'
  const lineas = p.lineas.map((l) => vistaLinea(l, confirmada))
  const subtotal = lineas.reduce((t, l) => t + l.subtotal, 0)
  const partes = new Map<string, number>()
  for (const l of lineas) partes.set(l.comercio.id, (partes.get(l.comercio.id) ?? 0) + l.subtotal)
  const salieron = p.salieron.map((s) => {
    const producto = productoDe(s.producto_id)!
    return {
      producto: { id: producto.id, nombre: producto.nombre, presentacion: producto.presentacion, unidad: producto.unidad, unidades_por_envase: producto.unidades_por_envase },
      cantidad: s.cantidad,
      comercio: comercioDe(s.comercio_id),
    }
  })
  const base = {
    id: p.id,
    persona_cuidada_id: p.persona_id,
    estado: estadoDe(p),
    precios_de_ejemplo: true,
    lineas,
    salieron,
    comercios: [...partes].map(([id, s]) => ({ comercio: comercioDe(id), subtotal_productos: s })),
    subtotal_productos: subtotal,
    costo_envio: COSTO_ENVIO,
    total: confirmada ? subtotal + COSTO_ENVIO : null,
    total_confirmado_en: p.confirmado_en,
    vence_en: p.vence ? new Date(p.vence).toISOString() : null,
    ventana_entrega: VENTANA,
    creado_en: p.creado_en,
    actualizado_en: p.actualizado_en,
    // MATU-62 (decisión 230)
    pago_en_curso: pagoEnCurso(p),
    pagado_en: p.pagado?.pagado_en ?? null,
  }
  if (rol === 'observador') return base
  const tel = p.telefono
  return {
    ...base,
    etag: etagDe(p),
    vigencia_segundos: vigente && p.vence ? Math.max(0, Math.round((p.vence - Date.now()) / 1000)) : null,
    entrega:
      confirmada && p.entrega && tel
        ? {
            ...(p.entrega as object),
            telefono_contacto: tel.origen === 'celular_cuenta' ? enmascarar(tel.numero) : tel.numero,
            telefono_origen: tel.origen,
            telefono_es_tuyo: tel.de === u.id,
          }
        : null,
    resumen: vigente
      ? {
          vendedor: 'MATU, piloto académico, sin persona jurídica',
          boleta: 'En este piloto no se emite boleta',
          ventana_entrega: VENTANA,
          canal_reclamo: CANAL_RECLAMO,
          condiciones: { version: '0.1', huella: HUELLA_CONDICIONES, enlace: '/v1/condiciones-pedido' },
        }
      : null,
  }
}

// ---------------------------------------------------------------- las autorizaciones

/** El ítem `despacho` de `GET …/consentimientos` (decisión 192). */
export function vistaDespacho(personaId: string, rol: Rol) {
  const d = despachos.get(personaId) ?? { estado: 'no', otorgado_en: null, revocado_en: null }
  const calidad = rol === 'admin' || rol === 'cuidador' ? { calidad_otorgante: d.estado === 'no' ? null : 'cuidador_de_hecho' } : {}
  const estado = { no: 'sin_autorizar', vigente: 'vigente', vencida: 'revision_vencida', retirada: 'retirada' }[d.estado]
  const revision = d.estado === 'vencida' && d.otorgado_en ? new Date(new Date(d.otorgado_en).getTime() + 365 * 86_400_000).toISOString() : null
  return { finalidad: 'despacho', estado, id: d.estado === 'no' ? null : `${personaId}-despacho`, ...calidad, otorgado_en: d.otorgado_en, revision_vence_en: revision, revocado_en: d.revocado_en, borrado_en: null, borrada: false }
}

/** `POST …/consentimientos` con `despacho`: la huella de la declaración, obligatoria (decisión 192). */
export function otorgarDespacho(res: ServerResponse, b: Record<string, unknown>, personaId: string, { json, problema }: Responder) {
  const mal = (campo: string, tipo: string) => problema(res, 422, '/errores/validacion', { errores: [{ campo, mensaje: 'MENSAJE DEL DOBLE: NO SE MUESTRA', tipo }] })
  const calidad = b.calidad_otorgante
  if (!['titular', 'representante_legal', 'cuidador_de_hecho'].includes(String(calidad))) return mal('calidad_otorgante', 'enum')
  if (typeof b.huella_declaracion !== 'string' || !/^[0-9a-f]{64}$/.test(b.huella_declaracion)) return mal('huella_declaracion', 'declaracion_no_vigente')
  const d = despachos.get(personaId)
  if (d?.estado === 'vigente') return problema(res, 409, '/errores/autorizacion-vigente')
  const ahora = new Date().toISOString()
  despachos.set(personaId, { estado: 'vigente', otorgado_en: ahora, revocado_en: null })
  return json(res, 201, {
    consentimiento: { id: randomUUID(), calidad_otorgante: calidad, finalidad: 'despacho', version_politica: '0.12', otorgado_en: ahora, revision_vence_en: null },
    aviso: null,
  })
}

/** `POST …/consentimientos/despacho/retiro`: cancela lo no pagado y borra su entrega; la dirección queda (C6). */
export function retirarDespacho(res: ServerResponse, personaId: string, rol: Rol, { json, problema }: Responder) {
  const d = despachos.get(personaId)
  if (!d || d.estado === 'no') return problema(res, 404, '/errores/no-encontrado')
  if (d.estado === 'retirada') return problema(res, 409, '/errores/ya-retirada')
  d.estado = 'retirada'
  d.revocado_en = new Date().toISOString()
  let cancelados = 0
  const id = enCurso.get(personaId)
  if (id) {
    const p = pedidos.get(id)!
    p.estado = 'cancelado'
    p.entrega = null
    enCurso.delete(personaId)
    cancelados = 1
  }
  return json(res, 200, { autorizacion: vistaDespacho(personaId, rol), enlaces_cortados: 0, pedidos_cancelados: cancelados })
}

// ---------------------------------------------------------------- las rutas

const editor = (rol: Rol) => rol === 'admin' || rol === 'cuidador'

/** Atiende la dirección y el pedido. `false` si la ruta no es suya. */
export function atenderPedido(
  req: IncomingMessage,
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  r: Responder,
  u: UsuarioPedido,
  rol: Rol | null,
  personaDe: (id: string) => PersonaPedido | null,
): boolean {
  const { json, problema } = r
  const metodo = req.method ?? 'GET'
  const ruta = (req.url ?? '').split('?')[0]
  const mDir = /^\/v1\/personas-cuidadas\/([^/]+)\/direccion$/.exec(ruta)
  const mPersona = /^\/v1\/personas-cuidadas\/([^/]+)\/(pedidos|pedido-en-curso|pedido-pagado)$/.exec(ruta)
  const mPedido = /^\/v1\/pedidos\/([^/]+)(?:\/(lineas|reglas-faltante|confirmar|contacto|cambiar|cancelar|pagar|pago))?$/.exec(ruta)
  if (!mDir && !mPersona && !mPedido) return false
  res.setHeader('Cache-Control', 'no-store')
  const no = () => (problema(res, 404, '/errores/no-encontrado'), true)
  if (!rol) return no()
  const mal = (campo: string, tipo: string) => (problema(res, 422, '/errores/validacion', { errores: [{ campo, mensaje: 'MENSAJE DEL DOBLE: NO SE MUESTRA', tipo }] }), true)

  // ------------------------------------------------ la dirección (decisiones 189 a 191, 216 y 219)
  if (mDir) {
    const p = personaDe(decodeURIComponent(mDir[1]))
    if (!p || !editor(rol)) return no()
    const actual = p.direccion
    const ifMatch = req.headers['if-match']
    const ifNone = req.headers['if-none-match']
    if (metodo === 'DELETE') {
      if (!actual) return no()
      if (!ifMatch || ifMatch === '*') return problema(res, 428, '/errores/falta-version'), true
      if (ifMatch !== actual.etag) return problema(res, 412, '/errores/version-desactualizada', { actual }), true
      p.direccion = null
      res.statusCode = 204
      return res.end(), true
    }
    if (metodo !== 'PUT') return no()
    if ((!ifMatch && !ifNone) || ifMatch === '*') return problema(res, 428, '/errores/falta-version'), true
    // Cuenta «pedido-conflicto»: otra persona cambia la dirección justo antes del primer guardado.
    if (u.modo === 'pedido-conflicto' && !conflictosDireccion.has(p.id)) {
      conflictosDireccion.add(p.id)
      p.direccion = { etiqueta: 'Casa', calle: 'Los Aromos', numero: '125', depto: null, comuna: 'La Reina', region: 'Metropolitana', referencia: null, etag: `"v${Date.now()}"` }
    }
    const vigente = p.direccion
    if ((ifNone && vigente) || (ifMatch && ifMatch !== vigente?.etag)) return problema(res, 412, '/errores/version-desactualizada', { actual: vigente }), true
    const b = cuerpo ?? {}
    for (const [campo, largo, requerido] of [['calle', 120, true], ['numero', 20, true], ['depto', 20, false], ['comuna', 60, true], ['referencia', 200, false]] as const) {
      const v = b[campo]
      if (requerido && (typeof v !== 'string' || !v.trim())) return mal(campo, 'string_too_short')
      if (typeof v === 'string' && v.length > largo) return mal(campo, 'string_too_long')
    }
    if ('lat' in b || 'lng' in b) return mal('lat', 'extra_forbidden')
    p.direccion = {
      etiqueta: typeof b.etiqueta === 'string' ? b.etiqueta : 'Casa',
      calle: b.calle,
      numero: b.numero,
      depto: b.depto ?? null,
      comuna: b.comuna,
      region: typeof b.region === 'string' ? b.region : 'Metropolitana',
      referencia: b.referencia ?? null,
      etag: `"v${Date.now()}"`,
    }
    res.setHeader('ETag', String(p.direccion.etag))
    return json(res, 200, p.direccion), true
  }

  const sinPermiso = (personaId: string) => {
    const d = despachos.get(personaId)?.estado ?? 'no'
    if (d === 'vigente') return false
    if (d === 'vencida') problema(res, 403, '/errores/revision-vencida', { finalidad: 'despacho' })
    else problema(res, 403, '/errores/sin-autorizacion-pedidos', { finalidad: 'despacho' })
    return true
  }
  const conVista = (status: number, p: Pedido) => {
    res.setHeader('ETag', etagDe(p))
    return json(res, status, vista(p, rol, u)), true
  }
  const lineasDe = (b: Record<string, unknown> | null, anteriores: Linea[] = []): Linea[] | null => {
    const pedidas = Array.isArray(b?.lineas) ? (b!.lineas as { oferta_id?: unknown; cantidad?: unknown }[]) : null
    if (!pedidas) return (mal('lineas', 'missing'), null)
    const salida: Linea[] = []
    for (const [i, x] of pedidas.entries()) {
      const o = typeof x.oferta_id === 'string' ? ofertaDe(x.oferta_id) : null
      if (!o) return (mal(`lineas.${i}.oferta_id`, 'oferta_no_disponible'), null)
      if (typeof x.cantidad !== 'number' || !Number.isInteger(x.cantidad) || x.cantidad < 1 || x.cantidad > 99) return (mal(`lineas.${i}.cantidad`, 'less_than_equal'), null)
      if (salida.some((l) => l.producto_id === o.producto.id)) return (mal(`lineas.${i}.oferta_id`, 'producto_repetido'), null)
      const antes = anteriores.find((l) => l.producto_id === o.producto.id)
      salida.push({
        id: antes?.id ?? randomUUID(),
        producto_id: o.producto.id,
        oferta_id: o.oferta.oferta_id,
        cantidad: x.cantidad,
        precio_carrito: antes && antes.oferta_id === o.oferta.oferta_id ? antes.precio_carrito : o.oferta.precio,
        regla: antes?.regla ?? 'otro_comercio',
      })
    }
    return salida
  }
  const tocar = (p: Pedido) => {
    p.version += 1
    p.actualizado_en = new Date().toISOString()
  }

  // ------------------------------------------------ crear y leer el pedido en curso (196 y 197)
  if (mPersona) {
    const personaId = decodeURIComponent(mPersona[1])
    if (!personaDe(personaId)) return no()
    // MATU-62 (decisión 237): el último pedido pagado de la persona.
    if (mPersona[2] === 'pedido-pagado') {
      if (metodo !== 'GET') return no()
      const id = ultimoPagado.get(personaId)
      const p = id ? pedidos.get(id) : undefined
      if (!p) return no()
      return json(res, 200, vistaPago(p, rol, u)), true
    }
    if (mPersona[2] === 'pedido-en-curso') {
      if (metodo !== 'GET') return no()
      const id = enCurso.get(personaId)
      const p = id ? pedidos.get(id) : undefined
      if (!p) return no()
      return conVista(200, p)
    }
    if (metodo !== 'POST' || !editor(rol)) return no()
    if (sinPermiso(personaId)) return true
    if (!req.headers['idempotency-key']) return problema(res, 428, '/errores/falta-idempotencia'), true
    const abierto = enCurso.get(personaId)
    if (abierto) return problema(res, 409, '/errores/pedido-abierto', { pedido_id: abierto }), true
    const lineas = lineasDe(cuerpo)
    if (!lineas) return true
    const ahora = new Date().toISOString()
    const p: Pedido = { id: randomUUID(), persona_id: personaId, estado: 'borrador', version: 1, lineas, salieron: [], vence: null, confirmado_en: null, telefono: null, entrega: null, creado_en: ahora, actualizado_en: ahora }
    pedidos.set(p.id, p)
    enCurso.set(personaId, p.id)
    res.setHeader('Location', `/v1/pedidos/${p.id}`)
    return conVista(201, p)
  }

  // ------------------------------------------------ operar un pedido (198 a 206 y 218)
  const p = mPedido ? pedidos.get(decodeURIComponent(mPedido[1])) : undefined
  if (!p || !personaDe(p.persona_id)) return no()
  const accion = mPedido![2]
  if (!accion) return metodo === 'GET' ? conVista(200, p) : no()
  // MATU-62 (decisión 236): el pago, con la vista de cada rol. No pide la autorización.
  if (accion === 'pago') return metodo === 'GET' ? (json(res, 200, vistaPago(p, rol, u)), true) : no()
  if (accion === 'pagar') return pagar(req, res, cuerpo, r, u, rol, p, sinPermiso), true
  if (!editor(rol)) return no()
  const estado = estadoDe(p)
  const transicion = () => (problema(res, 409, '/errores/estado-pedido', { estado }), true)

  if (accion === 'cancelar') {
    if (metodo !== 'POST') return no()
    if (!req.headers['idempotency-key']) return problema(res, 428, '/errores/falta-idempotencia'), true
    if (p.estado === 'cancelado') return transicion()
    p.estado = 'cancelado'
    p.entrega = null
    enCurso.delete(p.persona_id)
    tocar(p)
    return conVista(200, p)
  }
  if (sinPermiso(p.persona_id)) return true
  // MATU-62 (D-62-4, regla 1): con un pago en curso nadie cambia el pedido. Cancelar sí (arriba).
  if (pagoEnCurso(p)) return problema(res, 409, '/errores/pago-en-curso'), true
  const ifMatch = req.headers['if-match']
  const conIfMatch = accion === 'lineas' || accion === 'reglas-faltante' || accion === 'contacto'
  if (conIfMatch) {
    if (metodo !== 'PUT') return no()
    if (!ifMatch) return problema(res, 428, '/errores/falta-version'), true
    if (ifMatch !== etagDe(p)) return res.setHeader('ETag', etagDe(p)), problema(res, 412, '/errores/version-desactualizada', { actual: vista(p, rol, u) }), true
  } else if (metodo !== 'POST' || !req.headers['idempotency-key']) return problema(res, 428, '/errores/falta-idempotencia'), true

  if (accion === 'lineas') {
    if (estado !== 'borrador') return transicion()
    const lineas = lineasDe(cuerpo, p.lineas)
    if (!lineas) return true
    p.lineas = lineas
    tocar(p)
    return conVista(200, p)
  }
  if (accion === 'reglas-faltante') {
    if (p.estado === 'cancelado') return transicion()
    const reglas = Array.isArray(cuerpo?.reglas) ? (cuerpo!.reglas as { producto_id?: unknown; accion?: unknown }[]) : []
    for (const l of p.lineas) l.regla = 'otro_comercio'
    for (const [i, x] of reglas.entries()) {
      const l = p.lineas.find((y) => y.producto_id === x.producto_id)
      if (!l) return mal(`reglas.${i}.producto_id`, 'producto_no_esta')
      if (x.accion !== 'otro_comercio' && x.accion !== 'quitar') return mal(`reglas.${i}.accion`, 'enum')
      l.regla = x.accion
    }
    tocar(p)
    return conVista(200, p)
  }
  if (accion === 'contacto') {
    if (estado === 'borrador' || p.estado === 'cancelado') return transicion()
    const t = cuerpo?.telefono_contacto
    if (typeof t !== 'string' || !/^(\+?56 ?)?9( ?[0-9]){8}$/.test(t.trim())) return mal('telefono_contacto', 'celular_invalido')
    p.telefono = { numero: `+569${t.replace(/\D/g, '').slice(-8)}`, origen: 'escrito', de: u.id }
    tocar(p)
    return conVista(200, p)
  }
  if (accion === 'cambiar') {
    if (estado !== 'total_confirmado' && estado !== 'vencido') return transicion()
    // Las que salieron vuelven al carrito con su precio del carrito (decisión 218).
    for (const s of p.salieron) {
      const producto = productoDe(s.producto_id)!
      const o = producto.comercios.find((x) => x.comercio_id === s.comercio_id) ?? producto.comercios[0]
      p.lineas.push({ id: randomUUID(), producto_id: s.producto_id, oferta_id: o.oferta_id, cantidad: s.cantidad, precio_carrito: o.precio, regla: 'otro_comercio' })
    }
    for (const l of p.lineas) delete l.confirmada
    p.salieron = []
    p.estado = 'borrador'
    p.vence = null
    p.confirmado_en = null
    p.entrega = null
    tocar(p)
    return conVista(200, p)
  }
  // confirmar (201 a 205)
  if (p.estado === 'cancelado' || p.estado === 'pagado') return transicion()
  if (u.modo === 'pedido-falla') return problema(res, 503, '/errores/servicio-no-disponible'), true
  const persona = personaDe(p.persona_id)!
  if (!persona.direccion) return problema(res, 409, '/errores/sin-direccion'), true
  // Las que salieron la vez anterior se vuelven a consultar.
  for (const s of p.salieron) {
    const producto = productoDe(s.producto_id)!
    const o = producto.comercios.find((x) => x.comercio_id === s.comercio_id) ?? producto.comercios[0]
    p.lineas.push({ id: randomUUID(), producto_id: s.producto_id, oferta_id: o.oferta_id, cantidad: s.cantidad, precio_carrito: o.precio, regla: 'otro_comercio' })
  }
  p.salieron = []
  if (!p.lineas.length) return problema(res, 409, '/errores/pedido-vacio'), true
  const quedan: Linea[] = []
  for (const l of p.lineas) {
    const producto = productoDe(l.producto_id)!
    const propia = ofertaDe(l.oferta_id)!.oferta
    // Cuenta «pedido-cambios»: la primera línea cambia de precio, la segunda de comercio y la tercera sale.
    const i = p.lineas.indexOf(l)
    const cambios = u.modo === 'pedido-cambios'
    if (propia.disponible && !(cambios && i >= 1)) {
      l.confirmada = { comercio_id: propia.comercio_id, precio: cambios && i === 0 ? propia.precio - 540 : propia.precio }
      quedan.push(l)
      continue
    }
    const otra = l.regla === 'otro_comercio' && !(cambios && i >= 2) ? [...producto.comercios].filter((o) => o.comercio_id !== propia.comercio_id).sort((a, b) => a.precio - b.precio)[0] : undefined
    if (otra) {
      l.confirmada = { comercio_id: otra.comercio_id, precio: otra.precio }
      quedan.push(l)
    } else p.salieron.push({ producto_id: l.producto_id, cantidad: l.cantidad, comercio_id: propia.comercio_id })
  }
  if (!quedan.length) {
    for (const l of p.lineas) delete l.confirmada
    p.salieron = []
    return problema(res, 409, '/errores/nada-disponible'), true
  }
  p.lineas = quedan
  const t = cuerpo?.telefono_contacto
  if (typeof t === 'string') {
    if (!/^(\+?56 ?)?9( ?[0-9]){8}$/.test(t.trim())) return mal('telefono_contacto', 'celular_invalido')
    p.telefono = { numero: `+569${t.replace(/\D/g, '').slice(-8)}`, origen: 'escrito', de: u.id }
  } else if (!p.telefono) {
    if (!u.celularVerificado || !u.telefono) return mal('telefono_contacto', 'telefono_requerido')
    p.telefono = { numero: u.telefono, origen: 'celular_cuenta', de: u.id }
  }
  const { etag: _etag, etiqueta: _etiqueta, ...dir } = persona.direccion
  p.entrega = dir
  p.estado = 'total_confirmado'
  // Cuenta «pedido-plazo»: el total vale 130 s, para ver el aviso de los 2 minutos a los 10 s.
  p.vence = Date.now() + (u.modo === 'pedido-plazo' ? 130_000 : VIGENCIA_MS)
  p.confirmado_en = new Date().toISOString()
  tocar(p)
  return conVista(200, p)
}

// ---------------------------------------------------------------- las condiciones (decisión 207)

const TEXTO_CONDICIONES = `## 1. Quién vende

Vende MATU, piloto académico, sin persona jurídica. En este piloto no se emite boleta.

## 2. El total

Antes de pagar ves el total exacto: los productos con su precio y un solo envío. Todos los precios llevan el IVA incluido. El total vale 15 minutos.

## 3. Si falta un producto

Si al retirar falta un producto, lo buscamos en otro comercio y pagas lo mismo. Si nadie lo tiene, o elegiste sacarlo, anulamos su cobro el mismo día, a la misma tarjeta.

## 4. Nunca otra marca

Nunca cambiamos un producto por otra marca ni por otro producto.

## 5. Reclamos

Escríbenos a ${CANAL_RECLAMO}.
`
const HUELLA_CONDICIONES = 'c0ffee0000000000000000000000000000000000000000000000000000000001'
const VERSION_CONDICIONES = '0.1'

/** `GET /v1/condiciones-pedido`: pública, sin mirar cookies ni token. `true` si la ruta era suya. */
export function atenderCondiciones(metodo: string, url: string, res: ServerResponse): boolean {
  const [ruta, query] = url.split('?')
  if (ruta !== '/v1/condiciones-pedido' || metodo !== 'GET') return false
  // MATU-62 (decisión 240): `?version=` da esa versión publicada; el doble solo publicó la 0.1.
  const version = new URLSearchParams(query ?? '').get('version')
  if (version !== null && version !== VERSION_CONDICIONES) {
    res.statusCode = 404
    res.setHeader('Content-Type', 'application/problem+json')
    res.end(JSON.stringify({ type: '/errores/no-encontrado', title: 'TITLE DEL DOBLE: NO SE MUESTRA', status: 404, detail: null, errores: [], request_id: null }))
    return true
  }
  res.statusCode = 200
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Content-Type', 'application/json')
  res.end(JSON.stringify({ version: '0.1', actualizada_en: '2026-11-11', huella: HUELLA_CONDICIONES, texto: TEXTO_CONDICIONES }))
  return true
}

// ---------------------------------------------------------------- MATU-62: el pago

/**
 * Qué pasa en la página falsa de Webpay. Se elige en `/__doble/webpay` y lo aplica la vuelta. Ningún
 * número de tarjeta: solo el tipo, los últimos 4 de ejemplo y las cuotas, como los da Transbank.
 */
type Opcion =
  | 'debito'
  | 'credito'
  | 'prepago'
  | 'no_aprobado'
  | 'abandonado'
  | 'tiempo_agotado'
  | 'pendiente'
  | 'tardio'
  | 'anulado'
  | 'anulando'
  | 'sin_sesion'
  | 'desconocido'

const OPCIONES: [Opcion, string][] = [
  ['debito', 'Pagar con débito (aprobado) → «Pagaste tu pedido»'],
  ['credito', 'Pagar con crédito en 3 cuotas (aprobado)'],
  ['prepago', 'Pagar con prepago (aprobado)'],
  ['no_aprobado', 'El banco no lo aprueba → «El pago no se hizo»'],
  ['abandonado', 'Anular compra (vuelve por POST, con TBK_*) → «Saliste de Webpay sin pagar»'],
  ['tiempo_agotado', 'Se acaba el tiempo del formulario → «Se acabó el tiempo…»'],
  ['pendiente', 'Transbank no responde: «pendiente» durante 25 s y después aprobado (7.3)'],
  ['tardio', 'Aprobado después de que venció el total, y se respeta (7.6)'],
  ['anulado', 'Aprobado de un total que cambió: anulación hecha (7.9)'],
  ['anulando', 'Aprobado de un total que cambió: anulación en curso (7.9)'],
  ['sin_sesion', 'Aprobado, con la vuelta como si fuera de otra cuenta (7.10)'],
  ['desconocido', 'Vuelve con un token que no es de MATU (404)'],
]

interface Venta {
  id: string
  token: string
  orden: string
  sesion: string
  pedido_id: string
  /** La cuenta que tocó «Pagar». */
  quien: string
  creada: number
  /** El total al que quedó atada (D-62-4). */
  total_confirmado_en: string | null
  estado: 'iniciada' | 'autorizando' | 'aprobada' | 'rechazada'
  opcion: Opcion | null
  resultado: string | null
  anulacion: 'hecha' | 'en_curso' | null
  primeraVuelta: number | null
  clave: string
}
interface Tarjeta {
  tipo: 'debito' | 'credito' | 'prepago'
  ultimos4: string
  cuotas: number
}
interface Pagado {
  referencia: string
  pagado_en: string
  quien: string
  tarjeta: Tarjeta
  codigo: string
  aceptadas_en: string
  tardio: boolean
}
interface DevolucionDoble {
  motivo: 'pago_tardio' | 'producto_no_entregado' | 'cancelacion'
  monto: number
  producto_id: string | null
  estado: 'en_curso' | 'hecha'
  solicitada_en: string
  hecha_en: string | null
  ultimos4: string
  /** Quien pagó: solo esa cuenta ve los últimos 4 (D-62-2). */
  de: string
}

/** Decisión 230: una venta iniciada vale 10 minutos; una que espera el `commit`, hasta que se cierre. */
const VIDA_VENTA_MS = 10 * 60_000
const PENDIENTE_MS = 25_000
const ventas = new Map<string, Venta>()
const ultimoPagado = new Map<string, string>()
const condicionesUsadas = new Set<string>()
const RUTA_WEBPAY = '/__doble/webpay'

const ventasDe = (p: Pedido) => [...ventas.values()].filter((v) => v.pedido_id === p.id).sort((a, b) => a.creada - b.creada)
function pagoEnCurso(p: Pedido): boolean {
  return ventasDe(p).some((v) => v.estado === 'autorizando' || (v.estado === 'iniciada' && Date.now() - v.creada < VIDA_VENTA_MS))
}
const tarjetaDe = (o: Opcion | null): Tarjeta =>
  o === 'credito' ? { tipo: 'credito', ultimos4: '4051', cuotas: 3 } : o === 'prepago' ? { tipo: 'prepago', ultimos4: '7720', cuotas: 0 } : { tipo: 'debito', ultimos4: '4051', cuotas: 0 }
const totalDe = (p: Pedido) => p.lineas.reduce((t, l) => t + (l.confirmada?.precio ?? l.precio_carrito) * l.cantidad, 0) + COSTO_ENVIO
const aleatorio = (n: number) => String(Math.floor(Math.random() * 10 ** n)).padStart(n, '0')

function aprobar(p: Pedido, quien: string, tarjeta: Tarjeta, tardio: boolean, cuando = new Date()) {
  p.estado = 'pagado'
  p.pagado = { referencia: aleatorio(4), pagado_en: cuando.toISOString(), quien, tarjeta, codigo: aleatorio(6), aceptadas_en: new Date(cuando.getTime() - 3 * 60_000).toISOString(), tardio }
  p.entrega = p.entrega ?? { calle: 'Los Aromos', numero: '123', depto: '4', comuna: 'La Reina', region: 'Metropolitana', referencia: 'Portón verde' }
  enCurso.delete(p.persona_id)
  ultimoPagado.set(p.persona_id, p.id)
  p.version += 1
}

function vistaDevolucion(d: DevolucionDoble, u: UsuarioPedido) {
  const producto = d.producto_id ? productoDe(d.producto_id) : null
  return {
    motivo: d.motivo,
    monto: d.monto,
    producto: producto ? { id: producto.id, nombre: producto.nombre, presentacion: producto.presentacion, unidad: producto.unidad, unidades_por_envase: producto.unidades_por_envase } : null,
    estado: d.estado,
    solicitada_en: d.solicitada_en,
    hecha_en: d.hecha_en,
    ultimos4: d.de === u.id ? d.ultimos4 : null,
  }
}

/** `PagoVista` o `PagoVistaObservador` (decisión 236). La tarjeta, el código y el correo, solo para quien pagó. */
function vistaPago(p: Pedido, rol: Rol, u: UsuarioPedido) {
  if (rol === 'observador') return { pedido_id: p.id, estado: p.pagado ? 'pagado' : 'sin_pagar' }
  const vs = ventasDe(p)
  const ultima = vs[vs.length - 1]
  const devoluciones = (p.devoluciones ?? []).map((d) => vistaDevolucion(d, u))
  const pg = p.pagado
  const parcial = (p.devoluciones ?? []).some((d) => d.estado === 'hecha' && d.motivo !== 'pago_tardio')
  const estado = pg ? (parcial ? 'devuelto_parcial' : 'aprobado') : !ultima ? 'sin_intento' : ultima.estado === 'rechazada' ? 'no_aprobado' : ultima.estado === 'aprobada' ? 'anulado' : 'pendiente'
  const tuyo = !!pg && pg.quien === u.id
  const lineas = p.lineas.map((l) => vistaLinea(l, true))
  const subtotal = lineas.reduce((t, l) => t + l.subtotal, 0)
  return {
    pedido_id: p.id,
    estado,
    pago_en_curso: pagoEnCurso(p),
    pago_de_prueba: true,
    intento: ultima
      ? {
          id: ultima.id,
          resultado: ultima.estado === 'iniciada' ? 'en_webpay' : ultima.estado === 'autorizando' ? 'pendiente' : (ultima.resultado ?? 'pendiente'),
          iniciado_en: new Date(ultima.creada).toISOString(),
          cerrado_en: ultima.estado === 'aprobada' || ultima.estado === 'rechazada' ? new Date().toISOString() : null,
          es_tuyo: ultima.quien === u.id,
        }
      : null,
    devoluciones,
    comprobante: pg
      ? {
          referencia: pg.referencia,
          pagado_en: pg.pagado_en,
          lineas: lineas.map((l) => ({ producto: l.producto, cantidad: l.cantidad, precio_unitario: l.precio_unitario, subtotal: l.subtotal })),
          subtotal_productos: subtotal,
          costo_envio: COSTO_ENVIO,
          total: subtotal + COSTO_ENVIO,
          pagaste_tu: tuyo,
          tarjeta: tuyo ? pg.tarjeta : null,
          codigo_autorizacion: tuyo ? pg.codigo : null,
          vendedor: 'MATU, piloto académico, sin persona jurídica',
          ventana_entrega: VENTANA,
          canal_reclamo: CANAL_RECLAMO,
          condiciones: { version: VERSION_CONDICIONES, aceptadas_en: pg.aceptadas_en, huella: HUELLA_CONDICIONES, enlace: `/v1/condiciones-pedido?version=${VERSION_CONDICIONES}` },
          tardio: pg.tardio,
          devoluciones,
          precios_de_ejemplo: true,
          pago_de_prueba: true,
          correo: tuyo ? { destino: `${u.id.slice(0, 8)}@example.com`, enviado: false } : null,
        }
      : null,
  }
}

/** `POST /v1/pedidos/{id}/pagar` (decisiones 224 a 230), con su orden de errores. */
function pagar(
  req: IncomingMessage,
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  { json, problema }: Responder,
  u: UsuarioPedido,
  rol: Rol,
  p: Pedido,
  sinPermiso: (personaId: string) => boolean,
) {
  if (req.method !== 'POST' || (rol !== 'admin' && rol !== 'pagador')) return problema(res, 404, '/errores/no-encontrado')
  if (sinPermiso(p.persona_id)) return
  const clave = req.headers['idempotency-key']
  if (!clave) return problema(res, 428, '/errores/falta-idempotencia')
  const ifMatch = req.headers['if-match']
  if (!ifMatch || ifMatch === '*') return problema(res, 428, '/errores/falta-version')
  if (cuerpo?.acepta_condiciones !== true) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'acepta_condiciones', mensaje: 'MENSAJE DEL DOBLE: NO SE MUESTRA', tipo: 'literal_error' }] })
  // La misma clave repite la venta tal como está (decisión 229).
  const repetida = [...ventas.values()].find((v) => v.clave === clave && v.quien === u.id)
  if (repetida) {
    const abierta = repetida.estado === 'iniciada'
    return json(res, 201, { intento_id: repetida.id, estado: repetida.estado, monto: totalDe(p), total_confirmado_en: repetida.total_confirmado_en, url: abierta ? RUTA_WEBPAY : null, token: abierta ? repetida.token : null })
  }
  if (u.modo === 'pago-red') return problema(res, 500, '/errores/interno')
  const estado = vencido(p) || u.modo === 'pago-vencido' ? 'vencido' : p.estado
  if (estado !== 'total_confirmado') return problema(res, 409, '/errores/estado-pedido', { estado })
  if (pagoEnCurso(p) || u.modo === 'pago-409-en-curso') return problema(res, 409, '/errores/pago-en-curso')
  if (ifMatch !== etagDe(p)) return res.setHeader('ETag', etagDe(p)), problema(res, 412, '/errores/version-desactualizada', { actual: vista(p, rol, u) })
  const c = cuerpo?.condiciones as { version?: unknown; huella?: unknown } | undefined
  // Cuenta «pago-condiciones»: la primera vez se acaban de publicar otras condiciones.
  if (u.modo === 'pago-condiciones' && !condicionesUsadas.has(u.id)) {
    condicionesUsadas.add(u.id)
    return problema(res, 409, '/errores/condiciones-cambiaron', { version_vigente: VERSION_CONDICIONES })
  }
  if (c?.version !== VERSION_CONDICIONES || c?.huella !== HUELLA_CONDICIONES) return problema(res, 409, '/errores/condiciones-cambiaron', { version_vigente: VERSION_CONDICIONES })
  if (u.modo === 'pago-webpay-caido') return res.setHeader('Retry-After', '60'), problema(res, 503, '/errores/pasarela-no-disponible')
  const v: Venta = {
    id: randomUUID(),
    token: `doble${randomUUID().replace(/-/g, '')}`,
    orden: `o${aleatorio(10)}`,
    sesion: `s${aleatorio(10)}`,
    pedido_id: p.id,
    quien: u.id,
    creada: Date.now(),
    total_confirmado_en: p.confirmado_en,
    estado: 'iniciada',
    opcion: null,
    resultado: null,
    anulacion: null,
    primeraVuelta: null,
    clave: String(clave),
  }
  ventas.set(v.token, v)
  res.setHeader('Location', `/v1/pedidos/${p.id}/pago`)
  return json(res, 201, { intento_id: v.id, estado: 'iniciada', monto: totalDe(p), total_confirmado_en: p.confirmado_en, url: RUTA_WEBPAY, token: v.token })
}

/**
 * `POST /v1/pagos/retorno` (decisiones 231 a 235): pública, con la sesión si la hay. Aplica lo que se
 * eligió en la página falsa de Webpay. `grupoDe` dice el grupo y el rol de la cuenta para una persona.
 */
export function atenderRetorno(
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  { json, problema }: Responder,
  u: UsuarioPedido | null,
  grupoDe: (personaId: string) => { grupo_id: string; rol: Rol } | null,
) {
  res.setHeader('Cache-Control', 'no-store')
  const b = cuerpo ?? {}
  const texto = (k: string) => (typeof b[k] === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(b[k] as string) ? (b[k] as string) : null)
  const token = texto('token_ws') ?? texto('TBK_TOKEN')
  const orden = texto('TBK_ORDEN_COMPRA')
  const sesion = texto('TBK_ID_SESION')
  if (!token && !orden && !sesion) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'token_ws', mensaje: 'MENSAJE DEL DOBLE: NO SE MUESTRA', tipo: 'missing' }] })
  const v = token ? ventas.get(token) : [...ventas.values()].find((x) => x.orden === orden && x.sesion === sesion)
  if (!v || v.opcion === 'desconocido') return problema(res, 404, '/errores/no-encontrado')
  const p = pedidos.get(v.pedido_id)!
  let yaRegistrado = v.resultado !== null && v.resultado !== 'pendiente'
  if (!yaRegistrado) {
    const ahora = Date.now()
    const o = v.opcion
    if (o === 'pendiente' && (v.primeraVuelta ?? (v.primeraVuelta = ahora)) + PENDIENTE_MS > ahora) {
      v.estado = 'autorizando'
      v.resultado = 'pendiente'
    } else if (o === 'no_aprobado') {
      v.estado = 'rechazada'
      v.resultado = 'no_aprobado'
    } else if (o === 'abandonado' || o === 'tiempo_agotado' || o === null) {
      v.estado = 'rechazada'
      v.resultado = o ?? 'abandonado'
    } else {
      // Aprobado. Regla 3 de D-62-4: si el total ya no es el de la venta, se anula completo.
      v.estado = 'aprobada'
      const otroTotal = p.estado !== 'total_confirmado' || p.confirmado_en !== v.total_confirmado_en
      if (o === 'anulado' || o === 'anulando' || otroTotal) {
        v.resultado = 'anulado'
        v.anulacion = o === 'anulando' ? 'en_curso' : 'hecha'
        const ahoraIso = new Date().toISOString()
        p.devoluciones = [
          ...(p.devoluciones ?? []),
          { motivo: 'pago_tardio', monto: totalDe(p), producto_id: null, estado: v.anulacion, solicitada_en: ahoraIso, hecha_en: v.anulacion === 'hecha' ? ahoraIso : null, ultimos4: '4051', de: v.quien },
        ]
      } else {
        v.resultado = o === 'tardio' ? 'aprobado_tardio' : 'aprobado'
        aprobar(p, v.quien, tarjetaDe(o), o === 'tardio')
      }
    }
    yaRegistrado = false
  }
  const g = u && v.opcion !== 'sin_sesion' ? grupoDe(p.persona_id) : null
  const conIds = !!g && g.rol !== 'observador'
  return json(res, 200, {
    resultado: v.resultado,
    ya_registrado: yaRegistrado,
    anulacion: v.resultado === 'anulado' ? v.anulacion : null,
    volver_a_preguntar_en: v.resultado === 'pendiente' ? 15 : null,
    pago_de_prueba: true,
    grupo_id: conIds ? g!.grupo_id : null,
    persona_cuidada_id: conIds ? p.persona_id : null,
    pedido_id: conIds ? p.id : null,
  })
}

const escapar = (s: string) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)

async function leerFormulario(req: IncomingMessage): Promise<URLSearchParams> {
  const partes: Buffer[] = []
  for await (const parte of req) partes.push(parte as Buffer)
  return new URLSearchParams(Buffer.concat(partes).toString('utf8'))
}

/**
 * La página falsa de Webpay (solo desarrollo, fuera de `/v1`). `POST /__doble/webpay` con `token_ws`
 * muestra una opción por cada resultado; `POST /__doble/webpay/elegir` la guarda y vuelve a la
 * `return_url` como lo haría Transbank: por GET con `?token_ws=…`, o con los `TBK_*` en el fragmento
 * (el 303 que hace la API cuando Transbank vuelve por POST). `true` si la ruta era suya.
 */
export async function atenderWebpay(req: IncomingMessage, res: ServerResponse): Promise<boolean> {
  const ruta = (req.url ?? '').split('?')[0]
  if (ruta !== RUTA_WEBPAY && ruta !== `${RUTA_WEBPAY}/elegir`) return false
  res.setHeader('Cache-Control', 'no-store')
  res.setHeader('Referrer-Policy', 'no-referrer')
  if (req.method !== 'POST') {
    res.statusCode = 405
    res.end('Solo POST, como el formulario de Webpay.\n')
    return true
  }
  const f = await leerFormulario(req)
  const v = ventas.get(f.get('token_ws') ?? '')
  if (!v) {
    res.statusCode = 404
    res.setHeader('Content-Type', 'text/plain; charset=utf-8')
    res.end('El doble no conoce esta venta. Reinicia el pago desde MATU.\n')
    return true
  }
  if (ruta === RUTA_WEBPAY) {
    const p = pedidos.get(v.pedido_id)!
    const botones = OPCIONES.map(
      ([o, texto]) =>
        `<form method="post" action="${RUTA_WEBPAY}/elegir"><input type="hidden" name="token_ws" value="${escapar(v.token)}"><input type="hidden" name="opcion" value="${o}"><button type="submit">${escapar(texto)}</button></form>`,
    ).join('\n')
    res.statusCode = 200
    res.setHeader('Content-Type', 'text/html; charset=utf-8')
    res.end(`<!doctype html><html lang="es-CL"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="referrer" content="no-referrer"><title>Webpay del doble</title></head><body>
<h1>Webpay del doble (no es Transbank)</h1>
<p>Monto: $${totalDe(p).toLocaleString('es-CL')}. Elige qué pasa con este pago. Para ver «Hay un pago en curso», vuelve con el botón Atrás del navegador sin elegir.</p>
${botones}
</body></html>`)
    return true
  }
  const opcion = f.get('opcion') as Opcion | null
  v.opcion = OPCIONES.some(([o]) => o === opcion) ? opcion : 'debito'
  // Un token que no es de MATU: la venta de verdad se cierra sola y no queda un pago en curso.
  if (v.opcion === 'desconocido') v.estado = 'rechazada'
  // Aprobado tardío: el total vence mientras se paga.
  if (v.opcion === 'tardio') {
    const p = pedidos.get(v.pedido_id)!
    p.vence = Date.now() - 1000
  }
  const destino =
    v.opcion === 'abandonado'
      ? `/insumos/pedido/pago#TBK_TOKEN=${v.token}&TBK_ORDEN_COMPRA=${v.orden}&TBK_ID_SESION=${v.sesion}`
      : v.opcion === 'tiempo_agotado'
        ? `/insumos/pedido/pago#TBK_ORDEN_COMPRA=${v.orden}&TBK_ID_SESION=${v.sesion}`
        : `/insumos/pedido/pago?token_ws=${v.token}`
  res.statusCode = 303
  res.setHeader('Location', destino)
  res.end()
  return true
}

// ---------------------------------------------------------------- semillas del pago

/**
 * Un pedido ya pagado de la persona, con un borrador nuevo opcional. `quien` es la cuenta que pagó
 * (la de la semilla, u `otra-cuenta` para ver «Lo pagó otra persona de tu grupo.»).
 */
export function sembrarPagado(
  personaId: string,
  productosPorNombre: [string, number][],
  { quien, tarjeta = 'debito', tardio = false, devoluciones = false }: { quien: string; tarjeta?: 'debito' | 'credito' | 'prepago'; tardio?: boolean; devoluciones?: boolean },
) {
  const antes = enCurso.get(personaId)
  sembrarPedido(personaId, productosPorNombre, true)
  const p = pedidos.get(enCurso.get(personaId)!)!
  aprobar(p, quien, tarjetaDe(tarjeta), tardio, new Date(Date.now() - 2 * 3_600_000))
  if (devoluciones && p.lineas.length >= 2) {
    const [a, b] = p.lineas
    const precio = (l: Linea) => (l.confirmada?.precio ?? l.precio_carrito) * l.cantidad
    p.devoluciones = [
      { motivo: 'producto_no_entregado', monto: precio(a), producto_id: a.producto_id, estado: 'hecha', solicitada_en: hace(60), hecha_en: hace(55), ultimos4: tarjetaDe(tarjeta).ultimos4, de: quien },
      { motivo: 'producto_no_entregado', monto: precio(b), producto_id: b.producto_id, estado: 'en_curso', solicitada_en: hace(10), hecha_en: null, ultimos4: tarjetaDe(tarjeta).ultimos4, de: quien },
    ]
  }
  if (antes) enCurso.set(personaId, antes)
}

/** Un total confirmado que otra persona del grupo está pagando (6.1 y 6.2): la venta espera el `commit`. */
export function sembrarPagoEnCurso(personaId: string, productosPorNombre: [string, number][]) {
  sembrarPedido(personaId, productosPorNombre, true)
  const p = pedidos.get(enCurso.get(personaId)!)!
  const token = `doble${randomUUID().replace(/-/g, '')}`
  ventas.set(token, {
    id: randomUUID(),
    token,
    orden: `o${aleatorio(10)}`,
    sesion: `s${aleatorio(10)}`,
    pedido_id: p.id,
    quien: 'otra-cuenta',
    creada: Date.now(),
    total_confirmado_en: p.confirmado_en,
    estado: 'autorizando',
    opcion: null,
    resultado: 'pendiente',
    anulacion: null,
    primeraVuelta: null,
    clave: randomUUID(),
  })
}

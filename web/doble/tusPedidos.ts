// Doble de «Tus pedidos» (MATU-92; contrato docs/api/openapi.json, decisiones 436 a 448) para
// desarrollo y la revisión visual: la lista de los pagados con la vista del observador, el
// seguimiento por comercio, los productos para devolver con su `Idempotency-Key` y cancelar con
// devolución. Usa los pedidos de pedido.ts. Datos sintéticos: comercios ficticios y ningún código de
// retiro (D-63-5): el doble nunca los arma.
//
// Cuentas (doble/cuentas.ts): tus-pedidos@ (admin, un pedido en cada estado), tus-pedidos-pagador@
// (pagó él y se arrepiente), tus-pedidos-cuidador@ (no pagó), tus-pedidos-observador@,
// tus-pedidos-vacio@, tus-pedidos-carrera@ (el primer retracto responde 422 producto-no-retractable,
// como si otra persona hubiera ganado), tus-pedidos-red@ (cancelar y arrepentirse responden 503 la
// primera vez) y tus-pedidos-plazo@ (el plazo de la app venció, y otro pasó los 90 días).
// MATU-116: tus-pedidos-se-informa-pago@ (se informa y pagó dos de los cuatro: esos llegan con
// `vista: 'pagaste'` y la fila de quien paga, con `puede_cancelar` en false; los demás, con `se_informa`).
import { randomUUID } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { comercioDe, COSTO_ENVIO, productoDe, type Pedido, type Responder, type RetractoDoble, type Rol, type SeguimientoDoble, type UsuarioPedido } from './pedido'

const DIA = 86_400_000
/** La versión de las condiciones de los pedidos del doble (pedido.ts publica la 0.2). */
const CONDICIONES = '0.2'
const enChile = (ms: number) => new Date(ms)

/** El fin del décimo día hábil de Chile desde la entrega, sin feriados (basta para el doble). */
function plazoApp(entregado: string): string {
  const d = new Date(entregado)
  let habiles = 0
  while (habiles < 10) {
    d.setUTCDate(d.getUTCDate() + 1)
    const dia = d.getUTCDay()
    if (dia !== 0 && dia !== 6) habiles++
  }
  // 23:59:59 de Chile (UTC-3 en verano).
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1, 2, 59, 59, 999)).toISOString()
}
const plazoCorreo = (entregado: string) => enChile(new Date(entregado).getTime() + 90 * DIA).toISOString()

const precioDe = (p: Pedido, productoId: string) => {
  const l = p.lineas.find((x) => x.producto_id === productoId)
  return l ? (l.confirmada?.precio ?? l.precio_carrito) : 0
}
const totalDe = (p: Pedido) => p.lineas.reduce((t, l) => t + (l.confirmada?.precio ?? l.precio_carrito) * l.cantidad, 0) + COSTO_ENVIO
const productoVista = (id: string) => {
  const x = productoDe(id)!
  return { id: x.id, nombre: x.nombre, presentacion: x.presentacion, unidad: x.unidad, unidades_por_envase: x.unidades_por_envase }
}
const seg = (p: Pedido): SeguimientoDoble => p.seguimiento ?? { estado: 'pagado', entregado_en: null, cancelado_en: null, partes: {}, faltantes: {}, retractos: [], quien: p.pagado?.quien ?? '' }

/** Lo entregado y lo ya pedido de cada línea (también lo no aceptado, H3 y H8). */
function lineasParaRetracto(p: Pedido) {
  const s = seg(p)
  return p.lineas.map((l) => {
    const entregadas = l.cantidad - (s.faltantes[l.producto_id] ?? 0)
    const ya = s.retractos.flatMap((r) => r.lineas).filter((x) => x.producto_id === l.producto_id).reduce((t, x) => t + x.cantidad, 0)
    const producto = productoDe(l.producto_id)!
    return { linea_id: l.id, producto: productoVista(l.producto_id), entregadas, ya_pedidas: ya, disponibles: Math.max(0, entregadas - ya), precio_pagado: precioDe(p, l.producto_id), retracto_pierde_al_abrir: producto.retracto_pierde_al_abrir }
  })
}

function motivoArrepentirse(p: Pedido, rol: Rol, u: UsuarioPedido) {
  const s = seg(p)
  if (!s.entregado_en) return 'sin_entregar'
  if (Date.now() > new Date(plazoCorreo(s.entregado_en)).getTime()) return 'plazo_vencido'
  if (Date.now() > new Date(plazoApp(s.entregado_en)).getTime()) return 'plazo_app_vencido'
  // MATU-116 (C5): quien pagó se arrepiente también en «Se informa», mientras siga en el grupo.
  if (rol !== 'admin' && !((rol === 'pagador' || rol === 'observador') && s.quien === u.id)) return 'rol'
  if (!lineasParaRetracto(p).some((l) => l.disponibles > 0)) return 'nada_disponible'
  return null
}

function motivoCancelar(p: Pedido, rol: Rol) {
  const s = seg(p)
  if (s.estado === 'cancelado_con_devolucion') return 'cancelado'
  if (s.estado !== 'pagado' && s.estado !== 'enviado_a_comercio') return 'ya_se_prepara'
  if (rol !== 'admin') return 'rol'
  return null
}

/** MATU-116 (C5): el observador que pagó este pedido lo ve como quien paga. */
export const observadorQuePago = (p: Pedido, rol: Rol, u: UsuarioPedido) => rol === 'observador' && !!p.pagado && p.pagado.quien === u.id

/** La fila de quien ve el pago (`PedidoPagadoFila`), la del observador o, MATU-116, la del observador que pagó. */
function fila(p: Pedido, rol: Rol, u: UsuarioPedido) {
  const s = seg(p)
  const productos = p.lineas.map((l) => ({ producto: productoVista(l.producto_id), cantidad: l.cantidad }))
  const resumen = productos.length ? { primero: productos[0].producto.nombre, otros: productos.length - 1 } : null
  const pagaste = observadorQuePago(p, rol, u)
  // MATU-113 (decisión 472): el estado real de familia y la fecha de entrega, sin ningún monto.
  if (rol === 'observador' && !pagaste) return { vista: 'se_informa', pedido_id: p.id, pagado_en: p.pagado!.pagado_en, estado: s.estado, entregado_en: s.entregado_en, productos, resumen_productos: resumen, productos_borrados: false }
  const devs = p.devoluciones ?? []
  const devuelto = devs.filter((d) => d.estado === 'hecha' && d.motivo !== 'pago_tardio').reduce((t, d) => t + d.monto, 0)
  const ma = motivoArrepentirse(p, rol, u)
  const mc = motivoCancelar(p, rol)
  return {
    pedido_id: p.id,
    referencia: p.pagado!.referencia,
    pagado_en: p.pagado!.pagado_en,
    estado: s.estado,
    entregado_en: s.entregado_en,
    cancelado_en: s.cancelado_en,
    productos,
    resumen_productos: resumen,
    productos_borrados: false,
    total: totalDe(p),
    devuelto,
    devuelto_todo: devs.length > 0 && devs.filter((d) => d.motivo !== 'pago_tardio').every((d) => d.estado === 'hecha'),
    puede_cancelar: mc === null,
    cancelar_motivo: mc,
    // MATU-116: el observador que pagó nunca cancela (motivoCancelar da `rol` o el del estado).
    ...(pagaste ? { vista: 'pagaste' } : {}),
    puede_arrepentirse: ma === null,
    arrepentirse_motivo: ma,
    plazo_hasta: s.entregado_en ? plazoApp(s.entregado_en) : null,
    plazo_correo_hasta: s.entregado_en ? plazoCorreo(s.entregado_en) : null,
  }
}

const parteSegunPedido = (e: SeguimientoDoble['estado']) =>
  e === 'pagado' || e === 'enviado_a_comercio' ? 'enviada' : e === 'preparando' ? 'preparando' : e === 'listo_retiro' ? 'lista' : e === 'cancelado_con_devolucion' ? 'cancelada' : 'retirada'

function vistaRetracto(p: Pedido, r: RetractoDoble, u: UsuarioPedido) {
  const lineas = r.lineas.map((x) => ({ linea_id: p.lineas.find((l) => l.producto_id === x.producto_id)!.id, producto: productoVista(x.producto_id), cantidad: x.cantidad, monto: x.cantidad * precioDe(p, x.producto_id) }))
  const s = seg(p)
  return {
    id: r.id,
    pedido_id: p.id,
    estado: r.estado,
    solicitado_en: r.solicitado_en,
    plazo_hasta: s.entregado_en ? plazoApp(s.entregado_en) : r.solicitado_en,
    incluye_envio: r.incluye_envio,
    monto: lineas.reduce((t, l) => t + l.monto, 0) + (r.incluye_envio ? COSTO_ENVIO : 0),
    origen: r.origen,
    lineas,
    resuelto_en: r.resuelto_en,
    es_tuyo: r.de === u.id,
    motivo_rechazo: r.estado === 'rechazado' ? (r.motivo_rechazo ?? null) : null,
  }
}

/** `GET /v1/personas-cuidadas/{id}/pedidos` (decisión 436): los pagados, del más reciente, con cursor. */
export function listarPagados(req: IncomingMessage, res: ServerResponse, { json, problema }: Responder, u: UsuarioPedido, rol: Rol, todos: Pedido[]) {
  res.setHeader('Cache-Control', 'no-store')
  if (u.modo === 'tus-pedidos-falla') return problema(res, 500, '/errores/interno')
  const q = new URLSearchParams((req.url ?? '').split('?')[1] ?? '')
  const limite = Number(q.get('limite') ?? 20)
  if (!Number.isInteger(limite) || limite < 1 || limite > 100) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'limite', mensaje: 'MENSAJE DEL DOBLE: NO SE MUESTRA', tipo: 'less_than_equal' }] })
  const pagados = todos.filter((p) => p.pagado).sort((a, b) => b.pagado!.pagado_en.localeCompare(a.pagado!.pagado_en))
  const desde = q.get('cursor') ? Number(Buffer.from(q.get('cursor')!, 'base64url').toString('utf8')) : 0
  if (!Number.isInteger(desde) || desde < 0) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'cursor', mensaje: 'MENSAJE DEL DOBLE: NO SE MUESTRA', tipo: 'value_error' }] })
  const pagina = pagados.slice(desde, desde + limite)
  const siguiente = desde + limite < pagados.length ? Buffer.from(String(desde + limite), 'utf8').toString('base64url') : null
  return json(res, 200, { items: pagina.map((p) => fila(p, rol, u)), siguiente_cursor: siguiente })
}

const usadas = new Map<string, unknown>()
const primeraVez = new Set<string>()

/** El seguimiento, los retractos y cancelar con devolución de un pedido pagado. */
export function atenderTusPedidos(
  req: IncomingMessage,
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  { json, problema }: Responder,
  u: UsuarioPedido,
  rol: Rol,
  p: Pedido,
  accion: 'seguimiento' | 'retractos' | 'cancelar-con-devolucion',
) {
  res.setHeader('Cache-Control', 'no-store')
  const no = () => problema(res, 404, '/errores/no-encontrado')
  // D-92-1 a: el observador no tiene detalle (C6: también antes de mirar la cabecera o el cuerpo),
  // salvo en un pedido que pagó (MATU-116, C5).
  if ((rol === 'observador' && !observadorQuePago(p, rol, u)) || !p.pagado) return no()
  const s = seg(p)
  const metodo = req.method ?? 'GET'

  if (accion === 'seguimiento') {
    if (metodo !== 'GET') return no()
    const porComercio = new Map<string, Pedido['lineas']>()
    for (const l of p.lineas) {
      const c = l.confirmada?.comercio_id ?? ''
      porComercio.set(c, [...(porComercio.get(c) ?? []), l])
    }
    const partes = [...porComercio].map(([id, lineas]) => {
      const c = comercioDe(id)
      const estado = s.partes[id] ?? parteSegunPedido(s.estado)
      // Decisión 438: nunca el código, la referencia de la parte ni el id del comercio (C15).
      return {
        comercio: { nombre_fantasia: c.nombre_fantasia, ficticio: c.ficticio },
        estado,
        cancelada_por: estado === 'cancelada' ? (s.estado === 'cancelado_con_devolucion' ? 'pedido' : 'faltante') : null,
        lineas: lineas.map((l) => ({ linea_id: l.id, producto: productoVista(l.producto_id), cantidad: l.cantidad, unidades_faltantes: s.faltantes[l.producto_id] ?? 0 })),
      }
    })
    const { productos: _p, resumen_productos: _r, vista: _v, ...base } = fila(p, rol, u) as Record<string, unknown>
    return json(res, 200, { ...base, partes })
  }

  if (accion === 'cancelar-con-devolucion') {
    if (metodo !== 'POST' || rol !== 'admin') return no()
    const clave = req.headers['idempotency-key']
    if (!clave) return problema(res, 428, '/errores/falta-idempotencia')
    if (usadas.has(`c:${clave}`)) return json(res, 200, usadas.get(`c:${clave}`))
    if (u.modo === 'tus-pedidos-red' && !primeraVez.has(`c:${p.id}`)) {
      primeraVez.add(`c:${p.id}`)
      return problema(res, 503, '/errores/servicio-no-disponible')
    }
    const m = motivoCancelar(p, rol)
    if (m === 'cancelado') return problema(res, 409, '/errores/estado-pedido', { estado: 'cancelado_con_devolucion' })
    if (m === 'ya_se_prepara') return problema(res, 409, '/errores/ya-se-prepara')
    const ahora = new Date().toISOString()
    p.seguimiento = { ...s, estado: 'cancelado_con_devolucion', cancelado_en: ahora, partes: {} }
    p.devoluciones = [...(p.devoluciones ?? []), { motivo: 'cancelacion', monto: totalDe(p), producto_id: null, estado: 'en_curso', solicitada_en: ahora, hecha_en: null, ultimos4: p.pagado.tarjeta.ultimos4, de: p.pagado.quien }]
    const r = { pedido_id: p.id, estado: 'cancelado_con_devolucion' }
    usadas.set(`c:${clave}`, r)
    return json(res, 200, r)
  }

  // retractos
  if (!s.entregado_en) return no()
  if (metodo === 'GET') {
    const lineas = lineasParaRetracto(p)
    const ma = motivoArrepentirse(p, rol, u)
    const todoDisponible = lineas.some((l) => l.disponibles > 0) && !s.retractos.some((r) => r.estado !== 'rechazado' && r.incluye_envio)
    return json(res, 200, {
      plazo_hasta: plazoApp(s.entregado_en),
      plazo_correo_hasta: plazoCorreo(s.entregado_en),
      puede_arrepentirse: ma === null,
      arrepentirse_motivo: ma,
      condiciones_version: CONDICIONES,
      costo_envio: COSTO_ENVIO,
      incluye_envio_si_todo: todoDisponible,
      lineas,
      retractos: s.retractos.map((r) => vistaRetracto(p, r, u)),
    })
  }
  if (metodo !== 'POST') return no()
  if (rol !== 'admin' && !((rol === 'pagador' || rol === 'observador') && s.quien === u.id)) return no()
  const clave = req.headers['idempotency-key']
  if (!clave) return problema(res, 428, '/errores/falta-idempotencia')
  if (usadas.has(`r:${clave}`)) return json(res, 201, usadas.get(`r:${clave}`))
  if (u.modo === 'tus-pedidos-red' && !primeraVez.has(`r:${p.id}`)) {
    primeraVez.add(`r:${p.id}`)
    return problema(res, 503, '/errores/servicio-no-disponible')
  }
  const ma = motivoArrepentirse(p, rol, u)
  if (ma === 'plazo_app_vencido' || ma === 'plazo_vencido') return problema(res, 409, '/errores/fuera-de-plazo', { plazo_hasta: plazoApp(s.entregado_en) })
  // Cuenta «tus-pedidos-carrera»: otra persona pide devolver un pañal justo antes.
  if (u.modo === 'tus-pedidos-carrera' && !primeraVez.has(`carrera:${p.id}`)) {
    primeraVez.add(`carrera:${p.id}`)
    s.retractos.push({ id: randomUUID(), estado: 'solicitado', solicitado_en: new Date().toISOString(), resuelto_en: null, origen: 'app', de: 'otra-cuenta', incluye_envio: false, lineas: [{ producto_id: p.lineas[0].producto_id, cantidad: 1 }], clave: null })
    p.seguimiento = s
    return problema(res, 422, '/errores/producto-no-retractable')
  }
  const pedidas = Array.isArray(cuerpo?.lineas) ? (cuerpo!.lineas as { linea_id?: unknown; cantidad?: unknown }[]) : []
  const disponibles = lineasParaRetracto(p)
  const lineas: RetractoDoble['lineas'] = []
  for (const x of pedidas) {
    const l = disponibles.find((d) => d.linea_id === x.linea_id)
    if (!l || typeof x.cantidad !== 'number' || !Number.isInteger(x.cantidad) || x.cantidad < 1 || x.cantidad > l.disponibles) return problema(res, 422, '/errores/producto-no-retractable')
    lineas.push({ producto_id: l.producto.id, cantidad: x.cantidad })
  }
  if (!lineas.length) return problema(res, 422, '/errores/producto-no-retractable')
  const todo = disponibles.filter((d) => d.disponibles > 0).every((d) => lineas.find((x) => x.producto_id === d.producto.id)?.cantidad === d.disponibles)
  // C9: con las condiciones 0.1 y 0.2 (las del doble), el envío vuelve en cualquier retracto, una sola vez.
  const envioYa = s.retractos.some((x) => x.estado !== 'rechazado' && x.incluye_envio)
  const conEnvio = !envioYa && (CONDICIONES === '0.2' || todo)
  const r: RetractoDoble = { id: randomUUID(), estado: 'solicitado', solicitado_en: new Date().toISOString(), resuelto_en: null, origen: 'app', de: u.id, incluye_envio: conEnvio, lineas, clave: String(clave) }
  s.retractos.push(r)
  p.seguimiento = s
  const vista = vistaRetracto(p, r, u)
  usadas.set(`r:${clave}`, vista)
  return json(res, 201, vista)
}

/** Las semillas: cómo va un pedido ya pagado (pedido.ts, `sembrarPagado`). */
export function fijarSeguimiento(p: Pedido, s: Partial<SeguimientoDoble>) {
  p.seguimiento = { ...seg(p), quien: p.pagado?.quien ?? '', ...s }
}

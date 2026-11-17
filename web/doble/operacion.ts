// Doble de la consola de operación (MATU-81; contrato docs/api/openapi.json, decisiones 449 a 465)
// para desarrollo, la revisión visual y las pruebas. Una sola lógica, sin dependencias de Node: el
// servidor de Vite (doble/familia.ts) y el adaptador de las pruebas (pruebas/operacionFalso.tsx) le
// pasan la petición y devuelven su respuesta. Responde el segundo factor (401 `mfa-requerido` con el
// desafío, `codigo-mfa-incorrecto`, `codigo-mfa-usado`, `desafio-vencido`, 429 `mfa-bloqueado` y 503)
// y /v1/operacion/** con el ETag, el If-Match, 409, 412, 422 y 428 del contrato.
//
// Datos sintéticos: los comercios son de prueba, los pedidos son inventados y ninguna respuesta lleva
// nombre, dirección, grupo ni cuenta de nadie (C5). El único correo es el de un administrador
// inventado, que se compara y nunca se devuelve ni se escribe en la consola (D-81-9).
//
// Cuentas (contraseña de ejemplo de doble/cuentas.ts), todas con el código fijo CODIGO_MFA:
//   operacion@example.com          pedidos en cada estado, retractos, incidencias, cobros y catálogo
//   operacion-vacia@example.com    sin pedidos, retractos, incidencias ni cobros por revisar
//   operacion-falla@example.com    las listas responden 500
// Códigos del segundo paso: CODIGO_MFA entra · 111111 «ya usado» · 222222 desafío vencido · 999999 503
//   · cualquier otro no coincide (al quinto, 429 por 15 minutos).

export const CODIGO_MFA = '246810'
/** El correo del administrador inventado del retracto por correo: cualquier otro responde 422. */
export const CORREO_ADMIN_DE_EJEMPLO = 'admin@example.com'
/** El código de retiro que entrega el doble al generar uno (el «correcto» del doble del comercio). */
export const CODIGO_RETIRO_DE_EJEMPLO = '482173'

export interface PeticionDoble {
  metodo: string
  ruta: string
  query: URLSearchParams
  cuerpo: unknown
  ifMatch: string | null
}
export interface RespuestaDoble {
  status: number
  cuerpo?: unknown
  cabeceras?: Record<string, string>
}

const problema = (status: number, tipo: string, extra: Record<string, unknown> = {}, cabeceras: Record<string, string> = {}): RespuestaDoble => ({
  status,
  cuerpo: { type: `/errores/${tipo}`, title: 'DOBLE', status, ...extra },
  cabeceras: { 'content-type': 'application/problem+json', ...cabeceras },
})
const ok = (cuerpo: unknown, status = 200, cabeceras: Record<string, string> = {}): RespuestaDoble => ({ status, cuerpo, cabeceras: { 'cache-control': 'no-store', ...cabeceras } })
const MIN = 60_000
const DIA = 86_400_000

// ----------------------------------------------------------------- el segundo factor

/** El segundo paso de la entrada (C29 y C32). `ahora` en milisegundos. */
export function crearMfa(ahora: () => number = () => Date.now()) {
  const desafios = new Map<string, { email: string; vence: number }>()
  const fallidos = new Map<string, number>()
  let n = 0
  return {
    /** El 401 `mfa-requerido` de `POST /v1/sesiones` para una cuenta de operación. */
    desafiar(email: string): RespuestaDoble {
      const desafio = `desafio${++n}`.padEnd(43, 'x')
      const vence = ahora() + 5 * MIN
      desafios.set(desafio, { email, vence })
      return problema(401, 'mfa-requerido', { desafio, desafio_expira_en: new Date(vence).toISOString() })
    },
    /** `POST /v1/sesiones/mfa`: el correo de la cuenta si el código sirve, o el problema. */
    verificar(cuerpo: unknown): { email: string } | RespuestaDoble {
      const c = (cuerpo ?? {}) as { desafio?: unknown; codigo?: unknown }
      if (typeof c.desafio !== 'string' || !/^[A-Za-z0-9_-]{43}$/.test(c.desafio) || typeof c.codigo !== 'string' || !/^[0-9]{6}$/.test(c.codigo))
        return problema(422, 'validacion', { errores: [{ campo: 'codigo', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_pattern_mismatch' }] })
      if (c.codigo === '999999') return problema(503, 'servicio-no-disponible')
      const d = desafios.get(c.desafio)
      if (!d || d.vence < ahora() || c.codigo === '222222') {
        desafios.delete(c.desafio)
        return problema(401, 'desafio-vencido')
      }
      if ((fallidos.get(d.email) ?? 0) >= 5) {
        desafios.delete(c.desafio)
        return problema(429, 'mfa-bloqueado', { minutos_espera: 15 }, { 'retry-after': '900' })
      }
      if (c.codigo === CODIGO_MFA) {
        desafios.delete(c.desafio)
        fallidos.delete(d.email)
        return { email: d.email }
      }
      if (c.codigo === '111111') return problema(401, 'codigo-mfa-usado')
      const f = (fallidos.get(d.email) ?? 0) + 1
      fallidos.set(d.email, f)
      if (f >= 5) {
        desafios.delete(c.desafio)
        return problema(429, 'mfa-bloqueado', { minutos_espera: 15 }, { 'retry-after': '900' })
      }
      return problema(401, 'codigo-mfa-incorrecto', { intentos_restantes: 5 - f })
    },
  }
}

// ----------------------------------------------------------------- la consola

type EstadoPedido =
  | 'pagado'
  | 'enviado_a_comercio'
  | 'preparando'
  | 'listo_retiro'
  | 'retirado'
  | 'en_ruta'
  | 'entregado'
  | 'no_entregado'
  | 'reprogramado'
  | 'cerrado'
  | 'cancelado'
  | 'cancelado_con_devolucion'
type EstadoParte = 'enviada' | 'preparando' | 'lista' | 'retirada' | 'cancelada'
type EstadoCodigo = 'sin_codigo' | 'vigente' | 'usado' | 'bloqueado' | 'vencido'
type EstadoLinea = 'pendiente' | 'preparada' | 'faltante' | 'devuelta'

interface Comercio {
  nombre_fantasia: string
  ficticio: boolean
}
interface Linea {
  id: string
  parte_id: string
  producto: string
  presentacion: string
  cantidad: number
  precio_unitario: number
  estado_linea: EstadoLinea
  unidades_faltantes: number
  monto_devuelto: number
  devolucion: 'sin_devolucion' | 'en_curso' | 'hecha'
}
interface Parte {
  id: string
  referencia: string
  comercio: Comercio
  estado: EstadoParte
  estado_codigo: EstadoCodigo
  codigo_expira_en: string | null
  enviado_en: string | null
  preparando_en: string | null
  lista_en: string | null
  retirada_en: string | null
  cancelada_en: string | null
  motivo_cancelacion: 'producto_faltante' | 'familia_cancela' | null
}
interface Evento {
  en: string
  tipo: 'estado' | 'parte' | 'cobro' | 'anulacion' | 'retracto' | 'incidencia'
  actor_tipo: 'familia' | 'comercio' | 'operacion' | 'sistema'
  comercio: string | null
  desde: string | null
  hacia: string | null
  motivo: string | null
  monto: number | null
}
interface Venta {
  buy_order: string
  monto: number
  estado: 'iniciada' | 'autorizando' | 'aprobada' | 'rechazada' | 'error'
  creada_en: string
  respondida_en: string | null
}
interface Anulacion {
  id: string
  motivo: 'pago_tardio' | 'producto_no_entregado' | 'cancelacion' | 'retracto'
  monto: number
  estado: 'en_curso' | 'hecha' | 'rechazada'
  producto: string | null
  en: string
  intentos: number
}
interface Pedido {
  id: string
  referencia: string
  estado: EstadoPedido
  pagado_en: string
  entregado_en: string | null
  costo_envio: number
  partes: Parte[]
  lineas: Linea[]
  eventos: Evento[]
  ventas: Venta[]
  anulaciones: Anulacion[]
}
interface Retracto {
  id: string
  pedido_id: string
  estado: 'solicitado' | 'devuelto' | 'rechazado'
  solicitado_en: string
  plazo_hasta: string
  incluye_envio: boolean
  monto: number
  origen: 'app' | 'correo'
  lineas: { linea_id: string; cantidad: number }[]
  motivo_rechazo: 'sello_abierto' | 'producto_no_recibido' | null
  resuelto_en: string | null
}
interface Incidencia {
  id: string
  pedido_id: string
  tipo: 'faltante' | 'entrega_fallida' | 'reclamo_familia' | 'cobro_sin_respuesta' | 'devolucion_pendiente' | 'otro'
  estado: 'abierta' | 'en_gestion' | 'resuelta'
  descripcion: string
  resolucion: string | null
  creada_en: string
  resuelta_en: string | null
  asignada: boolean
  asignada_a_mi: boolean
  version: number
}
interface Oferta {
  id: string
  comercio: Comercio
  producto: string
  presentacion: string
  precio: number
  stock: number
  disponible: boolean
  version: number
}

const ALMACEN: Comercio = { nombre_fantasia: 'Almacén El Ejemplo', ficticio: true }
const FARMACIA: Comercio = { nombre_fantasia: 'Farmacia Los Aromos', ficticio: true }
const REAL: Comercio = { nombre_fantasia: 'Distribuidora del Centro', ficticio: false }

/** Los ids del doble, fijos para que las pruebas los nombren. */
export const ID_OPERACION = {
  enCamino: '81000000-0000-4000-8000-000000004821',
  listo: '81000000-0000-4000-8000-000000004822',
  enComercio: '81000000-0000-4000-8000-000000004823',
  porDespachar: '81000000-0000-4000-8000-000000004824',
  entregado: '81000000-0000-4000-8000-000000004825',
  conRetracto: '81000000-0000-4000-8000-000000004826',
  cancelado: '81000000-0000-4000-8000-000000004827',
  noEntregado: '81000000-0000-4000-8000-000000004828',
  fueraDePlazo: '81000000-0000-4000-8000-000000004831',
  parteVigente: '81000000-0000-4000-8000-00000000a822',
  parteSinCodigo: '81000000-0000-4000-8000-00000000b822',
  retractoApp: '81000000-0000-4000-8000-00000000c826',
  incidenciaAbierta: '81000000-0000-4000-8000-00000000d821',
  incidenciaEnGestion: '81000000-0000-4000-8000-00000000d827',
  incidenciaResuelta: '81000000-0000-4000-8000-00000000d825',
  ofertaPanal: '81000000-0000-4000-8000-00000000e001',
  ofertaToallitas: '81000000-0000-4000-8000-00000000e002',
  ofertaGuantes: '81000000-0000-4000-8000-00000000e003',
  ofertaCrema: '81000000-0000-4000-8000-00000000e004',
  ofertaReal: '81000000-0000-4000-8000-00000000e005',
}

export type ModoOperacion = 'operacion' | 'operacion-vacia' | 'operacion-falla'

/**
 * La consola con su estado en memoria. `ahora` es el reloj del servidor (la cabecera `Date`).
 * `trampas`: los guantes responden 412 la primera vez (para la revisión visual; las pruebas lo apagan).
 */
export function crearConsola({ ahora = () => new Date(), modo = 'operacion', trampas = false }: { ahora?: () => Date; modo?: ModoOperacion; trampas?: boolean } = {}) {
  const t0 = ahora().getTime()
  const en = (min: number) => new Date(t0 + min * MIN).toISOString()
  let sec = 0
  const nuevoId = () => `81000000-0000-4000-8000-${String(++sec).padStart(12, '0')}`

  const linea = (parte_id: string, producto: string, presentacion: string, cantidad: number, precio: number, extra: Partial<Linea> = {}): Linea => ({
    id: nuevoId(),
    parte_id,
    producto,
    presentacion,
    cantidad,
    precio_unitario: precio,
    estado_linea: 'pendiente',
    unidades_faltantes: 0,
    monto_devuelto: 0,
    devolucion: 'sin_devolucion',
    ...extra,
  })
  const parte = (id: string, referencia: string, comercio: Comercio, estado: EstadoParte, extra: Partial<Parte> = {}): Parte => ({
    id,
    referencia,
    comercio,
    estado,
    estado_codigo: estado === 'retirada' ? 'usado' : estado === 'lista' ? 'vigente' : 'sin_codigo',
    codigo_expira_en: null,
    enviado_en: en(-200),
    preparando_en: estado === 'enviada' ? null : en(-180),
    lista_en: estado === 'lista' || estado === 'retirada' ? en(-150) : null,
    retirada_en: estado === 'retirada' ? en(-120) : null,
    cancelada_en: estado === 'cancelada' ? en(-150) : null,
    motivo_cancelacion: null,
    ...extra,
  })
  const ev = (min: number, tipo: Evento['tipo'], actor_tipo: Evento['actor_tipo'], hacia: string | null, extra: Partial<Evento> = {}): Evento => ({
    en: en(min),
    tipo,
    actor_tipo,
    comercio: null,
    desde: null,
    hacia,
    motivo: null,
    monto: null,
    ...extra,
  })
  const subtotal = (p: Pedido) => p.lineas.reduce((s, l) => s + l.precio_unitario * l.cantidad, 0)
  const total = (p: Pedido) => subtotal(p) + p.costo_envio
  const cobrado = (p: Pedido) => p.ventas.filter((v) => v.estado === 'aprobada').reduce((s, v) => s + v.monto, 0)
  const devuelto = (p: Pedido) => p.anulaciones.filter((a) => a.estado === 'hecha').reduce((s, a) => s + a.monto, 0)

  /** Un pedido pagado con sus eventos de base: el pago y el envío a los comercios. */
  function pedido(id: string, referencia: string, estado: EstadoPedido, pagadoHace: number, partes: Parte[], lineas: Linea[], extra: Partial<Pedido> = {}): Pedido {
    const p: Pedido = { id, referencia, estado, pagado_en: en(-pagadoHace), entregado_en: null, costo_envio: 4990, partes, lineas, eventos: [], ventas: [], anulaciones: [], ...extra }
    p.ventas.unshift({ buy_order: `MATU-${referencia}-7Q2`, monto: total(p), estado: 'aprobada', creada_en: en(-pagadoHace - 2), respondida_en: en(-pagadoHace) })
    p.eventos.push(ev(-pagadoHace, 'estado', 'sistema', 'pagado', { desde: 'total_confirmado', motivo: 'pago_aprobado' }))
    p.eventos.push(ev(-pagadoHace, 'cobro', 'sistema', 'aprobada', { monto: total(p) }))
    if (estado !== 'pagado') p.eventos.push(ev(-pagadoHace + 1, 'estado', 'sistema', 'enviado_a_comercio', { desde: 'pagado' }))
    for (const x of partes) {
      if (x.preparando_en) p.eventos.push({ ...ev(0, 'parte', 'comercio', 'preparando', { comercio: x.comercio.nombre_fantasia }), en: x.preparando_en })
      if (x.lista_en) p.eventos.push({ ...ev(0, 'parte', 'comercio', 'lista', { comercio: x.comercio.nombre_fantasia }), en: x.lista_en })
      if (x.retirada_en) p.eventos.push({ ...ev(0, 'parte', 'comercio', 'retirada', { comercio: x.comercio.nombre_fantasia }), en: x.retirada_en })
      if (x.cancelada_en) p.eventos.push({ ...ev(0, 'parte', 'sistema', 'cancelada', { comercio: x.comercio.nombre_fantasia, motivo: x.motivo_cancelacion }), en: x.cancelada_en })
    }
    return p
  }

  const I = ID_OPERACION
  const pedidos: Pedido[] = []
  const retractos: Retracto[] = []
  const incidencias: Incidencia[] = []

  if (modo !== 'operacion-vacia') {
    // 4821 · en camino: el suplemento faltó (devuelto) y hay una incidencia abierta.
    const a1 = nuevoId()
    const a2 = nuevoId()
    const A = pedido(
      I.enCamino,
      '4821',
      'en_ruta',
      240,
      [parte(a1, 'K4M7XP', ALMACEN, 'retirada'), parte(a2, 'W2R9TB', FARMACIA, 'cancelada', { motivo_cancelacion: 'producto_faltante' })],
      [],
    )
    A.lineas = [
      linea(a1, 'Pañal adulto M x30', 'Paquete de 30 unidades', 2, 12990, { estado_linea: 'preparada' }),
      linea(a2, 'Suplemento vainilla x12', 'Caja de 12 unidades', 3, 8830, { estado_linea: 'faltante', unidades_faltantes: 3, monto_devuelto: 26490, devolucion: 'hecha' }),
    ]
    A.anulaciones.push({ id: nuevoId(), motivo: 'producto_no_entregado', monto: 26490, estado: 'hecha', producto: 'Suplemento vainilla x12', en: en(-148), intentos: 1 })
    A.eventos.push(ev(-148, 'anulacion', 'sistema', 'hecha', { motivo: 'producto_no_entregado', monto: 26490 }))
    A.eventos.push(ev(-120, 'estado', 'sistema', 'retirado', { desde: 'listo_retiro' }))
    A.eventos.push(ev(-90, 'estado', 'operacion', 'en_ruta', { desde: 'retirado' }))
    pedidos.push(A)
    incidencias.push({
      id: I.incidenciaAbierta,
      pedido_id: A.id,
      tipo: 'faltante',
      estado: 'abierta',
      descripcion: 'El comercio avisó que no le llegó el suplemento.',
      resolucion: null,
      creada_en: en(-140),
      resuelta_en: null,
      asignada: false,
      asignada_a_mi: false,
      version: 1,
    })
    A.eventos.push(ev(-140, 'incidencia', 'operacion', 'abierta', { motivo: 'faltante' }))

    // 4822 · listo para retirar: una parte con el código vigente y otra sin código.
    const B = pedido(I.listo, '4822', 'listo_retiro', 180, [parte(I.parteVigente, 'P5Q8ZA', ALMACEN, 'lista', { codigo_expira_en: en(60) }), parte(I.parteSinCodigo, 'H6N3VD', FARMACIA, 'lista', { estado_codigo: 'sin_codigo' })], [])
    B.lineas = [linea(I.parteVigente, 'Pañal adulto M x30', 'Paquete de 30 unidades', 1, 12990, { estado_linea: 'preparada' }), linea(I.parteSinCodigo, 'Toallitas húmedas x80', 'Paquete de 80 unidades', 2, 3290, { estado_linea: 'preparada' })]
    B.eventos.push(ev(-140, 'estado', 'sistema', 'listo_retiro', { desde: 'preparando' }))
    pedidos.push(B)

    // 4823 · en el comercio, se puede cancelar con devolución. Una venta anterior quedó sin respuesta.
    const c1 = nuevoId()
    const C = pedido(I.enComercio, '4823', 'enviado_a_comercio', 20, [parte(c1, 'R8T2WQ', ALMACEN, 'enviada')], [])
    C.lineas = [linea(c1, 'Crema protectora 200 g', 'Pote de 200 gramos', 1, 6490)]
    C.ventas.push({ buy_order: 'MATU-4823-K2', monto: total(C), estado: 'autorizando', creada_en: en(-38), respondida_en: null })
    pedidos.push(C)

    // 4824 · retirado, por despachar.
    const d1 = nuevoId()
    const D = pedido(I.porDespachar, '4824', 'retirado', 300, [parte(d1, 'T8F2HJ', ALMACEN, 'retirada')], [])
    D.lineas = [linea(d1, 'Toallitas húmedas x80', 'Paquete de 80 unidades', 2, 3290, { estado_linea: 'preparada' })]
    D.eventos.push(ev(-120, 'estado', 'sistema', 'retirado', { desde: 'listo_retiro' }))
    pedidos.push(D)

    // 4825 · entregado hace 2 días: se puede registrar un retracto por correo. Una incidencia resuelta.
    const e1 = nuevoId()
    const E = pedido(I.entregado, '4825', 'entregado', 3 * 24 * 60, [parte(e1, 'N3V7QD', ALMACEN, 'retirada')], [], { entregado_en: en(-2 * 24 * 60) })
    E.lineas = [linea(e1, 'Pañal adulto M x30', 'Paquete de 30 unidades', 2, 12990, { estado_linea: 'preparada' }), linea(e1, 'Crema protectora 200 g', 'Pote de 200 gramos', 1, 6490, { estado_linea: 'preparada' })]
    E.eventos.push(ev(-2 * 24 * 60, 'estado', 'operacion', 'entregado', { desde: 'en_ruta' }))
    pedidos.push(E)
    incidencias.push({
      id: I.incidenciaResuelta,
      pedido_id: E.id,
      tipo: 'reclamo_familia',
      estado: 'resuelta',
      descripcion: 'La familia escribió que la caja llegó abierta.',
      resolucion: 'Se revisó con el comercio: los productos estaban completos.',
      creada_en: en(-2 * 24 * 60 + 30),
      resuelta_en: en(-24 * 60),
      asignada: true,
      asignada_a_mi: false,
      version: 3,
    })

    // 4826 · entregado, con un retracto por la app que vence mañana.
    const f1 = nuevoId()
    const F = pedido(I.conRetracto, '4826', 'entregado', 10 * 24 * 60, [parte(f1, 'J9M4KC', FARMACIA, 'retirada')], [], { entregado_en: en(-9 * 24 * 60) })
    F.lineas = [linea(f1, 'Suplemento vainilla x12', 'Caja de 12 unidades', 3, 8830, { estado_linea: 'preparada' })]
    F.eventos.push(ev(-9 * 24 * 60, 'estado', 'operacion', 'entregado', { desde: 'en_ruta' }))
    pedidos.push(F)
    retractos.push({
      id: I.retractoApp,
      pedido_id: F.id,
      estado: 'solicitado',
      solicitado_en: en(-24 * 60),
      plazo_hasta: en(24 * 60),
      incluye_envio: false,
      monto: 26490,
      origen: 'app',
      lineas: [{ linea_id: F.lineas[0].id, cantidad: 3 }],
      motivo_rechazo: null,
      resuelto_en: null,
    })
    F.eventos.push(ev(-24 * 60, 'retracto', 'familia', 'solicitado'))

    // 4827 · cancelado con devolución, y la devolución quedó sin terminar.
    const g1 = nuevoId()
    const G = pedido(I.cancelado, '4827', 'cancelado_con_devolucion', 26 * 60, [parte(g1, 'Z5V7NQ', ALMACEN, 'cancelada', { motivo_cancelacion: 'familia_cancela' })], [])
    G.lineas = [linea(g1, 'Pañal adulto M x30', 'Paquete de 30 unidades', 1, 12990)]
    G.anulaciones.push({ id: nuevoId(), motivo: 'cancelacion', monto: total(G), estado: 'rechazada', producto: null, en: en(-25 * 60), intentos: 3 })
    G.eventos.push(ev(-25 * 60, 'estado', 'operacion', 'cancelado_con_devolucion', { desde: 'enviado_a_comercio' }))
    G.eventos.push(ev(-25 * 60, 'anulacion', 'sistema', 'rechazada', { motivo: 'cancelacion', monto: total(G) }))
    pedidos.push(G)
    incidencias.push({
      id: I.incidenciaEnGestion,
      pedido_id: G.id,
      tipo: 'devolucion_pendiente',
      estado: 'en_gestion',
      descripcion: 'Transbank no confirmó la devolución.',
      resolucion: null,
      creada_en: en(-24 * 60),
      resuelta_en: null,
      asignada: true,
      asignada_a_mi: true,
      version: 2,
    })

    // 4828 · no se entregó: se cancela con devolución de todo.
    const h1 = nuevoId()
    const H = pedido(I.noEntregado, '4828', 'no_entregado', 8 * 60, [parte(h1, 'Q2L6XF', ALMACEN, 'retirada')], [])
    H.lineas = [linea(h1, 'Pañal adulto M x30', 'Paquete de 30 unidades', 1, 12990, { estado_linea: 'preparada' }), linea(h1, 'Toallitas húmedas x80', 'Paquete de 80 unidades', 2, 3290, { estado_linea: 'preparada' })]
    H.eventos.push(ev(-60, 'estado', 'operacion', 'no_entregado', { desde: 'en_ruta' }))
    pedidos.push(H)

    // 4831 · entregado hace 100 días: el retracto por correo responde 409 fuera de plazo.
    const k1 = nuevoId()
    const K = pedido(I.fueraDePlazo, '4831', 'cerrado', 101 * 24 * 60, [parte(k1, 'B7C3MW', ALMACEN, 'retirada')], [], { entregado_en: en(-100 * 24 * 60) })
    K.lineas = [linea(k1, 'Crema protectora 200 g', 'Pote de 200 gramos', 2, 6490, { estado_linea: 'preparada' })]
    pedidos.push(K)
  }

  // Las líneas se arman después de las partes: el monto de la venta y de su evento sale de ellas.
  for (const p of pedidos) {
    p.ventas[0].monto = total(p)
    for (const e of p.eventos) if (e.tipo === 'cobro') e.monto = total(p)
  }
  for (const v of pedidos.find((p) => p.id === I.enComercio)?.ventas.slice(1) ?? []) v.monto = total(pedidos.find((p) => p.id === I.enComercio)!)

  const ofertas: Oferta[] = [
    { id: I.ofertaPanal, comercio: ALMACEN, producto: 'Pañal adulto M x30', presentacion: 'Paquete de 30 unidades', precio: 12990, stock: 14, disponible: true, version: 1 },
    { id: I.ofertaToallitas, comercio: ALMACEN, producto: 'Toallitas húmedas x80', presentacion: 'Paquete de 80 unidades', precio: 3290, stock: 0, disponible: true, version: 1 },
    { id: I.ofertaGuantes, comercio: FARMACIA, producto: 'Guantes desechables', presentacion: 'Caja de 100 unidades', precio: 6490, stock: 5, disponible: false, version: 1 },
    { id: I.ofertaCrema, comercio: FARMACIA, producto: 'Crema protectora 200 g', presentacion: 'Pote de 200 gramos', precio: 6490, stock: 8, disponible: true, version: 1 },
    { id: I.ofertaReal, comercio: REAL, producto: 'Pañal adulto L x20', presentacion: 'Paquete de 20 unidades', precio: 10990, stock: 30, disponible: true, version: 1 },
  ]
  const conflictoPendiente = new Set(trampas ? [I.ofertaGuantes] : [])

  // --------------------------------------------------------------- vistas

  const incidenciaAbierta = (p: Pedido) => incidencias.some((i) => i.pedido_id === p.id && i.estado !== 'resuelta')
  const sinTerminar = (p: Pedido) => p.anulaciones.some((a) => a.estado !== 'hecha')
  const faltantesPorDevolver = (p: Pedido) =>
    p.lineas.filter((l) => l.unidades_faltantes > 0 && l.devolucion !== 'hecha').reduce((s, l) => s + l.unidades_faltantes * l.precio_unitario - l.monto_devuelto, 0)

  function acciones(p: Pedido) {
    const queda = cobrado(p) - devuelto(p)
    const preparando = p.partes.some((x) => x.estado !== 'enviada')
    if (p.estado === 'retirado' || p.estado === 'reprogramado') return [{ accion: 'en_camino', monto_a_devolver: 0 }]
    if (p.estado === 'en_ruta')
      return [
        { accion: 'entregado', monto_a_devolver: faltantesPorDevolver(p) },
        { accion: 'no_entregado', monto_a_devolver: 0 },
      ]
    if (p.estado === 'no_entregado' || ((p.estado === 'pagado' || p.estado === 'enviado_a_comercio') && !preparando)) return [{ accion: 'cancelar_con_devolucion', monto_a_devolver: queda }]
    return []
  }

  const plazoRetracto = (p: Pedido) => (p.entregado_en ? new Date(new Date(p.entregado_en).getTime() + 90 * DIA).toISOString() : null)

  const fila = (p: Pedido) => ({
    id: p.id,
    estado: p.estado,
    referencia: p.referencia,
    entregado_en: p.entregado_en,
    partes: p.partes.map((x) => ({ id: x.id, comercio: x.comercio.nombre_fantasia, referencia: x.referencia, estado: x.estado, estado_codigo: x.estado_codigo })),
    pagado_en: p.pagado_en,
    total_confirmado: total(p),
    numero_partes: p.partes.length,
    incidencia_abierta: incidenciaAbierta(p),
    devolucion_sin_terminar: sinTerminar(p),
  })

  const detalle = (p: Pedido) => ({
    id: p.id,
    referencia: p.referencia,
    estado: p.estado,
    pagado_en: p.pagado_en,
    entregado_en: p.entregado_en,
    subtotal_productos: subtotal(p),
    costo_envio: p.costo_envio,
    total_confirmado: total(p),
    partes: p.partes.map((x) => ({ ...x, comercio: { ...x.comercio } })),
    lineas: p.lineas.map((l) => ({ ...l, subtotal: l.precio_unitario * l.cantidad })),
    linea_de_tiempo: [...p.eventos].sort((a, b) => a.en.localeCompare(b.en)),
    acciones: acciones(p),
    retracto_plazo_hasta: p.estado === 'entregado' || p.estado === 'cerrado' ? plazoRetracto(p) : null,
  })

  const cobro = (p: Pedido) => ({
    pedido_id: p.id,
    referencia: p.referencia,
    total_confirmado: total(p),
    cobrado: cobrado(p),
    devuelto: devuelto(p),
    queda_cobrado: cobrado(p) - devuelto(p),
    estado_cargo: cobrado(p) === 0 ? 'sin_cargo' : devuelto(p) >= cobrado(p) ? 'anulado' : devuelto(p) > 0 ? 'devuelto_parcial' : 'pagado',
    ventas: p.ventas.map((v) => ({ ...v })),
    anulaciones: p.anulaciones.map(({ intentos: _i, ...a }) => ({ ...a })),
    calza: cobrado(p) <= total(p) && !p.anulaciones.some((a) => a.estado === 'rechazada'),
  })

  const vistaRetracto = (r: Retracto) => {
    const p = pedidos.find((x) => x.id === r.pedido_id)!
    return {
      id: r.id,
      pedido_id: r.pedido_id,
      estado: r.estado,
      solicitado_en: r.solicitado_en,
      plazo_hasta: r.plazo_hasta,
      incluye_envio: r.incluye_envio,
      monto: r.monto,
      origen: r.origen,
      resuelto_en: r.resuelto_en,
      referencia: p.referencia,
      lineas: r.lineas.map((x) => {
        const l = p.lineas.find((y) => y.id === x.linea_id)!
        return { linea_id: l.id, producto: l.producto, presentacion: l.presentacion, cantidad: x.cantidad, monto: l.precio_unitario * x.cantidad }
      }),
      motivo_rechazo: r.motivo_rechazo,
    }
  }

  const vistaIncidencia = (i: Incidencia) => ({ ...i, referencia: pedidos.find((p) => p.id === i.pedido_id)?.referencia ?? null })
  const conEtag = (i: Incidencia, status = 200) => ok(vistaIncidencia(i), status, { etag: `"i${i.version}"` })
  const vistaOferta = (o: Oferta) => ({ id: o.id, comercio: { ...o.comercio }, producto: o.producto, presentacion: o.presentacion, precio: o.precio, stock: o.stock, disponible: o.disponible, editable: o.comercio.ficticio, version: `"o${o.version}"` })

  const GRUPOS: Record<string, EstadoPedido[]> = {
    por_atender: ['pagado', 'enviado_a_comercio', 'preparando', 'listo_retiro', 'retirado', 'reprogramado'],
    en_camino: ['en_ruta'],
    con_problema: ['no_entregado'],
    cerrados: ['entregado', 'cerrado'],
    cancelados: ['cancelado_con_devolucion', 'cancelado'],
  }

  // --------------------------------------------------------------- rutas

  function atender(q: PeticionDoble): RespuestaDoble | null {
    const { metodo, ruta, cuerpo } = q
    const c = (cuerpo ?? {}) as Record<string, unknown>
    const falla = modo === 'operacion-falla'

    if (metodo === 'GET' && ruta === '/v1/operacion/pedidos') {
      if (falla) return problema(500, 'interno')
      const grupo = q.query.get('grupo')
      if (grupo && !(grupo in GRUPOS) && grupo !== 'todos') return problema(422, 'validacion')
      const lista = pedidos.filter((p) => {
        if (grupo === 'todos') return true
        if (!grupo) return p.estado !== 'cerrado' && p.estado !== 'cancelado' && p.estado !== 'cancelado_con_devolucion'
        if (grupo === 'con_problema') return GRUPOS.con_problema.includes(p.estado) || incidenciaAbierta(p) || sinTerminar(p)
        return GRUPOS[grupo].includes(p.estado)
      })
      lista.sort((a, b) => b.pagado_en.localeCompare(a.pagado_en))
      return ok({ pedidos: lista.map(fila), hay_mas: false })
    }

    if (metodo === 'POST' && ruta === '/v1/operacion/pedidos/buscar') {
      const ref = typeof c.referencia === 'string' ? c.referencia.trim().toLowerCase() : ''
      if (!ref || ref.length > 64) return problema(422, 'validacion')
      const lista = pedidos.filter((p) => p.referencia.toLowerCase() === ref || p.partes.some((x) => x.referencia.toLowerCase() === ref))
      return ok({ pedidos: lista.map(fila), hay_mas: false })
    }

    if (metodo === 'GET' && ruta === '/v1/operacion/cobros/pendientes') {
      if (falla) return problema(500, 'interno')
      const limite = ahora().getTime() - 15 * MIN
      return ok({
        ventas_sin_respuesta: pedidos.flatMap((p) =>
          p.ventas
            .filter((v) => (v.estado === 'iniciada' || v.estado === 'autorizando') && new Date(v.creada_en).getTime() < limite)
            .map((v) => ({ pedido_id: p.id, referencia: p.referencia, buy_order: v.buy_order, monto: v.monto, creada_en: v.creada_en })),
        ),
        anulaciones_sin_terminar: pedidos.flatMap((p) =>
          // Decisión 467: `en_curso` mientras MATU la pide a Transbank; `sin_terminar` si el último intento falló.
          p.anulaciones
            .filter((a) => a.estado !== 'hecha')
            .map((a) => ({ pedido_id: p.id, estado: a.estado === 'en_curso' ? 'en_curso' : 'sin_terminar', referencia: p.referencia, motivo: a.motivo, monto: a.monto, creada_en: a.en, intentos: a.intentos })),
        ),
      })
    }

    let m = /^\/v1\/operacion\/pedidos\/([^/]+)(?:\/([a-z-]+))?$/.exec(ruta)
    if (m) {
      const p = pedidos.find((x) => x.id === m![1])
      if (!p) return problema(404, 'no-encontrado')
      const paso = m[2]
      if (metodo === 'GET' && !paso) return ok(detalle(p))
      if (metodo === 'GET' && paso === 'cobro') return ok(cobro(p))
      if (metodo === 'POST' && paso === 'en-camino') {
        if (p.estado !== 'retirado' && p.estado !== 'reprogramado') return problema(409, 'estado-pedido')
        return cambiar(p, 'en_ruta')
      }
      if (metodo === 'POST' && paso === 'entregado') {
        if (p.estado !== 'en_ruta') return problema(409, 'estado-pedido')
        p.entregado_en = ahora().toISOString()
        const porDevolver = faltantesPorDevolver(p)
        if (porDevolver > 0) {
          p.anulaciones.push({ id: nuevoId(), motivo: 'producto_no_entregado', monto: porDevolver, estado: 'en_curso', producto: null, en: ahora().toISOString(), intentos: 1 })
          for (const l of p.lineas) if (l.unidades_faltantes > 0) l.devolucion = 'en_curso'
        }
        return cambiar(p, 'entregado')
      }
      if (metodo === 'POST' && paso === 'no-entregado') {
        if (p.estado !== 'en_ruta') return problema(409, 'estado-pedido')
        return cambiar(p, 'no_entregado')
      }
      if (metodo === 'POST' && paso === 'cancelar-con-devolucion') {
        if (!acciones(p).some((a) => a.accion === 'cancelar_con_devolucion')) return problema(409, 'no-cancelable')
        const monto = cobrado(p) - devuelto(p)
        for (const x of p.partes)
          if (x.estado !== 'retirada' && x.estado !== 'cancelada') {
            x.estado = 'cancelada'
            x.cancelada_en = ahora().toISOString()
          }
        p.anulaciones.push({ id: nuevoId(), motivo: 'cancelacion', monto, estado: 'hecha', producto: null, en: ahora().toISOString(), intentos: 1 })
        p.eventos.push({ ...ev(0, 'anulacion', 'sistema', 'hecha', { motivo: 'cancelacion', monto }), en: ahora().toISOString() })
        return cambiar(p, 'cancelado_con_devolucion')
      }
      if (metodo === 'POST' && paso === 'incidencias') {
        const tipos = ['faltante', 'entrega_fallida', 'reclamo_familia', 'cobro_sin_respuesta', 'devolucion_pendiente', 'otro']
        const d = typeof c.descripcion === 'string' ? c.descripcion.trim() : ''
        const errores = [
          ...(typeof c.tipo === 'string' && tipos.includes(c.tipo) ? [] : [{ campo: 'tipo', mensaje: 'MENSAJE DEL DOBLE', tipo: 'enum' }]),
          ...(d.length === 0 ? [{ campo: 'descripcion', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_too_short' }] : d.length > 500 ? [{ campo: 'descripcion', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_too_long' }] : []),
        ]
        if (errores.length) return problema(422, 'validacion', { errores })
        const i: Incidencia = {
          id: nuevoId(),
          pedido_id: p.id,
          tipo: c.tipo as Incidencia['tipo'],
          estado: 'abierta',
          descripcion: d,
          resolucion: null,
          creada_en: ahora().toISOString(),
          resuelta_en: null,
          asignada: c.asignarme === true,
          asignada_a_mi: c.asignarme === true,
          version: 1,
        }
        incidencias.push(i)
        p.eventos.push({ ...ev(0, 'incidencia', 'operacion', 'abierta', { motivo: i.tipo }), en: i.creada_en })
        return conEtag(i, 201)
      }
      if (metodo === 'POST' && paso === 'retractos') return retractoPorCorreo(p, c)
      return problema(404, 'no-encontrado')
    }

    m = /^\/v1\/operacion\/partes\/([^/]+)\/codigo$/.exec(ruta)
    if (m && metodo === 'POST') {
      const p = pedidos.find((x) => x.partes.some((y) => y.id === m![1]))
      const x = p?.partes.find((y) => y.id === m![1])
      if (!x) return problema(404, 'no-encontrado')
      if (x.estado !== 'lista') return problema(409, 'estado-parte')
      x.estado_codigo = 'vigente'
      x.codigo_expira_en = new Date(ahora().getTime() + 4 * 60 * MIN).toISOString()
      return ok({ parte_id: x.id, codigo: CODIGO_RETIRO_DE_EJEMPLO, expira_en: x.codigo_expira_en }, 201)
    }

    if (metodo === 'GET' && ruta === '/v1/operacion/retractos') {
      if (falla) return problema(500, 'interno')
      // Decisión 466: `estado` repetido se suma; sin él, los por resolver. Primero los por resolver, del más
      // antiguo, y después los resueltos, del resuelto más reciente; hasta 200, con `hay_mas`.
      const enLaConsulta = q.query.getAll('estado')
      const validos = ['solicitado', 'devuelto', 'rechazado']
      if (enLaConsulta.some((e) => !validos.includes(e))) return problema(422, 'validacion', { errores: [{ campo: 'estado', mensaje: 'MENSAJE DEL DOBLE', tipo: 'enum' }] })
      const estados = enLaConsulta.length ? enLaConsulta : ['solicitado']
      const t = (iso: string | null) => (iso ? new Date(iso).getTime() : 0)
      const elegidos = retractos
        .filter((r) => estados.includes(r.estado))
        .sort((a, b) =>
          a.estado === 'solicitado' && b.estado === 'solicitado'
            ? t(a.solicitado_en) - t(b.solicitado_en)
            : a.estado === 'solicitado'
              ? -1
              : b.estado === 'solicitado'
                ? 1
                : t(b.resuelto_en) - t(a.resuelto_en),
        )
      return ok({ retractos: elegidos.slice(0, 200).map(vistaRetracto), hay_mas: elegidos.length > 200 })
    }
    m = /^\/v1\/operacion\/retractos\/([^/]+)(\/resolver)?$/.exec(ruta)
    if (m) {
      const r = retractos.find((x) => x.id === m![1])
      if (!r) return problema(404, 'no-encontrado')
      if (metodo === 'GET' && !m[2]) return ok(vistaRetracto(r))
      if (metodo === 'POST' && m[2]) {
        const decision = c.decision
        const motivo = c.motivo ?? null
        if (decision !== 'devolver' && decision !== 'rechazar') return problema(422, 'validacion')
        if ((decision === 'rechazar' && motivo !== 'sello_abierto' && motivo !== 'producto_no_recibido') || (decision === 'devolver' && motivo !== null)) return problema(422, 'motivo-rechazo')
        if (r.estado !== 'solicitado') return problema(409, 'retracto-no-resoluble')
        const p = pedidos.find((x) => x.id === r.pedido_id)!
        r.estado = decision === 'devolver' ? 'devuelto' : 'rechazado'
        r.motivo_rechazo = decision === 'rechazar' ? (motivo as Retracto['motivo_rechazo']) : null
        r.resuelto_en = ahora().toISOString()
        if (decision === 'devolver') p.anulaciones.push({ id: nuevoId(), motivo: 'retracto', monto: r.monto, estado: 'hecha', producto: null, en: ahora().toISOString(), intentos: 1 })
        p.eventos.push({ ...ev(0, 'retracto', 'operacion', r.estado, { desde: 'solicitado', motivo: r.motivo_rechazo }), en: ahora().toISOString() })
        return ok(vistaRetracto(r))
      }
    }

    if (metodo === 'GET' && ruta === '/v1/operacion/incidencias') {
      if (falla) return problema(500, 'interno')
      const estado = q.query.get('estado')
      if (estado && !['abierta', 'en_gestion', 'resuelta'].includes(estado)) return problema(422, 'validacion')
      return ok({ incidencias: incidencias.filter((i) => !estado || i.estado === estado).map(vistaIncidencia) })
    }
    m = /^\/v1\/operacion\/incidencias\/([^/]+)$/.exec(ruta)
    if (m) {
      const i = incidencias.find((x) => x.id === m![1])
      if (!i) return problema(404, 'no-encontrado')
      if (metodo === 'GET') return conEtag(i)
      if (metodo === 'PATCH') {
        if (!q.ifMatch) return problema(428, 'falta-version')
        if (q.ifMatch.replace(/^W\//, '') !== `"i${i.version}"`) return problema(412, 'version-desactualizada')
        if (i.estado === 'resuelta') return problema(409, 'incidencia-resuelta')
        const estado = (c.estado ?? null) as Incidencia['estado'] | null
        const resolucion = typeof c.resolucion === 'string' ? c.resolucion.trim() : null
        if (resolucion && resolucion.length > 500) return problema(422, 'validacion', { errores: [{ campo: 'resolucion', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_too_long' }] })
        if (estado === 'resuelta' && !resolucion) return problema(422, 'falta-resolucion', { errores: [{ campo: 'resolucion', mensaje: 'MENSAJE DEL DOBLE', tipo: 'falta_resolucion' }] })
        if (estado) i.estado = estado
        if (resolucion) i.resolucion = resolucion
        if (estado === 'resuelta') i.resuelta_en = ahora().toISOString()
        if (c.asignacion === 'a_mi') i.asignada = i.asignada_a_mi = true
        if (c.asignacion === 'sin_asignar') i.asignada = i.asignada_a_mi = false
        i.version += 1
        if (estado === 'resuelta') pedidos.find((p) => p.id === i.pedido_id)?.eventos.push({ ...ev(0, 'incidencia', 'operacion', 'resuelta', { motivo: i.tipo }), en: ahora().toISOString() })
        return conEtag(i)
      }
    }

    if (metodo === 'GET' && ruta === '/v1/operacion/catalogo') {
      if (falla) return problema(500, 'interno')
      return ok({ ofertas: ofertas.map(vistaOferta) })
    }
    m = /^\/v1\/operacion\/ofertas\/([^/]+)$/.exec(ruta)
    if (m && metodo === 'PATCH') {
      const o = ofertas.find((x) => x.id === m![1])
      if (!o) return problema(404, 'no-encontrado')
      if (!q.ifMatch) return problema(428, 'falta-version')
      if (conflictoPendiente.has(o.id)) {
        conflictoPendiente.delete(o.id)
        o.stock += 1
        o.version += 1
      }
      if (q.ifMatch !== `"o${o.version}"`) return problema(412, 'version-desactualizada')
      if (!o.comercio.ficticio) return problema(409, 'comercio-real')
      const precio = c.precio ?? o.precio
      const stock = c.stock ?? o.stock
      const disponible = c.disponible ?? o.disponible
      if (!Number.isInteger(precio) || (precio as number) <= 0 || (precio as number) > 9_999_999 || !Number.isInteger(stock) || (stock as number) < 0 || (stock as number) > 9999 || typeof disponible !== 'boolean')
        return problema(422, 'validacion', { errores: [{ campo: 'precio', mensaje: 'MENSAJE DEL DOBLE', tipo: 'greater_than' }] })
      Object.assign(o, { precio, stock, disponible, version: o.version + 1 })
      return ok(vistaOferta(o), 200, { etag: `"o${o.version}"` })
    }

    return ruta.startsWith('/v1/operacion') ? problema(404, 'no-encontrado') : null
  }

  function cambiar(p: Pedido, hacia: EstadoPedido): RespuestaDoble {
    p.eventos.push({ ...ev(0, 'estado', 'operacion', hacia, { desde: p.estado }), en: ahora().toISOString() })
    p.estado = hacia
    return ok({ pedido_id: p.id, estado: hacia })
  }

  function retractoPorCorreo(p: Pedido, c: Record<string, unknown>): RespuestaDoble {
    if (p.estado !== 'entregado' && p.estado !== 'cerrado') return problema(404, 'no-encontrado')
    // D-81-9: el correo solo se compara; nunca se guarda, se devuelve ni se escribe en la consola.
    if (typeof c.correo_solicitante !== 'string' || c.correo_solicitante.trim().toLowerCase() !== CORREO_ADMIN_DE_EJEMPLO) return problema(422, 'solicitante-invalido')
    const plazo = plazoRetracto(p)
    if (plazo && new Date(plazo).getTime() < ahora().getTime()) return problema(409, 'fuera-de-plazo', { plazo_hasta: plazo })
    // Hueco 4 (decidido): no hay 409 `retracto-en-curso`. Se admiten varios retractos por pedido mientras queden
    // unidades sin pedir; las ya pedidas (en cualquier retracto anterior, también los no aceptados) dan 422.
    const yaPedidas = (lineaId: string) =>
      retractos.filter((r) => r.pedido_id === p.id).reduce((t, r) => t + r.lineas.filter((x) => x.linea_id === lineaId).reduce((u, x) => u + x.cantidad, 0), 0)
    const lineas = Array.isArray(c.lineas) ? (c.lineas as { linea_id?: unknown; cantidad?: unknown }[]) : []
    const validas = lineas.every((x) => {
      const l = p.lineas.find((y) => y.id === x.linea_id)
      return l && Number.isInteger(x.cantidad) && (x.cantidad as number) >= 1 && (x.cantidad as number) <= l.cantidad - l.unidades_faltantes - yaPedidas(l.id)
    })
    if (!lineas.length || !validas) return problema(422, 'producto-no-retractable')
    const r: Retracto = {
      id: nuevoId(),
      pedido_id: p.id,
      estado: 'solicitado',
      solicitado_en: ahora().toISOString(),
      plazo_hasta: new Date(ahora().getTime() + 10 * DIA).toISOString(),
      incluye_envio: false,
      monto: lineas.reduce((s, x) => s + p.lineas.find((y) => y.id === x.linea_id)!.precio_unitario * (x.cantidad as number), 0),
      origen: 'correo',
      lineas: lineas.map((x) => ({ linea_id: String(x.linea_id), cantidad: x.cantidad as number })),
      motivo_rechazo: null,
      resuelto_en: null,
    }
    retractos.push(r)
    p.eventos.push({ ...ev(0, 'retracto', 'familia', 'solicitado'), en: r.solicitado_en })
    return ok(vistaRetracto(r), 201)
  }

  return { atender, estado: { pedidos, retractos, incidencias, ofertas } }
}

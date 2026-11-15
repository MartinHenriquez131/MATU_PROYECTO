// Doble de la consola del comercio (MATU-63; contrato docs/api/openapi.json, decisiones 407 a 425)
// para desarrollo y la revisión visual. Responde /v1/comercio/** por HTTP de verdad, con el ETag, el
// If-Match, 409, 412, 422 `lineas-pendientes`, 429 con Retry-After y 503. Datos sintéticos: el
// comercio es de prueba, los pedidos son inventados y nunca llevan quién pide ni a dónde va.
//
// Cuentas (contraseña de ejemplo de doble/cuentas.ts):
//   comercio@example.com           «Almacén El Ejemplo» (ficticio), partes en cada estado y productos
//   comercio-real@example.com      el mismo, sin `ficticio` (sin «(comercio ficticio)» ni rótulos)
//   comercio-inactivo@example.com  403 `comercio-inactivo`
//   comercio-vacio@example.com     sin partes ni productos
//   comercio-falla@example.com     la lista de partes y la de productos responden 500
//   comercio-lento@example.com     todo tarda 2 s, para ver «Cargando…»
//
// Códigos de retiro en una parte lista con el código vigente (el resultado de cada uno):
//   482173 correcto · 999999 vencido · 888888 usado · 777777 cancelada · 666666 bloqueado
//   555555 sin_codigo · 444444 429 (Retry-After 120) · 333333 503 · cualquier otro: no_es
//   (cinco intentos fallidos bloquean el código).
import { randomUUID } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { CUENTAS_COMERCIO } from './cuentas'

type EstadoParte = 'enviada' | 'preparando' | 'lista' | 'retirada' | 'cancelada'
type EstadoCodigo = 'sin_codigo' | 'vigente' | 'usado' | 'bloqueado' | 'vencido'
type EstadoLinea = 'pendiente' | 'preparada' | 'faltante' | 'devuelta'

interface Linea {
  id: string
  producto: { nombre: string; presentacion: string }
  cantidad: number
  estado_linea: EstadoLinea
  unidades_faltantes: number
}
interface Parte {
  id: string
  referencia: string
  estado: EstadoParte
  enviado_en: string
  preparar_antes_de: string
  estado_codigo: EstadoCodigo
  retirada_en: string | null
  cancelada_en: string | null
  lineas: Linea[]
  version: number
  intentos: number
  /** Decisión 430: por qué se canceló (O3 o la familia). */
  motivo?: 'producto_faltante' | 'cancelada_por_familia'
  /** Se cancela sola (la familia o MATU) este instante después de abrirla por primera vez. */
  cancelarAlVer?: number
  cancelaEn?: number
  /** Aparece en la lista este instante después de la primera vez que se pide la lista. */
  llegaTras?: number
  llegaEn?: number
}
interface Producto {
  oferta_id: string
  nombre: string
  presentacion: string
  precio: number
  stock: number
  apartado: number
  disponible: boolean
  version: number
  /** El primer PATCH responde 412: otra persona lo cambió antes. */
  conflicto?: boolean
}
interface Comercio {
  nombre_fantasia: string
  ficticio: boolean
  inactivo?: boolean
  falla?: boolean
  lento?: boolean
  partes: Parte[]
  productos: Producto[]
}

type Responder = {
  json: (res: ServerResponse, status: number, cuerpo: unknown) => void
  problema: (res: ServerResponse, status: number, tipo: string, extra?: Record<string, unknown>) => void
}

/** El contacto de MATU que devuelve `GET /v1/comercio` (CORREO_PRIVACIDAD en la API). */
const CONTACTO = 'cuidaconmatu@gmail.com'

export { CUENTAS_COMERCIO }
export const esCuentaDeComercio = (modo: string | undefined) => !!modo && modo.startsWith('comercio')

const minutos = (n: number) => new Date(Date.now() + n * 60_000).toISOString()

const linea = (nombre: string, presentacion: string, cantidad: number, estado_linea: EstadoLinea = 'pendiente', unidades_faltantes = 0): Linea => ({
  id: randomUUID(),
  producto: { nombre, presentacion },
  cantidad,
  estado_linea,
  unidades_faltantes,
})

const PANAL = ['Pañal adulto M x30', 'Paquete de 30 unidades'] as const
const SUPLEMENTO = ['Suplemento vainilla x12', 'Caja de 12 unidades'] as const
const TOALLITAS = ['Toallitas húmedas x80', 'Paquete de 80 unidades'] as const
const CREMA = ['Crema protectora 200 g', 'Pote de 200 gramos'] as const
const SACHET = ['Espesante en polvo x20', 'Caja de 20 sobres'] as const

function parte(referencia: string, estado: EstadoParte, llegoHace: number, lineas: Linea[], extra: Partial<Parte> = {}): Parte {
  return {
    id: randomUUID(),
    referencia,
    estado,
    enviado_en: minutos(-llegoHace),
    // «Preparar antes de»: dos horas después de llegar (decisión 411).
    preparar_antes_de: minutos(-llegoHace + 120),
    estado_codigo: estado === 'lista' ? 'vigente' : estado === 'retirada' ? 'usado' : 'sin_codigo',
    retirada_en: null,
    cancelada_en: null,
    lineas,
    version: 1,
    intentos: 5,
    ...extra,
  }
}

function partesDeEjemplo(): Parte[] {
  return [
    // Por preparar: una atrasada y una a tiempo.
    parte('K4M7XP', 'enviada', 140, [linea(...PANAL, 2), linea(...SUPLEMENTO, 3), linea(...TOALLITAS, 1)]),
    parte('R8T2WQ', 'enviada', 30, [linea(...CREMA, 1)]),
    // Se cancela 40 s después de abrirla: el aviso «se canceló» con el detalle a la vista (5.5).
    parte('C9N3FA', 'enviada', 10, [linea(...SACHET, 2), linea(...TOALLITAS, 1)], { cancelarAlVer: 40_000 }),
    // Preparando: una línea marcada, una sin marcar.
    parte('H6N3VD', 'preparando', 50, [linea(...PANAL, 1, 'preparada'), linea(...SUPLEMENTO, 2)]),
    // Listas: con el código vigente, vencido, bloqueado y sin código.
    parte('P5Q8ZA', 'lista', 70, [linea(...PANAL, 2, 'preparada'), linea(...SUPLEMENTO, 3, 'faltante', 1), linea(...TOALLITAS, 1, 'faltante', 1)]),
    parte('W2X9TE', 'lista', 80, [linea(...CREMA, 1, 'preparada')], { estado_codigo: 'vencido' }),
    parte('M3B6KS', 'lista', 85, [linea(...SACHET, 1, 'preparada')], { estado_codigo: 'bloqueado', intentos: 0 }),
    parte('Y7D4GU', 'lista', 90, [linea(...TOALLITAS, 2, 'preparada')], { estado_codigo: 'sin_codigo' }),
    // Retirados y cancelados de hoy.
    parte('T8F2HJ', 'retirada', 200, [linea(...PANAL, 1, 'preparada')], { retirada_en: minutos(-40) }),
    parte('Z5V7NQ', 'cancelada', 180, [linea(...CREMA, 2)], { cancelada_en: minutos(-60) }),
    // Llega 65 s después de abrir la lista: «Llegó un pedido nuevo» (5.5).
    parte('G4J8RB', 'enviada', 0, [linea(...SUPLEMENTO, 1)], { llegaTras: 65_000 }),
  ]
}

function productosDeEjemplo(): Producto[] {
  const p = (nombre: string, presentacion: string, precio: number, stock: number, apartado: number, disponible = true, extra: Partial<Producto> = {}): Producto => ({
    oferta_id: randomUUID(),
    nombre,
    presentacion,
    precio,
    stock,
    apartado,
    disponible,
    version: 1,
    ...extra,
  })
  return [
    p(...PANAL, 12_990, 14, 3),
    p(...CREMA, 6_490, 5, 0, false),
    p(...SUPLEMENTO, 18_990, 2, 4),
    p(...TOALLITAS, 3_290, 0, 0),
    p('Guantes de nitrilo x100', 'Caja de 100 unidades', 8_990, 20, 2, true, { conflicto: true }),
    p(...SACHET, 15_490, 9, 1, false),
  ]
}

function comercioDe(modo: string): Comercio {
  const base = { nombre_fantasia: 'Almacén El Ejemplo', ficticio: true, partes: partesDeEjemplo(), productos: productosDeEjemplo() }
  if (modo === 'comercio-real') return { ...base, nombre_fantasia: 'Farmacia Del Ejemplo', ficticio: false }
  if (modo === 'comercio-inactivo') return { ...base, inactivo: true }
  if (modo === 'comercio-vacio') return { ...base, partes: [], productos: [] }
  if (modo === 'comercio-falla') return { ...base, falla: true }
  if (modo === 'comercio-lento') return { ...base, lento: true }
  return base
}

// Estado en memoria, por cuenta: se pierde al reiniciar `npm run dev` (así se vuelve a cero).
const comercios = new Map<string, Comercio>()
const delCorreo = (email: string, modo: string) => {
  let c = comercios.get(email)
  if (!c) comercios.set(email, (c = comercioDe(modo)))
  return c
}

/** Lo que se ve de una parte en un momento: las que se cancelan o llegan solas. */
function alDia(p: Parte) {
  if (p.cancelaEn && Date.now() >= p.cancelaEn && p.estado !== 'cancelada') {
    p.estado = 'cancelada'
    p.cancelada_en = new Date().toISOString()
    p.version += 1
  }
}
const visible = (p: Parte) => !p.llegaTras || (p.llegaEn !== undefined && Date.now() >= p.llegaEn)

const resumen = (p: Parte) => ({
  id: p.id,
  referencia: p.referencia,
  estado: p.estado,
  enviado_en: p.llegaEn ? new Date(p.llegaEn).toISOString() : p.enviado_en,
  preparar_antes_de: p.llegaEn ? new Date(p.llegaEn + 120 * 60_000).toISOString() : p.preparar_antes_de,
  estado_codigo: p.estado_codigo,
  numero_lineas: p.lineas.length,
  retirada_en: p.retirada_en,
  cancelada_en: p.cancelada_en,
  motivo_cancelacion: p.estado === 'cancelada' ? (p.motivo ?? 'cancelada_por_familia') : null,
})
const vista = (p: Parte) => ({ ...resumen(p), lineas: p.lineas.map((l) => ({ ...l, producto: { ...l.producto } })) })
const productoVista = (p: Producto) => {
  const { version, conflicto, ...resto } = p
  void conflicto
  return { ...resto, disponibles: Math.max(0, p.stock - p.apartado), etag: `"v${version}"` }
}

export async function atenderComercio(
  req: IncomingMessage,
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  r: Responder,
  cuenta: { email: string; modo: string | undefined },
): Promise<void> {
  const { json, problema } = r
  const metodo = req.method ?? 'GET'
  const ruta = (req.url ?? '').split('?')[0]
  // Decisión 409: sin cuenta de comercio, 404; con la cuenta o el comercio inactivos, 403.
  if (!esCuentaDeComercio(cuenta.modo)) return problema(res, 404, '/errores/no-encontrado')
  const c = delCorreo(cuenta.email, cuenta.modo!)
  if (c.inactivo) return problema(res, 403, '/errores/comercio-inactivo')
  if (c.lento) await new Promise((listo) => setTimeout(listo, 2000))
  res.setHeader('Cache-Control', 'no-store')

  if (metodo === 'GET' && ruta === '/v1/comercio') return json(res, 200, { nombre_fantasia: c.nombre_fantasia, ficticio: c.ficticio, contacto: CONTACTO })

  if (metodo === 'GET' && ruta === '/v1/comercio/partes') {
    if (c.falla) return problema(res, 500, '/errores/interno')
    for (const p of c.partes) {
      if (p.llegaTras && p.llegaEn === undefined) p.llegaEn = Date.now() + p.llegaTras
      alDia(p)
    }
    return json(res, 200, { partes: c.partes.filter(visible).map(resumen) })
  }

  if (metodo === 'GET' && ruta === '/v1/comercio/productos') {
    if (c.falla) return problema(res, 500, '/errores/interno')
    return json(res, 200, { productos: c.productos.map(productoVista) })
  }

  const prod = /^\/v1\/comercio\/productos\/([^/]+)$/.exec(ruta)
  if (prod && metodo === 'PATCH') {
    const p = c.productos.find((x) => x.oferta_id === prod[1])
    if (!p) return problema(res, 404, '/errores/no-encontrado')
    const ifMatch = req.headers['if-match']
    if (p.conflicto) {
      // Otra persona del comercio lo cambió antes: la versión sube y el número cambia.
      p.conflicto = false
      p.stock += 5
      p.version += 1
      return problema(res, 412, '/errores/version-desactualizada')
    }
    if (ifMatch && ifMatch !== `"v${p.version}"`) return problema(res, 412, '/errores/version-desactualizada')
    const stock = cuerpo?.stock
    const disponible = cuerpo?.disponible
    const malo = (stock !== undefined && stock !== null && (typeof stock !== 'number' || !Number.isInteger(stock) || stock < 0 || stock > 9999)) || (disponible !== undefined && disponible !== null && typeof disponible !== 'boolean')
    if (malo) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'stock', mensaje: 'MENSAJE DEL DOBLE', tipo: 'less_than_equal' }] })
    if (typeof stock === 'number') p.stock = stock
    if (typeof disponible === 'boolean') p.disponible = disponible
    p.version += 1
    return json(res, 200, productoVista(p))
  }

  const m = /^\/v1\/comercio\/partes\/([^/]+)(?:\/(preparar|listo|validar-codigo|lineas\/([^/]+)))?$/.exec(ruta)
  if (!m) return problema(res, 404, '/errores/no-encontrado')
  const p = c.partes.find((x) => x.id === m[1] && visible(x))
  if (!p) return problema(res, 404, '/errores/no-encontrado')
  alDia(p)
  const accion = m[2]
  const conVersion = (status = 200) => {
    res.setHeader('ETag', `"v${p.version}"`)
    json(res, status, vista(p))
  }

  if (metodo === 'GET' && !accion) {
    if (p.cancelarAlVer && !p.cancelaEn) p.cancelaEn = Date.now() + p.cancelarAlVer
    return conVersion()
  }

  if (metodo === 'POST' && accion === 'validar-codigo') {
    const codigo = cuerpo?.codigo
    if (typeof codigo !== 'string' || !/^[0-9]{6}$/.test(codigo)) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'codigo', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_pattern_mismatch' }] })
    if (codigo === '444444') return res.setHeader('Retry-After', '120'), problema(res, 429, '/errores/demasiados-intentos')
    if (codigo === '333333') return problema(res, 503, '/errores/servicio-no-disponible')
    const responder = (resultado: string) => json(res, 200, { resultado, intentos_restantes: p.intentos, parte: vista(p) })
    if (p.estado === 'cancelada') return responder('cancelada')
    if (p.estado === 'retirada' || p.estado_codigo === 'usado') return responder('usado')
    if (p.estado_codigo === 'sin_codigo') return responder('sin_codigo')
    if (p.estado_codigo === 'bloqueado') return responder('bloqueado')
    if (p.estado_codigo === 'vencido') return responder('vencido')
    if (codigo === '482173') {
      p.estado = 'retirada'
      p.estado_codigo = 'usado'
      p.retirada_en = new Date().toISOString()
      p.version += 1
      return responder('correcto')
    }
    if (codigo === '999999') return (p.estado_codigo = 'vencido'), responder('vencido')
    // Ya se retiró (por ejemplo, desde otro teléfono del comercio): la parte queda retirada.
    if (codigo === '888888') return (p.estado = 'retirada'), (p.estado_codigo = 'usado'), (p.retirada_en ??= new Date().toISOString()), p.version++, responder('usado')
    if (codigo === '777777') return (p.estado = 'cancelada'), (p.cancelada_en = new Date().toISOString()), p.version++, responder('cancelada')
    if (codigo === '666666') return (p.estado_codigo = 'bloqueado'), (p.intentos = 0), responder('bloqueado')
    if (codigo === '555555') return responder('sin_codigo')
    p.intentos = Math.max(0, p.intentos - 1)
    if (p.intentos === 0) return (p.estado_codigo = 'bloqueado'), responder('bloqueado')
    return responder('no_es')
  }

  // Preparar, marcar y «Listo»: If-Match opcional (decisión 413).
  const ifMatch = req.headers['if-match']
  if (ifMatch && ifMatch !== `"v${p.version}"`) return problema(res, 412, '/errores/version-desactualizada')

  if (metodo === 'POST' && accion === 'preparar') {
    if (p.estado !== 'enviada') return problema(res, 409, '/errores/estado-parte')
    p.estado = 'preparando'
    p.version += 1
    return conVersion()
  }

  if (metodo === 'PUT' && m[3]) {
    if (p.estado !== 'preparando') return problema(res, 409, '/errores/estado-parte')
    const l = p.lineas.find((x) => x.id === m[3])
    if (!l) return problema(res, 404, '/errores/no-encontrado')
    const estado = cuerpo?.estado
    const faltan = cuerpo?.unidades_faltantes
    if (estado !== 'preparada' && estado !== 'faltante') return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'estado', mensaje: 'MENSAJE DEL DOBLE', tipo: 'literal_error' }] })
    if (faltan !== undefined && faltan !== null && (typeof faltan !== 'number' || !Number.isInteger(faltan) || faltan < 1 || faltan > l.cantidad))
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'unidades_faltantes', mensaje: 'MENSAJE DEL DOBLE', tipo: 'less_than_equal' }] })
    l.estado_linea = estado
    l.unidades_faltantes = estado === 'faltante' ? (typeof faltan === 'number' ? faltan : l.cantidad) : 0
    p.version += 1
    return conVersion()
  }

  if (metodo === 'POST' && accion === 'listo') {
    if (p.estado !== 'preparando') return problema(res, 409, '/errores/estado-parte')
    if (p.lineas.some((l) => l.estado_linea === 'pendiente')) return problema(res, 422, '/errores/lineas-pendientes')
    // O3: sin ninguno que entregar, la parte queda cancelada (motivo producto_faltante).
    const ninguno = p.lineas.every((l) => l.estado_linea === 'faltante' && l.unidades_faltantes >= l.cantidad)
    if (ninguno) {
      p.estado = 'cancelada'
      p.motivo = 'producto_faltante'
      p.cancelada_en = new Date().toISOString()
    } else {
      p.estado = 'lista'
      p.estado_codigo = 'vigente'
      p.intentos = 5
    }
    p.version += 1
    return conVersion()
  }

  return problema(res, 404, '/errores/no-encontrado')
}

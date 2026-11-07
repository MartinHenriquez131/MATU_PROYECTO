// Doble del consumo (MATU-36, contrato docs/api/openapi.json): la lista con `activo` y cursor,
// crear, cambiar con `If-Match` (412 y 428), seguir y dejar de seguir, eliminar y la autorización
// con finalidad `consumo`. Responde por HTTP de verdad y no entra al build. Datos sintéticos: los
// nombres son de insumos comunes, sin remedios (ADR-022).
import { randomUUID } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'

type Unidad = 'unidad' | 'sobre' | 'ml' | 'g'
type Rol = 'admin' | 'cuidador' | 'pagador' | 'observador'

export interface PerfilDoble {
  id: string
  nombre_libre: string
  unidad: Unidad
  tasa_unidades: number
  tasa_dias: number
  stock_unidades: number
  stock_medido_en: string
  dias_aviso: number
  activo: boolean
  version: number
  autor: { id: string; nombre: string } | null
  /** MATU-60 (decisión 121): cuántas unidades trae cada envase, o `null`. */
  unidades_por_envase?: number | null
}

export interface AlertaDoble {
  id: string
  perfil_id: string
  fecha_prevista: string
  estado: 'pendiente' | 'notificada' | 'resuelta' | 'descartada'
  creada_en: string
  notificada_en: string | null
  cerrada_en: string | null
}

export interface ConsumoDoble {
  autorizacion: 'no' | 'vigente' | 'vencida'
  perfiles: PerfilDoble[]
  /** MATU-37: las alertas que ya creó «el trabajo diario». Un perfil sin alerta da `alerta_id: null`. */
  alertas?: AlertaDoble[]
}

type Responder = {
  json: (res: ServerResponse, status: number, cuerpo: unknown) => void
  problema: (res: ServerResponse, status: number, tipo: string, extra?: Record<string, unknown>) => void
}

/** Página corta a propósito: la primera página trae `siguiente_cursor` (especificación 8). */
const PAGINA = 9
const MAX_COBERTURA = 3650

const DIA = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Santiago', year: 'numeric', month: '2-digit', day: '2-digit' })
const hoy = () => DIA.format(new Date())
const sumar = (iso: string, n: number) => {
  const [a, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(a, m - 1, d + n)).toISOString().slice(0, 10)
}
const entre = (a: string, b: string) => Math.round((Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 86_400_000)
const cobertura = (p: Pick<PerfilDoble, 'stock_unidades' | 'tasa_dias' | 'tasa_unidades'>) => Math.floor((p.stock_unidades * p.tasa_dias) / p.tasa_unidades)

export const RODRIGO_CONSUMO = { id: randomUUID(), nombre: 'Rodrigo' }

/** Un perfil anotado hace `hace` días. */
export function perfil(nombre: string, unidad: Unidad, tasa: number, cada: number, stock: number, hace: number, autor: { id: string; nombre: string } | null, activo = true, aviso = 7): PerfilDoble {
  return { id: randomUUID(), nombre_libre: nombre, unidad, tasa_unidades: tasa, tasa_dias: cada, stock_unidades: stock, stock_medido_en: sumar(hoy(), -hace), dias_aviso: aviso, activo, version: 1, autor }
}

/** La lista de la especificación 8: 6, 1 y 0 días, −2, 60 caracteres sin espacios, por sobre, cada 2 días y tres sin seguir: la primera página (9) muestra dos sin seguir y «Ver más» trae el tercero. */
export function listaCompleta(autor: { id: string; nombre: string }): PerfilDoble[] {
  return [
    perfil('Pañal adulto talla M', 'unidad', 4, 1, 24, 0, autor),
    perfil('Apósitos para la cama', 'unidad', 2, 1, 8, 3, autor),
    perfil('Guantes desechables', 'unidad', 6, 1, 18, 3, RODRIGO_CONSUMO),
    perfil('Crema humectante', 'unidad', 1, 1, 2, 4, autor),
    perfil('ToallitasHúmedasExtraGrandesSinPerfumeParaPielSensibleXXL60'.slice(0, 60), 'unidad', 3, 1, 48, 1, autor),
    perfil('Champú en sobre', 'sobre', 1, 1, 30, 0, autor),
    perfil('Sabanilla desechable', 'unidad', 1, 2, 10, 2, autor),
    perfil('Toallas de papel', 'unidad', 2, 1, 10, 6, autor, false),
    perfil('Alcohol gel', 'unidad', 1, 3, 4, 10, RODRIGO_CONSUMO, false),
    perfil('Bolsas de basura', 'unidad', 1, 1, 15, 12, autor, false),
  ]
}

function vista(p: PerfilDoble) {
  const quiebre = sumar(p.stock_medido_en, cobertura(p))
  return {
    id: p.id,
    producto: null,
    nombre_libre: p.nombre_libre,
    unidad: p.unidad,
    tasa_unidades: p.tasa_unidades,
    tasa_dias: p.tasa_dias,
    stock_unidades: p.stock_unidades,
    stock_medido_en: p.stock_medido_en,
    dias_aviso: p.dias_aviso,
    fecha_quiebre_estimada: quiebre,
    dias_restantes: entre(hoy(), quiebre),
    activo: p.activo,
    actualizado_por: p.autor,
    unidades_por_envase: p.unidades_por_envase ?? null,
    etag: `"v${p.version}"`,
  }
}

const orden = (a: PerfilDoble, b: PerfilDoble) => Number(b.activo) - Number(a.activo) || vista(a).fecha_quiebre_estimada.localeCompare(vista(b).fecha_quiebre_estimada)

const entero = (v: unknown, min: number, max: number) => typeof v === 'number' && Number.isInteger(v) && v >= min && v <= max

const CAMPOS_EDICION = ['nombre_libre', 'tasa_unidades', 'tasa_dias', 'stock_unidades', 'dias_aviso', 'unidades_por_envase']
const RANGOS: Record<string, [number, number]> = { tasa_unidades: [1, 10_000], tasa_dias: [1, 90], stock_unidades: [0, 100_000], dias_aviso: [0, 60] }

/** Errores de un cuerpo de creación o edición, con los tipos del contrato. */
function errores(b: Record<string, unknown>, parcial: boolean) {
  const e: { campo: string; mensaje: string; tipo: string }[] = []
  const add = (campo: string, tipo: string) => e.push({ campo, mensaje: 'MENSAJE DEL DOBLE: NO SE MUESTRA', tipo })
  for (const k of Object.keys(b)) if (![...CAMPOS_EDICION, ...(parcial ? [] : ['producto_id', 'unidad'])].includes(k)) add(k, 'extra_forbidden')
  if (!parcial || 'nombre_libre' in b) {
    const n = b.nombre_libre
    if (typeof n !== 'string' || !n.trim()) add('nombre_libre', parcial ? 'null_no_admitido' : 'producto_o_nombre')
    else if (n.length > 60) add('nombre_libre', 'string_too_long')
    else if (/[\u0000-\u001f\u007f]/.test(n)) add('nombre_libre', 'value_error')
  }
  for (const [k, [min, max]] of Object.entries(RANGOS)) {
    if (!(k in b)) {
      if (!parcial && (k === 'tasa_unidades' || k === 'stock_unidades')) add(k, 'missing')
      continue
    }
    const v = b[k]
    if (v === null) add(k, 'null_no_admitido')
    else if (typeof v !== 'number' || !Number.isInteger(v)) add(k, 'int_type')
    else if (v < min) add(k, 'greater_than_equal')
    else if (v > max) add(k, 'less_than_equal')
  }
  // MATU-60: opcional, de 1 a 10.000. `null` no lo trae (al crear) o lo borra (al cambiar).
  if ('unidades_por_envase' in b && b.unidades_por_envase !== null) {
    const v = b.unidades_por_envase
    if (typeof v !== 'number' || !Number.isInteger(v)) add('unidades_por_envase', 'int_type')
    else if (v < 1) add('unidades_por_envase', 'greater_than_equal')
    else if (v > 10_000) add('unidades_por_envase', 'less_than_equal')
  }
  if (!parcial && b.unidad !== undefined && b.unidad !== null && !['unidad', 'sobre', 'ml', 'g'].includes(String(b.unidad))) add('unidad', 'enum')
  if (parcial && !Object.keys(b).length) add('cuerpo', 'cuerpo_vacio')
  return e
}

const conflictosHechos = new Set<string>()

// ---------------------------------------------------------------- MATU-37 alertas

/** La alerta de la fecha estimada actual del perfil, abierta o cerrada. */
const alertaDe = (c: ConsumoDoble, p: PerfilDoble) => (c.alertas ?? []).find((a) => a.perfil_id === p.id && a.fecha_prevista === vista(p).fecha_quiebre_estimada)
const enVentana = (p: PerfilDoble) => p.activo && vista(p).dias_restantes <= p.dias_aviso
const abierta = (a: AlertaDoble | undefined) => !!a && (a.estado === 'pendiente' || a.estado === 'notificada')

function vistaPorAcabarse(c: ConsumoDoble, p: PerfilDoble) {
  const a = alertaDe(c, p)
  return { ...vista(p), avisando: enVentana(p) && (!a || abierta(a)), alerta_id: abierta(a) ? a!.id : null }
}

/** «El trabajo diario»: alertas abiertas para los perfiles en ventana, salvo el último (queda con `alerta_id: null`). */
export function crearAlertas(c: ConsumoDoble): void {
  const ahora = new Date().toISOString()
  const en = c.perfiles.filter(enVentana).sort(orden)
  c.alertas = en.slice(0, Math.max(0, en.length - 1)).map((p, i) => ({
    id: randomUUID(),
    perfil_id: p.id,
    fecha_prevista: vista(p).fecha_quiebre_estimada,
    estado: i === 0 ? 'notificada' : 'pendiente',
    creada_en: ahora,
    notificada_en: i === 0 ? ahora : null,
    cerrada_en: null,
  }))
}

const cerradasUnaVez = new Set<string>()

/** `por-acabarse`, `alertas`, `alertas/{id}/descartar` y `{perfil}/resolver`. Devuelve `false` si la ruta no es de alertas. */
function atenderAlertas(
  metodo: string,
  ruta: string,
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  ctx: { rol: Rol; consumo: ConsumoDoble; usuario: { id: string; nombre: string; modo?: string } },
  r: Responder,
  ifMatch?: string,
): boolean {
  const { json, problema } = r
  const { rol, consumo: c, usuario } = ctx
  const escribe = rol === 'admin' || rol === 'cuidador'
  const ahora = () => new Date().toISOString()

  if (/\/consumo\/por-acabarse$/.test(ruta) && metodo === 'GET') {
    if (usuario.modo === 'alertas-error-carga') return problema(res, 500, '/errores/error-interno'), true
    res.setHeader('Cache-Control', 'no-store')
    const items = c.perfiles.filter(enVentana).sort((a, b) => orden(a, b) || a.id.localeCompare(b.id))
    return json(res, 200, { items: items.map((p) => vistaPorAcabarse(c, p)) }), true
  }
  if (/\/consumo\/alertas$/.test(ruta) && metodo === 'GET') {
    res.setHeader('Cache-Control', 'no-store')
    return json(res, 200, { items: (c.alertas ?? []).filter(abierta), siguiente_cursor: null }), true
  }
  const md = /\/consumo\/alertas\/([^/]+)\/descartar$/.exec(ruta)
  if (md && metodo === 'POST') {
    if (!escribe) return problema(res, 404, '/errores/no-encontrado'), true
    const a = (c.alertas ?? []).find((x) => x.id === decodeURIComponent(md[1]))
    if (!a) return problema(res, 404, '/errores/no-encontrado'), true
    if (!abierta(a)) return problema(res, 409, '/errores/alerta-cerrada', { estado: a.estado }), true
    Object.assign(a, { estado: 'descartada', cerrada_en: ahora() })
    return json(res, 200, a), true
  }
  const mr = /\/consumo\/([^/]+)\/resolver$/.exec(ruta)
  if (mr && metodo === 'POST') {
    if (!escribe) return problema(res, 404, '/errores/no-encontrado'), true
    const p = c.perfiles.find((x) => x.id === decodeURIComponent(mr[1]))
    if (!p) return problema(res, 404, '/errores/no-encontrado'), true
    if (!p.activo) return problema(res, 409, '/errores/perfil-inactivo'), true
    // Decisión 80: siempre condicional.
    if (!ifMatch || ifMatch === '*') return problema(res, 428, '/errores/falta-version'), true
    // Cuenta «alertas-conflicto»: el primer intento de cada insumo encuentra que Rodrigo lo cambió.
    if (usuario.modo === 'alertas-conflicto' && !conflictosHechos.has(p.id)) {
      conflictosHechos.add(p.id)
      Object.assign(p, { version: p.version + 1, autor: RODRIGO_CONSUMO })
    }
    if (ifMatch !== `"v${p.version}"`) {
      res.setHeader('ETag', `"v${p.version}"`)
      return problema(res, 412, '/errores/version-desactualizada', { actual: vista(p) }), true
    }
    const b = cuerpo ?? {}
    for (const k of Object.keys(b))
      if (k !== 'cantidad') return problema(res, 422, '/errores/validacion', { errores: [{ campo: k, mensaje: 'MENSAJE DEL DOBLE', tipo: 'extra_forbidden' }] }), true
    const conCantidad = b.cantidad !== undefined && b.cantidad !== null
    if (conCantidad && !entero(b.cantidad, 1, 9999)) {
      const tipo = typeof b.cantidad === 'number' && Number.isInteger(b.cantidad) ? (b.cantidad < 1 ? 'greater_than_equal' : 'less_than_equal') : 'int_type'
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'cantidad', mensaje: 'MENSAJE DEL DOBLE', tipo }] }), true
    }
    if (usuario.modo === 'alertas-error') return problema(res, 500, '/errores/error-interno'), true
    let a = alertaDe(c, p)
    // Cuenta «alertas-cerrada»: el primer intento encuentra que alguien más ya la cerró.
    if (usuario.modo === 'alertas-cerrada' && !cerradasUnaVez.has(p.id)) {
      cerradasUnaVez.add(p.id)
      if (!a) {
        a = { id: randomUUID(), perfil_id: p.id, fecha_prevista: vista(p).fecha_quiebre_estimada, estado: 'pendiente', creada_en: ahora(), notificada_en: null, cerrada_en: null }
        ;(c.alertas ??= []).push(a)
      }
      Object.assign(a, { estado: 'descartada', cerrada_en: ahora() })
    }
    if (a && !abierta(a)) return problema(res, 409, '/errores/alerta-cerrada', { estado: a.estado }), true
    const estado = conCantidad ? 'resuelta' : 'descartada'
    const fechaPrevista = vista(p).fecha_quiebre_estimada
    if (a) Object.assign(a, { estado, cerrada_en: ahora() })
    if (conCantidad) {
      // Lo que se estima que queda hoy (nunca menos de 0) más lo comprado, medido hoy.
      const dias = entre(p.stock_medido_en, hoy())
      const queda = Math.max(0, p.stock_unidades - Math.floor((dias * p.tasa_unidades) / p.tasa_dias))
      Object.assign(p, { stock_unidades: queda + (b.cantidad as number), stock_medido_en: hoy(), version: p.version + 1, autor: { id: usuario.id, nombre: usuario.nombre } })
    }
    if (!a)
      (c.alertas ??= []).push({
        id: randomUUID(),
        perfil_id: p.id,
        fecha_prevista: fechaPrevista,
        estado,
        creada_en: ahora(),
        notificada_en: null,
        cerrada_en: ahora(),
      })
    return json(res, 200, vistaPorAcabarse(c, p)), true
  }
  return false
}

// ---------------------------------------------------------------- MATU-60 la lista de insumos

const sinMarcas = (t: string) => t.normalize('NFD').replace(/\p{Mn}/gu, '').toLowerCase()

/**
 * `GET …/consumo/lista` (decisiones 116 a 120): lo que está avisando en «Se acaban pronto», en el
 * orden de la decisión 117, con lo que falta para 30 días después de descontar lo que queda hoy.
 */
function listaDe(c: ConsumoDoble) {
  const items = c.perfiles
    .filter((p) => vistaPorAcabarse(c, p).avisando)
    .sort(
      (a, b) =>
        vista(a).fecha_quiebre_estimada.localeCompare(vista(b).fecha_quiebre_estimada) ||
        sinMarcas(a.nombre_libre).localeCompare(sinMarcas(b.nombre_libre)) ||
        a.nombre_libre.toLowerCase().localeCompare(b.nombre_libre.toLowerCase()) ||
        a.id.localeCompare(b.id),
    )
    .map((p) => {
      const dias = entre(p.stock_medido_en, hoy())
      const queda = Math.max(0, Math.floor(p.stock_unidades - (dias * p.tasa_unidades) / p.tasa_dias))
      const unidades = Math.max(1, Math.ceil((30 * p.tasa_unidades) / p.tasa_dias) - queda)
      const envase = p.unidades_por_envase ?? null
      return {
        perfil_id: p.id,
        nombre: p.nombre_libre,
        unidad: p.unidad,
        dias_restantes: vista(p).dias_restantes,
        unidades_sugeridas: unidades,
        unidades_por_envase: envase,
        envases_sugeridos: envase ? Math.ceil(unidades / envase) : null,
      }
    })
  return { fecha: hoy(), items }
}

const conEnvase = (p: PerfilDoble, u: number): PerfilDoble => ({ ...p, unidades_por_envase: u })

/**
 * La lista de la especificación MATU-60 (14): 6, 5, 3, 1, 0 y −2 días, con envase («5 envases de
 * 20 unidades»), sin envase en sobres, en ml con 1 envase, un nombre de 60 caracteres sin
 * espacios, y uno que alcanza para 40 días y no entra.
 */
export function listaParaLista(autor: { id: string; nombre: string }): PerfilDoble[] {
  return [
    conEnvase(perfil('Pañal adulto talla M', 'unidad', 4, 1, 24, 0, autor), 20),
    perfil('Toallitas húmedas', 'unidad', 3, 1, 3, 0, autor),
    perfil('Champú en sobre', 'sobre', 1, 1, 0, 0, autor),
    conEnvase(perfil('Crema humectante', 'ml', 50, 7, 50, 9, autor), 250),
    conEnvase(perfil('Guantes desechables', 'unidad', 6, 1, 30, 0, RODRIGO_CONSUMO), 100),
    perfil('ToallitasHúmedasExtraGrandesSinPerfumeParaPielSensibleXXL60'.slice(0, 60), 'unidad', 3, 1, 9, 0, autor),
    perfil('Bolsas de basura', 'unidad', 1, 1, 40, 0, autor),
  ]
}

/** Atiende `…/consumo…` y `…/consentimientos` de una persona ya resuelta en su grupo. */
export function atenderConsumo(
  req: IncomingMessage,
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  ctx: { rol: Rol; consumo: ConsumoDoble; usuario: { id: string; nombre: string; modo?: string } },
  r: Responder,
): void {
  const { json, problema } = r
  const metodo = req.method ?? 'GET'
  const [ruta, consulta = ''] = (req.url ?? '').split('?')
  const { rol, consumo, usuario } = ctx
  const escribe = rol === 'admin' || rol === 'cuidador'
  const m = /\/(consumo|consentimientos)(?:\/([^/]+))?(?:\/(activar|desactivar))?$/.exec(ruta)
  const deAlertas = /\/consumo\/(por-acabarse|alertas(\/.*)?|[^/]+\/resolver)$/.test(ruta)
  const deLista = /\/consumo\/lista$/.test(ruta)
  if (!m && !deAlertas) return problema(res, 404, '/errores/no-encontrado')
  const [, recurso, perfilId, accion] = m ?? ['', 'consumo', undefined, undefined]

  if (recurso === 'consentimientos') {
    if (metodo !== 'POST' || perfilId || !escribe) return problema(res, 404, '/errores/no-encontrado')
    const b = cuerpo ?? {}
    const calidad = b.calidad_otorgante
    const aviso = b.aviso as { id?: unknown; version?: unknown } | null | undefined
    const ref = typeof b.referencia_documento === 'string' ? b.referencia_documento.trim() : ''
    const mal = (campo: string, tipo: string) => problema(res, 422, '/errores/validacion', { errores: [{ campo, mensaje: 'MENSAJE DEL DOBLE: NO SE MUESTRA', tipo }] })
    if (b.finalidad !== 'consumo') return mal('finalidad', 'literal_error')
    if (!['titular', 'representante_legal', 'cuidador_de_hecho'].includes(String(calidad))) return mal('calidad_otorgante', 'enum')
    if (calidad === 'representante_legal' && !ref) return mal('referencia_documento', 'regla_calidad_otorgante')
    if (calidad === 'cuidador_de_hecho' && aviso?.id !== 'aviso_cuidador_de_hecho') return mal('aviso', 'regla_calidad_otorgante')
    if (calidad === 'titular' && (ref || aviso)) return mal('calidad_otorgante', 'regla_calidad_otorgante')
    if (consumo.autorizacion !== 'no') return problema(res, 409, '/errores/autorizacion-vigente')
    consumo.autorizacion = 'vigente'
    const ahora = new Date()
    return json(res, 201, {
      consentimiento: {
        id: randomUUID(),
        calidad_otorgante: calidad,
        finalidad: 'consumo',
        version_politica: '0.10',
        otorgado_en: ahora.toISOString(),
        revision_vence_en: calidad === 'cuidador_de_hecho' ? new Date(ahora.getTime() + 365 * 86_400_000).toISOString() : null,
      },
      aviso: null,
    })
  }

  // La autorización se evalúa antes de leer nada del consumo (contrato, 403).
  if (consumo.autorizacion === 'no') return problema(res, 403, '/errores/sin-consentimiento', { finalidad: 'consumo' })
  if (consumo.autorizacion === 'vencida') return problema(res, 403, '/errores/revision-vencida', { finalidad: 'consumo' })
  if (deLista) {
    if (metodo !== 'GET') return problema(res, 404, '/errores/no-encontrado')
    if (usuario.modo === 'lista-error') return problema(res, 500, '/errores/error-interno')
    res.setHeader('Cache-Control', 'no-store')
    return json(res, 200, listaDe(consumo))
  }
  if (deAlertas) {
    if (!atenderAlertas(metodo, ruta, res, cuerpo, ctx, r, req.headers['if-match'])) problema(res, 404, '/errores/no-encontrado')
    return
  }

  if (!perfilId) {
    if (metodo === 'GET') {
      const q = new URLSearchParams(consulta)
      const activo = q.get('activo') ?? 'true'
      if (!['true', 'false', 'todos'].includes(activo)) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'activo', mensaje: 'MENSAJE DEL DOBLE', tipo: 'enum' }] })
      const limite = Math.min(Number.parseInt(q.get('limite') ?? '20', 10) || 20, PAGINA)
      const desde = Number.parseInt(q.get('cursor') ?? '0', 10) || 0
      const todos = consumo.perfiles.filter((p) => activo === 'todos' || String(p.activo) === activo).sort(orden)
      const pagina = todos.slice(desde, desde + limite)
      res.setHeader('Cache-Control', 'no-store')
      return json(res, 200, { items: pagina.map(vista), siguiente_cursor: desde + limite < todos.length ? String(desde + limite) : null })
    }
    if (metodo !== 'POST' || !escribe) return problema(res, 404, '/errores/no-encontrado')
    if (usuario.modo === 'insumos-defectos' && cuerpo?.nombre_libre === 'Error') return problema(res, 500, '/errores/error-interno')
    const b = cuerpo ?? {}
    const e = errores(b, false)
    if (e.length) return problema(res, 422, '/errores/validacion', { errores: e })
    const p: PerfilDoble = {
      id: randomUUID(),
      nombre_libre: String(b.nombre_libre).trim(),
      unidad: (b.unidad as Unidad) ?? 'unidad',
      tasa_unidades: b.tasa_unidades as number,
      tasa_dias: (b.tasa_dias as number) ?? 1,
      stock_unidades: b.stock_unidades as number,
      stock_medido_en: hoy(),
      dias_aviso: (b.dias_aviso as number) ?? 7,
      unidades_por_envase: (b.unidades_por_envase as number | null | undefined) ?? null,
      activo: true,
      version: 1,
      autor: { id: usuario.id, nombre: usuario.nombre },
    }
    if (cobertura(p) > MAX_COBERTURA) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'stock_unidades', mensaje: 'MENSAJE DEL DOBLE', tipo: 'cobertura_maxima' }] })
    consumo.perfiles.push(p)
    res.setHeader('ETag', `"v${p.version}"`)
    return json(res, 201, vista(p))
  }

  const p = consumo.perfiles.find((x) => x.id === decodeURIComponent(perfilId))
  if (!p) return problema(res, 404, '/errores/no-encontrado')
  if (metodo === 'GET' && !accion) return json(res, 200, vista(p))
  if (!escribe) return problema(res, 404, '/errores/no-encontrado')

  if (accion && metodo === 'POST') {
    p.activo = accion === 'activar'
    p.version += 1
    p.autor = { id: usuario.id, nombre: usuario.nombre }
    return json(res, 200, vista(p))
  }

  if (metodo === 'DELETE' && !accion) {
    consumo.perfiles = consumo.perfiles.filter((x) => x !== p)
    res.statusCode = 204
    return void res.end()
  }

  if (metodo !== 'PATCH' || accion) return problema(res, 404, '/errores/no-encontrado')
  const ifMatch = req.headers['if-match']
  if (!ifMatch || ifMatch === '*') return problema(res, 428, '/errores/falta-version')

  // Cuenta «insumos-defectos»: el pañal choca una vez (412), los apósitos se dejan de seguir
  // mientras se cambian (409) y los guantes responden 500.
  if (usuario.modo === 'insumos-defectos') {
    if (p.nombre_libre.startsWith('Pañal') && !conflictosHechos.has(p.id)) {
      conflictosHechos.add(p.id)
      p.stock_unidades = 18
      p.stock_medido_en = hoy()
      p.version += 1
      p.autor = RODRIGO_CONSUMO
    } else if (p.nombre_libre.startsWith('Apósitos') && p.activo) {
      p.activo = false
      p.version += 1
      p.autor = RODRIGO_CONSUMO
    } else if (p.nombre_libre.startsWith('Guantes')) return problema(res, 500, '/errores/error-interno')
  }

  if (ifMatch !== `"v${p.version}"`) {
    res.setHeader('ETag', `"v${p.version}"`)
    return problema(res, 412, '/errores/version-desactualizada', { actual: vista(p) })
  }
  if (!p.activo) return problema(res, 409, '/errores/perfil-inactivo')
  const b = cuerpo ?? {}
  const e = errores(b, true)
  if (e.length) return problema(res, 422, '/errores/validacion', { errores: e })
  const nuevo = { ...p }
  if ('nombre_libre' in b) nuevo.nombre_libre = String(b.nombre_libre).trim()
  for (const k of ['tasa_unidades', 'tasa_dias', 'dias_aviso'] as const) if (entero(b[k], ...RANGOS[k])) nuevo[k] = b[k] as number
  if ('unidades_por_envase' in b) nuevo.unidades_por_envase = b.unidades_por_envase as number | null
  // Con stock nuevo se re-ancla la fecha a hoy (contrato).
  if (entero(b.stock_unidades, 0, 100_000)) {
    nuevo.stock_unidades = b.stock_unidades as number
    nuevo.stock_medido_en = hoy()
  }
  if (cobertura(nuevo) > MAX_COBERTURA) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'stock_unidades', mensaje: 'MENSAJE DEL DOBLE', tipo: 'cobertura_maxima' }] })
  Object.assign(p, nuevo, { version: p.version + 1, autor: { id: usuario.id, nombre: usuario.nombre } })
  res.setHeader('ETag', `"v${p.version}"`)
  return json(res, 200, vista(p))
}

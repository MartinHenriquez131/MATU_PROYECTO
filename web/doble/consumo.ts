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
}

export interface ConsumoDoble {
  autorizacion: 'no' | 'vigente' | 'vencida'
  perfiles: PerfilDoble[]
}

type Responder = {
  json: (res: ServerResponse, status: number, cuerpo: unknown) => void
  problema: (res: ServerResponse, status: number, tipo: string, extra?: Record<string, unknown>) => void
}

/** Página corta a propósito: la primera página trae `siguiente_cursor` (especificación 8). */
const PAGINA = 6
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

/** La lista de la especificación 8: 6, 1 y 0 días, −2, 60 caracteres sin espacios, por sobre, cada 2 días y dos sin seguir. */
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
    etag: `"v${p.version}"`,
  }
}

const orden = (a: PerfilDoble, b: PerfilDoble) => Number(b.activo) - Number(a.activo) || vista(a).fecha_quiebre_estimada.localeCompare(vista(b).fecha_quiebre_estimada)

const entero = (v: unknown, min: number, max: number) => typeof v === 'number' && Number.isInteger(v) && v >= min && v <= max

const CAMPOS_EDICION = ['nombre_libre', 'tasa_unidades', 'tasa_dias', 'stock_unidades', 'dias_aviso']
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
  if (!parcial && b.unidad !== undefined && b.unidad !== null && !['unidad', 'sobre', 'ml', 'g'].includes(String(b.unidad))) add('unidad', 'enum')
  if (parcial && !Object.keys(b).length) add('cuerpo', 'cuerpo_vacio')
  return e
}

const conflictosHechos = new Set<string>()

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
  if (!m) return problema(res, 404, '/errores/no-encontrado')
  const [, recurso, perfilId, accion] = m

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

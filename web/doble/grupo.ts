// Doble de MATU-42 (invitar y quiénes forman el grupo): `GET`, `PATCH` y `DELETE …/miembros`,
// `POST …/salida`, `GET`, `POST` y `DELETE …/invitaciones` y las tres rutas de la persona invitada
// (docs/api/openapi.json, decisiones 290 a 331). Solo el servidor de desarrollo: no entra al build.
// Datos sintéticos. Los modos de cuenta empiezan con «miembros-» (cuentas.ts). El código de las
// invitaciones de ejemplo es siempre 4729; el de una invitación creada sale en «Invitación lista».
import { randomBytes, randomInt, randomUUID } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { CODIGO_INVITACION_DE_EJEMPLO } from './cuentas'

export type Rol = 'admin' | 'cuidador' | 'pagador' | 'observador'

type Responder = {
  json: (res: ServerResponse, status: number, cuerpo: unknown) => void
  problema: (res: ServerResponse, status: number, tipo: string, extra?: Record<string, unknown>) => void
}

/** Lo que este módulo necesita de un grupo del doble de la familia. */
export interface GrupoConMiembros {
  id: string
  nombre: string
  rol: Rol
  puede_ver_plan: boolean
  personas: { nombre_pila: string }[]
  miembros?: MiembroDoble[]
  invitaciones?: InvitacionDoble[]
}
interface UsuarioConGrupos<G extends GrupoConMiembros> {
  nombre: string
  modo?: string
  grupos: G[]
}

/** Un miembro activo (decisión 302). `enlaces` = los accesos de relevo vigentes que compartió. */
export interface MiembroDoble {
  id: string
  nombre: string
  rol: Rol
  puede_ver_plan: boolean
  unido_en: string
  version: number
  enlaces: number
  eresTu: boolean
}
export interface InvitacionDoble {
  id: string
  token: string
  rol: Rol
  estado: 'pendiente' | 'bloqueada'
  creada_en: string
  expira_en: string
  por: { nombre: string | null; eresTu: boolean }
  /** Anular responde 409 `invitacion-cerrada` con este estado (P8). */
  cerrada?: 'usada' | 'vencida'
}

const DIA = 24 * 60
const hace = (min: number) => new Date(Date.now() - min * 60_000).toISOString()
const en = (min: number) => new Date(Date.now() + min * 60_000).toISOString()
const ROLES: Rol[] = ['admin', 'cuidador', 'pagador', 'observador']
const editaFicha = (r: Rol) => r === 'admin' || r === 'cuidador'
const conflictos = new Set<string>()

/** Un miembro de ejemplo, unido hace `dias` días. */
export function miembro(nombre: string, rol: Rol, dias: number, extra: Partial<MiembroDoble> = {}): MiembroDoble {
  return { id: randomUUID(), nombre, rol, puede_ver_plan: false, unido_en: hace(dias * DIA), version: 1, enlaces: 0, eresTu: false, ...extra }
}

/** Una invitación sin usar de ejemplo. Su token no abre nada: es solo la fila de la lista. */
export function invitacionPendiente(rol: Rol, por: InvitacionDoble['por'], extra: Partial<InvitacionDoble> = {}): InvitacionDoble {
  return { id: randomUUID(), token: `fila-${randomUUID()}`, rol, estado: 'pendiente', creada_en: hace(2 * DIA), expira_en: en(5 * DIA + 90), por, ...extra }
}

/**
 * Las cuentas de antes de MATU-42 no traen miembros: se arman al pedirlos, con la cuenta (tú) y,
 * según su nombre, Carmen que administra, Rodrigo que paga y Rosa que cuida.
 */
function miembrosDe(u: UsuarioConGrupos<GrupoConMiembros>, g: GrupoConMiembros): MiembroDoble[] {
  if (g.miembros) return g.miembros
  const yo = miembro(u.nombre, g.rol, 10, { eresTu: true, puede_ver_plan: g.puede_ver_plan, enlaces: editaFicha(g.rol) ? 1 : 0 })
  const otros = [miembro('Carmen Soto', 'admin', 12, { enlaces: 2 }), miembro('Rodrigo Soto', 'pagador', 8), miembro('Rosa Pérez', 'cuidador', 4, { enlaces: 1 })].filter(
    (m) => m.nombre.split(' ')[0] !== u.nombre,
  )
  if (!otros.some((m) => m.rol === 'admin') && g.rol !== 'admin') otros.unshift(miembro('Marta Soto', 'admin', 14))
  g.miembros = [yo, ...otros].sort((a, b) => a.unido_en.localeCompare(b.unido_en))
  return g.miembros
}

const etagDe = (m: MiembroDoble) => `"v${m.version}"`
function vistaMiembro(m: MiembroDoble, rolPropio: Rol) {
  return {
    id: m.id,
    nombre: m.nombre,
    rol: m.rol,
    puede_ver_plan: m.rol === 'pagador' ? m.puede_ver_plan : null,
    unido_en: m.unido_en,
    eres_tu: m.eresTu,
    etag: etagDe(m),
    // Decisión 302: quien administra los ve en todas las filas, y cada quien en la suya.
    enlaces_vigentes: rolPropio === 'admin' || m.eresTu ? m.enlaces : null,
  }
}
const vistaInvitacion = (i: InvitacionDoble) => ({
  id: i.id,
  rol: i.rol,
  estado: i.estado,
  creada_en: i.creada_en,
  expira_en: i.expira_en,
  invitada_por: { nombre: i.por.nombre, autor_activo: i.por.nombre !== null, eres_tu: i.por.eresTu },
})

/** El rol propio cambia: el grupo (lo que dice `GET /v1/grupos`) y la fila. */
function fijarRolPropio(g: GrupoConMiembros, rol: Rol, puedeVer = false) {
  g.rol = rol
  g.puede_ver_plan = rol === 'pagador' && puedeVer
  const yo = g.miembros?.find((m) => m.eresTu)
  if (yo) Object.assign(yo, { rol, puede_ver_plan: g.puede_ver_plan, version: yo.version + 1 })
}

// ---------------------------------------------------------------- la persona invitada

/** Las invitaciones del doble por token: las de ejemplo y las que crea quien administra. */
interface InvitacionPorToken {
  rol: Rol
  nombre_pila_invita: string
  grupo: string
  personas: string[]
  expira_en: string
  codigo: string
  intentos: number
  estado: 'pendiente' | 'usada' | 'vencida' | 'anulada' | 'bloqueada'
  /** Las de ejemplo no se gastan al aceptarlas: vuelven a servir. */
  ejemplo: boolean
  /** Fuerza una respuesta: 429, 500 o el 409 `ya-eres-parte` al aceptar. */
  forzar?: 'espera' | 'error' | 'ya-eres-parte'
}
const porToken = new Map<string, InvitacionPorToken>()

function deEjemplo(token: string, extra: Partial<InvitacionPorToken> = {}) {
  porToken.set(token, {
    rol: 'cuidador',
    nombre_pila_invita: 'Carmen',
    grupo: 'Familia Soto',
    personas: ['María'],
    expira_en: en(6 * DIA + 21 * 60),
    codigo: CODIGO_INVITACION_DE_EJEMPLO,
    intentos: 0,
    estado: 'pendiente',
    ejemplo: true,
    ...extra,
  })
}

deEjemplo('inv-cuidar')
deEjemplo('inv-administrar', { rol: 'admin' })
deEjemplo('inv-pagar', { rol: 'pagador', personas: ['María', 'Pedro'] })
deEjemplo('inv-informarte', { rol: 'observador', personas: ['María', 'Pedro', 'Elena'] })
deEjemplo('inv-sin-personas', { personas: [] })
// Con 3 fallidos, un código malo deja «Te queda 1 intento» y el siguiente la bloquea.
deEjemplo('inv-queda-1', { intentos: 3 })
deEjemplo('inv-usada', { estado: 'usada' })
deEjemplo('inv-vencida', { estado: 'vencida', expira_en: hace(DIA) })
deEjemplo('inv-anulada', { estado: 'anulada' })
deEjemplo('inv-bloqueada', { estado: 'bloqueada', intentos: 5 })
deEjemplo('inv-espera', { forzar: 'espera' })
deEjemplo('inv-error', { forzar: 'error' })
deEjemplo('inv-ya-eres-parte', { forzar: 'ya-eres-parte' })
deEjemplo('inv-largos', {
  nombre_pila_invita: 'Maximiliana',
  grupo: 'Familia Valenzuela Etchegaray de los Ángeles',
  personas: ['Bernardita', 'Constanza', 'Maximiliana'],
  rol: 'admin',
})

/**
 * Presentación, verificación y aceptación (decisión 299), en el orden de la API: cuerpo, 410, 423,
 * código, `ya-eres-parte`. Al aceptar, `unir` crea el grupo para la cuenta y devuelve sus ids.
 */
export function atenderInvitacionPublica(
  paso: 'presentacion' | 'verificacion' | 'aceptacion',
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  { json, problema }: Responder,
  cuenta: { grupos: { id: string }[] } | null,
  unir: (i: { grupo: string; rol: Rol; personas: string[]; nombre_pila_invita: string }) => { grupo_id: string; membresia_id: string },
) {
  res.setHeader('Cache-Control', 'no-store')
  const token = typeof cuerpo?.token === 'string' ? cuerpo.token : ''
  if (!token || token.length > 128) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'token', mensaje: 'MENSAJE DEL DOBLE', tipo: 'value_error' }] })
  const codigo = cuerpo?.codigo
  if (paso !== 'presentacion' && (typeof codigo !== 'string' || !/^[0-9]{4}$/.test(codigo)))
    return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'codigo', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_pattern_mismatch' }] })
  const i = porToken.get(token)
  if (i?.forzar === 'espera') return res.setHeader('Retry-After', '120'), problema(res, 429, '/errores/demasiadas-peticiones')
  if (i?.forzar === 'error') return problema(res, 500, '/errores/error-interno')
  if (!i || i.estado === 'anulada') return problema(res, 410, '/errores/invitacion-no-disponible')
  if (i.estado === 'usada') return problema(res, 410, '/errores/invitacion-usada')
  if (i.estado === 'vencida' || new Date(i.expira_en).getTime() <= Date.now()) return problema(res, 410, '/errores/invitacion-vencida')
  if (i.estado === 'bloqueada') return problema(res, 423, '/errores/invitacion-bloqueada', { nombre_pila_invita: i.nombre_pila_invita })
  if (paso === 'presentacion') return json(res, 200, { nombre_pila_invita: i.nombre_pila_invita, rol: i.rol, expira_en: i.expira_en })
  if (codigo !== i.codigo) {
    i.intentos += 1
    if (i.intentos >= 5) {
      i.estado = 'bloqueada'
      return problema(res, 423, '/errores/invitacion-bloqueada', { nombre_pila_invita: i.nombre_pila_invita })
    }
    return problema(res, 422, '/errores/codigo-incorrecto', { intentos_restantes: 5 - i.intentos })
  }
  i.intentos = 0
  if (paso === 'verificacion') return json(res, 200, { nombre_pila_invita: i.nombre_pila_invita, grupo: i.grupo, personas: i.personas, rol: i.rol, expira_en: i.expira_en })
  if (!cuenta) return problema(res, 401, '/errores/no-autenticado')
  if (i.forzar === 'ya-eres-parte') return problema(res, 409, '/errores/ya-eres-parte', { grupo_id: cuenta.grupos[0]?.id ?? randomUUID() })
  const unido = unir(i)
  if (!i.ejemplo) i.estado = 'usada'
  return json(res, 201, { ...unido, grupo: i.grupo, rol: i.rol, puede_ver_plan: false })
}

// ---------------------------------------------------------------- el grupo

export function atenderGrupo<G extends GrupoConMiembros>(
  req: IncomingMessage,
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  { json, problema }: Responder,
  u: UsuarioConGrupos<G>,
  g: G,
  que: 'miembros' | 'invitaciones' | 'salida',
  id: string | null,
) {
  const metodo = req.method ?? 'GET'
  res.setHeader('Cache-Control', 'no-store')
  const miembros = miembrosDe(u, g)
  const yo = miembros.find((m) => m.eresTu)!
  const admins = () => (g.miembros ?? []).filter((m) => m.rol === 'admin').length
  const modo = u.modo ?? ''
  const noEncontrado = () => problema(res, 404, '/errores/no-encontrado')
  /** «miembros-ya-no-admin»: la primera gestión responde 404 porque otra persona me bajó a cuidador. */
  const yaNoAdmin = () => {
    if (modo !== 'miembros-ya-no-admin' || g.rol !== 'admin') return false
    fijarRolPropio(g, 'cuidador')
    noEncontrado()
    return true
  }
  const fuera = () => {
    u.grupos = u.grupos.filter((x) => x.id !== g.id)
  }

  if (que === 'salida') {
    if (metodo !== 'POST' || id) return noEncontrado()
    if (modo === 'miembros-falla') return problema(res, 500, '/errores/error-interno')
    if (miembros.length === 1) return problema(res, 409, '/errores/unica-persona')
    if (modo === 'miembros-ultimo-admin' || (yo.rol === 'admin' && admins() === 1)) return problema(res, 409, '/errores/ultimo-admin')
    fuera()
    return json(res, 200, { enlaces_cortados: yo.enlaces })
  }

  if (que === 'miembros' && !id) {
    if (metodo !== 'GET') return noEncontrado()
    if (modo === 'miembros-lista-falla') return problema(res, 500, '/errores/error-interno')
    return json(res, 200, { miembros: miembros.map((m) => vistaMiembro(m, g.rol)) })
  }

  if (que === 'miembros' && id) {
    if (g.rol !== 'admin') return noEncontrado()
    if (yaNoAdmin()) return
    const m = miembros.find((x) => x.id === id)
    if (!m) return noEncontrado()
    if (metodo === 'DELETE') {
      if (modo === 'miembros-falla') return problema(res, 500, '/errores/error-interno')
      if (m.eresTu && miembros.length === 1) return problema(res, 409, '/errores/unica-persona')
      if (modo === 'miembros-ultimo-admin' || (m.rol === 'admin' && admins() === 1)) return problema(res, 409, '/errores/ultimo-admin')
      g.miembros = miembros.filter((x) => x.id !== m.id)
      if (m.eresTu) fuera()
      return json(res, 200, { enlaces_cortados: m.enlaces })
    }
    if (metodo !== 'PATCH') return noEncontrado()
    // Orden del contrato: 428, 422, 412, 409 (decisión 303).
    const ifMatch = String(req.headers['if-match'] ?? '').trim()
    if (!ifMatch || ifMatch === '*') return problema(res, 428, '/errores/falta-version')
    const b = cuerpo ?? {}
    const rol = b.rol
    const puede = b.puede_ver_plan
    const malo = (campo: string, tipo = 'value_error') => problema(res, 422, '/errores/validacion', { errores: [{ campo, mensaje: 'MENSAJE DEL DOBLE', tipo }] })
    if (rol === undefined && puede === undefined) return malo('rol')
    if (rol !== undefined && !ROLES.includes(rol as Rol)) return malo('rol')
    if (puede !== undefined && typeof puede !== 'boolean') return malo('puede_ver_plan')
    const rolNuevo = (rol as Rol | undefined) ?? m.rol
    if (puede !== undefined && rolNuevo !== 'pagador') return malo('puede_ver_plan', 'permiso_solo_pagador')
    // «miembros-conflicto»: la primera vez por persona, otra persona que administra la cambió antes.
    if (modo === 'miembros-conflicto' && !conflictos.has(m.id)) {
      conflictos.add(m.id)
      if (m.rol === 'pagador') m.puede_ver_plan = !m.puede_ver_plan
      else m.rol = m.rol === 'observador' ? 'pagador' : 'observador'
      m.version += 1
    }
    if (ifMatch !== etagDe(m)) return problema(res, 412, '/errores/version-desactualizada', { actual: vistaMiembro(m, g.rol) })
    if (m.rol === 'admin' && rolNuevo !== 'admin' && (modo === 'miembros-ultimo-admin' || admins() === 1)) return problema(res, 409, '/errores/ultimo-admin')
    if (modo === 'miembros-falla') return problema(res, 500, '/errores/error-interno')
    // Decisión 305: se corta al dejar de compartir (de admin o cuidador a pagador u observador).
    const cortados = editaFicha(m.rol) && !editaFicha(rolNuevo) ? m.enlaces : 0
    m.enlaces -= cortados
    const antes = m.rol
    m.rol = rolNuevo
    m.puede_ver_plan = rolNuevo !== 'pagador' ? false : typeof puede === 'boolean' ? puede : antes === 'pagador' ? m.puede_ver_plan : false
    m.version += 1
    if (m.eresTu) fijarRolPropio(g, m.rol, m.puede_ver_plan)
    res.setHeader('ETag', etagDe(m))
    return json(res, 200, { miembro: vistaMiembro(m, g.rol), enlaces_cortados: cortados })
  }

  // Las invitaciones: solo quien administra (C10).
  if (g.rol !== 'admin') return noEncontrado()
  const vigentes = () => (g.invitaciones ?? []).filter((i) => new Date(i.expira_en).getTime() > Date.now())
  if (!id && metodo === 'GET') return json(res, 200, { invitaciones: vigentes().sort((a, b) => b.creada_en.localeCompare(a.creada_en)).map(vistaInvitacion) })
  if (!id && metodo === 'POST') {
    if (yaNoAdmin()) return
    if (modo === 'miembros-tope') return res.setHeader('Retry-After', '3600'), problema(res, 429, '/errores/tope-invitaciones')
    const rol = cuerpo?.rol
    if (!ROLES.includes(rol as Rol)) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'rol', mensaje: 'MENSAJE DEL DOBLE', tipo: 'enum' }] })
    if (modo === 'miembros-falla') return problema(res, 500, '/errores/error-interno')
    const token = randomBytes(32).toString('base64url')
    const codigo = String(randomInt(0, 10_000)).padStart(4, '0')
    const ahora = new Date().toISOString()
    const expira = en(7 * DIA)
    const pila = yo.nombre.split(' ')[0]
    const nueva: InvitacionDoble = { id: randomUUID(), token, rol: rol as Rol, estado: 'pendiente', creada_en: ahora, expira_en: expira, por: { nombre: pila, eresTu: true } }
    g.invitaciones = [nueva, ...(g.invitaciones ?? [])]
    porToken.set(token, { rol: rol as Rol, nombre_pila_invita: pila, grupo: g.nombre, personas: g.personas.map((p) => p.nombre_pila), expira_en: expira, codigo, intentos: 0, estado: 'pendiente', ejemplo: false })
    return json(res, 201, { id: nueva.id, rol: nueva.rol, url: `http://${req.headers.host ?? 'localhost'}/invitacion#${token}`, codigo, creada_en: ahora, expira_en: expira })
  }
  if (id && metodo === 'DELETE') {
    if (yaNoAdmin()) return
    if (modo === 'miembros-falla') return problema(res, 500, '/errores/error-interno')
    const i = (g.invitaciones ?? []).find((x) => x.id === id)
    g.invitaciones = (g.invitaciones ?? []).filter((x) => x.id !== id)
    if (i?.cerrada) return problema(res, 409, '/errores/invitacion-cerrada', { estado: i.cerrada })
    const t = i ? porToken.get(i.token) : undefined
    if (t && !t.ejemplo) t.estado = 'anulada'
    // Decisión 308: ya anulada (o que no está) también es 204.
    res.statusCode = 204
    return res.end()
  }
  return noEncontrado()
}

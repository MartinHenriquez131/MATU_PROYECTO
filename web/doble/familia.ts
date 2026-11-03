// Doble del contrato de la app de la familia (docs/api/openapi.json) para desarrollo: cuentas,
// entrada con la cookie del refresh, grupos, personas y la ficha con ETag, 412 y 428. Igual que el
// doble del relevo, responde por HTTP de verdad y no entra al build. Datos sintéticos: Carmen cuida
// a María, Rodrigo es su hijo; los teléfonos usan la serie 5555, que no se asigna.
import { randomUUID } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'

export const CONTRASENA_DE_EJEMPLO = 'contrasena-ejemplo'

type Rol = 'admin' | 'cuidador' | 'pagador' | 'observador'
type CampoApi = 'rutina' | 'manejo_situaciones' | 'red_apoyo'
interface Campo {
  texto: string | null
  version: number
  autor: { id: string; nombre: string } | null
  en: string | null
}
interface Persona {
  id: string
  nombre: string
  nombre_pila: string
  nivel_apoyo: string
  direccion: Record<string, unknown> | null
  calidad: string
  campos: Record<CampoApi, Campo>
}
interface Grupo {
  id: string
  nombre: string
  rol: Rol
  puede_ver_plan: boolean
  personas: Persona[]
}
interface Usuario {
  id: string
  nombre: string
  email: string
  contrasena: string
  grupos: Grupo[]
  /** Comportamiento especial de la cuenta de ejemplo. */
  modo?: string
}

export interface CuentaDeEjemplo {
  email: string
  que: string
}

// ---------------------------------------------------------------- datos sintéticos

const RODRIGO = { id: randomUUID(), nombre: 'Rodrigo' }
const hace = (min: number) => new Date(Date.now() - min * 60_000).toISOString()
const vacio = (): Campo => ({ texto: null, version: 0, autor: null, en: null })
const escrito = (texto: string, autor: { id: string; nombre: string }, min = 42): Campo => ({ texto, version: 1, autor, en: hace(min) })

const SU_DIA = '08:00 Despierta. Le gusta que abran la cortina primero.\n08:30 Té con leche tibio, nunca caliente.\n13:00 Almuerza mejor si alguien la acompaña.'
const SI_SE_ALTERA = 'Bajar las persianas y poner la radio bajito. No hablarle fuerte.'
const A_QUIEN = 'Carmen, su hija: +56 9 5555 0141\nRodrigo, su hijo: +56 9 5555 0102'

function persona(nombre: string, pila: string, campos: Partial<Record<CampoApi, Campo>> = {}, calidad = 'titular'): Persona {
  return {
    id: randomUUID(),
    nombre,
    nombre_pila: pila,
    nivel_apoyo: 'apoyo_parcial',
    direccion: null,
    calidad,
    campos: { rutina: vacio(), manejo_situaciones: vacio(), red_apoyo: vacio(), ...campos },
  }
}

const usuarios = new Map<string, Usuario>()

function cuenta(email: string, nombre: string, grupos: Grupo[], modo?: string) {
  const u: Usuario = { id: randomUUID(), nombre, email, contrasena: CONTRASENA_DE_EJEMPLO, grupos, modo }
  usuarios.set(email, u)
  return u
}
const grupo = (nombre: string, rol: Rol, personas: Persona[], puede_ver_plan = false): Grupo => ({ id: randomUUID(), nombre, rol, puede_ver_plan, personas })

function sembrar() {
  const carmen = cuenta('carmen@ejemplo.cl', 'Carmen', [])
  const yo = { id: carmen.id, nombre: 'Carmen' }
  carmen.grupos.push(grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })]))
  cuenta('completa@ejemplo.cl', 'Carmen', [
    grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo), manejo_situaciones: escrito(SI_SE_ALTERA, RODRIGO, 5), red_apoyo: escrito(A_QUIEN, yo, 3) })]),
  ])
  cuenta('vacia@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])])
  cuenta('dos-grupos@ejemplo.cl', 'Carmen', [
    grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }), persona('Juan Soto', 'Juan')]),
    grupo('Familia Pérez', 'cuidador', [persona('Elena Pérez', 'Elena')]),
  ])
  cuenta('sin-persona@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [])])
  cuenta('sin-persona-pagador@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'pagador', [])])
  cuenta('pagador@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'pagador', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })])])
  cuenta('pagador-ve@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'pagador', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })], true)])
  cuenta('observador@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'observador', [persona('María Soto', 'María')])])
  cuenta('sin-autorizacion@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'sin-consentimiento')
  cuenta('renovar-autorizacion@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', {}, 'cuidador_de_hecho')])], 'revision-vencida')
  cuenta('revision-al-guardar@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'revision-al-guardar')
  cuenta('conflicto@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })])], 'conflicto')
  cuenta('defectos@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'defectos')
  cuenta('vence@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'vence')
  cuenta('lento@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })])], 'lento')
  cuenta(
    'largos@ejemplo.cl',
    'Bernardita',
    [grupo('Familia Valenzuela Etchegaray', 'admin', [persona('Maximiliana de los Ángeles Valenzuela Etchegaray', 'Maximiliana', { manejo_situaciones: escrito('Extraordinariamente tranquila cuando le hablan de su pueblo. '.repeat(8).slice(0, 480), yo) })])],
  )
}
sembrar()

export const CUENTAS: CuentaDeEjemplo[] = [
  { email: 'carmen@ejemplo.cl', que: 'Admin con María y «Su día» escrito (1 de 3). El correo ya tiene cuenta: úsalo en Crear cuenta para ver el 409' },
  { email: 'vacia@ejemplo.cl', que: 'Admin con la ficha en 0 de 3' },
  { email: 'completa@ejemplo.cl', que: 'Ficha en 3 de 3 (un campo lo escribió Rodrigo)' },
  { email: 'dos-grupos@ejemplo.cl', que: 'Dos grupos y dos personas: selector de persona' },
  { email: 'sin-persona@ejemplo.cl', que: 'Admin con grupo y sin persona: va a «¿A quién cuidas?»' },
  { email: 'sin-persona-pagador@ejemplo.cl', que: 'Pagador con grupo y sin persona: «Todavía no hay nadie registrado…»' },
  { email: 'pagador@ejemplo.cl', que: 'Pagador sin puede_ver_plan: sin «Ficha» en la navegación; /ficha muestra «No tienes acceso»' },
  { email: 'pagador-ve@ejemplo.cl', que: 'Pagador con puede_ver_plan: ve la ficha; al guardar, 404 y «No tienes acceso»' },
  { email: 'observador@ejemplo.cl', que: 'Observador: solo Insumos; /ficha a mano no pide nada' },
  { email: 'sin-autorizacion@ejemplo.cl', que: 'La ficha responde 403 sin-consentimiento (lenguaje 6.4)' },
  { email: 'renovar-autorizacion@ejemplo.cl', que: 'La ficha responde 403 revision-vencida (lenguaje 6.4b)' },
  { email: 'revision-al-guardar@ejemplo.cl', que: 'La ficha abre y al guardar responde 403 revision-vencida: lo escrito se muestra para copiar' },
  { email: 'conflicto@ejemplo.cl', que: 'Cada primer guardado de un campo responde 412: Rodrigo lo guardó mientras escribías' },
  { email: 'defectos@ejemplo.cl', que: 'Guardar «Su día» 428, «Si se altera» 422 string_too_long, «A quién llamar» 500' },
  { email: 'vence@ejemplo.cl', que: 'El token dura 20 s y la entrada 40 s: escribe y guarda pasado ese tiempo para ver la entrada vencida con texto sin guardar' },
  { email: 'lento@ejemplo.cl', que: 'Cada respuesta tarda 2 s: «Cargando…», «Guardando…»' },
  { email: 'largos@ejemplo.cl', que: 'Nombres largos y un campo de 480 caracteres, para revisar el texto al 200%' },
  { email: 'espera@ejemplo.cl', que: 'Entrar responde 429 con Retry-After: 90 («Espera 2 minutos»)' },
  { email: 'espera-1@ejemplo.cl', que: 'Entrar responde 429 con Retry-After: 30 («Espera 1 minuto»)' },
  { email: 'caido@ejemplo.cl', que: 'Entrar responde 503' },
]

// ---------------------------------------------------------------- sesiones

const COOKIE = 'matu-refresh-doble'
interface Refresh {
  email: string
  vence: number
}
const refrescos = new Map<string, Refresh>()
const tokens = new Map<string, { email: string; vence: number }>()

function emitirToken(u: Usuario) {
  const t = randomUUID()
  tokens.set(t, { email: u.email, vence: Date.now() + (u.modo === 'vence' ? 20_000 : 15 * 60_000) })
  return { access_token: t, token_type: 'bearer', expira_en: u.modo === 'vence' ? 20 : 900 }
}
function emitirRefresh(res: ServerResponse, u: Usuario, vence?: number) {
  const id = randomUUID()
  refrescos.set(id, { email: u.email, vence: vence ?? Date.now() + (u.modo === 'vence' ? 40_000 : 30 * 86_400_000) })
  res.setHeader('Set-Cookie', `${COOKIE}=${id}; Max-Age=2592000; Path=/v1/sesiones; HttpOnly; SameSite=Strict`)
}
const borrarRefresh = (res: ServerResponse) => res.setHeader('Set-Cookie', `${COOKIE}=; Max-Age=0; Path=/v1/sesiones; HttpOnly; SameSite=Strict`)
const refreshDe = (req: IncomingMessage) => new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]+)`).exec(req.headers.cookie ?? '')?.[1]

function usuarioDe(req: IncomingMessage): Usuario | null {
  const t = /^Bearer (.+)$/.exec(String(req.headers.authorization ?? ''))?.[1]
  const s = t ? tokens.get(t) : undefined
  if (!s || s.vence < Date.now()) return null
  return usuarios.get(s.email) ?? null
}

export const esLento = (req: IncomingMessage, cuerpo: Record<string, unknown> | null) =>
  usuarioDe(req)?.modo === 'lento' || cuerpo?.email === 'lento@ejemplo.cl'

// ---------------------------------------------------------------- respuestas

type Responder = {
  json: (res: ServerResponse, status: number, cuerpo: unknown) => void
  problema: (res: ServerResponse, status: number, tipo: string, extra?: Record<string, unknown>) => void
}

const vistaCampo = (c: Campo) => ({
  texto: c.texto,
  etag: c.version ? `"v${c.version}"` : null,
  actualizado_por: c.autor,
  actualizado_en: c.en,
})
const completitud = (p: Persona) => Math.round(((['rutina', 'manejo_situaciones', 'red_apoyo'] as CampoApi[]).filter((k) => p.campos[k].texto?.trim()).length * 100) / 3)

function vistaPersona(p: Persona, rol: Rol) {
  if (rol === 'observador') return { id: p.id, nombre: p.nombre }
  if (rol === 'pagador') return { id: p.id, nombre: p.nombre, direccion: p.direccion }
  return {
    id: p.id,
    nombre: p.nombre,
    nombre_pila: p.nombre_pila,
    nivel_apoyo: p.nivel_apoyo,
    direccion: p.direccion,
    consentimiento: { id: randomUUID(), calidad_otorgante: p.calidad, finalidad: 'plan_cuidado', version_politica: '0.9', otorgado_en: hace(60 * 24), revision_vence_en: null },
  }
}

const conflictosHechos = new Set<string>()

/** Atiende /v1 de la familia. `false` si la ruta no es suya. */
export async function atenderFamilia(req: IncomingMessage, res: ServerResponse, cuerpo: Record<string, unknown> | null, r: Responder): Promise<boolean> {
  const metodo = req.method ?? 'GET'
  const ruta = (req.url ?? '').split('?')[0]
  const { json, problema } = r

  if (metodo === 'POST' && ruta === '/v1/usuarios') {
    const nombre = cuerpo?.nombre
    const email = typeof cuerpo?.email === 'string' ? cuerpo.email.trim().toLowerCase() : ''
    const telefono = cuerpo?.telefono
    const contrasena = cuerpo?.contrasena
    const errores: { campo: string; mensaje: string; tipo: string }[] = []
    if (typeof nombre !== 'string' || !nombre.trim() || nombre.length > 100) errores.push({ campo: 'nombre', mensaje: 'MENSAJE DEL DOBLE', tipo: 'value_error' })
    if (!email.includes('@')) errores.push({ campo: 'email', mensaje: 'MENSAJE DEL DOBLE', tipo: 'value_error' })
    if (typeof telefono !== 'string' || !/^(\+?56 ?)?9( ?[0-9]){8}$/.test(telefono.trim())) errores.push({ campo: 'telefono', mensaje: 'MENSAJE DEL DOBLE', tipo: 'celular_invalido' })
    if (typeof contrasena !== 'string' || contrasena.length < 10 || contrasena.length > 128) errores.push({ campo: 'contrasena', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_too_short' })
    if (errores.length) return problema(res, 422, '/errores/validacion', { errores }), true
    if (usuarios.has(email)) return problema(res, 409, '/errores/email-registrado'), true
    const u = cuenta(email, String(nombre).trim(), [])
    u.contrasena = String(contrasena)
    return json(res, 201, { id: u.id, nombre: u.nombre, email: u.email }), true
  }

  if (metodo === 'POST' && ruta === '/v1/sesiones') {
    const email = typeof cuerpo?.email === 'string' ? cuerpo.email.trim().toLowerCase() : ''
    if (email === 'espera@ejemplo.cl') return res.setHeader('Retry-After', '90'), problema(res, 429, '/errores/demasiadas-peticiones'), true
    if (email === 'espera-1@ejemplo.cl') return res.setHeader('Retry-After', '30'), problema(res, 429, '/errores/demasiadas-peticiones'), true
    if (email === 'caido@ejemplo.cl') return problema(res, 503, '/errores/servicio-no-disponible'), true
    const u = usuarios.get(email)
    if (!u || u.contrasena !== cuerpo?.contrasena) return problema(res, 401, '/errores/credenciales-invalidas'), true
    emitirRefresh(res, u)
    return json(res, 200, emitirToken(u)), true
  }

  if (metodo === 'POST' && ruta === '/v1/sesiones/renovar') {
    if (req.headers['x-matu-cliente'] !== 'web') return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'X-MATU-Cliente', mensaje: 'MENSAJE DEL DOBLE', tipo: 'missing' }] }), true
    const id = refreshDe(req)
    const s = id ? refrescos.get(id) : undefined
    if (id) refrescos.delete(id) // rota: el anterior ya no sirve
    const u = s ? usuarios.get(s.email) : undefined
    if (!s || !u || s.vence < Date.now()) return borrarRefresh(res), problema(res, 401, '/errores/sesion-expirada'), true
    emitirRefresh(res, u, u.modo === 'vence' ? s.vence : undefined)
    return json(res, 200, emitirToken(u)), true
  }

  if (metodo === 'POST' && ruta === '/v1/sesiones/cerrar') {
    const id = refreshDe(req)
    if (id) refrescos.delete(id)
    borrarRefresh(res)
    res.statusCode = 204
    return res.end(), true
  }

  if (!ruta.startsWith('/v1/grupos') && !ruta.startsWith('/v1/personas-cuidadas')) return false

  const u = usuarioDe(req)
  if (!u) return problema(res, req.headers.authorization ? 401 : 401, req.headers.authorization ? '/errores/token-invalido' : '/errores/no-autenticado'), true

  if (ruta === '/v1/grupos' && metodo === 'GET') return json(res, 200, u.grupos.map(({ id, nombre, rol, puede_ver_plan }) => ({ id, nombre, rol, puede_ver_plan }))), true
  if (ruta === '/v1/grupos' && metodo === 'POST') {
    const nombre = cuerpo?.nombre
    if (typeof nombre !== 'string' || !nombre.trim()) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'nombre', mensaje: 'MENSAJE DEL DOBLE', tipo: 'value_error' }] }), true
    const g = grupo(nombre.trim(), 'admin', [])
    u.grupos.push(g)
    return json(res, 201, { id: g.id, nombre: g.nombre, rol: g.rol }), true
  }

  const g = u.grupos.find((x) => x.id === req.headers['x-grupo-id'])
  const mPersonas = /^\/v1\/grupos\/([^/]+)\/personas-cuidadas$/.exec(ruta)
  if (mPersonas) {
    if (!g || g.id !== decodeURIComponent(mPersonas[1])) return problema(res, 404, '/errores/no-encontrado'), true
    if (metodo === 'GET') return json(res, 200, g.personas.map((p) => vistaPersona(p, g.rol))), true
    if (g.rol !== 'admin' && g.rol !== 'cuidador') return problema(res, 404, '/errores/no-encontrado'), true
    const b = cuerpo ?? {}
    if (typeof b.nombre !== 'string' || !b.nombre.trim() || typeof b.nombre_pila !== 'string' || !b.nombre_pila.trim())
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'nombre', mensaje: 'MENSAJE DEL DOBLE', tipo: 'value_error' }] }), true
    const p = persona(b.nombre.trim(), b.nombre_pila.trim(), {}, String(b.calidad_otorgante))
    p.nivel_apoyo = String(b.nivel_apoyo)
    p.direccion = b.direccion ? { etiqueta: 'Casa', region: 'Metropolitana', referencia: null, depto: null, ...(b.direccion as object) } : null
    g.personas.push(p)
    return json(res, 201, { ...vistaPersona(p, 'admin'), aviso: null }), true
  }

  const mFicha = /^\/v1\/personas-cuidadas\/([^/]+)\/plan\/ficha(?:\/([a-z_]+))?$/.exec(ruta)
  if (!mFicha) return problema(res, 404, '/errores/no-encontrado'), true
  const p = g?.personas.find((x) => x.id === decodeURIComponent(mFicha[1]))
  if (!g || !p) return problema(res, 404, '/errores/no-encontrado'), true
  const puedeLeer = g.rol === 'admin' || g.rol === 'cuidador' || (g.rol === 'pagador' && g.puede_ver_plan)
  if (!puedeLeer) return problema(res, 404, '/errores/no-encontrado'), true
  if (u.modo === 'sin-consentimiento') return problema(res, 403, '/errores/sin-consentimiento'), true
  if (u.modo === 'revision-vencida') return problema(res, 403, '/errores/revision-vencida'), true

  if (metodo === 'GET' && !mFicha[2]) {
    res.setHeader('Cache-Control', 'no-store')
    const ultima = Object.values(p.campos).map((c) => c.en).filter(Boolean).sort().pop() ?? null
    return (
      json(res, 200, {
        persona_id: p.id,
        completitud: completitud(p),
        actualizado_en: ultima,
        campos: { rutina: vistaCampo(p.campos.rutina), manejo_situaciones: vistaCampo(p.campos.manejo_situaciones), red_apoyo: vistaCampo(p.campos.red_apoyo) },
      }),
      true
    )
  }

  if (metodo !== 'PUT' || !mFicha[2]) return problema(res, 404, '/errores/no-encontrado'), true
  const nombreCampo = mFicha[2] as CampoApi
  if (!['rutina', 'manejo_situaciones', 'red_apoyo'].includes(nombreCampo)) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'campo', mensaje: 'MENSAJE DEL DOBLE', tipo: 'enum' }] }), true
  if (g.rol !== 'admin' && g.rol !== 'cuidador') return problema(res, 404, '/errores/no-encontrado'), true
  if (u.modo === 'revision-al-guardar') return problema(res, 403, '/errores/revision-vencida'), true
  if (u.modo === 'defectos') {
    if (nombreCampo === 'rutina') return problema(res, 428, '/errores/falta-version'), true
    if (nombreCampo === 'manejo_situaciones')
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'texto', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_too_long' }] }), true
    return problema(res, 500, '/errores/error-interno'), true
  }
  const texto = cuerpo?.texto
  if (typeof texto !== 'string' || texto.length > 500) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'texto', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_too_long' }] }), true
  const ifMatch = req.headers['if-match']
  const ifNone = req.headers['if-none-match']
  if (ifMatch && ifNone) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'If-Match', mensaje: 'MENSAJE DEL DOBLE', tipo: 'precondicion_doble' }] }), true
  if ((!ifMatch && !ifNone) || ifMatch === '*' || ifMatch === '') return problema(res, 428, '/errores/falta-version'), true
  const c = p.campos[nombreCampo]

  // Cuenta "conflicto": Rodrigo guarda el campo justo antes del primer guardado.
  const clave = `${p.id}-${nombreCampo}`
  if (u.modo === 'conflicto' && !conflictosHechos.has(clave)) {
    conflictosHechos.add(clave)
    p.campos[nombreCampo] = { texto: 'Bajar las persianas. Si sigue inquieta, llamar a la nieta para que le hable un rato.', version: c.version + 1, autor: RODRIGO, en: hace(1) }
  }
  const actual = p.campos[nombreCampo]
  const etag = actual.version ? `"v${actual.version}"` : null
  const choca = ifNone ? ifNone !== '*' || actual.version > 0 : ifMatch !== etag
  if (ifNone && ifNone !== '*') return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'If-None-Match', mensaje: 'MENSAJE DEL DOBLE', tipo: 'precondicion_invalida' }] }), true
  if (ifNone && !texto.trim()) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'texto', mensaje: 'MENSAJE DEL DOBLE', tipo: 'vacio_sin_crear' }] }), true
  if (choca) {
    if (etag) res.setHeader('ETag', etag)
    res.setHeader('Cache-Control', 'no-store')
    return problema(res, 412, '/errores/version-desactualizada', { campo: nombreCampo, actual: vistaCampo(actual) }), true
  }
  const nuevo: Campo = { texto, version: actual.version + 1, autor: { id: u.id, nombre: u.nombre }, en: new Date().toISOString() }
  p.campos[nombreCampo] = nuevo
  res.setHeader('ETag', `"v${nuevo.version}"`)
  res.setHeader('Cache-Control', 'no-store')
  return (
    json(res, actual.version ? 200 : 201, {
      campo: nombreCampo,
      texto: nuevo.texto,
      etag: `"v${nuevo.version}"`,
      actualizado_por: nuevo.autor,
      actualizado_en: nuevo.en,
      completitud: completitud(p),
    }),
    true
  )
}

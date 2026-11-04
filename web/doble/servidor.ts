// Doble del contrato del relevo (docs/api/propuestos/relevo.openapi.yaml) para desarrollo, mientras
// no exista el backend de MATU-19. Es un middleware del servidor de Vite: responde
// POST /v1/relevo/presentacion, POST /v1/relevo/canje y GET /v1/relevo/ficha por HTTP de verdad,
// con la cookie HttpOnly, los códigos, el RFC 7807 y las cabeceras del contrato. El cliente no sabe
// que habla con un doble, y nada de esta carpeta entra al build de producción.
import { randomUUID } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'
import { ESCENARIOS, PIN_DE_EJEMPLO } from './escenarios'
import { atenderFamilia, esLento } from './familia'

const COOKIE = 'matu-relevo-doble'
const MAX_INTENTOS = 5
const TOKENS = new Set(ESCENARIOS.map((e) => e.token))

interface Sesion {
  token: string
  lecturas: number
  abiertaEn: number
}

// Estado en memoria: se pierde al reiniciar `npm run dev` (así se vuelve a cero).
const sesiones = new Map<string, Sesion>()
const fallidos = new Map<string, number>()
const presentacionesFallidas = new Map<string, number>()
const lecturasFallidas = new Map<string, number>()

type Campos = Partial<Record<'rutina' | 'manejo_situaciones' | 'red_apoyo', { texto: string | null }>>

const TRES_CAMPOS: Campos = {
  rutina: {
    texto:
      '8:00 Se levanta y toma desayuno en la cocina, con la radio prendida.\n10:30 Camina un rato por el patio, del brazo.\n13:00 Almuerza.\n15:00 Siesta hasta las 16:30.\n20:00 Cena liviana y ve las noticias.',
  },
  manejo_situaciones: {
    texto:
      'Le hace bien que le hablen despacio y le recuerden dónde está.\nSi se pone inquieta en la tarde, ofrecerle una agüita de hierbas y poner la música que le gusta.',
  },
  red_apoyo: { texto: null },
}

const UN_CAMPO: Campos = {
  red_apoyo: { texto: 'Primero a Carmen: +56 9 5555 0141.\nSi no contesta, a Rodrigo, su hijo: +56 9 5555 0102.' },
}

const largo = (base: string) => base.repeat(Math.ceil(500 / base.length)).slice(0, 500)
const TEXTOS_LARGOS: Campos = {
  rutina: {
    texto: largo(
      '07:30 Se despierta despacio y pide que le abran la cortina antes de levantarse de la cama.\n9.15 - Desayuno con pan amasado.\nSin hora: conversa con la vecina.\n',
    ),
  },
  manejo_situaciones: {
    texto: largo('Extraordinariamente tranquila cuando le hablan de su pueblo y de sus hermanas, y cuando le ofrecen una agüita. '),
  },
  red_apoyo: { texto: largo('Bernardita, su sobrina: +56 9 5555 0177. Rodrigo, su hijo: +56 9 5555 0102. ') },
}

// MATU-50: las secciones compartidas (ficha-ampliada.openapi.yaml), en el orden de ADR-028.
type SeccionRelevo = { tipo: 'quien_es' | 'preferencias' | 'alimentacion' | 'movilidad' | 'comunicacion' | 'remedios'; texto: string }
const DOS_SECCIONES: SeccionRelevo[] = [
  { tipo: 'quien_es', texto: 'Le dicen Mari. Fue costurera en Chillán y le encanta contar cómo era la fábrica.\nSu nieta Sofía le visita los domingos.' },
  { tipo: 'comunicacion', texto: 'Usa audífono en el oído izquierdo. Háblale de frente y despacio. Si algo le molesta, se toca la frente.' },
]
const SEIS_SECCIONES: SeccionRelevo[] = [
  DOS_SECCIONES[0],
  { tipo: 'preferencias', texto: 'Le gustan los boleros y conversar de fútbol. Ve las noticias a las 9 de la noche.' },
  { tipo: 'alimentacion', texto: 'Toma té con poca azúcar. Prefiere la comida picada en trozos chicos y el pan blando.\nNo le gusta el pescado.' },
  { tipo: 'movilidad', texto: 'Camina con bastón dentro de la casa. Para levantarse, ofrécele el brazo derecho.\nDuerme siesta después de almuerzo.' },
  DOS_SECCIONES[1],
  {
    tipo: 'remedios',
    texto: '08:00 con el desayuno: 1 pastilla blanca de la caja azul.\n14:00 después de almuerzo: media pastilla de la caja amarilla.\n20:00: 1 pastilla de la caja verde.',
  },
]
const SECCIONES_LARGAS: SeccionRelevo[] = SEIS_SECCIONES.map((s) => ({
  tipo: s.tipo,
  texto: s.tipo === 'remedios' ? '08:00 con el desayuno: 1 pastilla blanca de la caja azul.\n'.repeat(15).slice(0, 800).trim() : largo(`${s.texto.replace(/\n/g, ' ')} `),
}))

function seccionesDe(token: string): SeccionRelevo[] {
  if (token === 'ejemplo-con-secciones') return DOS_SECCIONES
  if (token === 'ejemplo-con-remedios') return SEIS_SECCIONES
  if (token === 'ejemplo-textos-largos') return SECCIONES_LARGAS
  return []
}

function fichaDe(s: Sesion) {
  const enDosDias = Math.ceil((Date.now() + 2 * 86_400_000) / 3_600_000) * 3_600_000
  const vence = s.token === 'ejemplo-vence-pronto' ? s.abiertaEn + 90_000 : enDosDias
  const largos = s.token === 'ejemplo-textos-largos'
  return {
    nombre_pila: largos ? 'Maximiliana' : 'María',
    nombre_pila_comparte: largos ? 'Bernardita' : 'Carmen',
    vence_en: new Date(vence).toISOString().replace(/\.\d{3}Z$/, 'Z'),
    campos: s.token === 'ejemplo-un-campo' ? UN_CAMPO : largos ? TEXTOS_LARGOS : TRES_CAMPOS,
    secciones: seccionesDe(s.token),
  }
}

function presentacionDe(token: string) {
  const largos = token === 'ejemplo-textos-largos'
  return { nombre_pila_comparte: largos ? 'Bernardita' : 'Carmen', nombre_pila: largos ? 'Maximiliana' : 'María' }
}

// ---------------------------------------------------------------- respuestas

function cabeceras(res: ServerResponse) {
  res.setHeader('X-Request-ID', randomUUID())
  res.setHeader('Cache-Control', 'no-store')
  res.setHeader('Referrer-Policy', 'no-referrer')
  res.setHeader('X-Robots-Tag', 'noindex')
}

function json(res: ServerResponse, status: number, cuerpo: unknown) {
  cabeceras(res)
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json')
  res.end(JSON.stringify(cuerpo))
}

// `title` y `detail` llevan a propósito un texto que la página nunca debe mostrar.
function problema(res: ServerResponse, status: number, tipo: string, extra: Record<string, unknown> = {}) {
  cabeceras(res)
  res.statusCode = status
  res.setHeader('Content-Type', 'application/problem+json')
  res.end(
    JSON.stringify({
      type: tipo,
      title: 'TITLE DEL DOBLE: NO SE MUESTRA',
      status,
      detail: 'DETAIL DEL DOBLE: NO SE MUESTRA',
      errores: [],
      request_id: randomUUID(),
      ...extra,
    }),
  )
}

const validacion = (res: ServerResponse, campo: string) =>
  problema(res, 422, '/errores/validacion', { errores: [{ campo, mensaje: 'MENSAJE DEL DOBLE: NO SE MUESTRA', tipo: 'string_pattern_mismatch' }] })

function borrarCookie(res: ServerResponse) {
  res.setHeader('Set-Cookie', `${COOKIE}=; Max-Age=0; Path=/v1/relevo; HttpOnly; SameSite=Strict`)
}

function demasiadas(res: ServerResponse, segundos: number | null) {
  if (segundos !== null) res.setHeader('Retry-After', String(segundos))
  problema(res, 429, '/errores/demasiadas-peticiones')
}

/** Estado del acceso en la presentación y el canje (pasos 3 a 5 del contrato). */
function estadoDelAcceso(res: ServerResponse, token: string): boolean {
  if (!TOKENS.has(token) || token === 'ejemplo-no-disponible') return problema(res, 410, '/errores/relevo-no-disponible'), true
  if (token === 'ejemplo-cortado') return problema(res, 410, '/errores/relevo-revocado'), true
  if (token === 'ejemplo-vencido') return problema(res, 410, '/errores/relevo-vencido'), true
  if (token === 'ejemplo-pausado') return problema(res, 410, '/errores/relevo-pausado'), true
  if (token === 'ejemplo-bloqueado' || (fallidos.get(token) ?? 0) >= MAX_INTENTOS) return problema(res, 423, '/errores/relevo-bloqueado'), true
  return false
}

// ---------------------------------------------------------------- rutas

async function leerCuerpo(req: IncomingMessage): Promise<Record<string, unknown> | null> {
  const partes: Buffer[] = []
  for await (const p of req) partes.push(p as Buffer)
  try {
    const v: unknown = JSON.parse(Buffer.concat(partes).toString('utf8') || 'null')
    return v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null
  } catch {
    return null
  }
}

const tokenValido = (t: unknown): t is string => typeof t === 'string' && t.length >= 1 && t.length <= 128

function presentacion(cuerpo: Record<string, unknown> | null, res: ServerResponse) {
  const token = cuerpo?.token
  if (token === 'ejemplo-espera-60') return demasiadas(res, 60)
  if (token === 'ejemplo-espera-600') return demasiadas(res, 600)
  if (token === 'ejemplo-espera-sin-cabecera') return demasiadas(res, null)
  if (!cuerpo || !tokenValido(token) || Object.keys(cuerpo).length !== 1) return validacion(res, 'token')
  if (token === 'ejemplo-error-500') return problema(res, 500, '/errores/interno')
  if (token === 'ejemplo-error-una-vez') {
    const n = (presentacionesFallidas.get(token) ?? 0) + 1
    presentacionesFallidas.set(token, n)
    if (n % 2 === 1) return problema(res, 500, '/errores/interno')
  }
  if (estadoDelAcceso(res, token)) return
  json(res, 200, presentacionDe(token))
}

function canje(cuerpo: Record<string, unknown> | null, res: ServerResponse) {
  const token = cuerpo?.token
  if (token === 'ejemplo-espera-canje') return demasiadas(res, 600)
  if (!cuerpo || !tokenValido(token)) return validacion(res, 'token')
  if (typeof cuerpo.pin !== 'string' || !/^[0-9]{4}$/.test(cuerpo.pin)) return validacion(res, 'pin')
  if (estadoDelAcceso(res, token)) return
  if (token === 'ejemplo-error-canje') return problema(res, 500, '/errores/interno')
  if (cuerpo.pin !== PIN_DE_EJEMPLO) {
    if (token === 'ejemplo-quedan-3') return problema(res, 401, '/errores/pin-incorrecto', { intentos_restantes: 3 })
    if (token === 'ejemplo-quedan-1') return problema(res, 401, '/errores/pin-incorrecto', { intentos_restantes: 1 })
    const n = (fallidos.get(token) ?? 0) + 1
    fallidos.set(token, n)
    if (n >= MAX_INTENTOS) return problema(res, 423, '/errores/relevo-bloqueado')
    return problema(res, 401, '/errores/pin-incorrecto', { intentos_restantes: MAX_INTENTOS - n })
  }
  fallidos.delete(token)
  const id = randomUUID()
  sesiones.set(id, { token, lecturas: 0, abiertaEn: Date.now() })
  cabeceras(res)
  res.setHeader('Set-Cookie', `${COOKIE}=${id}; Max-Age=43200; Path=/v1/relevo; HttpOnly; SameSite=Strict`)
  res.statusCode = 204
  res.end()
}

function ficha(id: string | undefined, res: ServerResponse) {
  const s = id ? sesiones.get(id) : undefined
  if (!id || !s) return problema(res, 401, '/errores/sin-sesion-relevo')
  s.lecturas += 1
  const despues = s.lecturas > 1
  const cerrar = (status: number, tipo: string) => {
    sesiones.delete(id)
    borrarCookie(res)
    problema(res, status, tipo)
  }
  if (s.token === 'ejemplo-error-ficha') {
    const n = (lecturasFallidas.get(id) ?? 0) + 1
    lecturasFallidas.set(id, n)
    if (n === 1) return problema(res, 500, '/errores/interno')
  }
  if (despues && s.token === 'ejemplo-sesion-cerrada') {
    sesiones.delete(id)
    return problema(res, 401, '/errores/sin-sesion-relevo')
  }
  if (despues && s.token === 'ejemplo-cortado-despues') return cerrar(410, '/errores/relevo-revocado')
  if (despues && s.token === 'ejemplo-bloqueado-despues') return cerrar(423, '/errores/relevo-bloqueado')
  if (despues && s.token === 'ejemplo-pausado-despues') return cerrar(410, '/errores/relevo-pausado')
  if (despues && s.token === 'ejemplo-actualizar-falla') return problema(res, 503, '/errores/servicio-no-disponible')
  if (s.token === 'ejemplo-vence-pronto' && Date.now() > s.abiertaEn + 90_000) return cerrar(410, '/errores/relevo-vencido')
  json(res, 200, fichaDe(s))
}

// ---------------------------------------------------------------- plugin

const idDeCookie = (req: IncomingMessage) => /(?:^|;\s*)matu-relevo-doble=([^;]+)/.exec(req.headers.cookie ?? '')?.[1]

async function atender(req: IncomingMessage, res: ServerResponse, siguiente: () => void) {
  const ruta = `${req.method} ${(req.url ?? '').split('?')[0]}`
  if (!ruta.includes(' /v1/')) return siguiente()
  const cuerpo = req.method === 'POST' || req.method === 'PUT' ? await leerCuerpo(req) : null
  const id = idDeCookie(req)
  // Latencia simulada: 150 ms, o 2 s con `ejemplo-lento` para ver los textos de carga.
  const lento = cuerpo?.token === 'ejemplo-lento' || esLento(req, cuerpo) || (id !== undefined && sesiones.get(id)?.token === 'ejemplo-lento')
  await new Promise((r) => setTimeout(r, lento ? 2000 : 150))
  if (ruta === 'POST /v1/relevo/presentacion') return presentacion(cuerpo, res)
  if (ruta === 'POST /v1/relevo/canje') return canje(cuerpo, res)
  if (ruta === 'GET /v1/relevo/ficha') return ficha(id, res)
  // La app de la familia (MATU-39): cuentas, entrada, grupos, personas y ficha.
  if (await atenderFamilia(req, res, cuerpo, { json, problema })) return
  problema(res, 404, '/errores/no-encontrado')
}

function middleware(req: IncomingMessage, res: ServerResponse, siguiente: () => void) {
  atender(req, res, siguiente).catch(() => problema(res, 500, '/errores/interno'))
}

/** Plugin de Vite: el doble atiende /v1 en `npm run dev` y `npm run preview`. */
export function dobleDelRelevo(): Plugin {
  return {
    name: 'matu-doble-relevo',
    configureServer(server) {
      server.middlewares.use(middleware)
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware)
    },
  }
}

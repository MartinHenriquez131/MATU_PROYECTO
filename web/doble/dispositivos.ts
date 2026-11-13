// MATU-55 en el doble: los dispositivos de cada cuenta, los últimos ingresos (`GET /v1/yo/ingresos`),
// los avisos (`/v1/yo/avisos`) y el push de este dispositivo (`/v1/dispositivos/actual/push`), con
// la forma del contrato docs/api/openapi.json. Cada entrada crea un dispositivo con el nombre que
// sale del agente de usuario (que no se guarda), y el access token lleva su id, como el claim `did`.
// Todo vive en memoria y se pierde al reiniciar `npm run dev`. Datos sintéticos.
import { generateKeyPairSync, randomUUID } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'

type Clase = 'telefono' | 'computador' | 'otro'
type Tipo =
  | 'entraste'
  | 'saliste'
  | 'cerraste_en_dispositivo'
  | 'salida_por_seguridad'
  | 'contrasena_cambiada'
  | 'celular_confirmado'
  | 'codigo_recuperacion_pedido'
  | 'avisos_cambiados'
  | 'avisos_activados'
  | 'avisos_desactivados'
  // MATU-54 (5.5): cada «Tus datos» abierto. La copia de la persona no entra aquí (decisión 358).
  | 'pediste_una_copia'

interface Dispositivo {
  id: string
  email: string
  nombre: string
  clase: Clase
  creado_en: string
  ultimo_uso_en: string | null
  revocado: boolean
  /** La conservación lo borró (decisión 59): sus eventos llegan con `dispositivo: null`. */
  borrado: boolean
  push: string | null
  /** MATU-54: cuándo se cerró, para «Se cerró el…» de «Tus datos». Los sembrados usan su último uso. */
  cerrado_en?: string | null
}
interface Evento {
  email: string
  tipo: Tipo
  ocurrido_en: string
  dispositivo: string | null
}

type Responder = {
  json: (res: ServerResponse, status: number, cuerpo: unknown) => void
  problema: (res: ServerResponse, status: number, tipo: string, extra?: Record<string, unknown>) => void
}

const dispositivos = new Map<string, Dispositivo>()
const eventos: Evento[] = []
const avisos = new Map<string, { correo: boolean; push: boolean }>()
const sembradas = new Set<string>()

// La clave pública VAPID del doble: un punto P-256 real (65 bytes sin comprimir, en base64url), para
// que `PushManager.subscribe()` funcione en un navegador de verdad. La privada no sale de aquí.
const CLAVE_PUBLICA = (() => {
  const { publicKey } = generateKeyPairSync('ec', { namedCurve: 'prime256v1' })
  const jwk = publicKey.export({ format: 'jwk' })
  const bytes = Buffer.concat([Buffer.from([4]), Buffer.from(String(jwk.x), 'base64url'), Buffer.from(String(jwk.y), 'base64url')])
  return bytes.toString('base64url')
})()

const hace = (min: number) => new Date(Date.now() - min * 60_000).toISOString()
const DIA = 24 * 60

/** «Chrome en Android» y su clase, del agente de usuario (como el servidor, decisión C7). El agente no se guarda. */
export function nombreDeAgente(ua: string): { nombre: string; clase: Clase } {
  const navegador = /SamsungBrowser/.test(ua) ? 'Samsung Internet' : /Edg\//.test(ua) ? 'Edge' : /Firefox|FxiOS/.test(ua) ? 'Firefox' : /Chrome|CriOS/.test(ua) ? 'Chrome' : /Safari/.test(ua) ? 'Safari' : null
  const [sistema, clase]: [string, Clase] | [null, Clase] = /Android/.test(ua)
    ? ['Android', 'telefono']
    : /iPhone|iPod/.test(ua)
      ? ['iPhone', 'telefono']
      : /iPad/.test(ua)
        ? ['iPad', 'otro']
        : /Windows/.test(ua)
          ? ['Windows', 'computador']
          : /CrOS/.test(ua)
            ? ['ChromeOS', 'computador']
            : /Mac OS X/.test(ua)
              ? ['Mac', 'computador']
              : /Linux/.test(ua)
                ? ['Linux', 'computador']
                : [null, 'otro']
  if (!navegador || !sistema) return { nombre: 'Navegador web', clase: 'otro' }
  return { nombre: `${navegador} en ${sistema}`, clase }
}

function nuevo(email: string, nombre: string, clase: Clase, creado: number, uso: number | null, extra: Partial<Dispositivo> = {}): Dispositivo {
  const d: Dispositivo = { id: randomUUID(), email, nombre, clase, creado_en: hace(creado), ultimo_uso_en: uso === null ? null : hace(uso), revocado: false, borrado: false, push: null, ...extra }
  dispositivos.set(d.id, d)
  return d
}
const anotar = (email: string, tipo: Tipo, min: number, dispositivo: string | null) => eventos.push({ email, tipo, ocurrido_en: hace(min), dispositivo })

/**
 * La primera vez que entra una cuenta, dos dispositivos más y una historia de ejemplo: un ingreso
 * desde un teléfono que la conservación ya borró, un código pedido (en `atenta`) y una salida por
 * seguridad. `ingresos-muchos`: 24 eventos, así que `hay_mas`. `ingresos-vacio`: sin historia.
 */
function sembrar(email: string, modo: string | undefined) {
  if (sembradas.has(email)) return
  sembradas.add(email)
  if (modo === 'ingresos-vacio') return
  const pc = nuevo(email, 'Chrome en Windows', 'computador', 30 * DIA, 2 * DIA + 7 * 60)
  const iphone = nuevo(email, 'Safari en iPhone', 'telefono', 12 * DIA, 26 * 60)
  const viejo = nuevo(email, 'Samsung Internet en Android', 'telefono', 120 * DIA, 95 * DIA, { revocado: true, borrado: true })
  anotar(email, 'codigo_recuperacion_pedido', 75, null)
  anotar(email, 'contrasena_cambiada', 26 * 60, null)
  anotar(email, 'entraste', 26 * 60 + 5, iphone.id)
  anotar(email, 'salida_por_seguridad', 3 * DIA, iphone.id)
  anotar(email, 'avisos_activados', 4 * DIA, iphone.id)
  anotar(email, 'celular_confirmado', 5 * DIA, null)
  anotar(email, 'avisos_cambiados', 8 * DIA, null)
  const prestado = nuevo(email, 'Firefox en Linux', 'computador', 7 * DIA, 7 * DIA - 30, { revocado: true })
  anotar(email, 'cerraste_en_dispositivo', 6 * DIA, prestado.id)
  anotar(email, 'entraste', 7 * DIA, prestado.id)
  anotar(email, 'avisos_desactivados', 7 * DIA + 60, iphone.id)
  anotar(email, 'saliste', 9 * DIA - 120, pc.id)
  anotar(email, 'entraste', 9 * DIA, pc.id)
  anotar(email, 'entraste', 40 * DIA, viejo.id)
  if (modo === 'ingresos-muchos') for (let i = 0; i < 16; i++) anotar(email, i % 2 ? 'saliste' : 'entraste', 10 * DIA + i * 180, pc.id)
  // MATU-54: más de 20 ingresos en 90 días («Ver más») y otros anteriores, que solo van en el archivo.
  if (modo === 'datos-historial') {
    for (let i = 0; i < 30; i++) anotar(email, i % 2 ? 'saliste' : 'entraste', 11 * DIA + i * 2 * DIA, pc.id)
    for (let i = 0; i < 6; i++) anotar(email, 'entraste', 95 * DIA + i * DIA, viejo.id)
  }
}

/** `POST /v1/sesiones`: un dispositivo nuevo, el `did` del token. */
export function alEntrar(email: string, ua: string, modo: string | undefined): string {
  sembrar(email, modo)
  const { nombre, clase } = nombreDeAgente(ua)
  const d = nuevo(email, nombre, clase, 0, 0)
  if (modo !== 'ingresos-vacio') anotar(email, 'entraste', 0, d.id)
  return d.id
}

/** `POST /v1/sesiones/cerrar`: el dispositivo se revoca. */
export function alSalir(did: string | undefined) {
  const d = did ? dispositivos.get(did) : undefined
  if (!d || d.revocado) return
  d.revocado = true
  d.cerrado_en = hace(0)
  d.push = null
  anotar(d.email, 'saliste', 0, d.id)
}

/** El refresh de un dispositivo revocado ya no renueva. */
export const dispositivoVivo = (did: string | undefined) => !!did && dispositivos.get(did)?.revocado === false

export function usoDe(did: string | undefined) {
  const d = did ? dispositivos.get(did) : undefined
  if (d) d.ultimo_uso_en = hace(0)
}

/** Lo que pasa sin dispositivo de por medio (MATU-57): el código pedido, la contraseña y el celular. */
export function anotarCuenta(email: string, tipo: 'codigo_recuperacion_pedido' | 'contrasena_cambiada' | 'celular_confirmado') {
  anotar(email, tipo, 0, null)
}

/** MATU-54: «Tus datos» se abrió, y la copia ya trae esta línea (decisión 347). */
export function anotarCopia(email: string) {
  anotar(email, 'pediste_una_copia', 0, null)
}

/**
 * MATU-54: lo de MATU-55 que va en «Tus datos»: todos los dispositivos que se guardan (también los
 * cerrados, salvo los que la conservación ya borró), todos los eventos y la preferencia de avisos.
 * `instante` escribe el instante con el desfase de Chile, como la copia (decisión 349).
 */
export function paraCopia(email: string, modo: string | undefined, editor: boolean, instante: (iso: string) => string) {
  sembrar(email, modo)
  const propios = [...dispositivos.values()].filter((d) => d.email === email && !d.borrado)
  return {
    dispositivos: propios.map((d) => ({
      nombre: d.nombre,
      clase: d.clase,
      creado_en: instante(d.creado_en),
      ultimo_uso_en: d.ultimo_uso_en ? instante(d.ultimo_uso_en) : null,
      cerrado_en: d.revocado ? instante(d.cerrado_en ?? d.ultimo_uso_en ?? d.creado_en) : null,
      avisos_activos: d.push !== null,
    })),
    eventos: eventos
      .filter((e) => e.email === email)
      .sort((a, b) => new Date(b.ocurrido_en).getTime() - new Date(a.ocurrido_en).getTime())
      .map((e) => {
        const d = e.dispositivo ? dispositivos.get(e.dispositivo) : undefined
        return { tipo: e.tipo, ocurrido_en: instante(e.ocurrido_en), dispositivo: d && !d.borrado ? { nombre: d.nombre, clase: d.clase } : null }
      }),
    preferencia_avisos: avisosDe(email, editor),
  }
}

/** Decisión 78: sin preferencia guardada, activos si es admin o cuidador en algún grupo. */
const avisosDe = (email: string, editor: boolean) => avisos.get(email) ?? { correo: editor, push: editor }

const vistaDispositivo = (d: Dispositivo, did: string | undefined) => ({
  id: d.id,
  plataforma: 'web',
  nombre: d.nombre,
  clase: d.clase,
  creado_en: d.creado_en,
  ultimo_uso_en: d.ultimo_uso_en,
  actual: d.id === did,
  push_activo: d.push !== null,
})

function vistaEvento(e: Evento, did: string | undefined) {
  const d = e.dispositivo ? dispositivos.get(e.dispositivo) : undefined
  return { tipo: e.tipo, ocurrido_en: e.ocurrido_en, dispositivo: d && !d.borrado ? { nombre: d.nombre, clase: d.clase, actual: d.id === did } : null }
}

const sinCuerpo = (res: ServerResponse) => {
  res.setHeader('Cache-Control', 'no-store')
  res.statusCode = 204
  res.end()
}

/**
 * Atiende /v1/dispositivos y /v1/yo de una cuenta que ya entró. `revocar` corta los refresh del
 * dispositivo que se cierra (el access token sigue sus 15 minutos, como en la API).
 */
export function atenderDispositivos(
  req: IncomingMessage,
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  { json, problema }: Responder,
  cuenta: { email: string; modo?: string; editor: boolean },
  did: string | undefined,
  revocar: (did: string) => void,
): boolean {
  const metodo = req.method ?? 'GET'
  const ruta = (req.url ?? '').split('?')[0]
  const { email, modo, editor } = cuenta
  const falla = (...modos: string[]) => !!modo && modos.includes(modo)
  if (!ruta.startsWith('/v1/dispositivos') && !ruta.startsWith('/v1/yo/')) return false
  res.setHeader('Cache-Control', 'no-store')

  if (metodo === 'GET' && ruta === '/v1/dispositivos') {
    if (falla('donde-falla')) return problema(res, 500, '/errores/interno'), true
    const propios = [...dispositivos.values()].filter((d) => d.email === email && !d.revocado)
    const uso = (d: Dispositivo) => new Date(d.ultimo_uso_en ?? d.creado_en).getTime()
    propios.sort((a, b) => (a.id === did ? -1 : b.id === did ? 1 : uso(b) - uso(a)))
    return json(res, 200, { items: propios.map((d) => vistaDispositivo(d, did)) }), true
  }

  if (metodo === 'GET' && ruta === '/v1/yo/ingresos') {
    if (falla('donde-falla')) return problema(res, 500, '/errores/interno'), true
    const desde = Date.now() - 90 * DIA * 60_000
    const propios = eventos
      .filter((e) => e.email === email && new Date(e.ocurrido_en).getTime() >= desde)
      .sort((a, b) => new Date(b.ocurrido_en).getTime() - new Date(a.ocurrido_en).getTime())
    return json(res, 200, { eventos: propios.slice(0, 20).map((e) => vistaEvento(e, did)), hay_mas: propios.length > 20 }), true
  }

  if (ruta === '/v1/dispositivos/actual/push') {
    const d = did ? dispositivos.get(did) : undefined
    if (!d || d.revocado) return problema(res, 404, '/errores/no-encontrado'), true
    if (metodo === 'GET') {
      if (falla('avisos-falla')) return problema(res, 500, '/errores/interno'), true
      return json(res, 200, { clave_publica: modo === 'push-sin-clave' || modo === 'push-no-permitido' ? null : CLAVE_PUBLICA, permitido: modo !== 'push-no-permitido', registrado: d.push !== null, envio_simulado: true }), true
    }
    if (metodo === 'PUT') {
      const token = cuerpo?.push_token
      if (typeof token !== 'string' || !/^https:\/\/\S+$/.test(token) || token.length < 12 || token.length > 1024)
        return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'push_token', mensaje: 'MENSAJE DEL DOBLE', tipo: 'push_no_admitido' }] }), true
      if (falla('avisos-guardar-falla')) return problema(res, 500, '/errores/interno'), true
      // MATU-107 (C14): fuera del equipo del piloto, o la regla cambió con la pantalla abierta.
      if (modo === 'push-no-permitido' || modo === 'push-409') return problema(res, 409, '/errores/push-no-permitido'), true
      if (d.push !== token) anotar(email, 'avisos_activados', 0, d.id)
      d.push = token
      return sinCuerpo(res), true
    }
    if (metodo === 'DELETE') {
      if (falla('avisos-guardar-falla')) return problema(res, 500, '/errores/interno'), true
      if (d.push !== null) anotar(email, 'avisos_desactivados', 0, d.id)
      d.push = null
      return sinCuerpo(res), true
    }
  }

  const id = /^\/v1\/dispositivos\/([^/]+)$/.exec(ruta)?.[1]
  if (metodo === 'DELETE' && id) {
    const d = dispositivos.get(id)
    if (!d || d.email !== email) return problema(res, 404, '/errores/no-encontrado'), true
    if (falla('cerrar-falla')) return problema(res, 500, '/errores/interno'), true
    if (!d.revocado) {
      d.revocado = true
      d.cerrado_en = hace(0)
      d.push = null
      revocar(d.id)
      anotar(email, 'cerraste_en_dispositivo', 0, d.id)
    }
    return sinCuerpo(res), true
  }

  if (ruta === '/v1/yo/avisos') {
    if (metodo === 'GET') {
      if (falla('avisos-falla')) return problema(res, 500, '/errores/interno'), true
      return json(res, 200, avisosDe(email, editor)), true
    }
    if (metodo === 'PUT') {
      if (typeof cuerpo?.correo !== 'boolean' || typeof cuerpo?.push !== 'boolean')
        return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'correo', mensaje: 'MENSAJE DEL DOBLE', tipo: 'bool_type' }] }), true
      if (falla('avisos-guardar-falla')) return problema(res, 500, '/errores/interno'), true
      const antes = avisosDe(email, editor)
      const nueva = { correo: cuerpo.correo, push: cuerpo.push }
      if (antes.correo !== nueva.correo || antes.push !== nueva.push) anotar(email, 'avisos_cambiados', 0, null)
      avisos.set(email, nueva)
      return json(res, 200, nueva), true
    }
  }
  return problema(res, 404, '/errores/no-encontrado'), true
}

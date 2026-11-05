// Doble del contrato de la app de la familia (docs/api/openapi.json) para desarrollo: cuentas,
// entrada con la cookie del refresh, grupos, personas y la ficha con ETag, 412 y 428. Igual que el
// doble del relevo, responde por HTTP de verdad y no entra al build. Datos sintéticos: Carmen cuida
// a María, Rodrigo es su hijo; los teléfonos usan la serie 5555, que no se asigna.
import { randomInt, randomUUID } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'

import { atenderConsumo, crearAlertas, listaCompleta, perfil, type ConsumoDoble } from './consumo'
import { CONTRASENA_DE_EJEMPLO } from './cuentas'

type Rol = 'admin' | 'cuidador' | 'pagador' | 'observador'
type CampoApi = 'rutina' | 'manejo_situaciones' | 'red_apoyo'
/** Las seis secciones complementarias (MATU-50, docs/api/propuestos/ficha-ampliada.openapi.yaml). */
type SeccionApi = 'quien_es' | 'preferencias' | 'alimentacion' | 'movilidad' | 'comunicacion' | 'remedios'
const SECCIONES: SeccionApi[] = ['quien_es', 'preferencias', 'alimentacion', 'movilidad', 'comunicacion', 'remedios']
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
  /** Solo las secciones agregadas: una sección quitada no queda vacía, deja de existir. */
  secciones: Partial<Record<SeccionApi, Campo>>
  /** MATU-36: la autorización con finalidad `consumo` y los insumos. */
  consumo: ConsumoDoble
  /** Lo que hicieron los relevos (MATU-45), del más reciente al más antiguo. */
  aperturas: Apertura[]
}
type TipoApertura = 'presentacion' | 'apertura' | 'pin_incorrecto' | 'bloqueo'
interface Apertura {
  ocurrido_en: string
  tipo: TipoApertura
  acceso: { id: string; nombre_relevo: string }
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
  /** MATU-57: el celular en E.164 (serie 5555), si está confirmado y el canal preferido. */
  telefono: string | null
  celularVerificado: boolean
  canal: 'sms' | 'whatsapp'
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
    secciones: {},
    consumo: { autorizacion: 'no', perfiles: [] },
    aperturas: [],
  }
}

const DIA = 24 * 60
/** Una línea de apertura `min` minutos atrás. */
const linea = (acceso: { id: string; nombre_relevo: string }, tipo: TipoApertura, min: number): Apertura => ({ ocurrido_en: hace(min), tipo, acceso })

/**
 * Las aperturas de María (MATU-45): los cuatro tipos, una presentación sin apertura (Carla), un
 * bloqueo (Pedro), varios días (hoy, ayer, hace 3 días y desde hace 10) y 27 líneas, para la paginación.
 */
function aperturasDeEjemplo(): Apertura[] {
  const rosa = { id: randomUUID(), nombre_relevo: 'Rosa' }
  const carla = { id: randomUUID(), nombre_relevo: 'Carla' }
  const pedro = { id: randomUUID(), nombre_relevo: 'Pedro' }
  const rosaAntes = { id: randomUUID(), nombre_relevo: 'Rosa' }
  const lista: Apertura[] = [
    linea(rosa, 'apertura', 25),
    linea(rosa, 'pin_incorrecto', 27),
    linea(rosa, 'presentacion', 28),
    linea(carla, 'presentacion', DIA + 120),
    linea(pedro, 'bloqueo', 3 * DIA),
    ...[1, 2, 3, 4, 5].map((i) => linea(pedro, 'pin_incorrecto', 3 * DIA + i)),
    linea(pedro, 'presentacion', 3 * DIA + 7),
  ]
  // Desde hace diez días: Rosa, la vez anterior, abre la ficha una vez por día.
  for (let d = 10; d < 18; d++) lista.push(linea(rosaAntes, 'apertura', d * DIA), linea(rosaAntes, 'presentacion', d * DIA + 1))
  return lista
}
const conAperturas = (p: Persona) => ((p.aperturas = aperturasDeEjemplo()), p)

// Secciones de ejemplo (MATU-50), con los textos de lenguaje 14.1 adaptados a María.
const TEXTOS_SECCION: Record<SeccionApi, string> = {
  quien_es: 'Le dicen Mari. Fue costurera en Chillán y le encanta contar cómo era la fábrica.\nSu nieta Sofía le visita los domingos.',
  preferencias: 'Le gustan los boleros y conversar de fútbol. Ve las noticias a las 9 de la noche.',
  alimentacion: 'Toma té con poca azúcar. Prefiere la comida picada en trozos chicos y el pan blando.\nNo le gusta el pescado.',
  movilidad: 'Camina con bastón dentro de la casa. Para levantarse, ofrécele el brazo derecho.\nDuerme siesta después de almuerzo.',
  comunicacion: 'Usa audífono en el oído izquierdo. Háblale de frente y despacio. Si algo le molesta, se toca la frente.',
  remedios: '08:00 con el desayuno: 1 pastilla blanca de la caja azul.\n14:00 después de almuerzo: media pastilla de la caja amarilla.\n20:00: 1 pastilla de la caja verde.',
}
const topeSeccion = (s: SeccionApi) => (s === 'remedios' ? 800 : 500)
const repetir = (base: string, n: number) => base.repeat(Math.ceil(n / base.length)).slice(0, n)

/** Agrega a `p` las secciones pedidas, escritas por `autor` (por defecto, el texto de ejemplo). */
function conSecciones(p: Persona, autor: { id: string; nombre: string }, lista: SeccionApi[], textos: Partial<Record<SeccionApi, string>> = {}) {
  lista.forEach((s, i) => (p.secciones[s] = escrito(textos[s] ?? TEXTOS_SECCION[s], autor, 60 * (i + 1))))
  return p
}

const usuarios = new Map<string, Usuario>()

function cuenta(email: string, nombre: string, grupos: Grupo[], modo?: string): Usuario {
  const u: Usuario = { id: randomUUID(), nombre, email, contrasena: CONTRASENA_DE_EJEMPLO, grupos, modo, telefono: '+56955550137', celularVerificado: false, canal: 'sms' }
  usuarios.set(email, u)
  return u
}
const grupo = (nombre: string, rol: Rol, personas: Persona[], puede_ver_plan = false): Grupo => ({ id: randomUUID(), nombre, rol, puede_ver_plan, personas })

/** MATU-36: la primera persona de la cuenta, con su consumo. */
function insumos(u: Usuario, autorizacion: ConsumoDoble['autorizacion'], lista: boolean) {
  const p = u.grupos[0].personas[0]
  p.consumo = { autorizacion, perfiles: lista ? listaCompleta({ id: u.id, nombre: u.nombre }) : [] }
  crearAlertas(p.consumo)
  return p.consumo
}

function sembrar() {
  const carmen = cuenta('carmen@ejemplo.cl', 'Carmen', [])
  const yo = { id: carmen.id, nombre: 'Carmen' }
  carmen.grupos.push(grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }))]))
  insumos(carmen, 'vigente', true)
  cuenta('completa@ejemplo.cl', 'Carmen', [
    grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo), manejo_situaciones: escrito(SI_SE_ALTERA, RODRIGO, 5), red_apoyo: escrito(A_QUIEN, yo, 3) }))]),
  ])
  cuenta('vacia@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])])
  cuenta('dos-grupos@ejemplo.cl', 'Carmen', [
    grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }), persona('Juan Soto', 'Juan')]),
    grupo('Familia Pérez', 'cuidador', [persona('Elena Pérez', 'Elena')]),
  ])
  cuenta('sin-persona@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [])])
  cuenta('sin-persona-pagador@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'pagador', [])])
  insumos(cuenta('pagador@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'pagador', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })])]), 'vigente', true)
  cuenta('pagador-ve@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'pagador', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }))], true)])
  cuenta('observador@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'observador', [conAperturas(persona('María Soto', 'María'))])])
  cuenta('cuidador@ejemplo.cl', 'Javiera', [grupo('Familia Soto', 'cuidador', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }))])])
  cuenta('aperturas-falla@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }))])], 'aperturas-falla')
  cuenta('sin-autorizacion@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'sin-consentimiento')
  cuenta('renovar-autorizacion@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', {}, 'cuidador_de_hecho')])], 'revision-vencida')
  cuenta('revision-al-guardar@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'revision-al-guardar')
  cuenta('conflicto@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })])], 'conflicto')
  cuenta('defectos@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'defectos')
  cuenta('vence@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'vence')
  insumos(cuenta('lento@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }))])], 'lento'), 'vigente', true)
  // MATU-36: insumos
  cuenta('insumos-permiso@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'cuidador', [persona('María Soto', 'María')])])
  insumos(cuenta('insumos-vacio@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])]), 'vigente', false)
  insumos(cuenta('insumos-observador@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'observador', [persona('María Soto', 'María')])]), 'vigente', true)
  insumos(cuenta('insumos-renovar@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', {}, 'cuidador_de_hecho')])]), 'vencida', true)
  insumos(cuenta('insumos-renovar-observador@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'observador', [persona('María Soto', 'María')])]), 'vencida', true)
  // MATU-37: «Se acaban pronto»
  insumos(cuenta('alertas@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])]), 'vigente', true)
  {
    const u = cuenta('alertas-sin@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])])
    const c = insumos(u, 'vigente', false)
    const yo = { id: u.id, nombre: u.nombre }
    c.perfiles = [perfil('Pañal adulto talla M', 'unidad', 4, 1, 120, 0, yo), perfil('Toallitas húmedas', 'unidad', 3, 1, 90, 1, yo), perfil('Champú en sobre', 'sobre', 1, 1, 30, 0, yo)]
    crearAlertas(c)
  }
  {
    // Recalculo en 0: usa 4 al día y no queda nada; comprar 1 a 3 deja «Alcanza para 0 días».
    const u = cuenta('alertas-cero@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])])
    const c = insumos(u, 'vigente', false)
    const yo = { id: u.id, nombre: u.nombre }
    c.perfiles = [perfil('Pañal adulto talla M', 'unidad', 4, 1, 0, 0, yo)]
    crearAlertas(c)
  }
  insumos(cuenta('alertas-observador@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'observador', [persona('María Soto', 'María')])]), 'vigente', true)
  insumos(cuenta('alertas-cerrada@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'cuidador', [persona('María Soto', 'María')])], 'alertas-cerrada'), 'vigente', true)
  insumos(cuenta('alertas-conflicto@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'cuidador', [persona('María Soto', 'María')])], 'alertas-conflicto'), 'vigente', true)
  insumos(cuenta('alertas-error@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'alertas-error'), 'vigente', true)
  insumos(cuenta('alertas-error-carga@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'alertas-error-carga'), 'vigente', true)
  insumos(cuenta('insumos-defectos@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'insumos-defectos'), 'vigente', true)
  // MATU-50: las secciones complementarias, una cuenta por estado.
  const completos = () => ({ rutina: escrito(SU_DIA, yo), manejo_situaciones: escrito(SI_SE_ALTERA, RODRIGO, 5), red_apoyo: escrito(A_QUIEN, yo, 3) })
  cuenta('secciones-ninguna@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', completos())])])
  cuenta('secciones-algunas@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [conSecciones(persona('María Soto', 'María', completos()), yo, ['quien_es', 'comunicacion'])])])
  cuenta('secciones-remedios@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [conSecciones(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }), yo, ['preferencias', 'remedios'])])])
  cuenta('secciones-todas@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [conSecciones(persona('María Soto', 'María', completos()), yo, SECCIONES)])])
  cuenta('secciones-conflicto@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [conSecciones(persona('María Soto', 'María', completos()), yo, ['quien_es', 'alimentacion', 'movilidad'])])], 'conflicto-secciones')
  cuenta('secciones-defectos@ejemplo.cl', 'Carmen', [grupo('Familia Soto', 'admin', [conSecciones(persona('María Soto', 'María', completos()), yo, ['quien_es', 'preferencias'])])], 'defectos-secciones')
  cuenta('secciones-pagador@ejemplo.cl', 'Rodrigo', [grupo('Familia Soto', 'pagador', [conSecciones(persona('María Soto', 'María', completos()), yo, ['quien_es', 'remedios'])], true)])
  cuenta('secciones-largas@ejemplo.cl', 'Bernardita', [
    grupo('Familia Valenzuela Etchegaray', 'admin', [
      conSecciones(persona('Maximiliana de los Ángeles Valenzuela Etchegaray', 'Maximiliana', completos()), yo, SECCIONES, {
        quien_es: repetir('Extraordinariamente conversadora cuando le preguntan por Constitución y por sus hermanas. ', 500),
        preferencias: repetir('Radio Cooperativa a todo volumen. ', 500),
        alimentacion: repetir('Pan amasado tibio con mantequilla. ', 500),
        movilidad: repetir('Necesita apoyo del brazo derecho al bajar la escalera. ', 500),
        comunicacion: repetir('Háblale despacio y de frente. ', 500),
        remedios: repetir('08:00 con el desayuno: 1 pastilla blanca de la caja azul.\n', 800).trim(),
      }),
    ]),
  ])
  cuenta(
    'largos@ejemplo.cl',
    'Bernardita',
    [grupo('Familia Valenzuela Etchegaray', 'admin', [persona('Maximiliana de los Ángeles Valenzuela Etchegaray', 'Maximiliana', { manejo_situaciones: escrito('Extraordinariamente tranquila cuando le hablan de su pueblo. '.repeat(8).slice(0, 480), yo) })])],
  )
  // MATU-57
  const soto = () => [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })])]
  cuenta('celular-verificado@ejemplo.cl', 'Carmen', soto()).celularVerificado = true
  cuenta('celular-sin-verificar@ejemplo.cl', 'Carmen', soto())
  cuenta('celular-espera@ejemplo.cl', 'Carmen', soto(), 'celular-espera')
  cuenta('sin-celular@ejemplo.cl', 'Carmen', soto()).telefono = null
  cuenta('recuperar-espera@ejemplo.cl', 'Carmen', soto(), 'recuperar-espera')
  cuenta('codigo-invalido@ejemplo.cl', 'Carmen', soto(), 'codigo-invalido')
}
sembrar()

// ---------------------------------------------------------------- códigos y envíos (MATU-57)
// Envío simulado: el código solo se escribe en la consola del servidor de desarrollo, nunca en una
// respuesta ni en la página. Datos sintéticos. Reglas de las decisiones 81 a 87: 6 dígitos, 10
// minutos, un solo uso, 5 intentos, pedir otro reemplaza al anterior, 60 s entre envíos del celular.

interface Codigo {
  codigo: string
  vence: number
  intentos: number
}
const codigos = new Map<string, Codigo>()
const ultimoEnvio = new Map<string, number>()

function enviarCodigo(clave: string, a: string, por: string) {
  const codigo = String(randomInt(0, 1_000_000)).padStart(6, '0')
  codigos.set(clave, { codigo, vence: Date.now() + 10 * 60_000, intentos: 0 })
  ultimoEnvio.set(clave, Date.now())
  console.info(`[doble · envío simulado] ${clave.split(':')[0]} → ${a} por ${por}: ${codigo}`)
}

/** `true` si el código sirve (y lo gasta). Cinco fallos lo agotan. */
function probarCodigo(clave: string, codigo: unknown): boolean {
  const c = codigos.get(clave)
  if (!c || c.vence < Date.now() || c.intentos >= 5) return false
  if (c.codigo !== codigo) {
    c.intentos += 1
    return false
  }
  codigos.delete(clave)
  return true
}

const enmascarar = (tel: string | null) => (tel ? `+56 9 •••• ••${tel.slice(-2)}` : null)
const sinCuerpo = (res: ServerResponse, status: 202 | 204) => {
  res.setHeader('Cache-Control', 'no-store')
  res.statusCode = status
  res.end()
}


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
    if (typeof contrasena !== 'string' || contrasena.length < 10 || contrasena.length > 128) errores.push({ campo: 'contrasena', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_too_short' }) // pragma: allowlist secret
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

  // ------------------------------------------------ MATU-57: recuperar (sin entrar)
  if (metodo === 'POST' && ruta === '/v1/recuperacion/codigo') {
    const email = typeof cuerpo?.email === 'string' ? cuerpo.email.trim().toLowerCase() : ''
    const extra = Object.keys(cuerpo ?? {}).filter((k) => k !== 'email' && k !== 'canal')
    if (!email || email.length > 254 || extra.length || (cuerpo?.canal != null && cuerpo.canal !== 'correo'))
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'email', mensaje: 'MENSAJE DEL DOBLE', tipo: 'value_error' }] }), true
    // Siempre 202 (decisión 84). Sin cuenta, o con un envío hace menos de 60 s, simplemente no se envía.
    const v = usuarios.get(email)
    const clave = `recuperar:${email}`
    if (v && Date.now() - (ultimoEnvio.get(clave) ?? 0) >= 60_000) {
      const alCelular = v.celularVerificado && v.telefono && cuerpo?.canal !== 'correo'
      enviarCodigo(clave, email, alCelular ? `${v.canal} al ${enmascarar(v.telefono)}` : 'correo')
    } else if (v) console.info(`[doble · envío simulado] recuperar → ${email}: no se envía (menos de 60 s del anterior)`)
    return sinCuerpo(res, 202), true
  }

  if (metodo === 'POST' && ruta === '/v1/recuperacion/contrasena') {
    const email = typeof cuerpo?.email === 'string' ? cuerpo.email.trim().toLowerCase() : ''
    const nueva = cuerpo?.contrasena_nueva
    const errores: { campo: string; mensaje: string; tipo: string }[] = []
    if (!email) errores.push({ campo: 'email', mensaje: 'MENSAJE DEL DOBLE', tipo: 'missing' })
    if (typeof cuerpo?.codigo !== 'string' || !/^[0-9]{6}$/.test(cuerpo.codigo)) errores.push({ campo: 'codigo', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_pattern_mismatch' })
    if (typeof nueva !== 'string' || nueva.length < 10 || nueva.length > 128) errores.push({ campo: 'contrasena_nueva', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_too_short' }) // pragma: allowlist secret
    if (errores.length) return problema(res, 422, '/errores/validacion', { errores }), true
    const v = usuarios.get(email)
    if (v?.modo === 'recuperar-espera') return res.setHeader('Retry-After', '120'), problema(res, 429, '/errores/demasiadas-peticiones'), true
    if (!v || v.modo === 'codigo-invalido' || !probarCodigo(`recuperar:${email}`, cuerpo?.codigo)) return problema(res, 422, '/errores/codigo-invalido'), true
    v.contrasena = String(nueva)
    // Revoca todas las entradas de la cuenta (decisión 86) y avisa por el otro canal.
    for (const [id, r] of refrescos) if (r.email === email) refrescos.delete(id)
    console.info(`[doble · envío simulado] aviso → ${email}: cambiaron tu contraseña`)
    return sinCuerpo(res, 204), true
  }

  if (!ruta.startsWith('/v1/grupos') && !ruta.startsWith('/v1/personas-cuidadas') && !ruta.startsWith('/v1/cuenta')) return false

  const u = usuarioDe(req)
  if (!u) return problema(res, req.headers.authorization ? 401 : 401, req.headers.authorization ? '/errores/token-invalido' : '/errores/no-autenticado'), true

  // ------------------------------------------------ MATU-57: la cuenta y el celular
  if (metodo === 'GET' && ruta === '/v1/cuenta') {
    res.setHeader('Cache-Control', 'no-store')
    const vista = { id: u.id, nombre: u.nombre, email: u.email, celular_enmascarado: enmascarar(u.telefono), celular_verificado: u.celularVerificado, celular_canal: u.canal }
    return json(res, 200, vista), true
  }
  if (metodo === 'POST' && ruta === '/v1/cuenta/celular/codigo') {
    if (u.celularVerificado) return problema(res, 409, '/errores/celular-verificado'), true
    if (!u.telefono) return problema(res, 409, '/errores/sin-celular'), true
    if (u.modo === 'celular-espera') return res.setHeader('Retry-After', '120'), problema(res, 429, '/errores/demasiadas-peticiones'), true
    const clave = `celular:${u.email}`
    const espera = 60_000 - (Date.now() - (ultimoEnvio.get(clave) ?? 0))
    if (espera > 0) return res.setHeader('Retry-After', String(Math.ceil(espera / 1000))), problema(res, 429, '/errores/demasiadas-peticiones'), true
    enviarCodigo(clave, enmascarar(u.telefono) ?? '', 'mensaje')
    return sinCuerpo(res, 202), true
  }
  if (metodo === 'POST' && ruta === '/v1/cuenta/celular/verificar') {
    const canal = cuerpo?.canal ?? 'sms'
    if (typeof cuerpo?.codigo !== 'string' || !/^[0-9]{6}$/.test(cuerpo.codigo) || (canal !== 'sms' && canal !== 'whatsapp'))
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'codigo', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_pattern_mismatch' }] }), true
    const c = codigos.get(`celular:${u.email}`)
    if (c && c.intentos >= 5) return res.setHeader('Retry-After', '600'), problema(res, 429, '/errores/demasiadas-peticiones'), true
    if (!probarCodigo(`celular:${u.email}`, cuerpo.codigo)) return problema(res, 422, '/errores/codigo-invalido'), true
    u.celularVerificado = true
    u.canal = canal
    return sinCuerpo(res, 204), true
  }

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

  // MATU-36: el consumo y su autorización.
  const mConsumo = /^\/v1\/personas-cuidadas\/([^/]+)\/(?:consumo|consentimientos)(?:\/|$)/.exec(ruta)
  if (mConsumo) {
    const pc = g?.personas.find((x) => x.id === decodeURIComponent(mConsumo[1]))
    if (!g || !pc) return problema(res, 404, '/errores/no-encontrado'), true
    return atenderConsumo(req, res, cuerpo, { rol: g.rol, consumo: pc.consumo, usuario: u }, r), true
  }

  // MATU-45: GET …/plan/aperturas, paginado con un cursor opaco (aquí, la posición en base64url).
  const mAperturas = /^\/v1\/personas-cuidadas\/([^/]+)\/plan\/aperturas$/.exec(ruta)
  if (mAperturas && metodo === 'GET') {
    const pa = g?.personas.find((x) => x.id === decodeURIComponent(mAperturas[1]))
    const puede = g && (g.rol === 'admin' || g.rol === 'cuidador' || (g.rol === 'pagador' && g.puede_ver_plan))
    if (!pa || !puede) return problema(res, 404, '/errores/no-encontrado'), true
    const q = new URL(req.url ?? '', 'http://doble').searchParams
    const limite = Number(q.get('limite') ?? '20')
    if (!Number.isInteger(limite) || limite < 1 || limite > 100)
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'limite', mensaje: 'MENSAJE DEL DOBLE', tipo: 'value_error' }] }), true
    const cursor = q.get('cursor')
    const desde = cursor ? Number(Buffer.from(cursor, 'base64url').toString('utf8')) : 0
    if (!Number.isInteger(desde) || desde < 0 || desde > pa.aperturas.length)
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'cursor', mensaje: 'MENSAJE DEL DOBLE', tipo: 'cursor_invalido' }] }), true
    // Cuenta «aperturas-falla»: «Ver aperturas anteriores» responde 500.
    if (u.modo === 'aperturas-falla' && desde > 0) return problema(res, 500, '/errores/error-interno'), true
    const hasta = desde + limite
    res.setHeader('Cache-Control', 'no-store')
    const siguiente = hasta < pa.aperturas.length ? Buffer.from(String(hasta)).toString('base64url') : null
    return json(res, 200, { items: pa.aperturas.slice(desde, hasta), siguiente_cursor: siguiente }), true
  }

  // MATU-50: PUT y DELETE …/plan/secciones/{seccion} (ficha-ampliada.openapi.yaml).
  const mSeccion = /^\/v1\/personas-cuidadas\/([^/]+)\/plan\/secciones\/([a-z_]+)$/.exec(ruta)
  if (mSeccion) return atenderSeccion(req, res, cuerpo, r, u, g, decodeURIComponent(mSeccion[1]), mSeccion[2]), true

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
        secciones: Object.fromEntries(SECCIONES.flatMap((s) => (p.secciones[s] ? [[s, vistaCampo(p.secciones[s]!)]] : []))),
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

// ---------------------------------------------------------------- secciones complementarias (MATU-50)

const seccionesHechas = new Set<string>()

/**
 * `PUT` y `DELETE …/plan/secciones/{seccion}`, con el orden de evaluación del contrato: alcance
 * (404), consentimiento (403), precondición (428/422), validación (422) y versión (412).
 * Cuenta «conflicto-secciones»: la primera escritura de cada sección choca con Rodrigo, que la
 * cambió (o la agregó), salvo «Moverse y descansar», que Rodrigo quitó (412 con `actual: null`).
 * Cuenta «defectos-secciones»: «Quién es» 428, «Lo que le hace bien» 422 largo_maximo, otra 500.
 */
function atenderSeccion(
  req: IncomingMessage,
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  { json, problema }: Responder,
  u: Usuario,
  g: Grupo | undefined,
  personaId: string,
  nombre: string,
) {
  const metodo = req.method ?? 'GET'
  const p = g?.personas.find((x) => x.id === personaId)
  if (!g || !p || !(SECCIONES as string[]).includes(nombre) || (metodo !== 'PUT' && metodo !== 'DELETE')) return problema(res, 404, '/errores/no-encontrado')
  const seccion = nombre as SeccionApi
  if (g.rol !== 'admin' && g.rol !== 'cuidador') return problema(res, 404, '/errores/no-encontrado')
  if (u.modo === 'sin-consentimiento') return problema(res, 403, '/errores/sin-consentimiento')
  if (u.modo === 'revision-vencida' || u.modo === 'revision-al-guardar') return problema(res, 403, '/errores/revision-vencida')
  if (u.modo === 'defectos-secciones') {
    if (seccion === 'quien_es') return problema(res, 428, '/errores/falta-version')
    if (seccion === 'preferencias')
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'texto', mensaje: 'MENSAJE DEL DOBLE', tipo: 'largo_maximo' }] })
    return problema(res, 500, '/errores/error-interno')
  }

  const ifMatch = req.headers['if-match']
  const ifNone = req.headers['if-none-match']
  const clave = `${p.id}-${seccion}`
  if (u.modo === 'conflicto-secciones' && !seccionesHechas.has(clave)) {
    seccionesHechas.add(clave)
    if (seccion === 'movilidad') delete p.secciones[seccion]
    else {
      const antes = p.secciones[seccion]
      p.secciones[seccion] = {
        texto: antes ? `${antes.texto}\nLos domingos almuerza con nosotros.` : 'Lo agregué yo recién, revísalo.',
        version: (antes?.version ?? 0) + 1,
        autor: RODRIGO,
        en: hace(1),
      }
    }
  }
  const actual = p.secciones[seccion]
  const etag = actual ? `"v${actual.version}"` : null
  const conflicto = () => {
    if (etag) res.setHeader('ETag', etag)
    res.setHeader('Cache-Control', 'no-store')
    return problema(res, 412, '/errores/version-desactualizada', { actual: actual ? vistaCampo(actual) : null })
  }

  if (metodo === 'DELETE') {
    if (ifNone) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'If-None-Match', mensaje: 'MENSAJE DEL DOBLE', tipo: 'precondicion_invalida' }] })
    if (!ifMatch || ifMatch === '*') return problema(res, 428, '/errores/falta-version')
    if (!actual || ifMatch !== etag) return conflicto()
    delete p.secciones[seccion]
    res.statusCode = 204
    return res.end()
  }

  // Como el backend real: el 422 del cuerpo va antes del 428 de la versión.
  const texto = typeof cuerpo?.texto === 'string' ? cuerpo.texto.trim() : ''
  if (!texto) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'texto', mensaje: 'MENSAJE DEL DOBLE', tipo: 'vacio' }] })
  if ([...texto].length > topeSeccion(seccion)) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'texto', mensaje: 'MENSAJE DEL DOBLE', tipo: 'largo_maximo' }] })
  if (ifMatch && ifNone) return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'If-Match', mensaje: 'MENSAJE DEL DOBLE', tipo: 'precondicion_doble' }] })
  if ((!ifMatch && !ifNone) || ifMatch === '*') return problema(res, 428, '/errores/falta-version')
  if (ifNone && ifNone !== '*') return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'If-None-Match', mensaje: 'MENSAJE DEL DOBLE', tipo: 'precondicion_invalida' }] })
  if (ifNone ? !!actual : ifMatch !== etag) return conflicto()
  const nuevo: Campo = { texto, version: (actual?.version ?? 0) + 1, autor: { id: u.id, nombre: u.nombre }, en: new Date().toISOString() }
  p.secciones[seccion] = nuevo
  res.setHeader('ETag', `"v${nuevo.version}"`)
  res.setHeader('Cache-Control', 'no-store')
  return json(res, actual ? 200 : 201, { seccion, texto: nuevo.texto, etag: `"v${nuevo.version}"`, actualizado_por: nuevo.autor, actualizado_en: nuevo.en })
}

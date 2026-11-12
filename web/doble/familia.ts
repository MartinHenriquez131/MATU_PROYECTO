// Doble del contrato de la app de la familia (docs/api/openapi.json) para desarrollo: cuentas,
// entrada con la cookie del refresh, grupos, personas y la ficha con ETag, 412 y 428. Igual que el
// doble del relevo, responde por HTTP de verdad y no entra al build. Datos sintéticos: Carmen cuida
// a María, Rodrigo es su hijo; los teléfonos usan la serie 5555, que no se asigna.
import { randomBytes, randomInt, randomUUID } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'

import { catalogoDoble } from './catalogo'
import { atenderConsumo, crearAlertas, listaCompleta, listaParaCompre, listaParaEnvases, listaParaLista, perfil, type ConsumoDoble } from './consumo'
import { CONTRASENA_DE_EJEMPLO, CORREO_POLITICA_CAMBIO, DOMINIO_NO_PERMITIDO } from './cuentas'
import {
  atenderPedido,
  atenderRetorno,
  otorgarDespacho,
  productoDelCatalogo,
  retirarDespacho,
  sembrarDespacho,
  sembrarPagado,
  sembrarPagoEnCurso,
  sembrarPedido,
  tieneDespacho,
  vistaDespacho,
} from './pedido'
import { aceptacionVigente, HUELLA, politicaPublicada } from './politica'
import { atenderGrupo, atenderInvitacionPublica, invitacionPendiente, miembro, type InvitacionDoble, type MiembroDoble } from './grupo'
import { alEntrar, alSalir, anotarCuenta, atenderDispositivos, dispositivoVivo, usoDe } from './dispositivos'

type Rol = 'admin' | 'cuidador' | 'pagador' | 'observador'
type CampoApi = 'rutina' | 'manejo_situaciones' | 'red_apoyo'
/** Las seis secciones complementarias (MATU-50, docs/api/propuestos/ficha-ampliada.openapi.yaml). */
type SeccionApi = 'quien_es' | 'preferencias' | 'alimentacion' | 'movilidad' | 'comunicacion' | 'remedios'
const SECCIONES: SeccionApi[] = ['quien_es', 'preferencias', 'alimentacion', 'movilidad', 'comunicacion', 'remedios']
/** MATU-42 (decisión 309): quien ya no está en el grupo llega con `nombre: null`. */
type AutorDoble = { id: string; nombre: string | null }
interface Campo {
  texto: string | null
  version: number
  autor: AutorDoble | null
  en: string | null
}
/** `AutorVista`, `AutorAccesoVista` y `AutorPerfilVista`: `autor_activo` es `false` si ya no está. */
export const autorVista = (a: AutorDoble | null) => (a ? { id: a.id, nombre: a.nombre, autor_activo: a.nombre !== null } : null)
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
  /** Los enlaces de relevo (MATU-48), del más nuevo al más antiguo. */
  accesos: Acceso[]
  /** MATU-44: cuándo se otorgó cada autorización y, si se retiró, cuándo y cuándo se borra lo guardado. */
  autorizaciones: Record<Finalidad, { otorgado_en: string; retiro: Retiro | null }>
  /** MATU-42 (decisión 311): quien registró las autorizaciones ya no está en el grupo. */
  autorizoQuienYaNoEsta?: boolean
}
type Finalidad = 'plan_cuidado' | 'consumo'
interface Retiro {
  revocado_en: string
  borrado_en: string
}
type Motivo = 'salgo_unas_horas' | 'fin_de_semana_fuera' | 'turno_de_noche' | 'otro'
interface Acceso {
  id: string
  nombre_relevo: string
  /** `null` cuando ya se borró, a los 30 días del vencimiento o del corte (decisión 25). */
  telefono_relevo: string | null
  campos: CampoApi[]
  secciones_adicionales: SeccionApi[]
  motivo: Motivo
  creado_en: string
  expira_en: string
  revocado_en: string | null
  bloqueado: boolean
  usos: number
  otorgado_por: AutorDoble | null
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
  /** MATU-42: quiénes forman el grupo. Sin definir, grupo.ts los arma al pedirlos. */
  miembros?: MiembroDoble[]
  /** MATU-42: las invitaciones sin usar (pendientes o bloqueadas). */
  invitaciones?: InvitacionDoble[]
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
  /** MATU-75: la última política que aceptó, o `null` si la cuenta no tiene registro (decisión 179). */
  politica: { version: string; huella: string; aceptada_en: string } | null
}


// ---------------------------------------------------------------- datos sintéticos

const RODRIGO = { id: randomUUID(), nombre: 'Rodrigo' }
const hace = (min: number) => new Date(Date.now() - min * 60_000).toISOString()
const vacio = (): Campo => ({ texto: null, version: 0, autor: null, en: null })
const escrito = (texto: string, autor: AutorDoble, min = 42): Campo => ({ texto, version: 1, autor, en: hace(min) })

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
    accesos: [],
    autorizaciones: { plan_cuidado: { otorgado_en: hace(60 * 24 * 2), retiro: null }, consumo: { otorgado_en: hace(60 * 24), retiro: null } },
  }
}

const NOVENTA_DIAS = 90 * 24 * 60
/** MATU-44: la finalidad se retiró hace `min` minutos; lo guardado se borra 90 días después. */
function conRetiro(p: Persona, finalidad: Finalidad, min: number) {
  p.autorizaciones[finalidad].retiro = { revocado_en: hace(min), borrado_en: en(NOVENTA_DIAS - min) }
  if (finalidad === 'plan_cuidado') for (const a of p.accesos) if (!a.revocado_en && new Date(a.expira_en).getTime() > Date.now()) a.revocado_en = hace(min)
  if (finalidad === 'consumo') p.consumo.autorizacion = 'no'
  return p
}

const DIA = 24 * 60
/** Una línea de apertura `min` minutos atrás. */
const linea = (acceso: { id: string; nombre_relevo: string }, tipo: TipoApertura, min: number): Apertura => ({ ocurrido_en: hace(min), tipo, acceso })

/**
 * Las aperturas de María (MATU-45): los cuatro tipos, una presentación sin apertura (Carla), un
 * bloqueo (Pedro), varios días (hoy, ayer, hace 3 días y desde hace 10) y 27 líneas, para la paginación.
 */
const TRES: CampoApi[] = ['rutina', 'manejo_situaciones', 'red_apoyo']
const en = (min: number) => new Date(Date.now() + min * 60_000).toISOString()
/** Un enlace de ejemplo: creado `creado` minutos atrás y que vence `vence` minutos desde ahora (negativo = ya venció). */
function acceso(
  id: { id: string; nombre_relevo: string },
  telefono: string | null,
  creado: number,
  vence: number,
  extra: Partial<Acceso> = {},
): Acceso {
  return {
    id: id.id,
    nombre_relevo: id.nombre_relevo,
    telefono_relevo: telefono,
    campos: TRES,
    secciones_adicionales: [],
    motivo: 'salgo_unas_horas',
    creado_en: hace(creado),
    expira_en: en(vence),
    revocado_en: null,
    bloqueado: false,
    usos: 0,
    otorgado_por: { id: randomUUID(), nombre: 'Carmen' },
    ...extra,
  }
}

function aperturasDeEjemplo(): { aperturas: Apertura[]; accesos: Acceso[] } {
  const rosa = { id: randomUUID(), nombre_relevo: 'Rosa' }
  const carla = { id: randomUUID(), nombre_relevo: 'Carla' }
  const pedro = { id: randomUUID(), nombre_relevo: 'Pedro' }
  const rosaAntes = { id: randomUUID(), nombre_relevo: 'Rosa' }
  const tomas = { id: randomUUID(), nombre_relevo: 'Tomás' }
  // MATU-48: los enlaces de esas aperturas. Rosa y Carla abren ahora; Pedro se bloqueó; Tomás lo
  // cortaron; el enlace anterior de Rosa venció hace más de 30 días y su teléfono ya se borró.
  const accesos: Acceso[] = [
    acceso(rosa, '+56955550137', 30, 23 * 60 - 30),
    acceso(carla, '+56955550152', DIA + 125, 3 * DIA, { motivo: 'fin_de_semana_fuera', otorgado_por: { id: RODRIGO.id, nombre: 'Rodrigo' } }),
    acceso(tomas, '+56955550160', 5 * DIA, -4 * DIA, { motivo: 'turno_de_noche', revocado_en: hace(4 * DIA + 200) }),
    acceso(pedro, '+56955550175', 3 * DIA + 10, 2 * DIA, { bloqueado: true, motivo: 'otro' }),
    acceso(rosaAntes, null, 50 * DIA, -35 * DIA, { campos: ['rutina', 'red_apoyo'] }),
  ]
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
  return { aperturas: lista, accesos }
}
const conAperturas = (p: Persona) => {
  const { aperturas, accesos } = aperturasDeEjemplo()
  p.aperturas = aperturas
  p.accesos = accesos
  return p
}

/** Un activo y 25 que ya no abren, para «Ver enlaces anteriores» (dos páginas de 20). */
function conMuchosEnlaces(p: Persona) {
  const nombres = ['Rosa', 'Carla', 'Tomás', 'Pedro', 'Javiera', 'Luis']
  p.accesos = [acceso({ id: randomUUID(), nombre_relevo: 'Rosa' }, '+56955550137', 60, 20 * 60)]
  for (let i = 0; i < 25; i++) {
    const id = { id: randomUUID(), nombre_relevo: nombres[i % nombres.length] }
    const creado = (i + 2) * DIA
    p.accesos.push(acceso(id, i < 20 ? '+56955550190' : null, creado, -creado + DIA, i % 3 === 0 ? { revocado_en: hace(creado - 120) } : {}))
  }
  return p
}

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

/** MATU-75: cuándo aceptaron la política las cuentas de ejemplo (09/11/2026, 12:00 de Chile). */
const ACEPTADA_EN_EJEMPLO = '2026-11-09T15:00:00Z'
/** Los correos que ya vieron su 409 `politica-cambio`: el segundo intento crea la cuenta. */
const politicaCambiada = new Set<string>()

/** `Retry-After` del 429 por IP al crear la cuenta, por correo; `null` = sin la cabecera. */
const ESPERA_IP_CREAR_CUENTA: Record<string, string | null> = {
  'espera-ip@example.com': '61',
  'espera-ip-60@example.com': '60',
  'espera-ip-sin-cabecera@example.com': null,
}

function cuenta(email: string, nombre: string, grupos: Grupo[], modo?: string): Usuario {
  // Como la semilla de la demo (decisión 181), las cuentas de ejemplo aceptaron la política vigente.
  const politica = aceptacionVigente(ACEPTADA_EN_EJEMPLO)
  const u: Usuario = { id: randomUUID(), nombre, email, contrasena: CONTRASENA_DE_EJEMPLO, grupos, modo, telefono: '+56955550137', celularVerificado: false, canal: 'sms', politica }
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
  const carmen = cuenta('carmen@example.com', 'Carmen', [])
  const yo = { id: carmen.id, nombre: 'Carmen' }
  carmen.grupos.push(grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }))]))
  insumos(carmen, 'vigente', true)
  cuenta('completa@example.com', 'Carmen', [
    grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo), manejo_situaciones: escrito(SI_SE_ALTERA, RODRIGO, 5), red_apoyo: escrito(A_QUIEN, yo, 3) }))]),
  ])
  cuenta('vacia@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])])
  cuenta('dos-grupos@example.com', 'Carmen', [
    grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }), persona('Juan Soto', 'Juan')]),
    grupo('Familia Pérez', 'cuidador', [persona('Elena Pérez', 'Elena')]),
  ])
  cuenta('sin-persona@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [])])
  cuenta('sin-persona-pagador@example.com', 'Rodrigo', [grupo('Familia Soto', 'pagador', [])])
  insumos(cuenta('pagador@example.com', 'Rodrigo', [grupo('Familia Soto', 'pagador', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })])]), 'vigente', true)
  cuenta('pagador-ve@example.com', 'Rodrigo', [grupo('Familia Soto', 'pagador', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }))], true)])
  cuenta('observador@example.com', 'Rodrigo', [grupo('Familia Soto', 'observador', [conAperturas(persona('María Soto', 'María'))])])
  cuenta('cuidador@example.com', 'Javiera', [grupo('Familia Soto', 'cuidador', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }))])])
  cuenta('aperturas-falla@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }))])], 'aperturas-falla')
  cuenta('sin-autorizacion@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conRetiro(persona('María Soto', 'María'), 'plan_cuidado', 60)])])
  cuenta('renovar-autorizacion@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', {}, 'cuidador_de_hecho')])], 'revision-vencida')
  cuenta('revision-al-guardar@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'revision-al-guardar')
  cuenta('conflicto@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })])], 'conflicto')
  cuenta('defectos@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'defectos')
  cuenta('vence@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'vence')
  insumos(cuenta('lento@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }))])], 'lento'), 'vigente', true)
  // MATU-36: insumos
  cuenta('insumos-permiso@example.com', 'Carmen', [grupo('Familia Soto', 'cuidador', [persona('María Soto', 'María')])])
  insumos(cuenta('insumos-vacio@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])]), 'vigente', false)
  insumos(cuenta('insumos-observador@example.com', 'Rodrigo', [grupo('Familia Soto', 'observador', [persona('María Soto', 'María')])]), 'vigente', true)
  insumos(cuenta('insumos-renovar@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', {}, 'cuidador_de_hecho')])]), 'vencida', true)
  insumos(cuenta('insumos-renovar-observador@example.com', 'Rodrigo', [grupo('Familia Soto', 'observador', [persona('María Soto', 'María')])]), 'vencida', true)
  // MATU-37: «Se acaban pronto»
  insumos(cuenta('alertas@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])]), 'vigente', true)
  {
    const u = cuenta('alertas-sin@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])])
    const c = insumos(u, 'vigente', false)
    const yo = { id: u.id, nombre: u.nombre }
    c.perfiles = [perfil('Pañal adulto talla M', 'unidad', 4, 1, 120, 0, yo), perfil('Toallitas húmedas', 'unidad', 3, 1, 90, 1, yo), perfil('Champú en sobre', 'sobre', 1, 1, 30, 0, yo)]
    crearAlertas(c)
  }
  {
    // Recalculo en 0: usa 4 al día y no queda nada; comprar 1 a 3 deja «Alcanza para 0 días».
    const u = cuenta('alertas-cero@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])])
    const c = insumos(u, 'vigente', false)
    const yo = { id: u.id, nombre: u.nombre }
    c.perfiles = [perfil('Pañal adulto talla M', 'unidad', 4, 1, 0, 0, yo)]
    crearAlertas(c)
  }
  insumos(cuenta('alertas-observador@example.com', 'Rodrigo', [grupo('Familia Soto', 'observador', [persona('María Soto', 'María')])]), 'vigente', true)
  insumos(cuenta('alertas-cerrada@example.com', 'Carmen', [grupo('Familia Soto', 'cuidador', [persona('María Soto', 'María')])], 'alertas-cerrada'), 'vigente', true)
  insumos(cuenta('alertas-conflicto@example.com', 'Carmen', [grupo('Familia Soto', 'cuidador', [persona('María Soto', 'María')])], 'alertas-conflicto'), 'vigente', true)
  insumos(cuenta('alertas-error@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'alertas-error'), 'vigente', true)
  insumos(cuenta('alertas-error-carga@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'alertas-error-carga'), 'vigente', true)
  insumos(cuenta('insumos-defectos@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María')])], 'insumos-defectos'), 'vigente', true)
  // MATU-60: la lista de insumos, una cuenta por estado y por rol.
  const conLista = (u: Usuario, autorizacion: ConsumoDoble['autorizacion'] = 'vigente', soloFuera = false) => {
    const c = insumos(u, autorizacion, false)
    c.perfiles = listaParaLista({ id: u.id, nombre: u.nombre }).filter((p) => !soloFuera || p.nombre_libre.startsWith('Bolsas'))
    crearAlertas(c)
  }
  const sotoLista = (rol: Rol, cuidadorDeHecho = false) => [grupo('Familia Soto', rol, [persona('María Soto', 'María', {}, cuidadorDeHecho ? 'cuidador_de_hecho' : undefined)])]
  conLista(cuenta('lista@example.com', 'Carmen', sotoLista('admin')))
  conLista(cuenta('lista-cuidador@example.com', 'Javiera', sotoLista('cuidador')))
  conLista(cuenta('lista-pagador@example.com', 'Rodrigo', sotoLista('pagador')))
  conLista(cuenta('lista-observador@example.com', 'Rodrigo', sotoLista('observador')))
  conLista(cuenta('lista-vacia@example.com', 'Carmen', sotoLista('admin')), 'vigente', true)
  conLista(cuenta('lista-permiso-cuidador@example.com', 'Javiera', sotoLista('cuidador')), 'no')
  conLista(cuenta('lista-permiso-observador@example.com', 'Rodrigo', sotoLista('observador')), 'no')
  conLista(cuenta('lista-renovar@example.com', 'Carmen', sotoLista('admin', true)), 'vencida')
  conLista(cuenta('lista-error@example.com', 'Carmen', sotoLista('admin'), 'lista-error'))
  // MATU-51: «Compré» y «Me quedan», una cuenta por estado y por rol (especificación 10).
  const conCompre = (u: Usuario) => {
    const c = insumos(u, 'vigente', false)
    c.perfiles = listaParaCompre({ id: u.id, nombre: u.nombre })
    crearAlertas(c)
  }
  conCompre(cuenta('compre@example.com', 'Carmen', sotoLista('admin')))
  conCompre(cuenta('compre-cuidador@example.com', 'Javiera', sotoLista('cuidador')))
  conCompre(cuenta('compre-pagador@example.com', 'Rodrigo', sotoLista('pagador')))
  conCompre(cuenta('compre-observador@example.com', 'Rodrigo', sotoLista('observador')))
  conCompre(cuenta('compre-defectos@example.com', 'Carmen', sotoLista('admin'), 'compre-defectos'))
  conCompre(cuenta('compre-renovar@example.com', 'Carmen', sotoLista('admin', true), 'compre-renovar'))
  conCompre(cuenta('compre-lento@example.com', 'Carmen', sotoLista('admin'), 'lento'))
  // MATU-84: «Me quedan» y el formulario en envases (especificación 13).
  const conEnvases = (u: Usuario) => {
    const c = insumos(u, 'vigente', false)
    c.perfiles = listaParaEnvases({ id: u.id, nombre: u.nombre })
    crearAlertas(c)
  }
  conEnvases(cuenta('envases@example.com', 'Carmen', sotoLista('admin')))
  conEnvases(cuenta('envases-defectos@example.com', 'Carmen', sotoLista('admin'), 'envases-defectos'))
  conEnvases(cuenta('envases-lento@example.com', 'Carmen', sotoLista('admin'), 'lento'))
  // MATU-50: las secciones complementarias, una cuenta por estado.
  const completos = () => ({ rutina: escrito(SU_DIA, yo), manejo_situaciones: escrito(SI_SE_ALTERA, RODRIGO, 5), red_apoyo: escrito(A_QUIEN, yo, 3) })
  cuenta('secciones-ninguna@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', completos())])])
  cuenta('secciones-algunas@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conSecciones(persona('María Soto', 'María', completos()), yo, ['quien_es', 'comunicacion'])])])
  cuenta('secciones-remedios@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conSecciones(persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) }), yo, ['preferencias', 'remedios'])])])
  cuenta('secciones-todas@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conSecciones(persona('María Soto', 'María', completos()), yo, SECCIONES)])])
  cuenta('secciones-conflicto@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conSecciones(persona('María Soto', 'María', completos()), yo, ['quien_es', 'alimentacion', 'movilidad'])])], 'conflicto-secciones')
  cuenta('secciones-defectos@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conSecciones(persona('María Soto', 'María', completos()), yo, ['quien_es', 'preferencias'])])], 'defectos-secciones')
  cuenta('secciones-pagador@example.com', 'Rodrigo', [grupo('Familia Soto', 'pagador', [conSecciones(persona('María Soto', 'María', completos()), yo, ['quien_es', 'remedios'])], true)])
  cuenta('secciones-largas@example.com', 'Bernardita', [
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
  // MATU-48: compartir y cortar, una cuenta por estado.
  const conTodas = () => conSecciones(persona('María Soto', 'María', completos()), yo, ['quien_es', 'comunicacion', 'remedios'])
  cuenta('enlaces-pausa@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', {}, 'cuidador_de_hecho'))])], 'revision-vencida')
  cuenta('enlaces-muchos@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conMuchosEnlaces(conTodas())])])
  // MATU-44: retirar y volver a autorizar, una cuenta por estado y por rol.
  {
    const u = cuenta('retirar@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', completos()))])])
    insumos(u, 'vigente', true)
  }
  {
    const p = conAperturas(persona('María Soto', 'María', completos()))
    const u = cuenta('retirada@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [p])])
    insumos(u, 'vigente', true)
    conRetiro(conRetiro(p, 'plan_cuidado', 2 * DIA), 'consumo', 2 * DIA)
  }
  const estados = (u: Usuario) => {
    // María: la ficha por renovar (la cuenta) y los insumos sin autorizar. Juan: las dos retiradas.
    // Elena: las dos retiradas hace más de 90 días, ya borradas.
    const [maria, juan, elena] = u.grupos[0].personas
    maria.autorizaciones.plan_cuidado.otorgado_en = hace(365 * DIA + 30 * DIA)
    maria.accesos = aperturasDeEjemplo().accesos
    juan.accesos = aperturasDeEjemplo().accesos
    juan.consumo = { autorizacion: 'vigente', perfiles: listaCompleta({ id: u.id, nombre: u.nombre }) }
    conRetiro(conRetiro(juan, 'plan_cuidado', 3 * DIA), 'consumo', DIA)
    elena.consumo = { autorizacion: 'vigente', perfiles: listaCompleta({ id: u.id, nombre: u.nombre }) }
    conRetiro(conRetiro(elena, 'plan_cuidado', 100 * DIA), 'consumo', 95 * DIA)
    return u
  }
  const tres = (rol: Rol) => [
    grupo('Familia Soto', rol, [persona('María Soto', 'María', completos(), 'cuidador_de_hecho'), persona('Juan Soto', 'Juan', completos()), persona('Elena Soto', 'Elena', completos())], rol === 'pagador'),
  ]
  {
    // P8 sin el modo de toda la cuenta: la ficha de María se retiró hace 100 días y ya se borró.
    // Al volver a autorizar empieza en blanco, en 0 de 3 (decisión 130).
    // Todo lo de los relevos pasó antes del corte: las aperturas y los enlaces se corren 101 días
    // atrás, y los que todavía abrían el día del retiro quedan cortados ese día.
    const p = conAperturas(persona('María Soto', 'María', completos()))
    conSecciones(p, yo, ['quien_es', 'comunicacion'])
    const antes = (iso: string) => new Date(new Date(iso).getTime() - 101 * DIA * 60_000).toISOString()
    p.aperturas = p.aperturas.map((x) => ({ ...x, ocurrido_en: antes(x.ocurrido_en) }))
    p.accesos = p.accesos.map((x) => ({ ...x, creado_en: antes(x.creado_en), expira_en: antes(x.expira_en), revocado_en: x.revocado_en && antes(x.revocado_en) }))
    conRetiro(p, 'plan_cuidado', 100 * DIA)
    const corte = p.autorizaciones.plan_cuidado.retiro!.revocado_en
    for (const x of p.accesos) if (!x.revocado_en && x.expira_en > corte) x.revocado_en = corte
    insumos(cuenta('borrada@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [p])]), 'vigente', true)
  }
  estados(cuenta('grupo-estados@example.com', 'Carmen', tres('admin'), 'revision-vencida'))
  estados(cuenta('grupo-pagador@example.com', 'Rodrigo', tres('pagador'), 'revision-vencida'))
  estados(cuenta('grupo-observador@example.com', 'Rodrigo', tres('observador'), 'revision-vencida'))
  for (const [email, modo] of [['retiro-falla@example.com', 'retiro-falla'], ['retiro-otra@example.com', 'retiro-otra'], ['retiro-lento@example.com', 'lento']] as const) {
    const u = cuenta(email, 'Carmen', [grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', completos()))])], modo)
    insumos(u, 'vigente', true)
  }
  // MATU-59: el catálogo vacío, con error y con la capa 3 apagada (los demás roles lo ven con sus cuentas de siempre).
  for (const modo of ['catalogo-vacio', 'catalogo-falla', 'catalogo-apagado'] as const) insumos(cuenta(`${modo}@example.com`, 'Carmen', [grupo('Familia Soto', 'admin', [conAperturas(persona('María Soto', 'María', completos()))])], modo), 'vigente', true)
  cuenta('enlaces-cortar-falla@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conAperturas(conTodas())])], 'cortar-falla')
  cuenta('enlaces-lista-falla@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conAperturas(conTodas())])], 'lista-falla')
  cuenta('compartir-nombre@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conTodas()])], '422-nombre_relevo')
  cuenta('compartir-telefono@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conTodas()])], '422-telefono_relevo')
  cuenta('compartir-avise@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conTodas()])], '422-relevo_informado')
  cuenta('compartir-vence-pasada@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conTodas()])], '422-vigencia_pasada')
  cuenta('compartir-vence-maxima@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conTodas()])], '422-vigencia_maxima')
  cuenta('compartir-seccion@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conTodas()])], '422-seccion_no_agregada')
  cuenta('compartir-caido@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conTodas()])], 'compartir-503')
  cuenta('compartir-falla@example.com', 'Carmen', [grupo('Familia Soto', 'admin', [conTodas()])], 'compartir-500')
  cuenta(
    'largos@example.com',
    'Bernardita',
    [grupo('Familia Valenzuela Etchegaray', 'admin', [persona('Maximiliana de los Ángeles Valenzuela Etchegaray', 'Maximiliana', { manejo_situaciones: escrito('Extraordinariamente tranquila cuando le hablan de su pueblo. '.repeat(8).slice(0, 480), yo) })])],
  )
  // MATU-57
  const soto = () => [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })])]
  cuenta('celular-verificado@example.com', 'Carmen', soto()).celularVerificado = true
  cuenta('celular-sin-verificar@example.com', 'Carmen', soto())
  cuenta('celular-espera@example.com', 'Carmen', soto(), 'celular-espera')
  const anterior = cuenta('sin-celular@example.com', 'Carmen', soto())
  anterior.telefono = null
  anterior.politica = null
  // MATU-75: «Tu cuenta» con y sin la política aceptada.
  cuenta('politica-aceptada@example.com', 'Carmen', soto())
  cuenta('politica-sin-registro@example.com', 'Carmen', soto()).politica = null
  cuenta('recuperar-espera@example.com', 'Carmen', soto(), 'recuperar-espera')
  cuenta('codigo-invalido@example.com', 'Carmen', soto(), 'codigo-invalido')
  // MATU-61: el pedido, una cuenta por estado y por rol (especificación 17). María tiene dirección
  // salvo en «pedido-vacio» y «pedido-permiso»; la lista de «pedido-permiso» trae productos del catálogo.
  const DIRECCION = { etiqueta: 'Casa', calle: 'Los Aromos', numero: '123', depto: '4', comuna: 'La Reina', region: 'Metropolitana', referencia: 'Portón verde', etag: '"v1"' }
  const conPedido = (email: string, nombre: string, rol: Rol, despacho: Parameters<typeof sembrarDespacho>[1], modo?: string, conDireccion = true) => {
    const u = cuenta(email, nombre, sotoLista(rol), modo)
    u.celularVerificado = true
    const p = u.grupos[0].personas[0]
    if (conDireccion) p.direccion = { ...DIRECCION }
    sembrarDespacho(p.id, despacho)
    return { u, p }
  }
  // MATU-94 (decisión 251): la capa 3 apagada con una autorización de pedidos de cuando estaba encendida
  // y la dirección guardada (C8: se ve y se vacía también así).
  conPedido('catalogo-apagado-despacho@example.com', 'Carmen', 'admin', 'vigente', 'catalogo-apagado-despacho')
  conPedido('catalogo-apagado-retirado@example.com', 'Carmen', 'admin', 'retirada', 'catalogo-apagado-retirado')
  const tresProductos: [string, number][] = [['Pañal adulto M', 2], ['Protectores diarios', 1], ['Toallitas húmedas', 3]]
  sembrarPedido(conPedido('pedido@example.com', 'Carmen', 'admin', 'vigente').p.id, tresProductos)
  sembrarPedido(conPedido('pedido-cuidador@example.com', 'Javiera', 'cuidador', 'vigente').p.id, tresProductos)
  conPedido('pedido-vacio@example.com', 'Carmen', 'admin', 'vigente', undefined, false)
  {
    const { u } = conPedido('pedido-permiso@example.com', 'Javiera', 'cuidador', 'no', undefined, false)
    const c = insumos(u, 'vigente', false)
    c.perfiles = listaParaLista({ id: u.id, nombre: u.nombre }).map((x) => ({
      ...x,
      producto_id: x.nombre_libre.startsWith('Pañal') ? productoDelCatalogo('Pañal adulto M') : x.nombre_libre === 'Toallitas húmedas' ? productoDelCatalogo('Toallitas húmedas') : null,
    }))
    crearAlertas(c)
  }
  sembrarPedido(conPedido('pedido-renovar@example.com', 'Carmen', 'admin', 'vencida').p.id, tresProductos)
  sembrarPedido(conPedido('pedido-pagador@example.com', 'Rodrigo', 'pagador', 'vigente').p.id, tresProductos, true)
  sembrarPedido(conPedido('pedido-observador@example.com', 'Rodrigo', 'observador', 'vigente').p.id, tresProductos)
  conPedido('pedido-observador-sin@example.com', 'Rodrigo', 'observador', 'no')
  sembrarPedido(conPedido('pedido-cambios@example.com', 'Carmen', 'admin', 'vigente', 'pedido-cambios').p.id, tresProductos)
  sembrarPedido(conPedido('pedido-plazo@example.com', 'Carmen', 'admin', 'vigente', 'pedido-plazo').p.id, tresProductos)
  sembrarPedido(conPedido('pedido-conflicto@example.com', 'Carmen', 'admin', 'vigente', 'pedido-conflicto').p.id, tresProductos)
  sembrarPedido(conPedido('pedido-falla@example.com', 'Carmen', 'admin', 'vigente', 'pedido-falla').p.id, tresProductos)
  conPedido('pedido-retirada@example.com', 'Carmen', 'admin', 'retirada')
  // MATU-62: el pago, una cuenta por estado y por rol. «Pagar» lleva a la página falsa de Webpay,
  // donde se elige el resultado (débito, crédito en cuotas, prepago, no aprobado, anular, tiempo
  // agotado, pendiente, tardío, anulado y sin sesión).
  sembrarPedido(conPedido('pago@example.com', 'Carmen', 'admin', 'vigente').p.id, tresProductos, true)
  sembrarPedido(conPedido('pago-pagador@example.com', 'Rodrigo', 'pagador', 'vigente').p.id, tresProductos, true)
  sembrarPedido(conPedido('pago-cuidador@example.com', 'Javiera', 'cuidador', 'vigente').p.id, tresProductos, true)
  sembrarPagoEnCurso(conPedido('pago-en-curso@example.com', 'Carmen', 'admin', 'vigente').p.id, tresProductos)
  sembrarPagoEnCurso(conPedido('pago-en-curso-cuidador@example.com', 'Javiera', 'cuidador', 'vigente').p.id, tresProductos)
  sembrarPagoEnCurso(conPedido('pago-en-curso-pagador@example.com', 'Rodrigo', 'pagador', 'vigente').p.id, tresProductos)
  for (const [email, modo] of [
    ['pago-webpay-caido@example.com', 'pago-webpay-caido'],
    ['pago-red@example.com', 'pago-red'],
    ['pago-vencido@example.com', 'pago-vencido'],
    ['pago-condiciones@example.com', 'pago-condiciones'],
    ['pago-409@example.com', 'pago-409-en-curso'],
  ] as const)
    sembrarPedido(conPedido(email, 'Carmen', 'admin', 'vigente', modo).p.id, tresProductos, true)
  {
    const { u, p } = conPedido('pago-pagado@example.com', 'Carmen', 'admin', 'vigente')
    sembrarPedido(p.id, [['Pañal adulto M', 1]])
    sembrarPagado(p.id, tresProductos, { quien: u.id })
  }
  sembrarPagado(conPedido('pago-pagado-otro@example.com', 'Carmen', 'admin', 'vigente').p.id, tresProductos, { quien: 'otra-cuenta', tarjeta: 'credito' })
  {
    const { u, p } = conPedido('pago-devoluciones@example.com', 'Carmen', 'admin', 'vigente')
    sembrarPagado(p.id, tresProductos, { quien: u.id, tarjeta: 'credito', devoluciones: true })
  }
  sembrarPagado(conPedido('pago-devoluciones-otro@example.com', 'Javiera', 'cuidador', 'vigente').p.id, tresProductos, { quien: 'otra-cuenta', devoluciones: true })
  {
    const { u, p } = conPedido('pago-prepago@example.com', 'Rodrigo', 'pagador', 'vigente')
    sembrarPagado(p.id, tresProductos, { quien: u.id, tarjeta: 'prepago' })
  }
  {
    const { u, p } = conPedido('pago-tardio@example.com', 'Carmen', 'admin', 'vigente')
    sembrarPagado(p.id, tresProductos, { quien: u.id, tardio: true })
  }
  sembrarPagado(conPedido('pago-observador@example.com', 'Rodrigo', 'observador', 'vigente').p.id, tresProductos, { quien: 'otra-cuenta' })
  // MATU-55: Dónde entraste y los avisos. Con carmen@ y las demás se ve la historia de ejemplo; cada una
  // la siembra la primera vez que entra (doble/dispositivos.ts).
  for (const [email, modo] of [
    ['ingresos-muchos@example.com', 'ingresos-muchos'],
    ['ingresos-vacio@example.com', 'ingresos-vacio'],
    ['donde-falla@example.com', 'donde-falla'],
    ['cerrar-falla@example.com', 'cerrar-falla'],
    ['avisos-falla@example.com', 'avisos-falla'],
    ['avisos-guardar-falla@example.com', 'avisos-guardar-falla'],
    ['push-sin-clave@example.com', 'push-sin-clave'],
  ])
    cuenta(email, 'Carmen', [grupo('Familia Soto', 'admin', [persona('María Soto', 'María', { rutina: escrito(SU_DIA, yo) })])], modo)
}
sembrar()

// ---------------------------------------------------------------- MATU-42: las cuentas del grupo

/** Las cuentas de MATU-42 y MATU-53 (cuentas.ts): una por rol y por estado. */
function sembrarMiembros() {
  const soto = (rol: Rol, puedeVer = false) => [grupo('Familia Soto', rol, [persona('María Soto', 'María', { rutina: escrito(SU_DIA, RODRIGO) })], puedeVer)]
  const conMiembros = (email: string, nombre: string, rol: Rol, lista: (yo: MiembroDoble) => MiembroDoble[], modo?: string, puedeVer = false) => {
    const u = cuenta(email, nombre, soto(rol, puedeVer), modo)
    const yo = miembro(`${nombre} Soto`, rol, 20, { eresTu: true, puede_ver_plan: rol === 'pagador' && puedeVer, enlaces: rol === 'admin' || rol === 'cuidador' ? 2 : 0 })
    u.grupos[0].miembros = lista(yo).sort((a, b) => a.unido_en.localeCompare(b.unido_en))
    insumos(u, 'vigente', true)
    return u
  }
  const familia = (yo: MiembroDoble) => [
    yo,
    miembro('Tomás Soto', 'admin', 18),
    miembro('Rodrigo Soto', 'pagador', 12),
    miembro('Rosa Pérez', 'cuidador', 2, { enlaces: 2 }),
    miembro('Pedro Soto', 'observador', 1),
  ]
  const sinTomas = (yo: MiembroDoble) => familia(yo).filter((m) => m.nombre !== 'Tomás Soto')
  // Saca a la persona de ejemplo con ese nombre, nunca a la fila propia (`yo` puede llamarse igual).
  const conCarmen = (yo: MiembroDoble, sin: string) => [miembro('Carmen Soto', 'admin', 30, { enlaces: 1 }), ...sinTomas(yo).filter((m) => m === yo || m.nombre !== sin)]
  const mia = () => invitacionPendiente('cuidador', { nombre: 'Carmen', eresTu: true })

  {
    // Admin con otra persona que administra («Cambiar tu rol»). Invitaciones: una suya, una bloqueada
    // de alguien que ya no está, y una que al anularla ya se usó (409 invitacion-cerrada).
    const u = conMiembros('miembros-admin@example.com', 'Carmen', 'admin', familia)
    u.grupos[0].invitaciones = [
      invitacionPendiente('observador', { nombre: 'Carmen', eresTu: true }),
      invitacionPendiente('cuidador', { nombre: null, eresTu: false }, { estado: 'bloqueada', creada_en: hace(3 * DIA) }),
      invitacionPendiente('pagador', { nombre: 'Tomás', eresTu: false }, { creada_en: hace(4 * DIA), cerrada: 'usada' }),
    ]
  }
  conMiembros('miembros-unico-admin@example.com', 'Carmen', 'admin', sinTomas)
  conMiembros('miembros-cuidador@example.com', 'Rosa', 'cuidador', (yo) => conCarmen(yo, 'Rosa Pérez'))
  conMiembros('miembros-pagador@example.com', 'Rodrigo', 'pagador', (yo) => conCarmen(yo, 'Rodrigo Soto'))
  conMiembros('miembros-pagador-ve@example.com', 'Rodrigo', 'pagador', (yo) => conCarmen(yo, 'Rodrigo Soto'), undefined, true)
  conMiembros('miembros-observador@example.com', 'Pedro', 'observador', (yo) => conCarmen(yo, 'Pedro Soto'))
  conMiembros('miembros-sola@example.com', 'Carmen', 'admin', (yo) => [yo])
  // 5.10 (v1.2): un grupo sin persona registrada, con Rodrigo que paga (dar la ficha) y Rosa (salir).
  conMiembros('miembros-sin-persona@example.com', 'Carmen', 'admin', (yo) => conCarmen(yo, 'Carmen Soto').filter((m) => m === yo || m.nombre !== 'Carmen Soto')).grupos[0].personas = []
  conMiembros('miembros-conflicto@example.com', 'Carmen', 'admin', familia, 'miembros-conflicto')
  conMiembros('miembros-ultimo-admin@example.com', 'Carmen', 'admin', familia, 'miembros-ultimo-admin')
  conMiembros('miembros-falla@example.com', 'Carmen', 'admin', familia, 'miembros-falla').grupos[0].invitaciones = [mia()]
  conMiembros('miembros-lista-falla@example.com', 'Carmen', 'admin', familia, 'miembros-lista-falla')
  conMiembros('miembros-ya-no-admin@example.com', 'Carmen', 'admin', familia, 'miembros-ya-no-admin').grupos[0].invitaciones = [mia()]
  conMiembros('miembros-tope@example.com', 'Carmen', 'admin', familia, 'miembros-tope')
  conMiembros('miembros-lento@example.com', 'Carmen', 'admin', familia, 'lento').grupos[0].invitaciones = [mia()]
  {
    // D-42-9 y D-42-10: quien escribió «Su día» y «Quién es», creó un enlace y dio las autorizaciones ya no está.
    const u = conMiembros('miembros-autor-salio@example.com', 'Carmen', 'admin', familia)
    const p = conAperturas(u.grupos[0].personas[0])
    const salio = { id: randomUUID(), nombre: null }
    p.campos.rutina = escrito(SU_DIA, salio)
    p.secciones.quien_es = escrito(TEXTOS_SECCION.quien_es, salio, 90)
    p.accesos[0].otorgado_por = salio
    p.autorizoQuienYaNoEsta = true
    u.grupos[0].invitaciones = [invitacionPendiente('cuidador', { nombre: null, eresTu: false })]
  }
}
sembrarMiembros()

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
  /** MATU-55: el dispositivo de la entrada, el claim `did`. */
  did: string
}
const refrescos = new Map<string, Refresh>()
const tokens = new Map<string, { email: string; vence: number; did: string }>()

function emitirToken(u: Usuario, did: string) {
  const t = randomUUID()
  usoDe(did)
  tokens.set(t, { email: u.email, vence: Date.now() + (u.modo === 'vence' ? 20_000 : 15 * 60_000), did })
  return { access_token: t, token_type: 'bearer', expira_en: u.modo === 'vence' ? 20 : 900 }
}
function emitirRefresh(res: ServerResponse, u: Usuario, did: string, vence?: number) {
  const id = randomUUID()
  refrescos.set(id, { email: u.email, vence: vence ?? Date.now() + (u.modo === 'vence' ? 40_000 : 30 * 86_400_000), did })
  res.setHeader('Set-Cookie', `${COOKIE}=${id}; Max-Age=2592000; Path=/v1/sesiones; HttpOnly; SameSite=Strict`)
}
const borrarRefresh = (res: ServerResponse) => res.setHeader('Set-Cookie', `${COOKIE}=; Max-Age=0; Path=/v1/sesiones; HttpOnly; SameSite=Strict`)
const refreshDe = (req: IncomingMessage) => new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]+)`).exec(req.headers.cookie ?? '')?.[1]

/** MATU-55: el `did` del access token, como el claim de la API. */
function didDe(req: IncomingMessage): string | undefined {
  const t = /^Bearer (.+)$/.exec(String(req.headers.authorization ?? ''))?.[1]
  return t ? tokens.get(t)?.did : undefined
}

/** MATU-55: cerrar un dispositivo corta sus refresh; el access token sigue sus 15 minutos. */
function revocarRefrescos(did: string) {
  for (const [id, r] of refrescos) if (r.did === did) refrescos.delete(id)
}

function usuarioDe(req: IncomingMessage): Usuario | null {
  const t = /^Bearer (.+)$/.exec(String(req.headers.authorization ?? ''))?.[1]
  const s = t ? tokens.get(t) : undefined
  if (!s || s.vence < Date.now()) return null
  return usuarios.get(s.email) ?? null
}

export const esLento = (req: IncomingMessage, cuerpo: Record<string, unknown> | null) =>
  usuarioDe(req)?.modo === 'lento' || cuerpo?.email === 'lento@example.com'

// ---------------------------------------------------------------- respuestas

type Responder = {
  json: (res: ServerResponse, status: number, cuerpo: unknown) => void
  problema: (res: ServerResponse, status: number, tipo: string, extra?: Record<string, unknown>) => void
}

const vistaCampo = (c: Campo) => ({
  texto: c.texto,
  etag: c.version ? `"v${c.version}"` : null,
  actualizado_por: autorVista(c.autor),
  actualizado_en: c.en,
})
const completitud = (p: Persona) => Math.round(((['rutina', 'manejo_situaciones', 'red_apoyo'] as CampoApi[]).filter((k) => p.campos[k].texto?.trim()).length * 100) / 3)

function vistaPersona(p: Persona, rol: Rol) {
  if (rol === 'observador') return { id: p.id, nombre: p.nombre }
  // MATU-61 (decisión 190): la dirección trae su `etag` para `If-Match`.
  const direccion = p.direccion ? { etag: '"v1"', ...p.direccion } : null
  if (rol === 'pagador') return { id: p.id, nombre: p.nombre, direccion }
  return {
    id: p.id,
    nombre: p.nombre,
    nombre_pila: p.nombre_pila,
    nivel_apoyo: p.nivel_apoyo,
    direccion,
    consentimiento: { id: randomUUID(), calidad_otorgante: p.calidad, finalidad: 'plan_cuidado', version_politica: '0.9', otorgado_en: hace(60 * 24), revision_vence_en: null },
  }
}

const conflictosHechos = new Set<string>()

/** Atiende /v1 de la familia. `false` si la ruta no es suya. */
/** MATU-72: las personas borradas, `grupo:persona`, para el 409 `ya-borrada`. Solo en memoria del doble. */
const borradas = new Set<string>()

export async function atenderFamilia(req: IncomingMessage, res: ServerResponse, cuerpo: Record<string, unknown> | null, r: Responder): Promise<boolean> {
  const metodo = req.method ?? 'GET'
  const ruta = (req.url ?? '').split('?')[0]
  const { json, problema } = r

  if (metodo === 'POST' && ruta === '/v1/usuarios') {
    const nombre = cuerpo?.nombre
    const email = typeof cuerpo?.email === 'string' ? cuerpo.email.trim().toLowerCase() : ''
    const telefono = cuerpo?.telefono
    const contrasena = cuerpo?.contrasena
    // Límite por IP de MATU-25: el 429 va antes del 422, como en la API. Sin IP en el doble: por correo.
    if (Object.hasOwn(ESPERA_IP_CREAR_CUENTA, email)) {
      const retryAfter = ESPERA_IP_CREAR_CUENTA[email]
      if (retryAfter) res.setHeader('Retry-After', retryAfter)
      return problema(res, 429, '/errores/demasiadas-peticiones'), true
    }
    const errores: { campo: string; mensaje: string; tipo: string }[] = []
    if (typeof nombre !== 'string' || !nombre.trim() || nombre.length > 100) errores.push({ campo: 'nombre', mensaje: 'MENSAJE DEL DOBLE', tipo: 'value_error' })
    if (!email.includes('@')) errores.push({ campo: 'email', mensaje: 'MENSAJE DEL DOBLE', tipo: 'value_error' })
    if (typeof telefono !== 'string' || !/^(\+?56 ?)?9( ?[0-9]){8}$/.test(telefono.trim())) errores.push({ campo: 'telefono', mensaje: 'MENSAJE DEL DOBLE', tipo: 'celular_invalido' })
    if (typeof contrasena !== 'string' || contrasena.length < 10 || contrasena.length > 128) errores.push({ campo: 'contrasena', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_too_short' }) // pragma: allowlist secret
    // MATU-75 (decisiones 176, 177 y 182): `acepta_politica` estricto en `true`, y la huella obligatoria y bien formada.
    if (cuerpo?.acepta_politica !== true)
      errores.push({ campo: 'acepta_politica', mensaje: 'MENSAJE DEL DOBLE', tipo: cuerpo?.acepta_politica === false ? 'politica_no_aceptada' : 'missing' })
    const huellaPolitica = cuerpo?.huella_politica
    // Decisión 182: la huella es obligatoria; sin ella o mal formada, 422 junto al campo.
    if (typeof huellaPolitica !== 'string' || !/^[0-9a-f]{64}$/.test(huellaPolitica))
      errores.push({ campo: 'huella_politica', mensaje: 'MENSAJE DEL DOBLE', tipo: 'string_pattern_mismatch' })
    if (errores.length) return problema(res, 422, '/errores/validacion', { errores }), true
    if (!politicaPublicada()) return problema(res, 503, '/errores/servicio-no-disponible'), true
    // `politica-cambio@example.com`: la primera vez, la política cambió mientras se creaba la cuenta.
    const cambioDeEjemplo = email === CORREO_POLITICA_CAMBIO && !politicaCambiada.has(email)
    if (cambioDeEjemplo) politicaCambiada.add(email)
    if (cambioDeEjemplo || huellaPolitica !== HUELLA) return problema(res, 409, '/errores/politica-cambio'), true
    // Decisión 105: en staging, después del cuerpo y antes del 409. El doble acepta cualquier dominio salvo este.
    if (email.endsWith(`@${DOMINIO_NO_PERMITIDO}`))
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'email', mensaje: 'MENSAJE DEL DOBLE', tipo: 'dominio_no_permitido' }] }), true
    if (usuarios.has(email)) return problema(res, 409, '/errores/email-registrado'), true
    const u = cuenta(email, String(nombre).trim(), [])
    u.contrasena = String(contrasena)
    u.politica = aceptacionVigente(new Date().toISOString())
    return json(res, 201, { id: u.id, nombre: u.nombre, email: u.email }), true
  }

  if (metodo === 'POST' && ruta === '/v1/sesiones') {
    const email = typeof cuerpo?.email === 'string' ? cuerpo.email.trim().toLowerCase() : ''
    if (email === 'espera@example.com') return res.setHeader('Retry-After', '90'), problema(res, 429, '/errores/demasiadas-peticiones'), true
    if (email === 'espera-1@example.com') return res.setHeader('Retry-After', '30'), problema(res, 429, '/errores/demasiadas-peticiones'), true
    if (email === 'caido@example.com') return problema(res, 503, '/errores/servicio-no-disponible'), true
    const u = usuarios.get(email)
    if (!u || u.contrasena !== cuerpo?.contrasena) return problema(res, 401, '/errores/credenciales-invalidas'), true
    const did = alEntrar(u.email, String(req.headers['user-agent'] ?? ''), u.modo)
    emitirRefresh(res, u, did)
    return json(res, 200, emitirToken(u, did)), true
  }

  if (metodo === 'POST' && ruta === '/v1/sesiones/renovar') {
    if (req.headers['x-matu-cliente'] !== 'web') return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'X-MATU-Cliente', mensaje: 'MENSAJE DEL DOBLE', tipo: 'missing' }] }), true
    const id = refreshDe(req)
    const s = id ? refrescos.get(id) : undefined
    if (id) refrescos.delete(id) // rota: el anterior ya no sirve
    const u = s ? usuarios.get(s.email) : undefined
    if (!s || !u || s.vence < Date.now() || !dispositivoVivo(s.did)) return borrarRefresh(res), problema(res, 401, '/errores/sesion-expirada'), true
    emitirRefresh(res, u, s.did, u.modo === 'vence' ? s.vence : undefined)
    return json(res, 200, emitirToken(u, s.did)), true
  }

  if (metodo === 'POST' && ruta === '/v1/sesiones/cerrar') {
    const id = refreshDe(req)
    if (id) {
      alSalir(refrescos.get(id)?.did)
      refrescos.delete(id)
    }
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
      anotarCuenta(email, 'codigo_recuperacion_pedido')
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
    anotarCuenta(email, 'contrasena_cambiada')
    // Revoca todas las entradas de la cuenta (decisión 86) y avisa por el otro canal.
    for (const [id, r] of refrescos) if (r.email === email) refrescos.delete(id)
    console.info(`[doble · envío simulado] aviso → ${email}: cambiaron tu contraseña`)
    return sinCuerpo(res, 204), true
  }

  // ------------------------------------------------ MATU-59: el catálogo, sin X-Grupo-Id ni persona
  if (metodo === 'GET' && ruta === '/v1/catalogo') {
    const u = usuarioDe(req)
    if (!u) return problema(res, 401, req.headers.authorization ? '/errores/token-invalido' : '/errores/no-autenticado'), true
    if (u.modo === 'catalogo-falla') return problema(res, 503, '/errores/servicio-no-disponible'), true
    // CAPA3_HABILITADA=false: la ruta no existe (decisión 167).
    if (u.modo?.startsWith('catalogo-apagado')) return problema(res, 404, '/errores/no-encontrado'), true
    return json(res, 200, catalogoDoble(u.modo)), true
  }

  // MATU-62 (decisión 234): la vuelta de Webpay es pública y la sesión es opcional; nunca responde 401.
  if (metodo === 'POST' && ruta === '/v1/pagos/retorno') {
    const yo = usuarioDe(req)
    const grupoDe = (personaId: string) => {
      const g = yo?.grupos.find((x) => x.personas.some((p) => p.id === personaId))
      return g ? { grupo_id: g.id, rol: g.rol } : null
    }
    return atenderRetorno(res, cuerpo, r, yo, grupoDe), true
  }

  // MATU-42: la persona invitada (decisión 299). La presentación y la verificación son públicas; la
  // aceptación, con sesión y sin `X-Grupo-Id`: une a la cuenta en un grupo nuevo del doble.
  if (metodo === 'POST' && ruta.startsWith('/v1/invitaciones/')) {
    const paso = ruta.slice('/v1/invitaciones/'.length)
    if (paso === 'presentacion' || paso === 'verificacion' || paso === 'aceptacion') {
      const yo = paso === 'aceptacion' ? usuarioDe(req) : null
      if (paso === 'aceptacion' && !yo) return problema(res, 401, req.headers.authorization ? '/errores/token-invalido' : '/errores/no-autenticado'), true
      atenderInvitacionPublica(paso, res, cuerpo, r, yo, (i) => {
        const g = grupo(i.grupo, i.rol, i.personas.map((pila) => persona(`${pila} Soto`, pila, { rutina: escrito(SU_DIA, { id: randomUUID(), nombre: i.nombre_pila_invita }) })))
        const nuevo = miembro(yo!.nombre, i.rol, 0, { eresTu: true })
        g.miembros = [miembro(`${i.nombre_pila_invita} Soto`, 'admin', 30, { enlaces: 1 }), nuevo]
        yo!.grupos.push(g)
        return { grupo_id: g.id, membresia_id: nuevo.id }
      })
      return true
    }
  }

  if (!ruta.startsWith('/v1/grupos') && !ruta.startsWith('/v1/personas-cuidadas') && !ruta.startsWith('/v1/cuenta') && !ruta.startsWith('/v1/accesos-relevo') && !ruta.startsWith('/v1/pedidos') && !ruta.startsWith('/v1/dispositivos') && !ruta.startsWith('/v1/yo/')) return false

  const u = usuarioDe(req)
  if (!u) return problema(res, req.headers.authorization ? 401 : 401, req.headers.authorization ? '/errores/token-invalido' : '/errores/no-autenticado'), true

  // ------------------------------------------------ MATU-55: dónde entraste, los avisos y el push
  const editor = u.grupos.some((g) => g.rol === 'admin' || g.rol === 'cuidador')
  if (atenderDispositivos(req, res, cuerpo, r, { email: u.email, modo: u.modo, editor }, didDe(req), revocarRefrescos)) return true

  // ------------------------------------------------ MATU-57: la cuenta y el celular
  if (metodo === 'GET' && ruta === '/v1/cuenta') {
    res.setHeader('Cache-Control', 'no-store')
    const vista = {
      id: u.id,
      nombre: u.nombre,
      email: u.email,
      celular_enmascarado: enmascarar(u.telefono),
      celular_verificado: u.celularVerificado,
      celular_canal: u.canal,
      politica_aceptada: u.politica,
    }
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
    anotarCuenta(u.email, 'celular_confirmado')
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
  // MATU-42: quiénes forman el grupo, cambiar el rol, sacar, salir y las invitaciones (grupo.ts).
  const mGrupo = /^\/v1\/grupos\/([^/]+)\/(miembros|invitaciones|salida)(?:\/([^/]+))?$/.exec(ruta)
  if (mGrupo) {
    if (!g || g.id !== decodeURIComponent(mGrupo[1])) return problema(res, 404, '/errores/no-encontrado'), true
    return atenderGrupo(req, res, cuerpo, r, u, g, mGrupo[2] as 'miembros' | 'invitaciones' | 'salida', mGrupo[3] ? decodeURIComponent(mGrupo[3]) : null), true
  }
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

  // MATU-61: la dirección y el pedido. Con la capa 3 apagada, las rutas del pedido no existen (C2).
  const capa3 = !u.modo?.startsWith('catalogo-apagado')
  if (capa3 || /\/direccion$/.test(ruta)) {
    const personaDe = (id: string) => g?.personas.find((x) => x.id === id) ?? null
    if (atenderPedido(req, res, cuerpo, r, u, g?.rol ?? null, personaDe)) return true
  }

  // MATU-72: `POST …/borrado` (decisiones 149 a 153). La persona sale del grupo y sus enlaces quedan
  // cortados; un segundo borrado responde 409. Cuentas: «retiro-falla» responde 500, «retiro-otra»
  // borra como si fuera otra persona y responde 409, y «retiro-lento» tarda 2 s.
  const mBorrado = /^\/v1\/personas-cuidadas\/([^/]+)\/borrado$/.exec(ruta)
  if (mBorrado && metodo === 'POST') {
    const id = decodeURIComponent(mBorrado[1])
    res.setHeader('Cache-Control', 'no-store')
    if (!g || (g.rol !== 'admin' && g.rol !== 'cuidador')) return problema(res, 404, '/errores/no-encontrado'), true
    if (borradas.has(`${g.id}:${id}`)) return problema(res, 409, '/errores/ya-borrada'), true
    const pc = g.personas.find((x) => x.id === id)
    if (!pc) return problema(res, 404, '/errores/no-encontrado'), true
    if (u.modo === 'retiro-falla') return problema(res, 500, '/errores/error-interno'), true
    const ahora = new Date().toISOString()
    const cortados = pc.accesos.filter((x) => estadoDe(x) !== 'vencido' && !x.revocado_en)
    for (const x of cortados) x.revocado_en = ahora
    const retiradas = (['plan_cuidado', 'consumo'] as const).filter((f) => !pc.autorizaciones[f].retiro).length
    g.personas = g.personas.filter((x) => x.id !== id)
    borradas.add(`${g.id}:${id}`)
    if (u.modo === 'retiro-otra') return problema(res, 409, '/errores/ya-borrada'), true
    return json(res, 200, { persona_id: id, borrado_en: ahora, enlaces_cortados: cortados.length, autorizaciones_retiradas: retiradas }), true
  }

  // MATU-44: el estado de las autorizaciones, retirar y volver a autorizar la ficha.
  const mAut = /^\/v1\/personas-cuidadas\/([^/]+)\/consentimientos(?:\/([^/]+)\/retiro)?$/.exec(ruta)
  if (mAut) {
    const pc = g?.personas.find((x) => x.id === decodeURIComponent(mAut[1]))
    if (!g || !pc) return problema(res, 404, '/errores/no-encontrado'), true
    const despacho = !u.modo?.startsWith('catalogo-apagado')
    const metodoAut = req.method ?? 'GET'
    const editorAut = g.rol === 'admin' || g.rol === 'cuidador'
    // MATU-61 (decisión 192): `despacho` se otorga como las otras, solo con la capa 3. Se retira
    // siempre (decisión 250) y, con la capa apagada, viene en la vista solo con un registro (decisión 251).
    if (metodoAut === 'POST' && editorAut && mAut[2] === 'despacho' && (despacho || tieneDespacho(pc.id))) return retirarDespacho(res, pc.id, g.rol, r, despacho), true
    if (despacho && metodoAut === 'POST' && editorAut && !mAut[2] && cuerpo?.finalidad === 'despacho') return otorgarDespacho(res, cuerpo, pc.id, r), true
    if (metodoAut === 'GET' && !mAut[2] && (despacho || tieneDespacho(pc.id))) {
      res.setHeader('Cache-Control', 'no-store')
      const vistas = (['plan_cuidado', 'consumo'] as const).map((f) => vistaAutorizacion(pc, u, f, g.rol))
      return r.json(res, 200, { autorizaciones: [...vistas, vistaDespacho(pc.id, g.rol, despacho)] }), true
    }
    const atendido = atenderAutorizaciones(req, res, cuerpo, r, u, g, pc, mAut[2] ? decodeURIComponent(mAut[2]) : null)
    if (atendido) return true
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

  // MATU-48: POST y GET …/plan/accesos-relevo, y DELETE /v1/accesos-relevo/{id}.
  const mAccesos = /^\/v1\/personas-cuidadas\/([^/]+)\/plan\/accesos-relevo$/.exec(ruta)
  if (mAccesos) return atenderAccesos(req, res, cuerpo, r, u, g, decodeURIComponent(mAccesos[1])), true
  const mCortar = /^\/v1\/accesos-relevo\/([^/]+)$/.exec(ruta)
  if (mCortar) return cortar(req, res, r, u, g, decodeURIComponent(mCortar[1])), true

  // MATU-50: PUT y DELETE …/plan/secciones/{seccion} (ficha-ampliada.openapi.yaml).
  const mSeccion = /^\/v1\/personas-cuidadas\/([^/]+)\/plan\/secciones\/([a-z_]+)$/.exec(ruta)
  if (mSeccion) return atenderSeccion(req, res, cuerpo, r, u, g, decodeURIComponent(mSeccion[1]), mSeccion[2]), true

  const mFicha = /^\/v1\/personas-cuidadas\/([^/]+)\/plan\/ficha(?:\/([a-z_]+))?$/.exec(ruta)
  if (!mFicha) return problema(res, 404, '/errores/no-encontrado'), true
  const p = g?.personas.find((x) => x.id === decodeURIComponent(mFicha[1]))
  if (!g || !p) return problema(res, 404, '/errores/no-encontrado'), true
  const puedeLeer = g.rol === 'admin' || g.rol === 'cuidador' || (g.rol === 'pagador' && g.puede_ver_plan)
  if (!puedeLeer) return problema(res, 404, '/errores/no-encontrado'), true
  if (u.modo === 'sin-consentimiento' || p.autorizaciones.plan_cuidado.retiro) return problema(res, 403, '/errores/sin-consentimiento'), true
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
      actualizado_por: autorVista(nuevo.autor),
      actualizado_en: nuevo.en,
      completitud: completitud(p),
    }),
    true
  )
}

// ---------------------------------------------------------------- autorizaciones (MATU-44)

/** La `AutorizacionVista` de una finalidad (decisión 127). Al pagador y al observador, sin la calidad. */
function vistaAutorizacion(p: Persona, u: Usuario, finalidad: Finalidad, rol: Rol) {
  const { otorgado_en, retiro } = p.autorizaciones[finalidad]
  // MATU-42 (decisión 311): `autorizo_alguien_que_ya_no_esta` solo para admin y cuidador, y solo sin retiro.
  const calidad = rol === 'admin' || rol === 'cuidador' ? { calidad_otorgante: p.calidad, autorizo_alguien_que_ya_no_esta: !retiro && p.autorizoQuienYaNoEsta === true } : {}
  const vacia = { revision_vence_en: null, revocado_en: null, borrado_en: null, borrada: false, se_puede_otorgar: true }
  if (retiro) {
    const borrada = new Date(retiro.borrado_en).getTime() <= Date.now()
    return { finalidad, estado: borrada ? 'borrada' : 'retirada', id: `${p.id}-${finalidad}`, ...calidad, otorgado_en, ...vacia, ...retiro, borrada }
  }
  const nunca = finalidad === 'consumo' && p.consumo.autorizacion === 'no'
  if (nunca) return { finalidad, estado: 'sin_autorizar', id: null, ...(rol === 'admin' || rol === 'cuidador' ? { calidad_otorgante: null, autorizo_alguien_que_ya_no_esta: false } : {}), otorgado_en: null, ...vacia }
  const vencida = finalidad === 'consumo' ? p.consumo.autorizacion === 'vencida' : u.modo === 'revision-vencida'
  // Por renovar: se otorgó hace más de un año y la revisión venció 12 meses después (decisión 33).
  const AÑO = 365 * DIA
  const otorgada = vencida && new Date(otorgado_en).getTime() > Date.now() - AÑO * 60_000 ? hace(AÑO + 30 * DIA) : otorgado_en
  return {
    finalidad,
    estado: vencida ? 'revision_vencida' : 'vigente',
    id: `${p.id}-${finalidad}`,
    ...calidad,
    otorgado_en: otorgada,
    ...vacia,
    revision_vence_en: vencida ? new Date(new Date(otorgada).getTime() + AÑO * 60_000).toISOString() : null,
  }
}

/**
 * `GET …/consentimientos`, `POST …/consentimientos/{finalidad}/retiro` y el `POST` con
 * `plan_cuidado`. El `POST` con `consumo` sigue en consumo.ts (devuelve `false`), salvo que antes
 * borra lo anotado si ya pasaron los 90 días. Cuentas: «retiro-falla» responde 500 al retirar y
 * «retiro-otra» retira como si fuera otra persona y responde 409.
 */
function atenderAutorizaciones(
  req: IncomingMessage,
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  { json, problema }: Responder,
  u: Usuario,
  g: Grupo,
  p: Persona,
  retiro: string | null,
): boolean {
  const metodo = req.method ?? 'GET'
  const editor = g.rol === 'admin' || g.rol === 'cuidador'
  if (metodo === 'GET' && !retiro) {
    res.setHeader('Cache-Control', 'no-store')
    return json(res, 200, { autorizaciones: (['plan_cuidado', 'consumo'] as const).map((f) => vistaAutorizacion(p, u, f, g.rol)) }), true
  }
  if (metodo !== 'POST' || !editor) return problema(res, 404, '/errores/no-encontrado'), true

  if (retiro) {
    if (retiro !== 'plan_cuidado' && retiro !== 'consumo') return problema(res, 404, '/errores/no-encontrado'), true
    const a = p.autorizaciones[retiro]
    if (retiro === 'consumo' && !a.retiro && p.consumo.autorizacion === 'no') return problema(res, 404, '/errores/no-encontrado'), true
    if (a.retiro) return problema(res, 409, '/errores/ya-retirada'), true
    if (u.modo === 'retiro-falla') return problema(res, 500, '/errores/error-interno'), true
    const antes = p.accesos.filter((x) => estadoDe(x) !== 'vencido' && !x.revocado_en).length
    conRetiro(p, retiro, 0)
    if (u.modo === 'retiro-otra') return problema(res, 409, '/errores/ya-retirada'), true
    return json(res, 200, { autorizacion: { ...vistaAutorizacion(p, u, retiro, g.rol), calidad_otorgante: p.calidad }, enlaces_cortados: retiro === 'plan_cuidado' ? antes : 0 }), true
  }

  const b = cuerpo ?? {}
  if (b.finalidad === 'consumo') {
    // Decisión 128: después del día 90, lo anotado se borra antes de autorizar de nuevo.
    const r = p.autorizaciones.consumo.retiro
    if (r && new Date(r.borrado_en).getTime() <= Date.now()) p.consumo.perfiles = []
    if (r) p.consumo.autorizacion = 'no'
    res.once('finish', () => {
      if (res.statusCode === 201) p.autorizaciones.consumo = { otorgado_en: new Date().toISOString(), retiro: null }
    })
    return false
  }
  if (b.finalidad !== 'plan_cuidado') return false
  const calidad = b.calidad_otorgante
  const aviso = b.aviso as { id?: unknown } | null | undefined
  const ref = typeof b.referencia_documento === 'string' ? b.referencia_documento.trim() : ''
  const mal = (campo: string, tipo: string) => (problema(res, 422, '/errores/validacion', { errores: [{ campo, mensaje: 'MENSAJE DEL DOBLE: NO SE MUESTRA', tipo }] }), true)
  if (!['titular', 'representante_legal', 'cuidador_de_hecho'].includes(String(calidad))) return mal('calidad_otorgante', 'enum')
  if (calidad === 'representante_legal' && !ref) return mal('referencia_documento', 'regla_calidad_otorgante')
  if (calidad === 'cuidador_de_hecho' && aviso?.id !== 'aviso_cuidador_de_hecho') return mal('aviso', 'regla_calidad_otorgante')
  const r = p.autorizaciones.plan_cuidado.retiro
  if (!r) return problema(res, 409, '/errores/autorizacion-vigente'), true
  // Decisión 130 (P8): después del día 90 la ficha empieza en blanco, en 0 de 3.
  if (new Date(r.borrado_en).getTime() <= Date.now()) {
    p.campos = { rutina: vacio(), manejo_situaciones: vacio(), red_apoyo: vacio() }
    p.secciones = {}
  }
  const ahora = new Date().toISOString()
  p.calidad = String(calidad)
  p.autorizaciones.plan_cuidado = { otorgado_en: ahora, retiro: null }
  const consentimiento = { id: randomUUID(), calidad_otorgante: calidad, finalidad: 'plan_cuidado', version_politica: '0.10', otorgado_en: ahora, revision_vence_en: null }
  return json(res, 201, { consentimiento, aviso: null }), true
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
  if (u.modo === 'sin-consentimiento' || p.autorizaciones.plan_cuidado.retiro) return problema(res, 403, '/errores/sin-consentimiento')
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
  return json(res, actual ? 200 : 201, { seccion, texto: nuevo.texto, etag: `"v${nuevo.version}"`, actualizado_por: autorVista(nuevo.autor), actualizado_en: nuevo.en })
}

// ---------------------------------------------------------------- accesos de relevo (MATU-48)

const MOTIVOS: Motivo[] = ['salgo_unas_horas', 'fin_de_semana_fuera', 'turno_de_noche', 'otro']
const CELULAR = /^(\+?56 ?)?9( ?[0-9]){8}$/
const seccionesQuitadas = new Set<string>()

function estadoDe(a: Acceso): 'vigente' | 'vencido' | 'revocado' | 'bloqueado' {
  if (a.revocado_en) return 'revocado'
  if (a.bloqueado) return 'bloqueado'
  return new Date(a.expira_en).getTime() <= Date.now() ? 'vencido' : 'vigente'
}

/** Decisión 31: el teléfono solo para admin y cuidador; para el pagador la propiedad no viene. */
function vistaAcceso(a: Acceso, rol: Rol) {
  const { bloqueado: _b, telefono_relevo, ...resto } = a
  void _b
  const vista = { ...resto, otorgado_por: autorVista(a.otorgado_por), estado: estadoDe(a), ultimo_uso_en: null as string | null }
  return rol === 'admin' || rol === 'cuidador' ? { ...vista, telefono_relevo } : vista
}

/**
 * `POST` y `GET …/plan/accesos-relevo`, con el orden del contrato: alcance (404), consentimiento
 * (403), validación (422). Las cuentas «compartir-…» responden el error de su nombre.
 */
function atenderAccesos(
  req: IncomingMessage,
  res: ServerResponse,
  cuerpo: Record<string, unknown> | null,
  { json, problema }: Responder,
  u: Usuario,
  g: Grupo | undefined,
  personaId: string,
) {
  const metodo = req.method ?? 'GET'
  const p = g?.personas.find((x) => x.id === personaId)
  if (!g || !p) return problema(res, 404, '/errores/no-encontrado')

  if (metodo === 'GET') {
    const puede = g.rol === 'admin' || g.rol === 'cuidador' || (g.rol === 'pagador' && g.puede_ver_plan)
    if (!puede) return problema(res, 404, '/errores/no-encontrado')
    if (u.modo === 'lista-falla') return problema(res, 500, '/errores/error-interno')
    const q = new URL(req.url ?? '', 'http://doble').searchParams
    const limite = Number(q.get('limite') ?? '20')
    if (!Number.isInteger(limite) || limite < 1 || limite > 100)
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'limite', mensaje: 'MENSAJE DEL DOBLE', tipo: 'value_error' }] })
    const estado = q.get('estado')
    const lista = p.accesos.filter((a) => !estado || estadoDe(a) === estado)
    const cursor = q.get('cursor')
    const desde = cursor ? Number(Buffer.from(cursor, 'base64url').toString('utf8')) : 0
    if (!Number.isInteger(desde) || desde < 0 || desde > lista.length)
      return problema(res, 422, '/errores/validacion', { errores: [{ campo: 'cursor', mensaje: 'MENSAJE DEL DOBLE', tipo: 'cursor_invalido' }] })
    const hasta = desde + limite
    res.setHeader('Cache-Control', 'no-store')
    const siguiente = hasta < lista.length ? Buffer.from(String(hasta)).toString('base64url') : null
    return json(res, 200, { items: lista.slice(desde, hasta).map((a) => vistaAcceso(a, g.rol)), siguiente_cursor: siguiente })
  }

  if (metodo !== 'POST') return problema(res, 404, '/errores/no-encontrado')
  if (g.rol !== 'admin' && g.rol !== 'cuidador') return problema(res, 404, '/errores/no-encontrado')
  if (u.modo === 'sin-consentimiento' || p.autorizaciones.plan_cuidado.retiro) return problema(res, 403, '/errores/sin-consentimiento')
  if (u.modo === 'revision-vencida') return problema(res, 403, '/errores/revision-vencida')
  const b = cuerpo ?? {}
  const error = (campo: string, tipo: string) => problema(res, 422, '/errores/validacion', { errores: [{ campo, mensaje: 'MENSAJE DEL DOBLE', tipo }] })
  const forzado = /^422-(.+)$/.exec(u.modo ?? '')?.[1]
  if (forzado === 'nombre_relevo') return error('nombre_relevo', 'string_too_short')
  if (forzado === 'telefono_relevo') return error('telefono_relevo', 'celular_invalido')
  if (forzado === 'relevo_informado') return error('relevo_informado', 'relevo_no_informado')
  if (forzado === 'vigencia_pasada' || forzado === 'vigencia_maxima') return error('expira_en', forzado)
  if (u.modo === 'compartir-503') return problema(res, 503, '/errores/servicio-no-disponible')
  if (u.modo === 'compartir-500') return problema(res, 500, '/errores/error-interno')

  const nombre = typeof b.nombre_relevo === 'string' ? b.nombre_relevo.trim() : ''
  if (!nombre || nombre.length > 60) return error('nombre_relevo', 'string_too_long')
  if (typeof b.telefono_relevo !== 'string' || !CELULAR.test(b.telefono_relevo)) return error('telefono_relevo', 'celular_invalido')
  if (b.relevo_informado !== true) return error('relevo_informado', 'relevo_no_informado')
  if (!MOTIVOS.includes(b.motivo as Motivo)) return error('motivo', 'enum')
  if (b.campos !== undefined && b.campos !== null) return error('campos', 'campos_base_obligatorios')
  const secciones = Array.isArray(b.secciones_adicionales) ? (b.secciones_adicionales as string[]) : []
  if (new Set(secciones).size !== secciones.length) return error('secciones_adicionales', 'duplicado')
  // Cuenta «compartir-seccion»: Rodrigo quita una de las elegidas justo antes del primer envío.
  if (forzado === 'seccion_no_agregada' && secciones.length && !seccionesQuitadas.has(p.id)) {
    seccionesQuitadas.add(p.id)
    delete p.secciones[secciones[0] as SeccionApi]
  }
  if (secciones.some((x) => !(SECCIONES as string[]).includes(x) || !p.secciones[x as SeccionApi])) return error('secciones_adicionales', 'seccion_no_agregada')
  const expira = typeof b.expira_en === 'string' ? new Date(b.expira_en).getTime() : Date.now() + DIA * 60_000
  if (Number.isNaN(expira)) return error('expira_en', 'datetime_parsing')
  if (expira <= Date.now()) return error('expira_en', 'vigencia_pasada')
  if (expira > Date.now() + 30 * DIA * 60_000) return error('expira_en', 'vigencia_maxima')

  const token = randomBytes(32).toString('base64url')
  const a: Acceso = {
    id: randomUUID(),
    nombre_relevo: nombre,
    telefono_relevo: String(b.telefono_relevo).replace(/\s+/g, '').replace(/^(?:\+?56)?9/, '+569'),
    campos: TRES,
    secciones_adicionales: SECCIONES.filter((x) => secciones.includes(x)),
    motivo: b.motivo as Motivo,
    creado_en: new Date().toISOString(),
    expira_en: new Date(expira).toISOString(),
    revocado_en: null,
    bloqueado: false,
    usos: 0,
    otorgado_por: { id: u.id, nombre: u.nombre.split(' ')[0] },
  }
  p.accesos.unshift(a)
  res.setHeader('Cache-Control', 'no-store')
  return json(res, 201, {
    id: a.id,
    url: `http://${req.headers.host ?? 'localhost'}/r#${token}`,
    pin: String(randomInt(0, 10_000)).padStart(4, '0'),
    campos: a.campos,
    secciones_adicionales: a.secciones_adicionales,
    expira_en: a.expira_en,
    nombre_relevo: a.nombre_relevo,
    nombre_pila_persona: p.nombre_pila,
  })
}

/** `DELETE /v1/accesos-relevo/{id}`: 204 idempotente; no exige autorización vigente (decisión 18). */
function cortar(req: IncomingMessage, res: ServerResponse, { problema }: Responder, u: Usuario, g: Grupo | undefined, id: string) {
  if (req.method !== 'DELETE') return problema(res, 404, '/errores/no-encontrado')
  if (!g || (g.rol !== 'admin' && g.rol !== 'cuidador')) return problema(res, 404, '/errores/no-encontrado')
  const a = g.personas.flatMap((p) => p.accesos).find((x) => x.id === id)
  if (!a) return problema(res, 404, '/errores/no-encontrado')
  if (u.modo === 'cortar-falla') return problema(res, 500, '/errores/error-interno')
  if (estadoDe(a) === 'vigente') a.revocado_en = new Date().toISOString()
  res.statusCode = 204
  return res.end()
}

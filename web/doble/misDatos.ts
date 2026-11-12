// MATU-54 en el doble: `GET /v1/personas-cuidadas/{persona_id}/datos` y `GET /v1/yo/datos`, con la forma
// del contrato propuesto (docs/api/propuestos/mis-datos.openapi.yaml): el orden 404, 503, 429, registro y
// 200; el límite de 10 copias por hora común a las dos rutas; `Content-Disposition` con el nombre del
// archivo; `Cache-Control: no-store`, y los instantes con el desfase de Chile. La copia se arma con lo
// que el doble ya tiene de la cuenta y la persona, más un historial de ejemplo. Datos sintéticos.
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { ConsumoDoble, PerfilDoble } from './consumo'
import { anotarCopia, paraCopia } from './dispositivos'

type Responder = {
  json: (res: ServerResponse, status: number, cuerpo: unknown) => void
  problema: (res: ServerResponse, status: number, tipo: string, extra?: Record<string, unknown>) => void
}
type Rol = 'admin' | 'cuidador' | 'pagador' | 'observador'
type CampoApi = 'rutina' | 'manejo_situaciones' | 'red_apoyo'
type SeccionApi = 'quien_es' | 'preferencias' | 'alimentacion' | 'movilidad' | 'comunicacion' | 'remedios'
type Autor = { id: string; nombre: string | null } | null
interface CampoDoble {
  texto: string | null
  autor: Autor
  en: string | null
}

/** Lo que la copia lee de una persona del doble (la `Persona` de familia.ts). */
export interface PersonaParaCopia {
  id: string
  nombre: string
  nombre_pila: string
  nivel_apoyo: string
  direccion: Record<string, unknown> | null
  calidad: string
  campos: Record<CampoApi, CampoDoble>
  secciones: Partial<Record<SeccionApi, CampoDoble>>
  consumo: ConsumoDoble
  aperturas: { ocurrido_en: string; tipo: 'presentacion' | 'apertura' | 'pin_incorrecto' | 'bloqueo'; acceso: { id: string; nombre_relevo: string } }[]
  accesos: {
    id: string
    nombre_relevo: string
    campos: CampoApi[]
    secciones_adicionales: SeccionApi[]
    motivo: string
    creado_en: string
    expira_en: string
    revocado_en: string | null
    bloqueado: boolean
    otorgado_por: Autor
  }[]
  autorizaciones: Record<'plan_cuidado' | 'consumo', { otorgado_en: string; retiro: { revocado_en: string; borrado_en: string } | null }>
}

/** Lo que la copia lee de una cuenta del doble (el `Usuario` de familia.ts). */
export interface CuentaParaCopia {
  nombre: string
  email: string
  modo?: string
  telefono: string | null
  celularVerificado: boolean
  canal: 'sms' | 'whatsapp'
  politica: { version: string; huella: string; aceptada_en: string } | null
  grupos: { id: string; nombre: string; rol: Rol; puede_ver_plan: boolean; personas: PersonaParaCopia[] }[]
}

// ---------------------------------------------------------------- tiempo, en la hora de Chile

const MIN = 60_000
const DIA = 24 * 60
const hace = (min: number) => new Date(Date.now() - min * MIN).toISOString()
const PARTES = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Santiago',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
})
const dos = (n: number) => String(n).padStart(2, '0')

/** RFC 3339 con el desfase de Chile, por ejemplo `2026-11-12T10:05:00-03:00` (decisión 349). */
export function chile(iso: string): string {
  const t = new Date(iso)
  t.setUTCMilliseconds(0)
  const p = Object.fromEntries(PARTES.formatToParts(t).map((x) => [x.type, x.value]))
  const pared = Date.UTC(Number(p.year), Number(p.month) - 1, Number(p.day), Number(p.hour), Number(p.minute), Number(p.second))
  const desfase = Math.round((pared - t.getTime()) / MIN)
  const signo = desfase < 0 ? '-' : '+'
  const abs = Math.abs(desfase)
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}${signo}${dos(Math.floor(abs / 60))}:${dos(abs % 60)}`
}
const diaChile = (iso: string) => chile(iso).slice(0, 10)
const hoyChile = () => diaChile(new Date().toISOString())
const sumarDias = (dia: string, n: number) => {
  const [a, m, d] = dia.split('-').map(Number)
  return new Date(Date.UTC(a, m - 1, d + n)).toISOString().slice(0, 10)
}

// ---------------------------------------------------------------- límite y lo que se registra

const AVISO =
  'Esta es una copia de los datos que MATU guarda, para que puedas conocerlos o llevarlos a otro lugar. No es la ficha para un relevo, y no se usa para compartirla. MATU no guarda esta copia, y el archivo que descargues queda en tu teléfono, fuera de MATU.'

/** Las copias pedidas por cuenta en la última hora, las dos rutas juntas (decisión 346). */
const pedidas = new Map<string, number[]>()
/** Las copias de cada persona, que aparecen en su historial como «Pidió una copia de los datos». */
const copiasDePersona = new Map<string, { quien: string; en: string }[]>()

/** 503 y 429, en el orden del contrato. `true` si ya respondió. */
function limite(res: ServerResponse, r: Responder, email: string, modo: string | undefined): boolean {
  if (modo === 'datos-caido') return r.problema(res, 503, '/errores/servicio-no-disponible'), true
  if (modo === 'datos-tope') return res.setHeader('Retry-After', '1260'), r.problema(res, 429, '/errores/tope-copias'), true
  const ahora = Date.now()
  const lista = (pedidas.get(email) ?? []).filter((t) => t > ahora - 60 * MIN)
  if (lista.length >= 10) {
    res.setHeader('Retry-After', String(Math.max(1, Math.ceil((lista[0] + 60 * MIN - ahora) / 1000))))
    r.problema(res, 429, '/errores/tope-copias')
    return true
  }
  lista.push(ahora)
  pedidas.set(email, lista)
  return false
}

function entregar(res: ServerResponse, prefijo: 'matu-datos' | 'matu-cuenta', copia: { generado_en: string }) {
  res.statusCode = 200
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.setHeader('Cache-Control', 'no-store')
  res.setHeader('Content-Disposition', `inline; filename="${prefijo}-${copia.generado_en.slice(0, 10)}.json"`)
  res.end(JSON.stringify(copia, null, 2))
}

// ---------------------------------------------------------------- la copia de la persona

const nombrada = (a: Autor, completo?: string) => (a ? { nombre: a.nombre === null ? null : (completo ?? a.nombre), activo: a.nombre !== null } : null)
const persona = (nombre: string | null) => ({ nombre, activo: nombre !== null })

function direccionDe(d: Record<string, unknown> | null) {
  if (!d) return null
  const t = (k: string, defecto: string | null = null) => (typeof d[k] === 'string' && d[k] ? String(d[k]) : defecto)
  return { etiqueta: t('etiqueta', 'Casa')!, calle: t('calle', 'Los Aromos')!, numero: t('numero', '123')!, depto: t('depto'), comuna: t('comuna', 'Ñuñoa')!, region: t('region', 'Metropolitana')!, referencia: t('referencia') }
}

function estadoAcceso(a: PersonaParaCopia['accesos'][number]) {
  if (a.bloqueado) return 'bloqueado'
  if (a.revocado_en) return 'revocado'
  if (new Date(a.expira_en).getTime() <= Date.now()) return 'vencido'
  return 'vigente'
}

const cobertura = (p: PerfilDoble) => Math.floor((p.stock_unidades * p.tasa_dias) / p.tasa_unidades)

function insumosDe(p: PersonaParaCopia, modo: string | undefined, nombre: string) {
  const retiro = p.autorizaciones.consumo.retiro
  const c = p.consumo
  const estado =
    modo === 'datos-borrada' ? 'sin_autorizar' : retiro ? 'retirada' : c.autorizacion === 'vencida' || modo === 'datos-pausa' ? 'en_pausa' : c.autorizacion === 'vigente' ? 'disponible' : 'sin_autorizar'
  if (estado !== 'disponible') return { estado, borrado_el: estado === 'retirada' && retiro ? diaChile(retiro.borrado_en) : null, lista: null, compras: null, avisos: null }
  const quien = (a: { nombre: string } | null) => (a ? persona(a.nombre === nombre ? `${a.nombre} Soto` : a.nombre) : null)
  const lista = c.perfiles.map((x) => ({
    nombre: x.nombre_libre,
    del_catalogo: !!x.producto_id,
    unidad: x.unidad,
    usa_unidades: x.tasa_unidades,
    cada_dias: x.tasa_dias,
    quedaban_unidades: x.stock_unidades,
    quedaban_el: x.stock_medido_en,
    se_acaba_el: sumarDias(x.stock_medido_en, cobertura(x)),
    dias_aviso: x.dias_aviso,
    unidades_por_envase: x.unidades_por_envase ?? null,
    se_sigue: x.activo,
    agregado_en: chile(hace(25 * DIA)),
    actualizado_en: chile(hace(2 * DIA + 75)),
    actualizado_por: quien(x.autor),
  }))
  const nombres = lista.map((x) => x.nombre)
  const n = modo === 'datos-historial' ? 24 : 4
  const compras = Array.from({ length: n }, (_, i) => {
    const en = hace(i * 3 * DIA + 200 + i * 37)
    return {
      insumo: nombres[i % Math.max(1, nombres.length)] ?? 'Pañal adulto talla M',
      unidades: [20, 1, 6, 30][i % 4],
      el: diaChile(en),
      origen: i % 4 === 3 ? 'pedido_matu' : 'declarada',
      anotada_en: chile(en),
      anotada_por: i % 4 === 3 ? null : i % 5 === 2 ? persona(null) : persona(i % 2 ? 'Rodrigo Soto' : 'Carmen Soto'),
    }
  })
  const porId = new Map(c.perfiles.map((x) => [x.id, x.nombre_libre]))
  const avisos = (c.alertas ?? []).map((a) => ({
    insumo: porId.get(a.perfil_id) ?? 'Un insumo',
    fecha_prevista: a.fecha_prevista,
    estado: a.estado,
    creado_en: chile(a.creada_en),
    notificado_en: a.notificada_en ? chile(a.notificada_en) : null,
    cerrado_en: a.cerrada_en ? chile(a.cerrada_en) : null,
  }))
  // Uno de cada estado que falta, para ver sus cuatro frases.
  avisos.push(
    { insumo: nombres[1] ?? 'Apósitos', fecha_prevista: sumarDias(hoyChile(), -12), estado: 'resuelta', creado_en: chile(hace(20 * DIA)), notificado_en: chile(hace(20 * DIA)), cerrado_en: chile(hace(13 * DIA)) },
    { insumo: nombres[2] ?? 'Guantes', fecha_prevista: sumarDias(hoyChile(), -30), estado: 'descartada', creado_en: chile(hace(40 * DIA)), notificado_en: null, cerrado_en: chile(hace(35 * DIA)) },
  )
  if (modo === 'datos-historial') avisos.push({ insumo: nombres[0] ?? 'Pañal', fecha_prevista: sumarDias(hoyChile(), -120), estado: 'resuelta', creado_en: chile(hace(125 * DIA)), notificado_en: chile(hace(125 * DIA)), cerrado_en: chile(hace(121 * DIA)) })
  return { estado, borrado_el: null, lista, compras, avisos }
}

function pedidosDe(modo: string | undefined, direccion: ReturnType<typeof direccionDe>) {
  if (modo === 'datos-sin-capa3') return null
  if (modo === 'datos-vacio' || modo === 'datos-retirada' || modo === 'datos-borrada') return []
  const entrega = direccion ? { calle: direccion.calle, numero: direccion.numero, depto: direccion.depto, comuna: direccion.comuna, region: direccion.region, referencia: direccion.referencia } : null
  const linea = (producto: string, presentacion: string, comercio: string, cantidad: number, precio: number, si_falta: 'otro_comercio' | 'quitar') => ({
    producto,
    presentacion,
    comercio,
    cantidad,
    precio_unitario: precio,
    subtotal: precio * cantidad,
    si_falta,
  })
  const entregado = {
    referencia: '4821',
    estado: 'entregado',
    creado_en: chile(hace(4 * DIA + 180)),
    total_confirmado_en: chile(hace(4 * DIA + 160)),
    lineas: [
      linea('Pañal adulto talla M', 'paquete de 30', 'Farmacia Los Aromos (comercio ficticio)', 2, 13_990, 'otro_comercio'),
      linea('Toallitas húmedas', 'paquete de 80', 'Farmacia Los Aromos (comercio ficticio)', 1, 5_290, 'quitar'),
    ],
    subtotal_productos: 33_270,
    costo_envio: 3_990,
    total: 37_260,
    entrega,
    pago: {
      estado: 'devuelto_parcial',
      pagado_en: chile(hace(4 * DIA + 150)),
      pagado_por: persona('Rodrigo Soto'),
      cobrado: 37_260,
      devuelto: 5_290,
      devoluciones: [{ motivo: 'producto_no_entregado', producto: 'Toallitas húmedas', monto: 5_290, estado: 'hecha', solicitada_en: chile(hace(3 * DIA)), hecha_en: chile(hace(3 * DIA - 30)) }],
      pago_de_prueba: true,
    },
    precios_de_ejemplo: true,
  }
  if (modo !== 'datos-pedidos') return [entregado]
  const base = { lineas: [linea('Guantes desechables', 'caja de 100', 'Farmacia Los Aromos (comercio ficticio)', 1, 6_490, 'otro_comercio')], subtotal_productos: 6_490, costo_envio: 3_990, entrega, precios_de_ejemplo: true }
  return [
    { ...base, referencia: null, estado: 'borrador', creado_en: chile(hace(30)), total_confirmado_en: null, total: null, pago: null },
    { ...base, referencia: null, estado: 'total_confirmado', creado_en: chile(hace(DIA)), total_confirmado_en: chile(hace(DIA - 5)), total: 10_480, pago: { estado: 'pendiente', pagado_en: null, pagado_por: null, cobrado: 0, devuelto: 0, devoluciones: [], pago_de_prueba: true } },
    { ...base, referencia: null, estado: 'vencido', creado_en: chile(hace(2 * DIA)), total_confirmado_en: chile(hace(2 * DIA - 5)), total: 10_480, pago: { estado: 'no_aprobado', pagado_en: null, pagado_por: null, cobrado: 0, devuelto: 0, devoluciones: [], pago_de_prueba: true } },
    { ...base, referencia: '4910', estado: 'en_ruta', creado_en: chile(hace(3 * DIA)), total_confirmado_en: chile(hace(3 * DIA - 5)), total: 10_480, pago: { estado: 'aprobado', pagado_en: chile(hace(3 * DIA - 10)), pagado_por: persona('Carmen Soto'), cobrado: 10_480, devuelto: 0, devoluciones: [], pago_de_prueba: true } },
    entregado,
    {
      ...base,
      referencia: '4702',
      estado: 'cancelado_con_devolucion',
      creado_en: chile(hace(10 * DIA)),
      total_confirmado_en: chile(hace(10 * DIA - 5)),
      total: 10_480,
      pago: {
        estado: 'anulado',
        pagado_en: chile(hace(10 * DIA - 10)),
        pagado_por: persona(null),
        cobrado: 10_480,
        devuelto: 10_480,
        devoluciones: [{ motivo: 'cancelacion', producto: null, monto: 10_480, estado: 'en_curso', solicitada_en: chile(hace(9 * DIA)), hecha_en: null }],
        pago_de_prueba: true,
      },
    },
    {
      ...base,
      referencia: '4650',
      estado: 'cerrado',
      creado_en: chile(hace(20 * DIA)),
      total_confirmado_en: chile(hace(20 * DIA - 5)),
      total: 10_480,
      pago: {
        estado: 'devuelto_parcial',
        pagado_en: chile(hace(20 * DIA - 40)),
        pagado_por: persona('Carmen Soto'),
        cobrado: 10_480,
        devuelto: 10_480,
        devoluciones: [{ motivo: 'pago_tardio', producto: null, monto: 10_480, estado: 'hecha', solicitada_en: chile(hace(20 * DIA - 41)), hecha_en: chile(hace(20 * DIA - 60)) }],
        pago_de_prueba: false,
      },
      precios_de_ejemplo: false,
    },
    { ...base, referencia: '4100', estado: 'entregado', creado_en: chile(hace(100 * DIA)), total_confirmado_en: chile(hace(100 * DIA - 5)), total: 10_480, pago: { estado: 'aprobado', pagado_en: chile(hace(100 * DIA - 10)), pagado_por: persona('Carmen Soto'), cobrado: 10_480, devuelto: 0, devoluciones: [], pago_de_prueba: true } },
  ]
}

/** Uno de cada tipo, de más nuevo a más viejo, con MATU y con alguien que ya no está (3.4.9). */
const TIPOS: [string, 'persona' | 'matu' | 'salio', string | null, string | null][] = [
  ['abrio_la_ficha', 'persona', null, null],
  ['edito_la_ficha', 'persona', 'rutina', null],
  ['edito_la_ficha', 'persona', null, 'comunicacion'],
  ['edito_la_ficha', 'salio', null, null],
  ['quito_una_seccion', 'persona', null, 'movilidad'],
  ['compartio_la_ficha', 'persona', null, null],
  ['corto_un_enlace', 'persona', null, null],
  ['agrego_un_insumo', 'persona', null, null],
  ['edito_un_insumo', 'persona', null, null],
  ['dejo_de_seguir_un_insumo', 'persona', null, null],
  ['volvio_a_seguir_un_insumo', 'persona', null, null],
  ['quito_un_insumo', 'persona', null, null],
  ['anoto_una_compra', 'persona', null, null],
  ['aviso_de_insumo', 'matu', null, null],
  ['descarto_un_aviso', 'persona', null, null],
  ['resolvio_un_aviso', 'persona', null, null],
  ['cambio_la_direccion', 'persona', null, null],
  ['creo_un_pedido', 'persona', null, null],
  ['confirmo_un_pedido', 'persona', null, null],
  ['cambio_que_hacer_si_falta', 'persona', null, null],
  ['inicio_un_pago', 'persona', null, null],
  ['pago_aprobado', 'matu', null, null],
  ['pago_anulado', 'matu', null, null],
  ['cancelo_un_pedido', 'persona', null, null],
  ['un_tipo_que_no_existe', 'persona', null, null],
  ['dio_una_autorizacion', 'persona', null, null],
  ['retiro_una_autorizacion', 'salio', null, null],
  ['ficha_borrada', 'matu', null, null],
  ['dio_una_autorizacion', 'persona', null, null],
]

function historialDe(p: PersonaParaCopia, rol: Rol, modo: string | undefined, yo: string) {
  const todo = rol === 'admin'
  const otro = 'Rodrigo Soto'
  const hechos: { tipo: string; ocurrido_en: string; quien: { tipo: 'persona' | 'matu'; nombre: string | null; activo: boolean | null }; campo: string | null; seccion: string | null }[] = []
  const quien = (q: 'persona' | 'matu' | 'salio', i: number) =>
    q === 'matu' ? { tipo: 'matu' as const, nombre: null, activo: null } : q === 'salio' ? { tipo: 'persona' as const, nombre: null, activo: false } : { tipo: 'persona' as const, nombre: todo && i % 3 === 1 ? otro : yo, activo: true }
  const pasos = modo === 'datos-historial' ? 3 : 1
  for (let vuelta = 0; vuelta < pasos; vuelta++)
    TIPOS.forEach(([tipo, q, campo, seccion], i) => {
      const n = vuelta * TIPOS.length + i
      hechos.push({ tipo, ocurrido_en: hace(90 + n * (modo === 'datos-historial' ? 13 * 60 : 7 * 60)), quien: quien(q, i), campo, seccion })
    })
  if (modo === 'datos-historial') for (let i = 0; i < 12; i++) hechos.push({ tipo: i % 2 ? 'abrio_la_ficha' : 'edito_la_ficha', ocurrido_en: hace(95 * DIA + i * DIA), quien: quien('persona', 0), campo: i % 2 ? null : 'red_apoyo', seccion: null })
  for (const c of copiasDePersona.get(p.id) ?? []) hechos.push({ tipo: 'pidio_una_copia', ocurrido_en: c.en, quien: { tipo: 'persona', nombre: c.quien, activo: true }, campo: null, seccion: null })
  // El cuidador ve solo sus filas (D-54-6): ni las de otros ni las de MATU.
  const visibles = todo ? hechos : hechos.filter((h) => h.quien.tipo === 'persona' && h.quien.nombre === yo)
  visibles.sort((a, b) => new Date(b.ocurrido_en).getTime() - new Date(a.ocurrido_en).getTime())
  return { alcance: todo ? 'todo' : 'lo_tuyo', hechos: visibles.map((h) => ({ ...h, ocurrido_en: chile(h.ocurrido_en) })), hay_hechos_sin_asociar: modo === 'datos-sin-asociar' }
}

function copiaPersona(p: PersonaParaCopia, rol: Rol, u: CuentaParaCopia, generado: string) {
  const modo = u.modo
  const yo = `${u.nombre} Soto`
  const vacio = modo === 'datos-vacio'
  const retiroFicha = p.autorizaciones.plan_cuidado.retiro
  const fichaEstado = modo === 'datos-borrada' ? 'borrada' : retiroFicha ? 'retirada' : modo === 'datos-pausa' ? 'en_pausa' : 'disponible'
  const declaracion = (version: string) => ({ identificador: 'declaracion_cuidador_de_hecho', version, huella: 'b'.repeat(64) })
  const autorizacion = (finalidad: 'plan_cuidado' | 'consumo' | 'despacho', estado: string, otorgada: string, retirada: string | null, registro: string | null) => ({
    finalidad,
    estado,
    calidad_otorgante: finalidad === 'despacho' ? 'titular' : p.calidad === 'titular' ? 'cuidador_de_hecho' : p.calidad,
    version_politica: '0.16',
    declaracion: finalidad === 'despacho' ? null : declaracion('1.0'),
    aviso: finalidad === 'plan_cuidado' ? { identificador: 'aviso_cuidador_de_hecho', version: '1.0', huella: null } : null,
    registrada_por: persona(registro),
    otorgada_en: chile(otorgada),
    revision_vence_en: estado === 'vigente' || estado === 'revision_vencida' ? chile(estado === 'revision_vencida' ? hace(3 * DIA) : new Date(new Date(otorgada).getTime() + 365 * DIA * MIN).toISOString()) : null,
    retirada_en: retirada ? chile(retirada) : null,
    hay_documento_representante: finalidad === 'plan_cuidado' && modo === 'datos-admin',
  })
  const estadoDe = (f: 'plan_cuidado' | 'consumo') => (p.autorizaciones[f].retiro ? 'retirada' : modo === 'datos-pausa' ? 'revision_vencida' : 'vigente')
  const autorizaciones = vacio
    ? [autorizacion('plan_cuidado', 'vigente', hace(DIA), null, yo)]
    : [
        autorizacion('despacho', 'vigente', hace(6 * DIA), null, 'Carmen Soto'),
        autorizacion('consumo', estadoDe('consumo'), p.autorizaciones.consumo.otorgado_en, p.autorizaciones.consumo.retiro?.revocado_en ?? null, 'Carmen Soto'),
        autorizacion('plan_cuidado', estadoDe('plan_cuidado'), p.autorizaciones.plan_cuidado.otorgado_en, retiroFicha?.revocado_en ?? null, 'Carmen Soto'),
        // La que se renovó: la vigente es otra fila. La registró alguien que ya no está.
        autorizacion('plan_cuidado', 'reemplazada', hace(380 * DIA), hace(15 * DIA), null),
      ]
  if (modo === 'datos-sin-capa3') autorizaciones.splice(0, 1)
  // La ficha ya borrada: su autorización se retiró hace 100 días, y los insumos nunca se autorizaron.
  if (modo === 'datos-borrada') autorizaciones.splice(1, 2, autorizacion('plan_cuidado', 'retirada', hace(200 * DIA), hace(100 * DIA), 'Carmen Soto'))
  const campos = (['rutina', 'manejo_situaciones', 'red_apoyo'] as CampoApi[]).map((k) => {
    const c = p.campos[k]
    return { campo: k, texto: c.texto, escrito_por: c.texto ? nombrada(c.autor, c.autor?.nombre ? `${c.autor.nombre} Soto` : undefined) : null, actualizado_en: c.texto && c.en ? chile(c.en) : null }
  })
  const secciones = (Object.keys(p.secciones) as SeccionApi[]).map((s) => {
    const c = p.secciones[s]!
    return { seccion: s, texto: c.texto ?? '', escrito_por: nombrada(c.autor), creada_en: chile(c.en ?? hace(DIA)), actualizado_en: chile(c.en ?? hace(DIA)) }
  })
  const listos = campos.filter((c) => c.texto).length
  const ficha =
    fichaEstado === 'disponible'
      ? { estado: 'disponible', borrado_el: null, completitud: [0, 33, 67, 100][listos], campos, secciones }
      : { estado: fichaEstado, borrado_el: fichaEstado === 'retirada' && retiroFicha ? diaChile(retiroFicha.borrado_en) : null, completitud: null, campos: null, secciones: null }
  const enlaces = vacio
    ? []
    : p.accesos.map((a) => {
        const propias = p.aperturas.filter((x) => x.acceso.id === a.id)
        const abiertas = propias.filter((x) => x.tipo === 'apertura')
        return {
          nombre_relevo: a.nombre_relevo,
          motivo: a.motivo,
          campos: a.campos,
          secciones: a.secciones_adicionales,
          estado: estadoAcceso(a),
          creado_en: chile(a.creado_en),
          vence_en: chile(a.expira_en),
          cortado_en: a.revocado_en ? chile(a.revocado_en) : a.bloqueado ? chile(propias.find((x) => x.tipo === 'bloqueo')?.ocurrido_en ?? a.creado_en) : null,
          compartido_por: a.otorgado_por?.nombre ?? 'Carmen',
          usos: abiertas.length,
          ultimo_uso_en: abiertas[0] ? chile(abiertas[0].ocurrido_en) : null,
          aperturas: propias.map((x) => ({ tipo: x.tipo, ocurrido_en: chile(x.ocurrido_en), secciones: x.tipo === 'apertura' ? [] : null })),
        }
      })
  const direccion = direccionDe(p.direccion)
  return {
    formato: 'matu-datos/1',
    tipo: 'persona_cuidada',
    generado_en: generado,
    aviso: AVISO,
    persona: { nombre: p.nombre, nombre_pila: p.nombre_pila, nivel_apoyo: p.nivel_apoyo, direccion, alta_en: chile(hace(30 * DIA)) },
    autorizaciones,
    ficha,
    enlaces_relevo: enlaces,
    insumos: vacio ? { estado: 'disponible', borrado_el: null, lista: [], compras: [], avisos: [] } : insumosDe(p, modo, u.nombre),
    pedidos: pedidosDe(modo, direccion),
    historial: vacio ? { alcance: rol === 'admin' ? 'todo' : 'lo_tuyo', hechos: [], hay_hechos_sin_asociar: false } : historialDe(p, rol, modo, yo),
  }
}

// ---------------------------------------------------------------- la copia de la cuenta

function copiaCuenta(u: CuentaParaCopia, generado: string) {
  const modo = u.modo
  const editor = u.grupos.some((g) => g.rol === 'admin' || g.rol === 'cuidador')
  const desde = paraCopia(u.email, modo, editor, chile)
  const capa3 = modo !== 'datos-sin-capa3'
  const paga = modo === 'datos-pagador' || modo === 'datos-pedidos' || modo === 'datos-admin'
  const avisos = [
    { creado_en: chile(hace(2 * DIA)), enviado_en: chile(hace(2 * DIA - 1)), canal: 'correo', resultado: 'en_el_piloto_no_salio' },
    { creado_en: chile(hace(2 * DIA)), enviado_en: chile(hace(2 * DIA - 1)), canal: 'push', resultado: 'en_el_piloto_no_salio' },
    { creado_en: chile(hace(5 * DIA)), enviado_en: null, canal: 'push', resultado: 'no_salio' },
    { creado_en: chile(hace(20)), enviado_en: null, canal: 'correo', resultado: 'pendiente' },
  ]
  if (modo === 'datos-historial') for (let i = 0; i < 30; i++) avisos.push({ creado_en: chile(hace(6 * DIA + i * 3 * DIA)), enviado_en: chile(hace(6 * DIA + i * 3 * DIA - 1)), canal: 'correo', resultado: 'en_el_piloto_no_salio' })
  const pagos = [
    { grupo: 'Familia Soto', referencia: '4821', pagado_en: chile(hace(4 * DIA + 150)), cobrado: 37_260, devuelto: 5_290, tarjeta: { tipo: 'credito', ultimos4: '4242', cuotas: 3 }, pago_de_prueba: true },
    ...(modo === 'datos-pedidos'
      ? [
          { grupo: 'Familia Soto', referencia: '4910', pagado_en: chile(hace(3 * DIA - 10)), cobrado: 10_480, devuelto: 0, tarjeta: { tipo: 'debito', ultimos4: '0019', cuotas: 0 }, pago_de_prueba: true },
          { grupo: 'Familia Soto', referencia: '4650', pagado_en: chile(hace(20 * DIA - 40)), cobrado: 10_480, devuelto: 10_480, tarjeta: null, pago_de_prueba: false },
        ]
      : []),
  ]
  const condiciones = [
    { grupo: 'Familia Soto', referencia: '4821', version: '1.0', huella: 'c'.repeat(64), aceptadas_en: chile(hace(4 * DIA + 152)) },
    ...(modo === 'datos-pedidos' ? [{ grupo: 'Familia Soto', referencia: null, version: '1.0', huella: 'd'.repeat(64), aceptadas_en: chile(hace(2 * DIA - 3)) }] : []),
  ]
  return {
    formato: 'matu-datos/1',
    tipo: 'cuenta',
    generado_en: generado,
    aviso: AVISO,
    cuenta: { nombre: `${u.nombre} Soto`, correo: u.email, celular: u.telefono, celular_confirmado: u.celularVerificado, canal_codigos: u.canal, creada_en: chile(hace(40 * DIA)) },
    politica: u.politica ? { version: u.politica.version, huella: u.politica.huella, aceptada_en: chile(u.politica.aceptada_en) } : null,
    grupos: u.grupos.map((g) => ({ nombre: g.nombre, rol: g.rol, unido_en: chile(hace(30 * DIA)), puede_ver_ficha: g.rol === 'pagador' ? g.puede_ver_plan : null })),
    dispositivos: desde.dispositivos,
    preferencia_avisos: desde.preferencia_avisos,
    eventos: desde.eventos,
    avisos_enviados: modo === 'datos-vacio' ? [] : avisos,
    envio_simulado: true,
    pagos: capa3 ? (paga ? pagos : []) : null,
    condiciones_aceptadas: capa3 ? (paga ? condiciones : []) : null,
  }
}

// ---------------------------------------------------------------- las rutas

/** Atiende las dos rutas de MATU-54. `false` si la ruta no es suya. */
export function atenderMisDatos(req: IncomingMessage, res: ServerResponse, r: Responder, u: CuentaParaCopia): boolean {
  if ((req.method ?? 'GET') !== 'GET') return false
  const ruta = (req.url ?? '').split('?')[0]
  if (ruta === '/v1/yo/datos') {
    res.setHeader('Cache-Control', 'no-store')
    if (limite(res, r, u.email, u.modo)) return true
    // La fila de «Pediste una copia de tus datos» se escribe antes de leer: la copia ya la trae.
    anotarCopia(u.email)
    const generado = chile(new Date().toISOString())
    entregar(res, 'matu-cuenta', copiaCuenta(u, generado))
    return true
  }
  const m = /^\/v1\/personas-cuidadas\/([^/]+)\/datos$/.exec(ruta)
  if (!m) return false
  res.setHeader('Cache-Control', 'no-store')
  const g = u.grupos.find((x) => x.id === req.headers['x-grupo-id'])
  const p = g?.personas.find((x) => x.id === decodeURIComponent(m[1]))
  // 404 primero: sin grupo, pagador u observador, o persona que no es del grupo. No cuenta en el límite.
  if (!g || !p || (g.rol !== 'admin' && g.rol !== 'cuidador')) return r.problema(res, 404, '/errores/no-encontrado'), true
  if (limite(res, r, u.email, u.modo)) return true
  const generado = chile(new Date().toISOString())
  const lista = copiasDePersona.get(p.id) ?? []
  lista.push({ quien: `${u.nombre} Soto`, en: new Date().toISOString() })
  copiasDePersona.set(p.id, lista)
  entregar(res, 'matu-datos', copiaPersona(p, g.rol, u, generado))
  return true
}

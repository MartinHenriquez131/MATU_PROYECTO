// MATU-80 · Carga básica del flujo de pedido (estrategia de pruebas, sección 2): catálogo, pedido y pago con la
// pasarela falsa, 50 usuarios virtuales y el percentil 95 bajo 800 ms. Instructivo: infra/carga/README.md.
//
// Cada usuario virtual es una familia de carga (cargaNN@example.com, de infra/carga/preparar_carga.py). Entra una
// vez y repite: ve el catálogo, arma un pedido de un pañal del «Comercio de Carga», confirma el total, lo paga y
// vuelve de Webpay. Con PASARELA_PAGO=falsa la venta se aprueba sola al volver: nunca llama a Transbank.
//
// Variables, del lado de quien lo corre (nunca en este archivo):
//   CARGA_CONTRASENA  la contraseña de las cuentas de carga (la SEMILLA_CONTRASENA de preparar_carga.py). Obligatoria
//   BASE_URL          la API local, por omisión http://localhost:8000. Solo localhost o 127.0.0.1
//   CARGA_USUARIOS    usuarios virtuales, por omisión 50 (tantos como cuentas preparadas)
//   CARGA_DURACION    por omisión 3m
//   CARGA_COMERCIO    el nombre_fantasia del comercio de carga, por omisión «Comercio de Carga»

import http from 'k6/http'
import { check, fail, sleep } from 'k6'
import exec from 'k6/execution'

const BASE_URL = (__ENV.BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')
const CONTRASENA = __ENV.CARGA_CONTRASENA || ''
const USUARIOS = parseInt(__ENV.CARGA_USUARIOS || '50', 10)
const DURACION = __ENV.CARGA_DURACION || '3m'
const COMERCIO = __ENV.CARGA_COMERCIO || 'Comercio de Carga'
const TELEFONO = '+56 9 5555 0177'

// Nunca contra staging, la demo de Railway ni Transbank: solo una API local con la pasarela falsa
const HOST = BASE_URL.replace(/^https?:\/\//, '').split(/[/:]/)[0]
if (!['localhost', '127.0.0.1'].includes(HOST)) {
  throw new Error('BASE_URL debe ser una API local (localhost o 127.0.0.1): la carga nunca va a staging ni a la demo')
}

// Los pasos del flujo, con la etiqueta `paso` que lleva cada petición. Los de PASOS_RNF05 son el flujo de RNF-05
// (arquitectura, sección 2.2: catálogo a pedido a pago bajo 800 ms en p95 con 50 usuarios), y cada uno tiene su umbral
// propio para saber cuál es el lento (hallazgo H4 de Martín, 17-11). `entrar` no es parte de RNF-05: se mide, pero no
// se exige (ver el umbral más abajo).
//
// `retorno` lleva la misma meta de 800 ms aunque sea la vuelta de Webpay: con PASARELA_PAGO=falsa la venta se aprueba
// en memoria (payments/infrastructure/pasarela_falsa.py, sin esperas ni red), así que el paso mide solo el trabajo de
// MATU al cerrar el pago. Con Transbank de verdad se sumaría la latencia de su API, que esta carga no mide ni puede
// medir (nunca va contra Transbank)
const PASOS_RNF05 = ['catalogo', 'pedido', 'confirmar', 'pagar', 'retorno']
const PASOS = ['entrar', ...PASOS_RNF05]
const META_P95_MS = 800

function umbralesPorPaso() {
  const umbrales = {}
  for (const paso of PASOS_RNF05) umbrales[`http_req_duration{paso:${paso}}`] = [`p(95)<${META_P95_MS}`]
  // `entrar` es el inicio de sesión: argon2id gasta CPU a propósito para que adivinar contraseñas cueste, y los 50
  // usuarios entran a la vez al partir, así que su tiempo es alto por diseño. Además ocurre una vez por usuario, no en
  // cada pedido. Un umbral de 800 ms mentiría sobre RNF-05 y uno holgado mentiría sobre la meta: `max>=0` siempre se
  // cumple, y solo está para que k6 calcule la submétrica del paso y salga en el resumen
  umbrales['http_req_duration{paso:entrar}'] = ['max>=0']
  return umbrales
}

export const options = {
  scenarios: {
    pedido: { executor: 'constant-vus', vus: USUARIOS, duration: DURACION, gracefulStop: '30s' },
  },
  thresholds: {
    // El umbral de la estrategia de pruebas: p95 bajo 800 ms en todas las peticiones del script. Incluye `entrar`, así
    // que es más exigente que RNF-05: si falla solo este y pasan los de cada paso, el culpable es el inicio de sesión
    http_req_duration: [`p(95)<${META_P95_MS}`],
    // El mismo umbral por paso: dice cuál de los pasos del flujo es el lento
    ...umbralesPorPaso(),
    // El flujo de punta a punta tiene que funcionar, no solo responder rápido
    checks: ['rate>0.99'],
    http_req_failed: ['rate<0.01'],
  },
  // Se guardan los cuerpos porque el flujo los lee con .json() (ids, etag y token de la venta). k6 no los muestra
  // en el resumen, y el script nunca los imprime
  discardResponseBodies: false,
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
}

const JSON_CT = { 'Content-Type': 'application/json' }

function uuid4() {
  // Una Idempotency-Key nueva por intento, como la pantalla
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

export function setup() {
  if (!CONTRASENA) fail('Falta CARGA_CONTRASENA: la contraseña de las cuentas de preparar_carga.py')
  const salud = http.get(`${BASE_URL}/v1/salud`)
  if (salud.status !== 200) fail('La API local no responde en /v1/salud')
  const condiciones = http.get(`${BASE_URL}/v1/condiciones-pedido`)
  if (condiciones.status !== 200) fail('La API no tiene la capa 3 encendida (CAPA3_HABILITADA=true)')
  const c = condiciones.json()
  return { condiciones: { version: c.version, huella: c.huella } }
}

// Lo que cada usuario virtual guarda entre iteraciones: su sesión, su grupo y su persona
let sesion = null

function entrar() {
  const numero = String(((exec.vu.idInTest - 1) % USUARIOS) + 1).padStart(2, '0')
  const r = http.post(
    `${BASE_URL}/v1/sesiones`,
    JSON.stringify({ email: `carga${numero}@example.com`, contrasena: CONTRASENA }),
    { headers: JSON_CT, tags: { paso: 'entrar' } },
  )
  if (!check(r, { 'entra': (x) => x.status === 200 })) fail(`la cuenta carga${numero} no entra: ¿corriste preparar_carga.py?`)
  const token = r.json('access_token')
  const auth = { Authorization: `Bearer ${token}` }
  const grupos = http.get(`${BASE_URL}/v1/grupos`, { headers: auth, tags: { paso: 'entrar' } })
  const grupo = grupos.json('0.id')
  const personas = http.get(`${BASE_URL}/v1/grupos/${grupo}/personas-cuidadas`, {
    headers: { ...auth, 'X-Grupo-Id': grupo },
    tags: { paso: 'entrar' },
  })
  sesion = { token, grupo, persona: personas.json('0.id') }
}

function cabeceras(extra = {}) {
  return { ...JSON_CT, Authorization: `Bearer ${sesion.token}`, 'X-Grupo-Id': sesion.grupo, ...extra }
}

function crearPedido(oferta) {
  const ruta = `${BASE_URL}/v1/personas-cuidadas/${sesion.persona}/pedidos`
  const cuerpo = JSON.stringify({ lineas: [{ oferta_id: oferta, cantidad: 1 }] })
  let r = http.post(ruta, cuerpo, { headers: cabeceras({ 'Idempotency-Key': uuid4() }), tags: { paso: 'pedido' } })
  if (r.status === 409) {
    // Un pedido sin pagar de una corrida anterior (C4): se cancela sin costo y se arma de nuevo
    const abierto = http.get(`${BASE_URL}/v1/personas-cuidadas/${sesion.persona}/pedido-en-curso`, {
      headers: cabeceras(),
      tags: { paso: 'pedido' },
    })
    if (abierto.status === 200) {
      http.post(`${BASE_URL}/v1/pedidos/${abierto.json('id')}/cancelar`, null, {
        headers: cabeceras({ 'Idempotency-Key': uuid4() }),
        tags: { paso: 'pedido' },
      })
    }
    r = http.post(ruta, cuerpo, { headers: cabeceras({ 'Idempotency-Key': uuid4() }), tags: { paso: 'pedido' } })
  }
  return r
}

export default function (datos) {
  if (sesion === null) entrar()

  // 1. El catálogo, y la oferta del comercio de carga
  const catalogo = http.get(`${BASE_URL}/v1/catalogo`, { headers: cabeceras(), tags: { paso: 'catalogo' } })
  if (catalogo.status === 401) {
    // El access token dura 15 minutos: se vuelve a entrar
    entrar()
    return
  }
  check(catalogo, { 'catálogo 200': (x) => x.status === 200 })
  let oferta = null
  for (const categoria of catalogo.json('categorias') || []) {
    for (const producto of categoria.productos) {
      for (const o of producto.comercios) {
        if (o.nombre_fantasia === COMERCIO && o.disponible) oferta = o.oferta_id
      }
    }
  }
  if (!check(oferta, { 'el comercio de carga tiene stock': (x) => x !== null })) return

  // 2. El carrito y el total confirmado (precios exactos más un envío, vale 15 minutos)
  const creado = crearPedido(oferta)
  if (!check(creado, { 'pedido 201': (x) => x.status === 201 })) return
  const confirmado = http.post(
    `${BASE_URL}/v1/pedidos/${creado.json('id')}/confirmar`,
    JSON.stringify({ telefono_contacto: TELEFONO }),
    { headers: cabeceras({ 'Idempotency-Key': uuid4() }), tags: { paso: 'confirmar' } },
  )
  if (!check(confirmado, { 'total confirmado 200': (x) => x.status === 200 })) return

  // 3. Pagar: acepta las condiciones y abre la venta en la pasarela falsa
  const pago = http.post(
    `${BASE_URL}/v1/pedidos/${confirmado.json('id')}/pagar`,
    JSON.stringify({ acepta_condiciones: true, condiciones: datos.condiciones }),
    {
      headers: cabeceras({ 'Idempotency-Key': uuid4(), 'If-Match': confirmado.json('etag') }),
      tags: { paso: 'pagar' },
    },
  )
  if (!check(pago, { 'pago abierto': (x) => x.status === 200 || x.status === 201 })) return

  // 4. La vuelta de Webpay, sin la sesión: la falsa aprueba el total confirmado
  const vuelta = http.post(`${BASE_URL}/v1/pagos/retorno`, JSON.stringify({ token_ws: pago.json('token') }), {
    headers: JSON_CT,
    tags: { paso: 'retorno' },
  })
  check(vuelta, { 'pagado': (x) => x.status === 200 && x.json('resultado') === 'aprobado' })

  // El tiempo de una persona entre un pedido y el siguiente
  sleep(1)
}

// --- El resumen por paso --------------------------------------------------------------------------------------
// Reemplaza el resumen de k6 en la terminal por uno que muestra p50, p95 y p99 de cada paso y si cumple su umbral.
// Solo usa métricas agregadas: ningún correo, token, id ni cuerpo de respuesta llega a `datos.metrics`. El código de
// salida de k6 no cambia: sigue siendo distinto de 0 si un umbral falla

function ms(valor) {
  return typeof valor === 'number' ? `${Math.round(valor)} ms` : '-'
}

function cumple(metrica) {
  const umbrales = Object.values((metrica && metrica.thresholds) || {})
  if (umbrales.length === 0) return '-'
  return umbrales.every((u) => u.ok) ? 'cumple' : 'NO CUMPLE'
}

function resumenPorPaso(datos) {
  const filas = [['paso', 'meta p95', 'p50', 'p95', 'p99', 'umbral']]
  for (const paso of PASOS) {
    const exigido = PASOS_RNF05.includes(paso)
    const m = datos.metrics[`http_req_duration{paso:${paso}}`]
    const v = (m && m.values) || {}
    const estado = !m ? 'sin datos' : exigido ? cumple(m) : 'no se exige'
    const meta = exigido ? `< ${META_P95_MS} ms` : 'se mide'
    filas.push([paso, meta, ms(v.med), ms(v['p(95)']), ms(v['p(99)']), estado])
  }
  const total = datos.metrics.http_req_duration
  const vt = (total && total.values) || {}
  filas.push(['total', `< ${META_P95_MS} ms`, ms(vt.med), ms(vt['p(95)']), ms(vt['p(99)']), cumple(total)])

  const anchos = filas[0].map((_, i) => Math.max(...filas.map((f) => f[i].length)))
  const linea = (f) => f.map((celda, i) => celda.padEnd(anchos[i])).join('  ')
  const tabla = filas.map(linea)
  tabla.splice(1, 0, anchos.map((a) => '-'.repeat(a)).join('  '))

  const chequeos = datos.metrics.checks
  const fallidas = datos.metrics.http_req_failed
  const iteraciones = datos.metrics.iterations
  const pie = [
    `checks: ${chequeos ? (chequeos.values.rate * 100).toFixed(2) : '-'} % (meta > 99 %), ${cumple(chequeos)}`,
    `http_req_failed: ${fallidas ? (fallidas.values.rate * 100).toFixed(2) : '-'} % (meta < 1 %), ${cumple(fallidas)}`,
    `iteraciones completas: ${iteraciones ? iteraciones.values.count : 0}`,
  ]
  return ['', 'MATU-80 · Tiempos por paso (RNF-05)', '', ...tabla, '', ...pie, ''].join('\n')
}

export function handleSummary(datos) {
  return { stdout: resumenPorPaso(datos) }
}

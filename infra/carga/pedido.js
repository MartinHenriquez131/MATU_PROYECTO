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

export const options = {
  scenarios: {
    pedido: { executor: 'constant-vus', vus: USUARIOS, duration: DURACION, gracefulStop: '30s' },
  },
  thresholds: {
    // El umbral de la estrategia de pruebas: p95 bajo 800 ms en todas las peticiones del flujo
    http_req_duration: ['p(95)<800'],
    // El flujo de punta a punta tiene que funcionar, no solo responder rápido
    checks: ['rate>0.99'],
    http_req_failed: ['rate<0.01'],
  },
  // Los cuerpos de las respuestas traen tokens: k6 no los guarda ni los muestra
  discardResponseBodies: false,
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'max'],
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

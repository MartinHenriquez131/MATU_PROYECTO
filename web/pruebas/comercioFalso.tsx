// La API de la consola del comercio para las pruebas de MATU-63: el cliente real (`apiFamilia`, con
// sus interceptores y `leerFallo`) sobre un adaptador de mentira con estado en memoria. Solo datos
// sintéticos: un comercio de prueba y pedidos inventados.
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import type { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { vi } from 'vitest'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import type { ParteResumen, ParteVista, ProductoDelComercio } from '../src/compartido/api/comercio'
import { apiFamilia } from '../src/compartido/api/sesion'
import type { RespuestaFalsa } from './apiFalsa'

export const ID = {
  porPreparar: '6f1d0c3e-0000-4000-8000-000000000631',
  atrasada: '6f1d0c3e-0000-4000-8000-000000000632',
  preparando: '6f1d0c3e-0000-4000-8000-000000000633',
  lista: '6f1d0c3e-0000-4000-8000-000000000634',
  retirada: '6f1d0c3e-0000-4000-8000-000000000635',
  cancelada: '6f1d0c3e-0000-4000-8000-000000000636',
}

/** El reloj del servidor en las pruebas: 13/11/2026, 14:20 de Chile (17:20 UTC). */
export const AHORA = new Date('2026-11-13T17:20:00Z')
const en = (min: number) => new Date(AHORA.getTime() + min * 60_000).toISOString()

let n = 0
const linea = (nombre: string, presentacion: string, cantidad: number, estado_linea: ParteVista['lineas'][number]['estado_linea'] = 'pendiente', unidades_faltantes = 0) => ({
  id: `6f1d0c3e-0000-4000-8000-1${String(++n).padStart(11, '0')}`,
  producto: { nombre, presentacion },
  cantidad,
  estado_linea,
  unidades_faltantes,
})

function parte(id: string, referencia: string, estado: ParteVista['estado'], lineas: ParteVista['lineas'], extra: Partial<ParteVista> = {}): ParteVista {
  return {
    id,
    referencia,
    estado,
    enviado_en: en(-10),
    preparar_antes_de: en(130),
    estado_codigo: estado === 'lista' ? 'vigente' : estado === 'retirada' ? 'usado' : 'sin_codigo',
    numero_lineas: lineas.length,
    retirada_en: null,
    cancelada_en: null,
    motivo_cancelacion: null,
    lineas,
    ...extra,
  }
}

/** Las partes de ejemplo, una por estado, más una atrasada. */
export function partesDeEjemplo(): ParteVista[] {
  return [
    parte(ID.porPreparar, 'R8T2WQ', 'enviada', [linea('Crema protectora 200 g', 'Pote de 200 gramos', 1)]),
    parte(ID.atrasada, 'K4M7XP', 'enviada', [linea('Pañal adulto M x30', 'Paquete de 30 unidades', 2), linea('Toallitas húmedas x80', 'Paquete de 80 unidades', 1)], {
      enviado_en: en(-140),
      preparar_antes_de: en(-20),
    }),
    parte(ID.preparando, 'H6N3VD', 'preparando', [linea('Pañal adulto M x30', 'Paquete de 30 unidades', 1), linea('Suplemento vainilla x12', 'Caja de 12 unidades', 3)]),
    parte(ID.lista, 'P5Q8ZA', 'lista', [linea('Pañal adulto M x30', 'Paquete de 30 unidades', 2, 'preparada'), linea('Suplemento vainilla x12', 'Caja de 12 unidades', 3, 'faltante', 1)]),
    parte(ID.retirada, 'T8F2HJ', 'retirada', [linea('Pañal adulto M x30', 'Paquete de 30 unidades', 1, 'preparada')], { retirada_en: en(-40) }),
    parte(ID.cancelada, 'Z5V7NQ', 'cancelada', [linea('Crema protectora 200 g', 'Pote de 200 gramos', 2)], { cancelada_en: en(-60) }),
  ]
}

export function productosDeEjemplo(): ProductoDelComercio[] {
  const p = (oferta_id: string, nombre: string, presentacion: string, precio: number, stock: number, apartado: number, disponible = true): ProductoDelComercio => ({
    oferta_id,
    nombre,
    presentacion,
    precio,
    stock,
    apartado,
    disponibles: Math.max(0, stock - apartado),
    disponible,
    etag: '"v1"',
  })
  return [
    p('0f1d0c3e-0000-4000-8000-000000000001', 'Toallitas húmedas x80', 'Paquete de 80 unidades', 3290, 0, 0),
    p('0f1d0c3e-0000-4000-8000-000000000002', 'Pañal adulto M x30', 'Paquete de 30 unidades', 12990, 14, 3),
    p('0f1d0c3e-0000-4000-8000-000000000003', 'Suplemento vainilla x12', 'Caja de 12 unidades', 18990, 2, 4),
    p('0f1d0c3e-0000-4000-8000-000000000004', 'Crema protectora 200 g', 'Pote de 200 gramos', 6490, 5, 1, false),
  ]
}

const resumen = (p: ParteVista): ParteResumen => {
  const { lineas, ...resto } = p
  return { ...resto, numero_lineas: lineas.length }
}

export interface Peticion {
  linea: string
  cuerpo: unknown
  ifMatch: string | null
}

type Sobre = (linea: string, cuerpo: unknown) => RespuestaFalsa | undefined

/**
 * Monta la API. `tipo` es el de la cuenta en `/renovar` (`null`: la cookie venció). `sobre` responde
 * antes que el estado en memoria, para los errores de cada prueba.
 */
export function apiComercio({
  tipo = 'comercio',
  ficticio = true,
  partes = partesDeEjemplo(),
  productos = productosDeEjemplo(),
  sobre,
}: {
  tipo?: 'comercio' | 'familia' | null
  ficticio?: boolean
  partes?: ParteVista[]
  productos?: ProductoDelComercio[]
  sobre?: Sobre
} = {}) {
  const peticiones: Peticion[] = []
  const estado = { partes, productos, version: 1 }
  const responder = (config: InternalAxiosRequestConfig, r: RespuestaFalsa): AxiosResponse => {
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: { date: AHORA.toUTCString(), ...(r.cabeceras ?? {}) }, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  axios.defaults.adapter = async (config) =>
    tipo === null
      ? responder(config, { status: 401, cuerpo: { type: '/errores/sesion-expirada', status: 401 } })
      : responder(config, { status: 200, cuerpo: { access_token: 'token-sintetico', token_type: 'bearer', expira_en: 900, tipo_cuenta: tipo } })
  const conVersion = (p: ParteVista): RespuestaFalsa => ({ status: 200, cuerpo: structuredClone(p), cabeceras: { etag: `"v${++estado.version}"` } })
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const linea = `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`
    const cuerpo = typeof config.data === 'string' && config.data ? (JSON.parse(config.data) as unknown) : null
    const ifMatch = config.headers?.get?.('If-Match')
    peticiones.push({ linea, cuerpo, ifMatch: typeof ifMatch === 'string' ? ifMatch : null })
    const especial = sobre?.(linea, cuerpo)
    if (especial) return responder(config, especial)
    if (linea === 'POST /v1/sesiones') return responder(config, { status: 200, cuerpo: { access_token: 'token-sintetico', token_type: 'bearer', expira_en: 900, tipo_cuenta: tipo ?? 'comercio' } })
    if (linea === 'POST /v1/sesiones/cerrar') return responder(config, { status: 204 })
    if (linea === 'GET /v1/comercio') return responder(config, { status: 200, cuerpo: { nombre_fantasia: 'Almacén El Ejemplo', ficticio, contacto: 'contacto@example.com' } })
    if (linea === 'GET /v1/comercio/partes') return responder(config, { status: 200, cuerpo: { partes: estado.partes.map(resumen) } })
    if (linea === 'GET /v1/comercio/productos') return responder(config, { status: 200, cuerpo: { productos: structuredClone(estado.productos) } })
    const m = /^(GET|POST|PUT) \/v1\/comercio\/partes\/([^/]+)(?:\/(preparar|listo|lineas\/([^/]+)))?$/.exec(linea)
    const p = m ? estado.partes.find((x) => x.id === m[2]) : undefined
    if (m && p) {
      if (m[1] === 'GET') return responder(config, conVersion(p))
      if (m[3] === 'preparar') {
        p.estado = 'preparando'
        return responder(config, conVersion(p))
      }
      if (m[4]) {
        const l = p.lineas.find((x) => x.id === m[4])!
        const c = cuerpo as { estado: 'preparada' | 'faltante'; unidades_faltantes?: number }
        l.estado_linea = c.estado
        l.unidades_faltantes = c.estado === 'faltante' ? (c.unidades_faltantes ?? l.cantidad) : 0
        return responder(config, conVersion(p))
      }
      if (m[3] === 'listo') {
        const ninguno = p.lineas.every((l) => l.estado_linea === 'faltante' && l.unidades_faltantes >= l.cantidad)
        p.estado = ninguno ? 'cancelada' : 'lista'
        if (ninguno) p.motivo_cancelacion = 'producto_faltante'
        if (!ninguno) p.estado_codigo = 'vigente'
        return responder(config, conVersion(p))
      }
    }
    const prod = /^PATCH \/v1\/comercio\/productos\/([^/]+)$/.exec(linea)
    const pr = prod ? estado.productos.find((x) => x.oferta_id === prod[1]) : undefined
    if (pr) {
      Object.assign(pr, cuerpo as object)
      pr.disponibles = Math.max(0, pr.stock - pr.apartado)
      pr.etag = `"v${++estado.version}"`
      return responder(config, { status: 200, cuerpo: { ...pr } })
    }
    return responder(config, { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404 } })
  }
  return { peticiones, estado, lineas: () => peticiones.map((x) => x.linea) }
}

/** Anota lo que se escribiría en el almacenamiento del navegador: nada de la consola va ahí. */
export function vigilarAlmacenamiento() {
  const claves: string[] = []
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    claves.push(clave)
  })
  return claves
}

/** La app con las regiones vivas antes, como en main.tsx. Las regiones se buscan por `aria-live`. */
export function conRegionesVivas(pantalla: ReactElement) {
  render(
    <>
      <RegionesVivas />
      {pantalla}
    </>,
  )
  return { amable: document.querySelector<HTMLElement>('[aria-live="polite"]')!, urgente: document.querySelector<HTMLElement>('[aria-live="assertive"]')! }
}

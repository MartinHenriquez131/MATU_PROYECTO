// MATU-54, «Mis datos»: la copia de la persona cuidada y la de la propia cuenta (docs/api/openapi.json;
// explicación en docs/api/propuestos/mis-datos.openapi.yaml y decisiones 342 a 400 de docs/api/README.md).
//
// Un solo GET por copia (decisión 343): la respuesta se pide como texto, la pantalla la lee con
// `JSON.parse` y «Descargar» guarda ese mismo texto, sin volver a llamar a la API. El texto vive solo
// en la memoria de la pantalla que lo pidió: nunca va al almacenamiento del navegador, a la URL, a
// `history.state` ni al título. Los tipos salen de `openapi.json` (decisión 396), en
// familia.openapi.ts, regenerado con `npm run contrato:familia`.
import type { components } from './familia.openapi'
import { apiFamilia } from './sesion'

type S = components['schemas']

/** RFC 3339 con el desfase de Chile, por ejemplo `2026-11-12T10:05:00-03:00` (decisión 349). */
export type Instante = string
/** `AAAA-MM-DD`, sin hora. */
export type Dia = string

/** Quien ya no está en el grupo llega con `nombre: null` y `activo: false`. */
export type PersonaNombrada = S['PersonaNombrada']

export type CampoCopiaApi = S['CampoCopia']['campo']
export type SeccionCopiaApi = S['SeccionCopia']['seccion']
export type FinalidadCopia = S['AutorizacionCopia']['finalidad']
export type EstadoBloque = S['FichaCopia']['estado']

// ---------------------------------------------------------------- la copia de la persona

export type CopiaDatosPersona = S['CopiaDatosPersona']
export type DatosPersonaCopia = S['DatosPersonaCopia']
export type DireccionCopia = S['DireccionCopia']
export type AutorizacionCopia = S['AutorizacionCopia']
export type FichaCopia = S['FichaCopia']
export type CampoCopia = S['CampoCopia']
export type SeccionCopia = S['SeccionCopia']
export type EnlaceRelevoCopia = S['EnlaceRelevoCopia']
export type AperturaCopia = S['AperturaCopia']
export type InsumosCopia = S['InsumosCopia']
export type InsumoCopia = S['InsumoCopia']
export type CompraCopia = S['CompraCopia']
export type AvisoInsumoCopia = S['AvisoInsumoCopia']
export type PedidoCopia = S['PedidoCopia']
export type EstadoPedidoCopia = S['PedidoCopia']['estado']
export type EntregaCopia = S['EntregaCopia']
export type PagoPedidoCopia = S['PagoPedidoCopia']
export type DevolucionCopia = S['DevolucionCopia']
export type HistorialCopia = S['HistorialCopia']
export type QuienCopia = S['QuienCopia']
/**
 * Los tipos del historial que la pantalla sabe decir (3.4.9). Los siete de MATU-63 (despacho y
 * retracto) ya están en el contrato, pero todavía no tienen frase ni ícono especificados: hasta
 * entonces `seMuestraHecho` los deja fuera, como a cualquier tipo que no conoce.
 */
export type TipoHecho = Exclude<
  S['HechoCopia']['tipo'],
  'devolucion_a_la_tarjeta' | 'pidio_un_retracto' | 'codigo_de_retiro_generado' | 'pedido_en_camino' | 'pedido_entregado' | 'pedido_no_entregado' | 'retracto_resuelto'
>
/**
 * Un hecho del historial. El contrato cierra la lista de tipos, pero la pantalla ignora uno que no
 * conoce sin romperse (3.4.9): aquí `tipo` también admite otro texto.
 */
export type HechoCopia = Omit<S['HechoCopia'], 'tipo'> & { tipo: TipoHecho | (string & {}) }

// ---------------------------------------------------------------- la copia de la cuenta

export type CopiaDatosCuenta = S['CopiaDatosCuenta']
export type CuentaCopia = S['CuentaCopia']
export type GrupoCopia = S['GrupoCopia']
/** F2 (decisión 401): un grupo del que la cuenta salió, sin su nombre. */
export type GrupoQueDejasteCopia = S['GrupoQueDejasteCopia']
export type DispositivoCopia = S['DispositivoCopia']
export type EventoCuentaCopia = S['EventoCuentaCopia']
export type AvisoEnviadoCopia = S['AvisoEnviadoCopia']
export type PagoCuentaCopia = S['PagoCuentaCopia']
export type CondicionesCopia = S['CondicionesCopia']

// ---------------------------------------------------------------- pedir la copia

/** Lo que la pantalla guarda en su memoria: el texto tal cual llegó, su nombre de archivo y lo leído. */
export interface Copia<T> {
  texto: string
  nombreArchivo: string
  datos: T
}

const NOMBRE_VALIDO = /^matu-(datos|cuenta)-\d{4}-\d{2}-\d{2}\.json$/

/**
 * El nombre del archivo, desde `Content-Disposition: inline; filename="…"` (C9). Si la cabecera no se
 * puede leer, el mismo nombre con el día de `generado_en`, que ya viene en hora de Chile. Nunca lleva
 * el nombre de la persona.
 */
export function nombreDeArchivo(cabecera: unknown, prefijo: 'matu-datos' | 'matu-cuenta', generadoEn: string): string {
  const nombre = typeof cabecera === 'string' ? /filename="([^"]+)"/.exec(cabecera)?.[1] : undefined
  if (nombre && NOMBRE_VALIDO.test(nombre) && nombre.startsWith(`${prefijo}-`)) return nombre
  const dia = /^\d{4}-\d{2}-\d{2}/.exec(generadoEn)?.[0] ?? 'copia'
  return `${prefijo}-${dia}.json`
}

async function pedirCopia<T extends { formato: string; tipo: string; generado_en: string }>(
  url: string,
  tipo: T['tipo'],
  prefijo: 'matu-datos' | 'matu-cuenta',
): Promise<Copia<T>> {
  // Como texto, sin que Axios lo interprete: «Descargar» guarda estos mismos caracteres.
  const r = await apiFamilia.get<string>(url, { responseType: 'text', transformResponse: [(d: unknown) => d] })
  const texto = typeof r.data === 'string' ? r.data : JSON.stringify(r.data)
  const datos = JSON.parse(texto) as T
  if (!datos || datos.formato !== 'matu-datos/1' || datos.tipo !== tipo || typeof datos.generado_en !== 'string') throw new Error('Copia con otra forma')
  return { texto, nombreArchivo: nombreDeArchivo(r.headers?.['content-disposition'], prefijo, datos.generado_en), datos }
}

/** `GET /v1/personas-cuidadas/{persona_id}/datos`, con `X-Grupo-Id` del grupo elegido (sesion.ts). */
export const pedirCopiaPersona = (personaId: string) =>
  pedirCopia<CopiaDatosPersona>(`/v1/personas-cuidadas/${encodeURIComponent(personaId)}/datos`, 'persona_cuidada', 'matu-datos')

/** `GET /v1/yo/datos`. `X-Grupo-Id`, si va, se ignora. */
export const pedirCopiaCuenta = () => pedirCopia<CopiaDatosCuenta>('/v1/yo/datos', 'cuenta', 'matu-cuenta')

/**
 * Guarda el texto en un archivo (3.7): un `Blob` con los mismos caracteres, un `<a download>` que no se
 * agrega a la página y `revokeObjectURL` de inmediato. Si el navegador no deja crear el `Blob` o la
 * URL, lanza, y el diálogo muestra el error.
 */
export function guardarArchivo(texto: string, nombre: string): void {
  const blob = new Blob([texto], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = url
    a.download = nombre
    a.rel = 'noopener'
    a.click()
  } finally {
    URL.revokeObjectURL(url)
  }
}

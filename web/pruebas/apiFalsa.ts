// Una API de mentira para las pruebas: reemplaza el adaptador de Axios de una instancia, así la
// pantalla pasa por su cliente real (interceptores y `leerFallo`) sin red. Solo datos sintéticos.
import { AxiosError, type AxiosInstance, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'

export interface RespuestaFalsa {
  status: number
  cuerpo?: unknown
  /** En minúsculas, como las entrega el navegador (por ejemplo `retry-after`). */
  cabeceras?: Record<string, string>
}

/** Responde en orden; la última se repite. Devuelve las peticiones (método y ruta, sin cuerpo). */
export function responderCon(instancia: AxiosInstance, ...respuestas: RespuestaFalsa[]) {
  const pedidas: string[] = []
  instancia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const r = respuestas[Math.min(pedidas.length, respuestas.length - 1)]
    pedidas.push(`${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`)
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return pedidas
}

/** Cuerpo RFC 7807 de un 422 con los campos de `errores[]`. */
export const problema422 = (...errores: { campo: string; tipo: string }[]) => ({
  type: '/errores/validacion',
  title: 'Validación',
  status: 422,
  errores: errores.map((e) => ({ ...e, mensaje: 'texto de la API que la pantalla no muestra' })),
})

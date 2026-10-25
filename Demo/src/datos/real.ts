// Adaptador real: Axios contra /v1 en el mismo origen (el proxy de Vite lo lleva a la API).
// El token JWT vive solo en esta clausura, en memoria. Nunca en storage ni en la URL.
import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { errorDeRed, errorDesdeProblema, rutaPlantilla, type ApiMatu, type Llamada } from './api'
import type {
  CuentaCreadaRespuesta,
  GrupoRespuesta,
  PersonaCreada,
  PersonaListada,
  Problema,
  SesionRespuesta,
  SolicitudGrupo,
  SolicitudPersona,
  SolicitudRegistro,
  SolicitudSesion,
} from './contrato'

type ConInicio = InternalAxiosRequestConfig & { inicio?: number }

export const BASE = '/v1'

export function crearCliente(anotar: (l: Omit<Llamada, 'id'>) => void): AxiosInstance {
  const http = axios.create({ baseURL: BASE, timeout: 8000, headers: { Accept: 'application/json' } })
  http.interceptors.request.use((c: ConInicio) => {
    c.inicio = performance.now()
    return c
  })
  const registrar = (c: ConInicio | undefined, status: number | null) => {
    anotar({
      metodo: (c?.method ?? 'get').toUpperCase(),
      ruta: rutaPlantilla(`${BASE}${c?.url ?? ''}`),
      status,
      ms: Math.round(performance.now() - (c?.inicio ?? performance.now())),
    })
  }
  http.interceptors.response.use(
    (r) => {
      registrar(r.config, r.status)
      return r
    },
    (e: AxiosError<Problema>) => {
      registrar(e.config, e.response?.status ?? null)
      if (!e.response) return Promise.reject(errorDeRed())
      return Promise.reject(errorDesdeProblema(e.response.status, e.response.data ?? null))
    },
  )
  return http
}

/** GET /v1/salud: si responde {"estado": "ok"} hay backend. */
export async function hayBackend(anotar: (l: Omit<Llamada, 'id'>) => void): Promise<boolean> {
  try {
    const r = await crearCliente(anotar).get<{ estado?: string }>('/salud', { timeout: 2000 })
    return r.data?.estado === 'ok'
  } catch {
    return false
  }
}

export function adaptadorReal(anotar: (l: Omit<Llamada, 'id'>) => void): ApiMatu {
  const http = crearCliente(anotar)
  let token: string | null = null
  let grupoId: string | null = null

  const auth = () => (token ? { Authorization: `Bearer ${token}` } : {})
  const conGrupo = () => ({ ...auth(), ...(grupoId ? { 'X-Grupo-Id': grupoId } : {}) })

  return {
    modo: 'real',
    async crearCuenta(nombre, email, contrasena) {
      const cuerpo: SolicitudRegistro = { nombre, email, contrasena }
      return (await http.post<CuentaCreadaRespuesta>('/usuarios', cuerpo)).data
    },
    async iniciarSesion(email, contrasena) {
      const cuerpo: SolicitudSesion = { email, contrasena }
      token = (await http.post<SesionRespuesta>('/sesiones', cuerpo)).data.access_token
    },
    async listarGrupos() {
      return (await http.get<GrupoRespuesta[]>('/grupos', { headers: auth() })).data
    },
    async crearGrupo(nombre) {
      const cuerpo: SolicitudGrupo = { nombre }
      return (await http.post<GrupoRespuesta>('/grupos', cuerpo, { headers: auth() })).data
    },
    elegirGrupo(id) {
      grupoId = id
    },
    async darDeAlta(datos: SolicitudPersona) {
      return (await http.post<PersonaCreada>(`/grupos/${grupoId}/personas-cuidadas`, datos, { headers: conGrupo() })).data
    },
    async listarPersonas() {
      return (await http.get<PersonaListada[]>(`/grupos/${grupoId}/personas-cuidadas`, { headers: conGrupo() })).data
    },
    cerrar() {
      token = null
      grupoId = null
    },
  }
}

// La interfaz de datos de la demo. Dos adaptadores la implementan: `real` (Axios contra /v1)
// y `simulado` (en memoria). Las pantallas no saben cuál están usando.
import type {
  CuentaCreadaRespuesta,
  GrupoRespuesta,
  PersonaCreada,
  PersonaListada,
  Problema,
  SolicitudPersona,
} from './contrato'

export type Modo = 'real' | 'simulado'

/** Lo que el presentador puede ver de cada llamada: nunca el cuerpo ni el token. */
export interface Llamada {
  id: number
  metodo: string
  ruta: string
  status: number | null
  ms: number
}

export interface ApiMatu {
  readonly modo: Modo
  crearCuenta(nombre: string, email: string, contrasena: string): Promise<CuentaCreadaRespuesta>
  iniciarSesion(email: string, contrasena: string): Promise<void>
  listarGrupos(): Promise<GrupoRespuesta[]>
  crearGrupo(nombre: string): Promise<GrupoRespuesta>
  /** Fija el grupo en contexto (cabecera X-Grupo-Id). */
  elegirGrupo(grupoId: string): void
  darDeAlta(datos: SolicitudPersona): Promise<PersonaCreada>
  listarPersonas(): Promise<PersonaListada[]>
  /** Olvida la sesión: el token solo vivía en memoria. */
  cerrar(): void
}

export type TipoError = 'red' | 'http'

/** Error con un texto para la persona: qué pasó y cómo seguir. */
export class ErrorApi extends Error {
  readonly tipo: TipoError
  readonly status: number | null
  readonly campos: Record<string, string>
  readonly codigo: string | null

  constructor(tipo: TipoError, mensaje: string, status: number | null = null, campos: Record<string, string> = {}, codigo: string | null = null) {
    super(mensaje)
    this.tipo = tipo
    this.status = status
    this.campos = campos
    this.codigo = codigo
  }

  /**
   * Falla de red, del servidor o sin sesión: aquí se ofrece seguir en modo simulado. La sesión
   * falta cuando el presentador salta a una escena real sin haber creado la cuenta antes.
   */
  get puedeSimular(): boolean {
    return this.tipo === 'red' || (this.status !== null && this.status >= 500) || this.codigo === 'sin-sesion'
  }
}

const CAMPOS_HUMANOS: Record<string, string> = {
  nombre: 'Revisa el nombre.',
  email: 'Ese email no tiene la forma de un email. Revisa que tenga @ y un dominio.',
  contrasena: 'La contraseña necesita al menos 10 caracteres.',
  nombre_pila: 'Revisa cómo le dicen.',
  nivel_apoyo: 'Elige cuánto apoyo necesita.',
  calidad_otorgante: 'Elige en qué calidad das el permiso.',
  referencia_documento: 'Escribe la referencia del documento que te nombra representante.',
  aviso: 'Vuelve a mostrar el aviso y acéptalo para seguir.',
  'direccion.calle': 'Revisa la calle.',
  'direccion.numero': 'Revisa el número.',
  'direccion.comuna': 'Revisa la comuna.',
}

/** Traduce un problema RFC 7807 a un texto humano, sin repetir datos de la persona. */
export function errorDesdeProblema(status: number, p: Partial<Problema> | null, ruta = ''): ErrorApi {
  const codigo = p?.type?.replace('/errores/', '') ?? null
  if (status === 401 && ruta !== '/sesiones') return errorSinSesion()
  if (status === 409 && codigo === 'email-registrado') {
    return new ErrorApi('http', 'Ese email ya tiene una cuenta. Entra con tu contraseña.', status, { email: 'Ese email ya tiene una cuenta.' }, codigo)
  }
  if (status === 401) {
    return new ErrorApi('http', 'El email o la contraseña no coinciden. Revísalos y vuelve a intentar.', status, {}, codigo)
  }
  if (status === 404) {
    return new ErrorApi('http', 'No encontramos ese grupo para tu cuenta. Entra de nuevo.', status, {}, codigo)
  }
  if (status === 422) {
    const campos: Record<string, string> = {}
    for (const e of p?.errores ?? []) campos[e.campo] = CAMPOS_HUMANOS[e.campo] ?? 'Revisa este dato.'
    const primero = Object.values(campos)[0]
    return new ErrorApi('http', primero ?? 'Revisa los datos marcados.', status, campos, codigo)
  }
  if (status >= 500) {
    return new ErrorApi('http', 'El servidor no pudo responder. Puedes seguir en modo simulado.', status, {}, codigo)
  }
  return new ErrorApi('http', 'No se pudo completar. Vuelve a intentar.', status, {}, codigo)
}

export const errorSinSesion = () =>
  new ErrorApi('http', 'No hay una sesión abierta. Crea tu cuenta o entra primero, o sigue con datos simulados.', 401, {}, 'sin-sesion')

export const errorDeRed = () =>
  new ErrorApi('red', 'No hay conexión con el servidor de MATU. Puedes seguir en modo simulado.')

/** Ruta legible para el panel: los identificadores se reemplazan por su nombre. */
export function rutaPlantilla(ruta: string): string {
  return ruta.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '{grupo_id}')
}

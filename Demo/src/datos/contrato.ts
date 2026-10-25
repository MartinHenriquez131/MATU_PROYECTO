// Tipos del contrato real de la API, copiados de los esquemas Pydantic de backend/app (solo
// lectura). No se inventan campos: si el backend cambia, se cambia aquí.
//   modules/iam/api/esquemas.py
//   modules/care_circle/api/esquemas.py
//   modules/care_circle/api/esquemas_personas.py

export type NivelApoyo = 'autovalente_con_supervision' | 'apoyo_parcial' | 'apoyo_total'
export type CalidadOtorgante = 'titular' | 'representante_legal' | 'cuidador_de_hecho'

/** POST /v1/usuarios */
export interface SolicitudRegistro {
  nombre: string
  email: string
  contrasena: string
}
export interface CuentaCreadaRespuesta {
  id: string
  nombre: string
  email: string
}

/** POST /v1/sesiones */
export interface SolicitudSesion {
  email: string
  contrasena: string
}
export interface SesionRespuesta {
  access_token: string
  token_type: 'bearer'
  expira_en: number
}

/** POST /v1/grupos y GET /v1/grupos */
export interface SolicitudGrupo {
  nombre: string
}
export interface GrupoRespuesta {
  id: string
  nombre: string
  rol: string
}

export interface DireccionNueva {
  etiqueta?: string
  calle: string
  numero: string
  depto?: string | null
  comuna: string
  region?: string
  referencia?: string | null
}
export interface DireccionVista {
  etiqueta: string
  calle: string
  numero: string
  depto: string | null
  comuna: string
  region: string
  referencia: string | null
}

/** POST /v1/grupos/{grupo_id}/personas-cuidadas, con la cabecera X-Grupo-Id */
export interface SolicitudPersona {
  nombre: string
  nombre_pila: string
  nivel_apoyo: NivelApoyo
  calidad_otorgante: CalidadOtorgante
  referencia_documento?: string | null
  aviso?: { id: string; version: string } | null
  direccion?: DireccionNueva | null
}

export interface ConsentimientoVista {
  id: string
  calidad_otorgante: CalidadOtorgante
  finalidad: string
  version_politica: string
  otorgado_en: string
  revision_vence_en: string | null
}

export interface AvisoVista {
  id: string
  version: string
  titulo: string
  parrafos: string[]
  sha256: string
}

export interface PersonaCreada {
  id: string
  nombre: string
  nombre_pila: string
  nivel_apoyo: NivelApoyo
  direccion: DireccionVista | null
  consentimiento: ConsentimientoVista
  aviso: AvisoVista | null
}

/** GET /v1/grupos/{grupo_id}/personas-cuidadas: la vista depende del rol. */
export interface PersonaVistaCompleta {
  id: string
  nombre: string
  nombre_pila: string
  nivel_apoyo: NivelApoyo
  direccion: DireccionVista | null
  consentimiento: ConsentimientoVista | null
}
export type PersonaListada = PersonaVistaCompleta | { id: string; nombre: string; direccion?: DireccionVista | null }

/** Problema RFC 7807 de app/core/errores.py */
export interface Problema {
  type: string
  title: string
  status: number
  detail?: string
  errores?: { campo: string; mensaje: string; tipo: string }[]
}

// Tipos del estado de la demo. Todo vive en memoria: nada se guarda en el navegador.

export type Rol = 'familia' | 'relevo' | 'comercio'

export type CampoId = 'su_dia' | 'si_se_altera' | 'a_quien_llamar'
export type Calidad = 'titular' | 'representante_legal' | 'cuidador_de_hecho'
export type Apoyo = 'autovalente_con_supervision' | 'apoyo_parcial' | 'apoyo_total'

export type PantallaFamiliaId =
  | 'bienvenida'
  | 'cuenta'
  | 'entrar'
  | 'a-quien'
  | 'permiso'
  | 'inicio'
  | 'completar'
  | 'guardado'
  | 'ficha'
  | 'compartir'
  | 'enlace-pin'
  | 'quien-vio'
  | 'enlaces'
  | 'imprimir'
  | 'conflicto'
  | 'se-acaba'
  | 'declarar'
  | 'agregar'
  | 'ya-compre'
  | 'reponer'
  | 'exportar'
  | 'pedido'
  | 'medio'
  | 'pasarela'
  | 'rechazado'
  | 'seguimiento'
  | 'entregado'

export type PantallaComercioId = 'c-pedidos' | 'c-preparar' | 'c-monto' | 'c-codigo'

export interface Pantalla<T extends string> {
  id: T
  /** Parámetro de la pantalla, por ejemplo el campo o el insumo. */
  p?: string
  /** Clave única de esta visita, para la transición. */
  n: number
}

export interface Cuenta {
  nombre: string
  email: string
  real: boolean
}

export interface DireccionPartes {
  calle: string
  numero: string
  comuna: string
}

export interface Persona {
  nombre: string
  nombrePila: string
  apoyo: Apoyo
  /** Dirección legible, o vacía si no se dio en el alta. */
  direccion: string
  partes: DireccionPartes | null
  /** Identificador que devolvió la API, si el alta fue real. */
  idReal: string | null
}

export interface Consentimiento {
  calidad: Calidad
  referenciaDocumento: string
  avisoId: string | null
  avisoVersion: string | null
  minuto: number
  revisionMinuto: number | null
}

export interface Campo {
  texto: string
  /** Hace las veces del ETag: cambia en cada escritura. */
  version: number
  autor: string
  minuto: number | null
}

export interface Borrador {
  campo: CampoId
  texto: string
  versionBase: number
}

export interface Conflicto {
  campo: CampoId
  suyo: Campo
  mio: string
}

export type EstadoAcceso = 'activo' | 'revocado' | 'bloqueado'

export interface Acceso {
  id: string
  token: string
  pin: string
  nombre: string
  telefono: string
  campos: CampoId[]
  motivo: string
  creadoMin: number
  venceMin: number
  estado: EstadoAcceso
  intentosFallidos: number
}

export interface Evento {
  id: number
  minuto: number
  texto: string
  tono: 'normal' | 'atento'
}

export interface Insumo {
  id: string
  nombre: string
  /** Cómo se nombra en una frase: "los pañales". */
  corto: string
  presentacion: string
  unidad: string
  preguntaDia: string
  porDia: number
  quedan: number
  tamanoPaquete: number
  /** Precio por paquete en pesos enteros. */
  precio: number
  declarado: boolean
}

export type Medio = 'credito' | 'debito'
export type EstadoPedido = 'borrador' | 'pagado' | 'preparando' | 'listo' | 'en_camino' | 'entregado'

export interface LineaPedido {
  insumoId: string
  nombre: string
  paquetes: number
  precio: number
  resolucion: 'ok' | 'sin_stock' | 'reemplazado' | 'no_disponible'
  reemplazo: { nombre: string; precio: number } | null
}

export interface Pedido {
  numero: number
  lineas: LineaPedido[]
  estimado: number
  aceptaEquivalente: boolean
  direccion: string
  medio: Medio | null
  /** Crédito: lo reservado. Débito: lo cobrado al confirmar. */
  montoPagado: number
  montoReal: number | null
  boleta: string
  estado: EstadoPedido
  codigoRetiro: string
  hitos: Partial<Record<EstadoPedido, number>>
  rechazos: number
  sumadoAlStock: boolean
}

export interface SesionRelevo {
  token: string | null
  fase: 'pin' | 'ficha' | 'no_disponible'
  pinErroneo: boolean
  urlLimpia: boolean
}

export interface Aviso {
  id: number
  texto: string
}

export interface Estado {
  rol: Rol
  nav: {
    familia: Pantalla<PantallaFamiliaId>[]
    comercio: Pantalla<PantallaComercioId>[]
  }
  dir: 'adelante' | 'atras'
  /** Minutos desde el viernes 30/10/2026 a las 14:20, hora de Chile. */
  ahora: number
  cuenta: Cuenta | null
  persona: Persona | null
  consentimiento: Consentimiento | null
  ficha: Record<CampoId, Campo>
  borrador: Borrador | null
  conflicto: Conflicto | null
  accesos: Acceso[]
  /** El PIN se muestra una sola vez: solo mientras este id esté aquí. */
  pinVisible: string | null
  eventos: Evento[]
  insumos: Insumo[]
  ajustesLista: Record<string, number>
  pedido: Pedido | null
  relevo: SesionRelevo
  texto200: boolean
  aviso: Aviso | null
  seq: number
}

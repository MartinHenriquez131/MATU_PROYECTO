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
  | 'pasarela'
  | 'rechazado'
  | 'seguimiento'
  | 'entregado'
  | 'grupo'

export type PantallaComercioId = 'c-pedidos' | 'c-preparar' | 'c-codigo'

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
/**
 * Estados del pedido con precio exacto (ADR-027): se confirma el stock, queda apartado con un
 * total que vale unos minutos, se paga una sola vez ese total y después se prepara y entrega.
 */
export type EstadoPedido = 'confirmando' | 'apartado' | 'pagado' | 'preparando' | 'listo' | 'en_camino' | 'entregado' | 'cancelado'

export interface LineaPedido {
  insumoId: string
  nombre: string
  paquetes: number
  /** Precio unitario confirmado, el que se paga. */
  precio: number
  /** Precio unitario que mostraba la lista. */
  precioLista: number
  comercio: string
  /** Qué cambió al confirmar el stock: nada, el precio o el comercio. */
  cambio: 'precio' | 'comercio' | null
  /** Lo que marca el comercio al preparar. */
  enComercio: 'pendiente' | 'listo' | 'ya_no_esta'
  /** El mismo producto, retirado en otro local: la familia paga lo mismo y MATU pone la diferencia. */
  reasignado: { comercio: string; precio: number } | null
  /** Nadie lo tenía: se devuelve su precio. */
  noLlego: boolean
}

/** Lo que estaba en la lista y ningún comercio tiene hoy: sale del pedido y no suma al total. */
export interface LineaFuera {
  insumoId: string
  nombre: string
  paquetes: number
  precio: number
}

export interface Pedido {
  numero: number
  lineas: LineaPedido[]
  salieron: LineaFuera[]
  envio: number
  /** Total de la lista antes de confirmar el stock, con envío. */
  totalLista: number
  /** Total confirmado con IVA y envío: lo que se paga una sola vez. */
  total: number
  direccion: string
  medio: Medio | null
  estado: EstadoPedido
  /** Hasta cuándo vale el total confirmado (minutos de la demo). */
  venceMin: number
  reconfirmado: boolean
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
  /** Escena elegida que no se deduce de la pantalla (la 35): vale mientras no se navegue. */
  escenaFija: { id: string; n: number } | null
  aviso: Aviso | null
  seq: number
}

// MATU-54, «Mis datos»: la copia de la persona cuidada y la de la propia cuenta (contrato propuesto
// docs/api/propuestos/mis-datos.openapi.yaml, decisiones 342 a 365 de docs/api/README.md).
//
// Un solo GET por copia (decisión 343): la respuesta se pide como texto, la pantalla la lee con
// `JSON.parse` y «Descargar» guarda ese mismo texto, sin volver a llamar a la API. El texto vive solo
// en la memoria de la pantalla que lo pidió: nunca va al almacenamiento del navegador, a la URL, a
// `history.state` ni al título. Los tipos se escriben a mano desde el YAML mientras no lleguen
// `openapi.json` y `familia.openapi.ts` regenerados; los nombres son los del contrato.
import { apiFamilia } from './sesion'

/** RFC 3339 con el desfase de Chile, por ejemplo `2026-11-12T10:05:00-03:00`. */
export type Instante = string
/** `AAAA-MM-DD`, sin hora. */
export type Dia = string
/** Pesos enteros, con IVA incluido. */
export type Pesos = number

/** Quien ya no está en el grupo llega con `nombre: null` y `activo: false`. */
export interface PersonaNombrada {
  nombre: string | null
  activo: boolean
}

export type CampoCopiaApi = 'rutina' | 'manejo_situaciones' | 'red_apoyo'
export type SeccionCopiaApi = 'quien_es' | 'preferencias' | 'alimentacion' | 'movilidad' | 'comunicacion' | 'remedios'
export type FinalidadCopia = 'plan_cuidado' | 'consumo' | 'despacho'
export type EstadoBloque = 'disponible' | 'retirada' | 'en_pausa' | 'borrada' | 'sin_autorizar'

// ---------------------------------------------------------------- la copia de la persona

export interface DireccionCopia {
  etiqueta: string
  calle: string
  numero: string
  depto: string | null
  comuna: string
  region: string
  referencia: string | null
}

export interface DatosPersonaCopia {
  nombre: string
  nombre_pila: string
  nivel_apoyo: 'autovalente_con_supervision' | 'apoyo_parcial' | 'apoyo_total'
  direccion: DireccionCopia | null
  alta_en: Instante
}

export interface TextoMostrado {
  identificador: string
  version: string
  huella: string | null
}

export interface AutorizacionCopia {
  finalidad: FinalidadCopia
  estado: 'vigente' | 'revision_vencida' | 'retirada' | 'reemplazada'
  calidad_otorgante: 'titular' | 'representante_legal' | 'cuidador_de_hecho'
  version_politica: string
  declaracion: TextoMostrado | null
  aviso: TextoMostrado | null
  registrada_por: PersonaNombrada
  otorgada_en: Instante
  revision_vence_en: Instante | null
  retirada_en: Instante | null
  hay_documento_representante: boolean
}

export interface CampoCopia {
  campo: CampoCopiaApi
  texto: string | null
  escrito_por: PersonaNombrada | null
  actualizado_en: Instante | null
}

export interface SeccionCopia {
  seccion: SeccionCopiaApi
  texto: string
  escrito_por: PersonaNombrada | null
  creada_en: Instante
  actualizado_en: Instante
}

export interface FichaCopia {
  estado: EstadoBloque
  borrado_el: Dia | null
  completitud: 0 | 33 | 67 | 100 | null
  campos: CampoCopia[] | null
  secciones: SeccionCopia[] | null
}

export interface AperturaCopia {
  tipo: 'presentacion' | 'apertura' | 'pin_incorrecto' | 'bloqueo'
  ocurrido_en: Instante
  secciones: SeccionCopiaApi[] | null
}

export interface EnlaceRelevoCopia {
  nombre_relevo: string
  motivo: 'salgo_unas_horas' | 'fin_de_semana_fuera' | 'turno_de_noche' | 'otro'
  campos: CampoCopiaApi[]
  secciones: SeccionCopiaApi[]
  estado: 'vigente' | 'vencido' | 'revocado' | 'bloqueado'
  creado_en: Instante
  vence_en: Instante
  cortado_en: Instante | null
  compartido_por: string
  usos: number
  ultimo_uso_en: Instante | null
  aperturas: AperturaCopia[]
}

export type UnidadCopia = 'unidad' | 'sobre' | 'ml' | 'g'

export interface InsumoCopia {
  nombre: string
  del_catalogo: boolean
  unidad: UnidadCopia
  usa_unidades: number
  cada_dias: number
  quedaban_unidades: number
  quedaban_el: Dia
  se_acaba_el: Dia
  dias_aviso: number
  unidades_por_envase: number | null
  se_sigue: boolean
  agregado_en: Instante
  actualizado_en: Instante
  actualizado_por: PersonaNombrada | null
}

export interface CompraCopia {
  insumo: string
  unidades: number
  el: Dia
  origen: 'declarada' | 'pedido_matu'
  anotada_en: Instante
  anotada_por: PersonaNombrada | null
}

export interface AvisoInsumoCopia {
  insumo: string
  fecha_prevista: Dia
  estado: 'pendiente' | 'notificada' | 'resuelta' | 'descartada'
  creado_en: Instante
  notificado_en: Instante | null
  cerrado_en: Instante | null
}

export interface InsumosCopia {
  estado: EstadoBloque
  borrado_el: Dia | null
  lista: InsumoCopia[] | null
  compras: CompraCopia[] | null
  avisos: AvisoInsumoCopia[] | null
}

export type EstadoPedidoCopia =
  | 'borrador'
  | 'total_confirmado'
  | 'vencido'
  | 'pagado'
  | 'enviado_a_comercio'
  | 'preparando'
  | 'listo_retiro'
  | 'asignado'
  | 'sin_repartidor'
  | 'retirado'
  | 'en_ruta'
  | 'entregado'
  | 'no_entregado'
  | 'reprogramado'
  | 'cerrado'
  | 'cancelado'
  | 'cancelado_con_devolucion'

export interface LineaPedidoCopia {
  producto: string
  presentacion: string
  comercio: string
  cantidad: number
  precio_unitario: Pesos
  subtotal: Pesos
  si_falta: 'otro_comercio' | 'quitar'
}

export interface EntregaCopia {
  calle: string
  numero: string
  depto: string | null
  comuna: string
  region: string
  referencia: string | null
}

export interface DevolucionCopia {
  motivo: 'pago_tardio' | 'producto_no_entregado' | 'cancelacion'
  producto: string | null
  monto: Pesos
  estado: 'en_curso' | 'hecha'
  solicitada_en: Instante
  hecha_en: Instante | null
}

export interface PagoPedidoCopia {
  estado: 'sin_intento' | 'pendiente' | 'aprobado' | 'no_aprobado' | 'devuelto_parcial' | 'anulado'
  pagado_en: Instante | null
  pagado_por: PersonaNombrada | null
  cobrado: Pesos
  devuelto: Pesos
  devoluciones: DevolucionCopia[]
  pago_de_prueba: boolean
}

export interface PedidoCopia {
  referencia: string | null
  estado: EstadoPedidoCopia
  creado_en: Instante
  total_confirmado_en: Instante | null
  lineas: LineaPedidoCopia[]
  subtotal_productos: Pesos
  costo_envio: Pesos
  total: Pesos | null
  entrega: EntregaCopia | null
  pago: PagoPedidoCopia | null
  precios_de_ejemplo: boolean
}

export type TipoHecho =
  | 'abrio_la_ficha'
  | 'edito_la_ficha'
  | 'quito_una_seccion'
  | 'ficha_borrada'
  | 'dio_una_autorizacion'
  | 'retiro_una_autorizacion'
  | 'compartio_la_ficha'
  | 'corto_un_enlace'
  | 'agrego_un_insumo'
  | 'edito_un_insumo'
  | 'dejo_de_seguir_un_insumo'
  | 'volvio_a_seguir_un_insumo'
  | 'quito_un_insumo'
  | 'anoto_una_compra'
  | 'aviso_de_insumo'
  | 'descarto_un_aviso'
  | 'resolvio_un_aviso'
  | 'cambio_la_direccion'
  | 'creo_un_pedido'
  | 'confirmo_un_pedido'
  | 'cancelo_un_pedido'
  | 'cambio_que_hacer_si_falta'
  | 'inicio_un_pago'
  | 'pago_aprobado'
  | 'pago_anulado'
  | 'pidio_una_copia'

/** Una persona del grupo o MATU (`nombre: null`, `activo: null`). */
export interface QuienCopia {
  tipo: 'persona' | 'matu'
  nombre: string | null
  activo: boolean | null
}

export interface HechoCopia {
  /** Un `tipo` que el cliente no conoce llega como `string` y no se muestra. */
  tipo: TipoHecho | (string & {})
  ocurrido_en: Instante
  quien: QuienCopia
  campo: CampoCopiaApi | null
  seccion: SeccionCopiaApi | null
}

export interface HistorialCopia {
  alcance: 'todo' | 'lo_tuyo'
  hechos: HechoCopia[]
  hay_hechos_sin_asociar: boolean
}

export interface CopiaDatosPersona {
  formato: 'matu-datos/1'
  tipo: 'persona_cuidada'
  generado_en: Instante
  aviso: string
  persona: DatosPersonaCopia
  autorizaciones: AutorizacionCopia[]
  ficha: FichaCopia
  enlaces_relevo: EnlaceRelevoCopia[]
  insumos: InsumosCopia
  /** `null` solo con la capa 3 quitada de la instalación: el bloque no existe. */
  pedidos: PedidoCopia[] | null
  historial: HistorialCopia
}

// ---------------------------------------------------------------- la copia de la cuenta

export type ClaseDispositivoCopia = 'telefono' | 'computador' | 'otro'

export interface CuentaCopia {
  nombre: string
  correo: string
  /** E.164 completo: la pantalla lo muestra enmascarado (P3) y el archivo lo trae entero. */
  celular: string | null
  celular_confirmado: boolean
  canal_codigos: 'sms' | 'whatsapp'
  creada_en: Instante
}

export interface PoliticaCopia {
  version: string
  huella: string
  aceptada_en: Instante
}

export interface GrupoCopia {
  nombre: string
  rol: 'admin' | 'cuidador' | 'pagador' | 'observador'
  unido_en: Instante
  puede_ver_ficha: boolean | null
}

export interface DispositivoCopia {
  nombre: string
  clase: ClaseDispositivoCopia
  creado_en: Instante
  ultimo_uso_en: Instante | null
  cerrado_en: Instante | null
  avisos_activos: boolean
}

export interface EventoCuentaCopia {
  tipo:
    | 'entraste'
    | 'saliste'
    | 'cerraste_en_dispositivo'
    | 'salida_por_seguridad'
    | 'contrasena_cambiada'
    | 'celular_confirmado'
    | 'codigo_recuperacion_pedido'
    | 'avisos_cambiados'
    | 'avisos_activados'
    | 'avisos_desactivados'
    | 'pediste_una_copia'
  ocurrido_en: Instante
  dispositivo: { nombre: string; clase: ClaseDispositivoCopia } | null
}

export interface AvisoEnviadoCopia {
  creado_en: Instante
  enviado_en: Instante | null
  canal: 'correo' | 'push' | 'sms'
  resultado: 'salio' | 'no_salio' | 'pendiente' | 'en_el_piloto_no_salio'
}

export interface PagoCuentaCopia {
  grupo: string
  referencia: string
  pagado_en: Instante
  cobrado: Pesos
  devuelto: Pesos
  tarjeta: { tipo: 'credito' | 'debito' | 'prepago'; ultimos4: string; cuotas: number } | null
  pago_de_prueba: boolean
}

export interface CondicionesCopia {
  grupo: string
  referencia: string | null
  version: string
  huella: string
  aceptadas_en: Instante
}

export interface CopiaDatosCuenta {
  formato: 'matu-datos/1'
  tipo: 'cuenta'
  generado_en: Instante
  aviso: string
  cuenta: CuentaCopia
  politica: PoliticaCopia | null
  grupos: GrupoCopia[]
  dispositivos: DispositivoCopia[]
  preferencia_avisos: { correo: boolean; push: boolean }
  eventos: EventoCuentaCopia[]
  avisos_enviados: AvisoEnviadoCopia[]
  envio_simulado: boolean
  /** `null` con la capa 3 quitada: los dos bloques no existen. */
  pagos: PagoCuentaCopia[] | null
  condiciones_aceptadas: CondicionesCopia[] | null
}

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

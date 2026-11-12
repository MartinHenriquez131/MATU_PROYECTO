// MATU-54: las dos copias sintéticas («Datos de María» y «Tus datos») con la forma del contrato
// propuesto, y una API falsa que las entrega como texto, con `Content-Disposition`, como la API real.
// Solo datos sintéticos: nombres de ejemplo, teléfonos de la serie 5555 y correos en example.org.
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { vi } from 'vitest'
import type { CopiaDatosCuenta, CopiaDatosPersona } from '../src/compartido/api/misDatos'
import { apiFamilia } from '../src/compartido/api/sesion'

/** 12/11/2026 a las 10:14 de Chile (UTC−3 en verano). */
export const AHORA = new Date('2026-11-12T13:14:00Z')
export function fijarAhora() {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(AHORA)
}

export const MARIA = { id: '3c9d4e20-0000-4000-8000-0000000054a1', nombre: 'María Soto Pérez', nombre_pila: 'María' }
export const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000054g1'

const yo = { nombre: 'Carmen Soto', activo: true }
const salio = { nombre: null, activo: false }

/** Un instante de Chile `dias` días y `min` minutos antes de AHORA, con el desfase de la copia. */
export function antes(dias: number, min = 0): string {
  const t = new Date(AHORA.getTime() - (dias * 24 * 60 + min) * 60_000 - 3 * 3_600_000)
  return `${t.toISOString().slice(0, 19)}-03:00`
}

/** Un hecho del historial, como lo manda la API. `tipo` admite uno desconocido, para probar que no rompe nada. */
export type Hecho = CopiaDatosPersona['historial']['hechos'][number]
export const hecho = (tipo: string, ocurrido_en: string, quien: Hecho['quien'] = { tipo: 'persona', ...yo }, campo: Hecho['campo'] = null, seccion: Hecho['seccion'] = null): Hecho => ({
  tipo: tipo as Hecho['tipo'],
  ocurrido_en,
  quien,
  campo,
  seccion,
  finalidad: null,
  referencia: null,
})

/** El texto fijo con que empieza toda copia (decisión 377). */
export const AVISO = 'Esta es una copia de los datos que MATU guarda, para que puedas conocerlos o llevarlos a otro lugar. No es la ficha para un relevo, y no se usa para compartirla. MATU no guarda esta copia. Este archivo queda donde lo descargaste, fuera de MATU: no vence y MATU no lo puede borrar.'
const MATU = { tipo: 'matu' as const, nombre: null, activo: null }

/** «A quién llamar» con los teléfonos tal como se escribieron (D-54-4). */
export const A_QUIEN = 'Carmen, su hija: +56 9 5555 0141\nRodrigo, su hijo: +56 9 5555 0102'

export function copiaPersona(cambios: Partial<CopiaDatosPersona> = {}): CopiaDatosPersona {
  return {
    formato: 'matu-datos/1',
    tipo: 'persona_cuidada',
    generado_en: '2026-11-12T10:14:00-03:00',
    aviso: AVISO,
    persona: {
      nombre: 'María Soto Pérez',
      nombre_pila: 'María',
      nivel_apoyo: 'apoyo_parcial',
      direccion: { etiqueta: 'Casa', calle: 'Los Aromos', numero: '123', depto: 'depto 4', comuna: 'Ñuñoa', region: 'Región Metropolitana', referencia: 'Reja verde' },
      alta_en: '2026-11-02T18:20:00-03:00',
    },
    autorizaciones: [
      {
        finalidad: 'plan_cuidado',
        estado: 'vigente',
        calidad_otorgante: 'cuidador_de_hecho',
        version_politica: '0.16',
        declaracion: { identificador: 'declaracion_cuidador_de_hecho', version: '1.0', huella: 'a'.repeat(64) },
        aviso: { identificador: 'aviso_cuidador_de_hecho', version: '1.0', huella: null },
        registrada_por: yo,
        otorgada_en: '2026-11-02T18:20:00-03:00',
        revision_vence_en: '2027-11-02T18:20:00-03:00',
        retirada_en: null,
        hay_documento_representante: true,
      },
      {
        finalidad: 'consumo',
        estado: 'retirada',
        calidad_otorgante: 'titular',
        version_politica: '0.16',
        declaracion: null,
        aviso: null,
        registrada_por: salio,
        otorgada_en: '2026-11-03T09:00:00-03:00',
        revision_vence_en: null,
        retirada_en: '2026-11-10T08:30:00-03:00',
        hay_documento_representante: false,
      },
      {
        finalidad: 'plan_cuidado',
        estado: 'reemplazada',
        calidad_otorgante: 'representante_legal',
        version_politica: '0.9',
        declaracion: { identificador: 'declaracion_representante', version: '0.9', huella: null },
        aviso: null,
        registrada_por: yo,
        otorgada_en: '2025-10-01T10:00:00-03:00',
        revision_vence_en: null,
        retirada_en: '2026-11-02T18:20:00-03:00',
        hay_documento_representante: false,
      },
    ],
    ficha: {
      estado: 'disponible',
      borrado_el: null,
      completitud: 67,
      campos: [
        { campo: 'rutina', texto: '08:00 Despierta.\n13:00 Almuerza.', escrito_por: yo, actualizado_en: '2026-11-05T21:02:00-03:00' },
        { campo: 'manejo_situaciones', texto: null, escrito_por: null, actualizado_en: null },
        { campo: 'red_apoyo', texto: A_QUIEN, escrito_por: salio, actualizado_en: '2026-11-06T10:00:00-03:00' },
      ],
      secciones: [{ seccion: 'comunicacion', texto: 'Hablarle despacio.', escrito_por: yo, creada_en: '2026-11-04T10:00:00-03:00', actualizado_en: '2026-11-04T11:00:00-03:00' }],
    },
    enlaces_relevo: [
      {
        nombre_relevo: 'Rosa',
        motivo: 'fin_de_semana_fuera',
        campos: ['rutina', 'red_apoyo'],
        secciones: ['comunicacion'],
        estado: 'vigente',
        creado_en: '2026-11-11T09:00:00-03:00',
        vence_en: '2026-11-15T23:59:00-03:00',
        cortado_en: null,
        compartido_por: 'Carmen',
        usos: 3,
        ultimo_uso_en: '2026-11-12T08:00:00-03:00',
        aperturas: Array.from({ length: 7 }, (_, i) => ({ tipo: i % 2 ? ('presentacion' as const) : ('apertura' as const), ocurrido_en: antes(0, 120 + i * 30), secciones: null })),
      },
      {
        nombre_relevo: 'Pedro',
        motivo: 'otro',
        campos: ['rutina'],
        secciones: [],
        estado: 'revocado',
        creado_en: '2026-11-01T09:00:00-03:00',
        vence_en: '2026-11-03T09:00:00-03:00',
        cortado_en: '2026-11-02T09:00:00-03:00',
        compartido_por: 'Rodrigo',
        usos: 0,
        ultimo_uso_en: null,
        aperturas: [],
      },
    ],
    insumos: {
      estado: 'disponible',
      borrado_el: null,
      lista: [
        {
          nombre: 'Champú en sobre',
          del_catalogo: false,
          unidad: 'sobre',
          usa_unidades: 1,
          cada_dias: 2,
          quedaban_unidades: 30,
          quedaban_el: '2026-11-10',
          se_acaba_el: '2027-01-09',
          dias_aviso: 0,
          unidades_por_envase: 10,
          se_sigue: true,
          agregado_en: '2026-10-20T12:00:00-03:00',
          actualizado_en: '2026-11-10T08:00:00-03:00',
          actualizado_por: yo,
        },
        {
          nombre: 'Toallitas húmedas',
          del_catalogo: true,
          unidad: 'unidad',
          usa_unidades: 3,
          cada_dias: 1,
          quedaban_unidades: 10,
          quedaban_el: '2026-11-01',
          se_acaba_el: '2026-11-04',
          dias_aviso: 7,
          unidades_por_envase: null,
          se_sigue: false,
          agregado_en: '2026-10-21T12:00:00-03:00',
          actualizado_en: '2026-11-01T08:00:00-03:00',
          actualizado_por: null,
        },
      ],
      compras: [
        { insumo: 'Champú en sobre', unidad: 'sobre', unidades: 20, el: '2026-11-10', origen: 'declarada', anotada_en: '2026-11-10T08:00:00-03:00', anotada_por: yo },
        { insumo: 'Toallitas húmedas', unidad: 'unidad', unidades: 80, el: '2026-11-08', origen: 'pedido_matu', anotada_en: '2026-11-08T08:00:00-03:00', anotada_por: null },
      ],
      avisos: [
        { insumo: 'Toallitas húmedas', fecha_prevista: '2026-11-04', estado: 'resuelta', creado_en: '2026-10-28T08:00:00-03:00', notificado_en: '2026-10-28T08:00:00-03:00', cerrado_en: '2026-11-01T08:00:00-03:00' },
        { insumo: 'Champú en sobre', fecha_prevista: '2027-01-09', estado: 'pendiente', creado_en: '2026-11-10T08:00:00-03:00', notificado_en: null, cerrado_en: null },
      ],
    },
    pedidos: [
      {
        referencia: '4821',
        estado: 'entregado',
        creado_en: '2026-11-08T11:02:00-03:00',
        total_confirmado_en: '2026-11-08T11:10:00-03:00',
        lineas: [
          { producto: 'Pañal adulto M', presentacion: 'paquete de 30', comercio: 'Farmacia Los Aromos (comercio ficticio)', cantidad: 2, precio_unitario: 13_990, subtotal: 27_980, si_falta: 'otro_comercio' },
          { producto: 'Toallitas', presentacion: 'paquete de 80', comercio: 'Farmacia Los Aromos (comercio ficticio)', cantidad: 1, precio_unitario: 5_290, subtotal: 5_290, si_falta: 'quitar' },
        ],
        subtotal_productos: 33_270,
        costo_envio: 3_990,
        total: 37_260,
        entrega: { calle: 'Los Aromos', numero: '123', depto: null, comuna: 'Ñuñoa', region: 'Región Metropolitana', referencia: null },
        pago: {
          estado: 'devuelto_parcial',
          pagado_en: '2026-11-08T11:24:00-03:00',
          pagado_por: { nombre: 'Rodrigo Soto', activo: true },
          cobrado: 37_260,
          devuelto: 5_290,
          devoluciones: [{ motivo: 'producto_no_entregado', producto: 'Toallitas', monto: 5_290, estado: 'hecha', solicitada_en: '2026-11-09T10:00:00-03:00', hecha_en: '2026-11-09T10:30:00-03:00' }],
          pago_de_prueba: true,
        },
        precios_de_ejemplo: true,
      },
      {
        referencia: null,
        estado: 'borrador',
        creado_en: '2026-11-11T10:00:00-03:00',
        total_confirmado_en: null,
        lineas: [],
        subtotal_productos: 0,
        costo_envio: 3_990,
        total: null,
        entrega: null,
        pago: null,
        precios_de_ejemplo: true,
      },
    ],
    historial: {
      alcance: 'todo',
      hechos: [
        hecho('pidio_una_copia', antes(0, 0)),
        hecho('edito_la_ficha', antes(0, 34), undefined, 'rutina'),
        hecho('edito_la_ficha', antes(0, 50), { tipo: 'persona', ...salio }),
        hecho('un_tipo_que_no_existe', antes(0, 60)),
        hecho('ficha_borrada', antes(1, 0), MATU),
        hecho('quito_una_seccion', antes(1, 30), undefined, null, 'movilidad'),
        hecho('pago_anulado', antes(3, 0), MATU),
      ],
      hay_hechos_sin_asociar: false,
    },
    ...cambios,
  }
}

export function copiaCuenta(cambios: Partial<CopiaDatosCuenta> = {}): CopiaDatosCuenta {
  return {
    formato: 'matu-datos/1',
    tipo: 'cuenta',
    generado_en: '2026-11-12T10:14:00-03:00',
    aviso: AVISO,
    cuenta: { nombre: 'Rodrigo Soto', correo: 'rodrigo.soto@example.org', celular: '+56955550137', celular_confirmado: true, canal_codigos: 'whatsapp', creada_en: '2026-10-20T18:20:00-03:00' },
    politica: { version: '0.16', huella: 'f'.repeat(64), aceptada_en: '2026-10-20T18:15:00-03:00' },
    grupos: [
      { nombre: 'Familia Soto', rol: 'pagador', unido_en: '2026-10-21T10:00:00-03:00', puede_ver_ficha: false },
      { nombre: 'Familia Pérez', rol: 'admin', unido_en: '2026-10-22T10:00:00-03:00', puede_ver_ficha: null },
    ],
    dispositivos: [
      { nombre: 'Chrome en Android', clase: 'telefono', creado_en: '2026-10-20T18:20:00-03:00', ultimo_uso_en: '2026-11-12T10:00:00-03:00', cerrado_en: null, avisos_activos: true },
      { nombre: 'Firefox en Linux', clase: 'computador', creado_en: '2026-11-01T18:20:00-03:00', ultimo_uso_en: '2026-11-02T18:20:00-03:00', cerrado_en: '2026-11-03T09:00:00-03:00', avisos_activos: false },
    ],
    preferencia_avisos: { correo: true, push: false },
    eventos: [
      { tipo: 'pediste_una_copia', ocurrido_en: '2026-11-12T10:14:00-03:00', dispositivo: null },
      { tipo: 'entraste', ocurrido_en: '2026-11-12T10:00:00-03:00', dispositivo: { nombre: 'Chrome en Android', clase: 'telefono' } },
      { tipo: 'entraste', ocurrido_en: '2026-07-01T10:00:00-04:00', dispositivo: null },
    ],
    avisos_enviados: [
      { creado_en: '2026-11-10T08:00:00-03:00', enviado_en: '2026-11-10T08:00:05-03:00', canal: 'correo', resultado: 'en_el_piloto_no_salio' },
      { creado_en: '2026-11-09T08:00:00-03:00', enviado_en: null, canal: 'push', resultado: 'no_salio' },
      { creado_en: '2026-11-12T09:00:00-03:00', enviado_en: null, canal: 'sms', resultado: 'pendiente' },
    ],
    envio_simulado: true,
    pagos: [
      { grupo: 'Familia Soto', referencia: '4821', pagado_en: '2026-11-08T11:24:00-03:00', cobrado: 37_260, devuelto: 5_290, tarjeta: { tipo: 'credito', ultimos4: '4242', cuotas: 3 }, pago_de_prueba: true },
      { grupo: 'Familia Soto', referencia: '4910', pagado_en: '2026-11-09T11:24:00-03:00', cobrado: 10_480, devuelto: 0, tarjeta: { tipo: 'debito', ultimos4: '0019', cuotas: 0 }, pago_de_prueba: false },
    ],
    condiciones_aceptadas: [
      { grupo: 'Familia Soto', referencia: '4821', version: '1.0', huella: 'c'.repeat(64), aceptadas_en: '2026-11-08T11:20:00-03:00' },
      { grupo: 'Familia Soto', referencia: null, version: '1.0', huella: 'd'.repeat(64), aceptadas_en: '2026-11-11T11:20:00-03:00' },
    ],
    ...cambios,
  }
}

export interface Respuesta {
  status: number
  /** El cuerpo, como texto: así lo entrega la API y así se guarda en el archivo. */
  texto?: string
  cabeceras?: Record<string, string>
}

export const copiaComoRespuesta = (copia: object, nombre: string): Respuesta => ({
  status: 200,
  texto: JSON.stringify(copia, null, 2),
  cabeceras: { 'content-disposition': `inline; filename="${nombre}"`, 'cache-control': 'no-store' },
})
export const problemaCopia = (status: number, tipo: string, cabeceras: Record<string, string> = {}): Respuesta => ({
  status,
  texto: JSON.stringify({ type: `/errores/${tipo}`, title: 'Texto de la API que no se muestra', status }),
  cabeceras,
})

/**
 * La API de la copia: responde en orden (la última se repite). Devuelve las peticiones con su método,
 * su ruta, su `responseType` y su `X-Grupo-Id`. Lo que no es de la copia responde 404.
 */
export function apiCopia(...respuestas: (Respuesta | Promise<Respuesta>)[]) {
  const pedidas: { linea: string; responseType: string | undefined }[] = []
  let n = 0
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const linea = `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`
    pedidas.push({ linea, responseType: config.responseType })
    const r = /\/datos$/.test(config.url ?? '') ? await respuestas[Math.min(n++, respuestas.length - 1)] : problemaCopia(404, 'no-encontrado')
    // Como el navegador con `responseType: 'text'`: el cuerpo llega como texto y pasa por `transformResponse`.
    const transformar = (config.transformResponse ?? []) as ((d: unknown) => unknown)[]
    const data = transformar.reduce<unknown>((d, f) => f.call(config, d), r.texto ?? '')
    const respuesta: AxiosResponse = { data, status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return pedidas
}

/** Una respuesta que llega cuando la prueba quiere. */
export function diferida() {
  let soltar!: (r: Respuesta) => void
  const promesa = new Promise<Respuesta>((ok) => (soltar = ok))
  return { promesa, soltar }
}

/** jsdom no trae `showModal` ni `close`. */
export function dialogoDeJsdom() {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.hasAttribute('open')) return
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
}

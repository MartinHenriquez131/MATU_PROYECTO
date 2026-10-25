// Reglas y formatos de la demo. Dinero siempre en pesos enteros, nunca decimales.
import type { Acceso, Insumo, Pedido } from './tipos'

/** Holgura que se reserva con crédito sobre el estimado (arquitectura, sección 8.2). */
export const MARGEN_PORCENTAJE = 15
/** Cinco PIN incorrectos bloquean el acceso (MATU-19). */
export const MAX_INTENTOS_PIN = 5
/** Se avisa cuando quedan 7 días o menos. */
export const DIAS_PRONTO = 7
export const DIAS_ATENTA = 14
/** La lista de reposición busca cubrir tres semanas. */
export const COBERTURA_DIAS = 21
/** Un equivalente puede costar hasta 10% más. */
export const TOPE_EQUIVALENTE_PORCENTAJE = 10
export const DIA = 1440

// Fecha fija de la demo: viernes 30/10/2026, 14:20 (hora de Chile). Se usa UTC solo como
// calendario, para que la zona horaria del proyector no mueva las fechas.
const BASE = Date.UTC(2026, 9, 30, 14, 20)

const fecha = (min: number) => new Date(BASE + min * 60_000)
const dos = (n: number) => String(n).padStart(2, '0')

export function fmtFecha(min: number): string {
  const d = fecha(min)
  return `${dos(d.getUTCDate())}/${dos(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`
}

export function fmtHora(min: number): string {
  const d = fecha(min)
  return `${dos(d.getUTCHours())}:${dos(d.getUTCMinutes())}`
}

/** Minuto de inicio del día que contiene a `min`. */
export function inicioDelDia(min: number): number {
  const d = fecha(min)
  return min - d.getUTCHours() * 60 - d.getUTCMinutes()
}

/** "Hoy, 14:20", "Ayer, 10:05", "Mañana, 14:22" o "25/10/2026, 23:59". */
export function fmtCuando(min: number, ahora: number): string {
  const dias = Math.round((inicioDelDia(min) - inicioDelDia(ahora)) / DIA)
  const hora = fmtHora(min)
  if (dias === 0) return `Hoy, ${hora}`
  if (dias === -1) return `Ayer, ${hora}`
  if (dias === 1) return `Mañana, ${hora}`
  return `${fmtFecha(min)}, ${hora}`
}

export function fmtRestante(min: number, ahora: number): string {
  const resta = min - ahora
  if (resta <= 0) return 'vencido'
  if (resta < 60) return `${resta} min`
  const horas = Math.floor(resta / 60)
  if (horas < 48) return `${horas} h`
  return `${Math.floor(horas / 24)} días`
}

const NOMBRES_DIA = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado']
export function diaDeLaSemana(min: number): string {
  return NOMBRES_DIA[fecha(min).getUTCDay()]
}

/** Hasta el domingo siguiente a las 23:59. */
export function finDeSemana(ahora: number): number {
  const dow = fecha(ahora).getUTCDay()
  const hastaDomingo = dow === 0 ? 7 : 7 - dow
  return inicioDelDia(ahora) + hastaDomingo * DIA + 23 * 60 + 59
}

export function fmtDinero(monto: number): string {
  if (!Number.isInteger(monto)) throw new Error('El dinero se maneja en pesos enteros')
  const signo = monto < 0 ? '-' : ''
  return `${signo}$${String(Math.abs(monto)).replace(/\B(?=(\d{3})+(?!\d))/g, '.')}`
}

/** Lee lo que escribió el comercio ("51.340", "$51340") como pesos enteros. */
export function leerPesos(texto: string): number | null {
  const limpio = texto.replace(/[$.\s]/g, '')
  if (!/^\d{1,7}$/.test(limpio)) return null
  return Number.parseInt(limpio, 10)
}

// ---------- Predicción ----------

/** Días que alcanzan: stock / consumo diario, hacia abajo. */
export function diasRestantes(i: Insumo): number {
  if (i.porDia <= 0) return Number.POSITIVE_INFINITY
  return Math.floor(i.quedan / i.porDia)
}

export type Nivel = 'pronto' | 'atenta' | 'tranquila'
export function nivel(dias: number): Nivel {
  if (dias <= DIAS_PRONTO) return 'pronto'
  if (dias <= DIAS_ATENTA) return 'atenta'
  return 'tranquila'
}

export const ETIQUETA_NIVEL: Record<Nivel, string> = {
  pronto: 'Pronto',
  atenta: 'Atenta',
  tranquila: 'Tranquila',
}

export function paquetesSugeridos(i: Insumo): number {
  if (!i.declarado || diasRestantes(i) >= COBERTURA_DIAS) return 0
  const falta = i.porDia * COBERTURA_DIAS - i.quedan
  return Math.max(1, Math.ceil(falta / i.tamanoPaquete))
}

export interface LineaLista {
  insumo: Insumo
  paquetes: number
  sugeridos: number
}

export function lineasLista(insumos: Insumo[], ajustes: Record<string, number>): LineaLista[] {
  return insumos
    .filter((i) => i.declarado)
    .map((insumo) => {
      const sugeridos = paquetesSugeridos(insumo)
      const paquetes = ajustes[insumo.id] ?? sugeridos
      return { insumo, paquetes, sugeridos }
    })
    .filter((l) => l.sugeridos > 0 || l.paquetes > 0)
    .sort((a, b) => diasRestantes(a.insumo) - diasRestantes(b.insumo))
}

export function totalEstimado(lineas: { paquetes: number; insumo: { precio: number } }[]): number {
  return lineas.reduce((suma, l) => suma + l.paquetes * l.insumo.precio, 0)
}

// ---------- Pago ----------

/** Crédito: se reserva el estimado más la holgura, redondeado hacia arriba al peso. */
export function reservaCredito(estimado: number): number {
  return estimado + Math.ceil((estimado * MARGEN_PORCENTAJE) / 100)
}

export function montoAPagar(estimado: number, medio: 'credito' | 'debito'): number {
  return medio === 'credito' ? reservaCredito(estimado) : estimado
}

/** Lo que vuelve a la persona: liberado (crédito) o devuelto (débito). */
export function diferencia(p: Pedido): number | null {
  if (p.montoReal === null) return null
  return p.montoPagado - p.montoReal
}

export function topeEquivalente(precio: number): number {
  return precio + Math.floor((precio * TOPE_EQUIVALENTE_PORCENTAJE) / 100)
}

// ---------- Relevo ----------

export function accesoVigente(a: Acceso, ahora: number): boolean {
  return a.estado === 'activo' && a.venceMin > ahora
}

export function estadoAccesoTexto(a: Acceso, ahora: number): string {
  if (a.estado === 'revocado') return 'Cortado'
  if (a.estado === 'bloqueado') return 'Bloqueado'
  if (a.venceMin <= ahora) return 'Vencido'
  return 'Activo'
}

function aleatorio(bytes: number): Uint8Array {
  const b = new Uint8Array(bytes)
  crypto.getRandomValues(b)
  return b
}

/** Token de 256 bits en base64url, como el de MATU-18. */
export function nuevoToken(): string {
  let s = ''
  for (const b of aleatorio(32)) s += String.fromCharCode(b)
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

const PIN_EVIDENTES = new Set(['0000', '1111', '1234', '4321', '1212', '2222', '9999'])
export function nuevoPin(): string {
  for (;;) {
    const [a, b] = aleatorio(2)
    const pin = String(((a << 8) | b) % 10000).padStart(4, '0')
    if (!PIN_EVIDENTES.has(pin)) return pin
  }
}

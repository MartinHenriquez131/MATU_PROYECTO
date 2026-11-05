// Fechas y horas en la hora de Chile: DD/MM/AAAA y HH:MM de 24 horas.
// `Intl.DateTimeFormat('es-CL')` escribe 31-10-2026 con guiones, así que la fecha se arma con
// `formatToParts`.
const FORMATO = new Intl.DateTimeFormat('es-CL', {
  timeZone: 'America/Santiago',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

export function fechaYHoraDeChile(instante: Date): { fecha: string; hora: string } {
  const p = Object.fromEntries(FORMATO.formatToParts(instante).map((x) => [x.type, x.value]))
  return { fecha: `${p.day}/${p.month}/${p.year}`, hora: `${p.hour}:${p.minute}` }
}

const DIA = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Santiago', year: 'numeric', month: '2-digit', day: '2-digit' })

/** Hoy en Chile como fecha ISO (AAAA-MM-DD), para comparar con las fechas del contrato. */
export const hoyEnChile = (): string => DIA.format(new Date())

/** Una fecha ISO del contrato (AAAA-MM-DD) en DD/MM/AAAA, sin pasar por la zona horaria. */
export function fechaCorta(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso
}

/** Suma días a una fecha ISO (AAAA-MM-DD), en calendario, sin horas. */
export function sumarDias(iso: string, dias: number): string {
  const [a, m, d] = iso.split('-').map(Number)
  return new Date(Date.UTC(a, m - 1, d + dias)).toISOString().slice(0, 10)
}

const DIA_SEMANA = new Intl.DateTimeFormat('es-CL', { timeZone: 'America/Santiago', weekday: 'long' })

/** Días de calendario de Chile entre `instante` y `ahora` (0 = hoy, 1 = ayer). */
export function diasAtrasEnChile(instante: Date, ahora: Date): number {
  const dia = (d: Date) => {
    const [dd, mm, aaaa] = fechaYHoraDeChile(d).fecha.split('/').map(Number)
    return Date.UTC(aaaa, mm - 1, dd)
  }
  return Math.round((dia(ahora) - dia(instante)) / 86_400_000)
}

/**
 * El día de una fecha, relativo hasta 6 días atrás y absoluto desde el 7.º (decisión D3 de MATU-45):
 * «Hoy», «Ayer», «El sábado», «El 24/10/2026». Con `minuscula`, para ir dentro de una frase.
 */
export function diaRelativoDeChile(instante: Date, ahora: Date, minuscula = false): string {
  const n = diasAtrasEnChile(instante, ahora)
  const texto = n <= 0 ? 'Hoy' : n === 1 ? 'Ayer' : n <= 6 ? `El ${DIA_SEMANA.format(instante)}` : `El ${fechaYHoraDeChile(instante).fecha}`
  return minuscula ? texto.charAt(0).toLowerCase() + texto.slice(1) : texto
}

const PARTES_CHILE = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Santiago',
  year: 'numeric',
  month: 'numeric',
  day: 'numeric',
  hour: 'numeric',
  minute: 'numeric',
  weekday: 'short',
  hourCycle: 'h23',
})
const DIAS_EN = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function partesDeChile(instante: Date) {
  const p = Object.fromEntries(PARTES_CHILE.formatToParts(instante).map((x) => [x.type, x.value]))
  return { anio: Number(p.year), mes: Number(p.month), dia: Number(p.day), hora: Number(p.hour), minuto: Number(p.minute), semana: DIAS_EN.indexOf(p.weekday) }
}

/** El instante de una fecha y hora de pared de Chile (con su horario de verano o de invierno). */
function instanteDeChile(anio: number, mes: number, dia: number, hora: number, minuto: number): Date {
  const pared = Date.UTC(anio, mes - 1, dia, hora, minuto)
  let t = pared + 4 * 3_600_000
  for (let i = 0; i < 3; i++) {
    const p = partesDeChile(new Date(t))
    t += pared - Date.UTC(p.anio, p.mes - 1, p.dia, p.hora, p.minuto)
  }
  return new Date(t)
}

/** «Fin de semana» (MATU-48 3.5): el domingo siguiente a las 23:59 de Chile; si hoy es domingo, el de la otra semana. */
export function finDeSemanaDeChile(ahora: Date): Date {
  const p = partesDeChile(ahora)
  const hasta = p.semana === 0 ? 7 : 7 - p.semana
  const d = new Date(Date.UTC(p.anio, p.mes - 1, p.dia + hasta))
  return instanteDeChile(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate(), 23, 59)
}

/** Lo que falta para `expira`, como la demo (`fmtRestante`): «45 min», «23 h», «3 días». Nunca menos de 1 min. */
export function restante(expira: Date, ahora: Date): string {
  const min = Math.max(1, Math.floor((expira.getTime() - ahora.getTime()) / 60_000))
  if (min < 60) return `${min} min`
  const horas = Math.floor(min / 60)
  if (horas < 48) return `${horas} h`
  return `${Math.floor(horas / 24)} días`
}

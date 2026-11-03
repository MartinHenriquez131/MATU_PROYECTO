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

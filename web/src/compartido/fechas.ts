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

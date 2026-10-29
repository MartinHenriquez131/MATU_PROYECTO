// Del error de la API a lo que ve Rosa. El texto se elige solo por `type` (lenguaje 8); el status
// solo decide si una respuesta desconocida obliga a descartar la ficha.
import { Clock3, Hourglass, KeyRound, Link2Off, Lock, CirclePause, Unlink, type LucideIcon } from 'lucide-react'
import type { FalloApi } from '../compartido/api/cliente'
import { ESPERA, QUE_HAGO } from './textos'

export type EstadoNoAbre = 'bloqueado' | 'vencido' | 'cortado' | 'no-disponible' | 'pausado' | 'sin-sesion' | 'espera'

export interface DefinicionEstado {
  icono: LucideIcon
  titulo: string
  /** Frase que dice por qué. `minutos` solo lo usa el 429. */
  texto: ((minutos: number | null) => string) | null
  /** Acción de la nota «¿Qué hago?», o `null` cuando el enlace sigue sirviendo. */
  accion: string | null
}

// lenguaje 7.3 y especificación 3.5 a 3.10
export const ESTADOS: Record<EstadoNoAbre, DefinicionEstado> = {
  bloqueado: {
    icono: Lock,
    titulo: 'Este enlace se bloqueó',
    texto: () => 'El PIN se escribió mal cinco veces. Por seguridad, el enlace ya no abre.',
    accion: QUE_HAGO.pedirOtro,
  },
  vencido: {
    icono: Clock3,
    titulo: 'Este enlace venció',
    texto: () => 'Los enlaces de MATU duran un tiempo fijo, y el de esta ficha ya terminó.',
    accion: QUE_HAGO.pedirOtro,
  },
  cortado: {
    icono: Unlink,
    titulo: 'Este enlace se cortó',
    texto: () => 'Quien te compartió la ficha cortó el enlace, y ya no abre.',
    accion: QUE_HAGO.pedirOtro,
  },
  'no-disponible': {
    icono: Link2Off,
    titulo: 'Este enlace no está disponible',
    texto: () => 'Puede que se haya copiado incompleto o que ya no exista. Revisa que lo abriste completo desde el mensaje.',
    accion: QUE_HAGO.pedirOtro,
  },
  // D3, decisión de Martín del 28/10: autorización por renovar. No dice el motivo a un tercero.
  // Texto [PROPUESTO]. Ícono pendiente de confirmar por el diseñador.
  pausado: {
    icono: CirclePause,
    titulo: 'Por ahora esta ficha no se puede ver.',
    texto: null,
    accion: QUE_HAGO.revisar,
  },
  'sin-sesion': {
    icono: KeyRound,
    titulo: 'Vuelve a abrir el enlace',
    texto: () => 'Por seguridad, la ficha se cierra después de un rato. Abre de nuevo el enlace que te enviaron y escribe el PIN.',
    accion: null,
  },
  espera: {
    icono: Hourglass,
    titulo: 'Espera un momento',
    texto: (m) => `Hubo muchos intentos de entrar desde esta conexión. ${ESPERA.minutos(m)}`,
    accion: null,
  },
}

/** `type` de la API → estado. `/errores/relevo-pausado` viene de la decisión D3 (pendiente en el contrato). */
const POR_TIPO: Record<string, EstadoNoAbre> = {
  '/errores/relevo-bloqueado': 'bloqueado',
  '/errores/relevo-vencido': 'vencido',
  '/errores/relevo-revocado': 'cortado',
  '/errores/relevo-no-disponible': 'no-disponible',
  '/errores/relevo-pausado': 'pausado',
  '/errores/sin-sesion-relevo': 'sin-sesion',
  '/errores/demasiadas-peticiones': 'espera',
}

export type Clasificacion =
  | { clase: 'estado'; estado: EstadoNoAbre; minutos: number | null }
  | { clase: 'pin-incorrecto'; intentos: number }
  | { clase: 'pin-incompleto' }
  /** Red, 5xx o un `type` no previsto. `descartar` = la respuesta obliga a sacar la ficha. */
  | { clase: 'general'; descartar: boolean }

export function clasificar(f: FalloApi, operacion: 'presentacion' | 'canje' | 'ficha'): Clasificacion {
  const estado = f.tipo ? POR_TIPO[f.tipo] : undefined
  if (estado) {
    const minutos = estado === 'espera' && f.reintentarEnSegundos ? Math.max(1, Math.ceil(f.reintentarEnSegundos / 60)) : null
    return { clase: 'estado', estado, minutos }
  }
  if (operacion === 'canje' && f.tipo === '/errores/pin-incorrecto' && f.intentosRestantes !== null) {
    return { clase: 'pin-incorrecto', intentos: f.intentosRestantes }
  }
  if (f.tipo === '/errores/validacion') {
    // Un 422 de la presentación es un enlace copiado mal (3.0). En el canje, el PIN o el enlace.
    if (operacion === 'canje' && f.campos.includes('pin')) return { clase: 'pin-incompleto' }
    if (operacion !== 'ficha') return { clase: 'estado', estado: 'no-disponible', minutos: null }
  }
  return { clase: 'general', descartar: f.status === 401 || f.status === 410 || f.status === 423 }
}

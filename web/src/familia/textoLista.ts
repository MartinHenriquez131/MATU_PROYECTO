// El texto de la lista de insumos (MATU-60, especificación 4.5, 7.2 y 8.1). Funciones puras: la
// misma `armarLista` alimenta el texto que se comparte o se copia y la hoja que se imprime, así el
// papel y el mensaje nunca dicen cosas distintas. Nunca llevan los días, el nombre de la persona
// cuidada, el del grupo, un enlace ni el de quien comparte (ADR-031, punto 4).
import { fechaCorta } from '../compartido/fechas'
import { LISTA } from './textos'

/** La unidad de una línea: la del insumo, o «envase» solo en lo agregado a mano. */
export type UnidadLinea = 'unidad' | 'sobre' | 'ml' | 'g' | 'envase'

/** «1.200», con punto de miles desde 1.000, como el dinero (4.5). */
export const miles = (n: number) => String(Math.trunc(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '.')

/** «unidad» o «unidades», «sobre» o «sobres», «ml», «g», «envase» o «envases». */
function palabra(n: number, unidad: UnidadLinea): string {
  const uno = n === 1
  switch (unidad) {
    case 'unidad':
      return uno ? 'unidad' : 'unidades'
    case 'sobre':
      return uno ? 'sobre' : 'sobres'
    case 'envase':
      return uno ? 'envase' : 'envases'
    default:
      return unidad
  }
}

/**
 * Lo que va después de la cifra: «envases de 20 unidades», «envase de 250 ml», «unidades»,
 * «sobre», «envases» (agregado a mano). `envase` son las unidades por envase, o `null`.
 */
export function sufijoCantidad(n: number, unidad: UnidadLinea, envase: number | null): string {
  if (envase !== null && unidad !== 'envase') return `${palabra(n, 'envase')} de ${miles(envase)} ${palabra(envase, unidad)}`
  return palabra(n, unidad)
}

/** «6 envases de 20 unidades», «1 sobre», «1.200 unidades». */
export const cantidadEnTexto = (n: number, unidad: UnidadLinea, envase: number | null) => `${miles(n)} ${sufijoCantidad(n, unidad, envase)}`

export interface LineaParaSacar {
  nombre: string
  cantidad: number
  unidad: UnidadLinea
  /** Unidades por envase, o `null`. Lo agregado a mano siempre va con `null`. */
  envase: number | null
}

export interface ListaArmada {
  /** «Lista de insumos · 06/11/2026». */
  titulo: string
  lineas: { nombre: string; cantidad: string }[]
  pie: string
}

/** Lo que sale del teléfono, con la fecha de la API (`fecha`, AAAA-MM-DD) y las líneas en su orden. */
export function armarLista(fecha: string, lineas: readonly LineaParaSacar[]): ListaArmada {
  return {
    titulo: LISTA.encabezado(fechaCorta(fecha)),
    lineas: lineas.map((l) => ({ nombre: l.nombre.replace(/\s+/g, ' ').trim(), cantidad: cantidadEnTexto(l.cantidad, l.unidad, l.envase) })),
    pie: LISTA.pie,
  }
}

/** El texto exacto de 7.2: una línea por insumo, `\n`, sin línea en blanco ni espacios al final. */
export function textoDeLista(lista: ListaArmada): string {
  return [lista.titulo, ...lista.lineas.map((l) => `- ${l.nombre}: ${l.cantidad}`), lista.pie].join('\n')
}

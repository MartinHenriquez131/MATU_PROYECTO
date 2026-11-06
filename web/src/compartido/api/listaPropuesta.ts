// PROVISORIO (MATU-60). Tipos de la lista de insumos y de `unidades_por_envase`, escritos a mano
// desde el contrato propuesto (docs/api/propuestos/app-familia.openapi.yaml: `ListaInsumos`,
// `LineaListaInsumos`, `UnidadesPorEnvase` y los fragmentos `Cambio*`, decisiones 116 a 122).
//
// Cuando el backend exporte la ruta y el perfil a docs/api/openapi.json: `npm run contrato:familia`,
// se borra este archivo y en consumo.ts los tipos pasan a salir de `components['schemas']`
// (`ListaInsumos`, `LineaListaInsumos` y el perfil con `unidades_por_envase`).
import type { components } from './familia.openapi'

type Unidad = components['schemas']['UnidadConsumo']

/** De 1 a 10.000, o `null` si no se anotó (decisión 121). */
export type UnidadesPorEnvase = number | null

/** Una línea de la lista (decisión 118). */
export interface LineaListaInsumos {
  perfil_id: string
  nombre: string
  unidad: Unidad
  dias_restantes: number
  unidades_sugeridas: number
  unidades_por_envase: UnidadesPorEnvase
  envases_sugeridos: number | null
}

/** `GET …/consumo/lista`, sin paginación (decisiones 116 a 118). */
export interface ListaInsumos {
  /** Hoy en Chile según la API, AAAA-MM-DD. */
  fecha: string
  items: LineaListaInsumos[]
}

/**
 * `CambioPerfilConsumoVista`: se suma a `PerfilConsumoVista` e `InsumoPorAcabarseVista`. Opcional
 * aquí mientras la API no lo devuelva: la pantalla lo lee con `?? null`.
 */
export interface CambioPerfilVista {
  unidades_por_envase?: UnidadesPorEnvase
}

/** `CambioSolicitudPerfil` y `CambioSolicitudEdicionPerfil`: omitido no cambia, `null` lo borra (solo en el `PATCH`). */
export interface CambioSolicitudEnvase {
  unidades_por_envase?: UnidadesPorEnvase
}

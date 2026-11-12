// MATU-42: lo que responden `GET …/miembros` y `GET …/invitaciones` en las pruebas de Grupo familiar
// que no son de esta historia (MATU-44 y MATU-72). Desde MATU-53, Grupo familiar pide también quiénes
// forman el grupo. Solo datos sintéticos.
import type { Miembro } from '../src/compartido/api/familia'
import type { RespuestaFalsa } from './apiFalsa'

export const miembroDePrueba = (cambios: Partial<Miembro> = {}): Miembro => ({
  id: '3c9d4e20-0000-4000-8000-00000000m001',
  nombre: 'Carmen Rojas',
  rol: 'admin',
  puede_ver_plan: null,
  unido_en: '2026-11-02T15:00:00Z',
  eres_tu: true,
  etag: '"v1"',
  enlaces_vigentes: 0,
  ...cambios,
})

/** Dos personas, para que «Salir del grupo» no muestre lo de la persona sola (7.3). */
const DOS = [
  miembroDePrueba(),
  miembroDePrueba({ id: '3c9d4e20-0000-4000-8000-00000000m002', nombre: 'Rodrigo Rojas', rol: 'pagador', puede_ver_plan: false, eres_tu: false }),
]

/** La respuesta de las dos rutas del grupo de MATU-42, o `null` si `linea` no es una de ellas. */
export function respuestaDelGrupo(linea: string, miembros: Miembro[] = DOS): RespuestaFalsa | null {
  if (/^GET \/v1\/grupos\/[^/]+\/miembros$/.test(linea)) return { status: 200, cuerpo: { miembros } }
  if (/^GET \/v1\/grupos\/[^/]+\/invitaciones$/.test(linea)) return { status: 200, cuerpo: { invitaciones: [] } }
  return null
}

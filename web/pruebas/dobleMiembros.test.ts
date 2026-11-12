// MATU-53 (revisión visual v1.2, P1): en el doble, las cuentas de pagador y de observador ven su propia
// fila, con «(tú)» (`eres_tu`) y el permiso de la ficha. Antes, el filtro por nombre se llevaba también
// la fila propia. Y la invitación de ejemplo `inv-queda-1` deja exactamente 1 intento. Datos sintéticos.
import type { IncomingMessage, ServerResponse } from 'node:http'
import { describe, expect, it } from 'vitest'
import { atenderFamilia } from '../doble/familia'

interface Respuesta {
  status: number
  cuerpo: Record<string, unknown>
}

/** Una petición al doble, sin servidor: el `req` y el `res` mínimos que usa. */
async function pedir(metodo: string, url: string, cuerpo: Record<string, unknown> | null = null, cabeceras: Record<string, string> = {}): Promise<Respuesta> {
  const r: Respuesta = { status: 0, cuerpo: {} }
  const req = { method: metodo, url, headers: cabeceras } as unknown as IncomingMessage
  const res = { setHeader: () => {}, end: () => {}, once: () => {}, statusCode: 200 } as unknown as ServerResponse
  await atenderFamilia(req, res, cuerpo, {
    json: (_res, status, c) => Object.assign(r, { status, cuerpo: c as Record<string, unknown> }),
    problema: (_res, status, tipo, extra = {}) => Object.assign(r, { status, cuerpo: { type: tipo, ...extra } }),
  })
  return r
}

async function miembrosDe(email: string) {
  const sesion = await pedir('POST', '/v1/sesiones', { email, contrasena: 'contrasena-ejemplo' }) // pragma: allowlist secret
  const auth = { authorization: `Bearer ${String(sesion.cuerpo.access_token)}` }
  const grupos = (await pedir('GET', '/v1/grupos', null, auth)).cuerpo as unknown as { id: string }[]
  const id = grupos[0].id
  const r = await pedir('GET', `/v1/grupos/${id}/miembros`, null, { ...auth, 'x-grupo-id': id })
  return r.cuerpo.miembros as { nombre: string; rol: string; eres_tu: boolean; puede_ver_plan: boolean | null }[]
}

describe('El doble de quiénes forman el grupo', () => {
  it.each([
    ['miembros-pagador@example.com', 'Rodrigo Soto', 'pagador', false],
    ['miembros-pagador-ve@example.com', 'Rodrigo Soto', 'pagador', true],
    ['miembros-observador@example.com', 'Pedro Soto', 'observador', null],
  ] as const)('%s ve su propia fila, con eres_tu y el permiso', async (email, nombre, rol, puede) => {
    const miembros = await miembrosDe(email)
    const propias = miembros.filter((m) => m.eres_tu)
    expect(propias).toHaveLength(1)
    expect(propias[0]).toMatchObject({ nombre, rol, puede_ver_plan: puede })
    // La persona de ejemplo con el mismo nombre no aparece dos veces.
    expect(miembros.filter((m) => m.nombre === nombre)).toHaveLength(1)
  })

  it('miembros-sin-persona: grupo sin personas registradas, con la propia fila de admin y un pagador', async () => {
    const sesion = await pedir('POST', '/v1/sesiones', { email: 'miembros-sin-persona@example.com', contrasena: 'contrasena-ejemplo' }) // pragma: allowlist secret
    const auth = { authorization: `Bearer ${String(sesion.cuerpo.access_token)}` }
    const grupos = (await pedir('GET', '/v1/grupos', null, auth)).cuerpo as unknown as { id: string; rol: string }[]
    expect(grupos[0].rol).toBe('admin')
    const id = grupos[0].id
    const personas = await pedir('GET', `/v1/grupos/${id}/personas-cuidadas`, null, { ...auth, 'x-grupo-id': id })
    expect(personas).toMatchObject({ status: 200, cuerpo: [] })
    const miembros = (await pedir('GET', `/v1/grupos/${id}/miembros`, null, { ...auth, 'x-grupo-id': id })).cuerpo.miembros as { rol: string; eres_tu: boolean }[]
    expect(miembros.filter((m) => m.eres_tu)).toEqual([expect.objectContaining({ rol: 'admin' })])
    expect(miembros.some((m) => m.rol === 'pagador')).toBe(true)
  })

  it('inv-queda-1: un código malo deja 1 intento, y el siguiente la bloquea', async () => {
    const malo = await pedir('POST', '/v1/invitaciones/verificacion', { token: 'inv-queda-1', codigo: '0000' })
    expect(malo).toMatchObject({ status: 422, cuerpo: { intentos_restantes: 1 } })
    expect((await pedir('POST', '/v1/invitaciones/verificacion', { token: 'inv-queda-1', codigo: '0000' })).status).toBe(423)
  })
})

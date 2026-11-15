// MATU-107 (C14): en el doble, push-no-permitido@ responde `permitido: false` y `clave_publica: null`
// (la cuenta no puede activar nada, así que no recibe la clave), y el PUT responde 409; push-409@ tiene
// `permitido: true` y la clave, pero el PUT responde 409 (la regla cambió con la pantalla abierta). Datos sintéticos.
import type { IncomingMessage, ServerResponse } from 'node:http'
import { describe, expect, it } from 'vitest'
import { atenderFamilia } from '../doble/familia'

interface Respuesta {
  status: number
  cuerpo: Record<string, unknown>
}

/** Una petición al doble, sin servidor: el `req` y el `res` mínimos que usa (como dobleMiembros.test.ts). */
async function pedir(metodo: string, url: string, cuerpo: Record<string, unknown> | null = null, cabeceras: Record<string, string> = {}): Promise<Respuesta> {
  const r: Respuesta = { status: 0, cuerpo: {} }
  const req = { method: metodo, url, headers: cabeceras } as unknown as IncomingMessage
  const res = { setHeader: () => {}, end: () => {}, once: () => {}, statusCode: 204 } as unknown as ServerResponse
  await atenderFamilia(req, res, cuerpo, {
    json: (_res, status, c) => Object.assign(r, { status, cuerpo: c as Record<string, unknown> }),
    problema: (_res, status, tipo, extra = {}) => Object.assign(r, { status, cuerpo: { type: tipo, ...extra } }),
  })
  return r
}

async function entrar(email: string) {
  const sesion = await pedir('POST', '/v1/sesiones', { email, contrasena: 'contrasena-ejemplo' }) // pragma: allowlist secret
  return { authorization: `Bearer ${String(sesion.cuerpo.access_token)}` }
}

describe('El doble del push de este teléfono (MATU-107)', () => {
  it('push-no-permitido@: permitido false, sin clave pública, y el PUT responde 409 push-no-permitido', async () => {
    const auth = await entrar('push-no-permitido@example.com')
    const leido = await pedir('GET', '/v1/dispositivos/actual/push', null, auth)
    expect(leido).toMatchObject({ status: 200, cuerpo: { permitido: false, clave_publica: null, registrado: false } })
    const guardado = await pedir('PUT', '/v1/dispositivos/actual/push', { push_token: 'https://push.example.org/envio/sintetico-1' }, auth)
    expect(guardado).toMatchObject({ status: 409, cuerpo: { type: '/errores/push-no-permitido' } })
  })

  it('push-409@: permitido true con la clave, pero el PUT responde 409', async () => {
    const auth = await entrar('push-409@example.com')
    const leido = await pedir('GET', '/v1/dispositivos/actual/push', null, auth)
    expect(leido.status).toBe(200)
    expect(leido.cuerpo.permitido).toBe(true)
    expect(typeof leido.cuerpo.clave_publica).toBe('string')
    const guardado = await pedir('PUT', '/v1/dispositivos/actual/push', { push_token: 'https://push.example.org/envio/sintetico-2' }, auth)
    expect(guardado).toMatchObject({ status: 409, cuerpo: { type: '/errores/push-no-permitido' } })
  })
})

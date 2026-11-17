// MATU-92: el doble de «Tus pedidos» responde como el contrato: la lista de los pagados con la vista
// del observador, el seguimiento sin códigos, el 404 del observador, la `Idempotency-Key` de los
// retractos y cancelar con devolución. Sin servidor: el `req` y el `res` mínimos. Datos sintéticos.
import type { IncomingMessage, ServerResponse } from 'node:http'
import { describe, expect, it } from 'vitest'
import { atenderFamilia } from '../doble/familia'

interface Respuesta {
  status: number
  cuerpo: Record<string, unknown>
}

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

async function entrar(email: string) {
  const sesion = await pedir('POST', '/v1/sesiones', { email, contrasena: 'contrasena-ejemplo' }) // pragma: allowlist secret
  const auth = { authorization: `Bearer ${String(sesion.cuerpo.access_token)}` }
  const grupos = (await pedir('GET', '/v1/grupos', null, auth)).cuerpo as unknown as { id: string }[]
  const h = { ...auth, 'x-grupo-id': grupos[0].id }
  const personas = (await pedir('GET', `/v1/grupos/${grupos[0].id}/personas-cuidadas`, null, h)).cuerpo as unknown as { id: string }[]
  return { h, personaId: personas[0].id }
}

type Fila = Record<string, unknown> & { pedido_id: string; estado: string }

describe('El doble de «Tus pedidos»', () => {
  it('admin: los cuatro pagados, del más reciente, con lo que se puede hacer; con cursor', async () => {
    const { h, personaId } = await entrar('tus-pedidos@example.com')
    const r = await pedir('GET', `/v1/personas-cuidadas/${personaId}/pedidos?limite=3`, null, h)
    expect(r.status).toBe(200)
    const items = r.cuerpo.items as Fila[]
    expect(items.map((f) => f.estado)).toEqual(['pagado', 'preparando', 'entregado'])
    expect(items[0]).toMatchObject({ puede_cancelar: true, cancelar_motivo: null })
    expect(items[2]).toMatchObject({ puede_arrepentirse: true, arrepentirse_motivo: null })
    const mas = await pedir('GET', `/v1/personas-cuidadas/${personaId}/pedidos?cursor=${String(r.cuerpo.siguiente_cursor)}`, null, h)
    expect((mas.cuerpo.items as Fila[]).map((f) => f.estado)).toEqual(['cancelado_con_devolucion'])
    expect(mas.cuerpo.siguiente_cursor).toBeNull()
  })

  it('observador: solo la fecha, los productos y «Pagado»; sin detalle (404)', async () => {
    const { h, personaId } = await entrar('tus-pedidos-observador@example.com')
    const items = (await pedir('GET', `/v1/personas-cuidadas/${personaId}/pedidos`, null, h)).cuerpo.items as Fila[]
    expect(items).toHaveLength(4)
    for (const f of items) {
      expect(Object.keys(f).sort()).toEqual(['estado', 'pagado_en', 'pedido_id', 'productos', 'productos_borrados', 'resumen_productos'])
      expect(f.estado).toBe('pagado')
    }
    expect((await pedir('GET', `/v1/pedidos/${items[0].pedido_id}/seguimiento`, null, h)).status).toBe(404)
    expect((await pedir('POST', `/v1/pedidos/${items[2].pedido_id}/retractos`, { lineas: [] }, h)).status).toBe(404)
  })

  it('el seguimiento nunca trae un código ni la referencia de la parte (C15)', async () => {
    const { h, personaId } = await entrar('tus-pedidos-cuidador@example.com')
    const items = (await pedir('GET', `/v1/personas-cuidadas/${personaId}/pedidos`, null, h)).cuerpo.items as Fila[]
    const s = await pedir('GET', `/v1/pedidos/${items[2].pedido_id}/seguimiento`, null, h)
    expect(s.status).toBe(200)
    expect(JSON.stringify(s.cuerpo)).not.toMatch(/codigo|comercio_id|"referencia_parte"/)
    expect((s.cuerpo.partes as { lineas: { unidades_faltantes: number }[] }[]).flatMap((p) => p.lineas).some((l) => l.unidades_faltantes === 1)).toBe(true)
    // La cuidadora no pagó: no se arrepiente ni cancela, con su motivo.
    expect(items[2]).toMatchObject({ puede_arrepentirse: false, arrepentirse_motivo: 'rol' })
    expect(items[0]).toMatchObject({ puede_cancelar: false, cancelar_motivo: 'rol' })
  })

  it('el retracto exige la clave y la misma clave repite el mismo; cancelar dos veces es 409 estado-pedido', async () => {
    const { h, personaId } = await entrar('tus-pedidos-pagador@example.com')
    const items = (await pedir('GET', `/v1/personas-cuidadas/${personaId}/pedidos`, null, h)).cuerpo.items as Fila[]
    const entregado = items[2].pedido_id
    const datos = (await pedir('GET', `/v1/pedidos/${entregado}/retractos`, null, h)).cuerpo as { lineas: { linea_id: string; disponibles: number }[] }
    const linea = datos.lineas.find((l) => l.disponibles > 0)!
    const cuerpo = { lineas: [{ linea_id: linea.linea_id, cantidad: 1 }] }
    expect((await pedir('POST', `/v1/pedidos/${entregado}/retractos`, cuerpo, h)).status).toBe(428)
    const k = { ...h, 'idempotency-key': 'clave-de-prueba-0001' }
    const a = await pedir('POST', `/v1/pedidos/${entregado}/retractos`, cuerpo, k)
    const b = await pedir('POST', `/v1/pedidos/${entregado}/retractos`, cuerpo, k)
    expect(a.status).toBe(201)
    expect(b.cuerpo.id).toBe(a.cuerpo.id)

    const admin = await entrar('tus-pedidos@example.com')
    const suyos = (await pedir('GET', `/v1/personas-cuidadas/${admin.personaId}/pedidos`, null, admin.h)).cuerpo.items as Fila[]
    const c1 = await pedir('POST', `/v1/pedidos/${suyos[0].pedido_id}/cancelar-con-devolucion`, null, { ...admin.h, 'idempotency-key': 'clave-cancelar-0001' })
    expect(c1.status).toBe(200)
    const c2 = await pedir('POST', `/v1/pedidos/${suyos[0].pedido_id}/cancelar-con-devolucion`, null, { ...admin.h, 'idempotency-key': 'clave-cancelar-0002' })
    expect(c2).toMatchObject({ status: 409, cuerpo: { type: '/errores/estado-pedido' } })
    const c3 = await pedir('POST', `/v1/pedidos/${suyos[1].pedido_id}/cancelar-con-devolucion`, null, { ...admin.h, 'idempotency-key': 'clave-cancelar-0003' })
    expect(c3).toMatchObject({ status: 409, cuerpo: { type: '/errores/ya-se-prepara' } })
  })
})

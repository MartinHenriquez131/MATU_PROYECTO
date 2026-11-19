// MATU-115 (P2 de Martín en el PR #117): el doble de «Datos de» cumple el contrato. Todo pedido de la
// copia trae `retractos` y `lo_que_paso` como listas, en todos los modos; con `datos-pedidos@example.com`
// la pantalla se mostraba caída en `p.retractos.length`. Sin servidor: el `req` y el `res` mínimos, y la
// copia del doble pasa tal cual por la API falsa. Solo datos sintéticos.
import type { IncomingMessage, ServerResponse } from 'node:http'
import { StrictMode } from 'react'
import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { atenderFamilia } from '../doble/familia'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { DatosDePersona } from '../src/familia/DatosPersona'
import { familiaFalsa } from './familiaFalsa'
import { apiCopia, dialogoDeJsdom, MARIA } from './misDatosFalso'
import { responderPolitica } from './politicaFalsa'
import { plazosConCarga } from './conCarga'

plazosConCarga()

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa({ datosDe: MARIA.id, personas: [MARIA], fijar: vi.fn(), anunciar: vi.fn() } as never),
}))

interface Respuesta {
  status: number
  cuerpo: unknown
  texto: string
  cabeceras: Record<string, string>
}

async function pedir(metodo: string, url: string, cuerpo: Record<string, unknown> | null = null, cabeceras: Record<string, string> = {}): Promise<Respuesta> {
  const r: Respuesta = { status: 0, cuerpo: {}, texto: '', cabeceras: {} }
  const req = { method: metodo, url, headers: cabeceras } as unknown as IncomingMessage
  const res = {
    statusCode: 200,
    setHeader: (k: string, v: string) => void (r.cabeceras[k.toLowerCase()] = String(v)),
    end: (t: string) => Object.assign(r, { status: res.statusCode, texto: t }),
    once: () => {},
  } as unknown as ServerResponse & { statusCode: number }
  await atenderFamilia(req, res, cuerpo, {
    json: (_res, status, c) => Object.assign(r, { status, cuerpo: c }),
    problema: (_res, status, tipo, extra = {}) => Object.assign(r, { status, cuerpo: { type: tipo, ...extra } }),
  })
  return r
}

/** La copia de la persona como la entrega el doble: el texto y sus cabeceras. */
async function copiaDelDoble(email: string) {
  const sesion = await pedir('POST', '/v1/sesiones', { email, contrasena: 'contrasena-ejemplo' }) // pragma: allowlist secret
  const auth = { authorization: `Bearer ${String((sesion.cuerpo as { access_token: string }).access_token)}` }
  const grupos = (await pedir('GET', '/v1/grupos', null, auth)).cuerpo as { id: string }[]
  const h = { ...auth, 'x-grupo-id': grupos[0].id }
  const personas = (await pedir('GET', `/v1/grupos/${grupos[0].id}/personas-cuidadas`, null, h)).cuerpo as { id: string }[]
  const r = await pedir('GET', `/v1/personas-cuidadas/${personas[0].id}/datos`, null, h)
  expect(r.status).toBe(200)
  return r
}

beforeEach(() => {
  dialogoDeJsdom()
  window.history.replaceState(null, '', '/grupo/datos')
  responderPolitica()
})

describe('El doble de «Datos de» cumple el contrato en los pedidos (MATU-115)', () => {
  it.each([
    'datos-admin@example.com',
    'datos-cuidador@example.com',
    'datos-retirada@example.com',
    'datos-pausa@example.com',
    'datos-borrada@example.com',
    'datos-sin-capa3@example.com',
    'datos-pedidos@example.com',
    'datos-historial@example.com',
    'datos-sin-asociar@example.com',
    'datos-vacio@example.com',
  ])('%s: todo pedido trae `retractos` y `lo_que_paso` como listas', async (email) => {
    const copia = JSON.parse((await copiaDelDoble(email)).texto) as { pedidos: Record<string, unknown>[] | null }
    for (const p of copia.pedidos ?? []) {
      expect(Array.isArray(p.retractos), `pedido ${String(p.referencia)} (${String(p.estado)}) sin retractos`).toBe(true)
      expect(Array.isArray(p.lo_que_paso), `pedido ${String(p.referencia)} (${String(p.estado)}) sin lo_que_paso`).toBe(true)
    }
  })

  it('datos-pedidos@example.com: «Datos de María» se muestra con sus ocho pedidos, sin caerse', async () => {
    const r = await copiaDelDoble('datos-pedidos@example.com')
    apiCopia({ status: 200, texto: r.texto, cabeceras: r.cabeceras })
    render(
      <StrictMode>
        <RegionesVivas />
        <DatosDePersona />
      </StrictMode>,
    )
    await screen.findByRole('button', { name: 'Descargar en un archivo' })
    const pedidos = screen.getByRole('region', { name: 'Sus pedidos' })
    expect(within(pedidos).getByText('4910')).toBeInTheDocument()
    expect(within(pedidos).getByText('4821')).toBeInTheDocument()
  })
})

// MATU-76 (D-76-1 a, C15; especificación 3.1): el aviso en el teléfono es uno solo y genérico. Corre
// `web/public/sw.js` con un `self` falso, le manda un push y mira qué muestra: «MATU» y «Tienes una
// novedad. Abre la app para verla.», con `tag: 'matu-novedad'`, sin leer el contenido del push.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'

const CODIGO = readFileSync(resolve(__dirname, '../public/sw.js'), 'utf-8')

function correrSw() {
  const manejadores = new Map<string, (e: unknown) => void>()
  const showNotification = vi.fn(async () => {})
  const self = {
    addEventListener: (tipo: string, fn: (e: unknown) => void) => manejadores.set(tipo, fn),
    skipWaiting: vi.fn(),
    registration: { showNotification },
    clients: { claim: vi.fn(), matchAll: vi.fn(async () => []), openWindow: vi.fn() },
    location: { origin: 'https://matu.example.org' },
  }
  new Function('self', CODIGO)(self)
  return { manejadores, showNotification }
}

describe('MATU-76: el push genérico de sw.js', () => {
  it('un solo título y cuerpo, el tag matu-novedad, en es-CL, sin leer el contenido del push', async () => {
    const { manejadores, showNotification } = correrSw()
    const leido = vi.fn()
    const evento = {
      waitUntil: vi.fn(),
      // Si sw.js leyera el contenido, la prueba lo notaría.
      get data() {
        leido()
        return { text: () => 'Pañal talla M', json: () => ({}) }
      },
    }
    manejadores.get('push')!(evento)
    expect(leido).not.toHaveBeenCalled()
    expect(showNotification).toHaveBeenCalledTimes(1)
    expect(showNotification).toHaveBeenCalledWith('MATU', {
      body: 'Tienes una novedad. Abre la app para verla.',
      lang: 'es-CL',
      icon: '/icono-192.png',
      tag: 'matu-novedad',
    })
  })

  it('el texto viejo del insumo ya no está, ni en el código ni en el comentario de la cabecera', () => {
    expect(CODIGO).not.toMatch(/Un insumo se está acabando|matu-insumo/)
    expect(CODIGO).toContain('«MATU · Tienes una novedad. Abre la app para verla.»')
    // No guarda nada: ni caché ni almacenamiento.
    expect(CODIGO).not.toMatch(/caches|indexedDB|localStorage|sessionStorage|\.data\b/)
  })
})

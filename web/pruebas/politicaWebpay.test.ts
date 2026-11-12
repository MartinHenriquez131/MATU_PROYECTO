// MATU-62 (4.5): la política de contenido del build deja enviar el formulario de «Pagar» a Webpay, y a
// ningún otro sitio. Con `form-action 'none'` el navegador bloqueaba la navegación a Transbank.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// La ruta en una variable: Vite cambia un `new URL('literal', import.meta.url)` por la de un recurso.
const leer = (ruta: string) => readFileSync(fileURLToPath(new URL(ruta, import.meta.url)), 'utf8')
const config = leer('../vite.config.ts')
const formAction = /['"](form-action [^'"]+)['"]/.exec(config)?.[1] ?? ''

describe('La política de contenido del build', () => {
  it('form-action permite solo Webpay de integración y de producción', () => {
    expect(formAction.split(/\s+/).slice(1).sort()).toEqual(['https://webpay3g.transbank.cl', 'https://webpay3gint.transbank.cl'])
  })
})

// MATU-61 (9.8, O6): la página pública /condiciones-pedido, con el armado de /privacidad: sin sesión
// ni cookies, la versión y la fecha arriba, el texto en Markdown y sin índice. Solo datos sintéticos.
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { describe, expect, it } from 'vitest'
import { apiPublica } from '../src/compartido/api/politica'
import { PaginaCondiciones } from '../src/privacidad/PaginaCondiciones'
import { conRegionesGlobales } from './pedidoFalso'

const CONDICIONES = {
  version: '0.1',
  actualizada_en: '2026-11-11',
  huella: 'b'.repeat(64),
  texto: '## 1. Quién vende\n\nVende MATU, piloto académico, sin persona jurídica.\n\n## 2. El total\n\nTodos los precios llevan el IVA incluido.\n',
}

function api(...respuestas: { status: number; cuerpo?: unknown }[]) {
  const pedidas: { ruta: string; credenciales: unknown; cabeceras: Record<string, unknown> }[] = []
  apiPublica.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    pedidas.push({ ruta: config.url ?? '', credenciales: config.withCredentials, cabeceras: config.headers.toJSON() as Record<string, unknown> })
    const r = respuestas[Math.min(pedidas.length - 1, respuestas.length - 1)]
    const respuesta = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return pedidas
}

describe('Condiciones del pedido', () => {
  it('el título, la versión y la fecha, las secciones y sin índice; sin sesión ni cookies', async () => {
    const pedidas = api({ status: 200, cuerpo: CONDICIONES })
    conRegionesGlobales(<PaginaCondiciones />)
    expect(screen.getByRole('heading', { level: 1, name: 'Condiciones del pedido' })).toBeVisible()
    expect(await screen.findByRole('heading', { level: 2, name: '1. Quién vende' })).toBeVisible()
    expect(screen.getByText('Versión', { exact: false })).toHaveTextContent('Versión 0.1 · actualizada el 11/11/2026')
    expect(screen.queryByText('Índice')).toBeNull()
    expect(screen.queryByText('Volver al índice')).toBeNull()
    await waitFor(() => expect(document.title).toBe('Condiciones del pedido · MATU'))
    expect(pedidas).toEqual([{ ruta: '/v1/condiciones-pedido', credenciales: false, cabeceras: expect.not.objectContaining({ Authorization: expect.anything() }) }])
  })

  it('sin conexión: el aviso y «Volver a intentar»', async () => {
    api({ status: 503, cuerpo: { type: '/errores/servicio-no-disponible', status: 503 } }, { status: 200, cuerpo: CONDICIONES })
    const { urgente } = conRegionesGlobales(<PaginaCondiciones />)
    await waitFor(() => expect(urgente).toHaveTextContent('No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo.'))
    await userEvent.click(screen.getByRole('button', { name: 'Volver a intentar' }))
    expect(await screen.findByRole('heading', { level: 2, name: '2. El total' })).toBeVisible()
  })
})

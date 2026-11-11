// MATU-60, 9: «¿Cuántas unidades trae cada envase?» en el formulario de Insumos. Opcional, de 1 a
// 10.000. Al cambiar, vaciarlo envía `null` (decisión 121). Al anotar, vacío no se envía. Un valor
// fuera de rango, o el 422 de la API en ese campo, deja el error en el campo con `aria-describedby`.
// El 412 muestra el envase en los dos bloques (9.4). Datos sintéticos.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { Insumos } from '../src/familia/Insumos'
import { problema422 } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'

const PERSONA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María' }
let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

const hoy = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Santiago', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())

const PANAL = {
  id: '3c9d4e20-0000-4000-8000-0000000000c1',
  producto: null,
  nombre_libre: 'Pañal adulto talla M',
  unidad: 'unidad',
  tasa_unidades: 4,
  tasa_dias: 1,
  stock_unidades: 120,
  stock_medido_en: hoy,
  dias_aviso: 7,
  fecha_quiebre_estimada: '2099-01-01',
  dias_restantes: 30,
  activo: true,
  actualizado_por: { id: 'u1', nombre: 'Carmen' },
  unidades_por_envase: 20,
  etag: '"v1"',
}

type Respuesta = { status: number; cuerpo?: unknown }

/** Responde según el método y la ruta, y guarda los cuerpos de lo que se envía. */
function api(escritura: (metodo: string) => Respuesta) {
  const enviados: { metodo: string; cuerpo: unknown }[] = []
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const metodo = (config.method ?? 'get').toUpperCase()
    let r: Respuesta
    if (metodo === 'GET' && /\/consumo\/por-acabarse$/.test(config.url ?? '')) r = { status: 200, cuerpo: { items: [] } }
    else if (metodo === 'GET') r = { status: 200, cuerpo: { items: [PANAL], siguiente_cursor: null } }
    else {
      enviados.push({ metodo, cuerpo: typeof config.data === 'string' ? JSON.parse(config.data) : config.data })
      r = escritura(metodo)
    }
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return enviados
}

async function abrirCambiar(escritura: (metodo: string) => Respuesta) {
  const enviados = api(escritura)
  render(
    <>
      <RegionesVivas />
      <Insumos />
    </>,
  )
  const u = userEvent.setup()
  await u.click(await screen.findByRole('button', { name: 'Cambiar Pañal adulto talla M' }))
  // MATU-84 (5.2): con envase guardado abre en envases. Este archivo prueba el campo en modo sueltos, al final.
  await u.click(await screen.findByRole('button', { name: 'Contar sueltos' }))
  const campo = await screen.findByRole('textbox', { name: '¿Cuántas unidades trae cada envase?' })
  return { enviados, u, campo }
}

beforeEach(() => {
  contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol: 'cuidador' } as never)
  window.history.replaceState(null, '', '/insumos')
})

describe('El campo del envase', () => {
  it('al cambiar trae el valor guardado, y vaciarlo envía `null` con If-Match', async () => {
    const { enviados, u, campo } = await abrirCambiar(() => ({ status: 200, cuerpo: { ...PANAL, unidades_por_envase: null, etag: '"v2"' } }))
    expect(campo).toHaveValue('20')
    expect(campo).toHaveAccessibleDescription('Si lo anotas, la lista sugiere envases enteros. Puedes dejarlo en blanco.')

    await u.clear(campo)
    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(enviados).toHaveLength(1))
    expect(enviados[0]).toEqual({ metodo: 'PATCH', cuerpo: { unidades_por_envase: null } })
  })

  it('sin cambios en el envase no lo envía', async () => {
    const { enviados, u } = await abrirCambiar(() => ({ status: 200, cuerpo: { ...PANAL, stock_unidades: 50, etag: '"v2"' } }))
    await u.type(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' }), '50')
    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(enviados).toHaveLength(1))
    expect(enviados[0].cuerpo).toEqual({ stock_unidades: 50 })
  })

  it('fuera de rango: el error en el campo con aria-describedby, el foco en él y nada se envía', async () => {
    const { enviados, u, campo } = await abrirCambiar(() => ({ status: 200, cuerpo: PANAL }))
    await u.clear(campo)
    await u.type(campo, '10001')
    // maxLength 5: el sexto dígito no entra.
    expect(campo).toHaveValue('10001')
    await u.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(campo).toBeInvalid()
    expect(campo).toHaveAccessibleDescription('Si lo anotas, la lista sugiere envases enteros. Puedes dejarlo en blanco. Escribe un número de 1 a 10.000, o déjalo en blanco.')
    expect(campo).toHaveFocus()
    expect(enviados).toEqual([])

    await u.clear(campo)
    await u.type(campo, '0')
    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(campo).toHaveAccessibleDescription(/Escribe un número de 1 a 10\.000, o déjalo en blanco\.$/)
    expect(enviados).toEqual([])
  })

  it('el 422 de la API en `unidades_por_envase` deja el mismo error en el campo', async () => {
    const { u, campo } = await abrirCambiar(() => ({ status: 422, cuerpo: problema422({ campo: 'unidades_por_envase', tipo: 'less_than_equal' }) }))
    await u.clear(campo)
    await u.type(campo, '30')
    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(campo).toBeInvalid())
    expect(campo).toHaveAccessibleDescription(/Escribe un número de 1 a 10\.000, o déjalo en blanco\.$/)
    expect(screen.queryByText(/texto de la API/)).toBeNull()
  })

  it('el 412 muestra el envase de los dos lados, con «(cambió)»', async () => {
    const actual = { ...PANAL, unidades_por_envase: 30, actualizado_por: { id: 'u2', nombre: 'Rodrigo' }, etag: '"v2"' }
    const { u, campo } = await abrirCambiar(() => ({ status: 412, cuerpo: { type: '/errores/version-desactualizada', status: 412, actual } }))
    await u.clear(campo)
    await u.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(await screen.findByText('Rodrigo cambió «Pañal adulto talla M» mientras lo cambiabas')).toBeVisible()
    expect(screen.getByText(/^Cada envase trae 30 unidades\./).closest('li')).toHaveTextContent('Cada envase trae 30 unidades. (cambió)')
    expect(screen.getByText('Sin unidades por envase.')).toBeVisible()
  })

  it.each([
    ['unidad', 'Cada envase trae 1 unidad.'],
    ['sobre', 'Cada envase trae 1 sobre.'],
    ['ml', 'Cada envase trae 1 ml.'],
    ['g', 'Cada envase trae 1 g.'],
  ])('el 412 con 1 por envase va en singular (9.4): %s', async (unidad, texto) => {
    const actual = { ...PANAL, unidad, unidades_por_envase: 1, actualizado_por: { id: 'u2', nombre: 'Rodrigo' }, etag: '"v2"' }
    const { u, campo } = await abrirCambiar(() => ({ status: 412, cuerpo: { type: '/errores/version-desactualizada', status: 412, actual } }))
    await u.clear(campo)
    await u.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(await screen.findByText('Rodrigo cambió «Pañal adulto talla M» mientras lo cambiabas')).toBeVisible()
    expect(screen.getByText(texto, { exact: false }).closest('li')).toHaveTextContent(`${texto} (cambió)`)
  })
})

describe('Al anotar', () => {
  it('vacío no se envía, y con valor va en el cuerpo', async () => {
    const enviados = api(() => ({ status: 201, cuerpo: PANAL }))
    window.history.replaceState(null, '', '/insumos/nuevo')
    render(
      <>
        <RegionesVivas />
        <Insumos />
      </>,
    )
    const u = userEvent.setup()
    await u.type(await screen.findByRole('textbox', { name: '¿Qué insumo es?' }), 'Gasas')
    await u.type(screen.getByRole('textbox', { name: '¿Cuántos quedan hoy, más o menos?' }), '10')
    const campo = screen.getByRole('textbox', { name: '¿Cuántas unidades trae cada envase?' })
    expect(campo).toHaveValue('')
    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(enviados).toHaveLength(1))
    expect(enviados[0].cuerpo).not.toHaveProperty('unidades_por_envase')
  })
})

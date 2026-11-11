// MATU-88, correcciones del TESTER de Martín (lenguaje.md 5.1, 18 y 30, commit 6932650 del
// repositorio MATU). 1) El relevo ve «¿Cómo es un día normal para {pila}?» sin «Puedes contar un día
// bueno o uno difícil.», que le habla a quien escribe la ficha (criterio de la 5.3); el editor de la
// familia no cambia. 2) En los insumos en sobres, el campo y el error del envase dicen «sobres»; con
// unidad quedan como estaban (H2 del TESTER de MATU-84). Solo datos sintéticos.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FichaRelevo } from '../src/compartido/api/relevo'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { CAMPOS as CAMPOS_FAMILIA } from '../src/familia/datos'
import { Insumos } from '../src/familia/Insumos'
import { PantallaFicha } from '../src/relevo/PantallaFicha'
import type { RespuestaFalsa } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'

// ---------------------------------------------------------------- 1. «Su día» en el relevo

const DIA_BUENO = /Puedes contar un día bueno o uno difícil/

function ficha(texto: string | null): FichaRelevo {
  return { nombre_pila: 'Elena', nombre_pila_comparte: 'Carmen', vence_en: '2026-11-12T20:00:00Z', campos: { rutina: { texto } }, secciones: [] }
}

const seccionSuDia = () => screen.getByRole('heading', { level: 2, name: 'Su día' }).closest('section') as HTMLElement

describe('5.1 · la pregunta de «Su día» (MATU-88)', () => {
  it.each([['con texto', '08:00 Desayuno con té.'], ['sin completar', null]])('el relevo no muestra «Puedes contar un día bueno o uno difícil.», %s', (_, texto) => {
    render(<PantallaFicha ficha={ficha(texto)} onActualizar={async () => 'ok'} />)
    expect(seccionSuDia().querySelector('h2 + p')?.textContent).toBe('¿Cómo es un día normal para Elena?')
    expect(document.body.textContent).not.toMatch(DIA_BUENO)
    for (const el of document.querySelectorAll('[aria-label], [aria-description]'))
      expect(`${el.getAttribute('aria-label')} ${el.getAttribute('aria-description')}`).not.toMatch(DIA_BUENO)
  })

  it('el editor de la familia sigue con la frase', () => {
    expect(CAMPOS_FAMILIA.find((c) => c.api === 'rutina')?.pregunta('Elena')).toBe('¿Cómo es un día normal para Elena? Puedes contar un día bueno o uno difícil.')
  })
})

// ---------------------------------------------------------------- 2. el envase en sobres

const PERSONA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María' }
let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

const BASE = `/v1/personas-cuidadas/${PERSONA.id}/consumo`

const perfil = (id: string, nombre: string, cambios: Record<string, unknown> = {}) => ({
  id: `3c9d4e20-0000-4000-8000-0000000000${id}`,
  producto: null,
  nombre_libre: nombre,
  unidad: 'unidad',
  tasa_unidades: 1,
  tasa_dias: 1,
  stock_unidades: 30,
  stock_medido_en: '2026-11-04',
  dias_aviso: 7,
  fecha_quiebre_estimada: '2026-12-04',
  dias_restantes: 23,
  activo: true,
  actualizado_por: { id: 'u1', nombre: 'Carmen' },
  unidades_por_envase: null,
  etag: '"v1"',
  ...cambios,
})

// Dos insumos sin envase guardado, uno en unidades y otro en sobres.
const GASAS = perfil('e1', 'Gasas')
const CHAMPU = perfil('e2', 'Champú en sobre', { unidad: 'sobre' })

const TEXTOS = {
  unidad: { campo: '¿Cuántas unidades trae cada envase?', error: 'Escribe cuántas unidades trae cada envase.' },
  sobre: { campo: '¿Cuántos sobres trae cada envase?', error: 'Escribe cuántos sobres trae cada envase.' },
} as const

const escritas: string[] = []

function api() {
  escritas.length = 0
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const linea = `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`
    let r: RespuestaFalsa
    if (linea === `GET ${BASE}/por-acabarse`) r = { status: 200, cuerpo: { items: [] } }
    else if (linea === `GET ${BASE}`) r = { status: 200, cuerpo: { items: [GASAS, CHAMPU], siguiente_cursor: null } }
    else {
      escritas.push(linea)
      r = { status: 500, cuerpo: { type: '/errores/error-interno', status: 500 } }
    }
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
}

function montar() {
  api()
  render(
    <>
      <RegionesVivas />
      <Insumos />
    </>,
  )
  return userEvent.setup()
}

beforeEach(() => {
  contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol: 'cuidador' } as never)
  window.history.replaceState(null, '', '/insumos')
})

describe('lenguaje 18 y 30 · el envase dice «sobres» en los insumos en sobres (MATU-88)', () => {
  it.each([
    ['unidad', 'Por unidad'],
    ['sobre', 'Por sobre'],
  ] as const)('el alta, en %s: el campo y el error', async (unidad, opcion) => {
    window.history.replaceState(null, '', '/insumos/nuevo')
    const u = montar()
    await u.type(await screen.findByRole('textbox', { name: '¿Qué insumo es?' }), 'Gasas')
    await u.click(screen.getByRole('radio', { name: opcion }))
    // El campo al final del formulario, en modo sueltos.
    expect(screen.getByRole('textbox', { name: TEXTOS[unidad].campo })).toBeInTheDocument()
    // En envases, con envases enteros y sin envase: el error bajo el envase.
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.type(screen.getByRole('textbox', { name: 'Envases enteros' }), '2')
    await u.click(screen.getByRole('button', { name: 'Guardar' }))
    const campo = screen.getByRole('textbox', { name: TEXTOS[unidad].campo })
    expect(campo).toBeInvalid()
    expect(campo).toHaveAccessibleDescription(`Lo guardamos para la próxima vez y para la lista. ${TEXTOS[unidad].error}`)
    const otra = unidad === 'sobre' ? TEXTOS.unidad : TEXTOS.sobre
    expect(document.body).not.toHaveTextContent(otra.campo)
    expect(document.body).not.toHaveTextContent(otra.error)
    expect(escritas).toEqual([])
  })

  it.each([
    ['unidad', GASAS],
    ['sobre', CHAMPU],
  ] as const)('«Me quedan», en %s: el campo y el error', async (unidad, p) => {
    const u = montar()
    await u.click(await screen.findByRole('button', { name: `Me quedan: ${p.nombre_libre}` }))
    await u.click(screen.getByRole('button', { name: 'Contar en envases' }))
    await u.click(screen.getByRole('button', { name: 'Uno más: Envases enteros' }))
    await u.click(screen.getByRole('button', { name: 'Anotar lo que queda' }))
    const campo = screen.getByRole('textbox', { name: TEXTOS[unidad].campo })
    expect(campo).toBeInvalid()
    expect(campo).toHaveAccessibleDescription(`Lo guardamos para la próxima vez y para la lista. ${TEXTOS[unidad].error}`)
    await waitFor(() => expect(campo).toHaveFocus())
    expect(escritas).toEqual([])
  })
})

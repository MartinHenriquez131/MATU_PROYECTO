// MATU-42 (decisiones 309 y 323) y MATU-53 (5.7): quien ya no está en el grupo llega con `nombre: null`
// y `autor_activo: false`, y la pantalla escribe «alguien que ya no está en el grupo», con el mismo
// estilo de un nombre, en la ficha, las secciones y los enlaces. Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Ficha } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { nombreDeAutor } from '../src/familia/autor'
import { Enlaces } from '../src/familia/Compartir'
import { MasSobre } from '../src/familia/Secciones'
import { responderCon } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'

const MARIA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María' }
const SALIO = { id: '3c9d4e20-0000-4000-8000-0000000000s1', nombre: null, autor_activo: false }

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

describe('nombreDeAutor', () => {
  it('el nombre, quien ya no está (al empezar y dentro de una oración), y nadie', () => {
    expect(nombreDeAutor({ nombre: 'Rodrigo', autor_activo: true })).toBe('Rodrigo')
    expect(nombreDeAutor(SALIO)).toBe('alguien que ya no está en el grupo')
    expect(nombreDeAutor(SALIO, { inicio: true })).toBe('Alguien que ya no está en el grupo')
    // `autor_activo: false` manda aunque viniera un nombre.
    expect(nombreDeAutor({ nombre: 'Rodrigo', autor_activo: false })).toBe('alguien que ya no está en el grupo')
    expect(nombreDeAutor(null)).toBeNull()
  })
})

describe('Donde se muestra un autor', () => {
  it('una sección escrita por quien ya no está: «Lo escribió alguien que ya no está en el grupo:», igual que un nombre', () => {
    contexto = familiaFalsa()
    const ficha = {
      completitud: 100,
      campos: {},
      secciones: { quien_es: { texto: 'Le dicen Mari.', etag: '"v1"', actualizado_por: SALIO, actualizado_en: '2026-11-05T15:00:00Z' } },
    } as unknown as Ficha
    render(<MasSobre ficha={ficha} pila="María" rol="admin" />)
    const linea = screen.getByText(/^Lo escribió/)
    expect(linea).toHaveTextContent(/^Lo escribió alguien que ya no está en el grupo:/)
    // El texto no va en cursiva ni con otro estilo: es quién lo hizo, no un estado.
    expect(linea.innerHTML).not.toMatch(/<i|<em|italic/)
  })

  it('un enlace creado por quien ya no está: «Lo creó alguien que ya no está en el grupo.»', async () => {
    contexto = familiaFalsa({ rol: 'admin', persona: MARIA, personaId: MARIA.id, autorizacion: null, grupo: { id: 'g1', nombre: 'Familia Soto', rol: 'admin', puede_ver_plan: false } } as never)
    const acceso = {
      id: 'a1',
      nombre_relevo: 'Rosa',
      telefono_relevo: null,
      campos: [],
      secciones_adicionales: [],
      motivo: 'otro',
      estado: 'vigente',
      creado_en: '2026-11-05T12:00:00Z',
      expira_en: '2026-11-20T00:30:00Z',
      revocado_en: null,
      usos: 0,
      ultimo_uso_en: null,
      otorgado_por: SALIO,
    }
    responderCon(apiFamilia, { status: 200, cuerpo: { items: [acceso], siguiente_cursor: null, completitud: 100, campos: {} } })
    render(<Enlaces />)
    expect(await screen.findByText(/^Lo creó alguien que ya no está en el grupo\./)).toBeVisible()
  })
})

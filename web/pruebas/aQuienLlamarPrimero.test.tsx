// MATU-95 (especificación docs/diseno/matu-95-ficha-a-quien-llamar.md, 17/11/2026): «A quién llamar»
// va primero en la hoja del relevo y en la de la familia, en un bloque con fondo e ícono. La lista
// para escribir no cambia de orden. Las alergias pasan a una pregunta cotidiana distinta en «Comer y
// beber» y en «Sus remedios» (lenguaje 14.2, decisión de Jorge del 17-11), y la ayuda vieja ya no
// aparece. Solo datos sintéticos: la serie 5555 y nombres de prueba.
import { render, screen } from '@testing-library/react'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FichaRelevo } from '../src/compartido/api/relevo'
import { CAMPOS, SECCIONES } from '../src/familia/datos'
import { EditorDeSeccion } from '../src/familia/EditorSeccion'
import { MAS } from '../src/familia/textos'
import { HojaFicha } from '../src/familia/ui'
import { PantallaFicha } from '../src/relevo/PantallaFicha'
import { familiaFalsa } from './familiaFalsa'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '../src')
const AYUDA_VIEJA = 'Si tiene alergia a algún remedio o alimento, anótalo aquí.'
const COMER = '¿Hay algo que no puede comer o tomar? Anótalo aquí.'
const REMEDIOS = '¿Hay algún remedio que no le pueden dar? Anótalo aquí.'

const RED = 'Rodrigo, su hijo: +56 9 5555 0141'
const SU_DIA = '08:00 Desayuno con té.'
const SE_ALTERA = 'Le hace bien que le tomen la mano.'

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

function fichaRelevo(red: string | null): FichaRelevo {
  return {
    nombre_pila: 'Elena',
    nombre_pila_comparte: 'Carmen',
    vence_en: '2026-11-20T20:00:00Z',
    campos: { rutina: { texto: SU_DIA }, manejo_situaciones: { texto: SE_ALTERA }, red_apoyo: { texto: red } },
    secciones: [],
  }
}

const titulos = (nivel: number) => screen.getAllByRole('heading', { level: nivel }).map((h) => h.textContent)

describe('MATU-95 · el relevo: «A quién llamar» primero', () => {
  it.each([
    ['con texto', RED],
    ['sin completar', null],
  ])('el primer h2 después del nombre es «A quién llamar», %s', (_, red) => {
    render(<PantallaFicha ficha={fichaRelevo(red)} onActualizar={async () => 'ok'} />)
    expect(titulos(1)).toEqual(['Elena'])
    expect(titulos(2)).toEqual(['A quién llamar', 'Su día', 'Si se altera'])
  })

  it('el bloque lleva fondo, borde e ícono; los otros campos no cambian', () => {
    render(<PantallaFicha ficha={fichaRelevo(RED)} onActualizar={async () => 'ok'} />)
    const h2 = screen.getByRole('heading', { level: 2, name: 'A quién llamar' })
    expect(h2).toHaveClass('text-2xl', 'font-bold', 'text-tinta')
    expect(h2.querySelector('svg')).toHaveClass('text-turquesa')
    expect(h2.querySelector('svg')).toHaveAttribute('aria-hidden')
    expect(h2.closest('section')).toHaveClass('bg-rocio', 'border-s-4', 'border-turquesa')
    expect(screen.getByRole('heading', { level: 2, name: 'Su día' })).toHaveClass('text-xl', 'text-turquesa')
    expect(document.querySelectorAll('.bg-rocio')).toHaveLength(1)
  })

  it('el teléfono de ejemplo no se ve, el real no es enlace `tel:` y no hay preguntas de las secciones', () => {
    render(<PantallaFicha ficha={fichaRelevo(RED)} onActualizar={async () => 'ok'} />)
    expect(document.body.textContent).not.toMatch(/5555 0102/)
    expect(document.body.textContent).not.toMatch(/Por ejemplo/)
    expect(document.querySelector('a[href^="tel:"]')).toBeNull()
    expect(document.body.textContent).not.toContain(COMER)
    expect(document.body.textContent).not.toContain(REMEDIOS)
  })
})

describe('MATU-95 · la hoja de la familia (HojaFicha)', () => {
  const textos = { rutina: SU_DIA, manejo_situaciones: SE_ALTERA, red_apoyo: RED }

  it('muestra «A quién llamar» primero, con el bloque en la escala de la hoja', () => {
    render(<HojaFicha pila="Elena" textos={textos} />)
    expect(titulos(3)).toEqual(['A quién llamar', 'Su día', 'Si se altera'])
    const h3 = screen.getByRole('heading', { level: 3, name: 'A quién llamar' })
    expect(h3).toHaveClass('text-xl', 'font-bold', 'text-tinta')
    expect(h3.querySelector('svg')).toHaveClass('text-turquesa')
    expect(h3.closest('section')).toHaveClass('bg-rocio', 'border-s-4', 'border-turquesa')
  })

  it('mientras se escribe ese campo, el borde pasa a miel', () => {
    render(<HojaFicha pila="Elena" textos={textos} escribiendo="red_apoyo" />)
    const bloque = screen.getByRole('heading', { level: 3, name: 'A quién llamar' }).closest('section')
    expect(bloque).toHaveClass('border-miel')
    expect(bloque).not.toHaveClass('border-turquesa', '-ml-3')
  })

  it('la lista para escribir no cambia de orden', () => {
    expect(CAMPOS.map((c) => c.titulo)).toEqual(['Su día', 'Si se altera', 'A quién llamar'])
  })
})

describe('MATU-95 · las alergias en preguntas cotidianas (lenguaje 14.2)', () => {
  const PERSONA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María' }
  const GRUPO = { id: '3c9d4e20-0000-4000-8000-0000000000bb', nombre: 'Familia Soto', rol: 'cuidador', puede_ver_plan: true }
  const vacio = { texto: null, etag: null, actualizado_en: null, actualizado_por: null }

  beforeEach(() => {
    const ficha = { persona_id: PERSONA.id, rutina: vacio, manejo_situaciones: vacio, red_apoyo: vacio, secciones: {}, completitud: 0 }
    contexto = familiaFalsa({ rol: 'cuidador', persona: PERSONA, personaId: PERSONA.id, personas: [PERSONA], grupos: [], grupo: GRUPO, ficha, sinGuardar: { current: null } } as never)
  })

  const ayuda = () => document.getElementById('seccion-ayuda')?.textContent ?? ''

  it.each([
    ['alimentacion', COMER, REMEDIOS],
    ['remedios', REMEDIOS, COMER],
  ] as const)('«%s» muestra su propia ayuda, y no la de la otra sección ni la vieja', (api, propia, otra) => {
    const seccion = SECCIONES.find((s) => s.api === api)!
    window.history.replaceState(null, '', seccion.ruta)
    render(<EditorDeSeccion seccion={seccion} />)
    expect(ayuda()).toContain(propia)
    expect(ayuda()).not.toContain(otra)
    expect(document.body.textContent).not.toContain(AYUDA_VIEJA)
  })

  it('las demás secciones no llevan ayuda de alergias', () => {
    for (const s of SECCIONES.filter((x) => x.api !== 'alimentacion' && x.api !== 'remedios')) expect(s.alergias).toBeNull()
    expect(MAS.alergias).toEqual({ alimentacion: COMER, remedios: REMEDIOS })
  })

  it('«Comer y beber» mantiene el dictado; «Sus remedios» sigue sin él (decisión de Jorge)', () => {
    vi.stubGlobal('webkitSpeechRecognition', class {})
    for (const [api, conDictado] of [
      ['alimentacion', true],
      ['remedios', false],
    ] as const) {
      const seccion = SECCIONES.find((s) => s.api === api)!
      window.history.replaceState(null, '', seccion.ruta)
      const { unmount } = render(<EditorDeSeccion seccion={seccion} />)
      expect(screen.queryByRole('button', { name: 'Dictar en vez de escribir' }) !== null).toBe(conDictado)
      unmount()
    }
    vi.unstubAllGlobals()
  })

  it('la ayuda vieja ya no aparece en ningún archivo de la aplicación', () => {
    const archivos = (dir: string): string[] =>
      readdirSync(dir).flatMap((n) => {
        const p = join(dir, n)
        return statSync(p).isDirectory() ? archivos(p) : /\.(ts|tsx)$/.test(n) ? [p] : []
      })
    for (const a of archivos(SRC)) expect(readFileSync(a, 'utf-8'), a).not.toContain(AYUDA_VIEJA)
  })
})

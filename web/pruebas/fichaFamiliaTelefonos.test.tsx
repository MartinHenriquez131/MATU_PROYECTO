// MATU-86: la hoja de la familia dibuja los teléfonos igual que el relevo (especificación MATU-23,
// 3.11.4; Demo/DISENO.md, sección 1: la hoja se ve igual en el inicio, al editar y en el relevo).
// La hoja del inicio y de la edición de un campo es `HojaFicha`; la del editor de una sección es
// `HojaSeccion`; la tarjeta de una sección usa `TextoSeccion` recortado. Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { HojaFicha, HojaSeccion, TextoSeccion } from '../src/familia/ui'

// La misma ficha de prueba del relevo (sección 8, `ejemplo-telefonos` del doble).
const RED = 'Rodrigo, su hijo: +56 9 5555 0141\nAna, la vecina del 3: 9 5555-0102. Si no contesta, a la farmacia +56 2 2555 0123\nConsultorio: +56955550199\nSu hermana: +56-9-5555-0177'
const SE_ALTERA = 'Le hace bien que la llame su hermana al 9 5555 0177 a las 18:00'
const SU_DIA = '08:00 Desayuno con té.\n10:00 Si tiene dolor, llamar a Rodrigo +56 9 5555 0141\n16:00 Llega el pedido de $69.000 que se pagó el 10/11/2026.'
const SECCION = 'Su nieta Sofía (+56 9 5555 0163) la visita los domingos a las 11:00.\nSi no está, su nieto al 9 5555-0102.'

const textos = { rutina: SU_DIA, manejo_situaciones: SE_ALTERA, red_apoyo: RED }
const seccion = (titulo: string) => screen.getByRole('heading', { level: 3, name: titulo }).closest('section') as HTMLElement
const bloques = (el: ParentNode) => [...el.querySelectorAll<HTMLElement>('span.inline-block')]

/** Cada bloque, como en el relevo: un inline-block con dos cifras y, tras un guion o sin separador, un <wbr>. */
function comoEnElRelevo(b: HTMLElement) {
  expect(b).toHaveClass('inline-block', 'max-w-full', 'tabular-nums')
  expect(b.querySelectorAll(':scope > span.cifras')).toHaveLength(2)
  const separador = b.childNodes[1].nodeName === '#text' ? b.childNodes[1].textContent : ''
  expect(b.children).toHaveLength(separador === ' ' ? 2 : 3)
  expect(b.closest('a')).toBeNull()
  expect([...b.attributes].map((a) => a.name)).toEqual(['class'])
}

describe('MATU-86 · la hoja del inicio y de la edición de un campo (HojaFicha)', () => {
  it('cada teléfono queda en un solo bloque, sin partir, igual que en el relevo', () => {
    render(<HojaFicha pila="Elena" textos={textos} secciones={[{ api: 'quien_es', texto: SECCION }]} />)
    const todos = bloques(document)
    expect(todos.map((b) => b.textContent)).toEqual([
      '+56 9 5555 0141', // Su día, en la línea de tiempo
      '9 5555 0177', // Si se altera, junto a una hora
      '+56 9 5555 0141',
      '9 5555-0102.',
      '+56 2 2555 0123',
      '+56955550199',
      '+56-9-5555-0177',
      '(+56 9 5555 0163)', // la sección, con sus paréntesis
      '9 5555-0102.',
    ])
    todos.forEach(comoEnElRelevo)
    expect([...todos[0].querySelectorAll('.cifras')].map((c) => c.textContent)).toEqual(['+56 9', '5555 0141'])
    // Con guion: el guion queda y después va el <wbr>.
    expect([...todos[6].childNodes].map((n) => n.nodeName)).toEqual(['SPAN', '#text', 'WBR', 'SPAN'])
    expect([...todos[6].childNodes].map((n) => n.textContent)).toEqual(['+56-9', '-', '', '5555-0177'])
    // Sin separador: un <wbr> entre el prefijo y el resto.
    expect([...todos[5].childNodes].map((n) => n.nodeName)).toEqual(['SPAN', 'WBR', 'SPAN'])
  })

  it('el textContent es el texto de la API, carácter por carácter', () => {
    render(<HojaFicha pila="Elena" textos={textos} secciones={[{ api: 'quien_es', texto: SECCION }]} />)
    const parrafos = (titulo: string) => [...seccion(titulo).querySelectorAll('div.renglones > p')].map((p) => p.textContent)
    expect(parrafos('A quién llamar')).toEqual(RED.split('\n'))
    expect(parrafos('Si se altera')).toEqual([SE_ALTERA])
    const horas = [...seccion('Su día').querySelectorAll('ol > li > span:last-child')].map((s) => s.textContent)
    expect(horas).toEqual(['Desayuno con té.', 'Si tiene dolor, llamar a Rodrigo +56 9 5555 0141', 'Llega el pedido de $69.000 que se pagó el 10/11/2026.'])
    expect(seccion('Quién es').querySelector('p:last-child')?.textContent).toBe(SECCION)
  })

  it('en la sección, la hora sigue en su propia cifra, fuera del bloque del número', () => {
    render(<HojaFicha pila="Elena" textos={textos} secciones={[{ api: 'quien_es', texto: SECCION }]} />)
    const p = seccion('Quién es').querySelector('p:last-child') as HTMLElement
    expect([...p.querySelectorAll(':scope > .cifras')].map((c) => c.textContent)).toEqual(['11:00'])
  })

  it('un número que no es teléfono no se toca', () => {
    const otros = 'Pedido de $69.000 el 10/11/2026 a las 08:30.\nRUT 12.345.678-9, 2 pañales cada 6 horas, PIN 4821, 5555 0141 y 22 555 0123'
    render(<HojaFicha pila="Elena" textos={{ rutina: null, manejo_situaciones: otros, red_apoyo: null }} secciones={[{ api: 'preferencias', texto: otros }]} />)
    expect(bloques(document)).toEqual([])
    expect([...seccion('Si se altera').querySelectorAll('div.renglones > p')].map((p) => p.textContent)).toEqual(otros.split('\n'))
    expect(seccion('Lo que le hace bien').querySelector('p:last-child')?.textContent).toBe(otros)
  })
})

describe('MATU-86 · la vista del editor de una sección (HojaSeccion)', () => {
  it('el teléfono no se parte y el texto queda igual', () => {
    render(<HojaSeccion pila="Elena" seccion="quien_es" texto={SECCION} />)
    const todos = bloques(document)
    expect(todos.map((b) => b.textContent)).toEqual(['(+56 9 5555 0163)', '9 5555-0102.'])
    todos.forEach(comoEnElRelevo)
    expect([...todos[0].querySelectorAll('.cifras')].map((c) => c.textContent)).toEqual(['(+56 9', '5555 0163)'])
    expect(seccion('Quién es').querySelector('p:last-child')?.textContent).toBe(SECCION)
  })

  it('mientras se escribe un número a medias, no se arma ningún bloque', () => {
    render(<HojaSeccion pila="Elena" seccion="quien_es" texto="Su nieto: +56 9 5555 01" />)
    expect(bloques(document)).toEqual([])
  })
})

describe('MATU-86 · la tarjeta de una sección (TextoSeccion recortado)', () => {
  it('el teléfono no se parte y el texto queda igual', () => {
    const { container } = render(<TextoSeccion texto={SECCION} recortar />)
    expect(bloques(container).map((b) => b.textContent)).toEqual(['(+56 9 5555 0163)', '9 5555-0102.'])
    expect(container.querySelector('p')?.textContent).toBe(SECCION)
  })
})

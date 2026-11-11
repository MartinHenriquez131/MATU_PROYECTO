// Tarjeta «Relevo: el teléfono escrito en la ficha no se parte, y "A quién llamar" le habla a quien
// reemplaza» (especificación MATU-23, 3.11.4 y 3.11.5, 10/11/2026). Las dos tablas de 3.11.4 van
// tal cual. Solo datos sintéticos: la serie 5555 y nombres de prueba.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { FichaRelevo } from '../src/compartido/api/relevo'
import { PantallaFicha } from '../src/relevo/PantallaFicha'
import { partesDeTelefono, TELEFONO, trozosConTelefonos, type Trozo } from '../src/relevo/telefonos'

const calces = (texto: string) => [...texto.matchAll(TELEFONO)].map((m) => m[0])
const unir = (texto: string) =>
  trozosConTelefonos(texto)
    .map((t) => (t.tipo === 'texto' ? t.texto : t.abre + t.prefijo + t.separador + t.resto + t.cierra))
    .join('')

// 3.11.4, «Ejemplos que sí calzan»: texto, lo que calza, prefijo y resto.
const SI_CALZAN: [string, string, string, string][] = [
  ['Rodrigo, su hijo: +56 9 5555 0141', '+56 9 5555 0141', '+56 9', '5555 0141'],
  ['+56 9 5555-0141', '+56 9 5555-0141', '+56 9', '5555-0141'],
  ['+56-9-5555-0141', '+56-9-5555-0141', '+56-9', '5555-0141'],
  ['+569 5555 0141', '+569 5555 0141', '+569', '5555 0141'],
  ['+56955550141', '+56955550141', '+569', '55550141'],
  ['56 9 5555 0141', '56 9 5555 0141', '56 9', '5555 0141'],
  ['Llama al 9 5555 0141.', '9 5555 0141', '9', '5555 0141'],
  ['955550141', '955550141', '9', '55550141'],
  ['(+56 9 5555 0141)', '+56 9 5555 0141', '+56 9', '5555 0141'],
  ['+56 2 2555 0123', '+56 2 2555 0123', '+56 2', '2555 0123'],
  ['+56 32 255 0123', '+56 32 255 0123', '+56 32', '255 0123'],
]

// 3.11.4, «Ejemplos que no calzan».
const NO_CALZAN = [
  '10/11/2026',
  '08:00',
  '8.30',
  '$69.000',
  '$955.550.141',
  '12.345.678-9',
  '12345678-9',
  '95555014-1',
  '2 pañales cada 6 horas',
  '5555 0141',
  '9 5555 014',
  '+56 9 5555 01412',
  'PIN 4821',
  '2026 0141',
  '9.5555.0141',
  '22 555 0123',
]

describe('3.11.4 · qué se reconoce como teléfono', () => {
  it.each(SI_CALZAN)('«%s» calza como «%s», en «%s» y «%s»', (texto, calza, prefijo, resto) => {
    expect(calces(texto)).toEqual([calza])
    const p = partesDeTelefono(calza)
    expect(p && { prefijo: p.prefijo, resto: p.resto }).toEqual({ prefijo, resto })
    expect(p && p.prefijo + p.separador + p.resto).toBe(calza)
    expect(unir(texto)).toBe(texto)
  })

  it('el guion queda entre el prefijo y el resto, tal como lo escribió la familia', () => {
    expect(partesDeTelefono('+56-9-5555-0141')?.separador).toBe('-')
    expect(partesDeTelefono('+56955550141')?.separador).toBe('')
    expect(partesDeTelefono('+56 9 5555 0141')?.separador).toBe(' ')
  })

  it('dos números en la misma línea se reconocen por separado', () => {
    const texto = 'Ana: 9 5555 0141, Rodrigo: +56 9 5555 0102'
    expect(calces(texto)).toEqual(['9 5555 0141', '+56 9 5555 0102'])
    const tel = trozosConTelefonos(texto).filter((t) => t.tipo === 'telefono')
    expect(tel).toEqual([
      { tipo: 'telefono', abre: '', prefijo: '9', separador: ' ', resto: '5555 0141', cierra: ',' },
      { tipo: 'telefono', abre: '', prefijo: '+56 9', separador: ' ', resto: '5555 0102', cierra: '' },
    ])
    expect(unir(texto)).toBe(texto)
  })

  // 3.11.4 v1.3: la puntuación pegada al número cambia de trozo, nunca de lugar ni de carácter.
  const tel = (abre: string, prefijo: string, separador: string, resto: string, cierra: string): Trozo => ({
    tipo: 'telefono',
    abre,
    prefijo,
    separador,
    resto,
    cierra,
  })
  it.each<[string, Trozo[]]>([
    ['Su nieta Sofía (+56 9 5555 0163) la visita', [{ tipo: 'texto', texto: 'Su nieta Sofía ' }, tel('(', '+56 9', ' ', '5555 0163', ')'), { tipo: 'texto', texto: ' la visita' }]],
    ['Ana: 9 5555-0102. Si no contesta', [{ tipo: 'texto', texto: 'Ana: ' }, tel('', '9', ' ', '5555-0102', '.'), { tipo: 'texto', texto: ' Si no contesta' }]],
    ['(+56 9 5555 0141)', [tel('(', '+56 9', ' ', '5555 0141', ')')]],
    ['«+56955550199».', [tel('«', '+569', '', '55550199', '».')]],
    ['[9 5555 0141];', [tel('[', '9', ' ', '5555 0141', '];')]],
    ['¿9 5555 0141?', [tel('¿', '9', ' ', '5555 0141', '?')]],
    ['¡+56 2 2555 0123!', [tel('¡', '+56 2', ' ', '2555 0123', '!')]],
    ['“9 5555 0141”, dijo', [tel('“', '9', ' ', '5555 0141', '”,'), { tipo: 'texto', texto: ' dijo' }]],
    ['"9 5555 0141":', [tel('"', '9', ' ', '5555 0141', '":')]],
    // Con un espacio en medio, el signo no se pega: queda en el texto.
    ['( 9 5555 0141 )', [{ tipo: 'texto', texto: '( ' }, tel('', '9', ' ', '5555 0141', ''), { tipo: 'texto', texto: ' )' }]],
    // Solo un signo de apertura, y un cierre más una puntuación.
    ['((9 5555 0141)).', [{ tipo: 'texto', texto: '(' }, tel('(', '9', ' ', '5555 0141', ')'), { tipo: 'texto', texto: ').' }]],
    ['9 5555 0141...', [tel('', '9', ' ', '5555 0141', '.'), { tipo: 'texto', texto: '..' }]],
  ])('«%s»: la apertura y el cierre pegados van con el número', (texto, trozos) => {
    expect(trozosConTelefonos(texto)).toEqual(trozos)
    expect(unir(texto)).toBe(texto)
  })

  it.each(NO_CALZAN)('«%s» no calza', (texto) => {
    expect(calces(texto)).toEqual([])
    expect(trozosConTelefonos(texto)).toEqual([{ tipo: 'texto', texto }])
  })
})

// La ficha de prueba de la sección 8 (la misma del doble, `ejemplo-telefonos`).
const RED = 'Rodrigo, su hijo: +56 9 5555 0141\nAna, la vecina del 3: 9 5555-0102. Si no contesta, a la farmacia +56 2 2555 0123\nConsultorio: +56955550199\nSu hermana: +56-9-5555-0177'
const SE_ALTERA = 'Le hace bien que la llame su hermana al 9 5555 0177 a las 18:00'
const SU_DIA = '08:00 Desayuno con té.\n10:00 Si tiene dolor, llamar a Rodrigo +56 9 5555 0141\n16:00 Llega el pedido de $69.000 que se pagó el 10/11/2026.'
const SECCION = 'Su nieta Sofía (+56 9 5555 0163) la visita los domingos a las 11:00.'

function ficha(): FichaRelevo {
  return {
    nombre_pila: 'Elena',
    nombre_pila_comparte: 'Carmen',
    vence_en: '2026-11-12T20:00:00Z',
    campos: { rutina: { texto: SU_DIA }, manejo_situaciones: { texto: SE_ALTERA }, red_apoyo: { texto: RED } },
    secciones: [{ tipo: 'quien_es', texto: SECCION }],
  }
}

const seccion = (titulo: string) => screen.getByRole('heading', { level: 2, name: titulo }).closest('section') as HTMLElement
const bloques = (el: ParentNode) => [...el.querySelectorAll<HTMLElement>('span.inline-block')]

describe('3.11.4 · el teléfono se dibuja sin cambiar el texto', () => {
  it('el textContent de cada párrafo es su línea del texto de la API, en cada campo y en las secciones', () => {
    render(<PantallaFicha ficha={ficha()} onActualizar={async () => 'ok'} />)
    const parrafos = (titulo: string) => [...seccion(titulo).querySelectorAll('div.renglones > p')].map((p) => p.textContent)
    expect(parrafos('A quién llamar')).toEqual(RED.split('\n'))
    expect(parrafos('Si se altera')).toEqual([SE_ALTERA])
    expect(parrafos('Quién es')).toEqual([SECCION])
  })

  it('en la línea de tiempo, el texto de cada hora queda intacto', () => {
    render(<PantallaFicha ficha={ficha()} onActualizar={async () => 'ok'} />)
    const textos = [...seccion('Su día').querySelectorAll('ol > li > span:last-child')].map((s) => s.textContent)
    expect(textos).toEqual(['Desayuno con té.', 'Si tiene dolor, llamar a Rodrigo +56 9 5555 0141', 'Llega el pedido de $69.000 que se pagó el 10/11/2026.'])
  })

  it('cada número va en un inline-block con dos cifras: el prefijo y el resto', () => {
    render(<PantallaFicha ficha={ficha()} onActualizar={async () => 'ok'} />)
    const todos = bloques(document)
    expect(todos.map((b) => b.textContent)).toEqual([
      '+56 9 5555 0141', // Su día, en la línea de tiempo
      '9 5555 0177', // Si se altera, junto a una hora
      '+56 9 5555 0141',
      '9 5555-0102.', // con el punto que lo sigue
      '+56 2 2555 0123',
      '+56955550199',
      '+56-9-5555-0177',
      '(+56 9 5555 0163)', // la sección, con sus paréntesis
    ])
    for (const b of todos) {
      expect(b).toHaveClass('inline-block', 'max-w-full', 'tabular-nums')
      const cifras = b.querySelectorAll(':scope > span.cifras')
      expect(cifras).toHaveLength(2)
      // <wbr> después de un guion o donde no hay separador; con un espacio, no (3.11.4 v1.3).
      const separador = b.childNodes[1].nodeName === '#text' ? b.childNodes[1].textContent : ''
      expect(b.children).toHaveLength(separador === ' ' ? 2 : 3)
      // Sin enlace, sin aria-* nuevos y sin partir en cualquier lugar.
      expect(b.closest('a')).toBeNull()
      expect([...b.attributes].map((a) => a.name)).toEqual(['class'])
      expect(b.className).not.toMatch(/break-all|wrap-anywhere/)
    }
    const [, alteraTel] = todos
    expect([...alteraTel.querySelectorAll('.cifras')].map((c) => c.textContent)).toEqual(['9', '5555 0177'])
    // La puntuación pegada va dentro de las cifras: al principio del prefijo y al final del resto.
    const sofia = todos[todos.length - 1]
    expect([...sofia.querySelectorAll('.cifras')].map((c) => c.textContent)).toEqual(['(+56 9', '5555 0163)'])
    expect([...todos[3].querySelectorAll('.cifras')].map((c) => c.textContent)).toEqual(['9', '5555-0102.'])
    // En las secciones, la hora sigue en su propia cifra, fuera del bloque del número.
    const enSeccion = seccion('Quién es').querySelector('p') as HTMLElement
    expect([...enSeccion.querySelectorAll(':scope > .cifras')].map((c) => c.textContent)).toEqual(['11:00'])
  })

  it('sin separador va un <wbr> entre el prefijo y el resto', () => {
    render(<PantallaFicha ficha={ficha()} onActualizar={async () => 'ok'} />)
    const sinSeparador = bloques(document).find((b) => b.textContent === '+56955550199') as HTMLElement
    const hijos = [...sinSeparador.childNodes]
    expect(hijos.map((n) => n.nodeName)).toEqual(['SPAN', 'WBR', 'SPAN'])
    expect(hijos.map((n) => n.textContent)).toEqual(['+569', '', '55550199'])
    // Con espacio, el espacio de la familia queda entre las dos cifras y no hay <wbr>.
    const conEspacio = bloques(seccion('A quién llamar'))[0]
    expect([...conEspacio.childNodes].map((n) => n.nodeName)).toEqual(['SPAN', '#text', 'SPAN'])
    expect(conEspacio.childNodes[1].textContent).toBe(' ')
  })

  it('con un guion entre el prefijo y el resto, el guion queda y después va un <wbr> (Firefox no corta solo)', () => {
    render(
      <PantallaFicha
        ficha={{ ...ficha(), campos: { red_apoyo: { texto: 'Rodrigo: +56-9-5555-0141' } }, secciones: [] }}
        onActualizar={async () => 'ok'}
      />,
    )
    const [b] = bloques(document)
    expect([...b.childNodes].map((n) => n.nodeName)).toEqual(['SPAN', '#text', 'WBR', 'SPAN'])
    expect([...b.childNodes].map((n) => n.textContent)).toEqual(['+56-9', '-', '', '5555-0141'])
    expect(b.parentElement?.textContent).toBe('Rodrigo: +56-9-5555-0141')
  })

  it('el «(» y el «).» pegados quedan dentro del bloque y el párrafo dice lo mismo que la API', () => {
    const texto = 'Rodrigo (+56 9 5555 0141). Ana (9 5555-0102), y «+56955550199».'
    render(<PantallaFicha ficha={{ ...ficha(), campos: { red_apoyo: { texto } }, secciones: [] }} onActualizar={async () => 'ok'} />)
    expect(bloques(document).map((b) => b.textContent)).toEqual(['(+56 9 5555 0141).', '(9 5555-0102),', '«+56955550199».'])
    const p = seccion('A quién llamar').querySelector('div.renglones > p') as HTMLElement
    expect(p.textContent).toBe(texto)
    // Fuera de los bloques quedan solo las palabras y los espacios.
    const fuera = [...p.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.textContent)
    expect(fuera).toEqual(['Rodrigo ', ' Ana ', ' y '])
  })

  it('un monto, una fecha y una hora no quedan dentro de un bloque de teléfono', () => {
    render(<PantallaFicha ficha={ficha()} onActualizar={async () => 'ok'} />)
    for (const b of bloques(document)) for (const t of ['$69.000', '10/11/2026', '18:00', '11:00', '10:00']) expect(b.textContent).not.toContain(t)
  })
})

// MATU-60, 4.5 y 7.2: el texto que se comparte, se copia y se imprime sale de una sola función, con
// el formato exacto de lenguaje.md, sección 21. Sin días, sin el nombre de la persona ni del grupo, y
// con la fecha del campo `fecha` de la API. Datos sintéticos.
import { describe, expect, it } from 'vitest'
import { armarLista, cantidadEnTexto, sufijoCantidad, textoDeLista } from '../src/familia/textoLista'

describe('La cantidad en texto (4.5)', () => {
  it('con envase: en envases, con las unidades de cada uno', () => {
    expect(cantidadEnTexto(6, 'unidad', 20)).toBe('6 envases de 20 unidades')
    expect(cantidadEnTexto(1, 'unidad', 20)).toBe('1 envase de 20 unidades')
    expect(cantidadEnTexto(2, 'ml', 250)).toBe('2 envases de 250 ml')
    expect(cantidadEnTexto(1, 'g', 500)).toBe('1 envase de 500 g')
    expect(cantidadEnTexto(3, 'sobre', 10)).toBe('3 envases de 10 sobres')
  })

  it('con envase de 1: el singular de la unidad', () => {
    expect(cantidadEnTexto(4, 'unidad', 1)).toBe('4 envases de 1 unidad')
    expect(cantidadEnTexto(4, 'sobre', 1)).toBe('4 envases de 1 sobre')
  })

  it('sin envase: en la unidad del insumo, con su singular', () => {
    expect(cantidadEnTexto(120, 'unidad', null)).toBe('120 unidades')
    expect(cantidadEnTexto(1, 'unidad', null)).toBe('1 unidad')
    expect(cantidadEnTexto(30, 'sobre', null)).toBe('30 sobres')
    expect(cantidadEnTexto(1, 'sobre', null)).toBe('1 sobre')
    expect(cantidadEnTexto(215, 'ml', null)).toBe('215 ml')
    expect(cantidadEnTexto(30, 'g', null)).toBe('30 g')
  })

  it('lo agregado a mano, en sus tres unidades y con 1', () => {
    expect(cantidadEnTexto(3, 'unidad', null)).toBe('3 unidades')
    expect(cantidadEnTexto(1, 'unidad', null)).toBe('1 unidad')
    expect(cantidadEnTexto(2, 'sobre', null)).toBe('2 sobres')
    expect(cantidadEnTexto(1, 'sobre', null)).toBe('1 sobre')
    expect(cantidadEnTexto(2, 'envase', null)).toBe('2 envases')
    expect(cantidadEnTexto(1, 'envase', null)).toBe('1 envase')
  })

  it('con punto de miles desde 1.000, también en el envase', () => {
    expect(cantidadEnTexto(1200, 'unidad', null)).toBe('1.200 unidades')
    expect(cantidadEnTexto(100000, 'unidad', null)).toBe('100.000 unidades')
    expect(cantidadEnTexto(999, 'unidad', null)).toBe('999 unidades')
    expect(cantidadEnTexto(2, 'ml', 1000)).toBe('2 envases de 1.000 ml')
  })

  it('el sufijo del campo es el mismo texto sin la cifra', () => {
    expect(sufijoCantidad(6, 'unidad', 20)).toBe('envases de 20 unidades')
    expect(sufijoCantidad(1, 'envase', null)).toBe('envase')
    expect(sufijoCantidad(0, 'unidad', null)).toBe('unidades')
  })
})

describe('El texto de la lista (7.2)', () => {
  it('tiene el formato exacto, con la fecha de la API en DD/MM/AAAA', () => {
    const lista = armarLista('2026-11-06', [
      { nombre: 'Pañal adulto talla M', cantidad: 6, unidad: 'unidad', envase: 20 },
      { nombre: 'Toallitas húmedas', cantidad: 120, unidad: 'unidad', envase: null },
      { nombre: 'Toallitas para el baño', cantidad: 2, unidad: 'envase', envase: null },
    ])
    expect(textoDeLista(lista)).toBe(
      'Lista de insumos · 06/11/2026\n' +
        '- Pañal adulto talla M: 6 envases de 20 unidades\n' +
        '- Toallitas húmedas: 120 unidades\n' +
        '- Toallitas para el baño: 2 envases\n' +
        'Piloto académico con datos de prueba',
    )
  })

  it('lo agregado a mano en sus tres unidades, en el orden en que llegan', () => {
    const texto = textoDeLista(
      armarLista('2026-01-31', [
        { nombre: 'Toallitas húmedas', cantidad: 2, unidad: 'envase', envase: null },
        { nombre: 'Gasas', cantidad: 1, unidad: 'sobre', envase: null },
        { nombre: 'Crema humectante', cantidad: 3, unidad: 'unidad', envase: null },
      ]),
    )
    expect(texto.split('\n')).toEqual([
      'Lista de insumos · 31/01/2026',
      '- Toallitas húmedas: 2 envases',
      '- Gasas: 1 sobre',
      '- Crema humectante: 3 unidades',
      'Piloto académico con datos de prueba',
    ])
  })

  it('sin línea en blanco, sin espacios al final y con el punto medio U+00B7', () => {
    const texto = textoDeLista(armarLista('2026-11-06', [{ nombre: '  Pañal\nadulto  ', cantidad: 1, unidad: 'unidad', envase: null }]))
    expect(texto).not.toMatch(/\n\n/)
    expect(texto).not.toMatch(/[ \t]$/m)
    expect(texto.split('\n')[0]).toBe('Lista de insumos · 06/11/2026')
    expect(texto.split('\n')[1]).toBe('- Pañal adulto: 1 unidad')
  })

  it('sin líneas: solo el título y el pie (8.5 y 4.10)', () => {
    expect(textoDeLista(armarLista('2026-11-06', []))).toBe('Lista de insumos · 06/11/2026\nPiloto académico con datos de prueba')
  })
})

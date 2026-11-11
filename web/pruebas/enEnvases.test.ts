// MATU-84 (especificación docs/diseno/matu-84-me-quedan-envases.md v1.1, secciones 3, 7 y 10): la
// cuenta de envases enteros más sueltos, los límites (envases hasta ⌊100.000 / u⌋, total hasta
// 100.000, envase de 1 a 10.000), el cambio de modo sin perder lo escrito, D2, D6 y los textos [L 30].
import { describe, expect, it } from 'vitest'
import { envaseUtil, envaseValido, juntar, maxEnvases, repartir, seCuentaEnEnvases, TOTAL_MAX, totalDe } from '../src/familia/enEnvases'
import { EN_ENVASES, totalEnTexto } from '../src/familia/textosInsumos'

describe('La cuenta', () => {
  it('envases × u + sueltos, con un vacío en 0 y los dos vacíos en null', () => {
    expect(totalDe('2', '5', 20)).toBe(45)
    expect(totalDe('2', '', 20)).toBe(40)
    expect(totalDe('', '5', 20)).toBe(5)
    expect(totalDe('0', '0', 20)).toBe(0)
    expect(totalDe('', '', 20)).toBeNull()
  })

  it('los sueltos pueden ser más que un envase: es «a ojo» y no se corrige (10)', () => {
    expect(totalDe('2', '25', 20)).toBe(65)
  })

  it('sin envase válido cuenta solo los sueltos (4.2)', () => {
    expect(totalDe('3', '5', null)).toBe(5)
    expect(totalDe('3', '', null)).toBe(0)
  })

  it('el total puede pasar de 100.000, y la pantalla lo detiene antes de enviar', () => {
    expect(totalDe('5000', '0', 20)).toBe(TOTAL_MAX)
    expect(totalDe('5000', '1', 20)! > TOTAL_MAX).toBe(true)
    expect(totalDe('11', '0', 10_000)).toBe(110_000)
  })
})

describe('Los límites (10)', () => {
  it('envases enteros de 0 a ⌊100.000 / u⌋', () => {
    expect(maxEnvases(20)).toBe(5000)
    expect(maxEnvases(30)).toBe(3333)
    expect(maxEnvases(10_000)).toBe(10)
    expect(maxEnvases(null)).toBe(100_000)
  })

  it('el envase de 1 a 10.000', () => {
    expect(envaseValido('1')).toBe(1)
    expect(envaseValido('10000')).toBe(10_000)
    expect(envaseValido('0')).toBeNull()
    expect(envaseValido('10001')).toBeNull()
    expect(envaseValido('')).toBeNull()
  })

  it('D6: un envase de 1 es como no tener envase', () => {
    expect(envaseUtil(1)).toBeNull()
    expect(envaseUtil(null)).toBeNull()
    expect(envaseUtil(undefined)).toBeNull()
    expect(envaseUtil(20)).toBe(20)
  })

  it('D2: solo unidades y sobres se cuentan en envases', () => {
    expect(seCuentaEnEnvases('unidad')).toBe(true)
    expect(seCuentaEnEnvases('sobre')).toBe(true)
    expect(seCuentaEnEnvases('ml')).toBe(false)
    expect(seCuentaEnEnvases('g')).toBe(false)
  })
})

describe('Cambiar de modo no pierde lo escrito (3)', () => {
  it('de sueltos a envases: 65 con envases de 20 son 3 y 5', () => {
    expect(repartir('65', 20)).toEqual({ envases: '3', sueltos: '5' })
    expect(repartir('40', 20)).toEqual({ envases: '2', sueltos: '0' })
    expect(repartir('5', 20)).toEqual({ envases: '0', sueltos: '5' })
  })

  it('sin envase, el número pasa entero a sueltos y envases enteros queda vacío', () => {
    expect(repartir('65', null)).toEqual({ envases: '', sueltos: '65' })
  })

  it('vacío deja los dos vacíos', () => {
    expect(repartir('', 20)).toEqual({ envases: '', sueltos: '' })
  })

  it('de envases a sueltos: el total, o vacío si los dos estaban vacíos', () => {
    expect(juntar('3', '5', 20)).toBe('65')
    expect(juntar('', '7', 20)).toBe('7')
    expect(juntar('', '', 20)).toBe('')
  })

  it('ida y vuelta da lo mismo', () => {
    const r = repartir('65', 20)
    expect(juntar(r.envases, r.sueltos, 20)).toBe('65')
  })
})

describe('Los textos [L 30]', () => {
  it('el total en vivo, sin nombrar el producto (D1)', () => {
    expect(totalEnTexto(45, 'unidad')).toBe('En total, quedan unas 45 unidades.')
    expect(totalEnTexto(12, 'sobre')).toBe('En total, quedan unos 12 sobres.')
    expect(totalEnTexto(1, 'unidad')).toBe('En total, queda 1 unidad.')
    expect(totalEnTexto(1, 'sobre')).toBe('En total, queda 1 sobre.')
    expect(totalEnTexto(0, 'unidad')).toBe('En total, no queda nada.')
    expect(totalEnTexto(0, 'sobre')).toBe('En total, no queda nada.')
    expect(totalEnTexto(1200, 'unidad')).toBe('En total, quedan unas 1.200 unidades.')
  })

  it('los demás', () => {
    expect(EN_ENVASES.sueltos('unidad')).toBe('Unidades sueltas')
    expect(EN_ENVASES.sueltos('sobre')).toBe('Sobres sueltos')
    expect(EN_ENVASES.tambienEnvase(20, 'unidad')).toBe('También anotamos que cada envase trae 20 unidades.')
    expect(EN_ENVASES.tambienEnvase(10, 'sobre')).toBe('También anotamos que cada envase trae 10 sobres.')
    expect(EN_ENVASES.errTotal('unidad')).toBe('Con eso quedarían más de 100.000 unidades. Revisa cuántos envases y sueltos anotaste.')
    expect(EN_ENVASES.errTotal('sobre')).toBe('Con eso quedarían más de 100.000 sobres. Revisa cuántos envases y sueltos anotaste.')
  })

  it('ninguno dice «stock», «inventario» ni «exacto» (criterio 13)', () => {
    const todos = [
      ...Object.values(EN_ENVASES).filter((v): v is string => typeof v === 'string'),
      EN_ENVASES.sueltos('unidad'),
      EN_ENVASES.sueltos('sobre'),
      EN_ENVASES.tambienEnvase(20, 'unidad'),
      EN_ENVASES.errTotal('unidad'),
      totalEnTexto(45, 'unidad'),
    ].join(' ')
    expect(todos).not.toMatch(/stock|inventario|exact|quiebre|repon|compr/i)
  })
})

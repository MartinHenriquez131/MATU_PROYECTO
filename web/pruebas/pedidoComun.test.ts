// MATU-61: las funciones puras del pedido (especificación 6.3, 7.5, 9.2 y O3) y la huella de las
// declaraciones de la autorización de pedidos (decisión 221). Solo datos sintéticos.
import { describe, expect, it } from 'vitest'
import type { ProductoCatalogo } from '../src/compartido/api/catalogo'
import type { LineaPedido, Pedido } from '../src/compartido/api/pedido'
import {
  cantidadDesdeLista,
  direccionEnTexto,
  enRango,
  enTuListaTexto,
  hayCambios,
  lineasParaGuardar,
  primeraOferta,
  productosDe,
  reglasConCambio,
  sufijoDelPedido,
  telefonoEnTexto,
} from '../src/familia/pedidoComun'
import { DECLARACION_PEDIDOS, huellaDe } from '../src/familia/textosPedido'

const oferta = (id: string, comercio: string, precio: number, disponible: boolean) => ({ oferta_id: id, comercio_id: comercio, nombre_fantasia: comercio, precio, disponible, ficticio: true })
const PANAL: ProductoCatalogo = {
  id: 'p-panal',
  nombre: 'Pañal adulto M x30',
  presentacion: 'Paquete de 30 unidades',
  unidad: 'unidad',
  unidades_por_envase: 30,
  retracto_pierde_al_abrir: true,
  comercios: [oferta('o-panal-a', 'c-a', 12990, false), oferta('o-panal-b', 'c-b', 13490, true)],
}
const CREMA: ProductoCatalogo = { ...PANAL, id: 'p-crema', nombre: 'Crema 100 g', unidad: 'g', unidades_por_envase: 100, comercios: [oferta('o-crema-a', 'c-a', 6990, true)] }
const CATALOGO = { precios_de_ejemplo: true, categorias: [{ id: 'k', nombre: 'Higiene', orden: 1, productos: [PANAL, CREMA] }] }

const linea = (producto: ProductoCatalogo, comercio: string, cantidad: number): LineaPedido => ({
  id: `l-${producto.id}`,
  producto: { id: producto.id, nombre: producto.nombre, presentacion: producto.presentacion, unidad: producto.unidad, unidades_por_envase: producto.unidades_por_envase },
  cantidad,
  comercio: { id: comercio, nombre_fantasia: comercio, ficticio: true },
  precio_unitario: 1000,
  subtotal: 1000 * cantidad,
  regla_faltante: 'otro_comercio',
  retracto_pierde_al_abrir: true,
  cambio: null,
})

describe('6.3: la cantidad de la lista en envases del catálogo', () => {
  it('6 envases de 20 unidades son 120 unidades: 4 paquetes de 30', () => {
    expect(cantidadDesdeLista({ cantidad: 6, unidad: 'unidad', envase: 20 }, PANAL)).toEqual({ cantidad: 4, exacta: true })
  })
  it('redondea hacia arriba: 31 unidades sueltas son 2 paquetes de 30', () => {
    expect(cantidadDesdeLista({ cantidad: 31, unidad: 'unidad', envase: null }, PANAL)).toEqual({ cantidad: 2, exacta: true })
  })
  it('nunca menos de 1 ni más de 99', () => {
    expect(cantidadDesdeLista({ cantidad: 1, unidad: 'unidad', envase: null }, PANAL).cantidad).toBe(1)
    expect(cantidadDesdeLista({ cantidad: 100_000, unidad: 'unidad', envase: null }, PANAL).cantidad).toBe(99)
  })
  it('con otra unidad (ml contra g) o agregado a mano en envases, pasa 1 y no es exacta', () => {
    expect(cantidadDesdeLista({ cantidad: 2, unidad: 'ml', envase: 250 }, CREMA)).toEqual({ cantidad: 1, exacta: false })
    expect(cantidadDesdeLista({ cantidad: 3, unidad: 'envase', envase: null }, PANAL)).toEqual({ cantidad: 1, exacta: false })
  })
  it('«En tu lista: …» repite el texto de MATU-60', () => {
    expect(enTuListaTexto({ cantidad: 6, unidad: 'unidad', envase: 20 })).toBe('6 envases de 20 unidades')
  })
})

describe('O3: el comercio de una línea de la lista', () => {
  it('es la primera oferta con «Hay» en el orden del catálogo, nunca la más barata', () => {
    expect(primeraOferta(PANAL)?.oferta_id).toBe('o-panal-b')
  })
  it('sin ninguna con «Hay», la primera (se resuelve al confirmar)', () => {
    expect(primeraOferta({ ...PANAL, comercios: [oferta('x', 'c-a', 1, false), oferta('y', 'c-b', 2, false)] })?.oferta_id).toBe('x')
  })
})

describe('Las líneas para PUT …/lineas', () => {
  const productos = productosDe(CATALOGO)
  const lineas = [linea(PANAL, 'c-b', 2), linea(CREMA, 'c-a', 1)]
  it('usa la oferta del catálogo de cada línea por producto y comercio, con la cantidad cambiada', () => {
    expect(lineasParaGuardar(lineas, productos, { cantidades: { 'p-panal': 5 } })).toEqual([
      { oferta_id: 'o-panal-b', cantidad: 5 },
      { oferta_id: 'o-crema-a', cantidad: 1 },
    ])
  })
  it('sin la línea que se saca', () => {
    expect(lineasParaGuardar(lineas, productos, { sacar: 'p-panal' })).toEqual([{ oferta_id: 'o-crema-a', cantidad: 1 }])
  })
  it('O4: un producto que ya estaba queda en una sola línea, en su comercio, con la cantidad nueva', () => {
    expect(lineasParaGuardar(lineas, productos, { nuevas: [{ producto_id: 'p-panal', oferta_id: 'o-panal-a', cantidad: 4 }] })).toEqual([
      { oferta_id: 'o-panal-b', cantidad: 4 },
      { oferta_id: 'o-crema-a', cantidad: 1 },
    ])
  })
  it('null si una línea ya no tiene su oferta en el catálogo', () => {
    expect(lineasParaGuardar([linea(PANAL, 'c-z', 1)], productos)).toBeNull()
  })
  it('las reglas de todo el pedido, con la de un producto cambiada', () => {
    expect(reglasConCambio(lineas, 'p-crema', 'quitar')).toEqual([
      { producto_id: 'p-panal', accion: 'otro_comercio' },
      { producto_id: 'p-crema', accion: 'quitar' },
    ])
  })
})

describe('Textos que arma la pantalla', () => {
  it('7.5: el sufijo en envases del catálogo, y «envases» sin datos del envase', () => {
    expect(sufijoDelPedido(2, PANAL)).toBe('envases de 30 unidades')
    expect(sufijoDelPedido(1, PANAL)).toBe('envase de 30 unidades')
    expect(sufijoDelPedido(2, {})).toBe('envases')
    expect(sufijoDelPedido(1, {})).toBe('envase')
  })
  it('la dirección, sin «depto» si no hay', () => {
    expect(direccionEnTexto({ calle: 'Los Aromos', numero: '123', depto: '4', comuna: 'La Reina' })).toBe('Los Aromos 123, depto 4, La Reina')
    expect(direccionEnTexto({ calle: 'Los Aromos', numero: 'S/N', depto: null, comuna: 'La Reina' })).toBe('Los Aromos S/N, La Reina')
  })
  it('el teléfono con el formato de DISENO.md 2, y el enmascarado tal cual', () => {
    expect(telefonoEnTexto('+56955550177')).toBe('+56 9 5555 0177')
    expect(telefonoEnTexto('9 5555 0177')).toBe('+56 9 5555 0177')
    expect(telefonoEnTexto('+56 9 •••• ••37')).toBe('+56 9 •••• ••37')
  })
  it('el rango de la cantidad es de 1 a 99', () => {
    expect([0, 1, 99, 100, null].map(enRango)).toEqual([false, true, true, false, false])
  })
  it('9.2: hay cambios con un producto que salió o una línea con `cambio`', () => {
    const base = { lineas: [linea(PANAL, 'c-b', 1)], salieron: [] } as unknown as Pedido
    expect(hayCambios(base)).toBe(false)
    expect(hayCambios({ ...base, lineas: [{ ...linea(PANAL, 'c-b', 1), cambio: { precio_antes: 900, comercio_antes: null } }] })).toBe(true)
  })
})

describe('Decisión 221: la huella de `declaracion_pedidos_<calidad>`', () => {
  // Las del backend (app/modules/care_circle/domain/declaraciones.py), calculadas sobre su texto exacto.
  it.each([
    ['titular', 'b5ec2914afc3e4f235e25c84f6ae78fbc17000b603e692463b33faf01914b6b9'],
    ['representante_legal', 'e9fe02da33c8c95333d34aed3e062796bdc8d2380e73b797ea4e02c56e6c16cf'],
    ['cuidador_de_hecho', '6d3ec2469b304e868a416b63c2c07e563147e312a6735ebb2f457d6d139f8988'],
  ] as const)('%s: el texto que se muestra tiene la huella que el backend acepta', async (calidad, huella) => {
    expect(await huellaDe(DECLARACION_PEDIDOS[calidad])).toBe(huella)
  })
})

// Doble de `GET /v1/catalogo` (MATU-59, decisiones 158 a 170) para desarrollo: lo mismo que deja
// infra/semillas/catalogo_demo.py, con los ids propios del doble. Solo `nombre_fantasia` del
// comercio y `disponible`, nunca la cantidad. Datos sintéticos: comercios y productos ficticios.
import { randomUUID } from 'node:crypto'

type Unidad = 'unidad' | 'sobre' | 'ml' | 'g'
interface Oferta {
  oferta_id: string
  comercio_id: string
  nombre_fantasia: string
  precio: number
  disponible: boolean
}

const ALMACEN = { id: randomUUID(), nombre: 'Almacén El Ejemplo' }
const BODEGA = { id: randomUUID(), nombre: 'Bodega La Muestra' }

const oferta = (c: typeof ALMACEN, precio: number, stock: number): Oferta => ({
  oferta_id: randomUUID(),
  comercio_id: c.id,
  nombre_fantasia: c.nombre,
  precio,
  disponible: stock > 0,
})

const producto = (nombre: string, presentacion: string, unidad: Unidad, unidades: number, retracto: boolean, uno: [number, number], dos: [number, number]) => ({
  id: randomUUID(),
  nombre,
  presentacion,
  unidad,
  unidades_por_envase: unidades,
  retracto_pierde_al_abrir: retracto,
  // Por nombre_fantasia, nunca por precio (decisión 162).
  comercios: [oferta(ALMACEN, ...uno), oferta(BODEGA, ...dos)],
})

const CATALOGO = {
  precios_de_ejemplo: true,
  categorias: [
    {
      id: randomUUID(),
      nombre: 'Higiene y cuidado personal',
      orden: 1,
      productos: [
        producto('Bolsa colectora x10', 'Caja de 10 unidades', 'unidad', 10, false, [15990, 0], [16490, 0]),
        producto('Pañal adulto M x30', 'Paquete de 30 unidades', 'unidad', 30, true, [12990, 24], [13490, 0]),
        producto('Protectores diarios x20', 'Caja de 20 unidades', 'unidad', 20, true, [3290, 12], [3490, 6]),
        producto('Toallitas húmedas x80', 'Paquete de 80 unidades', 'unidad', 80, true, [4590, 0], [4290, 30]),
      ],
    },
    {
      id: randomUUID(),
      nombre: 'Cuidado de la piel',
      orden: 2,
      productos: [producto('Crema protectora de la piel 100 g', 'Pote de 100 g', 'g', 100, true, [6990, 0], [7290, 10])],
    },
    {
      id: randomUUID(),
      nombre: 'Alimentación',
      orden: 3,
      productos: [producto('Suplemento nutricional en polvo 400 g', 'Tarro de 400 g', 'g', 400, false, [18990, 8], [17990, 4])],
    },
  ],
}

/** El catálogo según el modo de la cuenta: `catalogo-vacio` sin productos; cualquier otro, la semilla. */
export const catalogoDoble = (modo?: string) => (modo === 'catalogo-vacio' ? { precios_de_ejemplo: true, categorias: [] } : CATALOGO)

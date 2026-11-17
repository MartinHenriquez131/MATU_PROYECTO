// MATU-81, especificación 10 y 11: los cobros por revisar (sin la tarjeta, cada fila abre el pedido
// con «Volver a los cobros») y el catálogo de prueba (el precio con IVA, la confirmación con el precio
// anterior, el If-Match, el 412 que conserva lo escrito y el 409 `comercio-real`). Solo datos sintéticos.
import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { leerPrecio } from '../src/operacion/Catalogo'
import { AppOperacion } from '../src/operacion/AppOperacion'
import { apiOperacion, conRegionesVivas, dialogoDeJsdom, ID_OPERACION as ID, type Sobre } from './operacionFalso'

// Con la suite completa en paralelo, montar la consola puede tardar más que el segundo por omisión.
configure({ asyncUtilTimeout: 5000 })

beforeEach(() => dialogoDeJsdom())

const u = () => userEvent.setup({ delay: null })

async function abrir(ruta: string, sobre?: Sobre) {
  const api = apiOperacion({ sobre })
  window.history.replaceState(null, '', ruta)
  const regiones = conRegionesVivas(<AppOperacion />)
  return { api, usuario: u(), ...regiones }
}

describe('Cobros por revisar', () => {
  it('las ventas sin respuesta y las devoluciones sin terminar, con su número y sin la tarjeta', async () => {
    const { api } = await abrir('/operacion/cobros')
    expect(await screen.findByRole('heading', { level: 1, name: 'Cobros' })).toBeVisible()
    expect(document.title).toBe('Cobros · Operación · MATU')
    expect(await screen.findByRole('heading', { level: 2, name: 'Ventas sin respuesta (1)' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 2, name: 'Devoluciones sin terminar (1)' })).toBeVisible()
    const venta = screen.getByRole('button', { name: /^Pedido 4823,/ })
    expect(within(venta).getByText('MATU-4823-K2')).toBeVisible()
    expect(within(venta).getByText(/^Iniciada a las 13:42, hace 38\sminutos$/)).toHaveClass('text-atenta')
    const devolucion = screen.getByRole('button', { name: /^Pedido 4827,/ })
    expect(within(devolucion).getByText('Cancelación')).toBeVisible()
    expect(within(devolucion).getByText('Sin terminar')).toBeVisible()
    expect(document.body.textContent).not.toMatch(/terminada en|cuotas|código de autorización:|crédito|débito/i)
    expect(api.lineas()).toContain('GET /v1/operacion/cobros/pendientes')
  })

  it('una fila abre el pedido con la pestaña «Cobros» activa, «Volver a los cobros» y el pago que necesita revisión', async () => {
    const { usuario, api } = await abrir('/operacion/cobros')
    await usuario.click(await screen.findByRole('button', { name: /^Pedido 4827,/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Pedido 4827' })).toBeVisible()
    expect(window.location.pathname).toBe('/operacion/pedido')
    expect(screen.getByRole('link', { name: 'Cobros' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Pedidos' })).not.toHaveAttribute('aria-current')
    expect(await screen.findByText('Este pago necesita revisión.')).toBeVisible()
    expect(api.lineas()).toContain(`GET /v1/operacion/pedidos/${ID.cancelado}/cobro`)
    // «Anotar una incidencia» abre el formulario con el tipo ya elegido.
    await usuario.click(within(screen.getByRole('region', { name: 'Pago' })).getByRole('button', { name: 'Anotar una incidencia' }))
    expect(await screen.findByRole('radio', { name: 'Devolución pendiente' })).toBeChecked()
    await usuario.click(screen.getAllByRole('button', { name: 'Volver a los cobros' })[0])
    expect(await screen.findByRole('heading', { level: 1, name: 'Cobros' })).toBeVisible()
  })

  it('sin pendientes: los dos grupos con 0 y su frase', async () => {
    apiOperacion({ modo: 'operacion-vacia' })
    window.history.replaceState(null, '', '/operacion/cobros')
    conRegionesVivas(<AppOperacion />)
    expect(await screen.findByRole('heading', { level: 2, name: 'Ventas sin respuesta (0)' })).toBeVisible()
    expect(screen.getByText('No hay ventas sin respuesta.')).toBeVisible()
    expect(screen.getByText('No hay devoluciones sin terminar.')).toBeVisible()
  })
})

describe('Catálogo de prueba', () => {
  async function abrirCatalogo(sobre?: Sobre) {
    const r = await abrir('/operacion/catalogo', sobre)
    await screen.findByRole('heading', { level: 1, name: 'Catálogo' })
    await screen.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })
    return r
  }
  const fila = (producto: string) => screen.getByRole('heading', { level: 3, name: producto }).closest('li')!

  it('el aviso del precio nuevo, los precios con IVA incluido y el comercio real en solo lectura', async () => {
    await abrirCatalogo()
    expect(screen.getByText('El precio nuevo vale solo para los pedidos que se confirmen desde ahora. Los confirmados y los pagados mantienen su precio.')).toBeVisible()
    expect(screen.getByText('Solo puedes cambiar los comercios de prueba.')).toBeVisible()
    expect(within(fila('Pañal adulto M x30')).getByText('$12.990')).toBeVisible()
    expect(within(fila('Pañal adulto M x30')).getByText('· IVA incluido')).toBeVisible()
    expect(screen.getByRole('heading', { level: 2, name: 'Almacén El Ejemplo (comercio ficticio)' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 2, name: 'Distribuidora del Centro' })).toBeVisible()
    expect(screen.getByText('Este comercio no es de prueba: aquí no se cambia.')).toBeVisible()
    expect(within(fila('Pañal adulto L x20')).queryByRole('button', { name: 'Cambiar' })).toBeNull()
    expect(document.body.textContent).not.toMatch(/stock|\+ IVA/)
  })

  it('cambiar el precio pide confirmar con el anterior; guarda con If-Match y se anuncia', async () => {
    const { api, usuario, amable } = await abrirCatalogo()
    await usuario.click(within(fila('Pañal adulto M x30')).getByRole('button', { name: 'Cambiar' }))
    // Un editor a la vez: los demás «Cambiar» se ocultan.
    expect(screen.queryAllByRole('button', { name: 'Cambiar' })).toHaveLength(0)
    const precio = screen.getByLabelText('Precio, con IVA incluido')
    expect(precio).toHaveAttribute('inputmode', 'numeric')
    await usuario.clear(precio)
    await usuario.type(precio, '13.990')
    expect(screen.getByText('Se verá como $13.990.')).toBeVisible()
    await usuario.click(screen.getByRole('button', { name: 'Guardar' }))
    const dialogo = await screen.findByRole('dialog', { name: '¿Cambiar el precio de Pañal adulto M x30 a $13.990?' })
    expect(within(dialogo).getByText('Antes era $12.990.')).toBeVisible()
    expect(within(dialogo).getByText('Vale solo para los pedidos que se confirmen desde ahora.')).toHaveClass('font-bold')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Cambiar el precio' }))
    await waitFor(() => expect(amable).toHaveTextContent('Guardado: Pañal adulto M x30 a $13.990, tiene 14.'))
    const p = api.peticiones.find((x) => x.linea === `PATCH /v1/operacion/ofertas/${ID.ofertaPanal}`)!
    expect(p.ifMatch).toBe('"o1"')
    expect(p.cuerpo).toEqual({ precio: 13990, stock: 14, disponible: true })
    expect(within(fila('Pañal adulto M x30')).getByText('$13.990')).toBeVisible()
    await waitFor(() => expect(within(fila('Pañal adulto M x30')).getByRole('button', { name: 'Cambiar' })).toHaveFocus())
  })

  it('sin cambiar el precio guarda sin diálogo; un precio con coma o decimales no se envía', async () => {
    const { api, usuario } = await abrirCatalogo()
    await usuario.click(within(fila('Toallitas húmedas x80')).getByRole('button', { name: 'Cambiar' }))
    const precio = screen.getByLabelText('Precio, con IVA incluido')
    await usuario.clear(precio)
    await usuario.type(precio, '3290,5')
    await usuario.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(screen.getByText('Escribe el precio en pesos, mayor que 0, sin decimales. Por ejemplo, 12990.')).toBeVisible()
    expect(api.lineas().some((l) => l.startsWith('PATCH'))).toBe(false)
    await usuario.clear(precio)
    await usuario.type(precio, '3290')
    await usuario.clear(screen.getByLabelText('¿Cuántos tiene?'))
    await usuario.type(screen.getByLabelText('¿Cuántos tiene?'), '20')
    await usuario.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(api.lineas().some((l) => l.startsWith('PATCH'))).toBe(true))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('412: «Otra persona cambió este producto…», el editor sigue abierto con lo escrito', async () => {
    const { usuario, amable } = await abrirCatalogo((l) => (l.startsWith('PATCH') ? { status: 412, cuerpo: { type: '/errores/version-desactualizada', status: 412 } } : undefined))
    await usuario.click(within(fila('Toallitas húmedas x80')).getByRole('button', { name: 'Cambiar' }))
    await usuario.clear(screen.getByLabelText('¿Cuántos tiene?'))
    await usuario.type(screen.getByLabelText('¿Cuántos tiene?'), '7')
    await usuario.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(amable).toHaveTextContent('Otra persona cambió este producto mientras lo editabas. Te mostramos cómo quedó.'))
    expect(screen.getByLabelText('¿Cuántos tiene?')).toHaveValue('7')
  })

  it('409 `comercio-real`: la nota, el editor se cierra y la fila queda sin «Cambiar»', async () => {
    const { usuario, urgente } = await abrirCatalogo((l) => (l.startsWith('PATCH') ? { status: 409, cuerpo: { type: '/errores/comercio-real', status: 409 } } : undefined))
    await usuario.click(within(fila('Toallitas húmedas x80')).getByRole('button', { name: 'Cambiar' }))
    await usuario.click(screen.getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(urgente).toHaveTextContent('Este producto no se puede cambiar aquí: su comercio no es de prueba.'))
    expect(screen.queryByLabelText('¿Cuántos tiene?')).toBeNull()
    expect(within(fila('Toallitas húmedas x80')).queryByRole('button', { name: 'Cambiar' })).toBeNull()
  })

  it('el precio acepta «69000» y «69.000», y nada con coma, decimales, letras ni 0', () => {
    expect(leerPrecio('69000')).toBe(69000)
    expect(leerPrecio('69.000')).toBe(69000)
    for (const malo of ['69,5', '69000.5', '0', '', 'abc', '-5']) expect(leerPrecio(malo)).toBeNull()
  })
})

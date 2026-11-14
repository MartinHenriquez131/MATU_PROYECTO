// MATU-63, especificación 8: «Tus productos». El precio se lee y no se edita; cuántos tiene se cambia
// con un solo editor abierto, con If-Match y el 412; «Lo ofreces en MATU» se guarda al tocarlo.
// Solo datos sintéticos.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AppComercio } from '../src/comercio/AppComercio'
import { apiComercio, conRegionesVivas } from './comercioFalso'
import type { RespuestaFalsa } from './apiFalsa'

const u = () => userEvent.setup({ delay: null })

async function abrir(sobre?: (l: string, c: unknown) => RespuestaFalsa | undefined, extra: Parameters<typeof apiComercio>[0] = {}) {
  const api = apiComercio({ sobre, ...extra })
  window.history.replaceState(null, '', '/comercio/productos')
  const regiones = conRegionesVivas(<AppComercio />)
  await screen.findByRole('heading', { level: 2, name: 'Pañal adulto M x30' })
  return { api, usuario: u(), ...regiones }
}

const producto = (nombre: string) => screen.getByRole('heading', { level: 2, name: nombre }).closest('article')!

describe('Tus productos', () => {
  it('por nombre, con el precio de ejemplo solo para leer, las tres cifras y sin botón principal', async () => {
    await abrir()
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
      'Crema protectora 200 g',
      'Pañal adulto M x30',
      'Suplemento vainilla x12',
      'Toallitas húmedas x80',
    ])
    const panal = producto('Pañal adulto M x30')
    expect(within(panal).getByText('$12.990')).toBeVisible()
    expect(within(panal).getByText(/Precio de ejemplo/)).toBeVisible()
    expect(within(panal).queryAllByRole('textbox')).toHaveLength(0)
    const cifras = within(panal).getAllByRole('definition').map((d) => d.textContent)
    expect(cifras).toEqual(['14', '3', '11'])
    expect(document.querySelectorAll('button.bg-turquesa')).toHaveLength(0)
    expect(screen.getAllByText('Comercio de prueba.')).toHaveLength(1)
    expect(screen.getByText('Estos productos y precios son de ejemplo.')).toBeVisible()
    expect(document.title).toBe('Tus productos · Almacén El Ejemplo · MATU')
  })

  it('sin disponibles: «Sin disponibles»; con menos de los apartados, la nota; sin ofrecer, «No se ofrece»', async () => {
    await abrir()
    expect(within(producto('Toallitas húmedas x80')).getByText('Sin disponibles')).toBeVisible()
    expect(within(producto('Suplemento vainilla x12')).getByText(/Tienes menos de los que ya están apartados/)).toBeVisible()
    const crema = producto('Crema protectora 200 g')
    expect(within(crema).getByRole('checkbox', { name: 'Lo ofreces en MATU' })).not.toBeChecked()
    expect(within(crema).getByText('No se ofrece')).toBeVisible()
    expect(within(crema).getByText('Lo apartado sigue apartado.')).toBeVisible()
  })

  it('«Cambiar cuántos tienes» abre un solo editor; «Guardar» envía con If-Match, anuncia y devuelve el foco', async () => {
    const { api, usuario, amable } = await abrir()
    const panal = producto('Pañal adulto M x30')
    await usuario.click(within(panal).getByRole('button', { name: 'Cambiar cuántos tienes' }))
    const campo = within(panal).getByLabelText('¿Cuántos tienes ahora?')
    await waitFor(() => expect(campo).toHaveFocus())
    expect(campo).toHaveValue('14')
    expect(campo).toHaveAttribute('inputmode', 'numeric')
    // Las demás filas ocultan su botón: un solo «Guardar» principal.
    expect(screen.queryAllByRole('button', { name: 'Cambiar cuántos tienes' })).toHaveLength(0)
    expect(document.querySelectorAll('button.bg-turquesa')).toHaveLength(1)
    await usuario.clear(campo)
    await usuario.type(campo, '20')
    await usuario.click(within(panal).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(amable).toHaveTextContent('Guardado: tienes 20 de Pañal adulto M x30.'))
    const patch = api.peticiones.find((p) => p.linea.startsWith('PATCH'))!
    expect(patch.cuerpo).toEqual({ stock: 20 })
    expect(patch.ifMatch).toBe('"v1"')
    await waitFor(() => expect(within(panal).getByRole('button', { name: 'Cambiar cuántos tienes' })).toHaveFocus())
    expect(within(panal).getAllByRole('definition')[0]).toHaveTextContent('20')
  })

  it.each([
    ['', 'Escribe un número, desde 0.'],
    ['-2', 'Escribe un número, desde 0.'],
    ['diez', 'Escribe un número, desde 0.'],
    ['10000', 'Escribe un número hasta 9.999.'],
  ])('«%s» no se envía: «%s»', async (valor, error) => {
    const { api, usuario } = await abrir()
    const panal = producto('Pañal adulto M x30')
    await usuario.click(within(panal).getByRole('button', { name: 'Cambiar cuántos tienes' }))
    const campo = within(panal).getByLabelText('¿Cuántos tienes ahora?')
    await usuario.clear(campo)
    if (valor) await usuario.type(campo, valor)
    await usuario.click(within(panal).getByRole('button', { name: 'Guardar' }))
    expect(within(panal).getByText(error)).toBeVisible()
    expect(campo).toHaveAttribute('aria-invalid', 'true')
    expect(api.lineas().some((l) => l.startsWith('PATCH'))).toBe(false)
  })

  it('«Cancelar» cierra sin guardar y devuelve el foco a «Cambiar cuántos tienes»', async () => {
    const { api, usuario } = await abrir()
    const panal = producto('Pañal adulto M x30')
    await usuario.click(within(panal).getByRole('button', { name: 'Cambiar cuántos tienes' }))
    await usuario.click(within(panal).getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(within(panal).getByRole('button', { name: 'Cambiar cuántos tienes' })).toHaveFocus())
    expect(api.lineas().some((l) => l.startsWith('PATCH'))).toBe(false)
  })

  it('412: la nota de otra persona, las cifras al día y el editor abierto con lo escrito', async () => {
    let una = true
    const { usuario, amable, api } = await abrir((l) => {
      if (una && l.startsWith('PATCH')) {
        una = false
        return { status: 412, cuerpo: { type: '/errores/version-desactualizada', status: 412 } }
      }
      return undefined
    })
    api.estado.productos.find((p) => p.nombre.startsWith('Pañal'))!.stock = 30
    const panal = producto('Pañal adulto M x30')
    await usuario.click(within(panal).getByRole('button', { name: 'Cambiar cuántos tienes' }))
    const campo = within(panal).getByLabelText('¿Cuántos tienes ahora?')
    await usuario.clear(campo)
    await usuario.type(campo, '18')
    await usuario.click(within(panal).getByRole('button', { name: 'Guardar' }))
    await waitFor(() => expect(amable).toHaveTextContent('Otra persona cambió este producto mientras lo editabas. Te mostramos cómo quedó.'))
    expect(within(producto('Pañal adulto M x30')).getAllByRole('definition')[0]).toHaveTextContent('30')
    expect(within(producto('Pañal adulto M x30')).getByLabelText('¿Cuántos tienes ahora?')).toHaveValue('18')
  })

  it('red al guardar: el mensaje con «Lo que escribiste sigue aquí.»', async () => {
    const { usuario } = await abrir((l) => (l.startsWith('PATCH') ? { status: 500, cuerpo: { type: '/errores/interno', status: 500 } } : undefined))
    const panal = producto('Pañal adulto M x30')
    await usuario.click(within(panal).getByRole('button', { name: 'Cambiar cuántos tienes' }))
    await usuario.click(within(panal).getByRole('button', { name: 'Guardar' }))
    expect(await within(panal).findByText(/Lo que escribiste sigue aquí\./)).toBeVisible()
  })

  it('«Lo ofreces en MATU» se guarda al tocarlo, con { disponible }', async () => {
    const { api, usuario } = await abrir()
    const panal = producto('Pañal adulto M x30')
    await usuario.click(within(panal).getByRole('checkbox', { name: 'Lo ofreces en MATU' }))
    await waitFor(() => expect(within(producto('Pañal adulto M x30')).getByText('No se ofrece')).toBeVisible())
    expect(api.peticiones.find((p) => p.linea.startsWith('PATCH'))!.cuerpo).toEqual({ disponible: false })
  })

  it('vacío: «Todavía no tienes productos en MATU.» con el contacto', async () => {
    apiComercio({ productos: [] })
    window.history.replaceState(null, '', '/comercio/productos')
    conRegionesVivas(<AppComercio />)
    expect(await screen.findByText('Todavía no tienes productos en MATU.')).toBeVisible()
    expect(screen.getByText('Avisa a MATU para agregarlos: contacto@example.com.')).toBeVisible()
  })

  it('error al traer: la nota y «Volver a intentar»', async () => {
    apiComercio({ sobre: (l) => (l === 'GET /v1/comercio/productos' ? { status: 500, cuerpo: { type: '/errores/interno', status: 500 } } : undefined) })
    window.history.replaceState(null, '', '/comercio/productos')
    const { urgente } = conRegionesVivas(<AppComercio />)
    await waitFor(() => expect(urgente).toHaveTextContent('No pudimos traer tus productos. Revisa tu conexión y vuelve a intentarlo.'))
    expect(screen.getByRole('button', { name: 'Volver a intentar' })).toBeVisible()
  })
})

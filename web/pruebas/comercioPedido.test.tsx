// MATU-63, especificación 6: un pedido en cada estado, marcar lo que se tiene y lo que no (con la nota
// de no reemplazar y el `Stepper`), «Listo para retirar» con líneas sin marcar, todo faltante (O3) y
// los errores 404, 409, 412 y de red. Solo datos sintéticos.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AppComercio } from '../src/comercio/AppComercio'
import { apiComercio, conRegionesVivas, ID } from './comercioFalso'
import type { RespuestaFalsa } from './apiFalsa'

const u = () => userEvent.setup({ delay: null })

/** Abre la consola y elige la parte de `referencia`. */
async function abrirParte(referencia: string, sobre?: (l: string, c: unknown) => RespuestaFalsa | undefined) {
  const api = apiComercio({ sobre })
  window.history.replaceState(null, '', '/comercio')
  const regiones = conRegionesVivas(<AppComercio />)
  await screen.findByRole('heading', { level: 2, name: /Por preparar/ })
  const usuario = u()
  await usuario.click(screen.getByRole('button', { name: new RegExp(`Pedido ${referencia}`) }))
  await screen.findByRole('heading', { level: 1, name: `Pedido ${referencia}` })
  return { api, usuario, ...regiones }
}

const linea = (texto: RegExp) => screen.getByRole('group', { name: texto })
const principales = () => document.querySelectorAll('button.bg-turquesa')

describe('Por preparar', () => {
  it('solo lectura, la etiqueta «Por preparar» y «Empezar a preparar», que pasa a preparando con If-Match', async () => {
    const { api, usuario } = await abrirParte('R8T2WQ')
    expect(screen.getByText('Por preparar', { selector: 'span' })).toBeVisible()
    expect(screen.getByText('Toca «Empezar a preparar» cuando vayas a buscar los productos.')).toBeVisible()
    expect(screen.queryByRole('radio')).toBeNull()
    expect(principales()).toHaveLength(1)
    await usuario.click(screen.getByRole('button', { name: 'Empezar a preparar' }))
    expect(await screen.findByRole('radio', { name: 'Lo tengo' })).toBeInTheDocument()
    const preparar = api.peticiones.find((p) => p.linea === `POST /v1/comercio/partes/${ID.porPreparar}/preparar`)
    expect(preparar?.ifMatch).toMatch(/^"v\d+"$/)
    await waitFor(() => expect(screen.getByRole('heading', { level: 2, name: 'Productos' })).toHaveFocus())
  })

  it('la atrasada dice «Era para las 14:00.» con el ícono de aviso', async () => {
    await abrirParte('K4M7XP')
    const detalle = screen.getByRole('heading', { level: 1, name: 'Pedido K4M7XP' }).closest('section')!
    expect(within(detalle).getByText('Era para las 14:00.')).toBeVisible()
  })

  it('409 al empezar (otra persona ya empezó): se vuelve a pedir y se dice que cambió', async () => {
    let una = true
    const { usuario, amable } = await abrirParte('R8T2WQ', (l) => {
      if (una && l.endsWith('/preparar')) {
        una = false
        return { status: 409, cuerpo: { type: '/errores/estado-parte', status: 409 } }
      }
      return undefined
    })
    await usuario.click(screen.getByRole('button', { name: 'Empezar a preparar' }))
    await waitFor(() => expect(amable).toHaveTextContent('Este pedido cambió mientras lo veías. Te mostramos cómo quedó.'))
  })

  it('red al empezar: el mensaje sobre el botón, que sigue', async () => {
    const { usuario } = await abrirParte('R8T2WQ', (l) => (l.endsWith('/preparar') ? { status: 500, cuerpo: { type: '/errores/interno', status: 500 } } : undefined))
    await usuario.click(screen.getByRole('button', { name: 'Empezar a preparar' }))
    expect(await screen.findByText('No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Empezar a preparar' })).toBeVisible()
  })

  it('404: «Este pedido ya no está en tu lista.» y «Volver a los pedidos»', async () => {
    const { usuario } = await abrirParte('R8T2WQ', (l) => (l.endsWith('/preparar') ? { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404 } } : undefined))
    await usuario.click(screen.getByRole('button', { name: 'Empezar a preparar' }))
    expect(await screen.findByText('Este pedido ya no está en tu lista.')).toBeVisible()
    expect(screen.getAllByRole('button', { name: 'Volver a los pedidos' }).length).toBeGreaterThan(0)
  })
})

describe('Preparando', () => {
  it('«No lo tengo» muestra la nota de no reemplazar en la línea y en su descripción; «Lo tengo» la quita', async () => {
    const { api, usuario } = await abrirParte('H6N3VD')
    const grupo = linea(/Suplemento vainilla x12/)
    await usuario.click(within(grupo).getByRole('radio', { name: 'No lo tengo' }))
    const nota = within(grupo).getByText('No lo cambies por otra marca ni por otro producto. MATU se encarga del resto.')
    expect(nota).toBeVisible()
    expect(grupo).toHaveAccessibleDescription(/No lo cambies por otra marca/)
    await waitFor(() => expect(api.peticiones.some((p) => p.linea.includes('/lineas/') && (p.cuerpo as { estado: string }).estado === 'faltante')).toBe(true))
    const marca = api.peticiones.find((p) => p.linea.includes('/lineas/'))!
    expect(marca.cuerpo).toEqual({ estado: 'faltante', unidades_faltantes: 3 })
    await usuario.click(within(grupo).getByRole('radio', { name: 'Lo tengo' }))
    expect(within(grupo).queryByText(/No lo cambies/)).toBeNull()
  })

  it('«¿Cuántos te faltan?» solo con cantidad mayor que 1, entre 1 y la cantidad', async () => {
    const { usuario } = await abrirParte('H6N3VD')
    const uno = linea(/1\s×\sPañal adulto M x30/)
    await usuario.click(within(uno).getByRole('radio', { name: 'No lo tengo' }))
    expect(within(uno).queryByText('¿Cuántos te faltan?')).toBeNull()
    const tres = linea(/Suplemento vainilla x12/)
    await usuario.click(within(tres).getByRole('radio', { name: 'No lo tengo' }))
    expect(within(tres).getByText('¿Cuántos te faltan?')).toBeVisible()
    expect(within(tres).getByText('El pedido lleva 3.')).toBeVisible()
    expect(within(tres).getByRole('button', { name: 'Más: ¿Cuántos te faltan?' })).toBeDisabled()
    const menos = within(tres).getByRole('button', { name: 'Menos: ¿Cuántos te faltan?' })
    await usuario.click(menos)
    await usuario.click(menos)
    expect(menos).toBeDisabled()
  })

  it('«Listo para retirar» con una línea sin marcar no envía: el mensaje, el anillo y el foco en su primera opción', async () => {
    const { api, usuario } = await abrirParte('H6N3VD')
    await usuario.click(within(linea(/Pañal adulto M x30/)).getByRole('radio', { name: 'Lo tengo' }))
    const boton = screen.getByRole('button', { name: 'Listo para retirar' })
    expect(boton).toBeEnabled()
    expect(principales()).toHaveLength(1)
    await usuario.click(boton)
    expect(screen.getByText('Marca cada producto: si lo tienes o no.')).toBeVisible()
    const pendiente = linea(/Suplemento vainilla x12/)
    expect(pendiente).toHaveClass('ring-pronto')
    await waitFor(() => expect(within(pendiente).getByRole('radio', { name: 'Lo tengo' })).toHaveFocus())
    expect(api.lineas().some((l) => l.endsWith('/listo'))).toBe(false)
  })

  it('con todo marcado: «Pedido listo para retirar.» recibe el foco y aparece el código', async () => {
    const { usuario, amable } = await abrirParte('H6N3VD')
    await usuario.click(within(linea(/Pañal adulto M x30/)).getByRole('radio', { name: 'Lo tengo' }))
    await usuario.click(within(linea(/Suplemento vainilla x12/)).getByRole('radio', { name: 'Lo tengo' }))
    await usuario.click(screen.getByRole('button', { name: 'Listo para retirar' }))
    await waitFor(() => expect(amable).toHaveTextContent('Pedido listo para retirar. MATU le avisa a quien viene a buscarlo.'))
    await waitFor(() => expect(screen.getByText('Pedido listo para retirar.').closest('[tabindex="-1"]')).toHaveFocus())
    expect(screen.getByLabelText('Código de retiro (6 números)')).toBeVisible()
    expect(screen.getByText('Listo para retirar', { selector: 'span' })).toBeVisible()
    expect(principales()).toHaveLength(1)
  })

  it('O3: con todo en «No lo tengo», «Avisar que no tengo ninguno» y el pedido cancelado', async () => {
    const { usuario } = await abrirParte('H6N3VD')
    await usuario.click(within(linea(/Pañal adulto M x30/)).getByRole('radio', { name: 'No lo tengo' }))
    await usuario.click(within(linea(/Suplemento vainilla x12/)).getByRole('radio', { name: 'No lo tengo' }))
    await usuario.click(screen.getByRole('button', { name: 'Avisar que no tengo ninguno' }))
    expect(await screen.findByText('Este pedido se canceló. No lo prepares.')).toBeVisible()
    expect(screen.getByText('Avisaste que no tienes ninguno de estos productos. MATU se encarga del resto.')).toBeVisible()
    expect(principales()).toHaveLength(0)
  })

  it('si no se puede guardar una marca, vuelve a la anterior y lo dice bajo la línea', async () => {
    const { usuario } = await abrirParte('H6N3VD', (l) => (l.includes('/lineas/') ? { status: 500, cuerpo: { type: '/errores/interno', status: 500 } } : undefined))
    const grupo = linea(/Suplemento vainilla x12/)
    const tengo = within(grupo).getByRole('radio', { name: 'Lo tengo' })
    await usuario.click(tengo)
    expect(await within(grupo).findByText('No pudimos guardar lo que marcaste. Vuelve a intentarlo.')).toBeVisible()
    expect(tengo).not.toBeChecked()
  })

  it('412 al marcar: se vuelve a pedir la parte y se dice que cambió', async () => {
    const { usuario, amable, api } = await abrirParte('H6N3VD', (l) => (l.includes('/lineas/') ? { status: 412, cuerpo: { type: '/errores/version-desactualizada', status: 412 } } : undefined))
    await usuario.click(within(linea(/Suplemento vainilla x12/)).getByRole('radio', { name: 'Lo tengo' }))
    await waitFor(() => expect(amable).toHaveTextContent('Este pedido cambió mientras lo veías. Te mostramos cómo quedó.'))
    expect(api.lineas().filter((l) => l === `GET /v1/comercio/partes/${ID.preparando}`).length).toBeGreaterThanOrEqual(2)
  })
})

describe('Lista, retirado y cancelado', () => {
  it('lista: las líneas con lo marcado y «Faltan 1 de 3»', async () => {
    await abrirParte('P5Q8ZA')
    expect(screen.getByText('Faltan 1 de 3')).toBeVisible()
    expect(screen.getAllByText('Lo tengo').length).toBeGreaterThan(0)
    expect(screen.getAllByText('No lo tengo').length).toBeGreaterThan(0)
    expect(screen.queryByRole('radio')).toBeNull()
  })

  it('retirado: «Pedido retirado.» con la hora y sin acciones', async () => {
    await abrirParte('T8F2HJ')
    expect(screen.getByText('Pedido retirado.')).toBeVisible()
    expect(screen.getByText('Se retiró a las 13:40.')).toBeVisible()
    expect(principales()).toHaveLength(0)
  })

  it('cancelado: la nota y las líneas sin marcas', async () => {
    await abrirParte('Z5V7NQ')
    expect(screen.getByText('Este pedido se canceló. No lo prepares.')).toBeVisible()
    expect(screen.getByText('Si ya sacaste productos, vuelve a dejarlos en su lugar.')).toBeVisible()
    expect(screen.queryByText('Lo tengo')).toBeNull()
    expect(principales()).toHaveLength(0)
  })

  it('5.5: si la parte a la vista se cancela, se anuncia con la referencia por la región urgente', async () => {
    const { api, usuario, urgente } = await abrirParte('R8T2WQ')
    api.estado.partes.find((p) => p.id === ID.porPreparar)!.estado = 'cancelada'
    await usuario.click(screen.getByRole('button', { name: 'Actualizar' }))
    await waitFor(() => expect(urgente).toHaveTextContent('El pedido R8T2WQ se canceló. No lo prepares.'))
    expect(await screen.findByText('Si ya sacaste productos, vuelve a dejarlos en su lugar.')).toBeVisible()
  })
})

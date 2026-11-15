// MATU-63, especificación 3 y 5: la barra, los grupos de la cola, la parte elegida en memoria y no en
// la URL, la llegada de un pedido nuevo, los estados de la pantalla y los textos que nunca aparecen.
// Solo datos sintéticos.
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AppComercio } from '../src/comercio/AppComercio'
import { apiComercio, conRegionesVivas, ID, partesDeEjemplo, vigilarAlmacenamiento } from './comercioFalso'

const u = () => userEvent.setup({ delay: null })

function abrir(ruta = '/comercio') {
  window.history.replaceState(null, '', ruta)
  return conRegionesVivas(<AppComercio />)
}

const h2s = () => screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)

describe('Pedidos de hoy', () => {
  it('la barra: el nombre, «(comercio ficticio)» una vez, «Pedidos de MATU» y «Salir» sin turquesa', async () => {
    apiComercio()
    abrir()
    await screen.findByRole('heading', { level: 1, name: 'Pedidos de hoy' })
    const barra = screen.getByRole('banner')
    expect(barra).toHaveClass('bg-tinta', 'text-papel', '[&_:focus-visible]:outline-papel')
    expect(within(barra).getByText('Almacén El Ejemplo')).toBeVisible()
    expect(screen.getAllByText('(comercio ficticio)')).toHaveLength(1)
    expect(within(barra).getByText('Pedidos de MATU')).toBeVisible()
    const salir = within(barra).getByRole('button', { name: 'Salir' })
    expect(salir.className).not.toMatch(/turquesa/)
    // El distintivo, fuera de la barra.
    expect(within(barra).queryByText('Piloto académico')).toBeNull()
    expect(screen.getByText('Piloto académico')).toBeVisible()
    // Las pestañas.
    const nav = screen.getByRole('navigation', { name: 'Secciones del comercio' })
    expect(within(nav).getByRole('link', { name: 'Pedidos de hoy' })).toHaveAttribute('aria-current', 'page')
  })

  it('sin `ficticio`, ni «(comercio ficticio)» ni el rótulo «Comercio de prueba.»', async () => {
    apiComercio({ ficticio: false })
    abrir()
    await screen.findByRole('heading', { level: 2, name: /Por preparar/ })
    expect(screen.queryByText('(comercio ficticio)')).toBeNull()
    expect(screen.queryByText('Comercio de prueba.')).toBeNull()
  })

  it('los grupos en orden, con ícono, palabra y número; la atrasada primero, con «Era para las…»', async () => {
    apiComercio()
    abrir()
    await screen.findByRole('heading', { level: 2, name: /Por preparar/ })
    expect(h2s()).toEqual(['Por preparar (2)', 'Preparando (1)', 'Listos para retirar (1)', 'Retirados (1)', 'Cancelados (1)'])
    for (const h of screen.getAllByRole('heading', { level: 2 })) expect(h.querySelector('svg[aria-hidden="true"]')).not.toBeNull()
    const porPreparar = screen.getByRole('heading', { level: 2, name: 'Por preparar (2)' }).closest('section')!
    const filas = within(porPreparar).getAllByRole('button')
    // 5.3: la más temprana primero; el nombre accesible es todo su texto, en orden.
    expect(filas.map((f) => f.getAttribute('aria-label'))).toEqual(['Pedido K4M7XP, 2 productos, Era para las 14:00', 'Pedido R8T2WQ, 1 producto, Preparar antes de las 16:30'])
    expect(within(filas[0]).getByText('Era para las 14:00.')).toBeVisible()
    expect(screen.getByRole('button', { name: /Pedido P5Q8ZA/ })).toHaveTextContent('Esperando retiro')
    expect(screen.getByRole('button', { name: /Pedido T8F2HJ/ })).toHaveTextContent('Retirado a las 13:40')
    expect(screen.getByRole('button', { name: /Pedido Z5V7NQ/ })).toHaveTextContent('No lo prepares.')
  })

  it('el aviso de privacidad, «Actualizado a las…», el rótulo una vez y el pie con el contacto', async () => {
    apiComercio()
    abrir()
    await screen.findByRole('heading', { level: 2, name: /Por preparar/ })
    expect(screen.getByText('Aquí ves solo los productos. MATU no te muestra de quién es el pedido ni a dónde va.')).toBeVisible()
    expect(screen.getByText('Actualizado a las 14:20.')).toBeVisible()
    expect(screen.getAllByText('Comercio de prueba.')).toHaveLength(1)
    expect(screen.getByText('Estos pedidos son inventados.')).toBeVisible()
    expect(screen.getByText('¿Algo no calza? Avisa a MATU: contacto@example.com.')).toBeVisible()
    // 11.1: en /comercio no hay botón principal.
    expect(document.querySelectorAll('.bg-turquesa')).toHaveLength(0)
  })

  it('un grupo vacío no se muestra; sin abiertas, «No hay pedidos por preparar.»', async () => {
    apiComercio({ partes: partesDeEjemplo().filter((p) => p.estado === 'retirada') })
    abrir()
    expect(await screen.findByText('No hay pedidos por preparar.')).toBeVisible()
    expect(screen.getByText('Cuando llegue uno, aparece aquí.')).toBeVisible()
    expect(h2s()).toEqual(['Retirados (1)'])
  })

  it('error al traer: la nota y «Volver a intentar»', async () => {
    let falla = true
    apiComercio({ sobre: (l) => (falla && l === 'GET /v1/comercio/partes' ? { status: 500, cuerpo: { type: '/errores/interno', status: 500 } } : undefined) })
    const { urgente } = abrir()
    await waitFor(() => expect(urgente).toHaveTextContent('No pudimos traer los pedidos. Revisa tu conexión y vuelve a intentarlo.'))
    falla = false
    await u().click(screen.getByRole('button', { name: 'Volver a intentar' }))
    expect(await screen.findByRole('heading', { level: 2, name: /Por preparar/ })).toBeVisible()
  })

  it('5.5: un pedido nuevo en «Por preparar» se anuncia una vez, sin mover el foco', async () => {
    const api = apiComercio()
    const { amable } = abrir()
    const h1 = await screen.findByRole('heading', { level: 1, name: 'Pedidos de hoy' })
    await screen.findByRole('heading', { level: 2, name: /Por preparar/ })
    await waitFor(() => expect(h1).toHaveFocus())
    api.estado.partes.push({ ...partesDeEjemplo()[0], id: '6f1d0c3e-0000-4000-8000-000000000699', referencia: 'G4J8RB' })
    const usuario = u()
    await usuario.click(screen.getByRole('button', { name: 'Actualizar' }))
    await waitFor(() => expect(amable).toHaveTextContent('Llegó un pedido nuevo: G4J8RB.'))
    expect(screen.getByRole('heading', { level: 2, name: 'Por preparar (3)' })).toBeVisible()
  })

  it('403 con la consola abierta: la nota de cuenta inactiva, sin pestañas y con «Salir»', async () => {
    apiComercio({ sobre: (l) => (l === 'GET /v1/comercio/partes' ? { status: 403, cuerpo: { type: '/errores/comercio-inactivo', status: 403 } } : undefined) })
    abrir()
    expect(await screen.findByText('Esta cuenta de comercio no está activa.')).toBeVisible()
    expect(screen.queryByRole('navigation', { name: 'Secciones del comercio' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Salir' })).toBeVisible()
  })

  it('«Salir» vuelve a Entrar con el aviso de salida', async () => {
    const api = apiComercio()
    abrir()
    await screen.findByRole('heading', { level: 2, name: /Por preparar/ })
    await u().click(screen.getByRole('button', { name: 'Salir' }))
    expect(await screen.findByText('Saliste de MATU. Para volver, entra con tu correo y tu contraseña.')).toBeVisible()
    expect(window.location.pathname).toBe('/comercio/entrar')
    expect(api.lineas()).toContain('POST /v1/sesiones/cerrar')
  })
})

describe('La parte elegida vive en memoria', () => {
  it('elegir una fila lleva a /comercio/pedido sin id ni referencia en la URL, y nada al almacenamiento', async () => {
    const almacen = vigilarAlmacenamiento()
    apiComercio()
    abrir()
    await screen.findByRole('heading', { level: 2, name: /Por preparar/ })
    await u().click(screen.getByRole('button', { name: /Pedido R8T2WQ/ }))
    const h1 = await screen.findByRole('heading', { level: 1, name: 'Pedido R8T2WQ' })
    expect(window.location.pathname).toBe('/comercio/pedido')
    expect(window.location.href).not.toMatch(/R8T2WQ|6f1d0c3e/)
    expect(window.history.state).toBeNull()
    await waitFor(() => expect(h1).toHaveFocus())
    await waitFor(() => expect(document.title).toBe('Pedido R8T2WQ · MATU'))
    // La fila elegida (en ancho): aria-current y su ícono.
    const fila = screen.getByRole('button', { name: /Pedido R8T2WQ/ })
    expect(fila).toHaveAttribute('aria-current', 'true')
    expect(fila).toHaveClass('ring-2', 'ring-turquesa')
    expect(almacen).toEqual([])
    expect(sessionStorage.length).toBe(0)
  })

  it('recargar /comercio/pedido lleva a /comercio', async () => {
    apiComercio()
    abrir('/comercio/pedido')
    expect(await screen.findByRole('heading', { level: 1, name: 'Pedidos de hoy' })).toBeVisible()
    expect(window.location.pathname).toBe('/comercio')
  })

  it('«Volver a los pedidos» vuelve a la lista', async () => {
    apiComercio()
    abrir()
    await screen.findByRole('heading', { level: 2, name: /Por preparar/ })
    const usuario = u()
    await usuario.click(screen.getByRole('button', { name: /Pedido R8T2WQ/ }))
    await screen.findByRole('heading', { level: 1, name: 'Pedido R8T2WQ' })
    await usuario.click(screen.getByRole('button', { name: 'Volver a los pedidos' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Pedidos de hoy' })).toBeVisible()
    expect(window.location.pathname).toBe('/comercio')
  })
})

describe('Lo que la consola nunca dice (11.2 y 11.20)', () => {
  const raiz = join(dirname(fileURLToPath(import.meta.url)), '../src/comercio')
  const textos = readdirSync(raiz)
    .filter((f) => /\.tsx?$/.test(f))
    .map((f) => readFileSync(join(raiz, f), 'utf-8'))
    // Los comentarios no se ven en pantalla.
    .map((t) => t.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, ''))
    .join('\n')
  const cadenas = [...textos.matchAll(/'([^'\n]*)'|`([^`\n]*)`/g)].map((m) => m[1] ?? m[2]).join('\n')

  it.each(['María', 'Carmen', 'dirección', 'Total', 'Pagado'])('no aparece «%s»', (palabra) => {
    expect(cadenas).not.toContain(palabra)
  })

  it.each(['stock', 'reserva', 'sesión', 'inválido', 'token'])('ningún texto dice «%s»', (palabra) => {
    const visibles = [...textos.matchAll(/'([^'\n]*[ áéíóú][^'\n]*)'/g)].map((m) => m[1]).join('\n')
    expect(visibles.toLowerCase()).not.toContain(palabra)
  })

  it('el id de una parte de ejemplo no está en ninguna ruta del comercio', () => {
    expect(textos).not.toMatch(/\/comercio\/pedido\/|\/comercio\?/)
    expect(ID.lista).toBeTruthy()
  })
})

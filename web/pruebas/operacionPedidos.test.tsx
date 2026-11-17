// MATU-81, especificación 5, 6 y 7: la lista con su filtro, la búsqueda por referencia en el cuerpo,
// el detalle con las partes, el pago y la línea de tiempo, cada acción con su diálogo y el 409, y el
// código de retiro una sola vez. Nada de lo elegido va a la URL, el título ni el almacenamiento.
// Solo datos sintéticos.
import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { AppOperacion } from '../src/operacion/AppOperacion'
import { apiOperacion, CODIGO_RETIRO_DE_EJEMPLO, conRegionesVivas, dialogoDeJsdom, ID_OPERACION as ID, vigilarAlmacenamiento, type Sobre } from './operacionFalso'

// Con la suite completa en paralelo, montar la consola puede tardar más que el segundo por omisión.
configure({ asyncUtilTimeout: 5000 })

beforeEach(() => dialogoDeJsdom())

const u = () => userEvent.setup({ delay: null })

async function abrirLista(sobre?: Sobre) {
  const api = apiOperacion({ sobre })
  window.history.replaceState(null, '', '/operacion')
  const regiones = conRegionesVivas(<AppOperacion />)
  await screen.findByRole('heading', { level: 1, name: 'Pedidos' })
  await screen.findByRole('button', { name: /^Pedido 4822,/ })
  return { api, usuario: u(), ...regiones }
}

/** Abre un pedido desde la lista (con el filtro que lo muestra). */
async function abrirPedido(ref: string, filtro: string | null = null, sobre?: Sobre) {
  const r = await abrirLista(sobre)
  if (filtro) {
    await r.usuario.click(screen.getByRole('radio', { name: filtro }))
    await screen.findByRole('button', { name: new RegExp(`^Pedido ${ref},`) })
  }
  await r.usuario.click(screen.getByRole('button', { name: new RegExp(`^Pedido ${ref},`) }))
  await screen.findByRole('heading', { level: 1, name: `Pedido ${ref}` })
  await screen.findByText('Queda cobrado')
  return r
}

describe('La lista', () => {
  it('«Por atender» al abrir, sin datos de la familia; la fila dice estado, monto, partes y lo que pide atención', async () => {
    const { api } = await abrirLista()
    const listar = api.peticiones.find((p) => p.linea === 'GET /v1/operacion/pedidos')!
    expect(listar.query).toBe('grupo=por_atender')
    expect(screen.getByText(/Aquí no ves a quién cuida la familia ni dónde vive\. Abrir un pedido queda registrado/)).toBeVisible()
    expect(screen.getByRole('radio', { name: 'Por atender' })).toBeChecked()
    const fila = screen.getByRole('button', { name: /^Pedido 4822,/ })
    expect(fila).toHaveAccessibleName(/^Pedido 4822, Listo para retirar, \$24\.560, 2 partes, Pagado el 17\/11 a las 11:20$/)
    // Listar no abre ningún pedido: el detalle se pide solo al elegir (C9).
    expect(api.lineas().some((l) => /\/pedidos\/[^/]+$/.test(l) && l.startsWith('GET'))).toBe(false)
    expect(document.body.textContent).not.toMatch(/María|Carmen|Rosa|Rodrigo|dirección|grupo_id/)
    expect(screen.getByText('Datos de prueba.')).toBeVisible()
  })

  it('«Con problema» muestra primero lo que pide atención, con ícono y palabra', async () => {
    const { api, usuario } = await abrirLista()
    await usuario.click(screen.getByRole('radio', { name: 'Con problema' }))
    await waitFor(() => expect(api.peticiones.at(-1)?.query).toBe('grupo=con_problema'))
    const filas = await screen.findAllByRole('button', { name: /^Pedido \d+,/ })
    expect(filas[0]).toHaveAccessibleName(/Incidencia abierta|Devolución sin terminar/)
    expect(within(filas[0]).getAllByText(/Incidencia abierta|Devolución sin terminar/)[0].previousElementSibling).toHaveClass('lucide-triangle-alert')
  })

  it('vacío: «No hay pedidos en «Por atender».» y «Cuando se pague uno, aparece aquí.»', async () => {
    apiOperacion({ modo: 'operacion-vacia' })
    window.history.replaceState(null, '', '/operacion')
    conRegionesVivas(<AppOperacion />)
    expect(await screen.findByText('No hay pedidos en «Por atender».')).toBeVisible()
    expect(screen.getByText('Cuando se pague uno, aparece aquí.')).toBeVisible()
  })

  it('error al traer: la nota y «Volver a intentar», sin «Actualizar»', async () => {
    apiOperacion({ modo: 'operacion-falla' })
    window.history.replaceState(null, '', '/operacion')
    const { urgente } = conRegionesVivas(<AppOperacion />)
    await waitFor(() => expect(urgente).toHaveTextContent('No pudimos traer los pedidos. Revisa tu conexión y vuelve a intentarlo.'))
    expect(screen.getByRole('button', { name: 'Volver a intentar' })).toBeVisible()
    // Revisión visual (P3): mientras se ve el error, «Volver a intentar» es la única forma de pedirla.
    expect(screen.queryByRole('button', { name: 'Actualizar' })).toBeNull()
  })
})

describe('Buscar por referencia', () => {
  it('es un POST con la referencia en el cuerpo; con un resultado no se abre solo', async () => {
    const { api, usuario } = await abrirLista()
    const campo = screen.getByLabelText('Referencia del pedido')
    expect(campo).toHaveAttribute('autocomplete', 'off')
    expect(screen.getByRole('search')).toBeVisible()
    await usuario.type(campo, 'T8F2HJ')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    expect(await screen.findByText('Mostrando el pedido T8F2HJ.')).toBeVisible()
    const p = api.peticiones.find((x) => x.linea === 'POST /v1/operacion/pedidos/buscar')!
    expect(p.cuerpo).toEqual({ referencia: 'T8F2HJ' })
    expect(p.query).toBe('')
    expect(window.location.href).not.toContain('T8F2HJ')
    expect(screen.getAllByRole('button', { name: /^Pedido \d+,/ })).toHaveLength(1)
    expect(api.lineas().some((l) => l === `GET /v1/operacion/pedidos/${ID.porDespachar}`)).toBe(false)
    await usuario.click(screen.getByRole('button', { name: 'Ver todos' }))
    expect(screen.getByLabelText('Referencia del pedido')).toHaveValue('')
    expect(await screen.findByRole('radio', { name: 'Por atender' })).toBeChecked()
  })

  it('sin resultado: «No hay un pedido con la referencia …»; vacío: el mensaje del campo, sin enviar', async () => {
    const { api, usuario, amable } = await abrirLista()
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    expect(screen.getByText('Escribe la referencia del pedido.')).toBeVisible()
    expect(api.lineas()).not.toContain('POST /v1/operacion/pedidos/buscar')
    await usuario.type(screen.getByLabelText('Referencia del pedido'), '9999')
    await usuario.click(screen.getByRole('button', { name: 'Buscar' }))
    await waitFor(() => expect(amable).toHaveTextContent('No hay un pedido con la referencia 9999. Revisa que esté bien escrita.'))
  })
})

describe('Un pedido', () => {
  it('abre el detalle y el cobro; el título y la URL no llevan la referencia; partes, pago y lo que pasó', async () => {
    const almacen = vigilarAlmacenamiento()
    const { api } = await abrirPedido('4821', 'En camino')
    expect(api.lineas()).toContain(`GET /v1/operacion/pedidos/${ID.enCamino}`)
    expect(api.lineas()).toContain(`GET /v1/operacion/pedidos/${ID.enCamino}/cobro`)
    expect(window.location.pathname).toBe('/operacion/pedido')
    await waitFor(() => expect(document.title).toBe('Pedido · Operación · MATU'))
    expect(window.location.href).not.toContain(ID.enCamino)
    expect(window.history.state).toBeNull()
    // 6.3: las partes, con su comercio y sus líneas.
    const partes = screen.getByRole('region', { name: 'Partes' })
    expect(within(partes).getByRole('heading', { level: 3, name: 'Almacén El Ejemplo (comercio ficticio)' })).toBeVisible()
    expect(within(partes).getByText(/Faltan 3 de 3/)).toBeVisible()
    expect(within(partes).getByText('Código de retiro: ya se usó.')).toBeVisible()
    // 7: el pago, sin la tarjeta.
    const pago = screen.getByRole('region', { name: 'Pago' })
    expect(within(pago).getAllByText('$57.460').length).toBeGreaterThan(0)
    expect(within(pago).getByText('−$26.490')).toBeVisible()
    expect(within(pago).getByText('$30.970')).toBeVisible()
    expect(within(pago).getByText('MATU-4821-7Q2')).toBeVisible()
    expect(within(pago).getByText('Aprobada')).toBeVisible()
    expect(pago.textContent).not.toMatch(/terminada en|cuotas|autorización|crédito|débito/i)
    // 6.6: lo que pasó, con el actor en palabras.
    const linea = screen.getByRole('region', { name: 'Lo que pasó' })
    expect(within(linea).getAllByText('Equipo de MATU').length).toBeGreaterThan(0)
    expect(within(linea).getAllByText('MATU, de forma automática').length).toBeGreaterThan(0)
    expect(within(linea).getAllByText('Almacén El Ejemplo').length).toBeGreaterThan(0)
    expect(within(linea).getByText('de Por despachar a En camino')).toHaveClass('sr-only')
    expect(within(linea).getByText('Transbank aprobó el pago')).toBeVisible()
    expect(document.body.textContent).not.toMatch(/María|Carmen|Rosa|Rodrigo/)
    expect(almacen).toEqual([])
  })

  it('al recargar /operacion/pedido (sin pedido elegido) vuelve a /operacion', async () => {
    apiOperacion()
    window.history.replaceState(null, '', '/operacion/pedido')
    conRegionesVivas(<AppOperacion />)
    expect(await screen.findByRole('heading', { level: 1, name: 'Pedidos' })).toBeVisible()
    expect(window.location.pathname).toBe('/operacion')
  })

  it('«Volver a los pedidos» vuelve a la lista', async () => {
    const { usuario } = await abrirPedido('4824')
    await usuario.click(screen.getByRole('button', { name: 'Volver a los pedidos' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Pedidos' })).toBeVisible()
  })
})

describe('Las acciones del pedido', () => {
  it('«Marcar en camino»: el diálogo repite el verbo y dice «No se devuelve dinero.»; después, la nota con el foco', async () => {
    const { api, usuario, amable } = await abrirPedido('4824')
    await usuario.click(screen.getByRole('button', { name: 'Marcar en camino' }))
    const dialogo = await screen.findByRole('dialog', { name: '¿Marcar en camino el pedido 4824?' })
    expect(within(dialogo).getByText('La familia ve que su pedido salió a entregarse.')).toBeVisible()
    expect(within(dialogo).getByText('No se devuelve dinero.')).toHaveClass('font-bold')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Marcar en camino' }))
    await waitFor(() => expect(amable).toHaveTextContent('Marcaste en camino el pedido 4824.'))
    await waitFor(() => expect(document.getElementById('nota-del-pedido')).toHaveFocus())
    expect(api.lineas()).toContain(`POST /v1/operacion/pedidos/${ID.porDespachar}/en-camino`)
    expect(screen.queryByRole('dialog')).toBeNull()
    // La pantalla vuelve a pedir el pedido: ahora está en camino, con «Marcar entregado».
    expect(await screen.findByRole('button', { name: 'Marcar entregado' })).toBeVisible()
  })

  it('«Cancelar con devolución»: macizo `pronto` solo en el diálogo, con «No cancelar»', async () => {
    const { usuario } = await abrirPedido('4828', 'Con problema')
    const boton = screen.getByRole('button', { name: 'Cancelar con devolución' })
    expect(boton.className).not.toMatch(/(^| )bg-pronto( |$)/)
    await usuario.click(boton)
    const dialogo = await screen.findByRole('dialog', { name: '¿Cancelar con devolución el pedido 4828?' })
    expect(within(dialogo).getByText('Se cancelan todas sus partes y los comercios ven que no deben prepararlas. Esto no se deshace.')).toBeVisible()
    expect(within(dialogo).getByText('Se devuelven $24.560 a la misma tarjeta con que se pagó, envío incluido.')).toHaveClass('font-bold')
    expect(within(dialogo).getByRole('button', { name: 'No cancelar' })).toBeVisible()
  })

  it('C22: el monto del diálogo es el `monto_a_devolver` de la API, aunque no calce con las líneas', async () => {
    const { usuario, amable } = await abrirPedido('4828', 'Con problema', (l, _c, consola) => {
      if (l !== `GET /v1/operacion/pedidos/${ID.noEntregado}`) return undefined
      const base = consola.atender({ metodo: 'GET', ruta: `/v1/operacion/pedidos/${ID.noEntregado}`, query: new URLSearchParams(), cuerpo: null, ifMatch: null })!
      const d = base.cuerpo as { acciones: { accion: string; monto_a_devolver: number }[] }
      return { ...base, cuerpo: { ...d, acciones: d.acciones.map((a) => ({ ...a, monto_a_devolver: 12345 })) } }
    })
    await usuario.click(screen.getByRole('button', { name: 'Cancelar con devolución' }))
    const dialogo = await screen.findByRole('dialog')
    expect(within(dialogo).getByText('Se devuelven $12.345 a la misma tarjeta con que se pagó, envío incluido.')).toBeVisible()
    await usuario.click(within(dialogo).getByRole('button', { name: 'Cancelar con devolución' }))
    await waitFor(() => expect(amable).toHaveTextContent('Cancelaste el pedido 4828. Estamos devolviendo $12.345 a la misma tarjeta.'))
  })

  it('409: el diálogo se cierra, el pedido se vuelve a pedir y la nota dice que cambió', async () => {
    const { usuario, amable, api } = await abrirPedido('4824', null, (l) =>
      l.endsWith('/en-camino') ? { status: 409, cuerpo: { type: '/errores/estado-pedido', status: 409 } } : undefined,
    )
    const antes = api.lineas().filter((l) => l === `GET /v1/operacion/pedidos/${ID.porDespachar}`).length
    await usuario.click(screen.getByRole('button', { name: 'Marcar en camino' }))
    await usuario.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Marcar en camino' }))
    await waitFor(() => expect(amable).toHaveTextContent('Este pedido cambió mientras lo veías. Te mostramos cómo quedó. Revisa si todavía hace falta.'))
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(api.lineas().filter((l) => l === `GET /v1/operacion/pedidos/${ID.porDespachar}`).length).toBe(antes + 1)
  })

  it('503 al cancelar: el error en el diálogo, y el pedido no cambió', async () => {
    const { usuario } = await abrirPedido('4828', 'Con problema', (l) =>
      l.endsWith('/cancelar-con-devolucion') ? { status: 503, cuerpo: { type: '/errores/pasarela-no-disponible', status: 503 } } : undefined,
    )
    await usuario.click(screen.getByRole('button', { name: 'Cancelar con devolución' }))
    const dialogo = await screen.findByRole('dialog')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Cancelar con devolución' }))
    expect(await within(dialogo).findByText('No pudimos hablar con Transbank. El pedido no cambió. Vuelve a intentarlo en unos minutos.')).toBeVisible()
  })

  it('cerrar el diálogo sin hacer nada devuelve el foco al botón que lo abrió', async () => {
    const { usuario, api } = await abrirPedido('4824')
    await usuario.click(screen.getByRole('button', { name: 'Marcar en camino' }))
    await usuario.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Volver al pedido' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Marcar en camino' })).toHaveFocus())
    expect(api.lineas().some((l) => l.endsWith('/en-camino'))).toBe(false)
  })
})

describe('El código de retiro', () => {
  it('se genera con confirmación, se muestra una vez sin botón de copiar y desaparece con «Ya lo tengo»', async () => {
    const almacen = vigilarAlmacenamiento()
    const { usuario, amable, urgente, api } = await abrirPedido('4822')
    const parte = screen.getByRole('region', { name: /^Farmacia Los Aromos/ })
    expect(within(parte).getByText('Código de retiro: todavía no hay uno.')).toBeVisible()
    await usuario.click(within(parte).getByRole('button', { name: 'Generar el código' }))
    const dialogo = await screen.findByRole('dialog', { name: '¿Generar el código de retiro de la parte H6N3VD?' })
    expect(within(dialogo).getByText('Lo verás una sola vez. Tenlo a mano para dárselo a quien va a retirar el pedido.')).toBeVisible()
    expect(within(dialogo).queryByText(/El código anterior deja de servir/)).toBeNull()
    await usuario.click(within(dialogo).getByRole('button', { name: 'Generar el código' }))
    const titulo = await screen.findByRole('heading', { level: 3, name: 'Código de retiro · Parte H6N3VD' })
    await waitFor(() => expect(titulo).toHaveFocus())
    const digitos = screen.getByRole('img', { name: 'Código: 4 8 2 1 7 3' })
    expect(digitos).toHaveClass('select-none')
    expect(digitos.textContent).toBe(CODIGO_RETIRO_DE_EJEMPLO)
    expect(screen.getByText('Dáselo a quien va a retirar el pedido en Farmacia Los Aromos.')).toBeVisible()
    expect(screen.getByText('Solo lo verás ahora. Si generas otro, este deja de servir.')).toBeVisible()
    expect(screen.queryByRole('button', { name: /copiar/i })).toBeNull()
    expect(api.lineas()).toContain(`POST /v1/operacion/partes/${ID.parteSinCodigo}/codigo`)
    // C20: nunca en el almacenamiento, la URL, `history.state`, el título ni las regiones vivas.
    expect(almacen.join(' ')).not.toContain(CODIGO_RETIRO_DE_EJEMPLO)
    expect(window.location.href).not.toContain(CODIGO_RETIRO_DE_EJEMPLO)
    expect(JSON.stringify(window.history.state)).not.toContain(CODIGO_RETIRO_DE_EJEMPLO)
    expect(document.title).not.toContain(CODIGO_RETIRO_DE_EJEMPLO)
    expect(amable.textContent).not.toContain(CODIGO_RETIRO_DE_EJEMPLO)
    expect(urgente.textContent).not.toContain(CODIGO_RETIRO_DE_EJEMPLO)
    expect(document.querySelector(`[title*="${CODIGO_RETIRO_DE_EJEMPLO}"]`)).toBeNull()
    await usuario.click(screen.getByRole('button', { name: 'Ya lo tengo' }))
    expect(document.body.textContent).not.toContain(CODIGO_RETIRO_DE_EJEMPLO)
    expect(await within(screen.getByRole('region', { name: /^Farmacia Los Aromos/ })).findByText('Código de retiro: hay uno vigente.')).toBeVisible()
  })

  it('regenerar pide confirmar con «El código anterior deja de servir.» en negrita', async () => {
    const { usuario } = await abrirPedido('4822')
    const parte = screen.getByRole('region', { name: /^Almacén El Ejemplo/ })
    expect(within(parte).getByText('Código de retiro: hay uno vigente.')).toBeVisible()
    await usuario.click(within(parte).getByRole('button', { name: 'Generar un código nuevo' }))
    const dialogo = await screen.findByRole('dialog', { name: '¿Generar un código nuevo para la parte P5Q8ZA?' })
    expect(within(dialogo).getByText('El código anterior deja de servir. Si ya se lo diste a alguien, avísale que use el nuevo.')).toHaveClass('font-bold')
    expect(within(dialogo).getByRole('button', { name: 'Generar un código nuevo' })).toBeVisible()
  })

  it('se borra al salir del pedido: al volver no se ve, solo se puede generar otro', async () => {
    const { usuario } = await abrirPedido('4822')
    await usuario.click(within(screen.getByRole('region', { name: /^Farmacia Los Aromos/ })).getByRole('button', { name: 'Generar el código' }))
    await usuario.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Generar el código' }))
    await screen.findByRole('img', { name: /^Código:/ })
    await usuario.click(screen.getByRole('link', { name: 'Retractos' }))
    await screen.findByRole('heading', { level: 1, name: 'Retractos' })
    expect(document.body.textContent).not.toContain(CODIGO_RETIRO_DE_EJEMPLO)
    await usuario.click(screen.getByRole('link', { name: 'Pedidos' }))
    await usuario.click(await screen.findByRole('button', { name: /^Pedido 4822,/ }))
    await screen.findByRole('heading', { level: 1, name: 'Pedido 4822' })
    expect(screen.queryByRole('img', { name: /^Código:/ })).toBeNull()
    expect(document.body.textContent).not.toContain(CODIGO_RETIRO_DE_EJEMPLO)
  })

  it('409 (la parte ya no está lista): «Esta parte cambió mientras la veías.» y el pedido se vuelve a pedir', async () => {
    const { usuario, amable } = await abrirPedido('4822', null, (l) =>
      l.endsWith('/codigo') ? { status: 409, cuerpo: { type: '/errores/estado-parte', status: 409 } } : undefined,
    )
    await usuario.click(within(screen.getByRole('region', { name: /^Farmacia Los Aromos/ })).getByRole('button', { name: 'Generar el código' }))
    await usuario.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Generar el código' }))
    await waitFor(() => expect(amable).toHaveTextContent('Esta parte cambió mientras la veías. Te mostramos cómo quedó.'))
    expect(screen.queryByRole('img', { name: /^Código:/ })).toBeNull()
  })
})

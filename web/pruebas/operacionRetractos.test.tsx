// MATU-81, especificación 8 y 9: los retractos (devolver, no devolver con motivo, y el que llegó por
// correo con su 422 y su 409) y las incidencias (anotar, el 412 que conserva lo escrito, pasar a en
// gestión y resolver). El correo y la nota nunca van a la URL, un anuncio ni el almacenamiento.
// Solo datos sintéticos.
import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { AppOperacion } from '../src/operacion/AppOperacion'
import { apiOperacion, conRegionesVivas, CORREO_ADMIN_DE_EJEMPLO, dialogoDeJsdom, ID_OPERACION as ID, vigilarAlmacenamiento, type Sobre } from './operacionFalso'

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

async function abrirRetracto(sobre?: Sobre) {
  const r = await abrir('/operacion/retractos', sobre)
  await r.usuario.click(await screen.findByRole('button', { name: /^Retracto del pedido 4826,/ }, { timeout: 5000 }))
  await screen.findByRole('heading', { level: 1, name: 'Retracto del pedido 4826' })
  return r
}

/** Abre un pedido de la lista «Cerrados» (los entregados). */
async function abrirEntregado(ref: string, sobre?: Sobre) {
  const r = await abrir('/operacion', sobre)
  await screen.findByRole('heading', { level: 1, name: 'Pedidos' })
  await r.usuario.click(screen.getByRole('radio', { name: 'Cerrados' }))
  await r.usuario.click(await screen.findByRole('button', { name: new RegExp(`^Pedido ${ref},`) }))
  await screen.findByRole('heading', { level: 1, name: `Pedido ${ref}` })
  return r
}

describe('Retractos', () => {
  it('la lista: el plazo más cercano en `atenta` con su ícono, sin abrir el pedido', async () => {
    const { api } = await abrir('/operacion/retractos')
    // La primera prueba del archivo: con la suite completa en paralelo, montar la app tarda más de 1 s.
    const fila = await screen.findByRole('button', { name: /^Retracto del pedido 4826,/ }, { timeout: 5000 })
    expect(fila).toHaveAccessibleName(/\$26\.490, Por la app, Pedido el 16\/11, Responder antes del 18\/11\/2026$/)
    expect(within(fila).getByText('Responder antes del 18/11/2026').parentElement).toHaveClass('text-atenta')
    expect(api.lineas().some((l) => l.startsWith('GET /v1/operacion/pedidos'))).toBe(false)
    expect(screen.getByText(/Aquí no ves a quién cuida la familia/)).toBeVisible()
  })

  it('«Devolver»: el diálogo con el monto de la API; después, «Devolviste $26.490…» con el foco', async () => {
    const { api, usuario, amable } = await abrirRetracto()
    expect(screen.getByText('Productos que devuelve')).toBeVisible()
    expect(screen.getByText('Incluye el envío: no')).toBeVisible()
    await usuario.click(screen.getByRole('button', { name: 'Devolver $26.490' }))
    const dialogo = await screen.findByRole('dialog', { name: '¿Devolver $26.490 por este retracto?' })
    expect(within(dialogo).getByText('Es el retracto del pedido 4826. Esto no se deshace.')).toBeVisible()
    expect(within(dialogo).getByText('Se devuelven $26.490 a la misma tarjeta con que se pagó.')).toHaveClass('font-bold')
    await usuario.click(within(dialogo).getByRole('button', { name: 'Devolver $26.490' }))
    await waitFor(() => expect(amable).toHaveTextContent('Devolviste $26.490 por el retracto del pedido 4826. Cuándo se ve en la cuenta depende del banco.'))
    await waitFor(() => expect(document.getElementById('nota-del-retracto')).toHaveFocus())
    const p = api.peticiones.find((x) => x.linea === `POST /v1/operacion/retractos/${ID.retractoApp}/resolver`)!
    expect(p.cuerpo).toEqual({ decision: 'devolver' })
    expect(screen.getAllByText('Devuelto').length).toBeGreaterThan(0)
  })

  it('«No devolver» no envía sin motivo; con uno, el diálogo dice que la familia lo ve', async () => {
    const { api, usuario, amable } = await abrirRetracto()
    await usuario.click(screen.getByRole('button', { name: 'No devolver' }))
    expect(screen.getByText('¿Por qué no se devuelve?')).toBeVisible()
    expect(screen.getByText('La familia ve este motivo.')).toBeVisible()
    // Mientras se elige el motivo, «Devolver» se oculta: hay un solo macizo.
    expect(screen.queryByRole('button', { name: 'Devolver $26.490' })).toBeNull()
    await usuario.click(screen.getByRole('button', { name: 'No devolver' }))
    expect(screen.getByText('Elige por qué no se devuelve.')).toBeVisible()
    expect(screen.queryByRole('dialog')).toBeNull()
    await usuario.click(screen.getByRole('radio', { name: 'El sello del producto se abrió.' }))
    await usuario.click(screen.getByRole('button', { name: 'No devolver' }))
    const dialogo = await screen.findByRole('dialog', { name: '¿No devolver el dinero de este retracto?' })
    // O3 del analista: el motivo del diálogo es el texto exacto que lee la familia, no el de la consola.
    expect(within(dialogo).getByText('No se devuelve dinero. La familia ve el motivo: El producto volvió con el sello abierto.')).toBeVisible()
    await usuario.click(within(dialogo).getByRole('button', { name: 'No devolver' }))
    await waitFor(() => expect(amable).toHaveTextContent('Respondiste el retracto del pedido 4826 sin devolver dinero.'))
    const p = api.peticiones.find((x) => x.linea.endsWith('/resolver'))!
    expect(p.cuerpo).toEqual({ decision: 'rechazar', motivo: 'sello_abierto' })
  })

  it('8.4 (v1.1): al abrir «No devolver» el foco va a la primera opción; con «Cancelar», vuelve a «No devolver»', async () => {
    const { usuario } = await abrirRetracto()
    await usuario.click(screen.getByRole('button', { name: 'No devolver' }))
    await waitFor(() => expect(screen.getByRole('radio', { name: 'El sello del producto se abrió.' })).toHaveFocus())
    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'No devolver' })).toHaveFocus())
    expect(screen.queryByText('¿Por qué no se devuelve?')).toBeNull()
  })

  it('los chips (decisión 466): «Por resolver» pide estado=solicitado; «Devueltos», estado=devuelto, con su vacío', async () => {
    const { api, usuario } = await abrir('/operacion/retractos')
    await screen.findByRole('button', { name: /^Retracto del pedido 4826,/ }, { timeout: 5000 })
    const grupo = screen.getByRole('group', { name: 'Mostrar' })
    expect(within(grupo).getAllByRole('radio').map((r) => r.closest('label')?.textContent)).toEqual(['Por resolver', 'Devueltos', 'Sin devolución'])
    expect(within(grupo).getByRole('radio', { name: 'Por resolver' })).toBeChecked()
    const consultas = () => api.peticiones.filter((x) => x.linea === 'GET /v1/operacion/retractos').map((x) => x.query)
    expect(consultas()).toEqual(['estado=solicitado'])
    await usuario.click(within(grupo).getByRole('radio', { name: 'Devueltos' }))
    expect(await screen.findByText('No hay retractos en «Devueltos».')).toBeVisible()
    expect(consultas().at(-1)).toBe('estado=devuelto')
    expect(screen.getByRole('radio', { name: 'Devueltos' })).toHaveFocus()
    await usuario.click(within(grupo).getByRole('radio', { name: 'Sin devolución' }))
    expect(await screen.findByText('No hay retractos en «Sin devolución».')).toBeVisible()
    expect(consultas().at(-1)).toBe('estado=rechazado')
  })

  it('resuelto: sale de «Por resolver», aparece en «Sin devolución» y dice «Resuelto el … a las …» y el motivo, sin botones', async () => {
    const { usuario } = await abrirRetracto()
    await usuario.click(screen.getByRole('button', { name: 'No devolver' }))
    await usuario.click(screen.getByRole('radio', { name: 'MATU no recibió el producto de vuelta.' }))
    await usuario.click(screen.getByRole('button', { name: 'No devolver' }))
    await usuario.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'No devolver' }))
    expect(await screen.findByText('Resuelto el 17/11/2026 a las 14:20.')).toBeVisible()
    expect(screen.getByText('MATU no recibió el producto de vuelta.')).toBeVisible()
    expect(screen.queryByRole('button', { name: /^Devolver/ })).toBeNull()
    await waitFor(() => expect(screen.getByText('No hay retractos por resolver.')).toBeVisible())
    await usuario.click(screen.getByRole('radio', { name: 'Sin devolución' }))
    const fila = await screen.findByRole('button', { name: /^Retracto del pedido 4826,/ })
    // Ya no tiene plazo que responder.
    expect(fila).toHaveAccessibleName(/\$26\.490, Por la app, Pedido el 16\/11$/)
  })

  it('hay_mas: «Hay más de 200 retractos aquí. Mostramos los primeros 200.»', async () => {
    await abrir('/operacion/retractos', (l, _c, consola) =>
      l === 'GET /v1/operacion/retractos' ? { status: 200, cuerpo: { retractos: (consola.atender({ metodo: 'GET', ruta: l.slice(4), query: new URLSearchParams(), cuerpo: null, ifMatch: null })!.cuerpo as { retractos: unknown[] }).retractos, hay_mas: true } } : undefined,
    )
    await screen.findByRole('button', { name: /^Retracto del pedido 4826,/ }, { timeout: 5000 })
    expect(screen.getByText('Hay más de 200 retractos aquí. Mostramos los primeros 200.')).toHaveClass('text-tenue')
  })

  it('sin hay_mas no hay nota de los 200', async () => {
    await abrir('/operacion/retractos')
    await screen.findByRole('button', { name: /^Retracto del pedido 4826,/ }, { timeout: 5000 })
    expect(screen.queryByText(/Mostramos los primeros 200\./)).toBeNull()
  })

  it('8.5 (v1.1): en el pedido, cada retracto lleva la etiqueta de su estado y el plazo', async () => {
    const { api } = await abrirEntregado('4826')
    const fila = await within(await screen.findByRole('region', { name: 'Retractos' })).findByRole('button', { name: /^Retracto del pedido 4826/ })
    expect(fila).toHaveTextContent('Por resolver')
    expect(within(fila).getByText('Responder antes del 18/11/2026')).toBeVisible()
    // Los tres estados, para que también se vean «Devuelto» y «Sin devolución».
    expect(api.peticiones.filter((x) => x.linea === 'GET /v1/operacion/retractos').map((x) => x.query)).toContain('estado=solicitado&estado=devuelto&estado=rechazado')
  })

  it('8.5 (v1.1): un pedido sin retractos ni plazo para registrar uno no tiene sección «Retractos»', async () => {
    const { api, usuario } = await abrir('/operacion')
    await usuario.click(await screen.findByRole('button', { name: /^Pedido 4822,/ }, { timeout: 5000 }))
    await screen.findByRole('heading', { level: 1, name: 'Pedido 4822' })
    await waitFor(() => expect(api.lineas()).toContain('GET /v1/operacion/retractos'))
    await screen.findByRole('heading', { level: 2, name: 'Incidencias' })
    expect(screen.queryByRole('heading', { level: 2, name: 'Retractos' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Registrar un retracto por correo' })).toBeNull()
  })

  it('409 al resolver: «Este retracto cambió mientras lo veías.»', async () => {
    const { usuario, amable } = await abrirRetracto((l) => (l.endsWith('/resolver') ? { status: 409, cuerpo: { type: '/errores/retracto-no-resoluble', status: 409 } } : undefined))
    await usuario.click(screen.getByRole('button', { name: 'Devolver $26.490' }))
    await usuario.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Devolver $26.490' }))
    await waitFor(() => expect(amable).toHaveTextContent('Este retracto cambió mientras lo veías. Te mostramos cómo quedó.'))
  })
})

describe('El retracto que llegó por correo', () => {
  const CORREO_OTRO = 'otra-persona@example.com'

  async function abrirFormulario(ref = '4825', sobre?: Sobre) {
    const r = await abrirEntregado(ref, sobre)
    await r.usuario.click(screen.getByRole('button', { name: 'Registrar un retracto por correo' }))
    await screen.findByRole('heading', { level: 3, name: 'Registrar un retracto por correo' })
    return r
  }

  it('el campo sin autocompletar ni sugerencias; sin correo ni productos no envía', async () => {
    const { api, usuario } = await abrirFormulario()
    const campo = screen.getByLabelText('Correo de quien lo pidió')
    expect(campo).toHaveAttribute('autocomplete', 'off')
    expect(campo).toHaveAttribute('type', 'email')
    expect(campo).not.toHaveAttribute('list')
    expect(screen.getByText('Escríbelo tal como viene en el correo. Tiene que ser de quien administra el grupo de este pedido.')).toBeVisible()
    // Mientras el formulario está abierto, la acción principal del pedido se oculta (no tiene ninguna aquí).
    await usuario.click(screen.getByRole('button', { name: 'Registrar el retracto' }))
    expect(screen.getByText('Escribe el correo de quien lo pidió.')).toBeVisible()
    await usuario.type(campo, 'no-es-un-correo')
    await usuario.click(screen.getByRole('button', { name: 'Registrar el retracto' }))
    expect(screen.getByText('Escribe un correo, por ejemplo nombre@example.com.')).toBeVisible()
    await usuario.clear(campo)
    await usuario.type(campo, CORREO_ADMIN_DE_EJEMPLO)
    await usuario.click(screen.getByRole('button', { name: 'Registrar el retracto' }))
    expect(screen.getByText('Elige al menos un producto.')).toBeVisible()
    expect(api.lineas().some((l) => l.endsWith('/retractos') && l.startsWith('POST'))).toBe(false)
  })

  it('422: el correo no es de quien administra; el campo queda vacío y ningún aviso repite el correo', async () => {
    const almacen = vigilarAlmacenamiento()
    const { usuario, urgente } = await abrirFormulario()
    await usuario.type(screen.getByLabelText('Correo de quien lo pidió'), CORREO_OTRO)
    await usuario.click(screen.getAllByRole('button', { name: 'Más: ¿Cuántos?' })[0])
    await usuario.click(screen.getByRole('button', { name: 'Registrar el retracto' }))
    await waitFor(() => expect(urgente).toHaveTextContent('Ese correo no es de quien administra el grupo de este pedido. Revisa el correo. Si lo mandó otra persona, respóndele que lo pida quien administra.'))
    expect(screen.getByLabelText('Correo de quien lo pidió')).toHaveValue('')
    await waitFor(() => expect(screen.getByLabelText('Correo de quien lo pidió')).toHaveFocus())
    expect(document.body.textContent).not.toContain(CORREO_OTRO)
    expect(window.location.href).not.toContain('example.com')
    expect(almacen).toEqual([])
  })

  it('con el correo de quien administra: el correo va en el cuerpo, el retracto aparece y la nota lleva a Retractos', async () => {
    const { api, usuario, amable } = await abrirFormulario()
    await usuario.type(screen.getByLabelText('Correo de quien lo pidió'), CORREO_ADMIN_DE_EJEMPLO)
    await usuario.click(screen.getAllByRole('button', { name: 'Más: ¿Cuántos?' })[0])
    await usuario.click(screen.getByRole('button', { name: 'Registrar el retracto' }))
    await waitFor(() => expect(amable).toHaveTextContent('Registraste el retracto del pedido 4825. Resuélvelo en «Retractos».'))
    const p = api.peticiones.find((x) => x.linea === `POST /v1/operacion/pedidos/${ID.entregado}/retractos`)!
    expect(p.cuerpo).toMatchObject({ correo_solicitante: CORREO_ADMIN_DE_EJEMPLO, lineas: [{ cantidad: 1 }] })
    expect(document.body.textContent).not.toContain(CORREO_ADMIN_DE_EJEMPLO)
    await usuario.click(screen.getByRole('button', { name: 'Ir a Retractos' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Retracto del pedido 4825' })).toBeVisible()
  })

  it('409 fuera de plazo: «Este pedido ya no tiene plazo de retracto: venció el …»', async () => {
    const { usuario, urgente } = await abrirFormulario('4831')
    await usuario.type(screen.getByLabelText('Correo de quien lo pidió'), CORREO_ADMIN_DE_EJEMPLO)
    await usuario.click(screen.getAllByRole('button', { name: 'Más: ¿Cuántos?' })[0])
    await usuario.click(screen.getByRole('button', { name: 'Registrar el retracto' }))
    await waitFor(() => expect(urgente).toHaveTextContent(/^Este pedido ya no tiene plazo de retracto: venció el \d{2}\/\d{2}\/\d{4}\.$/))
    expect(screen.getByLabelText('Correo de quien lo pidió')).toHaveValue('')
  })

  // Con la máquina cargada pasó los 15 s: son tres envíos del formulario completo.
  it('varios retractos por pedido: un segundo se admite; pedir lo ya pedido es el 422 con su texto', { timeout: 30_000 }, async () => {
    const { api, usuario, amable, urgente } = await abrirFormulario()
    await usuario.type(screen.getByLabelText('Correo de quien lo pidió'), CORREO_ADMIN_DE_EJEMPLO)
    await usuario.click(screen.getAllByRole('button', { name: 'Más: ¿Cuántos?' })[0])
    await usuario.click(screen.getByRole('button', { name: 'Registrar el retracto' }))
    await waitFor(() => expect(amable).toHaveTextContent('Registraste el retracto del pedido 4825.'))
    // El segundo, con el primero todavía por resolver: las dos unidades del pañal, y una ya se pidió.
    await usuario.click(screen.getByRole('button', { name: 'Registrar un retracto por correo' }))
    await screen.findByRole('heading', { level: 3, name: 'Registrar un retracto por correo' })
    await usuario.type(screen.getByLabelText('Correo de quien lo pidió'), CORREO_ADMIN_DE_EJEMPLO)
    const mas = () => screen.getAllByRole('button', { name: 'Más: ¿Cuántos?' })[0]
    await usuario.click(mas())
    await usuario.click(mas())
    await usuario.click(screen.getByRole('button', { name: 'Registrar el retracto' }))
    await waitFor(() => expect(urgente).toHaveTextContent('Elige productos que se entregaron, hasta lo que queda por devolver.'))
    expect(document.body.textContent).not.toContain('ya tiene un retracto por resolver')
    // Con la unidad que queda, sí.
    await usuario.click(screen.getAllByRole('button', { name: 'Menos: ¿Cuántos?' })[0])
    await usuario.type(screen.getByLabelText('Correo de quien lo pidió'), CORREO_ADMIN_DE_EJEMPLO)
    await usuario.click(screen.getByRole('button', { name: 'Registrar el retracto' }))
    await waitFor(() => expect(api.peticiones.filter((x) => x.linea === `POST /v1/operacion/pedidos/${ID.entregado}/retractos`)).toHaveLength(3))
    await waitFor(() => expect(screen.queryByRole('heading', { level: 3, name: 'Registrar un retracto por correo' })).toBeNull())
    expect(api.consola.estado.retractos.filter((r) => r.pedido_id === ID.entregado)).toHaveLength(2)
  })

  it('sin respuesta: [L 8] completo y el correo se conserva', async () => {
    const { usuario, urgente } = await abrirFormulario('4825', (l) => (l.endsWith('/retractos') && l.startsWith('POST') ? { status: 500, cuerpo: { type: '/errores/interno', status: 500 } } : undefined))
    await usuario.type(screen.getByLabelText('Correo de quien lo pidió'), CORREO_ADMIN_DE_EJEMPLO)
    await usuario.click(screen.getAllByRole('button', { name: 'Más: ¿Cuántos?' })[0])
    await usuario.click(screen.getByRole('button', { name: 'Registrar el retracto' }))
    await waitFor(() => expect(urgente).toHaveTextContent('Lo que escribiste sigue aquí.'))
    expect(screen.getByLabelText('Correo de quien lo pidió')).toHaveValue(CORREO_ADMIN_DE_EJEMPLO)
  })
})

describe('Incidencias', () => {
  const NOTA = 'El comercio avisó que faltó la crema.'

  it('anotar desde el pedido: la ayuda antes del campo y en su descripción, el tope de 500 y el contador', async () => {
    const almacen = vigilarAlmacenamiento()
    const { api, usuario, amable } = await abrirEntregado('4825')
    await usuario.click(screen.getByRole('button', { name: 'Anotar una incidencia' }))
    await screen.findByRole('heading', { level: 3, name: 'Anotar una incidencia' })
    const campo = screen.getByLabelText('Nota')
    expect(campo).toHaveAttribute('maxlength', '500')
    expect(campo).toHaveAccessibleDescription(/No escribas nombres, datos de salud ni la dirección\. La familia puede leer esta nota\./)
    const ayuda = screen.getByText('No escribas nombres, datos de salud ni la dirección. La familia puede leer esta nota.')
    expect(ayuda.compareDocumentPosition(campo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByText('de 500 caracteres')).toBeVisible()
    await usuario.click(screen.getByRole('button', { name: 'Guardar la incidencia' }))
    expect(screen.getByText('Elige qué pasó.')).toBeVisible()
    await usuario.click(screen.getByRole('radio', { name: 'Falta un producto' }))
    await usuario.click(screen.getByRole('button', { name: 'Guardar la incidencia' }))
    expect(screen.getByText('Escribe qué pasó, sin nombres ni datos de salud.')).toBeVisible()
    await usuario.type(campo, NOTA)
    await usuario.click(screen.getByRole('button', { name: 'Guardar la incidencia' }))
    await waitFor(() => expect(amable).toHaveTextContent('Anotaste la incidencia en el pedido 4825.'))
    const p = api.peticiones.find((x) => x.linea === `POST /v1/operacion/pedidos/${ID.entregado}/incidencias`)!
    expect(p.cuerpo).toEqual({ tipo: 'faltante', descripcion: NOTA, asignarme: false })
    expect(amable.textContent).not.toContain(NOTA)
    expect(almacen).toEqual([])
    expect(within(screen.getByRole('region', { name: 'Incidencias' })).getByText('Abierta')).toBeVisible()
  })

  it('9.3 (v1.1): al abrir, el foco va a la primera opción de «¿Qué pasó?»; sin tipo, el error y el foco vuelven ahí', async () => {
    const { usuario } = await abrirEntregado('4825')
    await usuario.click(screen.getByRole('button', { name: 'Anotar una incidencia' }))
    const primera = await screen.findByRole('radio', { name: 'Falta un producto' })
    await waitFor(() => expect(primera).toHaveFocus())
    await usuario.click(screen.getByLabelText('Nota'))
    await usuario.click(screen.getByRole('button', { name: 'Guardar la incidencia' }))
    expect(screen.getByText('Elige qué pasó.')).toBeVisible()
    await waitFor(() => expect(primera).toHaveFocus())
    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Anotar una incidencia' })).toHaveFocus())
  })

  it('más de 500 (422): «La nota admite hasta 500 caracteres…»', async () => {
    const { usuario } = await abrirEntregado('4825', (l) =>
      l.endsWith('/incidencias') ? { status: 422, cuerpo: { type: '/errores/validacion', status: 422, errores: [{ campo: 'descripcion', mensaje: 'x', tipo: 'string_too_long' }] } } : undefined,
    )
    await usuario.click(screen.getByRole('button', { name: 'Anotar una incidencia' }))
    await usuario.click(await screen.findByRole('radio', { name: 'Otra cosa' }))
    await usuario.type(screen.getByLabelText('Nota'), NOTA)
    await usuario.click(screen.getByRole('button', { name: 'Guardar la incidencia' }))
    expect(await screen.findByText('La nota admite hasta 500 caracteres. Acórtala un poco para guardarla.')).toBeVisible()
    expect(screen.getByLabelText('Nota')).toHaveValue(NOTA)
  })

  it('la lista no muestra la nota; el detalle sí, y «Pasar a en gestión» manda If-Match', async () => {
    const { api, usuario, amable } = await abrir('/operacion/incidencias')
    const fila = await screen.findByRole('button', { name: /^Falta un producto, Abiertas, Pedido 4821/ })
    expect(fila.textContent).not.toContain('El comercio avisó')
    await usuario.click(fila)
    expect(await screen.findByRole('heading', { level: 1, name: 'Falta un producto' })).toBeVisible()
    expect(screen.getByText('El comercio avisó que no le llegó el suplemento.')).toBeVisible()
    await usuario.click(screen.getByRole('button', { name: 'Pasar a en gestión' }))
    await waitFor(() => expect(amable).toHaveTextContent('La incidencia quedó en gestión.'))
    const p = api.peticiones.find((x) => x.linea === `PATCH /v1/operacion/incidencias/${ID.incidenciaAbierta}`)!
    expect(p.ifMatch).toBe('"i1"')
    expect(p.cuerpo).toEqual({ estado: 'en_gestion', asignacion: 'a_mi' })
    expect(screen.getByText('La tienes tú.')).toBeVisible()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Resolver' })).toHaveFocus())
  })

  it('412 al resolver: la nota de otra persona, lo escrito se conserva y se guarda con el ETag nuevo', async () => {
    let primera = true
    const { api, usuario, amable } = await abrir('/operacion/incidencias', (l) => {
      if (l !== `PATCH /v1/operacion/incidencias/${ID.incidenciaAbierta}` || !primera) return undefined
      primera = false
      return { status: 412, cuerpo: { type: '/errores/version-desactualizada', status: 412 } }
    })
    await usuario.click(await screen.findByRole('button', { name: /^Falta un producto, Abiertas/ }))
    await usuario.click(await screen.findByRole('button', { name: 'Resolver' }))
    const campo = await screen.findByLabelText('Cómo se resolvió')
    expect(campo).toHaveAccessibleDescription(/La familia puede leer esta nota\./)
    await usuario.click(screen.getByRole('button', { name: 'Marcar resuelta' }))
    expect(screen.getByText('Escribe cómo se resolvió, sin nombres ni datos de salud.')).toBeVisible()
    await usuario.type(campo, 'Se devolvió el suplemento a la tarjeta.')
    await usuario.click(screen.getByRole('button', { name: 'Marcar resuelta' }))
    await waitFor(() => expect(amable).toHaveTextContent('Otra persona del equipo cambió esta incidencia mientras la veías. Te mostramos cómo quedó. Lo que escribiste sigue aquí.'))
    expect(screen.getByLabelText('Cómo se resolvió')).toHaveValue('Se devolvió el suplemento a la tarjeta.')
    await usuario.click(screen.getByRole('button', { name: 'Marcar resuelta' }))
    await waitFor(() => expect(amable).toHaveTextContent('Marcaste resuelta la incidencia.'))
    const patches = api.peticiones.filter((x) => x.linea.startsWith('PATCH'))
    expect(patches).toHaveLength(2)
    expect(patches[1].cuerpo).toEqual({ estado: 'resuelta', resolucion: 'Se devolvió el suplemento a la tarjeta.' })
    expect(screen.getByRole('heading', { level: 2, name: 'Cómo se resolvió' })).toBeVisible()
    expect(screen.getByText(/^Resuelta el \d{2}\/\d{2}\/\d{4} a las \d{2}:\d{2}\.$/)).toBeVisible()
  })

  it('decisión 471: una resuelta con su nota y su resolución no dice que la nota se borró', async () => {
    const { usuario } = await abrir('/operacion/incidencias')
    await usuario.click(await screen.findByRole('radio', { name: 'Resueltas' }))
    await usuario.click(await screen.findByRole('button', { name: /^Reclamo de la familia, Resueltas/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Reclamo de la familia' })).toBeVisible()
    expect(screen.getByText('La familia escribió que la caja llegó abierta.')).toBeVisible()
    expect(screen.getByText('Se revisó con el comercio: los productos estaban completos.')).toBeVisible()
    expect(screen.queryByText(/ya no está disponible/)).toBeNull()
  })

  it('decisión 471: sin la clave de las notas, «La nota ya no está disponible…» en vez de la nota y la resolución', async () => {
    const { api, usuario } = await abrir('/operacion/incidencias')
    api.consola.estado.incidencias.find((x) => x.id === ID.incidenciaResuelta)!.nota_disponible = false
    const escrito = vigilarAlmacenamiento()
    await usuario.click(await screen.findByRole('radio', { name: 'Resueltas' }))
    await usuario.click(await screen.findByRole('button', { name: /^Reclamo de la familia, Resueltas/ }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Reclamo de la familia' })).toBeVisible()
    const nota = screen.getByRole('region', { name: 'Nota' })
    expect(within(nota).getByText('La nota ya no está disponible: se borró con los datos de la persona.')).toBeVisible()
    expect(screen.queryByText('La familia escribió que la caja llegó abierta.')).toBeNull()
    expect(screen.queryByText('Se revisó con el comercio: los productos estaban completos.')).toBeNull()
    expect(screen.getByRole('heading', { level: 2, name: 'Cómo se resolvió' })).toBeVisible()
    expect(screen.getByText(/^Resuelta el \d{2}\/\d{2}\/\d{4} a las \d{2}:\d{2}\.$/)).toBeVisible()
    expect(escrito).toEqual([])
    expect(window.location.href).not.toMatch(/nota|borr/i)
  })
})

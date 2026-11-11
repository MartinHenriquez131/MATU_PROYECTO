// MATU-61: «Tu pedido» (especificación docs/diseno/matu-61-pedido.md v1.1, secciones 4, 7, 10 y 11).
// El carrito con la cantidad del U4, «Si falta» (RF-21), sacar, la entrega, «Ver el total», el
// permiso de los pedidos, el vacío, los errores, los roles y cancelar. Textos de la sección 15 tal
// cual. Solo datos sintéticos.
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { fijarGrupo } from '../src/compartido/api/sesion'
import { PantallaPedido } from '../src/familia/Pedido'
import { DECLARACION_PEDIDOS, huellaDe } from '../src/familia/textosPedido'
import { familiaFalsa } from './familiaFalsa'
import {
  ALMACEN,
  apiPedido,
  BODEGA,
  borrador,
  confirmado,
  enOrden,
  linea,
  NO_ENCONTRADO,
  OFERTAS,
  PANAL,
  PEDIDO_ID,
  persona,
  PERSONA_ID,
  problema,
  TOALLITAS,
  type Respuesta,
  conRegionesGlobales as conRegiones,
} from './pedidoFalso'

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

// jsdom no trae `showModal` ni `close`.
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})

let escrituras: string[] = []
beforeEach(() => {
  escrituras = []
  for (const s of [localStorage, sessionStorage]) s.clear()
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
  fijarGrupo('3c9d4e20-0000-4000-8000-0000000000g1')
})

function abrir(rol: Rol = 'admin', cambios: Partial<ReturnType<typeof familiaFalsa>> = {}) {
  window.history.replaceState(null, '', '/insumos/pedido')
  const p = persona()
  const vista = rol === 'observador' ? { id: p.id, nombre: p.nombre } : rol === 'pagador' ? { id: p.id, nombre: p.nombre, direccion: p.direccion } : p
  contexto = familiaFalsa({ persona: vista, personas: [vista], personaId: PERSONA_ID, rol, capa3: true, intencionPedido: null, llegadaPedido: null, direccionDesdeGrupo: false, ...cambios } as never)
  return conRegiones(<PantallaPedido />)
}

const lineaDe = (nombre: string) => screen.getByRole('heading', { level: 2, name: nombre }).closest('li')!
const cargado = () => screen.findByRole('heading', { level: 2, name: 'Pañal adulto M x30' })

describe('Tu pedido: el carrito (7)', () => {
  it('cada línea con su producto, comercio ficticio, precio, cantidad, subtotal, «Si falta», retracto y «Sacar del pedido»', async () => {
    apiPedido({})
    abrir()
    await cargado()
    expect(screen.getByRole('heading', { level: 1, name: 'Tu pedido' })).toBeVisible()
    expect(screen.getByText('Revisa los productos y cuántos quieres. Antes de pagar confirmamos que haya.')).toBeVisible()
    const panal = within(lineaDe('Pañal adulto M x30'))
    expect(panal.getByText('Paquete de 30 unidades')).toBeVisible()
    expect(panal.getByText('De Almacén El Ejemplo (comercio ficticio)')).toBeVisible()
    expect(panal.getByText('$12.990').className).not.toMatch(/turquesa/)
    expect(panal.getByText('cada uno')).toBeVisible()
    expect(panal.getByText('Precio de ejemplo · IVA incluido')).toBeVisible()
    // 7.5: el campo se nombra con su etiqueta y el producto, y los − y + llevan el producto.
    const campo = panal.getByRole('textbox', { name: 'Cantidad Pañal adulto M x30' })
    expect(campo).toHaveValue('2')
    expect(campo).toHaveAttribute('inputmode', 'numeric')
    expect(panal.getByRole('button', { name: 'Quitar uno: Pañal adulto M x30' })).toBeVisible()
    expect(panal.getByRole('button', { name: 'Agregar uno: Pañal adulto M x30' })).toBeVisible()
    expect(panal.getByText('envases de 30 unidades')).toBeVisible()
    expect(panal.getByText('Subtotal:').closest('p')).toHaveTextContent('Subtotal: $25.980')
    // 7.6 y O9: el grupo con el producto, descrito por «Nunca lo cambiamos…», con «Buscarlo en otro comercio» por omisión.
    const grupo = panal.getByRole('group', { name: 'Si falta este producto Pañal adulto M x30' })
    expect(grupo).toHaveAccessibleDescription('Nunca lo cambiamos por otra marca ni por otro producto.')
    expect(within(grupo).getByRole('radio', { name: /Buscarlo en otro comercio/ })).toBeChecked()
    expect(within(grupo).getByRole('radio', { name: 'Sacarlo del pedido y devolverme su precio' })).not.toBeChecked()
    expect(within(grupo).getByText('El mismo producto. Pagas lo mismo.').className).toMatch(/\btext-base\b/)
    expect(screen.getAllByText('Nunca lo cambiamos por otra marca ni por otro producto.')).toHaveLength(1)
    // C2: el retracto en cada línea, con letra igual a la del precio.
    const retracto = panal.getByText('Derecho a retracto:').closest('p')!
    expect(retracto).toHaveTextContent('Derecho a retracto: tienes 10 días desde que lo recibes. No aplica si abres el sello del producto.')
    expect(retracto.className).toMatch(/\btext-lg\b/)
    expect(panal.getByText('$12.990').className).toMatch(/\btext-lg\b/)
    expect(panal.getByRole('button', { name: 'Sacar del pedido: Pañal adulto M x30' })).toHaveTextContent('Sacar del pedido')
  })

  it('la entrega, «Productos» con la suma de la pantalla, sin envío ni total, y «Ver el total» como único macizo', async () => {
    apiPedido({})
    abrir()
    await cargado()
    const entrega = screen.getByRole('region', { name: 'Entrega' })
    expect(within(entrega).getByText('Los Aromos 123, depto 4, La Reina')).toBeVisible()
    expect(within(entrega).getByText('Portón verde')).toBeVisible()
    expect(within(entrega).getByRole('button', { name: 'Cambiar dirección' })).toBeVisible()
    expect(within(entrega).getByText('+56 9 •••• ••37')).toBeVisible()
    expect(within(entrega).getByText('(tu celular)')).toBeVisible()
    expect(within(entrega).getByText('Llega entre 24 y 48 horas hábiles.')).toBeVisible()
    expect(screen.getByText('Productos:').closest('p')).toHaveTextContent('Productos: $30.270')
    expect(screen.getByText('El envío y el total los ves al confirmar que haya cada producto.')).toBeVisible()
    // JC5 y JC-IVA: sin envío ni total antes de confirmar, e «IVA» solo en «Precio de ejemplo · IVA incluido».
    const texto = document.body.textContent ?? ''
    expect(texto).not.toMatch(/Total|Envío|\$3\.990/)
    expect(texto.match(/IVA/g)).toHaveLength(2)
    expect(texto).not.toMatch(/con IVA|más IVA|\+ IVA|stock|carrito|carro\b|reserva|monto real|estimado|aprox\./i)
    // 13.1: un solo macizo turquesa, «Ver el total».
    const macizos = screen.getAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className))
    expect(macizos).toEqual([screen.getByRole('button', { name: 'Ver el total' })])
    expect(screen.getAllByText('Precios de ejemplo.')).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Cancelar pedido' })).toBeVisible()
  })

  it('U4: escribir reemplaza todo el número, el subtotal cambia al tiro y la cantidad se guarda sola, con If-Match y las ofertas', async () => {
    const cantidad = (p: { cuerpo: unknown }) => (p.cuerpo as { lineas: { cantidad: number }[] }).lineas[0].cantidad
    const api = apiPedido({ 'PUT /lineas$': (p) => ({ status: 200, cuerpo: { ...borrador({ lineas: [linea(PANAL, ALMACEN, cantidad(p), 12990), linea(TOALLITAS, BODEGA, 1, 4290)] }), etag: 'p2' } }) })
    abrir()
    await cargado()
    const campo = screen.getByRole<HTMLInputElement>('textbox', { name: 'Cantidad Pañal adulto M x30' })
    await userEvent.click(campo)
    expect(campo.selectionStart).toBe(0)
    expect(campo.selectionEnd).toBe(1)
    await userEvent.keyboard('3')
    expect(campo).toHaveValue('3')
    expect(within(lineaDe('Pañal adulto M x30')).getByText('Subtotal:').closest('p')).toHaveTextContent('Subtotal: $38.970')
    expect(screen.getByText('Productos:').closest('p')).toHaveTextContent('Productos: $43.260')
    await waitFor(() => expect(api.escrituras()).toHaveLength(1), { timeout: 2000 })
    const put = api.escrituras()[0]
    expect(put.ruta).toBe(`/v1/pedidos/${PEDIDO_ID}/lineas`)
    expect(put.cabeceras['If-Match']).toBe('p1')
    expect(put.cuerpo).toEqual({ lineas: [{ oferta_id: OFERTAS.panalAlmacen, cantidad: 3 }, { oferta_id: OFERTAS.toallitasBodega, cantidad: 1 }] })
  })

  it('el + dos veces suma dos, y el − no baja de 1', async () => {
    apiPedido({ 'PUT /lineas$': { status: 200, cuerpo: { ...borrador(), etag: 'p2' } } })
    abrir()
    await cargado()
    const toallitas = within(lineaDe('Toallitas húmedas x80'))
    await userEvent.click(toallitas.getByRole('button', { name: 'Agregar uno: Toallitas húmedas x80' }))
    await userEvent.click(toallitas.getByRole('button', { name: 'Agregar uno: Toallitas húmedas x80' }))
    expect(toallitas.getByRole('textbox')).toHaveValue('3')
    for (let i = 0; i < 4; i++) await userEvent.click(toallitas.getByRole('button', { name: 'Quitar uno: Toallitas húmedas x80' }))
    expect(toallitas.getByRole('textbox')).toHaveValue('1')
  })

  it('fuera de rango al salir del campo: «Escribe una cantidad de 1 a 99.», y no se envía', async () => {
    const api = apiPedido({})
    abrir()
    await cargado()
    const campo = screen.getByRole('textbox', { name: 'Cantidad Pañal adulto M x30' })
    await userEvent.clear(campo)
    await userEvent.tab()
    expect(campo).toBeInvalid()
    expect(campo).toHaveAccessibleDescription('Escribe una cantidad de 1 a 99.')
    await new Promise((r) => setTimeout(r, 700))
    expect(api.escrituras()).toEqual([])
  })

  it('si no se pudo guardar la cantidad, vuelve a la guardada con su error', async () => {
    apiPedido({ 'PUT /lineas$': problema(503, 'servicio-no-disponible') })
    abrir()
    await cargado()
    const campo = screen.getByRole('textbox', { name: 'Cantidad Pañal adulto M x30' })
    await userEvent.click(campo)
    await userEvent.keyboard('5')
    await userEvent.tab()
    await waitFor(() => expect(campo).toHaveValue('2'))
    expect(campo).toHaveAccessibleDescription('No pudimos guardar la cantidad. Revisa tu conexión y vuelve a intentarlo.')
    expect(screen.queryByText('Texto de la API que no se muestra')).toBeNull()
  })

  it('«Si falta» se guarda al cambiar con PUT …/reglas-faltante; si falla, vuelve la de antes', async () => {
    const api = apiPedido({ 'PUT /reglas-faltante$': enOrden({ status: 200, cuerpo: { ...borrador({ lineas: [linea(PANAL, ALMACEN, 2, 12990, { regla_faltante: 'quitar' }), linea(TOALLITAS, BODEGA, 1, 4290)] }), etag: 'p2' } }, problema(500, 'error-interno')) })
    abrir()
    await cargado()
    const panal = within(screen.getByRole('group', { name: 'Si falta este producto Pañal adulto M x30' }))
    await userEvent.click(panal.getByRole('radio', { name: 'Sacarlo del pedido y devolverme su precio' }))
    await waitFor(() => expect(api.escrituras()).toHaveLength(1))
    expect(api.escrituras()[0].cuerpo).toEqual({ reglas: [{ producto_id: PANAL.id, accion: 'quitar' }, { producto_id: TOALLITAS.id, accion: 'otro_comercio' }] })
    expect(api.escrituras()[0].cabeceras['If-Match']).toBe('p1')
    expect(panal.getByRole('radio', { name: 'Sacarlo del pedido y devolverme su precio' })).toBeChecked()

    const toallitas = within(screen.getByRole('group', { name: 'Si falta este producto Toallitas húmedas x80' }))
    await userEvent.click(toallitas.getByRole('radio', { name: 'Sacarlo del pedido y devolverme su precio' }))
    expect(await toallitas.findByText('No pudimos guardar qué hacer si falta. Revisa tu conexión y vuelve a intentarlo.')).toBeVisible()
    expect(toallitas.getByRole('radio', { name: /Buscarlo en otro comercio/ })).toBeChecked()
  })

  it('7.7: «Sacar del pedido» sin confirmación, se anuncia y el foco va a la cantidad de la siguiente', async () => {
    const api = apiPedido({ 'PUT /lineas$': { status: 200, cuerpo: { ...borrador({ lineas: [linea(TOALLITAS, BODEGA, 1, 4290)] }), etag: 'p2' } } })
    const { amable } = abrir()
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Sacar del pedido: Pañal adulto M x30' }))
    await waitFor(() => expect(screen.queryByRole('heading', { level: 2, name: 'Pañal adulto M x30' })).toBeNull())
    expect(api.escrituras()[0].cuerpo).toEqual({ lineas: [{ oferta_id: OFERTAS.toallitasBodega, cantidad: 1 }] })
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(amable).toHaveTextContent('Sacamos «Pañal adulto M x30» del pedido.'))
    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Cantidad Toallitas húmedas x80' })).toHaveFocus())
  })

  it('si no se pudo sacar, la línea se queda con su error', async () => {
    apiPedido({ 'PUT /lineas$': problema(500, 'error-interno') })
    abrir()
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Sacar del pedido: Pañal adulto M x30' }))
    expect(await screen.findByText('No pudimos sacarlo. Revisa tu conexión y vuelve a intentarlo.')).toBeVisible()
    expect(screen.getByRole('heading', { level: 2, name: 'Pañal adulto M x30' })).toBeVisible()
  })

  it('412: «Este pedido cambió mientras lo revisabas…» y se ve lo de la otra persona', async () => {
    const actual = { ...borrador({ lineas: [linea(PANAL, ALMACEN, 6, 12990), linea(TOALLITAS, BODEGA, 1, 4290)] }), etag: 'p9' }
    apiPedido({ 'PUT /lineas$': problema(412, 'version-desactualizada', { actual }) })
    const { amable } = abrir()
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Agregar uno: Pañal adulto M x30' }))
    await userEvent.tab()
    await waitFor(() => expect(amable).toHaveTextContent('Este pedido cambió mientras lo revisabas. Te mostramos cómo quedó.'))
    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Cantidad Pañal adulto M x30' })).toHaveValue('6'))
  })
})

describe('«Ver el total» (7.9)', () => {
  it('sin dirección: el error bajo «Dirección», el foco en «Agregar la dirección», y no se confirma', async () => {
    const api = apiPedido({})
    window.history.replaceState(null, '', '/insumos/pedido')
    contexto = familiaFalsa({ persona: persona(null), personas: [persona(null)], personaId: PERSONA_ID, rol: 'admin', capa3: true } as never)
    conRegiones(<PantallaPedido />)
    await cargado()
    expect(screen.getByText('Todavía no hay una dirección de entrega.')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Ver el total' }))
    expect(screen.getByText('Agrega la dirección de entrega para ver el total.')).toBeVisible()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Agregar la dirección' })).toHaveFocus())
    expect(api.escrituras()).toEqual([])
  })

  it('confirma con Idempotency-Key, sin teléfono escrito, y lleva al resumen', async () => {
    const api = apiPedido({ 'POST /confirmar$': { status: 200, cuerpo: confirmado() } })
    abrir()
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Ver el total' }))
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido/resumen'))
    const post = api.escrituras()[0]
    expect(post.ruta).toBe(`/v1/pedidos/${PEDIDO_ID}/confirmar`)
    expect(String(post.cabeceras['Idempotency-Key'])).toMatch(/^[A-Za-z0-9_-]{16,64}$/)
    expect(post.cuerpo).toEqual({})
    expect(await screen.findByRole('heading', { level: 1, name: 'Antes de pagar' })).toBeVisible()
  })

  it('con un teléfono escrito, viaja en `confirmar` y nunca se guarda en el navegador', async () => {
    const api = apiPedido({ 'POST /confirmar$': { status: 200, cuerpo: confirmado() } })
    const { amable } = abrir()
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar teléfono' }))
    const tel = screen.getByRole('textbox', { name: 'Teléfono de contacto' })
    expect(tel).toHaveAccessibleDescription('Para que quien entrega pueda avisarte. Si es el de otra persona, avísale.')
    await userEvent.type(tel, '12345')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar el teléfono' }))
    expect(tel).toHaveAccessibleDescription(/Escribe un celular de Chile, por ejemplo \+56 9 5555 0137\./)
    await userEvent.clear(tel)
    await userEvent.type(tel, '+56 9 5555 0177')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar el teléfono' }))
    await waitFor(() => expect(amable).toHaveTextContent('Guardamos el teléfono.'))
    expect(screen.getByText('+56 9 5555 0177')).toBeVisible()
    expect(screen.queryByText('(tu celular)')).toBeNull()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Cambiar teléfono' })).toHaveFocus())
    await userEvent.click(screen.getByRole('button', { name: 'Ver el total' }))
    await waitFor(() => expect(api.escrituras()).toHaveLength(1))
    expect(api.escrituras()[0].cuerpo).toEqual({ telefono_contacto: '+56 9 5555 0177' })
    expect(escrituras).toEqual([])
    expect(window.location.href).not.toContain('5555')
  })

  it.each<[string, Respuesta, string]>([
    ['sin conexión', problema(503, 'servicio-no-disponible'), 'No pudimos confirmar el total. Revisa tu conexión y vuelve a intentarlo. Tu pedido sigue aquí.'],
    ['nada disponible', problema(409, 'nada-disponible'), 'Ahora ningún comercio tiene estos productos. No hay nada que pagar. Tu pedido sigue aquí para intentarlo más tarde.'],
  ])('%s: el aviso sobre el botón, sin rojo, y el carrito queda igual', async (_, r, texto) => {
    apiPedido({ 'POST /confirmar$': r })
    const { urgente } = abrir()
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Ver el total' }))
    await waitFor(() => expect(urgente).toHaveTextContent(texto))
    expect(window.location.pathname).toBe('/insumos/pedido')
    expect(screen.getByRole('heading', { level: 2, name: 'Pañal adulto M x30' })).toBeVisible()
  })

  it('409 sin-direccion: el mismo error de la dirección', async () => {
    apiPedido({ 'POST /confirmar$': problema(409, 'sin-direccion') })
    abrir()
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Ver el total' }))
    expect(await screen.findByText('Agrega la dirección de entrega para ver el total.')).toBeVisible()
  })
})

describe('Con el total confirmado (7.9)', () => {
  it('el carrito sin controles, con su nota, «Ver el total» que no vuelve a confirmar y «Cambiar el pedido»', async () => {
    const api = apiPedido({ 'POST /cambiar$': { status: 200, cuerpo: { ...borrador(), etag: 'p3' } } }, { pedido: confirmado() })
    abrir()
    await cargado()
    expect(screen.getByText('Ya confirmaste el total. Para cambiar algo, toca «Cambiar el pedido».')).toBeVisible()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByRole('radio')).toBeNull()
    expect(screen.queryByRole('button', { name: /Sacar del pedido/ })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Cambiar dirección' })).toBeNull()
    expect(screen.getAllByText('Si falta: lo buscamos en otro comercio.')).toHaveLength(2)
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar el pedido' }))
    expect(await screen.findByRole('textbox', { name: 'Cantidad Pañal adulto M x30' })).toBeVisible()
    // La nota se ve y se anuncia (la región viva repite su texto).
    expect(screen.getAllByText('Ya puedes cambiar tu pedido. Cuando termines, toca «Ver el total» para confirmarlo de nuevo.')[0]).toBeVisible()
    expect(api.escrituras().map((x) => `${x.metodo} ${x.ruta}`)).toEqual([`POST /v1/pedidos/${PEDIDO_ID}/cambiar`])
  })
})

describe('El permiso de los pedidos (4)', () => {
  it('admin sin la autorización: «Antes de pedir, un permiso»; al autorizar envía la huella y agrega lo que quería del catálogo', async () => {
    let autorizada = false
    let creado: ReturnType<typeof borrador> | null = null
    const api = apiPedido(
      {
        'GET /consentimientos$': () => ({ status: 200, cuerpo: (autorizada ? { autorizaciones: [{ finalidad: 'despacho', estado: 'vigente', id: 'x', otorgado_en: '2026-11-11T15:00:00Z', revision_vence_en: null, revocado_en: null, borrado_en: null, borrada: false }] } : { autorizaciones: [{ finalidad: 'despacho', estado: 'sin_autorizar', id: null, otorgado_en: null, revision_vence_en: null, revocado_en: null, borrado_en: null, borrada: false }] }) }),
        'POST /consentimientos$': () => ((autorizada = true), { status: 201, cuerpo: {} }),
        'POST /pedidos$': () => ((creado = borrador({ lineas: [linea(PANAL, ALMACEN, 1, 12990)] })), { status: 201, cuerpo: creado }),
        'GET /pedido-en-curso$': () => (creado ? { status: 200, cuerpo: creado } : NO_ENCONTRADO),
      },
      { pedido: null },
    )
    const fijar = vi.fn()
    window.history.replaceState(null, '', '/insumos/pedido')
    contexto = familiaFalsa({
      persona: persona(),
      personas: [persona()],
      personaId: PERSONA_ID,
      rol: 'cuidador',
      capa3: true,
      fijar,
      intencionPedido: { personaId: PERSONA_ID, desde: 'catalogo', agregar: [{ producto_id: PANAL.id, oferta_id: OFERTAS.panalAlmacen, cantidad: 1, nombre: PANAL.nombre, deLista: null }], fuera: [] },
    } as never)
    conRegiones(<PantallaPedido />)
    expect(await screen.findByRole('heading', { level: 1, name: 'Antes de pedir, un permiso' })).toBeVisible()
    expect(screen.getByText('Para pedir desde MATU, primero autoriza los pedidos. Sin esta autorización igual puedes imprimir o compartir la lista.')).toBeVisible()
    expect(screen.getByText('Es un permiso aparte del de su ficha y del de sus insumos.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Volver al catálogo' })).toBeVisible()
    expect(screen.getByRole('radio', { name: /Cuido a esta persona, pero no soy su representante legal/ })).toBeChecked()
    expect(screen.getByText(DECLARACION_PEDIDOS.cuidador_de_hecho)).toBeVisible()
    // La validación de MATU-36: sin marcar el aviso no se envía.
    await userEvent.click(screen.getByRole('button', { name: 'Autorizar los pedidos' }))
    expect(screen.getByText('Marca que leíste el aviso para seguir.')).toBeVisible()
    await userEvent.click(screen.getByRole('checkbox', { name: 'Leí el aviso y lo acepto' }))
    await userEvent.click(screen.getByRole('button', { name: 'Autorizar los pedidos' }))
    expect((await screen.findAllByText('Pedidos autorizados. Agregamos «Pañal adulto M x30» a tu pedido.'))[0]).toBeVisible()
    const post = api.escrituras().find((x) => /consentimientos$/.test(x.ruta))!
    expect(post.cuerpo).toMatchObject({ finalidad: 'despacho', calidad_otorgante: 'cuidador_de_hecho', huella_declaracion: await huellaDe(DECLARACION_PEDIDOS.cuidador_de_hecho) })
    expect(api.escrituras().find((x) => /\/pedidos$/.test(x.ruta))!.cuerpo).toEqual({ lineas: [{ oferta_id: OFERTAS.panalAlmacen, cantidad: 1 }] })
    expect(fijar).toHaveBeenCalledWith({ intencionPedido: null })
    expect(await screen.findByRole('heading', { level: 2, name: 'Pañal adulto M x30' })).toBeVisible()
  })

  it('pagador sin la autorización ni pedido: «Falta la autorización de pedidos…», sin botones', async () => {
    apiPedido({}, { pedido: null, despacho: 'sin_autorizar' })
    abrir('pagador')
    expect(await screen.findByText('Falta la autorización de pedidos para María.')).toBeVisible()
    expect(screen.getByText('Sin ella no se pueden hacer pedidos desde MATU. Pídele a quien administra el grupo o a quien cuida a María que la dé.')).toBeVisible()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('por renovar (4.5): admin con «Renovar la autorización», que muestra el permiso en el lugar', async () => {
    apiPedido({}, { despacho: 'revision_vencida' })
    abrir()
    expect(await screen.findByText('Hay que renovar la autorización de los pedidos de María.')).toBeVisible()
    expect(screen.getByText(/Se renueva una vez al año. Mientras tanto no se pueden hacer pedidos, pero tu pedido sigue guardado./)).toBeVisible()
    expect(document.querySelector('[role="alert"][data-aviso]')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Renovar la autorización' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Antes de pedir, un permiso' })).toBeVisible()
  })

  it('por renovar, el pagador: pide que la renueve, sin botón', async () => {
    apiPedido({}, { despacho: 'revision_vencida' })
    abrir('pagador')
    expect(await screen.findByText('Pídele a quien administra el grupo o a quien cuida a María que la renueve.')).toBeVisible()
    expect(screen.queryByRole('button')).toBeNull()
  })
})

describe('Vacío, errores y roles (7.2, 7.10 y 11)', () => {
  it('vacío para admin: la frase y dos salidas, sin macizo', async () => {
    apiPedido({}, { pedido: null })
    abrir()
    expect(await screen.findByText('Tu pedido está vacío. Agrega productos desde el catálogo o desde tu lista de insumos.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Ir al catálogo' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Ir a la lista de insumos' })).toBeVisible()
    expect(screen.getAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className))).toEqual([])
    expect(screen.queryByText('Precios de ejemplo.')).toBeNull()
    expect(screen.queryByText('Ver el total')).toBeNull()
  })

  it('vacío para el pagador: «Todavía no hay un pedido para María.», sin acciones', async () => {
    apiPedido({}, { pedido: null })
    abrir('pagador')
    expect(await screen.findByText('Todavía no hay un pedido para María.')).toBeVisible()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('la capa 3 apagada: «El pedido no está disponible por ahora.», sin reintento', async () => {
    apiPedido({ 'GET ^/v1/catalogo$': NO_ENCONTRADO })
    abrir()
    expect(await screen.findByText('El pedido no está disponible por ahora.')).toBeVisible()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('sin conexión al cargar: el texto en la región urgente y «Volver a intentar», sin un pedido viejo', async () => {
    let falla = true
    apiPedido({ 'GET /pedido-en-curso$': () => (falla ? problema(503, 'servicio-no-disponible') : { status: 200, cuerpo: borrador() }) })
    const { urgente } = abrir()
    await waitFor(() => expect(urgente).toHaveTextContent('No pudimos traer tu pedido. Revisa tu conexión e inténtalo de nuevo.'))
    expect(screen.queryByText('Pañal adulto M x30')).toBeNull()
    falla = false
    await userEvent.click(screen.getByRole('button', { name: 'Volver a intentar' }))
    expect(await cargado()).toBeVisible()
  })

  it('el pagador ve el carrito sin controles, sin teléfono, y «Ver el resumen» con el total confirmado', async () => {
    apiPedido({}, { pedido: confirmado() })
    abrir('pagador')
    await cargado()
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByRole('radio')).toBeNull()
    expect(screen.queryByRole('button', { name: /Sacar|Cancelar pedido|Ver el total|Cambiar/ })).toBeNull()
    expect(screen.getByText('Quien administra el grupo o quien cuida a María puede cambiar el pedido y ver el total.')).toBeVisible()
    expect(within(lineaDe('Pañal adulto M x30')).getByText('envases de 30 unidades').closest('p')).toHaveTextContent('2 envases de 30 unidades')
    const entrega = screen.getByRole('region', { name: 'Entrega' })
    expect(within(entrega).getByText('Los Aromos 123, depto 4, La Reina')).toBeVisible()
    expect(within(entrega).queryByText('Teléfono de contacto')).toBeNull()
    expect(screen.getByRole('button', { name: 'Ver el resumen' })).toBeVisible()
  })

  it('el observador no ve la entrega', async () => {
    apiPedido({})
    abrir('observador')
    await cargado()
    expect(screen.queryByRole('region', { name: 'Entrega' })).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('nada del pedido en el navegador, la URL ni el historial', async () => {
    apiPedido({})
    abrir()
    await cargado()
    expect(escrituras).toEqual([])
    expect(window.location.pathname).toBe('/insumos/pedido')
    expect(window.location.search + window.location.hash).toBe('')
    expect(window.history.state).toBeNull()
  })
})

describe('Cancelar (10)', () => {
  it('el diálogo con el foco en el título; «Seguir con el pedido» devuelve el foco', async () => {
    const api = apiPedido({})
    abrir('cuidador')
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar pedido' }))
    const dialogo = screen.getByRole('dialog', { name: '¿Cancelar este pedido?' })
    expect(dialogo).toHaveAccessibleDescription('No tiene costo.')
    expect(within(dialogo).getByRole('heading', { name: '¿Cancelar este pedido?' })).toHaveFocus()
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Seguir con el pedido' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Cancelar pedido' })).toHaveFocus())
    expect(api.escrituras()).toEqual([])
  })

  it('al cancelar: queda vacío con «Cancelamos el pedido. No se cobró nada.»', async () => {
    const api = apiPedido({ 'POST /cancelar$': { status: 200, cuerpo: { ...borrador(), estado: 'cancelado' } } })
    const { amable } = abrir('cuidador')
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar pedido' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancelar pedido' }))
    await waitFor(() => expect(amable).toHaveTextContent('Cancelamos el pedido. No se cobró nada.'))
    expect(screen.getByText('Tu pedido está vacío. Agrega productos desde el catálogo o desde tu lista de insumos.')).toBeVisible()
    expect(String(api.escrituras()[0].cabeceras['Idempotency-Key'])).toMatch(/^[A-Za-z0-9_-]{16,64}$/)
  })

  it('sin conexión: el error dentro del diálogo y todo sigue como estaba', async () => {
    apiPedido({ 'POST /cancelar$': problema(503, 'servicio-no-disponible') })
    abrir()
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar pedido' }))
    const dialogo = screen.getByRole('dialog')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    expect(await within(dialogo).findByText('No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.')).toBeVisible()
    await act(async () => {})
    expect(screen.getByRole('heading', { level: 2, name: 'Pañal adulto M x30' })).toBeInTheDocument()
  })

  it('ya cancelado por otra persona (409): el vacío con su nota, sin error', async () => {
    apiPedido({ 'POST /cancelar$': problema(409, 'estado-pedido', { estado: 'cancelado' }) })
    const { amable } = abrir()
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar pedido' }))
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancelar pedido' }))
    await waitFor(() => expect(amable).toHaveTextContent('Otra persona de tu grupo ya canceló este pedido.'))
  })
})

describe('Al llegar desde la lista (6.4)', () => {
  it('la nota con sus párrafos y «En tu lista: …» en la línea que vino de la lista', async () => {
    apiPedido({})
    abrir('admin', {
      llegadaPedido: {
        personaId: PERSONA_ID,
        tono: 'ok',
        parrafos: ['Agregamos 2 productos de tu lista a tu pedido.', 'Bolsas de basura no está en el catálogo y no va en el pedido.'],
        deLista: { [PANAL.id]: '6 envases de 20 unidades' },
      },
    } as never)
    await cargado()
    expect(screen.getByText('Agregamos 2 productos de tu lista a tu pedido.')).toBeVisible()
    expect(screen.getByText('Bolsas de basura no está en el catálogo y no va en el pedido.')).toBeVisible()
    expect(within(lineaDe('Pañal adulto M x30')).getByText('En tu lista: 6 envases de 20 unidades')).toBeVisible()
    expect(within(lineaDe('Toallitas húmedas x80')).queryByText(/En tu lista/)).toBeNull()
  })
})

describe('Revisión visual de MATU-61 en el carrito', () => {
  it('P3-2: el campo del teléfono se nombra con su título, sin una etiqueta visible que lo repita', async () => {
    apiPedido({})
    abrir()
    await cargado()
    await userEvent.click(screen.getByRole('button', { name: 'Cambiar teléfono' }))
    const tel = screen.getByRole('textbox', { name: 'Teléfono de contacto' })
    const titulo = screen.getByRole('heading', { level: 3, name: 'Teléfono de contacto' })
    expect(tel).toHaveAttribute('aria-labelledby', titulo.id)
    expect(tel).toHaveAccessibleDescription('Para que quien entrega pueda avisarte. Si es el de otra persona, avísale.')
    // «Teléfono de contacto» se lee una sola vez: el título, sin `<label>` aparte.
    expect(screen.getAllByText('Teléfono de contacto')).toEqual([titulo])
    expect((tel as HTMLInputElement).labels).toHaveLength(0)
  })

  it.each<[string, () => ReturnType<typeof confirmado>]>([
    ['confirmado', () => confirmado()],
    ['vencido', () => confirmado({ estado: 'vencido' })],
  ])('P3-3: con el total %s no se ve «El envío y el total los ves al confirmar…»', async (_, pedido) => {
    apiPedido({}, { pedido: pedido() })
    abrir()
    await cargado()
    expect(screen.getByText('Productos:')).toBeVisible()
    expect(screen.queryByText('El envío y el total los ves al confirmar que haya cada producto.')).toBeNull()
  })
})

describe('Revisión visual de MATU-61: el foco al llegar al permiso (P2-2)', () => {
  it.each<'catalogo' | 'lista'>(['catalogo', 'lista'])('desde %s, el h1 «Antes de pedir, un permiso» recibe el foco que tenía el de «Cargando»', async (desde) => {
    apiPedido({ 'GET /consentimientos$': { status: 200, cuerpo: { autorizaciones: [{ finalidad: 'despacho', estado: 'sin_autorizar', id: null, otorgado_en: null, revision_vence_en: null, revocado_en: null, borrado_en: null, borrada: false }] } } }, { pedido: null })
    abrir('admin', {
      intencionPedido: { personaId: PERSONA_ID, desde, agregar: [{ producto_id: PANAL.id, oferta_id: OFERTAS.panalAlmacen, cantidad: 1, nombre: PANAL.nombre, deLista: desde === 'lista' ? '2 paquetes' : null }], fuera: [] },
    } as never)
    // La regla de las rutas pone el foco en el h1 que está a la vista: el de «Cargando».
    screen.getByRole('heading', { level: 1, name: 'Tu pedido' }).focus()
    const h1 = await screen.findByRole('heading', { level: 1, name: 'Antes de pedir, un permiso' })
    await waitFor(() => expect(h1).toHaveFocus())
  })
})

describe('Decisión 222: la línea se reenvía con su propio oferta_id', () => {
  it('una línea cuya oferta ya no está en el catálogo se guarda igual, con su oferta_id, sin buscarla en el catálogo', async () => {
    const RETIRADA = '3c9d4e20-0000-4000-8000-0000000000o9'
    const lineas = (n: number) => [linea(PANAL, BODEGA, n, 13490, { oferta_id: RETIRADA }), linea(TOALLITAS, BODEGA, 1, 4290)]
    const api = apiPedido({ 'PUT /lineas$': { status: 200, cuerpo: { ...borrador({ lineas: lineas(4) }), etag: 'p2' } } }, { pedido: borrador({ lineas: lineas(2) }) })
    abrir()
    await cargado()
    const campo = screen.getByRole<HTMLInputElement>('textbox', { name: 'Cantidad Pañal adulto M x30' })
    await userEvent.click(campo)
    await userEvent.keyboard('4')
    await waitFor(() => expect(api.escrituras()).toHaveLength(1), { timeout: 2000 })
    expect(api.escrituras()[0].cuerpo).toEqual({ lineas: [{ oferta_id: RETIRADA, cantidad: 4 }, { oferta_id: OFERTAS.toallitasBodega, cantidad: 1 }] })
    expect(within(lineaDe('Pañal adulto M x30')).queryByText('No pudimos guardar la cantidad. Revisa tu conexión y vuelve a intentarlo.')).toBeNull()
  })
})

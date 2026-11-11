// MATU-61: «Agregar al pedido» en el catálogo (especificación 5) y «Pedir estos productos» en la lista
// (6, D10, O3 y O4). Solo admin y cuidador con la capa 3, solo en los comercios con «Hay», sin la
// autorización a pedirla con la intención en memoria, y la lista convertida a envases del catálogo.
// Solo datos sintéticos.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { fijarGrupo } from '../src/compartido/api/sesion'
import { Catalogo } from '../src/familia/Catalogo'
import { ListaDeInsumos } from '../src/familia/ListaInsumos'
import { familiaFalsa } from './familiaFalsa'
import { ALMACEN, apiPedido, borrador, BODEGA, conRegionesGlobales, linea, NO_ENCONTRADO, OFERTAS, PANAL, PERSONA_ID, persona, problema, TOALLITAS } from './pedidoFalso'

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

let escrituras: string[] = []
beforeEach(() => {
  escrituras = []
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
  fijarGrupo('3c9d4e20-0000-4000-8000-0000000000g1')
})

function abrirCatalogo(rol: Rol = 'admin') {
  window.history.replaceState(null, '', '/insumos/catalogo')
  const fijar = vi.fn()
  contexto = familiaFalsa({ persona: persona(), personaId: PERSONA_ID, rol, capa3: true, fijar } as never)
  return { ...conRegionesGlobales(<Catalogo />), fijar }
}
const tarjeta = (nombre: string) => within(screen.getByRole('heading', { level: 3, name: nombre }).closest('li')!)
const cargado = () => screen.findByRole('heading', { level: 3, name: PANAL.nombre })

describe('El catálogo: «Agregar al pedido» (5)', () => {
  it('admin: solo en los comercios con «Hay», secundario, con el producto y el comercio en el nombre accesible', async () => {
    apiPedido({}, { pedido: null })
    abrirCatalogo()
    await cargado()
    const panal = tarjeta(PANAL.nombre)
    const boton = await panal.findByRole('button', { name: 'Agregar al pedido: Pañal adulto M x30, de Almacén El Ejemplo' })
    expect(boton).toHaveTextContent('Agregar al pedido')
    expect(boton.className).not.toMatch(/\bbg-turquesa\b/)
    // La bodega no tiene pañales: sin botón; la bolsa no está en ningún comercio: sin botón.
    expect(panal.getAllByRole('button')).toHaveLength(1)
    expect(tarjeta('Bolsa colectora x10').queryByRole('button')).toBeNull()
    // 13.1: el catálogo sigue sin ningún macizo turquesa.
    expect(screen.getAllByRole('button').filter((b) => /\bbg-turquesa\b/.test(b.className))).toEqual([])
  })

  it.each<Rol>(['pagador', 'observador'])('%s: el catálogo de MATU-59, sin botones ni el pedido', async (rol) => {
    const api = apiPedido({}, { pedido: null })
    abrirCatalogo(rol)
    await screen.findByRole('heading', { level: 3, name: PANAL.nombre })
    expect(screen.queryByRole('button')).toBeNull()
    expect(api.pedidas.some((p) => /pedido/.test(p.ruta))).toBe(false)
  })

  it('al agregar: crea el borrador con 1 y la oferta, anuncia, y el foco va a «Ver tu pedido»', async () => {
    const api = apiPedido({ 'POST /pedidos$': { status: 201, cuerpo: borrador({ lineas: [linea(PANAL, ALMACEN, 1, 12990)] }) } }, { pedido: null })
    const { amable } = abrirCatalogo('cuidador')
    await cargado()
    await userEvent.click(await tarjeta(PANAL.nombre).findByRole('button', { name: /Agregar al pedido: Pañal/ }))
    await waitFor(() => expect(amable).toHaveTextContent('Agregamos «Pañal adulto M x30» a tu pedido.'))
    const post = api.escrituras()[0]
    expect(post.ruta).toBe(`/v1/personas-cuidadas/${PERSONA_ID}/pedidos`)
    expect(post.cuerpo).toEqual({ lineas: [{ oferta_id: OFERTAS.panalAlmacen, cantidad: 1 }] })
    expect(String(post.cabeceras['Idempotency-Key'])).toMatch(/^[A-Za-z0-9_-]{16,64}$/)
    const panal = tarjeta(PANAL.nombre)
    expect(panal.getByText('En tu pedido').closest('p')!.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-circle-check/)
    await waitFor(() => expect(panal.getByRole('link', { name: 'Ver tu pedido' })).toHaveFocus())
    expect(panal.queryByRole('button')).toBeNull()
    await userEvent.click(panal.getByRole('link', { name: 'Ver tu pedido' }))
    expect(window.location.pathname).toBe('/insumos/pedido')
    expect(escrituras).toEqual([])
  })

  it('con un pedido abierto, agrega a sus líneas con If-Match, y un producto que ya está no lleva botón', async () => {
    const actual = borrador({ lineas: [linea(TOALLITAS, BODEGA, 2, 4290)] })
    const api = apiPedido({ 'PUT /lineas$': { status: 200, cuerpo: { ...borrador({ lineas: [linea(TOALLITAS, BODEGA, 2, 4290), linea(PANAL, ALMACEN, 1, 12990)] }), etag: 'p2' } } }, { pedido: actual })
    abrirCatalogo()
    await cargado()
    const toallitas = tarjeta(TOALLITAS.nombre)
    expect(await toallitas.findByText('En tu pedido')).toBeVisible()
    expect(toallitas.queryByRole('button')).toBeNull()
    await userEvent.click(tarjeta(PANAL.nombre).getByRole('button', { name: /Agregar al pedido: Pañal/ }))
    await waitFor(() => expect(api.escrituras()).toHaveLength(1))
    expect(api.escrituras()[0].cabeceras['If-Match']).toBe('p1')
    expect(api.escrituras()[0].cuerpo).toEqual({ lineas: [{ oferta_id: OFERTAS.toallitasBodega, cantidad: 2 }, { oferta_id: OFERTAS.panalAlmacen, cantidad: 1 }] })
  })

  it('sin la autorización: guarda la intención en memoria y va a pedirla', async () => {
    apiPedido({ 'POST /pedidos$': problema(403, 'sin-autorizacion-pedidos', { finalidad: 'despacho' }) }, { pedido: null })
    const { fijar } = abrirCatalogo()
    await cargado()
    await userEvent.click(await tarjeta(PANAL.nombre).findByRole('button', { name: /Agregar al pedido: Pañal/ }))
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
    expect(fijar).toHaveBeenCalledWith({
      intencionPedido: { personaId: PERSONA_ID, desde: 'catalogo', agregar: [{ producto_id: PANAL.id, oferta_id: OFERTAS.panalAlmacen, cantidad: 1, nombre: PANAL.nombre, deLista: null }], fuera: [] },
    })
    expect(window.location.search + window.location.hash).toBe('')
    expect(escrituras).toEqual([])
  })

  it('sin conexión: el error bajo el botón', async () => {
    apiPedido({ 'POST /pedidos$': problema(503, 'servicio-no-disponible') }, { pedido: null })
    abrirCatalogo()
    await cargado()
    await userEvent.click(await tarjeta(PANAL.nombre).findByRole('button', { name: /Agregar al pedido: Pañal/ }))
    expect(await tarjeta(PANAL.nombre).findByText('No pudimos agregarlo. Revisa tu conexión y vuelve a intentarlo.')).toBeVisible()
  })
})

// ---------------------------------------------------------------- la lista

const itemLista = (perfil: string, nombre: string, unidad: string, sugeridas: number, envase: number | null, producto: string | null) => ({
  perfil_id: perfil,
  nombre,
  unidad,
  dias_restantes: 3,
  unidades_sugeridas: sugeridas,
  unidades_por_envase: envase,
  envases_sugeridos: envase ? Math.ceil(sugeridas / envase) : null,
  producto_id: producto,
})
const LISTA = {
  fecha: '2026-11-11',
  items: [
    itemLista('perfil-1', 'Pañal adulto talla M', 'unidad', 120, 20, PANAL.id),
    itemLista('perfil-2', 'Toallitas húmedas', 'unidad', 90, null, TOALLITAS.id),
    itemLista('perfil-3', 'Bolsas de basura', 'unidad', 30, null, null),
  ],
}

function abrirLista(rol: Rol = 'admin', capa3: boolean | null = true) {
  window.history.replaceState(null, '', '/insumos/lista')
  const fijar = vi.fn()
  contexto = familiaFalsa({ persona: persona(), personaId: PERSONA_ID, rol, capa3, fijar } as never)
  return { ...conRegionesGlobales(<ListaDeInsumos />), fijar }
}

describe('La lista: «Pedir estos productos» (6)', () => {
  it('un bloque propio después de los botones, secundario, con su frase', async () => {
    apiPedido({ 'GET /consumo/lista$': { status: 200, cuerpo: LISTA } })
    abrirLista()
    const boton = await screen.findByRole('button', { name: 'Pedir estos productos' })
    expect(boton.className).not.toMatch(/\bbg-turquesa\b/)
    expect(screen.getByText('Los productos de esta lista que están en el catálogo se pueden pedir con MATU. Antes de pagar ves el total.')).toBeVisible()
    expect(boton.parentElement!.className).toMatch(/border-t border-linea/)
    const copiar = screen.getByRole('button', { name: 'Copiar la lista' })
    expect(copiar.compareDocumentPosition(boton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it.each<[string, Rol, boolean | null]>([
    ['el pagador', 'pagador', true],
    ['el observador', 'observador', true],
    ['sin saber si la capa 3 está', 'admin', null],
    ['con la capa 3 apagada', 'admin', false],
  ])('no se ve para %s', async (_, rol, capa3) => {
    apiPedido({ 'GET /consumo/lista$': { status: 200, cuerpo: LISTA } })
    abrirLista(rol, capa3)
    await screen.findAllByText('Pañal adulto talla M')
    expect(screen.queryByRole('button', { name: 'Pedir estos productos' })).toBeNull()
  })

  it('pasa solo lo del catálogo, en envases del catálogo; lo que ya estaba queda con la cantidad de la lista, y nombra lo demás', async () => {
    const actual = borrador({ lineas: [linea(PANAL, ALMACEN, 1, 12990)] })
    const api = apiPedido(
      { 'GET /consumo/lista$': { status: 200, cuerpo: LISTA }, 'PUT /lineas$': { status: 200, cuerpo: { ...actual, etag: 'p2' } } },
      { pedido: actual },
    )
    const { fijar } = abrirLista('cuidador')
    await userEvent.click(await screen.findByRole('button', { name: 'Pedir estos productos' }))
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
    // 6 envases de 20 (120 unidades) son 4 paquetes de 30; 90 toallitas, 2 paquetes de 80.
    expect(api.escrituras()[0].cuerpo).toEqual({ lineas: [{ oferta_id: OFERTAS.panalAlmacen, cantidad: 4 }, { oferta_id: OFERTAS.toallitasBodega, cantidad: 2 }] })
    expect(fijar).toHaveBeenCalledWith({
      llegadaPedido: {
        personaId: PERSONA_ID,
        tono: 'ok',
        parrafos: ['Agregamos 2 productos de tu lista a tu pedido.', 'Pañal adulto M x30 ya estaba en tu pedido: dejamos la cantidad de la lista.', 'Bolsas de basura no está en el catálogo y no va en el pedido.'],
        deLista: { [PANAL.id]: '6 envases de 20 unidades', [TOALLITAS.id]: '90 unidades' },
      },
    })
    expect(escrituras).toEqual([])
  })

  it('sin la autorización: la intención con sus líneas y lo que no está en el catálogo, y va a pedirla', async () => {
    apiPedido({ 'GET /consumo/lista$': { status: 200, cuerpo: LISTA }, 'POST /pedidos$': problema(403, 'sin-autorizacion-pedidos', { finalidad: 'despacho' }) }, { pedido: null })
    const { fijar } = abrirLista()
    await userEvent.click(await screen.findByRole('button', { name: 'Pedir estos productos' }))
    await waitFor(() => expect(window.location.pathname).toBe('/insumos/pedido'))
    expect(fijar).toHaveBeenCalledWith({ intencionPedido: expect.objectContaining({ desde: 'lista', fuera: ['Bolsas de basura'] }) })
  })

  it('con una cantidad fuera de rango, el error de la lista y no se pide nada', async () => {
    const api = apiPedido({ 'GET /consumo/lista$': { status: 200, cuerpo: LISTA } })
    abrirLista()
    await screen.findByRole('button', { name: 'Pedir estos productos' })
    await userEvent.clear(screen.getAllByRole('textbox')[0])
    await userEvent.click(screen.getByRole('button', { name: 'Pedir estos productos' }))
    await waitFor(() => expect(screen.getAllByRole('textbox')[0]).toBeInvalid())
    expect(api.pedidas.filter((p) => /catalogo|pedido/.test(p.ruta))).toEqual([])
  })

  it('el catálogo no responde: el error de siempre y la lista sigue', async () => {
    apiPedido({ 'GET /consumo/lista$': { status: 200, cuerpo: LISTA }, 'GET ^/v1/catalogo$': NO_ENCONTRADO })
    abrirLista()
    await userEvent.click(await screen.findByRole('button', { name: 'Pedir estos productos' }))
    expect(await screen.findByText('No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo. Lo que escribiste sigue aquí.')).toBeVisible()
    expect(window.location.pathname).toBe('/insumos/lista')
  })
})

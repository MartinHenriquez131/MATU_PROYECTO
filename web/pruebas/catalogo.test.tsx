// MATU-59: la pantalla «Catálogo» (especificación docs/diseno/matu-59-catalogo.md v1.0, N1 y N2 de
// Jorge del 08-11). La agrupación y el orden por categoría, el precio en pesos con «Precio de
// ejemplo» e «IVA incluido», «Hay en…» y «No hay en… por ahora», «Por ahora no está disponible», el
// retracto según `retracto_pierde_al_abrir`, cargando, vacío y error con reintento, sin botón «Pedir»
// ni campos ajenos, sin `X-Grupo-Id` y nada en el navegador. Textos de lenguaje.md, sección 27, tal
// cual. Datos sintéticos: comercios y productos ficticios.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { apiFamilia, fijarGrupo } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { Catalogo } from '../src/familia/Catalogo'
import { Insumos } from '../src/familia/Insumos'
import { responderCon, type RespuestaFalsa } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'

const PERSONA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María' }
let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

const ALMACEN = '3c9d4e20-0000-4000-8000-0000000000e1'
const BODEGA = '3c9d4e20-0000-4000-8000-0000000000e2'
let n = 0
const id = () => `3c9d4e20-0000-4000-8000-${String(++n).padStart(12, '0')}`
const oferta = (comercio: 'almacen' | 'bodega', precio: number, disponible: boolean) => ({
  oferta_id: id(),
  comercio_id: comercio === 'almacen' ? ALMACEN : BODEGA,
  nombre_fantasia: comercio === 'almacen' ? 'Almacén El Ejemplo' : 'Bodega La Muestra',
  precio,
  disponible,
})
const producto = (nombre: string, presentacion: string, retracto: boolean, comercios: ReturnType<typeof oferta>[]) => ({
  id: id(),
  nombre,
  presentacion,
  unidad: 'unidad',
  unidades_por_envase: 1,
  retracto_pierde_al_abrir: retracto,
  comercios,
})

/** Como la semilla de MATU-59, pero con las categorías desordenadas: la pantalla las ordena por `orden`. */
function catalogo(preciosDeEjemplo = true) {
  return {
    precios_de_ejemplo: preciosDeEjemplo,
    categorias: [
      {
        id: id(),
        nombre: 'Alimentación',
        orden: 3,
        productos: [producto('Suplemento nutricional en polvo 400 g', 'Tarro de 400 g', false, [oferta('almacen', 18990, true), oferta('bodega', 19490, true)])],
      },
      {
        id: id(),
        nombre: 'Higiene y cuidado personal',
        orden: 1,
        productos: [
          producto('Bolsa colectora x10', 'Caja de 10 unidades', false, [oferta('almacen', 27030, false), oferta('bodega', 26500, false)]),
          producto('Pañal adulto M x30', 'Paquete de 30 unidades', true, [oferta('almacen', 12990, true), oferta('bodega', 13490, false)]),
        ],
      },
      {
        id: id(),
        nombre: 'Cuidado de la piel',
        orden: 2,
        productos: [producto('Crema protectora de la piel 100 g', 'Crema protectora de la piel 100 g', true, [oferta('bodega', 6990, true)])],
      },
    ],
  }
}
const CATALOGO_200: RespuestaFalsa = { status: 200, cuerpo: catalogo() }

function abrir(rol: Rol, ...respuestas: RespuestaFalsa[]) {
  contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol } as never)
  const cabeceras: Record<string, unknown>[] = []
  const pedidas = responderCon(apiFamilia, ...(respuestas.length ? respuestas : [CATALOGO_200]))
  // Lo que de verdad saldría a la red: las cabeceras ya pasadas por el interceptor de sesion.ts.
  const adaptador = apiFamilia.defaults.adapter as (c: InternalAxiosRequestConfig) => Promise<unknown>
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    cabeceras.push(config.headers.toJSON() as Record<string, unknown>)
    return adaptador(config) as never
  }
  const { container } = render(
    <>
      <RegionesVivas />
      <Catalogo />
    </>,
  )
  const urgente = container.querySelector<HTMLElement>('[aria-live="assertive"][aria-atomic="true"]')!
  return { pedidas, cabeceras, urgente, pantalla: within(container) }
}

const tarjeta = (nombre: string) => screen.getByRole('heading', { level: 3, name: nombre }).closest('li')!

let escrituras: string[] = []
beforeEach(() => {
  escrituras = []
  window.history.replaceState(null, '', '/insumos/catalogo')
  for (const s of [window.localStorage, window.sessionStorage]) s.clear()
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
  fijarGrupo('3c9d4e20-0000-4000-8000-0000000000g1')
})

describe('El catálogo', () => {
  it.each<Rol>(['admin', 'cuidador', 'pagador', 'observador'])('lo ve %s, igual para los cuatro roles, con un solo GET y sin X-Grupo-Id', async (rol) => {
    const { pedidas, cabeceras, pantalla } = abrir(rol)
    expect(await pantalla.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })).toBeVisible()
    expect(pedidas).toEqual(['GET /v1/catalogo'])
    // Con un grupo elegido en la sesión, el catálogo igual no lo manda (decisión 159).
    expect(Object.keys(cabeceras[0]).map((k) => k.toLowerCase())).not.toContain('x-grupo-id')

    expect(pantalla.getByRole('heading', { level: 1, name: 'Catálogo' })).toBeVisible()
    expect(pantalla.getByText('Productos que usan las familias que cuidan. Mirar no te compromete a nada.')).toBeVisible()
    const vistas = pantalla.getByRole('navigation', { name: 'Vistas de Insumos' })
    expect(within(vistas).getAllByRole('link').map((a) => a.textContent)).toEqual(['Insumos', 'Lista de insumos', 'Catálogo'])
    expect(within(vistas).getByRole('link', { name: 'Catálogo' })).toHaveAttribute('aria-current', 'page')
    expect(within(vistas).getByRole('link', { name: 'Catálogo' })).toHaveAttribute('href', '/insumos/catalogo')
    expect(pantalla.getAllByRole('heading', { level: 3 })).toHaveLength(4)
  })

  it('agrupa por categoría en su orden, con los productos y los comercios en el orden de la API', async () => {
    const { pantalla } = abrir('cuidador')
    await pantalla.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })
    expect(pantalla.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual(['Higiene y cuidado personal', 'Cuidado de la piel', 'Alimentación'])

    const higiene = pantalla.getByRole('region', { name: 'Higiene y cuidado personal' })
    expect(within(higiene).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['Bolsa colectora x10', 'Pañal adulto M x30'])
    expect(within(pantalla.getByRole('region', { name: 'Alimentación' })).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual([
      'Suplemento nutricional en polvo 400 g',
    ])
    // La bolsa: Bodega cobra menos y va igual segunda (nunca por precio, D6).
    const bolsa = within(tarjeta('Bolsa colectora x10'))
    expect(bolsa.getAllByText(/\(comercio ficticio\)$/).map((p) => p.textContent)).toEqual(['Almacén El Ejemplo (comercio ficticio)', 'Bodega La Muestra (comercio ficticio)'])
    expect(bolsa.getAllByText(/^\$/).map((p) => p.textContent)).toEqual(['$27.030', '$26.500'])
    expect(pantalla.queryByText(/Desde/)).toBeNull()
  })

  it('cada comercio con su precio, «Precio de ejemplo», «IVA incluido» y si lo tiene, con palabra e ícono', async () => {
    abrir('admin')
    const panal = within(await waitFor(() => tarjeta('Pañal adulto M x30')))
    expect(panal.getByText('Paquete de 30 unidades')).toBeVisible()
    const filas = panal.getAllByRole('listitem')
    expect(filas).toHaveLength(2)
    expect(filas[0]).toHaveTextContent('Almacén El Ejemplo (comercio ficticio)$12.990Precio de ejemploIVA incluidoHay en Almacén El Ejemplo')
    expect(filas[1]).toHaveTextContent('Bodega La Muestra (comercio ficticio)$13.490Precio de ejemploIVA incluidoNo hay en Bodega La Muestra por ahora')
    // «(comercio ficticio)» una vez por comercio en la tarjeta (N2); la línea de «Hay» lleva el nombre solo.
    expect(panal.getAllByText(/comercio ficticio/)).toHaveLength(2)
    // Íconos de forma distinta, ocultos al lector: el estado lo dice la frase.
    expect(panal.getByText('Hay en Almacén El Ejemplo').parentElement!.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    expect(panal.getByText('Hay en Almacén El Ejemplo').parentElement!.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-circle-check/)
    expect(panal.getByText('No hay en Bodega La Muestra por ahora').parentElement!.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-circle-minus/)
    // Con stock en uno de los dos, no lleva «Por ahora no está disponible».
    expect(panal.queryByText('Por ahora no está disponible')).toBeNull()
    // El precio nunca en turquesa: un precio no es una acción.
    expect(panal.getByText('$12.990').className).not.toMatch(/turquesa/)
  })

  it('el aviso del piloto y las notas, una sola vez arriba, antes de la primera categoría', async () => {
    const { pantalla } = abrir('pagador')
    await pantalla.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })
    const aviso = pantalla.getByText('Precios de ejemplo.')
    expect(pantalla.getAllByText('Precios de ejemplo.')).toHaveLength(1)
    expect(aviso.closest('div[class*="border-atenta"]')).toHaveTextContent(
      'Precios de ejemplo.MATU todavía no tiene convenio con comercios, y en esta demo no se cobra dinero real.',
    )
    // Sin rol: se lee en el orden del documento.
    expect(aviso.closest('[role]')).toBeNull()
    expect(pantalla.getAllByText('Lo que hay se confirma antes de pagar.')).toHaveLength(1)
    expect(pantalla.getAllByText('El envío se suma al pedido, una sola vez por pedido.')).toHaveLength(1)
    const primera = pantalla.getAllByRole('heading', { level: 2 })[0]
    expect(aviso.compareDocumentPosition(primera) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // Cada precio con su marca.
    expect(pantalla.getAllByText(/^\$\d/)).toHaveLength(7)
    expect(pantalla.getAllByText('Precio de ejemplo')).toHaveLength(7)
    expect(pantalla.getAllByText('IVA incluido')).toHaveLength(7)
  })

  it('con precios_de_ejemplo en false no van el aviso del piloto ni «Precio de ejemplo»', async () => {
    const { pantalla } = abrir('admin', { status: 200, cuerpo: catalogo(false) })
    await pantalla.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })
    expect(pantalla.queryByText('Precios de ejemplo.')).toBeNull()
    expect(pantalla.queryByText('Precio de ejemplo')).toBeNull()
    expect(pantalla.getAllByText('IVA incluido')).toHaveLength(7)
    expect(pantalla.getByText('Lo que hay se confirma antes de pagar.')).toBeVisible()
  })

  it('sin stock en ningún comercio: «Por ahora no está disponible», con sus precios y su retracto, sin opacidad', async () => {
    const { pantalla } = abrir('observador')
    const bolsa = within(await waitFor(() => tarjeta('Bolsa colectora x10')))
    const etiqueta = bolsa.getByText('Por ahora no está disponible')
    expect(etiqueta.querySelector('svg')!.getAttribute('class')).toMatch(/lucide-circle-minus/)
    expect(bolsa.getByText('No hay en Almacén El Ejemplo por ahora')).toBeVisible()
    expect(bolsa.getByText('No hay en Bodega La Muestra por ahora')).toBeVisible()
    expect(bolsa.getByText('$27.030')).toBeVisible()
    expect(bolsa.getByText('Derecho a retracto:')).toBeVisible()
    expect(tarjeta('Bolsa colectora x10').outerHTML).not.toMatch(/opacity/)
    expect(pantalla.getAllByText('Por ahora no está disponible')).toHaveLength(1)
  })

  it('el retracto sale de retracto_pierde_al_abrir, nunca de la categoría, con letra no menor que el precio', async () => {
    const { pantalla } = abrir('cuidador')
    await pantalla.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })
    const retracto = (nombre: string) => within(tarjeta(nombre)).getByText('Derecho a retracto:').closest('p')!
    const conSello = 'Derecho a retracto: tienes 10 días desde que lo recibes. No aplica si abres el sello del producto.'
    const sinSello = 'Derecho a retracto: tienes 10 días desde que lo recibes.'
    expect(retracto('Pañal adulto M x30')).toHaveTextContent(conSello)
    expect(retracto('Crema protectora de la piel 100 g')).toHaveTextContent(conSello)
    // La bolsa está en higiene y no lleva la frase del sello: manda el campo.
    expect(retracto('Bolsa colectora x10').textContent).toBe(sinSello)
    expect(retracto('Suplemento nutricional en polvo 400 g').textContent).toBe(sinSello)
    expect(retracto('Pañal adulto M x30').textContent).toBe(conSello)
    // Uno por producto, no uno por comercio.
    expect(pantalla.getAllByText('Derecho a retracto:')).toHaveLength(4)
    // D2: el retracto en text-lg, igual que la cifra del precio; nunca más chico.
    const precio = within(tarjeta('Pañal adulto M x30')).getByText('$12.990')
    expect(precio.className).toMatch(/\btext-lg\b/)
    expect(retracto('Pañal adulto M x30').className).toMatch(/\btext-lg\b/)
    expect(retracto('Pañal adulto M x30').className).not.toMatch(/\btext-(sm|base|xs)\b/)
  })

  it('N3: si la presentación repite el nombre, no se muestra dos veces', async () => {
    const { pantalla } = abrir('admin')
    await pantalla.findByRole('heading', { level: 3, name: 'Crema protectora de la piel 100 g' })
    expect(within(tarjeta('Crema protectora de la piel 100 g')).getAllByText('Crema protectora de la piel 100 g')).toHaveLength(1)
    expect(within(tarjeta('Suplemento nutricional en polvo 400 g')).getByText('Tarro de 400 g')).toBeVisible()
  })

  it('no hay botón «Pedir» ni ningún control dentro de las tarjetas: solo las pestañas', async () => {
    const { pantalla } = abrir('admin')
    await pantalla.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })
    expect(pantalla.queryByRole('button')).toBeNull()
    expect(pantalla.queryByText(/pedir|comprar|agregar|carro|stock|oferta|recomendad|más barato/i)).toBeNull()
    for (const li of document.querySelectorAll('section li')) {
      expect(li.querySelectorAll('a, button, input, select, textarea, [tabindex]')).toHaveLength(0)
    }
    expect(pantalla.getAllByRole('link').map((a) => a.textContent)).toEqual(['Insumos', 'Lista de insumos', 'Catálogo'])
  })

  it('no muestra campos ajenos aunque la API los mandara: datos del comercio, marca, stock ni unidades', async () => {
    const cuerpo = catalogo()
    const ajenos = {
      razon_social: 'Comercio de Prueba Uno (ficticio)',
      // RUT inválido a propósito (su DV correcto es 7), para no apuntar a una empresa real.
      rut: '77.777.701-8',
      direccion: 'Calle de Prueba 100',
      comuna: 'Comuna Inventada',
      telefono: '+56 2 5555 0101',
      stock: 4321,
    }
    for (const c of cuerpo.categorias)
      for (const p of c.productos) {
        Object.assign(p, { marca: 'Marca de ejemplo', unidades_por_envase: 9137, unidad: 'sobre', grupo_id: 'grupo-que-no-va', imagen: 'https://ejemplo.invalid/foto.png' })
        for (const o of p.comercios) Object.assign(o, ajenos)
      }
    const { pantalla } = abrir('admin', { status: 200, cuerpo })
    await pantalla.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })
    const texto = document.body.textContent ?? ''
    for (const v of [...Object.values(ajenos).map(String), 'Marca de ejemplo', '9137', '9.137', 'sobre', 'grupo-que-no-va', '4.321', 'Comuna'])
      expect(texto, `no debería mostrar «${v}»`).not.toContain(v)
    expect(document.querySelector('img')).toBeNull()
    expect(document.body.innerHTML).not.toContain('ejemplo.invalid')
  })

  it('esconde un producto sin comercios y una categoría que queda sin productos', async () => {
    const cuerpo = catalogo()
    cuerpo.categorias.push({ id: id(), nombre: 'Categoría sin nada', orden: 0, productos: [producto('Producto sin comercios', 'Sin presentación', false, [])] })
    const { pantalla } = abrir('admin', { status: 200, cuerpo })
    await pantalla.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })
    expect(pantalla.queryByText('Categoría sin nada')).toBeNull()
    expect(pantalla.queryByText('Producto sin comercios')).toBeNull()
  })

  it('nada del catálogo en el navegador ni en la URL', async () => {
    const { pantalla } = abrir('admin')
    await pantalla.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })
    expect(escrituras).toEqual([])
    expect(localStorage.length + sessionStorage.length).toBe(0)
    expect(window.location.pathname).toBe('/insumos/catalogo')
    expect(window.location.search + window.location.hash).toBe('')
    expect(window.history.state).toBeNull()
  })
})

describe('Cargando, vacío y error', () => {
  it('cargando: pestañas, título y bajada desde el principio, y «Cargando…» a los 400 ms con aria-busy', async () => {
    let soltar: () => void = () => {}
    contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol: 'admin' } as never)
    apiFamilia.defaults.adapter = (config: InternalAxiosRequestConfig) =>
      new Promise((ok) => {
        soltar = () => ok({ data: catalogo(), status: 200, statusText: '', headers: {}, config, request: {} })
      })
    render(<Catalogo />)
    expect(screen.getByRole('navigation', { name: 'Vistas de Insumos' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 1, name: 'Catálogo' })).toBeVisible()
    expect(screen.getByText('Productos que usan las familias que cuidan. Mirar no te compromete a nada.')).toBeVisible()
    const estado = screen.getByRole('status')
    expect(estado.closest('[aria-busy="true"]')).not.toBeNull()
    expect(estado).toHaveTextContent('')
    await waitFor(() => expect(estado).toHaveTextContent('Cargando…'), { timeout: 2000 })
    expect(screen.queryByText('Precios de ejemplo.')).toBeNull()
    soltar()
    expect(await screen.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })).toBeVisible()
    expect(screen.queryByText('Cargando…')).toBeNull()
  })

  it('vacío: «Todavía no hay productos en el catálogo.», sin acción, sin aviso ni notas', async () => {
    const { pantalla } = abrir('cuidador', { status: 200, cuerpo: { precios_de_ejemplo: true, categorias: [] } })
    expect(await pantalla.findByText('Todavía no hay productos en el catálogo.')).toBeVisible()
    expect(pantalla.queryByRole('button')).toBeNull()
    expect(pantalla.queryByText('Precios de ejemplo.')).toBeNull()
    expect(pantalla.queryByText('Lo que hay se confirma antes de pagar.')).toBeNull()
    expect(pantalla.queryByText('El envío se suma al pedido, una sola vez por pedido.')).toBeNull()
    expect(pantalla.getByRole('heading', { level: 1, name: 'Catálogo' })).toBeVisible()
  })

  it('error: el texto en la región urgente y «Volver a intentar» vuelve a pedir, sin mostrar un catálogo viejo', async () => {
    const { pedidas, urgente, pantalla } = abrir('admin', { status: 503, cuerpo: { type: '/errores/no-disponible', title: 'Texto de la API', status: 503 } }, CATALOGO_200)
    expect(await pantalla.findByText('No pudimos traer el catálogo. Revisa tu conexión e inténtalo de nuevo.')).toBeVisible()
    await waitFor(() => expect(urgente).toHaveTextContent('No pudimos traer el catálogo. Revisa tu conexión e inténtalo de nuevo.'))
    expect(pantalla.queryByText('Texto de la API')).toBeNull()
    expect(pantalla.queryByText('Precios de ejemplo.')).toBeNull()
    const boton = pantalla.getByRole('button', { name: 'Volver a intentar' })
    expect(pantalla.getAllByRole('button')).toHaveLength(1)

    await userEvent.click(boton)
    expect(await pantalla.findByRole('heading', { level: 3, name: 'Pañal adulto M x30' })).toBeVisible()
    expect(pedidas).toEqual(['GET /v1/catalogo', 'GET /v1/catalogo'])
    expect(pantalla.queryByText('No pudimos traer el catálogo. Revisa tu conexión e inténtalo de nuevo.')).toBeNull()
  })

  it('capa 3 apagada (404): «El catálogo no está disponible por ahora.», sin botón, sin región urgente, con las pestañas', async () => {
    const { pedidas, urgente, pantalla } = abrir('admin', { status: 404, cuerpo: { type: '/errores/no-encontrado', title: 'Texto de la API', status: 404 } })
    const texto = await pantalla.findByText('El catálogo no está disponible por ahora.')
    expect(texto).toBeVisible()
    expect(texto.closest('[role="alert"]')).toBeNull()
    // La única región con role=alert es la global de RegionesVivas, y queda vacía.
    expect(pantalla.getAllByRole('alert')).toEqual([urgente])
    expect(urgente).toHaveTextContent('')
    expect(pantalla.queryByRole('button')).toBeNull()
    expect(pantalla.queryByText('No pudimos traer el catálogo. Revisa tu conexión e inténtalo de nuevo.')).toBeNull()
    expect(pantalla.queryByText('Texto de la API')).toBeNull()
    expect(pantalla.queryByText('Precios de ejemplo.')).toBeNull()
    expect(pantalla.queryByText('Lo que hay se confirma antes de pagar.')).toBeNull()
    expect(pantalla.queryByText('El envío se suma al pedido, una sola vez por pedido.')).toBeNull()
    expect(pantalla.getByRole('navigation', { name: 'Vistas de Insumos' })).toBeVisible()
    expect(pantalla.getByRole('heading', { level: 1, name: 'Catálogo' })).toBeVisible()
    expect(pedidas).toEqual(['GET /v1/catalogo'])
  })

  it('el 503 no es «no disponible»: sigue el error con «Volver a intentar»', async () => {
    const { pantalla } = abrir('cuidador', { status: 503, cuerpo: { type: '/errores/servicio-no-disponible', title: 'Texto de la API', status: 503 } })
    expect(await pantalla.findByText('No pudimos traer el catálogo. Revisa tu conexión e inténtalo de nuevo.')).toBeVisible()
    expect(pantalla.getByRole('button', { name: 'Volver a intentar' })).toBeVisible()
    expect(pantalla.queryByText('El catálogo no está disponible por ahora.')).toBeNull()
  })

  it('error de red, sin respuesta: el mismo texto', async () => {
    contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol: 'observador' } as never)
    apiFamilia.defaults.adapter = async () => {
      throw new Error('Network Error')
    }
    render(<Catalogo />)
    expect(await screen.findByText('No pudimos traer el catálogo. Revisa tu conexión e inténtalo de nuevo.')).toBeVisible()
  })
})

describe('Las pestañas de Insumos (N1)', () => {
  const sinPermiso: RespuestaFalsa = { status: 403, cuerpo: { type: '/errores/sin-consentimiento', status: 403, finalidad: 'consumo' } }
  const renovar: RespuestaFalsa = { status: 403, cuerpo: { type: '/errores/revision-vencida', status: 403 } }

  function insumos(rol: Rol, r: RespuestaFalsa) {
    window.history.replaceState(null, '', '/insumos')
    contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol } as never)
    responderCon(apiFamilia, r)
    render(<Insumos />)
  }
  const pestanas = () => within(screen.getByRole('navigation', { name: 'Vistas de Insumos' })).getAllByRole('link').map((a) => a.textContent)

  it('en el permiso del cuidador: «Insumos» y «Catálogo», sin «Lista de insumos»', async () => {
    insumos('cuidador', sinPermiso)
    await screen.findByRole('heading', { level: 1, name: 'Antes de calcular, un permiso' })
    expect(pestanas()).toEqual(['Insumos', 'Catálogo'])
    expect(screen.getByRole('link', { name: 'Insumos' })).toHaveAttribute('aria-current', 'page')
  })

  it('en «Falta el permiso» del observador: «Insumos» y «Catálogo», y la pestaña lleva al catálogo', async () => {
    insumos('observador', sinPermiso)
    await screen.findByText(/^Falta el permiso/)
    expect(pestanas()).toEqual(['Insumos', 'Catálogo'])
    await userEvent.click(screen.getByRole('link', { name: 'Catálogo' }))
    expect(window.location.pathname).toBe('/insumos/catalogo')
  })

  it('en «Hay que renovar»: «Insumos» y «Catálogo»', async () => {
    insumos('admin', renovar)
    await screen.findByRole('heading', { level: 1, name: 'Insumos' })
    await waitFor(() => expect(pestanas()).toEqual(['Insumos', 'Catálogo']))
  })

  it('con la lista cargada: las tres pestañas, «Catálogo» al final', async () => {
    insumos('admin', { status: 200, cuerpo: { items: [], siguiente_cursor: null } })
    await waitFor(() => expect(pestanas()).toEqual(['Insumos', 'Lista de insumos', 'Catálogo']))
  })
})

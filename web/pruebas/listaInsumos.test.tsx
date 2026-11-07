// MATU-60: la pantalla «Lista de insumos» (especificación docs/diseno/matu-60-lista-insumos.md v1.2).
// El observador sin botones ni campos, el 403 con sus textos, quitar y agregar con sus anuncios,
// copiar con éxito y con error, `navigator.share` solo con `text`, la impresión y que nada se
// escribe en el navegador. Textos de lenguaje.md, sección 21, tal cual. Datos sintéticos.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Rol } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { Insumos } from '../src/familia/Insumos'
import { ListaDeInsumos } from '../src/familia/ListaInsumos'
import { useRuta } from '../src/familia/ruteo'
import { responderCon, type RespuestaFalsa } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'

const PERSONA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María' }
let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

const LISTA_200: RespuestaFalsa = {
  status: 200,
  cuerpo: {
    fecha: '2026-11-06',
    items: [
      { perfil_id: '3c9d4e20-0000-4000-8000-0000000000c2', nombre: 'Crema humectante', unidad: 'ml', dias_restantes: -2, unidades_sugeridas: 215, unidades_por_envase: 250, envases_sugeridos: 1 },
      { perfil_id: '3c9d4e20-0000-4000-8000-0000000000c3', nombre: 'Toallitas húmedas', unidad: 'unidad', dias_restantes: 0, unidades_sugeridas: 118, unidades_por_envase: null, envases_sugeridos: null },
      { perfil_id: '3c9d4e20-0000-4000-8000-0000000000c1', nombre: 'Pañal adulto talla M', unidad: 'unidad', dias_restantes: 6, unidades_sugeridas: 108, unidades_por_envase: 20, envases_sugeridos: 6 },
    ],
  },
}
const TEXTO_200 = [
  'Lista de insumos · 06/11/2026',
  '- Crema humectante: 1 envase de 250 ml',
  '- Toallitas húmedas: 118 unidades',
  '- Pañal adulto talla M: 6 envases de 20 unidades',
  'Piloto académico con datos de prueba',
].join('\n')

function abrir(rol: Rol, ...respuestas: RespuestaFalsa[]) {
  contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol } as never)
  const pedidas = responderCon(apiFamilia, ...(respuestas.length ? respuestas : [LISTA_200]))
  const { container } = render(
    <>
      <RegionesVivas />
      <ListaDeInsumos />
    </>,
  )
  const amable = container.querySelector<HTMLElement>('[aria-live="polite"][aria-atomic="true"]')!
  const urgente = container.querySelector<HTMLElement>('[aria-live="assertive"][aria-atomic="true"]')!
  return { pedidas, amable, urgente, pantalla: within(container) }
}

const hoja = () => document.body.querySelector<HTMLElement>(':scope > [data-impresion]')

let escrituras: string[] = []
beforeEach(() => {
  escrituras = []
  window.history.replaceState(null, '', '/insumos/lista')
  for (const s of [window.localStorage, window.sessionStorage]) s.clear()
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
})
afterEach(() => {
  delete (navigator as { share?: unknown }).share
  delete (navigator as { canShare?: unknown }).canShare
})

function portapapeles(writeText: (t: string) => Promise<void>) {
  const fn = vi.fn(writeText)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText: fn }, configurable: true })
  return fn
}

describe('La lista, para quien la puede sacar del teléfono', () => {
  it('pide la lista, muestra las líneas con días y cantidad, el aviso y los botones sin hoja de compartir', async () => {
    const { pedidas, pantalla } = abrir('cuidador')
    expect(await pantalla.findByText('Pañal adulto talla M')).toBeVisible()
    expect(pedidas).toEqual([`GET /v1/personas-cuidadas/${PERSONA.id}/consumo/lista`])

    expect(pantalla.getByRole('heading', { level: 1, name: 'Lista de insumos' })).toBeVisible()
    expect(pantalla.getByRole('navigation', { name: 'Vistas de Insumos' })).toBeVisible()
    expect(pantalla.getByRole('link', { name: 'Lista de insumos' })).toHaveAttribute('aria-current', 'page')
    expect(pantalla.getByText('Lo que se acaba pronto, con una cantidad sugerida para 30 días. Puedes cambiarla antes de imprimir o compartir.')).toBeVisible()
    expect(pantalla.getByText('Puede que ya no quede')).toBeVisible()
    expect(pantalla.getByText('Se acaba hoy')).toBeVisible()
    expect(pantalla.getByText(/Alcanza para/)).toHaveTextContent('Alcanza para 6 días')

    const panal = pantalla.getByRole('textbox', { name: 'Cantidad Pañal adulto talla M' })
    expect(panal).toHaveValue('6')
    expect(pantalla.getByText('envases de 20 unidades')).toBeVisible()
    expect(pantalla.getByRole('button', { name: 'Menos: Cantidad de Pañal adulto talla M' })).toBeVisible()
    expect(pantalla.getByRole('button', { name: 'Quitar de la lista: Pañal adulto talla M' })).toHaveTextContent('Quitar de la lista')

    expect(pantalla.getByText(/^La lista no lleva el nombre de María/)).toHaveTextContent(
      'La lista no lleva el nombre de María, pero sí lo que usa. Lo que imprimas o compartas sale de MATU y no podemos borrarlo. Compártela solo con quien va a comprar.',
    )
    // Sin navigator.share, imprimir es el principal y lo describe el aviso.
    expect(pantalla.queryByRole('button', { name: 'Compartir la lista' })).toBeNull()
    expect(pantalla.getByRole('button', { name: 'Imprimir o guardar en PDF' })).toHaveAccessibleDescription(/^La lista no lleva el nombre de María/)
    expect(pantalla.getByRole('button', { name: 'Copiar la lista' })).toBeVisible()
  })

  it('el pagador ve la nota con «lo que anotó la familia» y puede sacarla', async () => {
    const { pantalla } = abrir('pagador')
    expect(
      await pantalla.findByText('Es una sugerencia con lo que anotó la familia, y ya descuenta lo que queda. Cambia la cantidad si necesitas otra.'),
    ).toBeVisible()
    expect(pantalla.getByRole('button', { name: 'Copiar la lista' })).toBeVisible()
  })

  it('la hoja de impresión va fuera de la app, con el mismo texto, y el título cambia al imprimir', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    const { pantalla } = abrir('admin')
    const u = userEvent.setup()
    await pantalla.findByText('Pañal adulto talla M')

    const h = hoja()!
    expect(h).toHaveClass('hidden', 'print:block')
    expect(h.querySelector('p')).toHaveTextContent('Lista de insumos · 06/11/2026')
    expect([...h.querySelectorAll('li')].map((li) => li.textContent)).toEqual(['Crema humectante1 envase de 250 ml', 'Toallitas húmedas118 unidades', 'Pañal adulto talla M6 envases de 20 unidades'])
    expect(h).toHaveTextContent('Piloto académico con datos de prueba')
    expect(h.textContent).not.toMatch(/María|días|Se acaba/)

    await u.click(pantalla.getByRole('button', { name: 'Imprimir o guardar en PDF' }))
    await waitFor(() => expect(print).toHaveBeenCalledTimes(1))
    expect(document.title).toBe('Lista de insumos')
    window.dispatchEvent(new Event('afterprint'))
    expect(document.title).toBe('Lista de insumos · MATU')
    window.dispatchEvent(new Event('beforeprint'))
    expect(document.title).toBe('Lista de insumos')
  })
})

describe('El observador', () => {
  it('ve las líneas con nombre, días y cantidad, sin campos, sin aviso y sin botones', async () => {
    const { pantalla } = abrir('observador')
    expect(await pantalla.findByText('6 envases de 20 unidades')).toBeVisible()
    expect(pantalla.getByText('1 envase de 250 ml')).toBeVisible()
    // En pantalla, espacio duro tras cada cifra; la lista que se copia o comparte (TEXTO_200) no lo lleva.
    expect(pantalla.getByText('6 envases de 20 unidades').textContent).toBe('6 envases de 20 unidades')
    expect(pantalla.getByText('Lo que se acaba pronto, con una cantidad sugerida para 30 días.')).toBeVisible()
    expect(pantalla.getByText('Es una sugerencia con lo que anotó la familia, y ya descuenta lo que queda.')).toBeVisible()
    expect(pantalla.getByText('Quien administra, cuida o paga puede imprimirla o compartirla.')).toBeVisible()

    expect(pantalla.queryByRole('textbox')).toBeNull()
    // Solo las pestañas: ningún botón, ni deshabilitado.
    expect(pantalla.queryAllByRole('button')).toEqual([])
    expect(pantalla.queryByText(/La lista no lleva el nombre/)).toBeNull()
  })

  it('su hoja de impresión trae solo el título, su nota y el pie', async () => {
    const { pantalla } = abrir('observador')
    await pantalla.findByText('6 envases de 20 unidades')
    const h = hoja()!
    expect(h.querySelectorAll('li')).toHaveLength(0)
    expect(h).toHaveTextContent('Lista de insumos · 06/11/2026Quien administra, cuida o paga puede imprimirla o compartirla.Piloto académico con datos de prueba')
  })
})

describe('Los 403, el 404 y el error al cargar', () => {
  it('sin-consentimiento, pagador: «Falta el permiso…», sin botones ni región alert', async () => {
    const { pantalla, urgente } = abrir('pagador', { status: 403, cuerpo: { type: '/errores/sin-consentimiento', status: 403, finalidad: 'consumo' } })
    expect(await pantalla.findByText('Falta el permiso para calcular los insumos de María.')).toBeVisible()
    expect(pantalla.getByText(/^Falta el permiso/).closest('p')).toHaveTextContent(
      'Falta el permiso para calcular los insumos de María. Sin él no podemos mostrar cuándo se acaban. Pídele a quien administra el grupo o a quien cuida a María que lo registre.',
    )
    expect(pantalla.queryAllByRole('button')).toEqual([])
    expect(urgente).toBeEmptyDOMElement()
    expect(pantalla.getByRole('navigation', { name: 'Vistas de Insumos' })).toBeVisible()
  })

  it('sin-consentimiento, cuidador: va a Insumos, que pide el permiso, sin dejar una entrada en el historial', async () => {
    const largo = window.history.length
    abrir('cuidador', { status: 403, cuerpo: { type: '/errores/sin-consentimiento', status: 403 } })
    await waitFor(() => expect(window.location.pathname).toBe('/insumos'))
    expect(window.history.length).toBe(largo)
  })

  it('revision-vencida: «Hay que renovar…» para todos', async () => {
    const { pantalla } = abrir('cuidador', { status: 403, cuerpo: { type: '/errores/revision-vencida', status: 403 } })
    expect(await pantalla.findByText('Hay que renovar la autorización de los insumos de María.')).toBeVisible()
    expect(pantalla.getByText(/^Hay que renovar/).closest('p')).toHaveTextContent(
      'Hay que renovar la autorización de los insumos de María. Se renueva una vez al año. Mientras tanto, no podemos calcular ni mostrar sus insumos, pero lo que anotaste sigue guardado.',
    )
  })

  it('404: el texto de lenguaje 8 y «Volver al inicio»', async () => {
    const { pantalla } = abrir('admin', { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404, title: 'No encontrado', detail: 'detalle de la API' } })
    expect(await pantalla.findByText('No encontramos lo que buscas. Puede que ya no tengas acceso. Vuelve al inicio.')).toBeVisible()
    expect(pantalla.getByRole('link', { name: 'Volver al inicio' })).toBeVisible()
    expect(pantalla.queryByText(/detalle de la API/)).toBeNull()
  })

  it('500: el error va a la región alert, sin lista vieja, y «Volver a intentar» la pide de nuevo', async () => {
    const { pantalla, urgente, pedidas } = abrir('admin', { status: 500, cuerpo: { type: '/errores/error-interno', status: 500 } }, LISTA_200)
    await waitFor(() => expect(urgente).toHaveTextContent('No pudimos traer la lista. Revisa tu conexión e inténtalo de nuevo.'))
    expect(pantalla.queryByText('Pañal adulto talla M')).toBeNull()
    expect(hoja()).toBeNull()
    await userEvent.setup().click(pantalla.getByRole('button', { name: 'Volver a intentar' }))
    expect(await pantalla.findByText('Pañal adulto talla M')).toBeVisible()
    expect(pedidas).toHaveLength(2)
  })
})

describe('Quitar y agregar', () => {
  it('quitar una línea de MATU la saca de la pantalla y del texto, lo anuncia y mueve el foco a la siguiente', async () => {
    const { pantalla, amable } = abrir('admin')
    const u = userEvent.setup()
    await pantalla.findByText('Pañal adulto talla M')

    await u.click(pantalla.getByRole('button', { name: 'Quitar de la lista: Crema humectante' }))
    await waitFor(() => expect(amable).toHaveTextContent('Quitamos «Crema humectante» de la lista. Sigue en Insumos.'))
    expect(pantalla.queryByText('Crema humectante')).toBeNull()
    expect(pantalla.getByText('Lo que quitaste sigue en Insumos. Vuelve a esta lista cuando entras de nuevo.')).toBeVisible()
    await waitFor(() => expect(pantalla.getByRole('textbox', { name: 'Cantidad Toallitas húmedas' })).toHaveFocus())
    expect(hoja()!.textContent).not.toContain('Crema humectante')
  })

  it('quitar todas deja «Quitaste todo de la lista…», sin aviso ni botones, y el foco en «Agregar otro insumo»', async () => {
    const { pantalla } = abrir('admin')
    const u = userEvent.setup()
    await pantalla.findByText('Pañal adulto talla M')
    for (const n of ['Crema humectante', 'Toallitas húmedas', 'Pañal adulto talla M']) await u.click(pantalla.getByRole('button', { name: `Quitar de la lista: ${n}` }))

    expect(pantalla.getByText('Quitaste todo de la lista. Si quieres, agrega uno a mano.')).toBeVisible()
    expect(pantalla.queryByText('No hay insumos que se acaben pronto. Si quieres, agrega uno a mano.')).toBeNull()
    expect(pantalla.queryByRole('button', { name: 'Copiar la lista' })).toBeNull()
    expect(pantalla.queryByText(/La lista no lleva el nombre/)).toBeNull()
    await waitFor(() => expect(pantalla.getByRole('button', { name: 'Agregar otro insumo' })).toHaveFocus())
  })

  it('agregar a mano en envases: valida, agrega al final, lo anuncia, vuelve el foco y entra al texto', async () => {
    const { pantalla, amable } = abrir('admin')
    const u = userEvent.setup()
    await pantalla.findByText('Pañal adulto talla M')
    const writeText = portapapeles(async () => {})

    await u.click(pantalla.getByRole('button', { name: 'Agregar otro insumo' }))
    const nombre = pantalla.getByRole('textbox', { name: '¿Qué insumo es?' })
    await waitFor(() => expect(nombre).toHaveFocus())
    expect(pantalla.getByRole('radio', { name: 'Unidades' })).toBeChecked()
    expect(pantalla.getByText('Esto queda solo en esta pantalla. No lo guardamos.')).toBeVisible()

    // Sin nombre, el error queda en el campo.
    await u.click(pantalla.getByRole('button', { name: 'Agregar' }))
    expect(nombre).toHaveAccessibleDescription('Por ejemplo: «Toallitas húmedas». Sin remedios ni para qué se usa. Escribe el nombre del insumo.')
    expect(nombre).toHaveFocus()

    await u.type(nombre, 'Toallitas para el baño')
    await u.click(pantalla.getByRole('radio', { name: 'Envases' }))
    expect(pantalla.getByText('envase')).toBeVisible()
    await u.click(pantalla.getByRole('button', { name: 'Uno más: Cantidad' }))
    expect(pantalla.getByText('envases')).toBeVisible()
    await u.click(pantalla.getByRole('button', { name: 'Agregar' }))

    await waitFor(() => expect(amable).toHaveTextContent('Agregamos «Toallitas para el baño» a la lista.'))
    await waitFor(() => expect(pantalla.getByRole('button', { name: 'Agregar otro insumo' })).toHaveFocus())
    expect(pantalla.getByText('Solo en esta pantalla')).toBeVisible()
    expect(pantalla.getByRole('textbox', { name: 'Cantidad Toallitas para el baño' })).toHaveValue('2')

    await u.click(pantalla.getByRole('button', { name: 'Copiar la lista' }))
    expect(writeText).toHaveBeenCalledWith(`${TEXTO_200.replace('\nPiloto', '\n- Toallitas para el baño: 2 envases\nPiloto')}`)

    // Quitar lo agregado a mano: su propio anuncio, sin «Sigue en Insumos».
    await u.click(pantalla.getByRole('button', { name: 'Quitar de la lista: Toallitas para el baño' }))
    await waitFor(() => expect(amable).toHaveTextContent('Quitamos «Toallitas para el baño» de la lista.'))
    expect(amable.textContent).not.toContain('Sigue en Insumos')
    expect(pantalla.queryByText(/Lo que quitaste sigue en Insumos/)).toBeNull()
  })

  it('Esc cierra el panel sin agregar y devuelve el foco al botón', async () => {
    const { pantalla } = abrir('admin')
    const u = userEvent.setup()
    await pantalla.findByText('Pañal adulto talla M')
    await u.click(pantalla.getByRole('button', { name: 'Agregar otro insumo' }))
    await u.type(pantalla.getByRole('textbox', { name: '¿Qué insumo es?' }), 'Gasas')
    await u.keyboard('{Escape}')
    await waitFor(() => expect(pantalla.getByRole('button', { name: 'Agregar otro insumo' })).toHaveFocus())
    expect(pantalla.queryByText('Gasas')).toBeNull()
  })
})

describe('Copiar y compartir', () => {
  it('copiar con éxito: el texto exacto, el mensaje por la región status y el foco en el botón', async () => {
    const { pantalla, amable } = abrir('admin')
    const u = userEvent.setup()
    await pantalla.findByText('Pañal adulto talla M')
    const writeText = portapapeles(async () => {})

    const boton = pantalla.getByRole('button', { name: 'Copiar la lista' })
    await u.click(boton)
    expect(writeText).toHaveBeenCalledWith(TEXTO_200)
    await waitFor(() => expect(amable).toHaveTextContent('Copiamos la lista. Pégala donde quieras.'))
    expect(pantalla.getByText('Copiamos la lista. Pégala donde quieras.', { selector: '#mensaje-lista p' })).toBeVisible()
    expect(boton).toHaveFocus()

    // Se retira en cuanto cambia la lista.
    await u.click(pantalla.getByRole('button', { name: 'Más: Cantidad de Pañal adulto talla M' }))
    expect(pantalla.queryByText('Copiamos la lista. Pégala donde quieras.', { selector: '#mensaje-lista p' })).toBeNull()
    expect(amable).toBeEmptyDOMElement()
  })

  it('copiar falla: el error por la región alert, con «Imprimir» si no hay hoja de compartir', async () => {
    const { pantalla, urgente } = abrir('admin')
    const u = userEvent.setup()
    await pantalla.findByText('Pañal adulto talla M')
    portapapeles(async () => {
      throw new DOMException('No', 'NotAllowedError')
    })

    await u.click(pantalla.getByRole('button', { name: 'Copiar la lista' }))
    await waitFor(() => expect(urgente).toHaveTextContent('No pudimos copiar la lista. Usa «Imprimir o guardar en PDF».'))
    expect(pantalla.getByRole('button', { name: 'Copiar la lista' })).toHaveFocus()
  })

  it('con una cantidad fuera de rango no sale nada: el error en el campo y el foco en él', async () => {
    const { pantalla } = abrir('admin')
    const u = userEvent.setup()
    await pantalla.findByText('Pañal adulto talla M')
    const writeText = portapapeles(async () => {})

    const campo = pantalla.getByRole('textbox', { name: 'Cantidad Toallitas húmedas' })
    await u.clear(campo)
    await u.type(campo, '0')
    await u.click(pantalla.getByRole('button', { name: 'Copiar la lista' }))
    expect(writeText).not.toHaveBeenCalled()
    expect(campo).toHaveFocus()
    expect(campo).toBeInvalid()
    expect(campo).toHaveAccessibleDescription('Escribe una cantidad de 1 a 100.000.')
    // 8.3: la hoja usa el último valor válido.
    expect(hoja()).toHaveTextContent('Toallitas húmedas118 unidades')

    await u.type(campo, '5')
    expect(campo).not.toBeInvalid()
  })

  it('con navigator.share: «Compartir la lista» es el principal y se llama solo con `text`', async () => {
    const share = vi.fn(async (_datos: ShareData) => {})
    Object.defineProperty(navigator, 'share', { value: share, configurable: true })
    const { pantalla } = abrir('admin')
    const u = userEvent.setup()
    await pantalla.findByText('Pañal adulto talla M')

    const boton = pantalla.getByRole('button', { name: 'Compartir la lista' })
    expect(boton).toHaveAccessibleDescription(/^La lista no lleva el nombre de María/)
    expect(pantalla.getByRole('button', { name: 'Imprimir o guardar en PDF' })).not.toHaveAttribute('aria-describedby')
    await u.click(boton)
    expect(share).toHaveBeenCalledTimes(1)
    expect(share.mock.calls[0][0]).toStrictEqual({ text: TEXTO_200 })
    expect(Object.keys(share.mock.calls[0][0])).toEqual(['text'])
    // Sin «Enviada» ni «Compartida».
    expect(pantalla.queryByText(/Enviada|Compartida/)).toBeNull()
  })

  it('cerrar la hoja de compartir no muestra nada; otro error dice «Usa Copiar la lista»', async () => {
    const share = vi
      .fn<(d: ShareData) => Promise<void>>()
      .mockRejectedValueOnce(new DOMException('Cerrada', 'AbortError'))
      .mockRejectedValueOnce(new DOMException('No', 'NotAllowedError'))
    Object.defineProperty(navigator, 'share', { value: share, configurable: true })
    const { pantalla, urgente } = abrir('admin')
    const u = userEvent.setup()
    await pantalla.findByText('Pañal adulto talla M')

    await u.click(pantalla.getByRole('button', { name: 'Compartir la lista' }))
    expect(pantalla.queryByText(/No pudimos/)).toBeNull()
    await u.click(pantalla.getByRole('button', { name: 'Compartir la lista' }))
    await waitFor(() => expect(urgente).toHaveTextContent('No pudimos abrir Compartir. Usa «Copiar la lista».'))

    portapapeles(async () => {
      throw new Error('sin permiso')
    })
    await u.click(pantalla.getByRole('button', { name: 'Copiar la lista' }))
    await waitFor(() => expect(urgente).toHaveTextContent('No pudimos copiar la lista. Usa «Compartir la lista».'))
  })
})

describe('Nada de la lista queda en el navegador', () => {
  it('ni en localStorage, sessionStorage, la URL, history.state ni el título', async () => {
    const { pantalla } = abrir('admin')
    const u = userEvent.setup()
    await pantalla.findByText('Pañal adulto talla M')
    portapapeles(async () => {})

    await u.click(pantalla.getByRole('button', { name: 'Más: Cantidad de Pañal adulto talla M' }))
    await u.click(pantalla.getByRole('button', { name: 'Agregar otro insumo' }))
    await u.type(pantalla.getByRole('textbox', { name: '¿Qué insumo es?' }), 'Gasas')
    await u.click(pantalla.getByRole('button', { name: 'Agregar' }))
    await u.click(pantalla.getByRole('button', { name: 'Quitar de la lista: Crema humectante' }))
    await u.click(pantalla.getByRole('button', { name: 'Copiar la lista' }))

    expect(escrituras).toEqual([])
    expect(window.localStorage).toHaveLength(0)
    expect(window.sessionStorage).toHaveLength(0)
    expect(window.location.pathname + window.location.search + window.location.hash).toBe('/insumos/lista')
    expect(window.history.state).toBeNull()
    expect(document.title).not.toMatch(/Pañal|Gasas|María/)
  })
})

describe('Revisión visual del 06-11 (v1.2)', () => {
  /** 2.3: `useAncho` mide el ancho del contenedor; jsdom no tiene diseño, así que se simula. */
  const enAncho = () => vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(1200)

  it('4.3: la grilla de la línea se decide por el ancho de la lista, con la cantidad en una columna de 20 rem', async () => {
    const { pantalla } = abrir('admin')
    await pantalla.findByText('Pañal adulto talla M')
    const ul = pantalla.getByText('Pañal adulto talla M').closest('ul')!
    expect(ul).toHaveClass('@container/lista')
    for (const li of ul.querySelectorAll('li')) {
      expect(li).toHaveClass('grid', 'grid-cols-1', '@2xl/lista:grid-cols-[minmax(0,1fr)_20rem_auto]', '@2xl/lista:items-center', 'gap-x-6', 'gap-y-2')
      expect(li.className).not.toMatch(/@3xl\/main/)
    }
    const quitar = pantalla.getByRole('button', { name: 'Quitar de la lista: Pañal adulto talla M' })
    expect(quitar).toHaveClass('@2xl/lista:mt-0', 'justify-self-end')
    expect(quitar.className).not.toMatch(/@3xl\/main/)
  })

  it('4.3: la línea del observador son dos columnas, con la cantidad a la derecha solo en ancho', async () => {
    const { pantalla } = abrir('observador')
    const cantidad = await pantalla.findByText('6 envases de 20 unidades')
    expect(cantidad).toHaveClass('@2xl/lista:text-right')
    // A 360 px, una sola columna: la cantidad no va a la derecha.
    expect(cantidad).not.toHaveClass('text-right')
    expect(cantidad.closest('li')).toHaveClass('@2xl/lista:grid-cols-[minmax(0,1fr)_auto]')
    expect(cantidad.closest('ul')).toHaveClass('@container/lista')
  })

  it('2.3: el observador en ancho va en una sola columna: líneas, nota y la frase debajo', async () => {
    enAncho()
    const { pantalla } = abrir('observador')
    await pantalla.findByText('6 envases de 20 unidades')
    const ul = pantalla.getByText('6 envases de 20 unidades').closest('ul')!
    const columna = ul.parentElement!
    expect(columna).toHaveClass('flex', 'flex-col', 'gap-5', 'max-w-3xl')
    expect([...columna.children].map((x) => `${x.tagName}:${x.tagName === 'UL' ? '' : x.textContent}`)).toEqual([
      'UL:',
      'P:Es una sugerencia con lo que anotó la familia, y ya descuenta lo que queda.',
      'P:Quien administra, cuida o paga puede imprimirla o compartirla.',
    ])
    expect(document.querySelector('[class*="grid-cols-[3fr_2fr]"]')).toBeNull()
  })

  it('2.3: los demás roles en ancho siguen con la salida a la derecha', async () => {
    enAncho()
    const { pantalla } = abrir('admin')
    await pantalla.findByText('Pañal adulto talla M')
    expect(pantalla.getByRole('button', { name: 'Copiar la lista' }).closest('[class*="grid-cols-[3fr_2fr]"]')).not.toBeNull()
  })

  it('6.2: el cuidador sin el permiso llega a Insumos con el foco en su h1', async () => {
    contexto = familiaFalsa({ persona: PERSONA, personaId: PERSONA.id, rol: 'cuidador' } as never)
    const sinPermiso = { type: '/errores/sin-consentimiento', status: 403, finalidad: 'consumo' }
    apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
      // La lista responde de inmediato; Insumos, como en la red, después de que la ruta enfocó su h1.
      if (!/\/consumo\/lista$/.test(config.url ?? '')) await new Promise((r) => setTimeout(r, 60))
      const respuesta: AxiosResponse = { data: sinPermiso, status: 403, statusText: '', headers: {}, config, request: {} }
      throw new AxiosError('HTTP 403', AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    }
    /** Lo mismo que hace AppFamilia (2.6): al cambiar de ruta, el foco va al h1. */
    function DosRutas() {
      const ruta = useRuta()
      useEffect(() => {
        const t = window.setTimeout(() => document.getElementById('titulo-pagina')?.focus(), 0)
        return () => window.clearTimeout(t)
      }, [ruta])
      return ruta === '/insumos/lista' ? <ListaDeInsumos /> : <Insumos />
    }
    render(<DosRutas />)

    await waitFor(() => expect(window.location.pathname).toBe('/insumos'))
    const h1 = await screen.findByRole('heading', { level: 1, name: 'Antes de calcular, un permiso' })
    await waitFor(() => expect(h1).toHaveFocus())
    // Y sigue ahí: nada lo devuelve al body.
    await new Promise((r) => setTimeout(r, 200))
    expect(h1).toHaveFocus()
  })
})

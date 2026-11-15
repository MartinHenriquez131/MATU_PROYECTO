// MATU-63, especificación 7: el campo del código de retiro y cada resultado (correcto, no es,
// bloqueado, vencido, usado, cancelada, sin código, 429, 503 y red). El código va solo en el cuerpo,
// nunca a la URL, un aviso ni el almacenamiento, y se borra al cerrar la revisión. Datos sintéticos.
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AppComercio } from '../src/comercio/AppComercio'
import type { ParteVista } from '../src/compartido/api/comercio'
import { apiComercio, conRegionesVivas, ID, partesDeEjemplo, vigilarAlmacenamiento } from './comercioFalso'
import type { RespuestaFalsa } from './apiFalsa'

const u = () => userEvent.setup({ delay: null })
const CAMPO = 'Código de retiro (6 números)'

/** El resultado de `validar-codigo` con la parte como queda. */
function resultado(tipo: string, intentos: number, cambio: Partial<ParteVista> = {}): RespuestaFalsa {
  const parte = { ...partesDeEjemplo().find((p) => p.id === ID.lista)!, ...cambio }
  return { status: 200, cuerpo: { resultado: tipo, intentos_restantes: intentos, parte } }
}

async function abrirLista(respuesta?: RespuestaFalsa, partes?: ParteVista[]) {
  const api = apiComercio({ partes, sobre: (l) => (l.endsWith('/validar-codigo') ? respuesta : undefined) })
  window.history.replaceState(null, '', '/comercio')
  const regiones = conRegionesVivas(<AppComercio />)
  await screen.findByRole('heading', { level: 2, name: /Listos para retirar/ })
  const usuario = u()
  await usuario.click(screen.getByRole('button', { name: /Pedido P5Q8ZA/ }))
  await screen.findByRole('heading', { level: 1, name: 'Pedido P5Q8ZA' })
  return { api, usuario, ...regiones }
}

async function revisar(usuario: ReturnType<typeof u>, codigo: string) {
  await usuario.type(screen.getByLabelText(CAMPO), codigo)
  await usuario.click(screen.getByRole('button', { name: 'Revisar código' }))
}

const nota = (titulo: string) => screen.getByText(titulo).closest('[tabindex="-1"]')

describe('El campo del código', () => {
  it('numérico, sin autocompletar ni sugerir los SMS del teléfono, y al pegar «482 173» queda «482173»', async () => {
    const { usuario } = await abrirLista()
    const campo = screen.getByLabelText(CAMPO)
    expect(campo).toHaveAttribute('inputmode', 'numeric')
    expect(campo).toHaveAttribute('autocomplete', 'off')
    expect(campo).not.toHaveAttribute('autocomplete', 'one-time-code')
    expect(campo).toHaveClass('digitos', 'text-3xl', 'angosto:text-2xl')
    campo.focus()
    await usuario.paste('482 173')
    expect(campo).toHaveValue('482173')
    await usuario.clear(campo)
    await usuario.type(campo, '48-21-73-9')
    expect(campo).toHaveValue('482173')
  })

  it('con menos de 6 números no envía: el mensaje y el foco en el campo', async () => {
    const { api, usuario } = await abrirLista()
    await revisar(usuario, '4821')
    expect(screen.getByText('Escribe los 6 números del código.')).toBeVisible()
    expect(screen.getByLabelText(CAMPO)).toHaveFocus()
    expect(api.lineas().some((l) => l.endsWith('/validar-codigo'))).toBe(false)
  })
})

describe('Los resultados', () => {
  it('correcto: la nota recibe el foco y dice qué entregar; el campo ya no existe y se ve «Pedido retirado.»', async () => {
    const almacen = vigilarAlmacenamiento()
    const { api, usuario, amable } = await abrirLista(resultado('correcto', 5, { estado: 'retirada', estado_codigo: 'usado', retirada_en: '2026-11-13T17:25:00Z' }))
    await revisar(usuario, '482173')
    await waitFor(() => expect(amable).toHaveTextContent('Código correcto. Entrega el pedido P5Q8ZA.'))
    await waitFor(() => expect(nota('Código correcto. Entrega el pedido P5Q8ZA.')).toHaveFocus())
    expect(screen.getByText('Entrega estos productos:')).toBeVisible()
    // Descuenta lo que falta: 2 pañales y 2 de 3 suplementos.
    expect(screen.getByText(/2\s×\sPañal adulto M x30/)).toBeVisible()
    expect(screen.getByText(/2\s×\sSuplemento vainilla x12/)).toBeVisible()
    expect(screen.queryByLabelText(CAMPO)).toBeNull()
    expect(screen.getByText('Pedido retirado.')).toBeVisible()
    // El código solo en el cuerpo.
    const p = api.peticiones.find((x) => x.linea.endsWith('/validar-codigo'))!
    expect(p.linea).toBe(`POST /v1/comercio/partes/${ID.lista}/validar-codigo`)
    expect(p.cuerpo).toEqual({ codigo: '482173' })
    expect(window.location.href).not.toContain('482173')
    expect(amable.textContent).not.toContain('482173')
    expect(almacen).toEqual([])
  })

  it('no es: «No entregues el pedido todavía.», los intentos en negrita, el campo sigue con lo escrito', async () => {
    const { usuario, urgente } = await abrirLista(resultado('no_es', 3))
    await revisar(usuario, '111222')
    await waitFor(() => expect(urgente).toHaveTextContent('Ese código no es el de este pedido. No entregues el pedido todavía. Te quedan 3 intentos.'))
    expect(screen.getByText('3 intentos').tagName).toBe('B')
    const campo = screen.getByLabelText(CAMPO)
    expect(campo).toHaveValue('111222')
    expect(campo).toHaveAttribute('aria-invalid', 'true')
    await waitFor(() => expect(nota('Ese código no es el de este pedido.')).toHaveFocus())
  })

  it('no es con 1: «Te queda 1 intento.»', async () => {
    const { usuario, urgente } = await abrirLista(resultado('no_es', 1))
    await revisar(usuario, '111222')
    await waitFor(() => expect(urgente).toHaveTextContent('Te queda 1 intento.'))
  })

  it.each([
    ['bloqueado', 'El código se bloqueó por demasiados intentos.', 'No entregues el pedido. Avisa a MATU: contacto@example.com.', {}],
    ['vencido', 'Este código venció.', 'No entregues el pedido todavía. Avisa a MATU para que le den un código nuevo a quien viene a buscarlo: contacto@example.com.', {}],
    ['usado', 'Este pedido ya se retiró.', 'No lo entregues de nuevo.', { estado: 'retirada' }],
    ['cancelada', 'Este pedido se canceló. No lo prepares.', 'No lo entregues. Si ya lo preparaste, vuelve a dejar los productos en su lugar.', { estado: 'cancelada' }],
    ['sin_codigo', 'Todavía no hay un código para este pedido. Avisa a MATU: contacto@example.com.', null, {}],
  ] as const)('%s: su nota por la región urgente, el código se borra y el campo desaparece', async (tipo, titulo, texto, cambio) => {
    const { usuario, urgente } = await abrirLista(resultado(tipo, 0, cambio as Partial<ParteVista>))
    await revisar(usuario, '123456')
    await waitFor(() => expect(urgente).toHaveTextContent(titulo))
    if (texto) expect(urgente).toHaveTextContent(texto)
    expect(screen.queryByLabelText(CAMPO)).toBeNull()
    expect(urgente.textContent).not.toContain('123456')
  })

  it('429: «Hubo muchos intentos…», con los minutos y el botón con aria-disabled', async () => {
    const { usuario, amable, api } = await abrirLista({ status: 429, cuerpo: { type: '/errores/demasiados-intentos', status: 429 }, cabeceras: { 'retry-after': '120' } })
    await revisar(usuario, '123456')
    await waitFor(() => expect(amable.textContent?.replace(/ /g, ' ')).toContain('Hubo muchos intentos con códigos en poco tiempo. Espera 2 minutos y vuelve a intentarlo.'))
    const boton = screen.getByRole('button', { name: 'Revisar código' })
    expect(boton).toHaveAttribute('aria-disabled', 'true')
    await usuario.click(boton)
    expect(api.lineas().filter((l) => l.endsWith('/validar-codigo'))).toHaveLength(1)
  })

  it.each([
    ['503', { status: 503, cuerpo: { type: '/errores/servicio-no-disponible', status: 503 } }],
    ['red', { status: 500, cuerpo: { type: '/errores/interno', status: 500 } }],
  ] as const)('%s: «No pudimos revisar el código.» con «No entregues…», y el campo sigue con lo escrito', async (_, respuesta) => {
    const { usuario, urgente } = await abrirLista(respuesta)
    await revisar(usuario, '123456')
    await waitFor(() => expect(urgente).toHaveTextContent('No pudimos revisar el código. Revisa tu conexión y vuelve a intentarlo. No entregues el pedido hasta ver «Código correcto».'))
    expect(screen.getByLabelText(CAMPO)).toHaveValue('123456')
  })

  it('al abrir una parte lista con el código vencido, la nota sin rol ni foco, y sin campo', async () => {
    const partes = partesDeEjemplo().map((p) => (p.id === ID.lista ? { ...p, estado_codigo: 'vencido' as const } : p))
    const { amable, urgente } = await abrirLista(undefined, partes)
    expect(screen.getByText('Este código venció.')).toBeVisible()
    expect(screen.queryByLabelText(CAMPO)).toBeNull()
    expect(urgente).toBeEmptyDOMElement()
    expect(amable.textContent).not.toContain('venció')
  })
})

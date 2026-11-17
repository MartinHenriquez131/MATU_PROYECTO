// MATU-81, especificación 2, 3 y 4: la entrada en dos pasos (contraseña y código del teléfono) con
// cada resultado, la cuenta que no es del equipo, la entrada vencida y el desafío solo en memoria.
// Solo datos sintéticos: la cuenta operacion@example.com y el código fijo del doble.
import { configure, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { AppOperacion } from '../src/operacion/AppOperacion'
import { apiOperacion, CLAVE, CODIGO_MFA, conRegionesVivas, CORREO_OPERACION, horaDeChile, vigilarAlmacenamiento } from './operacionFalso'
import type { RespuestaDoble } from '../doble/operacion'

// Con la suite completa en paralelo, montar la consola puede tardar más que el segundo por omisión.
configure({ asyncUtilTimeout: 5000 })

const u = () => userEvent.setup({ delay: null })
const CAMPO = 'Código de 6 números'

function abrir(ruta: string) {
  window.history.replaceState(null, '', ruta)
  return conRegionesVivas(<AppOperacion />)
}

async function pasoUno(usuario: ReturnType<typeof u>, correo = CORREO_OPERACION, clave = CLAVE) {
  await usuario.type(screen.getByLabelText('Tu correo'), correo)
  await usuario.type(screen.getByLabelText('Tu contraseña'), clave)
  await usuario.click(screen.getByRole('button', { name: 'Seguir' }))
}

/** Entra hasta el paso 2 con la API dada. */
async function hastaElCodigo(sobre?: (linea: string, cuerpo: unknown) => RespuestaDoble | undefined) {
  apiOperacion({ tipo: null })
  const regiones = abrir('/operacion/entrar')
  await screen.findByRole('heading', { level: 1, name: 'Entrar a operación' })
  const api = apiOperacion({ tipo: null, sobre })
  const usuario = u()
  await pasoUno(usuario)
  await screen.findByRole('heading', { level: 1, name: 'Escribe el código de tu teléfono' })
  return { api, usuario, ...regiones }
}

describe('Entrar al equipo de MATU, paso 1', () => {
  it('sin entrada, /operacion lleva a /operacion/entrar con su título, el distintivo y el enlace a la familia', async () => {
    apiOperacion({ tipo: null })
    abrir('/operacion')
    expect(await screen.findByRole('heading', { level: 1, name: 'Entrar a operación' })).toBeVisible()
    expect(window.location.pathname).toBe('/operacion/entrar')
    expect(document.title).toBe('Entrar a operación · MATU')
    expect(screen.getByText('Para el equipo de MATU. Después de la contraseña te pedimos el código de tu teléfono.')).toBeVisible()
    expect(screen.getByText('Piloto académico')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Seguir' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'app de MATU para familias' })).toHaveAttribute('href', '/entrar')
  })

  it('sin datos no envía: «Escribe tu correo y tu contraseña.»', async () => {
    apiOperacion({ tipo: null })
    abrir('/operacion/entrar')
    await screen.findByRole('heading', { level: 1, name: 'Entrar a operación' })
    const api = apiOperacion({ tipo: null })
    await u().click(screen.getByRole('button', { name: 'Seguir' }))
    expect(screen.getByText('Escribe tu correo y tu contraseña.')).toBeVisible()
    expect(api.lineas()).toEqual([])
  })

  it('401: el correo o la contraseña no coinciden, por la región urgente', async () => {
    apiOperacion({ tipo: null })
    const { urgente } = abrir('/operacion/entrar')
    await screen.findByRole('heading', { level: 1, name: 'Entrar a operación' })
    apiOperacion({ tipo: null })
    await pasoUno(u(), CORREO_OPERACION, 'otra-clave-sintetica')
    await waitFor(() => expect(urgente).toHaveTextContent('El correo o la contraseña no coinciden. Revísalos y vuelve a intentarlo.'))
  })

  it('una cuenta de familia ve «Esta cuenta no es del equipo de MATU.», su entrada se cierra y la contraseña se borra', async () => {
    apiOperacion({ tipo: null })
    const { amable } = abrir('/operacion/entrar')
    await screen.findByRole('heading', { level: 1, name: 'Entrar a operación' })
    const api = apiOperacion({ tipo: null })
    await pasoUno(u(), 'familia@example.com')
    await waitFor(() => expect(amable).toHaveTextContent('Esta cuenta no es del equipo de MATU. Si atiendes un comercio, entra en la entrada del comercio. Si cuidas a alguien, entra en la app para familias.'))
    expect(api.lineas()).toContain('POST /v1/sesiones/cerrar')
    expect(screen.getByLabelText('Tu contraseña')).toHaveValue('')
    expect(window.location.pathname).toBe('/operacion/entrar')
    expect(api.lineas().some((l) => l.startsWith('GET /v1/operacion'))).toBe(false)
  })

  it('al abrir con una entrada de familia, el mismo aviso', async () => {
    apiOperacion({ tipo: 'familia' })
    abrir('/operacion')
    expect(await screen.findByText('Esta cuenta no es del equipo de MATU.')).toBeVisible()
    expect(window.location.pathname).toBe('/operacion/entrar')
  })
})

describe('Entrar al equipo de MATU, paso 2', () => {
  it('la contraseña sale de la pantalla, el foco va al h1 del paso 2 y el campo es el de un código de un solo uso', async () => {
    const almacen = vigilarAlmacenamiento()
    const { api } = await hastaElCodigo()
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveFocus())
    expect(api.peticiones.find((p) => p.linea === 'POST /v1/sesiones')).toBeTruthy()
    expect(screen.queryByLabelText('Tu contraseña')).toBeNull()
    const campo = screen.getByLabelText(CAMPO)
    expect(campo).toHaveAttribute('autocomplete', 'one-time-code')
    expect(campo).toHaveAttribute('inputmode', 'numeric')
    expect(campo).toHaveAttribute('type', 'text')
    // «Tienes hasta las HH:MM para escribirlo.», de `desafio_expira_en`.
    expect(screen.getByText(/^Tienes hasta las \d{2}:\d{2} para escribirlo\.$/)).toBeVisible()
    // El desafío nunca va al almacenamiento ni a la URL.
    expect(almacen).toEqual([])
    expect(window.location.href).not.toContain('desafio')
  })

  it('pegar «246 810» deja «246810»; con 6 números no envía solo; «Entrar» abre la consola con la hora de la entrada', async () => {
    const almacen = vigilarAlmacenamiento()
    const { api, usuario } = await hastaElCodigo()
    const campo = screen.getByLabelText(CAMPO)
    campo.focus()
    await usuario.paste('246 810')
    expect(campo).toHaveValue(CODIGO_MFA)
    expect(api.lineas()).not.toContain('POST /v1/sesiones/mfa')
    await usuario.click(screen.getByRole('button', { name: 'Entrar' }))
    const h1 = await screen.findByRole('heading', { level: 1, name: 'Pedidos' })
    await waitFor(() => expect(h1).toHaveFocus())
    expect(window.location.pathname).toBe('/operacion')
    expect(document.title).toBe('Pedidos · Operación · MATU')
    const mfa = api.peticiones.find((p) => p.linea === 'POST /v1/sesiones/mfa')!
    expect((mfa.cuerpo as { codigo: string }).codigo).toBe(CODIGO_MFA)
    expect((mfa.cuerpo as { desafio: string }).desafio).toHaveLength(43)
    // 3: la barra dice hasta cuándo vale la entrada (12 horas), de `sesion_vence_en`.
    const vence = horaDeChile(new Date(Date.now() + 12 * 3_600_000).toISOString())
    expect(screen.getByText(new RegExp(`^Tu entrada vale hasta las (${vence}|\\d{2}:\\d{2})\\.$`))).toBeVisible()
    expect(screen.getByText('Operación de MATU')).toBeVisible()
    expect(screen.getByText('Equipo de MATU')).toBeVisible()
    expect(screen.getByRole('navigation', { name: 'Secciones de operación' })).toBeVisible()
    expect(almacen).toEqual([])
  })

  it('con menos de 6 números no envía: el mensaje y el foco en el campo', async () => {
    const { api, usuario } = await hastaElCodigo()
    await usuario.type(screen.getByLabelText(CAMPO), '2468')
    await usuario.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(screen.getByText('Escribe los 6 números del código.')).toBeVisible()
    expect(screen.getByLabelText(CAMPO)).toHaveFocus()
    expect(api.lineas()).not.toContain('POST /v1/sesiones/mfa')
  })

  it.each([
    ['no coincide', '135790'],
    ['ya usado', '111111'],
  ])('%s: «Ese código no coincide.» por la región urgente, la nota recibe el foco y el campo conserva lo escrito', async (_, codigo) => {
    const { usuario, urgente } = await hastaElCodigo()
    await usuario.type(screen.getByLabelText(CAMPO), codigo)
    await usuario.click(screen.getByRole('button', { name: 'Entrar' }))
    await waitFor(() => expect(urgente).toHaveTextContent('Ese código no coincide. Revisa que sea el de MATU en tu aplicación y escribe el que se ve ahora.'))
    await waitFor(() => expect(screen.getByText('Ese código no coincide.').closest('[tabindex="-1"]')).toHaveFocus())
    const campo = screen.getByLabelText(CAMPO)
    expect(campo).toHaveValue(codigo)
    expect(campo).toHaveAttribute('aria-invalid', 'true')
  })

  it('cinco fallos: 429 con los minutos; se quitan el campo, «Entrar» y el plazo, y «Volver a la contraseña» espera', async () => {
    const { usuario, urgente } = await hastaElCodigo((l) =>
      l === 'POST /v1/sesiones/mfa' ? { status: 429, cuerpo: { type: '/errores/mfa-bloqueado', status: 429, minutos_espera: 15 }, cabeceras: { 'retry-after': '900' } } : undefined,
    )
    await usuario.type(screen.getByLabelText(CAMPO), '135790')
    await usuario.click(screen.getByRole('button', { name: 'Entrar' }))
    await waitFor(() => expect(urgente.textContent?.replace(/ /g, ' ')).toContain('Hubo 5 códigos que no coinciden. Espera 15 minutos y vuelve a entrar con tu contraseña.'))
    expect(screen.queryByLabelText(CAMPO)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Entrar' })).toBeNull()
    // 4.4 (v1.1): ya no hay nada que escribir, así que el plazo también se quita.
    expect(screen.queryByText(/^Tienes hasta las/)).toBeNull()
    const volver = screen.getByRole('button', { name: 'Volver a la contraseña' })
    expect(volver).toHaveAttribute('aria-disabled', 'true')
    // El estilo deshabilitado de `Boton`.
    expect(volver).toHaveClass('aria-disabled:cursor-not-allowed', 'aria-disabled:opacity-60')
    await usuario.click(volver)
    expect(screen.getByRole('heading', { level: 1, name: 'Escribe el código de tu teléfono' })).toBeVisible()
  })

  it('el desafío venció: vuelve al paso 1 con el correo escrito y «Pasaron más de 5 minutos.» con el foco', async () => {
    const { usuario, amable } = await hastaElCodigo()
    await usuario.type(screen.getByLabelText(CAMPO), '222222')
    await usuario.click(screen.getByRole('button', { name: 'Entrar' }))
    await screen.findByRole('heading', { level: 1, name: 'Entrar a operación' })
    await waitFor(() => expect(amable).toHaveTextContent('Pasaron más de 5 minutos. Vuelve a escribir tu contraseña para pedir otro código.'))
    await waitFor(() => expect(screen.getByText('Pasaron más de 5 minutos.').closest('[tabindex="-1"]')).toHaveFocus())
    expect(screen.getByLabelText('Tu correo')).toHaveValue(CORREO_OPERACION)
    expect(screen.getByLabelText('Tu contraseña')).toHaveValue('')
  })

  it('503: «No podemos revisar el código ahora.» y el campo sigue con lo escrito', async () => {
    const { usuario, urgente } = await hastaElCodigo()
    await usuario.type(screen.getByLabelText(CAMPO), '999999')
    await usuario.click(screen.getByRole('button', { name: 'Entrar' }))
    await waitFor(() => expect(urgente).toHaveTextContent('No podemos revisar el código ahora. Vuelve a intentarlo en unos minutos.'))
    expect(screen.getByLabelText(CAMPO)).toHaveValue('999999')
  })

  it('«Volver a la contraseña» borra el desafío y vuelve al paso 1 con el correo', async () => {
    const { usuario } = await hastaElCodigo()
    await usuario.click(screen.getByRole('button', { name: 'Volver a la contraseña' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Entrar a operación' })).toBeVisible()
    expect(screen.getByLabelText('Tu correo')).toHaveValue(CORREO_OPERACION)
  })
})

describe('La entrada que vence', () => {
  it('401 `mfa-requerido` de una ruta: a la contraseña con «Tu entrada venció…», y vuelve a la misma sección', async () => {
    apiOperacion({ sobre: (l) => (l === 'GET /v1/operacion/catalogo' ? { status: 401, cuerpo: { type: '/errores/mfa-requerido', status: 401 } } : undefined) })
    const { amable } = abrir('/operacion/catalogo')
    await screen.findByRole('heading', { level: 1, name: 'Entrar a operación' })
    await waitFor(() => expect(amable).toHaveTextContent('Tu entrada venció. Vuelve a entrar con tu contraseña y el código de tu teléfono.'))
    expect(window.location.pathname).toBe('/operacion/entrar')
    apiOperacion({ tipo: null })
    const usuario = u()
    await pasoUno(usuario)
    await usuario.type(await screen.findByLabelText(CAMPO), CODIGO_MFA)
    await usuario.click(screen.getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Catálogo' })).toBeVisible()
    expect(window.location.pathname).toBe('/operacion/catalogo')
  })

  it('404 de una lista (la cuenta no es de operación): a Entrar con «Esta cuenta no es del equipo de MATU.»', async () => {
    apiOperacion({ sobre: (l) => (l === 'GET /v1/operacion/pedidos' ? { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404 } } : undefined) })
    abrir('/operacion')
    expect(await screen.findByText('Esta cuenta no es del equipo de MATU.')).toBeVisible()
    expect(window.location.pathname).toBe('/operacion/entrar')
  })

  it('«Salir» cierra la entrada y vuelve a Entrar con el aviso de salida', async () => {
    const api = apiOperacion()
    const { amable } = abrir('/operacion')
    await screen.findByRole('heading', { level: 1, name: 'Pedidos' })
    await u().click(screen.getByRole('button', { name: 'Salir' }))
    await screen.findByRole('heading', { level: 1, name: 'Entrar a operación' })
    expect(api.lineas()).toContain('POST /v1/sesiones/cerrar')
    await waitFor(() => expect(amable).toHaveTextContent('Saliste de MATU.'))
  })
})

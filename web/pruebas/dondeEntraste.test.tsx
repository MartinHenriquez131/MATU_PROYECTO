// MATU-55 (especificación docs/diseno/matu-55-donde-entraste.md v1.1, sección 2): «Dónde entraste»,
// con los teléfonos y computadores, los últimos ingresos, el diálogo de cerrar y cada estado. Solo
// datos sintéticos.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DondeEntraste } from '../src/familia/DondeEntraste'
import { ACTUAL, apiCuenta, dialogoDeJsdom, EVENTOS, fijarAhora, ID_PC, IPAD, PC, problema } from './dondeEntrasteFalso'
import { familiaFalsa } from './familiaFalsa'
import { POLITICA_DE_PRUEBA, responderPolitica } from './politicaFalsa'

const salir = vi.fn(async () => {})
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa({ salir } as never),
}))

beforeEach(() => {
  fijarAhora()
  dialogoDeJsdom()
  salir.mockClear()
})
afterEach(() => {
  vi.useRealTimers()
})

const u = () => userEvent.setup({ delay: null })
const seccion = (nombre: string) => screen.getByRole('region', { name: nombre })

describe('«Dónde entraste»: tus teléfonos y computadores (2.4)', () => {
  it('el actual va primero, con «Este teléfono» en palabra y figura, y «Salir»; los demás, «Cerrar en ese…» según la clase', async () => {
    apiCuenta()
    responderPolitica()
    render(<DondeEntraste />)

    const lista = await within(seccion('Tus teléfonos y computadores')).findByRole('list')
    const filas = within(lista).getAllByRole('listitem')
    expect(filas).toHaveLength(3)

    const [primera, segunda, tercera] = filas
    expect(primera).toHaveTextContent('Chrome en Android')
    const marca = within(primera).getByText('Este teléfono')
    expect(marca.querySelector('svg.lucide-circle-dot')).not.toBeNull()
    expect(within(primera).getByRole('button', { name: 'Salir' })).toBeInTheDocument()
    expect(within(primera).queryByRole('button', { name: /Cerrar en ese/ })).toBeNull()

    // Cada botón dice cuál cierra por su descripción, sin cambiar el texto visible (WCAG 2.5.3).
    const cerrarPc = within(segunda).getByRole('button', { name: 'Cerrar en ese computador' })
    expect(cerrarPc).toHaveAccessibleDescription('Chrome en Windows')
    expect(within(tercera).getByRole('button', { name: 'Cerrar en ese navegador' })).toHaveAccessibleDescription('Safari en iPad')
  })

  it('«Última vez»: hoy, ayer o la fecha, y la hora; sin último uso, la de creación', async () => {
    apiCuenta()
    responderPolitica()
    render(<DondeEntraste />)

    const filas = within(await within(seccion('Tus teléfonos y computadores')).findByRole('list')).getAllByRole('listitem')
    expect(filas[0]).toHaveTextContent('Última vez: hoy a las 10:14')
    expect(filas[1]).toHaveTextContent('Última vez: ayer a las 18:40')
    expect(filas[2]).toHaveTextContent('Última vez: 01/11/2026 a las 09:05')
    const hora = filas[2].querySelector('time')!
    expect(hora).toHaveAttribute('dateTime', IPAD.creado_en)
    expect(hora.querySelectorAll('.cifras')).toHaveLength(2)
  })

  it('«Salir» en la fila del actual sale sin diálogo, como el de la cabecera', async () => {
    apiCuenta()
    responderPolitica()
    render(<DondeEntraste />)
    await u().click(await screen.findByRole('button', { name: 'Salir' }))
    expect(salir).toHaveBeenCalledTimes(1)
    expect(document.querySelector('dialog')).toBeNull()
  })

  it('error: «No pudimos traer dónde entraste…» y «Volver a intentar»; los ingresos se siguen viendo', async () => {
    const api = apiCuenta({ 'GET ^/v1/dispositivos$': [problema(500), { status: 200, cuerpo: { items: [ACTUAL] } }] })
    responderPolitica()
    render(<DondeEntraste />)

    const aviso = await screen.findByText('No pudimos traer dónde entraste. Revisa tu conexión e inténtalo de nuevo.')
    expect(aviso.closest('[data-aviso]')).toHaveAttribute('data-aviso', 'alert')
    expect(await within(seccion('Últimos ingresos')).findByText('Entraste')).toBeInTheDocument()

    await u().click(within(seccion('Tus teléfonos y computadores')).getByRole('button', { name: 'Volver a intentar' }))
    expect(await screen.findByText('Chrome en Android')).toBeInTheDocument()
    expect(api.de('GET', '/v1/dispositivos')).toHaveLength(2)
  })

  it('una lista vacía se trata como error: el actual siempre está', async () => {
    apiCuenta({ 'GET ^/v1/dispositivos$': { status: 200, cuerpo: { items: [] } } })
    responderPolitica()
    render(<DondeEntraste />)
    expect(await screen.findByText(/No pudimos traer dónde entraste/)).toBeInTheDocument()
  })
})

describe('«Dónde entraste»: los últimos ingresos (2.5)', () => {
  it('agrupados por día con h3, en el orden del servidor, con su frase y su cola', async () => {
    apiCuenta()
    responderPolitica()
    render(<DondeEntraste />)

    const ingresos = seccion('Últimos ingresos')
    await within(ingresos).findByText('Entraste')
    expect(within(ingresos).getByRole('heading', { level: 2, name: 'Últimos ingresos' })).toBeInTheDocument()
    expect(within(ingresos).getByText('Los de los últimos 90 días, hasta 20.')).toBeInTheDocument()
    expect(within(ingresos).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['Hoy', 'Ayer', 'El lunes', 'El 01/11/2026'])

    const lineas = within(ingresos).getAllByRole('listitem')
    expect(lineas.map((l) => l.textContent)).toEqual([
      'Entrastea las 10:14 · Chrome en Android (este teléfono)',
      'Se pidió un código para recuperar tu cuentaa las 09:02Si no lo pediste tú, no compartas el código con nadie.',
      'Cambiaste tu contraseñaa las 21:15',
      'Te sacamos de MATU en Chrome en Windows porque notamos un uso extraño.a las 19:00',
      'Cerraste MATU en Chrome en Windowsa las 12:00',
      'Salistea las 11:00 · en un teléfono o computador que ya no está en tu lista',
      'Activaste los avisos en Chrome en Androida las 12:00',
    ])
    const hora = lineas[0].querySelector('time')!
    expect(hora).toHaveAttribute('dateTime', EVENTOS[0].ocurrido_en)
    expect(hora).toHaveAttribute('title', '12/11/2026 10:14')
  })

  it('el uso extraño y el código pedido van en `atenta` con ShieldAlert; ninguna línea en `pronto`', async () => {
    apiCuenta()
    responderPolitica()
    render(<DondeEntraste />)
    const ingresos = seccion('Últimos ingresos')
    await within(ingresos).findByText('Entraste')
    const lineas = within(ingresos).getAllByRole('listitem')
    for (const i of [1, 3]) {
      const circulo = lineas[i].querySelector('span[aria-hidden]')!
      expect(circulo).toHaveClass('bg-atenta-fondo', 'text-atenta')
      expect(circulo.querySelector('svg.lucide-shield-alert')).not.toBeNull()
    }
    expect(lineas[0].querySelector('span[aria-hidden]')).toHaveClass('bg-rocio', 'text-turquesa')
    expect(ingresos.innerHTML).not.toMatch(/pronto/)
  })

  it('un tipo que el cliente no conoce no se muestra, y la pantalla no se rompe', async () => {
    const raro = { tipo: 'algo_nuevo', ocurrido_en: '2026-11-12T13:00:00Z', dispositivo: null }
    apiCuenta({ 'GET ^/v1/yo/ingresos$': { status: 200, cuerpo: { eventos: [raro, EVENTOS[0]], hay_mas: false } } })
    responderPolitica()
    render(<DondeEntraste />)
    const ingresos = seccion('Últimos ingresos')
    await within(ingresos).findByText('Entraste')
    expect(within(ingresos).getAllByRole('listitem')).toHaveLength(1)
  })

  it('la ayuda usa la clase del actual: en un computador, «Cierra MATU en ese computador»', async () => {
    const actualPc = { ...PC, actual: true }
    apiCuenta({ 'GET ^/v1/dispositivos$': { status: 200, cuerpo: { items: [actualPc, { ...ACTUAL, actual: false }] } } })
    responderPolitica()
    render(<DondeEntraste />)
    expect(
      await screen.findByText(
        '¿No reconoces un ingreso? Cierra MATU en ese computador. Para cambiar tu contraseña, sal de MATU y toca «¿Olvidaste tu contraseña?» al entrar.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('Este computador')).toBeInTheDocument()
  })

  it.each([
    [false, 'Si necesitas los ingresos anteriores a 90 días, escribe a privacidad@example.org desde el correo de tu cuenta.'],
    [true, 'Mostramos los 20 más recientes. Para ver los demás, o los anteriores a 90 días, escribe a privacidad@example.org desde el correo de tu cuenta.'],
  ])('hay_mas=%s: el párrafo de lo que no se muestra, con el correo en mailto:', async (hayMas, texto) => {
    apiCuenta({ 'GET ^/v1/yo/ingresos$': { status: 200, cuerpo: { eventos: EVENTOS, hay_mas: hayMas } } })
    responderPolitica()
    render(<DondeEntraste />)
    const correo = await screen.findByRole('link', { name: 'privacidad@example.org' })
    expect(correo).toHaveAttribute('href', 'mailto:privacidad@example.org')
    expect(correo).toHaveClass('[overflow-wrap:anywhere]')
    expect(correo.closest('p')).toHaveTextContent(texto)
  })

  it('sin correo configurado: con hay_mas solo «Mostramos los 20 más recientes.»; sin hay_mas, nada', async () => {
    apiCuenta({ 'GET ^/v1/yo/ingresos$': [{ status: 200, cuerpo: { eventos: EVENTOS, hay_mas: true } }] })
    const politica = responderPolitica({ status: 200, cuerpo: { ...POLITICA_DE_PRUEBA, correo_contacto: null } })
    const { unmount } = render(<DondeEntraste />)
    expect(await screen.findByText('Mostramos los 20 más recientes.')).toBeInTheDocument()
    await vi.waitFor(() => expect(politica).toHaveLength(1))
    unmount()

    apiCuenta()
    responderPolitica({ status: 200, cuerpo: { ...POLITICA_DE_PRUEBA, correo_contacto: null } })
    const { container } = render(<DondeEntraste />)
    await screen.findByText('Entraste')
    expect(container.querySelector('a[href^="mailto:"]')).toBeNull()
    expect(screen.queryByText(/anteriores a 90 días/)).toBeNull()
  })

  it('vacío: la nota, sin «¿No reconoces un ingreso?», pero con el párrafo del correo', async () => {
    apiCuenta({ 'GET ^/v1/yo/ingresos$': { status: 200, cuerpo: { eventos: [], hay_mas: false } } })
    responderPolitica()
    render(<DondeEntraste />)
    expect(await screen.findByText('No hay ingresos en los últimos 90 días.')).toBeInTheDocument()
    expect(screen.queryByText(/No reconoces un ingreso/)).toBeNull()
    expect(await screen.findByText(/Si necesitas los ingresos anteriores a 90 días/)).toBeInTheDocument()
  })

  it('error: «No pudimos traer tus últimos ingresos…» y «Volver a intentar»; los teléfonos se siguen viendo', async () => {
    apiCuenta({ 'GET ^/v1/yo/ingresos$': [problema(503), { status: 200, cuerpo: { eventos: EVENTOS, hay_mas: false } }] })
    responderPolitica()
    render(<DondeEntraste />)
    expect(await screen.findByText('No pudimos traer tus últimos ingresos. Revisa tu conexión e inténtalo de nuevo.')).toBeInTheDocument()
    expect(within(seccion('Tus teléfonos y computadores')).getByText('Chrome en Android')).toBeInTheDocument()
    await u().click(within(seccion('Últimos ingresos')).getByRole('button', { name: 'Volver a intentar' }))
    expect(await within(seccion('Últimos ingresos')).findByText('Entraste')).toBeInTheDocument()
  })
})

describe('«¿Cerrar MATU en…?» (2.6, D8)', () => {
  async function abrir() {
    const api = apiCuenta()
    responderPolitica()
    render(<DondeEntraste />)
    const boton = await screen.findByRole('button', { name: 'Cerrar en ese computador' })
    await u().click(boton)
    const dialogo = screen.getByRole('dialog', { name: '¿Cerrar MATU en Chrome en Windows?' })
    return { api, boton, dialogo }
  }

  it('abre con el foco en el título, dice lo de los 15 minutos y no pide contraseña', async () => {
    const { dialogo } = await abrir()
    expect(within(dialogo).getByRole('heading', { name: '¿Cerrar MATU en Chrome en Windows?' })).toHaveFocus()
    expect(dialogo).toHaveAccessibleDescription('Quien lo use tendrá que volver a entrar con tu correo y tu contraseña. Puede seguir abierto hasta 15 minutos.')
    expect(dialogo.querySelector('input')).toBeNull()
    expect(within(dialogo).getByRole('button', { name: 'Cerrar en ese computador' })).toBeInTheDocument()
  })

  it('«Dejarlo abierto» cierra sin pedir nada y el foco vuelve al botón que lo abrió', async () => {
    const { api, boton, dialogo } = await abrir()
    await u().click(within(dialogo).getByRole('button', { name: 'Dejarlo abierto' }))
    expect(document.querySelector('dialog')).toBeNull()
    await vi.waitFor(() => expect(boton).toHaveFocus())
    expect(api.pedidas.filter((p) => p.metodo === 'DELETE')).toHaveLength(0)
  })

  it('204: la fila sale, «Cerramos MATU en…» recibe el foco y los ingresos se vuelven a pedir', async () => {
    const { api, dialogo } = await abrir()
    await u().click(within(dialogo).getByRole('button', { name: 'Cerrar en ese computador' }))
    const nota = await screen.findByText('Cerramos MATU en Chrome en Windows.')
    const contenedor = nota.closest('[data-aviso]') as HTMLElement
    expect(contenedor).toHaveAttribute('data-aviso', 'status')
    await vi.waitFor(() => expect(contenedor).toHaveFocus())
    expect(document.querySelector('dialog')).toBeNull()
    expect(screen.queryByText('Chrome en Windows', { selector: 'p' })).toBeNull()
    expect(api.de('DELETE', `/v1/dispositivos/${ID_PC}`)).toHaveLength(1)
    await vi.waitFor(() => expect(api.de('GET', '/v1/yo/ingresos')).toHaveLength(2))
  })

  it('404: la fila sale y «Ese computador ya no estaba en tu lista.» en `atenta`', async () => {
    const api = apiCuenta({ 'DELETE ^/v1/dispositivos/': problema(404, 'no-encontrado') })
    responderPolitica()
    render(<DondeEntraste />)
    await u().click(await screen.findByRole('button', { name: 'Cerrar en ese computador' }))
    await u().click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cerrar en ese computador' }))
    const nota = await screen.findByText('Ese computador ya no estaba en tu lista.')
    expect(nota.closest('.bg-atenta-fondo')).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Cerrar en ese computador' })).toBeNull()
    expect(api.de('GET', '/v1/yo/ingresos')).toHaveLength(1)
  })

  it('error o sin red: el diálogo sigue abierto con su error, y la fila sigue', async () => {
    apiCuenta({ 'DELETE ^/v1/dispositivos/': problema(500) })
    responderPolitica()
    render(<DondeEntraste />)
    await u().click(await screen.findByRole('button', { name: 'Cerrar en ese computador' }))
    const dialogo = screen.getByRole('dialog')
    const confirmar = within(dialogo).getByRole('button', { name: 'Cerrar en ese computador' })
    await u().click(confirmar)
    expect(await within(dialogo).findByText('No pudimos cerrar MATU en ese computador. Revisa tu conexión y vuelve a intentarlo.')).toBeInTheDocument()
    expect(dialogo).toHaveAttribute('open')
    expect(confirmar).toHaveFocus()
  })
})

describe('«Dónde entraste»: lo que no se hace', () => {
  it('nada va al almacenamiento del navegador ni a la URL, ningún texto bajo 17 px y sin palabras prohibidas', async () => {
    const guardar = vi.spyOn(Storage.prototype, 'setItem')
    window.history.replaceState(null, '', '/cuenta/donde-entraste')
    apiCuenta()
    responderPolitica()
    const { container } = render(<DondeEntraste />)
    await screen.findByText('Entraste')
    await screen.findByRole('link', { name: 'privacidad@example.org' })
    expect(guardar).not.toHaveBeenCalled()
    expect(window.location.pathname + window.location.search + window.location.hash).toBe('/cuenta/donde-entraste')
    expect(container.innerHTML).not.toMatch(/text-(xs|sm)\b|text-\[/)
    // «IP» solo en la bajada, que dice que no se guarda (criterio 15).
    const sinBajada = container.textContent!.replace('No guardamos tu ubicación ni tu dirección IP.', '')
    expect(sinBajada).not.toMatch(/sesión|dispositivo|\bIP\b|token|evento|auditoría/i)
    // Ningún turquesa macizo en la página (criterio 1).
    expect(container.innerHTML).not.toMatch(/\bbg-turquesa\b/)
  })
})

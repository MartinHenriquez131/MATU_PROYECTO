// MATU-54 (especificación docs/diseno/matu-54-mis-datos.md v1.1, sección 5): «Tus datos», con la cuenta
// y el celular enmascarado, la política, los grupos, los teléfonos, los ingresos, los avisos, los pagos y
// las condiciones; su diálogo y sus estados. Solo datos sintéticos.
import { StrictMode } from 'react'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CopiaDatosCuenta } from '../src/compartido/api/misDatos'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { enmascararCelular, TusDatos } from '../src/familia/TusDatos'
import { familiaFalsa } from './familiaFalsa'
import { apiCopia, copiaComoRespuesta, copiaCuenta, dialogoDeJsdom, fijarAhora, problemaCopia } from './misDatosFalso'

const fijar = vi.fn()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa({ fijar, anunciar: vi.fn() } as never),
}))

let escrituras: string[] = []
beforeEach(() => {
  fijarAhora()
  dialogoDeJsdom()
  fijar.mockClear()
  escrituras = []
  window.history.replaceState(null, '', '/cuenta/datos')
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
})
afterEach(() => {
  vi.useRealTimers()
})

const u = () => userEvent.setup({ delay: null })
const ARCHIVO = 'matu-cuenta-2026-11-12.json'

function abrir(copia: CopiaDatosCuenta = copiaCuenta()) {
  const pedidas = apiCopia(copiaComoRespuesta(copia, ARCHIVO))
  render(
    <StrictMode>
      <RegionesVivas />
      <TusDatos />
    </StrictMode>,
  )
  return pedidas
}
const listo = () => screen.findByRole('button', { name: 'Descargar en un archivo' })
const bloque = (nombre: string) => screen.getByRole('region', { name: nombre })

describe('«Tus datos» (5.1 a 5.4)', () => {
  it('un solo GET a /v1/yo/datos, la bajada y los nueve bloques en orden, también en el índice', async () => {
    const pedidas = abrir()
    await listo()
    expect(pedidas).toEqual([{ linea: 'GET /v1/yo/datos', responseType: 'text' }])
    expect(screen.getByRole('heading', { level: 1, name: 'Tus datos' })).toBeInTheDocument()
    expect(screen.getByText(/Lo que MATU guarda hoy de tu cuenta/)).toHaveTextContent('Lo que MATU guarda hoy de tu cuenta, al 12/11/2026 a las 10:14.')
    const nombres = [
      'Tu cuenta',
      'Política de privacidad',
      'Tus grupos',
      'Tus teléfonos y computadores',
      'Últimos ingresos',
      'Tus avisos',
      'Avisos que te enviamos',
      'Tus pagos',
      'Condiciones de compra que aceptaste',
    ]
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent).filter((t) => t !== 'Índice')).toEqual(nombres)
    expect(within(screen.getAllByRole('navigation', { name: 'Índice' })[0]).getAllByRole('link').map((a) => a.textContent)).toEqual(nombres)
    expect(escrituras).toEqual([])
    expect(window.history.state).toBeNull()
  })

  it('la nota que manda a Grupo familiar, sin nombrar a ninguna persona cuidada', async () => {
    abrir()
    await listo()
    expect(screen.getByText('Lo que guardamos de las personas que cuidas lo ves en Grupo familiar.')).toBeInTheDocument()
    await u().click(screen.getByRole('button', { name: 'Ir a Grupo familiar' }))
    expect(window.location.pathname).toBe('/grupo')
  })

  it('Tu cuenta: el celular enmascarado con «Completo en el archivo.», el canal y la creación', async () => {
    abrir()
    await listo()
    // El celular lleva espacios duros (celularEnPantalla): se comparan como espacios.
    const filas = [...bloque('Tu cuenta').querySelectorAll('dl > div')].map((d) => d.textContent?.replace(/ /g, ' '))
    expect(filas).toEqual([
      'Tu nombreRodrigo Soto',
      'Tu correorodrigo.soto@example.org',
      'Tu celular+56 9 •••• ••37ConfirmadoCompleto en el archivo.',
      'Los códigos te lleganPor WhatsApp',
      'Cuenta creada20/10/2026',
    ])
    expect(bloque('Tu cuenta')).not.toHaveTextContent('55550137')
  })

  it('sin celular, el texto de Tu cuenta y sin la frase del archivo; sin política, «No hay una aceptación registrada.»', async () => {
    const c = copiaCuenta()
    abrir({ ...c, cuenta: { ...c.cuenta, celular: null }, politica: null })
    await listo()
    expect(bloque('Tu cuenta')).toHaveTextContent('Tu cuenta todavía no tiene un celular.')
    expect(bloque('Tu cuenta')).not.toHaveTextContent('Completo en el archivo.')
    expect(bloque('Política de privacidad')).toHaveTextContent('No hay una aceptación registrada.')
  })

  it('la política, los grupos con su rol en palabra y el permiso del pagador', async () => {
    abrir()
    await listo()
    const politica = bloque('Política de privacidad')
    expect(politica).toHaveTextContent('Aceptaste la versión 0.16 el 20/10/2026 a las 18:15.')
    expect(within(politica).getByText(/^Huella:/)).toHaveClass('break-all')
    const [soto, perez] = within(bloque('Tus grupos')).getAllByRole('listitem')
    expect(soto).toHaveTextContent('Familia SotoPagaTe uniste el 21/10/2026.No ve la ficha')
    expect(soto.querySelector('svg.lucide-eye-off')).not.toBeNull()
    expect(perez).toHaveTextContent('Familia PérezAdministra el grupoTe uniste el 22/10/2026.')
    expect(perez).not.toHaveTextContent('ficha')
  })

  it('los teléfonos y computadores, sin acciones ni el actual, con el cerrado en palabra y figura', async () => {
    abrir()
    await listo()
    const b = bloque('Tus teléfonos y computadores')
    const [android, linux] = within(b).getAllByRole('listitem')
    expect(android).toHaveTextContent('Chrome en AndroidDesde el 20/10/2026.Última vez: 12/11/2026 a las 10:00Recibe avisos.')
    expect(android).not.toHaveTextContent('Este teléfono')
    expect(linux).toHaveTextContent('Cerrado')
    expect(linux.querySelector('svg.lucide-circle')).not.toBeNull()
    expect(linux).toHaveTextContent('Se cerró el 03/11/2026 a las 09:00.')
    expect(within(b).queryByRole('button', { name: /Cerrar en ese/ })).toBeNull()
    await u().click(within(b).getByRole('button', { name: 'Ver dónde entraste' }))
    expect(window.location.pathname).toBe('/cuenta/donde-entraste')
  })

  it('últimos ingresos: «Pediste una copia de tus datos» con Download, sin «(este teléfono)», y lo anterior a 90 días va en el archivo', async () => {
    abrir()
    await listo()
    const b = bloque('Últimos ingresos')
    expect(within(b).getByText('Los de los últimos 90 días. Lo anterior va en el archivo.')).toBeInTheDocument()
    const lineas = within(b).getAllByRole('listitem')
    expect(lineas.map((l) => l.textContent)).toEqual(['Pediste una copia de tus datosa las 10:14', 'Entrastea las 10:00 · Chrome en Android'])
    expect(lineas[0].querySelector('svg.lucide-download')).not.toBeNull()
    expect(within(b).queryByText(/No reconoces/)).toBeNull()
  })

  it('tus avisos y los enviados: la nota del piloto una vez, palabra e ícono por resultado, sin «Salió» en lo simulado', async () => {
    abrir()
    await listo()
    expect(bloque('Tus avisos')).toHaveTextContent('Por correoSíEn tus teléfonosNoPuedes cambiarlos en Tu cuenta.')
    const b = bloque('Avisos que te enviamos')
    expect(within(b).getAllByText('En el piloto los avisos se prueban sin enviarse: aparecen aquí, pero no te llegaron.')).toHaveLength(1)
    const lineas = within(b).getAllByRole('listitem')
    expect(lineas.map((l) => l.textContent)).toEqual([
      '10/11/2026 a las 08:00 · Por correo · En el piloto no salió',
      '09/11/2026 a las 08:00 · En tus teléfonos · No salió',
      '12/11/2026 a las 09:00 · Por SMS · Todavía no sale',
    ])
    expect(lineas[0].querySelector('svg.lucide-circle-dashed')).not.toBeNull()
    expect(lineas[1].querySelector('svg.lucide-x')).not.toBeNull()
    expect(lineas[2].querySelector('svg.lucide-clock')).not.toBeNull()
    expect(lineas.some((l) => l.textContent?.endsWith('· Salió'))).toBe(false)
  })

  it('tus pagos: el grupo y la tarjeta en sus últimos 4, nunca la persona; y las condiciones aceptadas', async () => {
    abrir()
    await listo()
    const [credito, debito, sinReferencia] = within(bloque('Tus pagos')).getAllByRole('listitem')
    expect(within(credito).getByRole('heading', { level: 3 })).toHaveTextContent('Pago 4821')
    expect(credito).toHaveTextContent('08/11/2026 a las 11:24$37.260 en Familia SotoTarjeta de crédito terminada en 4242 · 3 cuotasDevuelto: $5.290Código de autorización: 1213Pago de prueba: no se cobró dinero real.')
    // 1.2 (P3-4): espacio duro antes del «·», para que un renglón nunca empiece con el punto.
    expect(credito.textContent).toContain('4242 · 3 cuotas')
    // F3 (decisión 402): el código solo si lo hay.
    expect(debito).not.toHaveTextContent('Código de autorización')
    expect(within(sinReferencia).getByRole('heading', { level: 3 })).toHaveTextContent('Pago del 10/11/2026')
    expect(sinReferencia).toHaveTextContent('Sin datos de la tarjeta.')
    expect(debito).toHaveTextContent('Tarjeta de débito terminada en 0019 · Sin cuotas')
    expect(debito).not.toHaveTextContent('Devuelto')
    expect(bloque('Tus pagos')).not.toHaveTextContent('María')
    const [pagadas, sinPagar] = within(bloque('Condiciones de compra que aceptaste')).getAllByRole('listitem')
    expect(pagadas).toHaveTextContent('Versión 1.0, el 08/11/2026 a las 11:20.En Familia Soto, para el pedido 4821.')
    expect(sinPagar).toHaveTextContent('En Familia Soto, para un pedido que no se pagó.')
  })

  it('con la capa 3 quitada, ni pagos ni condiciones, tampoco en el índice; vacíos con su frase', async () => {
    abrir(copiaCuenta({ pagos: null, condiciones_aceptadas: null, grupos: [], dispositivos: [], eventos: [], avisos_enviados: [] }))
    await listo()
    expect(screen.queryByRole('region', { name: 'Tus pagos' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Condiciones de compra que aceptaste' })).toBeNull()
    expect(within(screen.getAllByRole('navigation', { name: 'Índice' })[0]).queryByRole('link', { name: 'Tus pagos' })).toBeNull()
    expect(bloque('Tus grupos')).toHaveTextContent('No estás en ningún grupo.')
    expect(bloque('Tus teléfonos y computadores')).toHaveTextContent('Todavía no hay teléfonos ni computadores.')
    expect(bloque('Últimos ingresos')).toHaveTextContent('No hay ingresos en los últimos 90 días.')
    expect(bloque('Avisos que te enviamos')).toHaveTextContent('No hay avisos en los últimos 90 días.')
  })

  it('sin pagos (`[]`), los dos bloques tampoco aparecen', async () => {
    abrir(copiaCuenta({ pagos: [], condiciones_aceptadas: [] }))
    await listo()
    expect(screen.queryByRole('region', { name: 'Tus pagos' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Condiciones de compra que aceptaste' })).toBeNull()
  })
})

describe('«Tus datos»: el diálogo y los estados (5.6)', () => {
  it('el diálogo dice que trae el correo y el celular completos, sin la oración del relevo', async () => {
    abrir()
    await u().click(await listo())
    const dialogo = screen.getByRole('dialog', { name: 'Antes de descargar' })
    expect(dialogo).toHaveTextContent('El archivo trae tu correo y tu celular completos. Queda en tu teléfono o computador, fuera de MATU.')
    expect(dialogo).not.toHaveTextContent('relevo')
  })

  it('«Descargar» guarda el mismo texto con el nombre matu-cuenta-…', async () => {
    const creados: Blob[] = []
    const bajados: string[] = []
    URL.createObjectURL = vi.fn((b: Blob) => (creados.push(b), 'blob:prueba'))
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      bajados.push(this.download)
    })
    const copia = copiaCuenta()
    const pedidas = abrir(copia)
    await u().click(await listo())
    await u().click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Descargar' }))
    expect(await creados[0].text()).toBe(JSON.stringify(copia, null, 2))
    expect(bajados).toEqual([ARCHIVO])
    expect(pedidas).toHaveLength(1)
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:prueba')
  })

  it('no hay 404: si llega uno, es el error con «Volver a intentar»', async () => {
    apiCopia(problemaCopia(404, 'no-encontrado'))
    render(<TusDatos />)
    expect(await screen.findByText('No pudimos traer los datos. Revisa tu conexión y vuelve a intentarlo.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Volver a intentar' })).toBeInTheDocument()
  })

  it('429 con la hora, sin «Volver a intentar», y el foco en la nota', async () => {
    apiCopia(problemaCopia(429, 'tope-copias', { 'retry-after': '60' }))
    render(<TusDatos />)
    const nota = (await screen.findByText(/Ya pediste los datos varias veces/)).closest('[data-aviso]')!
    expect(nota).toHaveTextContent('Ya pediste los datos varias veces. Vuelve a intentarlo a las 10:15.')
    await waitFor(() => expect(nota).toHaveFocus())
    expect(screen.queryByRole('button', { name: 'Volver a intentar' })).toBeNull()
  })

  it('«Volver a tu cuenta» deja en memoria a qué botón vuelve el foco', async () => {
    abrir()
    await listo()
    await u().click(screen.getByRole('button', { name: 'Volver a tu cuenta' }))
    expect(fijar).toHaveBeenCalledWith({ focoAlVolver: 'ver-tus-datos' })
    expect(window.location.pathname).toBe('/cuenta')
  })
})

describe('el celular en pantalla (P3)', () => {
  it('enmascarado como en Tu cuenta, con espacios duros; otra forma, solo las dos últimas cifras', () => {
    expect(enmascararCelular('+56955550137')).toBe('+56 9 •••• ••37')
    expect(enmascararCelular('+5491155550137')).toBe('•••• ••37')
  })
})

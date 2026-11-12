// MATU-54 (especificación docs/diseno/matu-54-mis-datos.md v1.1, sección 3): «Datos de {nombre}», con
// sus nueve bloques, el índice, los 90 días y «Ver más», la descarga con «Antes de descargar» y los
// estados de la página. Un solo GET por visita, también con StrictMode. Solo datos sintéticos.
import { StrictMode } from 'react'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CopiaDatosPersona, TipoHecho } from '../src/compartido/api/misDatos'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { DatosDePersona } from '../src/familia/DatosPersona'
import { familiaFalsa } from './familiaFalsa'
import { A_QUIEN, antes, apiCopia, hecho, copiaComoRespuesta, copiaPersona, dialogoDeJsdom, diferida, fijarAhora, MARIA, problemaCopia } from './misDatosFalso'
import { responderPolitica } from './politicaFalsa'

const fijar = vi.fn()
const anunciar = vi.fn()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa({ datosDe: MARIA.id, personas: [MARIA], fijar, anunciar } as never),
}))

let escrituras: string[] = []
beforeEach(() => {
  fijarAhora()
  dialogoDeJsdom()
  fijar.mockClear()
  anunciar.mockClear()
  escrituras = []
  window.history.replaceState(null, '', '/grupo/datos')
  document.title = 'Datos guardados · MATU'
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
  responderPolitica()
})
afterEach(() => {
  vi.useRealTimers()
})

const u = () => userEvent.setup({ delay: null })
const ARCHIVO = 'matu-datos-2026-11-12.json'

function abrir(copia: CopiaDatosPersona = copiaPersona()) {
  const pedidas = apiCopia(copiaComoRespuesta(copia, ARCHIVO))
  render(
    <StrictMode>
      <RegionesVivas />
      <DatosDePersona />
    </StrictMode>,
  )
  return pedidas
}
const listo = () => screen.findByRole('button', { name: 'Descargar en un archivo' })
const bloque = (nombre: string) => screen.getByRole('region', { name: nombre })
/** El índice del teléfono (`details`); jsdom no aplica `@4xl/main:hidden`, así que también está el ancho. */
const elIndice = () => screen.getAllByRole('navigation', { name: 'Índice' })[0]

describe('«Datos de María»: la copia (3.1 a 3.3)', () => {
  it('un solo GET por visita, como texto, también con StrictMode; el h1 está desde el principio', async () => {
    const d = diferida()
    const pedidas = apiCopia(d.promesa)
    render(
      <StrictMode>
        <DatosDePersona />
      </StrictMode>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Datos de María' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Descargar en un archivo' })).toBeNull()
    d.soltar(copiaComoRespuesta(copiaPersona(), ARCHIVO))
    await listo()
    expect(pedidas).toEqual([{ linea: `GET /v1/personas-cuidadas/${MARIA.id}/datos`, responseType: 'text' }])
  })

  it('la bajada con la fecha y la hora de la copia, y los nueve bloques en su orden, también en el índice', async () => {
    abrir()
    await listo()
    expect(screen.getByText(/Lo que MATU guarda hoy de María, al/)).toHaveTextContent('Lo que MATU guarda hoy de María, al 12/11/2026 a las 10:14.')
    const nombres = [
      'Sus datos',
      'Autorizaciones',
      'Su ficha',
      'Enlaces de relevo',
      'Sus insumos',
      'Compras anotadas (últimos 90 días)',
      'Avisos de insumos',
      'Sus pedidos',
      'Quién abrió o editó la ficha',
    ]
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent).filter((t) => t !== 'Índice')).toEqual(nombres)
    const indice = elIndice()
    expect(within(indice).getAllByRole('link').map((a) => a.textContent)).toEqual(nombres)
  })

  it('el único macizo de la página es «Descargar en un archivo»', async () => {
    abrir()
    await listo()
    const macizos = [...document.querySelectorAll('button')].filter((b) => b.className.includes('bg-turquesa'))
    expect(macizos.map((b) => b.textContent)).toEqual(['Descargar en un archivo'])
  })

  it('el índice lleva el foco al bloque sin cambiar la dirección', async () => {
    abrir()
    await listo()
    const indice = elIndice()
    await u().click(within(indice).getByRole('link', { name: 'Sus pedidos' }))
    await waitFor(() => expect(screen.getByRole('heading', { level: 2, name: 'Sus pedidos' })).toHaveFocus())
    expect(window.location.pathname + window.location.hash).toBe('/grupo/datos')
  })

  it('nada de la copia va al navegador: ni almacenamiento, ni URL, ni history.state, ni el título', async () => {
    abrir()
    await listo()
    expect(escrituras).toEqual([])
    expect(window.location.pathname + window.location.search + window.location.hash).toBe('/grupo/datos')
    expect(window.history.state).toBeNull()
    expect(document.title).toBe('Datos guardados · MATU')
  })
})

describe('«Datos de María»: los bloques (3.4)', () => {
  it('Sus datos: el dl con la dirección y la referencia, y la rectificación por correo', async () => {
    abrir()
    await listo()
    const b = bloque('Sus datos')
    const filas = [...b.querySelectorAll('dl > div')].map((d) => d.textContent)
    expect(filas).toEqual([
      'NombreMaría Soto Pérez',
      'Le dicenMaría',
      'Cuánto apoyo necesitaNecesita apoyo en varias cosas',
      'DirecciónLos Aromos 123, depto 4, Ñuñoa, Región MetropolitanaReferencia: Reja verde',
      'En MATU desde02/11/2026',
    ])
    const correo = await within(b).findByRole('link', { name: 'privacidad@example.org' })
    expect(correo).toHaveAttribute('href', 'mailto:privacidad@example.org')
    expect(correo.closest('p')).toHaveTextContent('Si algo está mal, escribe a privacidad@example.org desde el correo de tu cuenta.')
  })

  it('sin dirección: «Sin dirección.»', async () => {
    const c = copiaPersona()
    abrir({ ...c, persona: { ...c.persona, direccion: null } })
    await listo()
    expect(within(bloque('Sus datos')).getByText('Sin dirección.')).toBeInTheDocument()
  })

  it('Autorizaciones: título, estado con palabra e ícono, quién la da, cuándo, renovación, retiro y lo aceptado', async () => {
    abrir()
    await listo()
    const items = within(bloque('Autorizaciones')).getAllByRole('listitem')
    expect(items).toHaveLength(3)
    const [vigente, retirada, renovada] = items
    expect(within(vigente).getByRole('heading', { level: 3 })).toHaveTextContent('Permiso para guardar su ficha')
    expect(vigente).toHaveTextContent('Vigente')
    expect(vigente.querySelector('svg.lucide-shield-check')).not.toBeNull()
    expect(vigente).toHaveTextContent('La da quien la cuida, sin ser su representante legal.')
    expect(vigente).toHaveTextContent('La registró Carmen Soto el 02/11/2026 a las 18:20.')
    expect(vigente).toHaveTextContent('Hay que renovarla el 02/11/2027.')
    expect(vigente).toHaveTextContent('Lo que se aceptó: política de privacidad 0.16, declaración 1.0 y aviso 1.0.')
    const nota = await within(vigente).findByRole('link', { name: 'privacidad@example.org' })
    expect(nota.closest('div')).toHaveTextContent('Hay una referencia al documento del representante legal. Si la necesitas, pídela a privacidad@example.org.')

    expect(retirada).toHaveTextContent('Permiso para calcular sus insumos')
    expect(retirada).toHaveTextContent('Retirada')
    expect(retirada.querySelector('svg.lucide-shield-off')).not.toBeNull()
    expect(retirada.className).toContain('border-dashed')
    expect(retirada).toHaveTextContent('La da María, por su cuenta.')
    expect(retirada).toHaveTextContent('La registró alguien que ya no está en el grupo el 03/11/2026 a las 09:00.')
    expect(retirada).toHaveTextContent('Se retiró el 10/11/2026 a las 08:30.')
    expect(retirada).toHaveTextContent('Lo que se aceptó: política de privacidad 0.16.')

    expect(renovada).toHaveTextContent('Se renovó')
    expect(renovada.querySelector('svg.lucide-refresh-cw')).not.toBeNull()
    expect(renovada.className).not.toContain('border-dashed')
    expect(renovada).toHaveTextContent('La da su representante legal.')
    expect(renovada).toHaveTextContent('Se renovó el 02/11/2026 a las 18:20.')
    expect(renovada).toHaveTextContent('Lo que se aceptó: política de privacidad 0.9 y declaración 0.9.')
    // Nunca la huella ni el identificador: van en el archivo.
    expect(bloque('Autorizaciones')).not.toHaveTextContent('declaracion_cuidador_de_hecho')
    expect(bloque('Autorizaciones')).not.toHaveTextContent('aaaaaaaa')
  })

  it('Su ficha: los tres campos en orden y las secciones, el texto tal cual (con los teléfonos) y «Sin escribir.»', async () => {
    abrir()
    await listo()
    const b = bloque('Su ficha')
    expect(within(b).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['Su día', 'Si se altera', 'A quién llamar', 'Cómo hablarle'])
    const items = within(b).getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('08:00 Despierta. 13:00 Almuerza.Lo escribió Carmen Soto el 05/11/2026 a las 21:02.')
    expect(items[0].querySelector('p')!.textContent).toBe('08:00 Despierta.\n13:00 Almuerza.')
    expect(items[1]).toHaveTextContent('Sin escribir.')
    expect(items[1]).not.toHaveTextContent('Lo escribió')
    expect(items[2].querySelector('p')!.textContent).toBe(A_QUIEN)
    expect(items[2]).toHaveTextContent('Lo escribió alguien que ya no está en el grupo el 06/11/2026 a las 10:00.')
  })

  it('Enlaces de relevo: sin el teléfono, con estado, motivo, qué ve, quién, hasta cuándo y el uso; las aperturas de a 5', async () => {
    abrir()
    await listo()
    const b = bloque('Enlaces de relevo')
    expect(within(b).getByText('No incluimos el teléfono de los relevos.')).toBeInTheDocument()
    const [rosa, pedro] = within(b).getAllByRole('listitem').filter((li) => li.parentElement?.tagName === 'UL')
    expect(within(rosa).getByRole('heading', { level: 3 })).toHaveTextContent('Rosa')
    expect(rosa).toHaveTextContent('Vigente')
    expect(rosa).toHaveTextContent('Fin de semana fuera')
    expect(rosa).toHaveTextContent('Ve: Su día, A quién llamar y Cómo hablarle.')
    expect(rosa).toHaveTextContent('Lo compartió Carmen el 11/11/2026 a las 09:00.')
    expect(rosa).toHaveTextContent('Vence el 15/11/2026 a las 23:59.')
    expect(rosa).toHaveTextContent('Se abrió 3 veces. La última, el 12/11/2026 a las 08:00.')
    expect(pedro).toHaveTextContent('Cortado')
    expect(pedro).toHaveTextContent('Otro motivo')
    expect(pedro).toHaveTextContent('Se cortó el 02/11/2026 a las 09:00.')
    expect(pedro).toHaveTextContent('No se ha abierto.')
    expect(b).not.toHaveTextContent('5555')

    const lineas = () => within(rosa).getByRole('list').querySelectorAll('li')
    expect(lineas()).toHaveLength(5)
    await u().click(within(rosa).getByRole('button', { name: 'Ver más' }))
    expect(lineas()).toHaveLength(7)
    await waitFor(() => expect(lineas()[5]).toHaveFocus())
    expect(anunciar).toHaveBeenCalledWith('Se agregaron 2 líneas.')
    expect(within(rosa).queryByRole('button', { name: 'Ver más' })).toBeNull()
  })

  it('Sus insumos: las frases de Insumos, el envase, el autor y «Ya no se sigue» con palabra y figura', async () => {
    abrir()
    await listo()
    const [champu, toallitas] = within(bloque('Sus insumos')).getAllByRole('listitem')
    expect(champu).toHaveTextContent('Usa 1 sobre cada 2 días.')
    expect(champu).toHaveTextContent('Quedaban 30 sobres el 10/11/2026.')
    expect(champu).toHaveTextContent('Se acaba el 09/01/2027.')
    expect(champu).toHaveTextContent('Avisa el mismo día.')
    expect(champu).toHaveTextContent('10 por envase.')
    expect(champu).toHaveTextContent('Lo agregaron el 20/10/2026. Lo cambió por última vez Carmen Soto el 10/11/2026 a las 08:00.')
    expect(champu).not.toHaveTextContent('Ya no se sigue')
    expect(toallitas).toHaveTextContent('Ya no se sigue')
    expect(toallitas.querySelector('svg.lucide-circle')).not.toBeNull()
    expect(toallitas).not.toHaveTextContent('Se acaba el')
    expect(toallitas).toHaveTextContent('Avisa 7 días antes.')
    expect(toallitas).toHaveTextContent('Lo cambió por última vez alguien que ya no está en el grupo')
  })

  it('Compras y avisos de insumos: origen, quién, y los cuatro estados del aviso', async () => {
    abrir()
    await listo()
    const compras = within(bloque('Compras anotadas (últimos 90 días)')).getAllByRole('listitem')
    expect(compras[0]).toHaveTextContent('20 sobres de Champú en sobreEl 10/11/2026 · Anotó Carmen Soto')
    expect(compras[1]).toHaveTextContent('80 unidades de Toallitas húmedasEl 08/11/2026 · Llegó con un pedido de MATU')
    // 1.2: la unidad de la compra (decisión 386), con espacio duro entre la cifra y su palabra.
    expect(compras[0].querySelector('.font-bold')!.textContent).toBe('20 sobres de Champú en sobre')
    const avisos = bloque('Avisos de insumos')
    expect(within(avisos).getByText('Los de los últimos 90 días.')).toBeInTheDocument()
    const [resuelta, pendiente] = within(avisos).getAllByRole('listitem')
    expect(resuelta).toHaveTextContent('Toallitas húmedas: se acaba el 04/11/2026.Se resolvió el 01/11/2026 a las 08:00.')
    expect(pendiente).toHaveTextContent('Todavía no se avisa.')
  })

  it('Sus pedidos: referencia, estado, líneas, montos sin IVA, pago, devolución, prueba, entrega y el rótulo del piloto una vez', async () => {
    abrir()
    await listo()
    const b = bloque('Sus pedidos')
    const [entregado, borrador] = within(b).getAllByRole('listitem')
    expect(within(entregado).getByRole('heading', { level: 3 })).toHaveTextContent('Pedido 4821')
    expect(entregado).toHaveTextContent('Entregado')
    expect(entregado).toHaveTextContent('Lo armaron el 08/11/2026 a las 11:02.')
    expect(entregado).toHaveTextContent('Pañal adulto M, paquete de 30 × 2$27.980')
    expect(entregado).toHaveTextContent('En Farmacia Los Aromos (comercio ficticio) · Si falta: buscarlo en otro comercio')
    expect(entregado).toHaveTextContent('Si falta: sacarlo del pedido y devolverme su precio')
    expect(entregado).toHaveTextContent('Productos$33.270Envío$3.990Total$37.260')
    expect(entregado).toHaveTextContent('Lo pagó Rodrigo Soto el 08/11/2026 a las 11:24.')
    expect(entregado).toHaveTextContent('Cobrado: $37.260 · Devuelto: $5.290.')
    expect(entregado).toHaveTextContent('Se devolvieron $5.290 porque no se pudo entregar Toallitas.')
    expect(entregado).toHaveTextContent('Pago de prueba: no se cobró dinero real.')
    expect(entregado).toHaveTextContent('Entrega: Los Aromos 123, Ñuñoa, Región Metropolitana')
    expect(within(borrador).getByRole('heading', { level: 3 })).toHaveTextContent('Pedido del 11/11/2026')
    expect(borrador).toHaveTextContent('Sin confirmar')
    expect(borrador).toHaveTextContent('Sin pagar.')
    expect(borrador).not.toHaveTextContent('Total')
    expect(b).not.toHaveTextContent(/IVA|Neto/)
    expect(within(b).getAllByText('Precios de ejemplo.')).toHaveLength(1)
  })

  it('con la capa 3 quitada (`pedidos: null`) no hay bloque ni entrada en el índice', async () => {
    abrir(copiaPersona({ pedidos: null }))
    await listo()
    expect(screen.queryByRole('region', { name: 'Sus pedidos' })).toBeNull()
    expect(within(elIndice()).queryByRole('link', { name: 'Sus pedidos' })).toBeNull()
  })
})

describe('«Datos de María»: autorización retirada, en pausa o borrada (3.5)', () => {
  it('retirada: la nota con ShieldOff, borde punteado y la fecha; sin texto de la ficha ni compras ni avisos', async () => {
    abrir(
      copiaPersona({
        ficha: { estado: 'retirada', borrado_el: '2027-02-10', completitud: null, campos: null, secciones: null },
        insumos: { estado: 'retirada', borrado_el: '2027-02-08', lista: null, compras: null, avisos: null },
      }),
    )
    await listo()
    const ficha = bloque('Su ficha')
    expect(ficha).toHaveTextContent('La autorización de la ficha está retirada. Lo escrito sigue guardado sin que nadie lo pueda leer, y se borra el 10/02/2027.')
    expect(ficha.querySelector('svg.lucide-shield-off')).not.toBeNull()
    expect(ficha.querySelector('.border-dashed')).not.toBeNull()
    expect(within(ficha).queryByRole('listitem')).toBeNull()
    expect(bloque('Sus insumos')).toHaveTextContent('La autorización de los insumos está retirada. Lo anotado se borra el 08/02/2027.')
    expect(screen.queryByRole('region', { name: 'Compras anotadas (últimos 90 días)' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Avisos de insumos' })).toBeNull()
    const indice = within(elIndice())
    expect(indice.queryByRole('link', { name: 'Avisos de insumos' })).toBeNull()
    // El diálogo no promete lo escrito en la ficha si no va.
    await u().click(screen.getByRole('button', { name: 'Descargar en un archivo' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('El archivo trae todo lo de esta pantalla, y lo anterior a 90 días.')
  })

  it('en pausa: Hourglass y sin borde punteado; borrada: Trash2 con borde; sin autorizar: ShieldQuestion', async () => {
    abrir(
      copiaPersona({
        ficha: { estado: 'en_pausa', borrado_el: null, completitud: null, campos: null, secciones: null },
        insumos: { estado: 'borrada', borrado_el: null, lista: null, compras: null, avisos: null },
      }),
    )
    await listo()
    const ficha = bloque('Su ficha')
    expect(ficha).toHaveTextContent('La ficha está en pausa porque falta renovar la autorización. Cuando se renueve, vuelve a aparecer aquí.')
    expect(ficha.querySelector('svg.lucide-hourglass')).not.toBeNull()
    expect(ficha.querySelector('.border-dashed')).toBeNull()
    const insumos = bloque('Sus insumos')
    expect(insumos).toHaveTextContent('La autorización de los insumos se retiró, y lo anotado ya se borró.')
    expect(insumos.querySelector('svg.lucide-trash-2')).not.toBeNull()
    expect(insumos.querySelector('.border-dashed')).not.toBeNull()
  })

  it('sin autorizar: «Nadie ha autorizado todavía…» con ShieldQuestion', async () => {
    abrir(copiaPersona({ insumos: { estado: 'sin_autorizar', borrado_el: null, lista: null, compras: null, avisos: null } }))
    await listo()
    const insumos = bloque('Sus insumos')
    expect(insumos).toHaveTextContent('Nadie ha autorizado todavía calcular los insumos de María.')
    expect(insumos.querySelector('svg.lucide-shield-question')).not.toBeNull()
  })
})

describe('«Datos de María»: quién abrió o editó la ficha (3.4.9 y 3.4.10)', () => {
  it('por día, en el orden del servidor; MATU sin nombre, quien salió como «alguien…», un tipo desconocido no se ve', async () => {
    abrir()
    await listo()
    const b = bloque('Quién abrió o editó la ficha')
    expect(within(b).getByText('Los de los últimos 90 días.')).toBeInTheDocument()
    expect(within(b).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['Hoy', 'Ayer', 'El lunes'])
    expect(within(b).getAllByRole('listitem').map((l) => l.textContent)).toEqual([
      'Pidió una copia de los datosa las 10:14 · Carmen Soto',
      'Editó «Su día»a las 09:40 · Carmen Soto',
      'Editó la fichaa las 09:24 · alguien que ya no está en el grupo',
      'MATU borró lo escrito en la fichaa las 10:14',
      'Quitó «Moverse y descansar»a las 09:44 · Carmen Soto',
      'Se devolvió dinero de un pagoa las 10:14',
    ])
    expect(within(b).queryByText(/un_tipo_que_no_existe/)).toBeNull()
    expect(b.querySelectorAll('ol li span.bg-rocio')).toHaveLength(6)
    expect(within(b).queryByText(/Aquí ves solo lo que hiciste tú/)).toBeNull()
    expect(within(b).queryByText(/Hay cambios antiguos/)).toBeNull()
  })

  it('los 26 tipos tienen su frase y su ícono', async () => {
    const tipos: TipoHecho[] = [
      'abrio_la_ficha',
      'edito_la_ficha',
      'quito_una_seccion',
      'ficha_borrada',
      'dio_una_autorizacion',
      'retiro_una_autorizacion',
      'compartio_la_ficha',
      'corto_un_enlace',
      'agrego_un_insumo',
      'edito_un_insumo',
      'dejo_de_seguir_un_insumo',
      'volvio_a_seguir_un_insumo',
      'quito_un_insumo',
      'anoto_una_compra',
      'aviso_de_insumo',
      'descarto_un_aviso',
      'resolvio_un_aviso',
      'cambio_la_direccion',
      'creo_un_pedido',
      'confirmo_un_pedido',
      'cancelo_un_pedido',
      'cambio_que_hacer_si_falta',
      'inicio_un_pago',
      'pago_aprobado',
      'pago_anulado',
      'pidio_una_copia',
    ]
    const hechos = tipos.map((tipo, i) => hecho(tipo, antes(0, i), { tipo: 'persona', nombre: 'Rosa', activo: true }))
    abrir(copiaPersona({ historial: { alcance: 'todo', hechos, hay_hechos_sin_asociar: false } }))
    await listo()
    const b = bloque('Quién abrió o editó la ficha')
    const lineas = within(b).getAllByRole('listitem')
    expect(lineas).toHaveLength(20)
    await u().click(within(b).getByRole('button', { name: 'Ver más' }))
    const todas = within(b).getAllByRole('listitem')
    expect(todas).toHaveLength(26)
    expect(new Set(todas.map((l) => l.querySelector('svg')!.getAttribute('class'))).size).toBe(26)
    expect(todas.map((l) => l.querySelector('.font-bold')!.textContent)).toEqual([
      'Abrió la ficha',
      'Editó la ficha',
      'Quitó una sección de la ficha',
      'MATU borró lo escrito en la ficha',
      'Dio una autorización',
      'Retiró una autorización',
      'Compartió la ficha con un relevo',
      'Cortó un enlace de relevo',
      'Agregó un insumo',
      'Cambió un insumo',
      'Dejó de seguir un insumo',
      'Volvió a seguir un insumo',
      'Quitó un insumo',
      'Anotó una compra',
      'MATU avisó que un insumo se está acabando',
      'Descartó un aviso de insumo',
      'Resolvió un aviso de insumo',
      'Cambió la dirección',
      'Armó un pedido',
      'Confirmó un pedido',
      'Canceló un pedido',
      'Cambió qué hacer si falta un producto',
      'Empezó a pagar un pedido',
      'Se aprobó el pago de un pedido',
      'Se devolvió dinero de un pago',
      'Pidió una copia de los datos',
    ])
  })

  it('solo los últimos 90 días: «Ver más» de a 20 dentro de ellos, el foco en la primera nueva y lo anterior en el archivo', async () => {
    const recientes = Array.from({ length: 45 }, (_, i) => hecho('abrio_la_ficha', antes(i, 5)))
    const viejos = Array.from({ length: 3 }, (_, i) => hecho('abrio_la_ficha', antes(91 + i)))
    abrir(copiaPersona({ historial: { alcance: 'todo', hechos: [...recientes, ...viejos], hay_hechos_sin_asociar: false } }))
    await listo()
    const b = bloque('Quién abrió o editó la ficha')
    expect(within(b).getByText('Los de los últimos 90 días. Lo anterior va en el archivo.')).toBeInTheDocument()
    expect(within(b).getAllByRole('listitem')).toHaveLength(20)
    await u().click(within(b).getByRole('button', { name: 'Ver más' }))
    expect(within(b).getAllByRole('listitem')).toHaveLength(40)
    await waitFor(() => expect(within(b).getAllByRole('listitem')[20]).toHaveFocus())
    expect(anunciar).toHaveBeenLastCalledWith('Se agregaron 20 líneas.')
    await u().click(within(b).getByRole('button', { name: 'Ver más' }))
    expect(within(b).getAllByRole('listitem')).toHaveLength(45)
    await waitFor(() => expect(within(b).getAllByRole('listitem')[40]).toHaveFocus())
    expect(within(b).queryByRole('button', { name: 'Ver más' })).toBeNull()
  })

  it('cuidadora (`lo_tuyo`): la nota de lo tuyo; `hay_hechos_sin_asociar`: la nota con el correo', async () => {
    const c = copiaPersona()
    abrir({ ...c, historial: { ...c.historial, alcance: 'lo_tuyo', hay_hechos_sin_asociar: true } })
    await listo()
    const b = bloque('Quién abrió o editó la ficha')
    expect(within(b).getByText('Aquí ves solo lo que hiciste tú. La lista completa la ve quien administra el grupo.')).toBeInTheDocument()
    const correo = await within(b).findByRole('link', { name: 'privacidad@example.org' })
    expect(correo.closest('div')).toHaveTextContent('Hay cambios antiguos que no podemos mostrar aquí ni en el archivo. Si los necesitas, pídelos a privacidad@example.org.')
  })

  it('los vacíos dicen lo suyo, sin ícono ni botón', async () => {
    const c = copiaPersona()
    abrir({
      ...c,
      enlaces_relevo: [],
      insumos: { estado: 'disponible', borrado_el: null, lista: [], compras: [], avisos: [] },
      pedidos: [],
      historial: { alcance: 'todo', hechos: [], hay_hechos_sin_asociar: false },
      autorizaciones: [],
    })
    await listo()
    expect(bloque('Autorizaciones')).toHaveTextContent('Todavía no hay autorizaciones.')
    expect(bloque('Enlaces de relevo')).toHaveTextContent('Todavía no hay enlaces de relevo.')
    expect(bloque('Sus insumos')).toHaveTextContent('Todavía no hay insumos.')
    expect(bloque('Compras anotadas (últimos 90 días)')).toHaveTextContent('No hay compras anotadas en los últimos 90 días.')
    expect(bloque('Avisos de insumos')).toHaveTextContent('No hay avisos en los últimos 90 días.')
    expect(bloque('Sus pedidos')).toHaveTextContent('No hay pedidos.')
    expect(bloque('Quién abrió o editó la ficha')).toHaveTextContent('No hay cambios en los últimos 90 días.')
  })
})

describe('«Datos de María»: descargar (3.7)', () => {
  let creados: Blob[] = []
  let soltados: string[] = []
  let bajados: { href: string; download: string; enPagina: boolean }[] = []
  beforeEach(() => {
    creados = []
    soltados = []
    bajados = []
    URL.createObjectURL = vi.fn((b: Blob) => {
      creados.push(b)
      return 'blob:prueba'
    })
    URL.revokeObjectURL = vi.fn((u: string) => void soltados.push(u))
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      bajados.push({ href: this.href, download: this.download, enPagina: document.body.contains(this) })
    })
  })

  it('nunca descarga directo: abre «Antes de descargar» con el foco en su título; «No descargar» devuelve el foco', async () => {
    abrir()
    const boton = await listo()
    expect(boton).toHaveAccessibleDescription('Es un archivo (JSON) que otro programa puede leer, para llevar estos datos a otro lugar.')
    await u().click(boton)
    const dialogo = screen.getByRole('dialog', { name: 'Antes de descargar' })
    await waitFor(() => expect(within(dialogo).getByRole('heading', { name: 'Antes de descargar' })).toHaveFocus())
    expect(dialogo).toHaveTextContent(
      'El archivo trae todo lo de esta pantalla, también lo escrito en la ficha y los nombres y teléfonos de «A quién llamar». Queda en tu teléfono o computador, fuera de MATU: no vence, no se puede cortar y MATU no lo puede borrar.',
    )
    expect(within(dialogo).getByText('No lo uses para compartir la ficha con un relevo: para eso está el enlace con PIN.')).toHaveClass('font-bold')
    expect(bajados).toEqual([])
    await u().click(within(dialogo).getByRole('button', { name: 'No descargar' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Descargar en un archivo' })).toHaveFocus())
    expect(bajados).toEqual([])
  })

  it('Esc cierra sin descargar y devuelve el foco', async () => {
    abrir()
    await u().click(await listo())
    // jsdom no convierte Esc en `cancel`: se dispara el evento que el navegador manda al diálogo.
    fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }))
    expect(screen.queryByRole('dialog')).toBeNull()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Descargar en un archivo' })).toHaveFocus())
    expect(bajados).toEqual([])
  })

  it('«Descargar» guarda los mismos caracteres que llegaron, con el nombre de la cabecera, sin otra petición', async () => {
    const copia = copiaPersona()
    const pedidas = abrir(copia)
    await u().click(await listo())
    await u().click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Descargar' }))
    expect(creados).toHaveLength(1)
    expect(creados[0].type).toBe('application/json')
    expect(await creados[0].text()).toBe(JSON.stringify(copia, null, 2))
    expect(bajados).toEqual([{ href: 'blob:prueba', download: ARCHIVO, enPagina: false }])
    expect(soltados).toEqual(['blob:prueba'])
    expect(pedidas).toHaveLength(1)
    expect(screen.queryByRole('dialog')).toBeNull()
    const nota = screen.getByText('Te entregamos el archivo. Búscalo en tus descargas.')
    await waitFor(() => expect(nota.closest('[tabindex="-1"]')).toHaveFocus())
    // La nota se borra al volver a abrir el diálogo.
    await u().click(screen.getByRole('button', { name: 'Descargar en un archivo' }))
    expect(screen.queryByText('Te entregamos el archivo. Búscalo en tus descargas.')).toBeNull()
  })

  it('sin la cabecera, el nombre sale del día de la copia y nunca lleva el nombre de la persona', async () => {
    apiCopia({ status: 200, texto: JSON.stringify(copiaPersona()), cabeceras: {} })
    render(<DatosDePersona />)
    await u().click(await listo())
    await u().click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Descargar' }))
    expect(bajados[0].download).toBe('matu-datos-2026-11-12.json')
  })

  it('si el navegador no deja armar el archivo, el error va dentro del diálogo, que sigue abierto', async () => {
    URL.createObjectURL = vi.fn(() => {
      throw new Error('sin blobs')
    })
    abrir()
    await u().click(await listo())
    const dialogo = screen.getByRole('dialog')
    await u().click(within(dialogo).getByRole('button', { name: 'Descargar' }))
    expect(within(dialogo).getByRole('alert')).toHaveTextContent('No pudimos armar el archivo en este navegador. Prueba en otro navegador o en un computador.')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.queryByText(/Te entregamos el archivo/)).toBeNull()
  })
})

describe('«Datos de María»: estados de la página (3.6)', () => {
  it('sin red: la nota con «Volver a intentar», que pide otra copia', async () => {
    const pedidas = apiCopia(problemaCopia(500, 'error-interno'), copiaComoRespuesta(copiaPersona(), ARCHIVO))
    render(<DatosDePersona />)
    const nota = await screen.findByText('No pudimos traer los datos. Revisa tu conexión y vuelve a intentarlo.')
    await waitFor(() => expect(nota.closest('[data-aviso]')).toHaveFocus())
    expect(nota.closest('[data-aviso]')).toHaveAttribute('data-aviso', 'alert')
    expect(screen.queryByRole('button', { name: 'Descargar en un archivo' })).toBeNull()
    await u().click(screen.getByRole('button', { name: 'Volver a intentar' }))
    await listo()
    expect(pedidas).toHaveLength(2)
  })

  it('503: no dice «Revisa tu conexión»', async () => {
    apiCopia(problemaCopia(503, 'servicio-no-disponible'))
    render(<DatosDePersona />)
    expect(await screen.findByText('No pudimos traer los datos en este momento. Vuelve a intentarlo en unos minutos.')).toBeInTheDocument()
    expect(screen.queryByText(/Revisa tu conexión/)).toBeNull()
    expect(screen.getByRole('button', { name: 'Volver a intentar' })).toBeInTheDocument()
  })

  it('429: la hora de Retry-After en `atenta` con Clock, sin «Volver a intentar»', async () => {
    apiCopia(problemaCopia(429, 'tope-copias', { 'retry-after': '1230' }))
    render(<DatosDePersona />)
    const nota = await screen.findByText(/Ya pediste los datos varias veces/)
    // 10:14 más 20 min 30 s, hacia arriba al minuto.
    expect(nota.closest('[data-aviso]')).toHaveTextContent('Ya pediste los datos varias veces. Vuelve a intentarlo a las 10:35.')
    expect(nota.closest('[data-aviso]')).toHaveClass('bg-atenta-fondo')
    expect(nota.closest('[data-aviso]')!.querySelector('svg.lucide-clock')).not.toBeNull()
    await waitFor(() => expect(nota.closest('[data-aviso]')).toHaveFocus())
    expect(screen.queryByRole('button', { name: 'Volver a intentar' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Volver a Grupo familiar' })).toBeInTheDocument()
  })

  it('429 sin Retry-After: «… en una hora.»', async () => {
    apiCopia(problemaCopia(429, 'tope-copias'))
    render(<DatosDePersona />)
    expect(await screen.findByText('Ya pediste los datos varias veces. Vuelve a intentarlo en una hora.')).toBeInTheDocument()
  })

  it('404: la nota general con Lock', async () => {
    apiCopia(problemaCopia(404, 'no-encontrado'))
    render(<DatosDePersona />)
    const nota = await screen.findByText('No encontramos lo que buscas. Puede que ya no tengas acceso. Vuelve al inicio.')
    expect(nota.closest('[tabindex="-1"]')!.querySelector('svg.lucide-lock')).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Volver a intentar' })).toBeNull()
  })

  it('«Volver a Grupo familiar» deja en memoria a qué botón vuelve el foco', async () => {
    abrir()
    await listo()
    await u().click(screen.getByRole('button', { name: 'Volver a Grupo familiar' }))
    expect(fijar).toHaveBeenCalledWith({ focoAlVolver: `datos-${MARIA.id}` })
    expect(window.location.pathname).toBe('/grupo')
  })
})

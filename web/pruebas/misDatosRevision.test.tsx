// MATU-54, especificación v1.2 y v1.3 (revisiones visuales del 12-11, secciones 12 y 13): el reflujo (P1-1, P1-2 y P2-1),
// las aperturas con la fecha completa, el 503 con CloudOff, las frases del historial con finalidad y
// referencia (F1), y en «Tus datos» los grupos que dejaste (F2) y el código de autorización (F3).
// jsdom no mide anchos: los P1 se verifican por la estructura de clases. Solo datos sintéticos.
import { render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CopiaDatosPersona } from '../src/compartido/api/misDatos'
import { DatosDePersona } from '../src/familia/DatosPersona'
import { TusDatos } from '../src/familia/TusDatos'
import { familiaFalsa } from './familiaFalsa'
import { antes, apiCopia, copiaComoRespuesta, copiaCuenta, copiaPersona, dialogoDeJsdom, fijarAhora, hecho, MARIA, problemaCopia, type Hecho } from './misDatosFalso'
import { responderPolitica } from './politicaFalsa'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa({ datosDe: MARIA.id, personas: [MARIA], fijar: vi.fn(), anunciar: vi.fn() } as never),
}))

beforeEach(() => {
  fijarAhora()
  dialogoDeJsdom()
  responderPolitica()
})
afterEach(() => {
  vi.useRealTimers()
})

async function abrirPersona(copia: CopiaDatosPersona = copiaPersona()) {
  apiCopia(copiaComoRespuesta(copia, 'matu-datos-2026-11-12.json'))
  render(<DatosDePersona />)
  await screen.findByRole('button', { name: 'Descargar en un archivo' })
}
const bloque = (nombre: string) => screen.getByRole('region', { name: nombre })
/** Las `li` de primer nivel de los bloques: las filas y las tarjetas. */
const filasDeBloques = () => [...document.querySelectorAll('section > ul > li, section > ol > li')] as HTMLElement[]
/**
 * P1-1: una fila en columna no lleva `items-start` (sus hijos tienen el ancho de la fila). Una fila
 * horizontal (ícono y texto) sí, porque solo alinea en vertical; si en modo angosto pasa a columna,
 * vuelve a estirar a sus hijos.
 */
function sinEncoger(li: HTMLElement) {
  const c = li.className.split(/\s+/)
  if (c.includes('flex-col')) expect(c).not.toContain('items-start')
  if (c.includes('angosto:flex-col') && c.includes('items-start')) expect(c).toContain('angosto:items-stretch')
}

describe('1.2 y 1.3, reflujo (P1-1, P1-2, P2-1 y los montos)', () => {
  it('P1-1: ninguna fila de bloque lleva `items-start`; la Etiqueta va con `self-start`, y el nombre largo puede partirse', async () => {
    const c = copiaPersona()
    const largo = 'ToallitasHúmedasExtraGrandesSinPerfumeParaPielSensibleXXL60'
    await abrirPersona({ ...c, insumos: { ...c.insumos, lista: [{ ...c.insumos.lista![1], nombre: largo }] } })
    const filas = filasDeBloques()
    expect(filas.length).toBeGreaterThan(10)
    filas.forEach(sinEncoger)
    const insumo = within(bloque('Sus insumos')).getByRole('heading', { level: 3, name: largo })
    expect(insumo.className).toMatch(/\bbreak-words\b/)
    expect(insumo.parentElement!.className).toMatch(/\bflex-col\b/)
    expect(insumo.parentElement!.className).not.toMatch(/\bitems-start\b/)
    for (const etiqueta of document.querySelectorAll('section li span.rounded-full.inline-flex')) expect(etiqueta.className).toMatch(/\bself-start\b/)
  })

  it('P1-2: las notas dentro de una tarjeta llevan el ícono en la primera línea en modo angosto', async () => {
    const c = copiaPersona()
    await abrirPersona({
      ...c,
      ficha: { estado: 'retirada', borrado_el: '2027-02-10', completitud: null, campos: null, secciones: null },
      historial: { ...c.historial, alcance: 'lo_tuyo', hay_hechos_sin_asociar: true },
    })
    const notas = [
      within(bloque('Autoriza­ciones')).getByText(/Hay una referencia al documento del representante legal/),
      within(bloque('Su ficha')).getByText(/La autorización de la ficha está retirada/),
      within(bloque('Quién abrió o editó la ficha')).getByText(/Aquí ves solo lo que hiciste tú/),
      within(bloque('Quién abrió o editó la ficha')).getByText(/Hay cambios antiguos/),
    ]
    for (const texto of notas) {
      const nota = texto.closest('.rounded-xl') as HTMLElement
      // El ícono de al lado se oculta en angosto y el de la línea aparece dentro del texto.
      expect(nota.querySelector(':scope > span.contents')!.className).toContain('angosto:hidden')
      expect(nota.querySelector('.leading-relaxed > span.hidden')!.className).toContain('angosto:inline-flex')
    }
  })

  it('P2-1 (1.3): «Autorizaciones» lleva un guion suave (U+00AD) y ningún título usa `hyphens-auto`', async () => {
    await abrirPersona()
    const h2 = document.getElementById('autorizaciones-t')!
    expect(h2.textContent).toBe('Autoriza\u00ADciones')
    // El índice usa el mismo texto.
    const enlaces = [...document.querySelectorAll('#indice-datos a')].map((a) => a.textContent)
    expect(enlaces).toContain('Autoriza\u00ADciones')
    for (const h of document.querySelectorAll('h2, h3')) expect(h.className).not.toMatch(/\bhyphens-auto\b/)
  })

  it('P2-1 (1.3) en «Tus datos»: «compu­tadores» y «acep­taste» con guion suave', async () => {
    apiCopia(copiaComoRespuesta(copiaCuenta(), 'matu-cuenta-2026-11-12.json'))
    render(<TusDatos />)
    await screen.findByRole('button', { name: 'Descargar en un archivo' })
    expect(document.getElementById('tus-dispositivos-t')!.textContent).toBe('Tus teléfonos y compu\u00ADtadores')
    expect(document.getElementById('condiciones-t')!.textContent).toBe('Condiciones de compra que acep\u00ADtaste')
    for (const h of document.querySelectorAll('h2, h3')) expect(h.className).not.toMatch(/\bhyphens-auto\b/)
    filasDeBloques().forEach(sinEncoger)
  })

  it('P2 (1.3): las filas de los montos del pedido pasan a una columna en modo angosto; P3: «×» y la cantidad juntos', async () => {
    await abrirPersona()
    const pedido = within(bloque('Sus pedidos')).getAllByRole('listitem')[0]
    const montos = [...pedido.querySelectorAll('dl')].at(-1)!
    const filas = [...montos.children] as HTMLElement[]
    expect(filas.map((f) => f.querySelector('dt')!.textContent)).toEqual(['Productos', 'Envío', 'Total'])
    for (const f of filas) {
      expect(f.className.split(/\s+/)).toContain('angosto:grid-cols-1')
      expect(f.querySelector('dd')!.className.split(/\s+/)).toContain('angosto:text-left')
    }
    expect(pedido.querySelector('dl dt')!.textContent).toContain('paquete de 30 ×\u00A02')
  })

  it('compras (1.3, decisión 403): con una de un pedido de MATU de más de 90 días, «Lo anterior va en el archivo.»; sin ella, nada', async () => {
    const c = copiaPersona()
    const vieja = { insumo: 'Toallitas húmedas', unidad: 'unidad' as const, unidades: 80, el: '2026-07-01', origen: 'pedido_matu' as const, anotada_en: '2026-07-01T08:00:00-04:00', anotada_por: null }
    await abrirPersona({ ...c, insumos: { ...c.insumos, compras: [...c.insumos.compras!, vieja] } })
    const b = bloque('Compras anotadas (últimos 90 días)')
    expect(within(b).getByText('Lo anterior va en el archivo.')).toHaveClass('text-tenue')
    expect(within(b).getAllByRole('listitem')).toHaveLength(2)
  })

  it('compras sin nada anterior a 90 días: sin la frase', async () => {
    await abrirPersona()
    expect(within(bloque('Compras anotadas (últimos 90 días)')).queryByText('Lo anterior va en el archivo.')).toBeNull()
  })
})

describe('1.2, P3', () => {
  it('las aperturas de un enlace dicen la fecha completa, sin «hoy»', async () => {
    await abrirPersona()
    const rosa = within(bloque('Enlaces de relevo')).getAllByRole('listitem')[0]
    const aperturas = [...rosa.querySelectorAll('ol > li')]
    expect(aperturas).toHaveLength(5)
    expect(aperturas[0].querySelector('time')).toHaveTextContent('el 12/11/2026 a las 08:14')
    for (const a of aperturas) expect(a).not.toHaveTextContent(/\bhoy\b|\bayer\b/)
  })

  it('el 503 lleva CloudOff; la falla de red sigue con WifiOff', async () => {
    apiCopia(problemaCopia(503, 'servicio-no-disponible'))
    render(<DatosDePersona />)
    const nota = (await screen.findByText(/en este momento/)).closest('[data-aviso]')!
    expect(nota.querySelector('svg.lucide-cloud-off')).not.toBeNull()
    expect(nota.querySelector('svg.lucide-wifi-off')).toBeNull()
  })

  it('500: WifiOff', async () => {
    apiCopia(problemaCopia(500, 'error-interno'))
    render(<DatosDePersona />)
    const nota = (await screen.findByText(/Revisa tu conexión/)).closest('[data-aviso]')!
    expect(nota.querySelector('svg.lucide-wifi-off')).not.toBeNull()
  })

  it('F1: con finalidad o referencia, la frase precisa (la referencia en cifras); con `null`, la general', async () => {
    const con = (h: Hecho, cambios: Partial<Hecho>): Hecho => ({ ...h, ...cambios })
    const hechos: Hecho[] = [
      con(hecho('dio_una_autorizacion', antes(0, 1)), { finalidad: 'plan_cuidado' }),
      con(hecho('dio_una_autorizacion', antes(0, 2)), { finalidad: 'consumo' }),
      con(hecho('retiro_una_autorizacion', antes(0, 3)), { finalidad: 'despacho' }),
      hecho('retiro_una_autorizacion', antes(0, 4)),
      con(hecho('creo_un_pedido', antes(0, 5)), { referencia: '4821' }),
      hecho('creo_un_pedido', antes(0, 6)),
      con(hecho('confirmo_un_pedido', antes(0, 7)), { referencia: '4821' }),
      con(hecho('cancelo_un_pedido', antes(0, 8)), { referencia: '4821' }),
      con(hecho('cambio_que_hacer_si_falta', antes(0, 9)), { referencia: '4821' }),
      con(hecho('inicio_un_pago', antes(0, 10)), { referencia: '4821' }),
      con(hecho('pago_aprobado', antes(0, 11), { tipo: 'matu', nombre: null, activo: null }), { referencia: '4821' }),
      con(hecho('pago_anulado', antes(0, 12), { tipo: 'matu', nombre: null, activo: null }), { referencia: '4821' }),
      hecho('pago_anulado', antes(0, 13), { tipo: 'matu', nombre: null, activo: null }),
    ]
    await abrirPersona(copiaPersona({ historial: { alcance: 'todo', hechos, hay_hechos_sin_asociar: false } }))
    const lineas = within(bloque('Quién abrió o editó la ficha')).getAllByRole('listitem')
    const frases = lineas.map((l) => l.querySelector('.font-bold')!.textContent)
    expect(frases).toEqual([
      'Dio la autorización de la ficha',
      'Dio la autorización de los insumos',
      'Retiró la autorización de los pedidos',
      'Retiró una autorización',
      'Armó el pedido 4821',
      'Armó un pedido',
      'Confirmó el pedido 4821',
      'Canceló el pedido 4821',
      'Cambió qué hacer si falta un producto en el pedido 4821',
      'Empezó a pagar el pedido 4821',
      'Se aprobó el pago del pedido 4821',
      'Se devolvió dinero del pago del pedido 4821',
      'Se devolvió dinero de un pago',
    ])
    expect(lineas[4].querySelector('.font-bold .cifras')).toHaveTextContent('4821')
    expect(lineas[5].querySelector('.font-bold .cifras')).toBeNull()
  })
})

describe('1.2, «Tus datos»: F2 y F3', () => {
  it('F2: un grupo del que saliste, con el rol y las dos fechas, sin el nombre del grupo', async () => {
    apiCopia(copiaComoRespuesta(copiaCuenta(), 'matu-cuenta-2026-11-12.json'))
    render(<TusDatos />)
    await screen.findByRole('button', { name: 'Descargar en un archivo' })
    const filas = within(bloque('Tus grupos')).getAllByRole('listitem')
    expect(filas).toHaveLength(3)
    expect(filas[2]).toHaveTextContent('Un grupo del que salisteCuidaTe uniste el 01/09/2026.Saliste el 15/10/2026.')
  })

  it('F2: sin grupos activos, la frase de vacío arriba y debajo los que dejaste (5.3, 1.3)', async () => {
    apiCopia(copiaComoRespuesta(copiaCuenta({ grupos: [] }), 'matu-cuenta-2026-11-12.json'))
    render(<TusDatos />)
    await screen.findByRole('button', { name: 'Descargar en un archivo' })
    expect(bloque('Tus grupos')).toHaveTextContent('No estás en ningún grupo.Un grupo del que salisteCuidaTe uniste el 01/09/2026.Saliste el 15/10/2026.')
  })

  it('F3: el código de autorización en cifras, solo en el pago que lo trae', async () => {
    apiCopia(copiaComoRespuesta(copiaCuenta(), 'matu-cuenta-2026-11-12.json'))
    render(<TusDatos />)
    await screen.findByRole('button', { name: 'Descargar en un archivo' })
    const [credito, debito] = within(bloque('Tus pagos')).getAllByRole('listitem')
    const codigo = within(credito).getByText(/Código de autorización/)
    expect(codigo).toHaveTextContent('Código de autorización: 1213')
    expect(codigo.querySelector('.cifras')).toHaveTextContent('1213')
    expect(debito).not.toHaveTextContent('Código de autorización')
  })
})

describe('tercera revisión (P3): el «·» de las colas nunca queda solo al comienzo de un renglón', () => {
  /** Cada «·» del texto va precedido de un espacio duro (U+00A0), nunca de un espacio común. */
  const sinPuntoSuelto = (raiz: Element) => {
    const texto = raiz.textContent ?? ''
    expect(texto.match(/·/g)?.length ?? 0).toBeGreaterThan(0)
    expect(texto).not.toMatch(/ ·/)
    expect(texto).not.toMatch(/(^|[^\u00A0])·/)
  }

  it('«Datos de María»: compras, líneas y montos del pedido, aperturas e historial', async () => {
    await abrirPersona()
    const compras = bloque('Compras anotadas (últimos 90 días)')
    expect(within(compras).getAllByRole('listitem')[0].textContent).toContain('10/11/2026\u00A0· Anotó Carmen Soto')
    const pedido = within(bloque('Sus pedidos')).getAllByRole('listitem')[0]
    expect(pedido.textContent).toContain('$37.260.\u00A0· Devuelto: $5.290.'.replace('.\u00A0', '\u00A0'))
    expect(pedido.textContent).toContain('(comercio ficticio)\u00A0· Si falta:')
    for (const nombre of ['Compras anotadas (últimos 90 días)', 'Sus pedidos', 'Quién abrió o editó la ficha']) sinPuntoSuelto(bloque(nombre))
  })

  it('«Tus datos»: ingresos, avisos enviados y cuotas', async () => {
    apiCopia(copiaComoRespuesta(copiaCuenta(), 'matu-cuenta-2026-11-12.json'))
    render(<TusDatos />)
    await screen.findByRole('button', { name: 'Descargar en un archivo' })
    for (const nombre of ['Últimos ingresos', 'Avisos que te enviamos', 'Tus pagos']) sinPuntoSuelto(bloque(nombre))
  })
})

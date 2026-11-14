// MATU-63, especificación de diseño v1.2, sección 14: los siete hechos del pedido después de pagar en el
// historial de «Datos de» (criterios 26 a 30). jsdom no mide anchos: el reflujo (30) se verifica por la
// estructura de clases, como en misDatosRevision. Solo datos sintéticos.
import { render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CopiaDatosPersona } from '../src/compartido/api/misDatos'
import { DatosDePersona } from '../src/familia/DatosPersona'
import { familiaFalsa } from './familiaFalsa'
import { antes, apiCopia, copiaComoRespuesta, copiaPersona, dialogoDeJsdom, fijarAhora, hecho, MARIA, type Hecho } from './misDatosFalso'
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

const MATU = { tipo: 'matu' as const, nombre: null, activo: null }
const CARMEN = { tipo: 'persona' as const, nombre: 'Carmen Soto', activo: true }
const SALIO = { tipo: 'persona' as const, nombre: null, activo: false }

/** Tabla 14.1: tipo, quién, frase con referencia (sin el número), frase general y la clase del ícono de lucide. */
const SIETE: [Hecho['tipo'], Hecho['quien'], string, string, string][] = [
  ['devolucion_a_la_tarjeta', MATU, 'MATU devolvió dinero a la tarjeta por el pedido ', 'MATU devolvió dinero a la tarjeta', 'lucide-hand-coins'],
  ['pidio_un_retracto', CARMEN, 'Pidió un retracto del pedido ', 'Pidió un retracto', 'lucide-rotate-ccw'],
  ['codigo_de_retiro_generado', MATU, 'MATU preparó el código de retiro del pedido ', 'MATU preparó un código de retiro', 'lucide-key-round'],
  ['pedido_en_camino', MATU, 'MATU salió a entregar el pedido ', 'MATU salió a entregar un pedido', 'lucide-truck'],
  ['pedido_entregado', MATU, 'MATU entregó el pedido ', 'MATU entregó un pedido', 'lucide-package-check'],
  ['pedido_no_entregado', MATU, 'MATU no pudo entregar el pedido ', 'MATU no pudo entregar un pedido', 'lucide-package-x'],
  ['retracto_resuelto', MATU, 'MATU respondió el retracto del pedido ', 'MATU respondió un retracto', 'lucide-message-square-reply'],
]

/** Los siete con la referencia 4821, después los siete sin ella, y el retracto de alguien que salió. */
function hechosDePedido(): Hecho[] {
  const con = SIETE.map(([tipo, quien], i) => ({ ...hecho(tipo, antes(0, 1 + i), quien), referencia: '4821' }))
  const sin = SIETE.map(([tipo, quien], i) => hecho(tipo, antes(0, 10 + i), quien))
  return [...con, ...sin, { ...hecho('pidio_un_retracto', antes(0, 20), SALIO), referencia: '4821' }]
}

async function lineasDelHistorial() {
  const c: CopiaDatosPersona = copiaPersona({ historial: { alcance: 'todo', hechos: hechosDePedido(), hay_hechos_sin_asociar: false } })
  apiCopia(copiaComoRespuesta(c, 'matu-datos-2026-11-13.json'))
  render(<DatosDePersona />)
  await screen.findByRole('button', { name: 'Descargar en un archivo' })
  return within(screen.getByRole('region', { name: 'Quién abrió o editó la ficha' })).getAllByRole('listitem')
}
const frase = (li: HTMLElement) => li.querySelector('.font-bold')!
/** La cola «a las {HH:MM} · {nombre}», que puede llevar espacios duros. */
const cola = (li: HTMLElement) => li.querySelector('.text-tenue')!.textContent!

describe('MATU-63, 14.3: los hechos del pedido en «Datos de»', () => {
  it('26 y 27: se muestran los siete, con su ícono; con referencia la frase termina en ella, en cifras; sin ella, la general', async () => {
    const lineas = await lineasDelHistorial()
    expect(lineas).toHaveLength(15)
    SIETE.forEach(([, , conReferencia, general, icono], i) => {
      const conRef = lineas[i]
      expect(frase(conRef).textContent).toBe(`${conReferencia}4821`)
      expect(frase(conRef).lastElementChild).toHaveClass('cifras')
      expect(frase(conRef).lastElementChild).toHaveTextContent('4821')
      const baldosa = conRef.querySelector('span[aria-hidden]')!
      expect(baldosa.className).toContain('bg-rocio')
      expect(baldosa.className).toContain('text-turquesa')
      expect(baldosa.querySelector(`svg.${icono}`)).not.toBeNull()
      const sinRef = lineas[7 + i]
      expect(frase(sinRef).textContent).toBe(general)
      expect(frase(sinRef).querySelector('.cifras')).toBeNull()
      expect(sinRef.querySelector(`svg.${icono}`)).not.toBeNull()
    })
  })

  it('28: los seis de MATU no llevan nombre en la cola; el retracto lleva el de quien lo pidió, o «alguien que ya no está…»', async () => {
    const lineas = await lineasDelHistorial()
    SIETE.forEach(([tipo], i) => {
      for (const li of [lineas[i], lineas[7 + i]]) {
        if (tipo === 'pidio_un_retracto') expect(cola(li)).toMatch(/^a las\s\d{2}:\d{2}\s·\sCarmen Soto$/)
        else expect(cola(li)).toMatch(/^a las\s\d{2}:\d{2}$/)
      }
    })
    expect(cola(lineas[14])).toMatch(/^a las\s\d{2}:\d{2}\s·\salguien que ya no está en el grupo$/)
  })

  it('29: ninguna línea tiene seis dígitos seguidos, el nombre de un comercio ni una dirección', async () => {
    const lineas = await lineasDelHistorial()
    const c = copiaPersona()
    const comercios = c.pedidos!.flatMap((p) => p.lineas.map((l) => l.comercio))
    const entrega = c.pedidos![0].entrega!
    for (const li of lineas) {
      const texto = li.textContent!
      expect(texto).not.toMatch(/\d{6}/)
      for (const comercio of comercios) expect(texto).not.toContain(comercio)
      for (const parte of [entrega.calle, entrega.comuna, 'Farmacia', 'Los Aromos']) expect(texto).not.toContain(parte)
    }
  })

  it('30: a 320 px y 200 %, la línea refluye: ícono arriba en angosto, frase que se parte y columna sin ancho mínimo', async () => {
    const lineas = await lineasDelHistorial()
    const larga = lineas[0]
    expect(frase(larga).textContent).toBe('MATU devolvió dinero a la tarjeta por el pedido 4821')
    for (const li of lineas) {
      const c = li.className.split(/\s+/)
      expect(c).toEqual(expect.arrayContaining(['angosto:flex-col', 'angosto:items-stretch']))
      expect(frase(li).className.split(/\s+/)).toContain('break-words')
      expect(frase(li).parentElement!.className.split(/\s+/)).toContain('min-w-0')
      expect(li.querySelector('.text-tenue')!.className.split(/\s+/)).toContain('break-words')
    }
  })
})

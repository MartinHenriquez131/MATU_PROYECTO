// MATU-115 (punto 4 de la tarjeta; MATU-81, decisión 468 y O3 del analista): el motivo por el que no se
// aceptó una devolución es un solo texto. Lo lee la familia en «Tus pedidos» y en «Datos de», y es el
// que el diálogo de la consola de operación dice que la familia va a ver. La pantalla de «Tus pedidos»
// con los dos motivos la recorre tusPedidos.test.tsx (MATU-81, C24); aquí, el diálogo con los dos y que
// las tres pantallas usan el mismo texto. Solo datos sintéticos.
import { configure, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { MIS_DATOS } from '../src/familia/textosMisDatos'
import { MOTIVO_RECHAZO_FAMILIA, TUS_PEDIDOS } from '../src/familia/textosTusPedidos'
import { AppOperacion } from '../src/operacion/AppOperacion'
import { RETRACTOS } from '../src/operacion/textos'
import { apiOperacion, conRegionesVivas, dialogoDeJsdom } from './operacionFalso'

configure({ asyncUtilTimeout: 5000 })
beforeEach(() => dialogoDeJsdom())

const MOTIVOS = [
  ['sello_abierto', 'El sello del producto se abrió.', 'El producto volvió con el sello abierto.'],
  ['producto_no_recibido', 'MATU no recibió el producto de vuelta.', 'No recibimos el producto de vuelta.'],
] as const

describe('MATU-115: el motivo de una devolución que no se aceptó', () => {
  it.each(MOTIVOS)('%s: el mismo texto en «Tus pedidos», en «Datos de» y en la consola', (motivo, _, familia) => {
    expect(MOTIVO_RECHAZO_FAMILIA[motivo]).toBe(familia)
    expect(TUS_PEDIDOS.motivoRechazo[motivo]).toBe(familia)
    expect(MIS_DATOS.seLePidioDevolver.motivo[motivo]).toBe(familia)
    expect(RETRACTOS.noDevolverDestacado(motivo)).toBe(`No se devuelve dinero. La familia ve el motivo: ${familia}`)
  })

  it.each(MOTIVOS)('%s: el diálogo de «No devolver» dice el texto que lee la familia, no el de la consola', async (motivo, consola, familia) => {
    const api = apiOperacion({})
    window.history.replaceState(null, '', '/operacion/retractos')
    conRegionesVivas(<AppOperacion />)
    const usuario = userEvent.setup({ delay: null })
    await usuario.click(await screen.findByRole('button', { name: /^Retracto del pedido 4826,/ }, { timeout: 5000 }))
    await screen.findByRole('heading', { level: 1, name: 'Retracto del pedido 4826' })
    await usuario.click(screen.getByRole('button', { name: 'No devolver' }))
    await usuario.click(screen.getByRole('radio', { name: consola }))
    await usuario.click(screen.getByRole('button', { name: 'No devolver' }))
    const dialogo = await screen.findByRole('dialog', { name: '¿No devolver el dinero de este retracto?' })
    expect(within(dialogo).getByText(`No se devuelve dinero. La familia ve el motivo: ${familia}`)).toBeVisible()
    expect(dialogo).not.toHaveTextContent(consola)
    // Todavía no se envía: falta confirmar en el diálogo. Al confirmar, va el motivo del contrato.
    expect(api.peticiones.some((p) => p.linea.endsWith('/resolver'))).toBe(false)
    await usuario.click(within(dialogo).getByRole('button', { name: 'No devolver' }))
    await waitFor(() => expect(api.peticiones.find((p) => p.linea.endsWith('/resolver'))?.cuerpo).toEqual({ decision: 'rechazar', motivo }))
  })
})

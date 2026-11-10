// MATU-75 (especificación 3, 5 y 6): la política en «Tu cuenta» (con y sin registro, y el `mailto:`),
// en las autorizaciones y en el relevo. Solo datos sintéticos.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Cuenta } from '../src/compartido/api/familia'
import { apiFamilia } from '../src/compartido/api/sesion'
import { DeclaracionFicha, useDeclaracionFicha } from '../src/familia/Alta'
import { TuCuenta } from '../src/familia/Cuenta'
import { Permiso } from '../src/familia/Insumos'
import { PantallaPin } from '../src/relevo/PantallaPin'
import { RUTA_POLITICA } from '../src/relevo/textos'
import { responderCon } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'
import { POLITICA_DE_PRUEBA, responderPolitica } from './politicaFalsa'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa(),
}))

const CUENTA: Cuenta = {
  id: '3c9d4e20-0000-4000-8000-0000000000c1',
  nombre: 'Carmen',
  email: 'carmen@example.org',
  celular_enmascarado: '+56 9 •••• ••37',
  celular_verificado: true,
  celular_canal: 'sms',
  // 23:30 del 09/11 en Chile (UTC−3): en UTC ya es el 10/11.
  politica_aceptada: { version: '0.11', huella: 'a'.repeat(64), aceptada_en: '2026-11-10T02:30:00Z' },
}

const ENLACE_SOLO = { name: 'Política de privacidad (se abre en otra pestaña)' }
const COMO_PEDIR = /Para cambiar tu nombre o tu correo, pedir una copia de tus datos o eliminar tu cuenta, escribe a/

describe('«Tu cuenta»: la política aceptada', () => {
  it('con registro: la versión y la fecha en hora de Chile, el enlace y cómo pedir con mailto:', async () => {
    responderCon(apiFamilia, { status: 200, cuerpo: CUENTA })
    responderPolitica()
    render(<TuCuenta />)

    const dato = await screen.findByText(/Aceptaste la versión/)
    expect(dato).toHaveTextContent('Aceptaste la versión 0.11 el 09/11/2026.')
    expect(screen.getByText('Política de privacidad', { selector: 'dt' })).toBeInTheDocument()
    const enlace = screen.getByRole('link', ENLACE_SOLO)
    expect(enlace).toHaveAttribute('href', '/privacidad')
    expect(enlace).toHaveAttribute('target', '_blank')
    expect(enlace).toHaveAttribute('rel', 'noopener noreferrer')

    const correo = await screen.findByRole('link', { name: 'privacidad@example.org' })
    // Sin asunto ni cuerpo: nada de la cuenta en la dirección.
    expect(correo).toHaveAttribute('href', 'mailto:privacidad@example.org')
    expect(correo).not.toHaveAttribute('target')
    expect(correo.closest('p')).toHaveTextContent(
      'Para cambiar tu nombre o tu correo, pedir una copia de tus datos o eliminar tu cuenta, escribe a privacidad@example.org desde el correo de tu cuenta.',
    )
    expect(correo.closest('dl')).toBeNull()
  })

  it('sin registro: «No tenemos registro de qué versión aceptaste.», con el enlace igual', async () => {
    responderCon(apiFamilia, { status: 200, cuerpo: { ...CUENTA, politica_aceptada: null } })
    responderPolitica()
    render(<TuCuenta />)

    expect(await screen.findByText('No tenemos registro de qué versión aceptaste.')).toBeInTheDocument()
    expect(screen.queryByText(/Aceptaste la versión/)).not.toBeInTheDocument()
    expect(screen.getByRole('link', ENLACE_SOLO)).toHaveAttribute('href', '/privacidad')
  })

  it('sin correo_contacto, el párrafo de cómo pedir no aparece y nunca se ve un marcador', async () => {
    responderCon(apiFamilia, { status: 200, cuerpo: CUENTA })
    const politica = responderPolitica({ status: 200, cuerpo: { ...POLITICA_DE_PRUEBA, correo_contacto: null } })
    const { container } = render(<TuCuenta />)

    await screen.findByText(/Aceptaste la versión/)
    await vi.waitFor(() => expect(politica).toEqual(['GET /v1/politica']))
    expect(screen.queryByText(COMO_PEDIR)).not.toBeInTheDocument()
    expect(container.querySelector('a[href^="mailto:"]')).toBeNull()
    expect(container.textContent).not.toMatch(/\{|correo_privacidad/)
  })

  it('si la política no llega, la cuenta se ve igual, sin el párrafo', async () => {
    responderCon(apiFamilia, { status: 200, cuerpo: CUENTA })
    responderPolitica({ status: 503 })
    render(<TuCuenta />)

    await screen.findByText(/Aceptaste la versión/)
    expect(screen.queryByText(COMO_PEDIR)).not.toBeInTheDocument()
  })
})

function AutorizacionFicha() {
  const d = useDeclaracionFicha()
  return <DeclaracionFicha pila="María" d={d} />
}

const LEE = 'Lee la política de privacidad (se abre en otra pestaña) antes de autorizar.'

describe('Las autorizaciones: «Lee la política de privacidad antes de autorizar.»', () => {
  it('la ficha (alta y volver a autorizar): último párrafo de «Lo que declaras», al elegir la calidad', async () => {
    render(<AutorizacionFicha />)
    expect(screen.queryByText(/antes de autorizar/)).not.toBeInTheDocument()

    await userEvent.click(screen.getAllByRole('radio')[0])

    const parrafo = screen.getByText(/antes de autorizar/)
    expect(parrafo).toHaveTextContent(LEE)
    expect(parrafo.parentElement?.lastElementChild).toBe(parrafo)
    expect(screen.getByRole('link', { name: 'política de privacidad (se abre en otra pestaña)' })).toHaveAttribute('href', '/privacidad')
  })

  it('el permiso de insumos', () => {
    responderCon(apiFamilia, { status: 201 })
    render(<Permiso pila="María" personaId="3c9d4e20-0000-4000-8000-0000000000aa" onListo={vi.fn()} onNoEncontrado={vi.fn()} />)

    const parrafo = screen.getByText(/antes de autorizar/)
    expect(parrafo).toHaveTextContent(LEE)
    const enlace = screen.getByRole('link', { name: 'política de privacidad (se abre en otra pestaña)' })
    expect(enlace).toHaveAttribute('target', '_blank')
    expect(enlace).toHaveAttribute('rel', 'noopener noreferrer')
  })
})

describe('El relevo: el enlace a la política', () => {
  it('RUTA_POLITICA es /privacidad, sin fragmento, en otra pestaña, y el aviso trae el correo de 7.5', () => {
    expect(RUTA_POLITICA).toBe('/privacidad')
    window.history.replaceState(null, '', '/r#ejemplo-tres-campos')
    render(<PantallaPin presentacion={{ nombre_pila_comparte: 'Carmen', nombre_pila: 'María' }} onCanjear={vi.fn()} />)

    const enlace = screen.getByRole('link', ENLACE_SOLO)
    expect(enlace).toHaveAttribute('href', '/privacidad')
    expect(enlace.getAttribute('href')).not.toContain('#')
    // El ícono junto al primer renglón cuando el texto se parte (v0.2, P3).
    expect(enlace).toHaveClass('items-start', 'py-3', 'min-h-12')
    expect(enlace.querySelector('svg')).toHaveClass('mt-0.5')
    expect(enlace).toHaveAttribute('target', '_blank')
    expect(enlace).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getByText(/Puedes pedir ver, corregir o borrar tus datos escribiendo a cuidaconmatu@gmail\.com\./)).toBeInTheDocument()
  })
})

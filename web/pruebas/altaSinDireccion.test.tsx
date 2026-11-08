// MATU-68, revisión del analista (Jorge, 08-11, opción A): el alta deja de pedir la dirección, que
// se pedirá con el primer pedido (MATU-61). «¿A quién cuidas?» no muestra campos de dirección, y al
// pulsar «Acepto y registro» sale una sola petición, con la persona y la autorización juntas y sin
// `direccion`: nada de la persona se guarda antes de autorizar, ni en la API ni en el navegador.
// Falla sin el cambio: antes la pantalla mostraba Calle, Número, Comuna y Depto, y el cuerpo llevaba
// `direccion: null`. Solo datos sintéticos.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { AQuien, Autorizacion } from '../src/familia/Alta'
import { familiaFalsa } from './familiaFalsa'

const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g1'
const PERSONA_ID = '3c9d4e20-0000-4000-8000-0000000000aa'

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

interface Pedida {
  linea: string
  cuerpo?: unknown
}

function api() {
  const pedidas: Pedida[] = []
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    pedidas.push({
      linea: `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`,
      cuerpo: typeof config.data === 'string' && config.data ? JSON.parse(config.data) : undefined,
    })
    const cuerpo = { id: PERSONA_ID, nombre: 'María Soto', nombre_pila: 'María', nivel_apoyo: 'apoyo_total', direccion: null, consentimiento: null }
    return { data: cuerpo, status: 201, statusText: '', headers: {}, config, request: {} } as AxiosResponse
  }
  return pedidas
}

let guardado: string[] = []
beforeEach(() => {
  guardado = []
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    guardado.push(clave)
  })
})

describe('El alta sin dirección', () => {
  it('«¿A quién cuidas?» no pide la dirección, y el borrador solo lleva nombre, cómo le dicen y el apoyo', async () => {
    const pedidas = api()
    contexto = familiaFalsa({ borrador: { nombre: '', pila: '', apoyo: null } } as never)
    window.history.replaceState(null, '', '/empezar/persona')
    render(<AQuien />)

    expect(screen.queryByText(/¿Dónde vive\?/)).not.toBeInTheDocument()
    expect(screen.queryByText(/primer pedido/)).not.toBeInTheDocument()
    for (const campo of ['Calle', 'Número', 'Comuna', 'Depto (si tiene)']) expect(screen.queryByLabelText(campo)).not.toBeInTheDocument()
    expect(screen.queryAllByRole('group').map((g) => g.textContent)).not.toContainEqual(expect.stringMatching(/Dónde vive/))

    const u = userEvent.setup()
    await u.type(screen.getByLabelText('¿Cómo se llama?'), 'María Soto')
    await u.type(screen.getByLabelText(/¿Cómo le dicen\?/), 'María')
    await u.click(screen.getByRole('radio', { name: 'Necesita apoyo en todo' }))
    await u.click(screen.getByRole('button', { name: 'Continuar' }))

    expect(contexto.fijar).toHaveBeenCalledWith({ borrador: { nombre: 'María Soto', pila: 'María', apoyo: 'apoyo_total' } })
    expect(window.location.pathname).toBe('/empezar/autorizacion')
    // Hasta aquí nada sale del navegador ni se guarda en él.
    expect(pedidas).toEqual([])
    expect(guardado).toEqual([])
  })

  it('«Acepto y registro» manda en una sola petición la persona y la autorización, sin `direccion`', async () => {
    const pedidas = api()
    // Con los campos de dirección de antes, vacíos: así, sin el cambio, la prueba falla porque el
    // cuerpo lleva `direccion: null`, y no por un campo que falta en el borrador.
    const borrador = { nombre: 'María Soto', pila: 'María', apoyo: 'apoyo_total', calle: '', numero: '', comuna: '', depto: '' }
    contexto = familiaFalsa({ borrador, grupoId: GRUPO_ID, personas: [] } as never)
    window.history.replaceState(null, '', '/empezar/autorizacion')
    render(<Autorizacion />)

    const u = userEvent.setup()
    await u.click(screen.getByRole('radio', { name: /María lo autoriza y yo lo registro/ }))
    // Elegir la calidad no envía nada: la persona no existe en la API antes de autorizar.
    expect(pedidas).toEqual([])
    await u.click(screen.getByRole('button', { name: 'Acepto y registro a María' }))

    await waitFor(() => expect(window.location.pathname).toBe('/cuenta/celular'))
    expect(pedidas).toEqual([
      {
        linea: `POST /v1/grupos/${GRUPO_ID}/personas-cuidadas`,
        cuerpo: { nombre: 'María Soto', nombre_pila: 'María', nivel_apoyo: 'apoyo_total', calidad_otorgante: 'titular', referencia_documento: null, aviso: null },
      },
    ])
    expect(pedidas[0].cuerpo).not.toHaveProperty('direccion')
    expect(guardado).toEqual([])
  })
})

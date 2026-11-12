// MATU-42 y MATU-53: invitar a alguien al grupo (especificación docs/diseno/matu-53-invitar-grupo.md
// v1.1, sección 3). Ningún rol de partida, la advertencia de admin, la vista previa, crear (429, sin
// red y 404), y «Invitación lista»: el código una sola vez, «Repetir el código», enviar y copiar sin el
// código. Solo datos sintéticos.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { InvitacionLista, Invitar } from '../src/familia/Invitar'
import type { RespuestaFalsa } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'
import { miembroDePrueba } from './miembrosFalsos'

const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g1'
const MARIA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María' }
const URL_INVITACION = 'http://localhost/invitacion#TokenSinteticoDeInvitacion0123456789abcdefghij'
const CREADA = { id: 'i1', rol: 'cuidador', url: URL_INVITACION, codigo: '4729', creada_en: '2026-11-12T21:30:00Z', expira_en: '2026-11-20T00:30:00Z' }

let contexto = familiaFalsa()
vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => contexto,
}))

let escrituras: string[] = []
beforeEach(() => {
  escrituras = []
  window.history.replaceState(null, '', '/grupo/invitar')
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
})
afterEach(() => {
  Object.defineProperty(navigator, 'share', { value: undefined, configurable: true })
})

interface Pedida {
  linea: string
  cuerpo?: Record<string, unknown>
  grupo: unknown
}
function api(atender: (p: Pedida) => RespuestaFalsa | Promise<RespuestaFalsa>) {
  const pedidas: Pedida[] = []
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const p: Pedida = {
      linea: `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`,
      cuerpo: typeof config.data === 'string' && config.data ? JSON.parse(config.data) : undefined,
      grupo: config.headers?.get?.('X-Grupo-Id'),
    }
    pedidas.push(p)
    const r = await atender(p)
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  return pedidas
}
const problema = (status: number, tipo: string): RespuestaFalsa => ({ status, cuerpo: { type: `/errores/${tipo}`, title: 'TEXTO DE LA API QUE NO SE MUESTRA', status } })

function apiInvitar(crear: (p: Pedida) => RespuestaFalsa = () => ({ status: 201, cuerpo: CREADA })) {
  return api((p) => {
    if (p.linea === `GET /v1/grupos/${GRUPO_ID}/miembros`) return { status: 200, cuerpo: { miembros: [miembroDePrueba({ nombre: 'Carmen Soto' })] } }
    if (p.linea === `POST /v1/grupos/${GRUPO_ID}/invitaciones`) return crear(p)
    if (p.linea === 'GET /v1/grupos') return { status: 200, cuerpo: [{ id: GRUPO_ID, nombre: 'Familia Soto', rol: 'cuidador', puede_ver_plan: false }] }
    return problema(404, 'no-encontrado')
  })
}

function abrirInvitar(cambios: Record<string, unknown> = {}) {
  contexto = familiaFalsa({
    grupo: { id: GRUPO_ID, nombre: 'Familia Soto', rol: 'admin', puede_ver_plan: false },
    rol: 'admin',
    personas: [MARIA],
    capa3: true,
    conocerCapa3: vi.fn(),
    ...cambios,
  } as never)
  return render(
    <>
      <RegionesVivas />
      <Invitar />
    </>,
  )
}

const opcion = (nombre: string) => screen.getByRole('radio', { name: nombre })

describe('/grupo/invitar', () => {
  it('ningún rol elegido, los cuatro con su descripción, sin campos de contacto, y la nota de contarle', async () => {
    apiInvitar()
    abrirInvitar()
    expect(screen.getByRole('heading', { level: 1, name: 'Invitar a alguien al grupo' })).toBeVisible()
    expect(screen.getByText('Le mandas un enlace desde tu teléfono y le dictas un código aparte. No guardamos su correo ni su teléfono.')).toBeVisible()
    const grupo = screen.getByRole('group', { name: '¿Qué podrá hacer?' })
    expect(within(grupo).getAllByRole('radio')).toHaveLength(4)
    for (const r of within(grupo).getAllByRole('radio')) expect(r).not.toBeChecked()
    expect(opcion('Administra el grupo')).toHaveAccessibleDescription('Ve y cambia todo, comparte la ficha, invita y cambia los permisos.')
    expect(opcion('Cuida')).toHaveAccessibleDescription('Ve y cambia la ficha y los insumos, y comparte la ficha con quien te reemplaza.')
    expect(opcion('Paga')).toHaveAccessibleDescription('Ve los insumos y paga los pedidos. Ve la ficha solo si quien administra le da permiso.')
    expect(opcion('Se informa')).toHaveAccessibleDescription('Ve el nombre de María y sus insumos. No ve la ficha.')
    // 10.4: ningún campo de correo, teléfono ni nombre.
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.getByText('Si María puede comprenderlo, cuéntale que invitaste a otra persona.')).toBeVisible()
    expect(screen.getByText('Vale 7 días y sirve una sola vez.')).toBeVisible()
    // El único macizo turquesa es «Crear la invitación».
    const macizos = [...document.querySelectorAll('.bg-turquesa')]
    expect(macizos).toHaveLength(1)
    expect(macizos[0]).toHaveAccessibleName('Crear la invitación')
  })

  it('sin la capa 3, «Paga» no nombra los pedidos', () => {
    apiInvitar()
    abrirInvitar({ capa3: false })
    expect(opcion('Paga')).toHaveAccessibleDescription('Ve los insumos. Ve la ficha solo si quien administra le da permiso.')
  })

  it('crear sin elegir no pide nada: el error bajo la leyenda y el foco en la primera opción', async () => {
    const pedidas = apiInvitar()
    abrirInvitar()
    await userEvent.click(screen.getByRole('button', { name: 'Crear la invitación' }))
    const error = screen.getByText('Elige qué podrá hacer.')
    expect(error).toBeVisible()
    // 3.2: bajo la leyenda, antes de las opciones, y el grupo lo anuncia.
    expect(error.compareDocumentPosition(opcion('Administra el grupo')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByRole('group', { name: '¿Qué podrá hacer?' })).toHaveAccessibleDescription('Elige qué podrá hacer.')
    await waitFor(() => expect(opcion('Administra el grupo')).toHaveFocus())
    expect(pedidas.filter((p) => p.linea.startsWith('POST'))).toEqual([])
  })

  it('la advertencia de admin aparece solo con «Administra el grupo», en una región viva montada desde el principio', async () => {
    apiInvitar()
    abrirInvitar()
    const regiones = [...document.querySelectorAll('[aria-live="polite"]')]
    expect(screen.queryByText(/Podrá invitar, cambiar permisos/)).toBeNull()
    await userEvent.click(opcion('Administra el grupo'))
    const aviso = screen.getByText('Podrá invitar, cambiar permisos y sacar a otras personas, también a ti.')
    expect(aviso).toBeVisible()
    expect(regiones).toContain(aviso.closest('[aria-live="polite"]'))
    await userEvent.click(opcion('Cuida'))
    expect(screen.queryByText(/Podrá invitar, cambiar permisos/)).toBeNull()
  })

  it('la vista previa usa el nombre de pila de quien invita y el rol elegido', async () => {
    apiInvitar()
    abrirInvitar()
    expect(await screen.findByText('Carmen te invita a su grupo de cuidado en MATU, para el rol que elijas.')).toBeVisible()
    await userEvent.click(opcion('Paga'))
    expect(screen.getByText('Carmen te invita a su grupo de cuidado en MATU, para pagar.')).toBeVisible()
  })

  it('crear: solo el rol en el cuerpo, «Creando la invitación…» con las opciones quietas, y a «Invitación lista»', async () => {
    let soltar: () => void = () => {}
    const pedidas = apiInvitar(() => ({ status: 201, cuerpo: CREADA }))
    const original = apiFamilia.defaults.adapter as (c: InternalAxiosRequestConfig) => Promise<AxiosResponse>
    apiFamilia.defaults.adapter = async (c: InternalAxiosRequestConfig) => {
      if (c.method === 'post') await new Promise<void>((r) => (soltar = r))
      return original(c)
    }
    abrirInvitar()
    await userEvent.click(opcion('Cuida'))
    await userEvent.click(screen.getByRole('button', { name: 'Crear la invitación' }))
    const boton = screen.getByRole('button', { name: /Crear la invitación/ })
    expect(boton).toHaveAttribute('aria-busy', 'true')
    expect(opcion('Cuida')).toBeDisabled()
    soltar()
    await waitFor(() => expect(window.location.pathname).toBe('/grupo/invitar/listo'))
    const post = pedidas.find((p) => p.linea.startsWith('POST'))!
    expect(post.cuerpo).toEqual({ rol: 'cuidador' })
    expect(post.grupo).toBe(GRUPO_ID)
    expect(escrituras).toEqual([])
  })

  it.each([
    [{ ...problema(429, 'tope-invitaciones'), cabeceras: { 'retry-after': '3600' } }, 'Ya creaste muchas invitaciones hoy. Vuelve a intentarlo mañana.'],
    [{ status: 500, cuerpo: { type: '/errores/error-interno', status: 500 } }, 'No pudimos crear la invitación. Revisa tu conexión y vuelve a intentarlo.'],
  ])('un error al crear se anuncia sobre el botón y el rol sigue elegido', async (respuesta, texto) => {
    apiInvitar(() => respuesta)
    abrirInvitar()
    await userEvent.click(opcion('Paga'))
    await userEvent.click(screen.getByRole('button', { name: 'Crear la invitación' }))
    expect(await screen.findByText(texto)).toBeVisible()
    expect(opcion('Paga')).toBeChecked()
    expect(window.location.pathname).toBe('/grupo/invitar')
  })

  it('404 (dejó de administrar): vuelve a Grupo familiar con el aviso y el rol nuevo', async () => {
    apiInvitar(() => problema(404, 'no-encontrado'))
    abrirInvitar()
    await userEvent.click(opcion('Cuida'))
    await userEvent.click(screen.getByRole('button', { name: 'Crear la invitación' }))
    await waitFor(() => expect(window.location.pathname).toBe('/grupo'))
    expect(contexto.fijar).toHaveBeenCalledWith(
      expect.objectContaining({ aviso: { titulo: 'Ya no administras el grupo, así que no puedes invitar.', tono: 'rocio' }, grupos: [expect.objectContaining({ rol: 'cuidador' })] }),
    )
  })
})

// ---------------------------------------------------------------- 3.4 a 3.6

/** Crea la invitación desde la pantalla, para que «Invitación lista» la reciba en memoria. */
async function crearYAbrirLista() {
  apiInvitar()
  const { unmount } = abrirInvitar()
  await userEvent.click(opcion('Cuida'))
  await userEvent.click(screen.getByRole('button', { name: 'Crear la invitación' }))
  await waitFor(() => expect(window.location.pathname).toBe('/grupo/invitar/listo'))
  unmount()
  return render(
    <>
      <RegionesVivas />
      <InvitacionLista />
    </>,
  )
}

describe('/grupo/invitar/listo', () => {
  it('el código una sola vez, quieto, leído dígito a dígito, y la dirección cortada', async () => {
    await crearYAbrirLista()
    expect(screen.getByRole('heading', { level: 1, name: 'Invitación lista' })).toBeVisible()
    expect(screen.getByText(/^Vale una sola vez/)).toHaveTextContent('Vale una sola vez, hasta el 19/11/2026 a las 21:30.')
    expect(screen.getByText('Para cuidar.')).toBeVisible()
    const codigo = screen.getByRole('img', { name: 'Código: 4 7 2 9' })
    expect(codigo).toHaveAttribute('tabindex', '-1')
    // 3.4: los dígitos aparecen quietos; la caída es solo del PIN del relevo.
    expect(codigo.querySelector('.animate-digito')).toBeNull()
    expect(screen.getByText('Díselo por teléfono, no lo escribas en el mensaje.').tagName).toBe('B')
    expect(screen.getByText('localhost/invitacion#TokenS…')).toBeVisible()
    expect(document.body.textContent).not.toContain(URL_INVITACION)
    expect(document.title).not.toContain('4729')
    expect(window.location.href).not.toContain('4729')
    expect(window.history.state).toBeNull()
  })

  it('«Repetir el código» lleva el foco a los dígitos', async () => {
    await crearYAbrirLista()
    await userEvent.click(screen.getByRole('button', { name: 'Repetir el código' }))
    await waitFor(() => expect(screen.getByRole('img', { name: 'Código: 4 7 2 9' })).toHaveFocus())
  })

  it('con la hoja de compartir: «Enviar el enlace» manda solo el enlace, nunca el código', async () => {
    const share = vi.fn(async () => {})
    Object.defineProperty(navigator, 'share', { value: share, configurable: true })
    await crearYAbrirLista()
    await userEvent.click(screen.getByRole('button', { name: 'Enviar el enlace' }))
    expect(share).toHaveBeenCalledWith({ text: `Te invito a mi grupo de cuidado en MATU. Abre este enlace para unirte. El código te lo digo por teléfono. ${URL_INVITACION}` })
    const enviado = JSON.stringify(share.mock.calls)
    expect(enviado).not.toContain('4729')
    expect(enviado).not.toMatch(/María|Familia Soto/)
    expect(screen.getByRole('button', { name: 'Copiar el enlace' })).toHaveClass('ring-turquesa/80')
  })

  it('sin la hoja de compartir: «Copiar el enlace» es el principal, copia solo la dirección y lo confirma', async () => {
    const writeText = vi.fn(async () => {})
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    await crearYAbrirLista()
    expect(screen.queryByRole('button', { name: 'Enviar el enlace' })).toBeNull()
    const copiar = screen.getByRole('button', { name: 'Copiar el enlace' })
    expect(copiar).toHaveClass('bg-turquesa')
    await userEvent.click(copiar)
    expect(writeText).toHaveBeenCalledWith(URL_INVITACION)
    expect(await screen.findByText('Enlace copiado. Pégalo en tu mensaje.')).toBeVisible()
  })

  it('si copiar falla sin la hoja, muestra el enlace completo para seleccionarlo', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: vi.fn(async () => Promise.reject(new Error('no'))) }, configurable: true })
    await crearYAbrirLista()
    await userEvent.click(screen.getByRole('button', { name: 'Copiar el enlace' }))
    expect(await screen.findByRole('textbox', { name: 'Enlace de la invitación' })).toHaveValue(URL_INVITACION)
  })

  it('al volver a entrar (o recargar), el código ya no se puede ver', async () => {
    const { unmount } = await crearYAbrirLista()
    unmount()
    render(<InvitacionLista />)
    expect(screen.getByRole('heading', { level: 1, name: 'Invitación lista' })).toBeVisible()
    expect(screen.getByText('El código ya no se puede ver')).toBeVisible()
    expect(screen.getByText('Por seguridad se muestra una sola vez. Si se perdió, anula la invitación desde Grupo familiar y crea una nueva.')).toBeVisible()
    expect(screen.queryByRole('img', { name: /Código/ })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Volver a Grupo familiar' }))
    expect(window.location.pathname).toBe('/grupo')
  })
})

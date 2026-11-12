// MATU-72 4: después del borrado, con la app de la familia entera (el estado real en memoria, la
// regla de ruta y la barra). Sin una sola persona, a `/empezar/persona` con la nota y el formulario
// vacío; con otras, en `/grupo` con el foco en la nota y sin rastro de la borrada en la barra ni en el
// selector. Nada en el navegador ni en la URL. Solo datos sintéticos.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios, { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { StrictMode } from 'react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { RegionesVivas } from '../src/compartido/ui/Anuncios'
import { AppFamilia } from '../src/familia/AppFamilia'
import type { RespuestaFalsa } from './apiFalsa'
import { respuestaDelGrupo } from './miembrosFalsos'

const GRUPO_ID = '3c9d4e20-0000-4000-8000-0000000000g1'
const MARIA = { id: '3c9d4e20-0000-4000-8000-0000000000aa', nombre: 'María Soto', nombre_pila: 'María', nivel_apoyo: 'apoyo_parcial' }
const PEDRO = { id: '3c9d4e20-0000-4000-8000-0000000000bb', nombre: 'Pedro Rojas', nombre_pila: 'Pedro', nivel_apoyo: 'apoyo_parcial' }

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.hasAttribute('open')) return
    this.removeAttribute('open')
    this.dispatchEvent(new Event('close'))
  }
})

let escrituras: string[] = []
beforeEach(() => {
  escrituras = []
  for (const s of [localStorage, sessionStorage]) s.clear()
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (this: Storage, clave: string) {
    escrituras.push(clave)
  })
})

const VIGENTES = ['plan_cuidado', 'consumo'].map((finalidad) => ({
  finalidad,
  estado: 'vigente',
  id: '3c9d4e20-0000-4000-8000-0000000000c1',
  otorgado_en: '2026-11-04T15:00:00Z',
  revision_vence_en: null,
  revocado_en: null,
  borrado_en: null,
  borrada: false,
  se_puede_otorgar: true,
  calidad_otorgante: 'titular',
}))

/** La API: entrar con la cookie, un grupo admin y sus personas. El borrado saca a la persona de la lista. */
const GRUPO_2 = '3c9d4e20-0000-4000-8000-0000000000g2'
const LUIS = { id: '3c9d4e20-0000-4000-8000-0000000000cc', nombre: 'Luis Díaz', nombre_pila: 'Luis', nivel_apoyo: 'apoyo_parcial' }

function apiApp(personasIniciales: (typeof MARIA)[], enlacesCortados = 2, { dosGrupos = false } = {}) {
  let personas = [...personasIniciales]
  const pedidas: string[] = []
  const responder = (config: InternalAxiosRequestConfig, r: RespuestaFalsa): AxiosResponse => {
    const respuesta: AxiosResponse = { data: r.cuerpo ?? '', status: r.status, statusText: '', headers: r.cabeceras ?? {}, config, request: {} }
    if (r.status >= 400) throw new AxiosError(`HTTP ${r.status}`, AxiosError.ERR_BAD_REQUEST, config, {}, respuesta)
    return respuesta
  }
  axios.defaults.adapter = async (config) => responder(config, { status: 200, cuerpo: { access_token: 'token-sintetico', token_type: 'bearer', expires_in: 900 } })
  apiFamilia.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const linea = `${(config.method ?? 'get').toUpperCase()} ${config.url ?? ''}`
    pedidas.push(linea)
    if (linea === 'GET /v1/grupos')
      return responder(config, {
        status: 200,
        cuerpo: [
          { id: GRUPO_ID, nombre: 'Familia Rojas', rol: 'admin', puede_ver_plan: true },
          ...(dosGrupos ? [{ id: GRUPO_2, nombre: 'Familia Díaz', rol: 'observador', puede_ver_plan: false }] : []),
        ],
      })
    if (linea === `GET /v1/grupos/${GRUPO_2}/personas-cuidadas`) return responder(config, { status: 200, cuerpo: [LUIS] })
    if (linea === `GET /v1/grupos/${GRUPO_ID}/personas-cuidadas`) return responder(config, { status: 200, cuerpo: personas })
    if (/\/consentimientos$/.test(linea)) return responder(config, { status: 200, cuerpo: { autorizaciones: VIGENTES } })
    if (/\/plan\/accesos-relevo$/.test(linea)) return responder(config, { status: 200, cuerpo: { items: [], siguiente_cursor: null } })
    const m = /^POST \/v1\/personas-cuidadas\/([^/]+)\/borrado$/.exec(linea)
    if (m) {
      personas = personas.filter((p) => p.id !== m[1])
      return responder(config, { status: 200, cuerpo: { persona_id: m[1], borrado_en: '2026-11-08T15:00:00Z', enlaces_cortados: enlacesCortados, autorizaciones_retiradas: 2 } })
    }
    // MATU-53: quiénes forman el grupo, que Grupo familiar pide aparte (miembrosFalsos.ts).
    const delGrupo = respuestaDelGrupo(linea)
    if (delGrupo) return responder(config, delGrupo)
    return responder(config, { status: 404, cuerpo: { type: '/errores/no-encontrado', status: 404 } })
  }
  return pedidas
}

/**
 * Sin `StrictMode` por omisión: en el build de producción los efectos corren una sola vez, y es ese
 * orden (el del efecto de la nota antes que el de la regla de ruta) el que decide adónde va el foco.
 */
function abrirApp({ estricto = false } = {}) {
  window.history.replaceState(null, '', '/grupo')
  const app = (
    <>
      <RegionesVivas />
      <AppFamilia />
    </>
  )
  return render(estricto ? <StrictMode>{app}</StrictMode> : app)
}

async function borrar(pila: string) {
  await userEvent.click(await screen.findByRole('button', { name: `Borrar los datos de ${pila}` }, { timeout: 5000 }))
  const d = screen.getByRole('dialog')
  await userEvent.click(within(d).getByRole('checkbox', { name: 'Entiendo que esto no se puede deshacer.' }))
  await userEvent.click(within(d).getByRole('button', { name: 'Borrar todo' }))
}

/**
 * El texto de la página sin el de la nota de una sola vez (que también repite la región viva de
 * main.tsx al anunciarla): fuera de ella, nada debe nombrar a la persona borrada.
 */
function textoFueraDeLaNota(nota: Element) {
  const suyo = nota.textContent ?? ''
  return (document.body.textContent ?? '').split(suyo).join(' ')
}

/** La nota visible (la región viva de main.tsx repite su texto para anunciarlo). */
async function notaCon(texto: string) {
  await waitFor(() => expect(screen.getAllByText(texto).some((n) => n.closest('[data-aviso]'))).toBe(true))
  return screen.getAllByText(texto).map((n) => n.closest('[data-aviso]')).find(Boolean)!
}

describe('Después de borrar, con la app entera', () => {
  it('la única persona: a /empezar/persona con la nota de hecho, el foco en el título y el formulario vacío', async () => {
    const pedidas = apiApp([MARIA], 2)
    abrirApp({ estricto: true })
    await borrar('María')

    await waitFor(() => expect(window.location.pathname).toBe('/empezar/persona'))
    const titulo = await screen.findByRole('heading', { level: 1, name: '¿A quién cuidas?' })
    await waitFor(() => expect(titulo).toHaveFocus())
    const nota = await notaCon('Borramos los datos de María. Cortamos 2 enlaces.')
    expect(nota).toHaveAttribute('data-aviso', 'status')
    // 4.4: la nota va debajo del encabezado y antes del formulario.
    expect(titulo.compareDocumentPosition(nota!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(nota!.compareDocumentPosition(document.querySelector('form')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // El formulario empieza en blanco.
    expect(screen.getByRole('textbox', { name: /¿Cómo se llama\?/ })).toHaveValue('')
    expect(screen.getByRole('textbox', { name: /¿Cómo le dicen\?/ })).toHaveValue('')
    // 4.1 y 8.11: fuera de la nota, nada la nombra.
    expect(textoFueraDeLaNota(nota)).not.toMatch(/María|Soto/)

    expect(pedidas.filter((p) => p.endsWith('/borrado'))).toEqual([`POST /v1/personas-cuidadas/${MARIA.id}/borrado`])
    // 4.2: nunca a la ficha, los insumos ni compartir de la borrada; nada en la URL ni en el navegador.
    expect(window.location.href).not.toContain(MARIA.id)
    expect(escrituras).toEqual([])
    expect(localStorage.length + sessionStorage.length).toBe(0)
    expect(document.title).not.toMatch(/María/)
  })

  it('la nota es de una sola vez: al volver al paso «Persona» ya no está', async () => {
    apiApp([MARIA], 0)
    abrirApp()
    await borrar('María')
    expect(await notaCon('Borramos los datos de María. No había enlaces que abrieran.')).toBeVisible()
    // Ir y volver: la regla de ruta lleva otra vez al paso «Persona», sin la nota. Desde MATU-53,
    // Grupo familiar se abre sin persona registrada: se va por la ficha, que sí lleva al paso.
    window.history.pushState(null, '', '/ficha')
    window.dispatchEvent(new PopStateEvent('popstate'))
    await waitFor(() => expect(window.location.pathname).toBe('/empezar/persona'))
    await screen.findByRole('heading', { level: 1, name: '¿A quién cuidas?' })
    await waitFor(() => expect(screen.queryByText(/Borramos los datos de María/)).toBeNull())
  })

  it('con otra persona, la elegida borrada: queda en /grupo con la otra elegida y el foco en la nota', async () => {
    apiApp([MARIA, PEDRO], 1)
    abrirApp()
    // La elegida es la primera, María: el encabezado dice «Cuidas a María Soto».
    expect(await screen.findByRole('region', { name: 'Pedro Rojas' }, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByRole('banner')).toHaveTextContent('María Soto')
    await borrar('María')

    const nota = await notaCon('Borramos los datos de María. Cortamos 1 enlace.')
    await waitFor(() => expect(nota).toHaveFocus())
    expect(nota).toHaveAttribute('tabindex', '-1')
    expect(window.location.pathname).toBe('/grupo')
    expect(await screen.findByRole('region', { name: 'Pedro Rojas' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'María Soto' })).toBeNull()
    // El encabezado muestra la que quedó elegida, sin selector (queda una sola).
    expect(screen.getByRole('banner')).toHaveTextContent('Pedro Rojas')
    expect(textoFueraDeLaNota(nota)).not.toMatch(/María|Soto/)
    expect(escrituras).toEqual([])
    expect(window.location.href).not.toContain(MARIA.id)
  })

  it('con otra persona, borrando la que no está elegida: la elegida sigue, la sección sale y el foco va a la nota', async () => {
    apiApp([PEDRO, MARIA], 2)
    abrirApp()
    expect(await screen.findByRole('region', { name: 'María Soto' }, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByRole('banner')).toHaveTextContent('Pedro Rojas')
    await borrar('María')

    const nota = await notaCon('Borramos los datos de María. Cortamos 2 enlaces.')
    await waitFor(() => expect(nota).toHaveFocus())
    expect(screen.queryByRole('region', { name: 'María Soto' })).toBeNull()
    expect(screen.getByRole('region', { name: 'Pedro Rojas' })).toBeInTheDocument()
    expect(screen.getByRole('banner')).toHaveTextContent('Pedro Rojas')
    expect(textoFueraDeLaNota(nota)).not.toMatch(/María|Soto/)
    expect(escrituras).toEqual([])
  })

  it('con dos grupos y el selector abierto, la lista deja de ofrecerla en cuanto se borra', async () => {
    apiApp([MARIA, PEDRO], 0, { dosGrupos: true })
    abrirApp()
    await screen.findByRole('region', { name: 'Pedro Rojas' }, { timeout: 5000 })
    // El selector se abre antes y queda abierto: pide las personas de cada grupo y arma la lista.
    await userEvent.click(screen.getByRole('button', { name: 'María Soto', expanded: false }))
    expect(await screen.findByRole('radio', { name: /María Soto/ })).toBeInTheDocument()
    await borrar('María')
    await notaCon('Borramos los datos de María. No había enlaces que abrieran.')

    expect(screen.getByRole('radio', { name: /Luis Díaz/ })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Pedro Rojas/ })).toBeChecked()
    expect(screen.queryByRole('radio', { name: /María/ })).toBeNull()
  })
})

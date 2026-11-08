// MATU-68, punto 3: tras un 422 de la API, el foco llega al campo cuando ese campo ya está marcado
// inválido y con su mensaje asociado, igual que en Crear cuenta (`Alta.tsx`, `flushSync`). Sin la
// corrección, después de un `await` React podía confirmar el estado después del `setTimeout` que
// mueve el foco: el campo recibía el foco sin `aria-invalid` (o el foco no llegaba), y el lector de
// pantalla no anunciaba el error. Se registra el estado del campo en el instante del foco, y el
// `setTimeout` de 0 ms corre en el acto (`alInstante`): así la carrera deja de depender de cómo
// jsdom ordena las tareas, y la prueba falla sin `flushSync`. Datos sintéticos.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { apiFamilia } from '../src/compartido/api/sesion'
import { ConfirmarCelular } from '../src/familia/Cuenta'
import { CambiarConCodigo, PedirCodigo } from '../src/familia/Recuperar'
import { problema422, responderCon } from './apiFalsa'
import { familiaFalsa } from './familiaFalsa'

vi.mock('../src/familia/estado', async (original) => ({
  ...(await original<typeof import('../src/familia/estado')>()),
  useFamilia: () => familiaFalsa({ correo: 'ana.prueba@example.org', celularDesde: 'cuenta' } as never),
}))

/** Lo que tenía el campo en el instante en que recibió el foco: `aria-invalid` y su descripción. */
function alEnfocar(campo: HTMLElement) {
  const vistos: { invalido: string | null; descripcion: string }[] = []
  campo.addEventListener('focus', () => {
    const ids = (campo.getAttribute('aria-describedby') ?? '').split(' ').filter(Boolean)
    vistos.push({
      invalido: campo.getAttribute('aria-invalid'),
      descripcion: ids.map((id) => document.getElementById(id)?.textContent ?? '').join(' '),
    })
  })
  return vistos
}

/** El peor orden posible: el `setTimeout` de 0 ms de la pantalla corre antes de que React confirme. */
function alInstante() {
  const original = window.setTimeout.bind(window)
  vi.spyOn(window, 'setTimeout').mockImplementation(((fn: TimerHandler, ms?: number, ...args: unknown[]) => {
    if (!ms && typeof fn === 'function') {
      fn(...args)
      return 0
    }
    return original(fn, ms, ...args)
  }) as typeof window.setTimeout)
}

describe('Recuperar el acceso: el foco tras un 422', () => {
  it('pedir el código: el correo recibe el foco ya inválido y con «Revisa tu correo.»', async () => {
    responderCon(apiFamilia, { status: 422, cuerpo: problema422({ campo: 'email', tipo: 'value_error' }) })
    render(<PedirCodigo />)
    const u = userEvent.setup({ delay: null })
    const correo = screen.getByLabelText('Tu correo')
    const vistos = alEnfocar(correo)

    alInstante()
    await u.click(screen.getByRole('button', { name: 'Enviar código' }))

    await waitFor(() => expect(correo).toHaveFocus())
    expect(vistos.at(-1)).toEqual({ invalido: 'true', descripcion: 'Revisa tu correo.' })
  })

  it('el código y la contraseña: el 422 de `contrasena_nueva` deja el foco en la contraseña ya inválida', async () => {
    responderCon(apiFamilia, { status: 422, cuerpo: problema422({ campo: 'contrasena_nueva', tipo: 'string_too_long' }) })
    render(<CambiarConCodigo />)
    const u = userEvent.setup({ delay: null })
    const clave = screen.getByLabelText('Nueva contraseña')
    await u.type(screen.getByLabelText('Código'), '123456')
    await u.type(clave, 'contrasena-ejemplo') // pragma: allowlist secret
    const vistos = alEnfocar(clave)
    clave.blur()

    alInstante()
    await u.click(screen.getByRole('button', { name: 'Cambiar contraseña' }))

    await waitFor(() => expect(clave).toHaveFocus())
    expect(vistos.at(-1)).toEqual({ invalido: 'true', descripcion: 'Al menos 10 caracteres. La contraseña necesita entre 10 y 128 caracteres.' })
  })

  it('el código y la contraseña: el 422 `codigo-invalido` deja el foco en el código ya inválido', async () => {
    responderCon(apiFamilia, { status: 422, cuerpo: { type: '/errores/codigo-invalido', status: 422 } })
    render(<CambiarConCodigo />)
    const u = userEvent.setup({ delay: null })
    const codigo = screen.getByLabelText('Código')
    await u.type(codigo, '123456')
    await u.type(screen.getByLabelText('Nueva contraseña'), 'contrasena-ejemplo') // pragma: allowlist secret
    const vistos = alEnfocar(codigo)

    alInstante()
    await u.click(screen.getByRole('button', { name: 'Cambiar contraseña' }))

    await waitFor(() => expect(codigo).toHaveFocus())
    expect(vistos.at(-1)).toEqual({ invalido: 'true', descripcion: 'El código no es correcto o ya venció. Pide uno nuevo.' })
    expect(codigo).toHaveValue('')
  })
})

describe('Confirma tu celular: el foco tras un 422', () => {
  const cuenta = {
    id: '00000000-0000-4000-8000-000000000068',
    nombre: 'Ana Prueba',
    email: 'ana.prueba@example.org',
    celular_enmascarado: '+56 9 •••• ••37',
    celular_verificado: false,
    celular_canal: 'sms',
  }

  it.each([
    ['`codigo-invalido`', { type: '/errores/codigo-invalido', status: 422 }, 'El código no es correcto o ya venció. Pide uno nuevo.'],
    ['de validación', problema422({ campo: 'codigo', tipo: 'string_pattern_mismatch' }), 'El código tiene 6 números.'],
  ])('el 422 %s deja el foco en el código ya inválido', async (_caso, cuerpo, texto) => {
    responderCon(apiFamilia, { status: 200, cuerpo: cuenta }, { status: 202 }, { status: 422, cuerpo })
    render(<ConfirmarCelular />)
    const u = userEvent.setup({ delay: null })
    await u.click(await screen.findByRole('button', { name: 'Enviar código' }))
    const codigo = await screen.findByLabelText('Código')
    await waitFor(() => expect(codigo).toHaveFocus())
    await u.type(codigo, '123456')
    const vistos = alEnfocar(codigo)
    codigo.blur()

    alInstante()
    await u.click(screen.getByRole('button', { name: 'Confirmar' }))

    await waitFor(() => expect(codigo).toHaveFocus())
    expect(vistos.at(-1)).toEqual({ invalido: 'true', descripcion: texto })
  })
})

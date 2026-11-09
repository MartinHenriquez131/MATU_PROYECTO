// MATU-39 5.7 con el `sinGuardar` de MATU-67 y el `ProveedorFamilia` real: si la entrada vence con
// texto de la ficha sin guardar, la pantalla «no se guardó» lo muestra y no se va a /entrar. Los
// formularios de Insumos y Compartir registran `texto: ''`: con ellos, igual que sin nada, se va a
// /entrar. Con dos fuentes, se encuentra el texto. Pedido por QA el 09-11. Datos sintéticos.
import { act, render } from '@testing-library/react'
import { useEffect } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { registrarSinGuardar, type FuenteSinGuardar } from '../src/compartido/version'
import { ProveedorFamilia, useFamilia } from '../src/familia/estado'

let oyente: ((suceso: string) => void) | null = null
vi.mock('../src/compartido/api/sesion', async (original) => ({
  ...(await original<object>()),
  escucharSesion: (fn: (suceso: string) => void) => {
    oyente = fn
    return () => {
      oyente = null
    }
  },
  renovar: async () => false,
  fijarGrupo: () => {},
}))
const navegar = vi.fn()
vi.mock('../src/familia/ruteo', async (original) => ({ ...(await original<object>()), navegar: (r: string) => navegar(r) }))

let leido: string | null = null
function Formularios({ fuentes }: { fuentes: FuenteSinGuardar[] }) {
  const f = useFamilia()
  leido = f.textoPerdido ?? null
  useEffect(() => {
    const limpiar = fuentes.map((x) => registrarSinGuardar(f.sinGuardar, x))
    return () => limpiar.forEach((l) => l?.())
    // Las fuentes se registran una vez, como un formulario al montarse.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f.sinGuardar])
  return null
}

/** Abre la app sin entrada, registra las fuentes y vence la entrada. */
async function vencer(fuentes: FuenteSinGuardar[]) {
  navegar.mockClear()
  leido = null
  const r = render(
    <ProveedorFamilia>
      <Formularios fuentes={fuentes} />
    </ProveedorFamilia>,
  )
  await act(async () => {
    await new Promise((listo) => setTimeout(listo, 10))
  })
  await act(async () => {
    oyente!('vencida')
  })
  const res = { leido, rutas: navegar.mock.calls.map((c) => c[0]) }
  r.unmount()
  return res
}

describe('La entrada vence (5.7)', () => {
  it('con texto de la ficha sin guardar, muestra «no se guardó» y no va a /entrar', async () => {
    const r = await vencer([() => ({ texto: 'Le dicen Tito.', donde: 'Quién es', foco: 'seccion-texto' })])
    expect(r.leido).toBe('Le dicen Tito.')
    expect(r.rutas).not.toContain('/entrar')
  })

  it.each<[string, FuenteSinGuardar[]]>([
    ['sin nada registrado', []],
    ['con un editor sin cambios (`null`)', [() => null]],
    ['con un formulario de Insumos con cambios (texto vacío)', [() => ({ texto: '', titulo: 'Lo que anotaste de «Gasas» no se guardó.', foco: 'x' })]],
    ['con texto solo de espacios', [() => ({ texto: '   ' })]],
  ])('%s, va a /entrar sin «no se guardó»', async (_, fuentes) => {
    const r = await vencer(fuentes)
    expect(r.leido).toBeNull()
    expect(r.rutas).toContain('/entrar')
  })

  it('con dos fuentes, la última sin cambios, encuentra el texto de la otra', async () => {
    const r = await vencer([() => ({ texto: 'Le dicen Tito.' }), () => null])
    expect(r.leido).toBe('Le dicen Tito.')
    expect(r.rutas).not.toContain('/entrar')
  })
})

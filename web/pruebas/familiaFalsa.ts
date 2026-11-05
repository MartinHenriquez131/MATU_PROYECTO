// El contexto de la app de la familia que usan las pantallas de entrada, sin `ProveedorFamilia`
// (que al abrir renueva la sesión). Cada prueba lo pasa con `vi.mock` de src/familia/estado.
import { vi } from 'vitest'
import type { useFamilia } from '../src/familia/estado'

type Contexto = ReturnType<typeof useFamilia>

export function familiaFalsa(cambios: Partial<Contexto> = {}): Contexto {
  return {
    avisoEntrar: null,
    correo: '',
    destino: null,
    alEntrar: vi.fn(async () => {}),
    fijar: vi.fn(),
    anunciar: vi.fn(),
    ...cambios,
  } as unknown as Contexto
}

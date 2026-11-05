// Se carga antes de cada archivo de prueba: los matchers de jest-dom (toBeInvalid,
// toHaveAccessibleDescription, toHaveFocus…) y la limpieza del DOM y de los anuncios entre pruebas.
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import { olvidarAnuncios } from '../src/compartido/ui/Anuncios'

afterEach(() => {
  cleanup()
  olvidarAnuncios()
  window.history.replaceState(null, '', '/')
})

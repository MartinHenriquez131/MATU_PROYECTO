// Se carga antes de cada archivo de prueba: los matchers de jest-dom (toBeInvalid,
// toHaveAccessibleDescription, toHaveFocus…) y la limpieza del DOM entre pruebas.
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', '/')
})

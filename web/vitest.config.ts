import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Pruebas de interfaz (estrategia de pruebas v1.2, fila «Interfaz web»): Vitest + Testing Library
// sobre jsdom. Viven en pruebas/, fuera de src/: `vite build` solo empaqueta lo que importa
// index.html, así que nunca entran a web/dist. Sin el doble ni Tailwind: no hace falta servidor.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['pruebas/**/*.test.{ts,tsx}'],
    setupFiles: ['pruebas/preparacion.ts'],
    restoreMocks: true,
  },
})

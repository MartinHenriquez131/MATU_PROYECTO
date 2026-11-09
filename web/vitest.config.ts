import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Pruebas de interfaz (estrategia de pruebas v1.2, fila «Interfaz web»): Vitest + Testing Library
// sobre jsdom. Viven en pruebas/, fuera de src/: `vite build` solo empaqueta lo que importa
// index.html, así que nunca entran a web/dist. Sin el doble ni Tailwind: no hace falta servidor.
export default defineConfig({
  plugins: [react()],
  // MATU-67: la versión que corre en las pruebas. El `version.json` falso de cada prueba la compara.
  define: { __MATU_VERSION__: JSON.stringify('prueba') },
  test: {
    environment: 'jsdom',
    include: ['pruebas/**/*.test.{ts,tsx}'],
    setupFiles: ['pruebas/preparacion.ts'],
    restoreMocks: true,
    // Llenar un formulario con userEvent tarda 2 a 5 s con los archivos en paralelo (jsdom); 5 s,
    // el valor por omisión, dejaba la primera prueba de cada archivo al borde.
    testTimeout: 15_000,
  },
})

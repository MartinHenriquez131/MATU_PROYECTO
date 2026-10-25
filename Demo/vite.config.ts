import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

// Política de contenido: nada de terceros. Solo se agrega al construir, porque el
// servidor de desarrollo de Vite inyecta scripts propios.
function politicaDeContenido(unSoloArchivo: boolean): Plugin {
  const script = unSoloArchivo ? "'self' 'unsafe-inline'" : "'self'"
  const csp = [
    "default-src 'self'",
    `script-src ${script}`,
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self' data:",
    "img-src 'self' data: blob:",
    "connect-src 'none'",
    "manifest-src 'self'",
    "base-uri 'none'",
    "form-action 'none'",
  ].join('; ')
  return {
    name: 'matu-politica-contenido',
    apply: 'build',
    transformIndexHtml(html) {
      let salida = html.replace(
        '<meta charset="UTF-8" />',
        `<meta charset="UTF-8" />\n    <meta http-equiv="Content-Security-Policy" content="${csp}" />`,
      )
      if (unSoloArchivo) {
        // Un solo HTML: sin manifiesto ni archivos de íconos externos.
        salida = salida.replace(/\s*<link rel="(manifest|apple-touch-icon)"[^>]*>/g, '')
      }
      return salida
    },
  }
}

export default defineConfig(({ mode }) => {
  const single = mode === 'single'
  // Mismo origen y sin CORS: /v1 va a la API local de MATU (uvicorn en el puerto 8000).
  const proxy = { '/v1': { target: 'http://127.0.0.1:8000', changeOrigin: false } }
  return {
    server: { proxy },
    preview: { proxy },
    base: './',
    publicDir: single ? false : 'public',
    plugins: [react(), tailwindcss(), politicaDeContenido(single), ...(single ? [viteSingleFile()] : [])],
    build: { outDir: single ? 'dist-single' : 'dist', emptyOutDir: true },
  }
})

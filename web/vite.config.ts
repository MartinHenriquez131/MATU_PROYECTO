import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { dobleDelRelevo } from './doble/servidor'

// Política de contenido: nada de terceros, ni scripts, ni fuentes, ni analítica. Solo se agrega al
// construir, porque el servidor de desarrollo de Vite inyecta scripts propios.
function politicaDeContenido(): Plugin {
  const csp = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "font-src 'self'",
    "img-src 'self' data:",
    // Solo la propia API, en el mismo origen.
    "connect-src 'self'",
    "base-uri 'none'",
    "form-action 'none'",
    "object-src 'none'",
  ].join('; ')
  return {
    name: 'matu-politica-contenido',
    apply: 'build',
    transformIndexHtml(html) {
      return html.replace('<meta charset="UTF-8" />', `<meta charset="UTF-8" />\n    <meta http-equiv="Content-Security-Policy" content="${csp}" />`)
    },
  }
}

// `npm run dev` y `npm run preview` responden /v1/relevo con el doble del contrato (doble/).
// Con `--mode api`, /v1 va a la API local de MATU (uvicorn en el puerto 8000), sin el doble.
export default defineConfig(({ mode }) => {
  const conApi = mode === 'api'
  const proxy = { '/v1': { target: 'http://127.0.0.1:8000', changeOrigin: false } }
  return {
    base: '/',
    plugins: [react(), tailwindcss(), politicaDeContenido(), ...(conApi ? [] : [dobleDelRelevo()])],
    server: conApi ? { proxy } : {},
    preview: conApi ? { proxy } : {},
    build: { outDir: 'dist', emptyOutDir: true },
  }
})

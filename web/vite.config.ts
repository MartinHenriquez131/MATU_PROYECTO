import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { createHash } from 'node:crypto'
import { dobleDelRelevo } from './doble/servidor'
import { dobleDeVersion, VERSION_DE_DESARROLLO } from './doble/version'

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
    // MATU-62 (4.5): el único formulario que se envía es el de «Pagar», a Webpay (integración y
    // producción, las URL de backend/app/modules/payments/infrastructure/pasarela_transbank.py).
    // Con 'none' el navegador bloqueaba la navegación a Transbank.
    'form-action https://webpay3gint.transbank.cl https://webpay3g.transbank.cl',
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

// MATU-67: el identificador de la versión. Al construir, el bundle lleva una marca que se cambia,
// al final, por un hash de los nombres de los archivos del build (cada uno ya trae el hash de su
// contenido): el mismo código da el mismo identificador, así que volver a desplegar lo mismo no
// muestra el aviso. El identificador queda en el bundle y en dist/version.json, `{"version": "…"}`,
// sin datos de nadie. En desarrollo es fijo, y el doble lo sirve (doble/version.ts).
const MARCA_VERSION = '__matu_version_del_build__'
function versionDelBuild(): Plugin {
  let construyendo = false
  return {
    name: 'matu-version',
    enforce: 'post',
    config(_, { command }) {
      construyendo = command === 'build'
      return { define: { __MATU_VERSION__: JSON.stringify(construyendo ? MARCA_VERSION : VERSION_DE_DESARROLLO) } }
    },
    generateBundle(_, bundle) {
      if (!construyendo) return
      const nombres = Object.keys(bundle)
        .filter((n) => n !== 'index.html' && n !== 'version.json')
        .sort()
      const version = createHash('sha256').update(nombres.join(' ')).digest('hex').slice(0, 16)
      for (const archivo of Object.values(bundle)) {
        if (archivo.type === 'chunk' && archivo.code.includes(MARCA_VERSION)) archivo.code = archivo.code.split(MARCA_VERSION).join(version)
      }
      this.emitFile({ type: 'asset', fileName: 'version.json', source: JSON.stringify({ version }) })
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
    plugins: [react(), tailwindcss(), politicaDeContenido(), versionDelBuild(), ...(conApi ? [] : [dobleDelRelevo(), dobleDeVersion()])],
    server: conApi ? { proxy } : {},
    preview: conApi ? { proxy } : {},
    build: { outDir: 'dist', emptyOutDir: true },
  }
})

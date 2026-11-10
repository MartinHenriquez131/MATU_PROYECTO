// MATU-67: el doble de `/version.json`, para ver el aviso de versión nueva sin desplegar nada. En
// `npm run dev` responde la versión de desarrollo, la misma que lleva el bundle (no hay aviso). En
// `npm run preview` deja pasar el `version.json` de dist/. Con `/__doble/version-nueva` simula que
// se publicó otra versión: desde ahí, `/version.json` responde otra, y el aviso aparece en la
// próxima revisión (al volver a la pestaña, o a los 15 minutos). `/__doble/version-igual` vuelve a
// la normal. Todo con `Cache-Control: no-store`, como lo sirve la API (decisión 172), y en memoria.
// Nada de esta carpeta entra al build.
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'

export const VERSION_DE_DESARROLLO = 'desarrollo'

let simulada: string | null = null

function responder(res: ServerResponse, status: number, cuerpo: string, tipo: string) {
  res.statusCode = status
  res.setHeader('Content-Type', tipo)
  res.setHeader('Cache-Control', 'no-store')
  res.end(cuerpo)
}

function middleware(enPreview: boolean) {
  return (req: IncomingMessage, res: ServerResponse, siguiente: () => void) => {
    const ruta = (req.url ?? '').split('?')[0]
    if (ruta === '/__doble/version-nueva') {
      simulada = `simulada-${Date.now().toString(36)}`
      return responder(res, 200, `Listo: /version.json ahora responde «${simulada}». Vuelve a la pestaña de MATU para ver el aviso.\n`, 'text/plain; charset=utf-8')
    }
    if (ruta === '/__doble/version-igual') {
      simulada = null
      return responder(res, 200, 'Listo: /version.json vuelve a responder la versión que corre.\n', 'text/plain; charset=utf-8')
    }
    if (ruta !== '/version.json') return siguiente()
    if (simulada) return responder(res, 200, JSON.stringify({ version: simulada }), 'application/json')
    // En preview, el archivo del build.
    if (enPreview) {
      res.setHeader('Cache-Control', 'no-store')
      return siguiente()
    }
    return responder(res, 200, JSON.stringify({ version: VERSION_DE_DESARROLLO }), 'application/json')
  }
}

export function dobleDeVersion(): Plugin {
  return {
    name: 'matu-doble-version',
    configureServer(server) {
      server.middlewares.use(middleware(false))
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware(true))
    },
  }
}

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { PaginaRelevo } from './relevo/PaginaRelevo'

const raiz = createRoot(document.getElementById('raiz')!)

// Por ahora la única ruta es /r, la página del relevo. La app de la familia llega después.
const esRelevo = /^\/r\/?$/.test(window.location.pathname)

if (esRelevo) {
  raiz.render(
    <StrictMode>
      <PaginaRelevo />
    </StrictMode>,
  )
} else if (import.meta.env.DEV && import.meta.env.MODE !== 'api') {
  // Solo en desarrollo con el doble: la lista de enlaces de ejemplo. No entra al build.
  void import('./desarrollo/Ejemplos').then(({ Ejemplos }) =>
    raiz.render(
      <StrictMode>
        <Ejemplos />
      </StrictMode>,
    ),
  )
}

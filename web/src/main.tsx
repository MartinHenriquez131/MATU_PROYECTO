import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { AppFamilia } from './familia/AppFamilia'
import { PaginaRelevo } from './relevo/PaginaRelevo'

const raiz = createRoot(document.getElementById('raiz')!)
const ruta = window.location.pathname

// /r es la página del relevo (MATU-23): no usa el marco de la familia. Todo lo demás es la app de
// la familia (MATU-39). /ejemplos solo existe en desarrollo con el doble y no entra al build.
if (/^\/r\/?$/.test(ruta)) {
  raiz.render(
    <StrictMode>
      <PaginaRelevo />
    </StrictMode>,
  )
} else if (import.meta.env.DEV && import.meta.env.MODE !== 'api' && /^\/ejemplos\/?$/.test(ruta)) {
  void import('./desarrollo/Ejemplos').then(({ Ejemplos }) =>
    raiz.render(
      <StrictMode>
        <Ejemplos />
      </StrictMode>,
    ),
  )
} else {
  raiz.render(
    <StrictMode>
      <AppFamilia />
    </StrictMode>,
  )
}

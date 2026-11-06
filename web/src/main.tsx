import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { AppFamilia } from './familia/AppFamilia'
import { PaginaRelevo } from './relevo/PaginaRelevo'
import { RegionesVivas } from './compartido/ui/Anuncios'

const raiz = createRoot(document.getElementById('raiz')!)
const ruta = window.location.pathname

// /r es la página del relevo (MATU-23): no usa el marco de la familia. Todo lo demás es la app de
// la familia (MATU-39). /ejemplos solo existe en desarrollo con el doble y no entra al build.
// Las regiones vivas van antes que la app, vacías desde el primer render: por ellas se anuncian
// los avisos de las dos (compartido/ui/Anuncios).
if (/^\/r\/?$/.test(ruta)) {
  raiz.render(
    <StrictMode>
      <RegionesVivas />
      <PaginaRelevo />
    </StrictMode>,
  )
} else if (import.meta.env.DEV && import.meta.env.MODE !== 'api' && /^\/ejemplos\/?$/.test(ruta)) {
  void import('./desarrollo/Ejemplos').then(({ Ejemplos }) =>
    raiz.render(
      <StrictMode>
        <RegionesVivas />
        <Ejemplos />
      </StrictMode>,
    ),
  )
} else {
  raiz.render(
    <StrictMode>
      <RegionesVivas />
      <AppFamilia />
    </StrictMode>,
  )
}

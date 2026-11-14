import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { AppFamilia } from './familia/AppFamilia'
import { AppComercio } from './comercio/AppComercio'
import { PaginaRelevo } from './relevo/PaginaRelevo'
import { PaginaPrivacidad } from './privacidad/PaginaPrivacidad'
import { PaginaCondiciones } from './privacidad/PaginaCondiciones'
import { RegionesVivas } from './compartido/ui/Anuncios'
import { capturarRetorno } from './familia/vueltaPago'

const raiz = createRoot(document.getElementById('raiz')!)
const ruta = window.location.pathname

// /r es la página del relevo (MATU-23): no usa el marco de la familia. Todo lo demás es la app de
// la familia (MATU-39). /ejemplos solo existe en desarrollo con el doble y no entra al build.
// Las regiones vivas van antes que la app, vacías desde el primer render: por ellas se anuncian
// los avisos de las dos (compartido/ui/Anuncios).
// /privacidad es la política de privacidad, pública (MATU-75): su propia rama, sin `ProveedorFamilia`
// ni sesión, y sin leer el fragmento. No lleva el aviso de versión nueva de la app.
if (/^\/r\/?$/.test(ruta)) {
  raiz.render(
    <StrictMode>
      <RegionesVivas />
      <PaginaRelevo />
    </StrictMode>,
  )
} else if (/^\/privacidad\/?$/.test(ruta)) {
  raiz.render(
    <StrictMode>
      <RegionesVivas />
      <PaginaPrivacidad />
    </StrictMode>,
  )
} else if (/^\/condiciones-pedido\/?$/.test(ruta)) {
  // MATU-61 (9.8, O6): las condiciones del pedido, públicas, con el mismo armado de /privacidad.
  raiz.render(
    <StrictMode>
      <RegionesVivas />
      <PaginaCondiciones />
    </StrictMode>,
  )
} else if (/^\/comercio(\/|$)/.test(ruta)) {
  // MATU-63 (2.1): la consola del comercio, su propia rama, sin `ProveedorFamilia`. La parte elegida
  // vive en memoria: ninguna ruta de /comercio lleva ids ni la referencia.
  raiz.render(
    <StrictMode>
      <RegionesVivas />
      <AppComercio />
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
  // MATU-62 (7.1 y 11): si es la vuelta de Webpay, sus valores pasan a la memoria y salen de la
  // dirección con `history.replaceState` antes de dibujar nada.
  capturarRetorno()
  raiz.render(
    <StrictMode>
      <RegionesVivas />
      <AppFamilia />
    </StrictMode>,
  )
}

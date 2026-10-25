import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { ProveedorDemo } from './demo/estado'
import { ProveedorBackend } from './datos/backend'
import { Escenario } from './components/Escenario'
import { leerTokenDelFragmento, rutaDeRelevo } from './components/RelevoUrl'

// Si alguien abre directo un enlace /r#<token>, la demo parte como relevo. El estado vive en
// memoria, así que un token de otra ventana no existe aquí: verá "ya no está disponible".
const comoRelevo = rutaDeRelevo() && leerTokenDelFragmento() !== null

createRoot(document.getElementById('raiz')!).render(
  <StrictMode>
    <ProveedorBackend>
      <ProveedorDemo rol={comoRelevo ? 'relevo' : 'familia'} token={comoRelevo ? leerTokenDelFragmento() : null}>
        <Escenario />
      </ProveedorDemo>
    </ProveedorBackend>
  </StrictMode>,
)

// La política de privacidad de las pruebas (MATU-75): `GET /v1/politica` por `apiPublica`, sin red.
// Texto sintético y corto; la huella es una cualquiera de 64 hexadecimales.
import { apiPublica, type Politica } from '../src/compartido/api/politica'
import { responderCon, type RespuestaFalsa } from './apiFalsa'

export const HUELLA_DE_PRUEBA = 'a'.repeat(64)
export const HUELLA_NUEVA = 'b'.repeat(64)

export const POLITICA_DE_PRUEBA: Politica = {
  version: '0.11',
  actualizada_en: '2026-11-09',
  huella: HUELLA_DE_PRUEBA,
  texto: '## En un minuto\n\n- Un resumen de prueba.\n\n## 1. Una sección\n\nUn párrafo.\n',
  correo_contacto: 'privacidad@example.org',
}

/** `GET /v1/politica` responde en orden; la última se repite. Por omisión, 200 con la de prueba. */
export function responderPolitica(...respuestas: RespuestaFalsa[]) {
  return responderCon(apiPublica, ...(respuestas.length ? respuestas : [{ status: 200, cuerpo: POLITICA_DE_PRUEBA }]))
}

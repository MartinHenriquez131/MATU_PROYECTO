// Los textos de la política de privacidad (MATU-75), tal cual de docs/lenguaje.md, sección 29
// (aprobados por Jorge el 09-11), y el enlace de 7.5. Los usan la página /privacidad, Crear cuenta,
// las autorizaciones, «Tu cuenta» y el relevo. Lo que va entre corchetes en lenguaje.md es el enlace.

/** La página pública de la política. Sin ancla ni fragmento: nunca lleva el token del relevo. */
export const RUTA_PRIVACIDAD = '/privacidad'

export const POLITICA = {
  titulo: 'Política de privacidad', // [lenguaje 29]
  tituloDocumento: 'Política de privacidad · MATU', // [lenguaje 29]
  // [lenguaje 29] «Versión {version} · actualizada el {DD/MM/AAAA}», en partes para las cifras.
  version: 'Versión',
  actualizada: '· actualizada el',
  indice: 'Índice', // [lenguaje 29]
  volverAlIndice: 'Volver al índice', // [lenguaje 29]

  /** [lenguaje 29] «{texto} (se abre en otra pestaña)», el enlace dentro de una frase. */
  enlaceEnFrase: 'política de privacidad (se abre en otra pestaña)',
  /** [lenguaje 7.5 y 29] el enlace solo, en el relevo y en «Tu cuenta». */
  enlaceSolo: 'Política de privacidad (se abre en otra pestaña)',
  /** [lenguaje 29] «(se abre en otra pestaña)», para un enlace del texto de la política. */
  otraPestana: '(se abre en otra pestaña)',

  // [lenguaje 29] Crear cuenta: «Leí y acepto la [política de privacidad].»
  casillaAntes: 'Leí y acepto la ',
  casillaDespues: '.',
  errCasilla: 'Para crear tu cuenta, marca que leíste la política de privacidad.', // [lenguaje 29]
  cambioTitulo: 'Actualizamos la política de privacidad.', // [lenguaje 29]
  cambioTexto: 'Cambió mientras creabas tu cuenta. Léela de nuevo y vuelve a marcar la casilla.', // [lenguaje 29]

  // [lenguaje 29] Autorizaciones: «Lee la [política de privacidad] antes de autorizar.»
  autorizarAntes: 'Lee la ',
  autorizarDespues: ' antes de autorizar.',

  // «Tu cuenta»
  fila: 'Política de privacidad', // [lenguaje 29]
  // [lenguaje 29] «Aceptaste la versión {version} el {DD/MM/AAAA}.», en partes para las cifras.
  aceptasteAntes: 'Aceptaste la versión',
  aceptasteEl: 'el',
  sinRegistro: 'No tenemos registro de qué versión aceptaste.', // [lenguaje 29]
  // [lenguaje 29] «… escribe a {correo} desde el correo de tu cuenta.»; el correo es `correo_contacto`.
  comoPedirAntes: 'Para cambiar tu nombre o tu correo, pedir una copia de tus datos o eliminar tu cuenta, escribe a ',
  comoPedirDespues: ' desde el correo de tu cuenta.',
}

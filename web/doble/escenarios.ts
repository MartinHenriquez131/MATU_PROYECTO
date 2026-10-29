// Tokens de ejemplo del doble del contrato del relevo, uno por estado (especificación MATU-23,
// sección 8). Datos sintéticos: Carmen cuida a María y Rosa la reemplaza; los teléfonos usan la
// serie 5555, que no se asigna. Solo los usa el servidor de desarrollo, nunca el build.

export const PIN_DE_EJEMPLO = '4821'

export interface Escenario {
  token: string
  que: string
}

export const ESCENARIOS: Escenario[] = [
  { token: 'ejemplo-tres-campos', que: 'PIN 4821: ficha con los tres campos (Su día con horas, Si se altera corrido, A quién llamar sin completar). Cada PIN incorrecto descuenta un intento; el quinto bloquea' },
  { token: 'ejemplo-un-campo', que: 'PIN 4821: ficha con un solo campo (A quién llamar)' },
  { token: 'ejemplo-quedan-3', que: 'Cualquier PIN distinto de 4821: «Te quedan 3 intentos»' },
  { token: 'ejemplo-quedan-1', que: 'Cualquier PIN distinto de 4821: «Te queda 1 intento». 4821 abre la ficha' },
  { token: 'ejemplo-bloqueado', que: 'Presentación 423: «Este enlace se bloqueó»' },
  { token: 'ejemplo-vencido', que: 'Presentación 410 relevo-vencido' },
  { token: 'ejemplo-cortado', que: 'Presentación 410 relevo-revocado: «Este enlace se cortó»' },
  { token: 'ejemplo-no-disponible', que: 'Presentación 410 relevo-no-disponible (igual que cualquier token desconocido)' },
  { token: 'ejemplo-pausado', que: 'Presentación 410 relevo-pausado (D3): «Por ahora esta ficha no se puede ver.»' },
  { token: 'ejemplo-espera-60', que: 'Presentación 429 con Retry-After: 60 («1 minuto»)' },
  { token: 'ejemplo-espera-600', que: 'Presentación 429 con Retry-After: 600 («10 minutos»)' },
  { token: 'ejemplo-espera-sin-cabecera', que: 'Presentación 429 sin Retry-After («unos minutos»)' },
  { token: 'ejemplo-espera-canje', que: 'Presentación 200 y canje 429 con Retry-After: 600' },
  { token: 'ejemplo-error-500', que: 'Presentación 500: error general; «Volver a intentar» falla otra vez' },
  { token: 'ejemplo-error-una-vez', que: 'Presentación 500 la primera vez y 200 al volver a intentar' },
  { token: 'ejemplo-error-canje', que: 'Canje 500: mensaje de conexión bajo el PIN' },
  { token: 'ejemplo-error-ficha', que: 'Canje 204 y la primera lectura de la ficha 500: error general; al volver a intentar abre' },
  { token: 'ejemplo-sesion-cerrada', que: 'PIN 4821: la ficha abre y al «Actualizar» o recargar responde 401: «Vuelve a abrir el enlace»' },
  { token: 'ejemplo-cortado-despues', que: 'PIN 4821: la ficha abre y al «Actualizar» responde 410 relevo-revocado (la hoja se descarta)' },
  { token: 'ejemplo-bloqueado-despues', que: 'PIN 4821: la ficha abre y al «Actualizar» responde 423' },
  { token: 'ejemplo-pausado-despues', que: 'PIN 4821: la ficha abre y al «Actualizar» responde 410 relevo-pausado' },
  { token: 'ejemplo-vence-pronto', que: 'PIN 4821: la ficha vence 90 segundos después de abrirla; la página la vuelve a pedir sola y muestra «Este enlace venció»' },
  { token: 'ejemplo-actualizar-falla', que: 'PIN 4821: la ficha abre y «Actualizar» responde 503: la hoja sigue y aparece el mensaje' },
  { token: 'ejemplo-lento', que: 'Cada respuesta tarda 2 segundos: se ven «Abriendo el enlace…», «Abriendo la ficha…» y «Actualizando…»' },
  { token: 'ejemplo-textos-largos', que: 'PIN 4821: nombres largos y campos de 500 caracteres, para revisar el texto al 200%' },
]

export const SIN_FRAGMENTO = 'Abrir /r sin fragmento y sin haber entrado: GET /ficha 401, «Vuelve a abrir el enlace»'
export const TOKEN_LARGO = 'Un fragmento de más de 128 caracteres: presentación 422, «Este enlace no está disponible»'

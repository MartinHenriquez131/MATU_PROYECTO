// Cuentas de ejemplo del doble de la familia: solo datos, sin dependencias de Node, porque las
// importa también la lista de /ejemplos en el navegador. Datos sintéticos.

export const CONTRASENA_DE_EJEMPLO = 'contrasena-ejemplo' // pragma: allowlist secret

export interface CuentaDeEjemplo {
  email: string
  que: string
}

export const CUENTAS: CuentaDeEjemplo[] = [
  { email: 'carmen@ejemplo.cl', que: 'Admin con María y «Su día» escrito (1 de 3). El correo ya tiene cuenta: úsalo en Crear cuenta para ver el 409' },
  { email: 'vacia@ejemplo.cl', que: 'Admin con la ficha en 0 de 3' },
  { email: 'completa@ejemplo.cl', que: 'Ficha en 3 de 3 (un campo lo escribió Rodrigo)' },
  { email: 'dos-grupos@ejemplo.cl', que: 'Dos grupos y dos personas: selector de persona' },
  { email: 'sin-persona@ejemplo.cl', que: 'Admin con grupo y sin persona: va a «¿A quién cuidas?»' },
  { email: 'sin-persona-pagador@ejemplo.cl', que: 'Pagador con grupo y sin persona: «Todavía no hay nadie registrado…»' },
  { email: 'pagador@ejemplo.cl', que: 'Pagador sin puede_ver_plan: sin «Ficha» en la navegación; /ficha muestra «No tienes acceso»' },
  { email: 'pagador-ve@ejemplo.cl', que: 'Pagador con puede_ver_plan: ve la ficha; al guardar, 404 y «No tienes acceso»' },
  { email: 'observador@ejemplo.cl', que: 'Observador: solo Insumos; /ficha a mano no pide nada' },
  { email: 'sin-autorizacion@ejemplo.cl', que: 'La ficha responde 403 sin-consentimiento (lenguaje 6.4)' },
  { email: 'renovar-autorizacion@ejemplo.cl', que: 'La ficha responde 403 revision-vencida (lenguaje 6.4b)' },
  { email: 'revision-al-guardar@ejemplo.cl', que: 'La ficha abre y al guardar responde 403 revision-vencida: lo escrito se muestra para copiar' },
  { email: 'conflicto@ejemplo.cl', que: 'Cada primer guardado de un campo responde 412: Rodrigo lo guardó mientras escribías' },
  { email: 'defectos@ejemplo.cl', que: 'Guardar «Su día» 428, «Si se altera» 422 string_too_long, «A quién llamar» 500' },
  { email: 'vence@ejemplo.cl', que: 'El token dura 20 s y la entrada 40 s: escribe y guarda pasado ese tiempo para ver la entrada vencida con texto sin guardar' },
  { email: 'lento@ejemplo.cl', que: 'Cada respuesta tarda 2 s: «Cargando…», «Guardando…»' },
  { email: 'largos@ejemplo.cl', que: 'Nombres largos y un campo de 480 caracteres, para revisar el texto al 200%' },
  { email: 'espera@ejemplo.cl', que: 'Entrar responde 429 con Retry-After: 90 («Espera 2 minutos»)' },
  { email: 'espera-1@ejemplo.cl', que: 'Entrar responde 429 con Retry-After: 30 («Espera 1 minuto»)' },
  { email: 'caido@ejemplo.cl', que: 'Entrar responde 503' },
  // MATU-57: recuperar el acceso y confirmar el celular. Los códigos solo se ven en la consola del doble.
  { email: 'celular-verificado@ejemplo.cl', que: 'Celular confirmado: «Tu cuenta» dice «Confirmado»; recuperar envía el código «al celular»' },
  { email: 'celular-sin-verificar@ejemplo.cl', que: 'Celular sin confirmar: «Tu cuenta» ofrece «Confirmar celular» (SMS o WhatsApp)' },
  { email: 'celular-espera@ejemplo.cl', que: 'Pedir el código del celular responde 429 con Retry-After: 120' },
  { email: 'sin-celular@ejemplo.cl', que: 'Cuenta anterior a MATU-39, sin celular: «Tu cuenta» lo dice' },
  { email: 'recuperar-espera@ejemplo.cl', que: 'Cambiar la contraseña con el código responde 429 con Retry-After: 120' },
  { email: 'codigo-invalido@ejemplo.cl', que: 'Cambiar la contraseña responde siempre 422 codigo-invalido' },
]

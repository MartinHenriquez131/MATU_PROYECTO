// Textos de MATU-55, «Dónde entraste» y los avisos de «Tu cuenta» (especificación
// docs/diseno/matu-55-donde-entraste.md v1.1). Las marcas siguen a la especificación: [lenguaje 13.3]
// y las demás ya están aprobadas; [analista] los propuso la revisión previa; [nuevo] no está en
// ninguna parte todavía; [ajuste] cambia un texto aprobado. El orquestador los lleva a lenguaje.md.
// Nunca se dice «sesión», «dispositivo», «evento», «registro», «auditoría», «IP» ni «token», salvo la
// IP de la bajada, que dice que no se guarda.
import type { ClaseDispositivo, TipoEventoCuenta } from '../compartido/api/familia'

/** E1: el sustantivo según `clase`. `otro` (iPad, «Navegador web») es «navegador». */
export const sustantivo = (clase: ClaseDispositivo | null | undefined) => (clase === 'telefono' ? 'teléfono' : clase === 'computador' ? 'computador' : 'navegador')

export const DONDE = {
  titulo: 'Dónde entraste', // [lenguaje 13.3]
  bajada: 'Los teléfonos y computadores donde entraste a MATU. No guardamos tu ubicación ni tu dirección IP.', // [especificación 2.2]
  tusDispositivos: 'Tus teléfonos y computadores', // [especificación 2.2]
  /** «Este teléfono» [lenguaje 13.3]; «Este computador» y «Este navegador» [nuevo]. */
  este: (clase: ClaseDispositivo | null | undefined) => `Este ${sustantivo(clase)}`,
  /** «Última vez: {fecha} a las {hora}» [lenguaje 13.3]; «hoy» y «ayer» [ajuste]. */
  ultimaVez: 'Última vez:',
  hoy: 'hoy',
  ayer: 'ayer',
  aLas: 'a las',
  /** «Cerrar en ese teléfono» [lenguaje 13.3]; computador y navegador [nuevo]. */
  cerrarEnEse: (clase: ClaseDispositivo | null | undefined) => `Cerrar en ese ${sustantivo(clase)}`,

  ultimos: 'Últimos ingresos', // [especificación 2.2]
  ultimosBajada: 'Los de los últimos 90 días, hasta 20.', // [ajuste] del texto del analista, con «hasta 20»
  /** Con `dispositivo: null`, en lugar del nombre [nuevo]. */
  yaNoEnLista: 'un teléfono o computador que ya no está en tu lista',
  /** «(este teléfono)» [analista]; «(este computador)» y «(este navegador)» [nuevo]. */
  esteEntreParentesis: (clase: ClaseDispositivo | null | undefined) => `(este ${sustantivo(clase)})`,
  codigoNoCompartas: 'Si no lo pediste tú, no compartas el código con nadie.', // [nuevo] [analista-cierre]
  /** [ajuste] del texto del analista (E5): el camino real para cambiar la contraseña. */
  noReconoces: (clase: ClaseDispositivo | null | undefined) =>
    `¿No reconoces un ingreso? Cierra MATU en ese ${sustantivo(clase)}. Para cambiar tu contraseña, sal de MATU y toca «¿Olvidaste tu contraseña?» al entrar.`,
  /** Lo que no se muestra, según `hay_mas`, antes y después del correo [nuevo]. */
  anterioresSinMas: ['Si necesitas los ingresos anteriores a 90 días, escribe a ', ' desde el correo de tu cuenta.'] as const,
  anterioresConMas: ['Mostramos los 20 más recientes. Para ver los demás, o los anteriores a 90 días, escribe a ', ' desde el correo de tu cuenta.'] as const,
  conMasSinCorreo: 'Mostramos los 20 más recientes.', // [nuevo]
  vacio: 'No hay ingresos en los últimos 90 días.', // [analista]
  errDispositivos: 'No pudimos traer dónde entraste. Revisa tu conexión e inténtalo de nuevo.', // [analista]
  errIngresos: 'No pudimos traer tus últimos ingresos. Revisa tu conexión e inténtalo de nuevo.', // [nuevo]

  // 2.6, el diálogo (D8): sin contraseña y con una sola confirmación.
  dialogoTitulo: (nombre: string) => `¿Cerrar MATU en ${nombre}?`, // [analista]
  dialogoTexto: 'Quien lo use tendrá que volver a entrar con tu correo y tu contraseña. Puede seguir abierto hasta 15 minutos.', // [analista]
  cerrando: 'Cerrando…', // [nuevo]
  dejarloAbierto: 'Dejarlo abierto', // [analista]
  errCerrar: (clase: ClaseDispositivo | null | undefined) => `No pudimos cerrar MATU en ese ${sustantivo(clase)}. Revisa tu conexión y vuelve a intentarlo.`, // [nuevo]
  cerramos: (nombre: string) => `Cerramos MATU en ${nombre}.`, // [analista]
  /** «Ese teléfono ya no estaba en tu lista.» [analista]; computador y navegador [nuevo]. */
  yaNoEstaba: (clase: ClaseDispositivo | null | undefined) => `Ese ${sustantivo(clase)} ya no estaba en tu lista.`,
}

/**
 * 2.5: la frase de cada tipo. `nombre` ya viene resuelto (el del dispositivo o «un teléfono o
 * computador que ya no está en tu lista»). Un tipo que no está aquí no se muestra.
 */
export const FRASE_INGRESO: Record<TipoEventoCuenta, (nombre: string) => string> = {
  entraste: () => 'Entraste', // [analista]
  saliste: () => 'Saliste', // [analista]
  cerraste_en_dispositivo: (n) => `Cerraste MATU en ${n}`, // [analista]
  salida_por_seguridad: (n) => `Te sacamos de MATU en ${n} porque notamos un uso extraño.`, // [ajuste], sin «Vuelve a entrar.»
  contrasena_cambiada: () => 'Cambiaste tu contraseña', // [analista]
  celular_confirmado: () => 'Confirmaste tu celular', // [analista]
  codigo_recuperacion_pedido: () => 'Se pidió un código para recuperar tu cuenta', // [analista]
  avisos_activados: (n) => `Activaste los avisos en ${n}`, // [analista]
  avisos_desactivados: (n) => `Desactivaste los avisos en ${n}`, // [analista]
  avisos_cambiados: () => 'Cambiaste tus avisos', // [analista]
  pediste_una_copia: () => 'Pediste una copia de tus datos', // [nuevo] MATU-54, 5.5
}

/** 3.5: la entrada a «Dónde entraste» dentro de «Tu cuenta». */
export const ENTRADA_DONDE = {
  titulo: 'Dónde entraste', // [lenguaje 13.3]
  bajada: 'Los teléfonos y computadores donde entraste, y tus últimos ingresos.', // [nuevo]
  ver: 'Ver dónde entraste', // [nuevo]
}

/** 3.3: las preferencias (D5). */
export const AVISOS = {
  leyenda: 'Avisos cuando un insumo se está acabando', // [lenguaje 20]
  ayuda: 'Te avisamos cuando un insumo se esté acabando. El aviso no dice cuál ni de quién.', // [analista]
  alcance: 'Vale para todos tus grupos.', // [analista, D5]
  correo: 'Por correo', // [lenguaje 20]
  push: 'En tus teléfonos', // [ajuste de lenguaje 20, D5]
  guardando: 'Guardando…', // [lenguaje 17]
  guardado: 'Guardamos tus avisos.', // [analista]
  errGuardar: 'No pudimos guardar. Revisa tu conexión y vuelve a intentarlo.', // [lenguaje 17]
  piloto: 'En el piloto los avisos se prueban sin enviarse: no te llegará nada.', // [analista]
  errCargar: 'No pudimos traer tus avisos. Revisa tu conexión e inténtalo de nuevo.', // [nuevo]
}

/** 3.4: «Este teléfono», recibir avisos aquí (D6). `s` es el sustantivo de E1. */
export const PUSH = {
  errCargar: (s: string) => `No pudimos ver los avisos de este ${s}. Revisa tu conexión e inténtalo de nuevo.`, // [nuevo]
  activados: 'Activados', // [nuevo]
  sinActivar: 'Sin activar', // [nuevo]
  desactivar: (s: string) => `Desactivar en este ${s}`, // [nuevo]
  activar: (s: string) => `Activar en este ${s}`, // [nuevo]
  /** [lenguaje 33, PR MATU #81] La misma línea de la política 0.14. */
  ayudaActivar:
    'Al activarlos, tu navegador anota una dirección de avisos en el servicio de su fabricante, y MATU la guarda hasta que los desactives o salgas. En el piloto, MATU no le envía nada a ese servicio.',
  bloqueado: 'Tu navegador no deja que MATU te avise. Puedes cambiarlo en los ajustes del navegador.', // [analista]
  sinSoporte: 'Este navegador no puede recibir avisos.', // [analista]
  porCorreo: 'Puedes recibirlos por correo.', // [nuevo]
  sinClave: (s: string) => `Por ahora no se pueden activar los avisos en este ${s}. Puedes recibirlos por correo.`, // [nuevo]
  iosTitulo: 'En iPhone, primero agrega MATU a tu pantalla de inicio.', // [nuevo]
  iosPaso1: ['Toca Compartir', 'en Safari.'] as const, // [nuevo], con el ícono Share entre las dos partes
  iosCompartir: 'Compartir',
  iosPaso2: 'Elige «Agregar a inicio».', // [nuevo]
  iosPaso3: 'Abre MATU desde su ícono y vuelve a Tu cuenta.', // [nuevo]
  activando: 'Activando…', // [nuevo]
  activaste: (s: string) => `Activaste los avisos en este ${s}.`, // [nuevo]
  noActivamos: 'No activamos los avisos. Puedes volver a intentarlo.', // [nuevo]
  errActivar: 'No pudimos activar los avisos. Revisa tu conexión y vuelve a intentarlo.', // [nuevo]
  desactivando: 'Desactivando…', // [nuevo]
  desactivaste: (s: string) => `Desactivaste los avisos en este ${s}.`, // [nuevo]
  errDesactivar: 'No pudimos desactivar los avisos. Revisa tu conexión y vuelve a intentarlo.', // [nuevo]
  /** [lenguaje 33, G; analista, C14] MATU-107: la cuenta no está en el equipo del piloto (`permitido: false`). Igual en un computador. */
  noPermitido: 'En el piloto, los avisos en el teléfono solo se prueban en los teléfonos del equipo de MATU.',
}

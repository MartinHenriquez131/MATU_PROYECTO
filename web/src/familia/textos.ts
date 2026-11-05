// Todos los textos de la app de la familia (especificación MATU-39, versión 1.1). Las marcas dicen
// de dónde sale cada uno:
//   [lenguaje X]   docs/lenguaje.md, sección X, tal cual
//   [demo]         la demo aprobada, con "email" cambiado a "correo" (D1)
//   [PROPUESTO]    de la especificación, pendiente de entrar a lenguaje.md (sección 8)
//   [INSTRUCCIÓN]  dictado por decisión de Jorge del 02-11, pendiente de lenguaje.md
//   [aprobado por Jorge el 03-11]  textos de MATU-57, pendientes de lenguaje.md
// Nunca se muestra `title`, `detail` ni `mensaje` de la API.

export const GENERAL = {
  /** [lenguaje 8] Cualquier otro, o sin respuesta. */
  error: 'No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo. Lo que escribiste sigue aquí.',
  /** [lenguaje 8] sin la última frase, al cargar (5.2). */
  errorAlCargar: 'No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo.',
  volverAIntentar: 'Volver a intentar', // [PROPUESTO]
  cargando: 'Cargando…', // [PROPUESTO]
  abriendo: 'Abriendo MATU…', // [PROPUESTO]
  /** [lenguaje 8] 404 de la familia. */
  noEncontrado: 'No encontramos lo que buscas. Puede que ya no tengas acceso. Vuelve al inicio.',
}

export const MARCO = {
  saltar: 'Saltar al contenido',
  cuidasA: 'Cuidas a', // [demo]
  salir: 'Salir',
  secciones: 'Secciones',
  leDicen: (pila: string) => `Le dicen ${pila}`, // [PROPUESTO]
  cambiar: (nombre: string) => `${nombre}. Cambiar de persona`,
}

export const PASOS = ['Tu cuenta', 'Tu grupo', 'A quién cuidas', 'La autorización'] // [PROPUESTO]
export const pasoDe = (n: number) => `Paso ${n} de 4` // [PROPUESTO]
export const FRASE = 'Que el cuidado no dependa de una sola persona.' // [demo]

export const CUENTA = {
  titulo: 'Crea tu cuenta', // [demo]
  bajada: 'Para empezar te pedimos solo esto.', // [demo]
  nombre: 'Tu nombre', // [demo]
  nombreAyuda: 'Así te verán en tu grupo.', // [PROPUESTO]
  correo: 'Tu correo', // [PROPUESTO]
  celular: 'Tu celular', // [PROPUESTO]
  celularAyuda: 'Para ayudarte a recuperar tu cuenta si olvidas la contraseña.', // [PROPUESTO]
  celularEjemplo: '+56 9',
  contrasena: 'Una contraseña', // [demo] // pragma: allowlist secret
  contrasenaAyuda: 'Al menos 10 caracteres.', // [demo] // pragma: allowlist secret
  mostrar: 'Mostrar', // [PROPUESTO]
  ocultar: 'Ocultar', // [PROPUESTO]
  boton: 'Crear cuenta',
  enviando: 'Creando la cuenta…', // [demo]
  creada: 'Cuenta creada.', // [demo]
  yaTienes: '¿Ya tienes cuenta?',
  irAEntrar: 'Entrar',
  errNombre: 'Escribe tu nombre.', // [PROPUESTO]
  errCorreo: 'Revisa tu correo.', // [PROPUESTO]
  /** [lenguaje 13.3] 422 `email` con `tipo: dominio_no_permitido`, solo en staging (decisión 105). */
  errDominio: 'En este ambiente de prueba usa un correo terminado en @example.com.',
  errCelular: 'Escribe un celular de Chile, por ejemplo +56 9 5555 0137.', // [lenguaje 8]
  errContrasenaCorta: 'La contraseña necesita al menos 10 caracteres.', // [demo] // pragma: allowlist secret
  // 422 de la API, por `errores[].campo`
  err422Nombre: 'Escribe tu nombre, de hasta 100 letras.', // [PROPUESTO]
  err422Contrasena: 'La contraseña necesita entre 10 y 128 caracteres.', // [PROPUESTO] // pragma: allowlist secret
  registradoTitulo: 'Ese correo ya tiene una cuenta', // [demo]
  registradoTexto: 'Entra con tu contraseña, o usa otro correo.', // [demo]
  registradoBoton: 'Entrar con ese correo', // [demo]
}

/**
 * [lenguaje 13.3] 429 del límite por IP de MATU-25 (`/errores/demasiadas-peticiones`), al crear la
 * cuenta. Los minutos salen de `Retry-After` (`esperaDe`, compartido/api/cliente.ts).
 */
export const ESPERA_CONEXION = {
  titulo: 'Espera un momento',
  texto: (minutos: number) => `Hubo muchos intentos desde esta conexión. Vuelve a intentarlo en ${minutos === 1 ? '1 minuto' : `${minutos} minutos`}.`,
}

export const ENTRAR = {
  titulo: 'Entrar',
  correo: 'Tu correo',
  contrasena: 'Tu contraseña', // pragma: allowlist secret
  boton: 'Entrar',
  enviando: 'Entrando…',
  faltan: 'Escribe tu correo y tu contraseña.', // [PROPUESTO]
  noTienes: '¿No tienes cuenta?',
  irACrear: 'Crear cuenta',
  vencida: 'Hace tiempo que no entrabas. Vuelve a entrar con tu correo y tu contraseña.', // [INSTRUCCIÓN]
  salio: 'Saliste de MATU. Para volver, entra con tu correo y tu contraseña.', // [PROPUESTO]
  credenciales: 'El correo o la contraseña no coinciden. Revísalos y vuelve a intentarlo.', // [PROPUESTO]
  /** [aprobado por Jorge el 03-11] MATU-57 (especificación 4): reemplaza el de lenguaje 13.3; sigue el enlace a recuperar. */
  espera: (minutos: number) => `Hubo varios intentos de entrar. ${minutos === 1 ? 'Espera 1 minuto.' : `Espera ${minutos} minutos.`}`,
  esperaRecuperar: 'Recupera tu cuenta', // [aprobado por Jorge el 03-11] MATU-57 // pragma: allowlist secret
  olvidaste: '¿Olvidaste tu contraseña?', // [aprobado por Jorge el 03-11] MATU-57 // pragma: allowlist secret
  /** [aprobado por Jorge el 03-11, D2] Tras cambiar la contraseña con el código. */
  claveCambiada: 'Listo. Cambiamos tu contraseña. Por seguridad, tendrás que volver a entrar en tus otros teléfonos y computadores.', // pragma: allowlist secret
  noDisponible: 'MATU no está disponible en este momento. Vuelve a intentarlo en unos minutos.', // [PROPUESTO]
}

export const GRUPO = {
  titulo: 'Ponle nombre a tu grupo', // [PROPUESTO]
  bajada: 'Es el grupo de las personas que cuidan contigo.', // [PROPUESTO]
  campo: 'Nombre del grupo', // [PROPUESTO]
  /** Política de privacidad, sección 2, tal cual. */
  ayuda: 'Usa un nombre corto, como «Familia Soto». No incluyas el nombre completo de la persona que cuidas ni datos de salud.',
  boton: 'Crear el grupo', // [PROPUESTO]
  enviando: 'Creando el grupo…', // [PROPUESTO]
  errVacio: 'Escribe un nombre para el grupo.', // [PROPUESTO]
}

export const PERSONA = {
  titulo: '¿A quién cuidas?',
  nombre: '¿Cómo se llama?', // [demo]
  pila: '¿Cómo le dicen?', // [demo]
  pilaAyuda: 'Es el nombre que verá quien te reemplace.', // [demo]
  apoyo: '¿Cuánto apoyo necesita en el día a día?', // [demo]
  direccion: '¿Dónde vive? Puedes dejarlo para después', // [demo]
  direccionAyuda: 'La pedimos recién con el primer pedido. La ficha no la usa.', // [demo]
  calle: 'Calle',
  numero: 'Número',
  comuna: 'Comuna',
  depto: 'Depto (si tiene)', // [PROPUESTO]
  sinDiagnostico: 'No te preguntamos qué enfermedad tiene. No lo necesitamos y no lo guardamos.', // [demo]
  boton: 'Continuar',
  errNombres: 'Escribe su nombre y cómo le dicen para seguir.', // [demo]
  errDireccion: 'Completa calle, número y comuna, o deja los tres vacíos.', // [demo]
  errApoyo: 'Elige cuánto apoyo necesita.', // [PROPUESTO]
}

export const AUTORIZACION = {
  titulo: 'La autorización para guardar su ficha', // [PROPUESTO]
  bajada: (pila: string) =>
    `Lo que anotes sobre el cuidado de ${pila} es información sensible. Para guardarla necesitamos saber en qué calidad das la autorización.`, // [PROPUESTO]
  leyenda: 'Doy esta autorización porque…', // [PROPUESTO]
  referencia: 'Referencia del documento', // [demo]
  referenciaAyuda: 'Por ejemplo: resolución y fecha', // [demo]
  leido: 'Leí el aviso y lo acepto', // [demo]
  declaras: 'Lo que declaras', // [demo]
  boton: (pila: string) => `Acepto y registro a ${pila}`, // [PROPUESTO]
  enviando: (pila: string) => `Registrando a ${pila}…`, // [PROPUESTO]
  registrada: (pila: string) => `Listo. Ahora, la ficha de ${pila}.`, // [PROPUESTO, preferida]
  volverACorregir: (pila: string) => `Volver a corregir los datos de ${pila}`, // [PROPUESTO]
  volver: 'Volver a ¿A quién cuidas?',
  errCalidad: 'Elige en qué calidad das la autorización.', // [PROPUESTO]
  errReferencia: 'Escribe la referencia del documento que te nombra representante.', // [demo]
  errLeido: 'Marca que leíste el aviso para seguir.', // [demo]
}

export const FICHA = {
  titulo: 'Ficha de relevo', // [lenguaje 5.4]
  // Aprobado por Jorge el 03-11 (MATU-49 10.3): con ADR-028 los tres campos se comparten siempre.
  bajada: 'Tres campos cortos para que quien te reemplace sepa qué hacer. Cada campo se guarda por separado.',
  avance: (n: number) => `${n} de 3 campos listos`,
  /** Lo que va después del número, que lleva `cifras` aparte. */
  avanceResto: 'de 3 campos listos',
  listo: 'Listo',
  falta: 'Falta',
  completar: (c: string) => `Completar «${c}»`,
  editar: (c: string) => `Editar «${c}»`,
  loEscribio: (autor: string) => `Lo escribió ${autor}:`,
  cifrado: 'Cada campo se guarda cifrado, por separado.', // [lenguaje 5.4, desde MATU-11]
  vistaPrevia: 'Así la ve quien te reemplaza',
  mientrasEscribes: 'La hoja, mientras escribes',
  hojaDe: (pila: string) => `Ficha de ${pila}`,
  sinCompletar: 'Sin completar',
  campoN: (n: number) => `Campo ${n} de 3`,
  contador: (n: number) => `${n} de 500 caracteres`,
  guardar: 'Guardar',
  guardando: 'Guardando…',
  seguirDespues: 'Seguir después',
  volverALaFicha: 'Volver a la ficha', // aprobado por Jorge el 03-11
  // Dictado (3.7.1)
  dictar: 'Dictar en vez de escribir', // [lenguaje 5.4]
  escuchando: 'Escuchando…', // [lenguaje 5.4]
  detener: 'Detener', // [PROPUESTO]
  sinMicrofono: 'No pudimos usar el micrófono. Puedes escribir el texto.', // [PROPUESTO]
  // Salir sin guardar (3.7)
  sinGuardar: (c: string) => `Lo que escribiste en «${c}» no se guardó. ¿Salir igual?`, // [PROPUESTO]
  salirSinGuardar: 'Salir sin guardar', // [PROPUESTO]
  seguirEscribiendo: 'Seguir escribiendo', // [PROPUESTO]
  // Guardado [lenguaje 6.1]
  guardado: (c: string) => `«${c}» guardado`,
  vasEn: (n: number) => `Vas en ${n} de 3. Puedes seguir cuando quieras, no se pierde nada.`,
  completa: 'La ficha está completa.',
  seguirCon: (c: string) => `Seguir con «${c}»`,
  verLosCampos: 'Ver los campos',
  // 428 [lenguaje 6.3]
  faltaVersionTitulo: 'No pudimos guardar este campo.',
  faltaVersion: 'Vuelve a abrirlo y guarda de nuevo. Lo que escribiste sigue aquí.',
  // 422 [lenguaje 6.5]
  muyLargo: 'Cada campo admite hasta 500 caracteres. Acorta un poco el texto para guardarlo.',
  // 403 [lenguaje 6.4 y 6.4b]
  sinConsentimientoTitulo: (pila: string) => `Falta la autorización para usar la ficha de ${pila}.`,
  sinConsentimiento: 'Sin ella no podemos guardar ni mostrar la ficha. Pídele a quien administra el grupo que la registre.',
  revisionTitulo: (pila: string) => `Hay que renovar la autorización de la ficha de ${pila}.`,
  revision: 'Se renueva una vez al año. Mientras tanto, la ficha no se puede ver ni cambiar, pero lo que escribiste sigue guardado.',
  revisionPide: 'Pídele a quien administra el grupo que la renueve.',
  chileAtiende: 'Apoyos del Estado para quienes cuidan',
  chileAtiendeNota: '(se abre en ChileAtiende)',
  chileAtiendeUrl: 'https://www.chileatiende.gob.cl/fichas/112779-persona-cuidadora',
  loEscrito: 'Lo que escribiste sigue aquí. Cópialo si lo quieres guardar en otra parte.', // [PROPUESTO]
  // 5.7
  vencidaConTexto: 'Tienes que volver a entrar. Copia lo que escribiste antes de seguir: no se guardó.', // [PROPUESTO]
}

/** Secciones complementarias (MATU-50). [lenguaje 14.2 y 14.3], aprobados por Jorge el 03-11. */
export const MAS = {
  titulo: (pila: string) => `Más sobre ${pila}`,
  bajada: (pila: string) => `Si quieres, cuenta más para que quien te reemplace conozca a ${pila}. Agrega solo lo que te sirva, cuando tengas tiempo.`,
  agregadas: (n: number) => (n === 1 ? 'Agregaste 1 sección.' : `Agregaste ${n} secciones.`),
  puedesAgregar: 'Puedes agregar',
  agregar: (t: string) => `Agregar «${t}»`,
  editar: (t: string) => `Editar «${t}»`,
  vistaPrevia: 'Cada relevo ve solo las secciones que eliges al compartir.',
  // Editor
  ayuda: 'No hace falta escribir diagnósticos ni enfermedades. Escribe lo que ayuda a cuidar.',
  alergias: 'Si tiene alergia a algún remedio o alimento, anótalo aquí.',
  ejemplo: (e: string) => `Por ejemplo: «${e}»`,
  contador: (n: number, tope: number) => `${n} de ${tope} caracteres`,
  // Guardado (4.4)
  agregaste: (t: string) => `Agregaste «${t}».`,
  guardamos: (t: string) => `Guardamos «${t}».`,
  conEnlaces: 'Quien ya tiene un enlace no la verá. Para que la vea, crea un enlace nuevo.',
  // Quitar (4.5 y 4.6)
  quitar: (t: string) => `Quitar «${t}»`,
  quitarPregunta: (t: string) => `¿Quitar «${t}»?`,
  quitarTexto: 'Se borra lo que escribiste en esta sección. Quien tenga un enlace dejará de verla. No se puede deshacer.',
  quitarYBorrar: 'Quitar y borrar',
  dejarla: 'Dejarla como está',
  quitando: 'Quitando…',
  quitaste: (t: string) => `Quitaste «${t}».`,
  yaNoEstaba: (t: string) => `«${t}» ya no estaba en la ficha.`,
  conflictoQuitar: (autor: string, t: string) => `${autor} cambió «${t}» mientras la ibas a quitar`,
  versionDe: (autor: string) => `Esta es la versión que guardó ${autor}:`,
  quitarlaIgual: 'Quitarla igual',
  // Aprobados por Jorge el 03-11 (MATU-49 10.3)
  dejasteComoLaGuardo: (t: string, autor: string) => `Dejaste «${t}» como la guardó ${autor}.`,
  /** 4.7: el 422 de largo. Partido para poner el tope en `cifras`. */
  muyLargo: ['Esta sección admite hasta ', ' caracteres. Acorta un poco el texto para guardarlo.'] as const,
  // 4.6: guardar cuando otra persona la quitó (412 con `actual: null`)
  quitadaTitulo: (t: string) => `Otra persona quitó «${t}» mientras escribías`,
  quitadaTexto: 'Lo que escribiste no se guardó. Puedes agregarla de nuevo con tu texto.',
  agregarlaDeNuevo: 'Agregarla de nuevo',
  dejarlaQuitada: 'Dejarla quitada',
  quitadaPie: 'Si quieres, copia lo que escribiste antes de elegir.',
  dejasteQuitada: (t: string) => `Dejaste «${t}» quitada.`,
}

/** El paso de compartir (MATU-48), para el selector de secciones. [lenguaje 14.2 y 14.3] */
export const COMPARTIR_SECCIONES = {
  siempreVe: 'Siempre ve',
  base: 'Su día, Si se altera y A quién llamar.',
  queMas: '¿Qué más puede ver?',
  elige: 'Elige las secciones que le sirven.',
  incluirRemedios: 'Incluir Sus remedios',
  ayudaRemedios: 'Quien te reemplaza verá qué remedios toma y a qué hora. Márcalo solo si va a dárselos o a estar a cargo de ellos.',
  /** Partido en tres para poner la fecha en `cifras` y en negrita. */
  confirmacion: (nombre: string) => [`Vas a compartir sus remedios con ${nombre} hasta el `, '. Puedes cortar el acceso cuando quieras.'] as const,
  si: 'Sí, crear el enlace',
  no: 'No incluir sus remedios',
  /** PIN y Enlaces: «Ve su día, si se altera, a quién llamar, quién es y sus remedios.» */
  loQueVe: (titulos: string[]) => {
    const todo = ['su día', 'si se altera', 'a quién llamar', ...titulos.map((t) => t.toLowerCase())]
    return `Ve ${todo.slice(0, -1).join(', ')} y ${todo[todo.length - 1]}.`
  },
  despues: (nombre: string) => `Si agregas una sección después, ${nombre} no la verá. Para que la vea, crea un enlace nuevo.`,
}

export const CONFLICTO = {
  // [lenguaje 6.2]
  titulo: (autor: string, campo: string) => `${autor} guardó «${campo}» mientras escribías`,
  explicacion: 'No guardamos lo tuyo encima de lo suyo. Elige qué versión dejar: la otra se descarta.',
  laDe: (autor: string) => `La de ${autor}`,
  guardadaA: 'Guardada a las',
  laTuya: 'La tuya',
  laTuyaDetalle: 'Lo que escribiste recién, sin guardar',
  vacia: 'Vacía',
  dejarLaDe: (autor: string) => `Dejar la de ${autor}`,
  dejarLaMia: 'Dejar la mía',
  nota: 'MATU no mezcla los textos solo. Si quieres, copia una parte antes de elegir.',
  dejasteTuya: 'Dejaste tu versión.',
  dejasteSuya: (autor: string) => `Dejaste la versión de ${autor}.`,
  otraPersona: 'Otra persona',
}

export const ESTADOS = {
  // 5.4 [PROPUESTO]
  sinPersona: (grupo: string) =>
    `Todavía no hay nadie registrado en ${grupo}. Quien administra el grupo puede registrar a la persona que cuidan.`,
  // 5.5 [PROPUESTO]
  compartirTitulo: 'Compartir',
  compartirPronto: 'Pronto vas a poder compartir la ficha con quien te reemplace desde aquí.',
  // 5.6 [PROPUESTO]
  sinAcceso: (nombre: string) => `No tienes acceso a la ficha de ${nombre}. Si la necesitas, pídeselo a quien administra el grupo.`,
  insumosTitulo: 'Insumos',
}

// ---------------------------------------------------------------- MATU-57
// Especificación docs/diseno/matu-57-recuperar-acceso.md. Siempre «correo», nunca «email» (D1), y
// nunca «sesión» (D2). Ningún texto dice a qué canal fue el código.

export const RECUPERAR = {
  volver: 'Volver a entrar', // [aprobado por Jorge el 03-11]
  titulo: 'Recupera tu cuenta', // [aprobado por Jorge el 03-11]
  bajada: 'Escribe tu correo y te enviaremos un código para crear una contraseña nueva.', // [aprobado por Jorge el 03-11] // pragma: allowlist secret
  correo: 'Tu correo',
  boton: 'Enviar código', // [aprobado por Jorge el 03-11]
  enviando: 'Enviando…', // [aprobado por Jorge el 03-11]
  errCorreo: 'Revisa tu correo.', // [MATU-39]
  /** [aprobado por Jorge el 03-11], con «correo» (D1). */
  enviado: 'Si hay una cuenta con ese correo, te enviamos un código. Puede tardar un minuto.',
  // Pantalla del código
  volverCodigo: 'Volver', // [aprobado por Jorge el 03-11]
  tituloCodigo: 'Escribe el código', // [aprobado por Jorge el 03-11]
  bajadaCodigo: 'Te lo enviamos por mensaje al celular o al correo. Tiene 6 números.', // [aprobado por Jorge el 03-11]
  codigo: 'Código', // [aprobado por Jorge el 03-11]
  nueva: 'Nueva contraseña', // [aprobado por Jorge el 03-11] // pragma: allowlist secret
  nuevaAyuda: 'Al menos 10 caracteres.', // [MATU-39]
  botonCambiar: 'Cambiar contraseña', // [aprobado por Jorge el 03-11] // pragma: allowlist secret
  cambiando: 'Cambiando…', // [aprobado por Jorge el 03-11]
  noLlego: '¿No te llegó?', // [aprobado por Jorge el 03-11]
  reenviar: 'Pide que te lo enviemos a tu correo', // [aprobado por Jorge el 03-11]
  // Sin «El código anterior ya no sirve»: dentro de 60 s la API no envía otro (decisión 84) y el anterior sigue sirviendo.
  reenviado: 'Si hay una cuenta con ese correo, te enviamos un código nuevo al correo. Puede tardar un minuto.', // [aprobado por Jorge el 03-11]
  enUnMinuto: 'Puedes pedir otro en un minuto.', // [aprobado por Jorge el 03-11] especificación 6.6
  errCodigoCorto: 'El código tiene 6 números.', // [aprobado por Jorge el 03-11]
  errCodigo: 'El código no es correcto o ya venció. Pide uno nuevo.', // [aprobado por Jorge el 03-11]
  errClaveCorta: 'La contraseña necesita al menos 10 caracteres.', // [MATU-39] // pragma: allowlist secret
  errClave422: 'La contraseña necesita entre 10 y 128 caracteres.', // [MATU-39] // pragma: allowlist secret
  /** [aprobado por Jorge el 03-11] 429 al probar el código. */
  esperaCodigo: (minutos: number) => `Hubo varios intentos con ese código. Pide uno nuevo en ${minutos === 1 ? '1 minuto' : `${minutos} minutos`}.`,
}

export const CUENTA_PROPIA = {
  menu: 'Tu cuenta', // [aprobado por Jorge el 03-11] D5
  titulo: 'Tu cuenta', // [aprobado por Jorge el 03-11] D5
  bajada: 'Tus datos para entrar a MATU.', // [aprobado por Jorge el 03-11]
  correo: 'Tu correo',
  celular: 'Tu celular', // [aprobado por Jorge el 03-11]
  confirmado: 'Confirmado', // [aprobado por Jorge el 03-11]
  sinConfirmar: 'Sin confirmar', // [aprobado por Jorge el 03-11]
  sinCelular: 'Tu cuenta todavía no tiene un celular.', // [aprobado por Jorge el 03-11]
  confirmar: 'Confirmar celular', // [aprobado por Jorge el 03-11]
  volver: 'Volver a tu cuenta', // [aprobado por Jorge el 03-11]
}

export const CELULAR = {
  titulo: 'Confirma tu celular', // [aprobado por Jorge el 03-11]
  explicacion: 'Si algún día olvidas la contraseña, te enviaremos un código a este número para que puedas volver a entrar.', // [aprobado por Jorge el 03-11] // pragma: allowlist secret
  tuCelular: 'Tu celular', // [aprobado por Jorge el 03-11]
  /** SMS o WhatsApp se elige una vez, al confirmar (decisión de Jorge del 03-11). */
  canal: '¿Cómo prefieres recibir los códigos?', // [aprobado por Jorge el 03-11]
  sms: 'Mensaje de texto (SMS)', // [aprobado por Jorge el 03-11]
  whatsapp: 'WhatsApp', // [aprobado por Jorge el 03-11]
  enviar: 'Enviar código', // [aprobado por Jorge el 03-11]
  enviando: 'Enviando…', // [aprobado por Jorge el 03-11]
  ahoraNo: 'Ahora no', // [aprobado por Jorge el 03-11] D4
  enviado: 'Te enviamos un código al ', // [aprobado por Jorge el 03-11]
  confirmar: 'Confirmar', // [aprobado por Jorge el 03-11]
  confirmando: 'Confirmando…', // [aprobado por Jorge el 03-11]
  otro: '¿No te llegó? Enviar otro código', // [aprobado por Jorge el 03-11]
  enUnMinuto: 'Puedes pedir otro en un minuto.', // [aprobado por Jorge el 03-11]
  listo: 'Listo. Tu celular quedó confirmado.', // [aprobado por Jorge el 03-11]
  irAFicha: 'Ir a la ficha', // [aprobado por Jorge el 03-11]
  errCodigo: 'El código no es correcto o ya venció. Pide uno nuevo.', // [aprobado por Jorge el 03-11]
  errCodigoCorto: 'El código tiene 6 números.', // [aprobado por Jorge el 03-11]
  /** [aprobado por Jorge el 03-11] */
  espera: (minutos: number) => `Ya pediste varios códigos. Espera ${minutos === 1 ? '1 minuto' : `${minutos} minutos`} y vuelve a intentarlo.`,
  noEnvio: 'No pudimos enviar el mensaje ahora. Vuelve a intentarlo en unos minutos.', // [aprobado por Jorge el 03-11]
}

/** Quién la vio (MATU-45, especificación docs/diseno/matu-45-aperturas.md). */
export const QUIEN = {
  titulo: 'Quién la vio', // [lenguaje 9]
  bajada: 'Una línea por cada vez que alguien abre el enlace o la ficha, o escribe mal el PIN. Es un respaldo para ti.', // aprobado por Jorge el 03-11
  presentacion: (n: string) => `${n} abrió el enlace`, // [lenguaje 9]
  apertura: (n: string) => `${n} abrió la ficha`, // [lenguaje 9]
  pinIncorrecto: (n: string) => `${n} escribió mal el PIN`, // [lenguaje 9]
  bloqueo: (n: string) => `El enlace de ${n} se bloqueó por PIN incorrecto`, // [lenguaje 9]
  aLas: (hora: string) => `a las ${hora}`,
  // D2, aprobado por Jorge el 03-11. La última oración («…desde Enlaces.») espera a MATU-48 (D4).
  sinAbrir: 'Todavía no abre la ficha. Puede que no haya escrito el PIN aún, o que el enlace le haya llegado a otra persona.',
  // Aprobado por Jorge el 03-11.
  bloqueado: 'Ya no abre con ese enlace. Si fue un error al escribir, crea uno nuevo y díctale el PIN de nuevo.',
  vacio: 'Todavía nadie ha abierto la ficha. Cuando alguien la abra, aparece aquí.', // [lenguaje 9, D1]
  error: 'No pudimos traer quién la vio. Revisa tu conexión e inténtalo de nuevo.', // aprobado por Jorge el 03-11
  intentar: 'Intentar de nuevo',
  anteriores: 'Ver aperturas anteriores', // aprobado por Jorge el 03-11
  seAgregaron: (n: number) => `Se agregaron ${n} ${n === 1 ? 'línea' : 'líneas'}.`, // aprobado por Jorge el 03-11
  noHayMas: 'No hay más.', // aprobado por Jorge el 03-11
  nadieDeMatu: 'La ficha se guarda cifrada.', // aprobado por Jorge el 03-11 (reemplaza «Nadie de MATU puede abrir la ficha.», no verificable en el semestre)
  ultimas: 'Últimas aperturas', // [demo]
  verTodo: 'Ver todo en Quién la vio', // [demo]
}

export const TITULOS: Record<string, string> = {
  '/crear-cuenta': CUENTA.titulo,
  '/entrar': ENTRAR.titulo,
  '/entrar/recuperar': RECUPERAR.titulo,
  '/entrar/recuperar/codigo': RECUPERAR.tituloCodigo,
  '/cuenta': CUENTA_PROPIA.titulo,
  '/cuenta/celular': CELULAR.titulo,
  '/empezar/grupo': GRUPO.titulo,
  '/empezar/persona': PERSONA.titulo,
  '/empezar/autorizacion': AUTORIZACION.titulo,
  '/ficha': FICHA.titulo,
  '/ficha/quien-la-vio': QUIEN.titulo,
  '/insumos': ESTADOS.insumosTitulo,
  '/insumos/nuevo': 'Anotar un insumo', // [PROPUESTO] MATU-36, 2.2
  '/insumos/cambiar': 'Cambiar un insumo', // [PROPUESTO] MATU-36, 2.2
  '/compartir': ESTADOS.compartirTitulo,
}

// Todos los textos de la app de la familia (especificación MATU-39, versión 1.1). Las marcas dicen
// de dónde sale cada uno:
//   [lenguaje X]   docs/lenguaje.md, sección X, tal cual
//   [demo]         la demo aprobada, con "email" cambiado a "correo" (D1)
//   [PROPUESTO]    de la especificación, pendiente de entrar a lenguaje.md (sección 8)
//   [INSTRUCCIÓN]  dictado por decisión de Jorge del 02-11, pendiente de lenguaje.md
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
  errCelular: 'Escribe un celular de Chile, por ejemplo +56 9 5555 0137.', // [lenguaje 8]
  errContrasenaCorta: 'La contraseña necesita al menos 10 caracteres.', // [demo] // pragma: allowlist secret
  // 422 de la API, por `errores[].campo`
  err422Nombre: 'Escribe tu nombre, de hasta 100 letras.', // [PROPUESTO]
  err422Contrasena: 'La contraseña necesita entre 10 y 128 caracteres.', // [PROPUESTO] // pragma: allowlist secret
  registradoTitulo: 'Ese correo ya tiene una cuenta', // [demo]
  registradoTexto: 'Entra con tu contraseña, o usa otro correo.', // [demo]
  registradoBoton: 'Entrar con ese correo', // [demo]
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
  /** [INSTRUCCIÓN], con «Espera 1 minuto.» [PROPUESTO] */
  espera: (minutos: number) =>
    `Hubo varios intentos de entrar. ${minutos === 1 ? 'Espera 1 minuto.' : `Espera ${minutos} minutos.`} Si olvidaste tu contraseña, pídele ayuda a alguien de tu familia.`,
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
  bajada: 'Tres campos cortos para que quien te reemplace sepa qué hacer. Cada campo se guarda por separado y puedes compartir solo algunos.',
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
  volverALaFicha: 'Volver a la ficha', // [PROPUESTO]
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

export const TITULOS: Record<string, string> = {
  '/crear-cuenta': CUENTA.titulo,
  '/entrar': ENTRAR.titulo,
  '/empezar/grupo': GRUPO.titulo,
  '/empezar/persona': PERSONA.titulo,
  '/empezar/autorizacion': AUTORIZACION.titulo,
  '/ficha': FICHA.titulo,
  '/insumos': ESTADOS.insumosTitulo,
  '/compartir': ESTADOS.compartirTitulo,
}

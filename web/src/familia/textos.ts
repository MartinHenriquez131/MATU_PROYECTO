// Todos los textos de la app de la familia (especificación MATU-39, versión 1.1). Las marcas dicen
// de dónde sale cada uno:
//   [lenguaje X]   docs/lenguaje.md, sección X, tal cual
//   [INSTRUCCIÓN]  dictado por decisión de Jorge del 02-11, pendiente de lenguaje.md
//   [aprobado por Jorge el 03-11]  textos de MATU-57, pendientes de lenguaje.md
// Nunca se muestra `title`, `detail` ni `mensaje` de la API.

import type { Unidad } from '../compartido/api/consumo'

export const GENERAL = {
  /** [lenguaje 8] Cualquier otro, o sin respuesta. */
  error: 'No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo. Lo que escribiste sigue aquí.',
  /** [lenguaje 8] sin la última frase, al cargar (5.2). */
  errorAlCargar: 'No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo.',
  volverAIntentar: 'Volver a intentar', // [lenguaje 26]
  cargando: 'Cargando…', // [lenguaje 26]
  abriendo: 'Abriendo MATU…', // [lenguaje 26]
  /** [lenguaje 8] 404 de la familia. */
  noEncontrado: 'No encontramos lo que buscas. Puede que ya no tengas acceso. Vuelve al inicio.',
}

export const MARCO = {
  saltar: 'Saltar al contenido',
  cuidasA: 'Cuidas a', // [lenguaje 26]
  salir: 'Salir',
  secciones: 'Secciones',
  leDicen: (pila: string) => `Le dicen ${pila}`, // [lenguaje 26]
  cambiar: (nombre: string) => `${nombre}. Cambiar de persona`,
}

export const PASOS = ['Tu cuenta', 'Tu grupo', 'A quién cuidas', 'La autorización'] // [lenguaje 25]
export const pasoDe = (n: number) => `Paso ${n} de 4` // [lenguaje 25]
export const FRASE = 'Que el cuidado no dependa de una sola persona.' // [lenguaje 25]

export const CUENTA = {
  titulo: 'Crea tu cuenta', // [lenguaje 25.1]
  bajada: 'Para empezar te pedimos solo esto.', // [lenguaje 25.1]
  nombre: 'Tu nombre', // [lenguaje 25.1]
  nombreAyuda: 'Así te verán en tu grupo. Quien te reemplace verá tu nombre de pila.', // [lenguaje 25.1]
  correo: 'Tu correo', // [lenguaje 19]
  celular: 'Tu celular', // [lenguaje 19]
  celularAyuda: 'Para ayudarte a recuperar tu cuenta si olvidas la contraseña.', // [lenguaje 25.1]
  celularEjemplo: '+56 9',
  contrasena: 'Una contraseña', // [lenguaje 25.1] // pragma: allowlist secret
  contrasenaAyuda: 'Al menos 10 caracteres.', // [lenguaje 25.1] // pragma: allowlist secret
  mostrar: 'Mostrar', // [lenguaje 25.1]
  ocultar: 'Ocultar', // [lenguaje 25.1]
  boton: 'Crear cuenta',
  enviando: 'Creando la cuenta…', // [lenguaje 25.1]
  creada: 'Cuenta creada.', // [lenguaje 25.1]
  yaTienes: '¿Ya tienes cuenta?',
  irAEntrar: 'Entrar',
  errNombre: 'Escribe tu nombre.', // [lenguaje 25.1]
  errCorreo: 'Revisa cómo escribiste tu correo.', // [lenguaje 25.1]
  /** [lenguaje 13.3] 422 `email` con `tipo: dominio_no_permitido`, solo en staging (decisión 105). */
  errDominio: 'En este ambiente de prueba usa un correo terminado en @example.com.',
  errCelular: 'Escribe un celular de Chile, por ejemplo +56 9 5555 0137.', // [lenguaje 8]
  errContrasenaCorta: 'La contraseña necesita al menos 10 caracteres.', // [lenguaje 25.1] // pragma: allowlist secret
  // 422 de la API, por `errores[].campo`
  err422Nombre: 'Escribe tu nombre, de hasta 100 caracteres.', // [lenguaje 25.1]
  err422Contrasena: 'La contraseña necesita entre 10 y 128 caracteres.', // [lenguaje 25.1] // pragma: allowlist secret
  registradoTitulo: 'Ese correo ya tiene una cuenta', // [lenguaje 25.1]
  registradoTexto: 'Entra con tu contraseña, o usa otro correo.', // [lenguaje 25.1]
  registradoBoton: 'Entrar con ese correo', // [lenguaje 25.1]
}

/**
 * [lenguaje 13.3] 429 del límite por IP de MATU-25 (`/errores/demasiadas-peticiones`), solo al crear
 * la cuenta: recuperar y el celular conservan los de la sección 19 (corregido el 05-11). Los minutos
 * salen de `Retry-After` (`esperaDe`, compartido/api/cliente.ts). Entre el número y «minuto(s)» va
 * un espacio duro (`\u00A0`), aquí y en las otras esperas: al cortar la línea no se separan.
 */
export const ESPERA_CONEXION = {
  titulo: 'Espera un momento',
  texto: (minutos: number) => `Hubo muchos intentos desde esta conexión. Vuelve a intentarlo en ${minutos === 1 ? '1\u00A0minuto' : `${minutos}\u00A0minutos`}.`,
}

export const ENTRAR = {
  titulo: 'Entrar',
  correo: 'Tu correo',
  contrasena: 'Tu contraseña', // pragma: allowlist secret
  boton: 'Entrar',
  enviando: 'Entrando…',
  faltan: 'Escribe tu correo y tu contraseña.', // [lenguaje 13.3]
  noTienes: '¿No tienes cuenta?',
  irACrear: 'Crear cuenta',
  vencida: 'Hace tiempo que no entrabas. Vuelve a entrar con tu correo y tu contraseña.', // [INSTRUCCIÓN]
  salio: 'Saliste de MATU. Para volver, entra con tu correo y tu contraseña.', // [lenguaje 13.3]
  credenciales: 'El correo o la contraseña no coinciden. Revísalos y vuelve a intentarlo.', // [lenguaje 13.3]
  /** [aprobado por Jorge el 03-11] MATU-57 (especificación 4): reemplaza el de lenguaje 13.3; sigue el enlace a recuperar. */
  espera: (minutos: number) => `Hubo varios intentos de entrar. ${minutos === 1 ? 'Espera 1\u00A0minuto.' : `Espera ${minutos}\u00A0minutos.`}`,
  esperaRecuperar: 'Recupera tu cuenta', // [aprobado por Jorge el 03-11] MATU-57 // pragma: allowlist secret
  olvidaste: '¿Olvidaste tu contraseña?', // [aprobado por Jorge el 03-11] MATU-57 // pragma: allowlist secret
  /** [aprobado por Jorge el 03-11, D2] Tras cambiar la contraseña con el código. */
  claveCambiada: 'Listo. Cambiamos tu contraseña. Por seguridad, tendrás que volver a entrar en tus otros teléfonos y computadores.', // pragma: allowlist secret
  noDisponible: 'MATU no está disponible en este momento. Vuelve a intentarlo en unos minutos.', // [lenguaje 9.1]
}

export const GRUPO = {
  titulo: 'Ponle nombre a tu grupo', // [lenguaje 25.2]
  bajada: 'Es el grupo de las personas que cuidan contigo.', // [lenguaje 25.2]
  campo: 'Nombre del grupo', // [lenguaje 25.2]
  /** Política de privacidad, sección 4 («De tu grupo»), tal cual. */
  ayuda: 'Usa un nombre corto, como «Familia Soto». No incluyas el nombre completo de la persona que cuidas ni datos de salud.',
  boton: 'Crear el grupo', // [lenguaje 25.2]
  enviando: 'Creando el grupo…', // [lenguaje 25.2]
  errVacio: 'Escribe un nombre para el grupo.', // [lenguaje 25.2]
}

export const PERSONA = {
  titulo: '¿A quién cuidas?',
  nombre: '¿Cómo se llama?', // [lenguaje 25.3]
  pila: '¿Cómo le dicen?', // [lenguaje 25.3]
  pilaAyuda: 'Es el nombre que verá quien te reemplace.', // [lenguaje 25.3]
  apoyo: '¿Cuánto apoyo necesita en el día a día?', // [lenguaje 25.3]
  sinDiagnostico: 'No te preguntamos qué enfermedad tiene, porque para cuidar no hace falta.', // [lenguaje 25.3]
  boton: 'Continuar',
  errNombres: 'Escribe su nombre y cómo le dicen para seguir.', // [lenguaje 25.3]
  errApoyo: 'Elige cuánto apoyo necesita.', // [lenguaje 25.3]
}

export const AUTORIZACION = {
  titulo: 'Permiso para guardar su ficha', // [lenguaje 22], para el alta desde el 08-11 (Jorge)
  bajada: (pila: string) =>
    `Lo que anotes sobre el cuidado de ${pila} puede decir algo de su salud. Por eso lo protegemos de forma especial y necesitamos una autorización. Puedes retirarla cuando quieras, desde Grupo familiar.`, // [lenguaje 25.4]
  leyenda: '¿Quién da la autorización?', // [lenguaje 25.4]
  referencia: 'Referencia del documento', // [lenguaje 25.4]
  referenciaAyuda: 'Por ejemplo: número de resolución y fecha. Sin el RUT.', // [lenguaje 25.4]
  leido: 'Leí el aviso y lo acepto', // [lenguaje 25.4]
  declaras: 'Lo que declaras', // [lenguaje 25.4]
  boton: (pila: string) => `Acepto y registro a ${pila}`, // [lenguaje 25.4]
  enviando: (pila: string) => `Registrando a ${pila}…`, // [lenguaje 25.4]
  registrada: (pila: string) => `Listo. Registramos a ${pila} y la autorización. Ahora puedes completar su ficha.`, // [lenguaje 25.4]
  volverACorregir: (pila: string) => `Volver a corregir los datos de ${pila}`, // [lenguaje 25.4]
  volver: 'Volver a ¿A quién cuidas?',
  errCalidad: 'Elige quién da la autorización.', // [lenguaje 25.4]
  errReferencia: 'Escribe la referencia del documento que te nombra representante.', // [lenguaje 25.4]
  errLeido: 'Marca que leíste el aviso para seguir.', // [lenguaje 25.4]
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
  detener: 'Detener', // [lenguaje 5.4]
  sinMicrofono: 'No pudimos usar el micrófono. Puedes escribir el texto.', // [lenguaje 5.4]
  // Salir sin guardar (3.7)
  sinGuardar: (c: string) => `Lo que escribiste en «${c}» no se guardó. ¿Salir igual?`, // [lenguaje 6.6]
  salirSinGuardar: 'Salir sin guardar', // [lenguaje 6.6]
  seguirEscribiendo: 'Seguir escribiendo', // [lenguaje 6.6]
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
  // [lenguaje 6.4] El final cambia por rol (MATU-44, P4): admin y cuidador ven «La puedes volver a
  // autorizar desde Grupo familiar.» (GRUPO_FAMILIAR.fichaPuedesVolver) y el resto, `sinConsentimientoPide`.
  sinConsentimiento: 'Sin ella no podemos guardar ni mostrar la ficha.',
  sinConsentimientoPide: 'Pídele a quien administra el grupo que la registre.',
  revisionTitulo: (pila: string) => `Hay que renovar la autorización de la ficha de ${pila}.`,
  revision: 'Se renueva una vez al año. Mientras tanto, la ficha no se puede ver ni cambiar, pero lo que escribiste sigue guardado.',
  revisionPide: 'Pídele a quien administra el grupo que la renueve.',
  chileAtiende: 'Apoyos del Estado para quienes cuidan',
  chileAtiendeNota: '(se abre en ChileAtiende)',
  chileAtiendeUrl: 'https://www.chileatiende.gob.cl/fichas/112779-persona-cuidadora',
  loEscrito: 'Lo que escribiste sigue aquí. Cópialo si lo quieres guardar en otra parte.', // [lenguaje 6.6]
  // 5.7
  vencidaConTexto: 'Tienes que volver a entrar. Copia lo que escribiste antes de seguir: no se guardó.', // [lenguaje 6.6]
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
  // 5.4 [lenguaje 25.3]
  sinPersona: (grupo: string) =>
    `Todavía no hay nadie registrado en ${grupo}. Quien administra el grupo puede registrar a la persona que cuidan.`,
  // MATU-48 2.1: la pantalla «Pronto vas a poder compartir…» de MATU-39 5.5 sale.
  compartirTitulo: 'Compartir',
  // 5.6 [lenguaje 8]
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
  errCorreo: 'Revisa cómo escribiste tu correo.', // [lenguaje 25.1] el mismo que CUENTA.errCorreo
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
  esperaCodigo: (minutos: number) => `Hubo varios intentos con ese código. Pide uno nuevo en ${minutos === 1 ? '1\u00A0minuto' : `${minutos}\u00A0minutos`}.`,
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
  espera: (minutos: number) => `Ya pediste varios códigos. Espera ${minutos === 1 ? '1\u00A0minuto' : `${minutos}\u00A0minutos`} y vuelve a intentarlo.`,
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
  // D2, aprobado por Jorge el 03-11. Con MATU-48 suma `siTePreocupa` (lenguaje 15), solo para admin y cuidador.
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
  ultimas: 'Últimas aperturas', // [lenguaje 15]
  verTodo: 'Ver todo en Quién la vio', // [lenguaje 9.1]
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
  '/insumos/nuevo': 'Anotar un insumo', // [lenguaje 18] MATU-36, 2.2
  '/insumos/cambiar': 'Cambiar un insumo', // [lenguaje 18] MATU-36, 2.2
  '/insumos/lista': 'Lista de insumos', // [lenguaje 21] MATU-60, 2.2
  '/insumos/catalogo': 'Catálogo', // [lenguaje 27] MATU-59, 2.2
  // MATU-61 2.1 [lenguaje 31]: sin nombres ni ids.
  '/insumos/pedido': 'Tu pedido',
  '/insumos/pedido/direccion': '¿Dónde lo entregamos?',
  '/insumos/pedido/resumen': 'Antes de pagar',
  // MATU-62 2.1: el `h1` de cada estado; la pantalla lo cambia. Al llegar desde Webpay, este.
  '/insumos/pedido/pago': 'Estamos confirmando tu pago',
  '/compartir': ESTADOS.compartirTitulo,
  // MATU-48 2.1: nunca el nombre del relevo ni de la persona.
  '/compartir/listo': 'Enlace creado', // aprobado por Jorge el 04-11
  '/compartir/enlaces': 'Enlaces',
  // MATU-44 2.1: las tres rutas, sin nombres.
  '/grupo': 'Grupo familiar',
  '/grupo/autorizar-ficha': 'Grupo familiar',
  '/grupo/autorizar-insumos': 'Grupo familiar',
  '/grupo/autorizar-pedidos': 'Permiso para pedir sus insumos', // MATU-61 2.1
}

/**
 * Compartir la ficha con un relevo y cortar el acceso (MATU-48, docs/diseno/matu-48-compartir.md).
 * [lenguaje 9] y [lenguaje 9.1] tal cual; lo demás, aprobado por Jorge el 04-11.
 */
export const COMPARTIR = {
  titulo: 'Compartir', // [lenguaje 9.1]
  enlaces: 'Enlaces', // [lenguaje 9.1]
  vistas: 'Vistas de Compartir',
  // Aprobado por Jorge el 04-11: reemplaza el de lenguaje 9, que decía «por WhatsApp».
  bajada: 'Quien te reemplaza recibe un enlace en un mensaje y el PIN se lo dictas tú. El enlace vence solo y lo puedes cortar antes.',
  /** Cuando todavía no se escribe el nombre. */
  quienTeReemplaza: 'quien te reemplaza',
  nombre: '¿Quién te va a reemplazar?', // [lenguaje 9]
  nombreAyuda: 'Basta con su nombre de pila.',
  telefono: 'Su teléfono', // [lenguaje 9]
  telefonoAyuda: 'Para enviarle el enlace y poder contactarle.', // [lenguaje 9]
  /** [lenguaje 9.1] «Si se altera y A quién llamar están vacíos: Rosa verá «Sin completar».» */
  vacios: (campos: string[], nombre: string) => {
    const lista = campos.length > 1 ? `${campos.slice(0, -1).join(', ')} y ${campos[campos.length - 1]}` : campos[0]
    return `${lista} ${campos.length > 1 ? 'están vacíos' : 'está vacío'}: ${nombre} verá «Sin completar».`
  },
  recordatorio: (pila: string) =>
    `Comparte solo lo que necesita para cuidar a ${pila}. Quien recibe el enlace puede anotar o fotografiar lo que lee, y MATU no puede impedirlo.`,
  hastaCuando: '¿Hasta cuándo?', // [lenguaje 9]
  vigencias: { '24h': '24 horas', finde: 'Fin de semana', dias: 'Otra cantidad de días' }, // [lenguaje 9.1]
  cuantosDias: '¿Cuántos días?', // [lenguaje 9]
  hasta30: 'Hasta 30 días.', // [lenguaje 9]
  dias: 'días', // [lenguaje 9.1]
  /** «Vence el {fecha} a las {hora}.», partido para poner la fecha y la hora en `cifras`. */
  vence: ['Vence el ', ' a las ', '.'] as const,
  paraQue: '¿Para qué lo compartes?', // [lenguaje 9]
  motivos: {
    salgo_unas_horas: 'Salgo unas horas',
    fin_de_semana_fuera: 'Fin de semana fuera',
    turno_de_noche: 'Turno de noche',
    otro: 'Otro motivo',
  }, // [lenguaje 9]
  avise: (nombre: string) => `Le avisé a ${nombre} que MATU guarda su nombre y su teléfono para enviarle la ficha.`, // [contrato, decisión 34]
  errAvise: (nombre: string) => `Marca que le avisaste a ${nombre} para crear el enlace.`,
  errNombre: 'Escribe el nombre de quien te reemplaza.', // [lenguaje 8]
  errTelefono: 'Escribe un celular de Chile, por ejemplo +56 9 5555 0137.', // [lenguaje 8]
  errMaxima: 'El enlace puede durar como máximo 30 días.', // [lenguaje 8]
  errPasada: 'Esa fecha ya pasó. Elige de nuevo hasta cuándo.',
  errSeccion: 'Otra persona quitó una sección mientras compartías. Revisa qué más puede ver y vuelve a crear el enlace.',
  noDisponible: 'MATU no está disponible en este momento. Vuelve a intentarlo en unos minutos.', // [lenguaje 9.1]
  crear: 'Crear enlace', // [lenguaje 9.1]
  creando: 'Creando el enlace…',
  loQueVera: (nombre: string) => `Lo que verá ${nombre}`, // [lenguaje 9.1]

  // El PIN, una sola vez (4)
  creadoPara: (nombre: string) => `Enlace creado para ${nombre}`, // [lenguaje 9.1]
  creado: 'Enlace creado',
  pinTitulo: 'PIN para abrir la ficha', // [lenguaje 9.1]
  /** [lenguaje 9] La primera oración va en negrita. */
  dictaselo: (nombre: string) => [`Díctaselo a ${nombre} por teléfono.`, ' No lo mandes junto con el enlace. Solo lo verás ahora.'] as const,
  cuentale: (nombre: string) => `Cuéntale a ${nombre} que anotaste su nombre y su teléfono en MATU, y que cada vez que abra el enlace o la ficha queda registrado.`, // [lenguaje 9]
  enviar: 'Enviar el enlace',
  copiar: 'Copiar el enlace',
  /** Lo que se comparte: nunca el PIN. */
  mensaje: (nombre: string, url: string) => `Hola, ${nombre}. Te comparto la ficha de cuidado en MATU: ${url}. El PIN te lo digo por teléfono.`,
  copiado: (nombre: string) => `Enlace copiado. Pégalo en tu mensaje a ${nombre}.`,
  noCopiado: 'No pudimos copiar el enlace. Usa «Enviar el enlace».',
  enlacePara: (nombre: string) => `Enlace para ${nombre}`,
  verEnlaces: 'Ver los enlaces', // [lenguaje 9.1]
  pinPerdidoTitulo: 'El PIN ya no se puede ver', // [lenguaje 9]
  pinPerdido: 'Por seguridad se muestra una sola vez. Si se perdió, crea un enlace nuevo y corta el anterior.', // [lenguaje 9]
  crearNuevo: 'Crear un enlace nuevo', // [lenguaje 9.1]

  // Enlaces (5)
  enlacesBajada:
    'Al cortar un enlace deja de abrir de inmediato. Si quien lo tenía estaba mirando la ficha, se cierra cuando vuelva a mirarla. Quien lo tenía no recibe aviso.', // [lenguaje 9]
  abrenAhora: 'Abren ahora',
  yaNoAbren: 'Ya no abren',
  ninguno: 'Ningún enlace abre ahora.',
  sinEnlaces: 'No hay enlaces todavía. Crea uno desde Compartir.', // [lenguaje 9]
  activoVence: 'Activo, vence en', // [lenguaje 9 + demo]
  estados: { vencido: 'Vencido', revocado: 'Cortado', bloqueado: 'Bloqueado' }, // [lenguaje 9]
  // Decisión 33, aprobado por Jorge el 04-11: con la autorización por renovar, los enlaces quedan en
  // pausa. [lenguaje 9.1, ajustado el 06-11 por MATU-44] La retirada está en GRUPO_FAMILIAR.
  enPausa: 'En pausa',
  pausa: 'Mientras no se renueve la autorización, ningún enlace abre. Cuando se renueve, vuelven a abrir los que no hayan vencido.',
  loCreo: (nombre: string) => `Lo creó ${nombre}.`,
  /** «Venció el {fecha} a las {hora}.» y «Lo cortaron el {fecha} a las {hora}.», partidos para `cifras`. */
  vencio: ['Venció el ', ' a las ', '.'] as const,
  loCortaron: ['Lo cortaron el ', ' a las ', '.'] as const,
  detalleBloqueado: 'Se bloqueó porque el PIN se escribió mal cinco veces.', // [lenguaje 9]
  cortar: (nombre: string) => `Cortar el enlace de ${nombre}`, // [lenguaje 9]
  cortando: 'Cortando…',
  cortado: (nombre: string) => `Enlace cortado. Ya no abre para ${nombre}.`, // [lenguaje 9]
  cortadoAbierta: (nombre: string) => `Si ${nombre} tenía la ficha abierta, se cierra cuando vuelva a mirarla.`, // [lenguaje 9.1]
  errCortar: 'No pudimos cortar el enlace. Revisa tu conexión y vuelve a intentarlo. El enlace todavía abre.',
  errListar: 'No pudimos traer los enlaces. Revisa tu conexión e inténtalo de nuevo.',
  intentar: 'Intentar de nuevo', // [lenguaje 15]
  anteriores: 'Ver enlaces anteriores',
  seAgregaron: (n: number) => (n === 1 ? 'Se agregó 1 enlace.' : `Se agregaron ${n} enlaces.`),
  noHayMas: 'No hay más.', // [lenguaje 15]
  verCuando: 'Ver cuándo la abrió', // [lenguaje 9.1]
  llamar: (nombre: string) => `Llamar a ${nombre}`,
  sinTelefono: 'Ya no guardamos su teléfono.',

  // Puertas de entrada (2.3 y 2.4)
  conRelevo: 'Compartir con un relevo', // [lenguaje 6.1]
  laFicha: 'Compartir la ficha',
  puedenVerla: 'Quién puede verla ahora',
  venceEn: 'vence en', // [lenguaje 9.1]
  nadieActivo: 'Nadie tiene un enlace activo ahora.',
  verYCortar: 'Ver y cortar enlaces',
  /** [lenguaje 15] «Enlaces» va como enlace en línea. */
  siTePreocupa: ['Si te preocupa, puedes cortarlo desde ', 'Enlaces', '.'] as const,
}

/**
 * «Ve su día, si se altera, a quién llamar y quién es.» con los campos y las secciones del acceso,
 * en el orden fijo (lenguaje 14.3). Los accesos anteriores a MATU-50 pueden tener uno o dos campos.
 */
export const loQueVeAcceso = (campos: readonly string[], secciones: readonly string[]) => {
  const todo = [...campos, ...secciones].map((t) => t.toLowerCase())
  if (!todo.length) return ''
  return todo.length === 1 ? `Ve ${todo[0]}.` : `Ve ${todo.slice(0, -1).join(', ')} y ${todo[todo.length - 1]}.`
}

/**
 * La lista de insumos (MATU-60, docs/diseno/matu-60-lista-insumos.md v1.1). Todos [lenguaje 21],
 * aprobados por Jorge el 06-11, incluidos los [NUEVO] y [AJUSTE] de la sección 13 de la
 * especificación, que van a lenguaje.md en el PR de documentos #45. Nunca «reposición», «quiebre»,
 * «stock», «comprar» ni «pedir». La línea «Esta pantalla no se imprime.» vive en index.css (8.4).
 */
export const LISTA = {
  titulo: 'Lista de insumos',
  /** Las pestañas de Insumos (2.1). La primera es «Insumos» [M36]. */
  vistas: 'Vistas de Insumos',
  /** `document.title` durante la impresión (8.3). Fuera de ella, «Lista de insumos · MATU». */
  documentoImpreso: 'Lista de insumos',
  bajada: 'Lo que se acaba pronto, con una cantidad sugerida para 30 días. Puedes cambiarla antes de imprimir o compartir.',
  bajadaObservador: 'Lo que se acaba pronto, con una cantidad sugerida para 30 días.',

  // 4.3 La línea
  alcanzaPara: 'Alcanza para', // + {n} + «días» / «día», con la cifra aparte
  seAcabaHoy: 'Se acaba hoy',
  puedeQueNo: 'Puede que ya no quede',
  soloAqui: 'Solo en esta pantalla',
  cantidad: 'Cantidad',
  menos: (nombre: string) => `Menos: Cantidad de ${nombre}`,
  mas: (nombre: string) => `Más: Cantidad de ${nombre}`,
  errCantidad: 'Escribe una cantidad de 1 a 100.000.',
  quitar: 'Quitar de la lista', // [AJUSTE]
  quitarDe: (nombre: string) => `Quitar de la lista: ${nombre}`, // [AJUSTE v1.2] empieza con el texto visible (WCAG 2.5.3)

  // 4.6 Nota del cálculo [AJUSTE]
  nota: 'Es una sugerencia con lo que anotaste, y ya descuenta lo que queda. Cambia la cantidad si necesitas otra.',
  notaPagador: 'Es una sugerencia con lo que anotó la familia, y ya descuenta lo que queda. Cambia la cantidad si necesitas otra.',
  notaObservador: 'Es una sugerencia con lo que anotó la familia, y ya descuenta lo que queda.',

  // 4.7 Agregar otro insumo
  agregarOtro: 'Agregar otro insumo',
  nombre: '¿Qué insumo es?', // [lenguaje 18]
  nombreAyuda: 'Por ejemplo: «Toallitas húmedas». Sin remedios ni para qué se usa.',
  comoSeCuenta: '¿Cómo se cuenta?', // [lenguaje 18]
  /** [NUEVO] decisión 2, en este orden. */
  unidades: [
    { valor: 'unidad' as const, texto: 'Unidades' },
    { valor: 'sobre' as const, texto: 'Sobres' },
    { valor: 'envase' as const, texto: 'Envases' },
  ],
  soloAquiNota: 'Esto queda solo en esta pantalla. No lo guardamos.',
  agregar: 'Agregar',
  cancelar: 'Cancelar', // [M36]
  errNombre: 'Escribe el nombre del insumo.', // [lenguaje 18]
  errNombreLargo: 'El nombre admite hasta 60 caracteres. Acórtalo un poco.', // [lenguaje 18]
  agregamos: (nombre: string) => `Agregamos «${nombre}» a la lista.`,

  // 4.10 Quitar
  quitamosDeMatu: (nombre: string) => `Quitamos «${nombre}» de la lista. Sigue en Insumos.`, // [NUEVO]
  quitamos: (nombre: string) => `Quitamos «${nombre}» de la lista.`, // [AJUSTE]
  sigueEnInsumos: 'Lo que quitaste sigue en Insumos. Vuelve a esta lista cuando entras de nuevo.', // [NUEVO]
  quitasteTodo: 'Quitaste todo de la lista. Si quieres, agrega uno a mano.', // [NUEVO]

  // 4.8 y 4.9 Aviso y botones
  aviso: (pila: string) =>
    `La lista no lleva el nombre de ${pila}, pero sí lo que usa. Lo que imprimas o compartas sale de MATU y no podemos borrarlo. Compártela solo con quien va a comprar.`,
  compartir: 'Compartir la lista',
  imprimir: 'Imprimir o guardar en PDF',
  copiar: 'Copiar la lista',

  // 7.3 y 7.4 Mensajes
  copiada: 'Copiamos la lista. Pégala donde quieras.',
  errCopiarCompartir: 'No pudimos copiar la lista. Usa «Compartir la lista».',
  errCopiarImprimir: 'No pudimos copiar la lista. Usa «Imprimir o guardar en PDF».',
  errCompartir: 'No pudimos abrir Compartir. Usa «Copiar la lista».',

  // 5 y 6
  vacio: 'No hay insumos que se acaben pronto. Si quieres, agrega uno a mano.',
  vacioObservador: 'No hay insumos que se acaben pronto.',
  observador: 'Quien administra, cuida o paga puede imprimirla o compartirla.',
  errCarga: 'No pudimos traer la lista. Revisa tu conexión e inténtalo de nuevo.',

  // 7.2 y 8 El texto y el papel
  encabezado: (fecha: string) => `Lista de insumos · ${fecha}`,
  pie: 'Piloto académico con datos de prueba',

  // 9 El campo del envase en el formulario del insumo
  /** [lenguaje 18] MATU-88: en los insumos en sobres dice «sobres» (H2 del TESTER de MATU-84). */
  envase: (unidad: Unidad) => (unidad === 'sobre' ? '¿Cuántos sobres trae cada envase?' : '¿Cuántas unidades trae cada envase?'),
  envaseAyuda: 'Si lo anotas, la lista sugiere envases enteros. Puedes dejarlo en blanco.',
  errEnvase: 'Escribe un número de 1 a 10.000, o déjalo en blanco.',
  envaseConflicto: (u: string, sufijo: string) => `Cada envase trae ${u} ${sufijo}.`,
  sinEnvase: 'Sin unidades por envase.',
  // MATU-84 (especificación matu-84-me-quedan-envases.md, 7): el mismo campo dentro de «Contar en envases» [L 30]
  envaseAyudaEnvases: 'Lo guardamos para la próxima vez y para la lista.', // [L 30]
  errFaltaEnvase: (unidad: Unidad) => (unidad === 'sobre' ? 'Escribe cuántos sobres trae cada envase.' : 'Escribe cuántas unidades trae cada envase.'), // [L 30] y MATU-88
  errEnvaseRango: 'Escribe un número de 1 a 10.000.', // [L 30]
}

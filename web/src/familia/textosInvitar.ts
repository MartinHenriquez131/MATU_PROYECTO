// Invitar a un familiar y ver el grupo (MATU-42 y MATU-53, especificación
// docs/diseno/matu-53-invitar-grupo.md v1.1). Marcas, como en la especificación:
// - [ANALISTA]: de la revisión previa del analista (sección 5), aprobada por Jorge el 12-11.
// - [NUEVO]: de la especificación, aprobado por el orquestador por delegación de Jorge (0.4). Ninguno
//   está todavía en lenguaje.md: entran en su sección 33 con el PR de documentos (decisión 326).
// - [L n]: ya está en lenguaje.md, sección n.
// - [NUEVO v1.2]: los seis vacíos de la v1.1, decididos tras la revisión visual (sección 0.5).
// En la interfaz nunca se dice «token», «usuario», «observador», «revocar», «rechazar», «invitado» ni
// «invitada», y ningún texto asume el género de nadie (criterio 16).
import type { Rol } from '../compartido/api/familia'
import { CORREO_CONTACTO } from '../compartido/contacto'

/** Une nombres con «y»: «María», «María y Pedro», «María, Pedro y Elena» (4.5). */
export function unirNombres(nombres: readonly string[]): string {
  if (nombres.length <= 1) return nombres[0] ?? ''
  return `${nombres.slice(0, -1).join(', ')} y ${nombres[nombres.length - 1]}`
}

/** 5.7: quien ya no está en el grupo. Se escribe como un nombre, con el mismo estilo. */
export const YA_NO_ESTA = {
  inicio: 'Alguien que ya no está en el grupo', // [ANALISTA]
  medio: 'alguien que ya no está en el grupo', // [NUEVO]
}

/** 5.10: sin persona registrada, donde la frase pide su nombre de pila. [NUEVO v1.2] */
const SIN_PERSONA = 'la persona que cuidan'
const pilasO = (pilas: readonly string[]) => (pilas.length ? unirNombres(pilas) : SIN_PERSONA)

/** El rol, siempre en palabra (5.3). [ANALISTA] */
export const ROL: Record<Rol, string> = {
  admin: 'Administra el grupo',
  cuidador: 'Cuida',
  pagador: 'Paga',
  observador: 'Se informa',
}

/** 4.2: el rol en infinitivo, para «…para cuidar». [NUEVO] */
export const ROL_INFINITIVO: Record<Rol, string> = {
  admin: 'administrar el grupo',
  cuidador: 'cuidar',
  pagador: 'pagar',
  observador: 'informarte',
}

/** 6.4 (v1.2): el rol propio en segunda persona. [NUEVO v1.2] */
const ROL_TU: Record<Rol, string> = {
  admin: 'administras el grupo',
  cuidador: 'cuidas',
  pagador: 'pagas',
  observador: 'te informas',
}

/** 6.4: «Ahora Rosa cuida.» El rol en minúscula. [ANALISTA] */
const ROL_MINUSCULA: Record<Rol, string> = {
  admin: 'administra el grupo',
  cuidador: 'cuida',
  pagador: 'paga',
  observador: 'se informa',
}

/**
 * Lo que permite cada rol (3.2). La de «Paga» sin la capa 3 no nombra los pedidos (ajuste de Jorge,
 * 6.3) [NUEVO]; con la capa 3, la del analista. «Se informa» nombra a las personas cuidadas.
 */
export function descripcionRol(rol: Rol, { capa3, pilas }: { capa3: boolean; pilas: readonly string[] }): string {
  if (rol === 'admin') return 'Ve y cambia todo, comparte la ficha, invita y cambia los permisos.' // [ANALISTA]
  if (rol === 'cuidador') return 'Ve y cambia la ficha y los insumos, y comparte la ficha con quien te reemplaza.' // [ANALISTA]
  if (rol === 'pagador')
    return capa3
      ? 'Ve los insumos y paga los pedidos. Ve la ficha solo si quien administra le da permiso.' // [ANALISTA]
      : 'Ve los insumos. Ve la ficha solo si quien administra le da permiso.' // [NUEVO]
  return `Ve el nombre de ${pilasO(pilas)} y sus insumos. No ve la ficha.` // [ANALISTA]
}

const enlaces = (n: number, uno: string, varios: (n: number) => string) => (n === 1 ? uno : varios(n))

/** «Cortamos 1 enlace.» y «Cortamos {n} enlaces.», solo si hubo. [NUEVO, la forma de L 22] */
export const cortamos = (n: number) => (n <= 0 ? '' : enlaces(n, 'Cortamos 1 enlace.', (k) => `Cortamos ${k} enlaces.`))

// ---------------------------------------------------------------- 5 Grupo familiar

export const MIEMBROS = {
  bajada: (grupo: string) => `Quiénes forman ${grupo}, a quién cuidan y qué permisos dieron.`, // [NUEVO]
  titulo: 'Quiénes forman el grupo', // [ANALISTA]
  tu: '(tú)', // [ANALISTA]
  seUnio: 'Se unió el', // [NUEVO] «Se unió el {fecha}.»
  puedeVerFicha: 'Puede ver la ficha', // [ANALISTA]
  noVeFicha: 'No ve la ficha', // [ANALISTA]
  cambiar: 'Cambiar lo que puede hacer', // [NUEVO]
  cambiarDe: (nombre: string) => `Cambiar lo que puede hacer ${nombre}`,
  cambiarTuRol: 'Cambiar tu rol', // [NUEVO]
  darFicha: 'Dejar que vea la ficha', // [ANALISTA]
  darFichaA: (nombre: string) => `Dejar que vea la ficha a ${nombre}`,
  quitarFicha: 'Quitarle la ficha', // [ANALISTA]
  quitarFichaA: (nombre: string) => `Quitarle la ficha a ${nombre}`,
  sacar: 'Sacar del grupo', // [ANALISTA]
  sacarA: (nombre: string) => `Sacar del grupo a ${nombre}`,
  unicoAdmin: 'Eres la única persona que administra el grupo. Para dejar ese rol, primero dáselo a otra persona.', // [NUEVO]
  invitar: 'Invitar a alguien', // [ANALISTA]
  soloAdmin: 'Solo quien administra el grupo invita, cambia los roles y saca a alguien.', // [NUEVO]
  soloTu: 'Por ahora solo estás tú. Invita a quien cuida contigo.', // [NUEVO]
  errCargar: 'No pudimos traer quiénes forman el grupo. Revisa tu conexión e inténtalo de nuevo.', // [ANALISTA]
  volverAIntentar: 'Volver a intentar', // [L 26]
  yaNoEstaba: 'Esa persona ya no estaba en el grupo.', // [ANALISTA]
  yaNoAdministras: 'Ya no administras el grupo.', // [NUEVO]

  // 5.4 Invitaciones sin usar
  invitaciones: 'Invitaciones sin usar', // [ANALISTA]
  /** «{rol} · vence el {fecha} a las {hora}.» [ANALISTA, con la hora] */
  vence: ['· vence el', 'a las'] as const,
  /** 5.4 (v1.2): la invitación bloqueada. [NUEVO v1.2] */
  seBloqueo: '· se bloqueó.',
  bloqueada: 'El código se escribió mal cinco veces. Ya no sirve.',
  laCreo: (nombre: string) => `La creó ${nombre}.`, // [NUEVO]
  anular: 'Anular la invitación', // [ANALISTA]
  anulada: 'Invitación anulada.', // [ANALISTA]

  // 5.5 y 5.6
  necesitaAdmin: 'El grupo necesita alguien que lo administre. Primero da ese rol a otra persona.', // [ANALISTA]
  autorizoQuienYaNoEsta: 'La autorización la dio alguien que ya no está en el grupo. Sigue vigente.', // [ANALISTA, ajustado y aprobado]
}

// ---------------------------------------------------------------- 8.4 Anular (la especificación no la trae)

export const ANULAR = {
  pregunta: '¿Anular la invitación?', // [NUEVO v1.2]
  texto: 'El enlace deja de servir, también con el código. Si quieres que esa persona se una, crea una invitación nueva.', // [NUEVO v1.2]
  boton: 'Anular la invitación', // [ANALISTA]
  no: 'No anular', // [NUEVO v1.2]
  ocupado: 'Anulando la invitación…', // [NUEVO v1.2]
  errRed: 'No pudimos anular la invitación. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.', // [NUEVO v1.2]
  cerrada: (estado: string | null) =>
    estado === 'usada' ? 'Esa invitación ya se usó.' : estado === 'vencida' ? 'Esa invitación ya venció.' : 'Esa invitación ya no se puede anular.', // [NUEVO v1.2]
}

// ---------------------------------------------------------------- 6 Cambiar el rol

export const CAMBIAR_ROL = {
  pregunta: (nombre: string) => `Cambiar lo que puede hacer ${nombre}`, // [NUEVO]
  preguntaTuya: 'Cambiar tu rol', // [NUEVO]
  leyenda: '¿Qué podrá hacer?', // [ANALISTA]
  ahora: 'Ahora', // [NUEVO]
  mismoRol: 'Elige otro rol para guardar.', // [NUEVO]
  seraAdmin: (nombre: string) => `${nombre} podrá invitar, cambiar permisos y sacar a otras personas, también a ti.`, // [ANALISTA, con el nombre]
  pierdeFicha: (nombre: string, n: number | null) => {
    const primera = `${nombre} dejará de ver la ficha.` // [NUEVO]
    if (n === null || n <= 0) return primera
    return `${primera} ${enlaces(n, 'Se corta 1 enlace de relevo que compartió.', (k) => `Se cortan ${k} enlaces de relevo que compartió.`)}` // [ANALISTA] y [NUEVO, singular]
  },
  comoPaga: 'Como paga, no verá la ficha hasta que le des permiso.', // [NUEVO]
  dejasDeAdministrar: 'Dejarás de administrar el grupo. Para volver a hacerlo, otra persona que administra tendrá que dártelo.', // [NUEVO]
  /** 6.3 (v1.3): otra persona deja de administrar y sigue viendo la ficha (de admin a cuida). [NUEVO v1.3] */
  dejaraDeAdministrar: (nombre: string) => `${nombre} dejará de administrar el grupo.`,
  guardar: 'Guardar el cambio', // [ANALISTA]
  noCambiar: 'No cambiar', // [ANALISTA]
  guardando: 'Guardando el cambio…', // [NUEVO]
  hecho: (nombre: string, rol: Rol, n: number) => [`Ahora ${nombre} ${ROL_MINUSCULA[rol]}.`, cortamos(n)].filter(Boolean).join(' '), // [ANALISTA] + [NUEVO]
  /** 6.4 (v1.2): mi propio rol, en segunda persona y sin mi nombre. «Ahora administras…» no ocurre. [NUEVO v1.2] */
  hechoPropio: (rol: Rol, n: number) => [`Ahora ${ROL_TU[rol]}.`, cortamos(n)].filter(Boolean).join(' '),
  errRed: 'No pudimos guardar el cambio. Todo sigue como estaba.', // [ANALISTA]
  conflicto: (nombre: string, rol: Rol) =>
    `Otra persona del grupo cambió lo que puede hacer ${nombre} mientras lo mirabas. Ahora ${nombre} ${ROL_MINUSCULA[rol]}. Revisa y vuelve a elegir.`, // [NUEVO]
}

// ---------------------------------------------------------------- 6.7 El permiso del pagador

export const PERMISO_FICHA = {
  darPregunta: (nombre: string) => `¿Dejar que ${nombre} vea la ficha?`, // [NUEVO]
  darTexto: (pilas: readonly string[]) =>
    `Podrá leer ${pilas.length > 1 ? 'las fichas' : 'la ficha'} de ${pilasO(pilas)} y ver sus enlaces de relevo. No podrá cambiarla ni compartirla.`, // [NUEVO]
  darBoton: 'Dejar que vea la ficha', // [ANALISTA]
  darNo: 'No por ahora', // [NUEVO]
  dado: (nombre: string) => `Ahora ${nombre} puede ver la ficha.`, // [NUEVO]
  quitarPregunta: (nombre: string) => `¿Quitarle la ficha a ${nombre}?`, // [NUEVO]
  quitarTexto: (nombre: string) => `${nombre} dejará de ver la ficha desde ahora.`, // [NUEVO]
  quitarBoton: 'Quitarle la ficha', // [ANALISTA]
  quitarNo: 'No quitar', // [NUEVO]
  quitado: (nombre: string) => `${nombre} ya no ve la ficha.`, // [NUEVO]
}

// ---------------------------------------------------------------- 7 Sacar y salir

export const SACAR = {
  pregunta: (nombre: string) => `¿Sacar a ${nombre} del grupo?`, // [ANALISTA]
  dejaraDeVerlo: 'Dejará de verlo ahora.', // [ANALISTA]
  enlaces: (n: number | null) =>
    n === null
      ? 'Se cortan los enlaces de relevo que compartió.' // [ANALISTA, sin el número cuando no se sabe]
      : n <= 0
        ? 'No tiene enlaces de relevo que abran ahora.' // [NUEVO]
        : enlaces(n, 'Se corta 1 enlace de relevo que compartió.', (k) => `Se cortan ${k} enlaces de relevo que compartió.`), // [ANALISTA]
  fichaQueda: 'Lo que escribió en la ficha queda.', // [ANALISTA]
  paraVolver: (nombre: string) => `Para volver, tendrías que invitar a ${nombre} de nuevo.`, // [NUEVO]
  boton: 'Sacar del grupo', // [ANALISTA]
  no: 'No sacar', // [ANALISTA]
  ocupado: 'Sacando del grupo…', // [NUEVO]
  hecho: (nombre: string, n: number) => [`${nombre} ya no está en el grupo.`, cortamos(n)].filter(Boolean).join(' '), // [ANALISTA] + [NUEVO]
  errRed: (nombre: string) => `No pudimos sacar a ${nombre} del grupo. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.`, // [NUEVO]
}

export const SALIR = {
  titulo: 'Salir del grupo', // [ANALISTA]
  texto: (grupo: string) => `Dejarás de ver ${grupo} y se cortan los enlaces de relevo que compartiste.`, // [NUEVO]
  boton: 'Salir del grupo', // [ANALISTA]
  pregunta: (grupo: string) => `¿Salir de ${grupo}?`, // [ANALISTA]
  dejarasDeVerlo: 'Dejarás de verlo ahora.', // [ANALISTA]
  seCortan: 'Se cortan los enlaces de relevo que compartiste.', // [ANALISTA]
  // «Hoy abren {n}.» es GRUPO_FAMILIAR.hoyAbren [L 22].
  /** 5.10: sin persona registrada no hay ficha, y el punto no aparece (lo decide la pantalla). [NUEVO] */
  fichaQueda: (pilas: readonly string[]) => `Lo que escribiste en la ficha queda, porque es parte del cuidado de ${pilasO(pilas)}.`, // [NUEVO]
  paraVolver: 'Para volver, alguien que administra el grupo tiene que invitarte de nuevo.', // [NUEVO]
  quedarme: 'Quedarme', // [ANALISTA]
  /** 7.2 (v1.3): bajo la lista, para todos los roles. El correo va como texto, sin enlace. [NUEVO v1.3] */
  pideloA: (capa3: boolean) =>
    capa3
      ? `Si después necesitas lo que hiciste en el grupo o los comprobantes de tus pagos, pídelos a ${CORREO_CONTACTO}.`
      : `Si después necesitas lo que hiciste en el grupo, pídelo a ${CORREO_CONTACTO}.`,
  ocupado: 'Saliendo del grupo…', // [NUEVO]
  hecho: (grupo: string, n: number) => [`Saliste de ${grupo}.`, cortamos(n)].filter(Boolean).join(' '), // [NUEVO]
  errRed: 'No pudimos sacarte del grupo. Revisa tu conexión y vuelve a intentarlo. Sigues en el grupo.', // [NUEVO]
  unicoAdmin: (grupo: string) => `Eres la única persona que administra ${grupo}. Para salir, primero da ese rol a otra persona.`, // [NUEVO]
  /** 7.3; sin persona registrada (5.10, v1.2), solo la primera oración. [NUEVO] */
  unicaPersona: (grupo: string, pilas: readonly string[]) =>
    pilas.length
      ? `Eres la única persona de ${grupo}, así que no puedes salir. Si ya no usan MATU para cuidar a ${unirNombres(pilas)}, puedes borrar sus datos en «Borrar sus datos», más arriba.`
      : `Eres la única persona de ${grupo}, así que no puedes salir.`,
}

// ---------------------------------------------------------------- 0.6 (v1.3) quien deja de administrar

/** O4: el backend anula sus invitaciones sin usar (decisión 322). Genérico: la API no dice cuántas. [NUEVO v1.3] */
export const INVITACIONES_SE_ANULAN = {
  otra: 'Si creó invitaciones que nadie ha usado, se anulan.',
  propia: 'Si creaste invitaciones que nadie ha usado, se anulan.',
}

// ---------------------------------------------------------------- 3 Invitar

export const INVITAR = {
  titulo: 'Invitar a alguien al grupo', // [NUEVO, del esquema de 3.2]
  bajada: 'Le mandas un enlace desde tu teléfono y le dictas un código aparte. No guardamos su correo ni su teléfono.', // [NUEVO]
  leyenda: '¿Qué podrá hacer?', // [ANALISTA]
  sinRol: 'Elige qué podrá hacer.', // [NUEVO]
  avisoAdmin: 'Podrá invitar, cambiar permisos y sacar a otras personas, también a ti.', // [ANALISTA]
  /** Con una persona, la frase del analista; con varias, en plural. [ANALISTA; plural NUEVO] */
  cuentale: (pilas: readonly string[]) =>
    pilas.length > 1
      ? `Si ${unirNombres(pilas)} pueden comprenderlo, cuéntales que invitaste a otra persona.`
      : `Si ${pilas[0]} puede comprenderlo, cuéntale que invitaste a otra persona.`,
  vale: 'Vale 7 días y sirve una sola vez.', // [NUEVO]
  crear: 'Crear la invitación', // [ANALISTA]
  creando: 'Creando la invitación…', // [NUEVO]
  vistaPrevia: 'Lo que verá al abrir el enlace', // [NUEVO]
  errRed: 'No pudimos crear la invitación. Revisa tu conexión y vuelve a intentarlo.', // [NUEVO]
  tope: 'Ya creaste muchas invitaciones hoy. Vuelve a intentarlo mañana.', // [NUEVO]
  yaNoAdministras: 'Ya no administras el grupo, así que no puedes invitar.', // [NUEVO]

  // 3.4 a 3.6
  lista: 'Invitación lista', // [ANALISTA]
  valeHasta: ['Vale una sola vez, hasta el', 'a las'] as const, // [ANALISTA]
  para: (rol: Rol) => `Para ${ROL_INFINITIVO[rol]}.`, // [NUEVO]
  codigoTitulo: 'Código para unirse', // [NUEVO]
  codigoAria: (codigo: string) => `Código: ${codigo.split('').join(' ')}`,
  dictaselo: ['Díselo por teléfono, no lo escribas en el mensaje.', ' No lo volverás a ver.'] as const, // [ANALISTA]
  repetir: 'Repetir el código', // [NUEVO]
  enviar: 'Enviar el enlace', // [ANALISTA]
  copiar: 'Copiar el enlace', // [ANALISTA]
  mensaje: (url: string) => `Te invito a mi grupo de cuidado en MATU. Abre este enlace para unirte. El código te lo digo por teléfono. ${url}`, // [ANALISTA]
  copiado: 'Enlace copiado. Pégalo en tu mensaje.', // [NUEVO]
  noCopiado: 'No pudimos copiar el enlace. Usa «Enviar el enlace».', // [L 9.1]
  enlaceDeLaInvitacion: 'Enlace de la invitación', // [NUEVO]
  perdidoTitulo: 'El código ya no se puede ver', // [NUEVO]
  perdido: 'Por seguridad se muestra una sola vez. Si se perdió, anula la invitación desde Grupo familiar y crea una nueva.', // [NUEVO]
}

/** 4.2: «Carmen te invita a su grupo de cuidado en MATU, para cuidar.» [ANALISTA, con el infinitivo NUEVO] */
export const teInvita = (nombre: string, rol: Rol | null) =>
  rol ? `${nombre} te invita a su grupo de cuidado en MATU, para ${ROL_INFINITIVO[rol]}.` : `${nombre} te invita a su grupo de cuidado en MATU, para el rol que elijas.` // [NUEVO, sin rol]

// ---------------------------------------------------------------- 4 /invitacion

export const INVITACION = {
  rotulo: 'Invitación a un grupo de cuidado', // [NUEVO]
  tituloPestana: 'Invitación a un grupo de cuidado', // [NUEVO] «… · MATU»
  abriendo: 'Abriendo la invitación…', // [NUEVO]
  escribeElCodigo: 'Escribe el código que te dijo.', // [ANALISTA]
  codigo: 'Código', // [NUEVO]
  seguir: 'Seguir', // [ANALISTA]
  revisando: 'Revisando el código…', // [NUEVO]
  valeHasta: ['Vale hasta el', 'a las'] as const, // [ANALISTA]
  codigoCorto: 'El código tiene 4 números. Revisa que estén todos.', // [NUEVO, como el PIN de L 7.3]
  noEs: 'Ese código no es.', // [ANALISTA]
  quedan: (n: number) =>
    n === 1 ? ' Te queda 1 intento. Después, la invitación se bloquea.' : ` Te quedan ${n} intentos. Después, la invitación se bloquea.`, // [ANALISTA, ajustado] y [NUEVO, singular]

  // 4.4
  cuentaTitulo: 'Para unirte, crea tu cuenta o entra con la que tienes.', // [ANALISTA]
  cuentaTexto: 'Te trae de vuelta aquí para terminar de unirte.', // [NUEVO]
  crearCuenta: 'Crear mi cuenta', // [NUEVO]
  entrar: 'Entrar con mi cuenta', // [NUEVO]
  vuelves: (nombre: string) => `Después de esto vuelves a la invitación de ${nombre}.`, // [NUEVO]

  // 4.5
  teUnes: (grupo: string, pilas: readonly string[]) =>
    pilas.length ? `Te unes a ${grupo}. Cuidan a ${unirNombres(pilas)}.` : `Te unes a ${grupo}. Todavía no registran a la persona que cuidan.`, // [ANALISTA] y [NUEVO]
  tuRol: (rol: Rol) => `Tu rol: ${ROL[rol]}.`, // [ANALISTA, ajustado]
  verasNombre: 'Las personas del grupo verán tu nombre. No verán tu correo ni tu celular.', // [ANALISTA]
  confidencial: (pilas: readonly string[]) => `Lo que veas sobre ${pilasO(pilas)} es para su cuidado. No lo compartas fuera del grupo.`, // [ANALISTA]
  teUnesComo: (nombre: string) => `Te unes como ${nombre}.`, // [NUEVO]
  unirme: 'Unirme al grupo', // [ANALISTA]
  uniendo: 'Uniéndote al grupo…', // [NUEVO]
  noQuiero: 'No quiero unirme', // [ANALISTA]
  noTeUniste: 'No te uniste al grupo', // [NUEVO]
  siCambias: 'Si cambias de opinión, vuelve a abrir el enlace antes del', // [NUEVO] «… {fecha}.»
  irAMatu: 'Ir a MATU', // [NUEVO]

  // 4.6
  yaEresParteDe: (grupo: string) => `Ya eres parte de ${grupo}.`, // [ANALISTA]

  // 4.7 y 4.8
  queHago: '¿Qué hago?', // [L 7.2]
  pideOtra: 'Pídele una nueva a quien te invitó.', // [ANALISTA]
  pideleA: (nombre: string) => `Pídele a ${nombre} una nueva.`, // [ANALISTA, partido]
  vencida: { titulo: 'Esta invitación venció', texto: 'Las invitaciones duran 7 días, y esta ya terminó.' }, // [NUEVO]
  usada: { titulo: 'Esta invitación ya se usó', texto: 'Cada invitación sirve una sola vez.' }, // [NUEVO]
  noDisponible: {
    titulo: 'Esta invitación no está disponible', // [NUEVO]
    texto: 'Puede que se haya copiado incompleta o que ya no exista. Revisa que la abriste completa desde el mensaje.', // [NUEVO, como L 7.3]
  },
  bloqueada: { titulo: 'Esta invitación se bloqueó', texto: 'El código se escribió mal cinco veces. Por seguridad, ya no sirve.' }, // [NUEVO]
  yaEresParte: 'Ya eres parte de este grupo', // [ANALISTA]
  espera: {
    titulo: 'Espera un momento', // [L 7.3]
    texto: (m: number) => `Hubo muchos intentos desde esta conexión. Vuelve a intentarlo en ${m === 1 ? '1 minuto' : `${m} minutos`}.`, // [L 7.3, sin «de entrar»]
  },
  red: { titulo: 'No pudimos completar esto.', texto: 'Revisa tu conexión y vuelve a intentarlo.' }, // [L 8]
  volverAIntentar: 'Volver a intentar', // [L 26]
  sinToken: { titulo: 'Vuelve a abrir el enlace', texto: 'Vuelve a abrir el enlace que te enviaron.' }, // [L 7.3] y [ANALISTA]
}

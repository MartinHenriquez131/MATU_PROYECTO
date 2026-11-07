// Grupo familiar, retirar una autorización y volver a autorizar (MATU-44, especificación
// docs/diseno/matu-44-retirar-autorizacion.md v1.1). Todos de lenguaje.md, sección 22, aprobados por
// Jorge el 06-11, tal cual. En la interfaz se dice «autorización», «permiso» y «retirar», nunca
// «consentimiento» ni «revocar». Las fechas y los números los da la API.

export const GRUPO_FAMILIAR = {
  titulo: 'Grupo familiar',
  corto: 'Grupo',
  bajada: (grupo: string) => `A quién cuidan en ${grupo} y qué permisos dieron.`,

  // 3.3 y 3.4: los dos bloques
  tituloFicha: 'Permiso para guardar su ficha',
  tituloInsumos: 'Permiso para calcular sus insumos',
  autorizadaFicha: 'Autorizada el',
  autorizadoInsumos: 'Autorizado el',
  renovarFicha: 'Hay que renovarla desde el',
  renovarInsumos: 'Hay que renovarlo desde el',
  sinAutorizar: 'Sin permiso todavía. Se pide al anotar el primer insumo.',
  retiradaEl: 'Autorización retirada el',
  siNoVuelves: 'Si no vuelves a autorizar, lo guardado se borra el',
  siNadieVuelve: 'Si nadie vuelve a autorizar, lo guardado se borra el',
  /** 3.4: con `borrado_en` en `null` en `retirada` (no debería pasar). */
  siNoVuelvesSinFecha: 'Si no vuelves a autorizar en 90 días, lo guardado se borra.',
  seBorro: 'Lo guardado se borró el',

  retirar: 'Retirar la autorización',
  volverAAutorizar: 'Volver a autorizar',
  retirarFichaDe: (pila: string) => `Retirar la autorización de la ficha de ${pila}`,
  retirarInsumosDe: (pila: string) => `Retirar la autorización de los insumos de ${pila}`,
  volverFichaDe: (pila: string) => `Volver a autorizar la ficha de ${pila}`,
  volverInsumosDe: (pila: string) => `Volver a autorizar los insumos de ${pila}`,

  // 3.6: pagador y observador
  puedeRetirarla: (pila: string) => `Puede retirarla quien administra el grupo o quien cuida a ${pila}.`,
  puedeVolverAAutorizarla: (pila: string) => `Puede volver a autorizarla quien administra el grupo o quien cuida a ${pila}.`,

  // 3.7
  cargando: 'Cargando…',
  errCargar: 'No pudimos traer los permisos. Revisa tu conexión e inténtalo de nuevo.',
  intentar: 'Intentar de nuevo',

  // 4: la confirmación
  preguntaFicha: (pila: string) => `¿Retirar la autorización de la ficha de ${pila}?`,
  preguntaInsumos: (pila: string) => `¿Retirar la autorización de los insumos de ${pila}?`,
  fichaNadie: 'Nadie del grupo podrá ver ni cambiar su ficha.',
  fichaSeCortan: 'Se cortan ahora todos sus enlaces de relevo.',
  hoyAbren: (n: number) => (n === 0 ? 'Hoy ningún enlace abre.' : n === 1 ? 'Hoy abre 1.' : `Hoy abren ${n}.`),
  hoyEnPausa: (n: number) => (n === 0 ? 'Hoy ningún enlace abre.' : n === 1 ? 'Hoy está en pausa 1.' : `Hoy están en pausa ${n}.`),
  fichaAbierta: 'Si alguien tiene la ficha abierta, se le cierra cuando vuelva a mirarla. No recibe aviso.',
  fichaNoVuelve: 'Un enlace cortado no vuelve a abrir, aunque autorices de nuevo.',
  fichaGuardado: 'Lo escrito queda guardado sin que nadie lo vea. Si no vuelves a autorizar en 90 días, se borra.',
  fichaInsumosNoCambia: 'La autorización de los insumos no cambia.',
  insumosDejamos: 'Dejamos de calcular cuándo se acaban y de avisar, desde ahora. Tampoco avisamos al resto del grupo.',
  insumosNadie: 'Nadie del grupo podrá ver los insumos anotados.',
  insumosGuardado: 'Lo anotado queda guardado sin que nadie lo vea. Si no vuelves a autorizar en 90 días, se borra.',
  insumosLista: 'Una lista que ya imprimiste o compartiste no se borra: quedó fuera de MATU.',
  insumosFichaNoCambia: 'Su ficha y los enlaces de relevo no cambian.',
  noRetirar: 'No retirar',
  retirando: 'Retirando…',
  errRetirar: 'No pudimos retirar la autorización. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.',

  // 3.5: después de retirar
  retiradaFicha: (n: number) =>
    n === 0 ? 'Autorización retirada. No había enlaces que abrieran.' : n === 1 ? 'Autorización retirada. Cortamos 1 enlace.' : `Autorización retirada. Cortamos ${n} enlaces.`,
  retiradaInsumos: (pila: string) => `Autorización retirada. Ya no calculamos ni avisamos por los insumos de ${pila}.`,
  yaRetirada: 'Otra persona de tu grupo ya retiró esta autorización.',

  // 5: volver a autorizar
  volverAGrupo: 'Volver a Grupo familiar',
  fichaVuelve: 'Al autorizar de nuevo, vuelve lo que estaba escrito. Los enlaces que se cortaron no vuelven a abrir.',
  // Con una fecha: [antes, lo que va pegado a la fecha dentro de su `cifras`, después] (3.4, revisión del 07-11).
  fichaSeBorro: ['Lo escrito antes se borró el ', '.', ' La ficha empieza en blanco.'] as const,
  fichaBoton: 'Acepto y vuelvo a autorizar',
  fichaEnviando: 'Autorizando…',
  insumosVuelve: ['Si vuelves a dar el permiso antes del ', ',', ' vuelve lo que estaba anotado.'] as const,
  insumosSeBorro: ['Lo anotado antes se borró el ', '.', ' Hay que anotar los insumos de nuevo.'] as const,
  errAutorizar: 'No pudimos guardar la autorización. Revisa lo que elegiste y vuelve a intentarlo.',
  yaAutorizada: 'Otra persona de tu grupo ya volvió a autorizar.',
  registradaFicha: (pila: string) => `Autorización registrada. Ya puedes ver y cambiar la ficha de ${pila}.`,
  registradaFichaEnBlanco: (pila: string) => `Autorización registrada. La ficha de ${pila} empieza en blanco.`,
  guardadoInsumos: 'Permiso guardado. Volvió lo que estaba anotado.',
  guardadoInsumosEnBlanco: 'Permiso guardado. Ahora anota el primer insumo.',

  // 4.5 y lenguaje 6.4: la ficha sin autorización, para admin y cuidador
  fichaPuedesVolver: 'La puedes volver a autorizar desde Grupo familiar.',

  // 4.5: Enlaces con la autorización retirada
  enlacesRetiradaTitulo: 'Se retiró la autorización de la ficha.',
  enlacesRetirada: 'Los enlaces se cortaron y no vuelven a abrir.',
  verPermisos: 'Ver los permisos en Grupo familiar',
}

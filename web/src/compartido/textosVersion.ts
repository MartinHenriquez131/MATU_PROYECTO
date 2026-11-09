// MATU-67: los textos del aviso de versión nueva (especificación, sección 6), los mismos en la app
// de la familia y en el relevo. Aprobados por Jorge el 09-11; van a docs/lenguaje.md, sección 28,
// «Aviso de versión nueva (MATU-67)». En el relevo se mantiene «Actualizar» (lenguaje 7.4), que es
// otra acción: trae la ficha al día. «Recargar» trae la versión nueva de la página.
export const AVISO_VERSION = {
  titulo: 'Hay una versión nueva de MATU.',
  bajadaFamilia: 'Recarga cuando termines lo que estás haciendo.',
  bajadaRelevo: 'Recarga cuando termines de leer.',
  recargar: 'Recargar',
  recargando: 'Recargando…',
  masTarde: 'Más tarde',
  sinGuardarEn: (donde: string) => `Lo que escribiste en «${donde}» no se guardó.`,
  sinGuardar: 'Hay algo que escribiste y no se guardó.',
  /** Insumos (revisión visual del 09-11, aprobado por Jorge): solo el nombre del insumo. */
  sinGuardarInsumo: (nombre: string) => `Lo que anotaste de «${nombre}» no se guardó.`,
  sinGuardarBajada: 'Si recargas ahora, se pierde.',
  seguirEscribiendo: 'Seguir escribiendo',
  recargarIgual: 'Recargar igual',
} as const

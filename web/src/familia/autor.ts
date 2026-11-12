// Quién hizo algo, en la ficha, las secciones y los enlaces (MATU-42, decisiones 309 y 323; diseño
// MATU-53, 5.7). Quien ya no está en el grupo llega con `nombre: null` y `autor_activo: false`, igual
// en todas las rutas, y la pantalla escribe «Alguien que ya no está en el grupo» con el mismo estilo
// de un nombre. En los 412 se sigue leyendo «Otra persona» (decisión 323): ahí no se usa esto.
import { YA_NO_ESTA } from './textosInvitar'

interface Autor {
  nombre: string | null
  autor_activo?: boolean
}

/** El nombre para mostrar, o `null` si no hay autor. `inicio`: la frase empieza con el nombre. */
export function nombreDeAutor(autor: Autor | null | undefined, { inicio = false }: { inicio?: boolean } = {}): string | null {
  if (!autor) return null
  if (autor.autor_activo === false || !autor.nombre?.trim()) return inicio ? YA_NO_ESTA.inicio : YA_NO_ESTA.medio
  return autor.nombre
}

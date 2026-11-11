// H3 del 09-11 (opción B de Jorge): a 320 px con el texto al 200 %, «+56 9 •••• ••37» se repartía
// por cualquier espacio. Solo en la pantalla, sin tocar la API: «+56 9» y «•••• ••37» van cada uno
// junto, con un espacio duro (U+00A0) dentro, y la línea solo puede cortarse entre los dos bloques.
// Como `cantidad` y `enPantalla` de textosInsumos.ts. Nunca `whitespace-nowrap` en el número entero.

const ENMASCARADO = /^(\+\d{1,3}) (\d) (•+) (•+\d+)$/

/**
 * «+56 9 •••• ••37» de `GET /v1/cuenta` → «+56 9 •••• ••37». Si el texto no tiene esa
 * forma, vuelve tal cual: la pantalla nunca inventa ni esconde parte del número.
 */
export function celularEnPantalla(enmascarado: string): string {
  const m = ENMASCARADO.exec(enmascarado)
  if (!m) return enmascarado
  const [, pais, prefijo, puntos, final] = m
  return `${pais} ${prefijo} ${puntos} ${final}`
}

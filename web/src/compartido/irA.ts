// MATU-63 (especificación 2.1 y O1): la app de la familia y la del comercio son dos raíces distintas
// de main.tsx, así que pasar de una a la otra recarga la página. La entrada vive solo en memoria y
// se recupera con la cookie del refresh al abrir. Un módulo propio para que las pruebas lo reemplacen.
// MATU-81: también la consola de operación, otra raíz, y su entrada (la cuenta de operación que entró por
// otra puerta: nunca lleva el desafío ni la contraseña).
export function irA(ruta: '/comercio' | '/operacion' | '/operacion/entrar' | '/entrar', { reemplazar = false }: { reemplazar?: boolean } = {}) {
  if (reemplazar) window.location.replace(ruta)
  else window.location.assign(ruta)
}

// MATU-63 (especificación 2.1 y O1): la app de la familia y la del comercio son dos raíces distintas
// de main.tsx, así que pasar de una a la otra recarga la página. La entrada vive solo en memoria y
// se recupera con la cookie del refresh al abrir. Un módulo propio para que las pruebas lo reemplacen.
export function irA(ruta: '/comercio' | '/entrar', { reemplazar = false }: { reemplazar?: boolean } = {}) {
  if (reemplazar) window.location.replace(ruta)
  else window.location.assign(ruta)
}

# MATU-103 · El velo de los diálogos oscurece en los dos temas · Especificación de diseño

**Versión 1.0 · 17/11/2026** · Agente 6, UI/UX. Especifica y no construye. El token y su justificación están en `Demo/DISENO.md`, sección 1 («El velo de los diálogos»), y en `web/src/index.css`.

## 1. Objetivo

Cuando se abre un diálogo, Carmen ve que la página de atrás queda **en penumbra** y que lo que importa es el diálogo, con el teléfono en tema claro o en oscuro.

## 2. El token

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `velo` | `rgb(4 12 14 / 0.45)` | `rgb(4 12 14 / 0.6)` | `backdrop:bg-velo`, **sin** `/NN` |

Medido sobre la página (`papel`):

| | Hoy (`tinta/40`) | Con `velo` |
|---|---|---|
| Claro, página velada | `#95A1A2` (oscurece) | `#848B8B` (oscurece) |
| Oscuro, página velada | `#636D6D` (**aclara**) | `#081012` (oscurece) |
| Claro, diálogo `hoja` sobre la página velada | 2,7:1 | 3,5:1 |
| Oscuro, diálogo `hoja` sobre la página velada | 3,0:1, pero por aclarar | 1,2:1, con el borde `ring-linea` |

## 3. Dónde se aplica

Los cinco `<dialog>` modales que hay hoy en `web/src` (`grep -rn "backdrop:" web/src`). En cada uno, **`backdrop:bg-tinta/40` pasa a `backdrop:bg-velo`, y se agrega `ring-1 ring-linea`** a la clase del `<dialog>`. Nada más cambia.

| Archivo y línea (7fceca1) | Componente | Tarjeta | Dónde se ve |
|---|---|---|---|
| `web/src/familia/PiezasInvitar.tsx:109` | `DialogoGrupo` | MATU-44 (patrón 4.1) y MATU-53 | «Miembros»: quitar a alguien o cancelar una invitación (`Miembros.tsx`) |
| `web/src/familia/Grupo.tsx:621` | `DialogoRetirar` | MATU-44 | «Grupo familiar»: retirar una autorización |
| `web/src/familia/Grupo.tsx:833` | `DialogoBorrar` | MATU-72 | «Grupo familiar»: borrar los datos de la persona cuidada |
| `web/src/familia/DialogoConfirmar.tsx:106` | `DialogoConfirmar` (y `DialogoPedido`) | MATU-61, MATU-55, MATU-54, MATU-92 | Cancelar el pedido y vaciar la dirección; «Cerrar en ese teléfono» (`DondeEntraste`); «Mis datos» (`PiezasMisDatos`); «Tus pedidos» (`TusPedidos`) |
| `web/src/familia/Insumos.tsx:2214` | `DialogoEliminar` | MATU-36 | «Insumos»: dejar de seguir un insumo |

Todo `<dialog>` modal nuevo usa las mismas dos clases. No hay diálogos en `relevo/`, `comercio/` ni `privacidad/` hoy. Si un componente nuevo usa `backdrop:` con otro color, es un hallazgo.

## 4. Criterios verificables

1. `grep -rn "backdrop:" web/src` devuelve solo `backdrop:bg-velo`, cinco veces. Ningún `backdrop:bg-tinta`.
2. En tema oscuro, con un diálogo abierto, la página detrás se ve **más oscura** que sin diálogo (captura a 360 px y a 1280 px, antes y después).
3. En tema claro, la página detrás se ve un poco más oscura que hoy, y el diálogo blanco se separa con claridad.
4. En tema oscuro, el contorno del diálogo se distingue sobre la página velada.
5. Con `prefers-reduced-motion`, el velo aparece de inmediato (hoy no tiene animación y sigue sin tenerla).
6. `web/pruebas/coloresRepetidos.test.ts` sigue en verde: `velo` está igual en `:root[data-tema='oscuro']` y en `prefers-color-scheme: dark`.

## 5. Estados

No cambian: los diálogos conservan su foco inicial, su error y su «en curso». Solo cambia el fondo de atrás y el contorno.

# MATU-121 · El ícono de la `Nota` va en línea en el modo angosto

**Versión 2 · 18/11/2026** · diseñador (agente 6). La versión 2 sale de la revisión visual del commit 1e2e2dd: corrige el criterio 3 de la sección 6 y suma la sección 8, el chevron de `Volver` en el modo angosto. Esta tarea sale del P3 de la revisión visual de MATU-114. A 320 px con el texto al 200 %, las notas partían palabras a la mitad: «correspon⏎den.», «60 minuto⏎s» y «01/11/202⏎6.». La regla corta queda en `Demo/DISENO.md`, sección 6 (fila «Nota»). Este documento trae el detalle y las mediciones.

## 1. Objetivo

Con el texto al 200 % en un teléfono angosto, Carmen tiene que poder leer cada aviso completo, sin palabras ni cifras partidas.

## 2. Qué cambia

En el modo `angosto` (la app mide menos de 16 rem), **el ícono de toda `Nota` va en línea por omisión.** El cambio es uno solo, en `web/src/compartido/ui/Nota.tsx`: `iconoEnLinea` pasa a valer `true` por omisión.

**Fuera del modo `angosto`, nada cambia:**
- a 360, 1280 y 1920 px con el texto normal, toda clase nueva lleva el prefijo `angosto:`;
- las capturas de esos anchos deben quedar idénticas a las de antes.

**Por qué conviene.** Con el ícono en su columna, el texto de la nota pierde unos 70 px de los ~220 px que tiene a 320 px con el texto al 200 %, y entonces `break-words` corta las palabras. Lo medí en una maqueta con las clases de la app:

| Nota de ejemplo (409 del retracto, «…venció el 01/11/2026.») | Alto | ¿Parte palabras? |
|---|---|---|
| Ícono en su columna (como está hoy) | 438 px | Sí: «01/11/202⏎6.» |
| Ícono en línea | 327 px | No |

Los 27 usos que ya llevan `iconoEnLinea` no cambian. Se puede dejar la propiedad escrita o quitarla, porque ahora es el valor por omisión.

## 3. Las tres preguntas del frontend

### 3.1 ¿Aplica a todos los tonos y a las notas con `borde`?

**Sí, a los cuatro tonos (`rocio`, `atenta`, `pronto` y `ok`) y también con `borde`.**
- El ícono es la forma que acompaña al tono, para que el estado no dependa solo del color. Ponerlo en línea no lo quita: sigue al comienzo de la nota, con el mismo dibujo y el mismo color.
- La línea izquierda de `borde`, de 4 px, es una señal aparte y se mantiene igual.
- Es el mismo patrón ya aprobado en `MensajeError` (revisión del #51) y en los avisos con `iconoEnLinea` de MATU-44, 54, 55, 59, 67 y 107, que ya incluían notas `atenta` y `rocio` con `borde`.

### 3.2 ¿Qué pasa con los íconos de 24 px (`size-6`)?

**En línea, todo ícono mide `size-5` (1,25 rem) y no lleva margen superior, venga como venga.**

Algunas pantallas le pasan a la nota un ícono de `size-6` con `mt-0.5`: `ShieldAlert` y `ShieldQuestion` en `Ficha.tsx:114`, y `ShieldAlert` en `Compartir.tsx:748`. `Pago.tsx:943` ya usa `CreditCard` en `size-5`. Lo resuelve el componente, no cada pantalla. Al envoltorio en línea se le agregan:

```
angosto:[&>svg]:size-5 angosto:[&>svg]:mt-0
```

Esto le gana a las clases `size-6 mt-0.5` del ícono que pasa la pantalla, porque el selector `envoltorio > svg` es más específico. En la columna, fuera del modo `angosto`, el ícono de 24 px se queda como está: ahí marca un aviso grande.

**Por qué.**
- Con 24 px en línea, la primera línea crece 2 px (327 contra 329 px en la maqueta) y el ícono queda más alto que las letras.
- En línea, el aviso grande ya se distingue por su `borde`.
- `size-5` es el tamaño de `ICONO_NOTA` y de `MensajeError`, así que no se crea ningún token nuevo.

### 3.3 ¿Qué pasa con las notas cuyo cuerpo empieza con un botón o un enlace?

**Con título, no pasa nada.** `EditorSeccion.tsx:358` y `Ficha.tsx:560` tienen título, así que el ícono va en la línea del título, «Tienes cambios sin guardar…», y las `Acciones` siguen debajo, sin cambios.

**Sin título y empezando con un control, el ícono se queda en su columna.** Hay un solo caso en `web/src`: `Alta.tsx:775`, con `<Volver>`. Esa nota lleva `iconoEnLinea={false}` explícito.
- Si el ícono flota o va en línea, queda solo, encima del botón (maqueta: 321 px de alto).
- En la columna, queda al lado (272 px).
- `Volver` es `inline-flex min-h-12` y además trae su propio `ChevronLeft`: dos íconos seguidos en la misma línea se leerían mal.

**Un caso que las preguntas no traían: notas sin título cuyo cuerpo empieza con un párrafo.** Son 20: `Pago.tsx` (392, 440, 445, 477, 608, 613, 671, 687, 794 y 943), `TusPedidos.tsx` (664, 668, 674, 678 y 1236), `ListaInsumos.tsx` (448 y 472), `Resumen.tsx` (405 y 418) y `TusDatos.tsx:85`.

Con el envoltorio en línea de hoy (`inline-flex` antes de los hijos), el ícono quedaría **solo en una línea, encima del primer `<p>`**. En la maqueta, eso da 455 px de alto, con el ícono aislado.

Por eso, **sin título, el ícono flota al comienzo del texto** en vez de ir en línea:
- con texto suelto se ve igual que en línea (327 px en los dos casos);
- con párrafos se pone al lado de la primera línea del primero (400 px).

Con título se mantiene el `inline-flex` ya aprobado.

## 4. Clases exactas

Todas con el prefijo `angosto:`, para que fuera de ese modo no cambie nada.

| Pieza | Hoy | MATU-121 |
|---|---|---|
| Valor por omisión de la propiedad | `iconoEnLinea = false` | `iconoEnLinea = true` |
| Ícono en la columna | `<span className="contents angosto:hidden">` | Sin cambios |
| Ícono en la línea del título | `hidden angosto:me-1.5 angosto:inline-flex angosto:align-middle` | Lo mismo, más `angosto:[&>svg]:size-5 angosto:[&>svg]:mt-0` |
| Ícono sin título, al comienzo del cuerpo | `hidden angosto:me-1.5 angosto:inline-flex angosto:align-middle` | `hidden angosto:block angosto:float-start angosto:me-1.5 angosto:mt-0.75 angosto:leading-none angosto:[&>svg]:size-5 angosto:[&>svg]:mt-0` |
| El `div` del cuerpo (`text-base leading-relaxed`) | Sin cambios | Más `angosto:flow-root`, para que la nota contenga al ícono flotante si el texto es más corto que él |

- **El margen `mt-0.75`** mide 0,1875 rem: centra un ícono de 1,25 rem en la línea de `leading-relaxed` (1,625 rem). Es la escala de espaciado de Tailwind, `var(--spacing)` × 0,75. Si la versión instalada no genera `mt-0.75`, se usa `mt-[calc(var(--spacing)*0.75)]`, que es el mismo valor. No es un número escrito a mano.
- **En el título no se toca la alineación:** `align-middle` con `size-5` ya está aprobado en MATU-44.

## 5. Estados

La nota no tiene estados propios: ni presionado, ni deshabilitado, ni cargando.
- Con `enfocable`, el foco programado no cambia, y sigue sin anillo porque no es un control (MATU-44 3.5).
- Los anuncios (`rol`) no cambian: el ícono sigue con `aria-hidden`.

## 6. Criterios visuales verificables

Con capturas en claro y en oscuro, a 320 px con el texto al 200 % y a 360, 1280 y 1920 px:

1. **Ninguna palabra, cifra ni fecha partida a la mitad** a 320 px con el texto al 200 %. Se mira por lo menos en:
   - el 409 del retracto por correo («01/11/2026.»);
   - el 429 («60 minutos», «corresponden.»);
   - `Pago.tsx:943`;
   - `TusPedidos.tsx:664`;
   - una nota `pronto` de red.

   Un correo o una palabra que mida más que el ancho de la nota se puede seguir partiendo: eso lo hace `break-words` a propósito.
2. **El ícono nunca queda solo en una línea**, con o sin título, con texto o con párrafos. El único caso en columna es `Alta.tsx:775`.
3. **El ícono en línea mide 1,25 rem** (21,25 px, o 42,5 px con el texto al 200 %), también en `Ficha.tsx:114` y `Compartir.tsx:748`. Su centro está a ±2 px del centro de la primera línea de texto con el texto normal, y a ±3 px con el texto al 200 %. **(v2)** El ±2 px de la versión 1 no tomaba en cuenta la escala. En la revisión, el `inline-flex align-middle` del título, ya aprobado en MATU-44, quedó a 2,6 px con el texto al 200 %, que equivale a 1,3 px con el texto normal, y no se nota.
4. **Ningún desplazamiento horizontal** a 320 px con el texto al 200 %.
5. **A 360, 1280 y 1920 px sin zoom, las notas son idénticas a las de `main`:** el ícono en su columna y de su tamaño de siempre, también los de 24 px.
6. **El estado no depende del color:** cada nota sigue mostrando el ícono de su tono, y la línea de 4 px si lleva `borde`.

## 7. Lo que no cambia

- `MensajeError`, que ya lleva su ícono en línea. Hay una sola `Nota`, la de `compartido/ui/Nota.tsx`; `familia/ui.tsx` solo la vuelve a exportar, así que el cambio llega a la app de la familia, al relevo, a la consola de operación y a la del comercio.
- Los textos: ninguno cambia.

## 8. (v2) El chevron de `Volver` va en línea en el modo angosto

**De dónde sale.** Es el P3 de la revisión del commit 1e2e2dd, y se resuelve en esta misma tarjeta.

En `Alta.tsx:775` (falla `paso1`), a 320 px con el texto al 200 %, coinciden dos cosas:
- la nota lleva `iconoEnLinea={false}` y su ícono va en columna;
- `Volver` es `inline-flex items-center`, con el `ChevronLeft` en su propia columna y centrado en la altura del botón.

Entre los dos, el texto «Volver a corregir los datos de María» queda en unos 125 px: una palabra por línea y 438 px de alto, con el chevron flotando a media altura (`capturas114/r121/alta-320-200-claro-nota1.png`).

**Objetivo.** Con el texto al 200 %, Carmen lee de corrido adónde la lleva el botón, y ve la flecha al comienzo de la frase, como en un enlace.

**Regla.** Funciona como en `MensajeError`:
- en el modo `angosto`, el botón deja de ser `flex` y pasa a `inline-block`, para que su texto corra en líneas;
- el chevron va en línea, como una letra más, al comienzo de la primera línea.

Fuera del modo `angosto` nada cambia. Esto vale para los 26 usos de `Volver` en `web/src`.

### Clases exactas (`web/src/familia/ui.tsx`, `Volver`)

| Pieza | Hoy | MATU-121 v2 |
|---|---|---|
| `button` | `inline-flex min-h-12 items-center gap-1 self-start rounded-lg pr-2 text-left font-bold text-turquesa hover:underline` | Lo mismo, más `angosto:inline-block` |
| `ChevronLeft` | `size-5 shrink-0` | `size-5 shrink-0 angosto:me-1 angosto:inline angosto:align-middle` |

- **El margen `angosto:me-1`** reemplaza al `gap-1` del `flex`, que deja de aplicar en el modo `angosto`. Es la misma separación de 0,25 rem.
- **El área táctil sigue en `min-h-12`.** Con el texto al 200 % cada línea ya mide 54 px, más que los 48 px pedidos.
- **El foco no cambia:** el contorno base rodea la caja del botón, de una o de varias líneas.
- **El subrayado de `hover:underline`** baja con el texto, línea por línea.
- **La nota de `Alta.tsx:775` mantiene `iconoEnLinea={false}`.** Con el chevron en línea, el texto del botón queda con unos 210 px, el ancho de la nota menos la columna del ícono, y la frase se lee en pocas líneas. Si el ícono de la nota también flotara, quedaría solo encima del botón (sección 3.3).

### Criterios visuales verificables

1. **A 320 px con el texto al 200 %**, en `Alta.tsx:775`, en claro y en oscuro:
   - el chevron está en la primera línea, junto a «Volver»;
   - su centro queda a ±3 px del centro de esa línea;
   - ninguna línea del botón lleva una sola palabra si la siguiente cabe;
   - no se parte ninguna palabra;
   - no hay desplazamiento horizontal.
2. **El mismo resultado en un `Volver` de encabezado**, por ejemplo «Volver a ¿A quién cuidas?» en el paso 4 del alta: el chevron en la primera línea y el texto de corrido.
3. **El botón mide 48 px de alto o más**, y muestra el contorno de foco base al llegar con el teclado.
4. **A 360, 1280 y 1920 px sin zoom, todo `Volver` es idéntico al de antes:** `inline-flex`, el chevron centrado y con la misma caja.

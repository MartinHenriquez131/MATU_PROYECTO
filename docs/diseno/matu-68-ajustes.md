# MATU-68 · Ajustes menores de la app de familia · Especificación de diseño

**Versión 1.0 · 08/11/2026** · Agente 6, UI/UX. Especifica y no construye.

**Historia:** dos ajustes que dejó la revisión de Martín de MATU-51. Las casillas de Insumos se ven chicas al lado de los botones, y «Ya lo resolví» queda casi pegado a los bordes de su botón a 320 px con el texto al 200 %.

**Fuentes:** `Demo/DISENO.md` (secciones 3 y 6, actualizadas en este mismo cambio), los tokens de `web/src/index.css` (sin agregar ninguno), la especificación de MATU-51 (3.8) y MATU-37 (el panel de «Ya lo resolví»), y el código de `web/src/familia/Insumos.tsx`, `web/src/familia/ui.tsx` y `web/src/compartido/ui/Boton.tsx`.

**No cambia:** textos, colores, tokens, el flujo, el bloque `@media print` ni el comentario de la sección 8.4 de `index.css`.

---

## 0. Las medidas, con la raíz de 17 px

| Clase | rem | Texto al 100 % | Texto al 200 % (raíz de 34 px) |
|---|---|---|---|
| `size-5` (hoy) | 1,25 | 21,25 px (Martín midió 21) | 42,5 px |
| `size-6` (propuesta) | 1,5 | 25,5 px | 51 px |
| `min-h-12` (la etiqueta) | 3 | 51 px | 102 px |
| `px-3` (botón en `angosto`) | 0,75 | 12,75 px | 25,5 px |
| `px-0.5` (hoy, «Ya lo resolví») | 0,125 | 2,1 px | 4,25 px |

---

## 1. Casillas de la app de familia

**Objetivo, desde Carmen:** «veo la casilla de un vistazo y sé si está marcada, aunque lea sin anteojos».

### 1.1 Decisión

**Se agrandan a `size-6` (1,5 rem, 25,5 px).** No es un token nuevo: es la misma medida que ya usan las casillas de Compartir (`Compartir.tsx`, «Avisarle a…») y de las secciones a compartir (`SeccionesCompartir.tsx`, «Incluir remedios»). Hoy la app tiene dos tamaños de casilla, y la regla queda en `DISENO.md`, sección 6 (fila «Casilla»): **una sola medida en toda la app.**

**Por qué `size-6` y no más:**
- El área que se toca no es la casilla sino su etiqueta, que ya mide `min-h-12` (51 px de alto) y abarca casilla, espacio y texto. Agrandar la casilla no cambia el área táctil: cambia lo que se ve.
- A 25,5 px el cuadro queda a la altura de una mayúscula y media del texto base y del ícono de 20 px de los botones vecinos: se lee como parte de la frase «Seguir», no como un control aparte.
- Una casilla nativa más grande (`size-7` u `size-8`) se dibuja con el borde y el check del navegador escalados, y empieza a competir con el botón principal. Para crecer más habría que dibujarla a mano, y eso es un componente nuevo que esta historia no pide.
- Con el texto al 200 % mide 51 px, porque está en rem.

**Por qué no un token:** `size-6` sale de la escala de espaciado de Tailwind, que ya es parte del sistema. Un token `--size-casilla` solo se justificaría si la casilla tuviera una medida fuera de la escala. Si más adelante se quiere un componente `Casilla`, la medida va dentro de él, no en un token.

### 1.2 Las dos casillas que cambian

| Dónde | Archivo y línea | Hoy | Cambia a |
|---|---|---|---|
| «Seguir» en cada fila de Insumos | `web/src/familia/Insumos.tsx`, el `<input type="checkbox">` dentro de la etiqueta de `seguir-{id}` | `size-5 shrink-0 accent-turquesa` | `size-6 shrink-0 accent-turquesa` |
| «Leí el aviso y lo acepto», del aviso de cuidador de hecho (la que aparece en la autorización de Insumos, y en el alta) | `web/src/familia/ui.tsx`, `AvisoCuidadorDeHecho` | `size-5 shrink-0 accent-turquesa` | `size-6 shrink-0 accent-turquesa` |

La segunda es la que llamamos «la del diálogo»: no está en un `<dialog>`, sino en la sección de autorización que se abre en Insumos (`Insumos.tsx`, `AvisoCuidadorDeHecho` con `idTitulo="aviso-consumo-t"`). Como el componente es compartido, el cambio también llega al alta (`Alta.tsx`), y es lo que se busca: una sola medida. Las dos etiquetas son de una línea y usan `items-center`, así que la casilla **no** lleva `mt-0.5` (ese margen es para las etiquetas de varias líneas con `items-start`, como las de Compartir).

Nada más cambia en las etiquetas: siguen con `min-h-12`, `gap-3`, `cursor-pointer` y `font-bold`.

### 1.3 Confirmación del área táctil

- **«Seguir»:** la etiqueta es `inline-flex min-h-12 items-center gap-3`. Alto: 51 px (102 px al 200 %). Ancho: 25,5 px de casilla, 12,75 px de espacio y el ancho de «Seguir» en negrita (unos 50 px), es decir unos 88 px. Toda la etiqueta marca la casilla porque el `<input>` está dentro del `<label>`. **Cumple 48 × 48.** Mientras guarda, el texto cambia a «Guardando…» y la etiqueta crece a unos 130 px; el botón «Cambiar» de al lado se corre. Es lo que pasa hoy y no se corrige en esta historia (P3, ver 4).
- **«Leí el aviso y lo acepto»:** la etiqueta es `flex` a todo el ancho de la sección con `min-h-12` y `py-3`. **Cumple 48 × 48.**

### 1.4 Estados (DISENO.md, sección 6, fila «Casilla»)

| Estado | Cómo se ve |
|---|---|
| Normal, sin marcar | Cuadro nativo de 25,5 px con su borde del navegador sobre `hoja`. `color-scheme: light dark` hace que el borde se dibuje claro en el tema oscuro |
| Marcada | Cuadro en `turquesa` (`accent-turquesa`) con el check que pone el navegador. `turquesa` sobre `hoja`: 6,7:1 en claro, 8,2:1 en oscuro |
| Foco | El contorno base de `index.css` (3 px `turquesa`, 2 px de separación) alrededor de la casilla |
| Guardando («Seguir») | El texto de la etiqueta dice «Guardando…», la casilla lleva `aria-busy` y la etiqueta `cursor-wait`. Sin cambios |
| Error | El mensaje en `pronto` negrita debajo, con `MensajeError`. En «Leí el aviso y lo acepto», `aria-invalid` y `aria-describedby`. Sin cambios |

El estado nunca va solo en el color: la casilla marcada lleva el check, y «Seguir» desmarcada se lee además en la etiqueta «Sin seguir» de la fila.

### 1.5 Cómo se ve

```
360 px, texto al 100 %                     1280 px
┌─────────────────────────────────┐        ┌───────────────────────────────────────────────┐
│ Pañales para adulto talla M     │        │ Pañales para adulto talla M                   │
│ ...                             │        │ ...                                           │
│ ─────────────────────────────── │        │ ───────────────────────────────────────────── │
│ [✓] Seguir   [ Cambiar ]   [🗑] │        │ [✓] Seguir   [ Cambiar ]                 [🗑] │
└─────────────────────────────────┘        └───────────────────────────────────────────────┘
  casilla de 25,5 px, alineada al centro de la línea de 51 px

320 px, texto al 200 % (modo angosto)
┌───────────────────────┐
│ [✓] Seguir            │   casilla de 51 px; la fila hace flex-wrap y
│ [ Cambiar ]     [🗑]  │   «Cambiar» baja a la línea siguiente, como hoy
└───────────────────────┘
```

---

## 2. «Ya lo resolví» en modo angosto

**Objetivo, desde Carmen con el texto al 200 %:** «el botón se ve como botón, con aire alrededor de las palabras, y lo toco sin buscarlo».

### 2.1 Lo que pasa hoy

A 320 px con el texto al 200 % la raíz mide 34 px y la app entra en modo `angosto`. El ancho que queda para el panel es 320 menos los rellenos `px-2` del `main`, de la sección «Se acaban pronto» y del aviso (17 px por lado cada uno): unos 218 px. Para que «Ya lo resolví» cupiera en una línea, el botón lleva `angosto:px-0.5!`, que deja 4,25 px entre el texto y el borde. El botón deja de leerse como botón y se rompe la regla de que el relleno sale de la variante (`principal` usa `angosto:px-3`).

### 2.2 Decisión

**En modo angosto, los dos botones del panel van uno bajo otro y a todo el ancho, con el relleno de su variante.** «Ya lo resolví» arriba (principal) y «Volver» debajo (secundario). Si el texto no cabe en una línea, se parte entre palabras («Ya lo» / «resolví»), centrado. Un botón de dos líneas a todo el ancho se reconoce mejor que uno de una línea pegada al borde.

La regla queda en `DISENO.md`, sección 3, fila `angosto:`: los botones de un panel o de un aviso van uno bajo otro y a todo el ancho en `angosto`, y nunca se achica el relleno de un solo botón para que su texto quepa. No contradice la sección 5 (sin botones de ancho completo en escritorio): `angosto` nunca se activa en escritorio sin zoom de más de 400 % ni en el proyector.

### 2.3 Clases exactas

En `web/src/familia/Insumos.tsx`, el panel de «Ya lo resolví» (el `div` con `id={panel}`, fila de botones bajo el `Stepper`):

| Elemento | Hoy | Cambia a |
|---|---|---|
| Fila de botones | `flex flex-wrap gap-3` | `flex flex-wrap gap-3 angosto:flex-col angosto:items-stretch` |
| «Ya lo resolví» (`confirmar-{id}`) | `className="angosto:px-0.5!"` | `className="angosto:w-full"` (sin `px-0.5!`; queda el `angosto:px-3` de la variante `principal`) |
| «Volver» | sin `className` | `className="angosto:w-full"` |

Con `items-stretch` en columna, `w-full` es redundante para el ancho, pero se deja explícito porque `Boton` es `inline-flex` con `max-w-full`, y así el ancho no depende de la alineación del padre. El texto se parte con lo que ya trae `Boton` (`[overflow-wrap:anywhere] hyphens-auto` en una celda `minmax(0,1fr)`): como «resolví» mide unos 113 px y caben 167 px (218 − 2 × 25,5), se parte entre palabras y no dentro de una.

**Mismo ancho mientras guarda:** «Guardando…» ocupa la misma celda que «Ya lo resolví» (MATU-37). A todo el ancho, el botón no cambia de tamaño al guardar.

**Fuera de `angosto` nada cambia:** a 320 px sin zoom, a 360 px y en pantalla ancha, los botones siguen al ancho de su texto, uno al lado del otro, alineados a la izquierda.

### 2.4 Estados

Sin cambios respecto de MATU-37 y MATU-51 (3.8): normal (`turquesa` macizo, único macizo de la pantalla mientras el panel está abierto), foco base, presionado `brightness-95`, guardando con «Guardando…» y `aria-busy`, «Volver» `disabled` mientras guarda, y el error en `MensajeError` debajo de la fila (`falla-{id}`), que en `angosto` también queda a todo el ancho.

### 2.5 Cómo se ve

```
360 px, texto al 100 % (no cambia)          1280 px (no cambia)
┌──────────────────────────────────┐        ┌──────────────────────────────────────────────────┐
│ ¿Compraste? ¿Cuántos envases?    │        │ ¿Cuántos envases…?  [ − ] 1 [ + ]  [ Ya lo resolví ] [ Volver ] │
│ [ − ]  1  [ + ]  envase          │        └──────────────────────────────────────────────────┘
│ [ Ya lo resolví ]  [ Volver ]    │
└──────────────────────────────────┘

320 px, texto al 200 % (modo angosto, cambia)
┌───────────────────────┐
│ ¿Compraste?           │
│ ¿Cuántos envases?     │
│ [ − ]  1  [ + ]       │
│ ┌───────────────────┐ │   principal, a todo el ancho,
│ │       Ya lo       │ │   25,5 px de relleno por lado,
│ │      resolví      │ │   unos 127 px de alto
│ └───────────────────┘ │
│ ┌───────────────────┐ │   secundario, a todo el ancho
│ │      Volver       │ │
│ └───────────────────┘ │
└───────────────────────┘
```

En los dos temas se ve igual: la forma no depende del color. `papel` sobre `turquesa` (botón principal): 6,0:1 en claro y 9,4:1 en oscuro.

---

## 3. Criterios visuales verificables

1. Toda casilla de la app de familia mide 25,5 × 25,5 px con el texto al 100 % y 51 × 51 px al 200 % (`getBoundingClientRect` del `input`). Ninguna `input[type=checkbox]` visible lleva `size-5`.
2. La etiqueta de «Seguir» y la de «Leí el aviso y lo acepto» miden 48 px o más de alto y de ancho.
3. A 320 px con el texto al 200 %, «Ya lo resolví» y «Volver» miden el ancho de su fila y están uno bajo otro; entre el texto de «Ya lo resolví» y el borde del botón hay al menos 25 px por lado.
4. Ningún botón de `web/src/familia/` lleva `px-0.5` ni un relleno con `!`.
5. A 360 px y 1280 px, sin zoom, el panel de «Ya lo resolví» se ve igual que antes: los dos botones al ancho de su texto, uno al lado del otro.
6. Sin desplazamiento horizontal a 320 px con el texto al 200 %, en tema claro y oscuro.
7. El botón principal sigue siendo el único elemento en `turquesa` macizo mientras el panel está abierto.

## 4. Fuera de alcance (P3, para otra tarjeta si Jorge quiere)

- «Seguir» cambia a «Guardando…» y la etiqueta crece, así que «Cambiar» se corre unos 40 px mientras guarda. Se arreglaría con la misma celda doble de `Boton` en la etiqueta. No se toca en MATU-68.

## 5. Revisión visual pendiente

Esta especificación se escribió sobre el código y las medidas calculadas con la raíz de 17 px, sin mirar la pantalla funcionando. Después de construirla, el diseñador la revisa con capturas a 320 px con el texto al 200 %, 360, 1280 y 1920 px, en claro y oscuro, y la aprueba o pide cambios. En esa revisión se confirma también el contraste del borde nativo de la casilla sin marcar (3:1 o más) en los dos temas.

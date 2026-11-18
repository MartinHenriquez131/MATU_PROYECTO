# MATU-117 · La etiqueta de varios renglones y el foco inicial de los diálogos · Especificación de diseño

**Versión 1.0 · 18/11/2026** · Agente 6, UI/UX. Especifica y no construye. **Sin tokens nuevos:** se usan `rounded-2xl` (el radio de los diálogos) y el foco base de la capa `base` de `web/src/index.css`. La regla queda también en `Demo/DISENO.md`, sección 6 (filas «Etiqueta de estado» y «Diálogo»).

**Origen:** el P3 de la revisión visual de MATU-113 (la etiqueta) y el H3 de Martín en `TESTER/2026-11-17-MATU-103-95-108-110-80.md` del repositorio MATU (el foco).

---

## 1. La etiqueta de estado con varios renglones

### 1.1 Objetivo

Carmen lee el estado de un pedido o de un permiso en una etiqueta que, con el texto al 200 % en un teléfono angosto, ocupa tres renglones, y la ve como una etiqueta, no como un óvalo.

### 1.2 Decisión

En `Etiqueta` (`web/src/familia/ui.tsx`), **`rounded-full` pasa a `rounded-2xl`**. Nada más cambia: ni el relleno, ni el espacio, ni el tono, ni `angosto:[&>svg]:hidden`.

```
antes   inline-flex max-w-full shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-base font-bold …
ahora   inline-flex max-w-full shrink-0 items-center gap-1.5 rounded-2xl  px-2.5 py-0.5 text-base font-bold …
```

**Por qué `rounded-2xl` y no `rounded-xl`.** La etiqueta de un renglón mide 1,75 rem de alto (renglón de 1,5 rem de `text-base` más los 0,125 rem arriba y abajo de `py-0.5`). Cuando dos radios vecinos suman más que el lado, el navegador los achica en la misma proporción (CSS Backgrounds 3, 5.5). Con `rounded-2xl` (1 rem + 1 rem = 2 rem sobre un lado de 1,75 rem) el radio efectivo queda en 0,875 rem, la mitad exacta del alto: la misma píldora de hoy. Con varios renglones el lado crece y el radio se queda en 1 rem, una esquina redonda de rectángulo. Como todo va en rem, vale igual con el texto al 100 % y al 200 %.

`rounded-xl` (0,75 rem) no cabe en esa regla: en un renglón deja un tramo recto en los lados y la etiqueta de hoy cambia.

**Medido el 18/11 en Chrome** (captura de la misma etiqueta con los tres radios, comparada píxel a píxel):

| Texto | Alto de un renglón | `rounded-full` = `rounded-2xl` | `rounded-full` = `rounded-xl` |
|---|---|---|---|
| 100 % (1 rem = 17 px) | 29,75 px | idéntica | distinta |
| 200 % (1 rem = 34 px) | 59,5 px | idéntica | distinta |

**Una condición para que siga igual:** la etiqueta de un renglón no puede medir más de 2 rem de alto. Hoy ninguna de sus 38 llamadas cambia el relleno (las clases extra son `self-start` y `flex-wrap`). Si una llamada futura le sube el relleno sobre `py-1`, la píldora se notaría y es un hallazgo.

### 1.3 Esquemas

**360 px, texto normal, y 1280 y 1920 px:** igual que hoy, en un renglón.

```
 ╭────────────────────────────────╮
 │ ◐ Hay que confirmarlo de nuevo │   píldora: rounded-2xl, radio efectivo 0,875 rem
 ╰────────────────────────────────╯
```

**320 px con el texto al 200 % (`angosto:`, 160 px efectivos):** la figura se oculta (MATU-107) y la palabra baja de renglón.

```
 hoy (rounded-full)            ahora (rounded-2xl)
   .-~~~~~~~~~~~~-.             ╭────────────────────╮
  (  Hay que       )            │ Hay que            │   286 × 161 px
 (   confirmarlo    )           │ confirmarlo de     │   esquinas de 1 rem (34 px)
  (  de nuevo      )            │ nuevo              │
   '-~~~~~~~~~~~~-'             ╰────────────────────╯
```

Con el radio de la píldora (80 px), el arco se comía el principio y el final de los renglones de arriba y de abajo. Con 34 px, el texto (que empieza a 0,625 rem del borde, 21 px) queda fuera de la curva en los renglones del centro y apenas la roza en los de los extremos.

### 1.4 Estados

No cambian. La etiqueta no es interactiva: no tiene foco, ni presionado, ni deshabilitado. Los cuatro tonos de `TONO_ETIQUETA` (`neutro`, `ok`, `activo` y `atenta`) usan la misma forma.

### 1.5 El distintivo del piloto

**Incluido en esta tarjeta por decisión del orquestador (18/11/2026).** `DistintivoPiloto` (`web/src/compartido/ui/Marca.tsx`, línea 15) también era `rounded-full` y se parte en renglones con el texto al 200 %. **Pasa a `rounded-2xl`**, sin otro cambio en su clase (`bg-tinta/7`, `px-3 py-1`, `text-base font-bold text-tenue` y el punto `miel` siguen iguales; el punto conserva su `rounded-full`, porque es un círculo).

- **En un renglón, la misma píldora.** Con `py-1` mide 2 rem de alto (1,5 rem de renglón más 0,25 rem arriba y abajo). Los dos radios de 1 rem suman justo el alto, así que la curva es la de `rounded-full`.
- **En varios renglones, un rectángulo** de esquinas de 1 rem, como la etiqueta (1.3).
- La regla del distintivo no cambia: siempre visible, en todas las pantallas, también con el texto al 200 % (`Demo/DISENO.md`, «Rótulos del piloto»).

Criterios 1 a 3 de la sección 4, aplicados también al distintivo: en un renglón se ve igual que en `main` a 360, 1280 y 1920 px, en claro y en oscuro; a 320 px con el texto al 200 % se ve como un rectángulo de esquinas redondas, sin desborde horizontal.

---

## 2. El foco inicial de los diálogos

### 2.1 Objetivo

Quien usa el teclado abre un diálogo y ve de inmediato dónde quedó el foco. Así sabe que Enter no va a borrar ni a cancelar nada. Quien toca la pantalla, como Carmen, no ve un recuadro que no pidió.

### 2.2 Lo que pasa hoy (medido el 18/11 en Chrome)

El H3 dice que `:focus-visible` no se activa porque el foco lo pone el programa. No es así. Chrome aplica la regla de CSS Selectors 4: el foco puesto por el programa **hereda la modalidad del gesto que abrió el diálogo**. Se probó con un `<dialog>` de prueba igual a los de MATU, sin datos:

| Se abre con | Foco en un título `tabIndex={-1}` | Foco en un botón |
|---|---|---|
| Teclado (Tab y Enter) | `:focus-visible` **sí** | `:focus-visible` **sí** |
| Ratón | no | no |
| Toque | no | no |

Así que hay dos casos distintos:

| Diálogo | Archivo | Foco inicial | Con teclado hoy |
|---|---|---|---|
| `DialogoGrupo` | `web/src/familia/PiezasInvitar.tsx:112` | El título `h2` | **Sin contorno:** el `h2` lleva `outline-none`, que le gana a la capa base |
| `DialogoRetirar` | `web/src/familia/Grupo.tsx:624` | El título `h2` | **Sin contorno**, por lo mismo |
| `DialogoConfirmar` (y `DialogoPedido`) | `web/src/familia/DialogoConfirmar.tsx:109` | El título `h2` | **Sin contorno**, por lo mismo |
| `DialogoBorrar` | `web/src/familia/Grupo.tsx:882` | «No borrar» (botón de texto) | Con el contorno base. Correcto |
| `DialogoEliminar` | `web/src/familia/Insumos.tsx:2246` | «Cancelar» (botón de texto) | Con el contorno base. Correcto |

Con el ratón o el toque no hay contorno en ninguno, y está bien: WCAG 2.4.7 pide el foco visible a quien navega con el teclado, y es lo que hace el foco base de MATU en todas las pantallas.

### 2.3 Decisión

1. **Qué recibe el foco: no cambia.** Los tres diálogos de MATU-44 (4.1) lo ponen en el título, para que el lector de pantalla diga la pregunta primero y para que un Enter apurado no confirme nada. `DialogoBorrar` (MATU-72, 3.3) y `DialogoEliminar` (MATU-36, 3.6.2) lo ponen en la salida segura. Las dos decisiones siguen valiendo.
2. **El título que recibe el foco muestra el contorno base cuando se abrió con el teclado.** En los tres `h2` de la tabla, **se quita `outline-none`** y no se agrega nada: la capa base pone `outline: 3px solid var(--color-turquesa)`, con `outline-offset: 2px` y `border-radius: 0.4rem`, solo bajo `:focus-visible`. No hay clase nueva ni token nuevo.

   ```
   antes   <h2 … tabIndex={-1} className="text-xl font-bold break-words outline-none">
   ahora   <h2 … tabIndex={-1} className="text-xl font-bold break-words">
   ```

3. **Con el ratón o el toque, ningún contorno** en el título ni en los botones. No se usa `:focus` (sin `-visible`) ni un `outline` fijo: un recuadro turquesa alrededor de la pregunta, al tocar «Eliminar», parece un campo para escribir.
4. **Por qué en los diálogos y no en los títulos de página.** Los títulos de página que reciben el foco al navegar (`titulo-pagina`) y los avisos con `tabIndex={-1}` siguen con `outline-none`: este cambio no los toca. En un diálogo la diferencia importa más, porque se abre para una decisión que no se deshace y quien usa el teclado necesita ver que el foco no quedó en el botón que borra. Si se quiere lo mismo en los títulos de página, es otra tarjeta.
5. **`DialogoBorrar` y `DialogoEliminar` no cambian.**

### 2.4 Esquema (360 px, abierto con el teclado)

```
 ┌──────────────────────────────────┐   dialog: rounded-2xl bg-hoja ring-1 ring-linea
 │ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓ │   contorno base: 3 px turquesa, 2 px de separación,
 │ ┃ ¿Retirar la autorización de  ┃ │   radio 0,4 rem, a todo el ancho del h2
 │ ┃ Rodrigo?                     ┃ │
 │ ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛ │
 │ Texto del diálogo…               │
 │ [ Retirar la autorización ]      │
 │ Dejarla como está                │
 └──────────────────────────────────┘
```

En pantalla ancha (1280 y 1920 px) es igual: el diálogo mide `max-w-md` y el contorno rodea el `h2` a ese ancho. Con el texto al 200 % a 320 px, el diálogo usa `angosto:px-2` (8 px de relleno) y el contorno ocupa 5 px fuera del `h2` (3 de trazo y 2 de separación), así que cabe dentro del relleno y el `overflow-y-auto` del diálogo no lo corta.

### 2.5 Contraste

Es el foco base, ya medido en `Demo/DISENO.md` (sección 1): `pino` (`turquesa` en `web/`) mide 6,7:1 sobre `hoja` en claro y 8,2:1 en oscuro, sobre el 3:1 que pide el foco.

### 2.6 Textos

No cambia ningún texto.

---

## 3. Casos de la revisión visual

Para cada uno, en tema claro y en oscuro.

| Ancho | Etiqueta (por ejemplo, «Tus pedidos» y «Grupo familiar») | Diálogo abierto con Tab y Enter | Diálogo abierto con un toque o un clic |
|---|---|---|---|
| 360 px | Un renglón, píldora igual a la de `main` | El `h2` con el contorno base en `DialogoGrupo`, `DialogoRetirar` y `DialogoConfirmar`; «No borrar» y «Cancelar» con el contorno en los otros dos | Sin contorno en ninguno |
| 1280 px | Igual | Igual | Igual |
| 1920 px | Igual | Igual | Igual |
| 320 px, texto al 200 % | Varios renglones, rectángulo de esquinas de 1 rem, sin desborde horizontal | El contorno entero dentro del diálogo, sin cortarse, sin desplazamiento horizontal | Sin contorno |

## 4. Criterios de revisión

1. `grep -n "rounded-" web/src/familia/ui.tsx` muestra `rounded-2xl` en `Etiqueta` y ningún `rounded-full` en esa línea. Nada más cambia en su clase.
2. A 360, 1280 y 1920 px, en claro y en oscuro, la etiqueta de un renglón se ve igual que en `main` (captura antes y después, a la misma posición).
3. A 320 px con el texto al 200 %, la etiqueta más larga de «Tus pedidos» se ve como un rectángulo de esquinas redondas, no como un óvalo, y ningún renglón queda tapado por la curva.
4. En los tres `h2` de `DialogoGrupo`, `DialogoRetirar` y `DialogoConfirmar` ya no está `outline-none`, y no se agregó ninguna clase de contorno ni de foco en su lugar.
5. Con el teclado (Tab hasta el botón y Enter), cada uno de los cinco diálogos muestra el contorno base en el elemento que recibe el foco, a 360 y 1280 px, en claro y en oscuro.
6. Con un toque o un clic, ninguno de los cinco diálogos muestra contorno al abrirse.
7. A 320 px con el texto al 200 %, el contorno del título se ve entero dentro del diálogo y no aparece desplazamiento horizontal.
8. El foco inicial sigue en el mismo elemento que hoy en los cinco diálogos, y Tab sigue llevando al primer botón.
9. Los títulos de página (`titulo-pagina`) y los avisos con `tabIndex={-1}` no cambian.
10. `web/pruebas/etiquetaAngosto.test.tsx` y `web/pruebas/veloDialogos.test.ts` siguen en verde. Conviene una prueba nueva que falle si `Etiqueta` vuelve a `rounded-full` y otra que falle si alguno de los tres `h2` vuelve a llevar `outline-none` (definición de terminado, punto 6).

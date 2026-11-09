# MATU-67 · Aviso de versión nueva · Especificación de diseño

**Versión 1.1 · 09-11-2026 · agente 6 UI/UX.** Base: `Demo/DISENO.md` (secciones 3, 4 y 6), los tokens de `web/src/index.css`, `docs/lenguaje.md` (solo lectura) y lo ya construido en `web/src/familia/Shell.tsx`, `web/src/familia/Alta.tsx` (`MarcoAlta`), `web/src/relevo/Marco.tsx`, `web/src/compartido/ui/Nota.tsx`, `web/src/compartido/ui/Boton.tsx` y `web/src/compartido/ui/Anuncios.tsx`. **Sin tokens nuevos ni colores nuevos.**

### Cambios de la v1.1 (revisión visual del 09-11, arreglos aprobados por Jorge)

| # | Cambio | Sección |
|---|---|---|
| 1 | El anillo del botón secundario pasa de `ring-turquesa/70` a **`ring-turquesa/80`** en toda la app. Con `/70` medía 2,91:1 contra `rocio` en tema claro, bajo el 3:1 de un borde de control (P1) | 3 |
| 2 | El relleno del secundario en modo angosto pasa de `angosto:px-3` a **`angosto:px-2`**, para que «Seguir escribiendo» no se corte dentro de la palabra a 320 px con texto al 200% (P2) | 3 y 5 |
| 3 | En la ficha del relevo, el aviso toma el ancho de la grilla (`max-w-6xl`) y la caja queda a la izquierda. En el PIN y los estados sigue `max-w-xl` centrado (P2) | 2.3 |
| 4 | Al pasar al estado sin guardar, la pantalla baja hasta el borde de arriba de la caja antes de mover el foco (P2) | 4.3 |
| 5 | En la pantalla «Lo que escribiste no se guardó» (`textoPerdido`) el aviso **espera**, como en `/compartir/listo` (P2) | 4.2 |
| 6 | Título propio para Insumos: «Lo que anotaste de «`{nombre}`» no se guardó.» (P3) | 4.3 y 6 |
| 7 | Se protegen con `sinGuardar` también «Ya lo resolví» y el formulario de `/compartir` | 4.3 |
| 8 | Contraste medido de `tinta` sobre `rocio`: 13,2:1 en claro y **10,9:1** en oscuro (la v0.1 decía «más de 12:1») | 3 |
| 9 | Se corrige qué pantallas usan `MarcoSimple`: `/entrar` va en `MarcoAlta` | 2.2 |

---

## 0. Lo que tiene que decidir alguien más

**Estado:** Jorge aprobó el 09-11 todas las propuestas de esta tabla y de G1 a G4 con la opción por defecto. Las marcas **[PROPUESTO]** quedan como registro de lo que se propuso.

| # | Pregunta | Propuesta (opción por defecto) |
|---|---|---|
| D1 | Texto del aviso | «Hay una versión nueva de MATU.» con el botón «Recargar». **[PROPUESTO, pendiente de Jorge]** |
| D2 | ¿Lleva una bajada? | **Sí**, porque sin ella el aviso no dice que es la persona quien decide cuándo. Familia: «Recarga cuando termines lo que estás haciendo.» Relevo: «Recarga cuando termines de leer.» **[PROPUESTO]**. Se descartó «Lo que escribiste no se pierde», porque hoy solo el editor de secciones sabe si hay texto sin guardar (`sinGuardar`). Los formularios de Insumos, el alta y Compartir no lo saben, y la frase sería falsa justo ahí (ver G1). Si el frontend extiende `sinGuardar` a todos los formularios, se puede sumar esa frase |
| D3 | ¿Se puede cerrar? | **Sí, con «Más tarde»** (botón de texto). **[PROPUESTO]** |
| D4 | Después de «Más tarde», ¿cuándo vuelve? | **No vuelve al cambiar de pantalla.** Vuelve en la próxima revisión (al volver a la pestaña o en la siguiente de cada 15 minutos) que encuentre una versión distinta de la que corre, **siempre que hayan pasado al menos 15 minutos** desde «Más tarde». Así no persigue a Carmen de pantalla en pantalla, y tampoco la deja una tarde entera con la versión vieja. Se recuerda solo en memoria. **[PROPUESTO]** |
| D5 | En el relevo ya existe «Actualizar» (lenguaje.md 7.4), que vuelve a pedir la ficha. «Recargar» está al lado | **Se mantienen los dos verbos.** «Actualizar» trae la ficha al día; «Recargar» trae la versión nueva de la página. La bajada del relevo dice que es la página y no la ficha. Si Jorge prefiere un solo verbo, la alternativa es «Abrir la versión nueva» en el botón del aviso |
| D6 | Texto cuando hay algo sin guardar y la persona toca «Recargar» (sección 4.3) | Título «Lo que escribiste en «`{sección}`» no se guardó.», bajada «Si recargas ahora, se pierde.», botones «Seguir escribiendo» y «Recargar igual». **[PROPUESTO]** |

**Para el orquestador (no son de diseño, pero el aviso depende de ellos):**

- **G1.** Una recarga borra lo que vive en memoria: el texto de un formulario de Insumos, el borrador del alta, la selección de Compartir y, lo más grave, **el PIN de `/compartir/listo`, que se muestra una sola vez**. Esta especificación lo resuelve en pantalla (secciones 4.2 y 4.3), pero la protección al tocar «Recargar» solo alcanza a lo que informa `sinGuardar`, que hoy solo usa `EditorSeccion`. Hay que decidir si se extiende a los demás formularios. **Resuelto (v1.1):** se extiende a los formularios de Insumos, incluido «Ya lo resolví», y al de `/compartir` (ver la tabla de 4.3). El alta, `/compartir/listo` y «Lo que escribiste no se guardó» quedan cubiertos porque ahí el aviso espera (4.2).
- **G2.** En el relevo, si la sesión de Rosa venció, al recargar ve «Vuelve a abrir el enlace» (lenguaje.md 7.3). Le pasaría igual al tocar «Actualizar», pero por eso la bajada del relevo no promete que no tendrá que volver a escribir el PIN.
- **G3.** `version.json` tiene que servirse sin caché (`Cache-Control: no-store`). Si no, el aviso no aparece nunca. Es del despliegue, no de la pantalla.
- **G4.** El aviso tiene que verse igual en las dos apps, y hoy `Nota` vive en `familia/ui.tsx`. El aviso va como **un solo componente en `compartido/ui/`** con la apariencia de `Nota` (sección 3). Cómo se reparte el código lo decide el frontend.

---

## 1. Objetivo y jerarquía

**Objetivo, desde la persona:** «Me entero de que hay algo nuevo, sin perder lo que estoy escribiendo, y recargo cuando a mí me acomoda.»

**Jerarquía dentro del aviso:**
1. El título, «Hay una versión nueva de MATU.»
2. «Recargar», el botón secundario.
3. La bajada y «Más tarde».

**Jerarquía en la pantalla:** el aviso **nunca** es lo primero. La acción principal de la pantalla (por ejemplo «Guardar») sigue siendo el único botón `turquesa` macizo. El aviso es un mensaje del sistema y queda en el borde del contenido, no en el medio.

---

## 2. Dónde aparece

**Regla común:** el aviso va **en el flujo del documento**, nunca fijo, flotante ni encima de nada. No tiene sombra (DISENO.md, principio 1: solo llevan sombra las capas que tapan algo, y esta no tapa nada). Por eso no tapa los botones de guardar ni la barra de secciones de abajo, y el `scroll-padding-bottom` de 6 rem no cambia.

Un solo elemento por marco, en una sola posición del DOM. No se dibuja dos veces para dos anchos.

### 2.1 App de la familia, con la barra de secciones (`ShellFamilia`)

Va **dentro del `aside`, después de `Navegacion`**, en el mismo contenedor flex.

- **Pantalla ancha (`@4xl/app`, desde 1280 px):** la barra lateral es una columna pegajosa (`sticky top-4`), así que el aviso queda **bajo las cuatro secciones** y sigue a la vista mientras Carmen se desplaza. **El contenido principal no se mueve** cuando aparece.
- **Entre 40 y 56 rem:** la barra lateral es la fila de arriba. El aviso toma su propio renglón (`basis-full`) bajo la marca y las secciones.
- **Teléfono (`telefono:`, 360 px):** las secciones son la barra fija de abajo, así que el aviso queda en la fila de arriba, **bajo la marca y el distintivo y sobre el encabezado** con la persona. Está arriba de todo. No queda junto a la barra de abajo ni junto a los botones de guardar.
- **Texto al 200% (`angosto:`):** las secciones vuelven arriba, apiladas. El aviso queda bajo ellas, antes del encabezado.

### 2.2 App de la familia sin barra de secciones

- **`MarcoSimple`** (v1.1): lo usan tres pantallas, «Abriendo MATU» (`Abriendo`), el error al abrir (`ErrorAlAbrir`) y «Lo que escribiste no se guardó» (`TextoPerdido`). El aviso es el **primer elemento de `main`**, dentro del `mx-auto max-w-7xl`, antes del título, con `mb-6`. En `TextoPerdido` el aviso espera (4.2, caso 4).
- **`MarcoAlta`** (crear cuenta, **entrar**, recuperar acceso y la primera visita): **no se muestra** (ver 4.2). La v0.1 ponía «entrar» en `MarcoSimple`. Era un error: `/entrar` va en `MarcoAlta`.

### 2.3 Página del relevo (`/r`, `relevo/Marco.tsx`)

**El relevo tiene su propio armazón:** `main.tsx` monta `PaginaRelevo` con su `Marco`, sin `ShellFamilia`, sin barra de secciones y con su propio `main`. Las regiones vivas son las mismas (`RegionesVivas`, montadas en `main.tsx` para las dos apps).

El aviso es el **primer elemento de `main`**, con `mb-6`, antes del momento que se muestre (PIN, ficha, estado o error). Su contenedor toma **el ancho de la columna del momento** (v1.1):

| Momento | Contenedor del aviso | La caja |
|---|---|---|
| PIN, estados y errores | `mx-auto max-w-xl`, el ancho de la columna del PIN | Centrada, como la columna |
| Ficha | `mx-auto max-w-6xl`, el ancho de la grilla de la ficha | **A la izquierda**, alineada con el borde izquierdo de **la tarjeta de la ficha**. La tarjeta va `mx-auto max-w-3xl` dentro de la primera columna, así que queda de 28 a 43 px más adentro que la grilla. La `max-w-prose` de `Nota` limita la caja |

En la v0.1 el aviso iba `max-w-xl` centrado en todos los momentos. En la ficha, a 1280 y 1920 px, quedaba flotando desalineado de la tarjeta y de la columna lateral. Cómo se entera el contenedor del momento (una prop de `Marco` o el aviso dentro de cada momento) lo decide el frontend.

En los dos casos el texto va alineado a la izquierda, aunque la columna del PIN use `text-center`, porque es un mensaje y no el PIN (DISENO.md 3, alineación).

### 2.4 Esquemas

**Familia a 360 px:**

```
┌────────────────────────────────────────┐
│ (♥) MATU   [Piloto académico / con …]  │  aside, papel
│ ┃ ⟳ Hay una versión nueva de MATU.     │  aviso: rocio, borde izq. turquesa
│ ┃   Recarga cuando termines lo que     │  text-base
│ ┃   estás haciendo.                    │
│ ┃   [ Recargar ]   Más tarde           │  secundario + texto, 48 px
├────────────────────────────────────────┤
│ Cuidas a                       Tu cuenta│  Encabezado
│ María Soto                        Salir │
├────────────────────────────────────────┤
│ Ficha de relevo                         │  título de la página
│ …                                       │
│ [ Guardar ]                             │  único turquesa macizo
│                                         │
├────────────────────────────────────────┤
│  Ficha   Insumos  Compartir  Grupo      │  barra fija: no cambia
└────────────────────────────────────────┘
```

**Familia a 1280 px:**

```
┌──────────────────┬──────────────────────────────────────────────────────┐
│ (♥) MATU         │ Cuidas a María Soto      Piloto…  Tu cuenta  Salir    │
│                  ├──────────────────────────────────────────────────────┤
│ ▣ Ficha  2 de 3  │ Ficha de relevo                                       │
│ □ Insumos        │                                                       │
│ □ Compartir      │  (contenido: no se mueve al aparecer el aviso)        │
│ □ Grupo familiar │                                                       │
│                  │                                                       │
│ ┃ ⟳ Hay una      │                                                       │
│ ┃ versión nueva  │                                                       │
│ ┃ de MATU.       │                                                       │
│ ┃ Recarga cuando │                                                       │
│ ┃ termines lo que│                                                       │
│ ┃ estás haciendo.│                                                       │
│ ┃ [ Recargar ]   │                                                       │
│ ┃ Más tarde      │                                                       │
└──────────────────┴──────────────────────────────────────────────────────┘
```

A 1920 px es igual: la barra lateral mide siempre 16,5 rem.

**Relevo a 360 px, y en pantalla ancha en el PIN y los estados:**

```
┌──────────────────────────────────────────────────────┐
│ (♥) MATU  Ficha de cuidado            [Piloto…]      │
├──────────────────────────────────────────────────────┤
│        ┃ ⟳ Hay una versión nueva de MATU.            │  max-w-xl, centrado
│        ┃   Recarga cuando termines de leer.          │  texto a la izquierda
│        ┃   [ Recargar ]   Más tarde                  │
│                                                      │
│              (PIN o estado)                          │
└──────────────────────────────────────────────────────┘
```

**Relevo en pantalla ancha, con la ficha (v1.1):**

```
┌──────────────────────────────────────────────────────────────────────┐
│ (♥) MATU  Ficha de cuidado compartida                     [Piloto…]  │
├──────────────────────────────────────────────────────────────────────┤
│  ┃ ⟳ Hay una versión nueva de MATU.                                  │  max-w-6xl, a la izquierda
│  ┃   Recarga cuando termines de leer.                                │  caja max-w-prose
│  ┃   [ Recargar ]   Más tarde                                        │
│                                                                      │
│  ┌─ Ficha de cuidado de María ──────────────┐   Puedes verla hasta…  │  mismo borde izquierdo
│  │ …                                        │   [ Actualizar ]       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Componente y tokens

La apariencia es la de **`Nota` con `tono="rocio"` y `borde`**, con el ícono en línea en modo angosto (`iconoEnLinea`). No es una pieza visual nueva.

| Parte | Token o pieza |
|---|---|
| Caja | `bg-rocio`, `border-l-4 border-turquesa`, `rounded-xl`, `px-4 py-3`, y en modo angosto `px-2`. `max-w-prose`. Sin sombra |
| Ícono | `RefreshCw` de `lucide-react`, `size-5`, `text-turquesa`, `aria-hidden`. Reemplaza al `Info` del tono `rocio` porque dice de qué se trata. Va en el título, no en el botón |
| Título | `font-bold`, `text-base`, `text-tinta` |
| Bajada | `text-base leading-relaxed text-tinta` (el cuerpo de `Nota`) |
| Acciones | `Acciones` (`flex flex-wrap items-center gap-x-5 gap-y-3`), con `mt-3` |
| «Recargar» | `Boton variante="secundario"`, sin ícono, `textoOcupado="Recargando…"` |
| Variante `secundario` de `Boton` (v1.1, **para toda la app**) | Anillo **`ring-2 ring-inset ring-turquesa/80`** (antes `/70`) y relleno **`px-5 angosto:px-2`** (antes `angosto:px-3`). El resto no cambia. Los controles con la misma apariencia escritos fuera de `Boton` (el enlace de `Alta.tsx`, `Dictado.tsx` y los `Stepper` de `insumosComun.tsx` y `ui.tsx`) pasan también a `ring-turquesa/80`, para que un stepper no se vea más claro que el «Volver» de al lado |
| «Más tarde» | `Boton variante="texto"` |
| Entrada | `animate-aparecer` (180 ms). Con `prefers-reduced-motion` es inmediata, por la regla global de `index.css` |

**Por qué `borde`:** en la barra lateral y en el relevo el aviso va sobre `papel`, y `rocio` sobre `papel` casi no se distingue (las dos son neblinas claras). La línea `turquesa` (6,0:1 sobre `papel` claro y 9,4:1 en oscuro) es la que separa el aviso del fondo. No es un control, así que no necesita un contorno de 3:1, pero la línea igual lo cumple.

**Por qué secundario y no principal:** la pantalla ya tiene su acción principal. Un segundo botón macizo competiría con «Guardar» (DISENO.md 6: «uno solo por pantalla»).

**Contrastes, medidos en pantalla en la revisión visual del 09-11** (píxeles de las capturas, con `rocio` ya mezclado):

| Par | Claro | Oscuro |
|---|---|---|
| Título y bajada `tinta` sobre `rocio` | 13,2:1 | **10,9:1** |
| Ícono `turquesa` sobre `rocio` | 5,6:1 | 6,7:1 |
| «Recargar»: texto `turquesa` sobre `hoja` | 6,7:1 | 8,2:1 |
| «Recargar»: anillo `turquesa/80` sobre `hoja`, por dentro | 4,3:1 | más de 4,7:1 |
| «Recargar»: anillo `turquesa/80` sobre `rocio`, el fondo del aviso | **3,6:1** | más de 3,8:1 |
| «Seguir escribiendo»: anillo `turquesa/80` sobre `atenta-fondo` | 3,5:1 aprox. | más de 4,3:1 |
| «Más tarde»: `turquesa` sobre `rocio` | 5,6:1 | 6,7:1 |
| Foco base, 3 px `turquesa`, sobre `rocio` | 5,6:1 | 6,7:1 |

**Por qué `/80` (v1.1):** el anillo de un control se mide contra los dos colores que toca. Con `/70`, el anillo medía 3,49:1 contra la `hoja` de adentro, pero **2,91:1 contra el `rocio` de afuera** en tema claro, bajo el 3:1 de WCAG 1.4.11. En oscuro medía 4,72 y 3,84 y cumplía. Con `/80` mide 3,6:1 sobre `rocio`, 3,84:1 sobre `papel` y 4,32:1 sobre `hoja`. El cambio va en la variante para toda la app, porque el secundario sobre `rocio` va a volver a aparecer, y en tema oscuro solo sube el contraste.

**Por qué `angosto:px-2` (v1.1):** a 320 px con texto al 200%, «escribiendo» mide 185 px y el botón de la barra lateral dejaba 180 px para el texto con `angosto:px-3`. La palabra se partía («escribiend / o»). Con `angosto:px-2` quedan 197 px.

**Áreas táctiles:** los dos botones miden `min-h-12` (51 px con la raíz de 17 px). «Más tarde» es de texto, sin relleno a los lados, y mide más de 48 px de ancho por su texto. Los dos tienen el foco base (contorno de 3 px `turquesa` con 2 px de separación).

---

## 4. Comportamiento y estados

### 4.1 Normal

- La app revisa `version.json` al volver a la pestaña (`visibilitychange` a `visible`) y cada 15 minutos mientras está visible. Si el identificador es distinto del de la versión que corre, aparece el aviso.
- **Nunca recarga sola.** Ningún temporizador, ninguna navegación y ninguna revisión llama a `location.reload()`. Solo el botón.
- **No toma el foco.** El foco se queda donde estaba.
- **Se anuncia una vez** por la región viva `status` (`polite`), con `useAnunciarAlMostrar`, igual que `Nota rol="status"`: «Hay una versión nueva de MATU. Recarga cuando termines lo que estás haciendo.» Los botones no se leen en el anuncio (`textoParaLeer` los omite). Si una revisión posterior encuentra otra versión todavía más nueva mientras el aviso está a la vista, el aviso no cambia y no se vuelve a anunciar.
- **Al cambiar de pantalla, el aviso se queda.** No se vuelve a anunciar.

### 4.2 Cuándo espera para aparecer

El aviso aparece en el flujo, así que, si apareciera mientras Carmen escribe, movería el campo. Por eso **espera**, sin perder la versión detectada, en estos casos:

1. **El foco está en un campo de texto** (`textarea`, o `input` de texto, correo, teléfono, número o contraseña). Aparece cuando el foco sale a algo que no es un campo de texto. Pasar de un campo a otro no cuenta como salir.
2. **En `MarcoAlta`** (alta y recuperar acceso): el borrador vive en memoria y una recarga lo borra. Aparece cuando la persona llega a una pantalla con `ShellFamilia` o `MarcoSimple`.
3. **En `/compartir/listo`:** el PIN se muestra una sola vez y una recarga lo borra (G1). Aparece cuando Carmen sale de esa pantalla. **Si el aviso ya estaba a la vista al llegar, se oculta** y vuelve al salir, sin anunciarse de nuevo (decisión del frontend, aprobada el 09-11).
4. **En «Lo que escribiste no se guardó» (`TextoPerdido`, v1.1):** la pantalla muestra el texto que no se guardó para que Carmen lo copie, y una recarga lo borra. Es una pantalla que retiene algo, como `/compartir/listo`. Aparece cuando Carmen sale de ella (al tocar «Entrar»). Si ya estaba a la vista, se oculta igual que en el caso 3. En la v0.1 el aviso se mostraba ahí, y al tocar «Recargar» quedaban dos avisos `atenta` seguidos que decían casi lo mismo, con un «Seguir escribiendo» que llevaba al título «Entrar», donde no hay nada que escribir.

Mientras espera, tampoco se anuncia: se anuncia cuando aparece.

En el relevo solo aplica el caso 1 (el campo del PIN). Recargar la pantalla del PIN no pierde nada, porque el enlace sigue en la dirección.

### 4.3 «Recargar» con algo sin guardar (solo familia)

Si al tocar «Recargar» `sinGuardar` devuelve texto, **no se recarga**. El mismo aviso cambia de estado:

```
┃ ⚠ Lo que escribiste en «Si se altera»     tono atenta, borde atenta
┃   no se guardó.
┃   Si recargas ahora, se pierde.
┃   [ Seguir escribiendo ]   Recargar igual
```

| Parte | Token o pieza |
|---|---|
| Caja | `Nota tono="atenta" borde`: `bg-atenta-fondo`, `border-l-4 border-atenta`, ícono `TriangleAlert` en `atenta`. Es el mismo tono del aviso «sin guardar» de `EditorSeccion`. El estado cambia de color, de ícono y de palabras, no solo de color |
| Anuncio | `alert`, porque es la respuesta a su acción y hay algo que se puede perder |
| «Seguir escribiendo» | `Boton variante="secundario"`, primero. **Recibe el foco** al cambiar de estado. Así, un segundo toque rápido en el mismo lugar no borra nada |
| «Recargar igual» | `Boton variante="textoPeligro"`, segundo. Recarga |

**Al cambiar de estado, primero se ve y después se enfoca (v1.1).** La caja `atenta` es más alta que la normal. A 320 px con texto al 200% mide unos 750 px. Si solo se enfoca «Seguir escribiendo», el navegador desplaza lo mínimo para mostrar el botón, y el título («… no se guardó.») queda fuera de la pantalla. Por eso, en este orden:

1. La pantalla baja hasta **el borde de arriba de la caja**: `scrollIntoView({ block: 'start' })`. Con `behavior: 'smooth'`, porque responde al toque de Carmen y le muestra hacia dónde se movió la pantalla (DISENO.md, principio 5, «movimiento solo como respuesta»). Con `prefers-reduced-motion` es `behavior: 'instant'`.
2. El foco va a «Seguir escribiendo» con `focus({ preventScroll: true })`, para que el navegador no vuelva a mover la pantalla.

**Qué protege `sinGuardar`** (v1.1, aprobado por Jorge el 09-11). Lo que tiene sin guardar cada formulario a la vista:

| Formulario | Título del estado sin guardar | El foco con «Seguir escribiendo» |
|---|---|---|
| Editor de un campo o una sección de la ficha | «Lo que escribiste en «`{sección}`» no se guardó.» | El campo de texto |
| Insumos: «Compré», «Me quedan», «Ya lo resolví» y el editor de un insumo existente | **«Lo que anotaste de «`{nombre}`» no se guardó.»**, con el nombre del insumo | El campo que cambió, o el primero del panel |
| Insumos: «Anotar un insumo» con el nombre todavía vacío | «Hay algo que escribiste y no se guardó.» | El primer campo que cambió |
| `/compartir`: el nombre y el teléfono de quien reemplaza, y el selector de días | «Hay algo que escribiste y no se guardó.» | El primer campo que cambió |

- **«Seguir escribiendo»** devuelve el aviso a su estado normal (4.1), sin volver a anunciarlo, y lleva el foco al campo que tiene el texto sin guardar. Si no se puede ubicar, el foco va a `#titulo-pagina`.
- **Por qué Insumos tiene su propio título:** en «Compré», «Me quedan» y «Ya lo resolví», Carmen muchas veces no escribe nada, solo toca «Uno más». «Escribiste» sería falso. Además, el `{sección}` de la v0.1 dejaba comillas dentro de comillas («Lo que escribiste en «Compré: Crema humectante» no se guardó.»). El título nuevo lleva solo el nombre del insumo.
- **«Ya lo resolví»** hace la misma pregunta que «Compré», así que se protege igual. En la primera construcción quedó sin proteger, y los dos paneles se comportaban distinto.
- Si `sinGuardar` no sabe dónde está lo que se perdería, el título es «Hay algo que escribiste y no se guardó.» (aprobado el 09-11).

### 4.4 Cargando

Al tocar «Recargar» (o «Recargar igual»), el botón queda `ocupado` y muestra «Recargando…», con `aria-busy`, hasta que el navegador cambia de página. En una conexión lenta del teléfono puede tomar unos segundos, y así no parece que el toque no hizo nada.

### 4.5 «Más tarde»

- El aviso desaparece de inmediato, sin animación de salida, y su texto sale de la región viva (`retirar`).
- **El foco va a `#titulo-pagina`.** Si no existe, va a `#contenido`. Nunca queda en el `body`.
- No hay confirmación ni anuncio.
- Cuándo vuelve: D4. Se guarda solo en memoria, nunca en `localStorage` ni en `sessionStorage`.

### 4.6 Vacío, error y conflicto

- **Sin versión nueva:** no hay nada en la pantalla. El espacio del aviso no se reserva.
- **`version.json` no responde, responde un error o trae un identificador vacío o mal formado:** no pasa nada. Ningún mensaje, ningún error en pantalla ni en la consola. Se intenta de nuevo en la próxima revisión. El aviso es una cortesía, y fallar al revisarlo no es un problema de Carmen.
- **Conflicto (412):** no aplica. El aviso no guarda nada.

---

## 5. Texto al 200% a 320 px, en los dos temas

Con «Texto al 200%» en un teléfono de 320 px, la app mide 160 px efectivos y entra en modo `angosto:`.

- La caja usa `angosto:px-2` y `angosto:gap-2` (los de `Nota`), y el ícono va en la primera línea del título (`iconoEnLinea`), para que el título use todo el ancho.
- Los botones se apilan solos (`flex-wrap`). «Recargar», «Seguir escribiendo» y «Recargar igual» usan `angosto:px-2` (v1.1, antes `angosto:px-3`). Con ese relleno, «Seguir escribiendo» parte entre palabras y no dentro de una. El `overflow-wrap:anywhere` de `Boton` queda solo como resguardo.
- Al pasar al estado sin guardar, la pantalla baja hasta el borde de arriba de la caja antes de enfocar (4.3), para que el título se vea.
- **Sin desplazamiento horizontal:** ninguna palabra del aviso se sale de la caja, ni la caja del `aside` o del `main`.
- En la familia, el aviso queda bajo las secciones apiladas y antes del encabezado (2.1). En el relevo, primero en `main`.
- **En tema oscuro**, lo mismo, con `rocio`, `atenta-fondo` y `turquesa` del tema oscuro. No hay ningún valor propio del tema en el aviso: todo sale de los tokens.

---

## 6. Textos exactos

| Elemento | Familia | Relevo |
|---|---|---|
| Título | «Hay una versión nueva de MATU.» **[PROPUESTO, D1]** | Igual |
| Bajada | «Recarga cuando termines lo que estás haciendo.» **[PROPUESTO, D2]** | «Recarga cuando termines de leer.» **[PROPUESTO, D2]** |
| Botón | «Recargar» · ocupado «Recargando…» | Igual |
| Cerrar | «Más tarde» **[PROPUESTO, D3]** | Igual |
| Anuncio (`status`) | «Hay una versión nueva de MATU. Recarga cuando termines lo que estás haciendo.» | «Hay una versión nueva de MATU. Recarga cuando termines de leer.» |
| Sin guardar, título | Ficha: «Lo que escribiste en «`{sección}`» no se guardó.» · Insumos (v1.1): «Lo que anotaste de «`{nombre}`» no se guardó.» · sin nombre: «Hay algo que escribiste y no se guardó.» | No aplica |
| Sin guardar, bajada | «Si recargas ahora, se pierde.» **[PROPUESTO, D6]** | No aplica |
| Sin guardar, botones | «Seguir escribiendo» · «Recargar igual» (ocupado «Recargando…») **[PROPUESTO, D6]** | No aplica |

Revisados contra lenguaje.md 3: en tú, en voz activa, sin «sesión», «token», «caché», «actualización del sistema» ni ningún código. «Versión» se usa en su sentido de la página, no en el del conflicto de la ficha (6.2), que vive en otra pantalla y en otro tono (`atenta`). Jorge los aprobó el 09-11, incluido el título de Insumos de la v1.1, y van a lenguaje.md, sección 28, «Aviso de versión nueva (MATU-67)». Las marcas **[PROPUESTO]** de la tabla quedan como registro.

---

## 7. Criterios visuales verificables

1. El aviso no tiene `position: fixed`, `absolute` ni `sticky` propio, ni sombra. Cuando aparece, ningún botón de la pantalla ni la barra de secciones queda tapado.
2. A 1280 y 1920 px, en la familia, el aviso está en la barra lateral bajo las secciones, y el título de la página no cambia de posición cuando aparece (se mide su `top` antes y después).
3. A 360 px, en la familia, el aviso está sobre el encabezado de la persona y la barra fija de abajo mide lo mismo que sin aviso.
4. El botón principal de la pantalla sigue siendo el único elemento en `turquesa` macizo. «Recargar» es secundario.
5. «Recargar» y «Más tarde» miden 48 px o más de alto, y los dos muestran el contorno de foco de 3 px al llegar con el teclado.
6. Con el foco en un campo de texto, una versión nueva no muestra el aviso. Al salir del campo con Tab hacia un botón, aparece.
7. En `/compartir/listo`, en «Lo que escribiste no se guardó» y en el alta el aviso no aparece, y si ya estaba a la vista se oculta. Aparece en la pantalla siguiente.
8. Con algo sin guardar en una sección, en un formulario de Insumos (incluido «Ya lo resolví») o en `/compartir`, «Recargar» no recarga. El aviso cambia a `atenta` con ícono y palabras distintas, el borde de arriba de la caja queda a la vista y el foco queda en «Seguir escribiendo». A 320 px con texto al 200%, el título del estado se ve completo.
9. «Más tarde» deja el foco en el título de la página, y el aviso no vuelve al cambiar de pantalla.
10. El lector de pantalla lee el aviso una sola vez, sin leer los botones dentro del anuncio.
11. Con «Texto al 200%» a 320 px, en tema claro y oscuro, no hay desplazamiento horizontal, ninguna palabra se sale de la caja y ningún botón parte una palabra por dentro («Seguir escribiendo» incluido).
12. Con `prefers-reduced-motion`, el aviso aparece sin fundido.
13. Ningún texto del aviso es `text-sm`: todo va en 1 rem o más, también en el proyector.
14. En el relevo, el aviso va primero en `main`, con el texto alineado a la izquierda. En el PIN y los estados va centrado en `max-w-xl`. En la ficha, a 1280 y 1920 px, su borde izquierdo coincide con el de la tarjeta de la ficha, con 2 px de tolerancia.
15. El anillo de «Recargar» y de «Seguir escribiendo» mide 3:1 o más contra el fondo del aviso (`rocio` o `atenta-fondo`) y contra la `hoja` de adentro, en los dos temas.

# MATU-126 · Los enlaces de correo dentro de una frase se tocan con el dedo sin errar · Especificación de diseño

**Versión 1.1 · 19/11/2026** (MATU-127: un enlace que se parte en dos renglones conserva su área táctil; los cambios están en la sección 11 y en 3, 5, 6 y 9) · Versión 1.0 · 18/11/2026 · Agente 6, UI/UX. Especifica y no construye. **Sin tokens nuevos de color, tamaño, espaciado ni sombra.** Se usan la escala de espaciado de Tailwind (`py-3.5` = 0,875 rem desde la v1.1, antes `-inset-y-3.5`; `gap-3`, `gap-6`) y el foco base de la capa `base` de `web/src/index.css`. Lo único nuevo es una capa, `z-1`, que no es un token del `@theme` (Tailwind v4 no saca `z-*` del tema) y queda escrita y justificada en `Demo/DISENO.md`, sección 6 (fila «Enlace dentro de una frase» y la nota «Capas»).

**Origen:** el H3 (P3) del informe TESTER de Martín del 18-11: los enlaces de correo dentro de una frase («pídelo a {correo}») miden 20 a 21 px de alto. WCAG 2.5.8 los exime por ir en línea, pero MATU pide 48 px.

**Dónde viven los tokens de `web/`:** en `web/src/index.css` (su propio `@theme`, con los nombres `turquesa`, `tenue`, etc.). `Demo/src/index.css` es el de la demo y no cambia.

---

## 0. Qué se midió antes de especificar

Medido en Chrome, con el servidor de desarrollo de `web/` y el doble (`/privacidad`, `/cuenta`, `/cuenta/donde-entraste`), contando con `document.elementFromPoint` cada medio píxel en el centro del enlace. La tabla dice **lo que se toca de verdad**, no lo que mide la caja del texto.

| Caso | Caja del texto (`getBoundingClientRect` del `a`) | Área del `::after` | Lo que se toca |
|---|---|---|---|
| Correo de un renglón, 360 px, texto base (`/privacidad`, `/cuenta`, `/cuenta/donde-entraste`) | 21 px | 50,75 px | 51,5 px |
| Correo partido en dos renglones, 320 px, texto al 200 %, oscuro | 42 px por renglón | 156,75 px | 113 px |
| **Correo y otro enlace en renglones seguidos, 1280 px** (`/privacidad`, sección 15 del doble) | 21 px | 50,75 px | **27,5 px**, y la parte de abajo de las letras del correo **abre el otro enlace** (la Biblioteca del Congreso, en otra pestaña) |

**Lo que dicen las medidas:**
1. **El área de 48 px ya existe desde MATU-75**, en un `::after` de `EnlaceEnFrase`. El H3 midió la caja del `a` con `getBoundingClientRect`, que no ve un seudoelemento: por eso dio 21 px. Que no se pueda medir con el método de siempre también es un defecto, porque nadie puede comprobar la regla de los 48 px.
2. **Hay un defecto real que el H3 no vio (P2):** cuando dos enlaces quedan en renglones seguidos, el área del de abajo se dibuja encima de las letras del de arriba. Tocar o hacer clic en la mitad de abajo de «cuidaconmatu@gmail.com» abre otro sitio. Eso es errar con el dedo, que es justo lo que la tarjeta quiere evitar.

---

## 1. Objetivo

Carmen, cansada y con el teléfono en una mano, toca el correo que aparece en medio de una frase y se abre su correo, al primer intento, sin abrir otra cosa por error.

## 2. Jerarquía

No cambia ninguna pantalla. El enlace sigue siendo parte de la frase:
1. La frase, que se lee de corrido.
2. El correo, que se reconoce como enlace por el subrayado y la negrita, no solo por el color.
3. Lo que se toca, que es más alto que el texto pero no se ve.

## 3. Cómo se agranda el área: un `span` vacío dentro del enlace

### 3.1 La decisión

> **Reemplazada en la v1.1 (MATU-127).** El `span` absoluto de esta sección queda con 0 px de ancho cuando el enlace empieza a mitad de renglón y su último renglón termina más a la izquierda (sección 11.1). **La forma vigente es la de 11.2:** el área es un `span` en línea, sin posición, con `py-3.5`, que envuelve al `span` del texto. El foco no cambia: sigue en el `a`. Lo de 3.1 a 3.4 queda como historia de la decisión; 3.3 (el texto en `z-1`) y 3.4 (la medida en rem) siguen valiendo.

Se mantenía la idea de MATU-75 (un área absoluta que no mueve los renglones), pero **el área deja de ser un `::after` y pasa a ser un `span` vacío y `aria-hidden`** dentro del `a`. Y **el texto del enlace va en un segundo `span`, por encima de toda área**.

```
<a class="relative font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa">
  <span aria-hidden="true" data-area-tactil class="absolute inset-x-0 -inset-y-3.5"></span>
  <span class="relative z-1">cuidaconmatu@gmail.com</span>
</a>
```

El esquema es de referencia para el frontend: los nombres de las clases son los de esta especificación, el armado del componente es suyo.

### 3.2 Por qué así, y no las otras dos formas

| Forma | Qué pasa | Veredicto |
|---|---|---|
| Relleno vertical con margen negativo (`py-3.5 -my-3.5`) | En un elemento en línea, el margen vertical **no hace nada**: el relleno no mueve los renglones, pero el contorno de foco rodea el relleno y **tacha el renglón de arriba y el de abajo**. Ya se probó y se descartó en MATU-75 (v0.1, revisión del 09-11) | Descartada |
| `::after` absoluto (lo de hoy) | No mueve los renglones y el contorno sigue al texto. Pero **no se puede medir** con `getBoundingClientRect`, ni probar en `jsdom`, ni seleccionar con el dedo en las herramientas del navegador del teléfono | Se reemplaza |
| **`span` vacío absoluto (esta especificación)** | La misma geometría que el `::after`, medida en pantalla: 50,8 px por `getBoundingClientRect` y 51,5 px de lo que se toca. Se mide con el método del H3 y la prueba unitaria puede verificar que está | **Elegida** |

**El `span` del área no cambia nada para quien usa lector de pantalla:** está vacío y lleva `aria-hidden="true"`, así que el nombre del enlace sigue siendo el correo. Al copiar la frase no aparece nada extra.

### 3.3 Por qué el texto va en un `span` con `z-1`

El área es un elemento posicionado, así que se dibuja sobre el texto normal de la página. Entre dos enlaces, el que viene después en la página queda encima. Por eso el área del enlace de abajo le quitaba las letras al de arriba (sección 0, tercera fila).

Con el texto de cada enlace en `relative z-1`, **las letras de cualquier enlace quedan por encima de cualquier área**. Probado en pantalla, a 1280 px con los dos enlaces de `/privacidad` en renglones seguidos:
- Antes: el correo se tocaba en 27,5 px y la parte de abajo de sus letras abría la Biblioteca del Congreso.
- Con el `span` en `z-1`: ninguna letra de un enlace abre el otro. El correo se toca en 36,5 px y el de abajo en 51,5 px.

El subrayado del `a` sigue dibujándose bajo el texto del `span` (verificado en tema claro y oscuro). El contorno de foco sigue en el `a` y rodea el texto, no el área: con el foco a 320 px y el texto al 200 %, el contorno de cada renglón no tacha el renglón vecino (verificado).

**`z-1` es la capa más baja que existe en `web/`.** Las otras son `z-10` (el imán y los puntos de «Su día»), `z-20` (la barra de secciones fija abajo en el teléfono) y `z-30` (el salto «Ir al contenido»). El texto de un enlace nunca se dibuja sobre la barra fija. Quedan escritas en `Demo/DISENO.md`, sección 6, nota «Capas».

### 3.4 La medida, en rem

`-inset-y-3.5` es 0,875 rem: 14,9 px con el texto base y 29,75 px con el texto al 200 %. El área crece con el texto. Con el texto base, el área de un renglón mide 21 + 2 × 14,9 ≈ 51 px. Con el texto al 200 % mide unos 102 px por renglón. Nunca baja de 48 px.

**Ninguna medida nueva.** Es la misma escala de espaciado de MATU-75.

## 4. Dos enlaces en renglones seguidos

Con un interlineado de 25,5 a 27,6 px, dos enlaces en renglones seguidos están a menos de 48 px. **Las dos áreas no pueden medir 48 px cada una sin pisarse.** Se resuelve en dos partes.

### 4.1 Lo que garantiza el componente, siempre

Con el texto en `z-1` (3.3), **las letras de un enlace siempre abren ese enlace**. Las áreas se reparten solo el espacio entre renglones y por encima y por debajo de ellos, y ahí manda el de abajo. En el peor caso medido, el de arriba se toca en 36,5 px, sobre los 24 px de WCAG 2.5.8, y ninguna letra abre el otro destino.

### 4.2 Lo que garantiza la composición, en cada pantalla

Para que cada enlace tenga sus 48 px completos:
- **Un solo enlace dentro de una frase por párrafo.** Si una frase necesita dos destinos, se parte en dos párrafos, o uno de los dos pasa a ser un enlace solo (`EnlaceRuta`, `inline-flex min-h-12`).
- **Entre dos párrafos que llevan enlace, `1.5rem` o más** (`gap-6` o `mt-6`). Así las dos áreas, de 0,875 rem cada una hacia el otro, no se tocan con el texto base ni al 200 %.
- **Entre el párrafo del enlace y otro control** (botón, campo, enlace solo, casilla), **`0.75rem` o más** (`gap-3`). El área sale unos 11 a 12 px del renglón con el texto base, y unos 25 px con el texto al 200 %. Con `0.75rem` no tapa el borde de un botón.
- **El texto de un enlace dentro de una frase mide 48 px de ancho o más**, porque el área no se ensancha a los lados. Hoy todos lo cumplen: los correos, «Ver tu pedido», «app de MATU para familias», «política de privacidad (se abre en otra pestaña)». Nunca «aquí» ni «acá».

**La excepción es el texto de los documentos** (`/privacidad` y `/condiciones-pedido`), que se escribe en `docs/legal/` y no en la pantalla. Ahí vale 4.1. El párrafo de la sección 15 del doble («Escríbenos a… Un enlace a otro sitio…») se queda como está: **es el caso de prueba** de dos enlaces en renglones seguidos.

## 5. Foco y estado

- **Foco:** el foco base de `web/src/index.css`, sin cambios, en el `a`. Con la forma de la v1.1 se ve **idéntico al de la v1.0**, píxel a píxel (11.3): el relleno del área está en un `span` hijo y el contorno del `a` no lo rodea. Contorno de 3 px en `turquesa` con 2 px de separación, que rodea las letras renglón por renglón (6,0:1 sobre `papel` en claro y 9,4:1 en oscuro). El área no lleva contorno ni fondo, y nunca recibe el foco: no es un elemento interactivo aparte.
- **El enlace no se reconoce solo por el color:** lleva negrita y subrayado `decoration-turquesa/40`, que pasa a subrayado pleno al pasar el puntero.
- **Presionado:** el comportamiento del navegador. Sin animación.
- **Con `prefers-reduced-motion`:** no hay nada que animar.
- **Estados vacío, cargando, error y conflicto:** no aplican al enlace. Si no hay correo (`correo_contacto` en `null`), la frase cambia por la de «sin correo» que ya existe (`FraseConCorreo`, `sinCorreo`), sin cambios.

## 6. Esquemas

**A 360 px, texto base** (`/cuenta`, «Cómo pedir»):

```
┌─ 360 ───────────────────────────────┐
│ Para cambiar tu nombre o tu correo, │
│ pídelo a ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │  ← el área sube 15 px sobre el renglón
│          cuidaconmatu@gmail.com     │  ← el texto, 21 px, encima de toda área
│ desde el ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │  ← el área baja 15 px: 51 px en total
│ correo de tu cuenta.                │
└─────────────────────────────────────┘
```

**A 320 px, texto al 200 %:** el correo se parte en dos renglones («cuidaconmatu@g» / «mail.com») sin desplazamiento horizontal. El área cubre los dos renglones y algo más (113 px de lo que se toca medidos en `/privacidad`).

**Un enlace que empieza a mitad de renglón y se parte (v1.1, 11.4):** cada renglón del enlace tiene su propia área, del ancho de sus letras y 50,8 px de alto con el texto base (101,5 px con el texto al 200 %).

```
┌─ 360 ───────────────────────────────┐
│                         ┄┄┄┄┄┄┄┄┄┄  │  ← el área del renglón 1 sube 15 px
│ ¿Cuidas a alguien? Entra en la app de│  ← «app de»: 55 px de ancho
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄    ┄┄┄┄┄┄┄┄┄┄  │  ← las dos áreas se juntan entre renglones
│ MATU para familias.                 │  ← «MATU para familias»: 157 px de ancho
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄                 │  ← el área del renglón 2 baja 15 px
└─────────────────────────────────────┘
```

**En pantalla ancha (1280 y 1920 px):** igual que a 360 px. Si la frase lleva dos enlaces (solo en los documentos, 4.2), el de arriba conserva todas sus letras.

## 7. Componentes y alcance

**Un solo componente cambia:** `EnlaceEnFrase`, en `web/src/compartido/ui/Enlaces.tsx`. Todo enlace dentro de una frase pasa por él. **No se crea otro componente.**

Además, para que ningún correo largo desborde a 320 px:
- **`EnlaceEnFrase` aplica `[overflow-wrap:anywhere]` por su cuenta cuando `href` empieza con `mailto:`**, y se quita de cada llamada. Hoy lo lleva cada pantalla a mano y `Resumen.tsx:358` no lo tiene.

**Lo que cubre** (todas las llamadas de hoy, por `grep` en `web/src`):

| Pantalla | Archivo y línea | Enlace |
|---|---|---|
| Tu cuenta, «Cómo pedir» | `familia/Cuenta.tsx:132` | Correo de privacidad (`mailto:`) |
| Dónde entraste | `familia/DondeEntraste.tsx:228` | Correo de privacidad (`mailto:`) |
| Datos de la persona, tres frases (rectificar, documento del representante, sin asociar) | `familia/DatosPersona.tsx:221`, `:310` y `:821`, por `FraseConCorreo` de `familia/PiezasMisDatos.tsx:494` | Correo de privacidad (`mailto:`) |
| Pago, condiciones («Si algo no está bien…») | `familia/Pago.tsx:841` | Canal de reclamo (`mailto:`) |
| Resumen del pedido, «Quién vende» | `familia/Resumen.tsx:358` | Canal de reclamo (`mailto:`) |
| Tus pedidos, retracto rechazado | `familia/TusPedidos.tsx:1002` | Correo de contacto (`mailto:`) |
| Tus pedidos, «Arrepentirme» fuera de plazo | `familia/TusPedidos.tsx:1060` | Correo de contacto (`mailto:`) |
| `/privacidad` y `/condiciones-pedido` | `privacidad/Documento.tsx:37` y `:41` (desde `privacidad/markdown.ts`) | Correos (`mailto:`), enlaces externos y anclas del documento |
| Crear cuenta, la casilla | `familia/Alta.tsx:153` (`EnlacePoliticaEnFrase`) | Política de privacidad |
| Autorizaciones del alta y de insumos | `familia/Alta.tsx:717` e `Insumos.tsx:1476` (`LeePoliticaAntesDeAutorizar`) | Política de privacidad |
| Catálogo, «En tu pedido» | `familia/Catalogo.tsx:309` | Ver tu pedido |
| Entrar del comercio y de operación | `comercio/Entrar.tsx:141` y `operacion/Entrar.tsx:164` | app de MATU para familias |

**No cubre** `EnlacePoliticaSolo` ni `EnlaceRuta`: son enlaces solos, con `inline-flex min-h-12`, y ya miden 48 px.

## 8. Textos

**No cambia ningún texto.** El enlace sigue diciendo el correo tal cual, sin «escríbenos aquí».

## 9. Cómo se verifica

### 9.1 En el navegador (la revisión visual y Martín)

En cada pantalla de la sección 7 que se pueda abrir con el doble, a **360, 1280 y 1920 px**, en **tema claro y oscuro**, y a **320 px con el texto al 200 %**, se pega esto en la consola (v1.1: mide **cada renglón** del enlace, no solo el primero):

```js
[...document.querySelectorAll('a')].filter(a => a.querySelector('[data-area-tactil]')).map(a => {
  const area = [...a.querySelector('[data-area-tactil]').getClientRects()].filter(r => r.width > 0)
  const texto = [...a.querySelector('.z-1').getClientRects()].filter(r => r.width > 0)
  const renglones = texto.map((r, i) => {
    const x = r.left + r.width / 2
    let ini = null, fin = null
    for (let y = r.top - 45; y <= r.bottom + 45; y += 0.5) {
      if (document.elementFromPoint(x, y)?.closest('a') === a) { ini ??= y; fin = y }
    }
    return { ancho: Math.round(r.width), area: Math.round(area[i]?.height ?? 0), seToca: ini === null ? 0 : fin - ini + 0.5 }
  })
  return { enlace: a.textContent.trim(), renglones }
})
```

Antes de pegarlo, el enlace tiene que estar a la vista (`elementFromPoint` solo ve lo que está en pantalla).

**Criterios (v1.1):**
1. En **cada renglón** de todo enlace dentro de una frase, `area` mide **48 o más**, en los cinco casos (360, 1280 y 1920 claro y oscuro, y 320 al 200 %). Se mide con `getClientRects` del área, renglón por renglón: el `getBoundingClientRect` de un enlace de dos renglones es la caja que los junta y no dice si un renglón quedó sin área. Valores esperados: 50,8 px con el texto base y 101,5 px con el texto al 200 %.
2. En **cada renglón**, `seToca` mide **48 o más** en todo enlace que cumple la composición de 4.2. En los documentos (4.2, excepción) mide 24 o más. **Ningún renglón mide 22 px** (el defecto de MATU-127).
3. **Ninguna letra de un enlace abre otro:** en `/privacidad`, sección 15 del doble, a 1280 px, un toque en la mitad de abajo de «cuidaconmatu@gmail.com» abre el correo, no la Biblioteca del Congreso.
4. **El área no tapa ningún control:** un toque en el borde de arriba y en el de abajo de cada botón, campo o casilla cercano activa ese control y no el enlace.
5. `document.documentElement.scrollWidth` es igual al ancho de la ventana a 320 px con el texto al 200 % (sin desplazamiento horizontal), también en «Quién vende» del resumen.
6. Con Tab, el contorno de foco rodea las letras del enlace, renglón por renglón, y no tacha el texto del renglón de arriba ni el de abajo. **Se ve igual que en la v1.0** (11.3).
7. El subrayado se ve en claro y en oscuro, bajo todas las letras del enlace.
8. Con el lector de pantalla, el enlace se anuncia solo con su texto (el correo), una vez.
9. En el teléfono, con la barra de secciones fija abajo, un enlace que pasa por debajo de la barra no se dibuja encima de ella.
10. **La frase no se mueve:** con el enlace en la v1.1, la pantalla se ve igual que con la v1.0 (los renglones no se separan ni se corren).

### 9.2 En las pruebas unitarias (sugerencia para el frontend)

`jsdom` no calcula medidas, así que la prueba verifica la estructura (v1.1, 11.2):
- `EnlaceEnFrase` tiene **un único** `[data-area-tactil]`, que es un `span` hijo directo del `a`.
- El área **envuelve** al texto: dentro de ella hay un `span` con `relative` y `z-1`, y ese `span` tiene el texto. El área tiene el mismo `textContent` que el enlace.
- El área lleva `py-3.5` y **no** lleva `absolute`, `relative`, `inline-block`, `inline-flex`, `block` ni `aria-hidden` (con `aria-hidden` el enlace se quedaría sin nombre, porque ahora el área contiene el texto).
- El `a` sigue con `relative` (11.2, tercera fila de la tabla).
- El nombre accesible del enlace (`getByRole('link', { name })`) es su texto, una vez.
- Un `href` con `mailto:` lleva `[overflow-wrap:anywhere]` en el `a` sin que la pantalla lo pida; un `href` que no es `mailto:` no lo lleva.

## 10. Lo que no decide esta especificación (para el orquestador)

**Los correos de los documentos legales no son enlaces.** En `backend/app/modules/iam/politica/politica-0.24.md` y en las condiciones del pedido, «escribe a cuidaconmatu@gmail.com» está escrito como texto plano, sin `[…](mailto:…)`. En `/privacidad` y `/condiciones-pedido` ese correo **no se puede tocar**: hay que copiarlo a mano. Convertirlo en enlace cambia el texto de la política (versión nueva y su registro), que es de `docs/legal/` y del backend, no de diseño. Si se hace, 4.2 pide un solo correo enlazado por párrafo.

---

## 11. v1.1 · MATU-127: un enlace que se parte en dos renglones conserva su área táctil

### 11.1 El defecto, medido

El área de la v1.0 es **una sola caja absoluta** (`absolute inset-x-0 -inset-y-3.5`). Cuando el `a` se parte en renglones, el navegador calcula esa caja entre el borde izquierdo del primer renglón y el borde derecho del último. Si el enlace empieza a mitad de renglón y su último renglón termina más a la izquierda que donde empezó, la caja queda con **0 px de ancho**, y solo se tocan las letras.

Medido en Chrome 157 con el doble, contando con `elementFromPoint` cada medio píxel en el centro de cada renglón:

| Pantalla | Caso | Área (`getBoundingClientRect`) | Lo que se toca, por renglón |
|---|---|---|---|
| Entrar del comercio (`/comercio/entrar`), «app de MATU para familias» | 360 px, texto base | **0 × 76 px** | 22 y 22 px |
| Entrar del comercio | 320 px, texto al 200 %, tres renglones | 0 × 203,5 px | 43 a 94 px (el mínimo, 43, en el borde de cada renglón) |
| Entrar a operación (`/operacion/entrar`), el mismo enlace | 360 px, claro y oscuro | 0 de ancho | 21,5 px |
| Crear cuenta (`/crear-cuenta`), la casilla, «política de privacidad (se abre en otra pestaña)» | 360 px, tres renglones | 0 de ancho | 21,5 px |
| `/privacidad`, sección 15, «la Biblioteca del Congreso Nacional (se abre en otra pestaña)» | 360 px, dos renglones | 0 de ancho | 22 px |

A 1280 y 1920 px esos enlaces caben en un renglón y miden 51,5 px. **El defecto es del teléfono**, que es donde está Carmen.

### 11.2 La decisión: el área es un `span` en línea que envuelve al texto

El área deja de ser una caja absoluta y pasa a ser **un `span` en línea, sin posición, con relleno vertical**, que envuelve al `span` del texto. Un elemento en línea se parte con la frase: **el navegador le da a cada renglón su propio pedazo de área**, del ancho de las letras de ese renglón y 0,875 rem por arriba y por abajo. El relleno vertical de un elemento en línea no mueve los renglones.

```
<a class="relative font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa">
  <span data-area-tactil class="py-3.5">
    <span class="relative z-1">app de MATU para familias</span>
  </span>
</a>
```

**Qué cambia en `EnlaceEnFrase`** (`web/src/compartido/ui/Enlaces.tsx`), y nada más:
1. El `span` vacío `aria-hidden` con `absolute inset-x-0 -inset-y-3.5` **se quita**.
2. Un `span` con `data-area-tactil` y `py-3.5` **envuelve** al `span` del texto (`relative z-1`, sin cambios). El área **no lleva `aria-hidden`**: ahora contiene el texto, y con `aria-hidden` el enlace se quedaría sin nombre.
3. El área queda **en línea**: sin `absolute`, `relative`, `inline-block`, `inline-flex` ni `block`. Con `inline-block` el enlace dejaría de partirse con la frase y volvería el desbordamiento a 320 px.
4. El `a` **conserva todas sus clases**, `relative` incluida, y el `[overflow-wrap:anywhere]` de los `mailto:`.
5. El comentario del componente se actualiza: el área ya no es un `span` vacío ni absoluto.

No cambia ninguna llamada a `EnlaceEnFrase`, ni `EnlacePoliticaEnFrase`, ni `LeePoliticaAntesDeAutorizar`. **Ningún token nuevo:** `py-3.5` es el mismo 0,875 rem de la v1.0.

**Las formas que se probaron en el navegador** (inyectando cada una sobre el DOM que arma `EnlaceEnFrase`, en las mismas pantallas y anchos):

| Forma | Qué pasa | Veredicto |
|---|---|---|
| `span` absoluto (v1.0) | 0 px de ancho en los enlaces partidos (11.1) | Se reemplaza |
| Relleno con `box-decoration-break: clone` | Vuelve el defecto de `/privacidad` §15: el área del enlace de abajo tapa las letras del de arriba | Descartada antes de esta versión |
| `span` en línea con `py-3.5` y `relative` | Mide lo mismo que la elegida, pero el área queda en la capa de los elementos posicionados sin necesidad | Descartada: una capa más sin ganancia |
| `span` en línea con `py-3.5`, sin `relative` en el `a` | En `/privacidad`, a 360 px, el correo baja a **39 px** de lo que se toca, porque el área del enlace de abajo le gana. Con `relative` en el `a` mide 51 | Descartada: el `a` tiene que seguir con `relative` |
| **`span` en línea con `py-3.5`, sin posición, y el `a` con `relative`** | Cada renglón mide 50,8 px de área y 50,5 a 52 px de lo que se toca. Todo lo de MATU-126 se mantiene (11.3) | **Elegida** |

### 11.3 Lo que se mantiene de MATU-126, medido

Medido con la forma elegida, en Chrome 157, en `/comercio/entrar`, `/operacion/entrar`, `/crear-cuenta`, `/privacidad`, `/cuenta`, `/cuenta/donde-entraste` y `/insumos/pedido/resumen`, a 360 px claro y oscuro, 1280 px oscuro, 1920 px claro y 320 px con el texto al 200 %:

| Lo que garantiza MATU-126 | v1.0 | v1.1 |
|---|---|---|
| Lo que se toca, el peor renglón, texto base | **21,5 px** (enlaces partidos) | **50,5 px** (operación, 360 px) |
| Lo que se toca, el peor renglón, texto al 200 % | 43 px | 102 px |
| Área por renglón (`getClientRects` del área) | 0 × 76 px en «app de MATU para familias» | 55 × 50,8 y 157 × 50,8 px; al 200 %, 101,5 px por renglón |
| Ninguna letra de un enlace abre otro (puntos en cada renglón de cada enlace, 15 por renglón) | 0 robos | **0 robos**, también en `/privacidad` §15 a 1280 px, donde el correo se sigue tocando en 36 px (4.1) |
| El área no tapa botones, campos ni casillas (bordes y centro de cada control a 80 px o menos) | 0 | **0** |
| La barra fija de «Tu cuenta» y del resumen, a 360 px | queda encima | **queda encima** |
| El foco | — | **idéntico píxel a píxel** a la v1.0 (capturas de Tab en `/comercio/entrar` a 360 px claro y a 320 px al 200 % oscuro, y en `/privacidad` a 1280 px). El contorno del `a` rodea las letras y no el relleno del `span` hijo, así que no tacha los renglones vecinos |
| Desplazamiento horizontal a 320 px con el texto al 200 % | ninguno | **ninguno** (`scrollWidth` = 320 en todas) |
| La frase no se mueve | — | **idéntica píxel a píxel** a la v1.0 sin foco |

**No hay que sacrificar ningún criterio.**

**Por qué el `py-3.5` en un hijo no repite el defecto de MATU-75 (3.2, primera fila):** allí el relleno estaba en el propio `a`, y el contorno de foco del `a` rodeaba su relleno y tachaba los renglones vecinos. Aquí el relleno está en un `span` hijo, y Chrome dibuja el contorno del `a` alrededor de sus propios renglones, sin el relleno del hijo. Medido: las capturas de foco de la v1.0 y de la v1.1 son el mismo archivo (mismo MD5).

### 11.4 Lo que cambia para quien mide

- **El `getBoundingClientRect` del área de un enlace de dos renglones no sirve para medir:** junta los dos renglones en una sola caja (76 px de alto a 360 px) y diría que todo está bien aunque un renglón no tuviera área. Se mide con `getClientRects`, renglón por renglón (9.1, criterio 1).
- El 4.2 sigue igual. El ancho mínimo de 48 px se cuenta sobre el texto completo del enlace, no sobre cada renglón: el último renglón de un correo partido puede ser corto («mail.com»), pero se junta con el área del renglón de arriba.

### 11.5 Pantallas a revisar después de construir

Las de la tabla de la sección 7, todas, con el guion de 9.1 y en los cinco casos. **Con prioridad, las que tienen enlaces que se parten a 360 px:**

| Pantalla | Ruta del doble | Enlace | Qué mirar |
|---|---|---|---|
| Entrar del comercio | `/comercio/entrar` | app de MATU para familias | Dos renglones a 360 px: cada uno 48 px o más |
| Entrar a operación | `/operacion/entrar` | app de MATU para familias | Igual |
| Crear cuenta, la casilla | `/crear-cuenta` | política de privacidad (se abre en otra pestaña) | Tres renglones a 360 px; un toque en el área no marca la casilla ni la tapa |
| Autorizaciones del alta y de insumos | `/crear-cuenta` (paso de autorizaciones) e insumos | política de privacidad (se abre en otra pestaña) | Igual que la casilla |
| `/privacidad`, sección 15 | `/privacidad` | el correo y la Biblioteca del Congreso | A 1280 px, la mitad de abajo del correo abre el correo; a 360 px, los dos renglones de la Biblioteca miden 48 px o más |
| «Quién vende» del resumen | `/insumos/pedido/resumen` | canal de reclamo | 320 px al 200 %, sin desplazamiento horizontal; la barra fija queda encima a 360 px |
| Tu cuenta y Dónde entraste | `/cuenta`, `/cuenta/donde-entraste` | correo de privacidad | La barra fija queda encima a 360 px |

Y en cada una, el foco con Tab a 1280 px claro y a 320 px al 200 % (criterio 6), y una captura sin foco para comparar con la v1.0 (criterio 10).

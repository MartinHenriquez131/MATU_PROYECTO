# MATU-126 · Los enlaces de correo dentro de una frase se tocan con el dedo sin errar · Especificación de diseño

**Versión 1.0 · 18/11/2026** · Agente 6, UI/UX. Especifica y no construye. **Sin tokens nuevos de color, tamaño, espaciado ni sombra.** Se usan la escala de espaciado de Tailwind (`-inset-y-3.5` = 0,875 rem, `gap-3`, `gap-6`) y el foco base de la capa `base` de `web/src/index.css`. Lo único nuevo es una capa, `z-1`, que no es un token del `@theme` (Tailwind v4 no saca `z-*` del tema) y queda escrita y justificada en `Demo/DISENO.md`, sección 6 (fila «Enlace dentro de una frase» y la nota «Capas»).

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

Se mantiene la idea de MATU-75 (un área absoluta que no mueve los renglones), pero **el área deja de ser un `::after` y pasa a ser un `span` vacío y `aria-hidden`** dentro del `a`. Y **el texto del enlace va en un segundo `span`, por encima de toda área**.

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

- **Foco:** el foco base de `web/src/index.css`, sin cambios. Contorno de 3 px en `turquesa` con 2 px de separación, que rodea las letras renglón por renglón (6,0:1 sobre `papel` en claro y 9,4:1 en oscuro). El área no lleva contorno ni fondo, y nunca recibe el foco: no es un elemento interactivo aparte.
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

En cada pantalla de la sección 7 que se pueda abrir con el doble, a **360, 1280 y 1920 px**, en **tema claro y oscuro**, y a **320 px con el texto al 200 %**, se pega esto en la consola:

```js
[...document.querySelectorAll('a')].filter(a => a.querySelector('[data-area-tactil]')).map(a => {
  const area = a.querySelector('[data-area-tactil]').getBoundingClientRect()
  const r = a.getClientRects()[0], x = r.left + Math.min(r.width / 2, 10)
  let ini = null, fin = null
  for (let y = r.top - 40; y <= r.bottom + 40; y += 0.5) {
    if (document.elementFromPoint(x, y)?.closest('a') === a) { ini ??= y; fin = y }
  }
  return { enlace: a.textContent.trim(), area: Math.round(area.height), seToca: ini === null ? 0 : fin - ini + 0.5 }
})
```

Antes de pegarlo, el enlace tiene que estar a la vista (`elementFromPoint` solo ve lo que está en pantalla).

**Criterios:**
1. `area` mide **48 o más** en todo enlace dentro de una frase, en los cinco casos (360, 1280 y 1920 claro y oscuro, y 320 al 200 %). Es la medida por `getBoundingClientRect` que pide la tarjeta.
2. `seToca` mide **48 o más** en todo enlace que cumple la composición de 4.2. En los documentos (4.2, excepción) mide 24 o más.
3. **Ninguna letra de un enlace abre otro:** en `/privacidad`, sección 15 del doble, a 1280 px, un toque en la mitad de abajo de «cuidaconmatu@gmail.com» abre el correo, no la Biblioteca del Congreso.
4. **El área no tapa ningún control:** un toque en el borde de arriba y en el de abajo de cada botón, campo o casilla cercano activa ese control y no el enlace.
5. `document.documentElement.scrollWidth` es igual al ancho de la ventana a 320 px con el texto al 200 % (sin desplazamiento horizontal), también en «Quién vende» del resumen.
6. Con Tab, el contorno de foco rodea las letras del enlace, renglón por renglón, y no tacha el texto del renglón de arriba ni el de abajo.
7. El subrayado se ve en claro y en oscuro, bajo todas las letras del enlace.
8. Con el lector de pantalla, el enlace se anuncia solo con su texto (el correo), una vez.
9. En el teléfono, con la barra de secciones fija abajo, un enlace que pasa por debajo de la barra no se dibuja encima de ella.

### 9.2 En las pruebas unitarias (sugerencia para el frontend)

`jsdom` no calcula medidas, así que la prueba verifica la estructura: `EnlaceEnFrase` tiene un único `[data-area-tactil]` con `aria-hidden="true"` y sin texto, su texto está en un `span` con `z-1`, el nombre accesible es el texto, y un `href` con `mailto:` lleva `[overflow-wrap:anywhere]` sin que la pantalla lo pida.

## 10. Lo que no decide esta especificación (para el orquestador)

**Los correos de los documentos legales no son enlaces.** En `backend/app/modules/iam/politica/politica-0.24.md` y en las condiciones del pedido, «escribe a cuidaconmatu@gmail.com» está escrito como texto plano, sin `[…](mailto:…)`. En `/privacidad` y `/condiciones-pedido` ese correo **no se puede tocar**: hay que copiarlo a mano. Convertirlo en enlace cambia el texto de la política (versión nueva y su registro), que es de `docs/legal/` y del backend, no de diseño. Si se hace, 4.2 pide un solo correo enlazado por párrafo.

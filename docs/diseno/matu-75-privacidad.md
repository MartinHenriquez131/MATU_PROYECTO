# MATU-75 · La política de privacidad, visible · Especificación de diseño

**Versión 0.3 · 09-11-2026 · agente 6 UI/UX.** La v0.3 sale de la segunda revisión visual (09-11): la etiqueta de la casilla pasa a `py-3` en vez de `@2xl/main:items-center` (2.4), y `EnlacePoliticaSolo` lleva `items-start py-3` (5.3). La v0.2 sale de la revisión visual del 09-11: el área táctil del enlace dentro de una frase pasa a un `::after` (sección 7), se saca el salto a un ancla al abrir la página (1.9), y se precisan la nota del 409 (2.5), las tablas apiladas (1.8) y la distancia entre la casilla y su error (2.4). La v0.1 era la especificación previa. Base: `Demo/DISENO.md` (secciones 2, 3, 4 y 6), los tokens de `web/src/index.css`, las decisiones D1 a D7 de Jorge del 09-11 y las condiciones del analista (revisión previa de MATU-75), `docs/lenguaje.md` (solo lectura) y lo ya construido en `web/src/main.tsx`, `web/src/relevo/Marco.tsx`, `web/src/relevo/PantallaPin.tsx` (`AvisoDatos`), `web/src/familia/Alta.tsx` (`MarcoAlta`, `CrearCuenta`, `DeclaracionFicha`), `web/src/familia/Insumos.tsx` (el permiso de insumos), `web/src/familia/Cuenta.tsx` (`TuCuenta`), `web/src/familia/ui.tsx` y `web/src/compartido/ui/`. **Sin tokens nuevos ni colores nuevos.** Lo único que se agrega a DISENO.md es una fila en la sección 6: el enlace dentro de una frase (sección 7 de esta especificación).

Los textos marcados **[aprobado, D6]** son los de la tabla D6 y van tal cual. Los marcados **[PROPUESTO]** no están en D6 y los decide Jorge (sección 0).

---

## 0. Lo que tiene que decidir alguien más

### Para Jorge (textos que faltan, con la opción por defecto)

| # | Pregunta | Propuesta (opción por defecto) |
|---|---|---|
| J1 | Rótulo del índice de `/privacidad` | «Índice» **[PROPUESTO]**. Es la palabra de un libro o un documento, la que usaría Carmen. Se descartaron «Contenido» y «En esta página» |
| J2 | Enlace al final de cada sección, en el teléfono | «Volver al índice» **[PROPUESTO]** |
| J3 | Cuando la política cambia mientras Carmen crea su cuenta (el servidor rechaza la huella, D2, P2) | Una nota `atenta` con el título «Actualizamos la política de privacidad.» y el texto «Cambió mientras creabas tu cuenta. Léela de nuevo y vuelve a marcar la casilla.» **[PROPUESTO]**. La casilla se desmarca. Lo demás que escribió sigue ahí |
| J4 | El enlace de «Tu cuenta» para leer la política | Se usa el texto que ya está aprobado en lenguaje 7.5 para el relevo: «Política de privacidad (se abre en otra pestaña)». No hace falta un texto nuevo. **Si Jorge prefiere que no haya enlace en «Tu cuenta»**, la fila queda solo con el dato |
| J5 | ¿El aviso «(se abre en otra pestaña)» se ve, o solo lo lee el lector de pantalla? | **Se ve**, como ya se ve en el relevo y como dice D6 («{texto} (se abre en otra pestaña)»). Carmen sabe así que no pierde lo que escribió en el formulario |

### Para el orquestador (no son de diseño, pero la pantalla depende de ellos)

- **G1 · `/privacidad` no monta la app de la familia.** `AppFamilia` monta `ProveedorFamilia`, que pide la sesión al abrir. La página pública tiene que ser **su propia rama en `main.tsx`**, como `/r`, antes de la familia, con `RegionesVivas` y nada más. Así no hay sesión ni petición con la cuenta. Además, `GET /v1/politica` se pide **sin credenciales** (`credentials: 'omit'` o su equivalente en Axios), para que el navegador no mande la cookie de una sesión abierta (condición del analista: sin sesión ni cookies).
- **G2 · Contrato que la pantalla necesita.** El backend lo define en `docs/api/`, y el frontend no lo inventa:
  - `GET /v1/politica`: la versión, la fecha de actualización (para «actualizada el DD/MM/AAAA»), la huella y el texto en markdown.
  - El alta: el campo con la huella que se mostró, y el error (código y `type`) cuando la huella ya no es la vigente (J3).
  - `GET /v1/cuenta`: la versión aceptada y la fecha, o nada si no hay registro (sección 5).
  - **El correo `{correo_privacidad}`** que va en «Tu cuenta». Propuesta: que `GET /v1/politica` lo traiga junto con la versión, para que haya una sola fuente. Mientras no exista la dirección (D5), el párrafo de «Tu cuenta» **no se muestra**: nunca se ve `{correo_privacidad}` ni una dirección inventada.
- **G3 · El texto se muestra tal cual llega.** La huella se calcula sobre el texto exacto (D2), así que el cliente **no reemplaza nada**: «Todavía no lo definimos.» ya tiene que venir escrito en el texto que sirve la API. El markdown se convierte a HTML **sin HTML crudo** (ni `dangerouslySetInnerHTML` con lo que traiga el texto) y sin dependencias desde una CDN.
- **G4 · Contenido que no es de diseño, para el analista.** Al revisar el texto que se va a mostrar (desde «En un minuto»):
  - La sección 5 tiene identificadores del sistema y una huella SHA-256 de 64 caracteres en `code` (`aviso_cuidador_de_hecho`, `declaracion_consumo_representante_legal`…). lenguaje.md 3 prohíbe códigos en la interfaz. Esta especificación los deja legibles y sin desborde (sección 2.5), pero Carmen no los entiende.
  - Al cambiar cada `[PENDIENTE: …]` por «Todavía no lo definimos.» quedan frases rotas, por ejemplo «escribe a Todavía no lo definimos.» y «Respondemos dentro de Todavía no lo definimos.» (sección 10). D4 y D7 resuelven esas dos, pero conviene revisar todas las que quedan a mitad de frase.
- **G5 · `Nota` y las piezas compartidas.** `Nota`, `MensajeError` y `useDemora` viven en `familia/`. La página pública no usa el marco de la familia, pero sí esas piezas (secciones 2.6 y 3). Cómo se reparten, o si pasan a `compartido/ui/`, lo decide el frontend.
- **G6 · El aviso de versión nueva (MATU-67)** no se muestra en `/privacidad`. La página se lee y se cierra, y la política llega de la API, no del paquete de la app.
- **G7 · El relevo.** `RUTA_POLITICA` pasa a `'/privacidad'` (`relevo/textos.ts`). D7 cambia también el texto de `AVISO` (lenguaje 7.5, con el correo). Ver la sección 6.

---

## 1. La página pública `/privacidad`

### 1.1 Objetivo y jerarquía

**Objetivo, desde la persona:** «Quiero saber qué hace MATU con mis datos y los de mi mamá, y encontrar rápido la parte que me importa, sin crear una cuenta.»

**Jerarquía:**
1. El título, «Política de privacidad», con la versión y la fecha justo debajo.
2. El índice y «En un minuto», que es el resumen y la primera sección.
3. El resto del documento, sección por sección.

**El marco es propio:** ni el de la familia (`ShellFamilia`, `MarcoAlta`) ni el del relevo (`relevo/Marco.tsx`). Es una página de lectura:
- sin navegación, sin «Entrar», sin «Salir» y sin el nombre de nadie;
- el logo **no es un enlace**. Rosa llega desde el relevo, y un enlace a la entrada de la familia la llevaría a un lugar que no es suyo;
- no hay botón para cerrar. La página se abre en otra pestaña desde la app y desde el relevo, y en el teléfono el botón «atrás» del navegador cierra esa pestaña y vuelve a la anterior.

No hay acción principal: la página no tiene ningún botón `turquesa` macizo.

### 1.2 Esquema a 360 px

```
┌──────────────────────────────────────┐
│ (♥) MATU   [● Piloto académico /     │  header: hoja, borde inferior linea
│              con datos de prueba]    │
├──────────────────────────────────────┤
│ Política de                          │  h1, titular text-3xl
│ privacidad                           │
│ Versión 0.11 · actualizada el        │  text-base tenue
│ 09/11/2026                           │
│                                      │
│ ┌──────────────────────────────────┐ │
│ │ Índice                        ⌄  │ │  details cerrado, summary 51 px
│ └──────────────────────────────────┘ │
│                                      │
│ En un minuto                         │  h2, text-xl bold
│ • MATU te ayuda a organizar el       │
│   cuidado de una persona mayor. …    │
│ • Hoy MATU es un piloto académico …  │
│ …                                    │
│ Volver al índice                     │  enlace de texto, 48 px
│                                      │
│ 1. Esto es un borrador del piloto    │  h2
│ académico                            │
│ …                                    │
└──────────────────────────────────────┘
```

Con el índice abierto:

```
│ ┌──────────────────────────────────┐ │
│ │ Índice                        ⌃  │ │
│ │ En un minuto                     │ │  cada ítem, 51 px de alto
│ │ 1. Esto es un borrador del       │ │
│ │    piloto académico              │ │
│ │ 2. Quién es responsable de los   │ │
│ │    datos                         │ │
│ │ …                                │ │
│ │ 14. Leyes que aplican            │ │
│ └──────────────────────────────────┘ │
```

### 1.3 Esquema a 1280 px (igual a 1920 px, con más margen a los lados)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ (♥) MATU                                 [● Piloto académico con datos …]   │
├─────────────────────────────────────────────────────────────────────────────┤
│   Política de privacidad                                       (max-w-6xl,  │  h1 text-5xl
│   Versión 0.11 · actualizada el 09/11/2026                      centrado)   │
│                                                                             │
│   Índice                       │ En un minuto                               │
│   En un minuto                 │ • MATU te ayuda a organizar el cuidado …   │
│   1. Esto es un borrador del   │ • Hoy MATU es un piloto académico …        │
│      piloto académico          │                                            │
│   2. Quién es responsable de   │ 1. Esto es un borrador del piloto académico│
│      los datos                 │ • MATU es un proyecto de título. …         │
│   3. Para qué usamos los datos │                                            │
│   …                            │  (columna de lectura, max-w-prose)         │
│   14. Leyes que aplican        │                                            │
│   (pegajoso: sigue a la vista) │                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

A 1920 px, la columna del contenido no crece más de `max-w-prose` (65 caracteres por línea, DISENO.md 2) y el conjunto queda centrado en `max-w-6xl`.

### 1.4 Esquema a 320 px con el texto al 200 % (160 px efectivos, modo `angosto:`)

```
┌──────────────────┐
│ (♥) MATU         │
│ [● Piloto        │
│  académico /     │
│  con datos de    │
│  prueba]         │
├──────────────────┤
│ Política de      │  h1 angosto:text-2xl
│ privacidad       │
│ Versión 0.11 ·   │
│ actualizada el   │
│ 09/11/2026       │  la fecha no se parte (cifras)
│ ┌──────────────┐ │
│ │ Índice     ⌄ │ │
│ └──────────────┘ │
│ En un minuto     │
│ • MATU te        │  angosto:ps-4
│   ayuda a …      │
│ …                │
│ ┌──────────────┐ │  una tabla, apilada (2.5)
│ │ Dato         │ │
│ │ Ficha de     │ │
│ │ relevo       │ │
│ │ Plazo        │ │
│ │ 90 días      │ │
│ └──────────────┘ │
│ Volver al índice │
└──────────────────┘
```

En tema oscuro los esquemas son los mismos. No hay ningún valor propio del tema en la página: todo sale de los tokens.

### 1.5 El marco

| Parte | Tokens y piezas |
|---|---|
| Cabecera | `header` con `border-b border-linea bg-hoja`. Adentro, el mismo contenedor que la cabecera del relevo: `mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 angosto:px-2 @3xl/app:px-10 py-3` |
| Marca | `Logo` (`size-8`) y «MATU» en `titular text-xl`, como en el relevo. Sin el nombre de la página al lado: el `h1` ya lo dice |
| Distintivo | `DistintivoPiloto` con `ms-auto`, sin cambios. Visible siempre, también con el texto al 200 % (DISENO.md 3, «visible siempre») |
| `main` | `id="contenido"`, `tabIndex={-1}`, `@container/main px-4 angosto:px-2 @3xl/app:px-10 pt-6 @3xl/app:pt-14 pb-16 outline-none`. Adentro, `mx-auto max-w-6xl` |
| Título | `h1` con `id="titulo-pagina"`, `titular text-3xl @2xl/main:text-5xl angosto:text-2xl`, como el `Titulo` del relevo |
| Bajo el título | `p` con `mt-2 text-base text-tenue`. La versión y la fecha en `cifras`, cada una por separado, para que la línea se parta entre palabras y nunca dentro de «09/11/2026» |
| Título del documento | «Política de privacidad · MATU» (`document.title`) |

Sin pie de página.

### 1.6 Cómo se navega el documento: el índice

El documento tiene 15 secciones de primer nivel («En un minuto» y de la 1 a la 14), con subsecciones, y unas 7.300 palabras. Por eso lleva un índice con **solo los títulos de primer nivel** (`##`). Los de segundo nivel (`###`) no entran: con ellos el índice pasaría de 25 renglones.

**Pantalla ancha (contenedor `main` desde `@4xl/main`, 56 rem):**
- Dos columnas: `grid grid-cols-1 gap-10 @4xl/main:grid-cols-[var(--container-xs)_minmax(0,1fr)] @4xl/main:gap-16`, con `mt-8` bajo el título. La columna del índice mide `--container-xs` (20 rem), un token que ya existe en Tailwind: no es una medida nueva.
- El índice es un `nav` con `aria-labelledby` y su rótulo «Índice» en un `h2` (`text-base font-bold text-tenue px-3`).
- Es **pegajoso**: `sticky top-6 self-start`, con `max-h-[calc(100dvh-3rem)]` y `overflow-y-auto`, para que en un proyector de 720 px de alto los 15 renglones se puedan recorrer sin salir de la pantalla. Los `3rem` son el `top-6` arriba y abajo.
- Se oculta en el teléfono: `hidden @4xl/main:block`.

**Teléfono y texto al 200 % (bajo `@4xl/main`):**
- El índice es un `details` cerrado, con `id="indice"`, entre la línea de la versión y «En un minuto». Así el resumen queda a la vista sin tener que pasar 15 renglones.
- Superficie: `rounded-xl bg-hoja ring-1 ring-linea`, `mt-6`.
- `summary`: `flex min-h-12 cursor-pointer list-none items-center justify-between gap-2 px-4 angosto:px-2 font-bold text-turquesa`, sin el triángulo nativo (`[&::-webkit-details-marker]:hidden`). Al final, `ChevronDown` (`size-5`, `aria-hidden`), que en el estado abierto se gira (`group-open:rotate-180`, sin transición). El estado lo dicen la forma del ícono y el `aria-expanded` nativo del `details`.
- La lista va adentro, con `px-4 angosto:px-2 pb-3`.
- Se oculta en pantalla ancha: `@4xl/main:hidden`.

Los dos índices tienen los mismos enlaces y nunca se ven los dos a la vez, así que el lector de pantalla encuentra uno solo.

**Los enlaces del índice** (en los dos):
- Lista `ul` con `role="list"` (Safari quita la semántica de lista cuando no hay viñetas), sin viñetas, `flex flex-col`.
- Cada enlace: `flex min-h-12 items-center rounded-lg px-3 angosto:px-2 py-2 text-base leading-snug text-turquesa hover:bg-rocio hover:underline`. El texto es el del título tal cual, con su número («5. La autorización para usar los datos de la persona que cuidas»).
- Sin subrayado en reposo: es una lista de navegación, no un enlace dentro de una frase (DISENO.md 3, la barra lateral de la familia hace lo mismo).
- Sin marca de «sección actual» al desplazarse: no hace falta para leer y suma movimiento.
- El enlace va a `#{id}` del título. **El salto es inmediato**, sin `scroll-behavior: smooth` (DISENO.md 4, principio 5).

**Las anclas.** Cada título `##` lleva un `id` estable y legible que sale de su número: `en-un-minuto`, `seccion-1` … `seccion-14`. Los `###` llevan un `id` también, por si el texto los cita, pero no entran al índice. Los títulos llevan `scroll-mt-6`, para no quedar pegados al borde de arriba al saltar.

**«Volver al índice»** (J2):
- Al final de cada sección de primer nivel, **solo bajo `@4xl/main`** (`@4xl/main:hidden`). En pantalla ancha el índice ya está a la vista.
- Es un enlace de texto: `inline-flex min-h-12 items-center gap-1 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa`, con `mt-4`. Sin ícono de flecha (DISENO.md 5).
- Al tocarlo, el foco va al `summary` del índice y la pantalla sube hasta él. El índice **se abre** si estaba cerrado, para no obligar a un segundo toque.

### 1.7 El documento: cómo se ve el markdown

La columna del contenido es un `article` con `min-w-0 max-w-prose`. El texto se agrupa por título de primer nivel: cada `##` y lo que le sigue, hasta el próximo `##`, van en un `section` con `aria-labelledby` apuntando a su título.

| Markdown | Elemento y clases |
|---|---|
| `##` | `h2`, `text-xl font-bold leading-snug scroll-mt-6`. Cada sección después de la primera lleva `mt-12`. En Atkinson y no en Bricolage: Bricolage es solo para titulares desde 1,5 rem (DISENO.md 2) |
| `###` | `h3`, `mt-8 text-lg font-bold leading-snug scroll-mt-6` |
| Párrafo | `p`, `mt-4 text-base leading-relaxed text-tinta`. El primer elemento después de un título va con `mt-3` |
| Lista con viñetas | `ul`, `mt-4 flex list-disc flex-col gap-2 ps-6 angosto:ps-4 leading-relaxed marker:text-tenue` |
| Lista numerada | `ol`, igual con `list-decimal` |
| `**negrita**` | `strong`, `font-bold` |
| `*cursiva*` | `em`, `italic`. Atkinson 400 cursiva ya está cargada (`latin-400-italic.css`) |
| Cita (`>`) | `blockquote`, `mt-4 rounded-xl border-l-4 border-turquesa bg-rocio px-4 angosto:px-2 py-3 leading-relaxed`. Los párrafos de adentro, con `mt-3` entre ellos. Es la misma apariencia de la nota «Lo que declaras» de las autorizaciones (`Nota tono="rocio" borde`), así que la declaración se ve igual en la política y en la app. Sin ícono |
| `---` | `hr`, `my-10 border-t border-linea` |
| `` `código` `` | `code`, en `text-base` (sin achicarlo) y en `font-mono`, que es la cara `digitos` (DISENO.md 2). Lleva `[overflow-wrap:anywhere]`, para que la huella de 64 caracteres se parta a 320 px con el texto al 200 % (ver G4) |
| Enlace | Si algún día el texto trae uno: enlace dentro de una frase (sección 7). Si va a otro sitio, se abre en otra pestaña con `rel="noopener noreferrer"` y «(se abre en otra pestaña)» después del texto |
| Tabla | Sección 1.8 |

Contrastes: `tinta` sobre `papel` 14,1:1 en claro y 15,4:1 en oscuro. `tenue` (la línea de la versión y las viñetas) 6,4:1 y 9,2:1. `tinta` sobre `rocio` (las citas) 13,2:1 y 10,9:1 (medidos en MATU-67).

La página va sobre `papel`, sin hoja ni tarjeta alrededor del texto: la hoja con sombra es solo la ficha (DISENO.md 4, principio 1).

### 1.8 Las tablas, sin desplazamiento horizontal

El texto de la 0.10 no tiene tablas, pero la página tiene que saber mostrarlas sin desplazamiento horizontal, también a 320 px con el texto al 200 %. **No se usa un contenedor con barra horizontal**: WCAG 1.4.10 permite las tablas con desplazamiento, pero el criterio de MATU es sin desplazamiento.

**Desde `@xl/main` (36 rem de `main`), es una tabla:**
- `table`: `mt-4 w-full border-collapse text-start`.
- `th`: `border-b-2 border-borde py-2 pe-4 text-start font-bold align-bottom`.
- `td`: `border-b border-linea py-3 pe-4 align-top leading-relaxed`.

**Bajo `@xl/main` (el teléfono y el texto al 200 %), cada fila es un bloque:**
- `thead` oculto (`hidden @xl/main:table-header-group`).
- `tr`: `block border-b border-linea py-3`, y `@xl/main:table-row`.
- `td`: `block`, y `@xl/main:table-cell`. Entre dos datos de la misma fila, `mt-2` (`not-first:mt-2 @xl/main:mt-0`), para que cada par de encabezado y valor se lea como un grupo (v0.2). Antes del valor, el encabezado de su columna, en un `span` con `block font-bold @xl/main:hidden`. Ese `span` **no** lleva `aria-hidden`: cuando la tabla está apilada, es lo que dice qué es cada dato.
- Como cambiar el `display` de una tabla le quita su semántica en algunos navegadores, la tabla lleva sus roles explícitos (`role="table"`, `rowgroup`, `row`, `columnheader`, `cell`).

### 1.9 Estados

El marco, el título «Política de privacidad» y el distintivo se ven siempre, en todos los estados: no dependen de la API. La línea de la versión, el índice y el documento aparecen juntos cuando llega la respuesta.

| Estado | Qué se ve |
|---|---|
| Cargando | Bajo el título, «Cargando…» **[lenguaje 26]** en `text-base text-tenue`, con `role="status"`, después de la demora de `useDemora` (400 ms), para que no parpadee en una conexión rápida. Sin esqueletos (DISENO.md 6, «Página») |
| Error (sin conexión, 5xx o respuesta que no se puede leer) | Bajo el título, el error en tono neutro, como el del PIN del relevo cuando no hay conexión: ícono `CircleAlert` (`size-5`, `text-tenue`, `aria-hidden`) y el texto en `text-tinta`: «No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo.» **[lenguaje 8, `errorAlCargar`]**. No va en `pronto`, porque no se perdió nada (DISENO.md 6). Se anuncia como `alert`. Debajo, `Boton variante="secundario"` «Volver a intentar» **[lenguaje 26]**, con `textoOcupado="Cargando…"` mientras vuelve a pedir |
| Lista | La versión, el índice y el documento |
| Vacío | No aplica: la política siempre tiene texto |
| Conflicto (412) | No aplica: la página no guarda nada |

Al abrir la página, el foco queda donde lo deja el navegador (al principio del documento).

**Sin salto a un ancla al abrir (v0.2).** La v0.1 pedía que `/privacidad#seccion-10` saltara a esa sección cuando llegara el texto. Se saca: para hacerlo, la página tendría que leer el fragmento de la dirección, y la condición del analista dice que `/privacidad` no lo lee. Además, ningún enlace de MATU lleva ancla (sección 4). Los enlaces del índice sí usan `#{id}` dentro de la página. Eso no lee nada: es el salto nativo del navegador.

---

## 2. Crear cuenta: la casilla de la política

### 2.1 Objetivo y jerarquía

**Objetivo, desde la persona:** «Antes de crear mi cuenta, digo que leí la política, y si quiero la leo sin perder lo que ya escribí.»

**Jerarquía:** no cambia. Los campos, después la casilla y al final «Crear cuenta», que sigue siendo el único botón `turquesa` macizo.

### 2.2 Dónde va

**Después de la contraseña y antes de los avisos y del botón.** Es lo último que Carmen hace antes de crear la cuenta. Va dentro del `form`, con el mismo `gap-5` de los campos.

### 2.3 Esquemas

**A 360 px:**

```
│ Una contraseña                       │
│ [••••••••••        ] [Mostrar]       │
│ Al menos 10 caracteres.              │
│                                      │
│ [☐] Leí y acepto la política de      │  label min-h-12, items-start
│     privacidad (se abre en otra      │  el enlace: turquesa, negrita,
│     pestaña).                        │  subrayado
│                                      │
│ [ Crear cuenta ]                     │  único turquesa macizo
│                                      │
│ ¿Ya tienes cuenta? Entrar            │
```

**Con el error:**

```
│ [☐] Leí y acepto la política de      │
│     privacidad (se abre en otra      │
│     pestaña).                        │
│ (!) Para crear tu cuenta, marca que  │  MensajeError: pronto, negrita, ícono
│     leíste la política de privacidad.│
```

**A 1280 px**, en `MarcoAlta`, la casilla queda en la columna del formulario, alineada a la izquierda con los campos, en `max-w-xl`, para que la frase no pase de un renglón y medio:

```
┌──────────────────────────────┬────────────────────────────────────────────────┐
│ (♥) MATU  [Piloto académico…]│ Paso 1 de 4                                    │
│                              │ Crea tu cuenta                                 │
│ Que el cuidado no dependa    │ …                                              │
│ de una sola persona.         │ Una contraseña                                 │
│                              │ [••••••••••             ] [Mostrar]            │
│  1 Tu cuenta          ahora  │                                                │
│  2 Tu grupo                  │ [☐] Leí y acepto la política de privacidad     │
│  …                           │     (se abre en otra pestaña).                 │
│                              │                                                │
│                              │ [ Crear cuenta ]                               │
└──────────────────────────────┴────────────────────────────────────────────────┘
```

**A 320 px con el texto al 200 %:** la casilla queda arriba a la izquierda (`items-start`, `mt-0.5`) y la frase usa el resto del ancho (unos 105 px de 143). «privacidad» en negrita mide unos 95 px y cabe sin partirse. La frase baja en cinco o seis renglones.

### 2.4 Componente y tokens

Es la **casilla nativa de DISENO.md 6**, sin una pieza nueva:

| Parte | Token o pieza |
|---|---|
| Etiqueta | `label` que envuelve la casilla y el texto: `flex min-h-12 cursor-pointer items-start gap-3 max-w-xl text-base leading-relaxed`. Es el área que se toca: mide 48 px o más de alto y todo el ancho de la frase. Sin negrita: la negrita la lleva el enlace |
| Casilla | `input type="checkbox"`, `size-6 shrink-0 accent-turquesa mt-0.5`, sin marcar al llegar. `required` no: la validación es la de MATU, al enviar. Con el error, `aria-invalid` y `aria-describedby` al mensaje |
| El texto | «Leí y acepto la » + enlace + «.» |
| El enlace | Enlace dentro de una frase (sección 7): `/privacidad`, `target="_blank"`, `rel="noopener noreferrer"`. Texto «política de privacidad (se abre en otra pestaña)» |
| El error | `MensajeError` con su `id`, justo bajo la etiqueta. `MensajeError` ya pone el ícono en línea en modo angosto. **La etiqueta lleva `py-3` y sigue con `items-start`**, y la casilla con `mt-0.5` (v0.3). Un renglón de 27,6 px más 2 × 12,75 px da 53 px. El texto de un renglón queda centrado en la caja, la casilla queda alineada con el primer renglón en cualquier ancho, y el error queda a unos 19 px del texto. La v0.2 pedía `@2xl/main:items-center`, pero en `MarcoAlta` a 1280 px el `main` mide 615 px, menos que `@2xl` (714 px). La frase ya cabía en un renglón, la variante no se activaba y el error seguía a 30 px. `py-3` no depende del ancho |

**Por qué el enlace va dentro de la etiqueta y no la marca.** Un enlace es contenido interactivo, y el HTML dice que tocar un elemento interactivo dentro de un `label` no activa el `label`: abre la política y la casilla no cambia. No hace falta código para impedirlo (y no se agrega un `preventDefault` que podría romperlo). El nombre accesible de la casilla queda como la frase entera: «Leí y acepto la política de privacidad (se abre en otra pestaña).»

**Lo que se toca:**
- La casilla y el texto fuera del enlace marcan y desmarcan.
- El enlace abre la política en otra pestaña y no cambia la casilla. Mide 48 px de alto en cada renglón (sección 7).
- La casilla mide 25,5 px y está a 12,75 px (`gap-3`) del texto, así que el enlace nunca queda encima de ella.

**Sin error, sin anillo.** La casilla sin marcar tiene su borde nativo, que mide 4:1 o más contra `papel` en los dos temas (medido en MATU-68). Con el error no se agrega un anillo a la etiqueta: el estado lo dicen el ícono y la frase en `pronto` negrita, nunca solo el color.

### 2.5 Estados

| Estado | Qué pasa |
|---|---|
| Normal | Sin marcar |
| Marcada | Cuadro `turquesa` con su check (6,7:1 sobre `hoja` en claro y 8,2:1 en oscuro, DISENO.md 6) |
| Error al enviar sin marcar | «Para crear tu cuenta, marca que leíste la política de privacidad.» **[aprobado, D6]** en `MensajeError`. Se valida junto con los demás campos, al enviar. Si es el único error, **el foco va a la casilla** (`enfocarPrimerError`, que ya busca `aria-invalid`). Si hay otros, el foco va al primero, en el orden de la pantalla, y la casilla es la última |
| Al marcarla | El error se quita en ese momento, como en el aviso del cuidador de hecho |
| Creando la cuenta | La casilla no cambia. El botón dice «Creando la cuenta…» |
| La política cambió mientras la leía (J3) | La casilla se desmarca. Sobre el botón, `Nota tono="atenta" rol="status" iconoEnLinea` con el texto de J3. Sin `iconoEnLinea`, a 320 px con el texto al 200 % el título se parte dentro de la palabra («Actualizamo / s», v0.2) **[PROPUESTO]**, en el mismo lugar que las otras notas del formulario. El foco va a la casilla. Lo que escribió sigue en los campos |
| Sin conexión al pedir la huella | El formulario se ve igual. Al enviar, se vuelve a pedir la política. Si tampoco responde, la nota `pronto` de siempre: «No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo. Lo que escribiste sigue aquí.» **[lenguaje 8]** |

---

## 3. Las autorizaciones de la ficha y de los insumos

### 3.1 Dónde va

En las tres pantallas que muestran «Lo que declaras»:
- el paso 4 del alta (`Autorizacion`, con `DeclaracionFicha`);
- volver a autorizar la ficha (`/grupo/autorizar-ficha`, con la misma `DeclaracionFicha`);
- el permiso de los insumos (`Insumos.tsx`, el que usa `DECLARACION_CONSUMO`), también al volver a autorizarlo.

La línea va **dentro de la nota «Lo que declaras», como su último párrafo**, bajo la declaración. Aparece y desaparece con la nota, o sea, cuando se elige en qué calidad se autoriza. Así queda pegada a «según la política de privacidad vigente», la frase de la declaración que remite a ella, y justo antes del botón «Autorizo…».

**Pantalla de pedidos:** todavía no existe. Cuando exista, lleva la misma línea en el mismo lugar (condición del analista).

### 3.2 Esquema (igual a 360 y 1280 px, la nota mide `max-w-prose`)

```
┃ (i) Lo que declaras                           Nota rocio, borde turquesa
┃     Declaro que la persona que cuido me
┃     dijo hoy, en persona, que autoriza a …
┃     … según la política de privacidad
┃     vigente. Yo solo registro su decisión.
┃
┃     Lee la política de privacidad (se abre    mt-3, el enlace en turquesa,
┃     en otra pestaña) antes de autorizar.      negrita y subrayado
```

### 3.3 Tokens y textos

| Parte | Token o pieza |
|---|---|
| Párrafo | `p` con `mt-3 max-w-prose`, dentro del cuerpo de `Nota` (`text-base leading-relaxed text-tinta`) |
| Texto | «Lee la » + enlace + « antes de autorizar.» **[aprobado, D6]** |
| Enlace | Enlace dentro de una frase (sección 7), en otra pestaña. Texto «política de privacidad (se abre en otra pestaña)» |
| Contraste | `turquesa` sobre `rocio`: 5,6:1 en claro y 6,7:1 en oscuro. `tinta` sobre `rocio`: 13,2:1 y 10,9:1 |

Si la nota hoy no lleva `borde` en alguna de las tres pantallas, no se le agrega: esta especificación solo suma el párrafo.

**Estados:** no tiene propios. El error, el «Autorizando…» y los demás siguen igual. La línea no es obligatoria: no hay casilla de «leí» en las autorizaciones.

---

## 4. Lo que se repite en las tres pantallas de la familia

- El enlace siempre se abre en otra pestaña: el formulario sigue ahí cuando Carmen vuelve.
- El destino es siempre `/privacidad`, sin ancla. La página no salta a una sección al abrir (1.9, v0.2).
- El texto del enlace es siempre «política de privacidad (se abre en otra pestaña)» dentro de una frase, y «Política de privacidad (se abre en otra pestaña)» cuando va solo (relevo y «Tu cuenta»).

---

## 5. «Tu cuenta»: la fila de la política

### 5.1 Objetivo y jerarquía

**Objetivo, desde la persona:** «Puedo ver qué versión de la política acepté y cuándo, y sé a quién escribir para cambiar o borrar mis datos.»

**Jerarquía:** las filas de siempre (tu correo, tu celular), después la de la política, y al final el párrafo de cómo pedir. La pantalla no tiene acción principal nueva.

### 5.2 Esquema a 360 px

```
│ Tu cuenta                            │  título
│ Tus datos para entrar a MATU.        │
│ ┌──────────────────────────────────┐ │  dl: hoja, ring linea
│ │ Tu correo                        │ │
│ │ carmen@example.com               │ │
│ ├──────────────────────────────────┤ │
│ │ Tu celular                       │ │
│ │ +56 9 •••• 0137  ✓ Confirmado    │ │
│ ├──────────────────────────────────┤ │
│ │ Política de privacidad           │ │  dt: text-sm tenue (como las otras)
│ │ Aceptaste la versión 0.11 el     │ │  dd: text-base; versión y fecha
│ │ 09/11/2026.                      │ │  en cifras negrita
│ │ (▤) Política de privacidad (se   │ │  enlace solo, 48 px, con FileText
│ │     abre en otra pestaña)        │ │
│ └──────────────────────────────────┘ │
│                                      │
│ Para cambiar tu nombre o tu correo,  │  p: text-base tinta, max-w-xl
│ pedir una copia de tus datos o       │
│ eliminar tu cuenta, escribe a        │
│ privacidad@…  desde el correo de tu  │  correo: enlace mailto
│ cuenta.                              │
```

**Sin registro:**

```
│ │ Política de privacidad           │ │
│ │ No tenemos registro de qué       │ │
│ │ versión aceptaste.               │ │
│ │ (▤) Política de privacidad (se   │ │
│ │     abre en otra pestaña)        │ │
```

**A 1280 px** es la misma columna (`max-w-xl`), dentro del `ShellFamilia`:

```
┌──────────────────┬──────────────────────────────────────────────────────┐
│ (♥) MATU         │ Cuidas a María Soto              Tu cuenta   Salir   │
│ ▣ Ficha          ├──────────────────────────────────────────────────────┤
│ □ Insumos        │ Tu cuenta                                            │
│ □ Compartir      │ Tus datos para entrar a MATU.                        │
│ □ Grupo familiar │ ┌──────────────────────────────────────┐             │
│                  │ │ Tu correo …                           │             │
│                  │ │ Tu celular …                          │             │
│                  │ │ Política de privacidad                │             │
│                  │ │ Aceptaste la versión 0.11 el 09/11/2026.            │
│                  │ │ (▤) Política de privacidad (se abre en otra pestaña)│
│                  │ └──────────────────────────────────────┘             │
│                  │ Para cambiar tu nombre o tu correo, pedir una copia  │
│                  │ de tus datos o eliminar tu cuenta, escribe a …       │
└──────────────────┴──────────────────────────────────────────────────────┘
```

### 5.3 Tokens y textos

| Parte | Token o pieza |
|---|---|
| Fila | Un `div` más dentro del `dl` existente: `flex flex-col gap-2 py-4`, después de la del celular. El `divide-y divide-linea` del `dl` la separa |
| `dt` | «Política de privacidad» **[aprobado, D6]**, `text-sm text-tenue`, igual que «Tu correo» y «Tu celular» |
| `dd`, con registro | «Aceptaste la versión `{version}` el `{DD/MM/AAAA}`.» **[aprobado, D6]**. `text-base`; la versión y la fecha en `cifras font-bold`, cada una por separado |
| `dd`, sin registro | «No tenemos registro de qué versión aceptaste.» **[aprobado, D6]**. `text-base text-tinta`, sin color de estado: no es un problema que Carmen tenga que resolver, y no hay nada que hacer desde la app |
| Enlace | Bajo el dato, en la misma `dd`: el enlace solo del relevo (`AvisoDatos`), es el componente `EnlacePoliticaSolo`, el mismo en el relevo y en «Tu cuenta». Clases: `inline-flex min-h-12 items-start py-3 gap-2 self-start font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa`, con `FileText` (`mt-0.5 size-5 shrink-0`, `aria-hidden`). **Por qué `items-start` con `py-3` (v0.3):**
- Con `items-center`, en un enlace de varios renglones el ícono quedaba al medio y no junto al primero.
- Con `items-start` y sin relleno, el enlace de un renglón quedaba arriba de su caja de 51 px, con 28 px vacíos abajo. El contorno de foco tenía el texto pegado arriba, y en «Tu cuenta» la tarjeta quedaba con más aire abajo que arriba.
- Con `py-3`, el renglón queda centrado (15 px arriba y 15 abajo, medido), el ícono va junto al primer renglón en cualquier caso, y la caja mide 51 px. Texto «Política de privacidad (se abre en otra pestaña)» **[lenguaje 7.5, J4]**. `/privacidad`, `target="_blank"`, `rel="noopener noreferrer"` |
| Cómo pedir | Un `p` **fuera del `dl`**, bajo él: `mt-6 max-w-xl text-base leading-relaxed text-tinta`. Texto: «Para cambiar tu nombre o tu correo, pedir una copia de tus datos o eliminar tu cuenta, escribe a `{correo_privacidad}` desde el correo de tu cuenta.» **[aprobado, D6]**. Va fuera del `dl` porque no es un dato de la cuenta sino cómo pedir algo, y vale para las tres filas |
| El correo | Enlace dentro de una frase (sección 7), `mailto:{correo_privacidad}`, sin asunto ni cuerpo prellenados (nada de la cuenta en la dirección). Con `[overflow-wrap:anywhere]`, para que la dirección se parta a 320 px con el texto al 200 % en vez de salirse. Sin «(se abre en otra pestaña)»: abre la app de correo, no una pestaña |

**Contrastes:** `tinta` sobre `hoja` 15:1 o más en los dos temas; `tenue` sobre `hoja` 7,2:1 y 8,1:1; `turquesa` sobre `hoja` 6,7:1 y 8,2:1; `turquesa` sobre `papel` (el correo) 6,0:1 y 9,4:1.

### 5.4 Estados

| Estado | Qué se ve |
|---|---|
| Cargando y error | Los de hoy: la fila nueva llega con las demás, en el mismo `GET /v1/cuenta`. No tiene un cargando propio |
| Con registro | El dato con la versión y la fecha |
| Sin registro | La frase sin registro. Las cuentas creadas antes de la 0.11 quedan así (D2): no se completan |
| Aceptó una versión anterior a la vigente | El mismo dato, con su versión («Aceptaste la versión 0.11 el …»). **No** se avisa que hay una más nueva: D1 dice que nadie tiene que volver a aceptar |
| Sin `{correo_privacidad}` configurado | El párrafo de cómo pedir **no se muestra** (G2). La fila de la política sí |

---

## 6. El relevo: el enlace de `AvisoDatos`

**No se rediseña.** El enlace ya está construido en `PantallaPin.tsx` y solo falta la ruta: `RUTA_POLITICA = '/privacidad'`. Lo revisé en el código (no se ve funcionando hasta que tenga ruta):

| Punto | Estado en el código | Veredicto |
|---|---|---|
| Destino y pestaña | `href={RUTA_POLITICA}`, `target="_blank"`, `rel="noopener noreferrer"` | Cumple la condición del analista |
| No lleva el token | `/privacidad`, sin fragmento: el `#<token>` del relevo no viaja. La página pública no lee el fragmento | Cumple |
| Texto | «Política de privacidad (se abre en otra pestaña)» **[lenguaje 7.5]** | Cumple D6 |
| Área táctil | `inline-flex min-h-12`: 51 px de alto | Cumple |
| Estado no solo por color | Subrayado (`decoration-turquesa/40`) e ícono `FileText` | Cumple |
| Contraste | `turquesa` sobre `papel`: 6,0:1 en claro y 9,4:1 en oscuro | Cumple |
| Foco | El foco base (3 px `turquesa`, 2 px de separación) | Cumple |
| Lugar | Al final de `AvisoDatos`, bajo el pie del PIN, alineado a la izquierda (`self-start`) en la columna de `max-w-md` | Cumple. El relevo no acepta nada: el enlace solo informa |
| 320 px con el texto al 200 % | El ícono y el texto van en un `inline-flex` con `self-start`. El texto puede partirse entre palabras dentro del enlace, y la palabra más larga («pestaña)») cabe | **A verificar funcionando** en la revisión visual: que el ícono quede arriba a la izquierda del primer renglón y que el texto no se salga de la columna |

**Lo único que cambia en el relevo** es el texto de los párrafos de `AVISO`, por D7 (lenguaje 7.5 con `{correo_privacidad}`). La apariencia no cambia. Si el correo todavía no existe, rige la variante sin correo de lenguaje 7.5, como hoy.

---

## 7. Pieza común: el enlace dentro de una frase (se suma a DISENO.md 6)

La casilla del alta, la línea de las autorizaciones y el correo de «Tu cuenta» llevan un enlace **en medio de una frase**. `EnlaceRuta` y el enlace del relevo usan `inline-flex min-h-12`, que no deja que el texto del enlace baje de renglón junto con la frase: a 320 px con el texto al 200 % quedaría un bloque aparte con la frase rota alrededor.

**La pieza:** un `a` en línea (no `inline-flex`), con:
- `font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa`;
- **El área táctil va en un `::after`, no en el enlace (v0.2):** `relative after:absolute after:inset-x-0 after:-inset-y-3.5 after:content-['']`, **sin relleno vertical** en el `a`. El seudoelemento agranda lo que se toca hasta unos 51 px de alto y no mueve los renglones.

**Por qué cambió (revisión visual del 09-11, P2).** La v0.1 pedía `py-3.5` en el propio enlace. Agrandaba bien lo que se toca, pero el contorno de foco rodea la caja con relleno: quedaba una caja de 51 px por renglón que, al bajar de renglón, se unía en un bloque y **tachaba el texto del renglón de arriba y del de abajo** («Leí y acepto la», «cuenta, escribe a», «otro sitio se abre en otra»). Se probó llevar el contorno hacia adentro (`outline-offset` negativo): como el enlace no tiene relleno a los lados, el contorno cortaba las letras. Con el `::after`, el contorno sigue el texto (21 px más los 2 px de separación) y no tapa nada. Está verificado en pantalla a 360 px y a 320 px con el texto al 200 %.

**Lo que hay que saber:**
- Cuando el enlace baja de renglón, el `::after` se calcula sobre el primer y el último renglón, y el navegador no lo garantiza para un elemento partido. Ahí lo que se toca es el enlace entero, que ya mide dos renglones o más (55 px o más). El `::after` es para el enlace de un solo renglón, que es el caso que medía 21 px.
- En la casilla del alta, el área de arriba y de abajo del enlace es del enlace y no de la etiqueta: tocar ahí abre la política y no marca la casilla. La casilla en sí nunca queda tapada (está a la izquierda, fuera de la columna del texto).
- No lleva ícono: el subrayado ya dice que es un enlace, y un ícono en medio de una frase la corta.

---

## 8. Textos exactos

| Dónde | Texto | Origen |
|---|---|---|
| `/privacidad`, título | Política de privacidad | D6 |
| `/privacidad`, título del documento | Política de privacidad · MATU | D6 |
| `/privacidad`, bajo el título | Versión `{version}` · actualizada el `{DD/MM/AAAA}` | D6 |
| `/privacidad`, rótulo del índice | Índice | **[PROPUESTO, J1]** |
| `/privacidad`, al final de cada sección (teléfono) | Volver al índice | **[PROPUESTO, J2]** |
| `/privacidad`, cargando | Cargando… | lenguaje 26 |
| `/privacidad`, error | No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo. | lenguaje 8 |
| `/privacidad`, botón del error | Volver a intentar · ocupado «Cargando…» | lenguaje 26 |
| `/privacidad`, cada `[PENDIENTE]` | Todavía no lo definimos. (viene escrito en el texto, G3) | D6 |
| Crear cuenta, casilla | Leí y acepto la [política de privacidad (se abre en otra pestaña)]. | D6 |
| Crear cuenta, error | Para crear tu cuenta, marca que leíste la política de privacidad. | D6 |
| Crear cuenta, la política cambió | Título «Actualizamos la política de privacidad.» Texto «Cambió mientras creabas tu cuenta. Léela de nuevo y vuelve a marcar la casilla.» | **[PROPUESTO, J3]** |
| Autorizaciones, bajo la declaración | Lee la [política de privacidad (se abre en otra pestaña)] antes de autorizar. | D6 |
| Tu cuenta, fila | Política de privacidad | D6 |
| Tu cuenta, dato | Aceptaste la versión `{version}` el `{DD/MM/AAAA}`. | D6 |
| Tu cuenta, sin registro | No tenemos registro de qué versión aceptaste. | D6 |
| Tu cuenta, enlace | Política de privacidad (se abre en otra pestaña) | lenguaje 7.5 (J4) |
| Tu cuenta, cómo pedir | Para cambiar tu nombre o tu correo, pedir una copia de tus datos o eliminar tu cuenta, escribe a `{correo_privacidad}` desde el correo de tu cuenta. | D6 |
| Relevo | Política de privacidad (se abre en otra pestaña) | lenguaje 7.5 |

Revisados contra lenguaje.md 3: en tú, en voz activa, sin términos clínicos ni códigos. «Aceptaste» y «Leí y acepto» usan el mismo verbo. Los propuestos van a lenguaje.md 29 si Jorge los aprueba.

---

## 9. Criterios visuales verificables

**`/privacidad`**
1. La página no tiene `ShellFamilia`, `MarcoAlta` ni la cabecera del relevo con «Ficha de cuidado». Tiene el logo, «MATU» y el distintivo del piloto, y ningún enlace ni botón en la cabecera.
2. Al abrirla no hay ninguna petición a la sesión ni a la cuenta, y `GET /v1/politica` sale sin cookie (se ve en la pestaña de red).
3. No hay ningún botón `turquesa` macizo en la página.
4. A 1280 y 1920 px, el índice es una columna de 20 rem a la izquierda que queda a la vista al desplazarse, y la columna del texto no pasa de `max-w-prose`.
5. A 360 px, el índice es un `details` cerrado entre la versión y «En un minuto», y su `summary` mide 48 px o más de alto.
6. Cada enlace del índice mide 48 px o más de alto, y lleva a su sección sin animación, con el título a la vista.
7. A 360 px, «Volver al índice» está al final de cada sección, abre el índice y deja el foco en su `summary`. A 1280 px no se ve.
8. Ningún texto del documento ni del índice es `text-sm`: todo va en 1 rem o más.
9. A 320 px con el texto al 200 %, en tema claro y oscuro, no hay desplazamiento horizontal en ninguna parte del documento: ni en la huella de 64 caracteres de la sección 5, ni en las citas, ni en una tabla (que se ve apilada, con el encabezado sobre cada dato), ni en el distintivo. «privacidad» del título no se parte por dentro.
10. Las citas (`>`) se ven como la nota «Lo que declaras» de las autorizaciones: fondo `rocio` y línea `turquesa` a la izquierda.
11. Mientras carga se ve «Cargando…» después de 400 ms. Sin conexión se ve el error en tono neutro (no `pronto`) con «Volver a intentar», y el título de la página sigue a la vista.
12. El título del documento es «Política de privacidad · MATU».

**Crear cuenta**
13. La casilla está después de la contraseña y antes de «Crear cuenta», y llega sin marcar.
14. Tocar el texto de la etiqueta fuera del enlace marca la casilla. Tocar el enlace abre `/privacidad` en otra pestaña y **la casilla no cambia**.
15. La etiqueta mide 48 px o más de alto. El enlace de un renglón mide 48 px o más con su `::after`, y el enlace partido mide 48 px o más en total. Con el teclado, el contorno de foco del enlace no cruza el texto de los renglones vecinos (v0.2).
16. Al enviar sin marcar, aparece «Para crear tu cuenta, marca que leíste la política de privacidad.» con ícono, en `pronto` negrita, bajo la casilla. Si es el único error, el foco queda en la casilla. Al marcarla, el error se va.
17. «Crear cuenta» sigue siendo el único botón `turquesa` macizo.

**Autorizaciones**
18. En el alta, al volver a autorizar la ficha y en el permiso de insumos, la nota «Lo que declaras» termina con «Lee la política de privacidad (se abre en otra pestaña) antes de autorizar.», y el enlace abre `/privacidad` en otra pestaña.

**Tu cuenta**
19. La fila «Política de privacidad» está después de la del celular, con la versión y la fecha en negrita, o con la frase sin registro, sin color de estado.
20. El enlace de la fila mide 48 px o más y abre `/privacidad` en otra pestaña. El correo del párrafo abre la app de correo, sin asunto ni cuerpo.
21. Sin `{correo_privacidad}` configurado, el párrafo no aparece y nunca se ve `{correo_privacidad}` en la pantalla.

**Relevo**
22. Con `RUTA_POLITICA = '/privacidad'`, el enlace aparece al final de «Tus datos en MATU», abre la política en otra pestaña sin el fragmento del token, y a 320 px con el texto al 200 % el texto no se sale de la columna.

**En todas**
23. Todo enlace y control muestra el contorno de foco de 3 px al llegar con el teclado, en los dos temas.
24. Con `prefers-reduced-motion`, nada se anima (ni el chevron del índice, ni la entrada de la página, ni el salto a una sección).

---

## 10. Revisión visual que haré después de construirla

Funcionando, con capturas a 360, 1280 y 1920 px, en tema claro y oscuro, y a 320 px con el texto al 200 %:
- `/privacidad`: arriba, con el índice cerrado y abierto, en la sección 5 (las citas y la huella) y en el error sin conexión.
- Crear cuenta: normal, con el error de la casilla y con el error en varios campos.
- Las tres autorizaciones, con una calidad elegida.
- «Tu cuenta», con registro, sin registro y sin correo configurado.
- El PIN del relevo, con el enlace.

Si para entonces el texto ya trae una tabla, la reviso en los dos modos. Si no, pido al frontend una página de ejemplo en `/ejemplos` con una tabla de tres columnas.

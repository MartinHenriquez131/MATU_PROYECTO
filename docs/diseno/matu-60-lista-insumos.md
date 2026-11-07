# MATU-60 · Lista de insumos · Especificación de diseño

**Versión 1.2 · 06/11/2026** · agente 6 (UI/UX) · para el frontend. La v1.1 aplicó las decisiones de Jorge del 06-11 sobre la v1.0 y los ajustes del contrato (decisiones 116 a 122 de `docs/api/README.md`). La v1.2 corrige lo que encontró la revisión visual del 06-11: la grilla de la línea en ancho (4.2), el observador en ancho (2.3), el `aria-label` de «Quitar de la lista» (4.3) y el singular del envase en el 412 (9.4)
**Historia:** MATU-60, la lista de insumos (RF-14 y RF-15, ADR-031). Con los insumos que hoy aparecen en «Se acaban pronto», MATU arma una lista con lo que falta para cubrir 30 días, que la familia puede ajustar, imprimir o compartir como texto.
**Dónde se construye:** `web/`, dentro de la sección «Insumos» de la app de la familia (MATU-39 y MATU-36), React 19, TypeScript y Tailwind CSS v4, mobile first.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` · las decisiones de Jorge del 06-11 con la revisión del analista normativo · `docs/lenguaje.md` del repositorio MATU, sección 21 (y las secciones 3, 8, 13, 16, 17 y 18) · ADR-031 · `docs/legal/politica-privacidad.md` («La lista de insumos») y `docs/legal/registro-tratamientos.md` (entrada «Lista de insumos») · las especificaciones `matu-36-insumos.md`, `matu-37-alertas.md` y `matu-48-compartir.md` de esta carpeta · el código actual de `web/src/familia/Insumos.tsx`, `ui.tsx`, `ruteo.ts`, `Shell.tsx` y `web/src/compartido/ui/Anuncios.tsx`.

**Cómo se lee:** los textos entre comillas latinas «» van tal cual. **[L 21]** es un texto de la sección 21 de `lenguaje.md`, aprobado por Jorge el 06-11. Incluye los 14 que en la v1.0 estaban como propuestos. **[NUEVO]** es un texto que sale de las decisiones 2, 3 y 6 de Jorge del 06-11 o del cambio de la cantidad sugerida, y que va a la sección 21 en el mismo PR de documentos para que Jorge lo apruebe. **[AJUSTE]** es un texto de la sección 21 que esta versión cambia, con la razón al lado. **[L 18]**, **[L 17]**, **[L 8]** son de esas secciones. **[M36]** es un texto ya aprobado en `matu-36-insumos.md`. Las llaves son datos: `{pila}` es el nombre de pila de la persona cuidada (como lo calcula hoy `Insumos.tsx`), `{nombre}` es el nombre del insumo, `{n}` son los días que quedan o la cantidad, según la fila, `{u}` son las unidades por envase y `{fecha}` es el campo `fecha` de la respuesta de la lista, en `DD/MM/AAAA`.

**Tokens:** ningún token nuevo. Todo sale de la capa de `web/src/index.css`. Hace falta **una regla nueva en la capa base para imprimir** (sección 8.4), que no agrega tokens: repite los valores del tema claro dentro de `@media print` y deja fuera del papel toda la app, en todas las pantallas.

### Qué cambió en la v1.1

| Sección | Cambio | Por qué |
|---|---|---|
| 0 | D1 a D5 cerradas. Quedan dos pendientes nuevos | Decisiones de Jorge del 06-11 y contrato propuesto |
| 3 | Los campos de la respuesta, por nombre. Sin paginación. La lista coincide con «Se acaban pronto» | Decisiones 116 a 118 del contrato |
| 4.1, 4.3 | «Quitar de la lista» en todas las líneas editables, también las que vienen de MATU | Decisión 3 de Jorge |
| 4.5 | Lo agregado a mano se cuenta en unidades, sobres o envases | Decisión 2 de Jorge |
| 4.6 | La nota del cálculo dice que la cantidad ya descuenta lo que queda | La cantidad sugerida ahora resta lo que MATU estima que queda hoy |
| 4.7 | El panel suma «¿Cómo se cuenta?». Quitar sirve para las dos clases de línea, con su anuncio | Decisiones 2 y 3 de Jorge |
| 4.10 | Nueva: qué pasa al quitar una línea de MATU y al quitarlas todas | Decisión 3 de Jorge |
| 7.2 | La fecha sale de la API | Decisión 118 del contrato |
| 8.2, 8.5 | La casilla se queda. El observador imprime solo título, nota y pie | Decisiones 1 y 4 de Jorge |
| 8.4 | La regla oculta toda la app al imprimir, en todas las pantallas, y deja una línea | Decisión 6 de Jorge |
| 9.2 | Al guardar, `null` borra el envase | Decisión 121 del contrato |
| 10, 12, 14 | Foco, áreas táctiles, componentes y revisión con lo nuevo | Lo anterior |
| 13 | La tabla final de la sección 21 de `lenguaje.md` | Decisión 5 de Jorge |
| Todas | Sin marcas de propuesto: los 14 textos están aprobados | Decisión 5 de Jorge |

---

## 0. Lo que tiene que decidir alguien más · *cambió en la v1.1*

### 0.1 Cerrado el 06-11

| # | Qué | Cómo se cerró |
|---|---|---|
| D1 | El contrato de la lista | Propuesto en `GET /v1/personas-cuidadas/{persona_id}/consumo/lista` (decisiones 116 a 122). Sin paginación. La sección 3 usa sus campos |
| D2 | Borrar las unidades por envase | El `PATCH` acepta `unidades_por_envase: null` y lo borra (decisión 121) |
| D3 | Qué imprime el observador con el menú del navegador | Jorge: solo el título, «Quien administra, cuida o paga puede imprimirla o compartirla.» y el pie (8.5) |
| D4 | Las otras pantallas se imprimen tal como se ven, también la ficha | Jorge: la regla de 8.4 oculta toda la app al imprimir, en todas las pantallas. Cierra el hueco de Ctrl+P en la ficha (ADR-029) |
| D5 | Quién aplica la regla de impresión | Jorge: el frontend la copia tal cual de 8.4 en `web/src/index.css`, y yo la reviso en la revisión visual |

### 0.2 Pendiente

| # | Qué | Para quién | Lo que hace la especificación mientras tanto |
|---|---|---|---|
| D6 | **Los textos [NUEVO] y [AJUSTE]** de la sección 13. Salen de las decisiones 2, 3 y 6 y de la cantidad que ahora descuenta lo que queda | Jorge, en el PR de documentos | Los usa. Si Jorge cambia uno, se cambia en `textos` sin tocar el diseño |
| D7 | **El registro de tratamientos dice «consumo de 30 días».** Con la cantidad que descuenta lo que queda, la lista ya no lleva el consumo de 30 días sino lo que falta para cubrirlos (nota del contrato, «Política y registro») | Orquestador → analista normativo | Nada en la pantalla. La bajada sigue siendo cierta (4.6) |

---

## 1. Para quién y qué

**Carmen** ve en Insumos que los pañales se acaban en 6 días. Quiere mandarle a su hermano, o llevar a la farmacia, una lista corta con lo que hay que conseguir y cuánto, sin hacer cuentas. La arma en un minuto, con una mano, y la manda por WhatsApp o la imprime.

**Rodrigo**, si es **pagador**, hace lo mismo: ajusta la cantidad y la comparte. Si es **observador**, ve la lista y nada más.

**Quien compra** recibe un texto o un papel. Lo lee de pie en un pasillo: nombre y cantidad, en letra grande, sin el nombre de la persona y sin los días.

**Lo que esta pantalla nunca hace:** ofrecer comprar, mostrar precios o comercios, guardar lo que se cambia, enviar la lista por su cuenta o crear un enlace (ADR-031).

---

## 2. Marco común

### 2.1 Ruta y acceso desde Insumos

- **Ruta:** `/insumos/lista`, sin ids ni nombres. Se agrega a `Ruta` y `RUTAS` de `ruteo.ts`. Es la misma sección «Insumos» de la navegación: `seccionDe` ya la reconoce por el prefijo.
- **Acceso: pestañas en la sección Insumos**, con el componente `Pestanas` de `ui.tsx`, igual que Compartir y Enlaces en MATU-48. Van **antes del título**, en el `antes` de la página:

  ```
  Insumos   Lista de insumos
  ━━━━━━━                           ← activa: borde inferior de 3 px, negrita y aria-current
  ```

  | Pestaña | Ruta | Texto |
  |---|---|---|
  | 1 | `/insumos` | «Insumos» [M36] |
  | 2 | `/insumos/lista` | «Lista de insumos» [L 21] |

  `aria-label` del `nav`: «Vistas de Insumos» [L 21], como «Vistas de Compartir» en MATU-48.

- **Por qué pestañas y no un botón dentro de «Se acaban pronto»:** el bloque de MATU-37 tiene una regla, «el aviso nunca ofrece comprar» [L 17], y una lista para conseguir insumos, puesta dentro del aviso, se lee como una invitación a comprar. Además, el bloque no se muestra cuando no hay alertas, y la lista sirve igual para agregar algo a mano. La pestaña está siempre, no compite con «Anotar un insumo» (que sigue siendo el único `turquesa` macizo de Insumos) y no agrega un segundo botón al bloque.
- **Dónde se ven las pestañas:**
  - En `/insumos` con la lista cargada (con o sin insumos) y en `/insumos/lista` en todos sus estados.
  - **No** en el permiso de Insumos (MATU-36, 3.1), en «Falta el permiso» o «Hay que renovar» de `/insumos`, ni en el formulario a 360 px (`/insumos/nuevo` y `/insumos/cambiar` reemplazan a la lista: son un momento, no una vista).
  - En pantalla ancha con el formulario abierto en la columna derecha, las pestañas siguen arriba con «Insumos» activa.
- **Roles:** las cuatro ven las dos pestañas. La lista la ven todos los miembros (registro de tratamientos).

### 2.2 Título, foco y `<title>`

- `h1` con el componente `Titulo` (`id="titulo-pagina"`, `tabIndex={-1}`), con la clase de Insumos: `text-3xl @2xl/main:text-5xl`. Texto: «Lista de insumos» [L 21].
- Al llegar a la ruta, el foco va al `h1`, como en toda la app.
- `<title>`: «Lista de insumos · MATU» [L 21], con la convención de `tituloDe` en `AppFamilia.tsx`. **Durante la impresión**, «Lista de insumos» (8.3).
- Sin transiciones entre vistas. Solo `aparecer` (180 ms) en los avisos. Con `prefers-reduced-motion`, inmediato (ya lo hace la capa base).

### 2.3 Composición

- Vive dentro del `<main id="contenido">` de `ShellFamilia`, con sus márgenes.
- **A 360 px y hasta 48 rem de contenido:** una columna. Orden: pestañas, título, bajada, líneas, nota, «Agregar otro insumo», aviso, botones y mensaje.
- **Desde 48 rem de contenido** (el mismo `useAncho` de `Insumos.tsx`): dos columnas `grid grid-cols-[3fr_2fr] items-start gap-10`, como Insumos. A la izquierda las líneas, la nota y «Agregar otro insumo». A la derecha el aviso, los botones y el mensaje, en una columna `flex flex-col items-start gap-4` con `sticky top-6`, para que los botones sigan a la vista con una lista larga. Es la composición de la tabla de DISENO.md (sección 3): a la izquierda las cantidades, a la derecha la salida.
- **El observador, en ancho, va en una sola columna** `flex flex-col gap-5 max-w-3xl`: las líneas, la nota y, debajo, «Quien administra, cuida o paga puede imprimirla o compartirla.». Sin columna derecha. *(Nuevo en la v1.2.)* La columna derecha es el lugar de la salida, y el observador no tiene salida: una frase sola arriba a la derecha se lee como un rótulo suelto, lejos de la lista a la que se refiere. `max-w-3xl` (48 rem) deja la cantidad cerca del nombre, como la columna izquierda de los demás roles.

### 2.4 Roles

| Rol | Ve | Puede |
|---|---|---|
| `admin`, `cuidador`, `pagador` | Todo | Cambiar la cantidad, agregar a mano, quitar cualquier línea de la lista (también las de MATU, solo en la pantalla), imprimir, compartir y copiar |
| `observador` | Las líneas con nombre, cantidad y días | Nada. Sin campos, sin «Agregar otro insumo», sin aviso y sin botones. **No se muestran deshabilitados: no se muestran.** Ve el texto «Quien administra, cuida o paga puede imprimirla o compartirla.» [L 21] |

El campo nuevo del formulario del insumo (sección 9) es de Insumos, así que solo lo ven `admin` y `cuidador`, que son quienes anotan y cambian insumos (MATU-36, 2.4).

---

## 3. Estados y cómo se llega a cada uno · *cambió en la v1.1*

### 3.1 Lo que trae la API

`GET /v1/personas-cuidadas/{persona_id}/consumo/lista`, con `X-Grupo-Id`, responde `{fecha, items}`, sin paginación (decisiones 116 a 118). Se pide una vez al llegar a la ruta, y otra vez cada vez que se vuelve a entrar.

| Campo | Dónde se usa |
|---|---|
| `fecha` | La primera línea del texto y del papel, en `DD/MM/AAAA` (7.2) |
| `items[].perfil_id` | La `key` de la línea y la identidad para quitarla. Nunca se muestra ni va a la URL |
| `items[].nombre` | El nombre de la línea (4.3) |
| `items[].dias_restantes` | Los días, solo en la pantalla (4.3) |
| `items[].unidad` | El sufijo y la palabra de la cantidad (4.5) |
| `items[].unidades_por_envase` | Si no es `null`, la cantidad va en envases (4.5) |
| `items[].envases_sugeridos` y `items[].unidades_sugeridas` | El valor inicial del campo: `envases_sugeridos` si no es `null`, y si no, `unidades_sugeridas` (4.4) |

**Qué trae:** los mismos insumos que en ese momento muestra «Se acaban pronto» en Insumos, calculados al pedirla. Por eso la bajada dice «Lo que se acaba pronto» y el vacío dice «No hay insumos que se acaben pronto»: si Insumos no muestra el bloque, la lista está vacía, y al revés. Lo verifico en la revisión (14).

**La cantidad sugerida** es lo que falta para cubrir 30 días, después de descontar lo que MATU estima que queda hoy, y como mínimo 1. La pantalla no la calcula: la muestra (4.6).

### 3.2 Estados

```
abre /insumos/lista ─► GET …/consumo/lista
                      ├─ 200 con líneas ─► lista (4)
                      ├─ 200 sin líneas ─► vacía (5)
                      ├─ 403 sin-consentimiento ─► admin o cuidador: reemplaza a /insumos, que muestra el permiso (MATU-36, 3.1)
                      │                          └► pagador u observador: «Falta el permiso» (6.2)
                      ├─ 403 revision-vencida ─► «Hay que renovar» (6.3), para todos
                      ├─ 401 ─► lo que ya hace la app (renovar la entrada una vez y, si falla, Entrar)
                      ├─ 404 ─► lenguaje 8, no-encontrado (6.4)
                      └─ red o 5xx ─► error al cargar (6.1)
«Quitar de la lista» ─► quedan líneas: lista (4) · no queda ninguna: «Quitaste todo de la lista» (4.10)
botones ─► validan las cantidades ─► con error: mensaje en el campo y foco en el primero (4.4)
        ├─ Compartir la lista ─► navigator.share({ text }) ─► sin mensaje · AbortError: nada · otro error: 7.4
        ├─ Imprimir o guardar en PDF ─► window.print() con la hoja de impresión (8)
        └─ Copiar la lista ─► navigator.clipboard.writeText(text) ─► copiada (7.3) · falla: 7.4
```

La pantalla elige el texto **solo por `type`** del error, nunca por `title`, `detail` ni `status` (lenguaje 8).

**Cargando:** el patrón de `Cargando` de `Insumos.tsx`. Pestañas y título visibles desde el principio. A los 400 ms, «Cargando los insumos…» [L 18] en `text-lg text-tenue`, con `aria-busy="true"` en la región. Sin esqueleto ni ícono que gira.

---

## 4. La lista

**Objetivo:** Carmen ve qué hay que conseguir y cuánto, lo ajusta con el pulgar y lo saca del teléfono sabiendo qué sale.

**Jerarquía:**
1. Las líneas: el **nombre** y la **cantidad** de cada insumo, el que se acaba primero arriba.
2. La acción principal de salida, con el aviso justo encima.
3. Los días que quedan, la nota del cálculo y «Agregar otro insumo».

### 4.1 Esquema a 360 px (admin, cuidador o pagador, con `navigator.share`) · *cambió en la v1.1*

```
┌────────────────────────────────────┐
│ (encabezado de la app)             │
├────────────────────────────────────┤
│ Insumos   Lista de insumos         │  Pestanas, 48 px, la activa con borde 3 px
│ ────────────━━━━━━━━━━━━━━━━────── │
│ Lista de insumos                   │  h1 titular text-3xl
│ Lo que se acaba pronto, con una    │  bajada text-base text-tenue max-w-prose
│ cantidad sugerida para 30 días.    │
│ Puedes cambiarla antes de imprimir │
│ o compartir.                       │
│ ┌────────────────────────────────┐ │  ul flex-col gap-2, cada li una hoja
│ │ Pañal adulto talla M           │ │  text-lg font-bold
│ │ Alcanza para 6 días            │ │  text-base text-tenue
│ │ Cantidad                       │ │  label font-bold
│ │ [ − ] [  6  ] [ + ]            │ │  Stepper de Insumos, botones size-12
│ │ envases de 20 unidades         │ │  sufijo text-base text-tenue (baja si no cabe)
│ │             Quitar de la lista │ │  textoPeligro, min-h-12, mt-2
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ Toallitas húmedas              │ │
│ │ (!) Se acaba hoy               │ │  CircleAlert text-atenta + texto text-tinta
│ │ Cantidad                       │ │
│ │ [ − ] [ 120 ] [ + ] unidades   │ │
│ │             Quitar de la lista │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │  agregado a mano
│ │ Toallitas para el baño         │ │
│ │ (✎ Solo en esta pantalla)      │ │  Etiqueta neutra con Pencil
│ │ Cantidad                       │ │
│ │ [ − ] [  2  ] [ + ] envases    │ │  la unidad que se eligió al agregarla
│ │             Quitar de la lista │ │
│ └────────────────────────────────┘ │
│ Es una sugerencia con lo que       │  nota text-base text-tenue
│ anotaste, y ya descuenta lo que    │
│ queda. Cambia la cantidad si       │
│ necesitas otra.                    │
│ [ + Agregar otro insumo ]          │  secundario, aria-expanded
│                                    │
│ ┃ (i) La lista no lleva el nombre │  Nota tono atenta, borde, icono Info
│ ┃ de María, pero sí lo que usa.   │
│ ┃ Lo que imprimas o compartas     │
│ ┃ sale de MATU y no podemos       │
│ ┃ borrarlo. Compártela solo con   │
│ ┃ quien va a comprar.             │
│ [ Compartir la lista ]             │  principal, Share2. Único turquesa macizo
│ [ Imprimir o guardar en PDF ]      │  secundario, Printer
│ [ Copiar la lista ]                │  secundario, Copy
│ (✓) Copiamos la lista. Pégala      │  Nota tono ok, solo después de copiar
│     donde quieras.                 │
└────────────────────────────────────┘
  (barra de secciones fija abajo: el main ya trae telefono:pb-36)
```

Los botones van **uno debajo del otro, al ancho de su texto** cuando no caben en una fila (`Acciones`, que ya envuelve). Nunca de ancho completo (DISENO.md, sección 5).

### 4.2 Esquema en pantalla ancha (1280 y 1920 px, sin `navigator.share`)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Insumos   Lista de insumos                                                       │
│ Lista de insumos                                                                 │
│ Lo que se acaba pronto, con una cantidad sugerida para 30 días. Puedes cambiarla │
│ antes de imprimir o compartir.                                                   │
│ ┌──────────────────────────────────────────────┐   ┌───────────────────────────┐ │
│ │ Pañal adulto talla M   Cantidad              │   │┃(i) La lista no lleva el  │ │
│ │ Alcanza para 6 días    [−][ 6 ][+]  Quitar   │   │┃nombre de María, pero sí  │ │
│ │                        envases de   de la    │   │┃lo que usa. Lo que…       │ │
│ │                        20 unidades  lista    │   └───────────────────────────┘ │
│ ├──────────────────────────────────────────────┤   [ Imprimir o guardar en PDF ] │
│ │ Toallitas húmedas      Cantidad              │   [ Copiar la lista ]           │
│ │ (!) Se acaba hoy       [−][120][+]  Quitar   │   (✓) Copiamos la lista…        │
│ │                        unidades     de la l. │          (columna sticky top-6) │
│ └──────────────────────────────────────────────┘                                 │
│ Es una sugerencia con lo que anotaste, y ya descuenta lo que queda. Cambia la    │
│ cantidad si necesitas otra.                                                      │
│ [ + Agregar otro insumo ]                                                        │
└──────────────────────────────────────────────────────────────────────────────────┘
```

- *(Corregido en la v1.2.)* La línea vive en la columna izquierda (3fr), así que su grilla se decide por **el ancho de la lista, no el del `main`**. El `ul` lleva `@container/lista`, y cada línea es `grid grid-cols-1 @2xl/lista:grid-cols-[minmax(0,1fr)_20rem_auto] @2xl/lista:items-center gap-x-6 gap-y-2`: nombre y días a la izquierda, la cantidad al medio en una columna fija de 20 rem (así el campo queda en la misma vertical en todas las líneas, y el sufijo largo baja dentro de ella) y «Quitar de la lista» al final, con `@2xl/lista:mt-0`. Para el observador, que no tiene «Quitar», son dos columnas (`@2xl/lista:grid-cols-[minmax(0,1fr)_auto]`, la cantidad con `text-right`). Bajo 42 rem de lista, una sola columna, con «Quitar de la lista» abajo a la derecha (`justify-self-end`), igual que a 360 px. **Por qué:** con `@3xl/main`, a 1280 px el `main` mide más de 48 rem pero la columna izquierda mide 518 px, las dos columnas `auto` se llevan 481 px y el nombre queda en 0 px, una letra por renglón (revisión del 06-11).
- Con eso, a 1280 px las líneas van en una columna dentro de la columna izquierda, y a 1920 px (lista de 791 px) en tres, con el nombre en unos 230 px.

### 4.3 La línea · *cambió en la v1.1*

| Parte | Componente y tokens | Texto |
|---|---|---|
| Contenedor | `li` con `rounded-xl bg-hoja px-4 angosto:px-2 py-3 ring-1 ring-linea`. **La línea no es un botón** | — |
| Nombre | `p` `text-lg font-bold break-words [overflow-wrap:anywhere]`, con `id` propio (lo usa el campo, 4.4) | `{nombre}` |
| Días, 2 o más | `p` `text-base text-tenue`, la cifra en `cifras` | «Alcanza para `{n}` días» [L 21] |
| Días, 1 | igual | «Alcanza para 1 día» [L 21] |
| Días, 0 | `p` `flex gap-1.5 text-base font-bold text-tinta`, con `CircleAlert` `size-5 text-atenta` `aria-hidden` delante | «Se acaba hoy» [L 21] |
| Días, negativo | igual que 0 | «Puede que ya no quede» [L 21] |
| Agregado a mano | En lugar de los días, `Etiqueta` neutra (`bg-tinta/7 text-tenue`) con `Pencil` `size-4` `aria-hidden` | «Solo en esta pantalla» [L 21] |
| Cantidad, editable | El `Stepper` de `Insumos.tsx` (campo de texto numérico con − y +), etiqueta «Cantidad» [L 21] y el sufijo de la unidad (4.5) | — |
| Cantidad, observador | `p` `text-lg tabular-nums`, sin etiqueta | El texto completo de 4.5, por ejemplo «6 envases de 20 unidades» |
| Quitar, en **todas** las líneas (de MATU y agregadas a mano), salvo para el observador | `Boton variante="textoPeligro"`, `justify-self-end` a 360 px, al final de la línea en ancho, separado del campo por al menos `gap-4` | «Quitar de la lista» **[AJUSTE]** de «Quitar» [L 21]: en una línea que viene de MATU, «Quitar» solo se puede leer como borrar el insumo de MATU. Con «de la lista» se entiende que sale de esta lista y nada más. Va igual en las dos clases de línea, para que el mismo botón diga lo mismo. `aria-label` «Quitar de la lista: `{nombre}`» **[AJUSTE v1.2]** de «Quitar «`{nombre}`» de la lista»: el nombre accesible tiene que empezar con el texto visible completo (WCAG 2.5.3), para que quien usa control por voz diga «Quitar de la lista» y funcione. Es la misma forma de «Menos: Cantidad de `{nombre}`» |

**Orden dentro de la línea:** nombre, días, cantidad. La sección 21 da el contenido de la línea («{nombre} · {cantidad} · {días}»). Pongo los días bajo el nombre y la cantidad al final para que el campo quede junto al pulgar y no separe el nombre de sus días. El texto no cambia.

**El estado nunca solo por color:** 0 y negativo cambian la palabra y suman el ícono. El agregado a mano se distingue por la etiqueta con palabra e ícono, no por un fondo.

**Orden de las líneas:** primero las de la API, en el orden en que llegan (por fecha estimada, el que se acaba primero arriba). Después las agregadas a mano, en el orden en que se agregaron. El mismo orden en la pantalla, en la impresión y en el texto compartido.

### 4.4 El campo «Cantidad»

- **Componente:** el `Stepper` local de `Insumos.tsx` (o el mismo extraído a un lugar común), con `inputMode="numeric"`, `pattern="[0-9]*"`, `autoComplete="off"`, solo dígitos. Botones − y + `size-12` con `ring-turquesa/70`. Campo `min-h-12 w-24 text-xl cifras` con `ring-2 ring-inset ring-borde`, foco `ring-turquesa` y el foco base.
- **Valor inicial:** `envases_sugeridos` si no es `null`, y si no, `unidades_sugeridas` (3.1). Para los agregados a mano, 1. *(Cambió en la v1.1: los nombres del contrato.)*
- **Rango:** de 1 a 100.000, paso 1. Si la API sugiere más de 100.000, el máximo es lo sugerido. Para no conseguir un insumo, se quita la línea (4.10), no se deja en 0.
- **Nombre accesible:** la etiqueta visible es «Cantidad», pero hay una por línea. El campo lleva `aria-labelledby` con el id de la etiqueta y el id del nombre de la línea, para que el lector diga «Cantidad, Pañal adulto talla M» (la etiqueta visible queda dentro del nombre, WCAG 2.5.3). Los botones: «Menos: Cantidad de `{nombre}`» y «Más: Cantidad de `{nombre}`» [L 21, solo para el lector], con `INSUMOS.menos` y `INSUMOS.mas`.
- **Validación, al tocar cualquiera de los tres botones de salida** (que nunca están deshabilitados): un campo vacío, en 0 o sobre el máximo muestra bajo él, con `MensajeError` y `aria-invalid`, «Escribe una cantidad de 1 a 100.000.» [L 21]. El foco va al primer campo con error y **no se imprime, comparte ni copia nada**. El error se borra al corregir el campo.
- **Nada se guarda.** El valor vive en la memoria de la página (sección 11).

### 4.5 Cómo se escribe la cantidad · *cambió en la v1.1*

Es el mismo texto en el sufijo del campo, en la línea del observador, en la impresión y en el texto compartido. Una sola función lo arma (7.2). Recibe la cantidad, la unidad (`unidad`, `sobre`, `ml`, `g` o, solo en lo agregado a mano, `envase`) y las unidades por envase o `null`.

| Caso | Sufijo del campo | Texto completo | Fuente |
|---|---|---|---|
| Con envase, `{n}` mayor que 1 | «envases de `{u}` unidades» | «`{n}` envases de `{u}` unidades» | [L 21] |
| Con envase, 1 | «envase de `{u}` unidades» | «1 envase de `{u}` unidades» | [L 21] |
| Con envase, en ml o g | «envases de `{u}` ml», «envases de `{u}` g» | «`{n}` envases de `{u}` ml» | [L 21] |
| Con envase, en sobres | «envases de `{u}` sobres» | «`{n}` envases de `{u}` sobres» | [L 21] |
| Con envase de 1 (`{u}` igual a 1) | «envases de 1 unidad», «envases de 1 sobre» | «`{n}` envases de 1 unidad» | [L 21], con el singular de la misma fila «Sin envase, 1» |
| Sin envase | «unidades», «sobres», «ml», «g» | «`{n}` unidades», «`{n}` sobres», «`{n}` ml», «`{n}` g» | [L 21] |
| Sin envase, 1 | «unidad», «sobre» | «1 unidad», «1 sobre» | [L 21] |
| Agregado a mano, en unidades | «unidades», con 1 «unidad» | «`{n}` unidades», «1 unidad» | [L 21] |
| Agregado a mano, en sobres | «sobres», con 1 «sobre» | «`{n}` sobres», «1 sobre» | **[NUEVO]**, decisión 2. Las mismas palabras de «Sin envase» [L 21] |
| Agregado a mano, en envases | «envases», con 1 «envase» | «`{n}` envases», «1 envase» | **[NUEVO]**, decisión 2. Sin «de `{u}` unidades», porque lo agregado a mano no trae cuántas unidades tiene el envase |

**Ejemplos del texto compartido y del papel con lo agregado a mano:** «- Toallitas húmedas: 2 envases», «- Gasas: 1 sobre», «- Crema humectante: 3 unidades».

**Cifras:** los números con punto de miles desde 1.000 («1.200 unidades»), como el dinero. En pantalla, la cifra en `tabular-nums`. El sufijo baja de renglón como texto (sin `cifras` en la frase completa).

### 4.6 Bajada y nota · *cambió en la v1.1*

| Dónde | Rol | Texto | Fuente |
|---|---|---|---|
| Bajada, bajo el título | admin, cuidador, pagador | Lo que se acaba pronto, con una cantidad sugerida para 30 días. Puedes cambiarla antes de imprimir o compartir. | [L 21], sin cambios |
| Bajada | observador | Lo que se acaba pronto, con una cantidad sugerida para 30 días. | [L 21], sin cambios |
| Nota, bajo las líneas | admin, cuidador | Es una sugerencia con lo que anotaste, y ya descuenta lo que queda. Cambia la cantidad si necesitas otra. | **[AJUSTE]** de [L 21] |
| Nota | pagador | Es una sugerencia con lo que anotó la familia, y ya descuenta lo que queda. Cambia la cantidad si necesitas otra. | **[AJUSTE]** de [L 21] |
| Nota | observador | Es una sugerencia con lo que anotó la familia, y ya descuenta lo que queda. | **[AJUSTE]** de [L 21] |

**Por qué la bajada se queda y la nota cambia.** Ahora la cantidad es lo que falta para cubrir 30 días, contando lo que MATU estima que queda hoy, y como mínimo 1 (3.1).

- **La bajada sigue siendo cierta.** «Lo que se acaba pronto» es exacto, porque la lista trae lo mismo que «Se acaban pronto». «Una cantidad sugerida para 30 días» se lee como «lo que hay que conseguir para tener 30 días», que es lo que calcula MATU. No la cambio.
- **La nota necesita decir que descuenta.** Quien sabe que su mamá usa 4 pañales al día espera 120, ve 108 y piensa que MATU se equivocó. La nota de la v1.0 era cierta pero dejaba esa duda. «Y ya descuenta lo que queda» la resuelve en seis palabras, sin cifras ni la palabra «estimación». Con envases la duda casi nunca aparece (el pañal del contrato da 6 envases con o sin descuento), pero la nota es la misma para todas las líneas.
- **El mínimo de 1** no necesita texto: es raro (lo que queda alcanza para más de 30 días) y se corrige con el campo o con «Quitar de la lista».

Bajada con el `Pagina` o el `Titulo` de `ui.tsx`: `mt-1.5 max-w-prose text-base text-tenue`. Nota: `p` `max-w-prose text-base text-tenue`.

### 4.7 Agregar otro insumo · *cambió en la v1.1*

**Objetivo:** Carmen suma algo que MATU no sigue (unas toallitas que compra a veces) sin salir de la lista, y dice en qué se cuenta para que quien compra no pregunte «¿2 qué?».

Es un panel que se abre en el lugar, con el patrón del panel de «Ya lo resolví» de MATU-37.

```
│ [ + Agregar otro insumo ]          │  cerrado: secundario, Plus, aria-expanded="false"
                 ▼ al tocar
│ ┌────────────────────────────────┐ │  form noValidate, bg-hoja rounded-xl ring-1 ring-linea px-4 py-4
│ │ ¿Qué insumo es?                │ │  label font-bold
│ │ Por ejemplo: «Toallitas        │ │  ayuda text-base text-tenue, ANTES del campo
│ │ húmedas». Sin remedios ni para │ │
│ │ qué se usa.                    │ │
│ │ ┌────────────────────────────┐ │ │  CampoTexto min-h-12, maxLength 60
│ │ └────────────────────────────┘ │ │
│ │ ¿Cómo se cuenta?               │ │  legend font-bold (GrupoOpciones forma="chips")
│ │ (●Unidades) (○Sobres)          │ │  chips min-h-12, flex-wrap gap-2
│ │ (○Envases)                     │ │  a 360 px van en dos renglones (ver abajo)
│ │ Cantidad                       │ │  Stepper, empieza en 1
│ │ [ − ] [  1  ] [ + ] unidad     │ │  el sufijo sigue a la unidad elegida
│ │ Esto queda solo en esta        │ │  text-base text-tenue
│ │ pantalla. No lo guardamos.     │ │
│ │ [ Agregar ]   Cancelar         │ │  secundario · enlace de acción
│ └────────────────────────────────┘ │
```

- **Abrir:** el botón «Agregar otro insumo» se oculta mientras el panel está abierto (como «Ya lo resolví» en MATU-37) y el foco va al campo del nombre.
- **Agregar:** valida, agrega la línea al final con la unidad elegida, cierra el panel y devuelve el foco al botón «Agregar otro insumo», para agregar otro si hace falta. Se anuncia por la región `status`.
- **Cancelar o `Esc`:** cierra sin agregar y devuelve el foco al botón. Lo escrito y la unidad elegida se descartan. La próxima vez el panel abre con «Unidades».
- **«Agregar» es secundario**, no macizo: el único `turquesa` macizo de la pantalla es la acción de salida (sección 10).
- **Nombre:** una línea. Un salto de línea pegado se reemplaza por un espacio y se quitan los espacios de los extremos antes de agregar.
- **Sin límite** de líneas agregadas.

#### El selector «¿Cómo se cuenta?» · *nuevo en la v1.1*

- **Componente:** `GrupoOpciones` de `ui.tsx` con `forma="chips"` y sin `columnas`. Es el mismo que usa Compartir para «¿Para qué?» (MATU-48): un `fieldset` con `legend`, tres `input type="radio"` reales (ocultos con `sr-only`) dentro de su `label`, y la piel del chip. Nada nuevo que construir.
- **Por qué este y no un `select`:** las tres opciones se ven sin abrir nada, se elige con un toque y el lector anuncia «¿Cómo se cuenta?, grupo, Unidades, botón de opción, seleccionado, 1 de 3». Un `select` nativo abre una lista que tapa la pantalla en el teléfono y esconde la opción elegida detrás de una flecha.
- **Opciones, en este orden:** «Unidades», «Sobres», «Envases» **[NUEVO]**. La leyenda es «¿Cómo se cuenta?» [L 18], la misma pregunta del formulario de Insumos.
- **Elegida al abrir: «Unidades».** No se deja sin elegir: un grupo de radios sin valor obliga a un error más, y Carmen tiene una mano. El riesgo de que quede «Unidades» sin querer es bajo, porque el sufijo del campo, justo debajo, dice la unidad con todas sus letras («1 unidad», «2 envases»), y la línea agregada la repite.
- **Estado, nunca solo por color:** la elegida lleva el punto dentro del círculo (forma), el fondo `bg-rocio`, el texto `text-turquesa` y el anillo `ring-turquesa`. Las demás, círculo vacío `ring-tenue`, texto `text-tenue` y anillo `ring-borde` (3,5:1 sobre `hoja`).
- **Áreas táctiles:** cada chip `min-h-12` (51 px) con `gap-2` entre ellos. Se toca el chip entero, no solo el círculo.
- **Foco:** el anillo base de 3 px `turquesa` sobre el chip, con `has-[:focus-visible]` (ya está en el componente). Tab entra al grupo en la opción elegida y las flechas cambian la opción, como todo grupo de radios nativo. Es una sola parada de Tab.
- **¿Cabe en una línea a 360 px? No.** El contenido del panel mide 294 px (360 menos 16 + 16 del `main` y 17 + 17 del panel). Los tres chips, con su relleno `px-4`, el círculo de 20 px y el texto en negrita a 17 px, miden unos 138, 119 y 129 px, más 16 de separación: unos 400 px. Para que entren en 294 habría que quitar el círculo (y el estado quedaría solo en el color) o bajar el relleno bajo lo que pide el chip. No lo hago. **A 360 px van en dos renglones: «Unidades» y «Sobres» arriba, «Envases» abajo**, alineados a la izquierda. En una línea desde unos 25 rem de contenido (la columna izquierda en pantalla ancha). En modo `angosto`, uno bajo el otro (`angosto:flex-col`, ya en el componente).
- **El sufijo del campo «Cantidad» sigue a la unidad:** «unidad» o «unidades», «sobre» o «sobres», «envase» o «envases», según la cantidad (4.5). Cambia en cuanto se elige otra opción, sin anuncio aparte: el lector ya dijo la opción elegida.
- **Una vez agregada, la unidad no se cambia en la línea.** Si se eligió mal, se quita y se agrega de nuevo, que toma segundos. Un selector en cada línea agregada alargaría todas las líneas por un caso raro.

| Parte | Texto | Fuente |
|---|---|---|
| Botón que abre | Agregar otro insumo | [L 21] |
| Etiqueta del nombre | ¿Qué insumo es? | [L 18] |
| Ayuda del nombre | Por ejemplo: «Toallitas húmedas». Sin remedios ni para qué se usa. | [L 21] (con punto final al mostrarse, como en MATU-36) |
| Leyenda de la unidad | ¿Cómo se cuenta? | [L 18] |
| Opciones de la unidad | Unidades · Sobres · Envases | **[NUEVO]**, decisión 2 |
| Etiqueta de la cantidad | Cantidad | [L 21] |
| Nota | Esto queda solo en esta pantalla. No lo guardamos. | [L 21] |
| Botón que agrega | Agregar | [L 21] |
| Cancelar | Cancelar | [M36] |
| Nombre vacío | Escribe el nombre del insumo. | [L 18] |
| Nombre de más de 60 (si llega pegado) | El nombre admite hasta 60 caracteres. Acórtalo un poco. | [L 18] |
| Cantidad fuera de rango | Escribe una cantidad de 1 a 100.000. | [L 21] (4.4) |
| Anuncio al agregar | Agregamos «`{nombre}`» a la lista. | [L 21], mismo verbo que el botón |

### 4.8 El aviso fijo

- **Texto:** «La lista no lleva el nombre de `{pila}`, pero sí lo que usa. Lo que imprimas o compartas sale de MATU y no podemos borrarlo. Compártela solo con quien va a comprar.» [L 21]
- **Componente:** `Nota tono="atenta" borde` con `icono` `Info` (`mt-0.5 size-5 shrink-0 text-atenta`, `aria-hidden`), como el rótulo «Precios de ejemplo» de DISENO.md: es una advertencia, no un estado. **Sin `rol`:** está desde que carga la pantalla y no se anuncia como aviso, se lee en el orden del documento.
- **Siempre visible**, justo encima de los botones, en la misma columna, en todos los anchos. Nunca dentro de un cuadro de confirmación, de un `details` ni de un tooltip, y nunca se cierra.
- Lleva `id="aviso-lista"`, y el botón principal lleva `aria-describedby="aviso-lista"`: quien llega con el lector directo al botón escucha el aviso. Los secundarios no lo repiten.
- Solo aparece cuando hay al menos una línea (de la API o a mano) y el rol puede sacar la lista del teléfono. El observador no lo ve.

### 4.9 Los botones

| Caso | Principal (`turquesa` macizo) | Secundarios |
|---|---|---|
| Con `navigator.share` y `navigator.canShare({ text })` verdadero (o sin `canShare`) | «Compartir la lista» [L 21], ícono `Share2` | «Imprimir o guardar en PDF» [L 21], `Printer` · «Copiar la lista» [L 21], `Copy` |
| Sin `navigator.share` | «Imprimir o guardar en PDF», `Printer` | «Copiar la lista», `Copy` |

- `Boton` de `compartido/ui/Boton.tsx`, dentro de `Acciones`. Íconos `size-5` `aria-hidden` (el `Boton` ya los oculta en modo angosto).
- **Por qué cambia el principal:** en el teléfono lo común es mandarla por WhatsApp a quien compra. En un computador sin hoja de compartir, lo común es imprimirla. Es la misma regla de «Enviar el enlace» y «Copiar el enlace» en MATU-48 (4.4).
- **«Copiar la lista» está siempre**, también con `navigator.share`.
- Ningún botón se deshabilita. Ninguno pide confirmación (decisión de Jorge).
- Solo aparecen cuando hay al menos una línea. Sin líneas no hay nada que sacar (sección 5).

### 4.10 Quitar de la lista · *nuevo en la v1.1*

**Objetivo:** Carmen saca de la lista lo que ya compró o no quiere conseguir esta vez, con un toque, sin miedo de borrar algo de MATU.

- **Dónde:** en cada línea editable, de MATU o agregada a mano (4.3). Nunca para el observador.
- **Qué hace:** saca la línea de la pantalla y, con ella, del texto compartido, de lo copiado y del papel. **No se guarda y no llega al servidor:** el insumo sigue en Insumos igual que antes, y su aviso de «Se acaban pronto» también. Una línea de MATU vuelve a la lista la próxima vez que se entra a `/insumos/lista` (3.1).
- **Sin confirmación**, igual en las dos clases de línea (decisión de Jorge): está solo en memoria y la de MATU vuelve sola al entrar de nuevo.
- **Foco:** al campo «Cantidad» de la línea siguiente o, si era la última, al botón «Agregar otro insumo».
- **Se retira** el mensaje «Copiamos la lista» si estaba (7.3), porque lo copiado ya no es lo que se ve.
- **Lo que se anuncia** por la región `status` (`anunciar(texto, 'status')`):

| Línea | Anuncio | Fuente |
|---|---|---|
| De MATU | Quitamos «`{nombre}`» de la lista. Sigue en Insumos. | **[NUEVO]**, decisión 3. Mismo verbo que el botón, y la segunda frase dice que no se borró nada |
| Agregada a mano | Quitamos «`{nombre}`» de la lista. | **[AJUSTE]** de «Quitamos «`{nombre}`».» [L 21], para que diga lo mismo que el botón |

- **Lo que se ve**, para quien no usa lector: la primera vez que se quita una línea de MATU aparece, bajo la nota del cálculo, un `p` `max-w-prose text-base text-tenue` con «Lo que quitaste sigue en Insumos. Vuelve a esta lista cuando entras de nuevo.» **[NUEVO]**, decisión 3. Queda hasta salir de la pantalla. Sin ícono, sin color y sin región viva: el anuncio ya lo dijo. No aparece si solo se quitaron líneas agregadas a mano, porque esas no vuelven.
- **Si se quitan todas las líneas** (de MATU y a mano), en lugar de las líneas va un `p` `max-w-prose text-lg` con «Quitaste todo de la lista. Si quieres, agrega uno a mano.» **[NUEVO]**, decisión 3, y debajo la nota «Lo que quitaste sigue en Insumos…» si alguna era de MATU, y «Agregar otro insumo». Sin baldosa, sin la nota del cálculo, sin el aviso fijo y sin los botones de salida, como en el vacío (5): sin líneas no hay nada que sacar. **No se usa el texto del vacío** («No hay insumos que se acaben pronto»), porque sí los hay. El foco va a «Agregar otro insumo». Al agregar una línea a mano, vuelven la lista, el aviso y los botones. Si en este estado se imprime con Ctrl+P o el menú, la hoja sale con el título y el pie, sin líneas.

---

## 5. Sin insumos

**Objetivo:** Carmen entiende que no hay nada por acabarse y que igual puede armar una lista.

```
┌────────────────────────────────────┐
│ Insumos   Lista de insumos         │
│ Lista de insumos                   │  h1
│ Lo que se acaba pronto, con una…   │  bajada
│ ┌────┐                             │  baldosa size-16 rounded-2xl bg-rocio
│ │ ✓≡ │                             │  ListChecks size-9 text-turquesa
│ └────┘                             │
│ No hay insumos que se acaben       │  p text-lg max-w-prose
│ pronto. Si quieres, agrega uno a   │
│ mano.                              │
│ [ + Agregar otro insumo ]          │  secundario
└────────────────────────────────────┘
```

| Rol | Texto | Acción | Fuente |
|---|---|---|---|
| admin, cuidador, pagador | No hay insumos que se acaben pronto. Si quieres, agrega uno a mano. | «Agregar otro insumo» (4.7) | [L 21] |
| observador | No hay insumos que se acaben pronto. | Ninguna. Baldosa `bg-tinta/7 text-tenue` | [L 21] |

- Sin aviso, sin nota y sin botones de salida mientras no haya líneas. Al agregar la primera a mano, el bloque vacío se reemplaza por la lista y aparecen el aviso y los botones.
- Es el vacío **que trae la API**. Cuando la lista se queda sin líneas porque la persona las quitó, el texto es otro (4.10). *(Nuevo en la v1.1.)*
- Alineado a la izquierda (`items-start`), como el vacío de Insumos. En ancho, en la columna izquierda, sin la derecha.

---

## 6. Errores y permisos

Todos con el patrón «una sola columna» de Insumos (`UnaColumna`): baldosa `size-16 rounded-2xl` con su ícono `size-9`, el texto en `max-w-prose text-lg`, y las pestañas arriba.

### 6.1 Error al cargar (red o 5xx)

- Baldosa `bg-tinta/7 text-tenue` con `CloudOff`.
- «No pudimos traer la lista. Revisa tu conexión e inténtalo de nuevo.» [L 21], anunciado por la región `alert` (con `Anunciado urgencia="alert"`).
- Botón principal «Volver a intentar» (texto de `GENERAL.volverAIntentar`, hoy propuesto en `textos.ts`). Nunca una lista vieja en su lugar.

### 6.2 Falta el permiso (403 `sin-consentimiento`)

- **admin o cuidador:** `navegar('/insumos', { reemplazar: true })`. Insumos muestra el permiso de MATU-36 (3.1), que es el único lugar donde se da. No se duplica el formulario aquí.
- **pagador u observador:** baldosa `bg-tinta/7 text-tenue` con `Lock`, y «**Falta el permiso para calcular los insumos de `{pila}`.** Sin él no podemos mostrar cuándo se acaban. Pídele a quien administra el grupo o a quien cuida a `{pila}` que lo registre.» [L 18]. Sin botones. No es un error: sin rojo y sin región `alert`.

### 6.3 Hay que renovar (403 `revision-vencida`)

Para todos. Baldosa `bg-atenta-fondo text-atenta` con `Hourglass`, y «**Hay que renovar la autorización de los insumos de `{pila}`.** Se renueva una vez al año. Mientras tanto, no podemos calcular ni mostrar sus insumos, pero lo que anotaste sigue guardado.» [L 18], con lo demás de MATU-36 3.1.4 (la frase para pedir la renovación y el enlace a ChileAtiende).

### 6.4 No encontrado (404)

«No encontramos lo que buscas. Puede que ya no tengas acceso. Vuelve al inicio.» [L 8], con baldosa `bg-tinta/7` y `CircleAlert`, y el enlace de acción «Volver al inicio» de Insumos. El 404 nunca dice si la persona existe en otro grupo.

---

## 7. Compartir, copiar y los mensajes

### 7.1 Compartir

- `navigator.share({ text })`, **solo con `text`**: sin `title`, sin `url` y sin `files` (ADR-031). Algunas aplicaciones anteponen el `title` o agregan la `url` de la página: por eso no van.
- Si la persona cierra la hoja de compartir (`AbortError`), no pasa nada y no hay mensaje.
- Si se compartió, **no hay mensaje**: MATU no sabe si se envió ni a quién, y no debe decir «Enviada».
- Otro error: 7.4.

### 7.2 El texto · *cambió en la v1.1*

Una sola función arma el texto, a partir de las líneas tal como están en la pantalla en ese momento (cantidades cambiadas, líneas quitadas y agregadas a mano incluidas). **La misma función alimenta la hoja de impresión**, para que el papel y el mensaje nunca digan cosas distintas.

```
Lista de insumos · 06/11/2026
- Pañal adulto talla M: 6 envases de 20 unidades
- Toallitas húmedas: 120 unidades
- Toallitas para el baño: 2 envases
Piloto académico con datos de prueba
```

[L 21], exacto:
- Primera línea: «Lista de insumos · `{fecha}`», con el campo `fecha` de la respuesta (hoy en Chile según la API, decisión 118) en `DD/MM/AAAA`. No la fecha del teléfono: las cantidades se calcularon para ese día, y la fecha tiene que ser la misma. El separador es espacio, punto medio (U+00B7) y espacio.
- Una línea por insumo: guion ASCII, espacio, el nombre, dos puntos, espacio y la cantidad de 4.5.
- Última línea: «Piloto académico con datos de prueba».
- Saltos de línea `\n`. Sin línea en blanco, sin espacios al final, sin emojis.
- **Nunca** los días, el nombre de la persona cuidada, el nombre del grupo, un enlace ni el nombre de quien comparte.

### 7.3 Copiar

- `navigator.clipboard.writeText(texto)`.
- Si funciona, bajo los botones: `Nota tono="ok" rol="status"` (`CircleCheck` en `text-ok`, texto en `tinta`, fundido `aparecer`) con «Copiamos la lista. Pégala donde quieras.» [L 21]. Mismo verbo que el botón.
- El mensaje queda hasta salir de la pantalla, no se va a los segundos. **Se retira en cuanto cambia la lista** (una cantidad, una línea agregada o quitada), porque lo copiado ya no es lo que se ve.
- El foco se queda en «Copiar la lista».

### 7.4 Cuando algo falla

Bajo los botones, con `MensajeError` dentro de `Anunciado urgencia="alert"` (el patrón de `Insumos.tsx`). El foco se queda en el botón que se tocó.

| Caso | Texto | Fuente |
|---|---|---|
| No se pudo copiar, con `navigator.share` | No pudimos copiar la lista. Usa «Compartir la lista». | [L 21] |
| No se pudo copiar, sin `navigator.share` | No pudimos copiar la lista. Usa «Imprimir o guardar en PDF». | [L 21] |
| No se pudo compartir (un error que no es `AbortError`) | No pudimos abrir Compartir. Usa «Copiar la lista». | [L 21] |

### 7.5 Qué se anuncia y por dónde

Por las regiones vivas de `Anuncios.tsx`, nunca con un `role` puesto sobre un elemento que aparece ya con su texto.

| Qué | Región | Cómo |
|---|---|---|
| «Cargando los insumos…» | `status` en el lugar | El patrón de `Cargando` de Insumos |
| Lista copiada | `status` (`polite`) | `Nota rol="status"` |
| Línea agregada, o quitada (de MATU o a mano) | `status` (`polite`) | `anunciar(texto, 'status')`, con los textos de 4.7 y 4.10 |
| «Lo que quitaste sigue en Insumos…» y «Quitaste todo de la lista…» | Ninguna | Se ven en la página. El anuncio de quitar ya lo dijo (4.10) |
| No se pudo copiar o compartir | `alert` (`assertive`) | `Anunciado urgencia="alert"` |
| Error al cargar | `alert` (`assertive`) | `Anunciado urgencia="alert"` |
| Cantidad o nombre con error | Ninguna | El foco va al campo, y su `aria-describedby` lee el error (como MATU-36, 3.4.3) |
| Compartir con éxito, imprimir | Ninguna | No hay nada que decir |
| El aviso fijo | Ninguna | Es parte de la página, y lo describe el botón principal (4.8) |

---

## 8. La vista impresa

**Objetivo:** un papel que quien compra lee de pie, sin anteojos, en blanco y negro.

### 8.1 Cómo se arma

- La pantalla monta, mientras está en `/insumos/lista`, una **hoja de impresión** con `createPortal` directo en `document.body`, fuera de `#raiz`, con `data-impresion` y la clase `hidden print:block`. En pantalla no existe a la vista ni para el lector de pantalla (`hidden`).
- La regla de la capa base (8.4) deja fuera del papel todo lo que no es esa hoja, siempre. Así **no puede colarse nada de la app**: ni el encabezado con el nombre de la persona, ni el selector de persona, ni el grupo, ni la navegación, ni el distintivo, ni los avisos, ni los botones, ni las regiones vivas. *(Cambió en la v1.1: la regla ya no depende de que exista la hoja.)*
- La hoja se arma con la misma función del texto compartido (7.2), así que trae lo que está en la pantalla en ese momento.

### 8.2 Cómo se ve en papel · *cambió en la v1.1 (la casilla, confirmada)*

```
┌──────────────────────────────────────────────┐   A4 o carta, margen de 18 mm arriba y abajo
│                                              │   y 16 mm a los lados
│  Lista de insumos · 06/11/2026               │   text-2xl font-bold (19 pt), Atkinson
│  ──────────────────────────────────────────  │   border-b-2 border-tinta
│  ☐  Pañal adulto talla M     6 envases de    │   text-lg (14 pt): nombre font-bold,
│                              20 unidades     │   cantidad normal, alineada a la derecha
│  ──────────────────────────────────────────  │   border-b border-borde
│  ☐  Toallitas húmedas         120 unidades   │
│  ──────────────────────────────────────────  │
│  ☐  Crema humectante              1 unidad   │
│  ──────────────────────────────────────────  │
│                                              │
│  Piloto académico con datos de prueba        │   text-base (12,75 pt), mt-8
└──────────────────────────────────────────────┘
```

- **Letra:** Atkinson Hyperlegible en todo, también en el título. En pantalla el titular es Bricolage porque es la identidad. En papel la hoja es una herramienta, y Atkinson está hecha para baja visión. Tamaños con la escala de siempre, que a 17 px por rem dan 19 pt el título, 14 pt las líneas y 12,75 pt el pie. Nada bajo 12 pt.
- **Color:** solo `tinta` para el texto, que en el tema claro es casi negro (14,1:1). **Nunca `tenue`, `turquesa` ni colores semánticos en papel:** una impresora en blanco y negro los aclara. Sin fondos. La hoja va sobre `bg-hoja`.
- **Líneas:** cada insumo en una grilla `grid grid-cols-[auto_minmax(0,1fr)_auto] items-baseline gap-x-4 py-3 border-b border-borde`, con `break-inside-avoid` para que una línea nunca quede partida entre dos páginas. El título lleva `break-after-avoid`.
- **La casilla se queda** (decisión 4 de Jorge, 06-11): un cuadrado vacío `size-4 rounded-sm border-2 border-tinta` `aria-hidden` delante de cada nombre, para tachar en el pasillo. Es la hoja del refrigerador, ahora en el bolsillo. No lleva texto. Solo existe en el papel: en el texto compartido no va, porque un `☐` llega como un cuadro roto en algunos teléfonos.
- **El nombre** se parte por palabras si es largo (`break-words`). **La cantidad** va a la derecha (`text-right`) y también puede bajar de renglón.
- **El pie** «Piloto académico con datos de prueba» [L 21] va una vez, al final de la lista y en el flujo (no fijo en cada página, porque un pie fijo tapa líneas en algunos navegadores).
- **Sin los días, sin el nombre de la persona, sin el grupo y sin la marca MATU.** Solo el título, las líneas y el pie (decisión de Jorge).

### 8.3 Título del documento y momento de imprimir

- Al tocar «Imprimir o guardar en PDF»: se valida (4.4), se espera `document.fonts.ready`, se cambia `document.title` a «Lista de insumos» [L 21] y se llama a `window.print()`.
- También con los eventos `beforeprint` y `afterprint` de `window`, para que Ctrl+P y el menú del navegador hagan lo mismo: en `beforeprint`, «Lista de insumos». En `afterprint`, vuelve a «Lista de insumos · MATU». Los eventos se escuchan solo mientras la pantalla está montada.
- Así el PDF se llama «Lista de insumos.pdf», y la cabecera que algunos navegadores imprimen en el margen dice «Lista de insumos» y la dirección `/insumos/lista`, que no lleva ids ni nombres.
- Con Ctrl+P y una cantidad inválida no se puede detener la impresión: la hoja usa el último valor válido de esa línea, o la cantidad sugerida si nunca hubo uno.

### 8.4 La regla de impresión de `web/src/index.css` · *cambió en la v1.1*

**Quién la aplica:** el frontend, en `web/src/index.css`, **copiándola tal cual** de este bloque, en el mismo PR de MATU-60 (decisión 6 de Jorge). La pega al final del archivo, después de los dos bloques del tema oscuro. Yo la reviso en la revisión visual (14). Si algo de ella no funciona, me lo devuelve y la corrijo aquí: no se cambia en el CSS sin cambiar esta sección.

**Vale para toda la app, en todas las pantallas** (familia, relevo, entrar y las demás que salen de `web/index.html`). Hace tres cosas:

1. **Fuerza el tema claro al imprimir.** Con el teléfono en tema oscuro, `tinta` sería `#E4EEEB` y el texto saldría casi blanco sobre el papel. Repite los valores claros que ya están en `@theme`, sin tokens nuevos, y va después de los dos bloques del tema oscuro para ganarles.
2. **Deja fuera del papel toda la app, siempre.** Todo hijo de `body` que no es una hoja de impresión (`#raiz`, y cualquier cosa que se monte con un portal) queda en `display: none`, y también un `dialog` abierto con `showModal`. No depende de qué pantalla está abierta ni de `:has()`, así que funciona también en un navegador que no conoce `:has()`. Va **fuera de `@layer`** a propósito: una regla sin capa gana a todas las capas de Tailwind, así que ninguna utilidad (`block`, `flex`) puesta mañana en un portal la puede deshacer. Cierra también el hueco de Ctrl+P en la ficha y en la página del relevo (ADR-029).
3. **En una pantalla sin hoja de impresión, deja una línea** en el papel: «Esta pantalla no se imprime.» **[NUEVO]**, decisión 6.

**Por qué una línea y no una hoja en blanco.** Una hoja en blanco parece una falla de la impresora: Carmen la vuelve a mandar, gasta papel y no entiende qué pasó. La línea dice qué pasó en cuatro palabras, y no lleva el nombre de la persona, de la pantalla ni del grupo, así que no revela nada si el papel queda olvidado en la bandeja de una impresora compartida. No dice cómo imprimir otra cosa, porque eso depende de la pantalla: en la ficha la respuesta es compartirla con un enlace (ADR-029) y en Insumos es la pestaña «Lista de insumos», y una línea que sirve en todas no puede decir las dos. Es el único texto de la app que vive en el CSS, porque tiene que salir en toda pantalla sin que cada una lo monte. Va igual en la sección 21 de `lenguaje.md`.

**Qué sale en el papel en cada caso:**

| Dónde se imprime | Qué sale |
|---|---|
| `/insumos/lista`, admin, cuidador o pagador, con el botón, Ctrl+P o el menú | La hoja de la lista (8.2) |
| `/insumos/lista`, observador, con Ctrl+P o el menú | Título, «Quien administra, cuida o paga puede imprimirla o compartirla.» y el pie (8.5) |
| Cualquier otra pantalla: Inicio, Insumos, la ficha, Compartir, Enlaces, Cuenta, Entrar, la página del relevo, un error | Solo «Esta pantalla no se imprime.», arriba a la izquierda, en `tinta`, Atkinson negrita `text-lg` (14 pt). Una página |
| Un navegador sin `:has()` (Firefox anterior a 121) en una pantalla sin hoja | Una hoja en blanco. Nunca la pantalla |

```css
/* Al imprimir, siempre el tema claro: el papel es blanco aunque el teléfono esté en oscuro.
   Mismos valores que @theme. Si cambia uno, cambia el otro (MATU-60, 8.4). */
@media print {
  :root:root,
  :root[data-tema='oscuro'],
  :root:not([data-tema='claro']) {
    color-scheme: light;
    --color-papel: #ecf3f2;
    --color-hoja: #ffffff;
    --color-tinta: #13252a;
    --color-tenue: #485b5f;
    --color-turquesa: #086764;
    --color-miel: #e3a43a;
    --color-pronto: #a8261b;
    --color-pronto-fondo: #fbe9e6;
    --color-atenta: #835000;
    --color-atenta-fondo: #fcefd8;
    --color-ok: #22663d;
    --color-ok-fondo: #e1f1e6;
  }
}

@page {
  margin: 18mm 16mm;
}

/* MATU no imprime pantallas (MATU-60 y ADR-029). Solo sale la hoja de impresión de una
   pantalla que la tenga (data-impresion), y en las demás una línea. Fuera de @layer a
   propósito: así ninguna utilidad de Tailwind la puede ganar. */
@media print {
  body > :not([data-impresion]),
  :modal {
    display: none;
  }
  body:not(:has(> [data-impresion]))::before {
    content: 'Esta pantalla no se imprime.';
    display: block;
    font-family: var(--font-sans);
    font-size: var(--text-lg, 1.125rem);
    line-height: 1.5;
    font-weight: 700;
    color: var(--color-tinta);
  }
}

@layer base {
  @media print {
    body {
      background: none;
      min-height: 0;
    }
  }
}
```

**Qué cambió frente a la v1.0:** la regla ocultaba `#raiz` solo si existía la hoja (`body:has(> [data-impresion]) > #raiz`). Ahora oculta todo lo que no es la hoja siempre, suma `:modal` y la línea, y sale de `@layer base`. El bloque del tema claro y `@page` no cambian.

**Cómo lo reviso (14):** la vista previa de impresión de Chrome en `/insumos/lista` con cada rol, en `/insumos`, en `/ficha`, en la página del relevo y con el diálogo de desactivar un insumo abierto, con el teléfono en tema oscuro. En la lista, la hoja y nada más. En las demás, la línea y nada más.

### 8.5 El observador y la impresión · *cambió en la v1.1*

El observador no tiene el botón, pero el navegador siempre deja imprimir. Para que lo impreso nunca tenga más que lo permitido, su hoja de impresión trae solo «Lista de insumos · `{fecha}`», «Quien administra, cuida o paga puede imprimirla o compartirla.» [L 21] y el pie. Ninguna línea. **Confirmado por Jorge el 06-11** (decisión 1). La nota va en `text-lg` y `tinta`, como las líneas, y el pie como en 8.2.

---

## 9. El campo nuevo en el formulario del insumo (Insumos, MATU-36)

**Objetivo:** Carmen anota, si quiere, cuántas unidades trae el paquete, y la lista le sugiere paquetes enteros en vez de «120 unidades».

### 9.1 Dónde va

- **Al final del formulario**, después de «¿Con cuántos días de anticipación te avisamos?» al anotar, y después del nombre y de la línea de la unidad al cambiar. Antes de la vista previa «Así, alcanza para…».
- **Por qué al final:** es opcional y no cambia la fecha. Ponerlo entre los campos que sí la cambian alarga el camino corto de anotar un insumo, que es el que MATU-36 cuida. Va en el mismo lugar al anotar y al cambiar.
- Solo `admin` y `cuidador` (los que ven el formulario).

```
│ ¿Con cuántos días de anticipación  │
│ te avisamos?                       │
│ [ − ] [  7  ] [ + ]  días antes    │
│                                    │
│ ¿Cuántas unidades trae cada        │  label font-bold
│ envase?                            │
│ Si lo anotas, la lista sugiere     │  ayuda text-base text-tenue, ANTES del campo
│ envases enteros. Puedes dejarlo en │
│ blanco.                            │
│ ┌──────────┐                       │  campo min-h-12 w-32, ring-2 ring-inset ring-borde
│ │          │ unidades              │  sufijo text-base text-tenue
│ └──────────┘                       │
│ ┃ Así, alcanza para 6 días, …     │  vista previa (sin cambios)
│ [ Guardar ]   Cancelar             │
```

### 9.2 Cómo es

| Parte | Componente y tokens | Texto |
|---|---|---|
| Etiqueta | `label` `font-bold` | «¿Cuántas unidades trae cada envase?» [L 21] |
| Ayuda | `span` `text-base text-tenue`, **antes** del campo (como la ayuda del `Stepper` en el mismo formulario), en el `aria-describedby` del campo | «Si lo anotas, la lista sugiere envases enteros. Puedes dejarlo en blanco.» [L 21] |
| Campo | `input type="text"` con `inputMode="numeric"`, `pattern="[0-9]*"`, `autoComplete="off"`, `maxLength={5}`, solo dígitos (`soloDigitos`). `cifras min-h-12 w-32 rounded-xl bg-hoja px-4 text-xl ring-2 ring-inset ring-borde`, foco `ring-turquesa` y el foco base. **Sin botones − y +**: los envases traen 20, 30 u 80, y de uno en uno no sirve | — |
| Sufijo | `span` `text-base text-tenue`, con `INSUMOS.sufijoStock(unidad)` | «unidades», «sobres», «ml» o «g» |
| Error | `MensajeError` bajo el campo, `aria-invalid` | 9.3 |

- **Al anotar:** vacío.
- **Al cambiar:** con el valor guardado. A diferencia de «¿Cuántos quedan hoy?», que va vacío a propósito (MATU-36, 3.4), el envase no envejece: describe el paquete, no lo que queda.
- **Al guardar:** se envía solo si cambió (decisión 41). Vacío se envía como `null`, que borra el dato (decisión 121 del contrato). Al anotar, vacío no se envía. *(Cambió en la v1.1.)*

### 9.3 Validación

Al tocar «Guardar», con el resto del formulario. El foco va al primer campo con error, en el orden del formulario.

| Caso | Texto | Fuente |
|---|---|---|
| Vacío | Sin error: es opcional | — |
| 0 o más de 10.000 | Escribe un número de 1 a 10.000, o déjalo en blanco. | [L 21] |
| 422 de la API en ese campo (`errores[].campo = unidades_por_envase`) | El mismo texto | [L 21] |

### 9.4 En el conflicto (412) de Insumos

Si la persona cambió este campo y otra persona guardó antes, los bloques «Lo que guardó» y «Lo tuyo, sin guardar» (MATU-36, 3.5) muestran el envase con «Cada envase trae `{u}` `{sufijo}`.» o «Sin unidades por envase.» [L 21], con «(cambió)» y negrita si es distinto. *(Precisado en la v1.2.)* Con `{u}` igual a 1, el sufijo va en singular: «Cada envase trae 1 unidad.», «Cada envase trae 1 sobre.» (con ml y g no cambia). Es la misma regla de 4.5, y la arma la misma `sufijoCantidad(u, unidad, null)` de `textoLista.ts`.

### 9.5 Lo que no cambia

La fila de Insumos no muestra el envase. La vista previa no lo usa. La confirmación sigue siendo «Guardamos «`{nombre}`». …» [M36].

---

## 10. Accesibilidad visual · *cambió en la v1.1 (10.1, 10.2, 10.3, 10.4 y 10.5)*

### 10.1 Elementos en `turquesa` macizo

| Estado | Cantidad |
|---|---|
| Lista, admin, cuidador o pagador, con `navigator.share` | 1: «Compartir la lista» |
| Lista, sin `navigator.share` | 1: «Imprimir o guardar en PDF» |
| Lista, observador | 0 |
| Vacía, o «Quitaste todo de la lista» | 0 («Agregar otro insumo» es secundario) |
| Panel «Agregar otro insumo» abierto | 1: la acción de salida («Agregar» es secundario, y el chip elegido de «¿Cómo se cuenta?» va en `bg-rocio`, no macizo) |
| Error al cargar | 1: «Volver a intentar» |
| Falta el permiso, hay que renovar, no encontrado | 0 |
| Insumos (`/insumos`), con las pestañas | Sin cambios: 1, «Anotar un insumo» |

La pestaña activa va en `text-turquesa` con borde inferior: texto y línea, no un bloque macizo.

### 10.2 Áreas táctiles de 48 × 48 px

Las pestañas (`min-h-12`), los botones − y + (`size-12`), cada campo «Cantidad» y el del envase (`min-h-12`), «Agregar otro insumo», «Agregar», «Cancelar», «Quitar de la lista» (`Boton` con `min-h-12`), cada chip de «¿Cómo se cuenta?» (`min-h-12`, el chip entero) y los tres botones de salida. Entre «Quitar de la lista» y el `Stepper` de la misma línea, al menos `gap-4` (en ancho, `gap-x-6`), para no tocarlo por error con el pulgar al usar el +. Entre chips, `gap-2`.

### 10.3 Contraste (valores de DISENO.md, sin colores nuevos)

| Elemento | Claro | Oscuro |
|---|---|---|
| Nombre y cantidad (`tinta` sobre `hoja`) | sobre 14:1 | sobre 13:1 |
| Días y bajada (`tenue` sobre `hoja` y `papel`) | 7,2:1 y 6,4:1 | 8,1:1 y 9,2:1 |
| Botón principal (`papel` sobre `turquesa`) | 6,0:1 | 9,4:1 |
| Botones secundarios y pestaña activa (`turquesa` sobre `hoja` y `papel`) | 6,7:1 y 6,0:1 | 8,2:1 y 9,4:1 |
| Anillo de los secundarios (`turquesa` al 70 %) | 3,5:1 | lo mido en la revisión |
| Borde de los campos y de los chips sin elegir (`borde`) | 3,5:1 sobre `hoja` | 4:1 sobre `hoja` |
| Chip elegido (`turquesa` sobre `rocio`, texto y anillo) | lo mido en la revisión (por cálculo, sobre 5,5:1) | lo mido en la revisión |
| «Quitar de la lista» (`pronto` sobre `hoja`) | lo mido en la revisión (por cálculo, sobre 6:1) | lo mido en la revisión |
| Aviso (`tinta` sobre `atenta-fondo`), ícono `atenta` | lo mido en la revisión (por cálculo, sobre 12:1 el texto) | igual |
| Error (`pronto`) | 6,1:1 sobre su fondo | lo mido en la revisión |
| Foco base (`turquesa`, 3 px, separación 2 px) | 6,0:1 sobre `papel` | 9,4:1 |

### 10.4 Foco y orden de tabulación

El orden del documento, sin `tabIndex` positivos:

1. Pestaña «Insumos», pestaña «Lista de insumos».
2. (El `h1` recibe el foco al llegar, pero no está en el orden de Tab.)
3. Por cada línea editable: −, campo «Cantidad», +, «Quitar de la lista». En todas las líneas, de MATU o a mano.
4. «Agregar otro insumo». Abierto: campo del nombre, «¿Cómo se cuenta?» (una sola parada, con las flechas entre opciones), −, «Cantidad», +, «Agregar», «Cancelar».
5. El botón principal, después los secundarios, en el orden de 4.9.

En ancho, la columna derecha va **después** de la izquierda en el DOM, así que el orden es el mismo que a 360 px. El foco nunca queda tapado por la barra de secciones del teléfono: el `scroll-padding-bottom` de la capa base y el `telefono:pb-36` del `main` ya lo cubren. El mensaje bajo los botones se desplaza a la vista con `scrollIntoView({ block: 'nearest' })`.

| Después de | El foco va a |
|---|---|
| Llegar a la ruta | El `h1` |
| Abrir «Agregar otro insumo» | El campo del nombre |
| Agregar, Cancelar o `Esc` | «Agregar otro insumo» |
| Quitar de la lista | El campo «Cantidad» de la línea siguiente, o «Agregar otro insumo» si era la última (también si no queda ninguna, 4.10) |
| Un error de validación | El primer campo con error |
| Copiar, compartir o imprimir | Se queda en el botón |
| 403 de admin o cuidador | El `h1` del permiso en `/insumos` |

### 10.5 Texto al 200% en 320 px (160 px efectivos)

- Sin desplazamiento horizontal: `scrollWidth <= innerWidth` en todos los estados.
- La app entra en modo `angosto`: rellenos `px-2`, el `Boton` oculta sus íconos, la `Nota` achica su separación.
- El `Stepper` envuelve: −, el campo y + pueden quedar en renglones distintos, y el sufijo «envases de 20 unidades» baja solo. Ningún elemento suelto mide más de 160 px (el campo mide 6 rem, 102 px).
- Los nombres se parten con `break-words [overflow-wrap:anywhere]` (un nombre de 60 caracteres sin espacios no desborda).
- Las pestañas envuelven (`flex-wrap`).
- Los chips de «¿Cómo se cuenta?» van uno bajo el otro (`angosto:flex-col`), y su texto se parte si hace falta.
- «Quitar de la lista» se parte en dos renglones si no cabe, sin salirse de la línea.
- Los botones quedan uno bajo el otro, al ancho de su texto, y su texto se parte por palabras.
- La columna `sticky` solo existe en ancho, así que con el texto al 200% no se activa.

### 10.6 Tema claro y oscuro

Los mismos tokens con sus valores oscuros, sin colores propios. La pestaña activa, el aviso `atenta`, el mensaje `ok` y el error `pronto` tienen su par oscuro en `index.css`. **La impresión siempre en claro** (8.4). La demo del proyector va en claro.

### 10.7 Movimiento

Solo `aparecer` (180 ms) en el mensaje de copiado. El panel de agregar aparece sin animación. Con `prefers-reduced-motion`, todo inmediato.

---

## 11. Lo que el frontend NO debe hacer

| Nunca | Por qué |
|---|---|
| Guardar las cantidades cambiadas, las líneas agregadas, las quitadas o el texto en `localStorage`, `sessionStorage`, IndexedDB, cookies o la caché del navegador | Viven solo en la memoria de la página (registro de tratamientos, CLAUDE.md agente 3). Se pierden al salir de la vista, al cambiar de persona o grupo y al salir de MATU |
| Poner la lista, un nombre, una cantidad o un id en la URL (consulta o fragmento) o en el `<title>` | CLAUDE.md, agente 3 |
| Enviar al servidor las cantidades cambiadas, las líneas agregadas a mano o las quitadas, o llamar a una ruta del insumo (desactivar, resolver la alerta) al quitar una línea | «No lo guardamos» [L 21]. La lista se arma con lo que el grupo ya ve, y nada nuevo llega al servidor |
| Generar un PDF en el navegador (jsPDF, `Blob`, descargas) o en el servidor, o crear un enlace a la lista | ADR-031: solo `window.print()` |
| Pasar `title`, `url` o `files` a `navigator.share` | ADR-031: solo texto |
| Incluir los días, el nombre de la persona cuidada, el del grupo, un enlace o el nombre de quien comparte en el texto o en el papel | ADR-031, punto 4 |
| Imprimir la pantalla: el encabezado, el selector de persona, la navegación, los avisos o los botones, aquí o en cualquier otra pantalla | Decisión de Jorge. La hoja de impresión es lo único que sale (8.1), y en las demás pantallas la línea de 8.4 |
| Cambiar la regla de impresión de 8.4 al copiarla, o escribir otra `@media print` en un componente | Es una sola regla para toda la app (8.4) |
| Pedir confirmación antes de quitar una línea, o mostrar «Deshacer» | Decisión de Jorge: igual que «Quitar» de lo agregado. La línea de MATU vuelve al entrar de nuevo (4.10) |
| Dejar «¿Cómo se cuenta?» sin opción elegida, o usar un `select` | 4.7 |
| Copiar o compartir sin que la persona toque el botón, o copiar al cargar | La salida siempre es una decisión de la persona |
| Poner un cuadro de confirmación antes de imprimir, compartir o copiar, o un aviso que se cierra | Decisión de Jorge: el aviso fijo basta |
| Decir «Enviada» o «Compartida» después de `navigator.share` | MATU no sabe si se envió |
| Mostrar una lista vieja si falla la carga, o pintar días o cantidades que la API no devolvió | Sin interfaz optimista que oculte errores (CLAUDE.md, agente 3) |
| Botones o campos deshabilitados para el observador | No se muestran (2.4) |
| Precios, comercios, «Comprar», «Pedir», «Reponer», «lista de reposición», «quiebre» o «stock» | Lenguaje 3.2 y 21 |
| Usar `document.execCommand('copy')` u otro truco de copia | Solo `navigator.clipboard.writeText`. Si falla, el mensaje de 7.4 |
| Colores, tamaños o sombras escritos a mano, o `style={{…}}` | Política 9. Las grillas con `[…]` son geometría, como en Insumos |
| Analítica, scripts de terceros o registrar en consola el texto de la lista | CLAUDE.md, agente 3 |
| Mostrar `title`, `detail` o `request_id` de un error | Lenguaje 8 |

---

## 12. Componentes y estados · *cambió en la v1.1*

| Componente | Normal | Foco | Presionado | Cargando | Error | Vacío |
|---|---|---|---|---|---|---|
| `Pestanas` | `text-tenue`, borde transparente | foco base | — | — | — | — |
| Pestaña activa | `text-turquesa font-bold border-b-3 border-turquesa`, `aria-current="page"` | foco base | — | — | — | — |
| Línea | `bg-hoja ring-1 ring-linea rounded-xl` | — (no es interactiva) | — | — | — | sección 5, o 4.10 si se quitaron todas |
| Línea agregada a mano | igual, con la `Etiqueta` «Solo en esta pantalla» | — | — | — | — | — |
| `Stepper` «Cantidad» | campo `ring-borde`, botones `ring-turquesa/70` | foco base | `bg-rocio` en − y + | — | `ring-pronto` y `MensajeError` | — |
| Campo del envase | `ring-borde` | `ring-turquesa` y foco base | — | — | `ring-pronto` y `MensajeError` | vacío, sin texto de ejemplo |
| Panel de agregar | `bg-hoja ring-1 ring-linea rounded-xl` | foco al nombre | — | — | errores en sus campos | — |
| «¿Cómo se cuenta?» (`GrupoOpciones forma="chips"`) | sin elegir: `bg-hoja text-tenue ring-borde`, círculo vacío `ring-tenue` · elegido: `bg-rocio text-turquesa ring-turquesa`, círculo con punto `bg-turquesa` | foco base sobre el chip (`has-[:focus-visible]`) | — | — | — (siempre hay una elegida) | «Unidades» elegida al abrir |
| Aviso fijo | `Nota` `atenta` con borde e `Info` | — | — | — | — | no se muestra sin líneas |
| Botón principal | `turquesa` macizo, texto `papel` | foco base | `active:brightness-95` | — | — (el error va debajo) | — |
| Botones secundarios | `hoja` con anillo `turquesa/70` | foco base | `bg-rocio` | — | — | — |
| «Quitar de la lista» | `textoPeligro`, en toda línea editable | foco `pronto` (ya en el `Boton`) | subrayado pleno | — | — | — |
| «Lo que quitaste sigue en Insumos…» | `p` `max-w-prose text-base text-tenue` | — | — | — | — | — |
| «Quitaste todo de la lista…» | `p` `max-w-prose text-lg` | — | — | — | — | es el vacío después de quitar (4.10) |
| Mensaje de copiado | `Nota` `ok` con `CircleCheck`, `aparecer` | — | — | — | — | — |
| Mensaje de error | `MensajeError` en `Anunciado` `alert` | — | — | — | — | — |
| Hoja de impresión | `hidden print:block`, `bg-hoja text-tinta` | — | — | — | — | solo título, nota y pie (observador, 8.5) |
| Otra pantalla, al imprimir | la línea «Esta pantalla no se imprime.» de la regla de 8.4 | — | — | — | — | — |

**Íconos (`lucide-react`, todos `aria-hidden`):** `Share2`, `Printer`, `Copy`, `Plus`, `Minus`, `Pencil`, `Info`, `CircleAlert`, `CircleCheck`, `ListChecks`, `CloudOff`, `Lock`, `Hourglass`.

---

## 13. Textos para `lenguaje.md`, sección 21 · *cambió en la v1.1*

Es la tabla final de la sección 21, para pegarla tal cual en el PR de documentos. Reemplaza la tabla actual. Trae los textos aprobados el 06-11 (los de la sección 21 y los 14 que estaban propuestos en la v1.0), y los **[NUEVO]** y **[AJUSTE]** de esta versión, que Jorge aprueba en el mismo PR (D6). El texto de introducción de la sección y el formato del texto compartido no cambian, salvo el ejemplo, que puede sumar una línea agregada a mano («- Toallitas para el baño: 2 envases»).

| Dónde | Texto |
|---|---|
| Título de la pantalla | Lista de insumos |
| Pestañas de la sección Insumos | Insumos · Lista de insumos |
| Nombre de las pestañas, para el lector | Vistas de Insumos |
| Título de la pestaña del navegador | Lista de insumos · MATU (al imprimir: Lista de insumos) |
| Título impreso y primera línea del texto compartido | Lista de insumos · {DD/MM/AAAA} |
| Bajada | Lo que se acaba pronto, con una cantidad sugerida para 30 días. Puedes cambiarla antes de imprimir o compartir. |
| Bajada, observador | Lo que se acaba pronto, con una cantidad sugerida para 30 días. |
| Línea, en pantalla | {nombre} · {cantidad} · Alcanza para {n} días / Alcanza para 1 día / Se acaba hoy / Puede que ya no quede |
| Línea agregada a mano, en pantalla | Solo en esta pantalla |
| Cantidad, con envase conocido | {n} envases de {u} unidades / 1 envase de {u} unidades (con sobres, ml o g: «de {u} sobres», «de {u} ml», «de {u} g». Con {u} igual a 1: «de 1 unidad», «de 1 sobre») |
| Cantidad, sin envase | {n} unidades / {n} sobres / {n} ml / {n} g (con 1: «1 unidad», «1 sobre») |
| Cantidad, agregado a mano | {n} unidades / {n} sobres / {n} envases (con 1: «1 unidad», «1 sobre», «1 envase») |
| Etiqueta del campo | Cantidad |
| Botones del campo, para el lector | Menos: Cantidad de {nombre} · Más: Cantidad de {nombre} |
| Cantidad fuera de rango | Escribe una cantidad de 1 a 100.000. |
| Nota del cálculo | Es una sugerencia con lo que anotaste, y ya descuenta lo que queda. Cambia la cantidad si necesitas otra. |
| Nota del cálculo, pagador | Es una sugerencia con lo que anotó la familia, y ya descuenta lo que queda. Cambia la cantidad si necesitas otra. |
| Nota del cálculo, observador | Es una sugerencia con lo que anotó la familia, y ya descuenta lo que queda. |
| Agregar a mano | Agregar otro insumo · Por ejemplo: «Toallitas húmedas». Sin remedios ni para qué se usa · Esto queda solo en esta pantalla. No lo guardamos. |
| Agregar a mano, cómo se cuenta | ¿Cómo se cuenta? (de la sección 18) · Unidades · Sobres · Envases |
| Agregar a mano, botón | Agregar |
| Agregar a mano, anuncio | Agregamos «{nombre}» a la lista. |
| Quitar una línea | Quitar de la lista · Para el lector: Quitar de la lista: {nombre} |
| Quitar, anuncio, línea de MATU | Quitamos «{nombre}» de la lista. Sigue en Insumos. |
| Quitar, anuncio, línea agregada a mano | Quitamos «{nombre}» de la lista. |
| Después de quitar una línea de MATU | Lo que quitaste sigue en Insumos. Vuelve a esta lista cuando entras de nuevo. |
| Sin líneas, después de quitarlas todas | Quitaste todo de la lista. Si quieres, agrega uno a mano. |
| Aviso, siempre visible sobre los botones | La lista no lleva el nombre de {pila}, pero sí lo que usa. Lo que imprimas o compartas sale de MATU y no podemos borrarlo. Compártela solo con quien va a comprar. |
| Botones | Imprimir o guardar en PDF · Compartir la lista · Copiar la lista |
| Copiada | Copiamos la lista. Pégala donde quieras. |
| No se pudo copiar | No pudimos copiar la lista. Usa «Compartir la lista». |
| No se pudo copiar, sin Compartir en el navegador | No pudimos copiar la lista. Usa «Imprimir o guardar en PDF». |
| No se pudo compartir | No pudimos abrir Compartir. Usa «Copiar la lista». |
| Sin insumos | No hay insumos que se acaben pronto. Si quieres, agrega uno a mano. |
| Sin insumos, observador | No hay insumos que se acaben pronto. |
| Observador | Quien administra, cuida o paga puede imprimirla o compartirla. |
| Error al cargar | No pudimos traer la lista. Revisa tu conexión e inténtalo de nuevo. |
| Sin autorización o revisión vencida | Los textos de «Permiso» de la sección 18 |
| Pie del texto compartido y de la impresión | Piloto académico con datos de prueba |
| Al imprimir cualquier otra pantalla de la app | Esta pantalla no se imprime. |
| Campo nuevo en el formulario del insumo (opcional) | ¿Cuántas unidades trae cada envase? · Ayuda: Si lo anotas, la lista sugiere envases enteros. Puedes dejarlo en blanco. |
| Campo del envase, fuera de rango | Escribe un número de 1 a 10.000, o déjalo en blanco. |
| Campo del envase, en el conflicto (412) | Cada envase trae {u} {unidades / sobres / ml / g}. (con 1: «Cada envase trae 1 unidad.», «Cada envase trae 1 sobre.») · Sin unidades por envase. |

**Qué es nuevo o cambió en esta versión**, para la descripción del PR:

| Fila | Estado | Antes | Por qué |
|---|---|---|---|
| Cantidad, agregado a mano | [NUEVO] | Solo «{n} unidades» | Decisión 2: unidades, sobres o envases |
| Cantidad, con envase de 1 | [NUEVO], precisión | No estaba | El singular de «Cantidad, sin envase» aplicado al envase |
| Agregar a mano, cómo se cuenta | [NUEVO] las opciones | No estaba | Decisión 2. La leyenda ya está aprobada en la sección 18 |
| Quitar una línea | [AJUSTE] | Quitar · Quitar «{nombre}» | Decisión 3: en una línea de MATU, «Quitar» se lee como borrar el insumo de MATU |
| Quitar, anuncio, línea de MATU | [NUEVO] | No estaba | Decisión 3 |
| Quitar, anuncio, línea agregada a mano | [AJUSTE] | Quitamos «{nombre}». | El mismo verbo y complemento que el botón |
| Después de quitar una línea de MATU | [NUEVO] | No estaba | Decisión 3: quien no usa lector también tiene que saber que no se borró nada |
| Sin líneas, después de quitarlas todas | [NUEVO] | No estaba | Decisión 3: «No hay insumos que se acaben pronto» sería falso |
| Nota del cálculo (los tres roles) | [AJUSTE] | Es una sugerencia con lo que anotaste. Cambia la cantidad si necesitas otra. (y sus versiones para pagador y observador) | La cantidad ahora descuenta lo que queda (4.6) |
| Al imprimir cualquier otra pantalla de la app | [NUEVO] | No estaba | Decisión 6 (8.4) |

---

## 14. Cómo la voy a revisar · *cambió en la v1.1*

No apruebo una pantalla que no vi funcionando. El frontend deja la pantalla levantable en local contra el doble del contrato, con:

- una lista con tres insumos (6, 1 y 0 días), uno con −2 días, uno con envase («6 envases de 20 unidades»), uno sin envase en sobres, uno en ml con envase, uno con un nombre de 60 caracteres sin espacios y uno con 1 envase
- la lista vacía, y el mismo doble en Insumos, para comprobar que la lista trae lo mismo que «Se acaban pronto»
- 403 `sin-consentimiento` con rol `cuidador` y con rol `observador`, 403 `revision-vencida`, un 404 y un 500
- los cuatro roles
- el navegador con y sin `navigator.share`, y `navigator.clipboard.writeText` que falla
- agregar a mano en unidades, en sobres y en envases, con 1 y con 2, y quitar después
- quitar una línea de MATU, quitar todas, y volver a entrar para ver que las de MATU vuelven
- el formulario de Insumos con el campo nuevo, al anotar y al cambiar, con 0, con 10.001, vaciándolo al cambiar y con un 412 que lo incluye.

**Capturas:** cada estado a 360 × 740, 1280 × 720 y 1920 × 1080, en claro y oscuro, a 320 px con el texto al 200%, y con `prefers-reduced-motion`. El panel de agregar abierto a 360 px, con los chips en dos renglones. **La impresión:** la vista previa de impresión de Chrome y el PDF guardado, con el teléfono en tema oscuro, en A4 y carta, en blanco y negro, con una lista que ocupe dos páginas, con una línea agregada en envases y con una línea de MATU quitada. **La regla de 8.4 en otras pantallas:** la vista previa en `/insumos`, `/ficha`, la página del relevo y con el diálogo de desactivar abierto, que deben mostrar solo «Esta pantalla no se imprime.».

**En cada una mido:** `scrollWidth <= innerWidth`, el alto de lo que se toca, el contraste del texto y de los bordes, el foco visible con Tab (también al abrir y cerrar el panel, al moverse entre los chips con las flechas y al quitar una línea), la tabla de `turquesa` macizo (10.1), que ningún texto quede bajo 17 px, y que lo copiado, lo compartido y lo impreso digan exactamente lo mismo, sin días, sin el nombre de la persona y sin las líneas quitadas. Comparo la regla de `web/src/index.css` con el bloque de 8.4, carácter por carácter.

---

## 15. Resumen · *cambió en la v1.1*

**Decisiones de diseño:**

1. **El acceso son pestañas** «Insumos» y «Lista de insumos» antes del título, como Compartir y Enlaces. No un botón dentro de «Se acaban pronto», porque el aviso nunca ofrece comprar y porque el bloque desaparece sin alertas.
2. **El botón principal depende del teléfono:** «Compartir la lista» si hay hoja de compartir, «Imprimir o guardar en PDF» si no. «Copiar la lista» siempre, secundario. Es la regla de MATU-48.
3. **El aviso fijo es una `Nota` `atenta` con `Info`**, justo sobre los botones, y describe al botón principal para el lector de pantalla.
4. **La línea muestra nombre, días y cantidad**, con el campo al final, junto al pulgar. «Cantidad» es el `Stepper` editable de Insumos.
5. **Agregar a mano es un panel que se abre en el lugar**, con «Agregar» secundario. Las líneas agregadas llevan «Solo en esta pantalla» y se cuentan en unidades, sobres o envases, con el `GrupoOpciones` de chips que ya existe y «Unidades» elegida al abrir. A 360 px los chips van en dos renglones: no caben en uno sin perder el círculo que marca la opción elegida.
6. **Toda línea editable se puede quitar** con «Quitar de la lista», sin confirmación. Una línea de MATU sale solo de la pantalla, el anuncio dice «Sigue en Insumos» y una nota visible dice que vuelve al entrar de nuevo. Sin líneas, un texto propio, no el del vacío.
7. **La impresión es una hoja aparte**, montada fuera de `#raiz`. Va siempre en tema claro, en Atkinson, solo en `tinta`, con la casilla vacía para tachar, y comparte la función que arma el texto. Así el papel y el mensaje no pueden diferir.
8. **La regla de impresión deja fuera del papel toda la app, en todas las pantallas**, sin depender de `:has()` y fuera de `@layer` para que ninguna utilidad la gane. Donde no hay hoja de impresión sale «Esta pantalla no se imprime.», y no una hoja en blanco.
9. **La bajada se queda y la nota del cálculo dice que ya descuenta lo que queda.**
10. **El campo del envase va al final del formulario**, sin − ni +, con el valor guardado al cambiar, y vacío se envía como `null`.

**Para Jorge:** los textos [NUEVO] y [AJUSTE] de la sección 13 (D6).

**Para el orquestador:** D7 (el registro de tratamientos dice «consumo de 30 días»), y que el frontend copie la regla de 8.4 sin cambios en `web/src/index.css`.

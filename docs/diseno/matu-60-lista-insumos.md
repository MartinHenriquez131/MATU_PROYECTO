# MATU-60 · Lista de insumos · Especificación de diseño

**Versión 1.0 · 06/11/2026** · agente 6 (UI/UX) · para el frontend, antes de construir
**Historia:** MATU-60, la lista de insumos (RF-14 y RF-15, ADR-031). Con los insumos que tienen una alerta abierta, MATU arma una lista con una cantidad sugerida para 30 días, que la familia puede ajustar, imprimir o compartir como texto.
**Dónde se construye:** `web/`, dentro de la sección «Insumos» de la app de la familia (MATU-39 y MATU-36), React 19, TypeScript y Tailwind CSS v4, mobile first.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` · las decisiones de Jorge del 06-11 con la revisión del analista normativo · `docs/lenguaje.md` del repositorio MATU, sección 21 (y las secciones 3, 8, 13, 16, 17 y 18) · ADR-031 · `docs/legal/politica-privacidad.md` («La lista de insumos») y `docs/legal/registro-tratamientos.md` (entrada «Lista de insumos») · las especificaciones `matu-36-insumos.md`, `matu-37-alertas.md` y `matu-48-compartir.md` de esta carpeta · el código actual de `web/src/familia/Insumos.tsx`, `ui.tsx`, `ruteo.ts`, `Shell.tsx` y `web/src/compartido/ui/Anuncios.tsx`.

**Cómo se lee:** los textos entre comillas latinas «» van tal cual. **[L 21]** es un texto aprobado por Jorge el 06-11 en la sección 21 de `lenguaje.md`. **[L 18]**, **[L 17]**, **[L 8]** son de esas secciones. **[M36]** es un texto ya aprobado en `matu-36-insumos.md`. **[PROPUESTO]** es un texto nuevo que no se usa hasta que Jorge lo apruebe. Las llaves son datos: `{pila}` es el nombre de pila de la persona cuidada (como lo calcula hoy `Insumos.tsx`), `{nombre}` es el nombre del insumo, `{n}` son los días que quedan, `{u}` son las unidades por envase y `{fecha}` es la fecha de hoy en Chile en `DD/MM/AAAA`.

**Tokens:** ningún token nuevo. Todo sale de la capa de `web/src/index.css`. Hace falta **una regla nueva en la capa base para imprimir** (sección 8.4), que no agrega tokens: repite los valores del tema claro dentro de `@media print`.

---

## 0. Lo que tiene que decidir alguien más

| # | Qué | Para quién | Lo que hace la especificación mientras tanto |
|---|---|---|---|
| D1 | **El contrato de la lista todavía no está.** La pantalla necesita, por línea: el id del insumo, su nombre, los días que quedan, la cantidad sugerida ya calculada (en envases o en la unidad), la unidad y las unidades por envase (o `null`). Ordenada por fecha estimada | Orquestador → backend (lo está escribiendo otro agente en `docs/api/`) | Usa los nombres que fije el contrato. Si la lista viene paginada, se agrega «Ver más» como en Insumos (MATU-36, 3.2) |
| D2 | **Borrar las unidades por envase.** El `PATCH` del insumo responde 422 `null_no_admitido` a un `null`. Para dejar el campo nuevo en blanco al cambiar un insumo, el contrato tiene que aceptar `unidades_por_envase: null` | Orquestador → backend | La pantalla envía `null` cuando la persona vacía el campo |
| D3 | **Qué imprime el observador con Ctrl+P o el menú del navegador.** El observador no tiene los botones, pero el navegador siempre deja imprimir | Jorge | La hoja impresa del observador trae solo el título, «Quien administra, cuida o paga puede imprimirla o compartirla.» y el pie. Nunca la pantalla, que lleva los días y el nombre de la persona (8.5) |
| D4 | **Las otras pantallas de la app se imprimen tal como se ven.** Hoy Ctrl+P en `/ficha` imprime la ficha con el nombre de la persona, y ADR-029 dice que la ficha no se imprime. Está fuera del alcance de MATU-60 | Orquestador → Jorge, para otra historia | Nada. Lo dejo anotado |
| D5 | **Quién aplica la regla de impresión** de la sección 8.4 en `web/src/index.css`. El archivo dice que los tokens son del diseñador, y el encargo de hoy me pide no editarlo sin avisar | Orquestador | La regla va escrita completa en 8.4. La aplico yo con su autorización, o el frontend la copia tal cual en el mismo PR |

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

  `aria-label` del `nav`: «Vistas de Insumos» **[PROPUESTO]**, como «Vistas de Compartir» en MATU-48.

- **Por qué pestañas y no un botón dentro de «Se acaban pronto»:** el bloque de MATU-37 tiene una regla, «el aviso nunca ofrece comprar» [L 17], y una lista para conseguir insumos, puesta dentro del aviso, se lee como una invitación a comprar. Además, el bloque no se muestra cuando no hay alertas, y la lista sirve igual para agregar algo a mano. La pestaña está siempre, no compite con «Anotar un insumo» (que sigue siendo el único `turquesa` macizo de Insumos) y no agrega un segundo botón al bloque.
- **Dónde se ven las pestañas:**
  - En `/insumos` con la lista cargada (con o sin insumos) y en `/insumos/lista` en todos sus estados.
  - **No** en el permiso de Insumos (MATU-36, 3.1), en «Falta el permiso» o «Hay que renovar» de `/insumos`, ni en el formulario a 360 px (`/insumos/nuevo` y `/insumos/cambiar` reemplazan a la lista: son un momento, no una vista).
  - En pantalla ancha con el formulario abierto en la columna derecha, las pestañas siguen arriba con «Insumos» activa.
- **Roles:** las cuatro ven las dos pestañas. La lista la ven todos los miembros (registro de tratamientos).

### 2.2 Título, foco y `<title>`

- `h1` con el componente `Titulo` (`id="titulo-pagina"`, `tabIndex={-1}`), con la clase de Insumos: `text-3xl @2xl/main:text-5xl`. Texto: «Lista de insumos» [L 21].
- Al llegar a la ruta, el foco va al `h1`, como en toda la app.
- `<title>`: «Lista de insumos · MATU» **[PROPUESTO]**, con la convención de `tituloDe` en `AppFamilia.tsx`. **Durante la impresión**, «Lista de insumos» (8.3).
- Sin transiciones entre vistas. Solo `aparecer` (180 ms) en los avisos. Con `prefers-reduced-motion`, inmediato (ya lo hace la capa base).

### 2.3 Composición

- Vive dentro del `<main id="contenido">` de `ShellFamilia`, con sus márgenes.
- **A 360 px y hasta 48 rem de contenido:** una columna. Orden: pestañas, título, bajada, líneas, nota, «Agregar otro insumo», aviso, botones y mensaje.
- **Desde 48 rem de contenido** (el mismo `useAncho` de `Insumos.tsx`): dos columnas `grid grid-cols-[3fr_2fr] items-start gap-10`, como Insumos. A la izquierda las líneas, la nota y «Agregar otro insumo». A la derecha el aviso, los botones y el mensaje, en una columna `flex flex-col items-start gap-4` con `sticky top-6`, para que los botones sigan a la vista con una lista larga. Es la composición de la tabla de DISENO.md (sección 3): a la izquierda las cantidades, a la derecha la salida.

### 2.4 Roles

| Rol | Ve | Puede |
|---|---|---|
| `admin`, `cuidador`, `pagador` | Todo | Cambiar la cantidad, agregar y quitar a mano, imprimir, compartir y copiar |
| `observador` | Las líneas con nombre, cantidad y días | Nada. Sin campos, sin «Agregar otro insumo», sin aviso y sin botones. **No se muestran deshabilitados: no se muestran.** Ve el texto «Quien administra, cuida o paga puede imprimirla o compartirla.» [L 21] |

El campo nuevo del formulario del insumo (sección 9) es de Insumos, así que solo lo ven `admin` y `cuidador`, que son quienes anotan y cambian insumos (MATU-36, 2.4).

---

## 3. Estados y cómo se llega a cada uno

```
abre /insumos/lista ─► GET de la lista (D1)
                      ├─ 200 con líneas ─► lista (4)
                      ├─ 200 sin líneas ─► vacía (5)
                      ├─ 403 sin-consentimiento ─► admin o cuidador: reemplaza a /insumos, que muestra el permiso (MATU-36, 3.1)
                      │                          └► pagador u observador: «Falta el permiso» (6.2)
                      ├─ 403 revision-vencida ─► «Hay que renovar» (6.3), para todos
                      ├─ 401 ─► lo que ya hace la app (renovar la entrada una vez y, si falla, Entrar)
                      ├─ 404 ─► lenguaje 8, no-encontrado (6.4)
                      └─ red o 5xx ─► error al cargar (6.1)
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

### 4.1 Esquema a 360 px (admin, cuidador o pagador, con `navigator.share`)

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
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ Toallitas húmedas              │ │
│ │ (!) Se acaba hoy               │ │  CircleAlert text-atenta + texto text-tinta
│ │ Cantidad                       │ │
│ │ [ − ] [ 120 ] [ + ] unidades   │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │  agregado a mano
│ │ Crema humectante               │ │
│ │ (✎ Solo en esta pantalla)      │ │  Etiqueta neutra con Pencil
│ │ Cantidad                       │ │
│ │ [ − ] [  1  ] [ + ] unidad     │ │
│ │                         Quitar │ │  textoPeligro, min-h-12
│ └────────────────────────────────┘ │
│ Es una sugerencia con lo que       │  nota text-base text-tenue
│ anotaste. Cambia la cantidad si    │
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
│ │ Pañal adulto talla M          Cantidad       │   │┃(i) La lista no lleva el  │ │
│ │ Alcanza para 6 días           [−][ 6 ][+]    │   │┃nombre de María, pero sí  │ │
│ │                               envases de 20 u│   │┃lo que usa. Lo que…       │ │
│ ├──────────────────────────────────────────────┤   └───────────────────────────┘ │
│ │ Toallitas húmedas             Cantidad       │   [ Imprimir o guardar en PDF ] │
│ │ (!) Se acaba hoy              [−][120][+]    │   [ Copiar la lista ]           │
│ │                               unidades       │   (✓) Copiamos la lista…        │
│ └──────────────────────────────────────────────┘          (columna sticky top-6) │
│ Es una sugerencia con lo que anotaste. Cambia la cantidad si necesitas otra.     │
│ [ + Agregar otro insumo ]                                                        │
└──────────────────────────────────────────────────────────────────────────────────┘
```

- Cada línea es `grid grid-cols-1 @3xl/main:grid-cols-[minmax(0,1fr)_auto] @3xl/main:items-center gap-x-6 gap-y-2`: nombre y días a la izquierda, la cantidad a la derecha. A 360 px, una sola columna.
- A 1920 px no cambia nada: el contenido ya está limitado por el `max-w-7xl` del marco.

### 4.3 La línea

| Parte | Componente y tokens | Texto |
|---|---|---|
| Contenedor | `li` con `rounded-xl bg-hoja px-4 angosto:px-2 py-3 ring-1 ring-linea`. **La línea no es un botón** | — |
| Nombre | `p` `text-lg font-bold break-words [overflow-wrap:anywhere]`, con `id` propio (lo usa el campo, 4.4) | `{nombre}` |
| Días, 2 o más | `p` `text-base text-tenue`, la cifra en `cifras` | «Alcanza para `{n}` días» [L 21] |
| Días, 1 | igual | «Alcanza para 1 día» [L 21] |
| Días, 0 | `p` `flex gap-1.5 text-base font-bold text-tinta`, con `CircleAlert` `size-5 text-atenta` `aria-hidden` delante | «Se acaba hoy» [L 21] |
| Días, negativo | igual que 0 | «Puede que ya no quede» [L 21] |
| Agregado a mano | En lugar de los días, `Etiqueta` neutra (`bg-tinta/7 text-tenue`) con `Pencil` `size-4` `aria-hidden` | «Solo en esta pantalla» **[PROPUESTO]**, sale de la nota aprobada «Esto queda solo en esta pantalla» [L 21] |
| Cantidad, editable | El `Stepper` de `Insumos.tsx` (campo de texto numérico con − y +), etiqueta «Cantidad» [L 21] y el sufijo de la unidad (4.5) | — |
| Cantidad, observador | `p` `text-lg tabular-nums`, sin etiqueta | El texto completo de 4.5, por ejemplo «6 envases de 20 unidades» |
| Quitar (solo agregados a mano) | `Boton variante="textoPeligro"`, `self-end` a 360 px, al final de la línea en ancho | «Quitar» **[PROPUESTO]**, `aria-label` «Quitar «`{nombre}`»» **[PROPUESTO]** |

**Orden dentro de la línea:** nombre, días, cantidad. La sección 21 da el contenido de la línea («{nombre} · {cantidad} · {días}»). Pongo los días bajo el nombre y la cantidad al final para que el campo quede junto al pulgar y no separe el nombre de sus días. El texto no cambia.

**El estado nunca solo por color:** 0 y negativo cambian la palabra y suman el ícono. El agregado a mano se distingue por la etiqueta con palabra e ícono, no por un fondo.

**Orden de las líneas:** primero las de la API, en el orden en que llegan (por fecha estimada, el que se acaba primero arriba). Después las agregadas a mano, en el orden en que se agregaron. El mismo orden en la pantalla, en la impresión y en el texto compartido.

### 4.4 El campo «Cantidad»

- **Componente:** el `Stepper` local de `Insumos.tsx` (o el mismo extraído a un lugar común), con `inputMode="numeric"`, `pattern="[0-9]*"`, `autoComplete="off"`, solo dígitos. Botones − y + `size-12` con `ring-turquesa/70`. Campo `min-h-12 w-24 text-xl cifras` con `ring-2 ring-inset ring-borde`, foco `ring-turquesa` y el foco base.
- **Valor inicial:** la cantidad sugerida que devuelve la API. Para los agregados a mano, 1.
- **Rango:** de 1 a 100.000, paso 1. Si la API sugiere más de 100.000, el máximo es lo sugerido.
- **Nombre accesible:** la etiqueta visible es «Cantidad», pero hay una por línea. El campo lleva `aria-labelledby` con el id de la etiqueta y el id del nombre de la línea, para que el lector diga «Cantidad, Pañal adulto talla M» (la etiqueta visible queda dentro del nombre, WCAG 2.5.3). Los botones: «Menos: Cantidad de `{nombre}`» y «Más: Cantidad de `{nombre}`» **[PROPUESTO, solo para el lector]**, con `INSUMOS.menos` y `INSUMOS.mas`.
- **Validación, al tocar cualquiera de los tres botones de salida** (que nunca están deshabilitados): un campo vacío, en 0 o sobre el máximo muestra bajo él, con `MensajeError` y `aria-invalid`, «Escribe una cantidad de 1 a 100.000.» **[PROPUESTO]**. El foco va al primer campo con error y **no se imprime, comparte ni copia nada**. El error se borra al corregir el campo.
- **Nada se guarda.** El valor vive en la memoria de la página (sección 11).

### 4.5 Cómo se escribe la cantidad

Es el mismo texto en el sufijo del campo, en la línea del observador, en la impresión y en el texto compartido. Una sola función lo arma (7.2).

| Caso | Sufijo del campo | Texto completo | Fuente |
|---|---|---|---|
| Con envase, `{n}` mayor que 1 | «envases de `{u}` unidades» | «`{n}` envases de `{u}` unidades» | [L 21] |
| Con envase, 1 | «envase de `{u}` unidades» | «1 envase de `{u}` unidades» | [L 21] |
| Con envase, en ml o g | «envases de `{u}` ml», «envases de `{u}` g» | «`{n}` envases de `{u}` ml» | [L 21] |
| Con envase, en sobres | «envases de `{u}` sobres» | «`{n}` envases de `{u}` sobres» | **[PROPUESTO]**, la sección 21 da unidades, ml y g |
| Sin envase | «unidades», «sobres», «ml», «g» | «`{n}` unidades», «`{n}` sobres», «`{n}` ml», «`{n}` g» | [L 21] |
| Sin envase, 1 | «unidad», «sobre» | «1 unidad», «1 sobre» | [L 21] |
| Agregado a mano | «unidades» (o «unidad» con 1) | «`{n}` unidades» | **[PROPUESTO]**: se cuenta por unidad (pregunta P2) |

**Cifras:** los números con punto de miles desde 1.000 («1.200 unidades»), como el dinero. En pantalla, la cifra en `tabular-nums`. El sufijo baja de renglón como texto (sin `cifras` en la frase completa).

### 4.6 Bajada y nota

| Dónde | Rol | Texto | Fuente |
|---|---|---|---|
| Bajada, bajo el título | admin, cuidador, pagador | Lo que se acaba pronto, con una cantidad sugerida para 30 días. Puedes cambiarla antes de imprimir o compartir. | [L 21] |
| Bajada | observador | Lo que se acaba pronto, con una cantidad sugerida para 30 días. | [L 21], solo la primera frase **[PROPUESTO]** |
| Nota, bajo las líneas | admin, cuidador | Es una sugerencia con lo que anotaste. Cambia la cantidad si necesitas otra. | [L 21] |
| Nota | pagador | Es una sugerencia con lo que anotó la familia. Cambia la cantidad si necesitas otra. | **[PROPUESTO]**, como la nota del pagador en [L 16]: el pagador no anota insumos |
| Nota | observador | Es una sugerencia con lo que anotó la familia. | **[PROPUESTO]**, igual |

Bajada con el `Pagina` o el `Titulo` de `ui.tsx`: `mt-1.5 max-w-prose text-base text-tenue`. Nota: `p` `max-w-prose text-base text-tenue`.

### 4.7 Agregar otro insumo

**Objetivo:** Carmen suma algo que MATU no sigue (unas toallitas que compra a veces) sin salir de la lista.

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
│ │ Cantidad                       │ │  Stepper, empieza en 1
│ │ [ − ] [  1  ] [ + ] unidades   │ │
│ │ Esto queda solo en esta        │ │  text-base text-tenue
│ │ pantalla. No lo guardamos.     │ │
│ │ [ Agregar ]   Cancelar         │ │  secundario · enlace de acción
│ └────────────────────────────────┘ │
```

- **Abrir:** el botón «Agregar otro insumo» se oculta mientras el panel está abierto (como «Ya lo resolví» en MATU-37) y el foco va al campo del nombre.
- **Agregar:** valida, agrega la línea al final, cierra el panel y devuelve el foco al botón «Agregar otro insumo», para agregar otro si hace falta. Se anuncia por la región `status`.
- **Cancelar o `Esc`:** cierra sin agregar y devuelve el foco al botón. Lo escrito se descarta.
- **«Agregar» es secundario**, no macizo: el único `turquesa` macizo de la pantalla es la acción de salida (sección 10).
- **Nombre:** una línea. Un salto de línea pegado se reemplaza por un espacio y se quitan los espacios de los extremos antes de agregar.
- **Quitar** (4.3) borra la línea al tocarlo, **sin confirmación**: está solo en memoria y se vuelve a agregar en segundos. El foco va a la línea siguiente (a su campo «Cantidad») o, si era la última, al botón «Agregar otro insumo». Se anuncia por `status`.
- **Sin límite** de líneas agregadas.

| Parte | Texto | Fuente |
|---|---|---|
| Botón que abre | Agregar otro insumo | [L 21] |
| Etiqueta del nombre | ¿Qué insumo es? | [L 18] |
| Ayuda del nombre | Por ejemplo: «Toallitas húmedas». Sin remedios ni para qué se usa. | [L 21] (con punto final al mostrarse, como en MATU-36) |
| Etiqueta de la cantidad | Cantidad | [L 21] |
| Nota | Esto queda solo en esta pantalla. No lo guardamos. | [L 21] |
| Botón que agrega | Agregar | **[PROPUESTO]** |
| Cancelar | Cancelar | [M36] |
| Nombre vacío | Escribe el nombre del insumo. | [L 18] |
| Nombre de más de 60 (si llega pegado) | El nombre admite hasta 60 caracteres. Acórtalo un poco. | [L 18] |
| Cantidad fuera de rango | Escribe una cantidad de 1 a 100.000. | **[PROPUESTO]** (4.4) |
| Anuncio al agregar | Agregamos «`{nombre}`» a la lista. | **[PROPUESTO]**, mismo verbo que el botón |
| Anuncio al quitar | Quitamos «`{nombre}`». | **[PROPUESTO]**, mismo verbo que el botón |

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
| observador | No hay insumos que se acaben pronto. | Ninguna. Baldosa `bg-tinta/7 text-tenue` | [L 21], solo la primera frase **[PROPUESTO]** |

- Sin aviso, sin nota y sin botones de salida mientras no haya líneas. Al agregar la primera a mano, el bloque vacío se reemplaza por la lista y aparecen el aviso y los botones.
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

### 7.2 El texto

Una sola función arma el texto, a partir de las líneas tal como están en la pantalla en ese momento (cantidades cambiadas y agregadas a mano incluidas). **La misma función alimenta la hoja de impresión**, para que el papel y el mensaje nunca digan cosas distintas.

```
Lista de insumos · 06/11/2026
- Pañal adulto talla M: 6 envases de 20 unidades
- Toallitas húmedas: 120 unidades
Piloto académico con datos de prueba
```

[L 21], exacto:
- Primera línea: «Lista de insumos · `{fecha}`», con la fecha de hoy en Chile en el momento de tocar el botón. El separador es espacio, punto medio (U+00B7) y espacio.
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
| No se pudo copiar, sin `navigator.share` | No pudimos copiar la lista. Usa «Imprimir o guardar en PDF». | **[PROPUESTO]**: sin hoja de compartir, el texto aprobado manda a un botón que no está |
| No se pudo compartir (un error que no es `AbortError`) | No pudimos abrir Compartir. Usa «Copiar la lista». | **[PROPUESTO]** |

### 7.5 Qué se anuncia y por dónde

Por las regiones vivas de `Anuncios.tsx`, nunca con un `role` puesto sobre un elemento que aparece ya con su texto.

| Qué | Región | Cómo |
|---|---|---|
| «Cargando los insumos…» | `status` en el lugar | El patrón de `Cargando` de Insumos |
| Lista copiada | `status` (`polite`) | `Nota rol="status"` |
| Línea agregada o quitada a mano | `status` (`polite`) | `anunciar(texto, 'status')` |
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
- La regla de la capa base (8.4) oculta `#raiz` completo al imprimir cuando existe esa hoja. Así **no puede colarse nada de la app**: ni el encabezado con el nombre de la persona, ni el selector de persona, ni el grupo, ni la navegación, ni el distintivo, ni los avisos, ni los botones, ni las regiones vivas.
- La hoja se arma con la misma función del texto compartido (7.2), así que trae lo que está en la pantalla en ese momento.

### 8.2 Cómo se ve en papel

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
- **La casilla:** un cuadrado vacío `size-4 rounded-sm border-2 border-tinta` `aria-hidden` delante de cada nombre, para tachar en el pasillo. Es la hoja del refrigerador, ahora en el bolsillo. No lleva texto.
- **El nombre** se parte por palabras si es largo (`break-words`). **La cantidad** va a la derecha (`text-right`) y también puede bajar de renglón.
- **El pie** «Piloto académico con datos de prueba» [L 21] va una vez, al final de la lista y en el flujo (no fijo en cada página, porque un pie fijo tapa líneas en algunos navegadores).
- **Sin los días, sin el nombre de la persona, sin el grupo y sin la marca MATU.** Solo el título, las líneas y el pie (decisión de Jorge).

### 8.3 Título del documento y momento de imprimir

- Al tocar «Imprimir o guardar en PDF»: se valida (4.4), se espera `document.fonts.ready`, se cambia `document.title` a «Lista de insumos» [L 21] y se llama a `window.print()`.
- También con los eventos `beforeprint` y `afterprint` de `window`, para que Ctrl+P y el menú del navegador hagan lo mismo: en `beforeprint`, «Lista de insumos». En `afterprint`, vuelve a «Lista de insumos · MATU». Los eventos se escuchan solo mientras la pantalla está montada.
- Así el PDF se llama «Lista de insumos.pdf», y la cabecera que algunos navegadores imprimen en el margen dice «Lista de insumos» y la dirección `/insumos/lista`, que no lleva ids ni nombres.
- Con Ctrl+P y una cantidad inválida no se puede detener la impresión: la hoja usa el último valor válido de esa línea, o la cantidad sugerida si nunca hubo uno.

### 8.4 La regla de la capa base (`web/src/index.css`, ver D5)

Hace dos cosas. Primero, **fuerza el tema claro al imprimir**: con el teléfono en tema oscuro, `tinta` sería `#E4EEEB` y el texto saldría casi blanco sobre el papel. Repite los valores claros que ya están en `@theme`, sin tokens nuevos, y va después de los dos bloques del tema oscuro para ganarles. Segundo, oculta la app cuando existe la hoja de impresión.

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

@layer base {
  @media print {
    body {
      background: none;
      min-height: 0;
    }
    /* Con la hoja de impresión de una pantalla (MATU-60), solo ella sale en el papel. */
    body:has(> [data-impresion]) > #raiz {
      display: none;
    }
  }
}
```

### 8.5 El observador y la impresión (D3)

El observador no tiene el botón, pero el navegador siempre deja imprimir. Para que lo impreso nunca tenga más que lo permitido, su hoja de impresión trae solo «Lista de insumos · `{fecha}`», «Quien administra, cuida o paga puede imprimirla o compartirla.» [L 21] y el pie. Ninguna línea. Lo confirma Jorge (D3).

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
- **Al guardar:** se envía solo si cambió (decisión 41). Vacío se envía como `null` (D2).

### 9.3 Validación

Al tocar «Guardar», con el resto del formulario. El foco va al primer campo con error, en el orden del formulario.

| Caso | Texto | Fuente |
|---|---|---|
| Vacío | Sin error: es opcional | — |
| 0 o más de 10.000 | Escribe un número de 1 a 10.000, o déjalo en blanco. | **[PROPUESTO]**, con el patrón de «Escribe un número entre 1 y 9999, o déjalo en blanco.» [L 17] |
| 422 de la API en ese campo | El mismo texto | **[PROPUESTO]** |

### 9.4 En el conflicto (412) de Insumos

Si la persona cambió este campo y otra persona guardó antes, los bloques «Lo que guardó» y «Lo tuyo, sin guardar» (MATU-36, 3.5) muestran el envase con «Cada envase trae `{u}` `{sufijo}`.» o «Sin unidades por envase.» **[PROPUESTO]**, con «(cambió)» y negrita si es distinto.

### 9.5 Lo que no cambia

La fila de Insumos no muestra el envase. La vista previa no lo usa. La confirmación sigue siendo «Guardamos «`{nombre}`». …» [M36].

---

## 10. Accesibilidad visual

### 10.1 Elementos en `turquesa` macizo

| Estado | Cantidad |
|---|---|
| Lista, admin, cuidador o pagador, con `navigator.share` | 1: «Compartir la lista» |
| Lista, sin `navigator.share` | 1: «Imprimir o guardar en PDF» |
| Lista, observador | 0 |
| Vacía | 0 («Agregar otro insumo» es secundario) |
| Panel «Agregar otro insumo» abierto | 1: la acción de salida («Agregar» es secundario) |
| Error al cargar | 1: «Volver a intentar» |
| Falta el permiso, hay que renovar, no encontrado | 0 |
| Insumos (`/insumos`), con las pestañas | Sin cambios: 1, «Anotar un insumo» |

La pestaña activa va en `text-turquesa` con borde inferior: texto y línea, no un bloque macizo.

### 10.2 Áreas táctiles de 48 × 48 px

Las pestañas (`min-h-12`), los botones − y + (`size-12`), cada campo «Cantidad» y el del envase (`min-h-12`), «Agregar otro insumo», «Agregar», «Cancelar», «Quitar» (`Boton` con `min-h-12`) y los tres botones de salida. Entre «Quitar» y el campo de la misma línea, al menos `gap-4`, para no tocarlo por error.

### 10.3 Contraste (valores de DISENO.md, sin colores nuevos)

| Elemento | Claro | Oscuro |
|---|---|---|
| Nombre y cantidad (`tinta` sobre `hoja`) | sobre 14:1 | sobre 13:1 |
| Días y bajada (`tenue` sobre `hoja` y `papel`) | 7,2:1 y 6,4:1 | 8,1:1 y 9,2:1 |
| Botón principal (`papel` sobre `turquesa`) | 6,0:1 | 9,4:1 |
| Botones secundarios y pestaña activa (`turquesa` sobre `hoja` y `papel`) | 6,7:1 y 6,0:1 | 8,2:1 y 9,4:1 |
| Anillo de los secundarios (`turquesa` al 70 %) | 3,5:1 | lo mido en la revisión |
| Borde de los campos (`borde`) | 3,5:1 sobre `hoja` | 4:1 sobre `hoja` |
| Aviso (`tinta` sobre `atenta-fondo`), ícono `atenta` | lo mido en la revisión (por cálculo, sobre 12:1 el texto) | igual |
| Error (`pronto`) | 6,1:1 sobre su fondo | lo mido en la revisión |
| Foco base (`turquesa`, 3 px, separación 2 px) | 6,0:1 sobre `papel` | 9,4:1 |

### 10.4 Foco y orden de tabulación

El orden del documento, sin `tabIndex` positivos:

1. Pestaña «Insumos», pestaña «Lista de insumos».
2. (El `h1` recibe el foco al llegar, pero no está en el orden de Tab.)
3. Por cada línea editable: −, campo «Cantidad», +, y «Quitar» si es a mano.
4. «Agregar otro insumo». Abierto: campo del nombre, −, «Cantidad», +, «Agregar», «Cancelar».
5. El botón principal, después los secundarios, en el orden de 4.9.

En ancho, la columna derecha va **después** de la izquierda en el DOM, así que el orden es el mismo que a 360 px. El foco nunca queda tapado por la barra de secciones del teléfono: el `scroll-padding-bottom` de la capa base y el `telefono:pb-36` del `main` ya lo cubren. El mensaje bajo los botones se desplaza a la vista con `scrollIntoView({ block: 'nearest' })`.

| Después de | El foco va a |
|---|---|
| Llegar a la ruta | El `h1` |
| Abrir «Agregar otro insumo» | El campo del nombre |
| Agregar, Cancelar o `Esc` | «Agregar otro insumo» |
| Quitar | El campo «Cantidad» de la línea siguiente, o «Agregar otro insumo» |
| Un error de validación | El primer campo con error |
| Copiar, compartir o imprimir | Se queda en el botón |
| 403 de admin o cuidador | El `h1` del permiso en `/insumos` |

### 10.5 Texto al 200% en 320 px (160 px efectivos)

- Sin desplazamiento horizontal: `scrollWidth <= innerWidth` en todos los estados.
- La app entra en modo `angosto`: rellenos `px-2`, el `Boton` oculta sus íconos, la `Nota` achica su separación.
- El `Stepper` envuelve: −, el campo y + pueden quedar en renglones distintos, y el sufijo «envases de 20 unidades» baja solo. Ningún elemento suelto mide más de 160 px (el campo mide 6 rem, 102 px).
- Los nombres se parten con `break-words [overflow-wrap:anywhere]` (un nombre de 60 caracteres sin espacios no desborda).
- Las pestañas envuelven (`flex-wrap`).
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
| Guardar las cantidades cambiadas, las líneas agregadas o el texto en `localStorage`, `sessionStorage`, IndexedDB, cookies o la caché del navegador | Viven solo en la memoria de la página (registro de tratamientos, CLAUDE.md agente 3). Se pierden al salir de la vista, al cambiar de persona o grupo y al salir de MATU |
| Poner la lista, un nombre, una cantidad o un id en la URL (consulta o fragmento) o en el `<title>` | CLAUDE.md, agente 3 |
| Enviar al servidor las cantidades cambiadas o las líneas agregadas a mano | «No lo guardamos» [L 21]. La lista se arma con lo que el grupo ya ve, y nada nuevo llega al servidor |
| Generar un PDF en el navegador (jsPDF, `Blob`, descargas) o en el servidor, o crear un enlace a la lista | ADR-031: solo `window.print()` |
| Pasar `title`, `url` o `files` a `navigator.share` | ADR-031: solo texto |
| Incluir los días, el nombre de la persona cuidada, el del grupo, un enlace o el nombre de quien comparte en el texto o en el papel | ADR-031, punto 4 |
| Imprimir la pantalla: el encabezado, el selector de persona, la navegación, los avisos o los botones | Decisión de Jorge. La hoja de impresión es lo único que sale (8.1) |
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

## 12. Componentes y estados

| Componente | Normal | Foco | Presionado | Cargando | Error | Vacío |
|---|---|---|---|---|---|---|
| `Pestanas` | `text-tenue`, borde transparente | foco base | — | — | — | — |
| Pestaña activa | `text-turquesa font-bold border-b-3 border-turquesa`, `aria-current="page"` | foco base | — | — | — | — |
| Línea | `bg-hoja ring-1 ring-linea rounded-xl` | — (no es interactiva) | — | — | — | sección 5 |
| Línea agregada a mano | igual, con la `Etiqueta` «Solo en esta pantalla» | — | — | — | — | — |
| `Stepper` «Cantidad» | campo `ring-borde`, botones `ring-turquesa/70` | foco base | `bg-rocio` en − y + | — | `ring-pronto` y `MensajeError` | — |
| Campo del envase | `ring-borde` | `ring-turquesa` y foco base | — | — | `ring-pronto` y `MensajeError` | vacío, sin texto de ejemplo |
| Panel de agregar | `bg-hoja ring-1 ring-linea rounded-xl` | foco al nombre | — | — | errores en sus campos | — |
| Aviso fijo | `Nota` `atenta` con borde e `Info` | — | — | — | — | no se muestra sin líneas |
| Botón principal | `turquesa` macizo, texto `papel` | foco base | `active:brightness-95` | — | — (el error va debajo) | — |
| Botones secundarios | `hoja` con anillo `turquesa/70` | foco base | `bg-rocio` | — | — | — |
| «Quitar» | `textoPeligro` | foco `pronto` (ya en el `Boton`) | subrayado pleno | — | — | — |
| Mensaje de copiado | `Nota` `ok` con `CircleCheck`, `aparecer` | — | — | — | — | — |
| Mensaje de error | `MensajeError` en `Anunciado` `alert` | — | — | — | — | — |
| Hoja de impresión | `hidden print:block`, `bg-hoja text-tinta` | — | — | — | — | solo título y pie (observador, 8.5) |

**Íconos (`lucide-react`, todos `aria-hidden`):** `Share2`, `Printer`, `Copy`, `Plus`, `Minus`, `Pencil`, `Info`, `CircleAlert`, `CircleCheck`, `ListChecks`, `CloudOff`, `Lock`, `Hourglass`.

---

## 13. Textos para `lenguaje.md`

Los aprobados vienen de la sección 21 (y de la 8, 17 y 18). Estos son los **[PROPUESTO]**, que no se usan hasta que Jorge los apruebe:

1. «Vistas de Insumos» (nombre de las pestañas para el lector)
2. «Lista de insumos · MATU» (`<title>`)
3. «Solo en esta pantalla» (etiqueta de una línea agregada a mano)
4. «Quitar», con «Quitar «`{nombre}`»» para el lector, y el anuncio «Quitamos «`{nombre}`».»
5. «Agregar» (botón del panel) y el anuncio «Agregamos «`{nombre}`» a la lista.»
6. «Menos: Cantidad de `{nombre}`» y «Más: Cantidad de `{nombre}`» (solo para el lector)
7. «Escribe una cantidad de 1 a 100.000.»
8. «`{n}` envases de `{u}` sobres» y la cantidad de un agregado a mano en unidades
9. «No pudimos copiar la lista. Usa «Imprimir o guardar en PDF».» (sin hoja de compartir)
10. «No pudimos abrir Compartir. Usa «Copiar la lista».»
11. Pagador: «Es una sugerencia con lo que anotó la familia. Cambia la cantidad si necesitas otra.» Observador: «Es una sugerencia con lo que anotó la familia.»
12. Observador: solo la primera frase de la bajada y del estado vacío
13. «Escribe un número de 1 a 10.000, o déjalo en blanco.» (campo del envase)
14. «Cada envase trae `{u}` `{sufijo}`.» y «Sin unidades por envase.» (conflicto de Insumos)

---

## 14. Cómo la voy a revisar

No apruebo una pantalla que no vi funcionando. El frontend deja la pantalla levantable en local contra el doble del contrato, con:

- una lista con tres insumos (6, 1 y 0 días), uno con −2 días, uno con envase («6 envases de 20 unidades»), uno sin envase en sobres, uno en ml con envase, uno con un nombre de 60 caracteres sin espacios y uno con 1 envase
- la lista vacía
- 403 `sin-consentimiento` con rol `cuidador` y con rol `observador`, 403 `revision-vencida`, un 404 y un 500
- los cuatro roles
- el navegador con y sin `navigator.share`, y `navigator.clipboard.writeText` que falla
- el formulario de Insumos con el campo nuevo, al anotar y al cambiar, con 0, con 10.001 y con un 412 que lo incluye.

**Capturas:** cada estado a 360 × 740, 1280 × 720 y 1920 × 1080, en claro y oscuro, a 320 px con el texto al 200%, y con `prefers-reduced-motion`. **La impresión:** la vista previa de impresión de Chrome y el PDF guardado, con el teléfono en tema oscuro, en A4 y carta, en blanco y negro, con una lista que ocupe dos páginas.

**En cada una mido:** `scrollWidth <= innerWidth`, el alto de lo que se toca, el contraste del texto y de los bordes, el foco visible con Tab (también al abrir y cerrar el panel y al quitar una línea), la tabla de `turquesa` macizo (10.1), que ningún texto quede bajo 17 px, y que lo copiado, lo compartido y lo impreso digan exactamente lo mismo, sin días y sin el nombre de la persona.

---

## 15. Resumen

**Decisiones de diseño que tomé:**

1. **El acceso son pestañas** «Insumos» y «Lista de insumos» antes del título, como Compartir y Enlaces. No un botón dentro de «Se acaban pronto», porque el aviso nunca ofrece comprar y porque el bloque desaparece sin alertas.
2. **El botón principal depende del teléfono:** «Compartir la lista» si hay hoja de compartir, «Imprimir o guardar en PDF» si no. «Copiar la lista» siempre, secundario. Es la regla de MATU-48.
3. **El aviso fijo es una `Nota` `atenta` con `Info`**, justo sobre los botones, y describe al botón principal para el lector de pantalla.
4. **La línea muestra nombre, días y cantidad**, con el campo al final, junto al pulgar. «Cantidad» es el `Stepper` editable de Insumos.
5. **Agregar a mano es un panel que se abre en el lugar**, con «Agregar» secundario y «Quitar» sin confirmación. Las líneas agregadas llevan «Solo en esta pantalla» y se cuentan en unidades.
6. **La impresión es una hoja aparte**, montada fuera de `#raiz`, que la capa base deja como lo único que sale en el papel. Va siempre en tema claro, en Atkinson, solo en `tinta`, con una casilla vacía para tachar, y comparte la función que arma el texto. Así el papel y el mensaje no pueden diferir.
7. **El campo del envase va al final del formulario**, sin − ni +, con el valor guardado al cambiar.

**Preguntas abiertas para Jorge:**

1. **D3:** ¿Te parece que, si un observador imprime con el menú del navegador, el papel salga solo con el título, «Quien administra, cuida o paga puede imprimirla o compartirla.» y el pie?
2. **P2:** ¿Lo agregado a mano se cuenta siempre en unidades, o prefieres que se pueda elegir «sobre»?
3. ¿Se puede sacar de la lista un insumo que viene de MATU y que no se quiere conseguir esta vez? Hoy la especificación no lo permite (la cantidad mínima es 1).
4. La casilla vacía para tachar en el papel: ¿la dejamos?
5. Los 14 textos **[PROPUESTO]** de la sección 13.

**Para el orquestador:** D1 y D2 (contrato de la lista y `null` en el envase), D4 (las otras pantallas se imprimen tal como se ven, también la ficha) y D5 (quién aplica la regla de impresión en `web/src/index.css`).

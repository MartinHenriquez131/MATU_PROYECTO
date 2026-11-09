# MATU-59 · Catálogo curado · Especificación de diseño

**Versión 1.1 · 08/11/2026** · agente 6 (UI/UX) · para el frontend
**Cambios de la 1.1 (revisión visual del 08-11, APROBADA):** en 4.7, las filas de la tarjeta en ancho (`@3xl/producto:grid-rows-[auto_1fr]`), que el frontend agregó y la revisión confirmó; y en 9.1, los tres P3 aceptados.
**Historia:** MATU-59, el catálogo curado (RF-20, capa 3). La familia mira los productos que usan las familias que cuidan, ordenados por categoría, con el precio de cada comercio y si lo tiene. **No se pide nada desde esta pantalla** (D4: el botón «Pedir» llega con MATU-61).
**Dónde se construye:** `web/`, en la app de la familia, React 19, TypeScript y Tailwind CSS v4, mobile first.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` · la revisión previa del analista y las decisiones D1 a D6 de Jorge del 08-11, con los textos aprobados el 08-11 (van a `lenguaje.md`, sección 27 «Catálogo (MATU-59)») · `lenguaje.md` secciones 3, 11 (primera mención de un comercio) y 26 (`Cargando…`, `Volver a intentar`) · `docs/modelo-datos.md` 4.4 (`categoria_cuidado`, `producto`, `oferta`) · las especificaciones `matu-36-insumos.md` y `matu-60-lista-insumos.md` de esta carpeta · el código actual de `web/src/familia/Shell.tsx`, `ui.tsx`, `ruteo.ts` e `Insumos.tsx`.

**Cómo se lee:** los textos entre comillas latinas «» van tal cual. **[L 27]** es un texto aprobado por Jorge el 08-11 para la sección 27. **[L 26]**, **[L 21]**, **[M36]** son de esas secciones o especificaciones. Las llaves son datos de la API: `{nombre}` del producto o del comercio, según la fila.

**Tokens:** ningún token nuevo, ningún color nuevo y ninguna regla nueva en la capa base. **No hay ningún `turquesa` macizo en el estado normal de la pantalla:** no hay acción principal (D4). El único botón macizo posible es «Volver a intentar», en el error.

**La demo del viernes 30 no tiene un catálogo dibujado.** Su escena 19 (Lista de reposición, `Demo/ESPEC-ADR-027.md` 2) muestra precios de un solo comercio dentro de la lista, con «Pedir a domicilio». De ella se reutiliza el rótulo `PreciosDeEjemplo` (DISENO.md, «Rótulos del piloto») y la regla de «(comercio ficticio)». No se reutiliza la composición: aquí no hay lista, ni cantidades, ni total, ni pedido.

---

## 0. Puntos abiertos

| # | Qué | Para quién | Opción por defecto (la que usa esta especificación) |
|---|---|---|---|
| N1 | **Dónde entra el catálogo en la navegación.** Como quinta sección de la barra no cabe en el teléfono (sección 2.1, medido): «Compartir» en negrita mide 70 px y la celda deja 58 px a 360 px y 50 px a 320 px. Sin cambiar un texto aprobado, no hay forma de que quepan cinco | Jorge | **Una tercera pestaña de Insumos**, «Catálogo», en `/insumos/catalogo`. La alternativa B (quinta sección) exige que Jorge apruebe un rótulo corto para Compartir de 6 letras o menos en la barra del teléfono, y se vuelve a medir |
| N2 | **«(comercio ficticio)», ¿una vez por pantalla o una vez por producto?** `lenguaje.md` 11 dice «primera mención en una pantalla». En una lista que se recorre por encabezados (lector de pantalla, o Carmen que baja directo a «Alimentación»), la primera mención queda en otra tarjeta, fuera de la vista | Jorge | **Una vez por tarjeta de producto**, en el nombre del comercio (4.3). Las líneas de stock de esa tarjeta llevan el nombre solo |
| N3 | **`nombre` y `presentacion` del producto no deben repetirse.** D3 llama «presentaciones» a textos que ya llevan el nombre («Pañal adulto M x30»). Si la semilla pone el mismo texto en los dos campos, la tarjeta dice dos veces lo mismo | Orquestador → backend | La tarjeta muestra los dos campos (4.2). Recomiendo en la semilla `nombre` = el texto de D3 («Pañal adulto M x30») y `presentacion` = cómo viene («Paquete de 30 unidades»). Si `presentacion` es igual a `nombre`, la tarjeta no la muestra |
| N4 | **Lo que la pantalla necesita de la API** (para el contrato que se escribe en paralelo) | Orquestador → backend | Ver 3.1. Tres pedidos concretos: las ofertas de cada producto en un orden neutro (por `nombre_fantasia`, nunca por precio), un producto sin ninguna oferta no viene en la respuesta, y una categoría sin productos tampoco |

**Choques entre los textos aprobados y una regla de accesibilidad:** ninguno que obligue a cambiar un texto. Los que aparecieron se resuelven con la composición:
- **El retracto con letra mayor o igual que el precio** (D2) se cumple con los dos en `text-lg` (1,125 rem, 19 px), así que se mantiene igual con el texto al 200 %. Para que el retracto no compita con el precio en cada tarjeta, el precio va en negrita y el retracto no (salvo «Derecho a retracto:»). El tamaño es el mismo; el peso no lo exige D2.
- **La pestaña nueva hace que las pestañas de Insumos pasen a dos renglones a 360 px** (2.1, medido). No es un choque con un texto, pero se ve: por eso N1.
- **No hay texto de carga aprobado para el catálogo.** Uso «Cargando…» [L 26], que ya existe, en vez de proponer uno nuevo.

---

## 1. Para quién y qué

**Carmen** ve en Insumos que los pañales se acaban en 6 días y quiere saber cuánto cuestan y dónde hay, sin comprometerse a nada. Abre el catálogo con una mano, baja a «Higiene y cuidado personal» y lee el precio de cada comercio.

**Rodrigo**, sea pagador u observador, ve lo mismo. El catálogo es igual para los cuatro roles: no depende del grupo ni de la persona cuidada.

**Lo que esta pantalla nunca hace:**
- Ofrecer pedir, agregar a un carro, guardar un favorito o «avisarme cuando haya» (D4).
- Cruzarse con lo que la familia anotó: nada de «ya usas», «en tu lista», «se te acaba» ni un orden distinto según Insumos (revisión del analista, punto 3). Tampoco al revés: **Insumos y la Lista de insumos no enlazan a un producto del catálogo.**
- Mostrar una marca real, una foto de envase, el RUT, la razón social, la dirección o el teléfono del comercio (D5 y analista 3).
- Decir «Desde $X» (D6) o recomendar el más barato.
- Poner filtros o una búsqueda: con seis productos en tres categorías no hacen falta, y así no hay texto libre que pueda ir a la URL o a un log (analista 3).

---

## 2. Navegación

### 2.1 Por qué no es una quinta sección (N1)

Medido con las métricas de Atkinson Hyperlegible (`@fontsource`, el archivo que usa la app), a `text-sm` (14,875 px), que es el rótulo de la barra del teléfono:

| Rótulo | Normal | Negrita (la activa) |
|---|---|---|
| Compartir | 65,8 px | 70,2 px |
| Catálogo | 58,5 px | 62,7 px |
| Insumos | 57,0 px | 61,4 px |

Celda útil de la barra (`Shell.tsx`: `px-1` en la barra, `gap-1` y `px-1` en cada enlace):

| Ancho | 4 columnas (hoy) | 5 columnas |
|---|---|---|
| 360 px | 76 px: todo cabe | 58 px: no caben «Compartir», «Catálogo» ni «Insumos» en negrita |
| 320 px | 66 px: cabe | 50 px: no cabe ninguno de los tres |

Con cinco, quien ve cinco secciones es justamente Carmen (`admin` o `cuidador`: Ficha, Insumos, Compartir, Catálogo y Grupo). La regla de la capa base (`overflow-wrap: break-word`) partiría «Compartir» en dos sin guion. Quitar el relleno no alcanza a 320 px, y `text-xs` no se usa (DISENO.md 2).

### 2.2 La opción por defecto: una pestaña de Insumos

- **Ruta:** `/insumos/catalogo`, sin ids ni nombres. Se agrega a `Ruta` y `RUTAS` de `ruteo.ts`. `seccionDe` ya la reconoce por el prefijo `/insumos`: la sección activa de la barra es Insumos.
- **Pestañas** con el componente `Pestanas` de `ui.tsx`, en el `antes` de la página, igual que la Lista de insumos (MATU-60, 2.1). `aria-label` del `nav`: «Vistas de Insumos» [L 21].

  | Pestaña | Ruta | Texto |
  |---|---|---|
  | 1 | `/insumos` | «Insumos» [M36] |
  | 2 | `/insumos/lista` | «Lista de insumos» [L 21] |
  | 3 | `/insumos/catalogo` | «Catálogo» [L 27] |

  Catálogo va **al final**: es la capa 3, y quitarla deja las dos pestañas de antes como estaban.

- **Dónde se ven las pestañas.** Lo de MATU-60 2.1 se mantiene, con dos cambios:
  1. En `/insumos/catalogo` se ven **en todos sus estados**.
  2. En `/insumos`, en los tres estados sin pestañas de hoy (el permiso de Insumos para `admin` o `cuidador`, «Falta el permiso» y «Hay que renovar»), **ahora se ven, solo con «Insumos» y «Catálogo»**. El catálogo no depende de la autorización de los insumos (no lleva persona ni grupo), y sin esto Carmen no llegaría a él hasta dar el permiso. «Lista de insumos» no se muestra en esos estados porque llevaría de vuelta a la misma pantalla (MATU-60, 6.2).
  - Siguen sin pestañas `/insumos/nuevo` y `/insumos/cambiar` a 360 px (son un momento, no una vista).
- **Las pestañas en dos renglones.** Medido a `text-base` en negrita con `px-3`: «Insumos» 96 px, «Lista de insumos» 163 px y «Catálogo» 97 px, más los espacios: 365 px. A 360 px el ancho útil es 328 px, así que **«Catálogo» baja a un segundo renglón**, alineado a la izquierda, con el borde inferior común de `Pestanas` debajo de los dos. Pasa también a 320 px y con el texto al 200 %. El componente ya lo resuelve (`flex-wrap`, el borde de 3 px va en cada pestaña): no se cambia. Desde unos 400 px de contenido van en una fila.
- **Roles:** las cuatro ven la pestaña. El relevo no ve la app de la familia, así que no la ve (analista 3).
- **Cambiar de persona** (el selector del encabezado) estando en `/insumos/catalogo` **deja la ruta en `/insumos/catalogo`**: el catálogo no cambia con la persona. Hoy `Persona.cambiar` en `Shell.tsx` lleva a `/insumos`; necesita ese caso.
- **Título y foco:** `h1` con `Titulo` y la clase de Insumos, `text-3xl @2xl/main:text-5xl`. Al llegar, el foco va al `h1`. `<title>`: «Catálogo · MATU», con la convención de `tituloDe` en `AppFamilia.tsx`.

### 2.3 La alternativa B, si Jorge la elige

Quinta entrada de la barra, después de Compartir y antes de Grupo familiar, con el ícono `Store` de lucide y la ruta `/catalogo`. Necesita un rótulo corto para Compartir (o para Catálogo) aprobado por Jorge que mida 50 px o menos en negrita a `text-sm`, y que yo lo mida antes de construir. Todo lo demás de esta especificación (secciones 3 a 8) vale igual en las dos opciones: solo cambian las pestañas (no habría) y la ruta.

---

## 3. Datos y estados

### 3.1 Lo que la pantalla usa de la API (N4)

Es lo mínimo que la pantalla muestra. El contrato lo escribe el backend; si un campo cambia de nombre, se cambia aquí sin tocar el diseño.

| Dato | Dónde se usa |
|---|---|
| Categoría: `id`, `nombre`, en su `orden` | El `h2` de cada grupo (4.1). El `id` es la `key`, nunca va a la URL |
| Producto: `id`, `nombre`, `presentacion` | El `h3` y la línea de abajo (4.2) |
| Producto: `retracto_pierde_al_abrir` (D2) | Cuál de los dos textos de retracto (4.4) |
| Oferta: `nombre_fantasia` del comercio, `precio` (pesos enteros con IVA), `disponible` | Cada fila de comercio (4.3) |

**Lo que la pantalla no usa y no debe recibir:** `razon_social`, `rut`, `direccion`, `telefono` y `comuna` del comercio (analista 3), y `marca` (D5: es null o «Marca de ejemplo», y mostrarla no informa nada).

**Orden:** categorías por `orden`. Productos y ofertas en el orden en que llegan. Pido al backend que las ofertas lleguen por `nombre_fantasia`: ordenarlas por precio pone primero al más barato, y eso es una recomendación que la pantalla no hace (D6).

**Lo que la pantalla esconde, por si llega:** una categoría sin productos, y un producto sin ninguna oferta (sin oferta no hay precio, y el precio sale siempre de una oferta real: analista 1a).

### 3.2 Estados

```
abre /insumos/catalogo ─► GET del catálogo (una vez al llegar, y otra cada vez que se vuelve a entrar)
                         ├─ 200 con productos ─► catálogo (4)
                         ├─ 200 sin productos ─► vacío (5.2)
                         ├─ 401 ─► lo que ya hace la app (renovar la entrada una vez y, si falla, Entrar)
                         └─ red o 5xx ─► error al cargar (5.3)
```

- **Cargando (5.1).** El texto elige solo por `type` del error, nunca por `title`, `detail` ni `status` (lenguaje 8).
- **Sin interfaz optimista ni caché en el navegador:** nada del catálogo en `localStorage` ni `sessionStorage`. No es un dato sensible, pero un precio viejo guardado sería un precio falso.
- **No se consulta el stock en vivo** al abrir: la pantalla muestra lo que trae la respuesta (analista 4.6). No hay botón de «Actualizar».

---

## 4. El catálogo

**Objetivo:** Carmen encuentra un producto en su categoría y ve, para cada comercio, cuánto cuesta y si lo tiene, sabiendo que el precio es de ejemplo y qué derecho tiene si lo compra.

**Jerarquía:**
1. El **nombre del producto** y, en cada comercio, el **precio**.
2. Si **hay** en cada comercio, y el **retracto** del producto (con letra igual al precio).
3. El aviso del piloto, las notas de stock y envío, «Precio de ejemplo» e «IVA incluido».

El aviso del piloto va arriba porque se lee una vez antes de mirar precios, pero no compite: no es macizo y se reconoce como rótulo.

### 4.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ (encabezado de la app)             │
├────────────────────────────────────┤
│ Insumos   Lista de insumos         │  Pestanas, 48 px. A 360 px, dos renglones
│ Catálogo                           │  la activa: borde inferior de 3 px, negrita, aria-current
│ ━━━━━━━━ ───────────────────────── │
│ Catálogo                           │  h1 titular text-3xl
│ Productos que usan las familias    │  bajada text-base text-tenue max-w-prose
│ que cuidan. Mirar no te compromete │
│ a nada.                            │
│ ┃(i) Precios de ejemplo.           │  Nota tono atenta borde, icono Info. Una vez
│ ┃ MATU todavía no tiene convenio   │
│ ┃ con comercios, y en esta demo no │
│ ┃ se cobra dinero real.            │
│ Lo que hay se confirma antes de    │  p text-base text-tenue
│ pagar.                             │
│ El envío se suma al pedido, una    │  p text-base text-tenue
│ sola vez por pedido.               │
│                                    │
│ Higiene y cuidado personal         │  h2 titular text-2xl, mt-10
│ ┌────────────────────────────────┐ │  li: rounded-xl bg-hoja ring-1 ring-linea px-4 py-4
│ │ Pañal adulto M x30             │ │  h3 text-xl font-bold
│ │ Paquete de 30 unidades         │ │  p text-base text-tenue
│ │ ────────────────────────────── │ │  border-t border-linea pt-3
│ │ Almacén El Ejemplo (comercio   │ │  p font-bold
│ │ ficticio)                      │ │
│ │ $12.990  Precio de ejemplo     │ │  cifra text-lg font-bold · marca text-base text-tenue
│ │ IVA incluido                   │ │  text-base text-tenue
│ │ (✓) Hay en Almacén El Ejemplo  │ │  CircleCheck text-ok + texto text-tinta
│ │ ────────────────────────────── │ │
│ │ Comercio de Muestra (comercio  │ │
│ │ ficticio)                      │ │
│ │ $13.490  Precio de ejemplo     │ │
│ │ IVA incluido                   │ │
│ │ (–) No hay en Comercio de      │ │  CircleMinus text-tenue + texto text-tenue
│ │     Muestra por ahora          │ │
│ │ ────────────────────────────── │ │
│ │ Derecho a retracto: tienes 10  │ │  p text-lg, «Derecho a retracto:» en negrita
│ │ días desde que lo recibes. No  │ │
│ │ aplica si abres el sello del   │ │
│ │ producto.                      │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │  ul flex-col gap-4
│ │ Toallitas húmedas x80          │ │
│ │ …                              │ │
│ └────────────────────────────────┘ │
│                                    │
│ Cuidado de la piel                 │  h2
│ ┌────────────────────────────────┐ │
│ │ Crema protectora de la piel    │ │
│ │ 100 g                          │ │
│ │ …                              │ │
│ └────────────────────────────────┘ │
│                                    │
│ Alimentación                       │  h2
│ ┌────────────────────────────────┐ │
│ │ Suplemento nutricional en      │ │
│ │ polvo 400 g                    │ │
│ │ (– Por ahora no está           │ │  Etiqueta neutra con CircleMinus (4.5)
│ │    disponible)                 │ │
│ │ ──── (filas con «No hay…») ─── │ │
│ │ Derecho a retracto: tienes 10  │ │  sin la frase del sello (retracto_pierde_al_abrir = false)
│ │ días desde que lo recibes.     │ │
│ └────────────────────────────────┘ │
└────────────────────────────────────┘
  (barra de secciones fija abajo: el main ya trae telefono:pb-36)
```

Los nombres de comercio del esquema son de ejemplo (D5): los que van en pantalla son los `nombre_fantasia` de la semilla.

### 4.2 La tarjeta del producto

| Parte | Componente y tokens | Texto |
|---|---|---|
| Lista de la categoría | `section` con `aria-labelledby` al `h2`. Dentro, `ul` `flex flex-col gap-4 max-w-6xl` | — |
| Encabezado de categoría | `h2` `titular text-2xl` (25,5 px), `mt-10` (la primera, `mt-8`), `mb-4` | `{nombre}` de la categoría: «Higiene y cuidado personal», «Cuidado de la piel», «Alimentación» [L 27] |
| Contenedor | `li` `@container/producto rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea`. **No es un botón ni un enlace**: no recibe foco ni cambia al pasar el puntero | — |
| Nombre | `h3` `text-xl font-bold break-words` | `{nombre}` del producto |
| Presentación | `p` `mt-0.5 text-base text-tenue`. No va si es igual al nombre (N3) | `{presentacion}` |
| Sin stock en ningún comercio | `Etiqueta tono="neutro"` (`bg-tinta/7 text-tenue`) con `CircleMinus` `size-4` `aria-hidden`, `mt-2`, bajo la presentación (4.5) | «Por ahora no está disponible» [L 27] |
| Comercios | `ul` `mt-3 @container/oferta grid grid-cols-1 gap-y-3` (4.3) | — |
| Retracto | `p` `mt-4 border-t border-linea pt-3 text-lg max-w-prose` (4.4) | Uno de los dos textos [L 27] |

Sin imagen. Sin marca. Sin cifra de unidades por envase aparte de lo que diga la presentación.

### 4.3 La fila de cada comercio

```
│ Almacén El Ejemplo (comercio ficticio)    │  p font-bold text-base
│ $12.990  Precio de ejemplo                │  flex flex-wrap items-baseline gap-x-2
│ IVA incluido                              │  p text-base text-tenue
│ (✓) Hay en Almacén El Ejemplo             │  p flex gap-1.5 text-base
```

| Parte | Componente y tokens | Texto |
|---|---|---|
| Fila | `li` `border-t border-linea pt-3` | — |
| Comercio | `p` `font-bold text-base break-words` | «`{nombre}` (comercio ficticio)» [L 27], en todas las filas de cada tarjeta (N2) |
| Precio | `p` `flex flex-wrap items-baseline gap-x-2 gap-y-0.5`. La cifra en `span` `cifras text-lg font-bold text-tinta`, formato `$12.990` (pesos enteros, punto de miles, sin decimales). **Nunca en `turquesa`**: un precio no es una acción | `{precio}` |
| Junto al precio | `span` `text-base text-tenue`, en el mismo renglón que la cifra; baja si no cabe | «Precio de ejemplo» [L 27] |
| Bajo el precio | `p` `text-base text-tenue` | «IVA incluido» [L 27] |
| Hay | `p` `mt-1 flex gap-1.5 text-base text-tinta`, con `CircleCheck` `mt-0.5 size-5 shrink-0 text-ok` `aria-hidden` delante | «Hay en `{nombre}`» [L 27] |
| No hay | `p` `mt-1 flex gap-1.5 text-base text-tenue`, con `CircleMinus` `mt-0.5 size-5 shrink-0 text-tenue` `aria-hidden` delante | «No hay en `{nombre}` por ahora» [L 27] |

- **El estado nunca solo por color:** «Hay» y «No hay» son frases distintas, con íconos de forma distinta (círculo con check y círculo con guion). El color (`ok` o `tenue`) refuerza. Un comercio que no tiene el producto **muestra igual su precio**, sin tachar: tachado se lee como descuento.
- **La fila no se resalta** según haya o no, ni se reordena: el orden es el de la API (3.1).
- **Medidas a 360 px:** el contenido de la tarjeta mide 294 px. «$27.030» en negrita a 19 px mide unos 74 px y «Precio de ejemplo» a 17 px, 136 px: van en un renglón. «Almacén El Ejemplo (comercio ficticio)» en negrita mide 308 px: baja a dos renglones como texto, sin cortar palabras.
- **Lector de pantalla:** lee en el orden visual, «Almacén El Ejemplo (comercio ficticio), $12.990, Precio de ejemplo, IVA incluido, Hay en Almacén El Ejemplo». No hace falta `aria-label` en la fila ni en la lista.

### 4.4 El retracto

| `retracto_pierde_al_abrir` | Texto [L 27] |
|---|---|
| `true` (pañales, toallitas, protectores, crema) | Derecho a retracto: tienes 10 días desde que lo recibes. No aplica si abres el sello del producto. |
| `false` (suplemento, bolsas colectoras) | Derecho a retracto: tienes 10 días desde que lo recibes. |

- **Tamaño:** `text-lg` (19 px), **el mismo del precio** (D2: mayor o igual). Nunca `text-sm` ni `text-base`. «Derecho a retracto:» en `font-bold`; el resto en peso normal, `text-tinta` (no `tenue`: es un derecho, no una ayuda).
- **Uno por producto**, no uno por comercio: el derecho es el mismo en los dos. Va en la tarjeta del producto, no en un pie común, para que se lea junto al precio de ese producto (analista: el texto depende del producto).
- **Siempre visible:** nunca dentro de un `details`, un tooltip ni un «Ver más».
- Sin ícono y sin fondo: no es una advertencia sobre la demo (eso es el aviso del piloto) ni un estado.
- La pantalla elige el texto **solo por el campo**, nunca por la categoría (D2).

### 4.5 Un producto sin stock en ningún comercio

- Bajo la presentación, la `Etiqueta` neutra «Por ahora no está disponible» con `CircleMinus` (4.2). Palabra y forma, sin rojo: no es un error ni urgente.
- Las filas de comercio siguen con su precio y su «No hay en `{nombre}` por ahora».
- El retracto se mantiene: describe el producto, y el precio sigue a la vista.
- La tarjeta queda en su lugar y con la misma superficie. **No se atenúa con opacidad**: bajaría el contraste del texto bajo 4,5:1.

### 4.6 El aviso del piloto y las notas

| Dónde | Componente y tokens | Texto |
|---|---|---|
| Aviso, una vez, bajo la bajada | `Nota tono="atenta" borde` con `titulo` e `icono` `Info` (`mt-0.5 size-5 shrink-0 text-atenta`, `aria-hidden`), `iconoEnLinea`, `mt-1`. **Sin `rol`**: está desde que carga y se lee en el orden del documento. Es el `PreciosDeEjemplo` de DISENO.md | Título: «Precios de ejemplo.» Texto: «MATU todavía no tiene convenio con comercios, y en esta demo no se cobra dinero real.» [L 27] |
| Nota de stock, bajo el aviso | `p` `mt-4 max-w-prose text-base text-tenue` | «Lo que hay se confirma antes de pagar.» [L 27] |
| Nota del envío, bajo la de stock | `p` `mt-1 max-w-prose text-base text-tenue` | «El envío se suma al pedido, una sola vez por pedido.» [L 27] |

- **Una sola vez por pantalla**, arriba, antes de la primera categoría. No se repiten por tarjeta ni por categoría. Nunca se cierran.
- **Por qué arriba y no al pie** (en la demo iba al pie de la lista): aquí no hay botón principal con el que pueda competir, y la lista es larga; al pie, Carmen ya leyó todos los precios antes de saber que son de ejemplo.
- Sin cifra de envío (analista 1a).

### 4.7 Esquema en pantalla ancha (1280 y 1920 px)

```
┌───────────────┬───────────────────────────────────────────────────────────────────────────┐
│ (M) MATU      │ Cuidas a María Soto                                Tu cuenta   Salir      │
│               ├───────────────────────────────────────────────────────────────────────────┤
│ Ficha de relevo│ Insumos   Lista de insumos   Catálogo                                    │
│ Insumos  ◄    │ ──────────────────────────── ━━━━━━━━                                     │
│ Compartir     │ Catálogo                                                                  │
│ Grupo familiar│ Productos que usan las familias que cuidan. Mirar no te compromete a nada.│
│               │ ┃(i) Precios de ejemplo. MATU todavía no tiene convenio con comercios, y │
│               │ ┃    en esta demo no se cobra dinero real.                                │
│               │ Lo que hay se confirma antes de pagar.                                    │
│               │ El envío se suma al pedido, una sola vez por pedido.                      │
│               │                                                                           │
│               │ Higiene y cuidado personal                                                │
│               │ ┌───────────────────────────────────────────────────────────────────────┐ │
│               │ │ Pañal adulto M x30       │ ─────────────────────  ─────────────────────│ │
│               │ │ Paquete de 30 unidades   │ Almacén El Ejemplo     Comercio de Muestra  │ │
│               │ │                          │ (comercio ficticio)    (comercio ficticio)  │ │
│               │ │ ──────────────────────── │ $12.990 Precio de      $13.490 Precio de    │ │
│               │ │ Derecho a retracto:      │ ejemplo                ejemplo              │ │
│               │ │ tienes 10 días desde que │ IVA incluido           IVA incluido         │ │
│               │ │ lo recibes. No aplica si │ (✓) Hay en Almacén El  (–) No hay en        │ │
│               │ │ abres el sello del       │ Ejemplo                Comercio de Muestra  │ │
│               │ │ producto.                │                        por ahora            │ │
│               │ └───────────────────────────────────────────────────────────────────────┘ │
│               │ ┌ Toallitas húmedas x80 … ──────────────────────────────────────────────┐ │
└───────────────┴───────────────────────────────────────────────────────────────────────────┘
```

- **La tarjeta en dos columnas desde 48 rem de tarjeta** (`@3xl/producto`, se decide por el ancho de la tarjeta, no del `main`, como aprendimos en MATU-60 4.2): `grid grid-cols-1 @3xl/producto:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] gap-x-8`. A la izquierda el producto (nombre, presentación, etiqueta y retracto); a la derecha los comercios. Es la regla de DISENO.md 3: a la izquierda qué es, a la derecha dónde y cuánto.
- **El orden del DOM no cambia:** nombre y presentación, comercios, retracto. En ancho, el retracto se ubica con `@3xl/producto:col-start-1 @3xl/producto:row-start-2` y los comercios con `@3xl/producto:col-start-2 @3xl/producto:row-start-1 @3xl/producto:row-span-2 @3xl/producto:mt-0`. El retracto pierde el `mt-4` y queda con `@3xl/producto:mt-3`. El lector y el Tab siguen el mismo orden que a 360 px.
- **Las filas en ancho: `@3xl/producto:grid-rows-[auto_1fr]`** (v1.1). Los comercios ocupan las dos filas y casi siempre son más altos que el producto. Con dos filas `auto`, el alto que sobra se reparte entre las dos y el retracto se separa del nombre. Con `auto_1fr`, la fila 1 mide justo el nombre, la presentación y la etiqueta, y la fila 2 se lleva el resto, así que el retracto queda pegado bajo el nombre (`mt-3`). Si la izquierda es más alta, `1fr` crece con su contenido y no recorta nada. Medido a 1280 px en Pañal: fila 1 de 57 px, fila 2 de 145,5 px, y el retracto a 12,75 px del nombre.
- **Los comercios lado a lado desde 28 rem de columna** (`@md/oferta:grid-cols-2 gap-x-6`). Cada fila conserva su `border-t`: en dos columnas se leen como dos columnas bajo una línea.
- **Medidas a 1280 px:** el contenido mide unos 906 px (1280 menos la barra lateral de 16,5 rem y el `px-11` del `main`) y la tarjeta por dentro, 872 px. Pasa los 816 px de `@3xl`: dos columnas, la izquierda de unos 280 px y la derecha de unos 560 px. La derecha pasa los 476 px de `@md`: dos comercios de unos 267 px cada uno. «$12.990» más «Precio de ejemplo» miden 206 px: caben en un renglón.
- **A 1920 px:** el `main` llega a su `max-w-7xl` y la lista se detiene en `max-w-6xl` (72 rem, 1.224 px), para que la cifra no quede lejos de su comercio. La izquierda mide unos 390 px y cada comercio unos 380 px.
- **Las categorías no van en columnas** ni el catálogo en una grilla de tarjetas iguales (DISENO.md 5 descartó la grilla de tarjetas para Insumos). Una tarjeta por renglón: se compara de arriba abajo, con el precio siempre en el mismo lugar.
- El aviso y las notas siguen en `max-w-prose`, arriba, en una columna.

### 4.8 Con el texto al 200 % a 320 px (160 px de app, modo `angosto`)

- Todo en una columna, como a 360 px. La tarjeta y la `Nota` pasan a `px-2` (`angosto:px-2`, ya en `Nota` y en la tarjeta de 4.2). El ícono del aviso va en la línea del título (`iconoEnLinea`).
- Las pestañas van una por renglón o de a dos, según quepan: «Lista de insumos» en negrita a 34 px mide 276 px de pantalla y baja a dos renglones como texto. Sin desplazamiento horizontal.
- «$12.990» (`cifras`, no se parte) y «Precio de ejemplo» van en renglones distintos. «Almacén El Ejemplo (comercio ficticio)» baja por palabras.
- El retracto sigue en `text-lg`, igual que el precio: con el zoom, los dos crecen juntos y la relación se mantiene (D2: legible con el texto al 200 %).
- La barra de secciones vuelve arriba, al flujo (ya lo hace `angosto`).

---

## 5. Cargando, vacío y error

Con el patrón de una sola columna de Insumos: las pestañas y el título siempre arriba, la baldosa `size-16 rounded-2xl` con su ícono `size-9`, el texto en `max-w-prose text-lg`. **Sin el aviso del piloto ni las notas:** no hay precios a la vista (DISENO.md: el rótulo va donde hay precios).

### 5.1 Cargando

- Pestañas, título y bajada visibles desde el principio.
- A los 400 ms, «Cargando…» [L 26] en `text-lg text-tenue`, con `aria-busy="true"` en la región. Es el patrón de `Cargando` de `Insumos.tsx`. Sin esqueleto ni ícono que gira.

### 5.2 Vacío (200 sin productos)

```
│ Catálogo                           │
│ Productos que usan las familias…   │
│ ┌────┐                             │  baldosa bg-tinta/7 text-tenue
│ │ ⌂  │                             │  Store size-9, aria-hidden
│ └────┘                             │
│ Todavía no hay productos en el     │  p text-lg max-w-prose
│ catálogo.                          │
```

Texto: «Todavía no hay productos en el catálogo.» [L 27]. Sin acción: la familia no puede agregar productos. Baldosa neutra, no `rocio`: no hay nada que hacer. Alineado a la izquierda.

### 5.3 Error al cargar (red o 5xx)

- Baldosa `bg-tinta/7 text-tenue` con `CloudOff`.
- «No pudimos traer el catálogo. Revisa tu conexión e inténtalo de nuevo.» [L 27], dentro de `Anunciado urgencia="alert"`.
- `Boton` principal «Volver a intentar» [L 26] (`GENERAL.volverAIntentar`). Es **el único `turquesa` macizo** que puede aparecer en esta pantalla. Al tocarlo vuelve a pedir y muestra «Cargando…».
- Nunca un catálogo viejo en su lugar.

### 5.4 Lo que no aplica

- **Éxito:** no hay acción que confirmar.
- **Conflicto (412):** no hay escritura.
- **403 de autorización de insumos:** el catálogo no la pide (analista 3). Si el contrato llegara a responder 403, es un defecto del backend, no un estado de la pantalla.
- **404:** no hay recurso por id en la ruta.

---

## 6. Accesibilidad

| Regla | Cómo se cumple |
|---|---|
| Contraste de texto (4,5:1) | Todo el texto en `tinta` o `tenue` sobre `hoja` o `papel` (7,2:1 o más en claro, 8,1:1 o más en oscuro). El aviso: `tinta` sobre `atenta-fondo`. La `Etiqueta` neutra: `tenue` sobre `tinta/7` sobre `hoja` (más de 6:1, lo mido en la revisión) |
| Íconos con significado (3:1) | `CircleCheck` en `ok` sobre `hoja` (6,9:1 en claro y 9,6:1 en oscuro, calculado); `CircleMinus` en `tenue`; `Info` en `atenta`. Todos llevan su palabra al lado: el ícono es `aria-hidden` |
| Áreas táctiles de 48 px | Lo único que se toca: las pestañas (`min-h-12`), la barra de secciones, el encabezado y «Volver a intentar» (`Boton`, 48 px). La tarjeta no se toca |
| Foco visible | El foco base (contorno de 3 px en `turquesa`, 2 px de separación) en las pestañas y el botón. La tarjeta no recibe foco. Al llegar, el foco va al `h1` |
| Estado nunca solo por color | «Hay en…» y «No hay en… por ahora», con íconos de forma distinta. «Por ahora no está disponible» con palabra e ícono. La pestaña activa con borde de 3 px, negrita y `aria-current` |
| Sin desplazamiento horizontal | A 320 px y con el texto al 200 %: una columna, las grillas con `grid-cols-1` en el ancho más chico, las cifras sueltas en `cifras` y las frases con `tabular-nums` sin `cifras` |
| Movimiento reducido | No hay movimiento: sin transición al llegar, sin fundido en el aviso (no aparece después de una acción) |
| Una sola acción principal | Ninguna en el estado normal; «Volver a intentar» en el error |
| Proyector | Ningún texto relevante bajo 1 rem: el precio, el retracto y el stock van en `text-base` o más. No se usa `text-sm` en esta pantalla |
| Encabezados | `h1` Catálogo, `h2` por categoría, `h3` por producto. Así se salta de categoría o de producto con el lector |
| Idioma y cifras | `lang="es-CL"` de la app. `$12.990` con punto de miles y sin decimales |

**Tema oscuro:** solo tokens, así que no hay nada que especificar aparte. En la revisión miro en especial el aviso (`atenta` sobre `atenta-fondo` oscuro) y la `Etiqueta` neutra.

---

## 7. Textos de la pantalla

Todos van a `lenguaje.md`, sección 27 «Catálogo (MATU-59)», tal como los aprobó Jorge el 08-11. Ninguno es nuevo de esta especificación.

| Dónde | Texto | Fuente |
|---|---|---|
| Pestaña, título y `<title>` | Catálogo · «Catálogo · MATU» | [L 27] |
| Bajada | Productos que usan las familias que cuidan. Mirar no te compromete a nada. | [L 27] |
| Aviso del piloto | **Precios de ejemplo.** MATU todavía no tiene convenio con comercios, y en esta demo no se cobra dinero real. | [L 27] |
| Junto a cada precio | Precio de ejemplo | [L 27] |
| Bajo el precio | IVA incluido | [L 27] |
| Comercio | `{nombre}` (comercio ficticio) | [L 27], una vez por tarjeta (N2) |
| Hay | Hay en `{nombre}` | [L 27] |
| No hay | No hay en `{nombre}` por ahora | [L 27] |
| Ningún comercio lo tiene | Por ahora no está disponible | [L 27] |
| Nota de stock | Lo que hay se confirma antes de pagar. | [L 27] |
| Envío | El envío se suma al pedido, una sola vez por pedido. | [L 27] |
| Retracto, con sello | Derecho a retracto: tienes 10 días desde que lo recibes. No aplica si abres el sello del producto. | [L 27] |
| Retracto, sin sello | Derecho a retracto: tienes 10 días desde que lo recibes. | [L 27] |
| Categorías | Higiene y cuidado personal · Cuidado de la piel · Alimentación | [L 27], vienen de los datos |
| Vacío | Todavía no hay productos en el catálogo. | [L 27] |
| Error | No pudimos traer el catálogo. Revisa tu conexión e inténtalo de nuevo. | [L 27] |
| Cargando | Cargando… | [L 26] |
| Botón del error | Volver a intentar | [L 26] |
| `aria-label` de las pestañas | Vistas de Insumos | [L 21] |

**Palabras que no aparecen en la pantalla:** «stock» (lenguaje 3: se dice «Hay» y «Lo que hay»), «Desde», «oferta», «comprar», «pedir», «carro», «agregar», «recomendado», «más barato», y los términos clínicos de lenguaje 3.2 (también en los nombres de producto: «Crema protectora de la piel», nunca escaras ni úlceras; «Bolsa colectora», nunca ostomía). Sin afirmaciones de salud en la presentación (D3).

---

## 8. Criterios visuales verificables

1. En el estado normal **no hay ningún elemento en `turquesa` macizo** (ni botón, ni chip, ni fondo). En el error, «Volver a intentar» es el único.
2. **No hay botón «Pedir»** ni ningún control dentro de las tarjetas: con Tab, después de las pestañas el foco sale de la pantalla sin pasar por ninguna tarjeta.
3. El aviso «Precios de ejemplo.» aparece **exactamente una vez**, antes de la primera categoría, y no aparece en los estados cargando, vacío ni error.
4. **Cada cifra de precio tiene «Precio de ejemplo» a su lado** (mismo renglón cuando cabe) e «IVA incluido» debajo. Ninguna cifra va en `turquesa`.
5. **El retracto de cada tarjeta tiene un `font-size` calculado mayor o igual al de su precio** (19 px y 19 px a tamaño normal; 38 px y 38 px con el texto al 200 %). Lo mido con las herramientas del navegador.
6. Pañales, toallitas, protectores y crema llevan la frase del sello; el suplemento y las bolsas, no. Coincide con `retracto_pierde_al_abrir` de la semilla, no con la categoría (las bolsas están en «Higiene y cuidado personal» y no la llevan).
7. Cada fila de comercio dice «Hay en…» o «No hay en… por ahora» con su ícono: el estado se entiende en escala de grises.
8. Cada nombre de comercio va seguido de «(comercio ficticio)» en su tarjeta. No aparecen RUT, razón social, dirección, teléfono ni marca.
9. Un producto sin stock en ningún comercio muestra «Por ahora no está disponible», sus precios y su retracto, sin opacidad reducida.
10. A 320 px, a 360 px y con el texto al 200 % a 320 px, `document.documentElement.scrollWidth` es igual a `clientWidth`.
11. A 1280 px, la tarjeta va en dos columnas y los dos comercios lado a lado; a 360 px, todo en una columna.
12. Ningún texto de la pantalla mide menos de 17 px de `font-size` calculado.
13. Nada del catálogo en `localStorage`, `sessionStorage` ni en la URL (la ruta es `/insumos/catalogo`, sin parámetros).
14. Insumos y la Lista de insumos no muestran nada del catálogo, y el catálogo no muestra nada de lo que la familia anotó.

---

## 9. Lo que reviso después de construir

Capturas a 320 px con el texto al 200 %, 360 px, 1280 px y 1920 px, en tema claro y oscuro, con la semilla de MATU-59 (seis productos, dos comercios, al menos un producto sin stock en ningún comercio y uno con stock en uno solo):

- `/insumos/catalogo` con productos, como `admin` y como `observador` (deben verse iguales).
- Cargando (con la red lenta), vacío (semilla sin productos) y error (backend detenido).
- `/insumos` en el permiso de Insumos y en «Falta el permiso», con las pestañas «Insumos» y «Catálogo».
- Las pestañas a 360 px en dos renglones.
- Los criterios 1 a 14 de la sección 8, uno por uno.

### 9.1 P3 aceptados en la revisión del 08-11 (v1.1)

- Con el 200 %, la `Etiqueta` neutra en `rounded-full` se parte en tres renglones y queda como un óvalo. Se lee y el contraste cumple; `angosto:rounded-xl` en `Etiqueta` queda para una historia de pulido. En `Permiso`, el antetítulo «Insumos» repite la pestaña activa (componente anterior, fuera de MATU-59). A 1920 px, la línea de las pestañas llega más allá que las tarjetas (`max-w-6xl`): es lo que pide 4.7.

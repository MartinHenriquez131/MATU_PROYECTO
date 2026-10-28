# MATU · Plan de diseño de la demo web

**Para qué es esta demo:** se proyecta desde un computador el viernes 30 de octubre, frente al profesor guía y público. Tiene que mostrar, en una pantalla ancha, que una persona puede dejar a la suya con otra y salir tranquila, que MATU avisa antes de que se acaben los insumos y que se paga una sola vez y se cobra lo justo.

**Quién la usa de verdad:** Carmen, que cuida a su mamá, está cansada y tiene poco tiempo. Rosa, que la reemplaza el fin de semana y abre un enlace sin cuenta. Y quien atiende el mostrador de Farmacia Los Aromos.

> **Nota del 26/10/2026: ADR-027 aprobado.** MATU pasa a precios exactos, confirmación de stock y un solo cobro del total con envío. Las pantallas de pedido, pago, comercio y entregado (escenas 21 a 29 y 32) se rediseñan: desaparecen la reserva del 15 %, el "monto real" y la devolución con débito. Lo que este documento dice de esas pantallas (la tabla de la sección 3, la boleta con estimado, reserva y monto real, y la consola con "Monto real") queda vigente solo hasta que llegue su especificación nueva. No se construye nada nuevo sobre el modelo anterior. **La especificación nueva ya está en [`ESPEC-ADR-027.md`](ESPEC-ADR-027.md)** (26/10) y manda sobre este documento en esas pantallas. Su sección 6 (27/10) especifica cinco ajustes de la ficha, el compartir, el PIN del relevo y "Quién la vio". Su sección 7 (27/10) especifica el reflujo a 320 px con el texto al 200%, los P3 del 27/10 y la vista de app en el teléfono.

**De dónde sale la identidad:** del mundo de Carmen. La **hoja pegada en el refrigerador** con el día de María, el **PIN dictado por teléfono** y la **boleta** de la farmacia. La hoja es lo memorable: se dibuja igual en el inicio, al editar, en la página de Rosa y para imprimir.

## 1. Color

**El color principal de MATU es el turquesa** (directriz de Jorge, 25/10/2026). **El logo es un corazón blanco dentro de un círculo turquesa.** Siete tokens de marca, en `src/index.css` (`@theme`). El tema sigue al sistema y se puede fijar desde la guía del presentador. Un proyector lava los contrastes, así que el tema claro es el de la presentación y el oscuro se mantiene completo.

El turquesa trabaja en dos tonos. El de **marca** es el que se reconoce: el círculo del logo y los acentos grandes. Ningún turquesa medio sostiene texto chico sobre fondo claro, así que el texto, los enlaces y los botones van en el **turquesa profundo**. Ese token conserva el nombre `pino` para no tocar los componentes. Se renombra a `turquesa` después de la demo, en el mismo cambio que los `.tsx`.

| Token | Claro | Oscuro | Rol | Contraste medido |
|---|---|---|---|---|
| `papel` | `#ECF3F2` | `#0D1719` | Fondo general, neblina de agua. También la barra lateral: sin bloque de color | — |
| `hoja` | `#FFFFFF` | `#152427` | La hoja de la ficha, los formularios y las listas | — |
| `tinta` | `#13252A` | `#E4EEEB` | Texto principal y la barra de la consola de la farmacia | 14,1:1 sobre `papel` claro; 15,4:1 sobre `papel` oscuro |
| `tenue` | `#485B5F` | `#A9BCB8` | Texto secundario | 6,4:1 sobre `papel` y 7,2:1 sobre `hoja` claros; 9,2:1 y 8,1:1 oscuros |
| `pino` (turquesa profundo) | `#086764` | `#52CCC3` | Texto de acción, enlaces, botones, foco, navegación activa, barras de avance | Claro: 6,0:1 sobre `papel`, 6,7:1 sobre `hoja`, 5,6:1 sobre `rocio`; `papel` sobre `pino` (botón) 6,0:1. Oscuro: 9,4:1 sobre `papel`, 8,2:1 sobre `hoja`, 6,7:1 sobre `rocio`; `papel` sobre `pino` (botón) 9,4:1 |
| `marca` (turquesa de marca) | `#0D9A94` | `#0D9A94` | El círculo del logo y los acentos grandes. Nunca texto | Corazón blanco sobre `marca`: **3,5:1** en los dos temas. `marca` sobre `papel`: 3,1:1 claro, 5,3:1 oscuro |
| `miel` | `#E3A43A` | `#E8B866` | Calidez: el imán de la hoja y los puntos de "Su día". Nunca texto ni dato | Decorativa: no lleva información, así que no tiene mínimo |

**Derivados**, no son tokens nuevos sino mezclas de los anteriores:

| Derivado | Mezcla | Rol | Contraste medido |
|---|---|---|---|
| `linea` | `tinta` al 14 % | Divisores y contornos de superficies. **Nunca el borde de un control** | 1,3:1: no identifica nada por sí sola |
| `rocio` | `pino` al 12 % sobre `hoja` | Fondo de notas, botón suave, opción elegida | ver `pino` |
| `borde` | `tinta` al 50 % con `hoja` | Borde de los controles: campos, opciones y chips sin elegir | 3,5:1 sobre `hoja` y 3,1:1 sobre `papel` claros; 4:1 y 4,6:1 oscuros (WCAG 1.4.11) |

**El logo.** Círculo `marca` con el `Heart` de lucide relleno en blanco (3,5:1 en los dos temas). Sobre un fondo de marca, como el panel del alta, se invierte: círculo blanco y corazón `marca` (3,5:1). Nunca el corazón en `miel` ni el círculo en `pino`. El favicon, los íconos del manifiesto y `theme-color` usan el mismo `#0D9A94`.

**Por qué se queda `miel`.** El imán es lo que hace que la hoja sea una hoja pegada en el refrigerador, y la hoja es lo memorable de MATU. Un turquesa solo, sobre blanco, es el uniforme de las apps de salud. El ámbar de la miel es casi el complementario del turquesa: con un solo punto cálido por pantalla, el imán se ve desde el fondo de la sala y la marca deja de ser clínica. Pierde un rol: ya no es el corazón del logo, que ahora es blanco.

Los semánticos van aparte del acento, siempre con su fondo y con una palabra: `pronto` (`#A8261B` sobre `#FBE9E6`, 6,1:1), `atenta` (`#835000` sobre `#FCEFD8`, 5,9:1) y `ok` (`#22663D` sobre `#E1F1E6`, 5,9:1). El turquesa nunca comunica estado: "Tranquila" y "Listo" son `ok`, un verde que no se confunde con la marca.

La pasarela de pago **no** usa la marca: es otra empresa y se ve en grises fijos, sin tema oscuro. Va rotulada dos veces: el encabezado "Pasarela de pago simulada · Transbank, ambiente de prueba" y, debajo, una franja `pasarela-hoja` con un borde izquierdo en `pasarela-tinta` y el ícono `Info` de lucide, con el texto "**Pago de prueba. No se cobra dinero real.**" en negrita y `text-base`. Tiene sus propios tokens, que los componentes ya usan (26/10): ningún color va escrito a mano para no escribir colores a mano: `pasarela` `#EEF0F3` (fondo), `pasarela-hoja` `#FFFFFF`, `pasarela-tinta` `#1F2A37` (12,7:1 sobre el fondo), `pasarela-presionado` `#111827`, `pasarela-tenue` `#4B5563` (6,6:1), `pasarela-rechazo` `#9F1C14` (7,9:1 sobre blanco) y `pasarela-rechazo-fondo` `#FEF2F2`.

## 2. Tipografía

| Cara | Rol |
|---|---|
| **Atkinson Hyperlegible** 400 y 700 | Todo el texto, los botones y las cifras. Diseñada para baja visión. Base de 17 px (`html { font-size: 106.25% }`) |
| **Bricolage Grotesque** variable, 800 (`titular`) | Solo titulares desde 1,5 rem: el título de cada página, el nombre en la hoja, "Enlace creado". Tracking negativo. Única excepción: la palabra "MATU" junto al logo, a 1,25 rem |
| **Atkinson Hyperlegible Mono** (`digitos`) | Solo lo que se dicta dígito a dígito: el PIN y el código de retiro. Es también `--font-mono`, para que `pre`, `code` y `kbd` nunca caigan en una fuente del sistema. El `pre` de la lista para exportar hereda la cara del texto |

**Escala.** Son los pasos de Tailwind, en rem sobre 17 px. Reemplazan a la escala del primer borrador (0,85 · 1 · 1,2 · 1,5 · 2,25 · 3,4) por el paso más cercano, porque así se construyó y se ve bien en el proyector:

| Clase | rem | px | Uso |
|---|---|---|---|
| `text-sm` | 0,875 | 14,9 | Solo datos secundarios: ayuda bajo un campo, hora al pie, nota de un renglón de la boleta. **Nunca un estado, una acción ni un dato que el público tenga que leer** |
| `text-base` | 1 | 17 | Texto, botones, chips de estado, pistas de la barra lateral |
| `text-lg`, `text-xl` | 1,125 y 1,25 | 19 y 21 | Subtítulos de sección |
| `text-2xl` | 1,5 | 25,5 | Título de página a 360 px, montos destacados |
| `text-3xl`, `text-4xl` | 1,875 y 2,25 | 32 y 38 | Título de página en pantalla ancha |
| `text-5xl`, `text-6xl` | 3 y 3,75 | 51 y 64 | El nombre en la hoja del relevo, el PIN, la bienvenida |

`text-xs` (12,75 px) no se usa. El dinero, las fechas y los días van con números tabulares en la cara del texto, nunca monoespaciada. La utilidad `cifras` (tabular y sin salto de línea) envuelve **solo una cifra, fecha u hora suelta**, para que "$27.980" o "30/10/2026" no se partan. Una fecha con su hora son **dos** `cifras` ("24/10/2026," y "10:05"), para que la hora pueda bajar de renglón sin cortar la fecha (pieza `Cuando`, ESPEC-ADR-027, 7.3). Una frase que contiene cifras ("$13.990 el paquete. Sugerimos 2.") usa `tabular-nums` sin `cifras`, para que refluya a 320 px. Párrafos de 65 caracteres como máximo.

## 3. Composición

Todo se diseña para 1280 a 1920 px y se ordena con **container queries**, no con media queries. Así, "Texto al 200%" (que aplica `zoom: 2` solo a la app) y el zoom del navegador al 400% en 1280 px (320 px efectivos) hacen que todo fluya a una columna sin desplazamiento horizontal. No hay una experiencia móvil aparte: es el mismo layout que se estrecha.

**Reflujo literal (27/10/2026).** El criterio es el de `CLAUDE.md` tomado al pie de la letra: 320 px de pantalla **con** "Texto al 200%", o sea 160 px efectivos para la app. Para que las 36 escenas pasen sin tocar lo que se ve en el proyector, hay dos piezas en `src/index.css`:
- **`overflow-wrap: break-word` en `body`.** Una palabra que no cabe sola en su renglón se parte. Es `break-word` y no `anywhere`, porque `anywhere` achica el ancho mínimo de todo y deja columnas de una letra por renglón.
- **Toda grilla declara sus columnas también en el ancho más chico** (`grid-cols-1`). Una pista `auto` no baja del ancho de su contenido.

**Dos variantes de composición.** Son las únicas reglas de layout que miran un ancho fijo, y por eso se definen una vez en `src/index.css` (`@custom-variant`) y no en cada componente:

| Variante | Cuándo | Para qué | Por qué ese corte |
|---|---|---|---|
| `angosto:` | La app mide menos de 16 rem (`@container app`) | Quitar rellenos (`px-2`), apilar un ícono grande y su título, y achicar el PIN y las fechas en tamaño de título | Solo pasa con "Texto al 200%" en una pantalla de menos de 544 px. Nunca a 320 px sin zoom ni en el proyector, así que no cambia nada de lo que ya se aprobó |
| `telefono:` | La pantalla mide menos de 40 rem (640 px) y la app no está en modo angosto | La vista de app móvil: la barra de secciones abajo | Mira la pantalla y no la app, así que "Texto al 200%" en el proyector nunca la activa. Con el texto al 200% en un teléfono, la app está en modo angosto y la barra vuelve arriba, porque cinco secciones fijas no caben en 160 px |

Lo que está fuera de la app (la franja y el distintivo del presentador) no tiene el contenedor `app`, así que usa `max-sm:`, el mismo corte de 40 rem.

**Lo fijo abajo no tapa el foco (28/10/2026).** Bajo 40 rem, la capa base de `src/index.css` le da al `html` un `scroll-padding-bottom` de 10 rem (`--spacing(40)`): la barra de secciones mide unos 69 px y el distintivo flotante va encima. Así, lo que recibe el foco o se desplaza a la vista queda sobre los dos (WCAG 2.4.11). Va en la capa base y no como clase en `index.html`, porque es una regla del documento entero.

**Medidas fijas del layout.** Son constantes de composición, una por lugar, y se escriben en rem en el componente: la barra lateral de la familia (16,5 rem), la columna del vencimiento en la página del relevo (17 rem), la cola de la consola (19 rem), la columna de etiquetas de Grupo familiar (12 rem) y el cajón de la guía (24 rem). No son tokens mientras se usen una sola vez. Si una se repite, pasa a `--container-*` en `@theme`.

**Alineación a la izquierda** en todo el contenido. Se centran solo el PIN (se lee en voz alta como un bloque) y la hoja en la página de Rosa (es el único objeto de la página).

### La familia (Carmen): la app principal

```
┌ Piloto académico con datos de prueba [Familia|Relevo|Comercio] ‹ 6 de 35 Inicio › Guía ? ┐
├──────────────┬────────────────────────────────────────────────────────────────────┤
│ (M) MATU     │ Cuidado de María Soto              viernes 30/10/2026, 14:20  (C) │
│              ├────────────────────────────────────────────────────────────────────┤
│ Inicio       │ Hola, Carmen                                                       │
│ Ficha  1 de 3│                                                                    │
│ Insumos   ●  │  ┌────(imán)──────────────┐   Lo que necesita atención             │
│ Pedidos      │  │ Ficha de María         │   ● Pronto  Pañal adulto M   6 días    │
│ Grupo        │  │ Su día ........ Listo  │   ▬▬▬▬▬▬▬░░░░░░░░░░░░░░░░             │
│              │  │ Si se altera .. Falta  │   Rosa puede ver la ficha, vence en 23 h│
│              │  │ A quién llamar  Falta  │   Rosa abrió la ficha, ayer 10:05       │
│              │  │ ▬▬▬ ░░░ ░░░            │                                        │
│              │  └────────────────────────┘                                        │
│              │  [Completar la ficha] [Compartir con un relevo]                    │
└──────────────┴────────────────────────────────────────────────────────────────────┘
```

- **Barra lateral** sobre `papel`, sin fondo propio, de **16,5 rem**: logo, cinco secciones y una pista de estado en cada una ("1 de 3", un punto de Pronto, "En curso"), en la misma línea que el nombre y en `text-base`, porque es un estado que el público lee en el proyector. La medida sale del renglón más largo: "Ficha de relevo 1 de 3" en negrita, cuando está activa, mide unos 248 px más la píldora y los márgenes. Con 14 rem sobresalía 22 px. Bajo 56 rem de ancho se vuelve una fila superior. **En el teléfono** (`telefono:`) es una barra fija abajo, con cinco columnas iguales de ícono y rótulo corto ("Inicio", "Ficha", "Insumos", "Pedidos", "Grupo"). Cada sección mide 56 px de alto como mínimo, la elegida va sobre `rocio`, y la pista pasa a un punto sobre el ícono, con su texto para el lector de pantalla (ESPEC-ADR-027, 7.6).
- **Encabezado** con la persona cuidada a la izquierda y quien está conectada a la derecha, con la fecha y la hora de la demo.
- **Pestañas** dentro de una sección cuando hay vistas hermanas: Ficha (Campos, Compartir, Enlaces, Quién la vio, Para imprimir) e Insumos (Qué se acaba, Lista de reposición).
- **Dos columnas** desde 48 rem de ancho de contenido. La izquierda es lo que se hace; la derecha, el resultado:

| Sección | Izquierda | Derecha |
|---|---|---|
| Ficha | Los tres campos, o el campo que se edita | La hoja tal como la verá el relevo, al día mientras se escribe |
| Compartir | Quién, qué campos, hasta cuándo | La hoja solo con los campos elegidos |
| Insumos | Horizonte de 30 días: una barra por producto que termina el día que se acaba | El detalle del producto elegido, declarar o "ya lo compré" |
| Lista de reposición | Cantidades por producto | Total, pedir a domicilio y exportar |
| Pedido | Productos, dirección, crédito o débito, seguimiento | La boleta: estimado, reserva o cobro, monto real y lo que vuelve |

```
 Insumos: el horizonte de 30 días
              hoy                aviso 7 d                                29/11
 Pañal M      ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬|                                ● Pronto    6 días
 Toallitas    ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬|▬▬▬▬▬▬▬▬▬▬▬                      ◐ Atenta   11 días
 Suplemento   ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬|▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬                ○ Tranquila 15 días
 Crema        ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬|▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬ ○ Tranquila 40 días
```

### El alta: antes de tener cuenta

```
┌───────────────────────────────┬────────────────────────────────────────────┐
│ (pino, turquesa profundo)     │ Paso 2 de 3                                │
│ (M) MATU                      │ ¿A quién cuidas?                           │
│                               │ [¿Cómo se llama?        ] [¿Cómo le dicen?]│
│ Que el cuidado no dependa     │ ¿Cuánto apoyo necesita?  ( ) ( ) ( )       │
│ de una sola persona.          │ ¿Dónde vive? Puedes dejarlo para después   │
│                               │ No te preguntamos qué enfermedad tiene…    │
│  1 Tu cuenta          hecho   │                                            │
│  2 A quién cuidas     ahora   │                         [Continuar]        │
│  3 El permiso                 │                                            │
└───────────────────────────────┴────────────────────────────────────────────┘
```

La bienvenida usa el panel izquierdo completo para la hoja, sujeta con su imán, y a la derecha lo que hace MATU en tres frases y las dos acciones. Los pasos sí van numerados porque son una secuencia.

### El relevo (Rosa, `/r#<token>`): una página pública

```
┌──────────────────────────────────────────────────────────────────────────┐
│ (M) MATU   Ficha de cuidado                                              │
├──────────────────────────────────────────────────────────────────────────┤
│                    ┌──────(imán)──────────────┐   Carmen te la compartió. │
│                    │ María                    │   Disponible hasta        │
│                    │ Su día                   │   31/10/2026, 14:22       │
│                    │  08:00 ● Despierta sola  │   [Actualizar]            │
│                    │  08:30 ● Desayuno…       │   Solo Carmen puede       │
│                    │ Si se altera             │   cambiarla.              │
│                    │ A quién llamar           │                           │
│                    └──────────────────────────┘                           │
└──────────────────────────────────────────────────────────────────────────┘
```

Sin cuenta, sin navegación y sin nada que no sea la ficha. Antes de la hoja, una sola pregunta centrada: el PIN de cuatro números. Después del canje el token se borra de la dirección con `history.replaceState`.

### El comercio (Farmacia Los Aromos): una consola de trabajo

```
┌ (tinta) Farmacia Los Aromos (comercio ficticio)   Pedidos de MATU   14:20 ┐
├──────────────────────────────┬─────────────────────────────────────────────┤
│ Pedidos de hoy               │ Pedido #4821 para María                     │
│ #4821  6 productos  ● Por    │ 1 Preparar  ─  2 Monto real  ─  3 Retiro    │
│        retiro 17–18  preparar│ Tope autorizado                   $69.000   │
│ #4822  3 productos  ◐ Prepa- │ Pañal adulto M x30 × 2            Listo     │
│ #4819  4 productos  ○ Retira-│ Toallitas x80 × 1               Sin stock   │
│                              │   [No disponible] [Reemplazar por $5.290]   │
└──────────────────────────────┴─────────────────────────────────────────────┘
```

Más densa y más sobria: la barra superior en `tinta`, la cola a la izquierda como una lista con el estado en la forma, y el pedido elegido a la derecha con sus tres pasos numerados (sí es una secuencia).

### El panel del presentador

```
┌ ● Piloto académico con datos de prueba │ Familia  Relevo  Comercio │ ‹ 11 de 35  Relevo: escribe el PIN  Simulado › │ PIN 4821 │  Guía ? ┐
```

- Una **franja superior** delgada, en el flujo del documento: el distintivo, el rol, la escena con anterior y siguiente, una ayuda contextual (el PIN del enlace o "Rodrigo guarda este campo") y el botón de la guía. Con el rol relevo muestra la dirección: `/r#k3J9…` y, después del canje, `/r`.
- Un **cajón lateral** de 24 rem que se abre con el botón o con `?`, sin tapar la app: la app se angosta y se reordena. Tiene el estado del backend, la escena actual con su nota y su etiqueta Real o Simulado, las escenas por capa, "Texto al 200%", el tema, el modo presentación, los atajos y "Reiniciar demo".
- **Modo presentación** (`p`): desaparece la franja y queda solo el distintivo, pequeño, en la esquina inferior izquierda, con un botón para volver a abrir la guía.
- **El distintivo** dice "**Piloto académico con datos de prueba**", con el punto `miel` delante, en una píldora `tinta` al 7 % con texto `tenue` en negrita. Lo exige la figura legal del piloto (4.1), así que la regla es: **visible siempre, en todas las pantallas y en las tres apps, también en modo presentación y con "Texto al 200%"**. Ningún modo, atajo ni ancho lo oculta. Bajo 90 rem se parte en dos líneas ("Piloto académico / con datos de prueba") dentro de la misma píldora. No se abrevia.
- **Bajo 90 rem, la franja se compacta** para caber en una línea: la guía queda como ícono y `?` (con `aria-label="Abrir la guía"`), los roles van sin ícono, la dirección del relevo se abrevia, las ayudas usan rótulos cortos ("PIN 4821", "Código 4729") y "Ver lo que ve la familia" se oculta mientras se muestra el código de retiro.
- **En el teléfono** (`max-sm:`), la franja queda en dos renglones de 48 px: el distintivo y la guía, y "‹ 6 de 36 ›" con la ayuda de la escena. El selector de rol, la dirección del relevo, el título de la escena y la etiqueta Real o Simulado se ven en el cajón (ESPEC-ADR-027, 7.6.3).

### Rótulos del piloto

Además del distintivo, los montos llevan un rótulo propio, porque el público podría leerlos como precios reales:

- **`PreciosDeEjemplo`.** Una `Nota` en tono `atenta` (fondo `atenta-fondo`) con el ícono `Info` de lucide en `atenta`. Título en negrita: "**Precios de ejemplo.**" Texto: "MATU todavía no tiene convenio con comercios, y en esta demo no se cobra dinero real." Va al pie de la lista de reposición, bajo "La lista sirve aunque compres en otra parte", y al pie de la boleta, en la columna derecha del pedido y de "Pedido entregado". Una vez por pantalla, nunca junto al botón principal.
- **Por qué `atenta` y no `rocio`.** `rocio` es el fondo de las notas que explican el producto ("Reservamos…", "Ya sumamos lo que llegó"). El rótulo del piloto es otra clase de mensaje: una advertencia sobre la demo misma. No se confunde con un estado "Pronto" ni "Atenta" porque no lleva figura de nivel (● ◐ ○) ni palabra de estado: lleva el ícono `Info` y una frase completa.
- **El comercio ficticio** se nombra siempre como "Farmacia Los Aromos (comercio ficticio)" la primera vez que aparece en cada pantalla: en la barra de la consola y en la bajada de "Tu pedido".
- **Atajos:** `?` guía, `]` o `Av Pág` siguiente escena, `[` o `Re Pág` anterior, `p` modo presentación. No actúan dentro de un campo de texto y se pueden apagar desde la guía (WCAG 2.1.4).

## 4. Principios

1. **La hoja del refrigerador es lo memorable.** Hoja de papel con renglones y un imán de miel, la única superficie con sombra de toda la demo (`shadow-xl`, el imán `shadow-md`). Todo lo demás es plano. Solo flotan con sombra las capas que tapan algo: el aviso (`shadow-lg`) y el cajón de la guía (`shadow-2xl`).
2. **Resumen antes del detalle.** Cada página abre con la frase que importa ("Le alcanza 6 días, hasta el 05/11/2026") y después muestra cómo se llegó a ella.
3. **El estado está en la forma.** Barras de días que terminan en su fecha, una marca a los 7 días, chips cuya figura cambia (● Pronto, ◐ Atenta, ○ Tranquila) y una franja a la izquierda de cada fila. Siempre con palabra, nunca solo con color.
4. **Cifras tabulares y formato chileno.** Pesos enteros (`$69.000`), fechas `DD/MM/AAAA`, hora de 24 horas.
5. **Movimiento solo como respuesta.** El aviso aparece después de una acción, la barra cambia de largo cuando cambia el número, el aviso y el cajón aparecen con un fundido de 180 ms (`aparecer`). Un solo momento orquestado: al crear el enlace, el ícono se traza y los cuatro dígitos del PIN caen uno a uno. Con `prefers-reduced-motion` todo es inmediato. Las páginas cambian sin deslizarse.
6. **El texto habla desde la persona.** Voz activa, en tú, y el mismo verbo en el botón y en su confirmación: "Crear cuenta" y "Cuenta creada", "Cortar el enlace" y "Enlace cortado", "Anotar la compra" y "Compra anotada". Los errores dicen qué pasó y cómo seguir.

## 5. Revisión contra la guía de diseño

El primer borrador de este plan, revisado contra `frontend-design.md` antes de escribir código. Lo que salió como default y se cambió:

| Primer borrador | Ahora | Por qué |
|---|---|---|
| Barra lateral en `pino` macizo con íconos blancos | Barra lateral sobre `papel`, sin fondo; la sección activa en una píldora `hoja` con texto `pino` | La barra oscura es el kit de cualquier panel SaaS. Sin bloque de color, la hoja queda como lo único con presencia |
| Inicio con cuatro tarjetas de indicadores (ficha 1/3, 6 días, pedido, enlaces) | La hoja a la izquierda y una sola lista de "Lo que necesita atención", ordenada por urgencia | El número grande con etiqueta chica es el tratamiento por defecto. Aquí el objeto real (la hoja) dice más que un 33% |
| Insumos como una grilla de tarjetas iguales, una por producto | Un horizonte de 30 días: cada producto es una barra que termina el día que se acaba, con la marca del aviso a los 7 días | La forma es el dato: se ve de un vistazo qué se acaba primero y cuánto falta para el aviso |
| Panel del presentador como columna fija a la derecha | Franja superior delgada y cajón que se abre con `?`, más un modo presentación | Una columna fija compite con la app en el proyector. El público tiene que mirar MATU, no la guía |
| Comercio con el mismo marco de la familia y otro color | Consola: barra en `tinta`, cola a la izquierda y pedido a la derecha | Es otra persona con otro trabajo. Cambiar solo el color no lo dice |
| Marcadores "01, 02, 03" en el alta | "Paso 2 de 3" y una lista numerada simple | Es una secuencia de verdad, así que hay números, pero sin el adorno del cero |
| Páginas que entran deslizándose | Cambio inmediato y foco al título | Las entradas deslizadas en cada página leen como generadas, y en un proyector marean |
| Etiquetas "CAPA 1", "ESCENA ACTUAL" en mayúsculas en la guía | "Capa 1. Ficha de relevo" en frase normal | Las etiquetas en mayúsculas con tracking son plantilla |
| Botones de ancho completo, como en la versión de teléfono | Botones al ancho de su texto, agrupados a la izquierda bajo lo que confirman | En escritorio un botón de 900 px no se lee como botón |
| "Pedir a domicilio →" | "Pedir a domicilio por $60.000 aprox." | La flecha en el botón es marca de plantilla; el monto informa |

Se mantiene, porque funcionó en la versión anterior y no es un default: Atkinson Hyperlegible, la hoja con el imán de miel, la boleta con el borde cortado y las fuentes locales con `@fontsource`.

### Revisión del 25/10/2026: la marca pasa al turquesa

Jorge decidió que el color principal de MATU es el turquesa y que el logo es un corazón blanco dentro de un círculo turquesa. El primer borrador había elegido el verde `pino` justamente para alejarse del turquesa de las apps de salud. Lo que cambió y cómo se evita ese genérico:

| Antes | Ahora | Por qué |
|---|---|---|
| `pino` `#0E5E57`, verde profundo (6,7:1 sobre `papel`) | `pino` `#086764`, turquesa profundo (6,0:1 sobre `papel`, 6,7:1 sobre `hoja`) | Gira el tono hacia el turquesa (178°) sin bajar de AA con margen para el proyector. Mantiene el nombre para no tocar ningún `.tsx` antes de la demo |
| Sin color de marca aparte: el logo usaba `pino` | `marca` `#0D9A94`, igual en los dos temas | El turquesa que se reconoce no alcanza 4,5:1 para texto chico, así que vive solo en el logo y en los acentos grandes. Es el más claro que todavía da 3:1 con el corazón blanco (3,5:1). El `#14B8A6` de las plantillas da 2,5:1 y no sirve |
| `pino` oscuro `#74D2C3`, menta | `pino` oscuro `#52CCC3`, turquesa claro | Más saturado, de la misma familia que la marca. Sigue en 8,2:1 sobre `hoja` oscura |
| `papel` `#EDF2EE`, verde neblina | `papel` `#ECF3F2`, neblina de agua | Un grado hacia el agua para que el fondo no tire a verde junto al turquesa. `tinta` y `tenue` no cambian y suben un poco su contraste |
| `miel` también en el corazón del logo | `miel` solo en el imán y los puntos de "Su día" | El corazón es blanco por la directriz. La miel queda como el único punto cálido, y eso es lo que aleja a la marca del turquesa clínico |
| El borde de los campos usaba `linea` (1,3:1) | Derivado `borde` (3,5:1 sobre `hoja`) | Hallazgo de esta revisión: los campos no se distinguían del fondo (WCAG 1.4.11). `linea` queda para los divisores |
| Barra lateral de 14 rem, pistas en `text-sm` (14,9 px) | Barra de 16,5 rem, pistas en `text-base` (17 px) | En el proyector, ningún estado bajo 1 rem. Con 14 rem la píldora activa sobresalía 22 px. Se descartó poner la pista debajo del nombre: suma cinco renglones y separa el estado de su sección |
| Colores de la pasarela escritos en el componente | Tokens `pasarela-*` con los mismos valores. **Hecho:** el 26/10 los componentes pasaron a usarlos | Política 9: ningún color a mano, ni siquiera en la parte que no es de la marca |

Para que el turquesa no sea el de cualquier app de salud: no hay degradados ni fondos turquesa a pantalla completa (salvo el panel del alta, en el tono profundo), el turquesa nunca comunica estado, la hoja con su imán sigue siendo lo que se recuerda y la tipografía de los titulares sigue siendo Bricolage.

## 6. Estados de los componentes

Todos con 48 px de alto como mínimo y el foco base: contorno de 3 px en `pino` con 2 px de separación (6,0:1 sobre `papel`). Ningún componente quita el contorno de foco sin poner otro igual de visible.

| Componente | Normal | Presionado o elegido | Deshabilitado | Cargando | Error |
|---|---|---|---|---|---|
| Botón principal | `pino` macizo con texto `papel`. Uno solo por pantalla | `brightness-95` | Opacidad 50 %, con una frase al lado que dice por qué ("Resuelve lo que falta para seguir") | Mismo ancho, texto en gerundio ("Guardando…") y `aria-busy` | El botón no cambia: el error va en `MensajeError` encima |
| Botón secundario | `hoja` con anillo `pino` al 70 % (3,5:1) y texto `pino` | Fondo `rocio` | Igual que el principal | Igual que el principal | — |
| Botón suave y de texto | `rocio` o subrayado, texto `pino` | `brightness-95` o subrayado pleno | Opacidad 50 % | — | — |
| Campo de texto | `hoja` con anillo `borde` de 2 px | Foco: anillo `pino` y el contorno de foco base | Opacidad 50 % | — | Anillo `pronto` y el mensaje en `pronto` negrita debajo |
| Opción (radio) y chip | `hoja`, anillo `borde`; indicador en `tenue` (7,2:1) | Fondo `rocio`, anillo `pino`, indicador lleno o con check. El chip elegido no va en `pino` macizo: ese lugar es del botón principal. **La figura dice cuántas se eligen** (27/10): un chip de opción única es un radio nativo con indicador redondo y punto; un chip de varias opciones lleva el cuadrado con check | Opacidad 50 % | — | — |
| Etiqueta de estado | Fondo semántico, palabra y figura (● ◐ ○ ✓) en `text-base` | — | — | — | — |
| Página | — | — | — | Sin esqueletos: el contenido llega en menos de un segundo en la demo | Qué pasó y cómo seguir, en `pronto` solo si se perdió algo; un conflicto de versiones (412) va en `atenta` |
| Lista vacía | Ícono en `rocio`, una frase desde la persona y una acción ("Empezar por los pañales") | — | — | — | — |

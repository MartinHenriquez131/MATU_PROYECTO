# MATU · Plan de diseño de la demo

Quién la usa: cuidadoras y familiares cansados, con poco tiempo, desde un teléfono y muchas veces con una mano. Qué tiene que hacer la interfaz: que una persona pueda dejar a la suya con otra y salir tranquila. Lo que hay en ese mundo, y de donde sale la identidad, es la **hoja pegada en el refrigerador** con el día de la persona cuidada, el **PIN dictado por teléfono** y la cuenta de los pañales que quedan.

## Color

Seis tokens de marca en `src/index.css` (`@theme`), con tema claro y oscuro por `prefers-color-scheme`.

| Token | Claro | Oscuro | Rol |
|---|---|---|---|
| `papel` | `#EDF2EE` | `#0D1719` | Fondo general. Verde neblina, no crema |
| `hoja` | `#FFFFFF` | `#152427` | La hoja de la ficha y las superficies |
| `tinta` | `#13252A` | `#E4EEEB` | Texto principal |
| `tenue` | `#485B5F` | `#A9BCB8` | Texto secundario, 7:1 sobre `hoja` |
| `pino` | `#0E5E57` | `#74D2C3` | Acciones y acento. 7,6:1 con texto `papel` |
| `miel` | `#E3A43A` | `#E8B866` | Calidez: el imán de la hoja, el corazón del logo, los puntos de "Su día". Nunca texto sobre claro |

Los semánticos van aparte del acento, cada uno con su fondo: `pronto` (rojo ladrillo), `atenta` (ámbar oscuro) y `ok` (verde hoja). Siempre acompañados de una palabra: Pronto, Atenta, Tranquila, Listo, Falta.

## Tipografía

| Cara | Rol |
|---|---|
| **Atkinson Hyperlegible** | Todo el texto y las cifras. Diseñada para baja visión. Texto base de 17 px (`html { font-size: 106.25% }`) |
| **Bricolage Grotesque** (variable) | Solo titulares grandes, desde 1,5 rem: el saludo, el título de la hoja, "Enlace creado". Peso 800 y tracking negativo. Nunca en botones ni en la barra de título |
| **Atkinson Hyperlegible Mono** | Solo lo que se dicta dígito a dígito: el PIN y el código de retiro |

Escala: 1 · 1,2 · 1,5 · 2 · 3,2 rem. Las cifras de dinero y fechas usan `tabular-nums` en la cara del texto, no monoespaciada.

## Composición

```
 Proyector (≥ 900 px)                                Celular (pantalla completa)
┌────────────────────────────────────────────────┐  ┌──────────────────────────┐
│        Demo con datos simulados                 │  │ Demo con datos …  [Guía] │
│   ╭──────────────────╮      MATU                │  ├──────────────────────────┤
│   │ 14:20   ▄▄▄  ▮▮  │      Panel del presentador│  │ Hola, Carmen             │
│   │ Hola, Carmen      │     ┌───────────────────┐│  │ Cuidado de María         │
│   │ ┌──── (imán) ───┐ │     │ Backend conectado ││  │ ┌──── (imán) ─────────┐  │
│   │ │ Ficha de María│ │     └───────────────────┘│  │ │ Ficha de María      │  │
│   │ │ ───────────── │ │     Ver como: Familia|Relevo|Comercio │ ─────────────────── │  │
│   │ │ 1 de 3 listos │ │     ┌ Escena actual ────┐│  │ │ 1 de 3 listos       │  │
│   │ └───────────────┘ │     │ nota · Real/Simul.││  │ └─────────────────────┘  │
│   │ Se acaban …  6 d  │     └───────────────────┘│  │ Se acaban los pañales    │
│   │ [Inicio][Ficha]…  │     Capa 1 … Capa 3 …    │  │ [Inicio][Ficha][…]       │
│   ╰──────────────────╯      [Texto 200%][Reiniciar]  └──────────────────────────┘
└────────────────────────────────────────────────┘
```

- **Alineación a la izquierda** en todo el contenido de la app. Se centra solo el PIN, porque se lee en voz alta como un bloque.
- Columna única de 390 px dentro del marco. Las acciones van en el pie, al alcance del pulgar.
- El panel del presentador es una columna de 26 rem a la derecha del teléfono, con su propio desplazamiento; la escena activa se mantiene a la vista.

## Principios

1. **La hoja del refrigerador es lo memorable.** La ficha se dibuja como una hoja de papel con renglones y un imán de miel, igual en el inicio, en "Para imprimir" y en lo que ve Rosa. Lo que ve el relevo en el teléfono es la misma hoja que la cuidadora pega en la cocina. Es el único lugar con audacia.
2. **Todo lo demás es sobrio.** Superficies planas con borde fino, sin sombras repetidas; las alertas son bloques tintados sin sombra; las filas de lista llevan una franja de estado a la izquierda.
3. **Movimiento solo como respuesta.** La pantalla entra desde el lado hacia donde se navegó, el aviso aparece después de una acción, y hay un único momento orquestado: al crear el enlace, el ícono se traza y los cuatro dígitos del PIN caen uno a uno. Con `prefers-reduced-motion` todo es inmediato.
4. **El texto habla desde la persona.** Voz activa, en tú, y el botón y su confirmación con el mismo verbo: "Crear cuenta" y "Cuenta creada", "Cortar el enlace" y "Enlace cortado", "Anotar la compra" y "Compra anotada". Los errores dicen qué pasó y cómo seguir, sin disculparse.
5. **El estado siempre con palabra.** Ningún estado se marca solo con color.

## Revisión contra la guía de diseño

Lo que se parecía a un default y se cambió, con el motivo:

| Antes (primer borrador) | Ahora | Por qué |
|---|---|---|
| Encabezado de inicio como bloque turquesa con arcos decorativos | Saludo sobrio sobre el fondo y la ficha como hoja con imán | El bloque de color con decoración es la entrada genérica de cualquier app. La hoja es lo propio de este mundo |
| Bricolage Grotesque en todos los títulos, incluida la barra superior | Solo en titulares de 1,5 rem o más | Dos caras en todas partes diluyen la personalidad. Atkinson en negrita sostiene los títulos chicos |
| Atkinson Mono en fechas, montos y horas | `tabular-nums` en la cara del texto; Mono solo para PIN y código | Monoespaciada en datos pequeños es una marca de diseño generado. El PIN sí se dicta dígito a dígito |
| "CAMPO 2 DE 3" y "FICHA DE RELEVO" en mayúsculas con tracking | Frases normales | Las etiquetas en mayúsculas sobre cada título son plantilla |
| Textos unidos con punto medio ("Cuidado de María · viernes", "Ir a pagar · $69.000") | Frases con preposición o dos líneas | El punto medio como separador es otra marca de plantilla |
| Distintivo "Demo · datos simulados" | "Demo con datos simulados" | Lo mismo |
| Tarjetas iguales con el mismo radio y la misma sombra | Hoja con imán (única con sombra), alertas planas, filas con franja | La jerarquía se ve en la forma, no solo en el texto |
| Bloques que aparecen deslizándose al cambiar de opción | Cambio inmediato | Las entradas deslizadas en cada sección leen como generadas |
| Contenido centrado en "Guardado", "Enlace listo" y "Lista lista" | Alineado a la izquierda | Centrar todo es el default; a la izquierda se lee mejor con texto grande |
| PIN en baldosas con subrayado de color y ondas | Dígitos grandes en Mono, sobrios; el movimiento queda en la caída de los dígitos | La audacia se gasta en la hoja, no en el PIN |
| "Listo para Rosa" | "Enlace creado para Rosa" | El botón dice "Crear enlace": el mismo verbo confirma |

El turquesa del prototipo v1.1 se conserva como continuidad con lo aprobado, pero más profundo y verde (`#0E5E57` en vez de `#0F766E` y `#14B8A6`) y acompañado de miel, para alejarlo del turquesa genérico de las apps de salud.

# MATU · Plan de diseño de la demo web

**Para qué es esta demo:** se proyecta desde un computador el viernes 30 de octubre, frente al profesor guía y público. Tiene que mostrar, en una pantalla ancha, que una persona puede dejar a la suya con otra y salir tranquila, que MATU avisa antes de que se acaben los insumos y que se paga una sola vez y se cobra lo justo.

**Quién la usa de verdad:** Carmen, que cuida a su mamá, está cansada y tiene poco tiempo. Rosa, que la reemplaza el fin de semana y abre un enlace sin cuenta. Y quien atiende el mostrador de Farmacia Los Aromos.

**De dónde sale la identidad:** del mundo de Carmen. La **hoja pegada en el refrigerador** con el día de María, el **PIN dictado por teléfono** y la **boleta** de la farmacia. La hoja es lo memorable: se dibuja igual en el inicio, al editar, en la página de Rosa y para imprimir.

## 1. Color

Seis tokens de marca, en `src/index.css` (`@theme`). El tema sigue al sistema y se puede fijar desde la guía del presentador. Un proyector lava los contrastes, así que el tema claro es el de la presentación y el oscuro se mantiene completo.

| Token | Claro | Oscuro | Rol |
|---|---|---|---|
| `papel` | `#EDF2EE` | `#0D1719` | Fondo general, verde neblina. También la barra lateral: sin bloque de color |
| `hoja` | `#FFFFFF` | `#152427` | La hoja de la ficha, los formularios y las listas |
| `tinta` | `#13252A` | `#E4EEEB` | Texto principal y la barra de la consola de la farmacia |
| `tenue` | `#485B5F` | `#A9BCB8` | Texto secundario. 6,3:1 sobre `papel` |
| `pino` | `#0E5E57` | `#74D2C3` | Acciones, foco y navegación activa. 6,7:1 sobre `papel` |
| `miel` | `#E3A43A` | `#E8B866` | Calidez: el imán, el corazón del logo y los puntos de "Su día". Nunca texto sobre claro |

Los semánticos van aparte del acento, siempre con su fondo y con una palabra: `pronto` (`#A8261B` sobre `#FBE9E6`, 6:1), `atenta` (`#835000` sobre `#FCEFD8`, 5,9:1) y `ok` (`#22663D` sobre `#E1F1E6`, 5,9:1).

La pasarela de pago **no** usa la marca: es otra empresa y se ve en grises neutros (`#F3F4F6`, `#1F2A37`), rotulada "Pasarela de pago simulada".

## 2. Tipografía

| Cara | Rol |
|---|---|
| **Atkinson Hyperlegible** 400 y 700 | Todo el texto, los botones y las cifras. Diseñada para baja visión. Base de 17 px (`html { font-size: 106.25% }`) |
| **Bricolage Grotesque** variable, 800 | Solo titulares desde 1,5 rem: el título de cada página, el nombre en la hoja, "Enlace creado". Tracking negativo |
| **Atkinson Hyperlegible Mono** | Solo lo que se dicta dígito a dígito: el PIN y el código de retiro |

**Escala** (rem, base 17 px): 0,85 · 1 · 1,2 · 1,5 · 2,25 · 3,4. La de 0,85 solo para datos secundarios (horas, notas al pie). El dinero, las fechas y los días usan `tabular-nums` en la cara del texto, nunca monoespaciada. Párrafos de 65 caracteres como máximo.

## 3. Composición

Todo se diseña para 1280 a 1920 px y se ordena con **container queries**, no con media queries. Así, "Texto al 200%" (que aplica `zoom: 2` solo a la app) y el zoom del navegador al 400% en 1280 px (320 px efectivos) hacen que todo fluya a una columna sin desplazamiento horizontal. No hay una experiencia móvil aparte: es el mismo layout que se estrecha.

**Alineación a la izquierda** en todo el contenido. Se centran solo el PIN (se lee en voz alta como un bloque) y la hoja en la página de Rosa (es el único objeto de la página).

### La familia (Carmen): la app principal

```
┌ Demo con datos simulados  [Familia|Relevo|Comercio]  ‹ 6 de 35 Inicio ›   Guía ? ┐
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

- **Barra lateral** sobre `papel`, sin fondo propio: logo, cinco secciones y una pista de estado en cada una ("1 de 3", un punto de Pronto, "En curso"). Bajo 56 rem de ancho se vuelve una fila superior.
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
│ (pino)                        │ Paso 2 de 3                                │
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
┌ (tinta) Farmacia Los Aromos   Pedidos de MATU                       14:20 ┐
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
┌ ● Demo con datos simulados │ Familia  Relevo  Comercio │ ‹ 11 de 35  Relevo: escribe el PIN  Simulado › │ PIN 4821 │  Guía ? ┐
```

- Una **franja superior** delgada, en el flujo del documento: el distintivo, el rol, la escena con anterior y siguiente, una ayuda contextual (el PIN del enlace o "Rodrigo guarda este campo") y el botón de la guía. Con el rol relevo muestra la dirección: `/r#k3J9…` y, después del canje, `/r`.
- Un **cajón lateral** de 24 rem que se abre con el botón o con `?`, sin tapar la app: la app se angosta y se reordena. Tiene el estado del backend, la escena actual con su nota y su etiqueta Real o Simulado, las escenas por capa, "Texto al 200%", el tema, el modo presentación, los atajos y "Reiniciar demo".
- **Modo presentación** (`p`): desaparece la franja y queda solo el distintivo, pequeño, en la esquina inferior izquierda, con un botón para volver a abrir la guía.
- **Atajos:** `?` guía, `]` o `Av Pág` siguiente escena, `[` o `Re Pág` anterior, `p` modo presentación. No actúan dentro de un campo de texto y se pueden apagar desde la guía (WCAG 2.1.4).

## 4. Principios

1. **La hoja del refrigerador es lo memorable.** Hoja de papel con renglones y un imán de miel, la única superficie con sombra de toda la demo. Todo lo demás es plano.
2. **Resumen antes del detalle.** Cada página abre con la frase que importa ("Le alcanza 6 días, hasta el 05/11/2026") y después muestra cómo se llegó a ella.
3. **El estado está en la forma.** Barras de días que terminan en su fecha, una marca a los 7 días, chips cuya figura cambia (● Pronto, ◐ Atenta, ○ Tranquila) y una franja a la izquierda de cada fila. Siempre con palabra, nunca solo con color.
4. **Cifras tabulares y formato chileno.** Pesos enteros (`$69.000`), fechas `DD/MM/AAAA`, hora de 24 horas.
5. **Movimiento solo como respuesta.** El aviso aparece después de una acción, la barra cambia de largo cuando cambia el número, el cajón se desliza al abrirlo. Un solo momento orquestado: al crear el enlace, el ícono se traza y los cuatro dígitos del PIN caen uno a uno. Con `prefers-reduced-motion` todo es inmediato. Las páginas cambian sin deslizarse.
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

Se mantiene, porque funcionó en la versión anterior y no es un default: Atkinson Hyperlegible, la hoja con el imán de miel, el verde `pino` profundo acompañado de miel (en vez del turquesa genérico de las apps de salud), la boleta con el borde cortado y las fuentes locales con `@fontsource`.

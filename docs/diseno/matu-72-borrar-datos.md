# MATU-72 · Borrar los datos de la persona al tiro · Especificación de diseño

**Versión 1.0 · 08/11/2026** · Agente 6, UI/UX. Especifica y no construye.

**Historia:** Carmen puede borrar, desde Grupo familiar, todo lo guardado de María: su ficha con todas sus secciones, sus insumos y las compras anotadas. Se cortan todos sus enlaces de relevo, María sale de MATU y no se puede deshacer. Volver es registrarla de nuevo, en blanco.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` (**sin agregar ninguno**) · las decisiones D1 a D8 de Jorge del 08-11 y los textos aprobados de la revisión previa (borrador de `lenguaje.md` sección 24) · la especificación de MATU-44 (`docs/diseno/matu-44-retirar-autorizacion.md`, secciones 3, 4 y 6), de la que esta reutiliza el bloque, el diálogo y sus reglas · MATU-39 (5.4 y 5.6) · el código de `web/src/familia/` (`Grupo.tsx`, `textosGrupo.ts`, `ui.tsx`, `estado.tsx`, `AppFamilia.tsx`, `Shell.tsx`) y `web/src/compartido/ui/Boton.tsx`.

**Marcas de los textos:** sin marca, el texto aprobado el 08-11 tal cual · **[REGLA]** cómo se arma un texto aprobado · **[A n]** punto abierto para Jorge (sección 0).

---

## 0. Lo que queda abierto para Jorge

Dos puntos de los textos aprobados chocan con una regla de accesibilidad o con la verdad de la pantalla. No los cambio: propongo, y el frontend construye la opción **por defecto** mientras Jorge no diga otra cosa.

| # | Qué pasa | Propuesta | Por defecto |
|---|---|---|---|
| A1 | El nombre accesible aprobado, «Borrar **todos** los datos de `{nombre_pila}`», no contiene el texto visible, «Borrar los datos de `{nombre_pila}`». Rompe WCAG 2.5.3 (etiqueta en el nombre): quien usa control por voz dice lo que ve, «Borrar los datos de María», y el botón no responde. En MATU-44 la regla fue que el `aria-label` **empieza con el texto visible** (3.3) | **Sin `aria-label`.** El texto visible ya lleva el nombre y es único en la página: no hace falta otro. Si Jorge quiere la palabra «todos», que vaya también en el texto visible: «Borrar todos los datos de `{nombre_pila}`» | Sin `aria-label`. Nombre accesible = texto visible |
| A2 | La explicación del bloque dice «**puedes** borrar todo lo guardado de ella». El pagador y el observador no pueden, y debajo leerían «Puede borrarlos quien administra el grupo…». Las dos frases se contradicen | Para esos dos roles, el bloque lleva el título y la línea de quién puede, **sin** la explicación. No agrega texto: omite uno | Omitida para pagador y observador |

---

## 1. Para quién y qué

**Carmen** (admin) o **Rodrigo** (cuidador). María pidió que la borren, o ya no la cuidan con MATU. Lo hacen una vez en la vida, desde el teléfono, quizás en un día malo. Tienen que entender en una lectura **qué se borra ahora, qué se corta, qué queda guardado sin texto y que no vuelve**, y no pueden llegar a borrar por un toque distraído.

**Quien paga u observa** ve que el borrado existe y quién lo puede hacer, sin botón.

**Rosa**, con un enlace, no ve nada nuevo: la próxima vez que mira la ficha recibe el 410 `relevo-revocado` de siempre (lenguaje 7.3). Esta historia no cambia la página del relevo.

**Tres momentos:**
1. **Ver** el bloque «Borrar sus datos» al final de la persona, en Grupo familiar (sección 2).
2. **Confirmar**, con la casilla obligatoria (sección 3).
3. **Salir**: la persona desaparece de la app y la navegación sigue sin ella (sección 4).

---

## 2. El bloque «Borrar sus datos»

**Objetivo, desde Carmen:** saber que puedes borrar todo lo de María y dónde, sin confundirlo con los permisos.

**Jerarquía dentro de la sección de cada persona:**
1. El nombre de la persona (`h2`, ya existe).
2. Sus dos permisos (MATU-44 3.3, sin cambios).
3. **Al final, separado por una línea:** «Borrar sus datos», la explicación y el botón.

**Por qué al final de cada persona y no una vez al final de la página:** «sus datos» y «de ella» se refieren a la persona del `h2`. Con dos personas en el grupo, un bloque suelto al final de la página no diría de quién. Con una sola persona, que es el caso de la demo, el bloque queda al final de Grupo familiar.

**Por qué no es una tarjeta como los permisos:** no es un tercer permiso. Va **sin fondo ni anillo**, sobre `papel`, detrás de una línea `linea` y con más aire que el que separa los permisos. Así se lee como otra cosa, y lo rojo es solo el botón.

**Acción principal en `turquesa` macizo:** ninguna (igual que MATU-44 6.2). El botón es `peligro`, nunca macizo fuera del diálogo.

### 2.1 Esquema a 360 px (admin o cuidador)

```
┌────────────────────────────────────┐
│ María Soto                         │  h2 (MATU-44)
│ ┌────────────────────────────────┐ │
│ │ Permiso para guardar su ficha  │ │  bloque MATU-44, sin cambios
│ │ ◈ Autorizada el 04/11/2026.    │ │
│ │ [ Retirar la autorización ]    │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ Permiso para calcular sus      │ │
│ │ insumos                        │ │
│ │ ◈ Autorizado el 05/11/2026.    │ │
│ │ [ Retirar la autorización ]    │ │
│ └────────────────────────────────┘ │
│                                    │  mt-4 (más gap-4 de la sección)
│ ────────────────────────────────── │  border-t border-linea
│                                    │  pt-6
│ Borrar sus datos                   │  h3 text-lg font-bold
│ Si María o su representante legal  │  p text-base max-w-prose
│ lo pide, o si ya no la cuidan con  │
│ MATU, puedes borrar todo lo        │
│ guardado de ella. No se puede      │
│ deshacer.                          │
│ [ Borrar los datos de María ]      │  Boton peligro, self-start
└────────────────────────────────────┘
│ Ficha  Insumos  Compartir  Grupo   │  barra fija (MATU-44 2.1)
```

**Pagador u observador** (A2, por defecto):

```
│ ────────────────────────────────── │
│ Borrar sus datos                   │  h3 text-lg font-bold
│ Puede borrarlos quien administra   │  p text-base text-tenue
│ el grupo o quien cuida a María     │
│ Soto.                              │  (sin nombre_pila: MATU-44 3.6)
```

### 2.2 Pantalla ancha (1280 y 1920 px)

- El bloque va **debajo** de la grilla de los dos permisos y ocupa el ancho de la sección, no una columna de la grilla. El texto en `max-w-prose`. El botón al ancho de su texto (DISENO.md 5).
- La línea `border-t` cruza el ancho de la sección (`max-w-5xl`, el de la página).
- A 1920 px no cambia nada más: el contenido sigue en `max-w-5xl`, alineado al inicio.

```
┌──────────────┬─────────────────────────────────────────────────────────────┐
│ (M) MATU     │ Cuidas a María Soto                     Tu cuenta   Salir   │
│ Ficha        ├─────────────────────────────────────────────────────────────┤
│ Insumos      │ Grupo familiar                                              │
│ Compartir    │ A quién cuidan en Familia Soto y qué permisos dieron.       │
│ Grupo famil. │                                                             │
│              │ María Soto                                                  │
│              │ ┌──────────────────────────┐  ┌──────────────────────────┐  │
│              │ │ Permiso para guardar su  │  │ Permiso para calcular    │  │
│              │ │ ficha                    │  │ sus insumos              │  │
│              │ │ ◈ Autorizada el 04/11/26 │  │ ◈ Autorizado el 05/11/26 │  │
│              │ │ [Retirar la autorización]│  │ [Retirar la autorización]│  │
│              │ └──────────────────────────┘  └──────────────────────────┘  │
│              │                                                             │
│              │ ─────────────────────────────────────────────────────────── │
│              │ Borrar sus datos                                            │
│              │ Si María o su representante legal lo pide, o si ya no la    │
│              │ cuidan con MATU, puedes borrar todo lo guardado de ella.    │
│              │ No se puede deshacer.                                       │
│              │ [ Borrar los datos de María ]                               │
└──────────────┴─────────────────────────────────────────────────────────────┘
```

### 2.3 Construcción

| Pieza | Construcción | Texto |
|---|---|---|
| Contenedor | `section aria-labelledby={id del h3}`, `mt-4 flex flex-col gap-3 border-t border-linea pt-6`. Sin fondo, sin anillo, sin `rounded`. Dentro de la `section` de la persona, después de la grilla | — |
| Título | `h3 text-lg font-bold break-words` | Borrar sus datos |
| Explicación | `p text-base max-w-prose`. Solo `admin` y `cuidador` (A2) | Si `{nombre_pila}` o su representante legal lo pide, o si ya no la cuidan con MATU, puedes borrar todo lo guardado de ella. No se puede deshacer. |
| Botón | `Boton variante="peligro"`, `self-start`, **sin ícono** (como «Retirar la autorización»). Solo `admin` y `cuidador`. Sin `aria-label` (A1) | Borrar los datos de `{nombre_pila}` |
| Quién puede | `p text-base text-tenue`. Solo `pagador` y `observador`, en lugar del botón | Puede borrarlos quien administra el grupo o quien cuida a `{nombre_pila}`. |

- `{nombre_pila}` sale de `nombrePilaDe(persona)`, como en MATU-44. Para el pagador y el observador es el nombre completo (MATU-44 3.6).
- El bloque se ve **en todo estado de los permisos**: vigentes, por renovar, retirados o borrados. Borrar es justamente lo que se pide cuando ya no la cuidan.
- Al tocar el botón se abre la confirmación (sección 3). El botón guarda su `id` (`borrar-{persona_id}`) para devolverle el foco al cancelar.

---

## 3. La confirmación

**Objetivo, desde Carmen:** entender en una lectura que esto no vuelve, y elegir con calma entre borrar y no borrar.

**Jerarquía:**
1. La pregunta, con el nombre.
2. «Esto no se puede deshacer.»
3. Lo que pasa ahora (ficha, enlaces, María sale de MATU).
4. Lo que queda guardado sin texto y lo que ya salió de MATU, en tono secundario.
5. La casilla, «Borrar todo» y «No borrar».

Una sola confirmación, con una casilla. Sin contraseña, sin motivo y sin escribir el nombre (D6).

### 3.1 Construcción

Es el diálogo de MATU-44 (4.1) con cuatro cambios: **párrafos en vez de lista**, **pie fijo** con la casilla y los botones, **foco inicial en «No borrar»** y **«Borrar todo» deshabilitado hasta marcar la casilla**.

- `<dialog>` modal nativo con `showModal()`, `aria-labelledby` (el `h2`) y `aria-describedby` (el contenedor de los párrafos).
- Caja: las mismas clases que el de MATU-44, `m-auto w-[calc(100%-2rem)] angosto:w-[calc(100%-1rem)] max-w-lg max-h-[calc(100dvh-2rem)] rounded-2xl bg-hoja text-tinta backdrop:bg-tinta/40`, **más** `flex flex-col` y **sin** `overflow-y-auto` ni `p-6` en la caja (pasan a las dos partes). Sin animación.
- **Cuerpo**, la parte que se desplaza: `div min-h-0 flex-1 overflow-y-auto px-6 pt-6 pb-4 angosto:px-2 angosto:pt-4`, con el título y los párrafos.
- **Pie**, fijo abajo: `div flex flex-col gap-3 border-t border-linea px-6 pt-4 pb-6 angosto:px-2 angosto:pb-4`, con la casilla, la región de error y los botones.
- **En modo angosto el pie deja de ser fijo:** `angosto:block` en la caja y `angosto:overflow-y-auto` en la caja, `angosto:overflow-visible` en el cuerpo. A 320 px con el texto al 200 % la ventana mide unos 160 × 280 px efectivos, y la casilla con los dos botones apilados la llenarían entera, sin dejar ver la pregunta. Ahí se desplaza todo junto, como el diálogo de MATU-44.
- Título: `h2 tabIndex={-1} text-xl font-bold break-words outline-none`. No recibe el foco inicial, pero queda enfocable para devolverlo ahí si hace falta.
- Párrafos: `div flex flex-col gap-3 text-base leading-relaxed max-w-prose`, un `p` por párrafo:
  - El primero, «Esto no se puede deshacer.», en **`font-bold`**. Es lo único en negrita.
  - Del segundo al cuarto (lo que pasa ahora), en `tinta`.
  - Del quinto al séptimo (lo que se guarda y lo que ya salió), en **`text-tenue`** (7,2:1 sobre `hoja` claro, 8,1:1 oscuro). Sigue siendo legible y relevante, pero se lee después.
- Casilla: `label flex min-h-12 cursor-pointer items-center gap-3 font-bold` con `input type="checkbox" className="size-5 shrink-0 accent-turquesa"`, el mismo trato que la casilla del aviso del cuidador de hecho (`AvisoCuidadorDeHecho`, `ui.tsx`). Toda la fila es el área táctil. Sin marcar al abrir, siempre.
- Región de error: `div role="alert" className="empty:hidden"`, montada vacía con el diálogo (MATU-44 4.1), dentro del pie, entre la casilla y los botones: el error queda a la vista sin desplazar.
- Botones con `Acciones` (`flex-wrap`): primero «Borrar todo», después «No borrar».
  - **«Borrar todo»:** `Boton variante="peligroPrincipal"` (`bg-pronto text-papel`), el único macizo del diálogo.
  - **Mientras la casilla no está marcada**, va con `aria-disabled="true"` (no `disabled`: conserva el foco y se anuncia, como el de Entrar en `Boton.tsx`) y **cambia de forma, no solo de color:** `aria-disabled:bg-hoja aria-disabled:text-tenue aria-disabled:ring-2 aria-disabled:ring-inset aria-disabled:ring-borde aria-disabled:cursor-not-allowed`, sin `hover:brightness`. Contorno neutro y texto `tenue` (7,2:1 sobre `hoja`, legible) en vez de macizo rojo. **Nada de `opacity-60`:** sobre `pronto` daría texto de menos de 3:1. Tocarlo así no hace nada.
  - Al marcar la casilla pasa a macizo `pronto`, en el mismo lugar y con el mismo ancho.
  - **«No borrar»:** de texto, igual que «No retirar» (`inline-flex min-h-12 items-center px-2 font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa`).

**Recomendación para el frontend:** el estado deshabilitado de `peligroPrincipal` cabe en la variante misma (`aria-disabled:` en `VARIANTES`), así no se repite en el diálogo. Es solo `hoja`, `tenue` y `borde`: ningún token nuevo.

### 3.2 Esquema a 360 px

```
┌────────────────────────────────────┐
│ ¿Borrar todo lo guardado de María? │  h2 text-xl font-bold
│                                    │
│ Esto no se puede deshacer.         │  p font-bold
│                                    │
│ Borramos ahora su ficha, con todas │  p text-base (tinta)
│ sus secciones, y los insumos y las │
│ compras anotadas. Nadie los podrá  │
│ recuperar, tampoco el equipo de    │
│ MATU.                              │
│                                    │
│ Se cortan ahora todos sus enlaces  │  p
│ de relevo. Hoy abren 2. Quien      │
│ tenga la ficha abierta deja de     │
│ verla cuando vuelva a mirarla. No  │
│ recibe aviso.                      │
│                                    │
│ María sale de MATU. Si después     │  p
│ quieren volver a usar MATU para    │
│ cuidarla, hay que registrarla de   │
│ nuevo, y todo empieza en blanco.   │
│                                    │
│ Guardamos, sin nada de lo escrito, │  p text-tenue
│ el registro de las autorizaciones, │       ↕ el cuerpo se desplaza
│ … (siguen dos párrafos tenue)      │
├────────────────────────────────────┤  border-t border-linea, pie fijo
│ ☐ Entiendo que esto no se puede    │  label min-h-12 font-bold
│   deshacer.                        │
│ [ Borrar todo ]  No borrar         │  aria-disabled: contorno borde,
└────────────────────────────────────┘  texto tenue · No borrar con foco
```

**Con la casilla marcada:**

```
├────────────────────────────────────┤
│ ☑ Entiendo que esto no se puede    │
│   deshacer.                        │
│ [█ Borrar todo █]  No borrar       │  bg-pronto text-papel
└────────────────────────────────────┘
```

### 3.3 Esquema a 320 px con el texto al 200 % (160 px efectivos, modo `angosto`)

```
┌──────────────────┐
│ ¿Borrar todo lo  │  h2, se ve primero (scrollTop 0)
│ guardado de      │
│ María?           │
│                  │
│ Esto no se puede │  font-bold
│ deshacer.        │
│                  │
│ Borramos ahora   │
│ su ficha, con    │
│ …                │   ↕ toda la caja se desplaza,
│ ──────────────── │     el pie va al final del flujo
│ ☐ Entiendo que   │
│   esto no se     │
│   puede          │
│   deshacer.      │
│ [ Borrar todo ]  │  los botones bajan de renglón
│ No borrar        │  (flex-wrap)
└──────────────────┘
```

- Ningún desplazamiento horizontal: títulos con `break-words`, botones con el `[overflow-wrap:anywhere]` de `Boton`, `px-2`.
- El foco inicial en «No borrar» se pone con `focus({ preventScroll: true })` y la caja queda en `scrollTop = 0`, para que lo primero que se vea sea la pregunta y no el pie. El lector de pantalla igual dice el nombre y la descripción del diálogo (`aria-labelledby` y `aria-describedby`). En cuanto Carmen se mueve con el teclado, el navegador desplaza hasta el control.

### 3.4 Pantalla ancha

El mismo diálogo, centrado, de 32 rem como máximo (`max-w-lg`). A 1280 px y a 1920 px suele caber entero sin desplazarse. Los dos botones en una fila, al ancho de su texto. El velo `tinta/40` cubre la barra lateral.

### 3.5 Textos que se arman

| Párrafo | Texto | Regla |
|---|---|---|
| Título | ¿Borrar todo lo guardado de `{nombre_pila}`? | — |
| 1 | Esto no se puede deshacer. | `font-bold` |
| 2 | Borramos ahora su ficha, con todas sus secciones, y los insumos y las compras anotadas. Nadie los podrá recuperar, tampoco el equipo de MATU. | — |
| 3 | Se cortan ahora todos sus enlaces de relevo. Hoy abren `{n}`. Quien tenga la ficha abierta deja de verla cuando vuelva a mirarla. No recibe aviso. | **[REGLA]** «Hoy abren `{n}`.» con 1: «Hoy abre 1.», con 0: «Hoy ningún enlace abre.» Ver abajo |
| 4 | `{nombre_pila}` sale de MATU. Si después quieren volver a usar MATU para cuidarla, hay que registrarla de nuevo, y todo empieza en blanco. | — |
| 5 | Guardamos, sin nada de lo escrito, el registro de las autorizaciones, de los enlaces y de quién abrió la ficha, por los plazos de la política de privacidad. | `text-tenue` |
| 6 | Lo borrado sigue en las copias de respaldo hasta que vencen, y nadie las usa para ver datos. | `text-tenue` |
| 7 | Una lista que ya imprimiste o compartiste no se borra: quedó fuera de MATU. | `text-tenue` |
| Casilla | Entiendo que esto no se puede deshacer. | — |
| Botones | Borrar todo · No borrar | — |

**[REGLA] De dónde sale `{n}` en el párrafo 3** (es la frase «Hoy abren» de MATU-44 4.3, con el conteo que Grupo familiar ya pide al abrir, 2.2 de MATU-44):

| Estado de la ficha | Frase |
|---|---|
| `vigente`, con el conteo | «Hoy abren `{n}`.» (1: «Hoy abre 1.» · 0: «Hoy ningún enlace abre.») |
| `vigente`, si el conteo falló | Se omite la frase (regla aprobada) |
| `revision_vencida` | «Hoy ningún enlace abre.» Están en pausa: no abren (decisión 33), y el texto aprobado no tiene la variante «en pausa» |
| `retirada` o `borrada` | «Hoy ningún enlace abre.» El retiro ya los cortó todos (MATU-44, decisión 124) |

`hoyAbren` ya existe en `textosGrupo.ts` con esas tres formas: se reutiliza.

### 3.6 Estados de la confirmación

| Estado | Qué se ve | Foco |
|---|---|---|
| Abierta | El esquema de 3.2. Casilla sin marcar, «Borrar todo» con `aria-disabled` | En **«No borrar»**, la opción segura. El orden del DOM es: título, párrafos, casilla, error, «Borrar todo», «No borrar». Desde «No borrar», `Shift+Tab` va a «Borrar todo» y otra vez a la casilla. El `h2` no está en el orden de `Tab` (`tabIndex={-1}`) |
| Casilla marcada | «Borrar todo» macizo `pronto`. Si se desmarca, vuelve al contorno neutro | En la casilla |
| «Borrar todo» sin la casilla | No pasa nada. No se envía | Se queda en el botón |
| En curso | «Borrar todo» dice «Borrando…», con el mismo ancho y `aria-busy` (`Boton` con `ocupado`). La casilla, «No borrar» y `Esc` no hacen nada: la casilla con `aria-disabled` (y `onChange` ignorado), «No borrar» con `aria-disabled`, `onCancel` con `preventDefault`. **Y el segundo `Esc`:** si el diálogo recibe `close` con la petición en curso, se vuelve a abrir con `showModal()` y el foco vuelve al botón (MATU-44 4.4, el mismo código) | Se queda en el botón |
| Hecho (200) | Se cierra el diálogo y la persona sale de la app (sección 4) | Sección 4 |
| 409 `ya-borrada` | Se cierra el diálogo y la persona sale igual (sección 4), con la nota del 409 | Sección 4 |
| Red o 5xx | En la región del pie, `MensajeError`: «No pudimos borrar los datos. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.» El botón vuelve a «Borrar todo», **la casilla sigue marcada** (no hay que volver a decidir). Es verdad que todo sigue igual: el borrado es una sola transacción (C1) | Se queda en el botón |
| 404 (cambió el rol, otro grupo o ya no está) | Se cierra el diálogo y Grupo familiar vuelve a cargar (MATU-44 3.7), sin decir por qué | En el `h1` |
| 401 | El cliente de MATU-39 | — |
| «No borrar» o `Esc` | Se cierra sin pedir nada | Vuelve al botón «Borrar los datos de `{nombre_pila}`» que la abrió |

**Sin interfaz optimista** (CLAUDE.md, agente 3, punto 4): nada cambia antes de la respuesta.

---

## 4. Después del borrado: la persona sale de la app

**Regla:** al 200 (o al 409), la app **saca de la memoria todo lo de esa persona** (C5) y sigue como si nunca hubiera estado. Sin pedir confirmación otra vez ni dejar un rastro visible de ella, salvo la nota de una sola vez.

### 4.1 Qué se saca de la memoria (`estado.tsx`)

En una sola llamada a `fijar`, antes de navegar:
- `personas`: sin esa persona.
- Si era la elegida: `personaId` pasa a la primera que queda (o `null`), y `ficha: null`, `autorizacion: null`.
- `reautorizar: null` si era de ella.
- `borrador`: vuelve a `BORRADOR_VACIO` si tiene su nombre. Si no, `/empezar/persona` podría aparecer con «María» escrito, y «todo empieza en blanco» sería falso.
- En Grupo familiar: sus `DatosPersona` (vistas y conteo de enlaces) y sus `avisos`.
- Cualquier pista de la barra o caché de insumos o ficha que la nombre.

El nombre de pila solo sobrevive dentro del texto de la nota de 4.3, que se borra al mostrarse (`AvisoDeLlegada`).

### 4.2 A dónde vuelve la navegación

| Caso | Adónde | Por qué |
|---|---|---|
| Quedan otras personas en el grupo | Se queda en **`/grupo`**. La sección de la persona borrada desaparece. El encabezado «Cuidas a…» muestra la que quedó elegida | Carmen sigue viendo los permisos de quien sí cuida |
| No queda nadie (el caso de la demo) | **`/empezar/persona`**, con `reemplazar: true`. Es lo que ya hace la regla de MATU-39 5.4 para `admin` y `cuidador` sin personas, así que el frontend no fuerza nada: solo deja que la regla actúe | Es el estado de un grupo sin personas. Registrar a alguien es la única acción posible, y el párrafo 4 ya lo anunció |

- **Nunca** a `/ficha`, `/insumos` ni `/compartir` de la persona borrada.
- `<title>` sin nombres, como siempre.
- **Pagador y observador conectados al mismo tiempo:** nada nuevo. Su próxima petición de esa persona responde 404, y aplica MATU-44 3.7 y MATU-39 5.6.

### 4.3 La nota de una sola vez

Se entrega con `fijar({ aviso })` y la muestra `AvisoDeLlegada`, el mismo mecanismo de MATU-44 5.3. **El frontend agrega `AvisoDeLlegada` arriba del paso «Persona» de `/empezar/persona`**, debajo de su encabezado, para el caso sin personas.

| Cuándo | Nota | Texto |
|---|---|---|
| 200 | `tono="ok"` (`CircleCheck`), `rol="status"` | Borramos los datos de `{nombre_pila}`. Cortamos `{n}` enlaces. **[REGLA]** 1: «Cortamos 1 enlace.» · 0: «No había enlaces que abrieran.» |
| 409 `ya-borrada` | `tono="rocio"` (`Info`), `rol="status"` | Otra persona de tu grupo ya borró los datos de `{nombre_pila}`. |

- `{n}` es el contador de enlaces cortados **de la respuesta del borrado** (el campo que fije el contrato de MATU-72), **no** el conteo de la confirmación: la API corta también los bloqueados y los en pausa (decisión C9), así que puede ser mayor que «Hoy abren `{n}`». Es la misma regla de MATU-44 3.5.
- **Foco:** si cambia de ruta (`/empezar/persona`), al `h1` por la regla de ruta, y la nota se anuncia por su `rol`. Si se queda en `/grupo`, la ruta no cambia, así que el foco va **a la nota** (`tabIndex={-1}`, `outline-none`, como las de MATU-44 3.5): el botón que abrió el diálogo ya no existe y el foco no puede quedar en el `body`.
- La nota va donde va hoy `AvisoDeLlegada` en Grupo familiar: debajo de la bajada, antes de las personas.

### 4.4 Esquema a 360 px, sin personas

```
┌────────────────────────────────────┐
│ (marco del alta, MATU-39)          │
│ ¿A quién cuidas?   ← h1 de siempre │  foco por la regla de ruta
│ ┌────────────────────────────────┐ │
│ │ ✓ Borramos los datos de María. │ │  Nota ok, rol status
│ │   Cortamos 2 enlaces.          │ │
│ └────────────────────────────────┘ │
│ (formulario de la persona, vacío)  │  borrador vacío
└────────────────────────────────────┘
```

(El título y el formulario son los que ya tiene el paso; aquí solo se agrega la nota arriba.)

---

## 5. Accesibilidad visual, temas y reflujo

- **Áreas táctiles:** «Borrar los datos de…» y «Borrar todo» con `Boton` (`min-h-12`, 51 px). «No borrar» con `min-h-12`. La casilla: la fila completa del `label`, `min-h-12`. Ningún control bajo 48 × 48 px.
- **Foco:** el botón del bloque usa `focus-visible:outline-pronto` (variante `peligro`, ya en `Boton`). «Borrar todo», «No borrar» y la casilla usan el foco base: contorno de 3 px `turquesa` con 2 px de separación, sobre `hoja`. El `h2` y las notas que reciben el foco no muestran contorno: no son controles.
- **Estado nunca solo por color:**
  - Lo destructivo lo dice el verbo: «Borrar» en el título del bloque, en el botón, en la pregunta y en «Borrar todo». Lo irreversible lo dice, en negrita, «Esto no se puede deshacer.» y la casilla.
  - Deshabilitado y habilitado cambian de **forma**: contorno neutro con texto `tenue`, o macizo `pronto`. En escala de grises se distinguen.
  - Las notas llevan `CircleCheck` o `Info`, y el error `CircleAlert`.
- **Contraste, a medir en la revisión** (por cálculo con los valores de DISENO.md):
  - `pronto` sobre `hoja` (botón del bloque): 6,1:1 o más en claro; en oscuro `#FFA395` sobre `#152427`, cerca de 9:1.
  - `papel` sobre `pronto` («Borrar todo»): 6,1:1 o más en claro, cerca de 10:1 en oscuro.
  - Deshabilitado: `tenue` sobre `hoja` 7,2:1 claro y 8,1:1 oscuro; el contorno `borde` 3,5:1 claro y 4:1 oscuro.
  - Párrafos `tenue` sobre `hoja`: 7,2:1 y 8,1:1.
  - La línea `linea` que separa el bloque es decorativa (1,3:1): no identifica un control. Lo que separa de verdad es el `h3`.
  - La casilla nativa con `accent-turquesa` y `color-scheme` de cada tema: su borde sin marcar debe medir 3:1 o más sobre `hoja` en los dos temas. A verificar en la captura.
- **Texto al 200 % a 320 px:** 3.3. El bloque sin rellenos laterales propios (no es tarjeta), así que no pierde ancho.
- **Temas claro y oscuro:** solo tokens. El fondo del diálogo es `hoja` y el velo `tinta/40` en los dos. El tema claro para el proyector.
- **`prefers-reduced-motion`:** el diálogo no tiene animación, y la salida de la persona es inmediata (sin transición de la sección que desaparece).
- **Proyector:** ningún texto relevante bajo `text-base` (17 px).

### 5.1 Anuncios

| Momento | Cómo se anuncia |
|---|---|
| Abrir la confirmación | El lector dice el nombre del diálogo (el `h2`) y su descripción (los párrafos), y después «No borrar, botón» |
| Marcar la casilla | El cambio de estado nativo de la casilla. «Borrar todo» deja de anunciarse como no disponible |
| En curso | `aria-busy` y «Borrando…» en el botón con el foco. Sin anuncio aparte |
| Error | La región `role="alert"` del pie, montada vacía con el diálogo |
| Hecho y 409 | La `Nota` con `rol="status"`, montada después de cerrar el diálogo (cuando lo de fuera ya no está inerte) |

### 5.2 Elementos en `turquesa` macizo

| Pantalla | Cantidad |
|---|---|
| Grupo familiar, con el bloque, cualquier rol | 0 |
| Confirmación de borrar | 0 (el único macizo es «Borrar todo», en `pronto`, y solo con la casilla marcada) |

---

## 6. El contrato que usa

La ruta y el esquema los define el backend en `docs/api/` en esta misma rama. La pantalla necesita:

| Para qué | Qué necesita |
|---|---|
| Borrar | Una petición sin cuerpo para la persona, con `X-Grupo-Id`. 200 con el **número de enlaces cortados** (C4: los contadores van en la respuesta) |
| Ya borrada | 409 con `type` que termina en `ya-borrada` (C3) |
| Otro rol, otro grupo, inexistente | 404 (D1) |
| El conteo de «Hoy abren `{n}`» | El que Grupo familiar ya pide (`GET …/accesos-relevo?estado=vigente&limite=100`, MATU-44 2.2). Ninguna petición nueva al abrir el diálogo |
| Saber quién puede | El `rol` del grupo, como hoy (`puedeEditar`) |

Si el contrato nombra el contador distinto, manda el contrato. La pantalla no necesita ningún otro dato.

---

## 7. Lo que el frontend no debe hacer

- **No guardar** nada de la persona borrada en memoria, `localStorage`, `sessionStorage` ni la URL (4.1).
- **No ser optimista:** la persona sale solo con la respuesta.
- **No usar** el conteo de la confirmación en la nota de hecho.
- **No mostrar** `title`, `detail` ni `mensaje` de la API (lenguaje 8). El texto se elige por `type`.
- **No agregar** contraseña, motivo, escribir el nombre ni una segunda confirmación (D6).
- **No preseleccionar** la casilla, ni recordarla entre aperturas del diálogo.
- **No poner** el foco inicial en «Borrar todo» ni en la casilla.
- **No usar** `disabled` ni `opacity-60` en «Borrar todo»: `aria-disabled` con contorno neutro (3.1).
- **No poner** el botón del bloque macizo, ni el bloque dentro de una tarjeta roja o con fondo `pronto-fondo`. Lo rojo es solo el botón.
- **No usar** las palabras «eliminar», «borrado», «suprimir», «revocar» ni «consentimiento» en la interfaz. Solo los textos de esta especificación.
- **No escribir** colores, tamaños ni sombras a mano. Ningún token nuevo. Íconos solo de lucide, y los que ya usan `Nota` y `MensajeError` (`CircleCheck`, `Info`, `CircleAlert`). El bloque y los botones van sin ícono.
- **No tocar** los bloques de permisos de MATU-44 ni su diálogo.

---

## 8. Criterios visuales verificables

1. En Grupo familiar, el bloque «Borrar sus datos» es lo último de la sección de cada persona, debajo de una línea `linea`, sin fondo ni anillo, y no está dentro de la grilla de los permisos.
2. El único elemento en `pronto` del bloque es su botón, de contorno (`peligro`), no macizo.
3. Pagador y observador ven el título y «Puede borrarlos quien…», sin botón ni la frase «puedes borrar».
4. Al abrir la confirmación, el foco está en «No borrar» y la pregunta se ve completa arriba, a 360 px y a 320 px con el texto al 200 %.
5. Con la casilla sin marcar, «Borrar todo» es de contorno neutro con texto `tenue`, y tocarlo no hace nada. Al marcarla es macizo `pronto`. En escala de grises se distinguen.
6. A 360 px y en pantalla ancha, la casilla y los botones quedan fijos abajo mientras los párrafos se desplazan. A 320 px con el texto al 200 % se desplaza todo, sin desplazamiento horizontal.
7. «Esto no se puede deshacer.» es el único párrafo en negrita, y los tres últimos van en `tenue`.
8. Mientras dice «Borrando…», ni «No borrar», ni la casilla, ni uno o dos `Esc` cierran o cambian el diálogo, y el botón no cambia de ancho.
9. Con un error de red, el mensaje aparece en el pie, a la vista, y la casilla sigue marcada.
10. Después de borrar a la única persona, la app está en `/empezar/persona` con «Borramos los datos de María…» arriba y el formulario vacío. Con otra persona en el grupo, queda en `/grupo` sin la sección borrada y con el foco en la nota.
11. En ninguna pantalla posterior aparece el nombre de la persona borrada, salvo esa nota.
12. Ningún texto relevante bajo 17 px, en los dos temas.

---

## 9. Cómo la voy a revisar

Mirándola funcionar, con datos sintéticos (María, Carmen, Rodrigo y Rosa). Capturas a 360, 1280 y 1920 px, en tema claro y oscuro, y a 320 px con el texto al 200 %, de:
- `/grupo` con el bloque, como admin, como pagador y como observador, con los permisos vigentes y retirados, y con dos personas
- la confirmación con 0, 1 y 2 enlaces, sin conteo y con la ficha retirada; sin marcar y marcada
- la confirmación en curso, con error de red
- después del 200 con una persona (`/empezar/persona`) y con dos (`/grupo`), y después del 409

Con el teclado: el foco al abrir, con la casilla, al cancelar, en curso con `Esc` dos veces y después del borrado. Con un lector de pantalla: que la nota de hecho se lea una sola vez.

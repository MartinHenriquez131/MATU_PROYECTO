# MATU-55 · Dónde entraste, últimos ingresos y avisos · Especificación de diseño

**Versión 1.3 · 12-11-2026 · agente 6 UI/UX.** La 1.1 se escribió antes de construir. La 1.2 y la 1.3 salen de las dos revisiones visuales de lo construido.

**Qué cambia de la 1.2 a la 1.3** (segunda revisión, commit bd321d7):
- la ayuda del estado B pasa al texto aprobado en el cierre del analista (3.4 y 8);
- la opacidad de la casilla que espera no se aplica mientras tiene el foco: `aria-disabled:not-focus-visible:opacity-60` (3.3). Con `opacity-60` sobre el `input`, el contorno de foco también queda al 60 % y en el tema claro baja a 2,82:1, bajo el 3:1 que pide el foco.

**Qué cambia de la 1.1 a la 1.2.** Las cinco diferencias que señaló el frontend se aceptan, y dos hallazgos de la revisión cambian la especificación:
- «Tu cuenta» pide `GET /v1/dispositivos` para saber la clase del dispositivo actual (E1, 3.5). Si falla, dice «navegador»;
- los ingresos traen `clase` en `dispositivo`, y «(este {…})» la usa (2.5 y C7);
- al desactivar, primero va el `DELETE` y después se borra la suscripción del navegador (3.4);
- `CELULAR.enUnMinuto` en «Confirma tu celular» queda para MATU-93: esa pantalla no es de esta historia;
- los íconos de la PWA usan el corazón del favicon (3.6);
- **hallazgo:** mientras se guarda una casilla, las dos van con `aria-disabled`, no con `disabled`, y el foco se devuelve después del render (3.3 y 3.4). Con `disabled` el navegador saca el foco al `body`;
- **hallazgo:** la nota del estado E lleva `iconoEnLinea`, porque a 320 px con el texto al 200 % se salía 22 px (3.4).

**Qué cambia de la 0.1 a la 1.1.** Entran las decisiones del orquestador, por delegación de Jorge (sección 0), y el contrato propuesto `docs/api/propuestos/donde-entraste.openapi.yaml`:
- `GET /v1/yo/ingresos` responde `eventos[]` y `hay_mas`;
- cada evento trae `tipo`, `ocurrido_en` y `dispositivo: {nombre, actual} | null`;
- `GET /v1/dispositivos/actual/push` responde `clave_publica`, `registrado` y `envio_simulado`;
- `clase` llega en `DispositivoVista`.

**Las bases son estas:**
- las decisiones de Jorge del 12-11, D1 a D8, en `docs/legal/revision-previa-matu-55.md` del repositorio MATU;
- `Demo/DISENO.md`, con la regla de MATU-93: **ningún texto bajo 17 px, salvo el rótulo de la barra inferior**;
- `docs/lenguaje.md`, secciones 13.3, 19, 20, 26 y 29;
- las especificaciones de MATU-45 (Quién la vio: líneas agrupadas por día), MATU-44 (el diálogo de confirmación) y MATU-57 (Tu cuenta).

**Sin tokens nuevos.** Todo se arma con `Pagina`, `Volver`, `Nota`, `Etiqueta`, `Boton`, `MensajeError`, `Acciones` y el diálogo de `DialogoPedido`, que conviene generalizar (ver 2.6).

**Cómo se leen las marcas de los textos:**
- **[LENGUAJE 13.3]** y las demás: el texto ya está aprobado en esa sección de `lenguaje.md`.
- **[ANALISTA]**: el analista lo propuso en la sección 5 de la revisión previa, pero todavía no está en `lenguaje.md`. Jorge lo aprueba con la pantalla.
- **[NUEVO]**: no está en ninguna de las dos partes.
- **[AJUSTE]**: cambia un texto ya aprobado. Se explica por qué.
- **[ANALISTA-CIERRE]**: el analista lo revisa en el cierre antes de copiarlo a `lenguaje.md`. Son dos textos: la ayuda del estado B (3.4), que repite la línea de la política 0.14, y «Si no lo pediste tú, no compartas el código con nadie.» (2.5).

> **Regla de 17 px (MATU-93).** Ningún texto de estas pantallas va bajo `text-base`. **Los rótulos del `dl` de `Cuenta.tsx` («Tu correo», «Tu celular» y «Política de privacidad») pasan de `text-sm` a `text-base`.** El worktree `wt55c` sale de la rama de MATU-62 y todavía no tiene MATU-93. Si MATU-93 se fusiona antes, `web/pruebas/textoMinimo17.test.ts` lo verifica. Si se fusiona después, MATU-55 ya tiene que cumplirlo.

---

## 0. Decisiones (del orquestador, por delegación de Jorge, 12-11)

| # | Decisión |
|---|---|
| E1 | **Aceptada.** El sustantivo sale de `clase`, que viene en `DispositivoVista`: `telefono` da «teléfono», `computador` da «computador» y `otro` da «navegador». Se usa en «Este {…}», en «(este {…})» y en «Cerrar en ese {…}». **(1.2)** Las líneas de ingresos traen `clase` en `dispositivo`, y «(este {…})» usa esa: es la misma que la de la fila actual, porque solo se agrega con `actual: true`. En «Tu cuenta», la clase sale de la fila con `actual: true` de `GET /v1/dispositivos`. Si esa lectura falla, el sustantivo es «navegador», que vale para cualquiera, y mientras no llega el `h3` del bloque no se muestra |
| E2 | **Aceptada.** «Dónde entraste» es una página propia, `/cuenta/donde-entraste`, con los teléfonos y los últimos ingresos. Los avisos van en «Tu cuenta», en un solo bloque con las preferencias y el teléfono actual |
| E3 | **Aceptada.** Cada casilla se guarda al marcarla, sin interfaz optimista: queda en «Guardando…» hasta el 200 |
| E4 | **Aceptada.** Al desmarcar «En tus teléfonos», el bloque del teléfono se oculta y la inscripción no se borra, porque no se envía nada. Con la casilla marcada y el teléfono activado, «Desactivar en este teléfono» sigue disponible en el bloque |
| E5 | **«Cambiar mi contraseña» se quita.** Con la entrada abierta no hay cómo cambiar la contraseña (sección 7, C6). La ayuda dice cómo hacerlo, en texto (2.5) |

---

## 1. Para quién y qué

- **Carmen** perdió el teléfono, o le prestó el computador a su cuñada. Quiere saber en una sola mirada dónde quedó abierta su cuenta, y cerrarla con un toque, sin escribir la contraseña (D8).
- **Ve sus propios ingresos**, nunca los de otra persona. Es su derecho de acceso (P1). La pantalla habla de lo que **ella** hizo («Entraste», «Cambiaste tu contraseña»). Nunca dice «sesión», «evento», «registro», «auditoría», «IP» ni «token» (`lenguaje.md` 13.3 y 19).
- **Los avisos** se eligen una vez, para todos sus grupos. La pantalla nunca da a entender que en el piloto los avisos llegan.

Las rutas son tres:
- `/cuenta`, que existe y cambia en la sección 3;
- `/cuenta/donde-entraste`, nueva **[PROPUESTO]**;
- el bloque de avisos, que vive dentro de `/cuenta`.

`<title>`: «Dónde entraste · MATU» y «Tu cuenta · MATU», con el patrón de las demás rutas.

---

## 2. «Dónde entraste» (`/cuenta/donde-entraste`)

**Objetivo, desde Carmen:** «Quiero ver dónde quedó abierta mi cuenta y cerrarla en el teléfono que ya no tengo.»

### 2.1 Jerarquía

1. **Primero:** el `h1` «Dónde entraste» **[LENGUAJE 13.3]** y su bajada, que dice que no se guarda la ubicación.
2. **Segundo:** «Tus teléfonos y computadores», con el actual arriba, cada uno con la última vez y su acción.
3. **Tercero:** «Últimos ingresos», la historia de 90 días, y la ayuda para cuando Carmen no reconoce un ingreso.

**Acción principal:** ninguna en macizo, porque es una pantalla de lectura, como Quién la vio. «Cerrar en ese teléfono» es `peligro`, y el macizo `pronto` vive solo dentro del diálogo. **No hay ningún `turquesa` macizo en la página.**

### 2.2 Esquema a 360 px

```
┌────────────────────────────────────┐
│ (cabecera de la app)               │
├────────────────────────────────────┤
│ ‹ Volver a tu cuenta               │  Volver, 48 px
│                                    │
│ Dónde entraste                     │  h1 titular text-3xl
│ Los teléfonos y computadores donde │  bajada text-base text-tenue
│ entraste a MATU. No guardamos tu   │
│ ubicación ni tu dirección IP.      │
│                                    │
│ Tus teléfonos y computadores       │  h2 text-xl font-bold
│ ┌────────────────────────────────┐ │  ul bg-hoja rounded-xl ring-1 ring-linea
│ │ ▯  Chrome en Android           │ │  ícono Smartphone + nombre font-bold
│ │    (◉ Este teléfono)           │ │  Etiqueta activo con CircleDot
│ │    Última vez: hoy a las 10:14 │ │  text-base text-tenue
│ │    Salir                       │ │  Boton texto
│ ├────────────────────────────────┤ │  divide-y divide-linea
│ │ ⌨  Chrome en Windows           │ │  ícono Laptop
│ │    Última vez: 09/11/2026      │ │
│ │    a las 18:40                 │ │
│ │    [ Cerrar en ese computador ]│ │  Boton peligro, ancho natural
│ └────────────────────────────────┘ │
│                                    │
│ Últimos ingresos                   │  h2 text-xl font-bold
│ Los de los últimos 90 días, hasta  │  text-base text-tenue
│ 20.                                │
│                                    │
│ Hoy                                │  h3 text-lg font-bold
│ (→] Entraste                       │  ícono en círculo size-9 + frase font-bold
│     a las 10:14 · Chrome en Android│  text-base text-tenue
│     (este teléfono)                │
│ ───────────────────────────────────│
│ (!) Se pidió un código para        │  círculo atenta-fondo, ShieldAlert
│     recuperar tu cuenta            │
│     a las 09:02                    │
│     Si no lo pediste tú, no        │  text-base text-tenue
│     compartas el código con nadie. │
│ Ayer                               │
│ (⌂) Cambiaste tu contraseña        │
│     a las 21:15 · Safari en iPhone │
│ …                                  │
│                                    │
│ ¿No reconoces un ingreso? Cierra   │  p text-base, max-w-prose
│ MATU en ese teléfono. Para cambiar │
│ tu contraseña, sal de MATU y toca  │
│ «¿Olvidaste tu contraseña?» al     │
│ entrar.                            │
│                                    │
│ Si necesitas los ingresos          │  p text-base text-tenue
│ anteriores a 90 días, escribe a    │  correo en EnlaceEnFrase mailto
│ cuidaconmatu@gmail.com desde el    │  (con hay_mas, otro texto: 2.5)
│ correo de tu cuenta.               │
├────────────────────────────────────┤
│ [Ficha] [Insumos] [Compartir] [Gr.]│  barra fija (telefono:)
└────────────────────────────────────┘
```

**En el modo `angosto`**, con 320 px y el texto al 200 %:
- el ícono de cada fila y de cada línea pasa arriba del texto (`angosto:flex-col angosto:gap-2`, como en MATU-45);
- la tarjeta pierde su relleno lateral (`px-4 angosto:px-2`);
- los botones van uno bajo otro, a todo el ancho de la tarjeta, con el relleno de su variante (DISENO 3, `angosto:`).

### 2.3 Pantalla ancha (`@3xl/main:` y más)

```
┌──────────────┬───────────────────────────────────────────────────────────────┐
│ (navegación) │ ‹ Volver a tu cuenta                                          │
│              │ Dónde entraste                                                │
│              │ Los teléfonos y computadores… ni tu dirección IP.             │
│              │                                                               │
│              │ ┌ Tus teléfonos y computadores ┐  ┌ Últimos ingresos ────────┐│
│              │ │ ▯ Chrome en Android          │  │ Los de los últimos 90 …  ││
│              │ │   ◉ Este teléfono            │  │ Hoy                      ││
│              │ │   Última vez: hoy a las 10:14│  │ (→] Entraste             ││
│              │ │   Salir                      │  │     a las 10:14 · Chrome…││
│              │ │ ⌨ Chrome en Windows          │  │ (!) Se pidió un código…  ││
│              │ │   Última vez: 09/11/2026 …   │  │ Ayer                     ││
│              │ │   [Cerrar en ese computador] │  │ …                        ││
│              │ └──────────────────────────────┘  │ ¿No reconoces un ingreso?││
│              │                                   │ Si necesitas los …       ││
│              │                                   └──────────────────────────┘│
└──────────────┴───────────────────────────────────────────────────────────────┘
```

- La grilla es `grid grid-cols-1 items-start gap-10 @3xl/main:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]`. Declara `grid-cols-1` en el ancho chico (DISENO 3, reflujo).
- Cada columna es una `section` con `aria-labelledby` en su `h2`, y lleva `min-w-0`.
- Las líneas de ingresos no pasan de `max-w-prose`.
- Los botones van al ancho de su texto, nunca de ancho completo en escritorio.
- A 1920 px, la página sigue el ancho máximo del `main` de la app. Es el mismo marco que Quién la vio.

### 2.4 Una fila de dispositivo

Es un `li` con `flex items-start gap-3 py-4`. El ícono va `aria-hidden`, en `size-6 text-tenue shrink-0 mt-0.5`, y el cuerpo en `flex min-w-0 flex-col items-start gap-1`.

| Parte | Contenido | Clases |
|---|---|---|
| Ícono | Según `clase`: `Smartphone` para `telefono`, `Laptop` para `computador` y `Globe` para `otro` (E1). Es decorativo: el nombre ya lo dice | `size-6 text-tenue` |
| Nombre | `nombre`, tal cual llega («Chrome en Android») | `font-bold break-words` |
| Marca del actual | Solo con `actual: true`. Es una `Etiqueta tono="activo"` con `CircleDot` (`size-4`) y «Este teléfono» **[LENGUAJE 13.3]**, «Este computador» **[NUEVO]** o «Este navegador» **[NUEVO]**, según E1 | `Etiqueta`, ya en `text-base` |
| Última vez | «Última vez: {fecha} a las {hora}» **[LENGUAJE 13.3]**, con `ultimo_uso_en` o, si es `null`, `creado_en`. `{fecha}` es «hoy», «ayer» o `DD/MM/AAAA` **[AJUSTE]**: «hoy» y «ayer» se leen más rápido, y Quién la vio ya los usa. La fecha y la hora van en dos `cifras` dentro de un `<time dateTime>` | `text-base text-tenue tabular-nums` |
| Acción, si es el actual | «Salir» **[LENGUAJE 26, `MARCO.salir`]**. Hace lo mismo que el «Salir» de la cabecera, sin diálogo (C12) | `Boton variante="texto"`, con el ícono `LogOut` igual que en la cabecera |
| Acción, si no es el actual | «Cerrar en ese teléfono» **[LENGUAJE 13.3]**, «Cerrar en ese computador» **[NUEVO]** o «Cerrar en ese navegador» **[NUEVO]**. Abre el diálogo 2.6 | `Boton variante="peligro"`, ancho natural, `self-start`. `aria-describedby` apunta al nombre de su fila, para que el lector diga cuál cierra sin cambiar el texto visible (WCAG 2.5.3) |

- El servidor ordena la lista: primero el actual y después por último uso. **El cliente no reordena.**
- La marca del actual **no es solo color**: lleva la palabra, la figura `CircleDot` y la posición, porque es la primera fila.
- Sin hora relativa («hace 5 minutos») y sin cuenta regresiva.

### 2.5 Una línea de «Últimos ingresos»

Es el patrón de `LineaApertura` de MATU-45 (4.3):
- un `ol` con un `li` por línea, en `flex items-start gap-3 border-b border-linea py-3 last:border-0`;
- el ícono en un círculo `size-9 rounded-full` y `aria-hidden`;
- la frase en `font-bold`, y debajo la cola en `text-base text-tenue tabular-nums`;
- las líneas se agrupan por día con un `h3` (`text-lg font-bold`): «Hoy», «Ayer», «El {día de la semana}» entre 2 y 6 días atrás, y «El DD/MM/AAAA» desde los 7 días. Son las mismas reglas de MATU-45. Si hay `h2` «Últimos ingresos», el día es `h3`;
- el orden es el del servidor, del más nuevo al más viejo. El cliente no reordena ni filtra: el servidor ya recorta a 90 días y 20 líneas (D2) y nunca manda los ingresos fallidos (D1).

**`{nombre}`** es `dispositivo.nombre`. Si `dispositivo` es `null` en un tipo que lleva dispositivo (la conservación lo borró a los 90 días sin uso), `{nombre}` se reemplaza por «un teléfono o computador que ya no está en tu lista» **[NUEVO]**. El evento no trae `clase`, así que no se puede elegir un solo sustantivo. Nunca se dice «dispositivo».

**La cola** dice «a las {HH:MM} · {nombre}» **[ANALISTA]**:
- solo la llevan `entraste` y `saliste`, que no nombran el dispositivo en su frase;
- con `dispositivo: null` en esos dos, la cola es «a las {HH:MM} · en un teléfono o computador que ya no está en tu lista» **[NUEVO]**;
- se agrega « (este teléfono)» **[ANALISTA]**, o «(este computador)» y «(este navegador)» **[NUEVO]**, si `dispositivo.actual` es `true`. El sustantivo sale de `dispositivo.clase` (E1, 1.2);
- en los demás tipos, la cola dice solo «a las {HH:MM}». Los que nombran el dispositivo ya lo dicen en la frase, y los de la cuenta no tienen dispositivo;
- `<time dateTime={ocurrido_en} title="DD/MM/AAAA HH:MM">` envuelve la hora;
- nunca la IP, la ubicación ni el correo (C3 y C5).

| `tipo` | Frase | Ícono lucide | Círculo |
|---|---|---|---|
| `entraste` | Entraste **[ANALISTA]** | `LogIn` | `bg-rocio text-turquesa` |
| `saliste` | Saliste **[ANALISTA]** | `LogOut` | `bg-rocio text-turquesa` |
| `cerraste_en_dispositivo` | Cerraste MATU en {nombre} **[ANALISTA]**, con el nombre del que se cerró (`dispositivo`, contrato C3). No dice desde dónde se cerró, porque el contrato no lo trae | `MonitorSmartphone` | `bg-rocio text-turquesa` |
| `salida_por_seguridad` | Te sacamos de MATU en {nombre} porque notamos un uso extraño. **[AJUSTE]** del texto del analista y del contrato, sin «Vuelve a entrar.»: en una historia, una orden en presente confunde | `ShieldAlert` | `bg-atenta-fondo text-atenta` |
| `contrasena_cambiada` | Cambiaste tu contraseña **[ANALISTA]** | `KeyRound` | `bg-rocio text-turquesa` |
| `celular_confirmado` | Confirmaste tu celular **[ANALISTA]** | `Phone` | `bg-rocio text-turquesa` |
| `codigo_recuperacion_pedido` | Se pidió un código para recuperar tu cuenta **[ANALISTA]**. Debajo, siempre: «Si no lo pediste tú, no compartas el código con nadie.» **[NUEVO] [ANALISTA-CIERRE]**, en `text-base text-tenue` | `ShieldAlert` | `bg-atenta-fondo text-atenta` |
| `avisos_activados` | Activaste los avisos en {nombre} **[ANALISTA]** | `Bell` | `bg-rocio text-turquesa` |
| `avisos_desactivados` | Desactivaste los avisos en {nombre} **[ANALISTA]** | `BellOff` | `bg-rocio text-turquesa` |
| `avisos_cambiados` | Cambiaste tus avisos **[ANALISTA]** | `Bell` | `bg-rocio text-turquesa` |
| Un `tipo` que el cliente no conoce | No se muestra, y la pantalla no se rompe (contrato, `TipoEventoCuenta`) | — | — |

- **Ninguna línea va en `pronto`.** Ni el uso extraño ni el código pedido son una emergencia: son algo para revisar, y por eso van en `atenta`, con su forma propia y su frase.
- El estado lo dicen la frase y la forma (diez íconos, y dos de ellos en otro tono). El color solo acompaña.

**La ayuda al pie de la lista** se ve siempre que haya líneas. Es un párrafo `text-base max-w-prose`, sin botón (E5): «¿No reconoces un ingreso? Cierra MATU en ese teléfono. Para cambiar tu contraseña, sal de MATU y toca «¿Olvidaste tu contraseña?» al entrar.» **[AJUSTE]** del texto del analista, que decía «y cambia tu contraseña». Con la entrada abierta no hay cómo cambiarla, así que el texto dice el camino real, que usa «¿Olvidaste tu contraseña?» de `lenguaje.md` 19. En un computador, «ese teléfono» cambia por «ese computador» o «ese navegador» según la clase del dispositivo actual (E1).

**Lo que no se muestra** va en un párrafo `text-base text-tenue max-w-prose`, que depende de `hay_mas`:

| `hay_mas` | Texto |
|---|---|
| `false` | Si necesitas los ingresos anteriores a 90 días, escribe a {correo} desde el correo de tu cuenta. **[NUEVO]** |
| `true` | Mostramos los 20 más recientes. Para ver los demás, o los anteriores a 90 días, escribe a {correo} desde el correo de tu cuenta. **[NUEVO]** |

- El correo es `correo_contacto` de `GET /v1/politica`, en un `EnlaceEnFrase` con `mailto:` y `[overflow-wrap:anywhere]`, igual que «Cómo pedir» de MATU-75.
- Sin correo configurado, con `hay_mas: true` queda solo «Mostramos los 20 más recientes.», y con `false` el párrafo no se muestra.
- La lista vacía (`eventos: []`) muestra el párrafo de `false`, bajo la nota del vacío.

### 2.6 El diálogo «¿Cerrar MATU en {nombre}?» (D8)

**Construcción.** Es el diálogo de MATU-44 (4.1), que hoy implementa `DialogoPedido`:
- un `<dialog>` modal con `showModal()`, `aria-labelledby` en el título y `aria-describedby` en el texto;
- el foco inicial va en el título, con `tabIndex={-1}`;
- tiene una región de error vacía, con `role="alert"`;
- no tiene animación.

**Recomendación al frontend:** `DialogoPedido` ya recibe el título, el texto y los botones. Conviene sacarlo del pedido (por ejemplo, como `DialogoConfirmar`) en vez de copiarlo. Las clases no cambian.

**Sin contraseña, sin escribir el nombre y con una sola confirmación** (D8 y C13).

```
┌────────────────────────────────────┐
│ ¿Cerrar MATU en Chrome en Windows? │  h2 text-xl font-bold, foco inicial
│                                    │
│ Quien lo use tendrá que volver a   │  p text-base leading-relaxed
│ entrar con tu correo y tu          │
│ contraseña. Puede seguir abierto   │
│ hasta 15 minutos.                  │
│                                    │
│ [ Cerrar en ese computador ]       │  peligroPrincipal (pronto macizo)
│ Dejarlo abierto                    │  Boton texto
└────────────────────────────────────┘
```

| Parte | Texto |
|---|---|
| Título | ¿Cerrar MATU en {nombre}? **[ANALISTA]** |
| Texto | Quien lo use tendrá que volver a entrar con tu correo y tu contraseña. Puede seguir abierto hasta 15 minutos. **[ANALISTA]**. Lo de los 15 minutos lo exige C11 |
| Confirmar | Cerrar en ese teléfono **[LENGUAJE 13.3]**, o ese computador o ese navegador (E1) |
| Mientras pide | Cerrando… **[NUEVO]** |
| Arrepentirse | Dejarlo abierto **[ANALISTA]** |

**Estados.**

| Estado | Qué se ve | Foco |
|---|---|---|
| Abierto | Lo de arriba | En el título |
| Pidiendo (`DELETE /v1/dispositivos/{id}`) | El botón en «Cerrando…» con `aria-busy`, y Esc no cancela la petición | Se queda en el botón |
| 204 | El diálogo se cierra y la fila sale de la lista. Arriba de la lista aparece `Nota tono="ok" enfocable rol="status"`: «Cerramos MATU en {nombre}.» **[ANALISTA]**. «Últimos ingresos» se vuelve a pedir, para que aparezca «Cerraste MATU en {nombre}» | En la nota |
| 404 | El diálogo se cierra y la fila sale de la lista. Arriba de la lista aparece `Nota tono="atenta" enfocable rol="status"`: «Ese teléfono ya no estaba en tu lista.» **[ANALISTA]**, o «Ese computador» o «Ese navegador» **[NUEVO]**, según la clase de la fila (E1) | En la nota |
| 401 | Lo resuelve el cliente de la app: la entrada venció | — |
| Error o sin red | El diálogo sigue abierto, y en su región de error aparece `MensajeError`: «No pudimos cerrar MATU en ese teléfono. Revisa tu conexión y vuelve a intentarlo.» **[NUEVO]**, o ese computador o ese navegador | Se queda en el botón de confirmar |
| Dejarlo abierto o Esc | Se cierra sin hacer nada | Vuelve al botón que lo abrió |

### 2.7 Estados de la página

Cada `section` carga por su cuenta. Si una falla, la otra se sigue viendo.

| Estado | Tus teléfonos y computadores | Últimos ingresos |
|---|---|---|
| Cargando | `p role="status" text-tenue` «Cargando…» **[LENGUAJE 26]**, después de la demora de `useDemora`. Sin esqueletos (DISENO 6, Página) | Igual |
| Vacío | No puede pasar, porque el dispositivo actual siempre está. Si `items` llega vacío, se trata como error | `Nota tono="rocio"`: «No hay ingresos en los últimos 90 días.» **[ANALISTA]**. Sin «¿No reconoces un ingreso?», pero con el párrafo del correo (2.5) |
| Error o sin red | `Nota tono="pronto" rol="alert"`: «No pudimos traer dónde entraste. Revisa tu conexión e inténtalo de nuevo.» **[ANALISTA]**, y `Boton variante="secundario"` «Volver a intentar» **[LENGUAJE 26]** | `Nota tono="pronto" rol="alert"`: «No pudimos traer tus últimos ingresos. Revisa tu conexión e inténtalo de nuevo.» **[NUEVO]**, y «Volver a intentar» |
| 401 | Lo resuelve el cliente de la app | Igual |
| 412 | **No aplica:** las dos son lecturas, y el `DELETE` no lleva versión | Igual |
| Al volver a la página | Se vuelve a pedir. Nada se guarda en el navegador (C6) | Igual |

---

## 3. «Tu cuenta» (`/cuenta`) con los avisos y la entrada a «Dónde entraste»

**Objetivo, desde Carmen:** «Quiero elegir cómo me avisa MATU y saber dónde está abierta mi cuenta, sin tener que buscarlo.»

### 3.1 Jerarquía

1. El `h1` «Tu cuenta» y su bajada, que ya existen.
2. Los datos que ya existen (correo, celular y política). **El único cambio es que los tres `dt` («Tu correo», «Tu celular» y «Política de privacidad») pasan de `text-sm text-tenue` a `text-base text-tenue`** (MATU-93). Se distinguen del dato por el color `tenue` y por el orden, nunca por el tamaño.
3. **Nuevo:** «Dónde entraste», con una frase y su botón.
4. **Nuevo:** «Avisos cuando un insumo se está acabando», con las dos casillas y, debajo de «En tus teléfonos», el teléfono actual.
5. «Cómo pedir» (MATU-75), que sigue al final.

**Acción principal:** ninguna en macizo, como hoy. Todo es `secundario` o casilla. **No hay ningún `turquesa` macizo en «Tu cuenta».**

### 3.2 Esquema a 360 px

```
┌────────────────────────────────────┐
│ Tu cuenta                          │  h1
│ Tus datos para entrar a MATU.      │
│ ┌────────────────────────────────┐ │  dl existente
│ │ Tu correo · Tu celular ·       │ │
│ │ Política de privacidad         │ │
│ └────────────────────────────────┘ │
│                                    │
│ ┌────────────────────────────────┐ │  section bg-hoja rounded-xl ring-1 ring-linea
│ │ Dónde entraste                 │ │  h2 text-xl font-bold
│ │ Los teléfonos y computadores   │ │  text-base text-tenue
│ │ donde entraste, y tus últimos  │ │
│ │ ingresos.                      │ │
│ │ [ Ver dónde entraste ]         │ │  Boton secundario
│ └────────────────────────────────┘ │
│                                    │
│ ┌────────────────────────────────┐ │  fieldset bg-hoja rounded-xl ring-1 ring-linea
│ │ Avisos cuando un insumo se     │ │  legend = h2 text-xl font-bold
│ │ está acabando                  │ │
│ │ Te avisamos cuando un insumo se│ │  text-base text-tenue
│ │ esté acabando. El aviso no dice│ │
│ │ cuál ni de quién.              │ │
│ │ Vale para todos tus grupos.    │ │  text-base font-bold
│ │                                │ │
│ │ [✓] Por correo                 │ │  casilla size-6, etiqueta min-h-12
│ │ [✓] En tus teléfonos           │ │
│ │   ┃ Este teléfono              │ │  bloque 3.4, border-l-4 border-linea ps-4
│ │   ┃ (✓ Activados)              │ │  Etiqueta ok
│ │   ┃ [ Desactivar en este       │ │  Boton secundario
│ │   ┃   teléfono ]               │ │
│ │                                │ │
│ │ Guardamos tus avisos.          │ │  role=status, text-base
│ │ ⓘ En el piloto los avisos se   │ │  Nota atenta con Info
│ │   prueban sin enviarse: no te  │ │
│ │   llegará nada.                │ │
│ └────────────────────────────────┘ │
│                                    │
│ Para cambiar tu nombre o tu correo…│  ComoPedir, existente
└────────────────────────────────────┘
```

**Pantalla ancha.** Es la misma columna de `max-w-xl` que hoy, alineada a la izquierda. «Tu cuenta» es una página de ajustes corta, y con dos columnas «Avisos» quedaría lejos del texto que la explica. En el modo `angosto`, las tarjetas pasan a `px-2`, y la sangría del bloque del teléfono baja a `ps-2` con `border-l-4`.

### 3.3 Las preferencias (D5)

Son un `fieldset` cuya `legend` lleva el estilo de un `h2`: «Avisos cuando un insumo se está acabando» **[LENGUAJE 20]**.

| Parte | Texto | Componente |
|---|---|---|
| Ayuda | Te avisamos cuando un insumo se esté acabando. El aviso no dice cuál ni de quién. **[ANALISTA]** | `p text-base text-tenue max-w-prose`, unido al `fieldset` con `aria-describedby` |
| Alcance | Vale para todos tus grupos. **[ANALISTA, D5]** | `p text-base font-bold`, también en el `aria-describedby`. Va en negrita porque es lo que la gente no espera |
| Casilla 1 | Por correo **[LENGUAJE 20]** → `correo` | La casilla de DISENO 6: `size-6`, `accent-turquesa` y la etiqueta de `min-h-12` como área táctil |
| Casilla 2 | En tus teléfonos **[AJUSTE de LENGUAJE 20, D5]**: reemplaza a «En este teléfono», porque la preferencia vale para todos los teléfonos → `push` | Igual |
| Guardando | Guardando… **[LENGUAJE 17]**. Es un `p role="status"` bajo las casillas. La casilla que se tocó lleva `aria-busy`, y las dos quedan con `aria-disabled="true"` mientras se guarda: un cambio en ese momento se ignora y la casilla no se mueve. **(1.2) No van `disabled`**: un control `disabled` pierde el foco y el navegador lo deja en el `body` (revisión del 12-11). Se ven igual que deshabilitadas, con la opacidad de DISENO 6, salvo la que tiene el foco: `aria-disabled:not-focus-visible:opacity-60` (1.3). La opacidad del `input` también apaga su contorno de foco | `text-base text-tenue` |
| Guardado | Guardamos tus avisos. **[ANALISTA]**, en el mismo `p role="status"`. Se borra al cambiar otra vez | `text-base` |
| Error o sin red | No pudimos guardar. Revisa tu conexión y vuelve a intentarlo. **[LENGUAJE 17]**. La casilla vuelve a lo que estaba antes de tocarla y el foco se queda en ella | `MensajeError` bajo las casillas |

**(1.2) El foco, en todo el bloque.** Cuando el foco tiene que ir a otro control después de una respuesta (la casilla tras guardar, «Desactivar…» tras activar, «Activar…» tras desactivar), se mueve **después de que React pinta el cambio**: en un efecto que mira el estado, como hace «Dónde entraste» con su nota, y no con un `setTimeout(0)` en el `finally`. En la revisión, el `setTimeout` corría antes del render y el foco terminaba en el `body` en los tres casos. Al guardar una casilla, «Activaste…» o «Desactivaste…» se borran, y al activar o desactivar se borra «Guardamos tus avisos.»: solo se ve el mensaje de lo último que se hizo.
| Piloto | En el piloto los avisos se prueban sin enviarse: no te llegará nada. **[ANALISTA]** | `Nota tono="atenta"` con el ícono `Info`, el rótulo del piloto de DISENO 3. Va una vez, al final del bloque, y vale para los dos canales. Se ve mientras `envio_simulado` de `GET /v1/dispositivos/actual/push` sea `true`, que en el semestre es siempre. Si esa lectura falla, se muestra igual, porque es lo cierto en el piloto |

**Estados del bloque.**

| Estado | Qué se ve |
|---|---|
| Cargando (`GET /v1/yo/avisos`) | El `legend` y la ayuda, y en lugar de las casillas «Cargando…» con `role="status"` |
| Error al cargar o sin red | `Nota tono="pronto" rol="alert"`: «No pudimos traer tus avisos. Revisa tu conexión e inténtalo de nuevo.» **[NUEVO]**, y «Volver a intentar». Sin las casillas, para no mostrar un valor inventado |
| Listo | Las casillas, con lo que dice el `GET`. El valor por omisión del rol lo resuelve el servidor (decisión 78), y la pantalla no lo explica |
| 412 | **No aplica.** `PUT /v1/yo/avisos` no lleva versión ni `If-Match`: se queda lo último que se guardó. Si el backend agrega versión, se vuelve a especificar |
| 422 | Solo puede pasar por un defecto. Se trata como el error |

### 3.4 «Este teléfono»: recibir avisos aquí (D6)

**Solo se ve si «En tus teléfonos» está marcada** (E4). Al desmarcarla, el bloque se oculta y la inscripción de este teléfono no se borra. Al volver a marcarla, el bloque reaparece en el estado en que quedó, y si estaba activado ofrece «Desactivar en este teléfono». Es un bloque `flex flex-col items-start gap-3 border-l-4 border-linea ps-4 angosto:ps-2 mt-1`, justo debajo de esa casilla, con un `h3` `text-lg font-bold`: «Este teléfono» **[LENGUAJE 13.3]**, «Este computador» o «Este navegador» **[NUEVO]** (E1). La raya izquierda en `linea` lo cuelga de la casilla. No es el borde de un control, así que no necesita 3:1.

**De dónde sale el estado:**
- de `GET /v1/dispositivos/actual/push`, que trae `clave_publica`, `registrado` y `envio_simulado`;
- del navegador: `Notification.permission`, `PushManager.getSubscription()` y si la app está instalada.

**La pantalla nunca pide el permiso al cargar: solo al tocar «Activar»** (D6-a).

Mientras carga esa lectura, el bloque muestra «Cargando…» con `role="status"`. Si falla o no hay red, muestra `Nota tono="pronto" rol="alert"`: «No pudimos ver los avisos de este teléfono. Revisa tu conexión e inténtalo de nuevo.» **[NUEVO]**, con «Volver a intentar». Las casillas siguen funcionando.

| Estado | Cuándo | Qué se ve |
|---|---|---|
| **A. Activados** | `registrado: true` y el navegador tiene una suscripción con la misma `clave_publica` | `Etiqueta tono="ok"` con `Check` y «Activados» **[NUEVO]**. `Boton variante="secundario"` «Desactivar en este teléfono» **[NUEVO]** |
| **B. Sin activar** | Hay soporte, `clave_publica` no es `null`, el permiso es `default` o `granted` y falta la suscripción o `registrado` | `Etiqueta` neutra con `Circle` y «Sin activar» **[NUEVO]**. La ayuda, en `text-base text-tenue max-w-prose`: «Al activarlos, tu navegador anota una dirección de avisos en el servicio de su fabricante, y MATU la guarda hasta que los desactives o salgas. En el piloto, MATU no le envía nada a ese servicio.» **[NUEVO, de la línea de la política 0.14, D6] [ANALISTA-CIERRE], texto aprobado en la 1.3]**. `Boton variante="secundario"` «Activar en este teléfono» **[NUEVO]** |
| **C. El navegador no deja** | `Notification.permission === 'denied'` | `Etiqueta` neutra con `Circle` y «Sin activar». `Nota tono="atenta"`: «Tu navegador no deja que MATU te avise. Puedes cambiarlo en los ajustes del navegador.» **[ANALISTA]**. Sin botón, porque no hay nada que MATU pueda hacer |
| **D. Sin soporte** | No hay `serviceWorker`, `PushManager` o `Notification`, y no es el caso E | `Nota tono="rocio"`: «Este navegador no puede recibir avisos.» **[ANALISTA]** «Puedes recibirlos por correo.» **[NUEVO]**. Sin etiqueta ni botón |
| **F. MATU todavía no puede activarlos** | `clave_publica: null`, en un navegador que sí tiene soporte (Q6 del contrato) | La misma forma que D, `Nota tono="rocio"` sin etiqueta ni botón: «Por ahora no se pueden activar los avisos en este teléfono. Puedes recibirlos por correo.» **[NUEVO]**. No habla de la clave ni de la configuración, y no culpa al navegador. En un computador o en otro navegador, «teléfono» cambia según E1. Si además falta el soporte, manda D, y en un iPhone sin instalar, manda E |
| **E. iPhone o iPad sin agregar a la pantalla de inicio** | iOS o iPadOS, sin `display-mode: standalone` ni `navigator.standalone` (ADR-026) | `Nota tono="rocio"` con el título «En iPhone, primero agrega MATU a tu pantalla de inicio.» **[NUEVO]** y una lista `ol list-decimal ps-5`: 1. «Toca Compartir {ícono `Share`} en Safari.» 2. «Elige «Agregar a inicio».» 3. «Abre MATU desde su ícono y vuelve a Tu cuenta.» **[NUEVO]**. El ícono `Share` va en línea, en `size-5`, con `aria-label="Compartir"`, porque es lo que la persona busca en la pantalla. **(1.2)** La `Nota` lleva `iconoEnLinea` (MATU-44), para que en el modo `angosto` el ícono vaya en la línea del título y la lista use todo el ancho: sin eso, a 320 px con el texto al 200 % «Compartir» se sale 22 px. Sin botón. Si el iPhone instalado tampoco tiene `PushManager` (iOS anterior a 16.4), pasa a D |

**Lo que pasa al tocar.**

| Momento | Qué se ve | Foco y anuncio |
|---|---|---|
| Activando (permiso, suscripción y `PUT`) | El botón en «Activando…» **[NUEVO]** con `aria-busy` | Se queda en el botón |
| Activado | Pasa al estado A. `p role="status"`: «Activaste los avisos en este teléfono.» **[NUEVO]**, el mismo verbo del botón | Al botón «Desactivar en este teléfono» |
| La persona cierra el aviso del navegador sin elegir (sigue `default`) | Sigue en B. `p role="status" text-base`: «No activamos los avisos. Puedes volver a intentarlo.» **[NUEVO]** | Se queda en el botón |
| La persona elige «Bloquear» | Pasa a C | A la nota de C, que es `enfocable` |
| Falla el `PUT` o no hay red | Sigue en B, y el frontend borra la suscripción del navegador para que no quede a medias. `MensajeError`: «No pudimos activar los avisos. Revisa tu conexión y vuelve a intentarlo.» **[NUEVO]** | Se queda en el botón |
| Desactivando (`DELETE /v1/dispositivos/actual/push` y, con el 204, borra la suscripción del navegador; 1.2) | «Desactivando…» **[NUEVO]**. Si el `DELETE` falla, la suscripción sigue y la pantalla sigue en A. Si después falla borrar la del navegador, no se avisa: el servidor ya no envía a este teléfono | Se queda en el botón |
| Desactivado | Pasa a B. `p role="status"`: «Desactivaste los avisos en este teléfono.» **[NUEVO]** | Al botón «Activar en este teléfono» |
| Falla el `DELETE` | Sigue en A. `MensajeError`: «No pudimos desactivar los avisos. Revisa tu conexión y vuelve a intentarlo.» **[NUEVO]** | Se queda en el botón |

En un computador o en un navegador genérico, «teléfono» cambia por «computador» o «navegador» en todos estos textos (E1).

### 3.5 «Dónde entraste» dentro de «Tu cuenta»

| Parte | Texto | Componente |
|---|---|---|
| Título | Dónde entraste **[LENGUAJE 13.3]** | `h2 text-xl font-bold` |
| Bajada | Los teléfonos y computadores donde entraste, y tus últimos ingresos. **[NUEVO]** | `p text-base text-tenue` |
| Botón | Ver dónde entraste **[NUEVO]** | `Boton variante="secundario"`, que navega a `/cuenta/donde-entraste`. Es un botón y no un enlace porque así lo hace hoy la app (`navegar`) |

Esta entrada no pide nada a la API: no muestra cuántos dispositivos hay, para que «Tu cuenta» no espere otra petición. **(1.2)** El bloque de avisos sí pide `GET /v1/dispositivos`, solo para la clase del dispositivo actual (E1). No espera esa lectura para mostrar las casillas.

### 3.6 El `manifest` y los íconos (D6, necesarios para iPhone)

Sin el `manifest`, el iPhone no instala MATU y el estado E no tiene salida.

| Campo | Valor |
|---|---|
| `name` y `short_name` | MATU |
| `lang` | es-CL |
| `description` | Que el cuidado no dependa de una sola persona. (DISENO 3, panel del alta) |
| `start_url` y `scope` | `/` (la entrada lleva a la ficha). **Nunca la ruta del relevo**, porque el token viaja en el fragmento |
| `display` | `standalone` |
| `theme_color` | `#0D9A94`, el `marca` (DISENO 1: el favicon, el `manifest` y `theme-color` usan el mismo) |
| `background_color` | `#ECF3F2`, el `papel` claro |
| Íconos | El logo de DISENO 1: el círculo `marca` con el `Heart` de lucide relleno en blanco. Van en PNG de 192 y 512 px, `purpose: any`, con fondo transparente fuera del círculo. Además, un PNG `maskable` de 512 px: el cuadrado entero en `marca` y el corazón blanco dentro del 60 % central, la zona segura. El `apple-touch-icon` es de 180 px, cuadrado y opaco (iOS pinta de negro lo transparente): fondo `marca` y el corazón blanco al 60 % |
| Dónde | `web/public/`, generados en local. **Nada desde una CDN** |
| El corazón (1.2) | Es el del favicon de `index.html`, no el `Heart` de lucide: así el favicon, el ícono de la pantalla de inicio y el del manifiesto tienen la misma forma. En la revisión mide el 49 % del ancho, y su punto más lejano queda a 0,27 del lado desde el centro: dentro del 60 % central y del círculo seguro de radio 0,4. Si se quiere el `Heart` de lucide igual que el logo de la barra, se cambia en el favicon y en los cuatro PNG en un mismo cambio (P3, no bloquea) |

---

## 4. Tokens y componentes

**Sin tokens nuevos.** Se usan:
- los colores `papel`, `hoja`, `tinta`, `tenue`, `turquesa` (foco, actual y texto de acción), `rocio`, `linea`, `borde`, `pronto` y `pronto-fondo` (solo el botón y el diálogo de cerrar, y los errores), `atenta` y `atenta-fondo`, y `ok` y `ok-fondo`;
- los radios `rounded-xl`, `rounded-2xl` (el diálogo) y `rounded-full`;
- las variantes `angosto:`, `telefono:` y `@3xl/main:`.

**Componentes:**
- los que hay: `Pagina`, `Volver`, `Nota`, `Etiqueta`, `Boton` (`secundario`, `texto`, `peligro` y `peligroPrincipal`), `MensajeError`, `EnlaceEnFrase` y la casilla de DISENO 6;
- el diálogo de `DialogoPedido`, generalizado;
- dos nuevos: `FilaDispositivo` (2.4) y `LineaIngreso` (2.5, copia de `LineaApertura`).

**Nada escrito a mano:** ni colores, ni `size-[…]`, ni sombras, ni `text-sm` o `text-xs`.

---

## 5. Accesibilidad

- **17 px:** ningún texto bajo `text-base`: ni la cola de las líneas, ni las ayudas, ni los rótulos del `dl` de `Cuenta.tsx`, que pasan de `text-sm` a `text-base` (MATU-93).
- **48 px:** «Salir», «Cerrar en ese…», «Ver dónde entraste», «Activar» y «Desactivar», «Volver a intentar», las dos etiquetas de casilla y los botones del diálogo miden `min-h-12`. El enlace del correo usa el `::after` de DISENO 6.
- **Foco:** el contorno base de 3 px en `turquesa`, y en `pronto` en los botones `peligro`. Al llegar a la página va al `h1`. Las notas que reciben el foco son `enfocable` y no dibujan contorno, porque no son controles.
- **El diálogo** atrapa el foco con `showModal` y lo devuelve al botón que lo abrió (P7).
- **El estado nunca solo por color:**
  - el dispositivo actual tiene palabra, `CircleDot` y la primera posición;
  - «Activados» y «Sin activar» tienen palabra y `Check` o `Circle`;
  - los tipos de ingreso tienen su frase y su ícono;
  - las casillas, el check nativo.
- **Anuncios:** «Guardando…», «Guardamos tus avisos.», «Activaste…», «Desactivaste…», «Cerramos MATU en…» y «Ese teléfono ya no estaba…» van por `role="status"`, y los errores por `role="alert"` (con las regiones vivas de `Anuncios`).
- **Semántica:**
  - los dispositivos son una `ul` y los ingresos una `ol` con `h3` por día;
  - las horas van en `<time>`;
  - el bloque de avisos es un `fieldset` con `legend`.
- **Reflujo a 320 px con el texto al 200 %:**
  - los nombres («Samsung Internet en Android») van en `break-words`;
  - el correo de contacto va en `[overflow-wrap:anywhere]`;
  - la fecha y la hora van en dos `cifras` para que la hora baje de renglón;
  - los íconos se apilan en el modo `angosto`;
  - sin desplazamiento horizontal.
- **Movimiento:** nada se anima. Con `prefers-reduced-motion` no cambia nada, porque ya es inmediato.
- **Datos:** nada de esta pantalla va a `localStorage`, `sessionStorage` ni a la URL (C6). La suscripción del navegador la guarda el propio navegador, no MATU.

---

## 6. Criterios visuales verificables

1. En `/cuenta/donde-entraste` y en `/cuenta` no hay ningún elemento en `turquesa` macizo. Dentro del diálogo, el único macizo es «Cerrar en ese…», en `pronto`.
2. La primera fila de «Tus teléfonos y computadores» es la del dispositivo actual. Lleva «Este teléfono» (o computador, o navegador) en palabra con `CircleDot`, y su acción es «Salir», no «Cerrar en ese…».
3. Ninguna línea ni fila muestra una IP, una ubicación, un correo ni un identificador.
4. Ninguna línea de «Últimos ingresos» va en `pronto`. El uso extraño y el código pedido van en `atenta` con `ShieldAlert`.
5. «Últimos ingresos» nunca tiene más de 20 líneas, ni una de hace más de 90 días, ni un ingreso fallido.
6. El diálogo abre con el foco en su título, dice lo de los 15 minutos y no tiene ningún campo de contraseña.
7. La casilla dice «En tus teléfonos», no «En este teléfono», y «Vale para todos tus grupos.» va en negrita dentro de la descripción del `fieldset`.
8. La nota del piloto se ve una sola vez en el bloque de avisos, en `atenta` con `Info`, en todos los estados del teléfono, mientras `envio_simulado` sea `true`.
9. Al cargar «Tu cuenta», el navegador no pide el permiso de avisos. Lo pide solo al tocar «Activar en este teléfono».
10. En un iPhone sin MATU en la pantalla de inicio se ven los tres pasos con el ícono `Share`, y ningún botón «Activar».
11. Ningún texto mide menos de 17 px. Todo lo tocable mide 48 px o más. A 320 px con el texto al 200 % no hay desplazamiento horizontal.
12. Con `clave_publica: null` se ve el estado F, sin la palabra «clave» y sin botón «Activar».
13. «Tu correo», «Tu celular» y «Política de privacidad» miden 17 px (`text-base`).
14. No hay ningún botón «Cambiar mi contraseña».
15. Ningún texto dice «sesión», «dispositivo», «IP» (salvo en la bajada, donde se dice que no se guarda), «token», «evento» ni «auditoría».
16. **(1.2)** Después de guardar una casilla (bien o con error), de activar o de desactivar, `document.activeElement` nunca es el `body`: es la casilla, el botón que aparece o la nota de C.

---

## 7. El contrato, resuelto (`docs/api/propuestos/donde-entraste.openapi.yaml`)

| # | Pregunta de la 0.1 | Cómo quedó |
|---|---|---|
| C1 | La ruta y la forma | `GET /v1/yo/ingresos` responde `{eventos[], hay_mas}`. Cada evento trae `{tipo, ocurrido_en, dispositivo: {nombre, actual} \| null}`, y `tipo` es un enum cerrado de diez valores (2.5). Nunca trae IP ni identificadores |
| C2 | El recorte | Lo hace el servidor: 90 días, 20 eventos y sin los fallidos. `hay_mas` avisa si hay más de 20 |
| C3 | El nombre en «Cerraste MATU en {nombre}» | Es el del dispositivo que se cerró. **Ojo, orquestador:** tu mensaje dice `objetivo.nombre`, pero el YAML de hoy lo trae en `dispositivo.nombre` (`TipoEventoCuenta`: «sí, el que se cerró»). La especificación sigue al YAML. Si el campo cambia de nombre, solo cambia la lectura, no el texto. El origen no llega, así que la línea no dice «desde…» |
| C4 | La clave VAPID | Llega por `GET /v1/dispositivos/actual/push` en `clave_publica`, o `null`. La misma respuesta trae `registrado` y `envio_simulado` (3.4) |
| C5 | `push_activo` por dispositivo | No hace falta. Para este teléfono basta `registrado` |
| C6 | Cambiar la contraseña con la entrada abierta | No se puede. Se quita «Cambiar mi contraseña» (E5) y la ayuda lo dice en texto (2.5) |
| C7 | `clase` | Está en `DispositivoVista`: `telefono`, `computador` u `otro` (E1). **(1.2)** También llega en el `dispositivo` de cada evento, y «(este {…})» la usa. Con `dispositivo: null` no hay clase, así que el texto nombra «un teléfono o computador» |
| C8 | `Cache-Control: no-store` | Sí, en todas las respuestas de `/v1/yo/` y `/v1/dispositivos` |
| C9 | `SolicitudPush` sin `p256dh` ni `auth` | Sigue igual. No afecta a la pantalla |

---

## 8. Textos para `lenguaje.md`

Son todos los marcados **[ANALISTA]**, **[NUEVO]** y **[AJUSTE]**, en una sección nueva («Dónde entraste y avisos», MATU-55).

**Los [NUEVO] que pidió el orquestador (Q6 del contrato):**
- `dispositivo: null`: «un teléfono o computador que ya no está en tu lista», en lugar de `{nombre}` o en la cola (2.5);
- `hay_mas`: con `false`, «Si necesitas los ingresos anteriores a 90 días, escribe a {correo} desde el correo de tu cuenta.»; con `true`, «Mostramos los 20 más recientes. Para ver los demás, o los anteriores a 90 días, escribe a {correo} desde el correo de tu cuenta.» (2.5);
- `clave_publica: null`: «Por ahora no se pueden activar los avisos en este teléfono. Puedes recibirlos por correo.» (3.4, estado F);
- el sustantivo de E1: «teléfono», «computador» o «navegador», en «Este…», «(este…)», «Cerrar en ese…», «Ese… ya no estaba en tu lista.» y los textos de avisos de 3.4.

**Los seis ajustes a textos ya aprobados o propuestos:**
1. «En tus teléfonos», en la sección 20, con «Vale para todos tus grupos.».
2. «hoy» y «ayer» en «Última vez», en la 13.3.
3. «Te sacamos de MATU en {nombre} porque notamos un uso extraño.», sin «Vuelve a entrar.», también en la tabla de `TipoEventoCuenta` del contrato.
4. «Los de los últimos 90 días, hasta 20.», con «hasta 20» agregado al texto del analista.
5. El sustantivo según la clase (E1).
6. «¿No reconoces un ingreso? Cierra MATU en ese teléfono. Para cambiar tu contraseña, sal de MATU y toca «¿Olvidaste tu contraseña?» al entrar.» (E5).

**[ANALISTA-CIERRE]**, los dos textos que el analista revisa en el cierre antes de copiarlos:
1. La ayuda del estado B: «Al activarlos, tu navegador anota una dirección de avisos en el servicio de su fabricante, y MATU la guarda hasta que los desactives o salgas. En el piloto, MATU no le envía nada a ese servicio.» Repite la línea de la política 0.14, y las dos tienen que decir lo mismo.
2. «Si no lo pediste tú, no compartas el código con nadie.», bajo `codigo_recuperacion_pedido`.

---

## 9. Cómo la voy a revisar

La voy a revisar funcionando, con capturas a 360, 1280 y 1920 px, en tema claro y oscuro, y a 320 px con el texto al 200 %. El recorrido es este:
1. Entrar en dos navegadores, A y B.
2. En A, ver los dos dispositivos y cerrar B, primero con «Dejarlo abierto» y después confirmando.
3. Ver «Cerraste MATU en…» en los ingresos.
4. Cerrar B otra vez desde una pestaña vieja, para ver el 404.
5. Pedir un código de recuperación y ver su línea en `atenta`.
6. Cambiar las dos casillas, y probar un error sin red.
7. Activar y desactivar los avisos, con el permiso concedido, cerrado sin elegir y bloqueado.
8. Desmarcar y volver a marcar «En tus teléfonos» con este teléfono activado (E4).
9. Probar un navegador sin soporte, y un backend sin `VAPID_CLAVE_PRIVADA` (estado F).
10. Ver un evento con `dispositivo: null` y otro con `hay_mas: true`, con datos sintéticos.

En el iPhone real, lo prueba Martín: Safari sin instalar (estado E), después agregar MATU a la pantalla de inicio y activar. Además, verifico el texto exacto de «Agregar a inicio» en un iOS en español.

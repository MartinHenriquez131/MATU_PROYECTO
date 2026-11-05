# MATU-48 · App de familia: compartir la ficha con un relevo y cortar el acceso · Especificación de diseño

**Versión 1.1 · 04/11/2026** · agente 6 (UI/UX) · para el frontend, antes de construir
**Cambios de la 1.1 (revisión visual del 04-11, confirmados por el orquestador):** D4, 2.4 (lugar de «Quién puede verla ahora» y cuadrícula desde `@3xl/main:`), 3.2 (vista previa en `max-w-prose` bajo `@4xl/main:`), 3.3 (motivos en chips al ancho de su texto), 4.4 (textos de L 9.1), 5.2 (`@3xl/main:`), 5.3 (fila «Llamar» y alineación de los botones de texto), 6.1 (`Boton`: relleno lateral por variante) y 9.4 (textos que reemplazó L 9.1). Donde esta especificación y `lenguaje.md` 9.1 difieran, manda 9.1.
**Historia:** Carmen crea un enlace con PIN para Rosa, le dicta el PIN una sola vez y, cuando quiere, corta el enlace en el acto.
**Dónde se construye:** `web/`, sobre el esqueleto de MATU-39 y con el selector de MATU-50 (`web/src/familia/SeccionesCompartir.tsx`).

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` (sin agregar ninguno) · la demo aprobada (`Demo/src/familia/Ficha.tsx`: `Compartir`, `EnlacePin`, `Enlaces`; `Demo/ESPEC-ADR-027.md` §6.2 y §6.3) · `docs/diseno/matu-39-app-familia.md`, `matu-45-aperturas.md` y `matu-49-ficha-ampliada.md` §6 · `docs/lenguaje.md` del repositorio MATU (secciones 2, 3, 4, 7.5, 8, 9, 14 y 15) · ADR-028 (secciones) y ADR-029 (la ficha no se imprime ni se exporta) · contrato: `docs/api/openapi.json` (`POST` y `GET …/plan/accesos-relevo`, `AccesoCreadoVista`, `AccesoResumenVista`) y `docs/api/propuestos/relevo.openapi.yaml` (`DELETE /v1/accesos-relevo/{acceso_id}`), con las decisiones 15, 16, 18, 22, 24, 25, 31 y 34 de `docs/api/README.md`.

**Cómo se lee:** igual que MATU-39. Los textos entre «» van tal cual. **[L 9]** = está en `lenguaje.md`, sección 9 (y así con cada sección). **[DEMO]** = texto de la demo aprobada que todavía no está en `lenguaje.md`: entra en el mismo PR. **[CONTRATO]** = lo fija una decisión del contrato y falta en `lenguaje.md`. **[PROPUESTO]** = nuevo, lo aprueba Jorge. Las llaves son datos de la API o de lo escrito. Donde la demo dice `pino`, en `web/` es `turquesa`.

---

## 0. Lo que tiene que decidir alguien más

| # | Qué | Por qué importa | Lo que hace la especificación mientras tanto |
|---|---|---|---|
| D1 | **Cómo se envía el enlace.** La demo dice «Enviar el enlace por WhatsApp». Un enlace `https://wa.me/{teléfono}?text={url}` pone el token en la consulta de una URL de un tercero (pasa por los servidores de wa.me antes de abrir la app), y el token solo debe viajar en el fragmento (CLAUDE.md, agente 3, punto 5) | Es una decisión de seguridad, no de diseño | **Compartir del sistema** (`navigator.share`), que abre la hoja de compartir del teléfono (WhatsApp, SMS, lo que tenga) sin pasar por un servidor; y «Copiar el enlace» donde no existe (computador). Ver 4.4. Para el analista y Jorge |
| D2 | **La casilla de la decisión 34** («Le avisé a `{nombre}` que MATU guarda su nombre y su teléfono para enviarle la ficha») está en el contrato y no en `lenguaje.md`, y no dice lo que agregó el 03-11 al aviso del relevo (7.5): que cada apertura queda registrada y la familia la ve | Sin la casilla el `POST` responde 422. La demo no la tenía | Va con el texto del contrato, marcado **[CONTRATO]**. El analista decide si suma el registro (sección 10) |
| D3 | `lenguaje.md` 9 tiene «¿Qué puede ver?» y el recordatorio «Comparte solo lo que necesita para cuidar**la**…», y 8 tiene «Elige al menos un campo.» | Con ADR-028 los tres campos ya no se eligen, y «cuidarla» asume el género de la persona cuidada (L 10, fila 8) | «¿Qué puede ver?» pasa a «Siempre ve» y «¿Qué más puede ver?» (L 14.3, ya aprobado). El recordatorio va neutro **[PROPUESTO]** (3.4). La fila de «Elige al menos un campo.» se retira de `lenguaje.md` 8 |
| D4 | **El teléfono del relevo en «Enlaces».** La API lo devuelve a `admin` y `cuidador` para poder contactarle (decisiones 24 y 31). La demo no lo muestra | Mostrarlo es más dato a la vista. Un botón «Llamar a `{nombre}`» sería una tercera acción por enlace | **Resuelta por Jorge el 04-11 (`lenguaje.md` 9.1):** el número nunca se muestra. Para `admin` y `cuidador`, cada tarjeta lleva el botón de texto «Llamar a `{nombre}`» con `Phone` y `tel:`, en **todos** los estados (también cortados y vencidos, mientras se guarde el teléfono). Si el teléfono ya se borró (30 días, decisión 25), en su lugar va «Ya no guardamos su teléfono.» en `text-base text-tenue`. Ver 5.3 |
| D5 | **El PIN se puede perder** si el teléfono descarta la pestaña mientras Carmen está en WhatsApp. El PIN vive solo en memoria y no se puede guardar en el navegador | Se pierde el PIN y hay que crear otro enlace | El PIN va **antes** del botón de enviar en el teléfono (4.2), para que Carmen lo vea o lo anote antes de salir. Riesgo aceptado: lo resuelve «El PIN ya no se puede ver» (4.6) |
| D6 | El esquema de MATU-45 4.1 dice «vence en 1 día 3 h»; la demo usa `fmtRestante` («45 min», «23 h», «3 días») | Dos formatos para lo mismo | Se usa el de la demo en las dos pantallas (5.3) |

**El contrato no tiene 410 en la app de la familia.** Los tres 410 (`relevo-vencido`, `relevo-revocado`, `relevo-no-disponible`) son de la página del relevo (MATU-23). Aquí un enlace vencido o cortado es un `estado` de la lista, y cortar uno que ya no abre responde 204 igual (es idempotente). No hay 412: los accesos no llevan `ETag`.

---

## 1. Para quién y qué

**Carmen** va a salir unas horas. Quiere que Rosa vea la ficha de María, con lo justo, por un tiempo, y sin que Rosa tenga que crear una cuenta. Escribe el nombre y el teléfono de Rosa, elige qué más ve y hasta cuándo, y toca un botón. MATU le muestra el PIN una sola vez: ella le manda el enlace a Rosa y le dicta el PIN por teléfono. Cuando vuelve, o si algo le preocupa, corta el enlace en el acto.

**Lo que no cambia contra la demo:** el orden del formulario, los motivos, las vigencias, el momento orquestado del PIN (DISENO.md, principio 5), la tarjeta de cada enlace y el verbo «cortar».

**Lo que cambia para `web/`**, en resumen:

| Demo | `web/` | Por qué |
|---|---|---|
| Compartir y Enlaces eran pestañas de la Ficha, junto a «Para imprimir» | **Compartir es una sección** de la navegación (MATU-39 2.2) con dos vistas: «Compartir» y «Enlaces». **No hay «Para imprimir»** | MATU-39 y ADR-029 |
| «¿Qué puede ver?» con los tres campos como chips | `ElegirSecciones` de MATU-50, tal cual: «Siempre ve» y las secciones agregadas | ADR-028, MATU-49 §6 |
| Sin casilla de aviso al relevo | Casilla «Le avisé a `{nombre}`…» obligatoria antes de crear | Decisión 34 (D2) |
| Sin el recordatorio de «anotar o fotografiar» | Visible bajo lo que ve | `lenguaje.md` 9, y ADR-029 lo da por mostrado |
| Valores precargados («Rosa», «+56 9 5555 0137») | Campos vacíos | Datos de la persona, no de la demo |
| Ícono del enlace en un cuadrado `pino` macizo, más el botón macizo | Cuadrado en `rocio` con el ícono `turquesa` | Un solo macizo por pantalla (ESPEC-ADR-027 6.3 ya lo pedía como criterio) |
| «Enviar el enlace por WhatsApp» | «Enviar el enlace» con la hoja de compartir del sistema, o «Copiar el enlace» | D1 |
| El fallback de nombre era «el relevo» | «quien te reemplaza» | `lenguaje.md` 4: en la app se dice «quien te reemplaza» |
| Ayudas y detalles en `text-sm` | `text-base` | Nada relevante bajo 1 rem |
| `Etiqueta` con tonos `pino` y `atenta` | El `Etiqueta` de `web/` suma los tonos `activo` y `atenta` (4.5) | Hoy solo tiene `neutro` y `ok` |
| `GrupoOpciones forma="chips"` y `Stepper` | Se copian de `Demo/src/components/Ui.tsx` a `web/src/familia/ui.tsx` | No existen en `web/` |

---

## 2. Rutas y cómo se llega

### 2.1 Rutas nuevas

| Ruta | Pantalla | `<title>` | Quién |
|---|---|---|---|
| `/compartir` | Crear un enlace (sección 3) | «Compartir · MATU» | `admin`, `cuidador` |
| `/compartir/listo` | El PIN, una sola vez (sección 4) | «Enlace creado · MATU» **[PROPUESTO]** | `admin`, `cuidador` |
| `/compartir/enlaces` | Enlaces (sección 5) | «Enlaces · MATU» | `admin`, `cuidador` |

- Ninguna ruta lleva el nombre del relevo, el id del acceso, el token ni el PIN.
- Las tres marcan «Compartir» como actual en la navegación (`seccionDe` de `Shell.tsx` pasa de `ruta === '/compartir'` a `ruta.startsWith('/compartir')`). Lo mismo en `redireccion` de `AppFamilia.tsx`: un `pagador` u `observador` que escribe cualquiera de las tres va a su inicio.
- `<title>` nunca lleva el nombre del relevo ni el de la persona (MATU-39 2.5).
- **Sale** la pantalla de MATU-39 5.5 («Pronto vas a poder compartir…») y su texto.

### 2.2 Las dos vistas de la sección

Arriba de cada `h1` de `/compartir` y `/compartir/enlaces`, en el `antes` de `Pagina`, va `Pestanas` copiada de `Demo/src/familia/Shell.tsx` con estos cambios: son **enlaces** (`<a href>` con `navegar`), no botones; `aria-label="Vistas de Compartir"` **[PROPUESTO]**; activa `border-turquesa text-turquesa` y `aria-current="page"`; `min-h-12`.

```
 Compartir   Enlaces
 ━━━━━━━━━              borde inferior de 3 px en la activa, más negrita: no solo color
```

`/compartir/listo` no lleva pestañas: es un momento, no una vista. Lleva sus propios botones de salida (4.3).

### 2.3 Las puertas de entrada

| Desde | Qué | Lleva a |
|---|---|---|
| Navegación (MATU-39 2.2) | «Compartir» con `Share2` | `/compartir` |
| La ficha con los tres campos listos (MATU-39 3.6) | Botón `variante="texto"` «Compartir con un relevo» **[L 6.1]** bajo los campos | `/compartir` |
| Guardado de un campo (MATU-39 3.7) | «Compartir con un relevo» **[L 6.1]**. Con campos por llenar: secundario («Seguir con…» es el principal). Con la ficha completa: **principal**, y «Ver los campos» pasa a secundario (cambia MATU-39 3.7, que lo dejaba principal porque Compartir no existía) | `/compartir` |
| Guardado de una sección con enlaces activos (MATU-49 4.4, L 14.3 «Quien ya tiene un enlace no la verá…») | Botón `variante="texto"` «Crear un enlace nuevo» **[DEMO]** al lado del texto | `/compartir` |
| Quién la vio, vacío (MATU-45 5.2) | «Compartir la ficha» secundario | `/compartir` |
| Quién la vio, línea `bloqueo` (MATU-45 4.3) | «Crear un enlace nuevo» de texto | `/compartir` |
| Quién la vio, presentación sin apertura (MATU-45 4.3) | Se agrega la oración «Si te preocupa, puedes cortarlo desde Enlaces.» **[L 15]**, con «Enlaces» como enlace en línea | `/compartir/enlaces` |
| Quién la vio, columna «Quién puede verla ahora» (MATU-45 4.2, D4 resuelta) | Secundario «Ver y cortar enlaces» | `/compartir/enlaces` |
| Enlaces, cada tarjeta | «Ver cuándo la abrió» de texto (MATU-45 2) | `/ficha/quien-la-vio` |

Las puertas de Quién la vio hacia Compartir y Enlaces solo se muestran a `admin` y `cuidador`. El `pagador` con `puede_ver_plan` ve la columna «Quién puede verla ahora» (la API le responde la lista sin el teléfono) **sin** el botón «Ver y cortar enlaces» y sin la oración de Enlaces.

### 2.4 «Quién puede verla ahora» en Quién la vio (cierra la D4 de MATU-45)

- **Lugar en la pantalla (cambia en la revisión visual del 04-11).** Es la respuesta a «¿quién la puede ver ahora?» y no puede quedar debajo de todo el registro:
  - La cuadrícula de Quién la vio parte en `@3xl/main:` (48 rem = 816 px), no en `@4xl/main:`. Así, a 1280 px con la navegación lateral (un contenedor de unos 906 px), la columna ya va a la derecha. Columnas `@3xl/main:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]`, `gap-10`.
  - Mientras la pantalla tenga una sola columna (bajo `@3xl/main:`, que con la cuadrícula nueva es lo mismo que «bajo `@4xl/main:`» de antes en el teléfono y con texto al 200 %), «Quién puede verla ahora» va **antes** del registro, entre la bajada y el primer día. Se resuelve con el orden del DOM, de modo que el foco y el lector de pantalla sigan el mismo orden que se ve: la `section` va primero en el DOM y, en ancho, pasa a la segunda columna con `@3xl/main:col-start-2 @3xl/main:row-start-1`. Nada de `order-*` que separe el orden visual del de lectura.
  - En una columna lleva debajo `border-b border-linea pb-6`, para separarla del registro.
- Pide `GET …/plan/accesos-relevo?estado=vigente&limite=100` al cargar la pantalla (no se guarda entre visitas).
- Una fila por enlace activo, como el esquema de MATU-45 4.1: `border-l-4 border-turquesa bg-hoja px-4 py-3`, `{nombre_relevo}` en `font-bold` y «vence en `{restante}`» **[DEMO]** en `text-base text-tenue tabular-nums` (5.3). `flex flex-wrap`, para que se apile en angosto.
- Sin enlaces activos: «Nadie tiene un enlace activo ahora.» **[PROPUESTO]** en `text-base text-tenue`. El botón «Ver y cortar enlaces» se queda (en Enlaces se ven los anteriores).
- Error: en lugar de las filas, «No pudimos traer los enlaces. Revisa tu conexión e inténtalo de nuevo.» **[PROPUESTO]** y «Intentar de nuevo» **[L 15]**, secundario. Nunca se esconde la columna en silencio: no saber quién la puede ver no es lo mismo que nadie.

---

## 3. Crear un enlace (`/compartir`)

**Objetivo:** que Carmen comparta la ficha con Rosa, solo lo que Rosa necesita y por el tiempo justo, en menos de un minuto.

**Jerarquía:**
1. El título «Compartir» y la bajada: cómo funciona en una frase.
2. Quién y su teléfono.
3. Lo que ve (siempre lo mismo, más lo que Carmen elija), hasta cuándo, para qué y el aviso a Rosa.
4. «Crear enlace», el único `turquesa` macizo.
5. En pantalla ancha, a la derecha: la hoja tal como la verá Rosa.

### 3.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ (cabecera de MATU-39)              │
├────────────────────────────────────┤
│ Compartir   Enlaces                │  pestañas, 48 px
│ ━━━━━━━━━                          │
│ Compartir                          │  h1 titular text-3xl
│ Quien te reemplaza recibe un       │  bajada, text-tenue
│ enlace por WhatsApp y el PIN se lo │
│ dictas tú. El enlace vence solo y  │
│ lo puedes cortar antes.            │
│                                    │
│ ¿Quién te va a reemplazar?         │
│ [                              ]   │
│ Su teléfono                        │
│ [                              ]   │
│ Para enviarle el enlace y poder    │
│ contactarle.                       │
│                                    │
│ Siempre ve                         │  ┐
│ ✓ Su día, Si se altera y A quién   │  │ ElegirSecciones (MATU-50),
│   llamar.                          │  │ tal cual
│ ¿Qué más puede ver?                │  │
│ Elige las secciones que le sirven. │  │
│ [☐ Quién es] [☐ Cómo hablarle]     │  │
│ ┌──────────────────────────────┐   │  │
│ │[☐] Incluir Sus remedios      │   │  │
│ │    Quien te reemplaza verá…  │   │  │
│ └──────────────────────────────┘   │  ┘
│ A quién llamar está vacío: Rosa    │  solo si hay campos vacíos
│ verá «Sin completar».              │
│ Comparte solo lo que necesita para │  recordatorio, text-tenue
│ cuidar a María. Quien recibe el    │
│ enlace puede anotar o fotografiar  │
│ lo que lee, y MATU no puede        │
│ impedirlo.                         │
│                                    │
│ ¿Hasta cuándo?                     │
│ (◉ 24 horas) (○ Fin de semana)     │  chips de opción única
│ (○ Otra cantidad de días)          │
│ ◷ Vence el 05/11/2026 a las 14:20  │
│                                    │
│ ¿Para qué lo compartes?            │
│ (◉ Salgo unas horas)               │
│ (○ Fin de semana fuera)            │
│ (○ Turno de noche) (○ Otro motivo) │
│                                    │
│ ┌──────────────────────────────┐   │
│ │[☐] Le avisé a Rosa que MATU  │   │  casilla obligatoria
│ │    guarda su nombre y su     │   │
│ │    teléfono para enviarle la │   │
│ │    ficha                     │   │
│ └──────────────────────────────┘   │
│                                    │
│ [ ⛓ Crear enlace ]                 │  único `turquesa` macizo
│                                    │
│ Lo que verá Rosa                   │  la hoja, debajo en el teléfono
│ ┌──(imán)───────────────────────┐  │
│ │ …                             │  │
├────────────────────────────────────┤
│ [Ficha] [Insumos] [Compartir]      │  barra fija
└────────────────────────────────────┘
```

### 3.2 Pantalla ancha (`@4xl/main:` y más)

```
┌──────────────┬───────────────────────────────────────────────────────────────────┐
│ (navegación) │ Compartir   Enlaces                                               │
│              │ Compartir                                                         │
│              │ Quien te reemplaza recibe un enlace…            (max-w-prose)     │
│              │                                                                   │
│              │ ┌ Datos del enlace ──────────────────┐ ┌ Lo que verá Rosa ──────┐ │
│              │ │ ¿Quién te va…?     Su teléfono      │ │ ┌──(imán)───────────┐  │ │
│              │ │ [Rosa         ]    [+56 9 …      ]  │ │ │ Su día            │  │ │
│              │ │ Siempre ve / ¿Qué más puede ver?    │ │ │ Si se altera      │  │ │
│              │ │ ¿Hasta cuándo? · ¿Para qué…?        │ │ │ A quién llamar    │  │ │
│              │ │ [☐] Le avisé a Rosa…                │ │ │ ─────────         │  │ │
│              │ │ [ Crear enlace ]                    │ │ │ Quién es          │  │ │
│              │ └─────────────────────────────────────┘ │ └───────────────────┘  │ │
│              │                                         └────────────────────────┘ │
└──────────────┴───────────────────────────────────────────────────────────────────┘
```

- Dos columnas `@4xl/main:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]`, `gap-10`, como la ficha (MATU-39 3.6). La derecha es `@4xl/main:sticky @4xl/main:top-4 self-start`.
- **Bajo `@4xl/main:`** (también a 1280 px con la navegación lateral, donde el contenedor mide unos 906 px y la vista previa cae bajo el formulario), el contenedor de la vista previa («Lo que verá…» y la hoja) lleva `max-w-prose`: se lee como una hoja y no se estira a todo el ancho con el imán perdido al centro. Desde `@4xl/main:` el ancho lo fija la columna de 26 rem (`@4xl/main:max-w-none`). Cambia en la revisión visual del 04-11.
- Nombre y teléfono en dos columnas desde `@2xl/main:grid-cols-2`; la ayuda del teléfono va debajo de su campo y los dos `input` quedan a la misma altura (ESPEC-ADR-027 6.2).
- Todo el formulario en `max-w-3xl`. Botón al ancho de su texto, nunca de ancho completo.
- A 1920 px la página sigue en `max-w-7xl` centrada (MATU-39 2.1).

### 3.3 Componentes, en orden

| Pieza | Componente | Detalle |
|---|---|---|
| Pestañas | `Pestanas` (2.2) | — |
| Título y bajada | `Pagina` de `web/src/familia/ui.tsx` | `titulo` «Compartir» **[L 9, sección]** · `bajada` «Quien te reemplaza recibe un enlace por WhatsApp y el PIN se lo dictas tú. El enlace vence solo y lo puedes cortar antes.» **[L 9]** (si D1 cambia el canal, «por WhatsApp» lo revisa Jorge) |
| Nombre | `CampoTexto` | «¿Quién te va a reemplazar?» **[L 9]** · `autoComplete="off"`, `maxLength={60}` (el contrato admite 60), una línea |
| Teléfono | `CampoTexto` | «Su teléfono» **[L 9]** · `type="tel"`, `inputMode="tel"`, `autoComplete="off"` · ayuda «Para enviarle el enlace y poder contactarle.» **[L 9]** · `placeholder` ninguno (la ayuda y el error ya dan el ejemplo) |
| Lo que ve | `ElegirSecciones` de `SeccionesCompartir.tsx`, **sin cambios** | Con `agregadas = seccionesAgregadas(ficha)` y el estado de `useEleccionSecciones()`. Va entre el teléfono y «¿Hasta cuándo?» (comentario del archivo, punto 1) |
| Campos vacíos | `p text-base text-tenue` | Solo si alguno de los tres campos está vacío (3.4) |
| Recordatorio | `p text-base text-tenue max-w-prose` | 3.4. Siempre visible. Sin ícono ni caja: no es una advertencia, es una regla de la casa |
| Vigencia | `GrupoOpciones forma="chips"` (copiar de la demo) | Leyenda «¿Hasta cuándo?» **[L 9]** · opciones «24 horas» · «Fin de semana» · «Otra cantidad de días» **[DEMO]** · elegida de partida «24 horas» |
| Días | `Stepper` (copiar de la demo) | Solo con «Otra cantidad de días». «¿Cuántos días?» y ayuda «Hasta 30 días.» **[L 9]** · unidad «días» **[DEMO]** · 1 a 30, de partida 3. Ayuda en `text-base` (la demo usa `text-sm`) |
| Vence | `p flex items-center gap-2` con `Clock3` (`text-turquesa`, `aria-hidden`) | «Vence el `{DD/MM/AAAA}` a las `{HH:MM}`» **[DEMO]**, fecha y hora en `<b class="cifras">` separadas (DISENO.md 2). Se recalcula al cambiar la opción o los días. `aria-live="polite"` |
| Motivo | `GrupoOpciones forma="chips"` | «¿Para qué lo compartes?» · «Salgo unas horas» · «Fin de semana fuera» · «Turno de noche» · «Otro motivo» **[L 9]** · siempre una elegida, de partida «Salgo unas horas» (ESPEC-ADR-027 6.3). **Chips al ancho de su texto, igual que las vigencias:** `GrupoOpciones` sin `columnas` (`inline-flex max-w-full`, en fila con `flex-wrap`), nunca una cuadrícula de pastillas de ancho completo. En angosto y con texto al 200 % se apilan solas, una por renglón, porque no caben dos (revisión visual del 04-11: a 1920 los motivos salían en 2 columnas de ancho completo, distintos de las vigencias) |
| Aviso a Rosa | Casilla en bloque, **la misma piel** que «Incluir Sus remedios» de `ElegirSecciones`: `label` `flex min-h-12 items-start gap-3 rounded border border-borde bg-hoja p-4`, `input type="checkbox"` visible `size-6 accent-turquesa`, texto `font-bold` | «Le avisé a `{nombre}` que MATU guarda su nombre y su teléfono para enviarle la ficha» **[CONTRATO, decisión 34]** (D2). **Desmarcada cada vez** que se abre la pantalla. En angosto, la casilla arriba del texto (`angosto:flex-col`), como la de remedios |
| Confirmación de remedios | `ConfirmacionRemedios` de `SeccionesCompartir.tsx`, **sin cambios** | MATU-49 6.3. Justo encima del botón |
| Botón | `Boton` principal con `Link2` | «Crear enlace» **[DEMO]** · ocupado «Creando el enlace…» **[PROPUESTO]** |
| Vista previa | `HojaFicha` con `HojaSeccion` de `ui.tsx` | Título `h2` «Lo que verá `{nombre}`» **[DEMO]**; sin nombre, «Lo que verá quien te reemplaza» **[PROPUESTO]**. Los tres campos siempre y **solo** las secciones marcadas, en el orden fijo, al día al marcar. Sus remedios con su aviso (MATU-49 5) |

`{nombre}` en todos los textos = lo escrito en «¿Quién te va a reemplazar?», sin espacios al borde. Si está vacío: «quien te reemplaza» **[PROPUESTO]** (la demo decía «el relevo»).

### 3.4 Textos que se arman

- **Campos vacíos** **[DEMO]**: «`{campos}` está vacío: `{nombre}` verá «Sin completar».» con un campo, y «`{campos}` están vacíos: …» con dos o tres. `{campos}` con sus títulos, en el orden fijo, unidos con comas e «y» («Si se altera y A quién llamar»). La demo lo pone en `text-sm`: aquí `text-base`. Va **bajo** `ElegirSecciones`, no adentro (el componente no se toca).
- **Recordatorio** **[L 9, ajuste PROPUESTO por D3]**: «Comparte solo lo que necesita para cuidar a `{nombre_pila}`. Quien recibe el enlace puede anotar o fotografiar lo que lee, y MATU no puede impedirlo.» (`lenguaje.md` dice «para cuidarla»).

### 3.5 Al tocar «Crear enlace»

Validación en el cliente, **al enviar**, nunca mientras escribe. Los errores van bajo su campo con `MensajeError` y `aria-describedby`, y el foco va al **primero** con error, en este orden:

| Qué | Mensaje |
|---|---|
| Nombre vacío | «Escribe el nombre de quien te reemplaza.» **[L 8]** |
| Teléfono que no es celular de Chile (mismo patrón del contrato: `^(\+?56 ?)?9( ?[0-9]){8}$`) | «Escribe un celular de Chile, por ejemplo +56 9 5555 0137.» **[L 8]** |
| Casilla sin marcar | «Marca que le avisaste a `{nombre}` para crear el enlace.» **[PROPUESTO]**. Con error, el borde de la caja pasa a `border-pronto` **y** aparece el mensaje con `CircleAlert` (no solo el color) |

Si todo está bien:
1. Si «Incluir Sus remedios» está marcada: se abre `ConfirmacionRemedios` y **no** se pide nada a la API hasta «Sí, crear el enlace» (MATU-49 6.3 y 6.5). «Crear enlace» se oculta mientras está abierta. Si cambia el nombre o la vigencia, se cierra.
2. `POST /v1/personas-cuidadas/{persona_id}/plan/accesos-relevo` con `X-Grupo-Id` y este cuerpo: `nombre_relevo`, `telefono_relevo`, `secciones_adicionales: eleccion.paraEnviar`, `expira_en`, `motivo`, `relevo_informado: true`. **Sin `campos`** (deprecado).
   - `expira_en` se calcula **en el momento de enviar**, en hora de Chile: «24 horas» = ahora + 24 h; «Fin de semana» = el domingo siguiente a las 23:59 (si hoy es domingo, el de la semana siguiente, como la demo); «Otra cantidad de días» = ahora + `{n}` × 24 h. Con 30 días se resta un minuto, para no chocar con el máximo del servidor por la diferencia de relojes.
   - `motivo`: «Salgo unas horas» → `salgo_unas_horas`, «Fin de semana fuera» → `fin_de_semana_fuera`, «Turno de noche» → `turno_de_noche`, «Otro motivo» → `otro`.
3. Mientras: el botón (o «Sí, crear el enlace») en ocupado, `aria-busy`. Los campos no se borran.
4. **201:** el PIN y lo demás de la respuesta pasan **en memoria** a `/compartir/listo`, con `navegar('/compartir/listo', { reemplazar: true })`: «Atrás» no vuelve al formulario lleno (no se crea un segundo enlace sin querer).

### 3.6 Estados de `/compartir`

| Estado | Qué se ve |
|---|---|
| Cargando la ficha (la pantalla la necesita para las secciones y los campos vacíos) | MATU-39 5.1: «Cargando…» **[PROPUESTO en MATU-39]** pasados 400 ms, `role="status"`, donde va el formulario. Las pestañas y el título se ven desde el principio |
| Error de red al cargar | MATU-39 5.2: `Nota tono="pronto"` con `WifiOff` y «Volver a intentar» |
| Ficha 403 `sin-consentimiento` o `revision-vencida` | En lugar del formulario, la pantalla grande de MATU-39 3.9 con el texto de L 6.4 o 6.4b. **La pestaña «Enlaces» sigue disponible:** cortar siempre se puede (decisión 18) |
| Ficha sin secciones agregadas | `ElegirSecciones` ya no muestra «¿Qué más puede ver?» (MATU-50). Nada más cambia |
| Error en un campo (cliente) | 3.5 |
| 422 del `POST` | Por `errores[].campo` y `errores[].tipo`, nunca el `mensaje` de la API: `nombre_relevo` y `telefono_relevo` → los textos de 3.5 · `relevo_informado` → el de la casilla · `expira_en` `vigencia_maxima` → «El enlace puede durar como máximo 30 días.» **[L 8]** · `expira_en` `vigencia_pasada` → «Esa fecha ya pasó. Elige de nuevo hasta cuándo.» **[PROPUESTO]**, bajo «¿Hasta cuándo?» · `secciones_adicionales` `seccion_no_agregada` → se vuelve a leer la ficha y, sobre el botón, `Nota tono="atenta"`: «Otra persona quitó una sección mientras compartías. Revisa qué más puede ver y vuelve a crear el enlace.» **[PROPUESTO]**; lo elegido que sigue existiendo queda marcado · cualquier otro (`duplicado`, `motivo`) es un defecto: texto general de L 8 |
| 403 del `POST` (la autorización cambió mientras tanto) | La pantalla de L 6.4 o 6.4b, como arriba. Lo escrito en el formulario se pierde: son datos de Rosa, no de la ficha, y no se guardan en ninguna parte |
| 404 del `POST` | L 8 `no-encontrado`, `Nota tono="pronto"` sobre el botón |
| 503 (falta la clave del PIN: compartir falla cerrado) | `Nota tono="pronto"` sobre el botón: «MATU no está disponible en este momento. Vuelve a intentarlo en unos minutos.» **[PROPUESTO en MATU-39 3.3]**. El formulario se queda |
| Red o 5xx | `Nota tono="pronto"` sobre el botón, con el texto general de L 8 («… Lo que escribiste sigue aquí.»). El formulario se queda |
| 401 | Lo resuelve el cliente de MATU-39 (sección 6). Si la entrada vence, se pierde lo escrito: no hay texto de la ficha en riesgo |

---

## 4. El PIN, una sola vez (`/compartir/listo`)

**Objetivo:** que Carmen le mande el enlace a Rosa y le dicte el PIN, sabiendo que no lo va a volver a ver.

**Jerarquía:**
1. «Enlace creado para `{nombre}`» y hasta cuándo.
2. El PIN, grande, con «Díctaselo… Solo lo verás ahora.»
3. «Enviar el enlace», el único macizo.
4. Lo que ve Rosa, el recordatorio de qué contarle y «Ver los enlaces».

### 4.1 Lo que se reutiliza de `EnlacePin` de la demo

Todo, salvo lo de 4.4 y estos cambios:
- **El cuadrado del ícono** pasa de `bg-pino text-papel` a `bg-rocio text-turquesa`. El trazo (`animate-trazo`) se queda.
- **Los dígitos** se quedan como en la demo: `digitos`, `bg-hoja text-turquesa`, `text-6xl` (en angosto `text-3xl`, `h-16`, `flex-1`), cayendo uno a uno con `animate-digito` (DISENO.md, principio 5: el único momento orquestado). Con `prefers-reduced-motion`, inmediatos. El párrafo lleva `aria-label="PIN: 4 8 2 1"` (los dígitos separados por espacio) y cada dígito es `aria-hidden`.
- **La URL** se muestra como en la demo, cortada: `{origen sin https://}/r#` y los **seis** primeros caracteres del token, seguidos de «…» (`min-w-0 truncate`, `Link2` en `text-turquesa`). Nunca el token completo en pantalla: así una captura de pantalla con el PIN no lleva también el enlace. «Enviar» y «Copiar» usan la `url` completa.
- **Lo que ve** usa `COMPARTIR_SECCIONES.loQueVe(titulos)` y, debajo, `COMPARTIR_SECCIONES.despues(nombre)` **[L 14.3]**, en `text-base text-tenue` (MATU-49 6.4), con `secciones_adicionales` de la respuesta.
- `{nombre}` = `nombre_relevo` de la respuesta; la fecha = `expira_en` de la respuesta, en hora de Chile (no la calculada en el cliente).

### 4.2 Esquema a 360 px

```
┌────────────────────────────────────┐
│ ┌──────┐                           │
│ │ ⛓    │  Enlace creado para Rosa  │  h1 titular text-3xl; el cuadrado en `rocio`
│ └──────┘                           │
│ Vence el 05/11/2026 a las 14:20.   │  text-tenue, cifras
│                                    │
│ ┌ 🔑 PIN para abrir la ficha ─────┐ │  section bg-rocio
│ │  [ 4 ] [ 8 ] [ 2 ] [ 1 ]        │ │  digitos text-6xl
│ │ Díctaselo a Rosa por teléfono.  │ │  negrita
│ │ No lo mandes junto con el       │ │
│ │ enlace. Solo lo verás ahora.    │ │
│ │ ─────────────────────────────── │ │
│ │ ☎ Cuéntale a Rosa que anotaste  │ │
│ │   su nombre y su teléfono en    │ │
│ │   MATU, y que cada vez que abra │ │
│ │   el enlace o la ficha queda    │ │
│ │   registrado.                   │ │
│ └─────────────────────────────────┘ │
│                                    │
│ ⛓ matu.cl/r#a1B2c3…                │  border-y linea
│ [ ➤ Enviar el enlace ]             │  único macizo
│ [ Copiar el enlace ]               │  secundario (solo con Compartir del sistema)
│ Ver los enlaces                    │  texto
│                                    │
│ Ve su día, si se altera, a quién   │  text-base text-tenue
│ llamar y quién es.                 │
│ Si agregas una sección después,    │
│ Rosa no la verá. Para que la vea,  │
│ crea un enlace nuevo.              │
└────────────────────────────────────┘
```

**Por qué el PIN va antes de «Enviar» en el teléfono (cambia contra la demo, D5):** enviar abre otra aplicación. Si el teléfono descarta la pestaña, el PIN se pierde. Con el PIN arriba, Carmen lo ve antes de salir.

### 4.3 Pantalla ancha (`@3xl/main:` y más)

Dos columnas `@3xl/main:grid-cols-2 gap-10`, como la demo: a la izquierda el título, «Vence…», lo que ve, la URL y los botones; a la derecha la sección del PIN. A 1920 px, en `max-w-7xl`, la sección del PIN no pasa de `max-w-lg`.

### 4.4 Enviar y copiar (D1)

| Situación | Botones |
|---|---|
| El navegador tiene `navigator.share` (teléfonos) | **«Enviar el enlace»** **[L 9.1]**, principal, ícono `Send` · «Copiar el enlace» **[L 9.1]**, secundario, ícono `Copy` · «Ver los enlaces» **[L 9.1]**, `variante="texto"` |
| Sin `navigator.share` (computador) | **«Copiar el enlace»**, principal, `Copy` · «Ver los enlaces», texto |

- **Enviar:** `navigator.share({ text })` con el texto aprobado en L 9.1: «Hola, `{nombre}`. Te comparto la ficha de cuidado en MATU: `{url}`. El PIN te lo digo por teléfono.» **[L 9.1]**. **Nunca el PIN.** El nombre que va es solo el del relevo, que es quien lo recibe. Si la persona cierra la hoja de compartir (`AbortError`), no pasa nada y no hay mensaje.
- **Copiar:** `navigator.clipboard.writeText(url)` (solo la URL). Al copiar, bajo los botones, `role="status"` con `CircleCheck` `text-ok`: «Enlace copiado. Pégalo en tu mensaje a `{nombre}`.» **[L 9.1]**. Si falla: «No pudimos copiar el enlace. Usa «Enviar el enlace».» **[L 9.1]**, o, sin `navigator.share`, se muestra la URL completa en un `input readOnly` seleccionable con la etiqueta «Enlace para `{nombre}`» **[PROPUESTO]** (es el único caso en que se ve completa).
- Apilados en el teléfono, los tres quedan alineados a la izquierda: «Ver los enlaces» sin relleno lateral (ver `Boton`, sección 6).
- Ningún botón de imprimir, descargar ni exportar (ADR-029).

### 4.5 Textos de la sección del PIN

| Pieza | Texto |
|---|---|
| Título (h1) | «Enlace creado para `{nombre}`» **[DEMO]** |
| Vence | «Vence el `{DD/MM/AAAA}` a las `{HH:MM}`.» **[DEMO]** |
| h2 de la sección | «PIN para abrir la ficha» **[DEMO]**, con `KeyRound` |
| Bajo el PIN | «**Díctaselo a `{nombre}` por teléfono.** No lo mandes junto con el enlace. Solo lo verás ahora.» **[L 9]** |
| Recordatorio | «Cuéntale a `{nombre}` que anotaste su nombre y su teléfono en MATU, y que cada vez que abra el enlace o la ficha queda registrado.» **[L 9]**, con `Phone`, `border-t border-linea pt-4 text-base` (ESPEC-ADR-027 6.3) |

El foco va al `h1` al llegar (MATU-39 2.6). **Cambia contra la demo:** el `h1` no lleva `role="status"`. Con el foco ya se anuncia, y dos anuncios a la vez se pisan.

### 4.6 El PIN ya no se puede ver

El PIN vive **solo en la memoria** de esta pantalla. Al salir de `/compartir/listo` (por cualquier camino: botón, navegación, «Atrás»), se borra. Nunca en `localStorage`, `sessionStorage`, la URL, el historial (`history.state`) ni el `<title>`.

Si se llega a `/compartir/listo` sin un PIN en memoria (recargó, volvió con «Adelante», abrió la ruta a mano), se muestra lo de `EnlacePin` de la demo sin acceso:

```
Enlace creado                                  h1 [PROPUESTO]
┃ 🔑 El PIN ya no se puede ver                 Nota tono="rocio", ícono KeyRound
┃ Por seguridad se muestra una sola vez. Si se perdió,
┃ crea un enlace nuevo y corta el anterior.
[ Crear un enlace nuevo ]  [ Ver los enlaces ]
```

Textos: título de la nota «El PIN ya no se puede ver», texto «Por seguridad se muestra una sola vez. Si se perdió, crea un enlace nuevo y corta el anterior.» **[L 9, partido en título y texto como la demo]** · «Crear un enlace nuevo» (principal, a `/compartir`) y «Ver los enlaces» (secundario, a `/compartir/enlaces`) **[DEMO]**.

---

## 5. Enlaces (`/compartir/enlaces`)

**Objetivo:** que Carmen vea quién puede abrir la ficha ahora y corte un enlace con un toque.

**Jerarquía:**
1. «Enlaces» y la bajada: cortar es inmediato.
2. Los enlaces que abren ahora, cada uno con «Cortar el enlace de `{nombre}`».
3. Los que ya no abren.
4. En pantalla ancha, a la derecha, las últimas aperturas.

**Acción principal:** ninguna en macizo cuando hay enlaces (como Quién la vio). «Cortar» es secundario: es la acción frecuente, pero una lista de botones macizos no tiene jerarquía. Solo el estado vacío tiene un principal.

### 5.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ Compartir   Enlaces                │
│             ━━━━━━━                │
│ Enlaces                            │  h1
│ Al cortar un enlace deja de abrir  │  bajada
│ de inmediato. Quien lo tenía no    │
│ recibe aviso.                      │
│                                    │
│ Abren ahora                        │  h2
│ ▌Rosa             ◷ Activo, vence  │  border-l-4 turquesa, bg-hoja
│ ▌                   en 23 h        │  Etiqueta activo (ícono + palabra)
│ ▌Ve su día, si se altera, a quién  │
│ ▌llamar y quién es. Salgo unas     │
│ ▌horas.                            │
│ ▌Lo creó Carmen. Vence el          │  text-base text-tenue
│ ▌05/11/2026 a las 14:20.           │
│ ▌[ ⛓̸ Cortar el enlace de Rosa ]    │  secundario
│ ▌Ver cuándo la abrió               │  texto
│                                    │
│ Ya no abren                        │  h2
│ ▌Rodrigo                  ⛓̸ Cortado │  border-l-4 linea
│ ▌Ve su día, si se altera y a quién │
│ ▌llamar. Turno de noche.           │
│ ▌Lo cortaron el 01/11/2026.        │
│ ▌Ver cuándo la abrió               │
│ ▌Rosa                   ! Bloqueado │  border-l-4 atenta
│ ▌Se bloqueó porque el PIN se       │
│ ▌escribió mal cinco veces.         │
│                                    │
│ [ Ver enlaces anteriores ]         │  secundario, si hay más
│ [ ⛓ Crear un enlace nuevo ]        │  secundario
│                                    │
│ Últimas aperturas                  │  h2, debajo en el teléfono
│ ◎ Rosa abrió la ficha              │
│   hoy a las 10:14                  │
│ Ver todo en Quién la vio           │
└────────────────────────────────────┘
```

### 5.2 Pantalla ancha

`grid @3xl/main:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-10` (la `Columnas izquierda="ancha"` de la demo): a la izquierda «Abren ahora», «Ya no abren» y los botones; a la derecha «Últimas aperturas». Cada tarjeta en `max-w-prose` de texto. Los botones al ancho de su texto.

**Parte en `@3xl/main:` (48 rem = 816 px), no en `@4xl/main:`** (cambia en la revisión visual del 04-11). Con `@4xl/main:`, a 1280 px con la navegación lateral (un contenedor de unos 906 px) la columna derecha no existía y «Últimas aperturas» caía debajo de todas las tarjetas. A 906 px las columnas quedan en unos 530 y 335 px: en la tarjeta, «Cortar…», «Llamar a…» y «Ver cuándo la abrió» bajan de renglón con `flex-wrap`, y eso está previsto.

### 5.3 Una tarjeta de enlace

Copia de cada `li` de `Enlaces` de la demo, contra `AccesoResumenVista`:

| Pieza | Construcción | Texto |
|---|---|---|
| Contenedor | `li flex flex-col gap-2 border-l-4 bg-hoja px-4 py-3.5` (angosto `px-2`). Borde: `border-turquesa` activo, `border-atenta` bloqueado, `border-linea` vencido o cortado | — |
| Nombre | `h3 text-lg font-bold break-words` | `{nombre_relevo}` |
| Estado | `Etiqueta` (cambia en `ui.tsx`: suma `tono="activo"` = `bg-rocio text-turquesa` y `tono="atenta"` = `bg-atenta-fondo text-atenta`; los dos con contraste de 4,5:1 en los dos temas, se mide en la revisión) | `vigente`: `Clock3` + «Activo, vence en `{restante}`» **[L 9 «Activo» + DEMO]** · `vencido`: `TimerOff` + «Vencido» · `revocado`: `Unlink` + «Cortado» · `bloqueado`: `CircleAlert` + «Bloqueado» **[L 9]**. Cada estado con **ícono distinto y palabra** |
| Lo que ve y para qué | `p text-base text-tenue` | «Ve `{campos y secciones}`.» **[L 14.3]** + « `{motivo}`.» **[L 9]**. Ojo: los accesos anteriores a MATU-50 pueden tener uno o dos campos: la frase se arma con `campos` y `secciones_adicionales` **del acceso**, en el orden fijo (hay que generalizar `loQueVe`, que hoy da por hechos los tres) |
| Detalle | `p text-base text-tenue tabular-nums` (la demo usa `text-sm`) | `vigente`: «Lo creó `{otorgado_por.nombre}`. Vence el `{DD/MM/AAAA}` a las `{HH:MM}`.» **[PROPUESTO; demo: «Creado: … Vence: …»]** · `vencido`: «Venció el `{DD/MM/AAAA}` a las `{HH:MM}`.» **[PROPUESTO; demo: «Venció: …»]** · `revocado`: «Lo cortaron el `{DD/MM/AAAA}` a las `{HH:MM}`.» **[PROPUESTO]**, con `revocado_en` · `bloqueado`: «Se bloqueó porque el PIN se escribió mal cinco veces.» **[L 9]**. Si `otorgado_por` es `null`, sin «Lo creó…» |
| Cortar | `Boton variante="secundario"` con `Unlink`, `self-start`. **Solo en `vigente`** | «Cortar el enlace de `{nombre}`» **[L 9]** · ocupado «Cortando…» **[PROPUESTO]** |
| Llamar | Solo `admin` y `cuidador` (decisión 31), en **todos** los estados. Enlace `tel:` con `claseBoton('texto')` y `Phone` (`angosto:hidden`) | «Llamar a `{nombre}`» **[L 9.1]**. Si la API ya no trae el teléfono (borrado a los 30 días, decisión 25): `p text-base text-tenue` «Ya no guardamos su teléfono.» **[L 9.1]**. El número no se ve nunca, ni en el texto ni en un `title` |
| Ver aperturas | `Boton variante="texto"`, `self-start` | «Ver cuándo la abrió» **[PROPUESTO en MATU-45]** → `/ficha/quien-la-vio` |

Los botones de texto («Llamar a…», «Ver cuándo la abrió») quedan alineados con el texto de la tarjeta, sin relleno lateral: el texto empieza en el mismo x que el nombre y el detalle (ver `Boton`, sección 6).

- **`{restante}`** = `fmtRestante` de la demo con `expira_en` y la hora actual: menos de 60 min «`{n}` min», menos de 48 h «`{n}` h», si no «`{n}` días». En `cifras` (D6). La misma función en Quién la vio (2.4).
- Nunca se muestran el número de teléfono (D4: solo «Llamar a…»), el `id`, `usos` ni `ultimo_uso_en` (Quién la vio ya cuenta las aperturas con palabras).
- Fechas en hora de Chile, `DD/MM/AAAA` y 24 h, con `fechaYHoraDeChile`.

### 5.4 Cortar

- **En el acto, sin confirmación** (como la demo): cortar no borra nada de la ficha y, si fue un error, se crea un enlace nuevo. Pero **no es optimista**: la tarjeta no cambia hasta el 204 (CLAUDE.md, agente 3, punto 4).
- `DELETE /v1/accesos-relevo/{id}` con `X-Grupo-Id`.
- **204:** en la misma tarjeta, que **no se mueve de lugar** hasta la próxima visita: la `Etiqueta` pasa a «Cortado» con `Unlink`, el borde a `border-linea`, y en lugar del botón aparece `Nota tono="ok"` (`CircleCheck`), `role="status"`, `tabIndex={-1}` con el foco: «Enlace cortado. Ya no abre para `{nombre}`.» **[L 9]**. Mismo verbo que el botón (DISENO.md, principio 6).
- **404:** la tarjeta muestra «No encontramos lo que buscas. Puede que ya no tengas acceso. Vuelve al inicio.» **[L 8]** en `Nota tono="pronto"` y se vuelve a pedir la lista.
- **Red o 5xx:** en la tarjeta, `Nota tono="pronto"`: «No pudimos cortar el enlace. Revisa tu conexión y vuelve a intentarlo. El enlace todavía abre.» **[PROPUESTO]**. La última oración es lo importante: Carmen no debe creer que lo cortó. El botón queda habilitado para reintentar.
- **401:** el cliente de MATU-39.
- Si el enlace venció o se bloqueó mientras la pantalla estaba abierta, cortar responde 204 igual (idempotente): se muestra la misma confirmación, que sigue siendo verdad.

### 5.5 Las dos listas

- **«Abren ahora»** **[PROPUESTO]**: `GET …/accesos-relevo?estado=vigente&limite=100`. Todas en una página: nadie tiene cien enlaces activos.
- **«Ya no abren»** **[PROPUESTO]**: `GET …/accesos-relevo?limite=20`, quitando en el cliente los `vigente` (ya están arriba). Si `siguiente_cursor` no es `null`, «Ver enlaces anteriores» **[PROPUESTO]**, secundario; al pulsar, se agregan abajo, el foco va a la primera tarjeta nueva y se anuncia «Se agregaron `{n}` enlaces.» **[PROPUESTO, como L 15]**. Al final, «No hay más.» **[L 15]**. Sin desplazamiento infinito.
- El orden es el del servidor (el más nuevo arriba). El cliente no reordena.
- Sin «Ya no abren» (ningún enlace anterior), el `h2` no aparece.
- Con anteriores pero sin activos, bajo «Abren ahora»: «Ningún enlace abre ahora.» **[PROPUESTO]**.
- Debajo de las listas, «Crear un enlace nuevo» **[DEMO]**, secundario con `Link2` (la demo usaba la variante `suave`, que no existe en `web/`).

### 5.6 Últimas aperturas

`GET …/plan/aperturas?limite=4`, con la `LineaApertura` de `QuienLaVio.tsx` en su forma `completa` («hoy a las 10:14»), sin `h2` por día y sin las notas largas. Título `h2` «Últimas aperturas» **[L 4, DEMO]** y `Boton variante="texto"` «Ver todo en Quién la vio» **[DEMO]**. Vacío: «Todavía nadie ha abierto la ficha. Cuando alguien la abra, aparece aquí.» **[L 9]** en `text-base text-tenue`. Si falla, la columna muestra el error de MATU-45 5.3 sin afectar la lista de enlaces.

### 5.7 Estados de `/compartir/enlaces`

| Estado | Qué se ve |
|---|---|
| Cargando | «Cargando…» pasados 400 ms, `role="status"`, en lugar de las listas (MATU-39 5.1) |
| Vacío (ninguna de las dos listas tiene nada) | `Nota tono="rocio"` con `Link2`: «No hay enlaces todavía. Crea uno desde Compartir.» **[L 9]** y debajo `Boton` **principal** «Crear un enlace nuevo» **[DEMO]** a `/compartir`. Es el único macizo de la pantalla y solo aparece aquí |
| Error al cargar | `Nota tono="atenta"` con `CloudOff`: «No pudimos traer los enlaces. Revisa tu conexión e inténtalo de nuevo.» **[PROPUESTO]** y «Intentar de nuevo» **[L 15]**, secundario. Igual que Quién la vio (MATU-45 5.3) |
| 404 al cargar | MATU-39 5.6 (sin acceso a la ficha), sin decir por qué |
| 422 (cursor) | Solo por un defecto: como «Error al cargar», y se pide la primera página |
| Sin autorización (403 de la ficha) | La lista se ve igual: listar y cortar no exigen autorización vigente (decisión 18) |

Al volver a la pantalla se piden de nuevo las listas (nada se guarda entre visitas). Sin sondeo automático.

---

## 6. Componentes y tokens

**Ningún token nuevo.** Se usan: `papel`, `hoja`, `tinta`, `tenue`, `turquesa`, `rocio`, `linea`, `borde`, `ok`, `ok-fondo`, `atenta`, `atenta-fondo`, `pronto`, `pronto-fondo`; `titular`, `cifras`, `digitos`; `animate-trazo`, `animate-digito`, `animate-aparecer`; `max-w-prose`, `max-w-3xl`, `max-w-7xl`; variantes `telefono:`, `angosto:`, `@2xl/main:`, `@3xl/main:`, `@4xl/main:`.

| Componente | De dónde | Estados que exige esta historia |
|---|---|---|
| `Pestanas` | Copiar de `Demo/src/familia/Shell.tsx` a `web/src/familia/ui.tsx`, como enlaces | normal, foco, actual (borde de 3 px + negrita + `aria-current`) |
| `GrupoOpciones forma="chips"` | Agregar la forma de `Demo/src/components/Ui.tsx` al de `web/` | normal, foco (`outline-3 outline-turquesa`), elegido (punto lleno + `bg-rocio ring-turquesa`) |
| `Stepper` | Copiar de la demo, `pino` → `turquesa` | normal, foco, en el mínimo y el máximo (`disabled`), valor anunciado (`aria-live`) |
| `ElegirSecciones`, `ConfirmacionRemedios`, `useEleccionSecciones` | `SeccionesCompartir.tsx`, **sin cambios** | Los de MATU-49 6 |
| Casilla del aviso a Rosa | Nueva, con la piel de «Incluir Sus remedios» | desmarcada, marcada, foco, error (borde `pronto` + `MensajeError`) |
| `CampoTexto`, `MensajeError`, `Nota`, `Boton` | Ya en `web/` | Los de MATU-39 4. `Nota` usa los cuatro tonos |
| `Etiqueta` | `ui.tsx`, **suma** `activo` y `atenta` | neutro, ok, activo, atenta, siempre con ícono y palabra |
| Sección del PIN | Copiar de `EnlacePin` | con PIN; sin PIN (4.6) |
| Tarjeta de enlace | Copiar de `Enlaces` | activo, cortando (`aria-busy`), recién cortado, vencido, cortado, bloqueado, error al cortar |
| `HojaFicha`, `HojaSeccion` | `ui.tsx` | Los tres campos (vacío = «Sin completar») y solo las secciones marcadas |
| `LineaApertura` | `QuienLaVio.tsx` (exportarla) | La forma `completa` |

### 6.1 `Boton`: relleno lateral por variante (revisión visual del 04-11)

**Problema:** `BASE` de `web/src/compartido/ui/Boton.tsx` trae `px-5 angosto:px-3`. Un `className="px-0"` no lo anula: Tailwind v4 escribe `px-0` antes que `px-5` en el CSS, así que gana `px-5`, y en angosto gana siempre `angosto:px-3`. Por eso los botones de texto quedaban 21 px corridos a la derecha (25 px con el texto al 200 %) del texto que acompañan: «Ver cuándo la abrió», «Llamar a…», «Ver todo en Quién la vio», «Crear un enlace nuevo» (bloqueo y sección guardada), «Compartir con un relevo» en la ficha y «Ver los enlaces» apilado.

**Corrección**, en el componente y no en cada pantalla:
- Se saca `px-5 angosto:px-3` de `BASE`.
- `principal`, `secundario` y `peligro` llevan `px-5 angosto:px-3`, como hoy.
- `texto` y `textoPeligro` llevan `px-0`. Siguen midiendo 48 px de alto (`min-h-12` está en `BASE`), y su ancho es el del texto, siempre mayor que 48 px.
- `claseBoton('texto')` (el enlace `tel:` de «Llamar a…») queda corregido con lo mismo.
- Se quitan los `className="px-0"` sueltos de `Compartir.tsx`, `QuienLaVio.tsx` y `Ficha.tsx`: ya no hacen falta.
- El anillo de foco no cambia (3 px `turquesa`, con su `outline-offset`). Sin relleno queda pegado al texto y sigue siendo visible.

**Criterio:** en una tarjeta de Enlaces, el texto de «Ver cuándo la abrió» empieza en el mismo x que el nombre y el detalle (±1 px), a 360 px, a 1280 px y a 320 px con el texto al 200 %.

Nada escrito a mano: ni colores, ni sombras, ni tamaños fuera de la escala. La única sombra de estas pantallas es la de la hoja de la vista previa (DISENO.md, principio 1).

---

## 7. Accesibilidad (además de MATU-39 y MATU-49 §9)

- **48 × 48 px** en todo lo que se toca: pestañas, chips de vigencia y de motivo, botones del `Stepper` (`size-12`), las dos casillas en bloque, «Cortar…», «Ver cuándo la abrió», «Ver los enlaces», «Copiar el enlace».
- **Foco** visible con el anillo de 3 px `turquesa`. Al llegar a cada pantalla, al `h1`. Tras un error de validación, al primer campo con error. Tras cortar, a la confirmación. Tras «Ver enlaces anteriores», a la primera tarjeta nueva. Al abrir la confirmación de remedios, a ella (ya lo hace el componente).
- **Nada solo por color:** estados del enlace con ícono y palabra; borde de la tarjeta como refuerzo; casilla con error con borde y mensaje; pestaña activa con borde inferior y negrita.
- **El PIN** se lee como «PIN: 4 8 2 1» (dígitos separados), no como «cuatro mil ochocientos veintiuno».
- **Anuncios:** «Vence el…» con `aria-live="polite"`; confirmación de cortar y de copiar con `role="status"`; los errores del `POST`, en la `Nota` sobre el botón, con `role="alert"` una sola vez.
- **Sin desplazamiento horizontal** a 320 px con texto al 200 %: chips en una columna, las casillas con la caja arriba del texto, los dígitos del PIN con `flex-1`, la URL cortada con `truncate`, la `Etiqueta` de estado baja de renglón bajo el nombre (`flex-wrap`).
- Con `prefers-reduced-motion`, el trazo y los dígitos aparecen sin animación.
- Nada relevante bajo 1 rem: ayudas, detalles de las tarjetas y estados en `text-base`.

---

## 8. Criterios visuales verificables

1. En `/compartir` el único `turquesa` macizo es «Crear enlace» (o «Sí, crear el enlace» con la confirmación abierta). En `/compartir/listo`, «Enviar el enlace» (o «Copiar el enlace» sin compartir del sistema); el cuadrado del ícono es `rocio`. En `/compartir/enlaces` no hay ninguno, salvo el estado vacío.
2. No existe ningún control para quitar Su día, Si se altera o A quién llamar (MATU-49 6.5).
3. «Incluir Sus remedios» y «Le avisé a…» aparecen desmarcadas **cada vez** que se abre `/compartir`.
4. Con «Le avisé a…» sin marcar, «Crear enlace» no hace ninguna petición a la API.
5. El PIN no aparece en la URL, en el `<title>`, en `history.state` ni en el almacenamiento del navegador; recargar `/compartir/listo` muestra «El PIN ya no se puede ver».
6. En la pantalla del PIN nunca se ve el token completo; el texto que se comparte no lleva el PIN, ni otro nombre que el del relevo que lo recibe (L 9.1).
7. Los cuatro estados de un enlace se distinguen en escala de grises (ícono y palabra).
8. Tras tocar «Cortar el enlace de Rosa» con la red cortada, la tarjeta sigue diciendo «Activo» y el aviso dice que el enlace todavía abre.
9. Ninguna pantalla de esta historia tiene un botón, vista, estilo ni atajo para imprimir, descargar o exportar la ficha (ADR-029).
10. A 320 px con texto al 200 %, sin desplazamiento horizontal en las tres pantallas; los dígitos del PIN caben en una fila.
11. Ningún texto dice «revocar», «acceso» (salvo «cortar el acceso» ya aprobado en L 14.2), «token», «relevo» dirigido a Carmen fuera de «Compartir con un relevo», ni un término de `lenguaje.md` 3. Ningún texto asume el género de María ni de Rosa.
12. En el proyector, nombre del enlace y estado en al menos `text-lg` y `text-base`; los dígitos del PIN legibles a varios metros (`text-6xl`).

---

## 9. Textos

### 9.1 Se usan tal cual (ya en `lenguaje.md`)

L 4: «Últimas aperturas». L 6.1: «Compartir con un relevo». L 8: «Escribe el nombre de quien te reemplaza.», «Escribe un celular de Chile, por ejemplo +56 9 5555 0137.», «El enlace puede durar como máximo 30 días.», `no-encontrado` y el texto general. L 9: bajada de Compartir, preguntas del formulario, ayuda del teléfono, motivos, PIN recién creado, PIN que ya no se ve, recordatorio al crear, estados (Activo · Vencido · Cortado · Bloqueado), detalle de bloqueado, «Cortar el enlace de `{nombre}`» y «Enlace cortado. Ya no abre para `{nombre}`.», bajada de Enlaces, sin enlaces, sin aperturas. L 14.2 y 14.3: todo lo de `ElegirSecciones`, la confirmación de remedios, «Ve …» y «Si agregas una sección después…». L 15: «Si te preocupa, puedes cortarlo desde Enlaces.», «Intentar de nuevo», «No hay más.».

### 9.2 De la demo, para agregar a `lenguaje.md` 9 **[DEMO]**

«Compartir» y «Enlaces» (pestañas y títulos) · «24 horas» · «Fin de semana» · «Otra cantidad de días» · «días» · «Vence el `{fecha}` a las `{hora}`» · «`{campos}` está vacío: `{nombre}` verá «Sin completar».» / «… están vacíos: …» · «Crear enlace» · «Lo que verá `{nombre}`» · «Enlace creado para `{nombre}`» · «PIN para abrir la ficha» · «Ver los enlaces» · «Crear un enlace nuevo» · «Activo, vence en `{restante}`» · «Ver todo en Quién la vio».

### 9.3 Del contrato **[CONTRATO]**

«Le avisé a `{nombre}` que MATU guarda su nombre y su teléfono para enviarle la ficha» (decisión 34; D2).

### 9.4 **[PROPUESTO]**, para Jorge

1. Título del documento: «Enlace creado · MATU»; título de la pantalla sin PIN: «Enlace creado»
2. `aria-label` de las pestañas: «Vistas de Compartir»
3. Sin nombre escrito: «quien te reemplaza» (en «Lo que verá…», «… verá «Sin completar»», la casilla y su error)
4. «Lo que verá quien te reemplaza»
5. Recordatorio neutro: «Comparte solo lo que necesita para cuidar a `{nombre_pila}`. Quien recibe el enlace puede anotar o fotografiar lo que lee, y MATU no puede impedirlo.» (D3)
6. Error de la casilla: «Marca que le avisaste a `{nombre}` para crear el enlace.»
7. «Creando el enlace…»
8. 422 `vigencia_pasada`: «Esa fecha ya pasó. Elige de nuevo hasta cuándo.»
9. 422 `seccion_no_agregada`: «Otra persona quitó una sección mientras compartías. Revisa qué más puede ver y vuelve a crear el enlace.»
10. «Enviar el enlace» (demo: «… por WhatsApp», D1) · «Copiar el enlace» — **aprobados en L 9.1**
11. Texto que se comparte — **reemplazado por el de L 9.1:** «Hola, `{nombre}`. Te comparto la ficha de cuidado en MATU: `{url}`. El PIN te lo digo por teléfono.»
12. «Enlace copiado. Pégalo en tu mensaje a `{nombre}`.» (**versión de L 9.1**) · «No pudimos copiar el enlace. Usa «Enviar el enlace».» (L 9.1) · «Enlace para `{nombre}`» (sigue propuesto)
13. Enlaces: «Abren ahora» · «Ya no abren» · «Ningún enlace abre ahora.»
14. Detalles: «Lo creó `{nombre}`. Vence el `{fecha}` a las `{hora}`.» · «Venció el `{fecha}` a las `{hora}`.» · «Lo cortaron el `{fecha}` a las `{hora}`.»
15. «Cortando…»
16. «No pudimos cortar el enlace. Revisa tu conexión y vuelve a intentarlo. El enlace todavía abre.»
17. «No pudimos traer los enlaces. Revisa tu conexión e inténtalo de nuevo.»
18. «Ver enlaces anteriores» · «Se agregaron `{n}` enlaces.» (con 1: «Se agregó 1 enlace.»)
19. Quién la vio: «Nadie tiene un enlace activo ahora.»

### 9.5 Se retiran

- `lenguaje.md` 8, fila «Compartir, `campos`»: «Elige al menos un campo.» (ADR-028: los tres van siempre).
- `lenguaje.md` 9, «¿Qué puede ver?» en las preguntas del formulario: la reemplazan «Siempre ve» y «¿Qué más puede ver?» (L 14.3).
- MATU-39 5.5: «Pronto vas a poder compartir la ficha con quien te reemplace desde aquí.»

Revisados contra `lenguaje.md` 3: ninguno usa un término prohibido ni «revocar», «token», «sesión», «auditoría» o «registro de accesos». «Le avisé a» y «Lo creó» no llevan género.

---

## 10. Pendiente del analista

El analista normativo hace su revisión previa en paralelo. Estos puntos quedan abiertos hasta su informe; si pide un aviso o un cambio de texto, entra aquí y en `lenguaje.md` en el mismo PR, sin cambiar la composición (todas las piezas tienen lugar previsto):

1. **Texto de la casilla de la decisión 34** (D2): si basta el del contrato o debe sumar que cada apertura queda registrada y la familia la ve (`lenguaje.md` 7.5 del 03-11). Y si, con la casilla, el recordatorio de la pantalla del PIN se mantiene, se acorta o se fusiona.
2. **Canal de envío** (D1): compartir del sistema frente a `wa.me` con el token en la consulta. Y el texto que se comparte: sin PIN y sin nombres (minimización), ¿suficiente?
3. **Copiar al portapapeles:** el enlace puede quedar en el historial del portapapeles del teléfono o del computador. ¿Requiere aviso?
4. **El recordatorio de «anotar o fotografiar»** (ADR-029 lo da por visible al compartir): si su lugar (bajo lo que ve, en `text-tenue`, sin caja) alcanza o debe ser una `Nota`.
5. **«Lo creó `{nombre}`»** en cada tarjeta: el contrato ya devuelve solo el nombre de pila (decisión 35). Confirmar que mostrarlo a los demás del grupo no pide nada más.
6. **El teléfono del relevo** (D4): no se muestra. Confirmar que no hay obligación de mostrarlo ni de informar algo más a la familia sobre su borrado a los 30 días (decisión 25).
7. Cualquier aviso legal sobre **Sus remedios** al compartir, además de la confirmación ya aprobada (MATU-49 6.3).

---

## 11. Cómo la voy a revisar

Con la app funcionando contra la API y los datos sintéticos (Carmen comparte la ficha de María con Rosa; Rodrigo, otro del grupo), capturas a 360, 1280 y 1920 px, tema claro y oscuro, y a 320 px con texto al 200 %, de:

1. `/compartir` vacío, con errores de validación, con secciones y sin secciones, con remedios marcada (confirmación abierta), con campos vacíos, con «Otra cantidad de días», con cada error del `POST` (422 por campo, `seccion_no_agregada`, 403, 503, red).
2. `/compartir/listo` con PIN (también en `prefers-reduced-motion`), con y sin `navigator.share`, copiado, y recargada (sin PIN).
3. `/compartir/enlaces` vacía, con activos y anteriores, con un bloqueado, cortando, recién cortado, error al cortar, y con «Ver enlaces anteriores».
4. Quién la vio con «Quién puede verla ahora» (con y sin activos) y las puertas nuevas, como `admin` y como `pagador`.
5. Contraste de las `Etiqueta` `activo` y `atenta` y del borde de la casilla con error, en los dos temas; foco visible y 48 px en cada control nuevo.

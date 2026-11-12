# MATU-53 · App de familia: invitar a un familiar y ver el grupo · Especificación de diseño

**Versión 1.1 · 12 de noviembre de 2026** (decisiones del orquestador, por delegación de Jorge: sección 0.4) · Agente UI/UX, a pedido del orquestador · Rama `matu-42-invitar-familiar`

**Fuentes, en este orden:**
- `Demo/DISENO.md`, con la regla de MATU-93 («ningún texto bajo 17 px», PR MATU_PROYECTO #87, todavía no en esta rama: ver 0.2).
- La revisión previa del analista de MATU-42 y MATU-53 (`docs/legal/revision-previa-matu-42-53.md` del repositorio MATU), con las decisiones de Jorge del 12-11. Sus secciones 5 (textos) y 6 (accesibilidad) se usan aquí.
- `docs/lenguaje.md` del repositorio MATU, secciones 3, 7, 8, 9.1, 22, 25 y 26.
- Lo que ya existe en `web/`: `Grupo.tsx` y `textosGrupo.ts` (MATU-44 y MATU-72), `Compartir.tsx` (`EnlaceListo`, MATU-48), `Codigo.tsx` (`CampoCodigo`, MATU-57), `relevo/Marco.tsx` (MATU-23) y `ui.tsx`.
- Las especificaciones `matu-44-retirar-autorizacion.md` (el diálogo) y `matu-48-compartir.md` (el PIN y el envío).

**Marcas de los textos:**
- **[L n]**: ya está en `lenguaje.md`, sección n. Se copia tal cual.
- **[ANALISTA]**: lo propuso el analista en la sección 5 de su revisión. Entra a `lenguaje.md` (sección 33, según la fila) con la aprobación de Jorge.
- **[ANALISTA, ajustado]**: el del analista, con un cambio que se explica al lado.
- **[NUEVO]**: no está en ninguna de las dos fuentes. Lo propone esta especificación y lo aprueba Jorge antes de construir.

---

## 0. Antes de construir

### 0.1 Decisiones de Jorge que mandan aquí

| Id | Lo que cambia en la pantalla |
|---|---|
| D-42-1 a | No hay campo de correo ni de teléfono al invitar. El enlace se manda desde el teléfono, como el relevo |
| D-42-2 a | Al crear la invitación se muestra una sola vez un código de 4 dígitos, para dictar aparte. Quien la recibe tiene 5 intentos |
| D-42-3 | La duración no se elige: siempre 7 días, porque siempre hay código |
| D-42-4 a | Antes del código, quien recibe ve solo el nombre de pila de quien invita, el rol y el vencimiento |
| D-42-5 | Los cuatro roles se pueden dar, con una advertencia para «Administra el grupo». El permiso del pagador para ver la ficha va en un paso aparte (C8) |
| D-42-7 a | Sacar a alguien, o quitarle la ficha con un cambio de rol, corta sus enlaces de relevo al tiro. La confirmación dice cuántos |
| D-42-9 a | Si quien autorizó sale, la autorización sigue y se avisa (ver 0.3, P10) |
| D-42-10 a | La lista muestra solo los miembros activos. Quien salió aparece como «Alguien que ya no está en el grupo» donde se le nombre |
| D-42-13 | «Salir del grupo» entra en esta historia |
| Ajuste | Lo de los pedidos en la descripción de «Paga» se muestra solo con la capa 3 encendida (`capa3` del estado de la app) |

### 0.2 Lo que señalo al orquestador

1. **MATU-93 no está en esta rama.** El `Demo/DISENO.md` de `wt42c` todavía permite `text-sm` para lo secundario. Esta especificación sigue la regla de MATU-93: **todo texto en `text-base` o más**, sin excepción, porque estas pantallas no tienen la barra inferior. Si el PR #87 se fusiona antes, la prueba `textoMinimo17` lo hará cumplir sola.
2. **Una contradicción entre D-42-10 y el texto D-42-9 del analista.** El analista propone «La autorización la dio `{nombre}`, que ya no está en el grupo.», pero con D-42-10 (a) la API ya no devuelve el nombre de quien salió. Propongo el texto sin nombre (5.6). Además, «renuévala» no tiene pantalla: hoy no existe una ruta para renovar la autorización (L 6.4b la marca como PENDIENTE). No elijo: va como pregunta P10.
3. **Una oración del analista que no calza con su descripción.** «Con tu rol podrás: `{descripción}`.» junta un futuro en segunda persona con descripciones en tercera («Ve y cambia la ficha…»). Propongo «Tu rol: `{rol}`. `{descripción}`» (4.5). Es un ajuste de forma, no de contenido.
4. **«Salir» y «Salir del grupo».** La cabecera de la app ya tiene «Salir» (cerrar la sesión). En esta historia el botón y el título siempre dicen «Salir del grupo» completo, nunca «Salir» solo.
5. **El botón para leer de nuevo el código** (analista §6). Lo resuelvo con «Repetir el código», un botón de texto que lleva el foco al bloque del código: se ve el anillo alrededor de los dígitos y el lector los vuelve a leer (3.4). No es un botón que hable con voz sintética: no se puede asegurar sin conexión ni con la misma voz en todos los teléfonos.

### 0.3 Preguntas para el contrato

El backend escribe en paralelo `docs/api/propuestos/invitar-familiar.openapi.yaml`. Estas pantallas necesitan lo siguiente. Si algo no está, el frontend no lo inventa.

| # | Pregunta | Para qué pantalla | Lo que recomiendo |
|---|---|---|---|
| P1 | **¿En qué orden van el código y la cuenta?** El analista ordena sus textos así: presentación, código, «Para unirte, crea tu cuenta…», detalles, «Unirme» | Aceptar (4) | Ese orden: el código **antes** de pedir cuenta. Quien recibe confirma que la invitación es para ella sin crear nada, y quien tiene un enlace reenviado se detiene en el código. Exige una verificación del código **sin sesión** que cuente los intentos de la invitación (C30) y devuelva los datos de C2. La aceptación, con sesión, vuelve a mandar token y código |
| P2 | **La presentación** (`POST`, solo el token, sin sesión): ¿devuelve `nombre_pila_invita`, `rol` y `expira_en`? ¿Y en un 423, el nombre de pila para «Pídele a `{nombre_pila_invita}` una nueva»? | 4.2 y 4.7 | Sí, las tres cosas. En el 423, el nombre de pila también, porque la presentación ya lo mostró. Si no, el texto cae a «Pídele una nueva a quien te invitó.» |
| P3 | **La verificación del código**: ¿devuelve el nombre del grupo, los nombres de pila de las personas cuidadas y el rol? ¿Y `intentos_restantes` en el código malo? | 4.3 y 4.5 | Sí. Sin esos datos no hay C2 |
| P4 | **Los `type` de 410.** ¿Se distinguen vencida, ya usada y no disponible (inexistente o anulada, que C28 junta)? | 4.7 | Tres `type`: `invitacion-vencida`, `invitacion-usada` e `invitacion-no-disponible`. Si el contrato deja uno solo, se usa el texto general del analista para los tres |
| P5 | **La lista de miembros**: id de la membresía, nombre, rol, `puede_ver_plan` (solo pagador), `unido_en` y `eres_tu` (C9). ¿Trae también cuántos enlaces de relevo vigentes creó cada uno? | 5 y 6 | Sí, un `enlaces_vigentes` por miembro, visible solo para quien administra. La confirmación de sacar y la de cambiar el rol dicen «Se cortan `{n}` enlaces» (D-42-7). Si no viene, el frontend no lo calcula |
| P6 | **El `ETag` de una membresía.** Si dos personas que administran cambian el rol de la misma persona a la vez, ¿hay 412? | 6 | Sí, `If-Match` en el cambio de rol y del permiso de la ficha. Si el contrato prefiere que gane el último, la sección 6.6 (412) no se construye |
| P7 | **Las invitaciones sin usar** (solo admin): id, rol, `creada_en`, `expira_en` y el nombre de quien la creó | 5.4 | Sí. Sin contacto, porque no se guarda |
| P8 | **Anular una invitación que se acaba de usar o vencer**: ¿409 o 410? | 5.4 | 409 con un `type` propio. El texto está en 5.4 |
| P9 | **Crear la invitación**: ¿devuelve `url` (o el token), `codigo` y `expira_en`? ¿Qué responde el tope diario (C31)? | 3 | La `url` completa, el código y `expira_en`. El tope, un 429 con su `type` |
| P10 | **El aviso de D-42-9**: ¿la vista de autorizaciones dice si quien autorizó ya no está en el grupo? ¿Hay una forma de renovar? | 5.6 | Un booleano `autorizo_quien_ya_no_esta` en la vista. Lo de renovar lo decide Jorge |
| P11 | **El autor que salió** (D-42-10), en la ficha, los pedidos y las autorizaciones: ¿cómo llega? | 5.7 | `nombre: null` más `autor_activo: false`, igual en todas las rutas. El texto lo pone la pantalla |
| P12 | **«No quiero unirme»**: ¿avisa algo al servidor? | 4.5 | No. La invitación sigue hasta que venza o quien administra la anule. Así no hace falta «rechazar» (palabra que se evita, L 3.2). Lo confirma el analista |
| P13 | **Los enlaces que corta la salida por cuenta propia**: ¿la respuesta trae `enlaces_cortados`, y la lista trae los míos antes de confirmar? | 7 | Sí, como al sacar a alguien |
| P14 | **La persona sola en su grupo**: si es la única persona y administra, no puede salir (C12). ¿Es así, o puede cerrar el grupo? | 7.3 | Que no pueda, con la frase de 7.3. Cerrar el grupo no está en ninguna historia del sprint |

### 0.4 Decisiones del orquestador (12-11, v1.1)

Por delegación de Jorge, que las confirma al fusionar. **Mandan sobre 0.2 y 0.3.**

| Tema | Decisión | Dónde cambia |
|---|---|---|
| D-42-9 (0.2, punto 2) | Se acepta «La autorización la dio alguien que ya no está en el grupo. Sigue vigente.». **No** se ofrece renovar: va en MATU-69. Se muestra con `autorizo_alguien_que_ya_no_esta: true` | 5.6 |
| Ajustes de forma (0.2, punto 3, y 4.2) | Se aceptan «Tu rol: `{rol}`. `{descripción}`» y los infinitivos («para cuidar») | 4.2 y 4.5 |
| «Salir del grupo» (0.2, punto 4) | Siempre completo | 7.2 |
| 17 px (0.2, punto 1) | Todo en `text-base` o más, aunque MATU-93 no esté en esta rama | 9 |
| P1 | El código va antes de la cuenta, con una verificación sin sesión | 4.1 a 4.4 |
| P4 | Hay tres 410: vencida, usada y no disponible. Sale la fila del 410 único | 4.7 |
| P5 | `enlaces_vigentes` por miembro, solo para admin | 6.3 y 7.1 |
| P6 | Hay 412 en el cambio de rol y del permiso de la ficha | 6.6 y 6.7 |
| P11 | El autor que salió llega con `nombre: null` y `autor_activo: false` | 5.7 |
| P12 | «No quiero unirme» no llama al servidor | 4.5 |
| P13 | Salir devuelve `enlaces_cortados` | 7.2 |
| P14 | Quien está sola en su grupo no puede salir: 409, con un texto que la lleva a «Borrar sus datos» (MATU-72) | 7.3 |
| P2, P3, P7, P8, P9 | Como se propusieron en 0.3 | 3, 4 y 5.4 |
| Textos **[NUEVO]** | Aprobados por el orquestador, por delegación de Jorge. Jorge los confirma al fusionar | 11 |

---

## 1. Para quién y qué

- **Carmen administra el grupo.** Quiere sumar a su hermano Rodrigo para que pague y a Rosa para que la cubra los fines de semana, sin aprender nada nuevo: invitar se parece a compartir la ficha, con un enlace por mensaje y un número dictado por teléfono.
- **Rodrigo recibe la invitación.** Abre un enlace desde el chat, quizás sin cuenta. Antes de unirse quiere saber quién lo invita, a qué grupo y qué podrá hacer.
- **Cualquier persona del grupo** quiere ver quiénes lo forman y con qué rol, y poder salir.

**La acción principal de cada pantalla**, la única en `turquesa` macizo:

| Pantalla | Acción principal |
|---|---|
| `/grupo` (admin) | «Invitar a alguien» |
| `/grupo` (otros roles) | Ninguna. Ver el grupo no pide nada |
| `/grupo/invitar` | «Crear la invitación» |
| `/grupo/invitar/listo` | «Enviar el enlace», o «Copiar el enlace» sin la hoja de compartir del sistema |
| `/invitacion`, antes del código | «Seguir» |
| `/invitacion`, sin cuenta | «Crear mi cuenta» |
| `/invitacion`, confirmar | «Unirme al grupo» |
| Diálogos que dan algo (permiso de la ficha) | El botón que confirma, en `turquesa` |
| Diálogos que quitan algo (sacar, salir, anular, bajar de rol) | El botón que confirma, en `pronto` macizo (`peligroPrincipal`), nunca `turquesa` |

---

## 2. Rutas

| Ruta | Quién | Marco | Cómo se llega |
|---|---|---|---|
| `/grupo` | Todo el grupo | El de la app (MATU-39) | La sección Grupo, como hoy |
| `/grupo/invitar` | Solo admin. Los demás roles se redirigen a `/grupo` | El de la app | «Invitar a alguien» en `/grupo` |
| `/grupo/invitar/listo` | Solo admin | El de la app | Después de crear. Sin código en memoria, muestra 3.6 |
| `/invitacion#<token>` | Cualquiera, con o sin sesión | **Público**, sin navegación (2.1) | El enlace del mensaje |

Ninguna ruta lleva el id de una persona, de una membresía ni de una invitación. El miembro elegido para cambiar el rol, sacarlo o darle la ficha vive en el estado del diálogo, como en MATU-44.

### 2.1 `/invitacion` vive dentro de la app de la familia

Es una ruta de `AppFamilia`, **no** una rama aparte de `main.tsx` como `/r`. La razón es la C25: el token y el código viven solo en memoria mientras la persona crea su cuenta o entra, y eso exige que `/crear-cuenta` y `/entrar` sean navegaciones de la misma aplicación, sin recargar.

- Se muestra igual con sesión y sin ella. **No usa el `Shell`**: sin barra lateral, sin barra inferior y sin selector de persona. Usa un marco público con la forma del de `relevo/Marco.tsx`: la franja `hoja` con el logo, «MATU», el rótulo «Invitación a un grupo de cuidado» **[NUEVO]** en `text-tenue` y el `DistintivoPiloto`.
- El título de la pestaña: «Invitación a un grupo de cuidado · MATU» **[NUEVO]**. En un estado que no sigue, `{título del estado} · MATU`, como L 7.1. Nunca el nombre de nadie ni el token.
- **El token en el fragmento.** Se lee de `location.hash` al montar y pasa a memoria. Se limpia con `history.replaceState(null, '', '/invitacion')` en el primero de estos momentos:
  1. el código se verificó bien (4.3);
  2. la persona toca «Crear mi cuenta» o «Entrar con mi cuenta» (4.4), **antes** de navegar, para que la entrada `/invitacion#…` no quede en el historial;
  3. la página llega a un estado que no sigue (410, 423).

  Mientras está en la pantalla del código, el fragmento se queda: si recarga ahí, la invitación vuelve a abrir, igual que el PIN del relevo.
- **Nada en el almacenamiento del navegador.** Ni el token, ni el código, ni el nombre de quien invita, ni el del grupo: ni en `localStorage`, ni en `sessionStorage`, ni en `history.state`, ni en el `<title>`. Si recarga después de limpiar el fragmento, se ve 4.8.
- **El regreso desde el alta.** Con una invitación en memoria, «Cuenta creada» y «Entrar» llevan a `/invitacion` (paso de confirmar), **nunca** a `/empezar/grupo`. Se usa el mismo mecanismo de `destino` que ya existe para volver a una ruta después de entrar.

---

## 3. Invitar (`/grupo/invitar` y `/grupo/invitar/listo`)

**Objetivo, desde Carmen:** sumar a alguien al grupo eligiendo qué podrá hacer, y mandarle el enlace sabiendo que sin el código no entra.

### 3.1 Jerarquía de `/grupo/invitar`

1. «Invitar a alguien al grupo».
2. «¿Qué podrá hacer?» con los cuatro roles, cada uno con lo que permite.
3. La advertencia si elige «Administra el grupo», y el recordatorio de contarle a la persona cuidada.
4. «Crear la invitación», con cuánto dura.
5. Lo que verá quien la abra (en pantalla ancha, a la derecha).

### 3.2 Esquema a 360 px

```
┌────────────────────────────────────┐
│ ‹ Volver a Grupo familiar          │  Volver (ui.tsx), texto
│                                    │
│ Invitar a alguien al grupo         │  h1 titular text-3xl, recibe el foco
│ Le mandas un enlace desde tu       │  bajada text-base text-tenue
│ teléfono y le dictas un código     │  max-w-prose
│ aparte. No guardamos su correo     │
│ ni su teléfono.                    │
│                                    │
│ ¿Qué podrá hacer?                  │  fieldset > legend text-lg font-bold
│ ┌────────────────────────────────┐ │
│ │ ○ Administra el grupo          │ │  GrupoOpciones forma="lista"
│ │   Ve y cambia todo, comparte   │ │  nombre font-bold
│ │   la ficha, invita y cambia    │ │  detalle text-base text-tenue
│ │   los permisos.                │ │  (aria-describedby)
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ ○ Cuida                        │ │
│ │   Ve y cambia la ficha y los   │ │
│ │   insumos, y comparte la ficha │ │
│ │   con quien te reemplaza.      │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ ○ Paga                         │ │
│ │   Ve los insumos y paga los    │ │
│ │   pedidos. Ve la ficha solo si │ │
│ │   quien administra le da       │ │
│ │   permiso.                     │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ ○ Se informa                   │ │
│ │   Ve el nombre de María y sus  │ │
│ │   insumos. No ve la ficha.     │ │
│ └────────────────────────────────┘ │
│                                    │
│ ┃ ⚠ Podrá invitar, cambiar        │  Nota tono="atenta", solo con
│ ┃   permisos y sacar a otras       │  «Administra el grupo» elegido
│ ┃   personas, también a ti.        │
│                                    │
│ ┃ ☎ Si María puede comprenderlo,  │  Nota tono="rocio", siempre
│ ┃   cuéntale que invitaste a otra  │
│ ┃   persona.                       │
│                                    │
│ Vale 7 días y sirve una sola vez.  │  text-base text-tenue
│ [ Crear la invitación ]            │  principal, único macizo
│                                    │
│ Lo que verá al abrir el enlace     │  h2 text-lg font-bold
│ ┌────────────────────────────────┐ │  bg-hoja ring-1 ring-linea
│ │ Carmen te invita a su grupo de │ │  rounded-xl p-4
│ │ cuidado en MATU, para cuidar.  │ │  la frase de 4.2, con el rol
│ │ Escribe el código que te dijo. │ │  elegido. Sin rol: «…para el
│ └────────────────────────────────┘ │  rol que elijas.»
└────────────────────────────────────┘
│ Ficha  Insumos  Compartir  Grupo   │  barra fija
```

**Ningún rol elegido de partida.** Elegir qué podrá hacer otra persona con los datos de María es una decisión, no un valor por omisión. Si toca «Crear la invitación» sin elegir, no se hace la petición, aparece «Elige qué podrá hacer.» **[NUEVO]** bajo la `legend` en `MensajeError`, y el foco va a la primera opción.

### 3.3 Pantalla ancha (`@3xl/main:` y más)

```
┌──────────────┬──────────────────────────────────────────────────────────────┐
│ (M) MATU     │ ‹ Volver a Grupo familiar                                    │
│ Ficha        │ Invitar a alguien al grupo                                   │
│ Insumos      │ Le mandas un enlace desde tu teléfono y le dictas un código  │
│ Compartir    │ aparte. No guardamos su correo ni su teléfono.               │
│ Grupo famil. │                                                              │
│              │ ¿Qué podrá hacer?                 Lo que verá al abrir el    │
│              │ (○) Administra el grupo           enlace                     │
│              │ (○) Cuida                         ┌────────────────────────┐ │
│              │ (●) Paga                          │ Carmen te invita a su  │ │
│              │ (○) Se informa                    │ grupo de cuidado en    │ │
│              │                                   │ MATU, para pagar.      │ │
│              │ ┃ Si María puede comprenderlo…    │ Escribe el código que  │ │
│              │ Vale 7 días y sirve una sola vez. │ te dijo.               │ │
│              │ [Crear la invitación]             └────────────────────────┘ │
└──────────────┴──────────────────────────────────────────────────────────────┘
```

- `grid grid-cols-1 gap-10 @3xl/main:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]`, dentro de `max-w-5xl`. A la izquierda lo que se hace, a la derecha el resultado (DISENO.md 3).
- La columna derecha es `@3xl/main:sticky @3xl/main:top-6`. A 1920 px no pasa de 22 rem.
- El botón, al ancho de su texto.

### 3.4 Al crear (`/grupo/invitar/listo`)

**Jerarquía:**
1. «Invitación lista» y hasta cuándo vale.
2. El código, grande, y que se dicta por teléfono.
3. «Enviar el enlace».
4. «Volver a Grupo familiar».

```
┌────────────────────────────────────┐
│ ┌──────┐                           │
│ │ ✉    │  Invitación lista         │  h1 titular text-3xl, recibe el foco
│ └──────┘                           │  cuadrado bg-rocio text-turquesa, MailPlus
│ Vale una sola vez, hasta el        │  text-base, fecha y hora en dos `cifras`
│ 19/11/2026 a las 21:30.            │
│ Para cuidar.                       │  el rol, en la forma de 4.2, text-tenue
│                                    │
│ ┌ 🔑 Código para unirse ─────────┐ │  section bg-rocio rounded-xl p-4
│ │  [ 4 ] [ 7 ] [ 2 ] [ 9 ]       │ │  digitos text-6xl, sin animación
│ │ Díselo por teléfono, no lo     │ │  font-bold la primera oración
│ │ escribas en el mensaje. No lo  │ │
│ │ volverás a ver.                │ │
│ │ Repetir el código              │ │  Boton texto
│ └────────────────────────────────┘ │
│                                    │
│ ⛓ matu.cl/invitacion#a1B2c3…       │  border-y linea, truncate
│ [ ➤ Enviar el enlace ]             │  principal, Send
│ [ Copiar el enlace ]               │  secundario, Copy
│ Volver a Grupo familiar            │  texto
└────────────────────────────────────┘
```

- **Se reutiliza `EnlaceListo` de `Compartir.tsx`** con estos cambios: el ícono es `MailPlus`, el h2 de la sección es «Código para unirse» **[NUEVO]** con `KeyRound`, no hay vista previa de la hoja ni recordatorio de datos del relevo, y **los dígitos no caen**: aparecen quietos. La caída de los dígitos es el único momento orquestado de MATU y es el del enlace de relevo (DISENO.md, principio 5).
- **Los dígitos:** `digitos`, `bg-hoja text-turquesa`, `text-6xl`. En `angosto:`, `text-3xl h-16 flex-1`, como el PIN. El párrafo lleva `aria-label="Código: 4 7 2 9"` (dígitos separados por espacio), `tabIndex={-1}` y el anillo de foco base. Cada dígito, `aria-hidden`.
- **«Repetir el código»** **[NUEVO]**, `variante="texto"`, lleva el foco al párrafo de los dígitos: se ve el anillo de 3 px alrededor del código y el lector lo vuelve a leer. Es lo que pide el analista en §6 con «un botón para leerlo de nuevo».
- **La dirección** se muestra cortada: `{origen sin https://}/invitacion#` y los seis primeros caracteres del token, más «…». Nunca completa: una captura con el código no lleva también el enlace.
- **Pantalla ancha:** dos columnas, como `/compartir/listo` (MATU-48 4.3). A la izquierda el título, «Vale…», la dirección y los botones. A la derecha el código, en `max-w-lg`.
- **Por qué el código va antes de «Enviar» a 360 px:** enviar abre otra aplicación, y si el teléfono descarta la pestaña, el código se pierde (MATU-48, D5).

### 3.5 Enviar y copiar

Igual que MATU-48 4.4, con otros textos:

| Situación | Botones |
|---|---|
| Con `navigator.share` | «Enviar el enlace» **[ANALISTA]**, principal, `Send` · «Copiar el enlace» **[ANALISTA]**, secundario, `Copy` · «Volver a Grupo familiar» **[L 22]**, texto |
| Sin `navigator.share` | «Copiar el enlace», principal · «Volver a Grupo familiar», texto |

- **Enviar:** `navigator.share({ text })` con «Te invito a mi grupo de cuidado en MATU. Abre este enlace para unirte. El código te lo digo por teléfono. `{enlace}`» **[ANALISTA]**. **Nunca el código**, ni el nombre de la persona cuidada, ni el del grupo (C33). Si cierra la hoja (`AbortError`), nada.
- **Copiar:** solo la `url`. Al copiar, `role="status"` con `CircleCheck` `text-ok`: «Enlace copiado. Pégalo en tu mensaje.» **[NUEVO]** (el de L 9.1 nombra al relevo, y aquí no sabemos su nombre). Si falla: «No pudimos copiar el enlace. Usa «Enviar el enlace».» **[L 9.1]**. Sin `navigator.share`, si falla, se muestra la `url` completa en un `input readOnly` con la etiqueta «Enlace de la invitación» **[NUEVO]**.

### 3.6 El código ya no se puede ver

El código vive solo en la memoria de `/grupo/invitar/listo`. Al salir por cualquier camino, se borra. Si se llega a la ruta sin código en memoria:

```
Invitación lista                                h1
┃ 🔑 El código ya no se puede ver               Nota tono="rocio", KeyRound
┃ Por seguridad se muestra una sola vez. Si se perdió,
┃ anula la invitación desde Grupo familiar y crea una nueva.
[ Volver a Grupo familiar ]                     secundario
```

Textos: «El código ya no se puede ver» · «Por seguridad se muestra una sola vez. Si se perdió, anula la invitación desde Grupo familiar y crea una nueva.» **[NUEVO, con la forma de L 9]**.

### 3.7 Estados

| Estado | Qué se ve |
|---|---|
| Creando | «Crear la invitación» pasa a «Creando la invitación…» **[NUEVO]**, mismo ancho, `aria-busy`. Las opciones quedan `disabled` |
| Sin red o 5xx | `Nota tono="atenta" rol="alert"` sobre el botón: «No pudimos crear la invitación. Revisa tu conexión y vuelve a intentarlo.» **[NUEVO]**. El rol elegido sigue elegido |
| 429, tope diario (C31) | `Nota tono="atenta" rol="alert"`: «Ya creaste muchas invitaciones hoy. Vuelve a intentarlo mañana.» **[NUEVO]** |
| 404 (dejó de administrar mientras tanto) | Vuelve a `/grupo` con el aviso de llegada «Ya no administras el grupo, así que no puedes invitar.» **[NUEVO]**, `tono="rocio"` |
| 422 sin rol | No llega: se valida antes (3.2) |
| Carga, vacío, 409, 410 y 412 | No aplican: la pantalla no pide nada al abrir y no edita nada versionado |

---

## 4. Aceptar la invitación (`/invitacion`)

**Objetivo, desde Rodrigo:** saber quién lo invita y para qué, comprobar con el código que es para él y unirse, aunque no tenga cuenta.

### 4.1 Los pasos

```
abre el enlace ─► 4.2 presentación + código ─► (sin sesión) 4.4 cuenta ─► 4.5 confirmar ─► 4.6 hecho
                         │                                                  │
                         └─► 4.7 estados que no siguen ◄─────────────────────┘
```

Con sesión, de 4.2 pasa directo a 4.5. Cada paso cambia el contenido de la misma página, sin animación, y el foco va a su `h1`.

### 4.2 Presentación y código

**Jerarquía:**
1. «`{nombre_pila_invita}` te invita a su grupo de cuidado en MATU, para `{rol en infinitivo}`.»
2. El campo del código.
3. «Seguir».
4. Hasta cuándo vale.

```
┌────────────────────────────────────┐
│ (M) MATU  Invitación a un grupo    │  marco público (2.1)
│           de cuidado    [Piloto…]  │
├────────────────────────────────────┤
│                                    │
│ ┌──────┐                           │
│ │ ✉    │                           │  Baldosa MailOpen, tono rocio
│ └──────┘                           │
│ Carmen te invita a su grupo de     │  h1 titular text-3xl, recibe el foco
│ cuidado en MATU, para cuidar.      │
│                                    │
│ Escribe el código que te dijo.     │  text-base
│                                    │
│ Código                             │  CampoCodigo, etiqueta font-bold
│ [ ____ ]                           │  maxLength 4, text-2xl
│                                    │
│ [ Seguir ]                         │  principal
│                                    │
│ Vale hasta el 19/11/2026 a las     │  text-base text-tenue
│ 21:30.                             │
└────────────────────────────────────┘
```

- **Pantalla ancha:** una sola columna centrada de `max-w-xl`, alineada a la izquierda por dentro, como la pantalla del PIN del relevo. A 1920 px no se estira.
- **El campo:** `CampoCodigo` de MATU-57 con un tope de 4 en vez de 6 (el frontend le agrega la prop `largo`). Un solo `input`, `inputmode="numeric"`, `autocomplete="one-time-code"`, admite pegar «47 29» o «47-29» (WCAG 3.3.8). Etiqueta «Código» **[NUEVO]**.
- **El rol en infinitivo** **[NUEVO]**, para que la frase del analista se lea bien: «para administrar el grupo» · «para cuidar» · «para pagar» · «para informarte». El analista escribe «para `{rol}`», y con los nombres de rol quedaría «para Cuida».
- Antes del código **no aparece** el nombre del grupo, ni el de la persona cuidada, ni el apellido de quien invita (C1, D-42-4 a).
- **Mientras abre**: «Abriendo la invitación…» **[NUEVO]**, en `role="status"`, en lugar del contenido, pasados 400 ms (como «Cargando…»).

### 4.3 El código

| Situación | Qué pasa | Texto |
|---|---|---|
| Menos de 4 números | No se hace la petición. Mensaje bajo el campo, foco en el campo | «El código tiene 4 números. Revisa que estén todos.» **[NUEVO, como el PIN de L 7.3]** |
| Revisando | «Seguir» pasa a «Revisando el código…» **[NUEVO]**, `aria-busy` | — |
| Código malo, quedan 2 o más | `MensajeError` bajo el campo, `role="alert"`, foco en el campo, el campo se vacía | «**Ese código no es.** Te quedan `{n}` intentos. Después, la invitación se bloquea.» **[ANALISTA, ajustado: se agrega la última oración, como L 7.3]** |
| Código malo, queda 1 | Igual | «**Ese código no es.** Te queda 1 intento. Después, la invitación se bloquea.» **[NUEVO, singular]** |
| Quinto código malo (423) | Pasa a 4.7, «Bloqueada» | — |
| Bien | Limpia el fragmento (2.1). Sin sesión, va a 4.4. Con sesión, a 4.5 | — |

### 4.4 Sin cuenta

```
│ Para unirte, crea tu cuenta o      │  h1 titular text-3xl
│ entra con la que tienes.           │
│                                    │
│ Te trae de vuelta aquí para        │  text-base text-tenue
│ terminar de unirte.                │
│                                    │
│ [ Crear mi cuenta ]                │  principal
│ [ Entrar con mi cuenta ]           │  secundario
```

- Textos: «Para unirte, crea tu cuenta o entra con la que tienes.» **[ANALISTA]** · «Te trae de vuelta aquí para terminar de unirte.» **[NUEVO]** · «Crear mi cuenta» y «Entrar con mi cuenta» **[NUEVO]**.
- **En `/crear-cuenta` y en `/entrar`**, con una invitación en memoria, arriba del formulario va una `Nota tono="rocio"` con `MailOpen`: «Después de esto vuelves a la invitación de `{nombre_pila_invita}`.» **[NUEVO]**. Así la persona no cree que la perdió.
- Crear la cuenta acepta la política vigente, como siempre (C3, MATU-75). Quien ya tenía cuenta no acepta nada más.

### 4.5 Confirmar

**Jerarquía:**
1. «Te unes a `{grupo}`. Cuidan a `{nombres_pila}`.»
2. Qué podrá hacer, con su rol.
3. Qué verá el grupo de ella y el aviso de confidencialidad.
4. «Unirme al grupo» y «No quiero unirme».

```
┌────────────────────────────────────┐
│ Te unes a Familia Soto.            │  h1 titular text-3xl, recibe el foco
│ Cuidan a María.                    │  (las dos oraciones en el h1)
│                                    │
│ Tu rol: Cuida.                     │  text-lg font-bold
│ Ve y cambia la ficha y los         │  text-base
│ insumos, y comparte la ficha con   │
│ quien te reemplaza.                │
│                                    │
│ ┃ 👤 Las personas del grupo verán │  Nota tono="rocio", UserRound
│ ┃   tu nombre. No verán tu correo  │
│ ┃   ni tu celular.                 │
│                                    │
│ ┃ 🔒 Lo que veas sobre María es   │  Nota tono="rocio", Lock
│ ┃   para su cuidado. No lo         │
│ ┃   compartas fuera del grupo.     │
│                                    │
│ Política de privacidad             │  EnlacePoliticaSolo (MATU-75)
│                                    │
│ Te unes como Rodrigo Soto.         │  text-base text-tenue
│                                    │
│ [ Unirme al grupo ]                │  principal
│ No quiero unirme                   │  texto
└────────────────────────────────────┘
```

**Textos:**
- h1: «Te unes a `{grupo}`. Cuidan a `{nombres_pila}`.» **[ANALISTA]**. `{nombres_pila}` se arma con «y»: «María», «María y Pedro», «María, Pedro y Elena». Sin nadie registrado todavía: «Te unes a `{grupo}`. Todavía no registran a la persona que cuidan.» **[NUEVO]**.
- «Tu rol: `{rol}`.» y debajo su descripción de 5.3 **[ANALISTA, ajustado: reemplaza «Con tu rol podrás: `{descripción}`.», ver 0.2]**.
- «Las personas del grupo verán tu nombre. No verán tu correo ni tu celular.» **[ANALISTA]**.
- «Lo que veas sobre `{nombre_pila}` es para su cuidado. No lo compartas fuera del grupo.» **[ANALISTA]**. Con varias personas: «Lo que veas sobre `{nombres_pila}` es para su cuidado.» con el mismo resto.
- «Política de privacidad» **[ANALISTA]**, con `EnlacePoliticaSolo`, que abre `/privacidad` en otra pestaña.
- «Te unes como `{tu nombre}`.» **[NUEVO]**. Sirve en un teléfono compartido: si la sesión es de otra persona, se nota antes de unirse.
- Botones: «Unirme al grupo» · «No quiero unirme» **[ANALISTA]**. Uniendo: «Uniéndote al grupo…» **[NUEVO]**.

**«No quiero unirme»** no llama al servidor (P12). Borra de la memoria el token y el código y muestra:

```
No te uniste al grupo                          h1 [NUEVO]
Si cambias de opinión, vuelve a abrir el enlace antes del 19/11/2026.   [NUEVO]
[ Ir a MATU ]                                  secundario, solo con sesión [NUEVO]
```

**Pantalla ancha:** la misma columna de `max-w-xl`. Las dos notas una debajo de la otra, no en dos columnas: se leen en orden.

### 4.6 Hecho

Al unirse, la app vuelve a pedir los grupos, elige el nuevo y lleva a su inicio (`/ficha` o `/insumos`, según el rol, regla de MATU-39). Ahí, el aviso de llegada `tono="ok"`, que recibe el foco: «Ya eres parte de `{grupo}`.» **[ANALISTA]**. Con más de un grupo, el selector del encabezado ya lo muestra.

### 4.7 Estados que no siguen

Todos con la forma de los estados del relevo (`PantallasSimples.tsx`): `Baldosa` con su ícono y tono, `h1` con el título, el texto y la nota «¿Qué hago?» **[L 7.2]** con la acción. El título se anuncia al cargar. Nunca solo por color: cada estado tiene su ícono y su título.

| Estado | Ícono y tono | Título | Texto | ¿Qué hago? |
|---|---|---|---|---|
| Vencida (410) | `CalendarX2`, atenta | «Esta invitación venció» **[NUEVO]** | «Las invitaciones duran 7 días, y esta ya terminó.» **[NUEVO]** | «Pídele una nueva a quien te invitó.» **[ANALISTA]** |
| Ya usada (410) | `CircleCheck`, neutro | «Esta invitación ya se usó» **[NUEVO]** | «Cada invitación sirve una sola vez.» **[NUEVO]** | Igual |
| No disponible (410, inexistente o anulada, C28) | `Link2Off`, neutro | «Esta invitación no está disponible» **[NUEVO]** | «Puede que se haya copiado incompleta o que ya no exista. Revisa que la abriste completa desde el mensaje.» **[NUEVO, como L 7.3]** | Igual |
| Bloqueada (423) | `Lock`, pronto | «Esta invitación se bloqueó» **[NUEVO]** | «El código se escribió mal cinco veces. Por seguridad, ya no sirve.» **[NUEVO]** | «Pídele a `{nombre_pila_invita}` una nueva.» **[ANALISTA, partido]**. Sin el nombre (P2): «Pídele una nueva a quien te invitó.» |
| Ya eres parte (409, C27) | `CircleCheck`, ok | «Ya eres parte de este grupo» **[ANALISTA]** | — | Botón secundario «Ir a MATU» **[NUEVO]** en vez de la nota |
| Demasiados intentos desde la conexión (429) | `Hourglass`, atenta | «Espera un momento» **[L 7.3]** | «Hubo muchos intentos desde esta conexión. Vuelve a intentarlo en `{minutos}` minutos.» **[L 7.3, sin «de entrar»]**, con las reglas de los minutos de L 7.3 | — |
| Sin red o 5xx | `CloudOff`, atenta | «No pudimos completar esto.» **[L 8, página del relevo]** | «Revisa tu conexión y vuelve a intentarlo.» | Botón «Volver a intentar» **[L 26]**, que repite la última petición. El código escrito sigue en el campo |

Un 410 o un 423 **durante la confirmación** (venció o la anularon mientras creaba su cuenta) lleva a la misma tabla.

### 4.8 Sin token en memoria

Si abre `/invitacion` sin fragmento y sin nada en memoria (recargó después de 2.1, o volvió con «Atrás»):

| Pieza | Texto |
|---|---|
| Título | «Vuelve a abrir el enlace» **[L 7.3, título de «Sin sesión»]** |
| Texto | «Vuelve a abrir el enlace que te enviaron.» **[ANALISTA]** |

Con `Baldosa` `Link2` tono rocio. Sin botón.

---

## 5. Ver el grupo (`/grupo`)

**Objetivo, desde cualquier persona del grupo:** saber quiénes lo forman y qué puede hacer cada una. Desde Carmen, además, invitar y gestionar.

### 5.1 Lo que cambia en la pantalla que ya existe

`GrupoFamiliar` en `Grupo.tsx` hoy muestra, por persona cuidada, sus permisos y «Borrar sus datos». Se agregan dos bloques arriba y uno abajo. **Lo de MATU-44 y MATU-72 no cambia.**

1. **Nuevo:** «Quiénes forman el grupo», con «Invitar a alguien» para admin.
2. **Nuevo, solo admin y solo si hay alguna:** «Invitaciones sin usar».
3. Lo de hoy: cada persona cuidada con sus permisos y «Borrar sus datos».
4. **Nuevo:** «Salir del grupo».

La bajada cambia: «Quiénes forman `{grupo}`, a quién cuidan y qué permisos dieron.» **[NUEVO, reemplaza a L 22 `bajada`]**.

### 5.2 Esquema a 360 px (admin)

```
┌────────────────────────────────────┐
│ Grupo familiar                     │  h1 titular text-3xl
│ Quiénes forman Familia Soto, a     │  bajada text-base text-tenue
│ quién cuidan y qué permisos dieron.│
│                                    │
│ Quiénes forman el grupo            │  h2 text-xl font-bold
│ ┌────────────────────────────────┐ │  ul bg-hoja ring-1 ring-linea
│ │ Carmen Soto (tú)               │ │  rounded-xl divide-y divide-linea
│ │ Administra el grupo            │ │  nombre text-lg font-bold
│ │ Se unió el 02/11/2026.         │ │  rol text-base, fecha text-tenue
│ │ Eres la única persona que      │ │  text-base text-tenue (5.5)
│ │ administra el grupo. Para      │ │
│ │ dejar ese rol, primero dáselo  │ │
│ │ a otra persona.                │ │
│ ├────────────────────────────────┤ │
│ │ Rodrigo Soto                   │ │
│ │ Paga                           │ │
│ │ ◌ No ve la ficha               │ │  EyeOff text-tenue + palabra
│ │ Se unió el 08/11/2026.         │ │
│ │ Cambiar lo que puede hacer     │ │  Boton texto
│ │ Dejar que vea la ficha         │ │  Boton texto
│ │ Sacar del grupo                │ │  Boton textoPeligro
│ ├────────────────────────────────┤ │
│ │ Rosa Pérez                     │ │
│ │ Cuida                          │ │
│ │ Se unió el 10/11/2026.         │ │
│ │ Cambiar lo que puede hacer     │ │
│ │ Sacar del grupo                │ │
│ └────────────────────────────────┘ │
│ [ Invitar a alguien ]              │  principal, único macizo
│                                    │
│ Invitaciones sin usar              │  h2 text-xl font-bold
│ ┌────────────────────────────────┐ │
│ │ Se informa · vence el          │ │  text-base font-bold
│ │ 19/11/2026 a las 21:30.        │ │
│ │ La creó Carmen.                │ │  text-tenue
│ │ Anular la invitación           │ │  Boton textoPeligro
│ └────────────────────────────────┘ │
│                                    │
│ María Soto                         │  lo de hoy (MATU-44, MATU-72)
│ ┌ Permiso para guardar su ficha ┐  │
│ …                                  │
│                                    │
│ ───────────────────────────────────│  border-t border-linea pt-6
│ Salir del grupo                    │  h2 text-xl font-bold
│ Dejarás de ver Familia Soto y se   │  text-base
│ cortan los enlaces de relevo que   │
│ compartiste.                       │
│ (o la frase de 7.3, sin botón)     │
└────────────────────────────────────┘
│ Ficha  Insumos  Compartir  Grupo   │
```

**Otros roles** ven la misma lista, sin ningún botón en las filas, sin «Invitar a alguien» ni «Invitaciones sin usar». Bajo la lista, en `text-base text-tenue`: «Solo quien administra el grupo invita, cambia los roles y saca a alguien.» **[NUEVO, de la política §6]**. El pagador ve «Puede ver la ficha» o «No ve la ficha» solo en su propia fila (C9: el campo viene solo para el pagador, y cada quien ve el suyo).

### 5.3 Una fila de la lista

- `ul` con una `li` por miembro activo, en el orden de la API. Dentro, `flex flex-col gap-1 px-4 angosto:px-2 py-4`.
- **Nombre:** `text-lg font-bold break-words`. En la fila propia, seguido de «(tú)» **[ANALISTA]** en peso normal.
- **Rol, siempre en palabra**, `text-base` **[ANALISTA]**: «Administra el grupo» · «Cuida» · «Paga» · «Se informa». Sin color ni ícono por rol: la palabra es el dato, y un color por rol leería como estado (DISENO.md, el turquesa nunca comunica estado).
- **Solo para el pagador**: «Puede ver la ficha» con `Eye` en `text-ok`, o «No ve la ficha» con `EyeOff` en `text-tenue` **[ANALISTA]**. El ícono acompaña a la palabra, nunca la reemplaza.
- **Desde cuándo:** «Se unió el `{fecha}`.» **[NUEVO]**, `text-tenue`, con la fecha en `cifras`. Para quien creó el grupo, la misma frase.
- **Acciones de admin, en otra persona:** `flex flex-wrap gap-x-6 gap-y-0`, a la izquierda, al ancho de su texto. En `angosto:` van una debajo de la otra.
  - «Cambiar lo que puede hacer» **[NUEVO]**, `texto`, con nombre accesible «Cambiar lo que puede hacer `{nombre}`» (empieza con el texto visible, WCAG 2.5.3).
  - Solo si es pagador: «Dejar que vea la ficha» o «Quitarle la ficha» **[ANALISTA]**, `texto`, con nombre accesible «… a `{nombre}`».
  - «Sacar del grupo» **[ANALISTA, el botón del diálogo]**, `textoPeligro`, con nombre accesible «Sacar del grupo a `{nombre}`».
- **En la fila propia de admin:** «Cambiar tu rol» **[NUEVO]**, `texto`, solo si hay otra persona que administra. Si no, la frase de 5.5. Nunca «Sacar del grupo» en la fila propia: para eso está «Salir del grupo».

### 5.4 Invitaciones sin usar (solo admin)

- `h2` «Invitaciones sin usar» **[ANALISTA]** y una `ul` con la misma superficie de la lista. Solo las vigentes. Si no hay ninguna, el bloque no aparece.
- Cada una: «`{rol}` · vence el `{fecha}` a las `{hora}`.» **[ANALISTA, con la hora agregada como pide su §6]**, `font-bold`. Debajo, «La creó `{nombre}`.» **[NUEVO]** en `text-tenue` (con dos personas que administran, sirve para saber de quién es). Si la creó alguien que ya no está: «La creó alguien que ya no está en el grupo.» (5.7).
- «Anular la invitación» **[ANALISTA]**, `textoPeligro`, abre el diálogo de 8.4.
- Después de anular, la fila sale y queda en su lugar una `Nota tono="ok"`, que recibe el foco: «Invitación anulada.» **[ANALISTA]**.

### 5.5 El grupo nunca queda sin admin

- **En la fila propia de la única persona que administra:** «Eres la única persona que administra el grupo. Para dejar ese rol, primero dáselo a otra persona.» **[NUEVO, de la frase del 409 del analista]**, `text-base text-tenue`, sin botón. Explica antes de que choque.
- **Si igual llega un 409** (otra persona que administraba salió al mismo tiempo), dentro del diálogo, en su región `role="alert"`: «El grupo necesita alguien que lo administre. Primero da ese rol a otra persona.» **[ANALISTA]**. El diálogo no se cierra, y la lista se vuelve a pedir detrás.

### 5.6 El aviso de D-42-9

Si la vista de la autorización trae `autorizo_alguien_que_ya_no_esta: true`, el bloque del permiso (el de MATU-44) suma, bajo su estado, una `Nota tono="rocio"` con `Info`, solo para admin y cuidador:

> «La autorización la dio alguien que ya no está en el grupo. Sigue vigente.» **[ANALISTA, ajustado y aprobado: sin el nombre, por D-42-10, y sin «renuévala»]**

Se aplica igual a los tres permisos (ficha, insumos y pedidos), como pide el ajuste de Jorge. **Sin botón ni enlace para renovar:** eso es de MATU-69. Con el campo en `false` o ausente, la nota no aparece.

### 5.7 «Alguien que ya no está en el grupo»

Es el nombre de toda persona cuya membresía ya no está activa, en cualquier pantalla de la app (D-42-10). La API la manda con `nombre: null` y `autor_activo: false`, igual en todas las rutas, y el texto lo pone la pantalla. Aparece en: quién guardó un campo de la ficha, quién creó un enlace, quién armó, confirmó o pagó un pedido, quién creó una invitación.

- Al empezar una oración: «Alguien que ya no está en el grupo» **[ANALISTA]**. Dentro de una oración: «alguien que ya no está en el grupo» **[NUEVO, la misma en minúscula]**. Ejemplo: «Guardado por alguien que ya no está en el grupo.»
- Se escribe igual que un nombre: mismo tamaño, mismo color y mismo peso que el nombre al que reemplaza. No va en cursiva ni en `tenue`: no es un estado, es quién lo hizo.
- **En la lista de miembros no aparece.** Quien salió simplemente ya no está en «Quiénes forman el grupo».

### 5.8 Pantalla ancha

```
┌──────────────┬─────────────────────────────────────────────────────────────┐
│ (M) MATU     │ Grupo familiar                                              │
│ Ficha        │ Quiénes forman Familia Soto, a quién cuidan y qué permisos  │
│ Insumos      │ dieron.                                                     │
│ Compartir    │                                                             │
│ Grupo famil. │ Quiénes forman el grupo                                     │
│              │ ┌──────────────────────────────────────────────────────────┐│
│              │ │ Carmen Soto (tú)        Administra el grupo              ││
│              │ │ Se unió el 02/11/2026.  Eres la única persona que…       ││
│              │ ├──────────────────────────────────────────────────────────┤│
│              │ │ Rodrigo Soto            Paga · ◌ No ve la ficha          ││
│              │ │ Se unió el 08/11/2026.  Cambiar lo que puede hacer       ││
│              │ │                         Dejar que vea la ficha           ││
│              │ │                         Sacar del grupo                  ││
│              │ └──────────────────────────────────────────────────────────┘│
│              │ [Invitar a alguien]                                         │
│              │                                                             │
│              │ María Soto                                                  │
│              │ ┌ Permiso para guardar… ┐  ┌ Permiso para calcular… ┐      │
└──────────────┴─────────────────────────────────────────────────────────────┘
```

- La lista en `max-w-3xl`. Cada `li`, desde `@3xl/main:`, en `grid grid-cols-[12rem_minmax(0,1fr)] gap-x-6`: a la izquierda el nombre y «Se unió el…», a la derecha el rol, la ficha del pagador, la frase de 5.5 y las acciones. Es la columna de etiquetas de 12 rem que ya usa Grupo familiar (DISENO.md 3, medidas fijas): no es un token nuevo.
- Las acciones, a la derecha, en `flex flex-wrap gap-x-6`. A 1920 px caben en una fila.
- «Invitar a alguien» bajo la lista, al ancho de su texto, alineado a la izquierda.
- Lo de MATU-44 sigue en su grilla de dos columnas.

### 5.9 Estados

| Estado | Qué se ve |
|---|---|
| Cargando | El `Cargando` de hoy, «Cargando…» **[L 26]**, para toda la página |
| Error al traer la lista | En el lugar del bloque, `Nota tono="atenta" rol="alert"` con `CloudOff`: «No pudimos traer quiénes forman el grupo. Revisa tu conexión e inténtalo de nuevo.» **[ANALISTA]** y «Volver a intentar» **[L 26]**, secundario. Lo de las personas cuidadas se muestra igual si cargó: los dos bloques fallan por separado |
| Solo estás tú (admin) | La lista con tu fila y, debajo, «Por ahora solo estás tú. Invita a quien cuida contigo.» **[NUEVO]** en `text-base`, antes de «Invitar a alguien». Sin ícono grande: no es una pantalla vacía |
| 404 al gestionar a alguien | En el diálogo, se cierra, la lista se vuelve a pedir y la `Nota tono="rocio"` dice «Esa persona ya no estaba en el grupo.» **[ANALISTA]** |
| Dejé de administrar (otro admin me bajó) | La siguiente petición de gestión responde 404. Se vuelve a pedir la lista y el rol propio, desaparecen los botones, y la nota dice «Ya no administras el grupo.» **[NUEVO]**, `tono="rocio"` |
| Me sacaron | Cualquier petición responde 404 sobre el grupo. La app vuelve a pedir los grupos y sigue la regla de MATU-39 (otro grupo o `/empezar/grupo`). Sin texto propio: la regla general de L 8, 404 |
| Sin red al gestionar | En el diálogo, región `role="alert"`: el error de cada diálogo (sección 8). Todo sigue como estaba |
| 410 | No aplica en `/grupo` |
| 412 | Ver 6.6 |

---

## 6. Cambiar el rol (diálogo, solo admin)

**Objetivo, desde Carmen:** cambiar qué puede hacer Rosa sabiendo, antes de confirmar, si pierde la ficha y qué enlaces se cortan.

### 6.1 Construcción

El diálogo de MATU-44 4.1, tal cual: `<dialog>` modal con `showModal()`, `max-w-lg`, `max-h-[calc(100dvh-2rem)] overflow-y-auto`, `rounded-2xl bg-hoja p-6 angosto:px-2 angosto:py-4`, `backdrop:bg-tinta/40`, sin animación. El foco inicial al `h2`, y al cerrar vuelve al botón que lo abrió. La región `role="alert"` montada vacía.

### 6.2 Esquema a 360 px

```
┌────────────────────────────────────┐
│ Cambiar lo que puede hacer Rosa    │  h2 text-xl font-bold, foco inicial
│                                    │
│ ¿Qué podrá hacer?                  │  fieldset > legend font-bold
│ (○) Administra el grupo            │  GrupoOpciones forma="lista",
│     Ve y cambia todo…              │  el rol actual elegido de partida
│ (●) Cuida              Ahora       │  «Ahora» junto al rol actual
│     Ve y cambia la ficha…          │
│ (○) Paga                           │
│     Ve los insumos…                │
│ (○) Se informa                     │
│     Ve el nombre de María…         │
│                                    │
│ ┃ ⚠ Rosa dejará de ver la ficha.  │  Nota tono="atenta", aria-live,
│ ┃   Se cortan 2 enlaces de relevo  │  solo si el cambio le quita la
│ ┃   que compartió.                 │  ficha (6.3)
│                                    │
│ [ Guardar el cambio ]              │  principal, o peligroPrincipal (6.3)
│ No cambiar                         │  texto
└────────────────────────────────────┘
```

En pantalla ancha, el mismo diálogo centrado, con los dos botones en una fila.

### 6.3 Lo que se muestra según el cambio

| Cambio | Nota | Botón |
|---|---|---|
| Sigue con el mismo rol | Ninguna | «Guardar el cambio» `aria-disabled`, con la frase «Elige otro rol para guardar.» **[NUEVO]** al lado |
| Pasa a «Administra el grupo» | `atenta`: «`{nombre}` podrá invitar, cambiar permisos y sacar a otras personas, también a ti.» **[ANALISTA, con el nombre]** | «Guardar el cambio» **[ANALISTA]**, principal |
| Pierde la ficha (de admin o cuidador a pagador u observador, o de pagador con permiso a observador) | `atenta`: «`{nombre}` dejará de ver la ficha. Se cortan `{n}` enlaces de relevo que compartió.» **[ANALISTA]**. Con 1: «Se corta 1 enlace de relevo que compartió.» Con 0: solo «`{nombre}` dejará de ver la ficha.» **[NUEVO, las formas de n]** | «Guardar el cambio», `peligroPrincipal`: quita algo |
| Pasa a «Paga» desde admin o cuidador | Además: «Como paga, no verá la ficha hasta que le des permiso.» **[NUEVO]** | Igual que arriba |
| Mi propia fila, dejo de administrar | `atenta`: «Dejarás de administrar el grupo. Para volver a hacerlo, otra persona que administra tendrá que dártelo.» **[NUEVO]** | `peligroPrincipal` |
| Cualquier otro | Ninguna | principal |

- La descripción de «Paga» sin capa 3: «Ve los insumos. Ve la ficha solo si quien administra le da permiso.» **[NUEVO, ajuste de Jorge]**. Con capa 3, la del analista.
- `{nombre_pila}` en «Se informa», con varias personas: «Ve el nombre de `{nombres_pila}` y sus insumos. No ve la ficha.»
- «Ahora» **[NUEVO]**: una `Etiqueta` neutra junto al rol actual, con palabra (no un color).
- Guardando: «Guardando el cambio…» **[NUEVO]**, `aria-busy`.

### 6.4 Después

El diálogo se cierra, la fila se actualiza en su lugar y, bajo la fila, una `Nota tono="ok"` que recibe el foco:
- «Ahora `{nombre}` `{rol en minúscula}`.» **[ANALISTA]**: «Ahora Rosa cuida.», «Ahora Rosa administra el grupo.», «Ahora Rosa paga.», «Ahora Rosa se informa.»
- Si se cortaron enlaces, sigue «Cortamos `{n}` enlaces.» o «Cortamos 1 enlace.» **[NUEVO, la forma de L 22]**.
- Si fue mi propio rol, la página se vuelve a dibujar con mi rol nuevo, y la nota va arriba de la lista.

### 6.5 Errores

| Caso | Texto, en la región `role="alert"` del diálogo |
|---|---|
| Sin red o 5xx | «No pudimos guardar el cambio. Todo sigue como estaba.» **[ANALISTA]** |
| 409, último admin | 5.5 |
| 404 | 5.9 |

### 6.6 Otra persona cambió el rol al mismo tiempo (412)

El diálogo no se cierra. Se vuelve a pedir el miembro, y la región `role="alert"` dice, en una `Nota tono="atenta"` (412 va en `atenta`, DISENO.md 6): «Otra persona del grupo cambió lo que puede hacer `{nombre}` mientras lo mirabas. Ahora `{nombre}` `{rol en minúscula}`. Revisa y vuelve a elegir.» **[NUEVO]**. «Ahora» se mueve al rol nuevo. Lo que había elegido se pierde, a propósito: se elige sobre lo que hay.

### 6.7 El permiso del pagador para ver la ficha

Dos diálogos chicos con la construcción de 6.1.

**Dar:**
- h2: «¿Dejar que `{nombre}` vea la ficha?» **[NUEVO]**
- Texto: «Podrá leer la ficha de `{nombres_pila}` y ver sus enlaces de relevo. No podrá cambiarla ni compartirla.» **[NUEVO]**. Con varias personas, «las fichas».
- Botones: «Dejar que vea la ficha» **[ANALISTA]**, principal · «No por ahora» **[NUEVO]**, texto.
- Hecho: «Ahora `{nombre}` puede ver la ficha.» **[NUEVO]**.

**Quitar:**
- h2: «¿Quitarle la ficha a `{nombre}`?» **[NUEVO]**
- Texto: «`{nombre}` dejará de ver la ficha desde ahora.» **[NUEVO]**. Sin línea de enlaces: quien paga no crea enlaces.
- Botones: «Quitarle la ficha» **[ANALISTA]**, `peligroPrincipal` · «No quitar» **[NUEVO]**, texto.
- Hecho: «`{nombre}` ya no ve la ficha.» **[NUEVO]**.

Error sin red, en los dos: «No pudimos guardar el cambio. Todo sigue como estaba.» **[ANALISTA]**. 412, como 6.6.

---

## 7. Sacar a alguien y salir del grupo

### 7.1 Sacar (diálogo, solo admin)

```
┌────────────────────────────────────┐
│ ¿Sacar a Rosa del grupo?           │  h2 text-xl font-bold, foco inicial
│                                    │
│ • Dejará de verlo ahora.           │  ul list-disc text-base
│ • Se cortan 2 enlaces de relevo    │  font-bold: es lo que no vuelve
│   que compartió.                   │
│ • Lo que escribió en la ficha      │
│   queda.                           │
│ • Para volver, tendrías que        │
│   invitar a Rosa de nuevo.         │
│                                    │
│ [ Sacar del grupo ]                │  peligroPrincipal
│ No sacar                           │  texto
└────────────────────────────────────┘
```

- h2: «¿Sacar a `{nombre}` del grupo?» **[ANALISTA]**.
- Puntos: «Dejará de verlo ahora.» · «Se cortan `{n}` enlaces de relevo que compartió.» · «Lo que escribió en la ficha queda.» **[ANALISTA, partido en puntos]**. Las formas de n de 6.3. Con 0 enlaces, el punto dice «No tiene enlaces de relevo que abran ahora.» **[NUEVO]**.
- Cuarto punto: «Para volver, tendrías que invitar a `{nombre}` de nuevo.» **[NUEVO]**. Sin pronombre, porque MATU no guarda el género (A3 de MATU-72).
- Botones: «Sacar del grupo» · «No sacar» **[ANALISTA]**. Sacando: «Sacando del grupo…» **[NUEVO]**.
- Hecho, `Nota tono="ok"` arriba de la lista, con el foco: «`{nombre}` ya no está en el grupo.» **[ANALISTA]**, más «Cortamos `{n}` enlaces.» si hubo **[NUEVO]**.
- Sin red: «No pudimos sacar a `{nombre}` del grupo. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba.» **[NUEVO]**. 404: 5.9.

### 7.2 Salir del grupo (la sección al final y su diálogo)

La sección va al final de `/grupo`, después de las personas cuidadas, separada con `border-t border-linea pt-6`, para todos los roles.

- h2: «Salir del grupo» **[ANALISTA]**.
- Texto: «Dejarás de ver `{grupo}` y se cortan los enlaces de relevo que compartiste.» **[NUEVO, de la confirmación del analista]**.
- Botón: «Salir del grupo» **[ANALISTA]**, `peligro` (secundario rojo). No es macizo: salir no es el camino de la pantalla.

**El diálogo:**

```
┌────────────────────────────────────┐
│ ¿Salir de Familia Soto?            │  h2, foco inicial
│                                    │
│ • Dejarás de verlo ahora.          │
│ • Se cortan los enlaces de relevo  │  font-bold
│   que compartiste. Hoy abren 2.    │
│ • Lo que escribiste en la ficha    │
│   queda, porque es parte del       │
│   cuidado de María.                │
│ • Para volver, alguien que         │
│   administra el grupo tiene que    │
│   invitarte de nuevo.              │
│                                    │
│ [ Salir del grupo ]                │  peligroPrincipal
│ Quedarme                           │  texto
└────────────────────────────────────┘
```

- h2: «¿Salir de `{grupo}`?» **[ANALISTA]**.
- Puntos: «Dejarás de verlo ahora.» · «Se cortan los enlaces de relevo que compartiste.» **[ANALISTA, partido]**, seguido de «Hoy abren `{n}`.» **[L 22, `hoyAbren`]**, con los enlaces vigentes propios de la lista. · «Lo que escribiste en la ficha queda, porque es parte del cuidado de `{nombres_pila}`.» **[NUEVO, de la política §4]** · «Para volver, alguien que administra el grupo tiene que invitarte de nuevo.» **[NUEVO]**.
- Botones: «Salir del grupo» · «Quedarme» **[ANALISTA]**. Saliendo: «Saliendo del grupo…» **[NUEVO]**.
- **Después:** la app vuelve a pedir los grupos. Si queda otro, lleva a su inicio. Si no queda ninguno, a `/empezar/grupo`. En los dos casos, el aviso de llegada `tono="ok"`: «Saliste de `{grupo}`.» **[NUEVO]**, más «Cortamos `{n}` enlaces.» si hubo.
- Sin red: «No pudimos sacarte del grupo. Revisa tu conexión y vuelve a intentarlo. Sigues en el grupo.» **[NUEVO]**. 409 último admin: 7.3.

### 7.3 Si eres la única persona que administra

En lugar del botón, en `text-base`:
- Con otras personas en el grupo: «Eres la única persona que administra `{grupo}`. Para salir, primero da ese rol a otra persona.» **[NUEVO, de la política §10]**.
- Sola en el grupo (P14): «Eres la única persona de `{grupo}`, así que no puedes salir. Si ya no usan MATU para cuidar a `{nombres_pila}`, puedes borrar sus datos en «Borrar sus datos», más arriba.» **[NUEVO]**. «Borrar sus datos» es el título del bloque de MATU-72 en esta misma página, sin enlace: el bloque está a la vista.

Si igual llega el 409: con otras personas en el grupo, el diálogo muestra la frase de 5.5. Si está sola, muestra la frase de arriba, y al cerrarlo el foco va al primer «Borrar los datos de `{nombre_pila}`» de la página.

---

## 8. Componentes y tokens

**Ningún token nuevo.** Se usan: `papel`, `hoja`, `tinta`, `tenue`, `turquesa`, `marca` (solo el logo), `rocio`, `linea`, `borde`, `ok`, `ok-fondo`, `atenta`, `atenta-fondo`, `pronto`, `pronto-fondo`, `titular`, `cifras`, `digitos`, `max-w-prose`, `max-w-xl`, `max-w-lg`, `max-w-3xl`, `max-w-5xl` y las variantes `angosto:`, `telefono:`, `@3xl/main:`.

| Componente | De dónde | Estados que exige esta historia |
|---|---|---|
| `Pagina`, `Volver`, `Acciones`, `MensajeError`, `Etiqueta` | `ui.tsx`, sin cambios | Los de MATU-39 |
| `GrupoOpciones forma="lista"` | `ui.tsx` | normal, foco, elegido, `disabled` mientras crea, error de la `legend`. En `angosto:`, el indicador arriba y el texto debajo (DISENO.md 6) |
| `CampoCodigo` | `Codigo.tsx`, con una prop `largo` (4 o 6) | vacío, escribiendo, error (`ring-pronto` + `MensajeError`), `disabled` mientras revisa |
| `Boton` | `compartido/ui/Boton.tsx` | `principal`, `secundario`, `texto`, `peligro`, `textoPeligro`, `peligroPrincipal`. Cargando con gerundio y `aria-busy`. `aria-disabled` donde tiene que conservar el foco (6.3) |
| `Nota` | `compartido/ui/Nota.tsx` | `rocio`, `ok`, `atenta`, `pronto`, con ícono siempre |
| Sección del código | `EnlaceListo` de `Compartir.tsx`, con los cambios de 3.4 | con código, sin código (3.6) |
| Diálogo | El de MATU-44 4.1 (`DialogoRetirar`) | abierto, enviando, error, 409, 412 |
| Marco público de `/invitacion` | La forma de `relevo/Marco.tsx`, con otro rótulo | — |
| Estado que no sigue | `Baldosa` y la forma de `PantallasSimples.tsx` | los ocho de 4.7 |
| `EnlacePoliticaSolo` | `compartido/ui/Enlaces.tsx` | Los de MATU-75 |
| Lista de miembros, fila de invitación | **Nuevos**, en `Grupo.tsx` | Los de 5.3 y 5.4 |

**Íconos, todos de `lucide-react`:** `MailPlus`, `MailOpen`, `KeyRound`, `Send`, `Copy`, `CircleCheck`, `Link2`, `Link2Off`, `CalendarX2`, `Lock`, `Hourglass`, `CloudOff`, `Eye`, `EyeOff`, `UserRound`, `Info`, `TriangleAlert`. Decorativos con `aria-hidden`.

Nada escrito a mano: ni colores, ni sombras, ni tamaños fuera de la escala, ni `text-sm`.

---

## 9. Accesibilidad

- **48 × 48 px** en todo lo que se toca: las cuatro opciones de rol, el campo del código, todos los botones, también los de texto de cada fila («Cambiar lo que puede hacer», «Sacar del grupo», «Anular la invitación», «Repetir el código»), que miden `min-h-12`.
- **Foco:** anillo de 3 px `turquesa` con 2 px de separación. En los `textoPeligro` y `peligroPrincipal`, el de su variante. Al llegar a cada pantalla o paso, al `h1`. Al abrir un diálogo, a su `h2`, y al cerrarlo, al botón que lo abrió. Tras un error de validación, al campo. Tras una acción que termina bien, a su `Nota`. Si la fila del botón que abrió el diálogo ya no existe (sacar), el foco va a la `Nota` de arriba de la lista.
- **Nada solo por color:** el rol es una palabra. El permiso del pagador, palabra con `Eye` o `EyeOff`. Los estados de 4.7, ícono y título. Lo que quita, además de `pronto`, dice qué quita en su texto.
- **Semántica:** la lista es `ul`. Los roles son un `fieldset` con `legend` y botones de radio, cada uno con `aria-describedby` a su descripción. Los diálogos atrapan el foco con `showModal()`.
- **Anuncios:** los errores del código y de los diálogos en `role="alert"`. Las notas de hecho en `role="status"` y con el foco. La advertencia de admin y la de perder la ficha aparecen en una región `aria-live="polite"` montada desde el principio.
- **El código** se lee «Código: 4 7 2 9», no «cuatro mil setecientos veintinueve».
- **El vencimiento escrito** siempre como «hasta el 19/11/2026 a las 21:30», con la fecha y la hora en dos `cifras`.
- **Sin desplazamiento horizontal** a 320 px con el texto al 200 % (160 px efectivos): las opciones de rol con el indicador arriba, los dígitos con `flex-1`, la dirección con `truncate`, las acciones de cada fila una debajo de otra, los nombres largos con `break-words` y la grilla de 12 rem solo desde `@3xl/main:`.
- **Ningún texto bajo 17 px** (MATU-93): ayudas, «Se unió el…», «La creó…», «Ahora», el vencimiento y las notas, todos en `text-base`.
- **Con `prefers-reduced-motion`**, nada cambia: estas pantallas no tienen animación.

---

## 10. Criterios visuales verificables

1. En `/grupo`, para admin, el único `turquesa` macizo es «Invitar a alguien». Para los otros roles no hay ninguno.
2. En `/grupo/invitar`, ningún rol está elegido al abrir, y tocar «Crear la invitación» sin elegir no hace ninguna petición.
3. La nota «Podrá invitar, cambiar permisos y sacar a otras personas, también a ti.» aparece solo con «Administra el grupo» elegido, y no antes.
4. El formulario de invitar no tiene ningún campo de correo, teléfono ni nombre.
5. El código aparece una sola vez: recargar `/grupo/invitar/listo` muestra «El código ya no se puede ver». El código no está en la URL, el `<title>`, `history.state` ni el almacenamiento del navegador.
6. El texto que se comparte no lleva el código, ni el nombre de la persona cuidada, ni el del grupo. En la pantalla nunca se ve la dirección completa con el código al lado.
7. En `/invitacion`, antes del código, el único nombre visible es el nombre de pila de quien invita. No aparece el grupo ni la persona cuidada.
8. Después de verificar el código, o de tocar «Crear mi cuenta», la barra de direcciones dice `/invitacion` sin fragmento, y «Atrás» no vuelve a una entrada con el token.
9. Quien crea su cuenta desde una invitación vuelve a «Te unes a…», nunca a «Ponle nombre a tu grupo».
10. La lista de miembros nunca muestra un correo ni un celular. Quien salió no está en la lista, y en las otras pantallas se nombra «Alguien que ya no está en el grupo», con el mismo estilo de un nombre.
11. La única persona que administra no ve «Cambiar tu rol» ni el botón «Salir del grupo», y ve la frase que lo explica.
12. Las confirmaciones de sacar, de bajar de rol y de salir dicen cuántos enlaces se cortan, y su botón es `pronto` macizo, no `turquesa`.
13. En escala de grises, el rol, el permiso del pagador y los ocho estados de 4.7 se distinguen igual.
14. A 320 px con el texto al 200 %, ninguna de las pantallas ni de los diálogos tiene desplazamiento horizontal, y los cuatro dígitos del código caben en una fila.
15. Ningún texto mide menos de 17 px.
16. Ningún texto dice «token», «usuario», «observador», «revocar», «rechazar», «invitado» ni «invitada», ni un término de L 3. Ninguno asume el género de nadie.
17. «Salir del grupo» nunca aparece abreviado como «Salir».

---

## 11. Textos para `lenguaje.md` (sección 33, al fusionar)

Van tal cual los de la sección 5 del analista, con estos ajustes, y los **[NUEVO]** de esta especificación. Los **[NUEVO]** quedaron aprobados por el orquestador el 12-11, por delegación de Jorge, que los confirma al fusionar:

| Dónde | Texto **[NUEVO]** |
|---|---|
| Bajada de Grupo familiar | Quiénes forman `{grupo}`, a quién cuidan y qué permisos dieron. |
| Bajada de Invitar | Le mandas un enlace desde tu teléfono y le dictas un código aparte. No guardamos su correo ni su teléfono. |
| Antes del botón de invitar | Vale 7 días y sirve una sola vez. |
| Sin rol elegido | Elige qué podrá hacer. |
| Vista previa | Lo que verá al abrir el enlace · sin rol: …para el rol que elijas. |
| Creando y errores | Creando la invitación… · No pudimos crear la invitación. Revisa tu conexión y vuelve a intentarlo. · Ya creaste muchas invitaciones hoy. Vuelve a intentarlo mañana. · Ya no administras el grupo, así que no puedes invitar. |
| Código | Código para unirse · Repetir el código · El código ya no se puede ver · Por seguridad se muestra una sola vez. Si se perdió, anula la invitación desde Grupo familiar y crea una nueva. |
| Copiar | Enlace copiado. Pégalo en tu mensaje. · Enlace de la invitación |
| Marco de `/invitacion` | Invitación a un grupo de cuidado · Invitación a un grupo de cuidado · MATU · Abriendo la invitación… |
| El rol en infinitivo | para administrar el grupo · para cuidar · para pagar · para informarte |
| El código | Código · El código tiene 4 números. Revisa que estén todos. · Revisando el código… · Ese código no es. Te queda 1 intento. Después, la invitación se bloquea. |
| Sin cuenta | Te trae de vuelta aquí para terminar de unirte. · Crear mi cuenta · Entrar con mi cuenta · Después de esto vuelves a la invitación de `{nombre_pila_invita}`. |
| Confirmar | Te unes a `{grupo}`. Todavía no registran a la persona que cuidan. · Tu rol: `{rol}`. · Te unes como `{tu nombre}`. · Uniéndote al grupo… · No te uniste al grupo · Si cambias de opinión, vuelve a abrir el enlace antes del `{fecha}`. · Ir a MATU |
| Estados de la invitación | Esta invitación venció · Las invitaciones duran 7 días, y esta ya terminó. · Esta invitación ya se usó · Cada invitación sirve una sola vez. · Esta invitación no está disponible · Puede que se haya copiado incompleta o que ya no exista. Revisa que la abriste completa desde el mensaje. · Esta invitación se bloqueó · El código se escribió mal cinco veces. Por seguridad, ya no sirve. |
| Lista | Se unió el `{fecha}`. · Cambiar lo que puede hacer · Cambiar tu rol · Solo quien administra el grupo invita, cambia los roles y saca a alguien. · Por ahora solo estás tú. Invita a quien cuida contigo. · Ya no administras el grupo. · La creó `{nombre}`. · alguien que ya no está en el grupo |
| Último admin | Eres la única persona que administra el grupo. Para dejar ese rol, primero dáselo a otra persona. |
| Cambiar el rol | Ahora (etiqueta) · Elige otro rol para guardar. · Se corta 1 enlace de relevo que compartió. · `{nombre}` dejará de ver la ficha. · Como paga, no verá la ficha hasta que le des permiso. · Dejarás de administrar el grupo. Para volver a hacerlo, otra persona que administra tendrá que dártelo. · Guardando el cambio… · Cortamos `{n}` enlaces. · Cortamos 1 enlace. · Otra persona del grupo cambió lo que puede hacer `{nombre}` mientras lo mirabas. Ahora `{nombre}` `{rol}`. Revisa y vuelve a elegir. |
| «Paga» sin capa 3 | Ve los insumos. Ve la ficha solo si quien administra le da permiso. |
| Permiso del pagador | ¿Dejar que `{nombre}` vea la ficha? · Podrá leer la ficha de `{nombres_pila}` y ver sus enlaces de relevo. No podrá cambiarla ni compartirla. · No por ahora · Ahora `{nombre}` puede ver la ficha. · ¿Quitarle la ficha a `{nombre}`? · `{nombre}` dejará de ver la ficha desde ahora. · No quitar · `{nombre}` ya no ve la ficha. |
| Sacar | No tiene enlaces de relevo que abran ahora. · Para volver, tendrías que invitar a `{nombre}` de nuevo. · Sacando del grupo… · No pudimos sacar a `{nombre}` del grupo. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba. |
| Salir | Dejarás de ver `{grupo}` y se cortan los enlaces de relevo que compartiste. · Lo que escribiste en la ficha queda, porque es parte del cuidado de `{nombres_pila}`. · Para volver, alguien que administra el grupo tiene que invitarte de nuevo. · Saliendo del grupo… · Saliste de `{grupo}`. · No pudimos sacarte del grupo. Revisa tu conexión y vuelve a intentarlo. Sigues en el grupo. · Eres la única persona que administra `{grupo}`. Para salir, primero da ese rol a otra persona. · Eres la única persona de `{grupo}`, así que no puedes salir. Si ya no usan MATU para cuidar a `{nombres_pila}`, puedes borrar sus datos en «Borrar sus datos», más arriba. |

**Ajustes a textos del analista:** «Con tu rol podrás: `{descripción}`.» pasa a «Tu rol: `{rol}`. `{descripción}`» (0.2). «Ese código no es. Te quedan `{n}` intentos.» suma «Después, la invitación se bloquea.» (4.3). El aviso D-42-9 va sin el nombre y sin «renuévala» (5.6, aprobado). «Código: `{codigo}`.» sale del texto, porque los dígitos ya están a la vista (3.4).

---

## 12. Cómo la voy a revisar

Con la app funcionando (`npm run dev` en `web/`, con el doble de la API o contra el backend de la rama), con datos sintéticos (Carmen administra, Rodrigo paga, Rosa cuida, Familia Soto, María):

- Capturas a 360, 1280 y 1920 px, en tema claro y oscuro, y a 320 px con el texto al 200 %, de: `/grupo` como admin y como pagador, `/grupo/invitar` con «Administra el grupo» elegido, `/grupo/invitar/listo` con y sin código, los cuatro pasos de `/invitacion`, cada estado de 4.7, y los cinco diálogos con su error.
- Mido el contraste de las notas en los dos temas, el alto de cada botón de texto de las filas, y que nada mida menos de 17 px.
- Recorro todo con el teclado y con el lector de pantalla: el foco al abrir y cerrar cada diálogo, el código leído dígito a dígito y los anuncios.
- Reviso el historial y el almacenamiento del navegador después de aceptar una invitación: sin token ni código.
- Contrasto los criterios de la sección 10, uno por uno.

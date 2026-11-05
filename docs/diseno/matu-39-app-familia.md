# MATU-39 · App de familia: cuenta, grupo, persona, entrada y ficha inicial · Especificación de diseño

**Versión 1.1 · 03/11/2026** (ajustes por las decisiones de Jorge del 03-11: celular en la cuenta, «¿Olvidaste tu contraseña?», dictado y barra fija) · agente 6 (UI/UX) · para el frontend, antes de construir
**Historia:** el primer tramo de la app de familia real: Carmen crea su cuenta, su grupo y registra a María con su autorización, entra y sale, y llena la ficha de tres campos en menos de 3 minutos.
**Dónde se construye:** `web/`, React 19, TypeScript, Vite y Tailwind CSS v4 (ADR-026), mobile first, contra la API real.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` (los de `docs/diseno/matu-23-pagina-relevo.md`, sección 6.2, sin agregar ninguno) · la demo aprobada (`Demo/src/familia/Alta.tsx`, `Shell.tsx`, `Ficha.tsx`, `Demo/src/components/Ui.tsx`, `HojaFicha.tsx`, `TextoFicha.tsx`, `Demo/src/demo/datos.ts`) · `docs/lenguaje.md` del repositorio MATU (secciones 2, 3, 5, 6, 8 y 11) · `docs/legal/politica-privacidad.md` del repositorio MATU (secciones 2, 5 y 6) · checklist de accesibilidad de `docs/estrategia-pruebas.md`, sección 7 · contrato `docs/api/openapi.json` y `docs/api/README.md` (decisiones 1 a 64).

**Cómo se lee:** igual que MATU-23. Los textos entre comillas latinas «» van tal cual. Los **[PROPUESTO]** no están en `lenguaje.md`: el orquestador los lleva a Jorge y entran a `lenguaje.md` en el mismo pull request. Los **[INSTRUCCIÓN]** los dictó el orquestador por decisión de Jorge (02-11) y tampoco están todavía en `lenguaje.md`. Las llaves son datos de la API. **Donde la demo dice `pino`, en `web/` es `turquesa`.** Donde la demo dice `@3xl:` sobre el contenedor implícito, en `web/` es `@3xl/app:`, como en MATU-23.

---

## 0. Lo que tiene que decidir alguien más

| # | Qué | Por qué importa | Lo que hace la especificación mientras tanto |
|---|---|---|---|
| D1 | ~~`lenguaje.md` decía "sesión" y "email".~~ **Resuelta (Jorge, 03-11):** se corrige en el PR MATU #23, que dice "correo" | — | Usa "correo" y "entrar" |
| D2 | ~~El 409 `email-registrado` falta en `openapi.json`.~~ **Lo resuelve el backend dentro de MATU-39** (03-11) | — | La pantalla lo trata por `type` (3.2) |
| D3 | ~~El pagador con permiso para ver la ficha.~~ **Lo resuelve el backend dentro de MATU-39** (03-11), con `puede_ver_plan` y el nombre que corresponda. Hasta verlo en el contrato, la especificación mantiene el plan B: el pagador ve «Ficha» y un 404 lleva a 5.6 | — | Cuando el contrato lo traiga, «Ficha» se muestra al pagador solo con `puede_ver_plan` |
| D4 | ~~Dictar en vez de escribir.~~ **Resuelta (Jorge, 03-11):** se construye, **sin aviso en la pantalla**; se informa en la política de privacidad | — | Especificado en 3.7.1 |
| D5 | **No hay `GET /v1/usuarios/yo`** (sigue igual, 03-11) (README, "Lo que no hay") | La app no puede saludar ni mostrar "Conectada: Carmen" como la demo | La cabecera no muestra el nombre de quien entra (2.1). Queda para el sprint 4 |
| D6 | **El texto de `credenciales-invalidas` (401 de `POST /v1/sesiones`) y el de 503** no están en `lenguaje.md` | El frontend no inventa textos | Textos **[PROPUESTO]** en 3.3 |
| D7 | ~~`scroll-padding-bottom` para la barra fija.~~ **Autorizado y hecho (03-11)** en la capa base de `web/src/index.css` | — | Sección 7 |
| D8 | **Textos que faltan en `lenguaje.md`** | — | Lista completa en la sección 8 |

---

## 1. Para quién y qué

**Carmen** cuida a su mamá, María. Abre MATU en su celular, con una mano y poco tiempo. En la primera visita crea su cuenta, nombra su grupo, registra a María con su autorización y escribe la ficha. La meta: **de la cuenta creada a la ficha completa en menos de 3 minutos**, sin aprender nada.

**Las veces siguientes** entra (o ya está dentro) y cae directo en la ficha de María.

**Lo que la hace MATU:** igual que en la demo, la hoja de la ficha con su imán de miel es lo único con presencia (DISENO.md, principio 1). El resto es papel, tinta y un solo botón `turquesa` macizo por pantalla.

**Rutas** (ninguna lleva nombres, ids de persona ni texto de la ficha; el grupo y la persona elegidos viven en memoria):

| Ruta | Pantalla | Sin entrar |
|---|---|---|
| `/` | Redirige: sin entrar → `/entrar`; sin grupo → `/empezar/grupo`; sin persona → `/empezar/persona`; si no → `/ficha` | — |
| `/crear-cuenta` | Crear cuenta (3.2) | Sí |
| `/entrar` | Entrar (3.3) | Sí |
| `/empezar/grupo` | Crear el grupo (3.4) | No |
| `/empezar/persona` | ¿A quién cuidas? (3.5, paso 1 de 2) | No |
| `/empezar/autorizacion` | La autorización (3.5, paso 2 de 2) | No |
| `/ficha` | La ficha (3.6) | No |
| `/ficha/su-dia`, `/ficha/si-se-altera`, `/ficha/a-quien-llamar` | El editor de un campo (3.7) | No |
| `/insumos` | MATU-36 (`docs/diseno/matu-36-insumos.md`) | No |
| `/compartir` | MATU-48. En este sprint solo se reserva la entrada | No |
| `/r` | La página del relevo (MATU-23). **No usa este marco** | — |

Una ruta que pide haber entrado, sin haber entrado, lleva a `/entrar` y, después de entrar, vuelve a esa ruta (guardada en memoria, nunca en la URL ni en almacenamiento).

---

## 2. El esqueleto (se construye primero, el martes)

MATU-36, MATU-48 y MATU-55 se montan encima. Se copia `ShellFamilia` de `Demo/src/familia/Shell.tsx` con estos cambios.

### 2.1 Estructura

```
<div id="raiz">                                     contenedor `app`
  <a href="#contenido">Saltar al contenido</a>      sr-only hasta recibir foco
  <header>                                          marca, distintivo, persona, Salir
  <nav aria-label="Secciones">                      Ficha · Insumos · Compartir
  <main id="contenido" tabIndex={-1}>               la pantalla
</div>
```

**A 360 px (teléfono):**

```
┌────────────────────────────────────┐
│ (♥) MATU          [Piloto académico│
│                    con datos de    │
│                    prueba]         │
│ Cuidas a                           │
│ María Soto  ▾          [Salir]     │
├────────────────────────────────────┤
│                                    │
│  la pantalla                       │
│                                    │
│                                    │
├────────────────────────────────────┤  barra fija abajo (`telefono:`)
│  [▤ Ficha]  [▢ Insumos] [⇪ Compartir]│
└────────────────────────────────────┘
```

**Pantalla ancha (≥ 64 rem en `app`, `@4xl/app:`):**

```
┌──────────────┬──────────────────────────────────────────────────────────┐
│ (♥) MATU     │ Cuidas a María Soto ▾     [Piloto académico con datos…]  │
│              │                                              [Salir]     │
│ ▤ Ficha de   ├──────────────────────────────────────────────────────────┤
│   relevo 2/3 │                                                          │
│ ▢ Insumos    │   la pantalla, `max-w-7xl` centrada                      │
│ ⇪ Compartir  │                                                          │
└──────────────┴──────────────────────────────────────────────────────────┘
```

- **Columna izquierda** (copia de `ShellFamilia`): `@4xl/app:grid-cols-[16.5rem_minmax(0,1fr)]`, borde `linea`, la marca (`Marca` de `web/src/compartido/ui/Marca.tsx`, ya existe) y la navegación. **Fondo `papel`, nunca un color macizo** (DISENO.md 5).
- **Cabecera** (`Encabezado` de la demo), `border-b border-linea px-4 angosto:px-2 @3xl/app:px-11 py-3`, `flex flex-wrap items-center justify-between gap-x-6 gap-y-2`. Cambios contra la demo:
  1. **Se quita** la fecha y hora y el círculo con la inicial y «Conectada: Carmen» (D5).
  2. **Se agrega el distintivo del piloto**, idéntico a MATU-23 2.2 (mismo componente, que el frontend saca de `web/src/relevo/Marco.tsx` a `compartido/ui/`). En el teléfono va junto a la marca; en pantalla ancha, en la cabecera.
  3. **La persona:** «Cuidas a» (`text-sm text-tenue`, lo mismo que la demo) y debajo `{nombre}` (`text-lg font-bold`). Si hay más de una persona o más de un grupo, es el selector (2.3).
  4. **«Salir»** (2.4).
- **La cabecera no es fija.** Lo único fijo es la barra de secciones en `telefono:`, como en la demo. Con `angosto:` (texto al 200% en 320 px) la barra deja de ser fija y vuelve al flujo arriba del contenido.
- **`main`:** `@container/main flex-1 px-4 angosto:px-2 @3xl/app:px-11 pt-6 pb-16 telefono:pb-36 outline-none`, y dentro `mx-auto max-w-7xl`.

### 2.2 La navegación

Copia de `Navegacion` de la demo, con tres secciones en este sprint (las demás no aparecen, ni deshabilitadas):

| Sección | `texto` | `corto` (barra del teléfono) | Ícono lucide | Ruta | Pista (`estadoPista`) |
|---|---|---|---|---|---|
| Ficha | «Ficha de relevo» | «Ficha» | `ClipboardList` | `/ficha` | «`{n}` de 3» con `completitud` de la ficha (0, 33, 67, 100 → 0, 1, 2, 3) |
| Insumos | «Insumos» | «Insumos» | `Package` | `/insumos` | La de MATU-36 (pronto con palabra, nunca solo el punto) |
| Compartir | «Compartir» | «Compartir» | `Share2` | `/compartir` | Ninguna |

- La sección activa lleva `aria-current="page"`, `font-bold text-turquesa` y fondo `hoja` con `ring-1 ring-linea` (en el teléfono `bg-rocio` sin anillo). El estado activo se ve por forma (fondo y negrita), no solo por color.
- Cada entrada mide al menos 48 px de alto: la demo usa `min-h-11` (44 px) en pantalla ancha. **Cambia a `min-h-12`.** En el teléfono, `telefono:min-h-14` como la demo.
- La barra del teléfono: `telefono:grid-cols-3` (la demo usa 5).
- **«Compartir» mientras MATU-48 no existe:** la entrada aparece y la ruta muestra el estado vacío de 5.5. No hay `href="#"`.
- **Por rol** (lo trae `GET /v1/grupos`, campo `rol`):
  - `admin` y `cuidador`: las tres.
  - `pagador`: «Ficha» e «Insumos». «Compartir» no aparece (no puede crear accesos).
  - `observador`: **sin «Ficha» y sin «Compartir»**. Solo «Insumos». `/` lo lleva a `/insumos`. Si escribe `/ficha` a mano, ve 5.6 sin pedir nada a la API.
  - Un rol que no se reconoce se trata como `observador`.

### 2.3 Selector de grupo y de persona

Solo aparece si `GET /v1/grupos` trae más de un grupo o la lista de personas trae más de una. Con uno de cada uno es texto, no control.

- Un botón con el nombre y `ChevronDown` (`aria-expanded`, `aria-controls`), mínimo 48 px de alto, que abre una lista en el flujo de la página (no un menú flotante: con el texto al 200% un flotante se corta).
- La lista: si hay más de un grupo, un `fieldset` por grupo con su `nombre` como `legend` y un radio por persona (`GrupoOpciones` de la demo). Cada opción, `{nombre}` de la persona; si el rol es `admin` o `cuidador`, debajo en `text-tenue` «Le dicen `{nombre_pila}`» **[PROPUESTO]**.
- Elegir cambia el grupo (`X-Grupo-Id`) y la persona en memoria, cierra la lista, lleva a la sección actual y pone el foco en el `h1`. El anuncio es el título de la pantalla nueva.
- Al entrar se elige el **primer grupo y la primera persona** que devuelve la API. No se recuerda la elección entre visitas (no hay dónde guardarla sin `localStorage`).

### 2.4 Salir

- Botón `variante="texto"` (el de `Boton` de `web/src/compartido/ui/Boton.tsx`), con el ícono `LogOut` y la palabra «Salir». 48 px de alto.
- Llama a `POST /v1/sesiones/cerrar` con `X-MATU-Cliente: web`. **Pase lo que pase** (204, error o sin red), borra el token y todo lo que está en memoria y lleva a `/entrar` con el aviso en `Nota tono="rocio"`: «Saliste de MATU. Para volver, entra con tu correo y tu contraseña.» **[PROPUESTO]**
- Sin confirmación: salir es reversible.

### 2.5 Título del documento

`<title>` = «`{título de la pantalla}` · MATU». Nunca el nombre de la persona ni el del grupo (se ve en la lista de pestañas y en el historial). Ejemplo: «Ficha de relevo · MATU».

### 2.6 Foco y movimiento

Igual que MATU-23 2.4: al cambiar de pantalla el foco va al `h1` (`tabIndex={-1}`, `outline-none` solo en el `h1`). Las pantallas no entran deslizándose: aparecen con `animate-aparecer` o sin animación. Con `prefers-reduced-motion`, todo inmediato (lo resuelve la capa base).

---

## 3. Pantallas

### 3.1 Cargando (al abrir la app)

Al abrir o recargar no hay token. La app llama a `POST /v1/sesiones/renovar` y después a `GET /v1/grupos` y a la lista de personas (README, "Cómo arranca la app").

- Mientras tanto: el marco de MATU-23 (marca y distintivo, sin navegación) y en `main` «Abriendo MATU…» **[PROPUESTO]** en `text-tenue`, con `role="status"`. Sin esqueletos grises ni girador. Si tarda menos de 400 ms no se muestra nada.
- 200 → sigue a la ruta pedida o a `/`.
- 401 `sesion-expirada` en la primera carga → `/entrar` **sin aviso** (es lo normal la primera vez).

### 3.2 Crear cuenta

**Objetivo:** que Carmen tenga cuenta en una pantalla, sin pensar.
**Copia:** `MarcoAlta` y `Cuenta` de `Alta.tsx`. **Cambia:** sin los valores precargados de la demo (los campos empiezan vacíos), el panel `aside` pasa de `bg-pino` macizo a `bg-hoja` con borde `linea` (DISENO.md 5, barra lateral maciza descartada; el panel de la demo era la bienvenida de la presentación) y los pasos del panel pasan a ser cuatro.

**Jerarquía:** 1) el título, 2) los cuatro campos, 3) «Crear cuenta». **El celular es obligatorio** (decisión de Jorge del 03-11, para recuperar el acceso, MATU-57). **El contrato de `POST /v1/usuarios` todavía no tiene el campo**: lo agrega el backend; el nombre del campo lo fija el contrato, no esta especificación. Debajo, la entrada para quien ya tiene cuenta.

**A 360 px:**

```
(♥) MATU      [Piloto académico / con datos de prueba]

Paso 1 de 4
Crea tu cuenta                      titular text-3xl
Para empezar te pedimos solo esto.  text-tenue

Tu nombre
[                              ]
Tu correo
[                              ]
Tu celular
[+56 9                         ]
Para ayudarte a recuperar tu cuenta si olvidas la contraseña.
Una contraseña
[                              ]
Al menos 10 caracteres.

[ Crear cuenta ]                    único `turquesa` macizo

¿Ya tienes cuenta? Entrar           enlace de texto
```

**Pantalla ancha:** `@4xl/app:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]` como `MarcoAlta`. A la izquierda, sobre `hoja`, la marca, la frase «Que el cuidado no dependa de una sola persona.» (`titular text-2xl @2xl:text-4xl`, tinta) y la lista de pasos; a la derecha el formulario en `max-w-3xl`. Correo y celular en dos columnas (`@2xl/main:grid-cols-2`); la contraseña debajo. El botón **no** es de ancho completo.

**Pasos del panel** (`ol aria-label="Pasos para empezar"`, el mismo marcado de la demo: círculo con número, `Check` cuando está hecho, texto `sr-only` «, hecho» / «, ahora»): «Tu cuenta» · «Tu grupo» · «A quién cuidas» · «La autorización» **[PROPUESTO: «Tu grupo» y «La autorización»; la demo dice «El permiso»]**. En el teléfono los pasos no se muestran; queda «Paso `{n}` de 4» sobre el título.

**Campos** (`CampoTexto` de `Ui.tsx`, con su etiqueta visible siempre arriba, nunca solo el `placeholder`):

| Etiqueta | Atributos | Ayuda |
|---|---|---|
| «Tu nombre» | `autoComplete="given-name"`, `maxLength={100}` | «Así te verán en tu grupo.» **[PROPUESTO]** |
| «Tu correo» | `type="email"`, `autoComplete="email"`, `maxLength={254}` | — |
| «Tu celular» | `type="tel"`, `autoComplete="tel"`, `inputMode="tel"`, obligatorio | «Para ayudarte a recuperar tu cuenta si olvidas la contraseña.» **[PROPUESTO]** Error: «Escribe un celular de Chile, por ejemplo +56 9 5555 0137.» (lenguaje 8, el mismo de Compartir) |
| «Una contraseña» | `type="password"`, `autoComplete="new-password"`, `minLength={10}`, `maxLength={128}` | «Al menos 10 caracteres.» |

- Botón con un ícono `Eye`/`EyeOff` y la palabra «Mostrar» / «Ocultar» **[PROPUESTO]** junto a la contraseña, 48 px, `aria-pressed`.
- **Validación en el cliente**, al enviar, nunca mientras escribe, con `MensajeError` bajo el campo y `aria-describedby`: nombre vacío «Escribe tu nombre.» **[PROPUESTO]**; correo sin `@` «Revisa tu correo.» **[PROPUESTO]**; contraseña corta «La contraseña necesita al menos 10 caracteres.» (demo). El foco va al primer campo con error.
- **Enviando:** el botón dice «Creando la cuenta…», `disabled`, `aria-busy`. Los campos no se borran.
- **201:** la app llama a `POST /v1/sesiones` con lo mismo (la API no entra sola) y sigue a `/empezar/grupo`. Sin pantalla de "cuenta creada": el paso 2 marcado como hecho lo dice. Anuncio en una región `aria-live="polite"`: «Cuenta creada.» (demo).
- **409 `email-registrado`** (D2): `Nota tono="atenta"` con el título «Ese correo ya tiene una cuenta» y el texto «Entra con tu contraseña, o usa otro correo.», y un `Boton variante="secundario"` «Entrar con ese correo» que lleva a `/entrar` con el correo ya escrito (en memoria). Textos de la demo con "email" cambiado a "correo" (D1).
- **422:** el mensaje va bajo el campo de `errores[].campo`, con textos **[PROPUESTO]**: `nombre` «Escribe tu nombre, de hasta 100 letras.»; `email` «Revisa tu correo.»; `contrasena` «La contraseña necesita entre 10 y 128 caracteres.». Nunca el `mensaje` de la API.
- **Red o 5xx:** el texto general de lenguaje 8 en `Nota tono="pronto"` sobre el botón.

### 3.3 Entrar

**Objetivo:** volver a la ficha de María con dos datos.
**Copia:** `Entrar` de `Alta.tsx`, dentro del mismo `MarcoAlta` sin pasos. **Cambia:** sin precarga, la bajada y "email".

```
Entrar                                titular text-3xl
[aviso, si viene de una entrada vencida o de Salir]
Tu correo
[                              ]
Tu contraseña
[                              ]  [Mostrar]
¿Olvidaste tu contraseña?             (cuando exista MATU-57)

[ Entrar ]

¿No tienes cuenta? Crear cuenta
```

- Bajada: **ninguna**. La de la demo («Tu sesión dura 15 minutos…») dice "sesión" (D1) y además ya no es cierta (el refresh dura 30 días).
- Campos: «Tu correo» (`autoComplete="email"`) y «Tu contraseña» (`autoComplete="current-password"`).
- Botón: «Entrar» / «Entrando…». Habilitado siempre; con un campo vacío, al enviar, «Escribe tu correo y tu contraseña.» **[PROPUESTO]**.
- **200:** guarda el token en memoria, pide grupos y personas, y va a la ruta guardada o a `/` (que decide según 1).
- **Avisos** (`Nota`, arriba del formulario, `role="status"` para que se lea al llegar):

| Situación | Tono | Texto |
|---|---|---|
| Entrada vencida (401 `sesion-expirada` al renovar después de haber estado dentro, o renovar falla tras un 401 `token-invalido`) | `rocio` | «Hace tiempo que no entrabas. Vuelve a entrar con tu correo y tu contraseña.» **[INSTRUCCIÓN]** |
| Después de «Salir» | `rocio` | 2.4 |
| 401 `credenciales-invalidas` | `pronto`, bajo los campos | «El correo o la contraseña no coinciden. Revísalos y vuelve a intentarlo.» **[PROPUESTO]** No dice cuál de los dos falló |
| 429 `demasiadas-peticiones` | `atenta` | «Hubo varios intentos de entrar. Espera `{minutos}` minutos. Si olvidaste tu contraseña, pídele ayuda a alguien de tu familia.» **[INSTRUCCIÓN]** `{minutos}` = `Retry-After` en segundos, redondeado hacia arriba, mínimo 1. Con 1, «Espera 1 minuto.» **[PROPUESTO]**. El botón queda `disabled` hasta que pase el tiempo, y vuelve a habilitarse solo, sin anunciar una cuenta regresiva |
| 503 | `pronto` | «MATU no está disponible en este momento. Vuelve a intentarlo en unos minutos.» **[PROPUESTO]** |
| Red o 5xx | `pronto` | Lenguaje 8, texto general |

- **Enlace «¿Olvidaste tu contraseña?»** (decisión de Jorge del 03-11), de texto, `turquesa` subrayado, 48 px de alto, bajo el campo de la contraseña. Lleva a la pantalla de recuperación, que especifica MATU-57. Mientras MATU-57 no exista, el enlace no se pone (nunca un `href="#"`). Cuando exista, el 429 cambia «pídele ayuda a alguien de tu familia» por ese enlace (texto a Jorge).

### 3.4 Crear el grupo

**Objetivo:** nombrar el grupo en un dato.
**Copia:** `MarcoAlta`, `Titulo` y `CampoTexto`. **Nuevo frente a la demo:** la demo creaba el grupo sola con «Cuidado de `{nombre_pila}`», que pone el nombre de la persona en el grupo; la política (sección 2, "De tu grupo") lo desaconseja.

```
Paso 2 de 4
Ponle nombre a tu grupo              titular text-3xl   [PROPUESTO]
Es el grupo de las personas que cuidan contigo.        [PROPUESTO]

Nombre del grupo                                       [PROPUESTO]
[                              ]
Usa un nombre corto, como «Familia Soto». No incluyas el nombre
completo de la persona que cuidas ni datos de salud.

[ Crear el grupo ]                                     [PROPUESTO]
```

- La ayuda es el texto exacto de la política de privacidad, sección 2, y va siempre visible, enlazada con `aria-describedby`.
- `maxLength={60}` **[PROPUESTO, el contrato no fija largo]**; `autoComplete="off"`.
- Vacío: «Escribe un nombre para el grupo.» **[PROPUESTO]**.
- Enviando: «Creando el grupo…» **[PROPUESTO]**. **201:** fija `X-Grupo-Id` con el `id` y va a `/empezar/persona`. **422:** el mismo texto de vacío. Red/5xx: lenguaje 8.
- **Con un grupo ya creado** (por ejemplo, volvió atrás): `/empezar/grupo` redirige a `/empezar/persona`. Esta pantalla no sirve para crear un segundo grupo en este sprint.

### 3.5 Registrar a la persona con su autorización (MATU-07)

**Objetivo:** que Carmen registre a María y dé la autorización correcta sin entender de leyes.
**Copia:** `AQuien` y `Permiso` de `Alta.tsx`, con `APOYOS`, `CALIDADES` y `AVISO_CUIDADOR` de `Demo/src/demo/datos.ts`. Son dos pantallas y **un solo `POST /v1/grupos/{grupo_id}/personas-cuidadas`** al final: lo del primer paso vive en memoria hasta entonces.

#### 3.5.1 ¿A quién cuidas? (`/empezar/persona`, paso 3 de 4)

Igual a `AQuien` de la demo. Cambios: sin valores precargados, el título «¿A quién cuidas?», y la dirección se completa con los campos del contrato.

```
Paso 3 de 4
¿A quién cuidas?

¿Cómo se llama?               ¿Cómo le dicen?
[                    ]        [                    ]
                              Es el nombre que verá quien te reemplace.

¿Cuánto apoyo necesita en el día a día?
( ) Se maneja sola, con supervisión
( ) Necesita apoyo en varias cosas
( ) Necesita apoyo en todo

¿Dónde vive? Puedes dejarlo para después
La pedimos recién con el primer pedido. La ficha no la usa.
Calle [          ] Número [    ] Comuna [        ]
Depto (si tiene) [    ]                               [PROPUESTO]

[ShieldCheck] No te preguntamos qué enfermedad tiene. No lo necesitamos y no lo guardamos.

[ Continuar ]
```

- `nombre` `maxLength={120}`, `nombre_pila` `maxLength={60}`, `nivel_apoyo` con `GrupoOpciones` (radios de 48 px, el elegido con borde `turquesa` **y** el punto del radio: forma más color). **Sin opción elegida de partida** (la demo trae `apoyo_parcial`): la persona elige.
- **Dirección:** se envía solo si están calle, número y comuna (los requeridos de `DireccionNueva`). `depto` opcional. **No se piden** `etiqueta`, `region` ni `referencia` en este sprint.
- Errores (de la demo): «Escribe su nombre y cómo le dicen para seguir.» y «Completa calle, número y comuna, o deja los tres vacíos.»; sin nivel elegido, «Elige cuánto apoyo necesita.» **[PROPUESTO]**.
- La nota con `ShieldCheck` va sobre `bg-rocio`, como en la demo, con el ícono en `text-turquesa`.

#### 3.5.2 La autorización (`/empezar/autorizacion`, paso 4 de 4)

Igual a `Permiso` de la demo. Cambios: título y botones sin la palabra "permiso" donde la política dice "autorización", el aviso marcado con forma y no solo con color, y sin calidad elegida de partida.

```
Paso 4 de 4
La autorización para guardar su ficha                     [PROPUESTO; demo: «Un permiso necesario»]
Lo que anotes sobre el cuidado de {nombre_pila} es información sensible.
Para guardarla necesitamos saber en qué calidad das la autorización.   [PROPUESTO, ajuste de la demo]

Doy esta autorización porque…                              [PROPUESTO; demo: «Doy este permiso porque…»]
( ) {nombre_pila} lo autoriza y yo lo registro
    {nombre_pila} decide por sí misma y tú anotas su decisión.
( ) Soy su representante legal
    Tienes un nombramiento legal para representarla.
( ) La cuido, pero no soy su representante legal          [PROPUESTO: el texto de la demo está en datos.ts]
    ...

[si representante_legal]  Referencia del documento [            ]
                          Por ejemplo: resolución y fecha

[si cuidador_de_hecho]
┃ [TriangleAlert] Aviso: tu autorización tiene un límite
┃ (tres párrafos, texto exacto de la política 5, v1.0)
┃ [x] Leí el aviso y lo acepto

Lo que declaras
(la declaración exacta de la calidad elegida, política 5)

[ Acepto y registro a {nombre_pila} ]                     [PROPUESTO; demo: «Acepto y continúo»]
```

- **Los textos de las tres calidades y de las tres declaraciones salen de `CALIDADES` de la demo**, que coinciden con la política v0.9, sección 5. El de `cuidador_de_hecho` se copia tal cual de `datos.ts` (no lo repito aquí para no tener dos copias). Donde la demo dice «Ella» o «María» se reemplaza por `{nombre_pila}`, como hace la demo. **Pendiente para el analista normativo:** «decide por sí misma» y «representarla» llevan género, y el modelo no lo guarda (lenguaje 5, decisión del 27-10).
- **Aviso del cuidador de hecho:** `AVISO_CUIDADOR` (id `aviso_cuidador_de_hecho`, versión `1.0`), con el título y los tres párrafos exactos de la política. Se envía en `aviso: {id, version}`. Contenedor: `border-l-4 border-atenta bg-atenta-fondo`, como la demo, **más el ícono `TriangleAlert`** (`aria-hidden`) junto al título, para que no dependa del color. La casilla, `size-5 accent-turquesa` dentro de una `label` de `min-h-12`.
- **«Lo que declaras»:** `Nota` `rocio`. Cambia al elegir otra calidad.
- `referencia_documento` `maxLength={200}`, solo con `representante_legal`; con las otras se envía `null`.
- Errores (de la demo): «Elige en qué calidad das el permiso.» → «Elige en qué calidad das la autorización.» **[PROPUESTO]**; «Escribe la referencia del documento que te nombra representante.»; «Marca que leíste el aviso para seguir.».
- **Enviando:** «Registrando a `{nombre_pila}`…» **[PROPUESTO]**. **201:** la persona queda elegida y va a `/ficha`, con el anuncio «`{nombre_pila}` quedó registrada. Ahora, su ficha.» **[PROPUESTO]**. (Ojo con el género: alternativa neutra «Listo. Ahora, la ficha de `{nombre_pila}`.» **[PROPUESTO, preferida]**.)
- **422:** el texto bajo el campo de `errores[].campo`; si el campo pertenece al paso 1 (`nombre`, `nombre_pila`, `direccion.*`), un enlace «Volver a corregir los datos de `{nombre_pila}`» **[PROPUESTO]** que lleva a 3.5.1 con lo escrito.
- **404** (el rol no alcanza: pagador u observador que llegó a esta ruta): lenguaje 8, `no-encontrado`.
- Volver de 3.5.2 a 3.5.1 (`Volver` de la demo, enlace de texto con `ChevronLeft`, 48 px) conserva todo lo escrito.

### 3.6 La ficha (`/ficha`)

**Objetivo:** ver qué falta y empezar por ahí. Meta total: **los tres campos en menos de 3 minutos**.
**Copia:** `TuFicha` de `Ficha.tsx` con `BarraCampos`, `HojaFicha` y `TextoFicha`. **Cambia:** sin `PestanasFicha` en este sprint (Compartir es otra sección; «Quién la vio» y «Enlaces» no existen todavía; «Imprimir» queda quitada: la ficha no se imprime ni se exporta, ADR-029), y sin la nota del cifrado (lenguaje 5.4, **[desde MATU-11]**: MATU-11 ya está hecho, así que **sí se muestra**; si el orquestador no lo confirma, se omite).

**Jerarquía:** 1) el título y cuántos campos van, 2) el primer campo que falta con su botón, 3) la hoja como vista previa.

**A 360 px:**

```
Ficha de relevo                         titular text-3xl
Tres campos cortos para que quien te reemplace sepa qué hacer.
Cada campo se guarda por separado y puedes compartir solo algunos.

1 de 3 campos listos   ▮▯▯               BarraCampos + texto

┌ Su día ────────────────── Listo ✓ ┐
│ 08:00 Despierta…                  │
│ Lo escribió Carmen: hoy, 10:42    │
│ [Editar «Su día»]                 │
└───────────────────────────────────┘
┌ Si se altera ─────────── Falta ○ ┐
│ ¿Qué calma a María cuando se      │
│ angustia?                         │
│ [Completar «Si se altera»]        │   el primero que falta: único `turquesa` macizo
└───────────────────────────────────┘
┌ A quién llamar ───────── Falta ○ ┐
│ …                                 │
│ [Completar «A quién llamar»]      │   secundario
└───────────────────────────────────┘
```

**Pantalla ancha:** dos columnas `@4xl/main:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]`: a la izquierda la lista; a la derecha `HojaFicha` con el título «Así la ve quien te reemplaza» (lenguaje 5.4), como `VistaPrevia` de la demo.

- **Textos:** lenguaje 5.4 tal cual (título, bajada, avance, Listo/Falta, Completar/Editar, Lo escribió).
- **Listo / Falta:** `Etiqueta` de `Ui.tsx`, `ok` con `Check` y «Listo», neutro con `Circle` y «Falta». Palabra más forma.
- **Una sola acción principal:** el botón del **primer campo que falta** es `Boton` primario; los demás, `variante="secundario"`. Con los tres listos no hay primario macizo (los tres «Editar» son secundarios) y aparece, si MATU-48 ya está, el enlace «Compartir con un relevo» (lenguaje 6.1).
- **Quién lo escribió:** `{autor}` = `actualizado_por.nombre`; `{cuándo}` con `Cuando` de `Ui.tsx` (`DD/MM/AAAA, HH:MM`, o «hoy, HH:MM»), `cifras`.
- **Campo vacío:** la pregunta guía (lenguaje 5.1 a 5.3, con `{nombre_pila}`) en `text-tenue`; en la hoja, «Sin completar».
- **Pagador** que ve la ficha: sin botones Completar/Editar si el `PUT` le responde 404 (no se sabe de antemano, D3): el botón se muestra y el 404 lleva a 5.6.

### 3.7 El editor de un campo (`/ficha/su-dia` y los otros dos)

**Objetivo:** escribir un campo y guardarlo sin perder nada.
**Copia:** `Completar` y `Guardado` de `Ficha.tsx`. **Cambia:** guardado contra la API con `ETag`, sin interfaz optimista.

**A 360 px:**

```
‹ Volver a la ficha                                      [PROPUESTO]
Campo 1 de 3
Su día                                    titular text-3xl
¿Cómo es un día normal para María? Puedes contar un día bueno o uno difícil.

┌──────────────────────────────────┐
│                                  │  textarea, renglones, min 8 líneas
│                                  │
└──────────────────────────────────┘
0 de 500 caracteres                       cifras, text-tenue
Por ejemplo: «08:00 Despierta. Le gusta que abran la cortina primero».
Si empiezas con la hora, lo mostramos como línea de tiempo.

[Mic] Dictar en vez de escribir          secundario
[ Guardar ]   Seguir después

Así la ve quien te reemplaza              (debajo en el teléfono; a la derecha en ancho)
[HojaFicha, mientras escribes]
```

- La pregunta es la `label` del `textarea` (lenguaje 5.1 a 5.3, con `{nombre_pila}`; para el pagador sin `nombre_pila`, `{nombre}`, D3). El ejemplo, en `text-tenue`, enlazado con `aria-describedby`.
- `maxLength={500}`. El contador «`{n}` de 500 caracteres» pasa a `text-atenta` con el ícono `TriangleAlert` desde 450 y se anuncia con `aria-live="polite"` solo al cruzar 450 y 500.
- **Botones:** «Guardar» (primario) y «Seguir después» (`variante="texto"`, vuelve a `/ficha` sin guardar; si hay texto sin guardar, lo dice antes: «Lo que escribiste en «`{campo}`» no se guardó. ¿Salir igual?» con «Salir sin guardar» y «Seguir escribiendo» **[PROPUESTO]**).
- **Guardar:** `PUT …/plan/ficha/{campo}` con `If-Match: {etag}` si el campo tiene `etag`, o `If-None-Match: *` si es `null`. Siempre `X-Grupo-Id`.
  - Mientras: «Guardando…», `disabled`, `aria-busy`; el `textarea` queda `readOnly` (no `disabled`, para que se pueda leer y copiar).
  - Vacío sobre un campo que nunca se escribió: no se envía nada y no hay mensaje (lenguaje 5.4).
  - **200 / 201:** guarda el `etag` y la `completitud` nuevos. Pantalla de guardado (de `Guardado` de la demo): título ««`{campo}`» guardado», texto «Vas en `{n}` de 3. Puedes seguir cuando quieras, no se pierde nada.» o «La ficha está completa.», y los botones de lenguaje 6.1 que existan en este sprint: **«Seguir con «`{campo siguiente}`»»** (primario, si falta alguno) y «Ver los campos» (secundario). «Compartir con un relevo» solo si MATU-48 está; «Volver al inicio» no aplica (no hay Inicio). Con la ficha completa, «Ver los campos» es el único y pasa a primario.
  - Para que la meta de 3 minutos se cumpla, la pantalla de guardado **no es un paso intermedio obligatorio**: puede ser un aviso en la misma página. Recomiendo una `Nota tono="ok"` con `CheckCircle2` arriba del editor del siguiente campo y el foco en su `h1`. Lo decide el frontend con la demo como referencia; los textos no cambian.

#### 3.7.1 Dictar en vez de escribir (decisión de Jorge del 03-11)

- **Botón** `Boton variante="secundario"`, ícono `Mic` de lucide (`aria-hidden`) y la palabra «Dictar en vez de escribir» (lenguaje 5.4). Mínimo 48 × 48 px. Va entre el área de texto y «Guardar»: nunca es la acción principal. **Sin aviso en la pantalla** sobre el servicio de voz: se informa en la política de privacidad.
- **Estados:**

| Estado | Ícono | Texto visible | Atributos |
|---|---|---|---|
| Detenido (normal) | `Mic` | «Dictar en vez de escribir» | `aria-pressed="false"` |
| Escuchando | `Square` (detener) | «Escuchando…» (lenguaje 5.4) y, al lado, «Detener» **[PROPUESTO]** | `aria-pressed="true"`; borde `turquesa` de 2 px y fondo `rocio`; un punto `turquesa` que late con `animate-aparecer` en bucle **solo sin** `prefers-reduced-motion`. El estado se lee por la palabra, no por el punto |
| No disponible (el navegador no tiene reconocimiento de voz) | — | **El botón no se muestra.** No hay botón deshabilitado ni explicación | — |
| Sin permiso de micrófono o error | `MicOff` | Vuelve a «Detenido» y bajo el botón, en `text-tenue`: «No pudimos usar el micrófono. Puedes escribir el texto.» **[PROPUESTO]** | `role="status"` |

- **Qué hace con el texto:** lo dictado **se agrega al final** de lo que ya hay en el área (con un espacio si hace falta), nunca reemplaza. Se ve mientras se dicta y la vista previa se actualiza. **No se guarda solo:** la persona lo revisa y toca «Guardar». El tope de 500 caracteres vale igual: al llegar, se detiene el dictado y el contador lo anuncia.
- Se detiene al tocar «Detener», al tocar «Guardar» o «Seguir después», al salir de la pantalla o tras unos segundos de silencio. Mientras se guarda, el botón queda `disabled`.
- Idioma del reconocimiento: `es-CL`. Ningún texto dictado ni audio se guarda en el navegador.

### 3.8 Conflicto (412 `version-desactualizada`)

**Copia:** `Conflicto` de `Ficha.tsx`. Textos de lenguaje 6.2, tal cual. La pantalla **muestra** el conflicto y no guarda nada sola.

```
Rodrigo guardó «Su día» mientras escribías            titular text-2xl
No guardamos lo tuyo encima de lo suyo. Elige qué versión dejar: la otra se descarta.

┌ La de Rodrigo · Guardada a las 10:42 ┐   ┌ La tuya · Lo que escribiste recién, sin guardar ┐
│ (texto de `actual`, o «Vacía»)       │   │ (tu texto)                                       │
│ [Dejar la de Rodrigo]  secundario    │   │ [Dejar la mía]  primario                          │
└──────────────────────────────────────┘   └──────────────────────────────────────────────────┘
MATU no mezcla los textos solo. Si quieres, copia una parte antes de elegir.
```

- En 360 px, una debajo de otra (primero la guardada); en ancho, lado a lado (`@3xl/main:grid-cols-2`). Las dos en `Hoja` sin imán; cada una con su título en negrita (la diferencia no es solo de color).
- Los dos textos son seleccionables. `{autor}` = `actual.actualizado_por.nombre`, o «Otra persona». `{hora}` en `cifras`, HH:MM.
- **«Dejar la de `{autor}`»:** toma `actual` como estado del campo (texto y `etag`), sin `PUT`. Confirmación «Dejaste la versión de `{autor}`.» y vuelve a `/ficha`.
- **«Dejar la mía»:** `PUT` con `If-Match` = el `ETag` de la respuesta 412 (o `If-None-Match: *` si no viene). Si responde otro 412, la pantalla se rehace con el `actual` nuevo. Confirmación «Dejaste tu versión.».
- El foco va al título. La región se anuncia con `role="alert"` solo una vez.

### 3.9 Otros errores del guardado y de la ficha

| Respuesta | Dónde se muestra | Texto | Qué pasa con lo escrito |
|---|---|---|---|
| 428 `falta-version` | `Nota tono="pronto"` sobre los botones | Lenguaje 6.3 | Se queda en el `textarea` |
| 422 `string_too_long` | `MensajeError` bajo el campo | Lenguaje 6.5 | Se queda |
| 403 `sin-consentimiento` (al leer o guardar) | Pantalla entera con el texto de lenguaje 6.4 | Lenguaje 6.4, con el final «Pídele a quien administra el grupo que la registre.» para todos los roles (lenguaje 6.4, [PENDIENTE]) | Si estaba escribiendo, el texto se muestra arriba, seleccionable, con «Lo que escribiste sigue aquí. Cópialo si lo quieres guardar en otra parte.» **[PROPUESTO]** |
| 403 `revision-vencida` | Pantalla entera con el texto de lenguaje 6.4b | Lenguaje 6.4b exacto, con el enlace a ChileAtiende (`target="_blank"`, `rel="noopener noreferrer"`, ícono `ExternalLink` y «(se abre en ChileAtiende)» visible) | Igual que la fila anterior |
| 404 | Pantalla de 5.6 | Lenguaje 8, `no-encontrado` | — |
| 401 tras renovar | `/entrar` con el aviso de entrada vencida | 3.3 | Se pierde: se avisa antes (sección 5) |
| Red, 5xx, 503 | `Nota tono="pronto"` sobre los botones | Lenguaje 8, general | Se queda |

Las pantallas de lenguaje 6.4 y 6.4b usan `Nota` grande: `bg-atenta-fondo` con `border-l-4 border-atenta` y el ícono `ShieldAlert` (6.4b) o `ShieldQuestion` (6.4). No son errores en rojo: son avisos. Sin botón primario macizo; la navegación sigue disponible.

---

## 4. Componentes y sus estados

| Componente | De dónde | Estados que exige esta pantalla |
|---|---|---|
| `Boton` | `web/src/compartido/ui/Boton.tsx` (ya existe) | primario, secundario, texto; foco; presionado; `disabled`; ocupado (texto en gerundio, `aria-busy`) |
| `Marca` | `web/src/compartido/ui/Marca.tsx` | — |
| Distintivo del piloto | Sacar de `web/src/relevo/Marco.tsx` a `compartido/ui/` | Partido en dos líneas en angosto |
| `CampoTexto` | Copiar de `Demo/src/components/Ui.tsx` | normal, foco, error (borde `pronto` **y** el mensaje con `CircleAlert`), `disabled`, con ayuda. Borde `borde`, nunca `linea` |
| Área de texto de la ficha | Copiar de `Ficha.tsx` (`Completar`) | normal, foco, `readOnly` al guardar, contador cerca y en el tope |
| `GrupoOpciones` | `Ui.tsx` | normal, foco, elegido (borde `turquesa` + radio marcado), error |
| `Nota` | `Ui.tsx` | `rocio`, `atenta`, `pronto`, `ok`. Cada una con ícono propio, nunca solo el color |
| `MensajeError` | `Ui.tsx` | — |
| `Etiqueta` | `Ui.tsx` | `ok` (Listo), neutro (Falta) |
| `BarraCampos` | `Ui.tsx` | 0 a 3, siempre con el texto «`{n}` de 3 campos listos» al lado |
| `HojaFicha`, `TextoFicha` | `Demo/src/components/` | campo vacío «Sin completar»; línea de tiempo si empieza con hora |
| `Cuando` | `Ui.tsx` | — |
| `Volver` | `Shell.tsx` | 48 px (`min-h-12` en todos los tamaños, la demo usa `min-h-10` en ancho: **cambia**) |
| Navegación | `Shell.tsx` (`Navegacion`) | normal, foco, actual (`aria-current`), con pista |
| Selector | Nuevo, con `GrupoOpciones` | cerrado, abierto, foco |

Ningún componente escribe un color, un tamaño o una sombra a mano. Si falta algo, se pide un token.

---

## 5. Estados transversales

### 5.1 Cargando

En toda pantalla que pide datos: si tarda más de 400 ms, el texto «Cargando…» **[PROPUESTO]** en `text-tenue` con `role="status"` donde va a aparecer el contenido, sin girador ni bloques grises. Los botones que llaman a la API usan su texto en gerundio (3.2 a 3.8).

### 5.2 Error de red al cargar

`Nota tono="pronto"` con `WifiOff`, el texto general de lenguaje 8 sin la frase «Lo que escribiste sigue aquí» (no había nada escrito), y un `Boton variante="secundario"` «Volver a intentar» **[PROPUESTO]**. La navegación sigue visible.

### 5.3 Sin grupo

`GET /v1/grupos` devuelve `[]`: `/` lleva a `/empezar/grupo`. Cualquier sección (Ficha, Insumos, Compartir) también. No hay pantalla vacía intermedia.

### 5.4 Sin persona

Con grupo y sin personas:
- `admin` o `cuidador`: lleva a `/empezar/persona`.
- `pagador` u `observador`: no puede registrar. En `main`: «Todavía no hay nadie registrado en `{nombre del grupo}`. Quien administra el grupo puede registrar a la persona que cuidan.» **[PROPUESTO]**, en `Nota tono="rocio"` con `UserRound`. Sin botón.

### 5.5 Compartir, mientras MATU-48 no existe

`/compartir` muestra el título «Compartir» y «Pronto vas a poder compartir la ficha con quien te reemplace desde aquí.» **[PROPUESTO]**. Sin botón. Se quita cuando llega MATU-48.

### 5.6 Sin acceso a la ficha (404 de la ficha, o observador en `/ficha`)

Título «Ficha de relevo» y en `Nota tono="rocio"` con `Lock`: «No tienes acceso a la ficha de `{nombre}`. Si la necesitas, pídeselo a quien administra el grupo.» **[PROPUESTO]**. Es distinto del 404 general de lenguaje 8 porque aquí sí sabemos que la persona es del grupo: no revela nada de otro grupo.

### 5.7 Entrada que vence mientras escribe

Si renovar falla con texto sin guardar en el editor, antes de ir a `/entrar` la pantalla muestra el texto escrito, seleccionable, con «Tienes que volver a entrar. Copia lo que escribiste antes de seguir: no se guardó.» **[PROPUESTO]** y el botón «Entrar» (primario). Nunca se guarda el texto en el navegador para recuperarlo.

### 5.8 Roles, en resumen

| Rol | Ficha | Editar ficha | Insumos | Compartir | Registrar persona |
|---|---|---|---|---|---|
| `admin` | Sí | Sí | Sí | Sí | Sí |
| `cuidador` | Sí | Sí | Sí | Sí | Sí |
| `pagador` | Si la API responde (D3) | Si la API responde | Leer (MATU-36) | No | No |
| `observador` | **Nunca**, ni se pide | No | Leer (MATU-36) | No | No |

---

## 6. La entrada en el cliente (para el frontend)

No es diseño visual, pero define qué ve la persona, así que lo dejo escrito:

1. **El access token vive solo en memoria** (una variable del módulo del cliente HTTP). Nunca en `localStorage`, `sessionStorage`, `IndexedDB`, la URL ni una cookie legible.
2. **Al abrir o recargar:** `POST /v1/sesiones/renovar` con `X-MATU-Cliente: web` y `credentials: 'include'` (3.1).
3. **Ante un 401 `token-invalido` o `no-autenticado`** en cualquier ruta: renueva **una vez** y repite la petición. Si la renovación responde 401, va a `/entrar` con el aviso de entrada vencida (3.3, o 5.7 si hay texto sin guardar).
4. **Renovación serializada entre pestañas con `navigator.locks.request('matu-renovar', …)`** (decisión 51). Dentro del lock, antes de renovar, la pestaña revisa si otra ya obtuvo un token nuevo (por ejemplo con un `BroadcastChannel('matu-entrada')` que avisa "renovado", **sin el token en el mensaje**) y en ese caso vuelve a renovar ella con la cookie ya rotada. Nunca reintenta con la cookie anterior. Las peticiones que esperan el lock esperan, no fallan.
5. **Una sola renovación en vuelo por pestaña:** las peticiones que reciben 401 a la vez esperan la misma promesa.
6. **Salir** avisa a las otras pestañas por el mismo canal ("salió"), y todas van a `/entrar` con el aviso de 2.4.
7. **Nada de la ficha, del consentimiento ni de la persona en almacenamiento del navegador ni en la URL.** El correo escrito para "Entrar con ese correo" (3.2) pasa en memoria, no por la URL.

---

## 7. Tokens y capa base

No se crea ningún token. Con la autorización del 03-11 (D7) agregué a la capa base de `web/src/index.css`, dentro de `@layer base`, el mismo relleno de la demo para la barra fija del teléfono:

```css
@media (width < 40rem) {
  html { scroll-padding-bottom: 6rem; }
}
```

Con `angosto:` la barra no es fija; el relleno de más no molesta.

---

## 8. Textos que faltan en `lenguaje.md`

**[INSTRUCCIÓN]** (Jorge, 02-11, falta escribirlos): entrada vencida y 429 (3.3).
**Corrección de `lenguaje.md`** (D1): la hace el PR MATU #23.
**[PROPUESTO]:**

1. Etiquetas «Tu correo», «Tu celular» y su ayuda «Para ayudarte a recuperar tu cuenta si olvidas la contraseña.»; «¿Olvidaste tu contraseña?» (con MATU-57); dictado: «Detener», «No pudimos usar el micrófono. Puedes escribir el texto.»; «Mostrar» / «Ocultar»; ayuda «Así te verán en tu grupo.» (3.2)
2. Pasos «Tu cuenta · Tu grupo · A quién cuidas · La autorización» y «Paso `{n}` de 4» (3.2)
3. Validaciones de cuenta: «Escribe tu nombre.», «Revisa tu correo.», «La contraseña necesita entre 10 y 128 caracteres.», «Escribe tu nombre, de hasta 100 letras.» (3.2)
4. Entrar: «Escribe tu correo y tu contraseña.»; 401 «El correo o la contraseña no coinciden. Revísalos y vuelve a intentarlo.»; «Espera 1 minuto.»; 503 «MATU no está disponible en este momento. Vuelve a intentarlo en unos minutos.» (3.3)
5. Salir: «Saliste de MATU. Para volver, entra con tu correo y tu contraseña.» (2.4)
6. Grupo: «Ponle nombre a tu grupo», «Es el grupo de las personas que cuidan contigo.», «Nombre del grupo», «Crear el grupo», «Creando el grupo…», «Escribe un nombre para el grupo.» (3.4)
7. Persona: «Depto (si tiene)», «Elige cuánto apoyo necesita.» (3.5.1)
8. Autorización: «La autorización para guardar su ficha», la bajada, «Doy esta autorización porque…», «Elige en qué calidad das la autorización.», «Acepto y registro a `{nombre_pila}`», «Registrando a `{nombre_pila}`…», «Listo. Ahora, la ficha de `{nombre_pila}`.», «Volver a corregir los datos de `{nombre_pila}`» (3.5.2)
9. Ficha: «Volver a la ficha»; salir sin guardar: «Lo que escribiste en «`{campo}`» no se guardó. ¿Salir igual?», «Salir sin guardar», «Seguir escribiendo»; «Lo que escribiste sigue aquí. Cópialo si lo quieres guardar en otra parte.» (3.7, 3.9)
10. Transversales: «Abriendo MATU…», «Cargando…», «Volver a intentar», sin persona, Compartir pronto, sin acceso a la ficha, entrada vencida con texto sin guardar; «Le dicen `{nombre_pila}`» (2.3, 3.1, 5)

---

## 9. Cómo la voy a revisar

Con la app funcionando contra la API, y la cuenta sintética de Carmen (María, Rosa, Rodrigo):

- Capturas a 360, 1280 y 1920 px, tema claro y oscuro, y a 320 px con texto al 200%, de: crear cuenta (normal, 409, errores), entrar (vencida, 401, 429), grupo, persona, autorización (las tres calidades), ficha (0, 1 y 3 campos), editor (cerca del tope), conflicto 412, 6.4 y 6.4b, y el esqueleto con el selector abierto.
- **Criterios verificables:**
  1. En cada pantalla hay **un solo** elemento en `turquesa` macizo (el botón principal), salvo la ficha completa, que no tiene ninguno.
  2. El distintivo del piloto se ve completo en todas las pantallas, sin abreviar, también a 320 px con texto al 200%.
  3. Sin desplazamiento horizontal a 320 px con texto al 200%; la barra de secciones deja de ser fija en `angosto`.
  4. Todo lo que se toca mide al menos 48 × 48 px (navegación, `Volver`, «Salir», radios, casilla del aviso, «Mostrar»).
  5. Listo/Falta, el estado activo de la navegación, el aviso del cuidador y los errores se distinguen en escala de grises.
  6. El foco se ve en todo, con el anillo de 3 px `turquesa`, y nunca queda tapado por la barra del teléfono.
  7. Ningún texto dice «sesión», «email», «token», «permiso» donde la política dice «autorización», ni un término clínico.
  8. La URL nunca contiene un nombre, un id de persona ni texto de la ficha; el almacenamiento del navegador queda vacío después de usar la app.
  9. De la cuenta creada a la ficha completa, cronometrado con los ejemplos sintéticos: menos de 3 minutos.

# MATU-23 · Página web del relevo · Especificación de diseño

**Versión 1.0 · 28/10/2026** · agente 6 (UI/UX) · para el frontend, antes de construir
**Historia:** "Como persona que reemplaza a la cuidadora, quiero leer la ficha desde el celular sin instalar nada, para saber qué hacer desde el primer minuto". RF-06.
**Dónde se construye:** `web/`, con React 19, TypeScript, Vite y Tailwind CSS v4 (decisión de Martín del 28/10, ADR-026). Es la primera ruta del cliente web: `/r`.

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `Demo/src/index.css` · prototipo v1.1 (pantallas `f1-7` y `f6-4`) · `docs/lenguaje.md` del repositorio MATU (secciones 4, 5, 7, 8 y 11) · checklist de accesibilidad de `docs/estrategia-pruebas.md`, sección 7 · contrato `docs/api/propuestos/relevo.openapi.yaml`. La demo (`Demo/src/relevo/Relevo.tsx`, `components/HojaFicha.tsx`, `components/TextoFicha.tsx` y `components/Ui.tsx`) es la referencia visual aprobada: esta especificación dice dónde se parece y dónde cambia.

**Cómo se lee:** los textos entre comillas latinas «» van tal cual. Los marcados **[PROPUESTO]** no están en `lenguaje.md`: el orquestador los lleva a Jorge y entran a `lenguaje.md` en el mismo pull request (lenguaje, sección 12). Hasta entonces no se usan otros. Las llaves son los datos de la API: `{nombre_comparte}` = `nombre_pila_comparte`, `{nombre_pila}` = `nombre_pila`.

---

## 0. Lo que tiene que decidir alguien más

No lo decido yo. Va al orquestador antes de construir:

| # | Qué | Por qué importa | Lo que hace la especificación mientras tanto |
|---|---|---|---|
| D1 | **El backlog dice otra cosa.** MATU-23 dice "HTML y JavaScript sin framework en `web/relevo/`". La decisión de Martín del 28/10 dice React en `web/` | Contradicción entre un documento de `docs/` y una instrucción. El backlog se corrige | Sigue la decisión del 28/10 y el ADR-026 |
| D2 | **Los ejemplos de la ficha en la página del relevo.** El criterio de Jorge del 28/10 pide mostrar la pregunta guía y el ejemplo de cada campo (lenguaje 5.1 a 5.3). Pero esos textos están escritos para quien **escribe** la ficha, no para quien la lee: | **Riesgo P1 de seguridad.** Con «A quién llamar» sin completar, Rosa ve "Rodrigo, su hijo: +56 9 5555 0102" y en un apuro puede llamar a un número de ejemplo | Muestra la pregunta y el ejemplo tal cual, con la mitigación de la sección 3.9. **Recomiendo** que en el relevo se muestre solo la pregunta guía y no el ejemplo. Lo decide Jorge |
| | · el ejemplo de «A quién llamar» trae un teléfono que parece real | | |
| | · el ejemplo de «Su día» termina en "Si empiezas con la hora, lo mostramos como línea de tiempo", que le habla a Carmen | | |
| | · "¿A quién llamar si algo pasa y no te ubican?" dice "te": a Rosa nadie la busca | | |
| D3 | **Autorización vencida en el relevo.** Lenguaje 6.4b dice que con la autorización por renovar "un relevo con un enlace anterior tampoco abre la ficha". El contrato del relevo no tiene un 403 en `/presentacion`, `/canje` ni `/ficha`, y `lenguaje.md` no tiene texto para Rosa en ese caso | Si la API responde un 403 al relevo, la página no sabe qué decir | Un `type` no previsto cae en el error general (sección 3.12). Falta: el código de respuesta en el contrato y el texto para Rosa en lenguaje 7.3. Propuesta: usar el estado "Este enlace no está disponible", porque para Rosa el efecto es el mismo y no conviene contarle a un tercero que falta una autorización |
| D4 | **El aviso 7.5 tiene un hueco.** El texto final trae "[PENDIENTE: correo de contacto]" | No se puede mostrar un texto con un marcador | Usa la variante sin el correo, la misma de la demo (lenguaje 7.5, "En la demo"), hasta la política 1.0 |
| D5 | **La política de privacidad no tiene ruta en `web/`** | El aviso enlaza a ella | El enlace apunta a la ruta que fije el orquestador. Si no existe al construir, el enlace no se pone y se anota como pendiente. Nunca un `href="#"` |
| D6 | **Las cabeceras de la página.** El contrato pone `no-store`, `no-referrer` y `noindex` en las respuestas de `/v1/relevo/`. El HTML de `/r` lo sirve la API con `StaticFiles` y el contrato no lo cubre | Con `no-store` en el HTML, el navegador no guarda la ficha en la caché de ida y vuelta, y al tocar "Atrás" después de salir no reaparece | Recomiendo las tres cabeceras también en la respuesta de `/r` (lo hace el backend). La página suma las etiquetas `meta` equivalentes (sección 6) |
| D7 | **Textos que faltan en `lenguaje.md`** | El frontend no inventa textos | Lista completa en la sección 7 |

---

## 1. Para quién y qué

**Rosa** reemplaza a Carmen el sábado. Recibió un enlace por WhatsApp y Carmen le dictó un PIN por teléfono. No tiene cuenta, no conoce MATU y abre la página en su celular, tal vez sin anteojos, en una casa ajena y con apuro. Tiene que entender en una lectura quién le manda esto, escribir cuatro números y leer qué hacer con María.

**La página** es una sola ruta, `/r`, sin navegación, sin cuenta y sin nada que no sea la ficha. Tiene tres momentos: **quién te la mandó y el PIN**, **la ficha** y, si el enlace ya no sirve, **qué pasó y qué hacer**.

**Lo que la hace MATU:** la hoja del refrigerador, con su imán de miel, es lo único con presencia (DISENO.md, principio 1). La misma hoja que Carmen ve al escribir es la que Rosa lee.

---

## 2. Marco común a todas las pantallas

### 2.1 Estructura

```
<div id="raiz">                         contenedor `app` (capa base, sección 6)
  <header>                              marca, nombre de la página y distintivo del piloto
  <main id="contenido" tabIndex={-1}>   contenedor `main`
    la pantalla del momento
  </main>
</div>
```

- **Cabecera** (`header`): fondo `hoja`, borde inferior `linea` (`border-b border-linea bg-hoja`). Adentro, una fila centrada de ancho máximo `max-w-6xl` con `flex flex-wrap items-center gap-x-4 gap-y-2 px-4 angosto:px-2 @3xl/app:px-10 py-3`:
  1. **Marca:** el logo (círculo `marca` con el `Heart` de lucide relleno en blanco, `size-8`, `aria-hidden`) y «MATU» en `titular text-xl`.
  2. **Nombre de la página:** «Ficha de cuidado compartida» en `text-tenue`. Juntos dicen «MATU · Ficha de cuidado compartida» (lenguaje 7.1). El punto medio no se escribe: lo da el espacio entre los dos.
  3. **Distintivo del piloto**, con `ms-auto` para ir a la derecha cuando cabe (sección 2.2).
- La cabecera **no es fija** (`sticky` ni `fixed`). Con el texto al 200% en 320 px, algo fijo se come media pantalla y tapa el foco (WCAG 1.4.10 y 2.4.11).
- **`main`:** `@container/main px-4 angosto:px-2 @3xl/app:px-10 pt-6 @3xl/app:pt-14 pb-16 outline-none`.
- **Sin pie de página.** Nada de enlaces a "Inicio", "Crear cuenta" ni "Conoce MATU".

### 2.2 Distintivo del piloto (lenguaje 11)

- Texto: «**Piloto académico con datos de prueba**». No se abrevia.
- Píldora `rounded-full bg-tinta/7 px-3 py-1 text-base font-bold text-tenue` (6,3:1 sobre `hoja` claro, 6,7:1 oscuro), con un punto `miel` delante (`size-2.5 rounded-full bg-miel`, `aria-hidden`).
- **Se parte en dos renglones por la frase, nunca por la mitad de una palabra:** dos `span` con `inline-block`, «Piloto académico» y «con datos de prueba», separados por un espacio. Si no caben juntos, el segundo baja.
- Va en la cabecera de **todas** las pantallas, incluidas "cargando" y los errores. Ningún estado, ancho ni zoom lo oculta.
- No es interactivo: no recibe foco ni tiene `title`.

### 2.3 Patrón "una sola columna centrada"

Lo usan la pantalla del PIN, "cargando" y los estados en que el enlace no abre:

- Columna `mx-auto flex max-w-xl flex-col items-center gap-6 text-center`.
- **Ícono del momento** en una baldosa `grid place-items-center rounded-2xl`, `size-14 @md/main:size-18`, con el ícono `size-8 @md/main:size-10` y `aria-hidden`.
- **Título** `h1` con `id="titulo-pagina" tabIndex={-1}`, `titular text-3xl @2xl/main:text-5xl angosto:text-2xl outline-none`.
- **Texto** en `text-lg text-tenue` (19 px), `max-w-md`.
- Lo que tiene varios renglones de lectura (el aviso, la nota "¿Qué hago?") va **alineado a la izquierda** dentro de la columna centrada (`w-full text-start`). Tres párrafos centrados no se leen.

Se centra porque es un único objeto en la página, igual que el PIN de la demo (DISENO.md, sección 3, "Alineación").

### 2.4 Foco y movimiento

- **Foco base** de la capa base: contorno de 3 px en `turquesa` con 2 px de separación. 6,0:1 sobre `papel` y 6,7:1 sobre `hoja` en claro, 9,3:1 y 8,2:1 en oscuro. Ningún componente lo quita.
- **Al cambiar de momento** (presentación → PIN → ficha → estado), el foco va al `h1` de la pantalla nueva (`titulo-pagina`). Así el lector de pantalla anuncia el título de cada estado al cargar (lenguaje 7.3, última nota).
- **Sin transiciones entre pantallas.** El cambio es inmediato (DISENO.md, sección 5: las páginas no entran deslizándose). La única animación permitida es `aparecer` (fundido de 180 ms) en el mensaje de confirmación de "Actualizar". Con `prefers-reduced-motion` es inmediato.

### 2.5 Título del documento (`<title>`)

El título queda en el historial del navegador y en la lista de pestañas, así que **nunca lleva un nombre**:

| Momento | `<title>` [PROPUESTO] |
|---|---|
| Cargando, PIN y ficha | Ficha de cuidado compartida · MATU |
| Un estado que no abre | `{título del estado}` · MATU (por ejemplo, "Este enlace venció · MATU") |

---

## 3. Pantallas y estados

### 3.0 Cómo se llega a cada uno

```
abre /r#<token> ─► ¿hay token en el fragmento?
                    ├─ sí ─► POST /presentacion ─► 200 ─► PIN (3.2)
                    │                            ├─ 410 / 423 / 429 / 422 ─► estado (3.5 a 3.10)
                    │                            └─ red o 5xx ─► error general (3.12)
                    └─ no (recargó después de entrar) ─► GET /ficha ─► 200 ─► ficha (3.11)
                                                                  └─ 401 ─► "Vuelve a abrir el enlace" (3.9)
PIN ─► POST /canje ─► 204 ─► replaceState a /r ─► GET /ficha ─► ficha
                    ├─ 401 pin-incorrecto ─► PIN con mensaje (3.3)
                    ├─ 422 ─► PIN con mensaje (3.3)
                    └─ 410 / 423 / 429 ─► estado
ficha ─► Actualizar ─► GET /ficha ─► 200 (sigue) · 401 / 410 / 423 ─► estado (la ficha se borra)
```

Un 422 de `/presentacion` (token vacío o de más de 128 caracteres) se muestra como "no disponible" (3.8): para Rosa es un enlace copiado mal. La página elige el texto **solo por `type`** y nunca muestra `title`, `detail`, `mensaje`, `status` ni `request_id` (lenguaje 8).

---

### 3.1 Cargando

**Objetivo:** Rosa sabe que la página está trabajando y que llegó a MATU.

**Jerarquía:** 1) la cabecera con la marca y el distintivo, que se pinta de inmediato · 2) una línea de texto.

**Esquema a 360 px y en pantalla ancha** (igual, centrado):

```
┌────────────────────────────────────┐
│ (♥) MATU  Ficha de cuidado         │
│ compartida                          │
│ (●) Piloto académico                │
│     con datos de prueba             │
├────────────────────────────────────┤
│                                    │
│        Abriendo el enlace…         │
│                                    │
└────────────────────────────────────┘
```

- **Sin esqueleto, sin ícono girando y sin baldosa.** Solo el texto, en `text-lg text-tenue`, dentro de un `p` con `role="status"`. El `main` lleva `aria-busy="true"`.
- **Aparece recién a los 400 ms.** Si la respuesta llega antes, Rosa no ve un parpadeo.
- Textos [PROPUESTO]: «Abriendo el enlace…» mientras se pide la presentación. «Abriendo la ficha…» mientras se pide la ficha.
- **Criterio:** la cabecera y el distintivo están en el HTML inicial o se pintan en el primer render, antes de cualquier respuesta de la API.

---

### 3.2 Quién te la mandó y el PIN

**Objetivo:** Rosa sabe que es Carmen quien le comparte la ficha de María y escribe el PIN que le dictaron, sin cuenta y sin instalar nada.

**Jerarquía:**
1. El título «Carmen te compartió la ficha de María» y el campo del PIN.
2. «Ver la ficha», el **único** elemento en `turquesa` macizo de la pantalla, y el pie «No necesitas cuenta…».
3. El aviso «Tus datos en MATU», debajo y separado por una línea.

**Esquema a 360 px:**

```
┌────────────────────────────────────┐
│ (♥) MATU  Ficha de cuidado         │
│ compartida                          │
│ (●) Piloto académico                │
│     con datos de prueba             │
├────────────────────────────────────┤
│              ┌────┐                │
│              │llave│               │  baldosa rocio, size-14
│              └────┘                │
│     Carmen te compartió la         │  h1 titular text-3xl
│        ficha de María              │
│  Escribe el PIN de cuatro números  │  text-lg tenue
│  que te dictaron por teléfono.     │
│                PIN                 │  label, font-bold
│          ┌──────────────┐          │
│          │   4 8 2 1    │          │  digitos text-5xl, min-h-18
│          └──────────────┘          │
│          [ Ver la ficha ]          │  único turquesa macizo
│  No necesitas cuenta ni instalar   │  text-base tenue
│  nada. Al entrar, el enlace se     │
│  borra de la barra de direcciones. │
│ ────────────────────────────────── │  border-t linea
│ (escudo) Tus datos en MATU         │  h2 text-base bold, a la izquierda
│ MATU guarda tu nombre y tu         │  text-base tenue leading-relaxed
│ teléfono, que anotó quien te …     │
│ (hoja) Política de privacidad      │  enlace, min-h-12
└────────────────────────────────────┘
```

**Pantalla ancha (1280 y 1920 px):** la misma columna centrada de `max-w-xl`, con la baldosa en `size-18`, el título en `text-5xl` y `pt-14` arriba. No se agrega una segunda columna ni una ilustración: el espacio vacío a los lados es intencional.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ (♥) MATU   Ficha de cuidado compartida        (●) Piloto académico con datos de prueba │
├──────────────────────────────────────────────────────────────────────────────┤
│                               ┌──────┐                                        │
│                               │ llave│                                        │
│                               └──────┘                                        │
│                  Carmen te compartió la ficha de María                        │
│            Escribe el PIN de cuatro números que te dictaron por teléfono.     │
│                                  PIN                                          │
│                            [   4 8 2 1   ]                                    │
│                            [ Ver la ficha ]                                   │
│             No necesitas cuenta ni instalar nada. Al entrar, …                │
│             ───────────────────────────────────────                           │
│             (escudo) Tus datos en MATU                                        │
│             MATU guarda tu nombre y tu teléfono, …                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Componentes y tokens:**

| Pieza | Construcción |
|---|---|
| Baldosa | `bg-rocio text-turquesa`, ícono `KeyRound` de lucide. Decorativa: el turquesa aquí no dice un estado |
| Título | Patrón 2.3 |
| Bajada | `p` con `id="pin-bajada"`, `text-lg text-tenue max-w-md` |
| Formulario | `form` con `noValidate`, `flex w-full flex-col items-center gap-3`. Enviar con Enter funciona |
| Etiqueta | `label htmlFor="pin"`, `font-bold`, texto «PIN» |
| Campo del PIN | Un solo `input`, como en la demo, no cuatro casillas: `id="pin"`, `type="text"`, `inputMode="numeric"`, `autoComplete="one-time-code"`, `enterKeyHint="go"`, `maxLength={4}`, `aria-describedby="pin-bajada"` (más `pin-mensaje` si hay mensaje). Clases: `digitos min-h-18 w-full max-w-60 rounded-xl bg-hoja text-center text-5xl angosto:text-3xl font-bold tracking-widest ring-2 ring-inset ring-borde focus-visible:ring-turquesa`. Al escribir, se quita todo lo que no es dígito (así se puede pegar "4 8 2 1") y se corta en 4. **No se enmascara**: Rosa compara lo que escribió con lo que le dictaron |
| Botón principal | «Ver la ficha». `type="submit"`, botón principal (sección 5). **Nunca deshabilitado**: la validación ocurre al enviar |
| Pie | `p`, `text-base text-tenue max-w-md`, texto de lenguaje 7.1 |
| Aviso | Sección 3.2.1 |

**Orden del foco:** campo del PIN → «Ver la ficha» → «Política de privacidad». La cabecera no tiene nada que reciba foco.

**Al cargar,** el foco va al `h1` (2.4), no al campo: en el teléfono, el teclado numérico taparía el título y Rosa no sabría quién le escribe. Un toque en el campo abre el teclado numérico.

**Mientras se canjea** (POST `/canje` en curso): el botón conserva su ancho, lleva `aria-busy="true"` y dice «Abriendo la ficha…» [PROPUESTO]. Un segundo toque no envía otra vez. El campo no se borra.

**Textos exactos** (lenguaje 7.1):

| Parte | Texto |
|---|---|
| Título | «`{nombre_comparte}` te compartió la ficha de `{nombre_pila}`» |
| Bajada | «Escribe el PIN de cuatro números que te dictaron por teléfono.» |
| Etiqueta | «PIN» |
| Botón | «Ver la ficha» |
| Pie | «No necesitas cuenta ni instalar nada. Al entrar, el enlace se borra de la barra de direcciones.» |

#### 3.2.1 Aviso «Tus datos en MATU» (lenguaje 7.5)

- `section` con `aria-labelledby="aviso-datos-t"`, después del pie: `flex w-full max-w-md flex-col gap-3 border-t border-linea pt-5 text-start`.
- Título `h2` con `id="aviso-datos-t"`: `flex items-center gap-2 text-base font-bold`, con el ícono `ShieldCheck` (`size-5 shrink-0 text-turquesa`, `aria-hidden`). Texto «Tus datos en MATU» [PROPUESTO para lenguaje 7.5: la demo lo usa y la ESPEC-ADR-027, 6.4, lo dejó como propuesta].
- **El texto aprobado, sin cambiar una palabra, en tres párrafos** (`text-base text-tenue leading-relaxed`; nunca `text-sm`). El corte es solo de presentación:
  1. «MATU guarda tu nombre y tu teléfono, que anotó quien te compartió la ficha, para enviarte el enlace y poder contactarte. Tu teléfono se borra 30 días después de que el enlace vence o se corta.»
  2. «También registra cada vez que abres el enlace o la ficha y cada PIN incorrecto, y guarda ese registro 3 años, para saber a quién se compartió.»
  3. «Responsables de tus datos: Jorge Espinoza y Martín Henríquez. Puedes pedir ver, corregir o borrar tus datos.» Esta es la variante sin el correo (D4). Cuando la política 1.0 fije el correo, el párrafo 3 pasa a: «Responsables de tus datos: Jorge Espinoza y Martín Henríquez. Puedes pedir ver, corregir o borrar tus datos escribiendo a `{correo}`.», con el correo como enlace `mailto:`.
- **«Política de privacidad»:** un `<a>` de verdad (no un botón), en su propio renglón, `inline-flex min-h-12 items-center gap-2 self-start font-bold text-turquesa underline underline-offset-4 decoration-turquesa/40 hover:decoration-turquesa`, con el ícono `FileText` (`size-5`, `aria-hidden`). Se abre en otra pestaña (`target="_blank" rel="noopener noreferrer"`) para que Rosa no pierda la página del PIN, y lo dice en el texto visible: «Política de privacidad (se abre en otra pestaña)» [PROPUESTO, mismo patrón que lenguaje 6.4b]. Ruta: D5.
- **Sin acordeón** ni "Ver más". Es lo que Rosa tiene que poder leer antes de entrar.
- **Aparece igual** en todos los estados de esta pantalla: normal, canjeando, PIN incompleto, PIN incorrecto y error de conexión. **No aparece** en "cargando", en los estados que no abren ni en la ficha.

**Criterios verificables de 3.2:**
- «Ver la ficha» es el **único** elemento en `turquesa` macizo de la pantalla.
- A 360 × 740 px, sin texto al 200%, el título, el campo del PIN y «Ver la ficha» se ven sin desplazar. A 1280 × 720 también. El aviso puede quedar más abajo.
- El texto del aviso, sin contar los cortes de párrafo, es idéntico al de lenguaje 7.5 en su variante sin correo.
- Ningún texto de la pantalla está bajo 1 rem (17 px). La pantalla no usa `text-sm`.
- El campo del PIN mide al menos 48 px de alto (mide `min-h-18`, 76,5 px). El botón y el enlace de la política, `min-h-12` (51 px).

---

### 3.3 PIN incompleto, PIN incorrecto y error al canjear

**Objetivo:** Rosa entiende qué pasó con el PIN y cuántas veces más puede probar, sin sentir que hizo algo mal.

Es la misma pantalla 3.2, con un **mensaje bajo el campo**, entre el campo y «Ver la ficha». No cambia el título ni se mueve nada de lo de arriba.

**Esquema a 360 px** (la zona que cambia):

```
│                PIN                 │
│          ┌──────────────┐          │  anillo pronto, dígitos en pronto
│          │   4 8 1 2    │          │
│          └──────────────┘          │
│  Ese PIN no es. Revisa los cuatro  │  «Ese PIN no es.» en negrita pronto
│  números que te dictaron. Te       │  el resto en tinta
│  quedan 3 intentos. Después, el    │
│  enlace se bloquea.                │
│          [ Ver la ficha ]          │
```

**Construcción del mensaje:**
- `p` con `id="pin-mensaje"`, `role="alert"`, `max-w-md text-base`. El campo suma `aria-invalid="true"` y `aria-describedby="pin-bajada pin-mensaje"`.
- **El foco se queda en el campo** (lenguaje 7.3, última nota). Después de un PIN incorrecto, los cuatro dígitos quedan escritos y seleccionados: Rosa los compara con lo que le dictaron y, si escribe, los reemplaza.
- **La baldosa** pasa a `bg-pronto-fondo text-pronto` con el mismo ícono `KeyRound`. El campo pasa a `ring-pronto text-pronto`. **El estado no se dice solo con color:** lo dicen las palabras «Ese PIN no es.» y el conteo de intentos.
- Contraste: `pronto` sobre `papel` 6,3:1 en claro y 9,5:1 en oscuro. Sobre `hoja`, 7,1:1 y 8,3:1.

| Caso | `type` y status | Texto exacto (lenguaje 7.3 y 8) | Estilo |
|---|---|---|---|
| Menos de 4 números | Se valida **antes** de enviar. Si la API responde `/errores/validacion` 422 con `errores[].campo = pin`, el mismo | «El PIN tiene 4 números. Revisa que estén todos.» | Todo en `font-bold text-pronto` |
| Incorrecto, quedan 2 a 4 | `/errores/pin-incorrecto` 401, `intentos_restantes` ≥ 2 | «**Ese PIN no es.** Revisa los cuatro números que te dictaron. Te quedan `{intentos_restantes}` intentos. Después, el enlace se bloquea.» | «Ese PIN no es.» en `font-bold text-pronto`. El resto en `text-tinta`, con «`{n}` intentos» en `font-bold` |
| Incorrecto, queda 1 | `/errores/pin-incorrecto` 401, `intentos_restantes` = 1 | «**Ese PIN no es.** Revisa los cuatro números que te dictaron. Te queda 1 intento. Después, el enlace se bloquea.» | Igual, con «1 intento» en `font-bold` |
| Sin conexión o 5xx al canjear | Red caída o 5xx | «**No pudimos completar esto.** Revisa tu conexión y vuelve a intentarlo. Lo que escribiste sigue aquí.» (lenguaje 8, "Cualquier otro") | Primera frase en `font-bold`, todo en `text-tinta`, con el ícono `CircleAlert` (`size-5 text-tenue`, `aria-hidden`) delante. **No** en `pronto`: Rosa no hizo nada mal y no se perdió nada. El campo **no** lleva `aria-invalid` y conserva el PIN. «Ver la ficha» sirve para reintentar |

- El quinto PIN incorrecto responde 423 y lleva a 3.5, no a este mensaje.
- **No se muestra el conteo de intentos antes del primer error.** Asustar a Rosa antes de que se equivoque no ayuda.

---

### 3.4 Patrón de los estados en que el enlace no abre

Bloqueado, vencido, cortado y no disponible usan la misma pantalla. Cambian el ícono, el título y el texto.

**Objetivo:** Rosa entiende que el enlace ya no sirve, que no es culpa suya y qué hacer: pedir otro.

**Jerarquía:**
1. El título, que dice qué pasó.
2. Una frase que dice por qué.
3. La nota «¿Qué hago?» con la acción.

**Esquema a 360 px:**

```
┌────────────────────────────────────┐
│ (♥) MATU  Ficha de cuidado         │
│ compartida                          │
│ (●) Piloto académico                │
│     con datos de prueba             │
├────────────────────────────────────┤
│              ┌────┐                │
│              │reloj│               │  baldosa neutra: bg-tinta/7 text-tenue
│              └────┘                │
│        Este enlace venció          │  h1 titular text-3xl
│  Los enlaces de MATU duran un      │  text-lg tenue
│  tiempo fijo, y el de esta ficha   │
│  ya terminó.                       │
│ ┌────────────────────────────────┐ │  Nota, fondo rocio, a la izquierda
│ │ ¿Qué hago?                     │ │
│ │ Pídele a quien te envió el     │ │
│ │ enlace uno nuevo.              │ │
│ └────────────────────────────────┘ │
└────────────────────────────────────┘
```

**Pantalla ancha:** la misma columna de `max-w-xl`, con el título en `text-5xl` y la baldosa en `size-18`.

**Componentes y tokens:**
- **Baldosa neutra** `bg-tinta/7 text-tenue` (`tenue` sobre ese fondo mide 5,6:1 en claro y 7,8:1 en oscuro). **No** en `pronto`: Rosa no perdió nada ni hizo nada mal (DISENO.md, sección 6, "Página": `pronto` solo si se perdió algo). Tampoco en `turquesa`, que nunca dice un estado.
- **Nota «¿Qué hago?»** (lenguaje 7.2): `w-full text-start rounded-xl bg-rocio px-4 py-3`. Título «¿Qué hago?» en `font-bold`, y la acción en `text-base font-bold`: «**Pídele a quien te envió el enlace uno nuevo.**». `tinta` sobre `rocio` mide 13,2:1 en claro y 10,6:1 en oscuro.
- **Sin botones.** No hay nada que Rosa pueda tocar que arregle el enlace, y un botón que no hace nada es peor que ninguno. Por eso **esta pantalla no tiene un elemento en `turquesa` macizo**.
- **Sin el aviso 7.5** ni el pie del PIN.
- **La ficha no está en el DOM ni en memoria.** Si se llegó aquí desde la ficha (por "Actualizar" o al vencer), el texto de los campos se descarta antes de pintar el estado.

### 3.5 Bloqueado

| | |
|---|---|
| Cuándo | `/errores/relevo-bloqueado` 423, desde `/presentacion`, `/canje` (incluido el quinto PIN incorrecto) o `/ficha` |
| Ícono | `Lock` |
| Título | «Este enlace se bloqueó» |
| Texto | «El PIN se escribió mal cinco veces. Por seguridad, el enlace ya no abre.» |
| Nota | «¿Qué hago?» · «Pídele a quien te envió el enlace uno nuevo.» |

### 3.6 Vencido

| | |
|---|---|
| Cuándo | `/errores/relevo-vencido` 410 |
| Ícono | `Clock3` |
| Título | «Este enlace venció» |
| Texto | «Los enlaces de MATU duran un tiempo fijo, y el de esta ficha ya terminó.» |
| Nota | «¿Qué hago?» · «Pídele a quien te envió el enlace uno nuevo.» |

### 3.7 Cortado

| | |
|---|---|
| Cuándo | `/errores/relevo-revocado` 410 |
| Ícono | `Unlink` |
| Título | «Este enlace se cortó» |
| Texto | «Quien te compartió la ficha cortó el enlace, y ya no abre.» |
| Nota | «¿Qué hago?» · «Pídele a quien te envió el enlace uno nuevo.» |

### 3.8 No disponible

| | |
|---|---|
| Cuándo | `/errores/relevo-no-disponible` 410, o un 422 de `/presentacion` (3.0) |
| Ícono | `Link2Off` |
| Título | «Este enlace no está disponible» |
| Texto | «Puede que se haya copiado incompleto o que ya no exista. Revisa que lo abriste completo desde el mensaje.» |
| Nota | «¿Qué hago?» · «Pídele a quien te envió el enlace uno nuevo.» |

### 3.9 Sin sesión: «Vuelve a abrir el enlace»

**Objetivo:** Rosa sabe que la ficha se cerró por tiempo y que **su mismo enlace sigue sirviendo**.

| | |
|---|---|
| Cuándo | `/errores/sin-sesion-relevo` 401 en `/ficha`: al recargar sin cookie, al tocar "Actualizar" con la sesión vencida (12 horas) o al volver a la página otro día |
| Ícono | `KeyRound` (el mismo del PIN: lo que sigue es escribirlo otra vez) |
| Título | «Vuelve a abrir el enlace» |
| Texto | «Por seguridad, la ficha se cierra después de un rato. Abre de nuevo el enlace que te enviaron y escribe el PIN.» |
| Nota | **Ninguna.** No lleva «¿Qué hago?» ni «Pídele…»: el enlace sigue sirviendo (lenguaje 7.3) |

Mismo patrón 3.4, sin la nota. Sin botones: después del canje el token ya no está en la dirección, así que la página no puede volver a pedir el PIN por su cuenta. Rosa vuelve al mensaje de WhatsApp. El texto lo dice.

### 3.10 Demasiados intentos desde la conexión

| | |
|---|---|
| Cuándo | `/errores/demasiadas-peticiones` 429, en `/presentacion` o en `/canje` |
| Ícono | `Hourglass` |
| Título | «Espera un momento» |
| Texto | «Hubo muchos intentos de entrar desde esta conexión. Vuelve a intentarlo en `{minutos}` minutos.» |
| Nota | **Ninguna.** El enlace sigue sirviendo |

- `{minutos}` = la cabecera `Retry-After` (segundos) dividida por 60 y **redondeada hacia arriba**, mínimo 1.
- Con 1 minuto, «1 minutos» está mal. [PROPUESTO para lenguaje 7.3]: «Vuelve a intentarlo en 1 minuto.»
- Si falta la cabecera, [PROPUESTO]: «Vuelve a intentarlo en unos minutos.»
- Sin cuenta regresiva animada ni botón. Cuando pase el tiempo, Rosa vuelve a abrir el enlace: como el canje no ocurrió, el token sigue en el mensaje.

---

### 3.11 La ficha abierta

**Objetivo:** Rosa lee, desde el primer minuto, cómo es el día de María, qué la calma y a quién llamar, y sabe hasta cuándo puede verlo.

**Jerarquía:**
1. **La hoja:** «Ficha de cuidado de» y el nombre, y los campos compartidos.
2. **Hasta cuándo** puede verla.
3. «Actualizar» y «Solo Carmen puede cambiar esta ficha».

**Esquema a 360 px:** la columna de datos va **arriba** y es corta (tres renglones y un botón), como en la demo aprobada. Así Rosa sabe desde el principio que la ficha vence.

```
┌────────────────────────────────────┐
│ (♥) MATU  Ficha de cuidado         │
│ compartida                          │
│ (●) Piloto académico                │
│     con datos de prueba             │
├────────────────────────────────────┤
│ (reloj) Puedes verla hasta el      │  text-base tinta, fecha y hora en bold cifras
│ 31/10/2026 a las 23:00.            │
│ [(↻) Actualizar]                   │  botón secundario
│ Solo Carmen puede cambiar esta     │  text-base tenue
│ ficha.                             │
│               (imán)               │  miel
│ ┌────────────────────────────────┐ │  la hoja: bg-hoja shadow-xl
│ │ Ficha de cuidado de            │ │  text-lg tenue
│ │ María                          │ │  h1 titular text-5xl
│ │ ══════════════════════════════ │ │  border-b-2 tinta
│ │ Su día                         │ │  h2 text-xl bold turquesa
│ │ ¿Cómo es un día normal para    │ │  pregunta guía, text-base tenue
│ │ María? Puedes contar un día    │ │
│ │ bueno o uno difícil.           │ │
│ │ 08:00 ● Se levanta y toma      │ │  línea de tiempo, text-lg
│ │         desayuno en la cocina  │ │
│ │ 13:00 ● Almuerza               │ │
│ │ │ Por ejemplo: «08:00 Despierta│ │  ejemplo, text-base tenue, borde izq.
│ │ │ …»                           │ │
│ │                                │ │
│ │ Si se altera                   │ │
│ │ ¿Qué calma a María cuando se   │ │
│ │ angustia?                      │ │
│ │ (◌ Sin completar)              │ │  etiqueta neutra
│ │ │ Por ejemplo: «Le hace bien…» │ │
│ └────────────────────────────────┘ │
└────────────────────────────────────┘
```

**Pantalla ancha** (desde 56 rem de ancho de `main`): dos columnas, la hoja a la izquierda y los datos a la derecha, en una columna fija de 17 rem que se queda quieta al desplazar (es la medida fija de DISENO.md, sección 3).

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ (♥) MATU   Ficha de cuidado compartida            (●) Piloto académico con datos de prueba │
├──────────────────────────────────────────────────────────────────────────────────┤
│        ┌──────────────(imán)──────────────────────┐   (reloj) Puedes verla hasta  │
│        │ Ficha de cuidado de                      │   el 31/10/2026 a las 23:00.  │
│        │ María                                    │   [(↻) Actualizar]            │
│        │ ════════════════════════════════════════ │   Solo Carmen puede cambiar   │
│        │ Su día                                   │   esta ficha.                 │
│        │ ¿Cómo es un día normal para María? …     │                               │
│        │ 08:00 ● Se levanta y toma desayuno…      │                               │
│        │ 13:00 ● Almuerza                         │                               │
│        │ │ Por ejemplo: «08:00 Despierta…»        │                               │
│        │ Si se altera                             │                               │
│        │ …                                        │                               │
│        └──────────────────────────────────────────┘                               │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**Composición:**
- Grilla `mx-auto grid max-w-6xl grid-cols-1 items-start gap-8 @4xl/main:grid-cols-[minmax(0,1fr)_17rem]`. La pista de la hoja es `minmax(0,1fr)`, nunca `auto`: una pista `auto` no baja del ancho de su contenido y desborda a 320 px (ESPEC-ADR-027, 7.3, R1).
- **Columna de datos** (`aside aria-label="Sobre esta ficha"` [PROPUESTO]): `order-first flex flex-col gap-4 @4xl/main:order-none @4xl/main:sticky @4xl/main:top-6`.
- **La hoja**, dentro de `mx-auto w-full max-w-3xl`. Es la de la demo (`Hoja` en `Demo/src/components/Ui.tsx`): `relative pt-3`, el imán `absolute top-0 left-1/2 z-10 size-7 -translate-x-1/2 rounded-full bg-miel shadow-md` (`aria-hidden`), y la superficie `rounded-sm bg-hoja px-4 angosto:px-2 @3xl/main:px-9 pt-7 pb-6 shadow-xl ring-1 ring-linea/60`. **Es la única superficie con sombra de la página.** No va inclinada.

**Encabezado de la hoja** (lenguaje 7.4): `div` con `border-b-2 border-tinta pb-3`:
- «Ficha de cuidado de» en `text-lg text-tenue`.
- `{nombre_pila}` en un `h1` (`id="titulo-pagina" tabIndex={-1}`), `titular text-5xl @2xl/main:text-6xl angosto:text-3xl leading-none outline-none`.

**Cada campo** (sección 3.11.1).

**Columna de datos** (lenguaje 7.4):

| Pieza | Texto | Construcción |
|---|---|---|
| Vigencia | «Puedes verla hasta el `{fecha}` a las `{hora}`.» | `p` con `flex items-start gap-2 text-base`, el ícono `Clock3` (`mt-0.5 size-5 shrink-0 text-turquesa`, `aria-hidden`). `{fecha}` y `{hora}` en `b` con `cifras`, cada una por separado, para que la hora pueda bajar de renglón sin partir la fecha |
| Botón | «Actualizar» | Botón **secundario** (sección 5), `self-start`, con el ícono `RefreshCw` (`size-5`, `aria-hidden`) |
| Confirmación | «Ficha actualizada a las `{hora}`.» [PROPUESTO: mismo verbo que el botón, DISENO.md principio 6] | `p` con `role="status"`, `text-base text-tenue`, con `animate-aparecer`. Aparece después de un "Actualizar" correcto y se reemplaza en el siguiente |
| Nota | «Solo `{nombre_comparte}` puede cambiar esta ficha.» | `p`, `text-base text-tenue` |

**La fecha y la hora de `vence_en`** se muestran en la hora de Chile (`America/Santiago`), en formato `DD/MM/AAAA` y `HH:MM` de 24 horas. **Ojo:** `Intl.DateTimeFormat('es-CL')` escribe `31-10-2026`, con guiones. La fecha se arma con `formatToParts` (`day`, `month`, `year` en dos, dos y cuatro dígitos, `hourCycle: 'h23'`). Ejemplo del contrato: `2026-11-01T02:00:00Z` se muestra «31/10/2026» y «23:00».

**"Actualizar":**
- Mientras pide la ficha: el botón conserva su ancho, lleva `aria-busy="true"` y dice «Actualizando…» [PROPUESTO]. La hoja sigue a la vista.
- **200:** la hoja se reemplaza con lo nuevo, sin moverse de lugar ni mover el foco, y aparece la confirmación.
- **401, 410 o 423:** la hoja se descarta y se muestra el estado (3.5 a 3.9).
- **Red o 5xx:** la hoja **sigue** a la vista y, bajo el botón, un `p` con `role="alert"` dice «**No pudimos completar esto.** Revisa tu conexión y vuelve a intentarlo.» (lenguaje 8, sin la frase "Lo que escribiste sigue aquí", que aquí no aplica: ver la sección 7).

**Revalidar sin que Rosa toque nada** (recomendación de comportamiento, la confirma el orquestador): la página vuelve a pedir la ficha cuando la pestaña vuelve a estar visible (`visibilitychange`) y cuando el reloj pasa `vence_en`. Así, si Carmen cortó el enlace o el enlace venció, Rosa ve el estado en vez de un texto que ya no debería ver. Esa petición no muestra "Actualizando…" ni la confirmación.

**Criterios verificables de 3.11:**
- La página de la ficha **no tiene ningún elemento en `turquesa` macizo**. La hoja es el objeto principal y «Actualizar» es secundario.
- La hoja es la única superficie con sombra.
- Solo aparecen los campos que vienen en `campos`, en el orden «Su día», «Si se altera», «A quién llamar». Un campo que no viene **no deja rastro**: ni título, ni "no compartido", ni un "2 de 3".
- Un campo con `texto: null` muestra la etiqueta «Sin completar».
- A 320 px con el texto al 200%: sin desplazamiento horizontal (`document.documentElement.scrollWidth <= innerWidth`), la hora de la línea de tiempo y su texto no se cortan, y la fecha de vencimiento no se parte.
- Ningún texto de la página está bajo 1 rem.

#### 3.11.1 Cada campo de la hoja

Construcción de un campo, de arriba abajo (`section aria-labelledby`, `mt-6` entre campos):

| Pieza | Texto | Construcción |
|---|---|---|
| Etiqueta | «Su día» · «Si se altera» · «A quién llamar» (lenguaje 5) | `h2`, `text-xl font-bold text-turquesa` |
| Pregunta guía | lenguaje 5.1, 5.2 y 5.3, con `{nombre_pila}` reemplazado | `p`, `text-base text-tenue`, `mt-1` |
| Contenido | El `texto` de la API | Sección 3.11.2, `mt-3` |
| Ejemplo | lenguaje 5.1, 5.2 y 5.3, tal cual, con las comillas «» | Sección 3.11.3, `mt-3` |

Textos exactos de la pregunta guía y del ejemplo (D2 pide confirmarlos para Rosa):

| Campo (`clave`) | Pregunta guía | Ejemplo |
|---|---|---|
| Su día (`rutina`) | «¿Cómo es un día normal para `{nombre_pila}`? Puedes contar un día bueno o uno difícil.» | «Por ejemplo: «08:00 Despierta. Le gusta que abran la cortina primero». Si empiezas con la hora, lo mostramos como línea de tiempo.» |
| Si se altera (`manejo_situaciones`) | «¿Qué calma a `{nombre_pila}` cuando se angustia?» | «Por ejemplo: «Le hace bien que le tomen la mano y le hablen de su pueblo».» |
| A quién llamar (`red_apoyo`) | «¿A quién llamar si algo pasa y no te ubican?» | «Por ejemplo: «Rodrigo, su hijo: +56 9 5555 0102».» |

#### 3.11.2 El contenido

- **Se pinta como texto, nunca como HTML** (sin `dangerouslySetInnerHTML`). Los saltos de línea del texto se respetan.
- **Texto corrido:** `renglones text-lg leading-7 max-w-prose`, en `tinta`. Un párrafo por línea del texto. `text-lg` (19 px) y no `text-base`, porque es lo que Rosa vino a leer y tal vez lo lee sin anteojos. `leading-7` (1,75 rem) coincide con el paso de la utilidad `renglones`.
- **Línea de tiempo:** si alguna línea empieza con una hora (`8:00`, `08:00`, `8.00`, con o sin guion después), el campo se muestra como la línea de tiempo de la demo (`LineaDeTiempo`, `Demo/src/components/TextoFicha.tsx`): una `ol`, cada hora en `cifras w-13 shrink-0 text-right font-bold text-turquesa`, un punto `size-3 rounded-full bg-miel ring-4 ring-hoja` (`aria-hidden`), la línea vertical `w-0.5 bg-miel/45` (`aria-hidden`) y el texto en `text-lg min-w-0`. Una hora de una cifra se completa con un cero (`8:00` → `08:00`). Una línea sin hora va sin hora, en su lugar.
- **Vacío** (`texto: null`, o solo espacios): la etiqueta «Sin completar» (lenguaje 5.4 y 7.4), una píldora `inline-flex items-center gap-1.5 rounded-full bg-tinta/7 px-2.5 py-0.5 text-base font-bold text-tenue` con el ícono `CircleDashed` (`size-4`, `aria-hidden`). Lleva figura y palabra, no solo un tono gris ni cursiva: Rosa tiene que entender que el campo está vacío, no que no cargó.
- **Los teléfonos no se vuelven enlaces.** Detectar un número dentro de un texto libre puede equivocarse, y un `tel:` mal armado en una urgencia es peor que ninguno. Queda como propuesta para después del piloto.

#### 3.11.3 El ejemplo

Mitigación del riesgo D2, mientras Jorge decide:
- Va **después** del contenido, nunca antes: Rosa lee primero lo que escribió Carmen.
- `p` con `border-s-2 border-linea ps-3 text-base text-tenue`. El borde y el gris lo separan del contenido, y el «Por ejemplo:» lo dice con palabras.
- **Nunca es un enlace**, tampoco el teléfono del ejemplo.
- Lleva `aria-describedby` hacia él desde la sección, no `aria-labelledby`: el lector de pantalla lo lee como descripción, después del contenido.

---

### 3.12 Error general (sin conexión, 5xx o un `type` no previsto)

**Objetivo:** Rosa sabe que algo falló de nuestro lado o de la conexión, y puede volver a intentar con un toque.

Se usa cuando falla la **primera** petición de una pantalla (la presentación al abrir, o la ficha después del canje o al recargar). Los errores del canje y de "Actualizar" no llegan aquí: van en su mensaje (3.3 y 3.11).

**Esquema a 360 px** (patrón 2.3):

```
│              ┌────┐                │
│              │ (!) │               │  baldosa neutra, ícono CircleAlert
│              └────┘                │
│     No pudimos completar esto.     │  h1
│  Revisa tu conexión y vuelve a     │  text-lg tenue
│  intentarlo.                       │
│        [ Volver a intentar ]       │  único turquesa macizo
```

| Pieza | Texto |
|---|---|
| Título | «No pudimos completar esto.» (primera frase de lenguaje 8, "Cualquier otro") [PROPUESTO como título] |
| Texto | «Revisa tu conexión y vuelve a intentarlo.» (lenguaje 8, sin "Lo que escribiste sigue aquí": aquí Rosa no escribió nada) |
| Botón principal | «Volver a intentar» [PROPUESTO: mismo verbo que el texto] |

- El botón repite la petición que falló, con el token que todavía está en la dirección (antes del canje) o con la cookie (después). Mientras tanto, «Abriendo el enlace…» o «Abriendo la ficha…» y `aria-busy`.
- Baldosa neutra `bg-tinta/7 text-tenue`, no `pronto`.
- Sin la nota «¿Qué hago?».

---

## 4. Lo que NO debe mostrarse

| Nunca | Por qué |
|---|---|
| El token, en ninguna parte de la página, ni en un texto, ni en un `title`, ni en un atributo `data-` | Es la llave. Viaja solo en el fragmento y en el cuerpo del POST |
| El token en la dirección **después del canje**. La barra queda en `/r` (`history.replaceState`) | Criterio de MATU-19 y lenguaje 7.1, pie |
| El PIN fuera del campo, y el PIN en el campo después de un canje correcto | Se dicta una vez. Después del 204, el campo se vacía y la pantalla se desmonta |
| El nombre de la persona o de quien compartió en el `<title>` | Queda en el historial y en la lista de pestañas (2.5) |
| La palabra «relevo» en cualquier texto que vea Rosa, también en el `<title>` y en los `aria-label` | Al relevo nunca se le dice "relevo": lee "ficha de cuidado" (lenguaje 4) |
| Los campos que no se compartieron, o un conteo como "2 de 3" | El contrato no los devuelve y la página no los insinúa (3.11) |
| El vencimiento, los campos o el nombre de Rosa **antes** del PIN | `/presentacion` devuelve solo los dos nombres de pila (contrato, decisión 28) |
| Quién escribió cada campo, cuándo, el apellido, la dirección o cualquier dato del grupo | El contrato no lo devuelve. La página no pide nada más |
| `title`, `detail`, `mensaje`, `status`, `request_id` o un código de error de la API | Lenguaje 8 y 3.2: el texto sale del `type` |
| El conteo de intentos antes del primer error | 3.3 |
| Los términos de lenguaje 3, entre ellos "token", "sesión", "canje", "revocado", "inválido", "denegado" | Lenguaje 3.2 |
| "Cifrado" o "cifrada" | No se dice hasta que MATU-11 exista (lenguaje 5.4) |
| Navegación de la familia, "Iniciar sesión", "Crear cuenta", "Descarga la app" o cualquier invitación a registrarse | Rosa no necesita cuenta (lenguaje 7.1, pie) |
| Fuentes, íconos o imágenes desde una CDN, scripts de terceros o analítica | CLAUDE.md, agente 3, punto 5 |
| La ficha en `localStorage`, `sessionStorage`, la URL o un service worker | CLAUDE.md, agente 3, punto 5 |
| La ficha en pantalla o en memoria después de un 401, 410 o 423 | 3.4 |
| Un botón deshabilitado sin una frase que diga por qué | DISENO.md, sección 6. Aquí no hay ninguno |

---

## 5. Componentes y sus estados

Los mismos de la demo (`Demo/src/components/Ui.tsx`), con el token renombrado a `turquesa` (sección 6.1). El frontend los construye en `web/` y no los importa desde `Demo/`.

| Componente | Normal | Foco | Presionado | Cargando | Error |
|---|---|---|---|---|---|
| **Botón principal** («Ver la ficha», «Volver a intentar») | `inline-flex min-h-12 max-w-full items-center justify-center gap-2 rounded-xl px-5 py-2.5 font-bold leading-tight bg-turquesa text-papel hover:brightness-110`. Al ancho de su texto, también en el teléfono (DISENO.md, sección 5). `papel` sobre `turquesa`: 6,0:1 claro, 9,3:1 oscuro | Foco base | `active:brightness-95` | Mismo ancho, texto en gerundio, `aria-busy="true"` | El botón no cambia. El mensaje va en su lugar (3.3) |
| **Botón secundario** («Actualizar») | Igual de alto, `bg-hoja text-turquesa ring-2 ring-inset ring-turquesa/70` | Foco base | `bg-rocio` | Igual que el principal | — |
| **Enlace** («Política de privacidad») | `text-turquesa underline underline-offset-4 decoration-turquesa/40`, `min-h-12` | Foco base | `decoration-turquesa` | — | — |
| **Campo del PIN** | `bg-hoja ring-2 ring-inset ring-borde` (3,5:1 sobre `hoja`) | `focus-visible:ring-turquesa` y el foco base | — | Sin cambio | `ring-pronto text-pronto` y `aria-invalid` (3.3) |
| **Nota «¿Qué hago?»** | `rounded-xl bg-rocio px-4 py-3`, título en negrita | — | — | — | — |
| **Etiqueta «Sin completar»** | Píldora neutra con `CircleDashed` (3.11.2) | — | — | — | — |
| **Baldosa del momento** | `rounded-2xl`, `bg-rocio text-turquesa` en el PIN y `bg-tinta/7 text-tenue` en los estados | — | — | — | `bg-pronto-fondo text-pronto` solo con un PIN incorrecto o incompleto |

**Áreas táctiles:** todo lo que se toca mide al menos 48 × 48 px. `min-h-12` es 3 rem = 51 px con la raíz de 17 px. **Ojo:** `min-h-11` y `size-11` dan 46,75 px y no alcanzan (ESPEC-ADR-027, 7.4).

**Íconos:** solo de `lucide-react`: `Heart`, `KeyRound`, `ShieldCheck`, `FileText`, `Lock`, `Clock3`, `Unlink`, `Link2Off`, `Hourglass`, `CircleAlert`, `RefreshCw` y `CircleDashed`. Todos con `aria-hidden`: el texto a su lado dice lo mismo.

---

## 6. Los tokens en `web/`

### 6.1 La decisión

**`web/` tiene su propia copia de los tokens, en `web/src/index.css`, y no importa nada de `Demo/`.** La demo es un proyecto aparte, se congela después del 30/10 y no es parte de la aplicación. `web/` es la aplicación definitiva, y su capa de tokens es la de abajo, copiada **tal cual**. Desde hoy, el dueño de esos tokens es el diseñador, igual que en la demo: el frontend no los edita, y un cambio pasa primero por esta carpeta (`docs/diseno/`).

Qué cambia respecto de `Demo/src/index.css`, y por qué:

| Cambio | Por qué |
|---|---|
| **`pino` pasa a llamarse `turquesa`**, con los mismos valores | DISENO.md, sección 1, ya lo había decidido: "Se renombra a `turquesa` después de la demo". `web/` empieza sin componentes, así que es el momento sin costo. **Al copiar clases de la demo, `pino` se reemplaza por `turquesa`.** Tailwind no avisa si una clase no existe: la revisión visual lo detecta |
| **Sin los tokens `pasarela-*`** | La pasarela simulada es de la demo. En la aplicación, el pago lo muestra Transbank en su propia página |
| **Sin `overflow-x: hidden` en `body`** | En la demo protegía el escenario del presentador. En `web/` escondería un desborde en vez de mostrarlo, y la verificación `scrollWidth <= innerWidth` dejaría de detectarlo |
| **Sin el `scroll-padding-bottom` de 10 rem** | Existe por la barra de secciones fija abajo de la app de la familia. La página del relevo no tiene nada fijo. Vuelve cuando se construya esa barra |
| **El contenedor `app` se declara en la capa base, sobre `#raiz`** | En la demo lo pone el escenario (`Escenario.tsx`). En `web/` no hay escenario, y sin ese contenedor las variantes `angosto:` y `telefono:` no se activan nunca |
| **El tema sigue al sistema.** Se mantienen los selectores `[data-tema]` para un selector futuro, pero la página del relevo no tiene uno | Para la presentación, el computador del proyector va en tema claro (DISENO.md, sección 1) |

**Dependencias de `web/package.json`** (fuentes locales, sin CDN): `@fontsource/atkinson-hyperlegible`, `@fontsource/atkinson-hyperlegible-mono`, `@fontsource-variable/bricolage-grotesque`, `lucide-react`, `tailwindcss` y `@tailwindcss/vite`, en las mismas versiones mayores de `Demo/package.json`.

### 6.2 La capa de tokens, para copiar tal cual en `web/src/index.css`

```css
@import 'tailwindcss';

/* Fuentes locales, sin CDN: la página funciona igual sin acceso a terceros. */
@import '@fontsource/atkinson-hyperlegible/latin-400.css';
@import '@fontsource/atkinson-hyperlegible/latin-700.css';
@import '@fontsource/atkinson-hyperlegible/latin-400-italic.css';
@import '@fontsource/atkinson-hyperlegible-mono/latin-400.css';
@import '@fontsource/atkinson-hyperlegible-mono/latin-700.css';
@import '@fontsource-variable/bricolage-grotesque/wght.css';

/*
 * Identidad de MATU (Demo/DISENO.md, sección 1; docs/diseno/matu-23-pagina-relevo.md, sección 6).
 * Los tokens son del diseñador: el frontend no los edita. Contrastes medidos en DISENO.md.
 *   papel     fondo general, neblina de agua
 *   hoja      la hoja de la ficha, formularios y listas
 *   tinta     texto principal (14,1:1 sobre papel)
 *   tenue     texto secundario (6,4:1 sobre papel, 7,1:1 sobre hoja)
 *   turquesa  turquesa profundo: texto de acción, enlaces, botones, foco (6,0:1 sobre papel,
 *             6,7:1 sobre hoja). En la demo se llama `pino`
 *   marca     turquesa de marca: el círculo del logo y los acentos grandes. Igual en los dos
 *             temas. Nunca texto: el corazón blanco sobre ella mide 3,5:1
 *   miel      calidez: el imán de la hoja y los puntos de "Su día". Nunca texto ni dato
 * Semánticos, siempre con su fondo y con una palabra: pronto, atenta, ok.
 */
@theme {
  --color-papel: #ecf3f2;
  --color-hoja: #ffffff;
  --color-tinta: #13252a;
  --color-tenue: #485b5f;
  --color-turquesa: #086764;
  --color-marca: #0d9a94;
  --color-miel: #e3a43a;

  --color-pronto: #a8261b;
  --color-pronto-fondo: #fbe9e6;
  --color-atenta: #835000;
  --color-atenta-fondo: #fcefd8;
  --color-ok: #22663d;
  --color-ok-fondo: #e1f1e6;

  /* Derivados, no son tokens nuevos */
  --color-linea: color-mix(in oklab, var(--color-tinta) 14%, transparent);
  --color-rocio: color-mix(in oklab, var(--color-turquesa) 12%, var(--color-hoja));
  /* Borde de los controles: 3,5:1 sobre hoja y 3,1:1 sobre papel en claro, 4:1 sobre hoja en
     oscuro (WCAG 1.4.11). `linea` queda para divisores, nunca para el borde de un control. */
  --color-borde: color-mix(in oklab, var(--color-tinta) 50%, var(--color-hoja));

  --font-sans: 'Atkinson Hyperlegible', ui-sans-serif, system-ui, sans-serif;
  --font-display: 'Bricolage Grotesque Variable', 'Atkinson Hyperlegible', ui-sans-serif, sans-serif;
  --font-cifras: 'Atkinson Hyperlegible Mono', ui-monospace, monospace;
  /* Tailwind usa --font-mono en pre, code y kbd: que sea la cara local, nunca una del sistema. */
  --font-mono: var(--font-cifras);

  --ease-calma: cubic-bezier(0.22, 0.8, 0.24, 1);

  --animate-digito: digito 520ms var(--ease-calma) both;
  --animate-trazo: trazo 900ms var(--ease-calma) both;
  --animate-aparecer: aparecer 180ms ease-out both;

  @keyframes digito {
    0% { opacity: 0; transform: translateY(-0.6em) scale(0.9); }
    60% { opacity: 1; transform: translateY(0.06em) scale(1.02); }
    100% { opacity: 1; transform: none; }
  }
  @keyframes trazo {
    from { stroke-dashoffset: 1; }
    to { stroke-dashoffset: 0; }
  }
  @keyframes aparecer {
    from { opacity: 0; }
    to { opacity: 1; }
  }
}

/*
 * Tema oscuro: sigue al sistema, salvo que un selector futuro fije uno con data-tema.
 * Los valores van repetidos en el selector y en la media query porque CSS no deja compartir un
 * bloque entre los dos. Si cambia uno, cambia el otro. `marca` no cambia.
 */
:root[data-tema='oscuro'] {
  color-scheme: dark;
  --color-papel: #0d1719;
  --color-hoja: #152427;
  --color-tinta: #e4eeeb;
  --color-tenue: #a9bcb8;
  --color-turquesa: #52ccc3;
  --color-miel: #e8b866;
  --color-pronto: #ffa395;
  --color-pronto-fondo: #3b1b17;
  --color-atenta: #f2c46b;
  --color-atenta-fondo: #33270f;
  --color-ok: #8fd9a8;
  --color-ok-fondo: #13301f;
}
:root[data-tema='claro'] {
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-tema='claro']) {
    color-scheme: dark;
    --color-papel: #0d1719;
    --color-hoja: #152427;
    --color-tinta: #e4eeeb;
    --color-tenue: #a9bcb8;
    --color-turquesa: #52ccc3;
    --color-miel: #e8b866;
    --color-pronto: #ffa395;
    --color-pronto-fondo: #3b1b17;
    --color-atenta: #f2c46b;
    --color-atenta-fondo: #33270f;
    --color-ok: #8fd9a8;
    --color-ok-fondo: #13301f;
  }
}

@layer base {
  /* 1rem = 17 px: el texto base y todo el espaciado escalan con la preferencia de la persona. */
  html {
    font-size: 106.25%;
    -webkit-text-size-adjust: 100%;
    color-scheme: light dark;
  }
  body {
    @apply bg-papel text-tinta font-sans antialiased;
    line-height: 1.5;
    min-height: 100dvh;
    /* Una palabra que no cabe sola en su renglón se parte en vez de salirse. `break-word` y no
       `anywhere`: no cambia el ancho mínimo de nada ni deja columnas de una letra. Sin
       `overflow-x: hidden`: un desborde se tiene que ver para poder corregirlo. */
    overflow-wrap: break-word;
  }
  /* La raíz de React es el contenedor `app`: de ella dependen `angosto:` y `telefono:`. */
  #raiz {
    container: app / inline-size;
    display: flex;
    flex-direction: column;
    min-height: 100dvh;
  }
  button,
  input,
  textarea,
  select {
    font: inherit;
    color: inherit;
  }
  :focus-visible {
    outline: 3px solid var(--color-turquesa);
    outline-offset: 2px;
    border-radius: 0.4rem;
  }
  /* Un fieldset mide por defecto lo que su contenido: con el texto al 200% desbordaría. */
  fieldset {
    min-width: 0;
  }
  pre {
    font-family: inherit;
  }
  h1,
  h2,
  h3 {
    text-wrap: balance;
  }
  p {
    text-wrap: pretty;
  }
}

/*
 * Variantes de composición (Demo/DISENO.md, sección 3). Miran el contenedor `app` (#raiz).
 *   angosto   la app mide menos de 16 rem: con el texto al 200% en una pantalla de menos de
 *             544 px, o con el zoom del navegador sobre 400% en 1280 px. Se quitan rellenos y se
 *             achica lo que va en tamaño de título. Nunca se activa a 320 px sin zoom.
 *   telefono  la pantalla mide menos de 40 rem y la app no está en modo angosto. La usará la
 *             barra de secciones de la familia. La página del relevo no la necesita.
 */
@custom-variant angosto {
  @container app (width < 16rem) {
    @slot;
  }
}
@custom-variant telefono {
  @media (width < 40rem) {
    @container app (width >= 16rem) {
      @slot;
    }
  }
}

/* Cifras de dinero, fechas y horas: alineadas, en la cara del texto, sin partirse. */
@utility cifras {
  font-variant-numeric: tabular-nums lining-nums;
  white-space: nowrap;
}
/* Solo lo que se dicta dígito a dígito: el PIN y el código de retiro. */
@utility digitos {
  font-family: var(--font-cifras);
  font-variant-numeric: tabular-nums;
}
@utility titular {
  font-family: var(--font-display);
  font-weight: 800;
  letter-spacing: -0.025em;
  line-height: 1.05;
}
/* Renglones de cuaderno en la hoja de la ficha. */
@utility renglones {
  background-image: repeating-linear-gradient(
    to bottom,
    transparent 0,
    transparent calc(1.75rem - 1px),
    color-mix(in oklab, var(--color-turquesa) 12%, transparent) calc(1.75rem - 1px),
    color-mix(in oklab, var(--color-turquesa) 12%, transparent) 1.75rem
  );
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 1ms !important;
    animation-delay: 0ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 1ms !important;
    scroll-behavior: auto !important;
  }
}
```

### 6.3 `web/index.html`

- `<html lang="es-CL">`.
- `<meta name="viewport" content="width=device-width, initial-scale=1">`. **Nunca** `maximum-scale` ni `user-scalable=no`: Rosa tiene que poder ampliar.
- `<meta name="referrer" content="no-referrer">` y `<meta name="robots" content="noindex">`, como complemento de las cabeceras (D6).
- `<meta name="theme-color" content="#0d9a94">` y el favicon local del logo (círculo `#0D9A94` con el corazón blanco), igual que la demo.
- `<title>Ficha de cuidado compartida · MATU</title>` (2.5).
- `<div id="raiz"></div>`: el contenedor `app` de la capa base.

---

## 7. Textos que faltan en `lenguaje.md` (D7)

Ninguno se usa hasta que Jorge los apruebe. Van a la sección 7 de `lenguaje.md`:

| Dónde | Texto propuesto | Por qué |
|---|---|---|
| Cargando la presentación | Abriendo el enlace… | 3.1 |
| Cargando la ficha, y el botón «Ver la ficha» mientras canjea | Abriendo la ficha… | Gerundio del botón (DISENO.md, sección 6) |
| Botón «Actualizar» mientras carga | Actualizando… | Ídem |
| Confirmación de «Actualizar» | Ficha actualizada a las `{hora}`. | Mismo verbo que el botón (principio 6) |
| Título del error general | No pudimos completar esto. | Es la primera frase de lenguaje 8. Una pantalla necesita un `h1` |
| Error general cuando no hay nada escrito | Revisa tu conexión y vuelve a intentarlo. | Lenguaje 8 dice "Lo que escribiste sigue aquí", que es falso al abrir el enlace o al actualizar |
| Botón del error general | Volver a intentar | Mismo verbo que el texto |
| 429 con un minuto | Vuelve a intentarlo en 1 minuto. | "1 minutos", igual que lenguaje 7.3 ya resolvió "1 intento" |
| 429 sin `Retry-After` | Vuelve a intentarlo en unos minutos. | La cabecera es obligatoria en el contrato, pero la página no debe quedar con un hueco |
| Título del aviso al relevo | Tus datos en MATU | La demo lo usa. ESPEC-ADR-027, 6.4, lo dejó como propuesta |
| Enlace a la política | Política de privacidad (se abre en otra pestaña) | Mismo patrón que lenguaje 6.4b |
| Nombre de la columna de datos, para el lector de pantalla | Sobre esta ficha | `aria-label` de la demo |
| `<title>` | «Ficha de cuidado compartida · MATU» y, en un estado que no abre, «`{título del estado}` · MATU» | 2.5 |

---

## 8. Cómo la voy a revisar

No apruebo una pantalla que no vi funcionando (agente 6, punto 3). Para la revisión, el frontend deja la página levantable en local contra el doble del contrato (MATU-23, último criterio), con un token de ejemplo para **cada** estado: PIN correcto, PIN incorrecto con 3 y con 1 intento, bloqueado, vencido, cortado, no disponible, sin sesión, 429 con `Retry-After: 60` y 600, error 500, y una ficha con los tres campos (uno con horas, uno corrido, uno `null`) y otra con un solo campo.

Capturas de **cada** pantalla y estado:
- 360 × 740, 1280 × 720 y 1920 × 1080, en tema claro y oscuro.
- 320 px con el zoom del navegador al 200%, y 1280 px con el zoom al 400% (320 px efectivos).
- Con la preferencia de tamaño de texto del sistema al 200% en un teléfono Android real (checklist de la estrategia, sección 7: "Revisión en un teléfono real").
- Con `prefers-reduced-motion: reduce`.

En cada una mido: `scrollWidth <= innerWidth`, alto de lo que se toca (≥ 48 px), contraste del texto y de los bordes, el foco visible al recorrer con Tab, que el único `turquesa` macizo sea el de la tabla de abajo, y que ningún texto quede bajo 17 px.

| Pantalla | Elementos en `turquesa` macizo |
|---|---|
| Cargando | 0 |
| PIN, y sus mensajes | 1: «Ver la ficha» |
| Estados que no abren (3.5 a 3.10) | 0 |
| Ficha | 0 |
| Error general | 1: «Volver a intentar» |

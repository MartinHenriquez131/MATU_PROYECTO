# MATU-45 · Quién la vio · Especificación de diseño

Agente 6 (UI/UX) · 03-11-2026 · para el frontend sobre `web/` (esqueleto de MATU-39).
Fuentes: `Demo/DISENO.md`, tokens de `Demo/src/index.css`, `docs/lenguaje.md` 9, contrato `docs/api/propuestos/relevo.openapi.yaml` (`listarAperturasRelevo`, esquemas `Apertura` y `ListaAperturas`), y la pantalla `QuienVio` de la demo (`Demo/src/familia/Ficha.tsx`, líneas 580 a 643), que es el modelo.

Los textos marcados **[PROPUESTO]** esperan la aprobación de Jorge. Los marcados **[LENGUAJE]** ya están en `lenguaje.md` y no se cambian. Jorge aprobó el 03-11 los textos de Quién la vio (marcados **[APROBADO 03-11]**), con la bajada sin la frase final sobre vigilancia.

---

## 0. Lo que tiene que decidir alguien más

| # | Qué | Propuesta | Quién |
|---|---|---|---|
| D1 | `lenguaje.md` 9 dice «Todavía nadie ha abierto la ficha…» y la demo dice «Todavía nadie ha abierto el enlace ni la ficha…». No son iguales y la del documento no cubre el caso de solo presentaciones (no puede pasar: si hay una presentación ya no está vacío, así que ambas sirven). | Usar la de `lenguaje.md`, que manda. | Orquestador avisa a Jorge |
| D2 | La explicación de «presentación sin apertura» (sección 4.3) es texto nuevo, no está en `lenguaje.md`. | El texto de 4.3, para agregar a `lenguaje.md` 9 si se aprueba. | Jorge |
| D3 | Fechas relativas («hoy», «ayer», día de la semana) además del formato DD/MM/AAAA de CLAUDE.md 2. | Relativa hasta 6 días atrás, absoluta desde el 7.º, y siempre la fecha completa en `<time datetime>` (4.2). | Jorge |
| D4 | La columna «Quién puede verla ahora» necesita la lista de accesos de MATU-48 (`GET …/plan/accesos`). Si MATU-48 no está en `main` cuando se construya MATU-45, la columna no aparece (no se muestra vacía ni con datos inventados). | Así. | Orquestador |

---

## 1. Objetivo

**Carmen, después de compartir la ficha con Rosa, quiere quedarse tranquila de que Rosa la pudo abrir, sin sentir que está vigilando a nadie.**

No es una bitácora de seguridad: es un respaldo. Por eso la pantalla habla de personas y momentos («Rosa abrió la ficha, hoy a las 10:14»), nunca de «eventos», «registros», «auditoría» ni «accesos» (`lenguaje.md` 3, fila de auditoría).

## 2. Dónde se entra

La sección «Ficha» de MATU-39 no tiene subsecciones todavía. Se entra por tres puertas, todas a la misma ruta **`/ficha/quien-la-vio`**:

1. **Desde la ficha (`/ficha`, MATU-39 3.6):** bajo los tres campos, un bloque «Últimas aperturas» con las 3 más recientes (mismo componente, 4.1) y el botón `variante="texto"` «Ver todo en Quién la vio» **[LENGUAJE: demo]**. Si no hay ninguna, el bloque muestra solo el texto vacío corto (5.2) y no el botón. Solo con rol que pueda ver aperturas (sección 6).
2. **Desde Compartir / Enlaces (MATU-48):** en cada enlace de la lista, junto a «Cortar el enlace de `{nombre}`», el botón `variante="texto"` «Ver cuándo la abrió» **[PROPUESTO]**. Lleva a la misma ruta (sin filtro; el contrato no filtra por acceso y no se filtra en el cliente para no esconder líneas).
3. **Después de crear un enlace (MATU-48):** no hay atajo. Recién creado no hay nada que ver.

La navegación principal no cambia (MATU-39 2.2): «Quién la vio» vive dentro de «Ficha», que queda marcada como actual (`aria-current="page"`) mientras se está en esta ruta.

Volver: un enlace `variante="texto"` con `ChevronLeft` y «Volver a la ficha» **[APROBADO 03-11]** arriba del `h1`, 48 px de alto. Sin flecha decorativa en botones de acción (DISENO.md 5); este es navegación, como en la demo.

`<title>`: «Quién la vio · MATU».

## 3. Jerarquía

1. **Primero:** el `h1` «Quién la vio» **[LENGUAJE]** y la bajada «Una línea por cada vez que alguien abre el enlace o la ficha, o escribe mal el PIN. Es un respaldo para ti.» **[APROBADO 03-11]**
2. **Segundo:** la lista de aperturas, la más reciente arriba. La primera línea es la respuesta a «¿la pudo abrir?».
3. **Tercero:** «Quién puede verla ahora» (los enlaces activos) con «Ver y cortar enlaces», y la nota «La ficha se guarda cifrada.» **[APROBADO 03-11]**, con `ShieldCheck`.

**Acción principal:** ninguna en macizo. Es una pantalla de lectura. «Ver aperturas anteriores» es `secundario`; «Ver y cortar enlaces» es `secundario`. No hay ningún `pino` macizo en la pantalla.

## 4. Composición

### 4.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ (cabecera de MATU-39)              │
├────────────────────────────────────┤
│ ‹ Volver a la ficha                │  48 px
│                                    │
│ Quién la vio                       │  h1
│ Una línea por cada vez que alguien │  bajada, text-tenue
│ abre el enlace o la ficha, o       │
│ escribe mal el PIN. Es un respaldo │
│ para ti.                           │
│                                    │
│ Hoy                                │  h2 por día
│ ┌──┐ Rosa abrió la ficha           │  ícono en círculo + frase en negrita
│ │◎ │ a las 10:14                   │  text-tenue, <time>
│ └──┘───────────────────────────────│  border-b linea
│ ┌──┐ Rosa escribió mal el PIN      │
│ │! │ a las 10:01                   │  forma distinta (CircleAlert) + palabra
│ └──┘───────────────────────────────│
│ ┌──┐ Rosa abrió el enlace          │
│ │⛓ │ a las 10:01                   │
│ └──┘                               │
│ Ayer                               │
│ ┌──┐ Carla abrió el enlace         │
│ │⛓ │ a las 19:40                   │
│ │  │ Todavía no abre la ficha. …   │  nota 4.3, text-tenue
│ └──┘                               │
│                                    │
│ [ Ver aperturas anteriores ]       │  secundario, ancho natural
│                                    │
│ Quién puede verla ahora            │  h2
│ ▌Rosa          vence en 1 día 3 h  │  border-l-4 pino, bg-hoja
│ [ Ver y cortar enlaces ]           │
│ 🛡 La ficha se guarda cifrada.      │
├────────────────────────────────────┤
│ [Ficha] [Insumos] [Compartir]      │  barra fija
└────────────────────────────────────┘
```

Con `angosto:` (texto al 200% en 320 px) el ícono pasa arriba de la frase (`angosto:flex-col angosto:gap-2`, como la demo) y la fila de «Quién puede verla ahora» se apila (`flex-wrap`, ya lo hace).

### 4.2 Pantalla ancha (`@4xl/app:` y más)

```
┌──────────────┬───────────────────────────────────────────────────────────────┐
│ (navegación) │ ‹ Volver a la ficha                                           │
│              │ Quién la vio                                                  │
│              │ Una línea por cada vez … un respaldo para ti.  (max-w-prosa)  │
│              │                                                               │
│              │ ┌ Aperturas (ancha, ~2/3) ──────┐ ┌ Quién puede verla ahora ┐│
│              │ │ Hoy                            │ │ ▌Rosa  vence en 1 día 3 h││
│              │ │ ◎ Rosa abrió la ficha  10:14   │ │ [Ver y cortar enlaces]   ││
│              │ │ ! Rosa escribió mal el PIN …   │ │ 🛡 La ficha se guarda …  ││
│              │ │ …                              │ └──────────────────────────┘│
│              │ │ [Ver aperturas anteriores]     │                             │
│              │ └────────────────────────────────┘                             │
└──────────────┴───────────────────────────────────────────────────────────────┘
```

Mismas piezas que la demo: `PaginaFicha` con `bajada`, `Columnas izquierda="ancha"`, dos `Columna`. La lista nunca supera `max-w-prosa` de largo de línea útil. A 1920 px la página sigue en `max-w-7xl` centrada (MATU-39 2.1). Botones de ancho natural, nunca de ancho completo en escritorio.

### 4.3 Una línea de apertura

Componente `LineaApertura` (copia de `Eventos` de la demo, adaptado al contrato). `ol` con `li` por línea; `flex items-start gap-3 border-b border-linea py-3 last:border-0`.

| `tipo` | Frase (`font-bold`) | Ícono lucide en círculo `size-9 rounded-full` | Tono del círculo |
|---|---|---|---|
| `presentacion` | «`{nombre_relevo}` abrió el enlace» **[LENGUAJE]** | `Link2` | `bg-rocio text-pino` |
| `apertura` | «`{nombre_relevo}` abrió la ficha» **[LENGUAJE]** | `UserRound` | `bg-rocio text-pino` |
| `pin_incorrecto` | «`{nombre_relevo}` escribió mal el PIN» **[LENGUAJE]** | `CircleAlert` | `bg-atenta-fondo text-atenta` |
| `bloqueo` | «El enlace de `{nombre_relevo}` se bloqueó por PIN incorrecto» **[LENGUAJE]** | `Lock` | `bg-atenta-fondo text-atenta` |

- El ícono es `aria-hidden`: la frase ya dice qué pasó. El estado se distingue por **palabra y forma** (cuatro íconos distintos), el color solo acompaña.
- No se usa `alerta` (rojo) en ninguna línea. Un PIN mal escrito es lo normal de un dedo apurado; no es una emergencia.
- La frase nunca dice «intentó», «sospechoso», «falló», «acceso denegado» ni «registro».
- `nombre_relevo` se muestra tal cual, sin artículo ni pronombre: las frases no tienen género («abrió», «escribió», «el enlace de»). La persona cuidada no se nombra en esta pantalla.

**Fecha y hora** (debajo de la frase, `text-base text-tenue tabular-nums`, dentro de `<time dateTime={ocurrido_en}>`), en hora de Chile (`America/Santiago`), 24 h:

| Cuándo | Texto | Ejemplo |
|---|---|---|
| Hoy | «a las HH:MM» (el día va en el `h2`) | a las 10:14 |
| Ayer | «a las HH:MM» bajo `h2` «Ayer» | a las 19:40 |
| 2 a 6 días atrás | `h2` «El `{día de la semana}`» | h2 «El sábado», línea «a las 10:14» |
| 7 días o más | `h2` «El DD/MM/AAAA» | h2 «El 24/10/2026» |

- Las líneas se agrupan por día con un `h2` (`text-lg font-bold`, `mt-6` salvo el primero). El orden es el del servidor, del más reciente al más antiguo; el cliente no reordena.
- El `title` del `<time>` lleva siempre la fecha completa «DD/MM/AAAA HH:MM» para quien la pida. El lector de pantalla lee el `h2` y la línea, que juntos son completos.
- En el bloque «Últimas aperturas» de la ficha no hay `h2` por día: la fecha va completa en la línea («hoy a las 10:14», «ayer a las 19:40», «el sábado a las 10:14», «el 24/10/2026 a las 10:14»), que es la forma de la tarjeta: «La vio Carla, el sábado a las 10:14».

**Presentación sin apertura** (la explicación tranquila). Se agrega bajo una línea `presentacion` **solo si** no hay, más arriba en la lista ya cargada (más reciente), ningún otro evento del mismo `acceso.id`: ni `apertura`, ni `pin_incorrecto`, ni `bloqueo`. Si la persona ya escribió el PIN (bien o mal), la nota no explica nada y se omite. Regla en la función pura `presentacionSinAbrir` de `QuienLaVio.tsx`. Como la lista viene de la más nueva a la más vieja, lo que está más arriba ya está cargado: la regla no depende de la paginación.

> «Todavía no abre la ficha. Puede que no haya escrito el PIN aún, o que el enlace le haya llegado a otra persona. Si te preocupa, puedes cortarlo desde Enlaces.» **[APROBADO 03-11]**

`text-base text-tenue`, sin ícono, sin color. «Enlaces» es un enlace en línea (subrayado, 48 px de alto con `py` en el teléfono) a la lista de MATU-48; si MATU-48 no existe, la última oración se omite.

**Bloqueo** (sin alarmar). Bajo una línea `bloqueo`, siempre:

> «Ya no abre con ese enlace. Si fue un error al escribir, crea uno nuevo y díctale el PIN de nuevo.» **[APROBADO 03-11]**

`text-base text-tenue`. Más un `Boton variante="texto"` «Crear un enlace nuevo» **[LENGUAJE: demo]** a Compartir (solo `admin` y `cuidador`, y solo si MATU-48 existe). Sin rojo, sin signo de exclamación.

## 5. Estados

### 5.1 Cargando
Igual que MATU-39 5.1: tres líneas esqueleto (`bg-hoja` círculo y dos barras `rounded-control`) con `aria-busy="true"` en el `ol` y un texto `sr-only` «Cargando…». Sin spinner que gire; con `prefers-reduced-motion` sin pulso. Si tarda menos de 300 ms no se muestra.

### 5.2 Vacío (`items: []` en la primera página)
`Nota` (tono `rocio`, la de la demo): «Todavía nadie ha abierto la ficha. Cuando alguien la abra, aparece aquí.» **[LENGUAJE]** (ver D1). Debajo, si el rol puede compartir y MATU-48 existe, `Boton variante="secundario"` «Compartir la ficha» **[PROPUESTO]**. En la ficha (bloque corto) solo la nota.

### 5.3 Error de red o 5xx
MATU-39 5.2: `Nota tono="atenta"` con `CloudOff`: «No pudimos traer quién la vio. Revisa tu conexión e inténtalo de nuevo.» **[APROBADO 03-11]** y `Boton variante="secundario"` «Intentar de nuevo». Si ya había páginas cargadas y falla «Ver aperturas anteriores», la lista queda y el aviso va debajo, en lugar del botón, con el mismo «Intentar de nuevo».

### 5.4 Sin permiso (404)
El contrato responde el mismo 404 para «no existe» y «no puedes». La pantalla muestra lo mismo que MATU-39 5.6 (sin acceso a la ficha), sin decir por qué. El `observador` no ve la puerta de entrada (sección 6) y si escribe la ruta ve 5.6 sin llamar a la API.

### 5.5 Entrada vencida (401)
Lo resuelve el cliente de MATU-39 (sección 6 de esa especificación). Nada propio.

### 5.6 Cursor inválido (422)
Solo puede pasar por un defecto. Se trata como 5.3 y se vuelve a pedir la primera página con «Intentar de nuevo».

### 5.7 Paginación
- `limite=20`. Si `siguiente_cursor` no es `null`, al final de la lista `Boton variante="secundario"` «Ver aperturas anteriores» **[APROBADO 03-11]**, ancho natural, 48 px.
- Al pulsar: el botón pasa a cargando (`aria-disabled`, texto «Cargando…», mismo ancho), las nuevas líneas se **agregan abajo** y el foco va a la primera línea nueva (`tabIndex={-1}`). Un `role="status"` anuncia «Se agregaron `{n}` líneas.» **[APROBADO 03-11]**
- Sin desplazamiento infinito: la carga la decide la persona.
- Cuando `siguiente_cursor` es `null` y hubo más de una página: `text-tenue` «No hay más.» **[APROBADO 03-11]** en lugar del botón.
- Si una página nueva empieza con el mismo día que terminó la anterior, no se repite el `h2`.

### 5.8 Al volver a la pantalla
Se vuelve a pedir la primera página (no se guarda nada entre visitas, ni en el navegador). No hay actualización automática ni sondeo.

## 6. Roles

| Rol | Ve «Quién la vio» | Ve «Crear un enlace nuevo» y «Compartir la ficha» |
|---|---|---|
| `admin`, `cuidador` | Sí | Sí |
| `pagador` con `puede_ver_plan` | Sí | No |
| `pagador` sin él, `observador`, desconocido | No (ni la puerta en la ficha) | No |

## 7. Tokens y componentes

Sin tokens nuevos. Usa: `papel`, `hoja`, `linea`, `tinta`, `tenue`, `pino`, `rocio`, `turquesa` (foco y actual), `atenta`, `atenta-fondo`; `rounded-control`, `rounded-full`; `max-w-prosa`, `max-w-7xl`; `animate-aparecer`; variantes `telefono:` y `angosto:`.

Componentes: `PaginaFicha`, `Columnas`, `Columna`, `Subtitulo`, `Nota`, `Boton` (`secundario`, `texto`), `Cuando` (reescrito para `ocurrido_en` real en vez de minutos de la demo), `LineaApertura` (nuevo, copia de `Eventos`). Nada escrito a mano: ni colores, ni `size-[…]`, ni sombras.

## 8. Criterios visuales verificables

1. No hay ningún elemento en `pino` macizo ni en `alerta` en la pantalla.
2. Cada tipo de línea se distingue sin color: con escala de grises, las cuatro frases e íconos siguen siendo distintos.
3. Todo lo que se toca (volver, enlaces en línea, botones) mide al menos 48 × 48 px.
4. Ninguna fecha usa formato con mes en palabras ni hora AM/PM; las absolutas son DD/MM/AAAA y 24 h.
5. A 320 px con texto al 200% no hay desplazamiento horizontal; el ícono queda sobre la frase.
6. Ningún texto de la pantalla contiene «auditoría», «registro», «evento», «acceso denegado», «intento», «sospech», ni un pronombre o adjetivo con género para el relevo o la persona cuidada.
7. Nunca aparece la IP, el teléfono ni un identificador técnico (`acceso.id`, `request_id`).
8. El foco al llegar está en el `h1`, y tras «Ver aperturas anteriores» en la primera línea nueva.
9. En el proyector, la frase de cada línea es al menos `text-lg` y la hora al menos `text-base` (1 rem).

## 9. Textos nuevos para `lenguaje.md` (si Jorge aprueba)

- Volver a la ficha
- Ver cuándo la abrió
- Todavía no abre la ficha. Puede que no haya escrito el PIN aún, o que el enlace le haya llegado a otra persona. Si te preocupa, puedes cortarlo desde Enlaces.
- Ya no abre con ese enlace. Si fue un error al escribir, crea uno nuevo y díctale el PIN de nuevo.
- Compartir la ficha
- No pudimos traer quién la vio. Revisa tu conexión e inténtalo de nuevo.
- Ver aperturas anteriores · Se agregaron `{n}` líneas. · No hay más.
- Encabezados de día: Hoy · Ayer · El `{día}` · El DD/MM/AAAA

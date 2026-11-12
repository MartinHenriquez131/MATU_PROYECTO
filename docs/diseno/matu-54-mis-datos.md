# MATU-54 · Ver y descargar los datos («Datos de {nombre}» y «Tus datos») · Especificación de diseño

**Versión 1.0 · 12-11-2026 · agente 6 UI/UX.** Se escribió antes de construir y antes de que exista el contrato. Las preguntas que dependen del contrato van en la sección 10. **El frontend no inventa campos:** donde esta especificación nombra un dato, lo toma del contrato con el nombre que el contrato le dé.

**Las bases son estas:**
- la revisión previa del analista, `docs/legal/revision-previa-matu-54.md` del repositorio MATU, en especial la sección 3 («Qué lleva cada copia»), la sección 7 (textos) y las decisiones de Jorge D-54-1 a D-54-16;
- `Demo/DISENO.md`, con la regla de MATU-93: **ningún texto bajo 17 px**, 48 px en todo lo que se toca, y el estado nunca solo por color;
- `docs/lenguaje.md`, secciones 8, 13.3, 15, 20, 22, 24, 25, 26 y 29;
- las especificaciones de MATU-55 (`matu-55-donde-entraste.md`, v1.3: la entrada en «Tu cuenta», `LineaIngreso` y el diálogo), MATU-53 (`matu-53-invitar-grupo.md`, v1.3: «Grupo familiar», 5.7 y 5.10), MATU-44 (los bloques de autorización y sus íconos), MATU-45 (las líneas agrupadas por día) y MATU-75 (el índice de `/privacidad`).

**Sin tokens nuevos y sin cambios en `Demo/DISENO.md`.** Todo se arma con `Pagina`, `Volver`, `Nota`, `Etiqueta`, `Boton`, `MensajeError`, `EnlaceEnFrase`, `DialogoConfirmar`, `LineaApertura` (MATU-45) y `LineaIngreso` (MATU-55).

**Cómo se leen las marcas de los textos:**
- **[L n]**: ya está en `lenguaje.md`, sección n. Se copia tal cual.
- **[ANALISTA]**: está en la sección 7 de la revisión previa. Entra a `lenguaje.md`, **sección 35** («Copia de los datos (MATU-54)»), con la aprobación de Jorge. La revisión la llama 34, pero la 34 ya es de MATU-42.
- **[ANALISTA, ajustado]**: el del analista con un cambio, que se explica al lado.
- **[NUEVO]**: no está en ninguna de las dos fuentes. Lo propone esta especificación y lo aprueba Jorge antes de construir.

---

## 1. Para quién y qué

- **Carmen** administra el grupo. Un día María, o el abogado de la familia, le pregunta qué guarda MATU de ella. Carmen tiene que poder mostrarlo en el teléfono, en una sola página que se lee de arriba abajo, y entregar una copia sin escribir un correo.
- **Rodrigo** paga los pedidos. No ve la ficha, pero tiene derecho a ver lo que MATU guarda de **su** cuenta, incluidos sus pagos.
- **La pantalla es el formato que una persona lee** (P9 del analista). El archivo JSON es para otro programa. Por eso todo lo que trae el archivo en los últimos 90 días también se ve en la pantalla, con palabras y no con nombres de campo.
- La pantalla nunca dice «exportar», «auditoría», «registro de accesos», «consentimiento», «sesión», «token» ni «usuario» (revisión previa, 7).

Las rutas son cuatro:

| Ruta | Qué es |
|---|---|
| `/grupo` | Existe. Suma el bloque «Datos de {nombre_pila}» en cada persona (2) |
| `/grupo/datos` | **Nueva.** «Datos de {nombre_pila}» (3) |
| `/cuenta` | Existe. Suma el bloque «Tus datos» (4) |
| `/cuenta/datos` | **Nueva.** «Tus datos» (5) |

**La persona no va en la ruta** (C26). `/grupo/datos` lee a qué persona se refiere desde el estado de la app en memoria (`fijar`), igual que `/grupo/autorizar-ficha`. Si se recarga la página y la persona no está en memoria, se vuelve a `/grupo` con `reemplazar: true`, sin aviso.

**`<title>`, sin nombres** (C26): «Datos guardados · MATU» **[NUEVO]** en `/grupo/datos`, y «Tus datos · MATU» **[NUEVO]** en `/cuenta/datos`. Nunca «Datos de María · MATU»: el título queda en el historial del navegador y en la lista de pestañas.

---

## 2. La entrada en «Grupo familiar» (`/grupo`)

**Dónde va.** Dentro de la sección de cada persona cuidada, **entre los permisos y «Borrar sus datos»**. «Borrar sus datos» sigue siendo lo último de la persona, porque es lo que no se deshace.

```
│ María Soto                         │  h2 de la persona (existe)
│ ┌ Permiso para guardar su ficha ┐  │  bloques de MATU-44 (existen)
│ …                                  │
│ ───────────────────────────────────│  border-t border-linea pt-6
│ Datos de María                     │  h3 text-lg font-bold
│ Todo lo que MATU guarda de María.  │  p text-base max-w-prose
│ Si María o su representante legal  │
│ te lo pide, puedes mostrárselo o   │
│ darle una copia.                   │
│ [ Ver los datos de María ]         │  Boton secundario, self-start
│ ───────────────────────────────────│
│ Borrar sus datos                   │  (existe, MATU-72)
```

| Parte | Texto | Componente |
|---|---|---|
| Título | Datos de {nombre_pila} **[ANALISTA]** | `h3 text-lg font-bold break-words`, el mismo de `BloqueBorrar` |
| Texto, admin y cuidador | Todo lo que MATU guarda de {nombre_pila}. Si {nombre_pila} o su representante legal te lo pide, puedes mostrárselo o darle una copia. **[ANALISTA]** | `p text-base max-w-prose` |
| Botón, admin y cuidador | Ver los datos de {nombre_pila} **[ANALISTA]** | `Boton variante="secundario"`, `self-start`, `angosto:self-stretch`. Fija la persona en memoria y navega a `/grupo/datos`. Su `id` es `datos-{persona.id}`, para devolverle el foco al volver |
| Pagador y observador | Los puede ver quien administra el grupo o quien cuida a {nombre_pila}. **[ANALISTA]** | `p text-base text-tenue`, sin botón. Es el mismo molde de `B.quienPuede` |

- La sección es `section aria-labelledby` con `mt-4 flex flex-col gap-3 border-t border-linea pt-6`, igual que `BloqueBorrar`. **No es una tarjeta:** va sin fondo ni anillo, como «Borrar sus datos».
- **No es macizo.** El único macizo de `/grupo` sigue siendo «Invitar a alguien» (MATU-53, 5.2).
- **Sin persona registrada** (MATU-53, 5.10) no hay sección de persona, así que el bloque no aparece.
- **Al volver** de `/grupo/datos` con «Volver a Grupo familiar», el foco va al botón `datos-{persona.id}` después de que la lista se pinta (el mismo efecto de MATU-55, 3.3, nunca un `setTimeout(0)`). Si ya no está, va al `h1`.

---

## 3. «Datos de {nombre_pila}» (`/grupo/datos`)

**Objetivo, desde Carmen:** «Quiero ver de una vez todo lo que MATU sabe de mi mamá y poder darle una copia si me la pide.»

### 3.1 Jerarquía

1. **Primero:** el `h1` «Datos de {nombre_pila}» y la bajada con la fecha y la hora de la copia. Dice de quién son los datos y de cuándo.
2. **Segundo:** el panel de descarga, con el único botón macizo de la página, «Descargar en un archivo», y lo que el archivo es.
3. **Tercero:** los bloques, en este orden fijo, cada uno con su `h2`:
   1. Sus datos
   2. Autorizaciones
   3. Su ficha
   4. Enlaces de relevo
   5. Sus insumos
   6. Compras anotadas (últimos 90 días)
   7. Avisos de insumos
   8. Sus pedidos (D-54-14)
   9. Quién abrió o editó la ficha

**Acción principal:** «Descargar en un archivo», `principal`, en `turquesa` macizo. Es **el único macizo de la página**. Todo lo demás es lectura, `secundario` («Ver más», «Volver a intentar») o `texto`.

### 3.2 Esquema a 360 px

```
┌────────────────────────────────────┐
│ (cabecera de la app)               │
├────────────────────────────────────┤
│ ‹ Volver a Grupo familiar          │  Volver, 48 px [L 22]
│                                    │
│ Datos de María                     │  h1 titular text-3xl
│ Lo que MATU guarda hoy de María,   │  bajada text-base text-tenue
│ al 12/11/2026 a las 10:14.         │  fecha y hora en dos cifras
│                                    │
│ ┌────────────────────────────────┐ │  div bg-hoja rounded-xl ring-1 ring-linea
│ │ Es un archivo (JSON) que otro  │ │  p text-base (id: ayuda-archivo)
│ │ programa puede leer, para      │ │
│ │ llevar estos datos a otro      │ │
│ │ lugar.                         │ │
│ │ En esta pantalla, los          │ │  p text-base text-tenue
│ │ historiales muestran los       │ │
│ │ últimos 90 días. El archivo    │ │
│ │ trae todo lo guardado.         │ │
│ │ [ Descargar en un archivo ]    │ │  Boton principal, Download
│ │ (región del aviso de 3.6)      │ │
│ └────────────────────────────────┘ │
│                                    │
│ ┌ Índice ────────────────────── ⌄ ┐│  details cerrado (MATU-75), @4xl/main:hidden
│                                    │
│ Sus datos                          │  h2 text-xl font-bold
│ ┌────────────────────────────────┐ │  dl bg-hoja rounded-xl ring-1 ring-linea
│ │ Nombre                         │ │  dt text-base text-tenue
│ │ María Soto Pérez               │ │  dd font-bold break-words
│ │ Le dicen                       │ │
│ │ María                          │ │
│ │ Cuánto apoyo necesita          │ │
│ │ Necesita ayuda en algunas cosas│ │
│ │ Dirección                      │ │
│ │ Los Aromos 123, depto 4,       │ │
│ │ Ñuñoa, Región Metropolitana    │ │
│ │ Referencia: reja verde         │ │
│ │ En MATU desde                  │ │
│ │ 02/11/2026                     │ │
│ └────────────────────────────────┘ │
│ Si algo está mal, escribe a        │  p text-base text-tenue
│ {correo} desde el correo de tu     │  EnlaceEnFrase mailto
│ cuenta.                            │
│                                    │
│ Autorizaciones                     │  h2
│ ┌────────────────────────────────┐ │  ul, una li por autorización
│ │ Permiso para guardar su ficha  │ │  h3 text-lg font-bold
│ │ (✓ Vigente)                    │ │  Etiqueta con el ícono de MATU-44
│ │ La dio Carmen, como su hija,   │ │  text-base
│ │ el 02/11/2026 a las 18:20.     │ │
│ │ Hay que renovarla el           │ │
│ │ 02/11/2027.                    │ │
│ │ Lo que se aceptó: política de  │ │  text-base text-tenue
│ │ privacidad 0.16, declaración   │ │
│ │ 1.0 y aviso 1.0.               │ │
│ ├────────────────────────────────┤ │
│ │ Permiso para calcular insumos  │ │
│ │ …                              │ │
│ └────────────────────────────────┘ │
│                                    │
│ Su ficha                           │  h2
│ ┌────────────────────────────────┐ │
│ │ Su día                         │ │  h3 text-lg font-bold
│ │ Despierta sola a las 8. …      │ │  p whitespace-pre-line max-w-prose
│ │ Lo escribió Carmen el          │ │  text-base text-tenue
│ │ 05/11/2026 a las 21:02.        │ │
│ ├────────────────────────────────┤ │
│ │ Si se altera                   │ │
│ │ …                              │ │
│ └────────────────────────────────┘ │
│  (o la nota de 3.5 si la           │
│   autorización no está vigente)    │
│                                    │
│ Enlaces de relevo · Sus insumos ·  │  (3.4)
│ Compras anotadas · Avisos de       │
│ insumos · Sus pedidos              │
│                                    │
│ Quién abrió o editó la ficha       │  h2
│ Los de los últimos 90 días. Lo     │  p text-base text-tenue
│ anterior va en el archivo.         │
│ Hoy                                │  h3 text-lg font-bold
│ (✎) Editó «Su día»                 │  círculo size-9 + frase font-bold
│     a las 09:40 · Carmen           │  text-base text-tenue
│ (⬇) Pidió una copia de los datos   │
│     a las 10:14 · Carmen           │
│ …                                  │
│ [ Ver más ]                        │  Boton secundario
├────────────────────────────────────┤
│ [Ficha] [Insumos] [Compartir] [Gr.]│  barra fija (telefono:)
└────────────────────────────────────┘
```

**En el modo `angosto`** (320 px con el texto al 200 %):
- las tarjetas pasan a `px-2`;
- el ícono de cada línea del historial va arriba de su texto (`angosto:flex-col angosto:gap-2`, como en MATU-45 y MATU-55);
- «Descargar en un archivo» va a todo el ancho de su panel (`angosto:self-stretch`), con el relleno de su variante (DISENO 3);
- las `Etiqueta` de estado parten su texto y no se salen.

### 3.3 Pantalla ancha (`@4xl/main:` y más)

```
┌──────────────┬───────────────────────────────────────────────────────────────┐
│ (navegación) │ ‹ Volver a Grupo familiar                                     │
│              │ Datos de María                                                │
│              │ Lo que MATU guarda hoy de María, al 12/11/2026 a las 10:14.   │
│              │                                                               │
│              │ ┌ Es un archivo (JSON) que otro programa puede leer… ──────┐  │
│              │ │ En esta pantalla, los historiales muestran los últimos…  │  │
│              │ │ [Descargar en un archivo]                                │  │
│              │ └──────────────────────────────────────────────────────────┘  │
│              │                                                               │
│              │ Índice            │ Sus datos                                 │
│              │ Sus datos         │ ┌ Nombre ─────────── María Soto Pérez ┐   │
│              │ Autorizaciones    │ │ Le dicen ───────── María            │   │
│              │ Su ficha          │ │ …                                   │   │
│              │ Enlaces de relevo │ └─────────────────────────────────────┘   │
│              │ Sus insumos       │ Autorizaciones                            │
│              │ Compras anotadas  │ …                                         │
│              │ Avisos de insumos │                                           │
│              │ Sus pedidos       │                                           │
│              │ Quién abrió o …   │                                           │
└──────────────┴───────────────────────────────────────────────────────────────┘
```

- El panel de descarga va arriba y a lo ancho del contenido, en `max-w-xl`. Arriba de los bloques en los dos anchos, para que el orden de lectura sea el mismo con lector de pantalla y con la vista.
- Debajo, la grilla del índice de `/privacidad` (MATU-75), sin cambios: `grid grid-cols-1 gap-10 @4xl/main:grid-cols-[var(--container-xs)_minmax(0,1fr)] @4xl/main:gap-16`. El índice ancho es `nav sticky top-6 max-h-[calc(100dvh-3rem)] overflow-y-auto [scrollbar-width:thin]` (DISENO 3, columnas pegajosas). En el teléfono es el `details` cerrado de MATU-75.
- El índice lista solo los bloques que se ven. Si «Sus pedidos» se omite (capa 3 quitada) o los bloques de insumos no se muestran (3.5), no aparecen en el índice.
- Cada bloque es una `section aria-labelledby` con `min-w-0` y `scroll-mt-6`. Los textos largos no pasan de `max-w-prose`.
- En «Sus datos», desde `@3xl/main:`, cada fila del `dl` va en `grid grid-cols-[12rem_minmax(0,1fr)] gap-x-6`: es la columna de etiquetas de 12 rem de Grupo familiar (DISENO 3, medidas fijas). No es un token nuevo.
- Los botones van al ancho de su texto. A 1920 px, la página sigue el ancho máximo del `main` de la app.

### 3.4 Los bloques

Reglas comunes:
- cada bloque es una `section` con un `h2 text-xl font-bold`, y su contenido en una superficie `bg-hoja rounded-xl ring-1 ring-linea px-4 angosto:px-2`, con `divide-y divide-linea` entre filas;
- las fechas van como «{DD/MM/AAAA} a las {HH:MM}» en dos `cifras` dentro de un `<time dateTime>`. **En los bloques, nunca «hoy» ni «ayer»:** es una copia, y la fecha absoluta se lee igual mañana. Solo los grupos por día de los historiales (3.4.9) usan «Hoy», «Ayer» y «El {día}», como Quién la vio;
- el dinero, `$69.000` en `cifras`, siempre con IVA incluido y **nunca una línea de IVA** (D-54-14);
- quien salió del grupo se nombra «Alguien que ya no está en el grupo», o «alguien que ya no está en el grupo» dentro de una oración (MATU-53, 5.7), con el mismo peso y color del nombre al que reemplaza;
- **un bloque sin filas** muestra una frase en `p text-base text-tenue`, sin ícono grande ni botón: es una copia, no hay nada que empezar (tabla de 3.6).

#### 3.4.1 Sus datos

Es un `dl` como el de «Tu cuenta», con `dt text-base text-tenue` y `dd font-bold break-words`.

| `dt` | `dd` |
|---|---|
| Nombre **[NUEVO]** | El nombre completo |
| Le dicen **[NUEVO, de «¿Cómo le dicen?», L 25.3]** | El nombre de pila |
| Cuánto apoyo necesita **[NUEVO, de L 25.3]** | La opción de L 25.3, tal como se eligió en el alta |
| Dirección **[NUEVO]** | «{calle} {número}, {depto}, {comuna}, {región}» y, en otra línea, «Referencia: {referencia}» **[NUEVO]**. Sin dirección: «Sin dirección.» **[NUEVO]** en `font-normal text-tenue` |
| En MATU desde **[NUEVO]** | La fecha de alta |

Bajo el `dl`, siempre: «Si algo está mal, escribe a {correo} desde el correo de tu cuenta.» **[NUEVO]**, en `p text-base text-tenue max-w-prose`, con el correo en `EnlaceEnFrase mailto:` y `[overflow-wrap:anywhere]`. `{correo}` es `correo_contacto` de `GET /v1/politica`, como en MATU-55 2.5. Sin correo configurado, el párrafo no se muestra. Cubre la rectificación mientras no exista MATU-91.

#### 3.4.2 Autorizaciones

Una `ul`, con una `li` por autorización, en el orden del servidor. Cada `li`, en `flex flex-col items-start gap-2 py-4`:

| Parte | Texto | Componente |
|---|---|---|
| Título | El título del bloque de MATU-44: «Permiso para guardar su ficha», «Permiso para calcular sus insumos» o el de pedidos **[L 22]** | `h3 text-lg font-bold` |
| Estado | La palabra y el ícono de MATU-44 (`ShieldCheck` vigente, `Hourglass` por renovar o en pausa, `ShieldOff` retirada, `ShieldQuestion` sin autorizar) **[L 22]** | `Etiqueta`, en `text-base` |
| Quién y cuándo | La dio {nombre}, como {calidad}, el {fecha} a las {hora}. **[NUEVO]** `{calidad}` es la palabra de L 25.4 en minúscula | `p text-base` |
| Renovación | Hay que renovarla el {fecha}. **[NUEVO]** Solo si está vigente o por renovar | `p text-base` |
| Retiro | La retiró {nombre} el {fecha} a las {hora}. **[NUEVO]** Y, si hay motivo, en otra línea: «Motivo: {motivo}» **[NUEVO]** | `p text-base` |
| Lo aceptado | Lo que se aceptó: política de privacidad {versión}, declaración {versión} y aviso {versión}. **[NUEVO]** Con las versiones en `cifras` | `p text-base text-tenue` |
| Representante legal | Hay una referencia al documento del representante legal. Si la necesitas, pídela a {correo}. **[ANALISTA, ajustado: `{correo}` sale de la política, no va escrito]** Solo si existe | `Nota tono="rocio"` con `FileText`, el correo en `EnlaceEnFrase` |

El estado no depende del color: lleva la palabra, el ícono y, en la retirada, la frase del retiro.

#### 3.4.3 Su ficha

**Con la autorización de la ficha vigente:** una `ul` con una `li` por campo y por sección adicional, en el orden de la ficha.
- `h3 text-lg font-bold`: el nombre del campo o de la sección **[L 14.1]**;
- el texto en `p text-base whitespace-pre-line break-words max-w-prose`, **tal cual se escribió**, con los nombres y teléfonos de «A quién llamar» (D-54-4). No se cambia ningún carácter;
- «Lo escribió {nombre} el {fecha} a las {hora}.» **[NUEVO]**, en `text-base text-tenue`;
- un campo sin texto dice «Sin escribir.» **[NUEVO]** en `text-tenue`, sin la línea del autor.

**No se dibuja la hoja con el imán.** La hoja es la ficha para un relevo. Esto es una copia de datos, y verse como la hoja la confundiría con lo que se comparte (C10).

**Retirada o en pausa:** la nota de 3.5, en lugar de la lista.

#### 3.4.4 Enlaces de relevo

Bajo el `h2`, una sola vez: «No incluimos el teléfono de los relevos.» **[ANALISTA, ajustado: el texto era «No incluimos su teléfono.», que sin un relevo al lado no dice de quién]**, en `p text-base text-tenue`.

Una `ul` con una `li` por enlace, del más nuevo al más viejo:

| Parte | Texto |
|---|---|
| Para quién | {nombre_relevo}, en `text-lg font-bold break-words` |
| Por qué | El motivo, tal como se escribió, en `text-base` |
| Qué ve | Ve: {secciones}. **[NUEVO]** Los nombres de L 14.1, separados por coma y «y» |
| Quién y cuándo | Lo creó {nombre_pila} el {fecha} a las {hora}. **[NUEVO]** |
| Hasta cuándo | Vence el {fecha} a las {hora}. · Venció el {fecha} a las {hora}. · Lo cortó {nombre_pila} el {fecha} a las {hora}. **[NUEVO]** Con la forma de L 9.1 cuando ya existe |
| Uso | Se abrió {n} veces. La última, el {fecha} a las {hora}. · Se abrió una vez, el {fecha} a las {hora}. · No se ha abierto. **[NUEVO]** |
| Aperturas | Un `ol` de `LineaApertura` (MATU-45) con `notas={false}`, sin acciones, con las aperturas de los últimos 90 días. Si hay más de 5, se ven 5 y «Ver más» (3.4.10) |

#### 3.4.5 Sus insumos

**Con la autorización de insumos vigente:** una `ul` con una `li` por insumo.
- el nombre del producto o el escrito, en `text-lg font-bold break-words`;
- «Usa {cantidad} {unidad} cada {n} días.» **[NUEVO]** con la unidad de L 21;
- «Quedaban {cantidad} el {fecha}.» **[NUEVO]**;
- «Avisa {n} días antes.» **[NUEVO]**;
- «{n} por envase.» **[NUEVO]**, solo si se declaró;
- si ya no se sigue: `Etiqueta` neutra con `Circle` y «Ya no se sigue» **[NUEVO]**. Si se sigue, no lleva etiqueta: es lo normal.

Si el frontend ya tiene una frase de L 18 o L 21 que dice lo mismo, usa esa y lo avisa en su entrega.

**Retirada o en pausa:** la nota de 3.5.

#### 3.4.6 Compras anotadas (últimos 90 días)

El título es **[ANALISTA]** y ya dice el plazo, así que no lleva la frase de los 90 días. Un `ol` del más nuevo al más viejo, una `li` por compra:
- «{cantidad} {unidad} de {producto}» en `font-bold`;
- «El {fecha} a las {hora} · Anotó {nombre}» **[NUEVO]** en `text-base text-tenue`.

Más de 10: «Ver más» (3.4.10).

#### 3.4.7 Avisos de insumos

Bajo el `h2`, la frase de los 90 días (3.4.9). Un `ol` con una `li` por aviso:
- «{producto}: se acaba el {fecha prevista}.» **[NUEVO]** en `font-bold`;
- el estado en palabra, con el texto de L 17 para ese estado, en `text-base`;
- las fechas del aviso en `text-base text-tenue`.

Sin colores de urgencia (● ◐ ○): esto es lo que pasó, no lo que hay que hacer hoy.

#### 3.4.8 Sus pedidos (D-54-14 y D-54-15)

**Con la capa 3 quitada, el bloque no existe** y tampoco sale en el índice. Con la capa apagada o la autorización de pedidos retirada, el bloque se ve igual.

Bajo el `h2`, la frase de los 90 días. Una `ul` con una `li` por pedido, del más nuevo al más viejo:

```
│ Pedido del 08/11/2026 a las 11:20  │  h3 text-lg font-bold
│ (◐ Entregado)                      │  Etiqueta con la palabra de L 27
│ Pañal adulto M x30 × 2   $27.980   │  dl de productos, precio en cifras
│ Toallitas x80 × 1         $5.290   │
│ Envío                     $3.990   │
│ Total                    $37.260   │  font-bold
│ Lo pagó Rodrigo el 08/11/2026 a    │  text-base
│ las 11:24.                         │
│ Cobrado: $37.260 · Devuelto: $5.290│  text-base, solo si hubo devolución
│ A: Los Aromos 123, depto 4, Ñuñoa  │  text-base text-tenue
```

| Parte | Texto |
|---|---|
| Título | Pedido del {fecha} a las {hora} **[NUEVO]** |
| Estado | La palabra del pedido de L 27, con su figura, en `Etiqueta` |
| Productos | {producto} × {cantidad} y su precio, en un `dl` de dos columnas (`grid grid-cols-[minmax(0,1fr)_auto] gap-x-4`). El precio va alineado a la derecha y en `cifras`. En el modo `angosto`, el precio baja bajo el producto (`angosto:grid-cols-1`) |
| Envío | Envío **[L 27]** y su monto |
| Total | Total **[L 27]**, en `font-bold`. Nunca «IVA» ni «Neto» |
| Pago | Lo pagó {nombre} el {fecha} a las {hora}. **[NUEVO]** · Sin pagar. **[NUEVO]** |
| Lo cobrado | Cobrado: {monto}. **[NUEVO]** Y, si hubo anulación parcial: « · Devuelto: {monto}» **[NUEVO]** |
| Dirección | A: {dirección copiada en el pedido} **[NUEVO]**, en `text-tenue` |

**Nunca** el teléfono de contacto del pedido, ni el tipo de tarjeta, las cuotas o los dígitos, ni la orden, el token o el código de autorización (D-54-4 y D-54-14). Los datos de la tarjeta van solo en «Tus datos» de quien pagó (5.4).

#### 3.4.9 Quién abrió o editó la ficha

- Bajo el `h2`, la frase de los 90 días: «Los de los últimos 90 días. Lo anterior va en el archivo.» **[NUEVO]**, en `p text-base text-tenue`. La misma frase va bajo «Avisos de insumos», «Sus pedidos», «Últimos ingresos» y «Avisos que te enviamos». Si el servidor dice que no hay nada anterior, se queda solo «Los de los últimos 90 días.»;
- **solo para quien cuida** (no admin), bajo esa frase: «Aquí ves solo lo que hiciste tú. La lista completa la ve quien administra el grupo.» **[ANALISTA]**, en `Nota tono="rocio"` con `Info`. Así la lista corta no se lee como si nadie más hubiera hecho nada (D-54-6);
- las líneas son el patrón de `LineaIngreso` (MATU-55, 2.5): `ol`, un `li` por línea, el ícono en un círculo `size-9 rounded-full bg-rocio text-turquesa` y `aria-hidden`, la frase en `font-bold` y la cola «a las {HH:MM} · {nombre}» **[ANALISTA]** en `text-base text-tenue tabular-nums`;
- se agrupan por día con un `h3 text-lg font-bold`: «Hoy», «Ayer», «El {día de la semana}» y «El DD/MM/AAAA», con las reglas de MATU-45;
- el orden es el del servidor, del más nuevo al más viejo. El cliente no reordena.

| Acción | Frase | Ícono lucide |
|---|---|---|
| Abrir la ficha | Abrió la ficha **[ANALISTA]** (ver la pregunta P6) | `Eye` |
| Editar un campo o una sección | Editó «{sección}» **[ANALISTA]** | `PencilLine` |
| Quitar una sección | Quitó «{sección}» **[ANALISTA]** | `Eraser` |
| La copia | Pidió una copia de los datos **[ANALISTA]** | `Download` |
| Dar una autorización | Dio el {permiso} **[NUEVO]**, con el título de L 22 en minúscula | `ShieldCheck` |
| Retirar una autorización | Retiró el {permiso} **[NUEVO]** | `ShieldOff` |
| Crear un enlace | Creó un enlace para {nombre_relevo} **[NUEVO]** | `Link` |
| Cortar un enlace | Cortó el enlace de {nombre_relevo} **[NUEVO]** | `Unlink` |
| Agregar, cambiar o quitar un insumo | Agregó {producto} · Cambió {producto} · Quitó {producto} **[NUEVO]** | `Package` |
| Anotar una compra | Anotó una compra de {producto} **[NUEVO]** | `ShoppingBag` |
| Cambiar la dirección | Cambió la dirección **[NUEVO]** | `MapPin` |
| Una acción que el cliente no conoce | No se muestra, y la pantalla no se rompe | — |

La lista cerrada de acciones la fija el contrato (P2). Las de esta tabla que el contrato no traiga, no se construyen.

#### 3.4.10 «Ver más»

Todo historial muestra primero **20 líneas** (5 en las aperturas de cada enlace, 10 en las compras) y, si hay más dentro de los 90 días, `Boton variante="secundario"` «Ver más» **[aprobado 03-11, `INSUMOS.verMas`]**, al ancho de su texto, al final de su lista.
- Al tocarlo, se suman 20 más (o 5, o 10). **El foco va a la primera línea nueva**, que lleva `tabIndex={-1}`, y se anuncia «Se agregaron {n} líneas.» **[L 15]** por `role="status"`, como en Quién la vio.
- Cuando ya no quedan, el botón desaparece. Nunca queda un «Ver más» que no hace nada.
- Si los 90 días están en memoria (P1, opción A), «Ver más» no pide nada a la API y no tiene estado de carga.

### 3.5 Autorización retirada o en pausa (D-54-5)

En lugar del contenido de «Su ficha» o de «Sus insumos» va una `Nota`, con el estado y, si la hay, la fecha de borrado. Es el «bloque que reemplaza a la ficha» que el analista dejó para el diseñador.

```
│ Su ficha                           │  h2
│ ┌┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┐ │  Nota tono="rocio" borde, borde punteado
│ ┆ ⛨ La autorización de la ficha  ┆ │  ShieldOff size-5 text-turquesa
│ ┆   está retirada. Lo escrito    ┆ │
│ ┆   sigue guardado sin que nadie ┆ │
│ ┆   lo pueda leer, y se borra el ┆ │
│ ┆   10/02/2027.                  ┆ │  fecha en cifras
│ └┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘ │
```

| Caso | Texto | Ícono |
|---|---|---|
| Ficha retirada | La autorización de la ficha está retirada. Lo escrito sigue guardado sin que nadie lo pueda leer, y se borra el {DD/MM/AAAA}. **[ANALISTA]** | `ShieldOff` |
| Ficha en pausa | La ficha está en pausa porque falta renovar la autorización. Cuando se renueve, vuelve a aparecer aquí. **[ANALISTA]** | `Hourglass` |
| Insumos retirados | La autorización de los insumos está retirada. Lo anotado se borra el {DD/MM/AAAA}. **[ANALISTA]** | `ShieldOff` |
| Insumos en pausa | Los insumos están en pausa porque falta renovar la autorización. Cuando se renueve, vuelven a aparecer aquí. **[NUEVO, el molde de la ficha en pausa]** | `Hourglass` |
| Clave ya destruida (después de los 90 días) | La autorización de la ficha está retirada y lo escrito ya se borró. **[NUEVO]** Igual con «de los insumos» y «lo anotado» | `ShieldOff` |

- `tono="rocio"`, no `atenta` ni `pronto`: no se perdió nada sin aviso y no hay nada que hacer en esta pantalla. Es el tono de «Se retiró la autorización de la ficha» en Enlaces (MATU-44).
- La retirada lleva el **borde punteado** de MATU-44 (`border-2 border-dashed border-borde`), y la pausa no. El estado lo dicen la frase y la forma, no el color.
- **Con los insumos retirados o en pausa**, «Compras anotadas» y «Avisos de insumos» no se muestran, porque son lo anotado (C3), y salen del índice. La nota de «Sus insumos» vale por los tres (pregunta P4).
- «Enlaces de relevo» y «Quién abrió o editó la ficha» se ven igual: no traen texto de la ficha.

### 3.6 Estados de la página

| Estado | Qué se ve | Foco y anuncio |
|---|---|---|
| Cargando | El `Volver` y el `h1`, que ya se puede armar con el nombre de pila que está en memoria, sin la bajada (la hora la da la respuesta). Debajo, «Cargando…» **[L 26]** en `p role="status"` después de la demora de `useDemora`. Sin esqueletos (DISENO 6) | En el `h1` desde el principio |
| Listo | Lo de 3.2 | En el `h1` (`tabIndex={-1}`) |
| Error o sin red | Bajo el `Volver`, `Nota tono="pronto" rol="alert"` con `WifiOff`: «No pudimos traer los datos. Revisa tu conexión y vuelve a intentarlo.» **[ANALISTA]** y `Boton variante="secundario"` «Volver a intentar» **[L 26]**. Sin panel de descarga | A la nota (`enfocable`) |
| 404 | La persona ya no es accesible: se borró, se cambió el rol a pagador u observador, o salió del grupo. `Nota tono="rocio"` con `Lock` y el 404 general **[L 8]**, igual que Grupo familiar (MATU-44), y «Volver a Grupo familiar». Al volver, Grupo familiar se vuelve a pedir | A la nota |
| 429 | `Nota tono="atenta" rol="alert"` con `Clock`: «Ya pediste los datos varias veces. Vuelve a intentarlo en una hora.» **[ANALISTA]**. **Sin «Volver a intentar»**: daría otro 429. Solo «Volver a Grupo familiar» | A la nota |
| 401 | Lo resuelve el cliente de la app | — |
| 412 | **No aplica:** es una lectura | — |
| Un bloque vacío | Una frase en `text-base text-tenue` bajo su `h2`: «Todavía no hay enlaces de relevo.» · «Todavía no hay insumos.» · «No hay compras anotadas en los últimos 90 días.» · «No hay avisos en los últimos 90 días.» · «No hay pedidos en los últimos 90 días.» · «No hay cambios en los últimos 90 días.» **[NUEVO]**. Una autorización que nunca se dio aparece con su estado «sin autorizar» de L 22 | — |
| Al volver a la página | Se vuelve a pedir. **Nada se guarda en el navegador** (C26) | — |

**El 429 va en `atenta` y no en `pronto`:** no se perdió nada, solo hay que esperar (DISENO 6: `pronto` solo si se perdió algo).

### 3.7 Descargar

**El panel** (3.2) lleva, en este orden:
- «Es un archivo (JSON) que otro programa puede leer, para llevar estos datos a otro lugar.» **[ANALISTA]**, en `p text-base max-w-prose`, con `id` para el `aria-describedby` del botón;
- «En esta pantalla, los historiales muestran los últimos 90 días. El archivo trae todo lo guardado.» **[NUEVO]** (D-54-9), en `p text-base text-tenue max-w-prose`;
- `Boton variante="principal"` con el ícono `Download` y «Descargar en un archivo» **[ANALISTA]**, `aria-describedby` en la ayuda, `angosto:self-stretch`.

Tocarlo abre el diálogo «Antes de descargar». **Nunca descarga sin el diálogo** (C11).

#### El diálogo «Antes de descargar»

Es `DialogoConfirmar` (MATU-55, 2.6): `<dialog>` modal con `showModal()`, `aria-labelledby` en el título y `aria-describedby` en el texto, el foco inicial en el título con `tabIndex={-1}`, una región de error vacía con `role="alert"` y sin animación.

```
┌────────────────────────────────────┐
│ Antes de descargar                 │  h2 text-xl font-bold, foco inicial
│                                    │
│ El archivo trae todo lo de esta    │  p text-base leading-relaxed
│ pantalla, también lo escrito en la │  max-w-prose
│ ficha y los nombres y teléfonos de │
│ «A quién llamar». Queda en tu      │
│ teléfono o computador, fuera de    │
│ MATU: no vence, no se puede cortar │
│ y MATU no lo puede borrar.         │
│                                    │
│ No lo uses para compartir la ficha │  p text-base font-bold
│ con un relevo: para eso está el    │
│ enlace con PIN.                    │
│                                    │
│ [ Descargar ]                      │  Boton principal, Download
│ No descargar                       │  Boton texto
└────────────────────────────────────┘
```

| Parte | Texto |
|---|---|
| Título | Antes de descargar **[ANALISTA]** |
| Texto | El archivo trae todo lo de esta pantalla, también lo escrito en la ficha y los nombres y teléfonos de «A quién llamar». Queda en tu teléfono o computador, fuera de MATU: no vence, no se puede cortar y MATU no lo puede borrar. **[ANALISTA, ajustado: «en tu teléfono» pasa a «en tu teléfono o computador», porque también se descarga desde un computador]** |
| Lo que importa | No lo uses para compartir la ficha con un relevo: para eso está el enlace con PIN. **[ANALISTA]**, en un párrafo propio y en `font-bold`, porque es lo que la persona no espera |
| Sin la ficha | Si la ficha no está vigente (3.5), la primera oración cambia a «El archivo trae todo lo de esta pantalla.» **[NUEVO]**: no puede prometer lo escrito en la ficha si no va |
| Confirmar | Descargar **[ANALISTA]**, `principal` con `Download` |
| Arrepentirse | No descargar **[ANALISTA]**, `texto` |

**Estados.**

| Estado | Qué se ve | Foco |
|---|---|---|
| Abierto | Lo de arriba | En el título |
| Descargando | Con la opción A de P1, no hay espera: el archivo sale de la memoria. Con la opción B (un GET aparte para el archivo), el botón dice «Preparando el archivo…» **[NUEVO]** con `aria-busy`, y Esc no cancela | Se queda en el botón |
| Entregado | El diálogo se cierra. En el panel, bajo el botón, `Nota tono="ok" enfocable rol="status"`: «Te entregamos el archivo. Búscalo en tus descargas.» **[ANALISTA, ajustado: sin «de tu teléfono», por el computador]**. Se borra al volver a abrir el diálogo | En la nota |
| Error o sin red (opción B) | El diálogo sigue abierto, y en su región `role="alert"`, `MensajeError`: «No pudimos preparar el archivo. Revisa tu conexión y vuelve a intentarlo.» **[NUEVO]** | En el botón «Descargar» |
| 429 (opción B) | El diálogo se cierra y el panel muestra la nota del 429 de 3.6 en lugar de la de éxito. El botón sigue, porque los datos de la pantalla siguen siendo válidos | En la nota |
| No descargar o Esc | Se cierra sin hacer nada | Vuelve a «Descargar en un archivo» |

**Por qué «Te entregamos» y no «Descargaste».** DISENO 4.6 pide el mismo verbo en el botón y en la confirmación. Aquí no se cumple a propósito: el navegador no confirma que el archivo se guardó (C20), y «Descargaste el archivo» podría ser falso. «Te entregamos» dice lo único que MATU sabe.

**Cómo se guarda** (C8 y C9, para el frontend): un `Blob` con los bytes tal como llegaron, `URL.createObjectURL`, un `<a download="matu-datos-AAAA-MM-DD.json">` que no se agrega a la vista, y `URL.revokeObjectURL` de inmediato. El nombre nunca lleva el nombre de la persona.

### 3.8 Impresión

No se agrega nada. La regla global de `web/src/index.css` ya imprime «Esta pantalla no se imprime.» en toda pantalla sin `data-impresion` (C7). **Esta pantalla no lleva `data-impresion`.**

---

## 4. La entrada en «Tu cuenta» (`/cuenta`)

**Dónde va.** Una tarjeta nueva, **justo después de «Dónde entraste»** y antes del bloque de avisos. Las dos hablan de lo que MATU guarda de la cuenta.

```
│ ┌────────────────────────────────┐ │  section bg-hoja rounded-xl ring-1 ring-linea
│ │ Dónde entraste                 │ │  (existe, MATU-55)
│ │ [ Ver dónde entraste ]         │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │  section, la misma forma
│ │ Tus datos                      │ │  h2 text-xl font-bold leading-snug
│ │ Ver y descargar lo que MATU    │ │  p text-base text-tenue
│ │ guarda de tu cuenta.           │ │
│ │ [ Ver tus datos ]              │ │  Boton secundario
│ └────────────────────────────────┘ │
│ ┌ Avisos cuando un insumo… ──────┐ │  (existe)
```

| Parte | Texto | Componente |
|---|---|---|
| Título | Tus datos **[ANALISTA]** | `h2 text-xl font-bold leading-snug` |
| Bajada | Ver y descargar lo que MATU guarda de tu cuenta. **[ANALISTA]** | `p max-w-prose text-base text-tenue` |
| Botón | Ver tus datos **[NUEVO]** | `Boton variante="secundario"`, `angosto:self-stretch`, navega a `/cuenta/datos`. `id="ver-tus-datos"`, para devolverle el foco |

- La tarjeta copia las clases de la de «Dónde entraste»: `mt-6 flex max-w-xl flex-col items-start gap-3 rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea`.
- **No pide nada a la API**, como «Dónde entraste» (MATU-55, 3.5).
- **«Cómo pedir» cambia** (ajuste de L 29, revisión previa 7): «Para cambiar tu nombre o tu correo, o eliminar tu cuenta, escribe a {correo} desde el correo de tu cuenta. Para ver o descargar tus datos, entra a «Tus datos».» **[ANALISTA]**. «Tus datos», al final, es texto y no enlace: el botón está más arriba en la misma página.
- **No hay ningún `turquesa` macizo en «Tu cuenta»** (MATU-55, criterio 1). Sigue así.

---

## 5. «Tus datos» (`/cuenta/datos`)

**Objetivo, desde Rodrigo:** «Quiero ver qué guarda MATU de mí, también de lo que pagué, y llevármelo si lo necesito.»

### 5.1 Jerarquía

1. El `h1` «Tus datos» y su bajada con la fecha y la hora.
2. El panel de descarga, igual que en 3.7, con el único macizo.
3. La nota que manda a «Grupo familiar» para los datos de las personas cuidadas.
4. Los bloques, en este orden:
   1. Tu cuenta
   2. Política de privacidad
   3. Tus grupos
   4. Tus teléfonos y computadores
   5. Últimos ingresos
   6. Tus avisos
   7. Avisos que te enviamos
   8. Tus pagos (D-54-16), solo si pagaste algún pedido

### 5.2 Esquema a 360 px

```
┌────────────────────────────────────┐
│ ‹ Volver a tu cuenta               │  Volver [MATU-55]
│                                    │
│ Tus datos                          │  h1 titular text-3xl
│ Lo que MATU guarda hoy de tu       │  bajada text-base text-tenue
│ cuenta, al 12/11/2026 a las 10:14. │
│                                    │
│ ┌ panel de descarga (3.7) ───────┐ │
│                                    │
│ ⓘ Lo que guardamos de las personas │  Nota tono="rocio" con Info
│   que cuidas lo ves en Grupo       │
│   familiar.                        │
│   Ir a Grupo familiar              │  Boton texto → /grupo
│                                    │
│ ┌ Índice ────────────────────── ⌄ ┐│  details (MATU-75)
│                                    │
│ Tu cuenta                          │  h2
│ ┌────────────────────────────────┐ │  dl, como «Tu cuenta»
│ │ Tu nombre · Carmen Soto        │ │
│ │ Tu correo · carmen@ejemplo.cl  │ │
│ │ Tu celular · +56 9 •••• ••37   │ │  enmascarado (P3)
│ │   (✓ Confirmado)               │ │  Etiqueta de MATU-57
│ │   Completo en el archivo.      │ │  text-base text-tenue
│ │ Los códigos te llegan · Por SMS│ │
│ └────────────────────────────────┘ │
│                                    │
│ Política de privacidad             │  h2
│ Aceptaste la versión 0.16 el       │  p text-base
│ 02/11/2026 a las 18:15.            │
│ Huella: 3f9a…c21b                  │  text-base text-tenue, break-all
│                                    │
│ Tus grupos                         │  h2
│ • Familia Soto · Administra el     │  ul, rol en palabra [MATU-53 5.3]
│   grupo                            │
│                                    │
│ Tus teléfonos y computadores       │  h2, FilaDispositivo de MATU-55
│ Últimos ingresos                   │  h2, LineaIngreso de MATU-55
│ Tus avisos                         │  h2
│ Por correo: sí · En tus teléfonos: │
│ no                                 │
│ Avisos que te enviamos             │  h2
│ ⓘ En el piloto los avisos se       │  Nota tono="atenta" con Info
│   prueban sin enviarse: aparecen   │
│   aquí, pero no te llegaron.       │
│ (◌) 10/11/2026 a las 08:00 · Por   │
│     correo · En el piloto no salió │
│ Tus pagos                          │  h2, solo si pagaste
└────────────────────────────────────┘
```

**Pantalla ancha:** la misma composición de 3.3, con el panel arriba y la grilla del índice debajo.

### 5.3 Los bloques

| Bloque | Contenido | Componentes y textos |
|---|---|---|
| **Tu cuenta** | Nombre, correo, celular, si está confirmado y el canal de los códigos | `dl` como el de «Tu cuenta», con `dt text-base text-tenue`. Rótulos: «Tu nombre» **[NUEVO]**, «Tu correo» y «Tu celular» **[L 29, los de «Tu cuenta»]**, «Los códigos te llegan» **[NUEVO]** con «Por SMS» o «Por WhatsApp» **[NUEVO, con las palabras de L 19]**. El celular, la `Etiqueta` de confirmado y su forma, como en «Tu cuenta» (MATU-57). Bajo el celular, «Completo en el archivo.» **[NUEVO]** en `text-tenue` (P3) |
| **Política de privacidad** | Versión, fecha y huella | «Aceptaste la versión {versión} el {fecha} a las {hora}.» **[NUEVO]**. «Huella: {huella}» **[NUEVO]** en `text-base text-tenue` con `break-all`: es una cadena sin palabras, y aquí sí se puede partir en cualquier punto. Sin aceptación registrada: «No hay una aceptación registrada.» **[NUEVO]** |
| **Tus grupos** | Nombre y rol en cada uno | `ul`, una `li` por grupo: el nombre en `font-bold break-words` y el rol en palabra, «Administra el grupo» · «Cuida» · «Paga» · «Se informa» **[MATU-53, 5.3]**. Para el pagador, además «Puede ver la ficha» o «No ve la ficha» con `Eye` o `EyeOff` **[MATU-53, 5.3]** |
| **Tus teléfonos y computadores** | Nombre general, creación y último uso | La `ul` de `FilaDispositivo` (MATU-55, 2.4), **sin acciones**: aquí no se cierra nada. Al pie, `Boton variante="texto"` «Ver dónde entraste» **[MATU-55, 3.5]** a `/cuenta/donde-entraste`, para quien quiera cerrar alguno. La creación se suma a cada fila: «Desde el {fecha}.» **[NUEVO]** |
| **Últimos ingresos** | Los eventos de seguridad de la 0024 (D1 de MATU-55) | La frase de los 90 días (3.4.9) y el `ol` de `LineaIngreso` (MATU-55, 2.5), agrupado por día, con «Ver más» (3.4.10). **Sin** la ayuda «¿No reconoces un ingreso?»: vive en «Dónde entraste» |
| **Tus avisos** | La preferencia | «Por correo: sí» o «no» y «En tus teléfonos: sí» o «no» **[NUEVO, con los nombres de L 20 ajustados por MATU-55]**, en un `dl`. Al pie, «Puedes cambiarlos en Tu cuenta.» **[NUEVO]** |
| **Avisos que te enviamos** | Fecha, canal y estado | Ver 5.4 |
| **Tus pagos** | D-54-16 | Ver 5.4 |

**Nunca** la contraseña, el doble factor, la huella del correo, nada de las sesiones ni nada de una persona cuidada. «Tus datos» no nombra a María en ningún lugar, ni siquiera en «Tus pagos» (pregunta P5).

### 5.4 «Avisos que te enviamos» y «Tus pagos»

**Avisos que te enviamos.**
- Bajo el `h2`, la frase de los 90 días (3.4.9).
- Mientras haya algún aviso simulado, arriba de la lista y **una sola vez**: `Nota tono="atenta"` con `Info`, «En el piloto los avisos se prueban sin enviarse: aparecen aquí, pero no te llegaron.» **[ANALISTA]**. Es el rótulo del piloto de DISENO 3, y el mismo tono de la nota de avisos de «Tu cuenta».
- Un `ol` con una `li` por aviso: «{DD/MM/AAAA} a las {HH:MM} · {canal} · {estado}» **[ANALISTA]**, en `text-base tabular-nums`, con el ícono del estado delante, en `size-5 shrink-0 text-tenue aria-hidden`.
- **Nunca** el texto del aviso ni a dónde se envió (C16).

| Estado | Palabra | Ícono |
|---|---|---|
| Salió | Salió **[ANALISTA]** | `Check` |
| No salió | No salió **[ANALISTA]** | `X` |
| Simulado en el piloto | En el piloto no salió **[ANALISTA, D-54-11]** | `CircleDashed` |

| Canal | Palabra |
|---|---|
| Correo | Por correo **[L 20]** |
| Push | En tus teléfonos **[MATU-55, ajuste de L 20]** |

- Ninguna línea va en `pronto` ni en `ok`: el ícono y el texto van en `tenue` y `tinta`. «No salió» no es una alarma, y «Salió» no es un logro. El estado lo dice la palabra, y la forma del ícono lo acompaña.
- **«Salió» no se usa nunca para un aviso simulado** (D-54-11). La pantalla no lo deduce: usa el estado que manda el servidor (P2).

**Tus pagos** (D-54-16), solo si la cuenta pagó algún pedido. Una `ul` con una `li` por pago:

```
│ Pago del 08/11/2026 a las 11:24    │  h3 text-lg font-bold
│ $37.260 en Familia Soto            │  text-base, monto en cifras
│ Tarjeta de crédito terminada en    │  text-base
│ 4242 · 3 cuotas                    │
│ Devuelto: $5.290                   │  solo si hubo anulación parcial
│ Aceptaste las condiciones de       │  text-base text-tenue
│ compra {versión} el 08/11/2026.    │
```

| Parte | Texto |
|---|---|
| Título | Pago del {fecha} a las {hora} **[NUEVO]** |
| Monto | {monto} en {grupo} **[NUEVO]**. El total con IVA incluido, sin línea de IVA |
| Tarjeta | Tarjeta de crédito terminada en {últimos 4} · {n} cuotas · Tarjeta de débito terminada en {últimos 4} **[NUEVO]**. «Sin cuotas» si son 0 o 1 **[NUEVO]**. Los cuatro dígitos en `cifras` |
| Devolución | Devuelto: {monto} **[NUEVO]** |
| Condiciones | Aceptaste las condiciones de compra {versión} el {fecha}. **[NUEVO]**, con el nombre de las condiciones de L 27 |

**Nunca** el token, la orden, la sesión de pago ni el código de autorización (D-54-16).

### 5.5 Estados

Los de 3.6, con estos cambios:
- el error dice lo mismo: «No pudimos traer los datos. Revisa tu conexión y vuelve a intentarlo.» **[ANALISTA]**;
- **no hay 404 por persona**. Un 404 solo puede ser un defecto y se trata como el error;
- el 429 es el mismo texto, porque el límite es por cuenta y vale para las dos copias;
- **sin autorizaciones**: «Tus datos» no tiene bloques que dependan de una autorización;
- bloques vacíos: «No hay ingresos en los últimos 90 días.» **[MATU-55, 2.7]** y «No hay avisos en los últimos 90 días.» **[NUEVO]**. Sin pagos, el bloque «Tus pagos» no aparece.

El diálogo «Antes de descargar» es el de 3.7, con este texto: «El archivo trae tu correo y tu celular completos. Queda en tu teléfono o computador, fuera de MATU.» **[ANALISTA, ajustado: «o computador», como en 3.7]**. No lleva la oración sobre el relevo, porque «Tus datos» no trae la ficha.

---

## 6. Tokens y componentes

**Sin tokens nuevos.** Se usan:
- los colores `papel`, `hoja`, `tinta`, `tenue`, `turquesa` (el único macizo, el foco y el texto de acción), `rocio`, `linea`, `borde` (el borde punteado de la retirada), `atenta` y `atenta-fondo` (el 429 y el rótulo del piloto), `pronto` y `pronto-fondo` (solo el error de carga) y `ok` y `ok-fondo` (solo «Te entregamos el archivo»);
- los radios `rounded-xl`, `rounded-2xl` (el diálogo) y `rounded-full`;
- las variantes `angosto:`, `telefono:`, `@3xl/main:` y `@4xl/main:`;
- la medida fija de 12 rem de Grupo familiar y `var(--container-xs)` del índice de `/privacidad`, sin medidas nuevas.

**Componentes:**
- los que hay: `Pagina`, `Volver`, `Nota`, `Etiqueta`, `Boton` (`principal`, `secundario` y `texto`), `MensajeError`, `EnlaceEnFrase`, `DialogoConfirmar`, `LineaApertura`, `LineaIngreso`, `FilaDispositivo` (sin acciones) y el índice de `/privacidad`;
- **conviene sacar el índice de `PaginaPrivacidad` a un componente**, por ejemplo `IndicePagina`, en vez de copiarlo. Las clases no cambian;
- dos nuevos: `PanelDescarga` (3.7, el mismo en las dos pantallas) y `LineaHistorial` (3.4.9, el molde de `LineaIngreso` con la cola «a las {HH:MM} · {nombre}»).

**Nada escrito a mano:** ni colores, ni `size-[…]`, ni sombras, ni `text-sm` o `text-xs`.

---

## 7. Accesibilidad

- **17 px:** ningún texto bajo `text-base`: ni los `dt`, ni las colas de las líneas, ni la huella, ni los precios.
- **48 px:** «Ver los datos de…», «Ver tus datos», «Descargar en un archivo», «Descargar», «No descargar», «Ver más», «Volver a intentar», «Ir a Grupo familiar», «Ver dónde entraste», el `summary` del índice y los enlaces del índice miden `min-h-12`. El correo usa el `::after` de DISENO 6.
- **Foco:**
  - el contorno base de 3 px en `turquesa`;
  - al llegar a la página va al `h1`;
  - el diálogo atrapa el foco con `showModal`, empieza en su título y lo devuelve a «Descargar en un archivo» (C30);
  - tras «Ver más», a la primera línea nueva;
  - tras descargar, a la nota de éxito;
  - al volver a «Grupo familiar» o a «Tu cuenta», al botón que abrió la página;
  - **nunca en el `body`**: todo foco que sigue a una respuesta se da después de que React pinta (MATU-55, 3.3).
- **Encabezados** (C30): un `h1`, un `h2` por bloque y `h3` para cada autorización, campo, enlace, pedido, pago y grupo por día. Con un lector se salta de bloque en bloque sin el índice.
- **Listas semánticas:** `ul` para lo que no tiene orden temporal (autorizaciones, campos, insumos, grupos), `ol` para los historiales y `dl` para los pares de rótulo y dato.
- **El estado nunca solo por color:**
  - las autorizaciones llevan palabra e ícono propio, y la retirada, borde punteado;
  - los avisos enviados, palabra e ícono (`Check`, `X`, `CircleDashed`), todos en `tenue`;
  - las líneas del historial, frase e ícono;
  - el insumo que ya no se sigue, palabra y `Circle`.
- **Anuncios:** «Cargando…», «Se agregaron {n} líneas.» y «Te entregamos el archivo…» van por `role="status"`; el error y el 429, por `role="alert"`, con las regiones vivas de `Anuncios`.
- **Reflujo a 320 px con el texto al 200 %:**
  - los nombres, las direcciones, los textos de la ficha y el motivo de los enlaces van en `break-words`;
  - la huella va en `break-all`, y el correo en `[overflow-wrap:anywhere]`;
  - la fecha y la hora van en dos `cifras`;
  - los íconos de las líneas se apilan y la tabla de productos pasa a una columna en el modo `angosto`;
  - sin desplazamiento horizontal.
- **Movimiento:** nada se anima. El chevron del índice gira sin transición (MATU-75). Con `prefers-reduced-motion` no cambia nada.
- **Datos** (C26): nada de estas pantallas va a `localStorage`, `sessionStorage`, `history.state`, la URL ni `document.title`. El `Blob` del archivo se revoca de inmediato.

---

## 8. Criterios visuales verificables

1. En `/grupo/datos` y en `/cuenta/datos`, el único elemento en `turquesa` macizo es «Descargar en un archivo». Dentro del diálogo, el único macizo es «Descargar».
2. En `/grupo` y en `/cuenta` no aparece ningún macizo nuevo. «Ver los datos de…» y «Ver tus datos» son `secundario`.
3. En Grupo familiar, el bloque «Datos de {nombre_pila}» va entre los permisos y «Borrar sus datos». El pagador y el observador ven la frase de quién puede, sin botón.
4. Ni la URL ni el título de la pestaña llevan el nombre de la persona, ni ningún id. El título es «Datos guardados · MATU» o «Tus datos · MATU».
5. Tocar «Descargar en un archivo» nunca descarga directo: siempre abre «Antes de descargar», con el foco en su título.
6. El archivo descargado se llama `matu-datos-AAAA-MM-DD.json` (o el nombre que fije P7) y no lleva el nombre de la persona.
7. Con la autorización de la ficha retirada, «Su ficha» muestra solo la nota con `ShieldOff`, borde punteado y la fecha de borrado, y ningún texto de la ficha. En pausa, la nota con `Hourglass`, sin borde punteado.
8. Con los insumos retirados o en pausa, no se ven «Compras anotadas» ni «Avisos de insumos», ni en la página ni en el índice.
9. Ningún historial muestra una línea de hace más de 90 días. «Ver más» suma líneas y desaparece cuando no quedan.
10. Ningún aviso simulado dice «Salió». Todos dicen «En el piloto no salió», y la nota del piloto se ve una sola vez.
11. Ningún precio va sin IVA ni hay una línea «IVA» o «Neto». En «Datos de», ningún pedido muestra tarjeta, cuotas, dígitos ni teléfono de contacto.
12. En «Tus datos», un pago muestra solo el tipo de tarjeta, las cuotas y los últimos 4 dígitos. Nunca una orden, un token ni un código.
13. Ningún bloque muestra el teléfono de un relevo, ni el correo o el celular de otra persona del grupo. «A quién llamar» se ve tal cual se escribió.
14. Quien cuida ve la nota «Aquí ves solo lo que hiciste tú…» sobre su historial. Quien administra no la ve.
15. El 429 va en `atenta` con `Clock` y sin «Volver a intentar».
16. Ningún texto mide menos de 17 px. Todo lo tocable mide 48 px o más. A 320 px con el texto al 200 % no hay desplazamiento horizontal, ni con la huella, el correo o un texto largo de la ficha.
17. Ningún texto dice «exportar», «auditoría», «registro de accesos», «consentimiento», «sesión», «token», «usuario» ni «JSON» fuera de la ayuda del panel, donde va entre paréntesis.
18. Al imprimir cualquiera de las dos páginas sale solo «Esta pantalla no se imprime.».
19. Después de descargar, de «Ver más» o de volver a la página anterior, `document.activeElement` nunca es el `body`.
20. En el tema oscuro, la nota de la retirada, la del 429 y la del piloto mantienen su borde, su ícono y su palabra, y todo texto cumple 4,5:1 (son tokens con contraste ya medido).

---

## 9. Textos para `lenguaje.md`, sección 35 («Copia de los datos (MATU-54)»)

Entran todos los **[ANALISTA]** de las secciones 2 a 5, y los que siguen.

**Ajustes a textos del analista:**
1. «No incluimos su teléfono.» → «No incluimos el teléfono de los relevos.» (3.4.4): sin un relevo al lado, «su» no dice de quién.
2. «Queda en tu teléfono» → «Queda en tu teléfono o computador», en los dos diálogos (3.7 y 5.5).
3. «Te entregamos el archivo. Búscalo en las descargas de tu teléfono.» → «Te entregamos el archivo. Búscalo en tus descargas.» (3.7).
4. «Hay una referencia… pídela a cuidaconmatu@gmail.com.» → con `{correo}` de la política, como todo correo de la app (MATU-55, 2.5).

**[NUEVO]:**
- títulos de pestaña: «Datos guardados · MATU» y «Tus datos · MATU»;
- botón de «Tu cuenta»: «Ver tus datos»;
- panel: «En esta pantalla, los historiales muestran los últimos 90 días. El archivo trae todo lo guardado.»;
- historiales: «Los de los últimos 90 días. Lo anterior va en el archivo.» y, sin nada anterior, «Los de los últimos 90 días.»;
- rectificación: «Si algo está mal, escribe a {correo} desde el correo de tu cuenta.»;
- los rótulos y las frases de los bloques (3.4.1 a 3.4.8, 5.3 y 5.4);
- las frases del historial que no están en la revisión (3.4.9);
- insumos en pausa, clave destruida y el diálogo sin la ficha (3.5 y 3.7);
- «Preparando el archivo…» y «No pudimos preparar el archivo. Revisa tu conexión y vuelve a intentarlo.» (solo con la opción B de P1);
- los vacíos de 3.6 y 5.5;
- «Completo en el archivo.» (P3).

**Ajuste de L 29, «Cómo pedir»:** el del analista, en 4.

---

## 10. Preguntas abiertas para el orquestador

| # | Pregunta | Lo que recomiendo |
|---|---|---|
| P1 | **¿La pantalla y el archivo salen del mismo GET?** (A) Al abrir la página, un solo GET trae todo: la pantalla muestra 90 días y «Descargar» guarda esos mismos bytes desde la memoria. (B) Un GET para la pantalla, con 90 días, y otro para el archivo, con todo | **(A).** Cumple C8 al pie de la letra («un solo GET»), deja una sola línea «Pidió una copia de los datos» por visita y gasta una sola de las 10 copias por hora. La bajada («al {fecha} a las {hora}») y el archivo tienen la misma hora. «Ver más» no espera, y el diálogo no tiene estado «Descargando» ni error de red. El costo es que abrir la pantalla ya cuenta como una copia, y el historial de quien cuida lo va a mostrar así. Si el backend elige (B), se construyen las filas marcadas «opción B» de 3.7, y hay que decidir si la vista de la pantalla también se registra |
| P2 | **La forma del contrato.** La pantalla necesita: `generado_en`; por cada historial, si hay algo anterior a 90 días; la lista cerrada de acciones del historial (3.4.9); el estado de cada aviso enviado, con un valor propio para el simulado (D-54-11); los estados de los avisos de insumos y de los pedidos; la calidad de quien autorizó; y el nombre `null` con `autor_activo: false` para quien salió (MATU-53, P11) | Que el backend lo traiga así. El frontend no deduce un estado que el servidor no manda |
| P3 | **El celular en la pantalla de «Tus datos».** El analista dice que la copia lleva el celular completo, y su texto del diálogo dice que el **archivo** lo trae completo | En pantalla, **enmascarado** como en «Tu cuenta» (MATU-57), con «Completo en el archivo.». Se mira en la calle y a una mano. Si Jorge prefiere completo, se quita esa frase y el número va en dos `cifras` |
| P4 | **Compras y avisos de insumos con los insumos retirados o en pausa.** C3 dice «sin lo anotado de los insumos», sin nombrar las compras ni los avisos | Que no vayan, ni en la pantalla ni en el archivo (3.5). Lo confirma el analista |
| P5 | **«Tus pagos» y el grupo.** El monto dice «en {grupo}». Nombrar a la persona («para María») traería un dato de la persona cuidada a «Tus datos», y el analista dice que no va nada de ella | Solo el nombre del grupo. Lo confirma el analista |
| P6 | **«Abrió la ficha».** C21 dice que no se registra un `plan.leer`. Entonces, ¿qué fila da «Abrió la ficha»? ¿Las aperturas del relevo, que ya van en «Enlaces de relevo»? | Si son las del relevo, se quita la frase del historial para no mostrarlas dos veces. Si existe otra acción, el contrato la nombra |
| P7 | **Los nombres de los dos archivos.** C9 da un solo nombre. Si Carmen baja las dos copias el mismo día, el navegador las llama `matu-datos-…json` y `matu-datos-… (1).json` | `matu-datos-AAAA-MM-DD.json` para la persona y `matu-cuenta-AAAA-MM-DD.json` para «Tus datos». Ninguno lleva un nombre |
| P8 | **La rectificación** (faltante 3 del analista, MATU-91). Propongo «Si algo está mal, escribe a {correo}…» bajo «Sus datos» | Que Jorge lo apruebe con la sección 35. Sin eso, la persona ve un dato mal y no sabe qué hacer |
| P9 | **El principio del mismo verbo** (DISENO 4.6). «Descargar» y «Te entregamos el archivo» no lo cumplen, a propósito (3.7) | Aceptar la excepción. Si Jorge prefiere el mismo verbo, la única opción honesta es «Descargamos el archivo», y tampoco es cierto si el navegador lo bloquea |
| P10 | **La descarga en el iPhone.** Safari abre una vista previa del JSON en vez de guardarlo, según la versión | Que Martín lo pruebe en el iPhone real. Si abre la vista previa, el texto de éxito suma «En iPhone, toca Compartir y elige «Guardar en Archivos».» **[NUEVO]**, solo en iOS |
| P11 | **El índice en «Tus datos».** Con 7 u 8 bloques cortos, ¿hace falta? | Sí, por coherencia y porque en el teléfono «Tus pagos» queda muy abajo. Es el mismo componente |
| P12 | **La sección de `lenguaje.md`.** La revisión previa dice «34», y la 34 ya es de MATU-42 | **35**, como dijo el orquestador. Lo corrige quien copie los textos |

---

## 11. Cómo la voy a revisar

La voy a revisar funcionando, con capturas a 360, 1280 y 1920 px, en tema claro y oscuro, y a 320 px con el texto al 200 %. El recorrido, con datos sintéticos (Carmen, María, Rosa y Rodrigo):
1. Como Carmen (admin), entrar desde Grupo familiar a «Datos de María» y recorrer los nueve bloques con el índice, en el teléfono y en la pantalla ancha.
2. «Ver más» en «Quién abrió o editó la ficha» y en las aperturas de un enlace, mirando el foco.
3. Abrir «Antes de descargar», cerrarlo con «No descargar» y con Esc, y después descargar. Revisar el nombre del archivo y que no quede nada en el almacenamiento del navegador.
4. Retirar la autorización de la ficha y la de insumos, y volver a la página: las notas de 3.5, sin texto ni compras.
5. Con una cuenta sintética de rol «Cuida»: la nota de «solo lo que hiciste tú». Como Rodrigo (pagador): la frase sin botón en Grupo familiar.
6. Como Rodrigo, «Tus datos» con un pago, la tarjeta en sus últimos 4 dígitos y los avisos simulados en «En el piloto no salió».
7. Pedir once copias en una hora: el 429.
8. Sin red: el error y «Volver a intentar».
9. Imprimir las dos páginas.

En el iPhone real lo prueba Martín: la descarga en Safari (P10).

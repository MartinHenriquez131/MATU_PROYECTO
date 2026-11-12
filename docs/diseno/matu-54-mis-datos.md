# MATU-54 · Ver y descargar los datos («Datos de {nombre}» y «Tus datos») · Especificación de diseño

**Versión 1.2 · 12-11-2026 · agente 6 UI/UX.** La 1.2 sale de la revisión visual de lo construido (HEAD a12f8b5, sección 12) y de las decisiones 366 a 400 del README.

**Qué cambia de la 1.1 a la 1.2:**
- **Reflujo** (hallazgos P1-1, P1-2 y P2-1 de la revisión, 3.4):
  - las `li` de los bloques ya no van con `items-start`: solo la `Etiqueta` y los botones llevan `self-start`;
  - las `Nota` dentro de una tarjeta llevan `iconoEnLinea`;
  - los `h2` y los `h3` de las dos páginas llevan `hyphens-auto`.
- **F1** (decisión 384): las frases del historial con `finalidad` y `referencia` (3.4.9, tipos 5, 6 y 19 a 25).
- **F5** (decisión 386): las compras dicen su unidad (3.4.6).
- **F2** (decisión 385): la copia no dice quién retiró una autorización, por minimización. Queda como en la 1.1.
- **Las autorizaciones son tarjetas separadas**, como las construyó el frontend (3.4.2).
- **El nombre completo para el pagador y el observador**, que no reciben `nombre_pila` (2).
- **Las aperturas de cada enlace** usan la fecha completa (`completa` de `LineaApertura`), sin «hoy» (3.4.4).
- **El 503** cambia `WifiOff` por `CloudOff` (3.6).
- **C-1 y C-2 quedan resueltas** por las decisiones 383 y 376 (10.1).

**Versión 1.1 · 12-11-2026.** Se escribió antes de construir. La 1.0 se escribió sin contrato. La 1.1 sigue al contrato propuesto `docs/api/propuestos/mis-datos.openapi.yaml` (decisiones 342 a 365 del README, commits eee495b y e94ee52) y a las respuestas del orquestador a P1 a P12, por delegación de Jorge (sección 0). **El frontend no inventa campos:** usa los nombres del YAML, que esta versión ya cita.

**Qué cambia de la 1.0 a la 1.1:**
- **Un solo GET por copia** (P1 (A), decisión 343). La pantalla pide el JSON como texto, y «Descargar» guarda ese mismo texto. Sale el estado «Descargando», con su error y su 429 dentro del diálogo. El nombre del archivo viene de `Content-Disposition` (3.7).
- **El historial** tiene sus 26 tipos (`TipoHecho`), cada uno con su texto e ícono (3.4.9). El contrato no trae el objeto del hecho (qué insumo, qué relevo, qué permiso), así que las frases de la 1.0 con `{producto}`, `{nombre_relevo}` o `{permiso}` pasan a frases generales. Además, MATU aparece como autor de cuatro tipos, y entran `hay_hechos_sin_asociar` y «Editó la ficha» cuando `campo` es `null`.
- **«Dónde entraste» suma `pediste_una_copia`** (3.4.9 y 5.3), con la contradicción que señalo en 10.1.
- **Los bloques usan los campos y los enumerados del contrato** (3.4 y 5.3):
  - autorizaciones con `reemplazada` y sin motivo ni autor del retiro;
  - ficha con `borrada` y `sin_autorizar`;
  - enlaces con `compartido_por` y `bloqueado`;
  - compras con `origen`;
  - avisos de insumos con sus cuatro estados;
  - pedidos con referencia, comercio, `si_falta`, devoluciones, `precios_de_ejemplo` y `pago_de_prueba`;
  - «Tus datos» con `cerrado_en`, `avisos_activos`, `creada_en`, `unido_en`, el canal `sms`, el resultado `pendiente` y el bloque nuevo de las condiciones aceptadas.
- **El 429 dice la hora** con `Retry-After`, y entra el **503** (3.6).
- **Una contradicción entre el contrato y D-54-9** sobre «Ver más» (10.1). Mientras se resuelve, la especificación sigue a D-54-9.
- Se propone el texto definitivo del `aviso` fijo (`AvisoCopia`, Q12 del README) en la sección 9.

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

## 0. Decisiones del orquestador (12-11, por delegación de Jorge)

| # | Decisión | Dónde cambia |
|---|---|---|
| P1 | (A): un solo GET, y la descarga guarda los mismos bytes | 3.6 y 3.7 |
| P2 | Se cruzó la lista con el contrato. Lo que falta está en 10.2 | 3.4 y 10 |
| P3 | El celular va enmascarado en la pantalla y completo en el archivo | 5.3 |
| P4 | Sin compras ni avisos de insumos cuando los insumos están retirados o en pausa | 3.5 |
| P5 | «Tus pagos» nombra solo el grupo | 5.4 |
| P6 | Las aperturas del relevo van dentro de cada enlace, no en el historial. `abrio_la_ficha` es la ficha abierta por un miembro del grupo en la app | 3.4.4 y 3.4.9 |
| P7 | Los archivos se llaman `matu-datos-…` y `matu-cuenta-…` | 3.7 |
| P8 | Sí a la frase de rectificación por correo | 3.4.1 |
| P9 | Se acepta «Te entregamos el archivo» | 3.7 |
| P10 | Lo prueba Martín en el iPhone | 11 |
| P11 | El índice va en las dos copias | 3.3 y 5.2 |
| P12 | Los textos van en la sección 35 de `lenguaje.md` | 9 |

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
| **(1.2) Sin `nombre_pila`** | El pagador y el observador no reciben `nombre_pila` de la API, así que el título y la frase usan el `nombre` completo: «Datos de María Soto Pérez» y «… quien cuida a María Soto Pérez.». **Se confirma** lo que construyó el frontend: el nombre completo es cierto, y el cliente nunca recorta un nombre para inventar uno de pila | — |

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
│ │ La da quien la cuida, sin ser  │ │  text-base
│ │ su representante legal.        │ │
│ │ La registró Carmen el          │ │
│ │ 02/11/2026 a las 18:20.        │ │
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
- Cada bloque es una `section` con un `h2 text-xl font-bold`. Su contenido va en una superficie `bg-hoja rounded-xl ring-1 ring-linea px-4 angosto:px-2`, con `divide-y divide-linea` entre filas.
- Los instantes (`Instante`, con el desfase de Chile) se muestran como «{DD/MM/AAAA} a las {HH:MM}», en dos `cifras` dentro de un `<time dateTime>`. Los días (`Dia`) se muestran como «{DD/MM/AAAA}».
- **En los bloques, nunca «hoy» ni «ayer»:** es una copia, y la fecha absoluta se lee igual mañana. Solo los grupos por día de los historiales (3.4.9) usan «Hoy», «Ayer» y «El {día}», como Quién la vio.
- El dinero (`Pesos`) va como `$69.000` en `cifras`, siempre con IVA incluido y **nunca con una línea de IVA** (D-54-14).
- **Quien salió del grupo** llega como `PersonaNombrada` con `nombre: null` y `activo: false`. Se nombra «Alguien que ya no está en el grupo», o «alguien que ya no está en el grupo» dentro de una oración (MATU-53, 5.7), con el mismo peso y color del nombre al que reemplaza. Un `escrito_por` o un `anotada_por` en `null` se trata igual.
- **Un bloque sin filas** muestra una frase en `p text-base text-tenue`, sin ícono grande ni botón: es una copia y no hay nada que empezar (tabla de 3.6).
- **(1.2) Reflujo dentro de una fila.** Una `li` de bloque es `flex flex-col gap-2`, **sin `items-start`**: así sus hijos tienen el ancho de la fila, y `break-words` puede partir una palabra que no cabe. Con `items-start`, cada hijo toma el ancho de su contenido, y un nombre de una sola palabra larga lo ensancha más allá de la pantalla (P1-1). Solo la `Etiqueta` y los botones llevan `self-start`.
- **(1.2) Las notas dentro de una tarjeta** (la del representante legal, las de 3.5 y la de `lo_tuyo`) llevan `iconoEnLinea`, como en MATU-44 y MATU-55. Con el ícono al lado, a 320 px con el texto al 200 % «representante» no cabe, y la nota se sale 32 px de su tarjeta (P1-2).
- **(1.2) Títulos largos.** Los `h2` y los `h3` de las dos páginas llevan `hyphens-auto`. El `html` es `lang="es-CL"`, así que una palabra que no cabe se corta con guion en una sílaba («Autoriza-ciones») y no en la última letra («Autorizacione / s», P2-1). Si el navegador no tiene el diccionario, sigue `break-words`.
- **Los enumerados** se muestran con la palabra de esta especificación o de `lenguaje.md`, nunca con el valor del contrato. Un valor que el cliente no conoce no rompe la pantalla: la fila se muestra sin esa palabra.

#### 3.4.1 Sus datos (`persona`)

Es un `dl` como el de «Tu cuenta», con `dt text-base text-tenue` y `dd font-bold break-words`.

| `dt` | `dd`, desde el campo |
|---|---|
| Nombre **[NUEVO]** | `nombre` |
| Le dicen **[NUEVO, de «¿Cómo le dicen?», L 25.3]** | `nombre_pila` |
| Cuánto apoyo necesita **[NUEVO, de L 25.3]** | `nivel_apoyo`, con el texto de la opción del alta (L 25.3, el `texto` de `datos.ts`) |
| Dirección **[NUEVO]** | `direccion`: «{calle} {numero}, {depto}, {comuna}, {region}». Si `depto` es `null`, se omite con su coma. En otra línea, «Referencia: {referencia}» **[NUEVO]** si la hay. `etiqueta` no se muestra: es un nombre interno de la dirección y va en el archivo. Si `direccion` es `null`, «Sin dirección.» **[NUEVO]** en `font-normal text-tenue` |
| En MATU desde **[NUEVO]** | `alta_en`, solo el día |

Bajo el `dl`, siempre: «Si algo está mal, escribe a {correo} desde el correo de tu cuenta.» **[NUEVO, aprobado por P8]**, en `p text-base text-tenue max-w-prose`, con el correo en `EnlaceEnFrase mailto:` y `[overflow-wrap:anywhere]`. `{correo}` es `correo_contacto` de `GET /v1/politica`, como en MATU-55 2.5. Sin correo configurado, el párrafo no se muestra. Cubre la rectificación mientras no exista MATU-91.

#### 3.4.2 Autorizaciones (`autorizaciones`)

Una `ul` con una `li` por autorización, en el orden del servidor (de la más reciente a la más antigua, también las retiradas y las reemplazadas).

**(1.2) Cada autorización es su propia tarjeta**, como la construyó el frontend, y no una fila de una superficie común: la `ul` es `flex flex-col gap-4`, y cada `li` es `flex flex-col gap-2 rounded-xl bg-hoja px-4 angosto:px-2 py-4` con `ring-1 ring-linea`. La retirada cambia el anillo por `border-2 border-dashed border-borde`. **Se confirma** porque el borde punteado es la forma que dice «retirada» (MATU-44), y en una fila con separadores no tendría un contorno propio que cambiar. Además, cada autorización es un documento aparte, con su fecha y su versión. Las demás listas siguen en una sola superficie con separadores.

| Parte | Texto | Componente |
|---|---|---|
| Título | Según `finalidad`, el título del bloque de MATU-44: `plan_cuidado` «Permiso para guardar su ficha», `consumo` «Permiso para calcular sus insumos» y `despacho` el de pedidos **[L 22]** | `h3 text-lg font-bold` |
| Estado | Según `estado`: `vigente` «Vigente» con `ShieldCheck` y `revision_vencida` «En pausa» con `Hourglass` **[L 22]**, `retirada` «Retirada» con `ShieldOff` **[L 22]** y `reemplazada` «Se renovó» con `RefreshCw` **[NUEVO]** | `Etiqueta`, en `text-base` |
| Quién la da | Según `calidad_otorgante`: «La da {nombre_pila}, por su cuenta.» · «La da su representante legal.» · «La da quien la cuida, sin ser su representante legal.» **[NUEVO]**. Son las calidades de L 25.4, dichas en tercera persona | `p text-base` |
| Quién y cuándo | La registró {registrada_por} el {otorgada_en}. **[NUEVO]** | `p text-base` |
| Renovación | Hay que renovarla el {revision_vence_en}. **[NUEVO]** Solo con `vigente` y `revision_vence_en` presente. Con `revision_vencida`: «Había que renovarla el {revision_vence_en}.» **[NUEVO]** | `p text-base` |
| Retiro | Se retiró el {retirada_en}. **[NUEVO]** Con `reemplazada`: «Se renovó el {retirada_en}.» **[NUEVO]**. La copia no dice quién la retiró ni el motivo, por minimización (decisión 385) | `p text-base` |
| Lo aceptado | Lo que se aceptó: política de privacidad {version_politica}, declaración {declaracion.version} y aviso {aviso.version}. **[NUEVO]** Si `declaracion` o `aviso` es `null`, esa parte se omite con su coma o su «y». Las versiones van en `cifras`. El identificador y la huella **no se muestran**: van en el archivo y no le dicen nada a una persona | `p text-base text-tenue` |
| Representante legal | Hay una referencia al documento del representante legal. Si la necesitas, pídela a {correo}. **[ANALISTA, ajustado: el correo sale de la política]** Solo con `hay_documento_representante: true` | `Nota tono="rocio"` con `FileText`, el correo en `EnlaceEnFrase` |

El estado no depende del color: lleva la palabra, el ícono y la frase del retiro o de la renovación. La reemplazada no lleva borde punteado, porque no se retiró: se renovó.

#### 3.4.3 Su ficha (`ficha`)

**Con `estado: disponible`:** una `ul` con una `li` por cada uno de los tres `campos`, siempre en su orden, y después una por cada una de las `secciones`.
- El `h3 text-lg font-bold` lleva el nombre del campo (`rutina`, `manejo_situaciones` y `red_apoyo`: «Su día», «Si se altera» y «A quién llamar») o de la sección **[L 14.1]**.
- El `texto` va en `p text-base whitespace-pre-line break-words max-w-prose`, **tal cual se escribió**, con los nombres y teléfonos de «A quién llamar» (D-54-4). No se cambia ningún carácter.
- Debajo, «Lo escribió {escrito_por} el {actualizado_en}.» **[NUEVO]**, en `text-base text-tenue`.
- Un campo con `texto: null` dice «Sin escribir.» **[NUEVO]** en `text-tenue`, sin la línea del autor.
- `completitud` no se muestra: los tres campos ya se ven, con su texto o con «Sin escribir.».

**No se dibuja la hoja con el imán.** La hoja es la ficha para un relevo. Esto es una copia de datos, y verse como la hoja la confundiría con lo que se comparte (C10).

**En los demás estados:** la nota de 3.5, en lugar de la lista.

#### 3.4.4 Enlaces de relevo (`enlaces_relevo`)

Bajo el `h2`, una sola vez: «No incluimos el teléfono de los relevos.» **[ANALISTA, ajustado: el texto era «No incluimos su teléfono.», que sin un relevo al lado no dice de quién]**, en `p text-base text-tenue`.

Una `ul` con una `li` por enlace, en el orden del servidor:

| Parte | Texto |
|---|---|
| Para quién | `nombre_relevo`, en `text-lg font-bold break-words` |
| Estado | `vigente` «Vigente» **[NUEVO]**, `vencido` «Vencido», `revocado` «Cortado» y `bloqueado` «Bloqueado» **[L 9, `estados` de `textos.ts`]**, en `Etiqueta` con la figura que ya usa Enlaces (MATU-48) |
| Por qué | `motivo`, con el texto de L 9.1 («Salgo unas horas», «Fin de semana fuera»…). Con `otro`, la palabra de L 9.1 para «otro» |
| Qué ve | Ve: {campos y secciones}. **[NUEVO]** Los nombres de L 14.1, en el orden de la ficha, separados por coma y «y» |
| Quién y cuándo | Lo compartió {compartido_por} el {creado_en}. **[NUEVO]** `compartido_por` es el nombre de pila que vio el relevo. Es texto y no `PersonaNombrada`, así que nunca dice «alguien que ya no está en el grupo» |
| Hasta cuándo | Con `vigente`: «Vence el {vence_en}.» Con `vencido`: «Venció el {vence_en}.» Con `revocado` o `bloqueado` y `cortado_en`: «Se cortó el {cortado_en}.» **[NUEVO]** |
| Uso | Con `usos` 0: «No se ha abierto.» Con 1: «Se abrió una vez, el {ultimo_uso_en}.» Con más: «Se abrió {usos} veces. La última, el {ultimo_uso_en}.» **[NUEVO]** |
| Aperturas | Un `ol` de `LineaApertura` (MATU-45) con `notas={false}`, `completa` y sin acciones. **(1.2) `completa`** hace que la hora diga «el {DD/MM/AAAA} a las {HH:MM}» y no «hoy a las…»: en la misma tarjeta, «Se abrió una vez, el 12/11/2026» y «hoy a las 10:09» se leían como dos fechas distintas (P3-1). Lleva con las `aperturas` de los últimos 90 días. Son los cuatro tipos de MATU-45 (`presentacion`, `apertura`, `pin_incorrecto` y `bloqueo`), con sus frases e íconos de L 15. Si hay más de 5, se ven 5 y «Ver más» (3.4.10). Sin aperturas en 90 días, no hay lista |

#### 3.4.5 Sus insumos (`insumos.lista`)

**Con `insumos.estado: disponible`:** una `ul` con una `li` por insumo, en el orden del servidor.
- `nombre`, en `text-lg font-bold break-words`. `del_catalogo` no se muestra.
- «Usa {usa_unidades} {unidad} cada {cada_dias} días.» **[NUEVO]**, con la unidad de L 21 (`unidad`, `sobre`, `ml`, `g`) en singular o plural.
- «Quedaban {quedaban_unidades} el {quedaban_el}.» **[NUEVO]**.
- Solo si `se_sigue`: «Se acaba el {se_acaba_el}.» **[NUEVO]**.
- «Avisa {dias_aviso} días antes.» **[NUEVO]**. Con 0: «Avisa el mismo día.» **[NUEVO]**.
- «{unidades_por_envase} por envase.» **[NUEVO]**, solo si no es `null`.
- «Lo agregaron el {agregado_en}. Lo cambió por última vez {actualizado_por} el {actualizado_en}.» **[NUEVO]**, en `text-tenue`.
- Con `se_sigue: false`: `Etiqueta` neutra con `Circle` y «Ya no se sigue» **[NUEVO]**. Si se sigue, no lleva etiqueta: es lo normal.

Si el frontend ya tiene una frase de L 18 o L 21 que dice lo mismo, usa esa y lo avisa en su entrega.

**En los demás estados:** la nota de 3.5.

#### 3.4.6 Compras anotadas (últimos 90 días) (`insumos.compras`)

El título es **[ANALISTA]** y ya dice el plazo: el contrato confirma que las compras declaradas se borran a los 90 días, así que no lleva la frase de los 90 días. Un `ol`, en el orden del servidor, con una `li` por compra:
- **(1.2)** «{unidades} {unidad} de {insumo}» en `font-bold`, con `unidad` de la compra (decisión 386) y la palabra de L 21 en singular o plural: «20 unidades de Pañal adulto talla M», «2 sobres de Champú en sobre». Nunca se cruza con `lista` por el nombre;
- con `origen: declarada`: «El {el} · Anotó {anotada_por}» **[NUEVO]**;
- con `origen: pedido_matu`: «El {el} · Llegó con un pedido de MATU» **[NUEVO]**;
- todo en `text-base text-tenue`.

Con más de 10 compras se usa «Ver más» (3.4.10).

#### 3.4.7 Avisos de insumos (`insumos.avisos`)

Bajo el `h2`, la frase de los 90 días (3.4.9). Un `ol` con una `li` por aviso:
- «{insumo}: se acaba el {fecha_prevista}.» **[NUEVO]** en `font-bold`;
- debajo, en `text-base text-tenue`, el estado y su fecha:

| `estado` | Texto |
|---|---|
| `pendiente` | Todavía no se avisa. **[NUEVO]** |
| `notificada` | Se avisó el {notificado_en}. **[NUEVO]** |
| `resuelta` | Se resolvió el {cerrado_en}. **[NUEVO]**, el verbo de «Ya lo resolví» (decisión 79) |
| `descartada` | Se descartó el {cerrado_en}. **[NUEVO]** |

Sin colores de urgencia (● ◐ ○): esto es lo que pasó, no lo que hay que hacer hoy.

#### 3.4.8 Sus pedidos (`pedidos`, D-54-14 y D-54-15)

**Con `pedidos: null` (la capa 3 quitada), el bloque no existe** y no sale en el índice. Con la capa apagada o la autorización de pedidos retirada, el bloque se ve igual.

Bajo el `h2`, la frase de los 90 días. Una `ul` con una `li` por pedido, en el orden del servidor:

```
│ Pedido 4821                        │  h3 text-lg font-bold
│ (✓ Entregado)                      │  Etiqueta
│ Lo armaron el 08/11/2026 a las     │  text-base text-tenue
│ 11:02.                             │
│ Pañal adulto M, paquete de 30 × 2  │  dl de líneas
│   $27.980                          │  precio en cifras, a la derecha
│   En Farmacia Los Aromos (comercio │  text-tenue
│   ficticio) · Si falta: buscarlo en│
│   otro comercio                    │
│ Productos                 $33.270  │
│ Envío                      $3.990  │
│ Total                     $37.260  │  font-bold
│ Lo pagó Rodrigo el 08/11/2026 a    │  text-base
│ las 11:24.                         │
│ Cobrado: $37.260 · Devuelto: $5.290│
│ Se devolvieron $5.290 porque no se │  text-base text-tenue
│ pudo entregar Toallitas.           │
│ Pago de prueba: no se cobró dinero │  text-base font-bold
│ real.                              │
│ Entrega: Los Aromos 123, depto 4,  │  text-base text-tenue
│ Ñuñoa, Región Metropolitana        │
```

| Parte | Texto |
|---|---|
| Título | Con `referencia`: «Pedido {referencia}» **[NUEVO]**, en `cifras`: es el número del comprobante (MATU-62). Sin ella: «Pedido del {creado_en}» **[NUEVO]** |
| Estado | La palabra de `estado`, en `Etiqueta`, según la tabla que sigue |
| Cuándo | Lo armaron el {creado_en}. **[NUEVO]** |
| Líneas | Por cada `lineas[]`: «{producto}, {presentacion} × {cantidad}» y `subtotal`, en un `dl` de dos columnas (`grid grid-cols-[minmax(0,1fr)_auto] gap-x-4`), con el precio a la derecha en `cifras`. Debajo, en `text-tenue`: «En {comercio} · Si falta: {si_falta}», con los textos de `textosPedido` (`otroComercio` y `quitar`) en minúscula. En el modo `angosto`, el precio baja bajo el producto (`angosto:grid-cols-1`) |
| Montos | «Productos» **[NUEVO]** con `subtotal_productos`, «Envío» **[L 27]** con `costo_envio` y «Total» **[L 27]** con `total` en `font-bold`. Si `total` es `null` (borrador), la fila del total no aparece. Nunca «IVA» ni «Neto» |
| Pago | Según `pago` (tabla de pago, más abajo). Con `pago: null`, «Sin pagar.» **[NUEVO]** |
| Devoluciones | Por cada `devoluciones[]` (ver más abajo) |
| Entrega | Entrega: {calle} {numero}, {depto}, {comuna}, {region} **[NUEVO]**, en `text-tenue`, con `entrega`. Si es `null`, la línea no aparece |
| Piloto | Si algún pedido tiene `precios_de_ejemplo: true`, al pie del bloque y **una sola vez** va `PreciosDeEjemplo` (DISENO 3, rótulo del piloto). Si `pago.pago_de_prueba` es `true`, en ese pedido: «Pago de prueba: no se cobró dinero real.» **[NUEVO, el rótulo de la pasarela de DISENO 1 en una línea]**, en `font-bold` |

**El estado del pedido** (`estado`). Las palabras salen de L 27 y de `textosPago` donde ya existen. Las demás son **[NUEVO]**:

| `estado` | Palabra |
|---|---|
| `borrador` | Sin confirmar |
| `total_confirmado` | Por pagar |
| `vencido` | Venció sin pagar |
| `pagado` | Pagado **[`textosPago`]** |
| `enviado_a_comercio`, `preparando` | En preparación |
| `listo_retiro`, `asignado`, `sin_repartidor`, `retirado` | Por despachar |
| `en_ruta` | En camino |
| `entregado`, `cerrado` | Entregado |
| `no_entregado` | No se entregó |
| `reprogramado` | Reprogramado |
| `cancelado`, `cancelado_con_devolucion` | Cancelado |

Los estados se juntan porque a la familia no le cambia nada la diferencia entre, por ejemplo, `asignado` y `retirado`. El archivo trae el valor exacto.

**El pago** (`pago`):

| `pago.estado` | Texto |
|---|---|
| `sin_intento` | Sin pagar. **[NUEVO]** |
| `pendiente` | El pago está en curso. **[NUEVO]** |
| `aprobado`, `devuelto_parcial` | Lo pagó {pagado_por} el {pagado_en}. **[NUEVO]** Debajo, «Cobrado: {cobrado}.» y, si `devuelto` es mayor que 0, « · Devuelto: {devuelto}.» **[NUEVO]** |
| `no_aprobado` | El pago no se aprobó. **[NUEVO]** |
| `anulado` | Se devolvió todo el pago: {devuelto}. **[NUEVO]** |

**Cada devolución** (`devoluciones[]`), en `text-base text-tenue`:
- con `producto_no_entregado`: «Se devolvieron {monto} porque no se pudo entregar {producto}.»;
- con `pago_tardio`: «Se devolvieron {monto} porque el pago llegó cuando el total ya había vencido.»;
- con `cancelacion`: «Se devolvieron {monto} porque se canceló el pedido.»;
- con `estado: en_curso`, «Se devolvieron» cambia por «Se están devolviendo».

Todas son **[NUEVO]** y van con el verbo de ADR-027, «devolver».

**Nunca** el teléfono de contacto del pedido, ni el tipo de tarjeta, las cuotas o los dígitos, ni la orden, el token o el código de autorización (D-54-4 y D-54-14). El contrato no los trae. Los datos de la tarjeta van solo en «Tus datos» de quien pagó (5.4).

#### 3.4.9 Quién abrió o editó la ficha (`historial`)

- Bajo el `h2`, la frase de los 90 días: «Los de los últimos 90 días. Lo anterior va en el archivo.» **[NUEVO]**, en `p text-base text-tenue`.
  - La misma frase va bajo «Avisos de insumos», «Sus pedidos», «Últimos ingresos» y «Avisos que te enviamos».
  - Si la respuesta no trae nada anterior a 90 días en esa lista, queda solo «Los de los últimos 90 días.». Lo calcula la pantalla con la respuesta completa (Q18 del README).
- **Con `alcance: lo_tuyo`**, bajo esa frase: «Aquí ves solo lo que hiciste tú. La lista completa la ve quien administra el grupo.» **[ANALISTA]**, en `Nota tono="rocio"` con `Info`. Con `todo` no aparece.
- Las líneas son `LineaHistorial`, el patrón de `LineaIngreso` (MATU-55, 2.5):
  - un `ol` con un `li` por hecho;
  - el ícono en un círculo `size-9 rounded-full bg-rocio text-turquesa`, `aria-hidden`;
  - la frase en `font-bold`;
  - la cola en `text-base text-tenue tabular-nums`: «a las {HH:MM} · {quien.nombre}» **[ANALISTA]**. Con `quien.tipo: matu`, solo «a las {HH:MM}», porque la frase ya dice quién. Con `nombre: null` y `activo: false`, «a las {HH:MM} · alguien que ya no está en el grupo».
- Se agrupan por día con un `h3 text-lg font-bold`: «Hoy», «Ayer», «El {día de la semana}» y «El DD/MM/AAAA», con las reglas de MATU-45.
- El orden es el del servidor. El cliente no reordena.
- **Todos los círculos van en `rocio`.** Ningún hecho es una alarma: es lo que pasó. El tipo lo dicen la frase y la forma del ícono.

**Los 26 tipos** (`TipoHecho`). Los de la ficha traen `campo` o `seccion`. **(1.2)** Los de autorizaciones traen `finalidad`, y los de pedidos y pagos traen `referencia` (decisión 384). Los de insumos y enlaces no traen el objeto, así que su frase es general, y el detalle está en los otros bloques de la misma página.

| # | `tipo` | Quién | Frase | Ícono lucide |
|---|---|---|---|---|
| 1 | `abrio_la_ficha` | Persona | Abrió la ficha **[ANALISTA]**. Es un miembro en la app, no el relevo (P6) | `Eye` |
| 2 | `edito_la_ficha` | Persona | Con `campo` o `seccion`: Editó «{nombre}» **[ANALISTA]**, con el nombre de L 14.1. Con los dos `null`: Editó la ficha **[NUEVO, decisión 356]** | `PencilLine` |
| 3 | `quito_una_seccion` | Persona | Con `seccion`: Quitó «{nombre}» **[ANALISTA]**. Sin ella: Quitó una sección de la ficha **[NUEVO]** | `Eraser` |
| 4 | `ficha_borrada` | MATU | MATU borró lo escrito en la ficha **[README Q15]** | `Trash2` |
| 5 | `dio_una_autorizacion` | Persona | **(1.2)** Según `finalidad`: Dio la autorización de la ficha · Dio la autorización de los insumos · Dio la autorización de los pedidos **[NUEVO]**. Con `null`: Dio una autorización | `ShieldCheck` |
| 6 | `retiro_una_autorizacion` | Persona | **(1.2)** Retiró la autorización de la ficha · de los insumos · de los pedidos **[NUEVO]**, el molde de las notas de 3.5. Con `null`: Retiró una autorización | `ShieldOff` |
| 7 | `compartio_la_ficha` | Persona | Compartió la ficha con un relevo **[NUEVO]** | `Share2` |
| 8 | `corto_un_enlace` | Persona | Cortó un enlace de relevo **[NUEVO]** | `Unlink` |
| 9 | `agrego_un_insumo` | Persona | Agregó un insumo **[NUEVO]** | `PackagePlus` |
| 10 | `edito_un_insumo` | Persona | Cambió un insumo **[NUEVO]**, el verbo de `/insumos/cambiar` | `Package` |
| 11 | `dejo_de_seguir_un_insumo` | Persona | Dejó de seguir un insumo **[NUEVO]** | `CirclePause` |
| 12 | `volvio_a_seguir_un_insumo` | Persona | Volvió a seguir un insumo **[NUEVO]** | `CirclePlay` |
| 13 | `quito_un_insumo` | Persona | Quitó un insumo **[NUEVO]** | `PackageMinus` |
| 14 | `anoto_una_compra` | Persona | Anotó una compra **[NUEVO]** | `ShoppingBag` |
| 15 | `aviso_de_insumo` | MATU | MATU avisó que un insumo se está acabando **[NUEVO]** | `Bell` |
| 16 | `descarto_un_aviso` | Persona | Descartó un aviso de insumo **[NUEVO]** | `BellOff` |
| 17 | `resolvio_un_aviso` | Persona | Resolvió un aviso de insumo **[NUEVO]**, el verbo de «Ya lo resolví» | `CircleCheck` |
| 18 | `cambio_la_direccion` | Persona | Cambió la dirección **[NUEVO]** | `MapPin` |
| 19 | `creo_un_pedido` | Persona | **(1.2)** Armó el pedido {referencia} · sin referencia: Armó un pedido **[NUEVO]**, el verbo de MATU-53 5.7 | `ShoppingCart` |
| 20 | `confirmo_un_pedido` | Persona | **(1.2)** Confirmó el pedido {referencia} · Confirmó un pedido **[NUEVO]** | `ClipboardCheck` |
| 21 | `cancelo_un_pedido` | Persona | **(1.2)** Canceló el pedido {referencia} · Canceló un pedido **[NUEVO]** | `CircleX` |
| 22 | `cambio_que_hacer_si_falta` | Persona | **(1.2)** Cambió qué hacer si falta un producto en el pedido {referencia} · Cambió qué hacer si falta un producto **[NUEVO]** | `Replace` |
| 23 | `inicio_un_pago` | Persona | **(1.2)** Empezó a pagar el pedido {referencia} · Empezó a pagar un pedido **[NUEVO]** | `CreditCard` |
| 24 | `pago_aprobado` | MATU | **(1.2)** Se aprobó el pago del pedido {referencia} · Se aprobó el pago de un pedido **[README Q15, ajustado]** | `BadgeCheck` |
| 25 | `pago_anulado` | MATU | **(1.2)** Se devolvió dinero del pago del pedido {referencia} · Se devolvió dinero de un pago **[README Q15, ajustado: el README dice «Se anuló el pago». `pago.anular` es la anulación parcial de ADR-027, y «anuló el pago» se lee como si se hubiera deshecho el pago entero]** | `Undo2` |
| 26 | `pidio_una_copia` | Persona | Pidió una copia de los datos **[ANALISTA]** | `Download` |
| — | Un `tipo` que el cliente no conoce | — | No se muestra, y la pantalla no se rompe | — |

- Si un tipo de persona llega con `quien.tipo: matu`, o al revés, la frase no cambia y la cola sigue a `quien`. Es un defecto del servidor, no de la pantalla.
- **(1.2) Cómo se elige la frase.** Con `finalidad` o `referencia`, la frase precisa; con `null`, la general de la 1.1. La `referencia` va en `cifras`, porque es un número que se dicta («el pedido 4821»). Es la misma del título del pedido en «Sus pedidos» (3.4.8) y del comprobante, así que la persona la encuentra en la misma página.
- `referencia` es `null` en un pedido que no se pagó o que ya no existe (decisión 384): en un borrador, «Armó un pedido» y «Confirmó un pedido» son lo normal.
- Los de insumos (9 a 14, 16 y 17) y los de enlaces (7 y 8) siguen generales: el contrato no trae el nombre, y no se pide (minimización).

**`hay_hechos_sin_asociar: true`.** Al final de la lista, después de «Ver más», va una `Nota tono="rocio"` con `Info`: «Hay cambios antiguos que no podemos mostrar aquí ni en el archivo. Si los necesitas, pídelos a {correo}.» **[ANALISTA, ajustado]**. El texto del analista decía «…que no podemos mostrar aquí.», pero esos hechos tampoco van en el archivo (decisión 356), y la persona creería que están en la descarga. El correo va en `EnlaceEnFrase`, y sin correo configurado queda solo la primera oración. Con `false`, la nota no aparece. Se ve igual con `alcance` `todo` o `lo_tuyo`.

**El historial vacío:** «No hay cambios en los últimos 90 días.» (3.6), y la nota de `hay_hechos_sin_asociar` debajo si corresponde.

#### 3.4.10 «Ver más»

Todo historial muestra primero **20 líneas** (5 en las aperturas de cada enlace y 10 en las compras). Si quedan más **dentro de los 90 días**, al final de su lista va `Boton variante="secundario"` «Ver más» **[aprobado 03-11, `INSUMOS.verMas`]**, al ancho de su texto.
- Al tocarlo se suman 20 más (o 5, o 10). **El foco va a la primera línea nueva**, que lleva `tabIndex={-1}`, y se anuncia «Se agregaron {n} líneas.» **[L 15]** por `role="status"`, como en Quién la vio.
- Cuando ya no quedan, el botón desaparece. Nunca queda un «Ver más» que no hace nada.
- **No pide nada a la API** (decisión 357): todo está en la respuesta que ya llegó. No tiene estado de carga.
- **Lo anterior a 90 días no se muestra** (D-54-9 a): queda en el archivo, y la frase de los 90 días lo dice. El contrato propone que «Ver más» siga más allá de los 90 días. Es una contradicción con D-54-9 que no resuelvo yo (10.1). Si se decide como dice el contrato, el único cambio es quitar el corte de 90 días a «Ver más» y la frase pasa a «Primero ves los últimos 90 días.».

### 3.5 Autorización retirada, en pausa o borrada (D-54-5)

En lugar del contenido de «Su ficha» o de «Sus insumos» va una `Nota`, con el estado y, si la hay, la fecha de borrado (`borrado_el`). Es el «bloque que reemplaza a la ficha» que el analista dejó para el diseñador.

```
│ Su ficha                           │  h2
│ ┌┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┐ │  Nota tono="rocio", borde punteado
│ ┆ ⛨ La autorización de la ficha  ┆ │  ShieldOff size-5 text-turquesa
│ ┆   está retirada. Lo escrito    ┆ │
│ ┆   sigue guardado sin que nadie ┆ │
│ ┆   lo pueda leer, y se borra el ┆ │
│ ┆   10/02/2027.                  ┆ │  fecha en cifras
│ └┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘ │
```

| `estado` | Ficha | Insumos | Ícono | Borde |
|---|---|---|---|---|
| `retirada` | La autorización de la ficha está retirada. Lo escrito sigue guardado sin que nadie lo pueda leer, y se borra el {borrado_el}. **[ANALISTA]** | La autorización de los insumos está retirada. Lo anotado se borra el {borrado_el}. **[ANALISTA]** | `ShieldOff` | Punteado |
| `en_pausa` | La ficha está en pausa porque falta renovar la autorización. Cuando se renueve, vuelve a aparecer aquí. **[ANALISTA]** | Los insumos están en pausa porque falta renovar la autorización. Cuando se renueve, vuelven a aparecer aquí. **[NUEVO, el molde de la ficha]** | `Hourglass` | No |
| `borrada` | La autorización de la ficha se retiró, y lo escrito ya se borró. **[NUEVO]** | La autorización de los insumos se retiró, y lo anotado ya se borró. **[NUEVO]** | `Trash2` | Punteado |
| `sin_autorizar` | Nadie ha autorizado todavía guardar la ficha de {nombre_pila}. **[NUEVO]** | Nadie ha autorizado todavía calcular los insumos de {nombre_pila}. **[NUEVO]** | `ShieldQuestion` | No |

- `tono="rocio"`, no `atenta` ni `pronto`: no se perdió nada sin aviso, y en esta pantalla no hay nada que hacer. Es el tono de «Se retiró la autorización de la ficha» en Enlaces (MATU-44).
- El borde punteado es el de MATU-44 (`border-2 border-dashed border-borde`). El estado lo dicen la frase y la forma, no el color.
- Con `retirada` y `borrado_el: null` (no debería pasar), se omite «, y se borra el…».
- **Si los insumos no están `disponible`**, «Compras anotadas» y «Avisos de insumos» no se muestran, porque son lo anotado (P4, decisión 354), y salen del índice. La nota de «Sus insumos» vale por los tres.
- «Enlaces de relevo» y «Quién abrió o editó la ficha» se ven igual: no traen texto de la ficha.

### 3.6 Estados de la página

| Estado | Qué se ve | Foco y anuncio |
|---|---|---|
| Cargando | El `Volver` y el `h1`, que ya se puede armar con el nombre de pila que está en memoria, sin la bajada (la hora la da `generado_en`). Debajo, «Cargando…» **[L 26]** en `p role="status"` después de la demora de `useDemora`. Sin esqueletos (DISENO 6) | En el `h1` desde el principio |
| Listo | Lo de 3.2. La bajada usa `generado_en` | En el `h1` (`tabIndex={-1}`) |
| Error, sin red o 500 | Bajo el `Volver`, `Nota tono="pronto" rol="alert"` con `WifiOff`: «No pudimos traer los datos. Revisa tu conexión y vuelve a intentarlo.» **[ANALISTA]** y `Boton variante="secundario"` «Volver a intentar» **[L 26]**. Sin panel de descarga | A la nota (`enfocable`) |
| 503 (`servicio-no-disponible`) | La misma nota, **(1.2) con `CloudOff` y no `WifiOff`**: el ícono del wifi dice lo mismo que el texto que se quitó. Con «No pudimos traer los datos en este momento. Vuelve a intentarlo en unos minutos.» **[NUEVO]**: no es la conexión de la persona, y decirle que la revise la manda a buscar un problema que no tiene. Con «Volver a intentar» | A la nota |
| 404 | La persona ya no es accesible: se borró, a quien la abre le cambiaron el rol a pagador u observador, o salió del grupo. `Nota tono="rocio"` con `Lock` y el 404 general **[L 8]**, igual que Grupo familiar (MATU-44), y «Volver a Grupo familiar». Al volver, Grupo familiar se vuelve a pedir | A la nota |
| 429 (`tope-copias`) | `Nota tono="atenta" rol="alert"` con `Clock`: «Ya pediste los datos varias veces. Vuelve a intentarlo a las {HH:MM}.» **[ANALISTA, ajustado: la hora sale de `Retry-After`, sumada a la hora de la respuesta. «En una hora» es falso si quedan 5 minutos]**. Sin `Retry-After` legible, el texto del analista: «… Vuelve a intentarlo en una hora.». **Sin «Volver a intentar»**, porque daría otro 429. Solo «Volver a Grupo familiar» | A la nota |
| 401 | Lo resuelve el cliente de la app | — |
| 412 | **No aplica:** es una lectura | — |
| Un bloque vacío | Una frase en `text-base text-tenue` bajo su `h2` **[NUEVO]**: «Todavía no hay enlaces de relevo.» · «Todavía no hay insumos.» · «No hay compras anotadas en los últimos 90 días.» · «No hay avisos en los últimos 90 días.» · «No hay pedidos.» · «No hay cambios en los últimos 90 días.». Las autorizaciones nunca están vacías en una persona con alta: si llega `[]`, «Todavía no hay autorizaciones.» | — |
| Al volver a la página | Se vuelve a pedir, y esa es otra copia: suma una línea al historial y una al límite. **Nada se guarda en el navegador** (C26) | — |

**El 429 va en `atenta` y no en `pronto`:** no se perdió nada, solo hay que esperar (DISENO 6: `pronto` solo si se perdió algo). **Abrir la página es pedir una copia** (P1, decisión 343). Por eso el 429 aparece al abrir, y no al descargar.

### 3.7 Descargar

**El panel** (3.2) lleva, en este orden:
- «Es un archivo (JSON) que otro programa puede leer, para llevar estos datos a otro lugar.» **[ANALISTA]**, en `p text-base max-w-prose`, con `id` para el `aria-describedby` del botón;
- «En esta pantalla, los historiales muestran los últimos 90 días. El archivo trae todo lo guardado.» **[NUEVO]** (D-54-9), en `p text-base text-tenue max-w-prose`;
- `Boton variante="principal"` con el ícono `Download` y «Descargar en un archivo» **[ANALISTA]**, con `aria-describedby` en la ayuda y `angosto:self-stretch`.

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
| Sin la ficha | Si `ficha.estado` no es `disponible` (3.5), la primera oración cambia a «El archivo trae todo lo de esta pantalla, y lo anterior a 90 días.» **[NUEVO]**: no puede prometer lo escrito en la ficha si no va |
| Confirmar | Descargar **[ANALISTA]**, `principal` con `Download` |
| Arrepentirse | No descargar **[ANALISTA]**, `texto` |

**Estados.** Con un solo GET (P1), descargar no llama a la API: **no hay espera, ni error de red, ni 429 dentro del diálogo.**

| Estado | Qué se ve | Foco |
|---|---|---|
| Abierto | Lo de arriba | En el título |
| Entregado | El diálogo se cierra. En el panel, bajo el botón, `Nota tono="ok" enfocable rol="status"`: «Te entregamos el archivo. Búscalo en tus descargas.» **[ANALISTA, ajustado: sin «de tu teléfono», por el computador]**. Se borra al volver a abrir el diálogo | En la nota |
| El navegador no deja crear el archivo (excepción al crear el `Blob` o la URL) | El diálogo sigue abierto, y en su región `role="alert"`, `MensajeError`: «No pudimos armar el archivo en este navegador. Prueba en otro navegador o en un computador.» **[NUEVO]** | En el botón «Descargar» |
| No descargar o Esc | Se cierra sin hacer nada | Vuelve a «Descargar en un archivo» |

**Por qué «Te entregamos» y no «Descargaste»** (aprobado por P9). DISENO 4.6 pide el mismo verbo en el botón y en la confirmación. Aquí no se cumple, a propósito: el navegador no confirma que el archivo se guardó (C20), y «Descargaste el archivo» podría ser falso. «Te entregamos» dice lo único que MATU sabe.

**Cómo se guarda** (decisión 343, C8 y C9, para el frontend):
- la página pidió la copia como texto (`responseType: 'text'`), y la muestra con `JSON.parse`;
- «Descargar» arma un `Blob` con **ese mismo texto** (`application/json`), con `URL.createObjectURL`;
- lo baja con un `<a download>` que no se agrega a la vista, con el nombre del `filename` de `Content-Disposition`: `matu-datos-AAAA-MM-DD.json` en la persona y `matu-cuenta-AAAA-MM-DD.json` en la cuenta (P7). Si la cabecera no se puede leer, arma el mismo nombre con el día de `generado_en`;
- llama a `URL.revokeObjectURL` de inmediato;
- el nombre nunca lleva el nombre de la persona;
- **el texto de la respuesta vive solo en la memoria del componente**, y se suelta al salir de la página.

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
- **Abrir «Tus datos» es pedir una copia** (P1): suma una línea en tus ingresos y una al límite de 10 por hora. La bajada no lo dice, para no asustar. Lo dice la pantalla con su historial.
- **«Cómo pedir» cambia** (ajuste de L 29, revisión previa 7): «Para cambiar tu nombre o tu correo, o eliminar tu cuenta, escribe a {correo} desde el correo de tu cuenta. Para ver o descargar tus datos, entra a «Tus datos».» **[ANALISTA]**. «Tus datos», al final, es texto y no enlace: el botón está más arriba en la misma página.
- **No hay ningún `turquesa` macizo en «Tu cuenta»** (MATU-55, criterio 1). Sigue así.

---

## 5. «Tus datos» (`/cuenta/datos`)

**Objetivo, desde Rodrigo:** «Quiero ver qué guarda MATU de mí, también de lo que pagué, y llevármelo si lo necesito.»

### 5.1 Jerarquía

1. El `h1` «Tus datos» y su bajada: «Lo que MATU guarda hoy de tu cuenta, al {DD/MM/AAAA} a las {HH:MM}.» **[NUEVO, el molde de «Datos de»]**, con `generado_en`.
2. El panel de descarga, igual que en 3.7, con el único macizo.
3. La nota que manda a «Grupo familiar» para los datos de las personas cuidadas.
4. El índice (P11), con el patrón de 3.3.
5. Los bloques, en este orden:
   1. Tu cuenta (`cuenta`)
   2. Política de privacidad (`politica`)
   3. Tus grupos (`grupos`)
   4. Tus teléfonos y computadores (`dispositivos`)
   5. Últimos ingresos (`eventos`)
   6. Tus avisos (`preferencia_avisos`)
   7. Avisos que te enviamos (`avisos_enviados`)
   8. Tus pagos (`pagos`), solo si hay alguno
   9. Condiciones de compra que aceptaste (`condiciones_aceptadas`), solo si hay alguna **[NUEVO, el contrato las trae aparte]**

Con `pagos: null` y `condiciones_aceptadas: null` (la capa 3 quitada), los dos últimos bloques no existen.

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
│ │ Cuenta creada · 02/11/2026     │ │
│ └────────────────────────────────┘ │
│                                    │
│ Política de privacidad             │  h2
│ Aceptaste la versión 0.16 el       │  p text-base
│ 02/11/2026 a las 18:15.            │
│ Huella: 3f9a…c21b                  │  text-base text-tenue, break-all
│                                    │
│ Tus grupos                         │  h2
│ • Familia Soto · Administra el     │  ul, rol en palabra [MATU-53 5.3]
│   grupo · Te uniste el 02/11/2026  │
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
│ Condiciones de compra que aceptaste│  h2, solo si aceptaste
└────────────────────────────────────┘
```

**Pantalla ancha:** la misma composición de 3.3, con el panel arriba y la grilla del índice debajo.

### 5.3 Los bloques

| Bloque | Contenido | Componentes y textos |
|---|---|---|
| **Tu cuenta** (`cuenta`) | Nombre, correo, celular, si está confirmado, el canal de los códigos y la creación | `dl` como el de «Tu cuenta», con `dt text-base text-tenue`. Rótulos: «Tu nombre» **[NUEVO]**, «Tu correo» y «Tu celular» **[L 29, los de «Tu cuenta»]**, «Los códigos te llegan» **[NUEVO]** con «Por SMS» o «Por WhatsApp» **[NUEVO, con las palabras de L 19]**, y «Cuenta creada» **[NUEVO]** con el día de `creada_en`. **El celular, enmascarado** (P3): la API lo manda completo en E.164, y la pantalla lo muestra como «Tu cuenta», con `celularEnPantalla` (MATU-57), su `Etiqueta` de confirmado según `celular_confirmado` y «Completo en el archivo.» **[NUEVO]** en `text-tenue` debajo. Con `celular: null`, el texto de «Tu cuenta» (`CUENTA_PROPIA.sinCelular`) y sin la frase del archivo |
| **Política de privacidad** (`politica`) | Versión, fecha y huella | «Aceptaste la versión {version} el {aceptada_en}.» **[NUEVO]**. «Huella: {huella}» **[NUEVO]** en `text-base text-tenue` con `break-all`: es una cadena sin palabras, y aquí sí se puede partir en cualquier punto. Con `politica: null`: «No hay una aceptación registrada.» **[NUEVO]** |
| **Tus grupos** (`grupos`) | Nombre, rol, fecha de unión y el permiso del pagador | `ul`, una `li` por grupo: el `nombre` en `font-bold break-words`; el `rol` en palabra, «Administra el grupo» · «Cuida» · «Paga» · «Se informa» **[MATU-53, 5.3]**; «Te uniste el {unido_en}.» **[NUEVO]**; y, si `puede_ver_ficha` no es `null`, «Puede ver la ficha» o «No ve la ficha» con `Eye` o `EyeOff` **[MATU-53, 5.3]** |
| **Tus teléfonos y computadores** (`dispositivos`) | Todos los guardados, también los cerrados | La `ul` de `FilaDispositivo` (MATU-55, 2.4), **sin acciones y sin la marca del actual**: el contrato no trae `actual`, y aquí no se cierra nada. El ícono sale de `clase`. Debajo del nombre: «Desde el {creado_en}.» **[NUEVO]**, «Última vez: {ultimo_uso_en}» **[L 13.3]** con la fecha absoluta, y si `cerrado_en` no es `null`, «Se cerró el {cerrado_en}.» **[NUEVO]** con `Etiqueta` neutra y `Circle`. Con `avisos_activos: true`: «Recibe avisos.» **[NUEVO]** con `Bell`. Al pie, `Boton variante="texto"` «Ver dónde entraste» **[MATU-55, 3.5]** a `/cuenta/donde-entraste`, para quien quiera cerrar alguno |
| **Últimos ingresos** (`eventos`) | Los eventos de seguridad, más `pediste_una_copia` | La frase de los 90 días (3.4.9) y el `ol` de `LineaIngreso` (MATU-55, 2.5), agrupado por día, con «Ver más» (3.4.10). Los diez tipos de MATU-55 con sus frases, y `pediste_una_copia` con la fila de 5.5. **Sin «(este teléfono)»**, porque el contrato no trae `actual`. **Sin** la ayuda «¿No reconoces un ingreso?»: vive en «Dónde entraste» |
| **Tus avisos** (`preferencia_avisos`) | La preferencia | Un `dl` con «Por correo» y «En tus teléfonos» **[L 20, con el ajuste de MATU-55]**, y «Sí» o «No» **[NUEVO]**. Al pie, «Puedes cambiarlos en Tu cuenta.» **[NUEVO]** |
| **Avisos que te enviamos** (`avisos_enviados`) | Fecha, canal y resultado | Ver 5.4 |
| **Tus pagos** (`pagos`) | D-54-16 | Ver 5.4 |
| **Condiciones de compra que aceptaste** (`condiciones_aceptadas`) | D-54-16 | Ver 5.4 |

**Nunca** la contraseña, el doble factor, la huella del correo, nada de las sesiones ni nada de una persona cuidada. «Tus datos» no nombra a María en ningún lugar (P5).

### 5.4 «Avisos que te enviamos», «Tus pagos» y las condiciones

**Avisos que te enviamos** (`avisos_enviados`):
- bajo el `h2`, la frase de los 90 días (3.4.9);
- con `envio_simulado: true`, arriba de la lista y **una sola vez**: `Nota tono="atenta"` con `Info`, «En el piloto los avisos se prueban sin enviarse: aparecen aquí, pero no te llegaron.» **[ANALISTA]**. Es el rótulo del piloto de DISENO 3 y el mismo tono de la nota de avisos de «Tu cuenta». Con `false`, no aparece;
- un `ol` con una `li` por aviso: «{fecha} a las {hora} · {canal} · {resultado}» **[ANALISTA]**, en `text-base tabular-nums`, con el ícono del resultado delante, en `size-5 shrink-0 text-tenue aria-hidden`. La fecha es `enviado_en` o, si es `null`, `creado_en`;
- **nunca** el texto del aviso ni a dónde se envió (C16). El contrato no los trae.

| `resultado` | Palabra | Ícono |
|---|---|---|
| `salio` | Salió **[ANALISTA]** | `Check` |
| `no_salio` | No salió **[ANALISTA]** | `X` |
| `en_el_piloto_no_salio` | En el piloto no salió **[ANALISTA, D-54-11]** | `CircleDashed` |
| `pendiente` | Todavía no sale **[NUEVO]** | `Clock` |

| `canal` | Palabra |
|---|---|
| `correo` | Por correo **[L 20]** |
| `push` | En tus teléfonos **[MATU-55, ajuste de L 20]** |
| `sms` | Por SMS **[NUEVO]** |

- Ninguna línea va en `pronto` ni en `ok`: el ícono va en `tenue` y el texto en `tinta`. «No salió» no es una alarma, y «Salió» no es un logro. El estado lo dice la palabra, y la forma del ícono lo acompaña.
- **«Salió» no se deduce:** la pantalla usa el `resultado` del servidor (D-54-11, decisión 359).

**Tus pagos** (`pagos`, D-54-16), solo si la lista tiene alguno. Una `ul` con una `li` por pago:

```
│ Pago 4821                          │  h3 text-lg font-bold
│ 08/11/2026 a las 11:24             │  text-base text-tenue
│ $37.260 en Familia Soto            │  text-base, monto en cifras
│ Tarjeta de crédito terminada en    │  text-base
│ 4242 · 3 cuotas                    │
│ Devuelto: $5.290                   │  solo si devuelto > 0
│ Pago de prueba: no se cobró dinero │  font-bold, con pago_de_prueba
│ real.                              │
```

| Parte | Texto |
|---|---|
| Título | Pago {referencia} **[NUEVO]**, con la referencia del comprobante en `cifras` |
| Cuándo | {pagado_en}, en `text-tenue` |
| Monto | {cobrado} en {grupo} **[NUEVO]**: lo cobrado, con IVA incluido y sin línea de IVA. Nunca la persona (P5) |
| Tarjeta | Según `tarjeta.tipo`: «Tarjeta de crédito terminada en {ultimos4}», «Tarjeta de débito terminada en {ultimos4}» o «Tarjeta de prepago terminada en {ultimos4}» **[NUEVO]**, y « · {cuotas} cuotas» si `cuotas` es 2 o más, o « · Sin cuotas» **[NUEVO]**. Los cuatro dígitos en `cifras`. Con `tarjeta: null`: «Sin datos de la tarjeta.» **[NUEVO]**. **(1.2)** El espacio antes del «·» es no separable, para que un renglón nunca empiece con el punto (P3-4) |
| Devolución | Devuelto: {devuelto} **[NUEVO]**, solo si es mayor que 0 |
| Piloto | Con `pago_de_prueba: true`: «Pago de prueba: no se cobró dinero real.» (3.4.8), en `font-bold` |

**Nunca** el token, la orden, la sesión de pago ni el código de autorización (D-54-16). El contrato no los trae.

**Condiciones de compra que aceptaste** (`condiciones_aceptadas`). Una `ul` con una `li` por aceptación:
- «Versión {version}, el {aceptadas_en}.» **[NUEVO]** en `font-bold`;
- «En {grupo}, para el pedido {referencia}.» **[NUEVO]** o, con `referencia: null`, «En {grupo}, para un pedido que no se pagó.» **[NUEVO]**;
- «Huella: {huella}» en `text-tenue break-all`, como en la política.

### 5.5 `pediste_una_copia`, en «Tus datos» y en «Dónde entraste»

Es una fila nueva de la tabla de `LineaIngreso` (MATU-55, 2.5):

| `tipo` | Frase | Ícono lucide | Círculo |
|---|---|---|---|
| `pediste_una_copia` | Pediste una copia de tus datos **[NUEVO]** | `Download` | `bg-rocio text-turquesa` |

- La cola dice solo «a las {HH:MM}», como los tipos de la cuenta que no nombran el dispositivo (MATU-55, 2.5).
- **Solo «de tus datos».** El evento es `cuenta.datos_descargar`: la copia de la persona (`persona.datos_descargar`) es una acción del grupo y no entra en la lista de la cuenta (decisión 358). «Pediste una copia de los datos de {nombre}» no se puede construir con el contrato, y además pondría el nombre de una persona cuidada en «Tus datos», que no lleva nada de ella. Esa copia ya se ve en el historial de «Datos de» como «Pidió una copia de los datos».
- **En «Tus datos»** la fila se ve con lo que manda `eventos`.
- **En «Dónde entraste»** (`GET /v1/yo/ingresos`) la fila se agrega si el contrato de MATU-55 suma el tipo. Hoy el README dice que **no** (Q11). Es la contradicción de 10.1. Mientras no se resuelva, el frontend agrega la fila a la tabla de frases, y un tipo que la API no manda simplemente no aparece: no hay que construir nada condicional.
- Por qué la quiero también en «Dónde entraste»: es la lista que Carmen revisa cuando sospecha de un uso extraño, y una copia pedida desde otro teléfono es justo eso. Pero no lo decido yo.

### 5.6 Estados

Los de 3.6, con estos cambios:
- el error, el 503 y el 429 dicen lo mismo. El límite es por cuenta y **vale para las dos copias juntas** (decisión 346): tres «Datos de» y siete «Tus datos» ya son diez;
- **no hay 404** (decisión 345). Si llega uno, es un defecto y se trata como el error;
- **sin autorizaciones**: «Tus datos» no tiene bloques que dependan de una autorización;
- bloques vacíos: «No hay ingresos en los últimos 90 días.» **[MATU-55, 2.7]**, «No hay avisos en los últimos 90 días.» y «Todavía no hay teléfonos ni computadores.» **[NUEVO]**. Los grupos vacíos son posibles (una cuenta que salió de su único grupo): «No estás en ningún grupo.» **[NUEVO]**. Sin pagos ni condiciones, esos bloques no aparecen.

El diálogo «Antes de descargar» es el de 3.7, con este texto: «El archivo trae tu correo y tu celular completos. Queda en tu teléfono o computador, fuera de MATU.» **[ANALISTA, ajustado: «o computador», como en 3.7]**. No lleva la oración sobre el relevo, porque «Tus datos» no trae la ficha.

---

## 6. Tokens y componentes

**Sin tokens nuevos.** Se usan:
- los colores `papel`, `hoja`, `tinta`, `tenue`, `turquesa` (el único macizo, el foco y el texto de acción), `rocio`, `linea`, `borde` (el borde punteado), `atenta` y `atenta-fondo` (el 429 y los rótulos del piloto), `pronto` y `pronto-fondo` (solo el error de carga) y `ok` y `ok-fondo` (solo «Te entregamos el archivo»);
- los radios `rounded-xl`, `rounded-2xl` (el diálogo) y `rounded-full`;
- las variantes `angosto:`, `telefono:`, `@3xl/main:` y `@4xl/main:`;
- la medida fija de 12 rem de Grupo familiar y `var(--container-xs)` del índice de `/privacidad`, sin medidas nuevas.

**Componentes:**
- los que hay: `Pagina`, `Volver`, `Nota`, `Etiqueta`, `Boton` (`principal`, `secundario` y `texto`), `MensajeError`, `EnlaceEnFrase`, `DialogoConfirmar`, `PreciosDeEjemplo`, `LineaApertura`, `LineaIngreso`, `FilaDispositivo` (sin acciones ni marca del actual) y el índice de `/privacidad`;
- **conviene sacar el índice de `PaginaPrivacidad` a un componente**, por ejemplo `IndicePagina`, en vez de copiarlo. Las clases no cambian;
- dos nuevos: `PanelDescarga` (3.7, el mismo en las dos pantallas) y `LineaHistorial` (3.4.9, el molde de `LineaIngreso` con la cola «a las {HH:MM} · {nombre}»).

**Nada escrito a mano:** ni colores, ni `size-[…]`, ni sombras, ni `text-sm` o `text-xs`.

---

## 7. Accesibilidad

- **17 px:** ningún texto bajo `text-base`: ni los `dt`, ni las colas de las líneas, ni la huella, ni los precios.
- **48 px:** miden `min-h-12`:
  - «Ver los datos de…», «Ver tus datos» y «Descargar en un archivo»;
  - en el diálogo, «Descargar» y «No descargar»;
  - «Ver más», «Volver a intentar», «Ir a Grupo familiar» y «Ver dónde entraste»;
  - el `summary` del índice y los enlaces del índice.

  El correo usa el `::after` de DISENO 6.
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
  - las autorizaciones llevan palabra e ícono propio, y la retirada y la borrada llevan además borde punteado;
  - los avisos enviados, palabra e ícono (`Check`, `X`, `CircleDashed`, `Clock`), todos en `tenue`;
  - las líneas del historial, frase e ícono;
  - el insumo que ya no se sigue y el dispositivo cerrado, palabra y `Circle`.
- **Anuncios:** «Cargando…», «Se agregaron {n} líneas.» y «Te entregamos el archivo…» van por `role="status"`; el error, el 503 y el 429, por `role="alert"`, con las regiones vivas de `Anuncios`.
- **Reflujo a 320 px con el texto al 200 %:**
  - los nombres, las direcciones, los textos de la ficha y los productos van en `break-words`;
  - las huellas van en `break-all`, y el correo en `[overflow-wrap:anywhere]`;
  - la fecha y la hora van en dos `cifras`;
  - los íconos de las líneas se apilan y la tabla de productos pasa a una columna en el modo `angosto`;
  - sin desplazamiento horizontal.
- **Movimiento:** nada se anima. El chevron del índice gira sin transición (MATU-75). Con `prefers-reduced-motion` no cambia nada.
- **Datos** (C26): nada de estas pantallas va a `localStorage`, `sessionStorage`, `history.state`, la URL ni `document.title`. El texto de la respuesta vive solo en la memoria del componente, y el `Blob` se revoca de inmediato.

---

## 8. Criterios visuales verificables

1. En `/grupo/datos` y en `/cuenta/datos`, el único elemento en `turquesa` macizo es «Descargar en un archivo». Dentro del diálogo, el único macizo es «Descargar».
2. En `/grupo` y en `/cuenta` no aparece ningún macizo nuevo. «Ver los datos de…» y «Ver tus datos» son `secundario`.
3. En Grupo familiar, el bloque «Datos de {nombre_pila}» va entre los permisos y «Borrar sus datos». El pagador y el observador ven la frase de quién puede, sin botón.
4. Ni la URL ni el título de la pestaña llevan el nombre de la persona, ni ningún id. El título es «Datos guardados · MATU» o «Tus datos · MATU».
5. Tocar «Descargar en un archivo» nunca descarga directo: siempre abre «Antes de descargar», con el foco en su título. **Descargar no hace ninguna petición a la API** (se ve en la pestaña de red).
6. El archivo descargado se llama `matu-datos-AAAA-MM-DD.json` o `matu-cuenta-AAAA-MM-DD.json`, sin el nombre de la persona, y su contenido es idéntico, byte a byte, al cuerpo de la respuesta.
7. Con la ficha `retirada`, «Su ficha» muestra solo la nota con `ShieldOff`, borde punteado y la fecha de borrado, sin ningún texto de la ficha. Con `en_pausa`, la nota con `Hourglass` y sin borde punteado. Con `borrada`, la nota con `Trash2` y borde punteado.
8. Con los insumos en cualquier estado que no sea `disponible`, no se ven «Compras anotadas» ni «Avisos de insumos», ni en la página ni en el índice.
9. Ningún historial muestra una línea de hace más de 90 días (mientras no se resuelva 10.1). «Ver más» suma líneas sin pedir nada a la API y desaparece cuando no quedan.
10. Las 26 frases del historial existen en `lenguaje.md` 35, y un `tipo` desconocido no rompe la página. Los cuatro hechos de MATU llevan la cola sin nombre.
11. Con `hay_hechos_sin_asociar: true` se ve la nota «Hay cambios antiguos que no podemos mostrar aquí ni en el archivo…». Con `false` no se ve.
12. Ningún aviso simulado dice «Salió». Todos dicen «En el piloto no salió», y la nota del piloto se ve una sola vez.
13. Ningún precio va sin IVA, ni hay una línea «IVA» o «Neto». En «Datos de», ningún pedido muestra la tarjeta, las cuotas, los dígitos ni el teléfono de contacto. `PreciosDeEjemplo` se ve una sola vez en el bloque.
14. En «Tus datos», un pago muestra solo el tipo de tarjeta, las cuotas y los últimos 4 dígitos, nunca una orden, un token o un código, y nunca el nombre de la persona cuidada.
15. En la pantalla de «Tus datos», el celular se ve enmascarado, con «Completo en el archivo.».
16. Ningún bloque muestra el teléfono de un relevo, ni el correo o el celular de otra persona del grupo. «A quién llamar» se ve tal cual se escribió.
17. Con `alcance: lo_tuyo` se ve la nota «Aquí ves solo lo que hiciste tú…». Con `todo` no se ve.
18. El 429 va en `atenta` con `Clock`, dice la hora de `Retry-After` y no tiene «Volver a intentar». El 503 no dice «Revisa tu conexión».
19. Ningún texto mide menos de 17 px. Todo lo tocable mide 48 px o más. A 320 px con el texto al 200 % no hay desplazamiento horizontal, ni con las huellas, el correo o un texto largo de la ficha.
20. Ningún texto dice «exportar», «auditoría», «registro de accesos», «consentimiento», «sesión», «token» ni «usuario». «JSON» aparece solo en la ayuda del panel, entre paréntesis.
21. Al imprimir cualquiera de las dos páginas sale solo «Esta pantalla no se imprime.».
22. Después de descargar, de «Ver más» o de volver a la página anterior, `document.activeElement` nunca es el `body`.
23. En el tema oscuro, las notas de la retirada, del 429 y del piloto mantienen su borde, su ícono y su palabra, y todo texto cumple 4,5:1, porque son tokens con contraste ya medido.
24. **(1.2)** A 360 px sin zoom no hay desplazamiento horizontal, ni con un insumo de una sola palabra de 60 letras (`datos-admin`): `scrollWidth` es igual a `clientWidth`.
25. **(1.2)** A 320 px con el texto al 200 %, ninguna nota se sale de su tarjeta, y ningún título se parte en su última letra.
26. **(1.2)** Las frases del historial con `finalidad` o `referencia` dicen cuál («Dio la autorización de la ficha», «Confirmó el pedido 4821»). Sin ellas, dicen la general.

---

## 9. Textos para `lenguaje.md`, sección 35 («Copia de los datos (MATU-54)»)

Entran todos los **[ANALISTA]** de las secciones 2 a 5 y los que siguen.

**Ajustes a textos del analista y del README:**
1. «No incluimos su teléfono.» → «No incluimos el teléfono de los relevos.» (3.4.4).
2. «Queda en tu teléfono» → «Queda en tu teléfono o computador», en los dos diálogos (3.7 y 5.6).
3. «Te entregamos el archivo. Búscalo en las descargas de tu teléfono.» → «Te entregamos el archivo. Búscalo en tus descargas.» (3.7).
4. «Hay una referencia… pídela a cuidaconmatu@gmail.com.» → con `{correo}` de la política, como todo correo de la app (MATU-55, 2.5).
5. «Ya pediste los datos varias veces. Vuelve a intentarlo en una hora.» → «… Vuelve a intentarlo a las {HH:MM}.», con `Retry-After`. Sin la cabecera, queda el del analista (3.6).
6. `hay_hechos_sin_asociar`: «Hay cambios anteriores que no podemos mostrar aquí. Si los necesitas, pídelos a cuidaconmatu@gmail.com.» (README Q9) → «Hay cambios antiguos que no podemos mostrar aquí ni en el archivo. Si los necesitas, pídelos a {correo}.» (3.4.9).
7. `pago_aprobado`: «Se aprobó el pago» (README Q15) → «Se aprobó el pago de un pedido».
8. `pago_anulado`: «Se anuló el pago» (README Q15) → «Se devolvió dinero de un pago» (3.4.9).

**El `aviso` fijo del archivo** (`AvisoCopia`, Q12 del README). Propongo este texto definitivo:

> «Esta es una copia de los datos que MATU guarda, para que puedas conocerlos o llevarlos a otro lugar. No es la ficha para un relevo, y no se usa para compartirla. MATU no guarda esta copia. Este archivo queda donde lo descargaste, fuera de MATU: no vence y MATU no lo puede borrar.» **[AJUSTE del YAML]**

Cambia la última oración: el YAML dice «queda en tu teléfono», que no vale en un computador, y suma «no vence y MATU no lo puede borrar», que es lo que promete el diálogo. Es el mismo texto en las dos copias. Si cambia, cambia también la `const` del YAML.

**[NUEVO]:**
- títulos de pestaña: «Datos guardados · MATU» y «Tus datos · MATU»;
- botón de «Tu cuenta»: «Ver tus datos»;
- bajada de «Tus datos»;
- panel: «En esta pantalla, los historiales muestran los últimos 90 días. El archivo trae todo lo guardado.»;
- historiales: «Los de los últimos 90 días. Lo anterior va en el archivo.» y, sin nada anterior, «Los de los últimos 90 días.»;
- rectificación: «Si algo está mal, escribe a {correo} desde el correo de tu cuenta.»;
- los rótulos, las frases y las palabras de los enumerados de los bloques (3.4.1 a 3.4.8, 5.3 y 5.4), entre ellas los estados del pedido, del pago y de las devoluciones;
- las 26 frases del historial (3.4.9), salvo las tres **[ANALISTA]** y las dos del README ajustadas;
- `pediste_una_copia`: «Pediste una copia de tus datos» (5.5);
- las notas de 3.5 que no son del analista: insumos en pausa, ficha e insumos borrados y sin autorizar;
- el diálogo sin la ficha (3.7) y el error del navegador al armar el archivo;
- el 503: «No pudimos traer los datos en este momento. Vuelve a intentarlo en unos minutos.»;
- los vacíos de 3.6 y 5.6;
- «Completo en el archivo.».

**Ajuste de L 29, «Cómo pedir»:** el del analista, en 4.

---

## 10. Preguntas abiertas para el orquestador

### 10.1 Contradicciones (1.2: resueltas)

| # | Contradicción | Lo que hace esta versión |
|---|---|---|
| C-1 | **«Ver más» y los 90 días.** D-54-9 (a) de Jorge dice «90 días en pantalla y todo en el archivo», y la (b) descartada era «todo en pantalla». La decisión 357 del contrato, y la descripción de `hechos` y `eventos` en el YAML, dicen que «Ver más» muestra el resto, también lo anterior a 90 días. En la práctica eso es la (b) | **Resuelta** por la decisión 383: la pantalla filtra a 90 días y «Ver más» pagina dentro de ellos. Verificado en la revisión: con `datos-historial`, «Ver más» se detiene en 85 líneas y la más vieja es del 26/09/2026 |
| C-2 | **`pediste_una_copia` en «Dónde entraste».** El orquestador lo pide en `/v1/yo/ingresos`. El README, en la Q11, dice que esa ruta **no** lo suma: es un cambio de contrato de MATU-55 | **Resuelta** por la decisión 376: `GET /v1/yo/ingresos` suma `pediste_una_copia`, solo para la copia de «Tus datos». Verificado en «Dónde entraste» (12) |
| C-3 | **«… de los datos de {nombre}».** El orquestador lo propone como variante. Con el contrato no se puede: la lista de la cuenta solo trae `cuenta.datos_descargar`, y nombrar a la persona en «Tus datos» choca con la sección 3 del analista («nada de una persona cuidada») | Solo «Pediste una copia de tus datos». La copia de la persona ya se ve en su historial («Pidió una copia de los datos») |

### 10.2 P2: lo que el contrato todavía no trae

Crucé la lista de la 1.0 con el YAML. Trae `generado_en`, los enumerados de estado, la calidad, `PersonaNombrada` y `alcance`. Falta esto:

| # | Falta | Efecto en la pantalla | Lo que recomiendo |
|---|---|---|---|
| F1 | **(1.2: `finalidad` y `referencia`, decisión 384)** El objeto de cada hecho del historial (qué permiso, qué insumo, qué relevo, qué pedido) | Las frases 5 a 25 son generales: «Agregó un insumo», «Dio una autorización». Una persona que revisa no sabe cuál | Sumar a `HechoCopia` un `finalidad` en las autorizaciones y, si la auditoría lo permite sin texto cifrado, la `referencia` del pedido. El nombre del insumo o del relevo puede no estar en la auditoría: si no está, se queda general |
| F2 | **(1.2: no va, decisión 385)** Quién retiró la autorización y el motivo | La 1.0 decía «La retiró {nombre}» y «Motivo: …». La 1.1 dice solo «Se retiró el {fecha}» | Si `consentimiento` guarda quién revocó, sumarlo como `retirada_por: PersonaNombrada`. El motivo no hace falta en pantalla |
| F3 | **Quién cortó un enlace** | La 1.1 dice «Se cortó el {fecha}», sin quién | Lo puede ver en el historial («Cortó un enlace de relevo · Carmen»). No hace falta campo nuevo |
| F4 | **`actual` en los dispositivos y en los eventos de «Tus datos»** | No se marca «Este teléfono» ni «(este teléfono)» | No lo pido: es una copia y no hace falta. Lo dejo dicho para que el frontend no lo busque |
| F5 | **(1.2: `unidad`, decisión 386)** La unidad de cada compra | «{unidades} de {insumo}» sin la unidad, salvo que el frontend la cruce con `lista` por nombre | Sumar `unidad` a `CompraCopia`. Cruzar por nombre falla con dos insumos del mismo nombre |
| F6 | **Si hay algo anterior a 90 días** | Lo calcula la pantalla (Q18) | Basta, sin cambio |

### 10.3 Otras preguntas

| # | Pregunta | Lo que recomiendo |
|---|---|---|
| P13 | **Las palabras del estado del pedido.** No hay palabras aprobadas para casi ninguno de los 17 valores, y la 1.1 propone 11 palabras que juntan estados (3.4.8) | Que Jorge apruebe la tabla con la sección 35. Cuando MATU-63 o la historia del despacho fije sus palabras, esta tabla las toma |
| P14 | **El `aviso` fijo** (Q12). Propongo un texto que cambia la última oración del YAML (9) | Que Jorge lo apruebe, y el backend cambia la `const` en el mismo PR |
| P15 | **Abrir la página es pedir una copia** (P1). Quien entra a mirar dos veces gasta dos de diez, y su historial muestra dos «Pidió una copia de los datos» | Aceptarlo, porque es lo honesto: sí se leyeron todos los datos. Si molesta en las pruebas de usabilidad de Martín, se revisa |

---

## 11. Cómo la voy a revisar

La voy a revisar funcionando, con capturas a 360, 1280 y 1920 px, en tema claro y oscuro, y a 320 px con el texto al 200 %. El recorrido, con datos sintéticos (Carmen, María, Rosa y Rodrigo):
1. Como Carmen (admin), entrar desde Grupo familiar a «Datos de María» y recorrer los nueve bloques con el índice, en el teléfono y en la pantalla ancha.
2. Ver al menos un hecho de cada familia del historial (ficha, autorización, enlace, insumo, compra, aviso, pedido, pago y copia), uno de MATU y uno de alguien que ya no está en el grupo.
3. «Ver más» en el historial y en las aperturas de un enlace, mirando el foco.
4. Abrir «Antes de descargar», cerrarlo con «No descargar» y con Esc, y descargar. Revisar en la pestaña de red que no haya otra petición, el nombre del archivo, que el contenido sea el de la respuesta y que no quede nada en el almacenamiento del navegador.
5. Retirar la autorización de la ficha y la de insumos, y volver a la página: las notas de 3.5, sin texto ni compras.
6. Con una cuenta sintética de rol «Cuida»: la nota de `lo_tuyo`. Como Rodrigo (pagador): la frase sin botón en Grupo familiar.
7. Como Rodrigo, «Tus datos» con un pago y sus condiciones, la tarjeta en sus últimos 4 dígitos, el celular enmascarado y los avisos en «En el piloto no salió».
8. Pedir once copias en una hora, sumando las dos rutas: el 429 con la hora.
9. Sin red, y con el backend sin Redis: el error y el 503.
10. Imprimir las dos páginas.

En el iPhone real lo prueba Martín (P10): la descarga en Safari. Si Safari abre una vista previa del JSON en vez de guardarlo, el texto de éxito suma «En iPhone, toca Compartir y elige «Guardar en Archivos».» **[NUEVO]**, solo en iOS.


---

## 12. Revisión visual del 12-11-2026 (HEAD a12f8b5)

**Cómo se miró.**
- La app de `wt62/web` corrió en una instancia propia (puerto 5193), con el doble, para que el límite de 10 copias por hora no se cruzara con quien usaba el 5183.
- **Chrome 157**, con Playwright: 360, 1280 y 1920 px en tema claro y oscuro, y 320 px con el texto al 200 % aplicado al cargar (`html{font-size:212,5 %}`), también en los dos temas.
- **Firefox 160**, con el Firefox instalado y WebDriver BiDi (Puppeteer): las mismas medidas y la misma matriz.
  - El Firefox de Playwright no corre en este equipo («Permission denied» al ejecutarlo).
  - Por BiDi no se puede emular el tema, así que todas las capturas de Firefox salieron en el tema oscuro del sistema. El tema claro se miró solo en Chrome.
- Las capturas quedan en el scratchpad (`capturas54/`), no en el repositorio.

**Lo que pasa** (sin hallazgo):
- 17 px en todo lo nuevo, en los dos navegadores. Lo único bajo 17 px es «Cuidas a» de la cabecera, que es de la app y no de esta historia.
- 48 px en todo lo que se toca. Los enlaces del índice miden 51 px, y el correo usa el `::after`.
- El diálogo:
  - abre con el foco en «Antes de descargar»;
  - Esc y «No descargar» devuelven el foco a «Descargar en un archivo»;
  - **descargar no hace ninguna petición** (cero GET nuevos a `/datos`);
  - el archivo se llama `matu-datos-2026-11-12.json`, y es JSON válido con `formato: matu-datos/1`;
  - el foco queda en «Te entregamos el archivo…».
- Nada en `localStorage`, `sessionStorage` ni `history.state`. El título es «Datos guardados · MATU».
- «Ver más» lleva el foco a la primera línea nueva y se detiene dentro de los 90 días.
- El 429 dice la hora con `Retry-After` («a las 12:01»), va en `atenta` con `Clock`, no tiene «Volver a intentar» y se lleva el foco.
- El 503 dice «… en este momento…» y tiene «Volver a intentar». El 404 (simulado con una ruta interceptada) muestra el 404 general con `Lock`.
- Con `datos-lento`, «Cargando…» aparece con el `h1` ya armado y el foco en el `h1`.
- `retirada`, `en_pausa`, `borrada` y `sin_autorizar` se ven con su ícono, su borde y su texto. Con los insumos sin autorizar, compras y avisos salen también del índice. Sin capa 3, no hay «Sus pedidos».
- `lo_tuyo` muestra su nota, y `hay_hechos_sin_asociar` la suya.
- Al volver, el foco va a «Ver los datos de María» y a «Ver tus datos».
- En Grupo familiar:
  - el bloque va entre los permisos y «Borrar sus datos»;
  - el pagador y el observador ven la frase sin botón;
  - «Cómo pedir» tiene el texto del analista.
- «Pediste una copia de tus datos» aparece en «Dónde entraste» después de abrir «Tus datos».
- En «Tus datos», el celular sale enmascarado con «Completo en el archivo.», el aviso simulado dice «En el piloto no salió» y la tarjeta muestra solo el tipo, los 4 dígitos y las cuotas.

### «Datos de María» (`/grupo/datos`)

| Pantalla y ancho | Hallazgo | Sev. | Corrección |
|---|---|---|---|
| 360 px, sin zoom, claro y oscuro, Chrome y Firefox | **Desplazamiento horizontal de 273 px** (`scrollWidth` 633 en 360). El `h3` del insumo «ToallitasHúmedasExtraGrandesSinPerfumeParaPielSensibleXXL60» mide 599 px. Su `li` es `flex-col items-start`, así que el `h3` toma el ancho de su contenido y `break-words` nunca se aplica. Captura `chrome-z320-insumo-largo.png` | **P1** | Quitar `items-start` de las `li` de los bloques y poner `self-start` solo en la `Etiqueta` y los botones (3.4, 1.2). Con eso basta. Si se quiere dejar `items-start`, `max-w-full` en el `h3` y en los `p` |
| 320 px con el texto al 200 %, Chrome y Firefox | **La nota del representante legal se sale 32 px de su tarjeta y 15 px de la pantalla** (nota de 301 px, con su borde derecho en 320 sobre una tarjeta que termina en 288). Es el ícono al lado más «representante» en una línea. Captura `chrome-z320-nota-rep.png` | **P1** | `iconoEnLinea` en la `Nota`, y que la nota no herede el `items-start` de la `li` (3.4, 1.2) |
| 320 px con el texto al 200 % | **«Autorizaciones» se parte en «Autorizacione / s».** El `h2`, de 42,5 px, no cabe en 286 px. Lo mismo puede pasar con «Condiciones de compra…» y otros títulos. Captura `chrome-z320-h2.png` | **P2** | `hyphens-auto` en los `h2` y los `h3` de las dos páginas (`lang="es-CL"` ya está) |
| 360 px, «Enlaces de relevo» | Las aperturas dicen «hoy a las 10:09» y, en la misma tarjeta, «Se abrió una vez, el 12/11/2026 a las 10:09». Son dos formas de la misma fecha | P3 | `completa` en `LineaApertura` (3.4.4, 1.2) |
| 360 px, «Compras anotadas» | «20 de Pañal adulto talla M»: falta la unidad, que el contrato ya trae (decisión 386) | P3 | «{unidades} {unidad} de {insumo}» (3.4.6, 1.2) |
| 360 px, «Su ficha» | Los campos dicen «Lo escribió Carmen Soto» y las secciones «Lo escribió Carmen» | P3 | Usar `escrito_por.nombre` en los dos. Si el doble manda distinto, corregir el doble |
| Todos, error | El 503 usa `WifiOff`, que dice «revisa tu conexión», lo mismo que su texto evita decir | P3 | `CloudOff` (3.6, 1.2) |
| 360 px, historial | Las frases de autorizaciones y pedidos son las generales, aunque el contrato ya trae `finalidad` y `referencia` | P3 | Las frases de 3.4.9 (1.2) |
| Todos | Los estados del pedido usan todos la misma figura (`Circle`) | P3 | No bloquea, porque la palabra dice el estado. Si se quiere forma, `Check` para «Entregado» y `CircleX` para «Cancelado» y «Venció sin pagar». Queda a criterio del frontend, sin texto nuevo |

**Veredicto: CAMBIOS REQUERIDOS** (dos P1 de reflujo y un P2).

### «Tus datos» (`/cuenta/datos`)

| Pantalla y ancho | Hallazgo | Sev. | Corrección |
|---|---|---|---|
| 360 px, «Tus pagos» | «Tarjeta de crédito terminada en 4242» y, en el renglón siguiente, «· 3 cuotas»: el renglón empieza con el punto | P3 | Espacio no separable antes del «·» (5.4, 1.2) |
| 360 px, «Avisos que te enviamos» | El aviso `pendiente` del 12/11 sale después de uno del 07/11. La pantalla respeta el orden del servidor, así que es el orden del doble | P3 | Revisar el orden del doble. El frontend no reordena |

Sin desplazamiento horizontal a 360 ni a 320 px con el texto al 200 %, en los dos navegadores. **Veredicto: APROBADA.** Los P3 se arreglan en la misma vuelta.

### Las entradas y «Dónde entraste»

| Pantalla | Veredicto |
|---|---|
| Grupo familiar, bloque «Datos de {nombre}» (admin, pagador y observador) | **APROBADA** |
| Tu cuenta, tarjeta «Tus datos» y «Cómo pedir» | **APROBADA** |
| Dónde entraste, «Pediste una copia de tus datos» | **APROBADA** |

**Lo que queda por mirar después de la corrección:**
- «Datos de María» a 360 px sin zoom y a 320 px con el texto al 200 %, en los dos navegadores;
- la descarga en un iPhone real, que la prueba Martín (P10).

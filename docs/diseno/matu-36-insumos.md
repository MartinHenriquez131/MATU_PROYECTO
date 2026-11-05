# MATU-36 · Insumos de la app de familia · Especificación de diseño

**Versión 1.0 · 03/11/2026** · agente 6 (UI/UX) · para el frontend, antes de construir
**Historia:** MATU-36, perfil de consumo (RF-10, RF-11). La familia anota cuánto se usa de cada insumo y cuánto queda, y MATU calcula hasta cuándo alcanza.
**Dónde se construye:** `web/`, React 19, TypeScript, Vite y Tailwind CSS v4 (ADR-026), mobile first. Va **dentro del esqueleto de navegación de MATU-39**, que todavía no existe (sección 2.1).

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` (especificación de MATU-23, sección 6) · la pantalla de insumos de la demo (`Demo/src/familia/Insumos.tsx`, «Qué se acaba») y el paso del permiso del alta (`Demo/src/familia/Alta.tsx`, paso 3, y `Demo/src/demo/datos.ts`, `CALIDADES` y `AVISO_CUIDADOR`) · `docs/lenguaje.md` del repositorio MATU (secciones 2, 3, 6 y 8) · checklist de accesibilidad de `docs/estrategia-pruebas.md`, sección 7 · contrato `docs/api/propuestos/app-familia.openapi.yaml` y `docs/api/README.md` (decisiones 37 a 63).

**Cómo se lee:** los textos entre comillas latinas «» van tal cual. **[APROBADO 02-11]** son los que Jorge aprobó el 02-11. **[aprobado por Jorge el 03-11]** son los que Jorge aprobó el 03-11 (antes [PROPUESTO]); entran a `lenguaje.md` en el mismo pull request (lenguaje, sección 12). Las llaves son datos de la API: `{pila}` = el nombre de pila de la persona cuidada (`GET /v1/grupos/{grupo_id}/personas-cuidadas`), `{nombre}` = `nombre_libre` (o `producto.nombre` cuando exista el catálogo), `{n}` = `dias_restantes`, `{fecha}` = `fecha_quiebre_estimada` en `DD/MM/AAAA`.

**Lo que se reutiliza de la demo:** el lenguaje visual de «Qué se acaba» (lista en hojas blancas con el nombre en negrita, la cifra en `cifras`, la línea «Le alcanza … hasta el …» y la vista previa en `rocio` con borde `turquesa` del formulario «¿Cuánto usa…?»), el `Stepper`, el estado vacío «Aún no sabemos qué usa {pila}», el `GrupoOpciones` de las calidades y el aviso del cuidador de hecho del alta. **Lo que no:** la barra de 30 días (`BarraDias`), las etiquetas de nivel (`EtiquetaNivel`), «Ya lo compré», la lista de reposición, los precios y el catálogo. Los niveles y la barra son el lenguaje de «Qué se acaba pronto» (MATU-37); la compra es de la capa 3 y de MATU-51. **Al copiar clases de la demo, `pino` se reemplaza por `turquesa`** (MATU-23, 6.1).

---

## 0. Lo que tiene que decidir alguien más

| # | Qué | Por qué importa | Lo que hace la especificación mientras tanto |
|---|---|---|---|
| D1 | ~~La declaración del permiso para el consumo no tiene texto.~~ **Resuelta: Jorge aprobó las tres declaraciones el 03-11** (sección 7.2) | — | La nota «Lo que declaras» usa la declaración aprobada de la calidad elegida |
| D2 | **El 412 del perfil no dice quién guardó.** `actual` es un `PerfilConsumo`, sin `actualizado_por` (en la ficha sí viene) | Lenguaje 6.2 nombra a `{autor}` | Usa la variante sin nombre: «Otra persona» (6.2 ya la prevé). Si se quiere el nombre, falta un campo en el contrato |
| D3 | **Renovar la autorización no existe** (MATU-44) | Lenguaje 6.4b deja pendiente el botón «Renovar la autorización» | Mismo texto que 6.4b, adaptado a los insumos, con «Pídele a quien administra el grupo que la renueve» para todos los roles |
| D4 | ~~Los insumos que ya no se siguen.~~ **Resuelta (Jorge, 03-11):** «Seguir» y «Eliminar» son dos controles separados en cada fila, y los que no se siguen quedan en la misma lista (3.2 y 3.6). **Faltan en el contrato** la ruta para volver a seguir y `DELETE …/consumo/{perfil_id}`: las agrega el backend | — | La pantalla usa los nombres que fije el contrato |
| D5 | ~~Las unidades `ml` y `g`.~~ **Resuelta (Jorge, 03-11):** la app ofrece solo «unidad» y «sobre». La base sigue admitiendo `ml` y `g`, pero no se ofrecen | — | Si un perfil llega con `ml` o `g` (creado por otra vía), se muestra con su unidad («Usa 15 ml al día») y se puede cambiar igual |

---

## 1. Para quién y qué

**Carmen** cuida a María. Quiere saber, sin hacer cuentas, si los pañales alcanzan hasta el lunes. Abre «Insumos» con una mano, anota de vez en cuando cuántos quedan y quiere que MATU le avise antes de que se acaben. No le interesa una fórmula: le interesa una fecha.

**Rodrigo** aporta desde lejos. Puede ser pagador u observador: **solo mira**. Ve la misma lista sin ningún botón para escribir.

**La pantalla** tiene cuatro momentos: **el permiso** (solo la primera vez), **la lista** (con «Seguir» y «Eliminar» en cada fila), **anotar o cambiar un insumo** y **eliminarlo**.

**Decisiones de Jorge del 03-11 incorporadas:** «Seguir» y «Eliminar» separados (D4), solo «unidad» y «sobre» (D5), el stock vacío con ayuda al cambiar, las declaraciones del permiso (D1) y que **todos los miembros del grupo, también el observador, ven el consumo**. Solo `admin` y `cuidador` escriben.

---

## 2. Marco común

### 2.1 Dónde se monta (MATU-39)

- Es la sección **«Insumos»** de la navegación de la familia. La ruta la fija MATU-39. Propuesta: `/insumos` para la lista y `/insumos/nuevo` y `/insumos/{perfil_id}` para el formulario. **Nunca el nombre del insumo ni de la persona en la URL.**
- La pantalla vive dentro del `<main id="contenido">` del esqueleto, con el contenedor `@container/main` y los mismos márgenes de MATU-23 (2.1): `px-4 angosto:px-2 @3xl/app:px-10 pt-6 @3xl/app:pt-14 pb-16`.
- **Mientras MATU-39 no exista**, el frontend la monta en una ruta de desarrollo con el marco de MATU-23 (cabecera con la marca y el distintivo del piloto) y la deja lista para moverla. Si MATU-39 agrega una barra fija abajo, vuelve el `scroll-padding-bottom` de la demo (MATU-23, 6.1) y lo agrego yo a la capa base.
- El rol sale de `GET /v1/grupos` (`rol`) y la persona de `GET /v1/grupos/{grupo_id}/personas-cuidadas`. Este documento no especifica cómo se elige el grupo ni la persona: es de MATU-39.

### 2.2 Título y foco

- Título de la página, `h1` con `id="titulo-pagina" tabIndex={-1}`: «Insumos» en la lista. En el formulario, el título del formulario. Estilo `titular text-3xl @2xl/main:text-5xl angosto:text-2xl outline-none`.
- Al cambiar de momento (permiso → lista → formulario → lista), el foco va al `h1` nuevo. Al volver del formulario a la lista con un aviso de confirmación, el foco va al aviso (`role="status"`) y luego sigue el orden natural.
- `<title>` [aprobado por Jorge el 03-11]: «Insumos · MATU». En el formulario: «Anotar un insumo · MATU» o «Cambiar un insumo · MATU». **Nunca** el nombre del insumo ni de la persona.
- **Sin transiciones entre momentos.** Solo `aparecer` (180 ms) en los avisos de confirmación. Con `prefers-reduced-motion`, inmediato.

### 2.3 Composición en pantalla ancha

Desde `@3xl/main`, dos columnas como «Qué se acaba» en la demo (`Columnas izquierda="ancha"`): la lista a la izquierda (`3fr`) y el formulario a la derecha (`2fr`), con `gap-10` y `items-start`. Sin formulario abierto, la columna derecha muestra la nota de cómo se calcula (3.2). A 360 px y hasta `@3xl/main`, una columna: el formulario **reemplaza** a la lista, con un enlace «Volver a los insumos» arriba.

### 2.4 Roles

| Rol | Ve | Escribe |
|---|---|---|
| `admin`, `cuidador` | Todo | Da el permiso, anota, cambia y deja de seguir |
| `pagador`, `observador` | La lista completa, también los insumos que no se siguen. Todos los miembros ven el consumo (Jorge, 03-11) | **Nada.** Sin «Anotar un insumo», sin «Cambiar», sin la casilla «Seguir» (ven la palabra «Sin seguir» en su lugar) y sin la papelera. No se muestran deshabilitados: no se muestran. Las filas no son botones |

Si un `pagador` u `observador` llega a una ruta de formulario (`/insumos/nuevo`), se le muestra la lista. Si la API responde 404 a una escritura, se aplica el texto de lenguaje 8 para `no-encontrado`.

---

## 3. Pantallas y estados

### 3.0 Cómo se llega a cada uno

```
abre Insumos ─► GET …/consumo
               ├─ 200 con items ─► lista (3.2)
               ├─ 200 sin items ─► vacío (3.3)
               ├─ 403 sin-consentimiento ─► admin/cuidador: permiso (3.1) · otros: falta el permiso (3.1.3)
               ├─ 403 revision-vencida ─► por renovar (3.1.4)
               ├─ 401 ─► renovar sesión una vez (contrato, NoAutenticadoApp) ─► si falla, entrada
               └─ 404, red o 5xx ─► error (3.7)
permiso ─► POST …/consentimientos ─► 201 ─► formulario «Anotar un insumo» (3.4)
                                  ├─ 409 autorizacion-vigente ─► vuelve a pedir la lista
                                  └─ 422 ─► permiso con mensaje (3.1.2)
formulario ─► POST …/consumo (nuevo) o PATCH …/consumo/{id} con If-Match (cambio)
            ├─ 201 / 200 ─► lista con aviso «guardado» (3.4.6)
            ├─ 412 ─► conflicto (3.5)
            ├─ 409 perfil-inactivo ─► ya no se sigue (3.4.5)
            ├─ 422 ─► mensaje en el campo (3.4.5)
            └─ 428 ─► lenguaje 6.3 adaptado (3.4.5)
«Seguir» ─► desmarcar: POST …/desactivar ─► 200 ─► la fila pasa a «Sin seguir» (3.6.1)
         └► marcar: ruta nueva para volver a seguir ─► 200 ─► la fila vuelve a contar días (3.6.1)
papelera ─► confirmación ─► DELETE …/consumo/{perfil_id} ─► 204 o 200 ─► lista con aviso (3.6.2)
```

La pantalla elige el texto **solo por `type`**, y en un 422 por `errores[].campo` y `errores[].tipo`. Nunca muestra `title`, `detail`, `mensaje`, `status` ni `request_id` (lenguaje 8).

**Cargando:** igual que MATU-23, 3.1. Sin esqueleto ni ícono girando. A los 400 ms aparece «Cargando los insumos…» [aprobado por Jorge el 03-11] en `text-lg text-tenue`, `role="status"`, con `aria-busy="true"` en la región.

---

### 3.1 El permiso, en un solo paso

**Objetivo:** Carmen entiende para qué sirve el permiso y lo da en un paso, sin salir de «Insumos».

**Jerarquía:** 1) el título y la explicación de para qué sirve · 2) en qué calidad lo da (las tres opciones) · 3) el aviso del cuidador de hecho, si corresponde, la declaración y «Acepto y continúo».

#### 3.1.1 Pantalla

**Esquema a 360 px:**

```
┌────────────────────────────────────┐
│ (esqueleto MATU-39)                │
├────────────────────────────────────┤
│ Insumos                            │  línea de contexto, text-base tenue
│ Antes de calcular,                 │  h1 titular text-3xl
│ un permiso                         │
│ Para avisarte antes de que se      │  text-lg, max-w-prose
│ acabe algo, MATU guarda qué        │
│ insumos usa María, cuánto usa y    │
│ cuánto queda. Es un permiso aparte │
│ del de su ficha.                   │
│                                    │
│ Doy este permiso porque…           │  legend, font-bold
│ ┌────────────────────────────────┐ │
│ │ ( ) María lo autoriza y yo lo  │ │  GrupoOpciones, una por fila
│ │     registro                   │ │  min-h-12, ring-borde
│ │     María decide por sí misma… │ │
│ ├────────────────────────────────┤ │
│ │ ( ) Soy su representante legal │ │
│ ├────────────────────────────────┤ │
│ │ (•) La cuido, sin              │ │  preseleccionada, como en el alta
│ │     representación legal       │ │
│ └────────────────────────────────┘ │
│ ┃ Aviso: tu autorización tiene un │  atenta-fondo, borde-l-4 atenta
│ ┃ límite                          │
│ ┃ Declaraste que cuidas…          │
│ ┃ [ ] Leí el aviso y lo acepto    │  min-h-12
│ ┌ Lo que declaras ───────────────┐ │  Nota rocio
│ │ Declaro que cuido a esta       │ │  la declaración de la calidad
│ │ persona y que no soy su…       │ │  elegida (7.2)
│ └────────────────────────────────┘ │
│ [ Acepto y continúo ]              │  único turquesa macizo
└────────────────────────────────────┘
```

**Pantalla ancha:** una sola columna de `max-w-3xl`, alineada a la izquierda (no centrada: es un formulario, no un objeto único). Las tres opciones en tres columnas (`GrupoOpciones columnas`, como en el alta) desde `@2xl/main`. Sin la columna derecha de 2.3.

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Insumos                                                                   │
│ Antes de calcular, un permiso                                             │
│ Para avisarte antes de que se acabe algo, MATU guarda qué insumos usa…    │
│ Doy este permiso porque…                                                  │
│ ┌──────────────────────┐┌──────────────────────┐┌──────────────────────┐  │
│ │( ) María lo autoriza ││( ) Soy su represen-  ││(•) La cuido, sin     │  │
│ │    y yo lo registro  ││    tante legal       ││    representación    │  │
│ └──────────────────────┘└──────────────────────┘└──────────────────────┘  │
│ ┃ Aviso: tu autorización tiene un límite …  [ ] Leí el aviso y lo acepto │
│ Lo que declaras …                                                         │
│ [ Acepto y continúo ]                                                     │
└───────────────────────────────────────────────────────────────────────────┘
```

**Componentes:** los del alta en la demo, reconstruidos en `web/`: `GrupoOpciones` (radio nativo, cada opción `min-h-12` con `ring-2 ring-inset ring-borde`, elegida `ring-turquesa bg-rocio`, con un punto relleno además del color), el aviso del cuidador de hecho (`border-l-4 border-atenta bg-atenta-fondo`, casilla `size-5 accent-turquesa` dentro de una etiqueta `min-h-12`), `CampoTexto` para la referencia del documento (`maxLength={200}`), `Nota` en `rocio` y el botón principal.

**Reglas (las del alta, `validar_otorgamiento`):** con `titular`, sin aviso ni referencia. Con `representante_legal`, la referencia es obligatoria. Con `cuidador_de_hecho`, la casilla del aviso es obligatoria y se envía `aviso: { id: "aviso_cuidador_de_hecho", version: "1.0" }`. La validación ocurre **al tocar el botón**, que nunca está deshabilitado (componente `Boton` de `web/`).

**Textos:**

| Parte | Texto | Estado |
|---|---|---|
| Línea de contexto | Insumos | [aprobado por Jorge el 03-11] |
| Título | Antes de calcular, un permiso | [aprobado por Jorge el 03-11] |
| Explicación | Para avisarte antes de que se acabe algo, MATU guarda qué insumos usa `{pila}`, cuánto usa y cuánto queda. Es un permiso aparte del de su ficha. | La primera frase es la aprobada el 02-11 ("Para avisarte antes de que se acabe algo…"). El resto [aprobado por Jorge el 03-11] |
| Leyenda | Doy este permiso porque… | Alta (MATU-07) |
| Opciones | Las tres `CALIDADES` del alta: `texto` y `detalle`, con «Ella» y «María» reemplazados por `{pila}` | Alta (MATU-07) |
| Referencia | «Referencia del documento», ejemplo «Por ejemplo: resolución y fecha» | Alta (MATU-07) |
| Aviso | `AVISO_CUIDADOR` 1.0, título y párrafos tal cual, y «Leí el aviso y lo acepto» | Alta (MATU-07), sirve igual (contrato) |
| Nota | Título «Lo que declaras». Cuerpo: la declaración de la calidad elegida, tal cual (7.2) | Aprobado por Jorge el 03-11 |
| Botón | Acepto y continúo · mientras envía: Guardando el permiso… | Alta (MATU-07) |
| Confirmación (al llegar al formulario) | Permiso guardado. Ahora anota el primer insumo. | [aprobado por Jorge el 03-11] |

**Criterios visuales:** «Acepto y continúo» es el **único** elemento en `turquesa` macizo. La opción elegida se distingue por el punto relleno y el anillo, no solo por el fondo. Ninguna palabra de lenguaje 3.2: no dice "consentimiento" en ningún texto visible.

#### 3.1.2 Errores del permiso

Van en un `MensajeError` (`text-pronto`, ícono `CircleAlert`, `role="alert"`) debajo del grupo o del campo, con `aria-invalid` y `aria-describedby` en el campo.

| Caso | Texto | Estado |
|---|---|---|
| Sin elegir calidad | Elige en qué calidad das el permiso. | Alta |
| Representante sin referencia | Escribe la referencia del documento que te nombra representante. | Alta |
| Cuidador de hecho sin la casilla | Marca que leíste el aviso para seguir. | Alta |
| 422 `regla_calidad_otorgante` o cualquier otro 422 | No pudimos guardar el permiso. Revisa lo que elegiste y vuelve a intentarlo. | [aprobado por Jorge el 03-11] |
| 409 `autorizacion-vigente` | Sin texto: otra persona ya lo dio. Se vuelve a pedir la lista y se sigue | — |

#### 3.1.3 Falta el permiso y quien mira no puede darlo (pagador u observador)

Patrón "una sola columna" de MATU-23 (2.3), alineado a la izquierda, con la baldosa `bg-tinta/7 text-tenue` y el ícono `Lock`:

> **Falta el permiso para calcular los insumos de `{pila}`.** Sin él no podemos mostrar cuándo se acaban. Pídele a quien administra el grupo o a quien cuida a `{pila}` que lo registre.

[aprobado por Jorge el 03-11], hecho con el patrón de lenguaje 6.4. Sin botones.

#### 3.1.4 Autorización por renovar (403 `revision-vencida`)

Mismo patrón, baldosa `bg-atenta-fondo text-atenta` con `Hourglass`. Texto adaptado de lenguaje 6.4b, **[aprobado por Jorge el 03-11]** (6.4b está escrito para la ficha):

> **Hay que renovar la autorización de los insumos de `{pila}`.** Se renueva una vez al año. Mientras tanto, no podemos calcular ni mostrar sus insumos, pero lo que anotaste sigue guardado.
>
> Pídele a quien administra el grupo que la renueve.
>
> [Apoyos del Estado para quienes cuidan](https://www.chileatiende.gob.cl/fichas/112779-persona-cuidadora) (se abre en ChileAtiende)

El enlace, como en MATU-23: `text-turquesa underline`, `min-h-12`, `target="_blank" rel="noopener noreferrer"`. No es un error: sin `role="alert"` y sin rojo. Cuando exista MATU-44, admin y cuidador ven el botón «Renovar la autorización» (6.4b).

---

### 3.2 La lista de insumos

**Objetivo:** Carmen ve, sin hacer cuentas, hasta cuándo alcanza cada insumo, y lo que se acaba primero está arriba.

**Jerarquía:**
1. Los insumos, el que se acaba primero arriba (el orden lo da la API), con su nombre y «Alcanza para {n} días».
2. «Anotar un insumo», el único botón en `turquesa` macizo.
3. La nota de cómo se calcula y, en cada fila, lo que se anotó.

**Esquema a 360 px:**

```
┌────────────────────────────────────┐
│ Insumos                            │  h1
│ ┌ reservado para MATU-37 ────────┐ │  «Qué se acaba pronto»: no se
│ └────────────────────────────────┘ │  construye ahora (3.2.3)
│ Es un cálculo con lo que anotaste. │  text-base tenue, max-w-prose
│ Si compraste o te quedan menos,    │
│ anótalo.                           │
│ [ + Anotar un insumo ]             │  único turquesa macizo
│ ┌────────────────────────────────┐ │  ul, cada li una hoja
│ │ Pañal adulto M                 │ │  font-bold, break-words
│ │ Alcanza para 6 días            │ │  text-xl font-bold, cifra en cifras
│ │ hasta el 06/11/2026            │ │  text-base, fecha en cifras
│ │ Usa 4 al día. Quedaban 24 el   │ │  text-base tenue
│ │ 31/10/2026.                    │ │
│ │                    [ Cambiar ] │ │  secundario, solo admin/cuidador
│ ├────────────────────────────────┤ │
│ │ Toallitas húmedas              │ │
│ │ Alcanza para 16 días           │ │
│ │ …                              │ │
│ └────────────────────────────────┘ │
│ [ Ver más ]                        │  secundario, si siguiente_cursor
└────────────────────────────────────┘
```

**Pantalla ancha (desde `@3xl/main`):** la lista en la columna izquierda (2.3). Cada fila en una sola línea cuando cabe: nombre a la izquierda, «Alcanza para…» y la fecha a la derecha (`flex flex-wrap justify-between gap-x-6`), «Cambiar» al final. La columna derecha muestra, sin formulario abierto, la `Nota` «Cómo calculamos» (3.2.2). Con un formulario abierto, la fila de ese insumo lleva `aria-current="true"` y el anillo `ring-2 ring-inset ring-turquesa`, como la fila elegida en la demo.

```
┌───────────────────────────────────────────────┬───────────────────────────────┐
│ Insumos                    [ + Anotar un insumo ]                             │
│ (reservado MATU-37)                                                           │
│ Es un cálculo con lo que anotaste. Si compraste o te quedan menos, anótalo.   │
│ ┌───────────────────────────────────────────┐ │ ┌ Cómo calculamos ──────────┐ │
│ │ Pañal adulto M    Alcanza para 6 días     │ │ │ Dividimos lo que quedaba  │ │
│ │                   hasta el 06/11/2026     │ │ │ por lo que se usa…        │ │
│ │ Usa 4 al día. Quedaban 24 el 31/10/2026. [Cambiar] │ └──────────────┘ │
│ ├───────────────────────────────────────────┤ │                               │
│ │ Toallitas húmedas Alcanza para 16 días    │ │                               │
│ └───────────────────────────────────────────┘ │                               │
└───────────────────────────────────────────────┴───────────────────────────────┘
```

**Componentes y tokens:**
- Lista: `ul` con `flex flex-col gap-2`. Cada `li` es una hoja: `bg-hoja px-4 angosto:px-2 py-3 ring-1 ring-linea`. **Las filas no son botones**: sus controles son la casilla «Seguir», «Cambiar» y la papelera (3.6), en un renglón propio al pie de la fila (`flex flex-wrap items-center gap-4`).
- Nombre: `font-bold break-words` (un nombre de 60 caracteres sin espacios no debe desbordar a 320 px).
- Línea de días: `text-xl font-bold`, la cifra en `cifras`. A 360 px con texto al 200% baja de renglón por palabras.
- Fecha: `text-base`, «hasta el» y la fecha en `cifras`, con `whitespace-nowrap` solo en la fecha.
- Lo anotado: `text-base text-tenue`.
- «Cambiar»: botón secundario, `min-h-12`, con `aria-label="Cambiar {nombre}"`. A 360 px va a la derecha en su propio renglón (`self-end`).
- «Anotar un insumo»: botón principal con `Plus` (`size-5`, `aria-hidden`). Al ancho de su texto, también en el teléfono (DISENO.md, sección 5).
- «Ver más»: botón secundario, pide la página siguiente con `cursor` y la **agrega** a la lista. El foco va al primer elemento nuevo.

**El estado nunca solo por color.** En MATU-36 no hay niveles de color. Las filas con 0 o menos días cambian la **palabra** y suman la forma: el ícono `CircleAlert` (`size-5`, `aria-hidden`) delante, en `text-atenta`, y el texto en `text-tinta`. Ningún fondo de color en la fila. Los insumos sin seguir se distinguen como dice 3.6.1.

#### 3.2.1 Textos de cada fila

| `dias_restantes` | Línea principal | Línea de la fecha | Estado |
|---|---|---|---|
| 2 o más | Alcanza para `{n}` días | hasta el `{fecha}` | Principal [APROBADO 02-11]. Fecha [aprobado por Jorge el 03-11] |
| 1 | Alcanza para 1 día | hasta el `{fecha}` | [APROBADO 02-11] |
| 0 | Se acaba hoy | — | [APROBADO 02-11] |
| negativo | Puede que ya no quede | Según lo anotado, se acababa el `{fecha}`. | Principal [APROBADO 02-11]. Fecha [aprobado por Jorge el 03-11] |

**Lo anotado**, [aprobado por Jorge el 03-11]:
- Uso: con `tasa_dias = 1`, «Usa `{tasa_unidades}` al día». Con más, «Usa `{tasa_unidades}` cada `{tasa_dias}` días». Con `unidad` distinta de `unidad`, se agrega la unidad: «Usa 15 ml al día», «Usa 1 sobre al día», «Usa 2 sobres al día», «Usa 30 g al día».
- Stock: «Quedaban `{stock_unidades}` el `{stock_medido_en}`.» Si `stock_medido_en` es hoy: «Quedan `{stock_unidades}` hoy.» Con unidad: «Quedaban 380 ml…».
- Se dice "quedaban" porque `stock_unidades` es lo que quedaba al anotar, no lo de hoy (contrato, `stock_unidades`).

#### 3.2.2 La nota de cómo se calcula

- Bajo el título, siempre visible: «Es un cálculo con lo que anotaste. Si compraste o te quedan menos, anótalo.» [APROBADO 02-11]. `text-base text-tenue max-w-prose`.
- En pantalla ancha, en la columna derecha, `Nota` en `rocio` con el título «Cómo calculamos» y el texto «Dividimos lo que quedaba por lo que se usa, y contamos los días desde que lo anotaste. No sabe si compraste ni si cambió lo que usa `{pila}`.» [aprobado por Jorge el 03-11]. A 360 px no se muestra: la nota corta basta.

#### 3.2.3 El espacio para MATU-37

Entre el título y la nota queda **una región vacía** (`<section aria-labelledby>` que MATU-37 llena con «Qué se acaba pronto» y las alertas). En MATU-36 **no se pinta nada**: ni un borde, ni un texto "Próximamente", ni un alto fijo. Solo se deja el lugar en el código, para que MATU-37 no reordene la página.

#### 3.2.4 Pagador u observador

La misma lista, sin «Anotar un insumo» y sin «Cambiar». Nada en `turquesa` macizo.

---

### 3.3 Sin insumos (lista vacía)

**Objetivo:** Carmen sabe qué hacer para empezar, con un solo insumo.

Reutiliza el estado vacío de la demo (`SeAcaba`, `declarados.length === 0`):

```
┌────────────────────────────────────┐
│ Insumos                            │  h1
│ ┌────┐                             │  baldosa rocio, ListChecks
│ │ ✓≡ │                             │  size-16, ícono size-9 text-turquesa
│ └────┘                             │
│ Aún no sabemos qué usa María       │  h2 titular text-3xl
│ Cuéntanos de un solo producto, el  │  text-base tenue, max-w-prose
│ que más te preocupa. Con eso ya te │
│ podemos avisar antes de que se     │
│ acabe.                             │
│ [ + Anotar un insumo ]             │  único turquesa macizo
└────────────────────────────────────┘
```

Alineado a la izquierda (`items-start`), como en la demo. En pantalla ancha, el mismo bloque en la columna izquierda, sin la columna derecha.

| Rol | Título | Texto | Acción |
|---|---|---|---|
| admin, cuidador | Aún no sabemos qué usa `{pila}` (demo) | Cuéntanos de un solo producto, el que más te preocupa. Con eso ya te podemos avisar antes de que se acabe. (demo) | «Anotar un insumo» [aprobado por Jorge el 03-11]. Se quita el «Después» de la demo: no hay a dónde volver dentro de la sección |
| pagador, observador | Todavía no hay insumos anotados [aprobado por Jorge el 03-11] | Cuando alguien de tu grupo anote uno, aparece aquí. [aprobado por Jorge el 03-11] | Ninguna. Baldosa `bg-tinta/7 text-tenue` |

Los textos de la demo entran a `lenguaje.md` en el mismo pull request (no están hoy).

---

### 3.4 Anotar o cambiar un insumo

**Objetivo:** Carmen anota qué usa María, cuánto y cuánto queda, y ve de inmediato hasta cuándo alcanza.

**Jerarquía:**
1. El título y el primer campo.
2. La vista previa «Así, alcanza para {n} días», en `rocio`.
3. «Guardar», el único botón en `turquesa` macizo, y «Cancelar» como enlace.
4. (Eliminar no está en el formulario: es la papelera de la fila, 3.6.2.)

**Orden de los campos:**

| Al anotar (nuevo) | Al cambiar |
|---|---|
| 1. Nombre | 1. Cuánto queda hoy (lo más común: decisión 41) |
| 2. Unidad | 2. Cuánto se usa |
| 3. Cuánto se usa | 3. Cuándo avisar |
| 4. Cuánto queda | 4. Nombre |
| 5. Cuándo avisar | (la unidad se muestra como texto: no se edita) |

**Esquema a 360 px (anotar):**

```
┌────────────────────────────────────┐
│ ‹ Volver a los insumos             │  enlace, min-h-12
│ Anotar un insumo                   │  h1
│ ¿Qué insumo es?                    │  label font-bold
│ Por ejemplo: «Toallitas húmedas».  │  ayuda text-base tenue
│ Sin remedios ni para qué se usa.   │
│ ┌────────────────────────────────┐ │  input text, min-h-12
│ │ Pañal adulto M                 │ │  ring-2 ring-inset ring-borde
│ └────────────────────────────────┘ │
│                          14 de 60  │  contador, text-base tenue
│ ¿Cómo se cuenta?                   │  legend
│ (•) Por unidad  ( ) Por sobre      │  GrupoOpciones en fila, envuelve
│                                    │  (solo dos opciones, D5)
│ ¿Cada cuánto se usa?               │  legend
│ (•) Todos los días                 │
│ ( ) Cada algunos días              │
│ ¿Cuántos usa María al día?         │  Stepper con campo editable
│ [ − ] [  4  ] [ + ]  al día        │  botones size-12
│ ¿Cuántos quedan hoy, más o menos?  │  Stepper
│ [ − ] [ 24  ] [ + ]                │
│ ¿Con cuántos días de anticipación  │  Stepper, 7 por omisión
│ te avisamos?                       │
│ [ − ] [  7  ] [ + ]  días antes    │
│ ┃ Así, alcanza para 6 días,       │  rocio, border-l-4 turquesa
│ ┃ hasta el 09/11/2026.            │  aria-live="polite"
│ [ Guardar ]   Cancelar             │  Acciones
└────────────────────────────────────┘
```

Con «Cada algunos días», aparece debajo un `Stepper` «¿Cada cuántos días?» (2 a 90, empieza en 2) y la pregunta de uso cambia a «¿Cuántos usa `{pila}` cada `{d}` días?», con «cada `{d}` días» como sufijo. Así "uno cada dos días" se dice sin fracciones, y "al día" sigue siendo el caso de un toque.

**Esquema a 360 px (cambiar):** igual, con el título «`{nombre}`» y la bajada «Cambiar lo anotado» [aprobado por Jorge el 03-11], y el primer campo:

```
│ ¿Cuántos quedan hoy, más o menos?  │
│ El 31/10/2026 anotaste 24.         │  ayuda text-base tenue
│ ┌──────────┐                       │  campo VACÍO a propósito
│ │          │ unidades              │
│ └──────────┘                       │
│ ...                                │
│ ───────────────────────────────── │  border-t linea, mt-8
│                                    │  (sin «eliminar» aquí: está en la fila)
```

**Por qué el stock va vacío al cambiar:** `stock_unidades` es lo que quedaba **al anotar**, no hoy. Rellenarlo con 24 invita a guardar un número viejo como si fuera de hoy, y el `PATCH` re-ancla la fecha aunque el número sea el mismo (contrato). Vacío = no se envía. El frontend envía en el `PATCH` **solo los campos que cambiaron** (decisión 41), y si nada cambió, «Guardar» vuelve a la lista sin pedir nada, con el aviso «No había cambios.» [aprobado por Jorge el 03-11].

**Pantalla ancha:** el formulario va en la columna derecha (2.3), dentro de una hoja `bg-hoja px-7 py-5 ring-1 ring-linea` con el título como `h2` (`text-xl font-bold`) y foco en él, como el `Detalle` de la demo. Sin «Volver a los insumos» (la lista sigue a la vista). La página conserva el `h1` «Insumos».

#### 3.4.1 Componentes y tokens

- **Campo de texto (nombre):** `CampoTexto`, `min-h-12 w-full max-w-xl bg-hoja ring-2 ring-inset ring-borde`, foco `focus-visible:ring-turquesa` más el foco base. `maxLength={60}`, `autoComplete="off"`, `enterKeyHint="next"`. Una línea (`input`, no `textarea`): un salto de línea pegado se reemplaza por un espacio antes de enviar. El contador «`{n}` de 60» va en `aria-live="polite"` solo desde 50.
- **Stepper:** el de la demo, con dos cambios. 1) El número es un `input` editable (`inputMode="numeric"`, `pattern="[0-9]*"`, `w-24 text-center text-xl cifras`), no un `output`: con 100.000 como máximo, los botones solos no sirven. 2) Los botones `−` y `+` son `size-12` (no `size-11`), `ring-turquesa/70`. Sufijo de unidad en `text-base text-tenue`.
- **Rangos (contrato):** `tasa_unidades` 1 a 10.000, `tasa_dias` 1 a 90, `stock_unidades` 0 a 100.000, `dias_aviso` 0 a 60. El paso de los botones es 1.
- **Vista previa:** `flex flex-col gap-2 border-l-4 border-turquesa bg-rocio px-4 angosto:px-2 py-3`, con `CalendarCheck` (`size-5`, `aria-hidden`, oculto en `angosto`). Calcula con la fórmula del contrato, `piso(stock × tasa_dias / tasa_unidades)` días desde hoy. **Es solo una vista previa:** al guardar, la lista muestra lo que devuelve la API. Al cambiar sin escribir el stock, la vista previa no se muestra (no hay cómo calcularla sin inventar).
- **Acciones:** `Acciones` de la demo. «Guardar» principal y «Cancelar» como enlace (`text-turquesa underline`, `min-h-12`). A 360 px, uno junto al otro si caben, y si no, uno debajo del otro **al ancho de su texto**.
- **Sin acción de eliminar ni de dejar de seguir en el formulario.** Las dos viven en la fila de la lista (3.6).

#### 3.4.2 Textos del formulario

| Parte | Texto | Estado |
|---|---|---|
| Título al anotar | Anotar un insumo | [aprobado por Jorge el 03-11] |
| Título al cambiar | `{nombre}` y bajada «Cambiar lo anotado» | [aprobado por Jorge el 03-11] |
| Enlace de vuelta (360 px) | Volver a los insumos | [aprobado por Jorge el 03-11] |
| Nombre: etiqueta | ¿Qué insumo es? | [aprobado por Jorge el 03-11] |
| Nombre: ayuda | Por ejemplo: «Toallitas húmedas». Sin remedios ni para qué se usa | [APROBADO 02-11]. Va con punto final al mostrarse |
| Unidad: leyenda | ¿Cómo se cuenta? | [aprobado por Jorge el 03-11] |
| Unidad: opciones | Por unidad (`unidad`, por omisión) · Por sobre (`sobre`). Solo estas dos (D5) | [aprobado por Jorge el 03-11] |
| Unidad al cambiar | Se cuenta por unidad. / Se cuenta por sobre. (Un perfil antiguo en `ml` o `g`: Se cuenta en ml. / Se cuenta en gramos.) | [aprobado por Jorge el 03-11] |
| Frecuencia: leyenda | ¿Cada cuánto se usa? | [aprobado por Jorge el 03-11] |
| Frecuencia: opciones | Todos los días · Cada algunos días | [aprobado por Jorge el 03-11] |
| Cada cuántos días | ¿Cada cuántos días? · sufijo «días» | [aprobado por Jorge el 03-11] |
| Uso | ¿Cuántos usa `{pila}` al día? · sufijo «al día». Con «Cada algunos días»: ¿Cuántos usa `{pila}` cada `{d}` días? · sufijo «cada `{d}` días». Con `sobre`, el sufijo lleva la unidad («sobres al día») | [aprobado por Jorge el 03-11], a partir de la demo («¿Cuánto usa {pila}?») |
| Stock al anotar | ¿Cuántos quedan hoy, más o menos? | Demo («¿Cuántos le quedan, más o menos?»), ajustado [aprobado por Jorge el 03-11] |
| Stock al cambiar: ayuda | El `{stock_medido_en}` anotaste `{stock_unidades}`. Escribe cuántos quedan hoy, o déjalo en blanco si no lo sabes. | [aprobado por Jorge el 03-11] |
| Aviso | ¿Con cuántos días de anticipación te avisamos? · sufijo «días antes» · ayuda «Si pones 0, te avisamos el mismo día.» | [aprobado por Jorge el 03-11] |
| Vista previa | Así, alcanza para `{n}` días, hasta el `{fecha}`. Con 1: Así, alcanza para 1 día, hasta el `{fecha}`. Con 0: Así, se acaba hoy. | [aprobado por Jorge el 03-11], con las formas de 3.2.1 |
| Botón | Guardar · mientras envía: Guardando… | Lenguaje 5.4 («Guardando…») |
| Cancelar | Cancelar | Demo |
| Confirmación al volver a la lista | Guardamos «`{nombre}`». Alcanza para `{n}` días. (con las formas de 3.2.1) | [aprobado por Jorge el 03-11], mismo verbo que el botón (lenguaje 2.6) |

#### 3.4.3 Validación antes de enviar

Al tocar «Guardar» (nunca un botón deshabilitado). El mensaje va bajo el campo, en `text-pronto` con `CircleAlert` y `aria-invalid`, y el foco va al primer campo con error.

| Campo | Caso | Texto [aprobado por Jorge el 03-11] |
|---|---|---|
| Nombre | vacío o solo espacios | Escribe el nombre del insumo. |
| Uso | vacío o 0 | Escribe cuántos usa, al menos 1. |
| Uso | más de 10.000 | Escribe un número hasta 10.000. |
| Cada cuántos días | fuera de 2 a 90 | Escribe un número de 2 a 90. |
| Stock (al anotar) | vacío | Escribe cuántos quedan. Si no queda nada, escribe 0. |
| Stock | más de 100.000 | Escribe un número hasta 100.000. |
| Aviso | fuera de 0 a 60 | Escribe un número de 0 a 60. |

#### 3.4.4 Cargando

«Guardar» conserva su ancho, dice «Guardando…» y lleva `aria-busy="true"`. Los campos quedan editables pero no se envía dos veces. **Sin interfaz optimista** (CLAUDE.md, agente 3): la lista cambia solo con la respuesta de la API.

#### 3.4.5 Errores de la API

Lo escrito **nunca se borra** en un error.

| Respuesta | Dónde | Texto [aprobado por Jorge el 03-11] salvo que se diga |
|---|---|---|
| 422 `nombre_libre` `string_too_long` | Bajo el nombre | El nombre admite hasta 60 caracteres. Acórtalo un poco. |
| 422 `nombre_libre` `value_error` | Bajo el nombre | Escribe el nombre en una sola línea. |
| 422 `nombre_libre` `missing` o `producto_o_nombre` | Bajo el nombre | Escribe el nombre del insumo. |
| 422 `cobertura_maxima` | Sobre «Guardar» | Con esos números alcanzaría para más de 10 años. Revisa cuánto queda y cuánto se usa. |
| 422 de rango en un número | Bajo ese campo | El texto de 3.4.3 para ese campo |
| 422 `producto_no_admitido` | Sobre «Guardar» | Ese producto no se puede seguir en MATU. (No ocurre en el sprint 3: la app usa `nombre_libre`) |
| 422 de otro tipo | Sobre «Guardar» | No pudimos guardar. Revisa los datos y vuelve a intentarlo. |
| 409 `perfil-duplicado` | Sobre «Guardar» | Ese producto ya está anotado. Búscalo en la lista y cámbialo ahí. (No ocurre con `nombre_libre`) |
| 409 `perfil-inactivo` | Reemplaza el formulario, patrón de una columna, `PauseCircle` en baldosa `bg-tinta/7` | **Ya no se está siguiendo este insumo.** Alguien desmarcó «Seguir» mientras lo cambiabas. Para cambiarlo, vuelve a marcar «Seguir» en la lista. Botón secundario «Volver a los insumos» [aprobado por Jorge el 03-11] |
| 412 `version-desactualizada` | 3.5 | — |
| 428 `falta-version` | Sobre «Guardar» | Lenguaje 6.3, adaptado: **No pudimos guardar este insumo.** Vuelve a abrirlo y guarda de nuevo. Lo que escribiste sigue aquí. |
| 403 | Reemplaza la pantalla | 3.1.3 o 3.1.4 |
| 404 | Reemplaza la pantalla | Lenguaje 8. Si el insumo se eliminó mientras se cambiaba, el mismo 404: la lista se vuelve a pedir |
| Red o 5xx | Sobre «Guardar» | Lenguaje 8: No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo. Lo que escribiste sigue aquí. |

#### 3.4.6 Éxito

Vuelve a la lista (a 360 px) o cierra el formulario (en ancho), pide la lista de nuevo y muestra el aviso de confirmación de 3.4.2 arriba de la lista: `Nota` tono `ok` (`bg-ok-fondo`, `Check` en `text-ok`, texto en `tinta`), `role="status"`, animación `aparecer`. Se cierra sola al salir de la pantalla, no a los segundos (quien lee lento no lo pierde).

---

### 3.5 Conflicto: otra persona cambió el insumo (412)

**Objetivo:** Carmen ve qué guardó la otra persona y decide, sin que nada se pise en silencio.

Reemplaza las acciones del formulario por un bloque de conflicto (patrón de lenguaje 6.2), `border-l-4 border-atenta bg-atenta-fondo px-4 py-4`, `role="alert"`, foco en su título.

```
┌────────────────────────────────────┐
│ ┃ Otra persona cambió «Pañal      │  h2 text-xl font-bold
│ ┃ adulto M» mientras lo cambiabas │
│ ┃ No guardamos lo tuyo encima de  │
│ ┃ lo suyo. Elige qué dejar.       │
│ ┃ ┌ Lo que guardó ─────────────┐  │  dl, bg-hoja ring-1 ring-linea
│ ┃ │ Usa 4 al día               │  │
│ ┃ │ Quedaban 18 el 31/10/2026  │  │  lo distinto en negrita + «cambió»
│ ┃ │ Alcanza para 4 días        │  │
│ ┃ └────────────────────────────┘  │
│ ┃ ┌ Lo tuyo, sin guardar ──────┐  │
│ ┃ │ Quedan 20 hoy              │  │
│ ┃ └────────────────────────────┘  │
│ ┃ [ Guardar lo mío ]              │  principal
│ ┃ [ Dejar lo que guardó ]         │  secundario
└────────────────────────────────────┘
```

En pantalla ancha, «Lo que guardó» y «Lo tuyo» lado a lado desde `@2xl/main`.

- **«Lo que guardó»** sale de `actual` del 412. **«Lo tuyo»** muestra solo los campos que la persona cambió.
- Las diferencias se marcan con **negrita y la palabra «(cambió)»**, nunca solo con color.
- **«Guardar lo mío»** repite el `PATCH` con los campos propios y el `If-Match` de `actual.etag`. **«Dejar lo que guardó»** descarta lo propio, vuelve a la lista y muestra «Dejaste lo que guardó la otra persona.»
- Si `actual.activo` es `false`, se muestra 3.4.5 «Ya no se está siguiendo este insumo».

| Parte | Texto [aprobado por Jorge el 03-11], adaptado de lenguaje 6.2 sin `{autor}` (D2) |
|---|---|
| Título | Otra persona cambió «`{nombre}`» mientras lo cambiabas |
| Explicación | No guardamos lo tuyo encima de lo suyo. Elige qué dejar. |
| Bloques | Lo que guardó · Lo tuyo, sin guardar |
| Marca | (cambió) |
| Botones | Guardar lo mío · Dejar lo que guardó |
| Confirmaciones | Guardamos «`{nombre}`». Alcanza para `{n}` días. · Dejaste lo que guardó la otra persona. |

**Criterio:** en el conflicto, «Guardar lo mío» es el único `turquesa` macizo. Ningún dato de la otra persona se pierde de la pantalla hasta que se elige.

---

### 3.6 Seguir y eliminar (decisión de Jorge del 03-11)

Dos controles separados en cada fila, solo para `admin` y `cuidador`. **«Seguir» pausa y se deshace. La papelera borra para siempre.** Por eso uno es una casilla que se toca sin confirmar y el otro pide confirmación.

#### 3.6.1 La casilla «Seguir»

**Objetivo:** Carmen deja de calcular algo que ya no usan por un tiempo, sin perder lo anotado, y lo puede retomar con un toque.

```
┌────────────────────────────────────┐
│ Pañal adulto M                     │
│ Alcanza para 6 días                │
│ hasta el 06/11/2026                │
│ Usa 4 al día. Quedaban 24 el …     │
│ [x] Seguir      [ Cambiar ]  [pap] │  casilla min-h-12 · secundario · papelera size-12
└────────────────────────────────────┘
  Sin seguir                            h2 text-xl, mt-8
┌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┐  fondo papel, borde punteado
╎ Toallitas húmedas  (|| Sin seguir) ╎  píldora neutra con PauseCircle
╎ No calculamos ni avisamos mientras ╎  text-base tenue
╎ no lo sigues.                      ╎
╎ [ ] Seguir                   [pap] ╎  sin «Cambiar»
└╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┘
```

- **Casilla:** `input type="checkbox"` nativo, `size-5 accent-turquesa`, dentro de un `label` `inline-flex min-h-12 items-center gap-3 font-bold` con el texto «Seguir». Marcada por omisión al anotar. `aria-describedby` apunta al nombre del insumo, para que el lector diga «Seguir, Pañal adulto M».
- **Desmarcar** llama a `POST …/desactivar`. **Marcar** llama a la ruta nueva para volver a seguir (la fija el backend). **Sin interfaz optimista:** mientras responde, la casilla lleva `aria-busy="true"`, el texto pasa a «Guardando…» y no se puede tocar de nuevo. Si falla, vuelve a su estado y aparece bajo la fila el texto de red de lenguaje 8, sin «Lo que escribiste sigue aquí».
- **Cómo se distingue un insumo sin seguir, sin depender del color:** 1) la **palabra** «Sin seguir» en una píldora neutra (`bg-tinta/7 text-tenue`, ícono `PauseCircle`) junto al nombre · 2) la **línea de días se reemplaza** por «No calculamos ni avisamos mientras no lo sigues.» · 3) la **forma**: la hoja pasa a `bg-papel border-2 border-dashed border-borde` (sin `ring`) · 4) la **posición**: van al final, bajo el subtítulo `h2` «Sin seguir» (`text-xl font-bold mt-8`). La casilla desmarcada lo confirma.
- Los insumos sin seguir **no llevan «Cambiar»**: un `PATCH` sobre ellos responde 409 (contrato). Para cambiarlos, primero se vuelven a seguir.
- **Al volver a seguir**, la fila sube a su lugar por fecha y muestra sus días, con el aviso «Volviste a seguir «`{nombre}`». Si cambió cuánto queda, anótalo.» El foco sigue en la casilla.
- **Al dejar de seguir**, aviso en `role="status"`: «Dejaste de seguir «`{nombre}`». Lo anotado sigue guardado.» El foco sigue en la casilla, ahora en la sección «Sin seguir».
- **Pagador y observador** no ven la casilla: ven la píldora «Sin seguir» y la sección, nada más.
- La lista pide los dos grupos: `GET …/consumo` y `GET …/consumo?activo=false`. Si el orquestador prefiere una sola llamada, es un cambio del contrato.

| Parte | Texto [aprobado por Jorge el 03-11] |
|---|---|
| Casilla | Seguir · mientras guarda: Guardando… |
| Píldora y subtítulo | Sin seguir |
| Línea en lugar de los días | No calculamos ni avisamos mientras no lo sigues. |
| Al dejar de seguir | Dejaste de seguir «`{nombre}`». Lo anotado sigue guardado. |
| Al volver a seguir | Volviste a seguir «`{nombre}`». Si cambió cuánto queda, anótalo. |

#### 3.6.2 La papelera: eliminar

**Objetivo:** Carmen borra para siempre algo anotado por error, sabiendo que no vuelve.

- **Botón:** solo ícono `Trash2` (`size-5`, `aria-hidden`), `size-12`, `rounded-xl bg-hoja text-pronto ring-2 ring-inset ring-pronto/60`, `hover:bg-pronto-fondo`, foco base. `aria-label="Eliminar {nombre}"`. Va **al final de la fila, separado** de «Cambiar» (`ms-auto`, `gap-4`), para no tocarlo por error. Está en los insumos que se siguen y en los que no.
- **Diálogo:** `<dialog>` modal nativo, `aria-labelledby` y `aria-describedby`, foco inicial en **«Cancelar»** (lo seguro), `Esc` cancela, y al cerrar el foco vuelve a la papelera, o al `h1` si se eliminó. `bg-hoja rounded-2xl p-6 max-w-md w-[calc(100%-2rem)]`, `backdrop:bg-tinta/40`. Sin animación.

```
┌──────────────────────────────────┐
│ ¿Eliminar «Toallitas húmedas»?   │  h2 text-xl font-bold
│ Se borra todo lo anotado de este │  text-base
│ insumo y no se puede recuperar.  │
│ Si solo quieres dejar de         │  text-base tenue
│ calcularlo por un tiempo,        │
│ desmarca «Seguir».               │
│ [ Eliminar ]   Cancelar          │
└──────────────────────────────────┘
```

| Parte | Texto [aprobado por Jorge el 03-11] |
|---|---|
| Título | ¿Eliminar «`{nombre}`»? |
| Texto | Se borra todo lo anotado de este insumo y no se puede recuperar. |
| Alternativa | Si solo quieres dejar de calcularlo por un tiempo, desmarca «Seguir». (No va si el insumo ya está sin seguir) |
| Botones | Eliminar (mientras envía: Eliminando…) · Cancelar |
| Confirmación en la lista | Eliminaste «`{nombre}`». |
| Error de red o 5xx, dentro del diálogo | No pudimos completar esto. Revisa tu conexión y vuelve a intentarlo. |

- «Eliminar» es el único botón macizo del diálogo, en `bg-pronto text-papel` (cerca de 10:1 en claro y sobre 9:1 en oscuro, por cálculo; lo mido en la revisión). No es `turquesa` porque no es una acción de avance. Mismo verbo en el botón y en la confirmación.
- **Sin interfaz optimista:** la fila desaparece solo con la respuesta de la API. Un 404 (ya lo eliminó otra persona) se trata como éxito: se cierra el diálogo y se vuelve a pedir la lista, sin mensaje de error.
- Las palabras "desactivar", "reactivar" y "borrado" no aparecen en la interfaz.

### 3.7 Error al cargar la lista

Patrón "una sola columna" de MATU-23 (3.12), con `CircleAlert` en baldosa `bg-tinta/7`:

| Caso | Texto | Acción |
|---|---|---|
| 404 | Lenguaje 8: No encontramos lo que buscas. Puede que ya no tengas acceso. Vuelve al inicio. | Enlace «Volver al inicio» (ruta de MATU-39) |
| Red o 5xx | **No pudimos completar esto.** Revisa tu conexión y vuelve a intentarlo. (MATU-23, sección 7) | Botón principal «Volver a intentar» |

---

## 4. Lo que NO debe mostrarse

| Nunca | Por qué |
|---|---|
| El nombre del insumo o de la persona en la URL, el `<title>`, `localStorage` o `sessionStorage` | CLAUDE.md, agente 3, punto 5. El nombre libre es dato protegido por RLS (decisión 38) |
| Precios, comercio, «Pedir», «Ya lo compré» o la lista de reposición | Capa 3 y MATU-51. MATU-36 funciona sin ellos |
| Niveles de color («Pronto», «Atenta»), la barra de 30 días o «Qué se acaba pronto» | Son de MATU-37 |
| "Stock", "quiebre", "perfil", "consumo", "desactivar", "reactivar", "consentimiento", "fecha estimada" | Lenguaje 3.2 |
| Nombres de remedios en un ejemplo o un marcador de posición | ADR-022: MATU no trata remedios |
| La fórmula con signos («24 ÷ 4») como en la demo | La demo enseñaba el cálculo al profesor. Carmen necesita la fecha. Se dice en palabras en «Cómo calculamos» |
| Un número de días que la API no devolvió, después de guardar | Sin interfaz optimista |
| `title`, `detail`, `mensaje` o `request_id` de la API | Lenguaje 8 |
| Botones de escritura para pagador u observador, ni siquiera deshabilitados | 2.4 |

---

## 5. Componentes y estados

Los de MATU-23 (sección 5) más estos. Se construyen en `web/src/compartido/ui/` y no se importan desde `Demo/`.

| Componente | Normal | Foco | Presionado | Cargando | Error | Vacío |
|---|---|---|---|---|---|---|
| Botón principal | MATU-23 | foco base | `active:brightness-95` | gerundio, `aria-busy` | — | — |
| Botón de peligro (solo en el diálogo de eliminar, 3.6.2) | `bg-pronto text-papel`, misma forma que el principal | foco base | `active:brightness-95` | gerundio | — | — |
| Botón secundario («Cambiar», «Ver más») | MATU-23 | foco base | `bg-rocio` | gerundio | — | — |
| Enlace de acción («Cancelar», «Volver a los insumos») | `text-turquesa underline`, `min-h-12` | foco base | `decoration-turquesa` | — | — | — |
| Fila de insumo | hoja `ring-1 ring-linea`. Sin seguir: `bg-papel border-2 border-dashed border-borde` y píldora «Sin seguir» | — (la fila no es interactiva: sí su casilla, «Cambiar» y la papelera) | — | — | — | 3.3 |
| Fila elegida (ancho) | `ring-2 ring-inset ring-turquesa`, `aria-current` | — | — | — | — | — |
| CampoTexto | `ring-2 ring-inset ring-borde` | `ring-turquesa` + foco base | — | sin cambio | `ring-pronto`, mensaje `text-pronto` con `CircleAlert`, `aria-invalid` | marcador vacío, sin texto gris de ejemplo |
| Stepper | campo `ring-borde`, botones `ring-turquesa/70` | foco base en cada uno | `bg-rocio` | sin cambio | como CampoTexto | — |
| GrupoOpciones | opción `ring-borde` | foco base | — | — | `ring-pronto` en el grupo y mensaje | — |
| Vista previa | `rocio` + `border-l-4 border-turquesa` | — | — | — | se oculta si falta un dato | se oculta |
| Casilla «Seguir» | `size-5 accent-turquesa` en un `label` `min-h-12` | foco base | — | «Guardando…», `aria-busy` | vuelve a su estado y mensaje de red | — |
| Papelera | `size-12 text-pronto ring-2 ring-inset ring-pronto/60` | foco base | `bg-pronto-fondo` | — | — | — |
| Bloque de conflicto | `atenta-fondo` + `border-l-4 border-atenta` | foco en su título | — | — | — | — |
| Aviso de confirmación | `Nota` tono `ok` con `Check` | — | — | — | — | — |

**Íconos (`lucide-react`, todos `aria-hidden`):** `Plus`, `Minus`, `ListChecks`, `CalendarCheck`, `CircleAlert`, `Check`, `PauseCircle`, `Trash2`, `Lock`, `Hourglass`, `ChevronLeft` (en «Volver a los insumos») y los de MATU-23.

**Tokens:** ningún token nuevo. Todo sale de la capa de MATU-23, 6.2. Ningún valor escrito a mano (`style={{…}}`, `#hex`, `px` en clases arbitrarias), salvo `w-[calc(100%-2rem)]` del diálogo, que es geometría y no estilo.

---

## 6. Accesibilidad visual

- Texto base 17 px en `rem` (raíz de la capa base). Ningún texto relevante bajo `text-base`. El contador y las ayudas también van en `text-base`.
- Todo lo que se toca mide 48 × 48 px o más: `min-h-12` y `size-12`. **`size-11` no alcanza** (MATU-23, 5).
- Foco base de 3 px en `turquesa` en todo control, también en los botones del Stepper, las opciones del grupo y el diálogo.
- Estado nunca solo por color: días ≤ 0 llevan palabra e ícono; la opción elegida lleva el punto; el conflicto marca «(cambió)»; los errores llevan `CircleAlert` y texto.
- Sin desplazamiento horizontal a 320 px con texto al 200%: nombres con `break-words`, el Stepper con `flex-wrap`, las fechas con `whitespace-nowrap` solo en la cifra.
- Cada campo con su `label` visible, la ayuda en `aria-describedby` y el error también.
- La vista previa en `aria-live="polite"`, y solo anuncia cuando el número cambia, no en cada tecla (con un retraso de 500 ms).
- Con `prefers-reduced-motion`, `aparecer` es inmediato.
- Tema oscuro: los mismos tokens con sus valores oscuros. Sin colores propios.

**Elementos en `turquesa` macizo por pantalla:**

| Pantalla | Cantidad |
|---|---|
| Permiso (3.1) | 1: «Acepto y continúo» |
| Falta el permiso o por renovar (3.1.3, 3.1.4) | 0 |
| Lista, admin o cuidador | 1: «Anotar un insumo» |
| Lista, pagador u observador | 0 |
| Vacío, admin o cuidador | 1: «Anotar un insumo» |
| Formulario | 1: «Guardar» (en ancho, «Anotar un insumo» de la lista pasa a secundario mientras el formulario está abierto) |
| Conflicto | 1: «Guardar lo mío» |
| Diálogo de eliminar | 0 (el principal es `pronto`) |
| Error de red | 1: «Volver a intentar» |

---

## 7. Textos para `lenguaje.md`

### 7.1 Lista

Ninguno se usa hasta que Jorge los apruebe. Van a una sección nueva de `lenguaje.md`, «Insumos (MATU-36)», junto con los cuatro aprobados el 02-11 (3.2.1, 3.2.2 y la ayuda del nombre), que todavía no están escritos ahí.

Son todos los marcados **[aprobado por Jorge el 03-11]** en las secciones 2.2, 3.0, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6 y 3.7. Además, entran los textos de la demo que esta especificación reutiliza y que hoy no están en `lenguaje.md`: el estado vacío de 3.3 y los del paso del permiso del alta (leyenda, opciones, referencia, botón y errores de 3.1.2).

### 7.2 Declaraciones del permiso para el consumo · Aprobadas por Jorge el 03-11

Van tal cual en la nota «Lo que declaras» (3.1), según la calidad elegida, y entran a `lenguaje.md`:

- `titular`: «Declaro que la persona que cuido me dijo hoy, en persona, que autoriza a MATU a guardar qué insumos usa, cuánto usa y cuánto queda, y a calcular cuándo se acaban y avisarme cuando se esté por acabar, según la política de privacidad vigente. Yo solo registro su decisión.»
- `representante_legal`: «Declaro que soy representante legal de la persona que cuido y que la referencia que indico corresponde al documento que lo acredita. Como su representante, autorizo a MATU a guardar qué insumos usa, cuánto usa y cuánto queda, y a calcular cuándo se acaban y avisarme cuando se esté por acabar, según la política de privacidad vigente.»
- `cuidador_de_hecho`: «Declaro que cuido a esta persona y que no soy su representante legal. Autorizo a MATU a guardar qué insumos usa, cuánto usa y cuánto queda, y a calcular cuándo se acaban y avisarme cuando se esté por acabar, según la política de privacidad vigente. Leí el aviso sobre el límite de esta autorización.»

## 8. Cómo la voy a revisar

No apruebo una pantalla que no vi funcionando. El frontend deja la pantalla levantable en local contra un doble del contrato con: lista con 3 insumos (6, 1 y 0 días), uno con −2 días, uno de 60 caracteres sin espacios, uno «por sobre», uno «cada 2 días», dos sin seguir; lista vacía; 403 `sin-consentimiento` con rol `cuidador` y con rol `observador`; 403 `revision-vencida`; un `PATCH` que responde 412 con `actual`; uno que responde 409 `perfil-inactivo`; un 422 `cobertura_maxima`; un 500; y `siguiente_cursor` en la primera página.

Capturas de cada estado a 360 × 740, 1280 × 720 y 1920 × 1080, en claro y oscuro; a 320 px con zoom al 200%; con texto del sistema al 200% en un Android real; y con `prefers-reduced-motion`. En cada una mido `scrollWidth <= innerWidth`, alto de lo que se toca, contraste de texto y bordes, foco visible con Tab (también dentro del diálogo y al cerrarlo), la tabla de `turquesa` macizo de la sección 6 y que ningún texto quede bajo 17 px.

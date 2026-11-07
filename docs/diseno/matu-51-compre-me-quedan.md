# MATU-51 · «Compré» y «Me quedan» en cada insumo · Especificación de diseño

**Versión 1.0 · 07/11/2026** · Agente 6, UI/UX. Especifica y no construye.

**Historia:** Carmen anota en dos toques que compró un insumo, o cuántos le quedan después de contarlos. MATU recalcula en el acto cuánto alcanza y hasta cuándo, y si había un aviso que ya no corresponde, desaparece.

**Dónde se construye:** `web/`, dentro de la fila de cada insumo de la pantalla «Insumos» (`web/src/familia/Insumos.tsx`, componente `Fila`). No es una pantalla nueva ni una ruta nueva.

**Fuentes, en este orden:** `Demo/DISENO.md` (secciones 2, 4 y 6) y los tokens de `web/src/index.css` (sin agregar ninguno) · las decisiones de Jorge del 07-11 · `docs/lenguaje.md` del repositorio MATU (secciones 2, 3, 13, 17, 18, 21 y 22) · las especificaciones de MATU-36 (filas, `Stepper`, errores), MATU-37 (el panel de «Ya lo resolví», que esta especificación copia en forma), MATU-60 (el texto de la cantidad con envase, 4.5) y MATU-44 (el 403 de la autorización retirada o vencida) · el código de `web/src/familia/Insumos.tsx`, `insumosComun.tsx`, `textosInsumos.ts`, `textoLista.ts` y `web/src/compartido/ui/Boton.tsx`.

**Marcas de los textos:** **[L n]** ya está en `lenguaje.md`, sección n · **[NUEVO]** entra a `lenguaje.md` en el pull request de MATU-51 (tabla de la sección 11) · **[CAMBIA]** reemplaza un texto aprobado y necesita el visto de Jorge · **[ANALISTA]** propuesto por el analista normativo, se adopta tal cual. `{nombre}` es el nombre del insumo (`nombreDe(p)`), `{pila}` el nombre de pila de la persona cuidada, `{n}` los días, `{fecha}` en `DD/MM/AAAA`, `{u}` las unidades por envase.

---

## 0. Lo que tiene que decidir alguien más

| # | Qué | Por qué importa | Mientras tanto |
|---|---|---|---|
| A1 | **El contrato de MATU-51 todavía no está en el worktree.** La pantalla necesita saber: las dos rutas, si «Compré» recibe envases o unidades, los topes de cada cantidad, si alguna de las dos exige `If-Match` (y puede responder 412), si responde 409 `perfil-inactivo` y que la respuesta sea el `PerfilConsumoVista` recalculado (`dias_restantes`, `fecha_quiebre_estimada`, `stock_unidades`, `stock_medido_en`) | Sin la respuesta recalculada, la confirmación no puede decir hasta cuándo alcanza, y la pantalla no debe calcularlo | Esta especificación supone: respuesta = perfil recalculado, «Compré» de 1 a 9.999 (el tope de «Ya lo resolví»), «Me quedan» de 0 a 100.000 (el tope del stock de MATU-36), sin `If-Match`. Los textos de 412 y 409 (5.5) quedan listos por si el contrato los trae. **Lo cierra el orquestador con el backend** |
| A2 | **Dos maneras de anotar una compra, con unidades distintas.** «Ya lo resolví» de MATU-37 pregunta «¿Compraste? ¿Cuántos?» en la unidad del insumo (el campo `cantidad` de `SolicitudResolver` dice «no en envases»). «Compré» pregunta en envases cuando se conoce `unidades_por_envase` (decisión de Jorge del 07-11). Carmen puede ver las dos en la misma pantalla para el mismo insumo | Si en el bloque de avisos escribe «2» pensando en paquetes, MATU suma 2 pañales | **Recomiendo** que el campo de «Ya lo resolví» siga la misma regla que «Compré» (envases si se conoce el envase, vacío por omisión porque ahí es opcional), con la pregunta «¿Compraste? ¿Cuántos envases?» [NUEVO]. Cambia un texto aprobado de MATU-37, así que **lo decide Jorge**. Mientras no decida, el bloque «Se acaban pronto» no cambia en esta historia |
| A3 | **Los insumos «Sin seguir».** Jorge dijo «en cada insumo de la lista». Un insumo sin seguir no se calcula ni avisa (MATU-36 3.6) | Anotar una compra en algo que no se calcula no cambia nada en pantalla, y Carmen creería que no funcionó | **Propongo** que «Compré» y «Me quedan» se muestren solo en los insumos que se siguen. Para anotar en uno sin seguir, primero se marca «Seguir», que ya dice «Si cambió cuánto queda, anótalo» [L 18]. **Lo confirma Jorge** |
| A4 | **«Me quedan N» como rótulo.** El botón de la fila no puede llevar un número antes de que Carmen cuente | — | El botón dice «Me quedan» y la `N` se escribe en el panel. Es también lo que usa el texto del analista para «Cómo calculamos» («con «Compré» o «Me quedan»») |
| A5 | **Observación sobre MATU-37, fuera de alcance.** Su criterio 2 pide que, con el panel de «Ya lo resolví» abierto, «Anotar un insumo» deje de ser macizo. El código lo pasa a secundario solo cuando hay formulario (`variante={form ? 'secundario' : 'principal'}`) | Con un panel abierto quedan dos `turquesa` macizos | Esta historia lo resuelve para los tres paneles a la vez (3.6), porque la regla es la misma. Si el orquestador prefiere no tocar MATU-37, se aplica solo a los paneles nuevos |

---

## 1. Para quién y qué

**Carmen** vuelve del almacén con dos paquetes de pañales en una mano y el teléfono en la otra. Abre Insumos, busca el pañal y toca «Compré». El panel ya dice «1 envase de 20 unidades». Toca «+» una vez y «Anotar la compra». Son tres toques, sin escribir y sin teclado. Otro día cuenta lo que hay en el mueble, toca «Me quedan», escribe 12 y confirma.

**Lo que tiene que pasar en pantalla:** la fila dice al tiro cuánto alcanza ahora y hasta cuándo, en la misma fila donde tocó. Si el pañal estaba en «Se acaban pronto» y ya no corresponde, sale del bloque y la marca «Te estamos avisando» sale de la fila.

**Rodrigo** (pagador u observador) ve la fila igual que hoy, sin «Compré» ni «Me quedan». Lo que anota Carmen le llega como el cálculo nuevo.

**Lo que esta pantalla nunca hace:** ofrecer comprar, pedir, mostrar precios, catálogo, marca o lugar de compra. No pregunta la fecha (la fija el servidor: hoy). No muestra un historial de compras. «Compré» es una frase sobre lo ya hecho, nunca una invitación.

---

## 2. Objetivo y jerarquía

**Objetivo:** Carmen anota lo que compró o lo que le queda sin salir de la fila, y ve en el acto cuánto alcanza ahora.

**Jerarquía de la fila (sin cambios en lo de arriba):**

1. El nombre, la marca «Te estamos avisando» si corresponde y «Alcanza para {n} días» con su fecha (MATU-36 y MATU-37, igual que hoy).
2. «Usa … Quedaban …» (igual que hoy).
3. **Nuevo:** las dos acciones de registro, «Compré» y «Me quedan», en su propio renglón. Son lo que más se toca después de anotar el insumo, así que van antes de las de administración.
4. Las de administración, igual que hoy: «Seguir», «Cambiar» y la papelera, separadas por un divisor.

**Una sola acción principal por pantalla:** con los paneles cerrados, «Anotar un insumo» sigue siendo el único `turquesa` macizo. «Compré» y «Me quedan» son **secundarios**. Con un panel abierto, su botón de confirmar es el único macizo y «Anotar un insumo» pasa a secundario (3.6).

---

## 3. La fila

### 3.1 Esquema a 360 px (admin o cuidador, insumo que se sigue)

```
┌────────────────────────────────────┐
│ ┌────────────────────────────────┐ │  li bg-hoja ring-1 ring-linea rounded-xl (MATU-36)
│ │ Pañal adulto M                 │ │  font-bold break-words
│ │ (campana) Te estamos avisando  │ │  MATU-37, solo si avisando
│ │ Alcanza para 3 días            │ │  text-xl font-bold (MATU-36)
│ │ hasta el 10/11/2026            │ │  text-base
│ │ Usa 4 al día. Quedaban 24 el   │ │  text-base text-tenue (MATU-36)
│ │ 04/11/2026.                    │ │
│ │                                │ │
│ │ [ Compré ]  [ Me quedan ]      │ │  NUEVO. flex flex-wrap gap-3, dos secundarios
│ │ ────────────────────────────── │ │  NUEVO. border-t border-linea en el renglón de abajo
│ │ [x] Seguir  [ Cambiar ]   (pap)│ │  igual que hoy
│ └────────────────────────────────┘ │
└────────────────────────────────────┘
```

**Medidas a 360 px:** el contenido del `li` mide unos 296 px. «Compré» (unos 105 px) y «Me quedan» (unos 135 px) más el espacio caben en un renglón. **Sin íconos en los dos botones:** con un ícono cada uno pasan de 296 px y bajan de renglón, y lucide no tiene uno que diga «compré» sin parecer un carro de compras, que ofrecería comprar.

### 3.2 Pantalla ancha (1280 y 1920 px)

La fila vive en la columna izquierda (`3fr`), que mide unos 500 px a 1280 y unos 900 a 1920. La columna derecha («Cómo calculamos» o el formulario) no cambia, salvo su texto (sección 7).

```
┌───────────────────────────────────────────────┬───────────────────────────┐
│ Insumos                          [ + Anotar un insumo ]                    │
│ (Se acaban pronto, MATU-37)                    │ ┌ Cómo calculamos ──────┐ │
│ ┌────────────────────────────────────────────┐ │ │ Dividimos lo que      │ │
│ │ Pañal adulto M            Alcanza para 3 días│ │ │ quedaba por lo que se │ │
│ │ (campana) Te estamos avisando hasta el 10/11 │ │ │ usa… Si compraste o   │ │
│ │ Usa 4 al día. Quedaban 24 el 04/11/2026.   │ │ │ cambió lo que queda,  │ │
│ │ [ Compré ]  [ Me quedan ]                  │ │ │ anótalo con «Compré»  │ │
│ │ ────────────────────────────────────────── │ │ │ o «Me quedan»…        │ │
│ │ [x] Seguir  [ Cambiar ]               (pap)│ │ └───────────────────────┘ │
│ └────────────────────────────────────────────┘ │                           │
└───────────────────────────────────────────────┴───────────────────────────┘
```

**Siempre en dos renglones, también a 1920 px**, donde las cinco piezas cabrían en uno. Así el registro y la administración no se mezclan: «Cambiar» y «Me quedan» no quedan lado a lado con el mismo aspecto, y la fila se lee igual en el teléfono y en el proyector.

### 3.3 Componentes y tokens (todos existentes, **ningún token nuevo**)

| Parte | Componente y clases |
|---|---|
| Renglón de registro | `div` `flex flex-wrap items-center gap-3`. Solo si `editor && p.activo` (A3) |
| «Compré» | `Boton variante="secundario"` (`bg-hoja text-turquesa ring-2 ring-inset ring-turquesa/70`, `min-h-12`), `id="compre-{id}"`, `aria-label="Compré: {nombre}"`, `aria-expanded`, `aria-controls="panel-compre-{id}"` |
| «Me quedan» | `Boton variante="secundario"`, `id="quedan-{id}"`, `aria-label="Me quedan: {nombre}"`, `aria-expanded`, `aria-controls="panel-quedan-{id}"` |
| Renglón de administración | El de hoy, con `border-t border-linea pt-3` cuando hay renglón de registro encima. `linea` es divisor, nunca borde de control (DISENO 1) |
| Panel | `div` `role="group"` con `aria-labelledby` a la etiqueta del campo, `tabIndex={-1}`, `outline-none`, `flex scroll-mb-28 flex-col gap-3 border-t border-linea pt-3`. Es el panel de MATU-37 3.5 |
| Campo | `Stepper` de `insumosComun.tsx`, con `label` visible, ayuda en `aria-describedby` y sufijo |
| Confirmar | `Boton` principal (`bg-turquesa text-papel`), con `ocupado` y `textoOcupado` |
| Volver | `Boton variante="secundario"` |
| Confirmación en la fila | El aspecto de `AvisoOk`: `animate-aparecer flex gap-3 rounded-xl bg-ok-fondo px-4 angosto:px-2 py-3 outline-none`, `Check` `size-5 text-ok` `aria-hidden`, `role="status"`, `tabIndex={-1}`, con un `id` propio por fila (`hecho-{id}`), porque `aviso-insumos` es único en la página |
| Error del campo | El del `Stepper`: anillo `ring-pronto`, `aria-invalid` y `MensajeError` debajo |
| Error del panel | `MensajeError` dentro de un `div` `role="alert"` `tabIndex={-1}`, como `falla-{id}` de MATU-37 |

### 3.4 Panel «Compré»

Se abre **dentro del mismo `li`**, en el lugar del renglón de registro (los dos botones se van mientras está abierto). Sin modal, sin deslizar. El renglón de administración sigue debajo, sin cambios.

**Con `unidades_por_envase` (`{u}`):**

```
│ │ Usa 4 al día. Quedaban 24 el   │ │
│ │ 04/11/2026.                    │ │
│ │ ────────────────────────────── │ │  border-t border-linea
│ │ ¿Cuántos envases compraste?    │ │  label font-bold
│ │ Lo sumamos a lo que calculamos │ │  ayuda text-base text-tenue
│ │ que queda hoy.                 │ │
│ │ [ − ] [  1  ] [ + ]            │ │  Stepper, 1 por omisión
│ │ envase de 20 unidades          │ │  sufijo; baja de renglón si no cabe
│ │                                │ │
│ │ [ Anotar la compra ] [ Volver ]│ │  principal y secundario
│ │ ────────────────────────────── │ │
│ │ [x] Seguir  [ Cambiar ]   (pap)│ │
```

- Valor inicial **1**. Mínimo 1, máximo el del contrato (A1).
- El sufijo es `sufijoCantidad(n, unidad, u)` de `textoLista.ts`, el mismo de la lista de MATU-60 4.5: «envase de 20 unidades», «envases de 20 unidades», «envases de 250 ml», «envases de 10 sobres», «envases de 1 unidad». Cambia con el número, así que con 2 dice «envases».
- El sufijo de hoy en el `Stepper` es un `span` fijo al lado del campo. Con «envases de 20 unidades» no cabe junto a los botones a 360 px: va en el mismo `flex flex-wrap` y baja solo. No hace falta otra pieza.

**Sin `unidades_por_envase`:**

```
│ │ ¿Cuántos compraste?            │ │  o «¿Cuántos sobres compraste?», etc.
│ │ Lo sumamos a lo que calculamos │ │
│ │ que queda hoy.                 │ │
│ │ [ − ] [     ] [ + ]  unidades  │ │  Stepper vacío, foco en el campo
│ │ [ Anotar la compra ] [ Volver ]│ │
```

- **Vacío** al abrir: un «1» por omisión tiene sentido para un paquete, no para pañales sueltos o mililitros. Mínimo 1, máximo el del contrato.
- Sufijo `INSUMOS.sufijoStock(unidad)`: «unidades», «sobres», «ml», «g» [L 18].

**Lo que va a la API:** lo que diga el contrato (A1). Si el contrato pide unidades, la pantalla manda `envases × {u}`. Nunca manda una fecha.

### 3.5 Panel «Me quedan»

Mismo lugar y misma forma que «Compré».

```
│ │ ────────────────────────────── │ │
│ │ ¿Cuántos quedan hoy, más o     │ │  label font-bold [L 18]
│ │ menos?                         │ │
│ │ Reemplaza lo que calculábamos. │ │  ayuda text-base text-tenue
│ │ Si no queda nada, escribe 0.   │ │
│ │ [ − ] [     ] [ + ]  unidades  │ │  Stepper vacío, foco en el campo
│ │ [ Anotar lo que queda ] [Volver]│ │
```

- **Vacío** al abrir, por la misma razón que MATU-36 deja vacío el stock al cambiar: un número precargado invita a confirmar sin contar.
- Mínimo **0**, máximo el del contrato (A1). Siempre en la unidad del insumo, aunque tenga envase (decisión de Jorge). Sufijo `INSUMOS.sufijoStock(unidad)`.
- «−» con el campo vacío deja 0, como ya hace el `Stepper` con `min={0}`.

### 3.6 Reglas de los paneles

- **Uno abierto a la vez en toda la pantalla**, contando el de «Ya lo resolví» de MATU-37. Abrir otro cierra el anterior sin guardar.
- Mientras hay un panel abierto, «Anotar un insumo» va en `variante="secundario"` (A5). Al cerrarse, vuelve a principal.
- «Volver» y `Escape` cierran el panel y devuelven el foco al botón que lo abrió («Compré» o «Me quedan» de esa fila).
- Abrir un panel borra la confirmación anterior de cualquier fila y el `AvisoOk` de arriba. En la pantalla hay un solo mensaje a la vez.

### 3.7 Pagador, observador y «Sin seguir»

- **Pagador y observador:** el renglón de registro no existe en el DOM (no deshabilitado: ausente). La fila es la de hoy.
- **Insumo «Sin seguir»:** sin renglón de registro (A3). La fila es la de hoy, con «Seguir» desmarcado.

---

## 4. Foco y lectores de pantalla

| Momento | Dónde queda el foco | Qué se anuncia |
|---|---|---|
| Abre «Compré» con envase (valor 1) | **En el panel** (`role="group"`, `tabIndex={-1}`), no en el campo. Así el teclado del teléfono no se abre y tapa «Anotar la compra», y el camino corto son los toques «+» y confirmar | «¿Cuántos envases compraste?, grupo». El `Tab` sigue a «−», el campo, «+», «Anotar la compra» y «Volver» |
| Abre «Compré» sin envase, o «Me quedan» | En el campo, porque hay que escribir | La etiqueta y la ayuda (`aria-describedby`) |
| Al abrir, en los dos casos | El panel se desplaza con `scrollIntoView({ block: 'nearest' })`. `scroll-mb-28` deja la barra fija de secciones fuera del camino (DISENO 3, WCAG 2.4.11) | — |
| Enviando | El foco se queda en el botón de confirmar (`aria-busy`). Ver 5.2 | «Guardando…» |
| Éxito | En la confirmación de la fila (`hecho-{id}`), que se desplaza a la vista. La fila pudo moverse en la lista porque se ordena por fecha: el foco la sigue | El texto de la confirmación (`role="status"`) |
| Error del campo (validación o 422) | En el campo, con `aria-invalid` | El mensaje, por `aria-describedby` |
| Error del panel (red, 404, 409, 412) | En el mensaje (`role="alert"`, `tabIndex={-1}`), sin desplazar con `preventScroll`. Después se desplaza el panel entero a la vista | El mensaje |
| 403 | Al `h1` de la pantalla de permiso de MATU-36 o MATU-44 | El título de esa pantalla |

**Nombres de los botones:** «Compré: {nombre}» y «Me quedan: {nombre}», como «Ya lo resolví: {nombre}» [L 17]. El botón de confirmar no repite el nombre: está dentro del grupo, que ya lo tiene en su contexto. Los botones «−» y «+» del `Stepper` usan su texto de hoy («Uno menos: {etiqueta}», «Uno más: {etiqueta}»).

---

## 5. Estados

### 5.1 Normal

El de la sección 3. Sin cambios en la fila salvo el renglón de registro y el divisor.

### 5.2 Enviando

- **Sin interfaz optimista** (CLAUDE.md, frontend 4, y MATU-37 4.4). La fila no cambia hasta la respuesta.
- El botón de confirmar dice «Guardando…» [L 17], `aria-busy="true"`, con su mismo ancho. «Volver» y el campo quedan deshabilitados (`disabled` en «Volver», `readOnly` en el campo, los «−» y «+» ignoran el toque). `Escape` no cierra mientras guarda.
- Con la red lenta, nada se mueve: ni la fila, ni el bloque «Se acaban pronto».

### 5.3 Éxito

1. La respuesta trae el perfil recalculado. La fila se reemplaza con él, la lista se vuelve a ordenar por fecha y se vuelve a pedir `por-acabarse` (el `refrescarBloque` de hoy).
2. El panel se cierra. En su lugar, bajo «Usa … Quedan … hoy.», va la confirmación, con el foco.
3. «Usa 4 al día. Quedan 44 hoy.» ya sale bien solo: el servidor anota la fecha de hoy y la fila de MATU-36 dice «Quedan … hoy» cuando `stock_medido_en` es hoy.
4. Si el insumo estaba en «Se acaban pronto» y ya no corresponde, sale del bloque y la marca «Te estamos avisando» sale de la fila. Si el bloque queda sin avisos, desaparece entero, como en MATU-37 4.1. La confirmación no lo menciona: el cambio se ve en la fila.
5. Si el insumo **entra** al bloque (por ejemplo, «Me quedan 0»), aparece en el bloque y la fila gana la marca. Tampoco lo menciona la confirmación.
6. La confirmación se queda hasta la próxima acción en la pantalla (3.6).

Textos de la confirmación (sección 8): «Compra anotada…» para «Compré» y «Anotamos lo que queda…» para «Me quedan». El mismo verbo que el botón: «Anotar la compra» y «Compra anotada» es el ejemplo literal de DISENO, principio 6.

### 5.4 Error 422

| Caso | Dónde | Qué pasa |
|---|---|---|
| Campo vacío al confirmar (validación de la pantalla) | Bajo el campo | `aria-invalid`, foco al campo. No se llama a la API |
| Fuera de rango (pantalla o API, `errores[].campo` de la cantidad) | Bajo el campo | Igual |
| `cobertura_maxima` | Bajo el campo | Igual. El panel sigue abierto con lo escrito |
| Otro 422 | Error del panel | «No pudimos guardar. Revisa los datos y vuelve a intentarlo.» [L 18] |

Nunca se muestra `title`, `detail` ni `mensaje` de la API.

### 5.5 Otros errores

| Respuesta | Texto | Qué pasa |
|---|---|---|
| Red o 5xx | «No pudimos guardar. Revisa tu conexión y vuelve a intentarlo.» [L 17] | Error del panel. El panel sigue abierto con lo escrito y el botón vuelve a «Anotar la compra» o «Anotar lo que queda». No se reintenta solo |
| 404 | «Este insumo ya no está. Puede que alguien de tu familia lo haya eliminado.» [NUEVO] | Se cierra el panel, se recarga la lista en silencio (`cargar(true)`) y el mensaje va arriba, en el lugar del `AvisoOk`, como `MensajeError` con `role="alert"` y el foco. La fila ya no existe, así que el mensaje no puede ir en ella |
| 403 `sin-consentimiento` o `revision-vencida` | Los de MATU-36 y MATU-44 [L 18, L 22] | Se cierra el panel y la pantalla pasa al estado de permiso (`setCarga(permiso)`), como hoy con «Seguir» |
| 409 `perfil-inactivo`, si el contrato lo trae (A1) | «Alguien dejó de seguir «{nombre}» mientras lo anotabas. Para anotar, vuelve a marcar «Seguir».» [NUEVO] | Error del panel con «Ver cómo quedó» [L 17], que cierra el panel y recarga la lista |
| 412, si el contrato pide `If-Match` (A1) | «{autor} cambió «{nombre}» mientras lo anotabas. Revisa cómo quedó y vuelve a intentarlo.» [NUEVO, con la forma de L 17] · «Ver cómo quedó» [L 17] | Igual que el 409. No se suma ni se reemplaza nada |
| 401 | El de MATU-36 (renovar una vez y, si falla, a la entrada) | — |

### 5.6 Sin permiso

- **Por rol:** no hay botones (3.7). No hay texto: no se explica una acción que no se ofrece.
- **Por autorización retirada o vencida:** la pantalla entera es la de permiso de MATU-36 3.1.3 y 3.1.4, con lo de MATU-44. No aparece ninguna fila.

---

## 6. Accesibilidad visual, temas y reflujo

- **Áreas táctiles:** «Compré», «Me quedan», «Anotar la compra», «Anotar lo que queda», «Volver», «Ver cómo quedó» y los «−» y «+» del `Stepper` miden `min-h-12` (51 px) y al menos 48 px de ancho. Entre un botón y el siguiente, `gap-3` (12,75 px), para no tocar el vecino con el pulgar.
- **Foco visible:** el contorno base de 3 px en `turquesa` con 2 px de separación, sobre `hoja` (6,7:1 claro y 8,2:1 oscuro). El panel que recibe el foco por programa no es un control y no lleva contorno.
- **Contraste, con los valores de DISENO.md:** texto `turquesa` sobre `hoja` 6,7:1 y 8,2:1 · anillo `turquesa` al 70 % del secundario sobre `hoja` 3,5:1 · `papel` sobre `turquesa` (confirmar) 6,0:1 y 9,4:1 · `tenue` sobre `hoja` (ayuda y sufijo) 7,2:1 y 8,1:1 · `tinta` sobre `ok-fondo` y `ok` sobre `ok-fondo` (confirmación) 5,9:1 o más · `borde` del campo sobre `hoja` 3,5:1 y 4:1 · `pronto` del error sobre `hoja`, sobre 4,5:1. Se miden en la revisión en los dos temas.
- **Estado nunca solo con color:** la confirmación lleva palabra y el `Check`. El error lleva palabra, el ícono de `MensajeError` y el anillo del campo.
- **320 px con texto al 200% (160 px efectivos, modo `angosto:`):** los dos botones bajan uno por renglón, el `li` usa `angosto:px-2`, el `Stepper` y su sufijo bajan de renglón, «Anotar la compra» y «Volver» quedan uno bajo otro. La fecha de la confirmación va en `cifras` con el punto final dentro, y el resto de la frase refluye. Un nombre de 60 caracteres sin espacios se parte con `[overflow-wrap:anywhere]`, como hoy. Sin desplazamiento horizontal.
- **`prefers-reduced-motion`:** el panel abre y cierra sin animación, y la confirmación aparece sin el fundido de `aparecer`. La fila que se reordena cambia de lugar sin moverse.
- **Proyector:** nada relevante bajo `text-base`. El tema claro es el de la presentación.

---

## 7. «Cómo calculamos» y la nota corta

En pantalla ancha, la nota «Cómo calculamos» queda a la derecha. A 360 px no se ve, y lo que se lee es la nota corta bajo «Se acaban pronto».

| Dónde | Rol | Texto | Marca |
|---|---|---|---|
| Cómo calculamos | admin y cuidador | Dividimos lo que quedaba por lo que se usa, y contamos los días desde que lo anotaste. Si compraste o cambió lo que queda, anótalo con «Compré» o «Me quedan». No sabe si cambió lo que usa {pila}. | [ANALISTA] [CAMBIA] la fila de la sección 18 |
| Cómo calculamos | pagador y observador | Dividimos lo que quedaba por lo que se usa, y contamos los días desde que la familia lo anotó. Si compraron y no lo anotaron, no lo sabe. Tampoco sabe si cambió lo que usa {pila}. | [NUEVO] [CAMBIA] la sección 16. Hoy dice «No sabe si compraron», y desde MATU-51 la familia lo puede anotar |
| Nota corta, a 360 px | admin y cuidador | Es un cálculo con lo que anotaste. Si compraste o te quedan menos, anótalo con «Compré» o «Me quedan». | [CAMBIA] la fila de la sección 13.1. Dice dónde se anota, que hoy a 360 px no está en ninguna parte |
| Nota corta, a 360 px | pagador y observador | Es un cálculo con lo que anotó la familia. | [L 16], sin cambios |

La frase del analista se adopta tal cual. Dice «cambió lo que queda», que cubre los dos casos: que queden menos o que queden más de lo calculado.

---

## 8. Textos exactos

| Dónde | Texto | Marca |
|---|---|---|
| Botón de la fila | Compré | [NUEVO] (decisión de Jorge) |
| Botón de la fila | Me quedan | [NUEVO] (decisión de Jorge, A4) |
| Nombre accesible | Compré: {nombre} · Me quedan: {nombre} | [NUEVO] |
| Compré, etiqueta con envase | ¿Cuántos envases compraste? | [NUEVO] |
| Compré, etiqueta sin envase | ¿Cuántos compraste? · ¿Cuántos sobres compraste? · ¿Cuántos ml compraste? · ¿Cuántos gramos compraste? | [NUEVO] |
| Compré, ayuda | Lo sumamos a lo que calculamos que queda hoy. | [NUEVO] |
| Compré, sufijo con envase | envase de {u} unidades · envases de {u} unidades (con sobres, ml o g, «de {u} sobres», «de {u} ml», «de {u} g». Con {u} igual a 1, «de 1 unidad», «de 1 sobre») | [L 21] |
| Compré y Me quedan, sufijo sin envase | unidades · sobres · ml · g | [L 18] |
| Compré, confirmar | Anotar la compra | [NUEVO] (DISENO, principio 6) |
| Me quedan, etiqueta | ¿Cuántos quedan hoy, más o menos? | [L 18] |
| Me quedan, ayuda | Reemplaza lo que calculábamos. Si no queda nada, escribe 0. | [NUEVO] |
| Me quedan, confirmar | Anotar lo que queda | [NUEVO] |
| Los dos, enviando | Guardando… | [L 17] |
| Los dos, cerrar | Volver | [L 17] |
| Compré, hecho (2 o más días) | Compra anotada para «{nombre}»: {cantidad}. Ahora alcanza para {n} días, hasta el {fecha}. | [NUEVO] |
| Compré, hecho (1 día) | Compra anotada para «{nombre}»: {cantidad}. Ahora alcanza para 1 día, hasta el {fecha}. | [NUEVO] |
| Compré, hecho (0 días) | Compra anotada para «{nombre}»: {cantidad}. Así, se acaba hoy. | [NUEVO] |
| Compré, hecho (negativo, si el contrato lo permite) | Compra anotada para «{nombre}»: {cantidad}. Según lo anotado, puede que ya no quede. | [NUEVO] |
| Me quedan, hecho (2 o más días) | Anotamos lo que queda de «{nombre}»: {cantidad}. Alcanza para {n} días, hasta el {fecha}. | [NUEVO] |
| Me quedan, hecho (1 día) | Anotamos lo que queda de «{nombre}»: {cantidad}. Alcanza para 1 día, hasta el {fecha}. | [NUEVO] |
| Me quedan, hecho (más de 0 pero se acaba hoy) | Anotamos lo que queda de «{nombre}»: {cantidad}. Así, se acaba hoy. | [NUEVO] |
| Me quedan, hecho con 0 | Anotamos que no queda «{nombre}». Cuando compres, anótalo con «Compré». | [NUEVO] |
| Compré, campo vacío, con envase | Escribe cuántos envases compraste, al menos 1. | [NUEVO] |
| Compré, campo vacío, sin envase | Escribe cuántos compraste, al menos 1. | [NUEVO] |
| Compré, sobre el tope | Escribe un número hasta {tope}. (con punto de miles: «9.999») | [NUEVO], con la forma de «Escribe un número hasta 10.000.» [L 18] |
| Me quedan, campo vacío | Escribe cuántos quedan. Si no queda nada, escribe 0. | [L 18] |
| Me quedan, sobre el tope | Escribe un número hasta 100.000. | [L 18] |
| Compré, `cobertura_maxima` | Con esa compra alcanzaría para más de 10 años. Revisa cuántos compraste. | [NUEVO] |
| Me quedan, `cobertura_maxima` | Con esa cantidad alcanzaría para más de 10 años. Revisa cuántos quedan. | [NUEVO] |
| Otro 422 | No pudimos guardar. Revisa los datos y vuelve a intentarlo. | [L 18] |
| Red o 5xx | No pudimos guardar. Revisa tu conexión y vuelve a intentarlo. | [L 17] |
| 404 | Este insumo ya no está. Puede que alguien de tu familia lo haya eliminado. | [NUEVO] |
| 409 `perfil-inactivo` (A1) | Alguien dejó de seguir «{nombre}» mientras lo anotabas. Para anotar, vuelve a marcar «Seguir». | [NUEVO] |
| 412 (A1) | {autor} cambió «{nombre}» mientras lo anotabas. Revisa cómo quedó y vuelve a intentarlo. («Otra persona» si no hay autor, [L 18]) | [NUEVO] |
| Después de 409 o 412 | Ver cómo quedó | [L 17] |

**`{cantidad}`** es `cantidadEnTexto(n, unidad, envase)` de `textoLista.ts`: «2 envases de 20 unidades», «24 unidades», «1 sobre», «500 ml», «1.200 unidades». En «Me quedan», `envase` va siempre en `null`, porque se cuenta en la unidad del insumo. La cifra con punto de miles desde 1.000. **`{n}` y `{fecha}`** salen de la respuesta (`dias_restantes` y `fecha_quiebre_estimada`), nunca de un cálculo de la pantalla.

**Por qué el nombre va en la confirmación:** el lector de pantalla lee solo el texto del `role="status"`, sin la fila alrededor. Con el nombre, «Compra anotada» dice de qué.

**Prohibido en todos:** «quiebre», «stock», «reponer», «reposición», «lista de reposición», precios, «pedir» y «comprar» como acción ofrecida. «Compré», «compraste» y «compres» solo hablan de lo que la familia ya hizo o hará por su cuenta. Ningún término de `lenguaje.md` 3. Ningún texto asume el género de la persona cuidada.

---

## 9. Lo que el frontend no debe hacer

- Calcular los días, la fecha o lo que queda en la pantalla. Todo sale de la respuesta.
- Mostrar el resultado antes de la respuesta (interfaz optimista).
- Precargar «Me quedan» con un número, ni «Compré» sin envase.
- Pedir o mostrar una fecha.
- Poner íconos en «Compré» o «Me quedan», o un carro, una bolsa o un precio en cualquier parte.
- Abrir un modal, un cajón o una ruta nueva para anotar.
- Guardar la cantidad en `localStorage`, `sessionStorage` o la URL.
- Dejar los botones en el DOM, deshabilitados, para el pagador o el observador.
- Escribir colores, tamaños o sombras a mano: todo es de las clases de la sección 3.3.

---

## 10. Criterios visuales verificables

1. Con los paneles cerrados, «Anotar un insumo» es el único `turquesa` macizo de la pantalla. Con un panel abierto, el único es su botón de confirmar.
2. En cada insumo que se sigue, como admin o cuidador, «Compré» y «Me quedan» están en un renglón propio, encima del renglón de «Seguir», «Cambiar» y la papelera, con un divisor `linea` entre los dos. A 360 px los dos botones caben en un renglón.
3. Como pagador u observador, no existe ningún «Compré» ni «Me quedan» en el DOM. En un insumo «Sin seguir», tampoco (si Jorge confirma A3).
4. «Compré» en un insumo con 20 unidades por envase abre con «1» y «envase de 20 unidades», y el teclado del teléfono no se abre. «+» lo deja en «2» y «envases de 20 unidades». Se confirma con tres toques desde la fila.
5. «Compré» sin envase y «Me quedan» abren con el campo vacío y el foco en él.
6. Con la red lenta, la fila y el bloque «Se acaban pronto» no cambian hasta la respuesta, y el botón dice «Guardando…».
7. Después de anotar, la confirmación aparece dentro de la fila del insumo y recibe el foco, aunque la fila haya cambiado de lugar. Dice cuánto alcanza ahora y hasta cuándo.
8. Si el insumo estaba en «Se acaban pronto» y deja de corresponder, sale del bloque y su fila pierde «Te estamos avisando» sin recargar la página.
9. Un 422 `cobertura_maxima` deja el panel abierto, con el número escrito, el anillo `pronto` en el campo y el mensaje debajo.
10. A 320 px con texto al 200%, sin desplazamiento horizontal, con un nombre de 60 caracteres sin espacios y el sufijo «envases de 10.000 unidades».
11. Todo lo que se toca mide al menos 48 × 48 px, y el foco se ve en claro y en oscuro.
12. Ningún texto de la fila, del panel ni de la confirmación ofrece comprar, pedir, precios o catálogo, ni dice «quiebre», «stock» o «reposición».

**Para la revisión:** el frontend deja levantable, contra el doble del contrato, una lista con un insumo con envase de 20 que esté en «Se acaban pronto» y salga al comprar 2, uno sin envase en sobres, uno en ml, uno «Sin seguir», uno de 60 caracteres sin espacios, y respuestas de 422 `cobertura_maxima`, 404, 403 `revision-vencida`, 500 y una respuesta lenta. Las capturas son a 360, 1280 y 1920 px, en claro y oscuro, y con texto al 200%.

---

## 11. Textos para `lenguaje.md`, sección 23 nueva

Lista para pegar. Los que cambian textos aprobados van en la segunda tabla, con la fila que reemplazan.

### 23. Anotar una compra o lo que queda (MATU-51)

En la app se dice «Compré» y «Me quedan», nunca «reposición», «reponer» ni «stock». «Compré» habla de lo que la familia ya hizo: la app nunca ofrece comprar. La fecha la pone MATU (hoy) y la familia no la elige. Los días y la fecha de la confirmación los da la API.

| Dónde | Texto |
|---|---|
| Botones de cada insumo (solo admin y cuidador) | Compré · Me quedan |
| Nombre accesible de los botones | Compré: {nombre} · Me quedan: {nombre} |
| Compré, pregunta | Con envase conocido: ¿Cuántos envases compraste? · Sin envase: ¿Cuántos compraste? / ¿Cuántos sobres compraste? / ¿Cuántos ml compraste? / ¿Cuántos gramos compraste? |
| Compré, ayuda | Lo sumamos a lo que calculamos que queda hoy. |
| Compré, cantidad junto al campo | La de la sección 21 («envase de {u} unidades», «envases de {u} unidades»), y sin envase la de la sección 18 («unidades», «sobres», «ml», «g») |
| Compré, botón | Anotar la compra |
| Me quedan, pregunta | ¿Cuántos quedan hoy, más o menos? (de la sección 18) |
| Me quedan, ayuda | Reemplaza lo que calculábamos. Si no queda nada, escribe 0. |
| Me quedan, botón | Anotar lo que queda |
| En curso y cerrar | Guardando… · Volver (de la sección 17) |
| Compra anotada | Compra anotada para «{nombre}»: {cantidad}. Ahora alcanza para {n} días, hasta el {fecha}. (Con 1: «1 día». Con 0: «Compra anotada para «{nombre}»: {cantidad}. Así, se acaba hoy.» Negativo: «… Según lo anotado, puede que ya no quede.») |
| Lo que queda, anotado | Anotamos lo que queda de «{nombre}»: {cantidad}. Alcanza para {n} días, hasta el {fecha}. (Con 1: «1 día». Si se acaba hoy: «Anotamos lo que queda de «{nombre}»: {cantidad}. Así, se acaba hoy.») |
| Lo que queda, con 0 | Anotamos que no queda «{nombre}». Cuando compres, anótalo con «Compré». |
| Compré, falta la cantidad | Escribe cuántos envases compraste, al menos 1. · Escribe cuántos compraste, al menos 1. |
| Compré, sobre el tope | Escribe un número hasta {tope}. |
| Me quedan, falta o sobre el tope | Escribe cuántos quedan. Si no queda nada, escribe 0. · Escribe un número hasta 100.000. (de la sección 18) |
| Más de 10 años | Compré: Con esa compra alcanzaría para más de 10 años. Revisa cuántos compraste. · Me quedan: Con esa cantidad alcanzaría para más de 10 años. Revisa cuántos quedan. |
| El insumo ya no está (404) | Este insumo ya no está. Puede que alguien de tu familia lo haya eliminado. |
| Dejaron de seguirlo (409) | Alguien dejó de seguir «{nombre}» mientras lo anotabas. Para anotar, vuelve a marcar «Seguir». · Ver cómo quedó |
| Otra persona lo cambió (412) | {autor} cambió «{nombre}» mientras lo anotabas. Revisa cómo quedó y vuelve a intentarlo. · Ver cómo quedó |
| Errores generales | No pudimos guardar. Revisa tu conexión y vuelve a intentarlo. (sección 17) · No pudimos guardar. Revisa los datos y vuelve a intentarlo. (sección 18) |

**Si Jorge aprueba A2,** se agrega en la sección 17: «Panel, con envase conocido: ¿Compraste? ¿Cuántos envases?».

### Textos aprobados que cambian (con el visto de Jorge)

| Sección y fila | Hoy | Desde MATU-51 |
|---|---|---|
| 13.1, Nota bajo la fecha | Es un cálculo con lo que anotaste. Si compraste o te quedan menos, anótalo | Es un cálculo con lo que anotaste. Si compraste o te quedan menos, anótalo con «Compré» o «Me quedan». |
| 16, Cómo calculamos, observador y pagador | Dividimos lo que quedaba por lo que se usa, y contamos los días desde que la familia lo anotó. No sabe si compraron ni si cambió lo que usa {pila}. | Dividimos lo que quedaba por lo que se usa, y contamos los días desde que la familia lo anotó. Si compraron y no lo anotaron, no lo sabe. Tampoco sabe si cambió lo que usa {pila}. |
| 18, Lista, «Cómo calculamos» | … No sabe si compraste ni si cambió lo que usa {nombre}. | … Si compraste o cambió lo que queda, anótalo con «Compré» o «Me quedan». No sabe si cambió lo que usa {nombre}. (texto del analista) |

---

## 12. Decisiones que Jorge debe ver

1. **A2, la unidad de «Ya lo resolví».** Recomiendo que pregunte en envases igual que «Compré», para que la misma persona no anote 2 pañales creyendo que anotó 2 paquetes.
2. **A3, sin botones en los insumos «Sin seguir».**
3. **La confirmación va dentro de la fila y no arriba de la lista.** Después de anotar, la lista se reordena por fecha y la fila puede moverse. Con la confirmación en la fila, el foco y la vista la siguen. Arriba, en un teléfono, Carmen perdería la fila.
4. **Con envase, «Compré» abre con 1 y sin el teclado,** para confirmar en tres toques. Sin envase y en «Me quedan», el campo abre vacío, para no confirmar un número que no se contó.
5. **Los tres textos aprobados que cambian** (sección 11, segunda tabla). El de 360 px es el que más importa: hoy la nota corta dice «anótalo» sin decir dónde.

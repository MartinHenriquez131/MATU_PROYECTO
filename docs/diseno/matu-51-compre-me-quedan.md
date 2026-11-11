# MATU-51 · «Compré» y «Me quedan» en cada insumo · Especificación de diseño

**Versión 1.3 · 07/11/2026** · Agente 6, UI/UX. Especifica y no construye.

**Cambios de la 1.3 (revisión visual):** tres puntos que el frontend dejó abiertos quedan decididos, sin cambiar textos ni tokens. En el 412, «Ver cómo quedó» lleva el foco a la fila (`insumo-{id}`) (5.5). La confirmación, el error del panel y el 404 siguen con `role` directo porque reciben el foco, y `Anunciado` queda para los avisos que aparecen sin moverlo (4). La confirmación lleva `scroll-mb-28`, igual que el panel (3.3). Se corrige el contraste medido del borde del campo (6).

**Cambios de la 1.2:** las decisiones de Jorge del 07-11 sobre A2 a A5 cierran la sección 0. «Ya lo resolví» pregunta en envases (3.8, y los textos de la sección 17 que cambian, en 11), los insumos «Sin seguir» no tienen botones y su 409 tiene texto (5.5), y A5 se corrige en esta historia. El contrato de MATU-51 (`docs/api/README.md`, decisiones 136 a 146) ya está en la rama: confirma rutas, cuerpos, `If-Match` y respuesta, y se agrega el 428 (5.5).

**Cambios de la 1.1:** los topes cerrados por el orquestador (A1, 3.4, 3.5, 5.4) y sus textos de error (secciones 8 y 11).

**Historia:** Carmen anota en dos toques que compró un insumo, o cuántos le quedan después de contarlos. MATU recalcula en el acto cuánto alcanza y hasta cuándo, y si había un aviso que ya no corresponde, desaparece.

**Dónde se construye:** `web/`, dentro de la fila de cada insumo de la pantalla «Insumos» (`web/src/familia/Insumos.tsx`, componente `Fila`). No es una pantalla nueva ni una ruta nueva.

**Fuentes, en este orden:** `Demo/DISENO.md` (secciones 2, 4 y 6) y los tokens de `web/src/index.css` (sin agregar ninguno) · las decisiones de Jorge del 07-11 · `docs/lenguaje.md` del repositorio MATU (secciones 2, 3, 13, 17, 18, 21 y 22) · las especificaciones de MATU-36 (filas, `Stepper`, errores), MATU-37 (el panel de «Ya lo resolví», que esta especificación copia en forma), MATU-60 (el texto de la cantidad con envase, 4.5) y MATU-44 (el 403 de la autorización retirada o vencida) · el código de `web/src/familia/Insumos.tsx`, `insumosComun.tsx`, `textosInsumos.ts`, `textoLista.ts` y `web/src/compartido/ui/Boton.tsx`.

**Marcas de los textos:** **[L n]** ya está en `lenguaje.md`, sección n · **[NUEVO]** entra a `lenguaje.md` en el pull request de MATU-51 (tabla de la sección 11) · **[CAMBIA]** reemplaza un texto aprobado y necesita el visto de Jorge · **[ANALISTA]** propuesto por el analista normativo, se adopta tal cual. `{nombre}` es el nombre del insumo (`nombreDe(p)`), `{pila}` el nombre de pila de la persona cuidada, `{n}` los días, `{fecha}` en `DD/MM/AAAA`, `{u}` las unidades por envase.

---

## 0. Decisiones y lo que queda abierto

### 0.1 Cerrado el 07-11

| # | Qué | Decisión |
|---|---|---|
| A1, topes | Cuánto acepta cada campo | **Orquestador y contrato (decisión 137).** «Compré» en envases de 1 a 99, en la unidad del insumo de 1 a 10.000. «Me quedan» de 0 a 100.000. 422 `stock_maximo` si lo anotado deja más de 100.000 y `cobertura_maxima` si alcanzaría para más de 10 años (5.4) |
| A1, contrato | Rutas, cuerpo, versión y respuesta | **Contrato, decisiones 136 a 141.** `POST …/consumo/{perfil_id}/reponer` con `envases` o `cantidad` (exactamente uno), `POST …/consumo/{perfil_id}/recontar` con `stock_unidades`. Las dos con `If-Match` obligatorio (412 y 428 posibles), 409 `perfil-inactivo`, y la respuesta 200 es `InsumoPorAcabarseVista` (el perfil recalculado con `avisando`). El orquestador pidió dejar estos puntos como supuesto hasta que el backend los confirme implementados. La especificación ya los sigue |
| A2 | «Ya lo resolví» de MATU-37 preguntaba en unidades y «Compré» en envases | **Jorge.** «Ya lo resolví» pregunta igual que «Compré»: en envases, con 1 por omisión, cuando se sabe cuánto trae cada uno, y si no, en la unidad del insumo. Topes de 1 a 99 envases o de 1 a 10.000. Cambia textos aprobados de la sección 17. Se especifica en 3.8, y los reemplazos están en la sección 11 |
| A3 | Los insumos «Sin seguir» | **Jorge.** No muestran «Compré» ni «Me quedan» (3.7). Si llega un 409 porque el insumo dejó de seguirse en otro teléfono, el texto está en 5.5 |
| A4 | «Me quedan N» como rótulo | **Jorge, aceptado como se propuso.** El botón dice «Me quedan» y el número se escribe en el panel |
| A5 | Con el panel de «Ya lo resolví» abierto, «Anotar un insumo» seguía macizo, contra el criterio 2 de MATU-37 | **Jorge, se corrige en MATU-51.** La regla de 3.6 vale para los tres paneles |

### 0.2 Abierto, lo cierra el orquestador con el backend

| # | Qué | Por qué importa | Mientras tanto |
|---|---|---|---|
| A6 | **«Ya lo resolví» no tiene campo `envases`.** La decisión 144 sube su `cantidad` a 10.000, pero sigue en la unidad del insumo. «Compré» sí recibe `envases` (decisión 137), y su multiplicación puede pasar de 10.000 | Con la decisión A2 de Jorge, la pantalla tendría que mandar `envases × {u}` como `cantidad`. Con 99 envases de 200 ml serían 19.800 y el resolver respondería 422 en `cantidad`, aunque «Compré» acepta lo mismo | **Pido** que `SolicitudResolver` acepte `envases` (1 a 99) igual que `SolicitudReposicion`, con las mismas reglas. Si el backend prefiere no cambiarlo, la pantalla manda `envases × {u}` y un 422 de rango en `cantidad` muestra «Con esa compra quedarían más de 100.000…» o el error de rango con envase de 3.8. Los textos no cambian con esta decisión |

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
| Confirmación en la fila | El aspecto de `AvisoOk`: `animate-aparecer flex scroll-mb-28 gap-3 rounded-xl bg-ok-fondo px-4 angosto:px-2 py-3 outline-none` (`scroll-mb-28`, como el panel, para que la barra fija no la tape al recibir el foco), `Check` `size-5 text-ok` `aria-hidden`, `role="status"`, `tabIndex={-1}`, con un `id` propio por fila (`hecho-{id}`), porque `aviso-insumos` es único en la página |
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

- Valor inicial **1**. Mínimo 1, máximo **99 envases**. El `Stepper` no pasa de 99 con «+».
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

- **Vacío** al abrir: un «1» por omisión tiene sentido para un paquete, no para pañales sueltos o mililitros. Mínimo 1, máximo **10.000** en la unidad del insumo.
- Sufijo `INSUMOS.sufijoStock(unidad)`: «unidades», «sobres», «ml», «g» [L 18].

**Lo que va a la API (decisión 137):** con envase, `{"envases": n}`. Sin envase, `{"cantidad": n}`. Nunca los dos y nunca una fecha. Siempre con `If-Match` y el `etag` de la fila.

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
- Mínimo **0**, máximo **100.000**. Siempre en la unidad del insumo, aunque tenga envase (decisión de Jorge). Sufijo `INSUMOS.sufijoStock(unidad)`.
  - **Reemplazado para unidades y sobres por MATU-84 (decisión de Jorge del 10-11): ver `matu-84-me-quedan-envases.md`.** Con envase conocido, «Me quedan» pregunta en envases enteros más unos sueltos, y sin envase ofrece «Contar en envases». Con ml y g sigue igual.
- «−» con el campo vacío deja 0, como ya hace el `Stepper` con `min={0}`.
- **Lo que va a la API (decisión 139):** `{"stock_unidades": n}`, con `If-Match` y el `etag` de la fila. Nunca una fecha.

### 3.6 Reglas de los paneles

- **Uno abierto a la vez en toda la pantalla**, contando el de «Ya lo resolví» de MATU-37. Abrir otro cierra el anterior sin guardar.
- Mientras hay un panel abierto, sea «Compré», «Me quedan» o «Ya lo resolví», «Anotar un insumo» va en `variante="secundario"` (A5, decidido por Jorge: se corrige en MATU-51 también para el panel de MATU-37). Al cerrarse, vuelve a principal.
- «Volver» y `Escape` cierran el panel y devuelven el foco al botón que lo abrió («Compré» o «Me quedan» de esa fila).
- Abrir un panel borra la confirmación anterior de cualquier fila y el `AvisoOk` de arriba. En la pantalla hay un solo mensaje a la vez.

### 3.7 Pagador, observador y «Sin seguir»

- **Pagador y observador:** el renglón de registro no existe en el DOM (no deshabilitado: ausente). La fila es la de hoy.
- **Insumo «Sin seguir»:** sin renglón de registro (A3, decidido por Jorge). La fila es la de hoy, con «Seguir» desmarcado.

### 3.8 «Ya lo resolví» en el bloque «Se acaban pronto» (A2, decidido por Jorge)

**Cambia solo el campo del panel.** Lo demás de MATU-37 no cambia: el bloque, el botón «Ya lo resolví», el panel dentro del aviso, «Volver», `Escape`, la confirmación arriba del bloque, y los errores 409, 404, 412 y de red.

**Con `unidades_por_envase` (`{u}`):**

```
│ │ ┌────────────────────────────┐ │
│ │ │ Pañal adulto M             │ │
│ │ │ Alcanza para 3 días        │ │
│ │ │ Fecha estimada: 10/11/2026 │ │
│ │ │ ────────────────────────── │ │  border-t border-linea (MATU-37)
│ │ │ ¿Compraste? ¿Cuántos       │ │  label font-bold
│ │ │ envases?                   │ │
│ │ │ Si no compraste, déjalo en │ │  ayuda text-base text-tenue
│ │ │ 0 y solo dejamos de        │ │
│ │ │ avisarte.                  │ │
│ │ │ [ − ] [  1  ] [ + ]        │ │  Stepper, 1 por omisión, de 0 a 99
│ │ │ envase de 20 unidades      │ │  sufijoCantidad(n, unidad, u)
│ │ │ [ Ya lo resolví ]          │ │  principal
│ │ │ [ Volver ]                 │ │  secundario
│ │ └────────────────────────────┘ │
```

- **1 por omisión,** como «Compré» (decisión de Jorge).
- **El `Stepper` va de 0 a 99, no de 1 a 99.** Con 1 por omisión, quien no compró tendría que borrar el número con el teclado para solo descartar. Con mínimo 0, le basta un toque en «−». MATU-37 ya trata el 0 como vacío: 0 o vacío solo descarta, y de 1 a 99 anota la compra. El tope de 99 no cambia. Ver la sección 12, punto 1.
- La ayuda cambia de «déjalo en blanco» a «déjalo en 0», porque el campo ya no abre en blanco.
- El sufijo es el de «Compré»: «envase de 20 unidades», «envases de 20 unidades», «envases de 250 ml».
- **Foco al abrir:** en el panel (`role="group"` con `aria-labelledby` a la etiqueta, `tabIndex={-1}`), no en el campo, como «Compré» con envase (sección 4). El teclado no se abre. Hoy MATU-37 lleva el foco al campo: con envase, eso cambia.

**Sin `unidades_por_envase`:** como hoy en MATU-37. Pregunta en la unidad del insumo, abre vacío con el foco en el campo, y la ayuda dice «déjalo en blanco». Solo el tope pasa de 9.999 a **10.000** (decisión 144).

**Errores del campo:**

| Caso | Texto | Marca |
|---|---|---|
| Con envase, más de 99 | Escribe un número de 0 a 99. Si no compraste, déjalo en 0. | [CAMBIA] la fila «Cantidad inválida» de la sección 17 |
| Sin envase, fuera de 1 a 10.000 | Escribe un número de 1 a 10.000, o déjalo en blanco. | [CAMBIA] la misma fila (antes «entre 1 y 9999») |
| Lo que queda pasaría de 100.000 (422 `stock_maximo`, decisión 144) | Con esa compra quedarían más de 100.000 {unidades / sobres / ml / g}. Revisa cuántos compraste. | El texto de «Compré» (sección 8) |
| Más de 10 años (422 `cobertura_maxima`) | Con esa compra alcanzaría para más de 10 años. Revisa cuántos compraste. | El texto de «Compré» (sección 8) |

**Confirmación:** los textos de MATU-37 no cambian. Solo `{cantidad}` pasa a armarse con `cantidadEnTexto(n, unidad, envase)`, como en «Compré»: «Anotamos tu compra de Pañal adulto M: 2 envases de 20 unidades. Ahora alcanza para 23 días.» Sin envase, en unidades, dice «24 unidades» donde hoy dice «24».

**Lo que va a la API:** lo que diga el contrato (A6).

---

## 4. Foco y lectores de pantalla

| Momento | Dónde queda el foco | Qué se anuncia |
|---|---|---|
| Abre «Compré» con envase (valor 1) | **En el panel** (`role="group"`, `tabIndex={-1}`), no en el campo. Así el teclado del teléfono no se abre y tapa «Anotar la compra», y el camino corto son los toques «+» y confirmar | «¿Cuántos envases compraste?, grupo». El `Tab` sigue a «−», el campo, «+», «Anotar la compra» y «Volver» |
| Abre «Compré» sin envase, o «Me quedan» | En el campo, porque hay que escribir. **Reemplazado para «Me quedan» con envase conocido por MATU-84 (decisión de Jorge del 10-11, D4): ver `matu-84-me-quedan-envases.md`.** Ahí el foco va al panel, como «Compré» con envase. Sin envase, y con ml y g, sigue igual | La etiqueta y la ayuda (`aria-describedby`) |
| Al abrir, en los dos casos | El panel se desplaza con `scrollIntoView({ block: 'nearest' })`. `scroll-mb-28` deja la barra fija de secciones fuera del camino (DISENO 3, WCAG 2.4.11) | — |
| Enviando | El foco se queda en el botón de confirmar (`aria-busy`). Ver 5.2 | «Guardando…» |
| Éxito | En la confirmación de la fila (`hecho-{id}`), que se desplaza a la vista. La fila pudo moverse en la lista porque se ordena por fecha: el foco la sigue | El texto de la confirmación (`role="status"`) |
| Error del campo (validación o 422) | En el campo, con `aria-invalid` | El mensaje, por `aria-describedby` |
| Error del panel (red, 404, 409, 412) | En el mensaje (`role="alert"`, `tabIndex={-1}`), sin desplazar con `preventScroll`. Después se desplaza el panel entero a la vista | El mensaje |
| 403 | Al `h1` de la pantalla de permiso de MATU-36 o MATU-44 | El título de esa pantalla |

**Roles y regiones vivas (decidido en la revisión visual, 1.3).** La confirmación (`hecho-{id}`), el error del panel (`falla-{tipo}-{id}`) y el 404 (`aviso-insumos`) llevan `role="status"` o `role="alert"` directo, sin `Anunciado`, porque **reciben el foco**: el lector los lee al enfocarlos. Es la misma regla que dejó el PR #53 para `AvisoOk` y `falla-{id}` de MATU-37. `Anunciado` es para los avisos que aparecen **sin mover el foco**, como el error de «Seguir» en la fila. Un aviso nunca usa los dos a la vez, para que no se lea dos veces.

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
| Fuera de rango (pantalla o API, `errores[].campo` de la cantidad): «Compré» en envases sobre 99, en unidades sobre 10.000, «Me quedan» sobre 100.000 | Bajo el campo | Igual. La pantalla lo valida antes de enviar, y el texto es el mismo si lo devuelve la API |
| «Compré» deja lo que queda sobre 100.000 (la suma con lo que MATU calculaba) | Bajo el campo | Igual. Solo lo sabe la API: la pantalla no conoce lo que queda hoy |
| `cobertura_maxima` | Bajo el campo | Igual. El panel sigue abierto con lo escrito |
| Otro 422 | Error del panel | «No pudimos guardar. Revisa los datos y vuelve a intentarlo.» [L 18] |

Nunca se muestra `title`, `detail` ni `mensaje` de la API.

### 5.5 Otros errores

| Respuesta | Texto | Qué pasa |
|---|---|---|
| Red o 5xx | «No pudimos guardar. Revisa tu conexión y vuelve a intentarlo.» [L 17] | Error del panel. El panel sigue abierto con lo escrito y el botón vuelve a «Anotar la compra» o «Anotar lo que queda». No se reintenta solo |
| 404 | «Este insumo ya no está. Puede que alguien de tu familia lo haya eliminado.» [NUEVO] | Se cierra el panel, se recarga la lista en silencio (`cargar(true)`) y el mensaje va arriba, en el lugar del `AvisoOk`, como `MensajeError` con `role="alert"` y el foco. La fila ya no existe, así que el mensaje no puede ir en ella |
| 403 `sin-consentimiento` o `revision-vencida` | Los de MATU-36 y MATU-44 [L 18, L 22] | Se cierra el panel y la pantalla pasa al estado de permiso (`setCarga(permiso)`), como hoy con «Seguir» |
| 409 `perfil-inactivo` (A3: alguien desmarcó «Seguir» en otro teléfono mientras el panel estaba abierto) | «Alguien de tu familia dejó de seguir «{nombre}» mientras lo anotabas. No anotamos nada. Si quieres anotarlo, vuelve a marcar «Seguir».» [NUEVO] | Error del panel con «Ver cómo quedó» [L 17]. Al tocarlo se cierra el panel, se recarga la lista en silencio, la fila aparece en «Sin seguir» sin «Compré» ni «Me quedan», y el foco va a su casilla «Seguir» (`seguir-{id}`), que es el paso que sigue |
| 412 `version-desactualizada` (decisión 141) | «{autor} cambió «{nombre}» mientras lo anotabas. Revisa cómo quedó y vuelve a intentarlo.» [NUEVO, con la forma de L 17] · «Ver cómo quedó» [L 17] | Igual que el 409, salvo el foco: al tocar «Ver cómo quedó» va a la fila (`insumo-{id}`, `tabIndex={-1}`, sin contorno, como al anotar un insumo nuevo). El lector lee la fila con los datos nuevos, que es lo que pide el mensaje («Revisa cómo quedó»), y el `Tab` siguiente llega a «Compré» de esa misma fila para volver a intentarlo. Si la fila ya no está, al `h1`. No se suma ni se reemplaza nada |
| 428 `falta-version` (no debería pasar: la pantalla siempre manda `If-Match`) | «No pudimos guardar este insumo. Vuelve a abrirlo y guarda de nuevo. Lo que escribiste sigue aquí.» [L 18] | Error del panel. El panel sigue abierto con lo escrito |
| 401 | El de MATU-36 (renovar una vez y, si falla, a la entrada) | — |

### 5.6 Sin permiso

- **Por rol:** no hay botones (3.7). No hay texto: no se explica una acción que no se ofrece.
- **Por autorización retirada o vencida:** la pantalla entera es la de permiso de MATU-36 3.1.3 y 3.1.4, con lo de MATU-44. No aparece ninguna fila.

---

## 6. Accesibilidad visual, temas y reflujo

- **Áreas táctiles:** «Compré», «Me quedan», «Anotar la compra», «Anotar lo que queda», «Volver», «Ver cómo quedó» y los «−» y «+» del `Stepper` miden `min-h-12` (51 px) y al menos 48 px de ancho. Entre un botón y el siguiente, `gap-3` (12,75 px), para no tocar el vecino con el pulgar.
- **Foco visible:** el contorno base de 3 px en `turquesa` con 2 px de separación, sobre `hoja` (6,7:1 claro y 8,2:1 oscuro). El panel que recibe el foco por programa no es un control y no lleva contorno.
- **Contraste, con los valores de DISENO.md:** texto `turquesa` sobre `hoja` 6,7:1 y 8,2:1 · anillo `turquesa` al 70 % del secundario sobre `hoja` 3,5:1 · `papel` sobre `turquesa` (confirmar) 6,0:1 y 9,4:1 · `tenue` sobre `hoja` (ayuda y sufijo) 7,2:1 y 8,1:1 · `tinta` sobre `ok-fondo` y `ok` sobre `ok-fondo` (confirmación) 5,9:1 o más · `borde` del campo sobre `hoja` 3,2:1 y 4,4:1 (medido en la revisión) · `pronto` del error sobre `hoja`, sobre 4,5:1. Se miden en la revisión en los dos temas.
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
| Compré, sobre el tope, con envase (más de 99) | Escribe un número de 1 a 99 envases. | [NUEVO] |
| Compré, sobre el tope, sin envase (más de 10.000) | Escribe un número hasta 10.000. | [L 18] |
| Compré, lo que queda pasaría de 100.000 (422) | Con esa compra quedarían más de 100.000 {sufijo}. Revisa cuántos compraste. («{sufijo}» es «unidades», «sobres», «ml» o «g») | [NUEVO] |
| Me quedan, campo vacío | Escribe cuántos quedan. Si no queda nada, escribe 0. | [L 18] |
| Me quedan, sobre el tope | Escribe un número hasta 100.000. | [L 18] |
| Compré, `cobertura_maxima` | Con esa compra alcanzaría para más de 10 años. Revisa cuántos compraste. | [NUEVO] |
| Me quedan, `cobertura_maxima` | Con esa cantidad alcanzaría para más de 10 años. Revisa cuántos quedan. | [NUEVO] |
| Otro 422 | No pudimos guardar. Revisa los datos y vuelve a intentarlo. | [L 18] |
| Red o 5xx | No pudimos guardar. Revisa tu conexión y vuelve a intentarlo. | [L 17] |
| 404 | Este insumo ya no está. Puede que alguien de tu familia lo haya eliminado. | [NUEVO] |
| 409 `perfil-inactivo` (A3) | Alguien de tu familia dejó de seguir «{nombre}» mientras lo anotabas. No anotamos nada. Si quieres anotarlo, vuelve a marcar «Seguir». | [NUEVO] |
| 412 | {autor} cambió «{nombre}» mientras lo anotabas. Revisa cómo quedó y vuelve a intentarlo. («Otra persona» si no hay autor, [L 18]) | [NUEVO] |
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
3. Como pagador u observador, no existe ningún «Compré» ni «Me quedan» en el DOM. En un insumo «Sin seguir», tampoco.
4. «Compré» en un insumo con 20 unidades por envase abre con «1» y «envase de 20 unidades», y el teclado del teléfono no se abre. «+» lo deja en «2» y «envases de 20 unidades». Se confirma con tres toques desde la fila.
5. «Compré» sin envase y «Me quedan» abren con el campo vacío y el foco en él.
6. Con la red lenta, la fila y el bloque «Se acaban pronto» no cambian hasta la respuesta, y el botón dice «Guardando…».
7. Después de anotar, la confirmación aparece dentro de la fila del insumo y recibe el foco, aunque la fila haya cambiado de lugar. Dice cuánto alcanza ahora y hasta cuándo.
8. Si el insumo estaba en «Se acaban pronto» y deja de corresponder, sale del bloque y su fila pierde «Te estamos avisando» sin recargar la página.
9. Un 422 `cobertura_maxima` deja el panel abierto, con el número escrito, el anillo `pronto` en el campo y el mensaje debajo.
10. A 320 px con texto al 200%, sin desplazamiento horizontal, con un nombre de 60 caracteres sin espacios y el sufijo «envases de 10.000 unidades».
11. Todo lo que se toca mide al menos 48 × 48 px, y el foco se ve en claro y en oscuro.
12. Ningún texto de la fila, del panel ni de la confirmación ofrece comprar, pedir, precios o catálogo, ni dice «quiebre», «stock» o «reposición».
13. «Ya lo resolví» en un insumo con 20 unidades por envase abre con «1» y «envase de 20 unidades», sin abrir el teclado. Un toque en «−» lo deja en 0, y confirmar con 0 solo descarta el aviso («Listo. No te avisaremos de nuevo…»).
14. «Ya lo resolví» en un insumo sin envase abre vacío, con el foco en el campo, igual que en MATU-37.
15. Con cualquiera de los tres paneles abiertos, «Anotar un insumo» no es macizo (A5).
16. Después de un 409 `perfil-inactivo` y «Ver cómo quedó», la fila queda en «Sin seguir», sin «Compré» ni «Me quedan», y con el foco en su «Seguir».

**Para la revisión:** el frontend deja levantable, contra el doble del contrato, una lista con un insumo con envase de 20 que esté en «Se acaban pronto» y salga al comprar 2, uno sin envase en sobres, uno en ml, uno «Sin seguir», uno de 60 caracteres sin espacios, el bloque «Se acaban pronto» con un insumo con envase y otro sin envase, y respuestas de 409 `perfil-inactivo`, 412, 422 `cobertura_maxima`, 422 por pasar de 100.000, 404, 403 `revision-vencida`, 500 y una respuesta lenta. Las capturas son a 360, 1280 y 1920 px, en claro y oscuro, y con texto al 200%.

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
| Compré, sobre el tope | Con envase: Escribe un número de 1 a 99 envases. · Sin envase: Escribe un número hasta 10.000. (de la sección 18) |
| Compré, lo que queda pasaría de 100.000 | Con esa compra quedarían más de 100.000 {unidades / sobres / ml / g}. Revisa cuántos compraste. |
| Me quedan, falta o sobre el tope | Escribe cuántos quedan. Si no queda nada, escribe 0. · Escribe un número hasta 100.000. (de la sección 18) |
| Más de 10 años | Compré: Con esa compra alcanzaría para más de 10 años. Revisa cuántos compraste. · Me quedan: Con esa cantidad alcanzaría para más de 10 años. Revisa cuántos quedan. |
| El insumo ya no está (404) | Este insumo ya no está. Puede que alguien de tu familia lo haya eliminado. |
| Dejaron de seguirlo (409) | Alguien de tu familia dejó de seguir «{nombre}» mientras lo anotabas. No anotamos nada. Si quieres anotarlo, vuelve a marcar «Seguir». · Ver cómo quedó |
| Otra persona lo cambió (412) | {autor} cambió «{nombre}» mientras lo anotabas. Revisa cómo quedó y vuelve a intentarlo. · Ver cómo quedó |
| Errores generales | No pudimos guardar. Revisa tu conexión y vuelve a intentarlo. (sección 17) · No pudimos guardar. Revisa los datos y vuelve a intentarlo. (sección 18) |

### Textos aprobados que cambian

Las filas de la sección 17 salen de la decisión A2 de Jorge del 07-11. Las de las secciones 13.1, 16 y 18 todavía necesitan su visto.

| Sección y fila | Hoy | Desde MATU-51 |
|---|---|---|
| 13.1, Nota bajo la fecha | Es un cálculo con lo que anotaste. Si compraste o te quedan menos, anótalo | Es un cálculo con lo que anotaste. Si compraste o te quedan menos, anótalo con «Compré» o «Me quedan». |
| 16, Cómo calculamos, observador y pagador | Dividimos lo que quedaba por lo que se usa, y contamos los días desde que la familia lo anotó. No sabe si compraron ni si cambió lo que usa {pila}. | Dividimos lo que quedaba por lo que se usa, y contamos los días desde que la familia lo anotó. Si compraron y no lo anotaron, no lo sabe. Tampoco sabe si cambió lo que usa {pila}. |
| 18, Lista, «Cómo calculamos» | … No sabe si compraste ni si cambió lo que usa {nombre}. | … Si compraste o cambió lo que queda, anótalo con «Compré» o «Me quedan». No sabe si cambió lo que usa {nombre}. (texto del analista) |
| 17, Panel | ¿Compraste? ¿Cuántos? / ¿Cuántos sobres? · Si no compraste, déjalo en blanco y solo dejamos de avisarte. · Guardando… · Volver | Con envase conocido: ¿Compraste? ¿Cuántos envases? · Si no compraste, déjalo en 0 y solo dejamos de avisarte. · Junto al campo: envase de {u} unidades / envases de {u} unidades (la cantidad de la sección 21). Sin envase: ¿Compraste? ¿Cuántos? / ¿Cuántos sobres? / ¿Cuántos ml? / ¿Cuántos gramos? · Si no compraste, déjalo en blanco y solo dejamos de avisarte. En los dos: Guardando… · Volver |
| 17, Con cantidad · Con cantidad, si sigue en 0 o menos | {cantidad} como «4» o «2 sobres» | Los mismos textos, con {cantidad} armada como en la sección 21: «2 envases de 20 unidades», «24 unidades», «1 sobre», «500 ml» |
| 17, Cantidad inválida | Escribe un número entre 1 y 9999, o déjalo en blanco. | Con envase: Escribe un número de 0 a 99. Si no compraste, déjalo en 0. · Sin envase: Escribe un número de 1 a 10.000, o déjalo en blanco. |
| 17, fila nueva: más de 100.000 o más de 10 años | — | Los de «Compré» de la sección 23: Con esa compra quedarían más de 100.000 {unidades / sobres / ml / g}. Revisa cuántos compraste. · Con esa compra alcanzaría para más de 10 años. Revisa cuántos compraste. |

---

## 12. Lo que Jorge debe ver

1. **Mínimo 0 en «Ya lo resolví» con envase (3.8).** Jorge pidió 1 por omisión y de 1 a 99. Dejo el 1 por omisión y el tope de 99, pero el «−» baja hasta 0, que MATU-37 ya trata como «no compré, solo deja de avisar». Sin eso, quien no compró tendría que borrar el número con el teclado, o anotaría una compra que no hizo. Si Jorge prefiere de 1 a 99 sin el 0, la ayuda tiene que decir «Si no compraste, borra el número y solo dejamos de avisarte.» y el error «Escribe un número de 1 a 99, o bórralo si no compraste.».
2. **La confirmación va dentro de la fila y no arriba de la lista.** Después de anotar, la lista se reordena por fecha y la fila puede moverse. Con la confirmación en la fila, el foco y la vista la siguen.
3. **Con envase, «Compré» y «Ya lo resolví» abren con 1 y sin el teclado.** Sin envase, y en «Me quedan», el campo abre vacío para no confirmar un número que no se contó.
4. **Los textos aprobados de las secciones 13.1, 16 y 18 que cambian** (sección 11). El de 360 px es el que más importa: hoy la nota corta dice «anótalo» sin decir dónde.

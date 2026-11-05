# MATU-37 · «Se acaban pronto» dentro de Insumos · Especificación de diseño

**Versión 1.0 · 03/11/2026** · agente 6 (UI/UX) · para el frontend y el backend, antes de construir
**Historia:** MATU-37, alertas de lo que se acaba (RF-11, RF-12). MATU avisa antes de que un insumo se acabe, y quien cuida lo cierra con «Ya lo resolví».
**Dónde se construye:** `web/`, dentro de la pantalla «Insumos» de MATU-36 (`web/src/familia/Insumos.tsx`), en el espacio que su especificación ya reservó (`docs/diseno/matu-36-insumos.md`, 3.2, «reservado para MATU-37»).

**Fuentes, en este orden:** `Demo/DISENO.md` y los tokens de `web/src/index.css` · `docs/diseno/matu-36-insumos.md` (marco, roles, filas, 412, errores) · «Qué se acaba» de la demo · `docs/lenguaje.md`, sección 13 · checklist de accesibilidad de `docs/estrategia-pruebas.md`, sección 7 · contrato `docs/api/propuestos/app-familia.openapi.yaml` (`listarPorAcabarse`, `descartarAlertaQuiebre`).

**Cómo se lee:** «» va tal cual. **[APROBADO]** está en `lenguaje.md` 13 o fue decidido por Jorge. **[PROPUESTO]** es nuevo: entra a `lenguaje.md` en el mismo pull request. `{pila}`, `{nombre}`, `{n}` y `{fecha}` como en MATU-36. `{cantidad}` usa la función `cantidad(n, unidad)` de `textosInsumos.ts` («4», «2 sobres»).

---

## 0. Lo que tiene que decidir alguien más

| # | Qué | Por qué importa | Mientras tanto |
|---|---|---|---|
| A1 | **El contrato contradice la decisión de Jorge.** `descartarAlertaQuiebre` es «sin cuerpo» y dice que «Ya lo compré» (`resuelta`, declarar reposición) es MATU-51, sprint 4. Jorge decidió que «Ya lo resolví» pregunte cuánto se compró y, con cantidad, se declare la compra y se recalcule | Sin cambiar el contrato, el campo de cantidad no tiene a dónde ir. **Lo decide el orquestador con Jorge**, no el diseño | La especificación sigue a Jorge (sección 5). Si se mantiene el contrato, se quita el campo de cantidad (3.3) y queda solo la confirmación sin cantidad |
| A2 | **El bloque se arma con `por-acabarse`, pero el botón necesita `alerta_id`.** `por-acabarse` no trae la alerta, y `alertas` no trae el nombre ni los días. Además, descartar no saca el insumo de `por-acabarse` (contrato) | Sin esto, después de «Ya lo resolví» el insumo seguiría en el bloque con el botón, y Carmen creería que no funcionó | Sección 5: pido un campo `alerta` en cada ítem de `por-acabarse` |
| A3 | **Roles: el contrato responde 404 al pagador y al observador; la indicación menciona 403.** | Solo cambia el texto del error | Ambos tienen texto (4.4). Como el botón no se muestra a esos roles, en la práctica no ocurre |

---

## 1. Para quién y qué

**Carmen** recibe el aviso «MATU: un insumo se está acabando. Abre la app para ver cuál» [APROBADO]. Abre la app con una mano y tiene que ver **cuál**, **cuándo** y **qué hacer**, sin bajar. Si ya compró, lo dice en dos toques y MATU recalcula. Si no compró pero lo tiene cubierto, lo cierra sin dar explicaciones.

**Rodrigo** (pagador u observador) ve lo mismo para estar al tanto, sin botón.

**Lo que la alerta nunca hace:** ofrecer comprar, pedir, precios ni catálogo (capa 3 aparte). No pide marca ni lugar de compra.

---

## 2. Dónde se ve: un bloque «Se acaban pronto» arriba de la lista

**Decisión:** un **bloque propio arriba de la lista**, en el espacio reservado por MATU-36, y **no** solo una marca en la fila.

**Por qué:**
1. **El aviso push dice «Abre la app para ver cuál».** Lo que lo cumple es que lo primero bajo el título sea justamente ese insumo. Con una marca en la fila, si hay 12 insumos y el ordenado por fecha queda abajo de otros sin alerta (dias_aviso distinto por insumo), Carmen tendría que buscar.
2. **La lista de MATU-36 se ordena por fecha estimada, no por alerta.** Un insumo con aviso de 14 días puede ir debajo de uno con 10 días sin aviso (aviso de 7). El bloque separa «me están avisando» de «cuánto alcanza todo».
3. **«Ya lo resolví» es una acción sobre la alerta, no sobre el insumo.** En la fila ya están «Seguir», «Cambiar» y la papelera; un cuarto control en la misma fila a 360 px se vuelve un tablero de botones. En el bloque, el botón está junto al aviso al que responde.
4. Es el lenguaje de la demo («Qué se acaba pronto» como sección propia).

**La fila de la lista no cambia** salvo una marca: los insumos que están en el bloque llevan, bajo el nombre, la palabra «Te estamos avisando» [APROBADO por Jorge el 03-11] con el ícono `Bell` (`size-5`, `aria-hidden`, `text-atenta`), en `text-base text-tinta`. Así el estado no depende de ver el bloque y nunca es solo color. Los de 0 días o negativo mantienen el `CircleAlert` de MATU-36.

**Sin alertas, el bloque no se muestra** (ni vacío, ni «todo bien»): la lista de MATU-36 queda igual que hoy. Ver 4.1.

---

## 3. La pantalla

### 3.1 Objetivo y jerarquía

**Objetivo:** Carmen ve cuál insumo se acaba, cuándo, y lo cierra si ya lo resolvió.

1. El bloque «Se acaban pronto», con cada insumo: nombre, «Alcanza para {n} días» y «Fecha estimada: {fecha}».
2. En cada aviso, «Ya lo resolví» (solo `admin` y `cuidador`).
3. Debajo, todo lo de MATU-36: la nota, «Anotar un insumo» y la lista.

**Una sola acción principal por pantalla:** «Anotar un insumo» sigue siendo el único `turquesa` macizo. «Ya lo resolví» es **secundario** (borde, sin fondo macizo) en la lista de avisos. Solo dentro del panel abierto de 3.3 el botón de confirmar pasa a principal, porque ahí es la única acción.

### 3.2 Esquema a 360 px

```
┌────────────────────────────────────┐
│ Insumos                            │  h1 (MATU-36)
│ ┌────────────────────────────────┐ │  section aria-labelledby, bg-atenta-fondo
│ │ (!) Se acaban pronto           │ │  h2 text-xl font-bold, ícono BellRing text-atenta
│ │ ┌────────────────────────────┐ │ │  ul; cada li una hoja bg-hoja ring-1 ring-linea
│ │ │ Pañal adulto M             │ │ │  font-bold break-words
│ │ │ Alcanza para 3 días        │ │ │  text-xl font-bold, cifra en cifras
│ │ │ Fecha estimada: 06/11/2026 │ │ │  text-base, fecha en cifras nowrap
│ │ │           [ Ya lo resolví ]│ │ │  secundario min-h-12, solo admin/cuidador
│ │ └────────────────────────────┘ │ │
│ │ ┌────────────────────────────┐ │ │
│ │ │ (!) Toallitas húmedas      │ │ │  0 o negativo: CircleAlert text-pronto
│ │ │ Puede que ya no quede      │ │ │
│ │ │ Según lo anotado, se       │ │ │
│ │ │ acababa el 01/11/2026.     │ │ │
│ │ │           [ Ya lo resolví ]│ │ │
│ │ └────────────────────────────┘ │ │
│ │ Es una estimación con lo que   │ │  text-base text-tenue (nota, 1 vez)
│ │ anotaste.                      │ │
│ └────────────────────────────────┘ │
│ Es un cálculo con lo que anotaste… │  MATU-36 desde aquí, sin cambios
│ [ + Anotar un insumo ]             │
│ (lista)                            │
└────────────────────────────────────┘
```

### 3.3 Esquema del panel «Ya lo resolví» (360 px)

Se abre **dentro del mismo `li`**, debajo de la fecha, reemplazando el botón (sin modal, sin deslizar). El foco va a la pregunta.

```
│ ┌────────────────────────────┐ │
│ │ Pañal adulto M             │ │
│ │ Alcanza para 3 días        │ │
│ │ Fecha estimada: 06/11/2026 │ │
│ │ ────────────────────────── │ │  border-t border-linea
│ │ ¿Compraste? ¿Cuántos?      │ │  label, font-bold
│ │ Si no compraste, déjalo en │ │  ayuda, text-base text-tenue
│ │ blanco y solo dejamos de   │ │
│ │ avisarte.                  │ │
│ │ [ −  ][   24   ][  + ]     │ │  Stepper de MATU-36, vacío al abrir,
│ │                            │ │  unidad al lado si es sobre/ml/g
│ │ [ Ya lo resolví ]          │ │  principal turquesa, al ancho del texto
│ │ [ Volver ]                 │ │  secundario
│ └────────────────────────────┘ │
```

- El campo es **opcional**, entero de 1 a 9999, en la unidad del insumo. Vacío = solo descartar. 0 cuenta como vacío. Sin marca, sin lugar, sin precio.
- Solo un panel abierto a la vez. Abrir otro cierra el anterior sin guardar.
- «Volver» cierra y devuelve el foco al botón «Ya lo resolví» de ese aviso.
- `Escape` equivale a «Volver».

### 3.4 Pantalla ancha (desde `@3xl/main`)

El bloque ocupa **el ancho de la columna izquierda** (la de la lista, `3fr`), arriba de la nota y del botón; la columna derecha («Cómo calculamos» o el formulario) no cambia. Cada aviso en un renglón cuando cabe: nombre a la izquierda, «Alcanza para…» y «Fecha estimada…» al centro, «Ya lo resolví» a la derecha (`flex flex-wrap items-center justify-between gap-x-6 gap-y-2`). El panel de 3.3 se abre bajo el renglón, con el campo y los dos botones en una fila (`flex flex-wrap items-end gap-4`). Botones al ancho de su texto.

**Aprobado en la revisión (03/11/2026):** cuando la columna no da para los tres en un renglón (por ejemplo a 1280 px, donde la columna mide unos 500 px), «Ya lo resolví» baja a su propio renglón alineado a la derecha. Es el `flex-wrap` esperado y se acepta.

```
┌───────────────────────────────────────────────┬───────────────────────────┐
│ Insumos                          [ + Anotar un insumo ]                    │
│ ┌ (!) Se acaban pronto ─────────────────────┐ │ ┌ Cómo calculamos ──────┐ │
│ │ Pañal adulto M   Alcanza para 3 días       │ │ │ …                     │ │
│ │                  Fecha estimada: 06/11/2026  [Ya lo resolví] │       │ │
│ │ Toallitas        Puede que ya no quede     │ │ └───────────────────────┘ │
│ │                  Según lo anotado…           [Ya lo resolví] │         │
│ │ Es una estimación con lo que anotaste.     │ │                           │
│ └────────────────────────────────────────────┘ │                           │
│ (nota y lista de MATU-36)                      │                           │
└───────────────────────────────────────────────┴───────────────────────────┘
```

### 3.5 Componentes y tokens (todos existentes; **ningún token nuevo**)

| Parte | Clases y tokens |
|---|---|
| Bloque | `section` con `aria-labelledby="titulo-se-acaban"`, `bg-atenta-fondo px-4 angosto:px-2 py-4 ring-1 ring-linea flex flex-col gap-3`. Sin borde lateral de color macizo (DISENO 5) |
| Título del bloque | `h2 id="titulo-se-acaban"`, `text-xl font-bold text-tinta`, con `BellRing` `size-6 text-atenta aria-hidden` |
| Cada aviso | `li` hoja: `bg-hoja px-4 angosto:px-2 py-3 ring-1 ring-linea`. No es botón |
| Nombre | `font-bold break-words` |
| Línea de días | Textos de MATU-36 3.2.1, `text-xl font-bold`, cifra en `cifras` |
| 0 días o negativo | `CircleAlert size-5 text-pronto aria-hidden` delante; texto en `text-tinta`. La palabra cambia («Se acaba hoy», «Puede que ya no quede»): la forma y la palabra cargan el estado, el color solo acompaña |
| Fecha | `text-base`, fecha en `cifras whitespace-nowrap` |
| «Ya lo resolví» (cerrado) | Botón secundario de MATU-36 («Cambiar»), `min-h-12`, `aria-label="Ya lo resolví: {nombre}"`, `aria-expanded="false"`, `aria-controls` al panel |
| Panel | `div` con `border-t border-linea mt-3 pt-3 flex flex-col gap-3` |
| Campo | `Stepper` de MATU-36 con `label` visible y `aria-describedby` a la ayuda; `inputMode="numeric"`; vacío por defecto |
| Confirmar | Botón principal (`bg-turquesa`), `min-h-12`, con estado cargando |
| Volver | Secundario, `min-h-12` |
| Confirmación | `Aviso` de MATU-36 tipo éxito (`bg-ok-fondo text-tinta`, `CircleCheck text-ok`), `role="status"`, `aparecer` 180 ms; inmediato con `prefers-reduced-motion` |
| Error | `Aviso` de error de MATU-36 (`bg-pronto-fondo`, `CircleAlert text-pronto`), `role="alert"`, dentro del panel |

Contrastes a verificar en la revisión (claro y oscuro): `atenta` sobre `atenta-fondo` y `tinta` sobre `atenta-fondo` ≥ 4,5:1; `pronto` (ícono) sobre `hoja` ≥ 3:1; borde del botón secundario sobre `hoja` ≥ 3:1.

---

## 4. Estados

### 4.1 Sin alertas
El bloque **no se renderiza**. La pantalla es MATU-36 tal cual. Sin mensaje «no hay alertas»: no agrega nada a Carmen y empuja la lista hacia abajo.

### 4.2 Cargando
La lista y el bloque se piden juntos; mientras tanto, el «Cargando los insumos…» de MATU-36. **No se muestra la lista sin el bloque y después el bloque empujando** (salto de contenido): se pinta todo cuando llegan ambas. Si `por-acabarse` falla y la lista no, se muestra la lista y, en el lugar del bloque, el error de 4.6.

### 4.3 Una o varias
- Orden: el que da la API (fecha estimada, luego `id`). Los de 0 o negativo quedan arriba naturalmente.
- **Sin límite visual ni «ver más»:** la lista está acotada por los perfiles activos. Si hay más de 3, el título dice cuántos: «Se acaban pronto ({n})» [APROBADO por Jorge el 03-11], para que a 360 px se sepa que hay que bajar.
- Un solo aviso: el mismo bloque con un `li`.

### 4.4 Cerrando («Ya lo resolví» confirmado)
- **Sin interfaz optimista.** El botón principal pasa a «Guardando…» [APROBADO por Jorge el 03-11], `aria-busy="true"`, deshabilitado junto con «Volver» y el campo. El aviso no se mueve ni desaparece hasta la respuesta.
- **200:** se vuelve a pedir `por-acabarse` y la lista. El aviso sale del bloque (o se recalcula y sigue, si la compra no alcanzó a salir de la ventana). La confirmación va **arriba del bloque** (o en su lugar si quedó vacío) y recibe el foco:
  - Con cantidad: «Anotamos tu compra de {nombre}: {cantidad}. Ahora alcanza para {n} días.» [APROBADO por Jorge el 03-11]. Si `{n}` es 1, «1 día»; si el recálculo da 0 o negativo, «Anotamos tu compra de {nombre}: {cantidad}. Si te quedan menos, cámbialo en la lista.» [APROBADO por Jorge el 03-11]
  - Sin cantidad: «Listo. No te avisaremos de nuevo por {nombre} hasta que cambie la fecha estimada.» [APROBADO por Jorge el 03-11]
  - Mismo verbo: el botón dice «resolví», la confirmación confirma lo hecho («Anotamos tu compra» / «Listo»).
- Si quedan otros avisos, después de leer la confirmación el foco sigue el orden natural hacia el primer aviso.

### 4.5 Errores del cierre (dentro del panel, `role="alert"`, el panel sigue abierto con lo escrito)
| Respuesta | Texto | Qué pasa |
|---|---|---|
| 409 `alerta-cerrada` | «Alguien de tu familia ya resolvió este aviso.» [APROBADO por Jorge el 03-11] | Botón «Ver cómo quedó» [APROBADO por Jorge el 03-11] (secundario) que recarga el bloque y la lista. No se reintenta solo |
| 404 | «Este aviso ya no está. Puede que el insumo se haya cambiado o eliminado.» [APROBADO por Jorge el 03-11] | Mismo «Ver cómo quedó» |
| 403 `sin-consentimiento` / `revision-vencida` | Los de MATU-36 (3.1.3 y 3.1.4) | Se muestra el estado de permiso de MATU-36 en vez de la lista |
| 403 por rol (si el contrato lo cambia, A3) | «Solo quien administra o cuida puede resolver un aviso.» [APROBADO por Jorge el 03-11] | Se cierra el panel |
| 422 (cantidad fuera de rango) | «Escribe un número entre 1 y 9999, o déjalo en blanco.» [APROBADO por Jorge el 03-11] | Junto al campo, `aria-invalid`, foco al campo |
| 401 | Igual que MATU-36 (renovar una vez; si falla, entrada) | — |
| Red o 5xx | «No pudimos guardar. Revisa tu conexión y vuelve a intentarlo.» [APROBADO por Jorge el 03-11] | El botón principal vuelve a «Ya lo resolví» |

### 4.6 Error al cargar el bloque
En el lugar del bloque, `Aviso` de error: «No pudimos ver qué se acaba pronto.» [APROBADO por Jorge el 03-11] con botón secundario «Volver a intentar» (de MATU-36). La lista se muestra igual.

### 4.7 Roles
`pagador` y `observador`: el bloque completo, **sin** «Ya lo resolví» (no deshabilitado: ausente). La marca «Te estamos avisando» de la fila también la ven.

### 4.8 Conflicto 412
No aplica al cierre (sin `ETag`). Si la cantidad recalcula el perfil y el backend exige `If-Match`, ver A2/sección 5: el 412 usaría el texto de MATU-36 (6.2, «Otra persona…»).

---

## 5. Lo que necesito de la API (para el backend)

1. **`GET …/consumo/por-acabarse`: cada ítem con dos campos nuevos**, calculados por el backend: `avisando: boolean` (verdadero si `dias_restantes ≤ dias_aviso` **y** no hay una alerta `descartada` ni `resuelta` para la `fecha_quiebre_estimada` actual) y `alerta_id: uuid | null` (`null` si el trabajo diario aún no la creó). El bloque muestra solo los `avisando: true`; la marca «Te estamos avisando» de la lista usa el mismo dato. La regla vive en el backend, no en la pantalla.
2. **Poder cerrar aunque la alerta aún no exista** (`alerta_id` `null`): o el backend la crea al pedir `por-acabarse`, o el cierre se hace por perfil: `POST …/consumo/{perfil_id}/resolver`. Prefiero la ruta por perfil: una sola llamada, la pantalla no depende del trabajo diario.
3. **Cuerpo opcional `{ "cantidad": integer 1..9999 | null }`** (decisión de Jorge, A1). Con cantidad: suma al stock vigente estimado de hoy (o fija el stock, a definir por backend y Jorge; el texto «compraste» funciona con ambas), cierra la alerta como `resuelta` y devuelve el **perfil recalculado** (`dias_restantes`, `fecha_quiebre_estimada`) para la confirmación. Sin cantidad: `descartada`, devuelve el perfil sin cambios.
4. **Errores:** 409 `alerta-cerrada`, 404, 403 de consentimiento, 422 de `cantidad` con `errores[].campo = "cantidad"`. Nunca texto de la API en pantalla: la pantalla usa los de 4.5.
5. Auditoría y logs sin `nombre_libre` ni cantidad, como ya dice el contrato.

---

## 6. Accesibilidad

- Áreas táctiles: «Ya lo resolví», «Volver», «Ver cómo quedó», los botones del `Stepper`: `min-h-12 min-w-12`.
- Foco visible: el anillo de la capa base (2 px, `turquesa`) en todo; dentro de `bg-atenta-fondo` verificar 3:1 en la revisión.
- Estado nunca solo por color: título con palabra («Se acaban pronto»), ícono + palabra en 0/negativo, «Te estamos avisando» en la fila.
- Lectores de pantalla: el bloque es una región con nombre; cada `li` se lee nombre → días → fecha; el botón incluye el nombre en `aria-label`; confirmación `role="status"`, errores `role="alert"`.
- 320 px y texto al 200%: nombres largos con `break-words`, fecha `nowrap` solo en la fecha, botones bajan de renglón. Sin desplazamiento horizontal.
- `prefers-reduced-motion`: el panel abre y cierra sin animación; el aviso aparece inmediato.
- Proyector: nada relevante bajo `text-base`.

---

## 7. Textos

| Dónde | Texto | Estado |
|---|---|---|
| Aviso push (MATU-41) | MATU: un insumo se está acabando. Abre la app para ver cuál | [APROBADO] |
| Título del bloque | Se acaban pronto | [APROBADO por Jorge el 03-11] |
| Título con más de 3 | Se acaban pronto ({n}) | [APROBADO por Jorge el 03-11] |
| Días (2 o más / 1 / 0 / negativo) | Alcanza para {n} días · Alcanza para 1 día · Se acaba hoy · Puede que ya no quede | [APROBADO] |
| Fecha (n ≥ 0, salvo 0) | Fecha estimada: {fecha} | [APROBADO] (decisión de Jorge) |
| Fecha (negativo) | Según lo anotado, se acababa el {fecha}. | [PROPUESTO en MATU-36] |
| Nota al pie del bloque | Es una estimación con lo que anotaste. | [APROBADO por Jorge el 03-11] |
| Marca en la fila de la lista | Te estamos avisando | [APROBADO por Jorge el 03-11] |
| Botón | Ya lo resolví | [APROBADO] |
| `aria-label` del botón | Ya lo resolví: {nombre} | [APROBADO por Jorge el 03-11] |
| Pregunta (unidad) | ¿Compraste? ¿Cuántos? | [APROBADO por Jorge el 03-11] |
| Pregunta (sobre) | ¿Compraste? ¿Cuántos sobres? | [APROBADO por Jorge el 03-11] |
| Pregunta (ml / g) | ¿Compraste? ¿Cuántos ml? · ¿Compraste? ¿Cuántos gramos? | [APROBADO por Jorge el 03-11] |
| Ayuda del campo | Si no compraste, déjalo en blanco y solo dejamos de avisarte. | [APROBADO por Jorge el 03-11] |
| Confirmar | Ya lo resolví | [APROBADO] |
| Cargando | Guardando… | [APROBADO por Jorge el 03-11] |
| Volver | Volver | [APROBADO por Jorge el 03-11] |
| Éxito con cantidad | Anotamos tu compra de {nombre}: {cantidad}. Ahora alcanza para {n} días. | [APROBADO por Jorge el 03-11] |
| Éxito con cantidad, 0 o negativo | Anotamos tu compra de {nombre}: {cantidad}. Si te quedan menos, cámbialo en la lista. | [APROBADO por Jorge el 03-11] |
| Éxito sin cantidad | Listo. No te avisaremos de nuevo por {nombre} hasta que cambie la fecha estimada. | [APROBADO por Jorge el 03-11] |
| 409 | Alguien de tu familia ya resolvió este aviso. | [APROBADO por Jorge el 03-11] |
| 404 | Este aviso ya no está. Puede que el insumo se haya cambiado o eliminado. | [APROBADO por Jorge el 03-11] |
| 403 por rol | Solo quien administra o cuida puede resolver un aviso. | [APROBADO por Jorge el 03-11] |
| 422 | Escribe un número entre 1 y 9999, o déjalo en blanco. | [APROBADO por Jorge el 03-11] |
| Red o 5xx | No pudimos guardar. Revisa tu conexión y vuelve a intentarlo. | [APROBADO por Jorge el 03-11] |
| Botón tras 409/404 | Ver cómo quedó | [APROBADO por Jorge el 03-11] |
| Error al cargar el bloque | No pudimos ver qué se acaba pronto. | [APROBADO por Jorge el 03-11] |

Prohibido en todos: «quiebre», «stock», «reponer», precios, y «comprar» o «pedir» como **acción ofrecida** (botón o invitación; «compraste» solo como pregunta sobre lo ya hecho), y cualquier término de lenguaje 3.2. Ningún texto asume el género de la persona cuidada (no se nombra a la persona en el bloque).

---

## 8. Criterios visuales verificables

1. Con avisos, lo primero bajo el `h1` es el bloque «Se acaban pronto», visible sin desplazar a 360 × 640 con el primer aviso completo (nombre, días, fecha, botón).
2. «Anotar un insumo» es el único `turquesa` macizo con el panel cerrado; con el panel abierto, el «Ya lo resolví» del panel es el único.
3. Ningún aviso comunica su estado solo con color: cada uno tiene palabra, y los de 0 o negativo además `CircleAlert`.
4. Sin avisos, la pantalla es idéntica a la de MATU-36 aprobada (sin bloque vacío).
5. Como `pagador` u `observador`, no existe ningún «Ya lo resolví» en el DOM.
6. Tras confirmar, el aviso no desaparece antes de la respuesta 200 (probar con red lenta).
7. A 320 px y con texto al 200%, sin desplazamiento horizontal con un nombre de 60 caracteres sin espacios.
8. Ningún botón, enlace ni texto del bloque menciona comprar, pedir, precios o catálogo como acción.
9. Todos los controles miden al menos 48 × 48 px y el foco se ve sobre `atenta-fondo` en claro y oscuro.

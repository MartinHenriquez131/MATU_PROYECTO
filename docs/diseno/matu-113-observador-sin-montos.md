# MATU-113 · «Se informa» ve el pedido sin montos · Especificación de diseño

**Versión 1.0 · 17/11/2026** · Agente 6, UI/UX. Especifica y no construye.

**Viene de:** las decisiones de Jorge del 17-11 y la revisión previa del analista (condiciones C8 a C11 y textos D4):
- quien «Se informa» deja de ver los montos del pedido **en todos los estados**;
- ve **el estado completo** del pedido (pagado, en camino, entregado, cancelado…), sin montos.

**Es frontend y textos.** No hay tokens nuevos y `Demo/DISENO.md` no cambia. Todo lo que se usa ya existe: `bg-hoja`, `ring-linea`, `border-linea`, `text-tinta`, `text-tenue`, `cifras`, `titular` y los tonos `neutro`, `ok` y `atenta` de `Etiqueta`.

**Se construye en:**
- `web/src/familia/Pedido.tsx`: `Carrito`, `LineaCarrito` y el pie;
- `web/src/familia/TusPedidos.tsx`: `FilaDelObservador`, que también usa `BloqueTusPedidos` al final de «Pedido»;
- `textosPedido.ts` y `textosTusPedidos.ts`.

**Marcas:**
- **[L n]**: ya está en `lenguaje.md`, sección n. La sección 38 («Tus pedidos», MATU-92) todavía no está en `main` del repositorio MATU, y sus textos se citan como están en `textosTusPedidos.ts`.
- **[NUEVO]**: entra a `lenguaje.md` 31 o 38 y lo aprueba Jorge.

**En la interfaz nunca se dice** «observador», «te devolvemos», «precio de ejemplo», «IVA», «Subtotal» ni «Productos:» para este rol. El rol, cuando se nombra, es «Se informa» (L 34).

---

## 0. Lo que hay hoy (leído en el código de la rama, 17-11)

No levanté la pantalla para esta especificación: la vista del observador cambia con el contrato que el backend está haciendo en paralelo. La revisión visual (sección 6) se hace con la pantalla funcionando.

| Dónde | Qué muestra hoy a quien «Se informa» | Problema |
|---|---|---|
| `LineaCarrito`, ~1105 y ~1108 | `{precio} cada uno` e «IVA incluido» o «Precio de ejemplo · IVA incluido» | Montos (C8) |
| `LineaCarrito`, ~1135 | «Subtotal: {precio}» | Montos (C8) |
| Pie del `Carrito`, ~960 | «Productos: {precio}», que sale de `precio_unitario`. Sin el campo, la suma da `NaN` | Montos y `NaN` (C8) |
| Pie, ~1009 | «Quien administra el grupo o quien cuida a {pila} puede cambiar el pedido y ver el total.» | Ya no explica por qué no ve precios |
| `AvisoPiloto`, ~1023 | «Precios de ejemplo. MATU todavía no tiene convenio con comercios, y en esta demo no se cobra dinero real.» | Habla de precios y de cobro (C8) |
| «Si falta», ~1154 | «Si falta: lo sacamos y te devolvemos su precio.» | «te devolvemos» (C9) |
| `Retracto`, en cada línea | «Derecho a retracto: tienes 10 días hábiles desde que lo recibes.» | Le habla a quien compra. Quien «Se informa» no puede arrepentirse (L 38: «Pueden arrepentirse de la compra quien administra el grupo y quien la pagó.») |
| Estado del pedido sin pagar | Nada: la nota «Ya confirmaste el total…» es solo de admin y cuidador | No ve en qué estado está (decisión 2) |
| `FilaDelObservador` («Tus pedidos» y el bloque al final de «Pedido») | La fecha sola, «Pagado» siempre y los productos con su cantidad. **Ningún monto** | Siempre «Pagado», aunque el pedido vaya en camino o esté entregado (decisión 2). La fecha sola no dice de qué es |
| Detalle de «Tus pedidos» | No existe para este rol: la fila no se abre y la ruta lleva a la lista (MATU-92 2.1) | Nada que cambiar |

---

## 1. Decisiones y dependencias

| # | Qué | Propuesta | Quién |
|---|---|---|---|
| **O1** | **El estado completo en la fila de «Tus pedidos». Bloquea la parte 3.** `PedidoPagadoFilaObservador.estado` es `Literal["pagado"]` en el contrato (`backend/app/modules/backoffice/api/esquemas.py`, ~310) y la fila no trae `entregado_en`. Además, la especificación de MATU-92, 3.4, dice «El observador ve siempre «Pagado», en todos los estados» (D-92-1). La decisión 2 del 17-11 dice lo contrario | Que el backend, dentro de C7, dé a la fila del observador el mismo `estado` de la familia que `PedidoPagadoFila` (los 9 valores) y `entregado_en`, sin montos. Con eso, la decisión 2 reemplaza a D-92-1 en lo del estado, y la 3.4 de MATU-92 queda corregida por esta especificación. **No elijo yo:** lo informo al orquestador | Orquestador y backend |
| O2 | Sin «Derecho a retracto» para quien «Se informa» | La línea muestra solo producto, presentación, comercio, cantidad y «Si falta». El derecho lo ven quienes pueden ejercerlo | Jorge, con visto del analista (es información al consumidor, Ley 19.496) |
| O3 | Sin `AvisoPiloto` para quien «Se informa» | El aviso es «una vez por pantalla con precios» (L 31, «Aviso del piloto»), y esta pantalla ya no tiene precios. El «(comercio ficticio)» de cada línea sigue diciendo que es una demo | Jorge |
| O4 | El texto de D4 para la línea («{cantidad} × {producto} · De {comercio}») **no se usa tal cual** | En «Pedido» la línea sigue siendo la tarjeta de MATU-61, con el nombre como título y el comercio debajo. En la fila de «Tus pedidos», «{cantidad} × {producto}» ya existe, y el comercio no viene en `ProductoDeLaFila`. No se pide al contrato | — |
| O5 | «Si falta: lo sacan del pedido y se devuelve su precio.» (D4) pasa a **«Si falta: lo sacamos del pedido.»** | Es más corta. No habla de plata, así que no anuncia una devolución que quien «Se informa» no va a ver. Y mantiene el «nosotros» de MATU, como «Si falta: lo buscamos en otro comercio.» [L 31]. El «lo buscan» de D4 no dice quién lo busca | Jorge |

**Si O1 no entra en esta tarjeta,** la parte 3 se construye igual con «Pagado el {fecha}» y la etiqueta «Pagado» de siempre (3.3, columna «Sin O1»), y el estado completo queda como faltante en una tarjeta propia.

**Cómo decide la pantalla qué vista pinta:** por la forma de lo que llega (la guarda de `PedidoObservador`, como `esFilaCompleta` en MATU-92), nunca por el rol que tiene en memoria. Si llega una vista sin `etag` (`!esVistaCompleta`), se pinta la de este documento aunque traiga algún monto: **la vista de «Se informa» nunca lee ni muestra un campo de dinero**.

---

## 2. «Pedido» para quien «Se informa» (`/insumos/pedido`)

### 2.1 Objetivo y jerarquía

**Objetivo:** el hermano que «Se informa» sabe qué se le va a pedir a María, de dónde y en qué va el pedido, sin ver cuánto cuesta y sin quedarse con la duda de por qué.

1. El título «Tu pedido» y la bajada.
2. **El estado del pedido**, en una `Etiqueta` con ícono y palabra.
3. Los productos: nombre, presentación, comercio, cantidad y qué pasa si falta.
4. Al final, quién ve los precios.
5. Debajo, el bloque «Tus pedidos» con el último pedido pagado (parte 3).

**No hay acción principal.** No hay ningún `Boton` macizo ni secundario en la vista. Lo único que se toca son las pestañas y, si aparece, «Ver todos tus pedidos» (`variante="texto"`).

### 2.2 Esquema a 360 px

```
│ Catálogo · Lista · Pedido · Tus pedidos │  PestanasInsumos, sin cambios
│                                         │
│ Tu pedido                               │  h1 Titulo text-3xl
│ Lo que se va a pedir para María.        │  p text-base text-tenue max-w-prose
│ [⏱ Falta pagarlo]                       │  p > Etiqueta (2.4)
│                                         │
│ Nunca lo cambiamos por otra marca ni    │  p text-base font-bold, sin cambios
│ por otro producto.                      │
│ ┌─────────────────────────────────────┐ │  li rounded-xl bg-hoja ring-1 ring-linea
│ │ Pañal adulto M                      │ │  h2 text-xl font-bold
│ │ Paquete de 30                       │ │  p text-base text-tenue (si distinto del nombre)
│ │ De Farmacia Los Aromos (comercio    │ │  p text-base
│ │ ficticio)                           │ │
│ │ 2 envases de 30 unidades            │ │  p text-lg, la cifra en cifras
│ │ ─────────────────────────────────── │ │  border-t border-linea pt-3
│ │ Si falta: lo buscamos en otro       │ │  p text-base
│ │ comercio.                           │ │
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ Suplemento vainilla                 │ │
│ │ …                                   │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ Los precios y el total los ven quien    │  p text-base text-tenue max-w-prose
│ administra el grupo, quien cuida a      │
│ María y quien paga.                     │
│ ─────────────────────────────────────── │
│ Tus pedidos                             │  BloqueTusPedidos (parte 3)
│ ┌─────────────────────────────────────┐ │
│ │ Pagado el 11/11/2026                │ │
│ │ [🚚 En camino]                      │ │
│ │ • 2 × Pañal adulto M x30            │ │
│ └─────────────────────────────────────┘ │
```

- **Sin** el aviso del piloto, el precio, «IVA incluido», «Subtotal:», «Productos:», la entrega ni el derecho a retracto.
- Entre los elementos de la tarjeta, el mismo `gap-y-3` de hoy. **No queda un hueco** donde estaba el precio: los elementos se juntan.

### 2.3 Esquema en pantalla ancha (desde `@3xl/main`, 1280 y 1920 px)

```
│ Catálogo · Lista · Pedido · Tus pedidos                                              │
│ Tu pedido                                              h1 @2xl/main:text-5xl         │
│ Lo que se va a pedir para María.                                                     │
│ [⏱ Falta pagarlo]                                                                    │
│                                                                                      │
│ Nunca lo cambiamos por otra marca…           │ Los precios y el total los ven quien  │
│ ┌──────────────────────────────────────────┐ │ administra el grupo, quien cuida a    │
│ │ Pañal adulto M        │ 2 envases de 30  │ │ María y quien paga.                   │
│ │ Paquete de 30         │ unidades         │ │                                       │
│ │ De Farmacia Los       │ ──────────────── │ │ columna derecha, sticky, como hoy     │
│ │ Aromos (comercio      │ Si falta: lo     │ │                                       │
│ │ ficticio)             │ buscamos en otro │ │                                       │
│ │                       │ comercio.        │ │                                       │
│ └──────────────────────────────────────────┘ │                                       │
│  3fr                                         │  2fr                                  │
│ ──────────────────────────────────────────────────────────────────────────────────── │
│ Tus pedidos   (max-w-3xl)                                                            │
```

- La rejilla `3fr / 2fr` y la columna derecha `sticky` siguen como están. Para este rol, la columna derecha tiene solo la frase del pie.
- En la tarjeta, desde `@2xl/linea`: a la izquierda el nombre, la presentación y el comercio. A la derecha la cantidad y «Si falta». La fila 2 de la izquierda, donde iba el retracto, queda vacía sin alto propio.
- A 1920 px el contenido sigue limitado por el `main` de siempre. La etiqueta y la frase no se estiran (`max-w-prose`).

### 2.4 La etiqueta del estado

Va en un `p` propio, debajo de la bajada y antes de «Nunca lo cambiamos…». Es un `Etiqueta` existente, siempre con ícono `lucide-react` y palabra. A 320 px (`angosto`) se oculta el ícono y queda la palabra.

| `estado` del pedido en curso | Tono | Ícono | Texto | Origen |
|---|---|---|---|---|
| `borrador` | `neutro` | `ShoppingBasket` | Sin confirmar | **[NUEVO]** |
| `total_confirmado` (con o sin un pago en curso) | `neutro` | `Clock` | Falta pagarlo | **[NUEVO]** |
| `vencido` | `atenta` | `Hourglass` | Hay que confirmarlo de nuevo | **[NUEVO]** |
| Otro estado (no debería llegar por `…/pedido-en-curso`) | El de MATU-92 4.2 | El de MATU-92 4.2 | El de MATU-92 4.2, **sin la explicación** | [L 38] |

- No es una región viva: no se anuncia al cargar. Si el pedido cambia de estado al volver a leerlo, la etiqueta cambia sin anuncio y sin mover el foco.
- No se usa `ok` para ninguno de los tres: ninguno es un final.

### 2.5 La línea

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Nombre | `h2 text-xl font-bold break-words`, sin cambios | `{producto}` | — |
| Presentación | `p text-base text-tenue`, solo si es distinta del nombre | `{presentacion}` | — |
| Comercio | `p text-base break-words` | De `{comercio}` (comercio ficticio) | [L 31] |
| Cantidad | `p text-lg tabular-nums`, la cifra en `cifras` | `{n}` + el sufijo de la sección 21, por ejemplo «2 envases de 30 unidades» | [L 31] |
| Si falta | `p text-base`, dentro de `border-t border-linea pt-3` | Si falta: lo buscamos en otro comercio. · Si falta: lo sacamos del pedido. | [L 31] · **[NUEVO]** (O5) |

**No van:** el precio, «cada uno», «IVA incluido», «Precio de ejemplo · IVA incluido», «Subtotal:», «En tu lista:», el retracto (O2), `Stepper`, las opciones de «Si falta» ni «Sacar del pedido».

### 2.6 El pie

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Quién ve los precios | `p max-w-prose text-base text-tenue` | Los precios y el total los ven quien administra el grupo, quien cuida a `{pila}` y quien paga. | **[NUEVO]** (D4) |

- **Reemplaza, solo para este rol,** a «Productos: {precio}», a «El envío y el total los ves al confirmar…» y a «Quien administra el grupo o quien cuida a {pila} puede cambiar el pedido y ver el total.». El pagador sigue igual.
- La misma frase en los tres estados.

### 2.7 Estados de la pantalla

| Estado | Qué ve quien «Se informa» | Texto | Origen |
|---|---|---|---|
| **Cargando** | Sin cambios (MATU-61 11) | Cargando… | [L 26] |
| **Error al traer** | Sin cambios: una columna con `CloudOff` y «Volver a intentar», el único macizo | No pudimos traer tu pedido. Revisa tu conexión e inténtalo de nuevo. | [L 31] |
| **Vacío** (sin pedido en curso, también apenas se paga) | La bajada pasa a ser N1. Debajo, sin cambios: baldosa `bg-tinta/7 text-tenue`, sin botones, y el bloque «Tus pedidos» si hay pagados. La bajada de siempre invita a revisar y a elegir cantidades, y este rol no puede hacer ninguna de las dos. Aquí se elige por el rol (`rol === 'observador'`) porque no hay vista que mirar y es solo un texto, sin datos: la regla de no elegir por el rol protege la lectura de dinero, y eso aquí no aplica. El pagador y los demás roles mantienen su bajada | Bajada: Lo que se va a pedir para `{pila}`. Baldosa: Todavía no hay un pedido para `{pila}`. | N1 y [L 31] |
| **Sin autorización, por renovar, apagado y 404** | Sin cambios (MATU-61 4.4 y 11). Ninguno muestra montos | Los de L 31 | [L 31] |
| **Borrador** | 2.2, con «Sin confirmar» | 2.4 a 2.6 | — |
| **Total confirmado** | 2.2, con «Falta pagarlo» | 2.4 a 2.6 | — |
| **Vencido** | 2.2, con «Hay que confirmarlo de nuevo» | 2.4 a 2.6 | — |
| **Pagado y siguientes** | No están en «Pedido»: el pedido en curso responde 404 y se ve el vacío. El pagado aparece en el bloque «Tus pedidos» (parte 3) | — | — |
| **Conflicto (412)** | No aplica: quien «Se informa» no escribe nada en el pedido | — | — |
| **Llega una vista con montos** (contrato viejo o defecto) | Se pinta igual que arriba. Ningún monto en pantalla. Ningún `NaN` | — | — |

---

## 3. La fila de «Tus pedidos» para quien «Se informa»

La usan la lista `/insumos/tus-pedidos` y el bloque al final de «Pedido». **No tiene montos hoy y no se le agregan.** Sigue sin abrirse: es un `li`, no un `button`, y no recibe el foco.

### 3.1 Objetivo

Quien «Se informa» sabe cuándo se pagó cada pedido, en qué va y qué traía.

### 3.2 Esquema a 360 px y en pantalla ancha

```
│ ┌─────────────────────────────────────┐ │  li rounded-xl bg-hoja px-4 py-3 ring-1 ring-linea
│ │ Pagado el 11/11/2026                │ │  p text-lg font-bold, la fecha en cifras
│ │ [✓ Entregado el 13/11/2026]         │ │  Etiqueta (3.3), sin explicación
│ │ • 2 × Pañal adulto M x30            │ │  ul list-disc ps-5 text-base, sin cambios
│ │ • 1 × Suplemento vainilla x12       │ │
│ └─────────────────────────────────────┘ │
```

En pantalla ancha es igual, dentro del `max-w-3xl` de hoy: una sola columna, sin nada a la derecha (allí va el total en la fila de quien ve el pago).

La frase bajo la bajada de la lista sigue igual: «Quien administra el grupo, quien cuida a `{pila}` y quien paga ven el detalle.» [L 38].

### 3.3 Partes

| Parte | Con O1 | Sin O1 | Texto | Origen |
|---|---|---|---|---|
| Fecha | `p text-lg font-bold` | igual | Pagado el `{DD/MM/AAAA}` | **[NUEVO]** (D4, la misma pieza «Pagado el» del detalle de MATU-92) |
| Estado | `EtiquetaEstado` de MATU-92 4.2, con su tono y su ícono, **sin la explicación** | `Etiqueta tono="ok"` con `Check` | Con O1: Pagado · Enviado al comercio · En preparación · Listo para salir · En camino · Entregado el `{fecha}` · No pudimos entregarlo · Entrega reprogramada · Cancelado. Sin O1: Pagado | [L 38] |
| Productos | Sin cambios | igual | `{cantidad}` × `{producto}` · De este pedido guardamos solo lo que se pagó y lo que se devolvió. | [L 38] |

**Sin la explicación, en ningún estado.** Tres de ellas no sirven para este rol:
- «Te escribimos para coordinar otra entrega o devolverte el total.» habla de plata y le habla a quien pagó;
- «Te avisamos cuando salga de nuevo.» promete un aviso que este rol puede no recibir;
- «Devolvimos {total}, envío incluido…» es un monto.

Para que la regla sea una sola, tampoco va «Lo estamos enviando al comercio…».

---

## 4. Textos

### 4.1 Los que hay que aprobar

| # | Dónde | Texto | Va a |
|---|---|---|---|
| N1 | Bajada de «Pedido», «Se informa» | Lo que se va a pedir para `{pila}`. | L 31 |
| N2 | Etiqueta, borrador | Sin confirmar | L 31 |
| N3 | Etiqueta, total confirmado | Falta pagarlo | L 31 |
| N4 | Etiqueta, vencido | Hay que confirmarlo de nuevo | L 31 |
| N5 | Pie, «Se informa» | Los precios y el total los ven quien administra el grupo, quien cuida a `{pila}` y quien paga. | L 31 (D4) |
| N6 | Si falta, «Se informa», con la regla `quitar` | Si falta: lo sacamos del pedido. | L 31 (O5, mejora D4) |
| N7 | Fila de «Tus pedidos», «Se informa» | Pagado el `{DD/MM/AAAA}` | L 38 (D4) |

N1 es la única que no venía en D4. La de hoy («Revisa los productos y cuántos quieres…») invita a algo que este rol no puede hacer. Si Jorge no la aprueba, queda la de hoy y no rompe nada.

### 4.2 Los que ya están y se reusan

- De `{comercio}` (comercio ficticio) [L 31]
- Nunca lo cambiamos por otra marca ni por otro producto. [L 31]
- Si falta: lo buscamos en otro comercio. [L 31]
- Todavía no hay un pedido para `{pila}`. [L 31]
- Pagado y los demás estados de MATU-92 4.2 [L 38]
- Quien administra el grupo, quien cuida a `{pila}` y quien paga ven el detalle. [L 38]

### 4.3 Lo que cambia en `lenguaje.md` 31, para el orquestador

- En la fila «Pagador y observador», la frase «…puede cambiar el pedido y ver el total.» queda **solo para el pagador**.
- En la fila «Si falta, pagador y resumen», «…y te devolvemos su precio.» queda **solo para el pagador**.
- En el texto de la sección, la palabra «observador» va como nombre interno, nunca en la interfaz.

---

## 5. Accesibilidad

- **El estado nunca solo por color:** cada `Etiqueta` lleva su palabra, y a 320 px queda solo la palabra.
- **Contraste:** `text-tenue` sobre `bg-hoja` y sobre el fondo, y las etiquetas `neutro`, `ok` y `atenta`, ya están medidos en DISENO.md con al menos 4,5:1 en los dos temas. No hay combinaciones nuevas.
- **Foco:** la vista no agrega nada que se toque. Las pestañas y «Ver todos tus pedidos» conservan su anillo y sus 48 px.
- **Lector:** el orden del DOM es el de los esquemas: título, bajada, estado, «Nunca…», líneas, pie. La etiqueta se lee como texto, sin `aria-label` aparte. La fila de «Tus pedidos» se lee «Pagado el 11/11/2026, Entregado el 13/11/2026, 2 × Pañal adulto M x30».
- **Movimiento:** nada nuevo. Sin `animate-aparecer` en la etiqueta.

---

## 6. Criterios de revisión visual

Para quien «Se informa», salvo que se diga otro rol. Se revisa a 360, 1280 y 1920 px, con el tema claro y el oscuro, y a 320 px con el texto al 200 %.

1. En «Pedido», en borrador, total confirmado y vencido, **no aparece ningún «$»** en `main`. Tampoco aparecen «IVA», «Precio de ejemplo», «cada uno», «Subtotal», «Productos:», «total» como cifra, «te devolvemos» ni «observador».
2. No hay ningún `NaN` ni ningún renglón vacío donde estaba un monto.
3. No se ve el aviso «Precios de ejemplo.» del piloto (O3) ni el «Derecho a retracto» (O2). Cada línea sigue diciendo «(comercio ficticio)».
4. Cada línea muestra, en este orden, nombre, presentación (si es distinta), «De {comercio} (comercio ficticio)», la cantidad con su sufijo y «Si falta: …». Entre ellos, el mismo espacio.
5. Con la regla `quitar`, la línea dice «Si falta: lo sacamos del pedido.». Con `otro_comercio`, «Si falta: lo buscamos en otro comercio.».
6. Debajo de la bajada hay **una sola** `Etiqueta`, con ícono y palabra: «Sin confirmar», «Falta pagarlo» o «Hay que confirmarlo de nuevo», según el estado. Solo «Hay que confirmarlo de nuevo» va en `atenta`.
7. A 360 px, la etiqueta se ve sin desplazarse, en la primera pantalla.
8. El pie dice «Los precios y el total los ven quien administra el grupo, quien cuida a {pila} y quien paga.», y nada más. No dice «puede cambiar el pedido y ver el total».
9. No hay ningún botón macizo ni secundario en la vista. Ningún elemento en `pino` macizo.
10. En pantalla ancha, la columna derecha tiene solo la frase del pie. No hay entrega ni teléfono.
11. En la fila de «Tus pedidos», en la lista y en el bloque al final de «Pedido», la primera línea dice «Pagado el {DD/MM/AAAA}». Con O1, la etiqueta muestra el estado real, por ejemplo «En camino» o «Entregado el {fecha}», sin ninguna explicación debajo. Sin O1, dice «Pagado».
12. La fila de «Tus pedidos» no recibe el foco con Tab y no tiene ningún «$».
13. Con los roles admin, cuidador y pagador, «Pedido» y «Tus pedidos» se ven **igual que antes** de esta tarjeta, con precios, subtotales, «Productos:» y el aviso del piloto.
14. Sin desplazamiento horizontal a 320 px con el texto al 200 %: `scrollWidth` igual al ancho, en «Pedido» y en «Tus pedidos». La etiqueta más larga, «Hay que confirmarlo de nuevo», baja de renglón sin cortarse.
15. En el tema oscuro, la etiqueta `atenta` y el `text-tenue` del pie se leen con el contraste de DISENO.md.

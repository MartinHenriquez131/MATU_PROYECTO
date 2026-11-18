# MATU-116 · Quien pagó sigue viendo sus pagos · Especificación de diseño

**Versión 1.0 · 18/11/2026** · Agente 6, UI/UX. Especifica y no construye.

**Viene de:** las decisiones de Jorge del 18-11 (J1 a J7), las condiciones del analista para el frontend (C5, C10 y C11) y los textos T1 a T6, aprobados con J1 a J7.

**Es frontend y textos.** No hay tokens nuevos y `Demo/DISENO.md` no cambia. Todo lo que se usa ya existe: `bg-hoja`, `ring-linea`, `ring-borde`, `border-linea`, `divide-linea`, `text-tinta`, `text-tenue`, `cifras`, `titular`, los tonos `neutro`, `ok` y `atenta` de `Etiqueta`, `Boton` (`secundario` y `texto`), `Nota`, `EnlaceEnFrase`, y las piezas `Bloque`, `Vacio`, `SUPERFICIE` y `Cola` de «Tus datos».

**Se construye en:**
- `web/src/familia/AppFamilia.tsx`: la guarda de las rutas del detalle y de «Arrepentirme» (0, H1);
- `web/src/familia/TusPedidos.tsx`: `Lista` (la frase T1) y nada más en las filas ni en el detalle;
- `web/src/familia/TusDatos.tsx`: `Pago` y un bloque nuevo, «Lo que pediste devolver»;
- `web/src/familia/Miembros.tsx` o donde vivan «Salir del grupo» y «Cambiar tu rol» (T5 y T6);
- `textosTusPedidos.ts`, `textosMisDatos.ts` y `textosGrupo.ts`.

**Marcas:** **[T n]** es un texto aprobado de la revisión previa. **[L n]** ya está en `lenguaje.md`, sección n. **[NUEVO]** lo propongo yo, entra a `lenguaje.md` 35 o 38 y lo aprueba Jorge. **[AJUSTE]** es un texto aprobado con un cambio de forma, que también aprueba Jorge.

**En la interfaz nunca se dice** «observador», «retracto», «rechazado», «pagador», «membresía» ni «inactivo». El rol, cuando se nombra, es «Se informa» o «Paga» [L 34].

---

## 0. Lo que hay hoy (leído en el código de la rama, 18-11)

No levanté la pantalla para esta especificación: depende del contrato que el backend está haciendo en paralelo (C5, C2 a C4). La revisión visual (sección 6) se hace con la pantalla funcionando.

| # | Dónde | Qué pasa hoy | Qué implica |
|---|---|---|---|
| **H1** | `AppFamilia.tsx`, ~97 a 99 | Si `s.rol === 'observador'`, las rutas `/insumos/tus-pedidos/pedido` y `…/arrepentirme` llevan a la lista. **La pantalla decide por el rol** | Bloquea J1: aunque la fila se abra, el detalle no se ve. La guarda pasa a mirar solo que haya un `pedidoElegido` de la persona que se está viendo. Lo demás lo decide el servidor: si no pagó ese pedido, el seguimiento responde 404 y se ve «No encontramos este pedido.» (C5, C10). **P1 para el frontend** |
| H2 | Lista, filas | La lista ya pinta cada fila por su forma (`esFilaCompleta`): `FilaDelPedido` (un `button` que abre el detalle) o `FilaDelObservador` (un `li` que no se abre). La mezcla funciona sin cambios | Las filas no cambian (1.3) |
| **H3** | Detalle de «Paga» | **No tiene un bloque de entrega.** La dirección y el teléfono de entrega no se muestran en el detalle ni en el comprobante desde MATU-92 (4.7) y MATU-62 (7.5.1). Las notas del equipo tampoco llegan a la familia. Lo único de la entrega es «Entrega: {ventana}», en «Datos del pedido», que sale del comprobante y es la franja horaria, no la dirección | «Sin el bloque de entrega» no quita nada que se vea hoy: el detalle de quien pagó y está en «Se informa» es **el mismo** de «Paga». Lo informo al orquestador por si la intención de J1 era quitar también «Entrega: {ventana}». Mi propuesta es dejarla: no es un dato de `pedido_entrega` ni identifica a nadie, y es parte del comprobante que la persona ya recibió (D-116-1) |
| H4 | «Tus datos», `Pago`, ~433 | «{monto} en {grupo}». Si la API deja el grupo en blanco (C4), se lee «$37.260 en » | Hace falta T3 (2.2) |
| **H5** | «Tus datos» | **El contrato trae `retractos` (`RetractoCuentaCopia`, desde MATU-63) y ninguna pantalla los muestra.** La cuenta tiene derecho a ver lo que pidió devolver, y hoy solo lo ve en el archivo | Faltante. Esta especificación agrega el bloque (2.3). Lo informo al orquestador porque es anterior a esta tarjeta |
| H6 | Contrato, `PagoCuentaCopia.grupo` y `RetractoCuentaCopia.grupo` | Son `str`, no aceptan `null` | Para C4 pido `grupo: str \| None`, con `null` cuando ya no está en el grupo. La pantalla también trata `""` como `null`, por defensa. **No elijo yo:** lo informo al orquestador y al backend |

---

## 1. «Tus pedidos» para quien «Se informa» y pagó algunos pedidos

### 1.1 Objetivo

Rodrigo pagó dos pedidos de María y ahora «Se informa». Abre «Tus pedidos», reconoce los que pagó, entra a uno y puede arrepentirse de la compra, sin ver la dirección ni el teléfono de entrega.

### 1.2 Jerarquía de la lista

1. El título «Tus pedidos» y la bajada de siempre.
2. Las dos frases que explican qué ve: la de «Se informa» (si hay filas que no pagó) y T1 (si hay al menos una que pagó).
3. Las filas, del más reciente al más antiguo, mezcladas como las trae la API: las que pagó con su total y su estado, y las que no pagó con su fecha, su estado y sus productos.
4. «Ver más pedidos», si hay más.

**No hay acción principal** en la lista. Lo que se toca son las pestañas, las filas que pagó y «Ver más pedidos» (`secundario`).

### 1.3 Cómo se distinguen las dos filas, sin el color

Las dos filas usan la misma superficie (`rounded-xl bg-hoja ring-1 ring-linea`) y **no se les agrega ningún color, marca ni ícono**. Se distinguen por la palabra y por la forma, que ya tienen:

| | Fila que pagó (`FilaDelPedido`, sin cambios) | Fila que no pagó (`FilaDelObservador`, sin cambios) |
|---|---|---|
| **Primera línea** (lo que se lee primero) | «Pedido 4821 · 11/11/2026», con el número | «Pagado el 11/11/2026», sin número |
| **Monto** | «Total pagado: $37.260», a la derecha en pantalla ancha | Ninguno |
| **Estado** | `EtiquetaEstado` con su explicación | La misma etiqueta, sin explicación |
| **Productos** | Un resumen en una línea: «Pañal adulto M x30 y 1 producto más» | La lista con viñetas, con la cantidad |
| **Forma** | `button` del ancho de la lista, `min-h-12`, recibe el foco con su anillo, y `hover:ring-borde` | `li` que no recibe el foco ni cambia al pasar el puntero |
| **Lector** | «botón, Pedido 4821, 11/11/2026, …, Total pagado: $37.260» | «Pagado el 11/11/2026, En camino, 2 × Pañal adulto M x30» |

T1 dice con palabras que de los que pagó «ves el detalle». La palabra «Pedido» con su número y el «Total pagado» son lo que solo tienen esas filas.

**D-116-2 · Sin una marca «Lo pagaste» en la fila.** La pensé y la descarto: la pantalla tendría que deducir del rol en memoria que la fila es suya, y si el rol cambió mientras miraba (por ejemplo, volvió a «Paga»), diría que pagó un pedido que pagó otra persona. Una frase sobre dinero sale de un dato del servidor o no va (C10). Si Jorge la quiere, se pide al backend un campo en la fila y se agrega en una tarjeta propia.

### 1.4 Dónde va T1

Debajo de la bajada, en el mismo `div max-w-3xl` del encabezado, como la frase de «Se informa»:

| Frase | Cuándo | Componente |
|---|---|---|
| Bajada | Siempre | `p mt-1.5 max-w-prose text-base text-tenue`, sin cambios |
| «Quien administra el grupo, quien cuida a {pila} y quien paga ven el detalle.» | Con `carga === 'listo'` y al menos una fila que no pagó (`!esFilaCompleta`). Sin cambios | `p mt-1.5 max-w-prose text-base text-tenue` |
| **T1** «De los pedidos que pagaste, ves el detalle y puedes arrepentirte de la compra.» | Con `carga === 'listo'`, `rol === 'observador'` y **al menos una fila que pagó** (`esFilaCompleta`) entre las cargadas | El mismo `p mt-1.5 max-w-prose text-base text-tenue`, **después** de la frase de «Se informa» |

- **El orden se lee de corrido:** «… y quien paga ven el detalle. De los pedidos que pagaste, ves el detalle y puedes arrepentirte de la compra.»
- **Por qué aquí sí se mira el rol:** T1 es solo un texto y no muestra ningún dato. La forma de la fila no distingue a quien «Se informa» y pagó de quien «Paga», y T1 no debe salirle a «Paga». Es el mismo criterio de MATU-113 2.7: la regla de no decidir por el rol protege la lectura de dinero, y aquí no se lee dinero. Si el backend agrega a la lista un dato que lo diga, se usa ese dato y no el rol.
- **Si la fila que pagó llega con «Ver más pedidos»,** T1 aparece en ese momento, sin anuncio y sin mover el foco.
- **Solo filas que pagó** (todas `FilaDelPedido`): no se ve la frase de «Se informa», solo T1.

### 1.5 Esquema de la lista a 360 px

```
│ Catálogo · Lista · Pedido · Tus pedidos │  PestanasInsumos, sin cambios
│                                         │
│ Tus pedidos                             │  h1 Titulo text-3xl
│ Los pedidos pagados de María, de los    │  p text-base text-tenue max-w-prose
│ últimos 2 años.                         │
│ Quien administra el grupo, quien cuida  │  p text-base text-tenue (si hay filas que no pagó)
│ a María y quien paga ven el detalle.    │
│ De los pedidos que pagaste, ves el      │  p text-base text-tenue (T1)
│ detalle y puedes arrepentirte de la     │
│ compra.                                 │
│                                         │
│ ┌─────────────────────────────────────┐ │  li > button, FilaDelPedido
│ │ Pedido 4821 · 11/11/2026            │ │  text-lg font-bold, cifras
│ │ [🚚 En camino]                      │ │  EtiquetaEstado
│ │ Pañal adulto M x30 y 1 producto más │ │  text-base
│ │ Total pagado: $37.260               │ │  text-base, cifras font-bold
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │  li, FilaDelObservador
│ │ Pagado el 04/11/2026                │ │  text-lg font-bold
│ │ [✓ Entregado el 06/11/2026]         │ │  Etiqueta, sin explicación
│ │ • 2 × Pañal adulto M x30            │ │  ul list-disc ps-5 text-base
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │  li > button, FilaDelPedido
│ │ Pedido 4790 · 28/10/2026            │ │
│ │ [✓ Entregado el 30/10/2026]         │ │
│ │ Suplemento vainilla x12             │ │
│ │ Total pagado: $21.900               │ │
│ └─────────────────────────────────────┘ │
│ [ Ver más pedidos ]                     │  Boton secundario, si hay cursor
```

### 1.6 Esquema de la lista en pantalla ancha (1280 y 1920 px)

```
│ Catálogo · Lista · Pedido · Tus pedidos                                          │
│ Tus pedidos                                         h1 @2xl/main:text-5xl        │
│ Los pedidos pagados de María, de los últimos 2 años.                             │
│ Quien administra el grupo, quien cuida a María y quien paga ven el detalle.      │
│ De los pedidos que pagaste, ves el detalle y puedes arrepentirte de la compra.   │
│                                                                                  │
│ ┌──────────────────────────────────────────────────────────────┐                 │  max-w-3xl
│ │ Pedido 4821 · 11/11/2026                Total pagado: $37.260│                 │  @2xl/main: total a la derecha
│ │ [🚚 En camino]                                               │                 │
│ │ Pañal adulto M x30 y 1 producto más                          │                 │
│ └──────────────────────────────────────────────────────────────┘                 │
│ ┌──────────────────────────────────────────────────────────────┐                 │
│ │ Pagado el 04/11/2026                                         │                 │  una columna, nada a la derecha
│ │ [✓ Entregado el 06/11/2026]                                  │                 │
│ │ • 2 × Pañal adulto M x30                                     │                 │
│ └──────────────────────────────────────────────────────────────┘                 │
```

- Las dos frases y la lista quedan dentro del `max-w-3xl` de hoy. Las frases, en `max-w-prose`: a 1920 px no se estiran.
- **El lado derecho vacío de la fila que no pagó es la diferencia de forma más visible** en pantalla ancha: ahí va el total en la que pagó.

### 1.7 Estados de la lista

| Estado | Qué ve | Texto | Origen |
|---|---|---|---|
| **Cargando** | Sin cambios. Sin T1 ni la frase de «Se informa» hasta que carga | Cargando… | [L 26] |
| **Error al traer** | Sin cambios: `UnaColumna` con `CloudOff` y «Volver a intentar», el único macizo | No pudimos traer tus pedidos. Revisa tu conexión y vuelve a intentarlo. | [L 38] |
| **Vacío** | Sin cambios: la frase en `text-xl font-bold`, sin botón (este rol no edita el pedido) y sin T1 | Todavía no hay pedidos pagados para {pila}. | [L 38] |
| **Sin pedidos pagados por esta cuenta** | Igual que MATU-113: solo filas `FilaDelObservador`, la frase de «Se informa» y **sin T1** | Los de MATU-113 3 | [L 38] |
| **Con pedidos que pagó** | 1.5 y 1.6 | T1 | [T1] |
| **Solo pedidos que pagó** | Solo `FilaDelPedido`, solo T1 | T1 | [T1] |
| **Capa 3 apagada** | Sin cambios | Tus pedidos no están disponibles por ahora. | [L 38] |
| **Error en «Ver más»** | Sin cambios | El de MATU-92 | [L 38] |
| **Al día** (cada 60 s si alguno está en `pagado`, y al volver a la pestaña) | Sin cambios. Si una fila cambia de forma (por ejemplo, la API deja de darla como pagada), se reemplaza en su lugar, sin anuncio y sin mover el foco. Si el foco estaba en esa fila y la fila deja de ser un `button`, el foco pasa al `h1` (`titulo-pagina`) | — | — |

### 1.8 El bloque «Tus pedidos» al final de «Pedido»

Sin cambios. Muestra la fila más reciente con la forma que trae: si la pagó, es un `button` que abre el detalle. **T1 no va en el bloque**: es la frase de la lista.

### 1.9 El detalle de un pedido que pagó

**Objetivo:** Rodrigo ve cómo va el pedido que pagó, su comprobante y, si ya llegó, puede arrepentirse de la compra.

**Es el detalle de «Paga» de MATU-92, sin cambios en el componente (T2).** La pantalla pinta lo que trae la API (C10): si `puede_cancelar` llega en `false`, no hay botón de cancelar, y si `puede_arrepentirse` llega en `true`, está «Arrepentirme de la compra».

Jerarquía:
1. «Volver a tus pedidos», el `h1` «Pedido {referencia}», «Pagado el {fecha} a las {hora}» y la etiqueta del estado con su explicación.
2. «Cómo va»: las partes por comercio.
3. «Dinero devuelto» y «Productos para devolver», si hay.
4. «Arrepentirme de la compra», con el plazo y el botón `secundario`, si `puede_arrepentirse`.
5. «Cancelar el pedido» con la frase del rol y **sin botón** (4.6.2 de MATU-92, motivo `rol`).
6. El comprobante, «Datos del pedido», «Lo que te garantizamos» e «Imprimir o guardar en PDF».

**No aparece:** la dirección de entrega, el teléfono de contacto, las notas del equipo (ninguno se muestra hoy, H3), ni el `Boton variante="peligro"` «Cancelar el pedido».

**La tarjeta:** como pagó, el comprobante muestra «Tarjeta de crédito terminada en {últimos 4}». Nunca «Lo pagó otra persona de tu grupo.» en un pedido que pagó, porque lo dice el comprobante que trae la API.

**«Cancelar el pedido» sin botón.** Con `puede_cancelar: false` y `cancelar_motivo: 'rol'`, se ve el `h2` y la frase «Solo quien administra el grupo puede cancelar un pedido pagado, mientras el comercio no empiece a prepararlo.» [L 38], como le pasa a «Paga». Es la misma frase de «Lo que te garantizamos» y explica por qué no puede. Con `ya_se_prepara` o `cancelado`, nada, como hoy.

#### Esquema del detalle a 360 px

```
│ Catálogo · Lista · Pedido · Tus pedidos │
│ ‹ Volver a tus pedidos                  │  Volver
│ Pedido 4790                             │  h1 Titulo, cifras
│ Pagado el 28/10/2026 a las 11:24        │  p text-base text-tenue
│ [✓ Entregado el 30/10/2026]             │  EtiquetaEstado
│                                         │
│ Cómo va                                 │  h2 titular text-2xl
│ ┌─────────────────────────────────────┐ │  li bg-hoja ring-1 ring-linea
│ │ De Farmacia Los Aromos (comercio    │ │
│ │ ficticio)                           │ │
│ │ [▣ Retirado]                        │ │
│ │ 1 × Suplemento vainilla x12         │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ Arrepentirme de la compra               │  h2 titular text-2xl
│ Puedes hacerlo hasta el 13/11/2026.     │  p text-base max-w-prose
│ Pasamos a buscar los productos sin      │
│ costo y te devolvemos su precio a la    │
│ misma tarjeta cuando los recibimos con  │
│ su sello cerrado.                       │
│ [ Arrepentirme de la compra ]           │  Boton secundario
│                                         │
│ Cancelar el pedido                      │  h2 (solo si el motivo es rol)
│ Solo quien administra el grupo puede    │  p text-base, sin botón
│ cancelar un pedido pagado, mientras el  │
│ comercio no empiece a prepararlo.       │
│                                         │
│ ┌ Comprobante ────────────────────────┐ │  ComprobanteBoleta, sin cambios
│ │ … Total pagado            $21.900   │ │
│ │ Tarjeta de crédito terminada en 4242│ │
│ └─────────────────────────────────────┘ │
│ Datos del pedido                        │  Vende · Entrega: {ventana} · Condiciones
│ Lo que te garantizamos                  │
│ [ Imprimir o guardar en PDF ]           │  Boton secundario
```

#### Esquema del detalle en pantalla ancha

Igual que el de «Paga» (MATU-92 4.8): la rejilla `3fr / 2fr`, a la izquierda «Cómo va», lo devuelto, «Arrepentirme de la compra» y «Cancelar el pedido», y a la derecha el comprobante `sticky`. **No queda un hueco** donde estaría el botón de cancelar: la sección termina en su frase.

#### Estados del detalle y de «Arrepentirme»

| Estado | Qué ve | Texto | Origen |
|---|---|---|---|
| **Cargando** | Sin cambios: el encabezado corto con el `h1` y «Cargando…» | Cargando… | [L 26] |
| **Error al traer** | Sin cambios | No pudimos traer tu pedido. Revisa tu conexión e inténtalo de nuevo. | [L 31] |
| **404** (no pagó ese pedido, salió del grupo, o el pedido ya no está) | Sin cambios: `SearchX`, la frase y «Volver a tus pedidos» `secundario` | No encontramos este pedido. · Volver a tus pedidos | [L 31] · [L 38] |
| **El comprobante no llega** | Sin cambios | No pudimos traer el comprobante. Revisa tu conexión y vuelve a intentarlo. | [L 38] |
| **Arrepentirme** | La pantalla 5 de MATU-92, sin cambios. Al terminar, la nota «Recibimos tu pedido de devolución. Te escribimos para coordinar el retiro.» recibe el foco | Los de L 36 y L 38 | [L 36] |
| **Arrepentirme, 404** (dejó de ser quien pagó o salió mientras elegía) | Sin cambios: «No encontramos este pedido.» | — | [L 31] |
| **Conflicto (412)** | No aplica: el detalle no edita nada con `ETag` | — | — |
| **Al recargar** | Sin cambios: el pedido elegido vive en memoria, y al recargar se ve la lista sin aviso (MATU-92 2.1). Con H1 corregido, esto vale para todos los roles igual | — | — |

### 1.10 Foco y anuncio

- **En la lista:** nada nuevo. Las filas que pagó reciben el foco con Tab, con el anillo de siempre (2 px, `turquesa`, 3:1). Las que no pagó no lo reciben. T1 no es una región viva y no se anuncia al cargar.
- **Al abrir el detalle,** el foco va al `h1`, como hoy. **Al volver,** a la fila de ese pedido, como hoy.
- **Ninguna frase nueva se anuncia.** Lo único que se anuncia sigue siendo lo de MATU-92: los errores (`alert`) y la nota de «Hecho» (`status`, con foco).

---

## 2. «Tus datos»: «Tus pagos» y lo que pediste devolver

### 2.1 Objetivo

Rodrigo salió del grupo de María. En «Tus datos» ve todo lo que pagó y lo que pidió devolver, aunque ya no pueda leer el nombre del grupo, y sabe a quién pedir lo que falta.

### 2.2 «Tus pagos» de un grupo del que salió (T3)

Solo cambia la línea del monto. El resto es MATU-54 5.4, sin cambios.

| `grupo` | Línea del monto | Texto | Origen |
|---|---|---|---|
| Con nombre | Sin cambios | {monto} en {grupo} | [L 35] |
| `null` o `""` | La misma `p text-base break-words` | {monto} en un grupo del que saliste | **[AJUSTE]** de T3 |

- **Por qué [AJUSTE]:** T3 es «Un grupo del que saliste», con mayúscula, porque en «Tus grupos» va solo, en el lugar del título. Aquí va después de «en», así que empieza en minúscula. Son las mismas palabras. En el código va como una pieza propia (`enGrupoQueDejaste: ' en un grupo del que saliste'`), no como `toLowerCase()` del texto de «Tus grupos».
- **Sin pedido** (el pago se guarda 6 años y el pedido 2, C2): `referencia: null` y el título dice «Pago del {fecha}» [L 35], que ya está construido. Un pago sin pedido y de un grupo del que salió dice las dos cosas: «Pago del 08/11/2024» y «$37.260 en un grupo del que saliste».
- **La nota de la sección 35 (T3):** la nota de L 1625 suma «Tus pagos» y «Lo que pediste devolver»: «**«Un grupo del que saliste»** va en el lugar del nombre del grupo, en «Tus grupos», en «Tus pagos» y en «Lo que pediste devolver», porque la cuenta ya no lo puede leer…». Esto lo hace el orquestador en `lenguaje.md`.

Esquema a 360 px, un pago de un grupo del que salió y sin pedido:

```
│ Tus pagos                          │  h2 (Bloque)
│ ┌────────────────────────────────┐ │  ul SUPERFICIE
│ │ Pago del 08/11/2024            │ │  h3 text-lg font-bold, la fecha en cifras
│ │ 08/11/2024 a las 11:24         │ │  text-base text-tenue
│ │ $37.260 en un grupo del que    │ │  text-base, monto en cifras
│ │ saliste                        │ │
│ │ Tarjeta de crédito terminada en│ │
│ │ 4242 · 3 cuotas                │ │
│ │ Código de autorización: 1213   │ │
│ └────────────────────────────────┘ │
```

### 2.3 El bloque nuevo «Lo que pediste devolver» (H5, C3 y C11)

Va **después de «Tus pagos» y antes de «Condiciones de compra que aceptaste»**, y solo si `retractos` trae al menos uno. Con `retractos: null` (la capa 3 quitada) o vacío, el bloque no existe y tampoco su entrada en el índice, igual que «Tus pagos».

Es un `Bloque id="lo-que-pediste-devolver"` con una `ul SUPERFICIE` y una `li flex min-w-0 flex-col gap-1 py-4` por cada uno, como «Tus pagos».

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Título del bloque y del índice | `Bloque`, `h2` | Lo que pediste devolver | **[NUEVO]** |
| Título de cada uno | `h3 text-lg font-bold break-words`, la referencia en `cifras` | Pedido {referencia} · sin referencia: Devolución del {fecha de `solicitado_en`} | [L 38] · **[NUEVO]**, como «Pago del {fecha}» |
| Estado | `Etiqueta` con ícono `lucide-react` y palabra, `self-start` | `solicitado`: Devolución pedida (`neutro`, `Clock`) · `devuelto`: Devuelto el {fecha de `resuelto_en`} (`ok`, `CircleCheck`) · `rechazado`: No se aceptó la devolución (`neutro`, `CircleX`) | [L 38] |
| Cuándo lo pidió | `p text-base text-tenue` | Lo pediste el {fecha}. | **[NUEVO]** |
| Cuándo se respondió, solo `rechazado` | `p text-base text-tenue` | Respondimos el {fecha}. | **[NUEVO]**. En `devuelto` la fecha ya está en la etiqueta |
| El grupo | `p text-base break-words` | En {grupo}. · sin el grupo: En un grupo del que saliste. | **[NUEVO]**, como «En {grupo}, para el pedido…» [L 35] · **[AJUSTE]** de T3 |
| Productos, si sigue en el grupo | `ul list-disc ps-5 text-base marker:text-tenue`, un `li break-words` por producto | {producto} | — |
| **Productos, si salió del grupo** (T4) | `p max-w-prose text-base`, en lugar de la lista, con el correo en `EnlaceEnFrase` (`mailto:`, `[overflow-wrap:anywhere]`) | Los productos los puedes pedir a {correo}. | [T4] |
| Por qué no se aceptó, solo `rechazado` con `motivo_rechazo` | `p max-w-prose text-base` | El producto volvió con el sello abierto. · No recibimos el producto de vuelta. | [L 38] (`MOTIVO_RECHAZO_FAMILIA`) |

- **Cuándo va T4:** cuando `grupo` es `null` o `""`. No se deduce de una lista de productos vacía: el contrato dice si sigue en el grupo por el nombre (C4), y con eso basta. Si sigue en el grupo y la lista llegara vacía, no se muestra nada en su lugar.
- **«{correo}»** es `CORREO_CONTACTO`, el mismo de T5 y de la política.
- **Sin montos.** `RetractoCuentaCopia` no trae lo que se devolvió: eso está en «Tus pagos», en «Devuelto: {monto}».
- **Nunca** el nombre de la persona cuidada (P5 de MATU-54), «retracto» ni «rechazado».

Esquema a 360 px, uno de cada:

```
│ Lo que pediste devolver            │  h2 (Bloque)
│ ┌────────────────────────────────┐ │  ul SUPERFICIE
│ │ Pedido 4790                    │ │  h3 text-lg font-bold
│ │ [✓ Devuelto el 15/11/2026]     │ │  Etiqueta ok
│ │ Lo pediste el 12/11/2026.      │ │  text-base text-tenue
│ │ En Familia Soto.               │ │  text-base
│ │ • Suplemento vainilla x12      │ │  ul list-disc
│ │ ────────────────────────────── │ │  divide-linea
│ │ Pedido 4655                    │ │
│ │ [⊗ No se aceptó la devolución] │ │  Etiqueta neutro
│ │ Lo pediste el 02/10/2026.      │ │
│ │ Respondimos el 06/10/2026.     │ │
│ │ En un grupo del que saliste.   │ │
│ │ Los productos los puedes pedir │ │  T4, el correo es un enlace
│ │ a cuidaconmatu@gmail.com.      │ │
│ │ El producto volvió con el sello│ │  motivo
│ │ abierto.                       │ │
│ └────────────────────────────────┘ │
```

**Pantalla ancha:** la grilla del índice de MATU-54 3.3, sin cambios: el índice a la izquierda (`--container-xs`) y los bloques a la derecha. La `li` es una sola columna; la etiqueta y las frases no se estiran (`max-w-prose`).

### 2.4 Estados de «Tus datos»

| Estado | Qué ve | Origen |
|---|---|---|
| Cargando, error, límite de 10 por hora | Sin cambios (MATU-54 y MATU-107) | [L 35] |
| Sin pagos | Sin «Tus pagos» ni su entrada en el índice, como hoy | [L 35] |
| Sin nada que pidió devolver | Sin el bloque nuevo ni su entrada en el índice | — |
| Capa 3 quitada (`pagos`, `condiciones_aceptadas` y `retractos` en `null`) | Ninguno de los tres bloques | [L 35] |
| Todo de grupos de los que salió | «Tus grupos» con «No estás en ningún grupo.» arriba, y los pagos y lo que pidió devolver con T3 y T4 | [L 35] · [T3] · [T4] |

### 2.5 Foco y anuncio

- El índice suma «Lo que pediste devolver» y, al elegirlo, el foco va a su `h2` (`tabIndex={-1}`), como los demás bloques.
- El enlace del correo de T4 tiene el anillo de foco de `EnlaceEnFrase`. Va dentro de una frase, así que no necesita 48 px de alto (WCAG 2.5.8, excepción de los enlaces en línea), igual que el correo de «Productos para devolver».
- Nada se anuncia: es una copia que se lee.

---

## 3. Los textos de «Salir del grupo» y «Cambiar tu rol» (T5 y T6)

No cambian la composición. Van donde ya están sus vecinos en `lenguaje.md` 34:

| # | Dónde | Cuándo | Texto | Origen |
|---|---|---|---|---|
| T5 | «Salir del grupo», en la sección y en la pregunta, donde hoy va L 1409 | Con la capa 3. Sin la capa 3, sigue la frase de L 1410 | Tus pagos los seguirás viendo en Tus datos. Si después necesitas lo que hiciste en el grupo o el detalle de un pedido, pídelo a {correo}. | [T5] |
| T6 | «Cambiar tu rol», después de «También dejarás de ver la ficha.» [L 1379] | Solo al cambiar **tu propio** rol a «Se informa», y con la capa 3. Al pasar a «Paga» no va, porque «Paga» ve todo | Los pedidos que pagaste los seguirás viendo, con lo que pagaste. | [T6] |

- T5 y T6 van en `p text-base`, como la frase a la que acompañan, y el correo de T5 en `EnlaceEnFrase`.
- **T6 no depende de si pagó algo:** es una frase sobre lo que pasará, y la pantalla no sabe si pagó (C10).

---

## 4. Textos

### 4.1 Los que hay que aprobar

| # | Dónde | Texto | Va a |
|---|---|---|---|
| N1 | «Tus pagos», monto de un grupo del que salió | {monto} en un grupo del que saliste | L 35 (**[AJUSTE]** de T3) |
| N2 | Título del bloque y del índice | Lo que pediste devolver | L 35, «Los bloques» |
| N3 | Título sin referencia | Devolución del {fecha} | L 35 |
| N4 | Cuándo lo pidió | Lo pediste el {fecha}. | L 35 |
| N5 | Cuándo se respondió, sin aceptar | Respondimos el {fecha}. | L 35 |
| N6 | El grupo | En {grupo}. · En un grupo del que saliste. | L 35 (**[AJUSTE]** de T3 en la segunda) |

### 4.2 Los aprobados que se usan

- T1, bajo la bajada de «Tus pedidos». [T1]
- T2: el detalle y la fila de «Paga», sin cambios. [T2] y [L 38]
- T3: «Un grupo del que saliste», con N1 y N6 para cuando va dentro de una frase. [T3]
- T4: «Los productos los puedes pedir a {correo}.» [T4]
- T5 y T6, en la sección 3. [T5] [T6]
- De L 38: «Pedido {referencia}», «Total pagado:», «Pagado el», «Quien administra el grupo, quien cuida a {pila} y quien paga ven el detalle.», «No encontramos este pedido.», «Volver a tus pedidos», «Arrepentirme de la compra» y su plazo [L 36], «Solo quien administra el grupo puede cancelar un pedido pagado, mientras el comercio no empiece a prepararlo.», «Devolución pedida», «Devuelto el {fecha}», «No se aceptó la devolución» y los dos motivos.
- De L 35: «Pago {referencia}», «Pago del {fecha}», «{monto} en {grupo}», «Devuelto: {monto}», «Código de autorización: {código}».

### 4.3 Lo que cambia en `lenguaje.md`, para el orquestador

- **35, «Los bloques» de «Tus datos»** (L 1581): suma «Lo que pediste devolver», después de «Tus pagos».
- **35, una fila nueva «Lo que pediste devolver»** con N2 a N6, T4 y las etiquetas de L 38.
- **35, «Tus pagos»:** suma N1.
- **35, la nota de L 1625:** la de 2.2.
- **38, la regla de la sección:** «Quien «Se informa» ve por pedido la fecha del pago…» suma «salvo en los pedidos que pagó, que ve como quien paga, sin la entrega (MATU-116)». Y la fila de T1.
- **34:** T5 en lugar de L 1409, y T6 después de L 1379.

---

## 5. Accesibilidad

- **El estado nunca solo por color:** las dos filas se distinguen por la primera línea, el total y la forma (1.3). Cada `Etiqueta` lleva su palabra, y en `angosto` (320 px) queda solo la palabra.
- **Contraste:** `text-tenue` sobre `bg-hoja` y sobre el fondo, y las etiquetas `neutro` y `ok`, ya están medidos en DISENO.md con al menos 4,5:1 en los dos temas. No hay combinaciones nuevas.
- **Áreas táctiles:** las filas que pagó, «Arrepentirme de la compra», «Volver a tus pedidos» y «Ver más pedidos» ya tienen 48 px. Las filas que no pagó no se tocan.
- **Una sola acción principal:** en la lista y en el detalle, ningún macizo salvo «Volver a intentar» en el error. En el detalle, «Arrepentirme de la compra» es `secundario`, como en «Paga».
- **Lector:** el orden del DOM es el de los esquemas. T1 va después de la frase de «Se informa». En «Tus datos», cada `li` se lee «Pedido 4655, No se aceptó la devolución, Lo pediste el 02/10/2026, …».
- **Movimiento:** nada nuevo.

---

## 6. Criterios de revisión visual

Con una cuenta sintética en «Se informa» que pagó algunos pedidos (Rodrigo), salvo que se diga otro rol. Se revisa a 360, 1280 y 1920 px, con el tema claro y el oscuro, y a 320 px con el texto al 200 %.

**«Tus pedidos»**
1. La lista mezcla filas que empiezan con «Pedido {número} · {fecha}» y tienen «Total pagado:», con filas que empiezan con «Pagado el {fecha}» y no tienen ningún «$». Ninguna fila tiene un color, un ícono o una marca que no tenga la otra, fuera de la etiqueta del estado.
2. Con Tab, el foco entra solo a las filas que pagó, con el anillo visible. Las que no pagó no reciben el foco.
3. Debajo de la bajada hay dos frases en `text-tenue`, en este orden: «Quien administra el grupo, quien cuida a María y quien paga ven el detalle.» y «De los pedidos que pagaste, ves el detalle y puedes arrepentirte de la compra.».
4. Con una cuenta en «Se informa» que no pagó ninguno, la lista es la de MATU-113 y **no** aparece T1.
5. Con «Paga» y con quien administra, la lista se ve igual que antes de esta tarjeta y **no** aparece T1.
6. Al tocar una fila que pagó, se abre el detalle (H1 corregido). No vuelve a la lista.
7. El detalle es el de «Paga»: el estado con su explicación, «Cómo va», el comprobante con «Tarjeta de … terminada en {4 dígitos}», «Datos del pedido», «Lo que te garantizamos» e «Imprimir o guardar en PDF». En `main` no aparecen una dirección de entrega, un teléfono de contacto ni notas del equipo.
8. En el detalle no hay ningún botón «Cancelar el pedido» (`peligro`). Si se ve la sección, solo tiene su frase.
9. En un pedido entregado y dentro del plazo, «Arrepentirme de la compra» es un `secundario` y lleva a la pantalla de elegir. Al enviar, la nota de «Hecho» recibe el foco.
10. Si se abre por la consola de desarrollo un pedido que no pagó, el detalle dice «No encontramos este pedido.» y no muestra ningún dato del pedido.

**«Tus datos»**
11. Un pago de un grupo del que salió dice «{monto} en un grupo del que saliste», en minúscula, y nunca «en » solo.
12. Un pago sin pedido dice «Pago del {fecha}» en el título.
13. «Lo que pediste devolver» está después de «Tus pagos», y su entrada está en el índice en el mismo orden. Sin datos, no aparece ni en el índice.
14. Un retracto de un grupo del que salió no tiene productos y dice «Los productos los puedes pedir a {correo}.», con el correo como enlace. Uno de un grupo activo lista sus productos y no dice T4.
15. Ninguna línea dice «retracto», «rechazado», el nombre de María ni el de otro grupo del que salió.

**Siempre**
16. Sin desplazamiento horizontal a 320 px con el texto al 200 %: `scrollWidth` igual al ancho en «Tus pedidos», en el detalle y en «Tus datos». T1, T4 y «No se aceptó la devolución» bajan de renglón sin cortarse, y el correo de T4 se parte si hace falta.
17. En el tema oscuro, las frases en `text-tenue`, las etiquetas y el enlace de T4 se leen con el contraste de DISENO.md.
18. En el proyector (tema claro, 1920 px), T1 y las líneas de «Lo que pediste devolver» van en `text-base` (17 px) o más.

# MATU-92 · Tus pedidos: la lista, el detalle, arrepentirse y cancelar después de pagar · Especificación de diseño

**Versión 1.2 · 17/11/2026** · agente 6 (UI/UX) · para el frontend
**Cambios de la 1.2** (después de la revisión visual del 17-11):
- 5.5, 5.7 y 5.8: «ya se pidió» llega como **422 `producto-no-retractable`** (decisión 445 del contrato), no como 409. El plazo vencido llega como 409 `fuera-de-plazo`;
- 4.3: «De un comercio» cuando la parte no trae el nombre del comercio;
- 6.3: «No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo.», sin «Todo sigue como estaba.», cuando tampoco se pudo volver a leer el pedido;
- 4.9 y 9: la falla del comprobante lleva «Volver a intentar».

**Cambios de la 1.1:** se aplican las decisiones del orquestador sobre las contradicciones de la 1.0 (16-11, 00:30), D1 a D8:
- O1, O2 y O4 pasan a resueltos (sección 0);
- «10 días hábiles» también en el carrito y en el resumen (4.7, 9 y 10);
- se aceptan los [AJUSTE] del cancelado en curso y de «por correo»;
- el faltante de quien pagó usa [L 36];
- `matu-62-pago.md` §8 queda reemplazado por 2.3 y ya está actualizado (v1.2).

La sección 10 ahora registra lo que se decidió.
**Historia:** MATU-92. La familia ve los pedidos pagados de cada persona cuidada, cómo va cada uno, lo que se le devolvió y su comprobante. Desde ahí se arrepiente de la compra (R3) o cancela un pedido pagado que el comercio todavía no empieza a preparar (R15). Capa 3: si se quita, estas pantallas desaparecen y las capas 1 y 2 no cambian.
**Dónde se construye:** `web/`, en la app de la familia, con React 19, TypeScript y Tailwind CSS v4, mobile first.

**Fuentes, en este orden:**
- `Demo/DISENO.md` y los tokens de `web/src/index.css`.
- La revisión previa del analista y las decisiones del orquestador del 16-11: D-92-1 a D-92-4, las condiciones C1 a C28 y los textos de la sección 38 nueva de `lenguaje.md`.
- `lenguaje.md`, secciones 3, 8, 11, 26, 27, 31, 32 y 36.
- D-63-5: la familia nunca ve el código de retiro.
- `matu-61-pedido.md` v1.3: el diálogo de cancelar (10), los errores (11) y la línea (7.4).
- `matu-62-pago.md` v1.1: el comprobante (7.4 y 7.5), las devoluciones (7.7) y el bloque «Pedido pagado» (8), que esta historia reemplaza.
- `matu-63-comercio.md` v1.2: la fila de lista (5.3) y los estados con ícono y palabra (5.4).
- El código de `web/src/familia/`: `ruteo.ts`, `Shell.tsx`, `Insumos.tsx` (`PestanasInsumos`), `Pago.tsx`, `PiezasPedido.tsx`, `DialogoConfirmar.tsx` y `ui.tsx`.

**Cómo se lee:** los textos entre comillas latinas «» van tal cual en pantalla. Marcas de origen:
- **[L 38]**: texto de la sección 38 nueva, tal como la trae la revisión previa, que Jorge aprueba con esta historia;
- **[L 31]**, **[L 32]**, **[L 36]**: texto ya escrito en esa sección de `lenguaje.md`;
- **[AJUSTE]**: un texto de [L nn] que cambio, con el porqué;
- **[NUEVO]**: un texto mío, que Jorge aprueba antes de construir.

**Las llaves** son datos de la API, con el formato de `lenguaje.md` 31 y 32:
- `{referencia}`: el número corto del pedido;
- `{pila}`: el nombre de pila de la persona cuidada;
- `{producto}`: el `nombre` del producto;
- `{comercio}`: el `nombre_fantasia` del comercio;
- `{total}`, `{monto}` y `{precio}`: pesos enteros con punto de miles, como `$57.460`;
- `{DD/MM/AAAA}` y `{HH:MM}`: hora de Chile, 24 horas;
- `{correo}`: el canal de reclamo de las condiciones, cuidaconmatu@gmail.com;
- `{ultimos4}`: las cuatro últimas cifras de la tarjeta, solo para quien pagó (C17).

**Tokens:** **ningún token nuevo**, ningún color nuevo y ninguna regla nueva en la capa base. Todo sale de componentes que ya existen:
- de `ui.tsx` y de `compartido/ui/`: `Boton`, `Nota`, `Etiqueta`, `Stepper`, `MensajeError`, `Pestanas`, `Volver`, `Acciones`, `Anunciado`, `EnlaceEnFrase` y `Cuando`;
- de `PiezasPedido.tsx` y `Pago.tsx`: `UnaColumna`, `AvisoPiloto`, `DialogoConfirmar` y el comprobante de MATU-62.

El frontend arma dos piezas con tokens existentes: **la fila del pedido** (3.3), con el patrón de la fila de la cola del comercio, y **el resumen de la devolución** (5.4), con el contenedor de la boleta.

---

## 0. Puntos abiertos

Ninguno impide empezar: cada uno trae una propuesta, y la pantalla se construye con ella hasta que se decida otra cosa. El orquestador los lleva al backend o a Jorge.

**Resueltos en la v1.1** (decisiones del orquestador del 16-11, 00:30):
- **O1, resuelto (D6):** el contrato trae `cancelar_motivo` y `arrepentirse_motivo`, como se propone abajo. Ya se le pidió al backend.
- **O2, resuelto (D7):** la suma del frontend es solo una vista previa. El monto que manda es el del `POST`.
- **O4, resuelto (D5):** el título es «Dinero devuelto».

Siguen abiertos O3, O5 y O6.

| # | Qué | Para quién | Propuesta |
|---|---|---|---|
| O1 (resuelto) | **Por qué no se puede.** C7 dice que la pantalla no deduce `puede_cancelar` ni `puede_arrepentirse`. Pero el texto cambia según la razón: el rol, que todavía no se entrega, que venció el plazo de la app, que pasaron los 90 días o que ya se pidió devolver todo. Con un booleano, la pantalla tendría que deducir la razón | Backend | Junto a cada booleano, el motivo, que lo calcula el servidor. `cancelar_motivo`: `rol` · `ya_se_prepara` · `cancelado` · `null`. `arrepentirse_motivo`: `rol` · `sin_entregar` · `plazo_app_vencido` (hasta los 90 días) · `plazo_vencido` (después de los 90) · `nada_disponible` · `null`. La pantalla elige el texto con el motivo (4.6) y nunca con el rol que tiene en memoria |
| O2 (resuelto) | **El monto antes de confirmar el arrepentimiento.** C9 pide mostrarlo «a precio pagado» antes de enviar, y MATU-61 (14) dice que la pantalla no calcula montos | Backend y Jorge | La pantalla suma `cantidad × precio_pagado` en pesos enteros, con una función pura y sus pruebas. Solo es para la vista previa. Suma el envío si quedan elegidos todos los productos recibidos y la línea `incluye_envio_si_todo` del `GET …/retractos` es verdadera. **El monto que manda es el de la respuesta del `POST`.** Si difiere, la pantalla muestra el del servidor. La otra opción es un `POST …/retractos/vista-previa` del backend, que es más caro |
| O3 | **El estado de cada parte.** El contrato define los estados de la parte en el comercio (`enviada`, `preparando`, `lista`, `retirada` y `cancelada`), y C16 pide los textos de la familia. Con `cancelada` hay dos casos: el comercio no tenía nada (MATU-63, O3) o la familia canceló | Backend | La parte trae `cancelada_por`: `faltante` o `pedido`. Los textos van en 4.3 |
| O4 (resuelto) | **«Pagos anulados».** El encargo nombra así la sección de las devoluciones, pero la sección 38 no trae ese título. Además, «anulado» ya nombra en `lenguaje.md` 32 el pago tardío que nunca quedó en el pedido (MATU-62, 7.9) | Jorge | El `h2` se llama «Dinero devuelto» **[NUEVO]**. Es el verbo de todas sus frases («Devolvimos…»), sirve para quien pagó y para quien no, y no se confunde con «Anulamos tu pago». Un pago tardío anulado no aparece en «Tus pedidos», porque nunca fue un pedido pagado |
| O5 | **Los productos en la fila de quien ve el pago.** La lista de la revisión previa le trae los productos solo al observador. Para Carmen, «Pedido 4821» no dice nada. La fecha ayuda, y el primer producto ayudaría más | Backend (no bloquea) | Opcional: `resumen_productos` en la fila, con el primer nombre y cuántos más. Con eso, la fila suma «Pañal adulto M x30 y 2 productos más» **[NUEVO]**. Si no viene, la fila no lo muestra y no se pide aparte |
| O6 | **La hora del plazo.** L 36 dice «hasta el `{DD/MM/AAAA}`», y C19 pide la hora de Chile | Backend | `plazo_hasta` es el fin del día hábil en Chile (23:59), y la pantalla muestra solo la fecha. Si el plazo vence a otra hora, la pantalla agrega «a las `{HH:MM}`» |

**Lo que este documento no decide:**
- la pantalla de operación que resuelve los arrepentimientos y registra los que llegan por correo (MATU-81);
- el aviso por push o por correo (MATU-76). Aquí solo se propone adónde lleva (2.4);
- los textos de la política 0.20 (D-92-4).

---

## 1. Para quién y qué

**Carmen, admin**, recibe el aviso «MATU: hay una novedad en un pedido.» y abre MATU. Quiere saber dónde va el pedido de los pañales y si le devolvieron lo que faltó. Lo mira con una mano y en pocos segundos: el estado se lee primero, en palabras.

**Rodrigo, pagador**, ve el mismo pedido, con su tarjeta y su código de autorización porque pagó él. Si a María no le sirvió un suplemento, se arrepiente de la compra desde ahí.

**Un cuidador** ve el estado, los productos, los montos y el comprobante, sin la tarjeta. No cancela ni se arrepiente, y la pantalla le dice quién puede hacerlo, sin nombres.

**El observador** ve solo la fecha, los productos y «Pagado» (D-92-1). No abre el detalle.

**Lo que estas pantallas nunca hacen:**
- Mostrar el código de retiro, nombrarlo ni dar una pista de él (D-63-5). Tampoco la referencia opaca de la parte ni nada de la cuenta del comercio (C15).
- Mostrar una cancelación o un arrepentimiento como hechos antes de que el servidor responda: aquí no hay interfaz optimista (C10).
- Decidir por su cuenta quién puede cancelar o arrepentirse (C7, O1).
- Mostrar la tarjeta o el `{ultimos4}` a quien no pagó (C17), o el nombre de quien pidió algo (C18).
- Pedir el motivo del arrepentimiento (C9).
- Guardar algo de un pedido en `localStorage`, `sessionStorage`, la URL o el historial. Las rutas no llevan ids: el pedido elegido vive en la memoria de la página.
- Decir «rechazado», «fallido», «stock», «reserva», «con IVA», «código de retiro» ni los términos de `lenguaje.md` 3 (C26). Decir «10 días» sin «hábiles» (C20).

---

## 2. Rutas y cómo se llega

### 2.1 Rutas nuevas

| Ruta | Pantalla | Quién | `<title>` | Sección |
|---|---|---|---|---|
| `/insumos/tus-pedidos` | Tus pedidos | los cuatro roles | «Tus pedidos · MATU» [L 38] | 3 |
| `/insumos/tus-pedidos/pedido` | El detalle de un pedido | admin, cuidador y pagador | «Pedido `{referencia}` · MATU» [L 38] | 4 |
| `/insumos/tus-pedidos/arrepentirme` | Arrepentirme de la compra | quien el servidor permite (admin y quien pagó) | «Arrepentirme de la compra · MATU» **[NUEVO]**, con el botón de [L 36] | 5 |

- **Por qué `tus-pedidos` y no `pedidos`.** `Shell.tsx` (`Persona.cambiar`) reconoce el pedido en curso con `ruta.startsWith('/insumos/pedido')`. Una ruta `/insumos/pedidos` caería en ese caso y llevaría al carrito. Con `tus-pedidos` no hay choque, y la ruta repite el título.
- Se agregan a `Ruta` y `RUTAS` de `ruteo.ts`. `seccionDe` ya las reconoce por el prefijo `/insumos`, así que la sección activa de la barra es Insumos.
- **El pedido elegido vive en memoria.** Si se recarga el detalle o la página de arrepentirse, o si el pedido ya no viene en la lista, la app va a `/insumos/tus-pedidos` con `replace` y sin aviso (el patrón de MATU-63, 2.1).
- **El observador** que llega al detalle o a arrepentirse va a la lista, con `replace`. Lo mismo pasa con quien llega a arrepentirse sin `puede_arrepentirse`.
- **Al llegar a cada ruta, el foco va al `h1`** (la regla de la app).

### 2.2 La quinta pestaña de Insumos

| Pestaña | Ruta | Texto |
|---|---|---|
| 1 | `/insumos` | «Insumos» |
| 2 | `/insumos/lista` | «Lista de insumos» [L 21] |
| 3 | `/insumos/catalogo` | «Catálogo» [L 27] |
| 4 | `/insumos/pedido` | «Pedido» [L 31] |
| 5 | `/insumos/tus-pedidos` | «Tus pedidos» [L 38] |

- **Va al final, con la capa 3.** Se ve cuando se ve «Pedido» (`capa3 === true`) y para los cuatro roles. Si se quita la capa 3, salen las tres últimas pestañas y las de antes quedan como estaban.
- **Activa también en el detalle y en arrepentirse.** `PestanasInsumos` suma la ruta a su tipo `activa`.
- **Por qué una pestaña y no una sección de la barra.** La barra del teléfono lleva como máximo cuatro secciones (DISENO.md 2, MATU-107). Tampoco va en el selector de la persona del encabezado: ese control elige a quién se mira y no es un menú. Sumarle navegación le daría dos trabajos.
- **Medidas a 360 px** (328 px útiles, `text-base` en negrita con `px-3` y `gap-1`, con las medidas de MATU-61 2.2):
  - primer renglón: «Insumos» y «Lista de insumos», 263 px;
  - segundo renglón: «Catálogo» (97 px), «Pedido» (82 px) y «Tus pedidos» (unos 126 px), unos 313 px.

  Son los mismos dos renglones de hoy. Lo mido con captura en la revisión. Si «Tus pedidos» no cabe, baja sola a un tercer renglón: `Pestanas` ya envuelve, y no hay desplazamiento horizontal.
- **Sin número en la pestaña** (MATU-61 2.2).

### 2.3 El bloque «Tus pedidos» al final de «Pedido» (reemplaza a MATU-62, 8)

MATU-62 dejó al final de `/insumos/pedido` el bloque «Pedido pagado», con el último pedido pagado, y dijo que lo reemplazaba el seguimiento. Ahora ese bloque **lleva a la lista**:

```
│ ────────────────────────────────── │  mt-10 border-t border-linea pt-6
│ Tus pedidos                        │  h2 titular text-2xl
│ ┌────────────────────────────────┐ │  la fila de 3.3, la más reciente
│ │ Pedido 4821 · 11/11/2026       │ │
│ │ [▣ En preparación]             │ │
│ │ Total pagado: $57.460          │ │
│ └────────────────────────────────┘ │
│ Ver todos tus pedidos              │  Boton texto
```

| Parte | Texto | Origen |
|---|---|---|
| Título | Tus pedidos | [L 38] |
| Fila | La de 3.3, la del pedido pagado más reciente. Se toca para abrir el detalle | — |
| Enlace | Ver todos tus pedidos. Va solo si hay más de un pedido | **[NUEVO]** |

- Sin `turquesa` macizo: no compite con «Ver el total» del carrito.
- Para el observador, la fila es la de 3.4, sin detalle.
- Si no hay ningún pedido pagado, el bloque no va.
- **Por qué aquí:** después de pagar, Carmen vuelve a «Pedido» con «Ir a tu pedido» (MATU-62). Aquí encuentra el pagado sin buscarlo.

### 2.4 Otras entradas

- **El comprobante de la vuelta de Webpay** (MATU-62, 7.4) suma, junto a «Ir a tu pedido», `Boton variante="texto"` «Ver cómo va tu pedido» **[NUEVO]**, que abre el detalle de 4 con el pedido en memoria.
- **El aviso por push o por correo** (MATU-76): propongo que lleve a `/insumos/tus-pedidos` con la persona del pedido elegida. Lo decide esa historia.
- **No hay pantalla de inicio:** `/` lleva a la ficha o a Insumos (`AppFamilia.tsx`, `inicio`). La pestaña es la entrada estable.

### 2.5 Cambiar de persona

Al cambiar de persona en el encabezado, desde cualquiera de las tres rutas, la app va a `/insumos/tus-pedidos` de la otra persona. Pide `Persona.cambiar` un caso nuevo, antes del de `/insumos/pedido`.

---

## 3. Tus pedidos (la lista)

**Objetivo:** Carmen ve de un vistazo cómo va cada pedido pagado de su mamá y abre el que le importa.

**Jerarquía:**
1. El **estado** de cada pedido, en palabras y con un ícono.
2. La fecha y la referencia, que dicen cuál es.
3. El total pagado y lo devuelto, la bajada y «Ver más pedidos».

### 3.1 Esquema a 360 px (admin, cuidador y pagador)

```
┌────────────────────────────────────┐
│ Insumos   Lista de insumos         │  Pestanas, «Tus pedidos» activa
│ Catálogo  Pedido  Tus pedidos      │
│ Tus pedidos                        │  h1 titular text-3xl
│ Los pedidos pagados de María, de   │  bajada text-base text-tenue max-w-prose
│ los últimos 2 años.                │
│                                    │
│ ┌────────────────────────────────┐ │  li > button: la fila (3.3)
│ │ Pedido 4821 · 11/11/2026       │ │  font-bold, la fecha en cifras
│ │ [⊙ Pagado]                     │ │  Etiqueta ok, Check
│ │ Lo estamos enviando al         │ │  text-base text-tenue (H8)
│ │ comercio. Puede tardar unos    │ │
│ │ minutos.                       │ │
│ │ Total pagado: $57.460          │ │  text-base, la cifra font-bold
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ Pedido 4790 · 02/11/2026       │ │
│ │ [✓ Entregado el 04/11/2026]    │ │  Etiqueta ok, CircleCheck
│ │ Total pagado: $31.980 ·        │ │
│ │ Devuelto: $5.290               │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ Pedido 4655 · 20/10/2026       │ │
│ │ [⊘ Cancelado]                  │ │  Etiqueta neutro, Ban
│ │ Devolvimos $22.980, envío      │ │  text-base text-tenue
│ │ incluido, a la tarjeta con que │ │
│ │ se pagó.                       │ │
│ │ Total pagado: $22.980 ·        │ │
│ │ Devuelto: $22.980              │ │
│ └────────────────────────────────┘ │
│ [ Ver más pedidos ]                │  Boton secundario, solo si hay más
└────────────────────────────────────┘
  (barra de secciones fija abajo)
```

### 3.2 Pantalla ancha (1280 y 1920 px)

```
│ Insumos   Lista de insumos   Catálogo   Pedido   Tus pedidos                          │
│ Tus pedidos                                                                           │  h1
│ Los pedidos pagados de María, de los últimos 2 años.                                  │
│ ┌──────────────────────────────────────────────────────────────────────────────────┐ │  max-w-3xl
│ │ Pedido 4821 · 11/11/2026                                  Total pagado: $57.460  │ │
│ │ [⊙ Pagado]  Lo estamos enviando al comercio. Puede tardar unos minutos.          │ │
│ └──────────────────────────────────────────────────────────────────────────────────┘ │
│ ┌ Pedido 4790 · 02/11/2026                     Total pagado: $31.980 · Devuelto: … ┐ │
│ │ [✓ Entregado el 04/11/2026]                                                      │ │
│ └──────────────────────────────────────────────────────────────────────────────────┘ │
```

- Una columna de `max-w-3xl`, alineada a la izquierda. A 1920 px no se estira: el `main` llega a `max-w-7xl` y la lista queda en `max-w-3xl`. Una fila de 1400 px aleja el estado del total.
- **Desde `@2xl/main`**, la fila es una grilla `grid grid-cols-1 @2xl/main:grid-cols-[minmax(0,1fr)_auto] gap-x-6 gap-y-1`: a la izquierda, la referencia, la fecha y el estado; a la derecha, en la primera fila, el total. El orden del DOM no cambia (referencia, estado, explicación, total).
- Desde `@2xl/main`, la `Etiqueta` y su explicación van en un renglón (`flex flex-wrap items-baseline gap-x-3`).

### 3.3 La fila del pedido

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Lista | `ul flex flex-col gap-3` con `aria-labelledby` del `h1` | — | — |
| Fila | `li` con un `button` del ancho de la lista: es una fila que abre, no una acción. `flex w-full min-h-12 flex-col items-start gap-1.5 rounded-xl bg-hoja px-4 angosto:px-2 py-3 text-left ring-1 ring-linea hover:ring-borde`, y el foco base. Sin `ChevronRight` ni flecha (DISENO.md 5) | — | El patrón de MATU-63 5.3 |
| Primera línea | `p font-bold text-lg`. La referencia y la fecha, cada una en `cifras`, con la cola «·» de DISENO.md 2 | Pedido `{referencia}` · `{DD/MM/AAAA}` | [L 38] |
| Estado | `Etiqueta` con su ícono `size-4` `aria-hidden` y la palabra (4.2) | La primera parte del estado de 4.2 | [L 38] |
| Explicación | `p text-base text-tenue max-w-prose`, solo en los estados que la traen | La segunda parte del estado de 4.2 | [L 38] |
| Productos (O5) | `p text-base`, solo si el contrato los trae | `{producto}` y `{n}` productos más · con uno más: «y 1 producto más» | **[NUEVO]** |
| Total | `p text-base`, la cifra en `cifras font-bold`. Con devoluciones, la cola «·» y «Devuelto:», también en `cifras` | Total pagado: `{total}` · Devuelto: `{monto}` | [L 38] el total · **[NUEVO]** «Devuelto:», la forma que ya usa DISENO.md 2 |

- **El nombre accesible** del `button` es todo su texto, en orden, sin el «·»: «Pedido 4821, 11/11/2026, Pagado, Lo estamos enviando al comercio. Puede tardar unos minutos., Total pagado: $57.460». Sin `aria-label` aparte: lo que se lee es lo que se ve.
- **Orden:** la más reciente arriba (`pagado_en`, descendente).
- **Lo vencido no aparece** (C27): pasados 2 años desde el cierre (D-92-2), el servidor ya no lo trae. La pantalla no filtra nada.
- **Un pedido cancelado con los productos borrados** (C28) se ve igual en la fila: la fila no muestra productos de quien ve el pago.

### 3.4 Vista del observador (D-92-1, C3)

```
│ Tus pedidos                        │  h1
│ Los pedidos pagados de María, de   │  bajada
│ los últimos 2 años.                │
│ Quien administra el grupo, quien   │  p text-base text-tenue max-w-prose, una vez
│ cuida a María y quien paga ven el  │
│ detalle.                           │
│ ┌────────────────────────────────┐ │  li, sin button: no se abre
│ │ 11/11/2026                     │ │  font-bold text-lg, cifras
│ │ [✓ Pagado]                     │ │  Etiqueta ok, Check
│ │ · Pañal adulto M x30           │ │  ul text-base
│ │ · Suplemento vainilla x12      │ │
│ └────────────────────────────────┘ │
```

| Parte | Texto | Origen |
|---|---|---|
| Frase, una vez bajo la bajada | Quien administra el grupo, quien cuida a `{pila}` y quien paga ven el detalle. | [L 38] **[AJUSTE]**: el texto de L 38 empieza con «Pagado ·», que aquí ya dice la `Etiqueta` de cada fila. Repetirlo en la frase lo diría dos veces |
| Fila | `{DD/MM/AAAA}` · `Etiqueta tono="ok"` «Pagado» con `Check` · la lista de productos | [L 38] |
| Productos | `ul list-disc ps-5 text-base`, un `li` por `{producto}`. Con la cantidad solo si la vista del observador la trae («2 × Pañal adulto M x30»). La pantalla no la pide aparte | — |

- **La fila no es un botón** (`li` con `rounded-xl bg-hoja px-4 py-3 ring-1 ring-linea`) y no recibe el foco: no hay detalle que abrir.
- **El observador ve siempre «Pagado»**, en todos los estados. No ve la explicación de H8 («Lo estamos enviando al comercio…»): habla de la entrega, que el observador no ve (D-92-1).
- Sin la referencia, sin el total y sin lo devuelto (C3, C5).
- Un pedido con los productos borrados (C28) muestra, en vez de la lista, «De este pedido guardamos solo lo que se pagó y lo que se devolvió.» [L 38].

### 3.5 Estados de la pantalla

| Estado | Qué se ve | Texto | Origen |
|---|---|---|---|
| **Cargando** | Las pestañas, el `h1` y la bajada desde el principio. Pasados 400 ms, «Cargando…» en `text-lg text-tenue` con `aria-busy` en la lista. Sin esqueleto | Cargando… | [L 26] |
| **Vacío** | En lugar de la lista, `p text-xl font-bold`, y `Boton variante="texto"` «Ir a tu pedido» para admin y cuidador | Todavía no hay pedidos pagados para `{pila}`. · Ir a tu pedido | [L 38] · [L 31] |
| **Error al traer** | El patrón de una columna de MATU-61 11.1: baldosa `bg-tinta/7 text-tenue` con `CloudOff`, el texto en `Anunciado urgencia="alert"` y el `Boton` principal «Volver a intentar», el único macizo | No pudimos traer tus pedidos. Revisa tu conexión y vuelve a intentarlo. · Volver a intentar | [L 38] |
| **Ver más** | Bajo la lista, `Boton variante="secundario"` «Ver más pedidos», solo si hay otra página. Mientras carga, «Cargando más…» con `aria-busy`. Al llegar, el foco va a la primera fila nueva, que se lee, sin otro anuncio | Ver más pedidos · Cargando más… | **[NUEVO]** |
| **Ver más, sin conexión** | `MensajeError` bajo el botón. Las filas que ya estaban siguen a la vista | No pudimos traer más pedidos. Revisa tu conexión y vuelve a intentarlo. | **[NUEVO]**, con la forma de [L 38] |
| **404 de la persona** (de otro grupo, eliminada, o quien salió del grupo, C1 y C4) | Lo trata la app como hoy: vuelve a pedir las personas y va al inicio. Sin texto propio | — | — |
| **Capa 3 apagada** | La pestaña no se ve. Quien abra la ruta ve el patrón de una columna con | Tus pedidos no están disponibles por ahora. | **[NUEVO]**, con la forma de [L 31] |
| **Al día** | La lista se vuelve a pedir al volver a la pestaña (`visibilitychange`) y cada 60 segundos, solo mientras alguna fila esté en `pagado`, para que H8 pase a «Enviado al comercio» sin recargar. **No se anuncia**, y nunca mueve el foco ni el desplazamiento | — | — |

**Sin permiso:** la lista no pide la autorización `despacho` (C1) ni `puede_ver_plan` (C2), así que no hay pantalla de permiso. Quien no ve el pago recibe la vista del observador. La pantalla nunca oculta un dato que llegó: si llega, es un defecto del contrato (MATU-62, 2.3).

---

## 4. El detalle del pedido

**Objetivo:** Carmen sabe en qué va su pedido, qué faltó y cuánto se le devolvió, y si todavía puede cancelarlo o arrepentirse.

**Jerarquía:**
1. El **estado** del pedido, con su explicación.
2. **Cómo va**, por comercio, con los productos y lo que faltó. Después, el **dinero devuelto**.
3. Lo que se puede hacer (arrepentirse, cancelar), lo que se pidió devolver y el **comprobante**.

### 4.1 Esquema a 360 px (Rodrigo, pagador que pagó, pedido entregado)

```
┌────────────────────────────────────┐
│ (pestañas, «Tus pedidos» activa)   │
│ ‹ Volver a tus pedidos             │  Volver
│ Pedido 4790                        │  h1 titular text-3xl, cifras
│ Pagado el 02/11/2026 a las 16:41   │  text-base text-tenue, dos cifras
│ [✓ Entregado el 04/11/2026]        │  Etiqueta ok, CircleCheck
│ ┃(i) Precios de ejemplo. …         │  AvisoPiloto, una vez
│                                    │
│ Cómo va                            │  h2 titular text-2xl
│ ┌────────────────────────────────┐ │  li por parte, bg-hoja ring-1 ring-linea
│ │ De Almacén El Ejemplo          │ │  h3 text-lg font-bold
│ │ (comercio ficticio)            │ │
│ │ [⇥ Salió del comercio]         │ │  Etiqueta neutro, PackageCheck
│ │ 2 × Pañal adulto M x30         │ │  ul text-base, divide-y
│ │ 1 × Suplemento vainilla x12    │ │
│ │     [⊠ Faltaron 1]             │ │  Etiqueta neutro, PackageX
│ └────────────────────────────────┘ │
│                                    │
│ Dinero devuelto                    │  h2 titular text-2xl (O4)
│ ↶ Faltaron 1 de Suplemento         │  li: Undo2 text-ok + frase text-base
│   vainilla x12. Te devolvimos      │
│   $5.290 a tu tarjeta terminada en │
│   4051. Cuándo lo ves en tu cuenta │
│   depende de tu banco.             │
│                                    │
│ Arrepentirme de la compra          │  h2 titular text-2xl
│ Puedes hacerlo hasta el 18/11/2026.│  p text-base max-w-prose
│ Pasamos a buscar los productos sin │
│ costo y te devolvemos su precio a  │
│ la misma tarjeta cuando los        │
│ recibimos con su sello cerrado. Si │
│ devuelves todo, también el envío.  │
│ [ Arrepentirme de la compra ]      │  Boton secundario
│                                    │
│ ┌ Comprobante ───────────────────┐ │  el de MATU-62 7.5, sin cambios
│ │ Pedido 4790 …                  │ │
│ └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘ │
│ Datos del pedido · Lo que te       │  MATU-62 7.5.3
│ garantizamos                       │
│ [ Imprimir o guardar en PDF ]      │  Boton secundario, Printer
└────────────────────────────────────┘
```

**Orden del DOM, el mismo en todos los anchos:**
1. `Volver`, el `h1`, la fecha, el estado y el aviso del piloto;
2. Cómo va;
3. Dinero devuelto;
4. Productos para devolver;
5. lo que se puede hacer (4.6);
6. el comprobante con sus datos y sus garantías.

Una sección sin contenido no va: sin devoluciones no hay «Dinero devuelto».

### 4.2 El estado del pedido (C16, H8)

La primera parte va en la `Etiqueta`. La segunda, si la hay, en un `p text-lg max-w-prose` justo debajo. En la lista va en `text-base text-tenue` (3.3).

| `estado` | `Etiqueta`: tono, ícono (lucide, `aria-hidden`) y palabra | Explicación | Origen |
|---|---|---|---|
| `pagado` (H8) | `ok`, `Check`, «Pagado» | Lo estamos enviando al comercio. Puede tardar unos minutos. | [L 38] |
| `enviado_a_comercio` | `neutro`, `Store`, «Enviado al comercio» | — | [L 38] |
| `preparando` | `neutro`, `PackageOpen`, «En preparación» | — | [L 38], [L 36] |
| `listo_retiro`, `asignado`, `sin_repartidor`, `retirado` | `neutro`, `PackageCheck`, «Listo para salir» | — | [L 38], [L 36] |
| `en_ruta` | `neutro`, `Truck`, «En camino» | — | [L 38], [L 36] |
| `entregado`, `cerrado` | `ok`, `CircleCheck`, «Entregado el `{DD/MM/AAAA}`» | — | [L 38], [L 36] |
| `no_entregado` | `atenta`, `PackageX`, «No pudimos entregarlo» | Te escribimos para coordinar otra entrega o devolverte el total. | [L 38] |
| `reprogramado` | `atenta`, `CalendarClock`, «Entrega reprogramada» | Te avisamos cuando salga de nuevo. | [L 38] |
| `cancelado_con_devolucion`, devolución hecha | `neutro`, `Ban`, «Cancelado» | Devolvimos `{total}`, envío incluido, a la tarjeta con que se pagó. | [L 38] |
| `cancelado_con_devolucion`, devolución en curso | Igual | Estamos devolviendo `{total}`, envío incluido, a la tarjeta con que se pagó. | **[AJUSTE]** de [L 38]: mientras la devolución sigue en curso, «Devolvimos» es falso. Es el mismo paso de «Devolvimos» a «Estamos devolviendo» que ya hace [L 32] |

- **El estado nunca va solo por el color.** Cada `Etiqueta` lleva su palabra y su ícono, y en el modo `angosto` queda la palabra (`Etiqueta` ya lo hace). **El turquesa no se usa para ningún estado** (DISENO.md 1). `ok` marca lo que terminó bien (pagado, entregado), `atenta` lo que necesita a alguien, y `neutro` lo que va en curso o terminó sin más.
- **«Pagado» en `ok`** es la misma marca que usan el comprobante y el bloque de MATU-62.

### 4.3 Cómo va (las partes por comercio)

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Título | `h2 titular text-2xl` | Cómo va | **[NUEVO]** |
| Contenedor | `ul flex flex-col gap-3`. Cada parte, un `li` con `rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea flex flex-col gap-2` | — | — |
| Comercio | `h3 text-lg font-bold break-words`. «(comercio ficticio)» en su propio `inline-block`, solo si `ficticio` es verdadero | De `{comercio}` (comercio ficticio) · sin `nombre_fantasia`: «De un comercio» | [L 38] la forma de «Parte», [L 31] · **[NUEVO]** «De un comercio» |
| Estado de la parte | `Etiqueta` con ícono y palabra. Para el lector, el `h3` y la etiqueta se leen juntos: «De Almacén El Ejemplo (comercio ficticio): En preparación» (un `span sr-only` con «:» entre los dos) | Ver la tabla de abajo | [L 38] la forma «De `{comercio}`: `{estado}`» |
| Productos | `ul divide-y divide-linea`, cada `li` `py-2 text-base`, la cantidad en `cifras` | `{cantidad}` × `{producto}` | [L 31] |
| Faltaron | Al lado del producto, `Etiqueta tono="neutro"` con `PackageX`, solo si `unidades_faltantes` es mayor que 0 | Faltaron `{n}` | **[NUEVO]**. La frase completa con el monto va en «Dinero devuelto» |
| Entregado | Bajo el estado del pedido, no en la parte. La parte no repite la fecha | — | — |

**El estado de cada parte** (C16, O3), con los textos de la familia y nunca con los del comercio:

| Estado de la parte | Tono, ícono y texto | Origen |
|---|---|---|
| `enviada` | `neutro`, `Store`, «Enviado al comercio» | [L 38] |
| `preparando` | `neutro`, `PackageOpen`, «En preparación» | [L 38] |
| `lista` | `neutro`, `PackageCheck`, «Listo para salir» | [L 38] |
| `retirada` | `neutro`, `PackageCheck`, «Salió del comercio» | **[NUEVO]**: «Listo para salir» sería falso cuando el pedido ya va «En camino» o está «Entregado» |
| `cancelada` por faltante (O3) | `neutro`, `PackageX`, «No tenía estos productos» | **[NUEVO]** |
| `cancelada` porque se canceló el pedido | `neutro`, `Ban`, «Cancelado» | [L 38] |

- **Con una sola parte**, el bloque es el mismo: Carmen ve siempre de qué comercio viene.
- **Nunca** el código de retiro, la referencia de la parte, la dirección ni el teléfono del comercio (C15).
- **Productos borrados** (C28): en lugar de las partes va `p text-lg`, «De este pedido guardamos solo lo que se pagó y lo que se devolvió.» [L 38]. Se mantienen el estado, el dinero devuelto y el comprobante con lo que quede.

### 4.4 Dinero devuelto (O4, C13)

Una lista, no una `Nota` por devolución: en el detalle puede haber tres o cuatro, y cuatro avisos con borde seguidos se leen como alarmas.

| Parte | Componente y tokens |
|---|---|
| Título | `h2 titular text-2xl`, «Dinero devuelto» **[NUEVO]** (O4) |
| Lista | `ul divide-y divide-linea border-y border-linea`. Cada `li` con `flex gap-3 py-3 text-base max-w-prose`: el ícono `Undo2` `size-5 mt-0.5 shrink-0 aria-hidden`, en `text-ok` si está hecha y en `text-atenta` si está en curso, y la frase |
| Fecha | Si está hecha, bajo la frase, `p text-base text-tenue`: «El `{DD/MM/AAAA}`» **[NUEVO]**, en `cifras` |

**El estado va en el verbo**, no solo en el color del ícono: «Devolvimos» (hecha) o «Estamos devolviendo» (en curso).

| `motivo` y `producto` | Quien pagó | Quien no pagó | Origen |
|---|---|---|---|
| `producto_no_entregado`, con producto y con `unidades_faltantes` | Faltaron `{n}` de `{producto}`. Te devolvimos `{monto}` a tu tarjeta terminada en `{ultimos4}`. Cuándo lo ves en tu cuenta depende de tu banco. | Faltaron `{n}` de `{producto}`. Devolvimos `{monto}` a la tarjeta con que se pagó. Cuándo se ve en la cuenta depende del banco. | [L 36] · [L 38] (C25) |
| `producto_no_entregado` con producto, el pedido no entregado | Devolvimos `{monto}` a tu tarjeta terminada en `{ultimos4}`, por `{producto}`. Cuándo lo ves en tu cuenta depende de tu banco. | Devolvimos `{monto}` a la tarjeta con que se pagó, por `{producto}`. Cuándo se ve en la cuenta depende del banco. | [L 32] |
| `retracto`, con producto | Igual que la fila anterior | Igual que la fila anterior | [L 32] |
| Producto `null`, fuera de `cancelacion` (el envío) | Devolvimos el envío: `{monto}`. | Devolvimos el envío: `{monto}`. | [L 38] (C13) |
| `cancelacion` (el pedido completo) | Devolvimos `{monto}` a tu tarjeta terminada en `{ultimos4}`, por tu pedido completo. Cuándo lo ves en tu cuenta depende de tu banco. | Devolvimos `{monto}` a la tarjeta con que se pagó, por tu pedido completo. Cuándo se ve en la cuenta depende del banco. | [L 32] con «por tu pedido completo» [L 32] |
| Cualquiera, **en curso** | Estamos devolviendo `{monto}` a tu tarjeta. Si no se completa hoy, te escribimos. MATU nunca te pide los datos de tu banco por mensaje. | Estamos devolviendo `{monto}` a la tarjeta con que se pagó. Si no se completa hoy, le escribimos a quien pagó. MATU nunca pide los datos de un banco por mensaje. | [L 32] |

- **«a tu tarjeta terminada en `{ultimos4}`» solo si `ultimos4` llega**, o sea, solo para quien pagó (C17). Si no llega, la pantalla usa la columna de quien no pagó. No hay otra regla.
- **El pago tardío anulado no va aquí** (`pago_tardio`): no es un pedido pagado (MATU-62, 7.9).
- **El comprobante** de abajo muestra los renglones «Devolvimos: `{producto}`» y «Pagaste en total» de MATU-62 7.7, sin cambios. Esta lista explica, y el comprobante suma.

### 4.5 Productos para devolver (los arrepentimientos pedidos)

Solo si hay al menos uno (`GET …/retractos`).

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Título | `h2 titular text-2xl` | Productos para devolver | **[NUEVO]** |
| Cada pedido de devolución | `li` con `rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea flex flex-col gap-2` | — | — |
| Estado | `Etiqueta`. `solicitado`: `neutro` con `Clock`, «Devolución pedida». `devuelto`: `ok` con `CircleCheck`, «Devuelto el `{DD/MM/AAAA}`». El tercer estado: `neutro` con `CircleX`, «No se aceptó la devolución» | [L 38]. La palabra del contrato para el tercer estado nunca se muestra (C26) |
| Productos | `ul text-base`, `{cantidad}` × `{producto}` | [L 31] |
| Monto | `p text-base`, la cifra en `cifras font-bold`. Si el retracto incluye el envío, la segunda frase | Te devolvemos `{monto}` cuando recibamos los productos con su sello cerrado. · También te devolvemos el envío. | [L 38]. Solo con `solicitado`. Con `devuelto`, lo dice «Dinero devuelto» |
| No se aceptó | `p text-base` con `EnlaceEnFrase mailto:` | Si tienes dudas, escríbenos a `{correo}`. | [L 38], la segunda frase |
| Quién la pidió (C18) | `p text-base text-tenue`, solo si `es_tuyo` es falso | La pidió otra persona de tu grupo. | **[NUEVO]**, con la forma de «Lo pagó otra persona de tu grupo.» [L 32] |
| Por correo (C21) | `p text-base text-tenue`, si `origen` es `correo` | Tuya: «Esta devolución la pediste por correo. La registró el equipo de MATU.» · De otra persona: «Esta devolución se pidió por correo. La registró el equipo de MATU.» | [L 38] · **[AJUSTE]**: «la pediste» es falso cuando no la pidió quien mira |

Con `solicitado`, la primera vez que se ve después de pedirla vale el texto de 5.6. Aquí el estado se lee como «Devolución pedida».

### 4.6 Lo que se puede hacer

Va después de lo que se pidió devolver y antes del comprobante. Cada bloque lleva su `h2` (`titular text-2xl`). **En el detalle no hay ningún elemento en `turquesa` macizo**: no hay algo que Carmen tenga que hacer. Arrepentirse es secundario, y cancelar es `peligro`, porque ninguno es la tarea de todos los días.

#### 4.6.1 Arrepentirme de la compra

| `puede_arrepentirse` y motivo (O1) | Qué se ve | Texto | Origen |
|---|---|---|---|
| Sí | `h2` «Arrepentirme de la compra», la ayuda en `p text-base max-w-prose` y `Boton variante="secundario"` con el mismo texto, que lleva a 5 | Arrepentirme de la compra · Puedes hacerlo hasta el `{DD/MM/AAAA}`. Pasamos a buscar los productos sin costo y te devolvemos su precio a la misma tarjeta cuando los recibimos con su sello cerrado. Si devuelves todo, también el envío. | [L 36]. **La última frase va solo si las condiciones de la versión aceptada incluyen el envío** (C9) |
| No, `rol`, con el plazo abierto | El `h2` y la frase, sin botón | Pueden arrepentirse de la compra quien administra el grupo y quien la pagó. | [L 38] |
| No, `sin_entregar` | Nada: el derecho corre desde la entrega, y el comprobante ya lo dice en sus garantías | — | — |
| No, `nada_disponible` | El `h2` y la frase | Ya pediste devolver todos los productos de este pedido. | **[NUEVO]** |
| No, `plazo_app_vencido` (hasta 90 días) | El `h2` y la frase con `EnlaceEnFrase mailto:` | El plazo para arrepentirte desde la aplicación terminó el `{DD/MM/AAAA}`. Si todavía quieres devolver productos, o tienes un problema con el pedido, escríbenos a `{correo}`. | [L 38] (C22) |
| No, `plazo_vencido` (después de 90 días) | Igual | El plazo para arrepentirte terminó el `{DD/MM/AAAA}`. Si tienes un problema con el pedido, escríbenos a `{correo}`. | [L 38], [L 36] (C22) |

- La fecha sale de `plazo_hasta` (C19, O6), en `cifras`.
- **El botón lleva solo su texto**, sin flecha ni ícono (DISENO.md 5). Es el mismo verbo del `h2`, del `h1` de 5 y de su `<title>`.

#### 4.6.2 Cancelar el pedido

| `puede_cancelar` y motivo (O1) | Qué se ve | Texto | Origen |
|---|---|---|---|
| Sí (solo admin, C10) | `h2` «Cancelar el pedido», la frase en `p text-base max-w-prose` y `Boton variante="peligro"` con el texto del botón, que abre 6 | Cancelar el pedido · Puedes cancelarlo sin costo mientras el comercio no empiece a prepararlo. | [L 36] el botón · **[NUEVO]** la frase, en tú, de la garantía de [L 32] |
| No, `rol`, el comercio todavía no empieza | El `h2` y la frase, sin botón | Solo quien administra el grupo puede cancelar un pedido pagado, mientras el comercio no empiece a prepararlo. | [L 38] |
| No, `ya_se_prepara` o `cancelado` | Nada: el estado del pedido ya lo dice | — | — |

**Si se ven los dos bloques**, arrepentirse va primero. No pueden darse a la vez: cancelar es antes de preparar, y arrepentirse, después de entregar.

### 4.7 El comprobante (C14)

- Es el de MATU-62 7.5, **el mismo componente y sin cambios**, con los datos de `GET …/pago`: el encabezado, el sello del piloto si `pago_de_prueba` es verdadero, los renglones, «Total pagado», la `Etiqueta` «Pagado» y la tarjeta solo para quien pagó (o «Lo pagó otra persona de tu grupo.»). También los renglones de las devoluciones, «Datos del pedido», «Lo que te garantizamos» y «Imprimir o guardar en PDF».
- **«Lo que te garantizamos»** dice «Derecho a retracto: tienes 10 días hábiles desde que lo recibes.» (C24 y D1). El mismo cambio llega a los dos textos de retracto de [L 27], en el carrito y en el resumen de MATU-61. Se hace en `web/` y en `lenguaje.md` 27 y 32.
- **«Imprimir o guardar en PDF»** imprime solo el comprobante, con la hoja de MATU-62 7.5.5. Nunca imprime las partes ni el estado.
- El comprobante **no** lleva la dirección ni el teléfono de entrega (MATU-62, 7.5.1). El detalle tampoco los muestra.

### 4.8 Pantalla ancha (1280 y 1920 px)

```
│ ‹ Volver a tus pedidos                                                                 │
│ Pedido 4790                                                                            │  h1
│ Pagado el 02/11/2026 a las 16:41   [✓ Entregado el 04/11/2026]                         │
│ ┃(i) Precios de ejemplo. …                                                             │
│ Cómo va                                         ┌ Comprobante ─────────────────────┐  │
│ ┌ De Almacén El Ejemplo (comercio ficticio) ─┐  │ Pedido 4790                      │  │
│ │ [⇥ Salió del comercio]                     │  │ 02/11/2026 a las 16:41           │  │
│ │ 2 × Pañal adulto M x30                     │  │ ┃ Pago de prueba. …              │  │
│ │ 1 × Suplemento vainilla x12 [⊠ Faltaron 1] │  │ …                                │  │
│ └────────────────────────────────────────────┘  │ Total pagado            $31.980  │  │
│ Dinero devuelto                                 │ Devolvimos: Suplemento… −$5.290  │  │
│ ↶ Faltaron 1 de Suplemento vainilla x12. …      │ Pagaste en total        $26.690  │  │
│ Arrepentirme de la compra                       └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘  │
│ Puedes hacerlo hasta el 18/11/2026. …           Datos del pedido · Lo que te garantiz…│
│ [ Arrepentirme de la compra ]                   [ Imprimir o guardar en PDF ]         │
```

- **Dos columnas desde `@3xl/main`**, como el comprobante de MATU-62 7.4.2: `grid grid-cols-1 @3xl/main:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-x-10 gap-y-8`. A la izquierda, lo que pasa (4.3 a 4.6). A la derecha, el comprobante con sus datos y garantías, `@3xl/main:col-start-2 @3xl/main:row-start-1 @3xl/main:row-span-4`, pegajoso (`@3xl/main:sticky @3xl/main:top-6`), con `max-h-[calc(100dvh-3rem)] overflow-y-auto [scrollbar-width:thin]` (DISENO.md 3).
- **El encabezado** (`Volver`, `h1`, fecha, estado y aviso) va arriba, a todo el ancho. Desde `@xl/main`, la fecha y la `Etiqueta` van en un renglón (`flex flex-wrap items-center gap-x-4 gap-y-2`).
- **El DOM no cambia:** el comprobante va al final, como en el teléfono. Las secciones son independientes, así que el orden de lectura no pierde sentido (WCAG 1.3.2).
- **A 1920 px**, el `main` llega a `max-w-7xl` y el comprobante mide unos 470 px: no se estira.
- **La parte** no cambia de forma en ancho: el producto y «Faltaron» van en un renglón (`flex flex-wrap items-center gap-x-3`).

### 4.9 Estados de la pantalla

| Estado | Qué se ve | Texto | Origen |
|---|---|---|---|
| **Cargando** | El `Volver`, el `h1` con la referencia (viene de la fila) y, pasados 400 ms, «Cargando…» con `aria-busy` en el contenido | Cargando… | [L 26] |
| **Error al traer** | El patrón de una columna de 3.5, con el `h1` «Pedido `{referencia}`» | No pudimos traer tu pedido. Revisa tu conexión e inténtalo de nuevo. · Volver a intentar | [L 31] · [L 26] |
| **Falla solo el comprobante** (`GET …/pago`) | El detalle se ve, y en el lugar del comprobante va `Nota tono="atenta"` con `CloudOff` y `Boton variante="secundario"` «Volver a intentar» | No pudimos traer el comprobante. Revisa tu conexión y vuelve a intentarlo. · Volver a intentar | **[NUEVO]** · [L 26] |
| **404** (el pedido ya no es del grupo, la persona se eliminó o quien mira salió del grupo, C1 y C4) | Patrón de una columna, baldosa `bg-tinta/7` con `SearchX`, y `Boton variante="secundario"` «Volver a tus pedidos» | No encontramos este pedido. · Volver a tus pedidos | [L 31] · **[NUEVO]** |
| **Sin permiso** | No existe: el observador no llega al detalle (2.1), y quien no puede cancelar o arrepentirse ve la frase de 4.6 | — | — |
| **Al día** | Se vuelve a pedir al volver a la pestaña (`visibilitychange`), sin anunciar y sin mover el foco | — | — |

---

## 5. Arrepentirme de la compra (`/insumos/tus-pedidos/arrepentirme`)

**Objetivo:** Rodrigo elige qué productos devuelve y cuántos, sabe cuánto le devuelven y hasta cuándo, y lo pide con un toque.

**Jerarquía:**
1. Hasta cuándo y qué pasa: el `h1` y la bajada.
2. Los productos, con cuántos devuelve de cada uno.
3. El resumen de lo que va a devolver, con el monto, y «Devolver estos productos».

### 5.1 Esquema a 360 px

```
┌────────────────────────────────────┐
│ (pestañas, «Tus pedidos» activa)   │
│ ‹ Volver al pedido 4790            │  Volver
│ Arrepentirme de la compra          │  h1 titular text-3xl
│ Puedes hacerlo hasta el 18/11/2026.│  bajada text-lg max-w-prose
│ Pasamos a buscar los productos sin │
│ costo y te devolvemos su precio a  │
│ la misma tarjeta cuando los        │
│ recibimos con su sello cerrado. Si │
│ devuelves todo, también el envío.  │  (solo si las condiciones lo incluyen)
│                                    │
│ Elige qué productos devuelves      │  h2 text-xl font-bold
│ ┌────────────────────────────────┐ │  li, bg-hoja ring-1 ring-linea px-4 py-4
│ │ Pañal adulto M x30             │ │  h3 text-xl font-bold
│ │ Recibiste 2. Pagaste $12.990   │ │  text-base, cifras
│ │ cada uno.                      │ │
│ │ Si abres el sello, ya no se    │ │  text-lg font-bold (solo si pierde)
│ │ puede devolver.                │ │
│ │ ¿Cuántos devuelves?            │ │  Stepper, label font-bold
│ │ [ − ] [  0  ] [ + ]            │ │  size-12, campo w-24 text-xl
│ │ Puedes devolver hasta 2.       │ │  ayuda text-base text-tenue
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ Suplemento vainilla x12        │ │
│ │ Recibiste 3. Pagaste $26.490   │ │
│ │ cada uno.                      │ │
│ │ Ya pediste devolver 1.         │ │  text-base text-tenue
│ │ ¿Cuántos devuelves?            │ │
│ │ [ − ] [  1  ] [ + ]            │ │
│ │ Puedes devolver hasta 2.       │ │
│ └────────────────────────────────┘ │
│                                    │
│ ┌ Lo que vas a devolver ─────────┐ │  section, la boleta: bg-hoja ring-1 rounded-t-lg
│ │ Vas a devolver:                │ │  text-lg font-bold
│ │ · 1 × Suplemento vainilla x12  │ │  ul text-lg
│ │ Te devolvemos $26.490 cuando   │ │  text-lg, la cifra font-bold
│ │ recibamos los productos con su │ │
│ │ sello cerrado.                 │ │
│ └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘ │
│ [ Devolver estos productos ]       │  principal. Único turquesa macizo
│ No, volver                         │  Boton texto
└────────────────────────────────────┘
```

### 5.2 Pantalla ancha (1280 y 1920 px)

```
│ ‹ Volver al pedido 4790                                                                │
│ Arrepentirme de la compra                                                              │  h1
│ Puedes hacerlo hasta el 18/11/2026. Pasamos a buscar los productos sin costo y …       │  max-w-prose
│ Elige qué productos devuelves                   ┌ Lo que vas a devolver ────────────┐  │
│ ┌ Pañal adulto M x30 ────────────────────────┐  │ Vas a devolver:                   │  │
│ │ Recibiste 2. Pagaste $12.990 cada uno.      │  │ · 1 × Suplemento vainilla x12     │  │
│ │ Si abres el sello, ya no se puede devolver. │  │ Te devolvemos $26.490 cuando …    │  │
│ │ ¿Cuántos devuelves?  [−] [ 0 ] [+]          │  └~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~┘  │
│ │ Puedes devolver hasta 2.                    │  [ Devolver estos productos ]          │
│ └─────────────────────────────────────────────┘  No, volver                            │
```

- Dos columnas desde `@3xl/main`: `grid grid-cols-1 @3xl/main:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-x-10 gap-y-8`. A la derecha, el resumen y los dos botones, pegajosos (`@3xl/main:sticky @3xl/main:top-6`). Es la composición del resumen de MATU-61 9.10.
- **El DOM no cambia:** los productos van primero y el resumen con los botones después, como en el teléfono.
- **El botón no va a todo el ancho** de su columna (DISENO.md 5). Va al ancho de su texto.

### 5.3 La línea por devolver

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Contenedor | `li` con `rounded-xl bg-hoja px-4 angosto:px-2 py-4 ring-1 ring-linea grid grid-cols-1 gap-y-3`. La línea no es un botón | — | — |
| Producto | `h3 text-xl font-bold break-words`, con `id` | `{producto}` | — |
| Lo recibido | `p text-base tabular-nums`, sin `cifras` para que refluya | Recibiste `{entregado}`. Pagaste `{precio}` cada uno. | **[NUEVO]**. El precio es el pagado, nunca el del catálogo (C9) |
| El sello | `p text-lg font-bold max-w-prose`, solo si `retracto_pierde_al_abrir`. En `tinta`, sin color: se lee por la letra y la posición | Si abres el sello, ya no se puede devolver. | [L 38] |
| Ya pedido | `p text-base text-tenue`, solo si ya se pidió devolver alguno | Ya pediste devolver `{n}`. | **[NUEVO]** |
| Cuántos | `Stepper` de `insumosComun.tsx`, con `seleccionarAlEnfocar` (MATU-61 7.5): `min` 0, `max` lo disponible y valor inicial 0. Los botones con `textoMenos` «Uno menos: `{producto}`» y `textoMas` «Uno más: `{producto}`». El campo se nombra con `aria-labelledby` (la etiqueta y el `h3`) | ¿Cuántos devuelves? · Para el lector: Uno menos: `{producto}` · Uno más: `{producto}` | **[NUEVO]**, con la forma de [L 37] |
| Ayuda | `p text-base text-tenue`, en el `aria-describedby` del campo | Puedes devolver hasta `{disponible}`. | **[NUEVO]** |
| Nada disponible | En lugar del `Stepper` y la ayuda, `p text-base` | Ya pediste devolver todos. | **[NUEVO]** |
| Fuera de rango | `MensajeError` bajo el campo, `aria-invalid`, al salir del campo o al tocar «Devolver estos productos» | Escribe un número de 0 a `{disponible}`. | **[NUEVO]**, con la forma de [L 31] |

- **Se cuenta en envases del pedido**, los mismos de la línea (MATU-61 7.5). El valor inicial es 0: Rodrigo dice qué devuelve, y nada se marca por él.
- **Sin interfaz optimista y sin guardar al cambiar:** la cantidad vive en la memoria de la página hasta que se envía.

### 5.4 El resumen de la devolución (C9)

| Parte | Componente y tokens | Texto | Origen |
|---|---|---|---|
| Contenedor | El de la boleta de MATU-61 9.4: `section aria-labelledby`, `rounded-t-lg bg-hoja px-4 @3xl/main:px-7 angosto:px-2 pt-5 pb-8 ring-1 ring-linea` con la máscara del borde cortado | — | — |
| Título | `h2 text-xl font-bold` | Lo que vas a devolver | **[NUEVO]** |
| Sin nada elegido | `p text-lg text-tenue` | Todavía no eliges ningún producto. | **[NUEVO]** |
| Lo elegido | `p text-lg font-bold` y un `ul text-lg`, un `li` por línea con cantidad mayor que 0 | Vas a devolver: · `{cantidad}` × `{producto}` | [L 38] **[AJUSTE]**: en lista y no en una frase, porque pueden ser varios productos |
| Monto | `p text-lg max-w-prose`, la cifra en `cifras font-bold` | Te devolvemos `{monto}` cuando recibamos los productos con su sello cerrado. | [L 38]. El monto es el de O2 |
| Envío | `p text-lg`, solo si lo elegido completa todo lo recibido y las condiciones lo incluyen (O2) | También te devolvemos el envío. | [L 38] |
| Sello | `p text-lg font-bold`, solo si alguna línea elegida pierde el derecho al abrir | Si abres el sello, ya no se puede devolver. | [L 38] |
| Botón | `Boton` principal, al ancho de su texto. Mientras envía, `textoOcupado` y `aria-busy`. Nunca deshabilitado: la validación ocurre al tocarlo | Devolver estos productos · Enviando… | [L 38], [L 36] |
| Salida | `Boton variante="texto"`, que vuelve al detalle sin enviar nada | No, volver | [L 38], [L 36] |

- **El resumen cambia en cuanto cambia una cantidad**, sin región viva: el campo ya dice el número, y anunciar cada toque sería ruido (el patrón del subtotal de MATU-61 7.4).
- **No se pide el motivo** (C9).
- **La fecha límite** está en la bajada, sobre los productos, y no se repite en el resumen.

### 5.5 Al tocar «Devolver estos productos»

```
toca ─► ¿hay al menos una cantidad > 0 y todas en rango?
          ├─ no ─► MensajeError sobre el botón, el foco al primer campo con error o al primero
          └─ sí ─► POST …/retractos con Idempotency-Key (C8), el botón en «Enviando…»
                     ├─ 201 ─► al detalle (4), con la Nota de 5.6 y el foco en el h1
                     ├─ 422 producto-no-retractable, ya se pidió (otra persona, al mismo tiempo) ─► 5.7
                     ├─ 409 fuera-de-plazo, el plazo venció ─► al detalle, que muestra 4.6.1
                     ├─ 404 ─► 4.9, 404
                     └─ red o 5xx ─► MensajeError, lo elegido sigue en pantalla
```

- **Por qué 422 y no 409** (v1.2): la decisión 445 del contrato responde 422 `producto-no-retractable` cuando lo pedido ya no está disponible, también si otra persona ganó la carrera. Para la pantalla es el mismo caso de 5.7. Un 409 que no sea `fuera-de-plazo` ni el de la clave en curso se trata igual que el 422.
- **La `Idempotency-Key` se crea al tocar el botón** y se reutiliza si se vuelve a tocar después de un error de red, para no pedir dos veces lo mismo. Vive en la memoria de la página, nunca en el almacenamiento del navegador.
- Mientras envía, los `Stepper` son de solo lectura.

### 5.6 Textos del resultado y de los errores

| Caso | Componente | Texto | Origen |
|---|---|---|---|
| Nada elegido | `MensajeError` sobre el botón, también anunciado por `alert`. El foco va al primer campo | Elige al menos un producto y cuántos devuelves. | [L 38] |
| Hecho | En el detalle, bajo el estado, `Nota tono="ok"` con `rol="status"`, hasta salir de la pantalla. El foco va al `h1` | Recibimos tu pedido de devolución. Te escribimos para coordinar el retiro. | [L 36] |
| Red o 5xx | `MensajeError` sobre el botón, anunciado por `alert`. El foco se queda en el botón | No pudimos enviar tu pedido de devolución. Revisa tu conexión y vuelve a intentarlo. Lo que elegiste sigue aquí. | **[NUEVO]**, con la forma de [L 8] |

### 5.7 Ya se pidió (422 `producto-no-retractable`, carrera entre dos personas, C8)

Otra persona del grupo pidió devolver algunos de los mismos productos mientras Rodrigo elegía. La pantalla vuelve a pedir `GET …/retractos`, baja cada cantidad elegida al nuevo disponible (nunca la sube) y muestra, sobre «Elige qué productos devuelves», `Nota tono="atenta"` con `rol="alert"`, que recibe el foco (`enfocable`):

> **Otra persona de tu grupo ya pidió devolver algunos de estos productos.** Te mostramos lo que todavía puedes devolver. Revisa lo que elegiste antes de enviarlo. **[NUEVO]**, con el patrón de [L 31] («Este pedido cambió mientras lo revisabas.»)

Si ya no queda nada disponible, la pantalla va al detalle, que muestra «Ya pediste devolver todos los productos de este pedido.» (4.6.1).

### 5.8 Estados de la pantalla

| Estado | Qué se ve |
|---|---|
| **Cargando** (`GET …/retractos`) | El `Volver` y el `h1` desde el principio. Pasados 400 ms, «Cargando…» [L 26] con `aria-busy`. La bajada espera la fecha |
| **Error al traer** | El patrón de una columna de 3.5: «No pudimos traer tu pedido. Revisa tu conexión e inténtalo de nuevo.» [L 31] y «Volver a intentar» |
| **Sin permiso** | No llega: sin `puede_arrepentirse`, la ruta va a la lista (2.1). Si el servidor responde 404 (el observador, C6), es el 404 de 4.9 |
| **Plazo vencido al abrir** | Va al detalle, que muestra 4.6.1 |
| **422 `producto-no-retractable`** | 5.7 |

| Parte | Texto | Origen |
|---|---|---|
| `Volver` | Volver al pedido `{referencia}` | **[NUEVO]** |

---

## 6. Cancelar el pedido pagado (R15)

**Objetivo:** Carmen cancela un pedido que el comercio todavía no empieza a preparar, sabiendo exactamente cuánto vuelve y a dónde.

Desde 4.6.2, solo para el admin y solo si el servidor dice que se puede (C10). Es el `DialogoConfirmar` del pedido (MATU-61 10, el patrón de MATU-44 4.1): `<dialog>` modal con `showModal()`, `max-w-md`, el foco inicial en el título, la región de error vacía y sin animación.

### 6.1 Esquema (igual a 360 px y en ancho)

```
┌──────────────────────────────────┐
│ ¿Cancelar este pedido?           │  h2 text-xl font-bold, tabIndex -1
│ Te devolvemos $57.460, envío     │  p text-base, la cifra en cifras font-bold
│ incluido, a la misma tarjeta.    │
│ Cuándo lo ves en tu cuenta       │
│ depende de tu banco.             │
│ Pago de prueba. No se cobró      │  p text-base text-tenue (solo si pago_de_prueba)
│ dinero real.                     │
│ (región de error)                │
│ [ Cancelar el pedido ]           │  peligroPrincipal: macizo pronto
│ Seguir con el pedido             │  texto
└──────────────────────────────────┘
```

### 6.2 Textos

| Parte | Texto | Origen |
|---|---|---|
| Título | ¿Cancelar este pedido? | [L 38], [L 31] |
| Monto (C12) | Te devolvemos `{total}`, envío incluido, a la misma tarjeta. Cuándo lo ves en tu cuenta depende de tu banco. | [L 38]. `{total}` es el `total` del pedido que trae el servidor: la pantalla no lo calcula |
| Sello (C12) | Pago de prueba. No se cobró dinero real. Solo si `pago_de_prueba` es verdadero | [L 32] (D-62-7) |
| Botones | Cancelar el pedido (`peligroPrincipal`) · Seguir con el pedido (`texto`) | [L 38] |
| En curso | Cancelando… | [L 38] |

- **«a la misma tarjeta» sin los últimos 4** en el diálogo, también para quien pagó: es el texto de [L 38] y C12. La tarjeta se ve en el comprobante, debajo.
- **Por qué «Cancelar el pedido» y no «Cancelar pedido»** (MATU-61): es otro diálogo y otra acción (con devolución), y [L 36] y [L 38] lo fijan así. El botón de 4.6.2 y el del diálogo dicen lo mismo.

### 6.3 Sin interfaz optimista (C10)

```
toca «Cancelar el pedido» ─► el botón en «Cancelando…» (aria-busy), el diálogo sigue abierto
   POST …/cancelar-con-devolucion con Idempotency-Key (C8)
   ├─ 200 ─► cierra el diálogo, vuelve a pedir el pedido y el pago, y muestra el detalle nuevo
   │          con la Nota de «Hecho». El foco va a esa Nota
   ├─ 409 estado-pedido (ya se canceló, C11) ─► cierra, vuelve a pedir y muestra «Ya cancelado»
   ├─ 409 ya-se-prepara ─► cierra, vuelve a pedir y muestra «Ya se prepara»
   ├─ 403 o 404 ─► cierra y muestra 4.9, 404 (no debería pasar: el botón solo aparece si se puede)
   └─ red o 5xx ─► vuelve a pedir el pedido:
                    ├─ ya cancelado ─► como el 200 (la petición llegó)
                    └─ igual ─► error en la región del diálogo, que sigue abierto
```

- **Nada cambia en pantalla antes de la respuesta.** El estado, la `Etiqueta` y «Dinero devuelto» cambian cuando llega el pedido nuevo del servidor.
- **La `Idempotency-Key`** se crea al tocar el botón y se reutiliza si se vuelve a tocar después de un error de red.
- **`Esc` y «Seguir con el pedido»** cierran sin cancelar y devuelven el foco a «Cancelar el pedido» de 4.6.2. Mientras dice «Cancelando…», `Esc` no cierra el diálogo: la respuesta tiene que llegar a la pantalla.

| Resultado | Componente | Texto | Origen |
|---|---|---|---|
| Hecho | `Nota tono="ok"` con `rol="status"` y `enfocable`, bajo el estado, hasta salir de la pantalla. El bloque 4.6.2 desaparece (`puede_cancelar` ya es falso), así que el foco va a la nota, nunca a `body` | Cancelamos el pedido. Estamos devolviendo `{total}` a la tarjeta con que se pagó. | [L 38] |
| Ya cancelado (409 `estado-pedido`) | `Nota tono="rocio"` con `rol="status"` y `enfocable` | Este pedido ya se canceló. Te mostramos cómo quedó. | [L 38] |
| Ya se prepara (409) | `Nota tono="atenta"` con `rol="alert"` y `enfocable` | Ya están preparando tu pedido, así que no se puede cancelar. Cuando llegue, puedes arrepentirte de la compra. | [L 36] |
| Red o 5xx, sin cambio | En la región de error del diálogo, `rol="alert"` | No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba. | [L 31]. Es cierto, porque la pantalla volvió a leer el pedido antes de decirlo |
| Red o 5xx, y tampoco se pudo volver a leer el pedido | En la región de error del diálogo, `rol="alert"` | No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo. | **[NUEVO]**: sin «Todo sigue como estaba.», porque la pantalla no pudo comprobarlo |

---

## 7. Accesibilidad visual

### 7.1 Elementos en `turquesa` macizo, por pantalla

| Pantalla y estado | Único macizo |
|---|---|
| Tus pedidos, con filas o vacía | Ninguno (las filas son `bg-hoja`, y «Ver más pedidos» es secundario) |
| Tus pedidos, error al traer | «Volver a intentar» |
| El bloque de 2.3 en «Pedido» | Ninguno («Ver el total» del carrito sigue siendo el único) |
| El detalle | Ninguno («Arrepentirme de la compra» es secundario, y «Cancelar el pedido», `peligro`) |
| El detalle, error al traer | «Volver a intentar» |
| Arrepentirme de la compra | «Devolver estos productos» |
| El diálogo de cancelar | Ninguno en `turquesa`: «Cancelar el pedido» es macizo `pronto` |

### 7.2 Áreas táctiles de 48 × 48 px

Todo lo que se toca mide `min-h-12` (51 px):
- la fila de la lista, «Ver más pedidos» y «Ver todos tus pedidos»;
- `Volver` y los botones de 4.6;
- el − y el + del `Stepper` (`size-12`) y su campo;
- los dos botones del diálogo, «Devolver estos productos» y «No, volver»;
- los `mailto:` en frase, con el `::after` de DISENO.md 6;
- las cinco pestañas.

Entre filas hay `gap-3` (13 px). Entre el + de una línea y el − de la siguiente hay una tarjeta entera.

### 7.3 Contraste (valores de DISENO.md, sin colores nuevos)

| Elemento | Colores | Contraste |
|---|---|---|
| Texto de las filas, las partes y el resumen | `tinta` y `tenue` sobre `hoja` | 7,2:1 o más en claro y 8,1:1 o más en oscuro |
| `Etiqueta` `ok`, `atenta` y `neutro` | La de `ui.tsx` (`ok` y `atenta` sobre su fondo, `tenue` sobre `tinta/7`) | 5,9:1 los semánticos. `neutro` lo mido en la revisión, en los dos temas |
| `Undo2` en `ok` o `atenta` sobre `papel` | Ícono con significado | 3:1 o más (WCAG 1.4.11). El estado también va en el verbo |
| Contorno de la fila | `ring-linea` (1,3:1) es decoración, no el borde de un control: la fila se reconoce por su texto y por el foco. Al pasar el puntero, `ring-borde` (3,5:1) | — |
| `peligro` y `peligroPrincipal` | `pronto` sobre `hoja`, y `papel` sobre `pronto` | 6,1:1 o más |

### 7.4 Foco

- **El foco base** es un contorno de 3 px en `turquesa` con 2 px de separación, en todo lo que se toca. En `peligro` y en `peligroPrincipal` va en `pronto`, como en sus variantes.
- **Al llegar a cada ruta**, el foco va al `h1`. Al volver del detalle a la lista con `Volver` o con Atrás, el foco va al `h1` de la lista: no se busca la fila, porque la lista pudo cambiar.
- **Las notas que reciben el foco** después de una acción llevan `enfocable` y no muestran contorno, porque no son controles. Son las de 5.7 y la de «Hecho», «Ya cancelado» y «Ya se prepara» en 6.3. Se enfocan **después** de montarse con su contenido final, y el foco nunca termina en `body` (MATU-63 6.3).
- **El orden de Tab en la línea por devolver** es −, campo y +.
- **Lo fijo abajo no tapa el foco:** la capa base ya trae el `scroll-padding-bottom` (DISENO.md 3).

### 7.5 Estado nunca solo por color

| Estado | Palabra | Forma |
|---|---|---|
| Estado del pedido y de cada parte | El texto de la `Etiqueta` (4.2, 4.3) | El ícono propio de cada estado |
| Faltaron | «Faltaron `{n}`» | `PackageX` |
| Devolución hecha o en curso | «Devolvimos» o «Estamos devolviendo» | `Undo2`, y la fecha solo en las hechas |
| Retracto pedido, devuelto o no aceptado | «Devolución pedida», «Devuelto el…», «No se aceptó la devolución» | `Clock`, `CircleCheck` y `CircleX` |
| Plazo vencido | La frase de 4.6.1 | Sin botón |
| Sello del producto | «Si abres el sello, ya no se puede devolver.» | En negrita, en su línea |

### 7.6 Regiones vivas (`aria-live`)

| Qué | Región |
|---|---|
| Error al traer la lista, el detalle o el formulario | `Anunciado urgencia="alert"` |
| «Cargando…» y «Cargando más…» | `aria-busy` en la región. No se anuncian |
| Retracto hecho (5.6) y cancelación hecha (6.3) | `Nota` con `rol="status"` |
| «Este pedido ya se canceló.» | `Nota` con `rol="status"` |
| Ya se pidió (5.7) y ya se prepara (6.3) | `Nota` con `rol="alert"` |
| Nada elegido, cantidad fuera de rango y sin conexión al enviar | `MensajeError` y `anunciar(…, 'alert')` |
| Error en el diálogo | La región de error del diálogo, `rol="alert"` |
| La lista o el detalle se actualizan solos | **No se anuncian** |
| El resumen de la devolución cambia | **No se anuncia** (5.4) |

### 7.7 Texto al 200 % a 320 px (160 px de app, modo `angosto`)

- Todo va en una columna. Las filas, las partes, las líneas y el resumen pasan a `px-2`.
- **La fila:** la cola «·» de la primera línea y la del total se ocultan (`angosto:hidden`), y la fecha y «Devuelto:» bajan a su renglón (`angosto:block`, DISENO.md 2). La `Etiqueta` muestra solo la palabra.
- **«Entregado el 04/11/2026»** en la `Etiqueta`: la fecha va en `cifras`, y la etiqueta envuelve entre «el» y la fecha (`max-w-full`), sin partir la cifra.
- **El `Stepper`** baja de renglón por `flex-wrap`, como en MATU-61 13.7.
- **Los renglones del comprobante** pasan a `angosto:flex-col angosto:items-start`, como en MATU-62 7.5.1.
- **Los botones** de 4.6, del resumen y del diálogo van uno bajo otro, a todo el ancho, con el relleno de su variante (DISENO.md 3, `angosto:`).
- **Las pestañas** pasan a tres o cuatro renglones, sin desplazamiento.
- `document.documentElement.scrollWidth` es igual a `clientWidth` en las tres rutas y con el diálogo abierto.

### 7.8 Movimiento

Sin transiciones al llegar a una ruta y sin páginas que entran deslizándose. Las notas aparecen con el fundido `aparecer` de 180 ms, y con `prefers-reduced-motion` aparecen de inmediato (ya en la capa base). El diálogo abre sin animación.

### 7.9 Tema oscuro y proyector

Solo tokens. En la revisión miro:
- las `Etiqueta` `neutro` y `atenta` en el oscuro;
- `Undo2` en `atenta` sobre `papel` oscuro;
- la máscara del borde cortado del resumen, que no deje una línea clara.

Ningún texto usa `text-sm`. El tema claro es el de la presentación.

---

## 8. Lo que el frontend no debe hacer

- Deducir del rol en memoria si se puede cancelar o arrepentirse, o por qué no (C7, O1).
- Cambiar el estado, mostrar «Cancelado» o restar un monto antes de que responda el servidor (C10).
- Mostrar `ultimos4`, la tarjeta o el código de autorización si no llegaron, o completarlos con datos de otra vista (C17).
- Mostrar el código de retiro, la referencia de la parte o un campo `codigo_*`, aunque llegue por error. Si llega, es un defecto del contrato (C15).
- Guardar el pedido elegido, lo elegido para devolver o la `Idempotency-Key` en `localStorage`, `sessionStorage`, la URL o el historial.
- Filtrar los pedidos vencidos por su cuenta (C27).
- Usar la palabra del contrato para el retracto no aceptado, ni «fallido», «stock», «reserva», «con IVA» o «código de retiro» (C26).
- Escribir colores, tamaños o sombras a mano (CLAUDE.md, 5.9).
- Usar flechas en los botones o `ChevronRight` en las filas (DISENO.md 5).

---

## 9. Textos para `lenguaje.md`, sección 38 «Tus pedidos (MATU-92)»

La tabla de la revisión previa, con lo que suma o cambia esta especificación. El frontend los pone en `familia/textosPedidos.ts` (o en el archivo que elija), nunca sueltos en el componente.

| Dónde | Texto | Origen |
|---|---|---|
| Pestaña y título | Tus pedidos | [L 38] |
| `<title>` | Tus pedidos · MATU · Pedido `{referencia}` · MATU · Arrepentirme de la compra · MATU | [L 38] · **[NUEVO]** el tercero |
| Bajada | Los pedidos pagados de `{pila}`, de los últimos 2 años. | [L 38] |
| Vacío | Todavía no hay pedidos pagados para `{pila}`. · Ir a tu pedido | [L 38] · [L 31] |
| Fila | Pedido `{referencia}` · `{DD/MM/AAAA}` · Total pagado: `{total}` · Devuelto: `{monto}` | [L 38] · **[NUEVO]** «Devuelto:» |
| Fila, productos (O5) | `{producto}` y `{n}` productos más · y 1 producto más | **[NUEVO]** |
| Ver más | Ver más pedidos · Cargando más… · No pudimos traer más pedidos. Revisa tu conexión y vuelve a intentarlo. | **[NUEVO]** |
| Capa 3 apagada | Tus pedidos no están disponibles por ahora. | **[NUEVO]** |
| Observador | Quien administra el grupo, quien cuida a `{pila}` y quien paga ven el detalle. | [L 38] **[AJUSTE]**, sin «Pagado ·» |
| Bloque en «Pedido» | Tus pedidos · Ver todos tus pedidos | [L 38] · **[NUEVO]** |
| Desde el comprobante | Ver cómo va tu pedido | **[NUEVO]** |
| Estados | Los de [L 38] (4.2) · Cancelado · Estamos devolviendo `{total}`, envío incluido, a la tarjeta con que se pagó. | [L 38] · **[AJUSTE]** la devolución en curso |
| Detalle | Volver a tus pedidos · Pagado el `{DD/MM/AAAA}` a las `{HH:MM}` | **[NUEVO]** |
| Cómo va | Cómo va · De `{comercio}` (comercio ficticio) · De un comercio · Faltaron `{n}` | **[NUEVO]** · [L 38] · **[NUEVO]** (v1.2, sin el nombre del comercio) · **[NUEVO]** |
| Partes | Enviado al comercio · En preparación · Listo para salir · Salió del comercio · No tenía estos productos · Cancelado | [L 38] · **[NUEVO]** las dos del medio |
| Dinero devuelto | Dinero devuelto · El `{DD/MM/AAAA}` · Faltaron `{n}` de `{producto}`. Devolvimos `{monto}` a la tarjeta con que se pagó. Cuándo se ve en la cuenta depende del banco. · Devolvimos el envío: `{monto}`. · las de [L 32] y [L 36] | **[NUEVO]** el título y la fecha · [L 38] |
| Productos para devolver | Productos para devolver · Devolución pedida · Devuelto el `{DD/MM/AAAA}` · No se aceptó la devolución. Si tienes dudas, escríbenos a `{correo}`. · La pidió otra persona de tu grupo. | **[NUEVO]** · [L 38] · **[NUEVO]** |
| Por correo | Esta devolución la pediste por correo. La registró el equipo de MATU. · Esta devolución se pidió por correo. La registró el equipo de MATU. | [L 38] · **[AJUSTE]** |
| Arrepentirse, bloque | Arrepentirme de la compra · la ayuda de [L 36] · Pueden arrepentirse de la compra quien administra el grupo y quien la pagó. · Ya pediste devolver todos los productos de este pedido. | [L 36] · [L 38] · **[NUEVO]** |
| Plazo vencido | Los dos de [L 38] | [L 38] |
| Arrepentirse, pantalla | Volver al pedido `{referencia}` · Elige qué productos devuelves · Recibiste `{n}`. Pagaste `{precio}` cada uno. · Ya pediste devolver `{n}`. · ¿Cuántos devuelves? · Para el lector: Uno menos: `{producto}` · Uno más: `{producto}` · Puedes devolver hasta `{n}`. · Ya pediste devolver todos. · Escribe un número de 0 a `{n}`. | **[NUEVO]** · [L 36] el segundo |
| Resumen | Lo que vas a devolver · Todavía no eliges ningún producto. · Vas a devolver: (en lista) · Te devolvemos `{monto}` cuando recibamos los productos con su sello cerrado. · También te devolvemos el envío. · Si abres el sello, ya no se puede devolver. · Devolver estos productos · No, volver · Enviando… | **[NUEVO]** · [L 38] **[AJUSTE]** «Vas a devolver:» en lista |
| Resultado y errores | Elige al menos un producto y cuántos devuelves. · Recibimos tu pedido de devolución. Te escribimos para coordinar el retiro. · No pudimos enviar tu pedido de devolución. Revisa tu conexión y vuelve a intentarlo. Lo que elegiste sigue aquí. · Otra persona de tu grupo ya pidió devolver algunos de estos productos. Te mostramos lo que todavía puedes devolver. Revisa lo que elegiste antes de enviarlo. | [L 38] · [L 36] · **[NUEVO]** · **[NUEVO]** |
| Cancelar, bloque | Cancelar el pedido · Puedes cancelarlo sin costo mientras el comercio no empiece a prepararlo. · Solo quien administra el grupo puede cancelar un pedido pagado, mientras el comercio no empiece a prepararlo. | [L 36] · **[NUEVO]** · [L 38] |
| Cancelar, diálogo | Los de [L 38] · Pago de prueba. No se cobró dinero real. | [L 38] · [L 32] |
| Cancelar, resultado | Cancelamos el pedido. Estamos devolviendo `{total}` a la tarjeta con que se pagó. · Este pedido ya se canceló. Te mostramos cómo quedó. · Ya están preparando tu pedido, así que no se puede cancelar. Cuando llegue, puedes arrepentirte de la compra. · No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo. Todo sigue como estaba. · No pudimos cancelar el pedido. Revisa tu conexión y vuelve a intentarlo. | [L 38] · [L 38] · [L 36] · [L 31] · **[NUEVO]** (v1.2, cuando no se pudo volver a leer el pedido) |
| Productos borrados | De este pedido guardamos solo lo que se pagó y lo que se devolvió. | [L 38] |
| Errores | No pudimos traer tus pedidos. Revisa tu conexión y vuelve a intentarlo. · Volver a intentar · No pudimos traer tu pedido. Revisa tu conexión e inténtalo de nuevo. · No pudimos traer el comprobante. Revisa tu conexión y vuelve a intentarlo. · Volver a intentar (en la misma Nota) · No encontramos este pedido. · Volver a tus pedidos | [L 38] · [L 31] · **[NUEVO]** · [L 26] · [L 31] · **[NUEVO]** |

**Ninguno usa** los términos de `lenguaje.md` 3, «código de retiro», «rechazado», «fallido», «stock», «reserva», «con IVA» ni «10 días» sin «hábiles».

---

## 10. Contradicciones entre las fuentes y cómo se resolvieron

Las resolvió el orquestador el 16-11 a las 00:30, en la sección «Decisiones del orquestador sobre las contradicciones del diseñador» de la revisión previa. Todos los textos [NUEVO] y [AJUSTE] van a `lenguaje.md` 38, «Por aprobar por Jorge».

| # | Contradicción | Decisión | Dónde queda |
|---|---|---|---|
| 1 | **«10 días».** [L 27] (el carrito y el resumen) y [L 32] dicen «10 días», contra C20 | **D1:** todos dicen «10 días hábiles», también los de [L 27]. Se cambia en `web/` y en `lenguaje.md` 27 y 32 | 4.7, criterio 10 |
| 2 | **El cancelado con la devolución en curso** dice «Devolvimos», mientras «Cancelar, hecho» dice «Estamos devolviendo» | **D2:** se acepta el [AJUSTE]. Mientras está en curso, «Estamos devolviendo…»; cuando se confirma la anulación, «Devolvimos…» | 4.2 |
| 3 | **El faltante parcial de quien pagó:** «Te devolvimos…» en [L 36] contra «Devolvimos… a tu tarjeta» en [L 32] | **D3:** quien pagó lee [L 36], «Te devolvimos `{monto}` a tu tarjeta terminada en `{ultimos4}`…». Quien no pagó lee [L 38] | 4.4, primera fila |
| 4 | **«Por correo»** dice «la pediste» aunque no la haya pedido quien mira | **D4:** con `es_tuyo`, «la pediste por correo»; sin él, «se pidió por correo». Se acepta el [AJUSTE] | 4.5 |
| 5 | **«Pagos anulados»** del encargo, contra «Anulamos tu pago» de [L 32] | **D5:** el título es «Dinero devuelto» | 4.4, O4 |
| 6 | **La frase del observador** empieza con «Pagado ·», que repite la `Etiqueta` | **Sin decisión explícita.** Se construye con el [AJUSTE] (sin «Pagado ·») hasta que Jorge apruebe la sección 38 | 3.4 |
| 7 | **C7 (la pantalla no deduce) contra los textos por motivo** | **D6:** el contrato trae `cancelar_motivo` y `arrepentirse_motivo`. Ya se le pidió al backend | O1, 4.6 |
| 8 | **C9 (el monto antes de confirmar) contra MATU-61 14 (la pantalla no calcula montos)** | **D7:** la suma pura del frontend es solo una vista previa, y el monto que manda es el del `POST` | O2, 5.4 |
| 9 | **MATU-62 §8** («Pedido pagado» al final de «Pedido») | **D8:** queda reemplazado por 2.3. `matu-62-pago.md` §8 ya está actualizado, en la v1.2 | 2.3 |

---

## 11. Criterios visuales verificables

1. En la lista y en el detalle **no hay ningún elemento en `turquesa` macizo**, salvo «Volver a intentar» en el error al traer.
2. En «Arrepentirme de la compra», **«Devolver estos productos» es el único elemento en `turquesa` macizo**, y mide lo que su texto (no va a todo el ancho de la columna a 1280 px).
3. Cada estado del pedido, de una parte y de un retracto se ve con **palabra e ícono**. Con el texto al 200 %, la palabra queda.
4. Ninguna `Etiqueta`, texto o ícono de estado usa `turquesa`.
5. La fila de la lista es un único `button` cuyo nombre accesible es su texto visible, sin `ChevronRight` ni flecha. Para el observador, la fila no es un `button` y no recibe el foco.
6. El observador no ve la referencia, el total, lo devuelto, la explicación de H8, ningún detalle ni ningún botón.
7. En ninguna de las tres rutas aparece «código de retiro», un campo `codigo_*` ni la referencia de la parte, en la pantalla ni en el DOM.
8. `{ultimos4}` solo aparece para quien pagó. Para quien no pagó, el texto dice «la tarjeta con que se pagó».
9. Ningún texto visible mide menos de 17 px (`text-base`), salvo el rótulo de la barra en `estrecho:`.
10. «10 días» nunca aparece sin «hábiles» en las tres rutas.
11. Después de cancelar, el estado cambia **solo cuando responde el servidor**: con la red lenta (Chrome, «Slow 3G»), el diálogo sigue abierto con «Cancelando…» y el detalle no cambia.
12. Después de cancelar o de pedir una devolución, el foco está en la nota o en el `h1`, nunca en `body`.
13. Con el texto al 200 % a 320 px, `scrollWidth` es igual a `clientWidth` en las tres rutas y con el diálogo abierto.
14. A 360 px, «Tus pedidos» cabe en el segundo renglón de las pestañas o baja sola a un tercero, sin desplazamiento.
15. A 1280 y 1920 px, el comprobante del detalle va a la derecha, pegajoso y sin estirarse más de unos 470 px, y el resumen de la devolución va a la derecha con sus dos botones.
16. Con `prefers-reduced-motion`, las notas aparecen sin fundido.
17. Con el tema oscuro, toda `Etiqueta` y todo `Undo2` cumplen 3:1 o más contra su fondo, y el texto, 4,5:1 o más.

---

## 12. Cómo la voy a revisar

- Con la app funcionando, con los datos sintéticos de Carmen, María, Rosa y Rodrigo. Necesito pedidos pagados en cuatro estados: `pagado`, `preparando`, `entregado` con un faltante parcial y una devolución de envío, y `cancelado_con_devolucion`. También un retracto `solicitado` y uno por correo.
- Con capturas a 360, 1280 y 1920 px, en tema claro y oscuro, y una con «Texto al 200 %» a 320 px, de:
  - la lista, como admin y como observador;
  - el detalle, como pagador que pagó y como cuidador;
  - arrepentirse, con un producto elegido y con todos;
  - el diálogo de cancelar;
  - el 422 de 5.7.
- Con el teclado solo: el orden de Tab, el foco después de cada acción y `Esc` en el diálogo.
- Mido el contraste de las `Etiqueta` `neutro` y `atenta` y de `Undo2` en los dos temas.
